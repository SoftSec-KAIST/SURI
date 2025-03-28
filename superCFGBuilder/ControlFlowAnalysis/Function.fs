(*
  B2R2 - the Next-Generation Reversing Platform

  Copyright (c) SoftSec Lab. @ KAIST, since 2016

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
*)

namespace SuperCFG.ControlFlowAnalysis

open System.Collections.Generic
open System.Runtime.InteropServices
open B2R2
open B2R2.FrontEnd
open SuperCFG.BinGraph
open SuperCFG.ControlFlowGraph

/// Function can be either external or regualr.
type FunctionKind =
  /// Regular function.
  | Regular = 0
  /// External function.
  | External = 1

/// Callee's kind.
type CalleeKind =
  /// Callee is a regular function.
  | RegularCallee of Addr
  /// Callee is a set of indirect call targets. This means potential callees
  /// have been analyzed already.
  | IndirectCallees of Set<Addr>
  /// Callee (call target) is unresolved yet. This eventually will become
  /// IndirectCallees after indirect call analyses.
  | UnresolvedIndirectCallees
  /// There can be "call 0" to call an external function. This pattern is
  /// typically observed by object files, but sometimes we do see this pattern
  /// in regular executables, e.g., GNU libc.
  | NullCallee

/// NoReturnProperty of a function specifies whether the function will
/// eventually return or not. Some functions, e.g., exit, will never return in
/// any cases, and compilers often remove fall-through edges of callers of such
/// functions.
type NoReturnProperty =
  /// This function will never return. For example, the "exit" function should
  /// have this property.
  | NoRet
  /// Conditionally no-return; function does not return only if the n-th
  /// argument (starting from one) specified is non-zero.
  | ConditionalNoRet of int
  /// Regular case: this is *not* no-return, and we have already performed
  /// parameter analysis to examine the possibility of being conditional no-ret.
  | NotNoRetConfirmed
  /// Regular case: *not* no-return.
  | NotNoRet
  /// When we are not certain: we need further analyses.
  | UnknownNoRet

/// Indirect jump's kind.
type IndirectJumpKind =
  /// We did not analyzed this indirect jump yet.
  | YetAnalyzed
  /// We found jump targets for this indirect jump, but this does not use a jump
  /// table.
  | KnownJumpTargets of Set<Addr>
  /// We found a corresponding jump table at Addr.
  | JmpTbl of tAddr: Addr
  /// We analyzed the given jump, and we could not determine its kind.
  | UnknownIndJmp

/// Function is a non-overlapping chunk of code in a binary. We do not allow
/// function overlaps. When there exist two functions sharing common basic
/// blocks, B2R2 will create a new function to represent the common blocks.
/// Function can also represent a function defined outside of the current
/// binary. Such functions are called ExternalFunction.
[<AbstractClass>]
type Function (entryPoint, name) =
  let fid = Addr.toFuncName entryPoint
  let callers = SortedSet<Addr> ()
  let mutable noRetProp = UnknownNoRet

  /// Starting address of the function.
  member __.EntryPoint with get(): Addr = entryPoint

  /// Function's unique ID. This field is used to distinguish between functions.
  member __.FunctionID with get(): string = fid

  /// Function's symbolic name.
  member __.FunctionName with get(): string = name

  /// Function's kind. Is this external or regular?
  abstract FunctionKind: FunctionKind

  /// A set of functions which call this function.
  member __.Callers with get() = callers

  /// Register a set of callers to this function.
  member __.RegisterCallers (newCallers: Set<Addr>) =
    callers.UnionWith newCallers

  /// No-return property of this function.
  member __.NoReturnProperty
    with get() = noRetProp and set(b) = noRetProp <- b

/// FakeEdge is a tuple of (Callsite address, Call target address). This is to
/// uniquely identify edges from a call instruction to a fake block. Note that
/// even though there are multiple calls to the same outer function, each of the
/// callsites should be connected to an independent fake block. That's the
/// reason why we use FakeEdge to distinguish them.
type FakeEdge = Addr * Addr

module private RegularFunction =
  /// This is a heuristic to discover __x86.get_pc_thunk- family functions.
  /// We directly compare first 4 bytes of byte code. Because
  /// __x86.get_pc_thunk- family only has 4 bytes for its function body and
  /// their values are fixed.
  let obtainGetPCThunkReg (hdl: BinHandle) isa (addr: Addr) =
    match isa.Arch with
    | Architecture.IntelX86 ->
      match hdl.ReadUInt (addr, 4) with
      | 0xc324048bUL -> YesGetPCThunk <| hdl.RegisterFactory.RegIDFromString "EAX"
      | 0xc3241c8bUL -> YesGetPCThunk <| hdl.RegisterFactory.RegIDFromString "EBX"
      | 0xc3240c8bUL -> YesGetPCThunk <| hdl.RegisterFactory.RegIDFromString "ECX"
      | 0xc324148bUL -> YesGetPCThunk <| hdl.RegisterFactory.RegIDFromString "EDX"
      | 0xc324348bUL -> YesGetPCThunk <| hdl.RegisterFactory.RegIDFromString "ESI"
      | 0xc3243c8bUL -> YesGetPCThunk <| hdl.RegisterFactory.RegIDFromString "EDI"
      | 0xc3242c8bUL -> YesGetPCThunk <| hdl.RegisterFactory.RegIDFromString "EBP"
      | _ -> NoGetPCThunk
    | _ -> NoGetPCThunk

/// Regular function is a function that has its own body in the target binary.
/// Therefore, regular functions have their own IR-level CFG.
type RegularFunction private (histMgr: HistoryManager, ep, name, thunkInfo) =
  inherit Function (ep, name)

  let callEdges = SortedList<Addr, CalleeKind> ()
  let syscallSites = SortedSet<Addr> ()

  let defChains = Dictionary<Addr, Addr list list> ()

  let useChains = Dictionary<Addr, Addr list list> ()

  let jmpTblDict = Dictionary<Addr, uint64> ()

  let indirectJumps = Dictionary<Addr, Set<IndirectJumpKind>> ()

  let indJmpBBLs = Dictionary<Addr, ProgramPoint> ()

  let invalidAddrs = SortedSet<Addr> ()

  let markedTbls = SortedSet<Addr> ()

  let checkedTblCandidate = SortedSet<Addr*Addr> ()

  let unsolvedEdges = SortedSet<Addr*Addr*CFGEdgeKind>()

  let absorbingFuns = List<Addr>()

  let unreachableFuns = List<Addr>()

  let discardedEdges = List<Addr*Addr>()

  let regularVertices = Dictionary<ProgramPoint, Vertex<IRBasicBlock>> ()
  let fakeVertices = Dictionary<FakeEdge, Vertex<IRBasicBlock>> ()
  let coverage = CoverageMaintainer ()
  let mutable callEdgeChanged = false
  let mutable needRecalcSSA = true
  let mutable ircfg = IRCFG.init PersistentGraph
  let mutable ssacfg = SSACFG.init PersistentGraph
  let mutable amountUnwinding = 0L
  let mutable getPCThunkInfo = thunkInfo
  let mutable minAddr = ep
  let mutable maxAddr = ep

  let fdeRanges = SortedSet<Addr*Addr> ()

  /// Create a new RegularFunction.
  new (histMgr, hdl: BinHandle, isa, ep) =
    let name =
      match hdl.File.TryFindFunctionName ep with
      | Error _ -> Addr.toFuncName ep
      | Ok name -> name
    let thunkInfo = RegularFunction.obtainGetPCThunkReg hdl isa ep
    RegularFunction (histMgr, ep, name, thunkInfo)

  override __.FunctionKind with get() = FunctionKind.Regular

  /// A sequence of call edges (call site address, callee). That is, a CallEdge
  /// represents a function call edge from the caller bbl to its callee(s).
  member __.CallEdges with get() =
    callEdges
    |> Seq.map (fun (KeyValue (pp, callee)) -> pp, callee)
    |> Seq.toArray

  /// Is the given indirect call unresolved?
  member __.IsUnresolvedIndirectCall callSiteAddr =
    match callEdges.TryGetValue callSiteAddr with
    | true, UnresolvedIndirectCallees -> true
    | _ -> false

  /// Returns the set of call target addresses. This function returns the
  /// correct set regardless of their callee types; for indirect calls, it
  /// returns a set of resolved target addresses, and for direct calls, it
  /// returns a singleton target address set.
  member __.CallTargets callSiteAddr =
    match callEdges.TryGetValue callSiteAddr with
    | true, IndirectCallees targets -> targets
    | true, RegularCallee addr -> Set.singleton addr
    | _ -> Set.empty

  /// Remove call edge information from this function.
  member __.ClearCallEdges () = callEdges.Clear ()

  /// Return only a sequence of unresolved indirect call edge info: a tuple of
  /// (call site addr, fall-through addr).
  member __.UnresolvedIndirectCallEdges with get() =
    __.CallEdges
    |> Array.choose (fun (callSiteAddr, callee) ->
      match callee with
      | UnresolvedIndirectCallees -> Some callSiteAddr
      | _ -> None)

  /// A set of bbl entry points which have syscall at the end of each.
  member __.SyscallSites with get() = syscallSites

  /// Add a syscall callsite.
  member __.AddSysCallSite callSiteAddr =
    syscallSites.Add callSiteAddr |> ignore

  /// Remove the syscall callsite.
  member __.RemoveSysCallSite callSiteAddr =
    syscallSites.Remove callSiteAddr |> ignore

  /// IR-level CFG of this function.
  member __.IRCFG
    with get() = ircfg
    and private set(cfg) = ircfg <- cfg; needRecalcSSA <- true

  /// Check if the given vertex exists in this function.
  member __.HasVertex (v) = regularVertices.ContainsKey v

  /// Find an IRCFG vertex at the given program point.
  member __.FindVertex (pp) = regularVertices[pp]

  /// Try to find an IRCFG vertex at the given program point.
  member __.TryFindVertex (pp) =
    regularVertices.TryGetValue pp |> Utils.tupleResultToOpt

  /// Return the current number of regular vertices in this function's IRCFG.
  member __.CountRegularVertices with get() = regularVertices.Count

  /// Fold each regular vertex in this function.
  member __.FoldRegularVertices fn acc = regularVertices |> Seq.fold fn acc

  /// Iterate each regular vertex's program points.
  member __.IterRegularVertexPps fn =
    regularVertices.Keys |> Seq.iter fn

  /// Add a vertex of a parsed regular basic block to this function.
  member __.AddVertex (blk: IRBasicBlock) =
    let v, g = __.IRCFG.AddVertex blk
    __.IRCFG <- g
    regularVertices[blk.PPoint] <- v
    coverage.AddCoverage blk.Range
    v

  /// Add a parsed regular basic block (given as an array of instructions along
  /// with its leader address) to this function.
  member __.AddVertex (instrs, leader) =
    let blk = IRBasicBlock.initRegular instrs leader
    __.AddVertex blk

  /// Add/replace a regular edge to this function.
  member __.AddEdge (srcPp, dstPp, edge) =
    let src = regularVertices[srcPp]
    let dst = regularVertices[dstPp]
    __.IRCFG <- __.IRCFG.AddEdge (src, dst, edge)

  member private __.AddFakeVertex edgeKey bbl =
    let v, g = __.IRCFG.AddVertex bbl
    __.IRCFG <- g
    fakeVertices[edgeKey] <- v
    v

  /// Find a call fake block from callSite to callee. The third arg (isTailCall)
  /// indicates whether this is a tail call.
  member private __.GetOrAddFakeVertex (callSite, callee, isTailCall) =
    let edgeKey = callSite, callee
    match fakeVertices.TryGetValue (edgeKey) with
    | true, v -> v
    | _ ->
      let bbl = (* When callee = 0UL, then it means an indirect call. *)
        if callee = 0UL then
          IRBasicBlock.initIndirectCallBlock callSite isTailCall
        else IRBasicBlock.initCallBlock callee callSite isTailCall
      __.AddFakeVertex edgeKey bbl

  /// Add/replace a direct call edge to this function.
  member __.AddEdge (callerBlk, callSite, callee, isTailCall) =
    let src = regularVertices[callerBlk]
    let dst = __.GetOrAddFakeVertex (callSite, callee, isTailCall)
    callEdges[callSite] <-
      if callee = 0UL then NullCallee else RegularCallee callee
    callEdgeChanged <- true
    __.IRCFG <- DiGraph.AddEdge (__.IRCFG, src, dst, CallEdge)

  /// Add/replace an indirect call edge to this function.
  member __.AddEdge (callerBlk, callSite, knownCallee, isTailCall) =
    let src = regularVertices[callerBlk]
    let dst = __.GetOrAddFakeVertex (callSite, 0UL, isTailCall)
    match knownCallee with
    | Some callee -> callEdges[callSite] <- callee
    | None -> callEdges[callSite] <- UnresolvedIndirectCallees
    callEdgeChanged <- true
    __.IRCFG <- DiGraph.AddEdge (__.IRCFG, src, dst, IndirectCallEdge)

  /// Add/replace a ret edge to this function.
  member __.AddEdge (callSite, callee, ftAddr) =
    let src = __.GetOrAddFakeVertex (callSite, callee, false)
    let dst = regularVertices[(ProgramPoint (ftAddr, 0))]
    __.IRCFG <- DiGraph.AddEdge (__.IRCFG, src, dst, RetEdge)

  /// Update the call edge info.
  member __.UpdateCallEdgeInfo (callSiteAddr, callee) =
    callEdges[callSiteAddr] <- callee
    callEdgeChanged <- true

  /// Remove the basic block at the given program point from this function.
  member private __.RemoveVertex (v: Vertex<IRBasicBlock>) =
    __.IRCFG <- DiGraph.RemoveVertex (__.IRCFG, v)
    if v.VData.IsFakeBlock () then
      let callSite = v.VData.FakeBlockInfo.CallSite
      let edgeKey = callSite, v.VData.PPoint.Address
      fakeVertices.Remove (edgeKey) |> ignore
      callEdges.Remove callSite |> ignore
    else
      regularVertices.Remove v.VData.PPoint |> ignore
      coverage.RemoveCoverage v.VData.Range

  /// Remove the regular basic block at the given program point from this
  /// function.
  member __.RemoveVertex (pp: ProgramPoint) =
    regularVertices[pp] |> __.RemoveVertex

  /// Remove the fake block from this function.
  member __.RemoveFakeVertex ((callSite, _) as fakeEdgeKey) =
    let v = fakeVertices[fakeEdgeKey]
    __.IRCFG <- DiGraph.RemoveVertex (__.IRCFG, v)
    fakeVertices.Remove (fakeEdgeKey) |> ignore
    callEdges.Remove callSite |> ignore

  /// Remove the given edge.
  member __.RemoveEdge (src, dst) =
    __.IRCFG <- DiGraph.RemoveEdge (__.IRCFG, src, dst)

  /// Remove the given edge.
  member __.RemoveEdge (src, dst, _kind) =
    __.IRCFG <- DiGraph.RemoveEdge (__.IRCFG, src, dst)

  static member AddEdgeByType (fn: RegularFunction)
                              (src: Vertex<IRBasicBlock>)
                              (dst: Vertex<IRBasicBlock>) e =
    match e with
    | CallEdge ->
      let callSite = dst.VData.FakeBlockInfo.CallSite
      let callee = dst.VData.PPoint.Address
      let isTailCall = dst.VData.FakeBlockInfo.IsTailCall
      fn.AddEdge (src.VData.PPoint, callSite, callee, isTailCall)
    | IndirectCallEdge ->
      let callSite = dst.VData.FakeBlockInfo.CallSite
      let isTailCall = dst.VData.FakeBlockInfo.IsTailCall
      fn.AddEdge (src.VData.PPoint, callSite, None, isTailCall)
    | RetEdge ->
      let callSite = src.VData.FakeBlockInfo.CallSite
      let ftAddr = dst.VData.PPoint.Address
      fn.AddEdge (callSite, src.VData.PPoint.Address, ftAddr)
    | _ -> (* regular edges *)
      fn.AddEdge (src.VData.PPoint, dst.VData.PPoint, e)

  /// Split the given IR-level vertex (v) at the given point (splitPoint), and
  /// add the resulting vertices to the graph.
  member private __.AddByDividingVertex v (splitPoint: ProgramPoint) =
    let insInfos = (v: Vertex<IRBasicBlock>).VData.InsInfos
    let srcInfos, dstInfos =
      insInfos
      |> Array.partition (fun insInfo ->
        insInfo.Instruction.Address < splitPoint.Address)
    let dstInfos =
      dstInfos
      |> Array.map (fun insInfo ->
        { insInfo with BBLAddr = splitPoint.Address })
    let srcBlk = IRBasicBlock.initRegular srcInfos v.VData.PPoint
    let dstBlk = IRBasicBlock.initRegular dstInfos splitPoint
    let src = __.AddVertex srcBlk
    let dst = __.AddVertex dstBlk
    __.AddEdge (src.VData.PPoint, dst.VData.PPoint, FallThroughEdge)
    struct (src, dst)

  /// Split the BBL at bblPoint into two at the splitPoint. This function
  /// returns the second block located at the splitPoint.
  member __.SplitBBL (bblPoint: ProgramPoint, splitPoint: ProgramPoint) =
    assert (bblPoint < splitPoint)
    let v = regularVertices[bblPoint]
    let ins, outs, cycle = categorizeNeighboringEdges __.IRCFG v
    ins |> List.iter (fun (p, kind) -> __.RemoveEdge (p, v, kind))
    outs |> List.iter (fun (s, kind) -> __.RemoveEdge (v, s, kind))
    cycle |> Option.iter (fun kind -> __.RemoveEdge (v, v, kind))
    __.RemoveVertex v
    let struct (src, dst) = __.AddByDividingVertex v splitPoint
    ins |> List.iter (fun (p, e) -> RegularFunction.AddEdgeByType __ p src e)
    outs |> List.iter (fun (s, e) -> RegularFunction.AddEdgeByType __ dst s e)
    cycle |> Option.iter (fun e -> RegularFunction.AddEdgeByType __ dst src e)
    dst

  member private __.GetMergedVertex srcV dstV insAddrs chunk =
    let src = (srcV: IRVertex).VData.InsInfos
    let dst = (dstV: IRVertex).VData.InsInfos
    let fstAddr = List.head insAddrs
    let lastAddr = List.last insAddrs
    let chunkIdx =
      src |> Array.findIndex (fun i -> i.Instruction.Address >= fstAddr)
    let backIdx =
      dst |> Array.findIndexBack (fun i -> i.Instruction.Address <= lastAddr)
    let front = src[0 .. chunkIdx - 1]
    let back = dst[backIdx + 1 .. dst.Length - 1]
    let lastInsInfo = dst[backIdx]
    let chunkInfo =
      [| { Instruction = chunk;
           Stmts = lastInsInfo.Stmts;
           BBLAddr = src[0].BBLAddr } |]
    let insInfos = Array.concat [ front; chunkInfo; back ]
    IRBasicBlock.initRegular insInfos srcV.VData.PPoint
    |> __.AddVertex

  /// Merge two vertices connected with an inlined assembly chunk, where there
  /// is a control-flow to the middle of an instruction.
  member __.MergeVerticesWithInlinedAsmChunk (insAddrs,
                                              srcPp,
                                              dstLeaders,
                                              chunk) =
    let minPp = Set.minElement (dstLeaders: Set<ProgramPoint>)
    let dstLeaders =
      Set.filter (fun (leader: ProgramPoint) ->
        leader.Address = minPp.Address) dstLeaders
    let src = regularVertices[srcPp]
    let ins, _, _ = categorizeNeighboringEdges __.IRCFG src
    (* Here, we have an assumption that the inlined asm chunk should fall
       through to the next instruction. If we want to handle inlined asm chunks
       without the assumption, then we should FIX the below logic. *)
    let lastLeader = Set.maxElement dstLeaders
    let lastV = regularVertices[lastLeader]
    let _, outs, _ = categorizeNeighboringEdges __.IRCFG lastV
    regularVertices.Remove srcPp |> ignore
    Set.iter (fun pp ->
      let v = regularVertices[pp]
      __.RemoveVertex v
      regularVertices.Remove pp |> ignore) dstLeaders
    __.RemoveVertex src
    let v = __.GetMergedVertex src lastV insAddrs chunk
    ins |> List.iter (fun (p, e) ->
      (* When the incoming edge is from the merged vertex. This logic also
         assumes the assumption described in the above. *)
      if p.VData.PPoint = lastLeader then RegularFunction.AddEdgeByType __ v v e
      else RegularFunction.AddEdgeByType __ p v e)
    outs |> List.iter (fun (s, e) ->
      (* When the outgoing edge is to the merged vertex. What we should be aware
         of is when the successor is a fake-block. *)
      if s.VData.PPoint = srcPp && not <| s.VData.IsFakeBlock () then
        RegularFunction.AddEdgeByType __ v v e
      else RegularFunction.AddEdgeByType __ v s e)
    regularVertices[v.VData.PPoint] <- v

  member private __.AddCallEdge callSite callee =
    callEdges[callSite] <- callee

  member private __.RemoveCallEdge callSite =
    callEdges.Remove callSite |> ignore

  member private __.AddDefChains insAddr defs =
    if defChains.ContainsKey insAddr then
      defChains[insAddr] <- defs::defChains[insAddr]
    else
      defChains[insAddr] <- [defs]

  member private __.AddUseChains insAddr uses =
    if useChains.ContainsKey insAddr then
      useChains[insAddr] <- uses::useChains[insAddr]
    else
      useChains[insAddr] <- [uses]

  member private __.AddIndirectJump insAddr jmpKind =
    if indirectJumps.ContainsKey insAddr then
      if indirectJumps[insAddr] = Set.empty.Add (YetAnalyzed) then
        indirectJumps[insAddr] <- Set.empty.Add(jmpKind)
      else
        indirectJumps[insAddr] <- indirectJumps[insAddr]
                                  |> Set.filter(fun jmp -> jmp <> YetAnalyzed)
        indirectJumps[insAddr] <- indirectJumps[insAddr].Add(jmpKind)
    else
      indirectJumps[insAddr] <- Set.empty.Add(jmpKind)

  member __.UpdateIndJmpBBLeader insAddr leader =
    indJmpBBLs[insAddr] <- leader

  member private __.RemoveIndirectJump insAddr =
    indirectJumps.Remove insAddr |> ignore

  /// This field indicates the amount of stack unwinding happening at the return
  /// of this function. This value is 0 if caller cleans the stack (e.g.,
  /// cdecl). That is, this value is only meaning for calling conventions where
  /// callee cleans up the stack, such as stdcall.
  member __.AmountUnwinding
    with get() = amountUnwinding and set(n) = amountUnwinding <- n

  /// This field is to remember a register ID that holds a PC value. When this
  /// function is deemed as a special thunk (e.g., *_get_pc_thunk), the register
  /// will hold a PC value after this function returns.
  member __.GetPCThunkInfo
    with get() = getPCThunkInfo and set(i) = getPCThunkInfo <- i

  /// Return a Dictionary that maps an indirect jump address to its jump kinds.
  member __.DefChains with get() = defChains

  member __.IndirectJumps with get() = indirectJumps

  member __.JmpTblDict with get() = jmpTblDict

  member __.IndJmpBBLs with get(): Dictionary<Addr, ProgramPoint> = indJmpBBLs

  member __.UnsolvedEdges with get() = unsolvedEdges

  member __.AbsorbingFuns with get() = absorbingFuns

  member __.UnreachableFuns with get() = unreachableFuns

  member __.AddInvalidAddr (addr: Addr) =
    invalidAddrs.Add addr |> ignore

  member __.IsInvalidAddr (addr: Addr) =
    invalidAddrs.Contains addr

  member __.MarkRecoveryDone tblAddr =
    markedTbls.Add tblAddr |> ignore

  member __.IsMarkedTbl tblAddr =
    markedTbls.Contains tblAddr

  member __.RegisterTblCandidate jmpSite candidate =
    checkedTblCandidate.Add (jmpSite, candidate) |> ignore

  member __.IsRegisteredCandidate jmpSite candidate =
    checkedTblCandidate.Contains (jmpSite, candidate)

  member __.RegisterUnsolvedEdges src dst edgeType=
    unsolvedEdges.Add (src, dst, edgeType) |> ignore

  member __.UnregisterUnsolvedEdges (src, dst, edgeType) =
    unsolvedEdges.Remove (src, dst, edgeType)

  member __.ClearUnsolvedEdges () =
    unsolvedEdges.Clear()

  member __.RegisterAbsorber entry =
    absorbingFuns.Add entry

  member __.RegisterUnreachableFun entry =
    unreachableFuns.Add entry
  member __.HasUnsolvedEdges =
    unsolvedEdges.Count > 0

  member __.RegisterDiscardedEdges src dst =
    discardedEdges.Add (src, dst)

  /// Return an array of yet-analyzed indirect jump addresses.
  member __.YetAnalyzedIndirectJumpAddrs
    with get() =
      indirectJumps
      |> Seq.choose (fun (KeyValue (indJumpAddr, kinds)) ->
          if kinds |> Set.contains(YetAnalyzed) then Some indJumpAddr
          else None )
      |> Seq.toList
      (*
      |> Seq.choose (fun (KeyValue (indJumpAddr, kind)) ->
        match kind with
        | YetAnalyzed -> Some indJumpAddr
        | _ -> None)
      |> Seq.toList *)

  /// Retrieve the currently known jump table addresses.
  member __.JumpTableAddrs
    with get() =
      indirectJumps
      |> Seq.choose (fun (KeyValue (_, kinds)) ->
          let tbls = kinds |> Set.fold(fun acc kind ->
                                match kind with
                                | JmpTbl (tAddr) -> tAddr::acc
                                | _ -> acc ) []
          if tbls |> List.isEmpty then None
          else Some tbls )
      |> Seq.toList
      (*
        match kind with
        | JmpTbl (tAddr) -> Some tAddr
        | _ -> None)
      |> Seq.toList *)

  /// Retrieve the jump table address of a given indirect jump address.
  member __.FindJumpTableAddr indJumpAddr =
    match indirectJumps.TryGetValue indJumpAddr with
    | true, kinds ->
      let tbls = kinds |> Set.fold(fun acc kind ->
                        match kind with
                        | JmpTbl (tAddr) -> tAddr::acc
                        | _ -> acc ) []
      if tbls |> List.isEmpty then Utils.impossible()
      else tbls
    | _ -> Utils.impossible ()

  member __.UpdateJTableSize indJumpAddr size =
    jmpTblDict[indJumpAddr] <- size

  member __.RegisterDefChains indJumpAddr ppoints =
    __.AddDefChains indJumpAddr ppoints

   member __.RegisterUseChains leaAddr ppoints =
    __.AddUseChains leaAddr ppoints


  /// Register a new indirect jump as YetAnalyzed.
  member __.RegisterNewIndJump indJumpAddr =
    __.AddIndirectJump indJumpAddr YetAnalyzed

  /// Remove an indirect jump.
  member __.RemoveIndJump indJumpAddr =
    __.RemoveIndirectJump indJumpAddr |> ignore

  /// Mark the given indirect jump as unknown.
  member __.MarkIndJumpAsUnknown indJumpAddr =
    __.AddIndirectJump indJumpAddr UnknownIndJmp

  /// Mark the given indirect jump as unknown.
  member __.MarkIndJumpAsKnownJumpTargets indJumpAddr targets =
    __.AddIndirectJump indJumpAddr (KnownJumpTargets targets)

  /// Mark the given indirect jump as analyzed; we know the table address of it.
  member __.MarkIndJumpAsJumpTbl indJumpAddr tAddr =
    __.AddIndirectJump indJumpAddr (JmpTbl tAddr)

  /// The minimum address of this function's range.
  member __.MinAddr with get() = minAddr and set(a) = minAddr <- a

  /// The maximum address of this function's range.
  member __.MaxAddr with get() = maxAddr and set(a) = maxAddr <- a

  /// Set the boundary of this function; set both MinAddr and MaxAddr.
  member __.SetBoundary minAddr maxAddr =
    __.MinAddr <- minAddr
    __.MaxAddr <- maxAddr

  member __.GetSimpleSSACFG hdl isa =
    let root =
      __.IRCFG.FindVertexBy (fun v ->
        v.VData.PPoint.Address = __.EntryPoint
        && not <| v.VData.IsFakeBlock ())
    let struct (ssa, root) = SSACFG.ofSimpleIRCFG hdl isa __.IRCFG root
    ssa, root

  /// Retrieve the SSA CFG of this function.
  member __.GetSSACFG hdl isa =
    if needRecalcSSA then
      let root =
        __.IRCFG.FindVertexBy (fun v ->
          v.VData.PPoint.Address = __.EntryPoint
          && not <| v.VData.IsFakeBlock ())
      let struct (ssa, root) = SSACFG.ofIRCFG hdl isa __.IRCFG root
      let struct (ssa, root) = SSAPromotion.promote hdl isa ssa root
      ssacfg <- ssa
      needRecalcSSA <- false
      ssa, root
    else
      let root =
        ssacfg.FindVertexBy (fun v ->
          v.VData.PPoint.Address = __.EntryPoint
          && not <| v.VData.IsFakeBlock ())
      ssacfg, root

  member private __.AddXRef entry xrefs callee =
    match Map.tryFind callee xrefs with
    | Some callers -> Map.add callee (Set.add entry callers) xrefs
    | None -> Map.add callee (Set.singleton entry) xrefs

  /// Accumulate cross references only if there is a change in the call edges.
  member __.AccumulateXRefs xrefs =
    if callEdgeChanged then
      callEdgeChanged <- false
      let ep = __.EntryPoint
      callEdges
      |> Seq.fold (fun xrefs (KeyValue (_, callee)) ->
        match callee with
        | RegularCallee callee -> __.AddXRef ep xrefs callee
        | IndirectCallees callees -> Set.fold (__.AddXRef ep) xrefs callees
        | UnresolvedIndirectCallees | NullCallee -> xrefs) xrefs
    else xrefs

  /// Return the sorted gaps' ranges. Each range is a mapping from a start
  /// address to an end address (exclusive).
  member __.GapAddresses
    with get() = coverage.ComputeGapAddrs __.EntryPoint __.MaxAddr

  /// Check if the function regards the given address as a valid instruction
  /// address.
  member __.IsAddressCovered addr =
    coverage.IsAddressCovered addr

  member __.GetUnmarkedJumpTables =
    __.IndirectJumps.Values
    |> Seq.fold (fun acc kinds ->
      kinds
      |> Set.fold (fun acc jmpKind -> match jmpKind with
                                      | JmpTbl tAddr -> tAddr :: acc
                                      | _ -> acc ) acc
      ) []
    |> List.rev
    |> List.filter (__.IsMarkedTbl >> not)

  member __.RegisterFDERange addr1 addr2 =
    fdeRanges.Add (addr1, addr2)

  member __.IsInFDERange addr =
    if Seq.isEmpty fdeRanges then true
    else
      fdeRanges |> List.ofSeq
                |> List.exists(fun (fdeStart, fdeEnd) ->
                                    fdeStart <= addr &&
                                      (addr < fdeEnd || fdeEnd = uint64 0))
  member __.IsEndOfFDE addr =
    fdeRanges |> List.ofSeq
              |> List.exists(fun (_, fdeEnd) -> addr = fdeEnd)

  member __.FDERanges with get(): SortedSet<Addr*Addr> = fdeRanges

/// External function is a function that is defined in another binary. Functions
/// in PLT is also considered as an external function, and we always link a PLT
/// entry with its corresponding GOT entry to consider such a pair as an
/// external function, where its entry is located at the GOT and its trampoline
/// is at the PLT.
type ExternalFunction private (ep, name, trampoline) =
  inherit Function (ep, name)

  /// Known list of no-return function names.
  static let knownNoReturnFuncs =
    [| "__assert_fail"
       "__stack_chk_fail"
       "abort"
       "_abort"
       "exit"
       "_exit"
       "__longjmp_chk"
       "__cxa_throw"
       "_Unwind_Resume"
       "_ZSt20__throw_length_errorPKc"
       "_gfortran_stop_numeric"
       "__libc_start_main"
       "longjmp" |]

  override __.FunctionKind with get() = FunctionKind.External

  /// If there is a trampoline (e.g., PLT) for the external function, this
  /// function returns the address of it.
  member __.TrampolineAddr ([<Out>] addr: byref<Addr>) =
    match trampoline with
    | 0UL -> false
    | _ -> addr <- trampoline; true

  /// Create a new ExternalFunction.
  static member Init ep name trampoline =
    let noretProp =
      if Array.contains name knownNoReturnFuncs then NoRet
      elif name = "error" || name = "error_at_line" then ConditionalNoRet 1
      else NotNoRet
    ExternalFunction (ep, name, trampoline, NoReturnProperty = noretProp)

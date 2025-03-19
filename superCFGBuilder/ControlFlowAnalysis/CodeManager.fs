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

open System
open System.Collections.Generic
open B2R2
open B2R2.BinIR
open B2R2.FrontEnd
open B2R2.FrontEnd.BinLifter
open B2R2.FrontEnd.BinLifter.Intel
open SuperCFG.ControlFlowGraph

type SiteInfo = {
  Addr: string
  Regs: string list
  OpType: string
}
type RefSiteInfo = {
  SiteInfo: SiteInfo
  IsDeterminate: bool
}
type BranchInfo = {
  JmpSite: SiteInfo //Addr * string
  AddSite: SiteInfo //Addr * string * string
  MemAccSite: SiteInfo //Addr * string
  TblRefSite: RefSiteInfo list//(Addr * string * bool) list
  TblAddr: Addr
}

type FunCodeManager (hdl, lu: LiftingUnit) =
  let insMap = Dictionary<Addr, InstructionInfo> ()
  let bblMap = Dictionary<Addr, BBLInfo> ()

  let tblCandidateDict = Dictionary<Addr, Addr> ()

  let codePtrCandidateDict = Dictionary<Addr, Addr> ()

  let falseBBLSet = SortedSet<Addr> ()

  let tblCandidates = SortedSet<Addr> ()

  let codePtrCandidates = SortedSet<Addr>()

  let localCodePtr = SortedSet<Addr>()

  let brInfoDict = Dictionary<Addr, BranchInfo list>()
  let newInstructionInfo (lu: LiftingUnit) (ins: Instruction) bblAddr =
    let stmts = lu.LiftInstruction ins
    { Instruction = ins
      Stmts = stmts
      BBLAddr = bblAddr }

  let rec postProcessInstrs hdl leaderAddr acc instrs =
    match instrs with
    | (ins: Instruction) :: tl ->
      let addr = ins.Address
      let info = newInstructionInfo hdl ins leaderAddr
      insMap[addr] <- info
      postProcessInstrs hdl leaderAddr (info :: acc) tl
    | [] -> acc

  let hasENDBR64 (hdl: BinHandle) (target: Addr) =
    if hdl.File.IsExecutableAddr target then
      let data = hdl.ReadUInt (target, 4)
      uint32 data = (uint32 0xFA1E0FF3)
    else false

  let isRodataAddr (hdl: BinHandle) (addr: Addr) =
    let rodata = hdl.File.GetSections ".rodata" |> Seq.head
    rodata.Address <= addr && addr < rodata.Address + uint64 rodata.Size

  let checkCandidate (hdl: BinHandle) (ins: Instruction) pc nextAddr =
    let intelIns = ins :?> IntelInstruction
    if (intelIns.Opcode = Opcode.LEA) then
      match intelIns.Operands with
      | TwoOperands (_, OprMem (Some Register.RIP, None, Some offset, 64<rt>))
        ->  let target = (uint64 nextAddr + uint64 offset)
            if (target % uint64 4) = (uint64 0) &&
               isRodataAddr hdl target then
                let addr = target + hdl.ReadUInt (target, 4)
                let ref = addr &&& 0xFFFFFFFFUL
                if hdl.File.IsExecutableAddr ref then
#if CFGDEBUG2
                  printfn "%x: %x" target ref
#endif
                  tblCandidates.Add target |> ignore
                  tblCandidateDict[pc] <- target
            if hasENDBR64 hdl target then
              codePtrCandidates.Add target |> ignore
              codePtrCandidateDict[pc] <- target

      | _ -> ()


  /// This function *NEVER* returns an empty list.
  let rec parseBBL hdl mode acc (pc: Addr) (codeMgr:FunCodeManager) =
    lu.Parser.OperationMode <- mode
    match lu.TryParseInstruction pc with
    | Ok ins ->
      let nextAddr = pc + uint64 ins.Length
      checkCandidate hdl ins pc nextAddr
      if ins.IsTerminator () || bblMap.ContainsKey nextAddr then
        Ok <| struct (ins :: acc, ins)
      else
        // If a pre-defined (overlapped) BBL contains nextAddr, do not make
        // duplicated disassembled code
        match codeMgr.TryGetBBL nextAddr with
        | Some _ -> Ok <| struct (ins :: acc, ins)
        | None -> parseBBL hdl mode (ins :: acc) nextAddr codeMgr
    | Error _ -> Error pc


  let rec parseOverlappedBBL hdl mode acc (pc: Addr) (codeMgr: FunCodeManager) =
    lu.Parser.OperationMode <- mode
    match lu.TryParseInstruction pc with
    | Ok ins ->
      let nextAddr = pc + uint64 ins.Length
      checkCandidate hdl ins pc nextAddr
      if ins.IsTerminator () || bblMap.ContainsKey nextAddr then
        Ok <| struct (ins :: acc, ins)
      else
        // If a pre-defined (overlapped) BBL contains nextAddr, do not make
        // duplicated disassembled code
        match codeMgr.TryGetBBL nextAddr with
        | Some _ -> Ok <| struct (ins :: acc, ins)
        | None -> parseOverlappedBBL hdl mode (ins :: acc) nextAddr codeMgr
    | Error _ -> Error pc


  /// Parse an instruction-level basic block starting from the given leader
  /// address. Return new CFG events to handle.
  member this.ParseBBL hdl isa fnMaintainer excTbl mode leaderAddr func evts =
    match parseBBL hdl mode [] leaderAddr this with
    | Ok (instrs, lastIns) ->
      try
        let ins = postProcessInstrs lu leaderAddr [] instrs
        let nextAddr = lastIns.Address + uint64 lastIns.Length
        let struct (bbl, evts) =
          BBLManager.parseBBLInfo hdl isa ins leaderAddr nextAddr func
                                  fnMaintainer excTbl evts
        bblMap[leaderAddr] <- bbl
        Ok evts
      with
      | :? InvalidOperationException  ->
        printfn "Lifting error (operation exception) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      | :? InvalidOperandException  | :? InvalidOperandSizeException ->
        printfn "Lifting error (operand exception) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      | :? TypeCheckException ->
        printfn "Lifting error (type inconsistency) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      (* XXX: These become an internal exception type.
      | :? InvalidRegAccessException ->
        printfn "Lifting error (Invalid Reg Access) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      | :? ArithTypeMismatchException ->
        printfn "Lifting error (Arithmetic Type Mismatch) detected at %x"
          leaderAddr
        Error ErrorCase.ParsingFailure
      *)
    | Error addr ->
      /// printfn "Parsing error detected at %x" addr
      Error ErrorCase.ParsingFailure


  member this.ParseOverlappedBBL
              hdl isa fnMaintainer excTbl mode leaderAddr func evts =
    match parseOverlappedBBL hdl mode [] leaderAddr this with
    | Ok (instrs, lastIns) ->
      try
        let ins = postProcessInstrs lu leaderAddr [] instrs
        let nextAddr = lastIns.Address + uint64 lastIns.Length
        let struct (bbl, evts) =
          BBLManager.parseBBLInfo hdl isa ins leaderAddr nextAddr func
                                  fnMaintainer excTbl evts
        bblMap[leaderAddr] <- bbl
        Ok evts
      with
      | :? InvalidOperationException  ->
        printfn "Lifting error (operation exception) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      | :? InvalidOperandException  | :? InvalidOperandSizeException ->
        printfn "Lifting error (operand exception) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      | :? TypeCheckException ->
        printfn "Lifting error (type inconsistency) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      (* XXX: These become an internal exception type.
      | :? InvalidRegAccessException ->
        printfn "Lifting error (Invalid Reg Access) detected at %x" leaderAddr
        Error ErrorCase.ParsingFailure
      | :? ArithTypeMismatchException ->
        printfn "Lifting error (Arithmetic Type Mismatch) detected at %x"
          leaderAddr
        Error ErrorCase.ParsingFailure
      *)
      | :? UnhandledRegExprException ->
        printfn "Lifting error (Unexpected Reg Expr) detected at %x"
          leaderAddr
        Error ErrorCase.ParsingFailure
    | Error addr ->
      /// printfn "Parsing error detected at %x" addr
      Error ErrorCase.ParsingFailure

  /// Get the current instruction count.
  member __.InstructionCount with get() = insMap.Count

  /// Check if the manager contains parsed InstructionInfo located at the given
  /// address.
  member __.HasInstruction addr = insMap.ContainsKey addr

  /// Access instruction at the given address.
  member __.GetInstruction (addr: Addr) = insMap[addr]

  /// Fold every instruction stored in the CodeManager.
  member __.FoldInstructions fn acc =
    insMap |> Seq.fold fn acc

  /// Get the current basic block count.
  member __.BBLCount with get() = bblMap.Count

  /// Check if the manager contains a basic block starting at the given address.
  member __.HasBBL addr = bblMap.ContainsKey addr

  /// Find the corresponding BBL address from the given instruction address.
  member __.GetBBL addr = bblMap[insMap[addr].BBLAddr]

  member __.GetBBLs = bblMap
  member __.GetInstructions = insMap

  member __.FalseBlocks with get() = falseBBLSet

  member __.UpdateBrInfo addr brInfoList =
    brInfoDict[addr] <- brInfoList

  member __.BrInfoDict with get() = brInfoDict

  member __.InsMap with get() = insMap

  member __.RegisterFalseBlock (leader:Addr) =
    falseBBLSet.Add leader

  /// Try to find the corresponding BBL address from the given instruction
  /// address.
  member __.TryGetBBL addr =
    match insMap.TryGetValue addr with
    | true, ins ->
      match bblMap.TryGetValue ins.BBLAddr with
      | true, bbl -> Some bbl
      | _ -> None
    | _ -> None

  /// Add the given bbl information; update the instruction-to-bbl mapping
  /// information.
  member __.AddBBL blkRange irLeaders funcEntry insAddrs =
    match insAddrs with
    | leaderAddr :: _ ->
      insAddrs
      |> List.iter (fun addr ->
        let ins = insMap[addr]
        insMap[addr] <- { ins with BBLAddr = leaderAddr })
      bblMap[leaderAddr] <-
        BBLManager.initBBLInfo blkRange insAddrs irLeaders funcEntry
    | [] -> ()

  /// Remove the given BBLInfo.
  member __.RemoveBBL (bbl) =
    bblMap.Remove bbl.BlkRange.Min |> ignore

  /// Remove the given BBL located at the bblAddr.
  member __.RemoveBBL (bblAddr) =
    if bblMap.ContainsKey bblAddr then __.RemoveBBL bblMap[bblAddr]
    else ()

  /// Fold every instruction stored in the CodeManager.
  member __.FoldBBLs fn acc =
    bblMap |> Seq.fold fn acc

  member private __.SplitBBLInfo (bbl: BBLInfo) splitAddr splitPp =
    __.RemoveBBL (bbl)
    let fstAddrs, sndAddrs =
      Set.partition (fun insAddr -> insAddr < splitAddr) bbl.InstrAddrs
    let fstAddrs = Set.toList fstAddrs
    let sndAddrs = Set.toList sndAddrs
    let fstLeaders, sndLeaders =
      Set.add splitPp bbl.IRLeaders
      |> Set.partition (fun pp -> pp < splitPp)
    let oldRange = bbl.BlkRange
    let fstRange = AddrRange (oldRange.Min, splitAddr - 1UL)
    let sndRange = AddrRange (splitAddr, oldRange.Max)
    let entry = bbl.FunctionEntry
    __.AddBBL fstRange fstLeaders entry fstAddrs
    __.AddBBL sndRange sndLeaders entry sndAddrs

  /// This is when a contiguous bbl (it is even contiguous at the IR-level) is
  /// divided into two at the splitPoint.
  member private __.SplitCFG fn prevBBL splitPoint evts =
    let bblPoint = (* The program point of the dividing block. *)
      prevBBL.IRLeaders
      |> Set.partition (fun pp -> pp < splitPoint)
      |> fst |> Set.maxElement
    (fn: RegularFunction).SplitBBL (bblPoint, splitPoint) |> ignore
    Some bblPoint, CFGEvents.updateEvtsAfterBBLSplit fn bblPoint splitPoint evts

  /// Split the given basic block into two at the given address (splitAddr), and
  /// returns a pair of (the address of the front bbl after the cut-out, and new
  /// events). The front bbl may not exist if the split point is at the address
  /// of an existing bbl leader.
  member __.SplitBlock (func: RegularFunction) bbl splitAddr evts =
    let splitPp = ProgramPoint (splitAddr, 0)
#if CFGDEBUG
    dbglog (nameof FunCodeManager) "Split BBL @ %x%s"
      splitAddr (if Set.contains splitPp bbl.IRLeaders then " (& CFG)" else "")
#endif
    //let func = fnMaintainer.FindRegular bbl.FunctionEntry
    __.SplitBBLInfo bbl splitAddr splitPp
    let lastInst = List.last (bbl.InstrAddrs |> Set.toList |> List.sortBy id )
    match func.IndJmpBBLs.TryGetValue lastInst with
      | true, _ -> func.UpdateIndJmpBBLeader lastInst splitPp
      | false, _ -> ()
    if Set.contains splitPp bbl.IRLeaders then None, evts
    else __.SplitCFG func bbl splitPp evts

  member private __.MergeBBLInfoAndReplaceInlinedAssembly addrs fstBBL sndBBL =
    let restAddrs = List.tail addrs
    __.RemoveBBL (bbl=fstBBL)
    __.RemoveBBL (bbl=sndBBL)
    let blkRange = AddrRange (fstBBL.BlkRange.Min, sndBBL.BlkRange.Max)
    let leaders =
      Set.union fstBBL.IRLeaders sndBBL.IRLeaders
      |> Set.filter (fun leader ->
        not <| List.contains leader.Address restAddrs)
    let addrs =
      Set.union fstBBL.InstrAddrs sndBBL.InstrAddrs
      |> Set.filter (fun addr -> not <| List.contains addr restAddrs)
      |> Set.toList
    let entry = fstBBL.FunctionEntry
    __.AddBBL blkRange leaders entry addrs

  member __.ReplaceInlinedAssemblyChunk
          (fn: RegularFunction) insAddrs (chunk: Instruction) evts =
    let fstBBL = __.GetBBL chunk.Address
    let sndBBL = __.GetBBL (fstBBL.BlkRange.Max + 1UL)
    __.MergeBBLInfoAndReplaceInlinedAssembly insAddrs fstBBL sndBBL
    //let fn = fnMaintainer.FindRegular fstBBL.FunctionEntry
    let srcPoint = fstBBL.IRLeaders.MaximumElement
    let dstPoint = sndBBL.IRLeaders.MinimumElement
    let dstLeaders = sndBBL.IRLeaders
    fn.MergeVerticesWithInlinedAsmChunk (insAddrs, srcPoint, dstLeaders, chunk)
    CFGEvents.updateEvtsAfterBBLMerge fn srcPoint dstPoint evts

  /// Update function entry information for the basic block located at the given
  /// address.
  member __.UpdateFunctionEntry bblAddr funcEntry =
    match bblMap.TryGetValue bblAddr with
    | true, bbl ->
      let bbl = { bbl with FunctionEntry = funcEntry }
      bblMap[bbl.BlkRange.Min] <- bbl
    | _ -> ()

  member __.GetTblCandidates = tblCandidates

  member __.GetTblCandidateDict = tblCandidateDict

  member __.GetCodePtrCandidateDict = codePtrCandidateDict

  member __.CodePtrCandidates with get() = codePtrCandidates

  member __.UnregisterCodePtrCandidateDict addr =
    codePtrCandidateDict.Remove addr

  member __.RegisterLocalCodePtr addr =
    localCodePtr.Add addr |> ignore

  member __.GetLocalCodePtr = localCodePtr

/// CodeManager manages all the processed information about the binary code
/// including *parsed* instructions, their basic blocks, functions, as well as
/// exception handling routines.
type CodeManager (hdl, isa, lu) =
  let excTbl = ExceptionTable (hdl, lu)

  let history = HistoryManager ()

  let fnMaintainer = FunctionMaintainer.Init hdl isa history

  let funCodeDict = Dictionary<Addr, FunCodeManager> ()

  let insMap = Dictionary<Addr, InstructionInfo> ()
  let bblMap = Dictionary<Addr, BBLInfo> ()

  //Record false functions
  let falseFunSet = SortedSet<Addr> ()

  let suspiciousFunSet = SortedSet<Addr> ()

  let initialEntries = List<Addr> ()

  member __.RegisterInitEntries addr =
    initialEntries.Add addr

  member __.GetNextInitEntry addr =
    let entries = initialEntries |> Seq.filter(fun entry -> addr < entry)
    if entries |> Seq.isEmpty then None
    else entries |> Seq.min |> Some

  member __.GetPrevInitEntry addr =
    let entries = initialEntries |> Seq.filter(fun entry -> addr > entry)
    if entries |> Seq.isEmpty then None
    else entries |> Seq.max |> Some

  /// Return the function maintainer.
  member __.FunctionMaintainer with get() = fnMaintainer

  /// Return the history manager.
  member __.HistoryManager with get() = history

  member __.FunCodeDict with get() = funCodeDict

  member __.FalseFunSet with get() = falseFunSet

  member __.SuspiciousFunSet with get() = suspiciousFunSet

  member __.GetOrAddFunCodeMgr entry =
    match funCodeDict.TryGetValue entry with
      | true, funCodeMgr -> funCodeMgr
      | _, _ ->
        let funCodeMgr = FunCodeManager(hdl, lu)
        funCodeDict[entry] <- funCodeMgr
        funCodeMgr

  member __.GetFunCodeMgr (entry: Addr) =
    funCodeDict[entry]

  member __.HasFunCodeMgr (entry: Addr) =
    funCodeDict.ContainsKey entry

  member __.RemoveFunCodeMgr (entry:Addr) =
    funCodeDict.Remove entry

  member __.RegisterFalseFunc (entry:Addr) =
    falseFunSet.Add entry

  member __.IsFalseFunc (entry:Addr) =
    falseFunSet.Contains entry

  member __.RegisterSuspiciousFunc (entry:Addr) =
    suspiciousFunSet.Add entry

  member __.ExceptionTable with get() = excTbl

  member private __.RemoveFunction fnAddr =
    match fnMaintainer.TryFindRegular fnAddr with
    | Some fn ->
      let funCodeMgr = __.GetFunCodeMgr fnAddr
      fn.IterRegularVertexPps (fun pp -> funCodeMgr.RemoveBBL pp.Address)
      fnMaintainer.RemoveFunction fnAddr
    | None -> () (* Already removed. *)


  member private __.RollBackFact evts fact =
#if CFGDEBUG
    dbglog (nameof FunCodeManager) "Rollback %s" (HistoricalFact.toString fact)
#endif
    match fact with
    | CreatedFunction (fnAddr) ->
      __.RemoveFunction fnAddr
      CFGEvents.addFuncEvt fnAddr ArchOperationMode.NoMode evts (* XXX *)

  member __.RollBack (evts, fnAddrs: Addr list) =
    /// We do not need to remove function since we rebuild superset CFG
    (*
    fnAddrs
    |> List.fold (fun evts fnAddr ->
      history.PeekFunctionHistory fnAddr
      |> Array.fold __.RollBackFact evts
    ) evts
    *)
    evts

  member __.ConstructMap =
    funCodeDict |> Seq.sortBy (fun (KeyValue(k,v)) -> k)
                |> Seq.iter(fun (KeyValue(_,mgr)) ->
                  mgr.GetBBLs |>
                    Seq.iter(fun (KeyValue(addr, bbl)) ->
                              __.AddBBL addr bbl)
                  mgr.GetInstructions |>
                    Seq.iter(fun (KeyValue(addr, ins)) ->
                              __.AddInstruction addr ins)
                    )
    ()


  member __.GetInstruction (addr: Addr) = insMap[addr]
  member private __.AddBBL (addr: Addr) bbl =
    bblMap[addr] <- bbl

  member private __.AddInstruction (addr: Addr) ins =
    insMap[addr] <- ins

  member __.FoldBBLs fn acc =
    __.ConstructMap
    bblMap |> Seq.fold fn acc

  member __.FoldInstructions fn acc =
    __.ConstructMap
    insMap |> Seq.fold fn acc


  member __.GetValidNextBoundary addr =
    let nextEntry = __.GetNextInitEntry addr
    let nextFDE = __.ExceptionTable.GetNextFDEEntry addr
    match nextEntry, nextFDE with
    | Some tmpEnd1, Some tmpEnd2 ->
      if tmpEnd1 < tmpEnd2  then  Some tmpEnd1
      else Some tmpEnd2
    | Some tmpEnd, None
    | None, Some tmpEnd -> Some tmpEnd
    | _, _ -> None

  member __.GetValidPrevBoundary addr =
    let nextEntry = __.GetPrevInitEntry addr
    let nextFDE = __.ExceptionTable.GetPrevFDEEntry addr
    match nextEntry, nextFDE with
    | Some tmpEnd1, Some tmpEnd2 ->
      if tmpEnd1 > tmpEnd2  then  Some tmpEnd1
      else Some tmpEnd2
    | Some tmpEnd, None
    | None, Some tmpEnd -> Some tmpEnd
    | _, _ -> None

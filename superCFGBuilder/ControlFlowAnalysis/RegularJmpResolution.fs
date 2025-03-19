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
open B2R2
open B2R2.BinIR
open B2R2.FrontEnd
open B2R2.FrontEnd.BinFile
open SuperCFG.SSA
open B2R2.FrontEnd.BinLifter
open SuperCFG.ControlFlowGraph
open SuperCFG.ControlFlowAnalysis.IRHelper
open SuperCFG.DataFlow

[<AutoOpen>]
module private RegularJmpResolution =

  let rec isJmpTblAddr cpState depth = function
    | Var v  when depth > 0 ->
      match Map.tryFind v cpState.SSAEdges.Defs with
      | Some (Def (_, e)) -> isJmpTblAddr cpState (depth-1) e
      | Some (Phi (_, ids)) ->
        let bvs = ids |> Array.toList
                  |> List.map (fun id -> {v with Identifier = id})
                  |> List.filter (fun item -> item <> v)
                  |> List.distinct |> List.ofSeq
        if bvs |> List.isEmpty then
          false
        else
          bvs |> List.exists(fun v -> isJmpTblAddr cpState (depth-1) (Var v))
      | _ -> false
    | BinOp (BinOpType.MUL, _, _, Num _)
    | BinOp (BinOpType.MUL, _, Num _, _)
    | BinOp (BinOpType.SHL, _, _, Num _) -> true
    | BinOp (_, _, e1, e2) when depth > 0 ->
      isJmpTblAddr cpState (depth-1) e1 || isJmpTblAddr cpState (depth-1) e2
    | _ -> false

  let rec extractTableExpr = function
    | BinOp (BinOpType.ADD, _, BinOp (BinOpType.MUL, _, _, Num _), e)
    | BinOp (BinOpType.ADD, _, BinOp (BinOpType.MUL, _, Num _, _), e)
    | BinOp (BinOpType.ADD, _, BinOp (BinOpType.SHL, _, _, Num _), e)
    | BinOp (BinOpType.ADD, _, e, BinOp (BinOpType.MUL, _, _, Num _))
    | BinOp (BinOpType.ADD, _, e, BinOp (BinOpType.MUL, _, Num _, _))
    | BinOp (BinOpType.ADD, _, e, BinOp (BinOpType.SHL, _, _, Num _)) -> e
    | BinOp (op, rt, e1, e2) ->
      BinOp (op, rt, extractTableExpr e1, extractTableExpr e2)
    | UnOp (op, rt, e) -> UnOp (op, rt, extractTableExpr e)
    | Cast (op, rt, e) -> Cast (op, rt, extractTableExpr e)
    | Extract (e, rt, pos) -> Extract (extractTableExpr e, rt, pos)
    | e -> e

  let computeMask size =
    let rt = RegType.fromByteWidth size
    (* It is reasonable enough to assume that jump target addresses will never
       overflow when rt is greater than 64<rt>. *)
    if rt > 64<rt> then 0xFFFFFFFFFFFFFFFFUL
    else BitVector.UnsignedMax rt |> BitVector.ToUInt64

  /// Read a table entry and compute jump target
  let readTable (hdl: BinHandle) bAddr (entryAddr: Addr) size =
    let addr = bAddr + hdl.ReadUInt (entryAddr, size)
    addr &&& computeMask size

  let recoverIndirectEdge bld fn src dst =
    let evts =
      CFGEvents.empty
      //|> CFGEvents.addPerFuncAnalysisEvt (fn: RegularFunction).EntryPoint
      |> CFGEvents.addEdgeEvt fn src dst IndirectJmpEdge
    (bld: ICFGBuildable).Update evts

  let isPromisingEntry (hdl: BinHandle) (fn: RegularFunction) target =
    let isLocatedBeforeEntry =
      match hdl.File.EntryPoint with
      | Some entryPoint when entryPoint > target
                              && entryPoint < fn.EntryPoint -> true
      | _ -> false

    let hasENDBR64 (hdl: BinHandle) (target: Addr) =
      if hdl.File.IsExecutableAddr target then
        let data = hdl.ReadUInt (target, 4)
        uint32 data = (uint32 0xFA1E0FF3)
      else false
    // if target has no ENDBR and is located before entry point
    // we add it unsolved edge list
    isLocatedBeforeEntry && not (hasENDBR64 hdl target)


  let recoverOneEntry bld hdl codeMgr (dataMgr: DataManager) fn jt entryAddr =
    let dst = readTable hdl jt.BranchBaseAddr entryAddr jt.JTEntrySize
    let brAddr = jt.InstructionAddr
    let _, src = (fn: RegularFunction).IndJmpBBLs.TryGetValue brAddr

#if CFGDEBUG
    dbglog "IndJmpRecovery" "@%x Recovering %x -> %x (%x)"
      (fn: RegularFunction).EntryPoint src.Address dst entryAddr
#endif
    let funDataMgr = dataMgr.GetFunDataMgr fn.EntryPoint
    recoverIndirectEdge bld fn src dst
    |> Result.bind (fun _ ->
      (* This is really an exceptional case where we found a nested switch
         table, whose location is overlapping with our current entryAddr.
         Thus, the potential end-point address has been updated during the
         Update process, and we found out late that our attempt with entryAddr
         was wrong. *)
      let ep = funDataMgr.JumpTables.FindPotentialEndPoint
                 (jt.JTStartAddr, brAddr)
      let last = funDataMgr.JumpTables.FindConfirmedEndPoint
                   (jt.JTStartAddr, brAddr)
      if entryAddr >= ep then Error ErrorLateDetection
      elif entryAddr < last then Error ErrorVisitedSwitchEntry
      else Ok dst)
    |> function
      | Ok recoveredAddr ->
        let ep = entryAddr + uint64 jt.JTEntrySize
        let tblSize = (uint64 (ep - jt.JTStartAddr)/uint64 jt.JTEntrySize)
#if CFGDEBUG
        dbglog "IndJmpRecovery"
          "Successfully recovered %x -> %x from %x (tbl %x:%x)"
          jt.InstructionAddr recoveredAddr entryAddr jt.JTStartAddr tblSize
#endif
        fn.UpdateJTableSize jt.JTStartAddr tblSize
        let funDataMgr = dataMgr.GetFunDataMgr fn.EntryPoint
        funDataMgr.JumpTables.UpdateConfirmedEndPoint
          (jt.JTStartAddr, brAddr) ep |> Ok
      | Error e -> Error e

  (*
  /// Analyze less explored jump tables first.
  let sortJumpTablesByProgress (funDataMgr: FunDataManager) jmpTbls =
    jmpTbls
    |> List.sortBy (fun addr ->
      (funDataMgr.JumpTables.FindConfirmedEndPoint addr) - addr)
  *)
  (*
  /// We first recover the very first entry, since we are 100% sure about it.
  let rec getInitialRecoveryTarget (funDataMgr: FunDataManager) = function
    | tAddr :: tl ->
      let endPoint = funDataMgr.JumpTables.FindConfirmedEndPoint tAddr
      if funDataMgr.IsVisitedTbl tAddr then
        getInitialRecoveryTarget funDataMgr tl
      elif tAddr = endPoint then (* First entry *)
        Some (funDataMgr.JumpTables[tAddr], tAddr)
      else getInitialRecoveryTarget funDataMgr tl
    | [] -> None
  *)
  let isSemanticallyNop (lu: LiftingUnit) (ins: Instruction) =
    if ins.IsNop () then true
    else
      try
        match lu.LiftInstruction ins with
        | [| { LowUIR.S = LowUIR.ISMark (_) }
             { LowUIR.S = LowUIR.IEMark (_) } |] -> true
        | _ -> false
      with
        | :? InvalidOperationException  ->
          printfn "Lifting error (operation exception) detected at %x"
            ins.Address
          false
        | :? InvalidOperandException  | :? InvalidOperandSizeException ->
          printfn "Lifting error (operand exception) detected at %x"
            ins.Address
          false
        | :? TypeCheckException ->
          printfn "Lifting error (type inconsistency) detected at %x"
            ins.Address
          false

  /// Increment the current entry address of a jump table only if it can point
  /// to a valid entry.
  let incEntryAddr (hdl: BinHandle) (fn: RegularFunction) codeMgr jt entryAddr =
    let addr = readTable hdl jt.BranchBaseAddr entryAddr jt.JTEntrySize
#if CFGDEBUG
    dbglog "IndJmpRecovery" "Read %x from %x" addr entryAddr
#endif
    if hdl.File.IsExecutableAddr addr then
      if fn.IsInFDERange addr then
        Some entryAddr, None
      elif fn.IsEndOfFDE addr then
#if CFGDEBUG
        dbglog "IndJmpRecovery" "%x points to the end of FDE (func: %x)"
          addr fn.EntryPoint
#endif
        Some entryAddr, Some addr
      else
        let entries =
          (codeMgr: CodeManager).ExceptionTable.GetFunctionEntryPoints()
        //if switch entry point to other entry point, it may a cold function
        //We register FDE information
        if Set.contains addr entries then
#if CFGDEBUG
          dbglog "IndJmpRecovery" "%x points to the other FDE (func: %x)"
            addr fn.EntryPoint
#endif
          Some entryAddr, Some addr
        else
          match hdl.File.EntryPoint with
          | Some entryPoint when entryPoint > addr ->
#if CFGDEBUG
              dbglog "IndJmpRecovery" "%x may point to cold function (func: %x)"
                addr fn.EntryPoint
#endif
              Some entryAddr, Some addr
          | _ ->
#if CFGDEBUG
              dbglog "IndJmpRecovery" "%x points to outside of FDE (func: %x)"
                addr fn.EntryPoint
#endif
              None, None
    else None, None

  /// This is a less safer path than the gap-oriented search. We compute the
  /// next recovery end-point address by simply pointing to the next entry.
  let rec getNextRecoveryTargetFromTable
                    hdl codeMgr dataMgr fn unsolvedTargets = function
    | tAddr :: tl ->
      let funDataMgr =
        (dataMgr: DataManager).GetFunDataMgr (fn: RegularFunction).EntryPoint
      let jt = funDataMgr.JumpTables[tAddr]
      let deadEnd = funDataMgr.JumpTables.FindPotentialEndPoint tAddr
      let entryAddr = funDataMgr.JumpTables.FindConfirmedEndPoint tAddr
      let tblAddr, insAddr = tAddr
#if CFGDEBUG
      dbglog "IndJmpRecovery" "Last resort (tbl %x) %x < %x"
        tblAddr entryAddr deadEnd
#endif
      if entryAddr < deadEnd then
        match incEntryAddr hdl fn codeMgr jt entryAddr with
        | Some entry, None ->
#if CFGDEBUG
          dbglog "IndJmpRecovery" "Found entry %x from table (%x)"
            entry jt.JTStartAddr
#endif
          Some (jt, entry), unsolvedTargets
        | Some entry, Some target ->
#if CFGDEBUG
          dbglog "IndJmpRecovery" "Found entry %x from table (%x) %s "
            entry jt.JTStartAddr "which points to end of FDE or cold function"
#endif
          /// If jump table entry points to end of FDE, we just expand jump
          /// table size without adding edge
          funDataMgr.JumpTables.UpdateConfirmedEndPoint
            (jt.JTStartAddr, insAddr) (entryAddr + uint64 jt.JTEntrySize)

          let ep = entryAddr + uint64 jt.JTEntrySize
          let tblSize = (uint64 (ep - jt.JTStartAddr)/uint64 jt.JTEntrySize)
          fn.UpdateJTableSize jt.JTStartAddr tblSize

          if fn.IsEndOfFDE target then
            getNextRecoveryTargetFromTable hdl codeMgr dataMgr fn
              unsolvedTargets (tAddr::tl)
          else
            //Add unsolved target list if it refers to a promising cold block
            if isPromisingEntry hdl fn target then
              getNextRecoveryTargetFromTable hdl codeMgr dataMgr fn
                (target::unsolvedTargets) (tAddr::tl)
            else None, unsolvedTargets
        | None, _ ->
          fn.MarkRecoveryDone jt.JTStartAddr
          getNextRecoveryTargetFromTable
            hdl codeMgr dataMgr fn unsolvedTargets tl
      else
        fn.MarkRecoveryDone jt.JTStartAddr
        getNextRecoveryTargetFromTable hdl codeMgr dataMgr fn unsolvedTargets tl
    | [] -> None, unsolvedTargets

  /// Get the next analysis target information, such as end-point addresses
  /// where we should stop our recovery process, for recovering jump tables.
  (*
  let getNextAnalysisTarget hdl codeMgr (dataMgr: DataManager) func =
    let funDataMgr = dataMgr.GetFunDataMgr (func:RegularFunction).EntryPoint
    let jmpTbls = func.GetUnmarkedJumpTables
                  |> sortJumpTablesByProgress funDataMgr
#if CFGDEBUG
    dbglog "IndJmpRecovery" "%d table(s) at hand" (List.length jmpTbls)
#endif
    let funDataMgr = dataMgr.GetFunDataMgr func.EntryPoint
    match getInitialRecoveryTarget funDataMgr jmpTbls with
    | Some (jt, _) as target ->
#if CFGDEBUG
      dbglog "IndJmpRecovery" "Found the first entry from table (%x)"
        jt.JTStartAddr
#endif
      funDataMgr.MarkVisitedTbl jt.JTStartAddr
      target
    | None ->
      match getNextRecoveryTargetFromTable hdl codeMgr dataMgr func
              List.Empty jmpTbls with
      | Some (jt, entry), _ -> Some (jt, entry)
      | _ -> None
  *)
  let rec rollback
    (codeMgr: CodeManager) (dataMgr: DataManager) fn evts jt entryAddr e =
    let fnAddr = (fn: RegularFunction).EntryPoint
    let brAddr = jt.InstructionAddr
#if CFGDEBUG
    dbglog "IndJmpRecovery" "@%x Failed to recover %x (tbl %x), so rollback %s"
      fnAddr entryAddr jt.JTStartAddr (CFGError.toString e)
#endif
    let funDataMgr = dataMgr.GetFunDataMgr fn.EntryPoint
    funDataMgr.JumpTables.UpdateConfirmedEndPoint
      (jt.JTStartAddr, brAddr) jt.JTStartAddr
    match e with
    | ErrorBranchRecovery (errFnAddr, errBrAddr, rollbackFuncs) ->
      let rollbackFuncs = Set.add fnAddr rollbackFuncs
      if codeMgr.HistoryManager.HasFunctionLater fnAddr then
        Error <| ErrorBranchRecovery (errFnAddr, errBrAddr, rollbackFuncs)
      else codeMgr.RollBack (evts, Set.toList rollbackFuncs) |> Ok
    | ErrorLateDetection ->
      funDataMgr.JumpTables.UpdatePotentialEndPoint
        (jt.JTStartAddr, brAddr) entryAddr
      finishIfEmpty codeMgr fnAddr brAddr evts
    | ErrorConnectingEdge | ErrorParsing ->
      funDataMgr.JumpTables.UpdatePotentialEndPoint
        (jt.JTStartAddr, brAddr) entryAddr
      finishIfEmpty codeMgr fnAddr brAddr evts
    | _ -> Utils.impossible ()


  and finishIfEmpty codeMgr fnAddr brAddr evts =
    if codeMgr.HistoryManager.HasFunctionLater fnAddr then
      Error (ErrorBranchRecovery (fnAddr, brAddr, Set.singleton fnAddr))
    else Ok <| (codeMgr: CodeManager).RollBack (evts, [ fnAddr ])

  let getRelocatedAddr (file: IBinFile) relocationTarget defaultAddr =
    match file.GetRelocatedAddr relocationTarget with
    | Ok addr -> addr
    | Error _ -> defaultAddr

  let classifyPCRelative (hdl: BinHandle) isa cpState pcVar offset =
    match CPState.findReg cpState pcVar with
    | Const bv ->
      let ptr = BitVector.ToUInt64 bv + BitVector.ToUInt64 offset
      let size = isa.WordSize |> WordSize.toByteWidth
      let file = hdl.File
      match hdl.TryReadUInt (ptr, size) with
      | Ok target when target <> 0UL && file.IsExecutableAddr target ->
        ConstJmpPattern <| getRelocatedAddr file ptr target
      | _ -> UnknownPattern
    | _ -> UnknownPattern

  let classifyJumpTableExpr cpState baseExpr tblExpr rt =
    let baseExpr = foldWithConstant cpState baseExpr |> simplify
    let tblExpr = baseExpr
    (*
    let tblExpr =
      symbolicExpand cpState tblExpr
      |> extractTableExpr
      |> foldWithConstant cpState
    *)
#if CFGDEBUG
    dbglog "IndJmpRecovery" "base(%s); table(%s)"
      (Pp.expToString baseExpr) (Pp.expToString tblExpr)
#endif
    match baseExpr, tblExpr with
    | Num b, Num t
    | Num b, BinOp (BinOpType.ADD, _, Num t, _)
    | Num b, BinOp (BinOpType.ADD, _, _, Num t) ->
      let baseAddr = BitVector.ToUInt64 b
      let tblAddr = BitVector.ToUInt64 t
      JmpTablePattern (baseAddr, tblAddr, rt)
    | _ -> UnknownPattern

  let ClassifyJmpExpr hdl isa cpState = function
    | BinOp (BinOpType.ADD, _, Num b, Load (_, t, memExpr))
    | BinOp (BinOpType.ADD, _, Load (_, t, memExpr), Num b)
    | BinOp (BinOpType.ADD, _, Num b, Cast (_, _, Load (_, t, memExpr)))
    | BinOp (BinOpType.ADD, _, Cast (_, _, Load (_, t, memExpr)), Num b) ->
      if isJmpTblAddr cpState 3 memExpr then
        classifyJumpTableExpr cpState (Num b) memExpr t
      else UnknownPattern
    (* Symbolic patterns should be resolved with our constant analysis. *)
    | BinOp (BinOpType.ADD, _, (Load (_, _, e1) as l1),
                               (Load (_, t, e2) as l2)) ->
      if isJmpTblAddr cpState 3 e1 then classifyJumpTableExpr cpState l2 e1 t
      elif isJmpTblAddr cpState 3 e2 then classifyJumpTableExpr cpState l1 e2 t
      else UnknownPattern
    | BinOp (BinOpType.ADD, _, baseExpr, Load (_, t, tblExpr))
    | BinOp (BinOpType.ADD, _, Load (_, t, tblExpr), baseExpr) ->
      if isJmpTblAddr cpState 3 tblExpr then
        classifyJumpTableExpr cpState baseExpr tblExpr t
      else UnknownPattern
    (* This pattern is jump to an address stored at [PC + offset] *)
    | Load (_, _, BinOp (BinOpType.ADD, _,
                         Var ({ Kind = PCVar _} as pcVar), Num offset)) ->
      classifyPCRelative hdl isa cpState pcVar offset
    (* Patterns from non-pie executables. *)
    | Load (_, t, memExpr)
    | Cast (_, _, Load (_, t, memExpr)) ->
      if isJmpTblAddr cpState 3 memExpr then
        classifyJumpTableExpr cpState (Num <| BitVector.Zero t) memExpr t
      else UnknownPattern
    | _ -> UnknownPattern

/// RegularJmpResolution recovers indirect tail calls and jump targets of
/// indirect jumps by inferring their jump tables. It first identifies
/// jump table bases with constant propagation and recovers the entire
/// table ranges by leveraging the structural properties of the binary.
type RegularJmpResolution (bld) =
  inherit IndirectJumpResolution ()

  override __.Name = "RegularJmpResolution"



  override __.Classify2 hdl isa _srcV cpState jmpType =
    match jmpType with
    | InterJmp jmpExpr ->
      let candidates = GetSimpleUDChain cpState Set.empty 14 jmpExpr
                        |> Seq.filter(hdl.File.IsValidAddr)
      let result = candidates
                   |> Seq.toList |> List.map(fun addr ->
                      resolveExprWithTarget cpState false addr jmpExpr
                      |> List.map(fun symExp -> symExp, addr) )
      let result = List.concat result |> Seq.distinct |> List.ofSeq

      if result.Length = 0 then
        [(UnknownPattern, [], [])]
      else
        let patterns = result
                       |> List.map(fun (symbExpr, expectedAddr) ->
#if CFGDEBUG
          dbglog "IndJmpRecovery" "Pattern indjmp: %s" (Pp.expToString symbExpr)
#endif
          let pattern = ClassifyJmpExpr hdl isa cpState symbExpr
          match pattern with
          | JmpTablePattern (baseAddr, _, _ ) when baseAddr = expectedAddr ->
            let ess, _ = jmpExpr |> stage1 cpState baseAddr Set.empty 10
            let defChain = ess |> Set.toList
                           |> List.fold(fun acc var ->
                              cpState.SSAEdges.Var2PPoint[var].Address::acc) []
                           |> Set.ofList |> Set.toList
            let def = ess
                      |> Set.filter (fun v ->
                        match v.Kind with
                        | RegVar _ -> true
                        | _ -> false)
                      |> Set.filter(fun v ->
                        match CPState.findReg cpState v with
                          | Const bv -> BitVector.ToUInt64 bv = baseAddr
                          | _ -> false )
                      |> Set.toList
            (pattern, def, defChain)
          | _ -> (pattern, [], [])
        )
        patterns
    | _ -> Utils.impossible ()

  override __.Classify hdl isa _srcV cpState jmpType =
    match jmpType with
    | InterJmp jmpExpr ->
      let candidates = GetSimpleUDChain cpState Set.empty 10 jmpExpr
      let symbExprs = candidates |> Set.toList |> List.map(fun addr ->
        resolveExprWithTarget cpState false addr jmpExpr)
      let symbExprs = List.concat symbExprs
      if symbExprs.Length = 0 then
        UnknownPattern
      else
        let patterns = symbExprs |> List.map(fun symbExpr ->
#if CFGDEBUG
          dbglog "IndJmpRecovery" "Pattern indjmp: %s" (Pp.expToString symbExpr)
#endif
          let pattern = ClassifyJmpExpr hdl isa cpState symbExpr
          match pattern with
          | JmpTablePattern (baseAddr, tblAddr, rt) ->
            let ess, bFound = jmpExpr |> stage1 cpState baseAddr Set.empty 10
            pattern
          | _ -> pattern
        )
        patterns[0]
    | _ -> Utils.impossible ()

  override __.MarkIndJmpAsTarget codeMgr dataMgr fn insAddr _ evts pattern =
    match pattern with
    | JmpTablePattern (bAddr, tAddr, rt) ->
      let funCodeMgr = codeMgr.GetFunCodeMgr fn.EntryPoint
      if not (funCodeMgr.GetTblCandidates.Contains bAddr) then
       Ok (false, evts)
      else
#if CFGDEBUG
        dbglog "IndJmpRecovery" "Found known pattern %x, %x" bAddr tAddr
#endif
        if fn.JmpTblDict.ContainsKey tAddr then
          fn.MarkIndJumpAsJumpTbl insAddr tAddr
          Ok (true, evts)
        else
          let funDataMgr = dataMgr.GetFunDataMgr fn.EntryPoint
          let tbls = funDataMgr.JumpTables
          match tbls.Register fn.EntryPoint insAddr bAddr tAddr rt with
          | Ok () ->
            fn.MarkIndJumpAsJumpTbl insAddr tAddr
            Ok (true, evts)
          | Error jt -> Error (jt, tAddr) (* Overlapping jump table. *)
    | ConstJmpPattern (target) ->
#if CFGDEBUG
      dbglog "IndJmpRecovery" "Found ConstJmpPattern %x" target
#endif
      fn.RemoveIndJump insAddr
      let evts =
        if codeMgr.FunctionMaintainer.Contains (addr=target) then
          let callee = IndirectCallees <| Set.singleton target
          CFGEvents.addPerFuncAnalysisEvt (fn: RegularFunction).EntryPoint evts
          |> CFGEvents.addIndTailCallEvt fn insAddr callee
        else
          fn.MarkIndJumpAsKnownJumpTargets insAddr (Set.singleton target)
          let funCodeMgr = (codeMgr: CodeManager).GetFunCodeMgr fn.EntryPoint
          let bblInfo = funCodeMgr.GetBBL insAddr
          let src = bblInfo.IRLeaders |> Set.maxElement
          CFGEvents.addPerFuncAnalysisEvt (fn: RegularFunction).EntryPoint evts
          |> CFGEvents.addEdgeEvt fn src target IndirectJmpEdge
      Ok (false, evts)
    | _ ->
      fn.MarkIndJumpAsUnknown insAddr
      Ok (false, evts)

  override __.RecoverTable hdl codeMgr dataMgr fn jmpAddr tblAddr evts =
    let rec recoverTblEntry bld hdl codeMgr (dataMgr: DataManager) fn
          (jt: JumpTable) entryAddr unsolvedTargetList =

      let dst = readTable hdl jt.BranchBaseAddr entryAddr jt.JTEntrySize
      let res =
        if (fn: RegularFunction).IsInFDERange dst then
          match recoverOneEntry bld hdl codeMgr dataMgr fn jt entryAddr with
          | Ok () -> true, unsolvedTargetList
          | Error e -> false, unsolvedTargetList
        else
          if isPromisingEntry hdl fn dst then
            true, dst::unsolvedTargetList
          else false, unsolvedTargetList
      match res with
      | true, unsolvedTargetList ->
        match getNextRecoveryTargetFromTable hdl codeMgr dataMgr fn List.Empty
                [(jt.JTStartAddr, jmpAddr)] with
        | Some (jt, entryAddr), newUnsolvedTargetList ->
          let coldFunList = newUnsolvedTargetList@unsolvedTargetList
          recoverTblEntry bld hdl codeMgr dataMgr fn jt entryAddr coldFunList
        | None, newUnsolvedTargetList ->
          newUnsolvedTargetList@unsolvedTargetList
      | false, unsolvedTargetList -> unsolvedTargetList

    if fn.IsRegisteredCandidate jmpAddr tblAddr then evts
    else
      (fn: RegularFunction).RegisterTblCandidate jmpAddr tblAddr

      let funDataMgr = dataMgr.GetFunDataMgr fn.EntryPoint
      let tbls = funDataMgr.JumpTables
      tbls.Register fn.EntryPoint jmpAddr tblAddr tblAddr 32<rt> |> ignore
      fn.MarkIndJumpAsJumpTbl jmpAddr tblAddr


      let funDataMgr = dataMgr.GetFunDataMgr fn.EntryPoint
      let endPoint = funDataMgr.JumpTables.FindConfirmedEndPoint
                       (tblAddr, jmpAddr)
      if funDataMgr.IsVisitedTbl tblAddr then
        evts
      elif tblAddr = endPoint then (* First entry *)
        let jt = funDataMgr.JumpTables[(tblAddr, jmpAddr)]
        let unsolvedTargetList = recoverTblEntry bld hdl codeMgr dataMgr
                                                  fn jt tblAddr List.Empty
        unsolvedTargetList
        |> List.iter(fun target ->
           fn.RegisterUnsolvedEdges jt.InstructionAddr target IndirectJmpEdge)
        evts
        //|> List.fold(fun evts target ->
        //    CFGEvents.addFuncEvt target ArchOperationMode.NoMode evts) evts
      else
        evts


  override __.RecoverTarget hdl codeMgr dataMgr fn evts =
    (*
    let rec recoverTblEntry
        bld hdl codeMgr (dataMgr: DataManager) fn (jt: JumpTable) entryAddr =
      match recoverOneEntry bld hdl codeMgr dataMgr fn jt entryAddr with
      | Ok () ->
        match getNextRecoveryTargetFromTable hdl codeMgr dataMgr fn List.Empty
                [jt.JTStartAddr] with
        | Some (jt, entryAddr), _ ->
          recoverTblEntry bld hdl codeMgr dataMgr fn jt entryAddr
        | None, _ -> Ok ()
      | Error e -> Error e

    match getNextAnalysisTarget hdl codeMgr dataMgr fn with
    | Some (jt, entryAddr) ->
      match recoverTblEntry bld hdl codeMgr dataMgr fn jt entryAddr with
      //match recoverOneEntry bld hdl codeMgr dataMgr fn jt entryAddr with
      | Ok () ->
        RecoverContinue
      | Error ErrorVisitedSwitchEntry -> RecoverContinue
      | Error e ->
        //let res = rollback codeMgr dataMgr fn evts jt entryAddr e
        //RecoverDone res
        fn.MarkRecoveryDone jt.JTStartAddr
        RecoverContinue
    | None -> RecoverDone <| Ok evts
    *)
    RecoverDone <| Ok evts

  override __.OnError codeMgr dataMgr fn evts errInfo =
    match errInfo with
    | oldJT, newTblAddr ->
      let oldBrAddr = oldJT.InstructionAddr
      let oldFnAddr = oldJT.HostFunctionEntry
      let oldTblAddr = oldJT.JTStartAddr
      let funDataMgr = dataMgr.GetFunDataMgr fn.EntryPoint
#if CFGDEBUG
      dbglog "IndJmpRecovery" "@%x Failed to make jmptbl due to overlap: %x@%x"
        fn.EntryPoint oldBrAddr oldFnAddr
#endif
      (*
      funDataMgr.JumpTables.UpdatePotentialEndPoint oldTblAddr newTblAddr
      let fnToRollback = codeMgr.FunctionMaintainer.FindRegular oldFnAddr
      fnToRollback.JumpTableAddrs |> List.iter (fun tAddrList ->
        tAddrList |> List.iter(fun tAddr ->
          funDataMgr.JumpTables.UpdateConfirmedEndPoint tAddr tAddr))
      *)
      finishIfEmpty codeMgr oldFnAddr oldBrAddr evts

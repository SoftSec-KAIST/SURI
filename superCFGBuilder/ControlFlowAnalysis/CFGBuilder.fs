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
open B2R2
open B2R2.BinIR
open B2R2.FrontEnd
open B2R2.FrontEnd.BinFile
open B2R2.FrontEnd.BinFile.ELF
open B2R2.FrontEnd.BinLifter
open B2R2.FrontEnd.BinLifter.Intel
open SuperCFG.BinGraph
open SuperCFG.ControlFlowAnalysis.FortranRegularJmpResolution
open SuperCFG.ControlFlowGraph
open SuperCFG.DataFlow

open SuperCFG.SSA
open SuperCFG.ControlFlowAnalysis.IRHelper
open SuperCFG.ControlFlowAnalysis

/// Information about a fall-through block to resolve next.
type FallThroughInfo =
  | FTCall of caller: ProgramPoint
            * callSite: Addr
            * callee: Addr
            * ftAddr: Addr
  | FTNonCall of srcPp: ProgramPoint * ftAddr: Addr

[<AutoOpen>]
module private CFGBuilder =
  /// In this function, we only consider a single instruction-level basic block.
  /// We parse its corresponding IR-level basic blocks as well as
  /// intra-instruction edges. But we don't add inter-instruction CFG edges.
  /// Instead, this function returns a list of CFGEvents to perform in the next
  /// iteration.
  let buildBBL hdl isa (codeMgr: CodeManager) funCodeMgr func mode leaderAddr evts =
    match (funCodeMgr: FunCodeManager).ParseBBL hdl isa
            codeMgr.FunctionMaintainer codeMgr.ExceptionTable
            mode leaderAddr func evts with
    | Ok evts -> Ok evts
    | Error ErrorCase.ParsingFailure ->
      Error ErrorParsing
    | Error _ -> Utils.impossible ()

  let buildOverlappedBBL
      hdl isa (codeMgr: CodeManager) funCodeMgr func mode leaderAddr evts =
    match (funCodeMgr: FunCodeManager).ParseOverlappedBBL hdl isa
            codeMgr.FunctionMaintainer codeMgr.ExceptionTable
            mode leaderAddr func evts with
    | Ok evts -> Ok evts
    | Error ErrorCase.ParsingFailure ->
      Error ErrorParsing
    | Error _ -> Utils.impossible ()

  let removeFuncAnalysisEvents entry evts =
    let funAnalysisAddrs =
      evts.FunctionAnalysisAddrs |> List.filter(fun x -> x <> entry)
    let evts = { evts with FunctionAnalysisAddrs = funAnalysisAddrs }
    Ok evts

  let buildFunction (hdl: BinHandle) isa (codeMgr: CodeManager) _dataMgr entry mode evts =
     if not (hdl.File.IsExecutableAddr entry) then
        codeMgr.RegisterFalseFunc entry |> ignore
        removeFuncAnalysisEvents entry evts
     else
      let func =
        match codeMgr.FunctionMaintainer.TryFindRegular entry with
        | Some func -> func
        | None ->
          codeMgr.FunctionMaintainer.GetOrAddFunction entry

      (_dataMgr: DataManager).GetOrAddFunDataMgr entry |> ignore

      let funCodeMgr = codeMgr.GetOrAddFunCodeMgr entry

      if func.HasVertex (ProgramPoint (entry, 0)) then Ok evts
      else
        (match codeMgr.ExceptionTable.GetFDERangeDicts().TryFind entry with
         | Some fdeEnd -> func.RegisterFDERange entry fdeEnd
         | _ ->
           match codeMgr.ExceptionTable.TryFindValidFDERange entry with
           | Some (KeyValue(fdeStart,fdeEnd))
            -> func.RegisterFDERange fdeStart fdeEnd
           | _ ->
             match codeMgr.GetValidNextBoundary entry with
             | Some tmpEnd -> func.RegisterFDERange entry tmpEnd
             | _ -> func.RegisterFDERange entry (uint64 0))
        |> ignore

        match buildBBL hdl isa codeMgr funCodeMgr func mode entry evts with
        (* Build new block *)
        | Ok evts -> Ok evts
        | Error ErrorParsing ->
          codeMgr.FunctionMaintainer.RemoveFunction entry |> ignore
          codeMgr.RemoveFunCodeMgr entry |> ignore
          _dataMgr.RemoveFunDataMgr entry |> ignore
          codeMgr.RegisterFalseFunc entry |> ignore
          removeFuncAnalysisEvents entry evts
          //Error ErrorParsing
        | Error _ -> Utils.impossible ()

    (*
    match codeMgr.TryGetBBL entry with
    | Some bbl when bbl.FunctionEntry <> entry -> (* Need to split *)
      codeMgr.HistoryManager.Record <| CreatedFunction entry
      if bbl.BlkRange.Min <> entry then
        let _, evts = codeMgr.SplitBlock bbl entry evts
        let _, evts = codeMgr.PromoteBBL hdl entry bbl evts
        Ok evts
      else
        let _, evts = codeMgr.PromoteBBL hdl entry bbl evts
        Ok evts
    | _ ->
      let func =
        match codeMgr.FunctionMaintainer.TryFindRegular entry with
        | Some func -> func
        | None -> codeMgr.FunctionMaintainer.GetOrAddFunction entry
      if func.HasVertex (ProgramPoint (entry, 0)) then Ok evts
      else buildBBL hdl codeMgr func mode entry evts (* Build new block *)
    *)

  let inline isIntrudingBlk (funCodeMgr: FunCodeManager) addr =
    match funCodeMgr.TryGetBBL addr with
    | Some bbl -> addr <> bbl.BlkRange.Min
    | None -> false

  let splitAndConnectEdge
      hdl (funCodeMgr: FunCodeManager) (fn: RegularFunction) src dst edge evts =
    let bbl = funCodeMgr.GetBBL dst
    match funCodeMgr.SplitBlock fn bbl dst evts with
    | Some front, evts ->
      (* When a bbl is self-dividing itself, then the dst block should have a
         self-loop. For example, if a BBL has three instructions (a, b, c) and
         if c has a branch to b, then we split the block into (a) and (b, c),
         and the second block will have a self-loop. *)
      let src = if src = front then ProgramPoint (dst, 0) else src
      fn.AddEdge (src, ProgramPoint (dst, 0), edge)
      Ok evts
    | _, evts ->
      fn.AddEdge (src, ProgramPoint (dst, 0), edge)
      Ok evts
    (*
    if bbl.FunctionEntry <> (fn: RegularFunction).EntryPoint then
      (* There is an edge from a function to another function, and the edge is
         intruding an existing bbl, too. In this case, the destination address
         becomes a new function. This happens when there is an edge to the
         middle of a ".cold" snippet. *)
      let _, evts = codeMgr.SplitBlock bbl dst evts
      let _, evts = codeMgr.PromoteBBL hdl dst bbl evts
      Ok evts
    else
      match codeMgr.SplitBlock bbl dst evts with
      | Some front, evts ->
        (* When a bbl is self-dividing itself, then the dst block should have a
           self-loop. For example, if a BBL has three instructions (a, b, c) and
           if c has a branch to b, then we split the block into (a) and (b, c),
           and the second block will have a self-loop. *)
        let src = if src = front then ProgramPoint (dst, 0) else src
        fn.AddEdge (src, ProgramPoint (dst, 0), edge)
        Ok evts
      | _, evts ->
        fn.AddEdge (src, ProgramPoint (dst, 0), edge)
        Ok evts
    *)

  let getCallee (codeMgr: CodeManager) callee evts =
    match codeMgr.FunctionMaintainer.TryFind (addr=callee) with
    | Some calleeFunc -> calleeFunc, evts
    | None ->
      let calleeFunc = codeMgr.FunctionMaintainer.GetOrAddFunction callee
      codeMgr.GetOrAddFunCodeMgr callee |> ignore
      let evts = CFGEvents.addFuncEvt callee ArchOperationMode.NoMode evts
      calleeFunc :> Function, evts

  /// If there is a tail-call from my function to a callee, and the callee is a
  /// returning function, then we know that my function should *not* no return.
  let markAsReturning (myfn: RegularFunction) isTailCall (calleeFn: Function) =
    if isTailCall
      && (calleeFn.NoReturnProperty = NotNoRet
          || calleeFn.NoReturnProperty = NotNoRetConfirmed)
    then myfn.NoReturnProperty <- NotNoRet
    else ()

  let tryGetRelocatableFunction (codeMgr: CodeManager) dataMgr relocSite =
    let sym = (dataMgr: DataManager).RelocatableFuncs[relocSite]
    let funcName = sym.SymName
    match codeMgr.FunctionMaintainer.TryFind funcName with
    | Some calleeFn -> Some calleeFn.EntryPoint
    | _ -> None

  let buildCall codeMgr dataMgr fn callSite callee isTailCall evts =
    let funCodeMgr =
      (codeMgr: CodeManager).GetFunCodeMgr (fn: RegularFunction).EntryPoint
    let callerBBL = funCodeMgr.GetBBL callSite
    let callerPp = Set.maxElement callerBBL.IRLeaders
    let relocFuncs = (dataMgr: DataManager).RelocatableFuncs
    let relocSite = callSite + 1UL
    let callee =
      if relocFuncs.ContainsKey relocSite then
        tryGetRelocatableFunction codeMgr dataMgr relocSite
      //if callee is false function
      elif codeMgr.IsFalseFunc callee then
        None
      else Some callee
    let callerV = (fn: RegularFunction).FindVertex callerPp
    let last = callerV.VData.LastInstruction
    let ftAddr = last.Address + uint64 last.Length
    if (not isTailCall) && fn.IsInFDERange ftAddr then
      match callee with
      | Some 0UL -> Ok evts (* Ignore the callee for "call 0" cases. *)
      | Some callee when ftAddr <> callee ->
        (* No fakeblock for getpc thunks. *)
        let callee = codeMgr.FunctionMaintainer.ConvertPLTToInternalRef callee
        (fn: RegularFunction).AddEdge (callerPp, callSite, callee, isTailCall)
        let _, evts = getCallee codeMgr callee evts
        //markAsReturning fn isTailCall calleeFn
        evts
        |> CFGEvents.addRetEvt fn callee ftAddr callSite
        |> CFGEvents.addEdgeEvt fn callerPp ftAddr CallFallThroughEdge
        |> Ok
      | Some _ ->
        evts
        |> CFGEvents.addEdgeEvt fn callerPp ftAddr CallFallThroughEdge
        |> Ok
      | _ -> Ok evts
    else
      match callee with
      | Some 0UL -> Ok evts
      | Some callee ->
        let callee = codeMgr.FunctionMaintainer.ConvertPLTToInternalRef callee
        (fn: RegularFunction).AddEdge (callerPp, callSite, callee, isTailCall)
        let _, evts = getCallee codeMgr callee evts
        Ok evts
      | _ -> Ok evts

  let buildIndCall (codeMgr: CodeManager) fn callSite evts =
    let funCodeMgr = codeMgr.GetFunCodeMgr (fn:RegularFunction).EntryPoint
    let callerPp = Set.maxElement (funCodeMgr.GetBBL callSite).IRLeaders
    (fn: RegularFunction).AddEdge (callerPp, callSite, None, false)
    //Add fall through edge if fall though block is valid
    let callerV = (fn: RegularFunction).FindVertex callerPp
    let last = callerV.VData.LastInstruction
    let ftAddr = last.Address + uint64 last.Length
    if fn.IsInFDERange ftAddr then
      evts
      |> CFGEvents.addRetEvt fn 0UL ftAddr callSite
      |> CFGEvents.addEdgeEvt fn callerPp ftAddr CallFallThroughEdge
      |> Ok
    else Ok evts

  let buildIndTailCall (codeMgr: CodeManager) fn callSite
                       (calleeKind: CalleeKind option) evts =
    let funCodeMgr = codeMgr.GetFunCodeMgr (fn:RegularFunction).EntryPoint
    let callerPp = Set.maxElement (funCodeMgr.GetBBL callSite).IRLeaders
    (fn: RegularFunction).AddEdge (callerPp, callSite, calleeKind, true)
    Ok evts

  let buildTailCall codeMgr dataMgr fn caller calleeAddr evts =
    buildCall codeMgr dataMgr fn caller calleeAddr true evts

  let makeCalleeNoReturn (codeMgr: CodeManager) fn callee callSite =
    let funCodeMgr = codeMgr.GetFunCodeMgr (fn:RegularFunction).EntryPoint
    let callBlk = funCodeMgr.GetBBL callSite
    let srcPp = ProgramPoint (callBlk.BlkRange.Min, 0)
    let src = (fn: RegularFunction).FindVertex srcPp
    DiGraph.GetSuccs (fn.IRCFG, src)
    |> List.iter (fun dst ->
      (* Do not remove fake block *)
      if not <| dst.VData.IsFakeBlock () then
        let edge = DiGraph.FindEdgeData (fn.IRCFG, src, dst)
        match edge with
        // Do not remove ExceptionFallThroughEdge
        | ExceptionFallThroughEdge -> ()
        | _ -> fn.RemoveEdge (src, dst))
    match codeMgr.FunctionMaintainer.TryFind (addr=callee) with
    | Some callee ->
#if CFGDEBUG
      dbglog "CFGBuilder"
        "Ret edge connects to an existing func, %x must be noret"
        callee.EntryPoint
#endif
      callee.NoReturnProperty <- NoRet
    | None ->
#if CFGDEBUG
      dbglog "CFGBuilder"
        "Callee function %x does not exist" callee
#endif
      ()


  let buildRet codeMgr (fn: RegularFunction) callee ftAddr callSite evts =
    let funCodeMgr =
      (codeMgr: CodeManager).GetFunCodeMgr (fn:RegularFunction).EntryPoint
    match funCodeMgr.TryGetBBL ftAddr with
    | Some fallBlk when fallBlk.FunctionEntry = fn.EntryPoint ->
      fn.AddEdge (callSite=callSite, callee=callee, ftAddr=ftAddr)
      Ok evts
    | _ ->  makeCalleeNoReturn codeMgr fn callee callSite
            Ok evts

  let createJumpAfterLockChunk (codeMgr: CodeManager) fn chunkStartAddr addrs =
    let funCodeMgr = codeMgr.GetFunCodeMgr (fn:RegularFunction).EntryPoint
    let last = List.rev addrs |> List.head
    let lastIns = funCodeMgr.GetInstruction last
    let size = last + uint64 lastIns.Instruction.Length - chunkStartAddr
    let wordSize = lastIns.Instruction.WordSize
    let stmts = lastIns.Stmts
    InlinedAssembly.Init chunkStartAddr (uint32 size) wordSize stmts

  /// Build a regular edge, which is any edge that is not a call, an indirect
  /// call, nor a ret edge.
  let buildRegularEdge (hdl: BinHandle) isa (codeMgr: CodeManager) dataMgr fn src dst edge evts =
    let mode = ArchOperationMode.NoMode (* XXX: put mode in the event. *)
    let funCodeMgr = codeMgr.GetFunCodeMgr (fn:RegularFunction).EntryPoint
    if not (hdl.File.IsExecutableAddr (fn: RegularFunction).EntryPoint) then
      Error ErrorConnectingEdge (* Invalid bbl encountered. *)
    elif funCodeMgr.HasBBL dst then
      let dstPp = ProgramPoint (dst, 0)
      let dstBlk = funCodeMgr.GetBBL dst
      if fn.HasVertex dstPp then
        fn.AddEdge (src, ProgramPoint (dst, 0), edge)
        Ok evts
      elif (edge = CallFallThroughEdge || edge = ExceptionFallThroughEdge)
           && dstBlk.FunctionEntry = dst then
        Ok evts (* Undetected no-return case, so we do not add fall-through. *)
      else (* Tail-call. *)
        buildFunction hdl isa codeMgr dataMgr dst mode evts
        |> Result.bind (buildCall codeMgr dataMgr fn src.Address dst true)
    elif isIntrudingBlk funCodeMgr dst then
      splitAndConnectEdge hdl funCodeMgr fn src dst edge evts
    elif not (funCodeMgr.HasInstruction dst)
      && fn.IsAddressCovered dst then (* Jump to the middle of an instr *)
      match InlinedAssemblyPattern.checkInlinedAssemblyPattern hdl dst with
      | NotInlinedAssembly ->
        (* create new Basic Block for superset CFG*)
        match buildOverlappedBBL hdl isa codeMgr funCodeMgr fn mode dst evts with
        | Ok evts -> fn.AddEdge (src, ProgramPoint (dst, 0), edge); Ok evts
        | Error e ->
          funCodeMgr.RegisterFalseBlock dst |> ignore
          fn.AddInvalidAddr dst
          match edge with
          // In case of jump table recovery, we report the errors
          | IndirectJmpEdge when (evts.BasicEvents |> List.isEmpty)
                        && ((evts.FunctionAnalysisAddrs |> List.length) < 2) ->
            Error e
          //Superset CFG allows parsing errors
          | _ -> Ok evts
          //Error e
        //Error ErrorConnectingEdge
      | JumpAfterLock addrs ->
        let patternStart = List.head addrs
        let chunk = createJumpAfterLockChunk codeMgr fn patternStart addrs
        funCodeMgr.ReplaceInlinedAssemblyChunk fn addrs chunk evts |> Ok
    elif dst = 0UL then
      Ok evts (* "jmp 0" case (as in "call 0"). *)
    elif hdl.File.Type = FileType.ObjFile
      && not (hdl.File.IsExecutableAddr dst) then
      Ok evts (* call outside a section (occurs in an object file) *)
    else
      match buildBBL hdl isa codeMgr funCodeMgr fn mode dst evts with
      | Ok evts -> fn.AddEdge (src, ProgramPoint (dst, 0), edge); Ok evts
      | Error e ->
        funCodeMgr.RegisterFalseBlock dst |> ignore
        match edge with
        // In case of jump table recovery, we report the errors
        | IndirectJmpEdge when (evts.BasicEvents |> List.isEmpty)
                       && ((evts.FunctionAnalysisAddrs |> List.length) < 2) ->
          Error e
        //Superset CFG allows parsing errors
        | _ ->
          funCodeMgr.RegisterFalseBlock dst |> ignore
          fn.AddInvalidAddr dst
          Ok evts
        //Error e

  let checkIfIndCallAnalysisRequired (fn: RegularFunction) exitNodes =
    exitNodes
    |> List.exists (fun (v: Vertex<IRBasicBlock>) ->
      v.VData.IsFakeBlock ()
      && fn.IsUnresolvedIndirectCall v.VData.FakeBlockInfo.CallSite)

  /// Does the vertex (v) end with a regular (returning) syscall?
  let inline isReturningSyscall hdl isa (noret: NoReturnFunctionIdentification) v =
    match (v: Vertex<IRBasicBlock>).VData.SyscallTail with
    | UnknownSyscallTail ->
      if noret.IsNoRetSyscallBlk hdl isa v then
        v.VData.SyscallTail <- ExitSyscallTail; false
      else
        v.VData.SyscallTail <- RegularSyscallTail; true
    | RegularSyscallTail -> true
    | _ -> false

  /// Obtain fall-through information from a fake block and add it to the
  /// accumulator. The information includes a 4-tuple: (caller program point,
  /// call instruction address, callee's address, fall-through address).
  let accFTInfoFromFake (codeMgr: CodeManager) fn (v: IRVertex) infos =
    let callSite = v.VData.FakeBlockInfo.CallSite
    let funCodeMgr = codeMgr.GetFunCodeMgr (fn:RegularFunction).EntryPoint
    let callerPp = Set.maxElement (funCodeMgr.GetBBL callSite).IRLeaders
    let calleeAddr = v.VData.PPoint.Address
    let callerV = (fn: RegularFunction).FindVertex callerPp
    let last = callerV.VData.LastInstruction
    let ftAddr = last.Address + uint64 last.Length
    FTCall (callerPp, callSite, calleeAddr, ftAddr) :: infos

  /// Check if a call instruction is indeed a system call. In particular,
  /// call dword ptr [gs:0x10] is a system call in x86/x64 Linux environment.
  /// We pattern-match the instruction.
  let isIndirectSyscall (hdl: BinHandle) isa (fn: RegularFunction) (v: Vertex<IRBasicBlock>) =
    match hdl.File.Format, isa.Arch with
    | FileFormat.ELFBinary, Architecture.IntelX86 ->
      let caller = DiGraph.GetPreds (fn.IRCFG, v) |> List.head
      let callIns = caller.VData.LastInstruction :?> IntelInstruction
      match callIns.Prefixes, callIns.Operands with
      | Prefix.PrxGS, OneOperand (OprMem (None, None, Some 16L, _)) -> true
      | _ -> false
    | _ -> false

  /// Scan all exit nodes and obtain two things: (1) a list of addresses that
  /// are a target of fall-through edges; and (2) a set of function addresses
  /// which need to perform the no-ret analysis. We assume that the indirect
  /// call recovery is performed on the given function (fn).
  let scanCandidates hdl isa (codeMgr: CodeManager) noret fn exitNodes =
    exitNodes
    |> List.fold (fun (infos) (v: Vertex<IRBasicBlock>) ->
      if not (v.VData.IsFakeBlock ()) then
        if isReturningSyscall hdl isa noret v then
          let last = v.VData.LastInstruction
          let ftAddr = last.Address + uint64 last.Length
          // Disallow adding fallthrough event
          // only when the block was known as an invalid region
          if (fn: RegularFunction).IsInvalidAddr ftAddr then
            infos
          else
            FTNonCall (v.VData.PPoint, ftAddr) :: infos
        else infos
      elif isIndirectSyscall hdl isa fn v then
        (* First mark it as resolved indirect call so that indirect call
           analyzer will not analyze this again. *)
        let callsite = v.VData.FakeBlockInfo.CallSite
        fn.UpdateCallEdgeInfo (callsite, IndirectCallees Set.empty)
        v.VData.FakeBlockInfo <- { v.VData.FakeBlockInfo with IsSysCall = true }
        let caller = DiGraph.GetPreds (fn.IRCFG, v) |> List.head
        if noret.IsNoRetSyscallBlk hdl isa caller then infos
        else accFTInfoFromFake codeMgr fn v infos
      else
        infos
        //Utils.impossible()
        (*let callSite = v.VData.FakeBlockInfo.CallSite
        (fn: RegularFunction).CallTargets callSite
        |> Set.fold (fun (infos, toAnalyze) calleeAddr ->
          match codeMgr.FunctionMaintainer.TryFind calleeAddr with
          | Some callee ->
            match callee.NoReturnProperty with
            | NotNoRetConfirmed | NotNoRet ->
              if v.VData.FakeBlockInfo.IsTailCall then infos, toAnalyze
              else accFTInfoFromFake codeMgr fn v infos, toAnalyze
            | ConditionalNoRet arg ->
              let funCodeMgr =
                codeMgr.GetFunCodeMgr (fn:RegularFunction).EntryPoint
              let callerPp =
                Set.maxElement (funCodeMgr.GetBBL callSite).IRLeaders
              let callerV = fn.FindVertex callerPp
              if noret.HasNonZeroArg hdl callerV arg then infos, toAnalyze
              elif v.VData.FakeBlockInfo.IsTailCall then infos, toAnalyze
              else accFTInfoFromFake codeMgr fn v infos, toAnalyze
            | UnknownNoRet ->
              if callee.EntryPoint = fn.EntryPoint then (* Rec *)
                infos, toAnalyze
              else infos, Set.add calleeAddr toAnalyze
            | _ -> infos, toAnalyze
          | None ->
            infos, toAnalyze ) (infos, toAnalyze) *)
    ) ([])

  let addFallThroughEvts (hdl: BinHandle) codeMgr fn ftInfos evts =
    let evts =
      CFGEvents.addPerFuncAnalysisEvt (fn: RegularFunction).EntryPoint evts
    ftInfos
    |> List.fold (fun evts ftInfo ->
      match ftInfo with
      | FTCall (caller, callSite, callee, ftAddr) ->
        if not (hdl.File.IsExecutableAddr ftAddr) then
          let calleeFn = (codeMgr: CodeManager).FunctionMaintainer.Find callee
          calleeFn.NoReturnProperty <- NoRet
          evts
        else
          evts
          |> CFGEvents.addRetEvt fn callee ftAddr callSite
          |> CFGEvents.addEdgeEvt fn caller ftAddr CallFallThroughEdge
      | FTNonCall (srcPp, ftAddr) ->
        evts |> CFGEvents.addEdgeEvt fn srcPp ftAddr FallThroughEdge
      ) evts

  let updateCalleeInfo (codeMgr: CodeManager) (func: RegularFunction) =
    func.IRCFG.IterVertex (fun v ->
      if v.VData.IsFakeBlock () && v.VData.PPoint.Address <> 0UL then
        match codeMgr.FunctionMaintainer.TryFind v.VData.PPoint.Address with
        | Some calleeFunc ->
          if calleeFunc.FunctionKind = FunctionKind.Regular then
            let calleeFunc = calleeFunc :?> RegularFunction
            v.VData.FakeBlockInfo <-
              { v.VData.FakeBlockInfo with
                  UnwindingBytes = calleeFunc.AmountUnwinding
                  GetPCThunkInfo = calleeFunc.GetPCThunkInfo }
          else
            v.VData.FakeBlockInfo <- { v.VData.FakeBlockInfo with IsPLT = true }
        | None -> ()
      else ())

  let runIndirectCallRecovery hdl isa codeMgr dataMgr entry indcall fn evts =
#if CFGDEBUG
    dbglog "CFGBuilder" "@%x Started indcall analysis" entry
#endif
    updateCalleeInfo codeMgr fn
    CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint evts
    |> (indcall: PerFunctionAnalysis).Run hdl isa codeMgr dataMgr fn

  let runIndirectJmpRecovery hdl isa codeMgr dataMgr entry indjmp fn evts =
#if CFGDEBUG
    dbglog "CFGBuilder" "@%x Started indjmp analysis" entry
#endif
    updateCalleeInfo codeMgr fn
    CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint evts
    |> (indjmp: PerFunctionAnalysis).Run hdl isa codeMgr dataMgr fn

  let ResolveFortranIndirectJmp
      hdl codeMgr dataMgr entry fortranIndJmp (fn:RegularFunction) evts =
#if CFGDEBUG
    dbglog "CFGBuilder" "@%x Started fortranIndJmp analysis" entry
#endif
    //CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint evts
    (fortranIndJmp: FortranRegularJmpResolution).Resolve
      hdl codeMgr dataMgr fn evts

  let private hasPath src dst evts =
    let map = evts.CalleeAnalysisEdges
    let visited = HashSet<Addr> ()
    let rec dfs addrs =
      let addr = List.head addrs
      if addr = dst then true, List.rev addrs
      elif visited.Contains addr then false, addrs
      else
        visited.Add addr |> ignore
        Map.tryFind addr map
        |> Option.defaultValue Set.empty
        |> Set.fold (fun (found, path) succ ->
          if found then found, path
          else dfs (succ :: addrs)) (false, addrs)
    dfs [src]

  /// We consider mutually recursive functions to be "returning", i.e., "not no
  /// ret". This is to make sure that our analysis to terminate. When there is a
  /// function call chain a -> b -> c -> a -> ..., then we cannot decide the
  /// no-ret property of each function because our analysis assumes that all the
  /// callees of a function should be analyzed first. Thus, when we detect
  /// mutual recursions,  we simply consider the first function in the chain as
  /// a returning function.
  let makeMutuallyRecursiveFunctionsNotNoRet codeMgr myAddr toAnalyze evts =
    toAnalyze
    |> Set.iter (fun addr ->
      match hasPath addr myAddr evts with
      | true, path ->
        let funcsInPath =
          path |> List.map (fun a ->
            (codeMgr: CodeManager).FunctionMaintainer.FindRegular (a))
        if funcsInPath
           |> List.exists (fun f -> f.NoReturnProperty <> UnknownNoRet)
        then () (* No need to worry about infinite loop. *)
        else
          funcsInPath
          |> List.choose (fun f ->
            if f.NoReturnProperty = UnknownNoRet then Some f else None)
          |> List.sortByDescending (fun callee ->
            let nextAddr =
              codeMgr.FunctionMaintainer.FindNextFunctionAddr callee
            nextAddr - callee.MaxAddr)
          |> List.tryHead (* Take the one with the biggest gap *)
          |> function
            | Some callee ->
#if CFGDEBUG
              dbglog "CFGBuilder" "Make %x as NotNoRet (%x -> %x)"
                callee.EntryPoint addr myAddr
#endif
              callee.NoReturnProperty <- NotNoRet
            | None -> ()
      | false, _ -> ())

  /// Before we run the no-return analysis on this function (fn), we should
  /// first analyze the other callees, and come back later.
  let analyzeCalleesFirst codeMgr (fn: RegularFunction) toAnalyze evts =
    makeMutuallyRecursiveFunctionsNotNoRet codeMgr fn.EntryPoint toAnalyze evts
    let evts = CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint evts
    toAnalyze
    |> Set.fold (fun evts entry ->
      CFGEvents.addPerFuncAnalysisEvt entry evts
      |> CFGEvents.addCalleeAnalysisEvt fn.EntryPoint entry) evts
    |> Ok

  let retrieveStackAdjustment (ins: Instruction) =
    match ins.Immediate () with
    | true, v -> int64 v
    | false, _ -> 0L

  /// Assuming that "ret NN" instructions are used, compute how much stack
  /// unwinding is happening for the given function.
  ///
  /// TODO: We can extend this analysis further to make it more precise.
  let computeStackUnwindingAmount cfg =
    DiGraph.GetExits cfg
    |> List.fold (fun acc (v: Vertex<IRBasicBlock>) ->
      if Option.isSome acc || v.VData.IsFakeBlock () then acc
      else
        let ins = v.VData.LastInstruction
        if ins.IsRET () then retrieveStackAdjustment ins |> Some
        else acc) None
    |> function
       | None -> 0L
       | Some n -> n

  /// Update extra function information as we have finished all the per-function
  /// analyses.
  let finalizeFunctionInfo (func: RegularFunction) =
    let amountUnwinding = computeStackUnwindingAmount func.IRCFG
    if amountUnwinding <> 0L then func.AmountUnwinding <- amountUnwinding
    else ()

  let examineUnsolvableEdges (hdl:BinHandle)
    (fn: RegularFunction) (codeMgr: CodeManager) evts =
    let fdeRanges =
      fn.UnsolvedEdges
      |> Seq.fold(fun acc (src, dst, edgeType) ->
          match codeMgr.ExceptionTable.GetFDERangeDicts().TryFind dst with
          | Some fdeEnd -> (dst, fdeEnd)::acc
          | _ ->  acc
      ) List.Empty
    match fdeRanges with
    | (fdeStart, fdeEnd)::_ ->
      //change FDE range
      fn.RegisterFDERange fdeStart fdeEnd |> ignore
      //register merged info
      match codeMgr.FunctionMaintainer.TryFindRegular fdeStart with
      | Some target_fn -> target_fn.RegisterAbsorber fn.EntryPoint
      | _ -> ()

      //get solvable edges
      let solvableEdges =
        fn.UnsolvedEdges
        |> Seq.fold(fun acc (src, dst, edge) ->
            if fdeStart <= dst && dst < fdeEnd then
              (src, dst, edge)::acc
            else acc
          ) List.Empty

      solvableEdges
      |> Seq.iter(fun (a,b,c) -> fn.UnregisterUnsolvedEdges (a,b,c) |> ignore)

      //add edges that belongs to new FDE range
      let funCodeMgr = codeMgr.GetFunCodeMgr fn.EntryPoint
      let evts =
        solvableEdges
        |> Seq.distinct
        |> Seq.fold(fun evts (src, dst, edge) ->
          match funCodeMgr.TryGetBBL src with
          | Some bbl ->
            let srcPp = ProgramPoint(bbl.BlkRange.Min, 0)
            evts |>  CFGEvents.addEdgeEvt fn srcPp dst edge
          | None -> Utils.impossible()
         ) evts
      evts |> CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint
    | [] ->
      let funCodeMgr = codeMgr.GetFunCodeMgr fn.EntryPoint

      //otherwise, make unsolved targets as tail call target
      let evts =
        fn.UnsolvedEdges
        |> Seq.distinct
        |> Seq.fold(fun evts (src, dst, edgeType) ->
            match edgeType with
            | IndirectJmpEdge ->
              match codeMgr.GetValidNextBoundary dst with
              | Some tmpEnd ->
                let tStart = match codeMgr.GetValidPrevBoundary dst with
                             | Some tStart -> tStart
                             | _ ->
                               let text = hdl.File.GetTextSection ()
                               text.Address
                fn.RegisterFDERange tStart tmpEnd |> ignore
                match funCodeMgr.TryGetBBL src with
                | Some bbl ->
                  let srcPp = ProgramPoint(bbl.BlkRange.Min, 0)
                  evts |>  CFGEvents.addEdgeEvt fn srcPp dst edgeType
                | None -> Utils.impossible()
              | _ -> Utils.impossible()
              //register it to false bbl
              //funCodeMgr.RegisterFalseBlock dst |> ignore
            | _ when src > dst -> //it may part function
              //find FDE Start Address
              match codeMgr.ExceptionTable.TryFindValidFDERange dst with
              | Some (KeyValue(fdeStart, fdeEnd))
                  when fdeStart < dst && dst < fdeEnd ->

                  //register new FDE
                  fn.RegisterFDERange fdeStart fdeEnd |> ignore
                  //Then, find relavent function
                  match codeMgr.FunctionMaintainer.TryFindRegular fdeStart with
                  //Register current function as absorber
                  | Some target_fn -> target_fn.RegisterAbsorber fn.EntryPoint
                  | _ -> ()
              | _ ->
                  match (codeMgr.GetValidNextBoundary dst) with
                  | Some tmpEnd ->
                    let tStart = match codeMgr.GetValidPrevBoundary dst with
                                 | Some tStart -> tStart
                                 | _ ->
                                   let text = hdl.File.GetTextSection ()
                                   text.Address
                    fn.RegisterFDERange tStart tmpEnd |> ignore
                    ()
                  | _ -> Utils.impossible()
                //(fn: RegularFunction).RegisterUnreachableFun dst

              match funCodeMgr.TryGetBBL src with
              | Some bbl ->
                let srcPp = ProgramPoint(bbl.BlkRange.Min, 0)
                evts |>  CFGEvents.addEdgeEvt fn srcPp dst edgeType
              | None -> Utils.impossible()
            | _ ->
              // register the block as tail call target
              // It may produce false-functions
              CFGEvents.addFuncEvt dst ArchOperationMode.NoMode evts
            ) evts

      //clear unsolved edges
      fn.ClearUnsolvedEdges()

      evts |> CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint

  let registerCodePtr (fn: RegularFunction) (codeMgr: CodeManager) evts =
    let funCodeMgr = codeMgr.GetFunCodeMgr fn.EntryPoint

    //Register Code pointers candidates which has ENDBR64 instruction
    let evts =
      funCodeMgr.CodePtrCandidates
      |> Seq.filter(fun entry -> funCodeMgr.GetLocalCodePtr.Contains entry
                                 |> not)
      |> Seq.fold(fun evts entry ->
            match codeMgr.FunctionMaintainer.TryFindRegular entry with
            | Some _ -> evts
            | _ ->
              CFGEvents.addFuncEvt entry ArchOperationMode.NoMode evts
            ) evts

    evts

  let runPerFuncAnalysis hdl isa codeMgr dataMgr entry noret
                         indcall indjmp fortranIndJmp tblAnalyzer evts =
    let fn = (codeMgr: CodeManager).FunctionMaintainer.FindRegular (addr=entry)
    let funCodeMgr = codeMgr.GetFunCodeMgr fn.EntryPoint
    let exits = DiGraph.GetExits (fn: RegularFunction).IRCFG
    let ftInfos = scanCandidates hdl isa codeMgr noret fn exits
    if not (List.isEmpty ftInfos) then
      addFallThroughEvts hdl codeMgr fn ftInfos evts |> Ok
    elif not (fn.YetAnalyzedIndirectJumpAddrs |> Seq.isEmpty) then
      runIndirectJmpRecovery hdl isa codeMgr dataMgr entry indjmp fn evts
    elif codeMgr.HasFunCodeMgr entry &&
        (tblAnalyzer: TblAnalyzer).HasTblCandidates hdl codeMgr dataMgr fn then
      tblAnalyzer.Run hdl isa codeMgr dataMgr fn evts
    elif fn.HasUnsolvedEdges then
      examineUnsolvableEdges hdl fn codeMgr evts |> Ok
    else
#if CFGDEBUG
      dbglog "CFGBuilder" "@%x Finalize with no-ret analysis" entry
#endif

      //let bFound, evts = ResolveFortranIndirectJmp
      //                        hdl codeMgr dataMgr entry fortranIndJmp fn evts
      // Register code pointer
      let evts = registerCodePtr fn codeMgr evts

      if isa.Arch = Architecture.EVM then ()
      else finalizeFunctionInfo fn

      updateCalleeInfo codeMgr fn

      //Register false functions
      fn.UnreachableFuns
      |> Seq.iter(codeMgr.RegisterFalseFunc >> ignore)

      removeFuncAnalysisEvents entry evts


/// This is the main class for building a CFG from a given binary.
type CFGBuilder (hdl, isa, codeMgr: CodeManager, dataMgr: DataManager) as this =
  let noret = NoReturnFunctionIdentification ()
  let indcall = IndirectCallResolution ()
  let indjmp = RegularJmpResolution (this) :> PerFunctionAnalysis
  let fortranIndJmp = FortranRegularJmpResolution ()

  let tblAnalyzer = TblAnalyzer ()

#if CFGDEBUG
  let countEvts evts =
    "(" + (List.length evts.BasicEvents).ToString ()
        + ", "
        + (List.length evts.FunctionAnalysisAddrs).ToString ()
        + " left)"
#endif

  let rec update evts =
    match evts with
    | Ok ({ BasicEvents = CFGFunc (entry, mode) :: tl } as evts) ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x %s %s"
        entry (nameof CFGFunc) (countEvts evts)
#endif
      let evts = { evts with BasicEvents = tl }
      update (buildFunction hdl isa codeMgr dataMgr entry mode evts)
    | Ok ({ BasicEvents = CFGEdge (fn, src, dst, edge) :: tl } as evts) ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x %s (%x -> %x; %s) %s"
        fn.EntryPoint (nameof CFGEdge)
        src.Address dst (CFGEdgeKind.toString edge) (countEvts evts)
#endif
      let evts = { evts with BasicEvents = tl }
      if not (hdl.File.IsExecutableAddr dst) then
        update (Ok evts)
      else
        update (buildRegularEdge hdl isa codeMgr dataMgr fn src dst edge evts)
    | Ok ({ BasicEvents = CFGCall (fn, csite, callee) :: tl } as evts) ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x %s (%x -> %x) %s"
        fn.EntryPoint (nameof CFGCall) csite callee (countEvts evts)
#endif
      let evts = { evts with BasicEvents = tl }
      update (buildCall codeMgr dataMgr fn csite callee false evts)
    | Ok ({ BasicEvents = CFGIndCall (fn, callSite) :: tl } as evts) ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x %s (%x) %s"
        fn.EntryPoint (nameof CFGIndCall) callSite (countEvts evts)
#endif
      let evts = { evts with BasicEvents = tl }
      update (buildIndCall codeMgr fn callSite evts)
    | Ok ({ BasicEvents = CFGRet (fn, callee, ft, callSite) :: tl } as evts) ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x %s (%x -> %x) (%x -> %x) %s"
        fn.EntryPoint (nameof CFGRet) callSite ft callee ft (countEvts evts)
#endif
      let evts = { evts with BasicEvents = tl }
      update (buildRet codeMgr fn callee ft callSite evts)
    | Ok ({ BasicEvents = CFGTailCall (fn, callSite, callee) :: tl } as evts) ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x %s (%x -> %x) %s"
        fn.EntryPoint (nameof CFGTailCall) callSite callee (countEvts evts)
#endif
      let evts = { evts with BasicEvents = tl }
      update (buildTailCall codeMgr dataMgr fn callSite callee evts)
    | Ok ({ BasicEvents = CFGIndTailCall (fn, callSite, callee) :: tl } as evts)
      ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x %s (%x) %s"
        fn.EntryPoint (nameof CFGIndTailCall) callSite (countEvts evts)
#endif
      let evts = { evts with BasicEvents = tl }
      update (buildIndTailCall codeMgr fn callSite (Some callee) evts)
    | Ok ({ BasicEvents = []
            FunctionAnalysisAddrs = fnAddr :: tl } as evts) ->
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "@%x per-func-analysis %s"
        fnAddr (countEvts evts)
#endif
      let evts = { evts with FunctionAnalysisAddrs = tl }
      match codeMgr.FunctionMaintainer.TryFindRegular fnAddr with
      | Some _ ->
        let ret = (runPerFuncAnalysis
          hdl isa codeMgr dataMgr fnAddr noret indcall indjmp fortranIndJmp
          tblAnalyzer evts)
        update (ret)
      | None -> update (Ok evts)
    | Ok ({ BasicEvents = [] }) -> (* FunctionAnalysisAddrs is empty *)
#if CFGDEBUG
      dbglog (nameof CFGBuilder) "Done %s" (nameof update)
#endif
      codeMgr.FunctionMaintainer.UpdateCallerCrossReferences () |> Ok
    | Error err -> Error err

  interface ICFGBuildable with
    member __.Update evts =
      update (Ok evts)

  /// Add new events to the event list (evts).
  member private __.AddNewFunction evts (entry, mode) =
    if codeMgr.FunctionMaintainer.Contains (addr=entry) then Ok evts
    elif not <| hdl.File.IsExecutableAddr entry then Error ErrorParsing
    else CFGEvents.addFuncEvt entry mode evts |> Ok

  /// This is the only function that is available to users, which takes in a
  /// list of known function entry infos and recover the whole CFGs, thereby
  /// updating both code manager and data manager. The return value is Error if
  /// a fatal error is encountered.
  member __.AddNewFunctions entries =
#if CFGDEBUG
    dbglog (nameof CFGBuilder) "Start by adding %d function(s) for %s"
      (List.length entries) (hdl.File.Path)
#endif
    entries |> Seq.iter(fun (addr, _) -> codeMgr.RegisterInitEntries addr)
    (* List.foldBack is used here to preserve the order of input entries *)
    List.foldBack (fun elm evts ->
      match evts with
      | Ok evts -> __.AddNewFunction evts elm
      | Error e -> Error e) entries (Ok CFGEvents.empty)
    |> function
      | Ok evts -> (__ :> ICFGBuildable).Update evts
      | Error e -> Error e


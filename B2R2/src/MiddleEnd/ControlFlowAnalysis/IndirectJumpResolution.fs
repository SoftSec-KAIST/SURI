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

namespace B2R2.MiddleEnd.ControlFlowAnalysis

open B2R2
open B2R2.BinIR
open B2R2.BinIR.SSA
open B2R2.FrontEnd.BinInterface
open B2R2.MiddleEnd.BinGraph
open B2R2.MiddleEnd.ControlFlowGraph
open B2R2.MiddleEnd.DataFlow
open B2R2.MiddleEnd.ControlFlowAnalysis.LowUIRHelper

type BranchPattern =
  /// This encodes an indirect jump with a jump table where baseAddr is the jump
  /// target's base address, tblAddr is the start address of a jump table, and
  /// rt is the size of each entry in the jump table.
  | JmpTablePattern of baseAddr: Addr * tblAddr: Addr * rt: RegType
  /// Jump to a single constant target.
  | ConstJmpPattern of addr: Addr
  /// Conditional jump for constant targets. This pattern appears in EVM.
  | ConstCJmpPattern of tAddr: Addr * fAddr: Addr
  /// Call to a single constant target.
  | ConstCallPattern of calleeAddr: Addr * ftAddr: Addr
  /// Return back to caller pattern found in EVM.
  | ReturnPattern of sp: Addr
  /// Unknown pattern.
  | UnknownPattern

/// The resulting status of RecoverTarget.
type RecoveryStatus =
  /// Recovery process should stop.
  | RecoverDone of Result<CFGEvents, CFGError>
  /// Recovery process should continue.
  | RecoverContinue

/// Indirect jump resolution.
[<AbstractClass>]
type IndirectJumpResolution () =
  inherit PerFunctionAnalysis ()

  override __.Name = "IndirectJumpResolution"

  /// Analyze the given indirect jump type (JmpType) and return a BranchPattern.
  abstract member Classify:
    BinHandle
    -> SSAVertex
    -> CPState<SCPValue>
    -> JmpType
    -> BranchPattern

  /// Analyze the given indirect jump type (JmpType) and return a BranchPattern.
  abstract member Classify2:
    BinHandle
    -> SSAVertex
    -> CPState<SCPValue>
    -> JmpType
    -> List<BranchPattern * Variable list * List<Addr>>

  /// Check the given BranchPattern and mark the indirect jump as an analysis
  /// target.
  abstract member MarkIndJmpAsTarget:
    CodeManager
    -> DataManager
    -> RegularFunction
    -> Addr
    -> ProgramPoint
    -> CFGEvents
    -> BranchPattern
    -> Result<bool * CFGEvents, JumpTable * Addr>

  /// Recover the current target.
  abstract member RecoverTable:
    BinHandle
    -> CodeManager
    -> DataManager
    -> RegularFunction
    -> Addr
    -> Addr
    -> CFGEvents
    -> CFGEvents

  /// Recover the current target.
  abstract member RecoverTarget:
    BinHandle
    -> CodeManager
    -> DataManager
    -> RegularFunction
    -> CFGEvents
    -> RecoveryStatus

  /// Process recovery error(s).
  abstract member OnError:
    CodeManager
    -> DataManager
    -> RegularFunction
    -> CFGEvents
    -> (JumpTable * Addr)
    -> Result<CFGEvents, CFGError>

  member private __.FindIndJmpKind ssaCFG srcBlkAddr fstV (vs: SSAVertex list) =
    match vs with
    | v :: rest ->
      match v.VData.GetLastStmt () with
      | Jmp (InterJmp _ as jk) as e -> e
      | Jmp (InterCJmp _ as jk) as e -> e
      | _ ->
        let vs =
          DiGraph.GetSuccs (ssaCFG, v)
          |> List.fold (fun acc succ ->
            if succ <> fstV then succ :: acc else acc) rest
        __.FindIndJmpKind ssaCFG srcBlkAddr fstV vs
    | [] -> Utils.impossible ()

  /// Symbolically expand the indirect jump expression with the constant
  /// information obtained from the constatnt propagation step, and see if the
  /// jump target is in the form of loading a jump table.
  member private __.AnalyzeBranchPattern hdl ssaCFG cpState blkAddr blkEnd =
    let srcV = (* may not contain Jmp: get the right one @ FindIndJmpKind. *)
      DiGraph.FindVertexBy (ssaCFG, fun (v: SSAVertex) ->
        v.VData.PPoint.Address = blkAddr)
    let stmt =  if srcV.VData.Range.Max = blkEnd then srcV.VData.GetLastStmt ()
                else
                  let srcBlkAddr = (srcV: SSAVertex).VData.PPoint.Address
                  __.FindIndJmpKind ssaCFG srcBlkAddr srcV [ srcV ]
    match stmt with
    | Jmp (InterJmp _ as jk)
    | Jmp (InterCJmp _ as jk) ->

      __.Classify2 hdl srcV cpState jk
    | _ -> Utils.impossible ()

  member private __.Analyze2 hdl (codeMgr: CodeManager) dataMgr fn addrs evts =
    let rootBBL, bblDict, noV = ConstructBBLInfo fn

    match addrs with
    | iAddr :: rest ->
      let funCodeMgr = codeMgr.GetFunCodeMgr (fn: RegularFunction).EntryPoint
      let bblInfo = funCodeMgr.GetBBL iAddr
      let blkAddr = Set.minElement bblInfo.InstrAddrs
      let brInfo = ResolveIndBr codeMgr fn blkAddr iAddr rootBBL bblDict noV
      if brInfo.IsEmpty then
        fn.MarkIndJumpAsUnknown iAddr
        __.Analyze2 hdl codeMgr dataMgr fn rest evts
      else
        let tbls
            = brInfo |> List.map(fun info -> info.TblAddr) |> List.distinct
        if tbls.IsEmpty then
          fn.MarkIndJumpAsUnknown iAddr
        let evts
            = tbls
              |> List.fold(fun evts tblAddr
                               -> __.RecoverTable hdl codeMgr dataMgr fn iAddr
                                    tblAddr evts) evts
        __.Analyze2 hdl codeMgr dataMgr fn rest evts
    | [] -> evts


  member private __.Analyze
    hdl (codeMgr: CodeManager) dataMgr fn cpSt ssaCFG addrs needRecovery evts =
    match addrs with
    | iAddr :: rest ->
#if CFGDEBUG
      dbglog "IndJmpRecovery" "@%x Detected indjmp @ %x"
        (fn: RegularFunction).EntryPoint iAddr
#endif

      let funCodeMgr = codeMgr.GetFunCodeMgr (fn: RegularFunction).EntryPoint
      let bblInfo = funCodeMgr.GetBBL iAddr
      let blkAddr = Set.minElement bblInfo.InstrAddrs
      let blkEnd = bblInfo.BlkRange.Max
      let src = Set.maxElement bblInfo.IRLeaders
      let patterns = __.AnalyzeBranchPattern hdl ssaCFG cpSt blkAddr blkEnd
                      |> Seq.distinct |> List.ofSeq

      let ret = patterns |> List.map(fun (pattern, def, defChain) ->
                __.MarkIndJmpAsTarget codeMgr dataMgr fn iAddr src evts pattern
                ) |> List.filter(fun x -> match x with
                                            | Ok(true, _) -> true
                                            | _ -> false )
      if ret.Length > 0 then
          __.Analyze hdl codeMgr dataMgr fn cpSt ssaCFG rest true evts
      else if needRecovery then
          __.Analyze hdl codeMgr dataMgr fn cpSt ssaCFG rest true evts
      else
          fn.MarkIndJumpAsUnknown iAddr
          __.Analyze hdl codeMgr dataMgr fn cpSt ssaCFG rest false evts
    | [] -> Ok (needRecovery, evts)

  member private __.AnalyzeIndJmps hdl codeMgr dataMgr fn evts =
    let addrs = (fn: RegularFunction).YetAnalyzedIndirectJumpAddrs
    if List.isEmpty addrs then Ok (true, evts)
    else
      let struct (cpState, ssaCFG) = PerFunctionAnalysis.runCP hdl fn None
      __.Analyze hdl codeMgr dataMgr fn cpState ssaCFG addrs false evts

  member private __.Resolve hdl codeMgr dataMgr fn evts =

    let addrs = (fn: RegularFunction).YetAnalyzedIndirectJumpAddrs

    let evts = __.Analyze2 hdl codeMgr dataMgr fn addrs evts
    Ok evts
    (*
    match __.AnalyzeIndJmps hdl codeMgr dataMgr fn evts with
    | Ok (false, evts) when fn.GetUnmarkedJumpTables |> List.isEmpty ->
      (* We are in a nested update call, and found nothing to resolve. So, just
         return to the caller, and keep resolving the rest entries. *)
      Ok evts
    | Ok (_, evts) ->
      match __.RecoverTarget hdl codeMgr dataMgr fn evts with
      | RecoverDone res when fn.GetUnmarkedJumpTables |> List.isEmpty -> res
      | RecoverDone _ -> __.Resolve hdl codeMgr dataMgr fn evts
      | RecoverContinue -> __.Resolve hdl codeMgr dataMgr fn evts
    | Error err ->
      __.OnError codeMgr dataMgr fn evts err
    *)

  override __.Run hdl codeMgr dataMgr fn evts =
    let res = __.Resolve hdl codeMgr dataMgr fn evts

    match res with
    | Ok evts ->
      Ok (evts |> CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint)
    | Error err ->
      Error err

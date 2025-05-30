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

open B2R2
open B2R2.FrontEnd
open SuperCFG.SSA
open SuperCFG.ControlFlowGraph
open SuperCFG.DataFlow
open SuperCFG.ControlFlowAnalysis

[<AutoOpen>]
module private IndirectCallResolution =

  let [<Literal>] Myname = "IndCallRecovery"

  /// Try to look up the CPState to find a potential call target
  let resolveCallTarget st = function
    | Var v ->
      match v.Kind with
      | TempVar _ -> CPState.findReg st v
      | _ -> NotAConst //Utils.futureFeature ()
    | _ -> NotAConst //Utils.futureFeature ()

  let updateCallInfo (func: RegularFunction) callSiteAddr target =
#if CFGDEBUG
    dbglog Myname "@%x => %x" callSiteAddr target
#endif
    let callee = IndirectCallees <| Set.singleton target
    func.UpdateCallEdgeInfo (callSiteAddr, callee)

  let handleDiscoveredTarget func callSiteAddr target evts =
    updateCallInfo func callSiteAddr target
    evts

  let handleUndiscoveredTarget hdl codeMgr func callSiteAddr target evts =
    updateCallInfo func callSiteAddr target
    (codeMgr: CodeManager).FunctionMaintainer.GetOrAddFunction target
    |> ignore
    CFGEvents.addFuncEvt target ArchOperationMode.NoMode evts

  let handleUnresolvedCase
        (func: RegularFunction) (codeMgr: CodeManager) callSiteAddr evts =
    let funCodeMgr = codeMgr.GetFunCodeMgr func.EntryPoint
    let bbl = funCodeMgr.GetBBL callSiteAddr
    let caller = Set.maxElement bbl.IRLeaders
    let callee = IndirectCallees Set.empty
    let lastInsAddr = Set.maxElement bbl.InstrAddrs
    let lastIns = funCodeMgr.GetInstruction lastInsAddr
    let ftAddr = uint64 lastIns.Instruction.Length + lastInsAddr
    (func: RegularFunction).UpdateCallEdgeInfo (callSiteAddr, callee)
    CFGEvents.addPerFuncAnalysisEvt func.EntryPoint evts
    |> CFGEvents.addRetEvt func 0UL ftAddr callSiteAddr
    |> CFGEvents.addEdgeEvt func caller ftAddr CallFallThroughEdge

  let resolve (hdl: BinHandle) cpState ssaCFG acc callSiteAddr =
    let v = SSACFG.findVertexByAddr ssaCFG callSiteAddr
    match v.VData.GetLastStmt () with
    | Jmp (InterJmp e) -> (* The only possible form for an indrect call *)
#if CFGDEBUG
      dbglog Myname "@%x call exp %s" callSiteAddr (Pp.expToString e)
#endif
      match resolveCallTarget cpState e with
      | Const bv ->
        let target = BitVector.ToUInt64 bv
        if target <> 0UL && hdl.File.IsExecutableAddr target then
          Map.add callSiteAddr (Some target) acc
        else Map.add callSiteAddr None acc
      | NotAConst -> Map.add callSiteAddr None acc
      | _ -> Utils.impossible ()
    // handle exception case
    | _ -> Map.add callSiteAddr None acc // Utils.impossible ()

  let update hdl (codeMgr: CodeManager) func evts result =
    result
    |> Map.fold (fun evts callSiteAddr target ->
      match target with
      | Some target ->
        if codeMgr.FunctionMaintainer.Contains (addr=target) then
          handleDiscoveredTarget func callSiteAddr target evts
        else handleUndiscoveredTarget hdl codeMgr func callSiteAddr target evts
      | None -> handleUnresolvedCase func codeMgr callSiteAddr evts) evts

  let reader (hdl: BinHandle) (codeMgr: CodeManager) addr rt =
    if hdl.File.IsValidAddr addr then
      match hdl.File.GetSections addr |> Seq.tryHead with
      | Some sec ->
        if sec.Name = ".rodata" || sec.Name = ".data" then
          let v = hdl.ReadUInt (addr, RegType.toByteWidth rt)
          Some <| BitVector.OfUInt64 v rt
        elif sec.Name = ".got" then
          if codeMgr.FunctionMaintainer.Contains (addr=addr) then
            Some <| BitVector.OfUInt64 addr rt
          else None
        else None
      | None -> None
    else None

/// IndirectCallResolution tries to find indirect call target by constant
/// propagation. We should fix this if we meet a table-like indirect call
/// targets.
type IndirectCallResolution () =
  inherit PerFunctionAnalysis ()

  override __.Name = Myname

  override __.Run hdl isa codeMgr _dataMgr func evts =
    let reader = reader hdl codeMgr |> Some
    let struct (cpState, ssaCFG) = PerFunctionAnalysis.runCP hdl isa func reader
    func.UnresolvedIndirectCallEdges
    |> Seq.fold (resolve hdl cpState ssaCFG) Map.empty
    |> update hdl codeMgr func evts
    |> Ok

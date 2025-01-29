namespace B2R2.MiddleEnd.ControlFlowAnalysis

open B2R2
open B2R2.BinIR
open B2R2.BinIR.SSA
open B2R2.MiddleEnd.ControlFlowGraph
open B2R2.MiddleEnd.ControlFlowAnalysis.IRHelper
open B2R2.FrontEnd.BinFile
open B2R2.MiddleEnd.ControlFlowAnalysis.LowUIRHelper

[<AutoOpen>]
module TblAnalyzer =

type TblAnalyzer () =
  inherit PerFunctionAnalysis ()
  override __.Name = Myname

  override __.Run _hdl _codeMgr _dataMgr func evts =
    // Add per-function analysis event to resolve discovered tables
    if evts.FunctionAnalysisAddrs |> List.contains(func.EntryPoint) then
      (Ok evts)
    else
      (Ok (CFGEvents.addPerFuncAnalysisEvt func.EntryPoint evts))

  member private __.Analyze2 hdl (codeMgr: CodeManager) dataMgr fn addrs res =
    let rootBBL, bblDict, noV = ConstructBBLInfo fn

    match addrs with
    | iAddr :: rest ->
      let funCodeMgr = codeMgr.GetFunCodeMgr (fn: RegularFunction).EntryPoint
      let bblInfo = funCodeMgr.GetBBL iAddr
      let blkAddr = Set.minElement bblInfo.InstrAddrs
      let brInfo = ResolveIndBr codeMgr fn blkAddr iAddr rootBBL bblDict noV
      funCodeMgr.UpdateBrInfo iAddr brInfo
      let tbls
        = brInfo
          |> List.map(fun info -> info.TblAddr) |> List.distinct
          |> List.filter(fun addr ->
                        if fn.IsRegisteredCandidate iAddr addr then false
                        else
                          (fn: RegularFunction).RegisterNewIndJump iAddr
                          true
                        )

      if tbls.IsEmpty then
        __.Analyze2 hdl codeMgr dataMgr fn rest res
      else
        __.Analyze2 hdl codeMgr dataMgr fn rest true
    | [] -> res

  member __.HasTblCandidates
      hdl (codeMgr: CodeManager) (dataMgr: DataManager) (fn: RegularFunction) =
    let indJmps = fn.IndirectJumps |> Seq.map(fun (KeyValue(addr,_))-> addr )
    __.Analyze2 hdl codeMgr dataMgr fn (indJmps|> List.ofSeq) false



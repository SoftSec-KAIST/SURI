module SuperCFG.ControlFlowAnalysis.FortranRegularJmpResolution

open SuperCFG.ControlFlowGraph
open SuperCFG.ControlFlowAnalysis.LowUIRHelper
/// Indirect jump resolution.
type FortranRegularJmpResolution () =
  inherit PerFunctionAnalysis ()
  override __.Name = "FortranIndirectJumpResolution"


  member private __.Analyze hdl (codeMgr: CodeManager) dataMgr fn addrs res evts =
    let rootBBL, bblDict, noV = ConstructBBLInfo fn

    match addrs with
    | iAddr :: rest ->
      let funCodeMgr = codeMgr.GetFunCodeMgr (fn: RegularFunction).EntryPoint
      let bblInfo = funCodeMgr.GetBBL iAddr
      let blkAddr = Set.minElement bblInfo.InstrAddrs
      let brInfo = ResolveFortranIndBr
                     codeMgr fn blkAddr iAddr rootBBL bblDict noV
      let _, src = (fn: RegularFunction).IndJmpBBLs.TryGetValue iAddr
      if brInfo |> List.length > 0 then
        let evts =
          brInfo
          |> List.fold(fun evts target -> CFGEvents.addEdgeEvt fn src target
                                            IndirectJmpEdge evts) evts
        __.Analyze hdl codeMgr dataMgr fn addrs true evts
      else res, evts
    | [] -> res, evts


  member __.Resolve hdl codeMgr dataMgr fn evts =

    let addrs = (fn: RegularFunction).IndirectJumps
                  |> Seq.choose(
                    fun (KeyValue(addr, kinds)) ->
                       if kinds |> Set.contains(UnknownIndJmp) then Some addr
                       else None)
                  |> Seq.toList
    __.Analyze hdl codeMgr dataMgr fn addrs false evts



  override __.Run hdl isa codeMgr dataMgr fn evts =
    let res, evts = __.Resolve hdl codeMgr dataMgr fn evts

    match res with
    | true ->
      Ok (evts |> CFGEvents.addPerFuncAnalysisEvt fn.EntryPoint)
    | false ->
      Ok evts

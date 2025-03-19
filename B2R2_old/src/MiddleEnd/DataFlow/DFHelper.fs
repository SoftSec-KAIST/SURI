module B2R2.MiddleEnd.DataFlow.DFHelper

open B2R2
open B2R2.FrontEnd.BinLifter
open B2R2.MiddleEnd.DataFlow

let getDefs cfg root count =
    ///let cfg, root = BinEssence.getFunctionCFG ess 0UL |> Result.get
    let chain = DataFlowChain.init cfg root false
    let vp =
      { ProgramPoint = count //ProgramPoint (0x0UL, 1)
        VarExpr = Regular (Intel.Register.toRegID Intel.Register.RDX) }
    let res = chain.UseDefChain |> Map.find vp

    let vp2 =
      { ProgramPoint = ProgramPoint (0x685UL, 1)
        VarExpr = Regular (Intel.Register.toRegID Intel.Register.RDX) }

    ///let res2 = chain.UseDefChain |> Map.find res.[0] |> Set.toArray
    let res2 = chain.UseDefChain |> Map.find vp2 |> Set.toArray

    ///let res4 = chain.UseDefChain |> Map.find res2.[0] |> Set.toArray
    res2





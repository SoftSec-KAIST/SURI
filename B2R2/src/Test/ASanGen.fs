module SupersetCFG.ASanGen

open System.Collections
open B2R2
open B2R2.FrontEnd.BinInterface
open B2R2.MiddleEnd.BinEssence
open B2R2.FrontEnd.BinLifter.Intel
open B2R2.MiddleEnd.BinGraph
open B2R2.MiddleEnd.ControlFlowAnalysis
open B2R2.MiddleEnd.ControlFlowGraph
open B2R2.MiddleEnd.ControlFlowAnalysis.LowUIRHelper
open SupersetCFG.MetaGen

type MemInfo = {
  Addr: string
  MemAccType: string
  MemAccSize: uint list
}
type ASanInfo = {
  Addr: string
  InstList: MemInfo list
}

let isMemAccess = function
  | OprMem (_, _, _, size) -> uint size
  | _ -> uint 0

let getMemAccess = function
  | NoOperand -> []
  | OneOperand opr -> [(isMemAccess opr)]
  | TwoOperands (opr1, opr2) ->
    [(isMemAccess opr1); (isMemAccess opr2)]
  | ThreeOperands (opr1, opr2, opr3) ->
    [(isMemAccess opr1); (isMemAccess opr2); (isMemAccess opr3)]
  | FourOperands (opr1, opr2, opr3, opr4) ->
    [(isMemAccess opr1); (isMemAccess opr2);
     (isMemAccess opr3); (isMemAccess opr4)]

let getMemAccessType instInfo memAcc =
  let operands = memAcc |> List.filter(fun x -> x > uint 0)
  if operands |> List.length = 1 then
    let result = instInfo.Stmts
                 |> Seq.fold(fun acc stmt -> GetAccType stmt acc) List.Empty
                 |> List.distinct |> List.ofSeq

    result
  else List.Empty

let rec memAccCheckLoop (hdl: BinHandle) funCodeMgr (addr:Addr) (eAddr:Addr) acc =
  if addr = eAddr then acc
  else
      let ins = BinHandle.ParseInstr (hdl, addr)
      let memAcc = getMemAccess (ins :?> IntelInstruction).Operands

      let insInfo = (funCodeMgr: FunCodeManager).InsMap[addr]
      let memAccType = getMemAccessType insInfo memAcc
      let aType = if memAccType.Length > 1 then
                    "S"
                  elif memAccType.Length = 1 then memAccType[0]
                  else ""
      let nextAddr = addr + uint64 ins.Length
      if aType <> "" then
        let addrStr = sprintf "0x%x" addr
        let code = {Addr=addrStr; MemAccType=aType; MemAccSize=memAcc}
        memAccCheckLoop hdl funCodeMgr nextAddr eAddr (code::acc)
      else
        memAccCheckLoop hdl funCodeMgr nextAddr eAddr (acc)


let memAccCheck hdl funCodeMgr (vertex: Vertex<DisasmBasicBlock>) =
  let sAddr = vertex.VData.PPoint.Address
  if vertex.VData.IsFakeBlock() then
    None
  else if vertex.VData.PPoint.Position >= 0 then
    let eAddr = vertex.VData.Range.Count + sAddr
    let code = memAccCheckLoop hdl funCodeMgr sAddr eAddr [] |> List.rev
    Some code
  else
    None

let ASanMetaGen (ess: BinEssence) hdl =
  let fnList =
    ess.CodeManager.FunctionMaintainer.RegularFunctions
    |> List.ofArray
    |> List.filter (fun fn ->
        if ess.CodeManager.HasFunCodeMgr fn.EntryPoint then true
        else
           printf "Unresolved Entry point: %x" fn.EntryPoint
           false )
    |> List.map(fun fn ->
        let funCodeMgr = ess.CodeManager.GetFunCodeMgr fn.EntryPoint
        let cfg, root = BinEssence.getFunctionCFG ess fn.EntryPoint
                        |> Result.get
        let disasmcfg, root2 = DisasmLens.filter2 funCodeMgr cfg root
        let allVertices = CollectVertices disasmcfg root2
        let instList
            = allVertices
              |> List.fold(fun acc (v, edges) ->
                            match memAccCheck hdl funCodeMgr v with
                            | Some code -> code@acc
                            | _ -> acc
                            ) List.Empty
        {Addr = $"0x%x{fn.EntryPoint}"; InstList = instList} )

  ()
  fnList


module SupersetCFG.MetaGen

open System.Collections
open System.Collections.Generic
open B2R2
open B2R2.FrontEnd.BinInterface
open B2R2.MiddleEnd.BinEssence
open B2R2.FrontEnd.BinLifter.Intel
open B2R2.MiddleEnd.ControlFlowAnalysis
open B2R2.MiddleEnd.ControlFlowGraph
open B2R2.MiddleEnd.BinGraph

type JmpTblInfo = {
  JmpSite: string
  BaseAddr: string
  Size: uint64
  Entries: string list
}
type InstInfo = {
  Addr: string
  Length: uint
  ByteString: string
  Disassem: string
  RIPAddressing: bool list
  IsBranch: bool
}
type Edge = {
  From: string
  To: string
  EdgeType: string
}
type BlockInfo = {
  Addr: string
  Size: uint64
  Code: InstInfo list
  Edges: Edge list
}
type FDERange = {
  Start: string
  End: string
}
type FnInfo = {
  Addr: string
  InstAddrs: string list
  JmpTables: JmpTblInfo list
  JmpInfo: IDictionary<string, BranchInfo list>
  FDERanges: FDERange list
  BBLs: IDictionary<string, BlockInfo>
  AbsorbingFun: string list
  FalseBBLs: string list
}
let isRIPAccess = function
  | OprMem (Some reg, None, _, _)
  | OprMem (None, Some (reg, _), _, _) ->
    reg.ToString () = "RIP"
  | OprMem (Some reg1, Some (reg2, _), _, _) ->
    reg1.ToString () = "RIP" || reg2.ToString () = "RIP"
  | _ -> false

let getRIPAccess = function
  | NoOperand -> []
  | OneOperand opr -> [(isRIPAccess opr)]
  | TwoOperands (opr1, opr2) ->
    [(isRIPAccess opr1); (isRIPAccess opr2)]
  | ThreeOperands (opr1, opr2, opr3) ->
    [(isRIPAccess opr1); (isRIPAccess opr2); (isRIPAccess opr3)]
  | FourOperands (opr1, opr2, opr3, opr4) ->
    [(isRIPAccess opr1); (isRIPAccess opr2);
     (isRIPAccess opr3); (isRIPAccess opr4)]

let rec disasmLoop (hdl: BinHandle) (addr:Addr) (eAddr:Addr) acc =
  if addr = eAddr then acc
  else
      let ins = BinHandle.ParseInstr (hdl, addr)
      let addr = ins.Address
      let disasm = ins.Disasm ()
      let length = ins.Length
      let byteString = BinHandle.ReadBytes (hdl, addr, int length)
                        |> Array.map (fun b -> b.ToString ("X2"))
                        |> Array.reduce (+)
      let ripAccess = getRIPAccess (ins :?> IntelInstruction).Operands
      let addrStr = $"0x%x{addr}"
      let code = {Addr=addrStr; Length=length; ByteString=byteString
                  Disassem=disasm; RIPAddressing = ripAccess
                  IsBranch=ins.IsBranch()}
      disasmLoop hdl (addr + uint64 ins.Length) eAddr (code::acc)

let disassem hdl (vertex: Vertex<DisasmBasicBlock>) =
  let sAddr = vertex.VData.PPoint.Address
  if vertex.VData.IsFakeBlock() then
    None
  else if vertex.VData.PPoint.Position >= 0 then
    let eAddr = vertex.VData.Range.Count + sAddr
    let code = disasmLoop hdl sAddr eAddr [] |> List.rev
    Some code
  else
    None

let CollectVertices cfg (v: DisasmVertex) =
  let history = new Dictionary<VertexID, bool>()
  let remains = new List<DisasmVertex>()
  let ret = new List<_>()
  let mutable idx = 0
  remains.Add(v)
  let Edge2Str edge =
    match edge with
      | InterJmpEdge -> "InterJmpEdge"
      | InterCJmpTrueEdge -> "InterCJmpTrueEdge"
      | InterCJmpFalseEdge -> "InterCJmpFalseEdge"
      | IntraJmpEdge -> "IntraJmpEdge"
      | IntraCJmpTrueEdge -> "IntraCJmpTrueEdge"
      | IntraCJmpFalseEdge -> "IntraCJmpFalseEdge"
      | CallEdge -> "CallEdge"
      | RecursiveCallEdge -> "RecursiveCallEdge"
      | IndirectJmpEdge -> "IndirectJmpEdge"
      | IndirectCallEdge -> "IndirectCallEdge"
      | ExternalJmpEdge -> "ExternalJmpEdge"
      | ExternalCallEdge -> "ExternalCallEdge"
      | RetEdge -> "RetEdge"
      | FallThroughEdge -> "FallThroughEdge"
      | CallFallThroughEdge -> "CallFallThroughEdge"
      | NoReturnFallThroughEdge -> "NoReturnFallThroughEdge"
      | ExceptionFallThroughEdge -> "ExceptionFallThroughEdge"
      | ImplicitCallEdge -> "ImplicitCallEdge"
      | UnknownEdge -> "UnknownEdge"

  while (remains.Count > idx ) do
    let v = remains[idx]
    idx <- idx+1
    if not <| history.ContainsKey(v.GetID()) then
      let succs = DiGraph.GetSuccs (cfg, v)
      let edges
        = succs
          |> List.map(fun succ ->
                      let edgeType = DiGraph.FindEdgeData (cfg, v, succ)
                      {From= $"0x%x{v.VData.PPoint.Address}";
                       To= $"0x%x{succ.VData.PPoint.Address}";
                       //EdgeType= $"%A{edgeType}"}
                       EdgeType=Edge2Str edgeType }
                      )
      ret.Add((v, edges))

      succs |> List.iter (fun item -> remains.Add(item))
      history.Add(v.GetID(), true)

  List.ofSeq ret


let rec readTables hdl (bAddr: Addr) (idx: uint64) acc =
  let entryAddr = bAddr + uint64 4 * (idx - uint64 1)
  let data = BinHandle.ReadInt (hdl, entryAddr, 4)
  let entry = bAddr + uint64 data
  if idx = uint64 1 then entry::acc
  else readTables hdl bAddr (idx-(uint64 1)) (entry::acc)

let MetaGen (ess: BinEssence) hdl =
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
        let bblList
            = allVertices
              |> List.fold(fun acc (v, edges) ->
                            match disassem hdl v with
                            | Some code ->  let addr = v.VData.PPoint.Address
                                            { Addr = $"0x%x{addr}" ;
                                              Size = v.VData.Range.Count;
                                              Code = code; Edges = edges}::acc
                            | _ -> acc
                            ) List.Empty
        let jmpInfo = funCodeMgr.BrInfoDict
                      |> Seq.map(fun (KeyValue(k, v)) -> $"0x%x{k}" , v)
                      |> dict

        let jmpList
            = fn.IndirectJumps
              |> Seq.fold(fun acc (KeyValue(k,v)) ->
                          let jmpAddr = $"0x%x{k}"
                          v |> Seq.fold(fun acc j ->
                              match j with
                              | JmpTbl tAddr ->
                                let tblAddr = $"0x%x{tAddr}"
                                if fn.JmpTblDict.ContainsKey tAddr then
                                  let tblSize = fn.JmpTblDict[tAddr]
                                  let entries =
                                    readTables hdl tAddr tblSize List.Empty
                                    |> List.map(fun x -> $"0x%x{x}")
                                  {JmpSite=jmpAddr; BaseAddr=tblAddr
                                   Size=tblSize; Entries=entries}::acc
                                // part block may contain empty jump table
                                // since we decided the first was entry invalid
                                else {JmpSite=jmpAddr; BaseAddr=tblAddr
                                      Size=uint64 0; Entries=List.Empty}::acc
                              | _ -> acc ) acc
                          ) List.Empty
        let addrList
          = bblList
            |> List.fold(fun ess bbl ->
                (bbl.Code
                 |> List.map(fun inst -> inst.Addr))@ess) []
        //let (fdeStart, fdeEnd) = fn.FDERanges[0]
        let fdeRanges
            = fn.FDERanges
              |> Seq.distinct
              |> Seq.map(fun (a, b) ->
                {Start = ($"0x%x{a}"); End = ($"0x%x{b}")})
              |> List.ofSeq
        let bblDict = bblList
                      |> List.map(fun bbl -> bbl.Addr, bbl )
                      |> Seq.ofList |> dict

        let absorbers = fn.AbsorbingFuns
                        |> Seq.map(fun x -> $"0x%x{x}")
                        |> Seq.distinct |> List.ofSeq

        let falseBBLs = funCodeMgr.FalseBlocks
                        |> Seq.map(fun x -> $"0x%x{x}")
                        |> List.ofSeq

        {Addr = $"0x%x{fn.EntryPoint}";
         InstAddrs = addrList; BBLs = bblDict;
         JmpTables = jmpList; JmpInfo = jmpInfo;
         FDERanges = fdeRanges;
         AbsorbingFun = absorbers
         FalseBBLs = falseBBLs} )

  fnList

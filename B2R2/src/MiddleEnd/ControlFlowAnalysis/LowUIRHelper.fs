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
module B2R2.MiddleEnd.ControlFlowAnalysis.LowUIRHelper

open System.Collections
open System.Collections.Generic
open System.Security.Principal
open B2R2
open B2R2.BinIR
open B2R2.BinIR.LowUIR
open B2R2.FrontEnd.BinLifter.Intel
open B2R2.MiddleEnd.BinGraph
open B2R2.MiddleEnd.ControlFlowGraph



type RegInfo = {
  Addr: Addr
  RegStr: string
  RegID: RegisterID
}

type TwoRegInfo = {
  Target: RegInfo
  Other: RegInfo
  Expr: E
  Vertex: PerVertex<IRBasicBlock>
  Remains: (Stmt[]*Addr) list
}



(*
let findRegDef hdl fn Reg useSite =

  let rec collectPreds cfg depth acc ids v =
    if depth > 0 then
      DiGraph.GetPreds (cfg, v)
      |> List.fold (fun (acc, ids) pred ->
        let edge = DiGraph.FindEdgeData (cfg, pred, v)
        match edge with
        | FallThroughEdge
        | InterJmpEdge ->
          collectPreds cfg (depth-1) acc (v.VData.ID::ids) v
        | _ ->  if List.contains v acc then (acc, ids)
                else ((v::acc), ids)
      ) (acc, ids)
    elif List.contains v acc then (acc, ids)
    else (v::acc, ids)
  //let (bbls, ids) = collectPreds fn.IRCFG 5 List.Empty [targetBBL.VData.ID]
  //                          targetBBL
  true
*)

let GetIRInfo (v: PerVertex<IRBasicBlock>) =
  let isNop (inst: IntelInstruction) =
    if inst.Opcode = Opcode.NOP then true
    elif inst.Opcode = Opcode.XCHG then
      match inst.Operands with
      | Operands.TwoOperands (OprReg reg1, OprReg reg2) when reg1=reg2 -> true
      | _ -> false
    else false

  let addrList = v.VData.Instructions
                 |> Array.map(fun inst ->
                      ((isNop (inst :?> IntelInstruction)), inst.Address))
                 |> List.ofArray
  let irList = v.VData.IRStatements
                 |> List.ofArray

  List.zip irList addrList
  |> List.filter(fun (_, (isNop, _)) -> not isNop )
  |> List.map(fun (stmts, (_, addr)) -> (stmts, addr))


let rec GetJmpSiteIR cfg vs jmpSite visited =
  match vs with
  | v :: rest ->
    match GetIRInfo v |> List.rev with
    | head::remain ->
      let (ir, addr) = head
      if addr = jmpSite then
          let lastStmt = ir |> List.ofArray |> List.last
          match lastStmt.S with
          | InterJmp ({E=Var(64<rt>, regID, regStr, _)}, _) ->
            addr, regStr, Some regID, remain, v
          | _ -> uint64 0, "", None, [], v
      else
        let vs = DiGraph.GetSuccs (cfg, v)
                 |> List.fold (fun acc succ ->
                    let succ = succ :?>PerVertex<IRBasicBlock>
                    let edge = DiGraph.FindEdgeData (cfg, v, succ)
                    if succ <> v && edge <> IndirectJmpEdge &&
                       (List.contains succ visited |> not) then
                      acc@[succ]
                    else acc) rest
        GetJmpSiteIR cfg vs jmpSite (visited@vs)
    | [] -> Utils.impossible()
  | [] -> Utils.impossible()

let GetFallThroughPreds cfg v =
  DiGraph.GetPreds (cfg, v)
  |> List.fold (fun acc pred ->
    let edge = DiGraph.FindEdgeData (cfg, pred, v)
    match edge with
    | FallThroughEdge | InterJmpEdge -> pred::acc
    | _ ->  acc
  ) List.Empty

let rec TryGetBinOpIR cfg (v:PerVertex<IRBasicBlock>) irList targetReg acc =
  let rec findAddIR irList =
    match irList with
    | (ir, addr)::remain ->
      let res = ir |> List.ofArray
                |> List.rev
                |> List.fold( fun (tempID, regInfo, stage) stmt ->
                  match stmt.S with
                  | Put ({E=Var (_, _, regStr, _)}, {E=TempVar (_, id)})
                      when stage = 1 && regStr = targetReg
                       -> ([id], regInfo, 2)
                  | Put ({E=Var (_, _, regStr, _)}, _)
                      when stage = 1 && regStr = targetReg -> ([], regInfo, 0)
                  | Put ({E=TempVar (_, id0)},
                         {E=BinOp(BinOpType.ADD, 64<rt>, {E=TempVar(_, id1)},
                                  {E = TempVar(_, id2)}, _)})
                          when stage = 2 && tempID[0] = id0
                           -> ((id1::[id2]), regInfo, 3)
                  | Put ({E=TempVar (_, id0)}, {E=Var (_, regID, regStr, v4)})
                      when stage = 3 && (id0 = tempID[0] || id0 = tempID[1] )
                        -> (tempID,
                            ({Addr=addr; RegStr=regStr; RegID=regID})::regInfo,
                              3)
                  | _ -> (tempID, regInfo, stage)) (List.Empty, List.Empty, 1)

      let _, regInfo, stage = res
      if stage = 1 then findAddIR remain
      elif stage = 3 && (regInfo |> List.length = 2) then true, regInfo, remain
      else true, List.Empty, List.Empty
    | [] -> false, List.Empty, List.Empty

  let reset, regInfo, remains = findAddIR irList
  if reset then
    if regInfo.IsEmpty then acc
    else (regInfo, v, remains)::acc
  else
    let preds = GetFallThroughPreds cfg v
    preds |> List.fold(fun acc pred ->
      let pred = (pred :?> PerVertex<IRBasicBlock>)
      let irs = GetIRInfo pred |> List.rev
      TryGetBinOpIR cfg pred irs targetReg acc) acc

let rec findRegDef target other irList =
  match irList with
  | (ir, addr)::remain ->
    let res = ir |> List.ofArray
              |> List.rev
              |> List.fold(fun acc stmt ->
                  match stmt.S with
                  | Put ({E=Var (_, _, regStr, _)}, {E=exp} )
                    when regStr = target.RegStr ->
                    match exp with
                    | Cast (CastKind.SignExt, 64<rt>,
                            {E=Extract({E=Var(_,_,regStr2,_)},32<rt>,0,_)}, _)
                      ->  // handle cdqe instruction
                          if regStr = regStr2 then acc
                          //mov     eax, dword ptr [rdx, rax]
                          //movsxd  rdx, eax
                          else ({target with Addr=addr}, other, Some exp)::acc
                    | _ -> ({target with Addr=addr}, other, Some exp)::acc
                  | Put ({E=Var (_, _, regStr, _)}, {E=_} )
                    when regStr = other.RegStr ->
                    if other.Addr = uint64 0 then
                      (target, {other with Addr=addr}, None)::acc
                    else acc
                  | _ -> acc
                  ) List.Empty
    if res |> List.isEmpty then findRegDef target other remain
    elif res.Length = 1 then Some res[0], remain
    elif res.Length = 2 then
      match res[0], res[1] with
      | (t, _, Some e), (_, o, None)
      | (_, o, None), (t, _, Some e) -> Some (t, o, Some e), remain
      | (t1, o1, Some e1), (t2, o2, Some e2) when t1 = t2 && o1 = o2
        -> Some (t1, o1, Some e1), remain
      | (_, _, None), (_, _, None) -> None, []
      | _ -> Utils.impossible()
    else Utils.impossible()
  | [] -> None, []

let rec findFTDefs cfg v target other irList depth acc =
  if depth > 10 then acc
  else
    let def = findRegDef target other irList
    match def with
    | Some (_, other, None), remains
      //update other
      -> findFTDefs cfg v target other remains depth acc
    | Some (target, other, Some expr), remains
      -> match expr with
         | E.Cast(_, _, {E = Extract({E = Var(_, _, regStr, _)}, _, _, _)}, _)
            when regStr <>target.RegStr
            -> findFTDefs cfg v {target with RegStr=regStr}
                 other remains depth acc
         | _ -> {Target=target; Other=other; Expr=expr
                 Vertex=v; Remains=remains}::acc
    | None, _ ->
      let preds = GetFallThroughPreds cfg v
      preds |> List.fold(fun acc pred ->
        let pred = pred :?> PerVertex<IRBasicBlock>
        let irs = GetIRInfo pred |> List.rev
        findFTDefs cfg pred target other irs (depth+1) acc
        ) acc

let rec TryGetMemAccIR cfg
    ((regInfo: RegInfo list), (v: PerVertex<IRBasicBlock>), irList) acc =
  let regInfo1 = {regInfo[0] with Addr = uint64 0}
  let regInfo2 = {regInfo[1] with Addr = uint64 0}
  let rec getMemAccPatterns (expr: E) stage =
    match expr with
    | E.Cast (_, _, {E = Load (_, t, memExpr, _)}, _) when stage = 0
     -> getMemAccPatterns memExpr.E 1
    | BinOp (BinOpType.ADD, 64<rt>, {E=Var(_,regID1, regStr1, _)},
             {E=Var(_,regID2, regStr2, _)}, _) when stage = 1
      -> match regStr1 with
         | "CSBase" | "DSBase" | "ESBase" | "FSBase" | "GSBase" -> []
         | _ -> {RegID=regID1; RegStr=regStr1; Addr=uint64 0
                  }::[{RegID=regID2; RegStr=regStr2; Addr=uint64 0}]
    | BinOp (BinOpType.ADD, 64<rt>, {E=Var(_,regID1, regStr1, _)}, expr2, _)
    | BinOp (BinOpType.ADD, 64<rt>, expr2, {E=Var(_,regID1, regStr1, _)}, _)
      -> if stage <> 1 then []
         else match regStr1 with
              | "CSBase" | "DSBase" | "ESBase" | "FSBase" | "GSBase"
                -> getMemAccPatterns expr2.E stage
              | _ -> [{RegID=regID1; RegStr=regStr1; Addr=uint64 0}]
    | _ -> []

  let defs1 =  findFTDefs cfg v regInfo1 regInfo2 irList 0 List.Empty
  let defs2 =  findFTDefs cfg v regInfo2 regInfo1 irList 0 defs1

  let defs = defs2
             |> List.fold (fun acc info ->
                let regs = getMemAccPatterns info.Expr 0
                if regs.IsEmpty then acc
                else (info, regs)::acc
              ) List.Empty
  defs

let CreateBBLInfo (fn: RegularFunction) (rootBBL: PerVertex<IRBasicBlock>) =
  let visited = BitArray(10000000)
  //let baseIdx = rootBBL.GetID()
  let baseIdx = 0
  let bblDict = Dictionary<(Addr*Addr), BitArray>()
  let rec updateTbl cfg (v:PerVertex<IRBasicBlock>) cnt =
    if visited.Get(v.GetID()-baseIdx) then
      cnt
    else

      let ba = BitArray(40)
      visited.Set(v.GetID() - baseIdx, true)
      let rec accumulatedDef stmts =
        match stmts with
        | (stmt: LowUIR.Stmt)::tail -> match stmt.S with
                                        | Put ({E=Var (_, id, _, _)}, _)
                                          when int id < 40
                                         -> ba.Set(int id, true)
                                            accumulatedDef tail
                                        | _ -> accumulatedDef tail
        | [] -> ()
      if v.VData.IsFakeBlock() then
        ()
      else

        //v.VData.IRStatements
        v |> GetIRInfo |> List.iter(fun (stmts, _) ->
                                        accumulatedDef (stmts |> List.ofArray) )

        bblDict[(v.VData.Range.Min, v.VData.Range.Max)] <- ba

      DiGraph.GetSuccs(cfg, v)
      |> List.fold(fun cnt v ->
            //v.VData.Instructions
            if visited.Get(v.GetID()-baseIdx) then
              cnt
            else
              updateTbl cfg (v:?> PerVertex<IRBasicBlock>) (cnt+1)
        ) cnt

  let noV = updateTbl fn.IRCFG rootBBL 0
  noV, bblDict


let rec SearchRegDef cfg fn (bblDict: Dictionary<(Addr*Addr), BitArray>)
    (targetBBL: PerVertex<IRBasicBlock>) remains baseIdx acc
    (visitHistory: Dictionary<RegisterID, BitArray>) regInfo =

  let bArray = if visitHistory.ContainsKey regInfo.RegID then
                 visitHistory[regInfo.RegID]
               else
                 visitHistory[regInfo.RegID] <- BitArray(8000000)
                 visitHistory[regInfo.RegID]

  if (remains |> List.length) = (GetIRInfo targetBBL |> List.length) then
    bArray.Set(targetBBL.GetID()-baseIdx, true)

  let rec findRegDef id v irList =
    match irList with
    | (ir, addr)::remain ->
      let res = ir |> List.ofArray
                |> List.rev
                |> List.fold(fun acc stmt ->
                    match stmt.S with
                    | Put ({E=Var (_, v2, v3, _)},
                           {E=Var (_, regId, regStr,_ )} )
                      when v2 = id ->
                        /// if it is not 64 bit register, we stop searching
                        if int regId > 0x10 then acc
                        else SearchRegDef cfg fn bblDict v remain baseIdx acc
                              visitHistory {regInfo with RegID=regId}
                    | Put ({E=Var (v1, v2, v3, v4)}, {E=e} )
                      when v2 = id -> ({regInfo with Addr=addr}, e)::acc
                    | _ -> acc
                    ) List.Empty
      if res |> List.isEmpty then findRegDef id v remain
      else res
    | [] -> []

  let rec searchRegDef cfg (v: PerVertex<IRBasicBlock>) id target remain acc =
    let ba = bblDict[(v.VData.Range.Min, v.VData.Range.Max)]
    let x = if ((int id) <= ba.Length) && ba.Get((int id)) then
              findRegDef id v remain
            else []
    //let x =  findRegDef target remain
    if x |> List.isEmpty then
      DiGraph.GetPreds (cfg, v)
      |> List.fold (fun acc pred ->
        let edge = DiGraph.FindEdgeData (cfg, pred, v)
        match edge with
        | FallThroughEdge
        | CallFallThroughEdge
        | IndirectJmpEdge
        | InterJmpEdge
        | InterCJmpFalseEdge | InterCJmpTrueEdge
        | IntraCJmpFalseEdge | IntraCJmpTrueEdge
          ->
          let pred = pred :?> PerVertex<IRBasicBlock>
          if bArray.Get(pred.GetID()-baseIdx) then acc
          else
            bArray.Set(pred.GetID()-baseIdx, true)
            let targetIRs = GetIRInfo pred |> List.rev
            searchRegDef cfg pred id target targetIRs acc
        | _ -> acc
        ) acc
    else x@acc

  searchRegDef (fn:RegularFunction).IRCFG targetBBL
                regInfo.RegID regInfo.RegStr remains acc

let TryGetTblDef codeMgr fn bblDict targetBBL baseIdx
      (defs: (Addr*(TwoRegInfo*RegInfo list) list) list) jmpAddr jmpReg =

  let funCodeMgr =
      (codeMgr: CodeManager).GetFunCodeMgr (fn: RegularFunction).EntryPoint

  let makeStruct info memRegInfo addAddr =
    {JmpSite = {Addr=jmpAddr; Regs=[jmpReg]; OpType="JMP"};
     AddSite = {Addr=addAddr; Regs=[info.Target.RegStr; info.Other.RegStr]
                OpType="ADD"};
     MemAccSite = {Addr= $"0x%x{info.Target.Addr}"
                   Regs= [info.Target.RegStr]; OpType="MEM_ACCESS"};
     TblRefSite= if info.Other.Addr = uint64 0 then
                  [{ SiteInfo = {Addr= $"0x%x{memRegInfo.Addr}"
                                 Regs=[memRegInfo.RegStr]; OpType="REF"};
                    IsDeterminate=false}]
                 //if other register is defined before memory access, we add it
                 else [{ SiteInfo = {Addr= $"0x%x{info.Other.Addr}";
                                     Regs=[info.Other.RegStr]; OpType="REF"};
                         IsDeterminate=true};
                       { SiteInfo = {Addr= $"0x%x{memRegInfo.Addr}"
                                     Regs=[memRegInfo.RegStr]; OpType="REF"}
                         IsDeterminate=false}]
     TblAddr=funCodeMgr.GetTblCandidateDict[memRegInfo.Addr]}

  let getDef reg info addAddr =
    let visitHistory = Dictionary<RegisterID, BitArray>()
    let tblDefAddrs =
      reg
      |> SearchRegDef (fn.IRCFG) fn bblDict info.Vertex info.Remains
                 baseIdx List.Empty visitHistory
      |> List.filter(fun (refRegInfo, expr) ->
                 funCodeMgr.GetTblCandidateDict.ContainsKey refRegInfo.Addr)
      |> List.map(fun (refRegInfo, expr) ->
                  //printf "\tDef: 0x%x, 0x%x\n" refRegInfo.Addr
                  // funCodeMgr.GetTblCandidateDict[refRegInfo.Addr]
                  makeStruct info refRegInfo addAddr)
    tblDefAddrs

  defs
  |> List.fold (fun acc (addAddr, irs) ->
    irs |> List.fold (fun acc (info, memAccRegs) ->
      //printf "\tMemAccess: 0x%x %A\n" info.Target.Addr
      //  (memAccRegs|>List.map(fun memReg -> memReg.RegStr))
      if info.Other.Addr <> (uint64 0) then
        //printf "\tTable Def : 0x%x (%s)\n" info.Other.Addr info.Other.RegStr
        //TODO: analyze memAccess Pattern
        let tblDefAddrs
            = memAccRegs |> List.fold(fun (acc: BranchInfo list) reg->
               let tblDefAddrs = getDef reg info ( $"0x%x{addAddr}")
               tblDefAddrs@acc
              ) List.Empty
        tblDefAddrs@acc
      else
        //TODO: check memeAccess Pattern uses 'Other' register...
        let tblDefAddrs = getDef info.Other info ( $"0x%x{addAddr}")
        if info.Other = memAccRegs[0] then
          tblDefAddrs@acc

        else
          let tblDefAddrs2 = getDef memAccRegs[0] info ( $"0x%x{addAddr}")
          let tblDefAddrs3 =
            tblDefAddrs |> List.fold(fun acc info ->
              tblDefAddrs2 |> List.fold(fun acc info2 ->
                if info.AddSite = info2.AddSite
                  && info.JmpSite = info2.JmpSite
                  && info.MemAccSite = info2.MemAccSite
                  && info.TblAddr = info2.TblAddr then
                    let tblRefRegs1 = info.TblRefSite[0].SiteInfo.Regs
                    let tblRefRegs2 = info2.TblRefSite[0].SiteInfo.Regs
                    let tblRefRegs3 = tblRefRegs1@tblRefRegs2
                    assert (tblRefRegs3.Length = 2)
                    let tblRefSite =
                        [{ SiteInfo = {Addr=info.TblRefSite[0].SiteInfo.Addr
                                       Regs=tblRefRegs3; OpType="REF"};
                          IsDeterminate=false}]

                    {info with TblRefSite=tblRefSite}::acc
                else acc
                ) acc
              ) List.Empty
          tblDefAddrs3@acc
      ) acc ) List.Empty

let ConstructBBLInfo fn =
  // create block info
  let rootBBL =
      (fn:RegularFunction).IRCFG.FindVertexBy (fun v ->
        v.VData.PPoint.Address = fn.EntryPoint
        && not <| v.VData.IsFakeBlock ())

  //let stopWatch = System.Diagnostics.Stopwatch.StartNew()
  let noV, bblDict = CreateBBLInfo fn (rootBBL :?> PerVertex<IRBasicBlock>)
  rootBBL, bblDict, noV
  //stopWatch.Stop()
  //printfn "\t\t runtime total: %f msec" stopWatch.Elapsed.TotalMilliseconds

let ResolveIndBr codeMgr fn jmpBlkAddr jmpSite rootBBL bblDict noV =

  // step 1. find indirect branch IR
  let targetBBL =
      (fn:RegularFunction).IRCFG.FindVertexBy (fun v ->
        v.VData.PPoint.Address = jmpBlkAddr
        && not <| v.VData.IsFakeBlock ())
      :?> PerVertex<IRBasicBlock>
  //let baseIdx = rootBBL.GetID()
  let baseIdx = 0

  let jmpAddr, jmpReg, _, remains, targetBBL
      = GetJmpSiteIR (fn.IRCFG) [targetBBL] jmpSite List.Empty

  //printf "\tJump: 0x%x\n" jmpAddr

  // step 2. find BinOp
  let binOpIRs = TryGetBinOpIR (fn.IRCFG) targetBBL remains jmpReg List.Empty

  // step 3. find memory access IR
  let defs =
    binOpIRs
    |> List.fold(fun acc (regs, targetBBL, remains) ->
        let addAddr = regs[0].Addr
        let irs = TryGetMemAccIR fn.IRCFG (regs, targetBBL, remains) List.Empty
        (addAddr, irs)::acc
      ) List.Empty

  // step 4. search table Def
  let tbls = TryGetTblDef codeMgr fn bblDict targetBBL baseIdx
               defs ( $"0x%x{jmpAddr}" ) jmpReg

#if CFGDEBUG2
  tbls |> List.map(fun info -> info.TblAddr)
       |> List.distinct
       |> List.iter(fun addr -> printf "\tDiscovered Tbl %x\n" addr)
#endif

  //printf "\tNum vertex %d\n" noV
  tbls



let GetAccType stmt acc =
  let rec exprCheck (expr: E) =
    match expr with
    | Cast (_, _, ex, _) ->
      exprCheck ex.E
    | Load (_, _, ex, _) ->
      exprCheck ex.E
    | Var ( _,_, regBStr,_) ->
      if  regBStr <> "CSBase" && regBStr <> "DSBase" && regBStr <> "ESBase" &&
          regBStr <> "FSBase" && regBStr <> "GSBase" && regBStr <> "SSBase" &&
          regBStr <> "RSP" then
        true
      else false
    | BinOp (_, _, ex, _, _) ->
      exprCheck ex.E
    | _ -> true


  match stmt.S with
  | Put ({E=Var (_, _, regStr, _)},
         {E=Load (_, _, expr, exprInfo)})
    when regStr <> "RSP" && exprInfo.HasLoad
    ->  if exprCheck expr.E then "R"::acc
        else acc
  | Put ({E=Var (_, _, regStr, _)},
         {E=Cast (_, _, expr, exprInfo)})
    when regStr <> "RSP" && exprInfo.HasLoad
    ->  if exprCheck expr.E then "R"::acc
        else acc
  | Put ({E=TempVar (_,_)},
         {E=Load (_, _, expr, exprInfo)})
    when exprInfo.HasLoad
    ->  if exprCheck expr.E then "R"::acc
        else acc
  | InterJmp ({E=Load (_, _, _, exprInfo)}, _)
    when exprInfo.HasLoad
    -> "R"::acc
  | Store (_, expr, _)
    ->  if exprCheck expr.E then "S"::acc
        else acc
  | _ -> acc


let ResolveFortranIndBr codeMgr fn jmpBlkAddr jmpSite rootBBL bblDict noV =
  let targetBBL =
    (fn:RegularFunction).IRCFG.FindVertexBy (fun v ->
      v.VData.PPoint.Address = jmpBlkAddr
      && not <| v.VData.IsFakeBlock ())
    :?> PerVertex<IRBasicBlock>

  let baseIdx = 0

  let jmpAddr, jmpReg, jmpRegID, remains, targetBBL
      = GetJmpSiteIR (fn.IRCFG) [targetBBL] jmpSite List.Empty

  match jmpRegID with
  | Some regID ->
    let visitHistory = Dictionary<RegisterID, BitArray>()
    let reg = {RegID=regID; RegStr=jmpReg; Addr=uint64 jmpAddr}
    let funCodeMgr =
      (codeMgr: CodeManager).GetFunCodeMgr (fn: RegularFunction).EntryPoint
    let tblDefAddrs =
          SearchRegDef (fn.IRCFG) fn bblDict targetBBL remains
              baseIdx List.Empty visitHistory reg
          |> List.filter(fun (refRegInfo, expr) ->
                 funCodeMgr.GetCodePtrCandidateDict.ContainsKey refRegInfo.Addr)
          |> List.map(fun (refRegInfo, expr) ->
                let dst = funCodeMgr.GetCodePtrCandidateDict[refRegInfo.Addr]
                printfn "found fortran indirect jump %x -> %x"
                  jmpSite dst
                funCodeMgr.RegisterLocalCodePtr dst
                funCodeMgr.UnregisterCodePtrCandidateDict refRegInfo.Addr |> ignore
                dst
                )
    tblDefAddrs
  | _ -> []

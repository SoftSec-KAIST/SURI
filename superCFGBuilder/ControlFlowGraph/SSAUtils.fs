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

module internal SuperCFG.ControlFlowGraph.SSAUtils

open B2R2
open SuperCFG.SSA
open SuperCFG.BinGraph

let computeDominatorInfo g root =
  let domCtxt = Dominator.initDominatorContext g root
  let frontiers = Dominator.frontiers domCtxt
  g.IterVertex (fun (v: SSAVertex) ->
    let dfnum = domCtxt.ForwardDomInfo.DFNumMap[v.GetID ()]
    v.VData.ImmDominator <- Dominator.idom domCtxt v
    v.VData.DomFrontier <- frontiers[dfnum])
  domCtxt

let collectDefVars defs (_, stmt) =
  match stmt with
  | Def ({ Kind = k }, _) -> Set.add k defs
  | _ -> defs

let findPhiSites g defsPerNode variable (phiSites, workList) v =
  if Set.contains v phiSites then phiSites, workList
  else
    match variable with
    (* Temporary vars are only meaningful in an instruction boundary. Thus, a
       PhiSite for a TempVar should be an intra-instruction bbl, but not the
       start of an instruction. *)
    | TempVar _ when (v: SSAVertex).VData.PPoint.Position = 0 ->
      phiSites, workList
    | _ ->
      (* Insert Phi for v *)
      DiGraph.GetPreds (g, v)
      |> List.length
      |> v.VData.PrependPhi variable
      let phiSites = Set.add v phiSites
      let defs = (defsPerNode: DefsPerNode)[v]
      if not <| Set.contains variable defs then phiSites, v :: workList
      else phiSites, workList

let rec iterDefs g phiSites defsPerNode variable = function
  | [] -> phiSites
  | (v: SSAVertex) :: workList ->
    let phiSites, workList =
      v.VData.DomFrontier
      |> List.fold (findPhiSites g defsPerNode variable) (phiSites, workList)
    iterDefs g phiSites defsPerNode variable workList

let placePhis g vertices (defSites: DefSites) domCtxt =
  let defsPerNode = DefsPerNode ()
  vertices
  |> Seq.iter (fun (v: SSAVertex) ->
    let defs = v.VData.SSAStmtInfos |> Array.fold collectDefVars Set.empty
    defsPerNode[v] <- defs
    defs |> Set.iter (fun d ->
      if defSites.ContainsKey d then defSites[d] <- Set.add v defSites[d]
      else defSites[d] <- Set.singleton v))
  for KeyValue (variable, defs) in defSites do
    Set.toList defs
    |> iterDefs g Set.empty defsPerNode variable
    |> ignore
  domCtxt

let renameVar (stack: IDStack) (v: Variable) =
  match stack.TryGetValue v.Kind with
  | false, _ -> v.Identifier <- 0
  | true, ids -> v.Identifier <- List.head ids

let rec renameVarList stack = function
  | [] -> ()
  | v :: vs -> renameVar stack v; renameVarList stack vs

let rec renameExpr stack = function
  | Num (_)
  | Undefined (_)
  | FuncName (_)
  | Nil -> ()
  | ReturnVal (_, _, v) -> renameVar stack v
  | Var v -> renameVar stack v
  | Load (v, _, expr) ->
    renameVar stack v
    renameExpr stack expr
  | Store (mem, _, addr, expr) ->
    renameVar stack mem
    renameExpr stack addr
    renameExpr stack expr
  | UnOp (_, _, expr) ->
    renameExpr stack expr
  | BinOp (_, _, expr1, expr2) ->
    renameExpr stack expr1
    renameExpr stack expr2
  | RelOp (_, _, expr1, expr2) ->
    renameExpr stack expr1
    renameExpr stack expr2
  | Ite (expr1, _, expr2, expr3) ->
    renameExpr stack expr1
    renameExpr stack expr2
    renameExpr stack expr3
  | Cast (_, _, expr) ->
    renameExpr stack expr
  | Extract (expr, _, _) ->
    renameExpr stack expr

let renameJmp stack = function
  | IntraJmp _ -> ()
  | IntraCJmp (expr, _, _) ->
    renameExpr stack expr
  | InterJmp (expr) ->
    renameExpr stack expr
  | InterCJmp (cond, target1, target2) ->
    renameExpr stack cond
    renameExpr stack target1
    renameExpr stack target2

let introduceDef (count: VarCountMap) (stack: IDStack) (v: Variable) =
  count[v.Kind] <- count[v.Kind] + 1
  let i = count[v.Kind]
  stack[v.Kind] <- i :: stack[v.Kind]
  v.Identifier <- i

let rec introduceDefList count stack = function
  | [] -> ()
  | v :: vs -> introduceDef count stack v; introduceDefList count stack vs

let renameStmt count stack (_, stmt) =
  match stmt with
  | LMark _ -> ()
  | ExternalCall (e, inVars, outVars) ->
    renameExpr stack e
    renameVarList stack inVars
    introduceDefList count stack outVars
  | SideEffect _ -> ()
  | Jmp jmpTy -> renameJmp stack jmpTy
  | Def (def, e) ->
    renameExpr stack e
    introduceDef count stack def
  | Phi (def, _) ->
    introduceDef count stack def

let renamePhiAux (stack: IDStack) preds (parent: SSAVertex) (_, stmt) =
  match stmt with
  | Phi (def, nums) ->
    let idx =
      List.findIndex (fun (v: SSAVertex) ->
        v.VData = parent.VData) preds
    nums[idx] <- List.head stack[def.Kind]
  | _ -> ()

let renamePhi g stack parent (succ: SSAVertex) =
  succ.VData.SSAStmtInfos
  |> Array.iter (renamePhiAux stack (DiGraph.GetPreds (g, succ)) parent)

let popStack (stack: IDStack) (_, stmt) =
  match stmt with
  | Def (def, _)
  | Phi (def, _) -> stack[def.Kind] <- List.tail stack[def.Kind]
  | _ -> ()

let rec rename g domTree count stack (v: SSAVertex) =
  v.VData.SSAStmtInfos |> Array.iter (renameStmt count stack)
  DiGraph.GetSuccs (g, v) |> List.iter (renamePhi g stack v)
  traverseChildren g domTree count stack (Map.find v domTree)
  v.VData.SSAStmtInfos |> Array.iter (popStack stack)

and traverseChildren g domTree count stack = function
  | child :: rest ->
    rename g domTree count stack child
    traverseChildren g domTree count stack rest
  | [] -> ()

let renameVars g (defSites: DefSites) domCtxt =
  let domTree, root = Dominator.dominatorTree domCtxt
  let count = VarCountMap ()
  let stack = IDStack ()
  defSites.Keys |> Seq.iter (fun variable ->
    count[variable] <- 0
    stack[variable] <- [0])
  rename g domTree count stack root |> ignore

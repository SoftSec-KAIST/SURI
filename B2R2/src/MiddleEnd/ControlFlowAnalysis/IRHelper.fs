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

module B2R2.MiddleEnd.ControlFlowAnalysis.IRHelper

open B2R2
open B2R2.BinIR
open B2R2.BinIR.SSA
open B2R2.MiddleEnd.DataFlow
open B2R2.BinIR.SSA

let private varToBV cpState var id =
  let v = { var with Identifier = id }
  match CPState.findReg cpState v with
  | Const bv | Thunk bv | Pointer bv -> Some bv
  | _ -> None

let private expandPhi cpState var ids e =
  let bvs = ids |> Array.toList |> List.map (fun id -> varToBV cpState var id)
  match bvs[0] with
  | Some hd ->
    (*if bvs.Tail |> List.forall (function Some bv -> bv = hd | None -> false)
    then Num hd
    else e*)
    Num hd
  | None -> e

/// Recursively expand vars until we meet a Load expr.
let rec symbolicExpand cpState = function
  | Num _ as e -> e
  | Var v as e ->
    match Map.tryFind v cpState.SSAEdges.Defs with
    | Some (Def (_, e)) -> symbolicExpand cpState e
    | Some (Phi (_, ids)) -> expandPhi cpState v ids e
    | _ -> e
  | Load _ as e -> e
  | UnOp (_, _, Load _) as e -> e
  | UnOp (op, rt, e) ->
    let e = symbolicExpand cpState e
    UnOp (op, rt, e)
  | BinOp (_, _, Load _, _)
  | BinOp (_, _, _, Load _) as e -> e
  | BinOp (op, rt, e1, e2) ->
    let e1 = symbolicExpand cpState e1
    let e2 = symbolicExpand cpState e2
    BinOp (op, rt, e1, e2)
  | RelOp (_, _, Load _, _)
  | RelOp (_, _, _, Load _) as e -> e
  | RelOp (op, rt, e1, e2) ->
    let e1 = symbolicExpand cpState e1
    let e2 = symbolicExpand cpState e2
    RelOp (op, rt, e1, e2)
  | Ite (Load _, _, _, _)
  | Ite (_, _, Load _, _)
  | Ite (_, _, _, Load _) as e -> e
  | Ite (e1, rt, e2, e3) ->
    let e1 = symbolicExpand cpState e1
    let e2 = symbolicExpand cpState e2
    let e3 = symbolicExpand cpState e3
    Ite (e1, rt, e2, e3)
  | Cast (_, _, Load _) as e -> e
  | Cast (op, rt, e) ->
    let e = symbolicExpand cpState e
    Cast (op, rt, e)
  | Extract (Load _, _, _) as e -> e
  | Extract (e, rt, pos) ->
    let e = symbolicExpand cpState e
    Extract (e, rt, pos)
  | e -> e

let rec simplify = function
  | Load (v, rt, e) -> Load (v, rt, simplify e)
  | Store (v, rt, e1, e2) -> Store (v, rt, simplify e1, simplify e2)
  | BinOp (BinOpType.ADD, rt, BinOp (BinOpType.ADD, _, Num v1, e), Num v2)
  | BinOp (BinOpType.ADD, rt, BinOp (BinOpType.ADD, _, e, Num v1), Num v2)
  | BinOp (BinOpType.ADD, rt, Num v1, BinOp (BinOpType.ADD, _, e, Num v2))
  | BinOp (BinOpType.ADD, rt, Num v1, BinOp (BinOpType.ADD, _, Num v2, e)) ->
    BinOp (BinOpType.ADD, rt, e, Num (BitVector.Add (v1, v2)))
  | BinOp (BinOpType.ADD, _, Num v1, Num v2) -> Num (BitVector.Add (v1, v2))
  | BinOp (BinOpType.SUB, _, Num v1, Num v2) -> Num (BitVector.Sub (v1, v2))
  | BinOp (BinOpType.MUL, _, Num v1, Num v2) -> Num (BitVector.Mul (v1, v2))
  | BinOp (BinOpType.DIV, _, Num v1, Num v2) -> Num (BitVector.Div (v1, v2))
  | BinOp (BinOpType.AND, _, Num v1, Num v2) -> Num (BitVector.BAnd (v1, v2))
  | BinOp (BinOpType.OR, _, Num v1, Num v2) -> Num (BitVector.BOr (v1, v2))
  | BinOp (BinOpType.SHR, _, Num v1, Num v2) -> Num (BitVector.Shr (v1, v2))
  | BinOp (BinOpType.SHL, _, Num v1, Num v2) -> Num (BitVector.Shl (v1, v2))
  | BinOp (op, rt, e1, e2) ->
    let e1 = simplify e1
    let e2 = simplify e2
    match e1, e2 with
    | Num _, Num _ -> simplify (BinOp (op, rt, e1, e2))
    | _ -> BinOp (op, rt, e1, e2)
  | UnOp (op, rt, e) -> UnOp (op, rt, simplify e)
  | RelOp (op, rt, e1, e2) -> RelOp (op, rt, simplify e1, simplify e2)
  | Ite (c, rt, e1, e2) -> Ite (simplify c, rt, simplify e1, simplify e2)
  | Cast (k, rt, e) ->
     match simplify e with
      | Extract (Num v1, _, _) -> Num v1
      | e1 -> Cast (k, rt, e1 )
  | Extract (Cast (CastKind.ZeroExt, _, e), rt, 0) when AST.typeOf e = rt -> e
  | Extract (Cast (CastKind.SignExt, _, e), rt, 0) when AST.typeOf e = rt -> e
  | Extract (e, rt, pos) -> Extract (simplify e, rt, pos)
  | expr -> expr

let rec foldWithConstant cpState = function
  | Var v as e ->
    match CPState.findReg cpState v with
    | Const bv | Thunk bv | Pointer bv -> Num bv
    | _ ->
      match Map.tryFind v cpState.SSAEdges.Defs with
      | Some (Def (_, e)) -> foldWithConstant cpState e
      | _ -> e
  | Load (m, rt, addr) as e ->
    match foldWithConstant cpState addr with
    | Num addr ->
      let addr = BitVector.ToUInt64 addr
      match CPState.tryFindMem cpState m rt addr with
      | Some (Const bv) | Some (Thunk bv) | Some (Pointer bv) -> Num bv
      | _ -> e
    | _ -> e
  | UnOp (op, rt, e) -> UnOp (op, rt, foldWithConstant cpState e)
  | BinOp (op, rt, e1, e2) ->
    let e1 = foldWithConstant cpState e1
    let e2 = foldWithConstant cpState e2
    BinOp (op, rt, e1, e2) |> simplify
  | RelOp (op, rt, e1, e2) ->
    let e1 = foldWithConstant cpState e1
    let e2 = foldWithConstant cpState e2
    RelOp (op, rt, e1, e2)
  | Ite (e1, rt, e2, e3) ->
    let e1 = foldWithConstant cpState e1
    let e2 = foldWithConstant cpState e2
    let e3 = foldWithConstant cpState e3
    Ite (e1, rt, e2, e3)
  | Cast (op, rt, e) -> Cast (op, rt, foldWithConstant cpState e)
  | Extract (e, rt, pos) -> Extract (foldWithConstant cpState e, rt, pos)
  | e -> e

let resolveExpr cpState needConstFolding expr =
  expr
  |> symbolicExpand cpState
  |> fun expr ->
    if needConstFolding then foldWithConstant cpState expr else expr
  |> simplify


let rec discoverVar cpState addr depth ess v =
  if depth > 0 && (ess |> List.isEmpty) then
    match Map.tryFind v cpState.SSAEdges.Defs with
    | Some (Def (v0:Variable, e0)) ->
      match v.Kind, e0 with
      | RegVar _ as rv, e0  ->
        match CPState.findReg cpState v with
        | Const bv | Thunk bv | Pointer bv ->
          if BitVector.ToUInt64 bv = addr then bv::ess
          else ess
        | _ ->  match e0 with
                | Var v1 -> v1 |> discoverVar cpState addr (depth-1) ess
                | _ -> ess
      | _ -> ess
    | Some (Phi (_, ids)) ->
      let vars = ids |> Seq.distinct |> List.ofSeq
                  |> List.map (fun id -> { v with Identifier = id })
      if vars |> List.isEmpty then ess
      else (ess, vars)
            ||> List.fold(fun b v -> discoverVar cpState addr (depth-1) b v)
    | _ -> ess
  else
    ess

let private expandPhiWithTarget cpState var ids addr e =
  let bvs = ids |> Seq.distinct |> List.ofSeq
                |> List.map (fun id -> { var with Identifier = id })
                |> List.fold(discoverVar cpState addr 10) List.empty
  if bvs.IsEmpty then
    e
  else
    Num bvs[0]


let rec symbolicExpandWithTarget2 cpState addr depth = function
  | Num _ as e -> [e]
  | Var v as e when depth > 0 ->
    match Map.tryFind v cpState.SSAEdges.Defs with
    | Some (Def (_, e)) ->
      symbolicExpandWithTarget2 cpState addr (depth-1) e
    | Some (Phi (_, ids)) ->
      let res = ids |> Seq.distinct |> List.ofSeq
              |> List.map (fun id -> symbolicExpandWithTarget2 cpState addr
                                      (depth-1) (Var {v with Identifier = id}))
      (*
      let e1 = List.concat res
      if depth = 10 then (expandPhiWithTarget cpState v ids addr e)::e1
      else e1
      *)
      List.concat res
    | _ -> [e]
  | Load _ as e -> [e]
  | UnOp (_, _, Load _) as e -> [e]
  | UnOp (op, rt, e) ->
    let e = symbolicExpandWithTarget2 cpState addr (depth-1) e
    [UnOp (op, rt, e[0])]
  | BinOp (_, _, Load _, _)
  | BinOp (_, _, _, Load _) as e -> [e]
  | BinOp (op, rt, e1, e2) ->
    let e1 = symbolicExpandWithTarget2 cpState addr (depth-1) e1
    let e2 = symbolicExpandWithTarget2 cpState addr (depth-1) e2
    [BinOp (op, rt, e1[0], e2[0])]
  | RelOp (_, _, Load _, _)
  | RelOp (_, _, _, Load _) as e -> [e]
  | RelOp (op, rt, e1, e2) ->
    let e1 = symbolicExpandWithTarget2 cpState addr (depth-1) e1
    let e2 = symbolicExpandWithTarget2 cpState addr (depth-1) e2
    [RelOp (op, rt, e1[0], e2[0])]
  | Ite (Load _, _, _, _)
  | Ite (_, _, Load _, _)
  | Ite (_, _, _, Load _) as e -> [e]
  | Ite (e1, rt, e2, e3) ->
    let e1 = symbolicExpandWithTarget2 cpState addr (depth-1) e1
    let e2 = symbolicExpandWithTarget2 cpState addr (depth-1) e2
    let e3 = symbolicExpandWithTarget2 cpState addr (depth-1) e3
    [Ite (e1[0], rt, e2[0], e3[0])]
  | Cast (_, _, Load _) as e -> [e]
  | Cast (op, rt, e) ->
    let e = symbolicExpandWithTarget2 cpState addr (depth-1) e
    [Cast (op, rt, e[0])]
  | Extract (Load _, _, _) as e -> [e]
  // prohibit: lea reg32, dword ptr [rip+num]
  | Extract (BinOp (BinOpType.ADD, a, Var b, Num _), 32<rt>, 0x0) as e
    when b.Kind = PCVar 64<rt> -> [e]
  | Extract (BinOp (BinOpType.ADD, a, Num _, Var b), 32<rt>, 0x0) as e
    when b.Kind = PCVar 64<rt> -> [e]
  | Extract (e, rt, pos) ->
    let e = symbolicExpandWithTarget2 cpState addr (depth-1) e
    [Extract (e[0], rt, pos)]
  | e -> [e]

/// Recursively expand vars until we meet a Load expr.
let rec symbolicExpandWithTarget cpState addr depth stage = function
  | Var v as e when depth > 0 ->
    match Map.tryFind v cpState.SSAEdges.Defs with
    | Some (Def (_, e1)) when stage = 1 || stage = 2 ->
        symbolicExpandWithTarget cpState addr (depth-1) 2 e1
    | Some (Def (v1:Variable, e1)) when stage = 3 ->
      match v1.Kind with
      | RegVar _ -> symbolicExpandWithTarget2 cpState addr 10 e
      | _ -> symbolicExpandWithTarget cpState addr (depth-1) 3 e1
    | Some (Phi (_, ids)) when stage = 1 || stage = 2 ->
      let ret = ids |> Seq.distinct |> List.ofSeq
                    |> List.map (fun id -> symbolicExpandWithTarget cpState addr
                                            (depth-1) stage
                                            (Var { v with Identifier = id }))
      List.concat ret  // which one is jmp table based indirect brandh?
    | Some (Phi _) when stage = 3 ->
      symbolicExpandWithTarget2 cpState addr 10 e
    | _ -> [e]
  | BinOp (op, rt, e1, e2) when stage = 2->
    let e1 = symbolicExpandWithTarget cpState addr depth 3 e1
              |> List.filter
                   (fun expr -> match expr with
                                 | Num _ | Cast _ | BinOp _ -> true
                                 | _ -> false)
              |> List.map(simplify)
              |> Seq.distinct |> List.ofSeq
    let e2 = symbolicExpandWithTarget cpState addr depth 3 e2
              |> List.filter
                   (fun expr -> match expr with
                                 | Num _ | Cast _ | BinOp _ -> true
                                 | _ -> false)
              |> List.map(simplify)
              |> Seq.distinct |> List.ofSeq
    let rec makePairs x lst acc =
      match lst with
      | [] -> acc
      | _  -> makePairs x (List.tail lst)
                (acc @ [BinOp (op, rt, x, List.head lst)])
    // return possible combinations
    e1 |> List.fold(fun ess item -> makePairs item e2 ess) List.Empty
  | e -> [e]

let resolveExprWithTarget cpState needConstFolding addr expr =
  expr
  |> symbolicExpandWithTarget cpState addr 10 1
  |> List.map(fun expr ->
    if needConstFolding then foldWithConstant cpState expr else expr
    |> simplify)

let rec stage3 cpState baseAddr ess depth = function
  | Num _ as e -> e, ess, false
  | Var v as e ->
    if depth < 0 then e, ess, false
    else
      match Map.tryFind v cpState.SSAEdges.Defs with
      | Some (Def (v:Variable, e)) ->
        match v.Kind, e with
        | RegVar _, BinOp (BinOpType.ADD, _, e1, e2) ->
          let e1, ess, _ = stage3 cpState baseAddr ess (depth-1) e1
          let e2, ess, _ = stage3 cpState baseAddr ess (depth-1) e2
          match e1, e2 with
          | Num v1, Num v2 ->
            let ess = Set.add v ess
            let e3 = Num (v1.Add v2)    /// RIP-relative addressing
            let x3 = v1.Add v2    /// RIP-relative addressing
            if BitVector.ToUInt64 x3 = baseAddr then e3, ess, true
            else e3, ess, false
          | _ ->  e, ess, false
        | _ -> e, ess, false
      | Some (Phi (_, ids)) ->
        let bvs = ids |> Array.toList
                      |> List.map (fun id -> {v with Identifier = id})
        let res = bvs |> List.map(
                        fun v -> stage3 cpState baseAddr ess (depth-1) (Var v))
                      |> List.filter(fun (_,_,b) -> b)
        if res.Length > 0 then res.[0]
        else e, ess, false
      | _ -> e, ess, false
  | e -> e, ess, false

let rec stage2 cpState baseAddr ess depth = function
  | Var v as e ->
    if depth < 0 then e, ess, false
    else
      match Map.tryFind v cpState.SSAEdges.Defs with
      | Some (Def (v:Variable, e0)) ->
        match v.Kind, e0 with
        | RegVar _, BinOp (BinOpType.ADD, _, e1, e2)  ->
          //the register may hold jump table base address
          let ex, ess, bFound = stage3 cpState baseAddr ess (depth-1) e
          let ess = if bFound then Set.add v ess else ess
          ex, ess, bFound
        | _ ->
          let e, ess, bFound = stage2 cpState baseAddr ess (depth-1) e0
          let ess = if bFound then Set.add v ess else ess
          e, ess, bFound
      | Some (Phi (_, ids)) ->
        let bvs = ids |> Array.toList
                      |> List.map (fun id -> {v with Identifier = id})
        let res = bvs |> List.map(
                        fun v -> stage2 cpState baseAddr ess (depth-1) (Var v))
                      |> List.filter(fun (_,_,b) -> b)
        if res.Length > 0 then res.[0]
        else e, ess, false
      | _ -> e, ess, false
  | Cast (op, rt, e) ->
    stage2 cpState baseAddr ess (depth-1) e
  | Load (v, r, e) ->
    if depth < 0 then e, ess, false
    else
      match e with
      | BinOp (BinOpType.ADD, _, e1, e2) ->
        //one of two registers may hold jump table base address
        let e1, ess, bFound1 =  stage3 cpState baseAddr ess (depth-1) e1
        let e2, ess, bFound2 = stage3 cpState baseAddr ess (depth-1) e2
        match e1, e2 with
        | Num _, Num _ -> e, ess, false /// impossible ???
        | Num _, _ -> e1, ess, bFound1 || bFound2
        | _, Num _ -> e2, ess, bFound1 || bFound2
        | _ ->  e, ess, false
      | _ ->  e, ess, false
  | e -> e, ess, false

let rec stage1 cpState baseAddr ess depth = function
  | Var v as e ->
    if depth < 0 then ess, false
    else
      match Map.tryFind v cpState.SSAEdges.Defs with
      | Some (Def (v:Variable, e)) ->
        let ess, bFound = stage1 cpState baseAddr ess (depth-1) e
        match v.Kind with
        | RegVar _
        | TempVar _ ->
          let ess = if bFound then Set.add v ess else ess
          ess, bFound
        | _ -> ess, bFound
      | Some (Phi (_, ids)) ->
        let bvs = ids |> Array.toList
                      |> List.map (fun id -> {v with Identifier = id})
        let res = bvs |> List.map(
                        fun v -> stage1 cpState baseAddr ess (depth-1) (Var v))
        ess, false ///TODO
      | _ -> ess, false
  | BinOp (BinOpType.ADD, rt, e1, e2) as e ->
    if depth < 0 then ess, false
    else
      let r1, ess, bFound1 = stage2 cpState baseAddr ess depth e1
      let r2, ess, bFound2 = stage2 cpState baseAddr ess depth e2
      ess, bFound1 && bFound2
  | _ -> ess, false


let rec GetSimpleUDChain cpState ess depth = function
  | Var v as e ->
    if depth < 0 then ess
    else
      match Map.tryFind v cpState.SSAEdges.Defs with
      | Some (Def (v:Variable, e0)) ->
        match v.Kind with
        | RegVar _  ->
          match CPState.findReg cpState v with
          | Const bv ->
            let candidate = BitVector.ToUInt64 bv
            Set.add candidate ess
          | _ ->
            GetSimpleUDChain cpState ess (depth-1) e0
        | _ ->
          GetSimpleUDChain cpState ess (depth-1) e0
      | Some (Phi (_, ids)) ->
        if depth < 0 then ess
        else
          let bvs = ids |> Array.toList
                    |> List.map (fun id -> {v with Identifier = id})
                    |> List.filter (fun item -> item <> v)
                    |> List.distinct |> List.ofSeq
          if bvs |> List.isEmpty then
            ess
          else
            (ess, bvs) ||> List.fold(fun ess v ->
                        GetSimpleUDChain cpState ess (depth-1) (Var v))
      | _ -> ess
  | BinOp (BinOpType.ADD, rt, e1, e2) as e ->
    if depth < 0 then ess
    else
      match e1, e2 with
      | Var {Kind = PCVar _}, Num v2 ->
        let (Var v) = e1
        match Map.tryFind v cpState.SSAEdges.Defs with
        | Some (Def (v:Variable, Num v1))
          -> let candidate = BitVector.ToUInt64 (v1.Add v2)
             Set.add candidate ess
        | _ -> ess
      | _ ->
        let ess1 = GetSimpleUDChain cpState ess (depth-1) e1
        let ess2 = GetSimpleUDChain cpState ess1 (depth-1) e2
        ess2
  | e -> ess

let rec getPPoints cpState ess = function
  | Num _ as e -> e, ess
  | Var v as e ->
    match Map.tryFind v cpState.SSAEdges.Defs with
    | Some (Def (v:Variable, e)) ->
      let ess = match v.Kind with
                  | RegVar _  -> Set.add v ess
                  | _ -> ess
      getPPoints cpState ess e
    | Some (Phi (_, ids)) -> e, ess ///TODO
    | _ -> e, ess
  | Load (v, r, e) -> getPPoints cpState ess e
  | UnOp (_, _, Load _) as e -> e, ess
  | UnOp (op, rt, e) ->
    let e, ess = getPPoints cpState ess e
    UnOp (op, rt, e), ess
  | BinOp (_, _, Load _, _)
  | BinOp (_, _, _, Load _) as e -> e, ess
  | BinOp (op, rt, e1, e2) ->
    match op with
    | BinOpType.ADD ->
      let e1, ess =  getPPoints cpState ess e1
      let e2, ess = getPPoints cpState ess e2
      match e1, e2 with
      | Num v1, Num v2 ->
          let e3 = Num (v1.Add v2)
          BinOp (op, rt, e1, e2), ess
      | _ ->  BinOp (op, rt, e1, e2), ess
    | _ -> BinOp(op, rt, e1, e2), ess
  | RelOp (_, _, Load _, _)
  | RelOp (_, _, _, Load _) as e -> e, ess
  | RelOp (op, rt, e1, e2) ->
    let e1, ess = getPPoints cpState ess e1
    let e2, ess = getPPoints cpState ess e2
    RelOp (op, rt, e1, e2), ess
  | Ite (Load _, _, _, _)
  | Ite (_, _, Load _, _)
  | Ite (_, _, _, Load _) as e -> e, ess
  | Ite (e1, rt, e2, e3) ->
    let e1, ess = getPPoints cpState ess e1
    let e2, ess = getPPoints cpState ess e2
    let e3, ess = getPPoints cpState ess e3
    Ite (e1, rt, e2, e3), ess
  | Cast (op, rt, e) ->
    let e, ess = getPPoints cpState ess e
    Cast (op, rt, e), ess
  | Extract (Load _, _, _) as e -> e, ess
  | Extract (e, rt, pos) ->
    let e, ess = getPPoints cpState ess e
    Extract (e, rt, pos), ess
  | e -> e, ess



let tryResolveExprToBV cpState expr =
  match resolveExpr cpState true expr with
  | Num addr -> Some addr
  | _ -> None

let tryConvertBVToUInt32 bv =
  let bv = BitVector.Cast (bv, 256<rt>)
  let maxVal = BitVector.Cast (BitVector.MaxUInt32, 256<rt>)
  let isConvertible = BitVector.Le (bv, maxVal) |> BitVector.IsTrue
  if isConvertible then bv |> BitVector.ToUInt32 |> Some
  else None

let tryConvertBVToUInt64 bv =
  let bv = BitVector.Cast (bv, 256<rt>)
  let maxVal = BitVector.Cast (BitVector.MaxUInt64, 256<rt>)
  let isConvertible = BitVector.Le (bv, maxVal) |> BitVector.IsTrue
  if isConvertible then bv |> BitVector.ToUInt64 |> Some
  else None

let tryResolveExprToUInt32 cpState expr =
  match tryResolveExprToBV cpState expr with
  | Some addr -> addr |> tryConvertBVToUInt32
  | _ -> None

let tryResolveExprToUInt64 cpState expr =
  match tryResolveExprToBV cpState expr with
  | Some addr -> addr |> tryConvertBVToUInt64
  | _ -> None

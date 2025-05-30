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

namespace SuperCFG.BinGraph

[<AbstractClass>]
type DiGraph<'D, 'E when 'D :> VertexData and 'D : equality>
    (core: GraphCore<'D, 'E, DiGraph<'D, 'E>>) =
  inherit Graph<'D, 'E, DiGraph<'D, 'E>> ()

  override __.ImplementationType = core.ImplementationType

  override __.IsEmpty () = core.GetSize () = 0

  override __.GetSize () = core.GetSize ()

  override __.AddVertex data =
    let v, g = core.AddVertex __ data
    v, g

  override __.RemoveVertex vid =
    core.RemoveVertex __ vid

  override __.GetVertices () =
    core.Vertices

  override __.ExistsVertex vid =
    match core.TryFindVertexBy (fun v -> v.GetID () = vid) with
    | Some _ -> true
    | None -> false

  override __.FindVertexByID vid =
    core.FindVertexBy (fun v -> v.GetID () = vid)

  override __.TryFindVertexByID vid =
    core.TryFindVertexBy (fun v -> v.GetID () = vid)
    |> Option.bind (fun v -> v |> Some)

  override __.FindVertexByData data =
    core.FindVertexBy (fun v ->
      if v.IsDummy () then false else v.VData = data)

  override __.TryFindVertexByData data =
    core.TryFindVertexBy (fun v ->
      if v.IsDummy () then false else v.VData = data)
    |> Option.bind (fun v -> v  |> Some)

  override __.FindVertexBy fn =
    core.FindVertexBy fn

  override __.TryFindVertexBy fn =
    core.TryFindVertexBy fn |> Option.bind (fun v -> v |> Some)

  override __.AddEdge (srcid, dstid, e) =
    core.AddEdge __ srcid dstid e

  override __.RemoveEdge (srcid, dstid) =
    core.RemoveEdge __ srcid dstid

  override __.FindEdgeData (src, dst) =
    core.FindEdge src dst

  override __.TryFindEdgeData (src, dst) =
    core.TryFindEdge src dst

  override __.FoldVertex fn acc =
    core.FoldVertex fn acc

  override __.IterVertex fn =
    core.IterVertex fn

  override __.FoldEdge fn acc =
    core.FoldEdge fn acc

  override __.IterEdge fn =
    core.IterEdge fn

  override __.Clone () =
    core.InitGraph (Some core)

  override __.SubGraph vs =
    let g = core.InitGraph None
    (* Add vertices to new graph *)
    let g =
      vs |> Set.fold (fun (g: DiGraph<'D, 'E>) (v: Vertex<'D>) ->
        g.AddVertex v.VData |> snd) g
    (* Collect edges both ends are in vids *)
    let es =
      [] |> __.FoldEdge (fun acc src dst e ->
        if Set.contains src vs && Set.contains dst vs then
          (src, dst, e) :: acc
        else acc)
    (* Add edges to new graph *)
    List.fold (fun g (src: Vertex<_>, dst: Vertex<_>, e) ->
      let src = g.FindVertexByID <| src.GetID ()
      let dst = g.FindVertexByID <| dst.GetID ()
      g.AddEdge (src, dst, e)) g es

  override __.ToDOTStr (name, vToStrFn, _eToStrFn) =
    let inline strAppend (s: string) (sb: System.Text.StringBuilder) =
      sb.Append(s)
    let folder sb src dst _edata =
      strAppend (vToStrFn src) sb
      |> strAppend " -> "
      |> strAppend (vToStrFn dst)
      |> strAppend " [label=\""
      |> strAppend "\"];\n"
    let sb = System.Text.StringBuilder ()
    let sb = strAppend "digraph " sb |> strAppend name |> strAppend " {\n"
    let sb = __.FoldEdge folder sb
    sb.Append("}\n").ToString()

  /// A list of unreachable nodes. We always add nodes into this list first, and
  /// then later remove it from the list when adding edges.
  member __.Unreachables = core.Unreachables

  /// A list of exit nodes, which do not have any successors.
  member __.Exits = core.Exits

  member __.GetPreds vid = core.GetPreds vid

  member __.GetSuccs vid = core.GetSuccs vid

  member __.AddDummyVertex () =
    let v, g = core.AddDummyVertex __
    v, g

  member __.AddDummyEdge (srcid, dstid) =
    core.AddDummyEdge __ srcid dstid

  /// Return a new transposed (i.e., reversed) graph.
  member __.Reverse () =
    core.InitGraph None
    |> __.FoldVertex (fun g v ->
      if v.IsDummy () then g.AddDummyVertex () |> snd
      else g.AddVertex v.VData |> snd)
    |> __.FoldEdge (fun g src dst e ->
      let src = g.FindVertexByID <| src.GetID ()
      let dst = g.FindVertexByID <| dst.GetID ()
      g.AddEdge (dst, src, e))

  static member IsEmpty (g: DiGraph<'D, 'E>) =
    g.IsEmpty ()

  static member GetSize (g: DiGraph<'D, 'E>) =
    g.GetSize ()

  static member AddDummyVertex (g: DiGraph<'D, 'E>) =
    g.AddDummyVertex ()

  static member AddVertex (g: DiGraph<'D, 'E>, data) =
    g.AddVertex data

  static member RemoveVertex (g: DiGraph<'D, 'E>, v: Vertex<'D>)=
    g.RemoveVertex v

  static member GetPreds (g: DiGraph<'D, 'E>, v: Vertex<'D>) =
    g.GetPreds v

  static member GetSuccs (g: DiGraph<'D, 'E>, v: Vertex<'D>) =
    g.GetSuccs v

  static member GetUnreachables (g: DiGraph<'D, 'E>) =
    g.Unreachables

  static member GetExits (g: DiGraph<'D, 'E>) =
    g.Exits

  static member GetVertices (g: DiGraph<'D, 'E>) =
    g.GetVertices ()

  static member ExistsVertex (g: DiGraph<'D, 'E>, vid) =
    g.ExistsVertex vid

  static member FindVertexByID (g: DiGraph<'D, 'E>, vid) =
    g.FindVertexByID vid

  static member TryFindVertexByID (g: DiGraph<'D, 'E>, vid) =
    g.TryFindVertexByID vid

  static member FindVertexByData (g: DiGraph<'D, 'E>, data) =
    g.FindVertexByData data

  static member TryFindVertexByData (g: DiGraph<'D, 'E>, data) =
    g.TryFindVertexByData data

  static member FindVertexBy (g: DiGraph<'D, 'E>, fn) =
    g.FindVertexBy fn

  static member TryFindVertexBy (g: DiGraph<'D, 'E>, fn) =
    g.TryFindVertexBy fn

  static member AddDummyEdge (g: DiGraph<'D, 'E>, src, dst) =
    g.AddDummyEdge (src, dst)

  static member AddEdge (g: DiGraph<'D, 'E>, src, dst, e) =
    g.AddEdge (src, dst, e)

  static member RemoveEdge (g: DiGraph<'D, 'E>, src, dst) =
    g.RemoveEdge (src, dst)

  static member FindEdgeData (g: DiGraph<'D, 'E>, src, dst) =
    g.FindEdgeData (src, dst)

  static member TryFindEdgeData (g: DiGraph<'D, 'E>, src, dst) =
    g.TryFindEdgeData (src, dst)

  static member Clone (g: DiGraph<'D, 'E>) =
    g.Clone ()

  static member Reverse (g: DiGraph<'D, 'E>) =
    g.Reverse ()

  static member SubGraph (g: DiGraph<'D, 'E>, vs) =
    g.SubGraph vs

  static member ToDOTStr (g: DiGraph<'D, 'E>, name, vToStrfn, eToStrFn) =
    g.ToDOTStr (name, vToStrfn, eToStrFn)

// vim: set tw=80 sts=2 sw=2:

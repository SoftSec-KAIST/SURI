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

namespace SuperCFG.ControlFlowGraph

open SuperCFG.BinGraph
open SuperCFG.ControlFlowGraph

/// Disassembly-based CFG, where each node contains disassembly code.
type DisasmCFG = ControlFlowGraph<DisasmBasicBlock, CFGEdgeKind>

[<RequireQualifiedAccess>]
module DisasmCFG =
  let private initializer core =
    DisasmCFG (core) :> DiGraph<DisasmBasicBlock, CFGEdgeKind>

  let private initImperative () =
    ImperativeCore<DisasmBasicBlock, CFGEdgeKind> (initializer, UnknownEdge)
    |> DisasmCFG
    :> DiGraph<DisasmBasicBlock, CFGEdgeKind>

  let private initPersistent () =
    PersistentCore<DisasmBasicBlock, CFGEdgeKind> (initializer, UnknownEdge)
    |> DisasmCFG
    :> DiGraph<DisasmBasicBlock, CFGEdgeKind>

  /// Initialize IRCFG based on the implementation type.
  let init = function
    | ImperativeGraph -> initImperative ()
    | PersistentGraph -> initPersistent ()

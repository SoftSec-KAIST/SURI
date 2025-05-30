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

namespace SuperCFG.ControlFlowAnalysis

open System.Collections.Generic
open B2R2
open B2R2.FrontEnd
open B2R2.FrontEnd.BinFile
open B2R2.FrontEnd.BinFile.ELF

[<AutoOpen>]
module private DataManager =
  let parseRelocatableFunctionSymbols reloc =
    let dict = Dictionary ()
    let iter (KeyValue (addr, rel: RelocationEntry)) =
      match rel.RelType with
      | RelocationX86 RelocationX86.R_386_32
      | RelocationX86 RelocationX86.R_386_PC32
      | RelocationX64 RelocationX64.R_X86_64_PLT32 ->
        match rel.RelSymbol with
        | Some sym when sym.SymType = SymbolType.STT_FUNC ->
          dict.Add (addr, sym)
        | _ -> ()
      | _ -> ()
    reloc.RelocByAddr |> Seq.iter iter
    dict

  let parseRelocatableFuncs (hdl: BinHandle) =
    match hdl.File with
    | :? ELFBinFile as efi -> parseRelocatableFunctionSymbols efi.RelocationInfo
    | _ -> Dictionary ()

type FunDataManager () =

  let jmpTables = JumpTableMaintainer ()

  let visitedTbls = SortedSet<Addr> ()

  /// Return the JumpTableMaintainer.
  member __.JumpTables with get() = jmpTables

  member __.MarkVisitedTbl tblAddr =
    visitedTbls.Add tblAddr |> ignore

  member __.IsVisitedTbl tblAddr =
    visitedTbls.Contains tblAddr

type DataManager (hdl) =

  let funDataDict = Dictionary<Addr, FunDataManager> ()

  let relocatableFuncs = parseRelocatableFuncs hdl

  //let jmpTables = JumpTableMaintainer ()

  /// Return the JumpTableMaintainer.
  //member __.JumpTables with get() = jmpTables
  /// Return a map from a relocatable offset to its corresponding symbol. This
  /// map considers relocatable functions only.
  member __.RelocatableFuncs with get() = relocatableFuncs


  member __.GetOrAddFunDataMgr entry =
    match funDataDict.TryGetValue entry with
      | true, funCodeMgr -> funCodeMgr
      | _, _ ->
        let funDataMgr = FunDataManager()
        funDataDict[entry] <- funDataMgr
        funDataMgr
  member __.GetFunDataMgr entry =
    funDataDict[entry]

  member __.RemoveFunDataMgr (entry:Addr) =
    funDataDict.Remove entry

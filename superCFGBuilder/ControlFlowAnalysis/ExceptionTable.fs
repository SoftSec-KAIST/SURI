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

open B2R2
open B2R2.FrontEnd
open B2R2.FrontEnd.BinFile

module ELFExceptionTable =

  open B2R2.FrontEnd.BinFile.ELF

  let inline private loadCallSiteTable lsdaPointer lsdas =
    let lsda = Map.find lsdaPointer lsdas
    lsda.CallSiteTable

  /// If a landing pad has a direct branch to another function, then we consider
  /// the frame containing the lading pad as a non-function FDE.
  let private checkFDEIsFunction (lu: LiftingUnit) fde (landingPad: Addr) =
    match lu.ParseBBlock landingPad with
    | Ok (blk) ->
      let last = Array.last blk
      if last.IsCall () |> not then
        match last.DirectBranchTarget () with
        | true, jmpTarget -> fde.PCBegin <= jmpTarget && jmpTarget < fde.PCEnd
        | _ -> true
      else true
    | _ -> true

  let rec private loopCallSiteTable lu fde isFDEFunc acc = function
    | [] -> acc, isFDEFunc
    | csrec :: rest ->
      let blockStart = fde.PCBegin + csrec.Position
      let blockEnd = fde.PCBegin + csrec.Position + csrec.Length - 1UL
      let landingPad =
        if csrec.LandingPad = 0UL then 0UL else fde.PCBegin + csrec.LandingPad
      if landingPad = 0UL then loopCallSiteTable lu fde isFDEFunc acc rest
      else
        let acc = ARMap.add (AddrRange (blockStart, blockEnd)) landingPad acc
        let isFDEFunc = checkFDEIsFunction lu fde landingPad
        loopCallSiteTable lu fde isFDEFunc acc rest

  let private buildExceptionTable lu fde lsdas tbl =
    match fde.LSDAPointer with
    | None -> tbl, true
    | Some lsdaPointer ->
      loopCallSiteTable lu fde true tbl (loadCallSiteTable lsdaPointer lsdas)

  let private accumulateExceptionTableInfo acc lu fde lsdas =
    fde
    |> Array.fold (fun (exnTbl, fnEntryPoints, fdeRangeDicts) fde ->
       let exnTbl, isFDEFunction = buildExceptionTable lu fde lsdas exnTbl
       let fnEntryPoints =
        if isFDEFunction then Set.add fde.PCBegin fnEntryPoints
        else fnEntryPoints
       exnTbl, fnEntryPoints, Map.add fde.PCBegin fde.PCEnd fdeRangeDicts) acc

  let private computeExceptionTable lu excframes lsdas =
    excframes
    |> List.fold (fun acc frame ->
      accumulateExceptionTableInfo acc lu frame.FDERecord lsdas
    ) (ARMap.empty, Set.empty, Map.empty)

  let build lu (elf: ELFBinFile) =
    computeExceptionTable lu elf.ExceptionInfo.ExceptionFrames elf.ExceptionInfo.LSDAs

/// ExceptionTable holds parsed exception information of a binary code (given by
/// the BinHandle).
type ExceptionTable (hdl: BinHandle, lu) =
  let exnTbl, funcEntryPoints, fdeRangeDicts =
    match hdl.File.Format with
    | FileFormat.ELFBinary ->
      ELFExceptionTable.build lu (hdl.File :?> ELFBinFile)
    | _ -> ARMap.empty, Set.empty, Map.empty

  /// For a given instruction address, find the landing pad (exception target)
  /// of the instruction.
  member __.TryFindExceptionTarget insAddr =
    ARMap.tryFindByAddr insAddr exnTbl

  /// Return a set of function entry points that are visible from exception
  /// table information.
  member __.GetFunctionEntryPoints () =
    funcEntryPoints

  member __.GetFDERangeDicts () = fdeRangeDicts

  member __.GetNextFDEEntry addr =
    let entries = fdeRangeDicts.Keys |> Seq.filter(fun entry -> addr < entry )
    if entries |> Seq.isEmpty then None
    else entries |> Seq.min |> Some

  member __.GetPrevFDEEntry addr =
    let entries = fdeRangeDicts.Keys |> Seq.filter(fun entry -> addr > entry )
    if entries |> Seq.isEmpty then None
    else
      let candidate = entries |> Seq.max
      // if addr is larger than FDE End
      if addr > fdeRangeDicts[candidate] then
        Some fdeRangeDicts[candidate]
      else Some candidate

  member __.TryFindValidFDERange addr =
    fdeRangeDicts |> Seq.tryFind (fun (KeyValue(k,v)) -> k <= addr && addr < v)

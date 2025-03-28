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

namespace SuperCFG.BinEssence

open B2R2
open B2R2.FrontEnd
open B2R2.FrontEnd.BinFile
open SuperCFG.ControlFlowAnalysis

/// <summary>
///   BinEssence represents essential information about the binary at all
///   levels: a low-level interface for binary code and data, parsed
///   instructions, and recovered control-flow information including CFG itself.
///   Note that every field of BinEssence is *mutable*.
/// </summary>
type BinEssence = {
  /// Low-level access to binary code and data.
  BinHandle: BinHandle
  ISA: ISA
  LiftingUnit: LiftingUnit
  /// Higher-level access to the code. It handles parsed instructions, lifted
  /// IRs, basic blocks, functions, exception handlers, etc.
  CodeManager: CodeManager
  /// Higher-level access to the data.
  DataManager: DataManager
}

[<RequireQualifiedAccess>]
module BinEssence =

  /// Retrieve the IR-level CFG at the given address (addr) from the BinEssence.
  let getFunctionCFG ess (addr: Addr) =
    match ess.CodeManager.FunctionMaintainer.TryFindRegular addr with
    | Some func ->
      let root = func.FindVertex (ProgramPoint (addr, 0))
      Ok (func.IRCFG, root)
    | None -> Error ()

  let private getFunctionOperationMode (isa: ISA) entry =
    match isa.Arch with
    | Architecture.ARMv7 ->
      if entry &&& 1UL = 1UL then
        entry - 1UL, ArchOperationMode.ThumbMode
      else entry, ArchOperationMode.ARMMode
    | _ -> entry, ArchOperationMode.NoMode

  /// This function returns an initial sequence of entry points obtained from
  /// the binary itself (e.g., from its symbol information). Therefore, if the
  /// binary is stripped, the returned sequence will be incomplete, and we need
  /// to expand it during the other analyses.
  let private getInitialEntryPoints ess =
    let file = ess.BinHandle.File
    let entries =
      file.GetFunctionAddresses ()
      |> Set.ofSeq
      |> Set.union (ess.CodeManager.ExceptionTable.GetFunctionEntryPoints ())
      // Add all fde entries
      |> Set.union (ess.CodeManager.ExceptionTable.GetFDERangeDicts().Keys
                      |> Set.ofSeq )

    let entries =
      match file with
      | :? ELFBinFile as file ->
          file.RelocationInfo.RelocByAddr.Values
          |> Seq.filter
                 (fun reloc -> "R_X86_64_RELATIVE"
                                = (ELF.RelocationType.ToString reloc.RelType))
          |> Seq .filter (fun reloc -> (file: IBinFile).IsExecutableAddr reloc.RelAddend)
          |> Seq.fold (fun acc reloc -> Set.add reloc.RelAddend acc) entries
      | _ -> entries

    file.EntryPoint
    |> Option.fold (fun acc addr ->
      if file.Type = FileType.LibFile && addr = 0UL then acc
      else Set.add addr acc) entries
    |> Set.toList
    |> List.map (getFunctionOperationMode ess.ISA)

  let private initialize (hdl: BinHandle) isa =
    let lu = hdl.NewLiftingUnit ()
    { BinHandle = hdl
      ISA = isa
      LiftingUnit = lu
      CodeManager = CodeManager (hdl, isa, lu)
      DataManager = DataManager (hdl) }

  let private initialBuild ess (builder: CFGBuilder) =
    let entries = getInitialEntryPoints ess
    match builder.AddNewFunctions entries with
    | Ok () -> Ok ess
    | Error err -> Error err

  let private handlePluggableAnalysisResult ess name = function
    | PluggableAnalysisOk ->
      Ok ess
    | PluggableAnalysisError ->
      printfn "[*] %s failed." name
      Ok ess
    | PluggableAnalysisNewBinary hdl ->
      let ess = initialize hdl ess.ISA
      let builder = CFGBuilder (hdl, ess.ISA, ess.CodeManager, ess.DataManager)
      initialBuild ess builder

  let private runAnalyses builder analyses (ess: BinEssence) =
    analyses
    |> List.fold (fun ess (analysis: IPluggableAnalysis) ->
  #if DEBUG
      printfn "[*] %s started." analysis.Name
  #endif
      let ess =
        analysis.Run builder ess.BinHandle ess.CodeManager ess.DataManager
        |> handlePluggableAnalysisResult ess analysis.Name
      match ess with
      | Ok ess -> ess
      | Error e ->
        eprintfn "[*] Fatal error with %s" (CFGError.toString e)
        Utils.impossible ()) ess

  let private analyzeAll preAnalyses mainAnalyses postAnalyses builder ess =
    ess
    |> runAnalyses builder preAnalyses
    |> runAnalyses builder mainAnalyses
    |> runAnalyses builder postAnalyses

  [<CompiledName("Init")>]
  let init hdl isa preAnalyses mainAnalyses postAnalyses =
#if DEBUG
    let startTime = System.DateTime.Now
#endif
    let ess = initialize hdl isa
    let builder = CFGBuilder (hdl, ess.ISA, ess.CodeManager, ess.DataManager)
    match initialBuild ess builder with
    | Ok ess ->
      let ess = ess |> analyzeAll preAnalyses mainAnalyses postAnalyses builder
#if DEBUG
      let endTime = System.DateTime.Now
      endTime.Subtract(startTime).TotalSeconds
      |> printfn "[*] All done in %f sec."
#endif
      ess
    | Error e ->
      eprintfn "[*] Fatal error with %s" (CFGError.toString e)
      Utils.impossible ()

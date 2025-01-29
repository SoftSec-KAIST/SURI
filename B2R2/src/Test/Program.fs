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

open System.Collections.Generic
open B2R2
open B2R2.FrontEnd.BinInterface
open B2R2.FrontEnd.BinLifter
open B2R2.FrontEnd.BinLifter.Intel
open B2R2.MiddleEnd.BinEssence
open System.IO
#if DEBUG_META_FILE
open System.Text.Json
#else
open Newtonsoft.Json
#endif
open SupersetCFG.MetaGen
open SupersetCFG.ASanGen

type SupersetRecord = {
  FunDict: IDictionary<string, FnInfo>
  PLTDict: IDictionary<string, string>
  FalseFunList: string list
  SuspiciousFunList: string list
}

let ConstructCFG ess hdl =
#if DEBUG
    let startTime = System.DateTime.Now
#endif
    let fnList = MetaGen ess hdl
#if DEBUG
    let endTime = System.DateTime.Now
    endTime.Subtract(startTime).TotalSeconds
      |> printfn "[*] Construct CFG %f sec."
#endif
    fnList

let CreateASanMeta ess hdl =
#if DEBUG
    let startTime = System.DateTime.Now
#endif
    let fnList = ASanMetaGen ess hdl
#if DEBUG
    let endTime = System.DateTime.Now
    endTime.Subtract(startTime).TotalSeconds
      |> printfn "[*] Construct CFG %f sec."
#endif
    fnList

let MakeB2R2Meta ess (fnList: FnInfo list) =
#if DEBUG
    let startTime = System.DateTime.Now
#endif
    let falseFnList =
      ess.CodeManager.FalseFunSet
      |> Seq.distinct |> Seq.map(fun x-> $"0x%x{x}") |> List.ofSeq

    let suspiciousFnList =
      ess.CodeManager.SuspiciousFunSet
      |> Seq.distinct |> Seq.map(fun x-> $"0x%x{x}") |> List.ofSeq
      |> List.filter (fun entry -> not <| List.contains entry falseFnList)

    let fnDict = fnList |> Seq.map (fun funInfo -> funInfo.Addr, funInfo )
                        |> dict
    let pltDict = ess.CodeManager.FunctionMaintainer.PLTFunctions
                      |> Seq.map(fun (KeyValue(k, v)) -> ( $"0x%x{k}"), v)
                      |> dict
    let superSetRec = {FunDict = fnDict; PLTDict=pltDict
                       FalseFunList=falseFnList
                       SuspiciousFunList = suspiciousFnList}
#if DEBUG
    let endTime = System.DateTime.Now
    endTime.Subtract(startTime).TotalSeconds
      |> printfn "[*] Extract data %f sec."
#endif
    superSetRec

let MakeBioAsanMeta fnList =
    let fnDict = fnList |> Seq.map (fun funInfo -> funInfo.Addr, funInfo )
                        |> dict
    fnDict

let SaveJSON fileName data =
#if DEBUG
    let startTime = System.DateTime.Now
#endif

#if DEBUG_META_FILE
    let mutable options = JsonSerializerOptions()
    options.WriteIndented <- true
    let serialized_data = JsonSerializer.Serialize (data, options)
    File.WriteAllText(fileName, serialized_data);
#else
    let fileStream = new StreamWriter(fileName: string)
    let serializer = new JsonSerializer()
    serializer.Serialize(fileStream, data)
    fileStream.Close()
#endif

#if DEBUG
    let endTime = System.DateTime.Now
    endTime.Subtract(startTime).TotalSeconds
      |> printfn "[*] JsonSerializer %f sec."
#endif

[<EntryPoint>]
let main args =
  let path =  Path.Combine(Path.GetTempPath(), args[0])
  if File.Exists(path) then
    let hdl = BinHandle.Init(ISA.DefaultISA, fileName = args[0])
    let fileName = args[1]
    let ess = BinEssence.init hdl [] [] []
    if args.Length = 2 then
      let fnList = ConstructCFG ess hdl
      let data = MakeB2R2Meta ess fnList
      SaveJSON fileName data
    elif args.Length > 2 && args[2] = "att" then
      Disasm.setDisassemblyFlavor ATTSyntax
      let fnList = ConstructCFG ess hdl
      let data = MakeB2R2Meta ess fnList
      SaveJSON fileName data
    elif args.Length > 2 && args[2] = "asan" then
      let fnList = CreateASanMeta ess hdl
      SaveJSON fileName fnList
    0
  else 1

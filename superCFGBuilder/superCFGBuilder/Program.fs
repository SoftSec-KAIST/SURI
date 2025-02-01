module SupersetCFG.Main

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
  let path =  args[0]
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

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

namespace B2R2.FrontEnd.BinFile

open System
open System.Runtime.InteropServices
open B2R2

/// BinFile describes a binary file in a format-agnostic way.
[<AbstractClass>]
type BinFile () =
  /// <summary>
  ///   Raw byte values as a `ByteSpan`.
  /// </summary>
  abstract Span: ByteSpan

  /// <summary>
  ///   The format of this file: ELF, PE, Mach-O, or etc.
  /// </summary>
  abstract FileFormat: FileFormat

  /// <summary>
  ///   The ISA that this file expects to run on.
  /// </summary>
  abstract ISA: ISA

  /// <summary>
  ///   What kind of binary is this?
  /// </summary>
  abstract FileType: FileType

  /// <summary>
  ///   The file path where this file is located.
  /// </summary>
  abstract FilePath: string

  /// <summary>
  ///   Word size of the CPU that this binary can run on.
  /// </summary>
  abstract WordSize: WordSize

  /// <summary>
  ///   Is this binary stripped?
  /// </summary>
  abstract IsStripped: bool

  /// <summary>
  ///   Is NX enabled for this binary? (DEP enabled or not)
  /// </summary>
  abstract IsNXEnabled: bool

  /// <summary>
  ///   Is this binary relocatable (position-independent)?
  /// </summary>
  abstract IsRelocatable: bool

  /// <summary>
  ///   The base address of this binary at which this binary is prefered to be
  ///   loaded in memory.
  /// </summary>
  abstract BaseAddress: Addr

  /// <summary>
  ///   The entry point of this binary (the start address that this binary runs
  ///   at). Note that some binaries (e.g., PE DLL files) do not have a specific
  ///   entry point, and EntryPoint will return None in such a case.
  /// </summary>
  abstract EntryPoint: Addr option

  /// <summary>
  ///   The beginning of the text section of this binary.
  /// </summary>
  abstract TextStartAddr: Addr

  /// <summary>
  ///   Translate a virtual address into a relative offset to this binary.
  /// </summary>
  /// <param name="addr">Virtual address.</param>
  /// <returns>
  ///   Returns an offset to this binary for a given virtual address.
  /// </returns>
  /// <exception cref="T:B2R2.FrontEnd.BinFile.InvalidAddrReadException">
  ///   Thrown when the given address is out of a valid address range.
  /// </exception>
  abstract member TranslateAddress: addr: Addr -> int

  /// <summary>
  ///   Return a relocated address of the given virtual address if there is a
  ///   corresponding relocation entry.
  /// </summary>
  /// <param name="addr">Virtual address be relocated.</param>
  /// <returns>
  ///   Returns a relocated address for a given virtual address.
  /// </returns>
  abstract member GetRelocatedAddr: relocAddr: Addr -> Result<Addr, ErrorCase>

  /// <summary>
   ///   Add a symbol for the address. This function is useful when we can
   ///   obtain extra symbol information from outside of B2R2.
   /// </summary>
   /// <returns>
   ///   Does not return a value.
   /// </returns>
   abstract member AddSymbol: Addr -> Symbol -> unit

  /// <summary>
  ///   Return a list of all the symbols from the binary.
  /// </summary>
  /// <returns>
  ///   A sequence of symbols.
  /// </returns>
  abstract member GetSymbols: unit -> seq<Symbol>

  /// <summary>
  ///   Return a list of all the static symbols from the binary. Static symbols
  ///   can be removed when we strip the binary. Unlike dynamic symbols, static
  ///   symbols are not required to run the binary, thus they can be safely
  ///   removed before releasing it.
  /// </summary>
  /// <returns>
  ///   A sequence of static symbols.
  /// </returns>
  abstract member GetStaticSymbols: unit -> seq<Symbol>

  /// <summary>
  ///   Return a list of all the dynamic symbols from the binary. Dynamic
  ///   symbols are the ones that are required to run the binary. The
  ///   "excludeImported" argument indicates whether to exclude external symbols
  ///   that are imported from other files. However, even if "excludeImported"
  ///   is true, returned symbols may include a forwarding entry that redirects
  ///   to another function in an external file (cf. SymbolKind.ForwardType).
  ///   When "excludeImported" argument is not given, this function will simply
  ///   return all possible dynamic symbols.
  /// </summary>
  /// <returns>
  ///   A sequence of dynamic symbols.
  /// </returns>
  abstract member GetDynamicSymbols: ?excludeImported: bool -> seq<Symbol>

  /// <summary>
  ///   Return a list of all relocation symbols from the binary.
  /// </summary>
  /// <returns>
  ///   A sequence of relocation symbols.
  /// </returns>
  abstract member GetRelocationSymbols: unit -> seq<Symbol>

  /// <summary>
  ///   Return a list of all the sections from the binary.
  /// </summary>
  /// <returns>
  ///   A sequence of sections.
  /// </returns>
  abstract member GetSections: unit -> seq<Section>

  /// <summary>
  ///   Return a section that contains the given address.
  /// </summary>
  /// <param name="addr">The address that belongs to a section.</param>
  /// <returns>
  ///   A sequence of sections. This function returns a singleton if there
  ///   exists a corresponding section. Otherwise, it returns an empty sequence.
  /// </returns>
  abstract member GetSections: addr: Addr -> seq<Section>

  /// <summary>
  ///   Return a section that has the specified name.
  /// </summary>
  /// <param name="name">The name of the section.</param>
  /// <returns>
  ///   A sequence of sections that have the specified name. This function
  ///   returns an empty sequence if there is no section of the given name.
  /// </returns>
  abstract member GetSections: name: string -> seq<Section>

  /// <summary>
  ///   Return a sequence text sections.
  /// </summary>
  /// <returns>
  ///   A sequence of text sections.
  /// </returns>
  abstract member GetTextSections: unit -> seq<Section>

  /// <summary>
  ///   Return a list of segments from the binary. If the isLoadable parameter
  ///   is true, it will only return a list of "loadable" segments. Otherwise,
  ///   it will return all possible segments. By default, this function returns
  ///   only loadable segments, e.g., PT_LOAD segment of ELF.
  /// </summary>
  /// <returns>
  ///   A sequence of segments.
  /// </returns>
  abstract member GetSegments:
    [<Optional; DefaultParameterValue(true)>] isLoadable:bool
    -> seq<Segment>

  /// <summary>
  ///   Return a list of the segments from the binary, which contain the given
  ///   address.
  /// </summary>
  /// <param name="addr">The address that belongs to segments.</param>
  /// <returns>
  ///   A sequence of segments.
  /// </returns>
  member __.GetSegments (addr: Addr) =
    __.GetSegments ()
    |> Seq.filter (fun s -> (addr >= s.Address) && (addr < s.Address + s.Size))

  /// <summary>
  ///   For a given permission, return a list of segments that satisfy the
  ///   permission. For a given "READ-only" permission, this function may return
  ///   a segment whose permission is "READABLE and WRITABLE", as an instance.
  /// </summary>
  /// <returns>
  ///   A sequence of segments.
  /// </returns>
  member __.GetSegments (perm: Permission) =
    __.GetSegments ()
    |> Seq.filter (fun s -> (s.Permission &&& perm = perm) && s.Size > 0UL)

  /// <summary>
  ///   Return a list of all the linkage table entries from the binary.
  /// </summary>
  /// <returns>
  ///   A sequence of linkage table entries, e.g., PLT entries for ELF files.
  /// </returns>
  abstract member GetLinkageTableEntries: unit -> seq<LinkageTableEntry>

  /// <summary>
  ///   Return if a given address is an address of a linkage table entry.
  /// </summary>
  /// <returns>
  ///   True if the address is a linkage table address, false otherwise.
  /// </returns>
  abstract member IsLinkageTable: Addr -> bool

  /// <summary>
  ///   Find the symbol name for a given address.
  /// </summary>
  /// <returns>
  ///   Returns a symbol as an Ok value if a symbol exists, otherwise returns
  ///   an Error value.
  /// </returns>
  abstract member TryFindFunctionSymbolName: Addr -> Result<string, ErrorCase>

  /// <summary>
  ///   Convert the section at the address (Addr) into a binary pointer, which
  ///   can exclusively point to binary contents of the section.
  /// </summary>
  abstract member ToBinaryPointer: Addr -> BinaryPointer

  /// <summary>
  ///   Convert the section of the name (string) into a binary pointer, which
  ///   can exclusively point to binary contents of the section.
  /// </summary>
  abstract member ToBinaryPointer: string -> BinaryPointer

  /// <summary>
  ///   Check if the given address is valid for this binary. We say a given
  ///   address is valid for the binary if the address is within the range of
  ///   statically computable segment ranges.
  /// </summary>
  /// <returns>
  ///   Returns true if the address is within a valid range, false otherwise.
  /// </returns>
  abstract member IsValidAddr: Addr -> bool

  /// <summary>
  ///   Check if the given address range is valid. This function returns true
  ///   only if the whole range of the addressess are valid (for every address
  ///   in the range, IsValidAddr should return true).
  /// </summary>
  /// <returns>
  ///   Returns true if the whole range of addresses is within a valid range,
  ///   false otherwise.
  /// </returns>
  abstract member IsValidRange: AddrRange -> bool

  /// <summary>
  ///   Check if the given address is valid and there is an actual mapping from
  ///   the binary file to the corresponding memory. Unlike IsValidAddr, this
  ///   function checks if we can decide the actual value of the given address
  ///   from the binary. For example, a program header of an ELF file may
  ///   contain 100 bytes in size, but when it is mapped to a segment in memory,
  ///   the size of the segment can be larger than the size of the program
  ///   header. This function checks if the given address is in the range of the
  ///   segment that has a direct mapping to the file's program header.
  /// </summary>
  /// <returns>
  ///   Returns true if the address is within a mapped address range, false
  ///   otherwise.
  /// </returns>
  abstract member IsInFileAddr: Addr -> bool

  /// <summary>
  ///   Check if the given address range is valid and there exists a
  ///   corresponding region in the actual binary file. This function returns
  ///   true only if the whole range of the addressess are valid (for every
  ///   address in the range, IsInFileAddr should return true).
  /// </summary>
  /// <returns>
  ///   Returns true if the whole range of addresses is within a valid range,
  ///   false otherwise.
  /// </returns>
  abstract member IsInFileRange: AddrRange -> bool

  /// <summary>
  ///   Check if the given address is executable address for this binary. We say
  ///   a given address is executable if the address is within an executable
  ///   segment. Note we consider the addresses of known read-only sections
  ///   (such as .rodata) as non-executable, even though those sections are
  ///   within an executable segment. For object files, we simply consider a
  ///   .text section's address range as executable.
  /// </summary>
  /// <returns>
  ///   Returns true if the address is executable, false otherwise.
  /// </returns>
  abstract member IsExecutableAddr: Addr -> bool

  /// <summary>
  ///   Check if the given address is rodata address for this binary.
  /// </summary>
  /// <returns>
  ///   Returns true if the address is in rodata section, false otherwise.
  /// </returns>
  abstract member IsRodataAddr: Addr -> bool

  /// <summary>
  ///   Given a range r, return a list of address ranges (intervals) that are
  ///   within r, and that are not in-file.
  /// </summary>
  /// <returns>
  ///   Returns an empty list when the given range r is valid, i.e.,
  ///   `IsInFileRange r = true`.
  /// </returns>
  abstract member GetNotInFileIntervals: AddrRange -> seq<AddrRange>

  /// <summary>
  ///   Returns a sequence of local function symbols (excluding external
  ///   functions) from a given BinFile.
  /// </summary>
  /// <returns>
  ///   A sequence of function symbols.
  /// </returns>
  member __.GetFunctionSymbols () =
    let dict = Collections.Generic.Dictionary<Addr, Symbol> ()
    __.GetStaticSymbols ()
    |> Seq.iter (fun s ->
      if s.Kind = SymFunctionType then dict[s.Address] <- s
      elif s.Kind = SymNoType (* This is to handle ppc's PLT symbols. *)
        && s.Address > 0UL && s.Name.Contains "pic32."
      then dict[s.Address] <- s
      else ())
    __.GetDynamicSymbols (true) |> Seq.iter (fun s ->
      if dict.ContainsKey s.Address then ()
      elif s.Kind = SymFunctionType then dict[s.Address] <- s
      else ())
    dict.Values

  /// <summary>
  ///   Returns a sequence of local function addresses (excluding external
  ///   functions) from a given BinFile. This function only considers addresses
  ///   that are certain.
  /// </summary>
  /// <returns>
  ///   A sequence of function addresses.
  /// </returns>
  abstract member GetFunctionAddresses: unit -> seq<Addr>

  default __.GetFunctionAddresses () =
    __.GetFunctionSymbols ()
    |> Seq.map (fun s -> s.Address)

  /// <summary>
  ///   Returns a sequence of local function addresses (excluding external
  ///   functions) from a given BinFile. If the argument is true, then this
  ///   funciton utilizes exception information of the binary to infer function
  ///   entries. Note that the inference process is not necessarily precise, so
  ///   this is really just an experimental feature, and will be removed in the
  ///   future.
  /// </summary>
  /// <returns>
  ///   A sequence of function addresses.
  /// </returns>
  abstract member GetFunctionAddresses: bool -> seq<Addr>

  default __.GetFunctionAddresses (_) =
    __.GetFunctionSymbols ()
    |> Seq.map (fun s -> s.Address)

  /// <summary>
  ///   Return a new BinFile by replacing the content with the given byte array,
  ///   assuming the file format, ISA, and its file path do not change. The new
  ///   byte array is placed at the same base address as the original one. This
  ///   function does not directly affect the corresponding file in the file
  ///   system, though.
  /// </summary>
  /// <return>
  ///   A newly generated BinFile.
  /// </return>
  abstract member NewBinFile: byte[] -> BinFile

  /// <summary>
  ///   Return a new BinFile by replacing the content with the given byte array,
  ///   assuming the file format, ISA, and its file path do not change. The new
  ///   byte array is placed at the given base address (baseAddr). This function
  ///   does not directly affect the corresponding file in the file system,
  ///   though.
  /// </summary>
  /// <return>
  ///   A newly generated BinFile.
  /// </return>
  abstract member NewBinFile: byte[] * baseAddr: Addr -> BinFile

  /// <summary>
  ///   Get a sequence of executable sections including linkage table code
  ///   sections such as PLT.
  /// </summary>
  /// <returns>
  ///   A sequence of executable sections.
  /// </returns>
  member __.GetExecutableSections () =
    __.GetSections ()
    |> Seq.filter (fun s -> (s.Kind = SectionKind.ExecutableSection)
                         || (s.Kind = SectionKind.LinkageTableSection))

  /// <summary>
  ///   Convert <see cref="T:B2R2.FrontEnd.BinFile.FileType">FileType</see> to
  ///   string.
  /// </summary>
  /// <param name="ty">A FileType to convert.</param>
  /// <returns>
  ///   A converted string.
  /// </returns>
  static member FileTypeToString (ty) =
    match ty with
    | FileType.ExecutableFile -> "Executable"
    | FileType.CoreFile -> "Core dump"
    | FileType.LibFile -> "Library"
    | FileType.ObjFile -> "Object"
    | _ -> "Unknown"

  /// <summary>
  ///   Convert from permission to string.
  /// </summary>
  /// <param name="p">A permission to convert.</param>
  /// <returns>
  ///   A converted string.
  /// </returns>
  static member PermissionToString (p: Permission) =
    let r =
      if p &&& Permission.Readable = LanguagePrimitives.EnumOfValue 0 then ""
      else "R"
    let w =
      if p &&& Permission.Writable = LanguagePrimitives.EnumOfValue 0 then ""
      else "W"
    let x =
      if p &&& Permission.Executable = LanguagePrimitives.EnumOfValue 0 then ""
      else "X"
    r + w + x

  /// <summary>
  ///   Convert from entrypoint information to string.
  /// </summary>
  /// <param name="entryPoint">Entry point of a given binary.</param>
  /// <returns>
  ///   A converted string.
  /// </returns>
  static member EntryPointToString (entryPoint: Addr option) =
    match entryPoint with
    | None -> "none"
    | Some entry -> sprintf "0x%x" entry

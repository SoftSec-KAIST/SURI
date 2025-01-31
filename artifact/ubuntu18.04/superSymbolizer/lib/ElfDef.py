import enum
from collections import namedtuple
from ctypes import Structure, c_char, c_uint16, c_uint32, c_uint64, c_int64, c_uint8, string_at, byref, sizeof, \
    create_string_buffer, cast, pointer, POINTER


class ELFHeader(Structure):
    _fields_ = [
        ('e_ident', c_char * 16),  # 0x10
        ('e_type', c_uint16),  # 0x12
        ('e_machine', c_uint16),  # 0x14
        ('e_version', c_uint32),  # 0x18
        ('e_entry', c_uint64),  # 0x20
        ('e_phoff', c_uint64),  # 0x28
        ('e_shoff', c_uint64),  # 0x30
        ('e_flags', c_uint32),  # 0x34
        ('e_ehsize', c_uint16),  # 0x36
        ('e_phentsize', c_uint16),  # 0x38
        ('e_phnum', c_uint16),  # 0x3A
        ('e_shentsize', c_uint16),  # 0x3C
        ('e_shnum', c_uint16),  # 0x3E
        ('e_shstrndx', c_uint16),  # 0x40
    ]


class SectionHeader(Structure):
    _fields_ = [
        ('sh_name', c_uint32),  # 0x04
        ('sh_type', c_uint32),  # 0x08
        ('sh_flags', c_uint64),  # 0x10
        ('sh_addr', c_uint64),  # 0x18
        ('sh_offset', c_uint64),  # 0x20
        ('sh_size', c_uint64),  # 0x28
        ('sh_link', c_uint32),  # 0x2C
        ('sh_info', c_uint32),  # 0x30
        ('sh_addralign', c_int64),  # 0x38
        ('sh_entsize', c_int64),  # 0x40
    ]


class ProgramHeader(Structure):
    _fields_ = [
        ('p_type', c_uint32),  # 0x04
        ('p_flags', c_uint32),  # 0x08
        ('p_offset', c_uint64),  # 0x10
        ('p_vaddr', c_uint64),  # 0x18
        ('p_paddr', c_uint64),  # 0x20
        ('p_filesz', c_uint64),  # 0x28
        ('p_memsz', c_uint64),  # 0x30
        ('p_align', c_uint64),  # 0x38
    ]


class Elf64_Sym(Structure):
    _fields_ = [
        ('st_name', c_uint32),  # 0x04
        ('st_info', c_uint8),  # 0x05
        ('st_other', c_uint8),  # 0x06
        ('st_shndx', c_uint16),  # 0x08
        ('st_value', c_uint64),  # 0x10
        ('st_size', c_uint64),  # 0x18
    ]


class Elf64_Rel(Structure):
    _fields_ = [
        ('r_offset', c_uint64),  # 0x08
        ('r_info', c_uint64),  # 0x10
    ]


class Elf64_Rela(Structure):
    _fields_ = [
        ('r_offset', c_uint64),  # 0x08
        ('r_info', c_uint64),  # 0x10
        ('r_addend', c_uint64),  # 0x18
    ]


class Elf64_Dyn(Structure):
    _fields_ = [
        ('d_tag', c_uint64),    #0x8
        ('d_un', c_uint64),     #0x10
    ]


class Elf64_Verneed(Structure):
    _fields_ = [
        ('vn_version', c_uint16), #0x2
        ('vn_cnt', c_uint16),   #0x4
        ('vn_file', c_uint32),  #0x8
        ('vn_aux', c_uint32),   #0xc
        ('vn_next', c_uint32),  #0x10
    ]


class Elf64_Vernaux(Structure):
    _fields_ = [
        ('vna_hash', c_uint32), #0x4
        ('vna_flags', c_uint16),    #0x6
        ('vna_other', c_uint16),    #0x8
        ('vna_name', c_uint32), #0xc
        ('vna_next', c_uint32), #0x10
    ]


class Elf64_VernIdx(Structure):
    _fields_ = [
        ('idx', c_uint16), #0x2
    ]

class Elf64_Addr(Structure):
    _fields_ = [
        ('addr', c_uint64), #0x2
    ]

class SectionType (enum.IntEnum):
    SHT_NULL = 0
    SHT_PROGBITS = 1
    SHT_SYMTAB = 2
    SHT_STRTAB = 3
    SHT_RELA = 4
    SHT_HASH = 5
    SHT_DYNAMIC = 6
    SHT_NOTE = 7
    SHT_NOBITS = 8
    SHT_REL = 9
    SHT_SHLIB = 10
    SHT_DYNSYM = 11
    SHT_GNU_verneed = 0x6FFFFFFE
    SHT_GNU_versym = 0x6FFFFFFF


class SectionFlag(enum.IntEnum):
    SHF_WRITE = 1
    SHF_ALLOC = 2
    SHF_EXECINSTR = 4
    SHF_MASKPROC = 0xf0000000


class ProgramFlag(enum.IntEnum):
    PF_X = 1
    PF_W = 2
    PF_R = 4
    PF_MASKPROC = 0xf0000000


class ProgramType(enum.IntEnum):
    PT_NULL = 0
    PT_LOAD = 1
    PT_DYNAMIC = 2
    PT_INTERP = 3
    PT_NOTE = 4
    PT_SHLIB = 5
    PT_PHDR = 6
    PT_TLS = 7
    PT_NUM = 8
    PT_LOOS = 0x60000000
    PT_GNU_EH_FRAME = 0x6474E550
    PT_GNU_STACK = 0x6474E551
    PT_GNU_RELRO = 0x6474E552
    PT_GNU_PROPERTY = 0x6474E553
    PT_LOSUNW = 0x6FFFFFFA
    PT_SUNWBSS = 0x6FFFFFFA
    PT_SUNWSTACK = 0x6FFFFFFB
    PT_HISUNW = 0x6FFFFFFF
    PT_HIOS = 0x6FFFFFFF
    PT_LOPROC = 0x70000000
    PT_HIPROC = 0x7FFFFFFF
    PT_MIPS_REGINFO = 0x70000000
    PT_MIPS_RTPROC = 0x70000001
    PT_MIPS_OPTIONS = 0x70000002
    PT_MIPS_ABIFLAGS = 0x70000003
    PT_PARISC_ARCHEXT = 0x70000000
    PT_PARISC_UNWIND = 0x70000001


class SymbolType(enum.IntEnum):
    STT_NOTYPE = 0x0
    STT_OBJECT = 0x1
    STT_FUNC = 0x2
    STT_SECTION = 0x3
    STT_FILE = 0x4
    STT_COMMON = 0x5
    STT_TLS = 0x6
    STT_NUM = 0x7
    STT_LOOS = 0xA
    STT_GNU_IFUNC = 0xA
    STT_HIOS = 0xC
    STT_LOPROC = 0xD
    STT_HIPROC = 0xF
    STT_SPARC_REGISTER = 0xD
    STT_PARISC_MILLICODE = 0xD


class DynamicArrayTag(enum.IntEnum):
    DT_NULL = 0
    DT_NEEDED = 1
    DT_PLTRELSZ = 2
    DT_PLTGOT = 3
    DT_HASH = 4
    DT_STRTAB = 5
    DT_SYMTAB = 6
    DT_RELA = 7
    DT_RELASZ = 8
    DT_RELAENT = 9
    DT_STRSZ = 10
    DT_SYMENT = 11
    DT_INIT = 12
    DT_FINI = 13
    DT_SONAME = 14
    DT_RPATH = 15
    DT_SYMBOLIC = 16
    DT_REL = 17
    DT_RELSZ = 18
    DT_RELENT = 19
    DT_PLTREL = 20
    DT_DEBUG = 21
    DT_TEXTREL = 22
    DT_JMPREL = 23
    DT_BIND_NOW = 24
    DT_INIT_ARRAY = 25
    DT_FINI_ARRAY = 26
    DT_INIT_ARRAYSZ = 27
    DT_FINI_ARRAYSZ = 28
    DT_RUNPATH = 29
    DT_FLAGS = 30
    DT_ENCODING = 32
    DT_PREINIT_ARRAY = 32
    DT_PREINIT_ARRAYSZ = 33
    DT_LOOS = 0x6000000D
    DT_HIOS = 0x6ffff000
    DT_VERSYM = 0x6ffffff0
    DT_GNU_HASH = 0x6ffffef5
    DT_VERDEF = 0x6ffffffc
    DT_VERDEFNUM = 0x6ffffffd
    DT_VERNEED = 0x6ffffffe
    DT_VERNEEDNUM = 0x6fffffff
    DT_LOPROC = 0x70000000
    DT_HIPROC = 0x7fffffff


class RelocationType(enum.IntEnum):
    R_X86_64_NONE = 0
    R_X86_64_64 = 1
    R_X86_64_PC32 = 2
    R_X86_64_GOT32 = 3
    R_X86_64_PLT32 = 4
    R_X86_64_COPY = 5
    R_X86_64_GLOB_DAT = 6
    R_X86_64_JUMP_SLOT = 7
    R_X86_64_RELATIVE = 8
    R_X86_64_GOTPCREL = 9
    R_X86_64_32 = 10
    R_X86_64_32S = 11
    R_X86_64_16 = 12
    R_X86_64_PC16 = 13
    R_X86_64_8 = 14
    R_X86_64_PC8 = 15
    R_X86_64_NUM = 16


def Pack(ctype_instance):
    buf = string_at(byref(ctype_instance), sizeof(ctype_instance))
    return buf


def Unpack(ctype, buf):
    cstring = create_string_buffer(buf)
    ctype_instance = cast(pointer(cstring), POINTER(ctype)).contents
    return ctype_instance


SectionBrick = namedtuple('SectionBrick', ['name', 'OffsetRange', 'AddrRange', 'header', 'body'])
VersionBrick = namedtuple('VersionBrick', ['lib_name', 'ver_str', 'header', 'entry'])

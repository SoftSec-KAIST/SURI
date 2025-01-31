from collections import namedtuple
import re
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.elf.relocation import RelocationSection
from elftools.elf.enums import ENUM_RELOC_TYPE_x64
from enum import Enum
import os


class EParser:
    def __init__(self, filename):
        self.entry = None
        self.plt_dict = {}
        self.reloc_dict = {}
        self.fun_dict = {}
        with open(filename, 'rb') as f:

            elffile = ELFFile(f)
            self.entry = elffile.header['e_entry']

            # get R_X86_64_JUMP_SLOT info
            self.plt_ranges = []
            for sec in elffile.iter_sections():
                if isinstance(sec, RelocationSection):
                    symtab = elffile.get_section(sec['sh_link'])
                    self.examine_reloc(elffile, sec, symtab)
                if sec.name in ['.plt']:
                    self.plt_ranges.append(range(sec.header['sh_offset'], sec.header['sh_offset'] + sec.header['sh_size']))

            for sec in elffile.iter_sections():
                if isinstance(sec, SymbolTableSection):
                    self.examine_sym_tab(sec)

    def examine_reloc(self, elffile, section, symtab):

        for rel in section.iter_relocations():
            if rel['r_info_sym'] == 0:
                continue

            symbol = symtab.get_symbol(rel['r_info_sym'])

            if symbol['st_name'] == 0:
                symsec = elffile.get_section(symbol['st_shndx'])
                symbol_name = symsec.name
            else:
                symbol_name = symbol.name

            if rel['r_info_type'] == ENUM_RELOC_TYPE_x64['R_X86_64_JUMP_SLOT']:
                # register plt dictionary
                if 'R_X86_64_JUMP_SLOT' not in self.reloc_dict:
                    self.reloc_dict['R_X86_64_JUMP_SLOT'] = dict()
                offset = rel['r_offset']
                append = rel['r_addend']
                assert append == 0, 'Wierd!!!'
                self.reloc_dict['R_X86_64_JUMP_SLOT'][offset] = (symbol_name)
            '''
            # Code generator should handle following relocation
            elif rel['r_info_type'] == ENUM_RELOC_TYPE_x64['R_X86_64_64']:

                assert False, 'TODO'
            elif rel['r_info_type'] == ENUM_RELOC_TYPE_x64['R_X86_64_COPY']:
                continue
            elif rel['r_info_type'] == ENUM_RELOC_TYPE_x64['R_X86_64_GLOB_DAT']:
                assert False, 'TODO'
            elif rel['r_info_type'] == ENUM_RELOC_TYPE_x64['R_X86_64_RELATIVE']:
                assert False, 'TODO'
            else:
                assert False, 'TODO'
            '''

    def examine_sym_tab(self, section):
        if section.name not in ['.dynsym']:
            return

        if section['sh_entsize'] == 0:
            return

        for symbol in section.iter_symbols():
            if symbol['st_other']['visibility'] == "STV_HIDDEN":
                continue

            if (symbol['st_info']['type'] == 'STT_FUNC'
                    and symbol['st_shndx'] != 'SHN_UNDEF'):
                self.fun_dict[hex(symbol['st_value'])] = symbol.name


    def report(self):
        print("Entry: ", hex(self.entry))
        for (key, value) in self.plt_dict.items():
            print('%s: %s'%(hex(key), value))



class InstType(Enum):
    Comment=1
    JMP=2
    BR_SYM=3
    TBL_SYM=4

Instrumentation = namedtuple('Instrumentation', ['addr', 'comment', 'inst_type', 'args'])
RelocExpr = namedtuple('RelocExpr', ['addr', 'label', 'code', 'comment'])
FunBriefInfo = namedtuple('FunBriefInfo', ['label', 'startsWithENDBR'])

REGISTERS_x64 = ['RAX', 'RBX', 'RCX', 'RDX', 'RSI', 'RDI', 'RBP', 'RSP', 'R8', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15']
REGISTERS = ['RAX', 'RBX', 'RCX', 'RDX', 'RSI', 'RDI', 'RBP', 'RSP', 'R8',
'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15', 'EAX', 'EBX', 'ECX', 'EDX',
'ESI', 'EDI', 'EBP', 'ESP','R8D', 'R9D', 'R10D', 'R11D', 'R12D', 'R13D',
'R14D', 'R15D', 'AX', 'BX', 'CX', 'DX', 'BP', 'SI', 'DI', 'SP', 'R8W', 'R9W',
'R10W', 'R11W', 'R12W', 'R13W', 'R14W', 'R15W', 'AH', 'BH', 'CH', 'DH', 'AL',
'BL', 'CL', 'DL', 'BPL', 'SIL', 'DIL', 'SPL', 'R8B', 'R9B', 'R10B', 'R11B',
'R12B', 'R13B', 'R14B', 'R15B']


def is_register(target):
    if target.startswith('*%'):
        return target[2:] in REGISTERS
    return target in REGISTERS

def is_unsupported_instruction(reassem, syntax):
    opcode = reassem.split()[0]

    if opcode in ['lock']:
        #intel syntax
        opcode2 = reassem.split()[1]
        #if opcode2 in ['add', 'adc', 'and', 'btc', 'btr', 'bts', 'cmpxchg', 'cmpxch8b', 'cmpxchg16b', 'dec', 'inc', 'neg', 'not', 'or', 'sbb', 'sub', 'xor', 'xadd', 'xchg']:
        if opcode2 in ['add', 'adc', 'and', 'btc', 'btr', 'bts', 'cmpxchg', 'cmpxch8b', 'cmpxchg16b', 'dec', 'inc', 'or', 'sbb', 'sub', 'xor', 'xadd', 'xchg']:
            pass
        elif syntax != 'intel' and opcode2[:-1] in ['add', 'adc', 'and', 'btc', 'btr', 'bts', 'cmpxchg', 'cmpxch8b', 'cmpxchg16b', 'dec', 'inc', 'neg', 'not', 'or', 'sbb', 'sub', 'xor', 'xadd', 'xchg']:
            pass
        else:
            return True
        if opcode2 in ['inc', 'dec']:
            operand = reassem.split(',')[-1]
            if re.search('\[.*\]', operand):
                pass
            else:
                return True

        #undefined behavior
        if syntax == 'intel' and len(reassem.split(',')) > 1:
            source = reassem.split(',')[-1]
            if re.search('\[.*\]', source):
                return True

            dest = reassem.split(',')[-2]
            if not re.search('\[.*\]', dest):
                return True
        elif syntax != 'intel' and len(reassem.split()) > 3:
            source = reassem.split()[2]
            if '(' in source:
                if '),' in reassem:
                    return True
                else:
                    pass
            else:
                dest = reassem.split()[-1]
                if ')' not in dest:
                    return True

    elif opcode.startswith('rep'):
        opcode2 = reassem.split()[1]
        if opcode in ['rep']:
            if opcode2 in ['ins', 'outs', 'movs', 'lods', 'stos']:
                pass
            elif syntax != 'intel' and opcode2[:1] in ['ins', 'outs', 'movs', 'lods', 'stos']:
                pass
            else:
                return True
        elif opcode in ['repe', 'repne', 'repz', 'repnz']:
            if opcode2 in ['cmps', 'scas', 'ret', 'retq']:
                pass
            elif len(opcode2) == 5  and opcode2[:4] in ['cmps', 'scas', 'ins', 'outs', 'movs', 'lods', 'stos']:
                pass
            else:
                return True
    elif opcode in ['call']:
        dest = reassem.split()[-1]
        if dest in REGISTERS and dest not in REGISTERS_x64:
            return True

        if '*%' in dest:
            if dest[2:] in REGISTERS and dest[2:] not in REGISTERS_x64:
                return True
    # B2R2 BUG
    if opcode in ['movmskps']:
        if 'xmmword' in reassem:
            return True
    if opcode in ['bndstx']:
        return True
    if opcode in ['lea']:
        if reassem.split()[-1].startswith('SS:['):
            return True
    if opcode in ['movnti']:
        if reassem.split()[-1] in REGISTERS_x64:
            return True
        if reassem.split()[1][:-1] in REGISTERS:
            return True
    if opcode in ['cmovs']:
        if '{K7}{z}' in reassem:
            return True
    if opcode in ['vdppd']:
        if 'YMM' in reassem:
            return True
    '''
    elif opcode in ['vmovhpd', 'vsqrtsd']:
        if 'YMM' in reassem:
            return True
    elif opcode in ['in']:
        if reassem.split()[1][:-1] in REGISTERS_x64:
            return True
    elif opcode in ['cmovs']:
        if 'R9D{K3}{z}' in reassem:
            return True
    '''
    return False


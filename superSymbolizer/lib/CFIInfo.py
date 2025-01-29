#!/usr/bin/env python3 -tt
#-*- coding: utf-8 -*-
from elftools.elf.elffile import ELFFile
from elftools.dwarf.callframe import CallFrameInfo
from elftools.dwarf.callframe import FDE
from elftools.dwarf.structs import DWARFStructs
from elftools.dwarf.dwarf_expr import DW_OP_opcode2name
from lib.ExceptTable import GCCExceptTable
from lib.ExceptTable import decode_uleb128
import struct

class CFIInfo:
    def __init__(self, bin_path, arch='x86-64'):

        self.f = open(bin_path, 'rb')
        self.elffile = ELFFile(self.f)
        self.arch = arch

        self.dwarf = self.elffile.get_dwarf_info()
        self.eh_frame = self.dwarf.eh_frame_sec
        self.config = self.dwarf.config
        self.address_size = self.config.default_address_size

        self.my_struct = DWARFStructs(little_endian=self.config.little_endian, dwarf_format=32, address_size=self.config.default_address_size)

        self.cfi = CallFrameInfo(self.eh_frame.stream, self.eh_frame.size, self.eh_frame.address, base_structs=self.my_struct, for_eh_frame=True)

        self.entries = self.cfi.get_entries()

        self.fde_tbl = None
        self.get_fde_tbl()


    def get_eh_frame_section(self):
        for section in self.elffile.iter_sections():
            if section.name == '.eh_frame':
                return section
        return ''


    def get_augment_addr(self, section, c_offset, a_offset):
        data = section.data()
        cie = CIEHeader(data[c_offset:])

        if 'P_fp' in cie.aData:
            fp_offset = c_offset + cie.aData['P_fp'][0] + cie.aData['P_fp'][1]
        else:
            assert False

        if a_offset != cie.aData['P_fp'][0]:
            assert False
        return section.header.sh_addr + a_offset + c_offset + cie.aData['P_fp'][1]

    def get_fde_tbl(self):
        if self.fde_tbl is not None:
            return self.fde_tbl

        self.fde_tbl = []
        for item in self.entries:
            if isinstance(item, FDE):
                fde = FDE_REC(item, self.address_size, self.arch)
                fde.except_tbl = self.get_except_table(item)

                self.fde_tbl.append(fde)


        return self.fde_tbl


    def get_except_table(self, item):

        header = item.header
        #code address
        entry_point = header.initial_location
        #FDE location
        offset = item.offset

        gcc_except_table = GCCExceptTable(self.elffile)
        if len(item.augmentation_bytes) > 0:
            eh_frame = self.get_eh_frame_section()
            eh_frame_data = eh_frame.data()
            eh_frame_addr = eh_frame.header.sh_addr


            f_offset = item.cie.augmentation_dict['personality'].function
            f_addr = self.get_augment_addr(eh_frame, item.cie.offset, f_offset)

            #encoding
            LSDA_encoding = item.cie.augmentation_dict['LSDA_encoding']
            #gcc_except_table offset
            augment = struct.unpack('<I', item.augmentation_bytes)[0]

            gcc_except_table_addr = augment+offset+17+eh_frame_addr

            tbl = gcc_except_table.parse(gcc_except_table_addr)
            tbl['entry_point'] = entry_point
            tbl['gcc_except_table_addr'] = gcc_except_table_addr
            tbl['f_addr'] = f_addr
            return tbl

            '''
            tbl['header'].print_rec()
            tbl['csHeader'].print_rec()
            print('entry point: %s'%(hex(entry_point)))
            for region in tbl['region_tbl']:
                region.print_rec(entry_point)

            tbl['action'].print_rec()

            print('CIE fun(personality routine): %s'%hex(f_addr))

            for item in tbl['type_tbl'].tbl:
                sym_addr = item.get_addr(gcc_except_table_addr)
                print('FDE type table : %s'%hex(sym_addr))
            '''

        else:
            #gcc_except_table_addr = 0
            pass
        return None


class CIEHeader:
    def __init__(self, data):
        self.length = struct.unpack('<I', data[:4])[0]
        self.CIE_id = struct.unpack('<I', data[4:8])[0]
        self.version = struct.unpack('<b', data[8:9])[0]

        idx = 9
        self.augmentation = b''
        while True:
            if data[idx] == 0 or data[idx] == '\x00':
                break
            idx += 1
        self.augmentation = data[9:idx]
        idx += 1
        self.code_align = data[idx]
        idx += 1
        self.data_align = data[idx]
        idx += 1
        self.return_addr_reg = data[idx]

        self.aData = dict()
        if b'z' in self.augmentation:
            idx +=1
            aLength, tmp = decode_uleb128(data[idx:])
            idx += tmp
            augData = data[idx:idx+aLength]
            self.readAugData(augData, idx)

            idx += aLength - 1


        self.size = idx+1

    def readAugData(self, data, offset):
        idx = 0
        for item in self.augmentation[1:]:
            if item == 0x50: #'P':
                self.aData['P_encoding'] = (data[idx],idx+offset)
                idx += 1
                self.aData['P_fp'] = (struct.unpack('<I',data[idx:idx+4])[0],idx+offset)
                idx += 4
            elif item == 0x4c: #'L':
                self.aData['L_encoding'] = (data[idx],idx+offset)
                idx += 1
            elif item == 0x52: #'R':
                self.aData['R_encoding'] = (data[idx],idx+offset)
                idx += 1
            else:
                assert False

        if idx != len(data):
            assert False


class FDE_REC:
    def __init__(self, item, address_size, arch):
        self.header = item.header
        self.address_size = address_size
        self.state = -1
        self.arch = arch
        if self.arch == 'x86':
            #ref: https://www.uclibc.org/docs/psABI-i386.pdf (Table 2.14)
            #self.reg_name_dict = {0:'eax',3:'ebx',1:'ecx',2:'edx',6:'esi',7:'edi',5:'ebp',4:'esp'}
            self.reg_name_dict = {0:'eax',3:'ebx',1:'ecx',2:'edx',6:'esi',7:'edi',5:'edi',4:'esp',8:'eip'}
        elif self.arch in ['x86-64','x64']:
            #ref: https://www.uclibc.org/docs/psABI-x86_64.pdf (Figure 3.36)
            self.reg_name_dict = {0:'rax',3:'rbx',1:'rdx',2:'rcx',6:'rbp',7:'rsp',5:'rdi',4:'rsi',16:'rip',
                                8:'r8',9:'r9',10:'r10',11:'r11',12:'r12',13:'r13',14:'r14',15:'r15'}
        else:
            print('unknown archtecture')
            assert False

        self.start_proc = self.header.initial_location
        self.end_proc = self.start_proc + self.header.address_range

        self.cfi_dict = dict()
        self.desc_list = list()

        self.loc = self.header.initial_location
        if item.cie:
            for idx, inst in enumerate(item.cie.instructions):
                if inst.opcode == 0: break
                elif idx < 2: continue
                elif idx == 2: self.state=0
                desc = self.get_desc(inst)
                self.desc_list.append(desc)
                #print(desc)
        for inst in item.instructions:
            desc = self.get_desc(inst)
            self.desc_list.append(desc)

        #self.except_tbl = except_tbl

    def print_rec(self):
        print('pc=%s..%s'%(hex(self.start_proc), hex(self.end_proc)))
        for desc in self.desc_list:
            print('  %s'%(desc))

    def print_except_tbl(self):
        if self.except_tbl is None:
            return

        entry_point =self.except_tbl['entry_point']
        gcc_except_table_addr = self.except_tbl['gcc_except_table_addr']
        f_addr = self.except_tbl['f_addr']

        self.except_tbl['header'].print_rec()
        self.except_tbl['csHeader'].print_rec()
        print('entry point: %s'%(hex(entry_point)))
        for region in self.except_tbl['region_tbl']:
            region.print_rec(entry_point)

        print('CIE fun(personality routine): %s'%hex(f_addr))

        if self.except_tbl['header'].end_offset > 0:
            self.except_tbl['action'].print_rec()

            for item in self.except_tbl['type_tbl'].tbl:
                sym_addr = item.get_addr(gcc_except_table_addr)
                print('FDE type table : %s'%hex(sym_addr))


    def reg_name(self, reg):
        if self.arch == 'x86':
            if reg == 3: return 'ebx'
            if reg == 6: return 'esi'
            if reg == 7: return 'edi'
            if reg == 16: return 'eip'

            if reg == 0: return 'eax'
            if reg == 1: return 'ecx'
            if reg == 2: return 'edx'
            if reg == 5: return 'ebp'
            if reg == 4: return 'esp'
        elif self.arch == 'x86-64':
            if reg == 3: return 'rbx'
            if reg == 6: return 'rsi'
            if reg == 7: return 'rdi'
            if reg == 16: return 'rip'

            if reg == 0: return 'rax'
            if reg == 1: return 'rcx'
            if reg == 2: return 'rdx'
            if reg == 5: return 'ebp'
            if reg == 4: return 'rsp'
            return 'r%d'%(reg)

        assert False


    def reg_info(self, reg):
        return '%d (%s)'%(reg, self.reg_name_dict[reg])

    def get_expr(self, opcode_list):
        ret = ''
        idx = 0
        #print(opcode_list)
        while idx < len(opcode_list):
            if len(ret) > 0:
                ret += '; '

            opcode = opcode_list[idx]
            if opcode >= 0x70 and opcode <= 0x90:
                idx += 1
                ret += '%s (%s): %d'%(DW_OP_opcode2name[opcode],
                        self.reg_name_dict[opcode-0x70],
                        opcode_list[idx])
            else:
                ret += DW_OP_opcode2name[opcode]

            idx += 1


        return '(' + ret + ')'

    def get_desc(self, inst):
        opcode = inst.opcode

        if opcode == 0x0:
            self.state = -1
            return 'DW_CFA_nop'

        if opcode > 0x40 and opcode < 0x80:
            self.state = 0
            self.loc += inst.args[0]
            return 'DW_CFA_advance_loc: %d to %016x'%(inst.args[0], self.loc)

        if opcode == 0x2:
            self.state = 1
            self.loc += inst.args[0]
            return 'DW_CFA_advance_loc1: %d to %016x'%(inst.args[0],self.loc)

        if opcode == 0x3:
            self.state = 2
            self.loc += inst.args[0]
            return 'DW_CFA_advance_loc2: %d to %016x'%(inst.args[0],self.loc)

        if opcode == 0x4:
            self.state = 3
            self.loc += inst.args[0]
            return 'DW_CFA_advance_loc4: %d to %016x'%(inst.args[0],self.loc)

        if opcode == 0x7:
            return 'DW_CFA_undefined: r%d (%s)'%(inst.args[0], self.reg_name(inst.args[0]) )

        # -1: nop
        #  0: advance_loc
        #  1: advance_loc1
        #  2: advance_loc2
        #  3: advance_loc4
        #  4: else

        desc, cmd = self.get_cfi_cmd(opcode, inst)
        if self.state in [0,1,2,3] and  cmd is not None:
            if self.loc in self.cfi_dict:
                self.cfi_dict[self.loc].append(cmd)
            else:
                self.cfi_dict[self.loc] = [cmd]

        if desc is not None:
            return desc

        print(inst)
        import pdb
        pdb.set_trace()
        return 'Unknown:'+str(opcode)

    def get_cfi_cmd(self, opcode, inst):
        if opcode == 0xe:
            return ('DW_CFA_def_cfa_offset: %d'%(inst.args[0]),
                     '.cfi_def_cfa_offset %d'%(inst.args[0]))
        if opcode >= 0x80 and opcode < 0xa0:
            return ('DW_CFA_offset: r%s at cfa-%d'%(self.reg_info(inst.args[0]), self.address_size * inst.args[1]),
                     '.cfi_offset %d, -%d'%(inst.args[0], self.address_size * inst.args[1]))
        if opcode == 0xd:
            return ('DW_CFA_def_cfa_register: r%s'%(self.reg_info(inst.args[0])),
                    '.cfi_def_cfa_register %d'%(inst.args[0]))

        if opcode == 0xc:
            return ('DW_CFA_def_cfa: r%s ofs %d'%(self.reg_info(inst.args[0]),inst.args[1]),
                    '.cfi_def_cfa %d, %d'%(inst.args[0], inst.args[1]))

        if opcode == 0xa:
            return ('DW_CFA_remember_state',
                    '.cfi_remember_state')

        if opcode == 0xb:
            return ('DW_CFA_restore_state',
                    '.cfi_restore_state')
        if opcode > 0xc0 and opcode < 0xe0:
            return ('DW_CFA_restore: r%s'%(self.reg_info(inst.args[0])),
                     '.cfi_restore %d'%(inst.args[0]))

        if opcode == 0x2e:
            return ('DW_CFA_GNU_args_size: %s'%(inst.args[0]),
                    '.cfi_escape 0x2e,%s'%(inst.args[0]))

        if opcode == 0xf:
            return self.get_def_cfa_expression(inst.args)
        if opcode == 0x10:
            return self.get_cfa_expression(inst.args)

        return (None, None)

    def get_cfa_expression(self, args):
        disp = 'DW_CFA_expression: r%s %s'%(self.reg_info(args[0]),self.get_expr(args[1]))
        cmd = '.cfi_escape 0x10,%s,0x2,%s,%s'%(args[0],args[1][0],args[1][1])
        return disp, cmd
    def get_def_cfa_expression(self, args):
        disp = 'DW_CFA_def_cfa_expression ' + self.get_expr(args[0])
        cmd = '.cfi_escape 0xf,0x3,' + ','.join([hex(item) for item in args[0]])
        return disp, cmd

def print_except_table(cfi, item, ehTbl):

    header = item.header
    #code address
    entry_point = header.initial_location
    #FDE location
    offset = item.offset

    if len(item.augmentation_bytes) > 0:
        eh_frame = cfi.get_eh_frame_section()
        eh_frame_data = eh_frame.data()
        eh_frame_addr = eh_frame.header.sh_addr


        f_offset = item.cie.augmentation_dict['personality'].function
        f_addr = cfi.get_augment_addr(eh_frame, item.cie.offset, f_offset)

        #encoding
        LSDA_encoding = item.cie.augmentation_dict['LSDA_encoding']
        #gcc_except_table offset
        augment = struct.unpack('<I', item.augmentation_bytes)[0]

        gcc_except_table_addr = augment+offset+17+eh_frame_addr

        tbl = ehTbl.except_dict[gcc_except_table_addr]

        tbl['header'].print_rec()
        tbl['csHeader'].print_rec()
        print('entry point: %s'%(hex(entry_point)))
        for region in tbl['region_tbl']:
            region.print_rec(entry_point)

        tbl['action'].print_rec()


        print('CIE fun(personality routine): %s'%hex(f_addr))

        for item in tbl['type_tbl'].tbl:
            sym_addr = item.get_addr(gcc_except_table_addr)
            print('FDE type table : %s'%hex(sym_addr))


    else:
        gcc_except_table_addr = 0

import json

def get_gcc_except_table(tbl, start_proc, end_proc):
    global EHFUN_CNT
    global EHBB_CNT

    tbl_addr = tbl['gcc_except_table_addr']

    offset = tbl['header'].size
    #tbl['header'].print_rec()

    if tbl['csHeader'] is not None:
        offset += tbl['csHeader'].size
    #tbl['csHeader'].print_rec()


    except_tbl = []
    for item in tbl['region_tbl']:
        bb_start = start_proc + item.start
        bb_end = bb_start + item.length
        landing_pad_start = start_proc + item.landing_pad
        if landing_pad_start == start_proc:
            landing_pad_start = 0
        entry = {'block':{'start':hex(bb_start),'end':hex(bb_end)}, 'landing_pad':hex(landing_pad_start)}
        #print('%s - %s : %s'%(hex(bb_start), hex(bb_end), hex(landing_pad_start)))
        except_tbl.append(entry)

        offset += item.length
    return except_tbl


def get_except_tbls(filename, arch):

    cfi = CFIInfo(filename, arch)

    except_tbls = []
    for fde in cfi.get_fde_tbl():
        start_proc = fde.start_proc
        end_proc = fde.end_proc

        if fde.except_tbl is not None:
            tbl = get_gcc_except_table(fde.except_tbl, start_proc, end_proc)

            mydict = {'Function Info':{'start':'%s'%(hex(start_proc)),
                     'end':'%s'%(hex(end_proc))},
                     'Except Table':tbl}
            except_tbls.append(mydict)
    return except_tbls

import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Debug Info')
    parser.add_argument('bin_path', type=str, help='file path')
    parser.add_argument('arch', type=str, help='architect(x86, x86-64)')

    args = parser.parse_args()

    '''
    tbls = get_except_tbls(args.bin_path, args.arch)

    print(json.dumps(tbls, indent=1))
    '''
    cfi = CFIInfo(args.bin_path, args.arch)

    for fde in cfi.get_fde_tbl():
        fde.print_rec()
        print()
        #fde.print_except_tbl()
        pass

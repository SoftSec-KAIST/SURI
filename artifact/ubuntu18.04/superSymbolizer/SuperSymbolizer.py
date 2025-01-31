import struct

from ElfBricks import ElfBricks
from lib.CFIInfo import CFIInfo
from lib.LocalSymbolizer import LocalSymbolizer
from lib.Misc import EParser, FunBriefInfo
import json
import re

class SuperSymbolizer:

    def __init__(self, bin_file, meta_file, opt_level=0, syntax='intel'):
        with open(meta_file) as f:
            data = json.load(f)
            self.funDict = data['FunDict']
            self.false_fun_list = data['FalseFunList']
            self.plt_dict = data['PLTDict']

        eparser = EParser(bin_file)
        self.entry = eparser.entry
        self.opt_level = opt_level
        self.syntax = syntax

        # add plt that B2R2 missed
        #self.plt_dict = dict()
        for fun_addr in self.funDict.keys():
            if fun_addr in self.plt_dict:
                continue
            for plt_range in eparser.plt_ranges:
                if int(fun_addr, 16) in plt_range:
                    target = self.get_plt_target(self.funDict[fun_addr]['BBLs'][fun_addr]['Code'])
                    if target in  eparser.reloc_dict['R_X86_64_JUMP_SLOT']:
                        self.plt_dict[fun_addr] = eparser.reloc_dict['R_X86_64_JUMP_SLOT'][target]

        for key, value in self.plt_dict.items():
            self.plt_dict[key] = value + '@PLT'

        self.total_bbls = 0
        self.total_overlapped_bbls = 0
        self.total_br_sites = 0
        self.multi_br_sites = 0

        self.fun_dict = {}
        self.fun_ids = {}
        self.fun_info_dict = {}
        self.main_fun = None
        self.refer_fun_dict = {}
        self.fd = None
        self.part_fun_dict = {}

        self.cfi_dict = self.get_cfi_dict(bin_file)

        self.elfBrick = ElfBricks(bin_file)
        self.reloc_sym_dict = self.get_reloc_sym_dict(self.elfBrick)
        self.rip_access_addrs = []

    def get_reloc_sym_dict(self, elfBrick):
        symdict = dict()
        for rela in elfBrick._rela_list:
            idx = rela.r_info >> 32
            if idx > 0:
                sym = elfBrick._dynsym_list[idx]
                symname = str(elfBrick._dynstr[sym.st_name:].decode('utf-8')).split('\x00')[0]
                if rela.r_addend:
                    symdict[rela.r_offset] = symname + '+%d'%(rela.r_addend)
                else:
                    symdict[rela.r_offset] = symname

            else:
                symdict[rela.r_offset] = rela.r_addend
        return symdict

    def get_cfi_dict(self, bin_file):
        cfi_dict = dict()
        cfi = CFIInfo(bin_file)
        cfi_table = cfi.get_fde_tbl()
        for cfi_info in cfi_table:
            if cfi_info.start_proc in cfi_dict:
                assert False, "CFI info was overlapped"
            cfi_dict[cfi_info.start_proc] = cfi_info
        return cfi_dict

    def get_plt_target(self, bbl):
        for inst in bbl:
            if inst['IsBranch']:
                if self.syntax == 'intel':
                    pattern = re.findall('jmp .*\[RIP\+(.*)\]', inst['Disassem'])
                else:
                    pattern = re.findall('jmpq \*(.*)\(%RIP\)', inst['Disassem'])
                if pattern:
                    return int(pattern[0], 16) + int(inst['Addr'], 16) + inst['Length']
        return 0

    def get_id(self, fun_addr):
        return self.fun_ids[fun_addr]


    def symbolize(self, endbr=True, rip_access_list=None, disable_super_symbolize=False):
        for fun_id, fun_addr in enumerate(self.funDict.keys()):
            self.fun_ids[fun_addr] = fun_id
            label = 'fun_%d_%x'%(fun_id, int(fun_addr, 16))
            first_code = self.funDict[fun_addr]['BBLs'][fun_addr]['Code'][0]['Disassem']
            if first_code in ['endbr64']:
                hasENDBR = True
            else:
                if endbr: hasENDBR = False
                else:     hasENDBR = True

            self.fun_info_dict[fun_addr] = FunBriefInfo(label, hasENDBR)

        # update plt function info
        for fun_addr, label in self.plt_dict.items():
            self.fun_info_dict[fun_addr] = FunBriefInfo(label, True)
            if fun_addr in self.funDict:
                del self.funDict[fun_addr]

        # register false function info
        for fun_addr in self.false_fun_list:
            if fun_addr in self.fun_info_dict:
                continue
            addr = int(fun_addr, 16)
            label = 'false_fun_%x'%(addr)
            if addr > 0x100000000:
                addr = addr-0x10000000000000000
                fun_addr = hex(addr)
                label = 'false_fun_minus_%x'%(-addr)
            self.fun_info_dict[fun_addr] = FunBriefInfo(label, False)

        visit_log=dict()
        for fun_addr in self.funDict.keys():
            fun_id = self.fun_ids[fun_addr]
            fun_label = self.fun_info_dict[fun_addr].label
            fun_symbolizer = LocalSymbolizer(fun_addr, fun_id, fun_label, self.funDict[fun_addr], self.fun_info_dict,
                                             self.plt_dict, self.opt_level, self.syntax,
                                             disable_super_symbolize = disable_super_symbolize)
            fun_symbolizer.run(self.cfi_dict, self.reloc_sym_dict, rip_access_list, visit_log)

            self.fun_dict[fun_addr] = fun_symbolizer
            self.update_stat(fun_symbolizer)

            self.rip_access_addrs.extend(fun_symbolizer.rip_access_addrs)

        # search main function
        self.main_fun = self.search_main()

        # get .init, .fini function
        self.init_section_range = self.elfBrick._init_section_range
        self.fini_section_range = self.elfBrick._fini_section_range

        # get the function list that registered in .init_array .fini_array
        self.init_array = self.elfBrick._init_array
        self.fini_array = self.elfBrick._fini_array

    def search_main(self):
        main_fun = None
        start_fun = self.fun_dict[hex(self.entry)]
        for asm in reversed(start_fun.reassem_code[self.entry]):
            if self.syntax == 'intel':
                if 'lea ' in asm.code:
                    main_fun = re.search('\[RIP\+(.*)\]', asm.code).group(1)
                    break
            else:
                if 'leaq ' in asm.code:
                    main_fun = re.search(' (.*)\(%RIP\)', asm.code).group(1)
                    break
        assert main_fun
        return main_fun

    def report_statistics(self, filename):
        with open(filename, 'w') as fd:
            self.fd = fd
            self.write_code("# [*] Overlapped BBLs %d/%d "%(self.total_overlapped_bbls, self.total_bbls))
            self.write_code("# [*] Indirect Branch Sites %d (%d)"%(self.total_br_sites, self.multi_br_sites))
        self.fd = None


    def print_reassem_code(self, add_rodata=False):
        if self.syntax == 'intel':
            self.write_code('.intel_syntax noprefix')

        fun_list = [int(addr, 16) for addr in self.fun_dict.keys()]


        extra_block_dict = {}
        for fun_addr in fun_list:
            if len(self.fun_dict[hex(fun_addr)].reassem_code) > 1:
                for key in self.fun_dict[hex(fun_addr)].reassem_code.keys():
                    if hex(key) in self.fun_dict:
                        if key == fun_addr:
                            continue
                        if hex(key) in self.funDict and fun_addr in self.funDict[hex(key)]['AbsorbingFun']:
                            continue
                    if key not in extra_block_dict:
                        extra_block_dict[key] = []
                    extra_block_dict[key].append(hex(fun_addr))

        fun_list.extend([addr for addr in extra_block_dict.keys()])
        fun_list.sort()
        self.need_gxx_personality_symbol = False
        visited_fun = []
        jump_table_list = []
        for fun_addr in fun_list:
            if fun_addr in visited_fun:
                continue
            visited_fun.append(fun_addr)
            if hex(fun_addr) in self.fun_dict:
                self.print_reassem_fun_code(hex(fun_addr))
                if not add_rodata:
                    self.print_reassem_jump_tbls(hex(fun_addr))
                else:
                    jump_tables = self.get_jump_tables(hex(fun_addr))
                    if jump_tables:
                        jump_table_list.append(jump_tables)

            visited_absorber = []
            if hex(fun_addr) in self.funDict:
                for absorber in self.funDict[hex(fun_addr)]['AbsorbingFun']:
                    visited_absorber.append(absorber)
                    self.print_reassem_block_code(absorber, fun_addr)

            if fun_addr in extra_block_dict:
                for absorber in extra_block_dict[fun_addr]:
                    if absorber not in visited_absorber:
                        self.print_reassem_block_code(absorber, fun_addr)


        if add_rodata:
            self.print_rodata(jump_table_list)

        if self.need_gxx_personality_symbol:
            self.print_gxx_personality_symbol()

        data_label = []
        for fun_addr in fun_list:
            if hex(fun_addr) in self.fun_dict:
                fun_symbolizer = self.fun_dict[hex(fun_addr)]
                data_label.extend(fun_symbolizer.data_labels)


        data_label_set = list(set(data_label))
        data_label_set.sort()


        if self.false_fun_list:

            self.write_code('#----------------------------------------')
            self.write_code('# the definition of false function label')
            self.write_code('#----------------------------------------')
            for fun_addr in self.false_fun_list:
                addr = int(fun_addr, 16)

                if addr > 0x100000000:
                    addr = addr-0x10000000000000000
                    label = 'false_fun_minus_%x'%(-addr)
                else:
                    label = 'false_fun_%x'%(addr)
                code = '%s:'%(label)
                self.write_code(code)
            self.write_code('\tcall abort@PLT')


        self.write_code('#-----------------------------------')
        self.write_code('#    the definition of data labels')
        self.write_code('#-----------------------------------')
        for label in data_label_set:
            addr = int(label.split('_')[-1], 16)
            if label.split('_')[-2] == 'minus':
                #code = '.set %s, -%s'%(label, hex(addr))
                code = '.set %s, -1'%(label)
            else:
                code = '.set %s, %s'%(label, hex(addr))
            self.write_code(code)

    def print_rodata(self, jump_table_list):
        jump_dict = dict()
        label_dict = dict()
        for jump_tables in jump_table_list:
            for addr, tbls in jump_tables.items():
                if addr not in jump_dict:
                    jump_dict[addr] = tbls
                    label_dict[addr] = [tbls[0]]
                else:
                    if len(tbls) > len(jump_dict):
                        jump_dict[addr] = tbls

                    label_dict[addr].append(tbls[0])


        robase = self.elfBrick._rodata_base_addr
        rosize = len(self.elfBrick._rodata_sec)
        rodata = self.elfBrick._rodata_sec

        assert robase % 4 == 0, '.rodata section is misaligned'

        self.write_code('.section .my_rodata, "a", @progbits')

        emitted_code = []
        for cur_addr in range(robase, robase+rosize, 4):
            idx = cur_addr - robase

            if cur_addr in jump_dict:
                for label in label_dict[cur_addr]:
                    self.write_code(label)

                for line in jump_dict[cur_addr][1:]:
                    self.write_code(line)
                    if line.split()[0] in ['.long']:
                        entry = int(line.split()[-1],16)
                        assert (entry not in emitted_code), \
                            'find overlapped entry %s'%(hex(entry))
                        emitted_code.append(entry)

            if cur_addr in emitted_code:
                continue

            if cur_addr + 4 <= robase + rosize:
                contents = struct.unpack('<I', rodata[idx:idx + 4])[0]
                self.write_code(' \t.long %-10s %20s %s'%(hex(contents), "#", hex(cur_addr)))
            else:
                for cur_addr2 in range(cur_addr, robase+rosize, 1):
                    idx = cur_addr2 - robase
                    contents = struct.unpack('<B', rodata[idx:idx + 1])[0]
                    self.write_code('\t.byte %-10s %20s %s'%(hex(contents), "#", hex(cur_addr2)))



    def print_gxx_personality_symbol(self):
        self.write_code('#----------------------------------------')
        self.write_code('# define a label for __gxx_personality_v0')
        self.write_code('#----------------------------------------')

        self.write_code('.hidden DW.ref.__gxx_personality_v0')
        self.write_code('.weak   DW.ref.__gxx_personality_v0')
        self.write_code(
            '.section    .data.rel.local.DW.ref.__gxx_personality_v0,"awG",@progbits,DW.ref.__gxx_personality_v0,comdat')
        self.write_code('.align 8')
        self.write_code('.type   DW.ref.__gxx_personality_v0, @object')
        self.write_code('.size   DW.ref.__gxx_personality_v0, 8')
        self.write_code('DW.ref.__gxx_personality_v0:')
        self.write_code('.quad   __gxx_personality_v0')


    def print_reassem_block_code(self, absorber, block_addr):

        fun_symbolizer = self.fun_dict[absorber]
        if block_addr not in fun_symbolizer.reassem_code:
            return

        self.write_code('#----------------------------------------')
        self.write_code('# %s absorbs %s '%(absorber, hex(block_addr)))
        self.write_code('#----------------------------------------')

        part_fun_label = self.get_part_fun_label(absorber)

        self.print_section_name('.text')
        self.print_fun_type(part_fun_label)
        self.write_code('\t.align 8')
        self.write_code('%s:'%(part_fun_label))

        for code in fun_symbolizer.reassem_code[block_addr]:
            if code.label:
                if code.comment:
                    self.write_code('%-40s: %s'%(code.label))
                else:
                    self.write_code('%s:'%(code.label))
                continue

            if not code.code:
                self.write_code('%s'%(code.comment))
            elif not code.comment:
                self.write_code('\t%s'%(code.code))
            elif code.code and code.comment:
                self.write_code('\t%-40s %s'%(code.code, code.comment))

        self.print_fun_size_def(part_fun_label)

    def get_part_fun_label(self, fun_addr):
        fname = self.fun_info_dict[fun_addr].label
        if fname in self.part_fun_dict:
            id = self.part_fun_dict[fname] + 1
        else:
            id = 0
        self.part_fun_dict[fname] = id
        return fname + '.part.%d'%(id)

    def print_fun_brief_info(self, fun_addr, reassem_code):

        self.write_code()
        self.write_code()

        self.write_code('#-------------------------------------------')


        if reassem_code[0].addr != int(fun_addr, 16):
            self.write_code("# %s is not a start address of this function"%(fun_addr))
            if fun_addr in self.refer_fun_dict:
                refer_fun = [ addr for addr in self.refer_fun_dict[fun_addr] if addr != fun_addr ]
            else: refer_fun = []
            if len(refer_fun) == 1:
                for fdeRange in self.funDict[fun_addr]['FDERanges']:
                    if refer_fun[0] == fdeRange['Start']:
                        self.write_code("# %s is refered by part block (%s)"%(fun_addr, refer_fun[0]))

                inst_set1 = set(self.funDict[fun_addr]['InstAddrs'])
                for absorber in self.funDict[refer_fun[0]]['AbsorbingFun']:
                    inst_set2 = set(self.funDict[absorber]['InstAddrs'])
                    if len(inst_set1 - inst_set2) == 0:
                        self.write_code("# %s is may part of %s which absorbs %s"%(fun_addr, absorber, refer_fun[0]))



        if fun_addr in self.refer_fun_dict:
            self.write_code("# %s is refered by %d function(s) :"%(fun_addr, len(self.refer_fun_dict[fun_addr])) + str(self.refer_fun_dict[fun_addr]))
        if len(self.funDict[fun_addr]['FDERanges']) > 1:
            entry = int(fun_addr, 16)
            parts = []
            for fdeRange in self.funDict[fun_addr]['FDERanges']:
                fdeStart = int(fdeRange['Start'], 16)
                fdeEnd  = int(fdeRange['End'], 16)
                if entry < fdeStart or fdeEnd <= entry:
                    parts.append(hex(fdeStart))

            self.write_code("# %s has part blocks which are located at "%(fun_addr)+ str(parts))


        self.write_code('#-------------------------------------------')

    def print_fun_type(self, fun_name, bind_type=''):
        if bind_type:
            self.write_code('\t%s %s'%(bind_type, fun_name))
        self.write_code('\t.type %s, @function'%(fun_name))
    def print_fun_size_def(self, fun_name):
        self.print_section_name('.text')
        self.write_code('\t.size %s, .-%s'%(fun_name, fun_name))

    def print_section_name(self, sec_name):
        if sec_name in ['.text']:
            self.write_code('\t%s'%(sec_name))
        else:
            self.write_code('\t.section %s'%(sec_name))

    def print_init_array_function(self, fun_name):
        self.write_code('\t.section .init_array, "aw"')
        self.write_code('\t.align 8')
        self.write_code('\t.quad %s'%(fun_name))

    def print_fini_array_function(self, fun_name):
        self.write_code('\t.section .fini_array, "aw"')
        self.write_code('\t.align 8')
        self.write_code('\t.quad %s'%(fun_name))

    def print_reassem_fun_code(self, fun_addr):
        fun_symbolizer = self.fun_dict[fun_addr]
        fun_info = self.fun_info_dict[fun_addr]

        if not fun_symbolizer.reassem_code:
            self.print_section_name('.text')
            self.write_code('%s:'%(fun_info.label))
            self.write_code('\tcall abort@PLT')
            return

        reassem_code = fun_symbolizer.reassem_code[int(fun_addr, 16)]

        self.print_fun_brief_info(fun_addr, reassem_code)

        '''
        if int(fun_addr, 16) in self.init_section_range:
            self.print_section_name('.init')
        elif int(fun_addr, 16) in self.fini_section_range:
            self.print_section_name('.fini')
        else:
            self.print_section_name('.text')
        self.print_section_name('.text')
        '''

        if fun_info.label == self.main_fun:
            self.print_section_name('.text')
            self.print_fun_type('main', bind_type='.globl')
            self.write_code('\t.align 8')
            self.write_code('main:')
        else:
            self.print_section_name('.text')
            self.print_fun_type(fun_info.label)
            self.write_code('\t.align 8')

        for code in reassem_code:
            if code.label:
                if code.comment:
                    self.write_code('%-40s: %s'%(code.label))
                else:
                    self.write_code('%s:'%(code.label))
                continue

            if not code.code:
                self.write_code('%s'%(code.comment))
            elif not code.comment:
                self.write_code('\t%s'%(code.code))
            elif code.code and code.comment:
                self.write_code('\t%-40s %s'%(code.code, code.comment))
            if '.cfi_personality 0x9b,DW.ref.__gxx_personality_v0' in code.code:
                self.need_gxx_personality_symbol = True

        if fun_info.label == self.main_fun:
            self.print_fun_size_def('main')
        else:
            self.print_fun_size_def(fun_info.label)

        if int(fun_addr, 16) in self.init_array:
            self.print_init_array_function(fun_info.label)
        if int(fun_addr, 16) in self.fini_array:
            self.print_fini_array_function(fun_info.label)

    def print_reassem_jump_tbls(self, fun_addr):

        fun_symbolizer = self.fun_dict[fun_addr]

        tbl_addrs = list(fun_symbolizer.reassem_tbl.keys())
        tbl_addrs.sort()

        if tbl_addrs:
            self.print_section_name('.rodata')
            self.write_code('.align 4')

        for tbl_addr in tbl_addrs:
            reassem_code = fun_symbolizer.reassem_tbl[tbl_addr]
            for code in reassem_code:
                if code.label:
                    self.write_code('%s:'%(code.label))

                if not code.code:
                    self.write_code('%s'%(code.comment))
                elif not code.comment:
                    self.write_code('\t%s'%(code.code))
                elif code.code and code.comment:
                    self.write_code('\t%-40s %s'%(code.code, code.comment))
    def get_jump_tables(self, fun_addr):
        fun_symbolizer = self.fun_dict[fun_addr]
        #return fun_symbolizer.reassem_tbl

        tbl_addrs = list(fun_symbolizer.reassem_tbl.keys())
        tbl_addrs.sort()

        if tbl_addrs:
            self.print_section_name('.rodata')
            self.write_code('.align 4')

        tbl_dict = dict()


        for tbl_addr in tbl_addrs:
            reassem_code = fun_symbolizer.reassem_tbl[tbl_addr]
            lines = []
            for code in reassem_code:
                if code.label:
                    lines.append('%s:'%(code.label))

                if not code.code:
                    lines.append('%s'%(code.comment))
                elif not code.comment:
                    lines.append('\t%s'%(code.code))
                elif code.code and code.comment:
                    lines.append('\t%-40s %s'%(code.code, code.comment))

            tbl_dict[tbl_addr] = lines

        return tbl_dict

    def update_stat(self, fun_symbolizer):

        self.total_bbls += fun_symbolizer.no_bbls
        self.total_overlapped_bbls += fun_symbolizer.no_overlapped_bbls
        self.total_br_sites += fun_symbolizer.total_br_sites
        self.multi_br_sites += fun_symbolizer.multi_br_sites

        for refer_fun in fun_symbolizer.refer_funs:
            if refer_fun not in self.refer_fun_dict:
                self.refer_fun_dict[refer_fun] = []
            self.refer_fun_dict[refer_fun].append(fun_symbolizer.fun_addr)

    def write_code(self, line=''):
        if self.fd is None:
            print(line)
        else:
            print(line, file=self.fd)

    def create_reassem_file(self, filename, add_rodata=False):
        with open(filename, 'w') as fd:
            self.fd = fd
            self.print_reassem_code(add_rodata)
        self.fd = None


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Serializer')
    parser.add_argument('bin_file', type=str)
    parser.add_argument('b2r2_meta_file', type=str)
    parser.add_argument('reassembly_file', type=str)
    parser.add_argument('--optimization', type=int, default=0)
    parser.add_argument('--syntax', type=str, default='intel')
    parser.add_argument('--no-endbr', dest='endbr', action='store_false')
    parser.add_argument('--no-supersym', dest='supersym', action='store_false')

    args = parser.parse_args()

    sym = SuperSymbolizer(args.bin_file, args.b2r2_meta_file, args.optimization, args.syntax)
    sym.symbolize(args.endbr)
    if args.supersym:
        sym.create_reassem_file(args.reassembly_file)
    else:
        sym2 = SuperSymbolizer(args.bin_file, args.b2r2_meta_file, args.optimization, args.syntax)
        sym2.symbolize(args.endbr, sym.rip_access_addrs, disable_super_symbolize=True)
        sym2.create_reassem_file(args.reassembly_file, add_rodata=True)

    #sym.print_reassem_code()
    #sym.report_statistics()

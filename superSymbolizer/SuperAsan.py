import json
import re
from superSymbolizer.SuperSymbolizer import SuperSymbolizer


class SuperAsan(SuperSymbolizer):

    def read_asan_meta(self, meta_file):
        with open(meta_file) as f:
            data = json.load(f)
            self.asan_dict = {item['Addr']:item['InstList'] for item in data}


    def print_stack_poisoning(self, code, fun_addr):
        op_str = ' '.join(code.code.split()[1:])
        reg = op_str.split(', ')[1]
        dest = op_str.split(', ')[0]
        self.write_code('#------- STACK POISON %s %s------'%(fun_addr, code.addr))
        self.write_code('\tlea %s, %s'%(reg, dest))
        self.write_code('\tshr %s, 0x3'%(reg))
        self.write_code('\tmov BYTE PTR [%s+0x7fff8000], 0xff'%(reg))
        self.write_code('#----------------------------------')

    def print_stack_unpoisoning(self, code, fun_addr):
        op_str = ' '.join(code.code.split()[1:])
        reg = op_str.split(', ')[0]
        dest = op_str.split(', ')[1]
        self.write_code('#------- STACK UNPOISON %s %s------'%(fun_addr, code.addr))
        self.write_code('\tlea %s, %s'%(reg, dest))
        self.write_code('\tshr %s, 0x3'%(reg))
        self.write_code('\tmov BYTE PTR [%s+0x7fff8000], 0x0'%(reg))
        self.write_code('#----------------------------------')
        #print(code.code)

    def print_reassem_fun_code(self, fun_addr):
        fun_symbolizer = self.fun_dict[fun_addr]
        fun_info = self.fun_info_dict[fun_addr]
        reassem_code = fun_symbolizer.reassem_code[int(fun_addr, 16)]

        self.print_fun_brief_info(fun_addr, reassem_code)

        if fun_info.label == self.main_fun:
            self.print_section_name('.text')
            self.print_fun_type('main', bind_type='.globl')
            self.write_code('\t.align 8')
            self.write_code('main:')
        else:
            self.print_section_name('.text')
            self.print_fun_type(fun_info.label)
            self.write_code('\t.align 8')

        asan_meta = {item['Addr']:item for item in self.asan_dict[fun_addr]}
        bStackPoison = False
        poison_code = []
        for idx, code in enumerate(reassem_code):
            if code.label:
                if code.comment:
                    self.write_code('%-40s: %s'%(code.label))
                else:
                    self.write_code('%s:'%(code.label))
                continue

            if not code.code:
                self.write_code('%s'%(code.comment))
            else:
                if code.addr in poison_code:
                    pass
                elif code.addr in asan_meta and ('# %s '%(code.addr) in code.comment):
                    if bStackPoison and idx + 1 < len(reassem_code) and \
                        reassem_code[idx+1].code and reassem_code[idx+1].code.split()[-1] in ['FS:[0x28]']:
                            self.print_stack_unpoisoning(reassem_code[idx], fun_addr)
                    else:
                        meta = asan_meta[code.addr]
                        self.add_mem_check_instrument(fun_addr, code, meta)
                else:
                    if code.code.split()[-1] in ['FS:[0x28]']:
                        if reassem_code[idx+1].code.startswith('mov qword ptr'):
                            # stack poisoning
                            if self.bStack:
                                self.print_stack_poisoning(reassem_code[idx+1], fun_addr)
                                bStackPoison = True
                            poison_code.append(idx+1)

                if not code.comment:
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
        '''
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
        '''

    def add_mem_check_instrument(self, fun_addr, code, meta):
        reassem = code.code
        operands = reassem.split(',')

        for idx, acc_size in enumerate(meta['MemAccSize']):
            if acc_size in [8, 16, 32, 64]:

                operand = re.findall('\[.*\]', operands[idx])[0]

                # filter out 16 bit length operand (ex. movabs)
                ck = re.search('0x[a-f0-9]*', operand)
                if ck and len(ck[0]) > 10:
                    continue

                label = '.LC_ASAN_%x_%x'%(int(fun_addr, 16), int(code.addr, 16))

                self.write_code('#----------------------------------')
                # save register value
                self.write_code('\tmov fs:0x70, rdi')
                self.write_code('\tlea rdi, %s'%(operand))
                self.write_code('\tmov fs:0x78, rax')

                # save flag register
                self.write_code('\tseto al')
                self.write_code('\tlahf')
                self.write_code('\tmov fs:0x80, rax')

                # check shadow memory
                self.write_code('\tmov rax, rdi')
                self.write_code('\tshr rax, 0x3')
                #self.write_code('\tcmp BYTE PTR [rax+0x7fff8000], 0x0')
                self.write_code('\tmov al, BYTE PTR [rax+0x7fff8000]')
                self.write_code('\ttest al, al')
                self.write_code('\tje %s'%(label))

                if acc_size < 64:
                    self.write_code('\tand edi, 0x7')
                    #self.write_code('\tadd edi, 0x3')
                    self.write_code('\tmovsx eax, al')
                    self.write_code('\tcmp edi, eax')
                    self.write_code('\tjl %s'%(label))

                self.write_code('\tcall __asan_report_load%d@plt'%(int(acc_size/8)))

                self.write_code('%s:'%(label))

                # restore flag register
                self.write_code('\tmov rax, fs:0x80')
                self.write_code('\tadd al, 0x7f')
                self.write_code('\tsahf')

                # restore register value
                self.write_code('\tmov rax, fs:0x78')
                self.write_code('\tmov rdi, fs:0x70')

                self.write_code('#----------------------------------')

                return


    def print_asan_init(self):
        self.write_code('.section .init_array')
        self.write_code('.align 8')
        self.write_code('\t.quad asan.module_ctor')

        self.write_code('.section .fini_array')
        self.write_code('.align 8')
        self.write_code('\t.quad asan.module_dtor')

        self.write_code('.text')
        self.write_code('\t.align 16')
        self.write_code('asan.module_ctor:')
        self.write_code('\tpush rax')
        self.write_code('\tcall __asan_init@PLT')
        self.write_code('\tpop rax')
        self.write_code('\tret')

        self.write_code('.text')
        self.write_code('\t.align 16')
        self.write_code('asan.module_dtor:')
        self.write_code('\tpush rax')
        self.write_code('\tpop rax')
        self.write_code('\tret')

    def create_reassem_file(self, filename, bStack):
        self.bStack = bStack
        with open(filename, 'w') as fd:
            self.fd = fd
            self.print_reassem_code()
            self.print_asan_init()
        self.fd = None

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Serializer')
    parser.add_argument('bin_file', type=str)
    parser.add_argument('b2r2_meta_file', type=str)
    parser.add_argument('b2r2_asan_file', type=str)
    parser.add_argument('reassembly_file', type=str)
    parser.add_argument('--optimization', type=int, default=0)
    parser.add_argument('--syntax', type=str, default='intel')
    parser.add_argument('--no-endbr', dest='endbr', action='store_false')
    parser.add_argument('--with-stack-poisoning', dest='stack', action='store_true')

    args = parser.parse_args()

    sym = SuperAsan(args.bin_file, args.b2r2_meta_file, args.optimization, args.syntax)
    sym.read_asan_meta(args.b2r2_asan_file)
    sym.symbolize(args.endbr)
    sym.create_reassem_file(args.reassembly_file, args.stack)
    #sym.print_reassem_code()
    #sym.report_statistics()

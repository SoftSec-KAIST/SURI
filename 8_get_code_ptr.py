import os, pickle, glob
from elftools.elf.elffile import ELFFile
from collections import namedtuple
from reassessor.lib.types import InstType, DataType
import numpy as np
import multiprocessing

BuildConf = namedtuple('BuildConf', ['target', 'asm_file', 'key'])

global_key_list = []

def gen_option(input_root, output_root):
    ret = []
    global global_key_list
    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006']:
        for comp in ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']:
            for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
                for lopt in ['bfd', 'gold']:
                    sub_dir = '%s/%s/%s_%s'%(package, comp, opt, lopt)
                    input_dir = '%s/%s'%(input_root, sub_dir)

                    for target in glob.glob('%s/bin/*'%(input_dir)):

                        filename = os.path.basename(target)

                        if filename in ['416.gamess'] and opt not in ['o0']:
                            continue

                        asm_file = '%s/%s/%s/super/%s.s'%(output_root, sub_dir, filename, filename)

                        key = '%s_%s_%s_%s_%s'%(package, comp, opt, lopt, filename)
                        ret.append(BuildConf(target, asm_file, key))

                        global_key_list.append(key)
    return ret


class Stat:
    def __init__(self, conf):
        self.target = conf.target
        self.asm_file = conf.asm_file

    def get_addr(self, factor):
        addrx = 0
        for term in factor.terms:
            if isinstance(term, int):
                continue
            addrx += term.Address
        if addrx == 0: return 0,0

        return addrx, addrx + factor.num

    def check_factor(self, asm, factor):
        if factor.get_type() in [7]:
            if self.get_sec_name(factor.terms[0].get_value())[1] not in ['.text']:
                self.sym_list[8] += 1
            else:
                self.sym_list[7] += 1

        elif factor.get_type() in [3,4] and '%rip' in asm.asm_line:
            self.sym_list[factor.get_type()+2] += 1
        else:
            self.sym_list[factor.get_type()] += 1

        if factor.get_type() in [2,4,6]:
            base, addrx = self.get_addr(factor)
            if addrx != 0:
                self.xaddr_list.append((asm, base, addrx))
        elif factor.get_type() in [1,3,5]:

            if not isinstance(asm, InstType):
                return
            if not asm.asm_token.opcode.startswith('mov') and not asm.asm_token.opcode.startswith('lea'):
                return

            base, addrx = self.get_addr(factor)
            _, sec_name = self.get_sec_name(base)
            if sec_name in ['.text']:
                if base not in self.func_list:
                    msg = '%s:%s %s : %s is not func'%(self.target, hex(asm.addr), asm.asm_line, hex(base))
                    self.non_func_ptr_list.append(msg)

    def get_func_list(self):
        output = os.popen("readelf -s %s | grep FUNC | awk '{print $2}'"%(self.target)).read()
        return [int(item,16) for item in output.split()]


    def get_ptr_list(self):
        output = os.popen("grep 'RIP+fun_' %s | awk -F'RIP.fun_' '{print $2}' | awk -F'_' '{print $2}' | awk -F']' '{print $1}' "%(self.asm_file)).read()
        return [int(item,16) for item in output.split()]

    def examine(self):
        self.ptr_list = set(self.get_ptr_list())
        self.ptr_set = set(self.ptr_list)
        #self.func_set = set(self.get_func_list())


    def cleanup(self):
        self.sec_region_list = []
        self.xaddr_list = []


    def get_sec_name(self, addr):
        for idx, (sec_name, region) in enumerate(self.sec_region_list):
            if addr in region:
                return (idx, sec_name)
        return -1, ''

    def outside_check(self):
        for asm, base, xaddr in self.xaddr_list:
            bFound = False
            idx1, sec_name1 = self.get_sec_name(base)
            idx2, sec_name2 = self.get_sec_name(xaddr)

            if idx2 != -1:
                bFound = True

            if idx1 != idx2:
                self.outside.append('%s:%s %s [%d][from: %s -> to: %s ][ %s => %s ]'%(self.target, hex(asm.addr), asm.asm_line, bFound, hex(base), hex(xaddr), sec_name1, sec_name2))



def report(desc, sym_list, bSummary=True):
    tot = sym_list[0]
    if tot == 0:
        return
    if bSummary:
        print('%-20s : %6.3f%% %6.3f%% %6.3f%% %6.3f%% %6.3f%% %6.3f%% %6.3f%% %10d'%(desc,
            sym_list[1]/tot*100, sym_list[2]/tot*100, sym_list[8]/tot*100, sym_list[7]/tot*100,
            sym_list[3]/tot*100, sym_list[5]/tot*100, sym_list[6]/tot*100, sym_list[0]))
    else:
        print('%-70s : %6.3f%% %6.3f%% %6.3f%% %6.3f%% %6.3f%% %6.3f%% %6.3f%% %10d'%(desc,
            sym_list[1]/tot*100, sym_list[2]/tot*100, sym_list[8]/tot*100, sym_list[7]/tot*100,
            sym_list[3]/tot*100, sym_list[5]/tot*100, sym_list[6]/tot*100, sym_list[0]))


def job(conf):
    if os.path.exists('ptr_statistics/%s'%(conf.key)):
        return

    if not os.path.exists(conf.asm_file):
        return

    stat = Stat(conf)
    stat.examine()

    with open('ptr_statistics/%s'%(conf.key), 'w') as f:
        f.write('%d\n'%(len(stat.ptr_list)))
        for item in sorted(stat.ptr_set):
            f.write('%x\n'%(item))


class Manager:

    def __init__(self, input_root='./benchmark', reassem_root='./output'):
        self.stat_list = []
        self.input_root=input_root
        self.reassem_root=reassem_root
        self.config_list = gen_option(self.input_root, self.reassem_root)

    def run(self, core=1):

        if core and core > 1:
            p = multiprocessing.Pool(core)
            p.map(job, self.config_list)
        else:
            for conf in self.config_list:
                job(conf)

import argparse
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('reassem', type=str, help='reassem path')
    parser.add_argument('--package', type=str, help='Package')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--skip', action='store_true')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    mgr = Manager(reassem_root=args.reassem)

    if not args.skip:
        os.system('mkdir -p ./ptr_statistics')
        if args.core:
            mgr.run(args.core)
        else:
            mgr.run()


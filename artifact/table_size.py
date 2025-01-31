import json
import argparse
import pickle
import os, sys
import re
from json import JSONDecodeError

sys.path.append("../superSymbolizer")

from lib.CFGSerializer import construct_CFG
from lib.Misc import is_unsupported_instruction

REGISTERS_x64 = ['RAX', 'RBX', 'RCX', 'RDX', 'RSI', 'RDI', 'RBP', 'RSP', 'R8', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15']
REGISTERS = ['RAX', 'RBX', 'RCX', 'RDX', 'RSI', 'RDI', 'RBP', 'RSP', 'R8',
'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15', 'EAX', 'EBX', 'ECX', 'EDX',
'ESI', 'EDI', 'EBP', 'ESP','R8D', 'R9D', 'R10D', 'R11D', 'R12D', 'R13D',
'R14D', 'R15D', 'AX', 'BX', 'CX', 'DX', 'BP', 'SI', 'DI', 'SP', 'R8W', 'R9W',
'R10W', 'R11W', 'R12W', 'R13W', 'R14W', 'R15W', 'AH', 'BH', 'CH', 'DH', 'AL',
'BL', 'CL', 'DL', 'BPL', 'SIL', 'DIL', 'SPL', 'R8B', 'R9B', 'R10B', 'R11B',
'R12B', 'R13B', 'R14B', 'R15B']


class SuriCheck:
    def __init__(self):
        self.tables = 0
        self.entries = 0
        self.suri_entries = 0
        self.gt_inst = 0
        self.over_inst = 0
        pass

    def get_superset_addrs(self, fn_addr, BBLs, syntax, visit_log):
        leaders, _ = construct_CFG(fn_addr, BBLs, syntax, visit_log)
        addr_set = set()
        duplicated_addrs = set()
        for leader in leaders:
            start = int(leader, 16)
            end = BBLs[leader]['Size'] + start

            new_addrs = set([item['Addr'] for item in BBLs[leader]['Code']])

            duplicated_addrs = duplicated_addrs | (addr_set & new_addrs)
            addr_set = addr_set | new_addrs

        if duplicated_addrs:
            print('\t[-] WARN %s has duplicated instruction'%(fn_addr), duplicated_addrs)

        return addr_set



    '''
    def check_under_approx(under_approx, b2r2_data, fde_start):
        superset = set()
        for (key,item) in b2r2_data.items():
            if item['FDEStart'] == fde_start:
                superset = superset | construct_CFG(item['Addr'], item['BBLs'])
        return under_approx - superset
    '''
    def check(self, fn_addr, asm_data, b2r2_data, nop_region, visit_log, robust):
        superset_data = b2r2_data['FunDict']

        if robust and fn_addr not in superset_data:
            return 0, 0
        super_fun = superset_data[fn_addr]
        superset_addrs = self.get_superset_addrs(fn_addr, super_fun['BBLs'], 'intel', visit_log)

        under_approx = set(asm_data['inst_addrs']) - superset_addrs - nop_region

        #--------------
        gt_br_dict = {item['addr']:item['size'] for item in asm_data['jmp_tables']}
        suri_br_dict = {item['BaseAddr']:len(item['Entries']) for item in super_fun['JmpTables']}
        self.tables += len(asm_data['jmp_tables'])
        visited_table = set()
        for tbl in asm_data['jmp_tables']:
            if tbl['addr'] in visited_table:
                continue

            if tbl['addr'] in suri_br_dict:
                visited_table.add(tbl['addr'])
                self.entries += tbl['size']
            else:
                label = tbl['label']
                if re.search('^\.L[0-9]', label) or re.search('^\.LJ', label):
                    assert False, 'Missing!!'

        visited_table = set()
        for tbl in super_fun['JmpTables']:
            if tbl['BaseAddr'] in visited_table:
                continue
            if tbl['BaseAddr'] in gt_br_dict:
                self.suri_entries += len(tbl['Entries'])
            visited_table.add(tbl['BaseAddr'])

        #--------

        if super_fun['AbsorbingFun']:
            for absorber_addr in super_fun['AbsorbingFun']:
                absorber_fun = superset_data[absorber_addr]
                superset_addrs1 = self.get_superset_addrs(absorber_addr, absorber_fun['BBLs'], 'intel', visit_log)
                under_approx1 = set(asm_data['inst_addrs']) - superset_addrs1 - nop_region

                if len(under_approx) > len(under_approx1):
                    under_approx = under_approx1

        if under_approx:
            print("(WARN!) Superset missed instructions (%s: %s)"%(fn_addr, under_approx))
            '''
            under_approx = check_under_approx(under_approx, superset_data, super_fun['FDEStart'])
            if under_approx:
                print("(WARN!) Superset missed instructions (%s: %s)"%(fn_addr, under_approx))
            '''

        over_approx = superset_addrs - set(asm_data['inst_addrs'])
        if over_approx:
            #print("Superset overapproximated instructions (%s: %s)"%(fn_addr, over_approx))
            pass


        if asm_data['jmp_tables']:
            gt_tbl = {item['addr']:(item['size'], item['label']) for item in asm_data['jmp_tables']}
            b2r2_tbl = {item['BaseAddr']:item['Size'] for item in super_fun['JmpTables']}
            b2r2_tbl2 = {item['BaseAddr']:item['Entries'] for item in super_fun['JmpTables']}

            for tbl, (size, label) in gt_tbl.items():
                if tbl not in b2r2_tbl:
                    if re.search('^\.L[0-9]', label) or re.search('^\.LJ', label):
                        print("(WARN!) Superset Table miss table %s (%s)"%(tbl, label))
                else:
                    valid_size = 0
                    for entry in b2r2_tbl2[tbl]:
                        if entry not in superset_addrs:
                            valid = False
                            for fde in superset_data[fn_addr]['FDERanges']:
                                if fde['End'] == entry:
                                    valid = True
                            if not valid:
                                break
                        valid_size += 1

                    if size > valid_size: #b2r2_tbl[tbl]:
                        print('(WARN!) Table (%s) size is smaller than gt (%d vs %d)'%(tbl, size, valid_size))
                    if valid_size < b2r2_tbl[tbl]:
                        print('\t Eliminate invalid Table entries in (%s) (%d -> %d)'%(tbl, b2r2_tbl[tbl], valid_size))

        self.gt_inst += len(asm_data['inst_addrs'])
        self.over_inst += len(over_approx)

        return len(asm_data['inst_addrs']), len(over_approx)

    def report(self):
        print('Tables: ', self.tables)
        print('Entries: ', self.entries)
        print('SuriEntries: ', self.suri_entries)
        print('gt_inst: ', self.gt_inst)
        print('over_inst: ', self.over_inst)

def cmp(gt_file, b2r2_file, robust):
    f0 = open(os.path.dirname(gt_file) + '/gt.db', 'rb')
    db = pickle.load(f0)
    nop_region = set([hex(addr) for addr in db.aligned_region])
    visit_log = dict()
    with open(gt_file, 'r') as fd1:
        with open(b2r2_file, 'r') as fd2:
            gt = json.load(fd1)
            try:
                b2r2 = json.load(fd2)
            except JSONDecodeError:
                return

            gt_inst = 0
            over_inst = 0


            ck = SuriCheck()

            for fn_addr, data in gt.items():
                (len1,len2) = ck.check(fn_addr, data, b2r2, nop_region, visit_log, robust)
                gt_inst += len1
                over_inst += len2
            if gt_inst == 0:
                import pdb
                pdb.set_trace()
            print('Size Overhead: %f (%d/%d)'%((over_inst/gt_inst)*100, over_inst, gt_inst))
            ck.report()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='compare')
    parser.add_argument('gt_file', type=str)
    parser.add_argument('b2r2_file', type=str)
    parser.add_argument('--robust', action="store_true")
    args =  parser.parse_args()
    args.robust=True
    cmp(args.gt_file, args.b2r2_file, args.robust)

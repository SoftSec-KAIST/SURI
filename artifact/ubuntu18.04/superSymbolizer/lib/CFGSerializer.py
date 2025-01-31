from collections import namedtuple

from lib.Misc import is_unsupported_instruction, Instrumentation, InstType

BBLInfo = namedtuple('BBLInfo', ['Start', 'End', 'Fallthrough'])


def construct_CFG(root, BBLs, syntax, visit_log):
    leaders = []
    pred_dict = {}
    droppedBBLs = []
    queue = [("", root)]

    history = set()
    while queue:
        (pred, cur) = queue.pop()

        if cur not in pred_dict:
            pred_dict[cur] = []
        if pred not in pred_dict[cur]:
            pred_dict[cur].append(pred)

        if cur in leaders:
            continue

        bValid = True
        if cur not in visit_log:
            for inst in BBLs[cur]['Code']:
                if is_unsupported_instruction(inst['Disassem'], syntax):
                    print('[-] Unsupprted instruction %s %s' % (inst['Disassem'], inst['Addr']))
                    bValid = False
            if bValid:
                visit_log[cur] = True
            else:
                visit_log[cur] = False
        bValid = visit_log[cur]
        if bValid:
            leaders.append(cur)
        else:
            droppedBBLs.append(cur)

        if cur not in BBLs:
            continue

        for edge in BBLs[cur]['Edges']:
            if edge['EdgeType'] in ['IntraCJmpTrueEdge', 'IntraCJmpFalseEdge', 'IntraJmpEdge', 'CallEdge']:
                continue

            if (edge['From'], edge['To']) not in history:
                queue.append((edge['From'], edge['To']))
                history.add((edge['From'], edge['To']))

    if root not in leaders:
        return [], droppedBBLs + leaders
    return leaders, droppedBBLs


class CFGSerializer:

    def __init__(self, fun_addr, bbls, jmp_info, opt_level=0, syntax='intel'):
        self.root = fun_addr
        self._original_bbls = bbls
        self.jmp_info = jmp_info
        self.opt_level = opt_level
        self.syntax = syntax

        self.bbl_seq = {}
        self.overlapped_bbls = []
        self.bbl_addrs = {}

    def build_cfg(self, visit_log):

        self.br_dict, self.tbl_sym_dict, self.comment_dict = self.examine_br()

        leaders, droppedBBLs = construct_CFG(self.root, self._original_bbls, self.syntax, visit_log)

        regions = []
        for leader in leaders:
            start = int(leader, 16)
            end = self._original_bbls[leader]['Size'] + start
            ft = [int(entry['To'], 16) for entry in self._original_bbls[leader]['Edges'] if int(entry['To'],16) == end]
            if ft:
                regions.append(BBLInfo(start, end, ft[0]))
            else:
                regions.append(BBLInfo(start, end, 0))

        regions.sort()
        return regions, droppedBBLs

    def serialize(self, regions, fdeStart, fdeEnd):

        next_addr = 0

        queue = []
        overlap = []

        overlap_bbls = 0
        bbl_addrs = []
        for cur_bbl in regions:
            if cur_bbl.Start < fdeStart or (fdeEnd != 0 and fdeEnd <= cur_bbl.Start) :
                continue

            bbl_addrs.append(cur_bbl.Start)

            if cur_bbl.Start < next_addr:
                overlap.append(cur_bbl)
            else:
                if overlap:
                    last = queue.pop()
                    overlap.insert(0, last)

                    overlap_bbls += len(overlap)
                    sol = self.solve_overlap(overlap, next_addr)
                    queue.extend(sol)
                    overlap = []

                queue.append(cur_bbl)

            if cur_bbl.End > next_addr:
                next_addr = cur_bbl.End

        if overlap:
            last = queue.pop()
            overlap.insert(0, last)

            overlap_bbls += len(overlap)
            sol = self.solve_overlap(overlap, next_addr)
            queue.extend(sol)

        self.bbl_seq[fdeStart] = queue
        self.overlapped_bbls = overlap_bbls
        self.bbl_addrs[fdeStart] = bbl_addrs


    def solve_overlap(self, overlap, last_addr):
        queue = []
        visited = []
        first_bbl = overlap[0]
        comment = '\n# <--------- The Beginning of Overlapped Region (%s)'%(hex(first_bbl.Start))
        queue.append(Instrumentation(first_bbl.Start, comment, InstType.Comment, None))

        while overlap:
            cur_bbl = overlap[0]
            next_addr = cur_bbl.End
            comment = '# Overlapped Region <<<<< %s'%(hex(cur_bbl.Start))
            queue.append(Instrumentation(cur_bbl.Start, comment, InstType.Comment, None))
            queue.append(cur_bbl)
            visited.append(cur_bbl.Start)
            debugMsg = '\t\t\t[*] Serialize: 0x%x-0x%x'%(cur_bbl.Start, cur_bbl.End)
            for tmp_bbl in overlap:
                if tmp_bbl.Start == next_addr:
                    cur_bbl = tmp_bbl
                    queue.append(cur_bbl)
                    visited.append(cur_bbl.Start)
                    next_addr = cur_bbl.End
                    debugMsg += ', 0x%x-0x%x'%(cur_bbl.Start, cur_bbl.End)

                    if cur_bbl.Fallthrough != cur_bbl.End:
                        break

            overlap = list(filter(lambda item: item[0] not in visited, overlap))

            # jump to the next block
            if next_addr == last_addr:
                if overlap:
                    comment = '# Jump to next block >>>> %s'%(hex(last_addr))
                    queue.append(Instrumentation(next_addr, comment, InstType.JMP, None))
            elif next_addr in visited and cur_bbl.Fallthrough == cur_bbl.End:
                comment = '# Jump to next block >>>> %s' % (hex(next_addr))
                queue.append(Instrumentation(next_addr, comment, InstType.JMP, None))

        comment = '# <--------- The End of Overlapped Region (%s)\n'%(hex(last_addr))
        queue.append(Instrumentation(last_addr, comment, InstType.Comment, None))
        return queue


    def examine_br(self):
        jmp_sites = self.jmp_info.keys()

        queue = []
        history = []
        determined_ref_site_list = []
        for jmp_site in jmp_sites:
            patterns = self.jmp_info[jmp_site]

            tables = set([hex(item['TblAddr']) for item in patterns])
            if (self.opt_level >= 3 and len(tables) == 1) or self.opt_level >= 4:
                for pattern in patterns:
                    determined_ref_site_list.extend([item['SiteInfo']['Addr'] for item in pattern['TblRefSite']])


        for jmp_site in jmp_sites:
            patterns = self.jmp_info[jmp_site]

            tables = set([hex(item['TblAddr']) for item in patterns])
            pattern_set = set()

            is_single_table_candidate = False
            if (self.opt_level >= 3 and len(tables) == 1) or self.opt_level >= 4:
                is_single_table_candidate = True

            mem_acc_addr = ''
            for pattern in patterns:
                msg = '# JmpSite:%s, AddSite:%s, MemAccSite:%s'%(
                pattern['JmpSite']['Addr'], pattern['AddSite']['Addr'],
                pattern['MemAccSite']['Addr'])

                refs = [item['SiteInfo']['Addr'] for item in pattern['TblRefSite']]

                for ref in pattern['TblRefSite']:
                    if ref['IsDeterminate'] or is_single_table_candidate:
                        comment = '# @%s, table addr is assigned to %s before mem access '%(
                            ref['SiteInfo']['Addr'],  ref['SiteInfo']['Regs'][0])
                        if comment not in history:
                            queue.append(Instrumentation(int(ref['SiteInfo']['Addr'], 16),
                                comment, InstType.TBL_SYM, ref['SiteInfo']['Regs']))
                            history.append(comment)

                msg += ', TblRefSite:' + str(refs)
                msg += ', TblAddr:%s'%(hex(pattern['TblAddr']))
                pattern_set.add(msg)

                comment = msg
                if comment not in history and not is_single_table_candidate:
                    # Register Instrumentation Address
                    for tblRef in pattern['TblRefSite']:
                        if tblRef['SiteInfo']['Addr'] in determined_ref_site_list:
                            continue
                        queue.append(Instrumentation(int(pattern['MemAccSite']['Addr'], 16),
                            comment, InstType.BR_SYM, [tblRef['SiteInfo']['Regs'], pattern['TblAddr']]))
                    history.append(comment)

                mem_acc_addr = int(pattern['MemAccSite']['Addr'], 16)

            if len(tables) > 1:
                comment = '# [*] Multiple Candidates @%s: %s'%(jmp_site, tables)
                queue.append(Instrumentation(mem_acc_addr, comment, InstType.Comment, None))
                if len(pattern_set) > 1:
                    for pattern in pattern_set:
                        comment = '# %s'%(pattern)
                        queue.append(Instrumentation(mem_acc_addr, comment, InstType.Comment, None))
                        pass

            inst_site = set([item['MemAccSite']['Addr'] for item in patterns])
            if len(inst_site) > 1:
                comment = '# [*] Multiple Instrumentation points @%s: %s'%(jmp_site, inst_site)
                queue.append(Instrumentation(mem_acc_addr, comment, InstType.Comment, None))


        br_dict = dict()
        tbl_sym_dict = dict()
        comment_dict = dict()
        for job in queue:
            if job.inst_type == InstType.BR_SYM:
                if hex(job.addr) not in br_dict:
                    br_dict[hex(job.addr)] = []
                br_dict[hex(job.addr)].append(job)
            elif job.inst_type == InstType.TBL_SYM:
                if hex(job.addr) not in tbl_sym_dict:
                    tbl_sym_dict[hex(job.addr)] = []
                tbl_sym_dict[hex(job.addr)].append(job)
            elif job.inst_type == InstType.Comment:
                if hex(job.addr) not in comment_dict:
                    comment_dict[hex(job.addr)] = []
                comment_dict[hex(job.addr)].append(job)
            else:
                pass

        return br_dict, tbl_sym_dict, comment_dict

    def get_code(self, job):
        bbl_addr = hex(job.Start)
        return self._original_bbls[bbl_addr]['Code']

    def get_comments(self, inst):
        if inst['Addr'] in self.comment_dict:
            return self.comment_dict[inst['Addr']]
        return []

    def need_instrumentation(self, inst):
        return inst['Addr'] in self.br_dict

    def need_direct_symbolize(self, inst):
        return inst['Addr'] in self.tbl_sym_dict

    def get_br_insts(self, inst):
        return self.br_dict[inst['Addr']]

    def need_transformation(self, inst, label_location):
        if inst['IsBranch']:
            disassem = inst['Disassem']
            opcode = disassem.split()[0]
            if opcode.startswith('loop'):
                pc = int(inst['Addr'], 16)
                args = disassem.split()[1:]
                offset = eval(args[-1])
                target = pc + offset
                if target != label_location:
                    return True
            if opcode in ['jrcxz', 'jecxz', 'jcxz']:
                return True

        return False

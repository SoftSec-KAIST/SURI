import re
from superSymbolizer.lib.CFGSerializer import CFGSerializer
from superSymbolizer.lib.ExceptTable import EHTable
from superSymbolizer.lib.Misc import RelocExpr, Instrumentation, InstType, REGISTERS, is_register, REGISTERS_x64, is_unsupported_instruction

pattern = re.compile('\[(.*)\]')

class LocalSymbolizer:
    def __init__(self, fun_addr, fun_id, fun_label, fun_info, fun_info_dict, plt_dict, opt_level=0, syntax='intel',
                 disable_super_symbolize = False):
        self.fun_addr = fun_addr
        self.addr = int(fun_addr, 16)
        self.fun_label = fun_label
        self.fun_id = fun_id
        self.fun_info_dict = fun_info_dict
        self.plt_dict = plt_dict
        self.refer_funs = set()
        self.opt_level = opt_level
        self.syntax = syntax
        if disable_super_symbolize:
            self.super_symbolize = False
        else:
            self.super_symbolize = True

        self.bbls = fun_info['BBLs']
        self.jmp_info = fun_info['JmpInfo']
        self.jmp_tbls = fun_info['JmpTables']
        self.FDERanges = self.create_fde_list(fun_info['FDERanges'])

        self.falseBBLs = fun_info['FalseBBLs']
        self.tbl_list = self.get_jtable_list()

        self.reassem_code = []
        self.reassem_tbl = {}
        self.endbr_list = []

        self.no_bbls = 0
        self.no_overlapped_bbls = 0
        self.total_br_sites = 0
        self.multi_br_sites = 0
        self.local_label_dict = {}
        self.visited_local_labels = []
        self.stack_height = 0

        self.data_labels = []
        self.jtable_dict = {}
        self.instrument_label_dict = {}
        self.rip_access_addrs = []

    def create_fde_list(self, fde_info):
        fde_dict = {int(item['Start'], 16): int(item['End'], 16) for item in fde_info}
        fde_list = []
        for fdeStart in sorted(list(fde_dict.keys())):
            new_end = fde_dict[fdeStart]
            b_update = False
            for idx, item in enumerate(fde_list):
                if fdeStart in item:
                    new_end = max(item.stop, new_end)
                    fde_list[idx] = range(item.start, new_end )
                    b_update = True
                    break
            if not b_update:
                fde_list.append(range(fdeStart, new_end))
        fde_ranges = []
        for item in fde_list:
            fde_ranges.append({'Start':hex(item.start), 'End':hex(item.stop)})
        return fde_ranges

    def add_false_block_labels(self, reassem_code):
        visited_false_labels = []
        for falseBBL in self.falseBBLs:
            falseLeader = int(falseBBL, 16)
            if falseLeader in self.visited_local_labels:
                visited_false_labels.append(falseLeader)
        if visited_false_labels:
            comments = ['#----------------------------------------',
                        '# the definition of false BBLs',
                        '#----------------------------------------']
            for comment in comments:
                reassem_code.append(self.emit_comment('' , comment))
            for falseLeader in visited_false_labels:
                reassem_code.append(self.emit_local_label(falseLeader))
            reassem_code.append(self.emit_code('', 'call abort@PLT'))
        return reassem_code

    def run(self, cfi_dict, reloc_sym_dict, rip_access_list, visit_log):
        self.reassem_code = self.symbolize_fun(cfi_dict, reloc_sym_dict, visit_log)
        if self.reassem_code:
            self.reassem_tbl = self.symbolize_jtables(rip_access_list)
            self.reassem_code[self.addr] = self.add_false_block_labels(self.reassem_code[self.addr])

    def get_jtable_list(self):

        tbl_list = []
        for tbl in self.jmp_tbls:
            base_addr = int(tbl['BaseAddr'], 16)
            tbl_list.append(base_addr)
        return tbl_list

    def symbolize_jtables(self, rip_access_list):

        tbl_dict = dict()

        for tbl in self.jmp_tbls:

            jmp_site = tbl['JmpSite']
            base_addr = int(tbl['BaseAddr'], 16)
            if base_addr in tbl_dict:
                label = tbl_dict[base_addr][0].label
                code = tbl_dict[base_addr][0].code
                comment = tbl_dict[base_addr][0].comment + ', %s'%(jmp_site)
                tbl_dict[base_addr][0] = RelocExpr(base_addr, label, code, comment)
                continue
            else:
                size = tbl['Size']
                entries = tbl['Entries']

                reassem_code = []

                base_label = self.get_jt_label(base_addr)
                code = ''
                comment = '# jmp site(s): %s'%(jmp_site)
                reassem_code.append(RelocExpr(base_addr, base_label, code, comment))

                overlap = False
                for idx, entry in enumerate(entries):
                    target =  int(entry, 16)
                    target_label = self.get_local_label(target)

                    addr = base_addr + idx * 4

                    if idx > 0 and rip_access_list and (base_addr + idx * 4) in rip_access_list:
                        comment = '# Decrease size of jump Table (%s:%d) in (%s) since there is a memory access to %s'%\
                                  (hex(base_addr), idx, self.fun_addr, hex(base_addr + idx * 4))
                        reassem_code.append(self.emit_comment(addr, comment))
                        break

                    if not target_label or target_label.startswith('.LfalseBBL'):
                        comment = '# Decrease size of jump Table (%s:%d) in (%s) since the table has invalid entry'%\
                                  (hex(base_addr), idx, self.fun_addr)
                        reassem_code.append(self.emit_comment(addr, comment))
                        break
                    assert target_label

                    code = '.long %s - %s'%(target_label, base_label)
                    comment = '# %s'%(hex(addr))

                    if addr != base_addr and (overlap or addr in self.jmp_tbls):
                        comment += ' overlapped region'
                        overlap = True

                    reassem_code.append(self.emit_code(addr, code, comment))

                tbl_dict[base_addr] = reassem_code

        return tbl_dict


    def symbolize_fun(self, cfi_dict, reloc_sym_dict, visit_log):

        cfgSerializer = CFGSerializer(self.fun_addr, self.bbls, self.jmp_info, self.opt_level, self.syntax)
        regions, dropped_region = cfgSerializer.build_cfg(visit_log)
        if not regions:
            return []

        for falseBBL in dropped_region:
            self.falseBBLs.append(falseBBL)
        reassem_code = {}
        for fdeRange in self.FDERanges:
            fdeStart = int(fdeRange['Start'],16)
            fdeEnd =  int(fdeRange['End'], 16)
            cfgSerializer.serialize(regions, fdeStart, fdeEnd)
            self.make_local_labels(cfgSerializer, fdeStart)

        for fdeRange in self.FDERanges:
            fdeStart = int(fdeRange['Start'],16)
            fdeEnd =  int(fdeRange['End'], 16)
            if self.addr < fdeStart or fdeEnd <= self.addr:
                key = fdeStart
            else:
                key = self.addr
            symbolized_code = self.symbolize_disassem_code(cfgSerializer, fdeStart, fdeEnd, cfi_dict, reloc_sym_dict)
            if not symbolized_code:
                continue
            if key not in reassem_code:
                reassem_code[key] = []
            reassem_code[key].extend(symbolized_code)

        self.update_stat(cfgSerializer)

        return reassem_code

    def update_stat(self, serializer):
        self.no_bbls = sum([len(item) for (_,item) in serializer.bbl_seq.items()])
        self.no_overlapped_bbls = serializer.overlapped_bbls
        self.total_br_sites += len(serializer.br_dict)

        for _, tbl_info in serializer.br_dict.items():
            if len(set([tbl.comment.split('TblAddr:')[1] for tbl in tbl_info])) > 1:
                self.multi_br_sites += 1

        #self.multi_br_sites = len([patterns for patterns in serializer.br_dict.values() if len(patterns) > 10])

    def get_local_label(self, addr):
        if addr in self.local_label_dict:
            self.visited_local_labels.append(addr)
            return self.local_label_dict[addr]
        return ''

    def add_local_label(self, addr):
        self.local_label_dict[addr] = '.L%d_%x'%(self.fun_id, addr)

    def make_local_labels(self, serializer, fdeStart):
        for addr in serializer.bbl_addrs[fdeStart]:
            self.local_label_dict[addr] = '.L%d_%x'%(self.fun_id, addr)

        fdeStart_list = [int(item['Start'],16) for item in self.FDERanges]
        for item in self.FDERanges:
            fdeEnd = int(item['End'], 16)
            if fdeEnd not in fdeStart_list:
                self.local_label_dict[fdeEnd] = '.L%d_%x_end'%(self.fun_id, fdeEnd)

        for item in self.falseBBLs:
            addr = int(item, 16)
            self.local_label_dict[addr] = '.LfalseBBL_%d_%x'%(self.fun_id, addr)

    def create_false_local_label(self, addr):
        if addr not in self.local_label_dict:
            self.local_label_dict[addr] = '.LfalseBBL_%d_%x'%(self.fun_id, addr & 0xffffffff)
            self.falseBBLs.append(hex(addr))


    def get_jt_label(self, addr):
        if addr not in self.jtable_dict:
            label = '.Ljt_%d_%x'%(self.fun_id, addr)
            self.jtable_dict[addr] = label
        return self.jtable_dict[addr]

    def get_data_label(self, addr):
        if addr >= 0:
            label = '.Ldata_%x'%(addr)
        else:
            label = '.Ldata_minus_%x'%(-addr)
            #label = '.Ldata_%s'%( hex(addr & 0xffffffff).replace('0x',''))
        self.data_labels.append(label)
        return label

    def get_instrument_label(self, addr, idx=None):
        if addr in self.instrument_label_dict:
            return self.instrument_label_dict[addr]
        if idx is None:
            label = '.L%d_%x_inst_end'%(self.fun_id, addr)
        else:
            label = '.L%d_%x_inst_%d'%(self.fun_id, addr, idx)
        return label

    def has_self_loop(self, inst):
        if inst['IsBranch']:
            disassem = inst['Disassem']
            opcode = disassem.split()[0]
            args = disassem.split()[1:]
            if opcode not in ['ret'] and args[-1] in ['+0x0']:
                return True
        return False

    EHFUN_CNT = 0
    EHBB_CNT = 0
    EHTBL_CNT = 0

    def get_stack_height(self):
        if self.opt_level >= 2:
            return self.stack_height
        else:
            return -1

    def symbolize_disassem_code(self, serializer, fdeStart, fdeEnd, cfi_dict, reloc_sym_dict):

        reassem_code = []
        reassem_code.append(self.emit_directive('.text'))

        addr = self.fun_addr
        empty_code = ''

        cfi_info = None
        cfi_addr_set = set()
        bFound_cfi_start = False


        addr_set = set()
        for job in serializer.bbl_seq[fdeStart]:
            if not isinstance(job, Instrumentation):
                if hex(job.Start) in self.plt_dict:
                    continue

                for inst in serializer.get_code(job):
                    addr = int(inst['Addr'], 16)
                    if addr >= fdeStart:
                        addr_set.add(addr)
                    res = None
                    if 'endbr64' in inst['Disassem']:
                        self.endbr_list.append(addr)
                    if self.syntax == 'intel':
                        if 'RSP-' in inst['Disassem']:
                            res = re.findall('RSP-([0-9a-fx]*)', inst['Disassem'])

                    else:
                        if '%RSP' in inst['Disassem']:
                            res = re.findall('-([0-9a-fx]*)\(%RSP\)', inst['Disassem'])
                    if res:
                        try:
                            stack_height = int(res[0], 16)
                            if stack_height >= 0 and stack_height <= 0x8000000:
                                self.stack_height = stack_height
                        except ValueError:
                            pass



        if fdeStart in cfi_dict:
            if (fdeStart in addr_set) or (fdeStart+1 in addr_set):
                cfi_info = cfi_dict[fdeStart]
                cfi_addr_set = set(cfi_info.cfi_dict.keys())

        unresolved_cfi_addr_set = cfi_addr_set - addr_set

        inst_cnt = 0
        for job in serializer.bbl_seq[fdeStart]:
            if isinstance(job, Instrumentation):
                if job.inst_type == InstType.Comment:
                    reassem_code.append(self.emit_comment(job.addr, job.comment))
                elif job.inst_type == InstType.JMP:
                    last_inst = reassem_code[-1]
                    if not last_inst.code or last_inst.code.split()[0] not in ['jmp', 'loop', 'loope', 'loopne', 'ret']:
                        reassem_code.append(self.emit_jmp_code(job.addr, job.comment))

            else:
                if hex(job.Start) in self.plt_dict:
                    continue

                inst_cnt += 1
                # add a label of BBL
                label_location = job.Start

                if label_location == self.addr:
                    reassem_code.append(self.emit_directive('.align 8'))
                    reassem_code.append(self.emit_fun_label())

                if (label_location == fdeStart or label_location == fdeStart+1) and not bFound_cfi_start:
                    bFirst = True
                else:
                    bFirst = False

                if bFirst and  cfi_info:
                    reassem_code.append(self.emit_cfi_start())
                    bFound_cfi_start = True

                    # TODO: add encoding rule
                    if cfi_info and cfi_info.except_tbl:

                        #encoding, eh_label_before, eh_label_after, eh_table = EHTable(cfi_info.except_tbl, fdeStart)
                        eh_table = EHTable(cfi_info.except_tbl, fdeStart, reloc_sym_dict, self)
                        entry_idx = len(reassem_code)


                reassem_code.append(self.emit_local_label(label_location))

                for inst in serializer.get_code(job):

                    if cfi_info and bFound_cfi_start:
                        addr = int(inst['Addr'], 16)
                        next_addr = addr + inst['Length']
                        reassem_code.extend(self.emit_cfi_directives(cfi_info.cfi_dict, addr))
                        if next_addr in unresolved_cfi_addr_set:
                            reassem_code.extend(self.emit_cfi_directives(cfi_info.cfi_dict, next_addr))
                            unresolved_cfi_addr_set.remove(next_addr)

                        # TODO: add eh_label_before
                        if cfi_info.except_tbl:
                            reassem_code.extend(self.emit_eh_frame_label(eh_table.get_after_label(addr), addr))
                            reassem_code.extend(self.emit_eh_frame_label(eh_table.get_before_label(addr), addr))

                    # add additional label if it has self loop (ex. jmp +0x0)
                    if int(inst['Addr'], 16) != job.Start and self.has_self_loop(inst):
                        label_location = int(inst['Addr'], 16)
                        self.add_local_label(label_location)
                        reassem_code.append(self.emit_local_label(label_location))

                    # add comment
                    comments = serializer.get_comments(inst)
                    if comments:
                        reassem_code.extend(self.emit_comments(inst['Addr'], comments))

                    # add instrumentation code if it needs
                    if self.super_symbolize and serializer.need_instrumentation(inst):
                        reassem_code.extend(self.emit_instrumentation_code(serializer, inst))

                    # symbolize assembly code
                    if serializer.need_direct_symbolize(inst):
                        reassem_code.append(self.emit_jt_symbolized_code(inst))
                    elif serializer.need_transformation(inst, label_location):
                        reassem_code.extend(self.emit_transformed_code(inst))
                    else:
                        reassem_code.append(self.emit_symbolized_asm(inst))


                    if cfi_info and bFound_cfi_start:
                        addr = int(inst['Addr'], 16)

                        # TODO: add eh_label_after
                        if cfi_info.except_tbl:

                            next_addr = addr + inst['Length']
                            if next_addr not in addr_set:
                                reassem_code.extend(self.emit_eh_frame_label(eh_table.get_after_label(next_addr), next_addr))

        # if there is no valid instructions, we return empty list
        if inst_cnt == 0:
            return []


        if bFound_cfi_start:
            reassem_code.append(self.emit_cfi_end())

        reassem_code.append(self.emit_local_label(fdeEnd, bEnd=True))

        if bFound_cfi_start and cfi_info and cfi_info.except_tbl:
            if not eh_table.has_missing_labels():
                new_lines = []
                new_lines.extend(self.emit_eh_frame_label(eh_table.get_entry_label()))
                symname = self.get_data_label(cfi_info.except_tbl['f_addr'])
                new_lines.extend(self.emit_eh_frame(eh_table.get_encoding(symname)))
                reassem_code = reassem_code[:entry_idx] + new_lines + reassem_code[entry_idx:]

                reassem_code.extend(self.emit_eh_frame(eh_table.get_eh_table()))

        return reassem_code

    def emit_eh_frame_label(self, eh_labels, addr=''):
        if eh_labels:
            return [RelocExpr(addr,label, '', '') for label in eh_labels]
        else:
            return []

    def emit_eh_frame(self, eh_directives, addr=''):
        if eh_directives:
            return [RelocExpr(addr,'', directive, '') for directive in eh_directives]
        else:
            return []

    def emit_cfi_directives(self, cfi_dict, addr):
        if addr in cfi_dict:
            directives = cfi_dict[addr]
            return [RelocExpr('','', directive, '') for directive in directives]
        else:
            return []
    def emit_cfi_start(self):
        directive = '.cfi_startproc'
        return RelocExpr('', '', directive,'')

    def emit_cfi_end(self):
        directive = '.cfi_endproc'
        return RelocExpr('', '', directive,'')

    def emit_instrumentation_code(self, serializer, inst):
        reassem_code = []
        regs = []

        # add abort code for debugging
        if self.opt_level >= 3:
            debug = False
        else:
            debug = True

        for br_inst in serializer.get_br_insts(inst):
            regs.extend(br_inst.args[0])

        for reg in REGISTERS:
            if reg not in regs:
                tmp_reg = reg
                break

        reassem_code.extend(self.emit_push_code(inst['Addr'], tmp_reg))

        no_br = len(serializer.get_br_insts(inst))
        is_last = False
        for idx, br_inst in enumerate(serializer.get_br_insts(inst)):
            if no_br == idx+1:
                is_last = True
            reassem_code.extend(self.emit_resymbolize_code(inst['Addr'], br_inst, tmp_reg, idx, is_last, debug))

        if debug:
            reassem_code.append(self.emit_abort_code(inst['Addr']))

        reassem_code.append(self.emit_instrument_label(inst['Addr']))

        reassem_code.extend(self.emit_pop_code(inst['Addr'], tmp_reg))

        return reassem_code


    def emit_transformed_code(self, inst):
        disassem = inst['Disassem']
        opcode = disassem.split()[0]
        args = disassem.split()[1:]
        addr =  inst['Addr']
        pc = int(inst['Addr'], 16)
        offset = eval(args[-1])
        target = pc + offset
        idx = 0

        reassem_code = []

        reassem_code.append(self.emit_hyphen_comment())
        symbolized_reassem = self.symbolize_pc_addressing(disassem, inst['Addr'])
        comment = '# transform instruction: %s'%(symbolized_reassem)
        reassem_code.append(self.emit_comment(pc, '%-44s # %s'%(comment, hex(pc))))

        if opcode.startswith('loop'):
            #reassem_code.append(self.emit_pushf())
            reassem_code.extend(self.emit_new_pushf())
            if self.syntax == 'intel':
                reassem_code.append(self.emit_code(addr, 'dec RCX'))
            else:
                reassem_code.append(self.emit_code(addr, 'dec %RCX'))

            end_of_instrument_label = self.get_instrument_label(pc, idx)
            if opcode in ['loop']:
                reassem_code.append(self.emit_code(addr, 'jz %s'%(end_of_instrument_label)))
            if opcode in ['loope']:
                reassem_code.append(self.emit_code(addr, 'jz %s'%(end_of_instrument_label)))
            if opcode in ['loopne']:
                reassem_code.append(self.emit_code(addr, 'jnz %s'%(end_of_instrument_label)))

            #reassem_code.append(self.emit_popf())
            reassem_code.extend(self.emit_new_popf())

            symbolized_reassem = self.symbolize_pc_addressing('jmp %s'%(hex(offset)), inst['Addr'])
            reassem_code.append(self.emit_code(addr, symbolized_reassem))

            reassem_code.append(self.emit_instrument_label(inst['Addr'], idx))
            #reassem_code.append(self.emit_popf())
            reassem_code.extend(self.emit_new_popf())

        elif opcode in ['jrcxz', 'jecxz', 'jcxz']:
            #reassem_code.append(self.emit_pushf())
            reassem_code.extend(self.emit_new_pushf())

            if opcode in ['jrcxz']:
                if self.syntax == 'intel':
                    reassem_code.append(self.emit_code(addr, 'cmp RAX, 0x0'))
                else:
                    reassem_code.append(self.emit_code(addr, 'cmp $0x0, %RAX'))
            if opcode in ['jecxz']:
                if self.syntax == 'intel':
                    reassem_code.append(self.emit_code(addr, 'cmp EAX, 0x0'))
                else:
                    reassem_code.append(self.emit_code(addr, 'cmp $0x0, %EAX'))
            if opcode in ['jcxz']:
                if self.syntax == 'intel':
                    reassem_code.append(self.emit_code(addr, 'cmp AX, 0x0'))
                else:
                    reassem_code.append(self.emit_code(addr, 'cmp $0x0, %AX'))

            end_of_instrument_label = self.get_instrument_label(pc, idx)
            reassem_code.append(self.emit_code(addr, 'jne %s'%(end_of_instrument_label)))

            #reassem_code.append(self.emit_popf())
            reassem_code.extend(self.emit_new_popf())

            symbolized_reassem = self.symbolize_pc_addressing('jmp %s'%(hex(offset)), inst['Addr'])
            reassem_code.append(self.emit_code(addr, symbolized_reassem))

            reassem_code.append(self.emit_instrument_label(inst['Addr'], idx))
            #reassem_code.append(self.emit_popf())
            reassem_code.extend(self.emit_new_popf())
        else:
            assert False

        reassem_code.append(self.emit_hyphen_comment())

        return reassem_code


    def emit_instrument_label(self, addr, idx = None):
        label = self.get_instrument_label(int(addr, 16), idx)
        return RelocExpr(addr, label, '','')


    def emit_directive(self, directive):
        return RelocExpr('', '', directive,'')

    def emit_fun_label(self, suffix=''):
        label = self.fun_label + suffix
        return RelocExpr(self.addr, label, '','')

    def emit_local_label(self, addr, bEnd=False):
        label = self.get_local_label(addr)
        if not bEnd and label.endswith('_end'):
            label = ''
        if bEnd and not label.endswith('_end'):
            label = ''
        return RelocExpr(addr, label, '','')

    def emit_code(self, addr, code, comment=''):
        return RelocExpr(addr, '', code, comment)

    def emit_hyphen_comment(self):
        comment = '#------------------------'
        return self.emit_comment('' , comment)

    def emit_pushf(self):

        code = 'pushf'
        comment = '# push flags'
        return self.emit_code('', code, comment)

    def emit_new_pushf(self, has_side_effect=True, reg=''):
        if not reg:
            reg = 'R11'

        inst_list = []

        if self.get_stack_height() < 0:
            if self.syntax == 'intel':
                code = 'mov fs:0x58, %s'%(reg)
            else:
                code = 'mov %%%s, %%fs:0x58'%(reg)
            comment = '# save a value in register %s'%(reg)
            inst_list.append(self.emit_code('', code, comment))

            '''
            if self.syntax == 'intel':
                code = 'mov %s, qword ptr [RSP-8]'%(reg)
            else:
                code = 'movq -0x8(%%RSP), %%%s' % (reg)
            comment = '# get the value in [RSP-8]'
            inst_list.append(self.emit_code('', code, comment))

            if self.syntax == 'intel':
                code = 'mov fs:0x50, %s' % (reg)
            else:
                code = 'mov %%%s, %%fs:0x50' % (reg)
            comment = '# save a value in [RSP-8]'
            inst_list.append(self.emit_code('', code, comment))
            '''
        else:
            if self.syntax == 'intel':
                code = 'mov [RSP-%s], %s'%(self.get_stack_height() + 0x100, reg)
            else:
                code = 'mov %%%s, -%s(%%RSP)'%(reg, self.get_stack_height() + 0x100)
            comment = '# save a value to stack [RSP-%s]'%(self.get_stack_height ()+ 0x100)
            inst_list.append(self.emit_code('', code, comment))

        if self.opt_level == 0 or has_side_effect:
            '''
            code = 'pushf'
            '''
            comment = '# push flags'

            if reg != 'RAX':
                if self.syntax == 'intel':
                    code = 'mov fs:0x60, RAX'
                else:
                    code = 'mov %RAX, %fs:0x60'
                inst_list.append(self.emit_code('', code, comment))

            if self.syntax == 'intel':
                code = 'seto al'
            else:
                code = 'seto %al'
            inst_list.append(self.emit_code('', code, comment))
            code = 'lahf'
            inst_list.append(self.emit_code('', code, comment))
            if self.syntax == 'intel':
                code = 'mov fs:0x68, RAX'
            else:
                code = 'mov %RAX, %fs:0x68'
            inst_list.append(self.emit_code('', code, comment))

            if reg != 'RAX':
                if self.syntax == 'intel':
                    code = 'mov RAX, fs:0x60'
                else:
                    code = 'mov %fs:0x60, %RAX'
                inst_list.append(self.emit_code('', code, comment))

        return inst_list

    def emit_new_popf(self, has_side_effect=True, reg=''):
        if not reg:
            reg = 'R11'

        inst_list = []

        if self.opt_level == 0 or has_side_effect:
            '''
            code = 'popf'
            '''
            comment = '# pop flags'

            if reg != 'RAX':
                if self.syntax == 'intel':
                    code = 'mov fs:0x60, RAX'
                else:
                    code = 'mov %RAX, %fs:0x60'
                inst_list.append(self.emit_code('', code, comment))

            if self.syntax == 'intel':
                code = 'mov RAX, fs:0x68'
            else:
                code = 'mov %fs:0x68, %RAX'
            inst_list.append(self.emit_code('', code, comment))

            if self.syntax == 'intel':
                code = 'add al, 0x7f'
            else:
                code = 'add $0x7f, %al'
            inst_list.append(self.emit_code('', code, comment))

            code = 'sahf'
            inst_list.append(self.emit_code('', code, comment))

            if reg != 'RAX':
                if self.syntax == 'intel':
                    code = 'mov RAX, fs:0x60'
                else:
                    code = 'mov %fs:0x60, %RAX'
                inst_list.append(self.emit_code('', code, comment))

        if self.get_stack_height() < 0:
            '''
            if self.syntax == 'intel':
                code = 'mov %s, fs:0x50' % (reg)
            else:
                code = 'mov %%fs:0x50, %%%s' % (reg)
            comment = '# get a value in [RSP-8]'
            inst_list.append(self.emit_code('', code, comment))

            if self.syntax == 'intel':
                code = 'mov qword ptr [RSP-8], %s'%(reg)
            else:
                code = 'movq %%%s, -8(%%RSP)' % (reg)
            comment = '# restore the value in [RSP-8]'
            inst_list.append(self.emit_code('', code, comment))
            '''
            if self.syntax == 'intel':
                code = 'mov %s, fs:0x58' % (reg)
            else:
                code = 'mov %%fs:0x58, %%%s' % (reg)
            comment = '# restore a value in register %s' % (reg)
            inst_list.append(self.emit_code('', code, comment))
        else:
            if self.syntax == 'intel':
                code = 'mov %s, [RSP-%s]'%(reg, self.get_stack_height() + 0x100)
            else:
                code = 'movq -%s(%%RSP), %%%s' % (self.get_stack_height() + 0x100, reg)
            comment = '# load a value from stack [RSP-%s]'%(self.get_stack_height ()+ 0x100)
            inst_list.append(self.emit_code('', code, comment))

        return inst_list

    def emit_popf(self):
        code = 'popf'
        comment = '# pop flags'
        return self.emit_code('', code, comment)

    def emit_push_code(self, addr, reg):
        reassem_code = []
        reassem_code.append(self.emit_hyphen_comment())
        reassem_code.extend(self.emit_new_pushf(has_side_effect=False, reg=reg))
        return reassem_code

    def emit_pop_code(self, addr, reg):
        reassem_code = []
        reassem_code.extend(self.emit_new_popf(has_side_effect=False, reg=reg))
        reassem_code.append(self.emit_hyphen_comment())

        return reassem_code

    def emit_abort_code(self, addr):
        code = 'call abort@PLT'
        comment = '# Unexpected cases'
        return self.emit_code(addr, code, comment)

    def emit_resymbolize_code(self, addr, br_inst, tmp_reg, idx, is_last, debug=False):
        reassem_code = []
        empty_code = ''

        if debug:
            is_last = False
            instruments = self.get_duumy_br_symbolize_code(br_inst, tmp_reg, idx)
            reassem_code.append(self.emit_code(addr, empty_code, br_inst.comment))
            for inst in instruments:
                reassem_code.append(self.emit_code(addr, inst))

        instruments = self.get_br_symbolize_code(br_inst, tmp_reg, idx, is_last)
        reassem_code.append(self.emit_code(addr, empty_code, br_inst.comment))
        for inst in instruments:
            reassem_code.append(self.emit_code(addr, inst))

        reassem_code.append(self.emit_instrument_label(addr, idx))

        return reassem_code

    def emit_jt_symbolized_code(self, inst):

        disasm = inst['Disassem']

        for seg in ['CS', 'DS', 'ES', 'FS', 'GS', 'SS']:
            if '[%s:'%(seg) in disasm:
                disasm = disasm.replace('[%s:'%(seg), '%s:['%(seg))

        words = disasm.split(',')

        if self.syntax == 'intel':
            target_str = re.search(pattern, words[1]).group(1)
            if 'RIP' in target_str:
                words[1] = words[1].replace('RIP','')
                target_str = target_str.replace('RIP','')
                #target_addr = int(target_str, 16)
                pc = int(inst['Addr'], 16) + int(inst['Length'])
            else:
                pc = 0
        else:
            pc = int(inst['Addr'], 16) + int(inst['Length'])
            target_str = words[0].split()[1].replace('(%RIP)','')
            for seg in ['CS', 'DS', 'ES', 'FS', 'GS', 'SS']:
                if '%%%s:'%(seg) in target_str:
                    target_str = target_str.replace('%%%s:'%(seg), '')

        target_addr = int(target_str, 16) + pc
        if target_addr in self.tbl_list:
            label = self.get_jt_label(target_addr)
        else:
            self.create_false_local_label(target_addr)
            label = self.get_local_label(target_addr)

        if self.syntax == 'intel':
            words[1] = words[1].replace(target_str, 'RIP+%s'%(label))
        else:
            words[0] = words[0].replace(target_str, label)

        reassem = ','.join(words)

        if target_addr in self.tbl_list:
            comment = '# %s contains table address'%(inst['Addr'])
        else:
            comment = '# %s contains table candidate but the function has no such table' % (inst['Addr'])
        return self.emit_code(inst['Addr'], reassem, comment)

    def emit_jmp_code(self, addr, comment):
        label = self.get_local_label(addr)
        if not label:
            for item in self.FDERanges:
                fdeStart = int(item['End'], 16)
                fdeEnd = int(item['End'], 16)
                if fdeStart <= addr and addr < fdeEnd:
                    assert label
            code = ''
            comment = ''
        else:
            code = 'jmp %s'%(label)
        return self.emit_code(addr, code, comment)


    def emit_comment(self, addr, comment):
        empty_code = ''
        return self.emit_code(addr, empty_code, comment)

    def emit_comments(self, addr, comments):
        reassem_code = []
        for comment in comments:
            reassem_code.append(self.emit_comment(addr, comment.comment))
        return reassem_code

    def build_byte_instr(self, inst):
        instr = '.byte '
        byte_str = inst['ByteString']
        for i in range(len(byte_str) // 2):
            if i == 0:
                instr += '0x%s' % byte_str[2*i:2*i+2]
            else:
                instr += ', 0x%s' % byte_str[2*i:2*i+2]
        return instr

    def fix_b2r2_disassembly_bugs(self, reassem, inst):

        opcode = reassem.split()[0]

        if self.syntax != 'intel':


            if opcode[:-1] in ['movssl', 'movsdq', 'movqq', 'subssl', 'addssl', 'ucomissl', 'divssl', 'divsdq', 'mulssl', 'fbldt', 'comisdq', 'comissl', 'cvtss2sdl', 'fdivq', 'fiaddw', 'fidivrw', 'fildw', 'fimulw', 'fstq', 'ldmxcsrl', 'maxsdq', 'movdl', 'movhpsq', 'mulsdq', 'stmxcsrl', 'subsdq', 'ucomisdq', 'vmovdl', 'vmovddupq', 'vmovqq', 'vpbroadcastbb', 'vpbroadcastqq', 'fbstpt', 'iretd', 'sgdtt', 'addsdq', 'cvttsd2siq', 'fisubw', 'fsubq', 'fsubrq', 'cvttps2piq', 'fmulq', 'movhpdq', 'fcompq', 'fisttpw', 'fidivw', 'movlpdq', 'larw', 'fdivrq', 'cvttss2sil', 'prefetcht0l', 'cvtsd2ssq', 'minssl', 'maxssl', 'minsdq', 'cvtsd2ssq', 'cmpssl', 'cmpsdq', 'cvtps2pdq', 'pinsrww', 'movlpsq', 'cvtdq2pdq', 'sqrtsdq', 'fcomq', 'ficomw', 'porq', 'cvtpi2psq', 'fistpw', 'fisubrw', 'pcmpeqbq', 'prefetchntal', 'ficompw', 'sidtt', 'sqrtssl', 'pslldq', 'pmaxswq', 'paddswq', 'pxorq', 'cvtps2piq', 'packuswbq', 'psubsbq', 'psadbwq', 'pcmpgtdq']:
                print('Error:', opcode)


            if opcode in ['movssl', 'movsdq', 'movqq', 'subssl', 'addssl', 'ucomissl', 'divssl', 'divsdq', 'mulssl', 'fbldt', 'comisdq', 'comissl', 'cvtss2sdl', 'fdivq', 'fiaddw', 'fidivrw', 'fildw', 'fimulw', 'fstq', 'ldmxcsrl', 'maxsdq', 'movdl', 'movhpsq', 'mulsdq', 'stmxcsrl', 'subsdq', 'ucomisdq', 'vmovdl', 'vmovddupq', 'vmovqq', 'vpbroadcastbb', 'vpbroadcastqq', 'fbstpt', 'iretd', 'sgdtt', 'addsdq', 'cvttsd2siq', 'fisubw', 'fstpq', 'fsubq', 'fsubrq', 'cvttps2piq', 'fmulq', 'movhpdq', 'fcompq', 'fisttpw', 'fidivw', 'movlpdq', 'larw', 'fdivrq', 'cvttss2sil', 'prefetcht0l', 'cvtsd2ssq', 'minssl', 'maxssl', 'minsdq', 'cvtsd2ssq', 'cmpssl', 'cmpsdq', 'cvtps2pdq', 'pinsrww', 'movlpsq', 'cvtdq2pdq', 'sqrtsdq', 'fcomq', 'ficomw', 'porq', 'cvtpi2psq', 'fistpw', 'fisubrw', 'pcmpeqbq', 'prefetchntal', 'ficompw', 'sidtt', 'sqrtssl', 'pslldq', 'pmaxswq', 'paddswq', 'pxorq', 'cvtps2piq', 'packuswbq', 'psubsbq', 'psadbwq', 'pcmpgtdq']:
                reassem = reassem.replace(opcode, opcode[:-1])

            # different suffix format: l -> s / q -> l
            if opcode == 'fldl': reassem = reassem.replace(opcode, 'flds')
            elif opcode == 'fldq': reassem = reassem.replace(opcode, 'fldl')
            elif opcode == 'faddl': reassem = reassem.replace(opcode, 'fadds')
            elif opcode == 'faddq': reassem = reassem.replace(opcode, 'faddl')
            # different suffix format: w -> s / l -> l / q -> ll
            elif opcode == 'fistw': reassem = reassem.replace(opcode, 'fists')
            elif opcode == 'fistpw': reassem = reassem.replace(opcode, 'fistps')
            elif opcode == 'fistpq': reassem = reassem.replace(opcode, 'fistpll')

            # Not a sufffix, but d -> l
            elif 'scasd' == reassem: reassem = 'scasl'
            elif 'insd' == reassem: reassem = 'insl'
            elif 'lodsd' == reassem: reassem = 'lodsl'
            elif 'stosd' == reassem: reassem = 'stosl'
            elif 'outsd' == reassem: reassem = 'outsl'
            elif 'repz scasd' == reassem: reassem = 'repz scasl'
            elif 'repz insd' == reassem:  reassem = 'repz insl'
            elif 'repz lodsd' == reassem: reassem = 'repz lodsl'
            elif 'repz stosd' == reassem: reassem = 'repz stosl'
            elif 'repz outsd' == reassem: reassem = 'repz outsl'

        else:
            if 'movsxd' in opcode:
                args = reassem.split()[1:]
                if args[0].startswith('E') and (args[1].startswith('dword') or args[1].startswith('E')):
                    reassem = self.build_byte_instr(inst)
            elif 'int1' in opcode:
                reassem = self.build_byte_instr(inst)

            # GAS does not allow tbyte ptr
            #if opcode in ['sgdt', 'sidt']:
            #    reassem = reassem.replace('tbyte ptr ', '')
            #if opcode in ['vfmsub231ss']:
            #    reassem = reassem.replace('qword ptr', 'dword ptr')
            #if opcode in ['call']:
            #    reassem = reassem.replace('qword far ptr', 'far ptr')
            #if opcode in ['vcvtsi2ss', 'vdivsd']:
            #    reassem = reassem.replace('ymm', 'xmm')
            #    reassem = reassem.replace('YMM', 'XMM')
            #if opcode in ['jmp']:
            #    reassem = reassem.replace('qword far ptr', 'far ptr')

        # GAS bug


        if self.syntax == 'intel':
            if opcode in ['lar', 'lsl']:
                if ',' in reassem and reassem.split()[1][:-1] in REGISTERS_x64:
                    reassem = reassem.replace(' word ', ' qword ')
                else:
                    reassem = reassem.replace(' word ', ' dword ')
            '''
            elif opcode in ['fdiv']:
                reassem = reassem.replace(opcode, 'fdivr')
            elif opcode in ['fdivr']:
                reassem = reassem.replace(opcode, 'fdiv')
            if opcode in ['vpand']:
                reassem = reassem.replace(opcode, 'vpandq')
            if opcode in ['vpor']:
                reassem = reassem.replace(opcode, 'vporq')
            '''
        else:
            if opcode in ['enter']:
                operand1 = reassem.split()[1][:-1]
                operand2 = reassem.split()[2]
                reassem = 'enter %s, %s'%(operand2, operand1)
            elif opcode in ['fsubp']:
                reassem = reassem.replace(opcode, 'fsubrp')
            elif opcode in ['fsubrp']:
                reassem = reassem.replace(opcode, 'fsubp')


        return reassem


    def emit_symbolized_asm(self, inst):
        comment = ''
        reassem = inst['Disassem']

        #fix representation issue
        for seg in ['CS', 'DS', 'ES', 'FS', 'GS', 'SS']:
            if '[%s:'%(seg) in reassem:
                reassem = reassem.replace('[%s:'%(seg), '%s:['%(seg))

        for idx, isRIP in enumerate(inst['RIPAddressing']):
            if isRIP:
                reassem = self.symbolize_rip_addressing(reassem, inst, idx)
                comment = 'symbolize RIP-relative addressing'

        for fpReg in range(8):
            if ' ST%d'%(fpReg) in reassem:      # intel syntax
                reassem = reassem.replace(' ST%d'%(fpReg), ' ST(%d)'%(fpReg))
            elif ' %%ST%d'%(fpReg) in reassem: # AT&T Syntax
                reassem = reassem.replace(' %%ST%d'%(fpReg), ' %%ST(%d)'%(fpReg))

        if is_unsupported_instruction(reassem, self.syntax):
            # print('[-] Unsupported instruction %s'%(reassem))
            reassem = '# ' + reassem
            comment = 'Unsupported instruction'
        else:
            #fix B2R2 disassembly bug
            reassem = self.fix_b2r2_disassembly_bugs(reassem, inst)

        if comment == '' and (inst['IsBranch'] or reassem.split()[0] in ['xbegin']):
            if reassem.split()[0] in ['ret'] or is_register(reassem.split()[1]):
                pass
            elif reassem.split()[0] in ['bnd'] and reassem.split()[1] in ['ret']:
                pass
            else:
                symbolized_reassem = self.symbolize_pc_addressing(reassem, inst['Addr'])
                if symbolized_reassem:
                    reassem = symbolized_reassem
                    comment = 'symbolize PC-relative addressing'

                    opcode = reassem.split()[0]
                    if opcode.startswith('loop') or opcode in ['jcxe', 'jecxz', 'jrcxz'] or reassem.startswith('repz ret'): # which has 1 byte offset
                        dest = reassem.split()[-1]
                        if 'falseBBL' in dest:
                            reassem = '# ' + reassem
                            comment = 'invalid loop instruction since it points to false block'

                else:
                    if reassem.split()[-1] in REGISTERS_x64:
                        pass
                    elif '[' not in reassem :
                        comment = ', fun %s miss the target of PC-relative addressing '%(self.fun_addr)

        comment = '# %s %s'%(inst['Addr'], comment)
        if self.syntax != 'intel':
            reassem = reassem.replace(' +', ' ')
            reassem = reassem.replace(':+', ':')
            reassem = reassem.replace('*+', '*')
        return self.emit_code(inst['Addr'], reassem, comment)

    def symbolize_rip_addressing(self, disasm, inst, idx):
        words = disasm.split(',')
        if self.syntax == 'intel':
            target_str = re.search(pattern, words[idx]).group(1)
            if 'RIP' in target_str:
                words[idx] = words[idx].replace('RIP', '')
                target_str = target_str.replace('RIP', '')
                pc = int(inst['Addr'], 16) + int(inst['Length'])
            else:
                pc = 0
        else:
            # TODO: Fix Index value
            idx = len(words) - 1 - idx
            target_str = re.search('(.*)\(%RIP\)', words[idx].split()[-1]).group(1)
            for seg in ['CS', 'DS', 'ES', 'FS', 'GS', 'SS']:
                if '%%%s:'%(seg) in target_str:
                    target_str = target_str.replace('%%%s:'%(seg), '')
            if target_str.startswith('*'):
                target_str = target_str[1:]
            pc = int(inst['Addr'], 16) + int(inst['Length'])


        target_addr = int(target_str, 16) + pc

        self.rip_access_addrs.append(target_addr)
        label = ''
        if target_addr in self.endbr_list:
            label = self.get_local_label(target_addr)

        if not label and self.is_endbr_fun(hex(target_addr)):
            label = self.get_other_fun_label(hex(target_addr))

        if not label:
            if disasm.split()[0] in ['vmovdqa64']:
                # FIXME: current b2r2 incorrectly disiassebly it.
                offset_str = inst['ByteString'][-8:]
                offset = 0
                for n in range(4):
                    tmp = int(offset_str[n*2:(n+1)*2], 16)
                    offset += tmp << (8 * n)
                    #print('fix:' , hex(offset))
                #print(offset_str)
                target_addr = offset + pc


            label = self.get_data_label(target_addr)

        if self.syntax == 'intel':
            words[idx] = words[idx].replace(target_str, 'RIP+%s'%(label))
        else:
            words[idx] = words[idx].replace(target_str, '%s' % (label))

        return ','.join(words)

    def symbolize_pc_addressing(self, disasm, pc):
        opcode = disasm.split()[0]
        if opcode in ['bnd']:
            opcode = disasm.split()[1]

        if self.syntax == 'intel':
            words = disasm.split()
            if ':' in words[-1]:
                return ''
        else:
            if '*' in disasm:
                return ''
            words = disasm.split()
        try:
            offset = eval(words[-1])
            target = int(pc, 16) + offset

            if opcode in ['call']:
                # search function dict first
                label = self.get_other_fun_label(hex(target))
                if not label:
                    label = self.get_local_label(target)
            else:
                if hex(target) in self.plt_dict:
                    label = self.plt_dict [hex(target)]
                else:
                    # search local dict first
                    label = self.get_local_label(target)
                    if not label:
                        label = self.get_other_fun_label(hex(target))
                        if not label:
                            self.create_false_local_label(target)
                            label = self.get_local_label(target)

                    elif label.endswith('_end') and self.get_other_fun_label(hex(target)):
                        label = self.get_other_fun_label(hex(target))

            #TODO: symbolize plt functions
            if label:
                return disasm.replace(words[-1],label)
            return ''

        except NameError:
            pass

        return ''

    def is_endbr_fun(self, addr):
        if addr in self.fun_info_dict:
            return self.fun_info_dict[addr].startsWithENDBR
        return False

    def get_other_fun_label(self, addr):
        if addr in self.fun_info_dict:
            self.refer_funs.add(addr)
            return self.fun_info_dict[addr].label
        return ''

    def get_br_symbolize_code(self, instr, tmp_reg, idx, is_last):
        ins_list = []
        reg1 = instr.args[0][0]
        reg2 = tmp_reg

        target_addr = instr.args[1]
        old_label = self.get_data_label(target_addr)
        new_label = self.get_jt_label(target_addr)

        escape_label = self.get_instrument_label(instr.addr)
        end_of_instrument_label = self.get_instrument_label(instr.addr, idx)

        if self.syntax == 'intel':
            ins_list.append('lea %s, [RIP+%s]'%(reg2, old_label))
            ins_list.append('cmp %s, %s'%(reg1, reg2))
            # goto next block
            ins_list.append('jne %s'%(end_of_instrument_label))
            ins_list.append('lea %s, [RIP+%s]'%(reg1, new_label))
            # goto mem access instruction
        else:
            ins_list.append('leaq %s(%%RIP), %%%s'%(old_label, reg2))
            ins_list.append('cmp %%%s, %%%s'%(reg2, reg1))
            # goto next block
            ins_list.append('jne %s'%(end_of_instrument_label))
            ins_list.append('leaq %s(%%RIP), %%%s'%(new_label, reg1))
            # goto mem access instruction

        if len(instr.args[0]) == 2:
            ins_list.append('%s:' % (end_of_instrument_label+'_1'))
            if self.syntax == 'intel':
                ins_list.append('mov %s, %s'%(instr.args[0][1], reg1 ))
            else:
                ins_list.append('mov %%%s, %%%s'%(reg1, instr.args[0][1]))

        if not is_last:
            ins_list.append('jmp %s'%(escape_label))

        return ins_list


    def get_duumy_br_symbolize_code(self, instr, tmp_reg, idx):
        ins_list = []
        reg1 = instr.args[0][0]
        reg2 = tmp_reg

        target_addr = instr.args[1]
        new_label = self.get_jt_label(target_addr)

        escape_label = self.get_instrument_label(instr.addr)
        end_of_instrument_label = self.get_instrument_label(instr.addr, idx)

        if self.syntax == 'intel':
            ins_list.append('lea %s, [RIP+%s]'%(reg2, new_label))
            ins_list.append('cmp %s, %s'%(reg1, reg2))
        else:
            ins_list.append('lea %s(%%RIP), %%%s'%(new_label, reg2))
            ins_list.append('cmp %%%s, %%%s'%(reg2, reg1))

        if len(instr.args[0]) == 2:
            ins_list.append('je %s'%(end_of_instrument_label+'_1'))
        else:
            # goto mem access instruction
            ins_list.append('je %s'%(escape_label))

        return ins_list

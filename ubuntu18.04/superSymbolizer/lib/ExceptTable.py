#!/usr/bin/env python3 -tt
#-*- coding: utf-8 -*-

import struct

def my_int(data, form='B'):
    if isinstance(data, str):
        return struct.unpack(form, data)[0]
    return data

def decode_uleb128(data):
    idx = 0
    res = 0
    while True:
        x = my_int(data[idx])

        res +=  (x & ~0x80) << (idx*7)
        if x & 0x80 == 0:
            return res, idx+1
        idx += 1


class LSDA_HEADER:
    def __init__(self, data):
        idx = 0

        self.lp_format = my_int(data[idx])
        idx += 1
        if self.lp_format != 0xff:# and self.lp_format != '\xff':
            self.lp_start = data[idx]
            idx += 1
            import pdb
            pdb.set_trace()
            assert False

        self.tt_format = my_int(data[idx])
        idx += 1
        if self.tt_format != 0xff:# and self.tt_format != '\xff':
            if self.tt_format not in [0x9b, 0x9c]:
                # DW_EH_PE_sdata4 = 0x9b
                # DW_EH_PE_sdata8 = 0x9c
                assert False
            if self.tt_format in [0x9c]:
                self.item_size = 8
            else:
                self.item_size = 4
            self.end_offset, length = decode_uleb128(data[idx:])
            idx += length
        else:
            self.end_offset = -1

        self.size = idx

    def print_rec(self):
        print('lp_format: %s, tt_format: %s'%(hex(self.lp_format), hex(self.tt_format)))

class LSDA_CALLSITE_ENTRY:
    def __init__(self, data):
        idx = 0
        self.start, length = decode_uleb128(data[idx:])
        idx += length
        self.length, length = decode_uleb128(data[idx:])
        idx += length
        self.landing_pad, length = decode_uleb128(data[idx:])
        idx += length
        self.action, length = decode_uleb128(data[idx:])
        idx += length

        self.data = data[:idx]
        self.idx = idx


    def print_rec(self, entry=0):
        landing_pad = 0
        if self.landing_pad != 0:
            landing_pad = entry + self.landing_pad
        print('%s-%s: %s [%s]'%(hex(entry+self.start), hex(entry+self.start+self.length), hex(landing_pad), hex(self.action)))
        #print(self.data)

class LSDA_TYPE_TABLE:
    def __init__(self, data, start_offset, item_size):
        self.tbl = []
        idx = 0
        while idx != len(data):
            #print(data[idx:])
            entry = LSDA_TYPE_ENTRY(data[idx:idx + item_size], idx + start_offset, item_size)
            self.tbl.append(entry)

            idx += item_size

class LSDA_TYPE_ENTRY:
    def __init__(self, data, offset, item_size):
        self.data = data
        #if len(data) < 4:
        #    import pdb
        #    pdb.set_trace()
        if item_size == 8:
            self.r_offset = struct.unpack('<Q',data)[0]
        else:
            self.r_offset = struct.unpack('<I',data)[0]
        self.offset = offset

    def get_addr(self, gcc_except_tbl_addr):
        return self.r_offset + self.offset + gcc_except_tbl_addr


class LSDA_ACTION_TABLE:
    def __init__(self, data):
        self.tbl = []
        self.size = 0
        if len(data) > 0:
            idx = 0
            while idx + 1 < len(data):
                entry = LSDA_ACTION_ENTRY(data[idx:idx+2])
                self.tbl.append(entry)
                idx += 2

            self.size = len(data)

    def print_rec(self):
        for item in self.tbl:
            item.print_rec()

class LSDA_ACTION_ENTRY:
    def __init__(self,data):
        self.filter = my_int(data[0])
        self.next = my_int(data[1])

    def print_rec(self):
        print('action: %d %d'%(self.filter, self.next))

class LSDA_CALLSITE_HEADER:
    def __init__(self,data):
        self.callsite_format = my_int(data[0])
        if self.callsite_format != 0x1: # and self.callsite_format != '\x01':
            assert False

        idx = 1
        #self.table_length = data[1]
        self.table_length, length = decode_uleb128(data[idx:])

        idx += length

        self.size = idx

    def print_rec(self):
        print('callsite header: region format: %s, table length: %s'%(self.callsite_format, self.table_length))


class GCCExceptTable:
    def __init__(self, elffile):
        self.elffile = elffile

        #import pdb
        #pdb.set_trace()
        self.section, self.sec_addr = self.get_gcc_except_table()

        self.except_dict = dict()
        #self.parse(self.section)
        #print(self.except_dict.keys())
    '''
    def parse(self, section):

        #import pdb
        #pdb.set_trace()

        #print(section)

        idx = 0
        end = len(section)
        while idx < end:
            lsda, length = self.parse_LSDA(section[idx:])
            self.except_dict[idx+self.sec_addr] = lsda
            idx += length
    '''
    def parse(self, addr):

        #import pdb
        #pdb.set_trace()

        #print(section)
        offset = addr - self.sec_addr
        if offset > len(self.section):
            offset = offset & 0xffffffff
        lsda, length = self.parse_LSDA(self.section[offset:])
        self.except_dict[addr] = lsda
        return lsda

    def parse_LSDA(self, data):

        header = LSDA_HEADER(data[:])
        header_size = header.size
        #header.print_rec()

        csHeader = LSDA_CALLSITE_HEADER(data[header_size:])
        header_size += csHeader.size
        #csHeader.print_rec()

        #table_cnt = int(csHeader.table_length / 4)
        region_table = []
        idx = 0
        table_end = header_size + csHeader.table_length
        action_set = set()
        while idx < csHeader.table_length:
            entry = LSDA_CALLSITE_ENTRY(data[header_size+idx:table_end])
            idx += entry.idx
            action_set.add(entry.action)

            #print('%d/%d: '%(idx, csHeader.table_length),end='')
            #entry.print_rec()
            region_table.append(entry)


        if header.end_offset > 0:

            type_end = header.size + header.end_offset

            action_tbl_start = header_size + csHeader.table_length

            if action_set == set([0]): action_end = 2 + action_tbl_start
            else: action_end = max(action_set) + 1 + action_tbl_start

            actions = LSDA_ACTION_TABLE(data[action_tbl_start:action_end])

            type_ids = set()
            for item in actions.tbl:
                if item.filter > 0 and item.filter < 0x7f:
                    type_ids.add(item.filter)


            type_start = type_end
            typeTable = None
            num_type = 0
            if type_ids:
                type_start -= header.item_size
                while type_start >= header_size + csHeader.table_length + actions.size:
                    typeTable = LSDA_TYPE_TABLE(data[type_start:type_end], type_start, header.item_size)
                    '''
                    if typeTable.tbl[0].r_offset == 0:
                        break
                    if typeTable.tbl[0].r_offset in [0x7d, 0x7d01, 0x7d0100]:
                        print(hex(typeTable.tbl[0].r_offset))
                    '''
                    type_start -= header.item_size
                    num_type += 1

                    if num_type >= max(type_ids):
                        break

            while action_end + 2 <= type_start:
                action_end += 2
                actions = LSDA_ACTION_TABLE(data[action_tbl_start:action_end])
                last_item = actions.tbl[-1]
                if last_item.filter < 0x7f and last_item.filter > 0:
                    type_ids.add(last_item.filter)
                    last_type_id = max(type_ids)
                    type_start = type_end - header.item_size * last_type_id
                    typeTable = LSDA_TYPE_TABLE(data[type_start:type_end], type_start, header.item_size)

                    if type_start < action_end:
                        print('[-] Warning: Invalid type table parsing')
                    #assert type_start >= action_end, 'Invalid type table parsing'

                if type_start == action_end: break
                if last_item.filter == 0 and last_item.next == 0: break

            if typeTable is None and type_ids:
                print('check1!!')

            elif type_ids and max(type_ids) != len(typeTable.tbl):
                print('check2!!')

            lsda_end = type_end
        else:
            actions = None
            typeTable = None
            lsda_end = header.size + csHeader.table_length
        '''
            if action_set == set([0]) and \
                    header_size + csHeader.table_length == header.size + header.end_offset:
                action = LSDA_ACTION_TABLE('')
            else:
                action_tbl_size = max(action_set) + 1
                if action_tbl_size == 1: action_tbl_size += 1

                action_tbl_start = header_size + csHeader.table_length
                action = LSDA_ACTION_TABLE(data[action_tbl_start:action_tbl_start+action_tbl_size])
            #action.print_rec()
            #print(data[header_size+csHeader.table_length:header_size+csHeader.table_length+action.size])

            type_start = header_size + csHeader.table_length + action.size
            type_start = int((type_start+3)/4) * 4

            if action.size == 0 and type_end - type_start > 0:
                print('check!!!')
            #print(hex(header_size))
            #print(hex(csHeader.table_length))
            #print(hex(action.size))
            #print(hex(header.end_offset))
            #print(data[type_start:type_end])

            typeTable = LSDA_TYPE_TABLE(data[type_start:type_end], type_start)

            lsda_end = type_end
        else:
            action = None
            typeTable = None
            lsda_end = header.size + csHeader.table_length
        '''
        res = dict()
        res['header'] = header
        res['csHeader'] = csHeader
        res['region_tbl'] = region_table
        res['action'] = actions
        res['type_tbl'] = typeTable

        return res, lsda_end
        #return (header, csHeader, region_table, action, types), end



    def get_gcc_except_table(self):
        for section in self.elffile.iter_sections():
            if section.name == '.gcc_except_table':
                return section.data(), section.header.sh_addr
        return '',0


EHFUN_CNT = 0
EHBB_CNT = 0
EHTBL_CNT = 0


class EHTable:
    def __init__(self, tbl, start_proc_addr, reloc_sym_dict, symbolizer):
        global EHFUN_CNT
        global EHTBL_CNT

        self.tbl = tbl
        self.start_proc_addr = start_proc_addr
        self.before_label_dict = dict()
        self.after_label_dict = dict()

        self.eh_fun_id = EHFUN_CNT
        self.label = dict()
        self.label['fun'] = '.LEHF%d' % (EHFUN_CNT)
        self.label['begin'] = '.LLSDA%d' % (EHTBL_CNT)
        self.label['ttype'] = '.LLSDATTD%d' % (EHTBL_CNT)
        self.label['cs_begin'] = '.LLSDACSB%d' % (EHTBL_CNT)
        self.label['cs_end'] = '.LLSDACSE%d' % (EHTBL_CNT)
        self.label['end'] = '.LLSDATT%d' % (EHTBL_CNT)

        # tsection = resdic['.text']

        EHFUN_CNT += 1
        EHTBL_CNT += 1
        # tsection.get(start_proc_addr).eh_label_before += '%s:\n' % (label['fun'])
        #label_dict[start_proc_addr] = '%s:\n' % (self.label['fun'])
        self.ref_sym_dict = dict()
        self.eh_table = self._create_eh_table(reloc_sym_dict, symbolizer)
        self.after_label_history = list()
        self.before_label_history = list()


    def get_entry_label(self):
        contents = []
        contents.append(self.label['fun'])
        return contents


    def get_eh_table(self):
        return self.eh_table

    def _create_eh_table(self, reloc_sym_dict, symbolizer):
        contents = []
        contents.append('.section .gcc_except_table,"a",@progbits')
        contents.append('#----------except table %s------------' % (hex(self.start_proc_addr)))
        contents.extend(self.get_LSDA_header())

        contents.append('#---------- table entries ------------')
        contents.append('%s:' % (self.label['cs_begin']))
        contents.extend(self.get_LSDA_tbl_entries())
        contents.append('%s:' % (self.label['cs_end']))

        contents.append('#---------- action info ------------')
        contents.extend(self.get_action_tbl_entries())
        contents.append('#---------- type info ------------')
        contents.append(' .p2align 2')
        contents.extend(self.get_type_tbl_entries(reloc_sym_dict, symbolizer))
        contents.append('%s:' % (self.label['end']))
        return contents

    def get_encoding(self, symname):
        encodings = []
        encodings.append('.cfi_personality 0x9b,%s' % (symname))
        encodings.append('.cfi_lsda 0x1b,%s' % (self.label['begin']))
        return encodings

    def get_LSDA_header(self):
        contents = []
        contents.append(' .p2align 2')
        contents.append('%s:' % (self.label['begin']))
        contents.append(' .byte %s' % (hex(self.tbl['header'].lp_format)))
        contents.append(' .byte %s' % (hex(self.tbl['header'].tt_format)))
        if self.tbl['header'].tt_format in [0x9b, 0x9c]:
            contents.append(' .uleb128 %s-%s' % (self.label['end'], self.label['ttype']))
            contents.append('%s:\n' % (self.label['ttype']))

        contents.append(' .byte %s' % (hex(self.tbl['csHeader'].callsite_format)))
        if self.tbl['csHeader'].callsite_format == 0x1:
            contents.append(' .uleb128 %s-%s' % (self.label['cs_end'], self.label['cs_begin']))
        return contents

    def has_missing_labels(self):
        if set(self.before_label_dict.keys()) != set(self.before_label_history):
            return True
        if set(self.after_label_dict.keys()) != set(self.after_label_history):
            return True
        return False

    def get_before_label(self, addr):
        labels = []
        if addr in self.before_label_dict and addr not in self.before_label_history:
            labels.extend(self.before_label_dict[addr])
            self.before_label_history.append(addr)
        return labels

    def get_after_label(self, addr):
        labels = []
        if addr in self.after_label_dict and addr not in self.after_label_history:
            labels.extend(self.after_label_dict[addr])
            self.after_label_history.append(addr)
        return labels

    def register_before_label(self, addr, label):
        if addr not in self.before_label_dict:
            self.before_label_dict[addr] = list()
        self.before_label_dict[addr].append(label)

    def register_after_label(self, addr, label):
        if addr not in self.after_label_dict:
            self.after_label_dict[addr] = list()
        self.after_label_dict[addr].append(label)

    def get_LSDA_tbl_entries(self):
        # offset = 0
        contents = []
        global EHBB_CNT
        for item in self.tbl['region_tbl']:
            bb_start = self.start_proc_addr + item.start
            bb_end = bb_start + item.length
            landing_pad_start = self.start_proc_addr + item.landing_pad
            action = item.action
            # print(' entry: %s-%s : landing_pad: %s, action %d'%(hex(bb_start), hex(bb_end), hex(landing_pad_start), action))
            local_label = {}
            local_label['bb_begin'] = '.LEHB_%d_%d' % (self.eh_fun_id, EHBB_CNT)
            local_label['bb_end'] = '.LEHE_%d_%d' % (self.eh_fun_id, EHBB_CNT)
            local_label['landing_begin'] = ''
            if landing_pad_start > self.start_proc_addr:
                landing_label = '.LANDING_%d_%d' % (self.eh_fun_id, EHBB_CNT)
                local_label['landing_begin'] = landing_label
                self.register_before_label(landing_pad_start, landing_label)

            self.register_before_label(bb_start, local_label['bb_begin'])
            self.register_after_label(bb_end, local_label['bb_end'])

            EHBB_CNT += 1

            contents.append(' .uleb128 %s-%s' % (local_label['bb_begin'], self.label['fun']))
            contents.append(' .uleb128 %s-%s' % (local_label['bb_end'], local_label['bb_begin']))
            if local_label['landing_begin']:
                contents.append(' .uleb128 %s-%s' % (local_label['landing_begin'], self.label['fun']))
            else:
                contents.append(' .uleb128 0')
            contents.append(' .uleb128 %s' % (hex(action)))

        return contents
        # return contents, offset

    def get_action_tbl_entries(self):
        contents = []
        if self.tbl['action'] is not None:
            for act in self.tbl['action'].tbl:
                contents.append(' .byte %s' % (hex(act.filter)))
                contents.append(' .byte %s' % (hex(act.next)))
        return contents

    def get_type_tbl_entries(self, reloc_sym_dict, symbolizer):

        tbl_addr = self.tbl['gcc_except_table_addr']
        contents = []
        if self.tbl['type_tbl'] is not None:
            for item in self.tbl['type_tbl'].tbl:
                # if r_offset is zero
                if item.r_offset == 0:
                    if self.tbl['header'].item_size == 8:
                        contents.append(' .quad 0')
                    else:
                        contents.append(' .long 0')
                    continue

                target = tbl_addr + item.offset + item.r_offset
                if target not in reloc_sym_dict:
                    if self.tbl['header'].item_size == 8:
                        #target = target & 0xffffffffffffffff
                        target = target & 0xffffffff
                    else:
                        target = target & 0xffffffff

                if self.tbl['header'].item_size == 8:
                    contents.append(' .quad %s-.'%(symbolizer.get_data_label(target)))
                else:
                    contents.append(' .long %s-.' % (symbolizer.get_data_label(target)))
                '''
                if target in reloc_sym_dict:
                    sym = reloc_sym_dict[target]
                    # it may refer to stub region instead symbol
                    if isinstance(sym, int):
                        new_sym = reloc_sym_dict[sym]
                        ref_sym = 'DW.ref.%s'%(new_sym)
                        contents.append(' .long DW.ref.%s-.' % (ref_sym))
                        self.ref_sym_dict[ref_sym] = new_sym
                    else:
                        contents.append(' .long %s-.' % (sym))
                else:
                    print(hex(item.r_offset))
                    assert False, 'Invalid type table parsing'
                '''
        return contents


from lib.ElfDef import ELFHeader, SectionHeader, ProgramHeader, Elf64_Sym, Elf64_Rela, Elf64_Dyn, Elf64_Verneed, \
    Elf64_Vernaux, Elf64_VernIdx, SectionType, SectionFlag, ProgramFlag, ProgramType, DynamicArrayTag, RelocationType, \
    Pack, Unpack, SectionBrick, VersionBrick, Elf64_Addr





class ElfBricks:
    def __init__(self, filename=None):

        if filename:
            with open(filename, 'rb') as f:
                data = f.read()

            self._data = data
            self._header = Unpack(ELFHeader, data)
            self._program_header_list = self.get_program_header_list(data)
            self._shstrtab_header, self._shstrtab = self.get_shstrtab(data)
            self._sec_list = self.get_section_list(data)

            self._dynamic = self.get_dynamic_section(data, self._program_header_list)
            self._dynamic_dict = self.make_dynamic_dict(self._dynamic)
            self._dynstr = self.get_dynstr(self._dynamic_dict, data)
            self._dt_needed_list = self.get_dt_needed_list(self._dynamic, self._dynstr)

            self._dynsym = self.get_dynsym(self._dynamic_dict, data)
            self._dynsym_list = self.get_symtab_list(self._dynsym)
            self._rela_list = self.get_rela_list(self._dynamic_dict, data)
            self._rela_plt_list = self.get_rela_plt_list(self._dynamic_dict, data)
            self._symtab_dict = self.get_symtab_dict(self._sec_list)
            self._fun_map = self.map_sym2addr(self._symtab_dict)

            #self._version_dep_table = self.get_version_dependent_table(self._dynamic_dict, data)
            self._version_dict, self._version_table = self.get_version_table(self._dynamic_dict, data, len(self._dynsym_list))

            self._init_array = self._get_init_array_list(self._program_header_list, self._dynamic_dict, data)
            self._fini_array = self._get_fini_array_list(self._program_header_list, self._dynamic_dict, data)

            self._init_section_range = self._get_init_range(self._sec_list, self._dynamic_dict)
            self._fini_section_range = self._get_fini_range(self._sec_list, self._dynamic_dict)
            self._plt_section_range = self._get_plt_range(self._sec_list)

            self._gnu_hash_sec = self._get_gnu_hash_sec(self._sec_list, self._dynamic_dict, data)
            self._rodata_sec = self._get_section_data(self._sec_list, data, '.rodata')
            self._rodata_sec_offset = self._get_section_base_offset(self._sec_list, '.rodata')
            self._rodata_base_addr = self._get_section_base_addr(self._sec_list, '.rodata')
            # for ablation study
            self._myrodata_sec = self._get_section_data(self._sec_list, data, '.my_rodata')
            self._myrodata_sec_offset = self._get_section_base_offset(self._sec_list, '.my_rodata')
            self._myrodata_base_addr = self._get_section_base_addr(self._sec_list, '.my_rodata')

            self._vaddr_range = self.get_vaddr_range(self._program_header_list)
            self._offset_range = self.get_offset_range(self._program_header_list)
        else:
            assert False, "TODO"

    def get_dt_needed_list(self, dyn_sec, dynstr):
        dt_needed_list = []
        for idx in range(len(dyn_sec)>>4):
            entry = Unpack(Elf64_Dyn, dyn_sec[idx * 0x10:(idx + 1) * 0x10])
            if entry.d_tag == 1:
                lib = dynstr[entry.d_un:].decode().split('\0')[0]
                dt_needed_list.append((entry.d_un, lib))
        return dt_needed_list

    def get_rela_plt_list(self, dyn_dict, data):
        rela = self.get_matched_section(dyn_dict, data, DynamicArrayTag.DT_JMPREL)
        entry_size = dyn_dict[DynamicArrayTag.DT_RELAENT] #DT_RELAENT
        rela_size = len(rela)

        rela_list = []
        for idx in range(int(rela_size/entry_size)):
            entry = rela[idx*entry_size: (idx+1)*entry_size]
            rela_list.append(Unpack(Elf64_Rela, entry))

        return rela_list

    def is_in_plt_section(self, addr):
        for plt_range in self._plt_section_range:
            if addr in plt_range:
                return True
        return False

    def _get_plt_range(self, sec_list):
        plt_region_list = []
        for header in sec_list:
            if header.name in ['.plt', '.plt.sec', '.plt.got']:
                plt_region_list.append(header.AddrRange)
        return plt_region_list

    def _find_offset_range(self, sec_start, sec_list):
        for header in sec_list:
            if header.AddrRange.start == sec_start:
                return header.OffsetRange

        assert False, 'Could not found init section'
    def _get_gnu_hash_sec(self, sec_list, dynamic_dict, data):
        addr = dynamic_dict[DynamicArrayTag.DT_GNU_HASH]
        offset = self._find_offset_range(addr, sec_list)
        return data[offset.start:offset.stop]

    def _get_section_data(self, sec_list, data, sec_name):
        for header in sec_list:
            if header.name == sec_name:
                offset = header.OffsetRange
                return data[offset.start:offset.stop]
        return b''

    def _get_section_base_addr(self, sec_list, sec_name):
        for header in sec_list:
            if header.name == sec_name:
                return header.AddrRange.start
        return 0

    def _get_section_base_offset(self, sec_list, sec_name):
        for header in sec_list:
            if header.name == sec_name:
                return header.OffsetRange.start
        return 0

    def _find_sec_range(self, sec_start, sec_list):
        for header in sec_list:
            if header.AddrRange.start == sec_start:
                return header.AddrRange

        assert False, 'Could not found init section'
    def _get_init_range(self, sec_list, dynamic_dict):
        addr = dynamic_dict[DynamicArrayTag.DT_INIT]
        return self._find_sec_range(addr, sec_list)

    def _get_fini_range(self, sec_list, dynamic_dict):
        addr = dynamic_dict[DynamicArrayTag.DT_FINI]
        return self._find_sec_range(addr, sec_list)

    def _addr2offset(self, program_header_list, addr):
        for prog_header in program_header_list:
            if prog_header.p_type != int(ProgramType.PT_LOAD):
                continue
            if prog_header.p_vaddr <= addr and addr < prog_header.p_vaddr + prog_header.p_filesz:
               return addr - prog_header.p_vaddr + prog_header.p_offset

        assert False, "Could not resolve addr %s"%(hex(addr))
    def _get_addr_array(self, program_header_list, addr, size, data):
        offset = self._addr2offset(program_header_list, addr)
        array = []
        for idx in range(int(size/8)):
            entry = Unpack(Elf64_Addr, data[offset+(idx*8):offset+((idx+1)*8)])
            array.append(entry.addr)
        return array

    def _get_init_array_list(self, program_header_list, dynamic_dict, data):
        addr = dynamic_dict[DynamicArrayTag.DT_INIT_ARRAY]
        size = dynamic_dict[DynamicArrayTag.DT_INIT_ARRAYSZ]
        return self._get_addr_array(program_header_list, addr, size, data)

    def _get_fini_array_list(self, program_header_list, dynamic_dict, data):
        addr = dynamic_dict[DynamicArrayTag.DT_FINI_ARRAY]
        size = dynamic_dict[DynamicArrayTag.DT_FINI_ARRAYSZ]
        return self._get_addr_array(program_header_list, addr, size, data)

    def get_symtab_list(self, symtab):
        symtab_list = []
        for idx in range(int(len(symtab)/0x18)):
            symtab_list.append(Unpack(Elf64_Sym, symtab[idx * 0x18:]))
        return symtab_list
    def map_sym2addr(self, symtab_dict):
        fun_map = dict()
        for sym_name, entries in symtab_dict.items():
            if sym_name.startswith('fun_'):
                last = sym_name.split('_')[-1]
                if '.part.' in last:
                    continue
                old_addr = int(last,16)
                len(entries) == 1, 'Duplicated function name is not allowed'
                new_addr = entries[0].st_value
                fun_map[old_addr] = new_addr
        return fun_map
    def make_symtab_dict(self, symtab, strtab):
        entry_size = symtab.header.sh_entsize
        sym_dict = dict()
        for idx in range(int(symtab.header.sh_size / entry_size)):
            entry = Unpack(Elf64_Sym, symtab.body[idx * entry_size:])
            name = str(strtab[entry.st_name:].decode('utf-8')).split('\x00')[0]
            if name not in sym_dict:
                sym_dict[name] = list()
            sym_dict[name].append(entry)
        return sym_dict
    def get_symtab_dict(self, section_header_list):
        for idx, header in enumerate(section_header_list):
            if header.name in ['.symtab']:
                strtab_idx = header.header.sh_link
                return self.make_symtab_dict(header, section_header_list[strtab_idx].body)
        return dict()

    def get_offset_range(self, program_header_list, excluded_base_addr = 0):
        min_addr = -1
        max_addr = 0
        for header in program_header_list:
            if header.p_type == int(ProgramType.PT_LOAD):
                if header.p_offset == excluded_base_addr:
                    continue
                if min_addr < 0 or header.p_offset < min_addr:
                    # exclude my_rodata section
                    if self._myrodata_sec and self._myrodata_sec_offset == header.p_offset:
                        continue
                    min_addr = header.p_offset
                if max_addr < header.p_offset:
                    max_addr = header.p_offset + header.p_filesz
        return range(min_addr, max_addr)

    def get_vaddr_range(self, program_header_list, excluded_base_addr = 0):
        min_addr = -1
        max_addr = 0
        for header in program_header_list:
            if header.p_type == int(ProgramType.PT_LOAD):
                if header.p_offset == excluded_base_addr:
                    continue
                if min_addr < 0 or header.p_vaddr < min_addr:
                    # exclude my_rodata section
                    if self._myrodata_sec and self._myrodata_sec_offset == header.p_offset:
                        continue
                    min_addr = header.p_vaddr - (header.p_vaddr % header.p_align)
                if max_addr < header.p_vaddr:
                    max_addr = header.p_vaddr + header.p_memsz
                    if max_addr % header.p_align:
                        max_addr += header.p_align - (max_addr % header.p_align)
        return range(min_addr, max_addr)
    def create_dummy_section_header(self, addr, offset, size, link=0, info=0, type=0, flags=0, align=8, entsize=0):
        header = Unpack(SectionHeader, b'\x00' * 0x40)
        header.sh_addr = addr
        header.sh_offset = offset
        header.sh_size = size
        header.sh_link = link
        header.sh_info = info
        header.sh_type = type
        header.sh_flags = flags
        header.sh_addralign = align
        header.sh_entsize = entsize
        return header

    def create_dummy_program_header(self, offset, base_addr, size, type=0, flags=0, align=0x1000):
        header = Unpack(ProgramHeader, b'\x00' * 0x38)
        header.p_type = type
        header.p_flags = flags
        header.p_offset = offset
        header.p_vaddr = base_addr
        header.p_paddr = base_addr
        header.p_filesz = size
        header.p_memsz = size
        header.p_align = align
        return header

    def create_new_dynamic_sections(self, base_offset, base_addr,
                                    dynstr, dynsym, rela_dyn_list,
                                    version_sec, new_version_table_sec,
                                    new_dt_needed_list,
                                    new_gnu_hash_sec):

        dyn_sec = self._dynamic

        new_section_header_list = []

        #dyn_dict = self.make_dynamic_dict(dyn_sec)
        dyn_dict = dict()

        data = b''


        # DT_STRSZ, DT_STRTAB -----------------------
        cur_offset = len(data) + base_offset
        cur_addr = len(data) + base_addr
        dyn_dict[DynamicArrayTag.DT_STRSZ] = len(dynstr)  #DT_STRSZ
        dyn_dict[DynamicArrayTag.DT_STRTAB] = cur_addr  #DT_STRTAB
        data += dynstr
        sec_header = self.create_dummy_section_header(cur_addr, cur_offset, len(dynstr),
                                                      type=int(SectionType.SHT_STRTAB),
                                                      flags=int(SectionFlag.SHF_ALLOC),
                                                      align = 1)
        new_section_header_list.append(('.dynstr', sec_header))

        # DT_SYM -----------------------
        if len(data) % 8:
            data += b'\x00'*(8 - len(data) % 8)

        cur_offset = len(data) + base_offset
        cur_addr = len(data) + base_addr
        dyn_dict[DynamicArrayTag.DT_SYMTAB] = cur_addr  #DT_SYM
        data += dynsym
        sec_header = self.create_dummy_section_header(cur_addr, cur_offset, len(dynsym),
                                                      type=int(SectionType.SHT_DYNSYM),
                                                      flags=int(SectionFlag.SHF_ALLOC),
                                                      align = 8, entsize=0x18)
        new_section_header_list.append(('.dynsym', sec_header))

        # DT_GNU_HASH ----------------
        if len(data) % 8:
            data += b'\x00'*(8 - len(data) % 8)

        cur_offset = len(data) + base_offset
        cur_addr = len(data) + base_addr
        dyn_dict[DynamicArrayTag.DT_GNU_HASH] = cur_addr  #DT_GNU_HASH
        data += new_gnu_hash_sec
        sec_header = self.create_dummy_section_header(cur_addr, cur_offset, len(new_gnu_hash_sec),
                                                      type=int(SectionType.SHT_HASH),
                                                      flags=int(SectionFlag.SHF_ALLOC),
                                                      align = 8)
        new_section_header_list.append(('.gnu.hash', sec_header))


        # DT_VERSYM -----------------------
        cur_offset = len(data) + base_offset
        cur_addr = len(data) + base_addr

        data += new_version_table_sec

        dyn_dict[DynamicArrayTag.DT_VERSYM] = cur_addr
        sec_header = self.create_dummy_section_header(cur_addr, cur_offset, len(new_version_table_sec),
                                                      type=int(SectionType.SHT_GNU_versym),
                                                      flags=int(SectionFlag.SHF_ALLOC),
                                                      align = 2, entsize=2)
        new_section_header_list.append(('.gnu.version', sec_header))


        if len(data) % 8:
            data += b'\x00'*(8 - len(data) % 8)

        # DT_VERNEED ----------------------
        cur_offset = len(data) + base_offset
        cur_addr = len(data) + base_addr

        data += version_sec

        dyn_dict[DynamicArrayTag.DT_VERNEED] = cur_addr
        #dyn_dict[DynamicArrayTag.DT_VERNEEDNUM] = int(len(version_sec) / 0x10) - 1
        sec_header = self.create_dummy_section_header(cur_addr, cur_offset, len(version_sec),
                                                      type=int(SectionType.SHT_GNU_verneed),
                                                      flags=int(SectionFlag.SHF_ALLOC),
                                                      align = 4)
        new_section_header_list.append(('.gnu.version_r', sec_header))


        # --------
        # update relocation info
        rela_dyn1 = b''
        rela_dyn2 = b''
        num_of_r_x86_64_relative = 0
        for rentry in rela_dyn_list:
            if rentry.r_info & 0xffffffff in [RelocationType.R_X86_64_RELATIVE]:
                rela_dyn1 += Pack(rentry)
                num_of_r_x86_64_relative += 1
            else:
                rela_dyn2 += Pack(rentry)


        cur_offset = len(data) + base_offset
        cur_addr = len(data) + base_addr
        dyn_dict[DynamicArrayTag.DT_RELASZ] = len(rela_dyn_list) * 0x18 #DT_RELASZ
        dyn_dict[DynamicArrayTag.DT_RELAENT] = 0x18                  #DT_RELAENT
        dyn_dict[DynamicArrayTag.DT_RELA] = cur_addr              #DT_RELA
        rela_dyn = rela_dyn1 + rela_dyn2
        data += rela_dyn
        sec_header = self.create_dummy_section_header(cur_addr, cur_offset, len(rela_dyn),
                                                      type=int(SectionType.SHT_RELA),
                                                      flags=int(SectionFlag.SHF_ALLOC),
                                                      align = 8, entsize=0x18)
        dyn_dict[0x6ffffff9] = num_of_r_x86_64_relative
        new_section_header_list.append(('.rela.dyn', sec_header))

        new_dynamic_section = b''
        for item in new_dt_needed_list:
            entry = Unpack(Elf64_Dyn, b'\x00' * 0x10)
            entry.d_tag = DynamicArrayTag.DT_NEEDED
            entry.d_un = item[0]
            new_dynamic_section += Pack(entry)

        for idx in range(len(dyn_sec) >> 4):
            entry = Unpack(Elf64_Dyn, dyn_sec[idx * 0x10:(idx + 1) * 0x10])
            if entry.d_tag == DynamicArrayTag.DT_NEEDED:
                continue

            if entry.d_tag == 0:
                break
            if entry.d_tag in dyn_dict:
                entry.d_un = dyn_dict[entry.d_tag]
                del dyn_dict[entry.d_tag]
            new_dynamic_section += Pack(entry)

        if dyn_dict:
            for tag, un in dyn_dict.items():
                entry = Unpack(Elf64_Dyn, b'\x00'*0x10)
                entry.d_tag = tag
                entry.d_un = un
                new_dynamic_section += Pack(entry)

        new_dynamic_section += b'\x00' * (len(dyn_sec) - len(new_dynamic_section))
        assert len(new_dynamic_section) <= len(dyn_sec), 'new dynamic section is too large'

        return new_dynamic_section, new_section_header_list, data

    def get_matched_section(self, dyn_dict, data, tag, size=0):
        assert tag in dyn_dict, 'The binary file does not contain %s'%(hex(tag))

        addr = dyn_dict[tag]
        for sec in self._sec_list:
            if addr in sec.AddrRange:
                assert addr == sec.AddrRange.start, "Section address is mismatched"

                offset_start = sec.OffsetRange.start
                if size == 0:
                    offset_end = sec.OffsetRange.stop
                else:
                    offset_end = offset_start + size

                return data[offset_start:offset_end]
        assert False, "Couldn't find the matched section"

    def get_rela_list(self, dyn_dict, data):
        rela_size = dyn_dict[DynamicArrayTag.DT_RELASZ] #DT_RELASZ
        rela = self.get_matched_section(dyn_dict, data, DynamicArrayTag.DT_RELA, rela_size)
        entry_size = dyn_dict[DynamicArrayTag.DT_RELAENT] #DT_RELAENT

        rela_list = []
        for idx in range(int(rela_size/entry_size)):
            entry = rela[idx*entry_size: (idx+1)*entry_size]
            rela_list.append(Unpack(Elf64_Rela, entry))

        return rela_list

    def get_version_table(self, dyn_dict, data, num_of_entry):
        versym = self.get_matched_section(dyn_dict, data, DynamicArrayTag.DT_VERSYM, num_of_entry * 2)
        ver_table = []
        last_version = 0
        for idx in range(num_of_entry):
            idx = Unpack(Elf64_VernIdx, versym[idx * 2:])
            ver_table.append(idx)
            if idx.idx > last_version:
                last_version = idx.idx

        #num_of_versions = dyn_dict[DynamicArrayTag.DT_VERNEEDNUM]
        num_of_versions = last_version
        dynstr = self.get_dynstr(self._dynamic_dict, data)
        verneeded = self.get_matched_section(dyn_dict, data, DynamicArrayTag.DT_VERNEED, (num_of_versions + 20) * 0x10)

        version_dict = dict()
        offset = 0

        while True:
            header = Unpack(Elf64_Verneed, verneeded[offset:])
            lib_name = (dynstr[header.vn_file:].decode('utf-8')).split('\x00')[0]

            for idx in range(header.vn_cnt):
                entry = Unpack(Elf64_Vernaux, verneeded[offset + (idx + 1) * 0x10:])
                sym_name = (dynstr[entry.vna_name:].decode('utf-8')).split('\x00')[0]
                version_dict[entry.vna_other] = VersionBrick(lib_name, sym_name, header, entry)

            if header.vn_next == 0:
                break
            offset += header.vn_next

        return version_dict, ver_table


    def get_dynstr(self, dyn_dict, data):
        strsize = dyn_dict[DynamicArrayTag.DT_STRSZ] #DT_STRSZ
        return self.get_matched_section(dyn_dict, data, DynamicArrayTag.DT_STRTAB, strsize)

    def get_dynsym(self, dyn_dict, data):
        #ent_size = dyn_dict[DynamicArrayTag.DT_SYMENT] #DT_SYMENT
        return self.get_matched_section(dyn_dict, data, DynamicArrayTag.DT_SYMTAB)

    def make_dynamic_dict(self, dyn_sec):
        dyn_dict = dict()
        for idx in range(len(dyn_sec)>>4):
            entry = Unpack(Elf64_Dyn, dyn_sec[idx * 0x10:(idx + 1) * 0x10])
            if entry.d_tag == 0:
                break
            dyn_dict[entry.d_tag] = entry.d_un

        return dyn_dict
    def split_prog_header(self, prog_header, diff, offset = 0, addr = 0):
        new_prog_header = Unpack(ProgramHeader, Pack(prog_header))
        new_prog_header.p_offset = offset
        new_prog_header.p_vaddr = addr
        new_prog_header.p_paddr = addr
        new_prog_header.p_filesz = diff
        new_prog_header.p_memsz = diff
        new_prog_header.p_align = 0x1000
        new_prog_header.p_flags = 4  # Read

        prog_header.p_offset = diff
        prog_header.p_vaddr += diff
        prog_header.p_paddr += diff

        prog_header.p_filesz -= diff
        prog_header.p_memsz -= diff

        return new_prog_header, prog_header

    def get_interp_addr(self, program_header_list):
        for prog_header in program_header_list:
            if prog_header.p_type in [int(ProgramType.PT_INTERP)]:
                return prog_header.p_vaddr
        return 0

    def fix_program_headers(self, program_header_list, addend):
        fixed_program_header_list = []
        interp_base = self.get_interp_addr(program_header_list)

        new_prog_list = []
        for prog_header in program_header_list:
            if prog_header.p_type in [int(ProgramType.PT_NOTE), int(ProgramType.PT_GNU_PROPERTY)]:
                continue

            new_prog_list.append(prog_header)

        for idx, prog_header in enumerate(new_prog_list):

            if prog_header.p_type in [int(ProgramType.PT_PHDR)]:
                prog_header.p_vaddr = 0x40
                prog_header.p_paddr = 0x40
                prog_header.p_offset = 0x40
                prog_header.p_filesz += 0x38 * len(new_prog_list)
                prog_header.p_memsz += 0x38 * len(new_prog_list)

            elif prog_header.p_type in [int(ProgramType.PT_LOAD)]:
                # for ablation study
                if self._myrodata_base_addr > 0 and prog_header.p_vaddr == self._myrodata_base_addr:
                    continue

                # fix gas loader bug
                if prog_header.p_vaddr < interp_base and interp_base < prog_header.p_filesz + prog_header.p_vaddr:
                    # split load segment

                    diff = interp_base - prog_header.p_vaddr
                    assert diff % 0x1000 == 0

                    new_prog_header, prog_header = self.split_prog_header(prog_header, diff)

                    fixed_program_header_list.append(new_prog_header)
                elif prog_header.p_offset == 0 and prog_header.p_filesz < 0x2000:
                    prog_header.p_filesz = 0x1000
                    prog_header.p_memsz = 0x1000

            if prog_header.p_type in [int(ProgramType.PT_GNU_RELRO)]:
                continue
            if prog_header.p_offset > 0x40:
                prog_header.p_offset += addend

            fixed_program_header_list.append(prog_header)

        return fixed_program_header_list


    def reset_program_header_list(self, program_header_list):
        self.new_program_header_list = program_header_list

    def add_program_header(self, new_program_header):
        place_to_add = None
        if new_program_header.p_type == int(ProgramType.PT_LOAD):
            for idx, program_header in enumerate(self.new_program_header_list):
                if program_header.p_type == int(ProgramType.PT_LOAD):
                    if program_header.p_offset == new_program_header.p_offset:
                        if program_header.p_filesz < new_program_header.p_filesz:
                            self.new_program_header_list[idx] = new_program_header
                            return
                        else:
                            pass
                    elif program_header.p_vaddr > new_program_header.p_vaddr:
                        place_to_add = idx
                        break

        if place_to_add is None:
            self.new_program_header_list.append(new_program_header)
        else:
            self.new_program_header_list.insert(place_to_add, new_program_header)

    def reset_section_header_list(self):
        self.new_section_header_list = []

    def add_section_header(self, section_header):
        self.new_section_header_list.append(section_header)

    def overwrite_rodata_section(self, rodata_offset, new_rodata):
        size = len(new_rodata)
        old_rodata = self.new_data[rodata_offset: rodata_offset+size]
        self.new_data = self.new_data[:rodata_offset] + new_rodata + self.new_data[rodata_offset + size:]

    def reset_data(self, data):
        self.new_data = data
    def add_data(self, addtional_data):
        self.new_data += addtional_data

    def reorganize_version_list(self, elfBricks):
        version_dict1 = self._version_dict
        lib_names1 = set([entry.lib_name for entry in version_dict1.values()])
        version_dict2 = elfBricks._version_dict
        lib_names2 = set([entry.lib_name for entry in version_dict2.values()])

        version_idx = 1
        tot_version_list = []
        for lib_name in lib_names1:
            ver_set1 = set([entry.ver_str for entry in version_dict1.values() if entry.lib_name == lib_name])
            ver_set2 = set([entry.ver_str for entry in version_dict2.values() if entry.lib_name == lib_name])
            header = [entry.header for entry in version_dict1.values() if entry.lib_name == lib_name][0]
            version_list = []
            version_list.append((lib_name, header))
            for ver_str in ver_set1:
                entry = [entry.entry for entry in version_dict1.values()
                         if entry.lib_name == lib_name and entry.ver_str==ver_str][0]

                version_idx += 1
                entry.vna_other = version_idx
                entry.vna_next = 0x10
                version_list.append((ver_str, entry))
            for ver_str in (ver_set2 - ver_set1):
                entry = [entry.entry for entry in version_dict2.values()
                         if entry.lib_name == lib_name and entry.ver_str==ver_str][0]
                entry.vna_name += len(self._dynstr)
                version_idx += 1
                entry.vna_other = version_idx
                entry.vna_next = 0x10
                version_list.append((ver_str, entry))

            version_list[0][1].vn_cnt = len(version_list) - 1
            version_list[-1][1].vna_next = 0
            tot_version_list.append(version_list)

        for lib_name in (lib_names2 - lib_names1):
            ver_set2 = set([entry.ver_str for entry in version_dict2.values() if entry.lib_name == lib_name])
            header = [entry.header for entry in version_dict2.values() if entry.lib_name == lib_name][0]
            version_list = []
            header.vn_file += len(self._dynstr)
            version_list.append((lib_name, header))
            for ver_str in ver_set2:
                entry = [entry.entry for entry in version_dict2.values()
                         if entry.lib_name == lib_name and entry.ver_str == ver_str][0]
                entry.vna_name += len(self._dynstr)
                version_idx += 1
                entry.vna_other = version_idx
                entry.vna_next = 0x10
                version_list.append((ver_str, entry))

            version_list[0][1].vn_cnt = len(version_list) - 1
            version_list[-1][1].vna_next = 0
            tot_version_list.append(version_list)

        return tot_version_list, version_idx

    def merge_version_info(self, elfBricks):
        tot_version_list, version_idx = self.reorganize_version_list(elfBricks)

        my_version_table = self.create_version_table(self, tot_version_list)
        other_version_table = self.create_version_table(elfBricks, tot_version_list)

        new_version_table_sec = b''
        for entry in other_version_table:
            new_version_table_sec += Pack(entry)
        for entry in my_version_table:
            new_version_table_sec += Pack(entry)

        new_version_list = []
        for idx, ver_list in enumerate(tot_version_list, start=1):
            if idx < len(tot_version_list):
                ver_list[0][1].vn_next = 0x10 * len(ver_list)
            else:
                ver_list[0][1].vn_next = 0
            new_version_list.extend([item[1] for item in ver_list])

        new_version_sec = b''
        for version in new_version_list:
            new_version_sec += Pack(version)

        return new_version_table_sec, new_version_sec, version_idx

    def create_version_table(self, elfBricks, tot_version_list):
        new_version_table = []
        for idx in elfBricks._version_table:
            new_entry = Unpack(Elf64_VernIdx, b'\x00' * 2)
            if idx.idx > 1:
                version = elfBricks._version_dict[idx.idx]
                for ver_list in tot_version_list:
                    if ver_list[0][0] == version.lib_name:
                        for ent in ver_list[1:]:
                            if ent[0] == version.ver_str:
                                new_entry.idx = ent[1].vna_other
                                break
                        break
                assert new_entry.idx > 0, 'could not found version info'
            new_version_table.append(new_entry)
        return new_version_table


    def merge_dt_needed_list(self, elfBricks):
        dt_dict = {item[1]:item[0] for item in self._dt_needed_list}
        dt_list = []


        for offset, name in self._dt_needed_list:
            if name.split('.')[0] in ['libasan']:
                dt_list.append((offset, name))
                dt_dict.pop(name)

        # add all dt_needed list in target binary
        for offset, name in elfBricks._dt_needed_list:
            if name not in dt_dict:
                dt_list.append((len(self._dynstr)+offset, name))
            else:
                dt_list.append((dt_dict[name], name))
                dt_dict.pop(name)
        # add additional dt_needed list if the recompiled binary has
        for offset, name in self._dt_needed_list:
            if name in dt_dict:
                dt_list.append((offset, name))
        return dt_list

    def merge_dynsym(self, elfBricks, new_dynstr):

        new_dynsym = b''
        for entry in elfBricks._dynsym_list:
            name1 = str(elfBricks._dynstr[entry.st_name:].decode('utf-8')).split('\x00')[0]
            if entry.st_name:
                entry.st_name += len(self._dynstr)
                name2 = str(new_dynstr[entry.st_name:].decode('utf-8')).split('\x00')[0]
                assert name1 == name2, 'symbol table mismatch'
                if entry.st_value and elfBricks.is_in_plt_section(entry.st_value):
                    entry.st_value = 0
                # update dynsym if it is function addr.
                elif entry.st_value in self._fun_map:
                    entry.st_value = self._fun_map[entry.st_value]

            #if entry.st_shndx:
            #    entry.st_shndx = TODO
            new_dynsym += Pack(entry)

        my_dynsym = self._dynsym

        return new_dynsym + my_dynsym

    def merge_dynstr(self, elfBricks):
        return self._dynstr + elfBricks._dynstr

    def merge_rela_dyn(self, elfBricks):
        new_rela_dyn_list = []

        for rela in elfBricks._rela_list:
            r_idx = rela.r_info >> 32

            reloc_type = rela.r_info & 0xffffffff
            if reloc_type in [RelocationType.R_X86_64_RELATIVE]:
                if rela.r_addend in self._fun_map:
                    #print('[+] update relocation (R_X86_64_RELATIVE:%s) info %s -> %s'%(hex(rela.r_offset), hex(rela.r_addend), hex(self._fun_map[rela.r_addend])))
                    rela.r_addend = self._fun_map[rela.r_addend]
            elif reloc_type in [RelocationType.R_X86_64_64, RelocationType.R_X86_64_GLOB_DAT]:
                symbol = elfBricks._dynsym_list[r_idx]
                if symbol.st_value in self._fun_map:
                    print('[+] update relocation info (%s) %s -> %s'%(hex(rela.r_offset), hex(symbol.st_value), hex(self._fun_map[symbol.st_value])))
                    assert False, 'Not implement yet'
                    # TODO: add symbol into .dynsym
                    # rela.r_info



            new_rela_dyn_list.append(rela)

        base_idx = int(len(elfBricks._dynsym) / 0x18)
        for rela in self._rela_list:
            r_idx = rela.r_info >> 32
            if r_idx:
                rela.r_info = (base_idx + r_idx << 32) | (rela.r_info & 0xffffffff)
            new_rela_dyn_list.append(rela)

        return new_rela_dyn_list

    def update_plt_sec(self, elfBricks, dynstr):
        if DynamicArrayTag.DT_JMPREL not in self._dynamic_dict:
            return

        base_idx = int(len(elfBricks._dynsym) / 0x18)
        new_rela_plt = b''
        for rela in self._rela_plt_list:
            r_idx = rela.r_info >> 32
            if r_idx:
                rela.r_info = ((base_idx + r_idx) << 32) | (rela.r_info & 0xffffffff)

            new_rela_plt += Pack(rela)

        rela_addr = self._dynamic_dict[DynamicArrayTag.DT_JMPREL]
        self.update_section(rela_addr, new_rela_plt)

    def update_section(self, addr, new_sec_data):
        size = len(new_sec_data)
        for sec_header in self.new_section_header_list:
            if sec_header.sh_addr == addr:
                offset = sec_header.sh_offset
                assert size == sec_header.sh_size, 'different section size'
                self.new_data = self.new_data[:offset] + new_sec_data + self.new_data[offset+size:]
                return

        assert False, 'Could not found target section %s'%(hex(addr))



    def merge_section_header(self, elfBricks, new_section_header_list, data_start_offset, additional_offset, version_idx):
        map_old_to_new_idx = dict()
        new_sec_list = []

        target_sec_dict = elfBricks.get_loadable_section_info(elfBricks.get_load_segment_info())
        self.reset_section_header_list()
        for idx, section in enumerate(elfBricks._sec_list):
            if idx == 0:
                pass
            elif idx not in target_sec_dict:
                continue
            section.header.sh_name += len(self._shstrtab)
            section.header.sh_flags &= ~int(SectionFlag.SHF_EXECINSTR)
            new_sec_list.append(section.header)
            self.add_section_header(section.header)


        for idx, section in enumerate(self._sec_list):
            if section.name in ['.dynstr']:
                old_dynstr_idx = idx
                section.header.sh_type = int(SectionType.SHT_PROGBITS)
                continue
            if section.name in ['.dynsym']:
                old_dynsym_idx = idx
                section.header.sh_type = int(SectionType.SHT_PROGBITS)
                section.header.sh_info = 0
                continue
            if section.name in ['.rela.dyn']:
                old_rela_idx = idx
                section.header.sh_type = int(SectionType.SHT_PROGBITS)
                continue
            if section.name in ['.gnu.version']:
                old_version_idx = idx
                section.header.sh_type = int(SectionType.SHT_PROGBITS)
                continue
            if section.name in ['.gnu.version_r']:
                old_version_r_idx = idx
                section.header.sh_info = 0
                section.header.sh_type = int(SectionType.SHT_PROGBITS)
                continue
            if section.name in ['.gnu.hash']:
                old_gnu_hash_idx = idx
                section.header.sh_type = int(SectionType.SHT_PROGBITS)

            if idx == 0:
                pass
            elif section.header.sh_offset < data_start_offset:
                continue

            map_old_to_new_idx[idx] = len(new_sec_list) + len(map_old_to_new_idx)

        new_dynstr_idx = len(new_sec_list) + len(map_old_to_new_idx)
        new_dynsym_idx = len(new_sec_list) + len(map_old_to_new_idx)+1

        for idx, section in enumerate(self._sec_list):
            if idx not in map_old_to_new_idx:
                continue

            if section.header.sh_offset > 0:
                section.header.sh_offset += additional_offset

            if section.header.sh_info and section.header.sh_type in \
                    [int(SectionType.SHT_RELA), int(SectionType.SHT_REL), 0x6ffffffc]:
                section.header.sh_info = map_old_to_new_idx[section.header.sh_info]

            if section.header.sh_link:
                if section.header.sh_link == old_dynstr_idx:
                    section.header.sh_link = new_dynstr_idx
                elif section.header.sh_link == old_dynsym_idx:
                    section.header.sh_link = new_dynsym_idx
                else:
                    section.header.sh_link = map_old_to_new_idx[section.header.sh_link]


            self.add_section_header(section.header)
            new_sec_list.append(section.header)


        for sec_name, sec_header in new_section_header_list:
            if sec_name == '.dynstr':
                sec_header.sh_name = self._sec_list[old_dynstr_idx].header.sh_name
            elif sec_name == '.dynsym':
                sec_header.sh_name = self._sec_list[old_dynsym_idx].header.sh_name
                sec_header.sh_link = new_dynstr_idx
            elif sec_name == '.gnu.hash':
                sec_header.sh_name = self._sec_list[old_gnu_hash_idx].header.sh_name
            elif sec_name == '.rela.dyn':
                sec_header.sh_name = self._sec_list[old_rela_idx].header.sh_name
                sec_header.sh_link = new_dynsym_idx
            elif sec_name == '.gnu.version':
                sec_header.sh_name = self._sec_list[old_version_idx].header.sh_name
                sec_header.sh_link = new_dynsym_idx
            elif sec_name == '.gnu.version_r':
                sec_header.sh_name = self._sec_list[old_version_r_idx].header.sh_name
                sec_header.sh_link = new_dynstr_idx
                sec_header.sh_info = version_idx - 1

            self.add_section_header(sec_header)




    def fix_file(self, target, filename):

        new_base = self._vaddr_range.start

        # 1. read target file
        additional_data = b''
        with open(target, 'rb') as f:
            additional_data = f.read()

        elfBricks = ElfBricks(target)

        zeros = b'\x00' * (new_base - len(additional_data))
        additional_data += zeros

        data_start_offset = self._offset_range.start
        self.reset_data(additional_data)

        # overwrite original rodata section
        if self._myrodata_sec:
            self.overwrite_rodata_section(elfBricks._rodata_sec_offset, self._myrodata_sec)

        self.add_data(self._data[data_start_offset:])

        # 2. create program header
        additional_data_length = len(additional_data)
        additional_offset = additional_data_length - self._offset_range.start
        new_program_header_list = self.fix_program_headers(self._program_header_list, additional_offset)
        self.reset_program_header_list(new_program_header_list)

        for target_prog_header in elfBricks.get_load_segment_info():
            target_prog_header.p_flags = target_prog_header.p_flags & ~0x1 # clear X bit
            self.add_program_header(target_prog_header)



        #----------
        # 3. create dynamic section, .dynstr, .dynsym, .rela.dyn

        new_base_addr = self._vaddr_range.stop
        cur_offset = len(self.new_data)
        cur_base_addr =  (cur_offset % 0x1000) + new_base_addr

        new_dynstr = self.merge_dynstr(elfBricks)
        new_dynsym = self.merge_dynsym(elfBricks, new_dynstr)
        new_dt_needed_list = self.merge_dt_needed_list(elfBricks)
        new_version_table_sec, new_version_sec, version_idx = self.merge_version_info(elfBricks)

        # 3-1. merge reloc info
        new_rela_dyn_list = self.merge_rela_dyn(elfBricks)

        original_gnu_hash_sec = elfBricks._gnu_hash_sec

        # 3-2. create dynamic section, .dynstr, .dynsym, .rela.dyn
        new_dynamic_section, new_section_header_list, new_dyn_sections = \
            self.create_new_dynamic_sections(
                cur_offset, cur_base_addr,
                new_dynstr, new_dynsym, new_rela_dyn_list,
                new_version_sec, new_version_table_sec,
                new_dt_needed_list,
                original_gnu_hash_sec
            )

        # 3-3. replace dynamic section
        for prog_header in self.new_program_header_list:
            if prog_header.p_type in [int(ProgramType.PT_DYNAMIC)]:
                remain = prog_header.p_offset + len(new_dynamic_section)
                self.new_data = self.new_data[:prog_header.p_offset] + new_dynamic_section + self.new_data[remain:]
                break

        # 3-4. create section header & program header
        new_prog_header = self.create_dummy_program_header(
            cur_offset, cur_base_addr, len(new_dyn_sections),
            type=int(ProgramType.PT_LOAD), flags=int(ProgramFlag.PF_R))

        self.add_program_header(new_prog_header)

        # -----
        # 4. create section header
        self.merge_section_header(elfBricks, new_section_header_list, data_start_offset, additional_offset, version_idx)

        self.update_plt_sec(elfBricks, new_dynstr)
        self.add_data(new_dyn_sections)

        cur_offset = len(self.new_data)

        # 5. add shstrtab section and section header
        new_shstrtab = self._shstrtab + elfBricks._shstrtab
        new_shstrtab_header = Unpack(SectionHeader, Pack(self._shstrtab_header))
        new_shstrtab_header.sh_offset = cur_offset
        new_shstrtab_header.sh_size = len(new_shstrtab)

        self.add_section_header(new_shstrtab_header)
        self.add_data(new_shstrtab)

        self.glue(filename)

    def glue(self, filename):

        new_header = Unpack(ELFHeader, Pack(self._header))
        new_header.e_phoff = len(Pack(self._header))
        new_header.e_phnum = len(self.new_program_header_list)
        new_header.e_shoff = len(self.new_data)
        new_header.e_shnum = len(self.new_section_header_list)
        new_header.e_shstrndx = len(self.new_section_header_list) - 1

        with open(filename, 'wb') as f:
            offset = f.write(Pack(new_header))

            for p_header in self.new_program_header_list:
                offset += f.write(Pack(p_header))

            offset += f.write(self.new_data[offset:])

            for s_header in self.new_section_header_list:
                offset += f.write(Pack(s_header))

    def get_load_segment_info(self):
        load_prog_header_list = []
        for program_header in self._program_header_list:
            if program_header.p_type == int(ProgramType.PT_LOAD):
                load_prog_header_list.append(program_header)
            if program_header.p_type == int(ProgramType.PT_TLS):
                load_prog_header_list.append(program_header)
        return load_prog_header_list

    def make_rela_sec_dict(self):
        return self.make_sec_dict(section_types=[4])  #SHT_RELA

    def make_data_sec_dict(self):
        return self.make_sec_dict(section_types=[1,8]) #[1, 8]: # SHT_PROGBITS, SHT_NOBITS
    def make_sec_dict(self, section_types):
        sec_dict = dict()
        for idx, section in enumerate(self._sec_list):
            if section.header.sh_type in section_types:
                sec_dict[idx] = section
        return sec_dict
    def get_program_header_list(self, data):
        program_header_list = []
        offset = self._header.e_phoff
        entsize = self._header.e_phentsize

        for idx in range(self._header.e_phnum):
            phoff = offset + idx * entsize
            p_header = Unpack(ProgramHeader, data[phoff: phoff + entsize])
            program_header_list.append(p_header)
        return program_header_list

    def get_dynamic_section(self, data, program_header_list):
        for prog_header in program_header_list:
            if prog_header.p_type in [int(ProgramType.PT_DYNAMIC)]:
                return data[prog_header.p_offset:prog_header.p_offset+prog_header.p_filesz]
        return b''

    def get_shstrtab(self, data):
        offset = self._header.e_shoff
        entsize = self._header.e_shentsize

        shoff = offset + self._header.e_shstrndx * entsize
        sec_header = Unpack(SectionHeader, data[shoff: shoff + entsize])
        return sec_header, data[sec_header.sh_offset: sec_header.sh_offset + sec_header.sh_size]

    def get_section_list(self, data):

        section_list = []
        offset = self._header.e_shoff
        entsize = self._header.e_shentsize

        for idx in range(self._header.e_shnum):
            shoff = offset + idx * entsize
            sec_header = Unpack(SectionHeader, data[shoff: shoff + entsize])
            sec_name = str(self._shstrtab[sec_header.sh_name:].decode('utf-8')).split('\x00')[0]
            if sec_header.sh_type in [8]: # SHT_NOBITS
                offset_range = range(sec_header.sh_offset, sec_header.sh_offset)
                body = b''
            else:
                offset_range = range(sec_header.sh_offset, sec_header.sh_offset + sec_header.sh_size)
                body = data[sec_header.sh_offset: sec_header.sh_offset + sec_header.sh_size]
            addr_range = range(sec_header.sh_addr, sec_header.sh_addr + sec_header.sh_size)

            section_list.append(SectionBrick(sec_name, offset_range, addr_range, sec_header, body))

        return section_list

    def get_loadable_section_info(self, loadable_seg_list):
        loadable_sec_dict = dict()
        location_of_init = -1
        for sec_idx, sec in enumerate(self._sec_list):
            for seg_info in loadable_seg_list:
                if sec.name in ['.init']:
                    location_of_init = sec.header.sh_offset
                elif location_of_init < 0 or sec.header.sh_offset < location_of_init:
                    break
                elif sec.name in ['.dynamic']:
                    break

                if seg_info.p_offset <= sec.header.sh_offset and \
                        sec.header.sh_offset < seg_info.p_offset + seg_info.p_filesz:
                    loadable_sec_dict[sec_idx] = sec
                    break
                elif sec.name in ['.bss'] and \
                        (seg_info.p_offset <= sec.header.sh_offset and
                         sec.header.sh_offset <= seg_info.p_offset + seg_info.p_filesz):
                    loadable_sec_dict[sec_idx] = sec
                    break

        return loadable_sec_dict


class ElfInfo(ElfBricks):
    def __init__(self, filename):
        with open(filename, 'rb') as f:
            data = f.read()

        self._header = Unpack(ELFHeader, data)
        self._program_header_list = self.get_program_header_list(data)
        self._shstrtab_header, self._shstrtab = self.get_shstrtab(data)

        self._sec_list = self.get_section_list(data)

        self._dynamic = self.get_dynamic_section(data, self._program_header_list)
        self._dynamic_dict = self.make_dynamic_dict(self._dynamic)
        self._dynstr = self.get_dynstr(self._dynamic_dict, data)
        self._dt_needed_list = self.get_dt_needed_list(self._dynamic, self._dynstr)
        self._rodata_base_addr = self._get_section_base_addr(self._sec_list, '.rodata')

    def get_ld_option(self):
        lib_option = []
        for _, lib in self._dt_needed_list:
            if lib in ['libomp.so.5']:
                name = 'omp5'
            elif lib.endswith('.so'):
                name = lib[3:-3]
            elif '.so.' in lib:
                name = lib.split('.so.')[0][3:]
            else:
                name = lib.split('.')[0][3:]
            lib_option.append('-l'+name)
        return lib_option

import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ElfLego')
    parser.add_argument('target_file', type=str)
    parser.add_argument('code_file', type=str)
    parser.add_argument('output_file', type=str)
    args = parser.parse_args()
    #lego = ElfLego(args.target_file)
    #lego.create_new_file(args.output_file)
    lego = ElfBricks(args.code_file)
    lego.fix_file(args.target_file, args.output_file)

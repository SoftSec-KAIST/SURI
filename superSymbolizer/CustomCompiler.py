import os, sys
import enum
from ctypes import *

from ElfBricks import ElfInfo


class ProgramType(enum.IntEnum):
    PT_NULL = 0
    PT_LOAD = 1

class ELFHeader(Structure):
    _fields_ = [
        ('e_ident', c_char * 16),  # 0x10
        ('e_type', c_uint16),  # 0x12
        ('e_machine', c_uint16),  # 0x14
        ('e_version', c_uint32),  # 0x18
        ('e_entry', c_uint64),  # 0x20
        ('e_phoff', c_uint64),  # 0x28
        ('e_shoff', c_uint64),  # 0x30
        ('e_flags', c_uint32),  # 0x34
        ('e_ehsize', c_uint16),  # 0x36
        ('e_phentsize', c_uint16),  # 0x38
        ('e_phnum', c_uint16),  # 0x3A
        ('e_shentsize', c_uint16),  # 0x3C
        ('e_shnum', c_uint16),  # 0x3E
        ('e_shstrndx', c_uint16),  # 0x40
    ]


class ProgramHeader(Structure):
    _fields_ = [
        ('p_type', c_uint32),  # 0x04
        ('p_flags', c_uint32),  # 0x08
        ('p_offset', c_uint64),  # 0x10
        ('p_vaddr', c_uint64),  # 0x18
        ('p_paddr', c_uint64),  # 0x20
        ('p_filesz', c_uint64),  # 0x28
        ('p_memsz', c_uint64),  # 0x30
        ('p_align', c_uint64),  # 0x38
    ]

def Unpack(ctype, buf):
    cstring = create_string_buffer(buf)
    ctype_instance = cast(pointer(cstring), POINTER(ctype)).contents
    return ctype_instance

def get_program_header_list(data):
    header = Unpack(ELFHeader, data)
    program_header_list = []
    offset = header.e_phoff
    entsize = header.e_phentsize

    for idx in range(header.e_phnum):
        phoff = offset + idx * entsize
        p_header = Unpack(ProgramHeader, data[phoff: phoff + entsize])
        program_header_list.append(p_header)
    return program_header_list

def get_vaddr_max(program_header_list, page_size, excluded_base_addr = 0):
    max_addr = 0
    for header in program_header_list:
        if header.p_type == int(ProgramType.PT_LOAD):
            if header.p_offset == excluded_base_addr:
                continue
            if max_addr < header.p_vaddr:
                max_addr = header.p_vaddr + header.p_memsz
                page_align = header.p_align
                if max_addr % page_align:
                    max_addr += page_align - (max_addr % page_align)
    page_align = page_size
    if max_addr % page_align:
        max_addr += page_align - (max_addr % page_align)

    if max_addr < 0x400000:
        return 0x400000
    return max_addr

def get_next_vaddr(filename, page_size):
    with open(filename, 'rb') as f:
        data = f.read()
        program_header_list = get_program_header_list(data)
        return get_vaddr_max(program_header_list, page_size)


def run(target, reassem_path, output, page_size, asan, verbose):

    #elf = ElfInfo(target)
    #lopt_list2 = elf.get_ld_option()

    import subprocess
    result = subprocess.run(['ldd', target], stdout=subprocess.PIPE)
    lines = result.stdout.decode('utf-8').split('\n')
    lopt_list = []
    errors = []
    for opt in lines:
        if "=> " in opt:
            lopt_list.append(opt.split()[2])
        elif 'linux-vdso.so' in opt:
           continue
        elif 'not found' in opt:
            errors.append(opt.split()[0])
        elif opt.split():
            lopt_list.append(opt.split()[0])

    if errors:
        for err in errors:
            print('[-] We could not compile the code since %s could not found'%(err))
        return

    filename = os.path.basename(target)

    compiler = '/usr/bin/gcc-11'

    lopt = ''
    if asan:
        lopt = '-lasan '

    for opt in lopt_list[:]:

        #if opt in ['-lstdc++']:
        if opt.startswith('libstdc++.so'):
            compiler = '/usr/bin/g++-11'
        #elif opt in ['-lgfortran']:
        elif opt.startswith('libgfortran.so'):
            compiler = '/usr/bin/gfortran-11'
        #elif opt in ['-lc']:
        elif opt.startswith('libc.so'):
            continue

        lopt += opt + ' '

    if verbose:
        print(lopt_list)
        print(lopt)
    #lopt += ' -Wl,--section-start=.interp=%s -Wl,--section-start=.note.ABI-tag=0x1000,--section-start=.my_rodata=%s'%\
    #        (hex(get_next_vaddr(target, page_size)), hex(elf._rodata_base_addr))
    lopt += ' -Wl,--section-start=.interp=%s -Wl,--section-start=.note.ABI-tag=0x1000'%\
            (hex(get_next_vaddr(target, page_size)))
    lopt += ' -fcf-protection=full -pie -fPIE'
    lopt += ' -fcf-protection=full -pie -fPIE'
    lopt += ' -Wl,-z,lazy'


    abs_path = os.path.abspath(output)
    base = os.path.dirname(abs_path)
    filename = os.path.basename(output)
    tmp_file = '%s/tmp_%s'%(base, filename)
    my_file = '%s/my_%s'%(base, filename)

    if verbose:
        print("%s %s %s -o %s "%(compiler, reassem_path, lopt, tmp_file))
    os.system("%s %s %s -o %s "%(compiler, reassem_path, lopt, tmp_file))
    sys.stdout.flush()

    cur_dir = os.path.dirname(os.path.realpath(__file__))
    #print("python3 %s/ElfBricks.py %s %s %s"%(cur_dir, target, tmp_file, my_file))
    os.system("python3 %s/ElfBricks.py %s %s %s"%(cur_dir, target, tmp_file, my_file))

    if verbose:
        print('chmod +x %s'%(my_file))
    os.system('chmod +x %s'%(my_file))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('target', type=str, help='target')
    parser.add_argument('code', type=str, help='code')
    parser.add_argument('output', type=str, help='output')
    parser.add_argument('--page-size', type=int, dest='page_size', default=0x200000)
    parser.add_argument('--asan', action='store_true')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    run(args.target, args.code, args.output, args.page_size, args.asan, args.verbose)

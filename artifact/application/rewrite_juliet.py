import os, sys
import glob
import multiprocessing
from collections import namedtuple

CWES = [124, 126, 127, 122, 121, 129]

failures = set()

def run_docker(cmd):
    pwd = os.getcwd()
    dock_cmd = 'docker run --rm -v %s:/input -v %s:/output suri:v1.0 sh -c " %s"'%(pwd, pwd, cmd)
    os.system(dock_cmd)


ConfRetro = namedtuple('ConfRetro', ['file_name', 'asm_file', 'bin_file'])

def make_retro(args):
    target, asm_file, bin_file = args
    if not os.path.exists(asm_file):
        run_docker('python3 /project/retrowrite/retrowrite --asan /input/%s /output/%s'%(target, asm_file))

    if not os.path.exists(bin_file):
        os.system('g++ %s -lasan -lpthread -o %s'%(asm_file, bin_file))

    print(bin_file)

def build_retro(core):

    conf_list = []
    for target in glob.glob('bin_original/CWE*/*/*'):
        dir_name = os.path.dirname(target).replace('bin_original', 'bin_retro')
        base_name = os.path.basename(target)
        if not base_name.endswith('.bin'):
            continue

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        name = base_name[:-4]
        asm_file = os.path.join(dir_name, name + '.s')
        bin_file = os.path.join(dir_name, base_name)
        conf_list.append(ConfRetro(target, asm_file, bin_file))

    if core and core > 1:
        p = multiprocessing.Pool(core)
        p.map(make_retro, conf_list)
    else:
        for conf in conf_list:
            make_retro(conf)

ConfSURI = namedtuple('ConfSURI', ['target', 'b2r2_meta', 'b2r2_asan', 'asm_file', 'dirname'])

def make_suri(args):

    target, b2r2_meta, b2r2_asan, asm_file, dirname = args

    cmd_list = []
    cmd_list.append('dotnet run --project=/project/B2R2/src/Test /input/%s /output/%s'%(target, b2r2_meta))
    cmd_list.append('dotnet run --project=/project/B2R2/src/Test /input/%s /output/%s asan'%(target, b2r2_asan))
    cmd_list.append('python3 /project/superSymbolizer/SuperAsan.py /input/%s /output/%s /output/%s /output/%s'%(target, b2r2_meta, b2r2_asan, asm_file))
    cmd = ';'.join(cmd_list)
    run_docker(cmd)
    print(asm_file)

    src_dir = os.path.dirname(target)
    target_name = target.split('/')[-1]
    tmp_name = 'tmp_' + target_name
    new_name = 'my_' + target_name

    cmd_list = []
    pwd = os.getcwd()
    cmd_list.append('cd ../superSymbolizer')
    cmd_list.append('python3 CustomCompiler.py %s/%s %s/%s %s/%s --asan'%(pwd,target, pwd,asm_file, pwd,target))
    cmd_list.append('cd -')
    cmd_list.append('mv %s/%s %s/%s'%(src_dir, new_name, dirname, target_name ))
    cmd_list.append('rm %s'%(tmp_name))
    cmd = ';'.join(cmd_list)
    os.system(cmd)

def build_suri(core):

    conf_list = []
    for target in glob.glob('bin_original/CWE*/*/*'):
        dir_name = os.path.dirname(target).replace('bin_original', 'bin_suri')
        base_name = os.path.basename(target)
        if not base_name.endswith('.bin'):
            continue

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        name = base_name[:-4]
        b2r2_meta = os.path.join(dir_name, name + '.json')
        b2r2_asan = os.path.join(dir_name, name + '_asan.json')
        asm_file = os.path.join(dir_name, name + '.s')
        conf_list.append(ConfSURI(target, b2r2_meta, b2r2_asan, asm_file, dir_name))

    if core and core > 1:
        p = multiprocessing.Pool(core)
        p.map(make_suri, conf_list)
    else:
        for conf in conf_list:
            make_suri(conf)


def run(tool, core):
    if tool == 'retrowrite':
        build_retro(core)
    elif tool == 'suri':
        build_suri(core)



import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('tool', type=str, help='Tool')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    args = parser.parse_args()

    run(args.tool, args.core)

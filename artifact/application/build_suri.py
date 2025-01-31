import os, sys


# gcc -I./testcasesupport -DINCLUDEMAIN -o test.bin testcasesupport/io.c testcasesupport/std_thread.c testcases/CWE78_OS_Command_Injection/s02/CWE78_OS_Command_Injection__char_console_system_01.c
# CWE-121/122/124/126/127

CWES = [121, 122, 124, 126, 127, 129]

failures = set()

def run_docker(cmd):
    pwd = os.getcwd()
    dock_cmd = 'docker run --rm -v %s:/input -v %s:/output suri:v1.0 sh -c " %s"'%(pwd, pwd, cmd)
    os.system(dock_cmd)

def make_suri(target, b2r2_meta, b2r2_asan, asm_file, dirname):

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

import glob

def build_suri(out_dir, dir_name):

    for target in glob.glob('bin_original/CWE*/*/*'):
        print(target)
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
        make_suri(target, b2r2_meta, b2r2_asan, asm_file, dir_name)

def main(out_dir):
    for cwe in CWES:
        for dir_name in os.listdir('./C/testcases'):
            if dir_name.startswith('CWE%d' % cwe):
                build_suri(out_dir, dir_name)
                


if __name__ == '__main__':
    if len(sys.argv) < 2:
        out_dir = './bin_suri'
    else:
        # out_dir should be a valid path
        out_dir = sys.argv[1]

    os.system('mkdir -p %s' % out_dir)
    main(out_dir)

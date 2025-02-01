import os, sys
import glob


# gcc -I./testcasesupport -DINCLUDEMAIN -o test.bin testcasesupport/io.c testcasesupport/std_thread.c testcases/CWE78_OS_Command_Injection/s02/CWE78_OS_Command_Injection__char_console_system_01.c
# CWE-121/122/124/126/127

CWES = [124, 126, 127, 122, 121, 129]

failures = set()

def run_docker(cmd):
    print(cmd)
    pwd = os.getcwd()
    dock_cmd = 'docker run --rm -v %s:/input -v %s:/output suri_artifact:v1.0 sh -c " %s"'%(pwd, pwd, cmd)
    os.system(dock_cmd)


def make_retro(target, asm_file, bin_file):

    if not os.path.exists(asm_file):
        run_docker('python3 /project/retrowrite/retrowrite --asan /input/%s /output/%s'%(target, asm_file))

    if not os.path.exists(bin_file):
        os.system('g++ %s -lasan -lpthread -o %s'%(asm_file, bin_file))

    print(bin_file)


from collections import namedtuple
BuildConf = namedtuple('BuildConf', ['file_name', 'tc_dir', 'sub_name', 'dir_name'])

def build_retro(out_dir, dir_name):

    for target in glob.glob('bin_original/CWE*/*/*'):
        print(target)
        dir_name = os.path.dirname(target).replace('bin_original', 'bin_retro')
        base_name = os.path.basename(target)
        if not base_name.endswith('.bin'):
            continue

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        name = base_name[:-4]
        asm_file = os.path.join(dir_name, name + '.s')
        bin_file = os.path.join(dir_name, base_name)
        make_retro(target, asm_file, bin_file)

def main(out_dir):
    for cwe in CWES:
        for dir_name in os.listdir('/data5/juliet/C/testcases'):
            if dir_name.startswith('CWE%d' % cwe):
                build_retro(out_dir, dir_name)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        out_dir = './bin_original'
    else:
        out_dir = sys.argv[1]

    os.system('mkdir -p %s' % out_dir)
    main(out_dir)

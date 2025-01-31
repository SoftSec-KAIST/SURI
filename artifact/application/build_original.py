import os, sys
import multiprocessing


# gcc -I./testcasesupport -DINCLUDEMAIN -o test.bin testcasesupport/io.c testcasesupport/std_thread.c testcases/CWE78_OS_Command_Injection/s02/CWE78_OS_Command_Injection__char_console_system_01.c
# CWE-121/122/124/126/127

CWES = [121, 122, 124, 126, 127, 129]

failures = set()

def build_cwe(inputs):
    out_dir, dir_name = inputs
    base_dir = os.path.join('./C/testcases', dir_name)
    for sub_name in os.listdir(base_dir):
        if not sub_name.startswith('s'):
            continue

        tc_dir = os.path.join(base_dir, sub_name)

        done = set()

        for file_name in os.listdir(tc_dir):
            if file_name.startswith(dir_name) and (file_name.endswith('.c') or file_name.endswith('.cpp')):
                tokens = file_name.split('_')
                name = '_'.join(tokens[:-1])
                name += '_'
                for c in tokens[-1]:
                    if c in '0123456789':
                        name += c
                    else:
                        break
                if name in done:
                    continue
                done.add(name)
                srcs = []
                for fname in os.listdir(tc_dir):
                    if fname.startswith(name):
                        srcs.append(fname)

                bin_dir = os.path.join(out_dir, dir_name, sub_name)
                os.system('mkdir -p %s' % bin_dir)

                #src_path = os.path.join(tc_dir, file_name)
                bin_path = os.path.join(bin_dir, name + '.bin')
                cmd = ''
                cmd += 'g++-11'
                cmd += ' -fcf-protection=full -pie -fPIE '
                cmd += ' -I./C/testcasesupport'
                cmd += ' -DINCLUDEMAIN'
                cmd += ' -o %s' % bin_path
                cmd += ' ./C/testcasesupport/io.c'
                cmd += ' ./C/testcasesupport/std_thread.c'
                for fname in srcs:
                    cmd += ' %s' % os.path.join(tc_dir, fname)
                cmd += ' -lpthread'
                os.system(cmd)
                print(cmd)
                if not os.path.exists(bin_path):
                    failures.add(bin_path)

def main(out_dir):
    for cwe in CWES:
        targets = []
        for dir_name in os.listdir('./C/testcases'):
            if dir_name.startswith('CWE%d' % cwe):
                build_cwe(out_dir, dir_name)
                targets.append((out_dir, dir_name))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        out_dir = './bin_original'
    else:
        # out_dir should be a valid path
        out_dir = sys.argv[1]

    os.system('mkdir -p %s' % out_dir)
    main(out_dir)

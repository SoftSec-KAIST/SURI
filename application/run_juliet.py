import os, sys
import glob
import subprocess


# gcc -I./testcasesupport -DINCLUDEMAIN -o test.bin testcasesupport/io.c testcasesupport/std_thread.c testcases/CWE78_OS_Command_Injection/s02/CWE78_OS_Command_Injection__char_console_system_01.c
# CWE-121/122/124/126/127

CWES = [122, 124, 126, 127, 121, 129]

failures = set()


from collections import namedtuple
BuildConf = namedtuple('BuildConf', ['file_name', 'tc_dir', 'sub_name', 'dir_name'])

def single(target):

    log_file = '/'.join(target.split('/')[:2]) + '/logs/' + os.path.basename(target)

    dirname = os.path.dirname(log_file)
    if not os.path.exists(dirname):
        os.system('mkdir -p %s'%(dirname))

    if not os.path.exists(log_file):
        cmd = 'timeout 5 %s > %s 2>&1 '%(target, log_file)
        print(cmd)
        os.system(cmd)
    elif os.path.getsize(log_file) == 0:
        cmd = "script -qc 'timeout 5 %s' %s "%(target, log_file)
        print(log_file)
        os.system(cmd)


def job(target, multiple):

    log_file = '/'.join(target.split('/')[:2]) + '/logs/' + os.path.basename(target)

    dirname = os.path.dirname(log_file)
    if not os.path.exists(dirname):
        os.system('mkdir -p %s'%(dirname))

    cmd = 'timeout 5 %s > %s 2>&1 '%(target, log_file)
    if not os.path.exists(log_file):
        os.system('echo timeout > %s'%(log_file))
        os.system(cmd)

    res = subprocess.getoutput('grep "==ERROR" %s | wc -l'%(log_file))
    if res != '0':
        print(log_file)
        return
    for idx in range(multiple):
        os.system(cmd)
        res = subprocess.getoutput('grep "==ERROR" %s | wc -l'%(log_file))
        if res != '0':
            return

    print('not found')

import multiprocessing

def run_cwe(out_dir, dir_name, core, dataset, multiple):
    base_dir = os.path.join('./C/testcases', dir_name)
    conf_list = []


    pattern = '%s/*/*/*.bin'%(out_dir)

    print(pattern)
    for sub_name in glob.glob(pattern):

        target =  os.path.abspath (sub_name)

        filename = os.path.basename(target)
        conf_list.append(sub_name)

    if core and core > 1:
        p = multiprocessing.Pool(core)
        if dataset in ['original']:
            p.map(single, [(conf) for conf in conf_list])
        else:
            p.map(job, [(conf,multiple) for conf in conf_list])
    else:
        for conf in conf_list:
            if dataset in ['original']:
                single(conf)
            else:
                job(conf, multiple)

def main(out_dir, core, dataset, multiple):
    for cwe in CWES:
        for dir_name in os.listdir('./C/testcases'):
            if dir_name.startswith('CWE%d' % cwe):
                run_cwe(out_dir, dir_name, core, dataset, multiple)

    with open('./failed.txt', 'w') as f:
        for case in failures:
            f.write('%s\n' % case)

import argparse

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--multiple', type=int, default=1, help='Number of cores to use')

    args = parser.parse_args()

    assert args.dataset in ['original', 'asan', 'suri', 'retrowrite'], '"%s" is invalid.'%(args.dataset)


    out_dir = './bin_%s'%(args.dataset)

    os.system('mkdir -p %s' % out_dir)
    main(out_dir, args.core, args.dataset, args.multiple)

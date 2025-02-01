from collections import namedtuple
import glob, os, sys
import multiprocessing
import enum
from collections import namedtuple
from ctypes import *

BuildConf = namedtuple('BuildConf', ['cmd', 'dataset', 'log_dir', 'bExist'])


def gen_option(input_root, image, package):
    ret = []
    cnt = 0
    cwd = os.getcwd()
    if input_root == 'setA':
        log_root = 'log/setA'
    elif input_root == 'setB':
        log_root = 'log/setB'
    elif input_root == 'setC':
        log_root = 'log/setC'

    for arch in ['x64']:
        for comp in ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']:
            for popt in ['pie']:
                for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
                    for lopt in ['bfd', 'gold']:
                        sub_dir = '%s/%s/%s_%s'%(package, comp, opt, lopt)
                        test_dir = '%s/%s'%(input_root, sub_dir)
                        for dataset_dir in glob.glob('%s/*'%(test_dir)):
                            tool = dataset_dir.split('/')[-1]
                            log_dir = '%s/%s/%s'%(log_root, sub_dir, tool)
                            os.system('mkdir -p %s'%(log_dir))


                            bExist = os.path.exists('%s/log2.txt'%(log_dir))

                            cmd1 = 'cd %s'%(package)
                            cmd2 = '/bin/bash copy.sh > /logs/log1.txt 2>&1'
                            cmd3 = 'make check -j 8 > /logs/log2.txt 2>&1'

                            cmds = ';'.join([cmd1, cmd2, cmd3])
                            dock_cmd = 'docker run --rm -v "%s/%s:/dataset/" -v "%s/%s:/logs/" %s sh -c "%s"'%(cwd, dataset_dir, cwd, log_dir, image, cmds)

                            ret.append(BuildConf(dock_cmd, input_root, log_dir, bExist))

    return ret

def job(conf, reset=False):
    print(conf)
    sys.stdout.flush()
    os.system(conf)

    return

def run(input_root, image, package, core=1):
    if package not in ['coreutils-9.1', 'binutils-2.40']:
        return False
    config_list = gen_option(input_root, image, package)

    run_config_list = [ conf for conf in config_list if not conf.bExist ]

    if core and core > 1:
        p = multiprocessing.Pool(core)
        p.map(job, [(conf.cmd) for conf in run_config_list])
    else:
        for conf in run_config_list:
            job(conf.cmd)

    return config_list

def summary(config_list, dataset):
    stat = dict()

    for conf in config_list:
        with open('%s/log2.txt'%(conf.log_dir)) as fd:
            key = '/'.join(conf.log_dir.split('/')[:-1])
            tool = conf.log_dir.split('/')[-1]

            lines = fd.read().split('\n')
            if package == 'coreutils-9.1':
                value = set([line for line in lines if '# FAIL:' in line])
            else:
                value = set([line for line in lines if '# of expected passes' in line])


            if key not in stat:
                stat[key] = dict()

            stat[key][tool] = value

    report(dataset, stat, 'clang')
    report(dataset, stat, 'gcc')

def report(dataset, stat, comp):

    suri = 0
    ddisasm = 0
    egalito = 0

    stat = { k:v for (k,v) in stat.items() if comp in k}

    for key in sorted(stat.keys()):

        if stat[key]['original'] != stat[key]['suri']:
            print('[-] FAIL %s/suri'%(key))
            pass
        else:
            suri += 1

        if dataset == 'setA':
            if 'ddisasm' not in stat[key] or stat[key]['original'] != stat[key]['ddisasm']:
                #'print('[-] FAIL %s/ddisasm'%(key))
                pass
            else:
                ddisasm += 1

        if dataset == 'setB':
            if 'egalito' not in stat[key] or stat[key]['original'] != stat[key]['egalito']:
                #print('[-] FAIL %s/egalito'%(key))
                pass
            else:
                egalito += 1

    res1 = 'Fail'
    res2 = 'Fail'

    if suri == len(stat):
        res1 = 'Succ'

    if dataset == 'setA':
        if ddisasm == len(stat):
            res2 = 'Succ'
        print('%-15s (%-5s): %10s(%4d/%4d) %10s(%4d/%4d)'%(package, comp, res1, suri, len(stat), res2, ddisasm, len(stat)))
    elif dataset == 'setB':
        if egalito == len(stat):
            res2 = 'Succ'
        print('%-15s (%-5s): %10s(%4d/%4d) %10s(%4d/%4d)'%(package, comp, res1, suri, len(stat), res2, egalito, len(stat)))
    else:
        print('%-15s (%-5s): %10s(%4d/%4d)'%(package, comp, res1, suri, len(stat)))



import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, help='dataset')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], '"%s" is invalid. Please choose one from setA, setB, or setC.'%(args.dataset)

    if args.dataset in ['setA', 'setC']:
        image = 'suri_artifact:v1.0'
    elif args.dataset in ['setB']:
        image =  'suri_artifact_ubuntu18.04:v1.0'

    config_list = dict()
    for package in ['coreutils-9.1', 'binutils-2.40']:
        config_list[package] = run(args.dataset, image, package, args.core)

    if args.dataset == 'setA':
        print('%-15s %7s  %21s %21s'%('', '', 'suri', 'Ddiasm'))
    if args.dataset == 'setB':
        print('%-15s %7s  %21s %21s'%('', '', 'suri', 'Egalito'))
    if args.dataset == 'setC':
        print('%-15s %7s  %21s'%('', '', 'suri(no_ehframe)'))
    for package in ['coreutils-9.1', 'binutils-2.40']:
        summary(config_list[package], args.dataset)


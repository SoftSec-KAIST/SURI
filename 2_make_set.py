from collections import namedtuple
import glob, os, sys
import multiprocessing
import enum
from collections import namedtuple
from ctypes import *
from suri_utils import check_exclude_files

BuildConf = namedtuple('BuildConf', ['target', 'input_root', 'sub_dir', 'reassem_path', 'comp', 'pie', 'package', 'bin'])

def gen_option(input_root, reassem_root, dataset, package, blacklist, whitelist):
    ret = []
    cnt = 0
    comp_set =  ['clang-10', 'clang-13', 'gcc-11', 'gcc-13']

    for arch in ['x64']:
        for comp in comp_set:
            for popt in ['pie']:
                for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
                    for lopt in ['bfd', 'gold']:
                        sub_dir = '%s/%s/%s_%s'%(package, comp, opt, lopt)
                        input_dir = '%s/%s'%(input_root, sub_dir)
                        for target in glob.glob('%s/stripbin/*'%(input_dir)):

                            filename = os.path.basename(target)
                            binpath = '%s/stripbin/%s'%(input_dir, filename)

                            reassem_dir = '%s/%s/%s'%(reassem_root, sub_dir, filename)

                            if blacklist and filename in blacklist:
                                continue
                            if whitelist and filename not in whitelist:
                                continue

                            if check_exclude_files(dataset, package, comp, opt, filename):
                                continue

                            ret.append(BuildConf(target, input_root, sub_dir, reassem_dir, comp, popt, package, binpath))

                            cnt += 1
    return ret


def copy(src, dst, filename):
    if os.path.exists(src):
        if not os.path.exists(dst):
            os.system('mkdir -p %s'%(dst))

        if not os.path.exists('%s/%s'%(dst, filename)):
            print('cp %s %s/%s'%(src, dst, filename))
            os.system('cp %s %s/%s'%(src, dst, filename))


def create_set(dataset, conf, filename):

    output = './%s'%(dataset)

    org_bin = conf.bin
    org_to = '%s/%s/original'%(output, conf.sub_dir)

    super_bin = '%s/super/my_%s'%(conf.reassem_path, filename)
    super_to = '%s/%s/suri'%(output, conf.sub_dir)

    copy(org_bin, org_to, filename)
    copy(super_bin, super_to, filename)

    if args.dataset == ['setA']:
        ddisasm_bin = '%s/ddisasm/%s'%(conf.reassem_path, filename)
        ddisasm_to = '%s/%s/ddisasm'%(output, conf.sub_dir)
        copy(ddisasm_bin, ddisasm_to, filename)

    if args.dataset == ['setB']:
        ddisasm_bin = '%s/egalito/%s'%(conf.reassem_path, filename)
        ddisasm_to = '%s/%s/egalito'%(output, conf.sub_dir)
        copy(egalito_bin, egalito_to, filename)

def run(input_root, reassem_root, dataset, package, core=1, blacklist=None, whitelist=None):

    config_list = gen_option(input_root, reassem_root, dataset, package, blacklist, whitelist)

    for conf in config_list:
        filename = os.path.basename(conf.bin)
        create_set(dataset, conf, filename)


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, help='dataset')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--package', type=str, help='Package')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], '"%s" is invalid. Please choose one from setA, setB, or setC.'%(args.dataset)

    input_root = './%s/%s'%(args.input_dir, args.dataset)
    output_root = './%s/%s'%(args.output_dir, args.dataset)

    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
        run(input_root, output_root, args.dataset, package, args.core, args.blacklist, args.whitelist)

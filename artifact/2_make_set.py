import argparse, glob, os
from collections import namedtuple
from ctypes import *
from filter_utils import check_exclude_files
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'input_dir', 'output_dir', 'set_dir', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--package', type=str, help='Package')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')
    args = parser.parse_args()

    # Sanitizing arguments
    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

################################

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                input_base = os.path.join(args.input_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                output_base = os.path.join(args.output_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                strip_dir = os.path.join(input_base, 'stripbin', '*')
                set_dir = os.path.join('.', args.dataset, package, comp, '%s_%s' % (opt, lopt))

                for target in glob.glob(strip_dir):
                    filename = os.path.basename(target)

                    # Filter binaries
                    if args.blacklist and filename in args.blacklist:
                        continue
                    if args.whitelist and filename not in args.whitelist:
                        continue
                    if check_exclude_files(args.dataset, package, comp, opt, filename):
                        continue

                    bin_dir = os.path.join(input_base, 'stripbin')
                    out_dir = os.path.join(output_base, filename)
                    tasks.append(ExpTask(args.dataset, bin_dir, out_dir, set_dir, filename))

    return tasks

################################

def copy(src, dst):
    if os.path.exists(src) and not os.path.exists(dst):
        print('cp %s %s' % (src, dst))
        os.system('cp %s %s' % (src, dst))

def build_set(task):
    orig_src_path = os.path.join(task.input_dir, task.bin_name)
    orig_dst_dir = os.path.join(task.set_dir, 'original')
    os.system('mkdir -p %s' % orig_dst_dir)
    orig_dst_path = os.path.join(orig_dst_dir, task.bin_name)
    copy(orig_src_path, orig_dst_path)

    suri_src_path = os.path.join(task.output_dir, 'super', 'my_%s' % task.bin_name)
    suri_dst_dir = os.path.join(task.set_dir, 'suri')
    os.system('mkdir -p %s' % suri_dst_dir)
    suri_dst_path = os.path.join(suri_dst_dir, task.bin_name)
    copy(suri_src_path, suri_dst_path)

    if task.dataset == 'setA':
        ddisasm_src_path = os.path.join(task.output_dir, 'ddisasm', task.bin_name)
        ddisasm_dst_dir = os.path.join(task.set_dir, 'ddisasm')
        os.system('mkdir -p %s' % ddisasm_dst_dir)
        ddisasm_dst_path = os.path.join(ddisasm_dst_dir, task.bin_name)
        copy(ddisasm_src_path, ddisasm_dst_path)
    elif task.dataset == 'setB':
        egalito_src_path = os.path.join(task.output_dir, 'egalito', task.bin_name)
        egalito_dst_dir = os.path.join(task.set_dir, 'egalito')
        os.system('mkdir -p %s' % egalito_dst_dir)
        egalito_dst_path = os.path.join(egalito_dst_dir, task.bin_name)
        copy(egalito_src_path, egalito_dst_path)

################################

def run(args, package):
    tasks = prepare_tasks(args, package)
    for task in tasks:
        build_set(task)

if __name__ == '__main__':
    args = parse_arguments()
    for package in PACKAGES:
        run(args, package)

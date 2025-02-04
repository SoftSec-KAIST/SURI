from collections import namedtuple
import glob, os, sys
import multiprocessing
from filter_utils import check_exclude_files
import argparse

ExpTask = namedtuple('ExpTask', ['dataset', 'input_dir', 'output_dir', 'prefix', 'bin_name'])

PACKAGES = ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006']
COMPILERS = ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']
OPTIMIZATIONS = ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']
LINKERS = ['bfd', 'gold']

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--package', type=str, help='Select package (coreutils-9.1, binutils-2.40, spec_cpu2017, spec_cpu2006)')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)
    if args.package:
        assert args.package in PACKAGES, 'Invalid package: "%s"'%(args.package)

    return args

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                input_base = os.path.join(args.input_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                output_base = os.path.join(args.output_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                strip_dir = os.path.join(input_base, 'bin', '*')
                prefix = '_'.join([package, comp, opt, lopt])

                for target in glob.glob(strip_dir):
                    filename = os.path.basename(target)

                    # Filter binaries
                    if args.blacklist and filename in args.blacklist:
                        continue
                    if args.whitelist and filename not in args.whitelist:
                        continue
                    if check_exclude_files(args.dataset, package, comp, opt, filename):
                        continue

                    bin_dir = os.path.join(input_base, 'bin')
                    out_dir = os.path.join(output_base, filename)
                    tasks.append(ExpTask(args.dataset, bin_dir, out_dir, prefix, filename))

    return tasks

################################

def run_task(task):
    bin_path = os.path.join(task.input_dir, task.bin_name)

    b2r2_func_path = os.path.join(task.output_dir, 'super', 'tmp_%s' % task.bin_name)

    stat_dir = os.path.join('stat', 'size', task.dataset)
    os.system('mkdir -p %s' % stat_dir)
    out_path = os.path.join(stat_dir, task.prefix + '_' + task.bin_name)
    if os.path.exists(out_path):
        return
    print(out_path)

    os.system("objdump -d %s -j .text --no-show-raw-insn | grep '^ \s*[0-9a-f]' | grep -v 'xor    %%eax,%%eax' | grep -v 'xor    %%eax,%%eax' | grep -v 'data16 nop' | grep -v '\snop' | wc -l > %s" % (bin_path, out_path))
    os.system("objdump -d %s -j .text --no-show-raw-insn | grep '^ \s*[0-9a-f]' | grep -v 'xor    %%eax,%%eax' | grep -v 'xor    %%eax,%%eax' | grep -v 'data16 nop' | grep -v '\snop' | wc -l >> %s" % (b2r2_func_path, out_path))

def run_package(args, package):
    tasks = prepare_tasks(args, package)
    p = multiprocessing.Pool(args.core)
    p.map(run_task, tasks)

def run(args):
    if args.package:
        run_package(args, args.package)
    else:
        for package in PACKAGES:
            run_package(args, package)

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

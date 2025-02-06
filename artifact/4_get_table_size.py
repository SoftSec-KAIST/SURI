import argparse, glob, multiprocessing, os, sys
from collections import namedtuple
from filter_utils import check_exclude_files
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'output_dir', 'gt_dir', 'prefix', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--package', type=str, help='Select package (coreutils-9.1, binutils-2.40, spec_cpu2017, spec_cpu2006)')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--target', type=str)
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')
    args = parser.parse_args()

    # Sanitizing arguments
    assert args.dataset in ['setA', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)
    if args.package:
        assert args.package in PACKAGES, 'Invalid package: "%s"'%(args.package)

    return args

################################

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                input_base = os.path.join(args.input_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                output_base = os.path.join(args.output_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                gt_base = os.path.join('gt', args.dataset, package, comp, '%s_%s' % (opt, lopt))
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

                    out_dir = os.path.join(output_base, filename)
                    gt_dir = os.path.join(gt_base, filename)
                    tasks.append(ExpTask(args.dataset, out_dir, gt_dir, prefix, filename))

    return tasks

################################

def job(task):
    b2r2_func_path = os.path.join(task.output_dir, 'super', 'b2r2_meta.json')
    if not os.path.exists(b2r2_func_path):
        return

    gt_func_path = os.path.join(task.gt_dir, 'norm_db', 'func.json')
    if not os.path.exists(gt_func_path):
        #print(' [-] %s does not exist'%(gt_func_path))
        return

    stat_dir = os.path.join('stat', 'table', task.dataset)
    os.system('mkdir -p %s' % stat_dir)
    out_path = os.path.join(stat_dir, task.prefix + '_' + task.bin_name)
    if os.path.exists(out_path):
        return
    print(out_path)

    sys.stdout.flush()
    os.system("python3 table_size.py %s %s > %s" % (gt_func_path, b2r2_func_path, out_path))

def run_package(args, package):
    tasks = prepare_tasks(args, package)
    p = multiprocessing.Pool(args.core)
    p.map(job, tasks)

def run(args):
    if args.package:
        run_package(args, args.package)
    else:
        for package in PACKAGES:
            run_package(args, package)

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

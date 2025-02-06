from collections import namedtuple
import glob, os, sys
import multiprocessing
from filter_utils import check_exclude_files
import argparse
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'compiler', 'output_dir', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                input_base = os.path.join(args.input_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                output_base = os.path.join(args.output_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                strip_dir = os.path.join(input_base, 'stripbin', '*')

                for target in glob.glob(strip_dir):
                    filename = os.path.basename(target)

                    # Filter binaries
                    if check_exclude_files(args.dataset, package, comp, opt, filename):
                        continue

                    out_dir = os.path.join(output_base, filename)
                    tasks.append(ExpTask(args.dataset, comp, out_dir, filename))
    return tasks

################################

def read_time_data(filename):
    with open(filename) as f:
        data = f.read()
        if not data:
            return 0
        t = data.split()[0]
        if 'Command' in t:
            return 0

        if len(t.split(':'))  == 3:
            hour = int(t.split(':')[0])
            minute = int(t.split(':')[1])
            sec = int(t.split(':')[2])
            return (hour*60*60+minute*60+sec)

        minute = int(t.split(':')[0])
        sec = float(t.split(':')[1])
        return (minute*60+sec)

# Returns the time taken to reassemble a binary, or None if it failed.
def get_data_suri(task, is_setC, verbose):
    if task.dataset == 'setC' and not is_setC:
        out_dir = os.path.join(task.output_dir.replace('setC', 'setA'), 'super')
    else:
        out_dir = os.path.join(task.output_dir, 'super')
    res_path = os.path.join(out_dir, 'my_' + task.bin_name)

    if os.path.exists(res_path):
        return read_time_data('%s/tlog1.txt'%(out_dir))
    else:
        if verbose:
            print(' [-] SURI fails to reassemble %s'%(res_path))
        return None

# Returns the time taken to reassemble a binary, or None if it failed.
def get_data_ddisasm(task, verbose):
    out_dir = os.path.join(task.output_dir, 'ddisasm')
    res_path = os.path.join(out_dir, task.bin_name)

    if os.path.exists(res_path):
        t_reasm = read_time_data('%s/tlog.txt'%(out_dir))
        t_compile = read_time_data('%s/tlog2.txt'%(out_dir))
        return t_reasm + t_compile
    else:
        if verbose:
            print(' [-] Ddisasm fails to reassemble %s'%(res_path))
        return None

# Returns the time taken to reassemble a binary, or None if it failed.
def get_data_egalito(target, verbose):
    out_dir = os.path.join(task.output_dir, 'egalito')
    res_path = os.path.join(out_dir, task.bin_name)

    if os.path.exists(res_path):
        return read_time_data('%s/tlogx.txt'%(out_dir))
    else:
        if verbose:
            print(' [-] Egalito fails to reassemble %s'% res_path)
        return None

# Returns the data for SURI and the comparison target
def get_data(task, verbose):
    d_suri = get_data_suri(task, False, verbose)
    if task.dataset == 'setA':
        d_target = get_data_ddisasm(task, verbose)
    elif task.dataset == 'setB':
        d_target = get_data_egalito(task, verbose)
    elif task.dataset == 'setC':
        d_target = get_data_suri(task, True, verbose)

    return d_suri, d_target

def collect_data(args, package):
    tasks = prepare_tasks(args, package)

    data = {}
    for task in tasks:
        d_suri, d_target = get_data(task, args.verbose)

        if task.compiler not in data:
            data[task.compiler] = 0, 0, 0, 0, 0.0, 0.0
        num_bins, suri_succ, target_succ, both_succ, suri_time, target_time = data[task.compiler]

        num_bins += 1
        if d_suri is not None:
            suri_succ += 1
        if d_target is not None:
            target_succ += 1
        if d_suri is not None and d_target is not None: # Time is counted when both tools succeed for a fair comparison
            suri_time += d_suri
            target_time += d_target
            both_succ += 1

        data[task.compiler] = num_bins, suri_succ, target_succ, both_succ, suri_time, target_time

    return data

################################

def print_header(dataset):
    if dataset == 'setA':
        print(FMT_REWRITE_HEADER % ('', 'suri', 'ddisasm'))
    elif dataset == 'setB':
        print(FMT_REWRITE_HEADER % ('', 'suri', 'egalito'))
    elif dataset == 'setC':
        print(FMT_REWRITE_HEADER % ('', 'suri', 'suri(no_ehframe)'))

def print_line():
    print(FMT_LINE)

def print_data(package, data):
    total_num_bins, total_suri_succ, total_target_succ, total_both_succ, total_suri_time, total_target_time = 0, 0, 0, 0, 0.0, 0.0
    for compiler in data:
        num_bins, suri_succ, target_succ, both_succ, suri_time, target_time = data[compiler]

        comp_base = compiler.split('-')[0]
        print(FMT_REWRITE_INDIVIDUAL % (package, comp_base, num_bins,
            suri_succ / num_bins * 100, suri_time/both_succ,
            target_succ / num_bins * 100, target_time/both_succ ))

        total_num_bins += num_bins
        total_suri_succ += suri_succ
        total_target_succ += target_succ
        total_both_succ += both_succ
        total_suri_time += suri_time
        total_target_time += target_time

    return total_num_bins, total_suri_succ, total_target_succ, total_both_succ, total_suri_time, total_target_time

def run(args):
    data = {}
    for package in PACKAGES:
        data[package] = collect_data(args, package)

    print_header(args.dataset)
    print_line()

    total_num_bins, total_suri_succ, total_target_succ, total_both_succ, total_suri_time, total_target_time = 0, 0, 0, 0, 0.0, 0.0
    for package in PACKAGES:
        num_bins, suri_succ, target_succ, both_succ, suri_time, target_time = print_data(package, data[package])
        total_num_bins += num_bins
        total_suri_succ += suri_succ
        total_target_succ += target_succ
        total_both_succ += both_succ
        total_suri_time += suri_time
        total_target_time += target_time

    if total_num_bins:
        print_line()
        print(FMT_REWRITE_TOTAL % ('all', total_num_bins,
            total_suri_succ / total_num_bins * 100, total_suri_time / total_both_succ ,
            total_target_succ / total_num_bins * 100, total_target_time / total_both_succ ))

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

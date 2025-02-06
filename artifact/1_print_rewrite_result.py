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

                for target in glob.glob(strip_dir):
                    filename = os.path.basename(target)

                    # Filter binaries
                    if check_exclude_files(args.dataset, package, comp, opt, filename):
                        continue

                    out_dir = os.path.join(output_base, filename)
                    tasks.append(ExpTask(args.dataset, comp, out_dir, filename))
    return tasks

################################

def is_valid_data(t):
    if 'Command' in t:
        return False
    return True

def read_time_data(filename):
    with open(filename) as f:
        data = f.read()
        t = data.split()[0]
        if not is_valid_data(t):
            return None

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

def collect_setA(args):
    data = {}
    for package in PACKAGES_SPEC:
        if package not in data:
            data[package] = {}

        tasks = prepare_tasks(args, package)
        for task in tasks:
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0, 0, 0, 0.0, 0.0

        suri_time = get_data_suri(task, False, args.verbose)
        target_time = get_data_ddisasm(task, args.verbose) # Comparison target is Ddisasm

        num_bins, suri_succ, target_succ, both_succ, sum_suri_time, sum_target_time = data[package][task.compiler]
        num_bins += 1
        if suri_time is not None:
            suri_succ += 1
        if target_time is not None:
            target_succ += 1
        if suri_time is not None and target_time is not None: # Time is counted when both tools succeed for a fair comparison
            both_succ += 1
            sum_suri_time += suri_time
            sum_target_time += target_time

        data[package][task.compiler] = num_bins, suri_succ, target_succ, both_succ, sum_suri_time, sum_target_time

    return data

def collect_setB(args):
    data = {}
    for package in PACKAGES_SPEC:
        if package not in data:
            data[package] = {}

        tasks = prepare_tasks(args, package)
        for task in tasks:
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0, 0, 0, 0.0, 0.0

        suri_time = get_data_suri(task, False, args.verbose)
        target_time = get_data_egalito(task, args.verbose) # Comparison target is Egalito

        num_bins, suri_succ, target_succ, both_succ, sum_suri_time, sum_target_time = data[package][task.compiler]
        num_bins += 1
        if suri_time is not None:
            suri_succ += 1
        if target_time is not None:
            target_succ += 1
        if suri_time is not None and target_time is not None: # Time is counted when both tools succeed for a fair comparison
            both_succ += 1
            sum_suri_time += suri_time
            sum_target_time += target_time

        data[package][task.compiler] = num_bins, suri_succ, target_succ, both_succ, sum_suri_time, sum_target_time

    return data

def collect_setC(args):
    data = {}
    for package in PACKAGES_SPEC:
        if package not in data:
            data[package] = {}

        tasks = prepare_tasks(args, package)
        for task in tasks:
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0, 0, 0, 0.0, 0.0

        suri_time = get_data_suri(task, False, args.verbose) # SURI on setA
        target_time = get_data_suri(task, True, args.verbose) # Comparison target is SURI on setC

        num_bins, suri_succ, target_succ, both_succ, sum_suri_time, sum_target_time = data[package][task.compiler]
        num_bins += 1
        if suri_time is not None:
            suri_succ += 1
        if target_time is not None:
            target_succ += 1
        if suri_time is not None and target_time is not None: # Time is counted when both tools succeed for a fair comparison
            both_succ += 1
            sum_suri_time += suri_time
            sum_target_time += target_time

        data[package][task.compiler] = num_bins, suri_succ, target_succ, both_succ, sum_suri_time, sum_target_time

    return data

# Collect data generated by 1_get_reassembled_code.py.
def collect(args):
    if args.dataset == 'setA':
        return collect_setA(args)
    elif args.dataset == 'setB':
        return collect_setB(args)
    else:
        return collect_setC(args)

################################

def print_header(dataset):
    if dataset == 'setA':
        print(FMT_REWRITE_HEADER % ('', 'suri', 'ddisasm'))
    elif dataset == 'setB':
        print(FMT_REWRITE_HEADER % ('', 'suri', 'egalito'))
    elif dataset == 'setC':
        print(FMT_REWRITE_HEADER % ('', 'suri', 'suri(no_ehframe)'))

# Report the partial results of the percentage of average success rates of
# reassembly for Table 2 and Table 3 of our paper.
def report(args, data):
    print_header(args.dataset)
    print(FMT_LINE)

    total_num_bins = 0
    total_suri_succ = 0
    total_target_succ = 0
    total_both_succ = 0
    total_suri_time = 0.0
    total_target_time = 0.0, 0.0
    for package in PACKAGES:
        if package not in data:
            continue

        for compiler in COMPILERS:
            if compiler not in data[package]:
                continue

            num_bins, suri_succ, target_succ, both_succ, suri_time, target_time = data[package][compiler]
            total_num_bins += num_bins
            total_suri_succ += suri_succ
            total_target_succ += target_succ
            total_both_succ += both_succ
            total_suri_time += suri_time
            total_target_time += target_time
            if num_bins > 0:
                comp_name = compiler.split('-')[0]
                avg_suri_succ = suri_succ / num_bins * 100
                avg_target_succ = target_succ / num_bins * 100
                avg_suri_time = suri_time / both_succ
                avg_target_time = target_time / both_succ
                print(FMT_REWRITE_INDIVIDUAL % (package, comp_name, num_bins,
                                                avg_suri_succ, avg_suri_time,
                                                avg_target_succ, avg_target_time))

    if total_num_bins > 0:
        print(FMT_LINE)
        total_avg_suri_succ = total_suri_succ / total_num_bins * 100
        total_avg_target_succ = total_target_succ / total_num_bins * 100
        total_avg_suri_time = total_suri_time / total_both_succ
        total_avg_target_time = total_target_time / total_both_succ
        print(FMT_REWRITE_TOTAL % ('all', total_num_bins,
                                   total_avg_suri_succ, total_avg_suri_time,
                                   total_avg_target_succ, total_avg_target_time))

if __name__ == '__main__':
    args = parse_arguments()
    data = collect(args)
    report(args, data)

import glob
import os
import argparse
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'log_dir', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA)')

    args = parser.parse_args()

    assert args.dataset in ['setA'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                data_dir = os.path.join(args.dataset, package, comp, '%s_%s' % (opt, lopt))
                log_dir = os.path.join('stat', 'suri_runtime', task.dataset, package, comp, '%s_%s' % (opt, lopt))
                if os.path.exists(data_dir):
                    orig_dir = os.path.join(data_dir, 'original')
                    for target in glob.glob(orig_dir):
                        filename = os.path.basename(target)
                        tasks.append(ExpTask(args.dataset, log_dir, filename))

    return tasks

################################

def read_time_data(filepath):
    with open(filepath) as f:
        line = f.read().split('\n')[-2]

        if 'seconds' not in line:
            print(line)
            return None

        time = line.split(';')[1].split()[0]
        assert line.split(';')[1].split()[1] in ['total', 'seconds']

        return int(time)

def get_data_original(task, package):
    log_path = os.path.join(task.log_dir, 'original', task.bin_name, '%s.txt' % task.bin_name)
    return read_time_data(log_path)

def get_data_suri(task, package):
    log_path = os.path.join(task.log_dir, 'suri', task.bin_name, '%s.txt' % task.bin_name)
    return read_time_data(log_path)

def collect_data(args, package):
    tasks = prepare_tasks(args, tasks)

    num_bins = 0
    overhead = 0.0
    for task in tasks:
        d_original = get_data_original(task, package)
        d_suri = get_data_suri(task, package)

        # TODO: check None
        num_bins += 1
        overhead += d_suri / d_original

    return num_bins, overhead

################################

def print_header():
    print('%20s |  %8s  '%('', 'suri'))

def print_data(package, data):
    num_bins, overhead = data
    if num_bins == 0:
        return

    print('%-15s %4d | %8f%%' % (package, num_bins,
                                    overhead / len(s_dict['original'])*100-100))

if __name__ == '__main__':
    args = parse_arguments()

    print_header()

    total_num_bins = 0
    total_overhead = 0.0
    for package in PACKAGES_SPEC:
        data = collect_data(args, package)
        print_data(package, data)

        num_bins, overhead = data
        total_num_bins += num_bins
        total_overhead += overhead

    if total_num_bins != 0:
        print('%-15s %4d | %8f%%'%('Total', total_num_bins, (total_overhead/total_num_bins)*100-100))

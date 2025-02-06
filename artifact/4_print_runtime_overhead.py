import glob
import os
import argparse
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

def prepare_tasks(args, package):
    comp = 'gcc-11'
    opt = 'o3'
    lopt = 'bfd'

    tasks = []
    data_dir = os.path.join(args.dataset, package, comp, '%s_%s' % (opt, lopt))
    if os.path.exists(data_dir):
        orig_dir = os.path.join(data_dir, 'original')
        for target in glob.glob(orig_dir):
            filename = os.path.basename(target)
            tasks.append(ExpTask(args.dataset, filename))

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
    log_path = os.path.join('stat', 'runtime', task.dataset, package, 'gcc-11', 'o3_bfd', 'original', task.bin_name, '%s.txt' % task.bin_name)
    return read_time_data(log_path)

def get_data_suri(task, package, is_setC):
    if task.dataset == 'setC' and not is_setC:
        dataset = 'setA'
    else:
        dataset = task.dataset
    log_path = os.path.join('stat', 'runtime', dataset, package, 'gcc-11', 'o3_bfd', 'suri', task.bin_name, '%s.txt' % task.bin_name)
    return read_time_data(log_path)

def get_data_ddisasm(task, package):
    log_path = os.path.join('stat', 'runtime', task.dataset, package, 'gcc-11', 'o3_bfd', 'ddisasm', task.bin_name, '%s.txt' % task.bin_name)
    return read_time_data(log_path)

def get_data_egalito(task, package):
    log_path = os.path.join('stat', 'runtime', task.dataset, package, 'gcc-11', 'o3_bfd', 'egalito', task.bin_name, '%s.txt' % task.bin_name)
    return read_time_data(log_path)

def collect_data(args, package):
    tasks = prepare_tasks(args, tasks)

    num_bins = 0
    suri_overhead = 0.0
    target_overhead = 0.0
    for task in tasks:
        if args.dataset in ['setA', 'setB']:
            if task.bin_name in RUNTIME_TARGET_LIST:
                d_original = get_data_original(task, package)
                d_suri = get_data_suri(task, package, False)
                if args.dataset == 'setA':
                    d_target = get_data_ddisasm(task, package)
                else:
                    d_target = get_data_egalito(task, package)

                # TODO: check None
                num_bins += 1
                suri_overhead += d_suri / d_original
                target_overhead += d_target / d_original
        else:
            d_original = get_data_original(task, package)
            d_suri = get_data_suri(task, package, True)
            d_target = get_data_suri(task, package, False)

            num_bins += 1
            suri_overhead += d_suri / d_original
            target_overhead += d_target / d_original

    return num_bins, suri_overhead, target_overhead

################################

def print_data(package, data):
    num_bins, suri_overhead, target_overhead = data
    if num_bins == 0:
        return

    print(FMT_RUANTIME_INDIVIDUAL % (package, num_bins,
                                    suri_overhead / len(s_dict['original'])*100-100 ,
                                    target_overhead / len(s_dict['original'])*100-100 ))

def print_header(dataset):
    if dataset == 'setA':
        print(FMT_RUNTIME_HEADER_AB % ('', 'suri', 'ddisasm'))
    elif dataset == 'setB':
        print(FMT_RUNTIME_HEADER_AB % ('', 'suri', 'egalito'))
    else:
        print(FMT_RUNTIME_HEADER_C % ('', 'suri', 'suri(no_ehframe)'))

if __name__ == '__main__':
    args = parse_arguments()

    print_header(args.dataset)

    total_num_bins = 0
    total_suri_overhead = 0.0
    total_target_overhead = 0.0
    for package in PACKAGES_SPEC:
        data = collect_data(args, package)
        print_data(package, data)

        num_bins, suri_overhead, target_overhead = data
        total_num_bins += num_bins
        total_suri_overhead += suri_overhead
        total_target_overhead += target_overhead

    print(FMT_RUNTIME_TOTAL % ('Total', total_num_bins, (total_suri_overhead / total_num_bins)*100-100, (total_target_overhead / total_num_bins)*100-100))

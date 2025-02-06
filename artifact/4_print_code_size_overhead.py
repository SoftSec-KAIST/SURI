import glob
import argparse
import os
from consts import *

def parse_arguments():
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

################################

def read_code_size_data(filepath):
    with open(filepath) as fd:
        data = fd.read()
        if len(data.split()) != 2:
            print(filepath)
            return None
        else:
            old_size, new_size = data.split()
            old_size = int(old_size)
            new_size = int(new_size)
            overhead = (new_size/old_size - 1)
        return overhead

def collect_data(dataset):
    base_folder = os.path.join('stat', 'size', dataset)

    data = {}
    for filepath in glob.glob('%s/*'%(base_folder)):
        size = read_code_size_data(filepath)

        package, compiler = filepath.split('/')[-1].split('_')[:2]
        if package in ['spec']:
            pack1, pack2, compiler = filepath.split('/')[-1].split('_')[:3]
            package = pack1 + '_' + pack2

        if package not in data:
            data[package] = {}
        if compiler not in data[package]:
            data[package][compiler] = 0, 0
        if size is not None:
            num_bins, overhead = data[package][compiler]
            num_bins += 1
            overhead += size
            data[package][compiler] = num_bins, overhead

    return data

################################

def print_line():
    print('-----------------------------------------------')

def run(args):
    data = collect_data(args.dataset)

    total_num_bins = 0
    total_overhead = 0
    for package in PACKAGES:
        if package not in data:
            continue

        pkg_num_bins = 0
        pkg_overhead = 0
        for compiler in data[package]:
            num_bins, overhead = data[package][compiler]
            pkg_num_bins += num_bins
            pkg_overhead += overhead

        print('%15s %10d %10f' % (package, pkg_num_bins, pkg_overhead/pkg_num_bins*100))

        total_num_bins += pkg_num_bins
        total_overhead += pkg_overhead

    print_line()
    print('%15s %10s %10f' % ('[+]All', total_num_bins, total_overhead/total_num_bins*100))

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

import glob
import re
import argparse
from consts import *

def parse_arguments():
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

def read_table_data(filepath):
    with open(filepath) as f:
        data = fd.read()
        lines = data.split('\n')
        if len(lines) < 7:
            print(filepath)
            return None

        if 'Size Overhead:' not in lines[-7]:
            assert False, 'Invalid file format %s'%(filepath)

        gt_ent = int(lines[-5].split()[-1])
        suri_ent = int(lines[-4].split()[-1])

        if gt_ent > 0:
            entry_overhead = (suri_ent - gt_ent) / gt_ent
        else:
            entry_overhead = 0

        return entry_overhead

def collect_data(args):
    base_folder = './stat/table/%s'%(args.dataset)

    data = {}
    for filepath in glob.glob('%s/*'%(base_folder)):
        entry_overhead = read_table_data(filepath)

        package, compiler = filepath.split('/')[-1].split('_')[:2]
        if package in ['spec']:
            pack1, pack2, compiler = filepath.split('/')[-1].split('_')[:3]
            package = pack1 + '_' + pack2

        if package not in data:
            data[package] = 0, 0

        num_bins, overhead = data[package]
        num_bins += 1
        overhead += entry_overhead
        data[package] = num_bins, overhead
    return data

def print_data(data)
    total_num_bins = 0
    total_overhead = 0.0
    print('Table-------------')
    for package in PACKAGES:
        tot_cnt = 0
        tot_sum = 0
        if package not in data:
            continue

        num_bins, overhead = data[package]
        print('%15s %10d %10f' % (package, num_bins, overhead / num_bins))

        total_num_bins += num_bins
        total_overhead += overhead

    print('%15s %10d %10f' % ('[+]All', total_num_bins, total_overhead / total_num_bins))

if __name__ == '__main__':
    args = parse_arguments()

    data = collect_data(args)
    print_data(data)

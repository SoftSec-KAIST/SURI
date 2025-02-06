import glob
import re
import argparse
from consts import *

def parse_arguments():
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')
    args = parser.parse_args()

    # Sanitizing arguments
    assert args.dataset in ['setA', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

################################

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

# Report the percentage of average table size overheads for Section 4.3.1 of our
# paper.
def report(data)
    print(FMT_TABLE_HEADER)
    print(FMT_LINE)

    total_num_bins = 0
    total_overhead = 0.0
    for package in PACKAGES:
        if package not in data:
            continue

        num_bins, overhead = data[package]
        total_num_bins += num_bins
        total_overhead += overhead
        if num_bins > 0:
            avg_overhead = overhead / num_bins * 100
            print(FMT_OVERHEAD % (package, num_bins, avg_overhead)) # Report individual data per package

    if total_num_bins > 0:
        print(FMT_LINE)
        total_avg_overhead = total_overhead / total_num_bins * 100
        print(FMT_OVERHEAD % ('[+]All', total_num_bins, total_avg_overhead)) # Report overall data

if __name__ == '__main__':
    args = parse_arguments()

    data = collect_data(args)
    report(data)

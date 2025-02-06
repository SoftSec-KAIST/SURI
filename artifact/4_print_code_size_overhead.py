import glob
import argparse
import os
from consts import *

def parse_arguments():
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')
    args = parser.parse_args()

    # Sanitizing arguments
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

        package = filepath.split('/')[-1].split('_')[0]
        if package in ['spec']:
            pack1, pack2 = filepath.split('/')[-1].split('_')[:2]
            package = pack1 + '_' + pack2

        if package not in data:
            data[package] = 0, 0
        if size is not None:
            num_bins, overhead = data[package]
            num_bins += 1
            overhead += size
            data[package] = num_bins, overhead

    return data

################################

# Report the percentage of average code size overheads for Section 4.3.1 of our
# paper.
def report(data):
    print(FMT_CODE_HEADER)
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
    data = collect_data(args.dataset)
    report(data)

import glob
import re
import argparse
import os

PACKAGES = ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006']

def parse_arguments():
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')

    args = parser.parse_args()
    assert args.dataset in ['setA', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

################################

def read_branch_data(filepath):
    with open(filepath) as f:
        data = f.read()
        (br1, br2) = re.findall('Indirect Branch Sites (.*) \((.*)\)', data.split('\n')[1])[0]
        br1 = int(br1)
        br2 = int(br2)
        if br1 != 0:
            return br2 / br1
        else:
            return None

def collect_data(dataset):
    base_folder = os.path.join('stat', 'bbl', dataset)

    data = dict()
    for filepath in glob.glob('%s/*'%(base_folder)):
        br = read_branch_data(filepath)

        package, compiler = filepath.split('/')[-1].split('_')[:2]
        if package in ['spec']:
            pack1, pack2, compiler = filepath.split('/')[-1].split('_')[:3]
            package = pack1 + '_' + pack2

        if package not in data:
            data[package] = dict()
        if compiler not in data[package]:
            data[package][compiler] = 0, 0
        if br is not None:
            num_bins, overhead = data[package][compiler]
            num_bins += 1
            overhead += br
            data[package][compiler] = num_bins, overhead

    return data

################################

def print_header():
    print('Multi Br-------------')

def run(args):
    base_folder = './stat/bbl/%s'%(args.dataset)
    data = collect_data(args.dataset)

    print_header()

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

    if total_num_bins > 0:
        print('%15s %10d %10f' % ('[+]All', total_num_bins, total_overhead/total_num_bins*100))

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

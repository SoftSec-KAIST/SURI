import glob
import os
import argparse

ExpTask = namedtuple('ExpTask', ['dataset', 'bin_name'])

PACKAGES = ['spec_cpu2017', 'spec_cpu2006']

TARGET_LIST = [
    '400.perlbench',
    '401.bzip2',
    '403.gcc',
    '410.bwaves',
    '429.mcf',
    '433.milc',
    '434.zeusmp',
    '435.gromacs',
    '436.cactusADM',
    '437.leslie3d',
    '444.namd',
    '445.gobmk',
    '447.dealII',
    '454.calculix',
    '456.hmmer',
    '458.sjeng',
    '459.GemsFDTD',
    '462.libquantum',
    '464.h264ref',
    '465.tonto',
    '470.lbm',
    '473.astar',
    '481.wrf',
    '482.sphinx3',
    '503.bwaves_r',
    '505.mcf_r',
    '507.cactuBSSN_r',  #
    '508.namd_r',       #
    '519.lbm_r',
    '531.deepsjeng_r',
    '538.imagick_r',    #
    '544.nab_r',
    '548.exchange2_r',
    '549.fotonik3d_r',
    '557.xz_r',
    '603.bwaves_s',
    '605.mcf_s',
    '607.cactuBSSN_s',  #
    '619.lbm_s',
    '628.pop2_s',
    '631.deepsjeng_s',
    '638.imagick_s',    #
    '644.nab_s',
    '648.exchange2_s',
    '657.xz_s'
]

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
            if task.bin_name in WHITE_LIST:
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

    print('%-15s %4d | %8f%% %8f%%' % (package, num_bins,
                                    suri_overhead / len(s_dict['original'])*100-100 ,
                                    target_overhead / len(s_dict['original'])*100-100 ))

def print_header(dataset):
    if dataset == 'setA':
        print('%20s |  %8s  %8s'%('', 'suri', 'ddisasm'))
    elif dataset == 'setB':
        print('%20s |  %8s  %8s'%('', 'suri', 'egalito'))
    else:
        print('%20s |  %8s  %15s'%('', 'suri', 'suri(no_ehframe)'))

if __name__ == '__main__':
    args = parse_arguments()

    print_header(args.dataset)

    total_num_bins = 0
    total_suri_overhead = 0.0
    total_target_overhead = 0.0
    for package in PACKAGES:
        data = collect_data(args, package)
        print_data(package, data)

        num_bins, suri_overhead, target_overhead = data
        total_num_bins += num_bins
        total_suri_overhead += suri_overhead
        total_target_overhead += target_overhead

    print('%-15s %4d | %8f%%  %15f%%' % ('Total', total_num_bins, (total_suri_overhead / total_num_bins)*100-100, (total_target_overhead / total_num_bins)*100-100))

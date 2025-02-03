from collections import namedtuple
import glob, os, sys
import multiprocessing
from filter_utils import check_exclude_files

BuildConf = namedtuple('BuildConf', ['output_path', 'comp', 'bin', 'dataset'])

COMPILERS = ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']
OPTIMIZATIONS = ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']
LINKERS = ['bfd', 'gold']

def gen_option(input_root, output_root, package, dataset):
    ret = []
    cnt = 0
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                sub_dir = '%s/%s/%s_%s'%(package, comp, opt, lopt)
                input_dir = '%s/%s'%(input_root, sub_dir)
                for target in glob.glob('%s/stripbin/*'%(input_dir)):

                    filename = os.path.basename(target)
                    binpath = '%s/stripbin/%s'%(input_dir, filename)

                    out_dir = '%s/%s/%s'%(output_root, sub_dir, filename)

                    if check_exclude_files(dataset, package, comp, opt, filename):
                        continue

                    ret.append(BuildConf(out_dir, comp, binpath, dataset))

                    cnt += 1
    return ret

def read_time(filename):
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

def check_super(root, filename, verbose):
    target = '%s/%s'%(root, filename)

    if os.path.exists(target):
        t1 = read_time('%s/tlog1.txt'%(root))
        if os.path.exists('%s/tlog2.txt'%(root)):
            t1 += read_time('%s/tlog2.txt'%(root))
        if os.path.exists('%s/tlog3.txt'%(root)):
            t1 += read_time('%s/tlog3.txt'%(root))
        return t1
    if verbose:
        print(' [-] SURI fails to reassemble %s'%(target))
    return 0.0

def check_ddisasm(root, filename, verbose):
    target = '%s/%s'%(root, filename)

    if os.path.exists(target):
        t1 = read_time('%s/tlog.txt'%(root))
        t2 = read_time('%s/tlog2.txt'%(root))
        return t1 + t2
    if verbose:
        print(' [-] Ddisasm fails to reassemble %s'%(target))
    return 0.0

def check_egalito(root, filename, verbose):
    target = '%s/%s'%(root, filename)
    if os.path.exists(target):
        t1 = read_time('%s/tlogx.txt'%(root))
        return t1, True
    if verbose:
        print(' [-] Egalito fails to reassemble %s'%(target))
    return 0.0, False

def job(conf, verbose):
    filename = os.path.basename(conf.bin)
    super_dir = '%s/super'%(conf.output_path)
    ddisasm_dir = '%s/ddisasm'%(conf.output_path)
    egalito_dir = '%s/egalito'%(conf.output_path)

    t1 = check_super(super_dir, 'my_'+filename, verbose)
    if conf.dataset == 'setA':
        t2 = check_ddisasm(ddisasm_dir, filename, verbose)
        egalito_succ = False
    elif conf.dataset == 'setB':
        t2, egalito_succ = check_egalito(egalito_dir, filename, verbose)
    elif conf.dataset == 'setC':
        t2 = check_super(super_dir.replace('setC','setA'), 'my_'+filename, verbose)
        egalito_succ = False

    return (filename, t1, t2, egalito_succ)



def run(input_root, output_root, dataset, package, verbose):

    if package not in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006' ]:
        return False

    config_list = gen_option(input_root, output_root, package, dataset)

    time_dict = dict()
    file_dict = dict()
    suri_dict = dict()
    other_dict = dict()
    for conf in config_list:
        if conf.comp not in time_dict:
            time_dict[conf.comp] = dict()
            file_dict[conf.comp] = 0
            suri_dict[conf.comp] = 0
            other_dict[conf.comp] = 0

        filename, t1, t2, egalito_succ = job(conf, verbose)
        if t1 > 0 and t2 > 0:
            if filename not in time_dict[conf.comp]:
                time_dict[conf.comp][filename] = []
            time_dict[conf.comp][filename].append((t1, t2))

        if t1 > 0:
            suri_dict[conf.comp] += 1
        if t2 > 0:
            other_dict[conf.comp] += 1
        elif egalito_succ:
            other_dict[conf.comp] += 1
        file_dict[conf.comp] += 1



    file_cnt, suri_cnt, other_cnt, suri_sum, other_sum = 0, 0, 0, 0, 0

    for comp_base in ['clang', 'gcc']:
        suri_sum_cnt = 0
        other_sum_cnt = 0
        file_sum_cnt = 0

        success = 0

        tot1 = 0
        tot2 = 0
        for comp in sorted(time_dict):
            if comp_base not in comp:
                continue

            filedict = time_dict[comp]
            for filename in filedict.keys():
                for (t1, t2) in time_dict[comp][filename]:
                    tot1 += t1
                    tot2 += t2
                    success += 1
            suri_sum_cnt += suri_dict[comp]
            other_sum_cnt += other_dict[comp]
            file_sum_cnt += file_dict[comp]

        if success == 0:
            continue

        print('%15s %10s (%4d) : %10f%% %10f : %10f%% %10f'%(package, comp_base, file_sum_cnt,
            suri_sum_cnt / file_sum_cnt * 100, tot1/success,
            other_sum_cnt / file_sum_cnt * 100, tot2/success ))

        file_cnt += file_sum_cnt
        suri_cnt += suri_sum_cnt
        other_cnt += other_sum_cnt
        suri_sum += tot1
        other_sum += tot2

    return file_cnt, suri_cnt, other_cnt, suri_sum, other_sum


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, help='dataset')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], '"%s" is invalid. Please choose one from setA, setB, or setC.'%(args.dataset)

    dataset = args.dataset
    input_root = './%s/%s'%(args.input_dir, args.dataset)
    output_root = './%s/%s'%(args.output_dir, args.dataset)

    if dataset == 'setA':
        print('%32s    %22s   %22s'%('', 'suri', 'ddisasm'))
    elif dataset == 'setB':
        print('%32s    %22s   %22s'%('', 'suri', 'egalito'))
    elif dataset == 'setC':
        print('%32s    %22s   %22s'%('', 'suri(no_ehframe)', 'suri'))

    print('-----------------------------------------------------------------------------------')

    file_cnt, suri_cnt, other_cnt, suri_sum, other_sum = 0, 0, 0, 0, 0
    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
        cnt1, cnt2, cnt3, cnt4, cnt5 = run(input_root, output_root, dataset, package, args.verbose)
        file_cnt += cnt1
        suri_cnt += cnt2
        other_cnt += cnt3
        suri_sum += cnt4
        other_sum += cnt5

    if file_cnt:
        print('----------------------------------------------------------------------------------')
        print('%26s (%4d) : %10f%% %10f : %10f%% %10f'%('all', file_cnt,
            suri_cnt / file_cnt * 100, suri_sum / file_cnt ,
            other_cnt / file_cnt * 100, other_sum / file_cnt ))

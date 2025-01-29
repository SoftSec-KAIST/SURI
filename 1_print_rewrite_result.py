from collections import namedtuple
import glob, os, sys
import multiprocessing
from suri_utils import check_exclude_files

BuildConf = namedtuple('BuildConf', ['target', 'input_root', 'sub_dir', 'output_path', 'comp', 'pie', 'package', 'bin'])

def gen_option(input_root, output_root, package):
    ret = []
    cnt = 0
    for arch in ['x64']:
        for comp in ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']:
            for popt in ['pie']:
                for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
                    for lopt in ['bfd', 'gold']:
                        sub_dir = '%s/%s/%s_%s'%(package, comp, opt, lopt)
                        input_dir = '%s/%s'%(input_root, sub_dir)
                        for target in glob.glob('%s/stripbin/*'%(input_dir)):

                            filename = os.path.basename(target)
                            binpath = '%s/stripbin/%s'%(input_dir, filename)

                            out_dir = '%s/%s/%s'%(output_root, sub_dir, filename)

                            if check_exclude_files(dataset, package, comp, opt, filename):
                                continue

                            ret.append(BuildConf(target, input_root, sub_dir, out_dir, comp, popt, package, binpath))

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
    root = root.replace('./output', '/data3/3_supersetCFG/output')
    target = '%s/%s'%(root, filename)

    if os.path.exists(target):
        t1 = read_time('%s/tlog1.txt'%(root))
        if t1 == 0:
            return 0.0
        t2 = read_time('%s/tlog2.txt'%(root))
        t3 = read_time('%s/tlog3.txt'%(root))
        return t1 + t2 + t3
    if verbose:
        print(' [-] SURI fails to reassemble %s'%(target))
    return 0.0

def check_ddisasm(root, filename, verbose):
    root = root.replace('./output', '/data5/2024/output')

    target = '%s/%s'%(root, filename)
    if os.path.exists(target):
        t1 = read_time('%s/tlog.txt'%(root))
        t2 = read_time('%s/tlog2.txt'%(root))
        return t1 + t2
    if verbose:
        print(' [-] Ddisasm fails to reassemble %s'%(target))
    return 0.0

def job(conf, verbose):
    filename = os.path.basename(conf.bin)
    super_dir = '%s/super'%(conf.output_path)
    ddisasm_dir = '%s/ddisasm'%(conf.output_path)

    t1 = check_super(super_dir, 'my_'+filename, verbose)
    t2 = check_ddisasm(ddisasm_dir, filename, verbose)

    return (filename, t1, t2)





def run(dataset, package, verbose):
    if package not in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006' ]:
        return False

    if dataset == 'setA':
        input_root = './benchmark/%s'%(dataset)
        output_root = './output/%s'(dataset)
    else:
        assert False, 'Invalid dataset'

    config_list = gen_option(input_root, output_root, package)

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

        filename, t1, t2 = job(conf, verbose)
        if t1 > 0 and t2 > 0:
            if filename not in time_dict[conf.comp]:
                time_dict[conf.comp][filename] = []
            time_dict[conf.comp][filename].append((t1, t2))

        if t1 > 0:
            suri_dict[conf.comp] += 1
        if t2 > 0:
            other_dict[conf.comp] += 1
        file_dict[conf.comp] += 1



    file_cnt, suri_cnt, other_cnt, suri_sum, other_sum = 0, 0, 0, 0, 0

    for comp_base in ['clang', 'gcc']:
        suri_sum_cnt = 0
        other_sum_cnt = 0
        file_sum_cnt = 0
        for comp in sorted(time_dict):
            if comp_base not in comp:
                continue

            filedict = time_dict[comp]
            success = 0

            tot1 = 0
            tot2 = 0
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

        print('%15s %10s  : %10f%% %10f : %10f%% %10f'%(package, comp_base,
            suri_sum_cnt / file_sum_cnt * 100, tot1/success,
            other_sum_cnt / file_sum_cnt * 100, tot2/success ))

        file_cnt += file_dict[comp]
        suri_cnt += suri_dict[comp]
        other_cnt += other_dict[comp]
        suri_sum += tot1
        other_sum += tot2

    return file_cnt, suri_cnt, other_cnt, suri_sum, other_sum


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, help='dataset')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    if args.dataset == ['setA']:
        print('%26s    %22s   %22s'%('', 'suri', 'ddisasm'))
    elif args.dataset == ['setB']:
        print('%26s    %22s   %22s'%('', 'suri', 'egalito'))
    elif args.dataset == ['setC']:
        print('%26s    %22s   %22s'%('', 'suri', 'suri(no_ehframe)'))

    print('-----------------------------------------------------------------------------')

    file_cnt, suri_cnt, other_cnt, suri_sum, other_sum = 0, 0, 0, 0, 0
    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
        cnt1, cnt2, cnt3, cnt4, cnt5 = run(args.dataset, package, args.verbose)
        file_cnt += cnt1
        suri_cnt += cnt2
        other_cnt += cnt3
        suri_sum += cnt4
        other_sum += cnt5

    print('-----------------------------------------------------------------------------')
    print('%26s  : %10f%% %10f : %10f%% %10f'%('all',
        suri_cnt / file_cnt * 100, suri_sum / file_cnt ,
        other_cnt / file_cnt * 100, other_sum / file_cnt ))

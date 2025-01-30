import glob
import re

def run(base_folder):
    res = dict()
    res2 = dict()
    for filepath in glob.glob('%s/*'%(base_folder)):
        with open(filepath) as fd:
            data = fd.read()
            overhead = eval(data.split('\n')[0].split()[-1])
            (br1, br2) =re.findall('Indirect Branch Sites (.*) \((.*)\)', data.split('\n')[1])[0]
            if int(br1) != 0:
                overhead2 = int(br2) / int(br1)

            package, compiler = filepath.split('/')[-1].split('_')[:2]

            if package in ['spec']:
                pack1, pack2, compiler = filepath.split('/')[-1].split('_')[:3]
                package = pack1 + '_' + pack2

            if package not in res:
                res[package] = dict()
                res2[package] = dict()
            if compiler not in res[package]:
                res[package][compiler] = []
                res2[package][compiler] = []
            res[package][compiler].append(overhead)
            if int(br1) != 0:
                res2[package][compiler].append(overhead2)

    print('BBL-------------')
    tot_tot_cnt = 0
    tot_tot_sum = 0
    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
        tot_cnt = 0
        tot_sum = 0
        for compiler in sorted(res[package].keys()):
            cnt = len(res[package][compiler])
            avg = sum(res[package][compiler]) / cnt
            print('%10s %10s %10d %10f'%(package, compiler, cnt, avg*100))
            tot_cnt += cnt
            tot_sum += sum(res[package][compiler])
        tot_tot_cnt += tot_cnt
        tot_tot_sum += tot_sum
        print()
    print('%10s %10s %10d %10f'%('[+]All', 'All', tot_tot_cnt, tot_tot_sum/tot_tot_cnt*100))
    print('Multi Br-------------')

    tot_tot_cnt = 0
    tot_tot_sum = 0
    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
        tot_cnt = 0
        tot_sum = 0
        for compiler in sorted(res2[package].keys()):
            cnt = len(res2[package][compiler])
            avg = sum(res2[package][compiler]) / cnt
            print('%10s %10s %10d %10f'%(package, compiler, cnt, avg*100))
            tot_cnt += cnt
            tot_sum += sum(res2[package][compiler])
        tot_tot_cnt += tot_cnt
        tot_tot_sum += tot_sum
        print()
    print('%10s %10s %10d %10f'%('[+]All', 'All', tot_tot_cnt, tot_tot_sum/tot_tot_cnt*100))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')

    args = parser.parse_args()
    assert args.dataset in ['setA', 'setC'], '"%s" is invalid. Please choose one from setA or setC.'%(args.dataset)

    base_folder = './stat/bbl/%s'%(args.dataset)
    run(base_folder)

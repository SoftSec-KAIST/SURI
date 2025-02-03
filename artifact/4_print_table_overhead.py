import glob
import re
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description='counter')
    #parser.add_argument('base_folder', type=str)
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')

    args = parser.parse_args()
    assert args.dataset in ['setA', 'setC'], '"%s" is invalid. Please choose one from setA or setC.'%(args.dataset)

    return args

def run(base_folder):
    res = dict()
    res2 = dict()
    for filepath in glob.glob('%s/*'%(base_folder)):
        with open(filepath) as fd:
            data = fd.read()
            lines = data.split('\n')
            if len(lines) < 7:
                print(filepath)
                continue
            if 'Size Overhead:' not in lines[-7]:
                assert False, 'Invalid file format %s'%(filepath)

            gt_ent = lines[-5].split()[-1]
            suri_ent = lines[-4].split()[-1]
            gt_inst = lines[-3].split()[-1]
            suri_inst = lines[-2].split()[-1]

            if int(gt_ent) > 0:
                overhead = (int(suri_ent) - int(gt_ent)) / int(gt_ent)
            overhead2 = int(suri_inst) / int(gt_inst)

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
            if overhead < 0 :
            #if overhead == overhead2:
                print(overhead)
                print(filepath)
            if int(gt_ent) > 0:
                res[package][compiler].append(overhead)
            res2[package][compiler].append(overhead2)

    tot_tot_cnt = 0
    tot_tot_sum = 0
    print('Table-------------')
    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
        tot_cnt = 0
        tot_sum = 0
        if package not in res:
            continue
        for compiler in sorted(res[package].keys()):
            cnt = len(res[package][compiler])
            avg = sum(res[package][compiler]) / cnt
            #print('%10s %10s %10d %10f'%(package, compiler, cnt, avg))
            tot_cnt += cnt
            tot_sum += sum(res[package][compiler])
        tot_tot_cnt += tot_cnt
        tot_tot_sum += tot_sum
        print('%15s %10d %10f'%(package, tot_cnt, tot_sum/tot_cnt))
    print('%15s %10d %10f'%('[+]All', tot_tot_cnt, tot_tot_sum/tot_tot_cnt))

if __name__ == '__main__':
    args = parse_arguments()

    base_folder = './stat/table/%s'%(args.dataset)
    run(base_folder)

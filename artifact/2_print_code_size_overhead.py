import glob

def run(base_folder):
    res = dict()
    for filepath in glob.glob('%s/*'%(base_folder)):
        with open(filepath) as fd:
            data = fd.read()
            if len(data.split()) != 2:
                print(filepath)
                continue
            old_size, new_size = data.split()
            old_size = int(old_size)
            new_size = int(new_size)
            overhead = (new_size/old_size - 1)
            package, compiler = filepath.split('/')[-1].split('_')[:2]
            if package in ['spec']:
                pack1, pack2, compiler = filepath.split('/')[-1].split('_')[:3]
                package = pack1 + '_' + pack2
            if package not in res:
                res[package] = dict()
            if compiler not in res[package]:
                res[package][compiler] = []
            res[package][compiler].append(overhead)

    tot_tot_cnt = 0
    tot_tot_sum = 0
    for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
        tot_cnt = 0
        tot_sum = 0

        if package not in res:
            continue

        for compiler in sorted(res[package].keys()):
            cnt = len(res[package][compiler])
            avg = sum(res[package][compiler]) / cnt
            #print('%10s %10s %10d %10f'%(package, compiler, cnt, avg*100))
            tot_cnt += cnt
            tot_sum += sum(res[package][compiler])

        print('%15s %10d %10f'%(package, tot_cnt, tot_sum/tot_cnt*100))
        tot_tot_cnt += tot_cnt
        tot_tot_sum += tot_sum
    print('-----------------------------------------------')
    print('%15s %10s %10f'%('[+]All', tot_tot_cnt, tot_tot_sum/tot_tot_cnt*100))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('dataset', type=str, help='dataset')
    args = parser.parse_args()

    assert args.dataset in ['setA', 'setC'], '"%s" is invalid. Please choose one from setA or setC.'%(args.dataset)

    input_dir = './stat/size/%s'%(args.dataset)

    run(input_dir)

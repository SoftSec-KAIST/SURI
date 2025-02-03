import glob
import os
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA)')
    args = parser.parse_args()
    assert args.dataset in ['setA'], '"%s" is invalid.'%(args.dataset)

    return args

def get_overhead(dataset, base_folder, package):

    s_dict = dict()
    s_dict['original'] = dict()
    s_dict['suri'] = dict()

    for folder in glob.glob('%s/%s/%s/*/*/*'%(base_folder, dataset, package)):
        for logfile in glob.glob('%s/*'%(folder)):
            if 'log.txt' in logfile:
                continue
            with open(logfile) as fd:
                line = fd.read().split('\n')[-2]

                if 'seconds' not in line:
                    print(line)
                    continue

                bin_name = os.path.basename(logfile)[:-4]
                tool = folder.split('/')[-1]
                key = '/'.join(folder.split('/')[:-1]) + bin_name

                if tool not in ['original', 'suri']:
                    continue


                val = line.split(';')[1].split()[0]
                assert line.split(';')[1].split()[1] in ['total', 'seconds']
                s_dict[tool][key] = int(val)

    tot = 0
    for key in s_dict['original']:
        tot += s_dict['suri'][key] / s_dict['original'][key]
    return tot, len(s_dict['original'])

if __name__ == '__main__':
    args = parse_arguments()

    base_folder = './stat/suri_runtime'
    print('%20s |  %8s  '%('', 'suri'))
    ov1 = 0
    nu1 = 0
    for package in ['spec_cpu2006', 'spec_cpu2017']:
        tot1, bins1 = get_overhead(args.dataset, base_folder, package)

        if bins1:
            print('%-15s %4d | %8f%%'%(package, bins1, (tot1/bins1)*100-100))
            ov1 += tot1
            nu1 += bins1
    if nu1:
        print('%-15s %4d | %8f%%'%('Total', nu1, (ov1/nu1)*100-100))



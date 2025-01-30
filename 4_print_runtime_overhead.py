import glob
import os

white_list=[
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

def run(dataset, base_folder, package):

    s_dict = dict()
    s_dict['original'] = dict()
    s_dict['suri'] = dict()
    s_dict['ddisasm'] = dict()
    s_dict['egalito'] = dict()

    for folder in glob.glob('%s/%s/gcc-11/o3_bfd/*'%(base_folder, package)):
        for logfile in glob.glob('%s/*'%(folder)):
            if 'log.txt' in logfile:
                continue
            with open(logfile) as fd:
                line = fd.read().split('\n')[-2]

                if 'seconds' not in line:
                    print(line)
                    continue

                tool = folder.split('/')[-1]
                key = os.path.basename(logfile)

                bin_name = key[:-4]
                if bin_name not in white_list:
                    continue

                val = line.split(';')[1].split()[0]
                assert line.split(';')[1].split()[1] in ['total', 'seconds']
                s_dict[tool][key] = int(val)

    tot = 0
    tot2 = 0
    for key in s_dict['original']:
        if s_dict['suri'][key] / s_dict['original'][key] > 1.1:
            #print('%10f: %s'%((s_dict['suri'][key] / s_dict['original'][key])*100, key))
            pass
        tot += s_dict['suri'][key] / s_dict['original'][key]
        if dataset == 'setA':
            tot2 += s_dict['ddisasm'][key] / s_dict['original'][key]
        elif dataset == 'setB':
            tot2 += s_dict['egalito'][key] / s_dict['original'][key]

        if 2 < s_dict['suri'][key] / s_dict['original'][key]:
            print(key)
            import pdb
            pdb.set_trace()


    print('%-15s %4d | %8f%% %8f%%'%(package, len(s_dict['original']),
                                    tot / len(s_dict['original'])*100-100 ,
                                    tot2 / len(s_dict['original'])*100-100 ))

    #print('remain: ', (31+47)*24-20 - len(s_dict['suri']))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB)')
    args = parser.parse_args()
    assert args.dataset in ['setA', 'setB'], '"%s" is invalid. Please choose one from setA or setB.'%(args.dataset)

    base_folder = './stat/runtime/%s'%(args.dataset)

    if args.dataset in ['setA']:
        print('%20s |  %8s  %8s'%('', 'suri', 'ddisasm'))
    if args.dataset in ['setB']:
        print('%20s | %8s %8s'%('', 'suri', 'egalito'))
    for package in ['spec_cpu2006', 'spec_cpu2017']:
        run(args.dataset, base_folder, package)

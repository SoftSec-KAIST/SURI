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
                if dataset in ['setA', 'setB'] and bin_name not in white_list:
                    continue

                val = line.split(';')[1].split()[0]
                assert line.split(';')[1].split()[1] in ['total', 'seconds']
                s_dict[tool][key] = int(val)

    tot = 0
    tot2 = 0
    for key in s_dict['original']:
        tot += s_dict['suri'][key] / s_dict['original'][key]
        if dataset == 'setA':
            tot2 += s_dict['ddisasm'][key] / s_dict['original'][key]
        elif dataset == 'setB':
            tot2 += s_dict['egalito'][key] / s_dict['original'][key]


    if (len(s_dict['original']) == 0):
        return;

    print('%-15s %4d | %8f%% %8f%%'%(package, len(s_dict['original']),
                                    tot / len(s_dict['original'])*100-100 ,
                                    tot2 / len(s_dict['original'])*100-100 ))


def get_overhead(dataset, base_folder, package):

    s_dict = dict()
    s_dict['original'] = dict()
    s_dict['suri'] = dict()

    for folder in glob.glob('%s/%s/%s/gcc-11/o3_bfd/*'%(base_folder, dataset, package)):
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

                if tool not in ['original', 'suri']:
                    continue

                bin_name = key[:-4]

                val = line.split(';')[1].split()[0]
                assert line.split(';')[1].split()[1] in ['total', 'seconds']
                s_dict[tool][key] = int(val)

    tot = 0
    for key in s_dict['original']:
        tot += s_dict['suri'][key] / s_dict['original'][key]
    return tot, len(s_dict['original'])




import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB)')
    args = parser.parse_args()
    assert args.dataset in ['setA', 'setB', 'setC'], '"%s" is invalid. Please choose one from setA, setB, or setC.'%(args.dataset)


    if args.dataset in ['setC']:
        base_folder = './stat/runtime'
        print('%20s |  %8s  %15s'%('', 'suri', 'suri(no_ehframe)'))
        ov1 = 0
        nu1 = 0
        ov2 = 0
        nu2 = 0
        for package in ['spec_cpu2006', 'spec_cpu2017']:
            tot1, bins1 = get_overhead('setA', base_folder, package)
            tot2, bins2 = get_overhead('setC', base_folder, package)

            if bins1 != bins2:
                print('[-] The number of tested binaries in %s are different'%(package))
                continue

            print('%-15s %4d | %8f%%  %15f%%'%(package, bins1, (tot1/bins1)*100-100, (tot2/bins2)*100-100))
            ov1 += tot1
            ov2 += tot2
            nu1 += bins1
            nu2 += bins2
        print('%-15s %4d | %8f%%  %15f%%'%('Total', nu1, (ov1/nu1)*100-100, (ov2/nu2)*100-100))

    else:
        base_folder = './stat/runtime/%s'%(args.dataset)
        if args.dataset in ['setA']:
            print('%20s |  %8s  %8s'%('', 'suri', 'ddisasm'))
        if args.dataset in ['setB']:
            print('%20s |  %8s  %8s'%('', 'suri', 'egalito'))
        for package in ['spec_cpu2006', 'spec_cpu2017']:
            run(args.dataset, base_folder, package)

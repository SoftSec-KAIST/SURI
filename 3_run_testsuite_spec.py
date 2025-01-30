from collections import namedtuple
import glob
import os
import multiprocessing

BuildConf = namedtuple('BuildConf', ['cmd', 'dataset', 'log_file', 'bExist'])

bin_dict = {
'482.sphinx3': 'sphinx_livepretend',
'483.xalancbmk': 'Xalan',
'500.perlbench_r': 'perlbench_r',
'502.gcc_r': 'cpugcc_r',
'503.bwaves_r': 'bwaves_r',
'505.mcf_r': 'mcf_r',
'507.cactuBSSN_r': 'cactusBSSN_r',
'508.namd_r': 'namd_r',
'510.parest_r': 'parest_r',
'511.povray_r': 'povray_r',
'519.lbm_r': 'lbm_r',
'520.omnetpp_r': 'omnetpp_r',
'521.wrf_r': 'wrf_r',
'523.xalancbmk_r': 'cpuxalan_r',
'525.x264_r': 'x264_r',
'526.blender_r': 'blender_r',
'527.cam4_r': 'cam4_r',
'531.deepsjeng_r': 'deepsjeng_r',
'538.imagick_r': 'imagick_r',
'541.leela_r': 'leela_r',
'544.nab_r': 'nab_r',
'548.exchange2_r': 'exchange2_r',
'549.fotonik3d_r': 'fotonik3d_r',
'554.roms_r': 'roms_r',
'557.xz_r': 'xz_r',
'600.perlbench_s': 'perlbench_s',
'602.gcc_s': 'sgcc',
'603.bwaves_s': 'speed_bwaves',
'605.mcf_s': 'mcf_s',
'607.cactuBSSN_s': 'cactuBSSN_s',
'619.lbm_s': 'lbm_s',
'620.omnetpp_s': 'omnetpp_s',
'621.wrf_s': 'wrf_s',
'623.xalancbmk_s': 'xalancbmk_s',
'625.x264_s': 'x264_s',
'627.cam4_s': 'cam4_s',
'628.pop2_s': 'speed_pop2',
'631.deepsjeng_s': 'deepsjeng_s',
'638.imagick_s': 'imagick_s',
'641.leela_s': 'leela_s',
'644.nab_s': 'nab_s',
'648.exchange2_s': 'exchange2_s',
'649.fotonik3d_s': 'fotonik3d_s',
'654.roms_s': 'sroms',
'657.xz_s': 'xz_s',
'996.specrand_fs': 'specrand_fs',
'997.specrand_fr': 'specrand_fr',
'998.specrand_is': 'specrand_is',
'999.specrand_ir': 'specrand_ir' }

def run(dataset, package, core):
    if package in ['spec_cpu2017']:
        run_script = 'run2017'
    elif package in ['spec_cpu2006']:
        run_script = 'run2006'

    if dataset in ['setA', 'setC']:
        image='suri_spec:v1.0'
    elif dataset in ['setB']:
        image='ubuntu18.04_spec2006'

    cur = os.getcwd()

    return make_script(dataset, image, package, run_script, cur, core)


def get_docker_cmd(cur, folder, script_folder, log_folder, run_script, image, cpu_id):
    cmd = 'docker run --rm '
    #cmd +=  '--memory 16g --cpus 1 '
    cmd +=  '--memory 16g --cpus 4 '
    cmd +=  '-v "%s/%s:/dataset/" '%(cur, folder)
    cmd +=  '-v "%s/%s:/script/" '%(cur, script_folder)
    cmd +=  '-v "%s/%s:/log/" '%(cur, log_folder)
    cmd +=  '%s '%(image)
    cmd +=  'sh -c "/bin/bash /script/%s" > %s/%s/log.txt 2>&1 '%(run_script, cur, log_folder)
    return cmd


def make_script(dataset, image, package, basename, cur, core):
    conf_list = []
    for linker in ['bfd', 'gold']:
        for comp in ['gcc-11', 'clang-13', 'gcc-13', 'clang-10']:
            for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
                ret = make_sub_script(dataset, image, package, basename, cur, linker, comp, opt)
                conf_list.extend(ret)

    cmd_list = [item.cmd for item in conf_list if not item.bExist]
    p = multiprocessing.Pool(core)
    p.map(job, cmd_list)
    return conf_list

def make_sub_script(dataset, image, package, basename, cur, linker, comp, opt):

    cpu_id = 0
    cmd_dict = dict()

    if dataset == 'setA':
        log_root = 'logA'
    elif dataset == 'setB':
        log_root = 'logB'
    elif dataset == 'setC':
        log_root = 'logC'

    for folder in glob.glob('%s/%s/%s/%s_%s/*'%(dataset, package, comp, opt, linker)):

        sub_folder = '/'.join(folder.split('/')[1:])

        script_folder = 'script/%s'%(sub_folder)
        log_folder = '%s/%s'%(log_root, sub_folder)
        os.system('mkdir -p %s'%(script_folder))
        os.system('mkdir -p %s'%(log_folder))

        for filepath in glob.glob(folder + '/*'):
            if 'original' in filepath:
                continue

            filename = os.path.basename(filepath)

            # 5 (opt) * 4 (comp) * 2 (linker) =  40
            if filename in ['416.gamess'] and opt not in ['o0']:
                continue
            # 1 (opt) * 1 (comp) * 2 (linker) = 2
            if filename in ['453.povray'] and opt in ['ofast'] and comp in ['gcc-13']:
                continue
            # 1 (opt) * 1 (comp) * 2 (linker) = 2
            if filename in ['511.povray_r'] and opt in ['ofast'] and comp in ['gcc-13']:
                continue

            run_script = basename + "_" + filename  + ".sh"
            log_file = '%s/%s.txt'%(log_folder, filename)

            if filename not in cmd_dict:
                cmd_dict[filename] = []

            if os.path.exists(log_file):
                cmd_dict[filename].append(BuildConf([], dataset, log_file, True))
                continue



            with open('%s/%s'%(script_folder, run_script), 'w') as f:

                if filename in bin_dict:
                    target = bin_dict[filename]
                else:
                    target = '.'.join(filename.split('.')[1:])

                print('cd /%s/'%(package), file=f)
                print('source shrc', file=f)
                print('ulimit -s unlimited', file=f)
                print('sleep 10', file=f)



                print('echo %s'%(filename), file=f)
                if package in ['spec_cpu2017']:
                    print('cp /dataset/%s /spec_cpu2017/benchspec/CPU/%s/exe/%s_base.case1_bfd.cfg-m64'%(filename, filename, target), file=f)
                    print('runcpu --action run --config case1_bfd.cfg --nobuild --iterations 1 --threads 4 %s > /log/%s.txt 2>&1'%(filename, filename), file=f)
                else:
                    print('cp /dataset/%s /spec_cpu2006/benchspec/CPU2006/%s/exe/%s_base.case1_bfd.cfg'%(filename, filename, target), file=f)
                    print('runspec --action run --config case1_bfd.cfg --nobuild --iterations 1 --threads 4 %s > /log/%s.txt 2>&1'%(filename, filename), file=f)


                cmd = get_docker_cmd(cur, folder, script_folder, log_folder, run_script, image, cpu_id)


                cmd_dict[filename].append(BuildConf(cmd, dataset, log_folder, False))

        cpu_id += 4

    ret = []
    for filename, cmd_list in cmd_dict.items():
        ret.extend(cmd_list)

    return ret


def job(cmd):
    print(cmd)
    os.system(cmd)
    pass


def summary(dataset, config_list):
    stat = dict()

    for conf in config_list:
        with open((conf.log_file)) as fd:
            key = '/'.join(conf.log_file.split('/')[:-2]) + '/' + conf.log_file.split('/')[-1].split('.txt')[0]
            tool = conf.log_file.split('/')[-2]


            try:
                data = fd.read()
                if 'Success:' in data:
                    value = True
                else:
                    value = False
            except UnicodeDecodeError:
                #print('[-] unicodeDecodeError: %s'%(conf.log_file))
                value = False

            if key not in stat:
                stat[key] = dict()

            stat[key][tool] = value

    report(dataset, stat, 'clang')
    report(dataset, stat, 'gcc')

def report(dataset, stat, comp):

    ck_cnt = 0
    suri = 0
    ddisasm = 0
    egalito = 0

    suri_all = 0
    stat = { k:v for (k,v) in stat.items() if comp in k.split('/')[2] }

    for key in sorted(stat.keys()):

        if stat[key]['suri']:
            suri_all += 1

        if len(stat[key]) != 2:
            continue

        ck_cnt += 1

        if stat[key]['suri']:
            suri += 1

        if dataset == 'setA':
            if stat[key]['ddisasm']:
                ddisasm += 1

        if dataset == 'setB':
            if stat[key]['egalito']:
                egalito += 1

    if dataset in ['setA']:
        print('%-15s (%-5s) : %10f%% (%4d/%4d) : %10f%% (%4d/%4d)'%(package, comp, suri/ck_cnt*100, suri, ck_cnt, ddisasm/ck_cnt*100, ddisasm, ck_cnt))
    if dataset in ['setB']:
        print('%-15s (%-5s) : %10f%% (%4d/%4d) : %10f%% (%4d/%4d)'%(package, comp, suri/ck_cnt*100, suri, ck_cnt, egalito/ck_cnt*100, egalito, ck_cnt))
    if dataset in ['setC']:
        print('%-15s (%-5s) : %10f%% (%4d/%4d)'%(package, comp, suri/ck_cnt*100, suri, ck_cnt))


    if suri_all == len(stat.keys()):
        print('\t\t\t[+] SURI passes all test suites (%d/%d)'%(suri_all, len(stat.keys())))




import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, help='dataset')
    parser.add_argument('--package', type=str, help='Package')
    parser.add_argument('--core', type=int, help='how many thread do you run', default=1)

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset'

    config_list = dict()
    if args.package:
        config_list = run(args.dataset, args.package, args.core)
    else:
        for package in ['spec_cpu2006', 'spec_cpu2017']:
            config_list[package] = run(args.dataset, package, args.core)


    if args.dataset == 'setA':
        print('%-15s %7s :   %21s :  %21s'%('', '', 'suri', 'ddiasm'))
    if args.dataset == 'setB':
        print('%-15s %7s :   %21s :  %21s'%('', '', 'suri', 'egalito'))
    if args.dataset == 'setC':
        print('%-15s %7s :   %21s'%('', '', 'suri (no ehframe)'))
    print('-----------------------------------------------------------------------------')
    for package in ['spec_cpu2006', 'spec_cpu2017']:
        summary(args.dataset, config_list[package])



import glob
import os
import multiprocessing
from filter_utils import check_exclude_files

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

def run(dataset, package):
    if package in ['spec_cpu2017']:
        run_script = 'run2017'
    elif package in ['spec_cpu2006']:
        run_script = 'run2006'

    if dataset in ['setA', 'setC']:
        image='suri_spec:v1.0'
    elif dataset in ['setB']:
        image='suri_ubuntu18.04_spec:v1.0'

    cur = os.getcwd()

    make_script(dataset, image, package, run_script, cur)


def get_docker_cmd(cur, folder, script_folder, log_folder, run_script, image, cpu_id):
    cmd = 'docker run --rm '
    cmd +=  '--memory 16g --cpus 1 '
    cmd +=  '--cpuset-cpus="%d" '%(cpu_id)
    cmd +=  '-v "%s/%s:/dataset/" '%(cur, folder)
    cmd +=  '-v "%s/%s:/script/" '%(cur, script_folder)
    cmd +=  '-v "%s/%s:/log/" '%(cur, log_folder)
    cmd +=  '%s '%(image)
    cmd +=  'sh -c "/bin/bash /script/%s" > %s/%s/log.txt 2>&1 '%(run_script, cur, log_folder)
    return cmd


def make_script(dataset, image, package, basename, cur):

    comp_set = ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']

    for comp in comp_set:
        for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
            for lopt in ['bfd', 'gold']:
                make_sub_script(dataset, image, package, basename, cur, lopt, comp, opt)

def make_sub_script(dataset, image, package, basename, cur, lopt, comp, opt):

    cpu_id = 0
    cmd_dict = dict()

    for folder in glob.glob('%s/%s/%s/%s_%s/*'%(dataset, package, comp, opt, lopt)):

        sub_folder = '/'.join(folder.split('/')[1:])

        script_folder = 'stat/suri_runtime/script/%s/%s'%(dataset, sub_folder)
        log_folder = 'stat/suri_runtime/%s/%s'%(dataset, sub_folder)
        os.system('mkdir -p %s'%(script_folder))
        os.system('mkdir -p %s'%(log_folder))
        for filepath in glob.glob(folder + '/*'):
            if filepath.split('/')[-2] not in ['original', 'suri']:
                continue

            filename = os.path.basename(filepath)

            if check_exclude_files(dataset, package, comp, opt, filename):
                continue

            run_script = basename + "_" + filename  + ".sh"
            with open('%s/%s'%(script_folder, run_script), 'w') as f:
                log_file = '%s/%s.txt'%(log_folder, filename)

                if os.path.exists(log_file):
                    continue

                if filename in bin_dict:
                    target = bin_dict[filename]
                else:
                    target = '.'.join(filename.split('.')[1:])

                print('cd /%s/'%(package), file=f)
                print('source shrc', file=f)
                print('ulimit -s unlimited', file=f)
                print('sleep 30', file=f)

                print('echo %s'%(filename), file=f)
                if package in ['spec_cpu2017']:
                    print('cp /dataset/%s /spec_cpu2017/benchspec/CPU/%s/exe/%s_base.case1_bfd.cfg-m64'%(filename, filename, target), file=f)
                    print('runcpu --action run --config case1_bfd.cfg --nobuild --iterations 3 --threads 1 %s > /log/%s.txt 2>&1'%(filename, filename), file=f)
                else:
                    print('cp /dataset/%s /spec_cpu2006/benchspec/CPU2006/%s/exe/%s_base.case1_bfd.cfg'%(filename, filename, target), file=f)
                    print('runspec --action run --config case1_bfd.cfg --nobuild --iterations 3 --threads 1 %s > /log/%s.txt 2>&1'%(filename, filename), file=f)

                if filename not in cmd_dict:
                    cmd_dict[filename] = []

                cmd = get_docker_cmd(cur, folder, script_folder, log_folder, run_script, image, cpu_id)
                cmd_dict[filename].append(cmd)

        cpu_id += 4

    for filename, cmd_list in cmd_dict.items():
        assert len(cmd_list) == 2, 'invalid cmd list %s %d'%(filename, len(cmd_list))

    for filename in sorted(cmd_dict.keys()):
        cmd_list = cmd_dict[filename]
        print('\n\n[%s]------------'%(filename), flush=True)
        p = multiprocessing.Pool(len(cmd_list))
        p.map(job, cmd_list)


def job(cmd):
    print(cmd, flush=True)
    os.system(cmd)


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA)')

    args = parser.parse_args()
    assert args.dataset in ['setA'], '"%s" is invalid. '%(args.dataset)

    for package in ['spec_cpu2017', 'spec_cpu2006']:
        run(args.dataset, package)


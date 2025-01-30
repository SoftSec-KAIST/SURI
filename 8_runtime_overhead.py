import glob
import os

white_list = [
'403.gcc',
]


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


def run_docker(cur, folder, script_folder, log_folder, run_script, image):
    print('docker run --rm ',
      '--memory 16g --cpus 1 ',
      '--cpuset-cpus="%d" '%(0),
      '-v "%s/%s:/dataset/" '%(cur, folder),
      '-v "%s/%s:/script/" '%(cur, script_folder),
      '-v "%s/%s:/log/" '%(cur, log_folder),
      '%s '%(image),
      'sh -c "/bin/bash /script/%s" > %s/%s/log.txt 2>&1 '%(run_script, cur, log_folder))

def make_script(dataset, image, package, basename, cur):

    for folder in glob.glob('%s/%s/gcc-11/o3_bfd*/*'%(dataset, package)):

        sub_folder = '/'.join(folder.split('/')[1:])

        script_folder = 'stat/runtime/script/%s/%s'%(dataset, sub_folder)
        log_folder = 'stat/runtime/overhead/%s/%s'%(dataset, sub_folder)
        os.system('mkdir -p %s'%(script_folder))
        os.system('mkdir -p %s'%(log_folder))

        for filepath in glob.glob(folder + '/*'):
            filename = os.path.basename(filepath)
            run_script = basename + "_" + filename  + ".sh"
            with open('%s/%s'%(script_folder, run_script), 'w') as f:
                log_file = '%s/%s.txt'%(log_folder, filename)

                if filename not in white_list:
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

                run_docker(cur, folder, script_folder, log_folder, run_script, image)


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')

    args = parser.parse_args()
    assert args.dataset in ['setA', 'setB', 'setC'], '"%s" is invalid. Please choose one from setA, setB, or setC.'%(args.dataset)

    for package in ['spec_cpu2017', 'spec_cpu2006']:
        run(args.dataset, package)

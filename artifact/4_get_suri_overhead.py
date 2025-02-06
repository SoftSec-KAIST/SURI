import glob
import os
import multiprocessing
from filter_utils import check_exclude_files
import argparse
from consts import *

BIN_NAME_MAP = {
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
    '999.specrand_ir': 'specrand_ir'
}

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA)')

    args = parser.parse_args()
    assert args.dataset in ['setA'], '"%s" is invalid. '%(args.dataset)

    return args

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                data_dir = os.path.join(args.dataset, package, comp, '%s_%s' % (opt, lopt))
                script_dir = os.path.join('stat', 'suri_runtime', 'script', args.dataset, package, comp, '%s_%s' % (opt, lopt))
                log_dir = os.path.join('stat', 'suri_runtime', args.dataset, package, comp, '%s_%s' % (opt, lopt))
                if os.path.exists(data_dir):
                    orig_dir = os.path.join(data_dir, 'original')
                    for target in glob.glob(orig_dir):
                        filename = os.path.basename(target)
                        tasks.append(ExpTask(args.dataset, comp, data_dir, script_dir, log_dir, filename))

    return tasks

def run_in_docker(cpu_id, data_dir, script_dir, log_dir, cmd):
    if data_dir[0] != '/':
        data_dir = os.path.join('.', data_dir)
    if script_dir[0] != '/':
        script_dir = os.path.join('.', script_dir)
    if log_dir[0] != '/':
        log_dir = os.path.join('.', log_dir)
    docker_cmd = 'docker run --memory 16g --cpus 1 --cpuset-cpus=%d --rm -v %s:/dataset -v %s:/script -v %s:/log %s sh -c "%s"' % (cpu_id, data_dir, script_dir, log_dir, image, cmd)
    print(docker_cmd)
    sys.stdout.flush()
    os.system(docker_cmd)

################################

def get_script_name(package):
    if package == 'spec_cpu2006':
        return 'run2006_%s.sh' % task.bin_name
    else:
        return 'run2017_%s.sh' % task.bin_name

def prepare_script(task, package, script_dir, script_name):
    script_path = os.path.join(script_dir, script_name)

    with open(script_path, 'w') as f:
        if task.bin_name in BIN_NAME_MAP:
            bin_name = BIN_NAME_MAP[task.bin_name]
        else:
            bin_name = task.bin_name.split('.', 1)[1]

        f.write('cd /%s/\n' % package)
        f.write('source shrc\n')
        f.write('ulimit -s unlimited\n')
        f.write('sleep 30\n')
        f.write('echo %s' % task.bin_name)

        if package == 'spec_cpu2006':
            f.write('cp /dataset/%s /spec_cpu2006/benchspec/CPU2006/%s/exe/%s_base.case1_bfd.cfg\n' % (task.bin_name, task.bin_name, bin_name))
            f.write('runspec --action run --config case1_bfd.cfg --nobuild --iterations 3 --threads 1 %s > /log/%s.txt 2>&1\n' % (task.bin_name, task.bin_name))
        elif package == 'spec_cpu2017':
            f.write('cp /dataset/%s /spec_cpu2017/benchspec/CPU/%s/exe/%s_base.case1_bfd.cfg-m64\n' % (task.bin_name, task.bin_name, bin_name))
            f.write('runcpu --action run --config case1_bfd.cfg --nobuild --iterations 3 --threads 1 %s > /log/%s.txt 2>&1\n' % (task.bin_name, task.bin_name))

def run_test_suite(cpu_id, task, package, script_name, tool_name):
    data_dir = os.path.join(task.data_dir, tool_name)
    script_dir = os.path.join(task.script_dir, tool_name)
    os.system('mkdir -p %s' % script_dir)
    prepare_script(task, package, script_dir, script_name)
    log_dir = os.path.join(task.log_dir, tool_name)
    os.system('mkdir -p %s' % log_dir)
    log_path = os.path.join(log_dir, 'log.txt')
    if os.path.exists(log_path):
        return

    cmd = '/bin/bash /script/%s > /log/log.txt 2>&1' % script_name

    run_in_docker(cpu_id, data_dir, script_dir, log_dir, cmd)

def run_parallel(arg):
    cpu_id, task, package, script_name, tool_name = arg
    run_test_suite(cpu_id, task, package, script_name, tool_name)

def run_task(task):
    script_name = get_script_name(package)
    print('\n\n[%s]------------' % task.bin_name, flush=True)

    args = [(0, task, package, script_name, 'original'),
            (4, task, package, script_name, 'suri')]
    p = multiprocessing.Pool(2)
    p.map(run_parallel, args)

def run_package(args, package):
    tasks = prepare_tasks(args, package)
    for task in tasks:
        run_task(task)

def run(args):
    for package in PACKAGES_SPEC:
        run_package(args, package)

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

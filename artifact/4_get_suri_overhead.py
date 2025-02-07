import argparse, glob, os, multiprocessing
from filter_utils import check_exclude_files
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'package', 'compiler', 'data_dir', 'script_dir', 'log_dir', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA)')
    args = parser.parse_args()

    # Sanitizing arguments
    assert args.dataset in ['setA'], '"%s" is invalid. '%(args.dataset)

    return args

################################

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                data_dir = os.path.join(args.dataset, package, comp, '%s_%s' % (opt, lopt))
                script_dir = os.path.join('stat', 'suri_runtime', 'script', args.dataset, package, comp, '%s_%s' % (opt, lopt))
                log_dir = os.path.join('stat', 'suri_runtime', args.dataset, package, comp, '%s_%s' % (opt, lopt))
                if os.path.exists(data_dir):
                    orig_dir = os.path.join(data_dir, 'original', '*')
                    for target in glob.glob(orig_dir):
                        filename = os.path.basename(target)
                        tasks.append(ExpTask(args.dataset, package, comp, data_dir, script_dir, log_dir, filename))

    return tasks

################################

def get_script_name(task):
    if task.package == 'spec_cpu2006':
        return 'run2006_%s.sh' % task.bin_name
    else:
        return 'run2017_%s.sh' % task.bin_name

def prepare_script(task, script_dir, script_name):
    script_path = os.path.join(script_dir, script_name)

    with open(script_path, 'w') as f:
        if task.bin_name in BIN_NAME_MAP:
            bin_name = BIN_NAME_MAP[task.bin_name]
        else:
            bin_name = task.bin_name.split('.', 1)[1]

        f.write('cd /%s/\n' % task.package)
        f.write('source shrc\n')
        f.write('ulimit -s unlimited\n')
        f.write('sleep 30\n')
        f.write('echo %s' % task.bin_name)

        if task.package == 'spec_cpu2006':
            f.write('cp /dataset/%s /spec_cpu2006/benchspec/CPU2006/%s/exe/%s_base.case1_bfd.cfg\n' % (task.bin_name, task.bin_name, bin_name))
            f.write('runspec --action run --config case1_bfd.cfg --nobuild --iterations 3 --threads 1 %s > /log/%s.txt 2>&1\n' % (task.bin_name, task.bin_name))
        elif task.package == 'spec_cpu2017':
            f.write('cp /dataset/%s /spec_cpu2017/benchspec/CPU/%s/exe/%s_base.case1_bfd.cfg-m64\n' % (task.bin_name, task.bin_name, bin_name))
            f.write('runcpu --action run --config case1_bfd.cfg --nobuild --iterations 3 --threads 1 %s > /log/%s.txt 2>&1\n' % (task.bin_name, task.bin_name))

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

def run_test_suite(cpu_id, task, script_name, tool_name):
    data_dir = os.path.join(task.data_dir, tool_name)
    script_dir = os.path.join(task.script_dir, tool_name)
    os.system('mkdir -p %s' % script_dir)
    prepare_script(task, script_dir, script_name)
    log_dir = os.path.join(task.log_dir, tool_name)
    os.system('mkdir -p %s' % log_dir)
    log_path = os.path.join(log_dir, '%s.txt' % task.bin_name)
    if os.path.exists(log_path):
        return

    cmd = '/bin/bash /script/%s > /log/log.txt 2>&1' % script_name

    run_in_docker(cpu_id, data_dir, script_dir, log_dir, cmd)

def run_parallel(arg):
    cpu_id, task, script_name, tool_name = arg
    run_test_suite(cpu_id, task, script_name, tool_name)

def run_task(task):
    script_name = get_script_name(task)
    print('\n\n[%s]------------' % task.bin_name, flush=True)

    args = [(0, task, script_name, 'original'),
            (4, task, script_name, 'suri')]
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

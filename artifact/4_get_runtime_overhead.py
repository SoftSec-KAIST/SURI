import glob
import os
import argparse
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'compiler', 'data_dir', 'script_dir', 'log_dir', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setC'], 'Invalid dataset'

    return args

def prepare_tasks(args, package):
    comp = 'gcc-11'
    opt = 'o3'
    lopt = 'bfd'

    tasks = []
    data_dir = os.path.join(args.dataset, package, comp, '%s_%s' % (opt, lopt))
    script_dir = os.path.join('stat', 'runtime', 'script', args.dataset, package, comp, '%s_%s' % (opt, lopt))
    log_dir = os.path.join('stat', 'runtime', args.dataset, package, comp, '%s_%s' % (opt, lopt))
    if os.path.exists(data_dir):
        orig_dir = os.path.join(data_dir, 'original')
        for target in glob.glob(orig_dir):
            filename = os.path.basename(target)
            tasks.append(ExpTask(args.dataset, comp, data_dir, script_dir, log_dir, filename))

    return tasks

def print_cmd_in_docker(image, data_dir, script_dir, log_dir, cmd):
    if data_dir[0] != '/':
        data_dir = os.path.join('.', data_dir)
    if script_dir[0] != '/':
        script_dir = os.path.join('.', script_dir)
    if log_dir[0] != '/':
        log_dir = os.path.join('.', log_dir)
    docker_cmd = 'docker run --memory 16g --cpus 1 --cpuset-cpus=0 --rm -v %s:/dataset -v %s:/script -v %s:/log %s sh -c "%s"' % (data_dir, script_dir, log_dir, image, cmd)
    print(docker_cmd)

################################

def get_docker_image(dataset):
    if dataset in ['setA', 'setC']:
        return 'suri_spec:v1.0'
    else:
        return 'suri_ubuntu18.04_spec:v1.0'

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

def run_test_suite(task, package, image, script_name, tool_name):
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

    print_cmd_in_docker(image, data_dir, script_dir, log_dir, cmd)

def run_task(task):
    image = get_docker_image(task.dataset)
    script_name = get_script_name(package)

    if task.dataset == 'setA':
        if task.bin_name in RUNTIME_TARGET_LIST:
            run_test_suite(task, package, image, script_name, 'original')
            run_test_suite(task, package, image, script_name, 'suri')
            run_test_suite(task, package, image, script_name, 'ddisasm')
        else:
            run_test_suite(task, package, image, script_name, 'original')
            run_test_suite(task, package, image, script_name, 'suri')
    elif task.dataset == 'setB':
        if task.bin_name in RUNTIME_TARGET_LIST:
            run_test_suite(task, package, image, script_name, 'original')
            run_test_suite(task, package, image, script_name, 'suri')
            run_test_suite(task, package, image, script_name, 'egalito')
    else:
        run_test_suite(task, package, image, script_name, 'original')
        run_test_suite(task, package, image, script_name, 'suri')

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

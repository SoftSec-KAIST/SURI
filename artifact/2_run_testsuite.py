from collections import namedtuple
import glob, os, sys
import multiprocessing
import enum
from ctypes import *
import argparse
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'compiler', 'data_dir', 'log_dir'])

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    args = parser.parse_args()

    # Sanitizing arguments
    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

################################

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                data_dir = os.path.join(args.dataset, package, comp, '%s_%s' % (opt, lopt))
                log_dir = os.path.join('log', args.dataset, package, comp, '%s_%s' % (opt, lopt))
                if os.path.exists(data_dir):
                    tasks.append(ExpTask(args.dataset, comp, data_dir, log_dir))

    return tasks

def run_in_docker(image, data_dir, log_dir, cmd):
    if data_dir[0] != '/':
        data_dir = os.path.join('.', data_dir)
    if log_dir[0] != '/':
        log_dir = os.path.join('.', log_dir)
    docker_cmd = 'docker run --rm -v %s:/dataset -v %s:/log %s sh -c "%s"' % (data_dir, log_dir, image, cmd)
    print(docker_cmd)
    sys.stdout.flush()
    os.system(docker_cmd)

################################

def get_docker_image(dataset):
    if dataset in ['setA', 'setC']:
        return 'suri_artifact:v1.0'
    else:
        return 'suri_artifact_ubuntu18.04:v1.0'

def run_test_suite(task, package, image, tool_name):
    data_dir = os.path.join(task.data_dir, tool_name)
    log_dir = os.path.join(task.log_dir, tool_name)
    os.system('mkdir -p %s' % log_dir)
    log_path = os.path.join(log_dir, 'log2.txt')
    if os.path.exists(log_path):
        return

    cmd1 = 'cd %s' % package
    cmd2 = '/bin/bash copy.sh > /log/log1.txt 2>&1'
    cmd3 = 'make check -j 8 > /log/log2.txt 2>&1'
    cmd = ';'.join([cmd1, cmd2, cmd3])

    run_in_docker(image, data_dir, log_dir, cmd)

def run_task(task):
    image = get_docker_image(task.dataset)

    run_test_suite(task, package, image, 'original')
    run_test_suite(task, package, image, 'suri')

    if task.dataset == 'setA':
        run_test_suite(task, package, image, 'ddisasm')
    elif task.dataset == 'setB':
        run_test_suite(task, package, image, 'egalito')

def run(args, tasks, package):
    p = multiprocessing.Pool(args.core)
    p.map(run_task, tasks)

################################

def read_test_data(package, filepath):
    with open(filepath) as f:
        lines = f.read().split('\n')
        if package == 'coreutils-9.1':
            value = set([line for line in lines if '# FAIL:' in line])
        else:
            value = set([line for line in lines if '# of expected passes' in line])
    return len(value)

def get_data_original(task, package):
    filepath = os.path.join(task.log_dir, 'original', 'log2.txt')
    return read_test_data(package, filepath)

def get_data_suri(task, package):
    filepath = os.path.join(task.log_dir, 'suri', 'log2.txt')
    return read_test_data(package, filepath)

def get_data_ddisasm(task, package):
    filepath = os.path.join(task.log_dir, 'ddisasm', 'log2.txt')
    return read_test_data(package, filepath)

def get_data_egalito(task, package):
    filepath = os.path.join(task.log_dir, 'egalito', 'log2.txt')
    return read_test_data(package, filepath)

def summary(args, tasks, package):
    data = {}
    for task in tasks:
        t_orig = get_data_original(task, package)
        t_suri = get_data_suri(task, package)
        if task.dataset == 'setA':
            t_target = get_data_ddisasm(task, package)
            if task.compiler not in data:
                data[task.compiler] = 0, 0, 0
            num_tests, suri_succ, target_succ = data[task.compiler]
            num_tests += 1
            if t_orig == t_suri:
                suri_succ += 1
            if t_orig == t_target:
                target_succ += 1
            data[task.compiler] = num_tests, suri_succ, target_succ
        elif task.dataset == 'setB':
            t_target = get_data_egalito(task, package)
            if task.compiler not in data:
                data[task.compiler] = 0, 0, 0
            num_tests, suri_succ, target_succ = data[task.compiler]
            num_tests += 1
            if t_orig == t_suri:
                suri_succ += 1
            if t_orig == t_target:
                target_succ += 1
            data[task.compiler] = num_tests, suri_succ, target_succ
        else:
            if task.compiler not in data:
                data[task.compiler] = 0, 0
            num_tests, suri_succ = data[task.compiler]
            num_tests += 1
            if t_orig == t_suri:
                suri_succ += 1
            data[task.compiler] = num_tests, suri_succ

    for compiler in data:
        if args.dataset in ['setA', 'setB']:
            num_tests, suri_succ, target_succ = data[compiler]
            if num_tests == suri_succ:
                suri_res = 'Succ'
            else:
                suri_res = 'Fail'
            if num_tests == target_succ:
                target_res = 'Succ'
            else:
                target_res = 'Fail'
            print(FMT_TESTSUITE_UTILS_INDIVIDUAL_AB % (package, compiler, suri_res, suri_succ, num_tests, target_res, target_succ, num_tests))
        else:
            num_tests, suri_succ = data[compiler]
            if num_tests == suri_succ:
                suri_res = 'Succ'
            else:
                suri_res = 'Fail'
            print(FMT_TESTSUITE_UTILS_INDIVIDUAL_C % (package, compiler, suri_res, suri_succ, num_tests))

def print_header(dataset):
    if dataset == 'setA':
        print(FMT_TESTSUITE_UTILS_HEADER_AB % ('', '', 'suri', 'Ddiasm'))
    elif dataset == 'setB':
        print(FMT_TESTSUITE_UTILS_HEADER_AB % ('', '', 'suri', 'Egalito'))
    elif dataset == 'setC':
        print(FMT_TESTSUITE_UTILS_HEADER_C % ('', '', 'suri(no_ehframe)'))

if __name__ == '__main__':
    args = parse_arguments()

    for package in PACKAGES_UTILS:
        tasks = prepare_tasks(args, package)
        run(args, tasks, package)

    print_header(args.dataset)
    print(FMT_LINE)
    for package in PACKAGES_UTILS:
        tasks = prepare_tasks(args, package)
        summary(args, tasks, package)

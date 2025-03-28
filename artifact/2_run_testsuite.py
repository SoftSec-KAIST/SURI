import argparse, multiprocessing, os, sys
from collections import namedtuple
from ctypes import *
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'package', 'compiler', 'data_dir', 'log_dir'])

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
                    tasks.append(ExpTask(args.dataset, package, comp, data_dir, log_dir))

    return tasks

################################

def get_docker_image(dataset):
    if dataset in ['setA', 'setC']:
        return 'suri_artifact:v1.0'
    else:
        return 'suri_artifact_ubuntu18.04:v1.0'

def run_in_docker(image, data_dir, log_dir, cmd):
    if data_dir[0] != '/':
        data_dir = os.path.join('.', data_dir)
    if log_dir[0] != '/':
        log_dir = os.path.join('.', log_dir)
    docker_cmd = 'docker run --rm -v %s:/dataset -v %s:/log %s sh -c "%s"' % (data_dir, log_dir, image, cmd)
    print(docker_cmd)
    sys.stdout.flush()
    os.system(docker_cmd)

def run_test_suite(task, image, tool_name):
    data_dir = os.path.join(task.data_dir, tool_name)
    log_dir = os.path.join(task.log_dir, tool_name)
    os.system('mkdir -p %s' % log_dir)
    log_path = os.path.join(log_dir, 'log2.txt')
    if os.path.exists(log_path):
        return

    cmd1 = 'cd %s' % task.package
    cmd2 = '/bin/bash copy.sh > /log/log1.txt 2>&1'
    cmd3 = 'make check -j 8 > /log/log2.txt 2>&1'
    cmd = ';'.join([cmd1, cmd2, cmd3])

    run_in_docker(image, data_dir, log_dir, cmd)

def run_task(task):
    image = get_docker_image(task.dataset)

    run_test_suite(task, image, 'original')
    run_test_suite(task, image, 'suri')

    if task.dataset == 'setA':
        run_test_suite(task, image, 'ddisasm')
    elif task.dataset == 'setB':
        run_test_suite(task, image, 'egalito')

def run_package(args, package):
    tasks = prepare_tasks(args, package)
    p = multiprocessing.Pool(args.core)
    p.map(run_task, tasks)

def run(args):
    for package in PACKAGES_UTILS:
        run_package(args, package)

################################

def read_test_data(package, filepath):
    with open(filepath) as f:
        lines = f.read().split('\n')
        if package == 'coreutils-9.1':
            value = set([line for line in lines if '# FAIL:' in line])
        else:
            value = set([line for line in lines if '# of expected passes' in line])
    return len(value)

def get_data(task, tool_name):
    filepath = os.path.join(task.log_dir, tool_name, 'log2.txt')
    return read_test_data(task.package, filepath)

def collect_setA(args):
    data = {}
    for package in PACKAGES_UTILS:
        tasks = prepare_tasks(args, package)
        for task in tasks:
            if package not in data:
                data[package] = {}
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0, 0

            tests_orig = get_data(task, 'original')
            tests_suri = get_data(task, 'suri')
            tests_target = get_data(task, 'ddisasm') # Comparison target is Ddisasm
            num_tests, suri_succ, target_succ = 0, 0, 0
            num_tests += 1
            if tests_orig == tests_suri:
                suri_succ += 1
            if tests_orig == tests_target:
                target_succ += 1
            data[package][task.compiler] = num_tests, suri_succ, target_succ

    return data

def collect_setB(args):
    data = {}
    for package in PACKAGES_UTILS:
        tasks = prepare_tasks(args, package)
        for task in tasks:
            if package not in data:
                data[package] = {}
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0, 0

            tests_orig = get_data(task, 'original')
            tests_suri = get_data(task, 'suri')
            tests_target = get_data(task, 'egalito') # Comparison target is Egalito
            num_tests, suri_succ, target_succ = 0, 0, 0
            num_tests += 1
            if tests_orig == tests_suri:
                suri_succ += 1
            if tests_orig == tests_target:
                target_succ += 1
            data[package][task.compiler] = num_tests, suri_succ, target_succ

    return data

def collect_setC(args):
    data = {}
    for package in PACKAGES_UTILS:
        tasks = prepare_tasks(args, package)
        for task in tasks:
            if package not in data:
                data[package] = {}
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0

            tests_orig = get_data(task, 'original')
            tests_suri = get_data(task, 'suri') # No comparison targets in this case.
            num_tests, suri_succ = 0, 0
            num_tests += 1
            if tests_orig == tests_suri:
                suri_succ += 1
            data[package][task.compiler] = num_tests, suri_succ

    return data

def collect(args):
    if args.dataset == 'setA':
        return collect_setA(args)
    elif args.dataset == 'setB':
        return collect_setB(args)
    else:
        return collect_setC(args)

################################

def print_header(dataset):
    if dataset == 'setA':
        print(FMT_TESTSUITE_UTILS_HEADER_AB % ('', '', 'suri', 'Ddiasm'))
    elif dataset == 'setB':
        print(FMT_TESTSUITE_UTILS_HEADER_AB % ('', '', 'suri', 'Egalito'))
    elif dataset == 'setC':
        print(FMT_TESTSUITE_UTILS_HEADER_C % ('', '', 'suri(no_ehframe)'))

def report_setAB(data):
    for package in PACKAGES_UTILS:
        if package not in data:
            continue

        for compiler in COMPILERS:
            if compiler not in data[package]:
                continue

            comp_name = compiler.split('-')[0]
            num_tests, suri_succ, target_succ = data[package][compiler]
            if num_tests == suri_succ:
                suri_res = 'Succ'
            else:
                suri_res = 'Fail'
            if num_tests == target_succ:
                target_res = 'Succ'
            else:
                target_res = 'Fail'
            print(FMT_TESTSUITE_UTILS_INDIVIDUAL_AB % (package, comp_name,
                                                       suri_res, suri_succ, num_tests,
                                                       target_res, target_succ, num_tests))

def report_setC(data):
    for package in PACKAGES_UTILS:
        if package not in data:
            continue

        for compiler in COMPILERS:
            if compiler not in data[package]:
                continue

            comp_name = compiler.split('-')[0]
            num_tests, suri_succ = data[package][compiler]
            if num_tests == suri_succ:
                suri_res = 'Succ'
            else:
                suri_res = 'Fail'
            print(FMT_TESTSUITE_UTILS_INDIVIDUAL_C % (package, comp_name,
                                                      suri_res, suri_succ, num_tests))

# Report the percentage of average success rates of test suites for Table 2 and
# Table 3 of our paper.
def report(args, data):
    print_header(args.dataset)

    if args.dataset == 'setA' or args.dataset == 'setB':
        report_setAB(data)
    else:
        report_setC(data)

if __name__ == '__main__':
    args = parse_arguments()
    run(args)
    data = collect(args)
    report(args, data)

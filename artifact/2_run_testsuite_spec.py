import argparse, glob, multiprocessing, os, sys
from collections import namedtuple
from consts import *

ExpTask = namedtuple('ExpTask', ['dataset', 'package', 'compiler', 'data_dir', 'script_dir', 'log_dir', 'bin_name'])

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--package', type=str, help='Select package (spec_cpu2017, spec_cpu2006)')
    parser.add_argument('--core', type=int, help='how many thread do you run', default=1)
    args = parser.parse_args()

    # Sanitizing arguments
    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset'
    if args.package:
        assert args.package in PACKAGES_SPEC, 'Invalid package: "%s"'%(args.package)

    return args

################################

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                data_dir = os.path.join(args.dataset, package, comp, '%s_%s' % (opt, lopt))
                script_dir = os.path.join('script', args.dataset, package, comp, '%s_%s' % (opt, lopt))
                log_dir = os.path.join('log', args.dataset, package, comp, '%s_%s' % (opt, lopt))
                if os.path.exists(data_dir):
                    orig_dir = os.path.join(data_dir, 'original/*')
                    for target in glob.glob(orig_dir):
                        filename = os.path.basename(target)

                        # Filter files
                        if package == 'spec_cpu2006':
                            if filename == '416.gamess' and opt != 'o0':
                                continue
                            elif filename == '453.povray' and opt == 'ofast' and comp == 'gcc-13':
                                continue
                        elif package == 'spec_cpu2017':
                            if filename == '511.povray_r' and opt == 'ofast' and comp == 'gcc-13':
                                continue

                        tasks.append(ExpTask(args.dataset, package, comp, data_dir, script_dir, log_dir, filename))

    return tasks

################################

def get_docker_image(dataset):
    if dataset in ['setA', 'setC']:
        return 'suri_spec:v1.0'
    else:
        return 'suri_ubuntu18.04_spec:v1.0'

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
        f.write('sleep 10\n')
        f.write('echo %s' % task.bin_name)

        if task.package == 'spec_cpu2006':
            f.write('cp /dataset/%s /spec_cpu2006/benchspec/CPU2006/%s/exe/%s_base.case1_bfd.cfg\n' % (task.bin_name, task.bin_name, bin_name))
            f.write('runspec --action run --config case1_bfd.cfg --nobuild --iterations 1 --threads 4 %s > /log/%s.txt 2>&1\n' % (task.bin_name, task.bin_name))
        elif task.package == 'spec_cpu2017':
            f.write('cp /dataset/%s /spec_cpu2017/benchspec/CPU/%s/exe/%s_base.case1_bfd.cfg-m64\n' % (task.bin_name, task.bin_name, bin_name))
            f.write('runcpu --action run --config case1_bfd.cfg --nobuild --iterations 1 --threads 4 %s > /log/%s.txt 2>&1\n' % (task.bin_name, task.bin_name))

def run_in_docker(image, data_dir, script_dir, log_dir, cmd):
    if data_dir[0] != '/':
        data_dir = os.path.join('.', data_dir)
    if script_dir[0] != '/':
        script_dir = os.path.join('.', script_dir)
    if log_dir[0] != '/':
        log_dir = os.path.join('.', log_dir)
    docker_cmd = 'docker run --memory 16g --cpus 4 --rm -v %s:/dataset -v %s:/script -v %s:/log %s sh -c "%s"' % (data_dir, script_dir, log_dir, image, cmd)
    print(docker_cmd)
    sys.stdout.flush()
    os.system(docker_cmd)

def run_test_suite(task, image, script_name, tool_name):
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

    run_in_docker(image, data_dir, script_dir, log_dir, cmd)

def run_task(task):
    image = get_docker_image(task.dataset)
    script_name = get_script_name(task)

    run_test_suite(task, image, script_name, 'suri')

    if task.dataset == 'setA':
        run_test_suite(task, image, script_name, 'ddisasm')
    elif task.dataset == 'setB':
        run_test_suite(task, image, script_name, 'egalito')

def run_package(args, package):
    tasks = prepare_tasks(args, package)
    p = multiprocessing.Pool(args.core)
    p.map(run_task, tasks)

def run(args):
    if args.package:
        run_package(args, args.package)
    else:
        for package in PACKAGES_SPEC:
            run_package(args, package)

################################

def read_test_data(filepath):
    with open(filepath) as f:
        try:
            data = f.read()
            if 'Success:' in data:
                value = True
            else:
                value = False
        except UnicodeDecodeError:
            value = False
    return value

def get_data(task, tool_name):
    filepath = os.path.join(task.log_dir, tool_name, '%s.txt' % task.bin_name)
    return read_test_data(filepath)

def collect_setA(args):
    data = {}
    for package in PACKAGES_SPEC:
        tasks = prepare_tasks(args, package)
        for task in tasks:
            if package not in data:
                data[package] = {}
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0, 0

            tests_suri = get_data(task, 'suri')
            tests_target = get_data(task, 'ddisasm') # Comparison target is Ddisasm
            num_tests, suri_succ, target_succ = 0, 0, 0
            num_tests += 1
            if tests_suri:
                suri_succ += 1
            if tests_target:
                target_succ += 1
            data[package][task.compiler] = num_tests, suri_succ, target_succ

    return data

def collect_setB(args):
    data = {}
    for package in PACKAGES_SPEC:
        tasks = prepare_tasks(args, package)
        for task in tasks:
            if package not in data:
                data[package] = {}
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0, 0

            tests_suri = get_data(task, 'suri')
            tests_target = get_data(task, 'egalito') # Comparison target is Egalito
            num_tests, suri_succ, target_succ = 0, 0, 0
            num_tests += 1
            if tests_suri:
                suri_succ += 1
            if tests_target:
                target_succ += 1
            data[package][task.compiler] = num_tests, suri_succ, target_succ

    return data

def collect_setC(args):
    data = {}
    for package in PACKAGES_SPEC:
        tasks = prepare_tasks(args, package)
        for task in tasks:
            if package not in data:
                data[package] = {}
            if task.compiler not in data[package]:
                data[package][task.compiler] = 0, 0

            tests_suri = get_data(task, 'suri') # No comparison targets in this case.
            num_tests, suri_succ = 0, 0
            num_tests += 1
            if tests_suri:
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
    if dataset == 'setA' or dataset == 'setB':
        print(FMT_TESTSUITE_SPEC_HEADER_AB % ('', '', 'suri', 'ddiasm'))
        print(FMT_TESTSUITE_SPEC_LINE_AB)
    else:
        print(FMT_TESTSUITE_SPEC_HEADER_C % ('', '', 'suri (no ehframe)'))
        print(FMT_TESTSUITE_SPEC_LINE_C)

def report_setAB(data):
    for package in PACKAGES_SPEC:
        if package not in data:
            continue

        total_num_tests = 0
        total_suri_succ = 0
        for compiler in COMPILERS:
            if compiler not in data[package]:
                continue

            comp_name = compiler.split('-')[0]
            num_tests, suri_succ, target_succ = data[package][compiler]
            avg_suri_succ = suri_succ / num_tests * 100
            avg_target_succ = target_succ / num_tests * 100
            print(FMT_TESTSUITE_SPEC_INDIVIDUAL_AB % (package, comp_name,
                                                      avg_suri_succ, suri_succ, num_tests,
                                                      avg_target_succ, target_succ, num_tests))

            total_num_tests += num_tests
            total_suri_succ += suri_succ

        if total_num_tests == total_suri_succ:
            print('\t\t\t[+] SURI passes all test suites (%d/%d)' % (total_suri_succ, total_num_tests))

def report_setC(data):
    for package in PACKAGES_SPEC:
        if package not in data:
            continue

        total_num_tests = 0
        total_suri_succ = 0
        for compiler in COMPILERS:
            if compiler not in data[package]:
                continue

            comp_name = compiler.split('-')[0]
            num_tests, suri_succ = data[package][compiler]
            avg_suri_succ = suri_succ / num_tests * 100
            print(FMT_TESTSUITE_SPEC_INDIVIDUAL_C % (package, comp_name,
                                                     avg_suri_succ, suri_succ, num_tests))

            total_num_tests += num_tests
            total_suri_succ += suri_succ

        if total_num_tests == total_suri_succ:
            print('\t\t\t[+] SURI passes all test suites (%d/%d)' % (total_suri_succ, total_num_tests))

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

from collections import namedtuple
import glob, os, sys
import multiprocessing
from filter_utils import check_exclude_files
import argparse
import subprocess

ExpTask = namedtuple('ExpTask', ['dataset', 'input_dir', 'output_dir', 'bin_name'])

PACKAGES = ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006']
COMPILERS = ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']
OPTIMIZATIONS = ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']
LINKERS = ['bfd', 'gold']

def parse_arguments():
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--package', type=str, help='Select package (coreutils-9.1, binutils-2.40, spec_cpu2017, spec_cpu2006)')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)
    if args.package:
        assert args.package in PACKAGES, 'Invalid package: "%s"'%(args.package)

    return args

def prepare_tasks(args, package):
    tasks = []
    for comp in COMPILERS:
        for opt in OPTIMIZATIONS:
            for lopt in LINKERS:
                input_base = os.path.join(args.input_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                output_base = os.path.join(args.output_dir, args.dataset, package, comp, '%s_%s' % (opt, lopt))
                strip_dir = os.path.join(input_base, 'stripbin', '*')

                for target in glob.glob(strip_dir):
                    filename = os.path.basename(target)

                    # Filter binaries
                    if args.blacklist and filename in args.blacklist:
                        continue
                    if args.whitelist and filename not in args.whitelist:
                        continue
                    if check_exclude_files(args.dataset, package, comp, opt, filename):
                        continue

                    bin_dir = os.path.join(input_base, 'stripbin')
                    out_dir = os.path.join(output_base, filename)
                    tasks.append(ExpTask(args.dataset, bin_dir, out_dir, filename))

    return tasks

def run_in_docker(image, in_dir, out_dir, log_name, cmd):
    time_cmd = '/usr/bin/time -f\'%%E %%U %%S\' -o /output/%s %s' % (log_name, cmd)
    docker_cmd = 'docker run --rm --memory 64g --cpus 1 -v %s:/input -v %s:/output %s sh -c "%s"' % (in_dir, out_dir, image, time_cmd)
    print(docker_cmd)
    sys.stdout.flush()
    os.system(docker_cmd)

################################

def reassem_suri(task, in_dir, out_dir):
    if task.dataset in ['setA', 'setC']:
        image = 'suri_artifact:v1.0'
    elif task.dataset in ['setB']:
        image = 'suri_artifact_ubuntu18.04:v1.0'

    cmd = 'python3 /project/SURI/suri.py /input/%s --ofolder /output/ --meta b2r2_meta >> /output/log.txt' % task.bin_name
    run_in_docker(image, in_dir, out_dir, 'tlog1.txt', cmd)

def has_result_suri(res_path):
    return os.path.exists(res_path)

def run_suri(task):
    in_dir = task.input_dir
    out_dir = os.path.join(task.output_dir, 'super')
    os.system('mkdir -p %s' % out_dir)

    res_path = os.path.join(out_dir, 'my_%s' % task.bin_name)
    if not has_result_suri(res_path):
        reassem_suri(task, in_dir, out_dir)

################################

def reassem_ddisasm(task, in_dir, out_dir):
    cmd = 'ddisasm /input/%s --asm /output/ddisasm.s > /output/log.txt' % task.bin_name
    run_in_docker('reassessor/ddisasm:1.7.0_time', in_dir, out_dir, 'tlog.txt', cmd)

def get_options(bin_path):
    result = subprocess.run(['ldd', bin_path], stdout=subprocess.PIPE)
    lines = result.stdout.decode('utf-8').split('\n')
    lopt_list = []
    for opt in lines:
        if "=> " in opt:
            lopt_list.append(opt.split()[2])
        elif 'linux-vdso.so' in opt:
           continue
        elif opt.split():
            lopt_list.append(opt.split()[0])

    compiler = '/usr/bin/gcc-11'
    lopt = ''
    for opt in lopt_list[:]:
        #if opt in ['-lstdc++']:
        if opt.startswith('libstdc++.so'):
            compiler = '/usr/bin/g++-11'
        #elif opt in ['-lgfortran']:
        elif opt.startswith('libgfortran.so'):
            compiler = '/usr/bin/gfortran-11'
        #elif opt in ['-lc']:
        elif opt.startswith('libc.so'):
            continue
        lopt += opt + ' '
    lopt += ' -fcf-protection=full -pie -fPIE'
    lopt += ' -Wl,-z,lazy'

    return compiler, lopt

def compile_ddisasm(task, in_dir, out_dir):
    bin_path = os.path.join(in_dir, task.bin_name)
    comp, lopt = get_options(bin_path)

    cmd = '%s /output/ddisasm.s %s -nostartfiles -o /output/%s' % (comp, lopt, task.bin_name)
    run_in_docker('suri_artifact:v1.0', in_dir, out_dir, 'tlog2.txt', cmd)

def has_reasm_result_ddisasm(asm_path):
    return os.path.exists(asm_path) and os.stat(asm_path).st_size > 0

def has_result_ddisasm(res_path):
    return os.path.exists(res_path)

def run_ddisasm(task):
    in_dir = task.input_dir
    out_dir = os.path.join(task.output_dir, 'ddisasm')
    os.system('mkdir -p %s' % out_dir)

    asm_path = os.path.join(out_dir, 'ddisasm.s')
    if not has_reasm_result_ddisasm(asm_path):
        reassem_ddisasm(task, in_dir, out_dir)

    res_path = os.path.join(out_dir, task.bin_name)
    if not has_result_ddisasm(res_path):
        compile_ddisasm(task, in_dir, out_dir)

################################

def reassem_egalito(task, in_dir, out_dir):
    cmd = '/project/egalito/app/etelf -m /input/%s /output/%s > /output/log.txt 2>&1' % (task.bin_name, task.bin_name)
    run_in_docker('suri_artifact_ubuntu18.04:v1.0', in_dir, out_dir, 'tlogx.txt', cmd)

def has_result_egalito(res_path):
    return os.path.exists(res_path) and os.stat(res_path).st_size > 0

def run_egalito(task):
    in_dir = task.input_dir
    out_dir = os.path.join(task.output_dir, 'egalito')
    os.system('mkdir -p %s' % out_dir)

    res_path = os.path.join(out_dir, task.bin_name)
    if not has_result_egalito(res_path):
        reassem_egalito(task, in_dir, out_dir)

################################

# setA: SURI vs. Ddisasm
# setB: SURI vs. Egalito
# setC: SURI
def run_task(task):
    run_suri(task)

    if task.dataset == 'setA':
        run_ddisasm(task)
    elif task.dataset == 'setB':
        run_egalito(task)

def run_package(args, package):
    tasks = prepare_tasks(args, package)
    p = multiprocessing.Pool(args.core)
    p.map(run_task, tasks)

def run(args):
    if args.package:
        run_package(args, args.package)
    else:
        for package in PACKAGES:
            run_package(args, package)

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

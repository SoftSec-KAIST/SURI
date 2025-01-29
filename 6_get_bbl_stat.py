from collections import namedtuple
import glob, os, sys
import multiprocessing

BuildConf = namedtuple('BuildConf', ['target', 'input_root', 'sub_dir', 'reassem_path', 'output_path', 'arch', 'pie', 'package', 'bin'])

def gen_option(input_root, reassem_root, output_root, package, blacklist, whitelist):
    ret = []
    cnt = 0
    for arch in ['x64']:
        for comp in ['clang-13', 'gcc-11']:
            for popt in ['pie']:
                for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
                    for lopt in ['bfd', 'gold']:
                        sub_dir = '%s/%s/%s_%s'%(package, comp, opt, lopt)
                        input_dir = '%s/%s'%(input_root, sub_dir)
                        for target in glob.glob('%s/bin/*'%(input_dir)):

                            filename = os.path.basename(target)
                            binpath = '%s/bin/%s'%(input_dir, filename)

                            if filename in ['416.gamess'] and opt not in ['o0']:
                                continue

                            reassem_dir = '%s/%s/%s'%(reassem_root, sub_dir, filename)
                            out_dir = '%s/%s/%s'%(output_root, sub_dir, filename)

                            if blacklist and filename in blacklist:
                                continue
                            if whitelist and filename not in whitelist:
                                continue

                            ret.append(BuildConf(target, input_root, sub_dir, reassem_dir, output_root, arch, popt, package, binpath))

                            cnt += 1
    return ret

def job(conf, reset=False):
    filename = os.path.basename(conf.bin)
    b2r2_func_path = '%s/super/b2r2_meta.json'%(conf.reassem_path)
    filename = os.path.basename(conf.bin)

    output_file = '%s/%s'%(conf.output_path, conf.sub_dir.replace('/','_')) + '_' + filename

    if not os.path.exists(conf.output_path):
        os.system('mkdir -p %s'%(conf.output_path))

    if os.path.exists(output_file):
        return

    print('python3 bbl_stat.py %s %s %s'%(conf.bin, b2r2_func_path, output_file))
    os.system('python3 bbl_stat.py %s %s %s'%(conf.bin, b2r2_func_path, output_file))


def run(input_root, reassem_root, dataset, package, core=1, blacklist=None, whitelist=None):
    if package not in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006']:
        return False
    output_root = 'stat/bbl/%s'%(dataset)

    config_list = gen_option(input_root, reassem_root, output_root, package, blacklist, whitelist)

    if core and core > 1:
        p = multiprocessing.Pool(core)
        p.map(job, [(conf) for conf in config_list])
    else:
        for conf in config_list:
            job(conf)


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--package', type=str, help='Package')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--target', type=str)
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')

    args = parser.parse_args()
    assert args.dataset in ['setA', 'setC'], '"%s" is invalid. Please choose one from setA or setC.'%(args.dataset)

    input_dir = '%s/%s'%(args.input_dir, args.dataset)
    output_dir = '%s/%s'%(args.output_dir, args.dataset)

    if args.package:
        run(input_dir, output_dir, args.dataset, args.package, args.core, args.blacklist, args.whitelist)
    else:
        for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']:
            run(input_dir, output_dir, args.dataset, package, args.core, args.blacklist, args.whitelist)

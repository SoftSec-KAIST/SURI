from collections import namedtuple
import glob, os, sys
import multiprocessing

BuildConf = namedtuple('BuildConf', ['target', 'input_root', 'sub_dir', 'output_path', 'arch', 'comp', 'pie', 'package', 'bin', 'dataset'])


setB_blacklist = [
'444.namd',
'447.dealII',
'450.soplex',
'453.povray',
'471.omnetpp',
'473.astar',
'483.xalancbmk',
'520.omnetpp_r', '620.omnetpp_s',
'523.xalancbmk_r', '623.xalancbmk_s',
'531.deepsjeng_r', '631.deepsjeng_s',
'541.leela_r', '641.leela_s',
'507.cactuBSSN_r', '607.cactuBSSN_s',
'508.namd_r',
'510.parest_r',
'511.povray_r',
'526.blender_r'
]


def gen_option(input_root, output_root, package, blacklist, whitelist, dataset):
    ret = []
    cnt = 0

    comp_set = ['clang-13', 'gcc-11', 'clang-10', 'gcc-13']

    for arch in ['x64']:
        for comp in comp_set:
            for popt in ['pie']:
                for opt in ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']:
                    for lopt in ['bfd', 'gold']:
                        sub_dir = '%s/%s/%s_%s'%(package, comp, opt, lopt)
                        input_dir = '%s/%s'%(input_root, sub_dir)
                        for target in glob.glob('%s/bin/*'%(input_dir)):

                            filename = os.path.basename(target)
                            binpath = '%s/stripbin/%s'%(input_dir, filename)

                            out_dir = '%s/%s/%s'%(output_root, sub_dir, filename)

                            if blacklist and filename in blacklist:
                                continue
                            if whitelist and filename not in whitelist:
                                continue

                            # Exclude C++ for Egalito
                            if dataset in ['setB'] and filename in setB_blacklist:
                                continue

                            if package in ['coreutils-9.1']:
                                # 1 (opt) * 2 (comp) * 2 (linker) = 4
                                if comp_set in ['gcc-11', 'gcc-13']:
                                    if opt in ['ofast']:
                                        if filename in ['seq']:
                                            continue

                            if package in ['spec_cpu2006']:
                                # 5 (opt) * 4 (comp) * 2 (linker) =  40
                                if filename in ['416.gamess'] and opt not in ['o0']:
                                    continue
                                # 1 (opt) * 1 (comp) * 2 (linker) = 2
                                if filename in ['453.povray'] and opt in ['ofast'] and comp in ['gcc-13']:
                                    continue

                            if package in ['spec_cpu2006']:
                                # 1 (opt) * 1 (comp) * 2 (linker) = 2
                                if filename in ['511.povray_r'] and opt in ['ofast'] and comp in ['gcc-13']:
                                    continue



                            ret.append(BuildConf(target, input_root, sub_dir, out_dir, arch, comp, popt, package, binpath, dataset))

                            cnt += 1
    return ret


def cfg_suri(conf, filename, input_dir, output_dir):
    sub1 = '/usr/bin/time  -f\'%%E %%U %%S\' -o /output/tlog1.txt dotnet run --project=/project/B2R2/src/Test /input/%s /output/b2r2_meta.json > /output/log.txt'%(filename)

    cmd = 'docker run --rm --memory 64g --cpus 1  -v %s:/input -v %s:/output suri:v1.0 sh -c " %s"'%( input_dir, output_dir, sub1)
    print(cmd)

    sys.stdout.flush()
    os.system(cmd)


def symbol_suri(conf, filename, input_dir, output_dir):

    reassem_file = '%s/b2r2_meta.json'%(output_dir)

    if not os.path.exists(reassem_file):
        return

    current = multiprocessing.current_process()

    sub2 = '/usr/bin/time  -f\'%%E %%U %%S\' -o /output/tlog2.txt python3 /project/superSymbolizer/SuperSymbolizer.py /input/%s /output/b2r2_meta.json /output/%s.s --optimization 3 >> /output/log.txt'%(filename, filename)

    cmd = 'docker run --rm --memory 64g --cpus 1 -v %s:/input -v %s:/output suri:v1.0 sh -c " %s; "'%(input_dir, output_dir, sub2 )
    print(cmd)

    sys.stdout.flush()
    os.system(cmd)


def compile_suri(conf, filename, input_dir, output_dir):
    current = multiprocessing.current_process()
    sub3 = 'cd /project/superSymbolizer/'
    sub4 = '/usr/bin/time  -f\'%%E %%U %%s\' -o /output/tlog3.txt python3 /project/superSymbolizer/CustomCompiler.py /input/%s /output/%s.s /output/%s'%(filename, filename, filename)

    if conf.datset in ['setA', 'setC']:
        cmd = 'docker run --rm --memory 64g --cpus 1 -v %s:/input -v %s:/output suri:v1.0 sh -c " %s; %s"'%( input_dir, output_dir, sub3, sub4)
    elif conf.dataset in ['setB']:
        cmd = 'docker run --rm --memory 64g --cpus 1 -v %s:/input -v %s:/output suri_ubuntu18.04:v1.0 sh -c " %s; %s"'%( input_dir, output_dir, sub3, sub4)

    print(cmd)

    sys.stdout.flush()
    os.system(cmd)


def run_suri(conf, filename):
    input_dir = os.path.dirname(conf.bin)
    output_dir = '%s/super'%(conf.output_path)

    if not os.path.exists(output_dir):
        os.system('mkdir -p %s'%(output_dir))


    if not os.path.exists('%s/b2r2_meta.json'%(output_dir)):
        cfg_suri(conf, filename, input_dir, output_dir)

    if not os.path.exists('%s/%s.s'%(output_dir, filename)) or os.stat('%s/%s.s'%(output_dir, filename)).st_size == 0:
        symbol_suri(conf, filename, input_dir, output_dir)

    if not os.path.exists('%s/my_%s'%(output_dir, filename)):
        compile_suri(conf, filename, input_dir, output_dir)

def get_options(filepath):
    import subprocess
    result = subprocess.run(['ldd', filepath], stdout=subprocess.PIPE)
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


def reassem_ddisasm(conf, filename, input_dir, output_dir):

    current = multiprocessing.current_process()

    cmd = 'docker run --rm --memory 64g --cpus 1 -v %s:/input -v %s:/output reassessor/ddisasm:1.7.0_time sh -c "/usr/bin/time  -f\'%%E %%U %%S\' -o /output/tlog.txt ddisasm /input/%s --asm /output/ddisasm.s > /output/log.txt "'%(input_dir, output_dir, filename)
    print(cmd)
    sys.stdout.flush()
    os.system(cmd)

def compile_ddisasm(conf, filename, input_dir, output_dir):

    comp, lopt = get_options(conf.bin)
    sub = '/usr/bin/time  -f\'%%E %%U %%s\' -o /output/tlog2.txt %s /output/ddisasm.s %s -nostartfiles -o /output/%s'%(comp, lopt, filename)
    cmd = 'docker run --rm --memory 64g --cpus 1 -v %s:/input -v %s:/output suri:v1.0 sh -c " %s;"'%( input_dir, output_dir, sub)
    print(cmd)
    os.system(cmd)

def run_ddisasm(conf, filename):

    input_dir = os.path.dirname(conf.bin)
    output_dir = '%s/ddisasm'%(conf.output_path)

    if not os.path.exists(output_dir):
        os.system('mkdir -p %s'%(output_dir))

    if not os.path.exists('%s/ddisasm.s'%(output_dir)) or os.stat('%s/ddisasm.s'%(output_dir)).st_size == 0:
        reassem_ddisasm(conf, filename, input_dir, output_dir)

    if not os.path.exists('%s/%s'%(output_dir, filename)):
        compile_ddisasm(conf, filename, input_dir, output_dir)


def reassem_egalito(conf, filename, input_dir, output_dir):

    current = multiprocessing.current_process()

    sub_cmd = '/usr/bin/time  -f\'%%E %%U %%s\' -o /output/tlogx.txt /project/egalito/app/etelf -m /input/%s /output/%s > /output/log.txt 2>&1'%(filename, filename)
    cmd = 'docker run --rm --memory 64g --cpus 1 -v %s:/input -v %s:/output supercfg:v1.2_ubuntu18.04 sh -c " %s"'%( input_dir, output_dir, sub_cmd)
    print(cmd)
    sys.stdout.flush()
    os.system(cmd)


def run_egalito(conf, filename):
    input_dir = os.path.dirname(conf.bin)
    output_dir = '%s/egalito'%(conf.output_path)

    if not os.path.exists(output_dir):
        os.system('mkdir -p %s'%(output_dir))

    if not os.path.exists('%s/%s'%(output_dir, filename)) or os.stat('%s/%s'%(output_dir, filename)).st_size == 0:
        reassem_egalito(conf, filename, input_dir, output_dir)




def job(conf):
    filename = os.path.basename(conf.bin)

    run_suri(conf, filename)

    if conf.dataset == 'setA':
        run_ddisasm(conf, filename)
    if conf.dataset == 'setB':
        run_egalito(conf, filename)


def run(input_root, output_root, package, core=1, blacklist=None, whitelist=None, dataset=''):
    if package not in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006']:
        return False
    config_list = gen_option(input_root, output_root, package, blacklist, whitelist, dataset)

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
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], '"%s" is invalid. Please choose one from setA, setB, or setC.'%(args.dataset)

    input_dir = '%s/%s'%(args.input_dir, args.dataset)
    output_dir = '%s/%s'%(args.input_dir, args.dataset)

    if args.package:
        run(input_dir, output_dir, args.dataset, args.package, args.core, args.blacklist, args.whitelist, args.dataset)
    else:
        for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006']:
            run(input_dir, output_dir, args.dataset, package, args.core, args.blacklist, args.whitelist, args.dataset)

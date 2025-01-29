from collections import namedtuple
import glob, os, sys
import multiprocessing

BuildConf = namedtuple('BuildConf', ['target', 'input_root', 'sub_dir', 'output_path', 'arch', 'pie', 'package', 'bin'])

def single_run(target, bDocker=False):
    input_path = '/data4/benchmark'
    output_path = '/data4/output3'
    package, _, _ = target.split('/')[-5:-2]
    arch = 'x64'
    popt = 'pie'
    sub_dir = '/'.join(target.split('/')[-5:-2])

    filename = os.path.basename(target)
    out_dir = '%s/%s/%s'%(output_path, sub_dir, filename)
    conf = BuildConf(target, input_path, sub_dir, out_dir, arch, popt, package, target)

    if not bDocker:
        job(conf, reset=True)
    else:
        docker_job(conf)


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
                        for target in glob.glob('%s/stripbin/*'%(input_dir)):

                            filename = os.path.basename(target)
                            binpath = '%s/stripbin/%s'%(input_dir, filename)

                            reassem_dir = '%s/%s/%s'%(reassem_root, sub_dir, filename)
                            out_dir = '%s/%s/%s'%(output_root, sub_dir, filename)

                            norm_dir = '%s/norm_db'%(out_dir)
                            b2r2_func_path = '%s/b2r2_meta.json'%(norm_dir)
                            if os.path.exists(b2r2_func_path):
                                continue

                            if blacklist and filename in blacklist:
                                continue
                            if whitelist and filename not in whitelist:
                                continue

                            ret.append(BuildConf(target, input_root, sub_dir, out_dir, arch, popt, package, binpath))

                            cnt += 1
    return ret

def job(conf, reset=False):
    #~/dotnet/dotnet run --project=src/Test  /Users/basic/Downloads/benchmark/case3 /Users/basic/project/supersetCFG/test/b3.json

    norm_dir = '%s/norm_db'%(conf.output_path)
    #b2r2_func_path = '%s/b2r2_strip_func.json'%(norm_dir)
    #b2r2_log_path = '%s/b2r2_strip_log.txt'%(norm_dir)

    b2r2_func_path = '%s/b2r2_meta.json'%(norm_dir)
    b2r2_log_path = '%s/b2r2_log.txt'%(norm_dir)

    if not reset and os.path.exists(b2r2_func_path):
        return

    print('mkdir -p %s'%(norm_dir))
    os.system('mkdir -p %s'%(norm_dir))
    #print("~/dotnet/dotnet run --project=src/Test %s %s att"%(conf.target, b2r2_func_path))
    #os.system("~/dotnet/dotnet run --project=src/Test %s %s att > %s 2>&1"%(conf.target, b2r2_func_path, b2r2_log_path))
    print("~/dotnet/dotnet run --project=src/Test %s %s "%(conf.target, b2r2_func_path))
    os.system("~/dotnet/dotnet run --project=src/Test %s %s > %s 2>&1"%(conf.target, b2r2_func_path, b2r2_log_path))
    sys.stdout.flush()





def docker_job(conf):
    filename=os.path.basename(conf.target)
    cmd = 'docker run --rm -v %s:/input -v %s:/output reassessor -v %s:/reassem sh -c '%(os.path.abspath(conf.input_root), os.path.abspath(conf.output_path), os.path.abspath(conf.reassem_path))
    cmd += '"python3 -m Reassessor.reassessor.reassessor /input/%s/reloc/%s /input/%s/asm /output/ --build_path /input/ --build_path /input/%s/bin/%s'%(conf.sub_dir, filename, conf.sub_dir, conf.sub_dir, filename)
    if os.path.exists(conf.reassem_path+'/ramblr.s'):
        cmd += ' --ramblr /reassem/ramblr.s'
    if os.path.exists(conf.reassem_path+'/retrowrite.s'):
        cmd += ' --retrowrite /reassem/retrowrite.s'
    if os.path.exists(conf.reassem_path+'/ddisasm.s'):
        cmd += ' --ddisasm /reassem/ddisasm.s'
    cmd += '"'
    print(cmd)
    os.system(cmd)


def run(package, core=1, bDocker=False, blacklist=None, whitelist=None):
    if package not in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017', 'spec_cpu2006', 'lighttpd-1.4.72', 'nginx-1.25.2', 'sqlite-3.43.2', 'mysql-server-8.0']:
        return False
    input_root = '/data4/benchmark'
    reassem_root = '/data4/output3'
    output_root = '/data4/output3'
    config_list = gen_option(input_root, reassem_root, output_root, package, blacklist, whitelist)

    if core and core > 1:
        p = multiprocessing.Pool(core)
        if not bDocker:
            p.map(job, [(conf) for conf in config_list])
        else:
            p.map(docker_job, [(conf) for conf in config_list])
    else:
        for conf in config_list:
            if not bDocker:
                job(conf)
            else:
                docker_job(conf)


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='manager')
    parser.add_argument('--package', type=str, help='Package')
    parser.add_argument('--core', type=int, default=1, help='Number of cores to use')
    parser.add_argument('--docker', action='store_true')
    parser.add_argument('--target', type=str)
    parser.add_argument('--blacklist', nargs='+')
    parser.add_argument('--whitelist', nargs='+')

    args = parser.parse_args()

    if args.target:
        single_run(args.target, args.docker)
    elif args.package:
        run(args.package, args.core, args.docker, args.blacklist, args.whitelist)
    else:
        #for package in ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2017']:
        #for package in ['coreutils-9.1', 'binutils-2.40']:
        #for package in ['binutils-2.40']:
        #for package in ['coreutils-9.1']:
        #for package in ['spec_cpu2017']:
        #for package in ['spec_cpu2006']:
        for package in ['lighttpd-1.4.72', 'nginx-1.25.2', 'sqlite-3.43.2', 'mysql-server-8.0']:
            run(package, args.core, args.docker, args.blacklist, args.whitelist)

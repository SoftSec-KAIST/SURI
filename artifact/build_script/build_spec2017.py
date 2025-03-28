import argparse
import os
import shutil

OPTIMIZATIONS = ['-O0', '-O1', '-O2', '-O3', '-Os', '-Ofast']
LINKERS = ['bfd', 'gold']

def parse_arguments():
    parser = argparse.ArgumentParser('setup spec_cpu2017')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--spec', type=str, default='spec2017_image')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setB', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)
    assert os.path.exists(os.path.join(args.spec, 'install.sh')), 'Invalid SPEC path: "%s"' % args.spec

    return args

def get_docker_image(dataset):
    if dataset in ['setA', 'setC']:
        return 'suri_artifact:v1.0'
    else:
        return 'suri_artifact_ubuntu18.04:v1.0'

################################

def setup(dataset, spec_path):
    image = get_docker_image(dataset)

    cmd = 'docker run --rm -v %s:/spec2017_image -v $(pwd)/src:/data %s sh -c "chmod -R +x /spec2017_image && /spec2017_image/install.sh -d /data/spec_cpu2017 -f"' % (spec_path, image)
    print(cmd)
    os.system(cmd)

    shutil.copyfile('script/base2017.cfg', './src/spec_cpu2017/config/base2017.cfg')
    print('[+] Successfully finish setup SPEC CPU2017')

################################

def get_script_name(dataset):
    if dataset in ['setA', 'setB']:
        return 'build-spec2017.sh'
    else:
        return 'build-spec2017_no_ehframe.sh'

def build(dataset, out_dir, opt, lopt):
    image = get_docker_image(dataset)
    script = get_script_name(dataset)

    cmd = 'docker run --rm -v $(pwd)/src:/data -v $(pwd)/script:/script -v %s:/output %s sh -c "/script/%s %s %s"' % (out_dir, image, script, opt, lopt)
    print(cmd)
    os.system(cmd)

################################

def run(args):
    spec_path = os.path.abspath(args.spec)
    out_dir = os.path.join(os.path.abspath("../benchmark"), args.dataset)

    setup(args.dataset, spec_path)
    for opt in OPTIMIZATIONS:
        for lopt in LINKERS:
            build(args.dataset, out_dir, opt, lopt)

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

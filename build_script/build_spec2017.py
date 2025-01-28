import argparse
import os
import shutil

def run(spec_path):
    src = os.path.abspath(spec_path)
    output = os.path.abspath("../benchmark")

    if os.path.exists('%s/install.sh'%(src)):

        cmd = 'docker run --rm -v "%s:/spec2017_image" -v "$(pwd)/src:/data" suri:v0.2 sh -c "/spec2017_image/install.sh -d /data/spec_cpu2017 -f"'%(src)
        print(cmd)
        os.system(cmd)
        shutil.copyfile('script/base2017.cfg', './src/spec_cpu2017/config/base2017.cfg')
        print('[+] Successfully finish setup SPEC CPU2017')
        cmd = 'docker run -it --rm -v "$(pwd)/src:/data" -v "$(pwd)/script:/script" -v %s:/output suri:v0.2 sh -c "/script/build-spec2017.sh"'%(output)
        print(cmd)
        os.system(cmd)
    else:
        print('[-] Install script does not exist')

if __name__ == '__main__':
    parser = argparse.ArgumentParser('setup spec_cpu2017')
    parser.add_argument('spec2017')

    args = parser.parse_args()

    run(args.spec2017)



import argparse
import os
import shutil

def run(spec_path):
    src = os.path.abspath(spec_path)
    output = os.path.abspath("../benchmark")

    if os.path.exists('%s/install.sh'%(src)):

        cmd = 'docker run --rm -v "%s:/spec2006_image" -v "$(pwd)/src:/data" suri_artifact:v1.0 sh -c "chmod -R +x /spec2006_image && /spec2006_image/install.sh -d /data/spec_cpu2006 -f"'%(src)
        print(cmd)
        os.system(cmd)
        shutil.copyfile('script/base2006.cfg', './src/spec_cpu2006/config/base2006.cfg')
        print('[+] Successfully finish setup SPEC CPU2006')

        for opt in ['-O0', '-O1', '-O2', '-O3', '-Os', '-Ofast']:
            for lopt in ['bfd', 'gold']:
                cmd = 'docker run --rm -v "$(pwd)/src:/data" -v "$(pwd)/script:/script" -v %s:/output suri_artifact:v1.0 sh -c "/script/build-spec2006.sh %s %s" '%(output, opt, lopt)
                print(cmd)
                os.system(cmd)
    else:
        print('[-] Install script does not exist')

if __name__ == '__main__':
    parser = argparse.ArgumentParser('setup spec_cpu2006')
    parser.add_argument('spec2006')

    args = parser.parse_args()

    run(args.spec2006)



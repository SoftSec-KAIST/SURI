import os

class Builder:
    def __init__(self, target, verbose):
        self.target =target
        self.input_dir = os.path.dirname(target)
        self.output_dir = os.getcwd()
        self.filename = os.path.basename(target)
        self.verbose = verbose


    def run_docker(self, cmd):
        if self.verbose:
            docker_cmd = 'docker run --rm -v %s:/input -v %s:/output suri_artifact:v1.0 sh -c " %s; "'%(self.input_dir, self.output_dir, cmd )
        else:
            docker_cmd = 'docker run --rm -v %s:/input -v %s:/output suri_artifact:v1.0 sh -c " %s 2> /dev/null "'%(self.input_dir, self.output_dir, cmd )
        os.system(docker_cmd)

    def run(self):
        cmd= 'python3 /project/SURI/suri.py /input/%s  --ofolder /output/output --without-compile'%(self.filename)
        self.run_docker(cmd)

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Builder')
    parser.add_argument('target', type=str, help='Target Binary')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    target = os.path.abspath(args.target)

    suri = Builder(target, args.verbose)
    suri.run()

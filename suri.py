import os

class SURI:
    def __init__(self, target, verbose):
        self.target =target
        self.input_dir = os.path.dirname(target)
        self.output_dir = os.getcwd()
        self.suri_dir = os.path.dirname(os.path.realpath(__file__))
        self.filename = os.path.basename(target)
        self.verbose = verbose

        self.json = '%s.json'%(self.filename)
        self.asm = '%s.s'%(self.filename)
        self.tmp = 'tmp_%s'%(self.filename)
        self.myfile = 'my_%s'%(self.filename)

    def run_docker(self, cmd):
        if self.verbose:
            print(cmd)
            docker_cmd = 'docker run --rm -v %s:/input -v %s:/output suri:v1.0 sh -c " %s; "'%(self.input_dir, self.output_dir, cmd )
        else:
            docker_cmd = 'docker run --rm -v %s:/input -v %s:/output suri:v1.0 sh -c " %s 2> /dev/null "'%(self.input_dir, self.output_dir, cmd )
        os.system(docker_cmd)

    def cfg_suri(self):
        cmd = 'dotnet run --project=/project/B2R2/src/Test /input/%s /output/%s'%(self.filename, self.json)
        self.run_docker(cmd)

    def symbol_suri(self):

        cmd= 'python3 /project/superSymbolizer/SuperSymbolizer.py /input/%s /output/%s /output/%s --optimization 3 '%(self.filename, self.json , self.asm)
        self.run_docker(cmd)

    def compile_suri(self):
        cmd = 'python3 %s/superSymbolizer/CustomCompiler.py %s %s/%s %s/%s'%(self.suri_dir, self.target, self.output_dir, self.asm, self.output_dir, self.filename)

        if self.verbose:
            print(cmd)

        os.system(cmd)

    def run(self):
        self.cfg_suri()
        if not os.path.exists(self.json):
            return

        self.symbol_suri()
        if not os.path.exists(self.asm):
            return

        self.compile_suri()

        print('[+] Generate rewritten binary: %s'%(self.myfile))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SURI')
    parser.add_argument('target', type=str, help='Target Binary')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    target = os.path.abspath(args.target)

    suri = SURI(target, args.verbose)
    suri.run()


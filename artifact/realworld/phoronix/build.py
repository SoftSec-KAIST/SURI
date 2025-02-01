import os

class Builder:
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
        cmd_list = []
        cmd_list.append('cd /project/superSymbolizer/')
        cmd_list.append('python3 CustomCompiler.py /input/%s /output/%s /output/%s'%(self.filename, self.asm, self.filename))
        cmd = ';'.join(cmd_list)
        if self.verbose:
            print(cmd)
        self.run_docker(cmd)

    def run(self):
        self.cfg_suri()
        if not os.path.exists(self.json):
            return

        self.symbol_suri()
        if not os.path.exists(self.asm):
            return

        print('[+] Generate assembly file: %s'%(self.asm))

        if os.path.exists(self.myfile):
            os.remove(self.myfile)

        self.verbose = True
        self.compile_suri()

        if os.path.exists(self.myfile):
            print('[+] Generate rewritten binary: %s'%(self.myfile))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Builder')
    parser.add_argument('target', type=str, help='Target Binary')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    target = os.path.abspath(args.target)

    suri = Builder(target, args.verbose)
    suri.run()

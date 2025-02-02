import os
from superSymbolizer import SuperSymbolizer, CustomCompiler, SuperAsan


class Emitter:
    def __init__(self, target, asm, new_out_dir, asan, use_docker, verbose):
        self.target = target
        self.input_dir = os.path.dirname(target)
        if new_out_dir:
            self.output_dir = os.path.abspath(new_out_dir)
        else:
            self.output_dir = os.getcwd()
        self.suri_dir = os.path.dirname(os.path.realpath(__file__))
        self.filename = os.path.basename(target)
        self.use_docker = use_docker
        self.verbose = verbose

        if asan:
            self.asan = '%s_asan.json'%(self.filename)
        else:
            self.asan = ''
        self.asm = asm
        self.tmp = 'tmp_%s'%(self.filename)
        self.myfile = 'my_%s'%(self.filename)

    def run_docker(self, cmd):
        if self.verbose:
            print(cmd)
            docker_cmd = 'docker run --rm -v %s:/input -v %s:/output suri:v1.0 sh -c " %s; "'%(self.input_dir, self.output_dir, cmd )
        else:
            docker_cmd = 'docker run --rm -v %s:/input -v %s:/output suri:v1.0 sh -c " %s 2> /dev/null "'%(self.input_dir, self.output_dir, cmd )
        os.system(docker_cmd)


    def compile_suri(self):
        if self.use_docker:
            input_path = '/input/%s'%(self.filename)
            asm_path = '/output/%s'%(self.asm)
            output_path = '/output/%s'%(self.filename)

            if self.asan:
                cmd = 'python3 /project/SURI/superSymbolizer/CustomCompiler.py %s %s %s --asan'%(input_path, asm_path, output_path)
            else:
                cmd = 'python3 /project/SURI/superSymbolizer/CustomCompiler.py %s %s %s'%(input_path, asm_path, output_path)

            if self.verbose:
                print(cmd)

            self.run_docker(cmd)
        else:
            input_path = '%s/%s'%(self.input_dir, self.filename)
            asm_path =   self.asm
            output_path = '%s/%s'%(self.output_dir, self.filename)

            if self.asan:
                CustomCompiler.emitter(input_path, asm_path, output_path, asan=True)
            else:
                CustomCompiler.emitter(input_path, asm_path, output_path)


    def run(self):
        my_path = '%s/%s'%(self.output_dir, self.myfile)

        if os.path.exists(my_path):
            os.remove(self.myfile)

        self.compile_suri()

        if os.path.exists(my_path):
            print('[+] Generate rewritten binary: %s'%(my_path))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Emitter')
    parser.add_argument('target', type=str, help='Target Binary')
    parser.add_argument('assembly', type=str, help='Assembly File')
    parser.add_argument('--ofolder', type=str, help='Output Dir')
    parser.add_argument('--asan', action='store_true')
    parser.add_argument('--usedocker', action='store_true')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    target = os.path.abspath(args.target)

    emitter = Emitter(target, args.assembly, args.ofolder, args.asan, args.usedocker, args.verbose)
    emitter.run()

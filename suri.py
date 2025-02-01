import os

class SURI:
    def __init__(self, target, use_docker, verbose):
        self.target = target
        self.input_dir = os.path.dirname(target)
        self.output_dir = os.getcwd()
        self.suri_dir = os.path.dirname(os.path.realpath(__file__))
        self.filename = os.path.basename(target)
        self.use_docker = use_docker
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
        if self.use_docker:
            file_path = '/input/%s'%(self.filename)
            json_path = '/output/%s'%(self.json)
            cmd = 'dotnet run --project=/project/superCFGBuilder/superCFGBuilder %s %s'%(file_path, json_path)
            self.run_docker(cmd)
        else:
            file_path = '%s/%s'%(self.input_dir, self.filename)
            json_path = '%s/%s'%(self.output_dir, self.json)
            cmd = 'dotnet run --project=%s/superCFGBuilder/superCFGBuilder %s %s'%(self.suri_dir, file_path, json_path)
            os.system(cmd)

    def symbol_suri(self):
        if self.use_docker:
            file_path = '/input/%s'%(self.filename)
            json_path = '/output/%s'%(self.json)
            asm_path = '/output/%s'%(self.asm)
            cmd = 'python3 /project/superSymbolizer/SuperSymbolizer.py %s %s %s --optimization 3 '%(file_path, json_path , asm_path)
            self.run_docker(cmd)
        else:
            file_path = '%s/%s'%(self.input_dir, self.filename)
            json_path = '%s/%s'%(self.output_dir, self.json)
            asm_path = '%s/%s'%(self.asm_dir, self.asm)
            cmd = 'python3 %s/superSymbolizer/SuperSymbolizer.py %s/%s %s/%s %s/%s --optimization 3 '%(self.suri_dir, file_path, json_path, asm_path)
            os.system(cmd)

    def compile_suri(self):
        if self.use_docker:
            input_path = '/input/%s'%(self.input_dir, self.filename)
            asm_path = '/output/%s'%(self.output_dir, self.asm)
            output_path = '/output/%s'%(self.output_dir, self.filename)
            cmd = 'python3 /project/superSymbolizer/CustomCompiler.py %s %s %s'%(self.suri_dir, input_path, asm_path, output_path)

            if self.verbose:
                print(cmd)

            self.run_docker(cmd)
        else:
            input_path = '%s/%s'%(self.input_dir, self.filename)
            asm_path = '%s/%s'%(self.output_dir, self.asm)
            output_path = '%s/%s'%(self.output_dir, self.filename)
            cmd = 'python3 %s/superSymbolizer/CustomCompiler.py %s %s %s'%(self.suri_dir, input_path, asm_path, output_path)

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

        print('[+] Generate assembly file: %s'%(self.asm))

        if os.path.exists(self.myfile):
            os.remove(self.myfile)

        self.compile_suri()

        if os.path.exists(self.myfile):
            print('[+] Generate rewritten binary: %s'%(self.myfile))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SURI')
    parser.add_argument('target', type=str, help='Target Binary')
    parser.add_argument('--usedocker', action='store_true')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    target = os.path.abspath(args.target)

    suri = SURI(target, args.usedocker, args.verbose)
    suri.run()

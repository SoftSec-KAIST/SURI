import os
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description='GT')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='gt')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setC'], 'Invalid dataset: "%s"'%(args.dataset)

    return args

def run(args):
    in_dir = os.path.join(args.input_dir, args.dataset)
    out_dir = os.path.join(args.output_dir, args.dataset)
    os.system('mkdir -p %s' % out_dir)

    in_dir = os.path.abspath(in_dir)
    out_dir = os.path.abspath(out_dir)

    cmd = 'docker run --rm -v %s:/data3/3_supersetCFG/benchmark -v %s:/output  suri_artifact:v1.0 sh -c "python3 /project/Reassessor/artifact/run_reassessor.py /data3/3_supersetCFG/benchmark /output"' % (in_dir, out_dir)
    print(cmd)
    os.system(cmd)

if __name__ == '__main__':
    args = parse_arguments()
    run(args)

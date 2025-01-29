import os

def run(input_dir, output_dir):

    input_dir = os.path.abspath(input_dir)

    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)
    output_dir = os.path.abspath(output_dir)

    cmd = 'docker run --rm -v %s:/data3/3_supersetCFG/benchmark -v %s:/output  suri:v1.0 sh -c "python3 /project/Reassessor/artifact/run_reassessor.py /data3/3_supersetCFG/benchmark /output"'%(input_dir, output_dir)
    print(cmd)
    os.system(cmd)


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GT')
    parser.add_argument('dataset', type=str, default='setA', help='Select dataset (setA, setB, setC)')
    parser.add_argument('--input_dir', type=str, default='benchmark')
    parser.add_argument('--output_dir', type=str, default='gt')

    args = parser.parse_args()

    assert args.dataset in ['setA', 'setC'], '"%s" is invalid. Please choose one from setA or setC.'%(args.dataset)

    input_dir = '%s/%s'%(args.input_dir, args.dataset)
    output_dir = '%s/%s'%(args.input_dir, args.dataset)
    run(input_dir, output_dir)


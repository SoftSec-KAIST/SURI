import glob
import os

errors = [
        b"bad(",
        b"Segmentation fault",
        b"Aborted",
        b"timeout: the monitored command dumped core"
        ]

def get_gt():
    bad = []
    good = []
    for log in glob.glob('bin_original/logs/*'):
        with open(log, 'rb') as fd:
            data = fd.read()
            filename = os.path.basename(log)
            for error in errors:
                if error in data:
                    bad.append(filename)
                    break
            if filename not in bad:
                good.append(filename)
            
    return (bad, good)

def get_res(dataset):
    bad = []
    good = []
    base = 'bin_%s'%(dataset)
    for log in glob.glob('%s/logs/*'%(base)):
        with open(log, 'rb') as fd:
            filename = os.path.basename(log)
            if filename.startswith('my_'):
                filename = filename[3:]

            data = fd.read()
            if b'=ERROR' in data:
                bad.append(filename)
            else:
                good.append(filename)

    return (bad, good)

def get_tp(gt, res1, res2, res3):
    tp1 = gt.intersection(res1)
    tp2 = gt.intersection(res2)
    tp3 = gt.intersection(res3)
    return len(tp1), len(tp2), len(tp3)

def get_fp(gt, res1, res2, res3):
    fp1 = res1 - gt
    fp2 = res2 - gt
    fp3 = res3 - gt
    return len(fp1), len(fp2), len(fp3)

def get_fn(gt, res1, res2, res3):
    fn1 = gt - res1 
    fn2 = gt - res2 
    fn3 = gt - res3 
    return len(fn1), len(fn2), len(fn3)

def get_tn(gt, res1, res2, res3):
    tn1 = gt.intersection(res1)
    tn2 = gt.intersection(res2)
    tn3 = gt.intersection(res3)
    return len(tn1), len(tn2), len(tn3)

def summary(gt, suri, retro, asan):
    gt_bad_set = set(gt[0])
    suri_bad_set = set(suri[0])
    retro_bad_set = set(retro[0])
    asan_bad_set = set(asan[0])

    gt_good_set = set(gt[1])
    suri_good_set = set(suri[1])
    retro_good_set = set(retro[1])
    asan_good_set = set(asan[1])

    print('%15s %10s %10s %10s'%('', 'Ours', 'BASan', 'ASan'))

    res1, res2, res3 = get_tp(gt_bad_set, suri_bad_set, retro_bad_set, asan_bad_set)
    print('%15s %10d %10d %10d'%('True Positive', res1, res2, res3) )

    res1, res2, res3 = get_fp(gt_bad_set, suri_bad_set, retro_bad_set, asan_bad_set)
    print('%15s %10d %10d %10d'%('False Positive', res1, res2, res3) )

    res1, res2, res3 = get_fn(gt_bad_set, suri_bad_set, retro_bad_set, asan_bad_set)
    print('%15s %10d %10d %10d'%('False Negative', res1, res2, res3) )

    res1, res2, res3 = get_tn(gt_good_set, suri_good_set, retro_good_set, asan_good_set)
    print('%15s %10d %10d %10d'%('True Negative', res1, res2, res3) )

    print('-------------------------------------------------')
    print('%15s %10d %10d %10d'%('Total Binaries', 
        len(suri_bad_set | suri_good_set), 
        len(retro_bad_set | retro_good_set),
        len(asan_bad_set | asan_good_set)))

if __name__ == '__main__':
    
    gt = get_gt()
    
    suri = get_res('suri')
    retro = get_res('retro')
    asan = get_res('asan')

    summary(gt, suri, retro, asan)



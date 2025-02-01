# How To Run Experiments

:alarm_clock:: This mark shows the estimated time when we ran the experiment on our environment.
Depending on your computing machine, the actual time may be different from the indicated time.
Note that we used a machine with an Intel Core i9-11900K processor and 128GB of RAM.

## Exp1: Reassembly completion comparison (RQ1)

:alarm_clock: 28 hrs on Coreutils and Binutils, 10 days on full dataset

In this experiment, we rewrite binaries using SURI (setA, setB, and setC), Ddisasm (setA), Egalito (setB) and see if reassembly is successful.

To rewrite the binaries in each dataset, use the `1_get_reassembled_code.py` script provided in the artifact.

For setA, rewrite the binaries using SURI and Ddisasm:
```
$ python3 1_get_reassembled_code.py setA
```

If you want to process multiple binaries in parallel, you can use the `--core`
option. Note that this may affect the rewriting time.
```
$ python3 1_get_reassembled_code.py setA --core 4
```

Repeat the process for setB:
```
$ python3 1_get_reassembled_code.py setB
```

And for setC:
```
$ python3 1_get_reassembled_code.py setC
```

Once rewriting is complete, you can check the success rate and reassembly time
using the following script. Then the partial results for Table 2 and 3 of our paper are shown
on the screen.
```
$ python3 1_print_rewrite_result.py setA
                                                      suri                  ddisasm
-----------------------------------------------------------------------------------
  coreutils-9.1      clang (2592) : 100.000000%   6.387157 : 100.000000%   1.605671
  coreutils-9.1        gcc (2588) : 100.000000%   6.297713 : 100.000000%   1.463037
  binutils-2.40      clang ( 360) : 100.000000%  31.467667 : 100.000000%  51.741306
  binutils-2.40        gcc ( 360) : 100.000000%  31.824139 : 100.000000%  47.637750
   spec_cpu2006      clang ( 724) : 100.000000%  27.779019 : 100.000000%  67.314296
   spec_cpu2006        gcc ( 722) : 100.000000%  27.872659 : 100.000000%  71.868601
   spec_cpu2017      clang (1128) : 100.000000%  97.727291 :  95.567376% 194.729230
   spec_cpu2017        gcc (1126) : 100.000000% 102.809319 :  99.111901% 208.144185
----------------------------------------------------------------------------------
                       all (9600) : 100.000000%  32.912534 :  99.375000%  61.099625

$ python3 1_print_rewrite_result.py setB
                                                      suri                  egalito
-----------------------------------------------------------------------------------
  coreutils-9.1      clang (1296) : 100.000000%   7.307790 : 100.000000%   0.085969
  coreutils-9.1        gcc (1294) : 100.000000%   6.136468 :  89.799073%   0.090805
  binutils-2.40      clang ( 180) : 100.000000%  37.031034 :  96.666667%   2.200230
  binutils-2.40        gcc ( 180) : 100.000000%  32.977152 :  87.777778%   1.958038
   spec_cpu2006      clang ( 278) : 100.000000%  28.286615 :  98.920863%   1.499615
   spec_cpu2006        gcc ( 278) : 100.000000%  28.612017 :  93.165468%   1.489496
   spec_cpu2017      clang ( 384) : 100.000000% 107.652470 :  97.395833%   6.142199
   spec_cpu2017        gcc ( 396) : 100.000000% 131.231783 :  90.909091%   8.151433
----------------------------------------------------------------------------------
                       all (4286) : 100.000000%  27.821629 :  94.680355%   1.458404
```

## Exp2: Test suite pass rate comparison (RQ1)

In this experiment, we run the test suite of each benchmark to see if the rewritten binaries from Exp1 run normally as before.

You need to first collect the binaries for the reliability testing using the `2_make_set.py` script.
This will create setA, setB, and setC directories in the project directory.
```
$ python3 2_make_set.py setA
$ python3 2_make_set.py setB
$ python3 2_make_set.py setC
```

### Coreutils and Binutils Tests

:alarm_clock: 15 hrs, 3-5 mins per each test suite

To verify the reliability of the rewritten binaries, run the test suites for Coreutils and Binutils.

Run the test suite for setA (SURI vs. Ddisasm):
```
$ python3 2_run_testsuite.py setA
...
                                          suri                Ddiasm
coreutils-9.1   (clang):       Succ(  24/  24)       Succ(  24/  24)
coreutils-9.1   (gcc  ):       Succ(  24/  24)       Fail(  14/  24)
binutils-2.40   (clang):       Succ(  24/  24)       Succ(  24/  24)
binutils-2.40   (gcc  ):       Succ(  24/  24)       Fail(   7/  24)
```

Run the test suite for setB (SURI vs. Egalito):
```
$ python3 2_run_testsuite.py setB
...
                                          suri               Egalito
coreutils-9.1   (gcc  ):       Succ(  12/  12)       Fail(   0/  12)
coreutils-9.1   (clang):       Succ(  12/  12)       Fail(   0/  12)
binutils-2.40   (gcc  ):       Succ(  12/  12)       Fail(   0/  12)
binutils-2.40   (clang):       Succ(  12/  12)       Fail(   0/  12)
```

If Egalito produces invalid binaries that cause the test suite to hang, use the
provided script to terminate the Docker process:

```
$ /bin/bash terminate_suri_docker.sh
```

Finally, test setC (ablation study of SURI):
```
$ python3 2_run_testsuite.py setC
...
                              suri(no_ehframe)
coreutils-9.1   (clang):       Succ(  24/  24)
coreutils-9.1   (gcc  ):       Succ(  24/  24)
binutils-2.40   (clang):       Succ(  24/  24)
binutils-2.40   (gcc  ):       Succ(  24/  24)

```

### SPEC Benchmark

:alarm_clock: 7-10 days

If you have your own SPEC benchmarks and you have built updated Docker images
(FIXME), then you can run the SPEC benchmark test suites. Execute the test
suite using the `2_run_testsuite_spec.py` script. After running the script, the
results will be displayed.

If the tests are stopped occasionally, you can continue from the stopped test suite.

```
$ python3 2_run_testsuite_spec.py setA
                        :                    suri :                 ddiasm
-----------------------------------------------------------------------------
spec_cpu2006    (clang) : 100.000000% ( 724/ 724) :  86.878453% ( 629/ 724)
			[+] SURI passes all test suites (724/724)
spec_cpu2006    (gcc  ) : 100.000000% ( 722/ 722) :  85.872576% ( 620/ 722)
			[+] SURI passes all test suites (722/722)
spec_cpu2017    (clang) : 100.000000% (1078/1078) :  86.270872% ( 930/1078)
			[+] SURI passes all test suites (1128/1128)
spec_cpu2017    (gcc  ) : 100.000000% (1116/1116) :  82.885305% ( 925/1116)
			[+] SURI passes all test suites (1126/1126)

$ python3 2_run_testsuite_spec.py setB
                        :                    suri :                egalito
-----------------------------------------------------------------------------
spec_cpu2006    (clang) : 100.000000% ( 275/ 275) :  93.454545% ( 257/ 275)
			[+] SURI passes all test suites (278/278)
spec_cpu2006    (gcc  ) : 100.000000% ( 259/ 259) :  85.714286% ( 222/ 259)
			[+] SURI passes all test suites (278/278)
spec_cpu2017    (clang) : 100.000000% ( 374/ 374) :  87.967914% ( 329/ 374)
			[+] SURI passes all test suites (384/384)
spec_cpu2017    (gcc  ) : 100.000000% ( 360/ 360) :  80.555556% ( 290/ 360)
			[+] SURI passes all test suites (396/396)

$ python3 2_run_testsuite_spec.py setC
                        :       suri (no ehframe)
-----------------------------------------------------------------------------
spec_cpu2006    (clang) : 100.000000% ( 724/ 724)
			[+] SURI passes all test suites (724/724)
spec_cpu2006    (gcc  ) : 100.000000% ( 722/ 722)
			[+] SURI passes all test suites (722/722)
spec_cpu2017    (clang) : 100.000000% (1128/1128)
			[+] SURI passes all test suites (1128/1128)
spec_cpu2017    (gcc  ) : 100.000000% (1126/1126)
			[+] SURI passes all test suites (1126/1126)
```
If your PC has enough memory, we can ran it with multithreading by enabling --core options.
```
$ python3 2_run_testsuite_spec.py setA --core 4
```

These results correspond to the remaining data of Table 2 and 3 in our paper.

## Exp3: Reliability test on real-world programs (RQ1)

:alarm_clock: 1 days

In this experiment, we rewrite real-world binaries and runs their own test suites to further demonstrate the reliability of SURI.

First, you can rewrite five real-world programs (7zip, apache, mariadb, nginx,
sqlite3) in Phoronix test suite. The Phoenix binaries will be executed
within the Phoenix test suite inside the `suri:v1.0` Docker image. We provide a
separate build script to ensure that the binaries can be compiled in an Ubuntu
20.04 environment.

```
$ cd realworld/phoronix
$ /bin/bash build.sh
```

After execution, the following binaries will be generated: `my_7zip`,
`my_apache`, `my_mariadb`, `my_nginx`, and `my_sqlite3`.

Next, run the Docker container and copy the binaries to the Phoronix directory:
```
# Run docker
$ /bin/bash run_docker.sh

# Copy to Phoronix directory.
root@bc838d2d3cfe:/# /bin/bash /data/copy.sh
```

You can run the Phoronix Test Suite using the following commands. When running
the test suite, you can select the desired benchmark for each test.
```
root@bc838d2d3cfe:/# phoronix-test-suite benchmark 7zip

root@bc838d2d3cfe:/# phoronix-test-suite benchmark apache

root@bc838d2d3cfe:/# phoronix-test-suite benchmark mysqlslap

root@bc838d2d3cfe:/# phoronix-test-suite benchmark nginx

root@bc838d2d3cfe:/# phoronix-test-suite benchmark sqlite
```
Each command will report the success of test suites. We compared the execution
results of the rewritten binaries with those of the original binaries before
running /data/copy.sh to determine whether the rewritten binaries were
successfully executed.

Similarly, to rewrite real-world client programs, follow the steps below:
```
$ cd realworld/client
$ ls
epiphany  filezilla  openssh  putty  vim

$ python3 ../../../suri.py epiphany
$ python3 ../../../suri.py filezilla
$ python3 ../../../suri.py openssh
$ python3 ../../../suri.py putty
$ python3 ../../../suri.py vim
```
Since these programs do not have their own Phoronix test suites, you can manually test the rewritten binaries by executing them.

Additionally, Epiphany, PuTTY, and FileZilla are GNU programs that require a
desktop environment to run. For Epiphany, we provide a dedicated script,
`run_epiphany.sh`, to facilitate execution.
```
$ /bin/bash run_epiphany.sh

$ ./my_filezilla

$ ./my_openssh

$ ./my_putty

$ ./my_vim
```

## Exp4: Overhead of Rewritten Binaries (RQ2)

### Overhead Incurred by SURI

In this experiment, we measured the instrumentation overhead of the binaries
rewritten by SURI, as explained in Section 4.3.1 of the paper.

To measure code size overhead, execute the following scripts:
```
$ python3 4_get_code_size.py setA
$ python3 4_print_code_size_overhead.py setA

  coreutils-9.1       5180   2.691429
  binutils-2.40        720   0.598323
   spec_cpu2006       1446   4.737552
   spec_cpu2017       2254   2.311999
-----------------------------------------------
         [+]All       9600   2.753556

```

To analyze the overhead of if-then-else statements, run:
```
$ python3 4_get_br_stat.py ./benchmark ./output
$ python3 4_print_br_overhead.py setA

Multi Br-------------
  coreutils-9.1       5136   0.020213
  binutils-2.40        720   0.013744
   spec_cpu2006       1034   0.016690
   spec_cpu2017       1584   0.019901
         [+]All       8474   1.917495
```

Finally, to measure jump table entries overhead, run:
```
$ python3 4_get_table_size.py ./benchmark ./output
$ python3 4_print_table_overhead.py

Table-------------
  coreutils-9.1       5136   0.097256
  binutils-2.40        720   0.114545
   spec_cpu2006       1034   0.085990
   spec_cpu2017       1592   0.097313
         [+]All       8482   0.097361

```


### Comparison against SOTA Reassemblers

:alarm_clock: 2.5 days

To accurately measure runtime overhead, we run one test suite instance at a
time. Running multiple test suites simultaneously may interfere with time
measurements, as the SPEC benchmark test suite is highly sensitive.

To measure runtime overhead, execute the following commands:

```
$ python3 4_get_runtime_overhead.py setA | tee 2_runtime_overheadA.sh
$ /bin/bash 2_runtime_overheadA.sh

$ python3 4_get_runtime_overhead.py setB | tee 2_runtime_overheadB.sh
$ /bin/bash 2_runtime_overheadB.sh

```

After running the above commands, you can analyze the results using
`2_print_runtime_overhead.py`:

```
$ python3 4_print_runtime_overhead.py setA
                     |      suri   ddisasm
spec_cpu2006      24 | 0.329513% 0.321086%
spec_cpu2017      21 | 0.188620% 0.319419%

$ python3 4_print_runtime_overhead.py setB
                     |     suri    egalito
spec_cpu2006      24 | 0.457050% 0.694204%
spec_cpu2017      21 | 0.167273% 0.037466%

```

These results correspond to Table 4 in our paper.

## Exp5: Application of SURI (Section 4.4)

:alarm_clock: 5 days

In this experiment, we implement our own binary-only address sanitizer on top of SURI and compare to BASan, a binary-only address sanitizer on top of RetroWrite.

To set up Juliet testsuite:
```
$ cd ./application
$ wget https://samate.nist.gov/SARD/downloads/test-suites/2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip
$ unzip  2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip
```

To build Juliet testsuite binaries, run the following commands:
```
$ python3 build_original.py
$ python3 build_asan.py
```

Rewrite original Juliet testsuite binaries with SURI and RetroWrite.
```
$ python3 build_suri.py
$ python3 build_retrowrite.py
```

To run juliet testsuit binaries, execute the following commands:
```
$ python3 run_juliet.py original    --core $(nproc)
$ python3 run_juliet.py suri        --core $(nproc)
$ python3 run_juliet.py asan        --core $(nproc)
$ python3 run_juliet.py retrowrite  --core $(nproc)
```

The `summary.py` script prints the results from both our binary-only address sanatizer, BASan, and ASan.
```
$ python3 summary.py
                      Ours      BASan       ASan
  True Positive      10233       9552      13378
 False Positive          0          8          0
 False Negative       5528       6209       2383
  True Negative        577        569        577
-------------------------------------------------
 Total Binaries      16338      16338      16338
```

These results correspond to Table 5 in our paper.

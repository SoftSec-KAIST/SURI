# SURI: Towards Sound Reassembly of Modern x86-64 Binaries

This artifact is intended to reproduce the experimental results presented in
our paper, "Towards Sound Reassembly of Modern x86-64 Binaries", published at
ASPLOS '25. It provides (1) the source code of SURI, (2) scripts for running
experiments, and (3) datasets we used.

## Preperation

This artifact can be downloaded from [Zenodo](https://zenodo.org/records/14770657).
It contains both all codes and data necessary for the artifact evaluation.
You can also access our source code through the [GitHub](https://github.com/SoftSec-KAIST/SURI) repository.

:warning: We exclude SPEC benchmark binaries from our dataset because they are
proprietary. See [2.4 Docker Images with SPEC CPU](#24-docker-images-with-spec-cpu)
and [3.1 Build SPEC CPU Benchmark Binaries](#31-build-spec-cpu-benchmark-binaries)
for more details.

### 1 Download the Artifact

(1) From Zenodo:
```
wget FIXME/src.zip // FIX the filename
wget https://zenodo.org/records/14770657/files/dataset.zip
unzip src.zip // FIX the filename
unzip dataset.zip
cd src/
mv ../dataset/ .
```

(2) From GitHub:
```
$ git clone https://github.com/SoftSec-KAIST/SURI.git
$ cd SURI
$ wget https://zenodo.org/records/14770657/files/dataset.zip
$ unzip dataset.zip
```
FIXME above with the right command to download dataset

### 2 Build Docker Images

We provide Docker images for easy reproduction of our experimental results. Here,
we explain how to build Docker images for running SURI, Ddisasm, and Egalito, and
additional Docker images for running SPEC CPU benchmark test suites.

### 2.1 Docker Image for SURI

This image sets up the execution environment based on Ubuntu 20.04 for running
SURI. To build this image, run this command at the top-level directory:
```
$ docker build --tag suri:v1.0 .
```

### 2.2 Docker Image for Ddisasm

For Ddisasm, we used the official Docker image provided by GrammaTech. This
image is also based on Ubuntu 20.04. To ensure reproducibility, we uploaded
the exact version used in our experiments to Docker Hub. You can download it
using this command:
```
$ docker pull reassessor/ddisasm:1.7.0_time
```

### 2.3 Docker Image for Egalito

Unfortunately, Egalito could not run with binaries compiled on Ubuntu 20.04.
Thus, we provide an additional environment based on Ubuntu 18.04 for a fair
comparison. This image includes SURI, Egalito, and RetroWrite. The Dockerfile
for this image is located in the `./ubuntu18.04` directory. To build this
image, run these commands at the top-level directory:
```
$ cd ./ubuntu18.04
$ docker build --tag suri_ubuntu18.04:v1.0 .
```

### 2.4 Docker Images with SPEC CPU

If you have your own SPEC CPU benchmark, then you need to build additional
Docker images for our reliability test experiment on SPEC CPU benchmarks (see [here](#122-spec-benchmark)).

We assume that the SPEC CPU2006 image is unzipped under `./build_script/test_suite_script/spec2006_image` and
SPEC CPU 2017 image is unzipped under `./build_script/test_suite_script/spec2017_image`.
If the locations of SPEC benchmarks differ, then you need to manually update the paths
in line 3 and line 15 of the Dockerfiles at `./build_script/test_suite_script/Dockerfile` and
`./build_script/test_suite_script_ubuntu18.04/Dockerfile` accordingly.

Then, build the suri_spec:v1.0 image using the following command at the top-level directory:
```
$ cd ./build_script/test_suite_script/
$ docker build -tag suri_spec:v1.0 .
```

To build the one for the ubuntu 18.04 image, run the following command at the top-level directory:
```
$ cd ./build_script/test_suite_script_ubuntu18.04/
$ docker build -tag suri_ubuntu18.04_spec:v1.0 .
```

### 3 Prepare Dataset

Our dataset used for our evaluation consists of Coreutils v9.1, Binutils v2.40,
SPEC CPU 2006 (v1.1) and SPEC CPU 2017 (v1.1). We provide the dataset (including
binaries and ground truths) for Coreutils and Binutils through Zenodo (see
[1. Download the Artifact](#1-download-the-artifact)). However, due to licensing
restrictions, we are not able to distribute SPEC CPU benchmark binaries. Instead,
we provide scripts to allow users to build those binaries themselves.

Note that you can still run our artifact **without** SPEC CPU benchmark binaries.
Our experiment scripts will show the results on Coreutils and Binutils benchmarks
only if you do not have SPEC CPU benchmark.

### 3.1 Build SPEC CPU Benchmark Binaries

If you have a valid license for SPEC CPU, you can generate the benchmark
binaries by following these steps.

Assuming the SPEC CPU2006 image is unzipped under `/path/to/spec_cpu2006`, you can
build the benchmark binaries by running the following commands:
```
$ ls /path/to/spec_cpu2006
Docs         MANIFEST    benchspec  install.bat              result    uninstall.sh
Docs.txt     README      bin        install.sh               shrc      version.txt
LICENSE      README.txt  config     install_archives         shrc.bat
LICENSE.txt  Revisions   cshrc      redistributable_sources  tools

$ cd build_script
$ python3 build_spec2006.py /path/to/spec_cpu2006
[+] ...
```
The `build_spec2006.py` script compiles the SPEC benchmark binaries with
48 different options. The process takes approximately 20–40 minutes per set of
benchmark binaries. Thus, generating all combinations will take about one day.

You can do the similar process for the SPEC CPU2017:
```
$ ls /path/to/spec_cpu2017
Docs         PTDaemon    bin          install.sh               shrc      uninstall.sh
LICENSE.txt  README.txt  cshrc        install_archives         shrc.bat  version.txt
MANIFEST     Revisions   install.bat  redistributable_sources  tools

$ cd build_script
$ python3 build_spec2017.py /path/to/spec_cpu2017
[+] ...
```
This process takes approximately 30–50 minutes per set of benchmark binaries.
Thus, generating all combinations will take about 1.5 days.

If all build processes are done, the benchmark binaries are built under `dataset/...` (FIXME).

### 3.2 Generate Ground Truth

Once SPEC CPU benchmark binaries are built, you need to generate ground truth for
measuring the instrumentation code size overhead of SURI (see [2.1 Overhead Incurred by SURI (Section 4.3.1)](#21-overhead-incurred-by-suri-section-431)).
We used Reassessor [1] to generate the ground truth from the binaries. You can
install Reassessor using the provided an install script included in this artifact:
```
$ /bin/bash ./install.sh
```

After Reassessor is installed, you can generate ground truth from our dataset
using these commands (see [Run Experiments](#run-experiments) if you want to know what setA and setC are):
```
$ python3 make_gt.py setA
$ python3 make_gt.py setC
```

## Usage

```
python3 suri.py [target binary]
```

```
python3 suri.py realworld/client/vim
[*] All done in 27.285196 sec.
[*] Construct CFG 4.193936 sec.
[*] Extract data 0.004162 sec.
[*] JsonSerializer 1.452532 sec.
[+] Generate rewritten binary: my_vim
...


SURI generates rewrite binary which starts with 'my_'
```
$ ls -al my_vim
-rwxrwxr-x 1 test test 7608639 Jan 31 18:46 my_vim
```


## Run Experiments

We have three different sets of benchmark binaries because we have different running
environments for our comparison targets, Ddisasm and Egalito (see [2 Build Docker Images](#2-build-docker-images)).

To easily distinguish between different benchmark binary sets, we define the
following categories:

- setA: Binaries compiled on Ubuntu 20.04 (SURI vs. Ddisasm).
- setB: Binaries compiled on Ubuntu 18.04 (SURI vs. Egalito).
- setC: Binaries compiled on Ubuntu 20.04 without call frame information (see Section 4.3.3 of the paper).

Note 1: setB excludes C++ binaries because Egalito cannot handle binaries
written in C++ language.

Note 2: We used a machine with an Intel Core i9-11900K processor and
128GB of RAM when we ran experiments. Thus, it will take more or less time
depending on your computing machine.

Note 3: Our scripts automatically detect whether SPEC binaries are included in the dataset or not,
and show the results accordingly unless commands are separated between SPEC binaries and others.

### 1 Reliability Comparison (Section 4.2)

This experiment answers **RQ1**: How well does SURI compare to the state-of-the-art reassembly tools in terms of reliability?
We rewrite binaries using SURI and other comparison targets and see if the binary rewriting is successful and the rewritten binaries can pass the test suites.

### 1.1 Rewriting Completion Comparison against Ddisasm and Egalito (Section 4.2.1 and 4.2.2)

:alarm_clock: 28 hrs on Coreutils and Binutils, 10 days on full dataset

To rewrite the binaries in each dataset, use the `1_get_reassembled_code.py`
script provided in the artifact.

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

Once rewriting is complete, you can check the success rate and execution time
using the following script. Then the results for Table 2 and 3 of our paper are shown
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

### 1.2 Testsuite Pass Rate Comparison against Ddisasm and Egalito (Section 4.2.1 and 4.2.2)

After completion of the previous experiment, collect the binaries for the
reliability testing using the `make_set.py` script. This will create setA,
setB, and setC folders in the project directory.
```
$ python3 make_set.py setA
$ python3 make_set.py setB
$ python3 make_set.py setC
```

#### 1.2.1 Coreutils and Binutils Tests

:alarm_clock: 15 hrs, 3-5 mins per each test suite

To verify the reliability of the rewritten binaries, run the test suites for
Coreutils and Binutils.

Run the test suite for setA (SURI vs. Ddisasm):
```
$ python3 1_run_testsuite.py setA
...
                                          suri                Ddiasm
coreutils-9.1   (clang):       Succ(  24/  24)       Succ(  24/  24)
coreutils-9.1   (gcc  ):       Succ(  24/  24)       Fail(  14/  24)
binutils-2.40   (clang):       Succ(  24/  24)       Succ(  24/  24)
binutils-2.40   (gcc  ):       Succ(  24/  24)       Fail(   7/  24)
```

Run the test suite for setB (SURI vs. Egalito):
```
$ python3 1_run_testsuite.py setB
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

Finally, test setC:
```
$ python3 1_run_testsuite.py setC
...
                              suri(no_ehframe)
coreutils-9.1   (clang):       Succ(  24/  24)
coreutils-9.1   (gcc  ):       Succ(  24/  24)
binutils-2.40   (clang):       Succ(  24/  24)
binutils-2.40   (gcc  ):       Succ(  24/  24)

```

#### 1.2.2 SPEC Benchmark

:alarm_clock: 7-10 days

If you have your own SPEC benchmarks and you have built updated Docker images
(See 1.1.4), then you can run the SPEC benchmark test suites. Execute the test
suite using the `1_run_testsuite_spec.py' script. After running the script, the
results will be displayed.

If you restart the script, it will skip previously completed tests and continue
from the next test suite.

```
$ python3 1_run_testsuite_spec.py setA
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

$ python3 1_run_testsuite_spec.py setB
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

$ python3 1_run_testsuite_spec.py setC
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
$ python3 1_run_testsuite_spec.py setA --core 4
```

These results correspond to Table 2 and 3 in our paper.

### 2 Overhead of Rewritten Binaries (Section 4.3)

This experiment answers **RQ2**: How big is the performance overhead introduced by SURI for rewritten binaries?

### 2.1 Overhead Incurred by SURI (Section 4.3.1)

In this experiment, we measured the instrumentation overhead of the binaries
rewritten by SURI, as explained in Section 4.3.1 of the paper.

To measure code size overhead, execute the following scripts:
```
$ python3 2_get_code_size.py setA
$ python3 2_print_code_size_overhead.py setA

  coreutils-9.1       5180   2.691429
  binutils-2.40        720   0.598323
   spec_cpu2006       1446   4.737552
   spec_cpu2017       2254   2.311999
-----------------------------------------------
         [+]All       9600   2.753556

```

To analyze the overhead of if-then-else statements, run:
```
$ python3 2_get_br_stat.py ./benchmark ./output
$ python3 2_print_br_overhead.py setA

Multi Br-------------
  coreutils-9.1       5136   0.020213
  binutils-2.40        720   0.013744
   spec_cpu2006       1034   0.016690
   spec_cpu2017       1584   0.019901
         [+]All       8474   1.917495
```

Finally, to measure jump table entries overhead, run:
```
$ python3 2_get_table_size.py ./benchmark ./output
$ python3 2_print_table_overhead.py

Table-------------
  coreutils-9.1       5136   0.097256
  binutils-2.40        720   0.114545
   spec_cpu2006       1034   0.085990
   spec_cpu2017       1592   0.097313
         [+]All       8482   0.097361

```


### 2.2 Comparison against SOTA Reassemblers (Section 4.3.2)

:alarm_clock: 2.5 days

To accurately measure runtime overhead, we run one test suite instance at a
time. Running multiple test suites simultaneously may interfere with time
measurements, as the SPEC benchmark test suite is highly sensitive.

To measure runtime overhead, execute the following commands:

```
$ python3 2_get_runtime_overhead.py setA | tee 2_runtime_overheadA.sh
$ /bin/bash 2_runtime_overheadA.sh

$ python3 2_get_runtime_overhead.py setB | tee 2_runtime_overheadB.sh
$ /bin/bash 2_runtime_overheadB.sh

```

After running the above commands, you can analyze the results using
`2_print_runtime_overhead.py`:

```
$ python3 2_print_runtime_overhead.py setA
                     |      suri   ddisasm
spec_cpu2006      24 | 0.329513% 0.321086%
spec_cpu2017      21 | 0.188620% 0.319419%

$ python3 2_print_runtime_overhead.py setB
                     |     suri    egalito
spec_cpu2006      24 | 0.457050% 0.694204%
spec_cpu2017      21 | 0.167273% 0.037466%

```

These results correspond to Table 4 in our paper.

### 3 Application of SURI (Section 4.4)

This experiment answers **RQ3**: Is SURI applicable to real-world scenarios, such as runtime memory sanitization?
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
$ python3 run_juliet.py original
$ python3 run_juliet.py suri
$ python3 run_juliet.py asan
$ python3 run_juliet.py retrowrite
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

## References

[1] Hyungseok Kim, Soomin Kim, Junoh Lee, Kangkook Jee, and Sang Kil Cha,
    "Reassembly is Hard: A Reflection on Challenges and Strategies," USENIX
    Security Symposium 2023, 1469-1486

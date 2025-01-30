# suri_artifact

This artifact is designed to reproduce the results presented in our paper,
"Towards Sound Reassembly of Modern x86-64 Binaries." We provide all benchmark
binaries, except for the SPEC binaries, which are proprietary software.
Instead, we include build scripts to allow users to generate the binaries
themselves. Please refer to Section 1.3 for details.

## 1. Preperation

The artifact can be downloaded through the [GitHub](https://github.com/witbring/suri_artifact.git) repository.
Additionally, the dataset (dataset.zip) used for the artifact can be downloaded
from [Zenodo](https://zenodo.org/records/14770657).

- Artifact URL: https://github.com/witbring/suri_artifact.git
- Dataset URL: https://zenodo.org/records/14770657

```
$ git clone https://github.com/witbring/suri_artifact.git
$ cd suri_artifact
$ unzip /path/to/dataset.zip
```


### 1.1 Create Docker Images

Binary rewriting and test suite execution are configured to run within Docker
images. Before running the experiments, you need to build the necessary Docker
images. Since our experiments were conducted on both Ubuntu 20.04 and Ubuntu
18.04, you should build separate Docker images for each environment.

First, use the `Dockerfile` in the project folder to set up the Ubuntu 20.04
execution environment:

```
$ docker build --tag suri:v1.0 .
```

Next, to conduct experiments on Ubuntu 18.04, build the Docker image located in
the ./ubuntu18.04 folder. This image includes both the Egalito and RetroWrite
tools.

```
$ cd ./ubuntu18.04
$ docker build --tag suri_ubuntu18.04:v1.0 .
```

For Ddisasm, we used the official Docker image provided by GrammaTech. To
ensure reproducibility, we have uploaded the exact version used in our
experiments to Docker Hub. You can download it as follows:

```
$ docker push reassessor/ddisasm:1.7.0_time
```

### 1.2 Install Additional Package

To measure the overhead of SURI, as described in Section 4.3.1 of our paper, we
used Reassessor [1] to extract the ground truth of target binaries.  You need
to install Reassessor before proceeding. You can install it using the provided
Reassessor project included in this artifact:

```
$ cd ./Reassessor
$ pip3 install -r requirements.txt
$ python3 setup.py install --user
```

### 1.3 Build Benchmark binaries.

In our paper, we evaluated the reliability and overhead of rewritten binaries
using SPEC CPU2006 v1.2 and SPEC CPU2017 v1.1.5. However, due to licensing
restrictions, these benchmarks are not included in this artifact. Instead, we
provide scripts to allow users to build the benchmarks themselves.

If you have a valid license for SPEC CPU, you can generate the benchmark
binaries by following these steps.

First, if the SPEC CPU2006 image is located in /path/to/spec_cpu2006, you can
generate the benchmark binaries by running the build_spec2006.sh script from
the build_script folder. This script compiles the SPEC benchmark binaries with
48 different options. The process takes approximately 20–40 minutes per set of
benchmark binaries. Thus, generating all combinations will take about one day.


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

Similarly, you can use the build_spec2017.sh script in the build_script folder
to generate SPEC CPU2017 benchmark binaries. This process takes approximately
30–50 minutes per set of benchmark binaries. Thus, generating all combinations
will take about 1.5 day.

```
$ ls /path/to/spec_cpu2017
Docs         PTDaemon    bin          install.sh               shrc      uninstall.sh
LICENSE.txt  README.txt  cshrc        install_archives         shrc.bat  version.txt
MANIFEST     Revisions   install.bat  redistributable_sources  tools

$ cd build_script
$ python3 build_spec2017.py /path/to/spec_cpu2017
[+] ...
```

## 2. Rewrite Benchmark

In our experiments, we compared SURI with Ddisasm and Egalito. However, since
Egalito could not correctly process binaries compiled on Ubuntu 20.04, we
conducted a separate experiment on Ubuntu 18.04.

To easily distinguish between different benchmark binary sets, we define the
following categories:

- setA: Binaries compiled on Ubuntu 20.04.
- setB: Binaries compiled on Ubuntu 18.04, excluding C++ binaries for a fair comparison with Egalito.
- setC: Binaries compiled on Ubuntu 20.04 with call frame information manually disabled (see Section 4.3.3 of the paper).

### 2.1 Rewrite binaries

For the rewriting experiments, we used a machine with an Intel Core i9-11900K
processor and 128GB of RAM.

To rewrite the binaries in each dataset, use the `1_get_reassembled_code.py`
script provided in the artifact.

For setA, rewrite the binaries using SURI and Ddisasm:

```
$ python3 1_get_reassembled_code.py setA
```

If you want to process multiple binaries in parallel, you can use the `--core`
option. However, note that this may affect the rewriting time measurements.

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

Rewriting the provided Coreutils and Binutils binaries takes approximately 28
hours. If you include all 9,600 binaries from the SPEC benchmark set, the
process takes about 10 days.

Once rewriting is complete, you can check the success rate and execution time
using the following script. The results are used for Table 2 and Table 3 in the
paper.

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

### 2.2 Reliability Test

After rewriting, collect the binaries for testing using the `2_make_set.py`
script. This will create setA, setB, and setC folders in the project directory.

```
$ python3 2_make_set.py setA
$ python3 2_make_set.py setB
$ python3 2_make_set.py setC
```


### 2.2.1 Coreutils and Binutils Tests

To verify the reliability of the rewritten binaries, run the test suites for
Coreutils and Binutils. Use the `suri:v1.0` and `suri_ubuntu:v1.0` Docker images
created in Section 1.1.


Each test suite takes approximately 3–5 minutes, and the full test set takes
about 15 hours.

Run the test suite for setA (SURI vs. Ddisasm):
```
$ python3 3_run_testsuite.py setA
...
                                          suri                Ddiasm
coreutils-9.1   (clang):       Succ(  24/  24)       Succ(  24/  24)
coreutils-9.1   (gcc  ):       Succ(  24/  24)       Fail(  14/  24)
binutils-2.40   (clang):       Succ(  24/  24)       Succ(  24/  24)
binutils-2.40   (gcc  ):       Succ(  24/  24)       Fail(   7/  24)
```

Run the test suite for setB (SURI vs. Egalito):
```
$ python3 3_run_testsuite.py setB
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
$ /bin/bash 3_terminate_suri_docker.sh
```

Finally, test setC:
```
$ python3 3_run_testsuite.py setC
...
                              suri(no_ehframe)
coreutils-9.1   (clang):       Succ(  24/  24)
coreutils-9.1   (gcc  ):       Succ(  24/  24)
binutils-2.40   (clang):       Succ(  24/  24)
binutils-2.40   (gcc  ):       Succ(  24/  24)

```

### 2.2.2 SPEC Benchmark

To run the SPEC benchmark tests, additional Docker images are required.

First, modify the `Dockerfile` in `./build_script/test_suite_script/` to include
the correct paths for the SPEC CPU2006 and SPEC CPU2017 installation files:

Specifically, `Dockerfile` assumes that the SPEC CPU2006 and SPEC CPU2017 installation
files are located in the `./build_script/test_suite_script/spec2006_image` and
`./build_script/test_suite_script/spec2017_image` folders.

If the folder names are different, update the paths in line 3 and line 15 of
the Dockerfile accordingly.

```
$ cat ./build_script/test_suite_script/Dockerfile -n
     1	FROM suri:v1.0
     2
     3	COPY ./spec2006_image /spec_cpu2006
    ...
    15	COPY ./spec2017_image /spec_cpu2017
    ...
```

Then, build the suri_spec:v1.0 image using the following command:
```
$ cd ./build_script/test_suite_script/
$ docker build -tag suri_spec:v1.0 .
```

For setB, modify the `Dockerfile` in ./build_script/test_suite_script_ubuntu18.04/ and build the image:

```
$ cat ./build_script/test_suite_script_ubuntu18.04/Dockerfile -n
     1	FROM suri_ubuntu18.04:v1.0
     2
     3	COPY ./spec2006_image /spec_cpu2006
    ...
    15	COPY ./spec2017_image /spec_cpu2017
    ...

$ cd ./build_script/test_suite_script_ubuntu18.04/
$ docker build -tag suri_ubuntu18.04_spec:v1.0 .
```

Now, you are ready to run the SPEC benchmark test suite.  Execute the test
suite using the `3_run_testsuite_spec.py' script After running the script, the
results will be displayed. Completing all test suites for each set typically
takes 7 to 10 days.

If you restart the script, it will skip previously completed tests and continue
from the next test suite.

```
$ python3 3_run_testsuite_spec.py setA
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

$ python3 3_run_testsuite_spec.py setB
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

$ python3 3_run_testsuite_spec.py setC
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
$ python3 3_run_testsuite_spec.py setA --core 4
```


### 2.3 Runtime Overhead

To accurately measure runtime overhead, we run one test suite instance at a
time. Running multiple test suites simultaneously may interfere with time
measurements, as the SPEC benchmark test suite is highly sensitive.

We estimate that each set takes approximately 2.5 days to complete.

To measure runtime overhead, execute the following commands:

```
$ python3 4_get_runtime_overhead.py setA | tee 4_runtime_overheadA.sh
$ /bin/bash 4_runtime_overheadA.sh

$ python3 4_get_runtime_overhead.py setB | tee 4_runtime_overheadB.sh
$ /bin/bash 4_runtime_overheadB.sh

```

After running the above commands, you can analyze the results using
`4_print_runtime_overhead.py`:

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

These results correspond to Table 4 in the paper.


### 2.4 SURI Overhead

In this experiment, we measured the instrumentation overhead of the binaries
rewritten by SURI, as introduced in Section 4.3.1 of the paper.


If you generate additional SPEC benchmark binaries, use the following script to
update the ground truth:

```
$ python3 5_make_gt.py setA
$ python3 5_make_gt.py setC
```


To measure code size overhead, execute the following scripts:
```
$ python3 5_get_code_size.py setA
$ python3 5_print_code_size_overhead.py setA

  coreutils-9.1       5180   2.691429
  binutils-2.40        720   0.598323
   spec_cpu2006       1446   4.737552
   spec_cpu2017       2254   2.311999
-----------------------------------------------
         [+]All       9600   2.753556

```

To analyze the overhead of if-then-else statements, run:
```
$ python3 5_get_br_stat.py ./benchmark ./output
$ python3 5_print_br_overhead.py setA

Multi Br-------------
  coreutils-9.1       5136   0.020213
  binutils-2.40        720   0.013744
   spec_cpu2006       1034   0.016690
   spec_cpu2017       1584   0.019901
         [+]All       8474   1.917495
```

Finally, to measure jump table entries overhead, run:
```
$ python3 5_get_table_size.py ./benchmark ./output
$ python3 5_print_table_overhead.py

Table-------------
  coreutils-9.1       5136   0.097256
  binutils-2.40        720   0.114545
   spec_cpu2006       1034   0.085990
   spec_cpu2017       1592   0.097313
         [+]All       8482   0.097361

```


### References

[1] Hyungseok Kim, Soomin Kim, Junoh Lee, Kangkook Jee, and Sang Kil Cha,
    "Reassembly is Hard: A Reflection on Challenges and Strategies," USENIX
    Security Symposium 2023, 1469-1486

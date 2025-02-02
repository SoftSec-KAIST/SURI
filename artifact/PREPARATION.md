# Preperation

This artifact can be downloaded from
[Zenodo](https://zenodo.org/records/14788616), It contains both all codes and
data necessary for the artifact evaluation.  You can also access our source
code through the [GitHub](https://github.com/SoftSec-KAIST/SURI) repository.

### 1. Download the Artifact

(1) From Zenodo:
```
$ wget https://zenodo.org/records/14788616/files/SURI.zip
$ unzip SURI.zip
$ cd ./SURI/artifact
$ export SURI_AE_HOME=$(pwd) # set up an environment variable to avoid confusion
$ wget https://zenodo.org/records/14788616/files/dataset.zip
$ unzip dataset.zip
```

(2) From GitHub:
```
$ git clone https://github.com/SoftSec-KAIST/SURI.git
$ cd ./SURI/artifact
$ export SURI_AE_HOME=$(pwd) # set up an environment variable to avoid confusion
$ wget https://zenodo.org/records/14788616/files/dataset.zip
$ unzip dataset.zip
```

### 2. Build Docker Images

We provide Docker images for easy reproduction of our experimental results. Here,
we explain how to build Docker images for running SURI, Ddisasm, and Egalito, and
additional Docker images for running SPEC CPU benchmark test suites.

### 2.1. Docker Image for SURI

This image sets up the execution environment based on Ubuntu 20.04 for running
SURI. To build the image, you first need to build the SURI Docker image (see
[here](../README.md#docker-environment)).
Then, run these commands:
```
$ cd $SURI_AE_HOME
$ docker build --tag suri_artifact:v1.0 .
```

### 2.2. Docker Image for Ddisasm

For Ddisasm, we used the official Docker image provided by GrammaTech. This
image is also based on Ubuntu 20.04. To ensure reproducibility, we uploaded
the exact version used in our experiments to Docker Hub. You can download it
using this command:
```
$ docker pull reassessor/ddisasm:1.7.0_time
```

### 2.3. Docker Image for Egalito

Unfortunately, Egalito could not run with binaries compiled on Ubuntu 20.04.
Thus, we provide an additional environment based on Ubuntu 18.04 for a fair
comparison. This image includes SURI, Egalito, and RetroWrite. The Dockerfile
for this image is located in the `$SURI_AE_HOME/ubuntu18.04` directory. To build this
image, run these commands at the top-level directory:
```
$ cd $SURI_AE_HOME/ubuntu18.04
$ docker build --tag suri_artifact_ubuntu18.04:v1.0 .
```

### 2.4. Docker Images with SPEC CPU

If you have your own SPEC CPU benchmark, then you need to build additional Docker images for running SPEC CPU test suites for Exp2.

We assume that the SPEC CPU2006 image is unzipped under `$SURI_AE_HOME/build_script/test_suite_script/spec2006_image` and
SPEC CPU 2017 image is unzipped under `$SURI_AE_HOMEbuild_script/test_suite_script/spec2017_image`.
If the locations of SPEC benchmarks differ, then you need to manually update the paths
in line 3 and line 15 of the Dockerfiles at `$SURI_AE_HOME/build_script/test_suite_script/Dockerfile` and
`$SURI_AE_HOME/build_script/test_suite_script_ubuntu18.04/Dockerfile` accordingly.

Then, build the suri_spec:v1.0 image using the following command at the top-level directory:
```
$ cd $SURI_AE_HOME/build_script/test_suite_script/
$ docker build -tag suri_spec:v1.0 .
```

To build the one for the ubuntu 18.04 image, run the following command at the top-level directory:
```
$ cd $SURI_AE_HOME/build_script/test_suite_script_ubuntu18.04/
$ docker build -tag suri_ubuntu18.04_spec:v1.0 .
```

### 3. Prepare Dataset

This section describes building SPEC CPU benchmark binaries only. For other kinds of binaries, they are already provided through Zenodo.

Note that you can still run our artifact **without** SPEC CPU benchmark binaries.
Our experiment scripts will show the results on Coreutils and Binutils benchmarks
only if you do not have SPEC CPU benchmark.

### 3.1. Build SPEC CPU Benchmark Binaries

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

$ cd $SURI_AE_HOME/build_script
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

$ cd $SURI_AE_HOME/build_script
$ python3 build_spec2017.py /path/to/spec_cpu2017
[+] ...
```
This process takes approximately 30–50 minutes per set of benchmark binaries.
Thus, generating all combinations will take about 1.5 days.

If all build processes are done, the benchmark binaries are built under `$SURI_AE_HOME/benchmark/...`

### 3.2. Generate Ground Truth

Once SPEC CPU benchmark binaries are built, you need to generate ground truth for Exp4.
We used [Reassessor](https://github.com/SoftSec-KAIST/Reassessor) to generate the ground truth from the binaries. You can
install Reassessor using the provided an install script included in this artifact:
```
$ cd $SURI_AE_HOME
$ /bin/bash ./install.sh
```

After Reassessor is installed, you can generate ground truth from our dataset using these commands:
```
$ cd $SURI_AE_HOME
$ python3 make_gt.py setA
$ python3 make_gt.py setC
```

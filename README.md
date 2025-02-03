# SURI: Towards Sound Reassembly of Modern x86-64 Binaries

SURI is a binary reassembler for CET- and PIE-enabled x86-64 binaries. For a
detailed technical description, please refer to our paper "Towards Sound
Reassembly of Modern x86-64 Binaries", which will be published in the ACM
International Conference on Architectural Support for Programming Languages and
Operating Systems (ASPLOS) 2025.

If you are interested in our artifact, visit [here](artifact/README.md)

## Dependencies

SURI requires the following software dependencies:

- .NET 7.0
- Python 3 (with pip)
- gcc-11

.NET is necessary for our Superset CFG Builder, which is based on
[B2R2](https://github.com/B2R2-org/B2R2). All other components of SURI are
written in Python 3. Lastly, our reassembler internally uses `gcc-11` for the
reassembly process.

If you have installed Python 3, you need to install
[pyelftools](https://github.com/eliben/pyelftools) using the following command:
```
$ pip install pyelftools
```


## Install SURI

You need to build our Superset CFG Builder and install SURI Python project in order to use SURI.
Try:
```
$ python3 setup.py install --user # install SURI Python project
$ cd superCFGBuilder
$ dotnet build # build Superset CFG Builder
```

### Docker environment

We also provide Docker environment in case you don't want to struggle to set up
the software dependencies. You still need to install SURI python project though.
Type this on your shell:
```
$ python3 setup.py install --user # install SURI Python project
$ docker build --tag suri:v1.0 . # build Docker image for .NET and gcc-11
```

Note that you still need Python 3 because the top-level SURI script runs on
outside of the Docker image.


## Usage

If you want to reassemble a target binary, use following command;
```
$ python3 suri.py [target_binary_path]
```

For example, to rewrite the 7zip binary located at artifact/realworld/phoronix/7zip, run SURI as follows:
```
$ python3 suri.py artifact/realworld/phoronix/7zip
[*] All done in 26.445190 sec.
[*] Construct CFG 3.714226 sec.
[*] Extract data 0.003845 sec.
[*] JsonSerializer 1.575038 sec.
[+] Generate assembly file: 7zip.s
[+] Generate rewritten binary: /test/SURI/my_7zip
```

SURI generates a reassembled binary.
```
$ ls -al my_7zip
-rw-rw-r-- 1 test  test 7428218  Jan  2 14:22 my_7zip
```

#### Running SURI in a Docker environment

If you want to use the Docker environment, you need to pass the `--usedocker` flag to SURI.
```
python3 suri.py [target binary path] --usedocker
```

This will make that Superset CFG Builder and compiler for reassembly run inside the provided Docker image.

### Two-step SURI execution

If you want to manually instrument the assembly file from the target binary, follow the steps below.

#### 1. Generating assembly code using SURI

If you want to generate the assembly file without compiling it, use the `--without-compile` option:
```
python3 suri.py [target binary path] [--without-compile]
```

For example,
```
$ python3 suri.py artifact/realworld/phoronix/7zip --without-compile
[*] All done in 26.201983 sec.
[*] Construct CFG 3.704804 sec.
[*] Extract data 0.003851 sec.
[*] JsonSerializer 1.571691 sec.
[+] Generate assembly file: 7zip.s
```

SURI will generate an assembly file with the `.s` extension:
```
$ ls -al 7zip.s
-rw-rw-r-- 1 test  test 43578474 Jan  2 14:22 7zip.s
```
You can modify the assembly code for instrumentation if necessary.

#### 2. Compiling the assembly file

After editing the assembly file, you can compile the assembly file using `emitter.py` script:
```
$ python3 emitter.py artifact/realworld/phoronix/7zip 7zip.s
[+] Generate rewritten binary: /test/SURI/my_7zip
```

## Application

### Binary Only Address Sanitizer
If you want to enable the AddressSanitizer feature in the target binary, 
use the `--asan` option. This will generate a binary with memory sanitizing 
code inserted.
```
python3 suri.py [target_binary_path] --asan
```

For example,
```
$ python3 suri.py artifact/realworld/phoronix/7zip --asan
...
[+] Generate rewritten binary: /test/SURI/my_7zip
```

## Directory Structure

This tree shows some important files and directories only.

```
.
├── artifact/                   : contains files related to the artifact evaluation
├── superCFGBuilder/            : contains our Superset CFG Builder module
├── superSymbolizer/
│   ├── lib/
│   │   └── CFGSerializer.py    : contains our CFG Serializer module
│   ├── CustomCompiler.py.py    : contains our Emitter module
│   └── SuperSymbolizer.py      : contains our Pointer Repairer and Superset Symbolizer modules
├── README.md                   : this document
└── suri.py                     : the main entry point of SURI
└── emitter.py                  : a script for compiling assembly file
```

## Citation

If you want to cite SURI:
```
T.B.D.
```

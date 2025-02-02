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


## Build SURI

You need to build our Superset CFG Builder in order to use SURI. You can simply
build it by:
```
$ cd superCFGBuilder
$ dotnet build
```

### Docker environment

We also provide Docker environment in case you don't want to struggle to set up
the software dependencies. Type this on your shell:
```
$ docker build --tag suri:v1.0 .
```

Note that you still need Python 3 because the top-level SURI script runs on
outside of the Docker image.


## Usage

### Generating Assembly Code Using SURI

To generate a assembly code using SURI, provide the target binary path as an argument:

```
python3 suri.py [target binary path] [--usedocker]
```

For example, to create an assembly file for the vim binary located at realworld/client/vim, run SURI as follows:

```
$ python3 suri.py artifact/realworld/client/vim
[*] All done in 27.285196 sec.
[*] Construct CFG 4.193936 sec.
[*] Extract data 0.004162 sec.
[*] JsonSerializer 1.452532 sec.
[+] Generate assembly file: vim.s
```

SURI generates an assembly file with the `.s` extension:
```
$ ls -al vim.s
-rw-rw-r-- 1 test  test 41286215 Jan  2 14:22 vim.s
```

You can modify the assembly code for instrumentation if needed.

### Compiling the Assembly File

After editing, you can compile the assembly file using `emitter.py` script:

```
python3 emitter.py artifact/realworld/client/vim vim.s
[+] Generate rewritten binary: /test/my_vim
```

### Generating and Compiling in One Step

If you want to generate the assembly file and compile it in a single step, use the `--with-compile` option:

```
python3 suri.py [target binary path] [--with-compile]
```

For example,
```
$ python3 suri.py artifact/realworld/client/vim
[*] All done in 27.285196 sec.
[*] Construct CFG 4.193936 sec.
[*] Extract data 0.004162 sec.
[*] JsonSerializer 1.452532 sec.
[+] Generate assembly file: vim.s
[+] Generate rewritten binary: /test/my_vim
```

Running this command will generate both vim.s and my_vim in a single execution.

### Running SURI in a Docker Environment

If you want to use the Docker environment, you need to pass the `--usedocker` flag to SURI.

```
python3 suri.py [target binary path] --usedocker
```
This ensures that SURI runs inside the provided Docker container.

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
```

## Citation

If you want to cite SURI:
```
T.B.D.
```

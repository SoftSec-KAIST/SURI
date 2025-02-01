# SURI Artifact

This artifact is intended to reproduce the experimental results presented in
our paper, "Towards Sound Reassembly of Modern x86-64 Binaries", published at
ASPLOS '25. It contains scripts for running experiments and datasets we used.

## Overview

### Experiments

This artifact will answer all three research questions from our paper:
- RQ1: How well does SURI compare to the state-of-the-art reassembly tools in terms of reliability?
- RQ2: How big is the performance overhead introduced by SURI for rewritten binaries?
- RQ3: Is SURI applicable to real-world scenarios, such as runtime memory sanitization?

To answer these questions, we conducted total 5 experiments as follows:
- Exp1: Reassembly completion comparison (RQ1)
- Exp2: Test suite pass rate comparison (RQ1)
- Exp3: Reliability test on real-world programs (RQ1)
- Exp4: Reassembly overhead measurement (RQ2)
- Exp5: Application of SURI (RQ3)

### Comparison Targets

We have three comparison targets for the comparative study of SURI.
- [Ddisasm](https://github.com/GrammaTech/ddisasm): a binary reassembler based on datalog disassembly (USENIX Security '20)
- [Egalito](https://github.com/columbia/egalito): a binary recompiler based on layout-agnostifc binary recompilation (ASPLOS '20)
- BASan: a binary-only address sanitizer implemented on top of [RetroWrite](https://github.com/HexHive/retrowrite) (S&P '20)

This table is a brief summary of each tool:
| Tool    | Running Env. | Exp1 | Exp2 | Exp3 | Exp4 | Exp5 |
| ------- | ------------ | ---- | ---- | ---- | ---- | ---- |
| Ddisasm | Ubuntu 20.04 | :o:  | :o:  |      | :o:  |      |
| Egalito | Ubuntu 18.04 | :o:  | :o:  |      | :o:  |      |
| BASan   | Ubuntu 20.04 |      |      |      |      | :o:  |

### Dataset

We used 5 different kinds of benchmark programs to evaluate SURI:
- Coreutils v9.1
- Binutils v2.40
- SPEC CPU 2006 v1.1 and 2017 v1.1
- 10 real-world programs
  - Apache v2.4.56
  - MariaDB v11.5.0
  - Nginx v1.23.3
  - SQLitev 3.31.2
  - 7-Zip-24.05
  - Epiphany-3.36.4
  - Filezilla v3.46.3
  - Openssh v8.2p1
  - Putty v0.73
  - Vim v8.1
- Juliet Test Suite v1.3

Coreutils, Binutils, and SPEC are used for Exp1, Exp2, and Exp4, real-world programs are used for Exp3, and Juliet Test Suite is used for Exp5.

For Coreutils, Binutils and SPEC benchmarks, we further make three different datasets:
- setA: binaries compiled on Ubuntu 20.04 (SURI vs. Ddisasm)
- setB: binaries compiled on Ubuntu 18.04 (SURI vs. Egalito)
- setC: binaries compiled on Ubuntu 20.04 w/o call frame information (ablation study - see Section 4.3.3 of the paper)

Below table sumarizes our datasets:
| Dataset    | Language       | Exp1 | Exp2 | Exp3 | Exp4 | Exp5 |
| ---------- | -------------- | ---- | ---- | ---- | ---- | ---- |
| setA       | C/C++, Fortran | :o:  | :o:  |      | :o:  |      |
| setB       | C              | :o:  | :o:  |      | :o:  |      |
| setC       | C/C++, Fortran | :o:  | :o:  |      | :o:  |      |
| Real-world | C/C++          |      |      | :o:  |      |      |
| Juliet     | C/C++          |      |      |      |      | :o:  |

:warning: We exclude SPEC benchmark binaries from our dataset because they are
proprietary. However, we prepare benchmark building scripts for SPEC benchmarks, in case you have a valid license of SPEC CPU 2006 or 2017.
Our experimental scripts will work well regardless of the existence of SPEC binaries, though.

## Links

These are the links that explain how to set up our artifact and how to run the experiments.
- [Preparation](FIXME)
- [Experiment](FIXME)

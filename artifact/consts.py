# The below constants defines configurations for our benchmark.
# See Section 4.1.1 of our paper.

# Four popular software packages that include well-maintained test suites:
PACKAGES = ['coreutils-9.1', 'binutils-2.40', 'spec_cpu2006', 'spec_cpu2017']
PACKAGES_UTILS = ['coreutils-9.1', 'binutils-2.40']
PACKAGES_SPEC = ['spec_cpu2006', 'spec_cpu2017']

# Four major compilers:
COMPILERS = ['gcc-11', 'gcc-13', 'clang-10', 'clang-13']

# Six optimization levels:
OPTIMIZATIONS = ['o0', 'o1', 'o2', 'o3', 'os', 'ofast']

# Two linkers:
# bfd: GNU ld v2.34
# gold: GNU gold v1.16
LINKERS = ['bfd', 'gold']

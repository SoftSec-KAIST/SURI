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

################################

# The below is a mapping from a package identifier to a binary name in SPEC
# benchmarks. We need this mapping because sometimes the name in the identifier
# (e.g. gcc_r from 502.gcc_r) can be different from the actual binary name in
# the SPEC benchmark (e.g. cpugcc_r).

BIN_NAME_MAP = {
    '482.sphinx3': 'sphinx_livepretend',
    '483.xalancbmk': 'Xalan',
    '500.perlbench_r': 'perlbench_r',
    '502.gcc_r': 'cpugcc_r',
    '503.bwaves_r': 'bwaves_r',
    '505.mcf_r': 'mcf_r',
    '507.cactuBSSN_r': 'cactusBSSN_r',
    '508.namd_r': 'namd_r',
    '510.parest_r': 'parest_r',
    '511.povray_r': 'povray_r',
    '519.lbm_r': 'lbm_r',
    '520.omnetpp_r': 'omnetpp_r',
    '521.wrf_r': 'wrf_r',
    '523.xalancbmk_r': 'cpuxalan_r',
    '525.x264_r': 'x264_r',
    '526.blender_r': 'blender_r',
    '527.cam4_r': 'cam4_r',
    '531.deepsjeng_r': 'deepsjeng_r',
    '538.imagick_r': 'imagick_r',
    '541.leela_r': 'leela_r',
    '544.nab_r': 'nab_r',
    '548.exchange2_r': 'exchange2_r',
    '549.fotonik3d_r': 'fotonik3d_r',
    '554.roms_r': 'roms_r',
    '557.xz_r': 'xz_r',
    '600.perlbench_s': 'perlbench_s',
    '602.gcc_s': 'sgcc',
    '603.bwaves_s': 'speed_bwaves',
    '605.mcf_s': 'mcf_s',
    '607.cactuBSSN_s': 'cactuBSSN_s',
    '619.lbm_s': 'lbm_s',
    '620.omnetpp_s': 'omnetpp_s',
    '621.wrf_s': 'wrf_s',
    '623.xalancbmk_s': 'xalancbmk_s',
    '625.x264_s': 'x264_s',
    '627.cam4_s': 'cam4_s',
    '628.pop2_s': 'speed_pop2',
    '631.deepsjeng_s': 'deepsjeng_s',
    '638.imagick_s': 'imagick_s',
    '641.leela_s': 'leela_s',
    '644.nab_s': 'nab_s',
    '648.exchange2_s': 'exchange2_s',
    '649.fotonik3d_s': 'fotonik3d_s',
    '654.roms_s': 'sroms',
    '657.xz_s': 'xz_s',
    '996.specrand_fs': 'specrand_fs',
    '997.specrand_fr': 'specrand_fr',
    '998.specrand_is': 'specrand_is',
    '999.specrand_ir': 'specrand_ir'
}

################################

# The below is a list of SPEC benchmark binaries that are used to measure
# runtime overheads in Section 4.3.2. We used this list because all three
# reassemblers can successfully reassemble these binaries.

RUNTIME_TARGET_LIST = [
    '400.perlbench',
    '401.bzip2',
    '403.gcc',
    '410.bwaves',
    '429.mcf',
    '433.milc',
    '434.zeusmp',
    '435.gromacs',
    '436.cactusADM',
    '437.leslie3d',
    '444.namd',
    '445.gobmk',
    '447.dealII',
    '454.calculix',
    '456.hmmer',
    '458.sjeng',
    '459.GemsFDTD',
    '462.libquantum',
    '464.h264ref',
    '465.tonto',
    '470.lbm',
    '473.astar',
    '481.wrf',
    '482.sphinx3',
    '503.bwaves_r',
    '505.mcf_r',
    '507.cactuBSSN_r',  #
    '508.namd_r',       #
    '519.lbm_r',
    '531.deepsjeng_r',
    '538.imagick_r',    #
    '544.nab_r',
    '548.exchange2_r',
    '549.fotonik3d_r',
    '557.xz_r',
    '603.bwaves_s',
    '605.mcf_s',
    '607.cactuBSSN_s',  #
    '619.lbm_s',
    '628.pop2_s',
    '631.deepsjeng_s',
    '638.imagick_s',    #
    '644.nab_s',
    '648.exchange2_s',
    '657.xz_s'
]

################################

# These are format strings to print our experimental results.

FMT_REWRITE_HEADER     = '%32s    %22s   %22s'
FMT_REWRITE_INDIVIDUAL = '%15s %10s (%4d) : %10f%% %10f : %10f%% %10f'
FMT_REWRITE_TOTAL      = '%26s (%4d) : %10f%% %10f : %10f%% %10f'
FMT_REWRITE_LINE       = '-----------------------------------------------------------------------------------'

FMT_TESTSUITE_UTILS_HEADER_AB     = '%-15s %7s  %21s %21s'
FMT_TESTSUITE_UTILS_HEADER_C      = '%-15s %7s  %21s'
FMT_TESTSUITE_UTILS_INDIVIDUAL_AB = '%-15s (%-5s): %10s(%4d/%4d) %10s(%4d/%4d)'
FMT_TESTSUITE_UTILS_INDIVIDUAL_C  = '%-15s (%-5s): %10s(%4d/%4d)'

FMT_TESTSUITE_SPEC_HEADER_AB     = '%-15s %7s :   %21s :  %21s'
FMT_TESTSUITE_SPEC_HEADER_C      = '%-15s %7s :   %21s'
FMT_TESTSUITE_SPEC_INDIVIDUAL_AB = '%-15s (%-5s) : %10f%% (%4d/%4d) : %10f%% (%4d/%4d)'
FMT_TESTSUITE_SPEC_INDIVIDUAL_C  = '%-15s (%-5s) : %10f%% (%4d/%4d)'
FMT_TESTSUITE_SPEC_LINE_AB       = '--------------------------------------------------------------------------'
FMT_TESTSUITE_SPEC_LINE_C        = '-------------------------------------------------------'

FMT_BRANCH_HEADER = 'Multi Br-------------'
FMT_CODE_HEADER   = 'Code Size-------------'
FMT_TABLE_HEADER  = 'Table-------------'
FMT_OVERHEAD      = '%15s %10d %10f%%'

FMT_RUNTIME_HEADER_AB  = '%20s |  %8s  %8s'
FMT_RUNTIME_HEADER_C   = '%20s |  %8s  %15s'
FMT_RUNTIME_INDIVIDUAL = '%-15s %4d | %8f%% %8f%%'
FMT_RUNTIME_TOTAL      = '%-15s %4d | %8f%%  %15f%%'

FMT_SURI_HEADER = '%20s |  %8s  '
FMT_SURI        = '%-15s %4d | %8f%%'

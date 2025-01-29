setB_blacklist = [
'444.namd',
'447.dealII',
'450.soplex',
'453.povray',
'471.omnetpp',
'473.astar',
'483.xalancbmk',
'520.omnetpp_r', '620.omnetpp_s',
'523.xalancbmk_r', '623.xalancbmk_s',
'531.deepsjeng_r', '631.deepsjeng_s',
'541.leela_r', '641.leela_s',
'507.cactuBSSN_r', '607.cactuBSSN_s',
'508.namd_r',
'510.parest_r',
'511.povray_r',
'526.blender_r'
]


def check_exclude_files(dataset, package, comp, opt, filename):

    # Exclude C++ for Egalito
    if dataset in ['setB'] and filename in setB_blacklist:
        return True

    # Exclude Errornous Binaries

    if package in ['coreutils-9.1']:
        # 1 (opt) * 2 (comp) * 2 (linker) = 4
        if comp in ['gcc-11', 'gcc-13']:
            if opt in ['ofast']:
                if filename in ['seq']:
                    return True

    if package in ['spec_cpu2006']:
        # 5 (opt) * 4 (comp) * 2 (linker) =  40
        if filename in ['416.gamess'] and opt not in ['o0']:
            return True
        # 1 (opt) * 1 (comp) * 2 (linker) = 2
        if filename in ['453.povray'] and opt in ['ofast'] and comp in ['gcc-13']:
            return True

    if package in ['spec_cpu2017']:
        # 1 (opt) * 1 (comp) * 2 (linker) = 2
        if filename in ['511.povray_r'] and opt in ['ofast'] and comp in ['gcc-13']:
            return True

    return False



#!/bin/bash

PACKAGE="spec_cpu2017"

SRCDIR=/data4/src
WORKDIR=/data4/build_script
MYDIR="$(dirname "$0")"

OPTS=("-Os" "-Ofast" "-O3" "-O2" "-O1" "-O0")
PIEOPTS=("-pie")
TARGETOPTS=("x64" )
LINKEROPTS=("-fuse-ld=gold" "-fuse-ld=bfd")

COMMON="-ggdb -save-temps=obj -fverbose-asm -Wl,--emit-relocs -fcf-protection=full"
COMMON="-ggdb -save-temps=obj -fverbose-asm -fcf-protection=full -mno-avx512f -mno-avx2 -fno-unwind-tables  -fno-asynchronous-unwind-tables"

build_bin(){
    PACKAGE=$1
    TARGET=$2
    OPT=$3
    PIEOPT=$4
    LINKEROPT=$5

    LINKEROPTSTR=`echo $LINKEROPT | sed 's/-fuse-ld=//g'`
    BINDOPT="-Wl,-z,lazy"

    echo $TARGETOPT $OPT $PIEOPT $BINDOPT $LINKEROPT


    OPTSTR=`echo ${OPT:1} | tr '[:upper:]' '[:lower:]'`
    PIEOPTSTR=`echo $PIEOPT | tr '[:upper:]' '[:lower:]' | tr -d '-'`

    GCCOPT="$GCC"
    GPPOPT="$GPP"
    FORTRANOPT="$GFORTRAN"

    COMPILER=$(basename $GCCOPT)


    if [ "$TARGET" = "x86" ]; then
        EXTRAFLAGS="--build=i386-pc-linux TIME_T_32_BIT_OK=yes"
        EXTRAOPT="-m32"
    else
        EXTRAFLAGS=""
        EXTRAOPT=""
    fi

    if [ "$PIEOPT" = "-pie" ]; then
        PIEFLAGS="-fPIE"
    else
        PIEFLAGS="-fno-PIC"
    fi

    COMPILERSTR=`echo "$COMPILER" | sed 's$-.*$$g'`

    if [ "$COMPILERSTR" = "clang" ]; then
        ALL_FLAGS="$COMMON $OPT $PIEOPT $BINDOPT $LOPT $EXTRAOPT $PIEFLAGS $LINKEROPT $LINKEROPT2 -L/usr/lib/llvm-13/lib/"
    else
        ALL_FLAGS="$COMMON $OPT $PIEOPT $BINDOPT $LOPT $EXTRAOPT $PIEFLAGS $LINKEROPT $LINKEROPT2"
    fi

    OFOLDER=$SRCDIR/$PACKAGE

    OUTPUT=case6_no_ehframe_$COMPILER\_$OPTSTR\_$LINKEROPTSTR.cfg

    if [ -f "$OFOLDER/config/$OUTPUT" ]; then
        echo "$OUTPUT exists"

        cd $OFOLDER/config/
        sed "s|_OPT_FLAGS_|OPTIMIZE = $OPT |g" base.cfg | sed "s|_COMPILE_OPTION_|CC = $GCCOPT $ALL_FLAGS -std=c99\nCXX = $GPPOPT $ALL_FLAGS -std=c++11\nFC = $FORTRANOPT  $ALL_FLAGS $FFLAGS -std=legacy |g" | sed "s|_OUTPUT_FOLDER_|$OUTPUT|g" > $OUTPUT

        cd ..
        source shrc
        runcpu --config=$OUTPUT --action=build --tune=base all
        cd $WORKDIR

    else
        cd $OFOLDER/config/
        sed "s|_OPT_FLAGS_|OPTIMIZE = $OPT |g" base.cfg | sed "s|_COMPILE_OPTION_|CC = $GCCOPT $ALL_FLAGS -std=c99\nCXX = $GPPOPT $ALL_FLAGS -std=c++11\nFC = $FORTRANOPT  $ALL_FLAGS $FFLAGS -std=legacy |g" | sed "s|_OUTPUT_FOLDER_|$OUTPUT|g" > $OUTPUT

        cd ..
        source shrc
        runcpu --config=$OUTPUT --action=build --tune=base all
        cd $WORKDIR
    fi

}

build_all(){
    for TARGETOPT in ${TARGETOPTS[@]}
    do
        for OPT in ${OPTS[@]}
        do
            for PIEOPT in ${PIEOPTS[@]}
            do
                for LINKEROPT in ${LINKEROPTS[@]}
                do
                    echo build_bin $TARGETOPT $OPT $PIEOPT $LINKEROPT
                    build_bin $PACKAGE $TARGETOPT $OPT $PIEOPT $LINKEROPT
                done
            done
        done
    done
}

GCC=/usr/bin/gcc-11
GPP=/usr/bin/g++-11
GFORTRAN=/usr/bin/gfortran-11

GCC=/usr/bin/gcc-13
GPP=/usr/bin/g++-13
GFORTRAN=/usr/bin/gfortran-13

build_all
#build_bin spec_cpu2017 x64 -Os -pie -fuse-ld=bfd

GCC=/usr/bin/clang-13
GPP=/usr/bin/clang++-13

GCC=/usr/bin/clang-10
GPP=/usr/bin/clang++-10
GFORTRAN=/usr/bin/gfortran-11

build_all
#build_bin spec_cpu2017 x64 -O1 -pie -fuse-ld=bfd

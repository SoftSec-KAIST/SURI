#!/bin/bash

PACKAGE="spec_cpu2006"

SRCDIR=/data/

WORKDIR=/script/

MYDIR="$(dirname "$0")"
OPTS=("-O0" "-O1" "-O2" "-O3" "-Ofast" "-Os")
PIEOPTS=("-pie")
TARGETOPTS=("x64" )
LINKEROPTS=("-fuse-ld=gold" "-fuse-ld=bfd")

build_bin(){
    PAKAGE=$1
    TARGET=$2
    OPT=$3
    PIEOPT=$4
    LINKEROPT=$5

    LINKEROPTSTR=`echo $LINKEROPT | sed 's/-fuse-ld=//g'`
    BINDOPT="-Wl,-z,lazy"

    #echo $TARGETOPT $OPT $PIEOPT $BINDOPT $LINKEROPT


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

    if [ "$COMPILER" = "clang-13" ]; then
        ALL_FLAGS="$COMMON $OPT $PIEOPT $BINDOPT $LOPT $EXTRAOPT $PIEFLAGS $LINKEROPT -L/usr/lib/llvm-13/lib/"
    elif [ "$COMPILER" = "clang-10" ]; then
        ALL_FLAGS="$COMMON $OPT $PIEOPT $BINDOPT $LOPT $EXTRAOPT $PIEFLAGS $LINKEROPT -L/usr/lib/llvm-10/lib/"
    else
        ALL_FLAGS="$COMMON $OPT $PIEOPT $BINDOPT $LOPT $EXTRAOPT $PIEFLAGS $LINKEROPT "
    fi

    OFOLDER=$SRCDIR/$PACKAGE

    OUTPUT=case1_$COMPILER\_$OPTSTR\_$LINKEROPTSTR.cfg

    if [ -f "$OFOLDER/config/$OUTPUT" ]; then
        echo "$OUTPUT exists"
        cd $OFOLDER/
        source shrc
        runspec --config=$OUTPUT --action=build --tune=base all
        cd $WORKDIR
    else
        cd $OFOLDER/config/
        sed "s|_OPT_FLAGS_|COPTIMIZE = $OPT \nCXXOPTIMIZE = $OPT\nFOPTIMIZE = $OPT |g" base2006.cfg | sed "s|_COMPILE_OPTION_|CC = $GCCOPT $ALL_FLAGS -std=gnu89\nCXX = $GPPOPT $ALL_FLAGS -std=gnu++98\nFC = $FORTRANOPT $ALL_FLAGS $FFLAGS -std=legacy --save-temps |g" | sed "s|_OUTPUT_FOLDER_|ext = $OUTPUT|g" | sed "s|wrf_data_header_size|#wrf_data_header_size|g" > $OUTPUT
        cd ..
        source shrc
        runspec --config=$OUTPUT --action=build --tune=base all
        cd $WORKDIR
    fi
    /bin/bash ./copy.sh spec_cpu2006 case1 $COMPILER $OPTSTR $LINKEROPTSTR
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
COMMON="-ggdb -save-temps=obj -fverbose-asm -fcf-protection=full -mno-avx512f -mno-avx2"

build_all
#build_bin spec_cpu2006 x64 -O3 -pie -fuse-ld=bfd

GCC=/usr/bin/gcc-13
GPP=/usr/bin/g++-13
GFORTRAN=/usr/bin/gfortran-13
COMMON="-ggdb -save-temps=obj -fverbose-asm -fcf-protection=full -mno-avx512f -mno-avx2"

build_all
#build_bin spec_cpu2006 x64 -O3 -pie -fuse-ld=bfd

GCC=/usr/bin/clang-10
GPP=/usr/bin/clang++-10
GFORTRAN=/usr/bin/gfortran-11
COMMON="-ggdb -save-temps=obj -fverbose-asm -fcf-protection=full -mno-avx512f -mno-avx2"

build_all
#build_bin spec_cpu2006 x64 -O3 -pie -fuse-ld=bfd

GCC=/usr/bin/clang-13
GPP=/usr/bin/clang++-13
GFORTRAN=/usr/bin/gfortran-11
COMMON="-ggdb -save-temps=obj -fverbose-asm -fcf-protection=full -mno-avx512f -mno-avx2"

build_all
#build_bin spec_cpu2006 x64 -O3 -pie -fuse-ld=bfd


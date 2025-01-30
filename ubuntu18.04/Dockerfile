FROM ubuntu:18.04

RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y git wget software-properties-common && \
    add-apt-repository ppa:ubuntu-toolchain-r/test -y && \
    apt update && \
    apt install gcc-11 g++-11 clang-10 gfortran-11 -y

RUN apt install python3-pip -y && \
    pip3 install pyelftools

RUN apt install time flex -y

RUN apt install make g++ libreadline-dev gdb lsb-release unzip -y && \
    apt install libc6-dbg libstdc++6-7-dbg -y

RUN mkdir /project && cd /project && \
    git clone https://github.com/columbia/egalito.git && \
    cd egalito && \
    git reset --hard c5bccb4 && \
    sed -i 's|git@github.com:|https://github.com/|' .gitmodules && \
    git submodule update --init --recursive && \
    make

COPY ./superSymbolizer /project/superSymbolizer

RUN wget https://ftp.gnu.org/gnu/coreutils/coreutils-9.1.tar.gz && \
    tar -xzf coreutils-9.1.tar.gz

RUN cd /coreutils-9.1 && \
    FORCE_UNSAFE_CONFIGURE=1 ./configure && \
    make

COPY ./build_script/script/coreutils_copy.sh /coreutils-9.1/copy.sh
COPY ./build_script/script/coreutils-9.1_list.txt /coreutils-9.1/coreutils-9.1_list.txt

RUN wget https://ftp.gnu.org/gnu/binutils/binutils-2.40.tar.gz && \
    tar -xzf binutils-2.40.tar.gz

RUN DEBIAN_FRONTEND=noninteractive apt install texinfo bison dejagnu -y  && \
    cd /binutils-2.40 && \
    ./configure && \
    make

COPY ./build_script/script/binutils_copy.sh /binutils-2.40/copy.sh
COPY ./build_script/script/binutils-2.40_list.txt /binutils-2.40/binutils-2.40_list.txt

RUN git clone https://github.com/witbring/retrowrite_ef4e541.git /project/retrowrite && \
    cd /project/retrowrite && \
    pip3 install -r requirements.txt

RUN apt install -y libcap-dev 

FROM ubuntu:18.04

ENV DEBIAN_FRONTEND="noninteractive"
ENV DEBIAN_FRONTEND="Etc/UTC"

RUN apt update && \
    apt install -y git wget software-properties-common python3-pip

# Install compilers
RUN add-apt-repository ppa:ubuntu-toolchain-r/test -y && \
    apt update && \
    apt install -y gcc-11 g++-11 clang-10 gfortran-11

# Install dotnet7
RUN wget https://packages.microsoft.com/config/ubuntu/18.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y dotnet-sdk-7.0

# Install Python3 dependency
RUN pip3 install pyelftools

# Install Egalito dependencies
RUN apt install -y make g++ libreadline-dev gdb lsb-release unzip \
                   libc6-dbg libstdc++6-7-dbg

# Install additional dependencies
RUN apt install -y time flex texinfo bison dejagnu libcap-dev

RUN mkdir -p /project

# Add SURI
RUN cd /project/ && git clone https://github.com/SoftSec-KAIST/SURI.git && \
    cd SURI && python3 setup.py install

# Build superCFGBuilder
RUN cd /project/SURI/superCFGBuilder && dotnet build -c Release

# Install Egalito
RUN cd /project && \
    git clone https://github.com/columbia/egalito.git && \
    cd egalito && \
    git reset --hard c5bccb4 && \
    sed -i 's|git@github.com:|https://github.com/|' .gitmodules && \
    git submodule update --init --recursive && \
    make

# Build Coreutils for test suite
RUN wget https://ftp.gnu.org/gnu/coreutils/coreutils-9.1.tar.gz && \
    tar -xzf coreutils-9.1.tar.gz && \
    cd /coreutils-9.1 && \
    FORCE_UNSAFE_CONFIGURE=1 ./configure && \
    make

COPY ./build_script/script/coreutils_copy.sh /coreutils-9.1/copy.sh
COPY ./build_script/script/coreutils-9.1_list.txt /coreutils-9.1/coreutils-9.1_list.txt

# Build Binutils for test suite
RUN wget https://ftp.gnu.org/gnu/binutils/binutils-2.40.tar.gz && \
    tar -xzf binutils-2.40.tar.gz && \
    cd /binutils-2.40 && \
    ./configure && \
    make

COPY ./build_script/script/binutils_copy.sh /binutils-2.40/copy.sh
COPY ./build_script/script/binutils-2.40_list.txt /binutils-2.40/binutils-2.40_list.txt

FROM ubuntu:20.04

ENV DEBIAN_FRONTEND="noninteractive"
ENV DEBIAN_FRONTEND="Etc/UTC"

RUN apt update && \
    apt install -y git wget software-properties-common python3-pip

# Install compilers
RUN add-apt-repository ppa:ubuntu-toolchain-r/test -y && \
    apt update && \
    apt install -y gcc-13 g++-13 gcc-11 g++-11 clang-10 clang-11 gfortran-11 gfortran-13

# Install dotnet7
RUN wget https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y dotnet-sdk-7.0

# Install Python3 dependency
RUN pip install pyelftools

RUN mkdir -p /project

# Add SURI
RUN cd /project/ && git clone https://github.com/SoftSec-KAIST/SURI.git && \
    cd SURI && python3 setup.py install

# Build superCFGBuilder
RUN cd /project/SURI/superCFGBuilder && dotnet build

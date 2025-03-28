FROM suri:v1.0

# Install additional dependencies
RUN apt -y install time flex texinfo bison dejagnu

RUN wget --no-check-certificate -O - https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add - && \
    add-apt-repository 'deb http://apt.llvm.org/focal/   llvm-toolchain-focal-13  main' && \
    apt update && \
    apt install -y clang-13 libomp-dev && \
    apt install -y libomp-13-dev

RUN apt -y install php-cli php-xml

# Install Reassessor
RUN cd /project && \
    git clone https://github.com/SoftSec-KAIST/Reassessor.git && \
    cd /project/Reassessor && \
    git checkout suri && \
    pip install -r requirements.txt && \
    python3 setup.py install

# Install RetroWrite
RUN git clone https://github.com/witbring/retrowrite_ef4e541.git /project/retrowrite && \
    cd /project/retrowrite && \
    pip3 install -r requirements.txt

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

# Install phoronix test suites
RUN git clone https://github.com/phoronix-test-suite/phoronix-test-suite.git && \
    cd /phoronix-test-suite && \
    ./install-sh && \
    phoronix-test-suite install  sqlite && \
    phoronix-test-suite intsall  nginx && \
    phoronix-test-suite install  apache && \
    phoronix-test-suite install compress-7zip && \
    phoronix-test-suite install mysqlslap

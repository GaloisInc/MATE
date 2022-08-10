# NOTE: The value of BASE must be kept in-sync with the value of
# MATE_COMPATIBLE_BASE_IMAGE in frontend/mate/mate/build/common.py.
ARG BASE=ubuntu:20.04
FROM $BASE as base

SHELL ["/bin/bash", "-c"]

# Base image should have as few layers as possible
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    apt-get update && \
    apt-get install -y \
      libboost-system-dev libboost-filesystem-dev libboost-iostreams-dev \
      libssl-dev libboost-program-options-dev clang-10 man \
      git python3.8 python3.8-dev python3-pip python3-setuptools python3.8-venv \
      golang libstdc++-8-dev libomp-dev libzmqpp-dev \
      netcat vim emacs-nox libgraphviz-dev graphviz wait-for-it && \
    update-alternatives --install /usr/bin/cc cc /usr/bin/clang-10 100 && \
    update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-10 100 && \
    update-alternatives --install /usr/bin/clang clang /usr/bin/clang-10 100 && \
    update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-10 100 && \
    rm -rf /var/lib/apt/lists/*

FROM artifactory.galois.com:5004/tob-llvm-wedlock:155b9cdb as tob-llvm-wedlock
FROM base as dev

# TODO(lb): Remove the last three lines of dependencies and download pre-built
# packages when Souffle finds another host for pre-built packages:
# https://github.com/souffle-lang/souffle/issues/1855
RUN apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:hvr/ghc && \
    apt-get update && \
    apt-get install -y \
      antlr4 curl locales \
      cabal-install-2.4 wget git-lfs \
      clang-format-10 clang-tidy-10 cmake ghc unzip \
      zlib1g-dev ninja-build gdb shellcheck python3.8-dev \
      autoconf automake bison build-essential clang doxygen flex g++ git \
      libffi-dev libncurses5-dev libtool libsqlite3-dev make mcpp python \
      sqlite zlib1g-dev libc++-dev libc++abi-dev lld && \
    update-alternatives --install /usr/bin/cabal cabal /opt/cabal/bin/cabal 100 && \
    update-alternatives --install /usr/bin/clang-format clang-format /usr/bin/clang-format-10 100 && \
    rm -rf /var/lib/apt/lists/*

RUN cd /tmp && \
    git clone --single-branch --branch=master https://github.com/souffle-lang/souffle && \
    cd souffle && \
    git checkout fce85d9ec8898a53365a0abb39485f27b14987b0 && \
    cmake -S . -B build -G Ninja \
        -DCMAKE_C_FLAGS=-g \
        -DCMAKE_CXX_FLAGS=-g \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DSOUFFLE_USE_ZLIB=ON && \
    cmake --build build --target install && \
    cd && \
    rm -rf /tmp/souffle

RUN wget -qnc -O /tmp/mustache.zip https://github.com/quantumew/mustache-cli/releases/download/v1.0.0/mustache-cli-linux-amd64.zip && \
    unzip -j -d /usr/bin /tmp/mustache.zip mustache && \
    rm /tmp/mustache.zip

RUN wget -qnc -O /usr/bin/hadolint https://github.com/hadolint/hadolint/releases/download/v1.17.5/hadolint-Linux-x86_64 && \
    chmod +x /usr/bin/hadolint

RUN cabal v2-update
RUN cabal v2-install -j --overwrite-policy=always Cabal cabal-install

RUN wget -q -O vagrant.deb https://releases.hashicorp.com/vagrant/2.2.9/vagrant_2.2.9_x86_64.deb && \
    apt-get install -y ./vagrant.deb && \
    rm ./vagrant.deb

ENV PATH=/root/.cabal/bin:$PATH \
    DOCKERIZED_MATE=1

WORKDIR /mate
COPY shake/mate.cabal /mate/mate/mate.cabal
RUN cd mate; rm -rf dist; rm -rf dist-newstyle; cabal v2-build --only-dependencies exe:mate

COPY ./dev-requirements.txt /mate
RUN python3.8 -m pip install -r dev-requirements.txt

RUN locale-gen --purge en_US.UTF-8 && \
    update-locale && \
    dpkg-reconfigure -f noninteractive locales

COPY --from=tob-llvm-wedlock /opt/llvm-wedlock /opt/llvm-wedlock

# If you want the paths to work for dev, then you need to run the dev container
# with the mate repo mounted at '/mate', i.e. '-v <mate-repo-root>:/mate'
ENV MATE_BDIST_ROOT "/mate/.out/bdist"
ENV LLVM_WEDLOCK_INSTALL_DIR="${MATE_BDIST_ROOT}/llvm-wedlock"

ENV LLVM_DIR="${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/llvm" \
    Clang_DIR="${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/clang"

# Keep the following lines updated with what shows up in dist,
# except for MYPYPATH, which must not appear here.
ENV LANG=en_US.UTF-8 \
    PATH="${MATE_BDIST_ROOT}/local/bin:${MATE_BDIST_ROOT}/bin:${PATH}" \
    PYTHONPATH="${MATE_BDIST_ROOT}/local/lib/python3.8/site-packages:${MATE_BDIST_ROOT}/lib/python3.8/site-packages:${PYTHONPATH}" \
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${MATE_BDIST_ROOT}/lib" \
    MANPATH="${MATE_BDIST_ROOT}/local/doc/man:${MATE_BDIST_ROOT}/doc/man"

FROM base as dist
ENV MATE_BDIST_ROOT=/opt/mate
ENV LLVM_WEDLOCK_INSTALL_DIR="${MATE_BDIST_ROOT}/llvm-wedlock"

ENV LLVM_DIR="${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/llvm" \
    Clang_DIR="${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/clang"

ENV PATH="${MATE_BDIST_ROOT}/local/bin:${MATE_BDIST_ROOT}/bin:${PATH}" \
    PYTHONPATH="${MATE_BDIST_ROOT}/local/lib/python3.8/site-packages:${MATE_BDIST_ROOT}/lib/python3.8/site-packages:${PYTHONPATH}" \
    MYPYPATH="${MATE_BDIST_ROOT}/local/lib/python3.8/site-packages:${MATE_BDIST_ROOT}/lib/python3.8/site-packages:${MYPYPATH}" \
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${MATE_BDIST_ROOT}/lib" \
    MANPATH="${MATE_BDIST_ROOT}/local/doc/man:${MATE_BDIST_ROOT}/doc/man" \
    PYTHONWARNINGS=ignore

COPY .out/bdist/llvm-wedlock "${MATE_BDIST_ROOT}/llvm-wedlock"
COPY .out/bdist/bin "${MATE_BDIST_ROOT}/bin"
COPY .out/bdist/lib "${MATE_BDIST_ROOT}/lib"
COPY .out/bdist/libexec "${MATE_BDIST_ROOT}/libexec"
COPY .out/bdist/local "${MATE_BDIST_ROOT}/local"
COPY .out/bdist/share "${MATE_BDIST_ROOT}/share"

# Remove our prebuilt llvm-wedlock copy, now that we've stuffed it into the bdist.
RUN rm -rf /opt/llvm-wedlock

WORKDIR /root
CMD "${MATE_BDIST_ROOT}/local/bin/mate" "-v" "serve"

FROM dist AS notebook

ENV MATE_BDIST_ROOT=/opt/mate
ENV LLVM_WEDLOCK_INSTALL_DIR="${MATE_BDIST_ROOT}/llvm-wedlock"

ENV LLVM_DIR="${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/llvm" \
    Clang_DIR="${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/clang"

ENV PATH="${MATE_BDIST_ROOT}/local/bin:${MATE_BDIST_ROOT}/bin:${PATH}" \
    PYTHONPATH="${MATE_BDIST_ROOT}/local/lib/python3.8/site-packages:${MATE_BDIST_ROOT}/lib/python3.8/site-packages:${PYTHONPATH}" \
    MYPYPATH="${MATE_BDIST_ROOT}/local/lib/python3.8/site-packages:${MATE_BDIST_ROOT}/lib/python3.8/site-packages:${MYPYPATH}" \
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${MATE_BDIST_ROOT}/lib" \
    MANPATH="${MATE_BDIST_ROOT}/local/doc/man:${MATE_BDIST_ROOT}/doc/man"

RUN python3.8 -m pip install jupyter pygraphviz

WORKDIR /chess/galois_items/notebooks

COPY jupyter/start-notebook-server.sh "${MATE_BDIST_ROOT}/local/bin/start-notebook-server.sh"
COPY jupyter/examples /root/notebook-examples
COPY jupyter/ipython_config.py /root/.ipython/profile_default/ipython_config.py

CMD "${MATE_BDIST_ROOT}/local/bin/start-notebook-server.sh"

FROM $BASE AS ui

ARG DEBIAN_FRONTEND=noninteractive

# node installation based on https://www.digitalocean.com/community/tutorials/how-to-install-node-js-on-ubuntu-20-04
RUN curl -sL https://deb.nodesource.com/setup_14.x | bash -
RUN apt-get update && \
  apt-get install -y \
  nodejs npm && \
  rm -rf /var/lib/apt/lists/*

# Build UI
WORKDIR /ui-client
COPY ui-client/package*.json ./
COPY ui-client/tsconfig.json ./
COPY ui-client/public ./public
RUN npm install
RUN npm rebuild node-sass
COPY ui-client/src ./src
RUN npm build

CMD [ "npm", "start" ]

# Build dev by default
FROM dev

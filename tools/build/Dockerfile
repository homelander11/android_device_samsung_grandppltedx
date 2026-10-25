# SPDX-License-Identifier: Apache-2.0
FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    bc bison build-essential ca-certificates curl flex g++-multilib \
    gcc-multilib git git-lfs gnupg gperf imagemagick lib32ncurses5-dev \
    lib32readline-dev lib32z1-dev libelf-dev liblz4-tool libncurses5 \
    libncurses5-dev libsdl1.2-dev libssl-dev libxml2 libxml2-utils lzop \
    pngcrush python-is-python3 python3 python3-pip rsync schedtool \
    squashfs-tools time unzip x11proto-core-dev xsltproc zip zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 builder && \
    useradd -M -d /work/home -s /bin/bash -u 1000 -g 1000 builder

WORKDIR /work/lineage
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 HOME=/work/home

#!/bin/bash -xe

. /etc/os-release
if [ "x${ID}" == "xcentos" ]; then
    yum -y install python3
elif [ "x${ID}" == "xopensuse" -o "x${ID}" == "xopensuse-leap" ]; then
    zypper -n install python3
elif [ "x${ID}" == "xdebian" -o "x${ID}" == "xubuntu" ]; then
    apt-get -y update
    apt-get -y upgrade
    apt-get install -y python3
fi

PBS_DIR=$(dirname $(readlink -f $(basename $0)))
${PBS_DIR}/ci/ci --local

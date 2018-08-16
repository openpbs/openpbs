#!/bin/bash -xe
BUILDPKGS='build-essential dpkg-dev autoconf libtool rpm alien libssl-dev libxt-dev libpq-dev libexpat1-dev libedit-dev libncurses5-dev libical-dev libhwloc-dev pkg-config tcl-dev tk-dev python-dev swig'
DEPPKGS='expat postgresql postgresql-contrib'
TESTPKGS='python-pip sudo man-db'
if [ "x${DEBIAN_FRONTEND}x" == "xx" ]; then
  export DEBIAN_FRONTEND=noninteractive
fi
${DOCKER_EXEC} apt-get -qq update
${DOCKER_EXEC} apt-get install -y ${BUILDPKGS} ${DEPPKGS} ${TESTPKGS}
${DOCKER_EXEC} ./autogen.sh
${DOCKER_EXEC} ./configure
${DOCKER_EXEC} make dist
${DOCKER_EXEC} /bin/bash -c 'mkdir -p /root/rpmbuild/SOURCES/; cp -fv pbspro-*.tar.gz /root/rpmbuild/SOURCES/'
${DOCKER_EXEC} /bin/bash -c 'CFLAGS="-g -O2 -Wall -Werror" rpmbuild -bb --nodeps pbspro.spec'
${DOCKER_EXEC} /bin/bash -c 'alien --to-deb --scripts /root/rpmbuild/RPMS/x86_64/pbspro-server-??.*.x86_64.rpm'
${DOCKER_EXEC} /bin/bash -c 'dpkg -i pbspro-server_*_amd64.deb'
${DOCKER_EXEC} /bin/bash -c 'sed -i "s@PBS_START_MOM=0@PBS_START_MOM=1@" /etc/pbs.conf'
${DOCKER_EXEC} /etc/init.d/pbs start

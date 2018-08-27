#!/bin/bash -xe
${DOCKER_EXEC} yum clean all
${DOCKER_EXEC} yum -y update
${DOCKER_EXEC} yum -y install yum-utils epel-release rpmdevtools libasan llvm
${DOCKER_EXEC} rpmdev-setuptree
${DOCKER_EXEC} yum-builddep -y ./pbspro.spec
${DOCKER_EXEC} ./autogen.sh
${DOCKER_EXEC} ./configure
${DOCKER_EXEC} make dist
${DOCKER_EXEC} /bin/bash -c 'cp -fv pbspro-*.tar.gz /root/rpmbuild/SOURCES/'
${DOCKER_EXEC} /bin/bash -c 'CFLAGS="-g -O2 -Wall -Werror -fsanitize=address -fno-omit-frame-pointer" rpmbuild -bb pbspro.spec'
${DOCKER_EXEC} /bin/bash -c 'yum -y install /root/rpmbuild/RPMS/x86_64/pbspro-server-??.*.x86_64.rpm'
${DOCKER_EXEC} /bin/bash -c 'sed -i "s@PBS_START_MOM=0@PBS_START_MOM=1@" /etc/pbs.conf'
${DOCKER_EXEC} /etc/init.d/pbs start
${DOCKER_EXEC} yum -y install python-pip sudo which net-tools man-db time.x86_64

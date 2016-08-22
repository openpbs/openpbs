#!/bin/bash -xe
${DOCKER_EXEC} yum -y update
${DOCKER_EXEC} yum -y install yum-utils epel-release rpmdevtools
${DOCKER_EXEC} yum -y install time.x86_64
${DOCKER_EXEC} rpmdev-setuptree
${DOCKER_EXEC} yum-builddep -y ./pbspro.spec
${DOCKER_EXEC} ./autogen.sh
${DOCKER_EXEC} ./configure
${DOCKER_EXEC} make dist
${DOCKER_EXEC} /bin/sh -c 'cp -fv pbspro-*.tar.gz /root/rpmbuild/SOURCES/'
${DOCKER_EXEC} rpmbuild -bb pbspro.spec
${DOCKER_EXEC} /bin/sh -c 'yum -y install /root/rpmbuild/RPMS/x86_64/pbspro-server-*.x86_64.rpm'
${DOCKER_EXEC} /etc/init.d/pbs start
${DOCKER_EXEC} yum -y install python-pip sudo which net-tools

#!/bin/bash -xe
OS_NAME=$(${DOCKER_EXEC} cat /etc/os-release | awk -F[=\"] '/^NAME=/ {print $3}')
OS_VERSION=$(${DOCKER_EXEC} cat /etc/os-release | awk -F[=\"] '/^VERSION=/ {print $3}')
OS_NAME_VERSION=${OS_NAME// /_}_${OS_VERSION// /_}
${DOCKER_EXEC} zypper -n ar -f -G http://download.opensuse.org/repositories/devel:/tools/${OS_NAME_VERSION}/devel:tools.repo
${DOCKER_EXEC} zypper -n ar -f -G http://download.opensuse.org/repositories/devel:/libraries:/c_c++/${OS_NAME_VERSION}/devel:libraries:c_c++.repo
${DOCKER_EXEC} zypper -n ref
${DOCKER_EXEC} zypper -n update
${DOCKER_EXEC} zypper -n install rpmdevtools
${DOCKER_EXEC} rpmdev-setuptree
${DOCKER_EXEC} /bin/bash -c "zypper -n install --force-resolution \$(rpmspec --buildrequires -q pbspro.spec)"
${DOCKER_EXEC} ./autogen.sh
${DOCKER_EXEC} ./configure
${DOCKER_EXEC} make dist
${DOCKER_EXEC} /bin/bash -c 'cp -fv pbspro-*.tar.gz /root/rpmbuild/SOURCES/'
${DOCKER_EXEC} /bin/bash -c 'CFLAGS="-g -O2 -Wall -Werror" rpmbuild -bb pbspro.spec'
${DOCKER_EXEC} /bin/bash -c 'zypper --no-gpg-checks -n install /root/rpmbuild/RPMS/x86_64/pbspro-server-??.*.x86_64.rpm'
${DOCKER_EXEC} /bin/bash -c 'sed -i "s@PBS_START_MOM=0@PBS_START_MOM=1@" /etc/pbs.conf'
${DOCKER_EXEC} /etc/init.d/pbs start
${DOCKER_EXEC} zypper -n install python-pip sudo which net-tools man time.x86_64

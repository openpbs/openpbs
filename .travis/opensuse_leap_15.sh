#!/bin/bash -xe
PRETTY_NAME=$(${DOCKER_EXEC} cat /etc/os-release | awk -F[=\"] '/^PRETTY_NAME=/ {print $3}')
PRETTY_NAME=${PRETTY_NAME# }
PRETTY_NAME=${PRETTY_NAME% }
${DOCKER_EXEC} zypper -n ar -f -G http://download.opensuse.org/repositories/devel:/tools/${PRETTY_NAME// /_}/devel:tools.repo
${DOCKER_EXEC} zypper -n ar -f -G http://download.opensuse.org/repositories/devel:/libraries:/c_c++/${PRETTY_NAME// /_}/devel:libraries:c_c++.repo
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

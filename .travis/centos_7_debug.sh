#!/bin/bash -xe
${DOCKER_EXEC} /bin/bash -c "sed -i 's@baseurl=@#baseurl=@g' /etc/yum.repos.d/CentOS-Base.repo"
${DOCKER_EXEC} /bin/bash -c "sed -i 's@#mirrorlist=@mirrorlist=@g' /etc/yum.repos.d/CentOS-Base.repo"
${DOCKER_EXEC} /bin/bash -c "sed -i 's@\$releasever@7.2.1511@g' /etc/yum.repos.d/CentOS-Sources.repo"
${DOCKER_EXEC} yum -y update
${DOCKER_EXEC} yum -y install yum-utils epel-release rpmdevtools
${DOCKER_EXEC} rpmdev-setuptree
${DOCKER_EXEC} yum-builddep -y ./pbspro.spec
${DOCKER_EXEC} ./autogen.sh
${DOCKER_EXEC} ./configure
${DOCKER_EXEC} make dist
${DOCKER_EXEC} /bin/sh -c 'cp -fv pbspro-*.tar.gz /root/rpmbuild/SOURCES/'
${DOCKER_EXEC} /bin/sh -c 'CFLAGS="-g -O0 -DDEBUG -Wall -Werror" rpmbuild -bb pbspro.spec'


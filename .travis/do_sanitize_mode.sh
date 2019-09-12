#!/bin/bash -xe

yum clean all
yum -y update
yum -y install yum-utils epel-release rpmdevtools libasan llvm
rpmdev-setuptree
yum -y install python36-pip sudo which net-tools man-db time.x86_64
yum-builddep -y ./pbspro.spec
./autogen.sh
rm -rf target-sanitize
mkdir -p target-sanitize
cd target-sanitize
../configure
make dist
cp -fv pbspro-*.tar.gz /root/rpmbuild/SOURCES/
CFLAGS="-g -O2 -Wall -Werror -fsanitize=address -fno-omit-frame-pointer" rpmbuild -bb --with ptl pbspro.spec
yum -y install /root/rpmbuild/RPMS/x86_64/pbspro-server-??.*.x86_64.rpm
yum -y install /root/rpmbuild/RPMS/x86_64/pbspro-debuginfo-??.*.x86_64.rpm
yum -y install /root/rpmbuild/RPMS/x86_64/pbspro-ptl-??.*.x86_64.rpm
sed -i "s@PBS_START_MOM=0@PBS_START_MOM=1@" /etc/pbs.conf
/etc/init.d/pbs start
set +e
. /etc/profile.d/ptl.sh
set -e
pbs_config --make-ug

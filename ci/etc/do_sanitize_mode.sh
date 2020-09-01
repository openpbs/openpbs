#!/bin/bash -xe

# Copyright (C) 1994-2020 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of both the OpenPBS software ("OpenPBS")
# and the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# OpenPBS is free software. You can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# OpenPBS is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# PBS Pro is commercially licensed software that shares a common core with
# the OpenPBS software.  For a copy of the commercial license terms and
# conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
# Altair Legal Department.
#
# Altair's dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of OpenPBS and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair's trademarks, including but not limited to "PBS™",
# "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
# subject to Altair's trademark licensing policies.

PBS_DIR=$(readlink -f $0 | awk -F'/ci/' '{print $1}')
cd ${PBS_DIR}

yum clean all
yum -y update
yum -y install yum-utils epel-release rpmdevtools libasan llvm
rpmdev-setuptree
yum -y install python3-pip sudo which net-tools man-db time.x86_64
yum-builddep -y ./*.spec
./autogen.sh
rm -rf target-sanitize
mkdir -p target-sanitize
cd target-sanitize
../configure
make dist
cp -fv *.tar.gz /root/rpmbuild/SOURCES/
CFLAGS="-g -O2 -Wall -Werror -fsanitize=address -fno-omit-frame-pointer" CXXFLAGS="-g -O2 -fsanitize=address -fno-omit-frame-pointer" rpmbuild -bb --with ptl *.spec
yum -y install /root/rpmbuild/RPMS/x86_64/*-server-??.*.x86_64.rpm
yum -y install /root/rpmbuild/RPMS/x86_64/*-debuginfo-??.*.x86_64.rpm
yum -y install /root/rpmbuild/RPMS/x86_64/*-ptl-??.*.x86_64.rpm
sed -i "s@PBS_START_MOM=0@PBS_START_MOM=1@" /etc/pbs.conf
/etc/init.d/pbs start
set +e
. /etc/profile.d/ptl.sh
set -e
pbs_config --make-ug
cd /opt/ptl/tests/
pbs_benchpress --tags=smoke

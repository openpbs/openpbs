#! /bin/bash -xe

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

. /etc/os-release

pbsdir=/pbssrc
rpm_dir=/root/rpmbuild

rm -rf /src/packages
mkdir -p /src/packages
mkdir -p ${rpm_dir}/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

if [ "x${ID}" == "xcentos" -a "x${VERSION_ID}" == "x8" ]; then
	export LANG="C.utf8"
	swig_opt="--with-swig=/usr/local"
	if [ ! -f /tmp/swig/swig/configure ]; then
		# source install swig
		dnf -y install gcc-c++ byacc pcre-devel
		mkdir -p /tmp/swig/
		cd /tmp/swig
		git clone https://github.com/swig/swig --branch rel-4.0.0 --single-branch
		cd swig
		./autogen.sh
		./configure
		make -j8
		make install
		cd ${PBS_DIR}
	fi
fi

cp -r $pbsdir /tmp/pbs
cd /tmp/pbs
./autogen.sh
mkdir target
cd target
../configure --prefix=/opt/pbs --enable-ptl ${swig_opt}
make dist
cp *.tar.gz ${rpm_dir}/SOURCES
cp ../*-rpmlintrc ${rpm_dir}/SOURCES
cp *.spec ${rpm_dir}/SPECS
cflags="-g -O2 -Wall -Werror"
cxxflags="-g -O2 -Wall"
if [ "x${ID}" == "xdebian" -o "x${ID}" == "xubuntu" ]; then
	CFLAGS="${cflags} -Wno-unused-result" CXXFLAGS="${cxxflags} -Wno-unused-result" rpmbuild -ba --nodeps *.spec --with ptl
else
	if [ "x${ID}" == "xcentos" -a "x${VERSION_ID}" == "x8" ]; then
		CFLAGS="${cflags}" CXXFLAGS="${cxxflags}" rpmbuild -ba *.spec --with ptl -D "_with_swig ${swig_opt}"
	else
		CFLAGS="${cflags}" CXXFLAGS="${cxxflags}" rpmbuild -ba *.spec --with ptl
	fi
fi

cp ${pbsdir}/README.md /src/packages/
cp ${pbsdir}/LICENSE /src/packages/
cp ${pbsdir}/COPYRIGHT /src/packages/
mv ${rpm_dir}/RPMS/*/*pbs* /src/packages/
mv ${rpm_dir}/SRPMS/*pbs* /src/packages/
cd /src/packages
rm -rf /tmp/pbs

if [ "x${ID}" == "xdebian" -o "x${ID}" == "xubuntu" ]; then
	_target_arch=$(dpkg --print-architecture)
	fakeroot alien --to-deb --scripts --target=${_target_arch} *-debuginfo*.rpm -g
	_dir=$(/bin/ls -1d *debuginfo* | grep -vE '(rpm|orig)')
	mv ${_dir}/opt/pbs/usr/ ${_dir}/
	rm -rf ${_dir}/opt
	(
		cd ${_dir}
		dpkg-buildpackage -d -b -us -uc
	)
	rm -rf ${_dir} ${_dir}.orig *debuginfo*.buildinfo *debuginfo*.changes *debuginfo*.rpm
	fakeroot alien --to-deb --scripts --target=${_target_arch} *.rpm
	rm -f *.rpm
fi

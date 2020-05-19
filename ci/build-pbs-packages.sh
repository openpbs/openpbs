#! /bin/bash -xe

. /etc/os-release

pbsdir=/pbssrc
rpm_dir=/root/rpmbuild

rm -rf /src/packages
mkdir -p /src/packages
mkdir -p ${rpm_dir}/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

cp -r $pbsdir /tmp/pbs
cd /tmp/pbs
./autogen.sh
mkdir target
cd target
../configure --prefix=/opt/pbs --enable-ptl
make dist
cp *.tar.gz ${rpm_dir}/SOURCES
cp ../*-rpmlintrc ${rpm_dir}/SOURCES
cp *.spec ${rpm_dir}/SPECS
cflags="-g -O2 -Wall -Werror"
if [ "x${ID}" == "xdebian" -o "x${ID}" == "xubuntu" ]; then
	CFLAGS="${cflags} -Wno-unused-result" rpmbuild -ba --nodeps *.spec --with ptl
else
	CFLAGS="${cflags}" rpmbuild -ba *.spec --with ptl
fi

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
	(cd ${_dir}; dpkg-buildpackage -d -b -us -uc)
	rm -rf ${_dir} ${_dir}.orig *debuginfo*.buildinfo *debuginfo*.changes *debuginfo*.rpm
	fakeroot alien --to-deb --scripts --target=${_target_arch} *.rpm
	rm -f *.rpm
fi

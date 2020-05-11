#! /bin/bash -xe

. /etc/os-release

pbsdir=/pbssrc
rpm_dir=/root/rpmbuild

mkdir -p /src/packages
mkdir -p ${rpm_dir}/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

cp -r $pbsdir /tmp/pbs
cd /tmp/pbs
./autogen.sh
./configure --prefix=/opt/pbs --enable-ptl
make dist
cp pbspro-*.tar.gz ${rpm_dir}/SOURCES
cp pbspro-rpmlintrc ${rpm_dir}/SOURCES
cp pbspro.spec ${rpm_dir}/SPECS
cd ${rpm_dir}/SPECS
if [ "x${ID}" == "xdebian" -o "x${ID}" == "xubuntu" ]; then
	rpmbuild -ba --nodeps pbspro.spec --with ptl
else
	rpmbuild -ba pbspro.spec --with ptl
fi
cd /src/packages/
rm -rf ./*
mv ${rpm_dir}/RPMS/*/*pbs* /src/packages/
mv ${rpm_dir}/SRPMS/*pbs* /src/packages/
rm -rf /tmp/pbs

if [ "x${ID}" == "xdebian" -o "x${ID}" == "xubuntu" ]; then
	target_arch=$(dpkg --print-architecture)
	fakeroot alien --to-deb --scripts --target=${target_arch} ./*pbs*.rpm
	errcode=$?
	if [ $errcode -ne 0 ]; then
		echo "ERROR: Conversion of RPM to DEB FAILED"
		exit 1
	fi
	rm -rf *pbs*.rpm
fi

chmod 755 *pbs*

#!/bin/bash

create_file()
{
#substituting variables bcz pbs spec file contains similar strings, sed	command fails
 	first=$1
 	second=$2
	third=$3

#adding shebang for shell scripts	
	echo "#!/bin/bash" > $third
	echo "RPM_INSTALL_PREFIX=/opt/pbs" >> $third	
	echo "export RPM_INSTALL_PREFIX" >> $third

#Moving pbs_* files from etc to /opt/pbs/etc/ in postinst
	if [ $third == "postinst" ]
	then
		echo "mkdir /opt/pbs/etc" >> $third
		echo "mv /etc/pbs_* /opt/pbs/etc/" >> $third 
	fi

#sed -n '/%post %{pbs_server}/,/%post %{pbs_execution}/p' pbspro.spec | tee ex.sh
	eval "sed -n '/$first/,/$second/p' pbspro.spec | tee -a $third"	
#sed -i '$ d' ex.sh
	eval "sed -i '$ d' $third"
#sed -i 's/%post %{pbs_server}/#!bin\/bash\//' ex.sh
	eval "sed -i 's/$first/#xxx/' $third"

#replacing macros with values as they are not recognizable in shell script	
	eval "sed -i 's/%{pbs_prefix}/\/opt\/pbs/' $third"
	eval "sed -i 's/%{version}/${pbs_version}/' $third"
	eval "sed -i 's/%{pbs_home}/\/var\/spool\/pbs/' $third"
	eval "sed -i 's/%{pbs_dbuser}/postgres/' $third"
	eval "sed -i 's/%endif/#xxx/' $third"
	eval "sed -i 's/%if %{defined have_systemd}/#xxx/' $third"
}

usage(){
	echo "This script takes all arguments for configure and builds debian package
				eg ./deb_build --enable-ptl --prefix=/tmp/dir/
				Check for available configure options using ./confgure --help
	--help: Prints usage of script"
}

create_configure_options(){
	while [ $# -gt 0 ]
	do
		if [ "$1" == "--help" ];then
			usage
			exit 0
		fi  
		param_string=" ${param_string}$1"
		shift
	done

}

create_configure_options $@
./autogen.sh
./configure --prefix=/opt/pbs --libexecdir=/opt/pbs/libexec${param_string}
if [ $? -ne 0 ]; then
	usage
	echo "incorrect arguments for configure"
	exit 1
fi

#Rename current directory to pbspro-{version}
pbs_version=$( cat pbspro.spec | grep pbs_version.*[0-9]$ | awk -F' ' '{print $3}' )
mv $( dirname $(pwd)/pbspro.spec ) ../pbspro-${pbs_version}

#creating debian folder templates
dh_make --createorig --single --yes

#creating debian scripts
create_file "%post %{pbs_server}" "%post %{pbs_execution}" postinst
create_file "%postun %{pbs_server}" "%postun %{pbs_execution}" postrm
create_file "%preun %{pbs_server}" "%preun %{pbs_execution}" prerm

#adding configuration rules in debian/rules file
echo "override_dh_auto_configure:
	dh_auto_configure -- --prefix=/opt/pbs --libexecdir=/opt/pbs/libexec${param_string}" >> debian/rules

#moving scripts to debian folder
mv postinst debian/
mv prerm debian/
mv postrm debian/

#building the package
dpkg-buildpackage -d -b -us -uc

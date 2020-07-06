#! /bin/bash -x

if [ -f /src/.config_dir/.requirements_decorator ]; then
	. /src/.config_dir/.requirements_decorator
fi

if [ "x${NODE_TYPE}" == "xmom" ]; then
	sed -i "s@PBS_SERVER=$(hostname)@PBS_SERVER=pbs_server@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=1@PBS_START_SERVER=0@" /etc/pbs.conf
	HOST_NAME=$(hostname -s)
	ssh -t root@pbs_server " /opt/pbs/bin/qmgr -c 'c n ${HOST_NAME}'"
	if [ "x$no_comm_on_mom" == "xTrue" ]; then
		sed -i "s@PBS_START_COMM=1@PBS_START_COMM=0@" /etc/pbs.conf
	fi
fi

if [ "x${NODE_TYPE}" == "xserver" ]; then
	if [ "x$no_comm_on_server" == "xTrue" ]; then
		sed -i "s@PBS_START_COMM=1@PBS_START_COMM=0@" /etc/pbs.conf
	fi
	if [ "x$no_mom_on_server" == "xTrue" ]; then
		sed -i "s@PBS_START_MOM=1@PBS_START_MOM=0@" /etc/pbs.conf
	fi
fi

if [ "x${NODE_TYPE}" == "xcomm" ]; then
	sed -i "s@PBS_SERVER=$(hostname)@PBS_SERVER=pbs_server@" /etc/pbs.conf
	sed -i "s@PBS_START_MOM=1@PBS_START_MOM=0@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=1@PBS_START_SERVER=0@" /etc/pbs.conf
fi

#! /bin/bash -x

if [ -f /src/.config_dir/.requirements_decorator ]; then
	. /src/.config_dir/.requirements_decorator
fi

if [ "x${NODE_TYPE}" == "xmom" ]; then
	sed -i "s@PBS_SERVER=.*@PBS_SERVER=pbs-server@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=.*@PBS_START_SERVER=0@" /etc/pbs.conf
	HOST_NAME=$(hostname -s)
	ssh -t root@pbs-server " /opt/pbs/bin/qmgr -c 'c n ${HOST_NAME}'"
	if [ "x$no_comm_on_mom" == "xTrue" ]; then
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=0@" /etc/pbs.conf
	else
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=1@" /etc/pbs.conf
	fi
	sed -i "s@PBS_START_SCHED=.*@PBS_START_SCHED=0@" /etc/pbs.conf
fi

if [ "x${NODE_TYPE}" == "xserver" ]; then
	sed -i "s@PBS_SERVER=.*@PBS_SERVER=$(hostname)@" /etc/pbs.conf
	if [ "x$no_comm_on_server" == "xTrue" ]; then
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=0@" /etc/pbs.conf
	else
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=1@" /etc/pbs.conf
	fi
	if [ "x$no_mom_on_server" == "xTrue" ]; then
		sed -i "s@PBS_START_MOM=.*@PBS_START_MOM=0@" /etc/pbs.conf
	else
		sed -i "s@PBS_START_MOM=.*@PBS_START_MOM=1@" /etc/pbs.conf
	fi
	sed -i "s@PBS_START_SERVER=.*@PBS_START_SERVER=1@" /etc/pbs.conf
	sed -i "s@PBS_START_SCHED=.*@PBS_START_SCHED=1@" /etc/pbs.conf
fi

if [ "x${NODE_TYPE}" == "xcomm" ]; then
	sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=1@" /etc/pbs.conf
	sed -i "s@PBS_SERVER=.*@PBS_SERVER=pbs-server@" /etc/pbs.conf
	sed -i "s@PBS_START_MOM=.*@PBS_START_MOM=0@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=.*@PBS_START_SERVER=0@" /etc/pbs.conf
	sed -i "s@PBS_START_SCHED=.*@PBS_START_SCHED=0@" /etc/pbs.conf
fi

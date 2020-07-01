#! /bin/bash -x

set_requirement_decorator() {
	if [ ! -f /src/.config_dir/.benchpress_opt ]; then
		touch /src/.config_dir/.benchpress_opt
	fi
	if [ "x$(cat /src/.config_dir/.benchpress_opt)" == "x" ]; then
		echo "-t SmokeTest" >/src/.config_dir/.benchpress_opt
	fi
	if [ ! -f "/src/ptl_ts_tree.json" ]; then
		/src/etc/gen_ptl_json.sh "$(cat /src/.config_dir/.benchpress_opt)"
	fi

	node_flags=$(python -c "
import json
no_mom_on_server_flag = False
no_comm_on_mom_flag = False
no_comm_on_server_flag = False
config = json.loads(open('/src/ptl_ts_tree.json').read())
for ts in config.values():
    for tclist in ts['tclist'].values():
        no_mom_on_server_flag = tclist['requirements']['no_mom_on_server'] or no_mom_on_server_flag
        no_comm_on_server_flag = tclist['requirements']['no_comm_on_server'] or no_comm_on_server_flag
        no_comm_on_mom_flag = tclist['requirements']['no_comm_on_mom'] or no_comm_on_mom_flag
print(str(no_mom_on_server_flag) +';' + str(no_comm_on_server_flag) + ';' + str(no_comm_on_mom_flag))
")
	no_mom_on_server=$(echo $node_flags | awk -F';' '{print $1}')
	no_comm_on_server=$(echo $node_flags | awk -F';' '{print $2}')
	no_comm_on_mom=$(echo $node_flags | awk -F';' '{print $3}')
}

set_requirement_decorator

if [ "x${NODE_TYPE}" == "xmom" ]; then
	sed -i "s@PBS_SERVER=$(hostname)@PBS_SERVER=pbs_server@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=1@PBS_START_SERVER=0@" /etc/pbs.conf
	HOST_NAME=$(hostname -f)
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
	sed -i "s@PBS_START_MOM=1@PBS_START_MOM=0@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=1@PBS_START_SERVER=0@" /etc/pbs.conf
fi

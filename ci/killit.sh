#!/bin/bash -x


killit(){
    if [ -z "$1" ]	
	then	
		return 0	
	fi	
	pid=$(ps -ef 2>/dev/null | grep $1 | grep -v grep | awk '{print $2}')	
	if [ ! -z "${pid}" ]	
	then	
		echo "kill -TERM ${pid}"	
		kill -TERM ${pid} 2>/dev/null	
	else	
		return 0	
	fi	
	sleep 10	
	pid=$(ps -ef 2>/dev/null | grep $1 | grep -v grep | awk '{print $2}')	
	if [ ! -z "${pid}" ]	
	then	
		echo "kill -KILL ${pid}"	
		kill -KILL ${pid} 2>/dev/null	
	fi	
}

kill_pbs_process(){
    ps -eaf 2>/dev/null | grep pbs_ | grep -v grep | wc -l
    if [ $ret -gt 0 ];then
        killit pbs_server
        killit pbs_mom
        killit pbs_comm
        killit pbs_sched
        killit pbs_ds_monitor
		killit /opt/pbs/pgsql/bin/postgres
        killit pbs_benchpress
        ps_count=$(ps -eaf 2>/dev/null | grep pbs_ | grep -v grep | wc -l ) 
		if [ ${ps_count} -eq 0 ]; then
			return 0
		else
			return 1
		fi 
    fi
}

clean=${1}
. /etc/os-release
echo "Trying to stop all process via init.d"
/etc/init.d/pbs stop
ret=$?
if [ ${ret} -ne 0 ];then
    echo "failed graceful stop"
    echo "force kill all processes"
    kill_pbs_process
else
    echo "checking for running ptl"
    benchpress_count=$(ps -ef 2>/dev/null | grep $1 | grep -v grep | wc -l)
    if [ ${benchpress_count} -gt 0 ]; then
        killit pbs_benchpress
    else
        echo "No running ptl tests found"
    fi
fi

if [ "XX${clean}" == "XXclean" ];then
    cd /pbspro/target-${ID} && make uninstall
	rm -rf /etc/init.d/pbs
    rm -rf /etc/pbs.conf
    rm -rf /var/spool/pbs
    rm -rf /opt/ptl
    rm -rf /opt/pbs
fi

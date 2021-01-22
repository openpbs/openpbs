#!/bin/bash -x

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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

killit() {
    if [ -z "$1" ]; then
        return 0
    fi
    pid=$(ps -ef 2>/dev/null | grep $1 | grep -v grep | awk '{print $2}')
    if [ ! -z "${pid}" ]; then
        echo "kill -TERM ${pid}"
        kill -TERM ${pid} 2>/dev/null
    else
        return 0
    fi
    sleep 10
    pid=$(ps -ef 2>/dev/null | grep $1 | grep -v grep | awk '{print $2}')
    if [ ! -z "${pid}" ]; then
        echo "kill -KILL ${pid}"
        kill -KILL ${pid} 2>/dev/null
    fi
}

kill_pbs_process() {
    ps -eaf 2>/dev/null | grep pbs_ | grep -v grep | wc -l
    if [ $ret -gt 0 ]; then
        killit pbs_server
        killit pbs_mom
        killit pbs_comm
        killit pbs_sched
        killit pbs_ds_monitor
        killit /opt/pbs/pgsql/bin/postgres
        killit pbs_benchpress
        ps_count=$(ps -eaf 2>/dev/null | grep pbs_ | grep -v grep | wc -l)
        if [ ${ps_count} -eq 0 ]; then
            return 0
        else
            return 1
        fi
    fi
}

. /etc/os-release

if [ "x$1" == "xbackup" ]; then
    time_stamp=$(date -u "+%Y-%m-%d-%H%M%S")
    folder=session-${time_stamp}
    mkdir -p /logs/${folder}
    cp /logs/build-* /logs/${folder}
    cp /logs/logfile* /logs/${folder}
    cp /logs/result* /logs/${folder}
    cp /src/.config_dir/.conf.json /logs/${folder}/conf.json
    cp /src/docker-compose.json /logs/${folder}/
    rm -rf /logs/build-*
    rm -rf /logs/logfile*
    rm -rf /logs/result*
    rm -rf /pbssrc/target-*
    exit 0
fi

clean=${1}
echo "Trying to stop all process via init.d"
/etc/init.d/pbs stop
ret=$?
if [ ${ret} -ne 0 ]; then
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

if [ "XX${clean}" == "XXclean" ]; then
    cd /pbssrc/target-${ID} && make uninstall
    rm -rf /etc/init.d/pbs
    rm -rf /etc/pbs.conf
    rm -rf /var/spool/pbs
    rm -rf /opt/ptl
    rm -rf /opt/pbs
fi

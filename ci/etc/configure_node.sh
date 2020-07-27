#! /bin/bash -x

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

. /src/etc/macros
if [ -f /src/${CONFIG_DIR}/${REQUIREMENT_DECORATOR_FILE} ]; then
	. /src/${CONFIG_DIR}/${REQUIREMENT_DECORATOR_FILE}
fi

if [ "x${NODE_TYPE}" == "xmom" ]; then
	sed -i "s@PBS_SERVER=.*@PBS_SERVER=${SERVER}@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=.*@PBS_START_SERVER=0@" /etc/pbs.conf
	ssh -t root@${SERVER} " /opt/pbs/bin/qmgr -c 'c n $(hostname -s)'"
	if [ "x${no_comm_on_mom}" == "xTrue" ]; then
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=0@" /etc/pbs.conf
	else
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=1@" /etc/pbs.conf
	fi
	sed -i "s@PBS_START_SCHED=.*@PBS_START_SCHED=0@" /etc/pbs.conf
fi

if [ "x${NODE_TYPE}" == "xserver" ]; then
	sed -i "s@PBS_SERVER=.*@PBS_SERVER=$(hostname)@" /etc/pbs.conf
	if [ "x${no_comm_on_server}" == "xTrue" ]; then
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=0@" /etc/pbs.conf
	else
		sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=1@" /etc/pbs.conf
	fi
	if [ "x${no_mom_on_server}" == "xTrue" ]; then
		sed -i "s@PBS_START_MOM=.*@PBS_START_MOM=0@" /etc/pbs.conf
	else
		sed -i "s@PBS_START_MOM=.*@PBS_START_MOM=1@" /etc/pbs.conf
	fi
	sed -i "s@PBS_START_SERVER=.*@PBS_START_SERVER=1@" /etc/pbs.conf
	sed -i "s@PBS_START_SCHED=.*@PBS_START_SCHED=1@" /etc/pbs.conf
fi

if [ "x${NODE_TYPE}" == "xcomm" ]; then
	sed -i "s@PBS_START_COMM=.*@PBS_START_COMM=1@" /etc/pbs.conf
	sed -i "s@PBS_SERVER=.*@PBS_SERVER=${SERVER}@" /etc/pbs.conf
	sed -i "s@PBS_START_MOM=.*@PBS_START_MOM=0@" /etc/pbs.conf
	sed -i "s@PBS_START_SERVER=.*@PBS_START_SERVER=0@" /etc/pbs.conf
	sed -i "s@PBS_START_SCHED=.*@PBS_START_SCHED=0@" /etc/pbs.conf
fi

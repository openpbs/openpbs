#!/bin/sh
# Copyright (C) 1994-2018 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# For a copy of the commercial license terms and conditions,
# go to: (http://www.pbspro.com/UserArea/agreement.html)
# or contact the Altair Legal Department.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.
#
# writevnode - write cpuset information for a vnode
#    $1 is the subdirectory (node0, node1, ...) under SYSDIRNODE
#    $2 is the vnode name of the form "host[n]" for multiple nodes
#       or "host" for a single node
#    $3 is the node number, 0 to n-1
#
writevnode ()
{
        numcpus=`ls -1d ${SYSDIRNODE}/${1}/cpu* | grep cpu\[0-9\] | wc -l`
	numcpus=`echo $numcpus | sed -e "s/^ *//"`
        cpustr=`ls -1d ${SYSDIRNODE}/${1}/cpu* | grep cpu\[0-9\] | \
                sed -e "s/^.*cpu\([0-9]*\)/\1/" | sort -n`
        cpustr=`echo $cpustr | sed -e "s/ /,/g"`
	echo "${2}: resources_available.ncpus = $numcpus"
	echo "${2}: cpus = $cpustr"
	amtmem=`grep MemTotal ${SYSDIRNODE}/${1}/meminfo | sed -e "s/^.*: *//"`
	amtmem=`echo $amtmem | sed -e "s/ .*$//"`
	echo "${2}: resources_available.mem = ${amtmem}kb"
	echo "${2}: mems = $3"
}

host=`/bin/hostname | sed -e 's/\..*//'`

echo "\$configversion 2"
echo "$host: pnames = router"

if [ -n "$1" ] 
then
    if [ "$1" = "cpuset" ]
    then
	
#	create and write cpuset related information

	SYSDIRNODE="/sys/devices/system/node"
	NODECT=`ls -1d $SYSDIRNODE/node[0-9]* | wc -l`
	if [ $NODECT -eq 1 ] ; then
            echo "$host: sharing = default_excl"
            writevnode "node0" $host "0"
	else
            echo "$host: sharing = ignore_excl"
            echo "$host: resources_available.ncpus = 0"
            echo "$host: resources_available.mem = 0"
	    JN=0
            while [ $JN -lt $NODECT ] ; do
                echo "${host}[${JN}]: sharing = default_excl"
                writevnode "node${JN}" "${host}[${JN}]" ${JN}
                JN=`expr $JN + 1`
            done
        fi
    else
	echo invalid argument to script $0
    fi
fi

exit 0

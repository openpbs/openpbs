#!/bin/sh
#  Copyright (C) 1994-2016 Altair Engineering, Inc.
#  For more information, contact Altair at www.altair.com.
#   
#  This file is part of the PBS Professional ("PBS Pro") software.
#  
#  Open Source License Information:
#   
#  PBS Pro is free software. You can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License as published by the Free 
#  Software Foundation, either version 3 of the License, or (at your option) any 
#  later version.
#   
#  PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY 
#  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#   
#  You should have received a copy of the GNU Affero General Public License along 
#  with this program.  If not, see <http://www.gnu.org/licenses/>.
#   
#  Commercial License Information: 
#  
#  The PBS Pro software is licensed under the terms of the GNU Affero General 
#  Public License agreement ("AGPL"), except where a separate commercial license 
#  agreement for PBS Pro version 14 or later has been executed in writing with Altair.
#   
#  Altair’s dual-license business model allows companies, individuals, and 
#  organizations to create proprietary derivative works of PBS Pro and distribute 
#  them - whether embedded or bundled with other software - under a commercial 
#  license agreement.
#  
#  Use of Altair’s trademarks, including but not limited to "PBS™", 
#  "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
#  trademark licensing policies.

. ${PBS_CONF_FILE:-/etc/pbs.conf}

echo Setting placement set data ...
${PBS_EXEC}/bin/pbsnodes -a | grep "^[a-zA-Z]" | while read node
do
    if [ -n "`echo $node | grep 'r[0-9][0-9]*i[0-9]n[0-9][0-9]*'`" ]
    then
	L1=`echo $node | sed -e "s/\(r[0-9][0-9]*i[0-9][0-9]*\)n.*/\1/"`
	L2=`echo $node | sed -e "s/\(r[0-9][0-9]*\)i[0-9][0-9]*n.*/\1/"`
	echo "  for $node as resources_available.router=\"${L1},${L2}\""
	${PBS_EXEC}/bin/qmgr -c "s node $node resources_available.router=\"${L1},${L2}\""
    else
	echo " "
	echo Node ${node} name is not in standard SGI naming convention,
	echo no placement set created for ${node}
	echo " "
    fi

done
exit 0

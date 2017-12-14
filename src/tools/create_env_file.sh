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
#
# Script to create an environment variables files for the PBS daemons
#
if [ $# -eq 0 ] ; then
	echo Usage: $0 filename
	exit 1
fi
F=$1
ans=y
ED=${EDITOR:-vi}
if [ -f $F ] ; then
	if [ -w $F ] ; then
		echo ""
		echo PBS environment file $F exists and is writable.
		echo 'Do you wish to overwrite it [y|(n)]?'
		read ans
		if [ X$ans = X ] ; then ans=n ; fi
		if [ $ans = y ] ; then
			echo 'Are you sure [y\|(n)]?'
			read ans
			if [ X$ans = X ] ; then ans=n ; fi
			if [ $ans = y ] ; then
				rm $F
			fi
		fi
	elif [ -r $F ] ; then
		echo WARNING, file $F exists and is not writable.
		exit 1
	fi
fi
if [ $ans = y ] ; then
	echo ""
	echo Creating PBS environment file $F
	printenv > $F
	chmod 700 $F
fi
echo 'Do you wish to edit it [(y)\|n]?'
read ans
if [ X$ans = X ] ; then ans=y ; fi
if [ $ans = y ] ; then
	$ED $F
fi

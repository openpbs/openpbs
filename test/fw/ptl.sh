#!/usr/bin/sh
#
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


# This file will set path variables in case of ptl installation

if [ -f /etc/debian_version ]; then
    __ptlpkgname=$(dpkg -W -f='${binary:Package}\n' 2>/dev/null | grep -E '*-ptl$')
    if [ "x${__ptlpkgname}" != "x" ]; then
        ptl_prefix_lib=$(dpkg -L ${__ptlpkgname} 2>/dev/null | grep -m 1 lib$ 2>/dev/null)
    fi
else
    __ptlpkgname=$(rpm -qa 2>/dev/null | grep -E '*-ptl-[[:digit:]]')
    if [ "x${__ptlpkgname}" != "x" ]; then
        ptl_prefix_lib=$(rpm -ql ${__ptlpkgname} 2>/dev/null | grep -m 1 lib$ 2>/dev/null)
    fi
fi
if [ "x${ptl_prefix_lib}" != "x" ]; then
	python_dir=$( /bin/ls -1 ${ptl_prefix_lib} )
	prefix=$( dirname ${ptl_prefix_lib} )

	export PATH=${prefix}/bin/:${PATH}
	export PYTHONPATH=${prefix}/lib/${python_dir}/site-packages${PYTHONPATH:+:$PYTHONPATH}
	unset python_dir
	unset prefix
	unset ptl_prefix_lib
else
	conf="${PBS_CONF_FILE:-/etc/pbs.conf}"
	if [ -r "${conf}" ]; then
		# we only need PBS_EXEC from pbs.conf
		__PBS_EXEC=$( grep '^[[:space:]]*PBS_EXEC=' "$conf" | tail -1 | sed 's/^[[:space:]]*PBS_EXEC=\([^[:space:]]*\)[[:space:]]*/\1/' )
		if [ "X${__PBS_EXEC}" != "X" ]; then
			# Define PATH and PYTHONPATH for the users
			PTL_PREFIX=$( dirname ${__PBS_EXEC} )/ptl
			python_dir=$( /bin/ls -1 ${PTL_PREFIX}/lib )/site-packages
			[ -d "${PTL_PREFIX}/bin" ] && export PATH="${PATH}:${PTL_PREFIX}/bin"
			[ -d "${PTL_PREFIX}/lib/${python_dir}" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}${PTL_PREFIX}/lib/${python_dir}"
			[ -d "${__PBS_EXEC}/lib/python/altair" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}${__PBS_EXEC}/lib/python/altair"
			[ -d "${__PBS_EXEC}/lib64/python/altair" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}${__PBS_EXEC}/lib64/python/altair"
		fi
		unset __PBS_EXEC
		unset PTL_PREFIX
		unset conf
		unset python_dir
	fi
fi

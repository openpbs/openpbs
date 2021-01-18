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

cleanup() {
	cd ${etcdir}
	rm -rf ./tmpptl
}

etcdir=$(dirname $(readlink -f "$0"))
cidir=/pbssrc/ci
cd ${etcdir}
mkdir tmpptl
workdir=${etcdir}/tmpptl
cd ${workdir}
mkdir -p ptlsrc
/bin/cp -rf ${cidir}/../test/* ptlsrc/
if [ -f ptlsrc/fw/setup.py.in ]; then
	sed "s;@PBS_VERSION@;1.0.0;g" ptlsrc/fw/setup.py.in >ptlsrc/fw/setup.py
	sed "s;@PBS_VERSION@;1.0.0;g" ptlsrc/fw/ptl/__init__.py.in >ptlsrc/fw/ptl/__init__.py
fi
cd ${workdir}/ptlsrc
mkdir ../tp
__python="$(grep -rE '^#!/usr/bin/(python|env python)[23]' fw/bin/pbs_benchpress | awk -F[/" "] '{print $NF}')"
${__python} -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --prefix $(pwd)/tp -r fw/requirements.txt fw/.
cd tests
PYTHONPATH=../tp/lib/$(/bin/ls -1 ../tp/lib)/site-packages ${__python} ../tp/bin/pbs_benchpress $1 --gen-ts-tree
ret=$?
if [ ${ret} -ne 0 ]; then
	echo "Failed to generate ptl json"
	cleanup
	exit $ret
else
	mv ptl_ts_tree.json ${cidir}
fi

cleanup

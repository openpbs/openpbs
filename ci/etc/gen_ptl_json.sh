#!/bin/bash -x

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

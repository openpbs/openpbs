#!/bin/bash -xe

API_URL=https://api.github.com/repos/PBSPro/pbspro

PR_NUM=${1:-""}

cd test/fw
pip install -r requirements.txt .
pbs_config --make-ug
cd ../tests

if [ -z ${PR_NUM} ]; then
	changed_files=$(git status -s . | awk '{print $2}' | grep -v "pbs_smoketest.py" | grep -v "__init__.py")
else
	changed_files=$(curl --silent --insecure ${API_URL}/pulls/$1/files | grep '"filename": "test/tests/' | grep -v "pbs_smoketest.py" | grep -v "__init__.py" | cut -d \" -f4)
fi

if [ ! -z ${changed_files} ]; then
	for f in ${changed_files}
	do
		if [ ! -f ${f} ]; then
			continue
		fi
		ts_name=$(grep -oP 'class[\s]+(\KTest\w+)(?=\(.*\):)' ${f})
		if [ ! -z ${ts_name} ]; then
			pbs_benchpress -o ../../ptl_${ts_name}.txt -t ${ts_name}
		fi
	done
fi

pbs_benchpress -o ../../ptl_smoketag.txt --tags=smoke


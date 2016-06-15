# coding: utf-8

# Copyright (C) 1994-2016 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and distribute
# them - whether embedded or bundled with other software - under a commercial
# license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

import os
import string
import subprocess

from ptl.utils.pbs_testsuite import *


class TestQstatPerformance(PBSTestSuite):

    """
    Testing Qstat Performance
    """
    qr_list=('`qselect`','workq `qselect`', 'abcd','`qselect` workq','-s `qselect`','-f `qselect`','-f workq','-f workq `qselect`','-E `qselect`','-E workq `qselect`', '-E abcd','-E `qselect` workq','-sE `qselect`','-fE `qselect`','-fE workq','-fE workq `qselect`')
    qsub_exec = '/bin/sleep'
    qsub_exec_arg = '1000'

    def run_and_time_qstat(self, query):
	exec_dir = self.server.client_conf['PBS_EXEC']
	cmd =  'time '+exec_dir+'/bin/qstat '+query+' > /dev/null'
	ret = subprocess.Popen(cmd, stdout=None, stderr=subprocess.PIPE, shell=True)
	result = ret.communicate()
	for line in result:
	    if line == None:
		continue
	    elif line.startswith("qstat: "):
		raise RuntimeError("Qstat failed")
	    else:
		for a in line.split('\n'):
		    if a.startswith("real"):
			b  = a.split()
			return b[1]


    def submit_simple_jobs(self, user, num_jobs):
        job = Job(user)
        job.set_execargs(self.qsub_exec, self.qsub_exec_arg)
        jobidList = []
        for _ in range(num_jobs):
            jobidList.append(self.server.submit(job))

        return jobidList

    def test_with_10_jobs(self):
        """
        Submit 10 job and compute performace of qstat
        """
	num_jobs=10
        jobidList = self.submit_simple_jobs(ADMIN_USER, num_jobs)
	for qr in self.qr_list:
	    try:
		time_elapsed = self.run_and_time_qstat(qr)
		output = "time elapsed in querying - "+qr+" = "+time_elapsed
	    except RuntimeError as x:
		output = "qstat failed for "+qr
	    self.logger.info(output)

    def test_with_100_jobs(self):
        """
        Submit 100 job and compute performace of qstat
        """
	num_jobs=100
        jobidList = self.submit_simple_jobs(ADMIN_USER, num_jobs)
	for qr in self.qr_list:
	    try:
		time_elapsed = self.run_and_time_qstat(qr)
		output = "time elapsed in querying - "+qr+" = "+time_elapsed
	    except RuntimeError as x:
		output = "qstat failed for "+qr
	    self.logger.info(output)

    def test_with_1000_jobs(self):
        """
        Submit 1000 job and compute performace of qstat
        """
	num_jobs=1000
        jobidList = self.submit_simple_jobs(ADMIN_USER, num_jobs)
	for qr in self.qr_list:
	    try:
		time_elapsed = self.run_and_time_qstat(qr)
		output = "time elapsed in querying - "+qr+" = "+time_elapsed
	    except RuntimeError as x:
		output = "qstat failed for "+qr
	    self.logger.info(output)

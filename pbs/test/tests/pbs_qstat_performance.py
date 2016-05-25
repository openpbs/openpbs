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

from ptl.utils.pbs_testsuite import *


class TestQstatPerformance(PBSTestSuite):

    """
    Testing Qstat Performance
    """

    def submit_simple_jobs(self, user, num_jobs, qsub_exec, qsub_exec_arg):
        job = Job(user)
        job.set_execargs(qsub_exec, qsub_exec_arg)
        jobidList = []
        for _ in range(num_jobs):
            jobidList.append(self.server.submit(job))

        return jobidList

    def performce_measurement(self, num_jobs):
        s = self.server
        qsub_exec = '/bin/true'
        qsub_exec_arg = ''
        elapsedTime = 0

        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)

        jobidList = self.submit_simple_jobs(
            ADMIN_USER, num_jobs, qsub_exec, qsub_exec_arg)
        jobIds = ' '. join(jobidList)

        pcmd = os.path.join(self.server.client_conf[
                            'PBS_EXEC'], 'bin', 'qstat ') + jobIds

        startTime = time.time()
        ret = self.du.run_cmd(socket.gethostname(
        ), pcmd, runas=ADMIN_USER, as_script=False, level=logging.INFOCLI, logerr=True)
        if ret['rc'] != 0:
            self.logger.error('Error in executing the command ' +
                              pcmd + 'rc =' + str(ret['rc']))
            return elapsedTime
        # FIXME self.server.status doesnt support multiple job ids
        # qstat = self.server.status(JOB, id=jobIds)
        endTime = time.time()
        elapsedTime = endTime - startTime
        return elapsedTime

    def test_with_10_jobs(self):
        """
        Submit 10 job and compute performace of qstat
        """
        time_taken = self.performce_measurement(10)
        if time_taken == 0:
            self.assertTrue(time_taken)
        else:
            self.logger.info(
                "Elapsed time for qstat command for 10 job ids is " + str(time_taken))
            self.assertTrue(time_taken)

    def test_with_100_jobs(self):
        """
        Submit 100 job and compute performace of qstat
        """
        time_taken = self.performce_measurement(100)
        if time_taken == 0:
            self.assertTrue(time_taken)
        else:
            self.logger.info(
                "Elapsed time for qstat command for 100 job ids is " + str(time_taken))
            self.assertTrue(time_taken)

    def test_with_1000_jobs(self):
        """
        Submit 1000 job and compute performace of qstat
        """
        time_taken = self.performce_measurement(1000)
        if time_taken == 0:
            self.assertTrue(time_taken)
        else:
            self.logger.info(
                "Elapsed time for qstat command for 1000 job ids is " + str(time_taken))
            self.assertTrue(time_taken)

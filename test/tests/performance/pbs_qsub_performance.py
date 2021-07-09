# coding: utf-8

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

import subprocess
from tests.performance import *


class TestQsubPerformance(TestPerformance):

    def setUp(self):
        TestPerformance.setUp(self)
        attr = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)

    def submit_jobs(self, qsub_exec_arg=None, env=None):
        """
        Submits n num of jobs according to the arguments provided
        and returns submission time
        :param qsub_exec_arg: Arguments to qsub.
        :type qsub_exec_arg: String. Defaults to None.
        :param env: Environment variable to be set before submittign job.
        :type env: Dictionary. Defaults to None.
        """
        user = self.du.get_current_user()
        qsub_path = os.path.join(
                  self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub')
        common_cmd = ' -u ' + user + ' ' + qsub_path
        if qsub_exec_arg is not None:
            job_sub_arg = "sudo -E" + common_cmd + ' ' + qsub_exec_arg
        else:
            job_sub_arg = 'sudo' + common_cmd

        job_sub_arg += ' -- /bin/sleep 100'

        for _ in range(1000):
            start_time = time.time()
            subprocess.call(job_sub_arg, shell=True, env=env)
            end_time = time.time()
   
        sub_time = int(end_time - start_time)
        return sub_time

    def test_submit_large_env(self):
        """
        This test case does the following
        1. Submit 1000 jobs
        2. Set env variable with huge value
        3. Submit 1000 jobs again with -V as argument to qsub
        4. Collect time taken for both submissions
        """
        sub_time_without_env = self.submit_jobs()
        sub_time_with_env = self.submit_jobs(qsub_exec_arg="-V")

        self.logger.info(
            "Submission time without env is %d and with env is %d sec"
            % (sub_time_without_env, sub_time_with_env))
        self.perf_test_result(sub_time_without_env, "submission_time_without_env", "sec")
        self.perf_test_result(sub_time_with_env, "submission_time_with_env", "sec")

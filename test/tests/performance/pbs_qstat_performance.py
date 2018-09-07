# coding: utf-8

# Copyright (C) 1994-2019 Altair Engineering, Inc.
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

import os

from tests.performance import *


class TestQstatPerformance(TestPerformance):

    """
    Testing Qstat Performance
    """
    qstat_query_list = []
    time_command = 'time'

    def setUp(self):
        """
            Base class method overridding
            builds absolute path of commands to execute
        """
        TestPerformance.setUp(self)
        self.time_command = self.du.which(exe="time")
        if self.time_command == "time":
            self.skipTest("Time command not found")

        qselect_command = os.path.join(
            self.server.client_conf['PBS_EXEC'],
            'bin',
            'qselect')

        self.qstat_query_list.append(" `" + qselect_command + "`")
        self.qstat_query_list.append(" workq `" + qselect_command + "`")
        self.qstat_query_list.append(" `" + qselect_command + "` workq")

        self.qstat_query_list.append(" -s `" + qselect_command + "`")
        self.qstat_query_list.append(" -f `" + qselect_command + "` workq")
        self.qstat_query_list.append(" -f workq `" + qselect_command + "`")

    def compute_elapse_time(self, query):
        """
        Computes qstat time in secs"
        Arguments :
             query - qstat query to run
        return :
              -1 on qstat fail
        """
        command = self.time_command
        command += " -f \"%e\" "
        command += os.path.join(
            self.server.client_conf['PBS_EXEC'],
            'bin',
            'qstat')
        command += query

        # compute elapse time without -E option
        without_E_option = self.du.run_cmd(self.server.hostname,
                                           command,
                                           as_script=True,
                                           logerr=False)
        if without_E_option['rc'] != 0:
            return -1
        # compute elapse time with -E option
        command += " -E"
        with_E_option = self.du.run_cmd(self.server.hostname,
                                        command,
                                        as_script=True,
                                        logerr=False)

        if with_E_option['rc'] != 0:
            return -1
        self.logger.info("Without E option :" + without_E_option['err'][0])
        self.logger.info("With E option    :" + with_E_option['err'][0])
        self.assertTrue(
            (without_E_option['err'][0] >= with_E_option['err'][0]),
            "Qstat command with option : " + query + " Failed")

    def submit_jobs(self, user, num_jobs):
        """
        Submit specified number of simple jobs
        Arguments :
             user - user under which qstat to run
             num_jobs - number of jobs to submit and stat
        """
        job = Job(user)
        job.set_sleep_time(1000)
        for _ in range(num_jobs):
            self.server.submit(job)

    def submit_and_stat_jobs(self, number_jobs):
        """
        Submit specified number of simple jobs and stats jobs
        Arguments :
             num_jobs - number of jobs to submit and stat
        """
        self.submit_jobs(TEST_USER1, number_jobs)
        for query in self.qstat_query_list:
            self.compute_elapse_time(query)

    @timeout(600)
    def test_with_100_jobs(self):
        """
        Submit 100 job and compute performace of qstat
        """
        self.submit_and_stat_jobs(100)

    @timeout(600)
    def test_with_1000_jobs(self):
        """
        Submit 1000 job and compute performace of qstat
        """
        self.submit_and_stat_jobs(1000)

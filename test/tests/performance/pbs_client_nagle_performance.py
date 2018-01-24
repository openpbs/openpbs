# coding: utf-8

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

import os
import timeit

from tests.performance import *


class TestClientNagles(TestPerformance):

    """
    Testing the effect of Nagles algorithm on CLI Performance
    """
    time_command = 'time'

    def setUp(self):
        """
        Base class method overriding
        builds absolute path of commands to execute
        """
        TestPerformance.setUp(self)
        self.time_command = self.du.which(exe="time")
        if self.time_command == "time":
            self.skipTest("Time command not found")

    def tearDown(self):
        """
        cleanup jobs
        """

        TestPerformance.tearDown(self)
        self.server.cleanup_jobs(runas=ROOT_USER)

    def compute_qdel_time(self):
        """
        Computes qdel time in secs"
        return :
              -1 on qdel fail
        """
        qsel_list = self.server.select()
        qsel_list = " ".join(qsel_list)
        command = self.time_command
        command += " -f \"%e\" "
        command += os.path.join(self.server.client_conf['PBS_EXEC'],
                                'bin',
                                'qdel ')
        command += qsel_list
        # compute elapse time without -E option
        qdel_perf = self.du.run_cmd(self.server.hostname,
                                    command,
                                    as_script=True,
                                    runas=TEST_USER1,
                                    logerr=False)
        if qdel_perf['rc'] != 0:
            return -1

        return qdel_perf['err'][0]

    def submit_jobs(self, user, num_jobs):
        """
        Submit specified number of simple jobs
        Arguments :
             user - user under which to submit jobs
             num_jobs - number of jobs to submit
        """
        job = Job(user)
        job.set_sleep_time(1)
        for _ in range(num_jobs):
            self.server.submit(job)

    @timeout(600)
    def test_qdel_nagle_perf(self):
        """
        Submit 500 jobs, measure qdel performace before/after adding managers
        """

        # Adding to managers ensures that packets are larger than 1023 bytes
        # that triggers Nagle's algorithm which slows down the communication.
        # Effect on TCP seems irreversible till server is restarted, so in
        # this test case we restart server so that any effects from earlier
        # test cases/runs do not interfere

        # Baseline qdel performance with scheduling false and managers unset
        # Restart server to ensure no effect from earlier tests/operations
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_UNSET, SERVER, 'managers')
        self.server.restart()

        self.submit_jobs(TEST_USER1, 500)
        qdel_perf = self.compute_qdel_time()
        self.assertTrue((qdel_perf != -1), "qdel command failed")

        # Add to the managers list so that TCP packets are now larger and
        # triggers Nagle's
        manager = TEST_USER1.name + '@' + self.server.hostname
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'managers': (INCR, manager)}, sudo=True)

        # Remeasure the qdel performance
        self.submit_jobs(TEST_USER1, 500)
        qdel_perf2 = self.compute_qdel_time()
        self.assertTrue((qdel_perf2 != -1), "qdel command failed")

        self.logger.info("qdel performance: " + str(qdel_perf))
        self.logger.info(
            "qdel performance after setting manager: " + str(qdel_perf2))

    @timeout(600)
    def test_qsub_perf(self):
        """
        Test that qsub performance have improved when run
        with -f option
        """

        # Restart server
        self.server.restart()

        # Submit a job for 500 times and timeit
        cmd = os.path.join(
            self.server.client_conf['PBS_EXEC'],
            'bin',
            'qsub -- /bin/true >/dev/null')
        start_time = timeit.default_timer()
        for x in range(1, 500):
            rv = self.du.run_cmd(self.server.hostname, cmd)
            self.assertTrue(rv['rc'] == 0)
        elap_time1 = timeit.default_timer() - float(start_time)

        # submit a job with -f for 500 times and timeit
        cmd = os.path.join(
            self.server.client_conf['PBS_EXEC'],
            'bin',
            'qsub -f -- /bin/true >/dev/null >/dev/null')
        start_time = timeit.default_timer()
        for x in range(1, 500):
            rv = self.du.run_cmd(self.server.hostname,
                                 cmd)
            self.assertTrue(rv['rc'] == 0)
        elap_time2 = timeit.default_timer() - float(start_time)
        self.logger.info("Time taken by qsub -f is " + str(elap_time2) +
                         " and time taken by qsub is " + str(elap_time1))

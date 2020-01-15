# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

from tests.selftest import *


class TestJobCleanup(TestSelf):
    """
    Tests for checking the job cleanup functionality in PTL
    """

    @timeout(10000)
    def test_cleanup_perf(self):
        """
        Test the time that it takes to cleanup a large number of jobs
        """
        num_jobs = 10000

        # Set npcus to a number that'll allow half the jobs to run
        ncpus = int(num_jobs / 2)
        a = {'resources_available.ncpus': str(ncpus)}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        for i in range(num_jobs):
            j = Job()
            j.set_sleep_time(1000)
            self.server.submit(j)

        self.scheduler.run_scheduling_cycle()

        # Measure job cleanup performance
        t1 = time.time()
        self.server.cleanup_jobs()

        # Restart the mom
        self.mom.restart()
        t2 = time.time()

        self.logger.info("Time taken for job cleanup " + str(t2 - t1))

    def test_del_large_num_jobs(self):
        """
        Test that the delete jobs functionality works correctly with large
        number of jobs
        """
        num_jobs = 1000
        a = {'resources_available.ncpus': 1,
             'resources_available.mem': '2gb'}
        self.server.create_vnodes('vnode', a, num_jobs, self.mom,
                                  sharednode=False, expect=False)
        self.server.expect(NODE, {'state=free': (GE, num_jobs)})

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        for i in range(num_jobs):
            j = Job(TEST_USER)
            self.server.submit(j)

        self.scheduler.run_scheduling_cycle()
        self.server.expect(JOB, {'job_state=R': num_jobs}, max_attempts=120)

        self.server.cleanup_jobs()
        self.server.expect(SERVER, {'total_jobs': 0})

    def test_del_queued_jobs(self):
        """
        Test that the delete jobs functionality works correctly with large
        number of queued jobs that do not have processes associated with them.
        """
        num_jobs = 1000
        a = {'resources_available.ncpus': 1,
             'resources_available.mem': '2gb'}
        self.server.create_vnodes('vnode', a, num_jobs, self.mom,
                                  sharednode=False, expect=False)
        self.server.expect(NODE, {'state=free': (GE, num_jobs)})

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        for i in range(num_jobs):
            j = Job(TEST_USER, attrs={ATTR_l + '.select': '1:ncpus=4'})
            self.server.submit(j)

        self.scheduler.run_scheduling_cycle()
        self.server.expect(JOB, {'job_state=Q': num_jobs}, max_attempts=120)

        self.server.cleanup_jobs()
        self.server.expect(SERVER, {'total_jobs': 0})

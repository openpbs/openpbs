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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

import os

from tests.performance import *


class TestJobEquivClassPerf(TestPerformance):
    """
    Test job equivalence class performance
    """

    def setUp(self):
        TestPerformance.setUp(self)
        a = {'resources_available.ncpus': 1, 'resources_available.mem': '8gb'}
        self.server.create_vnodes('vnode', a, 10000, self.mom,
                                  sharednode=False)

    @timeout(1000)
    def test_basic(self):
        """
        Test basic functionality of job equivalence classes.
        Pre test: one class per job
        Post test: one class for all jobs
        """

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        num_jobs = 5000
        jids = []
        # Create num_jobs different equivalence classes.  These jobs can't run
        # because there aren't 2cpu nodes.  This bypasses the quick
        # 'can I run?' check the scheduler does.  It will better show the
        # equivalence class performance.
        for n in range(num_jobs):
            a = {'Resource_List.select': str(n + 1) + ':ncpus=2',
                 "Resource_List.place": "free"}
            J = Job(TEST_USER, attrs=a)
            jid = self.server.submit(J)
            jids += [jid]

        t = time.time()

        # run only one cycle
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # wait for cycle to finish
        m = self.scheduler.log_match("Leaving Scheduling Cycle", starttime=t,
                                     max_attempts=120)
        self.assertTrue(m)

        c = self.scheduler.cycles(lastN=1)[0]
        cycle1_time = c.end - c.start

        # Make all jobs into one equivalence class
        a = {'Resource_List.select': str(num_jobs) + ":ncpus=2",
             "Resource_List.place": "free"}
        for n in range(num_jobs):
            self.server.alterjob(jids[n], a)

        t = time.time()

        # run only one cycle
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # wait for cycle to finish
        m = self.scheduler.log_match("Leaving Scheduling Cycle", starttime=t,
                                     max_attempts=120)
        self.assertTrue(m)

        c = self.scheduler.cycles(lastN=1)[0]
        cycle2_time = c.end - c.start

        self.logger.info('Cycle 1: %d Cycle 2: %d Cycle time difference: %d' %
                         (cycle1_time, cycle2_time, cycle1_time - cycle2_time))
        self.assertTrue(cycle1_time > cycle2_time)

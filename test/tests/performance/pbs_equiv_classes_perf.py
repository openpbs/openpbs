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


class TestJobEquivClassPerf(TestPerformance):

    """
    Test job equivalence class performance
    """

    def setUp(self):
        TestPerformance.setUp(self)
        self.scheduler.set_sched_config({'log_filter': 2048})

        # Create vnodes
        a = {'resources_available.ncpus': 1, 'resources_available.mem': '8gb'}
        self.server.create_vnodes('vnode', a, 10000, self.mom,
                                  sharednode=False)

    def run_n_get_cycle_time(self):
        """
        Run a scheduling cycle and calculate its duration
        """

        t = int(time.time())

        # Run only one cycle
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # Wait for cycle to finish
        self.scheduler.log_match("Leaving Scheduling Cycle", starttime=t,
                                 max_attempts=300, interval=3)

        c = self.scheduler.cycles(lastN=1)[0]
        cycle_time = c.end - c.start

        return cycle_time

    @timeout(2000)
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

        cycle1_time = self.run_n_get_cycle_time()

        # Make all jobs into one equivalence class
        a = {'Resource_List.select': str(num_jobs) + ":ncpus=2",
             "Resource_List.place": "free"}
        for n in range(num_jobs):
            self.server.alterjob(jids[n], a)

        cycle2_time = self.run_n_get_cycle_time()

        self.logger.info('Cycle 1: %d Cycle 2: %d Cycle time difference: %d' %
                         (cycle1_time, cycle2_time, cycle1_time - cycle2_time))
        self.assertGreaterEqual(cycle1_time, cycle2_time)
        time_diff = cycle1_time - cycle2_time
        self.perf_test_result(cycle1_time, "different_equiv_class", "sec")
        self.perf_test_result(cycle2_time, "single_equiv_class", "sec")
        self.perf_test_result(time_diff,
                              "time_diff_bn_single_diff_equiv_classes", "sec")

    @timeout(10000)
    def test_server_queue_limit(self):
        """
        Test the performance with hard and soft limits
        on resources
        """

        # Create workq2
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='workq2')

        # Set queue limit
        a = {
            'max_run': '[o:PBS_ALL=100],[g:PBS_GENERIC=20],\
                       [u:PBS_GENERIC=20],[g:tstgrp01 = 8],[u:%s=10]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, QUEUE,
                            a, id='workq2')

        a = {'max_run_res.ncpus':
             '[o:PBS_ALL=100],[g:PBS_GENERIC=50],\
             [u:PBS_GENERIC=20],[g:tstgrp01=13],[u:%s=12]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq2')

        a = {'max_run_res_soft.ncpus':
             '[o:PBS_ALL=100],[g:PBS_GENERIC=30],\
             [u:PBS_GENERIC=10],[g:tstgrp01=10],[u:%s=10]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq2')

        # Set server limits
        a = {
            'max_run': '[o:PBS_ALL=100],[g:PBS_GENERIC=50],\
            [u:PBS_GENERIC=20],[g:tstgrp01=13],[u:%s=13]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'max_run_soft':
             '[o:PBS_ALL=50],[g:PBS_GENERIC=25],[u:PBS_GENERIC=10],\
             [g:tstgrp01=10],[u:%s=10]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Turn scheduling off
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'false'})

        # Submit jobs as pbsuser1 from group tstgrp01 in workq2
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP1, ATTR_q: 'workq2'}
            J = Job(TEST_USER1, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for ~100 classes
        cyc1 = self.run_n_get_cycle_time()

        # Submit jobs as pbsuser1 from group tstgrp02 in workq2
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP2, ATTR_q: 'workq2'}
            J = Job(TEST_USER1, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for ~200 classes
        cyc2 = self.run_n_get_cycle_time()

        # Submit jobs as pbsuser2 from tstgrp01 in workq2
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP1, ATTR_q: 'workq2'}
            J = Job(TEST_USER2, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for ~300 classes
        cyc3 = self.run_n_get_cycle_time()

        # Submit jobs as pbsuser2 from tstgrp03 in workq2
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP3, ATTR_q: 'workq2'}
            J = Job(TEST_USER2, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for ~400 classes
        cyc4 = self.run_n_get_cycle_time()

        # Submit jobs as pbsuser1 from tstgrp01 in workq
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP1, ATTR_q: 'workq'}
            J = Job(TEST_USER1, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for ~500 classes
        cyc5 = self.run_n_get_cycle_time()

        # Submit jobs as pbsuser1 from tstgrp02 in workq
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP2, ATTR_q: 'workq'}
            J = Job(TEST_USER1, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for 60k jobs for ~600 classes
        cyc6 = self.run_n_get_cycle_time()

        # Submit jobs as pbsuser2 from tstgrp01 in workq
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP1, ATTR_q: 'workq'}
            J = Job(TEST_USER2, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for 70k jobs for ~700 classes
        cyc7 = self.run_n_get_cycle_time()

        # Submit jobs as pbsuser2 from tstgrp03 in workq
        for x in range(100):
            a = {'Resource_List.select': '1:ncpus=2',
                 'Resource_List.walltime': int(x),
                 'group_list': TSTGRP3, ATTR_q: 'workq'}
            J = Job(TEST_USER2, attrs=a)
            for y in range(100):
                self.server.submit(J)

        # Get time for 80k jobs for ~800 classes
        cyc8 = self.run_n_get_cycle_time()

        # Print the time taken for all the classes and compare
        # it against previous releases
        self.logger.info("time taken for \n100 classes is %d"
                         "\n200 classes is %d,"
                         "\n300 classes is %d,"
                         "\n400 classes is %d,"
                         "\n500 classes is %d,"
                         "\n600 classes is %d,"
                         "\n700 classes is %d,"
                         "\n800 classes is %d"
                         % (cyc1, cyc2, cyc3, cyc4, cyc5, cyc6, cyc7, cyc8))
        self.perf_test_result(cyc1, "100_class_time", "sec")
        self.perf_test_result(cyc2, "200_class_time", "sec")
        self.perf_test_result(cyc3, "300_class_time", "sec")
        self.perf_test_result(cyc4, "400_class_time", "sec")
        self.perf_test_result(cyc5, "500_class_time", "sec")
        self.perf_test_result(cyc6, "600_class_time", "sec")
        self.perf_test_result(cyc7, "700_class_time", "sec")
        self.perf_test_result(cyc8, "800_class_time", "sec")

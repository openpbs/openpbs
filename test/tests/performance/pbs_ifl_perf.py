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

from tests.performance import *


class TestIFLPerf(TestPerformance):
    @timeout(3600)
    def test_attr_update_perf_from_sched(self):
        """
        Test performance of job attribute updates from sched,
        tests pbs_alterjob & PBSD_manager
        """
        # Set ncpus to 1
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # Submit 10k jobs
        for _ in range(10000):
            j = Job(TEST_USER)
            self.server.submit(j)

        t1 = time.time()
        self.scheduler.run_scheduling_cycle()
        self.scheduler.log_match("Leaving Scheduling Cycle", starttime=t1,
                                 max_attempts=1200, interval=1)

        c = self.scheduler.cycles(lastN=1)[0]
        td = c.end - c.start

        self.logger.info("Time taken by the sched cycle: " + str(td))

        # Delete all jobs
        self.server.cleanup_jobs()

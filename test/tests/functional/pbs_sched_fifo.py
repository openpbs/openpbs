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

from tests.functional import *


class TestSchedFifo(TestFunctional):
    """
    Test suite for PBSPro's FIFO scheduling
    """
    def test_sched_fifo(self):
        """
        Check that FIFO works.
        """

        # Configure sched for FIFO
        self.scheduler.set_sched_config({'strict_ordering': 'True',
                                         'by_queue': 'False',
                                         'help_starving_jobs': 'False'})

        # Create a new queue to test FIFO
        queue_attrib = {ATTR_qtype: 'execution',
                        ATTR_start: 'True',
                        ATTR_enable: 'True'}
        self.server.manager(MGR_CMD_CREATE,
                            QUEUE, queue_attrib, id="workq2")

        # Set ncpus to 2 so it is easy to test, and scheduling off
        self.server.manager(MGR_CMD_SET,
                            NODE, {'resources_available.ncpus': 2},
                            self.mom.shortname)
        self.server.manager(MGR_CMD_SET,
                            SERVER, {'scheduling': 'False'})

        # Submit 3 jobs: j1 (workq), j2 (workq2), j3 (workq)
        j1 = Job(TEST_USER, attrs={
            ATTR_queue: "workq"})
        j2 = Job(TEST_USER, attrs={
            ATTR_queue: "workq2"})
        j3 = Job(TEST_USER, attrs={
            ATTR_queue: "workq"})

        j_id1 = self.server.submit(j1)
        j_id2 = self.server.submit(j2)
        j_id3 = self.server.submit(j3)

        # Turn scheduling on again
        self.server.manager(MGR_CMD_SET,
                            SERVER, {'scheduling': 'True'})

        # j1 and j2 should be running
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j_id1, max_attempts=10)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j_id2, max_attempts=10)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=j_id3, max_attempts=10)

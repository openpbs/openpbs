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


class TestPreemption(TestFunctional):
    """
    Contains tests for scheduler's preemption functionality
    """

    def test_preempted_never_run(self):
        """
        Test that a preempted job is not marked as "Job will never run"
        """
        # Set ncpus to 2
        attr = {'resources_available.ncpus': '2'}
        self.server.manager(MGR_CMD_SET, NODE, attr, self.mom.shortname,
                            expect=True)

        # Create a high priority queue
        attr = {"queue_type": "Execution", "Priority": 200, "started": "True",
                "enabled": "True"}
        queue_id_h = "highp"
        self.server.manager(MGR_CMD_CREATE, QUEUE, attr, id=queue_id_h,
                            logerr=False)

        # Create a low priority queue
        attr = {"queue_type": "Execution", "Priority": 100, "started": "True",
                "enabled": "True"}
        queue_id_l = "lowp"
        self.server.manager(MGR_CMD_CREATE, QUEUE, attr, id=queue_id_l,
                            logerr=False)

        # Submit a job to low priority queue
        attr = {"Resource_List.ncpus": 2,
                "queue": queue_id_l,
                "Resource_List.walltime": "00:10:00"}
        j = Job(TEST_USER, attrs=attr)
        jidl = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jidl)

        # Submit a job to high priority queue
        attr["queue"] = queue_id_h
        j = Job(TEST_USER, attrs=attr)
        jidh = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jidh)

        # The low priority job should be preempted
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jidl)

        # Check whether scheduler marked the preempted job as "will never run"
        self.scheduler.log_match(
            jidl + ";Job will never run", existence=False, max_attempts=5)

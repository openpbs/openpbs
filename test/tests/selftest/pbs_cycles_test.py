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


class PBSTestCycle(TestSelf):
    """
    Tests to check that the cycle function returns correct information
    for schedulers
    """

    def test_cycle_multi_sched(self):
        """
        Test that scheduler.cycle() reads the correct multisched log file
        This test will check the start time and political order from the
        cycles() output to test the correct log file is being read.
        """
        # Create a queue, vnode and link them to the newly created sched
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq')

        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vnode', a, 1, self.mom)

        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq')
        self.server.manager(MGR_CMD_SET, NODE, p1, id='vnode[0]')

        a = {'partition': 'P1',
             'sched_host': self.server.hostname,
             'sched_port': '15050'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc")
        self.scheds['sc'].create_scheduler()
        self.scheds['sc'].start()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc")
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047}, id='sc')

        # Turn off scheduling for all the scheds.
        for name in self.scheds:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'False'}, id=name)
        st = time.time()

        # submit jobs and check political order
        a = {ATTR_queue: 'wq'}

        j1 = Job(TEST_USER1, attrs=a)
        jid1 = self.server.submit(j1)
        j2 = Job(TEST_USER1, attrs=a)
        jid2 = self.server.submit(j2)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id='sc')
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        cycles = self.scheds['sc'].cycles(start=st, firstN=1)
        self.assertNotEqual(len(cycles), 0)
        cycle = cycles[0]

        political_order = cycle.political_order
        self.assertNotEqual(len(political_order), 0)
        firstconsidered = political_order[0]

        # Check that the cycle start time is after st
        self.assertGreater(cycle.start, st)

        # check the first considered is jid1
        self.assertEqual(firstconsidered, jid1.split('.')[0])

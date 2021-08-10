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


from tests.functional import *


class TestNodeSleepState(TestFunctional):

    """
    This test suite contains regression tests for node sleep state
    """

    def test_node_set_sleep_state(self):
        """
        Tests node setting state to sleep
        """
        self.server.manager(MGR_CMD_SET, NODE, {'state': 'sleep'},
                            id=self.mom.shortname)
        self.server.expect(NODE, {'state': 'sleep'})
        # submit a job and it should remain in Q state
        j = Job(self.du.get_current_user())
        self.jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=self.jid)

    def test_node_state_sleep_to_free_manual(self):
        """
        Tests setting node state to free from sleep manually
        """
        self.test_node_set_sleep_state()
        self.server.manager(MGR_CMD_SET, NODE, {'state': 'free'},
                            id=self.mom.shortname)
        self.server.expect(NODE, {'state': 'free'})
        self.server.expect(JOB, {'job_state': 'R'}, id=self.jid)

    def test_node_state_sleep_to_free_on_node_restart(self):
        """
        Tests setting node state to free from sleep on node restart
        """
        self.test_node_set_sleep_state()
        self.mom.stop()
        self.server.expect(NODE, {'state': 'down,sleep'})
        self.mom.start()
        self.server.expect(NODE, {'state': 'free'})
        self.server.expect(JOB, {'job_state': 'R'}, id=self.jid)

    def test_node_state_offline_and_sleep_restart(self):
        """
        Tests setting node state to offline and sleep on restart node
        will still remain in offline
        """
        self.test_node_set_sleep_state()
        self.server.manager(MGR_CMD_SET, NODE, {'state': (INCR, 'offline')},
                            id=self.mom.shortname)
        self.mom.stop()
        self.server.expect(NODE, {'state': 'down,offline,sleep'})
        self.mom.start()
        self.server.expect(NODE, {'state': 'offline'})

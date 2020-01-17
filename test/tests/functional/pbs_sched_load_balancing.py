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

from tests.functional import *


class TestSchedLoadBalancing(TestFunctional):
    """
    Test suite for PBSPro's Scheduler load balancing
    """
    def setUp(self):
        """
        Set scheduler load_balancing
        """
        TestFunctional.setUp(self)
        self.scheduler.set_sched_config({'load_balancing': 'true	ALL'})

    def test_load_bal_node_ip(self):
        """
        This test case tests scheduler load balancing
        feature, when node is added using ip address.
        """
        # Check current load in system
        cmd = os.path.join(self.server.pbs_conf[
                           'PBS_EXEC'], 'unsupported', 'pbs_rmget')
        cmd += ' -m ' + self.mom.hostname + ' loadave '
        ret = self.du.run_cmd(self.mom.hostname, cmd)
        current_load = float(ret['out'][0].split('=')[1])
        # Considering our job will need 1 cpu
        ideal_load = current_load + 1
        max_load = current_load + 2
        self.mom.add_config({'$ideal_load': ideal_load})
        self.mom.add_config({'$max_load': max_load})
        self.server.manager(MGR_CMD_DELETE, NODE, None, '')
        ipaddr = socket.gethostbyname(self.mom.hostname)
        self.server.manager(MGR_CMD_CREATE, NODE,  id=ipaddr)
        self.server.expect(NODE, {'state=free': 1})

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

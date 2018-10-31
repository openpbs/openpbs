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


class TestNodeJobsRestart(TestFunctional):
    """
    Make sure that jobs remain on the node's jobs line after a server restart
    """

    def test_node_jobs_restart(self):
        """
        Make sure that jobs attribute remains set properly after the
        server is restarted
        """
        J = Job()
        jid = self.server.submit(J)
        self.server.expect(JOB, 'exec_vnode', op=SET, id=jid)

        job_nodes = J.get_vnodes(J.exec_vnode)
        svr_nodes = self.server.status(NODE, id=job_nodes[0])
        msg = 'Job ' + jid + ' not in node ' + job_nodes[0] + '\'s jobs line'
        self.assertTrue(jid in svr_nodes[0]['jobs'], msg)

        self.server.restart()

        self.server.expect(NODE, 'jobs', op=SET, id=job_nodes[0])
        svr_nodes2 = self.server.status(NODE, id=job_nodes[0])
        self.assertTrue(jid in svr_nodes2[0]['jobs'], msg)

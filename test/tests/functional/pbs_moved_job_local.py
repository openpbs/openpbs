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


class TestMovedJobLocal(TestFunctional):
    """
    This test suite tests moved jobs between two queues
    """

    def test_moved_job_acl_hosts_allow(self):
        """
        This test suite verifies that job can be moved
        into queue with acl_host_enabled.
        """
        a = {'queue_type': 'Execution',
             'enabled': 'True',
             'started': 'True',
             'acl_host_enable': 'True',
             'acl_hosts': self.servers.keys()[0]}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='testq')
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.movejob(jid, 'testq', runas=TEST_USER)
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(JOB, {ATTR_queue: 'testq', 'job_state': 'R'},
                           attrop=PTL_AND)

    def test_moved_job_acl_hosts_denial(self):
        """
        This test suite verifies that job can not be moved
        into queue with acl_host_enabled without the right hostname.
        """
        a = {'queue_type': 'Execution',
             'enabled': 'True',
             'started': 'True',
             'acl_host_enable': 'True',
             'acl_hosts': 'foo'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='testq')
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        err = "Access from host not allowed, or unknown host " + jid
        with self.assertRaises(PbsMoveError) as e:
            self.server.movejob(jid, 'testq', runas=TEST_USER)
        self.assertIn(err, e.exception.msg[0])

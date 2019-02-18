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

from tests.functional import *


class TestQstatTwoServers(TestFunctional):

    """
    This test suite checks that qstat works correctly when there
    are 2 PBS servers set up
    """

    def setUp(self):
        if len(self.servers) != 2 or self.server.client in self.servers:
            self.skipTest("This test needs two servers and one client")
        # Because of a bug in PTL, having moms on respective server hosts
        # don't work, so the server hosts need to be passed as nomom hosts
        svrnames = self.servers.keys()
        if "nomom" not in self.conf or \
                svrnames[0] not in self.conf["nomom"] or \
                svrnames[1] not in self.conf["nomom"]:
            self.skipTest("This test needs the server hosts to be passed"
                          " as nomom hosts: -p servers=<host1>:<host2>,"
                          "nomom=<host1>:<host2>")
        TestFunctional.setUp(self)

    def test_qstat_req_server(self):
        _m = self.server.get_op_mode()
        if _m != PTL_CLI:
            self.skipTest("Test only supported for CLI mode")

        self.server1 = self.servers.values()[0]
        self.server2 = self.servers.values()[1]
        a = {'scheduling': 'false', 'flatuid': 'true'}
        self.server1.manager(MGR_CMD_SET, SERVER, a)
        self.server2.manager(MGR_CMD_SET, SERVER, a)

        j = Job(TEST_USER)
        jid = self.server1.submit(j)
        destination = '@%s' % self.server2.hostname
        self.server1.movejob(jobid=jid, destination=destination)
        self.server1.status(JOB, id=jid + '@%s' % self.server2.hostname,
                            runas=str(TEST_USER))
        expmsg = "Type 19 request received"\
                 " from %s@%s" % (str(TEST_USER), self.server.client)
        self.server1.log_match(msg=expmsg, existence=False, max_attempts=5)
        self.server2.log_match(msg=expmsg)

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


class QstatTest(TestFunctional):

    """
    This test suite checks whether qstat sends the
    status request to the correct server or not for
    requests like job_id.serverA@serverB
    """

    def setUp(self):
        if len(self.servers) != 2 or self.server.client in self.servers:
            self.skipTest("This test needs two servers and one client")
        TestFunctional.setUp(self)
        self.server1 = self.servers.values()[0]
        self.server2 = self.servers.values()[1]
        a = {'scheduling': 'false', 'flatuid': 'true'}
        self.server1.manager(MGR_CMD_SET, SERVER, a)
        self.server2.manager(MGR_CMD_SET, SERVER, a)

    def test_qstat_req_server(self):
        j = Job(TEST_USER)
        jid = self.server1.submit(j)
        destination = '@%s' % self.server2.hostname
        self.server1.movejob(jobid=jid, destination=destination)
        self.client_conf = self.du.parse_pbs_config(
            hostname=self.server.client)
        self.du.set_pbs_config(self.server.client, confs={'PBS_SERVER': ''})
        self.server1.status(JOB, id=jid+'@%s' % self.server2.hostname,
                            runas=str(TEST_USER))
        expmsg = "Type 19 request received"\
                 " from %s@%s" % (str(TEST_USER), self.server.client)
        self.server1.log_match(msg=expmsg, existence=False, max_attempts=5)
        self.server2.log_match(msg=expmsg)

    def tearDown(self):
        a = {'PBS_SERVER': self.client_conf['PBS_SERVER']}
        self.du.set_pbs_config(self.server.client, confs=a)
        TestFunctional.tearDown(self)

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


class TestPbsnodes(TestFunctional):

    """
    This test suite contains regression tests for pbsnodes command.
    """

    def setUp(self):
        TestFunctional.setUp(self)

        self.header = ['vnode', 'state', 'OS', 'hardware', 'host',
                       'queue', 'mem', 'ncpus', 'nmics', 'ngpus', 'comment']
        self.pbs_exec = self.server.pbs_conf['PBS_EXEC']
        self.pbsnodes = [os.path.join(self.pbs_exec, 'bin', 'pbsnodes')]
        self.svrname = self.server.pbs_server_name
        self.hostA = self.moms.values()[0].shortname

    def test_pbsnodes_S(self):
        """
        This verifies that 'pbsnodes -S' results in a usage message
        """
        pbsnodes_S = self.pbsnodes + ['-S']
        out = self.du.run_cmd(self.svrname, cmd=pbsnodes_S)
        self.logger.info(out['err'][0])
        self.assertIn('usage:', out['err'][
                      0], 'usage not found in error message')

    def test_pbsnodes_S_host(self):
        """
        This verifies that 'pbsnodes -S <host>' results in an output
        with correct headers.
        """
        pbsnodes_S_host = self.pbsnodes + ['-S', self.hostA]
        out1 = self.du.run_cmd(self.svrname, cmd=pbsnodes_S_host)
        self.logger.info(out1['out'])
        for hdr in self.header:
            self.assertIn(
                hdr, out1['out'][0],
                "header %s not found in output" % hdr)

    def test_pbsnodes_aS(self):
        """
        This verifies that 'pbsnodes -aS' results in an output
        with correct headers.
        """
        pbsnodes_aS = self.pbsnodes + ['-aS']
        out2 = self.du.run_cmd(self.svrname, cmd=pbsnodes_aS)
        self.logger.info(out2['out'])
        for hdr in self.header:
            self.assertIn(
                hdr, out2['out'][0],
                "header %s not found in output" % hdr)

    def test_pbsnodes_av(self):
        """
        This verifies the values of last_used_time in 'pbsnodes -av'
        result before and after server shutdown, once a job submitted.
        """
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid = self.server.submit(j)
        self.server.accounting_match("E;%s;" % jid)
        prev = self.server.status(NODE, 'last_used_time')[0]['last_used_time']
        self.logger.info("Restarting server")
        self.server.restart()
        self.assertTrue(self.server.isUp(), 'Failed to restart Server Daemon')
        now = self.server.status(NODE, 'last_used_time')[0]['last_used_time']
        self.logger.info("Before: " + prev + ". After: " + now + ".")
        self.assertEquals(prev.strip(), now.strip(),
                          'Last used time mismatch after server restart')

# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from tests.functional import *


class Test_acl_host_moms(TestFunctional):
    """
    This test suite is for testing the server attribute acl_host_moms_enable
    and this test requires two moms.
    """

    def setUp(self):
        """
        Determine the remote host and set acl_host_enable = True
        """

        TestFunctional.setUp(self)

        if len(self.moms) != 2:
            self.skip_test('test requires two MoMs as input, ' +
                           '  use -p moms=<mom1>:<mom2>')

        # PBSTestSuite returns the moms passed in as parameters as dictionary
        # of hostname and MoM object
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        self.remote_host = None

        if not self.du.is_localhost(self.hostA):
            self.remote_host = self.hostA

        if not self.du.is_localhost(self.hostB):
            self.remote_host = self.hostB

        self.assertTrue(self.remote_host)

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_enable': True}, expect=True)

        self.pbsnodes_cmd = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'pbsnodes') + ' -a'

    def test_acl_host_moms_enable(self):
        """
        Set acl_host_moms_enable = True and check whether or not the remote
        host is able run pbsnodes.
        """

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_moms_enable': True}, expect=True)

        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertEqual(ret['rc'], 0)

    def test_acl_host_moms_disable(self):
        """
        Set acl_host_moms_enable = False and check whether or not the remote
        host is forbidden to run pbsnodes.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_moms_enable': False}, expect=True)

        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertEqual(ret['rc'], 1)

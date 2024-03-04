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


class Test_acl_host_server(TestFunctional):
    """
    This test suite is for testing the subnets in server's
    attribute acl_hosts. This test requires remote client.
    """

    def setUp(self):
        """
        Determine the server ip and remote host
        """

        TestFunctional.setUp(self)

        usage_string = 'test requires a remote client as input,' + \
                       ' use -p client=<client>'

        self.serverip = socket.gethostbyname(self.server.hostname)

        if not self.du.is_localhost(self.server.client):
            self.remote_host = socket.getfqdn(self.server.client)
        else:
            self.skip_test(usage_string)

        self.assertTrue(self.remote_host)

        self.pbsnodes_cmd = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'pbsnodes') + ' -av' \
            + ' -s ' + self.server.hostname

    def test_acl_subnet_enable_allow(self):
        """
        Set acl_host_enable = True, subnet to server ip with the mask
        255.255.0.0 or 16 and check whether or not the remote host
        is able to run pbsnodes. It should allow.
        """

        a = {"acl_host_enable": True,
             "acl_hosts": self.serverip + "/255.255.0.0"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertEqual(ret['rc'], 0)

        a = {"acl_host_enable": True,
             "acl_hosts": self.serverip + "/16"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertEqual(ret['rc'], 0)

    def test_acl_subnet_enable_refuse(self):
        """
        Set acl_host_enable = True, subnet to server ip with the mask
        255.255.255.255 or 32 and check whether or not the remote host
        is able to run pbsnodes. It should refuse.
        """

        a = {"acl_host_enable": True,
             "acl_hosts": self.serverip + "/255.255.255.255"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertNotEqual(ret['rc'], 0)

        a = {"acl_host_enable": True,
             "acl_hosts": self.serverip + "/32"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertNotEqual(ret['rc'], 0)

    def tearDown(self):
        """
        Unset the acl attributes so tearDown can process on remote host.
        """

        a = ["acl_host_enable", "acl_hosts"]
        self.server.manager(MGR_CMD_UNSET, SERVER, a)

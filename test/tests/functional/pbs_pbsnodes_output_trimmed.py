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
import socket


class TestPbsnodesOutputTrimmed(TestFunctional):
    """
    This test suite tests pbsnodes executable with -l
    and makes sure that the node names are not trimmed.
    """
    temp_list = []
    is_host_file_changed = False

    @classmethod
    def hostname_resolves(self, hostname):
        try:
            socket.gethostbyname(hostname)
            return 1
        except socket.error:
            return 0

    def test_pbsnodes_output(self):
        """
        This method adds a new entry to /etc/hosts and creates
        a mom with name more than 20 characters, then makes the
        node offline and checks the pbsnodes -l output and
        makes sure it is not trimmed
        """
        with open("/etc/hosts", "r")as fd:
            self.temp_list = fd.readlines()
        pbsnodes = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                "bin", "pbsnodes")
        hname = "long123456789012345678901234567890.pbspro.com"
        ret = self.hostname_resolves(hname)
        if ret == 0:
            with open("/etc/hosts", "a") as fd:
                tmpentry = '127.0.0.1' + " " + hname + " " + hname
                fd.write(tmpentry)
                fd.write("\n")
            self.is_host_file_changed = True
        self.server.manager(MGR_CMD_DELETE, NODE, None, '')
        self.server.manager(MGR_CMD_CREATE, NODE,
                            {'resources_available.ncpus': '1'}, hname)
        command = pbsnodes + " -l"
        rc = self.du.run_cmd(cmd=command, sudo=True)
        res = rc['out']
        self.assertEqual(res[0].split(" ")[0], hname)
        self.server.manager(MGR_CMD_DELETE, NODE, None, '')

    def tearDown(self):
        if self.is_host_file_changed:
            with open("/etc/hosts", "w") as fd:
                fd.writelines(self.temp_list)

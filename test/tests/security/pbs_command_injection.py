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

from tests.security import *


class Test_command_injection(TestSecurity):
    """
    This test suite is for testing command injection
    """
    def setUp(self):
        TestSecurity.setUp(self)

    def test_pbs_rcp_command_injection(self):
        """
        """
        cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'sbin', 'pbs_rcp')
        cmd_opt = \
            [cmd, 'test@1.1.1.1:/tmp/abc;cat /etc/passwd test@2.2.2.2:/tmp']
        ret = self.du.run_cmd(self.server.hostname, cmd=cmd_opt, logerr=False)

        self.assertNotEqual(ret['rc'], 0,
                            'pbs_rcp returned with success')

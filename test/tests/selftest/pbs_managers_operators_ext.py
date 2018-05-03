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

from tests.selftest import *


class ManagersOperators(TestSelf):

    """
    This test suite contains tests related to managers and operators

    """
    def test_managers_unset_setup(self):
        """
        Additional managers users, except current user should get unset
        after test setUp run
        """
        runas = ROOT_USER
        current_usr = pwd.getpwuid(os.getuid())[0]
        attr = {ATTR_managers: current_usr + '@*'}
        self.server.expect(SERVER, attrib=attr)
        mgr_user1 = str(TEST_USER)
        mgr_user2 = str(TEST_USER1)
        a = {ATTR_managers: (INCR, mgr_user1 + '@*,' + mgr_user2 + '@*')}
        self.server.manager(MGR_CMD_SET, SERVER, a, runas=runas)
        self.logger.info("Calling test setUp:")
        TestSelf.setUp(self)
        self.server.expect(SERVER, attrib=attr)

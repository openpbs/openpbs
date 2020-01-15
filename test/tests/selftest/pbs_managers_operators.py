# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class TestManagersOperators(TestSelf):

    """
        Additional managers users, except current user and MGR_USER
        should get unset after test setUp run
    """
    def test_managers_unset_setup(self):
        """
        Additional managers users, except current user and MGR_USER should
        get unset after test setUp run
        """
        runas = ROOT_USER
        manager_usr_str = str(MGR_USER) + '@*'
        current_usr = pwd.getpwuid(os.getuid())[0]
        current_usr_str = str(current_usr) + '@*'
        mgr_users = {manager_usr_str, current_usr_str}
        svr_mgr = self.server.status(SERVER, 'managers')[0]['managers']\
            .split(",")
        self.assertEqual(mgr_users, set(svr_mgr))

        mgr_user1 = str(TEST_USER)
        mgr_user2 = str(TEST_USER1)
        a = {ATTR_managers: (INCR, mgr_user1 + '@*,' + mgr_user2 + '@*')}
        self.server.manager(MGR_CMD_SET, SERVER, a, runas=runas)
        self.logger.info("Calling test setUp:")
        TestSelf.setUp(self)

        svr_mgr = self.server.status(SERVER, 'managers')[0]['managers'] \
            .split(",")
        self.assertEqual(mgr_users, set(svr_mgr))

    def test_default_oper(self):
        """
        Check that default operator user is set on PTL setup
        """
        svr_opr = self.server.status(SERVER, 'operators')[0].get('operators')
        opr_usr = str(OPER_USER) + '@*'
        self.assertEqual(opr_usr, svr_opr)

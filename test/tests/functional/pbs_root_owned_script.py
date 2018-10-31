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


class Test_RootOwnedScript(TestFunctional):
    """
    Test suite to test whether the root owned script is getting rejected
    and the comment is getting updated when root_reject_scripts set to true.
    """

    def setUp(self):
        """
        Set up the parameters required for Test_RootOwnedScript
        """
        if os.getuid() != 0:
            self.skipTest("Test need to run as root")
        TestFunctional.setUp(self)
        mom_conf_attr = {'$reject_root_scripts': 'true'}
        qmgr_attr = {'acl_roots': ROOT_USER}
        self.mom.add_config(mom_conf_attr)
        self.mom.restart()
        self.server.manager(MGR_CMD_SET, SERVER, qmgr_attr)
        self.sleep_5 = """#!/bin/bash
        sleep 5
        """

    def test_root_owned_script(self):
        """
        Edit the mom config to reject root script
        submit a script as root and observe the job comment.
        """
        j = Job(ROOT_USER)
        j.create_script(self.sleep_5)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        _comment = 'Not Running: PBS Error: Execution server rejected request'
        self.server.expect(JOB, {'comment': _comment}, id=jid)

    def test_non_root_script(self):
        """
        Edit the mom config to reject root script
        submit a script as TEST_USER and observe the job comment.
        """
        j = Job(TEST_USER)
        j.create_script(self.sleep_5)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

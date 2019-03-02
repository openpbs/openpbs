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

import os
from tests.functional import *


class TestHookTimeout(TestFunctional):

    """
    Test to make sure hooks are resent to moms that don't ack when
    the hooks are sent
    """

    def setUp(self):
        TestFunctional.setUp(self)

        if len(self.moms) != 3:
            self.skip_test('Test requires 3 moms, use -p <moms>')

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momC = self.moms.values()[2]
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()
        self.momC.delete_vnode_defs()

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.momC.shortname

        self.server.manager(MGR_CMD_DELETE, NODE, None, "")

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostC)

        self.server.expect(VNODE, {'state=free': 3}, op=EQ, count=True,
                           max_attempts=10, interval=2)

    @timeout(600)
    def test_hook_send(self):
        """
        Test when the server doesn't receive an ACK from a mom for
        sending hooks he resends them
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})
        timeout_max_attempt = 7

        # Make momB unresponsive
        self.logger.info("Stopping MomB")
        self.momB.signal("-STOP")

        start_time = int(time.time())

        hook_body = "import pbs\n"
        a = {'event': 'execjob_epilogue', 'enabled': 'True'}

        rv = self.server.create_import_hook("test", a, hook_body)
        self.assertTrue(rv)

        # First batch of hook update is for the *.HK files
        self.server.log_match(
            "Timing out previous send of mom hook updates "
            "(send replies expected=3 received=2)", n=600,
            max_attempts=timeout_max_attempt, interval=30,
            starttime=start_time)

        # sent hook control file
        for h in [self.hostA, self.hostB, self.hostC]:
            hfile = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                 "server_priv", "hooks", "test.HK")
            if h != self.hostB:
                exist = True
            else:
                exist = False
            self.server.log_match(
                ".*successfully sent hook file %s to %s.*" %
                (hfile, h), max_attempts=5, interval=1,
                regexp=True, existence=exist,
                starttime=start_time)

        # Second batch of hook update is for the *.PY files + resend of
        # *.HK file to momB
        self.server.log_match(
            "Timing out previous send of mom hook updates "
            "(send replies expected=4 received=2)", n=600,
            max_attempts=timeout_max_attempt, interval=30,
            starttime=start_time)

        # sent hook content file
        for h in [self.hostA, self.hostB, self.hostC]:
            hfile = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                 "server_priv", "hooks", "test.PY")
            if h != self.hostB:
                exist = True
            else:
                exist = False

            self.server.log_match(
                ".*successfully sent hook file %s to %s.*" %
                (hfile, h), max_attempts=3, interval=1,
                regexp=True, existence=exist,
                starttime=start_time)

        # Now check to make sure moms have received the hook files
        for m in [self.momA, self.momB, self.momC]:
            if m != self.momB:
                exist = True
            else:
                exist = False
            m.log_match(
                "test.HK;copy hook-related file request received",
                regexp=True, max_attempts=3, interval=1,
                existence=exist, starttime=start_time)

            m.log_match(
                "test.PY;copy hook-related file request received",
                regexp=True, max_attempts=3, interval=1,
                existence=exist, starttime=start_time)

        # Ensure that hook send updates are retried for
        # the *.HK and *.PY file to momB
        self.server.log_match(
            "Timing out previous send of mom hook updates "
            "(send replies expected=2 received=0)", n=600,
            max_attempts=timeout_max_attempt, interval=30,
            starttime=start_time)

        # Submit a job, it should still run
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'scatter'}
        j1 = Job(TEST_USER, attrs=a)
        j1id = self.server.submit(j1)

        # Wait for the job to start running.
        a = {ATTR_state: (EQ, 'R'), ATTR_substate: (EQ, 41)}
        self.server.expect(JOB, a, op=PTL_AND, id=j1id)

        self.server.log_match(
            "%s;vnode %s's parent mom.*has a pending copy hook "
            "or delete hook request.*" % (j1id, self.hostB),
            max_attempts=5, interval=1, regexp=True,
            starttime=start_time)

    def tearDown(self):
        self.momB.signal("-CONT")
        TestFunctional.tearDown(self)

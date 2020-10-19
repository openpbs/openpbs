# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


import os
from tests.functional import *
from time import sleep


@requirements(num_moms=3)
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
        for mom in self.moms.values():
            self.server.expect(NODE, {'state': 'free'}, id=mom.shortname)

    def timeout_messages(self, num_msg=1, starttime=None):
        msg_found = None
        for count in range(10):
            sleep(30)
            allmatch_msg = self.server.log_match(
                "Timing out previous send of mom hook updates ",
                max_attempts=1, starttime=starttime, allmatch=True)
            if len(allmatch_msg) >= num_msg:
                msg_found = allmatch_msg
                break
        self.assertIsNotNone(msg_found,
                             msg="Didn't get expected timeout messages")

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

        start_time = time.time()

        hook_body = "import pbs\n"
        a = {'event': 'execjob_epilogue', 'enabled': 'True'}

        self.server.create_hook("test", a)
        self.server.import_hook("test", hook_body)

        # First batch of hook update is for the *.HK files
        self.server.log_match(
            "Timing out previous send of mom hook updates ", n=600,
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
        self.timeout_messages(2, start_time)
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
                regexp=True, max_attempts=10, interval=1,
                existence=exist, starttime=start_time)

            m.log_match(
                "test.PY;copy hook-related file request received",
                regexp=True, max_attempts=10, interval=1,
                existence=exist, starttime=start_time)

        # Ensure that hook send updates are retried for
        # the *.HK and *.PY file to momB
        self.timeout_messages(3, start_time)
        # Submit a job, it should still run
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'scatter'}
        j1 = Job(TEST_USER, attrs=a)
        j1id = self.server.submit(j1)

        # Wait for the job to start running.
        a = {ATTR_state: (EQ, 'R'), ATTR_substate: (EQ, 41)}
        self.server.expect(JOB, a, op=PTL_AND, id=j1id)

        self.server.log_match(
            "%s;vnode %s.*parent mom.*has a pending copy hook "
            "or delete hook request.*" % (j1id, self.hostB),
            max_attempts=5, interval=1, regexp=True,
            starttime=start_time)

    def tearDown(self):
        self.momB.signal("-CONT")
        TestFunctional.tearDown(self)

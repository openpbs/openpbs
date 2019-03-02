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

from tests.functional import *


class TestOnlySmallFilesOverTPP(TestFunctional):
    """
    This test suite is for testing that only smaller job files (.OU/.ER/.CK)
    and scripts (size < 2MB) are sent over TPP and larger files are sent by
    forking.
    """

    def setUp(self):
        TestFunctional.setUp(self)

        if len(self.moms) != 2:
            self.skip_test(reason="need 2 mom hosts: -p moms=<m1>:<m2>")

        self.server.set_op_mode(PTL_CLI)

        # PBSTestSuite returns the moms passed in as parameters as dictionary
        # of hostname and MoM object
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        self.server.manager(MGR_CMD_DELETE, NODE, None, "")

        islocal = self.du.is_localhost(self.hostA)
        if islocal is False:
            self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
        else:
            self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)

        self.server.manager(MGR_CMD_SET, SERVER, {'job_requeue_timeout': 175})

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})

    def test_small_job_file(self):
        """
        This test case tests that small output files are sent over TPP.
        """
        j = Job(TEST_USER, attrs={ATTR_N: 'small_job_file'})

        test = []
        test += ['dd if=/dev/zero of=file bs=1024 count=0 seek=1024\n']
        test += ['cat file\n']
        test += ['sleep 30\n']

        j.create_script(test, hostname=self.server.client)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R', 'substate': 42},
                           id=jid, max_attempts=30, interval=2)
        time.sleep(5)
        try:
            self.server.rerunjob(jid)
        except PbsRerunError as e:
            self.assertTrue('qrerun: Response timed out. Job rerun request ' +
                            'still in progress for' in e.msg[0])

        msg = jid + ";big job files, sending via subprocess"
        self.server.log_match(msg, max_attempts=10, interval=2,
                              existence=False)

    def test_big_job_file(self):
        """
        This test case tests that large output files are not sent over TPP.
        """
        j = Job(TEST_USER, attrs={ATTR_N: 'big_job_file'})

        test = []
        test += ['dd if=/dev/zero of=file bs=1024 count=0 seek=3072\n']
        test += ['cat file\n']
        test += ['sleep 30\n']

        j.create_script(test, hostname=self.server.client)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R', 'substate': 42},
                           id=jid, max_attempts=30, interval=2)
        time.sleep(5)
        try:
            self.server.rerunjob(jid)
        except PbsRerunError as e:
            self.assertTrue('qrerun: Response timed out. Job rerun request ' +
                            'still in progress for' in e.msg[0])

        msg = jid + ";big job files, sending via subprocess"
        self.server.log_match(msg, max_attempts=30, interval=2)

    def test_big_job_script(self):
        """
        This test case tests that large job scripts are not sent over TPP.
        """
        j = Job(TEST_USER, attrs={
            ATTR_N: 'big_job_script'})

        # Create a big job script.
        test = []
        for i in range(105000):
            test += ['echo hey > /dev/null']
            test += ['sleep 5']

        j.create_script(test, hostname=self.server.client)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R', 'substate': 42},
                           id=jid, max_attempts=30, interval=2)

        msg = jid + ";big job files, sending via subprocess"
        self.server.log_match(
            msg, max_attempts=30, interval=2)

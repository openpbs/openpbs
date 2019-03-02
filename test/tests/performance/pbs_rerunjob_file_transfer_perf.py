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

from tests.performance import *


class JobRerunFileTransferPerf(TestPerformance):
    """
    This test suite is for testing the performance of job script
    and job output (stdout) transfers in case of rerun
    """

    def setUp(self):
        TestPerformance.setUp(self)

        if len(self.moms) != 2:
            self.logger.error('test requires two MoMs as input, ' +
                              '  use -p moms=<mom1>:<mom2>')
            self.assertEqual(len(self.moms), 2)

        # PBSTestSuite returns the moms passed in as parameters as dictionary
        # of hostname and MoM object
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})

        self.server.manager(MGR_CMD_SET, SERVER, {'job_requeue_timeout': 1000})

    @timeout(600)
    def test_huge_job_file(self):
        j = Job(TEST_USER, attrs={
                ATTR_N: 'huge_job_file', 'Resource_List.select': '1:host=%s'
                % self.momB.shortname})

        test = []
        test += ['dd if=/dev/zero of=file bs=1024 count=0 seek=250000\n']
        test += ['cat file\n']
        test += ['sleep 10000\n']

        j.create_script(test, hostname=self.server.client)

        now1 = int(time.time())
        jid = self.server.submit(j)
        self.server.expect(
            JOB, {'job_state': 'R', 'substate': 42}, id=jid,
            max_attempts=30, interval=5)
        now2 = int(time.time())
        self.logger.info("Job %s took %d seconds to start\n",
                         jid, (now2 - now1))

        # give a few seconds to job to create large spool file
        time.sleep(5)

        now1 = int(time.time())
        self.server.rerunjob(jid)
        self.server.expect(
            JOB, {'job_state': 'R', 'substate': 42}, id=jid,
            max_attempts=500, interval=5)
        now2 = int(time.time())
        self.logger.info("Job %s took %d seconds to rerun\n",
                         jid, (now2 - now1))

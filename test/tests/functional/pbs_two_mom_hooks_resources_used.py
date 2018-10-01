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


class TestAcctlogRescUsedWithTwoMomHooks(TestFunctional):

    """
    This test suite tests the accounting logs to have non-zero resources_used
    in the scenario where we have execjob_begin and execjob_end hooks.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        if len(self.moms) != 2:
            self.skipTest('Test requires two MoMs as input, '
                          'use -p moms=<mom1>:<mom2>')

        hook_body = "import time\n"
        a = {'event': 'execjob_begin', 'enabled': 'True'}
        rv = self.server.create_import_hook("test", a, hook_body)
        self.assertTrue(rv)

        a = {'event': 'execjob_end', 'enabled': 'True'}
        rv = self.server.create_import_hook("test2", a, hook_body)
        self.assertTrue(rv)

        a = {ATTR_nodefailrq: 5}
        rc = self.server.manager(MGR_CMD_SET, SERVER, a)
        self.assertEqual(rc, 0)

        a = {'job_history_enable': 'True'}
        rc = self.server.manager(MGR_CMD_SET, SERVER, a)
        self.assertEqual(rc, 0)

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        rc = self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)
        self.assertEqual(rc, 0)

    def test_Rrecord(self):
        """
        This test case runs a job on two nodes. Kills the mom process on
        MS, waits for the job to be requeued and tests for the
        resources_used value to be present in the 'R' record.
        """

        test = []
        test += ['#PBS -N NodeFailRequeueTest\n']
        test += ['echo Starting test at `date`\n']
        test += ['sleep 5\n']

        select = "vnode=" + self.hostA + "+vnode=" + self.hostB
        j1 = Job(TEST_USER, attrs={
            'Resource_List.select': select})
        j1.create_script(body=test)
        jid1 = self.server.submit(j1)

        # Wait for the job to start running.
        self.server.expect(JOB, {ATTR_state: 'R'}, jid1)
        # Kill the MoM process on the MS.

        self.momA.signal('-KILL')
        # Wait for the job to be requeued.
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

        # Check for resources_used value in the 'R' record.
        msg = '.*R;' + str(jid1) + '.*resources_used.ncpus=2.*'
        self.server.accounting_match(msg, tail=True, regexp=True)

    def test_Erecord(self):
        """
        This test case runs a job on two nodes. Waits for the job to complete.
        After that, tests for the E record to have non-zero values in
        resources_used.
        """

        test = []
        test += ['#PBS -N JobEndTest\n']
        test += ['echo Starting test at `date`\n']
        test += ['sleep 1\n']

        select = "vnode=" + self.hostA + "+vnode=" + self.hostB
        j1 = Job(TEST_USER, attrs={
            'Resource_List.select': select})
        j1.create_script(body=test)
        jid1 = self.server.submit(j1)

        # Wait for the job to start running.
        self.server.expect(JOB, {ATTR_state: 'R'}, jid1)

        # Wait for the job to finish running.
        self.server.expect(JOB, {'job_state': 'F'}, id=jid1, extend='x')

        rv = 0
        # Check if resources_used.walltime is zero or not.
        try:
            rv = self.server.expect(JOB, {'resources_used.walltime': '0'},
                                    id=jid1, max_attempts=2, extend='x')
        except PtlExpectError, e:
            # resources_used.walltime is non-zero.
            self.assertFalse(rv)
        else:
            # resources_used.walltime is zero, test case fails.
            self.logger.info("resources_used.walltime reported to be zero")
            self.assertFalse(True)

        # Check for the E record to NOT have zero walltime.
        msg = '.*E;' + str(jid1) + '.*resources_used.walltime=\"00:00:00.*'
        self.server.accounting_match(msg, tail=True, regexp=True,
                                     existence=False)

        # Check for the E record to have non-zero ncpus.
        msg = '.*E;' + str(jid1) + '.*resources_used.ncpus=2.*'
        self.server.accounting_match(msg, tail=True, regexp=True)

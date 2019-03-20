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
import re


class Test_Rrecord_with_resources_used(TestFunctional):

    """
    This test suite tests whether the 'R' record in accounting logs has
    information on resources_used in the following scenarios.
        a) The node the job was running on goes down and node_fail_requeue
           timeout is hit.
        b) It is rerun using qrerun <job-id>.
        c) It is rerun using qrerun -Wforce <job-id>.
        d) mom is restarted without any options or with the '-r' option
    """

    def setUp(self):
        TestFunctional.setUp(self)

        if len(self.moms) != 2:
            self.skipTest('test requires two MoMs as input, ' +
                          'use -p moms=<mom1>:<mom2>')

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

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)

        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostA)
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostB)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

    def common(self, is_nonrerunnable, restart_mom):

        # Set node_fail_requeue=5 on server

        a = {ATTR_nodefailrq: 5}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job script

        test = []
        test += ['#PBS -N RequeueTest\n']
        test += ['#PBS -l ncpus=1\n']
        test += ['echo Starting test at `date`\n']
        test += ['sleep 1000\n']

        test1 = []
        test1 += ['#PBS -N RequeueTest\n']
        test1 += ['#PBS -lselect=1:ncpus=1 -l place=scatter\n']
        test1 += ['echo Starting test at `date`\n']
        test1 += ['sleep 1000\n']

        # Submit three jobs J1,J2,J3[]

        j1 = Job(TEST_USER, attrs={ATTR_k: 'oe'})
        j1.create_script(body=test)
        jid1 = self.server.submit(j1)

        if is_nonrerunnable is True:
            j2 = Job(TEST_USER, attrs={ATTR_r: 'n', ATTR_k: 'oe'})
        else:
            j2 = Job(TEST_USER, attrs={ATTR_r: 'y', ATTR_k: 'oe'})

        j2.create_script(body=test1)
        jid2 = self.server.submit(j2)

        j3 = Job(TEST_USER, attrs={ATTR_J: '1-6', ATTR_k: 'oe'})
        j3.create_script(body=test)
        jid3 = self.server.submit(j3)

        subjobs = self.server.status(JOB, id=jid3, extend='t')
        jid3s1 = subjobs[1]['id']

        # Wait for the jobs to start running.
        self.server.expect(JOB, {ATTR_substate: '42'}, jid1)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid2)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid3s1)

        # Verify that accounting logs have Resource_List.<resource> value
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid1, regexp=True)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid2, regexp=True)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid3s1, regexp=True)

        # Bring both moms down using kill -9 <mom pid>
        self.momA.signal('-KILL')
        self.momB.signal('-KILL')

        # Verify that both nodes are reported to be down.
        self.server.expect(NODE, {ATTR_NODE_state: (
            MATCH_RE, '.*down.*')}, id=self.hostA)
        self.server.expect(NODE, {ATTR_NODE_state: (
            MATCH_RE, '.*down.*')}, id=self.hostB)

        self.server.expect(JOB, {ATTR_state: 'Q'}, jid1)
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid3s1)
        if is_nonrerunnable is False:
            # All rerunnable jobs - all should be in 'Q' state.
            self.server.expect(JOB, {ATTR_state: 'Q'}, jid2)
        else:
            # Job2 is non-rerunnable.
            self.server.expect(JOB, {ATTR_state: 'F'}, jid2, extend='x')

        # tracejob should show "Job requeued, execution node <node name> down"
        self.server.tracejob_match(
            msg='Job requeued, execution node .* down', id=jid1, regexp=True)

        if is_nonrerunnable is False:
            e = True
        else:
            e = False
        msg = 'Job requeued, execution node .* down'
        self.server.tracejob_match(msg=msg, id=jid2, regexp=True,
                                   existence=e)

        self.server.tracejob_match(
            msg='Job requeued, execution node .* down', id=jid3s1, regexp=True)

        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid1, regexp=True)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid2, regexp=True)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid3s1, regexp=True)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        if restart_mom == 's':
            # Start mom without any  option
            self.momA.start()
            self.momB.start()
        elif restart_mom == 'r':
            # Start mom with -r option
            self.momA.start(args=['-r'])
            self.momB.start(args=['-r'])

        return jid1, jid2, jid3s1

    def test_Rrecord_with_nodefailrequeue(self):
        """
        Scenario: The node on which the job was running goes down and
                  node_fail_requeue time-out is hit.
        Expected outcome: Server should record last known resource usage in
                  the 'R' record.
        """

        jid1, jid2, jid3s1 = self.common(False, False)

        self.server.accounting_match(
            msg='.*R;' + jid1 + '.*resources_used.*', id=jid1, regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 + '.*resources_used.*', id=jid2, regexp=True)
        self.server.accounting_match(
            msg='.*R;' + re.escape(jid3s1) + '.*resources_used.*',
            id=jid3s1, regexp=True)

    def test_Rrecord_when_mom_restarted_with_r(self):
        """
        Scenario: The node on which the job was running goes down and
                  node_fail_requeue time-out is hit and mom is restarted
                  with '-r'
        Expected outcome: Server should record last known resource usage in
                  the 'R' record.
        """

        jid1, jid2, jid3s1 = self.common(False, 'r')

        self.server.accounting_match(
            msg='.*R;' + jid1 + '.*resources_used.*run_count=1', id=jid1,
            regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 + '.*resources_used.*run_count=1', id=jid2,
            regexp=True)
        self.server.accounting_match(
            msg='.*R;' + re.escape(jid3s1) + '.*resources_used.*run_count=1',
            id=jid3s1, regexp=True)

    def test_Rrecord_for_nonrerunnable_jobs(self):
        """
        Scenario: One non-rerunnable job. The node on which the job was
                  running goes down and node_fail_requeue time-out is hit.
        Expected outcome: Server should record last known resource usage in
                  the 'R' record only for rerunnable jobs.
        """
        a = {ATTR_JobHistoryEnable: 1}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid1, jid2, jid3s1 = self.common(True, 'r')

        self.server.accounting_match(
            msg='.*R;' + jid1 + '.*resources_used.*run_count=1', id=jid1,
            regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 + '.*resources_used.*run_count=1', id=jid2,
            regexp=True, existence=False, max_attempts=5)
        self.server.accounting_match(
            msg='.*R;' + re.escape(jid3s1) + '.*resources_used.*run_count=1',
            id=jid3s1, regexp=True)

    def test_Rrecord_when_mom_restarted_without_r(self):
        """
        Scenario: Mom restarted without '-r' option and jobs are requeued
                   using qrerun.
        Expected outcome: Server should record last known resource usage in
                   the 'R' record for both.
        """

        jid1, jid2, jid3s1 = self.common(False, 's')

        self.server.accounting_match(
            msg='.*R;' + jid1 + '.*resources_used.*run_count=1', id=jid1,
            regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 + '.*resources_used.*run_count=1', id=jid2,
            regexp=True)
        self.server.accounting_match(
            msg='.*R;' + re.escape(jid3s1) + '.*resources_used.*run_count=1',
            id=jid3s1, regexp=True)

        # Verify that the jobs are in 'Q' state.
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid1)
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid3s1)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {ATTR_substate: '42'}, jid1)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid2)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid3s1)

        # qrerun the jobs and wait for them to start running.
        self.server.rerunjob(jobid=jid1)
        self.server.rerunjob(jobid=jid2)
        self.server.rerunjob(jobid=jid3s1)

        # Confirm that the 'R' record is generated and the run_count is 2.
        self.server.accounting_match(
            msg='.*R;' + jid1 + '.*resources_used.*run_count=2', id=jid1,
            regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 + '.*resources_used.*run_count=2', id=jid2,
            regexp=True)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

    def test_Rrecord_with_multiple_reruns(self):
        """
        Scenario: Job is rerun multiple times.
        Expected outcome: Server should record last known resource usage
                  every time the job is rerun.
        """

        dflt_q = self.server.default_queue

        # As user submit three jobs.
        test = []
        test += ['#PBS -N RequeueTest\n']
        test += ['#PBS -l ncpus=1\n']
        test += ['echo Starting test at `date`\n']
        test += ['sleep 1000\n']

        j1 = Job(TEST_USER)
        j1.create_script(body=test)
        j1.set_attributes({ATTR_r: 'y', ATTR_l + '.ncpus': 2})
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER)
        j2.create_script(body=test)
        j2.set_attributes({ATTR_r: 'n', ATTR_l + '.ncpus': 2})
        jid2 = self.server.submit(j2)

        j3 = Job(TEST_USER)
        j3.create_script(body=test)
        j3.set_attributes({ATTR_J: '1-4', ATTR_k: 'oe'})
        jid3 = self.server.submit(j3)

        subjobs = self.server.status(JOB, id=jid3, extend='t')
        jid3s1 = subjobs[1]['id']

        # Verify that the jobs have started running.
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid1)
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid2)
        self.server.expect(JOB, {ATTR_state: 'B'}, jid3)
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid3s1)

        # Verify that the accounting logs have Resource_List.<resource> but no
        # R records.
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid1, regexp=True)
        msg = '.*R;' + jid1 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid1, regexp=True,
                                     existence=False)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid2, regexp=True)
        msg = '.*R;' + jid2 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid2, regexp=True,
                                     existence=False)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid3s1, regexp=True)
        self.server.accounting_match(msg='.*R;' + re.escape(jid3s1) +
                                         '.*resources_used.*', id=jid3s1,
                                         regexp=True, existence=False)

        # sleep for 5 seconds so the jobs use some resources.
        time.sleep(5)

        self.server.rerunjob(jid1)
        self.server.rerunjob(jid3s1)

        # Verify that the accounting logs have R logs with last known resource
        # usage. No R logs for J2.

        self.server.accounting_match(
            msg='.*R;' + jid1 +
            '.*Exit_status=-11.*.*resources_used.*.*run_count=1.*',
            id=jid1, regexp=True)

        msg = '.*R;' + jid2 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid2, regexp=True,
                                     existence=False)

        self.server.accounting_match(msg='.*R;' + re.escape(
            jid3s1) + '.*Exit_status=-11.*.*resources_used.*.*run_count=1.*',
            id=jid3s1, regexp=True)

        # sleep for 5 seconds so the jobs use some resources.
        time.sleep(5)

        self.server.rerunjob(jid1)
        self.server.rerunjob(jid3s1)

        # Verify that the accounting logs should R logs with last known
        # resource usage Resource_used and run_count should be 3 for J1.
        # No R logs in accounting for J2.
        self.server.accounting_match(
            msg='.*R;' + jid1 +
            '.*Exit_status=-11.*.*resources_used.*.*run_count=2.*',
            id=jid1, regexp=True)
        msg = '.*R;' + jid2 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid2, regexp=True,
                                     existence=False)
        self.server.accounting_match(
            msg='.*R;' + re.escape(jid3s1) +
            '.*Exit_status=-11.*.*resources_used.*.*run_count=1.*',
            id=jid3s1, regexp=True)

    def test_Rrecord_with_multiple_reruns_case2(self):
        """
        Scenario: Jobs submitted with select cput and ncpus. Job is rerun
                  multiple times.
        Expected outcome: Server should record last known resource usage
                  that has cputime.
        """
        dflt_q = self.server.default_queue

        script = []
        script += ['i=0;\n']
        script += ['while [ $i -ne 0 ] || sleep 0.125;\n']
        script += ['do i=$(((i+1) % 10000 ));\n']
        script += ['done\n']
        j1 = Job(TEST_USER)
        j1.create_script(body=script)

        j1.set_attributes(
            {ATTR_l + '.cput': 160, ATTR_l + '.ncpus': 3, ATTR_k: 'oe'})
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER)
        j2.create_script(body=script)
        j2.set_attributes(
            {ATTR_l + '.cput': 180, ATTR_l + '.ncpus': 3,  ATTR_k: 'oe'})
        jid2 = self.server.submit(j2)

        # Verify that the jobs have started running.
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid1)
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid2)

        # Verify that the accounting logs have Resource_List.<resource> but no
        # R records.
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid1, regexp=True)
        msg = '.*R;' + jid1 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid1, regexp=True,
                                     existence=False)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid2, regexp=True)
        msg = '.*R;' + jid2 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid2, regexp=True,
                                     existence=False)

        time.sleep(5)

        jids = self.server.select()
        self.server.rerunjob(jids)

        # Verify that the accounting logs have R record with last known
        # resource usage and run_count should be 2 for J1 and J2.

        self.server.accounting_match(
            msg='.*R;' + jid1 +
            '.*.*resources_used.cput=[0-9]*:[0-9]*:[0-9]*.*.*run_count=1.*',
            id=jid1, regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 +
            '.*.*resources_used.cput=[0-9]*:[0-9]*:[0-9]*.*.*run_count=1.*',
            id=jid2, regexp=True)

        time.sleep(5)

        jids = self.server.select()
        self.server.rerunjob(jids)

        self.server.accounting_match(
            msg='.*R;' + jid1 +
            '.*.*resources_used.cput=[0-9]*:[0-9]*:[0-9]*.*.*run_count=2.*',
            id=jid1, regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 +
            '.*.*resources_used.cput=[0-9]*:[0-9]*:[0-9]*.*.*run_count=2.*',
            id=jid2, regexp=True)

    def test_Rrecord_job_rerun_forcefully(self):
        """
        Scenario: Job is forcefully rerun.
        Expected outcome: server should record last known resource usage in
                  the R record.
        """

        dflt_q = self.server.default_queue

        test = []
        test += ['#PBS -N RequeueTest\n']
        test += ['#PBS -l ncpus=1\n']
        test += ['echo Starting test at `date`\n']
        test += ['sleep 1000\n']

        j1 = Job(TEST_USER)
        j1.create_script(body=test)
        j1.set_attributes({ATTR_r: 'y', ATTR_l + '.ncpus': 2})
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER)
        j2.create_script(body=test)
        j2.set_attributes({ATTR_r: 'n', ATTR_l + '.ncpus': 2})
        jid2 = self.server.submit(j2)

        j3 = Job(TEST_USER)
        j3.create_script(body=test)
        j3.set_attributes({ATTR_J: '1-4', ATTR_k: 'oe'})
        jid3 = self.server.submit(j3)
        subjobs = self.server.status(JOB, id=jid3, extend='t')
        jid3s1 = subjobs[1]['id']

        # Verify that the jobs have started running.
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid1)
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid2)
        self.server.expect(JOB, {ATTR_state: 'B'}, jid3)
        self.server.expect(JOB, {ATTR_substate: '42', 'run_count': 1}, jid3s1)

        # Verify that the accounting logs have Resource_List.<resource> but no
        # R records.
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid1, regexp=True)
        msg = '.*R;' + jid1 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid1, regexp=True,
                                     existence=False)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid2, regexp=True)
        msg = '.*R;' + jid2 + '.*resources_used.*'
        self.server.accounting_match(msg=msg, id=jid2, regexp=True,
                                     existence=False)
        self.server.accounting_match(
            msg='.*Resource_List.*', id=jid3s1, regexp=True)
        self.server.accounting_match(msg='.*R;' +
                                         re.escape(jid3s1) +
                                         '.*resources_used.*',
                                         id=jid3s1, regexp=True,
                                     existence=False)

        time.sleep(5)

        jids = self.server.select(extend='T')
        self.server.rerunjob(jids, extend='force')

        # Verify that the accounting logs have R record with last known
        # resource usage and run_count should be 2 for J1 and J2

        self.server.accounting_match(
            msg='.*R;' + jid1 +
            '.*Exit_status=0.*.*resources_used.*.*run_count=1.*',
            id=jid1, regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 +
            '.*Exit_status=0.*.*resources_used.*.*run_count=1.*',
            id=jid2, regexp=True)
        self.server.accounting_match(msg='.*R;' + re.escape(
            jid3s1) + '.*Exit_status=0.*.*resources_used.*.*run_count=1.*',
            id=jid3s1, regexp=True)
        time.sleep(5)

        jids = self.server.select(extend='T')
        self.server.rerunjob(jids, extend='force')

        # Verify that the accounting logs have R record with last known
        # usage and run_count should be 3 for J1 and J2.
        self.server.accounting_match(
            msg='.*R;' + jid1 +
            '.*Exit_status=0.*.*resources_used.*.*run_count=2.*',
            id=jid1, regexp=True)
        self.server.accounting_match(
            msg='.*R;' + jid2 +
            '.*Exit_status=0.*.*resources_used.*.*run_count=2.*',
            id=jid2, regexp=True)
        self.server.accounting_match(msg='.*R;' + re.escape(
            jid3s1) +
            '.*Exit_status=0.*.*resources_used.*.*run_count=1.*',
            id=jid3s1, regexp=True)

    def tearDown(self):
        TestFunctional.tearDown(self)

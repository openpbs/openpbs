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


class TestPreemption(TestFunctional):
    """
    Contains tests for scheduler's preemption functionality
    """
    def setUp(self):
        TestFunctional.setUp(self)

        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        # create express queue
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")
        if len(self.moms) == 2:
            self.mom1 = self.moms.keys()[0]
            self.mom2 = self.moms.keys()[1]
            # Since some tests need multi-node setup and majority don't,
            # delete the second node so that single node tests don't fail.
            # Tests needing multi-node setup will create the second node
            # explicity.
            self.server.manager(MGR_CMD_DELETE, NODE, id=self.mom2)

    def submit_jobs(self):
        """
        Function to submit two normal job and one high priority job
        """
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        time.sleep(1)
        j2 = Job(TEST_USER)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_q: 'expressq'})
        jid3 = self.server.submit(j3)

        return jid1, jid2, jid3

    def submit_and_preempt_jobs(self, preempt_order='R'):
        """
        This function will set the prempt order, submit jobs,
        preempt jobs and do log_match()
        """
        if preempt_order == 'R':
            job_state = 'Q'
            preempted_by = 'requeuing'
        elif preempt_order == 'C':
            job_state = 'Q'
            preempted_by = 'checkpointing'
        elif preempt_order == 'S':
            job_state = 'S'
            preempted_by = 'suspension'

        # set preempt order
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'preempt_order': preempt_order}, runas=ROOT_USER)

        attrs = {ATTR_l + '.select': '1:ncpus=1'}

        # submit a job to regular queue
        j1 = Job(TEST_USER, attrs)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        # submit a job to high priority queue
        attrs['queue'] = 'expressq'
        j2 = Job(TEST_USER, attrs)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': job_state}, id=jid1)

        self.scheduler.log_match(jid1 + ";Job preempted by " + preempted_by)
        self.scheduler.log_match(
            jid1 + ";Job will never run", existence=False, max_attempts=5)

    def test_never_run_preempt_suspension(self):
        """
        Test that a job preempted by suspension is not
        marked as "Job will never run"
        """
        self.submit_and_preempt_jobs(preempt_order='S')

    def test_never_run_preempt_checkpoint(self):
        """
        Test that a preempted job with checkpoint is not
        marked as "Job will never run"
        """

        # Create checkpoint
        chk_script = """#!/bin/bash
kill $1
exit 0
"""
        self.chk_file = self.du.create_temp_file(body=chk_script)
        self.du.chmod(path=self.chk_file, mode=0755)
        self.du.chown(path=self.chk_file, uid=0, gid=0, sudo=True)
        c = {'$action': 'checkpoint_abort 30 !' + self.chk_file + ' %sid'}
        self.mom.add_config(c)
        self.attrs = {ATTR_l + '.select': '1:ncpus=1'}

        # preempt jobs and check logs
        self.submit_and_preempt_jobs(preempt_order='C')

    def test_never_run_preempt_requeue(self):
        """
        Test that a preempted job by requeueing is not
        marked as "Job will never run"
        """
        self.submit_and_preempt_jobs(preempt_order='R')

    def test_qalter_preempt_targets_to_none(self):
        """
        Test that a job requesting preempt targets set to two different queues
        can be altered to set preempt_targets as NONE
        """

        # create an addition queue
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "workq2")

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'False'})
        # submit a job in expressq with preempt targets set to workq, workq2
        a = {'Resource_List.preempt_targets': 'queue=workq,queue=workq2'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)

        self.server.alterjob(jobid=jid,
                             attrib={'Resource_List.preempt_targets': 'None'})
        self.server.expect(JOB, id=jid,
                           attrib={'Resource_List.preempt_targets': 'None'})

    def test_preempt_sort_when_set(self):
        """
        This test is for preempt_sort when it is set to min_time_since_start
        """
        a = {ATTR_rescavail + '.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        a = {'preempt_sort': 'min_time_since_start'}
        self.server.manager(MGR_CMD_SET, SCHED, a)
        jid1, jid2, jid3 = self.submit_jobs()
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)

    def test_preempt_sort_when_unset(self):
        """
        This test is for preempt_sort when it is unset
        """
        a = {ATTR_rescavail + '.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_sort')
        jid1, jid2, jid3 = self.submit_jobs()
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)

    def test_preempt_retry(self):
        """
        Test to make sure that preemption is retried if it fails.
        """
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        abort_script = """#!/bin/bash
exit 3
"""
        abort_file = self.du.create_temp_file(body=abort_script)
        self.du.chmod(path=abort_file, mode=0755)
        self.du.chown(path=abort_file, uid=0, gid=0, runas=ROOT_USER)
        c = {'$action': 'checkpoint_abort 30 !' + abort_file}
        self.mom.add_config(c)

        # submit two jobs to regular queue
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)

        time.sleep(2)

        j2 = Job(TEST_USER)
        jid2 = self.server.submit(j2)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        # set preempt order
        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': 'C'})

        # submit a job to high priority queue
        a = {ATTR_q: 'expressq'}
        j3 = Job(TEST_USER, a)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)

        self.mom.log_match(jid2 + ";checkpoint failed:")
        self.mom.log_match(jid1 + ";checkpoint failed:")

        abort_script = """#!/bin/bash
kill -9 $1
exit 0
"""
        abort_file = self.du.create_temp_file(body=abort_script)
        self.du.chmod(path=abort_file, mode=0755)
        self.du.chown(path=abort_file, uid=0, gid=0, runas=ROOT_USER)
        c = {'$action': 'checkpoint_abort 30 !' + abort_file + ' %sid'}
        self.mom.add_config(c)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

    def test_vnode_resource_contention(self):
        """
        Test to make sure that preemption happens when the resource in
        contention is vnode.
        """

        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes(name='vnode', attrib=a, num=11,
                                  mom=self.mom, usenatvnode=False)

        a = {'Resource_List.select': '1:ncpus=2+1:ncpus=2'}
        for _ in range(5):
            j = Job(TEST_USER, attrs=a)
            jid = self.server.submit(j)
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Randomly select a vnode with running jobs on it. Request this
        # vnode in the high priority job later.
        self.server.expect(NODE, {'state': 'job-busy'}, id='vnode[4]')

        a = {ATTR_q: 'expressq', 'Resource_List.vnode': 'vnode[4]'}
        hj = Job(TEST_USER, attrs=a)
        hjid = self.server.submit(hj)
        self.server.expect(JOB, {'job_state': 'R'}, id=hjid)

        # Since high priority job consumed only one ncpu, vnode[4]'s
        # node state should be free now
        self.server.expect(NODE, {'state': 'free'}, id='vnode[4]')

    def test_host_resource_contention(self):
        """
        Test to make sure that preemption happens when the resource in
        contention is host.
        """
        # Skip test if number of mom provided is not equal to two
        if len(self.moms) != 2:
            self.skipTest("test requires two MoMs as input, " +
                          "use -p moms=<mom1>:<mom2>")
        else:
            self.server.manager(MGR_CMD_CREATE, NODE, id=self.mom2)

        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom1)
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom2)

        a = {'Resource_List.select': '1:ncpus=2'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        # Stat job to check which job is running on mom1
        pjid = jid2
        job_stat = self.server.status(JOB, id=jid1)
        ehost = job_stat[0]['exec_host'].partition('/')[0]
        if ehost == self.mom1:
            pjid = jid1

        # Submit a express queue job requesting the host
        a = {ATTR_q: 'expressq', 'Resource_List.host': self.mom1}
        hj = Job(TEST_USER, attrs=a)
        hjid = self.server.submit(hj)
        self.server.expect(JOB, {'job_state': 'R'}, id=hjid)
        self.server.expect(JOB, {'job_state': 'S'}, id=pjid)

        # Submit another express queue job requesting the host,
        # this job will stay queued
        a = {ATTR_q: 'expressq', 'Resource_List.host': self.mom1,
             'Resource_List.ncpus': 2}
        hj2 = Job(TEST_USER, attrs=a)
        hjid2 = self.server.submit(hj2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=hjid2)
        comment = "Not Running: Insufficient amount of resource: host"
        self.server.expect(JOB, {'comment': comment}, id=hjid2)

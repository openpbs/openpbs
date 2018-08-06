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


class TestPreemption(TestFunctional):
    """
    Contains tests for scheduler's preemption functionality
    """
    def setUp(self):
        TestFunctional.setUp(self)

        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            expect=True)

        # create express queue
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")

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
        self.scheduler.set_sched_config({'preempt_order': preempt_order})

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

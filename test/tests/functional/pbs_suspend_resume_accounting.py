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


from tests.functional import *


class TestSuspendResumeAccounting(TestFunctional):
    """
    Testsuite for verifying accounting of
    suspend/resume events of job
    """

    script = ['#!/bin/bash\nfor ((c=1; c <= 1000000000; c++));']
    script += ['do']
    script += ['sleep 1']
    script += ['done']

    def test_suspend_resume_job_signal(self):
        """
        Test case to verify accounting suspend
        and resume records when the events are
        triggered by client for one job.
        """
        j = Job()
        j.create_script(self.script)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        self.server.sigjob(jobid=jid, signal="suspend")

        record = 'z;%s;.*resources_used.' % jid
        self.server.accounting_match(msg=record, id=jid, regexp=True)

        self.server.sigjob(jobid=jid, signal="resume")
        record = 'r;%s;' % jid
        self.server.accounting_match(msg=record, id=jid)

    def test_suspend_resume_job_array_signal(self):
        """
        Test case to verify accounting suspend
        and resume records when the events are
        triggered by client for a job array.
        """
        a = {ATTR_rescavail + '.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        j = Job()
        j.create_script(self.script)
        j.set_attributes({ATTR_J: '1-2'})
        jid = self.server.submit(j)

        sub_jid1 = j.create_subjob_id(jid, 1)
        sub_jid2 = j.create_subjob_id(jid, 2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sub_jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sub_jid2)

        # suspend job
        self.server.sigjob(jobid=jid, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S'}, id=sub_jid1)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=sub_jid2)

        record = 'z;%s;resources_used.' % sub_jid1
        self.server.accounting_match(msg=record, id=sub_jid1)

        record = 'z;%s;resources_used.' % sub_jid2
        self.server.accounting_match(msg=record, id=sub_jid2)

        self.server.sigjob(jobid=jid, signal="resume")
        record = 'r;%s;' % sub_jid1
        self.server.accounting_match(msg=record, id=sub_jid1)

        record = 'r;%s;' % sub_jid2
        self.server.accounting_match(msg=record, id=sub_jid2)

    def test_interactive_job_suspend_resume(self):
        """
        Test case to verify accounting suspend
        and resume records when the events are
        triggered by client for a interactive job.
        """

        cmd = 'sleep 10'
        j = Job(attrs={ATTR_inter: ''})
        j.interactive_script = [('hostname', '.*'),
                                (cmd, '.*')]

        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.sigjob(jobid=jid, signal="suspend")

        record = 'z;%s;.*resources_used.' % jid
        self.server.accounting_match(msg=record, id=jid, regexp=True)

        self.server.sigjob(jobid=jid, signal="resume")
        record = 'r;%s;' % jid
        self.server.accounting_match(msg=record, id=jid)

    def test_suspend_resume_job_scheduler(self):
        """
        Test case to verify accounting suspend
        and resume records when the events are
        triggered by Scheduler.
        """

        a = {ATTR_rescavail + '.ncpus': 4, ATTR_rescavail + '.mem': '2gb'}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        # Create an express queue
        b = {ATTR_qtype: 'Execution', ATTR_enable: 'True',
             ATTR_start: 'True', ATTR_p: '200'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, b, "expressq")

        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j1 = Job()
        j1.create_script(self.script)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        j2 = Job()
        j2.create_script(self.script)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=512mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        resc_released = "resources_released=(%s:ncpus=4:mem=524288kb)" \
                        % self.mom.shortname
        record = 'z;%s;resources_used.' % jid1
        line = self.server.accounting_match(msg=record, id=jid1)[1]
        self.assertIn(resc_released, line)

        self.server.delete(jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        record = 'r;%s;' % jid1
        self.server.accounting_match(msg=record, id=jid1)

    def test_admin_suspend_resume_signal(self):
        """
        Test case to verify accounting of admin-suspend
        and admin-resume records.
        """
        j = Job()
        j.create_script(self.script)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

        record = 'z;%s;.*resources_used.' % jid
        self.server.accounting_match(msg=record, id=jid, regexp=True)

        self.server.sigjob(jid, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        record = 'r;%s;' % jid
        self.server.accounting_match(msg=record, id=jid)

    def test_resc_released_susp_resume(self):
        """
        Test case to verify accounting of suspend/resume
        events with restrict_res_to_release_on_suspend set
        on server
        """
        # Set both ncpus and mem
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j = Job()
        j.create_script(self.script)
        j.set_attributes({ATTR_l + '.select': '1:ncpus=1:mem=512mb'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        self.server.sigjob(jobid=jid, signal="suspend")

        # check for both ncpus and mem are released
        resc_released = 'resources_released=(%s:ncpus=1:mem=524288kb)'

        node = self.server.status(JOB, 'exec_vnode', id=jid)[0]['exec_vnode']
        vn = node.split('+')[0].split(':')[0].split('(')[1]
        resc_released = resc_released % vn
        record = 'z;%s;resources_used.' % jid
        line = self.server.accounting_match(msg=record, id=jid)[1]
        self.assertIn(resc_released, line)

        self.server.sigjob(jobid=jid, signal="resume")
        record = 'r;%s;' % jid
        self.server.accounting_match(msg=record, id=jid)

    def test_resc_released_susp_resume_multi_vnode(self):
        """
        Test case to verify accounting of suspend/resume
        events with restrict_res_to_release_on_suspend set
        on server for multiple vnodes
        """
        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        b = {ATTR_qtype: 'Execution', ATTR_enable: 'True',
             ATTR_start: 'True', ATTR_p: '200'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, b, "expressq")

        vn_attrs = {ATTR_rescavail + '.ncpus': 8,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.mom.create_vnodes(vn_attrs, 1,
                               fname="vnodedef1", vname="vnode1")
        # Append a vnode
        vn_attrs = {ATTR_rescavail + '.ncpus': 6,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.mom.create_vnodes(vn_attrs, 1, additive=True,
                               fname="vnodedef2", vname="vnode2")

        # Submit a low priority job
        j1 = Job()
        j1.create_script(self.script)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=8:mem=512mb+1'
                                               ':ncpus=6:mem=256mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job()
        j2.create_script(self.script)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=8:mem=256mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        resc_released = 'resources_released=(vnode1[0]:ncpus=8)+' \
                        '(vnode2[0]:ncpus=6)'
        record = 'z;%s;resources_used.' % jid1
        line = self.server.accounting_match(msg=record, id=jid1)[1]
        self.assertIn(resc_released, line)

    def test_higher_priority_job_hook_reject(self):
        """
        Test case to verify accounting of suspend/resume
        events of a job which gets suspended by a higher priority
        job and gets resumed when the runjob hook rejects the
        higher priority job.
        """
        a = {ATTR_rescavail + '.ncpus': 4, ATTR_rescavail + '.mem': '2gb'}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        b = {ATTR_qtype: 'Execution', ATTR_enable: 'True',
             ATTR_start: 'True', ATTR_p: '200'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, b, "expressq")

        # Define a runjob hook
        hook = """
import pbs
e = pbs.event()
e.reject()
"""
        j1 = Job()
        j1.create_script(self.script)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        a = {'event': 'runjob', 'enabled': 'True'}
        self.server.create_import_hook("sr_hook", a, hook)

        j2 = Job()
        j2.create_script(self.script)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=512mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        record = 'z;%s;.*resources_used.' % jid1
        self.server.accounting_match(msg=record, id=jid1, regexp=True)

        record = 'r;%s;' % jid1
        self.server.accounting_match(msg=record, id=jid1)

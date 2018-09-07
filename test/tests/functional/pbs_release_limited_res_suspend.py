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

import time
from tests.functional import *


class TestReleaseLimitedResOnSuspend(TestFunctional):
    """
    Test that based on admin's input only limited number of resources are
    released when suspending a running job.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        # Set default resources available on the default mom
        a = {ATTR_rescavail + '.ncpus': 4, ATTR_rescavail + '.mem': '2gb'}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        # Create an express queue
        b = {ATTR_qtype: 'Execution', ATTR_enable: 'True',
             ATTR_start: 'True', ATTR_p: '200'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, b, "expressq")

    def test_do_not_release_mem_sched_susp(self):
        """
        During preemption by suspension test that only ncpus are released from
        the running job and memory is not released.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=512mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        ras_mem = ATTR_rescassn + '.mem'
        ras_ncpus = ATTR_rescassn + '.ncpus'

        rv = self.server.status(
            NODE, [ras_ncpus, ras_mem], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_mem], "1048576kb",
                         msg="pbs should not release memory")
        self.assertEqual(rv[0][ras_ncpus], "2",
                         msg="pbs did not release ncpus")

    def test_do_not_release_mem_qsig_susp(self):
        """
        If a running job is suspended using qsig, test that only ncpus are
        released from the running job and memory is not released.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")

        ras_mem = ATTR_rescassn + '.mem'
        ras_ncpus = ATTR_rescassn + '.ncpus'

        rv = self.server.status(
            NODE, [ras_ncpus, ras_mem], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_mem], "524288kb",
                         msg="pbs should not release memory")
        self.assertEqual(rv[0][ras_ncpus], "0",
                         msg="pbs did not release ncpus")

    def test_change_in_res_to_release_on_suspend(self):
        """
        set restrict_res_to_release_on_suspend to only ncpus and then suspend
        a job after the job is suspended change
        restrict_res_to_release_on_suspend to release only memory and check
        if the suspended job resumes and do not account for memory twice.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=256mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        # Change restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        rc = 0
        try:
            rc = self.server.deljob(jid2, wait=True)
        except PbsDeljobError as e:
            self.assertEqual(rc, 0, e.msg[0])

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        ras_mem = ATTR_rescassn + '.mem'
        ras_ncpus = ATTR_rescassn + '.ncpus'

        rv = self.server.status(
            NODE, [ras_ncpus, ras_mem], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_mem], "524288kb",
                         msg="pbs did not account for memory correctly")
        self.assertEqual(rv[0][ras_ncpus], "4",
                         msg="pbs did not account for ncpus correctly")

    def test_res_released_sched_susp(self):
        """
        Test if job's resources_released attribute is correctly set when
        it is suspended.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=512mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        job = self.server.status(JOB, id=jid1)

        rr = "(%s:ncpus=4)" % self.mom.shortname
        self.assertEqual(job[0][ATTR_released], rr,
                         msg="resources_released incorrect")

    def test_res_released_sched_susp_multi_vnode(self):
        """
        Test if job's resources_released attribute is correctly set when
        a multi vnode job is suspended.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        vn_attrs = {ATTR_rescavail + '.ncpus': 8,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.server.create_vnodes("vnode1", vn_attrs, 1,
                                  self.mom, fname="vnodedef1")
        # Append a vnode
        vn_attrs = {ATTR_rescavail + '.ncpus': 6,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.server.create_vnodes("vnode2", vn_attrs, 1,
                                  self.mom, additive=True, fname="vnodedef2")

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select':
                           '1:ncpus=8:mem=512mb+1:ncpus=6:mem=256mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=8:mem=256mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        job = self.server.status(JOB, id=jid1)

        rr = "(vnode1[0]:ncpus=8)+(vnode2[0]:ncpus=6)"
        self.logger.info("resources released are " + job[0][ATTR_released])
        self.assertEqual(job[0][ATTR_released], rr,
                         msg="resources_released incorrect")

    def test_res_released_sched_susp_arrayjob(self):
        """
        Test if array subjob's resources_released attribute is correctly
        set when it is suspended.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb',
                           ATTR_J: '1-3'})
        jid1 = self.server.submit(j1)
        subjobs = self.server.status(JOB, id=jid1, extend='t')
        sub_jid1 = subjobs[1]['id']
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sub_jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=512mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45},
                           id=sub_jid1)

        job = self.server.status(JOB, id=sub_jid1)

        rr = "(%s:ncpus=4)" % self.mom.shortname
        self.assertEqual(job[0][ATTR_released], rr,
                         msg="resources_released incorrect")

    def test_res_released_list_sched_susp_arrayjob(self):
        """
        Test if array subjob's resources_released_list attribute is correctly
        set when it is suspended.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb',
                           ATTR_J: '1-3'})
        jid1 = self.server.submit(j1)
        subjobs = self.server.status(JOB, id=jid1, extend='t')
        sub_jid1 = subjobs[1]['id']
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sub_jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=256mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45},
                           id=sub_jid1)

        job = self.server.status(JOB, id=sub_jid1)

        rr_l_ncpus = job[0][ATTR_rel_list + ".ncpus"]
        self.assertEqual(rr_l_ncpus, "4", msg="ncpus not released")
        rr_l_mem = job[0][ATTR_rel_list + ".mem"]
        self.assertEqual(rr_l_mem, "524288kb", msg="memory not released")

    def test_res_released_list_sched_susp(self):
        """
        Test if job's resources_released_list attribute is correctly set when
        it is suspended.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=256mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        job = self.server.status(JOB, id=jid1)

        rr_l_ncpus = job[0][ATTR_rel_list + ".ncpus"]
        self.assertEqual(rr_l_ncpus, "4", msg="ncpus not released")
        rr_l_mem = job[0][ATTR_rel_list + ".mem"]
        self.assertEqual(rr_l_mem, "524288kb", msg="memory not released")

    def test_res_released_list_sched_susp_multi_vnode(self):
        """
        Test if job's resources_released_list attribute is correctly set when
        a multi vnode job is suspended.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        vn_attrs = {ATTR_rescavail + '.ncpus': 8,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.server.create_vnodes("vnode1", vn_attrs, 1,
                                  self.mom, fname="vnodedef1")
        # Append a vnode
        vn_attrs = {ATTR_rescavail + '.ncpus': 6,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.server.create_vnodes("vnode2", vn_attrs, 1,
                                  self.mom, additive=True, fname="vnodedef2")

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select':
                           '1:ncpus=8:mem=512mb+1:ncpus=6:mem=256mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=8:mem=256mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        job = self.server.status(JOB, id=jid1)

        rr_l_ncpus = job[0][ATTR_rel_list + ".ncpus"]
        self.assertEqual(rr_l_ncpus, "14", msg="ncpus not released")
        rr_l_mem = job[0][ATTR_rel_list + ".mem"]
        self.assertNotEqual(rr_l_mem, "2097152kb", msg="memory not released")

    def test_node_res_after_deleting_suspended_job(self):
        """
        Test that once a suspended job is deleted node's resources assigned
        are back to 0.
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 43}, id=jid1)

        ras_mem = ATTR_rescassn + '.mem'
        ras_ncpus = ATTR_rescassn + '.ncpus'

        rv = self.server.status(
            NODE, [ras_ncpus, ras_mem], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertEqual(
            rv[0][ras_mem], "524288kb",
            msg="pbs did not retain memory correctly on the node")
        self.assertEqual(
            rv[0][ras_ncpus], "0",
            msg="pbs did not release ncpus correctly on the node")

        rc = 0
        try:
            rc = self.server.deljob(jid1, wait=True)
        except PbsDeljobError as e:
            self.assertEqual(rc, 0, e.msg[0])

        rv = self.server.status(
            NODE, [ras_ncpus, ras_mem], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertEqual(
            rv[0][ras_mem], "0kb",
            msg="pbs did not reassign memory correctly on the node")
        self.assertEqual(
            rv[0][ras_ncpus], "0",
            msg="pbs did not reassign ncpus correctly on the node")

    def test_default_restrict_res_released_on_suspend(self):
        """
        Test the default value of restrict_res_to_release_on_suspend.
        It should release all the resources by default.
        """
        # Submit a low priority job
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2:mem=256mb',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        ras_mem = ATTR_rescassn + '.mem'
        ras_ncpus = ATTR_rescassn + '.ncpus'

        rv = self.server.status(
            NODE, [ras_ncpus, ras_mem], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_mem], "262144kb",
                         msg="pbs did not release memory")
        self.assertEqual(rv[0][ras_ncpus], "2",
                         msg="pbs did not release ncpus")

    def test_setting_unknown_resc(self):
        """
        Set a non existing resource in restrict_res_to_release_on_suspend
        and expect an unknown resource error
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,abc'}
        try:
            self.server.manager(MGR_CMD_SET, SERVER, a)
        except PbsManagerError as e:
            self.assertTrue("Unknown resource" in e.msg[0])

    def test_delete_res_busy_on_res_to_release_list(self):
        """
        Create a resource, set it in restrict_res_to_release_on_suspend
        then delete the resource and check for resource busy error
        """

        # create a custom resource
        attr = {ATTR_RESC_TYPE: 'long'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='foo')
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='bar')

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,foo,bar'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # delete the custom resources
        try:
            self.server.manager(MGR_CMD_DELETE, RSC, id='foo')
        except PbsManagerError as e:
            self.assertTrue("Resource busy on server" in e.msg[0])

        try:
            self.server.manager(MGR_CMD_DELETE, RSC, id='bar')
        except PbsManagerError as e:
            self.assertTrue("Resource busy on server" in e.msg[0])

    def test_queue_res_release_upon_suspension(self):
        """
        Create 2 consumable resources and set it on queue,
        set one of those resouces in restrict_res_to_release_on_suspend,
        submit a job requesting these resources, check if the resource
        set in restrict_res_to_release_on_suspend shows up as released
        on the queue
        """

        # create a custom resource
        attr = {ATTR_RESC_TYPE: 'long',
                ATTR_RESC_FLAG: 'q'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='foo')
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='bar')

        # Set foo in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,foo'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {ATTR_rescavail + ".foo": '100',
             ATTR_rescavail + ".bar": '100'}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id="workq")

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.ncpus': '4',
                           ATTR_l + '.foo': '30',
                           ATTR_l + '.bar': '40'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")

        ras_foo = ATTR_rescassn + '.foo'
        ras_bar = ATTR_rescassn + '.bar'

        rv = self.server.status(
            QUEUE, [ras_foo, ras_bar], id="workq")
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_foo], "0",
                         msg="pbs did not release resource foo")

        self.assertEqual(rv[0][ras_bar], "40",
                         msg="pbs should not release resource bar")

    def test_server_res_release_upon_suspension_using_qsig(self):
        """
        Create 2 consumable resources and set it on server,
        set one of those resouces in restrict_res_to_release_on_suspend,
        submit a job requesting these resources, check if the resource
        set in restrict_res_to_release_on_suspend shows up as released
        on the server when job is suspended using qsig
        """

        # create a custom resource
        attr = {ATTR_RESC_TYPE: 'long',
                ATTR_RESC_FLAG: 'q'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='foo')
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='bar')

        # Set foo in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,foo'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {ATTR_rescavail + ".foo": '100',
             ATTR_rescavail + ".bar": '100'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.ncpus': '4',
                           ATTR_l + '.foo': '30',
                           ATTR_l + '.bar': '40'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")

        ras_foo = ATTR_rescassn + '.foo'
        ras_bar = ATTR_rescassn + '.bar'

        rv = self.server.status(
            SERVER, [ras_foo, ras_bar])
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_foo], "0",
                         msg="pbs did not release resource foo")

        self.assertEqual(rv[0][ras_bar], "40",
                         msg="pbs should not release resource bar")

    def test_server_res_release_upon_suspension_using_preemption(self):
        """
        Create 2 consumable resources and set it on server,
        set one of those resouces in restrict_res_to_release_on_suspend,
        submit a job requesting these resources, check if the resource
        set in restrict_res_to_release_on_suspend shows up as released
        on the server when preemption happens
        """

        # create a custom resource
        attr = {ATTR_RESC_TYPE: 'long',
                ATTR_RESC_FLAG: 'q'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='foo')
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='bar')

        # Set foo in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,foo'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Add foo and bar to the resources scheduler checks for
        resources = self.scheduler.sched_config['resources']
        resources = resources[:-1] + ', foo, bar\"'
        self.scheduler.set_sched_config({'resources': resources})

        a = {ATTR_rescavail + ".foo": '100',
             ATTR_rescavail + ".bar": '100'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        # Submit 2 normal priority jobs
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.ncpus': '1',
                           ATTR_l + '.foo': '40',
                           ATTR_l + '.bar': '20'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.ncpus': '1',
                           ATTR_l + '.foo': '40',
                           ATTR_l + '.bar': '20'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        # Submit a high priority job
        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.ncpus': '1',
                           ATTR_l + '.foo': '70',
                           ATTR_l + '.bar': '20',
                           ATTR_q: 'expressq'})
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

        ras_foo = ATTR_rescassn + '.foo'
        ras_bar = ATTR_rescassn + '.bar'

        rv = self.server.status(
            SERVER, [ras_foo, ras_bar])
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_foo], "70",
                         msg="pbs did not release resource foo")

        self.assertEqual(rv[0][ras_bar], "60",
                         msg="pbs should not release resource bar")

    def test_node_custom_res_release_upon_suspension(self):
        """
        Create 2 consumable resources and set it on node,
        set one of those resouces in restrict_res_to_release_on_suspend,
        submit a job requesting these resources, check if the resource
        set in restrict_res_to_release_on_suspend shows up as released
        on the node
        """

        # create a custom resource
        attr = {ATTR_RESC_TYPE: 'long',
                ATTR_RESC_FLAG: 'nh'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='foo')
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='bar')

        # Set foo in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus,foo'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.add_resource("foo,bar")

        a = {ATTR_rescavail + ".foo": '100',
             ATTR_rescavail + ".bar": '100'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.ncpus': '4',
                           ATTR_l + '.foo': '30',
                           ATTR_l + '.bar': '40'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")

        ras_foo = ATTR_rescassn + '.foo'
        ras_bar = ATTR_rescassn + '.bar'

        rv = self.server.status(
            NODE, [ras_foo, ras_bar], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertEqual(rv[0][ras_foo], "0",
                         msg="pbs did not release resource foo")

        self.assertEqual(rv[0][ras_bar], "40",
                         msg="pbs should not release resource bar")

    def test_resuming_with_no_res_released(self):
        """
        Set restrict_res_to_release_on_suspend to a resource that a job
        does not request and then suspend this running job using qsig
        check if such a job resumes when qsig -s resume is issued
        """
        # Set mem in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.ncpus': '4'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")

        job = self.server.status(JOB, id=jid1)

        rr = "(%s:ncpus=0)" % self.mom.shortname
        self.assertEqual(job[0][ATTR_released], rr,
                         msg="resources_released incorrect")

        # resume job
        self.server.sigjob(jobid=jid1, signal="resume")
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

    def test_resuming_with_no_res_released_multi_vnode(self):
        """
        Set restrict_res_to_release_on_suspend to a resource that multi-vnode
        job does not request and then suspend this running job using qsig
        check if such a job resumes when qsig -s resume is issued
        """
        # Set mem in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        vn_attrs = {ATTR_rescavail + '.ncpus': 2,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.server.create_vnodes("vnode1", vn_attrs, 1,
                                  self.mom, fname="vnodedef1")
        # Append a vnode
        vn_attrs = {ATTR_rescavail + '.ncpus': 6,
                    ATTR_rescavail + '.mem': '1024mb'}
        self.server.create_vnodes("vnode2", vn_attrs, 1,
                                  self.mom, additive=True, fname="vnodedef2")
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select':
                           '1:ncpus=2+1:ncpus=6',
                           ATTR_l + '.place': 'vscatter'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")

        job = self.server.status(JOB, id=jid1)

        rr = "(vnode1[0]:ncpus=0)+(vnode2[0]:ncpus=0)"
        self.assertEqual(job[0][ATTR_released], rr,
                         msg="resources_released incorrect")

        # resume job
        self.server.sigjob(jobid=jid1, signal="resume")
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

    def test_resuming_excljob_with_no_res_released(self):
        """
        Set restrict_res_to_release_on_suspend to a resource that an node excl
        job does not request and then suspend this running job using peemption
        check if such a job resumes when high priority job is deleted
        """
        # Set mem in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_l + '.place': 'excl'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {ATTR_l + '.select': '1:ncpus=2',
             ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 45}, id=jid1)

        job = self.server.status(JOB, id=jid1)

        rr = "(%s:ncpus=0)" % self.mom.shortname
        self.assertEqual(job[0][ATTR_released], rr,
                         msg="resources_released incorrect")

        # resume job
        self.server.deljob(jid2, wait=True)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

    def test_normal_user_unable_to_see_res_released(self):
        """
        Check if normal user (non-operator, non-manager) has privileges to see
        resources_released and resource_released_list attribute in job status
        """
        # Set mem in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        # suspend job
        self.server.sigjob(jobid=jid1, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

        # stat the job as a normal user
        attrs = self.server.status(JOB, id=jid1, runas=TEST_USER)
        self.assertFalse("resources_released" in attrs[0],
                         "Normal user can see resources_released "
                         "which is not expected")

        self.assertFalse("resource_released_list.mem" in attrs[0],
                         "Normal user can see resources_released_list "
                         "which is not expected")

    def test_if_node_gets_oversubscribed(self):
        """
        Check if the node gets oversubscribed if a filler job runs
        on resources left on the node after suspension.
        """
        # Set mem in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {ATTR_sched_preempt_enforce_resumption: True}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=2:mem=512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a filler job
        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=3',
                           ATTR_l + '.walltime': 50})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid2)

        # Submit a high priority job
        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.select': '1:ncpus=1:mem=2gb',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 100})
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        # Check that resources_assigned is not exceeding resources_available
        ras_ncpus = ATTR_rescassn + '.ncpus'
        rav_ncpus = ATTR_rescavail + '.ncpus'
        rv = self.server.status(
            NODE, [ras_ncpus, rav_ncpus], id=self.mom.shortname)
        self.assertNotEqual(rv, None)

        self.assertLessEqual(rv[0][ras_ncpus], rv[0][rav_ncpus],
                             msg="pbs released resource ncpus incorrectly")

        # Expect filler job to be in queued state because
        # suspended job did not release any ncpus
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid2)

    def test_suspended_job_gets_calendered(self):
        """
        Check if a job which releases limited amount of resources gets
        calendared in the same cycle when it gets suspended.
        """
        # Set mem in restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {ATTR_sched_preempt_enforce_resumption: True}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        # Set 5 ncpus available on the node
        a = {ATTR_rescavail + '.ncpus': 5}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=3:mem=1512mb'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job
        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=2:mem=2gb',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 100})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

        # Check if the job is calendared
        self.scheduler.log_match(
            jid1 + ";Can't find start time estimate", existence=False,
            max_attempts=2)

    def helper_test_preempt_release_all(self, preempt_method):
        """
        Helper function to test that when preempting jobs, all resources
        are released during preemption simulation for R and C methods
        """
        if preempt_method == "R":
            schedlog_msg = "Job preempted by requeuing"
        elif preempt_method == "C":
            schedlog_msg = "Job preempted by checkpointing"
        else:
            raise Exception("Unexpected value of argument preempt_method: %s"
                            % (preempt_method))

        a = {ATTR_restrict_res_to_release_on_suspend: 'mem'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'preempt_order': preempt_method}, runas=ROOT_USER)

        # Set 1gb mem available on the node
        a = {ATTR_rescavail + '.ncpus': "2"}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        # Submit a low priority jobs which takes up all of the ncpus
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=2'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Submit a high priority job which requests 1 ncpus
        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_q: 'expressq'})
        jid2 = self.server.submit(j2)

        # Even though server is configured to only release mem for suspend,
        # for requeue and checkpointing, we should have released ncpus as well
        # and correctly preempted the low priority job
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.scheduler.log_match(jid1 + ";" + schedlog_msg)

    def test_preempt_requeue_release_all(self):
        """
        Test that when preempting jobs via Requeue, all resources
        are release during the preemption simulation
        """
        self.helper_test_preempt_release_all("R")

    def test_preempt_checkpoint_release_all(self):
        """
        Test that when preempting jobs via Checkpointing, all resources
        are release during the preemption simulation
        """
        # Create checkpoint
        chk_script = """#!/bin/bash
                kill $1
                exit 0
                """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        self.chk_file = self.du.create_temp_file(body=chk_script,
                                                 dirname=pbs_home)
        self.du.chmod(path=self.chk_file, mode=0o755)
        self.du.chown(path=self.chk_file, uid=0, gid=0, sudo=True)
        c = {'$action': 'checkpoint_abort 30 !' + self.chk_file + ' %sid'}
        self.mom.add_config(c)

        self.helper_test_preempt_release_all("C")

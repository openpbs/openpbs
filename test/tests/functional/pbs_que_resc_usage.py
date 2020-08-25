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


class TestQueRescUsage(TestFunctional):
    """
    Test resource behavior after set/unset/assign/release resource on the queue
    """
    err_msg = 'Failed to get the expected resource value'

    def setUp(self):
        TestFunctional.setUp(self)
        self.server.manager(MGR_CMD_SET, NODE, {
                            'resources_available.ncpus': 10},
                            self.mom.shortname)

    def create_custom_resc(self):
        """
        function to create the resource named as "foo"
        """
        self.server.manager(MGR_CMD_CREATE, RSC, {
                            'type': 'long', 'flag': 'q'}, id='foo')
        self.scheduler.add_resource('foo')
        self.server.manager(MGR_CMD_SET, QUEUE, {
                            'resources_available.foo': 6}, id='workq')

    def test_resc_assigned_set_unset(self):
        """
        Test "resources_assigned" attribute of the resource and it's behavior
        during set/unset
        """

        # set a resource and unset it without using
        self.server.manager(MGR_CMD_SET, QUEUE, {
                            'resources_available.ncpus': 4}, id='workq')
        q_status = self.server.status(QUEUE, id='workq')
        self.assertEqual(
            int(q_status[0]['resources_available.ncpus']), 4, self.err_msg)
        self.assertNotIn('resources_assigned.ncpus',
                         q_status[0], self.err_msg)
        self.server.manager(MGR_CMD_UNSET, QUEUE,
                            'resources_available.ncpus', id='workq')
        q_status = self.server.status(QUEUE, id='workq')
        self.assertNotIn('resources_available.ncpus',
                         q_status[0], self.err_msg)

        # set the resource and unset it after using
        a = {'resources_available.ncpus': 8}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq')
        q_status = self.server.status(QUEUE, id='workq')
        self.assertEqual(
            int(q_status[0]['resources_available.ncpus']), 8, self.err_msg)
        # job submission
        j_attr = {'Resource_List.ncpus': '3'}
        j1 = Job(attrs=j_attr)
        j1.set_sleep_time(30)
        jid_1 = self.server.submit(j1)
        j2 = Job(attrs=j_attr)
        j2.set_sleep_time(30)
        jid_2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, jid_1)
        self.server.expect(JOB, {'job_state': 'R'}, jid_2)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.ncpus', id='workq')
        self.assertEqual(
            int(q_status[0]['resources_assigned.ncpus']), 6, self.err_msg)
        self.server.manager(MGR_CMD_UNSET, QUEUE,
                            'resources_available.ncpus', id='workq')
        q_status = self.server.status(QUEUE, id='workq')
        self.assertNotIn('resources_available.ncpus',
                         q_status[0], self.err_msg)
        self.assertIn('resources_assigned.ncpus',
                      q_status[0], self.err_msg)

        # Restart the server() and check "resources_assigned" value when
        # resource is not set but still some jobs are running in the system
        # and using the same resource.
        self.server.restart()
        q_status = self.server.status(QUEUE, id='workq')
        self.assertNotIn('resources_available.ncpus',
                         q_status[0], self.err_msg)
        self.assertEqual(
            int(q_status[0]['resources_assigned.ncpus']), 6, self.err_msg)
        # If no jobs are running at the time of restart the server
        self.server.expect(JOB, 'queue', op=UNSET, id=jid_1)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid_2)
        self.server.restart()
        q_status = self.server.status(QUEUE, id='workq')
        self.assertNotIn('resources_available.ncpus',
                         q_status[0], self.err_msg)
        self.assertNotIn('resources_assigned.ncpus',
                         q_status[0], self.err_msg)

    def test_resources_assigned_with_zero_val(self):
        """
        In PBS we can request +ve or -ve values so sometimes resources_assigned
        becomes zero despite some jobs are still using the same resource.
        In this case resources_assigned shouldn't be unset if jobs are there
        in the system or else unset it.
        """

        # create a resource
        self.create_custom_resc()

        # resources_assigned is zero but still jobs are in the system
        j1_attr = {'Resource_List.foo': '3'}
        j1 = Job(attrs=j1_attr)
        j1.set_sleep_time(30)
        jid_1 = self.server.submit(j1)
        # requesting negative resource here
        j2_attr = {'Resource_List.foo': '-3'}
        j2 = Job(attrs=j2_attr)
        j2.set_sleep_time(30)
        jid_2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, jid_1)
        self.server.expect(JOB, {'job_state': 'R'}, jid_2)
        q_status = self.server.status(QUEUE, id='workq')
        self.assertEqual(
            int(q_status[0]['resources_assigned.foo']), 0, self.err_msg)
        self.server.manager(MGR_CMD_UNSET, QUEUE,
                            'resources_available.foo', id='workq')
        self.server.restart()
        q_status = self.server.status(QUEUE, id='workq')
        self.assertEqual(
            int(q_status[0]['resources_assigned.foo']), 0, self.err_msg)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid_1)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid_2)
        # jobs are finished now, resources_assigned should unset this time
        self.server.restart()
        q_status = self.server.status(QUEUE, id='workq')
        self.assertNotIn('resources_assigned.foo',
                         q_status[0], self.err_msg)

    def test_resources_assigned_deletion(self):
        """
        Test resources_assigned.<resc_name> deletion from the system
        """
        # create a resource
        self.create_custom_resc()
        # submit jobs
        j_attr = {'Resource_List.foo': '3'}
        j1 = Job(attrs=j_attr)
        j1.set_sleep_time(30)
        jid_1 = self.server.submit(j1)
        j2 = Job(attrs=j_attr)
        j2.set_sleep_time(30)
        jid_2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, jid_1)
        self.server.expect(JOB, {'job_state': 'R'}, jid_2)
        # try to delete the resource when it's busy on job
        try:
            self.server.manager(MGR_CMD_DELETE, RSC, id='foo')
        except PbsManagerError as e:
            self.assertIn("Resource busy on job", e.msg[0])
        self.server.expect(JOB, 'queue', op=UNSET, id=jid_1)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid_2)
        # now jobs has been finished, try to delete the resource again
        self.server.manager(MGR_CMD_DELETE, RSC, id='foo')
        q_status = self.server.status(QUEUE, id='workq')
        self.assertNotIn('resources_assigned.foo',
                         q_status[0], self.err_msg)
        self.assertNotIn('resources_available.foo',
                         q_status[0], self.err_msg)

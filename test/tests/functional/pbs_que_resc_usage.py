# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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
import time


class TestQueRescUsage(TestFunctional):
    """
    Test built-in and custom resource behavior after
    set/unset/assign/release resource on the queue
    """
    err_msg = 'Failed to get the expected resource value/result'

    def setUp(self):
        TestFunctional.setUp(self)
        self.server.manager(MGR_CMD_SET, NODE, {
                            'resources_available.ncpus': 5},
                            self.mom.shortname)
        a = {'queue_type': 'execution', 'enabled': True, 'started': True}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='new_q')

    def test_built_in_resc(self):
        """
        Test built-in resource and check the assigned resource value
        after unset and shouldn't set to any negative value
        """
        # Unset the resource after job completion
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='new_q')
        j_attr = {ATTR_queue: 'new_q', 'Resource_List.select': '1:ncpus=3'}
        j = Job(TEST_USER, j_attr)
        j.set_sleep_time(20)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.ncpus', id='new_q', extend='f')
        self.assertEqual(
            int(q_status[0]['resources_assigned.ncpus']), 3, self.err_msg)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.ncpus', id='new_q', extend='f')
        self.assertEqual(
            int(q_status[0]['resources_assigned.ncpus']), 0, self.err_msg)
        self.server.manager(MGR_CMD_UNSET, QUEUE,
                            'resources_available.ncpus', id='new_q')
        q_status = self.server.status(QUEUE, id='new_q', extend='f')
        self.assertNotIn('resources_available.ncpus',
                         q_status[0].keys(), self.err_msg)
        self.assertNotIn('resources_assigned.ncpus',
                         q_status[0].keys(), self.err_msg)

        # Unset the resource before job completion
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='new_q')
        j = Job(TEST_USER, j_attr)
        j.set_sleep_time(50)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.ncpus', id='new_q', extend='f')
        self.assertEqual(
            int(q_status[0]['resources_assigned.ncpus']), 3, self.err_msg)
        self.server.manager(MGR_CMD_UNSET, QUEUE,
                            'resources_available.ncpus', id='new_q')
        q_status = self.server.status(QUEUE, id='new_q', extend='f')
        self.assertNotIn('resources_available.ncpus',
                         q_status[0].keys(), self.err_msg)
        self.assertEqual(
            int(q_status[0]['resources_assigned.ncpus']), 3, self.err_msg)
        self.server.delete(jid, wait=True)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.ncpus', id='new_q', extend='f')
        self.assertEqual(
            int(q_status[0]['resources_assigned.ncpus']), 0, self.err_msg)

    def test_custom_resc(self):
        """
        Test custom resource and check the assigned resource value
        after unset and shouldn't set to any negative value
        """
        # Unset the resource after job completion
        self.server.manager(MGR_CMD_CREATE, RSC, {
                            'type': 'long', 'flag': 'q'}, id='foo')
        self.scheduler.add_resource('foo')
        self.server.manager(MGR_CMD_SET, QUEUE, {
                            'resources_available.foo': 11}, id='new_q')
        j_attr = {ATTR_queue: 'new_q',
                  'Resource_List.select': '1:ncpus=1',
                  'Resource_List.foo': '5'}
        j = Job(TEST_USER, j_attr)
        j.set_sleep_time(20)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.foo', id='new_q', extend='f')
        self.assertEqual(
            int(q_status[0]['resources_assigned.foo']), 5, self.err_msg)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)
        self.server.manager(MGR_CMD_UNSET, QUEUE,
                            'resources_available.foo', id='new_q')
        q_status = self.server.status(QUEUE, id='new_q', extend='f')
        self.assertNotIn('resources_available.foo',
                         q_status[0].keys(), self.err_msg)
        self.assertNotIn(
            'resources_assigned.foo',
            q_status[0].keys(),
            self.err_msg)

        # Unset the resource before job completion
        self.server.manager(MGR_CMD_SET, QUEUE, {
                            'resources_available.foo': 11}, id='new_q')
        j_attr = {ATTR_queue: 'new_q',
                  'Resource_List.select': '1:ncpus=1',
                  'Resource_List.foo': '5'}
        j = Job(TEST_USER, j_attr)
        j.set_sleep_time(50)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        j_1 = Job(TEST_USER, j_attr)
        j_1.set_sleep_time(50)
        jid_1 = self.server.submit(j_1)
        self.server.expect(JOB, {'job_state': 'R'}, jid_1)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.foo', id='new_q', extend='f')
        self.assertEqual(
            int(q_status[0]['resources_assigned.foo']), 10, self.err_msg)
        self.server.manager(MGR_CMD_UNSET, QUEUE,
                            'resources_available.foo', id='new_q')
        q_status = self.server.status(QUEUE, id='new_q', extend='f')
        self.assertNotIn('resources_available.foo',
                         q_status[0].keys(), self.err_msg)
        self.assertEqual(
            int(q_status[0]['resources_assigned.foo']), 10, self.err_msg)
        # delete one job only and check resource_assigned
        self.server.delete(jid, wait=True)
        q_status = self.server.status(
            QUEUE, 'resources_assigned.foo', id='new_q', extend='f')
        self.assertEqual(
            int(q_status[0]['resources_assigned.foo']), 5, self.err_msg)
        # delete last job in queue
        self.server.delete(jid_1, wait=True)
        q_status = self.server.status(QUEUE, id='new_q', extend='f')
        self.assertNotIn(
            'resources_assigned.foo',
            q_status[0].keys(),
            self.err_msg)

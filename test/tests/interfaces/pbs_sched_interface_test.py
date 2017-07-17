# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from tests.interfaces import *


@tags('multisched')
class TestSchedulerInterface(TestInterfaces):

    """
    Test suite to test different scheduler interfaces
    """

    def setUp(self):
        TestInterfaces.setUp(self)

        self.server.manager(MGR_CMD_CREATE,
                            SCHED,
                            id="TestCommonSched")

    def test_duplicate_scheduler_name(self):
        """
        Check for the scheduler object name.
        """
        try:
            self.server.manager(MGR_CMD_CREATE,
                                SCHED,
                                id="TestCommonSched")
        except PbsManagerError, e:
            if self.server.get_op_mode() == PTL_CLI:
                self.assertTrue(
                    'qmgr: Error (15211) returned from server' in e.msg[1])

    def test_permission_on_scheduler(self):
        """
        Check for the permission to create/delete/modify scheduler object.
        """
        # Check for create permission
        try:
            self.server.manager(MGR_CMD_CREATE,
                                SCHED,
                                id="testCreateSched",
                                runas=OPER_USER)
        except PbsManagerError, e:
            if self.server.get_op_mode() == PTL_CLI:
                self.assertTrue(
                    'qmgr: Error (15007) returned from server' in e.msg[1])

        self.server.manager(MGR_CMD_CREATE,
                            SCHED,
                            id="testCreateSched",
                            runas=ROOT_USER)

        # Check for delete permission
        self.server.manager(MGR_CMD_CREATE,
                            SCHED,
                            id="testDeleteSched")
        try:
            self.server.manager(MGR_CMD_DELETE,
                                SCHED,
                                id="testDeleteSched",
                                runas=OPER_USER)
        except PbsManagerError, e:
            if self.server.get_op_mode() == PTL_CLI:
                self.assertTrue(
                    'qmgr: Error (15007) returned from server' in e.msg[1])

        self.server.manager(MGR_CMD_DELETE,
                            SCHED,
                            id="testDeleteSched",
                            runas=ROOT_USER)

        # Check for attribute set permission
        try:
            self.server.manager(MGR_CMD_SET,
                                SCHED,
                                {'sched_cycle_length': 12000},
                                id="TestCommonSched",
                                runas=OPER_USER)
        except PbsManagerError, e:
            if self.server.get_op_mode() == PTL_CLI:
                self.assertTrue(
                    'qmgr: Error (15007) returned from server' in e.msg[1])

        self.server.manager(MGR_CMD_SET,
                            SCHED,
                            {'sched_cycle_length': 12000},
                            id="TestCommonSched",
                            runas=ROOT_USER,
                            expect=True)

    def test_delete_default_sched(self):
        """
        Delete default scheduler.
        """
        try:
            self.server.manager(MGR_CMD_DELETE,
                                SCHED,
                                id="default")
        except PbsManagerError, e:
            if self.server.get_op_mode() == PTL_CLI:
                self.assertTrue(
                    'qmgr: Error (15214) returned from server' in e.msg[1])

    def test_set_and_unset_sched_attributes(self):
        """
        Set and unset an attribute of a scheduler object .
        """
        # Set an attribute of a scheduler object.
        self.server.manager(MGR_CMD_SET,
                            SCHED,
                            {'sched_cycle_length': 1234},
                            id="TestCommonSched",
                            expect=True)

        # Unset an attribute of a scheduler object.
        self.server.manager(MGR_CMD_UNSET,
                            SCHED,
                            'sched_cycle_length',
                            id="TestCommonSched")
        self.server.manager(MGR_CMD_LIST,
                            SCHED,
                            id="TestCommonSched")
        sched = None
        sched = self.server.schedulers['TestCommonSched']
        self.assertNotEqual(sched, None)
        self.assertEqual(
            sched.attributes['sched_cycle_length'],
            '00:20:00')

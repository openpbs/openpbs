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

from tests.interfaces import *


class TestSchedulerInterface(TestInterfaces):

    """
    Test suite to test different scheduler interfaces
    """

    def setUp(self):
        TestInterfaces.setUp(self)
        a = {'partition': 'P1',
             'sched_host': self.server.hostname,
             'sched_port': '15051'}
        self.server.manager(MGR_CMD_CREATE,
                            SCHED, a,
                            id="TestCommonSched")
        self.sched_configure("TestCommonSched")

    def test_duplicate_scheduler_name(self):
        """
        Check for the scheduler object name.
        """
        try:
            self.server.manager(MGR_CMD_CREATE,
                                SCHED,
                                {'sched_port': '15052'},
                                id="TestCommonSched")
        except PbsManagerError as e:
            if self.server.get_op_mode() == PTL_CLI:
                self.assertTrue(
                    'qmgr: Error (15211) returned from server' in e.msg[1])

    def test_invalid_sched_port(self):
        """
        Test setting invalid port.
        """
        try:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_port': 'asdf'},
                                id="TestCommonSched",
                                runas=ROOT_USER)
        except PbsManagerError as e:
            err_msg = "Illegal attribute or resource value"
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")

    def test_permission_on_scheduler(self):
        """
        Check for the permission to create/delete/modify scheduler object.
        """
        # Check for create permission
        try:
            self.server.manager(MGR_CMD_CREATE,
                                SCHED,
                                {'sched_port': '15052'},
                                id="testCreateSched",
                                runas=OPER_USER)
        except PbsManagerError as e:
            if self.server.get_op_mode() == PTL_CLI:
                self.assertTrue(
                    'qmgr: Error (15007) returned from server' in e.msg[1])

        self.server.manager(MGR_CMD_CREATE,
                            SCHED,
                            {'sched_port': '15052'},
                            id="testCreateSched",
                            runas=ROOT_USER)

        # Check for delete permission
        self.server.manager(MGR_CMD_CREATE,
                            SCHED,
                            {'sched_port': '15052'},
                            id="testDeleteSched")
        try:
            self.server.manager(MGR_CMD_DELETE,
                                SCHED,
                                id="testDeleteSched",
                                runas=OPER_USER)
        except PbsManagerError as e:
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
        except PbsManagerError as e:
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
        except PbsManagerError as e:
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
        a = {'sched_cycle_length': '00:20:00'}
        self.server.expect(SCHED, a, id='TestCommonSched', max_attempts=10)

    def test_sched_default_attrs(self):
        """
        Test all sched attributes are set by default on default scheduler
        """
        sched_priv = os.path.join(
            self.server.pbs_conf['PBS_HOME'], 'sched_priv')
        sched_logs = os.path.join(
            self.server.pbs_conf['PBS_HOME'], 'sched_logs')
        a = {'sched_port': 15004,
             'sched_host': self.server.hostname,
             'sched_priv': sched_priv,
             'sched_log': sched_logs,
             'scheduling': 'True',
             'scheduler_iteration': 600,
             'state': 'idle',
             'sched_cycle_length': '00:20:00'}
        self.server.expect(SCHED, a, id='default',
                           attrop=PTL_AND, max_attempts=10)

    def test_scheduling_attribute(self):
        """
        Test scheduling attribute on newly created scheduler is false
        unless made true
        """
        self.server.expect(SCHED, {'scheduling': 'False'},
                           id='TestCommonSched', max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'},
                            runas=ROOT_USER, id='TestCommonSched')
        self.server.expect(SCHED, {'scheduling': 'True'},
                           id='TestCommonSched', max_attempts=10)

    def test_set_sched_priv_log_duplicate_value(self):
        """
        Test setting of sched_priv and sched_log to a
        value assigned to another scheduler
        """
        err_msg = "Another Sched object also has same "
        err_msg += "value for its sched_priv directory"
        try:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_priv': '/var/spool/pbs/sched_priv'},
                                runas=ROOT_USER, id='TestCommonSched')
        except PbsManagerError as e:
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")
        err_msg = "Another Sched object also has same "
        err_msg += "value for its sched_log directory"
        try:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_log': '/var/spool/pbs/sched_logs'},
                                runas=ROOT_USER, id='TestCommonSched')
        except PbsManagerError as e:
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")

    def test_set_default_sched_not_permitted(self):
        """
        Test setting partition on default scheduler
        """
        err_msg = "Operation is not permitted on default scheduler"
        try:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'partition': 'P1'},
                                runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_priv': '/var/spool/somedir'},
                                runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_log': '/var/spool/somedir'},
                                runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")

    def test_sched_name_too_long(self):
        """
        Test creating a scheduler with name longer than 15 chars
        """
        try:
            self.server.manager(MGR_CMD_CREATE, SCHED,
                                runas=ROOT_USER, id="TestLongScheduler")
        except PbsManagerError as e:
            self.assertTrue("Scheduler name is too long" in e.msg[0],
                            "Error message is not expected")

    def test_set_default_sched_attrs(self):
        """
        Test setting scheduling and scheduler_iteration on default scheduler
        and it updates server attributes and vice versa
        """
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'},
                            runas=ROOT_USER)
        self.server.expect(SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'},
                            runas=ROOT_USER)
        self.server.expect(SCHED, {'scheduling': 'True'},
                           id='default', max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduler_iteration': 300},
                            runas=ROOT_USER)
        self.server.expect(SERVER, {'scheduler_iteration': 300})
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduler_iteration': 500},
                            runas=ROOT_USER)
        self.server.expect(SCHED, {'scheduler_iteration': 500},
                           id='default', max_attempts=10)

    def tearDown(self):
        self.du.run_cmd(self.server.hostname, [
                        'pkill', '-9', 'pbs_sched'], sudo=True)
        TestInterfaces.tearDown(self)

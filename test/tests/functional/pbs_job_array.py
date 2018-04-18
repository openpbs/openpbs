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


class TestJobArray(TestFunctional):
    """
    Test suite for PBSPro's job array feature
    """

    def test_arrayjob_Erecord_startval(self):
        """
        Check that an arrayjob's E record's 'start' value is not set to 0
        """
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2',
            'Resource_List.select': 'ncpus=1'
        })
        j.set_sleep_time(1)

        j_id = self.server.submit(j)

        # Check for the E record for the arrayjob
        acct_string = ";E;" + str(j_id)
        _, record = self.server.accounting_match(acct_string, max_attempts=10,
                                                 interval=1)

        # Extract the 'start' value from the E record
        values = record.split(";", 3)[3]
        start_str = " start="
        values_temp = values.split(start_str, 1)[1]
        start_val = int(values_temp.split()[0])

        # Verify that the value of 'start' isn't 0
        self.assertNotEqual(start_val, 0,
                            "E record value of 'start' for arrayjob is 0")

    def kill_and_restart_svr(self):
        try:
            self.server.stop('-KILL')
        except PbsServiceError as e:
            # The server failed to stop
            raise self.failureException("Server failed to stop:" + e.msg)

        try:
            self.server.start()
        except PbsServiceError as e:
            # The server failed to start
            raise self.failureException("Server failed to start:" + e.msg)

    def test_running_subjob_survive_restart(self):
        """
        Test to check if a running subjob of an array job survive a
        pbs_server restart
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-3', 'Resource_List.select': 'ncpus=1'})

        j.set_sleep_time(10)

        j_id = self.server.submit(j)
        subjid_2 = j.create_subjob_id(j_id, 2)

        # 1. check job array has begun
        self.server.expect(JOB, {'job_state': 'B'}, j_id)

        # 2. wait till subjob 2 starts running
        self.server.expect(JOB, {'job_state': 'R'}, subjid_2)

        # 3. Kill and restart the server
        self.kill_and_restart_svr()

        # 4. array job should be B
        self.server.expect(JOB, {'job_state': 'B'}, j_id, max_attempts=1)

        # 5. subjob 1 should be X
        self.server.expect(JOB, {'job_state': 'X'},
                           j.create_subjob_id(j_id, 1), max_attempts=1)

        # 6. subjob 2 should be R
        self.server.expect(JOB, {'job_state': 'R'}, subjid_2, max_attempts=1)

        # 7. subjob 3 should be Q
        self.server.expect(JOB, {'job_state': 'Q'},
                           j.create_subjob_id(j_id, 3), max_attempts=1)

    def test_running_subjob_survive_restart_with_history(self):
        """
        Test to check if a running subjob of an array job survive a
        pbs_server restart when history is enabled
        """
        attr = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        self.test_running_subjob_survive_restart()

    def test_suspended_subjob_survive_restart(self):
        """
        Test to check if a suspended subjob of an array job survive a
        pbs_server restart
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-3', 'Resource_List.select': 'ncpus=1'})

        j.set_sleep_time(10)

        j_id = self.server.submit(j)
        subjid_2 = j.create_subjob_id(j_id, 2)

        # 1. check job array has begun
        self.server.expect(JOB, {'job_state': 'B'}, j_id)

        # 2. wait till subjob_2 starts running
        self.server.expect(JOB, {'job_state': 'R'}, subjid_2)

        try:
            self.server.sigjob(subjid_2, 'suspend')
        except PbsSignalError as e:
            raise self.failureException("Failed to suspend subjob:" + e.msg)

        self.server.expect(JOB, {'job_state': 'S'}, subjid_2, max_attempts=1)

        # 3. Kill and restart the server
        self.kill_and_restart_svr()

        # 4. array job should be B
        self.server.expect(JOB, {'job_state': 'B'}, j_id, max_attempts=1)

        # 5. subjob_2 should be S
        self.server.expect(JOB, {'job_state': 'S'}, subjid_2, max_attempts=1)

        try:
            self.server.sigjob(subjid_2, 'resume')
        except PbsSignalError as e:
            raise self.failureException("Failed to resume subjob:" + e.msg)

    def test_suspended_subjob_survive_restart_with_history(self):
        """
        Test to check if a suspended subjob of an array job survive a
        pbs_server restart when history is enabled
        """
        attr = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        self.test_suspended_subjob_survive_restart()

    def test_deleted_q_subjob_survive_restart(self):
        """
        Test to check if a deleted queued subjob of an array job survive a
        pbs_server restart when history is disabled
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-3', 'Resource_List.select': 'ncpus=1'})

        j.set_sleep_time(10)

        j_id = self.server.submit(j)
        subjid_3 = j.create_subjob_id(j_id, 3)

        self.server.expect(JOB, {'job_state': 'B'}, j_id)
        self.server.deljob(subjid_3)
        self.server.expect(JOB, {'job_state': 'X'}, subjid_3)

        self.kill_and_restart_svr()

        self.server.expect(JOB, {'job_state': 'B'}, j_id, max_attempts=1)
        self.server.expect(JOB, {'job_state': 'X'}, subjid_3, max_attempts=1)

    def test_deleted_q_subjob_survive_restart_w_history(self):
        """
        Test to check if a deleted queued subjob of an array job survive a
        pbs_server restart when history is enabled
        """
        attr = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        self.test_deleted_q_subjob_survive_restart()

    def test_deleted_r_subjob_survive_restart(self):
        """
        Test to check if a deleted running subjob of an array job survive a
        pbs_server restart when history is disabled
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-3', 'Resource_List.select': 'ncpus=1'})

        j.set_sleep_time(10)

        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)

        self.server.expect(JOB, {'job_state': 'B'}, j_id)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_1)
        self.server.deljob(subjid_1)
        self.server.expect(JOB, {'job_state': 'X'}, subjid_1)

        self.kill_and_restart_svr()

        self.server.expect(JOB, {'job_state': 'B'}, j_id, max_attempts=1)
        self.server.expect(JOB, {'job_state': 'X'}, subjid_1, max_attempts=1)

    def test_deleted_r_subjob_survive_restart_w_history(self):
        """
        Test to check if a deleted running subjob of an array job survive a
        pbs_server restart when history is enabled
        """
        attr = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        self.test_deleted_q_subjob_survive_restart()

    def test_qdel_expired_subjob(self):
        """
        Test to check if qdel of a subjob is disallowed
        """
        attr = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-3', 'Resource_List.select': 'ncpus=1'})

        j.set_sleep_time(5)

        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)

        # 1. check job array has begun
        self.server.expect(JOB, {'job_state': 'B'}, j_id)

        # 2. wait till subjob 1 becomes expired
        self.server.expect(JOB, {'job_state': 'X'}, subjid_1)

        try:
            self.server.deljob(subjid_1)
        except PbsDeljobError as e:
            err_msg = "Request invalid for finished array subjob"
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")
        else:
            raise self.failureException("subjob in X state can be deleted")

        try:
            self.server.deljob(subjid_1, extend="deletehist")
        except PbsDeljobError as e:
            err_msg = "Request invalid for finished array subjob"
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")
        else:
            raise self.failureException("subjob in X state can be deleted")

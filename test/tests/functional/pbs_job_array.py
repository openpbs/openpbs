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
        self.server.isUp()
        rv = self.is_server_licensed(self.server)
        _msg = 'No license found on server %s' % (self.server.shortname)
        self.assertTrue(rv, _msg)

    def test_running_subjob_survive_restart(self):
        """
        Test to check if a running subjob of an array job survive a
        pbs_server restart
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-3', 'Resource_List.select': 'ncpus=1'})

        j.set_sleep_time(20)

        j_id = self.server.submit(j)
        subjid_2 = j.create_subjob_id(j_id, 2)

        # 1. check job array has begun
        self.server.expect(JOB, {'job_state': 'B'}, j_id)

        # 2. wait till subjob 2 starts running
        self.server.expect(JOB, {'job_state': 'R'}, subjid_2, offset=20)

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

    def test_subjob_comments(self):
        """
        Test subjob comments for finished and terminated subjobs
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-30', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(8)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        subjid_2 = j.create_subjob_id(j_id, 2)
        self.server.expect(JOB, {'comment': 'Subjob finished'}, subjid_1,
                           offset=8)
        self.server.delete(subjid_2, extend='force')
        self.server.expect(JOB, {'comment': 'Subjob terminated'}, subjid_2)
        self.kill_and_restart_svr()
        self.server.expect(
            JOB, {'comment': 'Subjob finished'}, subjid_1, max_attempts=1)

    def test_subjob_comments_with_history(self):
        """
        Test subjob comments for finished, failed and terminated subjobs
        when history is enabled
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(5)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        subjid_2 = j.create_subjob_id(j_id, 2)
        self.server.delete(subjid_2, extend='force')
        self.server.expect(
            JOB, {'comment': (MATCH_RE, 'terminated')}, subjid_2, extend='x')
        self.server.expect(JOB, {'comment': (
            MATCH_RE, 'Job run at.*and finished')}, subjid_1, extend='x')
        self.kill_and_restart_svr()
        self.server.expect(JOB, {'comment': (
            MATCH_RE, 'Job run at.*and finished')}, subjid_1, extend='x',
            max_attempts=1)
        script_body = "exit 1"
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.create_script(body=script_body)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        subjid_2 = j.create_subjob_id(j_id, 2)
        self.server.expect(
            JOB, {'comment': (MATCH_RE, 'Job run at.*and failed')}, subjid_1,
            extend='x')
        self.server.expect(
            JOB, {'comment': (MATCH_RE, 'Job run at.*and failed')}, subjid_2,
            extend='x')
        self.kill_and_restart_svr()
        self.server.expect(
            JOB, {'comment': (MATCH_RE, 'Job run at.*and failed')}, subjid_1,
            extend='x', max_attempts=1)
        self.server.expect(
            JOB, {'comment': (MATCH_RE, 'Job run at.*and failed')}, subjid_2,
            extend='x')

    def test_multiple_server_restarts(self):
        """
        Test subjobs wont rerun after multiple server restarts
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        a = {'job_state': 'R', 'run_count': 1}
        self.server.expect(JOB, a, subjid_1, attrop=PTL_AND)
        for _ in range(5):
            self.kill_and_restart_svr()
            self.server.expect(
                JOB, a, subjid_1, attrop=PTL_AND, max_attempts=1)

    def test_job_array_history_duration(self):
        """
        Test that job array and subjobs are purged after history duration
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'job_history_duration': 30}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(5)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        subjid_2 = j.create_subjob_id(j_id, 2)
        a = {'job_state': 'R', 'run_count': 1}
        self.server.expect(JOB, a, subjid_1, attrop=PTL_AND)
        self.server.delete(subjid_1, extend='force')
        b = {'job_state': 'X'}
        self.server.expect(JOB, b, subjid_1)
        self.server.expect(JOB, a, subjid_2, attrop=PTL_AND)
        msg = "Waiting for 150 secs as server will purge db once"
        msg += " in 2 mins plus 30 sec of history duration"
        self.logger.info(msg)
        self.server.expect(JOB, 'job_state', op=UNSET,
                           id=subjid_1, offset=150, extend='x')
        self.server.expect(JOB, 'job_state', op=UNSET,
                           id=subjid_2, extend='x')

    def test_queue_deletion_after_terminated_subjob(self):
        """
        Test that queue can be deleted after the job array is
        terminated and server is restarted.
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        a = {'job_state': 'R', 'run_count': 1}
        self.server.expect(JOB, a, subjid_1, attrop=PTL_AND)
        self.server.delete(subjid_1, extend='force')
        self.kill_and_restart_svr()
        self.server.delete(j_id, wait=True)
        self.server.manager(MGR_CMD_DELETE, QUEUE, id='workq')

    def test_held_job_array_survive_server_restart(self):
        """
        Test held job array can be released after server restart
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(60)
        j_id = self.server.submit(j)
        j_id2 = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        subjid_3 = j.create_subjob_id(j_id2, 1)
        a = {'job_state': 'R', 'run_count': 1}
        self.server.expect(JOB, a, subjid_1, attrop=PTL_AND)
        self.server.holdjob(j_id2, USER_HOLD)
        self.server.expect(JOB, {'job_state': 'H'}, j_id2)
        self.kill_and_restart_svr()
        self.server.delete(j_id, wait=True)
        self.server.expect(JOB, {'job_state': 'H'}, j_id2)
        self.server.rlsjob(j_id2, USER_HOLD)
        self.server.expect(JOB, {'job_state': 'B'}, j_id2)
        self.server.expect(JOB, a, subjid_3, attrop=PTL_AND)

    def test_held_job_array_survive_server_restart_w_history(self):
        """
        Test held job array can be released after server restart
        when history is enabled
        """
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.test_held_job_array_survive_server_restart()

    def test_subjobs_qrun(self):
        """
        Test that job array's subjobs can be qrun
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(60)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        self.server.runjob(subjid_1)
        self.server.expect(JOB, {'job_state': 'B'}, j_id)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_1)

    def test_dependent_job_array_server_restart(self):
        """
        Check Job array dependency is not released after server restart
        """
        a = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(10)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        subjid_2 = j.create_subjob_id(j_id, 2)
        self.server.expect(JOB, {'job_state': 'B'}, j_id)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_2)
        depend_value = 'afterok:' + j_id
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1',
            ATTR_depend: depend_value})
        j_id2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'H'}, j_id2)
        self.kill_and_restart_svr()
        self.server.expect(JOB, {'job_state': 'F'},
                           j_id, extend='x', interval=5)
        self.server.expect(JOB, {'job_state': 'B'}, j_id2, interval=5)

    def test_rerun_subjobs_server_restart(self):
        """
        Test that subjobs which are requeued remain queued after server restart
        """
        a = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(60)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_1)
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.rerunjob(subjid_1)
        self.server.expect(JOB, {'job_state': 'Q'}, subjid_1)
        self.kill_and_restart_svr()
        self.server.expect(JOB, {'job_state': 'Q'}, subjid_1)
        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, subjid_1)

    def test_rerun_node_fail_requeue(self):
        """
        Test sub jobs gets requeued after node_fail_requeue time
        """
        a = {'node_fail_requeue': 10}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(60)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_1)
        self.mom.stop()
        self.server.expect(JOB, {'job_state': 'Q'}, subjid_1, offset=5)

    def test_qmove_job_array(self):
        """
        Test job array's can be qmoved to a high priority queue
        and qmoved job array preempts running subjob
        """
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        a = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(60)
        j_id = self.server.submit(j)
        subjid_1 = j.create_subjob_id(j_id, 1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_1)
        j_id2 = self.server.submit(j)
        subjid_3 = j.create_subjob_id(j_id2, 1)
        self.server.movejob(j_id2, 'wq1')
        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(JOB, {'job_state': 'S'}, subjid_1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid_3)

    def test_delete_history_subjob_server_restart(self):
        """
        Test that subjobs can be deleted from history
        and they remain deleted after server restart
        """
        a = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        j.set_sleep_time(5)
        j_id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'F'}, j_id, extend='x', offset=5)
        self.server.delete(j_id, extend='deletehist')
        self.server.expect(JOB, 'job_state', op=UNSET, extend='x', id=j_id)
        self.kill_and_restart_svr()
        self.server.expect(JOB, 'job_state', op=UNSET, extend='x', id=j_id)

    def test_job_id_duplicate_server_restart(self):
        """
        Test that after server restart there is no duplication
        of job identifiers
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
        self.server.submit(j)
        j = Job(TEST_USER)
        self.server.submit(j)
        self.kill_and_restart_svr()
        try:
            j = Job(TEST_USER, attrs={
                ATTR_J: '1-2', 'Resource_List.select': 'ncpus=1'})
            self.server.submit(j)
        except PbsSubmitError as e:
            raise self.failureException("Failed to submit job: " + str(e.msg))

    def test_expired_subjobs_not_reported(self):
        """
        Test if a subjob is finished and moves to expired state,
        it is not reported to scheduler in the next scheduling
        cycle. Scheduler expects only running subjobs to be reported to it.
        """

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        req_node = ":host=" + self.mom.shortname
        res_req = {'Resource_List.select': '1:ncpus=1' + req_node,
                   'array_indices_submitted': '1-16',
                   'Resource_List.place': 'excl'}
        j1 = Job(TEST_USER, attrs=res_req)
        j1.set_sleep_time(2)
        jid1 = self.server.submit(j1)
        j1_sub1 = j1.create_subjob_id(jid1, 1)

        self.server.expect(JOB, {'job_state': 'X'}, j1_sub1)
        # Trigger a sched cycle
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        msg = j1_sub1 + ";" + "Subjob found in undesirable state"
        msg += ", ignoring this job"
        self.scheduler.log_match(msg, existence=False, max_attempts=10)

    def test_subjob_stdfile_custom_dir(self):
        """
        Test that subjobs standard error and out files are generated
        in the custom directory provided with oe qsub options
        """
        tmp_dir = self.du.mkdtemp(uid=TEST_USER.uid)
        a = {ATTR_e: tmp_dir, ATTR_o: tmp_dir, ATTR_J: '1-4'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(2)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        self.server.expect(JOB, ATTR_state, op=UNSET, id=jid)
        file_list = [name for name in os.listdir(
            tmp_dir) if os.path.isfile(os.path.join(tmp_dir, name))]
        self.assertEqual(8, len(file_list), 'expected 8 std files')
        for ext in ['.OU', '.ER']:
            for sub_ind in range(1, 5):
                f_name = j.create_subjob_id(jid, sub_ind) + ext
                if f_name not in file_list:
                    raise self.failureException("std file " + f_name
                                                + " not found")

    @skipOnCpuSet
    @skipOnCray
    def test_subjob_wrong_state(self):
        """
        Test that after submitting a job and restarting the server,
        the subjobs are not in the wrong substate and can be scheduled.
        """
        a = {'resources_available.ncpus': 200}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(attrs={ATTR_J: '1-200'})
        self.server.submit(j)
        # while the server is sending the jobs to the MoM, restart the server
        self.server.restart()
        # make sure the mom is free so the scheduler can run jobs on it
        self.server.expect(NODE, {'state': 'free'}, id=self.mom.shortname)
        self.logger.info('Sleeping to ensure licenses are received')
        time.sleep(5)
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        # ensure the sched cycle is finished
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'}, expect=True)
        # ensure all the subjobs are running
        self.server.expect(JOB, {'job_state=R': 200}, extend='t')

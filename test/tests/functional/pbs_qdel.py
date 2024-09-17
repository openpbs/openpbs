# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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
import re


class TestQdel(TestFunctional):
    """
    This test suite contains tests for qdel
    """

    def test_qdel_with_server_tagged_in_jobid(self):
        """
        Test to make sure that qdel uses server tagged in jobid instead of
        the PBS_SERVER conf setting
        """
        self.du.set_pbs_config(confs={'PBS_SERVER': 'not-a-server'})
        j = Job(TEST_USER)
        j.set_attributes({ATTR_q: 'workq@' + self.server.hostname})
        jid = self.server.submit(j)
        try:
            self.server.delete(jid)
        except PbsDeleteError as e:
            self.assertFalse(
                'Unknown Host' in e.msg[0],
                "Error message is not expected as server name is"
                "tagged in the jobid")
        self.du.set_pbs_config(confs={'PBS_SERVER': self.server.hostname})

    def test_qdel_unknown(self):
        """
        Test that qdel for an unknown job throws error saying the same
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.delete(jid, wait=True)
        try:
            self.server.delete(jid)
            self.fail("qdel didn't throw 'Unknown job id' error")
        except PbsDeleteError as e:
            self.assertEqual("qdel: Unknown Job Id " + jid, e.msg[0])

    def test_qdel_history_job(self):
        """
        Test deleting a history job after a custom resource is deleted
        The deletion of the history job happens in teardown
        """
        self.server.add_resource('foo')
        a = {'job_history_enable': 'True'}
        rc = self.server.manager(MGR_CMD_SET, SERVER, a)
        hook_body = "import pbs\n"
        hook_body += "e = pbs.event()\n"
        hook_body += "e.job.resources_used[\"foo\"] = \"10\"\n"
        a = {'event': 'execjob_epilogue', 'enabled': 'True'}
        self.server.create_import_hook("epi", a, hook_body)
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid,
                           extend='x', max_attempts=20)
        msg = "Resource allowed to be deleted"
        with self.assertRaises(PbsManagerError, msg=msg) as e:
            self.server.manager(MGR_CMD_DELETE, RSC, id="foo")
        m = "Resource busy on job"
        self.assertIn(m, e.exception.msg[0])
        self.server.delete(jid, extend='deletehist')

    def test_qdel_arrayjob_in_transit(self):
        """
        Test the array job deletion
        soon after they have been signalled for running.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'false'})
        a = {'resources_available.ncpus': 6}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-3', 'Resource_List.select': 'ncpus=1'})
        job_set = []
        for i in range(4):
            job_set.append(self.server.submit(j))
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'true'})
        self.server.delete(job_set)
        # Make sure that the counters are not going negative
        msg = "job*has already been deleted from delete job list"
        self.scheduler.log_match(msg, existence=False,
                                 max_attempts=3, regexp=True)
        # Make sure the last two jobs doesn't started running
        # while the deletion is in process
        for job in job_set[2:]:
            jobid, server = job.split('.')
            arrjob = jobid[-2:] + '[1]' + server
            msg = arrjob + ";Job Run at request of Scheduler"
            self.scheduler.log_match(msg, existence=False, max_attempts=3)

    def test_qdel_history_job_rerun(self):
        """
        Test rerunning a history job that was prematurely terminated due
        to a a downed mom.
        """
        a = {'job_history_enable': 'True', 'job_history_duration': '5',
             'job_requeue_timeout': '5', 'node_fail_requeue': '5',
             'scheduler_iteration': '5'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job()
        j.set_sleep_time(30)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.mom.stop()

        # Force job to be prematurely terminated
        try:
            self.server.deljob(jid)
        except PbsDeljobError as e:
            err_msg = "could not connect to MOM"
            self.assertTrue(err_msg in e.msg[0],
                            "Did not get the expected message")
            self.assertTrue(e.rc != 0, "Exit code shows success")
        else:
            raise self.failureException("qdel job did not return error")

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.mom.start()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        # Upon rerun, finished status should be '92' (Finished)
        a = {'job_state': 'F', 'substate': '92'}
        self.server.expect(JOB, a, extend='x',
                           offset=30, id=jid, interval=1)

    def test_qdel_history_job_rerun_nx(self):
        """
        Test rerunning a history job that was prematurely terminated due
        to a a downed mom.
        """
        a = {'job_history_enable': 'True', 'job_history_duration': '5',
             'job_requeue_timeout': '5', 'node_fail_requeue': '5',
             'scheduler_iteration': '5'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job()
        j.set_sleep_time(30)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.mom.stop()

        # Force job to be prematurely terminated and try to delete it more than
        # once.
        err_msg = "could not connect to MOM"
        msg = "qdel job did not return error"
        with self.assertRaises(PbsDeljobError, msg=msg) as e:
            self.server.deljob([jid, jid, jid, jid])
        self.assertIn(err_msg, e.exception.msg[0])
        self.assertNotEqual(e.exception.rc, 0)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.mom.start()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        # Upon rerun, finished status should be '92' (Finished)
        a = {'job_state': 'F', 'substate': '92'}
        self.server.expect(JOB, a, extend='x',
                           offset=1, id=jid, interval=1)

    def test_qdel_same_jobid_nx_00(self):
        """
        Test that qdel that deletes the job more than once in the same line.
        """
        a = {'job_history_enable': 'True'}
        rc = self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: "R"}, id=jid)
        self.server.delete([jid.split(".")[0], jid, jid, jid, jid], wait=True)
        self.server.expect(JOB, {'job_state': 'F', 'substate': 91}, id=jid,
                           extend='x', max_attempts=20)

    def test_qdel_same_jobid_nx_01(self):
        """
        Test that qdel that deletes the job more than once in the same line.
        Done twice.
        """
        a = {'job_history_enable': 'True'}
        rc = self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: "R"}, id=jid)
        self.server.delete([jid, jid], wait=True)
        self.server.expect(JOB, {'job_state': 'F', 'substate': 91}, id=jid,
                           extend='x', max_attempts=20)

        # this may take 2 or more times to break.
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: "R"}, id=jid)
        self.server.delete([jid, jid], wait=True)
        self.server.expect(JOB, {'job_state': 'F', 'substate': 91}, id=jid,
                           extend='x', max_attempts=20)

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: "R"}, id=jid)
        self.server.delete([jid, jid], wait=True)
        self.server.expect(JOB, {'job_state': 'F', 'substate': 91}, id=jid,
                           extend='x', max_attempts=20)

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: "R"}, id=jid)
        self.server.delete([jid, jid], wait=True)
        self.server.expect(JOB, {'job_state': 'F', 'substate': 91}, id=jid,
                           extend='x', max_attempts=20)

    def test_qdel_same_jobid_nx_02(self):
        """
        Test that qdel that deletes the job more than once in the same line.
        With rerun.
        """
        a = {'job_history_enable': 'True'}
        rc = self.server.manager(MGR_CMD_SET, SERVER, a)
        attrs = {ATTR_r: 'y'}
        j = Job(TEST_USER, attrs=attrs)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: "R"}, id=jid)
        self.server.delete([jid, jid, jid, jid, jid], wait=True)
        self.server.expect(JOB, {'job_state': 'F', 'substate': 91}, id=jid,
                           extend='x', max_attempts=20)

    def array_job_start(self, job_sleep_time, ncpus, sj_range=None):
        """
        Start an array job and capture job and subjob info
        """
        if not sj_range:
            sj_range = f"1-{ncpus}"
        elif isinstance(sj_range, int):
            sj_range = f"1-{sj_range}"
        a = {
            # 'log_events': 4095,
            'job_history_enable': 'True'
        }
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': ncpus}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={ATTR_J: sj_range})
        j.set_sleep_time(job_sleep_time)
        jid = self.server.submit(j)
        array_id = jid.split("[")[0]
        sjm = re.match(r'(\d+)-(\d+)(:(\d+))?', sj_range).groups()
        sj_range_start = int(sjm[0])
        sj_range_end = int(sjm[1])
        sj_range_step = int(sjm[3]) if sjm[3] else 1
        sjids = [j.create_subjob_id(jid, sjn) for sjn in
                 range(sj_range_start, sj_range_end+1, sj_range_step or 1)]
        return (jid, array_id, sjids)

    def test_qdel_same_jobid_nx_array_00(self):
        """
        Test that qdel that deletes the array job more than once in the same
        line.
        """
        jid, _, sjids = self.array_job_start(20, 6, 2)
        self.server.expect(JOB, {ATTR_state: "R"}, id=sjids[0])
        self.server.delete([jid] * 10, wait=True)
        self.server.expect(JOB, {'job_state': 'F', 'substate': 91}, id=jid,
                           extend='x', max_attempts=20)

    def test_qdel_same_jobid_nx_array_01(self):
        """
        Test that qdel that deletes the array job more than once in the same
        line.
        """
        jid, _, sjids = self.array_job_start(20, 6, '0-734:512')
        self.server.expect(JOB, {ATTR_state: "R"}, id=sjids[0])
        self.server.delete([jid] * 10, wait=True)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid,
                           extend='x', max_attempts=60)

    def test_qdel_same_jobid_nx_array_subjob_00(self):
        """
        Test that the server handles deleting a running array subjob repeated
        multiple times in the same operation (qdel command).
        """
        jid, _, sjids = self.array_job_start(20, 6, 2)
        for sjid in sjids:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)
        self.server.delete([sjids[0]] * 10, wait=True)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid,
                           extend='x', max_attempts=60)

    def test_qdel_same_jobid_nx_array_subjob_01(self):
        """
        Test that the server handles deleting a running array subjob repeated
        multiple times in the same operation (qdel command) where the array
        specification containes a step.
        """
        jid, _, sjids = self.array_job_start(20, 6, '0-734:512')
        for sjid in sjids:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)
        self.server.delete([sjids[0]] * 10, wait=True)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid,
                           extend='x', max_attempts=60)

    @requirements(num_moms=1)
    def test_qdel_same_jobid_nx_array_subjob_02(self):
        """
        Test that the server handles deleting repeating overlapping ranges of
        running array subjobs in the same operation (qdel command).
        """
        jid, array_id, sjids = self.array_job_start(20, 6, 12)
        for sjid in sjids[:6]:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)

        sj_range1 = f"{array_id}[2-4]"
        sj_range2 = f"{array_id}[3-5]"
        sj_list = [sj_range1, sj_range2] * 10
        self.server.delete(sj_list, wait=True)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=jid, extend='x', max_attempts=20)

    @requirements(num_moms=1)
    def test_qdel_same_jobid_nx_array_subjob_03(self):
        """
        Test that the server handles deleting repeating overlapping ranges of
        running array subjobs in the multiple operations (multiple qdel
        commands backgrounded).
        """
        jid, array_id, sjids = self.array_job_start(20, 6, 12)
        for sjid in sjids[:6]:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)

        sj_range1 = f"{array_id}[2-4]"
        sj_range2 = f"{array_id}[3-5]"
        sj_list = [sj_range1, sj_range2] * 10
        # roughly equivalent to "qdel & qdel & qdel & wait"
        self.server.delete(sj_list, wait=False)
        self.server.delete(sj_list, wait=False)
        self.server.delete(sj_list, wait=True)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=jid, extend='x', max_attempts=20)

    @requirements(num_moms=1)
    def test_qdel_same_jobid_nx_array_subjob_04(self):
        """
        Test that the server handles deleting repeating overlapping ranges of
        array subjobs in a single operation, where a subset are running, but
        none have completed, and some are queued.
        """
        jid, array_id, sjids = self.array_job_start(20, 6, 12)
        for sjid in sjids[:6]:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)

        sj_range1 = f"{array_id}[1-4]"
        sj_range2 = f"{array_id}[3-8]"
        sj_list = [sj_range1, sj_range2] * 10
        self.server.delete(sj_list, wait=True)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=jid, extend='x', max_attempts=20)

    @requirements(num_moms=1)
    def test_qdel_same_jobid_nx_array_subjob_05(self):
        """
        Test that the server handles deleting repeating overlapping ranges of
        array subjobs in a single operation, where some subjobs have completed,
        a subset are running, and some are queued.
        """
        jid, array_id, sjids = self.array_job_start(20, 4, 12)
        for sjid in sjids[:6]:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)
        sj_range1 = f"{array_id}[1-4]"
        sj_range2 = f"{array_id}[3-8]"
        sj_list = [sj_range1, sj_range2] * 10
        self.server.delete(sj_list, wait=True)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=jid, extend='x', max_attempts=20)

    @requirements(num_moms=1)
    def test_qdel_same_jobid_nx_array_subjob_06(self):
        """
        Test that the server handles deleting repeating ranges of
        array subjobs in a single operation, where some subjobs have completed,
        a subset are running, and some are queued.
        """
        jid, array_id, sjids = self.array_job_start(20, 4, 12)
        for sjid in sjids[:6]:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)
        sj_range1 = f"{array_id}[1-4]"
        sj_list = [sj_range1] * 20
        self.server.delete(sj_list, wait=True)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=jid, extend='x', max_attempts=20)

    @requirements(num_moms=1)
    def test_qdel_same_jobid_nx_array_subjob_07(self):
        """
        Test that the server handles deleting repeating ranges of
        array subjobs in a single operation, where some subjobs have completed,
        a subset are running, and some are queued.
        """
        jid, array_id, sjids = self.array_job_start(20, 4, 12)
        for sjid in sjids[:6]:
            self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)
        sj_range1 = f"{array_id}[1-4]"
        sj_range2 = f"{array_id}[3-6]"
        sj_range3 = f"{array_id}[5-8]"

        sj_list = [sj_range1, sj_range2, sj_range3]
        self.server.delete(sj_list, wait=True)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=jid, extend='x', max_attempts=20)

    # TODO: add rerun nx for job arrays

    def test_qdel_with_list_of_jobids(self):
        """
        Test deleting the list of jobids, containing unknown, queued
        and running jobs in the list.
        """

        self.server.manager(
            MGR_CMD_SET, SERVER, {
                'job_history_enable': 'True'})
        fail_msg = f'qdel didn\'t throw unknown job error'
        with self.assertRaises(PbsDeleteError, msg=fail_msg) as c:
            j = Job(TEST_USER)
            j.set_sleep_time(5)
            unknown_jid = "100000"
            jid = self.server.submit(j)
            stripped_jid = jid.split('.')[0]
            self.server.expect(JOB, {'job_state': 'R'}, id=stripped_jid)
            j = Job(TEST_USER)
            j.set_sleep_time(1000)
            running_jid = self.server.submit(j)
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
            j = Job(TEST_USER)
            queued_jid = self.server.submit(j)

            self.server.expect(JOB, {'job_state': 'R'}, id=running_jid)
            self.server.expect(JOB, {'job_state': 'Q'}, id=queued_jid)
            job_set = [unknown_jid, running_jid, queued_jid, stripped_jid]
            self.server.delete(job_set)
        msg = f'qdel: Unknown Job Id {unknown_jid}'
        self.assertTrue(c.exception.msg[0].startswith(msg))
        self.server.expect(JOB, {'job_state': 'F'}, id=stripped_jid,
                           extend='x')
        self.server.expect(JOB, {'job_state': 'F'}, id=running_jid,
                           extend='x')
        self.server.expect(JOB, {'job_state': 'F'}, id=queued_jid,
                           extend='x')

    def test_qdel_with_duplicate_jobids_in_list(self):
        """
        This tests server crash with duplicate jobids
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        jid_list = [jid, jid, jid, jid]
        self.server.delete(jid_list)
        rv = self.server.isUp()
        self.assertTrue(rv, "Server crashed")
        j = Job(TEST_USER)
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)
        jid3 = self.server.submit(j)
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        jid_list = [jid1, jid2, jid1, jid2, jid3, jid4, jid4, jid3]
        self.server.delete(jid_list)
        rv = self.server.isUp()
        self.assertTrue(rv, "Server crashed")

    def test_qdel_with_duplicate_array_jobs(self):
        """
        Test server crash with duplicate array jobs
        """
        j = Job(TEST_USER, {
            ATTR_J: '1-20', 'Resource_List.select': 'ncpus=1'})
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)
        jid3 = self.server.submit(j)
        jid4 = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'B'}, jid1)
        jid_list = [jid1, jid1, jid2, jid1, jid3, jid4, jid3, jid2]
        self.server.delete(jid_list)
        rv = self.server.isUp()
        self.assertTrue(rv, "Server crashed")

    def test_qdel_with_duplicate_array_non_array_jobs(self):
        """
        Test server crash with duplicate array and non-array jobs
        """
        j = Job(TEST_USER, {
            ATTR_J: '1-20', 'Resource_List.select': 'ncpus=1'})
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)

        j = Job(TEST_USER, {'Resource_List.select': 'ncpus=1'})
        jid3 = self.server.submit(j)
        jid4 = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'B'}, jid1)
        jid_list = [jid1, jid1, jid2, jid1, jid3, jid4, jid3, jid2]
        self.server.delete(jid_list)
        rv = self.server.isUp()
        self.assertTrue(rv, "Server crashed")

    def test_qdel_with_overlaping_array_jobs(self):
        """
        Test server crash with overlaping array jobs
        """
        j = Job(TEST_USER, {
            ATTR_J: '1-20', 'Resource_List.select': 'ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        subjob1 = jid.replace('[]', '[1-6]')
        subjob2 = jid.replace('[]', '[5-8]')
        jid_list = [subjob1, subjob2]
        self.server.delete(jid_list)
        rv = self.server.isUp()
        self.assertTrue(rv, "Server crashed")

        subjob3 = jid.replace('[]', '[11-18]')
        subjob4 = jid.replace('[]', '[15-19]')
        jid_list = [subjob3, subjob4]
        self.server.delete(jid_list)
        rv = self.server.isUp()
        self.assertTrue(rv, "Server crashed")

    def test_qdel_mix_of_job_and_arrayjob_range(self):
        """
        Test that the server handles deleting mix of common job
        and array job range in one request
        """
        j = Job(TEST_USER, {'Resource_List.select': 'ncpus=1'})
        jid = self.server.submit(j)

        ajid, array_id, sjids = self.array_job_start(20, 2, 2)

        sj_list = [jid, f"{array_id}[1]", f"{array_id}[2]"]
        self.server.delete(sj_list, wait=True)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=jid, extend='x', max_attempts=20)
        self.server.expect(
            JOB, {'job_state': 'F'}, id=ajid, extend='x', max_attempts=20)

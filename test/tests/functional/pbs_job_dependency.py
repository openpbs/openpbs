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


class TestJobDependency(TestFunctional):

    """
    Test suite to test different job dependencies
    """
    hook_body = """
import pbs
e = pbs.event()
j = e.job
if ('DEPENDENT_JOB' in j.Variable_List):
    j.depend = pbs.depend("runone:" + str(j.Variable_List['DEPENDENT_JOB']))
e.accept()
"""

    def setUp(self):
        TestFunctional.setUp(self)
        attr = {ATTR_RESC_TYPE: 'string', ATTR_RESC_FLAG: 'h'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='NewRes')
        self.scheduler.add_resource('NewRes', apply=True)
        attr = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(attr, 6, attrfunc=self.cust_attr,
                               usenatvnode=False)

    def cust_attr(self, name, totnodes, numnode, attrib):
        res_str = "ver" + str(numnode)
        attr = {'resources_available.NewRes': res_str}
        return {**attrib, **attr}

    def assert_dependency(self, *jobs):
        dl = []
        num = len(jobs)
        for ind, job in enumerate(jobs):
            temp = self.server.status(JOB, id=job)[0][ATTR_depend]
            dl.append([i.split('@')[0] for i in temp.split(':')[1:]])
            self.assertEqual(num - 1, len(dl[ind]))

        for ind, job in enumerate(jobs):
            # make a list of dependency list that does not contain the
            # enumerated job
            check_dl = dl[:ind] + dl[ind + 1:]
            for job_list in check_dl:
                self.assertIn(job, job_list)

    def test_runone_depend_basic(self):
        """
        Test basic runone dependency tests
        1 - Submit a job that runs and then submit a job having "runone"
        dependency on the first job. Check that second job is deleted as
        soon as the first job ends.
        2 - Submit a can never run job and submit a second job having "runone"
        dependency on the first job. Check that first job is deleted when
        second job ends.
        """

        job = Job(attrs={'Resource_List.select': '1:NewRes=ver3'})
        job.set_sleep_time(10)
        j1 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j1})
        j1_2 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'R'}, id=j1)
        self.server.expect(JOB, {'job_state': 'H'}, id=j1_2)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j1_2)

        job = Job(attrs={'Resource_List.select': '1:ncpus=4:NewRes=ver3'})
        job.set_sleep_time(10)
        j2 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j2})
        j2_2 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'H'}, id=j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2_2)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j2)

    def test_runone_dependency_on_running_job(self):
        """
        Submit a job putting runone dependency on an already running job
        check to see that the second job is put on system hold as soon
        as it is submitted, then submit another job dependent on the
        second held job and see if that gets held as well.
        Also test that all jobs have dependency on other two jobs.
        """

        job = Job()
        j1 = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)

        a = {ATTR_depend: 'runone:' + j1}
        job2 = Job(attrs=a)
        j2 = self.server.submit(job2)
        self.server.expect(JOB, {ATTR_state: 'H', ATTR_h: 's'}, id=j2)
        self.assert_dependency(j1, j2)

        a = {ATTR_depend: 'runone:' + j2}
        job3 = Job(attrs=a)
        j3 = self.server.submit(job3)
        self.server.expect(JOB, {ATTR_state: 'H', ATTR_h: 's'}, id=j3)
        self.assert_dependency(j1, j2, j3)

    def test_runone_depend_basic_on_job_array(self):
        """
        Test basic runone dependency tests on job arrays
        1 - Submit a job array that runs and then submit a job having "runone"
        dependency on the parent job array. Check that second job is held as
        soon as it is submitted.
        2 - Submit a can never run array job and submit a second job having
        "runone" dependency on the array parent. Check that first job is
        deleted when second job runs.
        3 - Submit a runone dependency on an array subjob and check if job
        submission fails in this case.
        """

        job = Job(attrs={'Resource_List.select': '1:ncpus=1',
                         ATTR_J: '1-2'})
        job.set_sleep_time(10)
        j1 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j1})
        j1_2 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'B'}, id=j1)
        self.server.expect(JOB, {'job_state': 'H'}, id=j1_2)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j1_2)

        job = Job(attrs={'Resource_List.select': '1:ncpus=4:NewRes=ver3',
                         ATTR_J: '1-2'})
        job.set_sleep_time(10)
        j2 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j2})
        j2_1 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2_1)
        self.server.expect(JOB, {'job_state': 'H'}, id=j2)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j2)

        job = Job(attrs={'Resource_List.select': '1:ncpus=1',
                         ATTR_J: '1-2'})
        job.set_sleep_time(10)
        j3 = self.server.submit(job)
        j3_1 = job.create_subjob_id(j3, 1)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j3_1})
        with self.assertRaises(PbsSubmitError):
            self.server.submit(d_job)

    def test_runone_queuejob_hook(self):
        """
        Check to see that a queue job hook can set runone job
        dependency.
        """
        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook('h1', a, self.hook_body)
        job = Job()
        j1 = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)

        a = {ATTR_v: 'DEPENDENT_JOB=' + j1}
        job2 = Job(attrs=a)
        j2 = self.server.submit(job2)
        self.server.expect(JOB, {ATTR_state: 'H', ATTR_h: 's'}, id=j2)

        self.assert_dependency(j1, j2)

    def test_runone_runjob_hook(self):
        """
        Check to see that a run job hook cannot set runone job
        dependency.
        """
        a = {'event': 'runjob', 'enabled': 'True'}
        self.server.create_import_hook('h1', a, self.hook_body)
        job = Job()
        j1 = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)

        a = {ATTR_v: 'DEPENDENT_JOB=' + j1}
        job2 = Job(attrs=a)
        j2 = self.server.submit(job2)
        logmsg = "cannot modify job after runjob request has been accepted"
        self.server.log_match(logmsg)

    def test_deleting_one_runone_dependency_job(self):
        """
        Submit a job putting runone dependency on an already running job
        check to see that the second job is put on system hold as soon
        as it is submitted, then submit another job dependent on the
        second held job and see if that gets held as well.
        Then test that deleting second job updates dependencies on
        other two jobs.
        """
        job = Job()
        j1 = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)

        a = {ATTR_depend: 'runone:' + j1}
        job2 = Job(attrs=a)
        j2 = self.server.submit(job2)
        self.server.expect(JOB, {ATTR_state: 'H', ATTR_h: 's'}, id=j2)

        a = {ATTR_depend: 'runone:' + j2}
        job3 = Job(attrs=a)
        j3 = self.server.submit(job3)
        self.server.expect(JOB, {ATTR_state: 'H', ATTR_h: 's'}, id=j3)

        self.assert_dependency(j1, j2, j3)

        self.server.delete(j2)
        self.assert_dependency(j1, j3)

    def check_job(self, attr, msg, state):
        """
        helper function to submit a dependent job and check the job
        to see if the dependency is met or rejected
        """
        j = Job(attrs=attr)
        jid = self.server.submit(j)
        msg_to_check = jid + ';' + msg
        self.server.expect(JOB, {ATTR_state: state}, id=jid, extend='x')
        self.server.log_match(msg_to_check)
        if state == 'R':
            self.server.delete(jid)

    def test_dependency_on_finished_job(self):
        """
        Submit a short job and when it ends submit jobs dependent on the
        finished job and check that after, afterok, afterany dependencies
        do not hold the dependent job. Also check that the job is not
        accepted for any other afternotok, before, beforeok, beforenotok
        dependency types.
        """
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = Job()
        job.set_sleep_time(5)
        j1 = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j1, extend='x')
        accept_msg = j1 + " Job has finished, dependency satisfied"
        reject_msg = j1 + " Finished job did not satisfy dependency"

        a = {ATTR_depend: 'after:' + j1}
        self.check_job(a, accept_msg, 'R')

        a = {ATTR_depend: 'afterok:' + j1}
        self.check_job(a, accept_msg, 'R')

        a = {ATTR_depend: 'afterany:' + j1}
        self.check_job(a, accept_msg, 'R')

        a = {ATTR_depend: 'afternotok:' + j1}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'before:' + j1}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'beforeany:' + j1}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'beforeok:' + j1}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'beforenotok:' + j1}
        self.check_job(a, reject_msg, 'F')

    def test_dependency_on_multiple_finished_job(self):
        """
        Submit a short job and and a long job, when the short job ends
        submit dependent jobs on finished job and running job,
        check that after dependecy runs, afterok, afterany dependencies
        hold the dependent job, because there is a running job in the
        system. Also check that the job is not accepted for any other
        afternotok, before, beforeok, beforenotok dependency types.
        """
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = Job()
        job.set_sleep_time(5)
        j1 = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j1, extend='x')
        job = Job()
        job.set_sleep_time(500)
        j2 = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j2)
        accept_msg = j1 + " Job has finished, dependency satisfied"
        reject_msg = j1 + " Finished job did not satisfy dependency"

        a = {ATTR_depend: 'after:' + j1 + ":" + j2}
        self.check_job(a, accept_msg, 'R')

        a = {ATTR_depend: 'afterok:' + j1 + ":" + j2}
        self.check_job(a, accept_msg, 'H')

        a = {ATTR_depend: 'afterany:' + j1 + ":" + j2}
        self.check_job(a, accept_msg, 'H')

        a = {ATTR_depend: 'afternotok:' + j1 + ":" + j2}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'before:' + j1 + ":" + j2}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'beforeany:' + j1 + ":" + j2}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'beforeok:' + j1 + ":" + j2}
        self.check_job(a, reject_msg, 'F')

        a = {ATTR_depend: 'beforenotok:' + j1 + ":" + j2}
        self.check_job(a, reject_msg, 'F')

    def check_depend_delete_msg(self, pjid, cjid):
        """
        helper function to check ia message that the dependent job (cjid)
        is deleted because of the parent job (pjid)
        """
        msg = cjid + ";Job deleted as result of dependency on job " + pjid
        self.server.log_match(msg)

    def test_job_end_deleting_chain_of_dependency(self):
        """
        Submit a chain of dependent jobs and see if one of the running jobs
        ends, all the dependent jobs (and their dependent jobs)
        are also deleted.
        """

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job = Job()
        job.set_sleep_time(10)
        j1 = self.server.submit(job)

        a = {ATTR_depend: "afternotok:" + j1}
        job = Job(attrs=a)
        j2 = self.server.submit(job)

        a = {ATTR_depend: "afterok:" + j2}
        job = Job(attrs=a)
        j3 = self.server.submit(job)

        a = {ATTR_depend: "afterok:" + j1}
        job = Job(attrs=a)
        j4 = self.server.submit(job)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j1, extend='x')
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j2, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j1, j2)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j3, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j2, j3)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j4, max_attempts=3)

    def test_qdel_deleting_chain_of_dependency(self):
        """
        Submit a chain of dependent jobs and see if one of the running jobs
        is deleted, all the jobs without their dependency released
        are also deleted.
        Try the same test with array jobs as well.
        """

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job = Job()
        j1 = self.server.submit(job)

        a = {ATTR_depend: "afterok:" + j1}
        job = Job(attrs=a)
        j2 = self.server.submit(job)

        a = {ATTR_depend: "afternotok:" + j2}
        job = Job(attrs=a)
        j3 = self.server.submit(job)

        a = {ATTR_depend: "after:" + j1}
        job = Job(attrs=a)
        j4 = self.server.submit(job)

        a = {ATTR_depend: "afternotok:" + j1}
        job = Job(attrs=a)
        j5 = self.server.submit(job)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j4)
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j5)
        self.server.delete(j1)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j1, extend='x')
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j2, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j1, j2)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j3, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j2, j3)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j4)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j5)
        self.server.delete(j4)
        self.server.delete(j5)

        # repeat the steps for array job
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job = Job(attrs={ATTR_J: '1-2'})
        j5 = self.server.submit(job)

        a = {ATTR_depend: "afterok:" + j5}
        job = Job(attrs=a)
        j6 = self.server.submit(job)

        a = {ATTR_depend: "afternotok:" + j6}
        job = Job(attrs=a)
        j7 = self.server.submit(job)

        a = {ATTR_depend: "after:" + j5}
        job = Job(attrs=a)
        j8 = self.server.submit(job)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'B'}, id=j5)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j8)
        self.server.delete(j5)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j5, extend='x')
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j6, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j5, j6)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j7, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j6, j7)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j8)

    def test_qdel_held_job_deleting_chain_of_dependency(self):
        """
        Submit a chain of dependent jobs and see if one of the held jobs
        is deleted, all the jobs without their dependency released
        are also deleted.
        """

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job = Job()
        j1 = self.server.submit(job)

        a = {ATTR_depend: "afternotok:" + j1}
        job = Job(attrs=a)
        j2 = self.server.submit(job)

        a = {ATTR_depend: "afterok:" + j2}
        job = Job(attrs=a)
        j3 = self.server.submit(job)

        a = {ATTR_depend: "after:" + j2}
        job = Job(attrs=a)
        j4 = self.server.submit(job)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j2)
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j3)
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j4)
        self.server.delete(j2)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j2, extend='x',
                           max_attempts=3)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j3, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j2, j3)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j4, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j2, j4)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)

    def test_only_after_dependency_chain_is_deleted(self):
        """
        Submit a chain of dependent jobs and see that only downstream jobs
        with after dependencies are deleted.
        """

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job = Job()
        j1 = self.server.submit(job)

        a = {ATTR_depend: "afterok:" + j1}
        job = Job(attrs=a)
        j2 = self.server.submit(job)

        a = {ATTR_depend: "afterok:" + j2}
        job = Job(attrs=a)
        j3 = self.server.submit(job)

        a = {ATTR_depend: "after:" + j3}
        job = Job(attrs=a)
        j4 = self.server.submit(job)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j2)
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j3)
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j4)
        self.server.delete(j3)
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j2)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j3, extend='x',
                           max_attempts=3)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j4, extend='x',
                           max_attempts=3)
        self.check_depend_delete_msg(j3, j4)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1)

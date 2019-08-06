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
        rv = self.scheduler.add_resource('NewRes', apply=True)
        self.assertTrue(rv)
        a = {ATTR_rescavail + '.ncpus': 0}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

    def create_vnodes(self):
        attr = {'resources_available.ncpus': 1}
        self.server.create_vnodes('vnode', attr, 6, mom=self.mom)
        for i in range(6):
            res_str = "ver" + str(i)
            attr = {'resources_available.NewRes': res_str}
            vnode = 'vnode[' + str(i) + ']'
            self.server.manager(MGR_CMD_SET, NODE, attr, vnode)

    def assert_dependency(self, *jobs):
        dl = []
        num = len(jobs)
        for ind, _ in enumerate(jobs):
            temp = self.server.status(JOB, id=jobs[ind])[0][ATTR_depend]
            dl.append([i.split('@')[0] for i in temp.split(':')[1:]])
            self.assertEqual(num-1, len(dl[ind]))

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
        soon as it is submitted.
        2 - Submit a can never run job and submit a second job having "runone"
        dependency on the first job. Check that first job is deleted when
        second job runs.
        """

        self.create_vnodes()
        job = Job(attrs={'Resource_List.select': '1:NewRes=ver3'})
        job.set_sleep_time(2)
        j1 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j1})
        j1_2 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'R'}, id=j1)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j1_2)

        job = Job(attrs={'Resource_List.select': '1:ncpus=4:NewRes=ver3'})
        job.set_sleep_time(2)
        j2 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j2})
        j2_2 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2_2)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j2)

    def test_runone_dependency_on_running_job(self):
        """
        Submit a job putting runone dependency on an already running job
        check to see that the second job is put on system hold as soon
        as it is submitted.
        """
        self.create_vnodes()
        job = Job()
        j1 = self.server.submit(job)
        a = {ATTR_state: 'R'}
        self.server.expect(JOB, a, id=j1)

        a = {ATTR_depend: 'runone:' + j1}
        job2 = Job(attrs=a)
        j2 = self.server.submit(job2)
        a = {ATTR_state: 'H', ATTR_h: 's'}
        self.server.expect(JOB, a, id=j2)

        self.assert_dependency(j1, j2)

    def test_runone_dependency_on_already_held_job(self):
        """
        Submit a job putting runone dependency on an already running job
        check to see that the second job is put on system hold as soon
        as it is submitted, then submit another job dependent on the
        second held job and see if that gets held as well.
        Also test that all jobs have dependency on other two jobs.
        """
        self.create_vnodes()
        job = Job(TEST_USER)
        j1 = self.server.submit(job)
        a = {ATTR_state: 'R'}
        self.server.expect(JOB, a, id=j1)

        a = {ATTR_depend: 'runone:' + j1}
        job2 = Job(TEST_USER, attrs=a)
        j2 = self.server.submit(job2)
        a = {ATTR_state: 'H', ATTR_h: 's'}
        self.server.expect(JOB, a, id=j2)

        a = {ATTR_depend: 'runone:' + j2}
        job3 = Job(TEST_USER, attrs=a)
        j3 = self.server.submit(job3)
        a = {ATTR_state: 'H', ATTR_h: 's'}
        self.server.expect(JOB, a, id=j3)

        self.assert_dependency(j1, j2, j3)

    def test_runone_depend_basic_on_job_array(self):
        """
        Test basic runone dependency tests on job arrays
        1 - Submit a job array that runs and then submit a job having "runone"
        dependency on the parent job array. Check that second job is deleted as
        soon as it is submitted.
        2 - Submit a can never run array job and submit a second job having
        "runone" dependency on the array parent. Check that first job is
        deleted when second job runs.
        3 - Submit a runone dependency on an array subjob and check if job
        submission fails in this case.
        """

        self.create_vnodes()
        job = Job(attrs={'Resource_List.select': '1:ncpus=1',
                         ATTR_J: '1-3'})
        job.set_sleep_time(5)
        j1 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j1})
        j1_2 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'B'}, id=j1)
        self.server.expect(JOB, {'job_state': 'H'}, id=j1_2)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j1_2)

        job = Job(attrs={'Resource_List.select': '1:ncpus=4:NewRes=ver3',
                         ATTR_J: '1-3'})
        job.set_sleep_time(2)
        j2 = self.server.submit(job)
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j2})
        j2_1 = self.server.submit(d_job)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2_1)
        self.server.expect(JOB, {'job_state': 'H'}, id=j2)
        self.server.accounting_match("Job deleted as result of dependency",
                                     id=j2)

        job = Job(attrs={'Resource_List.select': '1:ncpus=1',
                         ATTR_J: '1-3'})
        job.set_sleep_time(2)
        j3 = self.server.submit(job)
        j3_1 = j3.split('[')[0] + '1' + j3.split('[')[1]
        d_job = Job(attrs={'Resource_List.select': '2:ncpus=1',
                           ATTR_depend: 'runone:' + j3_1})
        with self.assertRaises(PbsSubmitError) as e:
            self.server.submit(d_job)

    def test_runone_queuejob_hook(self):
        """
        Check to see that a queue job hook can set runone job
        dependency.
        """
        self.create_vnodes()
        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook('h1', a, self.hook_body)
        job = Job()
        j1 = self.server.submit(job)
        a = {ATTR_state: 'R'}
        self.server.expect(JOB, a, id=j1)

        a = {ATTR_v: 'DEPENDENT_JOB=' + j1}
        job2 = Job(attrs=a)
        j2 = self.server.submit(job2)
        a = {ATTR_state: 'H', ATTR_h: 's'}
        self.server.expect(JOB, a, id=j2)

        self.assert_dependency(j1, j2)

    def test_runone_runjob_hook(self):
        """
        Check to see that a run job hook cannot set runone job
        dependency.
        """
        self.create_vnodes()
        a = {'event': 'runjob', 'enabled': 'True'}
        self.server.create_import_hook('h1', a, self.hook_body)
        job = Job()
        j1 = self.server.submit(job)
        a = {ATTR_state: 'R'}
        self.server.expect(JOB, a, id=j1)

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
        self.create_vnodes()
        job = Job(TEST_USER)
        j1 = self.server.submit(job)
        a = {ATTR_state: 'R'}
        self.server.expect(JOB, a, id=j1)

        a = {ATTR_depend: 'runone:' + j1}
        job2 = Job(TEST_USER, attrs=a)
        j2 = self.server.submit(job2)
        a = {ATTR_state: 'H', ATTR_h: 's'}
        self.server.expect(JOB, a, id=j2)

        a = {ATTR_depend: 'runone:' + j2}
        job3 = Job(TEST_USER, attrs=a)
        j3 = self.server.submit(job3)
        a = {ATTR_state: 'H', ATTR_h: 's'}
        self.server.expect(JOB, a, id=j3)

        self.assert_dependency(j1, j2, j3)

        self.server.delete(j2)
        self.assert_dependency(j1, j3)

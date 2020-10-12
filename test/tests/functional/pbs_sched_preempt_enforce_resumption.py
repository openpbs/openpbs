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


class TestSchedPreemptEnforceResumption(TestFunctional):
    """
    Test sched_preempt_enforce_resumption working
    """

    def setUp(self):
        TestFunctional.setUp(self)

        a = {ATTR_qtype: 'Execution', ATTR_enable: 'True',
             ATTR_start: 'True', ATTR_p: '151'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")

        a = {ATTR_sched_preempt_enforce_resumption: True}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

    def test_filler_job_higher_walltime(self):
        """
        This test confirms that the filler job does not run if it conflicts
        with running of a suspended job.
        """
        a = {ATTR_rescavail + '.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_l + '.walltime': 80})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 30})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_l + '.walltime': 90})
        jid3 = self.server.submit(j3)
        logmsg = ";Job would conflict with reservation or top job"
        self.scheduler.log_match(jid3 + logmsg)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid3)

    def test_suspended_job_ded_time_calendared(self):
        """
        This test confirms that a suspended job becomes top job when unable to
        resume due to conflict with dedicated time.
        """
        a = {ATTR_rescavail + '.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        now = int(time.time())
        temp = 60 - now % 60
        start = now + 180 + temp
        end = start + 120
        self.scheduler.add_dedicated_time(start=start, end=end)

        j1 = Job(TEST_USER)
        jtime = int(time.time())
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_l + '.walltime': start - jtime - 10})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_l + '.walltime': 60,
                           ATTR_q: 'expressq'})
        j2.set_sleep_time(60)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

        self.server.tracejob_match(
            msg='Job is a top job and will run at', id=jid1)

        attr = 'estimated.start_time'
        stat = self.server.status(JOB, attr, id=jid1)
        est_val = stat[0][attr]
        est_str = time.strptime(est_val, '%c')
        est_start_time = int(time.mktime(est_str))

        self.assertGreaterEqual(est_start_time, end)

    def test_filler_job_lesser_walltime(self):
        """
        This test confirms that the filler job does run when the walltime does
        not conflict with running of a suspended job.
        """
        a = {ATTR_rescavail + '.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4',
                           ATTR_l + '.walltime': 50})
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_l + '.walltime': 80})
        jid2 = self.server.submit(j2)

        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_l + '.walltime': 50})
        jid3 = self.server.submit(j3)

        j4 = Job(TEST_USER)
        j4.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_l + '.walltime': 150})
        jid4 = self.server.submit(j4)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid4)

        j5 = Job(TEST_USER)
        j5.set_attributes({ATTR_l + '.select': '1:ncpus=1',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 100})
        jid5 = self.server.submit(j5)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid4)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid5)

        logmsg = ";Job would conflict with reservation or top job"
        self.scheduler.log_match(jid4 + logmsg)

    def test_filler_job_suspend(self):
        """
        This test confirms that the filler gets suspended by a high
        priority job.
        """
        a = {ATTR_rescavail + '.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4',
                           ATTR_l + '.walltime': 30})
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_l + '.walltime': 18})
        jid2 = self.server.submit(j2)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid2)

        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 20})
        jid3 = self.server.submit(j3)

        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)

        j4 = Job(TEST_USER)
        j4.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 5})
        jid4 = self.server.submit(j4)

        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid4)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid4, extend='x',
                           offset=5, interval=2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)

        logmsg = ";Job would conflict with reservation or top job"
        self.scheduler.log_match(jid2 + logmsg)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid3, extend='x',
                           offset=15, interval=2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid2)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid1, extend='x',
                           offset=30, interval=2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

    def test_preempted_job_server_soft_limits(self):
        """
        This test confirms that a preempted job remains suspended if it has
        violated server soft limits
        """
        a = {ATTR_rescavail + '.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        a = {'max_run_res_soft.ncpus': "[u:" + str(TEST_USER1) + "=2]"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        p = '"express_queue, normal_jobs, server_softlimits"'
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        j1 = Job(TEST_USER1)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4',
                           ATTR_l + '.walltime': 50})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 20})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_l + '.walltime': 25})
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid3)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid2, extend='x',
                           offset=30, interval=2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid3, extend='x',
                           offset=30, interval=2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

    def test_preempted_job_queue_soft_limits(self):
        """
        This test confirms that a preempted job remains suspended if it has
        violated queue soft limits
        """
        a = {ATTR_rescavail + '.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        a = {'max_run_res_soft.ncpus': "[u:" + str(TEST_USER1) + "=2]"}
        self.server.manager(MGR_CMD_SET, QUEUE, a, 'workq')

        p = '"express_queue, normal_jobs, queue_softlimits"'
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        j1 = Job(TEST_USER1)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4',
                           ATTR_l + '.walltime': 50})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 20})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_l + '.walltime': 25})
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid3)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid2, extend='x',
                           offset=30, interval=2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid3, extend='x',
                           offset=30, interval=2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

    def test_filler_jobs_with_no_walltime(self):
        """
        This test confirms that filler jobs with no walltime remain queued
        """
        a = {ATTR_rescavail + '.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        j1 = Job(TEST_USER1)
        j1.set_attributes({ATTR_l + '.select': '1:ncpus=4',
                           ATTR_l + '.walltime': 20})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:ncpus=2',
                           ATTR_q: 'expressq',
                           ATTR_l + '.walltime': 8})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        j3 = Job(TEST_USER)
        j3.set_attributes({ATTR_l + '.select': '1:ncpus=2'})
        jid3 = self.server.submit(j3)

        j4 = Job(TEST_USER)
        j4.set_attributes({ATTR_l + '.select': '1:ncpus=2'})
        jid4 = self.server.submit(j4)

        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid4)

    def test_filler_stf(self):
        """
        Test that confirms filler shrink to fit jobs will shrink correctly
        """
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        a = {ATTR_l + '.select': '1:ncpus=3',
             ATTR_l + '.walltime': 50}
        jid1 = self.server.submit(Job(attrs=a))
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        a = {ATTR_l + '.select': '1:ncpus=1',
             ATTR_l + '.walltime': 115,
             ATTR_q: 'expressq'}
        jid2 = self.server.submit(Job(attrs=a))
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

        a = {ATTR_l + '.select': '1:ncpus=1',
             ATTR_l + '.min_walltime': 70,
             ATTR_l + '.max_walltime': 90}
        jid3 = self.server.submit(Job(attrs=a))
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)
        self.scheduler.log_match('Job;%s;Job will run for duration=00:01:' %
                                 (jid3))

        a = {ATTR_l + '.select': '1:ncpus=1',
             ATTR_l + '.min_walltime': '01:00',
             ATTR_l + '.max_walltime': '10:00'}
        jid4 = self.server.submit(Job(attrs=a))
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid4)
        self.scheduler.log_match('Job;%s;Job will run for duration=00:01:' %
                                 (jid4))

        a = {ATTR_l + '.select': '1:ncpus=1',
             ATTR_l + '.min_walltime': '02:30',
             ATTR_l + '.max_walltime': '05:00'}
        jid5 = self.server.submit(Job(attrs=a))
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid5)

        stat = self.server.status(JOB, id=jid1)[0]
        j1start = datetime.datetime.strptime(stat['estimated.start_time'],
                                             '%c')

        stat = self.server.status(JOB, id=jid3)[0]
        t = datetime.datetime.strptime(stat[ATTR_l + '.walltime'], '%H:%M:%S')
        j3dur = datetime.timedelta(hours=t.hour,
                                   minutes=t.minute,
                                   seconds=t.second)
        j3start = datetime.datetime.strptime(stat[ATTR_stime], '%c')
        self.assertGreaterEqual(j1start, j3start + j3dur)
        self.assertGreaterEqual(j3dur.total_seconds(), 70)
        self.assertLessEqual(j3dur.total_seconds(), 90)

        stat = self.server.status(JOB, id=jid4)[0]
        t = datetime.datetime.strptime(stat[ATTR_l + '.walltime'], '%H:%M:%S')
        j4dur = datetime.timedelta(hours=t.hour,
                                   minutes=t.minute,
                                   seconds=t.second)
        j4start = datetime.datetime.strptime(stat[ATTR_stime], '%c')
        self.assertEquals(j4start + j4dur, j1start)

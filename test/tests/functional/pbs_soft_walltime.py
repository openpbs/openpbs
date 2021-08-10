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


def cvt_duration(duration):
    """
    convert string form of a duration (HH:MM:SS) into seconds
    """
    h = 0
    m = 0
    sp = duration.split(':')
    if len(sp) == 3:
        h = int(sp[0])
        m = int(sp[1])
        s = int(sp[2])
    elif len(sp) == 2:
        m = int(sp[0])
        s = int(sp[1])
    else:
        s = int(sp[0])

    return h * 3600 + m * 60 + s


class TestSoftWalltime(TestFunctional):

    """
    Test that the soft_walltime resource is being used properly and
    being extended properly when exceeded
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.server.manager(
            MGR_CMD_UNSET, SERVER, 'Resources_default.soft_walltime')
        # Delete operators if added
        self.server.manager(MGR_CMD_UNSET, SERVER, 'operators')

    def tearDown(self):
        if self.mom.is_cpuset_mom():
            # reset the freq value
            attrs = {'freq': 120}
            self.server.manager(MGR_CMD_SET, HOOK, attrs, "pbs_cgroups")
        TestFunctional.tearDown(self)

    def stat_job(self, job):
        """
        stat a job for its estimated.start_time and soft_walltime or walltime
        :param job: Job to stat
        :type job: string
        """
        a = ['estimated.start_time', 'Resource_List.soft_walltime',
             'Resource_List.walltime']
        # If we're in CLI mode, qstat returns times in a human readable format
        # We need to turn it back into an epoch.  API mode will be the epoch.
        Jstat = self.server.status(JOB, id=job, attrib=a)
        wt = 0
        if self.server.get_op_mode() == PTL_CLI:
            strp = time.strptime(Jstat[0]['estimated.start_time'], '%c')
            est = int(time.mktime(strp))
            if 'Resource_List.soft_walltime' in Jstat[0]:
                wt = cvt_duration(Jstat[0]['Resource_List.soft_walltime'])
            elif 'Resource_List.walltime' in Jstat[0]:
                wt = cvt_duration(Jstat[0]['Resource_List.walltime'])
        else:
            est = int(Jstat[0]['estimated.start_time'])
            if 'Resource_List.soft_walltime' in Jstat[0]:
                wt = int(Jstat[0]['Resource_List.soft_walltime'])
            elif 'Resource_List.walltime' in RN_stat[0]:
                wt = int(Jstat[0]['Resource_List.walltime'])

        return (est, wt)

    def compare_estimates(self, baseline_job, jobs):
        """
        Check if estimated start times are correct
        :param baseline_job: initial top job to base times off of
        :type baseline_job: string (job id)
        :param jobs: calendared jobs
        :type jobs: list of strings (job ids)
        """
        est, wt = self.stat_job(baseline_job)
        for j in jobs:
            est2, wt2 = self.stat_job(j)
            self.assertEqual(est + wt, est2)
            est = est2
            wt = wt2

    def setup_holidays(self, prime_offset, nonprime_offset):
        """
        Set up the holidays file for test execution.  This function will
        first remove all entries in the holidays file and then add a year,
        prime, and nonprime for all days.  The prime and nonprime entries
        will be offsets from the current time.

        This all is necessary because there are some holidays set by default.
        The test should be able to be run on any day of the year.  If it is
        run on one of these holidays, it will be nonprime time only.
        """
        # Delete all entries in the holidays file
        self.scheduler.holidays_delete_entry('a')

        lt = time.localtime(time.time())
        self.scheduler.holidays_set_year(str(lt[0]))

        now = int(time.time())
        prime = time.strftime('%H%M', time.localtime(now + prime_offset))
        nonprime = time.strftime('%H%M', time.localtime(now + nonprime_offset))

        # set prime-time and nonprime-time for all days
        self.scheduler.holidays_set_day('weekday', prime, nonprime)
        self.scheduler.holidays_set_day('saturday', prime, nonprime)
        self.scheduler.holidays_set_day('sunday', prime, nonprime)

    def test_soft_walltime_perms(self):
        """
        Test to see if soft_walltime can't be submitted with a job or
        altered by a normal user or operator
        """
        J = Job(TEST_USER, attrs={'Resource_List.soft_walltime': 10})
        msg = 'Cannot set attribute, read only or insufficient permission'

        jid = None
        try:
            jid = self.server.submit(J)
        except PbsSubmitError as e:
            self.assertTrue(msg in e.msg[0])

        self.assertEqual(jid, None)

        J = Job(TEST_USER)
        jid = self.server.submit(J)
        try:
            self.server.alterjob(jid, {'Resource_List.soft_walltime': 10},
                                 runas=TEST_USER)
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        self.server.expect(JOB, 'Resource_List.soft_walltime',
                           op=UNSET, id=jid)

        operator = str(OPER_USER) + '@*'
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'operators': (INCR, operator)},
                            sudo=True)

        try:
            self.server.alterjob(jid, {'Resource_List.soft_walltime': 10},
                                 runas=OPER_USER)
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        self.server.expect(JOB, 'Resource_List.soft_walltime',
                           op=UNSET, id=jid)

    def test_soft_walltime_STF(self):
        """
        Test that STF jobs can't have soft_walltime
        """
        msg = 'soft_walltime is not supported with Shrink to Fit jobs'
        J = Job(attrs={'Resource_List.min_walltime': 120, ATTR_h: None})
        jid = self.server.submit(J)
        try:
            self.server.alterjob(jid, {'Resource_List.soft_walltime': 10})
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        self.server.expect(JOB, 'Resource_List.soft_walltime',
                           op=UNSET, id=jid)

        J = Job(TEST_USER, attrs={ATTR_h: None})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 10})
        try:
            self.server.alterjob(jid, {'Resource_List.min_walltime': 120})
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        self.server.expect(JOB, 'Resource_List.min_walltime',
                           op=UNSET, id=jid)

        J = Job(TEST_USER, attrs={ATTR_h: None})
        jid = self.server.submit(J)
        a = {'Resource_List.soft_walltime': 10,
             'Resource_List.min_walltime': 120}
        try:
            self.server.alterjob(jid, a)
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        al = ['Resource_List.min_walltime', 'Resource_List.soft_walltime']
        self.server.expect(JOB, al, op=UNSET, id=jid)

    def test_soft_greater_hard(self):
        """
        Test that a job's soft_walltime can't be greater than its hard walltime
        """
        msg = 'Illegal attribute or resource value'
        J = Job(TEST_USER, attrs={'Resource_List.walltime': 120, ATTR_h: None})
        jid = self.server.submit(J)

        try:
            self.server.alterjob(jid, {'Resource_List.soft_walltime': 240})
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        self.server.expect(JOB, 'Resource_List.soft_walltime',
                           op=UNSET, id=jid)

        J = Job(TEST_USER, {ATTR_h: None})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 240})
        try:
            self.server.alterjob(jid, {'Resource_List.walltime': 120})
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        self.server.expect(JOB, 'Resource_List.walltime', op=UNSET, id=jid)

        J = Job(TEST_USER, {ATTR_h: None})
        jid = self.server.submit(J)
        try:
            self.server.alterjob(jid, {'Resource_List.walltime': 120,
                                       'Resource_List.soft_walltime': 240})
        except PbsAlterError as e:
            self.assertTrue(msg in e.msg[0])

        al = ['Resource_List.walltime', 'Resource_List.soft_walltime']
        self.server.expect(JOB, al, op=UNSET, id=jid)

    def test_direct_set_soft_walltime(self):
        """
        Test setting soft_walltime directly
        """
        hook_body = \
            """import pbs
e = pbs.event()
j = e.job
j.Resource_List["soft_walltime"] = \
pbs.duration(j.Resource_List["set_soft_walltime"])
e.accept()
"""
        self.server.manager(MGR_CMD_CREATE, RSC, {'type': 'long'},
                            id='set_soft_walltime')

        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook("que", a, hook_body)

        J = Job(TEST_USER, attrs={'Resource_List.set_soft_walltime': 5})
        jid = self.server.submit(J)

        self.server.expect(JOB, {'Resource_List.soft_walltime': 5}, id=jid)

    def test_soft_walltime_extend(self):
        """
        Test to see that soft_walltime is extended properly
        """
        J = Job(TEST_USER)
        jid = self.server.submit(J)

        self.server.alterjob(jid, {'Resource_List.soft_walltime': 6})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        time.sleep(7)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime': 6}, op=GT, id=jid)

        # Get the current soft_walltime
        jstat = self.server.status(JOB, id=jid,
                                   attrib=['estimated.soft_walltime'])
        est_soft_walltime = jstat[0]['estimated.soft_walltime']

        time.sleep(7)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        # Check if soft_walltime extended
        self.server.expect(JOB, {'estimated.soft_walltime':
                                 est_soft_walltime}, op=GT, id=jid)

    def test_soft_walltime_extend_hook(self):
        """
        Test to see that soft_walltime is extended properly when submitted
        through a queue job hook
        """
        hook_body = \
            """import pbs
e = pbs.event()
e.job.Resource_List["soft_walltime"] = pbs.duration(5)
e.accept()
"""
        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook("que", a, hook_body)

        J = Job(TEST_USER)
        jid = self.server.submit(J)

        self.server.expect(JOB, {'Resource_List.soft_walltime': 5}, id=jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        time.sleep(6)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime': 5}, op=GT, id=jid)

        # Get the current soft_walltime
        jstat = self.server.status(JOB, id=jid,
                                   attrib=['estimated.soft_walltime'])
        est_soft_walltime = jstat[0]['estimated.soft_walltime']

        time.sleep(6)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime':
                                 est_soft_walltime}, op=GT, id=jid)

    def test_soft_then_hard(self):
        """
        Test to see if a job has both a soft and a hard walltime, that
        the job's soft_walltime is not extended past its hard walltime.
        It should first extend once and then extend to its hard walltime
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

        J = Job(TEST_USER,
                attrs={'Resource_List.ncpus': 1, 'Resource_List.walltime': 16})
        jid = self.server.submit(J)

        self.server.alterjob(jid, {'Resource_List.soft_walltime': 6})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        time.sleep(7)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime': 6}, op=GT, id=jid)

        time.sleep(7)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime': 16},
                           offset=4, extend='x', id=jid)

        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

    def test_soft_before_dedicated(self):
        """
        Make sure that if a job's soft_walltime won't complete before
        dedicated time, the job does not start
        """

        now = int(time.time())
        self.scheduler.add_dedicated_time(start=now + 120, end=now + 2500)

        J = Job(TEST_USER)
        J.set_sleep_time(200)
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 180})
        comment = 'Not Running: Job would cross dedicated time boundary'
        self.server.expect(JOB, {'comment': comment}, id=jid)

    def test_soft_extend_dedicated(self):
        """
        Have a job with a soft_walltime extend into dedicated time and see
        the job continue running like normal
        """

        # Dedicated time is in the granularity of minutes.  This can't be set
        # any shorter without making it dedicated time right now.
        now = int(time.time())
        self.scheduler.add_dedicated_time(start=now + 70, end=now + 180)
        J = Job(TEST_USER, {'Resource_List.walltime': 180})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 5})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info("Waiting until dedicated time starts")
        time.sleep(61)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime': 65},
                           op=GE, id=jid)

    def test_soft_before_prime(self):
        """
        Make sure that if a job's soft_walltime won't complete before
        prime boundry, the job does not start
        """
        self.scheduler.set_sched_config({'backfill_prime': 'True'})

        self.setup_holidays(3600, 7200)

        J = Job(TEST_USER)
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 5400})
        comment = 'Not Running: Job will cross into primetime'
        self.server.expect(JOB, {'comment': comment}, id=jid)

    def test_soft_backfill_prime(self):
        """
        Test if soft_walltime is used to see if a job can run before
        the next prime boundry
        """
        self.scheduler.set_sched_config({'backfill_prime': 'True'})

        self.setup_holidays(60, 3600)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 5})

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        self.logger.info("Waiting until prime time starts.")
        time.sleep(61)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'estimated.soft_walltime': 65}, op=GE,
                           id=jid)

    def test_resv_conf_soft(self):
        """
        Test that there is no change in the reservation behavior with
        soft_walltime set on jobs with no hard walltime set
        """

        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        J = Job(TEST_USER, attrs={'Resource_List.ncpus': 4})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 5})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        now = time.time()
        a = {'Resource_List.ncpus': 1, 'reserve_start': now + 10,
             'reserve_end': now + 130}
        R = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(R)
        self.server.log_match(rid + ';reservation deleted', max_attempts=5)

    def test_resv_conf_soft_with_hard(self):
        """
        Test that there is no change in the reservation behavior with
        soft_walltime set on jobs with a hard walltime set.  The soft_walltime
        should be ignored and only the hard walltime should be used.
        """

        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        now = int(time.time())
        J = Job(TEST_USER, attrs={'Resource_List.ncpus': 4,
                                  'Resource_List.walltime': 120})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 5})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        a = {'Resource_List.ncpus': 1, 'reserve_start': now + 60,
             'reserve_end': now + 250}
        R = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(R)
        self.server.log_match(rid + ';reservation deleted', max_attempts=5)

    def test_resv_job_soft(self):
        """
        Test to see that a job with a soft walltime which would "end" before
        a reservation starts does not start.  It would interfere with the
        reservation.
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        now = int(time.time())

        a = {'Resource_List.ncpus': 4, 'reserve_start': now + 120,
             'reserve_end': now + 240}
        R = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(R)
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')},
                           id=rid)

        a = {'Resource_List.ncpus': 4, ATTR_h: None}
        J = Job(TEST_USER, attrs=a)
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 60})
        self.server.rlsjob(jid, 'u')
        a = {ATTR_state: 'Q', ATTR_comment:
             'Not Running: Job would conflict with reservation or top job'}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_resv_job_soft_hard(self):
        """
        Test to see that a job with a soft walltime and a hard walltime does
        not interfere with a confirmed reservation.  The soft walltime would
        have the job "end" before the reservation starts, but the hard
        walltime would not.
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        now = int(time.time())

        a = {'Resource_List.ncpus': 4, 'reserve_start': now + 120,
             'reserve_end': now + 240}
        R = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(R)
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')},
                           id=rid)

        a = {'Resource_List.ncpus': 4,
             'Resource_List.walltime': 150, ATTR_h: None}
        J = Job(TEST_USER, attrs=a)
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 60})
        self.server.rlsjob(jid, 'u')
        a = {ATTR_state: 'Q', ATTR_comment:
             'Not Running: Job would conflict with reservation or top job'}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_topjob(self):
        """
        Test that soft_walltime is used for calendaring of topjobs
        Submit 3 jobs:
        Job1 has a soft_walltime=150 and runs now
        Job2 has a soft_walltime=150 and gets added to the calendar at now+150
        Job3 has a soft_walltime=150 and gets added to the calendar at now+300
        Job4 has a soft_walltime=150 and gets added to the calendar at now+450
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_backfill_depth: 3})

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid1 = self.server.submit(J)
        self.server.alterjob(jid1, {'Resource_List.soft_walltime': 150})

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid2 = self.server.submit(J)
        self.server.alterjob(jid2, {'Resource_List.soft_walltime': 150})

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid3 = self.server.submit(J)
        self.server.alterjob(jid3, {'Resource_List.soft_walltime': 150})

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid4 = self.server.submit(J)
        self.server.alterjob(jid4, {'Resource_List.soft_walltime': 150})

        now = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.scheduler.log_match('Leaving Scheduling Cycle', starttime=now,
                                 max_attempts=20)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.compare_estimates(jid2, [jid3, jid4])

    def test_topjob2(self):
        """
        Test a mixture of soft_walltime and walltime used in the calendar
        Submit 3 jobs:
        Job1 has a soft_walltime=150 runs now
        Job2 has a soft_walltime=150 and gets added to the calendar at now+150
        Job3 has a soft_walltime=150 and gets added to the calendar at now+300
        Job4 has a walltime=300 and gets added to the calendar at now+450
        Job5 gets added to the calendar at now+750
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_backfill_depth: 4})

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid1 = self.server.submit(J)
        self.server.alterjob(jid1, {'Resource_List.soft_walltime': 150})

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid2 = self.server.submit(J)
        self.server.alterjob(jid2, {'Resource_List.soft_walltime': 150})

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid3 = self.server.submit(J)
        self.server.alterjob(jid3, {'Resource_List.soft_walltime': 150})

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid4 = self.server.submit(J)

        J = Job(TEST_USER, {'Resource_List.walltime': 300})
        jid5 = self.server.submit(J)

        now = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.scheduler.log_match('Leaving Scheduling Cycle', starttime=now)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.compare_estimates(jid2, [jid3, jid4, jid5])

    def test_filler_job(self):
        """
        Test to see if filler jobs will run based on their soft_walltime
        Submit 3 jobs:
        Job1 requests 1cpu and runs now
        Job2 requests 2cpus gets added to the calendar at now+300
        Job3 requests 1cpu and has a soft_walltime=150 and walltime=450
        Job3 should run because its soft_walltime will finish before now+300
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        J1 = Job(TEST_USER, {'Resource_List.walltime': 300,
                             'Resource_List.ncpus': 1})
        jid1 = self.server.submit(J1)

        J2 = Job(TEST_USER, {'Resource_List.walltime': 300,
                             'Resource_List.ncpus': 2})
        jid2 = self.server.submit(J2)

        J3 = Job(TEST_USER, {'Resource_List.walltime': 450,
                             'Resource_List.ncpus': 1})
        jid3 = self.server.submit(J3)
        self.server.alterjob(jid3, {'Resource_List.soft_walltime': 150})

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)

    def test_preempt_order(self):
        """
        Test if soft_walltime is used for preempt_order.  It should be used
        to calculate percent done and also if the soft_walltime is exceeded,
        the percent done should remain at 100%
        """
        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': "R 10 S"},
                            runas=ROOT_USER)
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        a = {'queue_type': 'Execution', 'enabled': 'True',
             'started': 'True', 'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='expressq')

        a = {'Resource_List.walltime': 600}
        J1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J1)
        a = {'Resource_List.soft_walltime': 45}
        self.server.alterjob(jid1, a)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # test preempt_order with percentage < 90.  jid1 should be requeued.
        express_a = {'Resource_List.ncpus': 2, ATTR_queue: 'expressq'}
        J2 = Job(TEST_USER, attrs=express_a)
        jid2 = self.server.submit(J2)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid1)

        self.server.deljob(jid2, wait=True)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # preempt_order percentage done is based on resources_used.walltime
        # this is only periodically updated.  Sleep until half way through
        # the extended soft_walltime to make sure we're over 100%
        self.logger.info("Sleeping 60 seconds to accumulate "
                         "resources_used.walltime")
        time.sleep(60)

        J3 = Job(TEST_USER, attrs=express_a)
        jid3 = self.server.submit(J3)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

    def test_soft_values_default(self):
        """
        Test to verify that soft_walltime will only take integer/long type
        value
        """

        msg = 'Illegal attribute or resource value'
        try:
            self.server.manager(
                MGR_CMD_SET, SERVER, {'resources_default.soft_walltime': '0'})
        except PbsManagerError as e:
            self.assertTrue(msg in e.msg[0])

        try:
            self.server.manager(
                MGR_CMD_SET, SERVER,
                {'resources_default.soft_walltime': '00:00:00'})
        except PbsManagerError as e:
            self.assertTrue(msg in e.msg[0])

        try:
            self.server.manager(
                MGR_CMD_SET, SERVER,
                {'resources_default.soft_walltime': 'abc'})
        except PbsManagerError as e:
            self.assertTrue(msg in e.msg[0])

        try:
            self.server.manager(
                MGR_CMD_SET, SERVER,
                {'resources_default.soft_walltime': '01:20:aa'})
        except PbsManagerError as e:
            self.assertTrue(msg in e.msg[0])

        try:
            self.server.manager(MGR_CMD_SET, SERVER, {
                                'resources_default.soft_walltime':
                                '1000000000000000000000000'})
        except PbsManagerError as e:
            self.assertTrue(msg in e.msg[0])

        try:
            self.server.manager(
                MGR_CMD_SET, SERVER,
                {'resources_default.soft_walltime': '-1'})
        except PbsManagerError as e:
            self.assertTrue(msg in e.msg[0])

        try:
            self.server.manager(
                MGR_CMD_SET, SERVER,
                {'resources_default.soft_walltime': '00.10'})
        except PbsManagerError as e:
            self.assertTrue(msg in e.msg[0])

        self.server.manager(
            MGR_CMD_SET, SERVER,
            {'resources_default.soft_walltime': '00:01:00'})

    def test_soft_runjob_hook(self):
        """
        Test that soft walltime is set by runjob hook
        """

        hook_body = \
            """import pbs
e = pbs.event()
e.job.Resource_List["soft_walltime"] = pbs.duration(5)
e.accept()
"""
        a = {'event': 'runjob', 'enabled': 'True'}
        self.server.create_import_hook("que", a, hook_body)

        J = Job(TEST_USER)
        jid = self.server.submit(J)

        self.server.expect(JOB, {'Resource_List.soft_walltime': 5}, id=jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_soft_modifyjob_hook(self):
        """
        Test that soft walltime is set by modifyjob hook
        """

        hook_body = \
            """import pbs
e = pbs.event()
e.job.Resource_List["soft_walltime"] = pbs.duration(15)
e.accept()
"""
        a = {'event': 'modifyjob', 'enabled': 'True'}
        self.server.create_import_hook("que", a, hook_body)

        J = Job(TEST_USER)
        jid = self.server.submit(J)

        self.server.expect(
            JOB, 'Resource_List.soft_walltime', op=UNSET, id=jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.alterjob(jid, {'Resource_List.soft_walltime': 5})
        self.server.expect(JOB, {'Resource_List.soft_walltime': 15}, id=jid)

    def test_walltime_default(self):
        """
        Test soft walltime behavior with hard walltime is same
        even if set under resource_default
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'resources_default.soft_walltime': '15'})

        J = Job(TEST_USER, attrs={'Resource_List.walltime': 15})
        jid = self.server.submit(J)
        self.server.expect(JOB, {'Resource_List.soft_walltime': 15}, id=jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.deljob(jid, wait=True)

        J = Job(TEST_USER, attrs={'Resource_List.walltime': 16})
        jid1 = self.server.submit(J)
        self.server.expect(JOB, {'Resource_List.soft_walltime': 15}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.deljob(jid1, wait=True)

        # following piece is commented due to PP-1058
        # try:
        #    J = Job(TEST_USER, attrs={'Resource_List.walltime': 10})
        #    jid1 = self.server.submit(J)
        # except PtlSubmitError as e:
        #    self.assertTrue("illegal attribute or resource value" in e.msg[0])
        # self.assertEqual(jid1, None)

    def test_soft_held(self):
        """
        Test that if job is held soft_walltime will not get extended
        """
        J = Job(TEST_USER, attrs={'Resource_List.walltime': '100'})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 7})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info(
            "Sleep to let soft_walltime get extended")
        time.sleep(10)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime': 7}, op=GT,
                           id=jid)

        # Save the soft_walltime before holding the job
        jstat = self.server.status(JOB, id=jid,
                                   attrib=['estimated.soft_walltime'])
        est_soft_walltime = jstat[0]['estimated.soft_walltime']

        self.server.holdjob(jid, 'u')
        self.server.rerunjob(jid)
        self.server.expect(JOB, {'job_state': 'H'}, id=jid)

        self.logger.info(
            "Sleep to verify that soft_walltime: %s"
            " doesn't change while job is held" % est_soft_walltime)
        time.sleep(10)
        self.server.expect(JOB, {'estimated.soft_walltime':
                                 est_soft_walltime}, id=jid)

        # release the job and look for the soft_walltime again
        self.server.rlsjob(jid, 'u')
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'R', 'estimated.soft_walltime':
                                 est_soft_walltime}, attrop=PTL_AND, id=jid)

        # Wait for some more time and verify that soft_walltime
        # extending again
        self.logger.info(
            "Sleep enough to let soft_walltime get extended again"
            " since the walltime was reset to 0")
        time.sleep(17)
        self.server.expect(JOB, {'estimated.soft_walltime': est_soft_walltime},
                           op=GT, id=jid)

    def test_soft_less_cput(self):
        """
        Test that soft_walltime has no impact on cput enforcement limit
        """

        script = """
i=0
while [ 1 ]
do
    sleep 0.125;
    dd if=/dev/zero of=/dev/null;
done
"""
        # If it is a cpuset mom, the cgroups hook relies on the periodic hook
        # to update cput, so make the periodic hook run more often for the
        # purpose of this test.
        if self.mom.is_cpuset_mom():
            attrs = {'freq': 1}
            self.server.manager(MGR_CMD_SET, HOOK, attrs, "pbs_cgroups")
            # cause the change to take effect now
            self.mom.restart()

        j1 = Job(TEST_USER, {'Resource_List.cput': 5})
        j1.create_script(body=script)
        jid = self.server.submit(j1)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 300})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info("Sleep 10 secs waiting for cput to cause the"
                         " job to be deleted")
        time.sleep(10)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

    def test_soft_walltime_resv(self):
        """
        Submit a job with soft walltime inside a reservation
        """

        now = int(time.time())

        a = {'Resource_List.ncpus': 1, 'reserve_start': now + 10,
             'reserve_end': now + 20}
        R = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(R)
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')},
                           id=rid)
        r1 = rid.split('.')[0]

        j1 = Job(TEST_USER, attrs={ATTR_queue: r1})
        jid = self.server.submit(j1)

        # Set soft walltime to greater than reservation end time
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 300})
        self.server.expect(JOB, {'Resource_List.soft_walltime': 300}, id=jid)

        # verify that the job gets deleted when reservation ends
        self.server.expect(
            JOB, 'queue', op=UNSET, id=jid, offset=20)

    def test_restart_server(self):
        """
        Test that on server restart soft walltime is not reset
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

        hook_body = \
            """import pbs
e = pbs.event()
e.job.Resource_List["soft_walltime"] = pbs.duration(8)
e.accept()
"""
        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook("que", a, hook_body)

        J = Job(TEST_USER)
        jid = self.server.submit(J)

        self.server.expect(JOB, {'Resource_List.soft_walltime': 8}, id=jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info("Wait till the soft_walltime is extended once")
        time.sleep(9)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'estimated.soft_walltime': 8}, op=GT,
                           id=jid)

        self.server.restart()

        self.server.expect(JOB, {'Resource_List.soft_walltime': 8}, id=jid)
        self.server.expect(JOB, {'estimated.soft_walltime': 8}, op=GT,
                           id=jid)

        # Get the current soft_walltime
        jstat = self.server.status(JOB, id=jid,
                                   attrib=['estimated.soft_walltime'])
        est_soft_walltime = jstat[0]['estimated.soft_walltime']

        # Delete the job and verify that estimated.soft_walltime is set
        # for job history
        self.server.deljob(jid, wait=True)
        self.server.expect(JOB,
                           {'job_state': 'F',
                            'estimated.soft_walltime':
                            est_soft_walltime}, op=GE,
                           extend='x', attrop=PTL_AND, id=jid)

    def test_soft_job_array(self):
        """
        Test that soft walltime works similar way with subjobs as
        regular jobs
        """

        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        J = Job(TEST_USER, attrs={ATTR_J: '1-5',
                                  'Resource_List.walltime': 15})
        jid = self.server.submit(J)
        self.server.alterjob(jid, {'Resource_List.soft_walltime': 5})

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(
            JOB, {'job_state': 'B', 'Resource_List.soft_walltime': 5}, id=jid)
        subjob1 = jid.replace('[]', '[1]')
        self.server.expect(
            JOB, {'job_state': 'R', 'Resource_List.soft_walltime': 5},
            id=subjob1)

        self.logger.info("Wait for 6s and make sure that subjob1 is not"
                         "deleted even past soft_walltime")
        time.sleep(6)
        self.server.expect(JOB, {'job_state': 'R'}, id=subjob1)

        # Make sure the subjob1 is deleted after 15s past walltime limit
        self.server.expect(JOB, {'job_state': 'X'}, id=subjob1,
                           offset=9)

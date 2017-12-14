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


class TestSTF(TestFunctional):

    """
    The goal for this test suite is to contain basic STF tests that use
    the following timed events that cause the STF job to shrink its walltime:

    - dedicated time

    - primetime (with backfill_prime)

    - reservations
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

    def set_primetime(self, ptime_start, ptime_end):
        """
        Set primttime to start at ptime_start and end at ptime_end.
        Remove all default holidays because will cause a test to fail on
        a holiday
        """
        # Delete all entries in the holidays file
        self.scheduler.holidays_delete_entry('a')

        # Without the YEAR entry primetime is considered to be 24 hours.
        p_yy = time.strftime('%Y', time.localtime(ptime_start))
        self.scheduler.holidays_set_year(p_yy)

        p_day = 'weekday'
        p_hhmm = time.strftime('%H%M', time.localtime(ptime_start))
        np_hhmm = time.strftime('%H%M', time.localtime(ptime_end))
        self.scheduler.holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'saturday'
        self.scheduler.holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'sunday'
        self.scheduler.holidays_set_day(p_day, p_hhmm, np_hhmm)

    def submit_resv(self, resv_start, ncpus, resv_dur):
        """
        Submit a reservation and expect it to be confirmed
        """
        a = {'Resource_List.select': '1:ncpus=%d' % ncpus,
             'Resource_List.place': 'free',
             'reserve_start': int(resv_start),
             'reserve_duration': int(resv_dur)
             }
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

    def submit_jq(self, ncpus):
        """
        Submit a job and expect it to stay queued
        """
        a = {'Resource_List.select': '1:ncpus=%d' % ncpus,
             'Resource_List.place': 'free',
             'Resource_List.walltime': '01:00:00'
             }
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, ATTR_comment, op=SET)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)

    def test_t_4_1_3(self):
        """
        Test shrink to fit by setting a dedicated time that started 20 minutes
        ago with a duration of 2 hours.  Submit a job that can run for as
        short as 1 minute and as long as 20 hours.  Submit a second job to the
        dedicated time queue.  Expect the first job to be in Q state and the
        second job in R state with a walltime that's less than or equal to
        1 hr 40 mins and greater than or equal to 1 min.
        """
        qname = 'ded_time'

        a = {'queue_type': 'execution', 'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)
        now = int(time.time())
        self.scheduler.add_dedicated_time(start=now - 1200, end=now + 6000)

        j = Job(TEST_USER)
        a = {'Resource_List.max_walltime': '20:00:00',
             'Resource_List.min_walltime': '00:01:00'}
        j.set_attributes(a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        a = {'queue': 'ded_time',
             'Resource_List.max_walltime': '20:00:00',
             'Resource_List.min_walltime': '00:01:00'}
        j = Job(TEST_USER, attrs=a)
        j2id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '01:40:00')}
        self.server.expect(JOB, attr, id=j2id)

        attr = {'Resource_List.walltime': (GE, '00:01:00')}
        self.server.expect(JOB, attr, id=j2id)

        sw = self.server.status(JOB, 'Resource_List.walltime', id=j2id)
        wt = sw[0]['Resource_List.walltime']
        wt2 = wt

        # Make walltime given by qstat to agree with format in sched_logs.
        # A leading '0' is removed in the hour string.
        hh = wt.split(':')[0]
        if len(hh) == 2 and hh[0] == '0':
            wt2 = wt[1:]

        msg = "Job;%s;Job will run for duration=[%s|%s]" % (j2id, wt, wt2)
        self.scheduler.log_match(msg, regexp=True, max_attempts=5, interval=2)

    def test_t_4_1_1(self):
        """
        Test shrink to fit by setting a dedicated time that starts 1 hour
        from now for 1 hour  Submit a job that can run for as low as 10 minutes
        and as long as 10 hours.  Expect the job in R state with a walltime
        that is less than or equal to 1 hour and greater than or equal to
        10 minutes.
        """
        now = int(time.time())
        self.scheduler.add_dedicated_time(start=now + 3600, end=now + 7200)

        a = {'Resource_List.max_walltime': '10:00:00',
             'Resource_List.min_walltime': '00:10:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '01:00:00')}
        self.server.expect(JOB, attr, id=jid)

        attr = {'Resource_List.walltime': (GE, '00:10:00')}
        self.server.expect(JOB, attr, id=jid)

    def test_t_4_2_1(self):
        """
        Test shrink to fit by setting primetime that starts 4 hours from now
        and ends 12 hours from now and scheduler's backfill_prime is true.
        A regular job is submitted which goes into Q state.  Then a STF job
        with a max_walltime of 10:00:00 is able to run with a shrunk walltime
        of less than or equal to 4:00:00.
        """
        now = time.time()
        ptime_start = now + 14400
        ptime_end = now + 43200

        self.set_primetime(ptime_start, ptime_end)

        self.scheduler.set_sched_config({'backfill_prime': 'True'})

        a = {'Resource_List.ncpus': '1'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        a2 = {'Resource_List.max_walltime': '10:00:00',
              'Resource_List.min_walltime': '00:10:00'}
        j = Job(TEST_USER, attrs=a2)
        j2id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '04:00:00')}
        self.server.expect(JOB, attr, id=j2id)

        attr = {'Resource_List.walltime': (GE, '00:10:00')}
        self.server.expect(JOB, attr, id=j2id)

    def test_t_4_2_3(self):
        """
        Test shrink to fit by setting primetime that starts 4 hours from now
        and ends 12 hours from now and scheduler's backfill_prime is true and
        prime_spill is 1 hour.  A STF job with a min_walltime of 00:10:00 and
        with a max_walltime of 10:00:00 gets queued with a shrunk walltime
        of less than or equal to 05:00:00.
        """
        now = time.time()
        ptime_start = now + 14400
        ptime_end = now + 43200

        self.set_primetime(ptime_start, ptime_end)

        self.scheduler.set_sched_config({'backfill_prime': 'True',
                                         'prime_spill': '01:00:00'})

        a2 = {'Resource_List.max_walltime': '10:00:00',
              'Resource_List.min_walltime': '00:10:00'}
        j = Job(TEST_USER, attrs=a2)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '05:00:00')}
        self.server.expect(JOB, attr, id=jid)

        attr = {'Resource_List.walltime': (GE, '00:10:00')}
        self.server.expect(JOB, attr, id=jid)

    def test_t_4_2_4(self):
        """
        Test shrink to fit by setting primetime that started 22 minutes ago
        and ends 5:38 hours from now and scheduler's backfill_prime is true and
        prime_spill is 1 hour.  A STF job with a min_walltime of 00:01:00 and
        with a max_walltime of 20:00:00 gets queued with a shrunk walltime
        of less than or equal to 06:38:00.
        """
        now = time.time()
        ptime_start = now - 1320
        ptime_end = now + 20280

        self.set_primetime(ptime_start, ptime_end)

        self.scheduler.set_sched_config({'backfill_prime': 'True',
                                         'prime_spill': '01:00:00'})

        a = {'Resource_List.max_walltime': '20:00:00',
             'Resource_List.min_walltime': '00:01:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '06:38:00')}
        self.server.expect(JOB, attr, id=jid)

        attr = {'Resource_List.walltime': (GE, '00:01:00')}
        self.server.expect(JOB, attr, id=jid)

    def test_t_4_3_1(self):
        """
        Test shrink to fit by creating 16 reservations, say from R110 to R125,
        with R117, R121, R124 having ncpus=3, all others having ncpus=2.
        Duration of 10 min with 30 min difference between consecutive
        reservation.	A STF job will shrink its walltime to less than or
        equal to 4 hours.
        """
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        now = int(time.time())
        resv_dur = 600

        for i in range(1, 8):
            resv_start = now + i * 1800
            self.submit_resv(resv_start, 2, resv_dur)

        resv_start = now + 8 * 1800
        self.submit_resv(resv_start, 3, resv_dur)

        for i in range(9, 12):
            resv_start = now + i * 1800
            self.submit_resv(resv_start, 2, resv_dur)

        resv_start = now + 12 * 1800
        self.submit_resv(resv_start, 3, resv_dur)

        for i in range(13, 15):
            resv_start = now + i * 1800
            self.submit_resv(resv_start, 2, resv_dur)

        resv_start = now + 15 * 1800
        self.submit_resv(resv_start, 3, resv_dur)

        resv_start = now + 16 * 1800
        self.submit_resv(resv_start, 2, resv_dur)

        a = {'Resource_List.max_walltime': '10:00:00',
             'Resource_List.min_walltime': '00:10:00'}
        j = Job(TEST_USER, attrs=a)

        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '04:00:00')}
        self.server.expect(JOB, attr, id=jid)

        attr = {'Resource_List.walltime': (GE, '00:10:00')}
        self.server.expect(JOB, attr, id=jid)

    def test_t_4_3_6(self):
        """
        Test shrink to fit by creating one reservation having ncpus=1,
        starting in 3 min. with a duration of two hours.  A preempted STF job
        with min_walltime of 2 min. and max_walltime of 2 hours will stay
        suspended after higher priority job goes away if its
        min_walltime can't be satisfied.
        """
        self.skip_test('Skipping test due to PP-1049')
        qname = 'highp'

        a = {'queue_type': 'execution', 'enabled': 'True', 'started': 'True',
             'priority': '150'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)

        now = int(time.time())
        resv_dur = 7200

        resv_start = now + 180
        d = self.submit_resv(resv_start, 1, resv_dur)
        self.assertTrue(d)

        a = {'Resource_List.max_walltime': '02:00:00',
             'Resource_List.min_walltime': '00:02:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '00:03:00')}
        self.server.expect(JOB, attr, id=jid)

        attr = {'Resource_List.walltime': (GE, '00:02:00')}
        self.server.expect(JOB, attr, id=jid)

        # The sleep below will leave less than 2 minutes window for jid
        # after j2id is deleted.  The min_walltime of jid can't be
        # satisfied and jid will stay in S state.
        self.logger.info("Sleeping 65s to leave less than 2m before resv")
        time.sleep(65)

        a = {'queue': 'highp', 'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '00:01:00'}
        j = Job(TEST_USER, attrs=a)
        j2id = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

        self.server.delete(j2id)

        t = int(time.time())
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.log_match("Leaving Scheduling Cycle", starttime=t,
                                 max_attempts=5)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

    def test_t_4_3_8(self):
        """
        Test shrink to fit by submitting a STF job and then creating a
        reservation having ncpus=1 that overlaps with the job.  The
        reservation is denied.
        """
        a = {'Resource_List.max_walltime': '02:00:00',
             'Resource_List.min_walltime': '00:02:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        now = int(time.time())
        resv_start = now + 300
        resv_dur = 7200

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'free',
             'reserve_start': resv_start,
             'reserve_duration': resv_dur
             }
        r = Reservation(TEST_USER, attrs=a)
        rid1 = self.server.submit(r)
        self.server.log_match(rid1 + ";reservation deleted", max_attempts=10)

        self.server.delete(jid, wait=True)

        a = {'Resource_List.select': '1:ncpus=1'}
        j = Job(TEST_USER, attrs=a)
        j2id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)

        resv_start = now + 300
        resv_dur = 7200

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'free',
             'reserve_start': resv_start,
             'reserve_duration': resv_dur
             }
        r = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r)

        self.server.log_match(rid2 + ";reservation deleted", max_attempts=10)

    def test_t_4_4_1(self):
        """
        Test shrink to fit by submitting top jobs as barrier.
        A STF job will shrink its walltime relative to top jobs
        """
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        a = {'strict_ordering': 'true ALL', 'backfill': 'true ALL'}
        self.scheduler.set_sched_config(a)

        a = {'backfill_depth': '20'}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)

        a = {'Resource_List.select': '1:ncpus=2',
             'Resource_List.place': 'free',
             'Resource_List.walltime': '01:00:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        for _ in range(1, 5):
            self.submit_jq(2)

        self.submit_jq(3)

        for _ in range(6, 8):
            self.submit_jq(2)

        self.submit_jq(3)

        for _ in range(9, 12):
            self.submit_jq(2)

        self.submit_jq(3)

        for _ in range(13, 16):
            self.submit_jq(2)

        a = {'Resource_List.max_walltime': '10:00:00',
             'Resource_List.min_walltime': '00:10:00',
             'Resource_List.select': '1:ncpus=1'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        attr = {'Resource_List.walltime': (LE, '05:00:00')}
        self.server.expect(JOB, attr, id=jid)

    def test_t_4_5_1(self):
        """
        Test shrink to fit by setting primetime that started 45 minutes ago
        and ends 2:45 hours from now and dedicated time starting in 5 minutes
        ending in 1:45 hours.  A STF job with a min_walltime of 00:01:00 and
        with a max_walltime of 20:00:00 gets queued with a shrunk walltime
        of less than or equal to 00:05:00.
        """
        now = int(time.time())
        ptime_start = now - 2700
        ptime_end = now + 9900

        p_day = 'weekday'
        p_hhmm = time.strftime('%H%M', time.localtime(ptime_start))
        np_hhmm = time.strftime('%H%M', time.localtime(ptime_end))
        self.scheduler.holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'saturday'
        self.scheduler.holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'sunday'
        self.scheduler.holidays_set_day(p_day, p_hhmm, np_hhmm)

        self.scheduler.add_dedicated_time(start=now + 300, end=now + 6300)

        a = {'Resource_List.max_walltime': '20:00:00',
             'Resource_List.min_walltime': '00:01:00'}
        j = Job(TEST_USER, attrs=a)
        j2id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)

        attr = {'Resource_List.walltime': (LE, '00:05:00')}
        self.server.expect(JOB, attr, id=j2id)

    def test_t_4_6_1(self):
        """
        Test shrink to fit by submitting a reservation and top jobs as
        barriers. A STF job will shrink its walltime relative to top jobs
        and reservations.
        """
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})

        now = int(time.time())
        resv_start = now + 4200
        resv_dur = 900
        self.submit_resv(resv_start, 3, resv_dur)

        a = {'Resource_List.select': '1:ncpus=2',
             'Resource_List.place': 'free',
             'Resource_List.walltime': '00:15:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        a = {'Resource_List.select': '1:ncpus=3',
             'Resource_List.place': 'free',
             'Resource_List.walltime': '00:15:00'}
        j = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        a = {'Resource_List.max_walltime': '02:00:00',
             'Resource_List.min_walltime': '00:01:00',
             'Resource_List.select': '1:ncpus=1'}
        j = Job(TEST_USER, attrs=a)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        attr = {'Resource_List.walltime': (LE, '00:01:00')}
        self.server.expect(JOB, attr, id=jid3)

    def test_t_5_1_1(self):
        """
        STF job's min/max_walltime relative to resources_min/max.walltime
        setting on queue.
        """
        a = {'resources_min.walltime': '00:10:00',
             'resources_max.walltime': '10:00:00'}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id="workq", expect=True)

        a = {'Resource_List.max_walltime': '10:00:00',
             'Resource_List.min_walltime': '00:09:00'}
        j = Job(TEST_USER, attrs=a)

        error_msg = 'Job violates queue and/or server resource limits'
        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

        a = {'Resource_List.max_walltime': '00:09:00',
             'Resource_List.min_walltime': '00:09:00'}
        j = Job(TEST_USER, attrs=a)

        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

        a = {'Resource_List.max_walltime': '11:00:00',
             'Resource_List.min_walltime': '00:10:00'}
        j = Job(TEST_USER, attrs=a)

        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

        a = {'Resource_List.max_walltime': '11:00:00',
             'Resource_List.min_walltime': '11:00:00'}
        j = Job(TEST_USER, attrs=a)
        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

        a = {'Resource_List.max_walltime': '10:00:00',
             'Resource_List.min_walltime': '00:10:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.delete(jid)

        a = {'Resource_List.max_walltime': '00:10:00',
             'Resource_List.min_walltime': '00:10:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.delete(jid)

        a = {'Resource_List.max_walltime': '10:00:00',
             'Resource_List.min_walltime': '10:00:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.delete(jid)

        a = {'Resource_List.max_walltime': '09:00:00',
             'Resource_List.min_walltime': '00:11:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_t_5_1_2(self):
        """
        STF job's max_walltime relative to resources_max.walltime
        setting on server.
        """
        a = {'resources_max.walltime': '15:00:00'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'Resource_List.max_walltime': '16:00:00',
             'Resource_List.min_walltime': '00:20:00'}
        j = Job(TEST_USER, attrs=a)

        error_msg = 'Job violates queue and/or server resource limits'
        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

        a = {'Resource_List.max_walltime': '16:00:00',
             'Resource_List.min_walltime': '16:00:00'}
        j = Job(TEST_USER, attrs=a)

        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

        a = {'Resource_List.max_walltime': '15:00:00',
             'Resource_List.min_walltime': '15:00:00'}
        j = Job(TEST_USER, attrs=a)

        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_t_5_2_1(self):
        """
        Setting resources_max.min_walltime on a queue.
        """
        a = {'resources_max.min_walltime': '10:00:00'}
        try:
            self.server.manager(MGR_CMD_SET, QUEUE, a, id="workq")
        except PbsManagerError as e:
            self.assertTrue('Resource limits can not be set for the resource'
                            in e.msg[0])

    def test_t_5_2_2(self):
        """
        Setting resources_max.min_walltime on the server.
        """
        a = {'resources_max.min_walltime': '10:00:00'}
        try:
            self.server.manager(MGR_CMD_SET, SERVER, a)
        except PbsManagerError as e:
            self.assertTrue('Resource limits can not be set for the resource'
                            in e.msg[0])

    def test_t_6(self):
        """
        Test to see that the min_walltime is not unset if the max_walltime
        is attempted to be set less than the min.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {'Resource_List.min_walltime': 9, 'Resource_List.max_walltime': 60}
        J = Job(TEST_USER, attrs=a)
        jid = self.server.submit(J)
        try:
            self.server.alterjob(jid, {'Resource_List.max_walltime': 3})
        except PbsAlterError as e:
            self.assertTrue('\"min_walltime\" can not be greater'
                            ' than \"max_walltime\"' in e.msg[0])

        self.server.expect(JOB, 'Resource_List.min_walltime', op=SET)
        self.server.expect(JOB, 'Resource_List.max_walltime', op=SET)

        try:
            self.server.alterjob(jid, {'Resource_List.min_walltime': 180})
        except PbsAlterError as e:
            self.assertTrue('\"min_walltime\" can not be greater'
                            ' than \"max_walltime\"' in e.msg[0])

        self.server.expect(JOB, 'Resource_List.min_walltime', op=SET)
        self.server.expect(JOB, 'Resource_List.max_walltime', op=SET)

        try:
            a = {'Resource_List.min_walltime': 60,
                 'Resource_List.max_walltime': 30}
            self.server.alterjob(jid, a)
        except PbsAlterError as e:
            self.assertTrue('\"min_walltime\" can not be greater'
                            ' than \"max_walltime\"' in e.msg[0])

        self.server.expect(JOB, 'Resource_List.min_walltime', op=SET)
        self.server.expect(JOB, 'Resource_List.max_walltime', op=SET)

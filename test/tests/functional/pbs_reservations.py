# coding: utf-8

# Copyright (C) 1994-2019 Altair Engineering, Inc.
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
import time


@tags('reservations')
class TestReservations(TestFunctional):
    """
    Various tests to verify behavior of PBS scheduler in handling
    reservations
    """

    def submit_standing_reservation(self, user, select, rrule, start, end,
                                    place='free'):
        """
        helper method to submit a standing reservation
        """
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'

        a = {'Resource_List.select': select,
             'Resource_List.place': place,
             ATTR_resv_rrule: rrule,
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             }
        r = Reservation(user, a)

        return self.server.submit(r)

    def submit_asap_reservation(self, user, jid):
        """
        Helper method to submit an ASAP reservation
        """
        a = {ATTR_convert: jid}
        r = Reservation(user, a)

        # PTL's Reservation class sets the default ATTR_resv_start
        # and ATTR_resv_end.
        # But pbs_rsub: -Wqmove is not compatible with -R or -E option
        # So, unset these attributes from the reservation instance.
        r.unset_attributes(['reserve_start', 'reserve_end'])

        return self.server.submit(r)

    def test_degraded_standing_reservations(self):
        """
        Verify that degraded standing reservations are reconfirmed on
        other avaialable vnodes
        """

        a = {'reserve_retry_init': 5, 'reserve_retry_cutoff': 1}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vn', a, num=2, mom=self.mom)

        now = int(time.time())

        # submitting 25 seconds from now to allow some of the older testbed
        # systems time to process (discovered empirically)
        rid = self.submit_standing_reservation(user=TEST_USER,
                                               select='1:ncpus=4',
                                               rrule='FREQ=HOURLY;COUNT=3',
                                               start=now + 25,
                                               end=now + 45)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]

        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        offset = 25 - (int(time.time()) - now)
        self.server.expect(RESV, a, id=rid, offset=offset, interval=1)

        a = {'state': 'offline'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=resv_node)

        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'),
             'reserve_substate': 10}
        self.server.expect(RESV, a, attrop=PTL_AND, id=rid)

        a = {'resources_available.ncpus': (GT, 0)}
        free_nodes = self.server.filter(NODE, a)
        nodes = list(free_nodes.values())[0]

        other_node = [nodes[0], nodes[1]][resv_node == nodes[0]]

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
             'resv_nodes': (MATCH_RE, re.escape(other_node))}
        offset = 45 - (int(time.time()) - now)
        self.server.expect(RESV, a, id=rid, interval=1, offset=offset,
                           attrop=PTL_AND)

    def test_not_honoring_resvs(self):
        """
        PBS schedules jobs on nodes without accounting
        for the reservation on the node
        """

        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vn', a, 1, self.mom, usenatvnode=True)

        r1 = Reservation(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1', 'reserve_start': int(
            time.time() + 5), 'reserve_end': int(time.time() + 15)}
        r1.set_attributes(a)
        r1id = self.server.submit(r1)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, r1id)

        r2 = Reservation(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=4', 'reserve_start': int(
            time.time() + 600), 'reserve_end': int(time.time() + 7800)}
        r2.set_attributes(a)
        r2id = self.server.submit(r2)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, r2id)

        r1_que = r1id.split('.')[0]
        for i in range(20):
            j = Job(TEST_USER)
            a = {'Resource_List.select': '1:ncpus=1',
                 'Resource_List.walltime': 10, 'queue': r1_que}
            j.set_attributes(a)
            self.server.submit(j)

        j1 = Job(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 7200}
        j1.set_attributes(a)
        j1id = self.server.submit(j1)

        j2 = Job(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 7200}
        j2.set_attributes(a)
        j2id = self.server.submit(j2)

        a = {'reserve_state': (MATCH_RE, "RESV_BEING_DELETED|7")}
        self.server.expect(RESV, a, id=r1id, interval=1)

        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.expect(JOB, {'job_state': 'Q'}, id=j1id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j2id)

    def test_sched_cycle_starts_on_resv_end(self):
        """
        This test checks whether the sched cycle gets started
        when the advance reservation ends.
        """
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            sudo=True)

        now = int(time.time())
        a = {'Resource_List.select': "1:ncpus=2",
             'reserve_start': now + 10,
             'reserve_end': now + 30,
             }
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, rid)

        attr = {'Resource_List.walltime': '00:00:20'}
        j = Job(TEST_USER, attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'Q'},
                           id=jid)
        msg = "Job would conflict with reservation or top job"
        self.server.expect(JOB, {ATTR_comment: "Not Running: " + msg}, id=jid)
        self.scheduler.log_match(
            jid + ";" + msg,
            max_attempts=30)

        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|2')}
        self.server.expect(RESV, a, rid)

        resid = rid.split('.')[0]
        self.server.log_match(resid + ";deleted at request of pbs_server",
                              id=resid, interval=5)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

    def test_exclusive_state(self):
        """
        Test that the resv-exclusive and job-exclusive
        states are approprately set
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            sudo=True)

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl', 'reserve_start': now + 30,
             'reserve_end': now + 3600}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid, offset=30)

        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=self.server.shortname)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl', 'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        n = self.server.status(NODE)
        states = n[0]['state'].split(',')
        self.assertIn('resv-exclusive', states)
        self.assertIn('job-exclusive', states)

    def test_resv_excl_future_resv(self):
        """
        Test to see that exclusive reservations in the near term do not
        interfere with longer term reservations
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            sudo=True)

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl', 'reserve_start': now + 30,
             'reserve_end': now + 3600}
        r1 = Reservation(TEST_USER, attrs=a)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a['reserve_start'] = now + 7200
        a['reserve_end'] = now + 10800
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)

        self.server.expect(RESV, exp_attr, id=rid2)

    def test_job_exceed_resv_end(self):
        """
        Test to see that a job when submitted to a reservation without the
        walltime would not show up as exceeding the reservation and
        making the scheduler reject future reservations.
        """

        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            sudo=True)

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 30,
             'reserve_end': now + 300}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid, offset=30)

        # Submit a job but do not specify walltime, scheduler will consider
        # the walltime of such a job to be 5 years
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit another reservation that will start after first
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 360,
             'reserve_end': now + 3600}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid2)

    def test_future_resv_conflicts_running_job(self):
        """
        Test if a running exclusive job without walltime will deny the future
        resv from getting confirmed.
        """

        now = int(time.time())
        # Submit a job but do not specify walltime, scheduler will consider
        # the walltime of such a job to be 5 years
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit a reservation that will start after the job starts running
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 360,
             'reserve_end': now + 3600}
        r1 = Reservation(TEST_USER, attrs=a)
        rid1 = self.server.submit(r1)

        self.server.log_match(rid1 + ";Reservation denied",
                              id=rid1, interval=5)

    def test_future_resv_confirms_after_running_job(self):
        """
        Test if a future reservation gets confirmed if its start time starts
        after the end time of a job running in an exclusive reservation
        """

        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            sudo=True)

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 30,
             'reserve_end': now + 300}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid, offset=30)

        # Submit a job with walltime exceeding reservation duration
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'Resource_List.walltime': 600,
             'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit another reservation that will start after the job ends
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 630,
             'reserve_end': now + 3600}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid2)

    def test_future_resv_confirms_before_non_excl_job(self):
        """
        Test if a future reservation gets confirmed if its start time starts
        before the end time of a non exclusive job running in an exclusive
        reservation.
        """

        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            sudo=True)

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 30,
             'reserve_end': now + 300}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid, offset=30)

        # Submit a job with walltime exceeding reservation duration
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 600,
             'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit another reservation that will start after the first
        # reservation ends
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 330,
             'reserve_end': now + 3600}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid2)

    def test_future_resv_with_non_excl_jobs(self):
        """
        Test if future reservations with/without exclusive placement are
        confirmed if their start time starts before end time of non exclusive
        jobs that are running in reservation.
        """

        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname,
                            sudo=True)

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 30,
             'reserve_end': now + 300}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid, offset=30)

        # Submit a job with walltime exceeding reservation
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 600,
             'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit another non exclusive reservation that will start after
        # previous reservation ends but before job's walltime is over.
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 330,
             'reserve_end': now + 3600}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid2)

        self.server.delete(rid2)

        # Submit another exclusive reservation that will start after
        # previous reservation ends but before job's walltime is over.
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 330,
             'reserve_end': now + 3600}
        r3 = Reservation(TEST_USER, attrs=a)
        rid3 = self.server.submit(r3)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid3)

    def test_resv_excl_with_jobs(self):
        """
        Test to see that exclusive reservations in the near term do not
        interfere with longer term reservations with jobs inside
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.server.shortname)

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl', 'reserve_start': now + 30,
             'reserve_end': now + 300}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid, offset=30)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'Resource_List.walltime': '30',
             'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit another reservation that will start after first
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl', 'reserve_start': now + 360,
             'reserve_end': now + 3600}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid2)

    def test_resv_server_restart(self):
        """
        Test if a reservation correctly goes into the resv-exclusive state
        if the server is restarted between when the reservation gets
        confirmed and when it starts
        """
        now = int(time.time())
        start = now + 30
        a = {'reserve_start': start, 'reserve_end': start + 300,
             'Resource_List.select': '1:ncpus=1:vnode=' +
                                     self.server.shortname,
             'Resource_List.place': 'excl'}

        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.server.restart()

        sleep_time = start - int(time.time())

        self.logger.info('Waiting %d seconds till resv starts' % sleep_time)
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid, offset=sleep_time)

        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=self.server.shortname)

    def test_multiple_asap_resv(self):
        """
        Test that multiple ASAP reservations are scheduled one after another
        """
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 1},
                            id=self.server.shortname)

        job_attrs = {'Resource_List.select': '1:ncpus=1',
                     'Resource_List.walltime': '1:00:00'}
        j = Job(TEST_USER, attrs=job_attrs)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        s = self.server.status(JOB, 'stime', id=jid1)
        job_stime = int(time.mktime(time.strptime(s[0]['stime'], '%c')))

        j = Job(TEST_USER, attrs=job_attrs)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, 'comment', op=SET, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        rid1 = self.submit_asap_reservation(TEST_USER, jid2)
        exp_attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attrs, id=rid1)
        s = self.server.status(RESV, 'reserve_start', id=rid1)
        resv1_stime = int(time.mktime(
            time.strptime(s[0]['reserve_start'], '%c')))
        msg = 'ASAP reservation has incorrect start time'
        self.assertEqual(resv1_stime, job_stime + 3600, msg)

        j = Job(TEST_USER, attrs=job_attrs)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, 'comment', op=SET, id=jid3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)

        rid2 = self.submit_asap_reservation(TEST_USER, jid3)
        exp_attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attrs, id=rid2)
        s = self.server.status(RESV, 'reserve_start', id=rid2)
        resv2_stime = int(time.mktime(
            time.strptime(s[0]['reserve_start'], '%c')))
        msg = 'ASAP reservation has incorrect start time'
        self.assertEqual(resv2_stime, resv1_stime + 3600, msg)

    def test_excl_asap_resv_before_longterm_resvs(self):
        """
        Test if an ASAP reservation created from an exclusive
        placement job does not interfere with subsequent long
        term advance and standing exclusive reservations
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        # Submit a job and let it run with available resources
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 30}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        # Submit a second job with exclusive node placement
        # and let it be queued
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 300,
             'Resource_List.place': 'excl'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, 'comment', op=SET, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        # Convert j2 into an ASAP reservation
        rid1 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid2)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        # Wait for the reservation to start
        self.logger.info('Waiting 30 seconds for reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid1, offset=30)

        # Submit a long term reservation with exclusive node
        # placement when rid1 is running
        # This reservation should be confirmed
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 3600,
             'reserve_end': now + 3605}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid2)

        # Submit a long term standing reservation with exclusive node
        # placement when rid1 is running
        # This reservation should also be confirmed
        now = int(time.time())
        rid3 = self.submit_standing_reservation(user=TEST_USER,
                                                select='1:ncpus=1',
                                                place='excl',
                                                rrule='FREQ=HOURLY;COUNT=3',
                                                start=now + 7200,
                                                end=now + 7205)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid3)

    def test_excl_asap_resv_after_longterm_resvs(self):
        """
        Test if an exclusive ASAP reservation created from an exclusive
        placement job does not interfere with already existing long term
        exclusive reservations.
        Also, test if future exclusive reservations are successful when
        the ASAP reservation is running.
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        # Submit a long term advance reservation with exclusive node
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 360,
             'reserve_end': now + 365}
        r1 = Reservation(TEST_USER, attrs=a)
        rid1 = self.server.submit(r1)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        # Submit a long term standing reservation with exclusive node
        now = int(time.time())
        rid2 = self.submit_standing_reservation(user=TEST_USER,
                                                select='1:ncpus=1',
                                                place='excl',
                                                rrule='FREQ=HOURLY;COUNT=3',
                                                start=now + 3600,
                                                end=now + 3605)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid2)

        # Submit a job and let it run with available resources
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 30}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        # Submit a second job with exclusive node placement
        # and let it be queued
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 300,
             'Resource_List.place': 'excl'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, 'comment', op=SET, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        # Convert j2 into an ASAP reservation
        rid1 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid2)

        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        # Wait for the reservation to start
        self.logger.info('Waiting 30 seconds for reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid1, offset=30)

        # Submit a long term reservation with exclusive node
        # placement when rid1 is running
        # This reservation should be confirmed
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             'reserve_start': now + 3600,
             'reserve_end': now + 3605}
        r3 = Reservation(TEST_USER, attrs=a)
        rid3 = self.server.submit(r3)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid3)

    def test_multi_vnode_excl_advance_resvs(self):
        """
        Test if long term exclusive reservations do not interfere
        with current reservations on a multi-vnoded host
        """
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vn', a, num=3, mom=self.mom)

        # Submit a long term standing reservation with
        # exclusive nodes.
        now = int(time.time())
        rid1 = self.submit_standing_reservation(user=TEST_USER,
                                                select='1:ncpus=9',
                                                place='excl',
                                                rrule='FREQ=HOURLY;COUNT=3',
                                                start=now + 7200,
                                                end=now + 7205)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        # Submit a long term advance reservation with exclusive node
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=10',
             'Resource_List.place': 'excl',
             'reserve_start': now + 3600,
             'reserve_end': now + 3605}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid2)

        # Submit a short term reservation requesting all the nodes
        # exclusively
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=12',
             'Resource_List.place': 'excl',
             'reserve_start': now + 20,
             'reserve_end': now + 100}
        r3 = Reservation(TEST_USER, attrs=a)
        rid3 = self.server.submit(r3)
        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid3)

        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid3, offset=30)

    def test_multi_vnode_excl_asap_resv(self):
        """
        Test if an ASAP reservation created from a excl placement
        job does not interfere with future multinode exclusive
        reservations on a multi-vnoded host
        """
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vn', a, num=3, mom=self.mom)

        # Submit 3 exclusive jobs, so all the nodes are busy
        # j1 requesting 4 cpus, j2 requesting 4 cpus and j3
        # requesting 5 cpus
        a = {'Resource_List.select': '1:ncpus=4',
             'Resource_List.place': 'excl',
             'Resource_List.walltime': 30}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        a['Resource_List.walltime'] = 400
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        a = {'Resource_List.select': '1:ncpus=5',
             'Resource_List.place': 'excl',
             'Resource_List.walltime': 100}
        j3 = Job(TEST_USER, attrs=a)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, 'comment', op=SET, id=jid3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)

        # Convert J3 to ASAP reservation
        rid1 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid3)

        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        # Wait for the reservation to start
        self.logger.info('Waiting 30 seconds for reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid1, offset=30)

        # Submit a long term reservation with exclusive node
        # placement when rid1 is running (requesting all nodes)
        # This reservation should be confirmed
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=12',
             'Resource_List.place': 'excl',
             'reserve_start': now + 3600,
             'reserve_end': now + 3605}
        r2 = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r2)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid2)

    def test_fail_confirm_resv_message(self):
        """
        Test if the scheduler fails to reserve a
        reservation, the reason will be logged.
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        # Submit a long term advance reservation that will be denied
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=10',
             'reserve_start': now + 360,
             'reserve_end': now + 365}
        rid = self.server.submit(Reservation(TEST_USER, attrs=a))
        self.server.log_match(rid + ";Reservation denied",
                              id=rid, interval=5)
        # The scheduler should log reason why it was denied
        self.scheduler.log_match(rid + ";PBS Failed to confirm resv: " +
                                 "Insufficient amount of resource: ncpus")

    def common_steps(self):
        """
        This function has common steps for configuration used in tests
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)
        self.server.manager(MGR_CMD_SET, SERVER, {
            'job_history_enable': 'True'})

    @skipOnCpuSet
    def test_advance_reservation_with_job_array(self):
        """
        Test to submit a job array within a advance reservation
        Check if the reservation gets confimed and the jobs
        inside the reservation starts running when the reservation runs.
        """
        self.common_steps()
        # Submit a job-array
        j = Job(TEST_USER, attrs={ATTR_J: '1-4'})
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           id=jid, extend='t')
        # Check status of the sub-job using qstat -fx once job completes
        self.server.expect(JOB, {'job_state': 'F'}, extend='x',
                           offset=10, id=jid)

        # Submit a advance reservation (R1) and an array job to the reservation
        # once reservation confirmed
        now = int(time.time())
        a = {'reserve_start': now + 20,
             'reserve_end': now + 120}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        a = {ATTR_q: rid_q, ATTR_J: '1-4'}
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(10)
        jid2 = self.server.submit(j2)
        subjid = []
        for i in range(1, 5):
            subjid.append(j.create_subjob_id(jid2, i))

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=20)
        self.server.expect(JOB, {'job_state': 'B'}, jid2)
        self.server.expect(JOB, {'job_state=R': 1}, count=True,
                           id=jid2, extend='t')
        self.server.expect(JOB, {'job_state=Q': 3}, count=True,
                           extend='t', id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid[0])
        self.server.expect(JOB, {'job_state': 'Q'}, id=subjid[1])
        self.server.expect(JOB, {'job_state': 'Q'}, id=subjid[2])
        self.server.expect(JOB, {'job_state': 'Q'}, id=subjid[3])
        self.server.delete(subjid[0])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid[1])
        # Wait for reservation to delete from server
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=10)
        # Check status of the sub-job using qstat -fx once job completes
        self.server.expect(JOB, {'job_state': 'F', 'Exit_status': '271'},
                           extend='x', attrop=PTL_AND, id=subjid[0])
        self.server.expect(JOB, {'job_state': 'F', 'Exit_status': '0'},
                           extend='x', attrop=PTL_AND, id=subjid[3])

        # Submit a advance reservation (R2) and an array job to the reservation
        # once reservation confirmed
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=4',
             'reserve_start': now + 20,
             'reserve_end': now + 180}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        a = {ATTR_q: rid_q, ATTR_J: '1-4'}
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(60)
        jid2 = self.server.submit(j2)
        subjid = []
        for i in range(1, 5):
            subjid.append(j.create_subjob_id(jid2, i))

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=20)
        self.server.expect(JOB, {'job_state': 'B'}, jid2)
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           id=jid2, extend='t')
        # Submit another job-array with small sleep time than job j2
        a = {ATTR_q: rid_q, ATTR_J: '1-4'}
        j3 = Job(TEST_USER, attrs=a)
        j3.set_sleep_time(10)
        jid3 = self.server.submit(j3)
        subjid2 = []
        for i in range(1, 5):
            subjid2.append(j.create_subjob_id(jid3, i))
        self.server.expect(JOB, {'job_state': 'Q'}, jid3)
        self.server.expect(JOB, {'job_state=Q': 5}, count=True,
                           id=jid3, extend='t')
        self.server.expect(JOB, {'job_state': 'Q'}, id=subjid2[0])
        # Wait for job array j2 to finish and verify all sub-job
        # from j3 start running
        self.server.expect(JOB, {'job_state': 'B'}, jid3, offset=60)
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           id=jid3, extend='t')
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=10)
        # Check status of the job-array using qstat -fx at the end of
        # reservation
        self.server.expect(JOB, {'job_state': 'F', 'Exit_status': '0'},
                           extend='x', attrop=PTL_AND, id=jid2)
        self.server.expect(JOB, {'job_state': 'F', 'Exit_status': '0'},
                           extend='x', attrop=PTL_AND, id=jid3)

    @requirements(num_moms=2)
    def test_advance_resv_with_multinode_job_array(self):
        """
        Test multinode job array with advance reservation
        """
        if (len(self.moms) < 2):
            self.skip_test("Test requires 2 moms: use -p mom1:mom2")
        a = {'resources_available.ncpus': 4}
        for mom in self.moms.values():
            self.server.manager(MGR_CMD_SET, NODE, a, id=mom.shortname)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})
        # Submit reservation with placement type scatter
        now = int(time.time())
        a = {'Resource_List.select': '2:ncpus=2',
             'Resource_List.place': 'scatter',
             'reserve_start': now + 30,
             'reserve_end': now + 300}
        r = Reservation(PBSROOT_USER, attrs=a)
        rid = self.server.submit(r)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        resv_queue = rid.split(".")[0]

        # Submit job array in reservation queue
        attrs = {ATTR_q: resv_queue, ATTR_J: '1-5',
                 'Resource_List.select': '2:ncpus=1'}
        j = Job(PBSROOT_USER, attrs)
        j.set_sleep_time(60)
        jid = self.server.submit(j)
        subjid = []
        for i in range(1, 6):
            subjid.append(j.create_subjob_id(jid, i))

        self.logger.info("Wait 30s for resv to be in Running state")
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid, offset=30)
        self.server.expect(JOB, {'job_state': 'B'}, id=jid)
        self.server.expect(JOB, {'job_state=R': 2}, count=True,
                           extend='t', id=jid)
        self.server.expect(JOB, {'job_state=Q': 3}, count=True,
                           extend='t', id=jid)
        self.server.sigjob(jobid=subjid[0], signal="suspend")
        self.server.expect(JOB, {'job_state': 'S'}, id=subjid[0])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid[2])

        # Submit job array with placement type scatter in resv queue
        attrs = {ATTR_q: resv_queue, ATTR_J: '1-5',
                 'Resource_List.place': 'scatter',
                 'Resource_List.select': '2:ncpus=1'}
        j1 = Job(PBSROOT_USER, attrs)
        j1.set_sleep_time(60)
        jid2 = self.server.submit(j1)
        subjid2 = []
        for i in range(1, 6):
            subjid2.append(j.create_subjob_id(jid2, i))
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        self.server.sigjob(subjid[0], 'resume')
        self.logger.info("Wait 120s for all the subjobs to complete")
        self.server.expect(JOB, {'job_state': 'F', 'exit_status': '0'},
                           id=jid, extend='x', interval=10, offset=120)

        self.server.expect(JOB, {'job_state': 'B'}, id=jid2)
        self.server.expect(JOB, {'job_state=R': 2}, count=True,
                           extend='t', id=jid2)
        self.server.expect(JOB, {'job_state=Q': 3}, count=True,
                           extend='t', id=jid2)
        self.server.sigjob(jobid=subjid2[0], signal="suspend")
        self.server.expect(JOB, {'job_state': 'S'}, id=subjid2[0])
        self.server.sigjob(jobid=subjid2[1], signal="suspend")
        self.server.expect(JOB, {'job_state': 'S'}, id=subjid2[1])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid2[2])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid2[3])
        self.server.delete([subjid2[2], subjid2[3]])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid2[4])
        self.server.expect(JOB, {'job_state': 'X'}, id=subjid2[4], offset=60)
        self.server.sigjob(subjid2[0], 'resume')
        self.server.sigjob(subjid2[1], 'resume')
        self.server.expect(JOB, {'job_state=R': 2}, count=True,
                           extend='t', id=jid2)
        self.logger.info("Wait 120s for all the subjobs to complete")
        self.server.expect(JOB, {'job_state': 'F'},
                           id=jid2, extend='x', interval=10, offset=120)

    def test_reservations_with_expired_subjobs(self):
        """
        Test that an array job submitted to a reservation ends when
        there are expired subjobs in the array job and job history is
        enabled
        """
        self.common_steps()
        # Submit a advance reservation and an array job to the reservation
        # once reservation confirmed
        now = int(time.time())
        a = {'reserve_start': now + 10,
             'reserve_end': now + 40}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        # submit enough jobs that there are some expired subjobs and some
        # queued/running subjobs left in the system by the time reservation
        # ends
        a = {ATTR_q: rid_q, ATTR_J: '1-20'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(2)
        jid = self.server.submit(j)

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        # Wait for reservation to delete from server
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=10)
        # Check status of the parent-job using qstat -fx once reservation ends
        self.server.expect(JOB, {'job_state': 'F', 'substate': '91'},
                           extend='x', id=jid)

    @skipOnCpuSet
    def test_ASAP_resv_with_job_array(self):
        """
        Test job-array converted into ASAP reservation
        should run as per resources requested in job-array.
        """
        self.common_steps()

        # Submit job j to take up the resources
        a = {'Resource_List.walltime': '10',
             'Resource_List.select': '1:ncpus=4'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        # Submit a job-array j2
        a = {ATTR_J: '1-10',
             'Resource_List.select': '1:ncpus=4',
             'Resource_List.walltime': '5'}
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(5)
        jid2 = self.server.submit(j2)
        subjid = []
        for i in range(1, 10):
            subjid.append(j.create_subjob_id(jid2, i))
        self.server.expect(JOB, {'job_state': 'Q'}, jid2)
        self.server.expect(JOB, {'job_state=Q': 11}, count=True,
                           id=jid2, extend='t')

        # Wait for job j to finish
        self.server.expect(JOB, {'job_state': 'F'},
                           extend='x', id=jid, interval=1)
        # Convert job-array j2 into an ASAP reservation
        now = int(time.time())
        rid1 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid2)
        rid1_q = rid1.split('.')[0]
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        self.server.expect(
            JOB, {'job_state': 'R', 'queue': 'workq'}, id=subjid[0])
        # Wait for the ASAP reservation to start, verify subjob state in
        # reservation
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid1, interval=1)
        self.server.expect(
            JOB, {'job_state': 'R', 'queue': rid1_q},
            attrop=PTL_AND, id=subjid[1])
        self.server.expect(
            JOB, {'job_state': 'Q', 'queue': rid1_q},
            attrop=PTL_AND, id=subjid[2])
        self.server.expect(
            JOB, {'job_state': 'Q', 'queue': rid1_q},
            attrop=PTL_AND, id=subjid[3])

        # Wait for reservation to be finish
        msg = "Que;" + rid1_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=10)
        # Check status of the parent job-array and subjobs using
        # qstat -fx at the end of  reservation
        self.server.expect(JOB, {'job_state=F': 1}, count=True,
                           id=jid2, extend='x')
        self.server.expect(JOB, {'job_state': 'F', 'queue': rid1_q,
                                 'substate': '91'}, id=subjid[1],
                           attrop=PTL_AND, extend='x')
        self.server.expect(JOB, {'job_state': 'F', 'queue': rid1_q,
                                 'substate': '91'}, id=subjid[2],
                           attrop=PTL_AND, extend='x')
        self.server.expect(JOB, {'job_state': 'F', 'queue': rid1_q,
                                 'substate': '91'}, id=subjid[3],
                           attrop=PTL_AND, extend='x')

    @skipOnCpuSet
    def test_ASAP_resv_request_same_time(self):
        """
        Test two job-array converted in two ASAP reservation
        which request same walltime should run and finish as
        per available resources.
        Also to verify 2 ASAP reservations with same start
        time doesn't crashes PBS daemon.
        """
        self.common_steps()

        # Submit job j to consume all resources
        a = {'Resource_List.walltime': '5',
             'Resource_List.select': '1:ncpus=4'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(5)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        # Submit a job-array j2
        a = {ATTR_J: '1-5',
             'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '10'}
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(10)
        jid2 = self.server.submit(j2)
        subjid = []
        for i in range(1, 5):
            subjid.append(j.create_subjob_id(jid2, i))
        self.server.expect(JOB, {'job_state=Q': 6}, count=True,
                           id=jid2, extend='t')

        # Convert j2 into an ASAP reservation
        now = int(time.time())
        rid1 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid2)
        rid1_q = rid1.split('.')[0]
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2"),
                    'reserve_duration': 10}
        self.server.expect(RESV, exp_attr, id=rid1)
        self.server.expect(
            JOB, {'job_state': 'Q', 'queue': rid1_q}, id=subjid[0])

        # Submit another job-array j3 same as j2
        j3 = Job(TEST_USER, attrs=a)
        j3.set_sleep_time(10)
        jid3 = self.server.submit(j3)
        subjid2 = []
        for i in range(1, 5):
            subjid2.append(j.create_subjob_id(jid3, i))
        self.server.expect(JOB, {'job_state': 'Q'}, jid3)
        self.server.expect(JOB, {'job_state=Q': 6}, count=True,
                           id=jid3, extend='t')

        # Convert j3 into an ASAP reservation
        now2 = int(time.time())
        rid2 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid3)
        rid2_q = rid2.split('.')[0]
        self.server.expect(RESV, exp_attr, id=rid2)
        self.server.expect(
            JOB, {'job_state': 'Q', 'queue': rid2_q}, id=subjid2[0])

        # Wait for both  reservation to start
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid1)
        self.server.expect(RESV, exp_attr, id=rid2)
        # Verify only one subjob from j2 and j3 start running
        self.server.expect(
            JOB, {'job_state': 'R', 'queue': rid1_q}, id=subjid[0])
        self.server.expect(
            JOB, {'job_state': 'R', 'queue': rid2_q}, id=subjid2[0])

        # Wait for reservations to be finish
        msg = "Que;" + rid1_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=5)
        msg = "Que;" + rid2_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now2)
        # Check status of the parent job-array using qstat -fx once reservation
        # ends
        jids = [jid2, jid3]
        for job in jids:
            self.server.expect(JOB, 'queue', op=UNSET, id=job)
            self.server.expect(JOB, {'job_state=F': 1}, count=True,
                               id=job, extend='x')

        # Check status of the subjob using qstat -fx once reservation
        # ends
        self.server.expect(JOB, {'job_state': 'F',
                                 'queue': rid1_q}, id=subjid[0],
                           attrop=PTL_AND,  extend='x')
        self.server.expect(JOB, {'job_state': 'F',
                                 'queue': rid2_q}, id=subjid2[0],
                           attrop=PTL_AND,  extend='x')
        # Verify pbs_server and pbs_scheduler is up
        if not self.server.isUp():
            self.fail("Server is not up")
        if not self.scheduler.isUp():
            self.fail("Scheduler is not up")

    @skipOnCpuSet
    def test_standing_resv_with_job_array(self):
        """
        Test job-array with standing reservation
        """
        self.common_steps()
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        # Submit a standing reservation to occur every other minute for a
        # total count of 2
        start = int(time.time()) + 10
        end = start + 20
        a = {'Resource_List.select': '1:ncpus=4',
             ATTR_resv_rrule: 'FREQ=MINUTELY;INTERVAL=2;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             }
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        rid_q = rid.split(".")[0]
        # Submit a job-array within reservation
        j = Job(TEST_USER, attrs={'Resource_List.select': '1:ncpus=1',
                                  ATTR_q: rid_q, ATTR_J: '1-4'})
        j.set_sleep_time(15)
        jid = self.server.submit(j)
        subjid = []
        for i in range(1, 4):
            subjid.append(j.create_subjob_id(jid, i))
        # Wait for standing reservation first instance to start
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid)
        self.server.expect(RESV, {'reserve_index': 1}, id=rid)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           id=jid, extend='t')
        # Wait for standing reservation first instance to finished
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)
        # Wait for standing reservation second instance to start
        self.logger.info(
            'Waiting 55 sec for second  instance of reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid, offset=55, interval=1)
        self.server.expect(RESV, {'reserve_index': 2}, id=rid)
        # Wait for reservations to be finished
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=end, interval=2)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

        # Check for subjob status for job-array
        # as all subjobs from job-array finished within the
        # instance so it should have substate=92
        for i in subjid:
            self.server.expect(JOB, {'job_state': 'F', 'substate': '92'},
                               extend='x', id=i)
        # Check for finished jobs by issuing the command qstat
        self.server.expect(JOB, {'job_state=F': 5, 'substate': '92'},
                           extend='xt', id=jid)

        start = int(time.time()) + 10
        end = int(time.time()) + 3660
        a = {ATTR_resv_rrule: 'FREQ=DAILY;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             }
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        rid_q = rid.split(".")[0]
        # Submit a job-array within resrvation
        j = Job(TEST_USER, attrs={
                'Resource_List.walltime': 20, ATTR_q: rid_q, ATTR_J: '1-5'})
        j.set_sleep_time(20)
        jid = self.server.submit(j)
        subjid = []
        for i in range(1, 6):
            subjid.append(j.create_subjob_id(jid, i))
        # Wait for standing reservation first instance to start
        # Verify one subjob start running and others remain queued
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid, interval=1)
        self.server.expect(RESV, {'reserve_index': 1}, id=rid)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        self.server.expect(JOB, {'job_state=R': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {'job_state=Q': 4}, count=True,
                           id=jid, extend='t')
        # Suspend running subjob[1], verify
        # subjob[2] start running
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid[0])
        self.server.sigjob(jobid=subjid[0], signal="suspend")
        self.server.expect(JOB, {'job_state': 'S'}, id=subjid[0])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid[1])
        # Resume subjob[1] and verify subjob[1] should
        # run once resources are available
        self.server.sigjob(subjid[0], 'resume')
        self.server.expect(JOB, {'job_state': 'S'}, id=subjid[0])
        self.server.delete(subjid[1])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid[2])
        self.server.delete([subjid[2], subjid[3], subjid[4]])
        self.server.expect(JOB, {'job_state': 'R'}, id=subjid[0])
        self.server.expect(JOB, {'job_state': 'F',  'substate': '92',
                                 'queue': rid_q}, id=subjid[0], extend='x')

        self.server.expect(JOB, {'job_state': 'F',  'queue': rid_q},
                           id=jid, extend='x')

    @skipOnCpuSet
    def test_multiple_job_array_within_standing_reservation(self):
        """
        Test multiple job-array submitted to a standing reservations
        and subjobs exceed walltime to run within instance of
        reservation
        """
        self.common_steps()
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'

        # Submit a standing reservation to occur every other minute for a
        # total count of 2
        start = int(time.time()) + 10
        end = start + 30
        a = {'Resource_List.select': '1:ncpus=4',
             ATTR_resv_rrule: 'FREQ=MINUTELY;INTERVAL=2;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             }
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        rid_q = rid.split(".")[0]
        # Submit 3 job-array within reservation with sleep time longer
        # than instance duration
        subjid = []
        jids = []
        for i in range(3):
            j = Job(TEST_USER, attrs={ATTR_q: rid_q, ATTR_J: '1-2'})
            j.set_sleep_time(100)
            pjid = self.server.submit(j)
            jids.append(pjid)
            for subid in range(1, 3):
                subjid.append(j.create_subjob_id(pjid, subid))
        # Wait for first instance of reservation to be start
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid, interval=1)
        self.server.expect(RESV, {'reserve_index': 1}, id=rid)
        self.server.expect(JOB, {'job_state': 'B'}, jids[0])
        self.server.expect(JOB, {'job_state=R': 2}, count=True,
                           id=jids[0], extend='t')
        self.server.expect(JOB, {'job_state=R': 2}, count=True,
                           id=jids[1], extend='t')
        self.server.expect(JOB, {'job_state=Q': 3}, count=True,
                           id=jids[2], extend='t')
        # At end of first instance of reservation ,verify running subjobs
        # should be finished
        self.logger.info(
            'Waiting 20 sec job-array 1 and 2 to be finished')
        self.server.expect(JOB, {'job_state=F': 3}, extend='xt',
                           offset=20, id=jids[0])
        self.server.expect(JOB, {'job_state=F': 3}, extend='xt',
                           id=jids[1])

        # Wait for standing reservation second instance to confirmed
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        # Check for queued jobs in second instance of reservation
        self.server.expect(JOB, {'job_state': 'Q',
                                 'comment': (MATCH_RE, 'Queue not started')},
                           id=jids[2])
        self.logger.info(
            'Waiting 55 sec for second instance of reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid, offset=55, interval=1)
        self.server.expect(RESV, {'reserve_index': 2}, id=rid)
        # Check for queued jobs should be running
        self.server.expect(JOB, {'job_state=R': 2}, extend='xt',
                           id=jids[2])

        # Check for running jobs in second instance should finished
        self.logger.info(
            'Waiting 30 sec for second instance of reservation to finished')
        self.server.expect(JOB, {'job_state=F': 3}, extend='xt',
                           offset=30, id=jids[2])

        # Wait for reservation to be finished
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=end, interval=2)
        for job in jids:
            self.server.expect(JOB, 'queue', op=UNSET, id=job)

        # At end of reservation,verify running subjobs from job-array 3
        # terminated
        self.server.expect(JOB, {'job_state': 'F', 'substate': '91'},
                           extend='x', id=jids[2])
        self.server.expect(JOB, {'job_state': 'F', 'substate': '91',
                                 'queue': rid_q}, extend='x',
                           attrop=PTL_AND, id=subjid[5])

        # Check for subjobs status of job-array 1 and 2
        # as all subjobs from job-array 1 and 2 exceed walltime of
        # reservation,so they will not complete running within an instance
        # so the substate of these subjobs should be 93
        job_list = subjid
        job_list.pop()
        job_list.pop()
        for subjob in job_list:
            self.server.expect(JOB, {'job_state': 'F', 'substate': '93',
                                     'queue': rid_q}, extend='xt',
                               attrop=PTL_AND, id=subjob)

    def common_config(self):
        """
        This function contains common steps for test
        "test_ASAP_resv_with_multivnode_job_array" and
        "test_standing_resv_with_multivnode_job_array"
        """
        vn_attrs = {ATTR_rescavail + '.ncpus': 4}
        self.server.create_vnodes("vnode1", vn_attrs, 2,
                                  self.mom, fname="vnodedef1")
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

    def test_ASAP_resv_with_multivnode_job_array(self):
        """
        Test 2 multivnode job array converted to ASAP resv
        having same start time run as per resources available and
        doesn't crashes PBS daemons on completion of reservation.
        """
        self.common_config()
        # Submit job array such that it consumes all the resources
        # on both vnodes
        attrs = {ATTR_J: '1-5',
                 'Resource_List.select': '2:ncpus=1',
                 'Resource_List.walltime': '10',
                 'Resource_List.place': 'vscatter'}
        j = Job(PBSROOT_USER)
        j.set_sleep_time(10)
        j.set_attributes(attrs)
        jid = self.server.submit(j)
        subjid = []
        for i in range(1, 6):
            subjid.append(j.create_subjob_id(jid, i))
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           extend='t', id=jid)
        self.server.expect(JOB, {'job_state=Q': 1}, count=True,
                           extend='t', id=jid)
        # Submit another job array and verify that all the subjobs in
        # it are in Q state
        j1 = Job(PBSROOT_USER)
        j1.set_sleep_time(10)
        j1.set_attributes(attrs)
        jid2 = self.server.submit(j1)
        subjid2 = []
        for i in range(1, 6):
            subjid2.append(j.create_subjob_id(jid2, i))
        self.server.expect(JOB, {'job_state=Q': 6}, count=True,
                           extend='t', id=jid2)
        # Convert 2 job array's into ASAP reservation
        now = int(time.time())
        rid1 = self.submit_asap_reservation(PBSROOT_USER, jid)
        rid1_q = rid1.split('.')[0]
        rid2 = self.submit_asap_reservation(PBSROOT_USER, jid2)
        rid2_q = rid2.split('.')[0]
        # Check both the reservation starts running
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid1, offset=10)
        self.server.expect(RESV, a, id=rid2)
        # Verify subjobs initially in R state completed
        self.server.expect(JOB, {'job_state=X': 4}, count=True,
                           extend='xt', id=jid)
        # Verify subjobs in Q state starts running as soon as resv starts
        self.server.expect(JOB, {'job_state': 'R'}, subjid[4])
        self.server.expect(JOB, {'job_state': 'R'}, subjid2[0])
        # Wait for reservation to end
        resv_queue = [rid1_q, rid2_q]
        for queue in resv_queue:
            msg = "Que;" + queue + ";deleted at request of pbs_server@"
            self.server.log_match(msg, starttime=now, interval=10)
        # Verify all the jobs are deleted once resv ends
        jids = [jid, jid2]
        for job in jids:
            self.server.expect(JOB, 'queue', op=UNSET, id=job)
        exp_attrib = {'job_state': 'F', 'substate': '91'}
        jobs = [subjid[1], subjid2[1]]
        for jid in jobs:
            self.server.expect(JOB, exp_attrib, id=jid, extend='x')
        # Verify all the PBS daemons are up and running upon resv completion
        self.server.isUp()
        self.mom.isUp()
        self.scheduler.isUp()

    def test_standing_resv_with_multivnode_job_array(self):
        """
        Test multivnode job array with standing reservation. Also
        verify that subjobs with walltime exceeding the resv duration
        are deleted once reservation ends
        """
        self.common_config()
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'

        start = int(time.time()) + 10
        end = int(time.time()) + 61
        a = {'Resource_List.select': '2:ncpus=2',
             ATTR_resv_rrule: 'FREQ=MINUTELY;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             'Resource_List.place': 'vscatter'}
        r = Reservation(PBSROOT_USER, attrs=a)
        rid = self.server.submit(r)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        resv_queue = rid.split(".")[0]
        # Submit job requesting more walltime than the resv duration
        attrs = {ATTR_q: resv_queue, ATTR_J: '1-5',
                 'Resource_List.select': '2:ncpus=1',
                 'Resource_List.place': 'vscatter'}
        j = Job(PBSROOT_USER)
        j.set_attributes(attrs)
        jid = self.server.submit(j)
        subjid = []
        for i in range(1, 6):
            subjid.append(j.create_subjob_id(jid, i))
        exp_attrib = {'job_state': 'Q',
                      'comment': (MATCH_RE, 'Queue not started')}
        self.server.expect(JOB, exp_attrib, id=subjid[0])
        # Wait for first instance of standing resv to start
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(JOB, {'job_state': 'B'}, id=jid)
        self.server.expect(JOB, {'job_state=R': 2}, count=True,
                           extend='t', id=jid)
        # Wait for second instance of standing resv to start
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'), 'reserve_index': 2}
        self.server.expect(RESV, a, offset=60, id=rid)
        # Verify running subjobs were terminated after the first
        # instance of standing resv
        jobs = [subjid[0], subjid[1]]
        attrib = {'job_state': 'X', 'substate': '93'}
        for jobid in jobs:
            self.server.expect(JOB, attrib, id=jobid)
        self.server.expect(JOB, {'job_state=R': 2}, count=True,
                           extend='t', id=jid)
        self.server.expect(JOB, {'job_state': 'Q'}, id=subjid[4])
        # Wait for reservation to end
        self.server.log_match(resv_queue + ";deleted at request of pbs_server",
                              id=rid, interval=10)
        # Verify all the jobs are deleted once resv ends
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)
        self.server.expect(JOB, {'job_state=F': 6}, count=True,
                           extend='xt', id=jid)

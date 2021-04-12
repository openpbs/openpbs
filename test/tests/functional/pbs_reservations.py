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


import time
from datetime import datetime as dt

from tests.functional import *


@tags('reservations')
class TestReservations(TestFunctional):
    """
    Various tests to verify behavior of PBS scheduler in handling
    reservations
    """

    def get_tz(self):
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        return tzone

    def dst_changes(self, start, end):
        """
        Returns true if it detects that DST changes between start and end
        """
        s = dt.fromtimestamp(start)
        e = dt.fromtimestamp(end)
        s_tz = s.astimezone().strftime("%Z")
        e_tz = e.astimezone().strftime("%Z")
        if s_tz != e_tz:
            return True
        return False

    def submit_reservation(self, select, start, end, user, rrule=None,
                           place='free', extra_attrs=None):
        """
        helper method to submit a reservation
        """
        a = {'Resource_List.select': select,
             'Resource_List.place': place,
             'reserve_start': start,
             }

        if self.dst_changes(start, end) is True:
            a['reserve_duration'] = int(end - start)
        else:
            a['reserve_end'] = end

        if rrule is not None:
            tzone = self.get_tz()
            a.update({ATTR_resv_rrule: rrule, ATTR_resv_timezone: tzone})

        if extra_attrs:
            a.update(extra_attrs)
        r = Reservation(user, a)

        return self.server.submit(r)

    def submit_asap_reservation(self, user, jid, extra_attrs=None):
        """
        Helper method to submit an ASAP reservation
        """
        a = {ATTR_convert: jid}
        if extra_attrs:
            a.update(extra_attrs)
        r = Reservation(user, a)

        # PTL's Reservation class sets the default ATTR_resv_start
        # and ATTR_resv_end.
        # But pbs_rsub: -Wqmove is not compatible with -R or -E option
        # So, unset these attributes from the reservation instance.
        r.unset_attributes(['reserve_start', 'reserve_end'])

        return self.server.submit(r)

    def submit_job(self, set_attrib=None, sleep=100, job_running=False):
        """
        This function submits job
        :param set_attrib: Job attributes to set
        :type set_attrib: Dictionary
        """
        j = Job(TEST_USER)
        if set_attrib is not None:
            j.set_attributes(set_attrib)
        j.set_sleep_time(sleep)
        jid = self.server.submit(j)
        self.logger.info("Job submitted successfully-%s" % jid)
        job_node = None
        if job_running:
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
            get_exec_vnode = self.server.status(JOB, 'exec_vnode', id=jid)[0]
            job_node = get_exec_vnode['exec_vnode']
        return (jid, job_node)

    @staticmethod
    def cust_attr(name, totnodes, numnode, attrib):
        a = {}
        if numnode % 2 == 0:
            a['resources_available.color'] = 'red'
        else:
            a['resources_available.color'] = 'blue'
        return {**attrib, **a}

    def degraded_resv_reconfirm(self, start, end, rrule=None, run=False):
        """
        Test that a degraded reservation gets reconfirmed
        """
        a = {'reserve_retry_time': 5}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'type': 'string', 'flag': 'h'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='color')
        self.scheduler.add_resource('color')

        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, num=5,
                               attrfunc=self.cust_attr)

        now = int(time.time())

        rid = self.submit_reservation(user=TEST_USER,
                                      select='2:ncpus=1:color=red',
                                      rrule=rrule, start=now + start,
                                      end=now + end)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node_list = self.server.reservations[rid].get_vnodes()
        resv_node = resv_node_list[0]

        if run:
            resv_state = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            self.logger.info('Sleeping until reservation starts')
            offset = start - int(time.time())
            self.server.expect(RESV, resv_state, id=rid,
                               offset=offset, interval=1)
        else:
            resv_state = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}

        a = {'state': 'offline'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=resv_node)

        a = {'reserve_substate': 10}
        a.update(resv_state)
        self.server.expect(RESV, a, id=rid)

        a = {'resources_available.color': 'red'}
        free_nodes = self.server.filter(NODE, a)
        nodes = list(free_nodes.values())[0]

        other_node = [x for x in nodes if x not in resv_node_list][0]

        if run:
            a = {'reserve_substate': 5}
        else:
            a = {'reserve_substate': 2}

        self.server.expect(RESV, a, id=rid, interval=1)

        self.server.status(RESV)
        self.assertEquals(set(self.server.reservations[rid].get_vnodes()),
                          {resv_node_list[1], other_node},
                          "Node not replaced correctly")
        if run:
            a = {'resources_assigned.ncpus': 0}
            self.server.expect(NODE, a, id=resv_node)
            a = {'resources_assigned.ncpus=1': 2}
            self.server.expect(NODE, a)

    def degraded_resv_failed_reconfirm(self, start, end, rrule=None,
                                       run=False, resume=False):
        """
        Test that reservations do not get reconfirmed if there is no place
        to put them.
        """
        a = {'reserve_retry_time': 5}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, num=2)

        now = time.time()

        rid = self.submit_reservation(user=TEST_USER, select='1:ncpus=1',
                                      rrule=rrule, start=now + start,
                                      end=now + end)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '1:00:00'}
        j = Job(attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.status(JOB, 'exec_vnode', id=jid)
        job_node = j.get_vnodes()[0]

        msg = 'Job and Resv share node'
        self.assertNotEqual(resv_node, job_node, msg)

        if run:
            resv_state = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            self.logger.info('Sleeping until reservation starts')
            offset = start - int(time.time())
            self.server.expect(RESV, resv_state, id=rid,
                               offset=offset, interval=1)
        else:
            resv_state = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}

        a = {'state': 'offline'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=resv_node)

        a = {'reserve_substate': 10}
        a.update(resv_state)
        self.server.expect(RESV, a, id=rid)

        self.scheduler.log_match(rid + ';Reservation is in degraded mode',
                                 starttime=now, interval=1)

        self.server.expect(RESV, a, id=rid)

        self.server.expect(RESV, {'resv_nodes':
                                  (MATCH_RE, re.escape(resv_node))}, id=rid)

        if rrule and run:
            a = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10'),
                 'reserve_substate': 10}
            t = end - int(time.time())
            self.logger.info('Sleeping until reservation ends')
            self.server.expect(RESV, a, id=rid, offset=t)

        self.server.manager(MGR_CMD_SET, NODE, {'state': (DECR, 'offline')},
                            id=resv_node)
        # If run and rrule are true, we waited until the occurrence
        # finished and the reservation is no longer running otherwise
        # the reservation is still running.
        if run:
            if rrule:
                resv_state = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                              'reserve_substate': 2}
            else:
                resv_state = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'),
                              'reserve_substate': 5}
        else:
            resv_state = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                          'reserve_substate': 2}

        self.server.expect(RESV, resv_state, id=rid)

    def test_degraded_standing_reservations(self):
        """
        Verify that degraded standing reservations are reconfirmed
        on other nodes
        """
        self.degraded_resv_reconfirm(start=125, end=625,
                                     rrule='freq=HOURLY;count=5')

    def test_degraded_advance_reservations(self):
        """
        Verify that degraded advance reservations are reconfirmed
        on other nodes
        """
        self.degraded_resv_reconfirm(start=125, end=625)

    def test_degraded_standing_running_reservations(self):
        """
        Verify that degraded standing reservations are reconfirmed
        on other nodes
        """
        self.degraded_resv_reconfirm(start=25, end=625,
                                     rrule='freq=HOURLY;count=5', run=True)

    def test_degraded_advance_running_reservations(self):
        """
        Verify that degraded advance reservations are not reconfirmed
        on other nodes if no space is available
        """
        self.degraded_resv_reconfirm(
            start=25, end=625, run=True)

    def test_degraded_standing_reservations_fail(self):
        """
        Verify that degraded standing reservations are not
        reconfirmed on other nodes if there is no space available
        """
        self.degraded_resv_failed_reconfirm(start=120, end=720,
                                            rrule='freq=HOURLY;count=5')

    def test_degraded_advance_reservations_fail(self):
        """
        Verify that advance reservations are not reconfirmed if there
        is no space available
        """
        self.degraded_resv_failed_reconfirm(start=120, end=720)

    def test_degraded_standing_running_reservations_fail(self):
        """
        Verify that degraded running standing reservations are not
        reconfirmed on other nodes if there is no space available
        """
        self.degraded_resv_failed_reconfirm(start=25, end=55,
                                            rrule='freq=HOURLY;count=5',
                                            run=True)

    def test_degraded_advance_running_reservations_fail(self):
        """
        Verify that advance running reservations are not reconfirmed if there
        is no space available
        """
        self.degraded_resv_failed_reconfirm(
            start=25, end=625, run=True)

    def test_degraded_advanced_reservation_superchunk(self):
        """
        Verify that an advanced reservation requesting a superchunk is
        correctly reconfirmed on other nodes
        """
        retry = 15
        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, num=6)
        self.server.manager(MGR_CMD_SET, SERVER, {'reserve_retry_time': retry})

        now = int(time.time())
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1+1:ncpus=3',
                                      start=now + 60,
                                      end=now + 240)

        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')}, id=rid)
        st = self.server.status(RESV, 'resv_nodes', id=rid)[0]
        nds1 = st['resv_nodes']
        # Should have 4 nodes.  Nodes 2-4 are the superchunk.  Choose the
        # middle node to avoid the '(' and ')' of the superchunk.
        sp = nds1.split('+')
        sn = sp[2].split(':')[0]

        # Keep the first chunk's node around to confirm it is still the same
        sc = sp[0]

        t = int(time.time())
        self.server.manager(MGR_CMD_SET, NODE, {'state': 'offline'}, id=sn)
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_DEGRADED|10')}, id=rid)

        retry_time = t + retry
        offset = retry_time - int(time.time())
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')},
                           id=rid, offset=offset)
        st = self.server.status(RESV, 'resv_nodes', id=rid)[0]
        nds2 = st['resv_nodes']
        self.assertEqual(len(sp), len(nds2.split('+')))
        self.assertNotEqual(nds1, nds2)
        self.assertEquals(sc, nds1.split('+')[0])

    def test_degraded_running_only_replace(self):
        """
        Test that when a running degraded reservation is reconfirmed,
        make sure that only the nodes that unavailable are replaced
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'reserve_retry_time': 15})

        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, 5)

        # Submit two jobs to take up nodes 0 and 1. This forces the reservation
        # onto nodes 3 and 4. The idea is to delete the two jobs and see
        # if the reservation shifts onto nodes 0 and 1 after the reconfirm
        j1 = Job(attrs={'Resource_List.select': '1:ncpus=1'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        j2 = Job(attrs={'Resource_List.select': '1:ncpus=1'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        now = int(time.time())
        start = now + 20
        rid = self.submit_reservation(user=TEST_USER,
                                      select='2:ncpus=1',
                                      start=start,
                                      end=start + 60)
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')}, id=rid)
        resv_queue = rid.split('.')[0]
        a = {'Resource_List.select': '1:ncpus=1', 'queue': resv_queue}
        j3 = Job(attrs=a)
        jid3 = self.server.submit(j3)

        self.logger.info('Sleeping until reservation starts')
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
                           id=rid, offset=start - int(time.time()))
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        self.server.delete(jid1, wait=True)
        self.server.delete(jid2, wait=True)
        self.server.status(RESV)
        rnodes = self.server.reservations[rid].get_vnodes()
        self.server.status(JOB)
        jnode = j3.get_vnodes()[0]
        other_node = rnodes[rnodes[0] == jnode]
        self.server.manager(MGR_CMD_SET, NODE, {
                            'state': (INCR, 'offline')}, id=other_node)
        self.server.expect(RESV, {'reserve_substate': 10}, id=rid)
        self.logger.info('Waiting until reconfirmation')
        self.server.expect(RESV, {'reserve_substate': 5}, id=rid, offset=7)
        self.server.status(RESV)
        rnodes2 = self.server.reservations[rid].get_vnodes()
        self.assertIn(jnode, rnodes2, 'Reservation not on job node')

    def test_standing_reservation_occurrence_two_not_degraded(self):
        """
        Test that when a standing reservation's occurrence 1 is on an offline
        vnode and occurrence 2 is not, that when the first occurrence finishes
        the reservation is back in the confirmed state
        """

        a = {'reserve_retry_time': 15}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, num=2)

        start_time = time.time()
        now = int(start_time)
        rid1 = self.submit_reservation(user=TEST_USER, select='1:ncpus=1',
                                       start=now + 3600, end=now + 7200)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid1)

        start = now + 25
        end = now + 55
        rid2 = self.submit_reservation(user=TEST_USER, select='1:ncpus=1',
                                       start=start, end=end,
                                       rrule='freq=HOURLY;count=5')
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid2)

        self.server.status(RESV, 'resv_nodes')
        resv_node = self.server.reservations[rid1].get_vnodes()[0]
        resv_node2 = self.server.reservations[rid2].get_vnodes()[0]

        msg = 'Reservations not on the same vnode'
        self.assertEqual(resv_node, resv_node2, msg)

        J = Job(attrs={'Resource_List.walltime': 1800})
        jid = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.manager(MGR_CMD_SET, NODE, {'state': 'offline'}, resv_node)

        self.logger.info('Sleeping until retry timer fires')
        time.sleep(15)
        # Can't reconfirm rid1 because rid2's second occurrence should be
        # on node 2 at that time.
        self.scheduler.log_match(rid1 + ';Reservation is in degraded mode',
                                 starttime=start_time, interval=1)
        # Can't reconfirm rid2 because the job is running on node 2.
        self.scheduler.log_match(rid2 + ';Reservation is in degraded mode',
                                 starttime=start_time, interval=1)

        self.logger.info('Sleeping until standing reservation runs')
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid2, offset=start - int(time.time()))

        self.logger.info('Sleeping until occurrence finishes')
        # occurrence 2 is not on the offlined node.  It should be confirmed
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid2, offset=end - int(time.time()))

    def test_degraded_reservation_reconfirm_running_job(self):
        """
        Test that a reservation isn't reconfirmed if there is a running job
        on an node that is offline until the job finishes.
        """
        a = {'reserve_retry_time': 5}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, num=2)

        now = int(time.time())
        start = now + 25
        rid = self.submit_reservation(select='1:ncpus=1', user=TEST_USER,
                                      start=start, end=now + 625)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)
        resv_queue = rid.split('.')[0]

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]

        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: resv_queue}
        J = Job(attrs=a)
        jid = self.server.submit(J)

        self.logger.info('Sleeping until reservation runs')
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
                           offset=start - int(time.time()), id=rid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.manager(MGR_CMD_SET, NODE, {'state': 'offline'},
                            id=resv_node)
        self.server.expect(RESV, {'reserve_substate': 10}, id=rid)
        self.scheduler.log_match(rid + ';PBS Failed to confirm resv: '
                                 'Reservation has running jobs in it',
                                 interval=1)

        self.server.delete(jid)

        self.server.expect(RESV, {'reserve_substate': 5}, id=rid)

    def test_not_honoring_resvs(self):
        """
        PBS schedules jobs on nodes without accounting
        for the reservation on the node
        """

        a = {'resources_available.ncpus': 4}
        self.mom.create_vnodes(a, 1, usenatvnode=True)

        now = int(time.time())
        start1 = now + 15
        end1 = now + 25
        start2 = now + 600
        end2 = now + 7200

        r1id = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       start=start1,
                                       end=end1)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, r1id)

        r2id = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=4',
                                       start=start2,
                                       end=end2)
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

        self.logger.info('Sleeping till Resv 1 ends')
        a = {'reserve_state': (MATCH_RE, "RESV_BEING_DELETED|7")}
        off = end1 - int(time.time())
        self.server.expect(RESV, a, id=r1id, interval=1, offset=off)

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
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=2',
                                      start=now + 10,
                                      end=now + 30)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, rid)

        attr = {'Resource_List.walltime': '00:00:20'}
        j = Job(TEST_USER, attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'Q'},
                           id=jid)
        msg = "Job would conflict with reservation or top job"
        self.server.expect(
            JOB, {ATTR_comment: "Not Running: " + msg}, id=jid)
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
        rid = self.submit_reservation('1:ncpus=1', now + 30, now + 3600,
                                      user=TEST_USER, place='excl')

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        exp_attr['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, exp_attr, id=rid, offset=30)

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_vnode = self.server.reservations[rid].get_vnodes()[0]
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_vnode)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl', 'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        n = self.server.status(NODE, id=resv_vnode)
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
        rid1 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       place='excl',
                                       start=now + 30,
                                       end=now + 3600)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       place='excl',
                                       start=now + 7200,
                                       end=now + 10800)

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
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      place='excl',
                                      start=now + 30,
                                      end=now + 300)

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
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       start=now + 360,
                                       end=now + 3600)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid2)

    def test_future_resv_conflicts_running_job(self):
        """
        Test if a running exclusive job without walltime will deny the future
        resv from getting confirmed.
        """

        vnode_val = None
        if self.mom.is_cpuset_mom():
            vnode_val = '1:ncpus=1:vnode=' + self.server.status(NODE)[1]['id']

        now = int(time.time())
        # Submit a job but do not specify walltime, scheduler will consider
        # the walltime of such a job to be 5 years
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl'}
        if self.mom.is_cpuset_mom():
            a['Resource_List.select'] = vnode_val

        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit a reservation that will start after the job starts running
        rid1 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       start=now + 360,
                                       end=now + 3600)

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
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      place='excl',
                                      start=now + 30,
                                      end=now + 300)

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
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       start=now + 630,
                                       end=now + 3600)

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
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      place='excl',
                                      start=now + 30,
                                      end=now + 300)

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
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       start=now + 330,
                                       end=now + 3600)

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
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      start=now + 30,
                                      end=now + 300)

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
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       start=now + 330,
                                       end=now + 3600)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid2)

        self.server.delete(rid2)

        # Submit another exclusive reservation that will start after
        # previous reservation ends but before job's walltime is over.
        rid3 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       place='excl',
                                       start=now + 330,
                                       end=now + 3600)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid3)

    def test_resv_excl_with_jobs(self):
        """
        Test to see that exclusive reservations in the near term do not
        interfere with longer term reservations with jobs inside
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        now = int(time.time())
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      place='excl',
                                      start=now + 30,
                                      end=now + 300)

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
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       place='excl',
                                       start=now + 360,
                                       end=now + 3600)

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
        a = {'Resource_List.select': '1:ncpus=1:vnode=' +
             self.mom.shortname}
        if self.mom.is_cpuset_mom():
            vnode_val = '1:ncpus=1:vnode=' + self.server.status(NODE)[1]['id']
            a['Resource_List.select'] = vnode_val

        rid = self.submit_reservation(user=TEST_USER,
                                      select=a['Resource_List.select'],
                                      place='excl',
                                      start=start,
                                      end=start + 3600)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.server.restart()

        sleep_time = start - int(time.time())

        self.logger.info('Waiting %d seconds till resv starts' % sleep_time)
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid, offset=sleep_time)

        mom_name = self.mom.shortname
        if self.mom.is_cpuset_mom():
            mom_name = self.server.status(NODE)[1]['id']
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=mom_name)

    def test_multiple_asap_resv(self):
        """
        Test that multiple ASAP reservations are scheduled one after another
        """
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 1},
                            id=self.mom.shortname)

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
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       place='excl',
                                       start=now + 3600,
                                       end=now + 3605)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid2)

        # Submit a long term standing reservation with exclusive node
        # placement when rid1 is running
        # This reservation should also be confirmed
        now = int(time.time())
        rid3 = self.submit_reservation(user=TEST_USER,
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
        rid1 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       place='excl',
                                       start=now + 360,
                                       end=now + 365)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        # Submit a long term standing reservation with exclusive node
        now = int(time.time())
        rid2 = self.submit_reservation(user=TEST_USER,
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
        rid3 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=1',
                                       place='excl',
                                       start=now + 3600,
                                       end=now + 3605)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid3)

    def test_multi_vnode_excl_advance_resvs(self):
        """
        Test if long term exclusive reservations do not interfere
        with current reservations on a multi-vnoded host
        """
        a = {'resources_available.ncpus': 4}
        self.mom.create_vnodes(a, num=3)

        # Submit a long term standing reservation with
        # exclusive nodes.
        now = int(time.time())
        rid1 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=9',
                                       place='excl',
                                       rrule='FREQ=HOURLY;COUNT=3',
                                       start=now + 7200,
                                       end=now + 7205)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid1)

        # Submit a long term advance reservation with exclusive node
        now = int(time.time())
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=10',
                                       place='excl',
                                       start=now + 3600,
                                       end=now + 3605)
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid2)

        # Submit a short term reservation requesting all the nodes
        # exclusively
        now = int(time.time())
        rid3 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=12',
                                       place='excl',
                                       start=now + 20,
                                       end=now + 100)
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
        self.mom.create_vnodes(a, num=3)

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
        rid2 = self.submit_reservation(user=TEST_USER,
                                       select='1:ncpus=12',
                                       place='excl',
                                       start=now + 3600,
                                       end=now + 3605)
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
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=10',
                                      start=now + 360,
                                      end=now + 365)
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
        start_time = time.time()
        resv_start_time = int(start_time) + 20
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      start=resv_start_time,
                                      end=resv_start_time + 100)
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        a = {ATTR_q: rid_q, ATTR_J: '1-4'}
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(20)
        jid2 = self.server.submit(j2)
        subjid = []
        for i in range(1, 5):
            subjid.append(j.create_subjob_id(jid2, i))

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        expect_offset = resv_start_time - int(time.time())
        self.server.expect(RESV, a, id=rid, offset=expect_offset)
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
        self.server.log_match(msg, starttime=start_time, interval=10)
        # Check status of the sub-job using qstat -fx once job completes
        self.server.expect(JOB, {'job_state': 'F', 'Exit_status': '271'},
                           extend='x', attrop=PTL_AND, id=subjid[0])
        self.server.expect(JOB, {'job_state': 'F', 'Exit_status': '0'},
                           extend='x', attrop=PTL_AND, id=subjid[3])

        # Submit a advance reservation (R2) and an array job to the reservation
        # once reservation confirmed
        start_time = time.time()
        resv_start_time = int(start_time) + 20
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=4',
                                      start=resv_start_time,
                                      end=resv_start_time + 160)
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
        expect_offset = resv_start_time - int(time.time())
        self.server.expect(RESV, a, id=rid, offset=expect_offset)
        self.server.expect(JOB, {'job_state': 'B'}, jid2)
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           id=jid2, extend='t')
        # Submit another job-array with small sleep time than job j2
        a = {ATTR_q: rid_q, ATTR_J: '1-4'}
        j3 = Job(TEST_USER, attrs=a)
        j3.set_sleep_time(20)
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
        self.server.expect(JOB, {'job_state': 'B'}, jid3, offset=30,
                           interval=5, max_attempts=30)
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           id=jid3, extend='t')
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=start_time, interval=10)
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
        rid = self.submit_reservation(user=TEST_USER,
                                      select='2:ncpus=2',
                                      place='scatter',
                                      start=now + 30,
                                      end=now + 300)
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
        # Submit an advance reservation and an array job to the reservation
        # once reservation confirmed
        start_time = time.time()
        now = int(start_time)
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      start=now + 10,
                                      end=now + 40)
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
        self.server.log_match(msg, starttime=start_time, interval=10)
        # Check status of the parent-job using qstat -fx once reservation ends
        self.server.expect(JOB, {'job_state': 'F', 'substate': '91'},
                           extend='x', id=jid)

    def test_ASAP_resv_request_same_time(self):
        """
        Test two jobs converted in two ASAP reservation
        which request same walltime should run and finish as
        per available resources.
        Also to verify 2 ASAP reservations with same start
        time doesn't crashes PBS daemon.
        """
        self.common_steps()

        # Submit job j to consume all resources
        a = {'Resource_List.walltime': '10',
             'Resource_List.select': '1:ncpus=4'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        # Submit a job j2
        a = {'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': '10'}
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(10)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, jid2)

        # Convert j2 into an ASAP reservation
        now = time.time()
        rid1 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid2)
        rid1_q = rid1.split('.')[0]
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2"),
                    'reserve_duration': 10}
        self.server.expect(RESV, exp_attr, id=rid1)
        self.server.expect(
            JOB, {'job_state': 'Q', 'queue': rid1_q}, id=jid2)

        # Submit another job j3 same as j2
        j3 = Job(TEST_USER, attrs=a)
        j3.set_sleep_time(10)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {'job_state': 'Q'}, jid3)
        # Convert j3 into an ASAP reservation
        now2 = time.time()
        rid2 = self.submit_asap_reservation(user=TEST_USER,
                                            jid=jid3)
        rid2_q = rid2.split('.')[0]
        self.server.expect(RESV, exp_attr, id=rid2)
        self.server.expect(
            JOB, {'job_state': 'Q', 'queue': rid2_q}, id=jid3)

        # Wait for both  reservation to start
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid1)
        self.server.expect(RESV, exp_attr, id=rid2)
        # Verify j2 and j3 start running
        self.server.expect(
            JOB, {'job_state': 'R', 'queue': rid1_q}, id=jid2)
        self.server.expect(
            JOB, {'job_state': 'R', 'queue': rid2_q}, id=jid3)

        # Wait for reservations to be finish
        msg = "Que;" + rid1_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=5)
        msg = "Que;" + rid2_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now2)
        # Check status of the job using qstat -fx once reservation
        # ends
        jids = [jid2, jid3]
        for job in jids:
            self.server.expect(JOB, 'queue', op=UNSET, id=job)
            self.server.expect(JOB, {'job_state=F': 1}, count=True,
                               id=job, extend='x')

        # Verify pbs_server and pbs_scheduler is up
        if not self.server.isUp():
            self.fail("Server is not up")
        if not self.scheduler.isUp():
            self.fail("Scheduler is not up")

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
        start = time.time() + 10
        now = start + 25
        start = int(start)
        end = int(now)
        rid = self.submit_reservation(user=TEST_USER, select='1:ncpus=4',
                                      rrule='FREQ=MINUTELY;INTERVAL=2;COUNT=2',
                                      start=start, end=end)
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
        self.logger.info('Waiting until reservation runs')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid,
                           offset=start - int(time.time()))
        self.server.expect(RESV, {'reserve_index': 1}, id=rid)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        self.server.expect(JOB, {'job_state=R': 4}, count=True,
                           id=jid, extend='t')
        # Wait for standing reservation first instance to finished
        self.logger.info('Waiting for first occurrence to finish')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid,
                           offset=end - int(time.time()))
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)
        # Wait for standing reservation second instance to start
        offset = end - int(time.time()) + 120 - (end - start)
        self.logger.info(
            'Waiting for second occurrence of reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, exp_attr, id=rid, offset=offset, interval=1)
        self.server.expect(RESV, {'reserve_index': 2}, id=rid)
        # Wait for reservations to be finished
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=2)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

        # Check for subjob status for job-array
        # as all subjobs from job-array finished within the
        # instance so it should have substate=92
        for i in subjid:
            self.server.expect(JOB, {'job_state': 'F', 'substate': '92'},
                               extend='x', id=i)
        # Check for finished jobs by issuing the command qstat
        self.server.expect(JOB, {'job_state': 'F', 'substate': '92'},
                           extend='xt', id=jid)

        start = int(time.time()) + 25
        end = int(time.time()) + 3660
        rid = self.submit_reservation(user=TEST_USER, select='1:ncpus=1',
                                      rrule='FREQ=DAILY;COUNT=2',
                                      start=start, end=end)
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

    def test_multiple_job_array_within_standing_reservation(self):
        """
        Test multiple job-array submitted to a standing reservations
        and subjobs exceed walltime to run within instance of
        reservation
        """
        self.common_steps()

        # Submit a standing reservation to occur every other minute for a
        # total count of 2
        start = time.time() + 10
        now = start + 30
        start = int(start)
        end = int(now)
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=4',
                                      rrule='FREQ=MINUTELY;INTERVAL=2;COUNT=2',
                                      start=start,
                                      end=end)
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
        self.server.log_match(msg, starttime=now, interval=2)
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

    def test_delete_idle_resv_basic(self):
        """
        Test basic functionality of delete_idle_time.  Submit a reservation
        with delete_idle_time and no jobs.  Wait until the timer expires
        and see the reservation get deleted
        """
        now = int(time.time())
        start = now + 30
        idle_timer = 15
        extra = {'delete_idle_time': idle_timer}
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      start=start,
                                      end=now + 3600,
                                      extra_attrs=extra)

        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)
        self.logger.info('Sleeping until reservation starts')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        offset = start - int(time.time())
        self.server.expect(RESV, exp_attr, id=rid, offset=offset)

        self.logger.info('Sleeping until resv idle timer fires')
        self.server.expect(RESV, 'queue', op=UNSET, id=rid, offset=idle_timer)

    def test_delete_idle_resv_job_finish(self):
        """
        Test that an idle reservation is properly deleted after its only
        job runs and finishes
        """
        now = int(time.time())
        start = now + 30
        idle_timer = 15
        extra = {'delete_idle_time': idle_timer}
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      start=start,
                                      end=now + 3600,
                                      extra_attrs=extra)

        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)

        rid_q = rid.split('.', 1)[0]

        a = {'Resource_List.select': '1:ncpus=1', ATTR_q: rid_q}
        j = Job(attrs=a)
        j.set_sleep_time(5)
        jid = self.server.submit(j)

        self.logger.info('Sleeping until reservation starts')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        offset = start - int(time.time())
        self.server.expect(RESV, exp_attr, id=rid, offset=offset)

        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

        # Wait for idle resv timer to hit and delete reservation
        self.logger.info('Sleeping until resv idle timer fires')
        self.server.expect(RESV, 'queue', op=UNSET,
                           id=rid, offset=idle_timer + 5)

    def test_delete_idle_resv_job_delete(self):
        """
        Test that when a running job is deleted, the
        idle reservation is deleted
        """
        now = int(time.time())
        start = now + 30
        idle_timer = 15
        extra = {'delete_idle_time': idle_timer}
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      start=start,
                                      end=now + 3600,
                                      extra_attrs=extra)

        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)

        rid_q = rid.split('.', 1)[0]

        a = {'Resource_List.select': '1:ncpus=1', ATTR_q: rid_q}
        j = Job(attrs=a)
        jid = self.server.submit(j)

        self.logger.info('Sleeping until reservation starts')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        offset = start - int(time.time())
        self.server.expect(RESV, exp_attr, id=rid, offset=offset)

        self.server.delete(jid)

        self.logger.info('Sleeping until resv idle timer fires')
        self.server.expect(RESV, 'queue', op=UNSET, id=rid,
                           offset=idle_timer)

    def test_delete_idle_resv_job_standing(self):
        """
        Test that an idle standing reservation is properly deleted after its
        only job finishes
        """
        now = int(time.time())
        start = now + 30
        idle_timer = 15
        extra = {'delete_idle_time': idle_timer}
        rid = self.submit_reservation(
            user=TEST_USER, select='1:ncpus=1', rrule='freq=DAILY;COUNT=3',
            start=start, end=start + 1800, extra_attrs=extra)

        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp_attr, id=rid)

        rid_q = rid.split('.', 1)[0]

        a = {'Resource_List.select': '1:ncpus=1', ATTR_q: rid_q}
        j = Job(attrs=a)
        j.set_sleep_time(5)
        jid = self.server.submit(j)

        self.logger.info('Sleeping until reservation starts')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        offset = start - int(time.time())
        self.server.expect(RESV, exp_attr, id=rid, offset=offset)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        strf_str = '%a %b %d %T %Y'
        start_str = time.strftime(strf_str, time.localtime(start + 86400))

        self.logger.info('Sleeping until resv idle timer fires')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2"),
                    'reserve_start': start_str}
        self.server.expect(RESV, exp_attr, id=rid, offset=idle_timer + 5)

    def test_asap_delete_idle_resv_set(self):
        """
        Test that an ASAP reservation gets a default 10m idle timer if not set
        or keeps its idle timer if it is set
        """
        ncpus = self.server.status(NODE)[0]['resources_available.ncpus']

        a = {'Resource_List.select': '1:ncpus=' + ncpus,
             'Resource_List.walltime': 3600}

        vnode_val = None
        if self.mom.is_cpuset_mom():
            vnode_val = 'vnode=' + self.server.status(NODE)[1]['id']
            ncpus = self.server.status(NODE)[1]['resources_available.ncpus']
            a['Resource_List.select'] = vnode_val + ":ncpus=" + ncpus

        j1 = Job(attrs=a)
        jid1 = self.server.submit(j1)

        j2 = Job(attrs=a)
        jid2 = self.server.submit(j2)

        j3 = Job(attrs=a)
        jid3 = self.server.submit(j3)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)

        rid = self.submit_asap_reservation(TEST_USER, jid2)
        self.server.expect(RESV, {'delete_idle_time': '10:00'}, id=rid)

        extra_attrs = {'delete_idle_time': '5:00'}
        rid = self.submit_asap_reservation(TEST_USER, jid3, extra_attrs)
        self.server.expect(RESV, {'delete_idle_time': '5:00'}, id=rid)

    def common_config(self):
        """
        This function contains common steps for test
        "test_ASAP_resv_with_multivnode_job" and
        "test_standing_resv_with_multivnode_job_array"
        """
        vn_attrs = {ATTR_rescavail + '.ncpus': 4}
        self.mom.create_vnodes(vn_attrs, 2,
                               fname="vnodedef1")
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

    def test_ASAP_resv_with_multivnode_job(self):
        """
        Test 2 multivnode jobs converted to ASAP resv
        having same start time run as per resources available and
        doesn't crashes PBS daemons on completion of reservation.
        """
        self.common_config()
        # Submit job such that it consumes all the resources
        # on both vnodes
        attrs = {'Resource_List.select': '2:ncpus=4',
                 'Resource_List.walltime': '10',
                 'Resource_List.place': 'vscatter'}
        j = Job(PBSROOT_USER)
        j.set_sleep_time(10)
        j.set_attributes(attrs)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        # Submit 2 jobs and verify that both jobs are in Q state
        attrs = {'Resource_List.select': '2:ncpus=2',
                 'Resource_List.walltime': '10',
                 'Resource_List.place': 'vscatter'}
        j1 = Job(PBSROOT_USER)
        j1.set_sleep_time(10)
        j1.set_attributes(attrs)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        j2 = Job(PBSROOT_USER)
        j2.set_sleep_time(10)
        j2.set_attributes(attrs)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        # Convert 2 jobs into ASAP reservation
        now = time.time()
        rid1 = self.submit_asap_reservation(PBSROOT_USER, jid1)
        rid1_q = rid1.split('.')[0]
        rid2 = self.submit_asap_reservation(PBSROOT_USER, jid2)
        rid2_q = rid2.split('.')[0]
        # Check both the reservation starts running
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid1, offset=10)
        self.server.expect(RESV, a, id=rid2)
        # Wait for reservation to end
        resv_queue = [rid1_q, rid2_q]
        for queue in resv_queue:
            msg = "Que;" + queue + ";deleted at request of pbs_server@"
            self.server.log_match(msg, starttime=now, interval=10)
        # Verify all the jobs are deleted once resv ends
        jids = [jid1, jid2]
        for job in jids:
            self.server.expect(JOB, 'queue', op=UNSET, id=job)
        exp_attrib = {'job_state': 'F', 'substate': '91'}
        for jid in jids:
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

        start = int(time.time()) + 10
        end = int(time.time()) + 61
        rid = self.submit_reservation(user=PBSROOT_USER,
                                      select='2:ncpus=2',
                                      place='vscatter',
                                      rrule='FREQ=MINUTELY;COUNT=2',
                                      start=start,
                                      end=end)
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

    def test_standing_resv_resc_used(self):
        """
        Test that resources are released from the server when a
        standing reservation's occurrence finishes
        """

        self.server.expect(SERVER, {'resources_assigned.ncpus': 0})
        now = int(time.time())

        # submitting 25 seconds from now to allow some of the older testbed
        # systems time to process (discovered empirically)
        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=1',
                                      rrule='FREQ=MINUTELY;COUNT=2',
                                      start=now + 25,
                                      end=now + 35)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)
        self.server.expect(SERVER, {'resources_assigned.ncpus': 0})

        offset = now + 25 - int(time.time())
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid, offset=offset, interval=1)
        self.server.expect(SERVER, {'resources_assigned.ncpus': 1})

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid, offset=10, interval=1)
        self.server.expect(SERVER, {'resources_assigned.ncpus': 0})

        offset = now + 85 - int(time.time())
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid, offset=offset, interval=1)
        self.server.expect(SERVER, {'resources_assigned.ncpus': 1})

        self.server.expect(RESV, 'queue', op=UNSET, id=rid, offset=10)
        self.server.expect(SERVER, {'resources_assigned.ncpus': 0})

    def test_server_recover_resv_queue(self):
        """
        Test that PBS server can recover a reservation queue after a
        restart
        """

        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, num=2)
        now = int(time.time())
        rid = self.submit_reservation(user=TEST_USER, select='1:ncpus=1',
                                      start=now + 5, end=now + 300)

        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid)

        self.server.restart()
        self.server.expect(RESV, a, id=rid)

        resv_queue = rid.split('.')[0]
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: resv_queue}
        J = Job(attrs=a)
        jid = self.server.submit(J)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

    def test_resv_job_hard_walltime(self):
        """
        Test that a job with hard walltime will not conflict with
        reservtion if hard walltime is less that reservation start time.
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        now = int(time.time())

        rid = self.submit_reservation(user=TEST_USER,
                                      select='1:ncpus=4',
                                      start=now + 65,
                                      end=now + 240)
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')},
                           id=rid)
        a = {'Resource_List.ncpus': 4,
             'Resource_List.walltime': 50}
        J = Job(TEST_USER, attrs=a)
        jid = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_resv_reconfirm_holding_partial_nodes(self):
        """
        Test that scheduler is able to reconfirm a reservation when
        only some of the nodes reservation was running on goes down.
        Also make sure it hangs on to the node that was not down.
        """
        a = {'reserve_retry_time': 5}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 2}
        self.mom.create_vnodes(a, num=3)
        vn_list = ["%s[%d]" % (self.mom.shortname, i) for i in range(3)]

        now = int(time.time())
        sel = '1:ncpus=2+1:ncpus=1'
        rid = self.submit_reservation(user=TEST_USER, select=sel,
                                      start=now + 5, end=now + 300)

        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid)

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node_list = self.server.reservations[rid].get_vnodes()
        resv_node = resv_node_list[0]
        resv_node2 = resv_node_list[1]
        vn = [i for i in vn_list if i not in resv_node_list]

        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.manager(MGR_CMD_SET, NODE, {'state': 'offline'},
                            id=resv_node)
        self.server.expect(RESV, {'reserve_substate': 10}, id=rid)

        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        solution = '(' + vn[0] + ':ncpus=2)+(' + resv_node2 + ':ncpus=1)'
        a = {'reserve_substate': '5', 'resv_nodes': solution}
        self.server.expect(RESV, a, id=rid)

    def test_standing_resv_with_start_in_past(self):
        """
        Test that PBS accepts standing reservations with its start time in the
        past and end time in future. Check that PBS treats this kind of
        reservation as a reservation for the next day.
        """

        now = int(time.time())

        # we cannot use self.server.submit to submit the reservation
        # because we don't want to specify date in start and end options
        start = [" -R " + time.strftime('%H%M', time.localtime(now - 3600))]
        end = [" -E " + time.strftime('%H%M', time.localtime(now + 3600))]

        runcmd = [os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                               'pbs_rsub')]
        tz = ['PBS_TZID=' + self.get_tz()]
        rule = ["-r 'freq=WEEKLY;BYDAY=SU;COUNT=3'"]

        runcmd = tz + runcmd + start + end + rule
        ret = self.du.run_cmd(self.server.hostname, runcmd, as_script=True)
        self.assertEqual(ret['rc'], 0)
        rid = ret['out'][0].split()[0]

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)
        d = datetime.datetime.today()

        # weekday() returns the weekday's index. Monday to Sunday (0 to 6)
        # We calculate how far away is today than Sunday and move
        # the day ahead.
        n = d.weekday()
        # If today is Sunday, move 7 days ahead, else move "6 - weekday()"
        delta = (6 - n) if (6 - n > 0) else 7
        d += datetime.timedelta(days=delta)
        sunday = d.strftime('%a %b %d')
        start = time.strftime('%H:%M', time.localtime(now - 3600))
        sunday = sunday + " " + start

        stat = self.server.status(RESV, 'reserve_start', id=rid)
        self.assertIn(sunday, stat[0]['reserve_start'])

    def qmove_job_to_reserv(self, Res_Status, Res_substate, start, end):
        """
        Function to qmove job into reservation and verify job state
        in reservation
        """
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)
        jid1 = self.submit_job(job_running=True)

        # Submit a standing reservation to occur every other minute for a
        # total count of 2
        rid = self.submit_reservation(user=TEST_USER, select='1:ncpus=1',
                                      rrule='FREQ=MINUTELY;INTERVAL=2;COUNT=2',
                                      start=start, end=end)
        rid_q = rid.split('.')[0]
        exp_attr = {'reserve_state': Res_Status,
                    'reserve_substate': Res_substate}
        self.server.expect(RESV, exp_attr, id=rid, offset=5)
        self.server.holdjob(jid1[0])
        # qrerun the jobs
        self.server.rerunjob(jobid=jid1[0])
        self.server.expect(JOB, {'job_state': 'H'}, id=jid1[0])
        # qmove the job to reservation queue
        self.server.movejob(jid1[0], rid_q)
        self.server.expect(JOB, {'job_state': 'H', 'queue': rid_q},
                           id=jid1[0])
        self.server.rlsjob(jid1[0], 'u')
        if Res_Status == 'RESV_CONFIRMED':
            self.server.expect(JOB, {'job_state': 'Q'}, id=jid1[0])
            self.logger.info('Job %s is in Q as expected' % jid1[0])
        if Res_Status == 'RESV_RUNNING':
            self.server.expect(JOB, {'job_state': 'R'}, id=jid1[0])
            self.logger.info('Job %s is in R as expected' % jid1[0])
        jid2 = self.submit_job(job_running=True)
        self.server.delete([rid, jid2[0]], wait=True)

    def test_qmove_job_into_standing_reservation(self):
        """
        Test qmove job into standing reservation
        """
        # Test qmove of a job to a confirmed standing reservation instance
        self.qmove_job_to_reserv("RESV_CONFIRMED", 2, time.time() + 15,
                                 time.time() + 60)

        # Test qmove of a job to a running standing reservation instance
        self.qmove_job_to_reserv("RESV_RUNNING", 5, time.time() + 10,
                                 time.time() + 60)

    def test_shared_exclusive_job_not_in_same_rsv_vnode(self):
        """
        Test to verify user cannot submit an exclusive placement job
        in a free placement reservation, job submission would be denied
        because placement spec does not match.
        Also verify  shared and exclusive job in reservation should
        not overlap on same vnode.
        """
        vn_attrs = {ATTR_rescavail + '.ncpus': 4,
                    'sharing': 'default_excl'}
        self.mom.create_vnodes(vn_attrs, 6)

        # Submit a advance reservation (R1)
        rid = self.submit_reservation(select='3:ncpus=4', user=TEST_USER,
                                      start=time.time() + 10,
                                      end=time.time() + 1000)
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)
        a = {'Resource_List.select': '1:ncpus=2',
             'Resource_List.place': 'shared',
             'queue': rid_q}
        jid = self.submit_job(set_attrib=a, job_running=True)
        vn = self.mom.shortname
        self.assertEqual(jid[1], '(' + vn + '[0]:ncpus=2)')
        a = {'Resource_List.select': '1:ncpus=8',
             'Resource_List.place': 'excl',
             'queue': rid_q}
        _msg = "qsub: job and reservation have conflicting specification "
        _msg += "Resource_List.place"
        try:
            self.submit_job(set_attrib=a)
        except PbsSubmitError as e:
            self.assertEqual(
                e.msg[0], _msg, msg="Did not get expected qsub err message")
            self.logger.info("Got expected qsub err message as %s", e.msg[0])
        else:
            self.fail("Job got submitted")
        self.server.delete([jid[0], rid], wait=True)

        # Repeat above test with reservation have place=excl
        # Submit a advance reservation (R2)
        rid = self.submit_reservation(select='3:ncpus=4', user=TEST_USER,
                                      start=time.time() + 10,
                                      end=time.time() + 1000,
                                      place='excl')
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)
        a = {'Resource_List.select': '1:ncpus=2',
             'Resource_List.place': 'shared',
             'queue': rid_q}
        jid = self.submit_job(set_attrib=a, job_running=True)
        job1_node = jid[1]
        self.assertEqual(jid[1], '(' + vn + '[0]:ncpus=2)')
        a = {'Resource_List.select': '1:ncpus=8',
             'Resource_List.place': 'excl',
             'queue': rid_q}
        jid2 = self.submit_job(set_attrib=a, job_running=True)
        job2_node = jid2[1]
        errmsg = 'job1_node contain job_node2 value'
        self.assertEqual(
            jid2[1], '(' + vn + '[1]:ncpus=4+' + vn + '[2]:ncpus=4)')
        self.assertNotIn(job1_node, job2_node, errmsg)

    def test_clashing_reservations(self):
        """
        Test that when a standing reservation and advance reservation
        are submitted to start at the same time on the same set of
        resources, then the one that is submitted first wins and second
        is rejected.
        """

        self.common_config()

        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        start = int(time.time()) + 300
        end = int(time.time()) + 1200
        srid = self.submit_reservation(user=TEST_USER,
                                       select='2:ncpus=4',
                                       rrule='FREQ=DAILY;COUNT=2',
                                       start=start,
                                       end=end)

        arid = self.submit_reservation(user=TEST_USER,
                                       select='2:ncpus=4',
                                       start=start,
                                       end=end)
        self.scheduler.run_scheduling_cycle()
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')},
                           id=srid, max_attempts=1)
        self.server.log_match(arid + ";Reservation denied", id=arid,
                              max_attempts=1)

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
import time


class TestReservations(TestFunctional):

    """
    Various tests to verify behavior of PBS scheduler in handling
    reservations
    """

    def submit_standing_reservation(self, user, select, rrule, start, end):
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
             ATTR_resv_rrule: rrule,
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             }
        r = Reservation(user, a)

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
        nodes = free_nodes.values()[0]

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
                            expect=True, sudo=True)

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

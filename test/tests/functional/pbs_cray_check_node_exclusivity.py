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


@tags('cray', 'reservation')
class TestCheckNodeExclusivity(TestFunctional):

    """
    Test suite for reservation. This test Suite checks
    the exclusivity of node when a reservation asks for it.
    Adapted for Cray Configuration
    """
    ncpus = None
    vnode = None

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on a Cray")
        self.script = []
        self.script += ['echo Hello World\n']
        self.script += ['aprun -b -B /bin/sleep 10']

        TestFunctional.setUp(self)

    def submit_and_confirm_resv(self, a=None, index=None):
        """
        This is common function to submit reservation
        and verify reservation confirmed
        """
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        if index is not None:
            a['reserve_index'] = index
        self.server.expect(RESV, a, id=rid)
        return rid

    def get_vnode_ncpus_value(self):
        all_nodes = self.server.status(NODE)
        for n in all_nodes:
            if n['resources_available.vntype'] == 'cray_compute':
                self.ncpus = n['resources_available.ncpus']
                self.vnode = n['resources_available.vnode']
                break

    def test_node_state_with_adavance_resv(self):
        """
        Test node state will change when reservation
        asks for exclusivity.
        """
        # Submit a reservation with place=excl
        start_time = time.time()
        now = int(start_time)
        a = {'Resource_List.select': '1:ncpus=1:vntype=cray_compute',
             'Resource_List.place': 'excl', 'reserve_start': now + 30,
             'reserve_end': now + 60}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)
        self.server.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)

        self.logger.info('Waiting 20s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=20)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Wait for reservation to delete from server
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=start_time, interval=10)
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)

    def test_node_state_with_standing_resv(self):
        """
        Test node state will change when reservation
        asks for exclusivity.
        """
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        # Submit a standing reservation to occur every other minute for a
        # total count of 2
        start = time.time() + 20
        now = start + 20
        start = int(start)
        end = int(now)
        a = {'Resource_List.select': '1:ncpus=1:vntype=cray_compute',
             'Resource_List.place': 'excl',
             ATTR_resv_rrule: 'FREQ=MINUTELY;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             }
        rid = self.submit_and_confirm_resv(a, 1)
        rid_q = rid.split(".")[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)
        self.logger.info('Waiting 10s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5"),
             'reserve_index': 1}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Wait for standing reservation first instance to finished
        self.logger.info(
            'Waiting 20 sec for second instance of reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2"),
                    'reserve_index': 2}
        self.server.expect(RESV, exp_attr, id=rid, offset=20)
        # Node state of the nodes in resv_nodes should be free
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)
        # Wait for standing reservation second instance to start
        self.logger.info(
            'Waiting 40 sec for second instance of reservation to start')
        exp_attr = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5"),
                    'reserve_index': 2}
        self.server.expect(RESV, exp_attr, id=rid, offset=40, interval=1)
        # check the node state of the nodes in resv_nodes
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Wait for reservations to be finished
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=now, interval=2)
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)

    def test_job_outside_resv_not_allowed(self):
        """
        Test Job outside the reservation will not be allowed
        to run if reservation has place=excl.
        """
        # Submit a reservation with place=excl
        start_time = time.time()
        now = int(start_time)
        a = {'Resource_List.select': '1:ncpus=1:vntype=cray_compute',
             'Resource_List.place': 'excl', 'reserve_start': now + 20,
             'reserve_end': now + 30}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)
        self.logger.info('Waiting 20s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=20)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Submit a job outside the reservation requesting resv_nodes
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_q: 'workq', ATTR_l + '.select': '1:vnode=%s' % resv_node}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        comment = 'Not Running: Insufficient amount of resource: vnode'
        self.server.expect(
            JOB, {'job_state': 'Q', 'comment': comment}, id=jid1)
        # Wait for reservation to end and verify node state
        # changed as job-exclusive
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=start_time, interval=2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive'},
                           id=resv_node)

    def test_conflict_reservation_on_resv_exclusive_node(self):
        """
        Test no other reservation will get confirmed (in the duration)
        when a node has a exclusive reservation confirmed on it.
        Reservation2 is inside the duration of confirmed reservation
        requesting the same vnode in Reservation1.
        """
        # Submit a reservation with place=excl
        start_time = time.time()
        now = int(start_time)
        a = {'Resource_List.select': '1:ncpus=1:vntype=cray_compute',
             'Resource_List.place': 'excl', 'reserve_start': now + 20,
             'reserve_end': now + 60}
        rid = self.submit_and_confirm_resv(a)
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.logger.info('Waiting 20s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=20)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Submit another reservation requesting on vnode in resv_node
        a = {ATTR_l + '.select': '1:ncpus=1:vnode=%s' % resv_node,
             'reserve_start': now + 25,
             'reserve_end': now + 30}
        r = Reservation(TEST_USER, attrs=a)
        rid2 = self.server.submit(r)
        msg = "Resv;" + rid2 + ";Reservation denied"
        self.server.log_match(msg, starttime=start_time, interval=2)
        msg2 = "Resv;" + rid2 + ";reservation deleted"
        self.server.log_match(msg2, starttime=now, interval=2)
        msg3 = "Resv;" + rid2 + ";PBS Failed to confirm resv: Insufficient "
        msg3 += "amount of resource: vnode"
        self.scheduler.log_match(msg3, starttime=now, interval=2)

    def test_node_exclusivity_with_multinode_reservation(self):
        """
        Test Jobs run correctly in multinode reservation
        and accordingly update node exclusivity.
        """
        self.get_vnode_ncpus_value()
        # Submit a reservation with place=excl
        now = int(time.time())
        a = {ATTR_l + '.select': '2:ncpus=%d' % (int(self.ncpus)),
             'Resource_List.place': 'excl', 'reserve_start': now + 10,
             'reserve_end': now + 1600}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split(".")[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()
        self.logger.info('Waiting 10s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node[0])
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node[1])
        # Submit a job inside the reservation
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '1:ncpus=1',
             'Resource_List.place': 'shared'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive,resv-exclusive'},
                           id=resv_node[0])
        # Submit another job inside the reservation
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '2:ncpus=1',
             'Resource_List.place': 'shared'}
        j2 = Job(TEST_USER, attrs=a)
        j2.create_script(self.script)
        jid2 = self.server.submit(j2, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(NODE, {'state': 'job-exclusive,resv-exclusive'},
                           id=resv_node[0])

    def test_multiple_reservation_request_exclusive_placement(self):
        """
        Test Multiple reservations requesting exclusive placement
        are confirmed when not overlapping in time.
        """
        self.get_vnode_ncpus_value()
        # Submit a reservation with place=excl
        now = int(time.time())
        a = {ATTR_l + '.select': '1:ncpus=1:vnode=%s' % self.vnode,
             'Resource_List.place': 'excl', 'reserve_start': now + 10,
             'reserve_duration': 3600}
        rid = self.submit_and_confirm_resv(a)
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        # Submit a non-overlapping reservation requesting place=excl
        a = {ATTR_l + '.select': '1:ncpus=1:vnode=%s' % resv_node,
             'Resource_List.place': 'excl',
             'reserve_start': now + 7200,
             'reserve_duration': 3600}
        self.submit_and_confirm_resv(a)

    def test_delete_future_resv_not_effect_node_state(self):
        """
        Test (Advance Reservation)Multiple reservations requesting exclusive
        placement are confirmed when not overlapping.
        Deleting the latter reservation after earlier one starts running
        leaves node in state resv-exclusive.
        """
        self.get_vnode_ncpus_value()
        # Submit a reservation with place=excl
        now = int(time.time())
        a = {ATTR_l + '.select': '1:ncpus=1:vnode=%s' % self.vnode,
             'Resource_List.place': 'excl', 'reserve_start': now + 10,
             'reserve_duration': 3600}
        rid = self.submit_and_confirm_resv(a)
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        # Submit a non-overlapping reservation requesting place=excli
        # on vnode in resv_node
        a = {ATTR_l + '.select': '1:ncpus=1:vnode=%s' % resv_node,
             'Resource_List.place': 'excl',
             'reserve_start': now + 7200,
             'reserve_duration': 3600}
        rid2 = self.submit_and_confirm_resv(a)
        self.logger.info('Waiting 10s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Delete future reservation rid2 and verify that resv node
        # is still in state resv-exclusive
        self.server.delete(rid2)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)

    def test_delete_future_standing_resv_not_effect_node_state(self):
        """
        Test (Standing Reservation)Multiple reservations requesting exclusive
        placement are confirmed when not overlapping.
        Deleting the latter reservation after earlier one starts running
        leaves node in state resv-exclusive.
        """
        self.get_vnode_ncpus_value()

        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        # Submit a standing reservation with place=excl
        now = int(time.time())
        a = {ATTR_l + '.select': '1:ncpus=1:vnode=%s' % self.vnode,
             'Resource_List.place': 'excl',
             ATTR_resv_rrule: 'FREQ=HOURLY;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': now + 10,
             'reserve_end': now + 3100}
        rid = self.submit_and_confirm_resv(a)
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        # Submit a non-overlapping reservation requesting place=excli
        # on vnode in resv_node
        a = {ATTR_l + '.select': '1:ncpus=1:vnode=%s' % resv_node,
             'Resource_List.place': 'excl',
             ATTR_resv_rrule: 'FREQ=HOURLY;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': now + 7200,
             'reserve_end': now + 10800}
        rid2 = self.submit_and_confirm_resv(a)
        self.logger.info('Waiting 10s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Delete future reservation rid2 and verify that resv node
        # is still in state resv-exclusive
        self.server.delete(rid2)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)

    def test_job_inside_exclusive_reservation(self):
        """
        Test Job will run correctly inside the exclusive
        reservation
        """
        self.script2 = []
        self.script2 += ['echo Hello World\n']
        self.script2 += ['/bin/sleep 10']

        # Submit a reservation with place=excl
        start_time = time.time()
        now = int(start_time)
        a = {'Resource_List.select': '1:ncpus=1:vntype=cray_login',
             'Resource_List.place': 'excl', 'reserve_start': now + 20,
             'reserve_end': now + 40}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)
        self.logger.info('Waiting 20s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=20)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Submit a job inside the reservation
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '1:ncpus=1:vntype=cray_login',
             'Resource_List.place': 'excl'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script2)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        self.server.expect(
            JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive,resv-exclusive'},
                           id=resv_node)
        # wait 5 sec for job to end
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node, offset=5, interval=10)
        # Wait for reservation to end and verify node state
        # changed as free
        msg = "Que;" + rid_q + ";deleted at request of pbs_server@"
        self.server.log_match(msg, starttime=start_time, interval=2)
        self.server.expect(NODE, {'state': 'free'},
                           id=resv_node)

        #  Test Job will run correctly inside the exclusive
        #  standing reservation requesting compute_node
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        # Submit a standing reservation with place=excl
        now = int(time.time())
        a = {ATTR_l + '.select': '1:ncpus=1:vntype=cray_compute',
             'Resource_List.place': 'excl',
             ATTR_resv_rrule: 'FREQ=HOURLY;COUNT=1',
             ATTR_resv_timezone: tzone,
             'reserve_start': now + 10,
             'reserve_end': now + 300}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.server.expect(NODE, {'state': 'free'}, id=resv_node)
        self.logger.info('Waiting 10s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node)
        # Submit a job inside the reservation
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_q: rid_q}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive,resv-exclusive'},
                           id=resv_node)
        # wait 5 sec for job to end
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node, offset=5, interval=10)

    def test_reservation_request_node_ignore_excl(self):
        """
        Test Reservation asking for place=excl
        will not get confirmed if node has
        ignore_excl set on it.
        """

        a = {'sharing': 'ignore_excl'}
        self.mom.create_vnodes(a, 1,
                               createnode=False,
                               delall=False, usenatvnode=True)
        self.server.expect(NODE, {'state': 'free',
                                  'sharing': 'ignore_excl'},
                           id=self.mom.shortname)
        # Submit a reservation
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1:vntype=cray_login',
             'Resource_List.place': 'excl', 'reserve_start': now + 20,
             'reserve_end': now + 40}
        rid = self.submit_and_confirm_resv(a)
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        # Wait for reservation to start and verify
        # node state should not be resv-exclusive
        self.logger.info('Waiting 10s for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'},
                           id=resv_node, op=NE)

    def test_multijob_on_resv_exclusive_node(self):
        """
        Test multiple jobs request inside a reservation
        if none(node,reservation or job) asks for exclusivity
        """
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2:vntype=cray_compute',
             'Resource_List.place': 'shared', 'reserve_start': now + 20,
             'reserve_end': now + 40}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.logger.info('Waiting for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'}, id=resv_node)
        a = {ATTR_q: rid_q}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive,resv-exclusive'},
                           id=resv_node)
        j2 = Job(TEST_USER, attrs=a)
        j2.create_script(self.script)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

    def test_job_with_exclusive_placement(self):
        """
        Job will honour exclusivity inside the reservation
        """
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2:vntype=cray_compute',
             'Resource_List.place': 'excl', 'reserve_start': now + 20,
             'reserve_end': now + 40}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.logger.info('Waiting for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '1:ncpus=1',
             'Resource_List.place': 'excl'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '1:ncpus=1',
             'Resource_List.place': 'shared'}
        j2 = Job(TEST_USER, attrs=a)
        j2.create_script(self.script)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid1, offset=5)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

    def test_job_running_on_multinode_reservation(self):
        """
        Test to submit job on multinode reservation with different placement
        """
        ncpus = []
        vnodes = self.server.status(NODE)
        num_vnodes = 2
        i = 0
        for vnode in vnodes:
            if i < 2:
                if vnode['resources_available.vntype'] == 'cray_compute':
                    ncpus.append(int(vnode['resources_available.ncpus']))
                    i += 1
                    if i == 2:
                        break
        total_ncpus = ncpus[0] + ncpus[1]
        req_ncpus = min(ncpus[0] / 2, ncpus[1] / 2)
        now = int(time.time())
        a = {
            'Resource_List.select': '2:ncpus=%d:vntype=cray_compute' % min(
                ncpus[0], ncpus[1]),
            'Resource_List.place': 'excl',
            'reserve_start': now + 20,
            'reserve_end': now + 60}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.logger.info('Waiting for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=20)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '2:ncpus=%d' % req_ncpus,
             'Resource_List.place': 'scatter'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '1:ncpus=%d' % ncpus[0],
             'Resource_List.place': 'excl'}
        j2 = Job(TEST_USER, attrs=a)
        j2.create_script(self.script)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        a = {ATTR_q: rid_q, ATTR_l + '.select': '1:ncpus=%d' % ncpus[1],
             'Resource_List.place': 'shared'}
        j3 = Job(TEST_USER, attrs=a)
        j3.create_script(self.script)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid1, offset=5)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

    def test_job_with_exclhost_placement_inside_resv(self):
        """
        Job inside a reservation asking for place=exclhost on host
        will have all resources of the vnodes present on host assigned to it
        """
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2:vntype=cray_compute',
             'Resource_List.place': 'exclhost', 'reserve_start': now + 20,
             'reserve_end': now + 40}
        rid = self.submit_and_confirm_resv(a)
        rid_q = rid.split('.')[0]
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        self.logger.info('Waiting for reservation to start')
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'resv-exclusive'}, id=resv_node)
        a = {ATTR_q: rid_q}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive,resv-exclusive'},
                           id=resv_node)
        a = {ATTR_q: rid_q}
        j2 = Job(TEST_USER, attrs=a)
        j2.create_script(self.script)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid1, offset=10)
        self.server.expect(RESV, 'queue', op=UNSET, id=rid, offset=10)
        self.server.expect(NODE, {'state': 'free'}, id=resv_node)

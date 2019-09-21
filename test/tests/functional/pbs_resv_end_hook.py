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


class TestResvEndHook(TestFunctional):
    """
    Tests to verify the reservation end hook for a confirm standing/advance/
    degraded reservation once the reservation ends or gets deleted.
    """

    advance_resv_hook_script = """
import pbs
e=pbs.event()

pbs.logmsg(pbs.LOG_DEBUG, 'Reservation End Hook name - %s' % e.hook_name)

if e.type == pbs.RESV_END:
    pbs.logmsg(pbs.LOG_DEBUG, 'Reservation ID - %s' % e.resv.resvid)
"""

    standing_resv_hook_script = """
import pbs
e=pbs.event()

pbs.logmsg(pbs.LOG_DEBUG, 'Reservation End Hook name - %s' % e.hook_name)

if e.type == pbs.RESV_END:
    pbs.logmsg(pbs.LOG_DEBUG, 'Reservation occurrence - %s' %
    e.resv.reserve_index)
"""

    def setUp(self):
        """
        Create a reservation end hook and set the server log level.
        """
        super(TestResvEndHook, self).setUp()
        self.hook_name = 'resvend_hook'
        attrs = {'event': 'resv_end'}
        self.server.create_hook(self.hook_name, attrs)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

    def submit_resv(self, offset, duration, select='1:ncpus=1', rrule=''):
        """
        Helper function to submit an advance/a standing reservation.
        """
        start_time = int(time.time()) + offset
        end_time = start_time + duration

        attrs = {
            'reserve_start': start_time,
            'reserve_end': end_time,
            'Resource_List.select': select
        }

        if rrule:
            if 'PBS_TZID' in self.conf:
                tzone = self.conf['PBS_TZID']
            elif 'PBS_TZID' in os.environ:
                tzone = os.environ['PBS_TZID']
            else:
                self.logger.info('Missing timezone, using Asia/Kolkata')
                tzone = 'Asia/Kolkata'
            attrs[ATTR_resv_rrule] = rrule
            attrs[ATTR_resv_timezone] = tzone

        rid = self.server.submit(Reservation(TEST_USER, attrs))

        return rid

    def test_delete_advance_resv(self):
        """
        Testcase to submit and confirm advance reservation, delete the same
        and verify the resvend hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    def test_delete_degraded_resv(self):
        """
        Testcase to submit and confirm an advance reservation, turn the mom
        off, delete the degraded reservation and verify the resvend
        hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.mom.stop()

        attrs['reserve_state'] = (MATCH_RE, 'RESV_DEGRADED|10')
        self.server.expect(RESV, attrs, id=rid)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    def test_server_down_case_1(self):
        """
        Testcase to submit and confirm an advance reservation, turn the server
        off, turn the server on, delete the reservation and verify the resvend
        hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.stop()

        self.server.start()

        self.server.delete(rid)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    @timeout(300)
    def test_server_down_case_2(self):
        """
        Testcase to submit and confirm an advance reservation, turn the
        server off, wait for the reservation duration to finish, turn the
        server on and verify the resvend hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.stop()

        self.logger.info('wait for 30 seconds till the reservation ends')
        time.sleep(30)

        self.server.start()

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    @timeout(240)
    def test_end_advance_resv(self):
        """
        Testcase to submit and confirm an advance reservation, wait for it
        to end and verify the reservation end hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        self.logger.info('wait 30 seconds until the reservation ends')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    def test_delete_advance_resv_with_jobs(self):
        """
        Testcase to submit and confirm an advance reservation, submit
        some jobs to the same, wait for the same to end and
        verify the reservation end hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        job_attrs = {
            'Resource_List.walltime': 5,
            'Resource_List.select': '1:ncpus=1',
            'queue': rid.split('.')[0]
        }

        for _ in range(10):
            self.server.submit(Job(TEST_USER, job_attrs))

        self.logger.info('wait 10 seconds till the reservation runs some jobs')
        time.sleep(10)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    @timeout(240)
    def test_end_advance_resv_with_jobs(self):
        """
        Testcase to submit and confirm an advance reservation, submit
        some jobs to the same, wait for it to start and end, verify
        the resvend hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        job_attrs = {
            'Resource_List.walltime': 10,
            'Resource_List.select': '1:ncpus=1',
            'queue': rid.split('.')[0]
        }

        for _ in range(10):
            self.server.submit(Job(TEST_USER, job_attrs))

        self.logger.info('wait till 30 seconds until the reservation ends')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    def test_set_attrs(self):
        """
        Testcase to submit and confirm an advance reservation, delete the
        reservation and verify the read permissions in the resvend hook.
        """

        hook_script = """
import pbs
e=pbs.event()

pbs.logmsg(pbs.LOG_DEBUG, 'Reservation End Hook name - %s' % e.hook_name)

if e.type == pbs.RESV_END:
    e.resv.resources_used.walltime = 10
    pbs.logmsg(pbs.LOG_DEBUG, 'Reservation ID - %s' %
    e.resv.resources_used.walltime)
"""

        self.server.import_hook(self.hook_name, hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.delete(rid)
        msg = 'Svr;Server@%s;PBS server internal error (15011) in Error ' \
              'evaluating Python script, attribute '"'resources_used'"' is ' \
              'part of a readonly object' % self.server.shortname
        self.server.log_match(msg, tail=True, max_attempts=30, interval=2)

    @timeout(300)
    def test_delete_resv_occurrence(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, wait for the first occurrence to end and verify
        the end hook for the same, delete the second occurrence and
        verify the resvend hook for the latter.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.standing_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration, rrule='FREQ=MINUTELY;COUNT=2')

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        self.logger.info('wait till 30 seconds until the reservation ends')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation occurrence - 1' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation end hook ran for first occurrence of '
                         'a standing reservation')

        self.logger.info(
            'wait for 10 seconds till the next occurrence is submitted')
        time.sleep(10)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation occurrence - 2' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    @timeout(300)
    def test_end_resv_occurrences(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, wait for the first occurrence to end and verify
        the end hook for the same, wait for the second occurrence to
        start and end, verify the resvend hook for the latter.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.standing_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration, rrule='FREQ=MINUTELY;COUNT=2')

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        self.logger.info('Sleep for 30 seconds for the reservation occurrence '
                         'to end')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation occurrence - 1' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation end hook ran for first occurrence of a '
                         'standing reservation')

        self.logger.info('Sleep for 30 seconds as this is a '
                         'minutely occurrence')
        time.sleep(30)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'),
                 'reserve_index': 2}
        self.server.expect(RESV, attrs, id=rid, attrop=PTL_AND)

        msg = 'Hook;Server@%s;Reservation occurrence - 2' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation end hook ran for second occurrence of a'
                         ' standing reservation')

    @timeout(300)
    def test_delete_resv_occurrence_with_jobs(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, submit some jobs to it, wait for the first
        occurrence to end and verify the end hook for the same,
        delete the second occurrence and verify the resvend hook
        for the latter.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.standing_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration, rrule='FREQ=MINUTELY;COUNT=2')

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        job_attrs = {
            'Resource_List.walltime': 5,
            'Resource_List.select': '1:ncpus=1',
            'queue': rid.split('.')[0]
        }

        for _ in range(10):
            self.server.submit(Job(TEST_USER, job_attrs))

        self.logger.info('Sleep for 30 seconds for the reservation occurrence '
                         'to end')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation occurrence - 1' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation end hook ran for first occurrence of a '
                         'standing reservation')

        self.logger.info(
            'wait for 10 seconds till the next occurrence is submitted')
        time.sleep(10)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation occurrence - 2' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    @timeout(300)
    def test_end_resv_occurrences_with_jobs(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, wait for the first occurrence to end and verify
        the end hook for the same, wait for the second occurrence to
        end and verify the resvend hook for the latter.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.standing_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration, rrule='FREQ=MINUTELY;COUNT=2')

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        job_attrs = {
            'Resource_List.walltime': 5,
            'Resource_List.select': '1:ncpus=1',
            'queue': rid.split('.')[0]
        }

        for _ in range(10):
            self.server.submit(Job(TEST_USER, job_attrs))

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        self.logger.info('Sleep for 30 seconds for the reservation occurrence '
                         'to end')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation occurrence - 1' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation end hook ran for first occurrence of a '
                         'standing reservation')

        self.logger.info('Sleep for 30 seconds as this is a '
                         'minutely occurrence')
        time.sleep(30)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'),
                 'reserve_index': 2}
        self.server.expect(RESV, attrs, id=rid, attrop=PTL_AND)

        msg = 'Hook;Server@%s;Reservation occurrence - 2' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation end hook ran for second occurrence of a '
                         'standing reservation')

    def test_unconfirmed_resv_with_node(self):
        """
        Testcase to set the node attributes such that the number of ncpus is 1,
        submit and confirm a reservation on the same node, submit another
        reservation on the same node and verify the reservation end hook
        as the latter one stays in unconfirmed state.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        node_attrs = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, node_attrs,
                            id=self.mom.shortname)
        offset = 10
        duration = 10
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        new_rid = self.submit_resv(offset, duration)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, new_rid)
        self.server.log_match(msg, tail=True, max_attempts=10,
                              existence=False)

    @timeout(240)
    def test_scheduler_down_case_1(self):
        """
        Testcase to turn off the scheduler and submit a reservation,
        the same will be in unconfirmed state and upon ending the
        resvend hook shall not run.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        self.scheduler.stop()

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        self.logger.info('wait for 30 seconds till the reservation ends ')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, max_attempts=10,
                              existence=False)

    def test_scheduler_down_case_2(self):
        """
        Testcase to turn off the scheduler and submit a reservation,
        the same will be in unconfirmed state and deleting that should
        not run the resvend hook.
        """
        self.server.import_hook(self.hook_name,
                                TestResvEndHook.advance_resv_hook_script)

        self.scheduler.stop()

        offset = 10
        duration = 10
        rid = self.submit_resv(offset, duration)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, max_attempts=10,
                              existence=False)

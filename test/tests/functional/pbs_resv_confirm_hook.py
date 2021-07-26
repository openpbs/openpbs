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

import textwrap
from tests.functional import *


class TestResvConfirmHook(TestFunctional):
    """
    Tests to verify the reservation begin hook for a confirm standing/advance/
    degraded reservation once the reservation begins.
    """

    advance_resv_hook_script = textwrap.dedent("""
        import pbs
        e=pbs.event()

        pbs.logmsg(pbs.LOG_DEBUG,
                   'Reservation Confirm Hook name - %s' % e.hook_name)

        if e.type == pbs.RESV_CONFIRM:
            pbs.logmsg(pbs.LOG_DEBUG,
                       'Reservation ID - %s' % e.resv.resvid)
            pbs.logmsg(pbs.LOG_DEBUG, 'Reservation occurrence - %s' %
                       e.resv.reserve_index)
    """)

    def setUp(self):
        """
        Create a reservation confirm hook and set the server log level.
        """
        super(TestResvConfirmHook, self).setUp()
        self.hook_name = 'resvconfirm_hook'
        attrs = {'event': 'resv_confirm'}
        self.server.create_hook(self.hook_name, attrs)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

    @tags('hooks')
    def test_run_advance_resv(self):
        """
        Testcase to submit and confirm advance reservation, delete the same
        and verify the resv_confirm hook ran.
        """
        self.server.import_hook(self.hook_name,
                                TestResvConfirmHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid, _, _ = self.server.submit_resv(offset, duration)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=1, max_attempts=10)

    @tags('hooks')
    def test_degraded_resv(self):
        """
        Testcase to submit and confirm an advance reservation, offline vnode,
        verify reservation degredation, restore the vnode and verify the
        resv_confirm hook ran the correct number of times.
        """
        self.server.import_hook(self.hook_name,
                                TestResvConfirmHook.advance_resv_hook_script)

        offset = 300
        duration = 30
        rid, _, _ = self.server.submit_resv(offset, duration)
        msg = 'Hook;Server@%s;Reservation ID - %s' % (self.server.shortname,
                                                      rid)
        self.server.log_match(msg, tail=True)

        self.server.manager(MGR_CMD_SET, NODE, {'state': (INCR, 'offline')},
                            id=self.mom.shortname)
        vnode_off_time = time.time()

        attrs = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.manager(MGR_CMD_SET, NODE, {'state': (DECR, 'offline')},
                            id=self.mom.shortname)
        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.log_match(msg, starttime=vnode_off_time, interval=1,
                              max_attempts=10, existence=False)

    @tags('hooks')
    def test_set_attrs(self):
        """
        Testcase to submit and confirm an advance reservation, delete the
        reservation and verify the read permissions in the resvconfirm hook.
        """

        hook_script = """\
            import pbs
            e=pbs.event()

            pbs.logmsg(pbs.LOG_DEBUG,
                       'Reservation confirm Hook name - %s' % e.hook_name)

            if e.type == pbs.RESV_CONFIRM:
                pbs.logmsg(pbs.LOG_DEBUG, "e.resv = %s" % e.resv.resvid)
                e.resv.queue = 'workq'
                pbs.logmsg(pbs.LOG_DEBUG, 'Reservation ID - %s' %
                e.resv.queue)
        """
        hook_script = textwrap.dedent(hook_script)
        self.server.import_hook(self.hook_name, hook_script)

        offset = 10
        duration = 30
        rid, _, _ = self.server.submit_resv(offset, duration)

        msg = 'Svr;Server@%s;PBS server internal error (15011) in Error ' \
              'evaluating Python script, attribute '"'queue'"' is ' \
              'part of a readonly object' % self.server.shortname
        self.server.log_match(msg, tail=True, max_attempts=30, interval=2)

    @tags('hooks')
    def test_delete_resv_after_first_occurrence(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, wait for the first occurrence to begin and verify
        the confirm hook for the reservation, delete before the second
        occurrence and verify the confirm ran only once.
        """
        self.server.import_hook(self.hook_name,
                                TestResvConfirmHook.advance_resv_hook_script)

        offset = 20
        duration = 30
        rid, _, _ = self.server.submit_resv(offset, duration,
                                            rrule='FREQ=MINUTELY;COUNT=2',
                                            conf=self.conf)
        msg = 'Hook;Server@%s;Reservation ID - %s' % (self.server.shortname,
                                                      rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation confirm hook ran for first occurrence of'
                         ' a standing reservation')
        post_first_conf_time = time.time()
        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid)
        off = offset + duration - time.time()
        self.logger.info('Wait %s sec until reservation completed.', off)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid, offset=off)

        self.server.log_match(msg, starttime=post_first_conf_time, interval=1,
                              max_attempts=10, existence=False)

    @tags('hooks')
    def test_unconfirmed_resv_with_node(self):
        """
        Testcase to set the node attributes such that the number of ncpus is 1,
        submit and confirm a reservation on the same node, submit another
        reservation on the same node and verify the reservation confirm hook
        did not run as the latter one never gets past the unconfirmed state.
        """
        self.server.import_hook(self.hook_name,
                                TestResvConfirmHook.advance_resv_hook_script)

        node_attrs = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, node_attrs,
                            id=self.mom.shortname)
        offset = 20
        duration = 300
        rid, _, _ = self.server.submit_resv(offset, duration)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, max_attempts=10)

        new_rid, _, _ = self.server.submit_resv(offset, duration,
                                                confirmed=False)
        msg = "Server@%s;Resv;%s;Reservation denied" % (self.server.shortname,
                                                        new_rid)
        self.server.log_match(msg, tail=True)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, new_rid)
        self.server.log_match(msg, tail=True, max_attempts=10,
                              existence=False)

    @tags('hooks')
    def test_scheduler_down(self):
        """
        Testcase to turn off the scheduler and submit a reservation,
        the same will be in unconfirmed state and upon ending the
        resv_confirm hook shall not run.
        """
        self.server.import_hook(self.hook_name,
                                TestResvConfirmHook.advance_resv_hook_script)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        offset = 20
        duration = 30
        rid, _, end = self.server.submit_resv(offset, duration,
                                              confirmed=False)
        off = end - time.time()

        self.logger.info('wait for %s seconds till the reservation begins',
                         off)
        time.sleep(off)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, max_attempts=3,
                              existence=False)

    @tags('hooks')
    def test_multiple_reconfirm_hooks(self):
        """
        Define multiple hooks for the resv_confirm event and make sure
        both get run.

        Check for initial confirmation and also in a degraded/reconfirmed case.
        """
        test_hook_script = textwrap.dedent("""
        import pbs
        e=pbs.event()

        pbs.logmsg(pbs.LOG_DEBUG,
                   'Reservation Confirm Hook name - %%s' %% e.hook_name)

        if e.type == pbs.RESV_CONFIRM:
            pbs.logmsg(pbs.LOG_DEBUG,
                       'Test %d Reservation ID - %%s' %% e.resv.resvid)
        """)

        attrs = {'event': 'resv_confirm'}
        self.server.create_import_hook("test_hook_1", attrs,
                                       test_hook_script % 1)
        self.server.create_import_hook("test_hook_2", attrs,
                                       test_hook_script % 2)
        a = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(a, 2)
        offset = 10
        duration = 30

        self.server.manager(MGR_CMD_SET, SERVER, {'reserve_retry_time': 5})
        rid, _, _ = self.server.submit_resv(offset, duration)
        msg1 = 'Hook;Server@%s;Test 1 Reservation ID - %s' % \
            (self.server.shortname, rid)
        self.server.log_match(msg1, tail=True)

        msg2 = 'Hook;Server@%s;Test 2 Reservation ID - %s' % \
            (self.server.shortname, rid)
        self.server.log_match(msg2, tail=True)

        self.server.status(RESV, 'resv_nodes', id=rid)
        rnodes = self.server.reservations[rid].get_vnodes()
        self.server.manager(MGR_CMD_SET, NODE, {'state': (INCR, 'offline')},
                            id=rnodes[0])
        vnode_off_time = time.time()

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.log_match(msg1, starttime=vnode_off_time, interval=1,
                              max_attempts=10)
        self.server.log_match(msg2, starttime=vnode_off_time, interval=1,
                              max_attempts=10)

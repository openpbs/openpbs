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


class TestModifyResvHook(TestFunctional):
    """
    Tests to verify the reservation begin hook for a confirm standing/advance/
    degraded reservation once the reservation begins.
    """

    advance_resv_hook_script = textwrap.dedent("""\
        import pbs
        e=pbs.event()

        pbs.logmsg(pbs.LOG_DEBUG, 'Reservation Modify Hook name - %s' %
                   e.hook_name)

        if e.type == pbs.MODIFYRESV:
            pbs.logmsg(pbs.LOG_DEBUG, 'Reservation ID - %s' % e.resv.resvid)
    """)

    def setUp(self):
        """
        Create a reservation begin hook and set the server log level.
        """
        super(TestModifyResvHook, self).setUp()
        self.hook_name = 'modifyresv_hook'
        attrs = {'event': 'modifyresv'}
        self.server.create_hook(self.hook_name, attrs)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

    @tags('hooks')
    def test_server_down_case_1(self):
        """
        Testcase to submit and confirm an advance reservation, turn the server
        off, attempt to modify the reservation, turn the server on, delete the
        reservation after start and verify the modifyresv hook didn't run.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

        offset = 20
        duration = 300
        shift = 30
        rid, start, end = self.server.submit_resv(offset, duration)

        self.server.stop()
        self.server.alter_a_reservation(rid, start, end, shift, whichMessage=0)
        self.server.start()

        time.sleep(11)

        self.server.delete(rid)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=1, max_attempts=10,
                              existence=False)

    @tags('hooks')
    def test_alter_advance_resv(self):
        """
        Testcase to submit and confirm an advance reservation, wait for it
        to begin and verify the reservation begin hook.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

        offset = 20
        duration = 30
        shift = 10
        rid, start, end = self.server.submit_resv(offset, duration)

        self.server.alter_a_reservation(rid, start, end, shift, alter_s=True,
                                        alter_e=True)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        off = offset + shift + 10
        self.logger.info("Waiting %s sec for resv to run.", off)
        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid, offset=off)

    @tags('hooks')
    def test_set_attrs(self):
        """
        Testcase to submit and confirm an advance reservation, delete the
        reservation and verify permissions in the modifyresv hook.
        """
        msg_rw = 'Reservation modify Hook - check rw Authorized_Groups'
        msg_ro = 'Reservation modify Hook - ctime is read-only.'

        hook_script = textwrap.dedent("""\
            import pbs
            e = pbs.event()
            r = e.resv
            pbs.logmsg(pbs.LOG_DEBUG,
                       'Reservation modify Hook name - %%s' %% e.hook_name)
            if e.type == pbs.MODIFYRESV:
                vo = r.Authorized_Groups
                r.Authorized_Groups = None
                r.Authorized_Groups = vo
                pbs.logmsg(pbs.LOG_DEBUG, "%s")
                try:
                    r.ctime = None
                except pbs.v1._exc_types.BadAttributeValueError:
                    pbs.logmsg(pbs.LOG_DEBUG, "%s")
        """ % (msg_rw, msg_ro))

        self.logger.info(hook_script)
        self.server.import_hook(self.hook_name, hook_script)

        offset = 10
        duration = 30
        shift = 10
        rid, start, end = self.server.submit_resv(offset, duration)
        self.server.alter_a_reservation(rid, start, end, shift, alter_s=True,
                                        alter_e=True)

        time.sleep(15)

        self.server.delete(rid)
        msg = "Reservation modify Hook name - %s" % (self.hook_name)
        self.server.log_match(msg, tail=True, max_attempts=30, interval=2)
        self.server.log_match(msg_rw, tail=True, max_attempts=30, interval=2)
        self.server.log_match(msg_ro, tail=True, max_attempts=30, interval=2)

    @tags('hooks')
    def test_scheduler_down(self):
        """
        Testcase to turn off the scheduler and submit a reservation,
        the same will be in unconfirmed state and upon ending the
        resvmodify hook would have run.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        offset = 10
        duration = 30
        shift = 10

        rid, start, end = self.server.submit_resv(offset, duration,
                                                  confirmed=False)
        self.server.alter_a_reservation(rid, start, end, shift, alter_s=True,
                                        alter_e=True, check_log=False,
                                        sched_down=True)

        time.sleep(5)

        msg = 'Hook;Server@%s;Reservation ID - %s' % (self.server.shortname,
                                                      rid)
        self.server.log_match(msg, tail=True)

    @tags('hooks')
    def test_multiple_hooks(self):
        """
        Define multiple hooks for the modifyresv event and make sure both
        get run.

        """
        test_hook_script = textwrap.dedent("""
        import pbs
        e=pbs.event()

        pbs.logmsg(pbs.LOG_DEBUG,
                   'Reservation Modify Hook name - %%s' %% e.hook_name)

        if e.type == pbs.MODIFYRESV:
            pbs.logmsg(pbs.LOG_DEBUG,
                       'Test %d Reservation ID - %%s' %% e.resv.resvid)
        """)

        attrs = {'event': 'modifyresv'}
        self.server.create_import_hook("test_hook_1", attrs,
                                       test_hook_script % 1)
        self.server.create_import_hook("test_hook_2", attrs,
                                       test_hook_script % 2)
        offset = 10
        duration = 30
        shift = 10
        rid, start, end = self.server.submit_resv(offset, duration)
        self.server.alter_a_reservation(rid, start, end, shift, alter_s=True,
                                        alter_e=True)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid, offset=10)

        msg = 'Hook;Server@%s;Test 1 Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=3)

        msg = 'Hook;Server@%s;Test 2 Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=3)

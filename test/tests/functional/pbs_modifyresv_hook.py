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

        pbs.logmsg(pbs.LOG_DEBUG, 'Reservation Modify Hook name - %s' % e.hook_name)

        if e.type == pbs.MODIFYRESV:
            pbs.logmsg(pbs.LOG_DEBUG, 'Reservation ID - %s' % e.resv.resvid)
    """)

    def setUp(self):
        """
        Create a reservation begin hook and set the server log level.
        """
        super(TestModifyResvHook, self).setUp()
        self.bu = BatchUtils()
        self.hook_name = 'modifyresv_hook'
        attrs = {'event': 'modifyresv'}
        self.server.create_hook(self.hook_name, attrs)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

    def submit_resv(self, offset, duration, select='1:ncpus=1', rrule='', times=False):
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

        if times:
            return rid, start_time, end_time
        return rid

    def alter_a_reservation(self, r, start, end, shift=0,
                            alter_s=False, alter_e=False,
                            whichMessage=1, confirm=True, check_log=True,
                            interactive=0, sequence=1,
                            a_duration=None, select=None, extend=None,
                            runas=None):
        """
        Helper method for altering a reservation.
        This method also checks for the server and accounting logs.

        :param r: Reservation id.
        :type  r: string.

        :param start: Start time of the reservation.
        :type  start: int.

        :param end: End time of the reservation.
        :type  end: int

        :param shift: Time in seconds the reservation times will be moved.
        :type  shift: int.

        :param alter_s: Whether the caller intends to change the start time.
                       Default - False.
        :type  alter_s: bool.

        :param alter_e: Whether the caller intends to change the end time.
                       Default - False.
        :type  alter_e: bool.

        :param whichMessage: Which message is expected to be returned.
                            Default: 1.
                             =-1 - No exception, don't check logs
                             =0 - PbsResvAlterError exception will be raised,
                                  so check for appropriate error response.
                             =1 - No exception, check for "CONFIRMED" message
                             =2 - No exception, check for "UNCONFIRMED" message
                             =3 - No exception, check for "DENIED" message
        :type  whichMessage: int.

        :param confirm: The expected state of the reservation after it is
                       altered. It can be either Confirmed or Running.
                       Default - Confirmed State.
        :type  confirm: bool.

        :param interactive: Time in seconds the CLI waits for a reply.
                           Default - 0 seconds.
        :type  interactive: int.

        :param sequence: To check the number of log matches corresponding
                        to alter.
                        Default: 1
        :type  sequence: int.

        :param a_duration: The duration to modify.
        :type a_duration: int.
        :param extend: extend parameter.
        :type extend: str.
        :param runas: User who own alters the reservation.
                      Default: user running the test.
        :type runas: PbsUser.
        """
        fmt = "%a %b %d %H:%M:%S %Y"
        new_start = start
        new_end = end
        attrs = {}

        if alter_s:
            new_start = start + shift
            new_start_conv = self.bu.convert_seconds_to_datetime(
                new_start)
            attrs['reserve_start'] = new_start_conv

        if alter_e:
            new_end = end + shift
            new_end_conv = self.bu.convert_seconds_to_datetime(new_end)
            attrs['reserve_end'] = new_end_conv

        if interactive > 0:
            attrs['interactive'] = interactive

        if a_duration:
            if isinstance(a_duration, str) and ':' in a_duration:
                new_duration_conv = self.bu.convert_duration(a_duration)
            else:
                new_duration_conv = a_duration

            if not alter_s and not alter_e:
                new_end = start + new_duration_conv + shift
            elif alter_s and not alter_e:
                new_end = new_start + new_duration_conv
            elif not alter_s and alter_e:
                new_start = new_end - new_duration_conv
            # else new_start and new_end have already been calculated
        else:
            new_duration_conv = new_end - new_start

        if a_duration:
            attrs['reserve_duration'] = new_duration_conv

        if select:
            attrs['Resource_List.select'] = select

        if runas is None:
            runas = self.du.get_current_user()

        if whichMessage:
            msg = ['']
            acct_msg = ['']

            if interactive:
                if whichMessage == 1:
                    msg = "pbs_ralter: " + r + " CONFIRMED"
                elif whichMessage == 2:
                    msg = "pbs_ralter: " + r + " UNCONFIRMED"
                else:
                    msg = "pbs_ralter: " + r + " DENIED"
            else:
                msg = "pbs_ralter: " + r + " ALTER REQUESTED"

            self.server.alterresv(r, attrs, extend=extend, runas=runas)

            self.assertEqual(msg, self.server.last_out[0])
            self.logger.info(msg + " displayed")

            if check_log:
                msg = "Resv;" + r + ";Attempting to modify reservation "
                if start != new_start:
                    msg += "start="
                    msg += time.strftime(fmt,
                                         time.localtime(int(new_start)))
                    msg += " "

                if end != new_end:
                    msg += "end="
                    msg += time.strftime(fmt,
                                         time.localtime(int(new_end)))
                    msg += " "

                if select:
                    msg += "select=" + select + " "

                # strip the last space
                msg = msg[:-1]
                self.server.log_match(msg, interval=2, max_attempts=30)

            if whichMessage == -1:
                return new_start, new_end
            elif whichMessage == 1:
                if alter_s:
                    new_start_conv = self.bu.convert_seconds_to_datetime(
                        new_start, fmt)
                    attrs['reserve_start'] = new_start_conv

                if alter_e:
                    new_end_conv = self.bu.convert_seconds_to_datetime(
                        new_end, fmt)
                    attrs['reserve_end'] = new_end_conv

                if a_duration:
                    attrs['reserve_duration'] = new_duration_conv

                if confirm:
                    attrs['reserve_state'] = (MATCH_RE, 'RESV_CONFIRMED|2')
                else:
                    attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')

                self.server.expect(RESV, attrs, id=r)
                if check_log:
                    acct_msg = "Y;" + r + ";requestor=Scheduler@.*" + " start="
                    acct_msg += str(new_start) + " end=" + str(new_end)
                    self.server.status(RESV, 'resv_nodes', id=r)
                    acct_msg += " nodes="
                    acct_msg += re.escape(self.server.reservations[r].
                                          resvnodes())

                    if r[0] == 'S':
                        self.server.status(RESV, 'reserve_count', id=r)
                        count = self.server.reservations[r].attributes[
                            'reserve_count']
                        acct_msg += " count=" + count

                    self.server.accounting_match(acct_msg, regexp=True,
                                                 interval=2,
                                                 max_attempts=30, n='ALL')

                # Check if reservation reports new start time
                # and updated duration.

                msg = "Resv;" + r + ";Reservation alter confirmed"
            else:
                msg = "Resv;" + r + ";Reservation alter denied"
            interval = 0.5
            max_attempts = 20
            for attempts in range(1, max_attempts + 1):
                lines = self.server.log_match(msg, n='ALL', allmatch=True,
                                              max_attempts=5)
                info_msg = "log_match: searching " + \
                    str(sequence) + " sequence of message: " + \
                    msg + ": Got: " + str(len(lines))
                self.logger.info(info_msg)
                if len(lines) == sequence:
                    break
                else:
                    attempts = attempts + 1
                    time.sleep(interval)
            if attempts > max_attempts:
                raise PtlLogMatchError(rc=1, rv=False, msg=info_msg)
            return new_start, new_end
        else:
            try:
                self.server.alterresv(r, attrs, extend=extend, runas=runas)
            except PbsResvAlterError as e:
                if e.rc == self.PBSE_RESV_NOT_EMPTY:
                    msg = "pbs_ralter: Reservation not empty"
                elif e.rc == self.PBSE_UNKRESVID:
                    msg = "pbs_ralter: Unknown Reservation Id"
                elif e.rc == self.PBSE_SELECT_NOT_SUBSET:
                    msg = "pbs_ralter: New select must be made up of a "
                    msg += "subset of the original chunks"
                elif e.rc == self.PBSE_STDG_RESV_OCCR_CONFLICT:
                    msg = "Requested time(s) will interfere with "
                    msg += "a later occurrence"
                    log_msg = "Resv;" + r + ";" + msg
                    msg = "pbs_ralter: " + msg
                    self.server.log_match(log_msg, interval=2,
                                          max_attempts=30)
                elif e.rc == self.PBSE_INCORRECT_USAGE:
                    pass
                elif e.rc == self.PBSE_PERM:
                    msg = "pbs_ralter: Unauthorized Request"
                elif e.rc == self.PBSE_NOSUP:
                    msg = "pbs_ralter: No support for requested service"

                self.assertNotEqual(e.msg, msg)
                return start, end
            else:
                self.assertFalse("Reservation alter allowed when it should" +
                                 "not be.")


    @tags('hooks')
    def test_delete_advance_resv(self):
        """
        Testcase to submit and confirm advance reservation, delete the same
        and verify the modifyresv hook did not run.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=1, max_attempts=10, existence=False)

    @tags('hooks')
    def test_server_down_case_1(self):
        """
        Testcase to submit and confirm an advance reservation, turn the server
        off, attempt to modify the reservation, turn the server on, delete the 
        reservation after start and verify the modifyresv hook didn't run.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

        offset = 10
        duration = 300
        shift = 30
        rid, start, end = self.submit_resv(offset, duration, times=True)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.stop()
        self.alter_a_reservation(rid, start, end, shift, whichMessage=0 )
        self.server.start()

        time.sleep(11)

        self.server.delete(rid)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=1, max_attempts=10)

    @tags('hooks')
    @timeout(30)
    def test_alter_advance_resv(self):
        """
        Testcase to submit and confirm an advance reservation, wait for it
        to begin and verify the reservation begin hook.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

        offset = 10
        duration = 30
        shift = 10
        rid, start, end = self.submit_resv(offset, duration, times=True)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)
        
        self.alter_a_reservation(rid, start, end, shift, alter_s=True, alter_e=True)
        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        time.sleep(offset + shift)
        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)
        # Don't need to wait.  Let teardown clear the reservation

    
    @tags('hooks')
    def test_set_attrs(self):
        """
        Testcase to submit and confirm an advance reservation, delete the
        reservation and verify the read permissions in the resvbegin hook.
        """

        hook_script = textwrap.dedent("""\
            import pbs
            e=pbs.event()

            pbs.logmsg(pbs.LOG_DEBUG, 'Reservation modify Hook name - %s' % e.hook_name)

            if e.type == pbs.RESV_MODIFY:
                pbs.logmsg(pbs.LOG_DEBUG, 'e.resv = %s' % e.resv.__dict__)
                e.resv.resources_used.walltime = 10
                pbs.logmsg(pbs.LOG_DEBUG, 'Reservation ID - %s' %
                e.resv.resources_used.walltime)
        """)

        self.server.import_hook(self.hook_name, hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        time.sleep(15)

        self.server.delete(rid)
        msg = 'Svr;Server@%s;PBS server internal error (15011) in Error ' \
              'evaluating Python script, attribute '"'resources_used'"' is ' \
              'part of a readonly object' % self.server.shortname
        self.server.log_match(msg, tail=True, max_attempts=30, interval=2)

    @tags('hooks')
    @timeout(300)
    def test_delete_resv_after_first_occurrence(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, wait for the first occurrence to begin and verify
        the begin hook for the same, delete before the second occurrence and
        verify the resvbegin hook for the latter didn't run.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.standing_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration, rrule='FREQ=MINUTELY;COUNT=2')

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        self.logger.info('wait till 30 seconds until the reservation begins')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation occurrence - 1' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation begin hook ran for first occurrence of '
                         'a standing reservation')

        self.logger.info('delete during first occurence')

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation occurrence - 2' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30,
                              existence=False)

    
    @tags('hooks')
    @timeout(300)
    def test_begin_resv_occurrences(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, wait for the first occurrence to begin and verify
        the begin hook for the same, wait for the second occurrence to
        start and end, verify the resvbegin hook for the latter.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.standing_resv_hook_script)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration, rrule='FREQ=MINUTELY;COUNT=2')

        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        msg = 'Hook;Server@%s;Reservation occurrence - 1' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation begin hook ran for first occurrence of a '
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
        self.logger.info('Reservation begin hook ran for second occurrence of a'
                         ' standing reservation')

    @tags('hooks')
    @timeout(300) #can delete? 
    def test_delete_resv_occurrence_with_jobs(self):
        """
        Testcase to submit and confirm a standing reservation for two
        occurrences, submit some jobs to it, wait for the first
        occurrence to begin and verify the begin hook for the same,
        delete the second occurrence and verify the resvbegin hook
        for the latter.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.standing_resv_hook_script)

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
                         'to begin')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation occurrence - 1' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)
        self.logger.info('Reservation begin hook ran for first occurrence of a '
                         'standing reservation')

        self.logger.info(
            'wait for 10 seconds till the next occurrence is submitted')
        time.sleep(10)

        self.server.delete(rid)
        msg = 'Hook;Server@%s;Reservation occurrence - 2' % \
              self.server.shortname
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

    @tags('hooks') 
    def test_unconfirmed_resv_with_node(self):
        """
        Testcase to set the node attributes such that the number of ncpus is 1,
        submit and confirm a reservation on the same node, submit another
        reservation on the same node and verify the reservation begin hook
        as the latter one stays in unconfirmed state.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

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

    @tags('hooks')
    @timeout(240)
    def test_scheduler_down(self):
        """
        Testcase to turn off the scheduler and submit a reservation,
        the same will be in unconfirmed state and upon ending the
        resvbegin hook shall not run.
        """
        self.server.import_hook(self.hook_name,
                                TestModifyResvHook.advance_resv_hook_script)

        self.scheduler.stop()

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)

        self.logger.info('wait for 30 seconds till the reservation begins ')
        time.sleep(30)

        msg = 'Hook;Server@%s;Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, max_attempts=10,
                              existence=False)

    @tags('hooks')
    @timeout(30)
    def test_multiple_hooks(self):
        """Define multiple hooks for the modifyresv event and make sure
        both get run.

        """
        test_hook_script_1 = textwrap.dedent("""\
        import pbs
        e=pbs.event()

        pbs.logmsg(pbs.LOG_DEBUG, 'Reservation Begin Hook name - %s' % e.hook_name)

        if e.type == pbs.RESV_BEGIN:
            pbs.logmsg(pbs.LOG_DEBUG, 'Test 1 Reservation ID - %s' % e.resv.resvid)
        """)

        test_hook_script_2 = textwrap.dedent("""\
        import pbs
        e=pbs.event()

        pbs.logmsg(pbs.LOG_DEBUG, 'Reservation Begin Hook name - %s' % e.hook_name)

        if e.type == pbs.RESV_BEGIN:
            pbs.logmsg(pbs.LOG_DEBUG, 'Test 2 Reservation ID - %s' % e.resv.resvid)
        """)

        attrs = {'event': 'resv_begin'}
        self.server.create_hook("test_hook_1", attrs)
        self.server.create_hook("test_hook_2", attrs)
        self.server.import_hook("test_hook_1", test_hook_script_1)
        self.server.import_hook("test_hook_2", test_hook_script_2)

        offset = 10
        duration = 30
        rid = self.submit_resv(offset, duration)
        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)
        attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, attrs, id=rid, offset=10)

        msg = 'Hook;Server@%s;Test 1 Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

        msg = 'Hook;Server@%s;Test 2 Reservation ID - %s' % \
              (self.server.shortname, rid)
        self.server.log_match(msg, tail=True, interval=2, max_attempts=30)

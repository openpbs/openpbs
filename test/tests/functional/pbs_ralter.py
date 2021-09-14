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


class TestPbsResvAlter(TestFunctional):

    """
    This test suite is for testing the reservation times modification feature.
    """

    # Class variables
    tzone = None
    # These must be equal to the declarations in pbs_error.h
    PBSE_UNKRESVID = 236
    PBSE_SELECT_NOT_SUBSET = 79
    PBSE_RESV_NOT_EMPTY = 74
    PBSE_STDG_RESV_OCCR_CONFLICT = 75
    PBSE_INCORRECT_USAGE = 2
    PBSE_PERM = 159
    PBSE_NOSUP = 181
    fmt = "%a %b %d %H:%M:%S %Y"
    bu = BatchUtils()

    def setUp(self):

        TestFunctional.setUp(self)
        self.server.set_op_mode(PTL_CLI)
        # Set PBS_TZID, needed for standing reservation.
        if 'PBS_TZID' in self.conf:
            self.tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            self.tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Timezone not set, using Asia/Kolkata')
            self.tzone = 'Asia/Kolkata'

        a = {'resources_available.ncpus': 4, 'resources_available.mem': '1gb'}
        self.mom.create_vnodes(a, num=2,
                               usenatvnode=True)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})

    def submit_and_confirm_reservation(self, offset, duration, standing=False,
                                       select="1:ncpus=4",
                                       rrule="FREQ=HOURLY;COUNT=2",
                                       ExpectSuccess=1, ruser=TEST_USER):
        """
        Helper function to submit a reservation and wait until it is confirmed.
        It also checks for the corresponding server and accounting logs.

        :param offset: time in seconds after which the reservation should
                       start.
        :type  offset: int

        :param duration: duration of the reservation to be submitted.
        :type  duration: int

        :param standing: whether to submit a standing reservation. Default: No.
        :type  standing: bool

        :param select: select specification for the reservation,
                      Default: "1:ncpus=4"
        :type  select: string.

        :param rrule:  iCal recurrence rule for submitting a standing
                      reservation.  Default: "FREQ=HOURLY;COUNT=2"
        :type  select: string.

        :param ExpectSuccess: Whether the caller expects the submission to be
                             successful or not. If set anything other than 1
                             or 0, reservation state is not checked at all.
                             Default: 1
        :type  ExpectSuccess: int.

        :param ruser: User who own the reservation. Default: TEST_USER.
        :type ruser: PbsUser.
        """
        start = int(time.time()) + offset
        end = start + duration

        if standing:
            attrs = {'Resource_List.select': select,
                     'reserve_start': start,
                     'reserve_end': end,
                     'reserve_timezone': self.tzone,
                     'reserve_rrule': rrule}
        else:
            attrs = {'Resource_List.select': select,
                     'reserve_start': start,
                     'reserve_end': end}

        rid = self.server.submit(Reservation(ruser, attrs))
        msg = "Resv;" + rid + ";New reservation submitted start="
        msg += time.strftime(self.fmt, time.localtime(int(start)))
        msg += " end="
        msg += time.strftime(self.fmt, time.localtime(int(end)))
        if standing:
            msg += " recurrence_rrule=" + rrule + " timezone="
            msg += self.tzone

        self.server.log_match(msg, interval=2, max_attempts=30)

        if ExpectSuccess == 1:
            attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
            self.server.expect(RESV, attrs, id=rid)

            msg = "Resv;" + rid + ";Reservation confirmed"
            self.server.log_match(msg, interval=2,
                                  max_attempts=30)

            self.server.expect(RESV, attrs, id=rid)
            acct_msg = "U;" + rid + ";requestor=" + ruser.name + "@.*"

            if standing:
                acct_msg += " recurrence_rrule=" + re.escape(rrule)
                acct_msg += " timezone=" + re.escape(self.tzone)

            self.server.accounting_match(acct_msg, interval=2, regexp=True,
                                         max_attempts=30, n='ALL')
        elif ExpectSuccess == 0:
            msg = "Resv;" + rid + ";Reservation denied"
            self.server.log_match(msg, interval=2,
                                  max_attempts=30)

        return rid, start, end

    def check_resv_running(self, rid, offset=0, display=True):
        """
        Helper method to wait for reservation to start running.

        :param rid: Reservation id.
        :type  rid: string.

        :param offset: Time in seconds to wait for the reservation to start
                      running.
        :type  offset: int.

        :param display: Whether to display a message or not, default - Yes.
        :type  display: bool
        """
        if offset > 0:
            if display:
                self.logger.info("Waiting for reservation to start running.")
            else:
                self.logger.info("Sleeping.")

        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid, offset=offset)

    def check_occr_finish(self, rid, duration):
        """
        Helper method to wait for a reservation occurrence to finish.
        This method will not work when waiting for the last occurrence of a
        standing reservation to finish running.

        :param rid: Reservation id.
        :type  rid: string.

        :param duration: Time in seconds to wait for the reservation to finish
                      running.
        :type  duration: int.

        :param standing: Whether to display a message or not, default - Yes.
        :type  standing: bool
        NOTE: This won't work for the final occurrence of a standing
              reservation.
        """
        if duration > 0:
            self.logger.info("Waiting for reservation to finish.")
        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid,
                           offset=(duration - 5), interval=2)

    def check_standing_resv_second_occurrence(self, rid, start, end,
                                              select=None, freq=3600,
                                              wait=False):
        """
        Helper method to verify that the second occurrence of a standing
        reservation retains its original start, and end times and select.
        Assumption: This method assumes that rid represents an HOURLY
                    reservation.

        :param rid: Reservation id.
        :type  rid: string.

        :param start: Start time of the first occurrence of the reservation.
        :type  start: int.

        :param end: End time of the first occurrence of the reservation.
        :type  end: int.

        :param freq: Frequency in seconds to run occurrences, default - 1 hour.
        :type  freq: int.

        :param wait: Whether to wait for occurrence to start, default - No.
        :type  wait: int.
        """
        next_start = start + freq
        next_end = end + freq
        duration = end - start
        next_start_conv = self.bu.convert_seconds_to_datetime(
            next_start, self.fmt)
        next_end_conv = self.bu.convert_seconds_to_datetime(
            next_end, self.fmt)
        attrs = {'reserve_start': next_start_conv,
                 'reserve_end': next_end_conv,
                 'reserve_duration': duration}
        if select:
            attrs.update({'Resource_List.select': select})
        self.server.expect(RESV, attrs, id=rid, max_attempts=10,
                           interval=5)
        if wait is True:
            attr = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            t = start + freq - time.time()
            self.server.expect(RESV, attr, id=rid,
                               offset=t, max_attempts=10)

    def submit_job_to_resv(self, rid, sleep=10, user=None):
        """
        Helper method for submitting a sleep job to the reservation.

        :param rid: Reservation id.
        :type  rid: string.

        :param sleep: Sleep time in seconds for the job.
        :type  sleep: int.
        """
        r_queue = rid.split('.')[0]
        a = {'queue': r_queue}
        if not user:
            user = TEST_USER
        j = Job(user, a)
        j.set_sleep_time(sleep)
        jid = self.server.submit(j)
        return jid

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
                    msg += time.strftime(self.fmt,
                                         time.localtime(int(new_start)))
                    msg += " "

                if end != new_end:
                    msg += "end="
                    msg += time.strftime(self.fmt,
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
                        new_start, self.fmt)
                    attrs['reserve_start'] = new_start_conv

                if alter_e:
                    new_end_conv = self.bu.convert_seconds_to_datetime(
                        new_end, self.fmt)
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

    def get_resv_time_info(self, rid):
        """
        Get the start time, end time and duration of a reservation
        in seconds
        :param rid: reservation id
        :type  rid: string
        """
        resv_data = self.server.status(RESV, id=rid)
        t_duration = int(resv_data[0]['reserve_duration'])
        t_end = self.bu.convert_stime_to_seconds(resv_data[0]['reserve_end'])
        t_start = self.bu.convert_stime_to_seconds(resv_data[0]
                                                   ['reserve_start'])
        return t_duration, t_start, t_end

    def test_alter_advance_resv_start_time_before_run(self):
        """
        This test case covers the below scenarios for an advance reservation
        that has not started running.

        1. Make an advance reservation start late (empty reservation)
        2. Make an advance reservation start early (empty reservation)
        3. Make an advance reservation start early (with a job in it)

        All the above operations are expected to be successful.
        """
        offset = 60
        duration = 20
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        new_start, new_end = self.alter_a_reservation(rid, start, end, shift,
                                                      alter_s=True, sequence=1)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      -shift, alter_s=True,
                                                      interactive=5,
                                                      sequence=2)

        # Submit a job to the reservation and change its start time.
        self.submit_job_to_resv(rid)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      -shift, alter_s=True,
                                                      sequence=3)

    def test_alter_advance_resv_start_time_after_run(self):
        """
        This test case covers the below scenarios for an advance reservation
        that has started running.

        1. Make an advance reservation start late (empty reservation)
        2. Make an advance reservation start late (with a job in it)

        Only operation 1 should be successful, operation 2 should fail.
        """
        offset = 10
        duration = 20
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Changing start time should be allowed as the reservation is empty.
        self.alter_a_reservation(rid, start, end, shift, alter_s=True)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Submit a job to the reservation.
        self.submit_job_to_resv(rid)

        # Changing start time should fail this time as it is not empty.
        self.alter_a_reservation(rid, start, end, shift, alter_s=True,
                                 whichMessage=0)

    def test_alter_advance_resv_end_time_before_run(self):
        """
        This test case covers the below scenarios for an advance reservation
        that has not started running.

        1. Make an advance reservation end late (empty reservation)
        2. Make an advance reservation end late (empty reservation)
        3. Make an advance reservation end late (with a job in it)

        All the above operations are expected to be successful.
        """
        duration = 20
        shift = 10
        offset = 60
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        new_start, new_end = self.alter_a_reservation(rid, start, end, shift,
                                                      alter_e=True, sequence=1)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      shift, alter_e=True,
                                                      sequence=2)

        # Submit a job to the reservation.
        self.submit_job_to_resv(rid)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      shift, alter_e=True,
                                                      sequence=3)

    def test_alter_advance_resv_end_time_after_run(self):
        """
        This test case covers the below scenarios for an advance reservation
        that has started running.

        1. Make an advance reservation end late (with a job in it)

        The above operation is expected to be successful.
        """
        duration = 20
        shift = 30
        offset = 10
        sleep = 45
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        # Submit a job to the reservation.
        jid = self.submit_job_to_resv(rid, sleep)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        self.alter_a_reservation(rid, start, end, shift, alter_e=True,
                                 confirm=False)

        self.check_resv_running(rid, duration, 0)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

    def test_alter_advance_resv_both_times_before_run(self):
        """
        This test case covers the below scenarios for an advance reservation
        that has not started running.

        1. Make an advance reservation start and end late (empty reservation)
        2. Make an advance reservation start and end early (empty reservation)
        3. Make an advance reservation start and end early (with a job in it)

        All the above operations are expected to be successful.
        """
        offset = 60
        duration = 20
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        new_start, new_end = self.alter_a_reservation(rid, start, end,
                                                      shift, alter_s=True,
                                                      alter_e=True, sequence=1)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      -shift, alter_s=True,
                                                      alter_e=True, sequence=2)

        # Submit a job to the reservation and change its start time.
        self.submit_job_to_resv(rid)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      -shift, alter_s=True,
                                                      alter_e=True, sequence=3)

    def test_alter_advance_resv_both_times_after_run(self):
        """
        This test case covers the below scenarios for an advance reservation
        that has started running.

        1. Make an advance reservation start and end late (empty reservation)
        2. Make an advance reservation start and end late (with a job in it)

        Only operation 1 should be successful, operation 2 should fail.
        """
        offset = 10
        duration = 200
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Changing start time should be allowed as the reservation is empty.
        new_start, new_end = self.alter_a_reservation(rid, start, end,
                                                      shift, alter_s=True,
                                                      alter_e=True)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Submit a job to the reservation.
        self.submit_job_to_resv(rid)

        # Changing start time should fail this time as it is not empty.
        self.alter_a_reservation(rid, new_start, new_end,
                                 shift, alter_s=True,
                                 alter_e=True, whichMessage=0)

    def test_alter_standing_resv_start_time_before_run(self):
        """
        This test case covers the below scenarios for a standing reservation
        that has not started running.

        1. Make an occurrence of a standing reservation start
           late (empty reservation)
        2. Make an occurrence of a standing reservation start
           early (empty reservation)
        3. Make an occurrence of a standing reservation start
           early (with a job in it)
        4. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        All the above operations are expected to be successful.
        """
        offset = 30
        duration = 20
        shift = 15
        rid, start, end = self.submit_and_confirm_reservation(offset,
                                                              duration,
                                                              standing=True)

        new_start, new_end = self.alter_a_reservation(rid, start, end, shift,
                                                      alter_s=True, sequence=1)

        new_start, new_end = self.alter_a_reservation(rid, new_start,
                                                      new_end, -shift,
                                                      alter_s=True, sequence=2)

        # Submit a job to the reservation and change its start time.
        self.submit_job_to_resv(rid)

        new_start, new_end = self.alter_a_reservation(rid, new_start,
                                                      new_end, -shift,
                                                      alter_s=True, sequence=3)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset - shift)

        # Wait for the reservation occurrence to finish.
        new_duration = new_end - new_start
        self.check_occr_finish(rid, new_duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_alter_standing_resv_start_time_after_run(self):
        """
        This test case covers the below scenarios for a standing reservation
        that has started running.

        1. Make an occurrence of a standing reservation start
           late (empty reservation)
        2. Make an occurrence of a standing reservation start
           late (with a job in it)
        3. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        Only operations 1 and 3 should be successful, operation 2 should fail.
        """
        offset = 10
        duration = 20
        shift = 15
        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              standing=True)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Changing start time should be allowed as the reservation is empty.
        new_start, new_end = self.alter_a_reservation(rid, start, end, shift,
                                                      alter_s=True)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Submit a job to the reservation.
        self.submit_job_to_resv(rid, sleep=15)

        # Changing start time should fail this time as it is not empty.
        self.alter_a_reservation(rid, new_start, new_end, shift,
                                 alter_s=True, whichMessage=False)

        # Wait for the reservation occurrence to finish.
        new_duration = new_end - new_start
        self.check_occr_finish(rid, new_duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_alter_standing_resv_end_time_before_run(self):
        """
        This test case covers the below scenarios for a standing reservation
        that has not started running and some scenarios after it starts
        running.

        1. Make an occurrence of a standing reservation end
           late (empty reservation)
        2. Make an occurrence of a standing reservation end early
           (empty reservation)
        3. Make an occurrence of a standing reservation end
           late (with a job in it)
        4. Check if the reservation continues to be in Running state after the
           original end time has passed.
        5. Verify that the job inside this reservation also continues to run
           after the original end time has passed.
        6. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        All the above operations are expected to be successful.
        """
        duration = 30
        shift = 10
        offset = 30
        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              standing=True)

        new_start, new_end = self.alter_a_reservation(rid, start, end, shift,
                                                      alter_e=True, sequence=1)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      -shift, alter_e=True,
                                                      sequence=2)

        # Submit a job to the reservation.
        jid = self.submit_job_to_resv(rid, 100)

        new_start, new_end = self.alter_a_reservation(rid, start, end, shift,
                                                      alter_e=True, sequence=3)

        self.check_resv_running(rid, offset)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

        # Sleep for the actual duration.
        time.sleep(duration)
        self.check_resv_running(rid)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

        # Wait for the reservation occurrence to finish.
        self.check_occr_finish(rid, shift)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_alter_standing_resv_end_time_after_run(self):
        """
        This test case covers the below scenarios for a standing reservation
        that has started running.

        1. Make an occurrence of a standing reservation end
           late (with a job in it)
        2. Check if the reservation continues to be in Running state after the
           original end time has passed.
        3. Verify that the job inside this reservation also continues to run
           after the original end time has passed.
        4. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        All the above operations are expected to be successful.
        """
        duration = 20
        shift = 10
        offset = 10
        sleep = 30
        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              standing=True)

        # Submit a job to the reservation.
        jid = self.submit_job_to_resv(rid, sleep)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        new_end = self.alter_a_reservation(rid, start, end,
                                           shift, alter_e=True,
                                           confirm=False)[1]

        self.check_resv_running(rid, end - int(time.time()) + 1, True)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

        # Wait for the reservation occurrence to finish.
        new_duration = int(new_end - time.time())
        self.check_occr_finish(rid, new_duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_alter_standing_resv_both_times_before_run(self):
        """
        This test case covers the below scenarios for a standing reservation
        that has not started running.

        1. Make an occurrence of a standing reservation start and end
           late (empty reservation).
        2. Make an occurrence of a standing reservation start and end early
           (empty reservation).
        3. Make an occurrence of a standing reservation start and end early
           (with a job in it).
        4. Check if the reservation starts and ends as per the new times.
        5. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        All the above operations are expected to be successful.
        """
        offset = 40
        duration = 20
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset,
                                                              duration,
                                                              standing=True)

        new_start, new_end = self.alter_a_reservation(rid, start, end,
                                                      shift, alter_s=True,
                                                      alter_e=True, sequence=1)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      -shift, alter_s=True,
                                                      alter_e=True, sequence=2)

        # Submit a job to the reservation and change its start time.
        self.submit_job_to_resv(rid)

        new_start, new_end = self.alter_a_reservation(rid, new_start, new_end,
                                                      -shift, alter_s=True,
                                                      alter_e=True, sequence=3)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset - shift)

        # Wait for the reservation occurrence to finish.
        self.check_occr_finish(rid, duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_alter_standing_resv_both_times_after_run(self):
        """
        This test case covers the below scenarios for a standing reservation
        that has started running.

        1. Make an occurrence of a standing reservation start and end
           late (empty reservation).
        2. Make an occurrence of a standing reservation start and end
           late (with a job in it).
        3. Check if the reservation starts and ends as per the new times.
        4. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        Only scenario 1, 3 and 4 should be successful, operation 3
        should fail.
        """
        offset = 10
        duration = 20
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              standing=True)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Changing start time should be allowed as the reservation is empty.
        new_start, new_end = self.alter_a_reservation(rid, start, end,
                                                      shift, alter_s=True,
                                                      alter_e=True,
                                                      confirm=False)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        # Submit a job to the reservation.
        self.submit_job_to_resv(rid)

        # Changing start time should fail this time as it is not empty.
        self.alter_a_reservation(rid, new_start, new_end, shift,
                                 alter_s=True, alter_e=True,
                                 whichMessage=False)

        # Wait for the reservation occurrence to finish.
        self.check_occr_finish(rid, duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_conflict_two_advance_resvs(self):
        """
        This test confirms that an advance reservation cannot be extended
        (made to end late) if there is a conflicting reservation and all the
        nodes in the complex are busy.

        Two back to back advance reservations are submitted that use all the
        nodes in the complex to test this.
        """
        duration = 120
        shift = 10
        offset1 = 60
        offset2 = 180

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration, select="2:ncpus=4")
        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset2, duration, select="2:ncpus=4")
        self.submit_and_confirm_reservation(offset1, duration,
                                            select="2:ncpus=4",
                                            ExpectSuccess=0)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_e=True,
                                 whichMessage=3)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_e=True,
                                 whichMessage=3, interactive=5, sequence=2)
        self.alter_a_reservation(rid2, start2, end2, -shift, alter_s=True,
                                 whichMessage=3)
        self.alter_a_reservation(rid2, start2, end2, -shift, alter_s=True,
                                 whichMessage=3, interactive=5, sequence=2)

    def test_conflict_two_standing_resvs(self):
        """
        This test confirms that an occurrence of a standing reservation cannot
        be extended (made to end late) if there is a conflicting reservation
        and all the nodes in the complex are busy.

        Two back to back standing reservations are submitted that use all the
        nodes in the complex to test this.
        """
        duration = 120
        shift = 10
        offset1 = 60
        offset2 = 180

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration, select="2:ncpus=4", standing=True)
        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset2, duration, select="2:ncpus=4", standing=True)
        self.submit_and_confirm_reservation(offset1, duration,
                                            select="2:ncpus=4",
                                            ExpectSuccess=0, standing=True)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_e=True,
                                 whichMessage=3)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_e=True,
                                 whichMessage=3, interactive=5, sequence=2)
        self.alter_a_reservation(rid2, start2, end2, -shift, alter_s=True,
                                 whichMessage=3)
        self.alter_a_reservation(rid2, start2, end2, -shift, alter_s=True,
                                 whichMessage=3, interactive=5, sequence=2)

    def test_check_alternate_nodes_advance_resv_endtime(self):
        """
        This test confirms that an advance reservation can be extended even if
        there is a conflicting reservation but there are nodes in the complex
        that satisfy the resource requirements of the reservation.

        Two back to back advance reservations are submitted that use the
        same nodes in the complex to test this and end time of the later
        reservation is altered.
        """
        duration = 120
        shift = 10
        offset1 = 60
        offset2 = 180

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration, select="1:ncpus=4")

        self.server.status(RESV, 'resv_nodes', id=rid1)
        resv_node = self.server.reservations[rid1].get_vnodes()[0]
        select = "1:vnode=" + resv_node + ":ncpus=4"
        rid2 = self.submit_and_confirm_reservation(
            offset2, duration, select=select)[0]

        attrs = {'resv_nodes': (MATCH_RE, re.escape(resv_node))}
        self.server.expect(RESV, attrs, id=rid2)

        nodes = self.server.status(NODE)
        free_node = nodes[resv_node == nodes[0]['id']]['id']

        self.alter_a_reservation(rid1, start1, end1, shift, alter_e=True)
        attrs = {'resv_nodes': (MATCH_RE, re.escape(free_node))}
        self.server.expect(RESV, attrs, id=rid1)

    def test_check_alternate_nodes_advance_resv_starttime(self):
        """
        This test confirms that an advance reservation can be extended even if
        there is a conflicting reservation but there are nodes in the complex
        that satisfy the resource requirements of the reservation.

        Two back to back advance reservations are submitted that use the
        same nodes in the complex to test this and start time of the former
        reservation is altered.
        """
        duration = 120
        shift = 40
        offset1 = 180
        offset2 = 30

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration, select="1:ncpus=4")

        self.server.status(RESV, 'resv_nodes', id=rid1)
        resv_node = self.server.reservations[rid1].get_vnodes()[0]

        select = "1:vnode=" + resv_node + ":ncpus=4"
        rid2 = self.submit_and_confirm_reservation(offset2, duration,
                                                   select=select)[0]

        attrs = {'resv_nodes': (MATCH_RE, re.escape(resv_node))}
        self.server.expect(RESV, attrs, id=rid2)

        nodes = self.server.status(NODE)
        free_node = nodes[resv_node == nodes[0]['id']]['id']

        self.alter_a_reservation(rid1, start1, end1, -shift, alter_s=True)
        attrs = {'resv_nodes': (MATCH_RE, re.escape(free_node))}
        self.server.expect(RESV, attrs, id=rid1)

    def test_check_alternate_nodes_standing_resv_endtime(self):
        """
        This test confirms that an occurrence of a standing reservation can be
        extended even if there is a conflicting reservation but there are
        nodes in the complex that satisfy the resource requirements of the
        reservation.

        Two back to back standing reservations are submitted that use the
        same nodes in the complex to test this and end time of the later
        reservation is altered.
        """
        duration = 120
        shift = 10
        offset1 = 60
        offset2 = 180

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration, standing=True)

        self.server.status(RESV, 'resv_nodes', id=rid1)
        resv_node = self.server.reservations[rid1].get_vnodes()[0]

        select = "1:vnode=" + resv_node + ":ncpus=4"
        rid2 = self.submit_and_confirm_reservation(offset2, duration,
                                                   select=select,
                                                   standing=True)[0]

        attrs = {'resv_nodes': (MATCH_RE, re.escape(resv_node))}
        self.server.expect(RESV, attrs, id=rid2)

        nodes = self.server.status(NODE)
        free_node = nodes[resv_node == nodes[0]['id']]['id']

        self.alter_a_reservation(rid1, start1, end1, shift, alter_e=True)
        attrs = {'resv_nodes': (MATCH_RE, re.escape(free_node))}
        self.server.expect(RESV, attrs, id=rid1)

    def test_check_alternate_nodes_standing_resv_starttime(self):
        """
        This test confirms that an advance reservation can be extended even if
        there is a conflicting reservation but there are nodes in the complex
        that satisfy the resource requirements of the reservation.

        Two back to back advance reservations are submitted that use the
        same nodes in the complex to test this and start time of the former
        reservation is altered.
        """
        duration = 120
        shift = 40
        offset1 = 30
        offset2 = 180

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset2, duration, select="1:ncpus=4", standing=True)

        self.server.status(RESV, 'resv_nodes', id=rid1)
        resv_node = self.server.reservations[rid1].get_vnodes()[0]

        select = "1:vnode=" + resv_node + ":ncpus=4"
        rid2 = self.submit_and_confirm_reservation(offset1, duration,
                                                   select=select,
                                                   standing=True)[0]

        attrs = {'resv_nodes': (MATCH_RE, re.escape(resv_node))}
        self.server.expect(RESV, attrs, id=rid2)

        nodes = self.server.status(NODE)
        free_node = nodes[resv_node == nodes[0]['id']]['id']

        self.alter_a_reservation(rid1, start1, end1, -shift, alter_s=True)
        attrs = {'resv_nodes': (MATCH_RE, re.escape(free_node))}
        self.server.expect(RESV, attrs, id=rid1)

    def test_conflict_standing_resv_occurrence(self):
        """
        This test confirms that if the requested time while altering an
        occurrence of a standing reservation will conflict with a later
        occurrence of the same standing reservation, the alter request
        will be denied.
        """
        duration = 60
        shift = 10
        offset = 10

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="1:ncpus=4", standing=True,
            rrule="FREQ=MINUTELY;COUNT=2")

        self.alter_a_reservation(rid, start, end, shift, alter_e=True,
                                 whichMessage=0)

    def test_large_resv_nodes_server_crash(self):
        """
        This test is to test whether the server crashes or not when a very
        large resv_nodes is being recorded in the 'Y' accounting log.
        If tested with a build without the fix, the test case will fail
        and vice versa.
        """
        duration = 60
        shift = 10
        offset = 10

        a = {'resources_available.ncpus': 4}
        self.mom.create_vnodes(a, num=256,
                               usenatvnode=True)

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="256:ncpus=4")

        self.alter_a_reservation(rid, start, end, shift, alter_s=True)

    def test_alter_advance_resv_boundary_values(self):
        """
        This test checks the alter of start and end times at the boundary
        values for advance reservation.
        """
        duration = 30
        shift = 5
        offset = 100

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration)

        start, end = self.alter_a_reservation(
            rid, start, end, shift, alter_e=True, sequence=1)
        start, end = self.alter_a_reservation(
            rid, start, end, -shift, alter_e=True, sequence=2)
        start, end = self.alter_a_reservation(
            rid, start, end, shift, alter_s=True, sequence=3)
        self.alter_a_reservation(
            rid, start, end, -shift, alter_s=True, sequence=4)

    def test_alter_standing_resv_boundary_values(self):
        """
        This test checks the alter of start and end times at the boundary
        values for standing reservation.
        """
        duration = 30
        shift = 5
        offset = 100

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, standing=True)

        start, end = self.alter_a_reservation(
            rid, start, end, shift, alter_e=True, sequence=1)
        start, end = self.alter_a_reservation(
            rid, start, end, -shift, alter_e=True, sequence=2)
        start, end = self.alter_a_reservation(
            rid, start, end, shift, alter_s=True, sequence=3)
        self.alter_a_reservation(
            rid, start, end, -shift, alter_s=True, sequence=4)

    def test_alter_degraded_resv_mom_down(self):
        """
        This test checks the alter of start and end times of reservations
        when mom is down.
        """
        duration = 30
        shift = 5
        offset = 200

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset, duration, select="1:ncpus=2")
        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset, duration, select="1:ncpus=2", standing=True)
        self.mom.stop()
        msg = 'mom is not down'
        self.assertFalse(self.mom.isUp(max_attempts=5), msg)
        attrs = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}
        self.server.expect(RESV, attrs, id=rid1)
        self.server.expect(RESV, attrs, id=rid2)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, sequence=1)
        self.alter_a_reservation(rid2, start2, end2, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, sequence=1)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, interactive=2,
                                 sequence=2)
        self.alter_a_reservation(rid2, start2, end2, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, interactive=2,
                                 sequence=2)
        self.mom.start()
        # test same for node offline case
        attrs1 = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs1, id=rid1)
        self.server.expect(RESV, attrs1, id=rid2)
        resv_node1 = self.server.status(RESV, 'resv_nodes', id=rid1)[0][
            'resv_nodes'].split(':')[0].split('(')[1]
        resv_node2 = self.server.status(RESV, 'resv_nodes', id=rid2)[0][
            'resv_nodes'].split(':')[0].split('(')[1]
        mtype = 0
        seq = 0
        if resv_node1 == resv_node2:
            self.server.manager(MGR_CMD_SET, NODE, {
                                'state': "offline"}, id=resv_node1)
            mtype = 1
            seq = 1
        else:
            self.server.manager(MGR_CMD_SET, NODE, {
                                'state': "offline"}, id=resv_node1)
            self.server.manager(MGR_CMD_SET, NODE, {
                                'state': "offline"}, id=resv_node2)
            mtype = 3
            seq = 3

        self.server.expect(RESV, attrs, id=rid1)
        self.server.expect(RESV, attrs, id=rid2)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_s=True,
                                 alter_e=True, whichMessage=mtype,
                                 sequence=seq)
        self.alter_a_reservation(rid2, start2, end2, shift, alter_s=True,
                                 alter_e=True, whichMessage=mtype,
                                 sequence=seq)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_s=True,
                                 alter_e=True, whichMessage=mtype,
                                 interactive=2, sequence=seq + 1)
        self.alter_a_reservation(rid2, start2, end2, shift, alter_s=True,
                                 alter_e=True, whichMessage=mtype,
                                 interactive=2, sequence=seq + 1)

    def test_alter_resv_name(self):
        """
        This test checks the alter of reservation name.
        """
        duration = 30
        offset = 20

        rid1 = self.submit_and_confirm_reservation(
            offset, duration)
        attr1 = {ATTR_N: "Adv_Resv"}
        self.server.alterresv(rid1[0], attr1)
        attr1 = {'Reserve_Name': "Adv_Resv"}
        self.server.expect(RESV, attr1, id=rid1[0])
        rid2 = self.submit_and_confirm_reservation(
            offset, duration, standing=True)
        attr2 = {ATTR_N: "Std_Resv"}
        self.server.alterresv(rid2[0], attr2)
        attr2 = {'Reserve_Name': "Std_Resv"}
        self.server.expect(RESV, attr2, id=rid2[0])

    def test_alter_user_permission(self):
        """
        This test checks the user permissions for pbs_ralter.
        """
        duration = 30
        offset = 20
        shift = 10

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset, duration)
        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset, duration, standing=True)
        new_start1 = self.bu.convert_seconds_to_datetime(start1 + shift)
        new_start2 = self.bu.convert_seconds_to_datetime(start2 + shift)
        new_end1 = self.bu.convert_seconds_to_datetime(end1 + shift)
        new_end2 = self.bu.convert_seconds_to_datetime(end2 + shift)
        try:
            attr = {'reserve_start': new_start1, 'reserve_end': new_end1}
            self.server.alterresv(rid1, attr, runas=TEST_USER1)
        except PbsResvAlterError as e:
            self.assertTrue("Unauthorized Request" in e.msg[0])
        try:
            attr = {'reserve_start': new_start2, 'reserve_end': new_end2}
            self.server.alterresv(rid2, attr, runas=TEST_USER1)
        except PbsResvAlterError as e:
            self.assertTrue("Unauthorized Request" in e.msg[0])

    def test_auth_user(self):
        """
        This test checks changing Authorized_Users
        """
        duration = 30
        offset = 1000
        rid = self.submit_and_confirm_reservation(offset, duration)[0]

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        with self.assertRaises(PbsSubmitError):
            self.submit_job_to_resv(rid, user=TEST_USER1)

        attr = {ATTR_auth_u: str(TEST_USER1)}
        self.server.alterresv(rid, attr)

        with self.assertRaises(PbsSubmitError):
            self.submit_job_to_resv(rid, user=TEST_USER)

        jid = self.submit_job_to_resv(rid, user=TEST_USER1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        attr = {ATTR_auth_u: str(TEST_USER) + ',' + str(TEST_USER1)}
        self.server.alterresv(rid, attr)

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        jid = self.submit_job_to_resv(rid, user=TEST_USER1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        attr = {ATTR_auth_u: str(TEST_USER) + ',-' + str(TEST_USER1)}
        self.server.alterresv(rid, attr)

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        with self.assertRaises(PbsSubmitError):
            self.submit_job_to_resv(rid, user=TEST_USER1)

    @skipOnShasta
    def test_auth_group(self):
        """
        This test checks changing Authorized_Groups
        Skipped on shasta due to groups not being setup on the server
        """
        duration = 30
        offset = 1000
        rid = self.submit_and_confirm_reservation(offset, duration)[0]

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        with self.assertRaises(PbsSubmitError):
            self.submit_job_to_resv(rid, user=TEST_USER4)

        attr = {ATTR_auth_g: str(TSTGRP0) + ',' + str(TSTGRP1)}
        self.server.alterresv(rid, attr)

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        with self.assertRaises(PbsSubmitError):
            self.submit_job_to_resv(rid, user=TEST_USER4)

        attr = {ATTR_auth_u: str(TEST_USER) + ',' + str(TEST_USER4),
                ATTR_auth_g: str(TSTGRP0) + ',' + str(TSTGRP1)}
        self.server.alterresv(rid, attr)

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        jid = self.submit_job_to_resv(rid, user=TEST_USER4)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

    @skipOnShasta
    def test_auth_group_restart(self):
        """
        This test checks changing Authorized_Groups survives a server restart
        Skipped on shasta due to groups not being setup on the server
        """
        self.skipTest('skipped due to existing bug unsetting attributes')
        duration = 30
        offset = 1000
        rid = self.submit_and_confirm_reservation(offset, duration)[0]
        qid = rid.split('.')[0]

        attr = {ATTR_auth_g: str(TSTGRP0) + ',' + str(TSTGRP1)}
        self.server.alterresv(rid, attr)
        attr2 = {
            ATTR_aclgroup: attr[ATTR_auth_g],
            ATTR_aclgren: 'True'
        }

        self.server.expect(RESV, attr, id=rid, max_attempts=5)
        self.server.expect(QUEUE, attr2, id=qid, max_attempts=5)

        self.server.restart()

        self.server.expect(RESV, attr, id=rid, max_attempts=5)
        self.server.expect(QUEUE, attr2, id=qid, max_attempts=5)

        attr = {ATTR_auth_g: ''}
        self.server.alterresv(rid, attr)

        attr = [ATTR_auth_g]
        attr2 = [ATTR_aclgroup, ATTR_aclgren]
        self.server.expect(RESV, attr, op=UNSET, id=rid, max_attempts=5)
        self.server.expect(QUEUE, attr2, op=UNSET, id=qid, max_attempts=5)

        self.server.restart()

        self.server.expect(RESV, attr, op=UNSET, id=rid, max_attempts=5)
        self.server.expect(QUEUE, attr2, op=UNSET, id=qid, max_attempts=5)

    def test_ralter_psets(self):
        """
        Test that PBS will not place a job across placement sets after
        successfully being altered
        """
        duration = 120
        offset1 = 30
        offset2 = 180

        a = {'type': 'string', 'flag': 'h'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='color')

        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.mom.create_vnodes(a, 3)

        a = {'resources_available.color': 'red'}
        vn = self.mom.shortname
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn + '[0]')
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn + '[1]')
        a = {'resources_available.color': 'green'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn + '[2]')

        a = {'node_group_key': 'color', 'node_group_enable': True}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration, select="2:ncpus=4")

        self.server.status(RESV)
        nodes = self.server.reservations[rid1].get_vnodes()

        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset2, duration, select="1:ncpus=4:vnode=" + nodes[0])

        c = 'resources_available.color'
        color1 = self.server.status(NODE, c, id=nodes[0])[0][c]
        color2 = self.server.status(NODE, c, id=nodes[1])[0][c]
        self.assertEqual(color1, color2)

        self.alter_a_reservation(rid1, start1, end1, shift=300,
                                 alter_e=True, whichMessage=3)

        t = start1 - int(time.time())
        self.logger.info('Sleeping until reservation starts')
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
                           id=rid1, offset=t)

        # sequence=2 because we'll get one message from the last alter attempt
        # and one message from this alter attempt
        self.alter_a_reservation(rid1, start1, end1, shift=300,
                                 alter_e=True, sequence=2, whichMessage=3)

    def test_failed_ralter(self):
        """
        Test that a failed ralter does not allow jobs to interfere with
        that reservation.
        """
        duration = 120
        offset1 = 30
        offset2 = 180

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration, select="2:ncpus=4")

        j = Job(attrs={'Resource_List.walltime': 100})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q',
                                 'comment': (MATCH_RE, 'Not Running')}, id=jid)

        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset2, duration, select="2:ncpus=4")

        self.alter_a_reservation(rid1, start1, end1, shift=300,
                                 alter_e=True, whichMessage=3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        self.logger.info('Sleeping until reservation starts')
        t = start1 - int(time.time())
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_RUNNING|5')},
                           offset=t, id=rid1)

        self.alter_a_reservation(rid1, start1, end1, shift=300,
                                 alter_e=True, sequence=2, whichMessage=3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

    def test_adv_resv_duration_before_start(self):
        """
        Test duration of reservation can be changed. In this case end
        time changes, and start time remains the same.
        """

        offset = 20
        duration = 20
        new_duration = 30
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        self.alter_a_reservation(rid, start, end, a_duration=new_duration,
                                 check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)

        self.assertEqual(t_end, end + shift)
        self.assertEqual(t_start, start)
        self.assertEqual(t_duration, new_duration)

        # Submit a job to the reservation and change its duration.
        self.submit_job_to_resv(rid)

        temp_end = t_end
        temp_start = t_start

        new_duration2 = new_duration + 10
        self.alter_a_reservation(rid, temp_start, temp_end, sequence=2,
                                 a_duration=new_duration2, check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_end, temp_end + shift)
        self.assertEqual(t_start, temp_start)
        self.assertEqual(t_duration, new_duration2)

        sleepdur = (temp_end + shift / 2) - time.time()
        self.logger.info('Sleeping until reservation would have ended')
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
                           id=rid, max_attempts=5, offset=sleepdur)

    def test_adv_resv_dur_and_endtime_before_start(self):
        """
        Test that duration and end time of reservation can be changed together.
        In this case the start time of reservation may also change.
        """

        offset = 20
        duration = 20
        new_duration = 40
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        self.alter_a_reservation(rid, start, end, shift=shift,
                                 alter_e=True, a_duration=new_duration,
                                 check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)

        self.assertEqual(t_end, end + shift)
        self.assertEqual(t_start, t_end - t_duration)
        self.assertEqual(t_duration, new_duration)

        # Submit a job to the reservation and change its start time.
        self.submit_job_to_resv(rid)
        temp_end = t_end
        temp_start = t_start

        new_duration2 = new_duration + 10
        self.alter_a_reservation(rid, temp_start, temp_end, shift=shift,
                                 alter_e=True, sequence=2,
                                 a_duration=new_duration2, check_log=False)
        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_end, temp_end + shift)
        self.assertEqual(t_start, t_end - t_duration)
        self.assertEqual(t_duration, new_duration2)

    def test_adv_resv_dur_and_starttime_before_start(self):
        """
        Test duration and starttime of reservation can be changed together.
        In this case the endtime will change accordingly
        """

        offset = 20
        duration = 20
        new_duration = 30
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        self.alter_a_reservation(rid, start, end, shift=shift,
                                 alter_s=True, a_duration=new_duration,
                                 check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)

        self.assertEqual(t_end, t_start + t_duration)
        self.assertEqual(t_start, start + shift)
        self.assertEqual(t_duration, new_duration)

        # Submit a job to the reservation and change its start time.
        self.submit_job_to_resv(rid)
        temp_end = t_end
        temp_start = t_start

        new_duration2 = new_duration + 10
        self.alter_a_reservation(rid, temp_start, temp_end, shift=shift,
                                 alter_s=True, sequence=2,
                                 a_duration=new_duration2, check_log=False)
        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_end, t_start + t_duration)
        self.assertEqual(t_start, temp_start + shift)
        self.assertEqual(t_duration, new_duration2)

    def test_adv_res_dur_after_start(self):
        """
        Test that duration can be changed after the reservation starts.
        Test that if the duration changes endtime of the reservation to an
        already passed time, the reservation is deleted
        """
        offset = 10
        duration = 20
        new_duration = 30
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        self.check_resv_running(rid, offset)

        self.alter_a_reservation(rid, start, end, a_duration=new_duration,
                                 confirm=False, check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_duration, new_duration)

        time.sleep(5)
        new_duration = int(time.time()) - int(t_start) - 1
        attr = {'reserve_duration': new_duration}
        self.server.alterresv(rid, attr)
        msg = "Resv;" + rid + ";Reservation alter confirmed"
        self.server.log_match(msg, id=rid)
        rid = rid.split('.')[0]
        self.server.log_match(rid + ";deleted at request of pbs_server",
                              id=rid, interval=2)

    def test_adv_resv_endtime_starttime_dur_together(self):
        """
        Test that all three end, start and duration can be changed together.
        If the values of start, end, duration are not reolves properly, this
        test should fail
        """
        offset = 20
        duration = 20
        new_duration = 25
        wrong_duration = 45
        shift_start = 10
        shift_end = 15
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)
        new_start = self.bu.convert_seconds_to_datetime(start + shift_start)
        new_end = self.bu.convert_seconds_to_datetime(end + shift_end)

        with self.assertRaises(PbsResvAlterError) as e:
            attr = {'reserve_start': new_start, 'reserve_end': new_end,
                    'reserve_duration': wrong_duration}
            self.server.alterresv(rid, attr)
        self.assertIn('pbs_ralter: Bad time specification(s)',
                      e.exception.msg[0])

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(int(t_start), start)
        self.assertEqual(int(t_duration), duration)
        self.assertEqual(int(t_end), end)

        attr = {'reserve_start': new_start, 'reserve_end': new_end,
                'reserve_duration': new_duration}
        self.server.alterresv(rid, attr)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(int(t_start), start + shift_start)
        self.assertEqual(int(t_duration), new_duration)
        self.assertEqual(int(t_end), end + shift_end)

    def test_standing_resv_duration(self):
        """
        This test case covers the below scenarios for a standing reservation.

        1. Change duration of standing reservation occurance
        2. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        All the above operations are expected to be successful.
        """
        offset = 20
        duration = 30
        new_duration = 90
        shift = 15
        rid, start, end = self.submit_and_confirm_reservation(offset,
                                                              duration,
                                                              standing=True)

        self.alter_a_reservation(rid, start, end, shift=shift,
                                 a_duration=new_duration, check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_duration, new_duration)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset - shift)

        # Wait for the reservation occurrence to finish.
        new_duration = t_end - t_start
        self.check_occr_finish(rid, new_duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_standing_resv_duration_and_endtime(self):
        """
        This test case covers the below scenarios for a standing reservation.

        1. Change duration and endtime of standing reservation
        2. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        All the above operations are expected to be successful.
        """
        offset = 20
        duration = 20
        new_duration = 30
        shift = 15
        rid, start, end = self.submit_and_confirm_reservation(offset,
                                                              duration,
                                                              standing=True)

        self.alter_a_reservation(rid, start, end, shift=shift, alter_e=True,
                                 a_duration=new_duration, check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_duration, new_duration)
        self.assertEqual(t_end, end + shift)
        self.assertEqual(t_start, t_end - t_duration)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset - shift)

        # Wait for the reservation occurrence to finish.
        new_duration = t_end - t_start
        self.check_occr_finish(rid, new_duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_standing_resv_duration_and_starttime(self):
        """
        This test case covers the below scenarios for a standing reservation.

        1. Change duration and endtime of standing reservation
        2. After the first occurrence of the reservation finishes, verify that
           the start and end time of the second occurrence have not changed.

        All the above operations are expected to be successful.
        """
        offset = 20
        duration = 20
        new_duration = 30
        shift = 15
        rid, start, end = self.submit_and_confirm_reservation(offset,
                                                              duration,
                                                              standing=True)

        self.alter_a_reservation(rid, start, end, shift=shift, alter_s=True,
                                 a_duration=new_duration, check_log=False)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_duration, new_duration)
        self.assertEqual(t_end, t_start + t_duration)
        self.assertEqual(t_start, start + shift)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset - shift)

        # Wait for the reservation occurrence to finish.
        new_duration = t_end - t_start
        self.check_occr_finish(rid, new_duration)

        # Check that duration of the second occurrence is not altered.
        self.check_standing_resv_second_occurrence(rid, start, end)

    def test_conflict_standing_resv_occurrence_duration(self):
        """
        This test confirms that if the requested duration while altering an
        occurrence of a standing reservation will conflict with a later
        occurrence of the same standing reservation, the alter request
        will be denied.
        """
        duration = 60
        new_duration = 70
        shift = 10
        offset = 10

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="1:ncpus=4", standing=True,
            rrule="FREQ=MINUTELY;COUNT=2")

        self.alter_a_reservation(rid, start, end, a_duration=new_duration,
                                 check_log=False, whichMessage=0)

        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(int(t_start), start)
        self.assertEqual(int(t_duration), duration)
        self.assertEqual(int(t_end), end)

    def test_alter_empty_fail(self):
        """
        This test confirms that if a requested ralter fails due to the
        reservation having running jobs, the attributes are kept the same
        """
        offset = 20
        dur = 20
        shift = 120

        rid, start, end = self.submit_and_confirm_reservation(offset, dur)

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid, offset=offset)

        now = int(time.time())
        new_start = self.bu.convert_seconds_to_datetime(now + shift)
        new_end = self.bu.convert_seconds_to_datetime(now + shift + dur)

        # This bug only shows if end time is changed before start time
        ralter_cmd = [
            os.path.join(
                self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_ralter'),
            '-E', str(new_end),
            '-R', str(new_start),
            rid
        ]
        ret = self.du.run_cmd(self.server.hostname, ralter_cmd)
        self.assertIn('pbs_ralter: Reservation not empty', ret['err'][0])

        # Test that the reservation state is Running and not RESV_NONE
        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(int(t_start), start)
        self.assertEqual(int(t_duration), dur)
        self.assertEqual(int(t_end), end)

    def test_duration_in_hhmmss_format(self):
        """
        Test duration input can be in hh:mm:ss format
        """
        offset = 20
        duration = 20
        new_duration = "00:00:30"
        new_duration_in_sec = 30
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        new_end = end + 10

        attr = {'reserve_duration': new_duration}
        self.server.alterresv(rid, attr)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(int(t_start), start)
        self.assertEqual(int(t_duration), new_duration_in_sec)
        self.assertEqual(int(t_end), new_end)

    def test_adv_resv_dur_and_endtime_with_running_jobs(self):
        """
        Test that duration and end time of reservation cannot be changed
        together if there are running jobs inside it. This will fail
        because start time cannot be changed when there are running
        jobs in a reservation.
        """

        offset = 10
        duration = 20
        new_duration = 30
        shift = 10
        rid, start, end = self.submit_and_confirm_reservation(offset, duration)

        self.check_resv_running(rid, offset)

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        new_end = self.bu.convert_seconds_to_datetime(end + 30)
        with self.assertRaises(PbsResvAlterError) as e:
            attr = {'reserve_end': new_end,
                    'reserve_duration': new_duration}
            self.server.alterresv(rid, attr)
        self.assertIn('pbs_ralter: Reservation not empty',
                      e.exception.msg[0])

        # Test that the reservation state is Running and not RESV_NONE
        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)

        self.assertEqual(t_end, end)
        self.assertEqual(t_start, start)
        self.assertEqual(t_duration, duration)

    def test_standing_resv_dur_and_endtime_with_running_jobs(self):
        """
        Change duration and endtime of standing reservation with
        running jobs in it. Verify that the alter fails and
        starttime remains the same
        """
        offset = 10
        duration = 20
        new_duration = 30
        shift = 15
        rid, start, end = self.submit_and_confirm_reservation(offset,
                                                              duration,
                                                              standing=True)

        jid = self.submit_job_to_resv(rid, user=TEST_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid, offset=offset)

        new_end = self.bu.convert_seconds_to_datetime(end + 30)
        with self.assertRaises(PbsResvAlterError) as e:
            attr = {'reserve_end': new_end,
                    'reserve_duration': new_duration}
            self.server.alterresv(rid, attr)
        self.assertIn('pbs_ralter: Reservation not empty',
                      e.exception.msg[0])

        # Test that the reservation state is Running and not RESV_NONE
        attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, attrs, id=rid)

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(t_end, end)
        self.assertEqual(t_start, start)
        self.assertEqual(t_duration, duration)

    def test_duration_walltime(self):
        """
        Check when ralter changes duration, it also changes walltime
        """

        rid, start, end = self.submit_and_confirm_reservation(3600, 600)

        self.server.expect(RESV, {'Resource_List.walltime': 600}, id=rid)

        # Alter start + end
        self.alter_a_reservation(rid, start, end, shift=30, alter_s=True,
                                 alter_e=True)
        self.server.expect(RESV, {'Resource_List.walltime': 600}, id=rid)

        # Alter start + duration
        self.alter_a_reservation(rid, start, end, shift=30, alter_s=True,
                                 a_duration=300, sequence=2)
        self.server.expect(RESV, {'Resource_List.walltime': 300}, id=rid)

        # Alter end + duration
        self.alter_a_reservation(rid, start, end, shift=30, alter_e=True,
                                 a_duration=450, sequence=3)
        self.server.expect(RESV, {'Resource_List.walltime': 450}, id=rid)

        # Alter start + end + duration
        self.alter_a_reservation(rid, start, end, shift=30, alter_e=True,
                                 alter_s=True, a_duration=600, sequence=4)
        self.server.expect(RESV, {'Resource_List.walltime': 600}, id=rid)

    def test_alter_select_basic(self):
        """
        Test basic use of pbs_ralter -l select to shrink a reservation
        We start with a 2 +'d reservation, and then we drop out the 1st and 3rd
        chunk, and then reduce further
        """
        select = "2:ncpus=1:mem=1gb+4:ncpus=1:mem=2gb+2:ncpus=1:mem=3gb"
        aselect1 = "4:ncpus=1:mem=2gb"
        aselect2 = "2:ncpus=1:mem=2gb"

        rid, start, end, rnodes = self.alter_select_initial(True, select)

        self.alter_select(
            rid, start, end, True, aselect1, 4, [], 1)

        self.alter_select(rid, start, end, True, aselect2, 2, [], 2)

    def test_alter_select_basic_running(self):
        """
        Test basic use of pbs_ralter -l select
        to shrink a running reservation
        We start with a 2 +'d reservation, and then we drop out the 1st and 3rd
        chunk, and then reduce further
        """
        select = "2:ncpus=1:mem=1gb+4:ncpus=1:mem=2gb+2:ncpus=1:mem=3gb"
        aselect1 = "4:ncpus=1:mem=2gb"
        aselect2 = "2:ncpus=1:mem=2gb"

        rid, start, end, rnodes = self.alter_select_initial(False, select)

        rnodes2 = self.alter_select(rid, start, end, False, aselect1, 4, [], 1)

        self.alter_select(rid, start, end, False, aselect2, 2, [], 2)

    def test_alter_select_complex(self):
        """
        Test more complex use of pbs_ralter -l select
        to shrink a reservation
        We start with a 2 +'d spec, and shrink each chunk by one, and
        then we shrink further and drop out the middle chunk
        """
        select = "2:ncpus=1:mem=1gb+4:ncpus=1:mem=2gb+2:ncpus=1:mem=3gb"
        aselect1 = "1:ncpus=1:mem=1gb+2:ncpus=1:mem=2gb+1:ncpus=1:mem=3gb"
        aselect2 = "1:ncpus=1:mem=2gb"

        rid, start, end, rnodes = self.alter_select_initial(True, select)

        self.alter_select(rid, start, end, True, aselect1, 4, [], 1)

        self.alter_select(rid, start, end, True, aselect2, 1, [], 2)

    def test_alter_select_complex_running(self):
        """
        Test more complex use of pbs_ralter -l select to
        shrink a running reservation
        We start with a 2 +'d spec, and shrink each chunk by one, and
        then we shrink further and drop out the middle chunk
        """
        select = "2:ncpus=1:mem=1gb+4:ncpus=1:mem=2gb+2:ncpus=1:mem=3gb"
        aselect1 = "1:ncpus=1:mem=1gb+2:ncpus=1:mem=2gb+1:ncpus=1:mem=3gb"
        aselect2 = "1:ncpus=1:mem=2gb"

        rid, start, end, rnodes = self.alter_select_initial(False, select)

        rnodes2 = self.alter_select(rid, start, end, False,
                                    aselect1, 4, [], 1)

        self.alter_select(rid, start, end, False, aselect2, 1, [], 2)

    def test_alter_select_complex2(self):
        """
        Test more complex use of pbs_ralter -l select
        to shrink a reservation
        We start with a 2 +'d chunk and then shrink each chunk by 1
        We then shrink further and drop out the middle chunk
        Lastly we drop out the first chunk
        """
        select = "3:ncpus=1:mem=1gb+2:ncpus=1:mem=2gb+3:ncpus=1:mem=3gb"
        aselect1 = "2:ncpus=1:mem=1gb+1:ncpus=1:mem=2gb+2:ncpus=1:mem=3gb"
        aselect2 = "1:ncpus=1:mem=1gb+1:ncpus=1:mem=3gb"
        aselect3 = "1:ncpus=1:mem=3gb"

        rid, start, end, rnodes = self.alter_select_initial(True, select)

        rnodes2 = self.alter_select(rid, start, end,
                                    True, aselect1, 5, [], 1)

        self.alter_select(rid, start, end, True, aselect2, 2, [], 2)

        self.alter_select(rid, start, end, True, aselect3, 1, [], 3)

    def test_alter_select_complex_running2(self):
        """
        Test more complex use of pbs_ralter -l select to
        shrink a running reservation
        We start with a 2 +'d chunk and then shrink each chunk by 1
        We then shrink further and drop out the middle chunk
        Lastly we drop out the first chunk
        """
        select = "3:ncpus=1:mem=1gb+2:ncpus=1:mem=2gb+3:ncpus=1:mem=3gb"
        aselect1 = "2:ncpus=1:mem=1gb+1:ncpus=1:mem=2gb+2:ncpus=1:mem=3gb"
        aselect2 = "1:ncpus=1:mem=1gb+1:ncpus=1:mem=3gb"
        aselect3 = "1:ncpus=1:mem=3gb"

        rid, start, end, rnodes = self.alter_select_initial(False, select)

        rnodes2 = self.alter_select(rid, start, end,
                                    False, aselect1, 5, [], 1)

        rnodes3 = self.alter_select(rid, start, end,
                                    False, aselect2, 2, [], 2)

        self.alter_select(rid, start, end, False, aselect3, 1, [], 3)

    def test_alter_select_complex_running3(self):
        """
        A complex set of ralters with running jobs
        """
        select = "3:ncpus=1:mem=1gb+2:ncpus=1:mem=2gb+3:ncpus=1:mem=3gb"
        aselect1 = "2:ncpus=1:mem=1gb+1:ncpus=1:mem=2gb+2:ncpus=1:mem=3gb"
        aselect2 = "1:ncpus=1:mem=1gb+1:ncpus=1:mem=3gb"
        aselect3 = "1:ncpus=1:mem=3gb"

        rid, start, end, rnodes = self.alter_select_initial(False, select)
        rq = rid.split('.')[0]

        a = {'queue': rq, 'Resource_List.select': '1:ncpus=1:mem=3gb'}
        J1 = Job(attrs=a)
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        a['Resource_List.select'] = '1:ncpus=1:mem=1gb'
        J2 = Job(attrs=a)
        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        st = self.server.status(JOB)

        nodes1 = J1.get_vnodes(st[0]['exec_vnode'])
        nodes2 = J2.get_vnodes(st[1]['exec_vnode'])
        needed_nodes = [nodes1[0], nodes2[0]]

        self.alter_select(rid, start, end, False, aselect1, 5, needed_nodes, 1)

        self.alter_select(rid, start, end, False, aselect2, 2, needed_nodes, 2)

        # Alter will fail because we're trying to release Jid2's node

        self.alter_select(rid, start, end, False, aselect3, 2,
                          needed_nodes, 1, False)

        self.server.delete(jid2, wait=True)

        self.alter_select(rid, start, end, False, aselect3, 1, nodes1, 3)

    def alter_select_initial(self, confirm, select):
        """
        Submit initial reservation and possibly wait until it starts
        """
        numnodes = 8
        offset = 30
        dur = 3600

        a = {'resources_available.ncpus': 1,
             'resources_available.mem': '8gb'}
        self.mom.create_vnodes(a, num=8)

        rid, start, end = self.submit_and_confirm_reservation(offset, dur,
                                                              select=select)
        st = self.server.status(RESV)
        resv_nodes = self.server.reservations[rid].get_vnodes()

        self.assertEquals(len(st[0]['resv_nodes'].split('+')), numnodes)
        a = {'Resource_List.ncpus': numnodes,
             'Resource_List.nodect': numnodes}
        self.server.expect(RESV, a, id=rid)

        if not confirm:
            a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            off = start - int(time.time())
            self.logger.info('Waiting until reservation runs')
            self.server.expect(RESV, a, id=rid, offset=off)

        return rid, start, end, resv_nodes

    def alter_select(self, rid, start, end,
                     confirm, selectN, numnodes, nodes, seq, success=True):
        """
        Alter a reservation and make sure it is on the correct nodes
        """

        w = 1
        if not success:
            w = 3
        self.alter_a_reservation(rid, start, end, select=selectN,
                                 confirm=confirm, sequence=seq, whichMessage=w)

        st = self.server.status(RESV)
        self.assertEquals(len(st[0]['resv_nodes'].split('+')), numnodes)
        a = {'Resource_List.ncpus': numnodes,
             'Resource_List.nodect': numnodes}
        self.server.expect(RESV, a, id=rid)
        resv_nodes = self.server.reservations[rid].get_vnodes()
        # nodes is a list of nodes we must keep
        for n in nodes:
            self.assertIn(n, resv_nodes, "Required node not in resv_nodes")
        return resv_nodes

    def test_alter_select_with_times(self):
        """
        Modify the select with the start and end times all at once
        """
        offset = 3600
        duration = 3600
        select = '6:ncpus=1'
        new_select = '4:ncpus=1'
        shift = 300

        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              select=select)
        st = self.server.status(RESV)
        self.assertEquals(len(st[0]['resv_nodes'].split('+')), 6)

        self.alter_a_reservation(rid, start, end, alter_s=True, alter_e=True,
                                 shift=shift, select=new_select, interactive=9)

        st = self.server.status(RESV)
        self.assertEquals(len(st[0]['resv_nodes'].split('+')), 4)
        t = int(time.mktime(time.strptime(st[0]['reserve_start'], '%c')))
        self.assertEquals(t, start + shift)

        t = int(time.mktime(time.strptime(st[0]['reserve_end'], '%c')))
        self.assertEquals(t, end + shift)

    def test_alter_select_with_running_jobs(self):
        """
        Test that when a reservation is running and has running jobs,
        that an ralter -lselect will release nodes without running jobs
        """
        offset = 20
        duration = 600
        select = '3:ncpus=4'
        select2 = '2:ncpus=4'
        select3 = '1:ncpus=4'

        a = {'resources_available.ncpus': 4, 'resources_available.mem': '1gb'}
        self.mom.create_vnodes(a, num=3,
                               usenatvnode=True)

        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              select=select)
        resv_queue = rid.split('.')[0]
        a = {'queue': resv_queue}
        j1 = Job(attrs=a)
        jid = self.server.submit(j1)

        self.logger.info('Waiting for reservation to start')
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        off = int(start - time.time())
        self.server.expect(RESV, a, id=rid, offset=off)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.status(JOB)
        job_node = j1.get_vnodes()[0]

        self.alter_a_reservation(rid, start, end,
                                 select=select2, confirm=False)
        self.server.status(RESV)
        resv_nodes = self.server.reservations[rid].get_vnodes()
        errmsg1 = 'Reservation does not have the right number of nodes'
        self.assertEquals(len(resv_nodes), 2, errmsg1)

        errmsg2 = 'Reservation does not contain job node'
        self.assertIn(job_node, resv_nodes, errmsg2)

        self.alter_a_reservation(rid, start, end,
                                 select=select3, confirm=False, sequence=2)
        self.server.status(RESV)
        resv_nodes = self.server.reservations[rid].get_vnodes()

        self.assertEquals(len(resv_nodes), 1, errmsg1)
        self.assertIn(job_node, resv_nodes, errmsg2)

    def test_alter_select_running_degraded(self):
        """
        Test that when a degraded running reservation with a running job is
        altered, the unavailable nodes are released and the node with the
        running job is kept
        """
        offset = 20
        duration = 3600
        select = '3:ncpus=4'
        select2 = '1:ncpus=4'

        a = {'resources_available.ncpus': 4, 'resources_available.mem': '1gb'}
        self.mom.create_vnodes(a, num=3,
                               usenatvnode=True)

        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              select=select)
        resv_queue = rid.split('.')[0]
        self.server.status(RESV)
        resv_nodes = self.server.reservations[rid].get_vnodes()

        self.assertEquals(len(resv_nodes), 3)

        a = {'queue': resv_queue,
             'Resource_List.select': '1:vnode=%s:ncpus=1' % resv_nodes[1]}
        j1 = Job(attrs=a)
        jid = self.server.submit(j1)

        self.logger.info('Waiting for reservation to start')
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        off = int(start - time.time())
        self.server.expect(RESV, a, id=rid, offset=off)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.status(JOB)
        job_node = j1.get_vnodes()[0]

        self.server.manager(MGR_CMD_SET, NODE, {'state': 'offline'},
                            id=resv_nodes[2])

        self.server.expect(RESV, {'reserve_substate': 10}, id=rid)

        self.alter_a_reservation(rid, start, end,
                                 select=select2, confirm=False)
        self.server.status(RESV)
        resv_nodes = self.server.reservations[rid].get_vnodes()

        errmsg1 = 'Reservation does not have the right number of nodes'
        self.assertEquals(len(resv_nodes), 1, errmsg1)

        errmsg2 = 'Reservation does not contain job node'
        self.assertIn(job_node, resv_nodes, errmsg2)

    def test_alter_select_with_times_standing(self):
        """
        Modify the select with start and end times on a standing reservation
        """
        offset = 20
        duration = 20
        select = '6:ncpus=1'
        new_select = '4:ncpus=1'
        shift = 15

        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              select=select,
                                                              standing=True)
        st = self.server.status(RESV)
        self.assertEquals(len(st[0]['resv_nodes'].split('+')), 6)

        self.alter_a_reservation(rid, start, end, alter_s=True, alter_e=True,
                                 shift=shift, select=new_select, interactive=9)

        st = self.server.status(RESV)
        self.assertEquals(len(st[0]['resv_nodes'].split('+')), 4)
        t = int(time.mktime(time.strptime(st[0]['reserve_start'], '%c')))
        self.assertEquals(t, start + shift)

        t = int(time.mktime(time.strptime(st[0]['reserve_end'], '%c')))
        self.assertEquals(t, end + shift)

        t = start + shift - int(time.time())

        self.logger.info('Waiting until reservation starts')
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_RUNNING|5')}, offset=t)

        self.check_standing_resv_second_occurrence(rid, start, end, select)

    def test_alter_select_larger_fail(self):
        """
        Test proper failures if ralter -lselect with a larger select
        """

        offset = 3600
        duration = 3600
        select = '6:ncpus=1'
        select_more = '7:ncpus=1'
        select_extra = '6:ncpus=1+1:ncpus=1:mem=1gb'
        select_different = '6:ncpus=4:mem=1gb'

        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              select=select)

        self.alter_a_reservation(rid, start, end, select=select_more,
                                 whichMessage=0)

        self.alter_a_reservation(rid, start, end, select=select_extra,
                                 whichMessage=0)
        self.alter_a_reservation(rid, start, end, select=select_different,
                                 whichMessage=0)

    def test_standing_multiple_alter(self):
        """
        Test that a standing reservation's second occurrence reverts to the
        original start/end/duration/select if it is altered multiple times
        """

        offset = 60
        shift1 = -20
        shift2 = -30
        dur = 30
        dur2 = 20
        dur3 = 15
        select = '6:ncpus=1'
        select2 = '4:ncpus=1'
        select3 = '2:ncpus=1'

        rid, start, end = \
            self.submit_and_confirm_reservation(offset, dur, select=select,
                                                standing=True,
                                                rrule="FREQ=MINUTELY;COUNT=2")

        self.alter_a_reservation(rid, start, end, alter_s=True,
                                 shift=shift1, a_duration=dur2, select=select2)
        self.alter_a_reservation(rid, start, end, alter_s=True,
                                 shift=shift2, a_duration=dur3,
                                 select=select3, sequence=2)

        t = start - int(time.time()) + shift2

        self.logger.info('Sleeping %ds until resv starts' % (t))
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
                           id=rid, offset=t)

        self.check_standing_resv_second_occurrence(rid, start, end, select,
                                                   freq=60, wait=True)

    def test_select_fail_revert(self):
        """
        Test that when a ralter fails, the select is reverted properly
        """
        offset = 3600
        offset2 = 7200
        shift = 1800
        dur = 3600
        select = '8:ncpus=1'
        select2 = '4:ncpus=1'

        rid, start, end = self.submit_and_confirm_reservation(offset, dur,
                                                              select=select)

        rid2, start2, end2 = self.submit_and_confirm_reservation(offset2, dur,
                                                                 select=select)

        self.alter_a_reservation(rid, start, end, alter_s=True, alter_e=True,
                                 shift=shift, select=select2, whichMessage=3)

        a = {'Resource_List.select': '8:ncpus=1', 'Resource_List.ncpus': 8,
             'Resource_List.nodect': 8}
        self.server.expect(RESV, a, id=rid)

    def test_resv_resc_assigned(self):
        """
        Test that when an ralter -D is issued, the resources on the node
        are still correct
        """

        offset = 60
        dur = 60
        select = '4:ncpus=1'

        rid, start, end = self.submit_and_confirm_reservation(offset, dur,
                                                              select=select)

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]

        sleepdur = start - time.time()
        self.logger.info('Sleeping until reservation starts')
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
                           offset=sleepdur)
        self.alter_a_reservation(rid, start, end, a_duration=600,
                                 confirm=False)
        self.server.expect(NODE, {'resources_assigned.ncpus': 4},
                           max_attempts=1, id=resv_node)

    def test_alter_start_standing_resv_future_occrs(self):
        """
        Test that when start time of a confirmed standing reservation is
        altered, only the upcoming occurence changes and not all occurences
        are modified.
        """

        duration = 20
        offset = 3600
        shift = -3000

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="2:ncpus=4", standing=True,
            rrule="FREQ=HOURLY;COUNT=3")

        # move the reservation 10 mins in future
        self.alter_a_reservation(rid, start, end, confirm=True, alter_s=True,
                                 alter_e=True, shift=shift)
        # Ideally this reservation should confirm because second occurrence
        # of the first reservation happens in almost 2 hrs from now.
        rid2, start, end = self.submit_and_confirm_reservation(
            3000, 1800, select="2:ncpus=4")

    def test_alter_duration_standing_resv_future_occrs(self):
        """
        Test that when duration of a confirmed standing reservation is
        altered, only the upcoming occurence changes and not all occurences
        are modified.
        """

        duration = 180
        offset = 300

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="2:ncpus=4", standing=True,
            rrule="FREQ=HOURLY;COUNT=3")

        # change the reservation's duration to 20 seconds
        self.alter_a_reservation(rid, start, end, confirm=True, a_duration=20)

        # Submit another reservation that starts in 1hr and 30 seconds.
        # Ideally, in 1 hr second occurrence of reservation will start running
        # and it will run for 3 mins. This means the new reservation will be
        # denied.
        new_offset = (start + 3630) - time.time()
        rid2, start, end = self.submit_and_confirm_reservation(
            new_offset, 180, select="2:ncpus=4", ExpectSuccess=0)

    def test_ralter_force_start_end_confirmed_resv(self):
        """
        Test that forcefully altering a confirmed reservation takes effect.
        Especially when there are conflicting reservations
        """

        duration1 = 3600
        offset1 = 3600

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset1, duration1, select="2:ncpus=4")

        duration2 = 1800
        offset2 = 600

        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset2, duration2, select="2:ncpus=4")

        self.alter_a_reservation(rid1, start1, end1, confirm=True, shift=-3000,
                                 alter_s=True, alter_e=True, extend='force')
        t_duration, t_start, t_end = self.get_resv_time_info(rid1)
        start1 = start1 - 3000
        end1 = end1 - 3000
        self.assertEqual(int(t_start), start1)
        self.assertEqual(int(t_duration), duration1)
        self.assertEqual(int(t_end), end1)

        # Try the same alter but in interactive mode
        duration = 300
        self.alter_a_reservation(rid1, start1, end1, confirm=True,
                                 a_duration=duration, extend='force',
                                 interactive=10, sequence=2)
        t_duration, _, _ = self.get_resv_time_info(rid1)
        self.assertEqual(int(t_duration), duration)

    def test_ralter_force_start_end_unconfirmed_resv(self):
        """
        Test that forcefully altering unconfirmed reservation takes effect.
        """

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'False'})

        duration = 3600
        offset = 3600

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="2:ncpus=4", ExpectSuccess=2)
        attrs = {}
        new_start = start - 1800
        new_end = end - 3600
        new_duration = duration - 1800

        new_start_conv = self.bu.convert_seconds_to_datetime(new_start)
        attrs['reserve_start'] = new_start_conv

        new_end_conv = self.bu.convert_seconds_to_datetime(new_end)
        attrs['reserve_end'] = new_end_conv

        self.server.alterresv(rid, attrs, extend='force')
        msg = "pbs_ralter: " + rid + " CONFIRMED"
        self.assertEqual(msg, self.server.last_out[0])

        t_duration, t_start, t_end = self.get_resv_time_info(rid)
        self.assertEqual(int(t_start), new_start)
        self.assertEqual(int(t_duration), new_duration)
        self.assertEqual(int(t_end), new_end)

        # Try the same alter but in interactive mode
        new_end = new_end - 100
        new_end_conv = self.bu.convert_seconds_to_datetime(new_end)
        attrs['reserve_end'] = new_end_conv
        attrs['interactive'] = 10
        self.server.alterresv(rid, attrs, extend='force')
        msg = "pbs_ralter: " + rid + " CONFIRMED"
        self.assertEqual(msg, self.server.last_out[0])

        _, _, t_end = self.get_resv_time_info(rid)
        self.assertEqual(int(t_end), new_end)
        check_attr = {'reserve_state': (MATCH_RE, 'RESV_UNCONFIRMED|1')}
        self.server.expect(RESV, check_attr, rid)

    def test_alter_force_duration_standing_resv_future_occrs(self):
        """
        Test that when duration of a confirmed standing reservation is
        forcefully altered, only the upcoming occurence changes and not all
        occurrences are modified.
        """

        duration = 180
        offset = 300
        offset_a = 500

        rid_a, start_a, end_a = self.submit_and_confirm_reservation(
            offset_a, duration, select="2:ncpus=4")

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="2:ncpus=4", standing=True,
            rrule="FREQ=HOURLY;COUNT=3")

        # change the reservation's duration to 300 seconds, so that it clashes
        # with the advance reservation
        self.alter_a_reservation(rid, start, end, confirm=True,
                                 a_duration=300, extend='force')

        # Submit another reservation that starts in 1hr and 200 seconds.
        # Ideally, in 1 hr second occurrence of reservation will start running
        # and it will run for 3 mins. This means the new reservation will be
        # confirmed.
        new_offset = (start + 3800) - int(time.time())
        rid2, start, end = self.submit_and_confirm_reservation(
            new_offset, 180, select="2:ncpus=4", ExpectSuccess=1)

    def test_alter_force_non_manager_user(self):
        """
        Test that ralter -Wforce option fails for non-manager users
        """

        duration = 180
        offset = 300
        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="2:ncpus=4", ruser=TEST_USER2)
        self.alter_a_reservation(rid, start, end,
                                 a_duration=300, extend='force',
                                 runas=TEST_USER2, whichMessage=0)

    def test_alter_force_select(self):
        """
        Test that ralter -Wforce option fails for select resource
        """

        duration = 180
        offset = 300
        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="2:ncpus=4", ruser=TEST_USER2)
        self.alter_a_reservation(rid, start, end, select="1:ncpus=1",
                                 a_duration=20, extend='force',
                                 whichMessage=0)

    def test_ralter_force_start_end_running_resv(self):
        """
        Test that forcefully altering a running reservation takes effect.
        """

        duration = 3600
        offset = 20

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, select="2:ncpus=4")

        resv_queue = rid.split('.')[0]
        a = {'queue': resv_queue}
        j = Job(attrs=a)
        jid = self.server.submit(j)

        self.logger.info('Waiting for reservation to start')
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        off = int(start - time.time())
        self.server.expect(RESV, a, id=rid, offset=off)

        # this alter command is rejected because the reservation has
        # a running job in it.
        self.alter_a_reservation(rid, start, end, confirm=False, shift=-10,
                                 alter_s=True, extend='force', whichMessage=0)

        self.alter_a_reservation(rid, start, end, confirm=False, shift=-100,
                                 alter_e=True, extend='force')
        _, _, t_end = self.get_resv_time_info(rid)
        end -= 100
        self.assertEqual(int(t_end), end)

        self.alter_a_reservation(rid, start, end, confirm=False,
                                 a_duration=4000, extend='force', sequence=2)
        t_duration, _, _ = self.get_resv_time_info(rid)
        self.assertEqual(int(t_duration), 4000)

        self.server.delete(jid, wait=True)
        end = start + 4000
        self.alter_a_reservation(rid, start, end, confirm=True, shift=1000,
                                 alter_s=True, extend='force', sequence=3)
        _, t_start, _ = self.get_resv_time_info(rid)
        self.assertEqual(int(t_start), start + 1000)

    def test_restart_revert(self):
        """
        Test that if a reservation is in state RESV_BEING_ALTERED and
        the server shuts down, when the server recovers the reservation
        from the database, it will revert the reservation to the original
        attributes.
        """

        duration = 60
        offset = 60
        shift = 5

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration)

        attrs = {'reserve_start':
                 self.bu.convert_seconds_to_datetime(start, self.fmt),
                 'reserve_end':
                 self.bu.convert_seconds_to_datetime(end, self.fmt),
                 'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': False})
        new_start, new_end = self.alter_a_reservation(rid, start, end,
                                                      alter_s=True,
                                                      alter_e=True,
                                                      shift=shift,
                                                      confirm=False,
                                                      whichMessage=-1)
        a2 = {'reserve_start':
              self.bu.convert_seconds_to_datetime(new_start, self.fmt),
              'reserve_end':
              self.bu.convert_seconds_to_datetime(new_end, self.fmt),
              'reserve_state': (MATCH_RE, 'RESV_BEING_ALTERED|11')}
        self.server.expect(RESV, a2, id=rid)
        self.server.restart()
        self.server.expect(RESV, attrs, id=rid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        self.server.expect(RESV, attrs, id=rid)
        wait = start - time.time()
        self.check_resv_running(rid, offset=wait)

    def test_alter_degrade_reconfirm_standing(self):
        """
        Test that if a standing reservation is altered, degraded,
        then reconfirmed, the reservation will use the original
        select
        """
        duration = 60
        offset = 60

        confirmed = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        degraded = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}
        offline = {'state': 'offline'}

        self.server.manager(MGR_CMD_SET, SERVER, {'reserve_retry_time': 5})

        rid, start, end = self.submit_and_confirm_reservation(
            offset, duration, standing=True, select="2:ncpus=2")

        self.alter_a_reservation(rid, start, end, select="1:ncpus=2")

        self.server.status(RESV, id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': False})
        self.server.manager(MGR_CMD_SET, NODE, offline, id=resv_node)
        self.server.expect(RESV, degraded, id=rid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        self.server.expect(RESV, confirmed, id=rid)

        stat = self.server.status(RESV, id=rid)[0]
        resvnodes = stat['resv_nodes']
        self.assertNotEquals(resv_node, resvnodes)
        self.assertEquals(1, len(resvnodes.split('+')))

        self.check_occr_finish(rid, end - time.time())
        stat = self.server.status(RESV, id=rid)[0]
        resvnodes = stat['resv_nodes']
        self.assertEquals(2, len(resvnodes.split('+')))

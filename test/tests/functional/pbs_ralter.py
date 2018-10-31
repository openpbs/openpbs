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


class TestPbsResvAlter(TestFunctional):

    """
    This test suite is for testing the reservation times modification feature.
    """

    # Class variables
    tzone = None
    # These must be equal to the declarations in pbs_error.h
    PBSE_UNKRESVID = 236
    PBSE_RESV_NOT_EMPTY = 74
    PBSE_STDG_RESV_OCCR_CONFLICT = 75
    PBSE_INCORRECT_USAGE = 2
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

        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vnode', a, num=2, mom=self.mom,
                                  usenatvnode=True)

        self.server.manager(MGR_CMD_SET, SERVER, {
            'log_events': 4095}, expect=True)

    def submit_and_confirm_reservation(self, offset, duration, standing=False,
                                       select="1:ncpus=4",
                                       rrule="FREQ=HOURLY;COUNT=2",
                                       ExpectSuccess=1):
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
                             successful or not.
        :type  ExpectSuccess: int.
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

        rid = self.server.submit(Reservation(TEST_USER, attrs))
        msg = "Resv;" + rid + ";New reservation submitted start="
        msg += time.strftime(self.fmt, time.localtime(int(start)))
        msg += " end="
        msg += time.strftime(self.fmt, time.localtime(int(end)))
        if standing:
            msg += " recurrence_rrule=" + rrule + " timezone="
            msg += self.tzone

        self.server.log_match(msg, interval=2, max_attempts=30)

        if ExpectSuccess:
            attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
            self.server.expect(RESV, attrs, id=rid)

            msg = "Resv;" + rid + ";Reservation confirmed"
            self.server.log_match(msg, interval=2,
                                  max_attempts=30)

            self.server.expect(RESV, attrs, id=rid)
            acct_msg = "U;" + rid + ";requestor=" + TEST_USER.name + "@.*"

            if standing:
                acct_msg += " recurrence_rrule=" + re.escape(rrule)
                acct_msg += " timezone=" + re.escape(self.tzone)

            self.server.accounting_match(acct_msg, interval=2, regexp=True,
                                         max_attempts=30)
        else:
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

    def check_standing_resv_second_occurrence(self, rid, start, end):
        """
        Helper method to verify that the second occurrence of a standing
        reservation retains its original start and end times.
        Assumption: This method assumes that rid represents an HOURLY
                    reservation.

        :param rid: Reservation id.
        :type  rid: string.

        :param start: Start time of the first occurrence of the reservation.
        :type  start: int.

        :param end: End time of the first occurrence of the reservation.
        :type  end: int.
        """
        next_start = start + 3600
        next_end = end + 3600
        duration = end - start
        next_start_conv = self.bu.convert_seconds_to_datetime(
            next_start, self.fmt)
        next_end_conv = self.bu.convert_seconds_to_datetime(
            next_end, self.fmt)
        attrs = {'reserve_start': next_start_conv,
                 'reserve_end': next_end_conv,
                 'reserve_duration': duration}
        self.server.expect(RESV, attrs, id=rid)

    def submit_job_to_resv(self, rid, sleep=10):
        """
        Helper method for submitting a sleep job to the reservation.

        :param rid: Reservation id.
        :type  rid: string.

        :param sleep: Sleep time in seconds for the job.
        :type  sleep: int.
        """
        r_queue = rid.split('.')[0]
        a = {'queue': r_queue}
        j = Job(TEST_USER, a)
        j.set_sleep_time(sleep)
        jid = self.server.submit(j)
        return jid

    def alter_a_reservation(self, r, start, end, shift,
                            alter_s=False, alter_e=False,
                            whichMessage=1, confirm=True,
                            interactive=0, sequence=1):
        """
        Helper method for altering a reservation.
        This method also checks for the server and accounting logs.

        :param r: Reservation id.
        :type  r: string.

        :param start: Start time of the reservation.
        :type  start: int.

        :param end: End time of the reservation.
        :type  end: int.

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

        new_duration = new_end - new_start
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

            self.server.alterresv(r, attrs)

            self.assertEqual(msg, self.server.last_out[0])
            self.logger.info(msg + " displayed")

            msg = "Resv;" + r + ";Attempting to modify reservation "
            if alter_s:
                msg += "start="
                msg += time.strftime(self.fmt, time.localtime(int(new_start)))

            if alter_e:
                if alter_s:
                    msg += " "
                    acct_msg += " "
                msg += "end="
                msg += time.strftime(self.fmt, time.localtime(int(new_end)))
                acct_msg += "end="
                acct_msg += str(new_end)

            self.server.log_match(msg, interval=2, max_attempts=30)

            if whichMessage == 1:
                if alter_s:
                    new_start_conv = self.bu.convert_seconds_to_datetime(
                        new_start, self.fmt)
                    attrs['reserve_start'] = new_start_conv

                if alter_e:
                    new_end_conv = self.bu.convert_seconds_to_datetime(
                        new_end, self.fmt)
                    attrs['reserve_end'] = new_end_conv

                attrs['reserve_duration'] = new_duration

                if confirm:
                    attrs['reserve_state'] = (MATCH_RE, 'RESV_CONFIRMED|2')
                else:
                    attrs['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')

                self.server.expect(RESV, attrs, id=r)
                acct_msg = "Y;" + r + ";requestor=Scheduler@.*" + " start="
                acct_msg += str(new_start) + " end=" + str(new_end)
                self.server.status(RESV, 'resv_nodes', id=r)
                acct_msg += " nodes="
                acct_msg += re.escape(self.server.reservations[r].resvnodes())

                if r[0] == 'S':
                    self.server.status(RESV, 'reserve_count', id=r)
                    count = self.server.reservations[r].attributes[
                        'reserve_count']
                    acct_msg += " count=" + count

                self.server.accounting_match(acct_msg, regexp=True, interval=2,
                                             max_attempts=30)

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
                self.server.alterresv(r, attrs)
            except PbsResvAlterError as e:
                if e.rc == self.PBSE_RESV_NOT_EMPTY:
                    msg = "pbs_ralter: Reservation not empty"
                elif e.rc == self.PBSE_UNKRESVID:
                    msg = "pbs_ralter: Unknown Reservation Id"
                elif e.rc == self.PBSE_STDG_RESV_OCCR_CONFLICT:
                    msg = "Requested time(s) will interfere with "
                    msg += "a later occurrence"
                    log_msg = "Resv;" + r + ";" + msg
                    msg = "pbs_ralter: " + msg
                    self.server.log_match(log_msg, interval=2,
                                          max_attempts=30)
                elif e.rc == self.PBSE_INCORRECT_USAGE:
                    pass

                self.assertNotEqual(e.msg, msg)
                return start, end
            else:
                self.assertFalse("Reservation alter allowed when it should" +
                                 "not be.")

    def test_alter_advance_resv_start_time_before_run(self):
        """
        This test case covers the below scenarios for an advance reservation
        that has not started running.

        1. Make an advance reservation start late (empty reservation)
        2. Make an advance reservation start early (empty reservation)
        3. Make an advance reservation start early (with a job in it)

        All the above operations are expected to be successful.
        """
        offset = 20
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
        offset = 10
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
        shift = 10
        offset = 10
        sleep = 25
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
        offset = 40
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
        duration = 20
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
        shift = 10
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
        self.submit_job_to_resv(rid)

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
        duration = 20
        shift = 10
        offset = 10
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
        sleep = 25
        rid, start, end = self.submit_and_confirm_reservation(offset, duration,
                                                              standing=True)

        # Submit a job to the reservation.
        jid = self.submit_job_to_resv(rid, sleep)

        # Wait for the reservation to start running.
        self.check_resv_running(rid, offset)

        new_end = self.alter_a_reservation(rid, start, end,
                                           shift, alter_e=True,
                                           confirm=False)[1]

        self.check_resv_running(rid, duration, 0)
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
        self.server.create_vnodes('vnode', a, num=256, mom=self.mom,
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
        offset = 5

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
        offset = 5

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
        offset = 60

        rid1, start1, end1 = self.submit_and_confirm_reservation(
            offset, duration, select="1:ncpus=2")
        rid2, start2, end2 = self.submit_and_confirm_reservation(
            offset, duration, select="1:ncpus=2", standing=True)
        self.mom.stop()
        msg = 'mom is not down'
        self.assertFalse(self.mom.isUp(), msg)
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
        if resv_node1 is resv_node2:
            self.server.manager(MGR_CMD_SET, NODE, {
                                'state': "offline"}, id=resv_node1)
        else:
            self.server.manager(MGR_CMD_SET, NODE, {
                                'state': "offline"}, id=resv_node1)
            self.server.manager(MGR_CMD_SET, NODE, {
                                'state': "offline"}, id=resv_node2)
        self.server.expect(RESV, attrs, id=rid1)
        self.server.expect(RESV, attrs, id=rid2)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, sequence=3)
        self.alter_a_reservation(rid2, start2, end2, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, sequence=3)
        self.alter_a_reservation(rid1, start1, end1, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, interactive=2,
                                 sequence=4)
        self.alter_a_reservation(rid2, start2, end2, shift, alter_s=True,
                                 alter_e=True, whichMessage=3, interactive=2,
                                 sequence=4)

    def test_alter_resv_name(self):
        """
        This test checks the alter of reservation name.
        """
        duration = 30
        offset = 5

        rid1 = self.submit_and_confirm_reservation(
            offset, duration)
        rid2 = self.submit_and_confirm_reservation(
            offset, duration, standing=True)
        attr1 = {ATTR_N: "Adv_Resv"}
        self.server.alterresv(rid1[0], attr1)
        attr2 = {ATTR_N: "Std_Resv"}
        self.server.alterresv(rid2[0], attr2)
        attr1 = {'Reserve_Name': "Adv_Resv"}
        attr2 = {'Reserve_Name': "Std_Resv"}
        self.server.expect(RESV, attr1, id=rid1[0])
        self.server.expect(RESV, attr2, id=rid2[0])

    def test_alter_user_permission(self):
        """
        This test checks the user permissions for pbs_ralter.
        """
        duration = 30
        offset = 5
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

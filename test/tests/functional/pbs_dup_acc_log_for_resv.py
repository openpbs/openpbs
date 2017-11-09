# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under a
# commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from tests.functional import *
import time


class TestDupAccLogForResv(TestFunctional):
    """
    This test suite is for testing duplicate records in accounting log
    for start of reservations.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        if len(self.moms) != 2:
            self.skipTest('test requires two MoMs as input, ' +
                          'use -p moms=<mom1>:<mom2>')

    def check_log_resv_time(self, accounting_log_msg, start_tup):
        """
        This is a helper function to retrieve start and end time
        of standing reservation from accounting log.
        """
        loglist_value = accounting_log_msg[start_tup][1]
        log_value = loglist_value.split()
        actual_reservation_time = []
        check_status = ['start', 'end']
        for status in check_status:
            for attribute in log_value:
                attribute_value = attribute.split("=")
                if attribute_value[0] == status:
                    actual_reservation_time.append(int(attribute_value[1]))

        return actual_reservation_time

    def differentiate_resv_instance(self, expected_start, expected_end,
                                    got_start, got_end, reserve_index):
        """
        This is a helper function to differentiate log match for each
        instance(reserve_index) of standing reservation.
        As input function accept expected_start,expected_end,got _start,
        got_end time value and reserve_ index.
        By comparison of expected_start & got_start and expected_end &
        got_end time value,function will log info for specific
        instance(reserve_index) of standing reservation.
        """

        self.assertTrue(((expected_start == got_start) and
                         (expected_end == got_end)),
                        'Time in the accounting log does not match with'
                        'the expected time for the standing reservation')

        match_string = 'Matched accounting log for instance' + reserve_index
        if reserve_index in ('1', '2', '3'):
            self.logger.info(match_string)
        else:
            self.assertTrue(False, "Unknown Instance")

    def test_accounting_logs(self):
        """
        Test for duplicate records in accounting log for advance reservations
        on restart of server
        """
        r1 = Reservation(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1', 'reserve_start': int(
            time.time() + 5), 'reserve_end': int(time.time() + 60)}
        r1.set_attributes(a)
        r1id = self.server.submit(r1)
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=r1id, max_attempts=30, offset=8)

        self.server.restart()
        m = self.server.accounting_match(
            msg='.*B;' + r1id, id=r1id, n='ALL', allmatch=True, regexp=True)
        self.assertEqual(len(m), 1)

    def test_advance_reservation(self):
        """
        Test for duplicate records in accounting log for advance reservations
        on restart of server multiple time
        """
        test = []
        test += ['echo Starting test at `date`\n']
        test += ['sleep 20\n']

        # Submit a advance reservation
        r = Reservation(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1', 'reserve_start': int(
            time.time() + 5), 'reserve_end': int(time.time() + 120)}
        r.set_attributes(a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid, max_attempts=30)
        rname = rid.split('.')

        # Submit a job inside reservation
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: rname[0]}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.create_script(body=test)
        jid = self.server.submit(j)

        # Verify job in running R state
        self.server.expect(
            JOB, {ATTR_state: 'R', ATTR_substate: '42'}, jid, max_attempts=30)

        # Verify accounting log before server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        # Restart server
        self.server.restart()

        # Verify accounting log,no duplicate log after server restart

        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, max_attempts=30, offset=8)

        # Restart server second time
        self.server.restart()

        # Verify accounting log,no duplicate log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

    def test_standing_reservation(self):
        """
        Test for duplicate records in accounting log for standing reservations
        on restart of server
        """
        # PBS_TZID environment variable must be set, there is no way to set
        # it through the API call, use CLI instead for this test

        _m = self.server.get_op_mode()
        if _m != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        if _m == PTL_API:
            self.server.set_op_mode(PTL_API)
        instance1_start = int(time.time() + 5)
        instance1_end = int(time.time() + 35)
        a = {'Resource_List.select': '1:ncpus=1',
             ATTR_resv_rrule: 'FREQ=MINUTELY;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': instance1_start,
             'reserve_end': instance1_end}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=6)

        ret = self.server.status(RESV, id=rid)
        rid_instance1 = ret[0]['reserve_index']

        # Verify accounting log before server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)
        # getting startime and endtime of first instance of standing
        # reservation
        got_time_instance1 = self.check_log_resv_time(
            accounting_log_msg=m, start_tup=0)

        self.differentiate_resv_instance(got_start=got_time_instance1[0],
                                         got_end=got_time_instance1[1],
                                         expected_start=instance1_start,
                                         expected_end=instance1_end,
                                         reserve_index=rid_instance1)
        # Restart server
        self.server.restart()

        # Verify accounting log,no duplicate log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        # Offset of 37 secs being used in server_expect()for reservation,
        # second instance to be in Confirmed state
        self.server.expect(RESV, a, id=rid, max_attempts=5, offset=37)

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        # Offset of 24 secs being used in server_expect()for reservation,
        # second instance to be in Runninng state
        self.server.expect(RESV, a, id=rid, max_attempts=5, offset=24)

        ret = self.server.status(RESV, id=rid)
        rid_instance2 = ret[0]['reserve_index']
        # Verify accounting log for start of second instance of the standing
        # reservation
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 2)

        # getting startime and endtime of second instance of standing
        # reservation
        got_time_instance2 = self.check_log_resv_time(
            accounting_log_msg=m, start_tup=1)

        self.differentiate_resv_instance(got_start=got_time_instance2[0],
                                         got_end=got_time_instance2[1],
                                         expected_start=(instance1_start + 60),
                                         expected_end=(instance1_start + 90),
                                         reserve_index=rid_instance2)

        # Restart server second time
        self.server.restart()

        # Verify accounting log,no duplicate log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 2)

    def test_multinode_advance_reservation(self):
        """
        Test for duplicate records in accounting log for advance reservations
        on restart of server requesting multiple nodes
        """
        # Submit a advance reservation requesting multiple nodes
        r = Reservation(TEST_USER)
        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'scatter',
             'reserve_start': int(time.time() + 5),
             'reserve_end': int(time.time() + 3600)}
        r.set_attributes(a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=6)

        # Verify accounting log before server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        # Restart server
        self.server.restart()

        # Verify accounting log, no duplicate log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid)

        # Restart server second time
        self.server.restart()
        # Verify accounting log, no duplicate log  after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

    def test_multinode_standing_reservation(self):
        """
        Test for duplicate records in accounting log for multi node standing
        reservations on restart of server requesting multi-node
        """
        # PBS_TZID environment variable must be set, there is no way to set
        # it through the API call, use CLI instead for this test

        _m = self.server.get_op_mode()
        if _m != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        if _m == PTL_API:
            self.server.set_op_mode(PTL_API)
        instance1_start = int(time.time() + 5)
        instance1_end = int(time.time() + 35)
        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'scatter',
             ATTR_resv_rrule: 'FREQ=MINUTELY;COUNT=3',
             ATTR_resv_timezone: tzone,
             'reserve_start': instance1_start,
             'reserve_end': instance1_end}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, offset=6)

        ret = self.server.status(RESV, id=rid)
        rid_instance1 = ret[0]['reserve_index']

        # Verify accounting log before server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        # getting startime and endtime of first instance of standing
        # reservation
        got_time_instance1 = self.check_log_resv_time(
            accounting_log_msg=m, start_tup=0)

        self.differentiate_resv_instance(got_start=got_time_instance1[0],
                                         got_end=got_time_instance1[1],
                                         expected_start=instance1_start,
                                         expected_end=instance1_end,
                                         reserve_index=rid_instance1)

        # Restart server
        self.server.restart()

        # Verify accounting log,no duplicate log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        # Offset of 37 secs being used in server_expect()for reservation,
        # second instance to be in Confirmed state
        self.server.expect(RESV, a, id=rid, max_attempts=5, offset=37)

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        # Offset of 24 secs being used in server_expect()for reservation,
        # second instance to be in Runninng state
        self.server.expect(RESV, a, id=rid, max_attempts=5, offset=24)

        ret = self.server.status(RESV, id=rid)
        rid_instance2 = ret[0]['reserve_index']

        # Verify accounting log for start of second instance of the standing
        # reservation
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 2)

        # getting startime and endtime of second instance of standing
        # reservation
        got_time_instance2 = self.check_log_resv_time(
            accounting_log_msg=m, start_tup=0)

        self.differentiate_resv_instance(got_start=got_time_instance2[0],
                                         got_end=got_time_instance2[1],
                                         expected_start=(instance1_start + 60),
                                         expected_end=(instance1_start + 90),
                                         reserve_index=rid_instance2)
        # Restart server
        self.server.restart()

        # Verify accounting log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 2)

        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        # Offset of 37 secs being used in server_expect()for reservation,
        # third instance to be in Confirmed state
        self.server.expect(RESV, a, id=rid, max_attempts=5, offset=37)

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        # Offset of 24 secs being used in server_expect()for reservation,
        # third instance to be in Runninng state
        self.server.expect(RESV, a, id=rid, max_attempts=5, offset=24)

        ret = self.server.status(RESV, id=rid)
        rid_instance3 = ret[0]['reserve_index']

        # Verify accounting log for start of third instance of the standing
        # reservation
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 3)
        ret = self.server.status(RESV, id=rid)
        rid_instance3 = ret[0]['reserve_index']

        # getting startime and endtime of third instance of standing
        # reservation
        got_time_instance3 = self.check_log_resv_time(
            accounting_log_msg=m, start_tup=0)

        self.differentiate_resv_instance(got_start=got_time_instance3[0],
                                         got_end=got_time_instance3[1],
                                         expected_start=(
                                             instance1_start + 120),
                                         expected_end=(instance1_start + 150),
                                         reserve_index=rid_instance3)
        # Restart server
        self.server.restart()

        # Verify accounting log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 3)

    def test_accounting_logs_after_qterm(self):
        """
        Test for duplicate records in accounting log for reservations
        when the server is stopped using qterm and started again.
        """
        # Submit a advance reservation
        r = Reservation(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1', 'reserve_start': int(
            time.time() + 5), 'reserve_end': int(time.time() + 120)}
        r.set_attributes(a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid,  max_attempts=30)

        # Verify accounting log before server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

        # Stop server using qterm command
        self.server.qterm()

        # Start server
        self.server.start()

        # Verify accounting log after server restart
        m = self.server.accounting_match(
            msg='.*B;' + rid, id=rid, n='ALL', allmatch=True, regexp=True)
        self.assertNotEqual(m, None)
        self.assertEqual(len(m), 1)

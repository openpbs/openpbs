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


class TestReservationRequests(TestFunctional):

    """
    Various tests to verify behavoir of server
    in validating reservation requests
    """
    # Class variables
    bu = BatchUtils()
    fmt = "%a %b %d %H:%M:%S %Y"

    def test_duration_end_resv(self):
        """
        To test if reservations can be made by using
        duration and endtime, making the server calculate
        the starttime.
        """
        # create reservation to end in 5 seconds and lasts 1.
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_end': now + 5,
             'reserve_duration': 1}
        R = Reservation(TEST_USER, attrs=a)
        R.unset_attributes(['reserve_start'])
        rid = self.server.submit(R)

        a = {'reserve_start': self.bu.convert_seconds_to_datetime(
            now + 4, self.fmt)}
        self.server.expect(RESV, a, id=rid)

    def test_duration_end_resv_fail(self):
        """
        To test if reservations made by using
        duration and endtime, making the server calculate
        the starttime and rejects if the starttime is before now.
        """
        # create reservation to end in 5 seconds and lasts 10.
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_end': int(time.time()) + 5,
             'reserve_duration': 10}
        R = Reservation(TEST_USER, attrs=a)
        R.unset_attributes(['reserve_start'])
        rid = None
        try:
            rid = self.server.submit(R)
        except PbsSubmitError as e:
            self.assertTrue('Bad time specification(s)' in e.msg[0],
                            'Reservation Submit failed in an unexpected way')
        self.assertTrue(rid is None,
                        'Reservation Submit succeeded ' +
                        'when it should have failed')

    def test_start_dur_end_resv_fail(self):
        """
        Test to submit a job with a start, end, and duration
        where start + duration != end.
        """
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 10,
             'reserve_end': now + 30,
             'reserve_duration': 10}
        R = Reservation(TEST_USER, attrs=a)
        rid = None
        try:
            rid = self.server.submit(R)
        except PbsSubmitError as e:
            self.assertTrue('Bad time specification(s)' in e.msg[0],
                            'Reservation Submit failed in an unexpected way')
        self.assertTrue(rid is None,
                        'Reservation Submit succeeded' +
                        'when it should have failed')

    def test_start_dur_end_resv(self):
        """
        Test to submit a job with a start, end, and duration
        where start + duration = end.
        """
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 20,
             'reserve_end': now + 30,
             'reserve_duration': 10}
        R = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(R)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

    def test_end_wall_resv(self):
        """
        Test to submit a job with end and walltime
        """
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '10',
             'reserve_end': now + 30}
        R = Reservation(TEST_USER, attrs=a)
        R.unset_attributes(['reserve_start'])
        rid = self.server.submit(R)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

    def test_rstat_longterm_resv(self):
        """
        Test to submit a reservation, where duration > INT_MAX.
        Check whether rstat displaying negative number.
        """
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 3600,
             'reserve_end': now + 4294970895}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        out = self.server.status(RESV, 'reserve_duration', id=rid)[0][
            'reserve_duration']
        dur = int(out)
        self.assertTrue(dur > 0, 'Duration ' + str(dur) + 'is negative.')

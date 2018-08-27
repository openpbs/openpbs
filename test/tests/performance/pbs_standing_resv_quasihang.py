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

from tests.performance import *


class StandingResvQuasihang(TestPerformance):
    """
    This test suite aims at testing the quasihang caused by a MoM HUP
    when there is a standing reservation with more than a 1000 instances.
    Without the fix, the server takes a lot of time to respond to a client.
    With the fix, the amount of time is significantly reduced.
    """

    def setUp(self):
        TestPerformance.setUp(self)

        # Set PBS_TZID, needed for standing reservation.
        if 'PBS_TZID' in self.conf:
            self.tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            self.tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Timezone not set, using Asia/Kolkata')
            self.tzone = 'Asia/Kolkata'

        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vnode', a, num=2000, mom=self.mom,
                                  usenatvnode=True)

    @timeout(6000)
    def test_time_for_stat_after_mom_hup(self):
        """
        This test case submits a standing reservation with 2000 instances,
        HUPS the MoM, stats the reservation and finds the amount of time
        the server took to respond.

        The test case is not designed to pass/fail on builds with/without
        the fix.
        """
        start = int(time.time()) + 3600
        attrs = {'Resource_List.select': "64:ncpus=2",
                 'reserve_start': start,
                 'reserve_duration': 2000,
                 'reserve_timezone': self.tzone,
                 'reserve_rrule': "FREQ=HOURLY;BYHOUR=1,2,3,4,5;COUNT=2000"}

        rid = self.server.submit(Reservation(TEST_USER, attrs))
        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}

        # it takes a while for all the instances of the reservation to get
        # confirmed, hence the interval of 5 seconds.
        self.server.expect(RESV, attrs, id=rid, interval=5)

        self.mom.signal('-HUP')

        # sleep for 5 seconds so that the HUP takes its effect.
        time.sleep(5)

        now1 = int(time.time())
        attrs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attrs, id=rid)

        now2 = int(time.time())
        self.logger.info("pbs_rstat took %d seconds to return\n",
                         (now2 - now1))

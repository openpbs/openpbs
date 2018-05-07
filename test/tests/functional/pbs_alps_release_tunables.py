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
import math


def get_epoch(msg):
    # Since its a log message split on ';' to get timestamp
    a = time.strptime(msg.split(';')[0], "%m/%d/%Y %H:%M:%S")
    return int(time.mktime(a))


@tags('cray')
class TestCrayAlpsReleaseTunables(TestFunctional):
    """
    Set of tests to verify alps release tunables namely alps_release_wait_time
    and alps_release_jitter
    """

    def setUp(self):
        machine = self.du.get_platform()
        if not machine == 'cray':
            self.skipTest("Test suite only meant to run on a Cray")
        TestFunctional.setUp(self)

    def test_alps_release_wait_time(self):
        """
        Set alps_release_wait_time to a higher value and then notice that
        subsequest reservation cancellation requests are made at least
        after the set interval.
        """
        # assigning a random value to alps_release_wait_time that is
        # measurable using mom log messages
        arwt = 4.298
        self.mom.add_config({'$alps_release_wait_time': arwt})

        # submit a job and then delete it after it starts running
        start_time = int(time.time())
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        time.sleep(2)
        self.server.delete(jid1)

        # Look for a message that confirms that reservation is deleted
        self.mom.log_match("%s;ALPS reservation cancelled" % jid1,
                           starttime=start_time)
        # Now that we know that reservation is cleared we should
        # check for time difference between each cancellation request
        out = self.mom.log_match("%s;Canceling ALPS reservation *" % jid1,
                                 n='ALL', regexp=True, allmatch=True)

        # We found something, Let's first check there are atleast 2 such
        # log messages, If not then that means reservation was cancelled
        # in the first attempt itself, at that point right thing to do is
        # to either run it again or find out a way to delay the reservation
        # cancellation at ALPS level itself.
        if len(out) >= 2:
            # variable 'out' is a list of tuples and every second element
            # in a tuple is the matched log message
            time_prev = get_epoch(out[0][1])
            for data in out[1:]:
                time_current = get_epoch(data[1])
                fail_msg = "alps_release_wait_time not working"
                self.assertGreaterEqual(time_current - time_prev,
                                        math.ceil(arwt),
                                        msg=fail_msg)
                time_prev = time_current

        else:
            self.skipTest("Reservation cancelled without retry, Try again!")

    def test_alps_release_jitter(self):
        """
        Set alps_release_jitter to a higher value and then notice that
        subsequest reservation cancellation requests are made by adding
        a random time interval (less than jitter) to alps_release_wait_time.
        """
        # assigning a random value to alps_release_jitter that is
        # measurable using mom log messages
        arj = 2.198
        arwt = 1
        max_delay = (arwt + math.ceil(arj))
        self.mom.add_config({'$alps_release_jitter': arj})
        self.mom.add_config({'$alps_release_wait_time': arwt})
        # There is no good way to test jitter and it is a random number
        # less than value set in alps_release_jitter. So in this case
        # we can probably try deleting a reservation a few times.
        n = retry = 5
        for _ in range(n):
            # submit a job and then delete it after it starts running
            start_time = int(time.time())
            j1 = Job(TEST_USER)
            jid1 = self.server.submit(j1)
            self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
            time.sleep(2)
            self.server.delete(jid1)

            # Look for a message that confirms that reservation is deleted
            self.mom.log_match("%s;ALPS reservation cancelled" % jid1,
                               starttime=start_time)
            # Now that we know that reservation is cleared we should
            # check for time difference between each cancellation request
            out = self.mom.log_match("%s;Canceling ALPS reservation *" % jid1,
                                     n='ALL', regexp=True, allmatch=True)

            # We found something, Let's first check there are atleast 2 such
            # log messages, If not then that means reservation was cancelled
            # in the first attempt itself, at that point right thing to do is
            # to either run it again or find out a way to delay the reservation
            # cancellation at ALPS level itself.
            if len(out) >= 2:
                retry -= 1
                # variable 'out' is a list of tuples and every second element
                # in a tuple is the matched log message
                time_prev = get_epoch(out[0][1])
                for data in out[1:]:
                    time_current = get_epoch(data[1])
                    self.assertLessEqual(time_current - time_prev, max_delay,
                                         msg="alps_release_jitter not working")
                    time_prev = time_current
        if retry == 5:
            self.skipTest("Reservation cancelled without retry, Try again!")

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

from tests.selftest import *
from ptl.utils.plugins.ptl_test_runner import TimeOut


class TestDefaultTimeout(TestSelf):
    """
    Test suite to verify increase default testcase timeout working properly.
    """

    def test_default_timeout(self):
        """
        Verify that test not timedout after 180 sec.
        i.e. after previous default timeout value
        """
        try:
            mssg = 'sleeping for %ssec and minimum-testcase-timeout is %ssec' \
                   % (MINIMUM_TESTCASE_TIMEOUT/2, MINIMUM_TESTCASE_TIMEOUT)
            self.logger.info(mssg)
            time.sleep(MINIMUM_TESTCASE_TIMEOUT/2)
        except TimeOut as e:
            mssg = 'Timed out after %s second' % MINIMUM_TESTCASE_TIMEOUT
            err_mssg = 'The test timed out for an incorrect timeout duration'
            self.assertEqual(mssg, str(e), err_mssg)

    def test_timeout_greater_default_value(self):
        """
        Verify that test timedout after 600 sec.
        """
        try:
            mssg = 'sleeping for %ssec and minimum-testcase-timeout is %ssec' \
                   % (MINIMUM_TESTCASE_TIMEOUT+1, MINIMUM_TESTCASE_TIMEOUT)
            self.logger.info(mssg)
            time.sleep(MINIMUM_TESTCASE_TIMEOUT+1)
        except TimeOut as e:
            mssg = 'Timed out after %s second' % MINIMUM_TESTCASE_TIMEOUT
            err_mssg = 'The test timed out for an incorrect timeout duration'
            self.assertEqual(mssg, str(e), err_mssg)
        else:
            msg = 'Test did not timeout after the min. timeout period of %d' \
                  % MINIMUM_TESTCASE_TIMEOUT
            self.fail(msg)

    @timeout(200)
    def test_timeout_decorator_less_default_value(self):
        """
        If timeout decorator value is less than 600 then
        default testcase timeout is considered
        """
        try:
            mssg = 'sleeping for %ssec and minimum-testcase-timeout is %ssec' \
                   % (MINIMUM_TESTCASE_TIMEOUT/2, MINIMUM_TESTCASE_TIMEOUT)
            self.logger.info(mssg)
            time.sleep(MINIMUM_TESTCASE_TIMEOUT/2)
        except TimeOut as e:
            mssg = 'Timed out after %s second' % MINIMUM_TESTCASE_TIMEOUT
            err_mssg = 'The test timed out for an incorrect timeout duration'
            self.assertEqual(mssg, str(e), err_mssg)

    @timeout(800)
    def test_timeout_decorator_greater_default_value(self):
        """
        If timeout decorator value is greater than 600 then
        testcase timeout value consider as timeout decorator value
        """
        try:
            mssg = 'sleeping for %ssec and minimum-testcase-timeout is %ssec' \
                   % (MINIMUM_TESTCASE_TIMEOUT+1, 800)
            self.logger.info(mssg)
            time.sleep(MINIMUM_TESTCASE_TIMEOUT+1)
        except TimeOut as e:
            mssg = 'Timed out after 800 second'
            err_mssg = 'The test timed out for an incorrect timeout duration'
            self.assertEqual(mssg, str(e), err_mssg)

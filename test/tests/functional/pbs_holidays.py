# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

import datetime
from tests.functional import *


class TestHolidays(TestFunctional):

    """
    This test suite tests if PBS scheduler's holidays file feature
    works correctly
    """
    days = ["monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday"]
    np_queue = "np_workq"
    p_queue = "p_workq"
    cur_year = datetime.datetime.today().year
    allprime_msg = "It is primetime.  It will never end"
    tom = datetime.date.today() + datetime.timedelta(days=1)
    tom = tom.strftime("%m/%d/%Y")
    dayprime_msg = r"It is primetime.  It will end in \d+ seconds at " +\
        tom + " 00:00:00"
    daynp_msg = r"It is non-primetime.  It will end in \d+ seconds at " +\
        tom + " 00:00:00"

    def setUp(self):
        TestFunctional.setUp(self)

        # Enable DEBUG2 sched log messages
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 1023})

    def test_missing_days(self):
        """
        Test that scheduler correctly assumes 24hr prime-time for days that
        are missing from the holidays file
        """
        self.scheduler.holidays_delete_entry('a')

        self.scheduler.holidays_set_year(self.cur_year)

        # Set all days of the week as non-prime time and today as prime time
        today_idx = datetime.datetime.today().weekday()
        today = self.days[today_idx]
        for i in range(7):
            if i != today_idx:
                self.scheduler.holidays_set_day(self.days[i], "none", "all")

        ctime = int(time.time())
        time.sleep(1)

        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})

        # Verify that there's no entry in holidays file for today
        ret = self.scheduler.holidays_get_day(today)
        self.assertIsNone(ret['p'])
        self.assertIsNone(ret['np'])
        self.assertIsNone(ret['valid'])

        # Verify that it's prime-time until tomorrow
        self.scheduler.log_match(msg=self.dayprime_msg, regexp=True,
                                 starttime=ctime)

    def test_inconsistent_days(self):
        """
        Test that scheduler correctly assumes 24hr prime-time for days that
        have inconsistent data
        """
        self.scheduler.holidays_delete_entry('a')

        self.scheduler.holidays_set_year(self.cur_year)

        # Set all days of the week as non-prime time except today
        today_idx = datetime.datetime.today().weekday()
        today = self.days[today_idx]
        for i in range(7):
            if i != today_idx:
                self.scheduler.holidays_set_day(self.days[i], "none", "all")

        # Set both prime and non-prime start times to 'all' for today
        # and check that scheduler assumes that day as prime-time
        self.scheduler.holidays_set_day(today, "all", "all")

        # Verify that it's prime-time until tomorrow
        ctime = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.dayprime_msg, regexp=True,
                                 starttime=ctime)

        # Set both prime and non-prime start times to 'all' for today
        self.scheduler.holidays_set_day(today, "none", "none")

        # Verify that it's prime-time until tomorrow
        ctime = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.dayprime_msg, regexp=True,
                                 starttime=ctime)

    def test_only_year(self):
        """
        Test that scheduler assumes all prime-time if there's only a year
        entry in the holidays file
        """
        self.scheduler.holidays_delete_entry('a')

        self.scheduler.holidays_set_year(self.cur_year)

        # Verify that the holidays file has only the year line
        h_content = self.scheduler.holidays_parse_file()
        self.assertEqual(len(h_content), 1)
        self.assertEqual(h_content[0], "YEAR\t%d" % self.cur_year)

        # Verify that it's 24x7 prime-time
        ctime = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.allprime_msg, regexp=True,
                                 starttime=ctime)

    def test_empty_holidays_file(self):
        """
        Test that the scheduler assumes all prime-time if the holidays
        file is completely empty
        """
        ctime = int(time.time())
        self.scheduler.holidays_delete_entry('a')

        # Verify that the holidays file is empty
        h_content = self.scheduler.holidays_parse_file()
        self.assertEqual(len(h_content), 0)

        # Verify that it's 24x7 prime-time
        ctime2 = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.allprime_msg, regexp=True,
                                 starttime=ctime2)

        # Verify that scheduler didn't log a message for out of date file
        msg = "holidays;The holiday file is out of date; please update it."
        self.scheduler.log_match(msg, starttime=ctime, existence=False,
                                 max_attempts=5)

    def test_stale_year(self):
        """
        Test that the scheduler logs out-of-date log message and assumed
        all prime-time for a holidays file with just a stale year line
        """
        ctime = int(time.time())
        self.scheduler.holidays_delete_entry('a')

        self.scheduler.holidays_set_year(self.cur_year - 1)

        # Verify that the holidays file has only the year line
        h_content = self.scheduler.holidays_parse_file()
        self.assertEqual(len(h_content), 1)
        self.assertEqual(h_content[0], "YEAR\t%d" % (self.cur_year - 1))

        # Verify that it's 24x7 prime-time
        ctime2 = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.allprime_msg, regexp=True,
                                 starttime=ctime2)

        # Verify that scheduler logged a message for out of date file
        msg = "holidays;The holiday file is out of date; please update it."
        self.scheduler.log_match(msg, starttime=ctime)

    def test_commented_holidays_file(self):
        """
        Test that the scheduler assumes all prime-time if the holidays
        file is completely commented out
        """
        ctime = int(time.time())
        self.scheduler.holidays_delete_entry('a')

        content = """# YEAR 1970
#  weekday 0600  1730
#  saturday  none  all
#  sunday  none  all"""

        self.scheduler.holidays_write_file(content=content)

        # Verify that the holidays file has 4 lines
        h_content = self.du.cat(filename=self.scheduler.holidays_file,
                                sudo=True)['out']
        self.assertEqual(len(h_content), 4)

        # Verify that it's 24x7 prime-time
        ctime2 = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.allprime_msg, regexp=True,
                                 starttime=ctime2)

        # Verify that scheduler didn't log a message for out of date file
        msg = "holidays;The holiday file is out of date; please update it."
        self.scheduler.log_match(msg, starttime=ctime, existence=False,
                                 max_attempts=5)

    def test_non_prime(self):
        """
        Test that non-prime time set via holidays file works correctly
        """
        self.scheduler.holidays_delete_entry('a')

        self.scheduler.holidays_set_year(self.cur_year)

        # Set all days of the week as prime time except today
        today_idx = datetime.datetime.today().weekday()
        today = self.days[today_idx]
        for i in range(7):
            if i != today_idx:
                self.scheduler.holidays_set_day(self.days[i], "all", "none")

        # Set today as all non-prime time
        self.scheduler.holidays_set_day(today, "none", "all")

        # Verify that it's non-prime time until tomorrow
        ctime = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.daynp_msg, regexp=True,
                                 starttime=ctime)

    def test_missing_year(self):
        """
        Test that scheduler assumes all prime time if the year entry is
        missing from holidays file
        """
        ctime = int(time.time())
        self.scheduler.holidays_delete_entry('a')

        # Create a holidays file with no year entry and all days set to
        # 24hrs non-prime time
        content = """  weekday none  all
  saturday  none  all
  sunday  none  all"""

        self.scheduler.holidays_write_file(content=content)

        # Verify that the holidays file has 3 lines
        h_content = self.du.cat(filename=self.scheduler.holidays_file,
                                sudo=True)['out']
        self.assertEqual(len(h_content), 3)

        # Verify that it's 24x7 prime-time
        ctime2 = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.allprime_msg, regexp=True,
                                 starttime=ctime2)

        # Verify that scheduler didn't log a message for out of date file
        msg = "holidays;The holiday file is out of date; please update it."
        self.scheduler.log_match(msg, starttime=ctime, existence=False,
                                 max_attempts=5)

    def test_prime_events_calendar(self):
        """
        Test that for a commented out holidays file, scheduler doesn't
        add policy change events to the calendar
        """
        self.scheduler.set_sched_config({'strict_ordering': "true    all"})
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        self.scheduler.holidays_delete_entry('a')

        # Create a holidays file with no year entry and all days set to
        # 24hrs non-prime time
        content = """# YEAR 1970
#  weekday 0600  1730
#  saturday  none  all
#  sunday  none  all"""
        self.scheduler.holidays_write_file(content=content)

        time.sleep(1)
        ctime = int(time.time())

        # Verify that it's 24x7 prime-time
        ctime2 = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.allprime_msg, regexp=True,
                                 starttime=ctime2)

        # Set ncpus on vnode to 1
        attrs = {ATTR_rescavail + ".ncpus": '1'}
        self.server.manager(MGR_CMD_SET, NODE, attrs)

        # Submit a job that will occupy all resources, without a walltime
        a = {'Resource_List.select': '1:ncpus=1'}
        j = Job(TEST_USER, attrs=a)
        self.server.submit(j)

        # Submit another job which will get calendared
        j = Job(TEST_USER, attrs=a)
        self.server.submit(j)

        # Verify that scheduler did not calendar any policy change events
        msg = r".*Simulation: Policy change.*"
        self.scheduler.log_match(msg, regexp=True, starttime=ctime,
                                 existence=False,
                                 max_attempts=5)

    def test_week_day_after_weekday(self):
        """
        Test that an individual weekday's entry after the 'weekday'
        entry takes precedence in the holidays file
        """
        self.scheduler.holidays_delete_entry('a')

        self.scheduler.holidays_set_year(self.cur_year)

        # Add a weekday entry with all prime-time
        self.scheduler.holidays_set_day("weekday", "all", "none")

        # Set today as all non-prime time
        today_idx = datetime.datetime.today().weekday()
        today = self.days[today_idx]
        self.scheduler.holidays_set_day(today, "none", "all")

        # Verify that it's non-prime time until tomorrow
        ctime = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.daynp_msg, regexp=True,
                                 starttime=ctime)

    def test_year_0(self):
        """
        Test that setting holidays file's year entry to 0 causes 24x7
        prime-time
        """
        ctime = int(time.time())
        self.scheduler.holidays_delete_entry('a')

        self.scheduler.holidays_set_year('0')

        # Verify that the holidays file has only the year line
        h_content = self.scheduler.holidays_parse_file()
        self.assertEqual(len(h_content), 1)
        self.assertEqual(h_content[0], "YEAR\t0")

        # Verify that it's 24x7 prime-time
        ctime2 = int(time.time())
        time.sleep(1)
        self.server.manager(MGR_CMD_SET, SERVER, {ATTR_scheduling: True})
        self.scheduler.log_match(msg=self.allprime_msg, regexp=True,
                                 starttime=ctime2)

        # Verify that scheduler didn't log a message for out of date file
        msg = "holidays;The holiday file is out of date; please update it."
        self.scheduler.log_match(msg, starttime=ctime, existence=False,
                                 max_attempts=5)

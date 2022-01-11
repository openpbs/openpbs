# coding: utf-8

# Copyright (C) 2022 Altair Engineering, Inc.
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

from tests.selftest import *
import re


class TestSchedConfig(TestSelf):
    """
    Test setting values in sched_config file.
    """

    def test_set_sched_config(self):
        '''
        Test whether Scheduler.set_sched_config() works as expected.
        '''
        sched = self.scheds['default']

        def set_and_get(confs):
            """
            Change settings in scheduler config file and fetch the new
            file contents
            """
            sched.set_sched_config(confs, apply=True, validate=False)
            sched.parse_sched_config()
            return sched.sched_config

        def cmp_dict(old, new):
            """
            Compare two dictionaries and build list of changes
            """
            all_keys = set(old.keys()) | set(new.keys())
            diffs = []
            for key in sorted(all_keys):
                o = old.get(key, '<missing>')
                n = new.get(key, '<missing>')
                if o != n:
                    diffs.append([key, n])
            return diffs

        # See if we can change an existing value, and leave others alone
        old_conf = sched.sched_config
        new_conf = set_and_get({'round_robin': 'True ALL'})
        diffs = cmp_dict(old_conf, new_conf)
        self.assertEqual(diffs, [['round_robin', 'True ALL']])

        # Repeat for initially missing setting
        old_conf = new_conf
        new_conf = set_and_get({'job_sort_key': '"ncpus HIGH"'})
        diffs = cmp_dict(old_conf, new_conf)
        self.assertEqual(diffs, [['job_sort_key', '"ncpus HIGH"']])

        # Test whether we can unset a value by setting to empty list
        old_conf = new_conf
        new_conf = set_and_get({'job_sort_key': []})
        diffs = cmp_dict(old_conf, new_conf)
        self.assertEqual(diffs, [['job_sort_key', '<missing>']])

        # Test whether we can set multiple values for one setting
        old_conf = new_conf
        jsk = ['"job_priority HIGH"', '"ncpus HIGH"']
        new_conf = set_and_get({'job_sort_key': jsk})
        diffs = cmp_dict(old_conf, new_conf)
        self.assertEqual(diffs, [['job_sort_key', jsk]])

        # Test whether we can change multiple settings
        old_conf = new_conf
        jsk = ['"job_priority LOW"', '"mem LOW"']
        new_conf = set_and_get({'primetime_prefix': 'xp_',
                                'job_sort_key': jsk})
        diffs = cmp_dict(old_conf, new_conf)
        self.assertEqual(diffs, [['job_sort_key', jsk],
                                 ['primetime_prefix', 'xp_']])

        # Finally, check if the scheduler likes the result
        sched.set_sched_config(confs={}, apply=True, validate=True)

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

    def set_and_get(self, confs={}, validate=False):
        """
        Change settings in scheduler config file and fetch the new
        file contents
        """
        sched = self.our_sched
        sched.set_sched_config(confs, apply=True, validate=validate)
        cfile = sched.sched_config_file
        clines = self.du.cat(sched.hostname, cfile, sudo=True,
                             level=logging.DEBUG2)['out']
        slines = [x for x in clines if re.match(r'[\w]', x)]
        return slines

    def get_a_setting(self, slines, key, squash=True):
        """"
        Extract lines changing a particular setting from a list of lines
        """
        vals = []
        key_colon = key + ':'
        for line in slines:
            if line.startswith(key_colon):
                value = line[len(key_colon):].strip()
                if squash:
                    value = ' '.join(value.split())
                vals.append(value)
        return vals

    def test_set_sched_config(self):
        '''
        Test whether Scheduler.set_sched_config() works as expected.
        '''
        self.our_sched = self.scheds['default']

        # First, get default settings for a few values and verify
        # they are what they should be as of this version of test.
        slines = self.set_and_get()
        def_rr = self.get_a_setting(slines, 'round_robin')
        def_nsk = self.get_a_setting(slines, 'node_sort_key')
        def_jsk = self.get_a_setting(slines, 'job_sort_key')
        self.assertEqual(def_rr, ["False all"])
        self.assertEqual(def_nsk, ['"sort_priority HIGH" ALL'])
        self.assertEqual(def_jsk, [])

        # See if we can change an existing value, and leave others alone
        slines = self.set_and_get({'round_robin': 'True ALL'})
        new_rr = self.get_a_setting(slines, 'round_robin')
        new_nsk = self.get_a_setting(slines, 'node_sort_key')
        new_jsk = self.get_a_setting(slines, 'job_sort_key')
        self.assertEqual(new_rr, ["True ALL"])
        def_rr = new_rr
        self.assertEqual(new_nsk, def_nsk, "Change to unexpected setting")
        self.assertEqual(new_jsk, def_jsk, "Change to unexpected setting")

        # Repeat for initially missing setting
        slines = self.set_and_get({'job_sort_key': '"ncpus HIGH"'})
        new_rr = self.get_a_setting(slines, 'round_robin')
        new_nsk = self.get_a_setting(slines, 'node_sort_key')
        new_jsk = self.get_a_setting(slines, 'job_sort_key')
        self.assertEqual(new_rr, def_rr, "Change to unexpected setting")
        self.assertEqual(new_nsk, def_nsk, "Change to unexpected setting")
        self.assertEqual(new_jsk, ['"ncpus HIGH"'])
        def_jsk = new_jsk

        # Test whether we can unset a value by setting to empty list
        slines = self.set_and_get({'job_sort_key': []})
        new_rr = self.get_a_setting(slines, 'round_robin')
        new_nsk = self.get_a_setting(slines, 'node_sort_key')
        new_jsk = self.get_a_setting(slines, 'job_sort_key')
        self.assertEqual(new_rr, def_rr, "Change to unexpected setting")
        self.assertEqual(new_nsk, def_nsk, "Change to unexpected setting")
        self.assertEqual(new_jsk, [])
        def_jsk = new_jsk

        # Test whether we can set multiple values
        slines = self.set_and_get({'job_sort_key':
                                   ['"job_priority HIGH"', '"ncpus HIGH"']})
        new_rr = self.get_a_setting(slines, 'round_robin')
        new_nsk = self.get_a_setting(slines, 'node_sort_key')
        new_jsk = self.get_a_setting(slines, 'job_sort_key')
        self.assertEqual(new_rr, def_rr, "Change to unexpected setting")
        self.assertEqual(new_nsk, def_nsk, "Change to unexpected setting")
        self.assertEqual(new_jsk, ['"job_priority HIGH"', '"ncpus HIGH"'])

        # Finally, check if the scheduler likes the final result
        self.our_sched.set_sched_config(apply=True, validate=True)

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
from ptl.utils.plugins.ptl_test_runner import PTLTestRunner


class TestParamDict(TestSelf):
    """
    Test parsing the pbs_benchpress -p argument
    """

    def test_gpd(self):
        """
        Pass various -p param strings to __get_param_dictionary and check
        that result is correct.
        """
        def try_one(runner, param):
            """
            Run get_param_dictionary to convert param string to dict
            """
            runner.param = param
            try:
                # Note that we call private routine directly to avoid
                # possible side effects.
                result = runner._PTLTestRunner__get_param_dictionary()
            except ValueError:
                result = None
            return result

        def compare(old, new, expect_none=False):
            """
            Compare new param dict to old
            """
            if new is None and not expect_none:
                return 'Unexpected parse error'
            if expect_none and new is not None:
                return 'Should have failed'
            all_keys = set(old.keys()) | set(new.keys())
            diffs = []
            for k in sorted(all_keys):
                o = old.get(k, None)
                n = new.get(k, None)
                if o != n:
                    diffs.append((k, n))
            return diffs

        def check_diffs(self, new, expected):
            """
            Validate changes between baseline and new param dict
            """
            if expected is None:
                self.assertEqual(new, expected)
                return
            diffs = compare(self.base, new)
            self.assertEqual(diffs, expected)

        our_runner = PTLTestRunner()

        # Create baseline dictionary
        self.base = try_one(our_runner, '')

        # Try simple key=value (boolean)
        new = try_one(our_runner, 'mom_on_server=True')
        check_diffs(self, new, [('mom_on_server', True)])

        # Try one that generates a set of hostnames
        new = try_one(our_runner, 'moms=foo')
        check_diffs(self, new, [('moms', set(['foo']))])

        # Test that unknown parameter is ignored
        new = try_one(our_runner, 'nonsense')
        check_diffs(self, new, [])

        # Test more complicated host list
        new = try_one(our_runner, 'comms=foo:bar@/path/to/bleem:baz')
        check_diffs(self, new, [('comms', set(['foo', 'baz', 'bar']))])

        # Test bad boolean arg
        new = try_one(our_runner, 'mom_on_server=oops')
        check_diffs(self, new, None)

        # Test multiple options, one of which is default
        new = try_one(our_runner,
                      'server=foo2:bar,mom_on_server=y,comm_on_server=f')
        expected = [('mom_on_server', True),
                    ('servers', set(['foo2', 'bar']))]
        check_diffs(self, new, expected)

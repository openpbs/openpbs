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
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
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
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from tests.functional import *


class TestJobArray(TestFunctional):
    """
    Test suite for PBSPro's job array feature
    """
    def test_arrayjob_Erecord_startval(self):
        """
        Check that an arrayjob's E record's 'start' value is not set to 0
        """
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2',
            'Resource_List.select': 'ncpus=1'
        })
        j.set_sleep_time(1)

        j_id = self.server.submit(j)

        # Check for the E record for the arrayjob
        acct_string = ";E;" + str(j_id)
        _, record = self.server.accounting_match(acct_string, max_attempts=10,
                                                 interval=1)

        # Extract the 'start' value from the E record
        values = record.split(";", 3)[3]
        start_str = " start="
        values_temp = values.split(start_str, 1)[1]
        start_val = int(values_temp.split()[0])

        # Verify that the value of 'start' isn't 0
        self.assertNotEqual(start_val, 0,
                            "E record value of 'start' for arrayjob is 0")

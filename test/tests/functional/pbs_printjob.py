# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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


from tests.functional import *


class TestPrintjob(TestFunctional):
    def test_state_substate(self):
        """
        Verify that printjob prints the state and substate in expected format
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        a = {'job_state': 'R', 'substate': 42}
        self.server.expect(JOB, a, id=jid)
        ret = self.mom.printjob(jid)
        self.assertEqual(ret['rc'], 0)
        sfound = False
        ssfound = False
        for line in ret['out']:
            if line.startswith("state:"):
                val = line.split("state:", 1)[1]
                val = val.strip()
                numval = int(val, 16)
                self.assertEqual(numval, 4)  # R state = numeric 4
                sfound = True
            elif line.startswith("substate:"):
                val = line.split("substate:", 1)[1]
                val = val.split()[0]
                val = val.strip()
                numval = int(val, 16)
                self.assertEqual(numval, 42)
                ssfound = True
        self.assertTrue(sfound and ssfound)

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


class Test_create_vnodes(TestSelf):
    """
    Tests to test Server().create_vnodes()
    """

    def test_delall_multi(self):
        # Skip test if number of mom provided is not equal to two
        if len(self.moms) != 2:
            self.skipTest("test requires atleast two MoMs as input, "
                          "use -p moms=<mom1:mom2>")
        mom1 = self.moms.values()[0]
        mom2 = self.moms.values()[1]
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes(mom1.shortname, a, 4, mom1)
        self.server.create_vnodes(mom2.shortname, a, 5, mom2,
                                  usenatvnode=True, delall=False)
        stat = self.server.status(NODE)
        self.assertEqual(len(stat), 10)

    def test_delall(self):
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('first', a, 4, self.mom)
        self.server.create_vnodes('second', a, 5, self.mom,
                                  usenatvnode=True, delall=False)
        self.server.create_vnodes('third', a, 5, self.mom,
                                  delall=False)
        stat = self.server.status(NODE)
        self.assertEqual(len(stat), 14)

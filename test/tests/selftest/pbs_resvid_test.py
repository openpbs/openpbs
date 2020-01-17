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

from tests.selftest import *


class TestPTLConvertsResvIDtoid(TestSelf):
    """
    This test suite tests PTL should not convert
    'Resv ID' to 'id' when query a reservation
    """

    def test_attrib_ResvID(self):
        """
        Test reservation attribute 'Resv Id' in pbs_rstat output
        is not replaced with 'id' by PTL framework.
        """
        r = Reservation(TEST_USER)
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 10,
             'reserve_end': now + 110}
        r.set_attributes(a)
        rid = self.server.submit(r)
        val = self.server.status(RESV, id=rid)
        self.logger.info("Verifying attribute in pbs_rstat -f rid")
        self.assertIn('id', val[0], msg="Failed to get expected attrib id")
        self.logger.info("Got expected attribute id")
        self.logger.info("Look for attribute Resv ID")
        self.assertIn(
            'Resv ID', val[0], msg="Failed to get expected attrib Resv ID")
        self.logger.info("Got expected attribute Resv ID")

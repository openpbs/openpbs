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


class TestPTLConvertsResvIDtoid(TestSelf):
    """
    This test suite tests PTL should not convert
    'Resv ID' to 'id' when query a reservation
    """

    def test_attrib_ResvID(self):
        """
        Test attrib 'Resv Id' in pbs_rstat for
        reservation is not replace with 'id' in PTL_framework.
        PTL converts 'Resv_ID' to 'id' when querying a reservation
        """
        r = Reservation(TEST_USER)
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 10,
             'reserve_end': now + 110}
        r.set_attributes(a)
        rid = self.server.submit(r)
        val = self.server.status(RESV, id=rid)
        self.logger.info("Got value as list")
        print(val)
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)
        val = self.server.status(RESV, id=rid)
        self.logger.info("Got value as dictionary")
        print(val[0])
        self.logger.info("Verifying  attribs in pbs_rstat -f rid")
        self.assertIn('reserve_state', val[
                      0], msg="Failed to get expected attrib reserve_state")
        self.logger.info("Got expected attib reserve_state")
        self.assertIn('id', val[0], msg="Failed to get expected attrib id")
        self.logger.info("Got expected attib id")
        self.logger.info("Look for attib Resv ID!")
        self.assertIn(
            'Resv ID', val[0], msg="Failed to get expected attrib Resv ID")
        self.logger.info("Got expected attib Resv ID")

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

from tests.functional import *


class TestPbsRstat(TestFunctional):
    """
    This test suite validates output of pbs_rstat
    """

    def test_rstat_missing_resv(self):
        """
        Test that checks if pbs_rstat will continue to display
        reservations after not locating one reservation
        """

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 1000,
             'reserve_end': now + 2000}
        r = Reservation(TEST_USER)
        r.set_attributes(a)
        rid = self.server.submit(r)
        exp = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp, id=rid)

        a2 = {'Resource_List.select': '1:ncpus=1',
              'reserve_start': now + 3000,
              'reserve_end': now + 4000}
        r2 = Reservation(TEST_USER)
        r.set_attributes(a2)
        rid2 = self.server.submit(r)
        self.server.expect(RESV, exp, id=rid2)

        self.server.delresv(rid, wait=True)

        rstat_cmd = \
            os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_rstat')
        rstat_opt = [rstat_cmd, '-B', rid, rid2]
        ret = self.du.run_cmd(self.server.hostname, cmd=rstat_opt,
                              logerr=False)

        self.assertEqual(ret['rc'], 0,
                         'pbs_rstat returned with non-zero exit status')

        rstat_out = '\n'.join(ret['out'])
        self.assertIn(rid2, rstat_out)

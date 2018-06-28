# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
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

from tests.performance import *


class TestQsubPerformance(TestPerformance):
    """
    This test suite contains tests of qsub performance
    """

    def setUp(self):
        TestPerformance.setUp(self)
        attr = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)

    @timeout(400)
    def test_submit_large_env(self):
        """
        submission of 1000 jobs
        before and after exporting variable
        to check submission performance
        """

        start_time1 = time.time()
        for _ in range(1000):
            j = Job(TEST_USER)
            self.server.submit(j)
        end_time1 = time.time()

        os.environ['VARIABLE'] = 'b' * 130000

        start_time2 = time.time()
        for _ in range(1000):
            j1 = Job(TEST_USER)
            self.server.submit(j1)
        end_time2 = time.time()

        sub_time1 = int(end_time1 - start_time1)
        sub_time2 = int(end_time2 - start_time2)

        self.logger.info(
            "Submission time without env is %d and with env is %d sec"
            % (sub_time1, sub_time2))

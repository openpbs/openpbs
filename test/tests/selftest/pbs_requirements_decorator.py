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


@requirements(num_servers=1, num_comms=1, min_mom_ram=1,
              min_mom_disk=5, min_server_ram=1, min_server_disk=5)
class TestRequirementsDecorator(TestSelf):

    """
    This test suite is to verify functionality of requirements
    decorator. This test suite when run on single node without any
    hostnames passed in -p or param file, tests run and skip functionality
    of this decorator

    """
    @requirements(num_servers=1, num_comms=1, min_mom_ram=2,
                  min_mom_disk=5, min_server_ram=2, min_server_disk=5)
    def test_tc_run(self):
        """
        Test to verify test run when requirements are satisfied
        test suite requirements overridden by test case requirements
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(SERVER, {'server_state': 'Active'})
        requirements_set = {
            'num_servers': 1,
            'num_comms': 1
        }
        ds = getattr(self, REQUIREMENTS_KEY, {})
        if ds == requirements_set:
            raise self.failureException("Requirements not as expected")

    @requirements(num_servers=3)
    def test_tc_skip(self):
        """
        Test to verify test skip when requirements are not satisfied
        due to num_servers
        """
        self.server.expect(SERVER, {'server_state': 'Active'})

    def test_ts_skip(self):
        """
        Test to verify test skip when requirements are not satisfied
        at test suite level
        """
        self.server.expect(SERVER, {'server_state': 'Active'})

    @requirements(num_servers=1, num_comms=1, no_mom_on_server=True)
    def test_skip_no_server_on_mom(self):
        """
        Test to verify test skip when requirements are not satisfied
        due to no_mom_on_server flag
        """
        self.server.expect(SERVER, {'server_state': 'Active'})

    @requirements(num_servers=1, num_comms=1, no_comm_on_mom=True)
    def test_skip_no_comm_on_mom(self):
        """
        Test to verify test skip when requirements are not satisfied
        due to no_comm_on_mom flag set true
        """
        self.server.expect(SERVER, {'server_state': 'Active'})

    @requirements(num_comms=2, num_moms=2, no_comm_on_server=True)
    def test_skip_no_comm_on_server(self):
        """
        Test to verify test skip when requirements are not satisfied
        due to no_comm_on_server flag set true
        """
        self.server.expect(SERVER, {'server_state': 'Active'})

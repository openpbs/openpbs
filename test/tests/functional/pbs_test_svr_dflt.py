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

from tests.functional import *


class TestServerDefaultAttrib(TestFunctional):

    dflt_attr = {'scheduling': 'True',
                 'query_other_jobs': 'True',
                 'scheduler_iteration': '600',
                 'resources_default.ncpus': '1',
                 'log_events': '511',
                 'mail_from': 'adm',
                 'pbs_license_linger_time': '31536000',
                 'pbs_license_min': '0',
                 'pbs_license_max': '2147483647',
                 'eligible_time_enable': 'False',
                 'max_concurrent_provision': '5',
                 'resv_enable': 'True',
                 'max_array_size': '10000',
                 }

    def test_server_unset_dflt_attr(self):
        """
        Test that server sets the listed attributes with their default values
        when they are unset
        """
        for attr in self.dflt_attr:
            self.server.manager(MGR_CMD_UNSET, SERVER, attr)

        self.server.expect(SERVER, self.dflt_attr, attrop=PTL_AND,
                           max_attempts=20)

    def test_server_unset_dflt_attr_and_restart(self):
        """
        Test that server sets the listed attributes with their default values
        when they are unset and retain it across boots
        """
        for attr in self.dflt_attr:
            self.server.manager(MGR_CMD_UNSET, SERVER, attr)

        self.server.expect(SERVER, self.dflt_attr, attrop=PTL_AND,
                           max_attempts=20)
        self.server.restart()
        self.server.expect(SERVER, self.dflt_attr, attrop=PTL_AND,
                           max_attempts=20)

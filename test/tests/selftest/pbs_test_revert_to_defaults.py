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
from datetime import datetime, timedelta


class TestPTLRevertToDefault(TestSelf):
    """
    This test suite tests PTL's revert to default functionality
    """

    svr_dflt_attr = {'scheduling': 'True',
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

    def test_svr_revert_to_default(self):
        """
        This test case tests the server attributes after revert_to_default
        is called.
        """
        modified_attr = {'scheduling': 'FALSE',
                         'query_other_jobs': 'FALSE',
                         'scheduler_iteration': '100',
                         'resources_default.ncpus': '12',
                         'log_events': '2047',
                         'mail_from': 'user1',
                         'pbs_license_linger_time': '6000',
                         'pbs_license_min': '10',
                         'pbs_license_max': '3647',
                         'eligible_time_enable': 'TRUE',
                         'max_concurrent_provision': '15',
                         'resv_enable': 'FALSE',
                         'max_array_size': '900',
                         }
        self.server.manager(MGR_CMD_SET, SERVER, modified_attr)
        self.server.revert_to_defaults()

        self.server.expect(SERVER, self.svr_dflt_attr,
                           attrop=PTL_AND, max_attempts=20)

    def test_sched_revert_to_defaults_dedtime(self):
        """
        Test that revert_to_defaults() reverts the dedicated time file
        """
        dt_start = datetime.now() + timedelta(seconds=3600)
        dt_start_str = dt_start.strftime("%m/%d/%Y %H:%M")
        dt_end = dt_start + timedelta(seconds=3600)
        dt_end_str = dt_end.strftime("%m/%d/%Y %H:%M")
        self.scheduler.add_dedicated_time(dt_start_str + ' ' + dt_end_str)

        J = Job(attrs={'Resource_List.walltime': '7200'})
        jid = self.server.submit(J)

        a = {'job_state': 'Q',
             'comment': 'Not Running: Job would cross dedicated time boundary'}
        self.server.expect(JOB, a, id=jid)

        self.scheduler.revert_to_defaults()

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

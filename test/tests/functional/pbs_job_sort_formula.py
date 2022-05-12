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


class TestJobSortFormula(TestFunctional):
    """
    Tests for the job_sort_formula
    """

    def test_job_sort_formula_negative_value(self):
        """
        Test to see that negative values in the
        job_sort_formula sort properly
        """
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        self.server.manager(MGR_CMD_CREATE, RSC, {'type': 'float'}, id='foo')

        a = {'job_sort_formula': 'foo', 'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a, runas=ROOT_USER)

        j1 = Job(TEST_USER, attrs={'Resource_List.foo': -2})
        jid1 = self.server.submit(j1)
        j2 = Job(TEST_USER, attrs={'Resource_List.foo': -1})
        jid2 = self.server.submit(j2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        c = self.scheduler.cycles(lastN=1)[0]
        job_order = [jid2, jid1]
        for i, job in enumerate(job_order):
            self.assertEqual(job.split('.')[0], c.political_order[i])

        self.server.expect(JOB, {'job_state=R': 2})

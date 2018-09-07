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


class Test_TestparamsDecorator(TestSelf):

    """
    This test suite is to verify functionality of requirements
    decorator. The test specific parameters can be modified by
    -p or param file.

    """
    @testparams(num_jobs=100, scheduling=False)
    def test_testparams(self):
        """
        Test to submit n number of jobs and expect jobs to be
        in running or queued state as per tunable scheduling
        parameter.
        """
        scheduling = self.conf["Test_TestparamsDecorator.scheduling"]
        num_jobs = self.conf["Test_TestparamsDecorator.num_jobs"]
        a = {'resources_available.ncpus': num_jobs}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)
        a = {'scheduling': scheduling}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER)
        for _ in range(num_jobs):
            self.server.submit(j)
        if scheduling:
            self.server.expect(JOB, {'job_state=R': num_jobs})
        else:
            self.server.expect(JOB, {'job_state=Q': num_jobs})

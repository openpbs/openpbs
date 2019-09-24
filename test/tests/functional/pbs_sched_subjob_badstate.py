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


class TestSchedSubjobBadstate(TestFunctional):

    @timeout(600)
    def test_sched_badstate_subjob(self):
        """
        This test case tests if scheduler goes into infinite loop
        when following conditions are met.
        - Kill a mom
        - mark the mom's state as free
        - submit an array job
        - check the sched log for "Leaving sched cycle" from the time
          array job was submitted.
        If we are unable to find a log match then scheduler is in
          endless loop and test case has failed.
        """

        self.mom.signal('-KILL')

        attr = {'state': 'free', 'resources_available.ncpus': '2'}
        self.server.manager(MGR_CMD_SET, NODE, attr, self.mom.shortname)

        attr = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)

        j1 = Job(TEST_USER)
        j1.set_attributes({'Resource_List.ncpus': '2', ATTR_J: '1-3'})
        j1id = self.server.submit(j1)

        now = time.time()

        attr = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)

        self.scheduler.log_match("Leaving Scheduling Cycle",
                                 starttime=now,
                                 interval=1)
        self.server.delete(j1id)

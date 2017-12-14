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

from tests.functional import *


class Test_qorder(TestFunctional):
    """
    Test suite to test whether the political order of selecting a job to run
    in scheduler changes when one does a qorder.
    """

    def test_qorder_job(self):
        """
        Submit two jobs, switch their order using qorder and then check if the
        jobs are selected to run in the newly created order.
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j1 = Job(TEST_USER)
        j1.set_sleep_time(10)
        j2 = Job(TEST_USER)
        j2.set_sleep_time(10)
        jid1 = self.server.submit(j1)
        jid2 = self.server.submit(j2)

        rc = self.server.orderjob(jobid1=jid1, jobid2=jid2)
        self.assertEqual(rc, 0)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'server_state': 'Scheduling'}
        self.server.expect(SERVER, a, op=NE)

        jid2 = jid2.split('.')[0]
        cycle = self.scheduler.cycles(start=self.server.ctime, lastN=1)
        cycle = cycle[0]
        firstconsidered = cycle.political_order[0]
        msg = 'testinfo: first job considered [' + str(firstconsidered) + \
              '] == second submitted [' + str(jid2) + ']'
        self.logger.info(msg)

        self.assertEqual(firstconsidered, jid2)

    def test_qorder_job_across_queues(self):
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'queue_type': 'e', 'enabled': '1', 'started': '1'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')

        self.scheduler.set_sched_config({'by_queue': 'False'})

        a = {ATTR_queue: 'workq'}
        j1 = Job(TEST_USER, a)
        j1.set_sleep_time(10)
        a = {ATTR_queue: 'workq2'}
        j2 = Job(TEST_USER, a)
        j2.set_sleep_time(10)
        jid1 = self.server.submit(j1)
        jid2 = self.server.submit(j2)

        rc = self.server.orderjob(jobid1=jid1, jobid2=jid2)
        self.assertEqual(rc, 0)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'server_state': 'Scheduling'}
        self.server.expect(SERVER, a, op=NE)

        jid2 = jid2.split('.')[0]
        cycle = self.scheduler.cycles(start=self.server.ctime, lastN=1)
        cycle = cycle[0]
        firstconsidered = cycle.political_order[0]
        msg = 'testinfo: first job considered [' + str(firstconsidered) + \
              '] == second submitted [' + str(jid2) + ']'
        self.logger.info(msg)

        self.assertEqual(firstconsidered, jid2)

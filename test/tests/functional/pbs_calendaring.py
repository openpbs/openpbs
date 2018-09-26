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

import time
from tests.functional import *


class TestCalendaring(TestFunctional):

    """
    This test suite tests if PBS scheduler calendars events correctly
    """
    def test_topjob_start_time(self):
        """
        In this test we test that the top job which gets added to the
        calendar has estimated start time correctly set for future when
        job history is enabled and opt_backfill_fuzzy is turned off.
        """

        self.scheduler.set_sched_config({'strict_ordering': 'true all'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'backfill_depth': '2', 'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        # Turn opt_backfill_fuzzy off because we want to check if the job can
        # run after performing every end event in calendaring code instead
        # of rounding it off to next time boundary (default it 60 seconds)
        a = {'opt_backfill_fuzzy': 'off'}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 10,
                   'array_indices_submitted': '1-6'}
        j1 = Job(TEST_USER, attrs=res_req)
        j1.set_sleep_time(10)
        jid1 = self.server.submit(j1)
        j1_sub1 = j1.create_subjob_id(jid1, 1)
        j1_sub2 = j1.create_subjob_id(jid1, 2)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 10}
        j2 = Job(TEST_USER, attrs=res_req)
        jid2 = self.server.submit(j2)

        self.server.expect(JOB, {'job_state': 'X'}, j1_sub1)
        self.server.expect(JOB, {'job_state': 'R'}, j1_sub2)
        self.server.expect(JOB, {'job_state': 'Q'}, jid2)
        job1 = self.server.status(JOB, id=jid1)
        job2 = self.server.status(JOB, id=jid2)
        time_now = int(time.time())

        # get estimated start time of both the jobs
        self.assertIn('estimated.start_time', job1[0])
        est_val1 = job1[0]['estimated.start_time']
        self.assertIn('estimated.start_time', job2[0])
        est_val2 = job2[0]['estimated.start_time']
        est1 = time.strptime(est_val1, "%a %b %d %H:%M:%S %Y")
        est2 = time.strptime(est_val2, "%a %b %d %H:%M:%S %Y")
        est_epoch1 = int(time.mktime(est1))
        est_epoch2 = int(time.mktime(est2))

        # since only one subjob of array parent can become topjob
        # second job must start 10 seconds after that because
        # walltime of array job is 10 seconds.
        self.assertEqual(est_epoch2, est_epoch1+10)
        # Also make sure that since second subjob from array is running
        # Third subjob should set estimated.start_time in future.
        self.assertGreater(est_epoch1, time_now)

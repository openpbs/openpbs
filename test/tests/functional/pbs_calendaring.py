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


import time
from tests.functional import *
from ptl.utils.pbs_logutils import PBSLogUtils


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
                   'Resource_List.walltime': 30,
                   'array_indices_submitted': '1-6'}
        j1 = Job(TEST_USER, attrs=res_req)
        j1.set_sleep_time(30)
        jid1 = self.server.submit(j1)
        j1_sub1 = j1.create_subjob_id(jid1, 1)
        j1_sub2 = j1.create_subjob_id(jid1, 2)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 30}
        j2 = Job(TEST_USER, attrs=res_req)
        jid2 = self.server.submit(j2)

        self.server.expect(JOB, {'job_state': 'X'}, j1_sub1, interval=1)
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
        self.assertEqual(est_epoch2, est_epoch1 + 30)
        # Also make sure that since second subjob from array is running
        # Third subjob should set estimated.start_time in future.
        self.assertGreater(est_epoch1, time_now)

    def test_topjob_start_time_of_subjob(self):
        """
        In this test we test that the subjob which gets added to the
        calendar as top job and it has estimated start time correctly set when
        opt_backfill_fuzzy is turned off.
        """

        self.scheduler.set_sched_config({'strict_ordering': 'true all'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'backfill_depth': '2'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        # Turn opt_backfill_fuzzy off because we want to check if the job can
        # run after performing every end event in calendaring code instead
        # of rounding it off to next time boundary (default it 60 seconds)
        a = {'opt_backfill_fuzzy': 'off'}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 20,
                   'array_indices_submitted': '1-6'}
        j = Job(TEST_USER, attrs=res_req)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        j1_sub1 = j.create_subjob_id(jid, 1)
        j1_sub2 = j.create_subjob_id(jid, 2)

        self.server.expect(JOB, {'job_state': 'X'}, j1_sub1, interval=1)
        self.server.expect(JOB, {'job_state': 'R'}, j1_sub2)
        job_arr = self.server.status(JOB, id=jid)

        # check estimated start time is set on job array
        self.assertIn('estimated.start_time', job_arr[0])
        errmsg = jid + ";Error in calculation of start time of top job"
        self.scheduler.log_match(errmsg, existence=False, max_attempts=10)

    def test_topjob_fail(self):
        """
        Test that when we fail to add a job to the calendar it doesn't
        take up a topjob slot.  The server's backfill_depth is 1 by default,
        so we just need to submit a job that can never run and a job that can.
        The can never run job will fail to be added to the calendar and the
        second job will be.
        """

        # We need two nodes to create the situation where a job can never run.
        # We need to create this situation in such a way that the scheduler
        # doesn't detect it.  If the scheduler detects that a job can't run,
        # it won't try and add it to the calendar.  To do this, we ask for
        # 1 node with 2 cpus.  There are 2 nodes with 1 cpu each.
        attrs = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(attrib=attrs, num=2,
                               sharednode=False)

        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})

        # Submit job to eat up all the resources
        attrs = {'Resource_List.select': '2:ncpus=1',
                 'Resource_List.walltime': '1:00:00'}
        j1 = Job(TEST_USER, attrs)
        jid1 = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # submit job that can never run.
        attrs['Resource_List.select'] = '1:ncpus=2'
        j2 = Job(TEST_USER, attrs)
        jid2 = self.server.submit(j2)

        # submit a job that can run, but just not now
        attrs['Resource_List.select'] = '1:ncpus=1'
        j3 = Job(TEST_USER, attrs)
        jid3 = self.server.submit(j3)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        msg = jid2 + ';Error in calculation of start time of top job'
        self.scheduler.log_match(msg)

        msg = jid3 + ';Job is a top job and will run at'
        self.scheduler.log_match(msg)

    def test_topjob_bucket(self):
        """
        In this test we test that a bucket job will be calendared to start
        at the end of the last job on a node
        """

        self.scheduler.set_sched_config({'strict_ordering': 'true all'})
        a = {'resources_available.ncpus': 2}
        self.mom.create_vnodes(a, 1)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 30}
        j1 = Job(TEST_USER, attrs=res_req)
        j1.set_sleep_time(30)
        jid1 = self.server.submit(j1)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 45}
        j2 = Job(TEST_USER, attrs=res_req)
        j2.set_sleep_time(45)
        jid2 = self.server.submit(j2)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.place': 'excl'}
        j3 = Job(TEST_USER, attrs=res_req)
        jid3 = self.server.submit(j3)

        self.server.expect(JOB, {'job_state': 'R'}, jid1)
        self.server.expect(JOB, {'job_state': 'R'}, jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, jid3)
        job1 = self.server.status(JOB, id=jid1)
        job2 = self.server.status(JOB, id=jid2)
        job3 = self.server.status(JOB, id=jid3)

        end_time = time.mktime(time.strptime(job2[0]['stime'], '%c')) + 45
        est_time = job3[0]['estimated.start_time']
        est_time = time.mktime(time.strptime(est_time, '%c'))
        self.assertAlmostEqual(end_time, est_time, delta=1)

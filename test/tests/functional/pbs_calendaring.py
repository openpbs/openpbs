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

    def test_zero_resource_pushes_topjob(self):
        """
        This test case tests the scenario where a job that requests zero
        instance of a resource as the last resource in the select statement
        pushes the start time of top jobs
        """
        attrs = {'resources_available.ncpus': 4}
        self.mom.create_vnodes(attrib=attrs, num=5,
                               sharednode=False)

        attr = {ATTR_RESC_TYPE: 'long', ATTR_RESC_FLAG: 'hn'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='ngpus')

        resources = self.scheduler.sched_config['resources']
        resources = resources[:-1] + ', ngpus, zz\"'
        a = {'job_sort_key': '"job_priority HIGH ALL"',
             'resources': resources,
             'strict_ordering': 'True ALL'}
        self.scheduler.set_sched_config(a)

        a = {'Resource_List.select': '2:ncpus=4',
             'Resource_List.walltime': '1:00:00',
             'Resource_List.place': 'vscatter'}

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid1 = self.server.submit(j)

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid2 = self.server.submit(j)

        a = {'Resource_List.select': '5:ncpus=4',
             'Resource_List.walltime': '1:00:00',
             ATTR_p: "1000",
             'Resource_List.place': 'vscatter'}

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid3 = self.server.submit(j)

        a = {'Resource_List.select': '1:ncpus=4',
             'Resource_List.walltime': '24:00:01',
             'Resource_List.place': 'vscatter'}

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid4 = self.server.submit(j)

        a = {'Resource_List.select': '1:ncpus=4:ngpus=0',
             'Resource_List.walltime': '24:00:01',
             'Resource_List.place': 'vscatter'}

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid5 = self.server.submit(j)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid3)
        c = "Not Running: Job would conflict with reservation or top job"
        self.server.expect(JOB, {ATTR_state: 'Q', ATTR_comment: c}, id=jid4)
        self.server.expect(JOB, {ATTR_state: 'Q', ATTR_comment: c}, id=jid5)

    def test_zero_resource_job_conflict_resv(self):
        """
        This test case tests the scenario where a job that requests zero
        instance of a resource as the last resource in the select statement
        pushes the start time of reservations
        """
        attrs = {'resources_available.ncpus': 4}
        self.mom.create_vnodes(attrib=attrs, num=5,
                               sharednode=False)

        attr = {ATTR_RESC_TYPE: 'long', ATTR_RESC_FLAG: 'hn'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='ngpus')

        resources = self.scheduler.sched_config['resources']
        resources = resources[:-1] + ', ngpus, zz\"'
        a = {'job_sort_key': '"job_priority HIGH ALL"',
             'resources': resources,
             'strict_ordering': 'True ALL'}
        self.scheduler.set_sched_config(a)

        a = {'Resource_List.select': '2:ncpus=4',
             'Resource_List.walltime': '1:00:00',
             'Resource_List.place': 'vscatter'}

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid1 = self.server.submit(j)

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid2 = self.server.submit(j)

        now = int(time.time())
        a = {'Resource_List.select': '5:ncpus=4',
             'reserve_start': now + 3610,
             'reserve_end': now + 6610,
             'Resource_List.place': 'vscatter'}

        r = Reservation(TEST_USER)
        r.set_attributes(a)
        rid = self.server.submit(r)
        exp = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp, id=rid)

        a = {'Resource_List.select': '1:ncpus=4',
             'Resource_List.walltime': '24:00:01',
             'Resource_List.place': 'vscatter'}

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid3 = self.server.submit(j)

        a = {'Resource_List.select': '1:ncpus=4:ngpus=0',
             'Resource_List.walltime': '24:00:01',
             'Resource_List.place': 'vscatter'}

        j = Job(TEST_USER)
        j.set_attributes(a)
        jid4 = self.server.submit(j)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        c = "Not Running: Job would conflict with reservation or top job"
        self.server.expect(JOB, {ATTR_state: 'Q', ATTR_comment: c}, id=jid3)
        self.server.expect(JOB, {ATTR_state: 'Q', ATTR_comment: c}, id=jid4)

    def test_topjob_stale_estimates_clearing_on_clear_attr_set(self):
        """
        In this test we test that former top job with stale estimate
        gets the estimate cleared once the server attribute
        clear_topjob_estimates_enable is set to True
        """

        self.scheduler.set_sched_config({'strict_ordering': 'true all'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'backfill_depth': '2'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'scheduler_iteration': '5'}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 300}
        j1 = Job(TEST_USER, attrs=res_req)
        jid1 = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, jid1)

        j2 = Job(TEST_USER, attrs=res_req)
        jid2 = self.server.submit(j2)
        job2 = self.server.status(JOB, id=jid2)
        self.assertIn('estimated.start_time', job2[0])
        self.assertIn('estimated.exec_vnode', job2[0])
        self.server.expect(JOB, {'topjob': True}, jid2, max_attempts=5)

        a = {'backfill_depth': '0'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        time.sleep(6)

        job2 = self.server.status(JOB, id=jid2)
        self.assertIn('estimated.start_time', job2[0])
        self.assertIn('estimated.exec_vnode', job2[0])
        self.server.expect(JOB, {'topjob': False}, jid2, max_attempts=5)

        a = {'clear_topjob_estimates_enable': True}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.expect(JOB, 'estimated.start_time', id=jid2, op=UNSET,
                           interval=1, max_attempts=10)
        self.server.expect(JOB, 'estimated.exec_vnode', id=jid2, op=UNSET,
                           interval=1, max_attempts=10)

    def test_topjob_estimates_clearing_enabled(self):
        """
        In this test we test that the top job which gets added to the
        calendar with valid estimate has estimate cleared once it losses
        top job status. The clearing needs to have the server attribute
        clear_topjob_estimates_enable set to true. Also, the job's topjob
        attribute is set accordingly.
        """

        self.scheduler.set_sched_config({'strict_ordering': 'true all'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'backfill_depth': '2', 'clear_topjob_estimates_enable': True}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'scheduler_iteration': '5'}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 300}
        j1 = Job(TEST_USER, attrs=res_req)
        jid1 = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, jid1)

        j2 = Job(TEST_USER, attrs=res_req)
        jid2 = self.server.submit(j2)
        job2 = self.server.status(JOB, id=jid2)
        self.assertIn('estimated.start_time', job2[0])
        self.assertIn('estimated.exec_vnode', job2[0])
        self.server.expect(JOB, {'topjob': True}, jid2, max_attempts=5)

        a = {'backfill_depth': '0'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        time.sleep(6)

        job2 = self.server.status(JOB, id=jid2)
        self.assertNotIn('estimated.start_time', job2[0])
        self.assertNotIn('estimated.exec_vnode', job2[0])
        self.server.expect(JOB, {'topjob': False}, jid2, max_attempts=5)

    def test_topjob_estimates_clearing_disabled(self):
        """
        In this test we test that the top job which gets added to the
        calendar with valid estimate has not estimate cleared if it losses
        top job status. The clearing is prevented by clear_topjob_estimates_enable
        set to false/unset. Also, the job's topjob attribute is set accordingly.
        """

        self.scheduler.set_sched_config({'strict_ordering': 'true all'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'backfill_depth': '2', 'clear_topjob_estimates_enable': False}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'scheduler_iteration': '5'}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        res_req = {'Resource_List.select': '1:ncpus=1',
                   'Resource_List.walltime': 300}
        j1 = Job(TEST_USER, attrs=res_req)
        jid1 = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, jid1)

        j2 = Job(TEST_USER, attrs=res_req)
        jid2 = self.server.submit(j2)
        job2 = self.server.status(JOB, id=jid2)
        self.assertIn('estimated.start_time', job2[0])
        self.assertIn('estimated.exec_vnode', job2[0])
        self.server.expect(JOB, {'topjob': True}, jid2, max_attempts=5)

        a = {'backfill_depth': '0'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        time.sleep(6)

        job2 = self.server.status(JOB, id=jid2)
        self.assertIn('estimated.start_time', job2[0])
        self.assertIn('estimated.exec_vnode', job2[0])
        self.server.expect(JOB, {'topjob': False}, jid2, max_attempts=5)

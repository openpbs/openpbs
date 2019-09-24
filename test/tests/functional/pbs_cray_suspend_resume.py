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

import time
from tests.functional import *
from ptl.utils.pbs_crayutils import CrayUtils


@tags('cray')
class TestSuspendResumeOnCray(TestFunctional):

    """
    Test special cases where suspend/resume functionality differs on cray
    as compared to other platforms.
    This test suite expects the platform to be 'cray' and assumes that
    suspend/resume feature is enabled on it.
    """
    cu = CrayUtils()

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on a Cray")
        TestFunctional.setUp(self)

    @tags('cray', 'smoke')
    def test_default_restrict_res_to_release_on_suspend_setting(self):
        """
        Check that on Cray restrict_res_to_release_on_suspend is always set
        to 'ncpus' by default
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.expect(SERVER, a)

    def test_exclusive_job_not_suspended(self):
        """
        If a running job is a job with exclusive placement then this job can
        not be suspended.
        This test is checking for a log message which is an unstable
        interface and may need change in future when interface changes.
        """

        msg_expected = "BASIL;ERROR: ALPS error: apsched: \
at least resid .* is exclusive"
        # Submit a job
        j = Job(TEST_USER, {ATTR_l + '.select': '1:ncpus=1',
                            ATTR_l + '.place': 'excl'})
        check_after = int(time.time())
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # suspend job
        try:
            self.server.sigjob(jobid=jid, signal="suspend")
        except PbsSignalError as e:
            self.assertTrue("Switching ALPS reservation failed" in e.msg[0])

        self.server.expect(JOB, 'exec_host', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        ehost = job_stat[0]['exec_host'].partition('/')[0]
        run_mom = self.moms[ehost]
        s = run_mom.log_match(msg_expected, starttime=check_after, regexp=True,
                              max_attempts=10)
        self.assertTrue(s)

    @tags('cray')
    def test_basic_admin_suspend_restart(self):
        """
        Test basic admin-suspend funcionality for jobs and array jobs with
        restart on Cray. The restart will test if the node recovers properly
        in maintenance. After turning off scheduling and a server restart, a
        subjob is always requeued and node shows up as free.
        """
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        qstat = self.server.status(JOB, 'exec_vnode', id=jid1)
        vname = qstat[0]['exec_vnode'].partition(':')[0].strip('(')

        # admin-suspend regular job
        self.server.sigjob(jid1, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(NODE, {'state': 'maintenance'}, id=vname)
        self.server.expect(NODE, {'maintenance_jobs': jid1})

        self.server.restart()
        self.server.expect(NODE, {'state': 'maintenance'}, id=vname)
        self.server.expect(NODE, {'maintenance_jobs': jid1})

        # Adding sleep to avoid failure at resume since PBS licenses
        # might not be available and as a result resume fails
        time.sleep(2)

        # admin-resume regular job. Make sure the node retuns to state
        # job-exclusive.
        self.server.sigjob(jid1, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=vname)
        self.server.cleanup_jobs()

        # admin-suspend job array
        jA = Job(TEST_USER, {ATTR_l + '.select': '1:ncpus=1', ATTR_J: '1-2'})
        jidA = self.server.submit(jA)
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jidA)

        subjobs = self.server.status(JOB, id=jidA, extend='t')
        # subjobs[0] is the array itself.  Need the subjobs
        jid1 = subjobs[1]['id']
        jid2 = subjobs[2]['id']

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        qstat = self.server.status(JOB, 'exec_vnode', id=jid1)
        vname1 = qstat[0]['exec_vnode'].partition(':')[0].strip('(')
        qstat = self.server.status(JOB, 'exec_vnode', id=jid2)
        vname2 = qstat[0]['exec_vnode'].partition(':')[0].strip('(')

        # admin-suspend subjob 1
        self.server.sigjob(jid1, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)
        self.server.expect(NODE, {'state': 'maintenance'}, id=vname1)
        self.server.expect(NODE, {'maintenance_jobs': jid1})

        # admin-resume subjob 1 . Make sure the node retuns to state
        # job-exclusive.
        self.server.sigjob(jid1, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=vname1)

        # admin-suspend subjob 2
        self.server.sigjob(jid2, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid2)
        self.server.expect(NODE, {'state': 'maintenance'}, id=vname2)
        self.server.expect(NODE, {'maintenance_jobs': jid2})

        # Turn off scheduling and restart server
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.restart()

        # Check that nodes are now free
        self.server.expect(NODE, {'state': 'free'}, id=vname1)
        self.server.expect(NODE, {'state': 'free'}, id=vname2)

    def test_admin_suspend_wrong_state(self):
        """
        Check that wrong 'resume' signal is correctly rejected.
        """
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.sigjob(jid1, "suspend", runas=ROOT_USER)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

        try:
            self.server.sigjob(jid1, "admin-resume", runas=ROOT_USER)
        except PbsSignalError as e:
            self.assertTrue(
                'Job can not be resumed with the requested resume signal'
                in e.msg[0])
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid1)

        j2 = Job(TEST_USER)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.sigjob(jid2, "admin-suspend", runas=ROOT_USER)
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 43}, id=jid2)

        try:
            self.server.sigjob(jid2, "resume", runas=ROOT_USER)
        except PbsSignalError as e:
            self.assertTrue(
                'Job can not be resumed with the requested resume signal'
                in e.msg[0])

        # The job should be in the same state as it was prior to the signal
        self.server.expect(JOB, {ATTR_state: 'S', ATTR_substate: 43}, id=jid2)

    def submit_resv(self, resv_start, chunks, resv_dur):
        """
        Function to request a PBS reservation with start time, chunks and
        duration as arguments.
        """
        a = {'Resource_List.select': '%d:ncpus=1:vntype=cray_compute' % chunks,
             'Resource_List.place': 'scatter',
             'reserve_start': int(resv_start),
             'reserve_duration': int(resv_dur)
             }
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        try:
            a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
            d = self.server.expect(RESV, a, id=rid)
        except PtlExpectError as e:
            d = e.rv
        return d

    @timeout(300)
    def test_preempt_STF(self):
        """
        Test shrink to fit by creating a reservation for all compute nodes
        starting in 100 sec. with a duration of two hours.  A preempted STF job
        with min_walltime of 1 min. and max_walltime of 2 hours will stay
        suspended after higher priority job goes away if its
        min_walltime can't be satisfied.
        """
        qname = 'highp'
        a = {'queue_type': 'execution'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)
        a = {'enabled': 'True', 'started': 'True', 'priority': '150'}
        self.server.manager(MGR_CMD_SET, QUEUE, a, qname)

        # Reserve all the compute nodes
        nv = self.cu.num_compute_vnodes(self.server)
        self.assertNotEqual(nv, 0, "There are no cray_compute vnodes present.")
        now = time.time()
        resv_start = now + 100
        resv_dur = 7200
        d = self.submit_resv(resv_start, nv, resv_dur)
        self.assertTrue(d)

        j = Job(TEST_USER, {ATTR_l + '.select': '%d:ncpus=1' % nv,
                            ATTR_l + '.place': 'scatter',
                            ATTR_l + '.min_walltime': '00:01:00',
                            ATTR_l + '.max_walltime': '02:00:00'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        self.server.expect(
            JOB, {ATTR_l + '.walltime': (LE, '00:01:40')}, id=jid)
        self.server.expect(
            JOB, {ATTR_l + '.walltime': (GE, '00:01:00')}, id=jid)

        # The sleep below will leave less than 1 minute window for jid
        # after j2id is deleted. The min_walltime of jid can't be
        # satisfied and jid will stay in S state.
        time.sleep(35)

        j2 = Job(TEST_USER, {ATTR_l + '.select': '%d:ncpus=1' % nv,
                             ATTR_l + '.walltime': '00:01:00',
                             ATTR_l + '.place': 'scatter',
                             ATTR_q: 'highp'})
        j2id = self.server.submit(j2)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=j2id)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

        # The sleep below will leave less than 1 minute window for jid
        time.sleep(50)

        self.server.delete(j2id)
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(SERVER, {'server_state': 'Active'})
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_multi_express(self):
        """
        Test of multiple express queues of different priorities.
        See that jobs from the higher express queues preempt jobs
        from lower express queues.  Also see when express jobs finish
        (or are deleted), suspended jobs restart.
        Make sure loadLimit is set to 4 on the server node:
        # apmgr config loadLimit 4
        """

        _t = ('\"express_queue, normal_jobs, server_softlimits,' +
              ' queue_softlimits\"')
        a = {'preempt_prio': _t}
        self.scheduler.set_sched_config(a)

        a = {'queue_type': 'e',
             'started': 'True',
             'enabled': 'True',
             'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")

        a['Priority'] = 160
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq2")

        a['Priority'] = 170
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq3")

        # Count the compute nodes
        nv = self.cu.num_compute_vnodes(self.server)
        self.assertNotEqual(nv, 0, "There are no cray_compute vnodes present.")

        j1 = Job(TEST_USER, {ATTR_l + '.select': '%d:ncpus=1' % nv,
                             ATTR_l + '.place': 'scatter',
                             ATTR_l + '.walltime': 3600})
        j1id = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1id)

        j2 = Job(TEST_USER, {ATTR_l + '.select': '%d:ncpus=1' % nv,
                             ATTR_l + '.place': 'scatter',
                             ATTR_l + '.walltime': 3600,
                             ATTR_q: 'expressq'})
        j2id = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=j1id)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j2id)

        j3 = Job(TEST_USER, {ATTR_l + '.select': '%d:ncpus=1' % nv,
                             ATTR_l + '.place': 'scatter',
                             ATTR_l + '.walltime': 3600,
                             ATTR_q: 'expressq2'})
        j3id = self.server.submit(j3)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=j2id)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j3id)

        j4 = Job(TEST_USER, {ATTR_l + '.select': '%d:ncpus=1' % nv,
                             ATTR_l + '.place': 'scatter',
                             ATTR_l + '.walltime': 3600,
                             ATTR_q: 'expressq3'})
        j4id = self.server.submit(j4)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=j3id)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j4id)

        self.server.delete(j4id)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j3id)

    def test_preempted_topjob_calendared(self):
        """
        That even if topjob_ineligible is set for
        a preempted job and sched_preempt_enforce_resumption
        is set true, the preempted job will be calendared
        """
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_preempt_enforce_resumption': 'true'})
        self.server.manager(MGR_CMD_SET, SERVER, {'backfill_depth': '2'})

        # Count the compute nodes
        nv = self.cu.num_compute_vnodes(self.server)
        self.assertNotEqual(nv, 0, "There are no cray_compute vnodes present.")

        # Submit a job
        j = Job(TEST_USER, {ATTR_l + '.select': '%d:ncpus=1' % nv,
                            ATTR_l + '.place': 'scatter',
                            ATTR_l + '.walltime': '120'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Alter topjob_ineligible for runnng job
        self.server.alterjob(jid1, {ATTR_W: "topjob_ineligible = true"},
                             runas=ROOT_USER, logerr=True)

        # Create a high priority queue
        a = {'queue_type': 'e', 'started': 't',
             'enabled': 'True', 'priority': '150'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id="highp")

        # Submit a job to high priority queue
        j = Job(TEST_USER, {ATTR_queue: 'highp', ATTR_l + '.walltime': '60'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

        # Verify that job1 is calendared
        self.server.expect(JOB, 'estimated.start_time',
                           op=SET, id=jid1)
        qstat = self.server.status(JOB, 'estimated.start_time',
                                   id=jid1)
        est_time = qstat[0]['estimated.start_time']
        self.assertNotEqual(est_time, None)
        self.scheduler.log_match(jid1 + ";Job is a top job",
                                 starttime=self.server.ctime,
                                 max_attempts=10)

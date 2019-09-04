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

from ptl.utils.pbs_testsuite import *


@tags('smoke')
class SmokeTest(PBSTestSuite):

    """
    This test suite contains a few smoke tests of PBS

    """
    # Class variables
    resc_types = [None, 'long', 'float', 'boolean', 'size', 'string',
                  'string_array']
    resc_flags = [None, 'n', 'h', 'nh', 'q', 'f', 'fh', 'm', 'mh']
    resc_flags_ctl = [None, 'r', 'i']
    objs = [QUEUE, SERVER, NODE, JOB, RESV]
    resc_name = "ptl_custom_res"
    avail_resc_name = 'resources_available.' + resc_name
    pu = ProcUtils()

    def test_submit_job(self):
        """
        Test to submit a job
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    @skipOnCpuSet
    def test_submit_job_array(self):
        """
        Test to submit a job array
        """
        a = {'resources_available.ncpus': 8}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER)
        j.set_attributes({ATTR_J: '1-3:1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')

    @skipOnCpuSet
    def test_advance_reservation(self):
        """
        Test to submit an advanced reservation and submit jobs to that
        reservation. Check if the reservation gets confimed and the jobs
        inside the reservation starts running when the reservation runs.
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)
        r = Reservation(TEST_USER)
        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=4',
             'reserve_start': now + 10,
             'reserve_end': now + 110}
        r.set_attributes(a)
        rid = self.server.submit(r)
        rid_q = rid.split('.')[0]
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        # submit a normal job and an array job to the reservation
        a = {'Resource_List.select': '1:ncpus=1',
             ATTR_q: rid_q}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        a = {'Resource_List.select': '1:ncpus=1',
             ATTR_q: rid_q, ATTR_J: '1-2'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)

        a = {'reserve_state': (MATCH_RE, "RESV_RUNNING|5")}
        self.server.expect(RESV, a, id=rid, interval=1)
        self.server.expect(JOB, {'job_state': 'R'}, jid1)
        self.server.expect(JOB, {'job_state': 'B'}, jid2)

    def test_standing_reservation(self):
        """
        Test to submit a standing reservation
        """
        # PBS_TZID environment variable must be set, there is no way to set
        # it through the API call, use CLI instead for this test

        _m = self.server.get_op_mode()
        if _m != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'
        a = {'Resource_List.select': '1:ncpus=1',
             ATTR_resv_rrule: 'FREQ=WEEKLY;COUNT=3',
             ATTR_resv_timezone: tzone,
             ATTR_resv_standing: '1',
             'reserve_start': time.time() + 20,
             'reserve_end': time.time() + 30, }
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)
        if _m == PTL_API:
            self.server.set_op_mode(PTL_API)

    @skipOnCpuSet
    def test_degraded_advance_reservation(self):
        """
        Make reservations more fault tolerant
        Test for an advance reservation
        """

        now = int(time.time())
        a = {'reserve_retry_init': 5, 'reserve_retry_cutoff': 1}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vn', a, num=2, mom=self.mom)
        a = {'Resource_List.select': '1:ncpus=4',
             'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)
        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]
        a = {'state': 'offline'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=resv_node)
        a = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}
        self.server.expect(RESV, a, id=rid)
        a = {'resources_available.ncpus': (GT, 0)}
        free_nodes = self.server.filter(NODE, a)
        nodes = free_nodes.values()[0]
        other_node = [nodes[0], nodes[1]][resv_node == nodes[0]]
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
             'resv_nodes': (MATCH_RE, re.escape(other_node))}
        self.server.expect(RESV, a, id=rid, offset=3, attrop=PTL_AND)

    def test_select(self):
        """
        Test to qselect
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        jobs = self.server.select()
        self.assertNotEqual(jobs, None)

    def test_alter(self):
        """
        Test to alter job
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.server.alterjob(jid, {'comment': 'job comment altered'})
        self.server.expect(JOB, {'comment': 'job comment altered'}, id=jid)

    def test_sigjob(self):
        """
        Test to signal job
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42},
                           attrop=PTL_AND, id=jid)
        self.server.sigjob(jid, 'suspend')
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)
        self.server.sigjob(jid, 'resume')
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    @skipOnCpuSet
    def test_backfilling(self):
        """
        Test for backfilling
        """
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 3600}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        a = {'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 3600}
        j = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, 'comment', op=SET, id=jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 1800}
        j = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

    def test_hold_release(self):
        """
        Test to hold and release a job
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        a = {'job_state': 'R', 'substate': '42'}
        self.server.expect(JOB, a, jid, attrop=PTL_AND)
        self.server.holdjob(jid, USER_HOLD)
        self.server.expect(JOB, {'Hold_Types': 'u'}, jid)
        self.server.rlsjob(jid, USER_HOLD)
        self.server.expect(JOB, {'Hold_Types': 'n'}, jid)

    @skipOnCpuSet
    def test_create_vnode(self):
        """
        Test to create vnodes
        """
        self.server.expect(SERVER, {'pbs_version': '8'}, op=GT)
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        a = {'resources_available.ncpus': 20, 'sharing': 'force_excl'}
        momstr = self.mom.create_vnode_def('testnode', a, 10)
        self.mom.insert_vnode_def(momstr)
        self.server.manager(MGR_CMD_CREATE, NODE, None, self.mom.hostname)
        a = {'resources_available.ncpus=20': 10}
        self.server.expect(VNODE, a, count=True, interval=5)

    def test_create_execution_queue(self):
        """
        Test to create execution queue
        """
        qname = 'testq'
        try:
            self.server.manager(MGR_CMD_DELETE, QUEUE, None, qname)
        except PbsManagerError:
            pass
        a = {'queue_type': 'Execution', 'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)
        self.server.manager(MGR_CMD_DELETE, QUEUE, id=qname)

    def test_create_routing_queue(self):
        """
        Test to create routing queue
        """
        qname = 'routeq'
        try:
            self.server.manager(MGR_CMD_DELETE, QUEUE, None, qname)
        except PbsManagerError:
            pass
        a = {'queue_type': 'Route', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)
        self.server.manager(MGR_CMD_DELETE, QUEUE, id=qname)

    @skipOnCpuSet
    def test_fgc_limits(self):
        """
        Test for limits
        """
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('lt', a, 2, self.mom)
        a = {'max_run': '[u:' + str(TEST_USER) + '=2]'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(SERVER, a)
        j1 = Job(TEST_USER)
        j2 = Job(TEST_USER)
        j3 = Job(TEST_USER)
        j1id = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, j1id)
        j2id = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        j3id = self.server.submit(j3)
        self.server.expect(JOB, 'comment', op=SET, id=j3id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j3id)

    @skipOnCpuSet
    def test_limits(self):
        """
        Test for limits
        """
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('lt', a, 2, self.mom)
        a = {'max_run_res.ncpus': '[u:' + str(TEST_USER) + '=1]'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        for _ in range(3):
            j = Job(TEST_USER)
            self.server.submit(j)
        a = {'server_state': 'Scheduling'}
        self.server.expect(SERVER, a, op=NE)
        a = {'job_state=R': 1, 'euser=' + str(TEST_USER): 1}
        self.server.expect(JOB, a, attrop=PTL_AND)

    @skipOnCpuSet
    @skip('This test is broken for oss')
    def test_finished_jobs(self):
        """
        Test for finished jobs and resource used for jobs.
        """
        a = {'resources_available.ncpus': '2'}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'Resource_List.ncpus': 2}
        j = Job(TEST_USER, a)
        j.set_sleep_time(15)
        j.create_eatcpu_job(15)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'F'}, extend='x', offset=15,
                           interval=1, id=jid)
        jobs = self.server.status(JOB, id=jid, extend='x')
        exp_eq_val = {ATTR_used+'.ncpus': '2',
                      ATTR_used+'.cput': '00:00:15', ATTR_exit_status: '0'}
        for key in exp_eq_val:
            self.assertEquals(exp_eq_val[key], jobs[0][key])
        exp_noteq_val = {ATTR_used+'.walltime': '00:00:00',
                         ATTR_used+'.mem': '0kb', ATTR_used+'.cpupercent': '0'}
        for key in exp_noteq_val:
            self.assertNotEquals(exp_noteq_val[key], jobs[0][key])

    def test_project_based_limits(self):
        """
        Test for project based limits
        """
        proj = 'testproject'
        a = {'max_run': '[p:' + proj + '=1]'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        for _ in range(5):
            j = Job(TEST_USER, attrs={ATTR_project: proj})
            self.server.submit(j)
        self.server.expect(SERVER, {'server_state': 'Scheduling'}, op=NE)
        self.server.expect(JOB, {'job_state=R': 1})

    @skipOnCpuSet
    def test_job_scheduling_order(self):
        """
        Test for job scheduling order
        """
        a = {'backfill_depth': 5}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        a = {'resources_available.ncpus': '1'}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'state=free': 1}
        self.server.expect(VNODE, a, attrop=PTL_AND)
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        for _ in range(6):
            j = Job(TEST_USER, attrs={'Resource_List.select': '1:ncpus=1',
                                      'Resource_List.walltime': 3600})
            self.server.submit(j)
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'server_state': 'Scheduling'}
        self.server.expect(SERVER, a, op=NE)
        self.server.expect(JOB, {'estimated.start_time': 5},
                           count=True, op=SET)

    @skipOnCpuSet
    def test_preemption(self):
        """
        Test for preemption
        """
        a = {'log_filter': 2048}
        self.scheduler.set_sched_config(a)
        a = {'resources_available.ncpus': '1'}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        self.server.status(QUEUE)
        if 'expressq' in self.server.queues.keys():
            self.server.manager(MGR_CMD_DELETE, QUEUE, None, 'expressq')
        a = {'queue_type': 'execution'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, 'expressq')
        a = {'enabled': 'True', 'started': 'True', 'priority': 150}
        self.server.manager(MGR_CMD_SET, QUEUE, a, 'expressq')
        j = Job(TEST_USER, attrs={'Resource_List.select': '1:ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        j2 = Job(TEST_USER,
                 attrs={'queue': 'expressq',
                        'Resource_List.select': '1:ncpus=1'})
        j2id = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

    @skipOnCpuSet
    def test_preemption_qrun(self):
        """
        Test that a job is preempted when a high priority job is run via qrun
        """
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 1},
                            id=self.mom.shortname)

        j = Job(TEST_USER)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        jid2 = self.server.submit(j2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        self.server.runjob(jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        self.scheduler.log_match(jid1 + ";Job preempted by suspension")

    @skipOnCpuSet
    def test_fairshare(self):
        """
        Test for fairshare
        """
        a = {'fair_share': 'true ALL',
             'fairshare_usage_res': 'ncpus*walltime',
             'unknown_shares': 10}
        self.scheduler.set_sched_config(a)
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vnode', a, 4, self.mom)
        a = {'Resource_List.select': '1:ncpus=4'}
        for _ in range(10):
            j = Job(TEST_USER1, a)
            self.server.submit(j)
        a = {'job_state=R': 4}
        self.server.expect(JOB, a)
        self.logger.info('testinfo: waiting for walltime accumulation')
        running_jobs = self.server.filter(JOB, {'job_state': 'R'})
        if running_jobs.values():
            for _j in running_jobs.values()[0]:
                a = {'resources_used.walltime': (NE, '00:00:00')}
                self.server.expect(JOB, a, id=_j, interval=1, max_attempts=30)
        j = Job(TEST_USER2)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid, offset=5)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        a = {'server_state': 'Scheduling'}
        self.server.expect(SERVER, a, op=NE)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        cycle = self.scheduler.cycles(start=self.server.ctime, lastN=10)
        if len(cycle) > 0:
            i = len(cycle) - 1
            while len(cycle[i].political_order) == 0:
                i -= 1
            cycle = cycle[i]
            firstconsidered = cycle.political_order[0]
            lastsubmitted = jid.split('.')[0]
            msg = 'testinfo: first job considered [' + str(firstconsidered) + \
                  '] == last submitted [' + str(lastsubmitted) + ']'
            self.logger.info(msg)
            self.assertEqual(firstconsidered, lastsubmitted)

    def test_server_hook(self):
        """
        Create a hook, import a hook content that rejects all jobs, verify
        that a job is rejected by the hook.
        """
        hook_name = "testhook"
        hook_body = "import pbs\npbs.event().reject('my custom message')\n"
        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, a, hook_body)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})
        j = Job(TEST_USER)
        now = int(time.time())
        try:
            self.server.submit(j)
        except PbsSubmitError:
            pass
        self.server.log_match("my custom message", starttime=now)

    def test_mom_hook(self):
        """
        Create a hook, import a hook content that rejects all jobs, verify
        that a job is rejected by the hook.
        """
        hook_name = "momhook"
        hook_body = "import pbs\npbs.event().reject('my custom message')\n"
        a = {'event': 'execjob_begin', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, a, hook_body)
        # Asynchronous copy of hook content, we wait for the copy to occur
        self.server.log_match(".*successfully sent hook file.*" +
                              hook_name + ".PY" + ".*", regexp=True,
                              max_attempts=100, interval=5)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.mom.log_match("my custom message", starttime=self.server.ctime,
                           interval=1)

    @skipOnCpuSet
    def test_shrink_to_fit(self):
        """
        Smoke test shrink to fit by setting a dedicated time to start in an
        hour and submit a job that can run for as low as 59 mn and as long as
        4 hours. Expect the job's walltime to be greater or equal than the
        minimum set.
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        now = time.time()
        self.scheduler.add_dedicated_time(start=now + 3600, end=now + 7200)
        j = Job(TEST_USER)
        a = {'Resource_List.max_walltime': '04:00:00',
             'Resource_List.min_walltime': '00:58:00'}
        j.set_attributes(a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        attr = {'Resource_List.walltime':
                (GE, a['Resource_List.min_walltime'])}
        self.server.expect(JOB, attr, id=jid)

    def test_submit_job_with_script(self):
        """
        Test to submit job with job script
        """
        a = {ATTR_rescavail + '.ncpus': '2'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)
        j = Job(TEST_USER, attrs={ATTR_N: 'test'})
        j.create_script('sleep 120\n', hostname=self.server.client)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.logger.info("Testing script with extension")
        j = Job(TEST_USER)
        fn = self.du.create_temp_file(suffix=".scr", body="/bin/sleep 10",
                                      asuser=str(TEST_USER))
        try:
            jid = self.server.submit(j, script=fn)
        except PbsSubmitError as e:
            self.assertNotIn('illegal -N value', e.msg[0],
                             'qsub: Not accepted "." in job name')
        else:
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
            self.logger.info('Job submitted successfully: ' + jid)

    @skipOnCpuSet
    def test_formula_match(self):
        """
        Test for job sort formula
        """
        a = {'resources_available.ncpus': 8}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        self.scheduler.set_sched_config({'log_filter': '2048'})
        a = {'job_sort_formula': 'ncpus'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        # purposely submitting a job that is highly unlikely to run so
        # it stays Q'd
        j = Job(TEST_USER, attrs={'Resource_List.select': '1:ncpus=128'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        _f1 = self.scheduler.job_formula(jid)
        _f2 = self.server.evaluate_formula(jid, full=False)
        self.assertEqual(_f1, _f2)
        self.logger.info(str(_f1) + " = " + str(_f2) + " ... OK")

    @skipOnShasta
    def test_staging(self):
        """
        Test for file staging
        """
        fn = self.du.create_temp_file(asuser=str(TEST_USER))
        a = {ATTR_stagein: fn + '2@' + self.server.hostname + ':' + fn}
        j = Job(TEST_USER, a)
        j.set_sleep_time(2)
        jid = self.server.submit(j)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=2)
        a = {ATTR_stageout: fn + '@' + self.server.hostname + ':' + fn + '2'}
        j = Job(TEST_USER, a)
        j.set_sleep_time(2)
        jid = self.server.submit(j)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=2)
        self.du.rm(self.server.hostname, fn, force=True, sudo=True)
        self.du.rm(self.server.hostname, fn + '2', force=True, sudo=True)

    def test_route_queue(self):
        """
        Verify that a routing queue routes a job into the appropriate execution
        queue.
        """
        a = {'queue_type': 'Execution', 'resources_min.ncpus': 1,
             'enabled': 'True', 'started': 'False'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='specialq')
        dflt_q = self.server.default_queue
        a = {'queue_type': 'route',
             'route_destinations': dflt_q + ',specialq',
             'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='routeq')
        a = {'resources_min.ncpus': 4}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id=dflt_q)
        j = Job(TEST_USER, attrs={ATTR_queue: 'routeq',
                                  'Resource_List.ncpus': 1})
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_queue: 'specialq'}, id=jid)

    def test_movejob(self):
        """
        Verify that a job can be moved to another queue than the one it was
        originally submitted to
        """
        a = {'queue_type': 'Execution', 'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='solverq')
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.movejob(jid, 'solverq')
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(JOB, {ATTR_queue: 'solverq', 'job_state': 'R'},
                           attrop=PTL_AND)

    @skipOnCpuSet
    def test_by_queue(self):
        """
        Test by_queue scheduling policy
        """
        a = OrderedDict()
        a['queue_type'] = 'execution'
        a['enabled'] = 'True'
        a['started'] = 'True'
        a['priority'] = 200
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='p1')
        a['priority'] = 400
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='p2')
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.set_sched_config({'by_queue': 'True'})
        a = {'resources_available.ncpus': 8}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'p1'}
        j = Job(TEST_USER, a)
        j1id = self.server.submit(j)
        a = {'Resource_List.select': '1:ncpus=8', ATTR_queue: 'p1'}
        j = Job(TEST_USER, a)
        j2id = self.server.submit(j)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'p1'}
        j = Job(TEST_USER, a)
        j3id = self.server.submit(j)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'p2'}
        j = Job(TEST_USER, a)
        j4id = self.server.submit(j)
        a = {'Resource_List.select': '1:ncpus=8', ATTR_queue: 'p2'}
        j = Job(TEST_USER, a)
        j5id = self.server.submit(j)
        a = {'Resource_List.select': '1:ncpus=8', ATTR_queue: 'p2'}
        j = Job(TEST_USER, a)
        j6id = self.server.submit(j)
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        # Given node configuration of 8 cpus the only jobs that could run are
        # j4id j1id and j3id
        self.server.expect(JOB, {'job_state=R': 3},
                           trigger_sched_cycle=False)
        cycle = self.scheduler.cycles(start=self.server.ctime, lastN=2)
        if len(cycle) > 0:
            i = len(cycle) - 1
            while len(cycle[i].political_order) == 0:
                i -= 1
            cycle = cycle[i]
            p1jobs = [j1id, j2id, j3id]
            p2jobs = [j4id, j5id, j6id]
            jobs = [j1id, j2id, j3id, j4id, j5id, j6id]
            job_order = map(lambda j: j.split('.')[0], p2jobs + p1jobs)
            self.logger.info(
                'Political order: ' + ','.join(cycle.political_order))
            self.logger.info('Expected order: ' + ','.join(job_order))
            self.assertTrue(cycle.political_order == job_order)

    @skipOnCpuSet
    def test_round_robin(self):
        """
        Test round_robin scheduling policy
        """
        a = OrderedDict()
        a['queue_type'] = 'execution'
        a['enabled'] = 'True'
        a['started'] = 'True'
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='p1')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='p2')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='p3')
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.set_sched_config({'round_robin': 'true   ALL'})
        a = {'resources_available.ncpus': 9}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        jids = []
        queues = ['p1', 'p2', 'p3']
        queue = queues[0]
        for i in range(9):
            if (i != 0) and (i % 3 == 0):
                del queues[0]
                queue = queues[0]
            a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: queue}
            j = Job(TEST_USER, a)
            jids.append(self.server.submit(j))
        start_time = int(time.time())
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(JOB, {'job_state=R': 9})
        cycle = self.scheduler.cycles(start=start_time, end=int(time.time()))
        if len(cycle) > 0:
            i = len(cycle) - 1
            while ((i >= 0) and (len(cycle[i].political_order) == 0)):
                i -= 1
            if i < 0:
                self.assertTrue(False, 'failed to found political order')
            cycle = cycle[i]
            jobs = [jids[0], jids[3], jids[6], jids[1], jids[4], jids[7],
                    jids[2], jids[5], jids[8]]
            job_order = map(lambda j: j.split('.')[0], jobs)
            self.logger.info(
                'Political order: ' + ','.join(cycle.political_order))
            self.logger.info('Expected order: ' + ','.join(job_order))
            self.assertTrue(cycle.political_order == job_order)

    def test_pbs_probe(self):
        """
        Verify that pbs_probe runs and returns 0 when no errors are detected
        """
        probe = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'sbin',
                             'pbs_probe')
        ret = self.du.run_cmd(self.server.hostname, [probe], sudo=True)
        self.assertEqual(ret['rc'], 0)

    def test_printjob(self):
        """
        Verify that printjob can be executed
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        a = {'job_state': 'R', 'substate': 42}
        self.server.expect(JOB, a, id=jid)
        printjob = os.path.join(self.mom.pbs_conf['PBS_EXEC'], 'bin',
                                'printjob')
        jbfile = os.path.join(self.mom.pbs_conf['PBS_HOME'], 'mom_priv',
                              'jobs', jid + '.JB')
        ret = self.du.run_cmd(self.mom.hostname, cmd=[printjob, jbfile],
                              sudo=True)
        self.assertEqual(ret['rc'], 0)

    def test_comm_service(self):
        """
        Examples to demonstrate how to start/stop/signal the pbs_comm service
        """
        comm = Comm()
        comm.isUp()
        comm.signal('-HUP')
        comm.stop()
        comm.start()
        comm.log_match('Thread')

    def test_add_server_dyn_res(self):
        """
        Examples to demonstrate how to add a server dynamic resource script
        """
        attr = {}
        attr['type'] = 'long'
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='foo')
        body = "echo 10"
        self.scheduler.add_server_dyn_res("foo", script_body=body)
        self.scheduler.add_resource("foo", apply=True)
        j1 = Job(TEST_USER)
        j1.set_attributes({'Resource_List': 'foo=15'})
        j1id = self.server.submit(j1)
        msg = "Can Never Run: Insufficient amount of server resource: foo "\
              "(R: 15 A: 10 T: 10)"
        a = {'job_state': 'Q', 'Resource_List.foo': '15',
             'comment': msg}
        self.server.expect(JOB, a, id=j1id)

    @skipOnCpuSet
    def test_schedlog_preempted_info(self):
        """
        Demonstrate how to retrieve a list of jobs that had to be preempted in
        order to run a high priority job
        """
        # run the preemption smoketest
        self.test_preemption()
        # Analyze the scheduler log
        a = PBSLogAnalyzer()
        a.analyze_scheduler_log(self.scheduler.logfile,
                                start=self.server.ctime)
        for cycle in a.scheduler.cycles:
            if cycle.preempted_jobs:
                self.logger.info('Preemption info: ' +
                                 str(cycle.preempted_jobs))

    @skipOnCpuSet
    def test_basic(self):
        """
        basic express queue preemption test
        """
        try:
            self.server.manager(MGR_CMD_DELETE, QUEUE, id="expressq")
        except PbsManagerError:
            pass
        a = {'queue_type': 'e',
             'started': 'True',
             'enabled': 'True',
             'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '2gb'}
        self.server.create_vnodes('vnode', a, 4, self.mom)
        j1 = Job(TEST_USER)
        j1.set_attributes(
            {'Resource_List.select': '4:ncpus=4',
             'Resource_List.walltime': 3600})
        j1id = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=j1id)
        j2 = Job(TEST_USER)
        j2.set_attributes(
            {'Resource_List.select': '1:ncpus=4',
             'Resource_List.walltime': 3600,
             'queue': 'expressq'})
        j2id = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'S'}, id=j1id)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.cleanup_jobs()
        self.server.expect(SERVER, {'total_jobs': 0})
        self.server.manager(MGR_CMD_DELETE, QUEUE, id="expressq")

    @skipOnCpuSet
    def test_basic_ja(self):
        """
        basic express queue preemption test with job array
        """
        try:
            self.server.manager(MGR_CMD_DELETE, QUEUE, id="expressq")
        except PbsManagerError:
            pass
        a = {'queue_type': 'e',
             'started': 'True',
             'enabled': 'True',
             'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '2gb'}
        self.server.create_vnodes('vnode', a, 4, self.mom)
        j1 = Job(TEST_USER)
        j1.set_attributes({'Resource_List.select': '4:ncpus=4',
                           'Resource_List.walltime': 3600})
        j1id = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=j1id)
        j2 = Job(TEST_USER)
        j2.set_attributes({'Resource_List.select': '1:ncpus=4',
                           'Resource_List.walltime': 3600,
                           'queue': 'expressq',
                           ATTR_J: '1-3'})
        j2id = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'S'}, id=j1id)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=j2id, extend='t')
        self.server.cleanup_jobs()
        self.server.expect(SERVER, {'total_jobs': 0})
        self.server.manager(MGR_CMD_DELETE, QUEUE, id="expressq")

    def submit_reserv(self, resv_start, ncpus, resv_dur):
        a = {'Resource_List.select': '1:ncpus=%d' % ncpus,
             'Resource_List.place': 'free',
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

    @skipOnCpuSet
    def test_shrink_to_fit_resv_barrier(self):
        """
        Test shrink to fit by creating one reservation having ncpus=1,
        starting in 3 hours with a duration of two hours.  A STF job with
        a min_walltime of 10 min. and max_walltime of 20.5 hrs will shrink
        its walltime to less than or equal to 3 hours and greater than or
        equal to 10 mins.
        """
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        now = time.time()
        resv_dur = 7200
        resv_start = now + 10800
        d = self.submit_reserv(resv_start, 1, resv_dur)
        self.assertTrue(d)
        j = Job(TEST_USER)
        a = {'Resource_List.ncpus': '1'}
        j.set_attributes(a)
        jid = self.server.submit(j)
        j2 = Job(TEST_USER)
        a = {'Resource_List.max_walltime': '20:30:00',
             'Resource_List.min_walltime': '00:10:00'}
        j2.set_attributes(a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        attr = {'Resource_List.walltime': (LE, '03:00:00')}
        self.server.expect(JOB, attr, id=jid2)
        attr = {'Resource_List.walltime': (GE, '00:10:00')}
        self.server.expect(JOB, attr, id=jid2)

    @skipOnCpuSet
    def test_job_sort_formula_threshold(self):
        """
        Test job_sort_formula_threshold basic behavior
        """
        self.scheduler.set_sched_config({'log_filter': '2048'})
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        a = {'job_sort_formula':
             'ceil(fabs(-ncpus*(mem/100.00)*sqrt(walltime)))'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'job_sort_formula_threshold': '7'}
        self.server.manager(MGR_CMD_SET, SCHED, a)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {'Resource_List.select': '1:ncpus=1:mem=300kb',
             'Resource_List.walltime': 4}
        J1 = Job(TEST_USER1, attrs=a)
        a = {'Resource_List.select': '1:ncpus=1:mem=350kb',
             'Resource_List.walltime': 4}
        J2 = Job(TEST_USER1, attrs=a)
        a = {'Resource_List.select': '1:ncpus=1:mem=380kb',
             'Resource_List.walltime': 4}
        J3 = Job(TEST_USER1, attrs=a)
        a = {'Resource_List.select': '1:ncpus=1:mem=440kb',
             'Resource_List.walltime': 4}
        J4 = Job(TEST_USER1, attrs=a)
        j1id = self.server.submit(J1)
        j2id = self.server.submit(J2)
        j3id = self.server.submit(J3)
        j4id = self.server.submit(J4)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        rv = self.server.expect(SERVER, {'server_state': 'Scheduling'}, op=NE)
        self.logger.info("Checking the job state of " + j4id)
        self.server.expect(JOB, {'job_state': 'R'}, id=j4id, max_attempts=30,
                           interval=2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j3id, max_attempts=30,
                           interval=2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j2id, max_attempts=30,
                           interval=2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j1id, max_attempts=30,
                           interval=2)
        msg = "Checking the job state of %s, runs after %s is deleted" % (j3id,
                                                                          j4id)
        self.logger.info(msg)
        self.server.deljob(id=j4id, wait=True)
        self.server.expect(JOB, {'job_state': 'R'}, id=j3id, max_attempts=30,
                           interval=2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j2id, max_attempts=30,
                           interval=2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j1id, max_attempts=30,
                           interval=2)
        self.scheduler.log_match(j1id + ";Formula Evaluation = 6",
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)
        m = ";Job's formula value 6 is under threshold 7"
        self.scheduler.log_match(j1id + m,
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)
        m = ";Job is under job_sort_formula threshold value"
        self.scheduler.log_match(j1id + m,
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)
        self.scheduler.log_match(j2id + ";Formula Evaluation = 7",
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)
        m = ";Job's formula value 7 is under threshold 7"
        self.scheduler.log_match(j2id + m,
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)
        m = ";Job is under job_sort_formula threshold value"
        self.scheduler.log_match(j1id + m,
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)
        self.scheduler.log_match(j3id + ";Formula Evaluation = 8",
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)
        self.scheduler.log_match(j4id + ";Formula Evaluation = 9",
                                 regexp=True, starttime=self.server.ctime,
                                 max_attempts=10, interval=2)

        # Make sure we can qrun a job under the threshold
        self.server.deljob(id=j3id, wait=True)
        rv = self.server.expect(SERVER, {'server_state': 'Scheduling'}, op=NE)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=j1id)
        self.server.runjob(jobid=j1id)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=j1id)

    def isSuspended(self, ppid):
        """
        Check wether <ppid> is in Suspended state, return True if
        <ppid> in Suspended state else return False
        """
        state = 'T'
        rv = self.pu.get_proc_state(self.mom.shortname, ppid)
        if rv != state:
            return False
        childlist = self.pu.get_proc_children(self.mom.shortname,
                                              ppid)
        for child in childlist:
            rv = self.pu.get_proc_state(self.mom.shortname, child)
            if rv != state:
                return False
        return True

    def do_preempt_config(self):
        """
        Do Scheduler Preemption configuration
        """
        _t = ('\"express_queue, normal_jobs, server_softlimits,' +
              ' queue_softlimits\"')
        a = {'preempt_prio': _t}
        self.scheduler.set_sched_config(a)
        try:
            self.server.manager(MGR_CMD_DELETE, QUEUE, None, 'expressq')
        except PbsManagerError:
            pass
        a = {'queue_type': 'e',
             'started': 'True',
             'Priority': 150,
             'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, 'expressq')

    def common_stuff(self, isJobArray=False, isWithPreempt=False):
        """
        Do common stuff for job like submitting, stating and suspending
        """
        if isJobArray:
            a = {'resources_available.ncpus': 3}
        else:
            a = {'resources_available.ncpus': 1}
        self.server.create_vnodes('vn', a, 1,
                                  mom=self.mom)
        if isWithPreempt:
            self.do_preempt_config()
        j1 = Job(TEST_USER, attrs={'Resource_List.walltime': 100})
        if isJobArray:
            j1.set_attributes({ATTR_J: '1-3'})
        j1id = self.server.submit(j1)
        if isJobArray:
            a = {'job_state=R': 3, 'substate=42': 3}
        else:
            a = {'job_state': 'R', 'substate': 42}
        self.server.expect(JOB, a, extend='t')
        if isWithPreempt:
            j2 = Job(TEST_USER, attrs={'Resource_List.walltime': 100,
                                       'queue': 'expressq'})
            if isJobArray:
                j2.set_attributes({ATTR_J: '1-3'})
            j2id = self.server.submit(j2)
            self.assertNotEqual(j2id, None)
            if isJobArray:
                a = {'job_state=R': 3, 'substate=42': 3}
            else:
                a = {'job_state': 'R', 'substate': 42}
            self.server.expect(JOB, a, id=j2id, extend='t')
        else:
            self.server.sigjob(j1id, 'suspend')
        if isJobArray:
            a = {'job_state=S': 3}
        else:
            a = {'job_state': 'S'}
        self.server.expect(JOB, a, id=j1id, extend='t')
        jobs = self.server.status(JOB, id=j1id)
        for job in jobs:
            if 'session_id' in job:
                self.server.expect(JOB, {'session_id': self.isSuspended},
                                   id=job['id'])
        if isWithPreempt:
            return (j1id, j2id)
        else:
            return j1id

    @skipOnCpuSet
    def test_suspend_job_with_preempt(self):
        """
        Test Suspend of Job using Scheduler Preemption
        """
        self.common_stuff(isWithPreempt=True)

    @skipOnCpuSet
    def test_resume_job_with_preempt(self):
        """
        Test Resume of Job using Scheduler Preemption
        """
        (j1id, j2id) = self.common_stuff(isWithPreempt=True)
        self.server.delete(j2id)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42},
                           id=j1id)
        jobs = self.server.status(JOB, id=j1id)
        for job in jobs:
            if 'session_id' in job:
                self.server.expect(JOB,
                                   {'session_id': (NOT, self.isSuspended)},
                                   id=job['id'])

    @skipOnCpuSet
    def test_suspend_job_array_with_preempt(self):
        """
        Test Suspend of Job array using Scheduler Preemption
        """
        self.common_stuff(isJobArray=True, isWithPreempt=True)

    @skipOnCpuSet
    def test_resume_job_array_with_preempt(self):
        """
        Test Resume of Job array using Scheduler Preemption
        """
        (j1id, j2id) = self.common_stuff(isJobArray=True, isWithPreempt=True)
        self.server.delete(j2id)
        self.server.expect(JOB,
                           {'job_state=R': 3, 'substate=42': 3},
                           extend='t')
        jobs = self.server.status(JOB, id=j1id, extend='t')
        for job in jobs:
            if 'session_id' in job:
                self.server.expect(JOB,
                                   {'session_id': (NOT, self.isSuspended)},
                                   id=job['id'])

    def create_resource_helper(self, r, t, f, c):
        """
        create a resource with associated type, flag, and control flag

        r - The resource name

        t - Type of the resource

        f - Permissions/flags associated to the resource

        c - Control flags

        This method handles expected errors for invalid settings
        """

        expect_error = self.expect_error(t, f)
        attr = {}
        if t is not None:
            attr['type'] = t
        if f is not None:
            attr['flag'] = f
        if c:
            if 'flag' in attr:
                attr['flag'] += c
            else:
                attr['flag'] = c
        if len(attr) == 0:
            attr = None
        try:
            rc = self.server.manager(MGR_CMD_CREATE, RSC, attr, id=r,
                                     logerr=False)
            msg = None
        except PbsManagerError as e:
            rc = e.rc
            msg = e.msg
        if expect_error:
            if msg:
                m = 'Expected error contains "Erroneous to have"'
                self.logger.info(m + ' in ' + msg[0])
                self.assertTrue('Erroneous to have' in msg[0])
            self.assertNotEqual(rc, 0)
            return False
        else:
            self.assertEqual(rc, 0)
            self.server.manager(MGR_CMD_LIST, RSC, id=r)
            rv = self.server.resources[r].attributes['type']
            if t is None:
                self.assertEqual(rv, 'string')
            else:
                self.assertEqual(rv, t)
            _f = ''
            if f is not None:
                _f = f
            if c is not None:
                _f += c
            if _f:
                rv = self.server.resources[r].attributes['flag']
                self.assertEqual(sorted(rv), sorted(_f))
        return True

    def expect_error(self, t, f):
        """
        Returns true for invalid combinations of flag and/or type
        """
        if (f in ['nh', 'f', 'fh', 'n', 'q'] and
                t in [None, 'string', 'string_array', 'boolean']):
            return True
        if (f == 'n' and t in [None, 'long', 'float', 'size']):
            return True
        if (f == 'f' and t in [None, 'long', 'float', 'size']):
            return True
        return False

    def test_resource_create(self):
        """
        Test behavior of resource creation by permuting over all possible and
        supported types and flags
        """
        rc = self.server.manager(MGR_CMD_CREATE, RSC, id=self.resc_name)
        self.assertEqual(rc, 0)
        rc = self.server.manager(MGR_CMD_LIST, RSC, id=self.resc_name)
        self.assertEqual(rc, 0)
        rsc = self.server.resources[self.resc_name]
        self.assertEqual(rsc.attributes['type'], 'string')
        self.logger.info(self.server.logprefix +
                         ' verify that default resource type is string...OK')
        self.logger.info(self.server.logprefix +
                         ' verify that duplicate resource creation fails')
        # check that duplicate is not allowed
        try:
            rc = self.server.manager(MGR_CMD_CREATE, RSC, None,
                                     id=self.resc_name,
                                     logerr=True)
        except PbsManagerError as e:
            rc = e.rc
            msg = e.msg
        self.assertNotEqual(rc, 0)
        self.assertTrue('Duplicate entry' in msg[0])
        self.logger.info('Expected error: Duplicate entry in ' + msg[0] +
                         ' ...OK')
        self.assertNotEqual(e.rc, 0)
        rc = self.server.manager(MGR_CMD_DELETE, RSC, id=self.resc_name)
        self.assertEqual(rc, 0)
        for t in self.resc_types:
            for f in self.resc_flags:
                for c in self.resc_flags_ctl:
                    rv = self.create_resource_helper(self.resc_name, t, f, c)
                    if rv:
                        rc = self.server.manager(MGR_CMD_DELETE, RSC,
                                                 id=self.resc_name)
                        self.assertEqual(rc, 0)
                    self.logger.info("")

    def delete_resource_helper(self, r, t, f, c, obj_type, obj_id):
        """
        Vierify behavior upon deleting a resource that is set on a PBS object.

        r - The resource to create and later on delete

        t - The type of resource

        f - The permissions/flags of the resource

        c - The control flags of the resource

        obj_type - The object type (server, queue, node, job, reservation) on
        which the resource is set.

        obj_id - The object identifier/name
        """
        ar = 'resources_available.' + r
        rv = self.create_resource_helper(self.resc_name, t, f, c)
        if rv:
            if t in ['long', 'float', 'size', 'boolean']:
                val = 0
            else:
                val = 'abc'
            if obj_type in [JOB, RESV]:
                if obj_type == JOB:
                    j = Job(TEST_USER1, {'Resource_List.' + r: val})
                else:
                    j = Reservation(TEST_USER1, {'Resource_List.' + r: val})
                try:
                    jid = self.server.submit(j)
                except PbsSubmitError as e:
                    jid = e.rv
                if c is not None and ('r' in c or 'i' in c):
                    self.assertEqual(jid, None)
                    self.logger.info('Verify that job/resv can not request '
                                     'invibile or read-only resource...OK')
                    self.server.manager(MGR_CMD_DELETE, RSC, id=r)
                    # done with the test case, just return
                    return
                if obj_type == RESV:
                    a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
                    self.server.expect(RESV, a, id=jid)
                self.assertNotEqual(jid, None)
            else:
                self.server.manager(MGR_CMD_SET, obj_type, {ar: val},
                                    id=obj_id)
            try:
                rc = self.server.manager(MGR_CMD_DELETE, RSC, id=r,
                                         logerr=False)
                msg = None
            except PbsManagerError as e:
                rc = e.rc
                msg = e.msg
            if obj_type in [JOB, RESV]:
                self.assertNotEqual(rc, 0)
                if msg:
                    m = "Resource busy on " + PBS_OBJ_MAP[obj_type]
                    self.logger.info('Expecting qmgr error: ' + m + ' in ' +
                                     msg[0])
                    self.assertTrue(m in msg[0])
                self.server.delete(jid)
                self.server.expect(obj_type, 'queue', op=UNSET)
                self.server.manager(MGR_CMD_DELETE, RSC, id=r)
            else:
                self.assertEqual(rc, 0)
                d = self.server.status(obj_type, ar, id=obj_id)
                if d and len(d) > 0:
                    self.assertFalse(ar in d[0])

    @timeout(720)
    def test_resource_delete(self):
        """
        Verify behavior of resource deletion when the resource is defined
        on a PBS object by varying over all permutations of types and flags
        """

        self.obj_map = {QUEUE: self.server.default_queue,
                        SERVER: self.server.name,
                        NODE: self.mom.shortname,
                        JOB: None, RESV: None}
        try:
            self.server.status(RSC, id=self.resc_name)
            self.server.manager(MGR_CMD_DELETE, RSC,
                                id=self.resc_name, logerr=False)
        except (PbsManagerError, PbsStatusError):
            pass
        for k in self.objs:
            if k not in self.obj_map:
                self.logger.error('can not map object ' + k)
                continue
            v = self.obj_map[k]
            for t in self.resc_types:
                for f in self.resc_flags:
                    for c in self.resc_flags_ctl:
                        self.delete_resource_helper(
                            self.resc_name, t, f, c, k, v)
                        self.logger.info("")

    def setup_fs(self, formula):

        # change resource group file and validate after all the changes are in
        self.scheduler.add_to_resource_group('grp1', 100, 'root', 60,
                                             validate=False)
        self.scheduler.add_to_resource_group('grp2', 200, 'root', 40,
                                             validate=False)
        self.scheduler.add_to_resource_group(TEST_USER1, 101, 'grp1', 40,
                                             validate=False)
        self.scheduler.add_to_resource_group(TEST_USER2, 102, 'grp1', 20,
                                             validate=False)
        self.scheduler.add_to_resource_group(TEST_USER3, 201, 'grp2', 30,
                                             validate=False)
        self.scheduler.add_to_resource_group(TEST_USER4, 202, 'grp2', 10,
                                             validate=True)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduler_iteration': 7})
        a = {'fair_share': 'True', 'fairshare_decay_time': '24:00:00',
             'fairshare_decay_factor': 0.5, 'fairshare_usage_res': formula,
             'log_filter': '0'}
        self.scheduler.set_sched_config(a)

    @skipOnCpuSet
    def test_fairshare_enhanced(self):
        """
        Test the basic fairshare behavior with custom resources for math module
        """
        rv = self.server.add_resource('foo1', 'float', 'nh')
        self.assertTrue(rv)
        # Set scheduler fairshare usage formula
        self.setup_fs('ceil(fabs(-ncpus*(foo1/100.00)*sqrt(100)))')
        node_attr = {'resources_available.ncpus': 1,
                     'resources_available.foo1': 5000}
        self.server.manager(MGR_CMD_SET, NODE, node_attr, self.mom.shortname)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job_attr = {'Resource_List.select': '1:ncpus=1:foo1=20'}
        J1 = Job(TEST_USER2, attrs=job_attr)
        J2 = Job(TEST_USER3, attrs=job_attr)
        J3 = Job(TEST_USER1, attrs=job_attr)
        j1id = self.server.submit(J1)
        j2id = self.server.submit(J2)
        j3id = self.server.submit(J3)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        rv = self.server.expect(SERVER, {'server_state': 'Scheduling'}, op=NE)

        self.logger.info("Checking the job state of " + j3id)
        self.server.expect(JOB, {'job_state': 'R'}, id=j3id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j2id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j1id)
        # While nothing has changed, we must run another cycle for the
        # scheduler to take note of the fairshare usage.
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.delete(j3id)
        msg = "Checking the job state of " + j2id + ", runs after "
        msg += j3id + " is deleted"
        self.logger.info(msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j1id)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.delete(j2id)
        msg = "Checking the job state of " + j1id + ", runs after "
        msg += j2id + " is deleted"
        self.logger.info(msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=j1id)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.delete(j1id)

        # query fairshare and check usage
        fs1 = self.scheduler.query_fairshare(name=str(TEST_USER1))
        self.logger.info('Checking ' + str(fs1.usage) + " == 3")
        self.assertEqual(fs1.usage, 3)
        fs2 = self.scheduler.query_fairshare(name=str(TEST_USER2))
        self.logger.info('Checking ' + str(fs2.usage) + " == 3")
        self.assertEqual(fs2.usage, 3)
        fs3 = self.scheduler.query_fairshare(name=str(TEST_USER3))
        self.logger.info('Checking ' + str(fs3.usage) + " == 3")
        self.assertEqual(fs3.usage, 3)
        fs4 = self.scheduler.query_fairshare(name=str(TEST_USER4))
        self.logger.info('Checking ' + str(fs4.usage) + " == 1")
        self.assertEqual(fs4.usage, 1)

        # Check the scheduler usage file whether it's updating or not
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        J1 = Job(TEST_USER4, attrs=job_attr)
        J2 = Job(TEST_USER2, attrs=job_attr)
        J3 = Job(TEST_USER1, attrs=job_attr)
        j1id = self.server.submit(J1)
        j2id = self.server.submit(J2)
        j3id = self.server.submit(J3)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.logger.info("Checking the job state of " + j1id)
        self.server.expect(JOB, {'job_state': 'R'}, id=j1id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j2id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j3id)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.delete(j1id)
        msg = "Checking the job state of " + j3id + ", runs after "
        msg += j1id + " is deleted"
        self.logger.info(msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=j3id)
        self.server.expect(JOB, {'job_state': 'Q'}, id=j2id)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.delete(j3id)
        msg = "Checking the job state of " + j2id + ", runs after "
        msg += j3id + " is deleted"
        self.logger.info(msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        # query fairshare and check usage
        fs1 = self.scheduler.query_fairshare(name=str(TEST_USER1))
        self.logger.info('Checking ' + str(fs1.usage) + " == 5")
        self.assertEqual(fs1.usage, 5)
        fs2 = self.scheduler.query_fairshare(name=str(TEST_USER2))
        self.logger.info('Checking ' + str(fs2.usage) + " == 5")
        self.assertEqual(fs2.usage, 5)
        fs3 = self.scheduler.query_fairshare(name=str(TEST_USER3))
        self.logger.info('Checking ' + str(fs3.usage) + " == 3")
        self.assertEqual(fs3.usage, 3)
        fs4 = self.scheduler.query_fairshare(name=str(TEST_USER4))
        self.logger.info('Checking ' + str(fs4.usage) + " == 3")
        self.assertEqual(fs4.usage, 3)

    @checkModule("pexpect")
    @skipOnShasta
    def test_interactive_job(self):
        """
        Submit an interactive job
        """
        cmd = 'sleep 10'
        j = Job(TEST_USER, attrs={ATTR_inter: ''})
        j.interactive_script = [('hostname', '.*'),
                                (cmd, '.*')]
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.delete(jid)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

    def test_man_pages(self):
        """
        Test basic functionality of man pages
        """
        pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        manpath = os.path.join(pbs_conf['PBS_EXEC'], "share", "man")
        pbs_cmnds = ["pbsnodes", "qsub"]
        os.environ['MANPATH'] = manpath
        for pbs_cmd in pbs_cmnds:
            cmd = "man %s" % pbs_cmd
            rc = self.du.run_cmd(cmd=cmd)
            msg = "Error while retrieving man page of %s" % pbs_cmd
            msg += "command: %s" % rc['err']
            self.assertEqual(rc['rc'], 0, msg)
            msg = "Successfully retrieved man page for"
            msg += " %s command" % pbs_cmd
            self.logger.info(msg)

    def test_exclhost(self):
        """
        Test that a job requesting exclhost is not placed on another host
        with a running job on it.
        """
        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vn', a, 8, sharednode=False,
                                  vnodes_per_host=4, mom=self.mom)

        J1 = Job(TEST_USER, {'Resource_List.select': '1:ncpus=1:vnode=vn[3]'})
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'exclhost'}
        J2 = Job(TEST_USER, a)
        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        st = self.server.status(JOB, 'exec_vnode', id=jid2)
        vnodes = J2.get_vnodes(st[0]['exec_vnode'])
        expected_vnodes = ['vn[4]', 'vn[5]', 'vn[6]', 'vn[7]']

        for v in vnodes:
            self.assertIn(v, expected_vnodes)

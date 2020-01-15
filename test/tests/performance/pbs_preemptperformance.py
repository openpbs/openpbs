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

from tests.performance import *
from ptl.utils.pbs_logutils import PBSLogUtils


class TestPreemptPerformance(TestPerformance):

    """
    Check the preemption performance
    """
    lu = PBSLogUtils()

    def setUp(self):
        TestPerformance.setUp(self)
        # set poll cycle to a high value because mom spends a lot of time
        # in gathering job's resources used. We don't need that in this test
        self.mom.add_config({'$min_check_poll': 7200, '$max_check_poll': 9600})

    def create_workload_and_preempt(self):
        a = {
            'queue_type': 'execution',
            'started': 'True',
            'enabled': 'True'
        }
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, 'workq2')

        a = {'max_run_res_soft.ncpus': "[u:PBS_GENERIC=2]"}
        self.server.manager(MGR_CMD_SET, QUEUE, a, 'workq')

        a = {'max_run_res.mem': "[u:" + str(TEST_USER) + "=1500mb]"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'Resource_List.select': '1:ncpus=3:mem=90mb',
             'Resource_List.walltime': 9999}
        for _ in range(8):
            j = Job(TEST_USER, attrs=a)
            j.set_sleep_time(9999)
            self.server.submit(j)

        for _ in range(7):
            j = Job(TEST_USER1, attrs=a)
            j.set_sleep_time(9999)
            self.server.submit(j)

        sched_off = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, sched_off)

        a = {'Resource_List.select': '1:ncpus=3',
             'Resource_List.walltime': 9999}
        for _ in range(775):
            j = Job(TEST_USER, attrs=a)
            j.set_sleep_time(9999)
            self.server.submit(j)

        for _ in range(800):
            j = Job(TEST_USER1, attrs=a)
            j.set_sleep_time(9999)
            self.server.submit(j)

        sched_on = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, sched_on)

        self.server.expect(JOB, {'job_state=R': 1590},
                           offset=15, interval=20)

        a = {'Resource_List.select': '1:ncpus=90:mem=1350mb',
             'Resource_List.walltime': 9999, ATTR_queue: 'workq2'}
        j1 = Job(TEST_USER, attrs=a)
        j1.set_sleep_time(9999)
        j1id = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, id=j1id,
                           offset=15, interval=5)
        self.server.expect(JOB, {'job_state=S': 20}, interval=5)

        (_, str1) = self.scheduler.log_match(j1id + ";Considering job to run",
                                             id=j1id, n='ALL',
                                             max_attempts=1, interval=2)
        (_, str2) = self.scheduler.log_match(j1id + ";Job run",
                                             id=j1id, n='ALL',
                                             max_attempts=1, interval=2)

        date_time1 = str1.split(";")[0]
        date_time2 = str2.split(";")[0]
        epoch1 = self.lu.convert_date_time(date_time1)
        epoch2 = self.lu.convert_date_time(date_time2)
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: THE TIME TAKEN IS : " + str(time_diff) + " SECONDS"
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)

    @timeout(3600)
    @tags('sched', 'scheduling_policy')
    def test_preemption_with_limits(self):
        """
        Measure the time scheduler takes to preempt when the high priority
        job hits soft/hard limits under a considerable amount of workload.
        """
        a = {'resources_available.ncpus': 4800,
             'resources_available.mem': '2800mb'}
        self.server.create_vnodes('vn', a, 1, self.mom, usenatvnode=True)
        p = '"express_queue, normal_jobs, server_softlimits, queue_softlimits"'
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_SET, SCHED, a, runas=ROOT_USER)

        self.create_workload_and_preempt()

    @timeout(3600)
    @tags('sched', 'scheduling_policy')
    def test_preemption_with_insufficient_resc(self):
        """
        Measure the time scheduler takes to preempt when the high priority
        job hits soft/hard limits and there is scarcity of resources
        under a considerable amount of workload.
        """
        a = {'resources_available.ncpus': 4800,
             'resources_available.mem': '1500mb'}
        self.server.create_vnodes('vn', a, 1, self.mom, usenatvnode=True)
        p = '"express_queue, normal_jobs, server_softlimits, queue_softlimits"'
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_SET, SCHED, a, runas=ROOT_USER)

        self.create_workload_and_preempt()

    @timeout(3600)
    @tags('sched', 'scheduling_policy')
    def test_insufficient_resc_non_cons(self):
        """
        Submit a number of low priority job and then submit a high priority
        job that needs a non-consumable resource which is assigned to last
        running job. This will make scheduler go through all running jobs
        to find the preemptable job.
        """

        a = {'type': 'string', 'flag': 'h'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='qlist')

        a = {ATTR_rescavail + ".qlist": "list1",
             ATTR_rescavail + ".ncpus": "8"}
        self.server.create_vnodes(
            "vn1", a, 400, self.mom, additive=True, fname="vnodedef1")

        a = {ATTR_rescavail + ".qlist": "list2",
             ATTR_rescavail + ".ncpus": "1"}
        self.server.create_vnodes(
            "vn2", a, 1, self.mom, additive=True, fname="vnodedef2")

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        a = {ATTR_l + '.select': '1:ncpus=1:qlist=list1'}
        for _ in range(3200):
            j = Job(TEST_USER, attrs=a)
            j.set_sleep_time(3000)
            self.server.submit(j)

        a = {ATTR_l + '.select': '1:ncpus=1:qlist=list2'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(3000)

        # Add qlist to the resources scheduler checks for
        self.scheduler.add_resource('qlist')
        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_sort',
                            runas=ROOT_USER)

        jid = self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state=R': 3201}, interval=20,
                           offset=15)

        qname = 'highp'
        a = {'queue_type': 'execution', 'priority': '200',
             'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)

        a = {ATTR_l + '.select': '1:ncpus=1:qlist=list2',
             ATTR_q: 'highp'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(3000)
        jid_highp = self.server.submit(j)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid_highp, interval=10)
        self.server.expect(JOB, {ATTR_state: (MATCH_RE, 'S|Q')}, id=jid)

        search_str = jid_highp + ";Considering job to run"
        (_, str1) = self.scheduler.log_match(search_str,
                                             id=jid_highp, n='ALL',
                                             max_attempts=1, interval=2)
        search_str = jid_highp + ";Job run"
        (_, str2) = self.scheduler.log_match(search_str,
                                             id=jid_highp, n='ALL',
                                             max_attempts=1, interval=2)
        date_time1 = str1.split(";")[0]
        date_time2 = str2.split(";")[0]
        epoch1 = self.lu.convert_date_time(date_time1)
        epoch2 = self.lu.convert_date_time(date_time2)
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: PREEMPTION TOOK: " + str(time_diff) + " SECONDS"
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        self.perf_test_result(time_diff,
                              "preempt_time_nonconsumable_resc", "sec")

    @timeout(3600)
    @tags('sched', 'scheduling_policy')
    def test_insufficient_resc_multiple_non_cons(self):
        """
        Submit a number of low priority jobs and then submit a high priority
        job that needs a non-consumable resource in 2 chunks. These resources
        are assigned to last two running jobs. This will make scheduler go
        through all running jobs to find preemptable jobs.
        """

        a = {'type': 'string', 'flag': 'h'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='qlist')

        a = {ATTR_rescavail + ".qlist": "list1",
             ATTR_rescavail + ".ncpus": "8"}
        self.server.create_vnodes(
            "vn1", a, 400, self.mom, additive=True, fname="vnodedef1")

        a = {ATTR_rescavail + ".qlist": "list2",
             ATTR_rescavail + ".ncpus": "1"}
        self.server.create_vnodes(
            "vn2", a, 1, self.mom, additive=True, fname="vnodedef2")

        a = {ATTR_rescavail + ".qlist": "list3",
             ATTR_rescavail + ".ncpus": "1"}
        self.server.create_vnodes(
            "vn3", a, 1, self.mom, additive=True, fname="vnodedef3")

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        a = {ATTR_l + '.select': '1:ncpus=1:qlist=list1'}
        for _ in range(3200):
            j = Job(TEST_USER, attrs=a)
            j.set_sleep_time(3000)
            self.server.submit(j)

        a = {ATTR_l + '.select': '1:ncpus=1:qlist=list2'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(3000)

        b = {ATTR_l + '.select': '1:ncpus=1:qlist=list3'}
        j2 = Job(TEST_USER, attrs=b)
        j2.set_sleep_time(3000)

        # Add qlist to the resources scheduler checks for
        self.scheduler.add_resource('qlist')
        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_sort',
                            runas=ROOT_USER)

        jid = self.server.submit(j)
        jid2 = self.server.submit(j2)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state=R': 3202}, interval=20,
                           offset=15)

        qname = 'highp'
        a = {'queue_type': 'execution', 'priority': '200',
             'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)

        a = {ATTR_l + '.select': '1:ncpus=1:qlist=list2+1:ncpus=1:qlist=list3',
             ATTR_q: 'highp'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(3000)
        jid_highp = self.server.submit(j)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid_highp, interval=10)
        self.server.expect(JOB, {ATTR_state: (MATCH_RE, 'S|Q')}, id=jid)
        self.server.expect(JOB, {ATTR_state: (MATCH_RE, 'S|Q')}, id=jid2)

        search_str = jid_highp + ";Considering job to run"
        (_, str1) = self.scheduler.log_match(search_str,
                                             id=jid_highp, n='ALL',
                                             max_attempts=1, interval=2)
        search_str = jid_highp + ";Job run"
        (_, str2) = self.scheduler.log_match(search_str,
                                             id=jid_highp, n='ALL',
                                             max_attempts=1, interval=2)
        date_time1 = str1.split(";")[0]
        date_time2 = str2.split(";")[0]
        epoch1 = self.lu.convert_date_time(date_time1)
        epoch2 = self.lu.convert_date_time(date_time2)
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: PREEMPTION TOOK: " + str(time_diff) + " SECONDS"
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        self.perf_test_result(time_diff,
                              "preempt_time_multiplenonconsumable_resc",
                              "sec")

    @timeout(3600)
    @tags('sched', 'scheduling_policy')
    def test_insufficient_server_resc(self):
        """
        Submit a number of low priority jobs and then make the last low
        priority job to consume some server level resources. Submit a
        high priority job that request for this server level resource
        and measure the time it takes for preemption.
        """

        a = {'type': 'long', 'flag': 'q'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='foo')

        a = {ATTR_rescavail + ".ncpus": "8"}
        self.server.create_vnodes(
            "vn1", a, 401, self.mom, additive=True, fname="vnodedef1")

        # Make resource foo available on server
        a = {ATTR_rescavail + ".foo": 50, 'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {ATTR_l + '.select': '1:ncpus=1'}
        for _ in range(3200):
            j = Job(TEST_USER, attrs=a)
            j.set_sleep_time(3000)
            self.server.submit(j)

        # Add foo to the resources scheduler checks for
        self.scheduler.add_resource('foo')
        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_sort',
                            runas=ROOT_USER)

        a = {ATTR_l + '.select': '1:ncpus=1', ATTR_l + '.foo': 25}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(3000)
        jid = self.server.submit(j)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state=R': 3201}, interval=20,
                           offset=15)

        qname = 'highp'
        a = {'queue_type': 'execution', 'priority': '200',
             'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)

        a = {ATTR_l + '.select': '1:ncpus=1', ATTR_l + '.foo': 50,
             ATTR_q: 'highp'}
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(3000)
        jid_highp = self.server.submit(j2)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid_highp, interval=10)
        self.server.expect(JOB, {ATTR_state: (MATCH_RE, 'S|Q')}, id=jid)

        search_str = jid_highp + ";Considering job to run"
        (_, str1) = self.scheduler.log_match(search_str,
                                             id=jid_highp, n='ALL',
                                             max_attempts=1, interval=2)
        search_str = jid_highp + ";Job run"
        (_, str2) = self.scheduler.log_match(search_str,
                                             id=jid_highp, n='ALL',
                                             max_attempts=1, interval=2)
        date_time1 = str1.split(";")[0]
        date_time2 = str2.split(";")[0]
        epoch1 = self.lu.convert_date_time(date_time1)
        epoch2 = self.lu.convert_date_time(date_time2)
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: PREEMPTION TOOK: " + str(time_diff) + " SECONDS"
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        self.perf_test_result(time_diff, "High_priority_preemption", "sec")

    @timeout(7200)
    def test_preemption_basic(self):
        """
        Submit a number of low priority job and then submit a high priority
        job.
        """

        a = {ATTR_rescavail + ".ncpus": "8"}
        self.server.create_vnodes(
            "vn1", a, 400, self.mom, additive=True, fname="vnodedef1")

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        a = {ATTR_l + '.select': '1:ncpus=1'}
        for _ in range(3200):
            j = Job(TEST_USER, attrs=a)
            j.set_sleep_time(3000)
            self.server.submit(j)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state=R': 3200}, interval=20,
                           offset=15)

        qname = 'highp'
        a = {'queue_type': 'execution', 'priority': '200',
             'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)

        ncpus = 20
        S_jobs = 20
        for _ in range(5):
            a = {ATTR_l + '.select': ncpus,
                 ATTR_q: 'highp'}
            j = Job(TEST_USER, attrs=a)
            j.set_sleep_time(3000)
            jid_highp = self.server.submit(j)

            self.server.expect(JOB, {ATTR_state: 'R'}, id=jid_highp,
                               interval=10)
            self.server.expect(JOB, {'job_state=S': S_jobs}, interval=5)
            search_str = jid_highp + ";Considering job to run"
            (_, str1) = self.scheduler.log_match(search_str,
                                                 id=jid_highp, n='ALL',
                                                 max_attempts=1)
            search_str = jid_highp + ";Job run"
            (_, str2) = self.scheduler.log_match(search_str,
                                                 id=jid_highp, n='ALL',
                                                 max_attempts=1)
            date_time1 = str1.split(";")[0]
            date_time2 = str2.split(";")[0]
            epoch1 = self.lu.convert_date_time(date_time1)
            epoch2 = self.lu.convert_date_time(date_time2)
            time_diff = epoch2 - epoch1
            self.logger.info('#' * 80)
            self.logger.info('#' * 80)
            res_str = "RESULT: PREEMPTION OF " + str(ncpus) + " JOBS TOOK: " \
                + str(time_diff) + " SECONDS"
            self.logger.info(res_str)
            self.logger.info('#' * 80)
            self.logger.info('#' * 80)
            ncpus *= 3
            S_jobs += ncpus
            self.perf_test_result(time_diff, "preemption_time", "sec")

    @timeout(3600)
    def test_preemption_with_unrelated_soft_limits(self):
        """
        Measure the time scheduler takes to preempt when there are user
        soft limits in the system and preemptor and preemptee jobs are
        submitted as different user.
        """
        a = {'resources_available.ncpus': 4,
             'resources_available.mem': '6400mb'}
        self.server.create_vnodes('vn', a, 500, self.mom, usenatvnode=False,
                                  sharednode=False)
        p = "express_queue, normal_jobs, server_softlimits, queue_softlimits"
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        a = {'max_run_res_soft.ncpus': "[u:" + str(TEST_USER) + "=1]"}
        self.server.manager(MGR_CMD_SET, QUEUE, a, 'workq')
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # submit a bunch of jobs as TEST_USER2
        a = {ATTR_l + '.select=1:ncpus': 1}
        for _ in range(2000):
            j = Job(TEST_USER2, attrs=a)
            j.set_sleep_time(3000)
            self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state=R': 2000}, interval=10, offset=5,
                           max_attempts=100)

        qname = 'highp'
        a = {'queue_type': 'execution', 'priority': '200',
             'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {ATTR_l + '.select=2000:ncpus': 1, ATTR_q: qname}
        j = Job(TEST_USER3, attrs=a)
        j.set_sleep_time(3000)
        hjid = self.server.submit(j)
        scycle = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        (_, str1) = self.scheduler.log_match(hjid + ";Considering job to run")

        date_time1 = str1.split(";")[0]
        epoch1 = self.lu.convert_date_time(date_time1)
        # make sure 2000 jobs were suspended
        self.server.expect(JOB, {'job_state=S': 2000}, interval=10, offset=5,
                           max_attempts=100)

        # check when server received the request
        (_, req_svr) = self.server.log_match(";Type 93 request received",
                                             starttime=epoch1)
        date_time_svr = req_svr.split(";")[0]
        epoch_svr = self.lu.convert_date_time(date_time_svr)
        # check when scheduler gets first reply from server
        (_, resp_sched) = self.scheduler.log_match(";Job preempted ",
                                                   starttime=epoch1)
        date_time_sched = resp_sched.split(";")[0]
        epoch_sched = self.lu.convert_date_time(date_time_sched)
        svr_delay = epoch_sched - epoch_svr

        # record the start time of high priority job
        (_, str2) = self.scheduler.log_match(hjid + ";Job run",
                                             n='ALL', interval=2)
        date_time2 = str2.split(";")[0]
        epoch2 = self.lu.convert_date_time(date_time2)
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: TOTAL PREEMPTION TIME: " + \
                  str(time_diff) + " SECONDS, SERVER TOOK: " + \
                  str(svr_delay) + " , SCHED TOOK: " + \
                  str(time_diff - svr_delay)
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)

    @timeout(3600)
    def test_preemption_with_user_soft_limits(self):
        """
        Measure the time scheduler takes to preempt when there are user
        soft limits in the system for one user and only some preemptee jobs
        are submitted as that user.
        """
        a = {'resources_available.ncpus': 4,
             'resources_available.mem': '6400mb'}
        self.server.create_vnodes('vn', a, 500, self.mom, usenatvnode=False,
                                  sharednode=False)
        p = "express_queue, normal_jobs, server_softlimits, queue_softlimits"
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        a = {'max_run_res_soft.ncpus': "[u:" + str(TEST_USER)+"=1]"}
        self.server.manager(MGR_CMD_SET, QUEUE, a, 'workq')
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # submit a bunch of jobs as different users
        a = {ATTR_l + '.select=1:ncpus': 1}
        usr_list = [TEST_USER, TEST_USER2, TEST_USER3, TEST_USER4]
        num_usr = len(usr_list)
        for ind in range(2000):
            j = Job(usr_list[ind % num_usr], attrs=a)
            j.set_sleep_time(3000)
            self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state=R': 2000}, interval=10, offset=5,
                           max_attempts=100)

        qname = 'highp'
        a = {'queue_type': 'execution', 'priority': '200',
             'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {ATTR_l + '.select=2000:ncpus': 1, ATTR_q: qname}
        j = Job(TEST_USER5, attrs=a)
        j.set_sleep_time(3000)
        hjid = self.server.submit(j)
        scycle = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        (_, str1) = self.scheduler.log_match(hjid + ";Considering job to run")

        date_time1 = str1.split(";")[0]
        epoch1 = self.lu.convert_date_time(date_time1)
        # make sure 2000 jobs were suspended
        self.server.expect(JOB, {'job_state=S': 2000}, interval=10, offset=5,
                           max_attempts=100)

        # check when server received the request
        (_, req_svr) = self.server.log_match(";Type 93 request received",
                                             starttime=epoch1)
        date_time_svr = req_svr.split(";")[0]
        epoch_svr = self.lu.convert_date_time(date_time_svr)
        # check when scheduler gets first reply from server
        (_, resp_sched) = self.scheduler.log_match(";Job preempted ",
                                                   starttime=epoch1)
        date_time_sched = resp_sched.split(";")[0]
        epoch_sched = self.lu.convert_date_time(date_time_sched)
        svr_delay = epoch_sched - epoch_svr

        # record the start time of high priority job
        (_, str2) = self.scheduler.log_match(hjid + ";Job run",
                                             n='ALL', interval=2)
        date_time2 = str2.split(";")[0]
        epoch2 = self.lu.convert_date_time(date_time2)
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: TOTAL PREEMPTION TIME: " + \
                  str(time_diff) + " SECONDS, SERVER TOOK: " + \
                  str(svr_delay) + " , SCHED TOOK: " + \
                  str(time_diff - svr_delay)
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        self.perf_test_result(time_diff, "preempt_time_soft_limits", "sec")

    def tearDown(self):
        TestPerformance.tearDown(self)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job_ids = self.server.select()
        self.server.delete(id=job_ids)

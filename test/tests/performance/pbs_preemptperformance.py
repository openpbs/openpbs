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

from tests.performance import *


class TestPreemptPerformance(TestPerformance):

    """
    Check the preemption performance
    """
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
        self.server.manager(MGR_CMD_SET, QUEUE, a, 'workq', expect=True)

        a = {'max_run_res.mem': "[u:" + str(TEST_USER) + "=1500mb]"}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)

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
        self.server.manager(MGR_CMD_SET, SERVER, sched_off, expect=True)

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
        self.server.manager(MGR_CMD_SET, SERVER, sched_on, expect=True)

        self.server.expect(JOB, {'substate=42': 1590},
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
        epoch1 = int(time.mktime(time.strptime(
            date_time1, '%m/%d/%Y %H:%M:%S')))
        epoch2 = int(time.mktime(time.strptime(
            date_time2, '%m/%d/%Y %H:%M:%S')))
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
        self.scheduler.set_sched_config({'preempt_prio': p})
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
        self.scheduler.set_sched_config({'preempt_prio': p})
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
        self.scheduler.unset_sched_config('preempt_sort')

        jid = self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'substate=42': 3201}, interval=20,
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
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
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
        epoch1 = int(time.mktime(time.strptime(
            date_time1, '%m/%d/%Y %H:%M:%S')))
        epoch2 = int(time.mktime(time.strptime(
            date_time2, '%m/%d/%Y %H:%M:%S')))
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: PREEMPTION TOOK: " + str(time_diff) + " SECONDS"
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)

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
        self.scheduler.unset_sched_config('preempt_sort')

        jid = self.server.submit(j)
        jid2 = self.server.submit(j2)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'substate=42': 3202}, interval=20,
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
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid2)
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
        epoch1 = int(time.mktime(time.strptime(
            date_time1, '%m/%d/%Y %H:%M:%S')))
        epoch2 = int(time.mktime(time.strptime(
            date_time2, '%m/%d/%Y %H:%M:%S')))
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: PREEMPTION TOOK: " + str(time_diff) + " SECONDS"
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)

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
        self.scheduler.unset_sched_config('preempt_sort')

        a = {ATTR_l + '.select': '1:ncpus=1', ATTR_l + '.foo': 25}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(3000)
        jid = self.server.submit(j)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'substate=42': 3201}, interval=20,
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
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
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
        epoch1 = int(time.mktime(time.strptime(
            date_time1, '%m/%d/%Y %H:%M:%S')))
        epoch2 = int(time.mktime(time.strptime(
            date_time2, '%m/%d/%Y %H:%M:%S')))
        time_diff = epoch2 - epoch1
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)
        res_str = "RESULT: PREEMPTION TOOK: " + str(time_diff) + " SECONDS"
        self.logger.info(res_str)
        self.logger.info('#' * 80)
        self.logger.info('#' * 80)

    def tearDown(self):
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        job_ids = self.server.select()
        self.server.delete(id=job_ids)

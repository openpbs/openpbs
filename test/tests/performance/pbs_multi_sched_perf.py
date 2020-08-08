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


class TestMultipleSchedulersPerf(TestPerformance):

    """
    Test suite to test performance of multiple schedulers
    """

    def setup_scheds(self):
        for i in range(1, 6):
            partition = 'P' + str(i)
            sched_port = 15049 + i
            sched_name = 'sc' + str(i)
            a = {'partition': partition,
                 'sched_host': self.server.hostname,
                 'sched_port': sched_port}
            self.server.manager(MGR_CMD_CREATE, SCHED,
                                a, id=sched_name)
            self.scheds[sched_name].create_scheduler()
            self.scheds[sched_name].start()
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'True'}, id=sched_name)

    def setup_queues_nodes(self):
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq2')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq3')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq4')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq5')
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq1')
        p2 = {'partition': 'P2'}
        self.server.manager(MGR_CMD_SET, QUEUE, p2, id='wq2')
        p3 = {'partition': 'P3'}
        self.server.manager(MGR_CMD_SET, QUEUE, p3, id='wq3')
        p4 = {'partition': 'P4'}
        self.server.manager(MGR_CMD_SET, QUEUE, p4, id='wq4')
        p5 = {'partition': 'P5'}
        self.server.manager(MGR_CMD_SET, QUEUE, p5, id='wq5')
        node = str(self.mom.shortname)
        self.server.manager(MGR_CMD_SET, NODE, p1, id=node + '[0]')
        self.server.manager(MGR_CMD_SET, NODE, p2, id=node + '[1]')
        self.server.manager(MGR_CMD_SET, NODE, p3, id=node + '[2]')
        self.server.manager(MGR_CMD_SET, NODE, p4, id=node + '[3]')
        self.server.manager(MGR_CMD_SET, NODE, p5, id=node + '[4]')

    def submit_jobs(self, num_jobs=1, attrs=None, user=TEST_USER):
        """
        Submit num_jobs number of jobs with attrs attributes for user.
        Return a list of job ids
        """
        if attrs is None:
            attrs = {ATTR_q: 'workq'}
        ret_jids = []
        for _ in range(num_jobs):
            J = Job(user, attrs)
            jid = self.server.submit(J)
            ret_jids += [jid]

        return ret_jids

    @timeout(3600)
    def test_multi_sched_perf(self):
        """
        Test time taken to schedule and run 5k jobs with
        single scheduler and workload divided among 5 schedulers.
        """
        a = {'resources_available.ncpus': 1000}
        self.server.create_vnodes(self.mom.shortname, a, 5, self.mom)
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.submit_jobs(5000)
        start = time.time()
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(SCHED, {'state': 'scheduling'},
                           id='default', max_attempts=10)
        self.scheduler.log_match(
            "Starting Scheduling Cycle", starttime=int(start),
            max_attempts=30)
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.log_match("Leaving Scheduling Cycle",
                                 starttime=int(start) + 1,
                                 max_attempts=30, interval=1)
        sclg = PBSLogAnalyzer()
        md = sclg.analyze_scheduler_log(
            filename=self.scheduler.logfile, start=int(start))
        dur = md['summary']['duration']
        dur = float(dur.split(':')[2])
        self.perf_test_result(dur, "single_sched_cycle_duration", "secs")
        self.server.cleanup_jobs()
        self.setup_scheds()
        self.setup_queues_nodes()
        for sc in self.scheds:
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SCHED, a, id=sc)
        a = {ATTR_q: 'wq1'}
        self.submit_jobs(1000, a)
        a = {ATTR_q: 'wq2'}
        self.submit_jobs(1000, a)
        a = {ATTR_q: 'wq3'}
        self.submit_jobs(1000, a)
        a = {ATTR_q: 'wq4'}
        self.submit_jobs(1000, a)
        a = {ATTR_q: 'wq5'}
        self.submit_jobs(1000, a)
        start = time.time()
        for sc in self.scheds:
            a = {'scheduling': 'True'}
            self.server.manager(MGR_CMD_SET, SCHED, a, id=sc)
        for sc in self.scheds:
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SCHED, a, id=sc)
        for sc in self.scheds:
            self.scheds[sc].log_match("Leaving Scheduling Cycle",
                                      starttime=int(start),
                                      max_attempts=30, interval=1)
        for sc in self.scheds:
            if sc != 'default':
                sclg = PBSLogAnalyzer()
                filename = self.scheds[sc].attributes['sched_log']
                md = sclg.analyze_scheduler_log(
                    filename=filename, start=int(start))
                dur = md['summary']['duration']
                dur = float(dur.split(':')[2])
                self.perf_test_result(dur, sc + "_cycle_duration", "secs")

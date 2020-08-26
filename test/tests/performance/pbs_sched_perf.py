# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


from ptl.utils.pbs_logutils import PBSLogUtils
from tests.performance import *


class TestSchedPerf(TestPerformance):
    """
    Test the performance of scheduler features
    """

    def common_setup1(self):
        TestPerformance.setUp(self)
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string', 'flag': 'h'}, id='color')
        self.colors = \
            ['red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet']
        a = {'resources_available.ncpus': 1, 'resources_available.mem': '8gb'}
        # 10010 nodes since it divides into 7 evenly.
        # Each node bucket will have 1430 nodes in it
        self.server.create_vnodes('vnode', a, 10010, self.mom,
                                  sharednode=False,
                                  attrfunc=self.cust_attr_func, expect=False)
        self.server.expect(NODE, {'state=free': (GE, 10010)})
        self.scheduler.add_resource('color')

    def cust_attr_func(self, name, totalnodes, numnode, attribs):
        """
        Add custom resources to nodes
        """
        a = {'resources_available.color': self.colors[numnode % 7]}
        return {**attribs, **a}

    def submit_jobs(self, attribs, num, step=1, wt_start=100):
        """
        Submit num jobs each in their individual equiv class
        """
        jids = []

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        for i in range(num):
            job_wt = wt_start + (i * step)
            attribs['Resource_List.walltime'] = job_wt
            J = Job(TEST_USER, attrs=attribs)
            J.set_sleep_time(job_wt)
            jid = self.server.submit(J)
            jids.append(jid)

        return jids

    def run_cycle(self):
        """
        Run a cycle and return the length of the cycle
        """
        self.server.expect(SERVER, {'server_state': 'Scheduling'}, op=NE)
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.expect(SERVER, {'server_state': 'Scheduling'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # 600 * 2sec = 20m which is the max cycle length
        self.server.expect(SERVER, {'server_state': 'Scheduling'}, op=NE,
                           max_attempts=600, interval=2)
        c = self.scheduler.cycles(lastN=1)[0]
        return c.end - c.start

    def compare_normal_path_to_buckets(self, place, num_jobs):
        """
        Submit num_jobs jobs and run two cycles.  First one with the normal
        node search code path and the second with buckets.  Print the
        time difference between the two cycles.
        """
        # Submit one job to eat up the resources.  We want to compare the
        # time it takes for the scheduler to attempt and fail to run the jobs
        a = {'Resource_List.select': '1429:ncpus=1:color=yellow',
             'Resource_List.place': place,
             'Resource_List.walltime': '1:00:00'}
        Jyellow = Job(TEST_USER, attrs=a)
        Jyellow.set_sleep_time(3600)
        jid_yellow = self.server.submit(Jyellow)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid_yellow)

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # Shared jobs use standard code path
        a = {'Resource_List.select':
             '1429:ncpus=1:color=blue+1429:ncpus=1:color=yellow',
             "Resource_List.place": place}
        jids = self.submit_jobs(a, num_jobs)

        cycle1_time = self.run_cycle()

        # Excl jobs use bucket codepath
        a = {'Resource_List.place': place + ':excl'}
        for jid in jids:
            self.server.alterjob(jid, a)

        cycle2_time = self.run_cycle()

        log_msg = 'Cycle 1: %.2f Cycle 2: %.2f Cycle time difference: %.2f'
        self.logger.info(log_msg % (cycle1_time, cycle2_time,
                                    cycle1_time - cycle2_time))
        self.assertGreater(cycle1_time, cycle2_time)

    @timeout(10000)
    def test_node_bucket_perf_scatter(self):
        """
        Submit a large number of jobs which use node buckets.  Run a cycle and
        compare that to a cycle that doesn't use node buckets.  Jobs require
        place=excl to use node buckets.
        This test uses place=scatter.  Scatter placement is quicker than free
        """
        self.common_setup1()
        num_jobs = 3000
        self.compare_normal_path_to_buckets('scatter', num_jobs)

    @timeout(10000)
    def test_node_bucket_perf_free(self):
        """
        Submit a large number of jobs which use node buckets.  Run a cycle and
        compare that to a cycle that doesn't use node buckets.  Jobs require
        place=excl to use node buckets.
        This test uses free placement.  Free placement is slower than scatter
        """
        self.common_setup1()
        num_jobs = 3000
        self.compare_normal_path_to_buckets('free', num_jobs)

    @timeout(3600)
    def test_run_many_normal_jobs(self):
        """
        Submit many normal path jobs and time the cycle that runs all of them.
        """
        self.common_setup1()
        num_jobs = 10000
        a = {'Resource_List.select': '1:ncpus=1'}
        jids = self.submit_jobs(a, num_jobs, wt_start=num_jobs)
        t = self.run_cycle()
        self.server.expect(JOB, {'job_state=R': num_jobs},
                           trigger_sched_cycle=False, interval=5,
                           max_attempts=240)
        self.logger.info('#' * 80)
        m = 'Time taken in cycle to run %d normal jobs: %.2f' % (num_jobs, t)
        self.logger.info(m)
        self.logger.info('#' * 80)

    @timeout(3600)
    def test_run_many_bucket_jobs(self):
        """
        Submit many bucket path jobs and time the cycle that runs all of them.
        """
        self.common_setup1()
        num_jobs = 10000
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl'}
        self.submit_jobs(a, num_jobs, wt_start=num_jobs)
        t = self.run_cycle()

        self.server.expect(JOB, {'job_state=R': num_jobs},
                           trigger_sched_cycle=False, interval=5,
                           max_attempts=240)
        self.logger.info('#' * 80)
        m = 'Time taken in cycle to run %d bucket jobs: %.2f' % (num_jobs, t)
        self.logger.info(m)
        self.logger.info('#' * 80)
        self.perf_test_result(t, m, "seconds")

    @timeout(3600)
    def test_pset_fuzzy_perf(self):
        """
        Test opt_backfill_fuzzy with placement sets.
        """
        self.common_setup1()
        a = {'strict_ordering': 'True'}
        self.scheduler.set_sched_config(a)

        a = {'node_group_key': 'color', 'node_group_enable': 'True',
             'scheduling': 'False'}

        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(SERVER, {'server_state': (NE, 'Scheduling')})

        a = {'Resource_List.select': '1:ncpus=1:color=yellow'}
        self.submit_jobs(attribs=a, num=1430, step=60, wt_start=3600)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        self.server.expect(JOB, {'job_state=R': 1430},
                           trigger_sched_cycle=False, interval=5,
                           max_attempts=240)

        a = {'Resource_List.select': '10000:ncpus=1'}
        tj = Job(TEST_USER, attrs=a)
        self.server.submit(tj)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        cycle1 = self.scheduler.cycles(lastN=1)[0]
        cycle1_time = cycle1.end - cycle1.start

        a = {'opt_backfill_fuzzy': 'High'}
        self.server.manager(MGR_CMD_SET, SCHED, a, id='default')

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        cycle2 = self.scheduler.cycles(lastN=1)[0]
        cycle2_time = cycle2.end - cycle2.start

        self.logger.info('Cycle 1: %f Cycle 2: %f Perc %.2f%%' % (
            cycle1_time, cycle2_time, (cycle1_time / cycle2_time) * 100))
        self.assertLess(cycle2_time, cycle1_time,
                        'Optimization was not faster')
        self.perf_test_result(((cycle1_time / cycle2_time) * 100),
                              "optimized_percentage", "percentage")

    @timeout(1200)
    def test_many_chunks(self):
        self.common_setup1()
        num_jobs = 1000
        num_cycles = 3
        # Submit jobs with a large number of chunks that can't run
        a = {'Resource_List.select': '9999:ncpus=1:color=red'}
        jids = self.submit_jobs(a, num_jobs, wt_start=1000)
        m = 'Time taken to consider %d normal jobs' % num_jobs
        times = []
        for i in range(num_cycles):
            t = self.run_cycle()
            times.append(t)

        self.logger.info('#' * 80)
        for i in range(num_cycles):
            m2 = '[%d] %s: %.2f' % (i, m, times[i])
            self.logger.info(m2)
        self.logger.info('#' * 80)

        self.perf_test_result(times, m, "sec")

    @timeout(10000)
    def test_many_jobs_with_calendaring(self):
        """
        Performance test for when there are many jobs and calendaring is on
        """
        self.common_setup1()
        # Turn strict ordering on and backfill_depth=20
        a = {'strict_ordering': 'True'}
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'backfill_depth': '20'})

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})
        jids = []

        # Submit around 10k jobs
        chunk_size = 100
        total_jobs = 10000
        while total_jobs > 0:
            for i in range(1, chunk_size + 1):
                a = {'Resource_List.select':
                     str(i) + ":ncpus=1:color=" + self.colors[i % 7]}
                njobs = int(chunk_size / i)
                _jids = self.submit_jobs(a, njobs, wt_start=1000)
                jids.extend(_jids)
                total_jobs -= njobs
                if total_jobs <= 0:
                    break

        t1 = time.time()
        for _ in range(100):
            self.scheduler.run_scheduling_cycle()
        t2 = time.time()

        self.logger.info("Time taken by 100 sched cycles: " + str(t2 - t1))

        # Delete all jobs
        self.server.cleanup_jobs()

    @timeout(5000)
    def test_attr_update_period_perf(self):
        """
        Test the performance boost gained by using attr_update_period
        """
        # Create 1 node with 1 cpu
        a = {"resources_available.ncpus": 1}
        self.server.create_vnodes('vnode', a, 1, self.mom, sharednode=False)

        a = {"attr_update_period": 10000, "scheduling": "False"}
        self.server.manager(MGR_CMD_SET, SCHED, a, id="default")

        # Submit 5k jobs
        for _ in range(5000):
            self.server.submit(Job())

        # The first scheduling cycle will send attribute updates
        self.scheduler.run_scheduling_cycle()
        cycle1 = self.scheduler.cycles(lastN=1)[0]
        cycle1_time = cycle1.end - cycle1.start

        # Delete all jobs, submit 5k jobs again
        self.server.cleanup_jobs()
        for _ in range(5000):
            self.server.submit(Job())

        # This is the second scheduling cycle. We gave a very long
        # attr_update_period value, so we should still be within that period
        # So, sched should NOT send updates this time
        self.scheduler.run_scheduling_cycle()
        cycle2 = self.scheduler.cycles(lastN=1)[0]
        cycle2_time = cycle2.end - cycle2.start

        # Compare performance of the 2 cycles
        self.logger.info("##################################################")
        self.logger.info(
            "Sched cycle time with attribute updates: %f" % cycle1_time)
        self.logger.info(
            "Sched cycle time without attribute updates: %f" % cycle2_time)
        self.logger.info("##################################################")
        m = "sched cycle time"
        self.perf_test_result([cycle1_time, cycle2_time], m, "sec")

    def setup_scheds(self):
        for i in range(1, 6):
            partition = 'P' + str(i)
            sched_name = 'sc' + str(i)
            a = {'partition': partition,
                 'sched_host': self.server.hostname}
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
        for i in range(1, 6):
            self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq' + str(i))
            p = {'partition': 'P' + str(i)}
            self.server.manager(MGR_CMD_SET, QUEUE, p, id='wq' + str(i))
            node = str(self.mom.shortname)
            num = i - 1
            self.server.manager(MGR_CMD_SET, NODE, p,
                                id=node + '[' + str(num) + ']')

    def submit_njobs(self, num_jobs=1, attrs=None, user=TEST_USER):
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
        self.submit_njobs(5000)
        start = time.time()
        self.scheduler.run_scheduling_cycle()
        c = self.scheduler.cycles(lastN=1)[0]
        cyc_dur = c.end - c.start
        self.perf_test_result(cyc_dur, "default_cycle_duration", "secs")
        msg = 'Time taken by default scheduler to run 5k jobs is '
        self.logger.info(msg + str(cyc_dur))
        self.server.cleanup_jobs()
        self.setup_scheds()
        self.setup_queues_nodes()
        for sc in self.scheds:
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SCHED, a, id=sc)
        a = {ATTR_q: 'wq1'}
        self.submit_njobs(1000, a)
        a = {ATTR_q: 'wq2'}
        self.submit_njobs(1000, a)
        a = {ATTR_q: 'wq3'}
        self.submit_njobs(1000, a)
        a = {ATTR_q: 'wq4'}
        self.submit_njobs(1000, a)
        a = {ATTR_q: 'wq5'}
        self.submit_njobs(1000, a)
        start = time.time()
        for sc in self.scheds:
            a = {'scheduling': 'True'}
            self.server.manager(MGR_CMD_SET, SCHED, a, id=sc)
        for sc in self.scheds:
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SCHED, a, id=sc)
        sc_dur = []
        for sc in self.scheds:
            if sc != 'default':
                self.logger.info("searching log for scheduler " + str(sc))
                log_msg = self.scheds[sc].log_match("Leaving Scheduling Cycle",
                                                    starttime=int(start),
                                                    max_attempts=30)
                endtime = PBSLogUtils.convert_date_time(
                    log_msg[1].split(';')[0])
                dur = endtime - start
                sc_dur.append(dur)
        max_dur = max(sc_dur)
        self.perf_test_result(max_dur, "max_multisched_cycle_duration", "secs")
        msg = 'Max time taken by one of the multi sched to run 1k jobs is '
        self.logger.info(msg + str(max_dur))
        self.perf_test_result(
            cyc_dur - max_dur, "multisched_defaultsched_cycle_diff", "secs")
        self.assertLess(max_dur, cyc_dur)
        msg1 = 'Multi scheduler is faster than single scheduler by '
        msg2 = 'secs in scheduling 5000 jobs with 5 schedulers'
        self.logger.info(msg1 + str(cyc_dur - max_dur) + msg2)

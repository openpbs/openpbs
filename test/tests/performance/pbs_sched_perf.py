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

from tests.performance import *


class TestSchedPerf(TestPerformance):
    """
    Test the performance of scheduler features
    """

    def setUp(self):
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
        a = {'PBS_LOG_HIGHRES_TIMESTAMP': 1}
        self.du.set_pbs_config(confs=a, append=True)
        self.scheduler.restart()

    def cust_attr_func(self, name, totalnodes, numnode, attribs):
        """
        Add custom resources to nodes
        """
        a = {'resources_available.color': self.colors[numnode % 7]}
        return dict(list(attribs.items()) + list(a.items()))

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
        num_jobs = 3000
        self.compare_normal_path_to_buckets('free', num_jobs)

    @timeout(3600)
    def test_run_many_jobs(self):
        """
        Submit many jobs and time the cycle that runs all of them.
        """
        num_jobs = 10000
        a = {'Resource_List.select': '1:ncpus=1'}
        jids = self.submit_jobs(a, num_jobs, wt_start=1000)
        t = self.run_cycle()
        self.server.expect(JOB, {'state=R': num_jobs})
        self.logger.info('#' * 80)
        m = 'Time taken in cycle to run %d normal jobs: %.2f' % (num_jobs, t)
        self.logger.info(m)
        self.logger.info('#' * 80)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        for j in jids:
            self.server.rerunjob(j)
            self.server.alterjob(j, {'Resource_List.place': 'excl'})

        self.server.expect(JOB, {'state=Q': num_jobs})

        t = self.run_cycle()

        self.server.expect(JOB, {'state=R': num_jobs})
        self.logger.info('#' * 80)
        m = 'Time taken in cycle to run %d bucket jobs: %.2f' % (num_jobs, t)
        self.logger.info(m)
        self.logger.info('#' * 80)

    @timeout(3600)
    def test_pset_fuzzy_perf(self):
        """
        Test opt_backfill_fuzzy with placement sets.
        """

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
        self.server.expect(SERVER, {'server_state': (NE, 'Scheduling')})

        self.server.expect(JOB, {'job_state=R': 1430})

        a = {'Resource_List.select': '10000:ncpus=1'}
        tj = Job(TEST_USER, attrs=a)
        self.server.submit(tj)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.expect(SERVER, {'server_state': (NE, 'Scheduling')},
                           interval=5, max_attempts=240)

        cycle1 = self.scheduler.cycles(lastN=1)[0]
        cycle1_time = cycle1.end - cycle1.start

        a = {'opt_backfill_fuzzy': 'High'}
        self.server.manager(MGR_CMD_SET, SCHED, a, id='default')

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.expect(SERVER, {'server_state': (NE, 'Scheduling')},
                           interval=5, max_attempts=240)

        cycle2 = self.scheduler.cycles(lastN=1)[0]
        cycle2_time = cycle2.end - cycle2.start

        self.logger.info('Cycle 1: %f Cycle 2: %f Perc %.2f%%' % (
            cycle1_time, cycle2_time, (cycle1_time / cycle2_time) * 100))
        self.assertLess(cycle2_time, cycle1_time,
                        'Optimization was not faster')
        self.perf_test_result(((cycle1_time / cycle2_time) * 100),
                              "optimized_percentage", "percentage")

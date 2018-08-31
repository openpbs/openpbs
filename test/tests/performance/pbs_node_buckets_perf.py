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


class TestNodeBucketPerf(TestPerformance):
    """
    Test the performance of node buckets
    """

    def setUp(self):
        TestPerformance.setUp(self)
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string', 'flag': 'h'}, id='color',
                            expect=True)
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
        return dict(attribs.items() + a.items())

    @timeout(10000)
    def test_node_bucket_perf(self):
        """
        Submit a large number of jobs which use node buckets.  Run a cycle and
        compare that to a cycle that doesn't use node buckets.  Jobs require
        place=scatter:excl to use node buckets.
        """
        num_jobs = 1000
        a = {'Resource_List.select': '1429:ncpus=1:color=yellow',
             'Resource_List.place': 'scatter'}
        Jyellow = Job(TEST_USER, attrs=a)
        jid_yellow = self.server.submit(Jyellow)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid_yellow)

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        jids = []
        a = {'Resource_List.select':
             '1429:ncpus=1:color=blue+1429:ncpus=1:color=yellow',
             "Resource_List.place": 'scatter'}
        J = Job(TEST_USER, attrs=a)
        a = {'Resource_List.select':
             '1429:ncpus=1:color=blue+1429:ncpus=1:color=yellow',
             "Resource_List.place": 'scatter',
             "Resource_List.walltime": 100}
        for n in range(num_jobs):
            a["Resource_List.walltime"] = a["Resource_List.walltime"] + n
            J = Job(TEST_USER, attrs=a)
            jid = self.server.submit(J)
            jids += [jid]

        t = int(time.time())
        # run only one cycle
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # wait for cycle to finish
        self.scheduler.log_match("Leaving Scheduling Cycle", starttime=t,
                                 max_attempts=120, interval=5)
        c = self.scheduler.cycles(lastN=1)[0]
        cycle1_time = c.end - c.start

        a = {'Resource_List.place': 'scatter:excl'}
        for jid in jids:
            self.server.alterjob(jid, a)

        t = int(time.time())

        # run only one cycle
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # wait for cycle to finish
        self.scheduler.log_match("Leaving Scheduling Cycle", starttime=t,
                                 max_attempts=120, interval=5)

        c = self.scheduler.cycles(lastN=1)[0]
        cycle2_time = c.end - c.start
        self.logger.info('Cycle 1: %d Cycle 2: %d Cycle time difference: %d' %
                         (cycle1_time, cycle2_time, cycle1_time - cycle2_time))
        self.assertTrue(cycle1_time > cycle2_time)

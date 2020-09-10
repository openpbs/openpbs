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

from tests.functional import *


@requirements(num_moms=2)
class TestPbsNodeRampDownCset(TestFunctional):

    """
    This tests the Node Rampdown Feature on a cluster where the
    sister mom is a cgroup cpuset system with two NUMA nodes.
    """

    def setUp(self):

        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

        # skip if there are no cpuset systems in the test cluster
        no_csetmom = True
        for mom in self.moms.values():
            if mom.is_cpuset_mom():
                no_csetmom = False
        if no_csetmom:
            self.skipTest("Skip on cluster without cgroup cpuset system.")

        # Various node names
        self.n0 = self.moms.values()[0].shortname
        self.n1 = self.moms.values()[1].shortname
        self.n2 = '%s[0]' % (self.n1,)
        self.n3 = '%s[1]' % (self.n1,)

        # skip if there are less than one regular vnode and
        # three from cpuset system (natural + 2 NUMA vnodes)
        nodeinfo = self.server.status(NODE)
        if len(nodeinfo) < 4:
            self.skipTest("Not enough vnodes to run the test.")
        # skip if second mom has less than two NUMA vnodes
        if nodeinfo[3]['id'] != self.n3:
            self.skipTest("Second mom has less than 2 vnodes")
        # skip if none of the vnodes are in free state
        for node in nodeinfo:
            if node['state'] != 'free':
                self.skipTest("Not all the vnodes are in free state")

        self.pbs_release_nodes_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_release_nodes')

        # number of resource ncpus to request initially
        ncpus = self.server.status(NODE, 'resources_available.ncpus',
                                   id=self.n3)[0]
        ncpus = int(ncpus['resources_available.ncpus'])
        self.ncpus2 = ncpus / 2

        # expected values upon successful job submission
        self.job1_schedselect = \
            "1:ncpus=1:mem=2gb+1:ncpus=%d:mem=2gb+" % self.ncpus2 + \
            "1:ncpus=%d:mem=2gb:vnode=%s" % (self.ncpus2, self.n3)
        self.job1_exec_host = "%s/0+%s/0*%d+%s/1*%d" % (
            self.n0, self.n1, self.ncpus2, self.n1, self.ncpus2)
        self.job1_exec_vnode = \
            "(%s:ncpus=1:mem=2097152kb)+" % (self.n0,) + \
            "(%s:ncpus=%d:mem=2097152kb)+" % (self.n2, self.ncpus2) + \
            "(%s:ncpus=%d:mem=2097152kb)" % (self.n3, self.ncpus2)

        # expected values after release of vnode
        self.job1_schedsel1 = \
            "1:ncpus=1:mem=2097152kb+1:ncpus=%d:mem=2097152kb" % (self.ncpus2)
        self.job1_exec_host1 = \
            "%s/0+%s/0*%d" % (self.n0, self.n1, self.ncpus2)
        self.job1_exec_vnode1 = \
            "(%s:ncpus=1:mem=2097152kb)+" % (self.n0,) + \
            "(%s:ncpus=%d:mem=2097152kb)" % (self.n2, self.ncpus2)

        # cgroup cpuset path on second node
        cmd = ['grep cgroup', '/proc/mounts', '|', 'grep cpuset', '|',
               'grep -v', '/dev/cpuset']
        ret = self.server.du.run_cmd(self.n1, cmd, runas=TEST_USER)
        self.cset_path = ret['out'][0].split()[1]

    def test_release_nodes_on_cpuset_sis(self):
        """
        Submit job that will use cpus on two NUMA vnodes on second mom,
        goes in R state. Use pbs_release_node to successfully release one
        of the NUMA vnodes and its resources used in the job.
        """
        # Submit a job that uses second mom's two NUMA nodes, in R state
        a = {'Resource_List.select':
             'ncpus=1:mem=2gb+ncpus=%d:mem=2gb+ncpus=%d:mem=2gb:vnode=%s' %
             (self.ncpus2, self.ncpus2, self.n3),
             'Resource_List.place': 'vscatter'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 1 + self.ncpus2 * 2,
                                 'Resource_List.nodect': 3,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid1)

        # Check the cpuset before releasing self.n3 from jid1
        cset_file = self.cset_path + '/pbs_jobs.service/jobid/' + jid1 + \
            '/cpuset.cpus'
        cset_before = self.du.cat(self.n1, cset_file)
        cset_j1_before = cset_before['out']
        self.logger.info("cset_j1_before : %s" % cset_j1_before)

        before_release = time.time()

        # Release a NUMA vnode on second mom using command pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid1, self.n3]
        ret = self.server.du.run_cmd(self.server.hostname,
                                     cmd, runas=TEST_USER)
        self.assertEqual(ret['rc'], 0)

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.ncpus': 1 + self.ncpus2,
                                 'Resource_List.nodect': 2,
                                 'schedselect': self.job1_schedsel1,
                                 'exec_host': self.job1_exec_host1,
                                 'exec_vnode': self.job1_exec_vnode1}, id=jid1)

        # Check if sister mom updated its internal nodes table after release
        self.moms.values()[1].log_match('Job;%s;updated nodes info' % jid1,
                                        starttime=before_release-1,
                                        max_attempts=10)

        # Check the cpuset for the job after releasing self.n3
        cset_after = self.du.cat(self.n1, cset_file)
        cset_j1_after = cset_after['out']
        self.logger.info("cset_j1_after : %s" % cset_j1_after)

        # Compare the before and after cpusets info
        msg = "%s: cpuset cpus remain after release of %s" % (jid1, self.n3)
        self.assertNotEqual(cset_j1_before, cset_j1_after, msg)

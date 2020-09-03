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
    sister mom is a cgroup cpuset system.
    """

    def setUp(self):

        # skip if there are less than one regular vnode and
        # three from cpuset system (natural + 2 NUMA vnodes)
        nodeinfo = self.server.status(NODE)
        if len(nodeinfo) < 4:
            self.skipTest("Not enough vnodes to run the test.")

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

        # skip if second mom has less than two NUMA vnodes
        try:
            self.server.expect(NODE, {'state': 'free'},
                               id=self.n3, max_attempts=10)
        except PtlExpectError:
            self.skipTest("Second mom has less than 2 vnodes")

        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

        a = {'state': 'free', 'resources_available.ncpus': (GE, 1)}
        self.server.expect(VNODE, {'state=free': 4}, op=EQ, count=True,
                           max_attempts=10, interval=2)

        self.pbs_release_nodes_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_release_nodes')

        # number of resource ncpus to request initially
        ncpus = self.server.status(NODE, 'resources_available.ncpus',
                                   id=self.n3)[0]
        ncpus = int(ncpus['resources_available.ncpus'])
        self.ncpus2 = ncpus / 2 - 1

        # expected values upon successful job submission
        self.job1_schedselect = \
            "1:ncpus=1:mem=2gb+1:ncpus=%d:mem=2gb+" % self.ncpus2 + \
            "1:ncpus=%d:mem=2gb" % self.ncpus2
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

    def test_release_nodes_on_cpuset_sis(self):
        """
        Submit job that will use cpus on two NUMA vnodes on second mom,
        goes in R state. Use pbs_release_node to release one of the NUMA
        vnodes. The NUMA vnode and its resources get released. Submit a
        second job requesting the released NUMA vnode. Job should run and
        a new cpuset gets created that uses the released cpus.
        """
        # Submit a job that uses second mom's two NUMA nodes, in R state
        a = {'Resource_List.select':
             'ncpus=1:mem=2gb+ncpus=%d:mem=2gb+ncpus=%d:mem=2gb' %
             (self.ncpus2, self.ncpus2), 'Resource_List.place': 'vscatter'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 1 + self.ncpus2 * 2,
                                 'Resource_List.nodect': 3,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid1)

        # Release on NUMA vnode on sis mom using command pbs_release_nodes
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

        # Submit a second job requesting the released NUMA node, in R state
        a = {'Resource_List.select': 'ncpus=%d:mem=2gb:vnode=%s' %
             (self.ncpus2 + 2, self.n3)}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2, max_attempts=10)

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

import time
from tests.functional import *


class TestPbsCpuset(TestFunctional):

    """
    This tests the Reliable Job Startup Feature with cpuset mom.
    A job can be started with extra nodes with node failures tolerated
    during job start. Released cpuset resources can be reused by another job.
    """

    def setUp(self):
        if not self.mom.is_cpuset_mom():
            self.skipTest("Test suite only meant to run with cpuset mom.")
        TestFunctional.setUp(self)

        # launch hook
        self.launch_hook_body = """
import pbs
import time
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")
# print out the vnode_list[] values
for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")
# print out the vnode_list_fail[] values:
for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
if e.job.in_ms_mom():
    pj = e.job.release_nodes(keep_select="ncpus=1:mem=2gb")
    if pj is None:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at LAUNCH")
pbs.logmsg(pbs.LOG_DEBUG, "Sleeping for 20sec")
time.sleep(20)
"""

    def test_reliable_job_startup_on_cpuset(self):
        """
        A job is started with two numa nodes and goes in R state.
        An execjob_launch hook will force job to have only one numa node.
        The released numa node can be used in another job.
        """

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        stime = int(time.time())
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # Check mom logs that the launch hook got propagated
        msg = "Hook;launch.PY;copy hook-related file request received"
        self.mom.log_match(msg, starttime=stime, interval=2, max_attempts=60)

        # Submit job1
        j = Job(TEST_USER, {
            ATTR_l + '.select': '2:ncpus=1:mem=2gb',
            ATTR_l + '.place': 'vscatter',
            ATTR_W: 'tolerate_node_failures=job_start'})
        stime = int(time.time())
        jid = self.server.submit(j)

        # Check the exec_vnode while in substate 41
        self.server.expect(JOB, {ATTR_substate: '41'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode1 = job_stat[0]['exec_vnode']
        self.logger.info("initial exec_vnode: %s" % execvnode1)
        initial_vnodes = execvnode1.split('+')

        # Check the exec_vnode after job is in substate 42
        self.server.expect(JOB, {ATTR_substate: '42'}, offset=20, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode2 = job_stat[0]['exec_vnode']
        self.logger.info("pruned exec_vnode: %s" % execvnode2)

        # Check for msg in mom logs indicating the job has cpuset
        msg = "new_cpuset:  setting altid to CPU set named /PBSPro/%s" % jid
        self.mom.log_match(msg, starttime=stime)

        # Check mom logs for pruned from and pruned to messages
        self.mom.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.mom.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, execvnode2), starttime=stime)

        # Find out the released vnode
        if initial_vnodes[0] == execvnode2:
            execvnodeB = initial_vnodes[1]
        else:
            execvnodeB = initial_vnodes[0]
        vnodeB = execvnodeB.split(':')[0].split('(')[1]
        self.logger.info("released vnode: %s" % vnodeB)

        # Submit job2 requesting the released vnode, job runs
        j2 = Job(TEST_USER, {
            ATTR_l + '.select': '1:ncpus=1:mem=2gb:vnode=%s' % vnodeB})
        stime = int(time.time())
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, offset=20, id=jid2)

        # Check for msg in mom logs indicating job has cpuset
        msg2 = "new_cpuset:  setting altid to CPU set named /PBSPro/%s" % jid2
        self.mom.log_match(msg2, starttime=stime)

        # Check if exec_vnode for job2 matches released vnode from job1
        self.server.expect(JOB, 'exec_vnode', id=jid2, op=SET)
        job_stat = self.server.status(JOB, id=jid2)
        execvnode3 = job_stat[0]['exec_vnode']
        self.assertEqual(execvnode3, execvnodeB)
        self.logger.info("job2 exec_vnode %s is the released vnode %s" % (
            execvnode3, execvnodeB))

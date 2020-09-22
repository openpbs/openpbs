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
class TestPbsCpuset(TestFunctional):

    """
    This testsuite covers various features using cgroup cpuset systems
        - Reliable Job Startup Feature
        - Node Rampdown Feature
    """

    def check_stageout_file_size(self):
        """
        This Function will check that atleast 1gb of test.img
        file which is to be stagedout is created in 10 seconds
        """
        fpath = os.path.join(TEST_USER.home, "test.img")
        cmd = ['stat', '-c', '%s', fpath]
        fsize = 0
        for i in range(11):
            rc = self.du.run_cmd(hosts=self.h0, cmd=cmd,
                                 runas=TEST_USER)
            if rc['rc'] == 0 and len(rc['out']) == 1:
                try:
                    fsize = int(rc['out'][0])
                except:
                    pass
            # 1073741824 == 1Gb
            if fsize > 1073741824:
                break
            else:
                time.sleep(1)
        if fsize <= 1073741824:
            self.fail("Failed to create 1gb file at %s" % fpath)

    def setUp(self):
        TestFunctional.setUp(self)

        # skip if there are no cpuset systems in the test cluster
        no_csetmom = True
        for mom in self.moms.values():
            if mom.is_cpuset_mom():
                no_csetmom = False
        if no_csetmom:
            self.skipTest("Skip on cluster without cgroup cpuset system.")

        # Various host names
        self.h0 = self.moms.values()[0].shortname
        self.h1 = self.moms.values()[1].shortname
        self.hostA = socket.getfqdn(self.h0)
        self.hostB = socket.getfqdn(self.h1)
        # Various node names. First mom may or may not be a cpuset system.
        try:
            self.n0 = self.server.status(
                NODE, id='%s[0]' % (self.h0))[0]['id']
        except PbsStatusError:
            self.n0 = self.h0
        self.n1 = self.h1
        self.n2 = '%s[0]' % (self.n1)
        self.n3 = '%s[1]' % (self.n1)

        # Skip if there are less than four vnodes. There should be
        # three from cpuset system (natural + two NUMA vnodes)
        nodeinfo = self.server.status(NODE)
        if len(nodeinfo) < 4:
            self.skipTest("Not enough vnodes to run the test.")
        # skip if second mom has less than two NUMA vnodes
        try:
            self.server.status(NODE, id=self.n3)
        except PbsStatusError:
            self.skipTest("vnode %s doesn't exist on pbs server" % (self.n3))
        # skip if vnodes are not in free state
        for node in nodeinfo:
            if node['state'] != 'free':
                self.skipTest("Not all the vnodes are in free state")

        self.pbs_release_nodes_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_release_nodes')
        # number of resource ncpus to request initially
        ncpus = self.server.status(NODE, 'resources_available.ncpus',
                                   id=self.n3)[0]
        # request a partial amount of ncpus in self.n3
        self.ncpus2 = int(ncpus['resources_available.ncpus']) / 2
        # cgroup cpuset path on second node
        cmd = ['grep cgroup', '/proc/mounts', '|', 'grep cpuset', '|',
               'grep -v', '/dev/cpuset']
        ret = self.server.du.run_cmd(self.n1, cmd, runas=TEST_USER)
        self.cset_path = ret['out'][0].split()[1]

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
    pj = e.job.release_nodes(keep_select="ncpus=1:mem=1gb")
    if pj is None:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at LAUNCH")
pbs.logmsg(pbs.LOG_DEBUG, "Sleeping for 20sec")
time.sleep(20)
"""

        self.script = {}
        self.job1_select = "ncpus=1:mem=1gb+" + \
            "ncpus=%d:mem=1gb:vnode=%s+" % (self.ncpus2, self.n2) + \
            "ncpus=%d:mem=1gb:vnode=%s" % (self.ncpus2, self.n3)
        self.job1_place = "vscatter"

        # expected values upon successful job submission
        self.job1_schedselect = "1:ncpus=1:mem=1gb+" + \
            "1:ncpus=%d:mem=1gb:vnode=%s+" % (self.ncpus2, self.n2) + \
            "1:ncpus=%d:mem=1gb:vnode=%s" % (self.ncpus2, self.n3)
        self.job1_exec_host = "%s/0+%s/0*%d+%s/1*%d" % (
            self.h0, self.h1, self.ncpus2, self.n1, self.ncpus2)
        self.job1_exec_vnode = "(%s:ncpus=1:mem=1048576kb)+" % (self.n0,) + \
            "(%s:ncpus=%d:mem=1048576kb)+" % (self.n2, self.ncpus2) + \
            "(%s:ncpus=%d:mem=1048576kb)" % (self.n3, self.ncpus2)

        # expected values after release of vnode of self.n3
        self.job1_schedsel1 = "1:ncpus=1:mem=1048576kb+" + \
            "1:ncpus=%d:mem=1048576kb:vnode=%s" % (self.ncpus2, self.n2)
        self.job1_exec_host1 = "%s/0+%s/0*%d" % (self.h0, self.h1, self.ncpus2)
        self.job1_exec_vnode1 = "(%s:ncpus=1:mem=1048576kb)+" % (self.n0,) + \
            "(%s:ncpus=%d:mem=1048576kb)" % (self.n2, self.ncpus2)

        # expected values during lengthy stageout
        self.job1_newsel = "1:ncpus=1:mem=1048576kb"
        self.job1_new_exec_host = "%s/0" % self.h0
        self.job1_new_exec_vnode = "(%s:ncpus=1:mem=1048576kb)" % self.n0

        # values to use when matching accounting logs
        self.job1_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1_exec_vnode_esc = self.job1_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.job1_sel_esc = self.job1_select.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.job1_new_exec_vnode_esc = self.job1_new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

    def tearDown(self):
        for host in [self.h0, self.h1]:
            test_img = os.path.join("/home", "pbsuser", "test.img")
            self.du.rm(hostname=host, path=test_img, force=True,
                       runas=TEST_USER)
        TestFunctional.tearDown(self)

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
        stime = time.time()
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # Check mom logs that the launch hook got propagated
        msg = "Hook;launch.PY;copy hook-related file request received"
        self.moms.values()[1].log_match(msg, starttime=stime)

        # Submit job1 that uses second mom's two NUMA nodes, in R state
        a = {ATTR_l + '.select': self.job1_select,
             ATTR_l + '.place': self.job1_place,
             ATTR_W: 'tolerate_node_failures=job_start'}
        j = Job(TEST_USER, attrs=a)
        stime = time.time()
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

        # Check mom logs for pruned from and pruned to messages
        self.moms.values()[0].log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.moms.values()[0].log_match("Job;%s;pruned to exec_vnode=%s" % (
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
            ATTR_l + '.select': '1:ncpus=4:mem=1gb:vnode=%s' % vnodeB})
        stime = time.time()
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, offset=20, id=jid2)

        # Check if exec_vnode for job2 matches released vnode from job1
        self.server.expect(JOB, 'exec_vnode', id=jid2, op=SET)
        job_stat = self.server.status(JOB, id=jid2)
        execvnode3 = job_stat[0]['exec_vnode']
        self.assertEqual(execvnode3, execvnodeB)
        self.logger.info("job2 exec_vnode %s is the released vnode %s" % (
            execvnode3, execvnodeB))

    def test_release_nodes_on_cpuset_sis(self):
        """
        On a cluster where the second mom is a cgroup cpuset system with two
        NUMA nodes, submit a job that will use cpus on both NUMA vnodes.
        The job goes in R state. Use pbs_release_nodes to successfully release
        one of the NUMA vnodes and its resources used in the job. Compare the
        job's cgroup cpuset info before and after calling pbs_release_nodes
        to verify that NUMA node's cpu resources were released.
        """
        # Submit a job that uses second mom's two NUMA nodes, in R state
        a = {ATTR_l + '.select': self.job1_select,
             ATTR_l + '.place': self.job1_place}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '3gb',
                                 'Resource_List.ncpus': 1 + self.ncpus2 * 2,
                                 'Resource_List.nodect': 3,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid1)

        # Check the cpuset before releasing self.n3 from jid1
        cset_file = os.path.join(self.cset_path, 'pbs_jobs.service/jobid',
                                 jid1, 'cpuset.cpus')
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
                                        starttime=before_release-1)

        # Check the cpuset for the job after releasing self.n3
        cset_after = self.du.cat(self.n1, cset_file)
        cset_j1_after = cset_after['out']
        self.logger.info("cset_j1_after : %s" % cset_j1_after)

        # Compare the before and after cpusets info
        msg = "%s: cpuset cpus remain after release of %s" % (jid1, self.n3)
        self.assertNotEqual(cset_j1_before, cset_j1_after, msg)

    def test_release_nodes_on_stageout_cset(self):
        """
        Submit a job, with -W release_nodes_on_stageout=true as a PBS directive
        in the job script, that will use cpus and mem on two NUMA vnodes on the
        second mom. The job goes in R state. The job creates a huge stageout
        file. When the job is deleted the sister NUMA vnodes are released
        during lengthy stageout and only the primary execution host's vnode
        is left assigned to the job.
        """
        FIB40 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', '') + \
            'pbs_python -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint(fib(40))\\\")"'
        FIB400 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', '') + \
            'pbs_python -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint(fib(400))\\\")"'

        self.script['job1'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            "#PBS -W stageout=test.img@%s:test.img\n" % (self.n1,) + \
            "#PBS -W release_nodes_on_stageout=true\n" + \
            "dd if=/dev/zero of=test.img count=1024 bs=2097152\n" + \
            "pbsdsh -n 1 -- %s\n" % (FIB40,) + \
            "pbsdsh -n 2 -- %s\n" % (FIB40,) + \
            "%s\n" % (FIB400,)

        stime = time.time()
        j = Job(TEST_USER)
        j.create_script(self.script['job1'])
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R',
                                 'release_nodes_on_stageout': 'True',
                                 'Resource_List.mem': '3gb',
                                 'Resource_List.ncpus': 1 + self.ncpus2 * 2,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)
        # Check various vnode status.
        attr0 = {'state': 'job-busy', 'jobs': jid + '/0',
                 'resources_assigned.ncpus': 1,
                 'resources_assigned.mem': '1048576kb'}
        self.server.expect(VNODE, attr0, id=self.n0)
        attr1 = {'state': 'free', 'resources_assigned.ncpus': 0,
                 'resources_assigned.mem': '0kb'}
        self.server.expect(VNODE, attr1, id=self.n1)
        attr2 = {'state': 'free',
                 'jobs': '%s/0, %s/1, %s/2, %s/3' % (jid, jid, jid, jid),
                 'resources_assigned.ncpus': 4,
                 'resources_assigned.mem': '1048576kb'}
        for vn in [self.n2, self.n3]:
            self.server.expect(VNODE, attr2, id=vn)
        # job's PBS_NODEFILE contents should match exec_host
        pbs_nodefile = os.path.join(self.server.
                                    pbs_conf['PBS_HOME'], 'aux', jid)
        cmd = ['cat', pbs_nodefile]
        ret = self.server.du.run_cmd(self.h0, cmd, sudo=False)
        self.assertTrue(self.hostA and self.hostB in ret['out'])

        # The job will write out enough file size to have a lengthy stageout
        self.check_stageout_file_size()

        # Deleting the job will trigger the stageout process
        # at which time the sister node is automatically released
        # due to release_nodes_stageout=true set
        self.server.delete(jid)

        # Verify remaining job resources.
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '1gb',
                                 'Resource_List.ncpus': 1,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)
        # Check various vnode status
        attr0 = {'state': 'job-busy', 'jobs': jid + '/0',
                 'resources_assigned.ncpus': 1,
                 'resources_assigned.mem': '1048576kb'}
        self.server.expect(VNODE, attr0, id=self.n0)
        attr1 = {'state': 'free', 'resources_assigned.ncpus': '0',
                 'resources_assigned.mem': '0kb'}
        for vn in [self.n1, self.n2, self.n3]:
            self.server.expect(VNODE, attr1, id=vn)
        # job's PBS_NODEFILE contents should match exec_host
        ret = self.server.du.run_cmd(self.h0, cmd, sudo=False)
        self.assertTrue(self.hostA in ret['out'])
        self.assertFalse(self.hostB in ret['out'])
        # Verify mom_logs
        self.moms.values()[0].log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.n1), n=10, regexp=True)
        self.moms.values()[1].log_match(
            "Job;%s;DELETE_JOB2 received" % (jid,), n=20)
        # Check account update ('u') record
        msg0 = ".*%s;%s.*exec_host=%s" % ('u', jid, self.job1_exec_host_esc)
        msg1 = ".*exec_vnode=%s" % self.job1_exec_vnode_esc
        msg2 = ".*Resource_List\.mem=%s" % '3gb'
        msg3 = ".*Resource_List\.ncpus=%d" % 9
        msg4 = ".*Resource_List\.place=%s" % self.job1_place
        msg5 = ".*Resource_List\.select=%s.*" % self.job1_sel_esc
        msg = msg0 + msg1 + msg2 + msg3 + msg4 + msg5
        self.server.accounting_match(msg=msg, regexp=True, n="ALL",
                                     starttime=stime)
        # Check to make sure 'c' (next) record got generated
        msg0 = ".*%s;%s.*exec_host=%s" % ('c', jid, self.job1_new_exec_host)
        msg1 = ".*exec_vnode=%s" % self.job1_new_exec_vnode_esc
        msg2 = ".*Resource_List\.mem=%s" % '1048576kb'
        msg3 = ".*Resource_List\.ncpus=%d" % 1
        msg4 = ".*Resource_List\.place=%s" % self.job1_place
        msg5 = ".*Resource_List\.select=%s.*" % self.job1_newsel
        msg = msg0 + msg1 + msg2 + msg3 + msg4 + msg5
        self.server.accounting_match(msg=msg, regexp=True, n="ALL",
                                     starttime=stime)

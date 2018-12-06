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

from tests.functional import *


def convert_time(fmt, tm, fixdate=False):
    """
    Convert given time stamp <tm> into given format <fmt>
    if fixdate is True add <space> before date if date is < 9
    (This is because to match output with ctime as qstat uses it)
    """
    rv = time.strftime(fmt, time.localtime(float(tm)))
    if ((sys.platform not in ('cygwin', 'win32')) and (fixdate)):
        rv = rv.split()
        date = int(rv[2])
        if date <= 9:
            date = ' ' + str(date)
        rv[2] = str(date)
        rv = ' '.join(rv)
    return rv


def create_subjob_id(job_array_id, subjob_index):
    """
    insert subjob index into the square brackets of job array id
    """
    idx = job_array_id.find('[]')
    return job_array_id[:idx + 1] + str(subjob_index) + job_array_id[idx + 1:]


class TestPbsReliableJobStartup(TestFunctional):

    """
    This tests the Reliable Job Startup Feature,
    where a job can be started with extra nodes,
    with node failures tolerated during job start
    (and even throughout the life of the job),
    before pruning job back to a set of healthy
    nodes that satisfy the original request.

    Custom parameters:
    moms: colon-separated hostnames of five MoMs
    """

    def pbs_nodefile_match_exec_host(self, jid, exec_host,
                                     schedselect=None):
        """
        Look into the PBS_NODEFILE on the first host listed in 'exec_host'
        and returns True if all host entries in 'exec_host' match the entries
        in the file. Otherwise, return False.

        # Look for 'mpiprocs' values in 'schedselect' (if not None), and
        # verify that the corresponding node hosts are appearing in
        # PBS_NODEFILE 'mpiprocs' number of times.
        """

        pbs_nodefile = os.path.join(self.server.
                                    pbs_conf['PBS_HOME'], 'aux', jid)

        # look for mpiprocs settings
        mpiprocs = []
        if schedselect is not None:
            for chunk in schedselect.split('+'):
                chl = chunk.split(':')
                for ch in chl:
                    if ch.find('=') != -1:
                        c = ch.split('=')
                        if c[0] == "mpiprocs":
                            mpiprocs.append(c[1])
        ehost = exec_host.split('+')
        first_host = ehost[0].split('/')[0]

        cmd = ['cat', pbs_nodefile]
        ret = self.server.du.run_cmd(first_host, cmd, sudo=False)
        ehost2 = []
        for h in ret['out']:
            ehost2.append(h.split('.')[0])

        ehost1 = []
        j = 0
        for eh in ehost:
            h = eh.split('/')
            if (len(mpiprocs) > 0):
                for _ in range(int(mpiprocs[j])):
                    ehost1.append(h[0])
            else:
                ehost1.append(h[0])
            j += 1

        self.logger.info("EHOST1=%s" % (ehost1,))
        self.logger.info("EHOST2=%s" % (ehost2,))
        if cmp(ehost1, ehost2) != 0:
            return False
        return True

    def match_accounting_log(self, atype, jid, exec_host, exec_vnode,
                             mem, ncpus, nodect, place, select):
        """
        This checks if there's an accounting log record 'atype' for
        job 'jid' containing the values given (i.e.
        Resource_List.exec_host, Resource_List.exec_vnode, etc...)
        This throws an exception upon encountering a non-matching
        accounting_logs entry.
        Some example values of 'atype' are: 'u' (update record due to
        release node request), 'c' (record containing the next
        set of resources to be used by a phased job as a result of
        release node request), 'e' (last update record for a phased job
        due to a release node request), 'E' (end of job record),
        's' (secondary start record).
        """

        if atype == 'e':
            self.mom.log_match("Job;%s;Obit sent" % (jid,), n=100,
                               max_attempts=5, interval=5)

        self.server.accounting_match(
            msg=".*%s;%s.*exec_host=%s" % (atype, jid, exec_host),
            regexp=True, n=20, max_attempts=3)

        self.server.accounting_match(
            msg=".*%s;%s.*exec_vnode=%s" % (atype, jid, exec_vnode),
            regexp=True, n=20, max_attempts=3)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.mem=%s" % (atype, jid,  mem),
            regexp=True, n=20, max_attempts=3)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.ncpus=%d" % (atype, jid, ncpus),
            regexp=True, n=20, max_attempts=3)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.nodect=%d" % (atype, jid, nodect),
            regexp=True, n=20, max_attempts=3)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.place=%s" % (atype, jid, place),
            regexp=True, n=20, max_attempts=3)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.select=%s" % (atype, jid, select),
            regexp=True, n=20, max_attempts=3)

        if (atype != 'c') and (atype != 'S') and (atype != 's'):
            self.server.accounting_match(
                msg=".*%s;%s.*resources_used\." % (atype, jid),
                regexp=True, n=20, max_attempts=3)

    def match_vnode_status(self, vnode_list, state, jobs=None, ncpus=None,
                           mem=None):
        """
        Given a list of vnode names in 'vnode_list', check to make
        sure each vnode's state, jobs string, resources_assigned.mem,
        and resources_assigned.ncpus match the passed arguments.
        This will throw an exception if a match is not found.
        """
        for vn in vnode_list:
            dict_match = {'state': state}
            if jobs is not None:
                dict_match['jobs'] = jobs
            if ncpus is not None:
                dict_match['resources_assigned.ncpus'] = ncpus
            if mem is not None:
                dict_match['resources_assigned.mem'] = mem

            self.server.expect(VNODE, dict_match, id=vn)

    def create_and_submit_job(self, job_type, attribs=None):
        """
        create the job object and submit it to the server
        based on 'job_type' and attributes list 'attribs'.
        """
        if attribs:
            retjob = Job(TEST_USER, attrs=attribs)
        else:
            retjob = Job(TEST_USER)

        if job_type == 'job1':
            retjob.create_script(self.script['job1'])
        elif job_type == 'job1_2':
            retjob.create_script(self.script['job1_2'])
        elif job_type == 'job1_3':
            retjob.create_script(self.script['job1_3'])
        elif job_type == 'job1_4':
            retjob.create_script(self.script['job1_4'])
        elif job_type == 'job2':
            retjob.create_script(self.script['job2'])
        elif job_type == 'job3':
            retjob.create_script(self.script['job3'])
        elif job_type == 'job4':
            retjob.create_script(self.script['job4'])
        elif job_type == 'job5':
            retjob.create_script(self.script['job5'])
        elif job_type == 'jobA':
            retjob.create_script(self.script['jobA'])

        return self.server.submit(retjob)

    def setUp(self):

        if len(self.moms) != 5:
            cmt = "need 5 mom hosts: -p moms=<m1>:<m2>:<m3>:<m4>:<m5>"
            self.skip_test(reason=cmt)

        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

        self.server.cleanup_jobs(extend="force")

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momC = self.moms.values()[2]
        self.momD = self.moms.values()[3]
        self.momE = self.moms.values()[4]

        # Now start setting up and creating the vnodes
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")

        # set node momA
        self.hostA = self.momA.shortname
        self.momA.delete_vnode_defs()
        vnode_prefix = self.hostA
        a = {'resources_available.mem': '1gb',
             'resources_available.ncpus': '1'}
        vnodedef = self.momA.create_vnode_def(vnode_prefix, a, 4)
        self.assertNotEqual(vnodedef, None)
        self.momA.insert_vnode_def(vnodedef, 'vnode.def')
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)

        # set node momB
        self.hostB = self.momB.shortname
        self.momB.delete_vnode_defs()
        vnode_prefix = self.hostB
        a = {'resources_available.mem': '1gb',
             'resources_available.ncpus': '1'}
        vnodedef = self.momB.create_vnode_def(vnode_prefix, a, 5,
                                              usenatvnode=True)
        self.assertNotEqual(vnodedef, None)
        self.momB.insert_vnode_def(vnodedef, 'vnode.def')
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)

        # set node momC
        # This one has no vnode definition.

        self.hostC = self.momC.shortname
        self.momC.delete_vnode_defs()
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostC)
        a = {'resources_available.ncpus': 2,
             'resources_available.mem': '2gb'}
        # set natural vnode of hostC
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostC,
                            expect=True)

        # set node momD
        # This one has no vnode definition.

        self.hostD = self.momD.shortname
        self.momD.delete_vnode_defs()
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostD)
        a = {'resources_available.ncpus': 5,
             'resources_available.mem': '5gb'}
        # set natural vnode of hostD
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostD,
                            expect=True)

        # set node momE
        self.hostE = self.momE.shortname
        self.momE.delete_vnode_defs()
        vnode_prefix = self.hostE
        a = {'resources_available.mem': '1gb',
             'resources_available.ncpus': '1'}
        vnodedef = self.momE.create_vnode_def(vnode_prefix, a, 5,
                                              usenatvnode=True)
        self.assertNotEqual(vnodedef, None)
        self.momE.insert_vnode_def(vnodedef, 'vnode.def')
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostE)

        # Various node names
        self.nA = self.hostA
        self.nAv0 = '%s[0]' % (self.hostA,)
        self.nAv1 = '%s[1]' % (self.hostA,)
        self.nAv2 = '%s[2]' % (self.hostA,)
        self.nAv3 = '%s[3]' % (self.hostA,)
        self.nB = self.hostB
        self.nBv0 = '%s[0]' % (self.hostB,)
        self.nBv1 = '%s[1]' % (self.hostB,)
        self.nBv2 = '%s[2]' % (self.hostB,)
        self.nBv3 = '%s[3]' % (self.hostB,)
        self.nC = self.hostC
        self.nD = self.hostD
        self.nE = self.hostE
        self.nEv0 = '%s[0]' % (self.hostE,)
        self.nEv1 = '%s[1]' % (self.hostE,)
        self.nEv2 = '%s[2]' % (self.hostE,)
        self.nEv3 = '%s[3]' % (self.hostE,)

        a = {'state': 'free', 'resources_available.ncpus': (GE, 1)}
        self.server.expect(VNODE, {'state=free': 17}, count=True,
                           max_attempts=10, interval=2)

        if sys.platform in ('cygwin', 'win32'):
            SLEEP_CMD = "pbs-sleep"
        else:
            SLEEP_CMD = os.path.join(os.sep, "bin", "sleep")

        self.pbs_release_nodes_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_release_nodes')

        FIB37 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                             'pbs_python') + \
            ' -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint fib(37)\\\")"'

        self.fib37_value = 24157817

        FIB40 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                             'pbs_python') + \
            ' -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint fib(40)\\\")"'

        # job submission arguments
        self.script = {}
        # original select spec
        self.job1_oselect = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=2:mem=2gb"
        self.job1_place = "scatter"
        # incremented values at job start and just before actual launch
        self.job1_iselect = \
            "1:ncpus=3:mem=2gb+2:ncpus=3:mem=2gb+2:ncpus=2:mem=2gb"
        self.job1_ischedselect = self.job1_iselect
        self.job1_iexec_host = "%s/0*0+%s/0*0+%s/0*3+%s/0*2+%s/0*0" % (
            self.nA, self.nB, self.nD, self.nC, self.nE)
        self.job1_iexec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:ncpus=2:mem=2097152kb)+" % (self.nC,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nE,) + \
            "%s:mem=1048576kb:ncpus=1)" % (self.nEv0,)
        self.job1_isel_esc = self.job1_iselect.replace("+", "\+")
        self.job1_iexec_host_esc = self.job1_iexec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1_iexec_vnode_esc = self.job1_iexec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version 1 upon successful job launch
        self.job1_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job1_schedselect = self.job1_select
        self.job1_exec_host = "%s/0*0+%s/0*3+%s/0*0" % (
            self.nA, self.nD, self.nE)
        self.job1_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nE,) + \
            "%s:mem=1048576kb:ncpus=1)" % (self.nEv0,)

        self.job1_sel_esc = self.job1_select.replace("+", "\+")
        self.job1_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1_exec_vnode_esc = self.job1_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version 2 upon successful job launch
        self.job1v2_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job1v2_schedselect = self.job1v2_select
        self.job1v2_exec_host = "%s/0*0+%s/0*3+%s/0*2" % (
            self.nA, self.nD, self.nC)
        self.job1v2_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.nC,)

        self.job1v2_sel_esc = self.job1v2_select.replace("+", "\+")
        self.job1v2_exec_host_esc = self.job1v2_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1v2_exec_vnode_esc = self.job1v2_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version 3 upon successful job launch
        self.job1v3_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job1v3_schedselect = self.job1v3_select
        self.job1v3_exec_host = "%s/0*0+%s/0*0+%s/0*0" % (
            self.nA, self.nB, self.nE)
        self.job1v3_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nE,) + \
            "%s:mem=1048576kb:ncpus=1)" % (self.nEv0,)

        self.job1v3_sel_esc = self.job1v3_select.replace("+", "\+")
        self.job1v3_exec_host_esc = self.job1v3_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1v3_exec_vnode_esc = self.job1v3_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version 4 upon successful job launch
        self.job1v4_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job1v4_schedselect = self.job1v4_select
        self.job1v4_exec_host = "%s/0*0+%s/0*0+%s/0*2" % (
            self.nA, self.nB, self.nD)
        self.job1v4_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.nD,)

        self.job1v4_sel_esc = self.job1v4_select.replace("+", "\+")
        self.job1v4_exec_host_esc = self.job1v4_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1v4_exec_vnode_esc = self.job1v4_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version 5 upon successful job launch
        self.job1v5_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job1v5_schedselect = self.job1v5_select
        self.job1v5_exec_host = "%s/0*0+%s/0*0+%s/0*2" % (
            self.nA, self.nB, self.nC)
        self.job1v5_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.nC,)

        self.job1v5_sel_esc = self.job1v5_select.replace("+", "\+")
        self.job1v5_exec_host_esc = self.job1v5_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1v5_exec_vnode_esc = self.job1v5_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version 6 upon successful job launch
        self.job1v6_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job1v6_select += "+1:ncpus=1:mem=1gb"
        self.job1v6_schedselect = self.job1v6_select
        self.job1v6_exec_host = "%s/0*0+%s/0*0+%s/0*2+%s/0" % (
            self.nA, self.nB, self.nC, self.nE)
        self.job1v6_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=2:mem=2097152kb)+" % (self.nC,) + \
            "(%s:mem=1048576kb:ncpus=1)" % (self.nE,)

        self.job1v6_sel_esc = self.job1v6_select.replace("+", "\+")
        self.job1v6_exec_host_esc = self.job1v6_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1v6_exec_vnode_esc = self.job1v6_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        self.script['job1'] = """
#PBS -l select=%s
#PBS -l place=%s
#PBS -W umask=022
#PBS -S /bin/bash
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
echo 'FIB TESTS'
echo 'pbsdsh -n 1 fib 37'
pbsdsh -n 1 -- %s
echo 'pbsdsh -n 2 fib 37'
pbsdsh -n 2 -- %s
echo 'fib 37'
%s
echo 'HOSTNAME TESTS'
echo 'pbsdsh -n 0 hostname'
pbsdsh -n 0 --  hostname -s
echo 'pbsdsh -n 1 hostname'
pbsdsh -n 1 --  hostname -s
echo 'pbsdsh -n 2 hostname'
pbsdsh -n 2 --  hostname -s
echo 'PBS_NODEFILE tests'
for h in `cat $PBS_NODEFILE`
do
    echo "HOST=$h"
    echo "pbs_tmrsh $h hostname"
    pbs_tmrsh $h hostname -s
done
""" % (self.job1_oselect, self.job1_place, FIB37, FIB37, FIB37)

        # original select spec
        self.jobA_oselect = "ncpus=1:mem=1gb+ncpus=1:mem=1gb+ncpus=1:mem=1gb"
        self.jobA_place = "scatter"
        # incremented values at job start and just before actual launch
        self.jobA_iselect = \
            "1:ncpus=1:mem=1gb+2:ncpus=1:mem=1gb+2:ncpus=1:mem=1gb"
        self.jobA_ischedselect = self.jobA_iselect
        self.jobA_iexec_host1 = "%s/0+%s/0+%s/0+%s/0+%s/0" % (
            self.nA, self.nB, self.nC, self.nD, self.nE)
        self.jobA_iexec_host2 = "%s/1+%s/1+%s/1+%s/1+%s/1" % (
            self.nA, self.nB, self.nC, self.nD, self.nE)
        self.jobA_iexec_host3 = "%s/2+%s/2+%s/0+%s/2+%s/0" % (
            self.nA, self.nB, self.nC, self.nD, self.nE)
        self.jobA_iexec_vnode1 = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nAv0,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nB,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nC,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nD,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.nE,)
        self.jobA_iexec_vnode2 = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nAv1,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nBv0,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nC,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nD,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.nEv0,)
        self.jobA_iexec_vnode3 = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nAv2,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nBv1,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nC,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nD,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.nE,)
        self.jobA_isel_esc = self.jobA_iselect.replace("+", "\+")
        self.jobA_iexec_host1_esc = self.jobA_iexec_host1.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.jobA_iexec_host2_esc = self.jobA_iexec_host2.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.jobA_iexec_host3_esc = self.jobA_iexec_host3.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.jobA_iexec_vnode1_esc = self.jobA_iexec_vnode1.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.jobA_iexec_vnode2_esc = self.jobA_iexec_vnode2.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.jobA_iexec_vnode3_esc = self.jobA_iexec_vnode3.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version 1 upon successful job launch
        self.jobA_select = \
            "1:ncpus=1:mem=1gb+1:ncpus=1:mem=1gb+1:ncpus=1:mem=1gb"
        self.jobA_schedselect = self.jobA_select
        self.jobA_exec_host1 = "%s/0+%s/0+%s/0" % (
            self.nA, self.nB, self.nD)
        self.jobA_exec_host2 = "%s/1+%s/1+%s/1" % (
            self.nA, self.nB, self.nD)
        self.jobA_exec_host3 = "%s/2+%s/2+%s/2" % (
            self.nA, self.nB, self.nD)
        self.jobA_exec_vnode1 = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nAv0,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nB,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.nD,)
        self.jobA_exec_vnode2 = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nAv1,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nBv0,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.nD,)
        self.jobA_exec_vnode3 = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nAv2,) + \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.nBv1,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.nD,)

        self.jobA_sel_esc = self.jobA_select.replace("+", "\+")
        self.jobA_exec_host1_esc = self.jobA_exec_host1.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.jobA_exec_host2_esc = self.jobA_exec_host2.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.jobA_exec_host3_esc = self.jobA_exec_host3.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.jobA_exec_vnode1_esc = self.jobA_exec_vnode1.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.jobA_exec_vnode2_esc = self.jobA_exec_vnode2.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.jobA_exec_vnode3_esc = self.jobA_exec_vnode3.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.script['jobA'] = """
#PBS -J 1-3
#PBS -l select=%s
#PBS -l place=%s
#PBS -S /bin/bash
echo 'HOSTNAME TESTS'
echo 'pbsdsh -n 0 hostname'
pbsdsh -n 0 -- hostname -s
echo 'pbsdsh -n 1 hostname'
pbsdsh -n 1 -- hostname -s
echo 'pbsdsh -n 2 hostname'
pbsdsh -n 2 -- hostname -s
sleep 180
""" % (self.jobA_oselect, self.jobA_place)

        self.script['job1_3'] = """
#PBS -l select=%s
#PBS -l place=%s
#PBS -W umask=022
#PBS -S /bin/bash
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
echo 'FIB TESTS'
echo 'pbsdsh -n 2 fib 40'
pbsdsh -n 2 -- %s
echo 'fib 40'
%s
echo 'HOSTNAME TESTS'
echo 'pbsdsh -n 0 hostname'
pbsdsh -n 0 -- hostname -s
echo 'pbsdsh -n 2 hostname'
pbsdsh -n 2 -- hostname -s
""" % (self.job1_oselect, self.job1_place, FIB40, FIB40)

        self.script['job1_2'] = """
#PBS -l select=%s
#PBS -l place=%s
#PBS -W umask=022
#PBS -S /bin/bash
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
echo 'FIB TESTS'
echo 'pbsdsh -n 2 fib 37'
pbsdsh -n 2 -- %s
echo 'fib 37'
%s
echo 'HOSTNAME TESTS'
echo 'pbsdsh -n 0 hostname'
pbsdsh -n 0 -- hostname -s
echo 'pbsdsh -n 2 hostname'
pbsdsh -n 2 -- hostname -s
""" % (self.job1_oselect, self.job1_place, FIB37, FIB37)

        self.script['job1_3'] = """
#PBS -l select=%s
#PBS -l place=%s
#PBS -W umask=022
#PBS -S /bin/bash
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
echo 'FIB TESTS'
echo 'pbsdsh -n 2 fib 40'
pbsdsh -n 2 -- %s
echo 'fib 40'
%s
echo 'HOSTNAME TESTS'
echo 'pbsdsh -n 0 hostname'
pbsdsh -n 0 -- hostname -s
echo 'pbsdsh -n 2 hostname'
pbsdsh -n 2 -- hostname -s
""" % (self.job1_oselect, self.job1_place, FIB40, FIB40)

        self.script['job1_4'] = """
#PBS -l select=%s
#PBS -l place=%s
#PBS -W umask=022
#PBS -S /bin/bash
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
echo 'FIB TESTS'
echo 'pbsdsh -n 1 fib 37'
pbsdsh -n 1 -- %s
echo 'pbsdsh -n 2 fib 37'
pbsdsh -n 2 -- %s
echo 'pbsdsh -n 3 fib 37'
pbsdsh -n 3 -- %s
echo 'fib 37'
%s
echo 'HOSTNAME TESTS'
echo 'pbsdsh -n 0 hostname'
pbsdsh -n 0 -- hostname -s
echo 'pbsdsh -n 1 hostname'
pbsdsh -n 1 -- hostname -s
echo 'pbsdsh -n 2 hostname'
pbsdsh -n 2 -- hostname -s
echo 'pbsdsh -n 3 hostname'
pbsdsh -n 3 -- hostname -s
echo 'PBS_NODEFILE tests'
for h in `cat $PBS_NODEFILE`
do
    echo "HOST=$h"
    echo "pbs_tmrsh $h hostname"
    pbs_tmrsh $h hostname -s
done
""" % (self.job1_oselect, self.job1_place, FIB37, FIB37, FIB37, FIB37)

        # original select spec
        self.job2_oselect = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=0:mem=2gb"
        self.job2_place = "scatter"
        # incremented values at job start and just before actual launch
        self.job2_iselect = \
            "1:ncpus=3:mem=2gb+2:ncpus=3:mem=2gb+2:ncpus=0:mem=2gb"
        self.job2_ischedselect = self.job2_iselect
        self.job2_iexec_host = "%s/0*0+%s/0*0+%s/0*3+%s/0*0+%s/0*0" % (
            self.nA, self.nB, self.nD, self.nC, self.nE)
        self.job2_iexec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:ncpus=0:mem=2097152kb)+" % (self.nC,) + \
            "(%s:mem=1048576kb:ncpus=0+" % (self.nE,) + \
            "%s:mem=1048576kb)" % (self.nEv0,)
        self.job2_isel_esc = self.job2_iselect.replace("+", "\+")
        self.job2_iexec_host_esc = self.job2_iexec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job2_iexec_vnode_esc = self.job2_iexec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # expected values version upon successful job launch
        self.job2_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=0:mem=2gb"
        self.job2_schedselect = self.job2_select
        self.job2_exec_host = "%s/0*0+%s/0*3+%s/0*0" % (
            self.nA, self.nD, self.nE)

        # ncpus=0 assigned hosts are not listed in $PBS_NODEFILE
        self.job2_exec_host_nfile = "%s/0*0+%s/0*3" % (
            self.nA, self.nD)

        self.job2_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:mem=1048576kb+" % (self.nE,) + \
            "%s:mem=1048576kb)" % (self.nEv0,)

        self.job2_sel_esc = self.job2_select.replace("+", "\+")
        self.job2_exec_host_esc = self.job2_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job2_exec_vnode_esc = self.job2_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        self.script['job2'] = \
            "#PBS -l select=" + self.job2_oselect + "\n" + \
            "#PBS -l place=" + self.job2_place + "\n" + \
            SLEEP_CMD + " 60\n"

        # Job with mpiprocs and ompthreads requested
        self.job3_oselect = \
            "ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+" + \
            "ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+" + \
            "ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"
        self.job3_place = "scatter"
        # incremented values at job start and just before actual launch
        self.job3_iselect = \
            "1:ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+" + \
            "2:ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+" + \
            "2:ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"
        self.job3_ischedselect = self.job3_iselect
        self.job3_iexec_host = \
            "%s/0*0+%s/0*0+%s/0*3+%s/0*2+%s/0*0" % (
                self.nA, self.nB, self.nD, self.nC, self.nE)
        self.job3_iexec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:ncpus=2:mem=2097152kb)+" % (self.nC,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nE,) + \
            "%s:mem=1048576kb:ncpus=1)" % (self.nEv0,)

        # expected values version 6 upon successful job launch
        self.job3_select = \
            "1:ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+" + \
            "1:ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+" + \
            "1:ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"

        self.job3_schedselect = self.job3_select
        self.job3_exec_host = "%s/0*0+%s/0*3+%s/0*0" % (
            self.nA, self.nD, self.nE)
        self.job3_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nE,) + \
            "%s:mem=1048576kb:ncpus=1)" % (self.nEv0,)

        self.job3_sel_esc = self.job3_select.replace("+", "\+")
        self.job3_exec_host_esc = self.job3_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job3_exec_vnode_esc = self.job3_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        self.job3_isel_esc = self.job3_iselect.replace("+", "\+")
        self.job3_iexec_host_esc = self.job3_iexec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job3_iexec_vnode_esc = self.job3_iexec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        self.script['job3'] = \
            "#PBS -l select=" + self.job3_oselect + "\n" + \
            "#PBS -l place=" + self.job3_place + "\n" + \
            SLEEP_CMD + " 300\n"

        self.job3_ischedselect = self.job3_iselect

        self.job4_oselect = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=2:mem=2gb"
        self.job4_place = "scatter:excl"
        self.job4_iselect = \
            "1:ncpus=3:mem=2gb+2:ncpus=3:mem=2gb+2:ncpus=2:mem=2gb"
        self.job4_ischedselect = self.job4_iselect
        self.job4_iexec_host = \
            "%s/0*0+%s/0*0+%s/0*3+%s/0*2+%s/0*0" % (
                self.nA, self.nB, self.nD, self.nC, self.nE)
        self.job4_iexec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:ncpus=2:mem=2097152kb)+" % (self.nC,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nE,) + \
            "%s:mem=1048576kb:ncpus=1)" % (self.nEv0,)

        # expected values upon successful job launch
        self.job4_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job4_schedselect = "1:ncpus=3:mem=2gb+" + \
            "1:ncpus=3:mem=2gb+1:ncpus=2:mem=2gb"
        self.job4_exec_host = "%s/0*0+%s/0*3+%s/0*0" % (
            self.nA, self.nD, self.nE)
        self.job4_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nE,) + \
            "%s:mem=1048576kb:ncpus=1)" % (self.nEv0,)

        self.script['job4'] = \
            "#PBS -l select=" + self.job4_oselect + "\n" + \
            "#PBS -l place=" + self.job4_place + "\n" + \
            SLEEP_CMD + " 300\n"

        self.job4_sel_esc = self.job4_select.replace("+", "\+")
        self.job4_exec_host_esc = self.job4_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job4_exec_vnode_esc = self.job4_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        self.job4_isel_esc = self.job4_iselect.replace("+", "\+")
        self.job4_iexec_host_esc = self.job4_iexec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job4_iexec_vnode_esc = self.job4_iexec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        self.job5_oselect = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=2:mem=2gb"
        self.job5_place = "free"
        self.job5_iselect = \
            "1:ncpus=3:mem=2gb+2:ncpus=3:mem=2gb+2:ncpus=2:mem=2gb"
        self.job5_ischedselect = self.job5_iselect
        self.job5_iexec_host = \
            "%s/0*0+%s/0*0+%s/0*3+%s/1*0+%s/0*2" % (
                self.nA, self.nB, self.nD, self.nB, self.nC)
        self.job5_iexec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:ncpus=3:mem=2097152kb)+" % (self.nD,) + \
            "(%s:mem=1048576kb+" % (self.nBv1,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv2,) + \
            "%s:ncpus=1)+" % (self.nBv3,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.nC,)

        # expected values upon successful job launch
        self.job5_select = \
            "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+1:ncpus=1:mem=1gb"
        self.job5_schedselect = self.job5_select
        self.job5_exec_host = "%s/0*0+%s/0*0+%s/1*0" % (
            self.nA, self.nB, self.nB)
        self.job5_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nAv0,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nAv1,) + \
            "%s:ncpus=1)+" % (self.nAv2) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.nB,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.nBv0,) + \
            "%s:ncpus=1)+" % (self.nBv1,) + \
            "(%s:mem=1048576kb+" % (self.nBv1,) + \
            "%s:ncpus=1)" % (self.nBv2,)

        self.script['job5'] = \
            "#PBS -l select=" + self.job5_oselect + "\n" + \
            "#PBS -l place=" + self.job5_place + "\n" + \
            SLEEP_CMD + " 300\n"

        self.job5_sel_esc = self.job5_select.replace("+", "\+")
        self.job5_exec_host_esc = self.job5_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job5_exec_vnode_esc = self.job5_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        self.job5_isel_esc = self.job5_iselect.replace("+", "\+")
        self.job5_iexec_host_esc = self.job5_iexec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job5_iexec_vnode_esc = self.job5_iexec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")

        # queuejob hooks used throughout the test
        self.qjob_hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "queuejob hook executed")
# Save current select spec in resource 'site'
e.job.Resource_List["site"] = str(e.job.Resource_List["select"])
new_select = e.job.Resource_List["select"].increment_chunks(1)
e.job.Resource_List["select"] = new_select
e.job.tolerate_node_failures = "job_start"
"""
        self.qjob_hook_body2 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "queuejob hook executed")
# Save current select spec in resource 'site'
e.job.Resource_List["site"] = str(e.job.Resource_List["select"])
new_select = e.job.Resource_List["select"].increment_chunks(1)
e.job.Resource_List["select"] = new_select
e.job.tolerate_node_failures = "all"
"""
        # begin hooks used throughout the test
        self.begin_hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing begin")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    e.reject("bad node")
""" % (self.nB,)
        # The below hook may not really be doing anything, but is
        # used in a test of the sister join job alarm time with
        # the hook's alarm value.
        self.begin_hook_body2 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing begin")
localnode=pbs.get_local_nodename()
"""
        self.begin_hook_body3 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing begin")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    x
""" % (self.nE,)

        self.begin_hook_body4 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing begin")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    e.reject("bad node")
""" % (self.nD,)

        self.begin_hook_body5 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing begin")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    e.reject("bad node")
""" % (self.nC,)

        # prologue hooks used throughout the test
        self.prolo_hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prolo")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list_fail[" + v.name + "]")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    e.reject("bad node")
""" % (self.nC,)

        self.prolo_hook_body2 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prologue")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    x
""" % (self.nC,)

        self.prolo_hook_body3 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prolo")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list_fail[" + v.name + "]")
localnode=pbs.get_local_nodename()
"""
        self.prolo_hook_body4 = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prolo")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list_fail[" + v.name + "]")
localnode=pbs.get_local_nodename()

if e.job.in_ms_mom():
    pj = e.job.release_nodes(keep_select=e.job.Resource_List["site"])
    if pj != None:
        pbs.logjobmsg(e.job.id, "prolo: job.exec_vnode=%s" % (pj.exec_vnode,))
        pbs.logjobmsg(e.job.id, "prolo: job.exec_host=%s" % (pj.exec_host,))
        pbs.logjobmsg(e.job.id,
                      "prolo: job.schedselect=%s" % (pj.schedselect,))
    else:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at PROLOGUE")
"""
        self.prolo_hook_body5 = """
import pbs
import time
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prolo")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "prolo: found vnode_list_fail[" + v.name + "]")
if not e.job.in_ms_mom():
    pbs.logjobmsg(e.job.id, "sleeping for 30 secs")
    time.sleep(30)
"""

        # launch hooks used throughout the test
        self.launch_hook_body = """
import pbs
e=pbs.event()

if 'PBS_NODEFILE' not in e.env:
    e.accept()

pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
if e.job.in_ms_mom():
    pj = e.job.release_nodes(keep_select=e.job.Resource_List["site"])
    if pj != None:
        pbs.logjobmsg(e.job.id, "launch: job.exec_vnode=%s" % (pj.exec_vnode,))
        pbs.logjobmsg(e.job.id, "launch: job.exec_host=%s" % (pj.exec_host,))
        pbs.logjobmsg(e.job.id,
                      "launch: job.schedselect=%s" % (pj.schedselect,))
    else:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at LAUNCH")
"""

        self.launch_hook_body2 = """
import pbs
e=pbs.event()

if 'PBS_NODEFILE' not in e.env:
    e.accept()

pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
if e.job.in_ms_mom():
    new_sel = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=1:mem=1gb"
    pj = e.job.release_nodes(keep_select=new_sel)
    if pj != None:
        pbs.logjobmsg(e.job.id, "launch: job.exec_vnode=%s" % (pj.exec_vnode,))
        pbs.logjobmsg(e.job.id, "launch: job.exec_host=%s" % (pj.exec_host,))
        pbs.logjobmsg(e.job.id,
                      "launch: job.schedselect=%s" % (pj.schedselect,))
    else:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at LAUNCH")
"""

    def tearDown(self):
        self.momA.signal("-CONT")
        self.momB.signal("-CONT")
        self.momC.signal("-CONT")
        self.momD.signal("-CONT")
        self.momE.signal("-CONT")
        self.momA.unset_mom_config('$sister_join_job_alarm', False)
        self.momA.unset_mom_config('$job_launch_delay', False)
        a = {'state': (DECR, 'offline')}
        self.server.manager(MGR_CMD_SET, NODE, a, self.momA.shortname)
        self.server.manager(MGR_CMD_SET, NODE, a, self.momB.shortname)
        self.server.manager(MGR_CMD_SET, NODE, a, self.momC.shortname)
        self.server.manager(MGR_CMD_SET, NODE, a, self.momD.shortname)
        self.server.manager(MGR_CMD_SET, NODE, a, self.momE.shortname)
        TestFunctional.tearDown(self)
        # Delete managers and operators if added
        attrib = ['operators', 'managers']
        self.server.manager(MGR_CMD_UNSET, SERVER, attrib, expect=True)

    @timeout(400)
    def test_t1(self):
        """
        Test tolerating job_start 2 node failures after adding
             extra nodes to the job, pruning
             job's assigned resources to match up to the original
             select spec, and offlining the failed vnodes.

             1.	Have a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=job_start

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                 chunk C.

             3. Have an execjob_begin hook that fails (causes rejection)
                when executed by mom managing vnodes in (B).

             4. Have an execjob_prologue hook that fails (causes rejection)
                when executed by mom managing vnodes in (C).

             5. Then create an execjob_launch hook that offlines the failed
                nodes (B) and (C), and prunes back the job's exec_vnode
                assignment back to satisfying the original 3-node select
                spec, choosing only healthy nodes.

             6. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(D)+(E)

                   since (B) and (C) contain vnodes from failed moms.

                b. vnodes in (B) and (C) are now showing a state of
                   "offline".
                c. The accounting log start record 'S' will reflect the
                   select request where additional chunks were added, while
                   the secondary start record 's' will reflect the assigned
                   resources after pruning the original select request via
                   the pbs.release_nodes(keep_select=...) call
                   inside execjob_launch hook.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_body = """
import pbs
e=pbs.event()

if 'PBS_NODEFILE' not in e.env:
    e.accept()

pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch:offline vnode_list_fail[" + v.name + "]")
    v.state = pbs.ND_OFFLINE
if e.job.in_ms_mom():
    pj = e.job.release_nodes(keep_select=e.job.Resource_List["site"])
    if pj != None:
        pbs.logjobmsg(e.job.id, "launch: job.exec_vnode=%s" % (pj.exec_vnode,))
        pbs.logjobmsg(e.job.id, "launch: job.exec_host=%s" % (pj.exec_host,))
        pbs.logjobmsg(e.job.id,
                      "launch: job.schedselect=%s" % (pj.schedselect,))
    else:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at LAUNCH")
"""
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nE, self.nEv0],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nBv2, self.nBv3,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        self.match_vnode_status([self.nB, self.nBv0, self.nBv1, self.nC],
                                'offline')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)
        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_prologue hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;prolo: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1, self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match(
                "Job;%s;launch:offline vnode_list_fail[%s]" % (jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momD.hostname, self.momE.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momD.shortname, self.momE.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname,
            self.momE.hostname, self.momE.hostname, self.momE.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    @timeout(400)
    def test_t2(self):
        """
        Test tolerating job_start 2 node failures after adding
             extra nodes to the job, pruning
             job's assigned resources to match up to the original
             select spec, without offlining the failed vnodes, and
             specifying mom config file options 'sister_join_job_alarm' and
             'job_launch_delay'.

             1. Set $sister_join_job_alarm and $job_launch_delay values
                in mom's config file.

             2.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=job_start

             3. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                chunk C.

             4. Prior to submitting a job, suspend mom B. When job runs,
                momB won't be able to join the job, so it won't be considered
                as a "healthy" mom.

             5. Have an execjob_begin hook that doesn't fail.

             6. Have an execjob_prologue hook that fails (causes rejection)
                when executed by mom managing vnodes in (C).

             7. Have an execjob_launch hook that prunes back the
                job's exec_vnode assignment back to satisfying the original
                3-node select spec, choosing only healthy nodes.

             8. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(D)+(E)

                   since (B) and (C) contain vnodes from failed moms.

                b. vnodes in (B) and (C) are now showing a state of "free".

                c. Mom's log file will show explicit values to
                   $sister_join_job_alarm and $job_launch_delay.

                c. The accounting log start record 'S' will reflect the
                   select request where additional chunks were added, while
                   the secondary start record 's' will reflect the assigned
                   resources after pruning the original select request via
                   the pbs.release_nodes(keep_select=...) call
                   inside execjob_launch hook.
        """
        # set mom config options:
        sis_join_alarm = 45
        c = {'$sister_join_job_alarm': sis_join_alarm}
        self.momA.add_config(c)

        job_launch_delay = 40
        c = {'$job_launch_delay': job_launch_delay}
        self.momA.add_config(c)

        self.momA.signal("-HUP")

        self.momA.log_match(
            "sister_join_job_alarm;%d" % (sis_join_alarm,), max_attempts=5,
            interval=5)
        self.momA.log_match(
            "job_launch_delay;%d" % (job_launch_delay,),
            max_attempts=5, interval=5)

        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body2)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # temporarily suspend momB, simulating a failed mom host.
        self.momB.signal("-STOP")
        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        # Set time to start scanning logs
        stime = int(time.time())

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND,
                           max_attempts=100)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Verify the logs and make sure sister_join_job_alarm is honored
        logs = self.mom.log_match(
            "Executing begin",
            allmatch=True, starttime=stime, max_attempts=8)
        log1 = logs[0][1]
        logs = self.mom.log_match(
            "Executing prolo",
            allmatch=True, starttime=stime, max_attempts=8)
        log2 = logs[0][1]
        pattern = '%m/%d/%Y %H:%M:%S'
        tmp = log1.split(';')
        # Convert the time into epoch time
        time1 = int(time.mktime(time.strptime(tmp[0], pattern)))
        tmp = log2.split(';')
        time2 = int(time.mktime(time.strptime(tmp[0], pattern)))

        diff = time2 - time1
        self.logger.info(
            "Time diff between begin hook and prologue hook is " +
            str(diff) + " seconds")
        # Leave a little wiggle room for slow systems
        self.assertTrue((diff >= sis_join_alarm) and
                        diff <= (sis_join_alarm + 5))

        self.mom.log_match(
            "sister_join_job_alarm wait time %d secs exceeded" % (
                sis_join_alarm,), starttime=stime, max_attempts=8)

        # Verify the logs and make sure job_launch_delay is honored
        logs = self.mom.log_match(
            "Executing prolo",
            allmatch=True, starttime=stime, max_attempts=8)
        log1 = logs[0][1]
        logs = self.mom.log_match(
            "Executing launch",
            allmatch=True, starttime=stime, max_attempts=8)
        log2 = logs[0][1]
        pattern = '%m/%d/%Y %H:%M:%S'
        tmp = log1.split(';')
        # Convert the time into epoch time
        time1 = int(time.mktime(time.strptime(tmp[0], pattern)))
        tmp = log2.split(';')
        time2 = int(time.mktime(time.strptime(tmp[0], pattern)))

        diff = time2 - time1
        self.logger.info("Time diff between prolo hook and launch hook is " +
                         str(diff) + " seconds")
        # Leave a little wiggle room for slow systems
        self.assertTrue((diff >= job_launch_delay) and
                        diff <= (job_launch_delay + 3))

        self.momA.log_match(
            "not all prologue hooks to sister moms completed, " +
            "but job will proceed to execute", n=10)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nE, self.nEv0],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nC,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)
        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momD.hostname, self.momE.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momD.shortname, self.momE.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname,
            self.momE.hostname, self.momE.hostname, self.momE.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    @timeout(400)
    def test_t3(self):
        """
        Test: tolerating job_start 2 node failures after adding
              extra nodes to the job, pruning
              job's assigned resources to match up to the original
              select spec, without offlining the failed vnodes, and
              with 2 execjob_prologue hooks, with prologue hook1
              having alarm1 and prologue hook2 having alarm2.
              This also test the default value to sister_join_job_alarm.

             1.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=job_start

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                chunk C.

             3. Prior to submitting a job, suspend mom B. When job runs,
                momB won't be able to join the job, so it won't be considered
                as a "healthy" mom.

             4. Have an execjob_prologue hook that doesn't fail any mom host
                with alarm=alarm1, order=1.

             5. Have an execjob_prologue hook2 with alarm=alarm2, order=2,
                that fails (causes rejection) when executed by mom managing
                vnodes in (C).

             6. Have an execjob_launch hook that prunes back the
                job's exec_vnode assignment back to satisfying the original
                3-node select spec, choosing only healthy nodes.

             7. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(D)+(E)

                   since (B) and (C) contain vnodes from failed moms.

                b. vnodes in (B) and (C) are now showing a state of "free".

                c. Mom's log file shows the wait time from execjob_prologue
                   hook1 execution and the execution of the exescjob_launch
                   hook is no more than alarm1+alarm2.

                c. The accounting log start record 'S' will reflect the
                   select request where additional chunks were added, while
                   the secondary start record 's' will reflect the assigned
                   resources after pruning the original select request via
                   the pbs.release_nodes(keep_select=...) call
                   inside execjob_launch hook.
        """

        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body2)

        # instantiate execjob_prologue hook #1
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prolo1")
localnode=pbs.get_local_nodename()
"""
        hook_event = "execjob_prologue"
        hook_name = "prolo1"
        alarm1 = 17
        a = {'event': hook_event, 'enabled': 'true', 'order': 1,
             'alarm': alarm1}
        self.server.create_import_hook(hook_name, a, hook_body)

        # instantiate execjob_prologue hook #2
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prolo2")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "prolo2: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "prolo2: found vnode_list_fail[" + v.name + "]")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    x
""" % (self.nC,)
        hook_event = "execjob_prologue"
        hook_name = "prolo2"
        alarm2 = 16
        a = {'event': hook_event, 'enabled': 'true', 'order': 2,
             'alarm': alarm2}
        self.server.create_import_hook(hook_name, a, hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # temporarily suspend momB, simulating a failed mom host.
        self.momB.signal("-STOP")

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        # Set time to start scanning logs
        stime = int(time.time())

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND,
                           max_attempts=100)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Verify the logs and make sure sister_join_job_alarm is honored
        logs = self.mom.log_match(
            "Executing begin",
            allmatch=True, starttime=stime, max_attempts=8)
        log1 = logs[0][1]
        logs = self.mom.log_match(
            "Executing prolo1",
            allmatch=True, starttime=stime, max_attempts=8)
        log2 = logs[0][1]
        pattern = '%m/%d/%Y %H:%M:%S'
        tmp = log1.split(';')
        # Convert the time into epoch time
        time1 = int(time.mktime(time.strptime(tmp[0], pattern)))
        tmp = log2.split(';')
        time2 = int(time.mktime(time.strptime(tmp[0], pattern)))

        diff = time2 - time1
        self.logger.info(
            "Time diff between begin hook and prologue hook is " +
            str(diff) + " seconds")
        # Leave a little wiggle room for slow systems

        # test default sister_join_job_alarm value
        sis_join_alarm = 30
        self.assertTrue((diff >= sis_join_alarm) and
                        diff <= (sis_join_alarm + 5))

        self.mom.log_match(
            "sister_join_job_alarm wait time %d secs exceeded" % (
                sis_join_alarm,), starttime=stime, max_attempts=8)

        # Verify the logs and make sure job_launch_delay is honored
        logs = self.mom.log_match(
            "Executing prolo1",
            allmatch=True, starttime=stime, max_attempts=8)
        log1 = logs[0][1]
        logs = self.mom.log_match(
            "Executing launch",
            allmatch=True, starttime=stime, max_attempts=8)
        log2 = logs[0][1]
        pattern = '%m/%d/%Y %H:%M:%S'
        tmp = log1.split(';')
        # Convert the time into epoch time
        time1 = int(time.mktime(time.strptime(tmp[0], pattern)))
        tmp = log2.split(';')
        time2 = int(time.mktime(time.strptime(tmp[0], pattern)))

        diff = time2 - time1
        self.logger.info(
            "Time diff between prolo1 hook and launch hook is " +
            str(diff) + " seconds")
        # Leave a little wiggle room for slow systems
        job_launch_delay = alarm1 + alarm2
        self.assertTrue((diff >= job_launch_delay) and
                        diff <= (job_launch_delay + 3))

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nE, self.nEv0],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nC,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)

        self.momA.log_match(
            "not all prologue hooks to sister moms completed, " +
            "but job will proceed to execute", n=10)

        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo2: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match(
                "Job;%s;launch: found vnode_list_fail[%s]" % (jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momD.hostname, self.momE.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momD.shortname, self.momE.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname,
            self.momE.hostname, self.momE.hostname, self.momE.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    @timeout(400)
    def test_t4(self):
        """
        Test: tolerating job_start 1 node failure that is used
              to satisfy a multi-chunk request, after adding
              extra nodes to the job, pruning
              job's assigned resources to match up to the original
              select spec.

             1.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=job_start

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                chunk C.

             3. Have an execjob_begin hook that fails (causes rejection)
                when executed by mom managing vnodes in (B).

             4. Then create an execjob_launch hook that
                prunes back the job's exec_vnode assignment back to
                satisfying the original 3-node select spec,
                choosing only healthy nodes.

             5. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(D)+(C)

                   since (B) contain vnodes from failed moms.

                b. The accounting log start record 'S' will reflect the
                   select request where additional chunks were added, while
                   the secondary start record 's' will reflect the assigned
                   resources after pruning the original select request via
                   the pbs.release_nodes(keep_select=...) call
                   inside execjob_launch hook.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1v2_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1v2_schedselect,
                                 'exec_host': self.job1v2_exec_host,
                                 'exec_vnode': self.job1v2_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=70)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.nC], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nE,
                                 self.nEv0, self.nEv1, self.nEv2,
                                 self.nEv3], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1v2_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1v2_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v2_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v2_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v2_exec_host_esc,
                                  self.job1v2_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1v2_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momD.hostname, self.momC.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momD.shortname, self.momC.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname,
            self.momC.hostname, self.momC.hostname, self.momC.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    @timeout(400)
    def test_t5(self):
        """
        Test: tolerating job_start 1 node failure used in a regular
              chunk after adding extra nodes to the job, pruning
             job's assigned resources to match up to the original
             select spec.

             1.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=job_start

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                chunk C.

             3. Have an execjob_prologue hook that fails (causes
                rejection) when executed by mom managing vnodes in (C).

             4. Then create an execjob_launch hook that
                prunes back the job's exec_vnode assignment back to
                satisfying the original 3-node select spec,
                choosing only healthy nodes.

             5. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(B)+(E)

                   since (C) contain vnodes from failed moms.

                b. The accounting log start record 'S' will reflect the
                   select request where additional chunks were added, while
                   the secondary start record 's' will reflect the assigned
                   resources after pruning the original select request via
                   the pbs.release_nodes(keep_select=...) call
                   inside execjob_launch hook.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body2)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1v3_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1v3_schedselect,
                                 'exec_host': self.job1v3_exec_host,
                                 'exec_vnode': self.job1v3_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=70)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1, self.nB, self.nBv0,
                                 self.nE, self.nEv0], 'job-busy', jobs_assn1,
                                1, '1048576kb')

        self.match_vnode_status([self.nAv2, self.nBv1],
                                'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nBv2, self.nBv3,
                                 self.nC, self.nD, self.nEv1, self.nEv2,
                                 self.nEv3], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1v3_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match(
                "Job;%s;launch: found vnode_list_fail[%s]" % (jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
                            jid, self.job1v3_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v3_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
                            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v3_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v3_exec_host_esc,
                                  self.job1v3_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1v3_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momB.hostname, self.momE.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momB.shortname, self.momE.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momB.hostname, self.momB.hostname, self.momB.shortname,
            self.momE.hostname, self.momE.hostname, self.momE.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    def test_t6(self):
        """
        Test: tolerating job_start of 2 node failures used to
              satisfy the smaller chunks, after adding extra nodes
              to the job, pruning job's assigned resources to match up
              to the original select spec.

             1.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=job_start

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                chunk C. (C) and (E) are of smaller chunks than (B)
                and (D). For example:
                    (D) =  "(nadal:ncpus=3:mem=2097152kb)"
                    (C) =  "(lendl:ncpus=2:mem=2097152kb)"

             3. Have an execjob_begin hook that fails (causes
                rejection) when executed by mom managing vnodes in (C).

             4. Have an execjob_prologue hook that fails (causes
                rejection) when executed by mom managing vnodes in (E).

             5. Then create an execjob_launch hook that
                prunes back the job's exec_vnode assignment back to
                satisfying the original 3-node select spec,
                choosing only healthy nodes.

             6. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(B)+(D)

                   since (C) and (E) contain vnodes from failed moms.
                   Note that from (D), only allocate enough resources
                   to satisfy the smaller third requested chunk.
                   if (D) originally has "(nadal:ncpus=3:mem=2097152kb)",
                   reassigning this would only be
                   "(nadal:ncpus=2:mem=2097152kb)".

                b. The accounting log start record 'S' will reflect the
                   select request where additional chunks were added, while
                   the secondary start record 's' will reflect the assigned
                   resources after pruning the original select request via
                   the pbs.release_nodes(keep_select=...) call
                   inside execjob_launch hook.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body3)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body2)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1v4_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1v4_schedselect,
                                 'exec_host': self.job1v4_exec_host,
                                 'exec_vnode': self.job1v4_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=70)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1, self.nB, self.nBv0],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.nAv2, self.nBv1],
                                'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nBv2, self.nBv3,
                                 self.nC, self.nD, self.nEv1, self.nEv2,
                                 self.nEv3], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1v4_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostE), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostE) +
            "is tolerant of node failures",
            regexp=True, n=10)

        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nC, self.nE]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1v4_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v4_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v4_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v4_exec_host_esc,
                                  self.job1v4_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1v4_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momB.hostname, self.momD.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momB.shortname, self.momD.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momB.hostname, self.momB.hostname, self.momB.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    def test_t7(self):
        """
        Test: tolerating job_start of 2 node failures used to
              satisfy the larger chunks, after adding extra nodes
              to the job. Pruning job's assigned resources to match up
              to the original select spec would fail, as the
              unsatisfied chunk requests cannot be handled by
              by the remaining smaller sized nodes. The failure
              to prune job is followed by a pbs.event().rerun()
              action and a job hold. Also, this test
              setting tolerate_node_falures=none.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_prologue hook
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prologue")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    x
""" % (self.nD,)
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostD) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostD) +
            "as job is tolerant of node failures", n=10, regexp=True)

        self.momA.log_match("Job;%s;could not satisfy select chunk" % (jid,),
                            n=10)

        self.momA.log_match("Job;%s;NEED chunks for keep_select" % (jid,),
                            n=10)

        self.momA.log_match(
            "Job;%s;HAVE chunks from job's exec_vnode" % (jid,), n=10)

        self.momA.log_match("execjob_launch request rejected by 'launch'",
                            n=10)

        errmsg = "unsuccessful at LAUNCH"
        self.momA.log_match("Job;%s;%s" % (jid, errmsg,), n=10)
        self.server.expect(JOB, {'job_state': 'H'},
                           id=jid, interval=1, max_attempts=70)

        # turn off queuejob
        self.server.manager(MGR_CMD_SET, HOOK, {'enabled': 'false'}, 'qjob')

        # modify job so as to not tolerate_node_failures
        a = {ATTR_tolerate_node_failures: "none"}
        self.server.alterjob(jobid=jid, attrib=a)

        # release hold on job
        self.server.rlsjob(jobid=jid, holdtype='s')

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+could not JOIN_JOB" % (
                jid), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostE) +
            "is tolerant of node failures",
            regexp=True, n=10, existence=False, max_attempts=10)

        self.server.expect(JOB, {'job_state': 'H'},
                           id=jid, interval=1, max_attempts=15)

        # turn off begin hook, leaving prologue hook in place
        self.server.manager(MGR_CMD_SET, HOOK, {'enabled': 'false'}, 'begin')

        # release hold on job
        self.server.rlsjob(jobid=jid, holdtype='s')

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.momA.log_match(
            "Job;%s;job_start_error.+could not IM_EXEC_PROLOGUE" % (jid,),
            n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True,
            existence=False, max_attempts=10)

        self.server.expect(JOB, {'job_state': 'H'},
                           id=jid, interval=1, max_attempts=15)

        # turn off prologue hook, so only launch hook remains.
        self.server.manager(MGR_CMD_SET, HOOK, {'enabled': 'false'}, 'prolo')

        # release hold on job
        self.server.rlsjob(jobid=jid, holdtype='s')

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'none',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'exec_host': self.job1_iexec_host,
                                 'exec_vnode': self.job1_iexec_vnode,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        # tolerate_node_failures=none and launch hook calls release_nodes()
        emsg = "no nodes released as job does not tolerate node failures"
        self.momA.log_match("%s: %s" % (jid, emsg), n=30)

    def test_t8(self):
        """
        Test tolerating node failures at job startup with no
             failed moms.

             1.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=all

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                 chunk C.

             3. Have an execjob_begin, execjob_prologue hooks that don't
                fail any of the sister moms.
                when executed by mom managing vnodes in (C).

             4. Then create an execjob_launch that prunes back the job's
                exec_vnode assignment back to satisfying the original 3-node
                select spec, choosing only healthy nodes.

             5. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(B)+(C)

                b. The accounting log start record 'S' will reflect the
                   select request where additional chunks were added, while
                   the secondary start record 's' will reflect the assigned
                   resources after pruning the original select request via
                   the pbs.release_nodes(keep_select=...) call
                   inside execjob_launch hook.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body2)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body3)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1v5_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1v5_schedselect,
                                 'exec_host': self.job1v5_exec_host,
                                 'exec_vnode': self.job1v5_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nB, self.nBv0],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2, self.nBv1],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)

        self.match_vnode_status([self.nC], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nBv2, self.nBv3,
                                 self.nE, self.nEv0, self.nEv1, self.nEv2,
                                 self.nEv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1v5_exec_host))

        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1v5_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v5_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v5_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v5_exec_host_esc,
                                  self.job1v5_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1v5_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momB.hostname, self.momC.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momB.shortname, self.momC.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momB.hostname, self.momB.hostname, self.momB.shortname,
            self.momC.hostname, self.momC.hostname, self.momC.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    @timeout(400)
    def test_t9(self):
        """
        Test tolerating 'all' node failures at job startup and
             within the life of the job.

             1.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=all

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                chunk C.

             3. Have an execjob_begin hook that fails (causes rejection)
                when executed by mom managing vnodes in (B).

             4. Have an execjob_prologue hook that fails (causes rejection)
                when executed by mom managing vnodes in (C).

             5. Then create an execjob_launch that prunes back the job's
                exec_vnode assignment back to satisfying the original 3-node
                select spec, choosing only healthy nodes.

             6. Now kill -KILL mom host hostD.

             7. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(D)+(E)

                   since (B) and (C) contain vnodes from failed moms.

                b. Job continues to run even after nodeD goes down with
                   only an indication in mom_logs with the message:
                   im_eof, Premature end of message from addr n stream 4

        """
        # set this so as to not linger on delaying job kill.
        c = {'$max_poll_downtime': 10}
        self.momA.add_config(c)

        # instantiate queuejob hook, tolerate_node_failure is set to 'all'
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body2)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1_2')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'all',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'all',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nE, self.nEv0],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nC,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)
        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_prologue hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;prolo: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1, self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match(
                "Job;%s;launch: found vnode_list_fail[%s]" % (jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # temporarily suspend momD, simulating a failed mom host.
        self.momD.signal("-KILL")
        self.momA.log_match("im_eof, Premature end of message.+on stream 4",
                            n=10, max_attempts=30, interval=2, regexp=True)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 2 hostname
%s
""" % (jid, self.momA.hostname, self.momD.hostname, self.momE.hostname,
            self.fib37_value, self.fib37_value, self.momA.shortname,
            self.momE.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)
        self.momD.start()

    def test_t10(self):
        """
        Test tolerating node failures at job startup but also
             cause a failure on one of the nodes after the job has
             started.

             1.	Submit a job that has been submitted with a select
                spec of 2 super-chunks say (A) and (B), and 1 chunk
                of (C), along with place spec of "scatter",
                resulting in the following assignment:

                    exec_vnode = (A)+(B)+(C)

                and -Wtolerate_node_failures=all

             2. Have a queuejob hook that adds 1 extra node to each
                chunk (except the MS (first) chunk), resulting in the
                assignment:

                    exec_vnode = (A)+(B)+(D)+(C)+(E)

                where D mirrors super-chunk B specs while E mirrors
                chunk C.

             3. Have an execjob_begin hook that fails (causes rejection)
                when executed by mom managing vnodes in (B).

             4. Have an execjob_prologue hook that fails (causes rejection)
                when executed by mom managing vnodes in (C).

             5. Then create an execjob_launch that prunes back the job's
                exec_vnode assignment back to satisfying the original 3-node
                select spec, choosing only healthy nodes.

             6. Now kill -KILL mom host hostD.

             7. Result:

                a. This results in the following reassignment of chunks:

                   exec_vnode = (A)+(D)+(E)

                   since (B) and (C) contain vnodes from failed moms.

                b. Job eventually aborts after nodeD goes down with
                   an indication in mom_logs with the message:
                   "im_eof, lost communication with <host>"
                   "node EOF 1 (<host>)"
                   "kill_job"

        """
        # set this so as to not linger on delaying job kill.
        c = {'$max_poll_downtime': 10}
        self.momA.add_config(c)

        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1_3')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nE, self.nEv0],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nC,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)
        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_prologue hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;prolo: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1, self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # temporarily suspend momD, simulating a failed mom host.
        self.momD.signal("-KILL")

        self.momA.log_match(
            "Job;%s;im_eof, lost communication with %s.+killing job now" % (
                jid, self.nD), n=10, max_attempts=30, interval=2, regexp=True)

        self.momA.log_match("Job;%s;kill_job" % (jid,),
                            n=10, max_attempts=60, interval=2)
        self.momD.start()

    def test_t11(self):
        """
        Test: tolerating node failures at job startup with
              job having an ncpus=0 assignment. This ensures
              the hooks will have the info for the ncpus=0 chunks
              in pbs.event().vnode_list[].
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job2')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 9,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job2_iselect,
                                 'Resource_List.site': self.job2_oselect,
                                 'Resource_List.place': self.job2_place,
                                 'schedselect': self.job2_ischedselect},
                           max_attempts=10, id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 6,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job2_select,
                                 'Resource_List.place': self.job2_place,
                                 'schedselect': self.job2_schedselect,
                                 'exec_host': self.job2_exec_host,
                                 'exec_vnode': self.job2_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nE, self.nEv0],
                                'free', jobs_assn1, 0, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nC,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 6,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 6,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job2_exec_host_nfile))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)
        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_prologue hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;prolo: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1, self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match(
                "Job;%s;launch: found vnode_list_fail[%s]" % (jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job2_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job2_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job2_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job2_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job2_iexec_host_esc,
                                  self.job2_iexec_vnode_esc, "10gb", 9, 5,
                                  self.job2_place,
                                  self.job2_isel_esc)

        self.match_accounting_log('s', jid, self.job2_exec_host_esc,
                                  self.job2_exec_vnode_esc,
                                  "6gb", 6, 3,
                                  self.job2_place,
                                  self.job2_sel_esc)

    def test_t12(self):
        """
        Test: tolerating node failures at job startup with
              extra resources requested such as mpiprocs and
              ompthtreads which would affect content of $PBS_NODEFILE.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job3')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job3_iselect,
                                 'Resource_List.site': self.job3_oselect,
                                 'Resource_List.place': self.job3_place,
                                 'schedselect': self.job3_ischedselect},
                           max_attempts=10, id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job3_select,
                                 'Resource_List.place': self.job3_place,
                                 'schedselect': self.job3_schedselect,
                                 'exec_host': self.job3_exec_host,
                                 'exec_vnode': self.job3_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nE, self.nEv0],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nC,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job3_exec_host,
                                              self.job3_schedselect))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)
        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_prologue hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;prolo: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1, self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job3_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job3_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job3_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job3_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job3_iexec_host_esc,
                                  self.job3_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job3_place,
                                  self.job3_isel_esc)

        self.match_accounting_log('s', jid, self.job3_exec_host_esc,
                                  self.job3_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job3_place,
                                  self.job3_sel_esc)

    def test_t13(self):
        """
        Test: pbs.event().job.select.increment_chunks() method.
        """
        # instantiate queuejob hook
        hook_body = """
import pbs
e=pbs.event()
sel=pbs.select("ncpus=3:mem=1gb+1:ncpus=2:mem=2gb+2:ncpus=1:mem=3gb")
inp=2
isel=sel.increment_chunks(inp)
pbs.logmsg(pbs.LOG_DEBUG, "sel=%s" % (sel,))
pbs.logmsg(pbs.LOG_DEBUG, "sel.increment_chunks(%d)=%s" % (inp,isel))
inp="3"
isel=sel.increment_chunks(inp)
pbs.logmsg(pbs.LOG_DEBUG, "sel.increment_chunks(%s)=%s" % (inp,isel))
inp="23.5%"
isel=sel.increment_chunks(inp)
pbs.logmsg(pbs.LOG_DEBUG, "sel.increment_chunks(%s)=%s" % (inp,isel))
inp={0: 0, 1: 4, 2: "50%"}
isel=sel.increment_chunks(inp)
pbs.logmsg(pbs.LOG_DEBUG, "sel.increment_chunks(%s)=%s" % (inp,isel))
sel=pbs.select("5:ncpus=3:mem=1gb+1:ncpus=2:mem=2gb+2:ncpus=1:mem=3gb")
pbs.logmsg(pbs.LOG_DEBUG, "sel=%s" % (sel,))
inp={0: "50%", 1: "50%", 2: "50%"}
isel=sel.increment_chunks(inp)
pbs.logmsg(pbs.LOG_DEBUG, "sel.increment_chunks(%s)=%s" % (inp,isel))
"""
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j1 = Job(TEST_USER)
        j1.set_sleep_time(10)
        self.server.submit(j1)

        # Verify server_logs
        self.server.log_match(
            "sel=ncpus=3:mem=1gb+1:ncpus=2:mem=2gb+2:ncpus=1:mem=3gb", n=10)

        self.server.log_match(
            "sel.increment_chunks(2)=1:ncpus=3:mem=1gb+" +
            "3:ncpus=2:mem=2gb+4:ncpus=1:mem=3gb", n=10)

        self.server.log_match(
            "sel.increment_chunks(3)=1:ncpus=3:mem=1gb+" +
            "4:ncpus=2:mem=2gb+5:ncpus=1:mem=3gb", n=10)

        self.server.log_match(
            "sel.increment_chunks(23.5%)=1:ncpus=3:mem=1gb+" +
            "2:ncpus=2:mem=2gb+3:ncpus=1:mem=3gb", n=10)

        self.server.log_match(
            "sel.increment_chunks({0: 0, 1: 4, 2: \'50%\'})=1:ncpus=3:" +
            "mem=1gb+5:ncpus=2:mem=2gb+3:ncpus=1:mem=3gb", n=10)

        self.server.log_match(
            "sel=5:ncpus=3:mem=1gb+1:ncpus=2:mem=2gb+2:ncpus=1:mem=3gb",
            n=10)

        self.server.log_match(
            "sel.increment_chunks({0: \'50%\', 1: \'50%\', 2: \'50%\'})=" +
            "7:ncpus=3:mem=1gb+2:ncpus=2:mem=2gb+3:ncpus=1:mem=3gb", n=10)

    def test_t14(self):
        """
        Test: tolerating job_start of no node failures,
              but pruning job's assigned nodes to satisfy the original
              select spec + 1 additional node.
              Basically, given an original spec requiring
              3 nodes, and a queuejob hook has added 2 more nodes,
              resulting in a new assignment:
                   exec_vnode=(A)+(B)+(C)+(D)+(E) where
              (C) mirrors (B) and satisfy the second chunk, and (E)
              mirrors (D) and satisfy the third chunk.
              Now pruning the assigned nodes to need 4 nodes, would
              result in:
                   exec_vnode=(A)+(B)+(D)+(e1)
              where (E) is a super-chunk of the form (e1+e2) and only
              need 'e1' part.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_launch hook
        hook_body = """
import pbs
e=pbs.event()

if 'PBS_NODEFILE' not in e.env:
    e.accept()

pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
if e.job.in_ms_mom():
    new_jsel = e.job.Resource_List["site"] + "+ncpus=1:mem=1gb"
    pj = e.job.release_nodes(keep_select=new_jsel)
    pbs.logmsg(pbs.LOG_DEBUG, "release_nodes(keep_select=%s)" % (new_jsel,))
    if pj != None:
        pbs.logjobmsg(e.job.id, "launch: job.exec_vnode=%s" % (pj.exec_vnode,))
        pbs.logjobmsg(e.job.id, "launch: job.exec_host=%s" % (pj.exec_host,))
        pbs.logjobmsg(e.job.id,
                      "launch: job.schedselect=%s" % (pj.schedselect,))
    else:
        e.job.delete()
        msg = "unsuccessful at LAUNCH"
        e.reject("unsuccessful at LAUNCH")
"""
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1_4')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '7gb',
                                 'Resource_List.ncpus': 9,
                                 'Resource_List.nodect': 4,
                                 'Resource_List.select': self.job1v6_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1v6_schedselect,
                                 'exec_host': self.job1v6_exec_host,
                                 'exec_vnode': self.job1v6_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nB, self.nBv0, self.nE],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2, self.nBv1],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)

        self.match_vnode_status([self.nC], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nBv2, self.nBv3,
                                 self.nEv0, self.nEv1, self.nEv2,
                                 self.nEv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 9,
                                    'resources_assigned.mem': '7340032kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 9,
                                   'resources_assigned.mem': '7340032kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1v6_exec_host))

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1v6_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v6_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v6_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v6_exec_host_esc,
                                  self.job1v6_exec_vnode_esc,
                                  "7gb", 9, 4,
                                  self.job1_place,
                                  self.job1v6_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
pbsdsh -n 3 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
pbsdsh -n 3 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momB.hostname, self.momC.hostname,
            self.momE.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.fib37_value,
            self.momA.shortname, self.momB.shortname, self.momC.shortname,
            self.momE.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momB.hostname, self.momB.hostname, self.momB.shortname,
            self.momC.hostname, self.momC.hostname, self.momC.shortname,
            self.momE.hostname, self.momE.hostname, self.momE.shortname)

        self.logger.info("expected out=%s" % (expected_out,))
        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()
            self.logger.info("job_out=%s" % (job_out,))

        self.assertEquals(job_out, expected_out)

    def test_t15(self):
        """
        Test: tolerating job_start of no node failures,
              but pruning job's assigned nodes to satisfy the original
              select spec minus 1 node, except one of the chunks is.
              unsatisfiable. This time, the action pbs.event().delete()
              action is specified on a failure to prune the job.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_launch hook
        hook_body = """
import pbs
e=pbs.event()

if 'PBS_NODEFILE' not in e.env:
    e.accept()

pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")

for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
if e.job.in_ms_mom():
    new_jsel ="ncpus=3:mem=2gb+ncpus=5:mem=3gb"
    pj = e.job.release_nodes(keep_select=new_jsel)
    pbs.logmsg(pbs.LOG_DEBUG, "release_nodes(keep_select=%s)" % (new_jsel,))
    if pj != None:
        pbs.logjobmsg(e.job.id, "launch: job.exec_vnode=%s" % (pj.exec_vnode,))
        pbs.logjobmsg(e.job.id, "launch: job.exec_host=%s" % (pj.exec_host,))
        pbs.logjobmsg(e.job.id,
                      "launch: job.schedselect=%s" % (pj.schedselect,))
    else:
        e.job.delete()
        msg = "unsuccessful at LAUNCH"
        e.reject("unsuccessful at LAUNCH")
"""
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1_4')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.momA.log_match("Job;%s;could not satisfy select chunk" % (jid,),
                            n=10, max_attempts=60, interval=2)

        self.momA.log_match("Job;%s;NEED chunks for keep_select" % (jid,),
                            n=10)

        self.momA.log_match(
            "Job;%s;HAVE chunks from job's exec_vnode" % (jid,), n=10)

        self.momA.log_match("execjob_launch request rejected by 'launch'",
                            n=10)

        errmsg = "unsuccessful at LAUNCH"
        self.momA.log_match("Job;%s;%s" % (jid, errmsg,), n=10)

        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

    def test_t16(self):
        """
        Test: tolerating node failures at job startup with
              a job submitted with -l place="scatter:excl".
              Like jobs submitted with only "-l place=scatter"
              except the vnodes assigned would have a
             "job-exclusive" state.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing begin")
localnode=pbs.get_local_nodename()
if not e.job.in_ms_mom() and (localnode == '%s'):
    x
""" % (self.nB,)
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job4')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job4_iselect,
                                 'Resource_List.site': self.job4_oselect,
                                 'Resource_List.place': self.job4_place,
                                 'schedselect': self.job4_ischedselect},
                           max_attempts=10, id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job4_select,
                                 'Resource_List.place': self.job4_place,
                                 'schedselect': self.job4_schedselect,
                                 'exec_host': self.job4_exec_host,
                                 'exec_vnode': self.job4_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1],
                                'job-exclusive', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nE, self.nEv0],
                                'job-exclusive', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'job-exclusive', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nC,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job4_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+" % (jid, self.hostC) +
            "could not IM_EXEC_PROLOGUE", n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+" % (jid, self.hostC) +
            "as job is tolerant of node failures", n=10, regexp=True)
        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_prologue hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;prolo: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1, self.nC]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job4_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job4_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job4_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job4_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job4_iexec_host_esc,
                                  self.job4_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job4_place,
                                  self.job4_isel_esc)

        self.match_accounting_log('s', jid, self.job4_exec_host_esc,
                                  self.job4_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job4_place,
                                  self.job4_sel_esc)

    def test_t17(self):
        """
        Test: tolerating 1 node failure at job startup with
              a job submitted with -l place="free".
              Like jobs submitted with only "-l place=scatter"
              except some vnodes from the same mom would get
              allocated to satisfy different chunks.
              This test breaks apart one of the multi-chunks of
              the form (b1+b2+b3) so that upon reassignment,
              (b1+b2) is used.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body4)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body3)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body2)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job5')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job5_iselect,
                                 'Resource_List.site': self.job5_oselect,
                                 'Resource_List.place': self.job5_place,
                                 'schedselect': self.job5_ischedselect},
                           max_attempts=10, id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job5_select,
                                 'Resource_List.place': self.job5_place,
                                 'schedselect': self.job5_schedselect,
                                 'exec_host': self.job5_exec_host,
                                 'exec_vnode': self.job5_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=60)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status(
            [self.nAv0, self.nAv1, self.nB, self.nBv0],
            'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2, self.nBv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        # due to free placement, job appears twice as it's been allocated
        # twice, one for mem only and the other for ncpus
        jobs_assn2 = "%s/0, %s/0" % (jid, jid)
        self.match_vnode_status([self.nBv1],
                                'job-busy', jobs_assn2, 1, '1048576kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nC, self.nD,
                                 self.nD, self.nE, self.nEv0, self.nEv1,
                                 self.nEv2, self.nEv3, self.nBv3], 'free')

        # Check server/queue counts.
        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id='workq', attrop=PTL_AND)
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job5_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostD), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostD) +
            "is tolerant of node failures",
            regexp=True, n=10)

        # Check vnode_list[] parameter in execjob_prologue hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nD]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job5_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job5_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job5_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job5_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job5_iexec_host_esc,
                                  self.job5_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job5_place,
                                  self.job5_isel_esc)

        self.match_accounting_log('s', jid, self.job5_exec_host_esc,
                                  self.job5_exec_vnode_esc,
                                  "5gb", 7, 3,
                                  self.job5_place,
                                  self.job5_sel_esc)

    def test_t18(self):
        """
        Test: having a node failure tolerant job waiting for healthy nodes
              to get rerun (i.e. qrerun). Upon qrerun, job should get
              killed, requeued, and restarted.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        jid = self.create_and_submit_job('job1')
        # job's substate is 41 (PRERUN) since it would be waiting for
        # healthy nodes being a node failure tolerant job.
        # With no prologue hook, MS would wait the default 30
        # seconds for healthy nodes.
        self.server.expect(JOB, {'job_state': 'R',
                                 'substate': 41,
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'exec_host': self.job1_iexec_host,
                                 'exec_vnode': self.job1_iexec_vnode,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1, self.nB, self.nBv0,
                                 self.nE, self.nEv0],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2, self.nBv1],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.nC], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nBv2, self.nBv3,
                                 self.nEv1, self.nEv2, self.nEv3], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 13,
                                    'resources_assigned.mem': '10485760'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 13,
                                   'resources_assigned.mem': '10485760'},
                           id='workq', attrop=PTL_AND)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.rerunjob(jid)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        self.match_vnode_status([self.nA, self.nAv0, self.nAv1, self.nAv2,
                                 self.nAv3,
                                 self.nB, self.nBv0, self.nBv1, self.nBv2,
                                 self.nBv3, self.nC, self.nD, self.nE,
                                 self.nEv0, self.nEv1, self.nEv2,
                                 self.nEv3], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 0,
                                    'resources_assigned.mem': '0kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 0,
                                   'resources_assigned.mem': '0kb'},
                           id='workq', attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Now job should start running again
        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1v2_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1v2_schedselect,
                                 'exec_host': self.job1v2_exec_host,
                                 'exec_vnode': self.job1v2_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=70)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.nAv2],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.nC], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        jobs_assn3 = "%s/0, %s/1, %s/2" % (jid, jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn3,
                                3, '2097152kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nB, self.nBv0,
                                 self.nBv1, self.nBv2, self.nBv3, self.nE,
                                 self.nEv0, self.nEv1, self.nEv2,
                                 self.nEv3], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1v2_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1v2_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v2_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v2_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v2_exec_host_esc,
                                  self.job1v2_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1v2_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momD.hostname, self.momC.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momD.shortname, self.momC.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname,
            self.momC.hostname, self.momC.hostname, self.momC.shortname)

        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()

        self.assertEquals(job_out, expected_out)

        # Re-check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Re-check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nB, self.nBv0, self.nBv1]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1v2_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v2_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v2_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v2_exec_host_esc,
                                  self.job1v2_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1v2_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momD.hostname, self.momC.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momD.shortname, self.momC.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname,
            self.momC.hostname, self.momC.hostname, self.momC.shortname)

        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()

        self.assertEquals(job_out, expected_out)

    def test_t19(self):
        """
        Test: having a node tolerant job waiting for healthy nodes
              to get issued a request to release nodes. The call
              to pbs_release_nodes would fail given that the job
              is not fully running yet, still figuring out which nodes
              assigned are deemed good.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        jid = self.create_and_submit_job('job1')
        # job's substate is 41 (PRERUN) since it would be waiting for
        # healthy nodes being a node failure tolerant job
        self.server.expect(JOB, {'job_state': 'R',
                                 'substate': 41,
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'exec_host': self.job1_iexec_host,
                                 'exec_vnode': self.job1_iexec_vnode,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                jid, self.hostB), n=10, regexp=True)

        self.momA.log_match(
            "Job;%s;ignoring error from %s.+as job " % (jid, self.hostB) +
            "is tolerant of node failures",
            regexp=True, n=10)

        # Run pbs_release_nodes on a job whose state is running but
        # substate is under PRERUN
        pbs_release_nodes_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_release_nodes')
        cmd = [pbs_release_nodes_cmd, '-j', jid, '-a']

        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: Request invalid for state of job'))

    def test_t20(self):
        """
        Test: node failure tolerant job array, with multiple subjobs
              starting at the same time, and job's assigned resources
              are pruned to match up to the original select spec using
              an execjob_prologue hook this time.
        """
        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_begin hook
        hook_event = "execjob_begin"
        hook_name = "begin"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.begin_hook_body5)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body4)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('jobA')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 5,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.jobA_iselect,
                                 'Resource_List.site': self.jobA_oselect,
                                 'Resource_List.place': self.jobA_place,
                                 'schedselect': self.jobA_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.server.expect(JOB, {'job_state': 'B',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 5,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.jobA_iselect,
                                 'Resource_List.site': self.jobA_oselect,
                                 'Resource_List.place': self.jobA_place,
                                 'schedselect': self.jobA_ischedselect},
                           id=jid, attrop=PTL_AND)

        self.server.expect(JOB, {'job_state=R': 3}, extend='t')

        for idx in range(1, 4):
            sjid = create_subjob_id(jid, idx)
            if idx == 1:
                iexec_host_esc = self.jobA_iexec_host1_esc
                iexec_vnode = self.jobA_iexec_vnode1
                iexec_vnode_esc = self.jobA_iexec_vnode1_esc
                exec_host = self.jobA_exec_host1
                exec_host_esc = self.jobA_exec_host1_esc
                exec_vnode = self.jobA_exec_vnode1
                exec_vnode_esc = self.jobA_exec_vnode1_esc
                vnode_list = [self.nAv0, self.nB, self.nC,
                              self.nD, self.nE]
            elif idx == 2:
                iexec_host_esc = self.jobA_iexec_host2_esc
                iexec_vnode = self.jobA_iexec_vnode2
                iexec_vnode_esc = self.jobA_iexec_vnode2_esc
                exec_host = self.jobA_exec_host2
                exec_host_esc = self.jobA_exec_host2_esc
                exec_vnode = self.jobA_exec_vnode2
                exec_vnode_esc = self.jobA_exec_vnode2_esc
                vnode_list = [self.nAv1, self.nBv0, self.nC,
                              self.nD, self.nEv0]
            elif idx == 3:
                iexec_host_esc = self.jobA_iexec_host3_esc
                iexec_vnode = self.jobA_iexec_vnode3
                iexec_vnode_esc = self.jobA_iexec_vnode3_esc
                exec_host = self.jobA_exec_host3
                exec_host_esc = self.jobA_exec_host3_esc
                exec_vnode = self.jobA_exec_vnode3
                exec_vnode_esc = self.jobA_exec_vnode3_esc
                vnode_list = [self.nAv2, self.nBv1, self.nC,
                              self.nD, self.nE]

            self.server.expect(JOB, {'job_state': 'R',
                                     'substate': 41,
                                     'tolerate_node_failures': 'job_start',
                                     'Resource_List.mem': '3gb',
                                     'Resource_List.ncpus': 3,
                                     'Resource_List.nodect': 3,
                                     'exec_host': exec_host,
                                     'exec_vnode': exec_vnode,
                                     'Resource_List.select': self.jobA_select,
                                     'Resource_List.site': self.jobA_oselect,
                                     'Resource_List.place': self.jobA_place,
                                     'schedselect': self.jobA_schedselect},
                               id=sjid, attrop=PTL_AND)

            # Verify mom_logs
            sjid_esc = sjid.replace(
                "[", "\[").replace("]", "\]").replace("(", "\(").replace(
                ")", "\)").replace("+", "\+")
            self.momA.log_match(
                "Job;%s;job_start_error.+from node %s.+could not JOIN_JOB" % (
                    sjid_esc, self.hostC), n=10, regexp=True)
            self.momA.log_match(
                "Job;%s;ignoring error from %s.+as job " % (
                    sjid_esc, self.hostC) + "is tolerant of node failures",
                regexp=True, n=10)

            for vn in vnode_list:
                self.momA.log_match("Job;%s;prolo: found vnode_list[%s]" % (
                                    sjid, vn), n=10)

            vnode_list_fail = [self.nC]
            for vn in vnode_list_fail:
                self.momA.log_match(
                    "Job;%s;prolo: found vnode_list_fail[%s]" % (
                        sjid, vn), n=10)
            # Check result of pbs.event().job.release_nodes(keep_select)
            # call
            self.momA.log_match("Job;%s;prolo: job.exec_vnode=%s" % (
                sjid, exec_vnode), n=10)
            self.momA.log_match("Job;%s;prolo: job.schedselect=%s" % (
                sjid, self.jobA_schedselect), n=10)
            self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
                sjid, iexec_vnode), n=10)
            self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
                sjid, exec_vnode), n=10)
            # Check accounting_logs
            self.match_accounting_log('S', sjid_esc, iexec_host_esc,
                                      iexec_vnode_esc, "5gb", 5, 5,
                                      self.jobA_place,
                                      self.jobA_isel_esc)
            self.match_accounting_log('s', sjid_esc, exec_host_esc,
                                      exec_vnode_esc,
                                      "3gb", 3, 3,
                                      self.jobA_place,
                                      self.jobA_sel_esc)

    @timeout(400)
    def test_t21(self):
        """
        Test: radio silent moms causing the primary mom to not get
              any acks from the sister moms executing prologue hooks.
              After some 'job_launch_delay' time has passed, primary
              mom will consider node hosts that have not acknowledged
              the prologue hook execution as failed hosts, and will
              not use their vnodes in the pruning of jobs.
        """
        job_launch_delay = 120
        c = {'$job_launch_delay': job_launch_delay}
        self.momA.add_config(c)

        # instantiate queuejob hook
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_prologue hook
        hook_event = "execjob_prologue"
        hook_name = "prolo"
        a = {'event': hook_event, 'enabled': 'true', 'alarm': 60}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body5)

        # instantiate execjob_launch hook
        hook_event = "execjob_launch"
        hook_name = "launch"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # First, turn off scheduling
        a = {'scheduling': 'false'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        jid = self.create_and_submit_job('job1')
        # Job gets queued and reflects the incremented values from queuejob
        # hook
        self.server.expect(JOB, {'job_state': 'Q',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '10gb',
                                 'Resource_List.ncpus': 13,
                                 'Resource_List.nodect': 5,
                                 'Resource_List.select': self.job1_iselect,
                                 'Resource_List.site': self.job1_oselect,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_ischedselect},
                           id=jid, attrop=PTL_AND)

        a = {'scheduling': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.momE.log_match(
            "Job;%s;sleeping for 30 secs" % (jid, ), n=10)

        # temporarily suspend momE, simulating a radio silent mom.
        self.momE.signal("-STOP")

        self.momC.log_match(
            "Job;%s;sleeping for 30 secs" % (jid, ), n=10)

        # temporarily suspend momC, simulating a radio silent mom.
        self.momC.signal("-STOP")

        # sleep as long as the time primary mom waits for all
        # prologue hook acknowledgement from the sister moms
        self.logger.info("sleeping for %d secs waiting for healthy nodes" % (
                         job_launch_delay,))
        time.sleep(job_launch_delay)

        # Job eventually launches reflecting the pruned back values
        # to the original select spec
        # There's a max_attempts=60 for it would take up to 60 seconds
        # for primary mom to wait for the sisters to join
        # (default $sister_join_job_alarm of 30 seconds) and to wait for
        # sisters to execjob_prologue hooks (default $job_launch_delay
        # value of 30 seconds)

        self.server.expect(JOB, {'job_state': 'R',
                                 'tolerate_node_failures': 'job_start',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1v4_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1v4_schedselect,
                                 'exec_host': self.job1v4_exec_host,
                                 'exec_vnode': self.job1v4_exec_vnode},
                           id=jid, interval=1, attrop=PTL_AND, max_attempts=70)

        thisjob = self.server.status(JOB, id=jid)
        if thisjob:
            job_output_file = thisjob[0]['Output_Path'].split(':')[1]

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.nAv0, self.nAv1, self.nB, self.nBv0],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.nD], 'free', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.nAv2, self.nBv1],
                                'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.nA, self.nAv3, self.nBv2, self.nBv3,
                                 self.nC, self.nD, self.nEv1, self.nEv2,
                                 self.nEv3, self.nE, self.nEv0], 'free')

        # check server/queue counts
        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'},
                           attrop=PTL_AND)
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id='workq', attrop=PTL_AND)

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1v4_exec_host))

        # Check vnode_list[] parameter in execjob_launch hook
        vnode_list = [self.nAv0, self.nAv1, self.nAv2,
                      self.nB, self.nBv0, self.nBv1,
                      self.nC, self.nD, self.nE, self.nEv0]
        for vn in vnode_list:
            self.momA.log_match("Job;%s;launch: found vnode_list[%s]" % (
                                jid, vn), n=10)

        # Check vnode_list_fail[] parameter in execjob_launch hook
        vnode_list_fail = [self.nC, self.nE, self.nEv0]
        for vn in vnode_list_fail:
            self.momA.log_match("Job;%s;launch: found vnode_list_fail[%s]" % (
                                jid, vn), n=10)

        # Check result of pbs.event().job.release_nodes(keep_select) call
        self.momA.log_match("Job;%s;launch: job.exec_vnode=%s" % (
            jid, self.job1v4_exec_vnode), n=10)

        self.momA.log_match("Job;%s;launch: job.schedselect=%s" % (
            jid, self.job1v4_schedselect), n=10)

        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, self.job1_iexec_vnode), n=10)

        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, self.job1v4_exec_vnode), n=10)

        # Check accounting_logs
        self.match_accounting_log('S', jid, self.job1_iexec_host_esc,
                                  self.job1_iexec_vnode_esc, "10gb", 13, 5,
                                  self.job1_place,
                                  self.job1_isel_esc)

        self.match_accounting_log('s', jid, self.job1v4_exec_host_esc,
                                  self.job1v4_exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1v4_sel_esc)

        self.momA.log_match("Job;%s;task.+started, hostname" % (jid,),
                            n=10, max_attempts=60, interval=2, regexp=True)

        self.momA.log_match("Job;%s;copy file request received" % (jid,),
                            n=10, max_attempts=10, interval=2)

        # validate output
        expected_out = """/var/spool/pbs/aux/%s
%s
%s
%s
FIB TESTS
pbsdsh -n 1 fib 37
%d
pbsdsh -n 2 fib 37
%d
fib 37
%d
HOSTNAME TESTS
pbsdsh -n 0 hostname
%s
pbsdsh -n 1 hostname
%s
pbsdsh -n 2 hostname
%s
PBS_NODEFILE tests
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
HOST=%s
pbs_tmrsh %s hostname
%s
""" % (jid, self.momA.hostname, self.momB.hostname, self.momD.hostname,
            self.fib37_value, self.fib37_value, self.fib37_value,
            self.momA.shortname, self.momB.shortname, self.momD.shortname,
            self.momA.hostname, self.momA.hostname, self.momA.shortname,
            self.momB.hostname, self.momB.hostname, self.momB.shortname,
            self.momD.hostname, self.momD.hostname, self.momD.shortname)

        job_out = ""
        with open(job_output_file, 'r') as fd:
            job_out = fd.read()

        self.assertEquals(job_out, expected_out)

# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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


@requirements(num_moms=3)
class TestPbsNodeRampDown(TestFunctional):

    """
    This tests the Node Rampdown Feature,
    where while a job is running, nodes/resources
    assigned by non-mother superior can be released.

    Custom parameters:
    moms: colon-separated hostnames of three MoMs
    """

    def transform_select(self, select):
        """
        Takes a select substring:
            "<res1>=<val1>:<res2>=<val2>...:<resN>=<valN>"
        and transform it so that if any of the resource
        (res1, res2,...,resN) matches 'mem', and
        the corresponding value has a suffix of 'gb',
        then convert it too 'kb' value. Also,
        this will attach a "1:' to the returned select
        substring.
        Ex:
             % str = "ncpus=7:mem=2gb:ompthreads=3"
             % transform_select(str)
             1:ompthreads=3:mem=2097152kb:ncpus=7
        """
        sel_list = select.split(':')
        mystr = "1:"
        for index in range(len(sel_list) - 1, -1, -1):
            if (index != len(sel_list) - 1):
                mystr += ":"
            nums = [s for s in sel_list[index] if s.isdigit()]
            key = sel_list[index].split('=')[0]
            if key == "mem":
                mystr += sel_list[index].\
                    replace(nums[0] + "gb",
                            str(int(nums[0]) * 1024 * 1024)) + "kb"
            else:
                mystr += sel_list[index]
        return mystr

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
            select_list = schedselect.split('+')

            for chunk in select_list:
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
                for k in range(int(mpiprocs[j])):
                    ehost1.append(h[0])
            else:
                ehost1.append(h[0])
            j += 1

        if ((ehost1 > ehost2) - (ehost1 < ehost2)) != 0:
            return False
        return True

    def check_stageout_file_size(self):
        """
        This Function will check that atleast 1gb of test.img
        file which is to be stagedout is created in 10 seconds
        """
        fpath = os.path.join(TEST_USER.home, "test.img")
        cmd = ['stat', '-c', '%s', fpath]
        fsize = 0
        for i in range(11):
            rc = self.du.run_cmd(hosts=self.hostA, cmd=cmd,
                                 runas=TEST_USER)
            if rc['rc'] == 0 and len(rc['out']) == 1:
                try:
                    fsize = int(rc['out'][0])
                except Exception:
                    pass
            # 1073741824 == 1Gb
            if fsize > 1073741824:
                break
            else:
                time.sleep(1)
        if fsize <= 1073741824:
            self.fail("Failed to create 1gb file at %s" % fpath)

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
        due to a release node request), 'E' (end of job record).
        """
        self.server.accounting_match(
            msg=".*%s;%s.*exec_host=%s.*" % (atype, jid, exec_host),
            regexp=True, n="ALL", starttime=self.stime)

        self.server.accounting_match(
            msg=".*%s;%s.*exec_vnode=%s.*" % (atype, jid, exec_vnode),
            regexp=True, n="ALL", starttime=self.stime)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.mem=%s.*" % (atype, jid, mem),
            regexp=True, n="ALL", starttime=self.stime)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.ncpus=%d.*" % (atype, jid, ncpus),
            regexp=True, n="ALL", starttime=self.stime)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.nodect=%d.*" % (atype, jid, nodect),
            regexp=True, n="ALL", starttime=self.stime)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.place=%s.*" % (atype, jid, place),
            regexp=True, n="ALL", starttime=self.stime)

        self.server.accounting_match(
            msg=".*%s;%s.*Resource_List\.select=%s.*" % (atype, jid, select),
            regexp=True, n="ALL", starttime=self.stime)

        if atype != 'c':
            self.server.accounting_match(
                msg=".*%s;%s.*resources_used\..*" % (atype, jid),
                regexp=True, n="ALL", starttime=self.stime)

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

    def create_and_submit_job(self, job_type, attribs={}):
        """
        create the job object and submit it to the server
        based on 'job_type' and attributes list 'attribs'.
        """
        retjob = Job(TEST_USER, attrs=attribs)

        if job_type == 'job1':
            retjob.create_script(self.script['job1'])
        elif job_type == 'job1_1':
            retjob.create_script(self.script['job1_1'])
        elif job_type == 'job1_2':
            retjob.create_script(self.script['job1_2'])
        elif job_type == 'job1_3':
            retjob.create_script(self.script['job1_3'])
        elif job_type == 'job1_5':
            retjob.create_script(self.script['job1_5'])
        elif job_type == 'job1_6':
            retjob.create_script(self.script['job1_6'])
        elif job_type == 'job1_extra_res':
            retjob.create_script(self.script['job1_extra_res'])
        elif job_type == 'job2':
            retjob.create_script(self.script['job2'])
        elif job_type == 'job3':
            retjob.create_script(self.script['job3'])
        elif job_type == 'job5':
            retjob.create_script(self.script['job5'])
        elif job_type == 'job11':
            retjob.create_script(self.script['job11'])
        elif job_type == 'job11x':
            retjob.create_script(self.script['job11x'])
        elif job_type == 'job12':
            retjob.create_script(self.script['job12'])
        elif job_type == 'job13':
            retjob.create_script(self.script['job13'])
        elif job_type == 'jobA':
            retjob.create_script(self.script['jobA'])

        return self.server.submit(retjob)

    def setUp(self):

        if len(self.moms) != 3:
            self.skip_test(reason="need 3 mom hosts: -p moms=<m1>:<m2>:<m3>")

        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

        self.server.cleanup_jobs()

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momC = self.moms.values()[2]

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
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostC)

        a = {'state': 'free', 'resources_available.ncpus': (GE, 1)}
        self.server.expect(VNODE, {'state=free': 11}, count=True,
                           interval=2)

        # Various node names
        self.n0 = self.hostA
        self.n1 = '%s[0]' % (self.hostA,)
        self.n2 = '%s[1]' % (self.hostA,)
        self.n3 = '%s[2]' % (self.hostA,)
        self.n4 = self.hostB
        self.n5 = '%s[0]' % (self.hostB,)
        self.n6 = '%s[1]' % (self.hostB,)
        self.n7 = self.hostC
        self.n8 = '%s[3]' % (self.hostA,)
        self.n9 = '%s[2]' % (self.hostB,)
        self.n10 = '%s[3]' % (self.hostB,)

        SLEEP_CMD = self.mom.sleep_cmd

        self.pbs_release_nodes_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_release_nodes')

        FIB40 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', '') + \
            'pbs_python -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint(fib(40))\\\")"'

        FIB45 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', '') + \
            'pbs_python -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint(fib(45))\\\")"'

        FIB50 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', '') + \
            'pbs_python -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint(fib(50))\\\")"'

        FIB400 = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', '') + \
            'pbs_python -c "exec(\\\"def fib(i):\\n if i < 2:\\n  \
return i\\n return fib(i-1) + fib(i-2)\\n\\nprint(fib(400))\\\")"'

        # job submission arguments
        self.script = {}
        self.job1_select = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=2:mem=2gb"
        self.job1_place = "scatter"

        # expected values upon successful job submission
        self.job1_schedselect = "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+" + \
            "1:ncpus=2:mem=2gb"
        self.job1_exec_host = "%s/0*0+%s/0*0+%s/0*2" % (
            self.n0, self.n4, self.n7)
        self.job1_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n1,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n2,) + \
            "%s:ncpus=1)+" % (self.n3) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n4,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,) + \
            "%s:ncpus=1)+" % (self.n6,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.n7,)

        self.job1_sel_esc = self.job1_select.replace("+", "\+")
        self.job1_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        self.job1_exec_vnode_esc = self.job1_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace("(", "\(").replace(
            ")", "\)").replace("+", "\+")
        self.job1_newsel = self.transform_select(self.job1_select.split(
            '+')[0])
        self.job1_new_exec_host = self.job1_exec_host.split('+')[0]
        self.job1_new_exec_vnode = self.job1_exec_vnode.split(')')[0] + ')'
        self.job1_new_exec_vnode_esc = \
            self.job1_new_exec_vnode.replace("[", "\[").replace(
                "]", "\]").replace("(", "\(").replace(")", "\)").replace(
                "+", "\+")

        self.script['job1'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            "#PBS -W stageout=test.img@%s:test.img\n" % (self.n4,) + \
            "#PBS -W release_nodes_on_stageout=true\n" + \
            "dd if=/dev/zero of=test.img count=1024 bs=2097152\n" + \
            "pbsdsh -n 1 -- %s\n" % (FIB40,) + \
            "pbsdsh -n 2 -- %s\n" % (FIB40,) + \
            "%s\n" % (FIB400,)

        self.script['job1_1'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            "#PBS -W stageout=test.img@%s:test.img\n" % (self.n4,) + \
            "#PBS -W release_nodes_on_stageout=false\n" + \
            "dd if=/dev/zero of=test.img count=1024 bs=2097152\n" + \
            "pbsdsh -n 1 -- %s\n" % (FIB40,) + \
            "pbsdsh -n 2 -- %s\n" % (FIB40,) + \
            "%s\n" % (FIB400,)

        self.script['job1_2'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            "#PBS -W stageout=test.img@%s:test.img\n" % (self.n4,) + \
            "dd if=/dev/zero of=test.img count=1024 bs=2097152\n" + \
            "pbsdsh -n 1 -- %s\n" % (FIB40,) + \
            "pbsdsh -n 2 -- %s\n" % (FIB40,) + \
            "%s\n" % (FIB400,)

        self.script['job1_3'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            SLEEP_CMD + " 30\n" + \
            "pbs_release_nodes -a\n" + \
            "%s\n" % (FIB50,)

        self.script['job1_5'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            "pbsdsh -n 1 -- %s &\n" % (FIB45,) + \
            "pbsdsh -n 2 -- %s &\n" % (FIB45,) + \
            "%s\n" % (FIB400,)

        self.script['jobA'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            "#PBS -J 1-5\n"\
            "pbsdsh -n 1 -- %s &\n" % (FIB45,) + \
            "pbsdsh -n 2 -- %s &\n" % (FIB45,) + \
            "%s\n" % (FIB45,)

        self.script['job1_6'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            SLEEP_CMD + " 30\n" + \
            self.pbs_release_nodes_cmd + " " + self.n4 + "\n" + \
            "%s\n" % (FIB50,)

        self.job1_extra_res_select = \
            "ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+" + \
            "ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+" + \
            "ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"
        self.job1_extra_res_place = "scatter"
        self.job1_extra_res_schedselect = \
            "1:ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+" + \
            "1:ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+" + \
            "1:ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"
        self.job1_extra_res_exec_host = "%s/0*0+%s/0*0+%s/0*2" % (
            self.n0, self.n4, self.n7)
        self.job1_extra_res_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n1,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n2,) + \
            "%s:ncpus=1)+" % (self.n3,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n4,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,) + \
            "%s:ncpus=1)+" % (self.n6,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.n7,)
        self.script['job1_extra_res'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job1_extra_res_select + "\n" + \
            "#PBS -l place=" + self.job1_extra_res_place + "\n" + \
            "pbsdsh -n 1 -- %s &\n" % (FIB40,) + \
            "pbsdsh -n 2 -- %s &\n" % (FIB40,) + \
            "%s\n" % (FIB50,)

        self.job2_select = "ncpus=1:mem=1gb+ncpus=4:mem=4gb+ncpus=2:mem=2gb"
        self.job2_place = "scatter"
        self.job2_schedselect = "1:ncpus=1:mem=1gb+1:ncpus=4:mem=4gb+" + \
            "1:ncpus=2:mem=2gb"
        self.job2_exec_host = "%s/1+%s/1*0+%s/1*2" % (
            self.n0, self.n4, self.n7)
        self.job2_exec_vnode = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.n8,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n4,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n9,) + \
            "%s:mem=1048576kb:ncpus=1)+" % (self.n10,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.n7,)

        self.job2_exec_vnode_var1 = \
            "(%s:ncpus=1:mem=1048576kb)+" % (self.n8,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n4,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n6,) + \
            "%s:mem=1048576kb:ncpus=1)+" % (self.n9,) + \
            "(%s:ncpus=2:mem=2097152kb)" % (self.n7,)

        self.script['job2'] = \
            "#PBS -l select=" + self.job2_select + "\n" + \
            "#PBS -l place=" + self.job2_place + "\n" + \
            SLEEP_CMD + " 60\n"

        self.script['job3'] = \
            "#PBS -l select=vnode=" + self.n4 + "+vnode=" + self.n0 + \
            ":mem=4mb\n" + SLEEP_CMD + " 30\n"

        self.script['job5'] = \
            "#PBS -l select=vnode=" + self.n0 + ":mem=4mb\n" + \
            SLEEP_CMD + " 300\n"

        self.job11x_select = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=1:mem=1gb"
        self.job11x_place = "scatter:excl"
        self.job11x_schedselect = "1:ncpus=3:mem=2gb+" + \
            "1:ncpus=3:mem=2gb+1:ncpus=1:mem=1gb"
        self.job11x_exec_host = "%s/0*0+%s/0*0+%s/0" % (
            self.n0, self.n4, self.n7)
        self.job11x_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n1,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n2,) + \
            "%s:ncpus=1)+" % (self.n3,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n4,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,) + \
            "%s:ncpus=1)+" % (self.n6,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.n7,)
        self.job11x_exec_vnode_match = \
            "\(.+:mem=1048576kb:ncpus=1\+" + \
            ".+:mem=1048576kb:ncpus=1\+" + \
            ".+:ncpus=1\)\+" + \
            "\(.+:mem=1048576kb:ncpus=1\+" + \
            ".+:mem=1048576kb:ncpus=1\+" + \
            ".+:ncpus=1\)\+" + \
            "\(.+:ncpus=1:mem=1048576kb\)"
        self.script['job11x'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job11x_select + "\n" + \
            "#PBS -l place=" + self.job11x_place + "\n" + \
            "pbsdsh -n 1 -- %s\n" % (FIB40,) + \
            "pbsdsh -n 2 -- %s\n" % (FIB40,) + \
            "%s\n" % (FIB50,)

        self.job11_select = "ncpus=3:mem=2gb+ncpus=3:mem=2gb+ncpus=1:mem=1gb"
        self.job11_place = "scatter"
        self.job11_schedselect = "1:ncpus=3:mem=2gb+1:ncpus=3:mem=2gb+" + \
            "1:ncpus=1:mem=1gb"
        self.job11_exec_host = "%s/0*0+%s/0*0+%s/0" % (
            self.n0, self.n4, self.n7)
        self.job11_exec_vnode = \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n1,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n2,) + \
            "%s:ncpus=1)+" % (self.n3,) + \
            "(%s:mem=1048576kb:ncpus=1+" % (self.n4,) + \
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,) + \
            "%s:ncpus=1)+" % (self.n6,) + \
            "(%s:ncpus=1:mem=1048576kb)" % (self.n7,)
        self.script['job11'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job11_select + "\n" + \
            "#PBS -l place=" + self.job11_place + "\n" + \
            "pbsdsh -n 1 -- %s\n" % (FIB40,) + \
            "pbsdsh -n 2 -- %s\n" % (FIB40,) + \
            "%s\n" % (FIB50,)

        self.job12_select = "vnode=%s:ncpus=1:mem=1gb" % (self.n7,)
        self.job12_schedselect = "1:vnode=%s:ncpus=1:mem=1gb" % (self.n7,)
        self.job12_place = "free"
        self.job12_exec_host = "%s/1" % (self.n7,)
        self.job12_exec_vnode = "(%s:ncpus=1:mem=1048576kb)" % (self.n7,)
        self.script['job12'] = \
            "#PBS -l select=" + self.job12_select + "\n" + \
            "#PBS -l place=" + self.job12_place + "\n" + \
            SLEEP_CMD + " 60\n"

        self.job13_select = "3:ncpus=1"
        self.script['job13'] = \
            "#PBS -S /bin/bash\n" \
            "#PBS -l select=" + self.job13_select + "\n" + \
            "#PBS -l place=" + self.job1_place + "\n" + \
            "pbsdsh -n 1 -- %s\n" % (FIB400,) + \
            "pbsdsh -n 2 -- %s\n" % (FIB400,) + \
            "pbsdsh -n 3 -- %s\n" % (FIB400,)

        self.stime = time.time()

    def tearDown(self):
        self.momA.signal("-CONT")
        self.momB.signal("-CONT")
        self.momC.signal("-CONT")
        for host in [self.hostA, self.hostB, self.hostC]:
            test_img = os.path.join("/home", "pbsuser", "test.img")
            self.du.rm(hostname=host, path=test_img, force=True,
                       runas=TEST_USER)
        TestFunctional.tearDown(self)

    def release_nodes_rerun(self, option="rerun"):
        """
        Test:
            Test the behavior of a job with released nodes when it
            gets rerun. Specifying an option "kill_mom_and_restart" will
            kill primary mom and restart, which would cause the job
            to requeue/rerun. Otherwise, a job qrerun will be issued
            directly.

            Given a job submitted with a select spec of
            2 super-chunks of ncpus=3 and mem=2gb each,
            and 1 chunk of ncpus=2 and mem=2gb, along with
            place spec of "scatter", resulting in an:

             exec_vnode=
                  (<n1>+<n2><n3>)+(<n4>+<n5>+<n6>)+(<n7>)

            First call:
              pbs_release_nodes -j <job-id> <n5> <n6> <n7>

            Then call:
              if option is "kill_and_restart_mom":
                  kill -KILL pbs_mom
                  start pbs_mom
              otherwise,
                  qrerun <job-id>
            Causes the job to rerun with the original requested
            resources.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5,
               self.n6, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # only mom hostC released the job since the sole vnode
        # <n7> has been released
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10, regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # Verify remaining job resources.

        sel_esc = self.job1_select.replace("+", "\+")
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=1"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host.replace(
            "+%s/0*2" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "+%s:mem=1048576kb:ncpus=1" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+%s:ncpus=1" % (self.n6,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '3gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "3145728kb",
                                  4, 2, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n5], 'job-busy', jobs_assn1,
                                1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n7, self.n8, self.n9, self.n10],
                                'free')

        # Now rerun the job

        if option == "kill_mom_and_restart":
            self.momA.signal("-KILL")
            self.momA.start()
        else:
            self.server.rerunjob(jid)

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

    def test_release_nodes_on_stageout_true(self):
        """
        Test:
              qsub -W release_nodes_on_stageout=true job.script
              where job.script specifies a select spec of
              2 super-chunks of ncpus=3 and mem=2gb each,
              and 1 chunk of ncpus=2 and mem=2gb, along with
              place spec of "scatter".

              With release_nodes_on_stageout=true option, when
              job is deleted and runs a lengthy stageout process,
              only the primary execution host's
              vnodes are left assigned to the job.
        """
        # Inside job1's script contains the
        # directive to release_nodes_on_stageout=true
        jid = self.create_and_submit_job('job1')

        self.server.expect(JOB, {'job_state': 'R',
                                 'release_nodes_on_stageout': 'True',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Deleting the job will trigger the stageout process
        # at which time sister nodes are automatically released
        # due to release_nodes_stageout=true set
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify remaining job resources.
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)
        # Check various vnode status
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.n4), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.n7), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

    def test_release_nodes_on_stageout_false(self):
        """
        Test:
              qsub -W release_nodes_on_stageout=False job.script
              where job.script specifies a select spec of
              2 super-chunks of ncpus=3 and mem=2gb each,
              and 1 chunk of ncpus=2 and mem=2gb, along with
              place spec of "scatter".

              With release_nodes_on_stageout=false option, when job is
              deleted and runs a lengthy stageout process, nothing
              changes in job's vnodes assignment.
        """
        # Inside job1_1's script contains the
        # directive to release_nodes_on_stageout=false
        jid = self.create_and_submit_job('job1_1')

        self.server.expect(JOB, {'job_state': 'R',
                                 'release_nodes_on_stageout': 'False',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Deleting a job should not trigger automatic
        # release of nodes due to release_nodes_stagout=False
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify no change in remaining job resources.
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Verify mom_logs
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_release_nodes_on_stageout_default(self):
        """
        Test:
              qsub: no -Wrelease_nodes_on_stageout
              option given.

              Job runs as normal.
        """
        jid = self.create_and_submit_job('job1_2')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify no change in remaining job resources.
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)
        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10],
                                'free')

        # Verify mom_logs
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_release_nodes_on_stageout_true_qalter(self):
        """
        Test:
              qalter -W release_nodes_on_stageout=true.

              After running job is modified by qalter,
              with release_nodes_on_stageout=true option, when
              job is deleted and runs a lengthy stageout process,
              only the primary execution host's
              vnodes are left assigned to the job.
        """

        jid = self.create_and_submit_job('job1_2')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # run qalter -Wrelease_nodes_on_stageout=true
        self.server.alterjob(jid,
                             {ATTR_W: 'release_nodes_on_stageout=true'})

        self.server.expect(JOB, {'release_nodes_on_stageout': 'True'}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # This triggers the lengthy stageout process
        # Wait for the Job to create test.img file
        self.check_stageout_file_size()
        self.server.delete(jid)

        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)
        # Check various vnode status
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1,
                                1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

    def test_release_nodes_on_stageout_false_qalter(self):
        """
        Test:
              qalter -W release_nodes_on_stageout=False.

              After running job is modified by qalter,
              With release_nodes_on_stageout=false option, when job is
              deleted and runs a lengthy stageout process, nothing
              changes in job's vnodes assignment.
        """
        jid = self.create_and_submit_job('job1_2')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # run qalter -Wrelease_nodes_on_stageout=true
        self.server.alterjob(jid,
                             {ATTR_W: 'release_nodes_on_stageout=false'})

        self.server.expect(JOB, {'release_nodes_on_stageout': 'False'}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # This triggers long stageout process
        # Wait for the Job to create test.img file
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify no change in remaining job resources.
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Verify mom_logs
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_hook_release_nodes_on_stageout_true(self):
        """
        Test:
              Using a queuejob hook to set
              release_nodes_on_stageout=true.

              When job is deleted and runs a
              lengthy stageout process, only
              the primary execution host's
              vnodes are left assigned to the job.
        """

        hook_body = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "queuejob hook executed")
pbs.event().job.release_nodes_on_stageout=True
"""
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        jid = self.create_and_submit_job('job1_2')

        self.server.log_match("queuejob hook executed", n=20,
                              interval=2)

        self.server.expect(JOB, {'job_state': 'R',
                                 'release_nodes_on_stageout': 'True',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Deleting the job will trigger the stageout process
        # at which time sister nodes are automatically released
        # due to release_nodes_stageout=true set
        # Wait for the Job to create test.img file
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify remaining job resources.

        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)

        # Check various vnode status
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Verify mom_logs

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.n4,), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

    def test_hook_release_nodes_on_stageout_false(self):
        """
        Test:
              Using a queuejob hook to set
              -Wrelease_nodes_on_stageout=False.

              When job is deleted and runs a
              lengthy stageout process, nothing
              changes in job's vnodes assignment.
        """

        hook_body = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "queuejob hook executed")
pbs.event().job.release_nodes_on_stageout=False
"""
        hook_event = "queuejob"
        hook_name = "qjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        jid = self.create_and_submit_job('job1_2')

        self.server.log_match("queuejob hook executed", n=20,
                              interval=2)

        self.server.expect(JOB, {'job_state': 'R',
                                 'release_nodes_on_stageout': 'False',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Deleting a job should not trigger automatic
        # release of nodes due to release_nodes_stagout=False
        # Wait for the Job to create test.img file
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify no change in remaining job resources.
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Verify mom_logs
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_hook2_release_nodes_on_stageout_true(self):
        """
        Test:
              Using a modifyjob hook to set
              release_nodes_on_stageout=true.

              When job is deleted and runs a
              lengthy stageout process, only
              the primary execution host's
              vnodes are left assigned to the job.
        """

        hook_body = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "modifyjob hook executed")
pbs.event().job.release_nodes_on_stageout=True
"""
        hook_event = "modifyjob"
        hook_name = "mjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        jid = self.create_and_submit_job('job1_2')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # This triggers the modifyjob hook
        self.server.alterjob(jid, {ATTR_N: "test"})

        self.server.log_match("modifyjob hook executed", n=100,
                              interval=2)

        self.server.expect(JOB, {'release_nodes_on_stageout': 'True'}, id=jid)

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Deleting the job will trigger the stageout process
        # at which time sister nodes are automatically released
        # due to release_nodes_stageout=true set
        # Wait for the Job to create test.img file
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify remaining job resources.

        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

    def test_hook2_release_nodes_on_stageout_false(self):
        """
        Test:
              Using a modifyjob hook to set
              release_nodes_on_stageout=False.

              When job is deleted and runs a
              lengthy stageout process, nothing
              changes in job's vnodes assignment.
        """

        hook_body = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "modifyjob hook executed")
pbs.event().job.release_nodes_on_stageout=False
"""
        hook_event = "modifyjob"
        hook_name = "mjob"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        jid = self.create_and_submit_job('job1_2')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # This triggers the modifyjob hook
        self.server.alterjob(jid, {ATTR_N: "test"})

        self.server.log_match("modifyjob hook executed", n=100,
                              interval=2)

        self.server.expect(JOB, {'release_nodes_on_stageout': 'False'}, id=jid)

        # Deleting a job should not trigger automatic
        # release of nodes due to release_nodes_stagout=False
        # Wait for the Job to create test.img file
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify no change in remaining job resources.
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Verify mom_logs
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, interval=1,
                            existence=False)

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_release_nodes_error(self):
        """
        Tests erroneous cases:
            - pbs_release_nodes (no options given)
            - pbs_release_nodes -j <job-id> (and nothing else)
            - pbs_release_nodes -a (not run inside a job)
            -  pbs_release_nodes -j <job-id> -a <node1>
                 (both -a and listed nodes are given)
            - pbs_release_nodes -j <unknown-job-id> -a
            - pbs_release_nodes -j <job-id> -a
              and job is not in a running state.

        Returns the appropriate error message.
        """
        # Test no option given
        cmd = [self.pbs_release_nodes_cmd]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith('usage:'))

        # test only -j <jobid> given
        cmd = [self.pbs_release_nodes_cmd, '-j', '23']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith('usage:'))

        # test only -a given
        cmd = [self.pbs_release_nodes_cmd, '-a']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: No jobid given'))

        # Test specifying an unknown job id
        cmd = [self.pbs_release_nodes_cmd, '-j', '300000', '-a']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: Unknown Job Id 300000'))

        # Test having '-a' and vnode parameter given to pbs_release_nodes
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'scatter'}
        jid = self.create_and_submit_job('job', a)

        cmd = [self.pbs_release_nodes_cmd, '-j', jid, '-a', self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith('usage:'))

        self.server.delete(jid)

        # Test pbs_release_nodes' permission
        jid = self.create_and_submit_job('job', a)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Run pbs_release_nodes as the executing user != TEST_USER
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, '-a']

        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER1)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: Unauthorized Request'))

        self.server.delete(jid)

        # Test pbs_release_nodes on a non-running job
        a = {'Resource_List.select': '3:ncpus=1',
             ATTR_h: None,
             'Resource_List.place': 'scatter'}
        jid = self.create_and_submit_job('job', a)

        self.server.expect(JOB, {'job_state': 'H'}, id=jid)

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, '-a']

        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: Request invalid for state of job'))

    def test_release_ms_nodes(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing pbs_release_nodes -j <job-id> <n5> <n6> <n1> <n7> where
             <n1> is a mother superior vnode, results in
             entire request to get rejected.
        """
        jid = self.create_and_submit_job('job1')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5, self.n6,
               self.n1, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)

        self.assertTrue(ret['err'][0].startswith(
            "pbs_release_nodes: " +
            "Can't free '%s' since " % (self.n1,) +
            "it's on a primary execution host"))

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_release_not_assigned_nodes(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing:
                 pbs_release_nodes -j <job-id> <n4> <n5> <no_node> <n6> <n7>
             with <no node> means such node is not assigned to the job.
             entire request to get rejected.
        Result:
              Returns an error message and no nodes get released.
        """
        jid = self.create_and_submit_job('job1')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4, self.n5,
               self.n8, self.n6, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)

        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            "pbs_release_nodes: node(s) requested " +
            "to be released not " +
            "part of the job: %s" % (self.n8,)))

        # Ensure nothing has changed with the job.
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_release_cray_nodes(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing:
                  pbs_release_nodes -j <job-id> <n4> <n5> <n6> <n7>
              where <n7> is a Cray node,
        Result:
              Returns an error message and no nodes get released.
        """
        jid = self.create_and_submit_job('job1')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Set hostC node to be of cray type
        a = {'resources_available.vntype': 'cray_login'}
        # set natural vnode of hostC
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.n7)

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4, self.n5,
               self.n6, self.n7]

        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)

        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            "pbs_release_nodes: not currently supported " +
            "on Cray X* series nodes: "
            "%s" % (self.n7,)))

        # Ensure nothing has changed with the job.
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy',
                                jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Check for no existence of account update ('u') record
        self.server.accounting_match(
            msg='.*u;' + jid + ".*exec_host=%s.*" % (self.job1_exec_host_esc,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

        # Check for no existence of account next ('c') record
        self.server.accounting_match(
            msg='.*c;' + jid + ".*exec_host=%s.*" % (self.job1_new_exec_host,),
            regexp=True, n="ALL", existence=False, max_attempts=5, interval=1,
            starttime=self.stime)

    def test_release_nodes_all(self):
        """
        Test:
              Given a job that specifies a select spec of
              2 super-chunks of ncpus=3 and mem=2gb each,
              and 1 chunk of ncpus=2 and mem=2gb, along with
              place spec of "scatter".

              Calling
                  pbs_release_nodes -j <job-id> -a

              will result in all the sister nodes getting
              unassigned from the job.
        """
        jid = self.create_and_submit_job('job1_2')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as regular user
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, '-a']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Verify remaining job resources.
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,

                                 self.n7, self.n8, self.n9, self.n10], 'free')
        self.server.expect(SERVER, {'resources_assigned.ncpus': 3,
                                    'resources_assigned.mem': '2097152kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 3,
                                   'resources_assigned.mem': '2097152kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

    def test_release_nodes_all_as_root(self):
        """
        Test:
             Same test as test_release_nodes_all except the pbs_release_nodes
             call is executed by root. Result is the same.
        """
        jid = self.create_and_submit_job('job1_2')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, '-a']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Verify remaining job resources.
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 3,
                                    'resources_assigned.mem': '2097152kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 3,
                                   'resources_assigned.mem': '2097152kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

    def test_release_nodes_all_inside_job(self):
        """
        Test:
            Like test_release_all test except instead of calling
            pbs_release_nodes from a command line, it is executed
            inside the job script of a running job. Same results.
        """
        # This one has a job script that calls 'pbs_release_nodes'
        # (no jobid specified)
        jid = self.create_and_submit_job('job1_3')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # wait for the job to execute pbs_release_nodes
        time.sleep(10)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Verify remaining job resources.
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 3,
                                    'resources_assigned.mem': '2097152kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 3,
                                   'resources_assigned.mem': '2097152kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

    def test_release_nodes1(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing pbs_release_nodes -j <job-id> <n4>
             results in:
             1. node <n4> no longer appearing in job's
                exec_vnode value,
             2. resources associated with the
                node are taken out of job's Resources_List.*,
                schedselect values,
             3. Since node <n4> is just one of the vnodes in the
                host assigned to the second super-chunk, the node
                still won't accept new jobs until all the other
                allocated vnodes from the same mom host are released.
                The resources then assigned to the job from
                node <n4> continues to be assigned including
                corresponding licenses.

             NOTE: This is testing to make sure the position of <n4>
             in the exec_vnode string (left end of a super-chunk) will
             not break the recreation of the attribute value after
             release.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # momB's host will not get DELETE_JOB2 request since
        # not all its vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host
        new_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb",
                                  7, 3, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "5242880kb", 7, 3,
                                  self.job1_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb",
                                  8, 3, self.job1_place, self.job1_sel_esc)

    def test_release_nodes1_as_user(self):
        """
        Test:
             Same as test_release_nodes1 except pbs_release_nodes
             is executed by as regular user. Same results.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as regular user
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # momB and momC's hosts will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host
        new_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb",
                                  7, 3, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "5242880kb", 7, 3,
                                  self.job1_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb",
                                  8, 3, self.job1_place, self.job1_sel_esc)

    def test_release_nodes1_extra(self):
        """
        Test:
             Like test_release_nodes1 except instead of the super-chunk
             and chunks getting only ncpus and mem values, additional
             resources mpiprocs and ompthreads are also requested and
             assigned:

             For example:

               qsub -l select="ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+
                               ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+
                               ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"

             We want to make sure the ompthreads and mpiprocs values are
             preserved in the new exec_vnode, and that in the $PBS_NODEFILE,
             the host names are duplicated according to the  number of
             mpiprocs. For example, if <n1> is assigned to first
             chunk, with mpiprocs=3, <n1> will appear 3 times in
             $PBS_NODEFILE.
        """
        jid = self.create_and_submit_job('job1_extra_res')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select':
                                 self.job1_extra_res_select,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'schedselect':
                                 self.job1_extra_res_schedselect,
                                 'exec_host':
                                 self.job1_extra_res_exec_host,
                                 'exec_vnode':
                                 self.job1_extra_res_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # inside pbs_nodefile_match_exec_host() function, takes  care of
        # verifying that the host names appear according to the number of
        # mpiprocs assigned to the chunk.
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(
                jid, self.job1_extra_res_exec_host,
                self.job1_extra_res_schedselect))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # momB and momC's hosts will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        sel_esc = self.job1_extra_res_select.replace("+", "\+")
        exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = \
            self.job1_extra_res_exec_vnode.replace(
                "[", "\[").replace(
                "]", "\]").replace("(", "\(").replace(")", "\)").replace(
                "+", "\+")

        newsel = "1:mem=2097152kb:ncpus=3:mpiprocs=3:ompthreads=2+" + \
            "1:mem=1048576kb:ncpus=2:mpiprocs=3:ompthreads=3+" + \
            "1:ncpus=2:mem=2097152kb:mpiprocs=2:ompthreads=2"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_extra_res_exec_host
        new_exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_extra_res_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB,
                           {'job_state': 'R',
                            'Resource_List.mem': '5gb',
                            'Resource_List.ncpus': 7,
                            'Resource_List.select': newsel,
                            'Resource_List.place': self.job1_extra_res_place,
                            'Resource_List.nodect': 3,
                            'schedselect': newsel,
                            'exec_host': new_exec_host,
                            'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_extra_res_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb",
                                  7, 3, self.job1_extra_res_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host, newsel))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "5242880kb", 7, 3,
                                  self.job1_extra_res_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb",
                                  8, 3, self.job1_extra_res_place,
                                  sel_esc)

    @timeout(400)
    def test_release_nodes2(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing pbs_release_nodes -j <job-id> <n5>
             results in:
             1. node <n5> no longer appearing in job's
                exec_vnode value,
             2. resources associated with the
                node are taken out of job's Resources_List.*,
                schedselect values,
             3. Since node <n5> is just one of the vnodes in the
                host assigned to the second super-chunk, the node
                still won't accept new jobs until all the other
                allocated vnodes from the same mom host are released.
                The resources then assigned to the job from
                node <n5> continues to be assigned including
                corresponding licenses.

             NOTE: This is testing to make sure the position of <n5>
             in the exec_vnode string (middle of a super-chunk) will
             not break the recreation of the attribute value after
             release.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # momB and momC's hosts will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host
        new_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb",
                                  7, 3, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "5242880kb", 7, 3,
                                  self.job1_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb",
                                  8, 3, self.job1_place, self.job1_sel_esc)

    def test_release_nodes2_extra(self):
        """
        Test:
             Like test_release_nodes2 except instead of the super-chunk
             and chunks getting only ncpus and mem values, additional
             resources mpiprocs and ompthreads are also requested and
             assigned:

             For example:

               qsub -l select="ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+
                               ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+
                               ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"

             We want to make sure the ompthreads and mpiprocs values are
             preserved in the new exec_vnode, and that in the $PBS_NODEFILE,
             the host names are duplicated according to the  number of
             mpiprocs. For example, if <n1> is assigned to first
             chunk, with mpiprocs=3, <n1> will appear 3 times in
             $PBS_NODEFILE.
        """
        jid = self.create_and_submit_job('job1_extra_res')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select':
                                 self.job1_extra_res_select,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'schedselect':
                                 self.job1_extra_res_schedselect,
                                 'exec_host':
                                 self.job1_extra_res_exec_host,
                                 'exec_vnode':
                                 self.job1_extra_res_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # inside pbs_nodefile_match_exec_host() function, takes care of
        # verifying that the host names appear according to the number of
        # mpiprocs assigned to the chunk.
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(
                jid, self.job1_extra_res_exec_host,
                self.job1_extra_res_schedselect))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # momB and momC's hosts will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        sel_esc = self.job1_extra_res_select.replace("+", "\+")
        exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_extra_res_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3:mpiprocs=3:ompthreads=2+" + \
                 "1:mem=1048576kb:ncpus=2:mpiprocs=3:ompthreads=3+" + \
                 "1:ncpus=2:mem=2097152kb:mpiprocs=2:ompthreads=2"

        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_extra_res_exec_host
        new_exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_extra_res_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB,
                           {'job_state': 'R',
                            'Resource_List.mem': '5gb',
                            'Resource_List.ncpus': 7,
                            'Resource_List.select': newsel,
                            'Resource_List.place': self.job1_extra_res_place,
                            'Resource_List.nodect': 3,
                            'schedselect': newsel,
                            'exec_host': new_exec_host,
                            'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_extra_res_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb",
                                  7, 3, self.job1_extra_res_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host, newsel))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "5242880kb", 7, 3,
                                  self.job1_extra_res_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb",
                                  8, 3, self.job1_extra_res_place,
                                  sel_esc)

    @timeout(400)
    def test_release_nodes3(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing pbs_release_nodes -j <job-id> <n6>
             results in:
             1. node <n6> no longer appearing in job's
                exec_vnode value,
             2. resources associated with the
                node are taken out of job's Resources_List.*,
                schedselect values,
             3. Since node <n6> is just one of the vnodes in the
                host assigned to the second super-chunk, the node
                still won't accept new jobs until all the other
                allocated vnodes from the same mom host are released.
                The resources then assigned to the job from
                node <n6> continues to be assigned including
                corresponding licenses.

             NOTE: This is testing to make sure the position of <n6>
             in the exec_vnode string (right end of a super-chunk) will
             not break the recreation of the attribute value after
             release.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n6]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # momB and momC's hosts will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")

        newsel = "1:mem=2097152kb:ncpus=3+1:mem=2097152kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host
        new_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace(
            "+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "+%s:ncpus=1" % (self.n6,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_exec_host_esc,
                                  new_exec_vnode_esc, "6291456kb",
                                  7, 3, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "6291456kb", 7, 3,
                                  self.job1_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb",
                                  8, 3, self.job1_place, self.job1_sel_esc)

    @timeout(400)
    def test_release_nodes3_extra(self):
        """
        Test:
             Like test_release_nodes3 except instead of the super-chunk
             and chunks getting only ncpus and mem values, additional
             resources mpiprocs and ompthreads are also requested and
             assigned:

             For example:

               qsub -l select="ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+
                               ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+
                               ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"

             We want to make sure the ompthreads and mpiprocs values are
             preserved in the new exec_vnode, and that in the $PBS_NODEFILE,
             the host names are duplicated according to the  number of
             mpiprocs. For example, if <n1> is assigned to first
             chunk, with mpiprocs=3, <n1> will appear 3 times in
             $PBS_NODEFILE.
        """
        jid = self.create_and_submit_job('job1_extra_res')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select':
                                 self.job1_extra_res_select,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'schedselect':
                                 self.job1_extra_res_schedselect,
                                 'exec_host':
                                 self.job1_extra_res_exec_host,
                                 'exec_vnode':
                                 self.job1_extra_res_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # inside pbs_nodefile_match_exec_host() function, takes  care of
        # verifying that the host names appear according to the number of
        # mpiprocs assigned to the chunk.
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(
                jid, self.job1_extra_res_exec_host,
                self.job1_extra_res_schedselect))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n6]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # momB and momC's hosts will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        sel_esc = self.job1_extra_res_select.replace("+", "\+")
        exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_extra_res_exec_vnode.replace(
            "[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")

        newsel = "1:mem=2097152kb:ncpus=3:mpiprocs=3:ompthreads=2+" + \
                 "1:mem=2097152kb:ncpus=2:mpiprocs=3:ompthreads=3+" + \
                 "1:ncpus=2:mem=2097152kb:mpiprocs=2:ompthreads=2"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_extra_res_exec_host
        new_exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_extra_res_exec_vnode.replace(
            "+%s:ncpus=1" % (self.n6,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB,
                           {'job_state': 'R',
                            'Resource_List.mem': '6gb',
                            'Resource_List.ncpus': 7,
                            'Resource_List.select': newsel,
                            'Resource_List.place':
                            self.job1_extra_res_place,
                            'Resource_List.nodect': 3,
                            'schedselect': newsel,
                            'exec_host': new_exec_host,
                            'exec_vnode': new_exec_vnode}, id=jid)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_extra_res_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "6291456kb",
                                  7, 3, self.job1_extra_res_place, newsel_esc)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host, newsel))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "6291456kb", 7, 3,
                                  self.job1_extra_res_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb",
                                  8, 3, self.job1_extra_res_place,
                                  sel_esc)

    def test_release_nodes4(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing pbs_release_nodes -j <job-id> <n4> <n5> <n7>
             results in:
             1. node <n4>, <n5>, and <n7> are no longer appearing in
                job's exec_vnode value,
             2. resources associated with the released
                nodes are taken out of job's Resources_List.*,
                schedselect values,
             3. Since nodes <n4> and <n5> are some of the vnodes in the
                host assigned to the second super-chunk, the node
                still won't accept new jobs until all the other
                allocated vnodes (<n6>)  from the same mom host are
                released.
             4. The resources then assigned to the job from
                node <n4> and <n5> continue to be assigned including
                corresponding licenses.
             5. <n7> is the only vnode assigned to the host mapped
                to the third chunk so it's fully deallocated and
                its assigned resources are removed from the job.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4, self.n5,
               self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # momB's host will not get job summary reported but
        # momC's host will get the job summary since all vnodes
        # from the host have been released.
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10, regexp=True, existence=False,
            max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10, regexp=True)

        # momB's host will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        # momC's host will get DELETE_JOB2 request since sole vnnode
        # <n7> has been released from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # Ensure the 'fib' process is gone on hostC when DELETE_JOB request
        # is received
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Verify remaining job resources.
        sel_esc = self.job1_select.replace("+", "\+")
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")

        newsel = "1:mem=2097152kb:ncpus=3+1:ncpus=1"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host.replace(
            "+%s/0*2" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n4> (1 cpu), <n5> (1 cpu), <n7> (2 cpus),
        # only <n7> got released.  <n4> and <n5> are part of a super
        # chunk that wasn't fully released.

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "2097152kb",
                                  4, 2, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        self.match_vnode_status([self.n0, self.n7, self.n8, self.n9, self.n10],
                                'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 6,
                                    'resources_assigned.mem': '4194304kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 6,
                                   'resources_assigned.mem': '4194304kb'},
                           id="workq")
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "2097152kb", 4, 2,
                                  self.job1_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb",
                                  8, 3, self.job1_place, self.job1_sel_esc)

    def test_release_nodes4_extra(self):
        """
        Test:
             Like test_release_nodes4 except instead of the super-chunk
             and chunks getting only ncpus and mem values, additional
             resources mpiprocs and ompthreads are also requested and
             assigned:

             For example:

               qsub -l select="ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+
                               ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+
                               ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"

             We want to make sure the ompthreads and mpiprocs values are
             preserved in the new exec_vnode, and that in the $PBS_NODEFILE,
             the host names are duplicated according to the  number of
             mpiprocs. For example, if <n1> is assigned to first
             chunk, with mpiprocs=3, <n1> will appear 3 times in
             $PBS_NODEFILE.
        """
        jid = self.create_and_submit_job('job1_extra_res')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select':
                                 self.job1_extra_res_select,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'schedselect':
                                 self.job1_extra_res_schedselect,
                                 'exec_host':
                                 self.job1_extra_res_exec_host,
                                 'exec_vnode':
                                 self.job1_extra_res_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # inside pbs_nodefile_match_exec_host() function, takes  care of
        # verifying that the host names appear according to the number of
        # mpiprocs assigned to the chunk.
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(
                jid, self.job1_extra_res_exec_host,
                self.job1_extra_res_schedselect))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4, self.n5,
               self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # momB's host will not get job summary reported but
        # momC's host will get the job summary since all vnodes
        # from the host have been released.
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10, regexp=True, existence=False,
            max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10, regexp=True)

        # momB's host will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        # momC will get DELETE_JOB2 request since sole vnode
        # <n7> has been released from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # Ensure the 'fib' process is gone from hostC when DELETE_JOB request
        # received
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Verify remaining job resources.
        sel_esc = self.job1_extra_res_select.replace("+", "\+")
        exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_extra_res_exec_vnode.replace(
            "[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")

        newsel = "1:mem=2097152kb:ncpus=3:mpiprocs=3:ompthreads=2+" + \
                 "1:ncpus=1:mpiprocs=3:ompthreads=3"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_extra_res_exec_host.replace(
            "+%s/0*2" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_extra_res_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n4> (1 cpu), <n5> (1 cpu), <n7> (2 cpus),
        # only <n7> got released.  <n4> and <n5> are part of a super
        # chunk that wasn't fully released.

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_extra_res_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "2097152kb",
                                  4, 2, self.job1_extra_res_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        self.match_vnode_status([self.n0, self.n7, self.n8, self.n9, self.n10],
                                'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 6,
                                    'resources_assigned.mem': '4194304kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 6,
                                   'resources_assigned.mem': '4194304kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host, newsel))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "2097152kb", 4, 2,
                                  self.job1_extra_res_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb",
                                  8, 3, self.job1_extra_res_place,
                                  sel_esc)

    def test_release_nodes5(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing pbs_release_nodes -j <job-id> <n5> <n6> <n7>
             results in:
             1. node <n5>, <n6>, and <n7> are no longer appearing in
                job's exec_vnode value,
             2. resources associated with the released
                nodes are taken out of job's Resources_List.*,
                schedselect values,
             3. Since nodes <n5> and <n6> are some of the vnodes in the
                host assigned to the second super-chunk, the node
                still won't accept new jobs until all the other
                allocated vnodes (<n4>) from the same mom host are
                released.
             4. The resources then assigned to the job from
                node <n5> and <n6> continue to be assigned including
                corresponding licenses.
             5. <n7> is the only vnode assigned to the host mapped
                to the third chunk so it's fully deallocated and
                its assigned resources are removed from the job.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5, self.n6,
               self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # momB's host will not get job summary reported but
        # momC's host will get the job summary since all vnodes
        # from the host have been released.
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10, regexp=True, existence=False,
            max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10, regexp=True)

        # momB's host will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        # momC will get DELETE_JOB2 request since sole vnode
        # <n7> has been released from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # Ensure the 'fib' process is gone from hostC when DELETE_JOB request
        # received
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Verify remaining job resources.
        sel_esc = self.job1_select.replace("+", "\+")
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=1"

        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host.replace(
            "+%s/0*2" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "+%s:mem=1048576kb:ncpus=1" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+%s:ncpus=1" % (self.n6,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = \
            new_exec_vnode.replace("[", "\[").replace("]", "\]").replace(
                "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '3gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n5> (1 cpu), <n6> (1 cpu), <n7> (2 cpus),
        # only <n7> got released.  <n5> and <n6> are part of a super
        # chunk that wasn't fully released.

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "3145728kb",
                                  4, 2, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        # <n5> still job-busy
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        # <n6> still job-busy
        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        # <n7> now free
        self.match_vnode_status([self.n0, self.n7, self.n8, self.n9, self.n10],
                                'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 6,
                                    'resources_assigned.mem': '4194304kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 6,
                                   'resources_assigned.mem': '4194304kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "3145728kb", 4, 2,
                                  self.job1_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb",
                                  8, 3, self.job1_place, self.job1_sel_esc)

    def test_release_nodes5_extra(self):
        """
        Test:
             Like test_release_nodes5 except instead of the super-chunk
             and chunks getting only ncpus and mem values, additional
             resources mpiprocs and ompthreads are also requested and
             assigned:

             For example:

               qsub -l select="ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+
                               ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+
                               ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"

             We want to make sure the ompthreads and mpiprocs values are
             preserved in the new exec_vnode, and that in the $PBS_NODEFILE,
             the host names are duplicated according to the  number of
             mpiprocs. For example, if <n1> is assigned to first
             chunk, with mpiprocs=3, <n1> will appear 3 times in
             $PBS_NODEFILE.
        """
        jid = self.create_and_submit_job('job1_extra_res')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select':
                                 self.job1_extra_res_select,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'schedselect':
                                 self.job1_extra_res_schedselect,
                                 'exec_host':
                                 self.job1_extra_res_exec_host,
                                 'exec_vnode':
                                 self.job1_extra_res_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # inside pbs_nodefile_match_exec_host() function, takes  care of
        # verifying that the host names appear according to the number of
        # mpiprocs assigned to the chunk.
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(
                jid, self.job1_extra_res_exec_host,
                self.job1_extra_res_schedselect))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5, self.n6,
               self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # momB's host will not get job summary reported but
        # momC's host will get the job summary since all vnodes
        # from the host have been released.
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10, regexp=True, existence=False,
            max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10, regexp=True)

        # momB's host will not get DELETE_JOB2 request since
        # not all their vnodes have been released yet from the job.
        # momC will get DELETE_JOB2 request since sole vnode
        # <n7> has been released from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # Ensure the 'fib' process is gone from hostC when DELETE_JOB request
        # received
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Verify remaining job resources.
        sel_esc = self.job1_extra_res_select.replace("+", "\+")
        exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = \
            self.job1_extra_res_exec_vnode.replace("[", "\[").replace(
                "]", "\]").replace("(", "\(").replace(")", "\)").replace(
                "+", "\+")
        newsel = \
            "1:mem=2097152kb:ncpus=3:mpiprocs=3:ompthreads=2+" + \
            "1:mem=1048576kb:ncpus=1:mpiprocs=3:ompthreads=3"

        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_extra_res_exec_host.replace(
            "+%s/0*2" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_extra_res_exec_vnode.replace(
            "+%s:mem=1048576kb:ncpus=1" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+%s:ncpus=1" % (self.n6,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = \
            new_exec_vnode.replace("[", "\[").replace("]", "\]").replace(
                "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '3gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n5> (1 cpu), <n6> (1 cpu), <n7> (2 cpus),
        # only <n7> got released.  <n5> and <n6> are part of a super
        # chunk that wasn't fully released.

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_extra_res_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "3145728kb",
                                  4, 2, self.job1_extra_res_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        # <n5> still job-busy
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        # <n6> still job-busy
        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        # <n7> is now free
        self.match_vnode_status([self.n0, self.n7, self.n8, self.n9, self.n10],
                                'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 6,
                                    'resources_assigned.mem': '4194304kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 6,
                                   'resources_assigned.mem': '4194304kb'},
                           id="workq")
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host, newsel))

        self.server.delete(jid)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "3145728kb", 4, 2,
                                  self.job1_extra_res_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb",
                                  8, 3, self.job1_extra_res_place,
                                  sel_esc)

    def test_release_nodes6(self):
        """
        Test:
             Given: a job that has been submitted with a select spec
             of 2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an

             exec_vnode=
                  (<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Executing pbs_release_nodes -j <job-id> <n4> <n5> <n6> <n7>
             is equivalent to doing 'pbs_release_nodes -a'  which
             will have the same result as test_release_nodes_all.
             That is, all sister nodes assigned to the job are
             released early from the job.
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_exec_host))

        # Run pbs_release_nodes as regular user
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4, self.n5,
               self.n6, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Ensure the 'fib' process is gone when DELETE_JOB2 received on momB
        self.server.pu.get_proc_info(
            self.momB.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Ensure the 'fib' process is gone when DELETE_JOB2 received on momC
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Verify remaining job resources.
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': self.job1_newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': self.job1_newsel,
                                 'exec_host': self.job1_new_exec_host,
                                 'exec_vnode': self.job1_new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        # nodes <n4>, <n5>, <n6>, <n7> are all free now
        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 3,
                                    'resources_assigned.mem': '2097152kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 3,
                                   'resources_assigned.mem': '2097152kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, self.job1_new_exec_host))

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, self.job1_newsel)

        # For job to end to get the end records in the accounting_logs
        self.server.delete(jid)

        # Check account phased end job ('e') record
        self.match_accounting_log('e', jid, self.job1_new_exec_host,
                                  self.job1_new_exec_vnode_esc, "2097152kb", 3,
                                  1, self.job1_place, self.job1_newsel)

        # Check account end of job ('E') record
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

    def test_release_nodes6_extra(self):
        """
        Test:
             Like test_release_nodes6 except instead of the super-chunk
             and chunks getting only ncpus and mem values, additional
             resources mpiprocs and ompthreads are also requested and
             assigned:

             For example:

               qsub -l select="ncpus=3:mem=2gb:mpiprocs=3:ompthreads=2+
                               ncpus=3:mem=2gb:mpiprocs=3:ompthreads=3+
                               ncpus=2:mem=2gb:mpiprocs=2:ompthreads=2"

             We want to make sure the ompthreads and mpiprocs values are
             preserved in the new exec_vnode, and that in the $PBS_NODEFILE,
             the host names are duplicated according to the  number of
             mpiprocs. For example, if <n1> is assigned to first
             chunk, with mpiprocs=3, <n1> will appear 3 times in
             $PBS_NODEFILE.
        """
        jid = self.create_and_submit_job('job1_extra_res')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select':
                                 self.job1_extra_res_select,
                                 'Resource_List.place':
                                 self.job1_extra_res_place,
                                 'schedselect':
                                 self.job1_extra_res_schedselect,
                                 'exec_host': self.job1_extra_res_exec_host,
                                 'exec_vnode': self.job1_extra_res_exec_vnode},
                           id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid,
                                              self.job1_extra_res_exec_host,
                                              self.job1_extra_res_schedselect))

        # Run pbs_release_nodes as regular user
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4, self.n5,
               self.n6, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Ensure the 'fib' process is gone when DELETE_JOB2 received on momB
        self.server.pu.get_proc_info(
            self.momB.hostname, ".*fib.*", None)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Ensure the 'fib' process is gone when DELETE_JOB2 received on momC
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Verify remaining job resources.
        sel_esc = self.job1_extra_res_select.replace("+", "\+")
        exec_host_esc = self.job1_extra_res_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = \
            self.job1_extra_res_exec_vnode.replace("[", "\[").replace(
                "]", "\]").replace(
                "(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3:mpiprocs=3:ompthreads=2"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_extra_res_exec_host.replace(
            "+%s/0*2" % (self.n7,), "")
        new_exec_host = new_exec_host.replace("+%s/0*0" % (self.n4,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_extra_res_exec_vnode.replace(
            "+%s:mem=1048576kb:ncpus=1" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+%s:ncpus=1" % (self.n6,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:mem=1048576kb:ncpus=1)" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = \
            new_exec_vnode.replace("[", "\[").replace("]", "\]").replace(
                "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB,
                           {'job_state': 'R',
                            'Resource_List.mem': '2gb',
                            'Resource_List.ncpus': 3,
                            'Resource_List.select': newsel,
                            'Resource_List.place':
                            self.job1_extra_res_place,
                            'Resource_List.nodect': 1,
                            'schedselect': newsel,
                            'exec_host': new_exec_host,
                            'exec_vnode': new_exec_vnode}, id=jid)

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 3,
                                    'resources_assigned.mem': '2097152kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 3,
                                   'resources_assigned.mem': '2097152kb'},
                           id="workq")

        # nodes <n4>, <n5>, <n6>, <n7> are all free now
        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10], 'free')

        # Ensure the $PBS_NODEFILE contents account for the mpiprocs value;
        # that is, each node hostname is listed 'mpiprocs' number of times in
        # the file.
        self.assertTrue(
            self.pbs_nodefile_match_exec_host(
                jid, self.job1_new_exec_host, newsel))

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc,
                                  "6gb", 8, 3,
                                  self.job1_extra_res_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  self.job1_new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, newsel_esc)

        # For job to end to get the end records in the accounting_logs
        self.server.delete(jid)

        # Check account phased end job ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "2097152kb", 3,
                                  1, self.job1_place, newsel_esc)

        # Check account end of job ('E') record
        self.match_accounting_log('E', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place, sel_esc)

    # longer timeout needed as the following test takes a bit
    # longer waiting for job to finish due to stage out
    @timeout(400)
    def test_release_nodes_cmd_plus_stageout(self):
        """
        Test:
            This test calling pbs_release_nodes command on a job
            submitted with release_nodes_on_stageout option.

            Given a job submitted as:
               qsub -W release_nodes_on_stageout=true job.script
            where job.script specifies a select spec of
            2 super-chunks of ncpus=3 and mem=2gb each,
            and 1 chunk of ncpus=2 and mem=2gb, along with
            place spec of "scatter", resulting in an:

            exec_vnode=(<n1>+<n2>+<n3>)+(<n4>+<n5>+<n6>)+(<n7>)

            Then issue:
                  pbs_release_nodes -j <job-id> <n7>

            This would generate a 'u' and 'c' accounting record.
            while <n7> vnode gets deallocated given that it's
            the only vnode assigned to host mapped to third chunk.

            Now call:
                  qdel <job-id>

            This would cause the remaining vnodes <n4>, <n5>, <n6>
            to be deallocated due to job have the
            -W release_nodes_on_stageout=true setting.
            The result is reflected in the 'u', 'c', and 'e'
            accounting logs. 'E' accounting record summarizes
            everything.
        """
        jid = self.create_and_submit_job('job1')

        self.server.expect(JOB, {'job_state': 'R',
                                 'release_nodes_on_stageout': 'True',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Only mom hostC will get the job summary it was released
        # early courtesy of sole vnode <n7>.
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostB), n=10,
            regexp=True, existence=False, max_attempts=5, interval=1)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            regexp=True)

        # Only mom hostC will gt the IM_DELETE_JOB2 request
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # Ensure the 'fib' process is gone from hostC when DELETE_JOB request
        # received
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        # Verify remaining job resources.

        sel_esc = self.job1_select.replace("+", "\+")
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")

        newsel = "1:mem=2097152kb:ncpus=3+1:mem=2097152kb:ncpus=3"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = "%s/0*0+%s/0*0" % (self.n0, self.hostB)
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '4194304kb',
                                 'Resource_List.ncpus': 6,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        # <n7> now free
        self.match_vnode_status([self.n0, self.n7, self.n8, self.n9, self.n10],
                                'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 6,
                                    'resources_assigned.mem': '4194304kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 6,
                                   'resources_assigned.mem': '4194304kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "4194304kb",
                                  6, 2, self.job1_place, newsel_esc)

        # Terminate the job
        self.check_stageout_file_size()
        self.server.delete(jid)

        # Verify remaining job resources.

        sel_esc = self.job1_select.replace("+", "\+")
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = self.transform_select(self.job1_select.split('+')[0])
        newsel_esc = newsel.replace("+", "\+")

        new_exec_host = self.job1_exec_host.split('+')[0]
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.split(')')[0] + ')'
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace(
            "+", "\+")
        self.server.expect(JOB, {'job_state': 'E',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check 'u' accounting record from release_nodes_on_stageout=true
        self.match_accounting_log('u', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "4194304kb", 6, 2,
                                  self.job1_place,
                                  newsel_esc)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Check various vnode status.

        # only vnodes from mother superior (sef.hostA) are job-busy
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5,
                                 self.n6, self.n7, self.n8, self.n9,
                                 self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        # Check 'c' accounting record from release_nodes_on_stageout=true
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, newsel_esc)

        # wait for job to finish
        self.server.expect(JOB, 'queue', id=jid, op=UNSET,
                           interval=4, offset=15)

        # Check 'e' record to release_nodes_on_stageout=true
        self.match_accounting_log('e', jid, new_exec_host,
                                  new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, newsel_esc)

        # Check 'E' (end of job) record to release_nodes_on_stageout=true
        self.match_accounting_log('E', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

    def test_multi_release_nodes(self):
        """
        Test:
             This tests several calls to pbs_release_nodes command for
             the same job.

             Given a job submitted with a select spec of
             2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an:

             has exec_vnode=
                  (<n1>+<n2><n3>)+(<n4>+<n5>+<n6>)+(<n7>)
             First call:

                  pbs_release_nodes -j <job-id> <n4>

             <n4> node no longer shows in job's exec_vnode,
             but it will still show as job-busy
             (not accept jobs) since the other 2 vnodes,
             <n5> and <n6> from the host mapped to second
             chunk are still assigned. The 'u' and 'c'
             accounting records will reflect this.

             Second call:

                  pbs_release_nodes -j <job-id> <n5> <n6> <n7>

             Now since all vnodes assigned to the job from
             host mapped to second chunk will show as free.
             Again, the accounting 'u' and 'c' records would
             reflect this fact.
        """
        jid = self.create_and_submit_job('job1')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.

        sel_esc = self.job1_select.replace("+", "\+")
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")

        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host
        new_exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode_esc = \
            new_exec_vnode.replace("[", "\[").replace(
                "]", "\]").replace("(", "\(").replace(
                ")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Though the job is listed with ncpus=7 taking away released vnode
        # <n4> (1 cpu), its license is not taken away as <n4> is assigned
        # to a super chunk, and the parent mom still has not released the
        # job as vnodes <n5> and <n6> are still allocated to the job.

        # Check various vnode status.
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10],
                                'free')

        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")

        # Check account update ('u') record
        self.match_accounting_log('u', jid, exec_host_esc,
                                  exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb",
                                  7, 3, self.job1_place, newsel_esc)

        # Run pbs_release_nodes again
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5,
               self.n6, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Now mom hostB and hostC can fully release the job
        # resulting in job summary information reported
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            interval=2, regexp=True)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            interval=2, regexp=True)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=2)

        # Check account update ('u') record got generated
        # second pbs_release_nodes call
        self.match_accounting_log('u', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb", 7, 3,
                                  self.job1_place,
                                  newsel_esc)

        # Verify remaining job resources.
        newsel = "1:mem=2097152kb:ncpus=3"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = new_exec_host.replace("+%s/0*2" % (self.n7,), "")
        new_exec_host = new_exec_host.replace("+%s/0*0" % (self.n4,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:mem=1048576kb:ncpus=1" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+%s:ncpus=1)" % (self.n6,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 3,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 1,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3], 'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n4, self.n5, self.n6,
                                 self.n7, self.n8, self.n9, self.n10],
                                'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 3,
                                    'resources_assigned.mem': '2097152kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 3,
                                   'resources_assigned.mem': '2097152kb'},
                           id="workq")

        # Check to make sure 'c' (next) record got generated for
        # second pbs_release_nodes call
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "2097152kb",
                                  3, 1, self.job1_place, newsel_esc)

    def test_release_nodes_run_next_job(self):
        """
        Test:
             Test releasing nodes of one job to allow another
             job to use resources from the released nodes.

             Given a job submitted with a select spec of
             2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter", resulting in an:

             exec_vnode=
                  (<n1>+<n2><n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             First call:

                pbs_release_nodes -j <job-id> <n4> <n5> <n7>

            Submit another job: j2 that will need also the
            unreleased vnode <n6> so job stays queued.

            Now execute:
                   pbs_release_nodes -j <job-id> <n6>>

            And job j2 starts executing using node <n6>
        """
        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid,
               self.n4, self.n5, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        # this is a 7-cpu job that needs <n6> which has not been freed
        jid2 = self.create_and_submit_job('job2')

        # we expect job_state to be Queued
        self.server.expect(JOB, 'comment', op=SET, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        # Let's release the remaining <node6> vnode from hostB
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n6]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # now job 2 should start running
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '7gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job2_select,
                                 'Resource_List.place': self.job2_place,
                                 'schedselect': self.job2_schedselect,
                                 'exec_host': self.job2_exec_host,
                                 'exec_vnode': self.job2_exec_vnode_var1},
                           id=jid2)

        jobs_assn2 = "%s/0" % (jid2,)
        self.match_vnode_status([self.n4, self.n5, self.n6, self.n8, self.n9],
                                'job-busy', jobs_assn2, 1, '1048576kb')

        jobs_assn3 = "%s/0, %s/1" % (jid2, jid2)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn3,
                                2, '2097152kb')
        self.match_vnode_status([self.n0, self.n10], 'free')

    def test_release_nodes_rerun(self):
        """
        Test:
            Test the behavior of a job with released nodes when it
            gets rerun. The job is killed, requeued, and assigned
            the original set of resources before pbs_release_nodes
            was called.
        """
        self.release_nodes_rerun()

    def test_release_nodes_rerun_downed_mom(self):
        """
        Test:
            Test the behavior of a job with released nodes when it
            gets rerun, due to primary mom getting killed and restarted.
            The job is killed, requeued, and assigned
            the original set of resources before pbs_release_nodes
            was called.
        """
        self.release_nodes_rerun("kill_mom_and_restart")

    def test_release_nodes_epilogue(self):
        """
        Test:
             Test to make sure when a job is removed from
             a mom host when all vnodes from that host have
             been released for the job, and run the epilogue hook.
        """

        # First, submit an epilogue hook:

        hook_body = """
import pbs
pbs.logjobmsg(pbs.event().job.id, "epilogue hook executed")
"""

        a = {'event': 'execjob_epilogue', 'enabled': 'true'}
        self.server.create_import_hook("epi", a, hook_body)

        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (jid, jid)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # Run pbs_release_nodes
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4, self.n5,
               self.n6, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)

        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        self.momB.log_match("Job;%s;epilogue hook executed" % (jid,), n=20)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            interval=5, regexp=True)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            interval=5, regexp=True)

        # Ensure the 'fib' process is gone when DELETE_JOB
        self.server.pu.get_proc_info(
            self.momB.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            interval=5)

        self.momC.log_match("Job;%s;epilogue hook executed" % (jid,), n=20,
                            interval=5)
        # Ensure the 'fib' process is gone when DELETE_JOB
        self.server.pu.get_proc_info(
            self.momC.hostname, ".*fib.*", None, regexp=True)
        self.assertEqual(len(self.server.pu.processes), 0)

    def test_release_nodes_complex(self):
        """
        Test:
             Test a complicated scenario involving
             releasing nodes from a job that has been
             submitted with exclusive placement
             (-l place=scatter:excl), having one of the
             parent moms of released vnodes being
             stopped and continued, suspending and resuming
             of jobs, and finally submitting a new job
             requiring a non-exclusive access to a vnode.

             Given a job submitted with a select spec of
             2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=1 and mem=1gb, along with
             place spec of "scatter:excl", resulting in an:

             exec_vnode=
                  (<n1>+<n2><n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Then stop parent mom host of <n7> (kill -STOP), now issue:
                pbs_release_nodes -j <job-id> <n4> <n5> <n7>

             causing <n4>, <n5>, and <n7> to still be tied to the job
             as there's still node <n6> tied to the job as part of mom
             hostB, which satisfies the second super-chunk.
             Node <n7> is still assigned to the job as parent
             mom hostC has been stopped.

             Submit another job (job2), needing the node <n7> and
             1 cpu but job ends up queued since first job is still
             using <n7>.
             Now Delete job2.

             Now suspend the first job, and all resources_assigned to
             the job's nodes are cleared.

             Now resume the mom of <n7> (kill -CONT). This mom would
             tell server to free up node <n7> as first job has
             been completely removed from the node.

             Now resume job1, and all resources_asssigned
             of the job's nodes including <n4>, <n5> are shown
             allocated, with resources in node <n7> freed.

             Then submit a new 1-cpu job that specifically asks for
             vnode <n7>, and job should run
             taking vnode <n7>, but on pbsnodes listing,
             notice that the vnode's state is still "free"
             and using 1 cpu and 1gb of memory. It's because
             there's still 1 cpu and 1 gb of memory left to
             use in vnode <n7>.
        """
        jid = self.create_and_submit_job('job11x')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job11x_select,
                                 'Resource_List.place': self.job11x_place,
                                 'schedselect': self.job11x_schedselect,
                                 'exec_host': self.job11x_exec_host,
                                 'exec_vnode': self.job11x_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5, self.n7],
                                'job-exclusive', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # temporarily suspend momC, prevents from operating on released nodes
        self.momC.signal("-STOP")

        # Run pbs_release_nodes on nodes belonging to momB and momC
        cmd = [self.pbs_release_nodes_cmd, '-j', jid,
               self.n4, self.n5, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # mom hostB and mom hostC continue to hold on to the job
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # since not all vnodes from momB have been freed from the job,
        # DELETE_JOB2 request from MS is not sent
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # since node <n7> from mom hostC has not been freed from the job
        # since mom is currently stopped, the DELETE_JOB2 request from
        # MS is not sent
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.

        sel_esc = self.job11x_select.replace("+", "\+")
        exec_host_esc = self.job11x_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job11x_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:ncpus=1"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job11x_exec_host.replace(
            "+%s/0" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job11x_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=1:mem=1048576kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11x_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n4> (1 cpu), <n5> (1 cpu), <n7> (1 cpu),
        # hostB hasn't released job because <n6> is still part of the job and
        # <n7> hasn't been released because the mom is stopped.

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5,
                                 self.n7], 'job-exclusive', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # submit a new job needing node <n7>, which is still currently tied
        # to the previous job.
        jid2 = self.create_and_submit_job('job12')

        # we expect job_state to be Queued as the previous job still has
        # vnode managed by hostC assigned exclusively.
        self.server.expect(JOB, 'comment', op=SET, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.delete(jid2)

        # now suspend previous job
        self.server.sigjob(jid, 'suspend')

        a = {'job_state': 'S'}
        self.server.expect(JOB, a, id=jid)

        self.match_vnode_status([self.n0, self.n1, self.n2, self.n3,
                                 self.n4, self.n5, self.n6, self.n7,
                                 self.n8, self.n9, self.n10], 'free')

        # check server's resources_assigned values
        self.server.expect(SERVER, {'resources_assigned.ncpus': 0,
                                    'resources_assigned.mem': '0kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 0,
                                   'resources_assigned.mem': '0kb'},
                           id="workq")

        # now resume previous job
        self.server.sigjob(jid, 'resume')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11x_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5,
                                 self.n7], 'job-exclusive', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # resume momC
        self.momC.signal("-CONT")

        # With momC resumed, it now receives DELETE_JOB2 request from
        # MS
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # submit this 1 cpu job that requests specifically vnode <n7>
        jid3 = self.create_and_submit_job('job12')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '1gb',
                                 'Resource_List.ncpus': 1,
                                 'Resource_List.nodect': 1,
                                 'Resource_List.select': self.job12_select,
                                 'Resource_List.place': self.job12_place,
                                 'schedselect': self.job12_schedselect,
                                 'exec_host': self.job12_exec_host,
                                 'exec_vnode': self.job12_exec_vnode},
                           id=jid3)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-exclusive', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        # Node <n7> shows as free since job 'jid3' did not request
        # exclusive access.
        jobs_assn2 = "%s/0" % (jid3,)
        self.match_vnode_status([self.n7], 'free', jobs_assn2,
                                1, '1048576kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

    def test_release_nodes_excl_server_restart_quick(self):
        """
        Test:
             Test having a job submitted with exclusive
             placement (-l place=scatter:excl),
             then release a node from it where parent
             mom is stopped, before stopping the
             server with qterm -t quick which
             will leave the job running, and when
             server is started in warm mode where
             also previous job retains its state,
             job continues to have previous node
             assignment including the pending
             released node.

             Given a job submitted with a select spec of
             2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter:excl", resulting in an:

             exec_vnode=
                  (<n1>+<n2><n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Then stop parent mom host of <n7> (kill -STOP), now issue:
                pbs_release_nodes -j <job-id> <n4> <n5> <n7>

             causing <n4>, <n5>, and <n7> to still be tied to the job
             as there's still node <n6> tied to the job as part of mom
             hostB, which satisfies the second super-chunk.
             Node <n7> is still assigned to the job as parent
             mom hostC has been stopped.

             Do a qterm -t quick, which will leave the job
             running.

             Now start pbs_server in default warm mode where all
             running jobs are retained in that state including
             their node assignments.

             The job is restored to the same nodes assignment
             as before taking into account the released nodes.

             Now resume the mom of <n7> (kill -CONT). This mom would
             tell server to free up node <n7> as first job has
             been completely removed from the node.
        """
        jid = self.create_and_submit_job('job11x')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job11x_select,
                                 'Resource_List.place': self.job11x_place,
                                 'schedselect': self.job11x_schedselect,
                                 'exec_host': self.job11x_exec_host,
                                 'exec_vnode': self.job11x_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5, self.n7],
                                'job-exclusive', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # temporarily suspend momC, prevents from operating on released nodes
        self.momC.signal("-STOP")

        # Run pbs_release_nodes on nodes belonging to momB and momC
        cmd = [self.pbs_release_nodes_cmd, '-j', jid,
               self.n4, self.n5, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # mom hostB and mom hostC continuue to hold on to the job
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # since not all vnodes from momB have been freed from the job,
        # DELETE_JOB2 request from MS is not sent
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # since node <n7> from mom hostC has not been freed from the job
        # since mom is currently stopped, the DELETE_JOB2 request from
        # MS is not sent
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.

        sel_esc = self.job11x_select.replace("+", "\+")
        exec_host_esc = self.job11x_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job11x_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:ncpus=1"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job11x_exec_host.replace(
            "+%s/0" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job11x_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=1:mem=1048576kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11x_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n4> (1 cpu), <n5> (1 cpu), <n7> (1 cpu),
        # hostB hasn't released job because <n6> is still part of the job and
        # <n7> hasn't been released because the mom is stopped.

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5,
                                 self.n7], 'job-exclusive', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # Stop and Start the server
        om = self.server.get_op_mode()
        self.server.set_op_mode(PTL_CLI)
        self.server.qterm(manner="quick")
        self.server.set_op_mode(om)
        self.assertFalse(self.server.isUp())
        self.server.start()
        self.assertTrue(self.server.isUp())

        # Job should have the same state as before
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11x_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-exclusive', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        # parent mom of <n7> is currently in stopped state
        self.match_vnode_status([self.n7], 'state-unknown,down,job-exclusive',
                                jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # resume momC
        self.momC.signal("-CONT")

        # With momC resumed, it now receives DELETE_JOB2 request from
        # MS
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

    def test_release_nodes_excl_server_restart_immed(self):
        """
        Test:
             Test having a job submitted with exclusive
             placement (-l place=scatter:excl),
             then release a node from it where parent
             mom is stopped, before stopping the
             server with qterm -t immediate which
             will requeue job completely, and when
             server is started, job gets assigned
             resources to the original request
             before the pbs_release_nodes call.

             Given a job submitted with a select spec of
             2 super-chunks of ncpus=3 and mem=2gb each,
             and 1 chunk of ncpus=2 and mem=2gb, along with
             place spec of "scatter:excl", resulting in an:

             exec_vnode=
                  (<n1>+<n2><n3>)+(<n4>+<n5>+<n6>)+(<n7>)

             Then stop parent mom host of <n7> (kill -STOP), now issue:
                pbs_release_nodes -j <job-id> <n4> <n5> <n7>

             causing <n4>, <n5>, and <n7> to still be tied to the job
             as there's still node <n6> tied to the job sd part of mom
             hostB, which satisfies the second super-chunk.
             Node <n7> is still assigned to the job as parent
             mom hostC has been stopped.

             Do a qterm -t immediate, which will requeue the
             currently running job.

             Now start pbs_server.

             The job goes back to getting assigned resources for the
             original request, before pbs_release_nodes
             was called.
        """
        jid = self.create_and_submit_job('job11x')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job11x_select,
                                 'Resource_List.place': self.job11x_place,
                                 'schedselect': self.job11x_schedselect,
                                 'exec_host': self.job11x_exec_host,
                                 'exec_vnode': self.job11x_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5, self.n7],
                                'job-exclusive', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # temporarily suspend momC, prevents from operating on released nodes
        self.momC.signal("-STOP")

        # Run pbs_release_nodes on nodes belonging to momB and momC
        cmd = [self.pbs_release_nodes_cmd, '-j', jid,
               self.n4, self.n5, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # mom hostB and mom hostC continuue to hold on to the job
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # since not all vnodes from momB have been freed from the job,
        # DELETE_JOB2 request from MS is not sent
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # since node <n7> from mom hostC has not been freed from the job
        # since mom is currently stopped, the DELETE_JOB2 request from
        # MS is not sent
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.

        sel_esc = self.job11x_select.replace("+", "\+")
        exec_host_esc = self.job11x_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job11x_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:ncpus=1"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job11x_exec_host.replace(
            "+%s/0" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job11x_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=1:mem=1048576kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11x_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n4> (1 cpu), <n5> (1 cpu), <n7> (1 cpu),
        # hostB hasn't released job because <n6> is still part of the job and
        # <n7> hasn't been released because the mom is stopped.

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5,
                                 self.n7], 'job-exclusive', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-exclusive', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # Stop and Start the server
        om = self.server.get_op_mode()
        self.server.set_op_mode(PTL_CLI)
        self.server.qterm(manner="immediate")
        self.server.set_op_mode(om)
        self.assertFalse(self.server.isUp())

        check_time = time.time()

        # resume momC, but this is a stale request (nothing happens)
        # since server is down.
        self.momC.signal("-CONT")

        # start the server again
        self.server.start()
        self.assertTrue(self.server.isUp())

        # make sure job is now running after server restart
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        # make sure job is running with assigned resources
        # from the original request
        self.server.expect(JOB, {'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job11x_select,
                                 'Resource_List.place': self.job11x_place,
                                 'schedselect': self.job11x_schedselect,
                                 'exec_host': self.job11x_exec_host}, id=jid)

        self.server.log_match("Job;%s;Job Run.+on exec_vnode %s" % (
                              jid, self.job11x_exec_vnode_match), regexp=True,
                              starttime=check_time)

        self.server.expect(VNODE, {'state=job-exclusive': 7},
                           count=True, max_attempts=20, interval=2)
        self.server.expect(VNODE, {'state=free': 4},
                           count=True, max_attempts=20, interval=2)

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

    def test_release_nodes_shared_server_restart_quick(self):
        """
        Test:
             Like test_release_nodes_excl_server_restart_quick test
             except the job submitted does not have exclusive
             placement, simply -l place=scatter.
             The results are the same, except the vnode states
             are either "job-busy" or "free" when there are resources
             still available to share.
        """

        jid = self.create_and_submit_job('job11')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job11_select,
                                 'Resource_List.place': self.job11_place,
                                 'schedselect': self.job11_schedselect,
                                 'exec_host': self.job11_exec_host,
                                 'exec_vnode': self.job11_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        # node <n7> is free since there's still 1 ncpus and 1 gb
        # that can be shared with other jobs
        self.match_vnode_status([self.n7], 'free', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # temporarily suspend momC, prevents from operating on released nodes
        self.momC.signal("-STOP")

        # Run pbs_release_nodes on nodes belonging to momB and momC
        cmd = [self.pbs_release_nodes_cmd, '-j', jid,
               self.n4, self.n5, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # mom hostB and mom hostC continuue to hold on to the job
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # since not all vnodes from momB have been freed from the job,
        # DELETE_JOB2 request from MS is not sent
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # since node <n7> from mom hostC has not been freed from the job
        # since mom is currently stopped, the DELETE_JOB2 request from
        # MS is not sent
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        sel_esc = self.job11_select.replace("+", "\+")
        exec_host_esc = self.job11_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job11_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:ncpus=1"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job11_exec_host.replace(
            "+%s/0" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job11_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=1:mem=1048576kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n4> (1 cpu), <n5> (1 cpu), <n7> (1 cpu),
        # hostB hasn't released job because <n6> is still part of the job and
        # <n7> hasn't been released because the mom is stopped.

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        # node <n7> is free since there's still 1 ncpus and 1 gb
        # that can be shared with other jobs
        self.match_vnode_status([self.n7], 'free', jobs_assn1,
                                1, '1048576kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # Stop and Start the server
        om = self.server.get_op_mode()
        self.server.set_op_mode(PTL_CLI)
        self.server.qterm(manner="quick")
        self.server.set_op_mode(om)
        self.assertFalse(self.server.isUp())
        self.server.start()
        self.assertTrue(self.server.isUp())

        # Job should have the same state as before
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        # parent mom of <n7> is currently in stopped state
        self.match_vnode_status([self.n7], 'state-unknown,down', jobs_assn1,
                                1, '1048576kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # resume momC
        self.momC.signal("-CONT")

        # With momC resumed, it now receives DELETE_JOB2 request from
        # MS
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

    def test_release_nodes_shared_server_restart_immed(self):
        """
        Test:
             Like test_release_nodes_excl_server_restart_quick test
             except the job submitted does not have exclusive
             placement, simply -l place=scatter.
             The results are the same, except the vnode states
             are either "job-busy" or "free" when there are resources
             still available to share.
        """

        jid = self.create_and_submit_job('job11')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job11_select,
                                 'Resource_List.place': self.job11_place,
                                 'schedselect': self.job11_schedselect,
                                 'exec_host': self.job11_exec_host,
                                 'exec_vnode': self.job11_exec_vnode}, id=jid)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        # node <n7> still has resources (ncpus=1, mem=1gb) to share
        self.match_vnode_status([self.n7], 'free', jobs_assn1,
                                1, '1048576kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        # temporarily suspend momC, prevents from operating on released nodes
        self.momC.signal("-STOP")

        # Run pbs_release_nodes on nodes belonging to momB and momC
        cmd = [self.pbs_release_nodes_cmd, '-j', jid,
               self.n4, self.n5, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # mom hostB and mom hostC continuue to hold on to the job
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostC), n=10,
            regexp=True,
            existence=False, max_attempts=5, interval=1)

        # since not all vnodes from momB have been freed from the job,
        # DELETE_JOB2 request from MS is not sent
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # since node <n7> from mom hostC has not been freed from the job
        # since mom is currently stopped, the DELETE_JOB2 request from
        # MS is not sent
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            existence=False, max_attempts=5, interval=1)

        # Verify remaining job resources.
        sel_esc = self.job11_select.replace("+", "\+")
        exec_host_esc = self.job11_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job11_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:ncpus=1"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job11_exec_host.replace(
            "+%s/0" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job11_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=1:mem=1048576kb)" % (self.n7,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        # job's substate is 41 (PRERUN) since MS mom is stopped
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '2gb',
                                 'Resource_List.ncpus': 4,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job11_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n4> (1 cpu), <n5> (1 cpu), <n7> (1 cpu),
        # hostB hasn't released job because <n6> is still part of the job and
        # <n7> hasn't been released because the mom is stopped.

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1,
                                '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        # node <n7> still has resources (ncpus=1, mem=1gb) to share
        self.match_vnode_status([self.n7], 'free', jobs_assn1,
                                1, '1048576kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

        # Stop and Start the server
        om = self.server.get_op_mode()
        self.server.set_op_mode(PTL_CLI)
        self.server.qterm(manner="immediate")
        self.server.set_op_mode(om)
        self.assertFalse(self.server.isUp())

        check_time = time.time()

        # resume momC, but this is a stale request (nothing happens)
        # since server is down.
        self.momC.signal("-CONT")

        # start the server again
        self.server.start()
        self.assertTrue(self.server.isUp())

        # make sure job is now running after server restart
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # make sure job is running with assigned resources
        # from the original request
        self.server.expect(JOB, {'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job11_select,
                                 'Resource_List.place': self.job11_place,
                                 'schedselect': self.job11_schedselect,
                                 'exec_host': self.job11_exec_host}, id=jid)

        self.server.log_match("Job;%s;Job Run.+on exec_vnode %s" % (
                              jid, self.job11x_exec_vnode_match), regexp=True,
                              starttime=check_time)

        # 7 vnodes are assigned in a shared way: 6 of them has single cpu,
        # while 1 has multiple cpus. So 6 will get "job-busy" state while
        # the other will be in "free" state like the rest.
        self.server.expect(VNODE, {'state=job-busy': 6},
                           count=True, max_attempts=20, interval=2)
        self.server.expect(VNODE, {'state=free': 5},
                           count=True, max_attempts=20, interval=2)

        self.server.expect(SERVER, {'resources_assigned.ncpus': 7,
                                    'resources_assigned.mem': '5242880kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 7,
                                   'resources_assigned.mem': '5242880kb'},
                           id="workq")

    def test_release_mgr_oper(self):
        """
        Test that nodes are getting released as manager and operator
        """

        jid = self.create_and_submit_job('job1_5')
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        self.server.manager(MGR_CMD_UNSET, SERVER, ["managers", "operators"])
        manager = str(MGR_USER) + '@*'
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (INCR, manager)},
                            sudo=True)
        operator = str(OPER_USER) + '@*'
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'operators': (INCR, operator)},
                            sudo=True)

        # Release hostC as manager
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=MGR_USER)
        self.assertEqual(ret['rc'], 0)

        # Only mom hostC will get the job summary it was released
        # early courtesy of sole vnode <n7>.
        self.momA.log_match(
            "Job;%s;%s.+cput=.+ mem=.+" % (jid, self.hostC), n=10,
            regexp=True)

        # Only mom hostC will get the IM_DELETE_JOB2 request
        self.momC.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20)

        # Release vnodes from momB as operator
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5, self.n6]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=OPER_USER)
        self.assertEqual(ret['rc'], 0)

        # momB's host will not get job summary reported
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            jid, self.hostB), n=10, regexp=True, max_attempts=5,
            existence=False, interval=1)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid,), n=20,
                            max_attempts=5, existence=False, interval=1)

        # Verify remaining job resources.
        sel_esc = self.job1_select.replace("+", "\+")
        exec_host_esc = self.job1_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        exec_vnode_esc = self.job1_exec_vnode.replace("[", "\[").replace(
            "]", "\]").replace("(", "\(").replace(")", "\)").replace("+", "\+")
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=1"

        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host.replace(
            "+%s/0*2" % (self.n7,), "")
        new_exec_host_esc = new_exec_host.replace(
            "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "+%s:mem=1048576kb:ncpus=1" % (self.n5,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+%s:ncpus=1" % (self.n6,), "")
        new_exec_vnode = new_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        new_exec_vnode_esc = \
            new_exec_vnode.replace("[", "\[").replace("]", "\]").replace(
                "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB,
                           {'job_state': 'R',
                            'Resource_List.mem': '3gb',
                            'Resource_List.ncpus': 4,
                            'Resource_List.select': newsel,
                            'Resource_List.place': self.job1_place,
                            'Resource_List.nodect': 2,
                            'schedselect': newsel,
                            'exec_host': new_exec_host,
                            'exec_vnode': new_exec_vnode},
                           id=jid,
                           runas=ROOT_USER)

        # Though the job is listed with ncpus=4 taking away released vnode
        # <n5> (1 cpu), <n6> (1 cpu), <n7> (2 cpus),
        # only <n7> got released.  <n5> and <n6> are part of a super
        # chunk that wasn't fully released.

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, new_exec_host_esc,
                                  new_exec_vnode_esc, "3145728kb",
                                  4, 2, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (jid,)
        # <n5> still job-busy
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        # <n6> still job-busy
        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        # <n7> now free
        self.match_vnode_status([self.n0, self.n7, self.n8, self.n9, self.n10],
                                'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 6,
                                    'resources_assigned.mem': '4194304kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 6,
                                   'resources_assigned.mem': '4194304kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(jid, new_exec_host))

        self.server.delete(jid, runas=ROOT_USER)

        # Check account phased end ('e') record
        self.match_accounting_log('e', jid, new_exec_host_esc,
                                  new_exec_vnode_esc,
                                  "3145728kb", 4, 2,
                                  self.job1_place,
                                  newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        self.match_accounting_log('E', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb",
                                  8, 3, self.job1_place, self.job1_sel_esc)

    def test_release_job_array(self):
        """
        Release vnodes from a job array and subjob
        """

        jid = self.create_and_submit_job('jobA')

        self.server.expect(JOB, {'job_state': 'B',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect}, id=jid)

        # Release nodes from job array. It will fail
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        try:
            ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                         sudo=True)
        except PtlExceptions as e:
            self.assertTrue("not supported for Array jobs" in e.msg)
            self.assertFalse(e.rc)

        # Verify the same for subjob1
        subjob1 = jid.replace('[]', '[1]')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode},
                           id=subjob1)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (subjob1,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6],
                                'job-busy', jobs_assn1, 1, '0kb')

        jobs_assn2 = "%s/0, %s/1" % (subjob1, subjob1)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(subjob1, self.job1_exec_host))

        # Run pbs_release_nodes as root
        cmd = [self.pbs_release_nodes_cmd, '-j', subjob1, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertEqual(ret['rc'], 0)

        # Verify mom_logs
        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            subjob1, self.hostB), n=10,
            regexp=True,
            max_attempts=5,
            existence=False, interval=1)

        self.momA.log_match("Job;%s;%s.+cput=.+ mem=.+" % (
            subjob1, self.hostC), n=10,
            regexp=True, max_attempts=5,
            existence=False, interval=1)

        # momB's host will not get DELETE_JOB2 request since
        # not all its vnodes have been released yet from the job.
        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (subjob1,),
                            n=20, max_attempts=5,
                            existence=False, interval=1)

        # Verify remaining job resources.
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_host = self.job1_exec_host

        # Below variable is being used for the accounting log match
        # which is currently blocked on PTL bug PP-596.
        # new_exec_host_esc = self.job1_exec_host.replace(
        # "*", "\*").replace("[", "\[").replace("]", "\]").replace("+", "\+")

        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=subjob1)

        # BELOW IS CODE IS BLOCEKD ON PP-596
        # Check account update ('u') record
        # self.match_accounting_log('u', subjob1, self.job1_exec_host_esc,
        #                          self.job1_exec_vnode_esc, "6gb", 8, 3,
        #                          self.job1_place,
        #                          self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        # self.match_accounting_log('c', subjob1, self.job1_exec_host_esc,
        #                          new_exec_vnode_esc, "5242880kb",
        #                          7, 3, self.job1_place, newsel_esc)

        # Check various vnode status.
        jobs_assn1 = "%s/0" % (subjob1,)
        self.match_vnode_status([self.n1, self.n2, self.n4, self.n5],
                                'job-busy', jobs_assn1, 1, '1048576kb')

        self.match_vnode_status([self.n3, self.n6], 'job-busy', jobs_assn1, 1,
                                '0kb')

        jobs_assn2 = "%s/0, %s/1" % (subjob1, subjob1)
        self.match_vnode_status([self.n7], 'job-busy', jobs_assn2,
                                2, '2097152kb')

        self.match_vnode_status([self.n0, self.n8, self.n9, self.n10], 'free')

        self.server.expect(SERVER, {'resources_assigned.ncpus': 8,
                                    'resources_assigned.mem': '6291456kb'})
        self.server.expect(QUEUE, {'resources_assigned.ncpus': 8,
                                   'resources_assigned.mem': '6291456kb'},
                           id="workq")

        self.assertTrue(
            self.pbs_nodefile_match_exec_host(subjob1, new_exec_host))

        self.server.delete(subjob1)

        # Check account phased end ('e') record
        # self.match_accounting_log('e', subjob1, new_exec_host_esc,
        #                          new_exec_vnode_esc,
        #                          "5242880kb", 7, 3,
        #                          self.job1_place,
        #                          newsel_esc)

        # Check to make sure 'E' (end of job) record got generated
        # self.match_accounting_log('E', subjob1, self.job1_exec_host_esc,
        #                          self.job1_exec_vnode_esc, "6gb",
        #                          8, 3, self.job1_place, self.job1_sel_esc)

    def test_release_job_states(self):
        """
        Release nodes on jobs in various states; Q, H, S, W
        """

        # Submit a regular job that cannot run
        a = {'Resource_List.ncpus': 100}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        # Release nodes from a queued job
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertNotEqual(ret['rc'], 0)

        self.server.delete(jid, wait=True)

        # Submit a held job and try releasing the node
        j1 = Job(TEST_USER, {ATTR_h: None})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'H'}, id=jid1)

        cmd = [self.pbs_release_nodes_cmd, '-j', jid1, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertNotEqual(ret['rc'], 0)
        self.server.delete(jid1, wait=True)

        # Submit a job in W state and try releasing the node
        mydate = int(time.time()) + 120
        mytime = convert_time('%m%d%H%M', str(mydate))
        j2 = Job(TEST_USER, {ATTR_a: mytime})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'W'}, id=jid2)

        cmd = [self.pbs_release_nodes_cmd, '-j', jid2, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertNotEqual(ret['rc'], 0)
        self.server.delete(jid2, wait=True)

    def test_release_finishjob(self):
        """
        Test that releasing vnodes on finished jobs will fail
        also verify the updated schedselect on a finished job
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': "true"}, sudo=True)

        jid = self.create_and_submit_job('job1_5')
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

        # Release hostC
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd)
        self.assertEqual(ret['rc'], 0)

        # Submit another job and make sure it is
        # picked up by hostC
        j = Job(TEST_USER,
                {'Resource_List.select': "1:host=" + self.hostC})
        jid2 = self.server.submit(j)
        ehost = self.hostC + "/1"
        self.server.expect(JOB, {'job_state': "R",
                                 "exec_host": ehost}, id=jid2)

        self.server.delete(jid, wait=True)

        # Release vnode4 from a finished job. It will throw error.
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd)
        self.assertNotEqual(ret['rc'], 0)

        # Verify the schedselect for a finished job
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=2097152kb:ncpus=3"
        new_exec_host = "%s/0*0+%s/0*0" % (self.n0, self.hostB)
        new_exec_vnode = self.job1_exec_vnode.replace(
            "+(%s:ncpus=2:mem=2097152kb)" % (self.n7,), "")
        self.server.expect(JOB, {'job_state': 'F',
                                 'Resource_List.mem': '4194304kb',
                                 'Resource_List.ncpus': 6,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 2,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           extend='x', id=jid)

    def test_release_suspendjob(self):
        """
        Test that releasing nodes on suspended job will also
        fail and schedselect will not change
        """

        jid = self.create_and_submit_job('job1_5')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n4]
        ret = self.server.du.run_cmd(self.server.hostname, cmd)
        self.assertEqual(ret['rc'], 0)

        # Verify remaining job resources
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Suspend the job with qsig
        self.server.sigjob(jid, 'suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

        # Try releasing a node from suspended job
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     sudo=True)
        self.assertNotEqual(ret['rc'], 0)

        # Verify that resources won't change
        self.server.expect(JOB, {'job_state': 'S',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

        # Release the job and make sure it is running
        self.server.sigjob(jid, 'resume')
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

    @timeout(500)
    def test_release_multi_jobs(self):
        """
        Release vnodes when multiple jobs are present
        """

        # Delete the vnodes and recreate them
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()
        self.momA.restart()
        self.momB.restart()
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostC)

        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 3},
                            id=self.hostA)
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 3},
                            id=self.hostB)
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 3},
                            id=self.hostC)

        self.server.expect(NODE, {'state=free': 3})

        # Submit multiple jobs
        jid1 = self.create_and_submit_job('job13')
        jid2 = self.create_and_submit_job('job13')
        jid3 = self.create_and_submit_job('job13')

        e_host_j1 = self.hostA + "/0+" + self.hostB + "/0+" + self.hostC + "/0"
        e_host_j2 = self.hostA + "/1+" + self.hostB + "/1+" + self.hostC + "/1"
        e_host_j3 = self.hostA + "/2+" + self.hostB + "/2+" + self.hostC + "/2"
        e_vnode = "(%s:ncpus=1)+(%s:ncpus=1)+(%s:ncpus=1)" \
            % (self.hostA, self.hostB, self.hostC)

        self.server.expect(JOB, {"job_state=R": 3})
        self.server.expect(JOB, {"exec_host": e_host_j1,
                                 "exec_vnode": e_vnode}, id=jid1)
        self.server.expect(JOB, {"exec_host": e_host_j2,
                                 "exec_vnode": e_vnode}, id=jid2)
        self.server.expect(JOB, {"exec_host": e_host_j3,
                                 "exec_vnode": e_vnode}, id=jid3)

        # Verify that 3 processes running on hostB
        n = retry = 5
        for _ in range(n):
            process = 0
            self.server.pu.get_proc_info(
                self.momB.hostname, ".*fib.*", None, regexp=True)
            if (self.server.pu.processes is not None):
                for key in self.server.pu.processes:
                    if ("fib" in key):
                        process = len(self.server.pu.processes[key])
                        self.logger.info(
                            "length of the process is " + str(process) +
                            ", expected 3")
            if process == 3:
                break
            retry -= 1
            if retry == 0:
                raise AssertionError("not found 3 fib processes")
            self.logger.info("sleeping 3 secs before next retry")
            time.sleep(3)

        # Release node2 from job1 only
        cmd = [self.pbs_release_nodes_cmd, '-j', jid1, self.hostB]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertEqual(ret['rc'], 0)

        self.momB.log_match("Job;%s;DELETE_JOB2 received" % (jid1,),
                            interval=2)

        # Verify that only 2 process left on hostB now
        process = 0
        self.server.pu.get_proc_info(
            self.momB.hostname, ".*fib.*", None, regexp=True)
        if (self.server.pu.processes is not None):
            for key in self.server.pu.processes:
                if ("fib" in key):
                    process = len(self.server.pu.processes[key])
                    self.logger.info("length of the process is %d" % process)
        self.assertEqual(process, 2)

        # Mom logs only have message for job1 for node3
        self.momA.log_match(
            "Job;%s;%s.+cput=.+mem.+" % (jid1, self.hostB),
            interval=2, regexp=True)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+mem.+" % (jid2, self.hostB),
            max_attempts=5, regexp=True,
            existence=False, interval=1)

        self.momA.log_match(
            "Job;%s;%s.+cput=.+mem.+" % (jid3, self.hostB),
            max_attempts=5, regexp=True,
            existence=False, interval=1)

        # Verify the new schedselect for job1
        new_e_host_j1 = e_host_j1.replace("+%s/0" % (self.hostB,), "")
        new_e_vnode = e_vnode.replace("+(%s:ncpus=1)" % (self.hostB,), "")
        self.server.expect(JOB, {'job_state': "R",
                                 "exec_host": new_e_host_j1,
                                 "exec_vnode": new_e_vnode,
                                 "schedselect": "1:ncpus=1+1:ncpus=1",
                                 "Resource_List.ncpus": 2,
                                 "Resource_List.nodect": 2}, id=jid1)

        # Verify that host and vnode won't change for job2 and job3
        self.server.expect(JOB, {'job_state': "R",
                                 "exec_host": e_host_j2,
                                 "exec_vnode": e_vnode,
                                 "Resource_List.nodect": 3}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R',
                                 "exec_host": e_host_j3,
                                 "exec_vnode": e_vnode,
                                 "Resource_List.nodect": 3}, id=jid3)

    def test_PBS_JOBID(self):
        """
        Test that if -j jobid is not provided then it is
        picked by env variable $PBS_JOBID in job script
        """

        # This one has a job script that calls 'pbs_release_nodes'
        # (no jobid specified)
        jid = self.create_and_submit_job('job1_6')

        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '6gb',
                                 'Resource_List.ncpus': 8,
                                 'Resource_List.nodect': 3,
                                 'Resource_List.select': self.job1_select,
                                 'Resource_List.place': self.job1_place,
                                 'schedselect': self.job1_schedselect,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': self.job1_exec_vnode}, id=jid)

        # Verify remaining job resources
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        newsel_esc = newsel.replace("+", "\+")
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n4,), "")
        new_exec_vnode_esc = new_exec_vnode.replace(
            "[", "\[").replace("]", "\]").replace(
            "(", "\(").replace(")", "\)").replace("+", "\+")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.place': self.job1_place,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': self.job1_exec_host,
                                 'exec_vnode': new_exec_vnode},
                           id=jid, interval=1)

        # Check account update ('u') record
        self.match_accounting_log('u', jid, self.job1_exec_host_esc,
                                  self.job1_exec_vnode_esc, "6gb", 8, 3,
                                  self.job1_place,
                                  self.job1_sel_esc)

        # Check to make sure 'c' (next) record got generated
        self.match_accounting_log('c', jid, self.job1_exec_host_esc,
                                  new_exec_vnode_esc, "5242880kb",
                                  7, 3, self.job1_place, newsel_esc)

    def test_release_nodes_on_stageout_diffvalues(self):
        """
        Set release_nodes_on_stageout to different values other than
        true or false
        """

        a = {ATTR_W: "release_nodes_on_stageout=-1"}
        j = Job(TEST_USER, a)
        try:
            self.server.submit(j)
        except PtlException as e:
            self.assertTrue("illegal -W value" in e.msg[0])

        a = {ATTR_W: "release_nodes_on_stageout=11"}
        j = Job(TEST_USER, a)
        try:
            self.server.submit(j)
        except PtlException as e:
            self.assertTrue("illegal -W value" in e.msg[0])

        a = {ATTR_W: "release_nodes_on_stageout=tru"}
        j = Job(TEST_USER, a)
        try:
            self.server.submit(j)
        except PtlException as e:
            self.assertTrue("illegal -W value" in e.msg[0])

    def test_resc_accumulation(self):
        """
        Test that resources gets accumulated when a mom is released
        """

        # skip this test due to PP-972
        self.skip_test(reason="Test fails due to PP-972")

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': "true"}, sudo=True)

        # Create custom resources
        attr = {}
        attr['type'] = 'float'
        attr['flag'] = 'nh'
        r = 'foo_f'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)

        attr1 = {}
        attr1['type'] = 'size'
        attr1['flag'] = 'nh'
        r1 = 'foo_i'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr1, id=r1, runas=ROOT_USER, logerr=False)

        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed epilogue hook")
if e.job.in_ms_mom():
    e.job.resources_used["vmem"] = pbs.size("9gb")
    e.job.resources_used["foo_i"] = pbs.size(999)
    e.job.resources_used["foo_f"] = 0.09
else:
    e.job.resources_used["vmem"] = pbs.size("10gb")
    e.job.resources_used["foo_i"] = pbs.size(1000)
    e.job.resources_used["foo_f"] = 0.10
"""

        hook_name = "epi"
        a = {'event': "execjob_epilogue", 'enabled': 'True'}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        jid = self.create_and_submit_job('job1_5')
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

        # Release hostC
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n7]
        ret = self.server.du.run_cmd(self.server.hostname, cmd)
        self.assertEqual(ret['rc'], 0)

        self.momC.log_match("executed epilogue hook")
        self.momC.log_match("DELETE_JOB2 received")

        self.server.delete(jid, wait=True)

        self.server.expect(JOB, {'job_state': 'F',
                                 "resources_used.foo_i": "3kb",
                                 "resources_used.foo_f": '0.29',
                                 "resources_used.vmem": '29gb'}, id=jid)

    @timeout(500)
    def test_release_reservations(self):
        """
        Release nodes from a reservation will throw error. However
        jobs inside reservation queue works as expected.
        """

        # Create a reservation on multiple nodes
        start = int(time.time()) + 30
        a = {'Resource_List.select': self.job1_select,
             'Resource_List.place': 'scatter',
             'reserve_start': start}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        rid = rid.split('.')[0]

        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")},
                           id=rid)

        # Release a vnode from reservation. It will throw error.
        cmd = [self.pbs_release_nodes_cmd, '-j', rid, self.n5]
        r = self.server.du.run_cmd(self.server.hostname, cmd)
        self.assertNotEqual(r['rc'], 0)

        # Submit a job inside reservations and release vnode
        a = {'queue': rid,
             'Resource_List.select': self.job1_select}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)

        # Wait for the job to start
        self.server.expect(JOB, {'job_state': 'R'},
                           offset=30, id=jid)

        # Release vnodes from the job
        cmd = [self.pbs_release_nodes_cmd, '-j', jid, self.n5]
        r = self.server.du.run_cmd(self.server.hostname, cmd)
        self.assertEqual(r['rc'], 0)

        # Verify the new schedselect
        newsel = "1:mem=2097152kb:ncpus=3+1:mem=1048576kb:ncpus=2+" + \
                 "1:ncpus=2:mem=2097152kb"
        new_exec_host = self.job1_exec_host
        new_exec_vnode = self.job1_exec_vnode.replace(
            "%s:mem=1048576kb:ncpus=1+" % (self.n5,), "")
        self.server.expect(JOB, {'job_state': 'R',
                                 'Resource_List.mem': '5gb',
                                 'Resource_List.ncpus': 7,
                                 'Resource_List.select': newsel,
                                 'Resource_List.nodect': 3,
                                 'schedselect': newsel,
                                 'exec_host': new_exec_host,
                                 'exec_vnode': new_exec_vnode}, id=jid)

    def test_execjob_end_called(self):
        """
        Test:
             Test to make sure when a job is removed from
             a mom host that the execjob_end hook is called on
             that mom.
        """

        # First, submit an execjob_end hook:

        hook_body = """
import pbs
pbs.logjobmsg(pbs.event().job.id, "execjob_end hook executed")
"""

        a = {'event': 'execjob_end', 'enabled': 'true'}
        self.server.create_import_hook("endjob", a, hook_body)

        # Create a multinode job request
        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Wait for the job to start
        self.server.expect(JOB, {'job_state': 'R'},
                           offset=30, id=jid)

        cmd = [self.pbs_release_nodes_cmd, '-j', jid, '-a']
        ret = self.server.du.run_cmd(self.server.hostname,
                                     cmd, runas=TEST_USER)
        self.assertEqual(ret['rc'], 0)

        # Check the sister mom log for the "execjob_end hook executed"
        self.momB.log_match("execjob_end hook executed")

        # Verify the rest of the job is still running
        self.server.expect(JOB, {'job_state': 'R'},
                           id=jid)

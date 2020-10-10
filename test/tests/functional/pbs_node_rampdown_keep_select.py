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

from collections import Counter
from copy import deepcopy
from os import name

from tests.functional import *


class n_conf:
    """
    used to define node configuration info
    """
    def __init__(self, node_a={}, node_ct=0, usenatvn=False):
        self.vnode_ct = node_ct
        self.a = node_a
        self.usenatvnode = usenatvn


class new_res:
    """
    used to define new custom resource
    """
    def __init__(self, res_name, res_a={}):
        self.res_name = res_name
        self.a = res_a


class test_config:
    """
    used to store config of a test case
    """
    def __init__(self, qsub_sel, keep_sel, sched_sel, expected_res, job_stat,
                 rel_user, qsub_sel_after, sched_sel_after, job_stat_after,
                 expected_res_after, skip_vnode_status_check=False,
                 use_script=False):
        self.qsub_sel = qsub_sel
        self.keep_sel = keep_sel
        self.sched_sel = sched_sel
        self.expected_res = expected_res
        self.job_stat = job_stat
        self.rel_user = rel_user
        self.qsub_sel_after = qsub_sel_after
        self.sched_sel_after = sched_sel_after
        self.job_stat_after = job_stat_after
        self.expected_res_after = expected_res_after
        self.skip_vnode_status_check = skip_vnode_status_check
        self.use_script = use_script


@requirements(num_moms=5)
class TestPbsNodeRampDownKeepSelect(TestFunctional):
    """
    This tests the Node Rampdown Feature's extension called keep_select,
    where while a job is running, nodes/resources assigned on non-mother
    superior can be released by specifying a subselect.

    Custom parameters:
    moms: colon-separated hostnames of five MoMs
    """

    res_s_h = {'type': 'string', 'flag': 'h'}
    res_b_h = {'type': 'boolean', 'flag': 'h'}
    res_l_nh = {'type': 'long', 'flag': 'nh'}
    res_sz_nh = {'type': 'size', 'flag': 'nh'}
    res_f_nh = {'type': 'float', 'flag': 'nh'}

    def pbs_nodefile_match_exec_host(self, jid, ehost, schedselect=None):
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
                ch_ct = '1'
                chl = chunk.split(':')
                if chl[0].isnumeric():
                    ch_ct = chl[0]
                    del chl[0]
                for x in range(int(ch_ct)):
                    tmpmpi = '1'
                    for ch in chl:
                        if ch.find('=') != -1:
                            c = ch.split('=')
                            if c[0] == "mpiprocs":
                                tmpmpi = c[1]
                    mpiprocs.append(tmpmpi)
        first_host = ehost[0]

        cmd = ['cat', pbs_nodefile]
        ret = self.server.du.run_cmd(first_host, cmd, sudo=False)
        ehost2 = []
        for h in ret['out']:
            ehost2.append(h.split('.')[0])

        ehost1 = []
        for (eh, mpin) in zip(ehost, mpiprocs):
            for k in range(int(mpin)):
                ehost1.append(eh)

        self.assertEqual(Counter(ehost1), Counter(ehost2),
                         'PBS_NODEFILE match failed')

    def match_vnode_status(self, vnode_list, state, ncpus=None, jobs=None,
                           mem=None):
        """
        Given a list of vnode names in 'vnode_list', check to make
        sure each vnode's state, jobs string, resources_assigned.mem,
        and resources_assigned.ncpus match the passed arguments.
        This will throw an exception if a match is not found.
        """
        if ncpus is None:
            if state == 'free':
                ncpus = [0 for x in range(len(vnode_list))]
            else:
                ncpus = [None for x in range(len(vnode_list))]
        for (vn, cpus) in zip(vnode_list, ncpus):
            dict_match = {'state': state}
            if jobs is not None:
                dict_match['jobs'] = jobs
            if cpus is not None:
                dict_match['resources_assigned.ncpus'] = cpus
            if mem is not None:
                dict_match['resources_assigned.mem'] = mem

            self.server.expect(VNODE, dict_match, id=vn)

    def create_res(self, res_list):
        """
        creates custom resources
        """
        for res in res_list:
            self.server.manager(MGR_CMD_CREATE, RSC, res.a, id=res.res_name)

    def config_nodes(self, node_conf):
        """
        configures nodes as per the node_conf list parameter
        """
        self.mom_list = []
        self.vnode_dict = {}
        # Now start setting up and creating the vnodes

        for (mom, conf) in zip(self.momArr, node_conf):
            if mom.has_vnode_defs():
                mom.delete_vnode_defs()
            start_time = time.time()
            mom.create_vnodes(conf.a, conf.vnode_ct,
                              delall=False,
                              usenatvnode=conf.usenatvnode)
            self.vnode_dict[mom.shortname] = {'mom': mom,
                                              'res': conf}
            vn_ct = conf.vnode_ct
            if conf.usenatvnode:
                vn_ct -= 1
            elif vn_ct:
                self.vnode_dict[mom.shortname]['res'] = None
            vstat = deepcopy(conf.a)
            vstat['state'] = 'free'
            for n in range(vn_ct):
                vnid = mom.shortname + '[' + str(n) + ']'
                self.server.expect(NODE, id=vnid, attrib=vstat)
                self.vnode_dict[vnid] = {'mom': mom,
                                         'res': conf}
            if not conf.usenatvnode:
                if not vn_ct:
                    nvstat = deepcopy(conf.a)
                else:
                    nvstat = {}
                nvstat['state'] = 'free'
                self.server.expect(NODE, id=mom.shortname, attrib=nvstat)
            mom.log_match("copy hook-related file request received",
                          starttime=start_time)
            self.mom_list.append(mom)

    def setUp(self):

        if len(self.moms) != 5:
            self.skip_test(reason="need 5 mom hosts: " +
                           "-p moms=<m1>:<m2>:<m3>:<m4>:<m5>")

        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

        self.server.cleanup_jobs()

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momC = self.moms.values()[2]
        self.momD = self.moms.values()[3]
        self.momE = self.moms.values()[4]

        self.momArr = [self.momA, self.momB, self.momC, self.momD, self.momE]

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.momC.shortname
        self.hostD = self.momD.shortname
        self.hostE = self.momE.shortname

        self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        if sys.platform in ('cygwin', 'win32'):
            SLEEP_CMD = "pbs-sleep"
        else:
            SLEEP_CMD = "/bin/sleep"

        self.rel_nodes_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_release_nodes')

    def tearDown(self):
        self.momA.signal(self.momA, "-CONT")
        self.momB.signal(self.momB, "-CONT")
        self.momC.signal(self.momC, "-CONT")
        self.momD.signal(self.momD, "-CONT")
        self.momE.signal(self.momE, "-CONT")
        TestFunctional.tearDown(self)
        # Delete managers and operators if added
        attrib = ['operators', 'managers']
        self.server.manager(MGR_CMD_UNSET, SERVER, attrib)

    def flatten_node_res(self, nc_list):
        """
        returns a list of flattened node resource dictionary
        """
        ret = []
        for nc in nc_list:
            ret.append(','.join("%s=%r" % (key, val) for key, val in
                                sorted(nc.a.items())))
        return ret

    def get_mom_vn_execvn(self, execvnode):
        """
        will get vnode list and corresponding mom list from
        the execvnode paramter
        """
        mlist = []
        vlist = []
        for chunk in execvnode:
            if chunk.vchunk:
                mlist.append(self.vnode_dict[chunk.vchunk[0].vnode]
                             ['mom'].shortname)
                for vch in chunk.vchunk:
                    vlist.append(vch.vnode)
            else:
                mlist.append(self.vnode_dict[chunk.vnode]['mom'].shortname)
                vlist.append(chunk.vnode)
        return (mlist, vlist)

    def common_tc_flow(self, tc):
        """
        Defines a common test case flow, the configuration of a test case is
        passed using the 'tc' argument
        """
        # 1. submit the job wih select spec
        job = Job(TEST_USER, attrs={'Resource_List.select': tc.qsub_sel})
        if tc.use_script is True:
            job.create_script(self.jobscript)
        else:
            job.set_sleep_time(1000)
        jid = self.server.submit(job)

        # 2. validate job state and attributes.
        self.server.expect(JOB, tc.job_stat, id=jid)
        js = self.server.status(JOB, [ATTR_execvnode, ATTR_exechost], jid)[0]

        # 3. extract vnode list and mom list from execvnode
        (mlist, vlist) = self.get_mom_vn_execvn(job.execvnode())
        actual_res = self.flatten_node_res([self.vnode_dict[vn]['res'] for vn
                                            in vlist])

        # 4. compare actual resources allocated vs expected
        self.assertEqual(Counter(tc.expected_res), Counter(actual_res),
                         'Actual Vnode resources are not as expected')

        # 5. validate hostnames in exechost correspond to vnodes in execvnode
        self.assertEqual(Counter(mlist),
                         Counter([list(x.keys())[0] for x in
                                  job.exechost().hosts]),
                         'exechost failed to correspond with execvnode')

        # 6. check assigned vnodes are in job-busy state
        self.match_vnode_status(vlist, 'job-busy',
                                [self.vnode_dict[x]['res'].a[
                                 'resources_available.ncpus'] for x in vlist])

        # 7. validate PBS_NODEFILE
        self.pbs_nodefile_match_exec_host(jid, mlist, tc.sched_sel)

        # 8. (drum rolls) submit release node command
        if tc.use_script is False:
            cmd = [self.rel_nodes_cmd, '-j', jid, '-k', tc.keep_sel]
            ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                         runas=tc.rel_user)
            self.assertEqual(ret['rc'], 0)
        else:
            self.server.sigjob(jid, 'INT')

        # 9. verify job state and attributes are as expected
        self.server.expect(JOB, tc.job_stat_after, id=jid)

        js = self.server.status(JOB, [ATTR_execvnode, ATTR_exechost], jid)[0]

        # 10. extract vnode list and mom list from execvnode
        (mlist_new, vlist_new) = self.get_mom_vn_execvn(job.execvnode())
        actual_res_after = self.flatten_node_res([self.vnode_dict[vn]['res']
                                                  for vn in vlist_new])

        # 11. compare actual resources allocated vs expected
        self.assertEqual(Counter(tc.expected_res_after),
                         Counter(actual_res_after),
                         'Actual Vnode resources are not as expected')

        # 12. validate hostnames in exechost correspond to vnodes in execvnode
        self.assertEqual(Counter(mlist_new),
                         Counter([list(x.keys())[0] for x in
                                 job.exechost().hosts]),
                         'exechost failed to correspond with execvnode')

        if tc.skip_vnode_status_check is False:
            # 13. check assigned vnodes are in job-busy state
            self.match_vnode_status(vlist_new, 'job-busy',
                                    [self.vnode_dict[x]['res'].a[
                                     'resources_available.ncpus'] for x in
                                     vlist_new])

            # 14. compute freed vnodes resource list
            freed_res = list(set(vlist) - set(vlist_new))

            # 15. check freed vnodes are in 'free' state
            self.match_vnode_status(freed_res, 'free')

        # 16. validate PBS_NODEFILE again
        self.pbs_nodefile_match_exec_host(jid, mlist_new, tc.sched_sel_after)

    def test_basic_use_case_ncpus(self, rel_user=TEST_USER, use_script=False):
        """
        submit job with below select string
        'select=ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2'
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=2+ncpus=3:mpiprocs=2'
        """
        n1 = n_conf({'resources_available.ncpus': '1'})
        n2 = n_conf({'resources_available.ncpus': '2'})
        n3 = n_conf({'resources_available.ncpus': '3'})

        nc_list = [n1, n2, n2, n3, n3]
        # 1. configure the cluster
        self.config_nodes(nc_list)

        args = {
            'qsub_sel': 'ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2',
            'keep_sel': 'select=ncpus=2+ncpus=3:mpiprocs=2',
            'sched_sel': '1:ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': rel_user,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2+1:ncpus=3:mpiprocs=2',
            'sched_sel_after': '1:ncpus=1+1:ncpus=2+1:ncpus=3:mpiprocs=2',
            'expected_res_after': self.flatten_node_res([n1, n2, n3])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.mpiprocs': 4,
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.mpiprocs': 2,
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        if use_script is True:
            args['use_script'] = True

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_basic_use_case_ncpus_as_root(self):
        """
        submit job with below select string
        'select=ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2'
        as root release nodes except the MS and nodes matching below sub
        select string 'select=ncpus=2+ncpus=3:mpiprocs=2'
        """
        self.test_basic_use_case_ncpus(rel_user=ROOT_USER)

    def test_basic_use_case_ncpus_using_script(self):
        """
        Like test_basic_use_case_ncpus test except instead of calling
        pbs_release_nodes from a command line, it is executed
        inside the job script of a running job. Same results.
        """
        self.jobscript = \
            "#!/bin/sh\n" + \
            "trap 'pbs_release_nodes -k select=ncpus=2+ncpus=3:mpiprocs=2" + \
            ";sleep 1000;exit 0' 2\n" + \
            "sleep 1000\n" + \
            "exit 0"
        self.test_basic_use_case_ncpus(use_script=True)

    def test_with_a_custom_str_res(self, partial_res_list=False):
        """
        submit job with select string containing a custom string resource
        'select=ncpus=1+ncpus=2:model=abc+ncpus=2:model=def+ncpus=3:model=def+
        ncpus=3:model=xyz'
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=2:model=def+ncpus=3:model=def'
        """
        # 1. create a custom string resources
        str_res = 'model'
        model_a = 'abc'
        model_b = 'def'
        model_c = 'xyz'
        self.create_res([new_res(str_res, self.res_s_h)])

        # 2. add the custom resource to sched_config
        self.scheduler.add_resource(str_res)

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2_a = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+str_res: model_a})
        n2_b = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+str_res: model_b})
        n3_b = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+str_res: model_b})
        n3_c = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+str_res: model_c})

        nc_list = [n1, n2_a, n2_b, n3_b, n3_c]
        # 3. configure the cluster
        self.config_nodes(nc_list)

        if partial_res_list is False:
            keep_sel = ('select=ncpus=2:model='+model_b +
                        '+ncpus=3:model='+model_b)
        else:
            keep_sel = 'select=2:model='+model_b

        args = {
            'qsub_sel': 'ncpus=1+ncpus=2:model='+model_a+'+ncpus=2:model=' +
            model_b+'+ncpus=3:model='+model_b+'+ncpus=3:model='+model_c,
            'keep_sel': keep_sel,
            'sched_sel': '1:ncpus=1+1:ncpus=2:model='+model_a +
            '+1:ncpus=2:model='+model_b+'+1:ncpus=3:model='+model_b +
            '+1:ncpus=3:model='+model_c,
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2:model='+model_b +
            '+1:ncpus=3:model='+model_b,
            'sched_sel_after': '1:ncpus=1+1:ncpus=2:model='+model_b +
            '+1:ncpus=3:model='+model_b,
            'expected_res_after': self.flatten_node_res([n1, n2_b, n3_b])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_with_a_custom_str_res_partial_list(self, partial_res_list=False):
        """
        submit job with select string containing a custom string resource
        'select=ncpus=1+ncpus=2:model=abc+ncpus=2:model=def+ncpus=3:model=def+
        ncpus=3:model=xyz'
        release nodes except the MS and nodes matching below sub select string
        containing partial resource list
        'select=2:model=def'
        """
        self.test_with_a_custom_str_res(partial_res_list=True)

    def test_with_a_custom_bool_res(self, partial_res_list=False):
        """
        submit job with select string containing a custom boolean resource
        'select=ncpus=1+ncpus=2:bigmem=true+ncpus=2+
        ncpus=3:bigmem=true+ncpus=3'
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=2:bigmem=true+ncpus=3:bigmem=true'
        """
        # 1. create a custom string resources
        bool_res = 'bigmem'
        self.create_res([new_res(bool_res, self.res_b_h)])

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2_a = n_conf({'resources_available.ncpus': '2'})
        n2_b = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+bool_res: 'True'})
        n3_b = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+bool_res: 'True'})
        n3_c = n_conf({'resources_available.ncpus': '3'})

        nc_list = [n1, n2_a, n2_b, n3_b, n3_c]
        # 2. configure the cluster
        self.config_nodes(nc_list)

        if partial_res_list is False:
            keep_sel = ('select=ncpus=2:'+bool_res+'=true+ncpus=3:' +
                        bool_res+'=true')
        else:
            keep_sel = 'select=2:'+bool_res+'=true'

        args = {
            'qsub_sel': 'ncpus=1+ncpus=2:'+bool_res+'=true+ncpus=2+ncpus=3:' +
            bool_res+'=true+ncpus=3',
            'keep_sel': keep_sel,
            'sched_sel': '1:ncpus=1+1:ncpus=2:'+bool_res +
            '=True+1:ncpus=2+1:ncpus=3:'+bool_res+'=True+1:ncpus=3',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2:'+bool_res +
            '=True+1:ncpus=3:'+bool_res+'=True',
            'sched_sel_after': '1:ncpus=1+1:ncpus=2:'+bool_res +
            '=True+1:ncpus=3:'+bool_res+'=True',
            'expected_res_after': self.flatten_node_res([n1, n2_b, n3_b])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_with_a_custom_bool_res_partial_list(self,
                                                 partial_res_list=False):
        """
        submit job with select string containing a boolean resource
        'select=ncpus=1+ncpus=2:bigmem=true+ncpus=2+
        ncpus=3:bigmem=true+ncpus=3'
        release nodes except the MS and nodes matching below sub select string
        containing partial resource list
        'select=2:bigmem=true'
        """
        self.test_with_a_custom_bool_res(partial_res_list=True)

    def test_with_a_custom_long_res(self, partial_res_list=False):
        """
        submit job with select string containing a custom long resource
        'select=ncpus=1+ncpus=2:longres=7+ncpus=2:longres=9+
        ncpus=3:longres=9+ncpus=3:longres=10'
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=2:longres=9+ncpus=3:longres=9'
        """
        # 1. create a custom string resources
        long_res = 'longres'
        self.create_res([new_res(long_res, self.res_l_nh)])

        # 2. add the custom resource to sched_config
        self.scheduler.add_resource(long_res)

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2_a = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+long_res: '7'})
        n2_b = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+long_res: '9'})
        n3_b = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+long_res: '9'})
        n3_c = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+long_res: '10'})

        nc_list = [n1, n2_a, n2_b, n3_b, n3_c]
        # 3. configure the cluster
        self.config_nodes(nc_list)

        if partial_res_list is False:
            keep_sel = ('select=ncpus=2:'+long_res+'=9+ncpus=3:' +
                        long_res+'=9')
        else:
            keep_sel = 'select=2:'+long_res+'=9'

        args = {
            'qsub_sel': 'ncpus=1+ncpus=2:'+long_res+'=7+ncpus=2:'+long_res +
            '=9+ncpus=3:'+long_res+'=9+ncpus=3:'+long_res+'=10',
            'keep_sel': keep_sel,
            'sched_sel': '1:ncpus=1+1:ncpus=2:'+long_res+'=7+1:ncpus=2:' +
            long_res+'=9+1:ncpus=3:'+long_res+'=9+1:ncpus=3:'+long_res+'=10',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2:'+long_res +
            '=9+1:ncpus=3:'+long_res+'=9',
            'sched_sel_after': '1:ncpus=1+1:ncpus=2:'+long_res +
            '=9+1:ncpus=3:'+long_res+'=9',
            'expected_res_after': self.flatten_node_res([n1, n2_b, n3_b])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.longres': 35,
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.longres': 18,
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_with_a_custom_long_partial_list(self, partial_res_list=False):
        """
        submit job with select string containing a custom long resource
        'select=ncpus=1+ncpus=2:longres=7+ncpus=2:longres=9+
        ncpus=3:longres=9+ncpus=3:longres=10'
        release nodes except the MS and nodes matching below sub select string
        containing partial resource list
        'select=2:longres=9'
        """
        self.test_with_a_custom_long_res(partial_res_list=True)

    def test_with_a_custom_size_res(self, partial_res_list=False):
        """
        submit job with select string containing a custom size resource
        'select=ncpus=1+ncpus=2:sizres=7k+ncpus=2:sizres=9k+
        ncpus=3:sizres=9k+ncpus=3:sizres=10k'
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=2:sizres=9k+ncpus=3:sizres=9k'
        """
        # 1. create a custom string resources
        size_res = 'sizres'
        self.create_res([new_res(size_res, self.res_sz_nh)])

        # 2. add the custom resource to sched_config
        self.scheduler.add_resource(size_res)

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2_a = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+size_res: '7kb'})
        n2_b = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+size_res: '9kb'})
        n3_b = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+size_res: '9kb'})
        n3_c = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+size_res: '10kb'})

        nc_list = [n1, n2_a, n2_b, n3_b, n3_c]
        # 3. configure the cluster
        self.config_nodes(nc_list)

        if partial_res_list is False:
            keep_sel = ('select=ncpus=2:'+size_res+'=9k+ncpus=3:' +
                        size_res+'=9k')
        else:
            keep_sel = 'select=2:'+size_res+'=9k'

        args = {
            'qsub_sel': 'ncpus=1+ncpus=2:'+size_res+'=7k+ncpus=2:'+size_res +
            '=9k+ncpus=3:'+size_res+'=9k+ncpus=3:'+size_res+'=10k',
            'keep_sel': keep_sel,
            'sched_sel': '1:ncpus=1+1:ncpus=2:'+size_res+'=7kb+1:ncpus=2:' +
            size_res+'=9kb+1:ncpus=3:'+size_res+'=9kb+1:ncpus=3:'+size_res +
            '=10kb',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2:'+size_res +
            '=9kb+1:ncpus=3:'+size_res+'=9kb',
            'sched_sel_after': '1:ncpus=1+1:ncpus=2:'+size_res +
            '=9kb+1:ncpus=3:'+size_res+'=9kb',
            'expected_res_after': self.flatten_node_res([n1, n2_b, n3_b])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.sizres': '35kb',
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.sizres': '18kb',
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_with_a_custom_size_partial_list(self, partial_res_list=False):
        """
        submit job with select string containing a custom size resource
        'select=ncpus=1+ncpus=2:sizres=7k+ncpus=2:sizres=9k+
        ncpus=3:sizres=9k+ncpus=3:sizres=10k'
        release nodes except the MS and nodes matching below sub select string
        containing partial resource list
        'select=2:sizres=9k'
        """
        self.test_with_a_custom_size_res(partial_res_list=True)

    def test_with_a_custom_float_res(self, partial_res_list=False):
        """
        submit job with select string containing a custom float resource
        'select=ncpus=1+ncpus=2:fltres=7.1+ncpus=2:fltres=9.1+
        ncpus=3:fltres=9.1+ncpus=3:fltres=10.1'
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=2:fltres=9.1+ncpus=3:fltres=9.1'
        """
        # 1. create a custom string resources
        float_res = 'fltres'
        self.create_res([new_res(float_res, self.res_f_nh)])

        # 2. add the custom resource to sched_config
        self.scheduler.add_resource(float_res)

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2_a = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+float_res: '7.1'})
        n2_b = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+float_res: '9.1'})
        n3_b = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+float_res: '9.1'})
        n3_c = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+float_res: '10.1'})

        nc_list = [n1, n2_a, n2_b, n3_b, n3_c]
        # 3. configure the cluster
        self.config_nodes(nc_list)

        if partial_res_list is False:
            keep_sel = ('select=ncpus=2:'+float_res+'=9.1+ncpus=3:' +
                        float_res+'=9.1')
        else:
            keep_sel = 'select=2:'+float_res+'=9.1'

        args = {
            'qsub_sel': 'ncpus=1+ncpus=2:'+float_res+'=7.1+ncpus=2:' +
            float_res+'=9.1+ncpus=3:'+float_res+'=9.1+ncpus=3:' +
            float_res+'=10.1',
            'keep_sel': keep_sel,
            'sched_sel': '1:ncpus=1+1:ncpus=2:'+float_res+'=7.1+1:ncpus=2:' +
            float_res+'=9.1+1:ncpus=3:'+float_res+'=9.1+1:ncpus=3:'+float_res +
            '=10.1',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2:'+float_res +
            '=9.1+1:ncpus=3:'+float_res+'=9.1',
            'sched_sel_after': '1:ncpus=1+1:ncpus=2:'+float_res +
            '=9.1+1:ncpus=3:'+float_res+'=9.1',
            'expected_res_after': self.flatten_node_res([n1, n2_b, n3_b])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.fltres': '35.4',
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.fltres': '18.2',
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_with_a_custom_float_partial_list(self, partial_res_list=False):
        """
        submit job with select string containing a custom float resource
        'select=ncpus=1+ncpus=2:fltres=7.1+ncpus=2:fltres=9.1+
        ncpus=3:fltres=9.1+ncpus=3:fltres=10.1'
        release nodes except the MS and nodes matching below sub select string
        containing partial resource list
        'select=2:fltres=9.1'
        """
        self.test_with_a_custom_float_res(partial_res_list=True)

    def test_with_mixed_custom_res(self, partial_res_list=False):
        """
        submit job with select string containing a mix of all types of
        custom resources
        'select=ncpus=1+ncpus=2:model=abc:longres=7:sizres=7k:fltres=7.1+
        ncpus=2:model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1+ncpus=3:
        model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1+ncpus=3:
        model=xyz:longres=10:sizres=10k:fltres=10.1'
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=2:model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1+
        ncpus=3:model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1'
        """
        # 1. create a custom string resources
        str_res = 'model'
        model_a = 'abc'
        model_b = 'def'
        model_c = 'xyz'
        bool_res = 'bigmem'
        long_res = 'longres'
        size_res = 'sizres'
        float_res = 'fltres'

        self.create_res(
            [
                new_res(str_res, self.res_s_h),
                new_res(bool_res, self.res_b_h),
                new_res(long_res, self.res_l_nh),
                new_res(size_res, self.res_sz_nh),
                new_res(float_res, self.res_f_nh)
            ])

        # 2. add the custom resource to sched_config
        self.scheduler.add_resource(str_res)
        self.scheduler.add_resource(long_res)
        self.scheduler.add_resource(size_res)
        self.scheduler.add_resource(float_res)

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2_a = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+str_res: model_a,
                       'resources_available.'+long_res: '7',
                       'resources_available.'+size_res: '7kb',
                       'resources_available.'+float_res: '7.1'})
        n2_b = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+str_res: model_b,
                       'resources_available.'+bool_res: 'True',
                       'resources_available.'+long_res: '9',
                       'resources_available.'+size_res: '9kb',
                       'resources_available.'+float_res: '9.1'})
        n3_b = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+str_res: model_b,
                       'resources_available.'+bool_res: 'True',
                       'resources_available.'+long_res: '9',
                       'resources_available.'+size_res: '9kb',
                       'resources_available.'+float_res: '9.1'})
        n3_c = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+str_res: model_c,
                       'resources_available.'+long_res: '10',
                       'resources_available.'+size_res: '10kb',
                       'resources_available.'+float_res: '10.1'})

        nc_list = [n1, n2_a, n2_b, n3_b, n3_c]
        # 3. configure the cluster
        self.config_nodes(nc_list)

        if partial_res_list is False:
            keep_sel = ('select=ncpus=2:model='+model_b+':' +
                        bool_res+'=true:'+long_res+'=9:'+size_res+'=9k:' +
                        float_res+'=9.1+ncpus=3:model='+model_b+':'+bool_res +
                        '=true:'+long_res+'=9:'+size_res+'=9k:'+float_res +
                        '=9.1')
        else:
            keep_sel = 'select=2:'+bool_res+'=true'

        args = {
            'qsub_sel': 'ncpus=1+ncpus=2:model='+model_a+':'+long_res+'=7:' +
            size_res+'=7k:'+float_res+'=7.1+ncpus=2:model='+model_b+':' +
            bool_res+'=true:'+long_res+'=9:'+size_res+'=9k:'+float_res +
            '=9.1+ncpus=3:model='+model_b+':'+bool_res+'=true:'+long_res +
            '=9:'+size_res+'=9k:'+float_res+'=9.1+ncpus=3:model='+model_c +
            ':'+long_res+'=10:'+size_res+'=10k:'+float_res+'=10.1',
            'keep_sel': keep_sel,
            'sched_sel': '1:ncpus=1+1:ncpus=2:model='+model_a+':'+long_res +
            '=7:'+size_res+'=7kb:'+float_res+'=7.1+1:ncpus=2:model='+model_b +
            ':'+bool_res+'=True:'+long_res+'=9:'+size_res+'=9kb:'+float_res +
            '=9.1+1:ncpus=3:model='+model_b+':'+bool_res+'=True:'+long_res +
            '=9:'+size_res+'=9kb:'+float_res+'=9.1+1:ncpus=3:model='+model_c +
            ':'+long_res+'=10:'+size_res+'=10kb:'+float_res+'=10.1',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2:model=' +
            model_b+':'+bool_res+'=True:'+long_res+'=9:'+size_res +
            '=9kb:'+float_res +
            '=9.1+1:ncpus=3:model='+model_b+':'+bool_res+'=True:'+long_res +
            '=9:'+size_res+'=9kb:'+float_res+'=9.1',
            'sched_sel_after': '1:ncpus=1+1:ncpus=2:model=' +
            model_b+':'+bool_res+'=True:'+long_res+'=9:'+size_res+'=9kb:' +
            float_res+'=9.1+1:ncpus=3:model='+model_b+':'+bool_res+'=True:' +
            long_res+'=9:'+size_res+'=9kb:'+float_res+'=9.1',
            'expected_res_after': self.flatten_node_res([n1, n2_b, n3_b])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.longres': 35,
                    'Resource_List.fltres': '35.4',
                    'Resource_List.sizres': '35kb',
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.longres': 18,
                          'Resource_List.sizres': '18kb',
                          'Resource_List.fltres': '18.2',
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_with_mixed_custom_res_partial_list(self, partial_res_list=False):
        """
        submit job with select string containing a mix of all types of
        custom resources
        'select=ncpus=1+ncpus=2:model=abc:longres=7:sizres=7k:fltres=7.1+
        ncpus=2:model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1+ncpus=3:
        model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1+ncpus=3:
        model=xyz:longres=10:sizres=10k:fltres=10.1'
        release nodes except the MS and nodes matching below sub select string
        containing partial resource list
        'select=2:bigmem=true'
        """
        self.test_with_mixed_custom_res(partial_res_list=True)

    def test_schunk_use_case(self, release_partial_schunk=False):
        """
        submit job with below select string
        'ncpus=1+2:ncpus=6+2:ncpus=9:mpiprocs=2'
        cluster is configured such that we get 4 superchunks
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=6+ncpus=9:mpiprocs=2'
        so that whole super chunks are released or kept
        """
        n1 = n_conf({'resources_available.ncpus': '1'})
        n2 = n_conf({'resources_available.ncpus': '2'}, 3)
        n3 = n_conf({'resources_available.ncpus': '3'}, 3)

        nc_list = [n1, n2, n2, n3, n3]
        # 1. configure the cluster
        self.config_nodes(nc_list)

        if release_partial_schunk is False:
            keep_sel = 'select=ncpus=6+ncpus=9:mpiprocs=2'
            expected_res_list = [n1, n2, n2, n2, n3, n3, n3]
        else:
            keep_sel = 'select=ncpus=4+ncpus=6:mpiprocs=2'
            expected_res_list = [n1, n2, n2, n3, n3]

        args = {
            'qsub_sel': 'ncpus=1+2:ncpus=6+2:ncpus=9:mpiprocs=2',
            'keep_sel': keep_sel,
            'sched_sel': '1:ncpus=1+2:ncpus=6+2:ncpus=9:mpiprocs=2',
            'expected_res': self.flatten_node_res(
                [n1, n2, n2, n2, n2, n2, n2, n3, n3, n3, n3, n3, n3]),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=6+1:ncpus=9:mpiprocs=2',
            'sched_sel_after': '1:ncpus=1+1:ncpus=6+1:ncpus=9:mpiprocs=2',
            'expected_res_after': self.flatten_node_res(expected_res_list)
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.mpiprocs': 4,
                    'Resource_List.ncpus': 31,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.mpiprocs': 2,
                          'Resource_List.ncpus': 16,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        if release_partial_schunk is True:
            args['skip_vnode_status_check'] = True

        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_schunk_partial_release_use_case(self):
        """
        submit job with below select string
        'ncpus=1+2:ncpus=6+2:ncpus=9:mpiprocs=2'
        cluster is configured such that we get 4 superchungs
        release nodes except the MS and nodes matching below sub select string
        'select=ncpus=4+ncpus=6:mpiprocs=2'
        so that some vnodes of super chunks are released or kept
        """
        self.test_schunk_use_case(release_partial_schunk=True)

    def test_release_nodes_error(self):
        """
        Tests erroneous cases:
        1. pbs_release_nodes -j <job-id> -a -k <select>
            "pbs_release_nodes: -a and -k options cannot be used together"
        2. pbs_release_nodes -j <job-id> -k <select> <node1>...
            "pbs_release_nodes: cannot supply node list with -k option"
        3. pbs_release_nodes -j <job-id> -k place=scatter
            "pbs_release_nodes: only a "select=" string is valid in -k option"
        4. pbs_release_nodes -j <job-id> -k <select containing undefined res>
            "pbs_release_nodes: Unknown resource: <undefined res name>"
        5. pbs_release_nodes -j <job-id> -k <unsatisfying/non-sub select>
            "pbs_release_nodes: Server returned error 15010 for job"
        6. pbs_release_nodes -j <job-id> -k <high node count>
            "pbs_release_nodes: Server returned error 15010 for job"
        """

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2 = n_conf({'resources_available.ncpus': '2'})
        n3 = n_conf({'resources_available.ncpus': '3'})

        nc_list = [n1, n2, n2, n3, n3]
        self.config_nodes(nc_list)
        qsub_sel = 'ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2'
        keep_sel = 'select=ncpus=2+ncpus=3:mpiprocs=2'
        job = Job(TEST_USER, attrs={'Resource_List.select': qsub_sel})
        job.set_sleep_time(1000)
        jid = self.server.submit(job)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # 1. "pbs_release_nodes: -a and -k options cannot be used together"
        cmd = [self.rel_nodes_cmd, '-j', jid, '-a', '-k', keep_sel]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: -a and -k options cannot be used together'))

        # 2. "pbs_release_nodes: cannot supply node list with -k option"
        cmd = [self.rel_nodes_cmd, '-j', jid, '-k', keep_sel,
               list(self.vnode_dict.keys())[2]]
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: cannot supply node list with -k option'))

        # 3. "pbs_release_nodes: only a "select=" string is valid in -k option"
        cmd = [self.rel_nodes_cmd, '-j', jid, '-k', 'place=scatter']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: only a "select=" string is valid in -k option'
            ))

        # 4. "pbs_release_nodes: Unknown resource: <undefined res name>"
        cmd = [self.rel_nodes_cmd, '-j', jid, '-k',
               'select=ncpus=2:unkownres=3']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: Unknown resource: unkownres'))

        # 5. "pbs_release_nodes: Server returned error 15010 for job"
        cmd = [self.rel_nodes_cmd, '-j', jid, '-k', 'select=ncpus=4']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: Server returned error 15010 for job'))

        # 6. "pbs_release_nodes: Server returned error 15010 for job"
        cmd = [self.rel_nodes_cmd, '-j', jid, '-k', '5']
        ret = self.server.du.run_cmd(self.server.hostname, cmd,
                                     runas=TEST_USER)
        self.assertNotEqual(ret['rc'], 0)
        self.assertTrue(ret['err'][0].startswith(
            'pbs_release_nodes: Server returned error 15010 for job'))

    def test_node_count(self, rel_user=TEST_USER, use_script=False):
        """
        submit job with below select string
        'select=ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2'
        release nodes except the MS and 2 nodes
        """
        n1 = n_conf({'resources_available.ncpus': '1'})
        n2 = n_conf({'resources_available.ncpus': '2'})
        n3 = n_conf({'resources_available.ncpus': '3'})

        nc_list = [n1, n2, n2, n3, n3]
        # 1. configure the cluster
        self.config_nodes(nc_list)

        args = {
            'qsub_sel': 'ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2',
            'keep_sel': '2',
            'sched_sel': '1:ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': rel_user,
            'qsub_sel_after': '1:ncpus=1+2:ncpus=2',
            'sched_sel_after': '1:ncpus=1+2:ncpus=2',
            'expected_res_after': self.flatten_node_res([n1, n2, n2])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.mpiprocs': 4,
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.ncpus': 5,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        if use_script is True:
            args['use_script'] = True

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_node_count_as_root(self):
        """
        submit job with below select string
        'select=ncpus=1+2:ncpus=2+2:ncpus=3:mpiprocs=2'
        as root release nodes except the MS and 2 nodes
        """
        self.test_node_count(rel_user=ROOT_USER)

    def test_node_count_using_script(self):
        """
        Like test_node_count test except instead of calling
        pbs_release_nodes from a command line, it is executed
        inside the job script of a running job. Same results.
        """
        self.jobscript = \
            "#!/bin/sh\n" + \
            "trap 'pbs_release_nodes -k 2" + \
            ";sleep 1000;exit 0' 2\n" + \
            "sleep 1000\n" + \
            "exit 0"
        self.test_node_count(use_script=True)

    def test_node_count_with_mixed_custom_res(self):
        """
        submit job with select string containing a mix of all types of
        custom resources
        'select=ncpus=1+ncpus=2:model=abc:longres=7:sizres=7k:fltres=7.1+
        ncpus=2:model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1+ncpus=3:
        model=def:bigmem=true:longres=9:sizres=9k:fltres=9.1+ncpus=3:
        model=xyz:longres=10:sizres=10k:fltres=10.1'
        release nodes except the MS and 2 nodes
        """
        # 1. create a custom string resources
        str_res = 'model'
        model_a = 'abc'
        model_b = 'def'
        model_c = 'xyz'
        bool_res = 'bigmem'
        long_res = 'longres'
        size_res = 'sizres'
        float_res = 'fltres'

        self.create_res(
            [
                new_res(str_res, self.res_s_h),
                new_res(bool_res, self.res_b_h),
                new_res(long_res, self.res_l_nh),
                new_res(size_res, self.res_sz_nh),
                new_res(float_res, self.res_f_nh)
            ])

        # 2. add the custom resource to sched_config
        self.scheduler.add_resource(str_res)
        self.scheduler.add_resource(long_res)
        self.scheduler.add_resource(size_res)
        self.scheduler.add_resource(float_res)

        n1 = n_conf({'resources_available.ncpus': '1'})
        n2_a = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+str_res: model_a,
                       'resources_available.'+long_res: '7',
                       'resources_available.'+size_res: '7kb',
                       'resources_available.'+float_res: '7.1'})
        n2_b = n_conf({'resources_available.ncpus': '2',
                       'resources_available.'+str_res: model_b,
                       'resources_available.'+bool_res: 'True',
                       'resources_available.'+long_res: '9',
                       'resources_available.'+size_res: '9kb',
                       'resources_available.'+float_res: '9.1'})
        n3_b = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+str_res: model_b,
                       'resources_available.'+bool_res: 'True',
                       'resources_available.'+long_res: '9',
                       'resources_available.'+size_res: '9kb',
                       'resources_available.'+float_res: '9.1'})
        n3_c = n_conf({'resources_available.ncpus': '3',
                       'resources_available.'+str_res: model_c,
                       'resources_available.'+long_res: '10',
                       'resources_available.'+size_res: '10kb',
                       'resources_available.'+float_res: '10.1'})

        nc_list = [n1, n2_a, n2_b, n3_b, n3_c]
        # 3. configure the cluster
        self.config_nodes(nc_list)

        args = {
            'qsub_sel': 'ncpus=1+ncpus=2:model='+model_a+':'+long_res+'=7:' +
            size_res+'=7k:'+float_res+'=7.1+ncpus=2:model='+model_b+':' +
            bool_res+'=true:'+long_res+'=9:'+size_res+'=9k:'+float_res +
            '=9.1+ncpus=3:model='+model_b+':'+bool_res+'=true:'+long_res +
            '=9:'+size_res+'=9k:'+float_res+'=9.1+ncpus=3:model='+model_c +
            ':'+long_res+'=10:'+size_res+'=10k:'+float_res+'=10.1',
            'keep_sel': '2',
            'sched_sel': '1:ncpus=1+1:ncpus=2:model='+model_a+':'+long_res +
            '=7:'+size_res+'=7kb:'+float_res+'=7.1+1:ncpus=2:model='+model_b +
            ':'+bool_res+'=True:'+long_res+'=9:'+size_res+'=9kb:'+float_res +
            '=9.1+1:ncpus=3:model='+model_b+':'+bool_res+'=True:'+long_res +
            '=9:'+size_res+'=9kb:'+float_res+'=9.1+1:ncpus=3:model='+model_c +
            ':'+long_res+'=10:'+size_res+'=10kb:'+float_res+'=10.1',
            'expected_res': self.flatten_node_res(nc_list),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+1:ncpus=2:model=' +
            model_a+':'+long_res+'=7:'+size_res+'=7kb:'+float_res +
            '=7.1+1:ncpus=3:model='+model_c+':'+long_res+'=10:'+size_res +
            '=10kb:'+float_res+'=10.1',
            'sched_sel_after': '1:ncpus=1+1:ncpus=2:model=' +
            model_a+':'+long_res+'=7:'+size_res+'=7kb:'+float_res +
            '=7.1+1:ncpus=3:model='+model_c+':'+long_res+'=10:'+size_res +
            '=10kb:'+float_res+'=10.1',
            'expected_res_after': self.flatten_node_res([n1, n2_a, n3_c])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.longres': 35,
                    'Resource_List.fltres': '35.4',
                    'Resource_List.sizres': '35kb',
                    'Resource_List.ncpus': 11,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.longres': 17,
                          'Resource_List.sizres': '17kb',
                          'Resource_List.fltres': '17.2',
                          'Resource_List.ncpus': 6,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after
        tc = test_config(**args)
        self.common_tc_flow(tc)

    def test_node_count_schunk_use_case(self):
        """
        submit job with below select string
        'ncpus=1+2:ncpus=6+2:ncpus=9:mpiprocs=2'
        cluster is configured such that we get 4 superchunks
        release nodes except the MS and 2 nodes
        """
        n1 = n_conf({'resources_available.ncpus': '1'})
        n2 = n_conf({'resources_available.ncpus': '2'}, 3)
        n3 = n_conf({'resources_available.ncpus': '3'}, 3)

        nc_list = [n1, n2, n2, n3, n3]
        # 1. configure the cluster
        self.config_nodes(nc_list)

        args = {
            'qsub_sel': 'ncpus=1+2:ncpus=6+2:ncpus=9:mpiprocs=2',
            'keep_sel': '2',
            'sched_sel': '1:ncpus=1+2:ncpus=6+2:ncpus=9:mpiprocs=2',
            'expected_res': self.flatten_node_res(
                [n1, n2, n2, n2, n2, n2, n2, n3, n3, n3, n3, n3, n3]),
            'rel_user': TEST_USER,
            'qsub_sel_after': '1:ncpus=1+2:ncpus=6',
            'sched_sel_after': '1:ncpus=1+2:ncpus=6',
            'expected_res_after': self.flatten_node_res(
                [n1, n2, n2, n2, n2, n2, n2])
            }

        job_stat = {'job_state': 'R',
                    'substate': 42,
                    'Resource_List.mpiprocs': 4,
                    'Resource_List.ncpus': 31,
                    'Resource_List.nodect': 5,
                    'Resource_List.select': args['qsub_sel'],
                    'schedselect': args['sched_sel']}

        args['job_stat'] = job_stat

        job_stat_after = {'job_state': 'R',
                          'substate': 42,
                          'Resource_List.ncpus': 13,
                          'Resource_List.nodect': 3,
                          'Resource_List.select': args['qsub_sel_after'],
                          'schedselect': args['sched_sel_after']}

        args['job_stat_after'] = job_stat_after

        tc = test_config(**args)
        self.common_tc_flow(tc)

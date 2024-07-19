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
import ast


@requirements(num_moms=3)
class TestPbsAccumulateRescUsed(TestFunctional):

    """
    This tests the feature in PBS that enables mom hooks to accumulate
    resources_used values for resources beside cput, cpupercent, and mem.
    This includes accumulation of custom resources. The mom hooks supported
    this feature are: exechost_periodic, execjob_prologue,
    and execjob_epilogue.


    PRE: Have a cluster of PBS with 3 mom hosts, with an exechost_startup
         that adds custom resources.

    POST: When a job ends, accounting_logs reflect the aggregated
          resources_used values. And with job_history_enable=true, one
          can do a 'qstat -x -f <jobid>' to obtain information of a previous
          job.
    """

    # Class variables

    def setUp(self):

        TestFunctional.setUp(self)
        self.logger.info("len moms = %d" % (len(self.moms)))
        if len(self.moms) != 3:
            usage_string = 'test requires 3 MoMs as input, ' + \
                           'use -p moms=<mom1>:<mom2>:<mom3>'
            self.skip_test(usage_string)

        # PBSTestSuite returns the moms passed in as parameters as dictionary
        # of hostname and MoM object
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momC = self.moms.values()[2]
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()
        self.momC.delete_vnode_defs()

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.momC.shortname

        rc = self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostC)
        self.assertEqual(rc, 0)

        # Give the moms a chance to contact the server.
        self.server.expect(NODE, {'state': 'free'}, id=self.hostA)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostB)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostC)

        # First set some custom resources via exechost_startup hook.
        startup_hook_body = """
import pbs
e=pbs.event()
localnode=pbs.get_local_nodename()

e.vnode_list[localnode].resources_available['foo_i'] = 7
e.vnode_list[localnode].resources_available['foo_f'] = 5.0
e.vnode_list[localnode].resources_available['foo_str'] = "seventyseven"
"""
        hook_name = "start"
        a = {'event': "exechost_startup", 'enabled': 'True'}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            startup_hook_body,
            overwrite=True)
        self.assertTrue(rv)

        self.momA.signal("-HUP")
        self.momB.signal("-HUP")
        self.momC.signal("-HUP")

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Next set some custom resources via qmgr -c 'create resource'
        attr = {}
        attr['type'] = 'string'
        attr['flag'] = 'h'
        r = 'foo_str2'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)
        self.assertEqual(rc, 0)

        # Ensure the new resource is seen by all moms.
        momlist = [self.momA, self.momB, self.momC]
        for m in momlist:
            m.log_match("resourcedef;copy hook-related file")

        attr['type'] = 'string'
        attr['flag'] = 'h'
        r = 'foo_str3'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)
        self.assertEqual(rc, 0)

        # Ensure the new resource is seen by all moms.
        for m in momlist:
            m.log_match("resourcedef;copy hook-related file")

        attr['type'] = 'string'
        attr['flag'] = 'h'
        r = 'foo_str4'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)
        self.assertEqual(rc, 0)

        # Ensure the new resource is seen by all moms.
        for m in momlist:
            m.log_match("resourcedef;copy hook-related file")

        attr['type'] = 'string_array'
        attr['flag'] = 'h'
        r = 'stra'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)
        self.assertEqual(rc, 0)

        # Give the moms a chance to receive the updated resource.
        # Ensure the new resource is seen by all moms.
        for m in momlist:
            m.log_match("resourcedef;copy hook-related file")

    def test_epilogue(self):
        """
        Test accumulatinon of resources of a multinode job from an
        exechost_epilogue hook.
        """
        self.logger.info("test_epilogue")
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed epilogue hook")
if e.job.in_ms_mom():
    e.job.resources_used["vmem"] = pbs.size("9gb")
    e.job.resources_used["foo_i"] = 9
    e.job.resources_used["foo_f"] = 0.09
    e.job.resources_used["foo_str"] = '{"seven":7}'
    e.job.resources_used["cput"] = 10
    e.job.resources_used["stra"] = '"glad,elated","happy"'
    e.job.resources_used["foo_str3"] = \
        \"\"\"{"a":6,"b":"some value #$%^&*@","c":54.4,"d":"32.5gb"}\"\"\"
    e.job.resources_used["foo_str2"] = "seven"
    e.job.resources_used["foo_str4"] = "eight"
else:
    e.job.resources_used["vmem"] = pbs.size("10gb")
    e.job.resources_used["foo_i"] = 10
    e.job.resources_used["foo_f"] = 0.10
    e.job.resources_used["foo_str"] = '{"eight":8,"nine":9}'
    e.job.resources_used["foo_str2"] = '{"seven":7}'
    e.job.resources_used["cput"] = 20
    e.job.resources_used["stra"] = '"cucumbers,bananas"'
    e.job.resources_used["foo_str3"] = \"\"\""vn1":4,"vn2":5,"vn3":6\"\"\"
"""

        hook_name = "epi"
        a = {'event': "execjob_epilogue", 'enabled': 'True', 'order': 999}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 10,
             'Resource_List.place': "scatter"}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time("10")
        jid = self.server.submit(j)

        # The results should show results for custom resources 'foo_i',
        # 'foo_f', 'foo_str', 'foo_str3', and bultin resources 'vmem',
        # 'cput', and should be accumulating  based
        # on the hook script, where MS defines 1 value, while the 2 sister
        # Moms define the same value. For 'string' type, it will be a
        # union of all values obtained from sister moms and local mom, and
        # the result will be in JSON-format.
        #
        # foo_str is for testing normal values.
        # foo_str2 is for testing non-JSON format value received from MS.
        # foo_str3 is for testing non-JSON format value received from a sister
        # mom.
        # foo_str4 is for testing MS-only set values.
        #
        # For string_array type  resource 'stra', it is not accumulated but
        # will be set to last seen value from a mom epilogue hook.
        self.server.expect(JOB, {
            'job_state': 'F',
            'resources_used.foo_f': '0.29',
            'resources_used.foo_i': '29',
            'resources_used.foo_str4': "eight",
            'resources_used.stra': "\"glad,elated\",\"happy\"",
            'resources_used.vmem': '29gb',
            'resources_used.cput': '00:00:50',
            'resources_used.ncpus': '3'},
            extend='x', offset=10, attrop=PTL_AND, id=jid)

        foo_str_dict_in = {"eight": 8, "seven": 7, "nine": 9}
        qstat = self.server.status(
            JOB, 'resources_used.foo_str', id=jid, extend='x')
        foo_str_dict_out_str = eval(qstat[0]['resources_used.foo_str'])
        foo_str_dict_out = eval(foo_str_dict_out_str)
        self.assertTrue(foo_str_dict_in == foo_str_dict_out)

        # resources_used.foo_str3 must not be set since a sister value is not
        # of JSON-format.
        self.server.expect(JOB, 'resources_used.foo_str3',
                           op=UNSET, extend='x', id=jid)

        self.momA.log_match(
            "Job %s resources_used.foo_str3 cannot be " % (jid,) +
            "accumulated: value '\"vn1\":4,\"vn2\":5,\"vn3\":6' " +
            "from mom %s not JSON-format" % (self.hostB,))

        # resources_used.foo_str2 must not be set.
        self.server.expect(JOB, 'resources_used.foo_str2', op=UNSET, id=jid)
        self.momA.log_match(
            "Job %s resources_used.foo_str2 cannot be " % (jid,) +
            "accumulated: value 'seven' from mom %s " % (self.hostA,) +
            "not JSON-format")

        # Match accounting_logs entry

        acctlog_match = 'resources_used.foo_f=0.29'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = 'resources_used.foo_i=29'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = "resources_used.foo_str='%s'" % (foo_str_dict_out_str,)
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = 'resources_used.vmem=29gb'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = 'resources_used.cput=00:00:50'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        # ensure resources_foo_str2 is not reported in accounting_logs since
        # it's unset due to non-JSON-format value.
        acctlog_match = 'resources_used.foo_str2='
        self.server.accounting_match("E;%s;.*%s.*" % (jid, acctlog_match),
                                     regexp=True, n=100, existence=False)

        acctlog_match = 'resources_used.foo_str4=eight'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = 'resources_used.ncpus=3'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        # resources_used.foo_str3 must not show up in accounting_logs
        acctlog_match = 'resources_used.foo_str3=',
        self.server.accounting_match("E;%s;.*%s.*" % (jid, acctlog_match),
                                     regexp=True, n=100, existence=False)

        acctlog_match = r'resources_used.stra=\"glad\,elated\"\,\"happy\"'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

    def test_prologue(self):
        """
        Test accumulatinon of resources of a multinode job from an
        exechost_prologue hook.
        On cpuset systems don't check for cput because the pbs_cgroups hook
        will be enabled and will overwrite the cput value set in the prologue
        hook
        """
        has_cpuset = False
        for mom in self.moms.values():
            if mom.is_cpuset_mom():
                has_cpuset = True

        self.logger.info("test_prologue")
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed prologue hook")
if e.job.in_ms_mom():
    e.job.resources_used["vmem"] = pbs.size("11gb")
    e.job.resources_used["foo_i"] = 11
    e.job.resources_used["foo_f"] = 0.11
    e.job.resources_used["foo_str"] = '{"seven":7}'
    e.job.resources_used["cput"] = 11
    e.job.resources_used["stra"] = '"glad,elated","happy"'
    e.job.resources_used["foo_str3"] = \
      \"\"\"{"a":6,"b":"some value #$%^&*@","c":54.4,"d":"32.5gb"}\"\"\"
    e.job.resources_used["foo_str2"] = "seven"
    e.job.resources_used["foo_str4"] = "eight"
else:
    e.job.resources_used["vmem"] = pbs.size("12gb")
    e.job.resources_used["foo_i"] = 12
    e.job.resources_used["foo_f"] = 0.12
    e.job.resources_used["foo_str"] = '{"eight":8,"nine":9}'
    e.job.resources_used["foo_str2"] = '{"seven":7}'
    e.job.resources_used["cput"] = 12
    e.job.resources_used["stra"] = '"cucumbers,bananas"'
    e.job.resources_used["foo_str3"] = \"\"\""vn1":4,"vn2":5,"vn3":6\"\"\"
"""

        hook_name = "prolo"
        a = {'event': "execjob_prologue", 'enabled': 'True'}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 10,
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)

        # The pbsdsh call is what allows a first task to get spawned on
        # on a sister mom, causing the execjob_prologue hook to execute.
        j.create_script(
            "pbsdsh -n 1 hostname\n" + "pbsdsh -n 2 hostname\n" + "sleep 10\n")

        jid = self.server.submit(j)

        # The results should show results for custom resources 'foo_i',
        # 'foo_f', 'foo_str', 'foo_str3', and bultin resources 'vmem',
        # 'cput', and should be accumulating  based
        # on the hook script, where MS defines 1 value, while the 2 sister
        # Moms define the same value. For 'string' type, it will be a
        # union of all values obtained from sister moms and local mom, and
        # the result will be in JSON-format.
        #
        # foo_str is for testing normal values.
        # foo_str2 is for testing non-JSON format value received from MS.
        # foo_str3 is for testing non-JSON format value received from a sister
        # mom.
        # foo_str4 is for testing MS-only set values.
        #
        # For string_array type  resource 'stra', it is not accumulated but
        # will be set to last seen value from a mom prologue hook.
        a = {
            'job_state': 'F',
            'resources_used.foo_f': '0.35',
            'resources_used.foo_i': '35',
            'resources_used.foo_str4': "eight",
            'resources_used.stra': "\"glad,elated\",\"happy\"",
            'resources_used.vmem': '35gb',
            'resources_used.ncpus': '3'}

        if not has_cpuset:
            a['resources_used.cput'] = '00:00:35'

        self.server.expect(JOB, a, extend='x', offset=10,
                           attrop=PTL_AND, id=jid)

        foo_str_dict_in = {"eight": 8, "seven": 7, "nine": 9}
        qstat = self.server.status(
            JOB, 'resources_used.foo_str', id=jid, extend='x')
        foo_str_dict_out_str = eval(qstat[0]['resources_used.foo_str'])
        foo_str_dict_out = eval(foo_str_dict_out_str)
        self.assertTrue(foo_str_dict_in == foo_str_dict_out)

        # resources_used.foo_str3 must not be set since a sister value is
        # not of JSON-format.
        self.server.expect(JOB, 'resources_used.foo_str3',
                           op=UNSET, extend='x', id=jid)

        self.momA.log_match(
            "Job %s resources_used.foo_str3 cannot be " % (jid,) +
            "accumulated: value '\"vn1\":4,\"vn2\":5,\"vn3\":6' " +
            "from mom %s not JSON-format" % (self.hostB,))
        self.momA.log_match(
            "Job %s resources_used.foo_str3 cannot be " % (jid,) +
            "accumulated: value '\"vn1\":4,\"vn2\":5,\"vn3\":6' " +
            "from mom %s not JSON-format" % (self.hostC,))

        # Ensure resources_used.foo_str3 is not set since it has a
        # non-JSON format value.
        self.server.expect(JOB, 'resources_used.foo_str3', op=UNSET,
                           extend='x', id=jid)

        # resources_used.foo_str2 must not be set.
        self.server.expect(JOB, 'resources_used.foo_str2', op=UNSET, id=jid)
        self.momA.log_match(
            "Job %s resources_used.foo_str2 cannot be " % (jid,) +
            "accumulated: value 'seven' from " +
            "mom %s not JSON-format" % (self.hostA,))

        # Match accounting_logs entry

        acctlog_match = 'resources_used.foo_f=0.35'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = 'resources_used.foo_i=35'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = "resources_used.foo_str='%s'" % (foo_str_dict_out_str,)
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = 'resources_used.vmem=35gb'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        if not has_cpuset:
            acctlog_match = 'resources_used.cput=00:00:35'
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        # resources_used.foo_str2 should not be reported in accounting_logs.
        acctlog_match = 'resources_used.foo_str2='
        self.server.accounting_match("E;%s;.*%s.*" % (jid, acctlog_match),
                                     regexp=True, n=100, existence=False)

        acctlog_match = 'resources_used.ncpus=3'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        # resources_used.foo_str3 must not show up in accounting_logs
        acctlog_match = 'resources_used.foo_str3='
        self.server.accounting_match("E;%s;.*%s.*" % (jid, acctlog_match),
                                     regexp=True, n=100, existence=False)

        acctlog_match = 'resources_used.foo_str4=eight'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

        acctlog_match = r'resources_used.stra=\"glad\,elated\"\,\"happy\"'
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

    def test_periodic(self):
        """
        Test accumulatinon of resources from an exechost_periodic hook.
        """
        self.logger.info("test_periodic")
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed periodic hook")
i = 0
l = []
for v in pbs.server().vnodes():
    pbs.logmsg(pbs.LOG_DEBUG, "node %s" % (v.name,))
    l.append(v.name)

local_node=pbs.get_local_nodename()
for jk in e.job_list.keys():
    if local_node == l[0]:
        e.job_list[jk].resources_used["vmem"] = pbs.size("11gb")
        e.job_list[jk].resources_used["foo_i"] = 11
        e.job_list[jk].resources_used["foo_f"] = 0.11
        e.job_list[jk].resources_used["foo_str"] = '{"seven":7}'
        e.job_list[jk].resources_used["cput"] = 11
        e.job_list[jk].resources_used["stra"] = '"glad,elated","happy"'
        e.job_list[jk].resources_used["foo_str3"] = \
         \"\"\"{"a":6,"b":"some value #$%^&*@","c":54.4,"d":"32.5gb"}\"\"\"
        e.job_list[jk].resources_used["foo_str2"] = "seven"
    elif local_node == l[1]:
        e.job_list[jk].resources_used["vmem"] = pbs.size("12gb")
        e.job_list[jk].resources_used["foo_i"] = 12
        e.job_list[jk].resources_used["foo_f"] = 0.12
        e.job_list[jk].resources_used["foo_str"] = '{"eight":8}'
        e.job_list[jk].resources_used["cput"] = 12
        e.job_list[jk].resources_used["stra"] = '"cucumbers,bananas"'
        e.job_list[jk].resources_used["foo_str2"] =  '{"seven":7}'
        e.job_list[jk].resources_used["foo_str3"] = \
                \"\"\"{"vn1":4,"vn2":5,"vn3":6}\"\"\"
    else:
        e.job_list[jk].resources_used["vmem"] = pbs.size("13gb")
        e.job_list[jk].resources_used["foo_i"] = 13
        e.job_list[jk].resources_used["foo_f"] = 0.13
        e.job_list[jk].resources_used["foo_str"] = '{"nine":9}'
        e.job_list[jk].resources_used["foo_str2"] =  '{"seven":7}'
        e.job_list[jk].resources_used["cput"] = 13
        e.job_list[jk].resources_used["stra"] = '"cucumbers,bananas"'
        e.job_list[jk].resources_used["foo_str3"] = \
                \"\"\"{"vn1":4,"vn2":5,"vn3":6}\"\"\"
"""

        hook_name = "period"
        a = {'event': "exechost_periodic", 'enabled': 'True', 'freq': 15}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        a = {'resources_available.ncpus': '2'}
        self.server.manager(MGR_CMD_SET, NODE, a, self.hostA)

        self.server.manager(MGR_CMD_SET, NODE, a, self.hostB)

        self.server.manager(MGR_CMD_SET, NODE, a, self.hostC)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time("35")
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)

        for jid in [jid1, jid2]:

            # The results should show results for custom resources 'foo_i',
            # 'foo_f', 'foo_str', 'foo_str3', and bultin resources 'vmem',
            # 'cput', and should be accumulating  based
            # on the hook script, where MS defines 1 value, while the 2 sister
            # Moms define the same value. For 'string' type, it will be a
            # union of all values obtained from sister moms and local mom, and
            # the result will be in JSON-format.
            # foo_str is for testing normal values.
            # foo_str2 is for testing non-JSON format value received from MS.
            # foo_str3 is for testing non-JSON format value received from a
            # sister mom.
            #

            self.server.expect(JOB, {
                'job_state': 'F',
                'resources_used.foo_f': '0.36',
                'resources_used.foo_i': '36',
                'resources_used.stra': "\"glad,elated\",\"happy\"",
                'resources_used.vmem': '36gb',
                'resources_used.cput': '00:00:36',
                'resources_used.ncpus': '3'},
                extend='x', offset=35, attrop=PTL_AND, id=jid)

            foo_str_dict_in = {"eight": 8, "seven": 7, "nine": 9}
            qstat = self.server.status(
                JOB, 'resources_used.foo_str', id=jid, extend='x')
            foo_str_dict_out_str = eval(qstat[0]['resources_used.foo_str'])
            foo_str_dict_out = eval(foo_str_dict_out_str)
            self.assertTrue(foo_str_dict_in == foo_str_dict_out)

            foo_str3_dict_in = {"a": 6, "b": "some value #$%^&*@",
                                "c": 54.4, "d": "32.5gb", "vn1": 4,
                                "vn2": 5, "vn3": 6}
            qstat = self.server.status(
                JOB, 'resources_used.foo_str3', id=jid, extend='x')
            foo_str3_dict_out_str = eval(qstat[0]['resources_used.foo_str3'])
            foo_str3_dict_out = eval(foo_str3_dict_out_str)
            self.assertTrue(foo_str3_dict_in == foo_str3_dict_out)

            # resources_used.foo_str2 must be unset since its value is not of
            # JSON-format.
            self.server.expect(JOB, 'resources_used.foo_str2', op=UNSET,
                               extend='x', id=jid)

            # Match accounting_logs entry

            acctlog_match = 'resources_used.foo_f=0.36'
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

            acctlog_match = 'resources_used.foo_i=36'
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

            acctlog_match = "resources_used.foo_str='%s'" % (
                foo_str_dict_out_str,)
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

            acctlog_match = 'resources_used.vmem=36gb'
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

            acctlog_match = 'resources_used.cput=00:00:36'
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

            # resources_used.foo_str2 must not show in accounting_logs
            acctlog_match = 'resources_used.foo_str2=',
            self.server.accounting_match("E;%s;.*%s.*" % (jid, acctlog_match),
                                         regexp=True, n=100, existence=False)

            acctlog_match = 'resources_used.ncpus=3'
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

            acctlog_match = "resources_used.foo_str3='%s'" % (
                foo_str3_dict_out_str.replace('.', r'\.').
                replace("#$%^&*@", r"\#\$\%\^\&\*\@"))
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
            acctlog_match = r'resources_used.stra=\"glad\,elated\"\,\"happy\"'
            self.server.accounting_match(
                "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)

    def test_resource_bool(self):
        """
        To test that boolean value are not getting aggregated
        """

        # Create a boolean type resource
        attr = {}
        attr['type'] = 'boolean'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr,
            id='foo_bool', runas=ROOT_USER,
            logerr=False)

        hook_body = """
import pbs
e=pbs.event()
j=e.job
if j.in_ms_mom():
    j.resources_used["foo_bool"] = True
else:
    j.resources_used["foo_bool"] = False
"""

        hook_name = "epi_bool"
        a = {'event': "execjob_epilogue", 'enabled': "True"}
        self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 10,
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time("5")
        jid = self.server.submit(j)

        # foo_bool is True
        a = {'resources_used.foo_bool': "True",
             'job_state': 'F'}
        self.server.expect(JOB, a, extend='x', offset=5, attrop=PTL_AND,
                           id=jid)

    def test_resource_invisible(self):
        """
        Test that value aggregation is same for invisible resources
        """

        # Set float and string_array to be invisible resource
        attr = {}
        attr['flag'] = 'ih'
        self.server.manager(
            MGR_CMD_SET, RSC, attr, id='foo_f', runas=ROOT_USER)
        self.server.manager(
            MGR_CMD_SET, RSC, attr, id='foo_str', runas=ROOT_USER)

        hook_body = """
import pbs
e=pbs.event()
j = e.job
if j.in_ms_mom():
    j.resources_used["foo_f"] = 2.114
    j.resources_used["foo_str"] = '{"one":1,"two":2}'
else:
    j.resources_used["foo_f"] = 3.246
    j.resources_used["foo_str"] = '{"two":2, "three":3}'
"""

        hook_name = "epi_invis"
        a = {'event': "execjob_epilogue", 'enabled': 'True'}
        self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 10,
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time("5")
        jid = self.server.submit(j)

        # Verify that values are accumulated for float and string array
        a = {'resources_used.foo_f': '8.606'}
        self.server.expect(JOB, a, extend='x', offset=5, id=jid)

        foo_str_dict_in = {"one": 1, "two": 2, "three": 3}
        qstat = self.server.status(
            JOB, 'resources_used.foo_str', id=jid, extend='x')
        foo_str_dict_out_str = eval(qstat[0]['resources_used.foo_str'])
        foo_str_dict_out = eval(foo_str_dict_out_str)
        self.assertEqual(foo_str_dict_in, foo_str_dict_out)

    def test_reservation(self):
        """
        Test that job inside reservations works same
        NOTE: Due to the reservation duration and the job duration
        both being equal, this test found 2 race conditions.
        KEEP the durations equal to each other.
        """
        # Create non-host level resources from qmgr
        attr = {}
        attr['type'] = 'size'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id='foo_i2', runas=ROOT_USER)
        # Ensure the new resource is seen by all moms.
        momlist = [self.momA, self.momB, self.momC]
        for m in momlist:
            m.log_match("resourcedef;copy hook-related file")

        attr['type'] = 'float'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id='foo_f2', runas=ROOT_USER)
        # Ensure the new resource is seen by all moms.
        for m in momlist:
            m.log_match("resourcedef;copy hook-related file")

        attr['type'] = 'string_array'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id='stra2', runas=ROOT_USER)
        # Ensure the new resource is seen by all moms.
        for m in momlist:
            m.log_match("resourcedef;copy hook-related file")

        # Create an epilogue hook
        hook_body = """
import pbs
e = pbs.event()
j = e.job
pbs.logmsg(pbs.LOG_DEBUG, "executed epilogue hook")
j.resources_used["foo_i"] = 2
j.resources_used["foo_i2"] = pbs.size(1000)
j.resources_used["foo_f"] = 1.02
j.resources_used["foo_f2"] = 2.01
j.resources_used["stra"] = '"happy"'
j.resources_used["stra2"] = '"glad"'
"""

        # Create and import hook
        a = {'event': "execjob_epilogue", 'enabled': 'True'}
        self.server.create_import_hook(
            "epi", a, hook_body,
            overwrite=True)

        # Submit a reservation
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'scatter',
             'reserve_start': time.time() + 10,
             'reserve_end': time.time() + 30, }
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        rname = rid.split('.')
        # Submit a job inside reservation
        a = {'Resource_List.select': '3:ncpus=1', ATTR_queue: rname[0]}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time(20)
        jid = self.server.submit(j)

        # Verify the resource values
        a = {'resources_used.foo_i': '6',
             'resources_used.foo_i2': '3kb',
             'resources_used.foo_f': '3.06',
             'resources_used.foo_f2': '6.03',
             'resources_used.stra': "\"happy\"",
             'resources_used.stra2': "\"glad\"",
             'job_state': 'F'}
        self.server.expect(JOB, a, extend='x', attrop=PTL_AND,
                           offset=30, interval=1, id=jid)

        # Below is commented out due to a problem with history jobs
        # disapearing after a server restart when the reservation is
        # in state BD during restart.
        # Once that bug is fixed, this test code should be uncommented
        # and run.

        # Restart server and verifies that the values are still the same
        # self.server.restart()
        # self.server.expect(JOB, a, extend='x', id=jid)

    def test_server_restart(self):
        """
        Test that resource accumulation will not get
        impacted if server is restarted during job execution
        On cpuset systems don't check for cput because the pbs_cgroups hook
        will be enabled and will overwrite the cput value set in the prologue
        hook
        """
        has_cpuset = False
        for mom in self.moms.values():
            if mom.is_cpuset_mom():
                has_cpuset = True

        # Create a prologue hook
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed prologue hook")
if e.job.in_ms_mom():
    e.job.resources_used["vmem"] = pbs.size("11gb")
    e.job.resources_used["foo_i"] = 11
    e.job.resources_used["foo_f"] = 0.11
    e.job.resources_used["foo_str"] = '{"seven":7}'
    e.job.resources_used["cput"] = 11
    e.job.resources_used["stra"] = '"glad,elated","happy"'
    e.job.resources_used["foo_str4"] = "eight"
else:
    e.job.resources_used["vmem"] = pbs.size("12gb")
    e.job.resources_used["foo_i"] = 12
    e.job.resources_used["foo_f"] = 0.12
    e.job.resources_used["foo_str"] = '{"eight":8,"nine":9}'
    e.job.resources_used["cput"] = 12
    e.job.resources_used["stra"] = '"cucumbers,bananas"'
"""

        hook_name = "prolo"
        a = {'event': "execjob_prologue", 'enabled': 'True'}
        self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 20,
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)

        # The pbsdsh call is what allows a first task to get spawned on
        # on a sister mom, causing the execjob_prologue hook to execute.
        j.create_script(
            "pbsdsh -n 1 hostname\n" +
            "pbsdsh -n 2 hostname\n" +
            "sleep 10\n")

        jid = self.server.submit(j)

        # Once the job is started running restart server
        self.server.expect(JOB, {'job_state': "R", "substate": 42}, id=jid)
        self.server.restart()

        # Job will be requeued and rerun. Verify that the
        # resource accumulation is similar as if server is
        # not started
        a = {'resources_used.foo_i': '35',
             'resources_used.foo_f': '0.35',
             'resources_used.vmem': '35gb',
             'resources_used.stra': "\"glad,elated\",\"happy\"",
             'resources_used.foo_str4': "eight",
             'job_state': 'F'}
        if not has_cpuset:
            a['resources_used.cput'] = '00:00:35'
        self.server.expect(JOB, a, extend='x',
                           offset=5, id=jid, interval=1, attrop=PTL_AND)

        foo_str_dict_in = {"eight": 8, "seven": 7, "nine": 9}
        qstat = self.server.status(
            JOB, 'resources_used.foo_str', id=jid, extend='x')
        foo_str_dict_out_str = eval(qstat[0]['resources_used.foo_str'])
        foo_str_dict_out = eval(foo_str_dict_out_str)
        self.assertEqual(foo_str_dict_in, foo_str_dict_out)

    def test_mom_down(self):
        """
        Test that resource_accumulation is not impacted due to
        mom restart
        """

        # Set node_fail_requeue to requeue job
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'node_fail_requeue': 10})

        hook_body = """
import pbs
e = pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed periodic hook")

for jj in e.job_list.keys():
    e.job_list[jj].resources_used["foo_i"] = 1
    e.job_list[jj].resources_used["foo_str"] = '{"happy":"true"}'
    e.job_list[jj].resources_used["stra"] = '"one","two"'
"""

        a = {'event': "exechost_periodic", 'enabled': 'True', 'freq': 10}
        self.server.create_import_hook(
            "period",
            a,
            hook_body,
            overwrite=True)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 300,
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)
        jid1 = self.server.submit(j)

        # Submit a job that can never run
        a = {'Resource_List.select': '5:ncpus=1',
             'Resource_List.place': 'scatter'}
        j.set_attributes(a)
        j.set_sleep_time("300")
        jid2 = self.server.submit(j)

        # Wait for 10s approx for hook to get executed
        # verify the resources_used.foo_i
        self.server.expect(JOB, {'resources_used.foo_i': '3'},
                           offset=10, id=jid1, interval=1)
        self.server.expect(JOB, "resources_used.foo_i", op=UNSET, id=jid2)

        # Bring sister mom down
        self.momB.stop()

        # Wait for 20 more seconds for preiodic hook to run
        # more than once and verify that value is still 3
        self.server.expect(JOB, {'resources_used.foo_i': '3'},
                           offset=20, id=jid1, interval=1)

        # Wait for job to be requeued by node_fail_requeue
        self.server.rerunjob(jid1, runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

        # Verify that resources_used.foo_i is unset
        self.server.expect(JOB, "resources_used.foo_i", op=UNSET, id=jid1)

        # Bring sister mom up
        self.momB.start()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1, interval=1)

        # Verify that value of foo_i for job1 is set back
        self.server.expect(JOB, {'resources_used.foo_i': '3'},
                           offset=10, id=jid1, interval=1)

    def test_job_rerun(self):
        """
        Test that resource accumulates once when job
        is rerun
        """

        hook_body = """
import pbs
e = pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed periodic hook")

for jj in e.job_list.keys():
    e.job_list[jj].resources_used["foo_f"] = 1.01
    e.job_list[jj].resources_used["cput"] = 10
"""

        a = {'event': "exechost_periodic", 'enabled': 'True', 'freq': 10}
        self.server.create_import_hook(
            "period",
            a,
            hook_body,
            overwrite=True)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "R", "substate": 42}, id=jid1)

        # Wait for 10s approx for hook to get executed
        # Verify the resources_used.foo_f
        a = {'resources_used.foo_f': '3.03',
             'resources_used.cput': 30}
        self.server.expect(JOB, a,
                           offset=10, id=jid1, attrop=PTL_AND, interval=1)

        # Rerun the job
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})
        self.server.rerunjob(jobid=jid1, runas=ROOT_USER)
        self.server.expect(JOB,
                           {'job_state': 'Q'}, id=jid1)

        # Verify that foo_f is unset
        self.server.expect(JOB,
                           'Resource_List.foo_f',
                           op=UNSET, id=jid1)

        # turn the scheduling on
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': "R", "substate": 42},
                           attrop=PTL_AND, id=jid1)

        # Validate that resources_used.foo_f is reset
        self.server.expect(JOB, a,
                           offset=10, id=jid1, attrop=PTL_AND, interval=1)

    def test_job_array(self):
        """
        Test that resource accumulation for subjobs also work
        """

        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed epilogue hook")
if e.job.in_ms_mom():
    e.job.resources_used["vmem"] = pbs.size("9gb")
    e.job.resources_used["foo_i"] = 9
    e.job.resources_used["foo_f"] = 0.09
    e.job.resources_used["foo_str"] = '{"seven":7}'
    e.job.resources_used["cput"] = 10
    e.job.resources_used["stra"] = '"glad,elated","happy"'
else:
    e.job.resources_used["vmem"] = pbs.size("10gb")
    e.job.resources_used["foo_i"] = 10
    e.job.resources_used["foo_f"] = 0.10
    e.job.resources_used["foo_str"] = '{"eight":8,"nine":9}'
    e.job.resources_used["cput"] = 20
    e.job.resources_used["stra"] = '"cucumbers,bananas"'
"""

        a = {'event': "execjob_epilogue", 'enabled': 'True'}
        self.server.create_import_hook(
            "test",
            a,
            hook_body,
            overwrite=True)

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 10,
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER, attrs={ATTR_J: '1-2'})
        j.set_attributes(a)
        j.set_sleep_time("5")
        jid = self.server.submit(j)

        # Verify that once subjobs are over values are
        # set for each subjob in the accounting logs
        subjob1 = str.replace(jid, '[]', '[1]')

        acctlog_match = 'resources_used.foo_f=0.29'
        # Below code is commented due to a PTL issue
        # s = self.server.accounting_match(
        #    "E;%s;.*%s.*" % (subjob1, acctlog_match), regexp=True, n=100)
        # self.assertTrue(s)

        acctlog_match = 'resources_used.foo_i=29'
        # s = self.server.accounting_match(
        #    "E;%s;.*%s.*" % (subjob1, acctlog_match), regexp=True, n=100)
        # self.assertTrue(s)

        foo_str_dict_in = {"eight": 8, "seven": 7, "nine": 9}
        acctlog_match = "resources_used.foo_str='%s'" % (foo_str_dict_in,)
        # s = self.server.accounting_match(
        #    "E;%s;.*%s.*" % (subjob1, acctlog_match), regexp=True, n=100)
        # self.assertTrue(s)

        acctlog_match = 'resources_used.vmem=29gb'
        # s = self.server.accounting_match(
        #    "E;%s;.*%s.*" % (subjob1, acctlog_match), regexp=True, n=100)
        # self.assertTrue(s)

        acctlog_match = 'resources_used.cput=00:00:50'
        # s = self.server.accounting_match(
        #    "E;%s;.*%s.*" % (subjob1, acctlog_match), regexp=True, n=100)
        # self.assertTrue(s)

        acctlog_match = r'resources_used.stra=\"glad\,elated\"\,\"happy\"'
        # s = self.server.accounting_match(
        #    "E;%s;.*%s.*" % (subjob1, acctlog_match), regexp=True, n=100)
        # self.assertTrue(s)

    def test_epi_pro(self):
        """
        Test that epilogue and prologue changing same
        and different resources. Values of same resource
        would get overwriteen by the last hook.
        On cpuset systems don't check for cput because the pbs_cgroups hook
        will be enabled and will overwrite the cput value set in the prologue
        hook
        """
        has_cpuset = False
        for mom in self.moms.values():
            if mom.is_cpuset_mom():
                has_cpuset = True

        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "In prologue hook")
e.job.resources_used["foo_i"] = 10
e.job.resources_used["foo_f"] = 0.10
"""

        a = {'event': "execjob_prologue", 'enabled': 'True'}
        self.server.create_import_hook(
            "pro", a, hook_body,
            overwrite=True)

        # Verify the copy message in the logs to avoid
        # race conditions
        momlist = [self.momA, self.momB, self.momC]
        for m in momlist:
            m.log_match("pro.PY;copy hook-related file")

        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "In epilogue hook")
e.job.resources_used["foo_f"] = 0.20
e.job.resources_used["cput"] = 10
"""

        a = {'event': "execjob_epilogue", 'enabled': 'True'}
        self.server.create_import_hook(
            "epi", a, hook_body,
            overwrite=True)

        # Verify the copy message in the logs to avoid
        # race conditions
        for m in momlist:
            m.log_match("epi.PY;copy hook-related file")

        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.create_script(
            "pbsdsh -n 1 hostname\n" +
            "pbsdsh -n 2 hostname\n" +
            "sleep 5\n")
        jid = self.server.submit(j)

        # Verify the resources_used once the job is over
        b = {
            'resources_used.foo_i': '30',
            'resources_used.foo_f': '0.6',
            'job_state': 'F'}

        if not has_cpuset:
            b['resources_used.cput'] = '30'
        self.server.expect(JOB, b, extend='x', id=jid, offset=5, interval=1)

        # Submit another job
        j1 = Job(TEST_USER)
        j1.set_attributes(a)
        j1.create_script(
            "pbsdsh -n 1 hostname\n" +
            "pbsdsh -n 2 hostname\n" +
            "sleep 300\n")
        jid1 = self.server.submit(j1)

        # Verify that prologue hook has set the values
        self.server.expect(JOB, {
            'job_state': 'R',
            'resources_used.foo_i': '30',
            'resources_used.foo_f': '0.3'}, attrop=PTL_AND,
            id=jid1, interval=2)

        # Force delete the job
        self.server.deljob(id=jid1, wait=True, attr_W="force")

        # Verify values are accumulated by prologue hook only
        self.server.expect(JOB, {
            'resources_used.foo_i': '30',
            'resources_used.foo_f': '0.3'}, attrop=PTL_AND,
            extend='x', id=jid1)

    def test_server_restart2(self):
        """
        Test that server restart during hook execution
        has no impact
        """

        hook_body = """
import pbs
import time

e = pbs.event()

pbs.logmsg(pbs.LOG_DEBUG, "executed epilogue hook")
if e.job.in_ms_mom():
        e.job.resources_used["vmem"] = pbs.size("9gb")
        e.job.resources_used["foo_i"] = 9
        e.job.resources_used["foo_f"] = 0.09
        e.job.resources_used["foo_str"] = '{"seven":7}'
        e.job.resources_used["cput"] = 10
else:
        e.job.resources_used["vmem"] = pbs.size("10gb")
        e.job.resources_used["foo_i"] = 10
        e.job.resources_used["foo_f"] = 0.10
        e.job.resources_used["foo_str"] = '{"eight":8,"nine":9}'
        e.job.resources_used["cput"] = 20

time.sleep(15)
"""

        a = {'event': "execjob_epilogue", 'enabled': 'True'}
        self.server.create_import_hook(
            "epi", a, hook_body, overwrite=True)

        # Submit a job
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 10,
             'Resource_List.place': "scatter",
             'Keep_Files': 'oe'}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time("5")
        jid = self.server.submit(j)

        # Verify the resource values
        a = {'resources_used.foo_i': 29,
             'resources_used.foo_f': 0.29}
        a_dict = {'eight': 8, 'seven': 7, 'nine': 9}

        self.server.expect(JOB, a, extend='x', attrop=PTL_AND,
                           offset=5, id=jid, interval=1)
        # check for dictionary resource
        job_status = self.server.status(JOB, id=jid, extend='x')
        job_str_resource = dict(job_status[0])['resources_used.foo_str']
        job_str_resource = ast.literal_eval(ast.literal_eval(job_str_resource))
        self.assertEqual(job_str_resource, a_dict)

        # Restart server while hook is still executing
        self.server.restart()

        # Verify that values again
        self.server.expect(JOB, a, extend='x', attrop=PTL_AND,
                           id=jid)
        # check for dictionary resource
        job_status = self.server.status(JOB, id=jid, extend='x')
        job_str_resource = dict(job_status[0])['resources_used.foo_str']
        job_str_resource = ast.literal_eval(ast.literal_eval(job_str_resource))
        self.assertEqual(job_str_resource, a_dict)

    def test_mom_down2(self):
        """
        Test that when mom is down values are still
        accumulated for resources
        """

        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed epilogue hook")
if e.job.in_ms_mom():
    e.job.resources_used["vmem"] = pbs.size("9gb")
    e.job.resources_used["foo_i"] = 9
    e.job.resources_used["foo_f"] = 0.09
    e.job.resources_used["foo_str"] = '{"seven":7}'
    e.job.resources_used["cput"] = 10
    e.job.resources_used["stra"] = '"glad,elated","happy"'
else:
    e.job.resources_used["vmem"] = pbs.size("10gb")
    e.job.resources_used["foo_i"] = 10
    e.job.resources_used["foo_f"] = 0.10
    e.job.resources_used["foo_str"] = '{"eight":8,"nine":9}'
    e.job.resources_used["cput"] = 20
    e.job.resources_used["stra"] = '"cucumbers,bananas"'
"""

        a = {'event': "execjob_epilogue",
             'enabled': 'True'}
        self.server.create_import_hook(
            "epi", a, hook_body,
            overwrite=True)

        # Submit a job
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': 40,
             'Resource_List.place': "scatter"}
        j = Job(TEST_USER)
        j.set_attributes(a)
        jid = self.server.submit(j)

        # Verify job is running
        self.server.expect(JOB,
                           {'job_state': "R"}, id=jid)

        # Bring sister mom down
        self.momB.stop()

        # Wait for job to end
        # Validate that the values are being set
        # with 2 moms only
        self.server.expect(JOB,
                           {'job_state': 'F',
                            'resources_used.foo_i': '19',
                            'resources_used.foo_f': '0.19'},
                           offset=10, id=jid, interval=1, extend='x',
                           attrop=PTL_AND)
        a_dict = {'eight': 8, 'nine': 9, 'seven': 7}

        # check for dictionary resource
        job_status = self.server.status(JOB, id=jid, extend='x')
        job_str_resource = dict(job_status[0])['resources_used.foo_str']
        job_str_resource = ast.literal_eval(ast.literal_eval(job_str_resource))
        self.assertEqual(job_str_resource, a_dict)

        # Bring the mom back up
        self.momB.start()

    def test_finished_walltime(self):
        """
        If used resources are modified from hook, this test makes sure
        that mem used resources are merged and once the job ends,
        the walltime is not zero.
        """
        hook_body = """
import pbs
e = pbs.event()
if e.type == pbs.EXECHOST_PERIODIC:
    for jobid in e.job_list:
        e.job_list[jobid].resources_used["mem"] = pbs.size('1024kb')
else:
    e.job.resources_used["mem"] = pbs.size('1024kb')
"""
        hook_name = "multinode_used"
        attr = {'event': 'exechost_periodic,execjob_epilogue,execjob_end',
                'freq': '3',
                'enabled': 'True'}
        rv = self.server.create_import_hook(hook_name, attr, hook_body)
        self.assertTrue(rv)

        sleeptime = 30
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.walltime': sleeptime,
             'Resource_List.place': "scatter"}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time(f"{sleeptime}")
        jid = self.server.submit(j)

        self.server.expect(JOB, {
            'job_state': 'R',
            'resources_used.mem': '3072kb'},
            attrop=PTL_AND, offset=sleeptime/2, id=jid)

        self.server.expect(JOB, {
            'job_state': 'F',
            'resources_used.mem': '3072kb',
            'resources_used.walltime': sleeptime}, op=GE,
            extend='x', offset=sleeptime/2, attrop=PTL_AND, id=jid)

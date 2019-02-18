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

import time
from tests.functional import *


class Test_singleNode_Job_ResourceUsed(TestFunctional):
    rsc_list = ['foo_str', 'foo_f', 'foo_i', 'foo_str2', 'foo_str3']

    def tearDown(self):
        self.du.set_pbs_config(confs={'PBS_SERVER': self.server.hostname})
        TestFunctional.tearDown(self)
        for r in self.rsc_list:
            try:
                self.server.manager(MGR_CMD_DELETE, RSC, id=r, runas=ROOT_USER)
            except:
                pass
        self.server.restart()
        self.mom.restart()

    def setUp(self):
        TestFunctional.setUp(self)
        for r in self.rsc_list:
            try:
                self.server.manager(MGR_CMD_DELETE, RSC, id=r, runas=ROOT_USER)
            except:
                pass

        self.server.restart()

        self.momA = self.moms.values()[0]
        self.momA.restart()
        self.momA.delete_vnode_defs()
        self.hostA = self.momA.shortname

        rc = self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
        self.assertEqual(rc, 0)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostA)

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Next set some custom resources via qmgr -c 'create resource'
        attr = {'type': 'string', 'flag': 'h'}
        r = 'foo_str2'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)
        self.assertEqual(rc, 0)

        r = 'foo_str3'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)
        self.assertEqual(rc, 0)

        attr['type'] = 'string_array'
        r = 'stra'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)
        self.assertEqual(rc, 0)

        # Set some custom resources via exechost_startup hook.
        startup_hook_body = """
import pbs
e=pbs.event()
localnode=pbs.get_local_nodename()
e.vnode_list[localnode].resources_available['foo_i'] = 7
e.vnode_list[localnode].resources_available['foo_f'] = 5.0
e.vnode_list[localnode].resources_available['foo_str'] = "seventyseven"
e.vnode_list[localnode].resources_available['foo_str2'] = "seven"
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
        # Give the moms a chance to receive the updated resource.
        # Ensure the new resource is seen by all moms.
        m = self.momA.log_match("resourcedef;copy hook-related file",
                                max_attempts=20, interval=1)
        self.assertTrue(m)

    def test_epilogue_single_node(self):
        """
        Test accumulation of resources of a single node job from an
        exechost_epilogue hook.
        """
        self.logger.info("test_epilogue_single_node")
        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "executed epilogue hook")
e.job.resources_used["vmem"] = pbs.size("9gb")
e.job.resources_used["foo_i"] = 9
e.job.resources_used["foo_f"] = 0.09
e.job.resources_used["foo_str"] = '{"seven":7}'
e.job.resources_used["foo_str3"] = \
"\"\"{"a":6,"b":"some value #$%^&*@","c":54.4,"d":"32.5gb"}\"\"\"
e.job.resources_used["foo_str2"] = "seven"
e.job.resources_used["cput"] = 10
e.job.resources_used["stra"] = '"glad,elated","happy"'
"""

        hook_name = "epi"
        a = {'event': "execjob_epilogue", 'enabled': 'True'}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 3
             }
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time("3")
        jid = self.server.submit(j)

        # The results should show value for custom resources 'foo_i',
        # 'foo_f', 'foo_str', 'foo_str3', and builtin resources 'vmem',
        # 'cput', and should be accumulating  based on the hook script,
        # For 'string' type resources set to a json string will be within
        # single quotes.
        #
        # foo_str and foo_str3 are string type resource set to JSON
        # format string

        self.server.expect(JOB, {
            'job_state': 'F',
            'resources_used.foo_f': '0.09',
            'resources_used.foo_i': '9',
            'resources_used.foo_str': '\'{"seven": 7}\'',
            'resources_used.foo_str2': 'seven',
            'resources_used.stra': "\"glad,elated\",\"happy\"",
            'resources_used.vmem': '9gb',
            'resources_used.cput': '00:00:10',
            'resources_used.ncpus': '1'},
            extend='x', offset=10, attrop=PTL_AND, id=jid)

        # Match accounting_logs entry

        acctlog_match = 'resources_used.foo_f=0.09'
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

        acctlog_match = 'resources_used.foo_i=9'
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

        acctlog_match = 'resources_used.foo_str=\'{"seven": 7}\''
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

        acctlog_match = 'resources_used.vmem=9gb'
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

        acctlog_match = 'resources_used.cput=00:00:10'
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

        acctlog_match = 'resources_used.foo_str2=seven'
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

        acctlog_match = 'resources_used.ncpus=1'
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

        acctlog_match = 'resources_used.foo_str3='
        s = self.server.accounting_match(
            "E;%s;.*%s'{.*}'.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)
        acctlog_match = 'resources_used.stra=\"glad\,elated\"\,\"happy\"'
        s = self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, acctlog_match), regexp=True, n=100)
        self.assertTrue(s)

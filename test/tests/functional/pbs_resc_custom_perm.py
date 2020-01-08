# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class Test_Custom_Resource_Perm(TestFunctional):
    rsc_list = ['foo_str', 'foo_strm', 'foo_strh']
    hook_list = ["start", "begin"]

    def setUp(self):
        TestFunctional.setUp(self)

        self.momA = self.moms.values()[0]
        self.momA.delete_vnode_defs()
        self.hostA = self.momA.shortname

        rc = self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
        self.assertEqual(rc, 0)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostA)

        # Next set custom resources with m flag and without m flag
        # via qmgr -c 'create resource'
        attr = {'type': 'string', 'flag': 'h'}
        r = 'foo_str'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, logerr=False)

        attr = {'type': 'string', 'flag': 'hm'}
        r = 'foo_strm'
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id=r, logerr=False)

        # Create a custom resources via exechost_startup hook.
        startup_hook_body = """
import pbs
e=pbs.event()
localnode=pbs.get_local_nodename()
e.vnode_list[localnode].resources_available['foo_strh'] = "str_hook"
"""
        hook_name = "start"
        a = {'event': "exechost_startup", 'enabled': 'True'}
        self.server.create_import_hook(
            hook_name,
            a,
            startup_hook_body,
            overwrite=True)

        # Restart the MoM so that exechost_startup hook can run.
        self.momA.restart()

        # Give the moms a chance to receive the updated resource.
        # Ensure the new resource is seen by all moms.
        self.momA.log_match("resourcedef;copy hook-related file",
                            max_attempts=20, interval=1)

        # Create a exechost_begin hook.
        begin_hook_body = """
import pbs
e=pbs.event()
res_list = getattr(e.job, 'Resource_List')
pbs.logjobmsg(e.job.id, "Resource_List is %s" % str(res_list))
"""
        hook_name = "begin"
        a = {'event': "execjob_begin", 'enabled': 'True'}
        self.server.create_import_hook(
            hook_name,
            a,
            begin_hook_body,
            overwrite=True)

    def test_custom_resc_single_node(self):
        """
        Test permission flag of resources of a single node job
        using a execjob_begin hook.
        """
        self.logger.info("test_custom_resc__single_node")

        a = {'Resource_List.foo_str': 'str_noperm',
             'Resource_List.foo_strm': 'str_perm',
             'Resource_List.foo_strh': 'str_hook'
             }
        j = Job(TEST_USER, a)
        j.set_sleep_time("100")
        jid = self.server.submit(j)

        self.server.expect(JOB, {
            'job_state': 'R',
            'Resource_List.foo_str': 'str_noperm',
            'Resource_List.foo_strm': 'str_perm',
            'Resource_List.foo_strh': 'str_hook'},
            offset=1, id=jid)

        # Match mom logs entry, only resoruces with "m" flag would show up.
        msg = 'foo_strm=str_perm'
        self.momA.log_match("Job;%s;.*%s.*" % (jid, msg),
                            regexp=True, n=10, max_attempts=10, interval=2)
        msg = 'foo_strh=str_hook'
        self.momA.log_match("Job;%s;.*%s.*" % (jid, msg),
                            regexp=True, n=10, max_attempts=10, interval=2)
        msg = 'foo_str=str_noperm'
        self.momA.log_match("Job;%s;.*%s.*" % (jid, msg),
                            regexp=True, n=5, max_attempts=10, interval=2,
                            existence=False)

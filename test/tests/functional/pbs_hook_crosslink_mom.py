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


@tags('hooks')
class TestPbsHookCrossLinkMom(TestFunctional):
    """
    When a hook updates attributes of vnodes not belonging to MoM on which
    the hook is running, the server wrongly cross links the MoM with the vnode.
    This testsuite tests the fix for this issue and needs two MoMs.
    """
    def setUp(self):
        TestFunctional.setUp(self)

        if len(self.moms) != 2:
            self.skipTest('test requires two MoMs as input, ' +
                          'use -p moms=<mom1>:<mom2>')

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

    def test_crosslink(self):
        """
        This test creates a execjob_end hook which updates an attribute of
        all vnodes. A job is submitted that runs on two different MoM hosts.
        When the job has finished, the test checks if the server did the wrong
        cross-linking or not.
        """
        status = self.server.status(NODE, id=self.hostA)
        Mom1_before = status[0][ATTR_NODE_Mom]

        status = self.server.status(NODE, id=self.hostB)
        Mom2_before = status[0][ATTR_NODE_Mom]

        hook_name = "job_end"
        hook_body = """
import pbs

this_event = pbs.event()
if this_event.type == pbs.EXECJOB_END:
    job = this_event.job
    exec_vnode = str(job.exec_vnode).replace("(", "").replace(")", "")
    vnodes = sorted(set([x.partition(':')[0]
                        for x in exec_vnode.split('+')]))
    for h in vnodes:
        try:
            pbs.logjobmsg(job.id, "vnode is %s ======" % h)
            pbs.event().vnode_list[h].current_eoe = None
        except:
            pass

this_event.accept()
"""

        a = {'event': "execjob_end", 'enabled': 'true', 'debug': 'true'}
        self.server.create_import_hook(hook_name, a, hook_body)

        select = "1:host=" + self.hostA + ":ncpus=1+1:host=" \
            + self.hostB + ":ncpus=1"
        a = {'Resource_List.select': select,  ATTR_k: 'oe'}

        j = Job(TEST_USER, a)
        j.set_sleep_time(1)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')

        status = self.server.status(NODE, id=self.hostA)
        Mom = status[0][ATTR_NODE_Mom]
        self.assertEquals(Mom, Mom1_before)

        status = self.server.status(NODE, id=self.hostB)
        Mom = status[0][ATTR_NODE_Mom]
        self.assertEquals(Mom, Mom2_before)

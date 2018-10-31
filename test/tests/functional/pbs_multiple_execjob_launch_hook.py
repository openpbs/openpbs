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


class TestExecJobHook(TestFunctional):

    hooks = {
        "execjob_hook1":
        """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "executing execjob_launch 1" )
e=pbs.event()
e.progname = "/usr/bin/echo"
e.argv=[]
e.argv.append("launch 1")
pbs.logmsg(pbs.LOG_DEBUG, "environment var from execjob_hook1 is %s" % (e.env))
        """,
        "execjob_hook2":
        """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "executing execjob_launch 2" )
e = pbs.event()
if (e.progname != "/usr/bin/echo"):
    pbs.logmsg(pbs.LOG_DEBUG,
        "Modified progname value did not propagated from launch1 hook")
    e.reject("")
else:
    pbs.logmsg(pbs.LOG_DEBUG,
        "Modified progname value got updated from launch1")
pbs.logmsg(pbs.LOG_DEBUG, "environment var from execjob_hook2 is %s" % (e.env))
        """,
    }

    def setUp(self):
        TestFunctional.setUp(self)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047},
                            expect=True)

    def test_multi_execjob_hook(self):
        """
        Unsetting ncpus, that is ['ncpus'] = None, in modifyjob hook
        """
        hook_names = ["execjob_hook1", "execjob_hook2"]
        hook_attrib = {'event': 'execjob_launch', 'enabled': 'True',
                       'order': ''}
        for hook_name in hook_names:
            hook_script = self.hooks[hook_name]
            hook_attrib['order'] = hook_names.index(hook_name) + 1
            retval = self.server.create_import_hook(hook_name,
                                                    hook_attrib,
                                                    hook_script,
                                                    overwrite=True)
            self.assertTrue(retval)

        job = Job(TEST_USER1, attrs={ATTR_l: 'select=1:ncpus=1',
                                     ATTR_e: '/tmp/',
                                     ATTR_o: '/tmp/'})
        job.set_sleep_time(1)
        jid = self.server.submit(job)
        self.mom.log_match(
            "Modified progname value got updated from launch1",
            max_attempts=3, interval=3)

        hook1 = ["execjob_hook1", "execjob_hook2"]

        for hk in hook1:
            msg = "environment var from " + hk
            rv = self.mom.log_match(msg, starttime=self.server.ctime,
                                    max_attempts=10)
            val = rv[1] + ','  # appending comma at the end
            self.assertTrue("PBS_TASKNUM=1," in val,
                            "Message not found for hook " + hk)

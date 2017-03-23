# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.


from tests.functional import *


class TestQsubWithQueuejobHook(TestFunctional):
    """
    This test suite validates the job submitted through qsub
    when queuejob hook is enabled in the PBS complex.
    """

    hooks = {
        "queuejob_hook1":
        """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "submitted job with long select" )
        """,
    }

    def setUp(self):
        TestFunctional.setUp(self)

    def test_qsub_long_select_with_hook(self):
        """
        This test case validates that, when a long string of resource is
        requested in qsub through lselect. The requested resource should not
        get truncated by the server hook infra when there exists a queuejob
        hook.
        """

        hook_names = ["queuejob_hook1"]
        hook_attrib = {'event': 'queuejob', 'enabled': 'True'}
        for hook_name in hook_names:
            hook_script = self.hooks[hook_name]
            retval = self.server.create_import_hook(hook_name,
                                                    hook_attrib,
                                                    hook_script,
                                                    overwrite=True)
            self.assertTrue(retval)

        # Create a long select statement for the job
        loop_str = "1:host=testnode"
        long_select = loop_str
        for loop_i in range(1, 5120, len(loop_str) + 1):
            long_select += "+" + loop_str

        select_len = len(long_select)
        long_select = "select=" + long_select
        job = Job(TEST_USER1, attrs={ATTR_l: long_select})
        jid = self.server.submit(job)
        job_status = self.server.status(JOB, id=jid)
        select_resource = job_status[0]['Resource_List.select']
        self.assertTrue(select_len == len(select_resource))

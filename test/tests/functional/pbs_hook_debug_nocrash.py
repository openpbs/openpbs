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


class TestHookDebugNoCrash(TestFunctional):

    """
    This tests to make sure the following does not occur:
          Hook debug causes file descriptor leak that crashes PBS server

    PRE: Have 3 queuejob hooks, qjob1, qjob2, qjob3 with order=1, order=2,
         order=3 respectively. qjob1 and qjob2 have debug=True while
         order=3 has debug=False. Try submitting 1000 jobs.
    POST: On a fixed PBS, this test case will run to completion.
          On a PBS containing the bug, the test could fail on a server crash,
          a failure in qsub with "Invalid credential", or even a qstat
          hang with ptl returning:
             corretja: /opt/pbs/bin/qstat -f 4833.corretja
              2016-07-08 12:56:52,799 INFO     TIMEDOUT
          and server_logs having the message "Too many open files".

         This is because a previous bug causes pbs_server to not close the
         debug output file descriptors opened by subsequent hook executions.

         NOTE: This is assuming on one's local system, we have the
                follwoing limit:
                # ulimit -a
                ...
                open files                      (-n) 1024
    """

    # Class variables
    open_files_limit_expected = 1024

    def setUp(self):
        ret = self.du.run_cmd(
            self.server.hostname, [
                'ulimit', '-n'], as_script=True, logerr=False)
        self.assertEqual(ret['rc'], 0)
        open_files_limit = ret['out'][0]
        if (open_files_limit == "unlimited") or (
                int(open_files_limit) > self.open_files_limit_expected):
            msg = "\n'This test requires 'open files' system limit"
            msg += " to be <= %d " % self.open_files_limit_expected
            msg += "(current value=%s)." % open_files_limit
            self.skipTest(msg)
        TestFunctional.setUp(self)

    def test_hook_debug_no_crash(self):

        hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "hook %s executed" % (e.hook_name,))
"""
        hook_name = "qjob1"
        a = {
            'event': "queuejob",
            'enabled': 'True',
            'debug': 'True',
            'order': 1}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        hook_name = "qjob2"
        a = {
            'event': "queuejob",
            'enabled': 'True',
            'debug': 'True',
            'order': 2}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        hook_name = "qjob3"
        a = {
            'event': "queuejob",
            'enabled': 'True',
            'debug': 'False',
            'order': 2}
        rv = self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'},
                            expect=True)

        for i in range(1000):
            j = Job(TEST_USER)
            a = {
                'Resource_List.select': '1:ncpus=1',
                'Resource_List.walltime': 3600}
            j.set_attributes(a)
            j.set_sleep_time("5")
            jid = self.server.submit(j)
            self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

# coding: utf-8

# Copyright (C) 1994-2016 Altair Engineering, Inc.
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

import time
from tests.functional import *


@tags('cray')
class TestSuspendResumeOnCray(TestFunctional):
    """
    Test special cases where suspend/resume functionality differs on cray
    as compared to other platforms.
    This test suite expects the platform to be 'cray' and assumes that
    suspend/resume feature is enabled on it.
    """
    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on a Cray")
        TestFunctional.setUp(self)

    def test_default_restrict_res_to_release_on_suspend_setting(self):
        """
        Check that on Cray restrict_res_to_release_on_suspend is always set
        to 'ncpus' by default
        """

        # Set restrict_res_to_release_on_suspend server attribute
        a = {ATTR_restrict_res_to_release_on_suspend: 'ncpus'}
        self.server.expect(SERVER, a)

    def test_exclusive_job_not_suspended(self):
        """
        If a running job is a job with exclusive placement then this job can
        not be suspended.
        This test is checking for a log message which is an unstable
        interface and may need change in future when interface changes.
        """

        msg_expected = "BASIL;ERROR: ALPS error: apsched: \
at least resid .* is exclusive"
        # Submit a job
        j = Job(TEST_USER, {ATTR_l+'.select': '1:ncpus=1',
                            ATTR_l+'.place': 'excl'})
        check_after = int(time.time())
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # suspend job
        try:
            self.server.sigjob(jobid=jid, signal="suspend")
        except PbsSignalError as e:
            self.assertTrue("Switching ALPS reservation failed" in e.msg[0])

        self.server.expect(JOB, 'exec_host', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        ehost = job_stat[0]['exec_host'].partition('/')[0]
        run_mom = self.moms[ehost]
        s = run_mom.log_match(msg_expected, starttime=check_after, regexp=True,
                              max_attempts=10)
        self.assertTrue(s)

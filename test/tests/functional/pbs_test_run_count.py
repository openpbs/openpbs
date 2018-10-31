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


class Test_run_count(TestFunctional):
    """
    Test suite to test run_count attribute of a job.
    """

    def create_reject_begin_hook(self):
        start_time = int(time.time())
        name = "h1"
        body = ("import pbs\n"
                "e=pbs.event()\n"
                "e.reject()\n")
        attr = {'event': 'execjob_begin'}
        self.server.create_import_hook(name, attr, body)

        # make sure hook has propogated to mom
        self.mom.log_match("h1.HK;copy hook-related file request received",
                           existence=True, starttime=start_time)

    def check_run_count(self, input_count="0", output_count="21"):
        """
        Creates a hook, submits a job and checks the run count.
        input_count is the user requested run_count and output_count
        is the run_count attribute of job from the scheduler.
        """
        # Create an execjob_begin hook that rejects the job
        self.create_reject_begin_hook()

        a = {ATTR_W: "run_count=" + input_count}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': "H", 'run_count': output_count},
                           attrop=PTL_AND, id=jid)

    def test_run_count_overflow(self):
        """
        Submit a job that requests run count exceeding 64 bit integer limit
        and see that such a job gets rejected.
        """
        a = {ATTR_W: "run_count=18446744073709551616"}
        j = Job(TEST_USER, a)
        try:
            self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue("illegal -W value" in e.msg[0])

    def test_large_run_count(self):
        """
        Submit a job with a large (>20) but valid run_count value and create
        an execjob_begin hook that will reject the job. Check run_count to
        make sure that the job goes to held state just after one rejection.
        This is so because if run_count is greater than 20 then PBS will hold
        the job upon the first rejection from mom.
        """

        self.check_run_count(input_count="184", output_count="185")

    def test_less_than_20_run_count(self):
        """
        Submit a job with a run count 15, create a execjob_begin
        hook to reject the job and test that the job goes
        into held state after 5 rejections
        """
        self.check_run_count(input_count="15", output_count="21")

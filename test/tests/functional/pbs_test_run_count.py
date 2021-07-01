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


class Test_run_count(TestFunctional):
    """
    Test suite to test run_count attribute of a job.
    """
    hook_name = "h1"
    hook_body = ("import pbs\n"
                 "e=pbs.event()\n"
                 "e.reject()\n")

    def create_reject_begin_hook(self):
        start_time = time.time()
        attr = {'event': 'execjob_begin'}
        self.server.create_import_hook(self.hook_name, attr, self.hook_body)

        # make sure hook has propogated to mom
        self.mom.log_match("h1.HK;copy hook-related file request received",
                           existence=True, starttime=start_time)

    def disable_reject_begin_hook(self):
        start_time = time.time()
        attr = {'enabled': 'false'}
        self.server.manager(MGR_CMD_SET, HOOK, attr, self.hook_name)

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

    def subjob_check(self, jid, sjid, maxruncount="21"):
        self.server.expect(JOB, {ATTR_state: "H", ATTR_runcount: maxruncount},
                           attrop=PTL_AND, id=sjid)
        ja_comment = "Job Array Held, too many failed attempts to run subjob"
        self.server.expect(JOB, {ATTR_state: "H",
                                 ATTR_comment: (MATCH_RE, ja_comment)},
                           attrop=PTL_AND, id=jid)
        self.disable_reject_begin_hook()
        self.server.rlsjob(jid, 's')
        self.server.expect(JOB, {ATTR_state: "R"}, id=sjid)
        ja_comment = "Job Array Began at"
        self.server.expect(JOB, {ATTR_state: "B",
                                 ATTR_comment: (MATCH_RE, ja_comment)},
                           attrop=PTL_AND, id=jid)

    def test_run_count_subjob(self):
        """
        Submit a job array and check if the subjob and the parent are getting
        held after 20 rejection from mom
        """
        # Create an execjob_begin hook that rejects the job
        self.create_reject_begin_hook()

        a = {ATTR_J: '1-2'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)
        self.subjob_check(jid=jid, sjid=j.create_subjob_id(jid, 1))

    def test_run_count_subjob_in_x(self):
        """
        Submit a job array and check if the subjob and the parent are getting
        held after 20 rejection from mom when there is another subjob in X
        """
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 1},
                            id=self.mom.shortname)

        a = {ATTR_J: '1-6'}
        j = Job(TEST_USER, a)
        j.set_sleep_time(20)
        jid = self.server.submit(j)
        self.logger.info("Waiting for second subjob to go in R state")
        self.server.expect(JOB, {ATTR_state: "R"},
                           id=j.create_subjob_id(jid, 2), offset=15)
        # Create an execjob_begin hook that rejects the job
        self.create_reject_begin_hook()
        self.logger.info("Waiting for subjob to finish")
        self.server.expect(JOB, {ATTR_state: "X"},
                           id=j.create_subjob_id(jid, 2), offset=15)

        self.subjob_check(jid=jid, sjid=j.create_subjob_id(jid, 3))

    def test_large_run_count_subjob(self):
        """
        Submit a job array with a large (>20) but valid run_count value and
        check if the subjob and the parent are getting
        held after 1 rejection from mom
        """
        # Create an execjob_begin hook that rejects the job
        self.create_reject_begin_hook()

        a = {ATTR_W: "run_count=39", ATTR_J: '1-2'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)
        sjid = j.create_subjob_id(jid, 1)
        self.subjob_check(jid, sjid, maxruncount="40")
        return sjid

    def test_large_run_count_subjob_in_x(self):
        """
        Submit a job array and check if the subjob and the parent are getting
        held after 20 rejection from mom when there is another subjob in X
        """
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 1},
                            id=self.mom.shortname)

        a = {ATTR_W: "run_count=453", ATTR_J: '1-6'}
        j = Job(TEST_USER, a)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: "R"},
                           id=j.create_subjob_id(jid, 2))
        self.server.manager(MGR_CMD_SET, SCHED, {"scheduling": "false"})
        # Create an execjob_begin hook that rejects the job
        self.create_reject_begin_hook()
        self.server.manager(MGR_CMD_SET, SCHED, {"scheduling": "true"})
        self.server.expect(JOB, {ATTR_state: "X"},
                           id=j.create_subjob_id(jid, 2))

        self.subjob_check(jid=jid, sjid=j.create_subjob_id(jid, 3),
                          maxruncount="454")

    def test_subjob_run_count_on_rerun(self):
        """
        to check if subjob which was previously held retains its run_count on
        rerun
        """
        sjid = self.test_large_run_count_subjob()
        self.server.rerunjob(sjid)
        self.server.expect(JOB, {ATTR_state: "R", ATTR_runcount: "42"},
                           attrop=PTL_AND, id=sjid)

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

    def test_qsub_N_cmdline(self):
        """
        This test case validates, illlegal characters in job name,
        cause qsub to error out
        """
        J = Job(TEST_USER, attrs={ATTR_N: 'j&whoami&gt;/tmp/b&'})
        try:
            jid = self.server.submit(J)
        except PbsSubmitError as e:
            self.assertTrue("illegal -N value" in e.msg[0])
            self.logger.info('qsub: illegal -N value.Job not submitted')
        else:
            self.logger.info('Job created with illegal name: ' + jid)
            self.assertTrue(False, "Job shouldn't be accepted")

    def test_qsub_N_jobscript(self):
        """
        This test case validates, illlegal characters in job name
        passed from job script, cause qsub to error out
        """
        j = Job(TEST_USER)
        scrpt = []
        scrpt += ['#!/bin/bash']
        scrpt += ['#PBS -N "j&whoami&gt;/tmp/b&"\n']
        scrpt += ['#PBS -j oe\n']
        scrpt += ['#PBS -m n\n']
        scrpt += ['#PBS -l select=1:ncpus=1\n']
        scrpt += ['#PBS -l walltime=00:0:15\n']
        scrpt += ['#PBS -l place=scatter:excl\n']
        scrpt += ['date +%s']
        j.create_script(body=scrpt, hostname=self.server.client)
        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue("illegal -N value" in e.msg[0])
            self.logger.info('qsub: illegal -N value.Job not submitted')
        else:
            self.logger.info('Job created with illegal name: ' + jid)
            self.assertTrue(False, "Job shouldn't be accepted")

    def test_qsub_N_job_array(self):
        """
        This test case validates, illlegal characters in job name
        for a job array, cause qsub to error out
        """
        J = Job(TEST_USER, attrs={ATTR_N: 'j&whoami&g;/tmp/b&', ATTR_J: '1-2'})
        try:
            jid = self.server.submit(J)
        except PbsSubmitError as e:
            self.assertTrue("illegal -N value" in e.msg[0])
            self.logger.info('qsub: illegal -N value.Job not submitted')
        else:
            self.logger.info('Job created with illegal name: ' + jid)
            self.assertTrue(False, "Job shouldn't be accepted")

    def test_qsub_N_validchar(self):
        """
        This test case validates whether character "."
        in job name passed via -N args in qsub works fine
        """
        j = Job(TEST_USER, {ATTR_N: 'job.scr'})
        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertNotIn('illegal -N value', e.msg[0],
                             'qsub: Not accepted "." in job name')
        else:
            self.server.expect(JOB, {'job_state': (MATCH_RE, '[RQ]')}, id=jid)
            self.logger.info('Job submitted successfully: ' + jid)

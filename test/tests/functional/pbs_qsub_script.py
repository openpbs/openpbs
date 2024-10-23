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


class TestQsubScript(TestFunctional):
    """
    This test suite validates that qsub does not modify the script file
    """

    def setUp(self):
        TestFunctional.setUp(self)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'true'})
        self.qsub_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub')
        self.sub_dir = self.du.create_temp_dir(asuser=TEST_USER)

    def test_qsub_basic_job(self):
        """
        This test case ensures that #PBS directive lines are not
        modified
        """
        script = """#!/bin/sh
        #PBS -m n
        cat $0
        """

        fn = self.du.create_temp_file(body=script, asuser=TEST_USER)
        cmd = [self.qsub_cmd, fn]
        rv = self.du.run_cmd(self.server.hostname,
                             cmd=cmd,
                             runas=TEST_USER,
                             cwd=self.sub_dir)
        self.assertEqual(rv['rc'], 0, 'qsub failed')
        jid = rv['out'][0]
        self.logger.info("Job ID: %s" % jid)

        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        job_status = self.server.status(JOB, id=jid, extend='x')
        if job_status:
            job_output_file = job_status[0]['Output_Path'].split(':')[1]
        rc = self.du.cmp(fileA=fn, fileB=job_output_file, runas=TEST_USER)
        self.assertEqual(rc, 0, 'cmp of job files failed')

    def test_qsub_line_extensions(self):
        """
        This test case ensures that only #PBS directive lines are treated
        as candidates for line extension
        """
        script = '''\
#!/bin/sh
#PBS -m \\
\\
n
# This is a test comment that shouldn't be extended \\
cat $0
'''
        expected_script = '''\
#!/bin/sh
#PBS -m n
# This is a test comment that shouldn't be extended \\
cat $0
'''

        j = Job()
        j.create_script(body=script, asuser=TEST_USER)
        submitted_script = j.script
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        job_status = self.server.status(JOB, id=jid, extend='x')
        if job_status:
            job_output_file = job_status[0]['Output_Path'].split(':')[1]
        expected_fn = self.du.create_temp_file(
            body=expected_script, asuser=TEST_USER)
        rc = self.du.cmp(fileA=expected_fn,
                         fileB=job_output_file, runas=TEST_USER)
        self.assertEqual(rc, 0, 'cmp of job files failed')

    def test_qsub_crlf(self):
        """
        This test case check the qsub rejects script ending with cr,lf.
        """
        script = """#!/bin/sh\r\nhostname\r\n"""
        j = Job(TEST_USER)
        j.create_script(script)
        fail_msg = 'qsub didn\'t throw an error'
        with self.assertRaises(PbsSubmitError, msg=fail_msg) as c:
            self.server.submit(j)
        msg = 'qsub: script contains cr, lf'
        self.assertEqual(c.exception.msg[0], msg)

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


class TestQsubOptionsArguments(TestFunctional):
    """
    validate qsub submission with a script and executable.
    note: The no-arg test is an interactive job, which is tested in
    SmokeTest.test_interactive_job
    """
    fn = None

    def setUp(self):
        TestFunctional.setUp(self)
        script = '/bin/hostname'
        self.fn = self.du.create_temp_file(body=script)
        self.qsub_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub')

    def test_qsub_with_script_executable(self):
        """
        submit a job with a script and executable
        """
        cmd = [self.qsub_cmd, self.fn, '--',  '/bin/sleep 10']
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        failed = rv['rc'] == 2 and rv['err'][0].split(' ')[0] == 'usage:'
        self.assertTrue(failed, 'qsub should have failed, but did not fail')

    def test_qsub_with_script_dashes(self):
        """
        submit a job with a script and dashes
        """
        cmd = [self.qsub_cmd, self.fn, '--']
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        failed = rv['rc'] == 2 and rv['err'][0].split(' ')[0] == 'usage:'
        self.assertTrue(failed, 'qsub should have failed, but did not fail')

    def test_qsub_with_dashes(self):
        """
        submit a job with only dashes
        """
        cmd = [self.qsub_cmd, '--']
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        failed = rv['rc'] == 2 and rv['err'][0].split(' ')[0] == 'usage:'
        self.assertTrue(failed, 'qsub should have failed, but did not fail')

    def test_qsub_with_script(self):
        """
        submit a job with only a script
        """
        cmd = [self.qsub_cmd, self.fn]
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        self.assertEquals(rv['rc'], 0, 'qsub failed')

    def test_qsub_with_executable(self):
        """
        submit a job with only an executable
        """
        cmd = [self.qsub_cmd, '--', '/bin/sleep 10']
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        self.assertEquals(rv['rc'], 0, 'qsub failed')

    def test_qsub_with_option_executable(self):
        """
        submit a job with an option and executable
        """
        cmd = [self.qsub_cmd, '-V', '--', '/bin/sleep', '10']
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        self.assertEquals(rv['rc'], 0, 'qsub failed')

    def test_qsub_with_option_script(self):
        """
        submit a job with an option and script
        """
        cmd = [self.qsub_cmd, '-V', self.fn]
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        self.assertEquals(rv['rc'], 0, 'qsub failed')

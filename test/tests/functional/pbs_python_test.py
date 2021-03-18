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


import subprocess
from subprocess import PIPE, Popen

from tests.functional import *


class Test_pbs_python(TestFunctional):
    """
    This test suite tests pbs_python executable
    and makes sure it works fine.
    """

    def test_pbs_python(self):
        """
        This method spawns a python process using
        pbs_python and checks for the result
        """
        fn = self.du.create_temp_file(prefix='test', suffix='.py',
                                      body="print(\"Hello\")", text=True)
        self.logger.info("created temp python script " + fn)
        pbs_python = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                  "bin", "pbs_python")
        msg = ['Hello']
        cmd = [pbs_python] + [fn]
        rc = self.du.run_cmd(cmd=cmd, sudo=True)
        self.assertTrue('out' in rc)
        self.assertEqual(rc['out'], msg)

    def test_pbs_python_zero_size(self):
        """
        This method verifies that there are no shenanigans
        when using pbs.size('0mb') et al
        """
        fn = self.du.create_temp_file(
            prefix='test_0mb', suffix='.py',
            body="import pbs\n"
                 "if pbs.size('10mb') > pbs.size('0mb'):\n"
                 "    pbs.event().accept()\n"
                 "else:\n"
                 "    pbs.event().reject()\n",
            text=True)
        self.logger.info("created test python script " + fn)
        fn2 = self.du.create_temp_file(
            prefix='dummy',
            suffix='.in',
            body="pbs.event().type=exechost_startup\n",
            text=True)
        self.logger.info("created dummy input file " + fn2)

        msg = "pbs.event().accept=True"
        pbs_python = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                  "bin", "pbs_python")
        cmd = [pbs_python] + ['--hook', '-i', fn2, fn]
        self.logger.info("running %s" % repr(cmd))
        rc = self.du.run_cmd(cmd=cmd, sudo=True)
        self.assertTrue('out' in rc, "command has no output")
        combined_output = '\n'.join(rc['out'])
        self.assertTrue(msg in combined_output, "Test hooklet rejected event")
        self.logger.info("Test hooklet accepted event")

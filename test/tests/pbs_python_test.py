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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
# Commercial License Information: 
#
# The PBS Pro software is licensed under the terms of the GNU Affero General 
# Public License agreement ("AGPL"), except where a separate commercial license 
# agreement for PBS Pro version 14 or later has been executed in writing with Altair.
# 
# Altair’s dual-license business model allows companies, individuals, and 
# organizations to create proprietary derivative works of PBS Pro and distribute 
# them - whether embedded or bundled with other software - under a commercial 
# license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™", 
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
# trademark licensing policies.


from ptl.utils.pbs_testsuite import *
import os
import subprocess
from subprocess import Popen,PIPE

class Test_pbs_python(PBSTestSuite):
	"""
	This test suite tests pbs_python executable
	and makes sure it works fine.
	"""
	def test_pbs_python(self):
		"""
		This method spawns a python process using 
		pbs_python and checks for the result
		"""
                fd,fn = tempfile.mkstemp(prefix='test', suffix='.py', text=True)
                os.write(fd,"print \"Hello\"")
                os.close(fd)
                pbs_python = self.server.pbs_conf['PBS_EXEC'] + "/bin/pbs_python"
                msg = ['Hello']
                cmd = [pbs_python] + [fn]
                rc = self.du.run_cmd(cmd=cmd, sudo=True)
                self.assertEqual(rc['out'], msg)

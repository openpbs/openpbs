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

from tests.functional import *


class Test_root_script(TestFunctional):
    """
    Test suite to test whether the root owned script is getting rejected
    and the comment is getting updated when root_reject_scripts set to true.
    """

    def test_root_owned(self):
	"""
	Edit the mom config to reject root script
	submit a script as root and observe the job comment.
	"""
	mom_conf_attr = {'$reject_root_scripts': 'true'}
	self.mom.add_config(mom_conf_attr)
	self.mom.restart()
	a = {'acl_roots': 'root'}
	self.server.manager(MGR_CMD_SET, SERVER, a)
	sleep_5 = """#!/bin/bash
	sleep 5
	"""
	j = Job(ROOT_USER)
	j.create_script(sleep_5)
	jid = self.server.submit(j)
	rv = self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
	self.assertTrue(rv)
	try:
		_comment = 'Not Running: PBS Error: Execution server rejected request'
		rv = self.server.expect(JOB, {'comment': _comment}, id=jid,
				    offset=2, max_attempts=2, interval=2)
		self.assertTrue(rv)
	except PtlExpectError, e:
	    self.assertTrue(False)
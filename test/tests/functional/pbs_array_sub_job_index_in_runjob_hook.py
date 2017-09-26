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


class TestArraySubJobIndexInRunjobHook(TestFunctional):
    """
    This test suite tests the index value in runjob event hook
    for array and normal job
    """
    hook_script = """
import pbs
e = pbs.event()
j = e.job
pbs.logmsg(pbs.LOG_DEBUG, "job_id=%s" % j.id)
pbs.logmsg(pbs.LOG_DEBUG, "sub_job_array_index=%s"
           % j.array_index)
e.accept()
"""

    def test_array_sub_job_index(self):
        """
        Submit a job array. Check the array sub-job index value
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.hook_script, overwrite=True)
        self.assertTrue(rv)
        j1 = Job(TEST_USER)
        lower = 1
        upper = 3
        j1.set_attributes({ATTR_J: '%d-%d' % (lower, upper)})
        self.server.submit(j1)
        for i in range(lower, upper + 1):
            self.server.log_match("sub_job_array_index=%d" % (i),
                                  max_attempts=10, interval=1)

    def test_normal_job_index(self):
        """
        Submit a normal job. Check the job index value which should be None
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.hook_script, overwrite=True)
        self.assertTrue(rv)
        j1 = Job(TEST_USER)
        self.server.submit(j1)
        self.server.log_match("sub_job_array_index=None",
                              max_attempts=10, interval=1)

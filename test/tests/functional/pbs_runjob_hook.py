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


class TestRunJobHook(TestFunctional):
    """
    This test suite tests the runjob hook
    """
    index_hook_script = """
import pbs
e = pbs.event()
j = e.job
pbs.logmsg(pbs.LOG_DEBUG, "job_id=%s" % j.id)
pbs.logmsg(pbs.LOG_DEBUG, "sub_job_array_index=%s"
           % j.array_index)
e.accept()
"""

    reject_hook_script = """
import pbs
pbs.event().reject("runjob hook rejected the job")
"""

    def test_array_sub_job_index(self):
        """
        Submit a job array. Check the array sub-job index value
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.index_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        lower = 1
        upper = 3
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_J: '%d-%d' % (lower, upper)})
        self.server.submit(j1)
        for i in range(lower, upper + 1):
            self.server.log_match("sub_job_array_index=%d" % (i),
                                  starttime=self.server.ctime)

    def test_normal_job_index(self):
        """
        Submit a normal job. Check the job index value which should be None
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.index_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        j1 = Job(TEST_USER)
        self.server.submit(j1)
        self.server.log_match("sub_job_array_index=None",
                              starttime=self.server.ctime)

    def test_reject_array_sub_job(self):
        """
        Test to check array subjobs,
        jobs should run after runjob hook enabled set to false.
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.reject_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_J: '1-3'})
        jid = self.server.submit(j1)
        msg = "Not Running: PBS Error: runjob hook rejected the job"
        self.server.expect(JOB, {'job_state': 'Q', 'comment': msg}, id=jid)
        a = {'enabled': 'false'}
        self.server.manager(MGR_CMD_SET, HOOK, a, id=hook_name,
                            expect=True, sudo=True)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'},
                            expect=True)
        self.server.expect(JOB, {'job_state': 'B'}, id=jid)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')

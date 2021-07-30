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


class TestCheckJobAttrib(TestFunctional):
    """
    This testsuite is to validate job attributes and values
    """

    def test_exec_vnode_after_job_rerun(self):
        """
        Test unsetting of exec_vnode of a job which got requeued
        after stage-in and make sure stage-in files are cleaned up.
        """
        hook_name = "momhook"
        hook_body = "import pbs\npbs.event().reject('my custom message')\n"
        a = {'event': 'execjob_begin', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, a, hook_body)

        self.server.log_match(".*successfully sent hook file.*" +
                              hook_name + ".PY" + ".*", regexp=True,
                              max_attempts=100, interval=5)
        storage_info = {}
        starttime = int(time.time())
        stagein_path = self.mom.create_and_format_stagein_path(
            storage_info, asuser=str(TEST_USER))
        a = {ATTR_stagein: stagein_path}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=UNSET)
        # make scheduling off to avoid any race conditions
        # otherwise scheduler tries to run job till it reached H state
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.expect(JOB, {'run_count': (GT, 0)}, id=jid)
        self.server.log_match('my custom message', starttime=starttime)
        path = stagein_path.split("@")
        msg = "Staged in file not cleaned"
        self.assertFalse(self.mom.isfile(path[0]), msg)

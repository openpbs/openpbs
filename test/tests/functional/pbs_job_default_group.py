# coding: utf-8

# Copyright (C) 1994-2022 Altair Engineering, Inc.
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

import pwd
from tests.functional import *


class TestJobDefaultGroup(TestFunctional):
    """
    This test suite contains test for job which gets default group
    """

    def test_job_with_default_group(self):
        """
        When a user group is not present on server machine
        then job will get a "-default-" group set on it.
        And MOM should be able to run that job
        """
        if self.server.hostname == self.mom.hostname:
            self.skipTest("Server and Execution host must be different")
        # add a temporary new user on execution host and assume that user
        # will be created and check user is not present on server host
        self.user_name = "ptlpbstestuser1"
        try:
            pwd.getpwnam(self.user_name)
            # user is present in server host, must delete user before
            # qsub
            cmd = f"userdel {self.user_name}"
            res = self.du.run_cmd(self.server.hostname, cmd=cmd, sudo=True)
            if res["rc"] != 0:
                raise PtlException("Unable to delete user on server host")
            self.logger.info(f"Deleted {self.user_name} on server host.")
        except KeyError:
            # good! user is not present on server host
            # just as we needed
            pass
        self.testuser_created = True
        cmd = f"useradd -m {self.user_name}"
        res = self.du.run_cmd(self.mom.hostname, cmd=cmd, sudo=True)
        if res["rc"] != 0:
            self.testuser_created = False
            raise PtlException("Unable to create user on execution host")
        attr = {"flatuid": True}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        starttime = int(time.time())
        user = PbsUser(self.user_name)
        self.server.client = self.mom.hostname
        jid = self.server.submit(Job(user), submit_dir="/tmp")
        self.server.client = self.server.hostname
        attr = {"job_state": "R"}
        self.server.expect(JOB, attr, id=jid)
        self.mom.log_match(
            f"Job;{jid};No Group Entry for Group -default-",
            starttime=starttime,
            existence=False,
            max_attempts=30,
        )

    def tearDown(self):
        super().tearDown()
        if self.testuser_created:
            cmd = f"userdel {self.user_name}"
            self.du.run_cmd(self.mom.hostname, cmd=cmd, sudo=True)

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


class TestUnknownResourceHookUpdate(TestFunctional):
    """
    Test that a resource that is not known to the server and is
    updated in an execjob_epilogue hook doesn't crash the server.
    """

    def test_epilogue_update(self):
        """
        Test setting resources_used values of resources that
        are unknown to the server, using an epilogue hook.
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

        hook_body = "import pbs\n"
        hook_body += "e = pbs.event()\n"
        hook_body += "hstr=\'" + "unkown_resource" + "\'\n"
        hook_body += "e.job.resources_used[\"foo_str\"] = 'unknown resource'\n"
        hook_body += "e.job.resources_used[\"foo_i\"] = 5\n"

        a = {'event': 'execjob_epilogue', 'enabled': 'True'}
        self.server.create_import_hook("ep", a, hook_body)

        J = Job()
        J.set_sleep_time(1)
        jid = self.server.submit(J)

        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')

        # Make sure the server is still up
        self.server.isUp()

        # Server_logs would only show the first resource it has failed to
        # update
        log_match = 'unable to update attribute resources_used.foo_str '
        log_match += 'in job_obit'
        self.server.log_match("%s;.*%s.*" % (jid, log_match), regexp=True)

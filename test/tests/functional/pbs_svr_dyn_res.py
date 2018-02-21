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
from ptl.lib.pbs_ifl_mock import *


class TestServerDynRes(TestFunctional):
    def test_invalid_script_out(self):
        """
        Test that the scheduler handles incorrect output from server_dyn_res
        script correctly
        """
        # Create a server_dyn_res of type long
        attr = {"type": "long"}
        resname = "mybadres"
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id=resname, expect=True)

        # Add it as a server_dyn_res that returns a string output
        script_body = "echo abc"
        filename = "badoutfile"
        tmpfilepath = os.path.join(os.sep, "tmp", filename)
        with open(tmpfilepath, "w") as fd:
            fd.write(script_body)
        self.scheduler.add_server_dyn_res(resname, file=tmpfilepath)

        # Add it to the scheduler's 'resources' line
        self.scheduler.add_resource(resname)

        # Submit a job
        j = Job(TEST_USER)
        jid = self.server.submit(j)

        # Make sure that "Problem with creating server data structure"
        # is not logged in sched_logs
        self.scheduler.log_match("Problem with creating server data structure",
                                 existence=False, max_attempts=10)

        # Also check that "Script %s returned bad output"
        # is logged
        self.scheduler.log_match("%s returned bad output" % (filename))

        # The scheduler uses 0 as the available amount of the dynamic resource
        # if the server_dyn_res script output is bad
        # So, submit a job that requests 1 of the resource
        attr = {"Resource_List." + resname: 1}
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        # The job shouldn't run
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        # Check for the expected log message for insufficient resources
        self.scheduler.log_match(
            "Insufficient amount of server resource: %s (R: 1 A: 0 T: 0)"
            % (resname))

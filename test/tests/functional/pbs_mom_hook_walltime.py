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


class TestMomHookWalltime(TestFunctional):

    def test_mom_hook_not_counted_in_walltime(self):
        """
        Test that time spent on mom hooks is not counted in walltime of the job
        """
        hook_name_event_dict = {
            'begin': 'execjob_begin',
            'prologue': 'execjob_prologue',
            'launch': 'execjob_launch',
            'epilogue': 'execjob_epilogue',
            'preterm': 'execjob_preterm',
            'end': 'execjob_end'
        }
        hook_script = (
            "import pbs\n"
            "import time\n"
            "time.sleep(2)\n"
            "pbs.event().accept\n"
        )
        hook_attrib = {'event': '', 'enabled': 'True'}
        for name, event in hook_name_event_dict.items():
            hook_attrib['event'] = event
            self.server.create_import_hook(name, hook_attrib, hook_script)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})
        job = Job(TEST_USER)
        job.set_sleep_time(3)
        jid = self.server.submit(job)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid, extend='x',
                           offset=15)
        self.server.expect(JOB, {'resources_used.walltime': 5}, op=LE, id=jid,
                           extend='x')

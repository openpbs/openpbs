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


class TestQstat(TestFunctional):

    def test_job_state_count(self):
        """
        test_job_state_count: Testing if jobs in the 'W' state
        will cuase the state_count to go negative or incorrect.
        """
        # Failing stage-in operation, to put job into the waiting state
        a = {ATTR_stagein: 'inputData@' +
             self.server.hostname + ':/noDir/nofile'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'W'}, id=jid)
        # Restart server
        self.server.restart()
        qstat = self.server.status(SERVER)
        self.logger.info("qstat[0]['state_count']:" + qstat[0]['state_count'])
        state_count = qstat[0]['state_count'].split()
        all_state_count = 0
        for s in state_count:
            state = s.split(':')
            # Check for negative value
            self.assertGreaterEqual(int(state[1]), 0)
            all_state_count = all_state_count + int(state[1])
        self.logger.info("qstat[0]['total_jobs']:" + qstat[0]['total_jobs'])
        self.logger.info("all_state_count = %d", all_state_count)
        self.assertEqual(int(qstat[0]['total_jobs']), all_state_count)

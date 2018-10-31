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

from tests.performance import *


class HistoryCleanupQuasihang(TestPerformance):
    """
    This test suite aims at testing the quasihang caused by a lot of jobs
    in the history.
    Without the fix, the server takes a lot of time to respond to a client.
    With the fix, the amount of time is significantly reduced.
    """

    def setUp(self):
        TestPerformance.setUp(self)

        a = {'job_history_enable': 'True', "job_history_duration": "10:00:00"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {ATTR_rescavail + '.ncpus': 100}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

    @timeout(18000)
    def test_time_for_stat_during_history_cleanup(self):
        """
        This test case submits 50k very short jobs so that the job history
        has a lot of jobs in it.
        After submitting the jobs, the job_history_duration is reduced so
        that the server could start purging the job history.

        Another job is submitted and stat-ed. The test case then finds the
        amount of time the server takes to respond.

        The test case is not designed to pass/fail on builds with/without
        the fix.
        """
        test = ['echo test\n']
        # Submit a lot of jobs.
        for _ in range(0, 10):
            for _ in range(0, 10):
                for _ in range(0, 500):
                    j = Job(TEST_USER, attrs={ATTR_k: 'oe'})
                    j.create_script(body=test)
                    jid = self.server.submit(j)
                time.sleep(1)
            self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x',
                               offset=10, interval=2, max_attempts=100)

        a = {"job_history_duration": "00:00:05"}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j = Job(TEST_USER)
        j.set_sleep_time(10000)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        now1 = 0
        now2 = 0
        i = 0

        while now2 - now1 < 2 and i < 125:
            time.sleep(1)
            now1 = int(time.time())
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
            now2 = int(time.time())
            i += 1

        self.logger.info("qstat took %d seconds to return\n",
                         (now2 - now1))

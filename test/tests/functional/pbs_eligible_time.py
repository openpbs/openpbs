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
from ptl.utils.pbs_logutils import PBSLogUtils


class TestEligibleTime(TestFunctional):
    """
    Test suite for eligible time tests
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'eligible_time_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

    def test_qsub_a(self):
        """
        Test that jobs requsting qsub -a <time> do not accrue
        eligible time until <time> is reached
        """
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        now = int(time.time())
        now += 120
        s = time.strftime("%H%M.%S", time.localtime(now))

        J1 = Job(TEST_USER, attrs={ATTR_a: s})
        jid = self.server.submit(J1)
        self.server.expect(JOB, {ATTR_state: 'W'}, id=jid)

        self.logger.info("Sleeping 120s till job is out of 'W' state")
        time.sleep(120)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)
        # eligible_time should really be 0, but just incase there is some
        # lag on some slow systems, add a little leeway.
        self.server.expect(JOB, {'eligible_time': 10}, op=LT)

    def test_job_array(self):
        """
        Test that a job array switches from accruing eligible time
        to ineligible time when its last subjob starts running
        """
        logutils = PBSLogUtils()
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        a = {'log_events': 2047}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        J1 = Job(TEST_USER, attrs={ATTR_J: '1-3'})
        J1.set_sleep_time(20)
        jid = self.server.submit(J1)
        jid_short = jid.split('[')[0]
        sjid1 = jid_short + '[1]'
        sjid2 = jid_short + '[2]'
        sjid3 = jid_short + '[3]'

        # Capture the time stamp when accrue type changed to
        # eligible time
        msg1 = jid + ";Accrue type has changed to eligible_time"
        m1 = self.server.log_match(msg1)
        t1 = logutils.convert_date_time(m1[1].split(';')[0])

        self.server.expect(JOB, {ATTR_state: 'R'}, id=sjid1, extend='t')
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sjid2, extend='t')
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=sjid3, extend='t')

        # accrue_type = 2 is eligible_time
        self.server.expect(JOB, {'accrue_type': 2}, id=jid)

        self.logger.info("subjobs 1 and 2 finished; subjob 3 must run now")
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sjid3,
                           extend='t', offset=20)
        self.server.expect(JOB, {'accrue_type': 1}, id=jid)

        # Capture the time stamp when accrue type changed to
        # ineligible time
        msg2 = jid + ";Accrue type has changed to ineligible_time"
        m2 = self.server.log_match(msg2)
        t2 = logutils.convert_date_time(m2[1].split(';')[0])
        eligible_time = t2 - t1

        m = jid + ";Accrue type has changed to ineligible_time, "
        m += "previous accrue type was eligible_time"
        m += " for %d secs, " % eligible_time
        m += "total eligible_time=00:00:%d" % eligible_time
        self.server.log_match(m)

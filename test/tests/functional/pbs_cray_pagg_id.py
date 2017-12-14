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


@tags('cray')
class TestCrayPaggIdUniqueness(TestFunctional):
    """
    This test suite is written to verify that the PAGG ID provided to ALPS
    while confirming and releasing an ALPS reservation is not equal to the
    session ID of the job.
    This test is specific to Cray and will also not work on the Cray simulator,
    hence, will be skipped on non-Cray systems and Cray simulator.
    """
    def setUp(self):
        platform = self.du.get_platform()
        if platform != 'cray':
            self.skipTest("not a cray")
        TestFunctional.setUp(self)

    def test_pagg_id(self):
        """
        This test case submits a job, waits for it to run and then checks
        the MoM logs to confirm that the PAGG ID provided in the ALPS
        query is not equal to the session ID of the job.
        """
        j1 = Job(TEST_USER)
        jid = self.server.submit(j1)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        self.mom.log_match("Job;%s;Started, pid" % (jid,), n=100,
                           max_attempts=5, interval=5, regexp=True)

        self.server.status(JOB, [ATTR_session], jid)
        sess_id = j1.attributes[ATTR_session]

        msg = "pagg_id =\"" + sess_id + "\""
        try:
            self.mom.log_match(msg, n='ALL')
        except PtlLogMatchError:
            self.logger.info("pagg_id is not equal to session id, test passes")
        else:
            self.assertFalse("pagg_id is equal to session id, test fails.")

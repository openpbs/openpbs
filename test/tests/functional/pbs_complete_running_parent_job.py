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


class Test_complete_running_parent_job(TestFunctional):
    """
    This test suite is for testing the complete_running() procedure
    is processed for parent array job.
    """

    def setUp(self):
        """
        Set eligible_time_enable = True.
        This is due to test the issue in PP-1211
        """

        TestFunctional.setUp(self)

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'eligible_time_enable': True}, expect=True)

    def test_parent_job_S_accounting_record(self):
        """
        Submit an array job and test whether the 'S' accounting record
        is created for parent job.
        """

        J = Job(TEST_USER, attrs={ATTR_J: '1-2'})
        J.set_sleep_time(1)
        parent_jid = self.server.submit(J)

        self.server.accounting_match(msg='.*;S;' +
                                     re.escape(parent_jid) + ".*",
                                     id=parent_jid, regexp=True)

    def test_parent_job_comment_and_stime(self):
        """
        Submit an array job and test whether the comment and stime is set
        for parent job.
        """

        J = Job(TEST_USER, attrs={ATTR_J: '1-2'})
        J.set_sleep_time(10)
        parent_jid = self.server.submit(J)

        attr = {
            ATTR_comment: (MATCH_RE, 'Job Array Began at .*'),
            ATTR_stime: (MATCH_RE, '.+')
        }
        self.server.expect(JOB, attr, id=parent_jid, attrop=PTL_AND)

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


class Test_acl_groups(TestFunctional):
    """
    Test to check acl_groups and acl_resv_groups considers secondary group
    """

    def test_acl_grp_queue(self):
        """
        Set acl_groups on a queue and submit a job with a user
        for whom the set group is a secondary group
        """
        a = {'queue_type': 'execution', 'started': 't', 'enabled': 't',
             'acl_group_enable': 't', 'acl_groups': TSTGRP1}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')
        a = {'queue': 'workq2'}
        j = Job(TEST_USER1, attrs=a)
        # If 'Unauthorized Request' is found in error message the test would
        # fail as user was not able to submit job as a secondary group member
        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertFalse('Unauthorized Request' in e.msg[0])

    def test_acl_resv_groups(self):
        """
        Set acl_resv_groups on server and submit a reservation
        from a user for whom the set group is a secondary group
        """
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_resv_group_enable': 'true'})
        self.server.manager(MGR_CMD_SET, SERVER, {'acl_resv_groups': TSTGRP1})
        # If 'Requestor's group not authorized' is found in error message the
        # test would fail as user was not able to submit reservation
        # as a secondary group member
        try:
            r = Reservation(TEST_USER1)
            rstart = int(time.time()) + 10
            rend = int(time.time()) + 360
            a = {'reserve_start': rstart,
                 'reserve_end': rend}
            r.set_attributes(a)
            rid = self.server.submit(r)
        except PbsSubmitError as e:
            self.assertFalse(
                'Requestor\'s group not authorized' in e.msg[0])

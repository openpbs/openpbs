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


class Test_explicit_psets(TestFunctional):
    """
    Test if 'only_explicit_psets = True' disables the creation of pool of nodes
    with unset resources in psets.
    """

    def setUp(self):
        """
        Set the attributes 'only_explicit_psets', 'do_not_span_psets'
        to True and create 'foo' host resource.
        """
        TestFunctional.setUp(self)
        sched_qmgr_attr = {'do_not_span_psets': 'True',
                           'only_explicit_psets': 'True'}
        self.server.manager(MGR_CMD_SET, SCHED, sched_qmgr_attr)

        attr = {'type': 'string',
                'flag': 'h'}
        r = 'foo'
        rc = self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, runas=ROOT_USER, logerr=False)

    def test_only_explicit_psets(self):
        """
        Test if job with '-lplace=group=foo' can run. It shouldn't.
        """

        # submit a job that can never run with only_explicit_psets = True
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'group=foo'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        c = "Can Never Run: can't fit in the largest placement set,\
 and can't span psets"
        self.server.expect(JOB, {'comment': c}, id=jid)

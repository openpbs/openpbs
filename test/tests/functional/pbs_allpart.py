# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class TestSchedAllPart(TestFunctional):
    """
    Test the scheduler's allpart optimization
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'resources_available.ncpus': 1, 'resources_available.mem': '1gb'}
        self.server.create_vnodes('vn', a, 2, self.mom, usenatvnode=True)

    def test_free_nodes(self):
        """
        Test that if there aren't enough free nodes available, it is reported
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {'Resource_List.select': '2:ncpus=1'}
        j1 = Job(TEST_USER, a)
        jid1 = self.server.submit(j1)
        j2 = Job(TEST_USER, a)
        jid2 = self.server.submit(j2)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        a = {'job_state': 'Q', 'comment':
             'Not Running: Not enough free nodes available'}
        self.server.expect(JOB, a, id=jid2)

    def test_vscatter(self):
        """
        Test that we determine we can't run a job when there aren't enough
        free nodes available due to vscatter
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {'Resource_List.select': '1:ncpus=1'}
        j1 = Job(TEST_USER, a)
        jid1 = self.server.submit(j1)

        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'vscatter'}
        j2 = Job(TEST_USER, a)
        jid2 = self.server.submit(j2)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        a = {'job_state': 'Q', 'comment':
             'Not Running: Not enough free nodes available'}
        self.server.expect(JOB, a, id=jid2)

    def test_vscatter2(self):
        """
        Test that we can determine a job can never run if it is requesting
        more nodes than is in the complex via vscatter
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'vscatter'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)

        a = {'job_state': 'Q', 'comment':
             'Can Never Run: Not enough total nodes available'}
        self.server.expect(JOB, a, id=jid)

    def test_rassn(self):
        """
        Test rassn resource (ncpus) is unavailable and the comment is shown
        with a RAT line
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        a = {'Resource_List.select': '1:ncpus=1'}
        j1 = Job(TEST_USER, a)
        jid1 = self.server.submit(j1)

        a = {'Resource_List.select': '2:ncpus=1'}
        j2 = Job(TEST_USER, a)
        jid2 = self.server.submit(j2)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        m = 'Not Running: Insufficient amount of resource: ncpus ' + \
            '(R: 2 A: 1 T: 2)'
        a = {'job_state': 'Q', 'comment': m}
        self.server.expect(JOB, a, id=jid2)

    def test_nonexistent_non_consumable(self):
        """
        Test that a nonexistent non-consumable value is caught as 'Never Run'
        """
        a = {'Resource_List.select': '1:ncpus=1:vnode=foo'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)

        m = r'Can Never Run: Insufficient amount of resource: vnode \(foo !='
        a = {'job_state': 'Q', 'comment': (MATCH_RE, m)}
        self.server.expect(JOB, a, id=jid)

    def test_too_many_ncpus(self):
        """
        test that a job is marked as can never run if it requests more cpus
        than are available on the entire complex
        """
        a = {'Resource_List.select': '3:ncpus=1'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)

        m = 'Can Never Run: Insufficient amount of resource: ncpus ' + \
            '(R: 3 A: 2 T: 2)'
        a = {'job_state': 'Q', 'comment': m}
        self.server.expect(JOB, a, id=jid)

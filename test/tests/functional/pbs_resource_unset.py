# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of both the OpenPBS software ("OpenPBS")
# and the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# OpenPBS is free software. You can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# OpenPBS is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# PBS Pro is commercially licensed software that shares a common core with
# the OpenPBS software.  For a copy of the commercial license terms and
# conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
# Altair Legal Department.
#
# Altair's dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of OpenPBS and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair's trademarks, including but not limited to "PBS™",
# "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
# subject to Altair's trademark licensing policies.


from tests.functional import *


class TestResourceUnset(TestFunctional):
    """
    Test that resources behave properly when unset
    """
    def setUp(self):
        TestFunctional.setUp(self)

        resources = {
            'tbool': {'type': 'boolean'},
            'tstr': {'type': 'string'},
            'tlong': {'type': 'long'},
            'thbool': {'type': 'boolean', 'flag': 'h'},
            'thstr': {'type': 'string', 'flag': 'h'},
            'thlong':  {'type': 'long', 'flag': 'h'}
        }
        res_str = ''
        for r in resources:
            self.server.manager(MGR_CMD_CREATE, RSC, resources[r], id=r)
            res_str += r + ','

        res_str = res_str[:-1]
        self.scheduler.add_resource(res_str)

        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 3},
                            id=self.mom.shortname)

    def test_unset_server_resources(self):
        """
        test server resources are ignored if unset and the job runs
        """

        J1 = Job(attrs={'Resource_List.tbool': True})
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        J2 = Job(attrs={'Resource_List.tstr': "foo"})
        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        J3 = Job(attrs={'Resource_List.tlong': 1})
        jid3 = self.server.submit(J3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

    def test_unset_node_resources(self):
        """
        test if node level resources are not matched if unset.
        The job does not run.
        """
        J1 = Job(attrs={'Resource_List.thbool': True})
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

        J2 = Job(attrs={'Resource_List.thstr': "foo"})
        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        J3 = Job(attrs={'Resource_List.thlong': 1})
        jid3 = self.server.submit(J3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)

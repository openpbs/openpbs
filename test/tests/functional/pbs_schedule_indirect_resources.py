# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class TestIndirectResources(TestFunctional):
    """
    Test Scheduler resolve indirect resources correctly
    """

    def config_complex_for_grouping(self, res, res_type='string', flag='h'):
        """
        Configure the PBS complex for node grouping test
        """
        # Create a custom resource
        attr = {"type": res_type, "flag": flag}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id=res)

        # Add resource to the resources line in sched_config
        self.scheduler.add_resource(res)

        # Set resource as the node_group_key
        attr = {'node_group_enable': 'True', 'node_group_key': res}
        self.server.manager(MGR_CMD_SET, SERVER, attr)

    def submit_job(self, attr):
        """
        Helper function to submit a sleep job with provided attributes
        """
        job = Job(TEST_USER1, attr)
        jobid = self.server.submit(job)

        return (jobid, job)

    @skipOnCpuSet
    def test_node_grouping_with_indirect_res(self):
        """
        Test node grouping with indirect resources set on some nodes
        Steps:
        -> Configure the system to have 6 vnodes with custom resource 'foostr'
        set as the node_group_key
        -> Set 'foostr' to 'A', 'B', and 'C' on the first three vnodes
        -> Set 'foostr' for the next three vnodes to point to the first three
        vnodes correspondingly
        -> Verify that the last three vnodes are part of their respective
        placement sets
        """

        # Create 6 vnodes
        attr = {'resources_available.ncpus': 1}
        self.mom.create_vnodes(attr, 6)
        vn = ['%s[%d]' % (self.mom.shortname, i) for i in range(6)]
        # Configure a system with 6 vnodes and 'foostr' as node_group_key
        self.config_complex_for_grouping('foostr')

        # Set 'foostr' to 'A', 'B' and 'C' respectively for the first
        # three vnodes
        attr = {'resources_available.foostr': 'A'}
        self.server.manager(MGR_CMD_SET, NODE, attr, vn[0])
        attr = {'resources_available.foostr': 'B'}
        self.server.manager(MGR_CMD_SET, NODE, attr, vn[1])
        attr = {'resources_available.foostr': 'C'}
        self.server.manager(MGR_CMD_SET, NODE, attr, vn[2])

        # Set 'foostr' for last three vnodes as indirect resource to
        # the first three vnodes correcpondingly
        attr = {'resources_available.foostr': '@' + vn[0]}
        self.server.manager(MGR_CMD_SET, NODE, attr, vn[3])
        attr = {'resources_available.foostr': '@' + vn[1]}
        self.server.manager(MGR_CMD_SET, NODE, attr, vn[4])
        attr = {'resources_available.foostr': '@' + vn[2]}
        self.server.manager(MGR_CMD_SET, NODE, attr, vn[5])

        # Submit 3 jobs requesting 2 vnodes and check they ran on the nodes
        # within same group
        attr = {'Resource_List.select': '2:ncpus=1'}

        # since there are 6 vnodes and the test grouped them on foostr
        # resource, we now have groups in pair of vnode 0+3, 1+4, 2+5
        # check that the jobs are running on correct vnode groups.
        for i in range(3):
            jid, j = self.submit_job(attr)
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
            self.server.status(JOB, 'exec_vnode', jid)
            vn = j.get_vnodes()
            self.assertEqual(int(vn[0][-2]) + 3, int(vn[1][-2]))

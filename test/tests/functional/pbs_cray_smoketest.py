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
from ptl.utils.pbs_crayutils import CrayUtils
import os


@tags('cray', 'smoke')
class TestCraySmokeTest(TestFunctional):

    """
    Set of tests that qualifies as smoketest for Cray platform
    """

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on a Cray")
        TestFunctional.setUp(self)

        # no node in 'resv' and 'use' in apstat
        cu = CrayUtils()
        self.assertEqual(cu.count_node_summ('resv'), 0,
                         "No compute node should be having ALPS reservation")
        self.assertEqual(cu.count_node_summ('use'), 0,
                         "No compute node should be in use")

        # The number of compute nodes in State up and batch mode
        # (State = 'UP  B') should equal the number of cray_compute nodes.
        nodes_up_b = cu.count_node_state('UP  B')
        self.logger.info("Nodes with State 'UP  B' : %s" % nodes_up_b)
        nodes_up_i = cu.count_node_state('UP  I')
        self.logger.info("Nodes with State 'UP  I' : %s" % nodes_up_i)
        nodes = self.server.filter(NODE,
                                   {ATTR_rescavail + '.vntype':
                                    'cray_compute'})
        num_cray_compute = len(nodes[ATTR_rescavail + '.vntype=cray_compute'])
        self.assertEqual(nodes_up_b, num_cray_compute)
        self.logger.info("nodes in State 'UP  B': %s == cray_compute: %s" %
                         (nodes_up_b, num_cray_compute))

        # nodes are free and resources are available.
        nodes = self.server.status(NODE)
        for node in nodes:
            self.assertEqual(node['state'], 'free')
            self.assertEqual(node['resources_assigned.ncpus'], '0')
            self.assertEqual(node['resources_assigned.mem'], '0kb')

    @staticmethod
    def find_hw(output_file):
        """
        Find the string "Hello World" in the specified file.
        Return 1 if found.
        """
        found = 0
        with open(output_file, 'r') as outf:
            for line in outf:
                if "Hello World" in line:
                    found = 1
                    break
                else:
                    continue
        return found

    @tags('cray', 'smoke')
    def test_cray_login_job(self):
        """
        Submit a simple sleep job that requests to run on a login node
        and expect that job to go in running state on a login node.
        Verify that the job runs to completion and check job output/error.
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})
        j1 = Job(TEST_USER, {ATTR_l + '.vntype': 'cray_login',
                             ATTR_N: 'cray_login'})

        scr = []
        scr += ['echo Hello World\n']
        scr += ['/bin/sleep 5\n']

        sub_dir = self.du.mkdtemp(uid=TEST_USER.uid)
        j1.create_script(scr)
        jid1 = self.server.submit(j1, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        # fetch node name where the job is running and check that the
        # node is a login node
        self.server.status(JOB, 'exec_vnode', id=jid1)
        vname = j1.get_vnodes()[0]
        self.server.expect(NODE, {ATTR_rescavail + '.vntype': 'cray_login'},
                           id=vname, max_attempts=1)

        cu = CrayUtils()
        # Check if number of compute nodes in use are 0
        self.assertEqual(cu.count_node_summ('use'), 0)

        # verify the contents of output/error files
        self.server.expect(JOB, {'job_state': 'F'}, id=jid1, extend='x')
        error_file = os.path.join(sub_dir, 'cray_login.e' + jid1.split('.')[0])
        self.assertEqual(os.stat(error_file).st_size, 0,
                         msg="Job error file should be empty")

        output_file = os.path.join(
            sub_dir, 'cray_login.o' + jid1.split('.')[0])
        foundhw = self.find_hw(output_file)
        self.assertEqual(foundhw, 1, msg="Job output file incorrect")

    @tags('cray', 'smoke')
    def test_cray_compute_job(self):
        """
        Submit a simple sleep job that runs on a compute node and
        expect the job to go in running state on a compute node.
        Verify that the job runs to completion and check job output/error.
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})
        j1 = Job(TEST_USER, {ATTR_l + '.vntype': 'cray_compute',
                             ATTR_N: 'cray_compute'})

        scr = []
        scr += ['echo Hello World\n']
        scr += ['/bin/sleep 5\n']
        scr += ['aprun -b -B /bin/sleep 10\n']

        sub_dir = self.du.mkdtemp(uid=TEST_USER.uid)
        j1.create_script(scr)
        jid1 = self.server.submit(j1, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        # fetch node name where the job is running and check that the
        # node is a compute node
        self.server.status(JOB, 'exec_vnode', id=jid1)
        vname = j1.get_vnodes()[0]
        self.server.expect(NODE, {ATTR_rescavail + '.vntype': 'cray_compute'},
                           id=vname)
        # Sleep for some time before aprun actually starts
        # using the reservation
        self.logger.info(
            "Sleeping 6 seconds before aprun starts using the reservation")
        time.sleep(6)

        cu = CrayUtils()
        # Check if number of compute nodes in use is 1
        self.assertEqual(cu.count_node_summ('resv'), 1)
        if self.du.get_platform() == 'cray':
            # Cray simulator will not show anything in 'use' because
            # aprun command is just a pass through on simulator
            self.assertEqual(cu.count_node_summ('use'), 1)
        # verify the contents of output/error files
        self.server.expect(JOB, {'job_state': 'F'}, id=jid1, extend='x')
        error_file = os.path.join(
            sub_dir, 'cray_compute.e' + jid1.split('.')[0])
        self.assertEqual(os.stat(error_file).st_size, 0,
                         msg="Job error file should be empty")

        output_file = os.path.join(
            sub_dir, 'cray_compute.o' + jid1.split('.')[0])
        foundhw = self.find_hw(output_file)
        self.assertEqual(foundhw, 1, msg="Job output file incorrect")

        (cu.node_status, cu.node_summary) = cu.parse_apstat_rn()
        self.assertEqual(cu.count_node_summ('resv'), 0)
        if self.du.get_platform() == 'cray':
            self.assertEqual(cu.count_node_summ('use'), 0)

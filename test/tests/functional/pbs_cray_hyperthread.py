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


@tags('cray')
class TestCrayHyperthread(TestFunctional):

    """
    The test will submit a job script that calls aprun with the
    option that will allow callers to use the hyperthreads
    on a hyperthreaded compute node.
    """

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on a Cray")
        TestFunctional.setUp(self)

    def test_hyperthread(self):
        """
        Check for a compute node that has hyperthreads, if there is one
        submit a job to that node requesting the hyperthreads.  Check
        there are no errors in the job error output.
        If there is no node with hyperthreads, skip the test.
        """
        # Get the compute nodes from PBS and see if they are threaded
        cu = CrayUtils()
        all_nodes = self.server.status(NODE)
        threaded = 0
        for n in all_nodes:
            if n['resources_available.vntype'] == 'cray_compute':
                numthreads = cu.get_numthreads(
                    n['resources_available.PBScraynid'])
                if numthreads > 1:
                    self.logger.info("Node %s has %s hyperthreads" %
                                     (n['resources_available.vnode'],
                                      numthreads))
                    ncpus = n['resources_available.ncpus']
                    vnode = n['resources_available.vnode']
                    threaded = 1
                    break
        if not threaded:
            self.skipTest("Test suite needs nodes with hyperthreads")

        # There is a node with hyperthreads, get the number of cpus
        aprun_args = '-j %d -n %d' % (int(numthreads), int(ncpus))
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})
        j1 = Job(TEST_USER, {ATTR_l + '.select': '1:ncpus=%d:vnode=%s' %
                             (int(ncpus), vnode),
                             ATTR_N: 'hyperthread'})

        scr = []
        scr += ['hostname\n']
        scr += ['/bin/sleep 5\n']
        scr += ['aprun -b %s /bin/hostname\n' % aprun_args]

        sub_dir = self.du.mkdtemp(uid=TEST_USER.uid)
        j1.create_script(scr)
        jid1 = self.server.submit(j1, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Verify the contents of the output/error files
        self.server.expect(JOB, {'job_state': 'F'}, id=jid1, extend='x')
        error_file = os.path.join(
            sub_dir, 'hyperthread.e' + jid1.split('.')[0])
        self.assertEqual(os.stat(error_file).st_size, 0,
                         msg="Job error file should be empty")

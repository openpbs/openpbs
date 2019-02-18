# coding: utf-8

# Copyright (C) 1994-2019 Altair Engineering, Inc.
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


@tags('cray', 'mom', 'configuration')
class TestVnodePerNumaNode(TestFunctional):

    """
    This test suite is for testing the new mom_priv configuration
    parameter, vnode_per_numa_node.
    Test that the information is correctly being compressed into one vnode
    using the default setting (equivalent to FALSE).
    """

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on a Cray")
        TestFunctional.setUp(self)

    @tags('cray', 'smoke')
    def test_settings(self):
        """
        vnode_per_numa_node is unset (defaults to FALSE).
        Set $vnode_per_numa_node to TRUE
        Sum up the ncpus, memory, and naccelerators for all vnodes that
        have the same host (i.e. NUMA nodes that belong to the same compute
        node).
        Unset $vnode_per_numa_node in mom_priv/config.
        Now for each host, compare the ncpus, mem, and naccelerators against
        the values we got when $vnode_per_numa_node was set to TRUE.
        They should be equal.

        Verify that PBS created only one vnode, and:
            - PBScrayseg attribute is not set
            - ncpus is a total from all NUMA nodes of that node
            - mem is a total from all NUMA nodes of that node
            - the naccelerators value is correct
            - the accelerator_memory value is correct

        Set $vnode_per_numa_node to FALSE.
        Compare the pbsnodes output when vnode_per_numa_node was unset
        versus when vnode_per_numa_node was set to False.
        """
        dncpus = {}
        dmem = {}
        dacc = {}
        daccmem = {}

        # First we mimic old behavior by setting vnode_per_numa_node to TRUE
        # Do not HUP now, we will do so when we reset the nodes
        rv = self.mom.add_config({'$vnode_per_numa_node': True}, False)
        self.assertTrue(rv)

        # Start from a clean slate, delete any existing nodes and re-create
        # them
        momname = self.mom.shortname
        self.reset_nodes(momname)

        # Get the pbsnodes -av output for comparison later
        vnodes_pernuma = self.server.status(NODE)
        for n in vnodes_pernuma:
            if n['resources_available.host'] not in dncpus.keys():
                dncpus[n['resources_available.host']] = int(
                    n['resources_available.ncpus'])
            else:
                dncpus[n['resources_available.host']
                       ] += int(n['resources_available.ncpus'])
            if n['resources_available.host'] not in dmem.keys():
                dmem[n['resources_available.host']] = int(
                    n['resources_available.mem'][0:-2])
            else:
                dmem[n['resources_available.host']
                     ] += int(n['resources_available.mem'][0:-2])
            if 'resources_available.naccelerators' in n.keys():
                if n['resources_available.naccelerators'][0] != '@':
                    if n['resources_available.host'] not in dacc.keys():
                        dacc[n['resources_available.host']] = int(
                            n['resources_available.naccelerators'])
                    else:
                        dacc[n['resources_available.host']
                             ] += int(n['resources_available.naccelerators'])
            if 'resources_available.accelerator_memory' in n.keys():
                if n['resources_available.accelerator_memory'][0] != '@':
                    if n['resources_available.host'] not in daccmem.keys():
                        daccmem[n['resources_available.host']] = int(
                            n['resources_available.accelerator_memory'][0:-2])
                    else:
                        daccmem[n['resources_available.host']] += int(n[
                            'resources_available.accelerator_memory'][0:-2])

        # Remove the configuration setting and re-read the vnodes
        rv = self.mom.unset_mom_config('$vnode_per_numa_node', False)
        self.assertTrue(rv)
        self.reset_nodes(momname)

        vnodes_combined = self.server.status(NODE)

        # Compare the multiple vnodes values to the combined vnode output

        for n in vnodes_combined:
            if 'resources_available.PBScrayseg' in n:
                self.logger.error(
                    "ERROR resources_available.PBScrayseg was found.")
                self.assertTrue(False)

            self.assertEqual(int(n['resources_available.ncpus']), dncpus[
                n['resources_available.host']])
            self.assertEqual(int(n['resources_available.mem'][0:-2]), dmem[
                n['resources_available.host']])
            if 'resources_available.naccelerators' in n:
                self.assertEqual(int(n['resources_available.naccelerators']),
                                 dacc[n['resources_available.host']])
            if 'resources_available.accelerator_memory' in n:
                self.assertEqual(int(n['resources_available.accelerator_memory'
                                       ][0:-2]),
                                 daccmem[n['resources_available.host']])

        # Set vnode_per_numa_node to FALSE and re-read the vnodes
        rv = self.mom.add_config({'$vnode_per_numa_node': False}, False)
        self.assertTrue(rv)
        self.reset_nodes(momname)

        vnodes_combined1 = self.server.status(NODE)

        # Compare the pbsnodes output when vnode_per_numa_node was unset
        # versus when vnode_per_numa_node was set to False.
        # List of resources to be ignored while comparing.
        ignr_rsc = ['license', 'last_state_change_time']
        len_vnodes_combined1 = len(vnodes_combined1)
        len_vnodes_combined = len(vnodes_combined)
        n = 0
        if len_vnodes_combined == len_vnodes_combined1:
            self.logger.info(
                "pbsnodes outputs are equal in length")
            for vdict in vnodes_combined:
                for key in vdict:
                    if key in ignr_rsc:
                        continue
                    if key in vnodes_combined1[n]:
                        if vdict[key] != vnodes_combined1[n][key]:
                            self.fail("ERROR vnode %s has "
                                      "differing element." % key)
                    else:
                        self.fail("ERROR vnode %s has "
                                  "differing element." % key)
                n += 1

        else:
            self.fail("ERROR pbsnodes outputs differ in length.")

    def restartPBS(self):
        try:
            svcs = PBSInitServices()
            svcs.restart()
        except PbsInitServicesError as e:
            self.logger.error("PBS restart failed: \n" + e.msg)
            self.assertTrue(e.rv)

    def reset_nodes(self, hostA):
        """
        Reset nodes.
        """

        # Remove all nodes
        rv = self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.assertEqual(rv, 0)

        # Restart PBS
        self.restartPBS()

        # Create node
        rv = self.server.manager(MGR_CMD_CREATE, NODE, None, hostA)
        self.assertEqual(rv, 0)

        # Wait for 3 seconds for changes to take effect
        time.sleep(3)

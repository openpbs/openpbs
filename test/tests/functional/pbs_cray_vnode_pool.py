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


@tags('cray', 'configuration')
class TestVnodePool(TestFunctional):

    """
    This test suite tests how PBS makes use of node attribute "vnode_pool"
    It expects at least 2 moms to be specified to it while executing.
    """

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("This test can only run on a cray")
        TestFunctional.setUp(self)
        if len(self.moms.values()) < 2:
            self.skipTest("Provide at least 2 moms while invoking test")

        # The moms provided to the test may have unwanted vnodedef files.
        if self.moms.values()[0].has_vnode_defs():
            self.moms.values()[0].delete_vnode_defs()
        if self.moms.values()[1].has_vnode_defs():
            self.moms.values()[1].delete_vnode_defs()

        # Check if vnodes exist before deleting nodes.
        # Clean all default nodes because each test case will set up nodes.
        try:
            self.server.status(NODE)
            self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        except PbsStatusError as e:
            self.assertTrue("Server has no node list" in e.msg[0])

    def test_invalid_values(self):
        """
        Invalid vnode_pool values shall result in errors.
        """
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        attr_A = {'vnode_pool': '-1'}
        try:
            self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA,
                                attrib=attr_A)
        except PbsManagerError as e:
            self.assertTrue("Illegal attribute or resource value" in e.msg[0])

        attr_A = {'vnode_pool': '0'}
        try:
            self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA,
                                attrib=attr_A)
        except PbsManagerError as e:
            self.assertTrue("Illegal attribute or resource value" in e.msg[0])

        attr_A = {'vnode_pool': 'a'}
        try:
            self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA,
                                attrib=attr_A)
        except PbsManagerError as e:
            self.assertTrue("Illegal attribute or resource value" in e.msg[0])

    def test_two_moms_single_vnode_pool(self):
        """
        Same vnode_pool for two moms shall result in one mom being the
        inventory mom and the other the non-inventory mom.
        The inventory mom goes down (e.g. killed).
        Compute nodes remain up even when the inventory mom is killed,
        since another mom is reporting them.
        Check that a new inventory mom is listed in the log.
        Bring up killed mom.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {"log_events": -1})

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        attr = {'vnode_pool': '1'}

        start_time = int(time.time())

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA, attrib=attr)
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB, attrib=attr)

        self.server.log_match("Mom %s added to vnode_pool %s" %
                              (self.momB.hostname, '1'), max_attempts=5,
                              starttime=start_time)

        _msg = "Hello (no inventory required) from server"
        try:
            self.momA.log_match(_msg, max_attempts=9, starttime=start_time)
            found_in_momA = 1
        except PtlLogMatchError:
            found_in_momA = 0
        try:
            self.momB.log_match(_msg, max_attempts=9, starttime=start_time)
            found_in_momB = 1
        except PtlLogMatchError:
            found_in_momB = 0
        self.assertEqual(found_in_momA + found_in_momB,
                         1, msg="an inventory mom not chosen correctly")

        # Only one mom is inventory mom
        if (found_in_momA == 0):
            inv_mom = self.momA
            noninv_mom = self.momB
        else:
            inv_mom = self.momB
            noninv_mom = self.momA

        self.logger.info("Inventory mom is %s." % inv_mom.shortname)
        self.logger.info("Non-inventory mom is %s." %
                         noninv_mom.shortname)

        start_time = int(time.time())

        # Kill inventory mom
        inv_mom.signal('-KILL')

        # Check that former inventory mom is down
        rv = self.server.expect(
            VNODE, {'state': 'down'}, id=inv_mom.shortname,
            max_attempts=10, interval=2)
        self.assertTrue(rv)

        # Check if inventory mom changed and is listed in the server log.
        self.server.log_match(
            "Setting inventory_mom for vnode_pool %s to %s" %
            ('1', noninv_mom.shortname), max_attempts=5,
            starttime=start_time)
        self.logger.info(
            "Inventory mom is now %s in server logs." %
            (noninv_mom.shortname))

        # Check compute nodes are up
        vlist = []
        try:
            vnl = self.server.filter(
                VNODE, {'resources_available.vntype': 'cray_compute'})
            vlist = vnl["resources_available.vntype=cray_compute"]
        except Exception:
            pass

        # Loop through each compute vnode in the list and check if state = free
        for v1 in vlist:
            # Check that the node is in free state
            rv = self.server.expect(
                VNODE, {'state': 'free'}, id=v1, max_attempts=3, interval=2)
            self.assertTrue(rv)

        # Start the previous inv mom.
        inv_mom.start()

        # Check previous inventory mom is up
        rv = self.server.expect(
            VNODE, {'state': 'free'}, id=inv_mom.shortname,
            max_attempts=3, interval=2)
        self.assertTrue(rv)

    def test_two_moms_different_vnode_pool(self):
        """
        Differing vnode_pool for two moms shall result in both moms reporting
        inventory.
        """
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        attr_A = {'vnode_pool': '1'}
        attr_B = {'vnode_pool': '2'}

        start_time = int(time.time())

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA, attrib=attr_A)
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB, attrib=attr_B)

        _msg = "Hello (no inventory required) from server"
        try:
            self.momA.log_match(_msg, max_attempts=5, starttime=start_time)
            found_in_momA = 1
        except PtlLogMatchError:
            found_in_momA = 0
        try:
            self.momB.log_match(_msg, max_attempts=5, starttime=start_time)
            found_in_momB = 1
        except PtlLogMatchError:
            found_in_momB = 0
        self.assertTrue((found_in_momA + found_in_momB == 0),
                        msg="Both moms must report inventory")

    def test_invalid_usage(self):
        """
        Setting vnode_pool for an existing mom that does not have a vnode_pool
        attribute shall not be allowable.
        Setting vnode_pool for an existing mom having a vnode_pool attribute
        shall not be allowable.
        Unsetting vnode_pool for an existing mom having a vnode_pool attribute
        shall not be allowable.
        """
        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        self.logger.info("hostA is %s." % self.hostA)

        start_time = int(time.time())

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)

        attr_2 = {'vnode_pool': '2'}
        try:
            self.server.manager(
                MGR_CMD_SET, NODE, id=self.hostA, attrib=attr_2)
        except PbsManagerError as e:
            self.assertTrue("Invalid request" in e.msg[0])

        self.server.log_match("Unsupported actions for vnode_pool",
                              max_attempts=5, starttime=start_time)
        self.logger.info("Found correct server log message")

        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname

        attr_1 = {'vnode_pool': '1'}

        start_time = int(time.time())

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB, attrib=attr_1)

        attr_2 = {'vnode_pool': '2'}
        try:
            self.server.manager(MGR_CMD_SET, NODE, id=self.hostB,
                                attrib=attr_2)
        except PbsManagerError as e:
            self.assertTrue("Invalid request" in e.msg[0])

        self.server.log_match("Unsupported actions for vnode_pool",
                              max_attempts=5, starttime=start_time)
        try:
            self.server.manager(MGR_CMD_UNSET, NODE, id=self.hostB,
                                attrib='vnode_pool')
        except PbsManagerError as e:
            self.assertTrue("Illegal value for node vnode_pool" in e.msg[0])

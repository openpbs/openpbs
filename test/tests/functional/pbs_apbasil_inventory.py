# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from tests.functional import *
from string import Template
import os
import tempfile
import xml.etree.ElementTree as ET


@tags('cray', 'mom')
class TestBasilInventory(TestFunctional):
    """
    This test suite is for testing the support for BASIL 1.4 inventory
    query.Test if query is made with correct BASIL version, and that
    vnodes are getting created as per the query response.
    """
    basil_version = ['1.4', '1.3', '1.2', '1.1']

    def restartPBS(self):
        try:
            svcs = PBSInitServices()
            svcs.restart()
        except PbsInitServicesError, e:
            self.logger.error("PBS restart failed: \n" + e.msg)
            self.assertTrue(e.rv)

    def reset_nodes(self, hostA):
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

    def setUp(self):
        momA = self.mom
        if not momA.is_cray():
            self.skipTest("%s: not a cray mom." % (momA.shortname))
        mom_config = momA.parse_config()
        if '$alps_client' not in mom_config:
            self.skipTest("alps_client not set in mom config.")

        if '$vnode_per_numa_node' in mom_config:
            momA.unset_mom_config('$vnode_per_numa_node', False)

        # check if required BASIL version available on the machine.
        xml_out = self.query_alps(self.basil_version[0], 'QUERY', 'ENGINE')
        xml_tree = ET.parse(xml_out)
        os.remove(xml_out)

        response = xml_tree.find(".//ResponseData")
        status = response.attrib['status']

        if status != "SUCCESS":
            self.skipTest("Basil version %s not available on the platform" %
                          (self.basil_version[0]))

        # Reset nodes
        self.reset_nodes(momA.shortname)

    def query_alps(self, ver, method, qtype):
        """
        Send a query to ALPS of a certain type and return the xml output file.
        """
        basil_protocol = 'protocol="%s"' % (ver)
        basil_method = 'method="%s"' % (method)
        basil_qtype = 'type="%s"' % (qtype)
        queryt = Template('<BasilRequest $ver $method $qtype/>\n')
        query = queryt.substitute(ver=basil_protocol,
                                  method=basil_method, qtype=basil_qtype)
        mom_config = self.mom.parse_config()
        alps_client = mom_config['$alps_client']
        (fd, fn) = self.du.mkstemp()
        os.write(fd, query)
        os.close(fd)
        (fd, xout) = self.du.mkstemp()
        os.close(fd)
        self.du.run_cmd(cmd="%s < %s > %s" % (alps_client, fn, xout),
                        as_script=True)
        os.remove(fn)
        return xout

    def comp_node(self, vnode):
        """
        Check if compute node is found in pbsnodes -av output.
        If so check if the vnode attribute has the correct values.
        """
        name = vnode['vnode']
        try:
            pbs_node = self.server.status(NODE, id=name)[0]
        except PbsStatusError:
            self.assertFalse(
                "Cray compute node %s doesn't exist on pbs server" % (name))

        for rsc, xval in vnode.iteritems():
            resource = 'resources_available.' + rsc
            if xval != "":
                if resource in pbs_node:
                    rval = pbs_node[resource]
                    if rval == xval:
                        self.logger.info(
                            "%s\t: node has %s=%s" % (name, rsc, rval))
                        self.assertTrue(True)
                    else:
                        self.assertFalse("%s\t: node has %s=%s but XML %s=%s"
                                         % (name, resource, rval,
                                            rsc, xval))
                else:
                    self.assertFalse(
                        "%s\t: node has no resource %s" % (name, rsc))

    def init_inventory_node(self):
        node = {}
        node['vnode'] = ""
        node['arch'] = ""
        node['host'] = ""
        node['mem'] = ""
        node['ncpus'] = ""
        node['PBScrayhost'] = ""
        node['PBScraynid'] = ""
        node['vntype'] = ""
        node['accelerator_memory'] = ""
        node['accelerator_model'] = ""
        node['naccelerators'] = ""
        return node

    def test_InventoryQueryVersion(self):
        """
        Test if BASIL version is set to required BASIL version
        on cray/simulator platform.
        """

        engine_query_log = "<BasilRequest protocol=\"%s\" method=\"QUERY\" \
type=\"ENGINE\"/>" % (self.basil_version[0])
        self.mom.log_match(engine_query_log, max_attempts=3)

        basil_version_log = "alps_engine_query;The basilversion is set to " + \
            self.basil_version[0]
        self.mom.log_match(basil_version_log, max_attempts=3)

    def test_InventoryVnodes(self):
        """
        This test validates the vnode created using alps inventory query
        response.
        """
        # Parse inventory query response and fetch node information.
        xml_out = self.query_alps(self.basil_version[0], 'QUERY', 'INVENTORY')
        xml_tree = ET.parse(xml_out)
        os.remove(xml_out)
        inventory_el = xml_tree.find(".//Inventory")
        hn = inventory_el.attrib["mpp_host"]

        # Fill vnode structure using BASIL response
        for node in inventory_el.getiterator('Node'):
            role = node.attrib["role"]
            if role == 'BATCH':
                # XML values
                node_id = node.attrib["node_id"]
                cu_el = node.findall('.//ComputeUnit')
                mem_el = node.findall('.//Memory')
                ac_el = node.findall('.//Accelerator')
                page_size_kb = mem_el[0].attrib["page_size_kb"]
                page_count = mem_el[0].attrib["page_count"]

                vnode = self.init_inventory_node()
                vnode['arch'] = node.attrib['architecture']
                vnode['vnode'] = hn + '_' + node_id
                vnode['vntype'] = "cray_compute"
                vnode['mem'] = str(int(page_size_kb) * int(page_count)
                                   * len(mem_el)) + "kb"
                vnode['host'] = vnode['vnode']
                vnode['PBScraynid'] = node_id
                vnode['PBScrayhost'] = hn
                vnode['ncpus'] = str(len(cu_el))
                if ac_el:
                    vnode['naccelerators'] = str(len(ac_el))
                    vnode['accelerator_memory'] = str(
                        ac_el[0].attrib['memory_mb']) + "mb"
                    vnode['accelerator_model'] = ac_el[0].attrib['family']

                # Compare xml vnode with pbs node.
                print "Validating vnode:%s" % (vnode['vnode'])
                self.comp_node(vnode)

    def test_cray_login_node_memory_unit(self):
        """
        This test validates that cray mom node resources value remain
        unchanged before and after adding $alps_client in mom config.
        """
        mom_id = self.mom.shortname
        try:
            cray_login_node = self.server.status(NODE, id=mom_id)[0]
            self.mom.unset_mom_config('$alps_client', False)
            self.reset_nodes(mom_id)
            pbs_node = self.server.status(NODE, id=mom_id)[0]

        except PbsStatusError:
            self.assertFalse(True,
                             "Mom node %s doesn't exist on pbs server"
                             % (mom_id))

        for rsc, val in pbs_node.iteritems():
            self.assertTrue(rsc in cray_login_node,
                            ("%s\t: login node has no rsc %s") %
                            (mom_id, rsc))
            rval = cray_login_node[rsc]
            self.assertEqual(rval, val,
                             ("%s\t: pbs node has %s=%s but login "
                              "node has %s=%s") %
                             (mom_id, rsc, val, rsc, rval))

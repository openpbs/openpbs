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
from string import Template
import os
import defusedxml.ElementTree as ET


@tags('cray', 'mom')
class TestBasilQuery(TestFunctional):
    """
    This test suite is for testing the support for BASIL 1.7/1.4 basil
    query.Test if query is made with correct BASIL version, and that
    vnodes are getting created as per the query response.
    """
    basil_version = ['1.7', '1.4', '1.3']
    available_version = ""

    @staticmethod
    def init_inventory_node():
        node = {}
        node['vnode'] = ""
        node['arch'] = ""
        node['current_aoe'] = ""
        node['host'] = ""
        node['hbmem'] = ""
        node['mem'] = ""
        node['ncpus'] = ""
        node['PBScrayhost'] = ""
        node['PBScraynid'] = ""
        node['vntype'] = ""
        node['accelerator_memory'] = ""
        node['accelerator_model'] = ""
        node['naccelerators'] = ""
        return node

    def reset_nodes(self, hostA):
        # Remove all nodes
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        # Restart PBS
        self.server.restart()
        # Create node
        self.server.manager(MGR_CMD_CREATE, NODE, None, hostA)
        # Wait for 3 seconds for changes to take effect
        time.sleep(3)

    def setUp(self):
        TestFunctional.setUp(self)

        self.server.manager(MGR_CMD_SET, PBS_HOOK,
                            {'enabled': 'true', 'freq': 10},
                            id='PBS_alps_inventory_check')

        momA = self.moms.values()[0]
        if not momA.is_cray():
            self.skipTest("%s: not a cray mom." % (momA.shortname))
        mom_config = momA.parse_config()
        if '$alps_client' not in mom_config:
            self.skipTest("alps_client not set in mom config.")

        if '$vnode_per_numa_node' in mom_config:
            momA.unset_mom_config('$vnode_per_numa_node', False)

        momA.add_config({'$logevent': '0xffffffff'})

        # check if required BASIL version available on the machine.
        for ver in self.basil_version:
            xml_out = self.query_alps(ver, 'QUERY', 'ENGINE')
            xml_tree = ET.parse(xml_out)
            os.remove(xml_out)
            response = xml_tree.find(".//ResponseData")
            status = response.attrib['status']
            if status == "SUCCESS":
                self.available_version = ver
                break
        if self.available_version == "":
            self.skipTest("No supported basil version found on the platform.")

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
        fn = self.du.create_temp_file(body=query)
        xout = self.du.create_temp_file()
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
            self.assertFalse(pbs_node is None,
                             "Cray compute node %s doesn't exist on pbs server"
                             % (name))

        for rsc, xval in vnode.items():
            if rsc != 'current_aoe':
                resource = 'resources_available.' + rsc
            else:
                resource = rsc
            if xval != "":
                if resource in pbs_node:
                    rval = pbs_node[resource]
                    if rval == xval:
                        self.logger.info(
                            "%s: node has %s=%s" % (name, rsc, rval))
                        self.assertTrue(True)
                    else:
                        self.assertFalse("%s: node has %s=%s but XML %s=%s"
                                         % (name, resource, rval,
                                            rsc, xval))
                else:
                    self.assertFalse(
                        "%s\t: node has no resource %s" % (name, rsc))

    def get_knl_vnodes(self):
        xml_out = self.query_alps('1.7', 'QUERY', 'SYSTEM')
        tree = ET.parse(xml_out)
        os.remove(xml_out)
        root = tree.getroot()
        knl_vnodes = {}
        knl_info = {}

        # If node has the KNL processor then add them
        # to knl_vnodes dictionary
        for node in root.getiterator('Nodes'):
            # XML values
            role = node.attrib["role"]
            state = node.attrib["state"]
            numa_cfg = node.attrib["numa_cfg"]
            hbm_size_mb = node.attrib["hbm_size_mb"]
            hbm_cache_pct = node.attrib["hbm_cache_pct"]

            if role == 'batch' and state == 'up' and numa_cfg is not ""\
               and hbm_size_mb is not "" and hbm_cache_pct is not "":
                # derived values from XML
                knl_info['current_aoe'] = numa_cfg + '_' + hbm_cache_pct
                knl_info['hbmem'] = hbm_size_mb + 'mb'
                nid_ranges = node.text.strip()
                nid_range_list = list(nid_ranges.split(','))
                while len(nid_range_list) > 0:
                    nid_range = nid_range_list.pop()
                    nid1 = nid_range.split('-')
                    if len(nid1) == 2:
                        # range of nodes
                        r1 = int(nid1[0])
                        r2 = int(nid1[1]) + 1
                        for node_id in range(r1, r2):
                            # associate each nid with it's knl information
                            knl_vnodes['%d' % node_id] = knl_info
                    else:
                        # single node
                        node_id = int(nid1[0])
                        knl_vnodes['%d' % node_id] = knl_info
        return knl_vnodes

    def retklist(self):
        """
        Return a list of KNL vnodes, empty list if there are no KNL vnodes.
        """
        klist = []
        # Find the list of KNL vnodes
        kvnl = self.server.filter(VNODE, {'current_aoe': (NE, "")})
        if len(kvnl) == 0:
            self.skipTest(reason='No KNL vnodes present')
        else:
            klist = list(kvnl.values())[0]
            self.logger.info("KNL vnode list: %s" % (klist))
        return klist

    def set_provisioning(self):
        """
        Set provisioning enabled and aoe resource on Xeon Phi nodes.
        """
        # Check for provisioning setup
        momA = self.moms.values()[0].shortname
        serverA = self.servers.values()[0].shortname
        msg = ("Provide a mom not present on server host while invoking"
               " the test: -p moms=<m1>")
        if momA == serverA:
            self.skipTest(reason=msg)

        nodelist = self.server.status(NODE, 'current_aoe')
        for node in nodelist:
            a = {'provision_enable': 'true',
                 'resources_available.aoe': '%s' % node['current_aoe']}
            self.server.manager(MGR_CMD_SET, NODE, a, id=node['id'])

    def unset_provisioning(self):
        """
        Unset provisioning attribute and aoe resource on Xeon Phi nodes.
        """
        nodelist = self.server.status(NODE, 'current_aoe')
        for node in nodelist:
            a = ['provision_enable',
                 'resources_available.aoe']
            self.server.manager(MGR_CMD_UNSET, NODE, a, id=node['id'])

    def request_current_aoe(self):
        """
        Get the value of current_aoe set on the XeonPhi vnodes
        """
        aoe_val = self.server.status(NODE, 'current_aoe')
        req_aoe = aoe_val[0]['current_aoe']
        return req_aoe

    def test_InventoryQueryVersion(self):
        """
        Test if BASIL version is set to required BASIL version
        on cray/simulator platform.
        """
        self.mom.signal('-HUP')

        engine_query_log = "<BasilRequest protocol=\"%s\" method=\"QUERY\" \
type=\"ENGINE\"/>" % (self.basil_version[1])
        self.mom.log_match(engine_query_log, n='ALL', max_attempts=3)

        if self.available_version == '1.7':
            msg = 'This Cray system supports the BASIL 1.7 protocol'
            self.mom.log_match(msg, n='ALL', max_attempts=3)
            basil_version_log = 'alps_engine_query;The basilversion is' \
                ' set to 1.4'
        else:
            basil_version_log = 'alps_engine_query;The basilversion is' \
                ' set to ' + self.available_version
        self.mom.log_match(basil_version_log, max_attempts=3)

    def test_InventoryVnodes(self):
        """
        This test validates the vnode created using alps BASIL 1.4 & 1.7
        inventory query response.
        """
        knl_vnodes = {}
        # Parse inventory query response and fetch node information.
        xml_out = self.query_alps('1.4', 'QUERY', 'INVENTORY')
        xml_tree = ET.parse(xml_out)
        os.remove(xml_out)
        inventory_1_4_el = xml_tree.find(".//Inventory")
        hn = inventory_1_4_el.attrib["mpp_host"]

        if self.available_version == '1.7':
            knl_vnodes = self.get_knl_vnodes()

        # Fill vnode structure using BASIL response
        for node in inventory_1_4_el.getiterator('Node'):
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
                vnode['mem'] = str(int(page_size_kb) *
                                   int(page_count) * len(mem_el)) + "kb"
                vnode['host'] = vnode['vnode']
                vnode['PBScraynid'] = node_id
                vnode['PBScrayhost'] = hn
                vnode['ncpus'] = str(len(cu_el))
                if ac_el:
                    vnode['naccelerators'] = str(len(ac_el))
                    vnode['accelerator_memory'] = str(
                        ac_el[0].attrib['memory_mb']) + "mb"
                    vnode['accelerator_model'] = ac_el[0].attrib['family']

                if node_id in knl_vnodes:
                    vnode['hbmem'] = knl_vnodes[node_id]['hbmem']
                    vnode['current_aoe'] = knl_vnodes[node_id]['current_aoe']
                    vnode['vnode'] = hn + '_' + node_id

                # Compare xml vnode with pbs node.
                self.logger.info("Validating vnode:%s" % (vnode['vnode']))
                self.comp_node(vnode)

    def test_cray_login_node(self):
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
        # List of resources to be ignored while comparing.
        ignr_rsc = ['license', 'last_state_change_time']

        for rsc, val in pbs_node.items():
            if rsc in ignr_rsc:
                continue
            self.assertTrue(rsc in cray_login_node,
                            ("%s\t: login node has no rsc %s") %
                            (mom_id, rsc))
            rval = cray_login_node[rsc]
            self.assertEqual(rval, val,
                             ("%s\t: pbs node has %s=%s but login "
                              "node has %s=%s") %
                             (mom_id, rsc, val, rsc, rval))

    def test_hbmemm_rsc(self):
        """
        Create a job that requests enough HBMEM. Submit the job to
        the Server. Check if the job is in the 'R' state and if the
        job runs on a KNL vnode. Delete the job.
        """

        knl_vnodes = self.get_knl_vnodes()

        if len(knl_vnodes) == 0:
            self.skipTest(reason='No KNL vnodes present')
        else:
            self.logger.info("KNL vnode list: %s" % (knl_vnodes))

        hbm_req = 4192
        a = {'Resource_List.select': '1:hbmem=%dmb' % hbm_req}
        job = Job(TEST_USER, attrs=a)

        job_id = self.server.submit(job)
        self.server.expect(JOB, {'job_state': 'R'}, id=job_id)

        # Check that exec_vnode is a KNL vnode.`
        self.server.status(JOB, 'exec_vnode', id=job_id)
        evnode = list(job.execvnode()[0].keys())[0]
        nid = evnode.split('_')[1]
        if nid in knl_vnodes.keys():
            self.logger.info("exec_vnode %s is a KNL vnode." % (evnode))
            rv = 1
        else:
            self.logger.info("exec_vnode %s is not a KNL vnode." % (evnode))
            rv = 0
        self.assertTrue(rv == 1)

        nodes = self.server.status(NODE)
        for n in nodes:
            v_name = n['id']
            if v_name == evnode:
                hbm_assig = n['resources_assigned.hbmem']
                hbm_int = int(re.search(r'\d+', hbm_assig).group())
                hbm_in_kb = hbm_req * 1024
                self.logger.info(
                    "vnode name=%s -- hbm assigned=%s -- hbm requested=%dkb"
                    % (v_name, hbm_assig, hbm_in_kb))
                if hbm_int == hbm_in_kb:
                    self.logger.info(
                        "The requested hbmem of %s mb has been assigned." %
                        (str(hbm_req)))
                    self.assertTrue(True)
                else:
                    self.logger.info(
                        "The assigned hbmem of %s, on %s, does not match "
                        "requested hbmem of %d mb" %
                        (hbm_assig, v_name, hbm_req))
                    self.assertTrue(False)

    def test_job_request_insufficent_hbmemm_rsc(self):
        """
        Submit a job request that requests more than available HBMEM.
        Check if the job is in the 'Q' state with valid comment.
        Delete the job
        """
        # Find the list of KNL vnodes
        knl_vnodes = self.get_knl_vnodes()

        if len(knl_vnodes) == 0:
            self.skipTest(reason='No KNL vnodes present')
        else:
            self.logger.info("KNL vnode list: %s" % (knl_vnodes))

        hbm_req = 18000
        a = {'Resource_List.select': '1:hbmem=%dmb' % hbm_req}
        job = Job(TEST_USER, attrs=a)

        job_id = self.server.submit(job)

        # Check that job is in Q state with valid comment
        job_comment = "Not Running: Insufficient amount of resource: hbmem"
        self.server.expect(JOB, {'job_state': 'Q', 'comment':
                                 (MATCH_RE, job_comment)}, attrop=PTL_AND,
                           id=job_id)

    def test_job_request_knl(self):
        """
        Create a job that requests aoe should run on a KNL vnode.
        Submit the job to the Server. Check if the job runs on a KNL vnode
        and if the job is in the 'R' state.
        """
        if self.du.platform == 'craysim':
            self.skipTest(reason='Test is not applicable for Craysim')

        # Find the list of KNL vnodes
        klist = self.retklist()

        # Set provisioning attributes on KNL vnode.
        self.set_provisioning()

        # Submit job that request aoe
        req_aoe = self.request_current_aoe()
        job = Job(TEST_USER)

        job.create_script(
            "#PBS -joe -o localhost:/tmp -lselect=1:ncpus=1:aoe=%s\n"
            % req_aoe +
            " cd /tmp\n"
            "aprun -B sleep 10\n"
            "sleep 10")

        job_id = self.server.submit(job)
        self.server.expect(JOB, {'job_state': 'R'}, id=job_id)

        # Check that exec_vnode is a KNL vnode.
        self.server.status(JOB, 'exec_vnode', id=job_id)
        evnode = job.get_vnodes()[0]
        self.assertIn(evnode, klist, "exec_vnode %s is not a KNL vnode."
                      % (evnode))
        self.logger.info("exec_vnode %s is a KNL vnode." % (evnode))

        # Unset provisioning attributes.
        self.unset_provisioning()

    def test_job_request_subchunk(self):
        """
        Test job request consist of subchunks with and without aoe resource.
        """
        if self.du.platform == 'craysim':
            self.skipTest(reason='Test is not applicable for craysim')

        # Find the list of KNL vnodes
        klist = self.retklist()

        # Set provisioning attributes.
        self.set_provisioning()

        # Submit job that request sub-chunk with and without aoe resources
        req_aoe = self.request_current_aoe()
        job = Job(TEST_USER)

        job.create_script(
            "#PBS -joe -o localhost:/tmp -lplace=scatter "
            "-lselect=1:ncpus=1:aoe=%s+1:ncpus=1\n" % req_aoe +
            " cd /tmp\n"
            "aprun -B sleep 10\n"
            "sleep 10")
        job_id = self.server.submit(job)
        self.server.expect(JOB, {'job_state': 'R'}, id=job_id)

        # Check that exec_vnode is a KNL vnode.
        self.server.status(JOB, 'exec_vnode', id=job_id)
        evnode = job.get_vnodes()
        self.assertIn(evnode[0], klist, "exec_vnode %s is not a KNL vnode."
                      % (evnode[0]))
        self.logger.info("exec_vnode %s is a KNL vnode." % (evnode[0]))

        self.assertNotIn(evnode[1], klist, "exec_vnode %s is a KNL"
                         " vnode." % (evnode[1]))
        self.logger.info("exec_vnode %s is not a KNL vnode." % (evnode[1]))

        # Unset provisioning attributes.
        self.unset_provisioning()

    def test_pbs_alps_in_sync(self):
        """
        Check for the presence of message indicating PBS and ALPS are
        in sync.
        """
        # Determine if BASIL 1.7 is supported.
        try:
            rv = self.mom.log_match(
                "This Cray system supports the BASIL 1.7 protocol.",
                n='ALL', max_attempts=10)
        except PtlLogMatchError:
            self.skipTest(
                reason='Test not applicable for system not having BASIL 1.7')

        # Determine if KNL vnodes are present.
        knl_vnodes = self.get_knl_vnodes()

        if len(knl_vnodes) == 0:
            self.skipTest(reason='No KNL vnodes present')
        else:
            self.logger.info("KNL vnode list: %s" % (knl_vnodes))

        # Check for PBS ALPS Inventory Hook message.
        now = int(time.time())
        rv = self.mom.log_match("ALPS Inventory Check: PBS and ALPS"
                                " are in sync",
                                starttime=now, interval=5)
        self.assertTrue(rv)

    def test_knl_batch_to_interactive(self):
        """
        Change the mode of any two KNL nodes to interactive. Then check if the
        PBS_alps_inventory_check hook picks up on the change and nodes are
        marked as stale. Restore changes to hook and mode of KNL nodes.
        """
        if self.du.platform == 'craysim':
            self.skipTest(reason='xtprocadmin cmd is not on cray simulator')

        # Find the list of KNL vnodes
        klist = self.retklist()

        # Change mode of two KNL nodes to interactive
        if len(klist) >= 2:
            k1 = klist[0]
            k2 = klist[len(klist) - 1]
            knl1 = re.search(r'\d+', k1).group()
            knl2 = re.search(r'\d+', k2).group()

        cmd = ['xtprocadmin', '-k', 'm', 'interactive', '-n', knl1]
        ret = self.server.du.run_cmd(self.server.hostname,
                                     cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)

        cmd = ['xtprocadmin', '-k', 'm', 'interactive', '-n', knl2]
        ret = self.server.du.run_cmd(self.server.hostname,
                                     cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)

        # Do Mom HUP
        self.mom.signal('-HUP')

        # Check that the nodes are now stale.
        self.server.expect(VNODE, {'state': 'Stale'}, id=k1,
                           max_attempts=10, interval=5)
        self.server.expect(VNODE, {'state': 'Stale'}, id=k2)

        # Change nodes back to batch mode
        cmd = ['xtprocadmin', '-k', 'm', 'batch']
        ret = self.server.du.run_cmd(self.server.hostname,
                                     cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)

        # Do Mom HUP
        self.mom.signal('-HUP')

        # Check that the nodes are now free.
        self.server.expect(VNODE, {'state': 'free'}, id=k1,
                           max_attempts=10, interval=5)
        self.server.expect(VNODE, {'state': 'free'}, id=k2)

    def test_job_run_on_knl_node(self):
        """
        Change the mode of KNL nodes to batch.
        Then check if the PBS_alps_inventory_check hook picks up on the change.
        Submit job and confirm job should be in R state
        """
        if self.du.platform == 'craysim':
            self.skipTest(reason='xtprocadmin cmd is not on cray simulator')

        # Find the list of KNL vnodes
        klist = self.retklist()

        # Change mode of all nodes to interactive
        cmd = ['xtprocadmin', '-k', 'm', 'interactive']
        ret = self.server.du.run_cmd(self.server.hostname,
                                     cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)

        # Change mode of two KNL nodes to batch
        if len(klist) >= 2:
            k1 = klist[0]
            k2 = klist[len(klist) - 1]
            knl1 = re.search(r'\d+', k1).group()
            knl2 = re.search(r'\d+', k2).group()

        cmd = ['xtprocadmin', '-k', 'm', 'batch', '-n', knl1]
        ret = self.server.du.run_cmd(self.server.hostname, cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)
        cmd = ['xtprocadmin', '-k', 'm', 'batch', '-n', knl2]
        ret = self.server.du.run_cmd(self.server.hostname, cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)

        # Do Mom HUP
        self.mom.signal('-HUP')

        # Check that the nodes are Free.
        self.server.expect(VNODE, {'state': 'free'}, id=k1, max_attempts=10,
                           interval=5)
        self.server.expect(VNODE, {'state': 'free'}, id=k2)

        # Submit few jobs
        a = {'Resource_List.select': '1:vntype=cray_compute'}
        job = Job(TEST_USER, attrs=a)

        job_id = self.server.submit(job)
        self.server.expect(JOB, {'job_state': 'R'}, id=job_id)
        # Check that exec_vnode is a KNL vnode.
        self.server.status(JOB, 'exec_vnode', id=job_id)
        evnode = job.get_vnodes()[0]
        self.assertIn(evnode, klist, "exec_vnode %s is not a KNL vnode."
                      % (evnode))
        self.logger.info("exec_vnode %s is a KNL vnode." % (evnode))

        job2 = Job(TEST_USER, attrs=a)

        job_id2 = self.server.submit(job2)
        self.server.expect(JOB, {'job_state': 'R'}, id=job_id2)
        # Check that exec_vnode is a KNL vnode.
        self.server.status(JOB, 'exec_vnode', id=job_id2)
        evnode = job2.get_vnodes()[0]
        self.assertIn(evnode, klist, "exec_vnode %s is not a KNL vnode."
                      % (evnode))
        self.logger.info("exec_vnode %s is a KNL vnode." % (evnode))

        job3 = Job(TEST_USER, attrs=a)

        job_id3 = self.server.submit(job3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=job_id3)

        # Delete the Job1.
        self.server.delete(job_id, wait=True)

        # Verify Job3 should start running
        self.server.expect(JOB, {'job_state': 'R'}, id=job_id3)
        # Check that exec_vnode is a KNL vnode.
        self.server.status(JOB, 'exec_vnode', id=job_id3)
        evnode = job3.get_vnodes()[0]
        self.assertIn(evnode, klist, "exec_vnode %s is not a KNL vnode."
                      % (evnode))
        self.logger.info("exec_vnode %s is a KNL vnode." % (evnode))

    def test_validate_pbs_xeon_phi_provision_hook(self):
        """
        Verify the default attribute of pbs_hook PBS_xeon_phi_provision hook.
        """
        if self.du.platform != 'cray':
            self.skipTest(reason='pbs_hook PBS_xeon_phi_provision is not'
                          ' available on non-cray machine')

        attr = {'type': 'pbs', 'enabled': 'false', 'event': 'provision',
                'alarm': 1800, 'order': 1, 'debug': 'false',
                'user': 'pbsadmin', 'fail_action': 'none'}

        self.server.manager(MGR_CMD_LIST, PBS_HOOK,
                            attr, id='PBS_xeon_phi_provision')

        self.server.manager(MGR_CMD_SET, PBS_HOOK, {'enabled': 'true',
                                                    'alarm': 1000},
                            id='PBS_xeon_phi_provision')
        self.server.manager(MGR_CMD_LIST, PBS_HOOK, {'enabled': 'true',
                                                     'alarm': 1000},
                            id='PBS_xeon_phi_provision')

        # Reset pbs_hook value to default PBS_xeon_phi_provision hook
        self.server.manager(MGR_CMD_SET, PBS_HOOK, {'enabled': 'false',
                                                    'alarm': 1800},
                            id='PBS_xeon_phi_provision')

        self.server.manager(MGR_CMD_LIST, PBS_HOOK,
                            attr, id='PBS_xeon_phi_provision')

    def tearDown(self):
        TestFunctional.tearDown(self)
        if self.du.platform == 'cray':
            # Change all nodes back to batch mode and restart PBS
            cmd = ['xtprocadmin', '-k', 'm', 'batch']
            self.logger.info(cmd)
            ret = self.server.du.run_cmd(self.server.hostname,
                                         cmd, logerr=True)
            self.assertEqual(ret['rc'], 0)

        # Restore hook freq to 300
        self.server.manager(MGR_CMD_SET, PBS_HOOK,
                            {'enabled': 'true', 'freq': 300},
                            id='PBS_alps_inventory_check')
        # Do Mom HUP
        self.mom.signal('-HUP')

# coding: utf-8
#
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


@tags('cray')
class TestCraySocketLic(TestFunctional):

    """
    All nodes in a Cray cluster, which includes vntypes of cray_login,
    cray_compute should come up licensed when there are enough socket
    licenses.
    Setup on Cray: All compute nodes and mom nodes are in batch mode;
    ensure that there are equal to or more than socket licenses as there
    are total sockets as determined by 'pbs_topologyinfo -a -s'.
    """
    def set_provisioning(self):
        """
        Set provisioning enabled and aoe resource on Xeon Phi nodes.
        """
        nodelist = self.server.status(NODE, 'current_aoe')
        for node in nodelist:
            a = {'provision_enable': 'true',
                 'resources_available.aoe': '%s' % node['current_aoe']}
            self.server.manager(MGR_CMD_SET, NODE,
                                a, id=node['id'], expect=True)

    def return_node_list(self, vn_type, isXeonPhi):
        """
        Return a list of a type of nodes, empty list if there are none.
        """
        nodelist = []
        try:
            if vn_type is 'cray_login' or not isXeonPhi:
                nl = self.server.filter(
                    VNODE, {'resources_available.vntype': "%s" % vn_type})
                nodelist = nl["resources_available.vntype=%s" % vn_type]
            if vn_type is 'cray_compute':
                n2 = self.server.filter(
                    VNODE, {'current_aoe': (NE, "")})
                if n2:
                    nodelist_XeonPhi = n2.values()[0]
                else:
                    nodelist_XeonPhi = []
                if isXeonPhi:
                    nodelist = nodelist_XeonPhi
                else:
                    temp = set(nodelist_XeonPhi)
                    nodelist_noXeon = [x for x in nodelist
                                       if x not in temp]
                    nodelist = nodelist_noXeon
        except Exception:
            sys.exc_clear()
        return nodelist

    def get_licinfo(self):
        """
        Get value of pbs_license_info.
        """
        # Get license info.
        lic_info = self.server.status(
            SERVER, 'pbs_license_info', level=logging.INFOCLI)
        if lic_info and 'pbs_license_info' in lic_info[0]:
            lic_info = lic_info[0]['pbs_license_info']
            self.logger.info('lic_info is: %s ', lic_info)
        return lic_info

    def reset_nodes_and_licenses(self, lic_info, hostA):
        """
        Reset nodes and licenses.
        """
        # Remove all nodes
        rc = self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.assertEqual(rc, 0)

        # Unset license info
        rc = self.server.manager(MGR_CMD_UNSET, SERVER, 'pbs_license_info',
                                 runas=ROOT_USER, logerr=True)
        self.assertEqual(rc, 0)

        # Restart PBS
        self.mom.restart()
        self.server.restart()

        # Set license info
        rc = self.server.manager(MGR_CMD_SET, SERVER,
                                 {'pbs_license_info': lic_info},
                                 runas=ROOT_USER, logerr=True)
        self.assertEqual(rc, 0)

        # Create node
        hostA = self.mom.shortname
        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=hostA)
        self.assertEqual(rc, 0)

        # Wait for 2 seconds for changes to take effect
        time.sleep(2)

    def make_vn_mode(self, mode, vnlist):
        """
        Change the mode of vnodes to either 'batch' or 'interactive'.
        """
        hname1 = self.server.status(NODE, 'resources_available.PBScrayhost',
                                    id=self.moms.values()[0].shortname)
        hname = hname1[0]['resources_available.PBScrayhost']

        # Parse the vnode names for the Cray compute node id, e.g.
        # hostname_28 has a NID of 28, then save to a comma-separated
        # string that can be passed to xtprocadmin -n option.
        vnstr = ''
        for vn in vnlist:
            vn2 = re.search(r'%s_(\d+)' % hname, vn)
            if vn2:
                vn1 = vn2.group(1)
                if vn1 not in vnstr.split(','):
                    vnstr = vn1 + ',' + vnstr
        vnstr = vnstr.strip(',')

        cmd = ['xtprocadmin', '-k', 'm', mode, '-n', vnstr]
        ret = self.du.run_cmd(self.server.hostname, cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)

    def sockets_equal_usedlic(self):
        """
        Check that the server has the same amount of sockets
        as there are used socket licenses.
        """
        # Get total sockets from topology info
        svrname = self.server.pbs_server_name
        pbs_topo = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_topologyinfo')
        cmd = [pbs_topo, '-a', '-s']
        topoinfo = self.du.run_cmd(svrname, cmd, logerr=True)
        tout = topoinfo['out']

        total_sockets = 0
        for l in tout:
            total_sockets = int(l.split()[1]) + total_sockets
        self.logger.info('Total sockets: %s', total_sockets)

        # Compare total sockets with used socket licenses
        lic = self.server.status(
            SERVER, 'license_count', level=logging.INFOCLI)
        if lic and 'license_count' in lic[0]:
            lic = PbsTypeLicenseCount(lic[0]['license_count'])

            avail_sockets = int(lic['Avail_Sockets'])
            if avail_sockets > 0:
                self.logger.info(
                    'Available socket licenses: %s ', avail_sockets)
            else:
                self.logger.info(
                    'Not enough available socket licenses: %s ', avail_sockets)
                self.assertTrue(avail_sockets > 0)

            unused_sockets = int(lic['Unused_Sockets'])
            self.logger.info('Unused socket licenses: %s ', unused_sockets)

            used_sockets = avail_sockets - unused_sockets
            if total_sockets == used_sockets:
                self.logger.info('Total sockets %s equal to used sockets %s ' %
                                 (total_sockets, used_sockets))
            else:
                self.logger.info(
                    'Total sockets %s not equal to used sockets %s ' %
                    (total_sockets, used_sockets))
                self.assertEqual(total_sockets, used_sockets)

    def request_current_aoe(self):
        """
        Get the list of current aoe set on the XeonPhi vnodes
        """
        list1 = self.server.status(NODE, 'current_aoe')
        req_aoe = list1[0]['current_aoe']
        return req_aoe

    def check_node_licensed(self, vn_type, vnlist, isXeonPhi):
        """
        Check if each node of specified vntype is licensed.
        A job requesting that node type should run. Then delete job.
        """
        # Loop through each node in the list and check if licensed.
        for vn in vnlist:
            # Check that the node is licensed
            rv = self.server.expect(
                VNODE, {'license': 'l'}, id=vn, max_attempts=3, interval=2)
            self.assertTrue(rv)

        # A job requesting the node type should run.
        jobdir = self.du.get_tempdir()
        attrs = {ATTR_j: 'oe', ATTR_o: jobdir,
                 ATTR_l + '.vntype': '%s' % vn_type}
        if isXeonPhi:
            req_aoe = self.request_current_aoe()
            attrs.update({ATTR_l + '.aoe': '%s' % req_aoe})
            self.set_provisioning()
        j1 = Job(TEST_USER, attrs)
        scr = []
        scr += ['sleep 5\n']
        if vn_type is 'cray_compute':
            scr += ['aprun -B sleep 10\n']

        sub_dir = self.du.mkdtemp(uid=int(TEST_USER))
        j1.create_script(scr)
        jid1 = self.server.submit(j1, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        # Check if the job is running on node type which was requested
        self.server.status(JOB, 'exec_vnode', id=jid1)
        vname = j1.get_vnodes()[0]
        self.assertTrue(vname in vnlist,
                        "Job did not run on node with requested vntype")

        # Delete the job.
        self.server.delete(jid1, wait=True)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid1)
        return True

    def check_cray_login_list(self):
        """
        Check presence of cray_login vnode types and if they are licensed.
        """
        loginlist = self.return_node_list('cray_login', False)
        if loginlist:
            rv = self.check_node_licensed('cray_login', loginlist, False)
            if rv:
                self.logger.info("Nodes of vntype cray_login are licensed.")
        else:
            self.logger.info("There are no login nodes.")
            self.assertTrue(False, "No login nodes")
        return

    def check_cray_compute_list(self):
        """
        Check presence of cray_compute vnode types and if they are licensed.
        """
        compute_list = self.return_node_list('cray_compute', False)
        if compute_list:
            rv = self.check_node_licensed('cray_compute', compute_list, False)
            if rv:
                self.logger.info("Nodes of vntype cray_compute are licensed.")
        else:
            self.logger.info("There are no nodes of vntype cray_compute.")
        return

    def check_cray_compute_XeonPhi_list(self):
        """
        Check presence of Xeon Phi cray_compute vnode types
        and if they are licensed.
        """
        computeXP_list = self.return_node_list('cray_compute', True)
        if computeXP_list:
            rv = self.check_node_licensed('cray_compute', computeXP_list, True)
            if rv:
                self.logger.info(
                    "Xeon Phi nodes of vntype cray_compute are licensed.")
        else:
            self.logger.info(
                "There are no Xeon Phi nodes of vntype cray_compute.")
        return

    def test_cray_allvntypes_socket(self):
        """
        Scenario 1: Socket license test using all compute and mom nodes.
        Check that the server has the same amount of sockets
        as there are used socket licenses.
        Check if each compute node is socket licensed.
        Submit a job requesting licensed vnodes should run.
        """
        self.logger.info(
            "Running the socket license tests using all node types ...")
        # Reset nodes and licenses
        lic_info = self.get_licinfo()

        hostA = self.moms.values()[0].shortname
        self.reset_nodes_and_licenses(lic_info, hostA)
        rv = self.sockets_equal_usedlic()
        if rv:
            self.logger.info("Amount of sockets equal used socket licenses.")

        self.check_cray_login_list()
        self.check_cray_compute_list()
        self.check_cray_compute_XeonPhi_list()

    def test_cray_XeonPhi_login_socket(self):
        """
        Scenario 2: Socket license test using Xeon Phi cray_compute
        and cray_login nodes.
        Check that the server has the same amount of sockets
        as there are used socket licenses.
        Check if each Xeon Phi cray_compute and cray_login node is socket
        licensed. Submit a job requesting licensed vnodes should run.
        """
        # If Xeon Phi cray_compute nodes exist then run the test.
        klist = self.return_node_list('cray_compute', True)
        if klist:
            # If cray_compute nodes exist then make them interactive
            computelist = self.return_node_list('cray_compute', False)
            if computelist:
                self.make_vn_mode('interactive', computelist)
            else:
                self.logger.info("There are no vnodes of vntype cray_compute.")

            # Reset nodes and licenses
            lic_info = self.get_licinfo()

            hostA = self.moms.values()[0].shortname
            self.reset_nodes_and_licenses(lic_info, hostA)

            # If cray_compute nodes are gone then run the tests.
            computelist1 = self.return_node_list('cray_compute', False)
            if not computelist1:
                self.logger.info(
                    "Running the socket license tests using " +
                    "Xeon Phi cray_compute and login nodes ...")
                rv = self.sockets_equal_usedlic()
                if rv:
                    self.logger.info(
                        "Amount of sockets equal used socket licenses.")
                self.check_cray_login_list()
                self.check_cray_compute_XeonPhi_list()
            else:
                self.logger.info(
                    "cray_compute vnodes still exist - can't run the test.")
                self.assertFalse(computelist1)
        else:
            self.skipTest("Provide a system with Xeon Phi node that have "
                          "a vntype of cray_compute - skipping the test.")

        # Restore cray_compute nodes back to batch mode
        if computelist:
            self.make_vn_mode('batch', computelist)
            self.reset_nodes_and_licenses(lic_info, hostA)

    def test_cray_compute_login_socket(self):
        """
        Scenario 3: Socket license test using cray_compute and
        cray_login nodes.
        Check that the server has the same amount of sockets
        as there are used socket licenses.
        Check if each cray_compute and cray_login node is socket licensed.
        Submit a job requesting licensed vnodes should run.
        """
        # If cray_compute nodes exist then run the test.
        computelist = self.return_node_list('cray_compute', False)
        if computelist:
            # If Xeon Phi cray_compute nodes exist then make them interactive
            klist = self.return_node_list('cray_compute', True)
            if klist:
                self.make_vn_mode('interactive', klist)
            else:
                self.logger.info("There are no Xeon Phi cray_compute vnodes.")

            # Reset nodes and licenses
            lic_info = self.get_licinfo()

            hostA = self.moms.values()[0].shortname
            self.reset_nodes_and_licenses(lic_info, hostA)

            # If Xeon Phi cray_compute nodes are gone then run the tests
            klist1 = self.return_node_list('cray_compute', True)
            if not klist1:
                self.logger.info(
                    "Running the socket license tests using cray_compute " +
                    "and cray_login nodes ...")
                rv = self.sockets_equal_usedlic()
                if rv:
                    self.logger.info(
                        "Amount of sockets equal used socket licenses.")
                self.check_cray_login_list()
                self.check_cray_compute_list()
            else:
                self.logger.info(
                    "Xeon Phi cray_compute vnodes still exist " +
                    "- can't run the test.")
                self.assertFalse(klist1)
        else:
            self.logger.info(
                "There are no cray_compute vnodes - can't run the test.")
            self.assertTrue(False, "no cray_compute vnodes")

        # Restore Xeon Phi cray_compute nodes back to batch mode
        if klist:
            self.make_vn_mode('batch', klist)
            self.reset_nodes_and_licenses(lic_info, hostA)

    def test_cray_login_socket(self):
        """
        Scenario 4: Socket license test using only cray_login nodes.
        Check that the server has the same amount of sockets
        as there are used socket licenses.
        Check if each cray_login node is socket licensed.
        Submit a job requesting licensed vnodes should run.
        """
        # If cray_compute nodes exist then make them interactive
        computelist = self.return_node_list('cray_compute', False)
        if computelist:
            self.make_vn_mode('interactive', computelist)
        else:
            self.logger.info("There are no cray_compute vnodes.")

        # If Xeon Phi cray_compute nodes exist then make them interactive.
        klist = self.return_node_list('cray_compute', True)
        if klist:
            self.make_vn_mode('interactive', klist)
        else:
            self.logger.info("There are no Xeon Phi cray_compute vnodes.")

        # Reset nodes and licenses
        lic_info = self.get_licinfo()

        hostA = self.moms.values()[0].shortname
        self.reset_nodes_and_licenses(lic_info, hostA)

        # If all cray_compute nodes are gone then run the tests.
        computelist1 = self.return_node_list('cray_compute', False)
        klist1 = self.return_node_list('cray_compute', True)
        if not computelist1 and not klist1:
            self.logger.info(
                "Running the socket license tests using only " +
                "cray_login nodes ...")
            rv = self.sockets_equal_usedlic()
            if rv:
                self.logger.info(
                    "Amount of sockets equal used socket licenses.")
            self.check_cray_login_list()
        else:
            self.logger.info(
                "There are node types other than cray_login " +
                "- can't run the test.")
            self.assertTrue(not computelist1 and not klist1)

        # Restore all cray_compute nodes back to batch mode
        cmd = ['xtprocadmin', '-k', 'm', 'batch']
        ret = self.du.run_cmd(self.server.hostname, cmd, logerr=True)
        self.assertEqual(ret['rc'], 0)

        self.reset_nodes_and_licenses(lic_info, hostA)

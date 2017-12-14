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
import os


@tags('cray', 'mom')
class TestAlpsInventoryCheckHook(TestFunctional):
    """
    PBS mom appears not to periodically automatically re-query the
    node inventory on Cray.
    """

    def setUp(self):
        self.platform = DshUtils().get_platform()
        if self.platform != 'cray' and self.platform != 'craysim':
            self.skipTest("This is not a cray platform")

        TestFunctional.setUp(self)
        with open("/etc/xthostname") as xthost_file:
            self.crayhostname = xthost_file.readline().rstrip()

        self.server.manager(MGR_CMD_SET, PBS_HOOK,
                            {'enabled': 'true', 'freq': 3},
                            id='PBS_alps_inventory_check')

    def delete_cray_compute_node(self):
        """
        Deletes the cray compute node from pbs node list
        """
        vnl = self.server.filter(
            VNODE, {'resources_available.vntype': 'cray_compute'})
        vlist = vnl["resources_available.vntype=cray_compute"]
        self.server.manager(MGR_CMD_DELETE, NODE, id=vlist[0])

    def test_apstat_cmd(self):
        """
        Test the log when apstat is not present in the
        expected/default location, it indicates a Cray system issue.
        """
        now = int(time.time())
        if self.platform == "craysim":
            if os.path.exists("/opt/cray/alps/default/bin/stat"):
                # The file to be renamed is conflicting with existing file
                self.skipTest("Conflict in the testcase settings")
            os.rename(
                "/opt/cray/alps/default/bin/apstat",
                "/opt/cray/alps/default/bin/stat")
            try:
                self.mom.log_match(
                    "ALPS Inventory Check: apstat command can not " +
                    "be found at /opt/cray/alps/default/bin/apstat",
                    starttime=now,
                    max_attempts=10,
                    interval=2)
            finally:
                os.rename(
                    "/opt/cray/alps/default/bin/stat",
                    "/opt/cray/alps/default/bin/apstat")
        else:
            self.skipTest("This test can be run on a simulator")

    def test_xthostname(self):
        """
        Test when hook attempts to read the /etc/xthostname file to
        determine Cray hostname, but the hostname file is missing.
        """
        now = int(time.time())
        if self.platform == "craysim":
            if os.path.exists("/etc/xt"):
                # The file to be renamed is conflicting with existing file
                self.skipTest("Conflict in the testcase settings")
            os.rename("/etc/xthostname", "/etc/xt")
            try:
                self.mom.log_match(
                    "/etc/xthostname file found on this host",
                    starttime=now,
                    max_attempts=10,
                    interval=2)
            finally:
                os.rename("/etc/xt", "/etc/xthostname")
        else:
            self.skipTest("This test can be run on a simulator")

    def test_start_of_hook(self):
        """
        Test log at the start of hook processing.
        """
        now = int(time.time())
        self.mom.log_match(
            "Processing ALPS inventory for crayhost %s" % self.crayhostname,
            starttime=now,
            max_attempts=10,
            interval=2)

    def test_cray_login_nodes(self):
        """
        Test log when no nodes with vntype 'cray_login' are present.
        """
        now = int(time.time())
        mc = self.mom.parse_config()
        save = mc["$alps_client"]
        del mc["$alps_client"]
        self.mom.apply_config(mc)
        self.host = self.mom.shortname
        try:
            self.server.manager(MGR_CMD_DELETE, NODE, None, "")
            self.server.manager(MGR_CMD_CREATE, NODE, id=self.host)
            self.mom.log_match(
                "ALPS Inventory Check: No eligible " +
                "login nodes to perform inventory check",
                starttime=now,
                max_attempts=10,
                interval=2)
        finally:
            mc["$alps_client"] = save
            self.mom.apply_config(mc, False)

    def test_pbs_home_path(self):
        """
        Test log when mom_priv directory is not in the expected/default
        location (PBS_HOME), indicating a PBS installation issue.
        """
        if self.platform == "craysim":
            now = int(time.time())
            pbs_conf = self.du.parse_pbs_config(self.server.shortname)
            save = pbs_conf['PBS_HOME']
            self.du.set_pbs_config(
                self.server.shortname, confs={
                    'PBS_HOME': ''})
            try:
                self.delete_cray_compute_node()
                self.mom.log_match(
                    "ALPS Inventory Check: Internal error in retrieving " +
                    "path to mom_priv",
                    starttime=now,
                    max_attempts=10,
                    interval=2)
            finally:
                self.du.set_pbs_config(
                    self.server.shortname, confs={
                        'PBS_HOME': save})
        else:
            self.skipTest("This test can be run on a simulator")

    def test_alps_and_pbs_are_in_sync(self):
        """
        Test log when both PBS and ALPS are in sync i.e. they report the
        same number of compute nodes in the Cray cluster.
        """
        now = int(time.time())
        self.mom.log_match(
            "ALPS Inventory Check: PBS and ALPS are in sync",
            starttime=now,
            max_attempts=10,
            interval=2)

    def test_nodes_out_of_sync(self):
        """
         Test the log when PBS and ALPS are out of sync
        """
        now = int(time.time())
        self.delete_cray_compute_node()
        self.mom.log_match(
            "ALPS Inventory Check: Compute " +
            "nodes defined in ALPS, but not in PBS",
            starttime=now,
            max_attempts=10,
            interval=2)

    def test_failure_in_refreshing_nodes(self):
        """
        Test log when the Hook is unable to HUP the Mom and successfully
        refresh nodes.
        """
        if self.platform == "craysim":
            now = int(time.time())
            pbs_conf = self.du.parse_pbs_config(self.server.shortname)
            save = pbs_conf['PBS_HOME']
            self.du.set_pbs_config(
                self.server.shortname, confs={'PBS_HOME': 'xyz'})
            try:
                self.delete_cray_compute_node()
                self.mom.log_match(
                    "ALPS Inventory Check: Failure in refreshing nodes on " +
                    "login node (%s)" %
                    self.mom.hostname,
                    starttime=now,
                    max_attempts=10,
                    interval=2)
            finally:
                self.du.set_pbs_config(
                    self.server.shortname, confs={
                        'PBS_HOME': save})
        else:
            self.skipTest("This test can be run on cray a simulator")

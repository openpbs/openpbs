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

from tests.selftest import *
from ptl.utils.pbs_snaputils import *


class TestPBSTestSuite(TestSelf):
    """
    Contains tests for pbs_testsuite module's functionality
    """

    def test_revert_pbsconf_onehost(self):
        """
        Test the functionality of PBSTestSuite.revert_pbsconf()
        for a single host type 1 installation
        """
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertTrue(pbs_conf_val and len(pbs_conf_val) >= 1,
                        "Could not parse pbs.conf on host %s" %
                        (self.server.hostname))

        # Since the setUp already ran, check that the start bits are turned on
        self.assertEqual(pbs_conf_val["PBS_START_MOM"], "1")
        self.assertEqual(pbs_conf_val["PBS_START_SERVER"], "1")
        self.assertEqual(pbs_conf_val["PBS_START_SCHED"], "1")
        self.assertEqual(pbs_conf_val["PBS_START_COMM"], "1")

        self.server.pi.stop()

        # Now, change pbs.conf to turn the sched off
        pbs_conf_val["PBS_START_SCHED"] = "0"
        self.du.set_pbs_config(confs=pbs_conf_val)

        # Start PBS again
        self.server.pi.start()

        # Verify that the scheduler didn't come up
        self.assertFalse(self.scheduler.isUp())

        # Now call revert_pbsconf()
        self.revert_pbsconf()

        # Verify that the scheduler came up and start bit is 1
        self.assertTrue(self.scheduler.isUp())
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertEqual(pbs_conf_val["PBS_START_SCHED"], "1")

    def test_revert_pbsconf_remotemom(self):
        """
        Test the functionality of PBSTestSuite.revert_pbsconf()
        with a remote mom setup
        """
        remotemom = None
        for mom in self.moms.values():
            if not self.du.is_localhost(mom.hostname):
                remotemom = mom
                break
        if remotemom is None:
            self.skip_test("Test needs at least one remote Mom host,"
                           " use -p moms=<hostname>")

        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertTrue(pbs_conf_val and len(pbs_conf_val) >= 1,
                        "Could not parse pbs.conf on host %s" %
                        (self.server.hostname))

        # Check that the start bits on server host are set correctly
        self.assertEqual(pbs_conf_val["PBS_START_SERVER"], "1")
        self.assertEqual(pbs_conf_val["PBS_START_SCHED"], "1")
        self.assertEqual(pbs_conf_val["PBS_START_COMM"], "1")
        if self.server.hostname in self.moms:
            self.assertEqual(pbs_conf_val["PBS_START_MOM"], "1")
        else:
            self.assertEqual(pbs_conf_val["PBS_START_MOM"], "0")

        # Check that the remote mom's pbs.conf has mom start bit on
        pbs_conf_val = self.du.parse_pbs_config(remotemom.hostname)
        self.assertEqual(pbs_conf_val["PBS_START_MOM"], "1")

        # Now set it to 0 and restart the mom
        remotemom.pi.stop(remotemom.hostname)
        pbs_conf_val["PBS_START_MOM"] = "0"
        self.du.set_pbs_config(remotemom.hostname, confs=pbs_conf_val)
        remotemom.pi.start(remotemom.hostname)

        # Confirm that the mom is down
        self.assertFalse(remotemom.isUp())

        # Now call revert_pbsconf()
        self.revert_pbsconf()

        # Confirm that the mom came up and start bit is 1
        self.assertTrue(remotemom.isUp())
        pbs_conf_val = self.du.parse_pbs_config(remotemom.hostname)
        self.assertEqual(pbs_conf_val["PBS_START_MOM"], "1")

    def test_revert_pbsconf_corelimit(self):
        """
        Test the functionality of PBSTestSuite.revert_pbsconf() when
        PBS_CORE_LIMIT is set to a value other than the default
        """
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertTrue(pbs_conf_val and len(pbs_conf_val) >= 1,
                        "Could not parse pbs.conf on host %s" %
                        (self.server.hostname))

        # Since the setUp already ran, check that PBS_CORE_LIMIT is set to
        # unlimited
        self.assertEqual(pbs_conf_val["PBS_CORE_LIMIT"], "unlimited")

        # Now, set the core limit to 0 and restart PBS
        self.server.pi.stop()
        pbs_conf_val["PBS_CORE_LIMIT"] = "0"
        self.du.set_pbs_config(confs=pbs_conf_val)
        self.server.pi.start()

        # First, check that there's no existing core file in mom_priv
        mom_priv_path = os.path.join(self.server.pbs_conf["PBS_HOME"],
                                     "mom_priv")
        mom_priv_filenames = self.du.listdir(self.server.hostname,
                                             mom_priv_path, sudo=True,
                                             fullpath=False)
        for filename in mom_priv_filenames:
            if filename.startswith("core"):
                # Found a core file, delete it
                corepath = os.path.join(mom_priv_path, filename)
                self.du.rm(self.server.hostname, corepath, sudo=True,
                           force=True)

        # Send SIGSEGV to pbs_mom
        self.assertTrue(self.mom.isUp())
        self.mom.signal("-SEGV")
        for _ in range(20):
            ret = self.mom.isUp(max_attempts=1)
            if not ret:
                break
            time.sleep(1)
        self.assertFalse(ret, "Mom was expected to go down but it didn't")

        # Confirm that no core file was generated
        mom_priv_filenames = self.du.listdir(self.server.hostname,
                                             mom_priv_path, sudo=True,
                                             fullpath=False)
        corefound = False
        for filename in mom_priv_filenames:
            if filename.startswith("core"):
                corefound = True
                break
        self.assertFalse(corefound, "mom unexpectedly dumped core")

        # Now, call self.revert_pbsconf()
        self.revert_pbsconf()

        # Confirm that PBS_CORE_LIMIT was reverted
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertEqual(pbs_conf_val["PBS_CORE_LIMIT"], "unlimited")

        # Send another SIGSEGV to pbs_mom
        self.assertTrue(self.mom.isUp())
        self.mom.signal("-SEGV")
        for _ in range(20):
            ret = self.mom.isUp(max_attempts=1)
            if not ret:
                break
            time.sleep(1)
        self.assertFalse(ret, "Mom was expected to go down but it didn't")

        # Confirm that a core file was generated this time
        mom_priv_filenames = self.du.listdir(self.server.hostname,
                                             mom_priv_path, sudo=True,
                                             fullpath=False)
        corefound = False
        for filename in mom_priv_filenames:
            if filename.startswith("core"):
                corefound = True
                break
        self.assertTrue(corefound,
                        "mom was expected to dump core but it didn't")

    def test_revert_pbsconf_extra_vars(self):
        """
        Test the functionality of PBSTestSuite.revert_pbsconf() when
        there are extra pbs.conf variables than the default
        """
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertTrue(pbs_conf_val and len(pbs_conf_val) >= 1,
                        "Could not parse pbs.conf on host %s" %
                        (self.server.hostname))

        # Set a non-default pbs.conf variables, let's say
        # PBS_LOCALLOG, and restart PBS
        self.server.pi.stop()
        pbs_conf_val["PBS_LOCALLOG"] = "1"
        self.du.set_pbs_config(confs=pbs_conf_val)
        self.server.pi.start()

        # Confirm that the pbs.conf variable is set
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertEqual(pbs_conf_val["PBS_LOCALLOG"], "1")

        # Now, call self.revert_pbsconf()
        self.revert_pbsconf()

        # Confirm that the value gets removed from the list as it is not
        # a default setting
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertFalse("PBS_LOCALLOG" in pbs_conf_val)

    def test_revert_pbsconf_fewer_vars(self):
        """
        Test the functionality of PBSTestSuite.revert_pbsconf() when
        there are fewer pbs.conf variables than the default
        """
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertTrue(pbs_conf_val and len(pbs_conf_val) >= 1,
                        "Could not parse pbs.conf on host %s" %
                        (self.server.hostname))

        # Remove a default pbs.conf variable, say PBS_CORE_LIMIT,
        # and restart PBS
        self.server.pi.stop()
        del pbs_conf_val["PBS_CORE_LIMIT"]
        self.du.set_pbs_config(confs=pbs_conf_val, append=False)
        self.server.pi.start()

        # Confirm that the pbs.conf variable is gone
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertNotIn("PBS_CORE_LIMIT", pbs_conf_val)

        # Now, call self.revert_pbsconf()
        self.revert_pbsconf()

        # Confirm that the variable was set again
        pbs_conf_val = self.du.parse_pbs_config(self.server.hostname)
        self.assertIn("PBS_CORE_LIMIT", pbs_conf_val)

    def test_revert_moms_default_conf(self):
        """
        Test if PBSTestSuite.revert_moms() reverts the mom configuration
        setting to defaults
        """
        c1 = self.mom.parse_config()
        # Save a copy of default config to check it was reverted
        # correctly later
        c2 = c1.copy()
        a = {'$prologalarm': '280'}
        self.mom.add_config(a)
        c1.update(a)
        self.assertEqual(self.mom.parse_config(), c1)
        self.mom.revert_to_defaults()
        # Make sure the default config is back
        self.assertEqual(self.mom.parse_config(), c2)

    def test_revert_conf_highres_logging(self):
        """
        Test that if PBS_LOG_HIGHRES_TIMESTAMP by default is set to 1 and
        if its value is changed in the test it will be reverted to 1 by
        revert_pbsconf()
        """
        highres_val = self.du.parse_pbs_config()\
            .get("PBS_LOG_HIGHRES_TIMESTAMP")
        self.assertEqual("1", highres_val)

        a = {'PBS_LOG_HIGHRES_TIMESTAMP': "0"}
        self.du.set_pbs_config(confs=a, append=True)
        highres_val = self.du.parse_pbs_config()\
            .get("PBS_LOG_HIGHRES_TIMESTAMP")
        self.assertEqual("0", highres_val)

        self.revert_pbsconf()
        highres_val = self.du.parse_pbs_config()\
            .get("PBS_LOG_HIGHRES_TIMESTAMP")
        self.assertEqual("1", highres_val)

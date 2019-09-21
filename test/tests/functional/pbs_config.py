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

import tarfile
from tests.functional import *


class TestPBSConfig(TestFunctional):
    """
    Test cases for pbs_config tool
    """

    snapdirs = []
    snaptars = []

    def test_config_for_snapshot(self):
        """
        Test pbs_config's --snap option
        """
        pbs_snapshot_path = os.path.join(
            self.server.pbs_conf["PBS_EXEC"], "sbin", "pbs_snapshot")
        if not os.path.isfile(pbs_snapshot_path):
            self.skipTest("pbs_snapshot not found")
        pbs_config_path = os.path.join(
            self.server.pbs_conf["PBS_EXEC"], "unsupported", "pbs_config")
        if not os.path.isfile(pbs_config_path):
            self.skipTest("pbs_config not found")

        # Create 4 vnodes
        a = {ATTR_rescavail + ".ncpus": 2}
        self.server.create_vnodes(name='vnode', attrib=a, num=4, mom=self.mom,
                                  usenatvnode=True)
        self.server.expect(VNODE, {'state=free': 4}, count=True)

        # Create a queue
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id="expressq")

        # Set preempt_order to 'R'
        a = {"preempt_order": "R"}
        self.server.manager(MGR_CMD_SET, SCHED, a, id="default")

        # Set sched_config 'smp_cluster_dist' to 'round_robin'
        self.scheds["default"].set_sched_config(
            {"smp_cluster_dist": "round_robin"})

        # Now that we have a custom configuration, take a snapshot
        outdir = pwd.getpwnam(self.du.get_current_user()).pw_dir
        snap_cmd = [pbs_snapshot_path, "-o " + outdir, "--with-sudo"]
        ret = self.du.run_cmd(cmd=snap_cmd, logerr=False, as_script=True)
        self.assertEqual(ret["rc"], 0, "pbs_snapshot command failed")
        snap_out = ret['out'][0]
        output_tar = snap_out.split(":")[1]
        output_tar = output_tar.strip()

        # Check that the output tarball was created
        self.assertTrue(os.path.isfile(output_tar),
                        "Error capturing snapshot:\n" + str(ret))
        self.snaptars.append(output_tar)

        # Unwrap the tarball
        tar = tarfile.open(output_tar)
        tar.extractall(path=outdir)
        tar.close()

        # snapshot directory name = <snapshot>.tgz[:-4]
        snap_dir = output_tar[:-4]
        self.assertTrue(os.path.isdir(snap_dir))
        self.snapdirs.append(snap_dir)

        # Let's revert the system back to default now
        TestFunctional.setUp(self)

        # Now, use pbs_config --snap to build the system captured
        # previously in the snapshot
        config_cmd = [pbs_config_path, "--snap=" + snap_dir]
        self.du.run_cmd(cmd=config_cmd, sudo=True, logerr=False)

        # Verify that there are 4 vnodes, expressq, preempt_order=R and
        # smp_cluster_dist=round_robin
        self.server.expect(VNODE, {'state=free': 4}, count=True)
        self.server.expect(QUEUE, {"Priority": 200}, id="expressq")
        self.server.expect(SCHED, {"preempt_order": "R"}, id="default")
        self.scheds["default"].parse_sched_config()
        self.assertEqual(
            self.scheds["default"].sched_config["smp_cluster_dist"],
            "round_robin",
            "pbs_config didn't load sched_config correctly")

    def tearDown(self):
        # Cleanup snapshot dirs and tars
        for snap_dir in self.snapdirs:
            self.du.rm(path=snap_dir, recursive=True, force=True)
        for snap_tar in self.snaptars:
            self.du.rm(path=snap_tar, force=True)

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

import time

from tests.functional import *
from ptl.utils.pbs_snaputils import *


class TestPBSSnapshot(TestFunctional):
    """
    Test suit with unit tests for the pbs_snapshot tool
    """
    pbs_snapshot_path = None

    def setUp(self):
        TestFunctional.setUp(self)

        # Create a custom resource called 'ngpus'
        # This will help us test parts of PBSSnapUtils which handle resources
        attr = {"type": "long", "flag": "nh"}
        self.assertTrue(self.server.manager(MGR_CMD_CREATE, RSC, attr,
                                            id="ngpus", expect=True,
                                            sudo=True))

        # Check whether pbs_snapshot is accessible
        try:
            self.pbs_snapshot_path = os.path.join(
                self.server.pbs_conf["PBS_EXEC"], "sbin", "pbs_snapshot")
            ret = self.du.run_cmd(cmd=[self.pbs_snapshot_path, "-h"])
            if ret['rc'] != 0:
                self.pbs_snapshot_path = None
        except Exception:
            self.pbs_snapshot_path = None

        # Check whether the user has root access or not
        # pbs_snapshot only supports being run as root, so skip the entire
        # testsuite if the user doesn't have root privileges
        ret = self.du.run_cmd(
            cmd=["ls", os.path.join(os.sep, "root")], sudo=True)
        if ret['rc'] != 0:
            self.skipTest("pbs_snapshot/PBSSnapUtils need root privileges")

    def test_capture_server(self):
        """
        Test the 'capture_server' interface of PBSSnapUtils
        """

        # Set something on the server so we can match it later
        job_hist_duration = "12:00:00"
        attr_list = {"job_history_enable": "True",
                     "job_history_duration": job_hist_duration}
        self.server.manager(MGR_CMD_SET, SERVER, attr_list)

        target_dir = self.du.get_tempdir()
        num_daemon_logs = 2
        num_acct_logs = 5

        with PBSSnapUtils(out_dir=target_dir, acct_logs=num_acct_logs,
                          daemon_logs=num_daemon_logs) as snap_obj:
            snap_dir = snap_obj.capture_server(True, True)

            # Go through the snapshot and perform certain checks
            # Check 1: the snapshot exists
            self.assertTrue(os.path.isdir(snap_dir))
            # Check 2: all directories except the 'server' directory have no
            # files
            svr_fullpath = os.path.join(snap_dir, "server")
            for root, _, files in os.walk(snap_dir):
                for filename in files:
                    file_fullpath = os.path.join(root, filename)
                    # Find the common paths between 'server' & the file
                    common_path = os.path.commonprefix([file_fullpath,
                                                        svr_fullpath])
                    self.assertEquals(os.path.basename(common_path), "server")
            # Check 3: qstat_Bf.out exists
            qstat_bf_out = os.path.join(snap_obj.snapdir, QSTAT_BF_PATH)
            self.assertTrue(os.path.isfile(qstat_bf_out))
            # Check 4: qstat_Bf.out has 'job_history_duration' set to 24:00:00
            with open(qstat_bf_out, "r") as fd:
                for line in fd:
                    if "job_history_duration" in line:
                        # Remove whitespaces
                        line = "".join(line.split())
                        # Split it up by '='
                        key_val = line.split("=")
                        self.assertEquals(key_val[1], job_hist_duration)

        # Cleanup
        if os.path.isdir(snap_dir):
            self.du.rm(path=snap_dir, recursive=True, force=True)

    def test_capture_all(self):
        """
        Test the 'capture_all' interface of PBSSnapUtils

        WARNING: Assumes that the test is being run on type - 1 PBS install
        """
        target_dir = self.du.get_tempdir()
        num_daemon_logs = 2
        num_acct_logs = 5

        # Check that all PBS daemons are up and running
        all_daemons_up = self.server.isUp()
        all_daemons_up = all_daemons_up and self.mom.isUp()
        all_daemons_up = all_daemons_up and self.comm.isUp()
        all_daemons_up = all_daemons_up and self.scheduler.isUp()

        if not all_daemons_up:
            # Skip the test
            self.skipTest("Type 1 installation not present or " +
                          "all daemons are not running")

        with PBSSnapUtils(out_dir=target_dir, acct_logs=num_acct_logs,
                          daemon_logs=num_daemon_logs, sudo=True) as snap_obj:
            snap_dir = snap_obj.capture_all()
            snap_obj.finalize()

            # Test that all the expected information has been captured
            # PBSSnapUtils has various dictionaries which store metadata
            # for various objects. Create a list of these dicts
            all_info = [snap_obj.server_info, snap_obj.job_info,
                        snap_obj.node_info, snap_obj.comm_info,
                        snap_obj.hook_info, snap_obj.sched_info,
                        snap_obj.resv_info, snap_obj.datastore_info,
                        snap_obj.pbs_info, snap_obj.core_info,
                        snap_obj.sys_info]
            skip_list = [ACCT_LOGS, QMGR_LPBSHOOK_OUT, "reservation", "job",
                         QMGR_PR_OUT, PG_LOGS, "core_file_bt",
                         "pbs_snapshot.log"]
            platform = self.du.get_platform()
            if not platform.startswith("linux"):
                skip_list.extend([ETC_HOSTS, ETC_NSSWITCH_CONF, LSOF_PBS_OUT,
                                  VMSTAT_OUT, DF_H_OUT, DMESG_OUT])
            for item_info in all_info:
                for key, info in item_info.iteritems():
                    info_path = info[0]
                    if info_path is None:
                        continue
                    # Check if we should skip checking this info
                    skip_item = False
                    for item in skip_list:
                        if isinstance(item, int):
                            if item == key:
                                skip_item = True
                                break
                        else:
                            if item in info_path:
                                skip_item = True
                                break
                    if skip_item:
                        continue

                    # Check if this information was captured
                    info_full_path = os.path.join(snap_dir, info_path)
                    self.assertTrue(os.path.exists(info_full_path),
                                    msg=info_full_path + " was not captured")

        # Cleanup
        if os.path.isdir(snap_dir):
            self.du.rm(path=snap_dir, recursive=True, force=True)

    def test_capture_pbs_logs(self):
        """
        Test the 'capture_pbs_logs' interface of PBSSnapUtils
        """
        target_dir = self.du.get_tempdir()
        num_daemon_logs = 2
        num_acct_logs = 5

        # Check which PBS daemons are up on this machine.
        # We'll only check for logs from the daemons which were up
        # when the snapshot was taken.
        server_up = self.server.isUp()
        mom_up = self.mom.isUp()
        comm_up = self.comm.isUp()
        sched_up = self.scheduler.isUp()

        if not (server_up or mom_up or comm_up or sched_up):
            # Skip the test
            self.skipTest("No PBSPro daemons found on the system," +
                          " skipping the test")

        with PBSSnapUtils(out_dir=target_dir, acct_logs=num_acct_logs,
                          daemon_logs=num_daemon_logs) as snap_obj:
            snap_dir = snap_obj.capture_pbs_logs()

            # Perform some checks
            # Check that the snapshot exists
            self.assertTrue(os.path.isdir(snap_dir))
            if server_up:
                # Check that 'server_logs' were captured
                log_path = os.path.join(snap_dir, SVR_LOGS_PATH)
                self.assertTrue(os.path.isdir(log_path))
                # Check that 'accounting_logs' were captured
                log_path = os.path.join(snap_dir, ACCT_LOGS_PATH)
                self.assertTrue(os.path.isdir(log_path))
            if mom_up:
                # Check that 'mom_logs' were captured
                log_path = os.path.join(snap_dir, MOM_LOGS_PATH)
                self.assertTrue(os.path.isdir(log_path))
            if comm_up:
                # Check that 'comm_logs' were captured
                log_path = os.path.join(snap_dir, COMM_LOGS_PATH)
                self.assertTrue(os.path.isdir(log_path))
            if sched_up:
                # Check that 'sched_logs' were captured
                log_path = os.path.join(snap_dir, SCHED_LOGS_PATH)
                self.assertTrue(os.path.isdir(log_path))

        if os.path.isdir(snap_dir):
            self.du.rm(path=snap_dir, recursive=True, force=True)

    def test_snapshot_basic(self):
        """
        Test capturing a snapshot via the pbs_snapshot program
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        target_dir = self.du.get_tempdir()
        snap_cmd = [self.pbs_snapshot_path, "-o", target_dir]
        ret = self.du.run_cmd(cmd=snap_cmd, sudo=True)
        self.assertEquals(ret['rc'], 0)

        # Get the name of the tarball that was created
        # pbs_snapshot prints to stdout only the following:
        #     "Snapshot available at: <path to tarball>"
        self.assertTrue(len(ret['out']) > 0)
        snap_out = ret['out'][0]
        output_tar = snap_out.split(":")[1]
        output_tar = output_tar.strip()

        # Check that the output tarball was created
        self.assertTrue(os.path.isfile(output_tar))

        # Cleanup
        self.du.rm(path=output_tar, recursive=True, force=True)

    def test_snapshot_without_logs(self):
        """
        Test capturing a snapshot via the pbs_snapshot program
        Capture no logs
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        target_dir = self.du.get_tempdir()
        snap_cmd = [self.pbs_snapshot_path, "-o", target_dir,
                    "--daemon-logs=0", "--accounting-logs=0"]
        ret = self.du.run_cmd(cmd=snap_cmd, sudo=True)
        self.assertEquals(ret['rc'], 0)

        # Get the name of the tarball that was created
        # pbs_snapshot prints to stdout only the following:
        #     "Snapshot available at: <path to tarball>"
        self.assertTrue(len(ret['out']) > 0)
        snap_out = ret['out'][0]
        output_tar = snap_out.split(":")[1]
        output_tar = output_tar.strip()

        # Check that the output tarball was created
        self.assertTrue(os.path.isfile(output_tar))

        # Unwrap the tarball
        tar = tarfile.open(output_tar)
        tar.extractall(path=target_dir)
        tar.close()

        # snapshot directory name = <snapshot>.tgz[:-4]
        snap_dir = output_tar[:-4]

        # Check that the directory exists
        self.assertTrue(os.path.isdir(snap_dir))

        # Check that 'server_logs' were not captured
        log_path = os.path.join(snap_dir, SVR_LOGS_PATH)
        self.assertTrue(not os.path.isdir(log_path))
        # Check that 'mom_logs' were not captured
        log_path = os.path.join(snap_dir, MOM_LOGS_PATH)
        self.assertTrue(not os.path.isdir(log_path))
        # Check that 'comm_logs' were not captured
        log_path = os.path.join(snap_dir, COMM_LOGS_PATH)
        self.assertTrue(not os.path.isdir(log_path))
        # Check that 'sched_logs' were not captured
        log_path = os.path.join(snap_dir, SCHED_LOGS_PATH)
        self.assertTrue(not os.path.isdir(log_path))
        # Check that 'accounting_logs' were not captured
        log_path = os.path.join(snap_dir, ACCT_LOGS_PATH)
        self.assertTrue(not os.path.isdir(log_path))

        # Cleanup
        self.du.rm(path=snap_dir, recursive=True, force=True)
        self.du.rm(path=output_tar, sudo=True, force=True)

    def test_obfuscate_resv_user_groups(self):
        """
        Test obfuscation of user & group related attributes while capturing
        snapshots via pbs_snapshot
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        now = int(time.time())

        # Let's submit a reservation with Authorized_Users and
        # Authorized_Groups set
        attribs = {ATTR_auth_u: TEST_USER1, ATTR_auth_g: TSTGRP0,
                   ATTR_l + ".ncpus": 2, 'reserve_start': now + 25,
                   'reserve_end': now + 45}
        resv_obj = Reservation(attrs=attribs)
        resv_id = self.server.submit(resv_obj)
        attribs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attribs, id=resv_id)

        # Now, take a snapshot with --obfuscate
        target_dir = self.du.get_tempdir()
        snap_cmd = [self.pbs_snapshot_path, "-o", target_dir,
                    "--daemon-logs=0", "--accounting-logs=0", "--obfuscate"]
        ret = self.du.run_cmd(cmd=snap_cmd, sudo=True)
        self.assertEquals(ret['rc'], 0)

        # Get the name of the tarball that was created
        # pbs_snapshot prints to stdout only the following:
        #     "Snapshot available at: <path to tarball>"
        self.assertTrue(len(ret['out']) > 0)
        snap_out = ret['out'][0]
        output_tar = snap_out.split(":")[1]
        output_tar = output_tar.strip()

        # Check that the output tarball was created
        self.assertTrue(os.path.isfile(output_tar))

        # Unwrap the tarball
        tar = tarfile.open(output_tar)
        tar.extractall(path=target_dir)
        tar.close()

        # snapshot directory name = <snapshot>.tgz[:-4]
        snap_dir = output_tar[:-4]

        # Check that the directory exists
        self.assertTrue(os.path.isdir(snap_dir))

        # Make sure that the pbs_rstat -f output captured doesn't have the
        # Authorized user and group names
        pbsrstat_path = os.path.join(snap_dir, PBS_RSTAT_F_PATH)
        self.assertTrue(os.path.isfile(pbsrstat_path))
        with open(pbsrstat_path, "r") as rstatfd:
            all_content = rstatfd.read()
            self.assertFalse(str(TEST_USER1) in all_content)
            self.assertFalse(str(TSTGRP0) in all_content)

        # Cleanup
        self.du.rm(path=snap_dir, recursive=True, force=True)
        self.du.rm(path=output_tar, sudo=True, force=True)

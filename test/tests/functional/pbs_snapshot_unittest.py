# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of both the OpenPBS software ("OpenPBS")
# and the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# OpenPBS is free software. You can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# OpenPBS is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# PBS Pro is commercially licensed software that shares a common core with
# the OpenPBS software.  For a copy of the commercial license terms and
# conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
# Altair Legal Department.
#
# Altair's dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of OpenPBS and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair's trademarks, including but not limited to "PBS™",
# "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
# subject to Altair's trademark licensing policies.


import json
import os
import time

from ptl.utils.pbs_snaputils import *
from tests.functional import *


class TestPBSSnapshot(TestFunctional):
    """
    Test suit with unit tests for the pbs_snapshot tool
    """
    pbs_snapshot_path = None
    snapdirs = []
    snaptars = []
    parent_dir = os.getcwd()

    def setUp(self):
        TestFunctional.setUp(self)

        # Create a custom resource called 'ngpus'
        # This will help us test parts of PBSSnapUtils which handle resources
        attr = {"type": "long", "flag": "nh"}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id="ngpus", sudo=True)

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

    def setup_sc(self, sched_id, partition, port,
                 sched_priv=None, sched_log=None):
        """
        Setup a scheduler

        :param sched_id: id of the scheduler
        :type sched_id: str
        :param partition: partition name for the scheduler (e.g "P1", "P1,P2")
        :type partition: str
        :param port: The port number string for the scheduler
        :type port: str
        :param sched_priv: 'sched_priv' (full path) for the scheduler
        :type sched_priv: str
        :param sched_log: 'sched_log' (full path) for the scheduler
        :type sched_log: str
        """
        a = {'partition': partition,
             'sched_host': self.server.hostname}
        if sched_priv is not None:
            a['sched_priv'] = sched_priv
        if sched_log is not None:
            a['sched_log'] = sched_log
        self.server.manager(MGR_CMD_CREATE, SCHED, a, id=sched_id)
        if 'sched_priv' in a:
            sched_dir = os.path.dirname(sched_priv)
            self.scheds[sched_id].create_scheduler(sched_dir)
            self.scheds[sched_id].start(sched_dir)
        else:
            self.scheds[sched_id].create_scheduler()
            self.scheds[sched_id].start()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id=sched_id)

    def setup_queues_nodes(self, num_partitions):
        """
        Given a no. of partitions, create equal no. of associated queues
        and nodes

        :param num_partitions: number of partitions
        :type num_partitions: int
        :return a tuple of lists of queue and node ids:
            ([q1, q1, ..], [n1, n2, ..])
        """
        queues = []
        nodes = []
        a_q = {"queue_type": "execution",
               "started": "True",
               "enabled": "True"}
        a_n = {"resources_available.ncpus": 2}
        self.mom.create_vnodes(a_n, (num_partitions + 1), vname='vnode')
        for i in range(num_partitions):
            partition_id = "P" + str(i + 1)

            # Create queue i + 1 with partition i + 1
            id_q = "wq" + str(i + 1)
            queues.append(id_q)
            a_q["partition"] = partition_id
            self.server.manager(MGR_CMD_CREATE, QUEUE, a_q, id=id_q)

            # Set the partition i + 1 on node i
            id_n = "vnode[" + str(i) + "]"
            nodes.append(id_n)
            a = {"partition": partition_id}
            self.server.manager(MGR_CMD_SET, NODE, a, id=id_n)

        return (queues, nodes)

    def take_snapshot(self, acct_logs=None, daemon_logs=None,
                      obfuscate=None, with_sudo=True, hosts=None,
                      primary_host=None, basic=None):
        """
        Take a snapshot using pbs_snapshot command

        :param acct_logs: Number of accounting logs to capture
        :type acct_logs: int
        :param daemon_logs: Number of daemon logs to capture
        :type daemon_logs: int
        :param obfuscate: Obfuscate information?
        :type obfuscate: bool
        :param with_sudo: use the --with-sudo option?
        :type with_sudo: bool
        :param hosts: list of additional hosts to capture information from
        :type list
        :param primary_host: hostname of the primary host to capture (-H)
        :type primary_host: str
        :param basic: use --basic option
        :type bool
        :return a tuple of name of tarball and snapshot directory captured:
            (tarfile, snapdir)
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        snap_cmd = [self.pbs_snapshot_path, "-o", self.parent_dir]
        if acct_logs is not None:
            snap_cmd.append("--accounting-logs=" + str(acct_logs))

        if daemon_logs is not None:
            snap_cmd.append("--daemon-logs=" + str(daemon_logs))

        if obfuscate:
            snap_cmd.append("--obfuscate")

        if with_sudo:
            snap_cmd.append("--with-sudo")

        if hosts is not None:
            hosts_str = ",".join(hosts)
            snap_cmd.append("--additional-hosts=" + hosts_str)
        if primary_host is not None:
            snap_cmd.append("-H " + primary_host)
        if basic is not None:
            snap_cmd.append("--basic")

        ret = self.du.run_cmd(cmd=snap_cmd, logerr=False, as_script=True)
        self.assertEqual(ret['rc'], 0)

        # Get the name of the tarball that was created
        # pbs_snapshot prints to stdout only the following:
        #     "Snapshot available at: <path to tarball>"
        self.assertTrue(len(ret['out']) > 0)
        snap_out = ret['out'][0]
        output_tar = snap_out.split(":")[1]
        output_tar = output_tar.strip()

        # Check that the output tarball was created
        self.assertTrue(os.path.isfile(output_tar),
                        "Error capturing snapshot:\n" + str(ret))

        # Unwrap the tarball
        tar = tarfile.open(output_tar)
        tar.extractall(path=self.parent_dir)
        tar.close()

        # snapshot directory name = <snapshot>.tgz[:-4]
        snap_dir = output_tar[:-4]

        # Check that the directory exists
        self.assertTrue(os.path.isdir(snap_dir))

        self.snapdirs.append(snap_dir)
        self.snaptars.append(output_tar)

        return (output_tar, snap_dir)

    def test_capture_server(self):
        """
        Test the 'capture_server' interface of PBSSnapUtils
        """

        # Set something on the server so we can match it later
        job_hist_duration = "12:00:00"
        attr_list = {"job_history_enable": "True",
                     "job_history_duration": job_hist_duration}
        self.server.manager(MGR_CMD_SET, SERVER, attr_list)

        num_daemon_logs = 2
        num_acct_logs = 5

        with PBSSnapUtils(out_dir=self.parent_dir, acct_logs=num_acct_logs,
                          daemon_logs=num_daemon_logs,
                          with_sudo=True) as snap_obj:
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
                    try:
                        self.assertEqual(os.path.basename(common_path),
                                         "server")
                    except AssertionError:
                        # Check if this was a server core file, which would
                        # explain why it was captured
                        svrcorepath = os.path.join(CORE_DIR, "server_priv")
                        if svrcorepath in file_fullpath:
                            continue
                        raise
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
                        self.assertEqual(key_val[1], job_hist_duration)

        # Cleanup
        if os.path.isdir(snap_dir):
            self.du.rm(path=snap_dir, recursive=True, force=True)

    def test_capture_all(self):
        """
        Test the 'capture_all' interface of PBSSnapUtils

        WARNING: Assumes that the test is being run on type - 1 PBS install
        """
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

        with PBSSnapUtils(out_dir=self.parent_dir, acct_logs=num_acct_logs,
                          daemon_logs=num_daemon_logs,
                          with_sudo=True) as snap_obj:
            snap_dir = snap_obj.capture_all()
            snap_obj.finalize()

            # Test that all the expected information has been captured
            # PBSSnapUtils has various dictionaries which store metadata
            # for various objects. Create a list of these dicts
            all_info = [snap_obj.server_info, snap_obj.job_info,
                        snap_obj.node_info, snap_obj.comm_info,
                        snap_obj.hook_info, snap_obj.sched_info,
                        snap_obj.resv_info, snap_obj.core_info,
                        snap_obj.sys_info]
            skip_list = [ACCT_LOGS, QMGR_LPBSHOOK_OUT, "reservation", "job",
                         QMGR_PR_OUT, PG_LOGS, "core_file_bt",
                         "pbs_snapshot.log"]
            platform = self.du.get_platform()
            if not platform.startswith("linux"):
                skip_list.extend([ETC_HOSTS, ETC_NSSWITCH_CONF, LSOF_PBS_OUT,
                                  VMSTAT_OUT, DF_H_OUT, DMESG_OUT])
            for item_info in all_info:
                for key, info in item_info.items():
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
            self.skipTest("No PBS daemons found on the system," +
                          " skipping the test")

        with PBSSnapUtils(out_dir=self.parent_dir, acct_logs=num_acct_logs,
                          daemon_logs=num_daemon_logs,
                          with_sudo=True) as snap_obj:
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
                log_path = os.path.join(snap_dir, DFLT_SCHED_LOGS_PATH)
                self.assertTrue(os.path.isdir(log_path))

        if os.path.isdir(snap_dir):
            self.du.rm(path=snap_dir, recursive=True, force=True)

    def test_snapshot_basic(self):
        """
        Test capturing a snapshot via the pbs_snapshot program
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        output_tar, _ = self.take_snapshot()

        # Check that the output tarball was created
        self.assertTrue(os.path.isfile(output_tar))

    def test_snapshot_without_logs(self):
        """
        Test capturing a snapshot via the pbs_snapshot program
        Capture no logs
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        (_, snap_dir) = self.take_snapshot(0, 0)

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
        log_path = os.path.join(snap_dir, DFLT_SCHED_LOGS_PATH)
        self.assertTrue(not os.path.isdir(log_path))
        # Check that 'accounting_logs' were not captured
        log_path = os.path.join(snap_dir, ACCT_LOGS_PATH)
        self.assertTrue(not os.path.isdir(log_path))

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
                   ATTR_l + ".ncpus": 1, 'reserve_start': now + 25,
                   'reserve_end': now + 45}
        resv_obj = Reservation(attrs=attribs)
        resv_id = self.server.submit(resv_obj)
        attribs = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, attribs, id=resv_id)

        # Now, take a snapshot with --obfuscate
        (_, snap_dir) = self.take_snapshot(0, 0, True)

        # Make sure that the pbs_rstat -f output captured doesn't have the
        # Authorized user and group names
        pbsrstat_path = os.path.join(snap_dir, PBS_RSTAT_F_PATH)
        self.assertTrue(os.path.isfile(pbsrstat_path))
        with open(pbsrstat_path, "r") as rstatfd:
            all_content = rstatfd.read()
            self.assertFalse(str(TEST_USER1) in all_content)
            self.assertFalse(str(TSTGRP0) in all_content)

    def test_obfuscate_acct_bad(self):
        """
        Test that pbs_snapshot --obfuscate can work with bad accounting records
        """
        if os.getuid() != 0:
            self.skipTest("Test need to run as root")

        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        # Delete all existing accounting logs
        acct_logpath = os.path.join(self.server.pbs_conf["PBS_HOME"],
                                    "server_priv", "accounting")
        self.du.rm(path=os.path.join(acct_logpath, "*"), force=True,
                   as_script=True)
        ret = os.listdir(acct_logpath)
        self.assertEqual(len(ret), 0)
        self.server.pi.restart()

        # Make sure that the restart generated a new accounting log
        # Let's submit a job to generate a new accounting log
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid = self.server.submit(j)

        # Check that the accounting E record was generated
        self.server.accounting_match(";E;%s;" % jid)

        # Now, Add some garbage data to the accounting file
        ret = os.listdir(acct_logpath)
        self.assertGreater(len(ret), 0)
        acct_filename = ret[0]
        filepath = os.path.join(acct_logpath, acct_filename)
        with open(filepath, "a+") as fd:
            fd.write("!@#$%^")

        # Now, take a snapshot with --obfuscate
        (_, snap_dir) = self.take_snapshot(obfuscate=True, with_sudo=False)

        # Make sure that the accounting log was captured with the job record
        snapacctdir = os.path.join(snap_dir, "server_priv", "accounting")
        self.assertTrue(os.path.isdir(snapacctdir))
        snapacctpath = os.path.join(snapacctdir, acct_filename)
        self.assertTrue(os.path.isfile(snapacctpath))
        with open(snapacctpath, "r") as fd:
            content = fd.read()
            self.assertIn(";E;%s;" % jid, content)

        # Now, modify the job record itself to add some garbage to it
        file_contents = []
        contents_out = []
        with open(filepath, "r") as fd:
            file_contents = fd.readlines()
        for line in file_contents:
            if ";E;%s;" % jid in line:
                line = line[:-1] + " !@#$^\n"
            contents_out.append(line)
        with open(filepath, "w") as fd:
            fd.writelines(contents_out)

        # Capture another snapshot with --obfuscate
        (_, snap_dir) = self.take_snapshot(obfuscate=True, with_sudo=False)

        # Make sure that the accounting log was captured
        # This time, the job record should not be captured as it had garbage
        snapacctdir = os.path.join(snap_dir, "server_priv", "accounting")
        self.assertTrue(os.path.isdir(snapacctdir))
        snapacctpath = os.path.join(snapacctdir, acct_filename)
        self.assertTrue(os.path.isfile(snapacctpath))
        with open(snapacctpath, "r") as fd:
            content = fd.read()
            self.assertNotIn(";E;%s;" % jid, content)

    def test_multisched_support(self):
        """
        Test that pbs_snapshot can capture details of all schedulers
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        # Setup 3 schedulers
        sched_ids = ["sc1", "sc2", "sc3", "default"]
        self.setup_sc(sched_ids[0], "P1", "15050")
        self.setup_sc(sched_ids[1], "P2", "15051")
        # Setup scheduler at non-default location
        dir_path = os.path.join(os.sep, 'var', 'spool', 'pbs', 'sched_dir')
        if not os.path.exists(dir_path):
            self.du.mkdir(path=dir_path, sudo=True)
        sched_priv = os.path.join(dir_path, 'sched_priv_sc3')
        sched_log = os.path.join(dir_path, 'sched_logs_sc3')
        self.setup_sc(sched_ids[2], "P3", "15052", sched_priv, sched_log)

        # Add 3 partitions, each associated with a queue and a node
        (q_ids, _) = self.setup_queues_nodes(3)

        # Submit some jobs to fill the system up and get the multiple
        # schedulers busy
        for q_id in q_ids:
            for _ in range(2):
                attr = {"queue": q_id, "Resource_List.ncpus": "1"}
                j = Job(TEST_USER1, attrs=attr)
                self.server.submit(j)

        # Capture a snapshot of the system with multiple schedulers
        (_, snapdir) = self.take_snapshot()

        # Check that sched priv and sched logs for all schedulers was captured
        for sched_id in sched_ids:
            if (sched_id == "default"):
                schedi_priv = os.path.join(snapdir, DFLT_SCHED_PRIV_PATH)
                schedi_logs = os.path.join(snapdir, DFLT_SCHED_LOGS_PATH)
            else:
                schedi_priv = os.path.join(snapdir, "sched_priv_" + sched_id)
                schedi_logs = os.path.join(snapdir, "sched_logs_" + sched_id)

            self.assertTrue(os.path.isdir(schedi_priv))
            self.assertTrue(os.path.isdir(schedi_logs))

            # Make sure that these directories are not empty
            self.assertTrue(len(os.listdir(schedi_priv)) > 0)
            self.assertTrue(len(os.listdir(schedi_logs)) > 0)

        # Check that qmgr -c "l sched" captured information about all scheds
        lschedpath = os.path.join(snapdir, QMGR_LSCHED_PATH)
        with open(lschedpath, "r") as fd:
            scheds_found = 0
            for line in fd:
                if line.startswith("Sched "):
                    sched_id = line.split("Sched ")[1]
                    sched_id = sched_id.strip()
                    self.assertTrue(sched_id in sched_ids)
                    scheds_found += 1
            self.assertEqual(scheds_found, 4)

    def test_snapshot_from_hook(self):
        """
        Test that pbs_snapshot can be called from inside a hook
        """
        logmsg = "pbs_snapshot was successfully run"
        hook_body = """
import pbs
import os
import subprocess
import time

pbs_snap_exec = os.path.join(pbs.pbs_conf['PBS_EXEC'], "sbin", "pbs_snapshot")
if not os.path.isfile(pbs_snap_exec):
    raise ValueError("pbs_snapshot executable not found")

ref_time = time.time()
snap_cmd = [pbs_snap_exec, "-o", "."]
assert(not subprocess.call(snap_cmd))

# Check that the snapshot was captured
snapshot_found = False
for filename in os.listdir("."):
    if filename.startswith("snapshot") and filename.endswith(".tgz"):
        # Make sure the mtime on this file is recent enough
        mtime_file = os.path.getmtime(filename)
        if mtime_file > ref_time:
            snapshot_found = True
            break
assert(snapshot_found)
pbs.logmsg(pbs.EVENT_DEBUG,"%s")
""" % (logmsg)
        hook_name = "snapshothook"
        attr = {"event": "periodic", "freq": 5}
        rv = self.server.create_import_hook(hook_name, attr, hook_body,
                                            overwrite=True)
        self.assertTrue(rv)
        self.server.log_match(logmsg)

    def snapshot_multi_mom_basic(self, obfuscate=False):
        """
        Test capturing data from a multi-mom system

        :param obfuscate: take snapshot with --obfuscate?
        :type obfuscate: bool
        """
        # Skip test if number of moms is not equal to two
        if len(self.moms) != 2:
            self.skipTest("test requires atleast two moms as input, "
                          "use -p moms=<mom 1>:<mom 2>")

        mom1 = self.moms.values()[0]
        mom2 = self.moms.values()[1]

        host1 = mom1.shortname
        host2 = mom2.shortname

        self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.server.manager(MGR_CMD_CREATE, NODE, id=host1)
        self.server.manager(MGR_CMD_CREATE, NODE, id=host2)

        # Give the moms a chance to contact the server.
        self.server.expect(NODE, {'state': 'free'}, id=host1)
        self.server.expect(NODE, {'state': 'free'}, id=host2)

        # Capture a snapshot with details from the remote moms
        (_, snapdir) = self.take_snapshot(hosts=[host1, host2],
                                          obfuscate=obfuscate)

        # Check that snapshots for the 2 hosts were captured
        host1_outtar = os.path.join(snapdir, host1 + "_snapshot.tgz")
        host2_outtar = os.path.join(snapdir, host2 + "_snapshot.tgz")

        self.assertTrue(os.path.isfile(host1_outtar),
                        "Failed to capture snapshot on %s" % (host1))
        self.assertTrue(os.path.isfile(host2_outtar),
                        "Failed to capture snapshot on %s" % (host2))

        # Unwrap the host snapshots
        host1_snapdir = host1 + "_snapshot"
        host2_snapdir = host2 + "_snapshot"
        os.mkdir(host1_snapdir)
        self.snapdirs.append(host1_snapdir)
        os.mkdir(host2_snapdir)
        self.snapdirs.append(host2_snapdir)
        tar = tarfile.open(host1_outtar)
        tar.extractall(path=host1_snapdir)
        tar.close()
        tar = tarfile.open(host2_outtar)
        tar.extractall(path=host2_snapdir)
        tar.close()

        # Determine the name of the child snapshots
        snap1_path = self.du.listdir(path=host1_snapdir, fullpath=True)
        snap2_path = self.du.listdir(path=host2_snapdir, fullpath=True)
        snap1_path = snap1_path[0]
        snap2_path = snap2_path[0]

        # Check that at least pbs.conf was captured on all of these hosts
        self.assertTrue(os.path.isfile(os.path.join(snapdir, "pbs.conf")),
                        "Main snapshot didn't capture all expected"
                        " information")
        self.assertTrue(os.path.isfile(os.path.join(snap1_path, "pbs.conf")),
                        "%s snapshot didn't capture all expected"
                        " information" % (host1))
        self.assertTrue(os.path.isfile(os.path.join(snap2_path, "pbs.conf")),
                        "%s snapshot didn't capture all expected"
                        " information" % (host2))

    @requirements(num_moms=2)
    def test_multi_mom_basic(self):
        """
        Test running pbs_snapshot on a multi-mom setup
        """
        self.snapshot_multi_mom_basic()

    @requirements(num_moms=2)
    def test_multi_mom_basic_obfuscate(self):
        """
        Test running pbs_snapshot on a multi-mom setup with obfuscation
        """
        self.snapshot_multi_mom_basic(obfuscate=True)

    def test_no_sudo(self):
        """
        Test that running pbs_snapshot without sudo doesn't fail
        """
        output_tar, _ = self.take_snapshot(with_sudo=False)

        # Check that the output tarball was created
        self.assertTrue(os.path.isfile(output_tar))

    def test_snapshot_json(self):
        """
        Test that pbs_snapshot captures job and vnode info in json
        """
        _, snap_dir = self.take_snapshot()

        # Verify that qstat json was captured
        jsonpath = os.path.join(snap_dir, QSTAT_F_JSON_PATH)
        self.assertTrue(os.path.isfile(jsonpath))
        with open(jsonpath, "r") as fd:
            json.load(fd)   # this will fail if file is not a valid json

        # Verify that pbsnodes json was captured
        jsonpath = os.path.join(snap_dir, PBSNODES_AVFJSON_PATH)
        self.assertTrue(os.path.isfile(jsonpath))
        with open(jsonpath, "r") as fd:
            json.load(fd)

    @requirements(no_mom_on_server=True)
    def test_remote_primary_mom(self):
        """
        Test that pbs_snapshot -H works correctly to capture a remote primary
        MoM host
        """
        # Skip test if there's no remote mom host available
        if len(self.moms) == 0 or \
                self.du.is_localhost((self.moms.values()[0]).shortname):
            self.skipTest("test requires a remote mom host as input, "
                          "use -p moms=<mom host>")

        mom_host = (self.moms.values()[0]).shortname

        _, snap_dir = self.take_snapshot(primary_host=mom_host)

        # Verify that mom_priv was captured
        momprivpath = os.path.join(snap_dir, "mom_priv")
        self.assertTrue(os.path.isdir(momprivpath))

    @requirements(num_moms=2)
    def test_remote_primary_multinode(self):
        """
        Test that pbs_snapshot -H works with --additional-hosts to capture
        """
        # Skip test if number of moms is not equal to two
        if len(self.moms) != 2:
            self.skipTest("test requires atleast two moms as input, "
                          "use -p moms=<mom 1>:<mom 2>")

        mom1 = self.moms.values()[0]
        mom2 = self.moms.values()[1]

        host1 = mom1.shortname
        host2 = mom2.shortname

        _, snap_dir = self.take_snapshot(hosts=[host2], primary_host=host1)

        # Verify that the primary host's mom_priv was captured
        momprivpath = os.path.join(snap_dir, "mom_priv")
        self.assertTrue(os.path.isdir(momprivpath))

        # The other host was captured as an additional host,
        # so there should be a snapshot tar for it inside the main snapshot
        host2_outtar = os.path.join(snap_dir, host2 + "_snapshot.tgz")
        self.assertTrue(os.path.isfile(host2_outtar))

        # Verify that mom_priv was captured, we can do this by just checking
        # for mom_priv/config file
        tar = tarfile.open(host2_outtar)
        host2_snapname = tar.getnames()[0].split(os.sep, 1)[0]
        try:
            config_path = os.path.join(host2_snapname, "mom_priv", "config")
            tar.getmember(config_path)
        except KeyError:
            self.fail("mom_priv/config not found in %s's snapshot" % host2)

    @skipOnShasta
    def test_snapshot_obf_stress(self):
        """
        A stress test to make sure that snapshot --obufscate really obfuscates
        the attributes that it claims to
        """
        real_values = {}

        # We will try to set all attributes which --obfuscate anonymizes
        manager1 = str(MGR_USER) + '@*'
        manager2 = str(TEST_USER) + "@*"
        self.server.manager(MGR_CMD_SET, SERVER,
                            {ATTR_managers: (INCR, manager2)},
                            sudo=True)
        real_values[ATTR_managers] = [manager1, manager2]

        operator = str(OPER_USER) + '@*'
        real_values[ATTR_operators] = [operator]

        real_values[ATTR_SvrHost] = [self.server.hostname]

        # Create a queue with acls set
        a = {ATTR_qtype: 'execution', ATTR_start: 'True', ATTR_enable: 'True',
             ATTR_aclgren: 'True', ATTR_aclgroup: TSTGRP0,
             ATTR_acluser: TEST_USER}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')
        real_values[ATTR_aclgroup] = [TSTGRP0]
        real_values[ATTR_acluser] = [TEST_USER]

        # Create a custom resource
        attr = {"type": "long", "flag": "nh"}
        rsc_id = "myres"
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id=rsc_id,
                            logerr=False)

        # Make it schedulable
        self.scheduler.add_resource("myres")

        # Set myres on the vnode
        attr = {"resources_available.myres": 1}
        self.server.manager(MGR_CMD_SET, NODE, attr, id=self.mom.shortname)

        # Set acls on server
        self.server.manager(MGR_CMD_SET, SERVER,
                            {ATTR_aclResvgroup: TSTGRP0,
                             ATTR_aclResvuser: TEST_USER,
                             ATTR_aclResvhost: self.server.hostname,
                             ATTR_aclhost: self.server.hostname},
                            sudo=True)
        real_values[ATTR_aclResvgroup] = [TSTGRP0]
        real_values[ATTR_aclResvuser] = [TEST_USER]

        # ATTR_SchedHost  is already set on the default host
        real_values[ATTR_SchedHost] = [self.server.hostname]

        # Add node's 'Host' & 'Mom'
        real_values[ATTR_NODE_Host] = [self.mom.shortname, self.mom.hostname]
        real_values[ATTR_NODE_Mom] = [self.mom.shortname, self.mom.hostname]
        real_values[ATTR_rescavail + ".host"] = [self.mom.shortname,
                                                 self.mom.hostname]
        real_values[ATTR_rescavail + ".vnode"] = [self.mom.shortname]

        # Submit a reservation with Authorized_Users & Authorized_Groups set
        a = {ATTR_auth_u: TEST_USER, ATTR_auth_g: TSTGRP0}
        Reservation(TEST_USER, a)
        real_values[ATTR_auth_u] = [TEST_USER]
        real_values[ATTR_auth_g] = [TSTGRP0]
        real_values[ATTR_resv_owner] = [TEST_USER, self.server.hostname]

        # Set up fairshare so that resource_group file gets filled
        self.scheduler.add_to_resource_group(TEST_USER, 11, 'root', 40)
        self.scheduler.add_to_resource_group(TEST_USER1, 11, 'root', 60)

        # Submit a job with sensitive attributes set
        a = {ATTR_project: 'p1', ATTR_A: 'a1', ATTR_g: TSTGRP0,
             ATTR_M: TEST_USER, ATTR_u: TEST_USER,
             ATTR_l + ".walltime": "00:01:00",
             ATTR_l + ".myres": 1, ATTR_S: "/bin/bash"}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(1000)
        self.server.submit(j)

        # Add job's attributes to the list
        # TEST_USER belongs to group TESTGRP0
        real_values[ATTR_euser] = [TEST_USER]
        real_values[ATTR_egroup] = [TSTGRP0]
        real_values[ATTR_project] = ['p1']
        real_values[ATTR_A] = ['a1']
        real_values[ATTR_g] = [TSTGRP0]
        real_values[ATTR_M] = [TEST_USER]
        real_values[ATTR_u] = [TEST_USER]
        real_values[ATTR_owner] = [TEST_USER, self.server.hostname]
        real_values[ATTR_exechost] = [self.server.hostname]
        real_values[ATTR_S] = ["/bin/bash"]
        real_values[ATTR_l] = ["myres"]

        # Take a snapshot with --obfuscate
        (_, snap_dir) = self.take_snapshot(obfuscate=True)

        # Make sure that none of the sensitive values were captured
        values = real_values.values()
        for val_list in values:
            for val in val_list:
                # Just do a grep for the value in the snapshot
                cmd = ["grep", "-wR", "\'" + str(val) + "\'", snap_dir]
                ret = self.du.run_cmd(cmd=cmd, level=logging.DEBUG)
                # grep returns 2 if an error occurred
                self.assertNotEqual(ret["rc"], 2, "grep failed!")
                self.assertIn(ret["out"], ["", None, []], str(val) +
                              " was not obfuscated. Real values:\n" +
                              str(real_values))
                # Also make sure that no filenames contain the sensitive val
                cmd = ["find", snap_dir, "-name", "\'*" + str(val) + "*\'"]
                ret = self.du.run_cmd(cmd=cmd, level=logging.DEBUG)
                self.assertEqual(ret["rc"], 0, "find command failed!")
                self.assertIn(ret["out"], ["", None, []], str(val) +
                              " was not obfuscated. Real values:\n" +
                              str(real_values))

    def test_basic_option(self):
        """
        Test pbs_snapshot --basic
        """
        if self.pbs_snapshot_path is None:
            self.skip_test("pbs_snapshot not found")

        _, snap_dir = self.take_snapshot(basic=True)

        # Check that the output tarball was created
        self.assertTrue(os.path.isdir(snap_dir))

        # Check that only the following was captured:
        target_files = ["server/qstat_Bf.out", "server/qstat_Qf.out",
                        "scheduler/qmgr_lsched.out", "node/pbsnodes_va.out",
                        "reservation/pbs_rstat_f.out", "job/qstat_f.out",
                        "hook/qmgr_lpbshook.out", "server_priv/resourcedef",
                        "pbs.conf", "pbs_snapshot.log", "ctime"]
        target_files = [os.path.join(snap_dir, f) for f in target_files]
        sched_priv_dir = os.path.join(snap_dir, "sched_priv")
        for (root, dirs, files) in os.walk(snap_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                if fpath not in target_files:
                    if not fpath.startswith(sched_priv_dir):
                        self.fail("Unexpected file " + fpath + " captured")

    def test_snapshot_mom_obf(self):
        """
        Test capturing a snapshot of a system that's only running pbs_mom
        """
        # Kill all daemons and start only pbs_mom
        self.server.pi.initd(op="stop", daemon="all")
        self.mom.pi.start_mom()
        self.assertTrue(self.mom.isUp())
        self.assertFalse(self.server.isUp())

        # Take & verify a snapshot with obfuscate
        self.take_snapshot(obfuscate=True, with_sudo=True, acct_logs=10)

        # Bring the rest of daemons up otherwise tearDown will error out
        self.server.pi.initd(op="start", daemon="all")

    def tearDown(self):
        # Delete the snapshot directories and tarballs created
        for snap_dir in self.snapdirs:
            self.du.rm(path=snap_dir, recursive=True, force=True)
        for snap_tar in self.snaptars:
            self.du.rm(path=snap_tar, sudo=True, force=True)

        TestFunctional.tearDown(self)

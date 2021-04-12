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


import collections
import logging
import os
import pprint
import random
import re
import shlex
import shutil
import socket
import tarfile
import time
import platform
from subprocess import STDOUT
from pathlib import Path

from ptl.lib.pbs_ifl_mock import *
from ptl.lib.pbs_testlib import (SCHED, BatchUtils, Scheduler, Server,
                                 PbsAttribute)
from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_logutils import PBSLogUtils

# Define an enum which is used to label various pieces of information
(   # qstat outputs
    QSTAT_B_OUT,
    QSTAT_BF_OUT,
    QSTAT_OUT,
    QSTAT_F_OUT,
    QSTAT_T_OUT,
    QSTAT_TF_OUT,
    QSTAT_X_OUT,
    QSTAT_XF_OUT,
    QSTAT_NS_OUT,
    QSTAT_FX_DSV_OUT,
    QSTAT_F_DSV_OUT,
    QSTAT_F_JSON_OUT,
    QSTAT_Q_OUT,
    QSTAT_QF_OUT,
    # qmgr outputs
    QMGR_PS_OUT,
    QMGR_PH_OUT,
    QMGR_LPBSHOOK_OUT,
    QMGR_LSCHED_OUT,
    QMGR_PN_OUT,
    QMGR_PR_OUT,
    QMGR_PQ_OUT,
    QMGR_PSCHED_OUT,
    # pbsnodes outputs
    PBSNODES_VA_OUT,
    PBSNODES_A_OUT,
    PBSNODES_AVSJ_OUT,
    PBSNODES_ASJ_OUT,
    PBSNODES_AVS_OUT,
    PBSNODES_AS_OUT,
    PBSNODES_AFDSV_OUT,
    PBSNODES_AVFDSV_OUT,
    PBSNODES_AVFJSON_OUT,
    # pbs_rstat outputs
    PBS_RSTAT_OUT,
    PBS_RSTAT_F_OUT,
    # PBS config related outputs
    PBS_CONF,
    PBS_PROBE_OUT,
    PBS_HOSTN_OUT,
    PBS_ENVIRONMENT,
    # System related outputs
    OS_INFO,
    PROCESS_INFO,
    LSOF_PBS_OUT,
    ETC_HOSTS,
    ETC_NSSWITCH_CONF,
    VMSTAT_OUT,
    DF_H_OUT,
    DMESG_OUT,
    PS_LEAF_OUT,
    # Logs
    ACCT_LOGS,
    SVR_LOGS,
    SCHED_LOGS,
    MOM_LOGS,
    PG_LOGS,
    COMM_LOGS,
    # Daemon priv directories
    SVR_PRIV,
    MOM_PRIV,
    SCHED_PRIV,
    # Core file information
    CORE_SCHED,
    CORE_SERVER,
    CORE_MOM,
    # Miscellaneous
    CTIME) = list(range(59))


# Define paths to various files/directories with respect to the snapshot
# server/
SERVER_DIR = "server"
QSTAT_B_PATH = os.path.join(SERVER_DIR, "qstat_B.out")
QSTAT_BF_PATH = os.path.join(SERVER_DIR, "qstat_Bf.out")
QMGR_PS_PATH = os.path.join(SERVER_DIR, "qmgr_ps.out")
QSTAT_Q_PATH = os.path.join(SERVER_DIR, "qstat_Q.out")
QSTAT_QF_PATH = os.path.join(SERVER_DIR, "qstat_Qf.out")
QMGR_PR_PATH = os.path.join(SERVER_DIR, "qmgr_pr.out")
QMGR_PQ_PATH = os.path.join(SERVER_DIR, "qmgr_pq.out")
# server_priv/
SVR_PRIV_PATH = "server_priv"
ACCT_LOGS_PATH = os.path.join("server_priv", "accounting")
RSCDEF_PATH = os.path.join("server_priv", "resourcedef")
# server_logs/
SVR_LOGS_PATH = "server_logs"
# job/
JOB_DIR = "job"
QSTAT_PATH = os.path.join(JOB_DIR, "qstat.out")
QSTAT_F_PATH = os.path.join(JOB_DIR, "qstat_f.out")
QSTAT_T_PATH = os.path.join(JOB_DIR, "qstat_t.out")
QSTAT_TF_PATH = os.path.join(JOB_DIR, "qstat_tf.out")
QSTAT_X_PATH = os.path.join(JOB_DIR, "qstat_x.out")
QSTAT_XF_PATH = os.path.join(JOB_DIR, "qstat_xf.out")
QSTAT_NS_PATH = os.path.join(JOB_DIR, "qstat_ns.out")
QSTAT_FX_DSV_PATH = os.path.join(JOB_DIR, "qstat_fx_F_dsv.out")
QSTAT_F_DSV_PATH = os.path.join(JOB_DIR, "qstat_f_F_dsv.out")
QSTAT_F_JSON_PATH = os.path.join(JOB_DIR, "qstat_f_F_json.out")
# node/
NODE_DIR = "node"
PBSNODES_VA_PATH = os.path.join(NODE_DIR, "pbsnodes_va.out")
PBSNODES_A_PATH = os.path.join(NODE_DIR, "pbsnodes_a.out")
PBSNODES_AVSJ_PATH = os.path.join(NODE_DIR, "pbsnodes_avSj.out")
PBSNODES_ASJ_PATH = os.path.join(NODE_DIR, "pbsnodes_aSj.out")
PBSNODES_AVS_PATH = os.path.join(NODE_DIR, "pbsnodes_avS.out")
PBSNODES_AS_PATH = os.path.join(NODE_DIR, "pbsnodes_aS.out")
PBSNODES_AFDSV_PATH = os.path.join(NODE_DIR, "pbsnodes_aFdsv.out")
PBSNODES_AVFDSV_PATH = os.path.join(NODE_DIR, "pbsnodes_avFdsv.out")
PBSNODES_AVFJSON_PATH = os.path.join(NODE_DIR, "pbsnodes_avFjson.out")
QMGR_PN_PATH = os.path.join(NODE_DIR, "qmgr_pn_default.out")
# mom_priv/
MOM_PRIV_PATH = "mom_priv"
# mom_logs/
MOM_LOGS_PATH = "mom_logs"
# comm_logs/
COMM_LOGS_PATH = "comm_logs"
# hook/
HOOK_DIR = "hook"
QMGR_PH_PATH = os.path.join(HOOK_DIR, "qmgr_ph_default.out")
QMGR_LPBSHOOK_PATH = os.path.join(HOOK_DIR, "qmgr_lpbshook.out")
# scheduler/
SCHED_DIR = "scheduler"
QMGR_LSCHED_PATH = os.path.join(SCHED_DIR, "qmgr_lsched.out")
QMGR_PSCHED_PATH = os.path.join(SCHED_DIR, "qmgr_psched.out")
# sched_priv/
DFLT_SCHED_PRIV_PATH = "sched_priv"
# sched_logs/
DFLT_SCHED_LOGS_PATH = "sched_logs"
# reservation/
RESV_DIR = "reservation"
PBS_RSTAT_PATH = os.path.join(RESV_DIR, "pbs_rstat.out")
PBS_RSTAT_F_PATH = os.path.join(RESV_DIR, "pbs_rstat_f.out")
# datastore/
DATASTORE_DIR = "datastore"
PG_LOGS_PATH = os.path.join(DATASTORE_DIR, "pg_log")
# core_file_bt/
CORE_DIR = "core_file_bt"
CORE_SERVER_PATH = os.path.join(CORE_DIR, "server_priv")
CORE_SCHED_PATH = os.path.join(CORE_DIR, "sched_priv")
CORE_MOM_PATH = os.path.join(CORE_DIR, "mom_priv")
# system/
SYS_DIR = "system"
PBS_PROBE_PATH = os.path.join(SYS_DIR, "pbs_probe_v.out")
PBS_HOSTN_PATH = os.path.join(SYS_DIR, "pbs_hostn_v.out")
PBS_ENV_PATH = os.path.join(SYS_DIR, "pbs_environment")
OS_PATH = os.path.join(SYS_DIR, "os_info")
PROCESS_PATH = os.path.join(SYS_DIR, "process_info")
ETC_HOSTS_PATH = os.path.join(SYS_DIR, "etc_hosts")
ETC_NSSWITCH_PATH = os.path.join(SYS_DIR, "etc_nsswitch_conf")
LSOF_PBS_PATH = os.path.join(SYS_DIR, "lsof_pbs.out")
VMSTAT_PATH = os.path.join(SYS_DIR, "vmstat.out")
DF_H_PATH = os.path.join(SYS_DIR, "df_h.out")
DMESG_PATH = os.path.join(SYS_DIR, "dmesg.out")
PS_LEAF_PATH = os.path.join(SYS_DIR, "ps_leaf.out")
# top-level
PBS_CONF_PATH = "pbs.conf"
CTIME_PATH = "ctime"

# Define paths to PBS commands used to capture data with respect to PBS_EXEC
QSTAT_CMD = os.path.join("bin", "qstat")
PBSNODES_CMD = os.path.join("bin", "pbsnodes")
QMGR_CMD = os.path.join("bin", "qmgr")
PBS_RSTAT_CMD = os.path.join("bin", "pbs_rstat")
PBS_PROBE_CMD = os.path.join("sbin", "pbs_probe")
PBS_HOSTN_CMD = os.path.join("bin", "pbs_hostn")


class ObfuscateSnapshot(object):
    val_obf_map = {}
    vals_to_del = []
    bu = BatchUtils()
    du = DshUtils()
    num_bad_acct_records = 0
    logger = logging.getLogger(__name__)

    job_attrs_del = [ATTR_v, ATTR_e, ATTR_jobdir,
                     ATTR_submit_arguments, ATTR_o, ATTR_S]
    resv_attrs_del = [ATTR_v]
    svr_attrs_del = [ATTR_mailfrom]
    job_attrs_obf = [ATTR_euser, ATTR_egroup, ATTR_project, ATTR_A,
                     ATTR_g, ATTR_M, ATTR_u, ATTR_owner, ATTR_name]
    resv_attrs_obf = [ATTR_A, ATTR_g, ATTR_M, ATTR_auth_u, ATTR_auth_g,
                      ATTR_auth_h, ATTR_resv_owner]
    svr_attrs_obf = [ATTR_SvrHost, ATTR_acluser, ATTR_aclResvuser,
                     ATTR_aclResvhost, ATTR_aclhost, ATTR_operators,
                     ATTR_managers]
    node_attrs_obf = [ATTR_NODE_Host, ATTR_NODE_Mom, ATTR_rescavail + ".host",
                      ATTR_rescavail + ".vnode"]
    sched_attrs_obf = [ATTR_SchedHost]
    queue_attrs_obf = [ATTR_acluser, ATTR_aclgroup, ATTR_aclhost]
    skip_vals = ["_pbs_project_default", "*", "pbsadmin", "pbsuser"]

    def _obfuscate_stat(self, file_path, attrs_to_obf, attrs_to_del):
        """
        Helper function to obfuscate qstat/rstat -f & pbsnodes -av outputs

        :param file_path - path to the qstat output file in snapshot
        :type file_path - str
        :param attrs_to_obf - attribute list to obfuscate
        :type list
        :param attrs_to_del- attribute list to delete
        :type list
        """
        fout = self.du.create_temp_file()

        with open(file_path, "r") as fdin, open(fout, "w") as fdout:
            delete_line = False
            val_obf = None
            val_del = None
            key_obf = None
            for line in fdin:
                # Check if this is a line extension for an attr being deleted
                if line[0] == "\t":
                    if delete_line:
                        val_del += line.strip()
                        continue
                    elif val_obf is not None:
                        val_obf += line.strip()
                        continue

                delete_line = False
                if val_del is not None:
                    self.vals_to_del.append(val_del)
                    val_del = None

                if val_obf is not None:
                    # Write the previous, obfuscated attribute first
                    val_to_write = []
                    for val in val_obf.split(","):
                        val = val.strip()
                        val = val.split("@")
                        out_val = []
                        for _val in val:
                            if _val in self.skip_vals:
                                obf = _val
                            elif _val not in self.val_obf_map:
                                obf = PbsAttribute.random_str(
                                    length=random.randint(8, 30))
                                self.val_obf_map[_val] = obf
                            else:
                                obf = self.val_obf_map[_val]
                            out_val.append(obf)
                        out_val = "@".join(out_val)
                        val_to_write.append(out_val)

                    # Some PBS outputs have inconsistent whitespaces
                    # e.g - pbs_rstat -f doesn't print leading spaces
                    # So, extract the lead from the original line
                    lead = ""
                    for c in line:
                        if not c.isspace():
                            break
                        lead += c

                    obf_line = lead + key_obf + " = " + \
                        ",".join(val_to_write) + "\n"
                    fdout.write(obf_line)
                    val_obf = None
                    key_obf = None

                if "=" in line:
                    attrname, attrval = line.split("=", 1)
                    attrname = attrname.strip()
                    attrval = attrval.strip()

                    # Check if this attribute needs to be deleted
                    if attrname in attrs_to_del:
                        delete_line = True
                        val_del = attrval

                    if delete_line is True:
                        continue

                    # Check if this attribute needs to be obfuscated
                    if attrname in attrs_to_obf:
                        val_obf = attrval
                        key_obf = attrname

                if val_obf is None:
                    fdout.write(line)

        shutil.move(fout, file_path)

    def _obfuscate_acct_file(self, attrs_obf, file_path):
        """
        Helper function to anonymize

        :param attrs_obf - list of attributes to obfuscate
        :type attrs_obf - list
        :param file_path - path of acct log file
        :type file_path - str
        """
        fout = self.du.create_temp_file()

        with open(file_path, "r") as fd, open(fout, "w") as fdout:
            for record in fd:
                # accounting log format is
                # %Y/%m/%d %H:%M:%S;<Key>;<Id>;<key1=val1> <key2=val2> ...
                record_list = record.split(";", 3)
                if record_list is None or len(record_list) < 4:
                    continue
                if record_list[1] in ("A", "L"):
                    fdout.write(record)
                    continue
                content_list = shlex.split(record_list[3].strip())

                skip_record = False
                kvl_list = [kv.split("=", 1) for kv in content_list]
                if kvl_list is None:
                    self.num_bad_acct_records += 1
                    self.logger.debug("Bad accounting record found:\n" +
                                      record)
                    continue
                for kvl in kvl_list:
                    try:
                        k, v = kvl
                    except ValueError:
                        self.num_bad_acct_records += 1
                        self.logger.debug("Bad accounting record found:\n" +
                                          record)
                        skip_record = True
                        break

                    if k in attrs_obf:
                        val = v.split("@")
                        obf = []
                        for _val in val:
                            if _val == "_pbs_project_default":
                                obf.append(_val)
                            elif _val not in self.val_obf_map:
                                obf_v = PbsAttribute.random_str(
                                    length=random.randint(8, 30))
                                self.val_obf_map[_val] = obf_v
                                obf.append(obf_v)
                            else:
                                obf.append(self.val_obf_map[_val])
                        kvl[1] = "@".join(obf)

                if not skip_record:
                    record = ";".join(record_list[:3]) + ";" + \
                        " ".join(["=".join(n) for n in kvl_list])
                    fdout.write(record + "\n")

        shutil.move(fout, file_path)

    def obfuscate_acct_logs(self, snap_dir, sudo_val):
        """
        Helper function to obfuscate accounting logs

        :param snap_dir - the snapshot directory path
        :type snap_dir - str
        """
        attrs_to_obf = self.job_attrs_obf + self.resv_attrs_obf +\
            self.svr_attrs_obf + self.queue_attrs_obf + self.node_attrs_obf +\
            self.sched_attrs_obf

        # Some accounting record attributes are named differently
        acct_extras = ["user", "requestor", "group", "account"]
        attrs_to_obf += acct_extras

        acct_path = os.path.join(snap_dir, "server_priv", "accounting")
        if not os.path.isdir(acct_path):
            return
        acct_fpaths = self.du.listdir(path=acct_path, sudo=sudo_val)
        for acct_fpath in acct_fpaths:
            self._obfuscate_acct_file(attrs_to_obf, acct_fpath)
        if self.num_bad_acct_records > 0:
            self.logger.info("Total bad records found: " +
                             str(self.num_bad_acct_records))

    def _obfuscate_with_map(self, fpath, sudo=False):
        """
        Helper function to obfuscate a file with obfuscation map

        :param filepath - path to the file
        :type filepath - str
        :param sudo - sudo True/False?
        :type bool

        :return fpath - possibly updated path to the obfuscated file
        """
        fout = self.du.create_temp_file()
        pathobj = Path(fpath)
        fname = pathobj.name
        fparent = pathobj.parent
        with open(fpath, "r", encoding="latin-1") as fd, \
                open(fout, "w") as fdout:
            alltext = fd.read()
            # Obfuscate values from val_obf_map
            for key, val in self.val_obf_map.items():
                alltext = re.sub(r'\b' + key + r'\b', val, alltext)
                if key in fname:
                    fname = fname.replace(key, val)
                    fpath = os.path.join(fparent, fname)
            # Remove the attr values from vals_to_del list
            for val in self.vals_to_del:
                alltext = alltext.replace(val, "")
            fdout.write(alltext)

        self.du.rm(path=fpath, sudo=sudo)
        shutil.move(fout, fpath)

        return fpath

    def obfuscate_snapshot(self, snap_dir, map_file, sudo_val):
        """
        Helper function to obfuscate a snapshot

        :param snap_dir - path to snapshot directory to obfsucate
        :type snap_dir - str
        :param map_file - path to the map file to create
        :type map_file - str
        :param sudo_val - value of the --with-sudo option (needed for printjob)
        :type sudo_val bool
        """
        if not os.path.isdir(snap_dir):
            raise ValueError("Snapshot directory path not accessible"
                             " for obfuscation")

        # Let's go through the qmgr, qstat, pbsnodes and resourcedef file
        # Get the values associated with attributes to obfuscate and
        # obfuscate them everywhere in the snapshot
        # Delete the attribute-value pair in the delete lists
        stat_f_files = {
            QSTAT_BF_PATH: [self.svr_attrs_obf, self.svr_attrs_del],
            QSTAT_F_PATH: [self.job_attrs_obf, self.job_attrs_del],
            QSTAT_TF_PATH: [self.job_attrs_obf, self.job_attrs_del],
            QSTAT_XF_PATH: [self.job_attrs_obf, self.job_attrs_del],
            QSTAT_QF_PATH: [self.queue_attrs_obf, []],
            PBSNODES_VA_PATH: [self.node_attrs_obf, []],
            PBS_RSTAT_F_PATH: [self.resv_attrs_obf, self.resv_attrs_del]
        }
        for s_f_file, attrs in stat_f_files.items():
            qstat_f_path = os.path.join(snap_dir, s_f_file)
            if os.path.isfile(qstat_f_path):
                self._obfuscate_stat(qstat_f_path, attrs[0], attrs[1])

        # Parse resourcedef file and add custom resources to obfuscation map
        # We will later do a sed on the whole snapshot, that's when these
        # will get obfuscated
        custom_rscs = []
        custrscs_path = os.path.join(snap_dir, RSCDEF_PATH)
        if os.path.isfile(custrscs_path):
            with open(custrscs_path, "r") as fd:
                for line in fd:
                    rscs_name = line.split(" ", 1)[0]
                    custom_rscs.append(rscs_name.strip())
        for rscs in custom_rscs:
            if rscs not in self.val_obf_map:
                obf = PbsAttribute.random_str(length=random.randint(8, 30))
                self.val_obf_map[rscs] = obf

        # Obfuscate accounting logs
        # Note: We can't rely on sed to do this because there might be logs
        # From long back which have usernames & hostnames that didn't get
        # captured in the qstat/pbs_rstat/pbsnodes outputs
        self.obfuscate_acct_logs(snap_dir, sudo_val)

        # Until we can support obfuscating daemon logs, delete them
        svr_logs = os.path.join(snap_dir, SVR_LOGS_PATH)
        mom_logs = os.path.join(snap_dir, MOM_LOGS_PATH)
        comm_logs = os.path.join(snap_dir, COMM_LOGS_PATH)
        db_logs = os.path.join(snap_dir, PG_LOGS_PATH)
        sched_logs = []
        for dirname in self.du.listdir(path=snap_dir, sudo=sudo_val):
            if dirname.startswith(DFLT_SCHED_LOGS_PATH):
                dirpath = os.path.join(snap_dir, str(dirname))
                sched_logs.append(dirpath)
        # Also delete any .JB files, store printjob outputs of them instead
        conf = self.du.parse_pbs_config()
        printjob = None
        if conf is not None:
            printjob = os.path.join(conf["PBS_EXEC"], "bin", "printjob")
            if not os.path.isfile(printjob):
                printjob = None
        if printjob is None:
            self.logger.error("printjob not found, so .JB files will "
                              "simply be deleted")
        jobspath = os.path.join(snap_dir, MOM_PRIV_PATH, "jobs")
        jbcontent = {}
        jbfilelist = self.du.listdir(path=jobspath, sudo=sudo_val)
        if jbfilelist is not None:
            for name in jbfilelist:
                if name.endswith(".JB"):
                    ret = None
                    fpath = os.path.join(jobspath, name)
                    if printjob is not None:
                        cmd = [printjob, fpath]
                        ret = self.du.run_cmd(cmd=cmd, sudo=sudo_val,
                                              as_script=True)
                    self.du.rm(path=fpath)
                    if ret is not None and ret["out"] is not None:
                        jbcontent[name] = "\n".join(ret["out"])
                # Also delete any other files/directories inside mom_priv/jobs
                else:
                    path = os.path.join(jobspath, name)
                    self.du.rm(path=path, recursive=True, force=True)
        for name, content in jbcontent.items():
            # Save the printjob outputs, these will be obfuscated later
            fpath = os.path.join(jobspath, name + "_printjob")
            with open(fpath, "w") as fd:
                fd.write(str(content))

        dirs_to_del = [svr_logs, mom_logs, comm_logs, db_logs] + sched_logs
        for dirpath in dirs_to_del:
            self.du.rm(path=dirpath, recursive=True, force=True)

        # Now, go through the obfuscation map and replace all other instances
        # of the sensitive values in the snapshot with their obfuscated values
        for root, _, fnames in os.walk(snap_dir):
            for fname in fnames:
                fpath = os.path.join(root, fname)
                self._obfuscate_with_map(fpath, sudo=sudo_val)

        with open(map_file, "w") as fd:
            fd.write("Attributes Obfuscated:\n")
            fd.write(pprint.pformat(self.val_obf_map) + "\n")
            fd.write("Attributes Deleted:\n")
            fd.write("\n".join(self.vals_to_del) + "\n")


class PBSSnapUtils(object):
    """
    Wrapper class around _PBSSnapUtils
    This makes sure that we do necessay cleanup before destroying objects
    """

    def __init__(self, out_dir, basic=None, acct_logs=None,
                 daemon_logs=None, create_tar=False, log_path=None,
                 with_sudo=False):
        self.out_dir = out_dir
        self.basic = basic
        self.acct_logs = acct_logs
        self.srvc_logs = daemon_logs
        self.create_tar = create_tar
        self.log_path = log_path
        self.with_sudo = with_sudo
        self.utils_obj = None

    def __enter__(self):
        self.utils_obj = _PBSSnapUtils(self.out_dir, self.basic,
                                       self.acct_logs, self.srvc_logs,
                                       self.create_tar, self.log_path,
                                       self.with_sudo)
        return self.utils_obj

    def __exit__(self, exc_type, exc_value, traceback):
        # Do some cleanup
        self.utils_obj.finalize()

        return False


class _PBSSnapUtils(object):

    """
    PBS snapshot utilities
    """

    def __init__(self, out_dir, basic=None, acct_logs=None,
                 daemon_logs=None, create_tar=False, log_path=None,
                 with_sudo=False):
        """
        Initialize a PBSSnapUtils object with the arguments specified

        :param out_dir: path to the directory where snapshot will be created
        :type out_dir: str
        :param basic: only capture basic PBS configuration & state data?
        :type basic: bool
        :param acct_logs: number of accounting logs to capture
        :type acct_logs: int or None
        :param daemon_logs: number of daemon logs to capture
        :type daemon_logs: int or None
        :param create_tar: Create a tarball of the output snapshot?
        :type create_tar: bool or None
        :param log_path: Path to pbs_snapshot's log file
        :type log_path: str or None
        :param with_sudo: Capture relevant information with sudo?
        :type with_sudo: bool
        """
        self.logger = logging.getLogger(__name__)
        self.du = DshUtils()
        self.basic = basic
        self.server_info = {}
        self.job_info = {}
        self.node_info = {}
        self.comm_info = {}
        self.hook_info = {}
        self.sched_info = {}
        self.resv_info = {}
        self.sys_info = {}
        self.core_info = {}
        self.all_hosts = []
        self.server = None
        self.mom = None
        self.comm = None
        self.scheduler = None
        self.log_utils = PBSLogUtils()
        self.outtar_path = None
        self.outtar_fd = None
        self.create_tar = create_tar
        self.snapshot_name = None
        self.with_sudo = with_sudo
        self.log_path = log_path
        self.server_up = False
        self.server_info_avail = False
        self.mom_info_avail = False
        self.comm_info_avail = False
        self.sched_info_avail = False
        if self.log_path is not None:
            self.log_filename = os.path.basename(self.log_path)
        else:
            self.log_filename = None
        self.capture_core_files = True

        filecmd = "file"
        self.filecmd = self.du.which(exe=filecmd)
        # du.which returns the input cmd name if it can't find the cmd
        if self.filecmd is filecmd:
            self.capture_core_files = False
            self.logger.info("Warning: file command not found, "
                             "can't capture traces from any core files")

        # finalize() is called by the context's __exit__() automatically
        # however, finalize() is non-reenterant, so set a flag to keep
        # track of whether it has been called or not.
        self.finalized = False

        # Parse the input arguments
        timestamp_str = time.strftime("%Y%m%d_%H_%M_%S")
        self.snapshot_name = "snapshot_" + timestamp_str
        # Make sure that the target directory exists
        dir_path = os.path.abspath(out_dir)
        if not os.path.isdir(dir_path):
            raise ValueError("Target directory either doesn't exist" +
                             "or not accessible. Quitting.")
        self.snapdir = os.path.join(dir_path, self.snapshot_name)
        self.num_acct_logs = int(acct_logs) if acct_logs is not None else 0
        if daemon_logs is not None:
            self.num_daemon_logs = int(daemon_logs)
        else:
            self.num_daemon_logs = 0

        # Check which of the PBS daemons' information is available
        self.server = Server()
        self.scheduler = None
        daemon_status = self.server.pi.status()
        if len(daemon_status) > 0 and daemon_status['rc'] == 0 and \
                len(daemon_status['err']) == 0:
            for d_stat in daemon_status['out']:
                if d_stat.startswith("pbs_server"):
                    self.server_info_avail = True
                    if "not running" not in d_stat:
                        self.server_up = True
                elif d_stat.startswith("pbs_sched"):
                    self.sched_info_avail = True
                    self.scheduler = Scheduler(server=self.server)
                elif d_stat.startswith("pbs_mom"):
                    self.mom_info_avail = True
                elif d_stat.startswith("pbs_comm"):
                    self.comm_info_avail = True
        self.custom_rscs = None
        if self.server_up:
            self.custom_rscs = self.server.parse_resources()

        # Store paths to PBS_HOME and PBS_EXEC
        self.pbs_home = self.server.pbs_conf["PBS_HOME"]
        self.pbs_exec = self.server.pbs_conf["PBS_EXEC"]

        # If output needs to be a tarball, create the tarfile name
        # tarfile name = <output directory name>.tgz
        self.outtar_path = self.snapdir + ".tgz"

        # Set up some infrastructure
        self.__init_cmd_path_map()

        # Create the snapshot directory tree
        self.__initialize_snapshot()

    def __init_cmd_path_map(self):
        """
        Fill in various dicts which map the commands used for capturing
        various classes of outputs along with the paths to the files where
        they will be stored inside the snapshot as a tuple.
        """
        if self.server_up:
            # Server information
            value = (QSTAT_BF_PATH, [QSTAT_CMD, "-Bf"])
            self.server_info[QSTAT_BF_OUT] = value
            value = (QSTAT_QF_PATH, [QSTAT_CMD, "-Qf"])
            self.server_info[QSTAT_QF_OUT] = value
            if not self.basic:
                value = (QSTAT_B_PATH, [QSTAT_CMD, "-B"])
                self.server_info[QSTAT_B_OUT] = value
                value = (QMGR_PS_PATH, [QMGR_CMD, "-c", "p s"])
                self.server_info[QMGR_PS_OUT] = value
                value = (QSTAT_Q_PATH, [QSTAT_CMD, "-Q"])
                self.server_info[QSTAT_Q_OUT] = value
                value = (QMGR_PR_PATH, [QMGR_CMD, "-c", "p r"])
                self.server_info[QMGR_PR_OUT] = value
                value = (QMGR_PQ_PATH, [QMGR_CMD, "-c", "p q @default"])
                self.server_info[QMGR_PQ_OUT] = value

            # Job information
            value = (QSTAT_F_PATH, [QSTAT_CMD, "-f"])
            self.job_info[QSTAT_F_OUT] = value
            value = (QSTAT_TF_PATH, [QSTAT_CMD, "-tf"])
            self.job_info[QSTAT_TF_OUT] = value
            if not self.basic:
                value = (QSTAT_PATH, [QSTAT_CMD])
                self.job_info[QSTAT_OUT] = value
                value = (QSTAT_T_PATH, [QSTAT_CMD, "-t"])
                self.job_info[QSTAT_T_OUT] = value
                value = (QSTAT_X_PATH, [QSTAT_CMD, "-x"])
                self.job_info[QSTAT_X_OUT] = value
                value = (QSTAT_XF_PATH, [QSTAT_CMD, "-xf"])
                self.job_info[QSTAT_XF_OUT] = value
                value = (QSTAT_NS_PATH, [QSTAT_CMD, "-ns"])
                self.job_info[QSTAT_NS_OUT] = value
                value = (QSTAT_FX_DSV_PATH, [QSTAT_CMD, "-fx", "-F", "dsv"])
                self.job_info[QSTAT_FX_DSV_OUT] = value
                value = (QSTAT_F_DSV_PATH, [QSTAT_CMD, "-f", "-F", "dsv"])
                self.job_info[QSTAT_F_DSV_OUT] = value
                value = (QSTAT_F_JSON_PATH, [QSTAT_CMD, "-f", "-F", "json"])
                self.job_info[QSTAT_F_JSON_OUT] = value

            # Node information
            value = (PBSNODES_VA_PATH, [PBSNODES_CMD, "-va"])
            self.node_info[PBSNODES_VA_OUT] = value
            if not self.basic:
                value = (PBSNODES_A_PATH, [PBSNODES_CMD, "-a"])
                self.node_info[PBSNODES_A_OUT] = value
                value = (PBSNODES_AVSJ_PATH, [PBSNODES_CMD, "-avSj"])
                self.node_info[PBSNODES_AVSJ_OUT] = value
                value = (PBSNODES_ASJ_PATH, [PBSNODES_CMD, "-aSj"])
                self.node_info[PBSNODES_ASJ_OUT] = value
                value = (PBSNODES_AVS_PATH, [PBSNODES_CMD, "-avS"])
                self.node_info[PBSNODES_AVS_OUT] = value
                value = (PBSNODES_AS_PATH, [PBSNODES_CMD, "-aS"])
                self.node_info[PBSNODES_AS_OUT] = value
                value = (PBSNODES_AFDSV_PATH, [PBSNODES_CMD, "-aFdsv"])
                self.node_info[PBSNODES_AFDSV_OUT] = value
                value = (PBSNODES_AVFDSV_PATH, [PBSNODES_CMD, "-avFdsv"])
                self.node_info[PBSNODES_AVFDSV_OUT] = value
                value = (PBSNODES_AVFJSON_PATH, [PBSNODES_CMD, "-avFjson"])
                self.node_info[PBSNODES_AVFJSON_OUT] = value
                value = (QMGR_PN_PATH, [QMGR_CMD, "-c", "p n @default"])
                self.node_info[QMGR_PN_OUT] = value

            # Hook information
            value = (QMGR_LPBSHOOK_PATH, [QMGR_CMD, "-c", "l pbshook"])
            self.hook_info[QMGR_LPBSHOOK_OUT] = value
            if not self.basic:
                value = (QMGR_PH_PATH, [QMGR_CMD, "-c", "p h @default"])
                self.hook_info[QMGR_PH_OUT] = value

            # Reservation information
            value = (PBS_RSTAT_F_PATH, [PBS_RSTAT_CMD, "-f"])
            self.resv_info[PBS_RSTAT_F_OUT] = value
            if not self.basic:
                value = (PBS_RSTAT_PATH, [PBS_RSTAT_CMD])
                self.resv_info[PBS_RSTAT_OUT] = value

            # Scheduler information
            value = (QMGR_LSCHED_PATH, [QMGR_CMD, "-c", "l sched"])
            self.sched_info[QMGR_LSCHED_OUT] = value
            if not self.basic:
                value = (QMGR_PSCHED_PATH, [QMGR_CMD, "-c", "p sched"])
                self.sched_info[QMGR_PSCHED_OUT] = value

        if self.server_info_avail:
            # Server priv and logs
            value = (SVR_PRIV_PATH, None)
            self.server_info[SVR_PRIV] = value
            value = (SVR_LOGS_PATH, None)
            self.server_info[SVR_LOGS] = value
            value = (ACCT_LOGS_PATH, None)
            self.server_info[ACCT_LOGS] = value

            # Core file information
            value = (CORE_SERVER_PATH, None)
            self.core_info[CORE_SERVER] = value

        if self.mom_info_avail:
            # Mom priv and logs
            value = (MOM_PRIV_PATH, None)
            self.node_info[MOM_PRIV] = value
            value = (MOM_LOGS_PATH, None)
            self.node_info[MOM_LOGS] = value

            # Core file information
            value = (CORE_MOM_PATH, None)
            self.core_info[CORE_MOM] = value

        if self.comm_info_avail:
            # Comm information
            value = (COMM_LOGS_PATH, None)
            self.comm_info[COMM_LOGS] = value

        if self.sched_info_avail:
            # Scheduler logs and priv
            value = (DFLT_SCHED_PRIV_PATH, None)
            self.sched_info[SCHED_PRIV] = value
            value = (DFLT_SCHED_LOGS_PATH, None)
            self.sched_info[SCHED_LOGS] = value

            # Core file information
            value = (CORE_SCHED_PATH, None)
            self.core_info[CORE_SCHED] = value

        # System information
        if not self.basic:
            value = (PBS_PROBE_PATH, [PBS_PROBE_CMD, "-v"])
            self.sys_info[PBS_PROBE_OUT] = value
            # We'll append hostname to this later (see capture_system_info)
            value = (PBS_HOSTN_PATH, [PBS_HOSTN_CMD, "-v"])
            self.sys_info[PBS_HOSTN_OUT] = value
            value = (PBS_ENV_PATH, None)
            self.sys_info[PBS_ENVIRONMENT] = value
            value = (OS_PATH, None)
            self.sys_info[OS_INFO] = value
            value = (PROCESS_PATH, ["ps", "aux", "|", "grep", "[p]bs"])
            self.sys_info[PROCESS_INFO] = value
            value = (ETC_HOSTS_PATH,
                     ["cat", os.path.join(os.sep, "etc", "hosts")])
            self.sys_info[ETC_HOSTS] = value
            value = (ETC_NSSWITCH_PATH,
                     ["cat", os.path.join(os.sep, "etc", "nsswitch.conf")])
            self.sys_info[ETC_NSSWITCH_CONF] = value
            value = (LSOF_PBS_PATH, ["lsof", "|", "grep", "[p]bs"])
            self.sys_info[LSOF_PBS_OUT] = value
            value = (VMSTAT_PATH, ["vmstat"])
            self.sys_info[VMSTAT_OUT] = value
            value = (DF_H_PATH, ["df", "-h"])
            self.sys_info[DF_H_OUT] = value
            value = (DMESG_PATH, ["dmesg", "-T"])
            self.sys_info[DMESG_OUT] = value
            value = (PS_LEAF_PATH, ["ps", "-leaf"])
            self.sys_info[PS_LEAF_OUT] = value

    def __initialize_snapshot(self):
        """
        Create a snapshot directory along with the directory structure
        Also create a tarfile and add the snapshot dir if create_tar is True
        """

        os.mkdir(self.snapdir)

        if self.create_tar:
            self.outtar_fd = tarfile.open(self.outtar_path, "w:gz")

        dirs_in_snapshot = [SYS_DIR, CORE_DIR]
        if self.server_up:
            dirs_in_snapshot.extend([SERVER_DIR, JOB_DIR, HOOK_DIR, RESV_DIR,
                                     NODE_DIR, SCHED_DIR])
        if self.server_info_avail:
            dirs_in_snapshot.extend([SVR_PRIV_PATH, SVR_LOGS_PATH,
                                     ACCT_LOGS_PATH, DATASTORE_DIR,
                                     PG_LOGS_PATH])
        if self.mom_info_avail:
            dirs_in_snapshot.extend([MOM_PRIV_PATH, MOM_LOGS_PATH])
        if self.comm_info_avail:
            dirs_in_snapshot.append(COMM_LOGS_PATH)
        if self.sched_info_avail:
            dirs_in_snapshot.extend([DFLT_SCHED_LOGS_PATH,
                                     DFLT_SCHED_PRIV_PATH])

        for item in dirs_in_snapshot:
            rel_path = os.path.join(self.snapdir, item)
            os.makedirs(rel_path, 0o755)

    def __capture_cmd_output(self, out_path, cmd, as_script=False,
                             ret_out=False, sudo=False):
        """
        Run a command and capture its output

        :param out_path: path of the output file for this command
        :type out_path: str
        :param cmd: The command to execute
        :type cmd: list
        :param as_script: Passed to run_cmd()
        :type as_Script: bool
        :param ret_out: Return output of the command?
        :type ret_out: bool
        """
        retstr = None

        with open(out_path, "a+") as out_fd:
            try:
                self.du.run_cmd(cmd=cmd, stdout=out_fd,
                                sudo=sudo, as_script=as_script)
                if ret_out:
                    out_fd.seek(0, 0)
                    retstr = out_fd.read()
            except OSError as e:
                # This usually happens when the command is not found
                # Just log and return
                self.logger.error(str(e))
                return

        if self.create_tar:
            self.__add_to_archive(out_path)

        if ret_out:
            return retstr

    @staticmethod
    def __convert_flag_to_numeric(flag):
        """
        Convert a resource's flag attribute to its numeric equivalent

        :param flag: the resource flag to convert
        :type flag: string

        :returns: numeric value of the resource flag
        """
        # Variable assignments below mirrors definitions
        # from src/include/pbs_internal.h
        ATR_DFLAG_USRD = 0x01
        ATR_DFLAG_USWR = 0x02
        ATR_DFLAG_OPRD = 0x04
        ATR_DFLAG_OPWR = 0x08
        ATR_DFLAG_MGRD = 0x10
        ATR_DFLAG_MGWR = 0x20
        ATR_DFLAG_MOM = 0x400
        ATR_DFLAG_RASSN = 0x4000
        ATR_DFLAG_ANASSN = 0x8000
        ATR_DFLAG_FNASSN = 0x10000
        ATR_DFLAG_CVTSLT = 0x20000

        NO_USER_SET = (ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD |
                       ATR_DFLAG_OPWR | ATR_DFLAG_MGWR)
        READ_WRITE = (ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD |
                      ATR_DFLAG_USWR | ATR_DFLAG_OPWR | ATR_DFLAG_MGWR)

        resc_flag = READ_WRITE
        if "q" in flag:
            resc_flag |= ATR_DFLAG_RASSN
        if "f" in flag:
            resc_flag |= ATR_DFLAG_FNASSN
        if "n" in flag:
            resc_flag |= ATR_DFLAG_ANASSN
        if "h" in flag:
            resc_flag |= ATR_DFLAG_CVTSLT
        if "m" in flag:
            resc_flag |= ATR_DFLAG_MOM
        if "r" in flag:
            resc_flag &= ~READ_WRITE
            resc_flag |= NO_USER_SET
        if "i" in flag:
            resc_flag &= ~READ_WRITE
            resc_flag |= (ATR_DFLAG_OPRD | ATR_DFLAG_OPWR |
                          ATR_DFLAG_MGRD | ATR_DFLAG_MGWR)
        return resc_flag

    @staticmethod
    def __convert_type_to_numeric(attr_type):
        """
        Convert a resource's type attribute to its numeric equivalent

        :param attr_type: the type to convert
        :type attr_type: string

        :returns: Numeric equivalent of attr_type
        """
        PBS_ATTR_TYPE_TO_INT = {
            "long": 1,
            "string": 3,
            "string_array": 4,
            "size": 5,
            "boolean": 11,
            "float": 14,
        }

        return PBS_ATTR_TYPE_TO_INT[attr_type.strip()]

    def __capture_trace_from_core(self, core_file_name, exec_path, out_path):
        """
        Capture stack strace from the core file specified

        :param core_file_name: name of the core file
        :type core_file_name: str
        :param exec_path: path to the executable which generated the core
        :type exec_path: str
        :param out_path: ofile to print the trace out to
        :type out_path: str
        """
        self.logger.info("capturing stack trace from core file " +
                         core_file_name)

        # Create a gdb-python script to capture backtrace from core
        gdb_python = """
import gdb
gdb.execute("file %s")
gdb.execute("core %s")
o = gdb.execute("thread apply all bt", to_string=True)
print(o)
gdb.execute("quit")
quit()
        """ % (exec_path, core_file_name)
        # Remove tabs from triple quoted strings
        gdb_python = gdb_python.replace("\t", "")

        # Write the gdb-python script in a temporary file
        fn = self.du.create_temp_file(body=gdb_python)

        # Catch the stack trace using gdb
        gdb_cmd = ["gdb", "-P", fn]
        with open(out_path, "w") as outfd:
            self.du.run_cmd(cmd=gdb_cmd, stdout=outfd, stderr=STDOUT,
                            sudo=self.with_sudo)

        # Remove the temp file
        os.remove(fn)

        if self.create_tar:
            self.__add_to_archive(out_path)

    def __capture_logs(self, pbs_logdir, snap_logdir, num_days_logs,
                       sudo=False):
        """
        Capture specific logs for the days mentioned

        :param pbs_logdir: path to the PBS logs directory (source)
        :type pbs_logdir: str
        :param snap_logdir: path to the snapshot logs directory (destination)
        :type snap_logdir: str
        :param num_days_logs: Number of days of logs to capture
        :type num_days_logs: int
        :param sudo: copy logs with sudo?
        :type sudo: bool
        """

        if num_days_logs < 1:
            self.logger.debug("Number of days of logs < 1, skipping")
            return

        end_time = self.server.ctime
        start_time = end_time - ((num_days_logs - 1) * 24 * 60 * 60)

        # Get the list of log file names to capture
        pbs_logfiles = self.log_utils.get_log_files(self.server.hostname,
                                                    pbs_logdir, start_time,
                                                    end_time, sudo)
        if len(pbs_logfiles) == 0:
            self.logger.debug(pbs_logdir + "not found/accessible")
            return

        self.logger.debug("Capturing " + str(num_days_logs) +
                          " days of logs from " + pbs_logdir)

        # Make sure that the target log dir exists
        if not os.path.isdir(snap_logdir):
            os.makedirs(snap_logdir)

        # Go over the list and copy over each log file
        for pbs_logfile in pbs_logfiles:
            snap_logfile = os.path.join(snap_logdir,
                                        os.path.basename(pbs_logfile))
            pbs_logfile = pbs_logfile
            self.du.run_copy(src=pbs_logfile, dest=snap_logfile,
                             recursive=False,
                             preserve_permission=False,
                             sudo=sudo)
            if sudo:
                # Copying files with sudo makes root the owner, set it to the
                # current user
                self.du.chown(path=snap_logfile, uid=os.getuid(),
                              gid=os.getgid(), sudo=self.with_sudo)

            if self.create_tar:
                self.__add_to_archive(snap_logfile)

    def __evaluate_core_file(self, file_path, core_dir):
        """
        Check whether the specified file is a core dump
        If yes, capture its stack trace and store it

        :param file_path: path to the file
        :type file_path: str
        :param core_dir: path to directory to store core information
        :type core_dir: str


        :returns: True if this was a valid core file, otherwise False
        """
        if not self.capture_core_files:
            return False

        if not self.du.isfile(path=file_path, sudo=self.with_sudo):
            self.logger.debug("Could not find file path " + str(file_path))
            return False

        # Get the header of this file
        ret = self.du.run_cmd(cmd=[self.filecmd, file_path],
                              sudo=self.with_sudo)
        if ret['err'] is not None and len(ret['err']) != 0:
            self.logger.error(
                "\'file\' command failed with error: " + ret['err'] +
                " on file: " + str(file_path))
            return False

        file_header = ret["out"][0]
        if "core file" not in file_header:
            return False

        # Identify the program which created this core file
        header_list = file_header.split()
        if "from" not in header_list:
            return False
        exec_index = header_list.index("from") + 1
        exec_name = header_list[exec_index].replace("\'", "")
        exec_name = exec_name.replace(",", "")

        # Capture the stack trace from this core file
        filename = os.path.basename(file_path)
        core_dest = os.path.join(core_dir, filename)
        if not os.path.isdir(core_dir):
            os.makedirs(core_dir, 0o755)
        self.__capture_trace_from_core(file_path, exec_name,
                                       core_dest)

        # Delete the core file itself
        if os.path.isfile(file_path):
            os.remove(file_path)

        return True

    def __copy_dir_with_core(self, src_path, dest_path, core_dir,
                             except_list=None, only_core=False, sudo=False):
        """
        Copy over a directory recursively which might have core files
        When a core file is found, capture the stack trace from it

        :param src_path: path of the source directory
        :type src_path: str
        :param dest_path: path of the destination directory
        :type dest_path: str
        :param core_dir: path to the directory to store core files' trace
        :type core_dir: str
        :param except_list: list  of files/directories (basenames) to exclude
        :type except_list: list
        :param only_core: Copy over only core files?
        :type only_core: bool
        :param sudo: Copy with sudo?
        :type sudo: bool
        """
        if except_list is None:
            except_list = []

        # This can happen when -o is a path that we are capturing
        # Just return success
        if os.path.basename(src_path) == self.snapshot_name:
            self.logger.debug("src_path %s seems to be snapshot directory,"
                              "ignoring" % src_path)
            return
        dir_list = self.du.listdir(path=src_path, fullpath=False,
                                   sudo=sudo)

        if dir_list is None:
            self.logger.info("Can't find/access " + src_path)
            return

        # Go over the list and copy over everything
        # If we find a core file, we'll store backtrace from it inside
        # core_file_bt
        for item in dir_list:
            if item in except_list:
                continue

            item_src_path = os.path.join(src_path, item)
            if not only_core:
                item_dest_path = os.path.join(dest_path, item)
            else:
                item_dest_path = core_dir

            # We can't directly use 'recursive' argument of run_copy
            # to copy the entire directory tree as we need to take care
            # of the 'except_list'. So, we recursively explore the whole
            # tree and copy over files individually.
            if self.du.isdir(path=item_src_path, sudo=sudo):
                # Make sure that the directory exists in the snapshot
                if not self.du.isdir(path=item_dest_path):
                    # Create the directory
                    os.makedirs(item_dest_path, 0o755)
                # Recursive call to copy contents of the directory
                self.__copy_dir_with_core(item_src_path, item_dest_path,
                                          core_dir, except_list, only_core,
                                          sudo=sudo)
            else:
                # Copy the file over
                item_src_path = item_src_path
                try:
                    self.du.run_copy(src=item_src_path, dest=item_dest_path,
                                     recursive=False,
                                     preserve_permission=False,
                                     level=logging.DEBUG, sudo=sudo)
                    if sudo:
                        # Copying files with sudo makes root the owner,
                        # set it to the current user
                        self.du.chown(path=item_dest_path, uid=os.getuid(),
                                      gid=os.getgid(), sudo=self.with_sudo)
                except OSError:
                    self.logger.error("Could not copy %s" % item_src_path)
                    continue

                # Check if this is a core file
                # If it is then this method will capture its stack trace
                is_core = self.__evaluate_core_file(item_dest_path, core_dir)

                # If it was a core file, then it's already been captured
                if is_core:
                    continue

                # If only_core is True and this was not a core file, then we
                # should delete it
                if only_core:
                    os.remove(item_dest_path)
                else:
                    # This was not a core file, and 'only_core' is not True
                    # So, we need to capture this file
                    if self.create_tar:
                        self.__add_to_archive(item_dest_path)

    def __capture_mom_priv(self):
        """
        Capture mom_priv information
        """
        pbs_home = self.pbs_home
        pbs_mom_priv = os.path.join(pbs_home, "mom_priv")
        snap_mom_priv = os.path.join(self.snapdir, MOM_PRIV_PATH)
        core_dir = os.path.join(self.snapdir, CORE_MOM_PATH)
        self.__copy_dir_with_core(pbs_mom_priv, snap_mom_priv, core_dir,
                                  sudo=self.with_sudo)

    def __add_to_archive(self, dest_path, src_path=None):
        """
        Add a file to the output tarball and delete the original file

        :param dest_path: path to the file inside the target tarball
        :type dest_path: str
        :param src_path: path to the file to add, if different than dest_path
        :type src_path: str
        """
        if src_path is None:
            src_path = dest_path

        self.logger.debug("Adding " + src_path + " to tarball " +
                          self.outtar_path)

        # Add file to tar
        dest_relpath = os.path.relpath(dest_path, self.snapdir)
        path_in_tar = os.path.join(self.snapshot_name, dest_relpath)
        try:
            self.outtar_fd.add(src_path, arcname=path_in_tar)

            # Remove original file
            os.remove(src_path)
        except OSError:
            self.logger.error(
                "File %s could not be added to tarball" % (src_path))

    def __capture_svr_logs(self):
        """
        Capture server logs
        """
        pbs_logdir = os.path.join(self.pbs_home, "server_logs")
        snap_logdir = os.path.join(self.snapdir, SVR_LOGS_PATH)
        self.__capture_logs(pbs_logdir, snap_logdir, self.num_daemon_logs)

    def __capture_acct_logs(self):
        """
        Capture accounting logs
        """
        pbs_logdir = os.path.join(self.pbs_home, "server_priv", "accounting")
        snap_logdir = os.path.join(self.snapdir, ACCT_LOGS_PATH)
        self.__capture_logs(pbs_logdir, snap_logdir, self.num_acct_logs,
                            sudo=self.with_sudo)

    def __capture_sched_logs(self, pbs_logdir, snap_logdir):
        """
        Capture scheduler logs
        """
        self.__capture_logs(pbs_logdir, snap_logdir, self.num_daemon_logs)

    def __capture_mom_logs(self):
        """
        Capture mom logs
        """
        pbs_home = self.pbs_home
        pbs_logdir = os.path.join(pbs_home, "mom_logs")
        snap_logdir = os.path.join(self.snapdir, MOM_LOGS_PATH)
        self.__capture_logs(pbs_logdir, snap_logdir, self.num_daemon_logs)

    def __capture_comm_logs(self):
        """
        Capture pbs_comm logs
        """
        pbs_home = self.pbs_home
        pbs_logdir = os.path.join(pbs_home, "comm_logs")
        snap_logdir = os.path.join(self.snapdir, COMM_LOGS_PATH)
        self.__capture_logs(pbs_logdir, snap_logdir, self.num_daemon_logs)

    def capture_server(self, with_svr_logs=False, with_acct_logs=False):
        """
        Capture PBS server specific information

        :param with_svr_logs: capture server logs as well?
        :type with_svr_logs: bool
        :param with_acct_logs: capture accounting logs as well?
        :type with_acct_logs: bool

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing server information")

        if self.server_up:
            # Go through 'server_info' and capture info that depends on
            # commands
            for (path, cmd_list) in self.server_info.values():
                if cmd_list is None:
                    continue
                cmd_list_cpy = list(cmd_list)

                # Add the path to PBS_EXEC to the command path
                # The command path is the first entry in command list
                cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
                snap_path = os.path.join(self.snapdir, path)
                self.__capture_cmd_output(snap_path, cmd_list_cpy,
                                          sudo=self.with_sudo)

        if self.server_info_avail:
            if self.basic:
                # Only copy over the resourcedef file
                snap_rscdef = os.path.join(self.snapdir, RSCDEF_PATH)
                pbs_rscdef = os.path.join(self.pbs_home, RSCDEF_PATH)
                self.du.run_copy(src=pbs_rscdef, dest=snap_rscdef,
                                 recursive=False,
                                 preserve_permission=False,
                                 level=logging.DEBUG, sudo=self.with_sudo)
                if self.create_tar:
                    self.__add_to_archive(snap_rscdef)

            else:
                # Copy over 'server_priv', everything except accounting logs
                snap_server_priv = os.path.join(self.snapdir, SVR_PRIV_PATH)
                pbs_server_priv = os.path.join(self.pbs_home, "server_priv")
                core_dir = os.path.join(self.snapdir, CORE_SERVER_PATH)
                exclude_list = ["accounting"]
                self.__copy_dir_with_core(pbs_server_priv,
                                          snap_server_priv, core_dir,
                                          exclude_list, sudo=self.with_sudo)

            if with_svr_logs and self.num_daemon_logs > 0:
                # Capture server logs
                self.__capture_svr_logs()

            if with_acct_logs and self.num_acct_logs > 0:
                # Capture accounting logs
                self.__capture_acct_logs()

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_jobs(self):
        """
        Capture information related to jobs

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing jobs information")

        if self.server_up:
            # Go through 'job_info' and capture info that depends on commands
            for (path, cmd_list) in self.job_info.values():
                cmd_list_cpy = list(cmd_list)

                # Add the path to PBS_EXEC to the command path
                # The command path is the first entry in command list
                cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
                snap_path = os.path.join(self.snapdir, path)
                self.__capture_cmd_output(snap_path, cmd_list_cpy,
                                          sudo=self.with_sudo)

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_nodes(self, with_mom_logs=False):
        """
        Capture information related to nodes & mom along with mom logs

        :param with_mom_logs: Capture mom logs?
        :type with_mom_logs: bool

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing nodes & mom information")

        if self.server_up:
            # Go through 'node_info' and capture info that depends on commands
            for (path, cmd_list) in self.node_info.values():
                if cmd_list is None:
                    continue
                cmd_list_cpy = list(cmd_list)

                # Add the path to PBS_EXEC to the command path
                # The command path is the first entry in command list
                cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
                snap_path = os.path.join(self.snapdir, path)
                self.__capture_cmd_output(snap_path, cmd_list_cpy,
                                          sudo=self.with_sudo)

        # Collect mom logs and priv
        if self.mom_info_avail:
            if not self.basic:
                # Capture mom_priv info
                self.__capture_mom_priv()

            if with_mom_logs and self.num_daemon_logs > 0:
                # Capture mom_logs
                self.__capture_mom_logs()

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_comms(self, with_comm_logs=False):
        """
        Capture Comm related information

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing comm information")

        # Capture comm logs
        if self.comm_info_avail:
            if self.num_daemon_logs > 0 and with_comm_logs:
                self.__capture_comm_logs()

        # If not already capturing server information, copy over server_priv
        # as pbs_comm runs out of it
        if not self.server_info_avail and not self.basic:
            pbs_server_priv = os.path.join(self.pbs_home, "server_priv")
            snap_server_priv = os.path.join(self.snapdir, SVR_PRIV_PATH)
            core_dir = os.path.join(self.snapdir, CORE_SERVER_PATH)
            exclude_list = ["accounting"]
            self.__copy_dir_with_core(pbs_server_priv,
                                      snap_server_priv, core_dir, exclude_list,
                                      sudo=self.with_sudo)
        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_scheduler(self, with_sched_logs=False):
        """
        Capture information related to the scheduler

        :param with_sched_logs: Capture scheduler logs?
        :type with_sched_logs: bool

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing scheduler information")

        qmgr_lsched = None
        if self.server_up:
            # Go through 'sched_info' and capture info that depends on commands
            for (path, cmd_list) in self.sched_info.values():
                if cmd_list is None:
                    continue
                cmd_list_cpy = list(cmd_list)

                # Add the path to PBS_EXEC to the command path
                # The command path is the first entry in command list
                cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
                snap_path = os.path.join(self.snapdir, path)
                if "l sched" in cmd_list_cpy:
                    qmgr_lsched = self.__capture_cmd_output(snap_path,
                                                            cmd_list_cpy,
                                                            ret_out=True)
                else:
                    self.__capture_cmd_output(snap_path, cmd_list_cpy,
                                              sudo=self.with_sudo)

        # Capture sched_priv & sched_logs for all schedulers
        if qmgr_lsched is not None and self.sched_info_avail:
            sched_details = {}
            sched_name = None
            for line in qmgr_lsched.splitlines():
                if line.startswith("Sched "):
                    sched_name = line.split("Sched ")[1]
                    sched_name = "".join(sched_name.split())
                    sched_details[sched_name] = {}
                    continue
                if sched_name is not None:
                    line = "".join(line.split())
                    if line.startswith("sched_priv="):
                        sched_details[sched_name]["sched_priv"] = \
                            line.split("=")[1]
                    elif line.startswith("sched_log="):
                        sched_details[sched_name]["sched_log"] = \
                            line.split("=")[1]

            for sched_name in sched_details:
                pbs_sched_priv = None
                # Capture sched_priv for the scheduler
                if len(sched_details) == 1:  # For pre-multisched outputs
                    pbs_sched_priv = os.path.join(self.pbs_home, "sched_priv")
                elif "sched_priv" in sched_details[sched_name]:
                    pbs_sched_priv = sched_details[sched_name]["sched_priv"]
                if sched_name == "default" or len(sched_details) == 1:
                    snap_sched_priv = os.path.join(self.snapdir,
                                                   DFLT_SCHED_PRIV_PATH)
                    core_dir = os.path.join(self.snapdir, CORE_SCHED_PATH)
                else:
                    dirname = DFLT_SCHED_PRIV_PATH + "_" + sched_name
                    coredirname = CORE_SCHED_PATH + "_" + sched_name
                    snap_sched_priv = os.path.join(self.snapdir, dirname)
                    os.makedirs(snap_sched_priv, 0o755)
                    core_dir = os.path.join(self.snapdir, coredirname)

                if pbs_sched_priv and os.path.isdir(pbs_sched_priv):
                    self.__copy_dir_with_core(pbs_sched_priv,
                                              snap_sched_priv, core_dir,
                                              sudo=self.with_sudo)
                if with_sched_logs and self.num_daemon_logs > 0:
                    pbs_sched_log = None
                    # Capture scheduler logs
                    if len(sched_details) == 1:  # For pre-multisched outputs
                        pbs_sched_log = os.path.join(self.pbs_home,
                                                     "sched_logs")
                    elif "sched_log" in sched_details[sched_name]:
                        pbs_sched_log = sched_details[sched_name]["sched_log"]
                    if sched_name == "default" or len(sched_details) == 1:
                        snap_sched_log = os.path.join(self.snapdir,
                                                      DFLT_SCHED_LOGS_PATH)
                    else:
                        dirname = DFLT_SCHED_LOGS_PATH + "_" + sched_name
                        snap_sched_log = os.path.join(self.snapdir, dirname)
                        os.makedirs(snap_sched_log, 0o755)

                    if pbs_sched_log and os.path.isdir(pbs_sched_log):
                        self.__capture_sched_logs(pbs_sched_log,
                                                  snap_sched_log)

        elif self.sched_info_avail:
            # We don't know about other multi-scheds,
            # but can still capture the default sched's logs & priv
            pbs_sched_priv = os.path.join(self.pbs_home, "sched_priv")
            snap_sched_priv = os.path.join(self.snapdir,
                                           DFLT_SCHED_PRIV_PATH)
            core_dir = os.path.join(self.snapdir, CORE_SCHED_PATH)
            self.__copy_dir_with_core(pbs_sched_priv,
                                      snap_sched_priv, core_dir,
                                      sudo=self.with_sudo)
            if with_sched_logs and self.num_daemon_logs > 0:
                pbs_sched_log = os.path.join(self.pbs_home,
                                             "sched_logs")
                snap_sched_log = os.path.join(self.snapdir,
                                              DFLT_SCHED_LOGS_PATH)
                self.__capture_sched_logs(pbs_sched_log, snap_sched_log)

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_hooks(self):
        """
        Capture information related to hooks

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing hooks information")

        # Go through 'hook_info' and capture info that depends on commands
        for (path, cmd_list) in self.hook_info.values():
            if cmd_list is None:
                continue
            cmd_list_cpy = list(cmd_list)

            # Add the path to PBS_EXEC to the command path
            # The command path is the first entry in command list
            cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
            snap_path = os.path.join(self.snapdir, path)
            self.__capture_cmd_output(snap_path, cmd_list_cpy,
                                      sudo=self.with_sudo)

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_reservations(self):
        """
        Capture information related to reservations

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing reservations information")

        # Go through 'resv_info' and capture info that depends on commands
        for (path, cmd_list) in self.resv_info.values():
            if cmd_list is None:
                continue
            cmd_list_cpy = list(cmd_list)

            # Add the path to PBS_EXEC to the command path
            # The command path is the first entry in command list
            cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
            snap_path = os.path.join(self.snapdir, path)
            self.__capture_cmd_output(snap_path, cmd_list_cpy,
                                      sudo=self.with_sudo)

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_datastore(self, with_db_logs=False):
        """
        Capture information related to datastore

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing datastore information")

        if with_db_logs and self.num_daemon_logs > 0:
            # Capture database logs
            pbs_logdir = os.path.join(self.pbs_home, PG_LOGS_PATH)
            snap_logdir = os.path.join(self.snapdir, PG_LOGS_PATH)
            self.__capture_logs(pbs_logdir, snap_logdir, self.num_daemon_logs,
                                sudo=self.with_sudo)

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_pbs_conf(self):
        """
        Capture pbs.conf file

        :returns: name of the output directory/tarfile containing the snapshot
        """
        # Capture pbs.conf
        self.logger.info("capturing pbs.conf")
        snap_confpath = os.path.join(self.snapdir, PBS_CONF_PATH)
        with open(snap_confpath, "w") as fd:
            for k, v in self.server.pbs_conf.items():
                fd.write(k + "=" + str(v) + "\n")

        if self.create_tar:
            self.__add_to_archive(snap_confpath)
            return self.outtar_path
        else:
            return self.snapdir

    def capture_system_info(self):
        """
        Capture system related information

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing system information")

        if self.basic:
            return

        sudo_cmds = [PBS_PROBE_OUT, LSOF_PBS_OUT, DMESG_OUT]
        as_script_cmds = [PROCESS_INFO, LSOF_PBS_OUT]
        pbs_cmds = [PBS_PROBE_OUT, PBS_HOSTN_OUT]

        host_platform = self.du.get_platform()
        win_platform = False
        if host_platform.startswith("win"):
            win_platform = True

        # Capture information that's dependent on commands
        for (key, values) in self.sys_info.items():
            sudo = False
            (path, cmd_list) = values
            if cmd_list is None:
                continue
            # For Windows, only capture PBS commands
            if win_platform and (key not in pbs_cmds):
                continue

            cmd_list_cpy = list(cmd_list)

            # Find the full path to the command on the host
            if key in pbs_cmds:
                cmd_full = os.path.join(self.pbs_exec, cmd_list_cpy[0])
            else:
                cmd_full = self.du.which(exe=cmd_list_cpy[0])
            # du.which() returns the name of the command passed if
            # it can't find the command
            if cmd_full is cmd_list_cpy[0]:
                continue
            cmd_list_cpy[0] = cmd_full

            # Handle special commands
            if "pbs_hostn" in cmd_list_cpy[0]:
                # Append hostname to the command list
                cmd_list_cpy.append(self.server.hostname)
            if key in as_script_cmds:
                as_script = True
                if key in sudo_cmds and self.with_sudo:
                    # Because this cmd needs to be run in a script,
                    # PTL run_cmd's sudo will try to run the script
                    # itself with sudo, not the cmd
                    # So, append sudo as a prefix to the cmd instead
                    cmd_list_cpy[0] = (' '.join(self.du.sudo_cmd) +
                                       ' ' + cmd_list_cpy[0])
            else:
                as_script = False
                if key in sudo_cmds:
                    sudo = self.with_sudo

            snap_path = os.path.join(self.snapdir, path)
            self.__capture_cmd_output(snap_path, cmd_list_cpy,
                                      as_script=as_script, sudo=sudo)

        # Capture platform dependent information
        if win_platform:
            # Capture process information using tasklist command
            cmd = ["tasklist", ["/v"]]
            snap_path = PROCESS_PATH
            self.__capture_cmd_output(snap_path, cmd,
                                      sudo=self.with_sudo)

        # Capture OS/platform information
        self.logger.info("capturing OS information")
        snap_ospath = os.path.join(self.snapdir, OS_PATH)
        with open(snap_ospath, "w") as osfd:
            osinfo = platform.platform()
            osfd.write(osinfo + "\n")
            # If /etc/os-release is available then save that as well
            fpath = os.path.join(os.sep, "etc", "os-release")
            if os.path.isfile(fpath):
                with open(fpath, "r") as fd:
                    fcontent = fd.read()
                osfd.write("\n/etc/os-release:\n" + fcontent)
        if self.create_tar:
            self.__add_to_archive(snap_ospath)

        # Capture pbs_environment
        self.logger.info("capturing pbs_environment")
        snap_envpath = os.path.join(self.snapdir, PBS_ENV_PATH)
        if self.server.pbs_env is not None:
            with open(snap_envpath, "w") as envfd:
                for k, v in self.server.pbs_env.items():
                    envfd.write(k + "=" + v + "\n")
        if self.create_tar:
            self.__add_to_archive(snap_envpath)

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_pbs_logs(self):
        """
        Capture PBS logs from all relevant hosts

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing PBS logs")

        if self.num_daemon_logs > 0:
            # Capture server logs
            if self.server_info_avail:
                self.__capture_svr_logs()

            # Capture sched logs for all schedulers
            if self.sched_info_avail:
                if self.server_up:
                    sched_info = self.server.status(SCHED)
                    for sched in sched_info:
                        sched_name = sched["id"]
                        pbs_sched_log = sched["sched_log"]
                        if sched_name != "default":
                            snap_sched_log = DFLT_SCHED_LOGS_PATH + \
                                "_" + sched["id"]
                        else:
                            snap_sched_log = DFLT_SCHED_LOGS_PATH
                        snap_sched_log = os.path.join(self.snapdir,
                                                      snap_sched_log)
                        self.__capture_sched_logs(pbs_sched_log,
                                                  snap_sched_log)
                else:
                    # Capture the default sched's logs
                    pbs_sched_log = os.path.join(self.pbs_home,
                                                 "sched_logs")
                    snap_sched_log = os.path.join(self.snapdir,
                                                  DFLT_SCHED_LOGS_PATH)
                    self.__capture_sched_logs(pbs_sched_log, snap_sched_log)

            # Capture mom & comm logs
            if self.mom_info_avail:
                self.__capture_mom_logs()
            if self.comm_info_avail:
                self.__capture_comm_logs()

        if self.num_acct_logs > 0:
            # Capture accounting logs
            self.__capture_acct_logs()

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_all(self):
        """
        Capture a snapshot from the PBS system

        :returns: name of the output directory/tarfile containing the snapshot
        """
        # Capture Server related information
        self.capture_server(with_svr_logs=True, with_acct_logs=True)
        # Capture scheduler information
        self.capture_scheduler(with_sched_logs=True)
        # Capture jobs related information
        self.capture_jobs()
        # Capture nodes relateed information
        self.capture_nodes(with_mom_logs=True)
        # Capture comm related information
        self.capture_comms(with_comm_logs=True)
        # Capture hooks related information
        self.capture_hooks()
        # Capture reservations related information
        self.capture_reservations()
        # Capture datastore related information
        self.capture_datastore(with_db_logs=True)
        # Capture pbs.conf
        self.capture_pbs_conf()
        # Capture system related information
        self.capture_system_info()

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def finalize(self):
        """
        Capture some common information and perform cleanup
        """

        if self.finalized:
            # This function is non-reenterant
            # So just return if it's already been called once
            self.logger.debug("finalize() already called once, skipping it.")
            return

        self.finalized = True

        # Record timestamp of the snapshot
        snap_ctimepath = os.path.join(self.snapdir, CTIME_PATH)
        with open(snap_ctimepath, "w") as ctimefd:
            ctimefd.write(str(self.server.ctime) + "\n")
        if self.create_tar:
            self.__add_to_archive(snap_ctimepath)

        # If the caller was pbs_snapshot, add its log file to the tarball
        if self.create_tar and self.log_path is not None:
            snap_logpath = os.path.join(self.snapdir, self.log_filename)
            self.__add_to_archive(snap_logpath, self.log_path)

        # Cleanup
        if self.create_tar:
            # Close the output tarfile
            self.outtar_fd.close()
            # Remove the snapshot directory
            self.du.rm(path=self.snapdir, recursive=True, force=True)

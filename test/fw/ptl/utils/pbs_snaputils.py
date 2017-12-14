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

import os
import time
import tarfile
import magic
import logging

from subprocess import STDOUT
from ptl.lib.pbs_testlib import Server, Scheduler
from ptl.lib.pbs_ifl_mock import *
from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_logutils import PBSLogUtils
from ptl.utils.pbs_anonutils import PBSAnonymizer

BUILT_IN_RSCS = """Name: cput
    type = 1
    flag = 3135
Name: mem
    type = 5
    flag = 181311
Name: walltime
    type = 1
    flag = 3135
Name: ncpus
    type = 1
    flag = 181311
Name: arch
    type = 3
    flag = 132159
Name: host
    type = 3
    flag = 131135
Name: vnode
    type = 3
    flag = 131135
Name: aoe
    type = 3
    flag = 131135
Name: min_walltime
    type = 1
    flag = 2111
Name: max_walltime
    type = 1
    flag = 2111
Name: preempt_targets
    type = 3
    flag = 63
Name: naccelerators
    type = 1
    flag = 181311
Name: select
    type = 3
    flag = 63
Name: place
    type = 3
    flag = 1087
Name: nodes
    type = 3
    flag = 63
Name: nodect
    type = 1
    flag = 16437
Name: nchunk
    type = 1
    flag = 131133
Name: vntype
    type = 3
    flag = 131135
Name: mpiprocs
    type = 1
    flag = 147519
Name: ompthreads
    type = 1
    flag = 131135
Name: cpupercent
    type = 1
    flag = 61
Name: file
    type = 5
    flag = 1087
Name: pmem
    type = 5
    flag = 1087
Name: vmem
    type = 5
    flag = 181311
Name: pvmem
    type = 5
    flag = 1087
Name: nice
    type = 1
    flag = 1087
Name: pcput
    type = 1
    flag = 1087
Name: nodemask
    type = 3
    flag = 1085
Name: hpm
    type = 1
    flag = 17471
Name: ssinodes
    type = 1
    flag = 1087
Name: resc
    type = 3
    flag = 63
Name: software
    type = 3
    flag = 63
Name: site
    type = 3
    flag = 1087
Name: exec_vnode
    type = 3
    flag = 61
Name: start_time
    type = 1
    flag = 61
Name: mpphost
    type = 3
    flag = 1087
Name: mpparch
    type = 3
    flag = 1087
Name: mpplabels
    type = 3
    flag = 1087
Name: mppwidth
    type = 1
    flag = 1087
Name: mppdepth
    type = 1
    flag = 1087
Name: mppnppn
    type = 1
    flag = 1087
Name: mppnodes
    type = 3
    flag = 3135
Name: mppmem
    type = 5
    flag = 1087
Name: mppt
    type = 1
    flag = 3135
Name: partition
    type = 3
    flag = 1085
Name: accelerator
    type = 11
    flag = 132159
Name: accelerator_model
    type = 3
    flag = 132159
Name: accelerator_memory
    type = 5
    flag = 181311
Name: accelerator_group
    type = 3
    flag = 131135
Name: |unknown|
    type = 0
    flag = 63
"""

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
    QSTAT_Q_OUT,
    QSTAT_QF_OUT,
    # qmgr outputs
    QMGR_PS_OUT,
    QMGR_PH_OUT,
    QMGR_LPBSHOOK_OUT,
    QMGR_LSCHED_OUT,
    QMGR_PN_OUT,
    QMGR_PR_OUT,
    # pbsnodes outputs
    PBSNODES_VA_OUT,
    PBSNODES_A_OUT,
    PBSNODES_AVSJ_OUT,
    PBSNODES_ASJ_OUT,
    PBSNODES_AVS_OUT,
    PBSNODES_AS_OUT,
    PBSNODES_AFDSV_OUT,
    PBSNODES_AVFDSV_OUT,
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
    RSCS_ALL,
    CTIME) = range(56)


# Define paths to various files/directories with respect to the snapshot
# server/
SERVER_DIR = "server"
QSTAT_B_PATH = os.path.join(SERVER_DIR, "qstat_B.out")
QSTAT_BF_PATH = os.path.join(SERVER_DIR, "qstat_Bf.out")
QMGR_PS_PATH = os.path.join(SERVER_DIR, "qmgr_ps.out")
QSTAT_Q_PATH = os.path.join(SERVER_DIR, "qstat_Q.out")
QSTAT_QF_PATH = os.path.join(SERVER_DIR, "qstat_Qf.out")
QMGR_PR_PATH = os.path.join(SERVER_DIR, "qmgr_pr.out")
RSCS_PATH = os.path.join(SERVER_DIR, "rscs_all")
# server_priv/
SVR_PRIV_PATH = "server_priv"
ACCT_LOGS_PATH = os.path.join("server_priv", "accounting")
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
# sched_priv/
SCHED_PRIV_PATH = "sched_priv"
# sched_logs/
SCHED_LOGS_PATH = "sched_logs"
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

# A global list of files which contain data in tabular form
FILE_TABULAR = ["qstat.out", "qstat_t.out", "qstat_x.out", "qstat_ns.out",
                "pbsnodes_aS.out", "pbsnodes_aSj.out", "pbsnodes_avS.out",
                "pbsnodes_avSj.out", "qstat_Q.out", "qstat_B.out",
                "pbs_rstat.out"]


class PBSSnapUtils(object):
    """
    Wrapper class around _PBSSnapUtils
    This makes sure that we do necessay cleanup before destroying objects
    """

    def __init__(self, out_dir, server_host=None, acct_logs=None,
                 daemon_logs=None, additional_hosts=None,
                 map_file=None, anonymize=None, create_tar=False,
                 log_path=None, sudo=False):
        self.out_dir = out_dir
        self.server_host = server_host
        self.acct_logs = acct_logs
        self.srvc_logs = daemon_logs
        self.additional_hosts = additional_hosts
        self.map_file = map_file
        self.anonymize = anonymize
        self.create_tar = create_tar
        self.log_path = log_path
        self.sudo = sudo
        self.utils_obj = None

    def __enter__(self):
        self.utils_obj = _PBSSnapUtils(self.out_dir, self.server_host,
                                       self.acct_logs, self.srvc_logs,
                                       self.additional_hosts,
                                       self.map_file, self.anonymize,
                                       self.create_tar, self.log_path,
                                       self.sudo)
        return self.utils_obj

    def __exit__(self, exc_type, exc_value, traceback):
        # Do some cleanup
        self.utils_obj.finalize()

        return False


class _PBSSnapUtils(object):

    """
    PBS snapshot utilities
    """

    def __init__(self, out_dir, server_host=None, acct_logs=None,
                 daemon_logs=None, additional_hosts=None,
                 map_file=None, anonymize=False, create_tar=False,
                 log_path=None, sudo=False):
        """
        Initialize a PBSSnapUtils object with the arguments specified

        :param out_dir: path to the directory where snapshot will be created
        :type out_dir: str
        :param server_host: Name of the host where PBS Server is running
        :type server_host: str or None
        :param acct_logs: number of accounting logs to capture
        :type acct_logs: int or None
        :param daemon_logs: number of daemon logs to capture
        :type daemon_logs: int or None
        :param additional_hosts: additional hosts to capture information from
        :type additional_hosts: str or None
        :param map_file: Path to map file for anonymization map
        :type map_file str or None
        :param anonymize: anonymize data?
        :type anonymize: bool
        :param create_tar: Create a tarball of the output snapshot?
        :type create_tar: bool or None
        :param log_path: Path to pbs_snapshot's log file
        :type log_path: str or None
        :param sudo: Capture information with sudo?
        :type sudo: bool
        """
        self.logger = logging.getLogger(__name__)
        self.du = DshUtils()
        self.snap_path = {}
        self.server_info = {}
        self.job_info = {}
        self.node_info = {}
        self.comm_info = {}
        self.hook_info = {}
        self.sched_info = {}
        self.resv_info = {}
        self.pbs_info = {}
        self.sys_info = {}
        self.core_info = {}
        self.datastore_info = {}
        self.anon_obj = None
        self.all_hosts = []
        self.server = None
        self.scheduler = None
        self.log_utils = PBSLogUtils()
        self.outtar_path = None
        self.outtar_fd = None
        self.create_tar = create_tar
        self.snapshot_name = None
        self.sudo = sudo
        self.log_path = log_path
        if self.log_path is not None:
            self.log_filename = os.path.basename(self.log_path)
        else:
            self.log_filename = None

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
        self.all_hosts = []
        if additional_hosts is not None:
            hosts_str = "".join(additional_hosts.split())  # remove whitespaces
            self.all_hosts.extend(hosts_str.split(","))
        self.mapfile = map_file

        # Initialize Server and Scheduler objects
        self.server = Server(server_host)
        self.scheduler = Scheduler(server=self.server)

        # Store paths to PBS_HOME and PBS_EXEC
        self.pbs_home = self.server.pbs_conf["PBS_HOME"]
        self.pbs_exec = self.server.pbs_conf["PBS_EXEC"]

        # Add self.server_host to the list of hosts
        self.server_host = self.server.hostname
        self.all_hosts.append(self.server_host)

        # If output needs to be a tarball, create the tarfile name
        # tarfile name = <output directory name>.tgz
        self.outtar_path = self.snapdir + ".tgz"

        # Set up some infrastructure
        self.__init_cmd_path_map()

        # Create the snapshot directory tree
        self.__initialize_snapshot()

        # Create a PBSAnonymizer object
        self.anonymize = anonymize
        self.custom_rscs = self.server.parse_resources()
        if self.anonymize:
            del_attrs = [ATTR_v, ATTR_e, ATTR_mailfrom, ATTR_m, ATTR_name,
                         ATTR_jobdir, ATTR_submit_arguments, ATTR_o, ATTR_S]
            obf_attrs = [ATTR_euser, ATTR_egroup, ATTR_project, ATTR_A,
                         ATTR_operators, ATTR_managers, ATTR_g, ATTR_M,
                         ATTR_u, ATTR_SvrHost, ATTR_aclgroup, ATTR_acluser,
                         ATTR_aclResvgroup, ATTR_aclResvuser, ATTR_SchedHost,
                         ATTR_aclResvhost, ATTR_aclhost, ATTR_owner,
                         ATTR_exechost, ATTR_NODE_Host, ATTR_NODE_Mom,
                         ATTR_rescavail + ".host", ATTR_rescavail + ".vnode",
                         ATTR_auth_u, ATTR_auth_g, ATTR_resv_owner]
            obf_rsc_attrs = []
            if self.custom_rscs is not None:
                for rsc in self.custom_rscs.keys():
                    obf_rsc_attrs.append(rsc)

            self.anon_obj = PBSAnonymizer(attr_delete=del_attrs,
                                          attr_val=obf_attrs,
                                          resc_key=obf_rsc_attrs)

    def __init_cmd_path_map(self):
        """
        Fill in various dicts which map the commands used for capturing
        various classes of outputs along with the paths to the files where
        they will be stored inside the snapshot as a tuple.
        """
        # Server information
        value = (QSTAT_B_PATH, [QSTAT_CMD, "-B"])
        self.server_info[QSTAT_B_OUT] = value
        value = (QSTAT_BF_PATH, [QSTAT_CMD, "-Bf"])
        self.server_info[QSTAT_BF_OUT] = value
        value = (QMGR_PS_PATH, [QMGR_CMD, "-c", "p s"])
        self.server_info[QMGR_PS_OUT] = value
        value = (QSTAT_Q_PATH, [QSTAT_CMD, "-Q"])
        self.server_info[QSTAT_Q_OUT] = value
        value = (QSTAT_QF_PATH, [QSTAT_CMD, "-Qf"])
        self.server_info[QSTAT_QF_OUT] = value
        value = (QMGR_PR_PATH, [QMGR_CMD, "-c", "p r"])
        self.server_info[QMGR_PR_OUT] = value
        value = (RSCS_PATH, None)
        self.server_info[RSCS_ALL] = value
        value = (SVR_PRIV_PATH, None)
        self.server_info[SVR_PRIV] = value
        value = (SVR_LOGS_PATH, None)
        self.server_info[SVR_LOGS] = value
        value = (ACCT_LOGS_PATH, None)
        self.server_info[ACCT_LOGS] = value

        # Job information
        value = (QSTAT_PATH, [QSTAT_CMD])
        self.job_info[QSTAT_OUT] = value
        value = (QSTAT_F_PATH, [QSTAT_CMD, "-f"])
        self.job_info[QSTAT_F_OUT] = value
        value = (QSTAT_T_PATH, [QSTAT_CMD, "-t"])
        self.job_info[QSTAT_T_OUT] = value
        value = (QSTAT_TF_PATH, [QSTAT_CMD, "-tf"])
        self.job_info[QSTAT_TF_OUT] = value
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

        # Node/MoM information
        value = (PBSNODES_VA_PATH, [PBSNODES_CMD, "-va"])
        self.node_info[PBSNODES_VA_OUT] = value
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
        value = (QMGR_PN_PATH, [QMGR_CMD, "-c", "p n @default"])
        self.node_info[QMGR_PN_OUT] = value
        value = (MOM_PRIV_PATH, None)
        self.node_info[MOM_PRIV] = value
        value = (MOM_LOGS_PATH, None)
        self.node_info[MOM_LOGS] = value

        # Comm information
        value = (COMM_LOGS_PATH, None)
        self.comm_info[COMM_LOGS] = value

        # Hook information
        value = (QMGR_PH_PATH, [QMGR_CMD, "-c", "p h @default"])
        self.hook_info[QMGR_PH_OUT] = value
        value = (QMGR_LPBSHOOK_PATH, [QMGR_CMD, "-c", "l pbshook"])
        self.hook_info[QMGR_LPBSHOOK_OUT] = value

        # Scheduler information
        value = (QMGR_LSCHED_PATH, [QMGR_CMD, "-c", "l sched"])
        self.sched_info[QMGR_LSCHED_OUT] = value
        value = (SCHED_PRIV_PATH, None)
        self.sched_info[SCHED_PRIV] = value
        value = (SCHED_LOGS_PATH, None)
        self.sched_info[SCHED_LOGS] = value

        # Reservation information
        value = (PBS_RSTAT_PATH, [PBS_RSTAT_CMD])
        self.resv_info[PBS_RSTAT_OUT] = value
        value = (PBS_RSTAT_F_PATH, [PBS_RSTAT_CMD, "-f"])
        self.resv_info[PBS_RSTAT_F_OUT] = value

        # Datastore information
        value = (PG_LOGS_PATH, None)
        self.datastore_info[PG_LOGS] = value

        # Core file information
        value = (CORE_SERVER_PATH, None)
        self.core_info[CORE_SERVER] = value
        value = (CORE_SCHED_PATH, None)
        self.core_info[CORE_SCHED] = value
        value = (CORE_MOM_PATH, None)
        self.core_info[CORE_MOM] = value

        # System information
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
        value = (DMESG_PATH, ["dmesg"])
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

        dirs_in_snapshot = [SERVER_DIR, JOB_DIR, NODE_DIR, HOOK_DIR,
                            SCHED_DIR, RESV_DIR, DATASTORE_DIR, CORE_DIR,
                            SYS_DIR, SCHED_PRIV_PATH, SVR_PRIV_PATH,
                            MOM_PRIV_PATH, ACCT_LOGS_PATH, COMM_LOGS_PATH,
                            SVR_LOGS_PATH, SCHED_LOGS_PATH, MOM_LOGS_PATH]
        for item in dirs_in_snapshot:
            rel_path = os.path.join(self.snapdir, item)
            os.makedirs(rel_path, 0755)

    def __capture_cmd_output(self, host, out_path, cmd, skip_anon=False,
                             as_script=False):
        """
        Run a command on the host specified and capture its output

        :param host: the host to run the command on
        :type host: str
        :param out_path: path of the output file for this command
        :type out_path: str
        :param cmd: The command to execute
        :type cmd: list
        :param skip_anon: Skip anonymization even though anonymize is True?
        :type skip_anon: bool
        """
        if "qmgr" in cmd[0]:
            # qmgr -c is being called
            if not self.du.is_localhost(host):
                # For remote hosts, wrap qmgr's command in quotes
                cmd[2] = "\'" + cmd[2] + "\'"

        with open(out_path, "w") as out_fd:
            self.du.run_cmd(host, cmd=cmd, stdout=out_fd,
                            sudo=self.sudo, as_script=as_script)

            if self.anonymize and not skip_anon:
                self.__anonymize_file(out_path)

        if self.create_tar:
            self.__add_to_archive(out_path)

    def __convert_flag_to_numeric(self, flag):
        """
        Convert a resource's flag attribute to its numeric equivalent

        :param flag: the resource flag to convert
        :type flag: string

        :returns: numeric value of the resource flag
        """
        ATR_DFLAG_USRD = 0x01
        ATR_DFLAG_USWR = 0x02
        ATR_DFLAG_OPRD = 0x04
        ATR_DFLAG_OPWR = 0x08
        ATR_DFLAG_MGRD = 0x10
        ATR_DFLAG_MGWR = 0x20
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
        if "r" in flag:
            resc_flag &= ~READ_WRITE
            resc_flag |= NO_USER_SET
        if "i" in flag:
            resc_flag &= ~READ_WRITE
            resc_flag |= (ATR_DFLAG_OPRD | ATR_DFLAG_OPWR |
                          ATR_DFLAG_MGRD | ATR_DFLAG_MGWR)
        return resc_flag

    def __convert_type_to_numeric(self, attr_type):
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
        gdb.execute("core %s")
        o = gdb.execute("thread apply all bt", to_string=True)
        print(o)
        gdb.execute("quit")
        quit()
        """ % (core_file_name)
        # Remove tabs from triple quoted strings
        gdb_python = gdb_python.replace("\t", "")

        # Open a temporary file to write the gdb-python script above
        fd, fn = self.du.mkstemp(mode=0755)
        with os.fdopen(fd, "w") as tempfd:
            tempfd.write(gdb_python)

        # Catch the stack trace using gdb
        gdb_cmd = ["gdb", exec_path, "-P", fn]
        with open(out_path, "w") as outfd:
            self.du.run_cmd(gdb_cmd, stdout=outfd, stderr=STDOUT)

        # Remove the temp file
        os.remove(fn)

        if self.create_tar:
            self.__add_to_archive(out_path)

    def __capture_logs(self, host, pbs_logdir, snap_logdir, num_days_logs):
        """
        Capture specific logs from host mentioned, for the days mentioned

        :param host: name of the host to get the logs from
        :type host: str
        :param pbs_logdir: path to the PBS logs directory (source)
        :type pbs_logdir: str
        :param snap_logdir: path to the snapshot logs directory (destination)
        :type snap_logdir: str
        :param num_days_logs: Number of days of logs to capture
        :type num_days_logs: int
        """

        end_time = self.server.ctime
        start_time = end_time - ((num_days_logs - 1) * 24 * 60 * 60)

        # Get the list of log file names to capture
        pbs_logfiles = self.log_utils.get_log_files(host, pbs_logdir,
                                                    start=start_time,
                                                    end=end_time)
        if len(pbs_logfiles) == 0:
            self.logger.debug(pbs_logdir + "not found/accessible on " + host)
            return

        self.logger.debug("Capturing " + str(num_days_logs) +
                          " days of logs from " + host + "( " + pbs_logdir +
                          ")")

        # For remote hosts, we need to prefix the
        # log path with the hostname
        if not self.du.is_localhost(host):
            prefix = host + ":"
            # Make sure that the target, host specific log dir exists
            if not os.path.isdir(snap_logdir):
                os.makedirs(snap_logdir)
        else:
            prefix = ""

        # Go over the list and copy over each log file
        for pbs_logfile in pbs_logfiles:
            snap_logfile = os.path.join(snap_logdir,
                                        os.path.basename(pbs_logfile))
            pbs_logfile = prefix + pbs_logfile
            self.du.run_copy(src=pbs_logfile, dest=snap_logfile,
                             sudo=self.sudo)

            # Anonymize accounting logs
            if self.anonymize and "accounting" in snap_logdir:
                anon = self.anon_obj.anonymize_accounting_log(snap_logfile)
                if anon is not None:
                    anon_fd = open(snap_logfile, "w")
                    anon_fd.write("\n".join(anon))
                    anon_fd.close()

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
        if not os.path.isfile(file_path):
            return False

        file_header = magic.from_file(file_path)
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
        self.__capture_trace_from_core(file_path, exec_name,
                                       core_dest)

        # Delete the core file itself
        if os.path.isfile(file_path):
            os.remove(file_path)

        return True

    def __anonymize_file(self, file_path):
        """
        Anonymize/obfuscate a file to remove sensitive information

        :param file_path: path to the file to anonymize
        :type file_path: str
        """
        if not self.anonymize or self.anon_obj is None:
            return

        self.logger.debug("Anonymizing " + file_path)

        file_name = os.path.basename(file_path)
        if file_name == "sched_config":
            self.anon_obj.anonymize_sched_config(self.scheduler)
            self.scheduler.apply_config(path=file_path, validate=False)
        elif file_name == "resource_group":
            anon = self.anon_obj.anonymize_resource_group(file_path)
            if anon is not None:
                with open(file_path, "w") as rgfd:
                    rgfd.write("\n".join(anon))
        elif file_name in FILE_TABULAR:
            self.anon_obj.anonymize_file_tabular(file_path, inplace=True)
        else:
            self.anon_obj.anonymize_file_kv(file_path, inplace=True)

    def __copy_dir_with_core(self, host, src_path, dest_path, core_dir,
                             except_list=None, only_core=False):
        """
        Copy over a directory recursively which might have core files
        When a core file is found, capture the stack trace from it

        :param host: name of the host where the source is located
        :type host: str
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
        """
        if except_list is None:
            except_list = []

        dir_list = self.du.listdir(host, src_path, fullpath=False,
                                   sudo=self.sudo)

        if dir_list is None:
            self.logger.info("Can't find/access " + src_path + " on host " +
                             host)
            return

        # Go over the list and copy over everything
        # If we find a core file, we'll store backtrace from it inside
        # core_file_bt
        if not self.du.is_localhost(host):
            prefix = host + ":"
        else:
            prefix = ""

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
            if self.du.isdir(host, item_src_path, sudo=self.sudo):
                # Make sure that the directory exists in the snapshot
                if not self.du.isdir(item_dest_path):
                    # Create the directory
                    os.makedirs(item_dest_path, 0755)
                # Recursive call to copy contents of the directory
                self.__copy_dir_with_core(host, item_src_path, item_dest_path,
                                          core_dir, except_list, only_core)
            else:
                # Copy the file over
                item_src_path = prefix + item_src_path
                self.du.run_copy(src=item_src_path, dest=item_dest_path,
                                 recursive=False, mode=0755,
                                 level=logging.DEBUG, sudo=self.sudo)

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
                    # So, we need to capture & anonymize this file
                    self.__anonymize_file(item_dest_path)
                    if self.create_tar:
                        self.__add_to_archive(item_dest_path)

    def __capture_mom_priv(self, host):
        """
        Capture mom_priv information from the host given

        :param host: name of the host
        :type host: str
        """
        if host != self.server_host:
            # Get path to PBS_HOME on this host
            host_pbs_config = self.du.parse_pbs_config(hostname=host)
            if "PBS_HOME" not in host_pbs_config.keys():
                self.logger.info("PBS_HOME not found on host " + host)
                return
            pbs_home = host_pbs_config["PBS_HOME"]
        else:
            pbs_home = self.pbs_home

        snap_mom_priv = os.path.join(self.snapdir, MOM_PRIV_PATH)
        if host != self.server_host:
            snap_mom_priv = os.path.join(snap_mom_priv, host)
            os.makedirs(snap_mom_priv, 0755)

        pbs_mom_priv = os.path.join(pbs_home, "mom_priv")

        core_dir = os.path.join(self.snapdir, CORE_MOM_PATH)
        if host != self.server_host:
            core_dir = os.path.join(core_dir, host)

        # Copy mom_priv over from the host
        self.__copy_dir_with_core(host, pbs_mom_priv, snap_mom_priv, core_dir)

    def __add_to_archive(self, dest_path):
        """
        Add a file to the output tarball and delete the original file

        :param dest_path: path to the file inside the target tarball
        :type dest_path: str
        """
        # pbs_snapshot's log file is located outside of the snapshot
        # handle it separately
        if os.path.basename(dest_path) == self.log_filename:
            src_path = self.log_path
        else:
            src_path = dest_path

        self.logger.debug("Adding " + src_path + " to tarball " +
                          self.outtar_path)

        # Add file to tar
        dest_relpath = os.path.relpath(dest_path, self.snapdir)
        path_in_tar = os.path.join(self.snapshot_name, dest_relpath)
        self.outtar_fd.add(src_path, arcname=path_in_tar)

        # Remove original file
        os.remove(src_path)

    def __capture_svr_logs(self):
        """
        Capture server logs
        """
        pbs_logdir = os.path.join(self.pbs_home, "server_logs")
        snap_logdir = os.path.join(self.snapdir, SVR_LOGS_PATH)
        self.__capture_logs(self.server_host, pbs_logdir, snap_logdir,
                            self.num_daemon_logs)

    def __capture_acct_logs(self):
        """
        Capture accounting logs
        """
        pbs_logdir = os.path.join(self.pbs_home, "server_priv", "accounting")
        snap_logdir = os.path.join(self.snapdir, ACCT_LOGS_PATH)
        self.__capture_logs(self.server_host, pbs_logdir, snap_logdir,
                            self.num_acct_logs)

    def __capture_sched_logs(self):
        """
        Capture scheduler logs
        """
        pbs_logdir = os.path.join(self.pbs_home, "sched_logs")
        snap_logdir = os.path.join(self.snapdir, SCHED_LOGS_PATH)
        self.__capture_logs(self.scheduler.hostname, pbs_logdir,
                            snap_logdir, self.num_daemon_logs)

    def __capture_mom_logs(self, host):
        """
        Capture mom logs for the host specified
        """
        if host != self.server_host:
            # Get path to PBS_HOME on this host
            host_pbs_config = self.du.parse_pbs_config(hostname=host)
            if "PBS_HOME" not in host_pbs_config.keys():
                self.logger.info("PBS_HOME not found on host " + host)
                return
            pbs_home = host_pbs_config["PBS_HOME"]
        else:
            pbs_home = self.pbs_home

        pbs_logdir = os.path.join(pbs_home, "mom_logs")
        snap_logdir = os.path.join(self.snapdir, MOM_LOGS_PATH)
        if host != self.server_host:
            snap_logdir = os.path.join(snap_logdir, host)
        self.__capture_logs(host, pbs_logdir, snap_logdir,
                            self.num_daemon_logs)

    def __capture_comm_logs(self, host):
        """
        Capture pbs_comm logs from the host specified
        """
        if host != self.server_host:
            # Get path to PBS_HOME on this host
            host_pbs_config = self.du.parse_pbs_config(hostname=host)
            if "PBS_HOME" not in host_pbs_config.keys():
                self.logger.info("PBS_HOME not found on host " + host)
                return
            pbs_home = host_pbs_config["PBS_HOME"]
        else:
            pbs_home = self.pbs_home

        # Capture comm_logs
        pbs_logdir = os.path.join(pbs_home, "comm_logs")
        snap_logdir = os.path.join(self.snapdir, COMM_LOGS_PATH)
        if host != self.server_host:
            snap_logdir = os.path.join(snap_logdir, host)
        self.__capture_logs(host, pbs_logdir, snap_logdir,
                            self.num_daemon_logs)

    def __capture_rscs_all(self):
        """
        Capture built-in as well as custom resources in a file called
        'rscs_all'
        """
        # Parse all custom resources
        resources = self.server.parse_resources()
        custom_rscs_names = None
        if resources is not None:
            # Convert type and flags to their numeric format
            for rsc in resources.values():
                if rsc.type:
                    rsc.set_type(self.__convert_type_to_numeric(rsc.type))
                if rsc.flag:
                    rsc.set_flag(str(self.__convert_flag_to_numeric(rsc.flag)))

            custom_rscs_names = resources.keys()

            # anonymize custom resources
            if self.anonymize and self.anon_obj.resc_key is not None:
                self.logger.debug("Anonymizing custom resources")
                resources = self.anon_obj.anonymize_resource_def(resources)
                custom_rscs_names = resources.keys()

        if custom_rscs_names is None:
            custom_rscs_names = []

        # The resourcedef file doesn't define the built-in resources.
        # Use the build-ins specified in the string "BUILT_IN_RSCS"
        # This string should be updated with each release PBSPro or
        # a better way of querying built-ins should be implemented
        builtin_rscs_str = BUILT_IN_RSCS

        # Write out resources in the following format:
        # Name: <resource id>
        #     type = <resource type>
        #     flag = <resource flag>
        self.logger.debug("capturing all resources in \"rscs_all\"")
        snap_rscs = os.path.join(self.snapdir, RSCS_PATH)
        with open(snap_rscs, "w") as rscfd:
            # Write out the built-in resources
            rscfd.write(builtin_rscs_str)

            # Write out the custom resources
            for rsc in custom_rscs_names:
                rsc_obj = resources[rsc]
                rsc_str = "Name: " + rsc_obj.attributes['id']
                rsc_str += "\n    type = " + str(rsc_obj.attributes['type'])
                rsc_str += "\n    flag = " + str(rsc_obj.attributes['flag'])
                rscfd.write(rsc_str + "\n")

        if self.create_tar:
            self.__add_to_archive(snap_rscs)

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

        # Go through 'server_info' and capture info that depends on commands
        for (path, cmd_list) in self.server_info.values():
            if cmd_list is None:
                continue
            cmd_list_cpy = list(cmd_list)

            # Add the path to PBS_EXEC to the command path
            # The command path is the first entry in command list
            cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
            snap_path = os.path.join(self.snapdir, path)
            self.__capture_cmd_output(self.server_host, snap_path,
                                      cmd_list_cpy)

        # Copy over 'server_priv', everything except accounting logs
        snap_server_priv = os.path.join(self.snapdir, SVR_PRIV_PATH)
        pbs_server_priv = os.path.join(self.pbs_home, "server_priv")
        core_dir = os.path.join(self.snapdir, CORE_SERVER_PATH)
        exclude_list = ["accounting"]
        self.__copy_dir_with_core(self.server_host, pbs_server_priv,
                                  snap_server_priv, core_dir, exclude_list)

        if with_svr_logs and self.num_daemon_logs > 0:
            # Capture server logs
            self.__capture_svr_logs()

        if with_acct_logs and self.num_acct_logs > 0:
            # Capture accounting logs
            self.__capture_acct_logs()

        # Capture built-in + custom resources
        self.__capture_rscs_all()

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

        # Go through 'job_info' and capture info that depends on commands
        for (path, cmd_list) in self.job_info.values():
            cmd_list_cpy = list(cmd_list)

            # Add the path to PBS_EXEC to the command path
            # The command path is the first entry in command list
            cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
            snap_path = os.path.join(self.snapdir, path)
            self.__capture_cmd_output(self.server_host, snap_path,
                                      cmd_list_cpy)

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

        # Go through 'node_info' and capture info that depends on commands
        for (path, cmd_list) in self.node_info.values():
            if cmd_list is None:
                continue
            cmd_list_cpy = list(cmd_list)

            # Add the path to PBS_EXEC to the command path
            # The command path is the first entry in command list
            cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
            snap_path = os.path.join(self.snapdir, path)
            self.__capture_cmd_output(self.server_host, snap_path,
                                      cmd_list_cpy)

        if len(self.all_hosts) == 0:
            self.all_hosts.append(self.server_host)

        # Go through the list of all hosts specified and collect mom info
        for host in self.all_hosts:
            # Capture mom_priv info
            self.__capture_mom_priv(host)

            if with_mom_logs and self.num_daemon_logs > 0:
                # Capture mom_logs
                self.__capture_mom_logs(host)

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

        if len(self.all_hosts) == 0:
            self.all_hosts.append(self.server_host)

        # Go through the list of all hosts specified and collect comm info
        for host in self.all_hosts:
            if self.num_daemon_logs > 0 and with_comm_logs:
                self.__capture_comm_logs(host)

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

        # Go through 'sched_info' and capture info that depends on commands
        for (path, cmd_list) in self.sched_info.values():
            if cmd_list is None:
                continue
            cmd_list_cpy = list(cmd_list)

            # Add the path to PBS_EXEC to the command path
            # The command path is the first entry in command list
            cmd_list_cpy[0] = os.path.join(self.pbs_exec, cmd_list[0])
            snap_path = os.path.join(self.snapdir, path)
            self.__capture_cmd_output(self.scheduler.hostname, snap_path,
                                      cmd_list_cpy)

        # Capture 'sched_priv'
        snap_sched_priv = os.path.join(self.snapdir, SCHED_PRIV_PATH)
        pbs_sched_priv = os.path.join(self.scheduler.pbs_conf["PBS_HOME"],
                                      "sched_priv")
        core_dir = os.path.join(self.snapdir, CORE_SCHED_PATH)
        self.__copy_dir_with_core(self.scheduler.hostname, pbs_sched_priv,
                                  snap_sched_priv, core_dir)

        if with_sched_logs and self.num_daemon_logs > 0:
            # Capture scheduler logs
            self.__capture_sched_logs()

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
            self.__capture_cmd_output(self.server_host, snap_path,
                                      cmd_list_cpy)

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
            self.__capture_cmd_output(self.server_host, snap_path,
                                      cmd_list_cpy)

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
            pbs_logdir = os.path.join(self.pbs_home, "datastore", "pg_log")
            snap_logdir = os.path.join(self.snapdir, PG_LOGS_PATH)
            self.__capture_logs(self.server_host, pbs_logdir, snap_logdir,
                                self.num_daemon_logs)

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

        # Go over all the hosts specified
        for host in self.all_hosts:
            host_platform = self.du.get_platform(host)
            win_platform = False
            if host_platform.startswith("win"):
                win_platform = True

            # Capture information that's dependent on commands
            for (key, values) in self.sys_info.iteritems():
                (path, cmd_list) = values
                if cmd_list is None:
                    continue
                # For Windows, only capture pbs_probe and pbs_hostn
                if win_platform and (key not in
                                     [PBS_PROBE_OUT, PBS_HOSTN_OUT]):
                    continue

                cmd_list_cpy = list(cmd_list)
                # Find the full path to the command on the host
                if key in [PBS_PROBE_OUT, PBS_HOSTN_OUT]:
                    cmd_full = os.path.join(self.pbs_exec, cmd_list[0])
                else:
                    cmd_full = self.du.which(host, cmd_list[0])
                # du.which() returns the name of the command passed if
                # it can't find the command
                if cmd_full is cmd_list[0]:
                    continue
                cmd_list_cpy[0] = cmd_full

                # Handle special commands
                if "pbs_hostn" in cmd_list[0]:
                    # Append hostname to the command list
                    cmd_list_cpy.append(self.server_host)
                if key in [PROCESS_INFO, LSOF_PBS_OUT]:
                    as_script = True
                else:
                    as_script = False

                snap_path = os.path.join(self.snapdir, path)
                self.__capture_cmd_output(host, snap_path, cmd_list_cpy,
                                          skip_anon=True, as_script=as_script)

            # Capture platform dependent information
            if win_platform:
                # Capture process information using tasklist command
                cmd = ["tasklist", ["/v"]]
                snap_path = PROCESS_PATH
                self.__capture_cmd_output(host, snap_path, cmd)

            # Capture OS/platform information
            self.logger.info("capturing OS information")
            snap_ospath = os.path.join(self.snapdir, OS_PATH)
            with open(snap_ospath, "w") as osfd:
                osinfo = self.du.get_os_info(host)
                osfd.write(osinfo)
            if self.create_tar:
                self.__add_to_archive(snap_ospath)

            # Capture pbs_environment
            self.logger.info("capturing pbs_environment")
            snap_envpath = os.path.join(self.snapdir, PBS_ENV_PATH)
            if self.server.pbs_env is not None:
                with open(snap_envpath, "w") as envfd:
                    for k, v in self.server.pbs_env.iteritems():
                        envfd.write(k + "=" + v + "\n")
            if self.create_tar:
                self.__add_to_archive(snap_envpath)

        if self.create_tar:
            return self.outtar_path
        else:
            return self.snapdir

    def capture_pbs_logs(self):
        """
        Capture PBSPro logs from all relevant hosts

        :returns: name of the output directory/tarfile containing the snapshot
        """
        self.logger.info("capturing PBSPro logs")

        if self.num_daemon_logs > 0:
            # Capture server logs
            self.__capture_svr_logs()

            # Capture scheduler logs
            self.__capture_sched_logs()

            # Capture mom & comm logs for all the known hosts
            for host in self.all_hosts:
                self.__capture_mom_logs(host)
                self.__capture_comm_logs(host)

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

        # Print out obfuscation map
        if self.anonymize and (self.mapfile is not None):
            try:
                with open(self.mapfile, "w") as mapfd:
                    mapfd.write(str(self.anon_obj))
            except Exception:
                self.logger.error("Error writing out the map file " +
                                  self.mapfile)

        # Record timestamp of the snapshot
        snap_ctimepath = os.path.join(self.snapdir, CTIME_PATH)
        with open(snap_ctimepath, "w") as ctimefd:
            ctimefd.write(str(self.server.ctime) + "\n")
        if self.create_tar:
            self.__add_to_archive(snap_ctimepath)

        # If the caller was pbs_snapshot, add its log file to the tarball
        if self.create_tar and self.log_path is not None:
            snap_logpath = os.path.join(self.snapdir, self.log_filename)
            self.__add_to_archive(snap_logpath)

        # Cleanup
        if self.create_tar:
            # Close the output tarfile
            self.outtar_fd.close()
            # Remove the snapshot directory
            self.du.rm(path=self.snapdir, recursive=True, force=True,
                       sudo=True)

# coding: utf-8
#
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


"""
Purpose:

- Force PBS to refresh nodes information when PBS and ALPS get out of
  sync.

Requirements:

- PBS Pro vnodes created in qmgr must be named after a locally-valid
  alias for each login node.

 Some enhanced operations in a multi-Cray or mixed Cray/non-Cray
 environment with an external server:

    1) Determine my node's cray host value by reading /etc/xthostname.
    2) Only compile lists of compute and login nodes whose PBScrayhost
       resource matches my crayhost value.
    3) Current host always validates itself against the first "up"
       Cray login node. This prevents non-Cray nodes from attempting
       obtain an ALPS inventory in cases where there is only one
       Cray login node. To facilitate this, we've a list,
       cray_login_list.
    4) Rather than attempting to index into the list of Cray login
       nodes (which fails with a spurious error message if the hook
       is running on a non-Cray node in a mixed environment, or if
       the vnode name of the host does not match the default hostname
       of the node), check all local aliases for this node against the
       vnode name of the first "up" Cray login node to determine
       whether to proceed.
    5) Check that the PBScraynid resource is defined before attempting
       to add a node's PBScraynid to the nid list. This prevents the
       hook from failing on a conversion error if a site sets the
       vntype resource on a non_Cray node.
    6) A compute node that is offlined in PBS, but still preset as a
       batch node in ALPS, would cause a false inventory mismatch
       since only "up" nodes were included in the pbs_nids_set. This
       would in turn cause the hook to HUP inventory MoM every cycle.
       It's perfectly reasonable for an Admin to offline a node
       without necessarily downing it in ALPS. We deal with this by:
       a) treating node states as a bitmask rather than as a set of
          integer values
       b) distinguishing between "down" states ("down", "unknown",
          "stale") and offline
       c) excluding down or offline login nodes from consideration as
          the inventory MoM
       d) special-casing offline compute nodes by removing their nids
          from the apstat_nids_set if present and excluding them from
          the pbs_nids_set. This essentially means that we don't care
          whether an offline node is present in ALPS or not.
    7) When we check to see whether the current node matches the
       inventory MoM, we actually resolve the inventory MoM and see
       if its IP matches a valid IP from the current node . This allows
       the hook to continue to work even if a site changes the default
       hostname of a MoM node after installation.
"""

import pbs
import time
import sys
import os
import re
import socket
import fcntl
import struct
from signal import SIGHUP
from subprocess import Popen, PIPE

XTHOSTNAME = "/etc/xthostname"
APSTAT_CMD = "/opt/cray/alps/default/bin/apstat"
SIOCGIFADDR = 0x8915


def get_mom_home():
    """
    Return the path to the PBS home directory
    """

    for v in ("PBS_MOM_HOME", "PBS_HOME"):
        if v in os.environ:
            return os.environ[v]

    home = None
    conf_file = os.environ.get("PBS_CONF_FILE", "/etc/pbs.conf")
    with open(conf_file) as conf:
        for line in conf:
            (key, val) = line.strip().split("=")
            if key == "PBS_MOM_HOME":
                home = val
                # PBS_MOM_HOME takes priority over PBS_HOME, so we are done
                # searching
                break
            elif key == "PBS_HOME":
                home = val

    if not home.strip():
        return None

    return home

def hup_mom():
    PBS_MOM_HOME = get_mom_home()
    pidfile = open(os.path.join(PBS_MOM_HOME, "mom_priv", "mom.lock"))
    pid = int(pidfile.readline())
    pidfile.close()
    os.kill(pid, SIGHUP)

def get_apstat_nids(msg):
    """
    Returns the number of nodes reported by ALPS as marked "up" and of type
    "batch".

    Sample output of the command 'apstat -rn':

    NID Arch State HW Rv Pl  PgSz     Avl    Conf Placed PEs Apids
    2   XT UP  B 16  -  -    4K 4194304       0      0   0
    3   XT UP  B 16  -  -    4K 4194304       0      0   0
    """

    if not os.path.isfile(APSTAT_CMD):
        msg += ["ALPS Inventory Check: apstat command can not be found at %s" %
                (APSTAT_CMD)]
        return None

    apstat_nids = set()
    cmd_apstat = APSTAT_CMD + " -nv"
    apstat_out = Popen(cmd_apstat, shell=True, stdout=PIPE)

    if apstat_out.wait() != 0 or apstat_out is None:
        msg += ["ALPS Inventory Check: No nodes reported by apstat."]
        hup_mom()
        __exit_hook(1, msg)

    pattern = re.compile(
        "(?P<nid>.+?)\s+(?P<arch>.+?)\s+(?P<state>.+?)\s+" +
        "(?P<hw>.+?)\s+(?P<everything>.+)")

    for apstat_line in apstat_out.stdout:
        apstat_line = apstat_line.strip()

        apstat_record = re.search(pattern, apstat_line)

        if apstat_record:
            if apstat_record.group('state') == "UP" and \
                    apstat_record.group('hw') == "B":
                apstat_nids.add(int(apstat_record.group('nid')))

    return apstat_nids


def flush_log_messages(msg=None):
    """
    Prints msg to the log file
    """
    if msg is not None:
        for m in msg:
            pbs.logmsg(pbs.LOG_DEBUG, m)


def __exit_hook(code=0, msg=None):
    flush_log_messages(msg)
    sys.exit(code)


def my_addresses():
    """ produces a list of ip strings for each network interface """

    for ifname in os.listdir('/sys/class/net'):
        if ifname == 'lo':
            continue

        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack('256s', ifname[:15])

        try:
            sockaddr_in = fcntl.ioctl(test_socket.fileno(),
                                      SIOCGIFADDR,
                                      ifreq)[20:24]
        except IOError:
            continue

        yield socket.inet_ntoa(sockaddr_in)


cray_login_list = []
offline_nids_list = []
pbs_nids_set = set()
now_mn = int(time.strftime("%M", time.gmtime()))
msg = []

if not os.path.isfile(XTHOSTNAME):
    msg += ["No %s file found on this host." % (XTHOSTNAME)]
    __exit_hook(0, msg)

# XTHOSTNAME file found on this host. Read it to determine our Cray hostname.

with open(XTHOSTNAME) as xthost_file:
    my_crayhost = xthost_file.readline()
    my_crayhost = my_crayhost.rstrip()
    msg += ["Processing ALPS inventory for crayhost %s" % (my_crayhost)]

start = time.time()
vnodes = pbs.server().vnodes()
vnodes_query_duration = time.time() - start
if not vnodes:
    msg += ["ALPS Inventory Check: No vnodes reported by PBS"]
    __exit_hook(1, msg)

down_states = pbs.ND_DOWN | pbs.ND_STALE | pbs.ND_STATE_UNKNOWN

for v in vnodes:
    str_v = str(v)
    vntype = " "

    if (v.state & down_states) or \
        "PBScrayhost" not in v.resources_available or \
            v.resources_available["PBScrayhost"] != my_crayhost:
        continue

    if "vntype" in v.resources_available:
        vntype = v.resources_available["vntype"]

    if vntype == "cray_login":
        if (not (v.state & pbs.ND_OFFLINE)) and \
                str_v not in cray_login_list:
            cray_login_list.append(str_v)

    elif vntype == "cray_compute":

        if "PBScraynid" in v.resources_available:
            pbs_craynid = v.resources_available["PBScraynid"]

        if pbs_craynid.isdigit():
            if (v.state & pbs.ND_OFFLINE):

                # if vnode is offline, add it to offline_nids_list.
                # Otherwise, add it to the pbs_nids_set.
                # Later on, the inventory MoM sill iterate through the
                # offline_nids_list and discard those nids from the
                # apstat_nids_set. This has the effect of causing us
                # to ignore any offline nids so we won't generate a
                # spurious HUP of the MoM if there are offline vnodes
                # whose nids are present in the apstat output. We use
                # the set.discard() method because it doesn't throw an
                # error if the nid isn't present in the apstat_nids_set.

                offline_nids_list.append(int(pbs_craynid))
            else:
                pbs_nids_set.add(int(pbs_craynid))

if len(cray_login_list) == 0:
    msg += ["ALPS Inventory Check: No eligible " +
            "login nodes to perform inventory check"]
    __exit_hook(0, msg)

cray_login_local_name = pbs.get_local_nodename()

try:
    inventory_node = cray_login_list[0]
    inventory_addr = socket.gethostbyname(inventory_node)

    if ((inventory_addr not in my_addresses()) and (
            inventory_node != cray_login_local_name)):
        msg += ["ALPS Inventory Check: Login node '%s' is in charge of "
                "verification, skipping check on '%s'." %
                (inventory_node, socket.gethostname())]
        __exit_hook(0, msg)

    start = time.time()
    apstat_nids_set = get_apstat_nids(msg)
    apstat_query_duration = time.time() - start

    if apstat_query_duration > 1 or vnodes_query_duration > 1:
        msg += ["ALPS Inventory Check: apstat query: %ds pbsnodes query: %ds" %
                (apstat_query_duration, vnodes_query_duration)]

#  Remove any offline nids from the apstat_nids_set.
    for offline_nid in offline_nids_list:
        apstat_nids_set.discard(offline_nid)

    pbs_apstat_diff = pbs_nids_set.difference(apstat_nids_set)
    apstat_pbs_diff = apstat_nids_set.difference(pbs_nids_set)

    if apstat_pbs_diff:
        msg += ["ALPS Inventory Check: Compute " +
                "node%s defined in ALPS, but not in PBS: %s" %
                (['', "s"][len(apstat_pbs_diff) > 0],
                 ",".join(str(n) for n in apstat_pbs_diff))]

    if pbs_apstat_diff:
        msg += ["ALPS Inventory Check: Compute " +
                "node%s defined in PBS, but not in ALPS: %s" %
                (['', "s"][len(pbs_apstat_diff) > 0],
                 ",".join(str(n) for n in pbs_apstat_diff))]

    if apstat_pbs_diff or pbs_apstat_diff:
        PBS_MOM_HOME = get_mom_home()
        if PBS_MOM_HOME is not None:
            flush_log_messages(msg)
            hup_mom()
            sys.exit(0)
        else:
            msg += ["ALPS Inventory Check: Internal error in retrieving path "
                    "to mom_priv"]
    else:
        msg += ["ALPS Inventory Check: PBS and ALPS are in sync"]

    flush_log_messages(msg)

except SystemExit:
    pass
except BaseException:
    msg += ["ALPS Inventory Check: Failure in refreshing "
            "nodes on login node (%s) " % (cray_login_local_name)]
    __exit_hook(1, msg)

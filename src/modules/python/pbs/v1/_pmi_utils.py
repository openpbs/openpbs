"""

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
__doc__ = """
$Id$
Utility power functions.
"""

import pbs
import os
import sys


def _pbs_conf(confvar):
    # Return the value of a setting in the pbs.conf file if it exists.
    # Save the values in a global dictionary for future use.

    if confvar in os.environ:
        return os.environ[confvar]

    global pmi_pbsconf
    if "pmi_pbsconf" not in globals():
        pmi_pbsconf = dict()
        cfile = "PBS_CONF_FILE"
        if cfile in os.environ:
            pbsconf = os.environ[cfile]
        else:
            pbsconf = "/etc/pbs.conf"

        try:
            fp = open(pbsconf)
        except:
            pbs.logmsg(pbs.DEBUG, "%s: Unable to open conf file." % pbsconf)
            return None 
        else:
            for line in fp:
                line = line.strip()
                # ignore empty lines or those beginning with '#'
                if line == "" or line[0] == "#":
                    continue
                var, eq, val = line.partition('=')
                if val == "":
                    continue
                pmi_pbsconf[var] = val
            fp.close()
    if confvar in pmi_pbsconf:
        return pmi_pbsconf[confvar]
    else:
        return None


def _is_node_provisionable():
    """
    Check if the local machine is running pbs_server or
    pbs_sched or pbs_comm. If any of these are running, provisioning
    must not be automatically enabled.
    """
    serv = _pbs_conf("PBS_START_SERVER")
    if serv is not None and serv == "1":
        return False

    sched = _pbs_conf("PBS_START_SCHED")
    if sched is not None and sched == "1":
        return False

    comm = _pbs_conf("PBS_START_COMM")
    if comm is not None and comm == "1":
        return False

    return True


def _get_hosts(job):
    """
    Form a list of unique short hostnames from a pbs job.
    The short names are used even if the hostnames from exec_host2
    are FQDNs because SGIMC seems to have a bug in that it will
    not accept FQDNs.
    """
    hosts = str(job.exec_host2)
    pbs_nodes = sorted({x.partition(':')[0].partition('.')[0]
                            for x in hosts.split('+')})
    return pbs_nodes


def _jobreq(job, name):
    """
    Get a requested resource from a job.
    """
    val = str(job.schedselect).partition(name + '=')[2]
    if len(val) == 0:
        return None
    else:
        return val.partition('+')[0].partition(':')[0]


def _get_vnode_names(job):
    """
    Return a list of vnodes being used for a job.
    """
    exec_vnode = str(job.exec_vnode).replace("(", "").replace(")", "")
    vnodes = sorted({x.partition(':')[0]
                        for x in exec_vnode.split('+')})
    return vnodes


def _svr_vnode(name):
    # Return a vnode object obtained from the server by name.
    # Save the values in a global dictionary for future use.
    global pmi_pbsconf
    if "pmi_pbsvnodes" not in globals():
        global pmi_pbsvnodes
        pmi_pbsvnodes = dict()
        for vn in pbs.server().vnodes():
            pmi_pbsvnodes[vn.name] = vn
    return pmi_pbsvnodes[name]


def _running_excl(job):
    # Look for any other job that is running on a job's vnodes
    for vname in _get_vnode_names(job):
        vnode = _svr_vnode(vname)
        for j in str(vnode.jobs).split(', '):
            id = j.partition('/')[0]
            if job.id != id:
                return False
    return True

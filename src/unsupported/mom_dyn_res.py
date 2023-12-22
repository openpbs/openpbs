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

# A hook script that periodically updates the values of a set of

# custom resources for the vnode representing the current mom.
#
# The current set includes 2 size types: scratch, home
#
# Prerequisites:
#
#    1. Define the following custom resources in server's resourcedef file, and
#       restart pbs_server.
#
#       % cat PBS_HOME/server_priv/resourcedef
#           scratch type=size flag=nh
#           home type=size flag=nh
#
#    2. Add the new resources to the "resources:" line in sched_config file and
#       restart pbs_sched:
#
#       % cat PBS_HOME/sched_priv/sched_config
#           resources: ncpus, mem, arch, [...], scratch, home
#
#    3. Install this hook as:
#       qmgr -c "create hook mom_dyn_res event=exechost_periodic,freq=30"
#       qmgr -c "import hook mom_dyn_res application/x-python default
#                mom_dyn_res.py"
#
# NOTE:
#    Update the dyn_res[] array below to include any other custom resources
#    to be included in the updates. Ensure that each resource added has an
#    entry in the server's resourcedef file and scheduler's sched_config file.

import os

import pbs


# get_filesystem_avail_unprivileged: returns available size in kbytes
# (in pbs.size type) to unprivileged users, of the filesystem where 'dirname'
# resides.
#
def get_filesystem_avail_unprivileged( dirname ):
    o = os.statvfs(dirname)
    return pbs.size( "%skb" % ((o.f_bsize * o.f_bavail) / 1024) )

# get_filesystem_avail_privileged: returns available size in kbytes
# (in pbs.size type) to privileged users, of the filesystem where 'dirname'
# resides.
#
def get_filesystem_avail_privileged( dirname ):
    o = os.statvfs(dirname)
    return pbs.size( "%skb" % ((o.f_bsize * o.f_bfree) / 1024) )


# Define here the custom resources as key, and the function and its argument
# for obtaining the value of the custom resource:
#    Format: dyn_res[<resource_name>] = [<function_name>, <function_argument>]
# So "<function_name>(<function_argument>)" is called to return the value
# for custom <resource_name>.
dyn_res = {}
dyn_res["scratch"] = [get_filesystem_avail_unprivileged, "/tmp"]
dyn_res["home"]    = [get_filesystem_avail_unprivileged, "/home"]

vnl = pbs.event().vnode_list
local_node = pbs.get_local_nodename()

for k in list(dyn_res.keys()):
    vnl[local_node].resources_available[k] = dyn_res[k][0](dyn_res[k][1])

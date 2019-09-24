# coding: utf-8
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
#       qmgr -c "import hook mom_dyn_res application/x-python default mom_dyn_res.py"
#
# NOTE:
#    Update the dyn_res[] array below to include any other custom resources
#    to be included in the updates. Ensure that each resource added has an
#    entry in the server's resourcedef file and scheduler's sched_config file.

import pbs
import os

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


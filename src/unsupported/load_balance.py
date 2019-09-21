# coding: utf-8
# This is a periodic hook script that monitors the load average on the local

# host, and offlines or frees the vnode representing the host depending the
# cpu load.
#
# A site can modify the "ideal_load" and "max_load" value below, so that:
# if the system's cpu load average falls above "max_load", then the
# vnode corresponding to the current host is offlined. 
# This prevents the scheduler from scheduling jobs on this vnode.
# 
# If the system's cpu load average falls below "ideal_load" value,
# then vnode representing the current host is set to free.
# This ensure the scheduler can now schedule jobs on this vnode.
#
# To instantiate this hook, specify the following:
#    qmgr -c "create hook load_balance event=exechost_periodic,freq=10"
#    qmgr -c "import hook load_balance application/x-python default load_balance.py"
import pbs
import os
import re

ideal_load=1.5
max_load=2.0

# get_la: returns a list of load averages within the past 1-minute, 5-minute,
#         15-minutes range.
def get_la():
    line=os.popen("uptime").read()
    r = re.search(r'load average: (\S+), (\S+), (\S+)$', line).groups()
    return list(map(float, r))

local_node = pbs.get_local_nodename()

vnl = pbs.event().vnode_list
current_state = pbs.server().vnode(local_node).state
mla = get_la()[0]
if (mla >= max_load) and ((current_state & pbs.ND_OFFLINE) == 0):
    vnl[local_node].state = pbs.ND_OFFLINE
    vnl[local_node].comment = "offlined node as it is heavily loaded"
elif (mla < ideal_load) and ((current_state & pbs.ND_OFFLINE) != 0):
    vnl[local_node].state = pbs.ND_FREE
    vnl[local_node].comment = None


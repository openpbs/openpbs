import pbs
import sys
import os
import time
import subprocess
import json as json

# Section to be moved to config file once available for provision hook
capmc_dir = '/opt/cray/capmc/default/bin'
power_up_checks = 20
power_up_sleep = 60

# Get the information about the node and aoe to provision
e = pbs.event()
vnode = e.vnode
aoe = e.aoe

numa_cfg, cache_percent = aoe.split('_')
nid = vnode.split('_')[1]

# Add capmc_dir to path
os.environ['PATH'] = capmc_dir + ":" + os.environ['PATH']

# capmc commands to configure the knl nodes
cmd_set_numa_cfg = ['capmc', 'set_numa_cfg', '--nids', '%s' % nid,
                    '--mode', '%s' % numa_cfg]
cmd_set_mcdram_cfg = ['capmc', 'set_mcdram_cfg', '--nids',
                      '%s' % nid, '--mode', '%s' % cache_percent]
cmd_node_reinit = ['capmc', 'node_reinit', '--nids', '%s' % nid]
cmd_node_status = ['capmc', 'node_status', '--nids', '%s' % nid]
cmd_list = (cmd_set_numa_cfg, cmd_set_mcdram_cfg, cmd_node_reinit)

pbs.logmsg(pbs.EVENT_DEBUG3, "vnode: %s" % vnode)
pbs.logmsg(pbs.EVENT_DEBUG3, "aoe: %s" % aoe)
pbs.logmsg(pbs.EVENT_DEBUG3, "numa cmd: %s" % cmd_set_numa_cfg)
pbs.logmsg(pbs.EVENT_DEBUG3, "cache cmd: %s" % cmd_set_mcdram_cfg)
pbs.logmsg(pbs.EVENT_DEBUG3, "power reinit cmd: %s" % cmd_node_reinit)

try:
    for cmd in cmd_list:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        (output, err) = process.communicate()
        if process.returncode != 0:
            error_msg = "Error while running %s: %s" % (cmd, err.strip())
            e.reject(error_msg, process.returncode)
        else:
            node_status = json.loads(output)
            # err_msg value will be Success
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s return code: %s err_msg: %s" % (
                cmd, process.returncode, node_status['err_msg']))

    # Nodes can take upwards of 15 minutes to come back online
    poll_val = 0
    poll_cnt = 0
    while poll_val < 1 and poll_cnt < power_up_checks:
        time.sleep(power_up_sleep)
        process = subprocess.Popen(cmd_node_status, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        (output, err) = process.communicate()
        if process.returncode != 0:
            error_msg = "Error while running %s: %s" % (cmd_node_status, err.strip())
            e.reject(error_msg, process.returncode)
        node_status = json.loads(output)
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "poll_cnt: %d node_status: %s" % (poll_cnt, node_status))
        if "ready" in node_status:
            if int(nid) in node_status['ready']:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Node was successfully powered on")
                poll_val = 1
        poll_cnt += 1

    if poll_val != 1:
        e.reject("Provisioning with reboot failed", 211)
    else:
        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to accept")
        e.accept(0)
except (OSError, ValueError) as err:
    e.reject("Caught exception : %s" % (str(err)), err.errno)
except Exception as err:
    e.reject("Caught exception : %s" % (str(err)), err.errno)

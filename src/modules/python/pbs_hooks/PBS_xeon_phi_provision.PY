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

import json as json
import os
import subprocess
import sys
import time

import pbs

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

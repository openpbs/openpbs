# coding: utf-8
"""
/*
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
 *
 */
"""

__doc__ = """
$Id$

This hook will activate and deactivate a power profile contained
in the 'eoe' value for a job.
"""

import pbs
import os
import socket
import time
import datetime
from subprocess import Popen, PIPE
import json
from pbs.v1._pmi_utils import _get_vnode_names, _svr_vnode


def init_power(event):
    # Get a Power structure and do the connect.  Reject on failure.
    try:
        confvar = "PBS_PMINAME"
        name = None
        if confvar in os.environ:
            name = os.environ[confvar]
        power = pbs.Power(name)
        power.connect()
    except Exception as e:
        event.reject(str(e))
    return power


def vnodes_enabled(job):
    # see if power operations are allowed on all job vnodes
    for vn in _get_vnode_names(job):
        if not _svr_vnode(vn).power_provisioning:
            pbs.logjobmsg(job.id,
                          "power functionality is disabled on vnode %s" % vn)
            return False
    return True


def get_local_node(name):
    # Get host names from /etc/hosts and return matching name for the MoM
    try:
        (hostname, aliaslist, _) = socket.gethostbyname_ex(name)
    except:
        return None
    aliaslist.append(hostname)
    # Search for possible match in server vnode list.
    pbsvnodes = dict()
    for vn in pbs.server().vnodes():
        pbsvnodes[vn.name] = vn
    for n in aliaslist:
        if n in pbsvnodes:
            return pbsvnodes[n]
    return None


# Read the config file in json format
def parse_config_file():
    # Turn everything off by default. These settings be modified
    # when the configuration file is read.
    global pbs_home
    global pbs_exec
    global power_ramp_rate_enable
    global power_on_off_enable
    global node_idle_limit
    global min_node_down_delay
    global max_jobs_analyze_limit
    global max_concurrent_nodes

    try:
        # This block will work for PBS Pro versions 13 and later
        pbs_conf = pbs.get_pbs_conf()
        pbs_home = pbs_conf['PBS_HOME']
        pbs_exec = pbs_conf['PBS_EXEC']
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "PBS_HOME needs to be defined in the config file")
        pbs.logmsg(pbs.EVENT_DEBUG, "Exiting the power hook")
        pbs.event().accept()

    # Identify the config file and read in the data
    config_file = ''
    if 'PBS_HOOK_CONFIG_FILE' in os.environ:
        config_file = os.environ["PBS_HOOK_CONFIG_FILE"]
    tmpcfg = ''
    if not config_file:
        tmpcfg = os.path.join(pbs_home, 'server_priv', 'hooks',
                              'PBS_power.CF')
    if os.path.isfile(tmpcfg):
        config_file = tmpcfg
    if not config_file:
        tmpcfg = os.path.join(pbs_home, 'mom_priv', 'hooks',
                              'PBS_power.CF')
    if os.path.isfile(tmpcfg):
        config_file = tmpcfg
    if not config_file:
        raise Exception("Config file not found")
    pbs.logmsg(pbs.EVENT_DEBUG3, "Config file is %s" % config_file)
    try:
        fd = open(config_file, 'r')
        config = json.load(fd)
        fd.close()
    except IOError:
        raise Exception("I/O error reading config file")
    except:
        raise Exception("Error reading config file")

    # Assign default values to attributes
    power_ramp_rate_enable = False
    power_on_off_enable = False
    node_idle_limit = 1800
    min_node_down_delay = 1800
    max_jobs_analyze_limit = 100
    max_concurrent_nodes = 10

    # Now assgin values read from config file
    if 'power_on_off_enable' in config:
        power_on_off_enable = config['power_on_off_enable']
        pbs.logmsg(pbs.EVENT_DEBUG3, "power_on_off_enable is set to %s" %
                   str(power_on_off_enable))
    if 'power_ramp_rate_enable' in config:
        power_ramp_rate_enable = config['power_ramp_rate_enable']
        pbs.logmsg(pbs.EVENT_DEBUG3, "power_ramp_rate_enable is set to %s" %
                   str(power_ramp_rate_enable))
    if 'node_idle_limit' in config:
        node_idle_limit = int(config['node_idle_limit'])
        if not node_idle_limit or node_idle_limit < 0:
            node_idle_limit = 1800
        pbs.logmsg(pbs.EVENT_DEBUG3, "node_idle_limit is set to %d" %
                   node_idle_limit)
    if 'min_node_down_delay' in config:
        min_node_down_delay = int(config['min_node_down_delay'])
        if not min_node_down_delay or min_node_down_delay < 0:
            min_node_down_delay = 1800
        pbs.logmsg(pbs.EVENT_DEBUG3, "min_node_down_delay is set to %d" %
                   min_node_down_delay)
    if 'max_jobs_analyze_limit' in config:
        max_jobs_analyze_limit = int(config['max_jobs_analyze_limit'])
        if not max_jobs_analyze_limit or max_jobs_analyze_limit < 0:
            max_jobs_analyze_limit = 100
        pbs.logmsg(pbs.EVENT_DEBUG3, "max_jobs_analyze_limit is set to %d" %
                   max_jobs_analyze_limit)
    if 'max_concurrent_nodes' in config:
        max_concurrent_nodes = int(config['max_concurrent_nodes'])
        if not max_concurrent_nodes or max_concurrent_nodes < 0:
            max_concurrent_nodes = 10
        pbs.logmsg(pbs.EVENT_DEBUG3, "max_concurrent_nodes is set to %d" %
                   max_concurrent_nodes)


# Accept if event not serviceable.
this_event = pbs.event()
if this_event.type not in [pbs.EXECJOB_PROLOGUE, pbs.EXECJOB_EPILOGUE,
                           pbs.EXECJOB_BEGIN, pbs.EXECJOB_END,
                           pbs.EXECHOST_STARTUP, pbs.EXECHOST_PERIODIC,
                           pbs.PERIODIC]:
    pbs.logmsg(pbs.LOG_WARNING,
               "Event not serviceable for power provisioning.")
    this_event.accept()


if this_event.type == pbs.PERIODIC:
    vnlist = this_event.vnode_list
    resvlist = this_event.resv_list
    time_now = time.time()

    # Parse the config file for power attributes
    try:
        parse_config_file()
    except Exception as e:
        this_event.reject(str(e))

    if power_ramp_rate_enable == 0 and power_on_off_enable == 0:
        this_event.accept()

    if power_on_off_enable and power_ramp_rate_enable:
        # Disable ramp rate if power on/off is enabled as well.
        power_ramp_rate_enable = 0
        pbs.logmsg(pbs.LOG_WARNING,
                   "Hook config: power_on_off_enable is over-riding power_ramp_rate_enable")

    qselect_cmd = os.path.join(pbs_exec, 'bin', 'qselect')
    qstat_cmd = os.path.join(pbs_exec, 'bin', 'qstat')
    dtnow = datetime.datetime.now().strftime("%m%d%H%M")
    qselect_cmd += " -tt.gt." + str(dtnow)
    try:
        p = Popen(qselect_cmd, shell=True, stdout=PIPE, stderr=PIPE)
        (o, e) = p.communicate()
        if p.returncode or not o:
            job_list = []
        else:
            job_list = o.splitlines()
    except (OSError, ValueError):
        job_list = []
    # Analyze queued jobs and see if any of the nodes are needed in near future
    exec_vnodes = {}
    i = 0
    pattern = '%a %b %d %H:%M:%S %Y'
    for jobid in job_list:
        if not jobid:
            break
        if i == max_jobs_analyze_limit:
            break
        cmd = qstat_cmd + " -f -F json " + jobid
        try:
            p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
            (o, e) = p.communicate()
            if p.returncode:
                continue
        except (OSError, ValueError):
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Error running qstat command for job %s" % jobid)
            continue
        evnlist = None
        start_time = 0
        job_state = None
        if not o:
            continue
        try:
            out = json.loads(o)
            job = out['Jobs'][jobid]
            if 'estimated' in job:
                est = job['estimated']
                if 'start_time' in est:
                    fmttime = est['start_time']
                    start_time = int(time.mktime(
                        time.strptime(fmttime, pattern)))
                if 'exec_vnode' in est:
                    evnlist = est['exec_vnode']
            if 'job_state' in job:
                job_state = job['job_state']
        except ValueError:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Error reading json output for job %s" % jobid)
            continue
        if job_state == 'Q':
            if start_time and evnlist:
                for chunk in evnlist.split("+"):
                    vn = chunk.split(":")[0][1:]
                    if vn not in exec_vnodes:
                        exec_vnodes[vn] = {}
                        exec_vnodes[vn]["neededby"] = start_time
                    elif start_time < exec_vnodes[vn]["neededby"]:
                        exec_vnodes[vn]["neededby"] = start_time
        i += 1

    pbs_conf = pbs.get_pbs_conf()
    if 'PBS_HOME' in pbs_conf:
        pbs_home = pbs_conf['PBS_HOME']
    else:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "PBS_HOME needs to be defined in the config file")
        pbs.logmsg(pbs.EVENT_DEBUG, "Exiting the power hook")
        pbs.event().accept()

    # Identify the nodes file and read in the data
    node_file = ''
    sleep_node_list = []
    node_file = os.path.join(pbs_home,
                             'server_priv', 'hooks', 'tmp', 'pbs_power_nodes_file')
    if os.path.isfile(node_file) and os.stat(node_file).st_size:
        pbs.logmsg(pbs.EVENT_DEBUG3, "pbs_power_nodes_file is %s" % node_file)
        try:
            with open(node_file, 'r') as fd:
                sleep_node_list = fd.read().split(',')
        except IOError as e:
            this_event.reject(str(e))

    nodes = {}
    for vn in vnlist:
        vnode = vnlist[vn]
        host = vnode.resources_available["host"]
        can_power_off = 0
        try:
            if vnode.resources_available["PBScraynid"]:
                if power_on_off_enable:
                    if vnode.poweroff_eligible:
                        can_power_off = vnode.poweroff_eligible
                else:
                    # For ramp rate limiting.
                    can_power_off = 1
        except Exception:
            pass

        if host not in nodes:
            # Initialize the nodes with new host
            nodes[host] = {}
            nodes[host]["can_power_off"] = can_power_off
            nodes[host]["poweroff"] = 0
            nodes[host]["poweron"] = 0
            nodes[host]["vnodes"] = []
        nodes[host]["vnodes"].append(vnode)

        if can_power_off == 0:
            # Not allowed to power on/off this node
            nodes[host]["can_power_off"] = 0
            nodes[host]["poweroff"] = 0
            nodes[host]["poweron"] = 0

        rs_list = []
        if vnode.resv:
            resv_str = str(vnode.resv)
            rs_list = resv_str.split(",")

        if nodes[host]["can_power_off"]:
            # See if the node is actually free
            if vnode.state != pbs.ND_FREE:
                nodes[host]["poweroff"] = 0
            else:
                # See if there are any reservations on the vnode
                # Reservations further in time can be ignored.
                for resid in rs_list:
                    resv = resvlist[resid.lstrip()]
                    rstates = [pbs.RESV_STATE_RUNNING, pbs.RESV_STATE_DELETED,
                               pbs.RESV_STATE_BEING_ALTERED,
                               pbs.RESV_STATE_DELETING_JOBS]
                    if resv.reserve_state in rstates:
                        nodes[host]["poweroff"] = 0
                        nodes[host]["can_power_off"] = 0
                    if resv.reserve_state == pbs.RESV_STATE_CONFIRMED:
                        reserve_start = resv.reserve_start
                        if vn not in exec_vnodes:
                            exec_vnodes[vn] = {}
                            exec_vnodes[vn]["neededby"] = reserve_start
                        elif reserve_start < exec_vnodes[vn]["neededby"]:
                            exec_vnodes[vn]["neededby"] = reserve_start
                        # Do not power off a node if it has reservation starting
                        # in (time_now + min_node_down_delay + 900) seconds
                        if time_now > (reserve_start - (min_node_down_delay + 900)):
                            nodes[host]["poweroff"] = 0
                            nodes[host]["can_power_off"] = 0

                # Is the node idle enough to put to sleep or power down?
                if nodes[host]["can_power_off"]:
                    if vnode.last_used_time:
                        last_used_time = vnode.last_used_time
                    else:
                        last_used_time = 0
                    idle_time = time_now - last_used_time
                    if node_idle_limit < idle_time:
                        nodes[host]["poweroff"] = 1

        # POWER-ON/RAMP-UP check: See if the node is down and
        # needs to be brought up. Check if the node needs to be
        # up before this periodic event runs again.
        if vnode.state == pbs.ND_SLEEP:
            if power_on_off_enable:
                # Ignore the nodes in sleep_node_list as they are
                # being powered up by previous interation of the hook.
                if vn in sleep_node_list:
                    continue
            # Look for upcoming reservation starts in the node.
            for resid in rs_list:
                resv = resvlist[resid.lstrip()]
                rstates = [pbs.RESV_STATE_CONFIRMED, pbs.RESV_STATE_DEGRADED]
                if resv.reserve_state in rstates:
                    reserve_start = resv.reserve_start
                    if vn not in exec_vnodes:
                        exec_vnodes[vn] = {}
                        exec_vnodes[vn]["neededby"] = reserve_start
                    elif reserve_start < exec_vnodes[vn]["neededby"]:
                        exec_vnodes[vn]["neededby"] = reserve_start
            if vn in exec_vnodes and exec_vnodes[vn]["neededby"]:
                neededby = exec_vnodes[vn]["neededby"]
            else:
                neededby = 0
            # Check if node is needed in near future.
            # Assuming node will take about 900 seconds to come up.
            if neededby and neededby < (time_now + 900):
                nodes[host]["poweron"] = 1
            # See when node was put down
            if vnode.last_state_change_time:
                last_state_change = vnode.last_state_change_time
            else:
                last_state_change = 0
            # Do not power on a node if it went down within less than
            # min_node_down_delay seconds
            if power_on_off_enable and last_state_change:
                if (time_now - last_state_change) < int(min_node_down_delay):
                    nodes[host]["poweron"] = 0

    poweroff_vnlist = []
    poweron_vnlist = []
    i = 0
    j = 0
    for n in nodes:
        # Check if any nodes need to be ramped-down/powered-off.
        if nodes[n]["poweroff"] == 1 and i < max_concurrent_nodes:
            poweroff_vnlist.append(n)
            i += 1
        # Check if any nodes need to be ramped-up/powered-on.
        elif nodes[n]["poweron"] == 1 and j < max_concurrent_nodes:
            poweron_vnlist.append(n)
            j += 1
        if i == max_concurrent_nodes and j == max_concurrent_nodes:
            break

    if poweroff_vnlist or poweron_vnlist or sleep_node_list:
        power = init_power(this_event)
    else:
        this_event.accept()
    try:
        if power_ramp_rate_enable:
            # Ramp rate limiting
            if poweroff_vnlist:
                power.ramp_down(poweroff_vnlist)
            if poweron_vnlist:
                power.ramp_up(poweron_vnlist)
        else:
            # Power on/off nodes
            if poweroff_vnlist:
                power.power_off(poweroff_vnlist)
            if poweron_vnlist:
                power.power_on(poweron_vnlist)
            ready_nodes = set()
            if sleep_node_list:
                ready_nodes = power.power_status(sleep_node_list)
                # For the nodes which are up remove ND_SLEEP
                for host in ready_nodes:
                    for vn in nodes[host]["vnodes"]:
                        prev_state = vn.state
                        vn.state = prev_state & ~(pbs.ND_SLEEP)
                        vn.last_used_time = time_now
            # nodes which are still booting, write them to
            # node file for status check in next iteration.
            if sleep_node_list or poweron_vnlist:
                if poweron_vnlist:
                    sleeping_nodes = poweron_vnlist
                else:
                    sleeping_nodes = []
                # Look for still booting nodes from previous iteration.
                for n in sleep_node_list:
                    if n not in ready_nodes:
                        sleeping_nodes.append(n)
                data = ','.join(sleeping_nodes)
                try:
                    with open(node_file, 'w') as fd:
                        fd.write(data)
                except IOError as e:
                    power.disconnect()
                    this_event.reject(str(e))
        # Mark nodes to ND_Sleep
        for nd in poweroff_vnlist:
            for vn in nodes[nd]["vnodes"]:
                vn.state = pbs.ND_SLEEP
        # Mark nodes to ND_free
        if power_ramp_rate_enable:
            for nd in poweron_vnlist:
                for vn in nodes[nd]["vnodes"]:
                    vn.state = pbs.ND_FREE
                    vn.last_used_time = time_now
        power.disconnect()
        this_event.accept()
    except Exception as e:
        power.disconnect()
        this_event.reject(str(e))


# Set eoe values for my node
if this_event.type == pbs.EXECHOST_STARTUP:
    from pbs.v1._pmi_utils import _is_node_provisionable

    # Don't connect if the server or sched is running.
    if not _is_node_provisionable():
        pbs.logmsg(pbs.LOG_DEBUG,
                   "Provisioning cannot be enabled on this host")
        this_event.accept()
    power = init_power(this_event)
    profiles = power.query(pbs.Power.QUERY_PROFILE)
    if profiles is not None:
        me = pbs.get_local_nodename()
        this_event.vnode_list[me].resources_available[
            "eoe"] = power._map_profile_names(profiles)
    power.disconnect()
    this_event.accept()


# Gather energy usage for all jobs
if this_event.type == pbs.EXECHOST_PERIODIC:
    # Check if any jobs are running
    if len(this_event.job_list) == 0:
        this_event.accept()

    power = init_power(this_event)
    for jobid in this_event.job_list:
        # set energy usage
        job = this_event.job_list[jobid]
        # skip any jobs that MOM is not MS
        if not job.in_ms_mom():
            continue
        # skip if vnodes have power_provisioning=0
        if not vnodes_enabled(job):
            continue

        try:
            usage = power.get_usage(job)
            if usage is not None:
                job.resources_used["energy"] = usage
        except Exception as e:
            pbs.logmsg(pbs.LOG_ERROR, str(e))
    power.disconnect()
    this_event.accept()

# From this point on, the event will have a job.
this_job = this_event.job

if this_event.type == pbs.EXECJOB_BEGIN:
    me = pbs.get_local_nodename()
    try:
        if not _svr_vnode(me).power_provisioning:
            this_event.accept()
    except:
        # Try with different hostname
        vn = get_local_node(me)
        if not _svr_vnode(vn.name).power_provisioning:
            this_event.accept()
    requested_profile = str(this_job.schedselect).partition(
        'eoe=')[2].partition('+')[0].partition(':')[0]
    if requested_profile != "":
        try:
            this_event.vnode_list[me].current_eoe = requested_profile
        except (KeyError, ValueError):
            pass
    this_event.accept()
if this_event.type == pbs.EXECJOB_END:
    me = pbs.get_local_nodename()
    try:
        this_event.vnode_list[me].current_eoe = None
    except (KeyError, ValueError):
        pass

    power = init_power(this_event)
    try:
        power.deactivate_profile(this_job)
    except Exception as e:
        pbs.logjobmsg(this_job.id, str(e))
    power.disconnect()
    this_event.accept()

# No further processing is needed if we are not mother superior.
if not this_job.in_ms_mom():
    this_event.accept()

# Don't do anything if power_provisioning=0
if not vnodes_enabled(this_job):
    this_event.accept()

# Was an EOE requested?
requested_profile = str(this_job.schedselect).partition(
    'eoe=')[2].partition('+')[0].partition(':')[0]
if requested_profile == "":
    this_event.accept()

if this_event.type == pbs.EXECJOB_PROLOGUE:
    power = init_power(this_event)
    try:
        power.activate_profile(requested_profile, this_job)
        power.disconnect()
    except Exception as e:
        power.disconnect()
        this_event.reject(str(e))
elif this_event.type == pbs.EXECJOB_EPILOGUE:
    power = init_power(this_event)
    # set energy usage
    try:
        usage = power.get_usage(this_job)
        if usage is not None:
            this_job.resources_used["energy"] = usage
    except Exception as e:
        pbs.logjobmsg(this_job.id, str(e))
    power.disconnect()

this_event.accept()

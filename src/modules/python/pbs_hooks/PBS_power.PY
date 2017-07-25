# coding: utf-8
"""
/*
#  Copyright (C) 1994-2017 Altair Engineering, Inc.
#  For more information, contact Altair at www.altair.com.
#
#  This file is part of the PBS Professional ("PBS Pro") software.
#
#  Open Source License Information:
#
#  PBS Pro is free software. You can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any
#  later version.
#
#  PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
#  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License along
#  with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#  Commercial License Information:
#
#  The PBS Pro software is licensed under the terms of the GNU Affero General
#  Public License agreement ("AGPL"), except where a separate commercial license
#  agreement for PBS Pro version 14 or later has been executed in writing with Altair.
#
#  Altair’s dual-license business model allows companies, individuals, and
#  organizations to create proprietary derivative works of PBS Pro and distribute
#  them - whether embedded or bundled with other software - under a commercial
#  license agreement.
#
#  Use of Altair’s trademarks, including but not limited to "PBS™",
#  "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
#  trademark licensing policies.
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
    except Exception, e:
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


# Accept if event not serviceable.
this_event = pbs.event()
if this_event.type not in [pbs.EXECJOB_PROLOGUE, pbs.EXECJOB_EPILOGUE,
                           pbs.EXECJOB_BEGIN, pbs.EXECJOB_END,
                           pbs.EXECHOST_STARTUP, pbs.EXECHOST_PERIODIC]:
    pbs.logmsg(pbs.LOG_WARNING,
               "Event not serviceable for power provisioning.")
    this_event.accept()


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
    for jobid in this_event.job_list.keys():
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
        except Exception, e:
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
        me = socket.getfqdn()
        if not _svr_vnode(me).power_provisioning:
            this_event.accept()
    requested_profile = str(this_job.schedselect).partition(
        'eoe=')[2].partition('+')[0].partition(':')[0]
    if requested_profile != "":
        try:
            this_event.vnode_list[me].current_eoe = requested_profile
        except:
            pass
    this_event.accept()
if this_event.type == pbs.EXECJOB_END:
    me = pbs.get_local_nodename()
    try:
        this_event.vnode_list[me].current_eoe = None
    except:
        pass
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
    except Exception, e:
        power.disconnect()
        this_event.reject(str(e))
elif this_event.type == pbs.EXECJOB_EPILOGUE:
    power = init_power(this_event)
    # set energy usage
    try:
        usage = power.get_usage(this_job)
        if usage is not None:
            this_job.resources_used["energy"] = usage
    except Exception, e:
        pbs.logjobmsg(this_job.id, str(e))

    try:
        power.deactivate_profile(this_job)
    except Exception, e:
        pbs.logjobmsg(this_job.id, str(e))
    power.disconnect()

this_event.accept()

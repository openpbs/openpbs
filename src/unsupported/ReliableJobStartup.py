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

# ReliableJobStartup.py:
#
# A job is started and one or more of the sister moms in a cluster fails to
# join job due to a reject from an execjob_begin hook or a reject from an
# execjob_prologue hook, and that sister mom goes offline.
# See NodeHealthCheck.py that might be used for this purpose.
#
# Using the reliable job startup feature, if the job's tolerate_node_failures
# is set to "job_start" (or "all"), the job's original select spec is
# expanded in increment_chunks() in a queuejob event.
#
# If ran by the primary mom, in an execjob_launch event the list of selected
# nodes for the job and the ones that failed after job started are logged and
# release_nodes(keep_select) will use good nodes to satisfy the select spec.
# The failed nodes are offlined.  The 's' accounting record is generated.

# To register the hook, as root via qmgr:
# qmgr << RJS
# create hook rjs_hook
# set hook rjs_hook event = 'queuejob,execjob_launch'
# set hook rjs_hook enabled = true
# import hook rjs_hook application/x-python default ReliableJobStartup.py
# RJS

import pbs
e = pbs.event()

if e.type == pbs.QUEUEJOB:
    # add a log entry in server logs
    pbs.logmsg(pbs.LOG_DEBUG, "queuejob hook executed")
    e.job.tolerate_node_failures = "job_start"

    # Save current select spec in resource 'site'
    selspec = e.job.Resource_List["select"]
    if selspec is None:
        e.reject("Event job does not have select spec!")
    e.job.Resource_List["site"] = str(selspec)

    # increment_chunks() can use a percentage argument or an integer. For
    # example add 1 chunk to each chunk (except the first) in the job's
    # select spec
    new_select = selspec.increment_chunks(1)
    e.job.Resource_List["select"] = new_select
    pbs.logmsg(pbs.LOG_DEBUG, "job's select spec changed to %s" % new_select)

elif e.type == pbs.EXECJOB_LAUNCH:
    if 'PBS_NODEFILE' not in e.env:
        e.accept()
    # add a log entry in primary mom logs
    pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")

    # print out the vnode_list[] values
    for vn in e.vnode_list:
        v = e.vnode_list[vn]
        pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")

    # print out the vnodes in vnode_list_fail[] and offline them
    for vn in e.vnode_list_fail:
        v = e.vnode_list_fail[vn]
        pbs.logjobmsg(
            e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
        v.state = pbs.ND_OFFLINE

    # prune the job's vnodes to satisfy the select spec in resource 'site'
    # and vnodes in vnode_list_fail[] are not used.
    if e.job.in_ms_mom():
        pj = e.job.release_nodes(keep_select=e.job.Resource_List["site"])
        if pj is None:
            e.job.Hold_Types = pbs.hold_types("s")
            e.job.rerun()
            e.reject("unsuccessful at LAUNCH")

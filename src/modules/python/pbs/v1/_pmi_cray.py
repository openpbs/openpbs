# coding: utf-8
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
 *
 */
"""
__doc__ = """
This module is used for Cray systems.
"""

import os
import stat
import time
import random
from subprocess import Popen, PIPE
from pbs.v1._pmi_types import BackendError
import pbs
from pbs.v1._pmi_utils import _running_excl, _pbs_conf, _get_vnode_names, \
    _svr_vnode

pbsexec = _pbs_conf("PBS_EXEC")
if pbsexec is None:
    raise BackendError("PBS_EXEC not found")


def launch(jid, args):
    """
    Run capmc and return the structured output.

    :param jid: job id
    :type jid: str
    :param args: arguments for capmc command
    :type args: str
    :returns: capmc output in json format.
    """
    import json

    # full path to capmc given by Cray
    cmd = os.path.join(os.path.sep, 'opt', 'cray',
                       'capmc', 'default', 'bin', 'capmc')
    if not os.path.exists(cmd):
        cmd = "capmc"		# should be in PATH then
    cmd = cmd + " " + args
    fail = ""

    pbs.logjobmsg(jid, "launch: " + cmd)
    cmd_run = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    (cmd_out, cmd_err) = cmd_run.communicate()
    exitval = cmd_run.returncode
    if exitval != 0:
        fail = "%s: exit %d" % (cmd, exitval)
    else:
        pbs.logjobmsg(jid, "launch: finished")

    try:
        out = json.loads(cmd_out)
    except Exception:
        out = None
    try:
        err = cmd_err.splitlines()[0]           # first line only
    except Exception:
        err = ""
    if out is not None:
        errno = out["e"]
        msg = out["err_msg"]
        if errno != 0 or (len(msg) > 0 and msg != "Success"):
            fail = "output: e=%d err_msg='%s'" % (errno, msg)
    if len(err) > 0:
        pbs.logjobmsg(jid, "stderr: %s" % err.strip())

    if len(fail) > 0:
        pbs.logjobmsg(jid, fail)
        raise BackendError(fail)
    return out


def jobnids(job):
    """
    Return the set of nids belonging to a job.

    :param job: job id
    :type job: str
    :returns: set of nids from node's resources_available[craynid].
    """
    nidset = set()
    craynid = "PBScraynid"
    for vname in _get_vnode_names(job):
        vnode = _svr_vnode(vname)
        try:
            nidset.add(int(vnode.resources_available[craynid]))
        except Exception:
            pass
    return nidset


def nodenids(hosts):
    """
    Return the set of nids from the host list.

    :param hosts: list of exec hosts from the job.
    :type hosts: str
    :returns: set of nids from node's resources_available[craynid].
    """
    nidset = set()
    craynid = "PBScraynid"
    for vnames in hosts:
        vnode = _svr_vnode(vnames)
        try:
            nidset.add(int(vnode.resources_available[craynid]))
        except Exception:
            pass
    return nidset


def nidlist(job=None, nidset=None):
    """
    Return a string to be used with capmc --nids option
    and the number of nids

    :param job: job id.
    :type job: str
    :param nidset: nid set
    :type nidset: set
    :returns: retunrs a list of nids that can be used with capmc.
              in the foramt "24-30, 51, 53, 60-65"
    """
    if nidset is None:
        nidset = jobnids(job)
    nids = []
    first = ""
    last = ""
    prev = 0
    for nid in sorted(nidset):
        val = nid
        if len(first) == 0:		# start point
            first = str(nid)
        elif prev + 1 != val:
            if prev == int(first):
                nids.append(first)
            else:
                nids.append(first + "-" + last)
            first = str(nid)
        prev = val
        last = str(nid)
    if len(first) > 0:
        if prev == int(first):
            nids.append(first)
        else:
            nids.append(first + "-" + last)
    return ",".join(nids), len(nidset)


def spool_file(name):
    """
    Form a path to the PBS spool directory with name as the last element.

    :param name: energy file name in format <jobid>.energy.
    :type name: str
    :returns: path to RUR/energy file in format PBS_HOME/spool/<jobid>.energy.
    """
    home = _pbs_conf("PBS_HOME")
    if home is None:
        raise BackendError("PBS_HOME not found")
    return os.path.join(home, "spool", name)


def energy_file(job):
    """
    Form a path to the PBS spool directory with name as the last element.

    :param job: job id.
    :type job: str
    :returns: path to energy file in format PBS_HOME/spool/<jobid>.energy.
    """
    return spool_file("%s.energy" % job.id)


def rur_file(job):
    """
    Form a path to the PBS spool directory with name as the last element.

    :param job: job id.
    :type job: str
    :returns: path to RUR file in format PBS_HOME/spool/<jobid>.rur.
    """
    return spool_file("%s.rur" % job.id)


def node_energy(jid, nids, cnt):
    """
    Return the result of running capmc get_node_energy_counter.
    The magic number of 15 seconds in the past is used because that
    is the most current value that can be expected from capmc.

    :param jid: job id.
    :type jid: str
    :param nids: nid list
    :type nids: str
    :param cnt: node count
    :type cnt: int
    :returns: ret on successfull energy usage capmc query.
              None on failure.
    """
    if cnt == 0:
        return None
    cmd = "get_node_energy_counter --nids %s" % nids
    ret = launch(jid, cmd)
    cntkey = "nid_count"
    gotcnt = "<notset>"
    if (ret is not None) and (cntkey in ret):
        gotcnt = ret[cntkey]
        if gotcnt == cnt:
            return ret

    pbs.logjobmsg(jid, "node count %s, should be %d" % (str(gotcnt), cnt))
    ret = launch(jid, cmd)
    gotcnt = "<notset>"
    if (ret is not None) and (cntkey in ret):
        gotcnt = ret[cntkey]
        if gotcnt == cnt:
            return ret

    pbs.logjobmsg(jid, "second query failed, node count %s, should be %d" %
                  (str(gotcnt), cnt))
    return None


def job_energy(job, nids, cnt):
    """
    Return energy counter from capmc.  Return None if no energy
    value is available.

    :param job: pbs job.
    :type job: str
    :param nids: nid list
    :type nids: str
    :param cnt: node count
    :type cnt: int
    :returns: ret on successfull energy usage capmc query.
              None on failure.
    """
    energy = None
    ret = node_energy(job.id, nids, cnt)
    if ret is not None and "nodes" in ret:
        energy = 0
        for node in ret["nodes"]:
            energy += node["energy_ctr"]
        pbs.logjobmsg(job.id, "energy usage %dJ" % energy)
    return energy


class Pmi:

    ninfo = None
    nidarray = dict()

    def __init__(self, pyhome=None):
        pbs.logmsg(pbs.EVENT_DEBUG3, "Cray: init")

    def _connect(self, endpoint=None, port=None, job=None):
        if job is None:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Cray: connect")
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Cray: %s connect" % (job.id))
        return

    def _disconnect(self, job=None):
        if job is None:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Cray: disconnect")
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Cray: %s disconnect" % (job.id))
        return

    def _get_usage(self, job):
        pbs.logmsg(pbs.EVENT_DEBUG3, "Cray: %s get_usage" % (job.id))
        try:
            f = open(energy_file(job), "r")
            start = int(f.read())
            f.close()
        except Exception:
            return None

        e = pbs.event()
        if e.type == pbs.EXECHOST_PERIODIC:
            # This function will be called for each job in turn when
            # running from a periodic hook.  Here we fill in some
            # global variables just once and use the information
            # for each job in turn.  Save the result of calling capmc
            # for all running jobs in the variable ninfo.  Keep a
            # dictionary with the job id's as keys holding a set
            # of nid numbers.
            if Pmi.ninfo is None:
                allnids = set()
                for jobid in list(e.job_list.keys()):
                    j = e.job_list[jobid]
                    nidset = jobnids(j)
                    allnids.update(nidset)
                    Pmi.nidarray[jobid] = nidset
                nids, cnt = nidlist(None, allnids)
                Pmi.ninfo = node_energy("all", nids, cnt)
            nidset = Pmi.nidarray[job.id]
            energy = None
            if Pmi.ninfo is not None and "nodes" in Pmi.ninfo:
                energy = 0
                for node in Pmi.ninfo["nodes"]:
                    if node["nid"] in nidset:		# owned by job of interest
                        energy += node["energy_ctr"]
                pbs.logjobmsg(job.id, "Cray: get_usage: energy %dJ" %
                              energy)
        else:
            nids, cnt = nidlist(job)
            energy = job_energy(job, nids, cnt)
        if energy is not None:
            return float(energy - start) / 3600000.0
        else:
            return None

    def _query(self, query_type):
        pbs.logmsg(pbs.LOG_DEBUG, "Cray: query")
        return None

    def _activate_profile(self, profile_name, job):
        pbs.logmsg(pbs.LOG_DEBUG, "Cray: %s activate '%s'" %
                   (job.id, str(profile_name)))

        nids, cnt = nidlist(job)
        if cnt == 0:
            pbs.logjobmsg(job.id, "Cray: no compute nodes for power setting")
            return False

        energy = job_energy(job, nids, cnt)
        if energy is not None:
            f = open(energy_file(job), "w")
            f.write(str(energy))
            f.close()

        # If this is the only job, set nodes to capped power.
        if _running_excl(job):
            cmd = "set_power_cap --nids " + nids
            doit = False

            pcap = job.Resource_List['pcap_node']
            if pcap is not None:
                pbs.logjobmsg(job.id, "Cray: pcap node %d" % pcap)
                cmd += " --node " + str(pcap)
                doit = True
            pcap = job.Resource_List['pcap_accelerator']
            if pcap is not None:
                pbs.logjobmsg(job.id, "Cray: pcap accel %d" % pcap)
                cmd += " --accel " + str(pcap)
                doit = True

            if doit:
                launch(job.id, cmd)
            else:
                pbs.logjobmsg(job.id, "Cray: no power cap to set")

        return True

    def _deactivate_profile(self, job):
        pbs.logmsg(pbs.LOG_DEBUG, "Cray: deactivate %s" % job.id)
        nids, cnt = nidlist(job)
        if cnt == 0:
            pbs.logjobmsg(job.id, "Cray: no compute nodes for power setting")
            return False

        # remove initial energy file
        try:
            os.unlink(energy_file(job))
        except Exception:
            pass

        # If this is the only job, undo any power cap we set.
        if _running_excl(job):
            cmd = "set_power_cap --nids " + nids
            doit = False

            pcap = job.Resource_List['pcap_node']
            if pcap is not None:
                pbs.logjobmsg(job.id, "Cray: remove pcap node %d" % pcap)
                cmd += " --node 0"
                doit = True
            pcap = job.Resource_List['pcap_accelerator']
            if pcap is not None:
                pbs.logjobmsg(job.id, "Cray: remove pcap accel %d" % pcap)
                cmd += " --accel 0"
                doit = True

            if doit:
                try:
                    launch(job.id, cmd)
                except Exception:
                    pass
            else:
                pbs.logjobmsg(job.id, "Cray: no power cap to remove")

        # Get final energy value from RUR data
        name = rur_file(job)
        try:
            rurfp = open(name, "r")
        except Exception:
            pbs.logjobmsg(job.id, "Cray: no RUR data")
            return False

        sbuf = os.fstat(rurfp.fileno())
        if (sbuf.st_uid != 0) or (sbuf.st_mode & stat.S_IWOTH):
            pbs.logjobmsg(job.id, "Cray: RUR file permission: %s" % name)
            rurfp.close()
            os.unlink(name)
            return False

        pbs.logjobmsg(job.id, "Cray: reading RUR file: %s" % name)
        energy = 0
        seen = False        # track if energy plugin is seen
        for line in rurfp:
            plugin, _, rest = line.partition(" : ")
            if plugin != "energy":		# check that the plugin is energy
                continue

            apid, _, metstr = rest.partition(" : ")
            seen = True
            try:						# parse the metric list
                metlist = eval(metstr, {})
                metrics = dict(metlist[i:i + 2] for i in range(0,
                                                               len(metlist), 2))
                joules = metrics["energy_used"]
                energy += joules
                pbs.logjobmsg(job.id,
                              'Cray:RUR: {"apid":%s,"apid_energy":%dJ,"job_energy":%dJ}' %
                              (apid, joules, energy))
            except Exception as e:
                pbs.logjobmsg(job.id,
                              "Cray:RUR: energy_used not found: %s" % str(e))

        rurfp.close()
        os.unlink(name)

        if not seen:
            pbs.logjobmsg(job.id, "Cray:RUR: no energy plugin")
            return False

        old_energy = job.resources_used["energy"]
        new_energy = float(energy) / 3600000.0
        if old_energy is None:
            pbs.logjobmsg(job.id, "Cray:RUR: energy %fkWh" % new_energy)
            job.resources_used["energy"] = new_energy
        elif new_energy > old_energy:
            pbs.logjobmsg(job.id,
                          "Cray:RUR: energy %fkWh replaces periodic energy %fkWh" %
                          (new_energy, old_energy))
            job.resources_used["energy"] = new_energy
        else:
            pbs.logjobmsg(job.id,
                          "Cray:RUR: energy %fkWh last periodic usage %fkWh" %
                          (new_energy, old_energy))
        return True

    def _pmi_power_off(self, hosts):
        pbs.logmsg(pbs.LOG_DEBUG, "Cray: powering-off the node")
        nidset = nodenids(hosts)
        nids, _ = nidlist(None, nidset)
        cmd = "node_off --nids " + nids
        func = "pmi_power_off"
        launch(func, cmd)
        return True

    def _pmi_power_on(self, hosts):
        pbs.logmsg(pbs.LOG_DEBUG, "Cray: powering-on the node")
        nidset = nodenids(hosts)
        nids, _ = nidlist(None, nidset)
        cmd = "node_on --nids " + nids
        func = "pmi_power_on"
        launch(func, cmd)
        return True

    def _pmi_ramp_down(self, hosts):
        pbs.logmsg(pbs.LOG_DEBUG, "Cray: ramping down the node")
        nidset = nodenids(hosts)
        nids, _ = nidlist(None, nidset)
        cmd = "get_sleep_state_limit_capabilities --nids " + nids
        func = "pmi_ramp_down"
        out = launch(func, cmd)
        for n in out["nids"]:
            if "data" in n:
                nid = n["nid"]
                states = n["data"]["PWR_Attrs"][0]["PWR_AttrValueCapabilities"]
                for s in states:
                    if int(s) != 0:
                        cmd = "set_sleep_state_limit --nids " + str(nid) + " --limit " + str(s)
                        launch(func, cmd)
                        sleep_time = random.randint(1, 10)
                        time.sleep(sleep_time)
        return True

    def _pmi_ramp_up(self, hosts):
        pbs.logmsg(pbs.LOG_DEBUG, "Cray: ramping up the node")
        nidset = nodenids(hosts)
        nids, _ = nidlist(None, nidset)
        cmd = "get_sleep_state_limit_capabilities --nids " + nids
        func = "pmi_ramp_up"
        out = launch(func, cmd)
        for n in out["nids"]:
            if "data" in n:
                nid = n["nid"]
                states = n["data"]["PWR_Attrs"][0]["PWR_AttrValueCapabilities"]
                for s in reversed(states):
                    if int(s) != 0:
                        cmd = "set_sleep_state_limit --nids " + str(nid) + " --limit " + str(s)
                        launch(func, cmd)
                        sleep_time = random.randint(1, 10)
                        time.sleep(sleep_time)
        return True

    def _pmi_power_status(self, hosts):
        # Do a capmc node_status and return a list of ready nodes.
        pbs.logmsg(pbs.EVENT_DEBUG3, "Cray: status of the nodes")
        nidset = nodenids(hosts)
        nids, _ = nidlist(nidset=nidset)
        cmd = "node_status --nids " + nids
        func = "pmi_power_status"
        out = launch(func, cmd)
        ready = []
        nodeset = set()
        if 'ready' in out:
            ready = out['ready']
        else:
            return nodeset
        craynid = "PBScraynid"
        for vnames in hosts:
            vnode = _svr_vnode(vnames)
            if craynid in vnode.resources_available:
                nid = int(vnode.resources_available[craynid])
                if nid in ready:
                    nodeset.add(vnames)
        return nodeset

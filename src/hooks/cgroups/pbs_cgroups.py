# coding: utf-8

# Copyright (C) 1994-2016 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and distribute
# them - whether embedded or bundled with other software - under a commercial
# license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

# When soft_limit is true for memory, memsw represents the hard limit.
#
# The resources value in sched_config must contain entries for mem and
# vmem if those subsystems are enabled in the hook configuration file. The
# amount of resource requested will not be avaiable to the hook if they
# are not present.

# This hook handles all of the operations necessary for PBS to support
# cgroups on linux hosts that support them (kernel 2.6.28 and higher)
#
# This hook services the following events:
# - exechost_periodic
# - exechost_startup
# - execjob_attach
# - execjob_begin
# - execjob_end
# - execjob_epilogue
# - execjob_launch

# Imports from __future__ must happen first
from __future__ import with_statement

# Additional imports
import sys
import os
import errno
import signal
import subprocess
import re
import glob
import time
import string
import platform
import traceback
import copy
from stat import S_ISBLK, S_ISCHR
import operator
import pwd
import pbs
import fnmatch
import socket

try:
    import json
except:
    import simplejson as json

CGROUP_KILL_ATTEMPTS = 12

# Flag to turn off features not in 12.2.40X branch
CRAY_12_BRANCH = False


# ============================================================================
# Derived error classes
# ============================================================================

# Base class for errors fixable only by administrative action.


class AdminError(Exception):
    pass

# Base class for errors in processing, unknown cause.


class ProcessingError(Exception):
    pass

# Base class for errors fixable by the user.


class UserError(Exception):
    pass

# Errors in PBS job resource values.


class JobValueError(UserError):
    pass

# Errors when the cgroup is busy.


class CgroupBusyError(ProcessingError):
    pass

# Errors in configuring cgroup.


class CgroupConfigError(AdminError):
    pass

# Errors in configuring cgroup.


class CgroupLimitError(AdminError):
    pass

# Errors processing cgroup.


class CgroupProcessingError(ProcessingError):
    pass

# ============================================================================
# Utility functions
# ============================================================================

#
# FUNCTION caller_name
#
# Return the name of the calling function or method.
#


def caller_name():
    return str(sys._getframe(1).f_code.co_name)

#
# FUNCTION convert_size
#
# Convert a string containing a size specification (e.g. "1m") to a
# string using different units (e.g. "1024k").
#
# This function only interprets a decimal number at the start of the string,
# stopping at any unrecognized character and ignoring the rest of the string.
#
# When down-converting (e.g. MB to KB), all calculations involve integers and
# the result returned is exact. When up-converting (e.g. KB to MB) floating
# point numbers are involved. The result is rounded up. For example:
#
# 1023MB -> GB yields 1g
# 1024MB -> GB yields 1g
# 1025MB -> GB yields 2g  <-- This value was rounded up
#
# Pattern matching or conversion may result in exceptions.
#


def convert_size(value, units='b'):
    logs = {'b': 0, 'k': 10, 'm': 20, 'g': 30,
            't': 40, 'p': 50, 'e': 60, 'z': 70, 'y': 80}
    try:
        new = units[0].lower()
        if new not in logs.keys():
            new = 'b'
        val, old = re.match('([-+]?\d+)([bkmgtpezy]?)',
                            str(value).lower()).groups()
        val = int(val)
        if val < 0:
            raise ValueError('Value may not be negative')
        if old not in logs.keys():
            old = 'b'
        factor = logs[old] - logs[new]
        val *= 2 ** factor
        slop = val - int(val)
        val = int(val)
        if slop > 0:
            val += 1
        # pbs.size() does not like units following zero
        if val <= 0:
            return '0'
        else:
            return str(val) + new
    except:
        return None

#
# FUNCTION size_as_int
#
# Convert a size string to an integer representation of size in bytes
#


def size_as_int(value):
    return int(convert_size(value).rstrip(string.ascii_lowercase))

#
# FUNCTION convert_time
#
# Converts a integer value for time into the value of the return unit
#
# A valid decimal number, with optional sign, may be followed by a character
# representing a scaling factor.  Scaling factors may be either upper or
# lower case. Examples include:
# 250ms
# 40s
# +15min
#
# Valid scaling factors are:
# ns  = 10**-9
# us  = 10**-6
# ms  = 10**-3
# s   =      1
# min =     60
# hr  =   3600
#
# Pattern matching or conversion may result in exceptions.
#


def convert_time(value, return_unit='s'):
    multipliers = {'':  1, 'ns': 10 ** -9, 'us': 10 ** -6,
                   'ms': 10 ** -3, 's': 1, 'min': 60, 'hr': 3600}
    n, factor = re.match('([-+]?\d+)(\w*[a-zA-Z])?',
                         str(value).lower()).groups(0)

    # Check to see if there was not unit of time specified
    if factor == 0:
        factor = ''

    # Check to see if the unit is valid
    if str.lower(factor) not in multipliers.keys():
        raise ValueError('Time unit not recognized.')

    # Convert the value to seconds
    value_in_sec = float(n) * float(multipliers[str.lower(factor)])
    if return_unit != 's':
        return value_in_sec / multipliers[str.lower(return_unit)]
    else:
        return float('%lf' % value_in_sec)

# simplejson hook to convert lists from unicode to utf-8


def decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        rv.append(item)
    return rv

# simplejson hook to convert dictionaries from unicode to utf-8


def decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        rv[key] = value
    return rv

# Convert CPU list format (with ranges) to a Python list


def cpus2list(s):
    # The input string is a comma separated list of digits and ranges.
    # Examples include:
    # 0-3,8-11
    # 0,2,4,6
    # 2,5-7,10
    cpus = []
    if s.strip() == '':
        return cpus
    for r in s.split(','):
        if '-' in r[1:]:
            start, end = r.split('-', 1)
            for i in range(int(start), int(end) + 1):
                cpus.append(int(i))
        else:
            cpus.append(int(r))
    return cpus


# Helper function to ignore suspended jobs when removing
# "already used" resources
def job_to_be_ignored(jobid):
    # Get job substate from small utility that calls printjob
    pbs_exec = ''
    if not CRAY_12_BRANCH:
        pbs_conf = pbs.get_pbs_conf()
        pbs_exec = pbs_conf['PBS_EXEC']
    else:
        if 'PBS_EXEC' in self.cfg:
            pbs_exec = self.cfg['PBS_EXEC']
        else:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "PBS_EXEC needs to be defined in the config file")
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Exiting the cgroups hook")
            pbs.event().accept()

    printjob_cmd = pbs_exec+os.sep+'bin'+os.sep+'printjob'

    cmd = [printjob_cmd, jobid]

    substate = None
    try:
        pbs.logmsg(pbs.EVENT_DEBUG3, "cmd: %s" % cmd)
        # Collect the job substate information
        process = subprocess.Popen(
                                   cmd,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        (out, err) = process.communicate()
        # Find the job substate
        substate_re = re.compile(r"substate:\s+(?P<jobstate>\S+)\s+")
        substate = substate_re.search(out)
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "Unexpected error in job_to_be_ignored: %s" %
                   ' '.join([repr(sys.exc_info()[0]),
                            repr(sys.exc_info()[1])]))
        out = "Unknown: failed to run " + printjob_cmd

    if substate is not None:
        substate = substate.group().split(':')[1].strip()
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Job %s has substate %s" % (jobid, substate))

        suspended_substates = ['0x2b', '0x2d', 'unknown']
        return (substate in suspended_substates)
    else:
        return False


# ============================================================================
# Utility classes
# ============================================================================

#
# CLASS HookUtils
#


class HookUtils:

    def __init__(self, hook_events=None):
        if hook_events is not None:
            self.hook_events = hook_events
        else:
            self.hook_events = {
                # Defined in the order they appear in module_pbs_v1.c
                pbs.QUEUEJOB: {
                    'name': 'queuejob',
                    'handler': None
                },
                pbs.MODIFYJOB: {
                    'name': 'modifyjob',
                    'handler': None
                },
                pbs.RESVSUB: {
                    'name': 'resvsub',
                    'handler': None
                },
                pbs.MOVEJOB: {
                    'name': 'movejob',
                    'handler': None
                },
                pbs.RUNJOB: {
                    'name': 'runjob',
                    'handler': None
                },
                pbs.PROVISION: {
                    'name': 'provision',
                    'handler': None
                },
                pbs.EXECJOB_BEGIN: {
                    'name': 'execjob_begin',
                    'handler': self.__execjob_begin_handler
                },
                pbs.EXECJOB_PROLOGUE: {
                    'name': 'execjob_prologue',
                    'handler': None
                },
                pbs.EXECJOB_EPILOGUE: {
                    'name': 'execjob_epilogue',
                    'handler': self.__execjob_epilogue_handler
                },
                pbs.EXECJOB_PRETERM: {
                    'name': 'execjob_preterm',
                    'handler': None
                },
                pbs.EXECJOB_END: {
                    'name': 'execjob_end',
                    'handler': self.__execjob_end_handler
                },
                pbs.EXECJOB_LAUNCH: {
                    'name': 'execjob_launch',
                    'handler': self.__execjob_launch_handler
                },
                pbs.EXECHOST_PERIODIC: {
                    'name': 'exechost_periodic',
                    'handler': self.__exechost_periodic_handler
                },
                pbs.EXECHOST_STARTUP: {
                    'name': 'exechost_startup',
                    'handler': self.__exechost_startup_handler
                },
                pbs.MOM_EVENTS: {
                    'name': 'mom_events',
                    'handler': None
                },
            }

            if not CRAY_12_BRANCH:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "CRAY 12 Branch: %s" % (CRAY_12_BRANCH))
                self.hook_events[pbs.EXECJOB_ATTACH] = {
                    'name': 'execjob_attach',
                    'handler': self.__execjob_attach_handler
                }

    def __repr__(self):
        return "HookUtils(%s)" % (repr(self.hook_events))

    def event_name(self, type):
        if type in self.hook_events:
            return self.hook_events[type]['name']
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "%s: Type: %s not found" % (caller_name(), type))
            return None

    def hashandler(self, type):
        if type in self.hook_events:
            return self.hook_events[type]['handler'] is not None
        else:
            return None

    def invoke_handler(self, event, cgroup, jobutil, *args):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: UID: real=%d, effective=%d" %
                   (caller_name(), os.getuid(), os.geteuid()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: GID: real=%d, effective=%d" %
                   (caller_name(), os.getgid(), os.getegid()))
        if self.hashandler(event.type):
            result = self.hook_events[event.type][
                'handler'](event, cgroup, jobutil, *args)
            return result
        else:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: %s event not handled by this hook." %
                       (caller_name(), self.event_name(event.type)))

    def __execjob_begin_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Instantiate the NodeConfig class for get_memory_on_node and
        # get_vmem_on node
        node = NodeConfig(cgroup.cfg)
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: NodeConfig class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: %s" % (caller_name(), repr(node)))
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Host assigned job resources: %s" %
                   (caller_name(), jobutil.host_resources))

        # Make sure the parent cgroup directories exist
        cgroup.create_paths()

        # Make sure that any old cgroups created in an earlier attempt
        # at creating or running the job are gone
        cgroup.delete(e.job.id)

        # Gather the assigned resources
        cgroup.gather_assigned_resources()
        # Create the cgroup(s) for the job
        cgroup.create_job(e.job.id, node)
        # Configure the new cgroup
        cgroup.configure_job(e.job.id, jobutil.host_resources, node)
        # Initialize resource usage for the job
        cgroup.update_job_usage(e.job.id, e.job.resources_used)
        # Write out the assigned resources
        cgroup.write_out_cgroup_host_assigned_resources(e.job.id)
        # Write out the environment variable for the host (pbs_attach)
        if 'devices_name' in cgroup.host_assigned_resources:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Devices: %s" %
                       cgroup.host_assigned_resources['devices_name'])
            env_list = list()
            if len(cgroup.host_assigned_resources['devices_name']) > 0:
                line = str()
                mics = list()
                gpus = list()
                for key in cgroup.host_assigned_resources['devices_name']:
                    if key.startswith('mic'):
                        mics.append(key[3:])
                    elif key.startswith('nvidia'):
                        gpus.append(key[6:])
                if len(mics) > 0:
                    env_list.append('OFFLOAD_DEVICES="%s"' %
                                    string.join(mics, ','))
                if len(gpus) > 0:
                    # don't put quotes around the values. ex "0" or "0,1".
                    # This will cause it to fail.
                    env_list.append('CUDA_VISIBLE_DEVICES=%s' %
                                    string.join(gpus, ','))

            pbs.logmsg(pbs.EVENT_DEBUG, "ENV_LIST: %s" % env_list)
            cgroup.write_out_cgroup_host_job_env_file(e.job.id, env_list)
        return True

    def __execjob_epilogue_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # The resources_used information has a base type of pbs_resource
        # Set the usage data
        cgroup.update_job_usage(e.job.id, e.job.resources_used)
        return True

    def __execjob_end_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Delete the cgroup(s) for the job
        cgroup.delete(e.job.id)
        # Remove the host_assigned_resources and job_env file
        for filename in [cgroup.hook_storage_dir+os.sep+e.job.id,
                         cgroup.host_job_env_filename % e.job.id]:
            try:
                os.remove(filename)
            except OSError:
                pbs.logmsg(pbs.EVENT_DEBUG3, "File: %s not found" % (filename))
            except:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Error removing file: %s" % (filename))
                pass

        return True

    def __execjob_launch_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Add the parent process id to the appropriate cgroups.
        cgroup.add_pids(os.getppid(), jobutil.job.id)
        # FUTURE: Add environment variable to the job environment
        # if job requested mic or gpu
        cgroup.read_in_cgroup_host_assigned_resources(e.job.id)
        if cgroup.host_assigned_resources is not None:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "host_assigned_resources: %s" %
                       (cgroup.host_assigned_resources))
            cgroup.setup_job_devices_env()
        return True

    def __exechost_periodic_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Cleanup cgroups for jobs not present on this node
        count = cgroup.cleanup_orphans(e.job_list)
        if ('periodic_resc_update' in cgroup.cfg and
                cgroup.cfg['periodic_resc_update']):
            for job in e.job_list.keys():
                pbs.logmsg(pbs.EVENT_DEBUG, "%s: job is %s" %
                           (caller_name(), job))
                cgroup.update_job_usage(job, e.job_list[job].resources_used)
        # Online nodes that were offlined due to a cgroup not cleaning up
        if count == 0 and cgroup.cfg['online_offlined_nodes']:
            vnode = pbs.event().vnode_list[cgroup.hostname]
            if os.path.isfile(cgroup.offline_file):
                line = 'Orphan cgroup(s) have been cleaned up. '

                # Check with the pbs server to see if the node comment matches
                try:
                    tmp_comment = pbs.server().vnode(cgroup.hostname).comment
                except:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "Unable to contact server for node comment")
                    tmp_comment = None
                if tmp_comment == cgroup.offline_msg:
                    line += 'Will bring the node back online'
                    vnode.state = pbs.ND_FREE
                    vnode.comment = None
                else:
                    line += 'However, the comment has changed since the node '
                    line += 'was offlined. Node will remain offline'

                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s: %s" % (caller_name(), line))
                # Remove file
                os.remove(cgroup.offline_file)
        return True

    def __exechost_startup_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        cgroup.create_paths()
        node = NodeConfig(cgroup.cfg)
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: NodeConfig class instantiated" %
                   (caller_name()))

        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: %s" % (caller_name(), repr(node)))
        node.create_vnodes()
        if 'memory' in cgroup.subsystems:
            val = node.get_memory_on_node(cgroup.cfg)
            if val is not None:
                if 'vnode_per_numa_node' in cgroup.cfg:
                    if not cgroup.cfg['vnode_per_numa_node']:
                        hn = node.hostname
                        e.vnode_list[hn].resources_available['mem'] = \
                            pbs.size(val)
                        val_cpus = node.totalcpus
                        if val_cpus is not None:
                            e.vnode_list[hn].resources_available['ncpus'] = \
                                int(val_cpus)
                cgroup.set_node_limit('mem', val)
        if 'memsw' in cgroup.subsystems:
            val = node.get_vmem_on_node(cgroup.cfg)
            if val is not None:
                e.vnode_list[node.hostname].resources_available['vmem'] = \
                    pbs.size(val)
                cgroup.set_node_limit('vmem', val)
        if 'hugetlb' in cgroup.subsystems:
            val = node.get_hpmem_on_node(cgroup.cfg)
            if val is not None:
                e.vnode_list[node.hostname].resources_available['hpmem'] = \
                    pbs.size(val)
                cgroup.set_node_limit('hpmem', val)
        return True

    def __execjob_attach_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logjobmsg(jobutil.job.id, "%s: Attaching PID %s" %
                      (caller_name(), e.pid))
        # Add the job process id to the appropriate cgroups.
        cgroup.add_pids(e.pid, jobutil.job.id)
        return True

#
# CLASS ShallIRunUtils
#


class ShallIRunUtils:

    def __init__(self, hostname, cfg):
        self.cfg = cfg
        self.hostname = hostname

    def allow_users(self, allow_users):
        """ This still needs to be defined """
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pass

    def exclude_hosts(self, exclude_hosts):
        """
        Gets the hostname for the node and checks to see if the hook should
        run on this node
        """
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        hostname = pbs.get_local_nodename()
        # check to see if hostname is in the exclude_hosts list
        if self.hostname in exclude_hosts:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: exclude host %s is in %s" %
                       (caller_name(), self.hostname, exclude_hosts))
            pbs.event().accept()

        # check to see if it regex syntax is used
        pass

    def exclude_vntypes(self, exclude_vntypes):
        """
        Gets the vntype for the node and checks to see if the hook should
        run on this node
        """
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        vntype = None

        # look for on file on the mom until we can pass the vntype to the hook
        pbs_home = ''
        if not CRAY_12_BRANCH:
            pbs_conf = pbs.get_pbs_conf()
            pbs_home = pbs_conf['PBS_HOME']
        else:
            if 'PBS_HOME' in self.cfg:
                pbs_home = self.cfg['PBS_HOME']
            else:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "PBS_HOME needs to be defined in the config file")
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "Exiting the cgroups hook")
                pbs.event().accept()

        vntype_file = pbs_home+os.sep+'mom_priv'+os.sep+'vntype'
        if os.path.isfile(vntype_file):
            fdata = open(vntype_file).readlines()
            if len(fdata) > 0:
                vntype = fdata[0].strip()
                pbs.logmsg(pbs.EVENT_DEBUG3, "vntype: %s" % vntype)
        if vntype is None:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "vntype is set to %s" % (vntype))
        elif vntype in exclude_vntypes:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "vntype: %s is in %s" % (vntype, exclude_vntypes))
            pbs.logmsg(pbs.EVENT_DEBUG3, "Exiting Hook")
            pbs.event().accept()
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "vntype: %s not in global exclude: %s" %
                       (vntype, exclude_vntypes))
        pass

    def run_only_on_hosts(self, approved_hosts):
        """
        Gets the list of approved nodes to run on and checks to see if the hook
        should run on this node
        """
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Approved hosts: %s, %s" %
                   (type(approved_hosts), approved_hosts))

        # check to see if hostname is in the approved_hosts list
        if approved_hosts == []:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "approved hosts list is empty: %s" % approved_hosts)
        elif self.hostname not in approved_hosts:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "%s is not in the approved list of hosts: %s" %
                       (self.hostname, approved_hosts))
            pbs.event().accept()

        else:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "%s in list of approved hosts: %s" %
                       (self.hostname, approved_hosts))

#
# CLASS JobUtils
#


class JobUtils:

    def __init__(self, job, hostname=None, resources=None):
        self.job = job
        self.host_vnodes = list()
        if hostname is not None:
            self.hostname = hostname
        else:
            self.hostname = pbs.get_local_nodename()
        if resources is not None:
            self.host_resources = resources
        else:
            self.host_resources = self.__host_assigned_resources()

    def __repr__(self):
        return "JobUtils(%s, %s, %s)" % (repr(self.job), repr(self.hostname),
                                         repr(self.host_resources))

    # Return a dictionary of resources assigned to the local node
    def __host_assigned_resources(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Bail out if no hostname was provided
        if self.hostname is None:
            raise CgroupProcessingError('No hostname available')
        # Bail out if no job information is present
        if self.job is None:
            raise CgroupProcessingError('No job information available')
        # Determine which vnodes are on this host, if any
        if self.hostname is not None:
            vnhost_pattern = "%s\[[\d+]\]" % self.hostname
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: vnhost pattern: %s" %
                       (caller_name(), vnhost_pattern))
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Job exec_vnode list: %s" %
                       (caller_name(), self.job.exec_vnode))
            for match in re.findall(vnhost_pattern, str(self.job.exec_vnode)):
                self.host_vnodes.append(match)
            if self.host_vnodes is not None:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s: Associate %s to vnodes on %s" %
                           (caller_name(), self.host_vnodes, self.hostname))

        # Collect host assigned resources
        resources = {}
        for chunk in self.job.exec_vnode.chunks:
            vnode = False
            if self.host_vnodes == [] and chunk.vnode_name != self.hostname:
                continue
            elif self.host_vnodes != [] and \
                    chunk.vnode_name not in self.host_vnodes:
                continue
            elif chunk.vnode_name in self.host_vnodes:
                vnode = True
                if 'vnodes' not in resources:
                    resources['vnodes'] = {}
                if chunk.vnode_name not in resources['vnodes']:
                    resources['vnodes'][chunk.vnode_name] = {}
                # This check is needed since not all resources are
                # required to be in each chunk of a job
                # i.e. exec_vnodes =
                # (node1[0]:ncpus=4:mem=4gb+node1[1]:mem=2gb) +
                # (node1[1]:ncpus=3+node[0]:ncpus=1:mem=4gb)
                if all(resc in resources['vnodes'][chunk.vnode_name]
                       for resc in chunk.chunk_resources.keys()):
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "%s: resources already defined" %
                               (caller_name()))
                    pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s,\t%s" %
                               (caller_name(),
                                chunk.chunk_resources.keys(),
                                resources['vnodes'][chunk.vnode_name].keys()))
                else:
                    # Initialize resources for each vnode
                    for resc in chunk.chunk_resources.keys():
                        # Initialize the new value
                        if isinstance(chunk.chunk_resources[resc],
                                      pbs.pbs_int):
                            resources['vnodes'][chunk.vnode_name][resc] = \
                                      pbs.pbs_int(0)
                        elif isinstance(chunk.chunk_resources[resc],
                                        pbs.pbs_float):
                            resources['vnodes'][chunk.vnode_name][resc] = \
                                      pbs.pbs_float(0)
                        elif isinstance(chunk.chunk_resources[resc], pbs.size):
                            resources['vnodes'][chunk.vnode_name][resc] = \
                                      pbs.size('0')

            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Chunk %s" %
                       (caller_name(), chunk.vnode_name))
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: resources: %s" %
                       (caller_name(), resources))
            for resc in chunk.chunk_resources.keys():
                if resc not in resources.keys():
                    # Initialize the new value
                    if isinstance(chunk.chunk_resources[resc], pbs.pbs_int):
                        resources[resc] = pbs.pbs_int(0)
                    elif isinstance(chunk.chunk_resources[resc],
                                    pbs.pbs_float):
                        resources[resc] = pbs.pbs_float(0.0)
                    elif isinstance(chunk.chunk_resources[resc], pbs.size):
                        resources[resc] = pbs.size('0')
                # Add resource value to total
                if type(chunk.chunk_resources[resc]) in \
                        [pbs.pbs_int, pbs.pbs_float, pbs.size]:
                    resources[resc] += chunk.chunk_resources[resc]
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "%s: resources[%s][%s] is now %s" %
                               (caller_name(), self.hostname, resc,
                                resources[resc]))
                    if vnode is True:
                        resources['vnodes'][chunk.vnode_name][resc] += \
                                  chunk.chunk_resources[resc]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "%s: Setting resource %s to string %s" %
                               (caller_name(), resc,
                                str(chunk.chunk_resources[resc])))
                    resources[resc] = str(chunk.chunk_resources[resc])
                    if vnode is True:
                        resources['vnodes'][chunk.vnode_name][resc] = \
                                  str(chunk.chunk_resources[resc])
        if not resources:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: No resources assigned to host %s" %
                       (caller_name(), self.hostname))
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Resources for %s: %s" %
                       (caller_name(), self.hostname, repr(resources)))

        # Return assigned resources for specified host
        pbs.logmsg(pbs.EVENT_DEBUG3, "Job Resources: %s" % (resources))
        return resources

    # Write a message to the job stdout file
    def write_to_stderr(self, job, msg):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        try:
            filename = job.stderr_file()
            if filename is None:
                return
            fd = open(filename, 'a')
            fd.write(msg)
        except Exception, exc:
            pass

    # Write a message to the job stdout file
    def write_to_stdout(self, job, msg):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        try:
            filename = job.stdout_file()
            if filename is None:
                return
            fd = open(filename, 'a')
            fd.write(msg)
        except Exception, exc:
            pass

#
# CLASS NodeConfig
#


class NodeConfig:

    def __init__(self, cfg, **kwargs):

        self.cfg = cfg
        hostname = None
        meminfo = None
        numa_nodes = None
        devices = None
        hyperthreading = None
        self.hyperthreads_per_core = 1
        self.totalcpus = self.__discover_cpus()

        pbs_home = ''
        if not CRAY_12_BRANCH:
            pbs_conf = pbs.get_pbs_conf()
            pbs_home = pbs_conf['PBS_HOME']
        else:
            if 'PBS_HOME' in self.cfg:
                pbs_home = self.cfg['PBS_HOME']
            else:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "PBS_HOME needs to be defined in the config file")
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "Exiting the cgroups hook")
                pbs.event().accept()

        self.host_mom_jobdir = pbs_home+'/mom_priv/jobs'

        if kwargs:
            for arg, val in kwargs.items():
                if arg == 'cfg':
                    cfg = val
                elif arg == 'hostname':
                    hostname = val
                elif arg == 'meminfo':
                    meminfo = val
                elif arg == 'numa_nodes':
                    numa_nodes = val
                elif arg == 'devices':
                    devices = val
                elif arg == 'hyperthreading':
                    hyperthreading = val

        if hostname is not None:
            self.hostname = hostname
        else:
            self.hostname = pbs.get_local_nodename()
        if meminfo is not None:
            self.meminfo = meminfo
        else:
            self.meminfo = self.__discover_meminfo()
        if numa_nodes is not None:
            self.numa_nodes = numa_nodes
        else:
            self.numa_nodes = self.__discover_numa_nodes()
        if devices is not None:
            self.devices = devices
        else:
            self.devices = self.__discover_devices()
        if hyperthreading is not None:
            self.hyperthreading = hyperthreading
        else:
            self.hyperthreading = self.__hyperthreading_enabled()

        # Add the devices count i.e. nmics and ngpus to the numa nodes
        self.__add_devices_to_numa_node()

    def __repr__(self):
        return ("NodeConfig(%s, %s, %s, %s, %s, %s)" %
                (repr(self.cfg), repr(self.hostname), repr(self.meminfo),
                 repr(self.numa_nodes), repr(self.devices),
                 repr(self.hyperthreading)))

    def __add_devices_to_numa_node(self):
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Node Devices: %s" % (self.devices.keys()))
        for device in self.devices.keys():
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "%s: Device Names: %s" % (caller_name(), device))
            if device == 'mic' or device == 'gpu':
                pbs.logmsg(pbs.EVENT_DEBUG3, "Devices: %s" %
                           (self.devices[device].keys()))
                for device_name in self.devices[device]:
                    device_socket = \
                        self.devices[device][device_name]['numa_node']
                    if device == 'mic':
                        if 'nmics' not in self.numa_nodes[device_socket]:
                            self.numa_nodes[device_socket]['nmics'] = 1
                        else:
                            self.numa_nodes[device_socket]['nmics'] += 1
                    elif device == 'gpu':
                        if 'ngpus' not in self.numa_nodes[device_socket]:
                            self.numa_nodes[device_socket]['ngpus'] = 1
                        else:
                            self.numa_nodes[device_socket]['ngpus'] += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Numa Nodes: %s" % (self.numa_nodes))

    # Discover what type of hardware is on this node and how is it partitioned
    def __discover_numa_nodes(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        numa_nodes = {}
        for dir in glob.glob(os.path.join(os.sep,
                             "sys", "devices", "system", "node", "node*")):
            id = int(dir.split(os.sep)[5][4:])
            if id not in numa_nodes.keys():
                numa_nodes[id] = {}
                numa_nodes[id]['devices'] = list()
            numa_nodes[id]['cpus'] = open(os.path.join(dir, "cpulist"),
                                          'r').readline().strip()
            with open(os.path.join(dir, "meminfo"), 'r') as fd:
                for line in fd:
                    # Each line will contain four or five fields. Examples:
                    # Node 0 MemTotal:       32995028 kB
                    # Node 0 HugePages_Total:     0
                    entries = line.split()
                    if len(entries) < 4:
                        continue
                    if entries[2] == "MemTotal:":
                        numa_nodes[id][entries[2].rstrip(':')] = \
                            convert_size(entries[3] + entries[4], 'kb')
                    elif entries[2] == "HugePages_Total:":
                        numa_nodes[id][entries[2].rstrip(':')] = entries[3]
        pbs.logmsg(pbs.EVENT_DEBUG3, "Discover Numa Nodes: %s" % numa_nodes)
        return numa_nodes

    # Identify devices and to which numa nodes they are attached
    def __discover_devices(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        devices = {}
        for file in glob.glob(os.path.join(os.sep, "sys", "class", "*", "*",
                                           "device", "numa_node")):
            # The file should contain a single integer
            numa_node = int(open(file, 'r').readline().strip())
            if numa_node < 0:
                numa_node = 0
            dirs = file.split(os.sep)
            name = dirs[3]
            instance = dirs[4]
            if name not in devices.keys():
                devices[name] = {}
            devices[name][instance] = {}
            devices[name][instance]['numa_node'] = numa_node
            if name == 'mic':
                s = os.stat('/dev/%s' % instance)
                devices[name][instance]['major'] = os.major(s.st_rdev)
                devices[name][instance]['minor'] = os.minor(s.st_rdev)
                devices[name][instance]['device_type'] = 'c'

        # Check to see if there are gpus on the node
        gpus = self.discover_gpus()
        if isinstance(gpus, dict) and len(gpus.keys()) > 0:
            devices['gpu'] = gpus['gpu']

        pbs.logmsg(pbs.EVENT_DEBUG3, "Discovered devices: %s" % (devices))
        return devices

    def discover_gpus(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        try:
            # Check to see if nvidia-smi exists and produces valid output
            cmd = ['/usr/bin/nvidia-smi', '-q', '-x']
            if 'nvidia-smi' in self.cfg:
                cmd[0] = self.cfg['nvidia-smi']

            pbs.logmsg(pbs.EVENT_DEBUG3, "cmd: %s" % cmd)
            # Collect the gpu information
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            output, err = process.communicate()

            # pbs.logmsg(pbs.EVENT_DEBUG3,"output: %s" % output)
            # import the xml library and parse the output
            import xml.etree.ElementTree as ET

            # Parse the data
            name = 'gpu'
            gpu_data = dict()
            gpu_data[name] = {}
            root = ET.fromstring(output)
            pbs.logmsg(pbs.EVENT_DEBUG3, "root.tag: %s" % root.tag)
            for child in root:
                if child.tag == "attached_gpus":
                    # gpu_data['ngpus'] = int(child.text)
                    pass
                if child.tag == "gpu":
                    device_id = child.get('id')
                    number = 'nvidia%s' % child.find('minor_number').text
                    gpu_data[name][number] = dict()
                    gpu_data[name][number]['id'] = device_id

                    # Determine which socket the device is on
                    filename = '/sys/bus/pci/devices/%s/numa_node' % \
                        device_id.lower()
                    isfile = os.path.isfile(filename)
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "%s, %s" % (filename, isfile))
                    if isfile:
                        numa_node = open(filename).read().strip()
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "numa_node: %s" % (numa_node))
                        if int(numa_node) == -1:
                            numa_node = 0
                        gpu_data[name][number]['numa_node'] = int(numa_node)
                        try:
                            dev_filename = '/dev/%s' % number
                            s = os.stat(dev_filename)
                        except OSError:
                            pbs.logmsg(pbs.EVENT_DEBUG,
                                       "Unable to find %s" % dev_filename)
                        except:
                            pbs.logmsg(pbs.EVENT_DEBUG,
                                       "Unexpected error: %s" %
                                       sys.exc_info()[0])
                        gpu_data[name][number]['major'] = os.major(s.st_rdev)
                        gpu_data[name][number]['minor'] = os.minor(s.st_rdev)
                        gpu_data[name][number]['device_type'] = 'c'
            pbs.logmsg(pbs.EVENT_DEBUG, "%s" % gpu_data)
            return gpu_data
        except OSError:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Unable to find %s" % string.join(cmd, " "))
            return {'gpu': {}}
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Unexpected error: %s" % sys.exc_info()[0])

        return {'gpu': {}}

    # Get the memory info on this host
    def __discover_meminfo(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        meminfo = {}
        with open(os.path.join(os.sep, "proc", "meminfo"), 'r') as fd:
            for line in fd:
                entries = line.split()
                if entries[0] == "MemTotal:":
                    meminfo[entries[0].rstrip(':')] = \
                        convert_size(entries[1] + entries[2], 'kb')
                elif entries[0] == "SwapTotal:":
                    meminfo[entries[0].rstrip(':')] = \
                        convert_size(entries[1] + entries[2], 'kb')
                elif entries[0] == "Hugepagesize:":
                    meminfo[entries[0].rstrip(':')] = \
                        convert_size(entries[1] + entries[2], 'kb')
                elif entries[0] == "HugePages_Total:":
                    meminfo[entries[0].rstrip(':')] = int(entries[1])
                elif entries[0] == "HugePages_Rsvd:":
                    meminfo[entries[0].rstrip(':')] = int(entries[1])
        pbs.logmsg(pbs.EVENT_DEBUG3, "Discover meminfo: %s" % meminfo)
        return meminfo

    # Determine if the cpus have hyperthreading enabled
    def __hyperthreading_enabled(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        rc = False
        with open(os.path.join(os.sep, "proc", "cpuinfo"), 'r') as fd:
            siblings = 0
            cpu_cores = 0
            for line in fd:
                entries = line.strip().split(":")
                if len(entries) < 1:
                    continue
                elif entries[0].strip() == "siblings":
                    pbs.logmsg(pbs.EVENT_DEBUG3, "%s: line: %s" %
                               (caller_name(), entries))
                    siblings = entries[1].strip()
                elif entries[0].strip() == "cpu cores":
                    pbs.logmsg(pbs.EVENT_DEBUG3, "%s: line: %s" %
                               (caller_name(), entries))
                    cpu_cores = entries[1].strip()
                elif entries[0].strip() == "flags":
                    flag_options = entries[1].split()
                    pbs.logmsg(pbs.EVENT_DEBUG3, "%s: flag_options: %s" %
                               (caller_name(), flag_options))
                    if "ht" in flag_options:
                        rc = True
                        break
        if rc is True:
            self.hyperthreads_per_core = int(siblings)/int(cpu_cores)
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: hyperthreads/core: %d" %
                       (caller_name(), self.hyperthreads_per_core))
            if self.hyperthreads_per_core == 1:
                rc = False
        return rc

    def __discover_cpus(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        rc = False
        with open(os.path.join(os.sep, "proc", "cpuinfo"), 'r') as fd:
            cpu_threads = 0
            for line in fd:
                entries = line.strip().split(":")
                if len(entries) < 1:
                    continue
                elif entries[0].strip() == "processor":
                    pbs.logmsg(pbs.EVENT_DEBUG3, "%s: line: %s" %
                               (caller_name(), entries))
                    cpu_threads += 1
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: processors found: %d" %
                   (caller_name(), cpu_threads))

        return cpu_threads

    # Gather the jobs running on this node
    def gather_jobs_on_node(self):
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "%s: Method called" % (caller_name()))
        # Get the job list from the server
        jobs = None
        try:
            jobs = pbs.server().vnode(self.hostname).jobs
        except:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Unable to contact server to get jobs")
            return None

        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Jobs from server for %s: %s" % (self.hostname, jobs))

        if jobs is None:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "No jobs found on %s " % (self.hostname))
            return None

        jobs_list = dict()
        for job in jobs.split(','):
            # The job list from the node has a space in front of the job id
            # This must be removed or it will not match the cgroup dir
            jobs_list[job.split('/')[0].strip()] = 0
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Jobs on %s: %s" % (self.hostname, jobs_list.keys()))

        return jobs_list.keys()

    # Gather the jobs running on this node
    def gather_jobs_on_node_local(self):
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Method called" % (caller_name()))
        # Get the job list from the jobs directory
        jobs_list = list()
        try:
            for file in os.listdir(self.host_mom_jobdir):
                if fnmatch.fnmatch(file, "*.JB"):
                    jobs_list.append(file[:-3])
            if not jobs_list:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "No jobs found on %s " % (self.hostname))
                return None
            else:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "Jobs from server for %s: %s" %
                           (self.hostname, repr(jobs_list)))

                return jobs_list
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Could not get job list from mom_priv/jobs for %s" %
                       self.hostname)

            return self.gather_jobs_on_node()

    # Get the memory resource on this mom
    def get_memory_on_node(self, config, MemTotal=None):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Calculate memory
        val = 0
        if MemTotal is None:
            val = size_as_int(self.meminfo['MemTotal'])
            pbs.logmsg(pbs.EVENT_DEBUG3, "val: %s" % val)
        else:
            val = size_as_int(MemTotal)
        if 'percent_reserve' in config['cgroup']['memory']:
            percent_reserve = config['cgroup']['memory']['percent_reserve']
            val -= (val * percent_reserve) / 100
        elif 'reserve_memory' in config['cgroup']['memory'].keys():
            reserve_memory = config['cgroup']['memory']['reserve_memory']
            try:
                pbs.size(reserve_memory)
                reserve_mem = size_as_int(reserve_memory)
                if val > reserve_mem:
                    val -= reserve_mem
                else:
                    val -= size_as_int("100mb")
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Unable to reserve more memory than " +
                               "available on the node. Available %s, " +
                               "Tried to reserve %s. Reserving 100mb" %
                               (val, reserve_mem))

            except:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "%s: Invalid memory reserve value: %s" %
                           (caller_name(), reserve_memory))

        pbs.logmsg(pbs.EVENT_DEBUG3, "Return val: %s" % val)
        return convert_size(str(val), 'kb')

    # Get the virtual memory resource on this mom
    def get_vmem_on_node(self, config, MemTotal=None):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Return the value for memory if no swap is configured
        if size_as_int(self.meminfo['SwapTotal']) <= 0:
            return self.get_memory_on_node(config)
        # Calculate vmem
        val = 0
        if MemTotal is None:
            val = size_as_int(self.meminfo['MemTotal'])
        else:
            val = size_as_int(MemTotal)

        val += size_as_int(self.meminfo['SwapTotal'])
        # Determine if memory needs to be reserved
        if 'percent_reserve' in config['cgroup']['memsw']:
            percent_reserve = config['cgroup']['memsw']['reserve_memory']
            val -= (val * percent_reserve) / 100
        elif 'reserve_memory' in config['cgroup']['memsw']:
            reserve_memory = config['cgroup']['memsw']['reserve_memory']
            try:
                pbs.size(reserve_memory)
                val -= size_as_int(reserve_memory)
            except:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "%s: Invalid memory reserve value: %s" %
                           (caller_name(), reserve_memory))
        return convert_size(str(val), 'kb')

    # Get the huge page memory resource on this mom
    def get_hpmem_on_node(self, config):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        if 'percent_reserve' in config['cgroup']['hugetlb'].keys():
            percent_reserve = config['cgroup']['hugetlb']['percent_reserve']
        else:
            percent_reserve = 0
        # Calculate vmem
        val = size_as_int(self.meminfo['Hugepagesize'])
        val *= (self.meminfo['HugePages_Total'] -
                self.meminfo['HugePages_Rsvd'])
        val -= (val * percent_reserve) / 100
        return convert_size(str(val), 'kb')

    # Create individual vnodes per socket
    def create_vnodes(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        key = "vnode_per_numa_node"
        if key in self.cfg.keys():
            if not self.cfg[key]:
                pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s is false" %
                           (caller_name(), key))
                return
        else:
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s not configured" %
                       (caller_name(), key))
            return

        # Create one vnode per numa node
        vnode_list = pbs.event().vnode_list
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: numa nodes: %s" %
                   (caller_name(), self.numa_nodes))
        # Define the vnodes
        vnode_name = self.hostname
        vnode_list[vnode_name] = pbs.vnode(vnode_name)
        for id in self.numa_nodes.keys():
            vnode_name = self.hostname + "[%d]" % id
            vnode_list[vnode_name] = pbs.vnode(vnode_name)
            for key, val in sorted(self.numa_nodes[id].iteritems()):
                if key == 'cpus':
                    vnode_list[vnode_name].resources_available['ncpus'] = \
                        len(cpus2list(val))/self.hyperthreads_per_core
                    # set the value on the host to 0
                    vnode_list[self.hostname].resources_available['ncpus'] = 0
                elif key == 'MemTotal':
                    mem = self.get_memory_on_node(self.cfg, val)
                    vnode_list[vnode_name].resources_available['mem'] = \
                        pbs.size(mem)
                    # set the value on the host to 0
                    vnode_list[self.hostname].resources_available['mem'] = \
                        pbs.size('0kb')
                elif key == 'HugePages_Total':
                    pass
                elif isinstance(val, list):
                    pass
                elif isinstance(val, dict):
                    pass
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG3, "%s: %s=%s" %
                               (caller_name(), key, val))
                    vnode_list[vnode_name].resources_available[key] = val

                    if isinstance(val, int):
                        vnode_list[self.hostname].resources_available[key] = 0
                    elif isinstance(val, float):
                        vnode_list[self.hostname].resources_available[key] = \
                            0.0
                    elif isinstance(val, pbs.size):
                        vnode_list[self.hostname].resources_available[key] = \
                            pbs.size('0kb')
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: vnode list: %s" %
                   (caller_name(), vnode_list))
        return True

#
# CLASS CgroupUtils
#


class CgroupUtils:
    def __init__(self, hostname, vnode, **kwargs):
        cfg = None
        subsystems = None
        paths = None
        vntype = None
        event = None
        self.assigned_resources = dict()
        self.existing_cgroups = dict()
        self.host_assigned_resources = None
        self.pid_lower_limit = 3

        if kwargs:
            for arg, val in kwargs.items():
                if arg == 'cfg':
                    cfg = val
                elif arg == 'subsystems':
                    subsystems = val
                elif arg == 'paths':
                    paths = val
                elif arg == 'vntype':
                    vntype = val
                elif arg == 'event':
                    event = val

        try:
            self.hostname = hostname
            self.vnode = vnode
            # __check_os will raise an exception if cgroups are not present
            self.__check_os()
            # Read in the config file
            if cfg is not None:
                self.cfg = cfg
            else:
                self.cfg = self.__parse_config_file()

            # Determine if the hook should run or exit
            siru = ShallIRunUtils(self.hostname, self.cfg)
            siru.exclude_hosts(self.cfg['exclude_hosts'])
            siru.exclude_vntypes(self.cfg['exclude_vntypes'])
            siru.run_only_on_hosts(self.cfg['run_only_on_hosts'])

            # Collect the mount points
            if paths is not None:
                self.paths = paths
            else:
                self.paths = self.__set_paths()
            # Define the local vnode type
            if vntype is not None:
                self.vntype = vntype
            else:
                self.vntype = self.__get_vnode_type()
            # Determine which subsystems we care about
            if subsystems is not None:
                self.subsystems = subsystems
            else:
                self.subsystems = self.__target_subsystems()

            # location to store information for the different hook events
            pbs_home = ''
            if not CRAY_12_BRANCH:
                pbs_conf = pbs.get_pbs_conf()
                pbs_home = pbs_conf['PBS_HOME']
            else:
                if 'PBS_HOME' in self.cfg:
                    pbs_home = self.cfg['PBS_HOME']
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "PBS_HOME needs to be defined in the " +
                               "config file")
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "Exiting the cgroups hook")
                    pbs.accept()

            self.hook_storage_dir = pbs_home+'/mom_priv/hooks/hook_data'
            self.host_job_env_dir = pbs_home+'/aux'
            self.host_job_env_filename = self.host_job_env_dir+os.sep+"%s.env"

            # information for offlining nodes
            self.offline_file = \
                pbs_home+os.sep+'mom_priv'+os.sep+'hooks'+os.sep
            self.offline_file += "%s.offline" % pbs.event().hook_name
            self.offline_msg = "Hook %s: " % pbs.event().hook_name
            self.offline_msg += "Unable to clean up one or more cgroups"

        except:
            raise

    def __repr__(self):
        return ("CgroupUtils(%s, %s, %s, %s, %s, %s)" %
                (repr(self.hostname), repr(self.vnode), repr(self.cfg),
                 repr(self.subsystems), repr(self.paths), repr(self.vntype)))

    # Validate the OS type and version
    def __check_os(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Check to see if the platform is linux and the kernel is new enough
        if platform.system() != 'Linux':
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: OS does not support cgroups" %
                       (caller_name()))
            raise CgroupConfigError("OS type not supported")
        rel = map(int,
                  string.split(string.split(platform.release(), '-')[0], '.'))
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "%s: Detected Linux kernel version %d.%d.%d" %
                   (caller_name(), rel[0], rel[1], rel[2]))
        supported = False
        if rel[0] > 2:
            supported = True
        elif rel[0] == 2:
            if rel[1] > 6:
                supported = True
            elif rel[1] == 6:
                if rel[2] >= 28:
                    supported = True
        if not supported:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: Kernel needs to be >= 2.6.28: %s" %
                       (caller_name(), system_info[2]))
            raise CgroupConfigError("OS version not supported")
        return supported

    # Read the config file in json format
    def __parse_config_file(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        config = {}
        # Identify the config file and read in the data
        if 'PBS_HOOK_CONFIG_FILE' in os.environ:
            config_file = os.environ["PBS_HOOK_CONFIG_FILE"]
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Config file is %s" %
                       (caller_name(), config_file))
            try:
                config = json.load(open(config_file, 'r'),
                                   object_hook=decode_dict)
            except IOError:
                raise CgroupConfigError("I/O error reading config file")
            except json.JSONDecodeError:
                raise CgroupConfigError(
                    "JSON parsing error reading config file")
            except Exception:
                raise
        else:
            raise CgroupConfigError("No configuration file present")
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Initial Cgroup Config: %s" %
                   (caller_name(), config))
        # Set some defaults if they are not present
        if 'cgroup_prefix' not in config.keys():
            config['cgroup_prefix'] = 'pbspro'
        if 'periodic_resc_update' not in config.keys():
            config['periodic_resc_update'] = False
        if 'vnode_per_numa_node' not in config.keys():
            config['vnode_per_numa_node'] = False
        if 'online_offlined_nodes' not in config.keys():
            config['online_offlined_nodes'] = False
        if 'exclude_hosts' not in config.keys():
            config['exclude_hosts'] = []
        if 'run_only_on_hosts' not in config.keys():
            config['run_only_on_hosts'] = []
        if 'exclude_vntypes' not in config.keys():
            config['exclude_vntypes'] = []
        if 'cgroup' not in config.keys():
            config['cgroup'] = {}
        else:
            for subsys in config['cgroup']:
                subsystem = config['cgroup'][subsys]
                if 'enabled' not in subsystem.keys():
                    config['cgroup'][subsys]['enabled'] = False
                if 'exclude_hosts' not in subsystem.keys():
                    config['cgroup'][subsys]['exclude_hosts'] = []
                if 'exclude_vntypes' not in subsystem.keys():
                    config['cgroup'][subsys]['exclude_vntypes'] = []

        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "%s: Cgroup Config with defaults: %s" %
                   (caller_name(), config))
        return config

    # Determine which subsystems are being requested
    def __target_subsystems(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        subsystems = []
        for key in self.cfg['cgroup'].keys():
            if self.enabled(key):
                subsystems.append(key)
        if 'memory' not in subsystems:
            if 'memsw' in subsystems:
                # Remove memsw since it must be greater then
                # or equal to memory
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Removing memsw from enabled subsystems")
                subsystems.remove('memsw')
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Enabled subsystems: %s" %
                   (caller_name(), subsystems))
        # It is not an error for all subsystems to be disabled.
        # This host or vnode type may be in the excluded list.
        return subsystems

    # Copy a setting from the parent cgroup
    def __copy_from_parent(self, dest):
        try:
            file = os.path.basename(dest)
            dir = os.path.dirname(dest)
            parent = os.path.dirname(dir)
            source = os.path.join(parent, file)
            if not os.path.isfile(source):
                raise CgroupConfigError('Failed to read %s' % (source))
            self.write_value(dest, open(source, 'r').read().strip())
        except:
            raise

    # Create a dictionary of the cgroup subsystems and their corresponding
    # directories
    def __set_paths(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        paths = {}
        try:
            # Loop through the mounts and collect the ones for cgroups
            with open(os.path.join(os.sep, "proc", "mounts"), 'r') as fd:
                for line in fd:
                    entries = line.split()
                    if len(entries) > 3 and entries[2] == "cgroup":
                        flags = entries[3].split(',')
                        pbs.logmsg(pbs.EVENT_DEBUG,
                                   "subsysdir: %s (flags=%s)" %
                                   (entries[1], flags))
                        for subsys in flags:
                            paths[subsys] = os.path.join(
                                entries[1], self.cfg["cgroup_prefix"])
        except:
            raise
        if len(paths.keys()) < 1:
            raise CgroupConfigError("Cgroup paths not detected")
        # Both the memory and memsw cgroups share the same mount point
        if "memory" in paths.keys():
            paths["memsw"] = paths["memory"]
        return paths

    # Create the cgroup parent directories that will contain the jobs
    def create_paths(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        try:
            # Create the directories that PBS will use to house the jobs
            old_umask = os.umask(0022)
            for subsys in self.subsystems:
                if subsys not in self.paths.keys():
                    raise CgroupConfigError('No path for subsystem: %s' %
                                            (subsys))
                if not os.path.exists(self.paths[subsys]):
                    os.makedirs(self.paths[subsys], 0755)
                    pbs.logmsg(pbs.EVENT_DEBUG, "%s: Created directory %s" %
                               (caller_name(), self.paths[subsys]))
                    if subsys == 'memory' or subsys == 'memsw':
                        # Set file to
                        # <cgroup>/memory/pbspro/memory.use_hierarchy
                        file = os.path.join(self.paths[subsys],
                                            'memory.use_hierarchy')
                        if not os.path.isfile(file):
                            raise CgroupConfigError('Failed to configure %s' %
                                                    (file))
                        self.write_value(file, 1)
                    elif subsys == 'cpuset':
                        self.__copy_from_parent(os.path.join(
                                                self.paths['cpuset'],
                                                'cpuset.cpus'))
                        self.__copy_from_parent(os.path.join(
                                                self.paths['cpuset'],
                                                'cpuset.mems'))

        except:
            raise CgroupConfigError("Failed to create directory: %s" %
                                    (self.paths[subsys]))
        finally:
            os.umask(old_umask)

    # Return the vnode type of the local node
    def __get_vnode_type(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))

        # look for on file on the mom until we can pass the vntype to the hook
        pbs_home = ''
        if not CRAY_12_BRANCH:
            pbs_conf = pbs.get_pbs_conf()
            pbs_home = pbs_conf['PBS_HOME']
        else:
            if 'PBS_HOME' in self.cfg:
                pbs_home = self.cfg['PBS_HOME']
            else:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "PBS_HOME needs to be defined in the config file")
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "Exiting the cgroups hook")

        # File to check for if it is not defined in the hook input file
        vntype_file = pbs_home+os.sep+'mom_priv'+os.sep+'vntype'

        # self.vnode is None for pbs_attach events
        pbs.logmsg(pbs.EVENT_DEBUG3, "vnode: %s" % self.vnode)
        if self.vnode is not None:
            if 'vntype' in self.vnode.resources_available and \
                    self.vnode.resources_available['vntype'] is not None:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "vntype: %s" %
                           self.vnode.resources_available['vntype'])
                return self.vnode.resources_available['vntype']
            else:
                pbs.logmsg(pbs.EVENT_DEBUG3, "vntype file: %s" % vntype_file)
                if os.path.isfile(vntype_file):
                    fdata = open(vntype_file).readlines()
                    if len(fdata) > 0:
                        vntype = fdata[0].strip()
                        pbs.logmsg(pbs.EVENT_DEBUG3, "vntype: %s" % vntype)
                        return vntype
        # If vntype was not set then log a message. It is too expensive
        # to have all moms query the server for large jobs.
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "%s: resources_available.vntype is " % caller_name() +
                   "not set for this vnode")
        return None

    # Gather resources that are already assigned
    def gather_assigned_resources(self):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))

        assigned_resources = {}

        # Gather the cpus and memory sockets assigned
        directories = [x[0] for x in os.walk(self.paths['cpuset'])]

        # Add the existing cgroups to a list to check if assigning
        # resources fail
        for dir in directories[1:]:
            if dir.find(pbs.event().job.id) == -1:
                self.existing_cgroups[dir] = []

        # Check to see if the subsystem is enabled before trying to
        # gather resources
        if 'cpuset' in self.subsystems and \
                self.cfg['cgroup']['cpuset']['enabled']:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Gather cpuset resources from: %s" % directories)
            if len(directories) > 1:
                for dir in directories[1:]:
                    tmp_dir = os.path.split(dir)[-1]
                    if tmp_dir not in assigned_resources:
                        assigned_resources[tmp_dir] = {}
                    path = os.path.join(self.paths['cpuset'], tmp_dir)
                    with open(path+os.sep+'cpuset.cpus') as fd:
                        tmp_val = fd.read()
                        assigned_resources[tmp_dir]['cpuset.cpus'] = \
                            cpus2list(tmp_val.strip())
                    with open(path+os.sep+'cpuset.mems') as fd:
                        tmp_val = fd.read()
                        assigned_resources[tmp_dir]['cpuset.mems'] = \
                            cpus2list(tmp_val.strip())

        # Check to see if the subsystem is enabled before trying
        # to gather resources
        if 'memory' in self.subsystems and \
                self.cfg['cgroup']['memory']['enabled']:
            # Gather the memory assigned for each socket
            directories = [x[0] for x in os.walk(self.paths['memory'])]

            # Add the existing cgroups to a list to check if assigning
            # resources fail
            for dir in directories[1:]:
                self.existing_cgroups[dir] = []

            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Gather memory resources from: %s" % directories)
            if len(directories) > 1:
                for dir in directories[1:]:
                    tmp_dir = os.path.split(dir)[-1]
                    if tmp_dir not in assigned_resources:
                        assigned_resources[tmp_dir] = {}
                    path = os.path.join(self.paths['memory'], tmp_dir)
                    with open(path+os.sep+'memory.limit_in_bytes') as fd:
                        tmp_val = fd.read()
                        assigned_resources[tmp_dir]['memory.limit'] = \
                            tmp_val.strip()
                    tmp_filename = path+os.sep+'memory.memsw.limit_in_bytes'
                    if not os.path.isfile(tmp_filename):
                        continue
                    tmp_filename = path+os.sep+'memory.memsw.limit_in_bytes'
                    with open(tmp_filename) as fd:
                        tmp_val = fd.read()
                        assigned_resources[tmp_dir]['memsw.limit'] = \
                            tmp_val.strip()

        # Check to see if the subsystem is enabled before trying to
        # gather resources
        if 'devices' in self.subsystems and \
                self.cfg['cgroup']['devices']['enabled']:
            # Gather the devices assigned
            directories = [x[0] for x in os.walk(self.paths['devices'])]

            # Add the existing cgroups to a list to check if assigning
            # resources fail
            for dir in directories[1:]:
                self.existing_cgroups[dir] = []

            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Gather device resources from: %s" % directories)
            if len(directories) > 1:
                for dir in directories[1:]:
                    tmp_dir = os.path.split(dir)[-1]
                    pbs.logmsg(pbs.EVENT_DEBUG3, "Dir: %s" % tmp_dir)
                    if tmp_dir not in assigned_resources:
                        assigned_resources[tmp_dir] = {}
                    path = os.path.join(self.paths['devices'], tmp_dir)
                    with open(path+os.sep+'devices.list') as fd:
                        tmp_val = fd.read()
                        assigned_resources[tmp_dir]['devices.list'] = \
                            tmp_val.strip().split('\n')
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "Dir: %s\n\tValue: %s" %
                                   (path, tmp_val.replace('\n', ',')))

        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Gathered assigned resources: %s" % assigned_resources)
        self.assigned_resources = assigned_resources

    # Return whether a subsystem is enabled
    def enabled(self, subsystem):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Check whether the subsystem is enabled in the configuration file
        if subsystem not in self.cfg['cgroup'].keys():
            return False
        if 'enabled' not in self.cfg['cgroup'][subsystem].keys():
            return False
        if not self.cfg['cgroup'][subsystem]['enabled']:
            return False
        # Check whether the cgroup is mounted for this subsystem
        if subsystem not in self.paths.keys():
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: cgroup not mounted for %s" %
                       (caller_name(), subsystem))
            return False
        # Check whether this host is excluded
        # if self.hostname in self.cfg['exclude_hosts']:
        #    pbs.logmsg(pbs.EVENT_DEBUG, "%s: cgroup excluded on host %s" %
        #               (caller_name(), self.hostname))
        #    pbs.event().accept()
        if self.hostname in self.cfg['cgroup'][subsystem]['exclude_hosts']:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: cgroup excluded for subsystem %s on host %s" %
                       (caller_name(), subsystem, self.hostname))
            return False
        # Check whether the vnode type is excluded
        if self.vntype is not None:
            # if self.vntype in self.cfg['exclude_vntypes']:
            #    pbs.logmsg(pbs.EVENT_DEBUG,
            #               "%s: cgroup excluded on vnode type %s" %
            #               (caller_name(), self.vntype))
            #    pbs.event().accept()
            if self.vntype in self.cfg['cgroup'][subsystem]['exclude_vntypes']:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           ("%s: cgroup excluded for " +
                            "subsystem %s on vnode type %s") %
                           (caller_name(), subsystem, self.vntype))
                return False
        return True

    # Return the default value for a subsystem
    def default(self, subsystem):
        if subsystem in self.cfg['cgroup']:
            if 'default' in self.cfg['cgroup'][subsystem]:
                return self.cfg['cgroup'][subsystem]['default']
        return None

    # Check to see if the pid matches the job owners uid
    def is_pid_owned_by_job_owner(self, pid):
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "%s: Method called" % (caller_name()))
        try:
            proc_uid = os.stat('/proc/%d' % pid).st_uid
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       '/proc/%d uid:%d' % (pid, proc_uid))

            job_owner_uid = pwd.getpwnam(pbs.event().job.euser)[2]
            pbs.logmsg(pbs.EVENT_DEBUG3, "Job uid: %d" % job_owner_uid)

            if proc_uid == job_owner_uid:
                return True
            else:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Proc uid: %d != Job owner:  %d" %
                           (proc_uid, job_owner_uid))
        except OSError:
            pbs.logmsg(pbs.EVENT_DEBUG, "Unknown pid: %d" % pid)
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Unexpected error: %s" % sys.exc_info()[0])

        # If we got to this point something did not match up
        return False

    # Add some number of PIDs to the cgroup tasks files for each subsystem
    def add_pids(self, pids, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))

        # make pids a list
        if isinstance(pids, int):
            pids = [pids]

        if pbs.event().type == pbs.EXECJOB_LAUNCH:
            if 1 in pids:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "1 is not a valid pid to add")
                # Hold the job for further review
                e.reject("Hook tried to add pid 1 to the tasks file " +
                         "for job %s" % jobid)

        # check pids to make sure that they are owned by the job owner
        if not CRAY_12_BRANCH:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Not in the Cray 12 Branch")
            pbs.logmsg(pbs.EVENT_DEBUG3, "check to see if execjob_attach")
            if pbs.event().type == pbs.EXECJOB_ATTACH:
                pbs.logmsg(pbs.EVENT_DEBUG3, "event type: attach or launch")
                tmp_pids = list()
                for p in pids:
                    if self.is_pid_owned_by_job_owner(p):
                        tmp_pids.append(p)
                if len(tmp_pids) == 0:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "%d is not a valid pids to add" % p)
                    return False
                else:
                    pids = tmp_pids

        # Determine which subsystems will be used
        for subsys in self.subsystems:
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: subsys = %s" %
                       (caller_name(), subsys))
            # memsw and memory use the same tasks file
            if subsys == "memsw":
                if "memory" in self.subsystems:
                    continue
            path = os.path.join(self.paths[subsys], jobid)
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: path = %s" %
                       (caller_name(), path))
            try:
                tasks_path = os.path.join(path, "tasks")
                for p in pids:
                    self.write_value(tasks_path, p, 'a')
            except IOError, exc:
                raise CgroupLimitError("Failed to add PIDs %s to %s (%s)" %
                                       (str(pids), tasks_path,
                                        errno.errorcode[exc.errno]))
            except:
                raise

    # Set a node limit
    def set_node_limit(self, resource, value):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s = %s" %
                   (caller_name(), resource, value))
        try:
            if resource == 'mem':
                if 'memory' in self.subsystems and \
                        self.cfg['cgroup']['memory']['enabled']:
                    self.write_value(os.path.join(self.paths['memory'],
                                     'memory.limit_in_bytes'),
                                     size_as_int(value))
            elif resource == 'vmem':
                if 'memsw' in self.subsystems and \
                        self.cfg['cgroup']['memsw']['enabled']:
                    self.write_value(os.path.join(self.paths['memsw'],
                                     'memory.memsw.limit_in_bytes'),
                                     size_as_int(value))
            elif resource == 'hpmem':
                if 'hugetlb' in self.subsystems and \
                        self.cfg['cgroup']['hugetlb']['enabled']:
                    self.write_value(glob.glob(os.path.join(
                                     self.paths['hugetlb'],
                                     'hugetlb.*MB.limit_in_bytes'))[0],
                                     size_as_int(value))
            else:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s: Node resource %s not handled" %
                           (caller_name(), resource))
        except:
            raise

    def setup_job_devices_env(self):
        """ Setup the job environment for the devices assigned to the job for an
            execjob_launch hook
         """
        if 'devices_name' in self.host_assigned_resources:
            names = self.host_assigned_resources['devices_name']
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "devices: %s" % (names))
            offload_devices = list()
            cuda_visible_devices = list()
            for name in names:
                if name.startswith('mic'):
                    offload_devices.append(name[3:])
                elif name.startswith('nvidia'):
                    cuda_visible_devices.append(name[6:])
            if len(offload_devices) > 0:
                value = '"%s"' % string.join(offload_devices, ",")
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Environment: %s" % pbs.event().env)
                pbs.event().env['OFFLOAD_DEVICES'] = value
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Post Add: %s" % pbs.event().env)
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "offload_devices: %s" % offload_devices)
            if len(cuda_visible_devices) > 0:
                value = '"%s"' % string.join(cuda_visible_devices, ",")
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Environment: %s" % pbs.event().env)
                pbs.event().env['CUDA_VISIBLE_DEVICES'] = value
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Post Add: %s" % pbs.event().env)
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "cuda_visible_devices: %s" % cuda_visible_devices)
            return [offload_devices, cuda_visible_devices]
        else:
            return False

    def setup_subsys_devices(self, path, node):
        subsys = 'devices'
        # Add the devices that the user is allowed to use
        if subsys in self.cfg['cgroup']:
            devices_allowed = open(os.path.join(path,
                                   "devices.list")).readlines()
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Initial devices.list: %s" %
                       devices_allowed)
            # Deny access to mic and gpu devices
            devices_list = list()
            devices = node.devices
            for device in devices:
                if device == 'mic' or device == 'gpu':
                    for name in devices[device]:
                        d = devices[device][name]
                        devices_list.append("%d:%d" % (d['major'], d['minor']))
            # For CentOS 7 we need to remove a *:* rwm from devices.list
            # before we can add anything to devices.allow. Otherwise our
            # changes are ignored. Check to see if a *:* rwm is in devices.list
            # If so remove it
            if "a *:* rwm\n" in devices_allowed:
                value = "a *:* rwm"
                self.write_value(os.path.join(path, 'devices.deny'), value)

            # Verify that the following devices are not in devices.list
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Removing access to the following: %s" %
                       devices_list)
            for device_str in devices_list:
                value = "c %s rwm" % device_str
                self.write_value(os.path.join(path, 'devices.deny'), value)

            # Add devices back to the list
            devices_allow = list()
            if 'allow' in self.cfg['cgroup'][subsys]:
                devices_allow = self.cfg['cgroup'][subsys]['allow']
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Allowing access to the following: %s" %
                           devices_allow)
                for item in devices_allow:
                    if isinstance(item, str):
                        pbs.logmsg(pbs.EVENT_DEBUG3, "string item: %s" % item)
                        value = "%s" % item
                        self.write_value(os.path.join(
                                         path, 'devices.allow'), value)
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "write_value: %s" % value)
                    elif isinstance(item, list):
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "list item: %s" % item)
                        try:
                            pbs.logmsg(pbs.EVENT_DEBUG3,
                                       "Device allow: %s" % item)
                            stat_filename = '/dev/%s' % item[0]
                            pbs.logmsg(pbs.EVENT_DEBUG3,
                                       "Stat file: %s" % stat_filename)
                            s = os.stat(stat_filename)
                            device_type = None
                            if S_ISBLK(s.st_mode):
                                device_type = "b"
                            elif S_ISCHR(s.st_mode):
                                device_type = "c"
                            if device_type is not None:
                                if len(item) == 3 and isinstance(item[2], str):
                                    value = "%s " % device_type
                                    value += "%s:" % os.major(s.st_rdev)
                                    value += "%s " % item[2]
                                    value += "%s" % item[1]
                                else:
                                    value = "%s " % device_type
                                    value += "%s:" % os.major(s.st_rdev)
                                    value += "%s " % os.minor(s.st_rdev)
                                    value += "%s" % item[1]
                                self.write_value(os.path.join(
                                                path, 'devices.allow'), value)
                                pbs.logmsg(pbs.EVENT_DEBUG3,
                                           "write_value: %s" % value)
                        except OSError:
                            pbs.logmsg(pbs.EVENT_DEBUG,
                                       "Unable to find /dev/%s. " % item[0] +
                                       "Not added to devices.allow!")
                        except:
                            pbs.logmsg(pbs.EVENT_DEBUG,
                                       "Unexpected error: %s" %
                                       sys.exc_info()[0])
                    else:
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "Not sure what to do with: %s" % item)
            devices_allowed = open(os.path.join(
                                   path, "devices.list")).readlines()
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "After setup devices.list: %s" % devices_allowed)

    # Select devices to assign to the job
    def assign_devices(
                       self,
                       device_type,
                       device_list,
                       number_of_devices,
                       node):
        devices = device_list[:number_of_devices]
        device_ids = list()
        device_names = list()
        for device in devices:
            device_info = node.devices[device_type][device]
            if len(device_ids) == 0:
                if device.find("mic") != -1:
                    # Requires the ctrl (0) and the scif (1) to be added
                    device_ids.append("%s %d:0 rwm" %
                                      (device_info['device_type'],
                                       device_info['major']))
                    device_ids.append("%s %d:1 rwm" %
                                      (device_info['device_type'],
                                       device_info['major']))
                elif device.find("nvidia") != -1:
                    # Requires the ctrl (0) and the scif (1) to be added
                    device_ids.append("%s %d:255 rwm" %
                                      (device_info['device_type'],
                                       device_info['major']))
            device_ids.append("%s %d:%d rwm" %
                              (device_info['device_type'],
                               device_info['major'],
                               device_info['minor']))
            device_names.append(device)
        return device_names, device_ids

    # Find the device name
    def get_device_name(self, node, available, socket, major, minor):
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Get device name: major: %s, minor: %s" % (major, minor))
        avail_device = None
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Possible devices: %s" % (available[socket]['devices']))
        for avail_device in available[socket]['devices']:
            avail_major = None
            avail_minor = None
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Checking device: %s" % (avail_device))
            if avail_device.find('mic') != -1:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Check mic device: %s" % (avail_device))
                avail_major = node.devices['mic'][avail_device]['major']
                avail_minor = node.devices['mic'][avail_device]['minor']
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Device major: %s, minor: %s" % (major, minor))
            elif avail_device.find('nvidia') != -1:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Check gpu device: %s" % (avail_device))
                avail_major = node.devices['gpu'][avail_device]['major']
                avail_minor = node.devices['gpu'][avail_device]['minor']
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Device major: %s, minor: %s" % (major, minor))
            if int(avail_major) == int(major) and \
                    int(avail_minor) == int(minor):
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Device match: name: %s, major: %s, minor: %s" %
                           (avail_device, major, minor))
                return avail_device
        pbs.logmsg(pbs.EVENT_DEBUG3, "No match found")
        return None

    # Assign resources to the job based off the vnodes assignments
    def assign_job_resources_by_vnode(self, resources, available, node):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Resources: %s" %
                   (caller_name(), resources))

        # Determine where the resources should be placed
        pbs.logmsg(pbs.EVENT_DEBUG3, "Resources: %s" % (resources))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Available: %s" % (available))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Numa Nodes: %s" % (node.numa_nodes))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Devices: %s" % (node.devices))

        # Loop through the vnodes and assign resources
        assigned = dict()
        assigned['cpuset.cpus'] = list()
        assigned['cpuset.mems'] = list()
        room_on_socket = True

        for vnode in resources['vnodes']:
            regex = re.compile(".*\[(\d+)\].*")
            socket = int(regex.search(vnode).group(1))
            pbs.logmsg(pbs.EVENT_DEBUG3, "Current Vnode: %s" % vnode)
            pbs.logmsg(pbs.EVENT_DEBUG3, "Current socket: %d" % socket)

            if 'ncpus' in resources['vnodes'][vnode]:
                tmp_ncpus = int(resources['vnodes'][vnode]['ncpus'])
                if int(resources['vnodes'][vnode]['ncpus']) <= \
                        len(available[socket]['cpus']):
                    assigned['cpuset.cpus'] += \
                        available[socket]['cpus'][:tmp_ncpus]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficent room on socket: %d" % socket)
                    pbs.logmsg(pbs.EVENT_DEBUG3, "tmp_ncpus: %s" % (tmp_ncpus))
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "available[%d]: %s" %
                               (socket, available[socket]))
                    room_on_socket = False
            if 'mem' in resources['vnodes'][vnode]:
                assigned['cpuset.mems'] += [socket]
            if ('nmics' in resources['vnodes'][vnode] and
               int(resources['vnodes'][vnode]['nmics']) > 0):
                if 'devices_name' not in assigned:
                    assigned['devices_name'] = list()
                    assigned['devices'] = list()
                regex = re.compile(".*(mic).*")
                tmp_nmics = int(resources['vnodes'][vnode]['nmics'])
                mics = [m.group(0)
                        for l in available[socket]['devices']
                        for m in [regex.search(l)] if m]
                if (int(resources['vnodes'][vnode]['nmics']) > 0 and
                   int(resources['vnodes'][vnode]['nmics']) <= len(mics)):
                    tmp_names, tmp_devices = self.assign_devices(
                             'mic', mics[:tmp_nmics], tmp_nmics, node)
                    assigned['devices_name'] += tmp_names
                    assigned['devices'] += tmp_devices
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficent room on socket: %d" % socket)
                    pbs.logmsg(pbs.EVENT_DEBUG3, "tmp_nmics: %s" % (tmp_nmics))
                    pbs.logmsg(pbs.EVENT_DEBUG3, "mics: %s" % (mics))
                    room_on_socket = False
            if ('ngpus' in resources['vnodes'][vnode] and
               int(resources['vnodes'][vnode]['ngpus']) > 0):
                if 'devices_name' not in assigned:
                    assigned['devices_name'] = list()
                    assigned['devices'] = list()
                regex = re.compile(".*(nvidia).*")
                tmp_ngpus = int(resources['vnodes'][vnode]['ngpus'])
                gpus = [m.group(0)
                        for l in available[socket]['devices']
                        for m in [regex.search(l)] if m]
                if (int(resources['vnodes'][vnode]['ngpus']) > 0 and
                   int(resources['vnodes'][vnode]['ngpus']) <= len(gpus)):
                    tmp_names, tmp_devices = self.assign_devices(
                        'gpu', gpus[:tmp_ngpus], tmp_ngpus, node)
                    assigned['devices_name'] += tmp_names
                    assigned['devices'] += tmp_devices
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficent room on socket: %d" % socket)
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "tmp_ngpus: %s" % (tmp_ngpus))
                    pbs.logmsg(pbs.EVENT_DEBUG3, "gpus: %s" % (gpus))
                    room_on_socket = False

        if room_on_socket:
            assigned['cpuset.cpus'].sort()
            assigned['cpuset.mems'].sort()
            assigned['cpuset.mems'] = list(set(assigned['cpuset.mems']))
            if 'devices' in assigned:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "device_ids pre set and sort: %s" %
                           (assigned['devices']))
                assigned['devices'] = list(set(assigned['devices']))
                assigned['devices'].sort()
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "device_ids post set and sort: %s" %
                           (assigned['devices']))
                assigned['devices_name'] = list(set(assigned['devices_name']))
                assigned['devices_name'].sort()
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Assigned Resources: %s" % (assigned))
            self.host_assigned_resources = assigned
            return assigned
        return False

    # Assign resources to the job
    def assign_job_resources(self, resources, available, node):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Resources: %s" %
                   (caller_name(), resources))

        # Determine where the resources should be placed
        pbs.logmsg(pbs.EVENT_DEBUG3, "Resources: %s" % (resources))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Available: %s" % (available))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Numa Nodes: %s" % (node.numa_nodes))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Devices: %s" % (node.devices))

        # What would we need to do different for a large smp (UV) system?
        # See if requested resources can fit on a single socket
        assigned = dict()
        pbs.logmsg(pbs.EVENT_DEBUG3, "Requested: %s" % (resources))

        # Determine the order that we should evaluate the sockets.
        socket_list = list()
        if 'placement_type' in self.cfg:
            if self.cfg['placement_type'] == 'round_robin':
                pbs.logmsg(pbs.EVENT_DEBUG3, "Requested round_robin placement")
                # Look at assigned_resources and determine which socket
                # to start with
                jobs_per_socket_cnt = dict()
                for socket in available.keys():
                    jobs_per_socket_cnt[socket] = 0
                for job in self.assigned_resources:
                    if 'cpuset.mems' in self.assigned_resources[job]:
                        for socket in \
                                self.assigned_resources[job]['cpuset.mems']:
                            jobs_per_socket_cnt[socket] += 1

                sorted_dict = sorted(jobs_per_socket_cnt.items(),
                                     key=operator.itemgetter(1))
                for x in sorted_dict:
                    socket_list.append(x[0])
        else:
            socket_list = available.keys()

        # Loop through the socket list and determine if the job
        # can fit on the socket
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Evaluate sockets in the following order: %s" %
                   (socket_list))
        for socket in socket_list:
            room_on_socket = True
            if 'ncpus' in resources:
                if int(resources['ncpus']) <= len(available[socket]['cpus']):
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Requested: %s, Available: %s" %
                               (resources['ncpus'], available[socket]['cpus']))
                    tmp_ncpus = int(resources['ncpus'])
                    assigned['cpuset.cpus'] = \
                        available[socket]['cpus'][:tmp_ncpus]
                    assigned['cpuset.mems'] = [socket]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficient ncpus on socket %d: R:%d,A:%s" %
                               (socket, resources['ncpus'],
                                available[socket]['cpus']))
                    room_on_socket = False
            # Check to see that nmics has been requested and not equal to 0
            if 'nmics' in resources and int(resources['nmics']) > 0:
                regex = re.compile(".*(mic).*")
                mics = [m.group(0)
                        for l in available[socket]['devices']
                        for m in [regex.search(l)] if m]
                if 'nmics' in resources and int(resources['nmics']) > 0 \
                        and int(resources['nmics']) <= len(mics):
                    tmp_nmics = int(resources['nmics'])
                    assigned['devices_name'], assigned['devices'] = \
                        self.assign_devices(
                            'mic', mics[:tmp_nmics], tmp_nmics, node)
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficient nmics on socket %d: R:%s,A:%s" %
                               (socket, resources['nmics'], mics))
                    room_on_socket = False
            # Check to see that ngpus has been requested and not equal to 0
            if 'ngpus' in resources and int(resources['ngpus']) > 0:
                regex = re.compile(".*(nvidia).*")
                gpus = [m.group(0)
                        for l in available[socket]['devices']
                        for m in [regex.search(l)] if m]
                if 'ngpus' in resources and int(resources['ngpus']) > 0 \
                        and int(resources['ngpus']) <= len(gpus):
                    tmp_ngpus = int(resources['ngpus'])
                    assigned['devices_name'], assigned['devices'] = \
                        self.assign_devices(
                            'gpu', gpus[:tmp_ngpus], tmp_ngpus, node)
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficient gpus on socket %d: R:%s,A:%s" %
                               (socket, resources['ngpus'], gpus))
                    room_on_socket = False
            if 'vmem' in resources:
                if size_as_int(resources['vmem']) >= \
                        available[socket]['memory']:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficient vmem on socket %d: R:%s,A:%s" %
                               (socket, resources['vmem'],
                                available[socket]['memory']))
                    room_on_socket = False
            if 'mem' in resources:
                if size_as_int(resources['mem']) >= \
                        available[socket]['memory']:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Insufficient memory on socket %d: R:%s,A:%s" %
                               (socket, resources['mem'],
                                available[socket]['memory']))
                    room_on_socket = False
            if room_on_socket:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Assigned Resources: %s" % (assigned))
                self.host_assigned_resources = assigned
                return assigned
        # If we made it here then the requested resources did not fit
        # on a single socket
        # Future: take distance into account when selecting sockets?
        # Combine available resources into a single list
        # This should work for a dual socket machine.
        # Needs additional work for machines with more than 2 sockets
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Unable to find requested resources: %s" % resources +
                   " on a socket. Checking the entire node")
        available_copy = copy.deepcopy(available)
        available_on_node = dict()
        socket_keys = available.keys()
        socket_keys.sort()
        available_on_node['sockets'] = socket_keys
        for socket in socket_keys:
            for key in available_copy[socket].keys():
                if isinstance(available[socket][key], int):
                    if key not in available_on_node:
                        available_on_node[key] = available_copy[socket][key]
                    else:
                        available_on_node[key] += available_copy[socket][key]
                if isinstance(available_copy[socket][key], str):
                    try:
                        if key not in available_on_node:
                            available_on_node[key] = \
                                size_as_int(available_copy[socket][key])
                        else:
                            available_on_node[key] += \
                                size_as_int(available_copy[socket][key])
                    except:
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "Unable to convert to int: %s" %
                                   (available_copy[socket][key]))

                if isinstance(available_copy[socket][key], list):
                    if key not in available_on_node:
                        available_on_node[key] = available_copy[socket][key]
                    else:
                        available_on_node[key] += available_copy[socket][key]

        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Available on node: %s" % (available_on_node))
        assigned = dict()
        room_on_node = False
        if 'ncpus' in resources:
            if int(resources['ncpus']) <= len(available_on_node['cpus']):
                room_on_node = True
                tmp_ncpus = int(resources['ncpus'])
                assigned['cpuset.cpus'] = available_on_node['cpus'][:tmp_ncpus]
                assigned['cpuset.mems'] = available_on_node['sockets']
            if 'nmics' in resources and int(resources['nmics']) != 0:
                regex = re.compile(".*(mic).*")
                mics = [m.group(0)
                        for l in available_on_node['devices']
                        for m in [regex.search(l)] if m]
                if int(resources['nmics']) <= len(mics) and \
                        int(resources['nmics']) > 0:
                    tmp_nmics = int(resources['nmics'])
                    assigned['devices_name'], assigned['devices'] = \
                        self.assign_devices(
                            'mic', mics[:tmp_nmics], tmp_nmics, node)
            if 'ngpus' in resources and int(resources['ngpus']) != 0:
                regex = re.compile(".*(nvidia).*")
                gpus = [m.group(0)
                        for l in available_on_node['devices']
                        for m in [regex.search(l)] if m]
                if int(resources['ngpus']) <= len(gpus) and \
                        int(resources['ngpus']) > 0:
                    tmp_ngpus = int(resources['ngpus'])
                    assigned['devices_name'], assigned['devices'] = \
                        self.assign_devices(
                            'gpu', gpus[:tmp_ngpus], tmp_ngpus, node)
        if room_on_node:
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Assigned Resources: %s" % (assigned))
            self.host_assigned_resources = assigned
            return assigned
        return False

        # Consolidate resources if needed to place the job

    # Determine which resources are available
    def available_node_resources(self, node):
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "%s: Method called" % (caller_name()))

        available = copy.deepcopy(node.numa_nodes)
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Available Keys: %s" % (available[0].keys()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Available: %s" % (available))
        for socket in available.keys():
            if 'cpus' in available[socket]:
                # Find the physical cores
                if available[socket]['cpus'].find('-') != -1 and \
                        node.hyperthreading:
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Splitting %s at ','" %
                               (available[socket]['cpus']))
                    available[socket]['cpus'] = cpus2list(
                        available[socket]['cpus'].split(',')[0])
                else:
                    available[socket]['cpus'] = cpus2list(
                        available[socket]['cpus'])
            if 'MemTotal' in available[socket]:
                # Find the memory on the socket in bites.
                # Remove the 'b' to simply math
                available[socket]['memory'] = size_as_int(
                    available[socket]['MemTotal'])

        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Available Pre device add: %s" % (available))
        pbs.logmsg(pbs.EVENT_DEBUG3,
                   "Node Devices: %s" % (node.devices.keys()))
        for device in node.devices.keys():
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "%s: Device Names: %s" %
                       (caller_name(), device))
            if device == 'mic' or device == 'gpu':
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Devices: %s" %
                           (node.devices[device].keys()))
                for device_name in node.devices[device].keys():
                    device_socket = \
                        node.devices[device][device_name]['numa_node']
                    if 'devices' not in available[device_socket]:
                        available[device_socket]['devices'] = list()
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Device: %s, Socket: %s" %
                               (device, device_socket))
                    available[device_socket]['devices'].append(device_name)
            # pbs.logmsg(pbs.EVENT_DEBUG3,
            #            "Available on socket %s: %s" %
            #            (socket,available[socket]))
        pbs.logmsg(pbs.EVENT_DEBUG3, "Available: %s" % (available))

        # Remove all of the resources that are assigned to other jobs
        for job in self.assigned_resources.keys():
            # Added by Alexis Cousein on 24th of Jan 2016 to support
            # suspended jobs on nodes
            if (not job_to_be_ignored(job)):
                cpus = list()
                sockets = list()
                devices = list()
                memory = 0
                if 'cpuset.cpus' in self.assigned_resources[job]:
                    cpus = self.assigned_resources[job]['cpuset.cpus']
                if 'cpuset.mems' in self.assigned_resources[job]:
                    sockets = self.assigned_resources[job]['cpuset.mems']
                if 'devices.list' in self.assigned_resources[job]:
                    devices = self.assigned_resources[job]['devices.list']
                if 'memory.limit' in self.assigned_resources[job]:
                    memory = size_as_int(
                                self.assigned_resources[job]['memory.limit'])

                pbs.logmsg(pbs.EVENT_DEBUG3, "cpuset.cpus: %s" % cpus)
                pbs.logmsg(pbs.EVENT_DEBUG3, "cpuset.mems: %s" % sockets)
                pbs.logmsg(pbs.EVENT_DEBUG3, "devices.list: %s" % devices)
                pbs.logmsg(pbs.EVENT_DEBUG3, "memory.limit: %s" % memory)

                # Loop through the sockets and remove cpus that are
                # assigned to other cgroups
                for socket in sockets:
                    for cpu in cpus:
                        try:
                            available[socket]['cpus'].remove(cpu)
                        except ValueError:
                            pass
                        except:
                            pbs.logmsg(pbs.EVENT_DEBUG3,
                                       "Error removing %d from %s" %
                                       (cpu, available[socket]['cpus']))

                if len(sockets) == 1:
                    avail_mem = available[sockets[0]]['memory']
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Sockets: %s\tAvailable: %s" %
                               (sockets, available))
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Decrementing memory: %d by %d" %
                               (size_as_int(avail_mem), memory))
                    if memory <= available[sockets[0]]['memory']:
                        available[sockets[0]]['memory'] -= memory

                # Loop throught the available sockets
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Assigned device to %s: %s" % (job, devices))
                for socket in available.keys():
                    for device in devices:
                        try:
                            # loop through know devices and see if they match
                            if len(available[socket]['devices']) != 0:
                                pbs.logmsg(pbs.EVENT_DEBUG3,
                                           "Check device: %s" % (device))
                                pbs.logmsg(pbs.EVENT_DEBUG3,
                                           "Available device: %s" %
                                           (available[socket]['devices']))
                                major, minor = device.split()[1].split(':')
                                avail_device = self.get_device_name(
                                                   node, available, socket,
                                                   major, minor)
                                pbs.logmsg(pbs.EVENT_DEBUG3,
                                           "Returned device: %s" %
                                           (avail_device))
                                if avail_device is not None:
                                    pbs.logmsg(pbs.EVENT_DEBUG3,
                                               "socket: %d,\t" % socket +
                                               "devices: %s,\t" %
                                               available[socket]['devices'] +
                                               "device to remove: %s" %
                                               (avail_device))
                                    available[socket]['devices'].remove(
                                        avail_device)
                        except ValueError:
                            pass
                        except:
                            pbs.logmsg(pbs.EVENT_DEBUG3,
                                       "Unexpected error: %s" %
                                       sys.exc_info()[0])
                            pbs.logmsg(pbs.EVENT_DEBUG3,
                                       "Error removing %s from %s" %
                                       (device, available[socket]['devices']))
            # Added by Alexis Cousein on 24th of Jan 2016 to support
            # suspended jobs on nodes
            else:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Job %s res not removed from host " % job +
                           "available res: suspended job")
        pbs.logmsg(pbs.EVENT_DEBUG, "Available resources: %s" % (available))
        return available

    # Set a job limit
    def set_job_limit(self, jobid, resource, value):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s: %s = %s" %
                   (caller_name(), jobid, resource, value))
        try:
            if resource == 'mem':
                if 'memory' in self.subsystems and \
                        self.cfg['cgroup']['memory']['enabled']:
                    self.write_value(os.path.join(self.paths['memory'],
                                     jobid, 'memory.limit_in_bytes'),
                                     size_as_int(value))
            elif resource == 'softmem':
                if 'memory' in self.subsystems and \
                        self.cfg['cgroup']['memory']['enabled']:
                    self.write_value(os.path.join(self.paths['memory'],
                                     jobid, 'memory.soft_limit_in_bytes'),
                                     size_as_int(value))
            elif resource == 'vmem':
                if 'memsw' in self.subsystems and \
                        self.cfg['cgroup']['memsw']['enabled']:
                    self.write_value(os.path.join(self.paths['memsw'],
                                     jobid, 'memory.memsw.limit_in_bytes'),
                                     size_as_int(value))
            elif resource == 'hpmem':
                if 'hugetlb' in self.subsystems and \
                        self.cfg['cgroup']['hugetlb']['enabled']:
                    self.write_value(glob.glob(os.path.join(
                                     self.paths['hugetlb'], jobid,
                                     'hugetlb.*MB.limit_in_bytes'))[0],
                                     size_as_int(value))
            elif resource == 'ncpus':
                if 'cpuset' in self.subsystems and \
                        self.cfg['cgroup']['cpuset']['enabled']:
                    path = os.path.join(self.paths['cpuset'],
                                        jobid, 'cpuset.cpus')
                    cpus = self.select_cpus(path, value)
                    if cpus is None:
                        raise CgroupLimitError("Failed to configure cpuset.")
                    cpus = ','.join(map(str, cpus))
                    self.write_value(path, cpus)
                    self.__copy_from_parent(os.path.join(self.paths['cpuset'],
                                            jobid, 'cpuset.mems'))
            elif resource == 'cpuset.cpus':
                if 'cpuset' in self.subsystems and \
                        self.cfg['cgroup']['cpuset']['enabled']:
                    path = os.path.join(self.paths['cpuset'],
                                        jobid, 'cpuset.cpus')
                    cpus = value
                    if cpus is None:
                        msg = "Failed to configure cpus in cpuset."
                        raise CgroupLimitError(msg)
                    cpus = ','.join(map(str, cpus))
                    self.write_value(path, cpus)
            elif resource == 'cpuset.mems':
                if 'cpuset' in self.subsystems and \
                        self.cfg['cgroup']['cpuset']['enabled']:
                    path = os.path.join(self.paths['cpuset'],
                                        jobid, 'cpuset.mems')
                    mems = value
                    if mems is None:
                        msg = "Failed to configure mems in cpuset."
                        raise CgroupLimitError(msg)
                    mems = ','.join(map(str, mems))
                    self.write_value(path, mems)
            elif resource == 'devices':
                if 'devices' in self.subsystems and \
                        self.cfg['cgroup']['devices']['enabled']:

                    path = os.path.join(self.paths['devices'],
                                        jobid, 'devices.allow')
                    devices = value
                    if devices is None:
                        msg = "Failed to configure device(s)."
                        raise CgroupLimitError(msg)
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "Setting devices: %s for %s" % (devices, jobid))
                    for device in devices:
                        self.write_value(path, device)

                    path = os.path.join(self.paths['devices'],
                                        jobid, 'devices.list')
                    output = open(path, 'r').read()
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "devices.list: %s" % output.replace("\n", ","))
            else:
                pbs.logmsg(pbs.EVENT_DEBUG, "%s: Job resource %s not handled" %
                           (caller_name(), resource))
        except:
            raise

    # Update resource usage for a job
    def update_job_usage(self, jobid, resc_used):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: resc_used = %s" %
                   (caller_name(), str(resc_used)))
        # Sort the subsystems so that we consistently look at the subsystems
        # in the same order every time
        self.subsystems.sort()
        for subsys in self.subsystems:
            path = os.path.join(self.paths[subsys], jobid)
            if subsys == "memory":
                max_mem = self.__get_max_mem_usage(path)
                if max_mem is None:
                    pbs.logjobmsg(jobid, "%s: No max mem data" %
                                  (caller_name()))
                else:
                    resc_used['mem'] = pbs.size(convert_size(max_mem, 'kb'))
                    pbs.logjobmsg(jobid,
                                  "%s: Memory usage: mem=%s" %
                                  (caller_name(), resc_used['mem']))
                mem_failcnt = self.__get_mem_failcnt(path)
                if mem_failcnt is None:
                    pbs.logjobmsg(jobid, "%s: No mem fail count data" %
                                  (caller_name()))
                else:
                    # Check to see if the job exceeded its resource limits
                    if mem_failcnt > 0:
                        err_msg = self.__get_error_msg(jobid)
                        pbs.logjobmsg(jobid,
                                      "Cgroup memory limit exceeded: %s" %
                                      (err_msg))
            elif subsys == "memsw":
                max_vmem = self.__get_max_memsw_usage(path)
                if max_vmem is None:
                    pbs.logjobmsg(jobid, "%s: No max vmem data" %
                                  (caller_name()))
                else:
                    resc_used['vmem'] = pbs.size(convert_size(max_vmem, 'kb'))
                    pbs.logjobmsg(jobid,
                                  "%s: Memory usage: vmem=%s" %
                                  (caller_name(), resc_used['vmem']))

                vmem_failcnt = self.__get_memsw_failcnt(path)
                if vmem_failcnt is None:
                    pbs.logjobmsg(jobid, "%s: No vmem fail count data" %
                                  (caller_name()))
                else:
                    pbs.logjobmsg(jobid, "%s: vmem fail count: %d " %
                                  (caller_name(), vmem_failcnt))
                    if vmem_failcnt > 0:
                        err_msg = self.__get_error_msg(jobid)
                        pbs.logjobmsg(jobid,
                                      "Cgroup memsw limit exceeded: %s" %
                                      (err_msg))
            elif subsys == "hugetlb":
                max_hpmem = self.__get_max_hugetlb_usage(path)
                if max_hpmem is None:
                    pbs.logjobmsg(jobid, "%s: No max hpmem data" %
                                  (caller_name()))
                    return
                hpmem_failcnt = self.__get_hugetlb_failcnt(path)
                if hpmem_failcnt is None:
                    pbs.logjobmsg(jobid, "%s: No hpmem fail count data" %
                                  (caller_name()))
                    return
                if hpmem_failcnt > 0:
                    err_msg = self.__get_error_msg(jobid)
                    pbs.logjobmsg(jobid, "Cgroup hugetlb limit exceeded: %s" %
                                  (err_msg))
                resc_used['hpmem'] = pbs.size(convert_size(max_hpmem, 'kb'))
                pbs.logjobmsg(jobid, "%s: Hugepage usage: %s" %
                              (caller_name(), resc_used['hpmem']))
            elif subsys == "cpuacct":
                cpu_usage = self.__get_cpu_usage(path)
                if cpu_usage is None:
                    pbs.logjobmsg(jobid, "%s: No CPU usage data" %
                                  (caller_name()))
                    return
                cpu_usage = convert_time(str(cpu_usage) + "ns")
                pbs.logjobmsg(jobid, "%s: CPU usage: %.3lf secs" %
                              (caller_name(), cpu_usage))
                resc_used['cput'] = pbs.duration(cpu_usage)

    # Creates the cgroup if it doesn't exists
    def create_job(self, jobid, node):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        # Iterate over the subsystems required
        for subsys in self.subsystems:
            # Create a directory for the job
            try:
                old_umask = os.umask(0022)
                path = self.paths[subsys]
                if not os.path.exists(path):
                    pbs.logmsg(pbs.EVENT_DEBUG, "%s: Creating directory %s" %
                               (caller_name(), path))
                    os.makedirs(path, 0755)
                path = os.path.join(self.paths[subsys], jobid)
                if not os.path.exists(path):
                    pbs.logmsg(pbs.EVENT_DEBUG, "%s: Creating directory %s" %
                               (caller_name(), path))
                    os.makedirs(path, 0755)
                if subsys == 'devices':
                    self.setup_subsys_devices(path, node)

            except OSError, exc:
                raise CgroupConfigError("Failed to create directory: %s (%s)" %
                                        (path, errno.errorcode[exc.errno]))
            except:
                raise
            finally:
                os.umask(old_umask)

    # Determine the cgroup limits and configure the cgroups
    def configure_job(self, jobid, hostresc, node):
        mem_enabled = 'memory' in self.subsystems
        vmem_enabled = 'memsw' in self.subsystems
        if mem_enabled or vmem_enabled:
            # Initialize mem variables
            mem_avail = node.get_memory_on_node(self.cfg)
            pbs.logmsg(pbs.EVENT_DEBUG, "mem_avail %s" % mem_avail)
            mem_requested = None
            if 'mem' in hostresc.keys():
                mem_requested = convert_size(hostresc['mem'], 'kb')
            mem_default = None
            if mem_enabled:
                mem_default = self.default('memory')
            # Initialize vmem variables
            vmem_avail = node.get_vmem_on_node(self.cfg)
            pbs.logmsg(pbs.EVENT_DEBUG, "vmem_avail %s" % vmem_avail)
            vmem_requested = None
            if 'vmem' in hostresc.keys():
                vmem_requested = convert_size(hostresc['vmem'], 'kb')
            vmem_default = None
            if vmem_enabled:
                vmem_default = self.default('memsw')
            # Initialize softmem variables
            if 'soft_limit' in self.cfg['cgroup']['memory'].keys():
                softmem_enabled = self.cfg['cgroup']['memory']['soft_limit']
            else:
                softmem_enabled = False
            # Sanity check
            if size_as_int(mem_avail) > size_as_int(vmem_avail):
                if size_as_int(mem_avail) - size_as_int(vmem_avail) > 10240:
                    raise CgroupLimitError(
                        'mem available (%s) exceeds vmem available (%s)' %
                        (mem_avail, vmem_avail))
            # Determine the mem limit
            if mem_requested is not None:
                # mem requested may not exceed available
                if size_as_int(mem_requested) > size_as_int(mem_avail):
                    raise JobValueError(
                        'mem requested (%s) exceeds mem available (%s)' %
                        (mem_requested, mem_avail))
                mem_limit = mem_requested
            else:
                # mem was not requested
                if mem_default is None:
                    mem_limit = mem_avail
                else:
                    mem_limit = mem_default
            # Determine the vmem limit
            if vmem_requested is not None:
                # vmem requested may not exceed available
                if size_as_int(vmem_requested) > size_as_int(vmem_avail):
                    raise JobValueError(
                        'vmem requested (%s) exceeds vmem available (%s)' %
                        (vmem_requested, vmem_avail))
                vmem_limit = vmem_requested
            else:
                # vmem was not requested
                if vmem_default is None:
                    vmem_limit = vmem_avail
                else:
                    vmem_limit = vmem_default
            # Ensure vmem is at least as large as mem
            if size_as_int(vmem_limit) < size_as_int(mem_limit):
                vmem_limit = mem_limit
            # Adjust for soft limits if enabled
            if mem_enabled and softmem_enabled:
                softmem_limit = mem_limit
                # The hard memory limit is assigned the lesser of the vmem
                # limit and available memory
                if size_as_int(vmem_limit) < size_as_int(mem_avail):
                    mem_limit = vmem_limit
                else:
                    mem_limit = mem_avail
            # Again, ensure vmem is at least as large as mem
            if size_as_int(vmem_limit) < size_as_int(mem_limit):
                vmem_limit = mem_limit
            # Sanity checks when both memory and memsw are enabled
            if mem_enabled and vmem_enabled:
                if vmem_requested is not None:
                    if size_as_int(vmem_limit) > size_as_int(vmem_requested):
                        # The user requested an invalid limit
                        raise JobValueError(
                            'vmem limit (%s) exceeds vmem requested (%s)' %
                            (vmem_limit, vmem_requested))
                if size_as_int(vmem_limit) > size_as_int(mem_limit):
                    # This job may utilize swap
                    if size_as_int(vmem_avail) <= size_as_int(mem_avail) and \
                      size_as_int(mem_avail) - size_as_int(vmem_avail) > 10240:
                        # No swap available
                        raise CgroupLimitError(
                            ('Job might utilize swap ' +
                             'and no swap space available'))
            # Assign mem and vmem
            if mem_enabled:
                if mem_requested is None:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               ("%s: mem not requested, " +
                                "assigning %s to cgroup") %
                               (caller_name(), mem_limit))
                    hostresc['mem'] = pbs.size(mem_limit)
                if softmem_enabled:
                    hostresc['softmem'] = pbs.size(softmem_limit)
            if vmem_enabled:
                if vmem_requested is None:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               ("%s: vmem not requested, " +
                                "assigning %s to cgroup") %
                               (caller_name(), vmem_limit))
                    hostresc['vmem'] = pbs.size(vmem_limit)
        # Initialize hpmem variables
        hpmem_enabled = 'hugetlb' in self.subsystems
        if hpmem_enabled:
            hpmem_avail = node.get_hpmem_on_node(self.cfg)
            hpmem_limit = None
            hpmem_default = self.default('hugetlb')
            if hpmem_default is None:
                hpmem_default = hpmem_avail
            if 'hpmem' in hostresc.keys():
                hpmem_limit = convert_size(hostresc['hpmem'], 'kb')
            else:
                hpmem_limit = hpmem_default
            # Assign hpmem
            if size_as_int(hpmem_limit) > size_as_int(hpmem_avail):
                raise JobValueError('hpmem limit (%s) exceeds available (%s)' %
                                    (hpmem_limit, hpmem_avail))
            hostresc['hpmem'] = pbs.size(hpmem_limit)
        # Initialize cpuset variables
        cpuset_enabled = 'cpuset' in self.subsystems
        if cpuset_enabled:
            cpu_limit = 1
            if 'ncpus' in hostresc.keys():
                cpu_limit = hostresc['ncpus']
            if cpu_limit < 1:
                cpu_limit = 1
            hostresc['ncpus'] = pbs.pbs_int(cpu_limit)

        # Find the available resources and assign the right ones to the job

        attempt = 0
        assign_resources = False

        # Two attempts since self.cleanup_orphans may actually fix the
        # problem we see in a first attempt
        while attempt < 2:
            attempt += 1
            available_resources = self.available_node_resources(node)
            if 'vnodes' in hostresc:
                assign_resources = self.assign_job_resources_by_vnode(
                    hostresc, available_resources, node)
            else:
                assign_resources = self.assign_job_resources(
                    hostresc, available_resources, node)

            if (assign_resources is False) and (attempt < 3):
                # No resources were assigned to the job.
                # Most likely cause was that a cgroup has
                # not been cleaned up yet
                pbs.logmsg(pbs.EVENT_DEBUG, "Failed to assign resources. " +
                           "Checking the following cgroups on the node " +
                           "with the server: %s" % self.existing_cgroups)

                # Collect the jobs on the node (try reading mom_priv/jobs,
                # if not successful ask server)
                jobs_list = None
                if attempt < 2:
                    jobs_list = node.gather_jobs_on_node_local()
                else:
                    # If after the first attempt we are still having issues
                    # look at the server jobs list instead of the moms
                    jobs_list = node.gather_jobs_on_node()

                if jobs_list is not None:
                    # Don't clean up the cgroup we just made for the
                    # job just yet
                    if jobid not in jobs_list:
                        jobs_list.append(jobid)

                    self.cleanup_orphans(jobs_list)

                    # Recheck what is now assigned after things were cleaned up
                    self.gather_assigned_resources()

        if assign_resources is False:
            # Cleanup cgroups for jobs not present on this node
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Assign resources failed. Attempting to cleanup all " +
                       "leftover cgroups (including event job %s)" % jobid)

            # Remove the current job from the jobs list so it will be
            # cleaned up as well.
            jobs_list.remove(jobid)

            self.cleanup_orphans(jobs_list)

            # Rerun the job and log the message
            line = 'Unable to assign resources to job. '
            line += 'Will requeue the job and try again.'
            line += 'job run_count: %d' % pbs.event().job.run_count
            pbs.event().job.rerun()
            pbs.event().reject(line)

        # Print out the assigned resources
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "Assigned resources: %s" % (assign_resources))

        if cpuset_enabled:
            hostresc.pop('ncpus', None)
            for key in ['cpuset.cpus', 'cpuset.mems']:
                if key in assign_resources:
                    hostresc[key] = assign_resources[key]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "Key: %s not found in assign_resources" % key)

        # Initialize devices variables
        devices_enabled = 'devices' in self.subsystems
        if devices_enabled:
            key = 'devices'
            if key in assign_resources:
                if key in assign_resources:
                    hostresc[key] = assign_resources[key]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "Key: %s not found in assign_resources" % key)

        # Apply the resource limits to the cgroups
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Setting cgroup limits for: %s" %
                   (caller_name(), hostresc))

        # The vmem limit must be set after the mem limit, so sort the keys
        for resc in sorted(hostresc.keys()):
            self.set_job_limit(jobid, resc, hostresc[resc])

    # Kill any processes contained within a tasks file
    def __kill_tasks(self, tasks_file):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        with open(tasks_file, 'r') as fd:
            for line in fd:
                os.kill(int(line.strip()), signal.SIGKILL)
        count = 0
        with open(tasks_file, 'r') as fd:
            for line in fd:
                count += 1
                pid = line.strip()
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s: Pid: %s did not clean up" %
                           (caller_name(), pid))
                if os.path.isfile('/proc/%s/status' % pid):
                    tmp = open('/proc/%s/status' % pid).readlines()
                    tmp_line = ''
                    for entry in tmp:
                        if entry.find('Name:') != -1:
                            tmp_line += entry.strip() + ', '
                        if entry.find('State:') != -1:
                            tmp_line += entry.strip() + ', '
                        if entry.find('Uid:') != -1:
                            tmp_line += entry.strip()
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "%s: %s" % (caller_name(), tmp_line))

        return count

    # Perform the actual removal of the cgroup directory
    # by default, only one attempt at killing tasks in cgroup, without sleeping
    # since this method could be called many times
    # (for N directories times M jobs)
    def __remove_cgroup(self, path, tasks_kill_attempts=1):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        try:
            if os.path.exists(path):
                tasks_file = os.path.join(path, 'tasks')
                task_cnt = self.__kill_tasks(tasks_file)
                kill_attempts = 0
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Task Kill Attempts: %d" % tasks_kill_attempts)
                while (task_cnt > 0) and (kill_attempts < tasks_kill_attempts):
                    kill_attempts += 1
                    count = 0

                    with open(tasks_file, 'r') as fd:
                        for line in fd:
                            count += 1
                        task_cnt = count

                    pbs.logmsg(pbs.EVENT_SYSTEM,
                               "Attempt: %d - cgroup still has %d tasks: %s" %
                               (kill_attempts, task_cnt, path))
                    if kill_attempts < tasks_kill_attempts:
                        time.sleep(1)
                        # Added since there are race conditions where tasks are
                        # being added at the same time we get the initial
                        # task count
                        tasks_file = os.path.join(path, 'tasks')
                        task_cnt = self.__kill_tasks(tasks_file)

                if task_cnt == 0:
                    pbs.logmsg(pbs.EVENT_DEBUG, "%s: Removing directory %s" %
                               (caller_name(), path))
                    os.rmdir(path)
                    if os.path.exists(path):
                        time.sleep(.25)
                        if os.path.exists(path):
                            pbs.logmsg(pbs.EVENT_DEBUG,
                                       "%s: 2nd Try Removing directory %s" %
                                       (caller_name(), path))
                            os.rmdir(path)
                            time.sleep(.25)
                        if os.path.exists(path):
                            return False
                else:
                    pbs.logmsg(pbs.EVENT_SYSTEM,
                               "cgroup still has %d tasks: %s" %
                               (task_cnt, path))

                    # Check to see if the offline file is already present
                    # on the mom
                    offline_file_exists = False
                    if os.path.isfile(self.offline_file):
                        msg = "Cgroup(s) not cleaning up but the node already "
                        msg += "has the offline file."

                        pbs.logmsg(pbs.EVENT_DEBUG, msg)
                    else:
                        # Check to see that the node is not already offline.
                        try:
                            tmp_state = pbs.server().vnode(self.hostname).state
                        except:
                            msg = "Unable to contact server for node state"
                            pbs.logmsg(pbs.EVENT_DEBUG, msg)
                            tmp_state = None
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "Current Node State: %d" % tmp_state)
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "Offline Node State: %d" % pbs.ND_OFFLINE)

                        if tmp_state == pbs.ND_OFFLINE:
                            msg = "Cgroup(s) not cleaning up but the node is "
                            msg += "already offline."
                            pbs.logmsg(pbs.EVENT_DEBUG, msg)
                        elif tmp_state is not None:
                            # Offline the node(s)
                            pbs.logmsg(pbs.EVENT_DEBUG, self.offline_msg)
                            msg = "Offlining node since cgroup(s) are not "
                            msg += "cleaning up"
                            pbs.logmsg(pbs.EVENT_DEBUG, msg)
                            vnode = pbs.event().vnode_list[self.hostname]

                            vnode.state = pbs.ND_OFFLINE

                            # Write a file locally to reduce server traffic
                            # when it comes time to online the node
                            pbs.logmsg(pbs.EVENT_DEBUG,
                                       "Offline file: %s" % self.offline_file)
                            open(self.offline_file, 'a').close()
                            vnode.comment = self.offline_msg

                            pbs.logmsg(pbs.EVENT_DEBUG, self.offline_msg)
                        else:
                            pass

                    return False

        except OSError, exc:
            pbs.logmsg(pbs.EVENT_SYSTEM,
                       "Failed to remove cgroup path: %s (%s)" %
                       (path, errno.errorcode[exc.errno]))
        except:
            pbs.logmsg(pbs.EVENT_SYSTEM, "Failed to remove cgroup path: %s" %
                       (path))

        return True

    # Removes cgroup directories that are not associated with a local job
    def cleanup_orphans(self, local_jobs):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        orphan_cnt = 0
        for key in self.paths.keys():
            for dir in glob.glob(os.path.join(self.paths[key], '[0-9]*')):
                jobid = os.path.basename(dir)
                if jobid not in local_jobs:
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "%s: Removing orphaned cgroup: %s" %
                               (caller_name(), dir))
                    # default number of attempts at killing tasks
                    status = self.__remove_cgroup(dir)
                    if not status:
                        pbs.logmsg(pbs.EVENT_DEBUG,
                                   "%s: Removing orphaned cgroup %s failed " %
                                   (caller_name(), dir))
                        orphan_cnt += 1
        return orphan_cnt

    # Removes the cgroup directories for a job
    def delete(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))

        tasks_kill_attempted = False

        # Determine which subsystems will be used
        for subsys in self.subsystems:
            if not tasks_kill_attempted:
                # Make multiple attempts at killing tasks in cgroups on
                # first subsystem encountered since it is "normal" for
                # a cgroup.delete to encounter processes hard to kill
                status = self.__remove_cgroup(os.path.join(self.paths[subsys],
                                                           jobid),
                                              tasks_kill_attempts=(
                                              CGROUP_KILL_ATTEMPTS))
                tasks_kill_attempted = True
            else:
                # We tried getting rid of job processes earlier,
                # so don't try N times with sleeps
                status = self.__remove_cgroup(os.path.join(self.paths[subsys],
                                              jobid), tasks_kill_attempts=1)

            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Status: %s" %
                       (caller_name(), status))
            if not status:
                # Rerun the job and log the message
                line = 'Unable to cleanup a cgroup. '
                line += 'Will offline the node and requeue the job '
                line += 'and try again. job run_count: %d' % \
                        pbs.event().job.run_count
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s: Failed to remove cgroup: %s" %
                           (caller_name(), line))
                pbs.event().accept()

    # Write a value to a limit file
    def write_value(self, file, value, mode='w'):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: writing %s to %s" %
                   (caller_name(), value, file))
        try:
            with open(file, mode) as fd:
                fd.write(str(value) + '\n')
        except IOError, exc:
            if exc.errno == errno.ENOENT:
                pbs.logmsg(pbs.EVENT_SYSTEM,
                           "Trying to set limit to unknown file %s" % file)
            elif exc.errno in [errno.EACCES, errno.EPERM]:
                pbs.logmsg(pbs.EVENT_SYSTEM, "Permission denied on file %s" %
                           file)
            elif exc.errno == errno.EBUSY:
                raise CgroupBusyError("Limit rejected")
            elif exc.errno == errno.EINVAL:
                raise CgroupLimitError("Invalid limit value: %s" % (value))
            else:
                raise
        except:
            raise

    # Return memory failcount
    def __get_mem_failcnt(self, path):
        try:
            return int(open(os.path.join(path,
                       "memory.failcnt"), 'r').read().strip())
        except:
            return None

    # Return vmem failcount
    def __get_memsw_failcnt(self, path):
        try:
            return int(open(os.path.join(path,
                       "memory.memsw.failcnt"), 'r').read().strip())
        except:
            return None

    # Return hpmem failcount
    def __get_hugetlb_failcnt(self, path):
        try:
            return int(open(glob.glob(os.path.join(path,
                       "hugetlb.*MB.failcnt"))[0], 'r').read().strip())
        except:
            return None

    # Return the max usage of memory in bytes
    def __get_max_mem_usage(self, path):
        try:
            return int(open(os.path.join(path,
                       "memory.max_usage_in_bytes"), 'r').read().strip())
        except:
            return None

    # Return the max usage of memsw in bytes
    def __get_max_memsw_usage(self, path):
        try:
            return int(open(os.path.join(path,
                       "memory.memsw.max_usage_in_bytes"), 'r').read().strip())
        except:
            return None

    # Return the max usage of hugetlb in bytes
    def __get_max_hugetlb_usage(self, path):
        try:
            return int(open(glob.glob(os.path.join(path,
                       "hugetlb.*MB.max_usage_in_bytes"))[0],
                            'r').read().strip())
        except:
            return None

    # Return the cpuacct.usage in cpu seconds
    def __get_cpu_usage(self, path):
        try:
            return int(open(os.path.join(path,
                       "cpuacct.usage"), 'r').read().strip())
        except:
            return None

    # Assign CPUs to the cpuset
    def select_cpus(self, path, ncpus):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: path is %s" % (caller_name(), path))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: ncpus is %s" %
                   (caller_name(), ncpus))
        if ncpus < 1:
            ncpus = 1
        try:
            # Must select from those currently available
            cpufile = os.path.basename(path)
            base = os.path.dirname(path)
            parent = os.path.dirname(base)
            avail = cpus2list(open(os.path.join(parent, cpufile),
                              'r').read().strip())
            if len(avail) < 1:
                raise CgroupProcessingError("No CPUs avaialble in cgroup.")
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Available CPUs: %s" %
                       (caller_name(), avail))
            assigned = []
            for file in glob.glob(os.path.join(parent, '[0-9]*', cpufile)):
                cpus = cpus2list(open(file, 'r').read().strip())
                for id in cpus:
                    if id in avail:
                        avail.remove(id)
            if len(avail) < ncpus:
                raise CgroupProcessingError(
                    "Insufficient CPUs avaialble in cgroup.")
            if len(avail) == ncpus:
                return avail
            # FUTURE: Try to minimize NUMA nodes based on memory requirement
            return avail[0:ncpus]
        except:
            raise

    # Return the error message in system message file
    def __get_error_msg(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        proc = subprocess.Popen(['dmesg'],
                                shell=False, stdout=subprocess.PIPE)
        stdout = proc.communicate()[0].splitlines()
        stdout.reverse()
        # Check to see if the job id is found in dmesg otherwise
        # you could get the information for another job that was killed
        # the line will look like Memory cgroup stats for /pbspro/279.centos7
        kill_line = ""

        for line in stdout:
            start = line.find('Killed process ')
            if start >= 0:
                kill_line = line[start:]
            job_start = line.find(jobid)
            if job_start >= 0:
                # pbs.logmsg(pbs.EVENT_DEBUG3,
                #           "%s: Jobid: %s, Line: %s" %
                #           (caller_name(), jobid, line))
                return kill_line
        return ""

    # Write out host cgroup assigned resources for this job
    def write_out_cgroup_host_job_env_file(self, jobid, env_list):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        # if not os.path.exists(self.host_job_env_dir):
        #    os.makedirs(self.host_job_env_dir, 0755)

        # Write out assigned_resources
        try:
            lines = string.join(env_list, '\n')
            filename = self.host_job_env_filename % jobid
            outfile = open(filename, "w")
            outfile.write(lines)
            outfile.close()
            pbs.logmsg(pbs.EVENT_DEBUG3, "Wrote out file: %s" % (filename))
            pbs.logmsg(pbs.EVENT_DEBUG3, "Data: %s" % (lines))
            return True
        except:
            return False

    # Write out host cgroup assigned resources for this job
    def write_out_cgroup_host_assigned_resources(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        if not os.path.exists(self.hook_storage_dir):
            os.makedirs(self.hook_storage_dir, 0755)

        # Write out assigned_resources
        try:
            json_str = json.dumps(self.host_assigned_resources)
            outfile = open(self.hook_storage_dir+os.sep+jobid, "w")
            outfile.write(json_str)
            outfile.close()
            pbs.logmsg(pbs.EVENT_DEBUG3, "Wrote out file: %s" %
                       (self.hook_storage_dir+os.sep+jobid))
            pbs.logmsg(pbs.EVENT_DEBUG3, "Data: %s" % (json_str))
            return True
        except:
            return False

    def read_in_cgroup_host_assigned_resources(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        pbs.logmsg(pbs.EVENT_DEBUG3, "Host assigned resources: %s" %
                   (self.host_assigned_resources))
        if os.path.isfile(self.hook_storage_dir+os.sep+jobid):
            # Write out assigned_resources
            try:
                infile = open(self.hook_storage_dir+os.sep+jobid, 'r')
                json_data = json.load(infile, object_hook=decode_dict)
                self.host_assigned_resources = json_data
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           "Host assigned resources: %s" %
                           (self.host_assigned_resources))
            except IOError:
                raise CgroupConfigError("I/O error reading config file")
            except json.JSONDecodeError:
                raise CgroupConfigError(
                    "JSON parsing error reading config file")
            except Exception:
                raise
            finally:
                infile.close()

        if self.host_assigned_resources is not None:
            return True
        else:
            return False

#
#
# FUNCTION main
#


def main():
    pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Function called" % (caller_name()))
    hostname = pbs.get_local_nodename()
    pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Host is %s" % (caller_name(), hostname))

    # Log the hook event type
    e = pbs.event()
    pbs.logmsg(pbs.EVENT_DEBUG, "%s: Hook name is %s" %
               (caller_name(), e.hook_name))

    try:
        # Instantiate the hook utility class
        hooks = HookUtils()
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Event type is %s" %
                   (caller_name(), hooks.event_name(e.type)))
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Hook utility class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: %s" % (caller_name(), repr(hooks)))
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "%s: Failed to instantiate hook utility class" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        e.accept()

    if not hooks.hashandler(e.type):
        # Bail out if there is no handler for this event
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s event not handled by this hook" %
                   (caller_name(), hooks.event_name(e.type)))
        e.accept()

    try:
        # If an exception occurs, jobutil must be set
        jobutil = None
        # Instantiate the job utility class first so jobutil can be accessed
        # by the exception handlers.
        if hasattr(e, 'job'):
            jobutil = JobUtils(e.job)
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: Job information class instantiated" %
                       (caller_name()))
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: %s" %
                       (caller_name(), repr(jobutil)))
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s: Event does not include a job" %
                       (caller_name()))
        # Instantiate the cgroup utility class
        vnode = None
        if hasattr(e, 'vnode_list'):
            if hostname in e.vnode_list.keys():
                vnode = e.vnode_list[hostname]
        cgroup = CgroupUtils(hostname, vnode)
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Cgroup utility class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG3, "%s: %s" % (caller_name(), repr(cgroup)))
        # Bail out if there is nothing to do
        if len(cgroup.subsystems) < 1:
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: All cgroups disabled" %
                       (caller_name()))
            e.accept()

        # Call the appropriate handler
        if hooks.invoke_handler(e, cgroup, jobutil) is True:
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Hook handler returned success" %
                       (caller_name()))
            e.accept()
        else:
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Hook handler returned failure" %
                       (caller_name()))
            e.reject()

    except SystemExit:
        # The e.accept() and e.reject() methods generate a SystemExit
        # exception.
        pass

    except AdminError, exc:
        # Something on the system is misconfigured
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("Admin error in %s handling %s event" %
               (e.hook_name, hooks.event_name(e.type)))
        if jobutil is not None:
            msg += (" for job %s" % (e.job.id))
            try:
                e.job.Hold_Types = pbs.hold_types("s")
                e.job.rerun()
                msg += " (suspended)"
            except:
                msg += " (suspend failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        e.reject(msg)

    except UserError, exc:
        # User must correct problem and resubmit job
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("User error in %s handling %s event" %
               (e.hook_name, hooks.event_name(e.type)))
        if jobutil is not None:
            msg += (" for job %s" % (e.job.id))
            try:
                e.job.delete()
                msg += " (deleted)"
            except:
                msg += " (delete failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        e.reject(msg)

    except JobValueError, exc:
        # Something in PBS is misconfigured
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("Job value error in %s handling %s event" %
               (e.hook_name, hooks.event_name(e.type)))
        if jobutil is not None:
            msg += (" for job %s" % (e.job.id))
            try:
                e.job.Hold_Types = pbs.hold_types("s")
                e.job.rerun()
                msg += " (suspended)"
            except:
                msg += " (suspend failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        e.reject(msg)

    except Exception, exc:
        # Catch all other exceptions and report them.
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("Unexpected error in %s handling %s event" %
               (e.hook_name, hooks.event_name(e.type)))
        if jobutil is not None:
            msg += (" for job %s" % (e.job.id))
            try:
                e.job.Hold_Types = pbs.hold_types("s")
                e.job.rerun()
                msg += " (suspended)"
            except:
                msg += " (suspend failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        e.reject(msg)

# line below required for unittesting
if __name__ == "__builtin__":
    start_time = time.time()
    try:
        main()
    except SystemExit:
        # The e.accept() and e.reject() methods generate a SystemExit
        # exception.
        pass
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
    finally:
        pbs.logmsg(pbs.EVENT_DEBUG, "Elapsed time: %0.4lf" %
                   (time.time() - start_time))

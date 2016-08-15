# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under a
# commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

# NOTES:
#
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

# Imports from __future__ must happen first.
# The following line may be removed once PBS Pro 12.x is unsupported.
from __future__ import with_statement

# Additional imports
import sys
import os
import fcntl
import stat
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
import operator
import pwd
import fnmatch
try:
    import json
except:
    import simplejson as json
import pbs

# Define some globals that get set in main
pbs_version = (0, 0, 0)
pbs_home = ''
pbs_exec = ''

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


# Timeout encountered.
class TimeoutError(ProcessingError):
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
        if new not in logs:
            raise ValueError('Invalid unit value')
        val, old = re.match('([-+]?\d+)([bkmgtpezy]?)',
                            str(value).lower()).groups()
        val = int(val)
        if val < 0:
            raise ValueError('Value may not be negative')
        if old not in logs:
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
                         str(value).lower()).groups()
    # Check to see if there was not unit of time specified
    if factor is None:
        factor = ''
    # Check to see if the unit is valid
    if str.lower(factor) not in multipliers:
        raise ValueError('Time unit not recognized.')
    # Convert the value to seconds
    value = float(n) * float(multipliers[str.lower(factor)])
    if return_unit != 's':
        value = value / multipliers[str.lower(return_unit)]
    # _pbs_v1.validate_input breaks with very small time values
    # because Python converts them to values like 1e-05
    if value < 0.001:
        value = 0.0
    return value


# json hook to convert lists from unicode to utf-8
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


# json hook to convert dictionaries from unicode to utf-8
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


# Merge together two multilevel dictionaries where new
# takes precedence over base
def merge_dict(base, new):
    if type(base) is not dict:
        raise ValueError('base must be type dict')
    if type(new) is not dict:
        raise ValueError('new must be type dict')
    newkeys = new.keys()
    merged = {}
    for key in base:
        if key in newkeys and type(base[key]) is dict:
            # Take it off the list of keys to copy
            newkeys.remove(key)
            merged[key] = merge_dict(base[key], new[key])
        else:
            merged[key] = copy.deepcopy(base[key])
    # Copy the remaining unique keys from new
    for key in newkeys:
        merged[key] = copy.deepcopy(new[key])
    return merged


# Convert condensed list format (with ranges) to a Python list
def expand_list(input):
    # The input string is a comma separated list of digits and ranges.
    # Examples include:
    # 0-3,8-11
    # 0,2,4,6
    # 2,5-7,10
    list = []
    s = input.strip()
    if not s:
        return list
    for r in s.split(','):
        if '-' in r[1:]:
            start, end = r.split('-', 1)
            for i in range(int(start), int(end) + 1):
                list.append(i)
        else:
            list.append(int(r))
    return list


# Return a list of files similar to the find command
def find_files(path, name=None, kind=None):
    result = []
    for root, dirs, files in os.walk(path):
        if name is None:
            filtered = files
        else:
            filtered = fnmatch.filter(files, name)
        for f in filtered:
            p = os.path.join(root, f)
            if kind is None:
                result.append(p)
                continue
            m = os.lstat(p).st_mode
            if 'f' in kind and stat.S_ISREG(m):
                result.append(p)
            elif 'l' in kind and stat.S_ISLNK(m):
                result.append(p)
            elif 'c' in kind and stat.S_ISCHR(m):
                result.append(p)
            elif 'b' in kind and stat.S_ISBLK(m):
                result.append(p)
            elif 'p' in kind and stat.S_ISFIFO(m):
                result.append(p)
            elif 's' in kind and stat.S_ISSOCK(m):
                result.append(p)
        if name is None:
            filtered = dirs
        else:
            filtered = fnmatch.filter(dirs, name)
        for d in filtered:
            p = os.path.join(root, d)
            if kind is None:
                result.append(p)
                continue
            m = os.lstat(p).st_mode
            if 'd' in kind and stat.S_ISDIR(m):
                result.append(p)
            elif 'l' in kind and stat.S_ISLNK(m):
                result.append(p)
    return result


# Return a properly cast zero value
def initialize_resource(resc):
    if isinstance(resc, pbs.pbs_int):
        return pbs.pbs_int(0)
    if isinstance(resc, pbs.pbs_float):
        return pbs.pbs_float(0)
    if isinstance(resc, pbs.size):
        return pbs.size('0')
    if isinstance(resc, int):
        return 0
    if isinstance(resc, float):
        return 0.0
    if isinstance(resc, list):
        return []
    if isinstance(resc, dict):
        return {}
    if isinstance(resc, tuple):
        return ()
    if isinstance(resc, str):
        return ''
    return resc


# Helper function to ignore suspended jobs when removing
# "already used" resources
def job_to_be_ignored(jobid):
    # This will fail for versions of PBS prior to 13.0
    pbs_conf = pbs.get_pbs_conf()
    pbs_exec = pbs_conf['PBS_EXEC']
    printjob_cmd = os.path.join(pbs_exec, 'bin', 'printjob')
    cmd = [printjob_cmd, jobid]
    substate = None
    # Get job substate based on printjob output
    try:
        pbs.logmsg(pbs.EVENT_DEBUG4, "cmd: %s" % cmd)
        # Collect the job substate information
        process = subprocess.Popen(cmd, shell=False,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        out, err = process.communicate()
        # Find the job substate
        substate_re = re.compile(r"substate:\s+(?P<jobstate>\S+)\s+")
        substate = substate_re.search(out)
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "Unexpected error in job_to_be_ignored: %s" %
                   string.join([repr(sys.exc_info()[0]),
                                repr(sys.exc_info()[1])], ' '))
        out = "Unknown: failed to run " + printjob_cmd
    if substate is not None:
        substate = substate.group('jobstate')
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Job %s has substate %s" % (jobid, substate))
        suspended_substates = ['0x2b', '0x2d', 'unknown']
        return (substate in suspended_substates)
    else:
        return False


# ============================================================================
# Utility classes
# ============================================================================

#
# CLASS lock
#
class lock:

    def __init__(self, path):
        self.path = path
        self.fd = None

    def __enter__(self):
        self.fd = open(self.path, 'w')
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def __exit__(self, exc, val, traceback):
        if self.fd:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            self.fd.close()


#
# CLASS dotimeout
#
class dotimeout:

    def __init__(self, duration=1, message='Operation timed out.'):
        self.duration = duration
        self.message = message

    def handler(self, sig, frame):
        raise TimeoutError(self.message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handler)
        signal.alarm(self.duration)

    def __exit__(self, exc, val, traceback):
        signal.alarm(0)


#
# CLASS HookUtils
#
class HookUtils:

    def __init__(self, hook_events=None):
        if hook_events is not None:
            self.hook_events = hook_events
        else:
            # Defined in the order they appear in module_pbs_v1.c
            self.hook_events = {}
            self.hook_events[pbs.QUEUEJOB] = {
                'name': 'queuejob',
                'handler': None
            }
            self.hook_events[pbs.MODIFYJOB] = {
                'name': 'modifyjob',
                'handler': None
            }
            self.hook_events[pbs.RESVSUB] = {
                'name': 'resvsub',
                'handler': None
            }
            self.hook_events[pbs.MOVEJOB] = {
                'name': 'movejob',
                'handler': None
            }
            self.hook_events[pbs.RUNJOB] = {
                'name': 'runjob',
                'handler': None
            }
            self.hook_events[pbs.PROVISION] = {
                'name': 'provision',
                'handler': None
            }
            self.hook_events[pbs.EXECJOB_BEGIN] = {
                'name': 'execjob_begin',
                'handler': self.__execjob_begin_handler
            }
            self.hook_events[pbs.EXECJOB_PROLOGUE] = {
                'name': 'execjob_prologue',
                'handler': None
            }
            self.hook_events[pbs.EXECJOB_EPILOGUE] = {
                'name': 'execjob_epilogue',
                'handler': self.__execjob_epilogue_handler
            }
            self.hook_events[pbs.EXECJOB_PRETERM] = {
                'name': 'execjob_preterm',
                'handler': None
            }
            self.hook_events[pbs.EXECJOB_END] = {
                'name': 'execjob_end',
                'handler': self.__execjob_end_handler
            }
            self.hook_events[pbs.EXECJOB_LAUNCH] = {
                'name': 'execjob_launch',
                'handler': self.__execjob_launch_handler
            }
            self.hook_events[pbs.EXECHOST_PERIODIC] = {
                'name': 'exechost_periodic',
                'handler': self.__exechost_periodic_handler
            }
            self.hook_events[pbs.EXECHOST_STARTUP] = {
                'name': 'exechost_startup',
                'handler': self.__exechost_startup_handler
            }
            if pbs_version[0] >= 13:
                self.hook_events[pbs.EXECJOB_ATTACH] = {
                    'name': 'execjob_attach',
                    'handler': self.__execjob_attach_handler
                }
            self.hook_events[pbs.MOM_EVENTS] = {
                'name': 'mom_events',
                'handler': None
            }

    def __repr__(self):
        return ("HookUtils(%s)" % (repr(self.hook_events)))

    def event_name(self, hooktype):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if hooktype in self.hook_events:
            return self.hook_events[hooktype]['name']
        else:
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "%s: Type: %s not found" % (caller_name(), type))
            return None

    def hashandler(self, hooktype):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if hooktype in self.hook_events:
            return self.hook_events[hooktype]['handler'] is not None
        else:
            return None

    def invoke_handler(self, event, cgroup, jobutil, *args):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: UID: real=%d, effective=%d" %
                   (caller_name(), os.getuid(), os.geteuid()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: GID: real=%d, effective=%d" %
                   (caller_name(), os.getgid(), os.getegid()))
        if self.hashandler(event.type):
            result = self.hook_events[event.type][
                'handler'](event, cgroup, jobutil, *args)
            return result
        else:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "%s: %s event not handled by this hook." %
                       (caller_name(), self.event_name(event.type)))

    def __execjob_begin_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Instantiate the NodeConfig class for get_memory_on_node and
        # get_vmem_on node
        node = NodeConfig(cgroup.cfg)
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: NodeConfig class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s" % (caller_name(), repr(node)))
        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Host assigned job resources: %s" %
                   (caller_name(), jobutil.assigned_resources))
        with lock(cgroup.cfg['cgroup_lock_file']):
            # Make sure the parent cgroup directories exist
            cgroup.create_paths()
            # Make sure the cgroup does not already exist
            # from a failed run
            cgroup.delete(e.job.id, False)
            # Create the cgroup(s) for the job
            cgroup.create_job(e.job.id, node)
            # Configure the new cgroup
            cgroup.configure_job(e.job.id, jobutil.assigned_resources, node)
            # Initialize resource usage for the job
            cgroup.update_job_usage(e.job.id, e.job.resources_used)
            # Write out the assigned resources
            cgroup.write_out_cgroup_assigned_resources(e.job.id)
            # Write out the environment variable for the host (pbs_attach)
            if 'device_names' in cgroup.assigned_resources:
                pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Devices: %s" %
                           (caller_name(),
                            cgroup.assigned_resources['device_names']))
                env_list = []
                if len(cgroup.assigned_resources['device_names']) > 0:
                    mics = []
                    gpus = []
                    for key in cgroup.assigned_resources['device_names']:
                        if key.startswith('mic'):
                            mics.append(key[3:])
                        elif key.startswith('nvidia'):
                            gpus.append(key[6:])
                    if len(mics) > 0:
                        env_list.append('OFFLOAD_DEVICES="%s"' %
                                        string.join(mics, ','))
                    if len(gpus) > 0:
                        # Don't put quotes around the values. ex "0" or "0,1".
                        # This will cause it to fail.
                        env_list.append('CUDA_VISIBLE_DEVICES=%s' %
                                        string.join(gpus, ','))
                pbs.logmsg(pbs.EVENT_DEBUG2, "ENV_LIST: %s" % env_list)
                cgroup.write_out_cgroup_host_job_env_file(e.job.id, env_list)
        return True

    def __execjob_epilogue_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # The resources_used information has a base type of pbs_resource.
        with lock(cgroup.cfg['cgroup_lock_file']):
            # Update the usage data
            cgroup.update_job_usage(e.job.id, e.job.resources_used)
            # The job script has completed, but the obit has not been sent.
            # Delete the cgroups for this job so that they don't interfere
            # with incoming jobs assigned to this node.
            cgroup.delete(e.job.id)
        return True

    def __execjob_end_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # The cgroup was already deleted in the epilogue handler.
        # Remove the assigned_resources and job_env files.
        filelist = []
        filelist.append(os.path.join(cgroup.hook_storage_dir, e.job.id))
        filelist.append(cgroup.host_job_env_filename % e.job.id)
        for filename in filelist:
            try:
                os.remove(filename)
            except OSError:
                pbs.logmsg(pbs.EVENT_DEBUG4, "File: %s not found" % (filename))
            except:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Error removing file: %s" % (filename))
        return True

    def __execjob_launch_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Add the parent process id to the appropriate cgroups.
        cgroup.add_pids(os.getppid(), jobutil.job.id)
        # FUTURE: Add environment variable to the job environment
        # if job requested mic or gpu
        cgroup.read_in_cgroup_assigned_resources(e.job.id)
        if cgroup.assigned_resources is not None:
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "assigned_resources: %s" %
                       (cgroup.assigned_resources))
            cgroup.setup_job_devices_env()
        return True

    def __exechost_periodic_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        with lock(cgroup.cfg['cgroup_lock_file']):
            # Cleanup cgroups for jobs not present on this node
            remaining = cgroup.cleanup_orphans(e.job_list)
            # Online nodes that were offlined due to a cgroup not cleaning up
            if remaining == 0 and cgroup.cfg['online_offlined_nodes']:
                vnode = pbs.event().vnode_list[cgroup.hostname]
                if os.path.isfile(cgroup.offline_file):
                    msg = 'Orphan cgroup(s) have been cleaned up. '
                    # Check with the server to see if the node comment matches
                    try:
                        with dotimeout(10, 'Timed out contacting server'):
                            comment = \
                                pbs.server().vnode(cgroup.hostname).comment
                            while not comment:
                                time.sleep(1)
                                comment = \
                                    pbs.server().vnode(cgroup.hostname).comment
                            pbs.logmsg(pbs.EVENT_DEBUG4,
                                       "Comment: %s" % comment)
                    except:
                        pbs.logmsg(pbs.EVENT_DEBUG,
                                   "Unable to contact server for node comment")
                        comment = None
                    if comment == cgroup.offline_msg:
                        msg += 'Node will be brought back online.'
                        vnode.state = pbs.ND_FREE
                        vnode.comment = None
                    else:
                        msg += 'The node comment has changed since the node '
                        msg += 'was offlined. Node will remain offline.'
                    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: %s" %
                               (caller_name(), msg))
                    # Remove file
                    try:
                        os.remove(cgroup.offline_file)
                    except:
                        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Failed to remove %s" %
                                   (caller_name(), msg))
            # Update the resource usage information for each job
            if cgroup.cfg['periodic_resc_update']:
                for job in e.job_list:
                    pbs.logmsg(pbs.EVENT_DEBUG4,
                               "%s: Updating resource usage for %s" %
                               (caller_name(), job))
                    try:
                        cgroup.update_job_usage(job,
                                                e.job_list[job].resources_used)
                    except:
                        pbs.logmsg(pbs.EVENT_DEBUG,
                                   "%s: Resource usage update failed for %s" %
                                   (caller_name(), job))
        return True

    def __exechost_startup_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        cgroup.create_paths()
        node = NodeConfig(cgroup.cfg)
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: NodeConfig class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s" % (caller_name(), repr(node)))
        node.create_vnodes()
        hn = node.hostname
        # The memory limits are interdependent and might fail when set.
        # There are three limits. Worst case scenario is to loop three
        # times in order to set them all.
        for _ in range(3):
            result = True
            if 'memory' in cgroup.subsystems:
                val = node.get_memory_on_node(cgroup.cfg)
                if val is not None:
                    if not cgroup.cfg['vnode_per_numa_node']:
                        e.vnode_list[hn].resources_available['mem'] = \
                            pbs.size(val)
                try:
                    cgroup.set_limit('mem', val)
                except:
                    result = False
            if 'memsw' in cgroup.subsystems:
                val = node.get_vmem_on_node(cgroup.cfg)
                if val is not None:
                    e.vnode_list[hn].resources_available['vmem'] = \
                        pbs.size(val)
                    try:
                        cgroup.set_limit('vmem', val)
                    except:
                        result = False
            if 'hugetlb' in cgroup.subsystems:
                val = node.get_hpmem_on_node(cgroup.cfg)
                if val is not None:
                    e.vnode_list[hn].resources_available['hpmem'] = \
                        pbs.size(val)
                    try:
                        cgroup.set_limit('hpmem', val)
                    except:
                        result = False
            if result:
                return True
        return False

    def __execjob_attach_handler(self, e, cgroup, jobutil):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logjobmsg(jobutil.job.id, "%s: Attaching PID %s" %
                      (caller_name(), e.pid))
        # Add the job process id to the appropriate cgroups.
        cgroup.add_pids(e.pid, jobutil.job.id)
        return True


#
# CLASS JobUtils
#
class JobUtils:

    def __init__(self, job, hostname=None, assigned_resources=None):
        self.job = job
        if hostname is not None:
            self.hostname = hostname
        else:
            self.hostname = pbs.get_local_nodename()
        if assigned_resources is not None:
            self.assigned_resources = assigned_resources
        else:
            self.assigned_resources = self.__get_assigned_job_resources()

    def __repr__(self):
        return ("JobUtils(%s, %s, %s)" %
                (repr(self.job),
                 repr(self.hostname),
                 repr(self.assigned_resources)))

    # Return a dictionary of assigned resources on the local node
    def __get_assigned_job_resources(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Bail out if no hostname was provided
        if self.hostname is None:
            raise CgroupProcessingError('No hostname available')
        # Bail out if no job information is present
        if self.job is None:
            raise CgroupProcessingError('No job information available')
        # Create a list of local vnodes
        vnodes = []
        vnhost_pattern = "%s\[[\d+]\]" % self.hostname
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: vnhost pattern: %s" %
                   (caller_name(), vnhost_pattern))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Job exec_vnode list: %s" %
                   (caller_name(), self.job.exec_vnode))
        for match in re.findall(vnhost_pattern, str(self.job.exec_vnode)):
            vnodes.append(match)
        if vnodes:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Vnodes on %s: %s" %
                       (caller_name(), self.hostname, vnodes))
        # Collect host assigned resources
        resources = {}
        for chunk in self.job.exec_vnode.chunks:
            if vnodes:
                # Vnodes list is not empty
                if chunk.vnode_name not in vnodes:
                    continue
                if 'vnodes' not in resources:
                    resources['vnodes'] = {}
                if chunk.vnode_name not in resources['vnodes']:
                    resources['vnodes'][chunk.vnode_name] = {}
                # Initialize any missing resources for the vnode.
                # This check is needed because some resources might
                # not be present in each chunk of a job. For example:
                # exec_vnodes =
                # (node1[0]:ncpus=4:mem=4gb+node1[1]:mem=2gb) +
                # (node1[1]:ncpus=3+node[0]:ncpus=1:mem=4gb)
                for resc in chunk.chunk_resources.keys():
                    vnresc = resources['vnodes'][chunk.vnode_name]
                    if resc in vnresc.keys():
                        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s:%s defined" %
                                   (caller_name(), chunk.vnode_name, resc))
                    else:
                        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s:%s missing" %
                                   (caller_name(), chunk.vnode_name, resc))
                        vnresc[resc] = \
                            initialize_resource(chunk.chunk_resources[resc])
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Chunk %s resources: %s" %
                           (caller_name(), chunk.vnode_name, resources))
            else:
                # Vnodes list is empty
                if chunk.vnode_name != self.hostname:
                    continue
            for resc in chunk.chunk_resources.keys():
                if resc not in resources.keys():
                    resources[resc] = \
                        initialize_resource(chunk.chunk_resources[resc])
                # Add resource value to total
                if type(chunk.chunk_resources[resc]) in \
                        [pbs.pbs_int, pbs.pbs_float, pbs.size]:
                    resources[resc] += chunk.chunk_resources[resc]
                    pbs.logmsg(pbs.EVENT_DEBUG4,
                               "%s: resources[%s][%s] is now %s" %
                               (caller_name(), self.hostname, resc,
                                resources[resc]))
                    if vnodes:
                        resources['vnodes'][chunk.vnode_name][resc] += \
                            chunk.chunk_resources[resc]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               "%s: Setting resource %s to string %s" %
                               (caller_name(), resc,
                                str(chunk.chunk_resources[resc])))
                    resources[resc] = str(chunk.chunk_resources[resc])
                    if vnodes:
                        resources['vnodes'][chunk.vnode_name][resc] = \
                            str(chunk.chunk_resources[resc])
        if resources:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Resources for %s: %s" %
                       (caller_name(), self.hostname, repr(resources)))
        else:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "%s: No resources assigned to host %s" %
                       (caller_name(), self.hostname))
        # Return assigned resources for specified host
        return resources

    # Write a message to the job stdout file
    def write_to_stderr(self, job, msg):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            filename = job.stderr_file()
            if filename is None:
                return
            with open(filename, 'a') as fd:
                fd.write(msg)
        except:
            pass

    # Write a message to the job stdout file
    def write_to_stdout(self, job, msg):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            filename = job.stdout_file()
            if filename is None:
                return
            with open(filename, 'a') as fd:
                fd.write(msg)
        except:
            pass


#
# CLASS NodeConfig
#
class NodeConfig:

    def __init__(self, cfg, hostname=None, cpuinfo=None, meminfo=None,
                 numa_nodes=None, devices=None):
        self.cfg = cfg
        if hostname is not None:
            self.hostname = hostname
        else:
            self.hostname = pbs.get_local_nodename()
        if cpuinfo is not None:
            self.cpuinfo = cpuinfo
        else:
            self.cpuinfo = self.__discover_cpuinfo()
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
        # Add the devices count i.e. nmics and ngpus to the numa nodes
        self.__add_device_counts_to_numa_nodes()

    def __repr__(self):
        return ("NodeConfig(%s, %s, %s, %s, %s, %s)" %
                (repr(self.cfg),
                 repr(self.hostname),
                 repr(self.cpuinfo),
                 repr(self.meminfo),
                 repr(self.numa_nodes),
                 repr(self.devices)))

    def __add_device_counts_to_numa_nodes(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "Node Devices: %s" % self.devices)
        for c in self.devices:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Device class: %s" %
                       (caller_name(), c))
            if c == 'mic' or c == 'gpu':
                pbs.logmsg(pbs.EVENT_DEBUG4, "Devices: %s" % self.devices[c])
                for i in self.devices[c]:
                    numa_node = self.devices[c][i]['numa_node']
                    if c == 'mic' and i.find('mic') != -1:
                        if 'nmics' not in self.numa_nodes[numa_node]:
                            self.numa_nodes[numa_node]['nmics'] = 1
                        else:
                            self.numa_nodes[numa_node]['nmics'] += 1
                    elif c == 'gpu':
                        if 'ngpus' not in self.numa_nodes[numa_node]:
                            self.numa_nodes[numa_node]['ngpus'] = 1
                        else:
                            self.numa_nodes[numa_node]['ngpus'] += 1
        pbs.logmsg(pbs.EVENT_DEBUG4, "NUMA nodes: %s" % (self.numa_nodes))
        return

    # Discover what type of hardware is on this node and how is it partitioned
    def __discover_numa_nodes(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        numa_nodes = {}
        for d in glob.glob(os.path.join(os.sep, "sys", "devices", "system",
                                        "node", "node*")):
            # The basename will be node0, node1, etc.
            # Capture the numeric portion as the identifier/ordinal.
            id = int(os.path.basename(d)[4:])
            if id not in numa_nodes:
                numa_nodes[id] = {}
                numa_nodes[id]['devices'] = []
            with open(os.path.join(d, "cpulist"), 'r') as fd:
                numa_nodes[id]['cpus'] = expand_list(fd.readline())
            with open(os.path.join(d, "meminfo"), 'r') as fd:
                for line in fd:
                    # Each line will contain four or five fields. Examples:
                    # Node 0 MemTotal:       32995028 kB
                    # Node 0 HugePages_Total:     0
                    entries = line.split()
                    if len(entries) < 4:
                        continue
                    if entries[2] == "MemTotal:":
                        numa_nodes[id]['MemTotal'] = \
                            convert_size(entries[3] + entries[4], 'kb')
                    elif entries[2] == "HugePages_Total:":
                        numa_nodes[id]['HugePages_Total'] = entries[3]
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s" % (caller_name(), numa_nodes))
        return numa_nodes

    # Identify devices and to which numa nodes they are attached
    def __discover_devices(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        devices = {}
        # First loop identifies all devices and determines their true path,
        # major/minor device IDs, and NUMA node affiliation (if any).
        for path in glob.glob(os.path.join(os.sep, "sys", "class", "*", "*")):
            # Skip this path if it is not a directory
            if not os.path.isdir(path):
                continue
            p = path.split(os.sep)   # Path components
            c = p[-2]   # Device class
            i = p[-1]   # Device instance
            if c not in devices:
                devices[c] = {}
            devices[c][i] = {}
            devices[c][i]['realpath'] = os.path.realpath(path)
            # Determine the PCI bus ID of the device
            devices[c][i]['bus_id'] = ''
            p = devices[c][i]['realpath'].split(os.sep)
            t = p[3]
            if t.startswith('pci'):
                devices[c][i]['bus_id'] = p[4]
            # Determine the major and minor device numbers
            file = os.path.join(devices[c][i]['realpath'], 'dev')
            devices[c][i]['major'] = None
            devices[c][i]['minor'] = None
            if os.path.isfile(file):
                with open(file, 'r') as fd:
                    major, minor = map(int, fd.readline().strip().split(':'))
                    devices[c][i]['major'] = major
                    devices[c][i]['minor'] = minor
            numa_node = -1
            dir = os.path.join(devices[c][i]['realpath'], 'device')
            # The numa_node file is not always in the same place
            # so work our way up the path trying to find it.
            while len(dir.split(os.sep)) > 2:
                file = os.path.join(dir, 'numa_node')
                if os.path.isfile(file):
                    # The file should contain a single integer
                    with open(file, 'r') as fd:
                        numa_node = int(fd.readline().strip())
                    break
                dir = os.path.dirname(dir)
            if numa_node < 0:
                numa_node = 0
            devices[c][i]['numa_node'] = numa_node
        # Second loop determines device types and their location
        # under /dev. Only look for block and character devices.
        for path in find_files(os.path.join(os.sep, 'dev'), kind=['b', 'c']):
            # If the stat fails, log it and continue.
            try:
                s = os.stat(path)
            except:
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Stat error on %s" %
                           (caller_name(), path))
                continue
            major = os.major(s.st_rdev)
            minor = os.minor(s.st_rdev)
            for c in devices:
                for i in devices[c]:
                    if 'type' not in devices[c][i]:
                        devices[c][i]['type'] = None
                    if 'device' not in devices[c][i]:
                        devices[c][i]['device'] = None
                    if devices[c][i]['major'] == major:
                        if devices[c][i]['minor'] == minor:
                            if stat.S_ISCHR(s.st_mode):
                                devices[c][i]['type'] = 'c'
                            else:
                                devices[c][i]['type'] = 'b'
                            devices[c][i]['device'] = path
        # Check to see if there are gpus on the node and copy them
        # into their own dictionary.
        devices['gpu'] = {}
        gpus = self.__discover_gpus()
        if gpus:
            for c in devices:
                for i in devices[c]:
                    for g in gpus:
                        if gpus[g] == devices[c][i]['bus_id']:
                            devices['gpu'][g] = devices[c][i]
        pbs.logmsg(pbs.EVENT_DEBUG4, "Discovered devices: %s" % (devices))
        return devices

    # Return a dictionary where the keys are the name of the GPU devices
    # and the values are the PCI bus IDs.
    def __discover_gpus(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        gpus = {}
        cmd = [self.cfg['nvidia-smi'], '-q', '-x']
        pbs.logmsg(pbs.EVENT_DEBUG4, "NVIDIA SMI command: %s" % cmd)
        try:
            # Try running the  nvidia-smi command
            process = subprocess.Popen(cmd, shell=False,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            out, err = process.communicate()
        except:
            pbs.logmsg(pbs.EVENT_DEBUG, "Failed to execute: %s" %
                       string.join(cmd, ' '))
            pbs.logmsg(pbs.EVENT_DEBUG, "No GPUs found")
            return gpus
        try:
            # Try parsing the output
            import xml.etree.ElementTree as xmlet
            root = xmlet.fromstring(out)
            pbs.logmsg(pbs.EVENT_DEBUG4, "root.tag: %s" % root.tag)
            for child in root:
                if child.tag == "gpu":
                    pci_bus_id = child.get('id')
                    name = 'nvidia%s' % child.find('minor_number').text
                    gpus[name] = pci_bus_id
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Unexpected error: %s" % sys.exc_info()[0])
        pbs.logmsg(pbs.EVENT_DEBUG2, "GPUs: %s" % gpus)
        return gpus

    # Return a dictionary where the keys are the NUMA node ordinals
    # and the values are the various memory sizes
    def __discover_meminfo(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
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
        pbs.logmsg(pbs.EVENT_DEBUG4, "Discover meminfo: %s" % meminfo)
        return meminfo

    # Return a dictionary where the keys include both global settings
    # and individual CPU characteristics
    def __discover_cpuinfo(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        cpuinfo = {}
        cpuinfo['cpu'] = {}
        proc = None
        with open(os.path.join(os.sep, "proc", "cpuinfo"), 'r') as fd:
            for line in fd:
                entries = line.strip().split(":")
                if len(entries) < 2:
                    # Blank line indicates end of processor
                    proc = None
                    continue
                key = entries[0].strip()
                val = entries[1].strip()
                if proc is None and key != 'processor':
                    raise ProcessingError('Failed to parse /proc/cpuinfo')
                if key == 'processor':
                    proc = int(val)
                    if proc in cpuinfo:
                        raise ProcessingError('Duplicate CPU ID found')
                    cpuinfo['cpu'][proc] = {}
                    cpuinfo['cpu'][proc]['threads'] = []
                elif key == 'flags':
                    cpuinfo['cpu'][proc][key] = val.split()
                elif val.isdigit():
                    cpuinfo['cpu'][proc][key] = int(val)
                else:
                    cpuinfo['cpu'][proc][key] = val
        if not cpuinfo['cpu']:
            raise ProcessingError('No CPU information found')
        cpuinfo['logical_cpus'] = len(cpuinfo['cpu'])
        cpuinfo['hyperthreads_per_core'] = 1
        cpuinfo['hyperthreads'] = []
        # Now try to construct a dictionary with hyperthread information
        # if this is an Intel based processor
        try:
            if 'Intel' in cpuinfo['cpu'][0]['vendor_id']:
                if 'ht' in cpuinfo['cpu'][0]['flags']:
                    cpuinfo['hyperthreads_per_core'] = \
                        cpuinfo['cpu'][0]['siblings'] / \
                        cpuinfo['cpu'][0]['cpu cores']
                    # Map hyperthreads to physical cores
                    if cpuinfo['hyperthreads_per_core'] > 1:
                        pbs.logmsg(pbs.EVENT_DEBUG4,
                                   "Mapping hyperthreads to cores")
                        cores = cpuinfo['cpu']
                        threads = []
                        # CPUs with matching core IDs are hyperthreads
                        # sharing the same physical core. Loop through
                        # the cores to construct a list of threads.
                        for xid in cores:
                            x = cpuinfo['cpu'][xid]
                            for yid in cores:
                                y = cpuinfo['cpu'][yid]
                                if xid >= yid:
                                    continue
                                if x['physical id'] != y['physical id']:
                                    continue
                                if x['core id'] == y['core id']:
                                    cpuinfo['cpu'][xid]['threads'].append(yid)
                                    threads.append(yid)
                        pbs.logmsg(pbs.EVENT_DEBUG4, "HT cores: %s" % threads)
                        cpuinfo['hyperthreads'] = threads
        except:
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Hyperthreading check failed" %
                       (caller_name()))
        cpuinfo['physical_cpus'] = cpuinfo['logical_cpus'] / \
            cpuinfo['hyperthreads_per_core']
        pbs.logmsg(pbs.EVENT_DEBUG4, "Discover cpuinfo: %s" % cpuinfo)
        return cpuinfo

    # Gather the jobs assigned to the natural vnode from the server
    def gather_jobs_on_node_from_server(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Get the job list from the server
        jobs = None
        try:
            jobs = pbs.server().vnode(self.hostname).jobs
        except:
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "Unable to contact server to get jobs")
            return None
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Jobs from server for %s: %s" % (self.hostname, jobs))
        if jobs is None:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "No jobs found on %s " % (self.hostname))
            return None
        jobs_list = {}
        for job in jobs.split(','):
            # The job list from the node has a space in front of the job id
            # This must be removed or it will not match the cgroup dir
            jobs_list[job.split('/')[0].strip()] = 0
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Jobs on %s: %s" % (self.hostname, jobs_list.keys()))
        return jobs_list.keys()

    # Gather the jobs assigned to this node and local vnodes
    def gather_jobs_on_node(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Get the job list from the jobs directory
        mom_jobdir = os.path.join(pbs_home, 'mom_priv', 'jobs')
        jobs_list = []
        try:
            for f in os.listdir(mom_jobdir):
                if fnmatch.fnmatch(f, "*.JB"):
                    jobs_list.append(f[:-3])
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "Jobs from server for %s: %s" %
                       (self.hostname, repr(jobs_list)))
            return jobs_list
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Could not get job list from mom_priv/jobs for %s" %
                       self.hostname)
            raise ProcessingError('Error gathering job information')

    # Get the memory resource on this mom
    def get_memory_on_node(self, config, MemTotal=None):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Calculate total memory
        try:
            if MemTotal is None:
                total = size_as_int(self.meminfo['MemTotal'])
            else:
                total = size_as_int(MemTotal)
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       '%s: Could not determine total node memory' %
                       (caller_name()))
            raise
        if total <= 0:
            raise ValueError('Total node memory value invalid')
        pbs.logmsg(pbs.EVENT_DEBUG4, "total mem: %d" % total)
        # Calculate reserved memory
        reserved = 0
        try:
            reserve_percent = config['cgroup']['memory']['reserve_percent']
            reserved += (total * int(reserve_percent)) / 100
            reserve_amount = config['cgroup']['memory']['reserve_amount']
            reserved += size_as_int(reserve_amount)
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       '%s: Could not determine reserved node memory' %
                       (caller_name()))
            raise
        pbs.logmsg(pbs.EVENT_DEBUG4, "reserved mem: %d" % reserved)
        # Calculate remaining memory
        remaining = total - reserved
        if remaining <= 0:
            raise ValueError('Too much reserved memory')
        pbs.logmsg(pbs.EVENT_DEBUG4, "remaining mem: %d" % remaining)
        amount = convert_size(str(remaining), 'kb')
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Returning: %s" %
                   (caller_name(), amount))
        return amount

    # Get the virtual memory resource on this mom
    def get_vmem_on_node(self, config, MemTotal=None):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Calculate total swap
        try:
            if MemTotal is None:
                swap = size_as_int(self.meminfo['SwapTotal'])
            else:
                swap = size_as_int(MemTotal)
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       '%s: Could not determine total node swap' %
                       (caller_name()))
            raise
        if swap <= 0:
            swap = 0
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       '%s: No swap space detected' %
                       (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "total swap: %d" % swap)
        # Calculate total vmem
        total = size_as_int(self.get_memory_on_node(config))
        pbs.logmsg(pbs.EVENT_DEBUG4, "total mem: %d" % total)
        total += swap
        pbs.logmsg(pbs.EVENT_DEBUG4, "total vmem: %d" % total)
        # Calculate reserved vmem
        reserved = 0
        try:
            reserve_percent = config['cgroup']['memsw']['reserve_percent']
            reserved += (total * int(reserve_percent)) / 100
            reserve_amount = config['cgroup']['memsw']['reserve_amount']
            reserved += size_as_int(reserve_amount)
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       '%s: Could not determine reserved node vmem' %
                       (caller_name()))
            raise
        pbs.logmsg(pbs.EVENT_DEBUG4, "reserved vmem: %d" % reserved)
        # Calculate remaining vmem
        remaining = total - reserved
        if remaining <= 0:
            raise ValueError('Too much reserved vmem')
        pbs.logmsg(pbs.EVENT_DEBUG4, "remaining vmem: %d" % remaining)
        amount = convert_size(str(remaining), 'kb')
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Returning: %s" %
                   (caller_name(), amount))
        return amount

    # Get the huge page memory resource on this mom
    def get_hpmem_on_node(self, config, MemTotal=None):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Calculate hpmem
        try:
            if MemTotal is None:
                total = size_as_int(self.meminfo['Hugepagesize'])
                total *= (self.meminfo['HugePages_Total'] -
                          self.meminfo['HugePages_Rsvd'])
            else:
                total = size_as_int(MemTotal)
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       '%s: Could not determine huge page availability' %
                       (caller_name()))
            raise
        if total <= 0:
            total = 0
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       '%s: No huge page memory detected' %
                       (caller_name()))
            return convert_size('0k', 'kb')
        # Calculate reserved hpmem
        reserved = 0
        try:
            if 'reserve_percent' in config['cgroup']['hugetlb']:
                reserve_percent = \
                    config['cgroup']['hugetlb']['reserve_percent']
                reserved += (total * int(reserve_percent)) / 100
            if 'reserve_amount' in config['cgroup']['hugetlb']:
                reserve_amount = config['cgroup']['hugetlb']['reserve_amount']
                reserved += size_as_int(reserve_amount)
        except:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       '%s: Could not determine reserved node hpmem' %
                       (caller_name()))
            raise
        pbs.logmsg(pbs.EVENT_DEBUG4, "reserved hpmem: %d" % reserved)
        # Calculate remaining vmem
        remaining = total - reserved
        if remaining <= 0:
            raise ValueError('Too much reserved hpmem')
        pbs.logmsg(pbs.EVENT_DEBUG4, "remaining hpmem: %d" % remaining)
        amount = convert_size(str(remaining), 'kb')
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Returning: %s" %
                   (caller_name(), amount))
        return amount

    # Create individual vnodes per socket
    def create_vnodes(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        vnode_list = pbs.event().vnode_list
        if self.cfg['vnode_per_numa_node']:
            vnodes = True
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: vnode_per_numa_node is enabled" %
                       (caller_name()))
        else:
            vnodes = False
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "%s: vnode_per_numa_node is disabled" % (caller_name()))
        vnode_name = self.hostname
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: numa nodes: %s" %
                   (caller_name(), self.numa_nodes))
        vnode_list[vnode_name] = pbs.vnode(vnode_name)
        host_resc_avail = vnode_list[self.hostname].resources_available
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: host_resc_avail: %s" %
                   (caller_name(), host_resc_avail))
        vnode_msg = "%s: vnode_list[%s].resources_available['ncpus'] = %d"
        for id in self.numa_nodes:
            if vnodes:
                vnode_name = self.hostname + "[%d]" % id
                vnode_list[vnode_name] = pbs.vnode(vnode_name)
                vnode_resc_avail = vnode_list[vnode_name].resources_available
            for key, val in sorted(self.numa_nodes[id].iteritems()):
                if key is None:
                    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: key is None" %
                               (caller_name()))
                    continue
                if val is None:
                    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: val is None" %
                               (caller_name()))
                    continue
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s = %s" %
                           (caller_name(), key, val))
                if key == 'cpus':
                    cores = len(val)
                    if not self.cfg['use_hyperthreads']:
                        # Do not treat a hyperthread as a core when
                        # use_hyperthreads is false.
                        cores /= self.cpuinfo['hyperthreads_per_core']
                    if vnodes:
                        # set the value on the host to 0
                        host_resc_avail['ncpus'] = 0
                        pbs.logmsg(pbs.EVENT_DEBUG4, vnode_msg %
                                   (caller_name(), self.hostname,
                                    host_resc_avail['ncpus']))
                        # set the vnode value
                        vnode_resc_avail['ncpus'] = cores
                        pbs.logmsg(pbs.EVENT_DEBUG4, vnode_msg %
                                   (caller_name(), vnode_name,
                                    vnode_resc_avail['ncpus']))
                    else:
                        if 'ncpus' not in host_resc_avail:
                            host_resc_avail['ncpus'] = 0
                        if type(host_resc_avail['ncpus']) not in \
                                [int, pbs.pbs_int]:
                            host_resc_avail['ncpus'] = 0
                        # update the cumulative value
                        host_resc_avail['ncpus'] += cores
                        pbs.logmsg(pbs.EVENT_DEBUG4, vnode_msg %
                                   (caller_name(), self.hostname,
                                    host_resc_avail['ncpus']))
                elif key == 'mem' or key == 'MemTotal':
                    mem = self.get_memory_on_node(self.cfg, val)
                    mem = pbs.size(convert_size(mem, 'kb'))
                    if vnodes:
                        # set the value on the vnode
                        vnode_resc_avail['mem'] = mem
                        # set the value on the host to 0
                        host_resc_avail['mem'] = pbs.size('0kb')
                    else:
                        if 'mem' not in host_resc_avail:
                            host_resc_avail['mem'] = pbs.size('0kb')
                        if not isinstance(host_resc_avail['mem'], pbs.size):
                            host_resc_avail['mem'] = pbs.size('0kb')
                        host_resc_avail['mem'] += mem
                elif key == 'HugePages_Total':
                    pass
                elif isinstance(val, list):
                    pass
                elif isinstance(val, dict):
                    pass
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s=%s" %
                               (caller_name(), key, val))
                    if vnodes:
                        vnode_resc_avail[key] = val
                        host_resc_avail[key] = initialize_resource(val)
                    else:
                        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: key = %s (%s)" %
                                   (caller_name(), key, type(key)))
                        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: val = %s (%s)" %
                                   (caller_name(), val, type(val)))
                        if key not in host_resc_avail:
                            host_resc_avail[key] = initialize_resource(val)
                        else:
                            if not host_resc_avail[key]:
                                host_resc_avail[key] = initialize_resource(val)
                        host_resc_avail[key] += val
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: vnode list: %s" %
                   (caller_name(), vnode_list))
        if vnodes:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: vnode_resc_avail: %s" %
                       (caller_name(), vnode_resc_avail))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: host_resc_avail: %s" %
                   (caller_name(), host_resc_avail))
        return True


#
# CLASS CgroupUtils
#
class CgroupUtils:

    def __init__(self, hostname, vnode, cfg=None, subsystems=None,
                 paths=None, vntype=None, assigned_resources=None):
        self.hostname = hostname
        self.vnode = vnode
        # __check_os will raise an exception if cgroups are not present
        self.__check_os()
        # Read in the config file
        if cfg is not None:
            self.cfg = cfg
        else:
            self.cfg = self.__parse_config_file()
        # Collect the cgroup mount points
        if paths is not None:
            self.paths = paths
        else:
            self.paths = self.__get_paths()
        # Raise an error if nothing is mounted
        if not self.paths:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: No cgroups mounted" %
                       (caller_name()))
            raise CgroupProcessingError("No CPUs avaialble in cgroup.")
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
        # Return now if nothing is enabled
        if not self.subsystems:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: No cgroups enabled" %
                       (caller_name()))
            self.assigned_resources = {}
            return
        # location to store information for the different hook events
        self.hook_storage_dir = os.path.join(pbs_home, 'mom_priv',
                                             'hooks', 'hook_data')
        self.host_job_env_dir = os.path.join(pbs_home, 'aux')
        self.host_job_env_filename = os.path.join(self.host_job_env_dir,
                                                  '%s.env')
        # information for offlining nodes
        self.offline_file = os.path.join(pbs_home, 'mom_priv', 'hooks',
                                         ('%s.offline' %
                                          pbs.event().hook_name))
        self.offline_msg = "Hook %s: " % pbs.event().hook_name
        self.offline_msg += "Unable to clean up one or more cgroups"
        # Collect the cgroup resources
        if assigned_resources:
            self.assigned_resources = assigned_resources
        else:
            self.assigned_resources = self.__get_assigned_cgroup_resources()

    def __repr__(self):
        return ("CgroupUtils(%s, %s, %s, %s, %s, %s, %s)" %
                (repr(self.hostname),
                 repr(self.vnode),
                 repr(self.cfg),
                 repr(self.subsystems),
                 repr(self.paths),
                 repr(self.vntype),
                 repr(self.assigned_resources)))

    # Validate the OS type and version
    def __check_os(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Check to see if the platform is linux and the kernel is new enough
        if platform.system() != 'Linux':
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: OS does not support cgroups" %
                       (caller_name()))
            raise CgroupConfigError("OS type not supported")
        rel = map(int,
                  string.split(string.split(platform.release(), '-')[0], '.'))
        pbs.logmsg(pbs.EVENT_DEBUG4,
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
            raise CgroupConfigError("Kernel does not support cgroups")
        return supported

    # Read the config file in json format
    def __parse_config_file(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Turn everything off by default. These settings be modified
        # when the configuration file is read. Keep the keys in sync
        # with the default cgroup configuration files.
        defaults = {}
        defaults['cgroup_prefix'] = 'pbspro'
        defaults['cgroup_lock_file'] = os.path.join(pbs_home, 'mom_priv',
                                                    'cgroups.lock')
        defaults['nvidia-smi'] = os.path.join(os.sep, 'usr', 'bin',
                                              'nvidia-smi')
        defaults['exclude_hosts'] = []
        defaults['exclude_vntypes'] = []
        defaults['run_only_on_hosts'] = []
        defaults['periodic_resc_update'] = False
        defaults['vnode_per_numa_node'] = False
        defaults['online_offlined_nodes'] = False
        defaults['use_hyperthreads'] = False
        defaults['kill_timeout'] = 10
        defaults['placement_type'] = 'load_balanced'
        defaults['cgroup'] = {}
        defaults['cgroup']['cpuacct'] = {}
        defaults['cgroup']['cpuacct']['enabled'] = False
        defaults['cgroup']['cpuacct']['exclude_hosts'] = []
        defaults['cgroup']['cpuacct']['exclude_vntypes'] = []
        defaults['cgroup']['cpuset'] = {}
        defaults['cgroup']['cpuset']['enabled'] = False
        defaults['cgroup']['cpuset']['exclude_hosts'] = []
        defaults['cgroup']['cpuset']['exclude_vntypes'] = []
        defaults['cgroup']['devices'] = {}
        defaults['cgroup']['devices']['enabled'] = False
        defaults['cgroup']['devices']['exclude_hosts'] = []
        defaults['cgroup']['devices']['exclude_vntypes'] = []
        defaults['cgroup']['devices']['allow'] = []
        defaults['cgroup']['hugetlb'] = {}
        defaults['cgroup']['hugetlb']['enabled'] = False
        defaults['cgroup']['hugetlb']['exclude_hosts'] = []
        defaults['cgroup']['hugetlb']['exclude_vntypes'] = []
        defaults['cgroup']['hugetlb']['default'] = '0MB'
        defaults['cgroup']['hugetlb']['reserve_percent'] = '0'
        defaults['cgroup']['hugetlb']['reserve_amount'] = '0MB'
        defaults['cgroup']['memory'] = {}
        defaults['cgroup']['memory']['enabled'] = False
        defaults['cgroup']['memory']['exclude_hosts'] = []
        defaults['cgroup']['memory']['exclude_vntypes'] = []
        defaults['cgroup']['memory']['soft_limit'] = False
        defaults['cgroup']['memory']['default'] = '0MB'
        defaults['cgroup']['memory']['reserve_percent'] = '0'
        defaults['cgroup']['memory']['reserve_amount'] = '0MB'
        defaults['cgroup']['memsw'] = {}
        defaults['cgroup']['memsw']['enabled'] = False
        defaults['cgroup']['memsw']['exclude_hosts'] = []
        defaults['cgroup']['memsw']['exclude_vntypes'] = []
        defaults['cgroup']['memsw']['default'] = '0MB'
        defaults['cgroup']['memsw']['reserve_percent'] = '0'
        defaults['cgroup']['memsw']['reserve_amount'] = '0MB'
        # Identify the config file and read in the data
        config_file = ''
        if 'PBS_HOOK_CONFIG_FILE' in os.environ:
            config_file = os.environ["PBS_HOOK_CONFIG_FILE"]
        if not config_file:
            tmpcfg = os.path.join(pbs_home, 'server_priv', 'hooks',
                                  'pbs_cgroups.CF')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            tmpcfg = os.path.join(pbs_home, 'mom_priv', 'hooks',
                                  'pbs_cgroups.CF')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            tmpcfg = os.path.join(pbs_home, 'server_priv', 'hooks',
                                  'pbs_cgroups.json')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            tmpcfg = os.path.join(pbs_home, 'mom_priv', 'hooks',
                                  'pbs_cgroups.json')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            raise CgroupConfigError("Config file not found")
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Config file is %s" %
                   (caller_name(), config_file))
        try:
            with open(config_file, 'r') as fd:
                config = merge_dict(defaults,
                                    json.load(fd, object_hook=decode_dict))
        except IOError:
            raise CgroupConfigError("I/O error reading config file")
        except:
            raise
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "%s: cgroup hook configuration: %s" %
                   (caller_name(), config))
        return config

    # Determine which subsystems are being requested
    def __target_subsystems(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Check to see if this node is in the approved hosts list
        if self.cfg['run_only_on_hosts']:
            # Approved host list is not empty
            if self.hostname not in self.cfg['run_only_on_hosts']:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s is not in the approved host list: %s" %
                           (self.hostname, self.cfg['run_only_on_hosts']))
                return []
        else:
            # Approved host list is empty. Check to see if self.hostname
            # is in the excluded host list.
            if self.hostname in self.cfg['exclude_hosts']:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s is in the excluded host list: %s" %
                           (self.hostname, self.cfg['exclude_hosts']))
                return []
            # Check to see if the local vnode type is in the excluded
            # vnode type list.
            if self.vntype in self.cfg['exclude_vntypes']:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s is in the excluded vnode type list: %s" %
                           (self.vntype, self.cfg['exclude_vntypes']))
                return []
        subsystems = []
        for key in self.cfg['cgroup']:
            if self.enabled(key):
                subsystems.append(key)
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Enabled subsystems: %s" %
                   (caller_name(), subsystems))
        # It is not an error for all subsystems to be disabled.
        # This host or vnode type may be in the excluded list.
        return subsystems

    # Copy a setting from the parent cgroup
    def __copy_from_parent(self, dest):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        file = os.path.basename(dest)
        dir = os.path.dirname(dest)
        parent = os.path.dirname(dir)
        source = os.path.join(parent, file)
        if not os.path.isfile(source):
            raise CgroupConfigError('Failed to read %s' % (source))
        with open(source, 'r') as fd:
            self.write_value(dest, fd.read().strip())

    # Determine the path for a cgroup directory given the subsystem, mount
    # point, and mount flags
    def __assemble_path(self, subsys, mp, flags):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if 'noprefix' in flags:
            prefix = ''
        else:
            if subsys == 'hugetlb':
                # hugetlb includes size in prefix
                # TODO: make size component configurable
                prefix = subsys + '.2MB.'
            elif subsys == 'memsw':
                prefix = 'memory.' + subsys + '.'
            else:
                prefix = subsys + '.'
        return os.path.join(mp, self.cfg['cgroup_prefix'], prefix)

    # Create a dictionary of the cgroup subsystems and their corresponding
    # directories taking mount options (noprefix) into account
    def __get_paths(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        paths = {}
        # Loop through the mounts and collect the ones for cgroups
        with open(os.path.join(os.sep, "proc", "mounts"), 'r') as fd:
            for line in fd:
                entries = line.split()
                if entries[2] != "cgroup":
                    continue
                subsys = None
                # It is possible to have more than one cgroup mounted in
                # the same place, so check them all for each mount.
                flags = entries[3].split(',')
                if 'cpu' in flags:
                    paths['cpu'] = \
                        self.__assemble_path('cpu', entries[1], flags)
                if 'cpuacct' in flags:
                    paths['cpuacct'] = \
                        self.__assemble_path('cpuacct', entries[1], flags)
                if 'cpuset' in flags:
                    paths['cpuset'] = \
                        self.__assemble_path('cpuset', entries[1], flags)
                if 'devices' in flags:
                    paths['devices'] = \
                        self.__assemble_path('devices', entries[1], flags)
                if 'hugetlb' in flags:
                    paths['hugetlb'] = \
                        self.__assemble_path('hugetlb', entries[1], flags)
                if 'memory' in flags:
                    paths['memory'] = \
                        self.__assemble_path('memory', entries[1], flags)
                    # memory and memsw share a common mount point,
                    # but use a different prefix
                    paths['memsw'] = \
                        self.__assemble_path('memsw', entries[1], flags)
        if not paths:
            raise CgroupConfigError("Cgroup paths not detected")
        return paths

    # Return the path to a cgroup file or directory
    def __cgroup_path(self, subsys, cgfile='', jobid=''):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Note: The tasks file never uses a prefix (e.g. use tasks and not
        # cpuset.tasks).
        # Note: The os.path.join() method is smart enough to ignore
        # empty strings unless they occur as the last parameter.
        if not subsys:
            return None
        if subsys not in self.paths:
            return None
        try:
            dir, prefix = os.path.split(self.paths[subsys])
        except:
            return None
        if not cgfile:
            # Caller wants directory name
            if jobid:
                return os.path.join(dir, jobid, '')
            else:
                return os.path.join(dir, '')
        else:
            # Caller wants file name
            if cgfile == 'tasks':
                return os.path.join(dir, jobid, cgfile)
            else:
                return os.path.join(dir, jobid, (prefix + cgfile))

    # Create the cgroup parent directories that will contain the jobs
    def create_paths(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            # Create the directories that PBS will use to house the jobs
            old_umask = os.umask(0022)
            for subsys in self.subsystems:
                dir = self.__cgroup_path(subsys)
                if not dir:
                    raise CgroupConfigError('No path for subsystem: %s' %
                                            (subsys))
                if not os.path.exists(dir):
                    os.makedirs(dir, 0755)
                    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Created directory %s" %
                               (caller_name(), dir))
                    if subsys == 'memory' or subsys == 'memsw':
                        # Enable 'use_hierarchy' for memory when either memory
                        # or memsw is in use.
                        file = self.__cgroup_path('memory', 'use_hierarchy')
                        if not os.path.isfile(file):
                            raise CgroupConfigError('Failed to configure %s' %
                                                    (file))
                        self.write_value(file, 1)
                    elif subsys == 'cpuset':
                        self.__copy_from_parent(self.__cgroup_path(subsys,
                                                'cpus'))
                        self.__copy_from_parent(self.__cgroup_path(subsys,
                                                'mems'))
        except:
            raise CgroupConfigError("Failed to create directory: %s" %
                                    (self.paths[subsys]))
        finally:
            os.umask(old_umask)

    # Return the vnode type of the local node
    def __get_vnode_type(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # self.vnode is not defined for pbs_attach events so the vnode
        # type gets cached in the mom_priv/vntype file. First, check
        # to see if it is defined.
        resc_vntype = ''
        if self.vnode is not None:
            if 'vntype' in self.vnode.resources_available:
                if self.vnode.resources_available['vntype']:
                    resc_vntype = self.vnode.resources_available['vntype']
        pbs.logmsg(pbs.EVENT_DEBUG4, "resc_vntype: %s" % resc_vntype)
        # Next, read it from the cache file.
        file_vntype = ''
        filename = os.path.join(pbs_home, 'mom_priv', 'vntype')
        try:
            with open(filename, 'r') as fd:
                file_vntype = fd.readline().strip()
        except:
            pass
        pbs.logmsg(pbs.EVENT_DEBUG4, "file_vntype: %s" % file_vntype)
        # If vntype was not set then log a message. It is too expensive
        # to have all moms query the server for large jobs.
        if not resc_vntype and not file_vntype:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "%s: Could not determine vntype" % caller_name())
            return None
        # Return file_vntype if it is set and resc_vntype is not.
        if not resc_vntype and file_vntype:
            pbs.logmsg(pbs.EVENT_DEBUG4, "vntype: %s" % file_vntype)
            return file_vntype
        # Make sure the cache file is up to date.
        if resc_vntype and resc_vntype != file_vntype:
            pbs.logmsg(pbs.EVENT_DEBUG4, "Updating vntype file")
            try:
                with open(filename, 'w') as fd:
                    fd.write(resc_vntype)
            except:
                pass
        pbs.logmsg(pbs.EVENT_DEBUG4, "vntype: %s" % resc_vntype)
        return resc_vntype

    # Return a dictionary of currently assigned cgroup resources per job
    def __get_assigned_cgroup_resources(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        assigned = {}
        for key in self.paths:
            path = os.path.dirname(self.__cgroup_path(key))
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Examining %s" %
                       (caller_name(), path))
            # Do not exclude orphans
            for d in glob.glob(os.path.join(path, '[0-9]*')):
                jobid = os.path.basename(d)
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Job ID is %s" %
                           (caller_name(), jobid))
                if jobid not in assigned:
                    assigned[jobid] = {}
                if key in ('cpu', 'cpuacct', 'memsw'):
                    continue
                if key not in assigned[jobid]:
                    assigned[jobid][key] = {}
                if key == 'cpuset':
                    with open(self.__cgroup_path(key, 'cpus', jobid)) as fd:
                        assigned[jobid][key]['cpus'] = \
                            expand_list(fd.readline())
                    with open(self.__cgroup_path(key, 'mems', jobid)) as fd:
                        assigned[jobid][key]['mems'] = \
                            expand_list(fd.readline())
                elif key == 'memory':
                    with open(self.__cgroup_path(key, 'limit_in_bytes',
                                                 jobid)) as fd:
                        assigned[jobid][key]['limit_in_bytes'] = \
                            int(fd.readline())
                    with open(self.__cgroup_path(key, 'soft_limit_in_bytes',
                                                 jobid)) as fd:
                        assigned[jobid][key]['soft_limit_in_bytes'] = \
                            int(fd.readline())
                    with open(self.__cgroup_path('memsw', 'limit_in_bytes',
                                                 jobid)) as fd:
                        assigned[jobid]['memsw'] = {}
                        assigned[jobid]['memsw']['limit_in_bytes'] = \
                            int(fd.readline())
                elif key == 'hugetlb':
                    with open(self.__cgroup_path(key, 'limit_in_bytes',
                                                 jobid)) as fd:
                        assigned[jobid][key]['limit_in_bytes'] = \
                            int(fd.readline())
                elif key == 'devices':
                    path = self.__cgroup_path(key, 'list', jobid)
                    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Devices path is %s" %
                               (caller_name(), path))
                    with open(path) as fd:
                        assigned[jobid][key]['list'] = []
                        for line in fd:
                            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Appending %s" %
                                       (caller_name(), line))
                            assigned[jobid][key]['list'].append(line)
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Unknown subsystem %s" %
                               (caller_name(), key))
                    raise(CgroupConfigError, "Unknown subsystem: %s" % (key))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Returning %s" %
                   (caller_name(), str(assigned)))
        return assigned

    # Return whether a subsystem is enabled
    def enabled(self, subsystem):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Check whether the subsystem is enabled in the configuration file
        if subsystem not in self.cfg['cgroup']:
            return False
        if 'enabled' not in self.cfg['cgroup'][subsystem]:
            return False
        if not self.cfg['cgroup'][subsystem]['enabled']:
            return False
        # Check whether the cgroup is mounted for this subsystem
        if subsystem not in self.paths:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: cgroup not mounted for %s" %
                       (caller_name(), subsystem))
            return False
        # Check whether this host is excluded
        if self.hostname in self.cfg['cgroup'][subsystem]['exclude_hosts']:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: cgroup excluded for subsystem %s on host %s" %
                       (caller_name(), subsystem, self.hostname))
            return False
        # Check whether the vnode type is excluded
        if self.vntype is not None:
            if self.vntype in self.cfg['cgroup'][subsystem]['exclude_vntypes']:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           ("%s: cgroup excluded for " +
                            "subsystem %s on vnode type %s") %
                           (caller_name(), subsystem, self.vntype))
                return False
        return True

    # Return the default value for a subsystem
    def default(self, subsystem):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if subsystem in self.cfg['cgroup']:
            if 'default' in self.cfg['cgroup'][subsystem]:
                return self.cfg['cgroup'][subsystem]['default']
        return None

    # Check to see if the pid's owner matches the job's owner
    def __is_pid_owned_by_job_owner(self, pid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            proc_uid = os.stat('/proc/%d' % pid).st_uid
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       '/proc/%d uid:%d' % (pid, proc_uid))
            job_owner_uid = pwd.getpwnam(pbs.event().job.euser)[2]
            pbs.logmsg(pbs.EVENT_DEBUG4, "Job uid: %d" % job_owner_uid)
            if proc_uid == job_owner_uid:
                return True
            else:
                pbs.logmsg(pbs.EVENT_DEBUG4,
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
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # make pids a list
        if isinstance(pids, int):
            pids = [pids]
        if pbs.event().type == pbs.EXECJOB_LAUNCH:
            if 1 in pids:
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "%s: Job %s contains defunct process" %
                           (caller_name(), jobid))
                # Use a list comprehension to remove all instances of the
                # number 1
                pids = [x for x in pids if x != 1]
        # check pids to make sure that they are owned by the job owner
        if pbs_version[0] >= 13:
            if pbs.event().type == pbs.EXECJOB_ATTACH:
                pbs.logmsg(pbs.EVENT_DEBUG4, "event type: attach")
                tmp_pids = []
                for p in pids:
                    if self.__is_pid_owned_by_job_owner(p):
                        tmp_pids.append(p)
                    else:
                        pbs.logmsg(pbs.EVENT_DEBUG2,
                                   "%d is not a valid pids to add" % p)
                if not tmp_pids:
                    return False
                else:
                    pids = tmp_pids
        # Determine which subsystems will be used
        for subsys in self.subsystems:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: subsys = %s" %
                       (caller_name(), subsys))
            # memsw and memory use the same tasks file
            if subsys == "memsw" and "memory" in self.subsystems:
                continue
            tasks_file = self.__cgroup_path(subsys, 'tasks', jobid)
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: tasks file = %s" %
                       (caller_name(), tasks_file))
            try:
                for p in pids:
                    self.write_value(tasks_file, p, 'a')
            except IOError, exc:
                raise CgroupLimitError("Failed to add PIDs %s to %s (%s)" %
                                       (str(pids), tasks_file,
                                        errno.errorcode[exc.errno]))
            except:
                raise

    def setup_job_devices_env(self):
        """
        Setup the job environment for the devices assigned to the job for an
        execjob_launch hook
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if 'device_names' in self.assigned_resources:
            names = self.assigned_resources['device_names']
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "devices: %s" % (names))
            offload_devices = []
            cuda_visible_devices = []
            for name in names:
                if name.startswith('mic'):
                    offload_devices.append(name[3:])
                elif name.startswith('nvidia'):
                    cuda_visible_devices.append(name[6:])
            if offload_devices:
                value = '"%s"' % string.join(offload_devices, ",")
                pbs.event().env['OFFLOAD_DEVICES'] = value
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "offload_devices: %s" % offload_devices)
            if cuda_visible_devices:
                value = '"%s"' % string.join(cuda_visible_devices, ",")
                pbs.event().env['CUDA_VISIBLE_DEVICES'] = value
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "cuda_visible_devices: %s" % cuda_visible_devices)
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "Environment: %s" % pbs.event().env)
            return [offload_devices, cuda_visible_devices]
        else:
            return False

    def __setup_subsys_devices(self, jobid, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if 'devices' not in self.subsystems:
            return
        devices_list_file = self.__cgroup_path('devices', 'list', jobid)
        devices_deny_file = self.__cgroup_path('devices', 'deny', jobid)
        devices_allow_file = self.__cgroup_path('devices', 'allow', jobid)
        # Add devices the user is granted access to
        with open(devices_list_file, 'r') as fd:
            devices_allowed = fd.read().splitlines()
        pbs.logmsg(pbs.EVENT_DEBUG4, "Initial devices.list: %s" %
                   devices_allowed)
        # Deny access to mic and gpu devices
        accelerators = []
        devices = node.devices
        for devclass in devices:
            if devclass == 'mic' or devclass == 'gpu':
                for instance in devices[devclass]:
                    dev = devices[devclass][instance]
                    accelerators.append("%d:%d" % (dev['major'], dev['minor']))
        # For CentOS 7 we need to remove a *:* rwm from devices.list
        # before we can add anything to devices.allow. Otherwise our
        # changes are ignored. Check to see if a *:* rwm is in devices.list
        # If so remove it
        value = 'a *:* rwm'
        if value in devices_allowed:
            self.write_value(devices_deny_file, value)
        # Verify that the following devices are not in devices.list
        pbs.logmsg(pbs.EVENT_DEBUG4, "Removing access to the following: %s" %
                   accelerators)
        for entry in accelerators:
            value = "c %s rwm" % entry
            self.write_value(devices_deny_file, value)
        # Add devices back to the list
        devices_allow = self.cfg['cgroup']['devices']['allow']
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Allowing access to the following: %s" %
                   devices_allow)
        for item in devices_allow:
            if isinstance(item, str):
                pbs.logmsg(pbs.EVENT_DEBUG4, "string item: %s" % item)
                self.write_value(devices_allow_file, item)
                pbs.logmsg(pbs.EVENT_DEBUG4, "write_value: %s" % value)
                continue
            if not isinstance(item, list):
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "%s: Entry is not a string or list: %s" %
                           (caller_name(), item))
                continue
            pbs.logmsg(pbs.EVENT_DEBUG4, "Device allow: %s" % item)
            stat_filename = os.path.join(os.sep, 'dev', item[0])
            pbs.logmsg(pbs.EVENT_DEBUG4, "Stat file: %s" % stat_filename)
            try:
                s = os.stat(stat_filename)
            except OSError:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s: Entry not added to devices.allow: %s" %
                           (caller_name(), item))
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: File not found: %s" %
                           (caller_name(), stat_filename))
                continue
            except:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "Unexpected error: %s" %
                           sys.exc_info()[0])
                continue
            device_type = None
            if stat.S_ISBLK(s.st_mode):
                device_type = "b"
            elif stat.S_ISCHR(s.st_mode):
                device_type = "c"
            if not device_type:
                pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Unknown device type: %s" %
                           (caller_name(), stat_filename))
                continue
            if len(item) == 3 and isinstance(item[2], str):
                value = "%s %s:%s %s" % (device_type,
                                         os.major(s.st_rdev),
                                         item[2], item[1])
            else:
                value = "%s %s:%s %s" % (device_type,
                                         os.major(s.st_rdev),
                                         os.minor(s.st_rdev),
                                         item[1])
            self.write_value(devices_allow_file, value)
            pbs.logmsg(pbs.EVENT_DEBUG4, "write_value: %s" % value)
        with open(devices_list_file, 'r') as fd:
            devices_allowed = fd.read().splitlines()
        pbs.logmsg(pbs.EVENT_DEBUG4, "Updated devices.list: %s" %
                   devices_allowed)

    # Select devices to assign to the job
    def __assign_devices(self, device_type, device_list, device_count, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        devices = device_list[:device_count]
        device_ids = []
        device_names = []
        for device in devices:
            device_info = node.devices[device_type][device]
            if len(device_ids) == 0:
                if device.find("mic") != -1:
                    # Requires the ctrl (0) and the scif (1) to be added
                    device_ids.append("%s %d:0 rwm" %
                                      (device_info['type'],
                                       device_info['major']))
                    device_ids.append("%s %d:1 rwm" %
                                      (device_info['type'],
                                       device_info['major']))
                elif device.find("nvidia") != -1:
                    # Requires the ctrl (0) and the scif (1) to be added
                    device_ids.append("%s %d:255 rwm" %
                                      (device_info['type'],
                                       device_info['major']))
            device_ids.append("%s %d:%d rwm" %
                              (device_info['type'],
                               device_info['major'],
                               device_info['minor']))
            device_names.append(device)
        return device_names, device_ids

    # Find the device name
    def get_device_name(self, node, available, socket, major, minor):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Get device name: major: %s, minor: %s" % (major, minor))
        avail_device = None
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Possible devices: %s" % (available[socket]['devices']))
        for avail_device in available[socket]['devices']:
            avail_major = None
            avail_minor = None
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "Checking device: %s" % (avail_device))
            if avail_device.find('mic') != -1:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Check mic device: %s" % (avail_device))
                avail_major = node.devices['mic'][avail_device]['major']
                avail_minor = node.devices['mic'][avail_device]['minor']
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Device major: %s, minor: %s" % (major, minor))
            elif avail_device.find('nvidia') != -1:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Check gpu device: %s" % (avail_device))
                avail_major = node.devices['gpu'][avail_device]['major']
                avail_minor = node.devices['gpu'][avail_device]['minor']
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Device major: %s, minor: %s" % (major, minor))
            if int(avail_major) == int(major) and \
                    int(avail_minor) == int(minor):
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Device match: name: %s, major: %s, minor: %s" %
                           (avail_device, major, minor))
                return avail_device
        pbs.logmsg(pbs.EVENT_DEBUG4, "No match found")
        return None

    # Take two dictionaries containing lists and combine them together
    def __append_resources(self, a, b):
        c = {}
        for d in [a, b]:
            for key in d:
                val = d[key]
                vtype = type(val)
                if key not in c:
                    if vtype is int:
                        c[key] = 0
                    elif vtype is float:
                        c[key] = 0.0
                    elif vtype is str:
                        c[key] = ''
                    elif vtype is list:
                        c[key] = []
                    elif vtype is dict:
                        c[key] = {}
                    elif vtype is tuple:
                        c[key] = ()
                    else:
                        raise ValueError('Unrecognized resource type.')
                c[key] += val
        return c

    # Determine whether a job fits within resources
    def __assign_resources(self, requested, available, socketlist, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        assigned = {}
        if 'ncpus' in requested:
            assigned['cpuset.cpus'] = []
            assigned['cpuset.mems'] = []
            req = int(requested['ncpus'])
            avail = len(available['cpus'])
            if not self.cfg['use_hyperthreads']:
                if node.cpuinfo['hyperthreads_per_core'] > 1:
                    avail /= node.cpuinfo['hyperthreads_per_core']
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "ncpus: requested: %d, available: %d" %
                       (req, avail))
            if req <= avail:
                pbs.logmsg(pbs.EVENT_DEBUG4, "Sufficient ncpus")
                if not self.cfg['use_hyperthreads']:
                    for val in available['cpus'][:req]:
                        assigned['cpuset.cpus'].append(val)
                else:
                    cores = available['cpus']
                    for ht in node.cpuinfo['hyperthreads']:
                        if ht in cores:
                            cores.remove(ht)
                    req /= node.cpuinfo['hyperthreads_per_core']
                    for val in cores[:req]:
                        assigned['cpuset.cpus'].append(val)
                        threads = node.cpuinfo['cpu'][val]['threads']
                        assigned['cpuset.cpus'] += threads
                # Set cpuset.mems to the socketlist for now even though
                # there may not be sufficient memory. Memory gets
                # checked later in this function.
                assigned['cpuset.mems'] = socketlist
            else:
                pbs.logmsg(pbs.EVENT_DEBUG4, "Insufficient ncpus: %s/%s" %
                           (req, available['cpus']))
                return {}
        if 'nmics' in requested and int(requested['nmics']) > 0:
            assigned['device_names'] = []
            assigned['devices'] = []
            regex = re.compile(".*(mic).*")
            nmics = int(requested['nmics'])
            # Use a list comprehension to construct the mics list
            mics = [m.group(0)
                    for l in available['devices']
                    for m in [regex.search(l)] if m]
            if nmics > len(mics):
                pbs.logmsg(pbs.EVENT_DEBUG4, "Insufficient nmics: %s/%s" %
                           (nmics, mics))
                return {}
            names, devices = self.__assign_devices('mic', mics[:nmics],
                                                   nmics, node)
            for val in names:
                assigned['device_names'].append(val)
            for val in devices:
                assigned['devices'].append(val)
        if 'ngpus' in requested and int(requested['ngpus']) > 0:
            if 'device_names' not in assigned:
                assigned['device_names'] = []
                assigned['devices'] = []
            regex = re.compile(".*(nvidia).*")
            ngpus = int(requested['ngpus'])
            # Use a list comprehension to construct the gpus list
            gpus = [m.group(0)
                    for l in available['devices']
                    for m in [regex.search(l)] if m]
            if ngpus > len(gpus):
                pbs.logmsg(pbs.EVENT_DEBUG4, "Insufficient ngpus: %s/%s" %
                           (ngpus, gpus))
                return {}
            names, devices = self.__assign_devices('gpu', gpus[:tmp_ngpus],
                                                   ngpus, node)
            for val in names:
                assigned['device_names'].append(val)
            for val in devices:
                assigned['devices'].append(val)
        if 'mem' in requested:
            req_mem = size_as_int(requested['mem'])
            avail_mem = available['memory']
            if req_mem > avail_mem:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Insufficient memory on socket(s) " +
                           "%s: requested:%s, assigned:%s" %
                           (socketlist, req_mem, available['memory']))
                return {}
            if mem not in assigned:
                assigned['mem'] = 0
            assigned['mem'] += req_mem
        return assigned

    # Assign resources to the job. There are two scenarios that need to
    # be handled:
    # 1. If vnodes are present in the requested resources, then the
    #    scheduler has already decided where the job is to run. Check
    #    the available resources to ensure an orphaned cgroup is not
    #    consuming them.
    # 2. If no vnodes are present in the requested resources, try to
    #    span the fewest number of sockets when creating the assignment.
    def assign_job(self, requested, available, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Requested: %s, Available: %s, Numa Nodes: %s" %
                   (requested, available, node.numa_nodes))
        pbs.logmsg(pbs.EVENT_DEBUG4, "Devices: %s" % (node.devices))
        # Create a list of vnode/socket pairs
        if 'vnodes' in requested:
            regex = re.compile("(.*)\[(\d+)\].*")
            pairlist = []
            for vnode in requested['vnodes']:
                pairlist.append([regex.search(vnode).group(1),
                                 int(regex.search(vnode).group(2))])
        else:
            sockets = available.keys()
            # If placement type is load_balanced, reorder the sockets
            if self.cfg['placement_type'] == 'load_balanced':
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Requested load_balanced placement")
                # Look at assigned_resources and determine which socket
                # to start with
                jobcount = {}
                for s in sockets:
                    jobcount[s] = 0
                for job in self.assigned_resources:
                    jobresc = self.assigned_resources[job]
                    if 'cpuset.mems' in jobresc:
                        for socket in jobresc['cpuset.mems']:
                            jobcount[socket] += 1
                sorted_jobcounts = sorted(jobcount.items(),
                                          key=operator.itemgetter(1))
                reordered = []
                for s in sorted_jobcounts:
                    reordered.append(s[0])
                sockets = reordered
            pairlist = []
            for s in sockets:
                pairlist.append([None, int(s)])
        # Loop through the sockets or vnodes and assign resources
        assigned = {}
        for p in pairlist:
            vnode = p[0]
            socket = p[1]
            if vnode:
                myname = 'vnode %s[%d]' % (vnode, socket)
                req = requested['vnodes']["%s[%d]" % (vnode, socket)]
            else:
                myname = 'socket %d' % socket
                req = requested
            pbs.logmsg(pbs.EVENT_DEBUG4, 'Current target is %s' % myname)
            new = self.__assign_resources(req, available[socket],
                                          [socket], node)
            if new:
                new['cpuset.mems'].append(socket)
                pbs.logmsg(pbs.EVENT_DEBUG4, "Resources assigned to %s" %
                           myname)
                if vnode:
                    assigned = self.__append_resources(assigned, new)
                else:
                    # Requested resources fit on this socket
                    return new
            else:
                pbs.logmsg(pbs.EVENT_DEBUG4, "Resources not assigned to %s" %
                           myname)
                # This is fatal in the case of vnodes
                if vnode:
                    return {}
        if vnode:
            assigned['cpuset.cpus'].sort()
            assigned['cpuset.mems'].sort()
            if 'devices' in assigned:
                assigned['devices'].sort()
                pbs.logmsg(pbs.EVENT_DEBUG4, "device ids: %s" %
                           (assigned['devices']))
                assigned['device_names'].sort()
                pbs.logmsg(pbs.EVENT_DEBUG4, "device names: %s" %
                           (assigned['device_names']))
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Assigned Resources: %s" % (assigned))
            return assigned
        # Not using vnodes so try spanning sockets
        pbs.logmsg(pbs.EVENT_DEBUG4, "Attempting to span sockets")
        total = {}
        socketlist = []
        for p in pairlist:
            socket = p[1]
            socketlist.append(socket)
            total = self.__append_resources(total, available[socket])
        pbs.logmsg(pbs.EVENT_DEBUG4, "Combined available resources: %s" %
                   (total))
        return self.__assign_resources(requested, total, socketlist, node)

    # Determine which resources are available
    def available_node_resources(self, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        available = copy.deepcopy(node.numa_nodes)
        pbs.logmsg(pbs.EVENT_DEBUG4, "Available Keys: %s" % (available[0]))
        pbs.logmsg(pbs.EVENT_DEBUG4, "Available: %s" % (available))
        for socket in available:
            if 'MemTotal' in available[socket]:
                # Find the memory on the socket in bytes.
                # Remove the 'b' to simplfy the math
                available[socket]['memory'] = size_as_int(
                    available[socket]['MemTotal'])
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Available Pre device add: %s" % (available))
        pbs.logmsg(pbs.EVENT_DEBUG4, "Node Devices: %s" % (node.devices))
        for device in node.devices:
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "%s: Device Names: %s" %
                       (caller_name(), device))
            if device == 'mic' or device == 'gpu':
                pbs.logmsg(pbs.EVENT_DEBUG4, "Devices: %s" %
                           node.devices[device])
                for device_name in node.devices[device]:
                    device_socket = \
                        node.devices[device][device_name]['numa_node']
                    if 'devices' not in available[device_socket]:
                        available[device_socket]['devices'] = []
                    pbs.logmsg(pbs.EVENT_DEBUG4,
                               "Device: %s, Socket: %s" %
                               (device, device_socket))
                    available[device_socket]['devices'].append(device_name)
        pbs.logmsg(pbs.EVENT_DEBUG4, "Available: %s" % (available))
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Assigned: %s" % (self.assigned_resources))
        # Remove all of the resources that are assigned to other jobs
        for job in self.assigned_resources:
            # Support suspended jobs on nodes
            if not job_to_be_ignored(job):
                cpus = []
                sockets = []
                devices = []
                memory = 0
                jra = self.assigned_resources[job]
                if 'cpuset' in jra:
                    if 'cpus' in jra['cpuset']:
                        cpus = jra['cpuset']['cpus']
                    if 'mems' in jra['cpuset']:
                        sockets = jra['cpuset']['mems']
                if 'devices' in jra:
                    if 'list' in jra['devices']:
                        devices = jra['devices']['list']
                if 'memory' in jra:
                    if 'limit_in_bytes' in jra['memory']:
                        memory = size_as_int(jra['memory']['limit_in_bytes'])
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "cpus: %s, sockets: %s, memory limit: %s" %
                           (cpus, sockets, memory))
                pbs.logmsg(pbs.EVENT_DEBUG4, "devices: %s" % devices)
                # Loop through the sockets and remove cpus that are
                # assigned to other cgroups
                for socket in sockets:
                    for cpu in cpus:
                        try:
                            available[socket]['cpus'].remove(cpu)
                        except ValueError:
                            pass
                        except:
                            pbs.logmsg(pbs.EVENT_DEBUG4,
                                       "Error removing %d from %s" %
                                       (cpu, available[socket]['cpus']))
                if len(sockets) == 1:
                    avail_mem = available[sockets[0]]['memory']
                    pbs.logmsg(pbs.EVENT_DEBUG4,
                               "Sockets: %s\tAvailable: %s" %
                               (sockets, available))
                    pbs.logmsg(pbs.EVENT_DEBUG4,
                               "Decrementing memory: %d by %d" %
                               (size_as_int(avail_mem), memory))
                    if memory <= available[sockets[0]]['memory']:
                        available[sockets[0]]['memory'] -= memory
                # Loop throught the available sockets
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Assigned device to %s: %s" % (job, devices))
                for socket in available:
                    for device in devices:
                        try:
                            # loop through know devices and see if they match
                            if len(available[socket]['devices']) != 0:
                                pbs.logmsg(pbs.EVENT_DEBUG4,
                                           "Check device: %s" % (device))
                                pbs.logmsg(pbs.EVENT_DEBUG4,
                                           "Available device: %s" %
                                           (available[socket]['devices']))
                                major, minor = device.split()[1].split(':')
                                avail_device = self.get_device_name(
                                                   node, available, socket,
                                                   major, minor)
                                pbs.logmsg(pbs.EVENT_DEBUG4,
                                           "Returned device: %s" %
                                           (avail_device))
                                if avail_device is not None:
                                    pbs.logmsg(pbs.EVENT_DEBUG4,
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
                            pbs.logmsg(pbs.EVENT_DEBUG4,
                                       "Unexpected error: %s" %
                                       sys.exc_info()[0])
                            pbs.logmsg(pbs.EVENT_DEBUG4,
                                       "Error removing %s from %s" %
                                       (device, available[socket]['devices']))
            else:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Job %s res not removed from host " % job +
                           "available res: suspended job")
        pbs.logmsg(pbs.EVENT_DEBUG2, "Available resources: %s" % (available))
        return available

    # Set a cgroup limit on a node or a job
    def set_limit(self, resource, value, jobid=''):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if jobid:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: %s = %s for job %s" %
                       (caller_name(), resource, value, jobid))
        else:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: %s = %s for node" %
                       (caller_name(), resource, value))
        if resource == 'mem':
            if 'memory' in self.subsystems:
                path = self.__cgroup_path('memory', 'limit_in_bytes', jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'softmem':
            if 'memory' in self.subsystems:
                path = self.__cgroup_path('memory', 'soft_limit_in_bytes',
                                          jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'vmem':
            if 'memsw' in self.subsystems:
                if 'memory' not in self.subsystems:
                    path = self.__cgroup_path('memory', 'limit_in_bytes',
                                              jobid)
                    self.write_value(path, size_as_int(value))
                path = self.__cgroup_path('memsw', 'limit_in_bytes', jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'hpmem':
            if 'hugetlb' in self.subsystems:
                path = self.__cgroup_path('hugetlb', 'limit_in_bytes', jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'ncpus':
            if 'cpuset' in self.subsystems:
                path = self.__cgroup_path('cpuset', 'cpus', jobid)
                cpus = self.select_cpus(path, value)
                if not cpus:
                    raise CgroupLimitError("Failed to configure cpuset.")
                cpus = string.join(map(str, cpus), ',')
                self.write_value(path, cpus)
                if jobid:
                    path = self.__cgroup_path('cpuset', 'mems', jobid)
                    self.__copy_from_parent(path)
        elif resource == 'cpuset.cpus':
            if 'cpuset' in self.subsystems:
                path = self.__cgroup_path('cpuset', 'cpus', jobid)
                cpus = value
                if not cpus:
                    raise CgroupLimitError("Failed to configure cpuset cpus.")
                cpus = string.join(map(str, cpus), ',')
                self.write_value(path, cpus)
        elif resource == 'cpuset.mems':
            if 'cpuset' in self.subsystems:
                path = self.__cgroup_path('cpuset', 'mems', jobid)
                mems = value
                if not mems:
                    raise CgroupLimitError("Failed to configure cpuset mems.")
                mems = string.join(map(str, mems), ',')
                self.write_value(path, mems)
        elif resource == 'devices':
            if 'devices' in self.subsystems:
                path = self.__cgroup_path('devices', 'allow', jobid)
                devices = value
                if not devices:
                    raise CgroupLimitError("Failed to configure devices.")
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "Setting devices: %s for %s" % (devices, jobid))
                for d in devices:
                    self.write_value(path, d)
                path = self.__cgroup_path('devices', 'list', jobid)
                with open(path, 'r') as fd:
                    output = fd.readlines()
                pbs.logmsg(pbs.EVENT_DEBUG4, "devices.list: %s" % output)
        else:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Resource %s not handled" %
                       (caller_name(), resource))

    # Update resource usage for a job
    def update_job_usage(self, jobid, resc_used):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: resc_used = %s" %
                   (caller_name(), str(resc_used)))
        # Sort the subsystems so that we consistently look at the subsystems
        # in the same order every time
        self.subsystems.sort()
        for subsys in self.subsystems:
            if subsys == "memory":
                max_mem = self.__get_max_mem_usage(jobid)
                if max_mem is None:
                    pbs.logjobmsg(jobid, "%s: No max mem data" %
                                  (caller_name()))
                else:
                    resc_used['mem'] = pbs.size(convert_size(max_mem, 'kb'))
                    pbs.logjobmsg(jobid,
                                  "%s: Memory usage: mem=%s" %
                                  (caller_name(), resc_used['mem']))
                mem_failcnt = self.__get_mem_failcnt(jobid)
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
                max_vmem = self.__get_max_memsw_usage(jobid)
                if max_vmem is None:
                    pbs.logjobmsg(jobid, "%s: No max vmem data" %
                                  (caller_name()))
                else:
                    resc_used['vmem'] = pbs.size(convert_size(max_vmem, 'kb'))
                    pbs.logjobmsg(jobid,
                                  "%s: Memory usage: vmem=%s" %
                                  (caller_name(), resc_used['vmem']))
                vmem_failcnt = self.__get_memsw_failcnt(jobid)
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
                max_hpmem = self.__get_max_hugetlb_usage(jobid)
                if max_hpmem is None:
                    pbs.logjobmsg(jobid, "%s: No max hpmem data" %
                                  (caller_name()))
                    return
                hpmem_failcnt = self.__get_hugetlb_failcnt(jobid)
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
                if 'walltime' not in resc_used:
                    walltime = 0
                else:
                    if resc_used['walltime']:
                        walltime = int(resc_used['walltime'])
                    else:
                        walltime = 0
                if 'cput' not in resc_used:
                    cput = 0
                else:
                    if resc_used['cput']:
                        cput = int(resc_used['cput'])
                    else:
                        cput = 0
                # Calculate cpupercent based on the reported values
                if walltime > 0:
                    cpupercent = 100 * cput / walltime
                else:
                    cpupercent = 0
                resc_used['cpupercent'] = pbs.pbs_int(cpupercent)
                pbs.logjobmsg(jobid, "%s: CPU percent: %d" %
                              (caller_name(), cpupercent))
                # Now update cput
                cput = self.__get_cpu_usage(jobid)
                if cput is None:
                    pbs.logjobmsg(jobid, "%s: No CPU usage data" %
                                  (caller_name()))
                    return
                cput = convert_time(str(cput) + "ns")
                resc_used['cput'] = pbs.duration(cput)
                pbs.logjobmsg(jobid, "%s: CPU usage: %.3lf secs" %
                              (caller_name(), cput))

    # Creates the cgroup if it doesn't exists
    def create_job(self, jobid, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Iterate over the subsystems required
        for subsys in self.subsystems:
            # Create a directory for the job
            try:
                old_umask = os.umask(0022)
                path = self.__cgroup_path(subsys, '', jobid)
                if not os.path.exists(path):
                    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Creating directory %s" %
                               (caller_name(), path))
                    os.makedirs(path, 0755)
                if subsys == 'devices':
                    self.__setup_subsys_devices(jobid, node)
            except OSError, exc:
                raise CgroupConfigError("Failed to create directory: %s (%s)" %
                                        (path, errno.errorcode[exc.errno]))
            except:
                raise
            finally:
                os.umask(old_umask)

    # Determine the cgroup limits and configure the cgroups
    def configure_job(self, jobid, hostresc, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        mem_enabled = 'memory' in self.subsystems
        vmem_enabled = 'memsw' in self.subsystems
        if mem_enabled or vmem_enabled:
            # Initialize mem variables
            mem_avail = node.get_memory_on_node(self.cfg)
            pbs.logmsg(pbs.EVENT_DEBUG2, "mem_avail %s" % mem_avail)
            mem_requested = None
            if 'mem' in hostresc:
                mem_requested = convert_size(hostresc['mem'], 'kb')
            mem_default = None
            if mem_enabled:
                mem_default = self.default('memory')
            # Initialize vmem variables
            vmem_avail = node.get_vmem_on_node(self.cfg)
            pbs.logmsg(pbs.EVENT_DEBUG2, "vmem_avail %s" % vmem_avail)
            vmem_requested = None
            if 'vmem' in hostresc:
                vmem_requested = convert_size(hostresc['vmem'], 'kb')
            vmem_default = None
            if vmem_enabled:
                vmem_default = self.default('memsw')
            # Initialize softmem variables
            if 'soft_limit' in self.cfg['cgroup']['memory']:
                softmem_enabled = self.cfg['cgroup']['memory']['soft_limit']
            else:
                softmem_enabled = False
            # Sanity check
            if size_as_int(mem_avail) > size_as_int(vmem_avail):
                pbs.logmsg(pbs.EVENT_SYSTEM,
                           "%s: WARNING: mem_avail > vmem_avail" %
                           caller_name())
                pbs.logmsg(pbs.EVENT_SYSTEM,
                           "%s: Check reserve_amount and reserve_percent" %
                           caller_name())
                # Increase vmem_avail to match mem_avail
                vmem_avail = mem_avail
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
                    if size_as_int(vmem_avail) <= size_as_int(mem_avail):
                        # No swap available
                        raise CgroupLimitError(
                            ('Job might utilize swap ' +
                             'and no swap space available'))
            # Assign mem and vmem
            if mem_enabled:
                if mem_requested is None:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               ("%s: mem not requested, " +
                                "assigning %s to cgroup") %
                               (caller_name(), mem_limit))
                    hostresc['mem'] = pbs.size(mem_limit)
                if softmem_enabled:
                    hostresc['softmem'] = pbs.size(softmem_limit)
            if vmem_enabled:
                if vmem_requested is None:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
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
            if 'hpmem' in hostresc:
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
            if 'ncpus' in hostresc:
                cpu_limit = hostresc['ncpus']
            if cpu_limit < 1:
                cpu_limit = 1
            hostresc['ncpus'] = pbs.pbs_int(cpu_limit)
        # Find the available resources and assign the right ones to the job
        assigned = {}
        # Make two attempts since self.cleanup_orphans may actually fix the
        # problem we see in a first attempt
        for attempt in range(2):
            avail_resc = self.available_node_resources(node)
            assigned = self.assign_job(hostresc, avail_resc, node)
            if not assigned:
                # No resources were assigned to the job.
                # Most likely cause was that a cgroup has
                # not been cleaned up yet
                pbs.logmsg(pbs.EVENT_DEBUG2, "Failed to assign job resources")
                pbs.logmsg(pbs.EVENT_DEBUG2, "Resyncing local job data")
                # Collect the jobs on the node (try reading mom_priv/jobs)
                jobs_list = []
                try:
                    jobs_list = node.gather_jobs_on_node()
                except:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               "Failed to resyncing local job data")
                # Job list should contain the new jobid. Do not attempt to
                # cleanup orphaned cgroups with an incomplete job list.
                # There could be other active jobs missing from the list.
                if jobs_list and jobid not in jobs_list:
                    pbs.logmsg(pbs.EVENT_DEBUG2, "Job not found: %s" % jobid)
                else:
                    self.cleanup_orphans(jobs_list)
                # Pause after the first attempt
                if attempt < 1:
                    sleep(0.5)
        if not assigned:
            # Log a message and rerun the job
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       'Requeuing job %s' % jobid)
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       'Run count for job %s: %d' %
                       (jobid, pbs.event().job.run_count))
            pbs.event().job.rerun()
            pbs.event().reject('Failed to assign resources')
        # Print out the assigned resources
        pbs.logmsg(pbs.EVENT_DEBUG2,
                   "Assigned resources: %s" % (assigned))
        self.assigned_resources = assigned
        if cpuset_enabled:
            # Remove the ncpus key if it exists. Ignore any KeyError.
            if 'ncpus' in hostresc:
                del hostresc['ncpus']
            for key in ['cpuset.cpus', 'cpuset.mems']:
                if key in assigned:
                    hostresc[key] = assigned[key]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               "Key: %s not found in assigned" % key)
        # Initialize devices variables
        key = 'devices'
        if key in self.subsystems:
            if key in assigned:
                hostresc[key] = assigned[key]
            else:
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "Key: %s not found in assigned" % key)
        # Apply the resource limits to the cgroups
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Setting cgroup limits for: %s" %
                   (caller_name(), hostresc))
        # The vmem limit must be set after the mem limit, so sort the keys
        for resc in sorted(hostresc):
            self.set_limit(resc, hostresc[resc], jobid)

    # Kill any processes contained within a tasks file
    def __kill_tasks(self, tasks_file, timeout=0):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        end = time.time() + timeout
        while True:
            count = 0
            with open(tasks_file, 'r') as tasks_fd:
                for line in tasks_fd:
                    count += 1
                    os.kill(int(line.strip()), signal.SIGKILL)
            if count == 0 or time.time() >= end:
                break
            else:
                time.sleep(0.1)
        if count == 0:
            return 0
        count = 0
        with open(tasks_file, 'r') as tasks_fd:
            for line in tasks_fd:
                count += 1
                pid = line.strip()
                filename = os.path.join(os.sep, 'proc', pid, 'status')
                statlist = []
                try:
                    with open(filename, 'r') as status_fd:
                        for line2 in status_fd:
                            if line2.find('Name:') != -1:
                                statlist.append(line2.strip())
                            if line2.find('State:') != -1:
                                statlist.append(line2.strip())
                            if line2.find('Uid:') != -1:
                                statlist.append(line2.strip())
                except:
                    pass
                pbs.logmsg(pbs.EVENT_DEBUG2, "%s: PID %s survived: %s" %
                           (caller_name(), pid, statlist))
        return count

    # Perform the actual removal of the cgroup directory.
    # Make only one attempt at killing tasks in cgroup,
    # since this method could be called many times (for N
    # directories times M jobs).
    def __remove_cgroup(self, path, jobid, timeout=0, do_offline=True):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if not os.path.isdir(path):
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: No such directory: %s" %
                       (caller_name(), path))
            return False
        tasks_file = os.path.join(path, 'tasks')
        if not os.path.isfile(tasks_file):
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: No such file: %s" %
                       (caller_name(), path))
            return False
        try:
            remaining = self.__kill_tasks(tasks_file, timeout)
        except:
            remaining = 0
        if remaining == 0:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Removing directory %s" %
                       (caller_name(), path))
            for attempt in range(2):
                try:
                    with dotimeout(2, 'Timed out removing cgroup %s' % (path)):
                        os.rmdir(path)
                except TimeoutError, exc:
                    pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s" %
                               (caller_name(), exc))
                except OSError, exc:
                    pbs.logmsg(pbs.EVENT_SYSTEM,
                               "OS error removing cgroup path: %s (%s)" %
                               (path, errno.errorcode[exc.errno]))
                except:
                    pbs.logmsg(pbs.EVENT_SYSTEM,
                               "Failed to remove cgroup path: %s" % (path))
                    raise
                if not os.path.isdir(path):
                    break
                time.sleep(0.5)
            if not os.path.isdir(path):
                return True
        # Cgroup removal has failed
        pbs.logmsg(pbs.EVENT_SYSTEM, "cgroup still has %d tasks: %s" %
                   (remaining, path))
        if not do_offline:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Offline not requested" %
                       (caller_name()))
            return False
        # Rerun the job and log the message
        pbs.logmsg(pbs.EVENT_DEBUG, '%s: Failed to cleanup cgroup for %s' %
                   (caller_name(), jobid))
        pbs.logmsg(pbs.EVENT_DEBUG2, '%s: Taking node offline' %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG2, '%s: Job %s will be requeued' %
                   (caller_name(), jobid))
        # Check to see if the offline file is already present
        if os.path.isfile(self.offline_file):
            msg = "Cgroup(s) not cleaning up but the node already "
            msg += "has the offline file."
            pbs.logmsg(pbs.EVENT_DEBUG2, msg)
        else:
            # Check to see that the node is not already offline.
            try:
                tmp_state = pbs.server().vnode(self.hostname).state
            except:
                msg = "Unable to contact server for node state"
                pbs.logmsg(pbs.EVENT_DEBUG, msg)
                tmp_state = None
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "Current Node State: %d" % tmp_state)
            if tmp_state == pbs.ND_OFFLINE:
                msg = "Cgroup(s) not cleaning up but the node is "
                msg += "already offline."
                pbs.logmsg(pbs.EVENT_DEBUG2, msg)
                return False
            if tmp_state is not None:
                # Offline the node(s)
                pbs.logmsg(pbs.EVENT_DEBUG2, self.offline_msg)
                msg = "Offlining node since cgroup(s) are not "
                msg += "cleaning up"
                pbs.logmsg(pbs.EVENT_DEBUG2, msg)
                vnode = pbs.event().vnode_list[self.hostname]
                vnode.state = pbs.ND_OFFLINE
                # Write a file locally to reduce server traffic
                # when it comes time to online the node
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "Offline file: %s" % self.offline_file)
                try:
                    with open(self.offline_file, 'w') as fd:
                        fd.write('Offlined %s\n' % time.strftime("%c"))
                except:
                    pass
                vnode.comment = self.offline_msg
                pbs.logmsg(pbs.EVENT_DEBUG2, self.offline_msg)
                if os.path.isfile(self.offline_file):
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               'Offlined: %s' % time.strftime("%c"))
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               'File not found: %s' % self.offline_file)
        return False

    # Removes cgroup directories that are not associated with a local job
    def cleanup_orphans(self, local_jobs):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        remaining = 0
        for key in self.paths:
            path = os.path.dirname(self.__cgroup_path(key))
            for d in glob.glob(os.path.join(path, '[0-9]*')):
                jobid = os.path.basename(d)
                if jobid not in local_jobs:
                    if not jobid.endswith('-orphan'):
                        try:
                            os.rename(d, d + '-orphan')
                        except:
                            pass
            for d in glob.glob(os.path.join(path, '[0-9]*-orphan')):
                jobid = os.path.basename(d)
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "%s: Removing orphaned cgroup: %s" %
                           (caller_name(), d))
                if not self.__remove_cgroup(d, jobid):
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "%s: Removing orphaned cgroup %s failed " %
                               (caller_name(), d))
                    remaining += 1
        return remaining

    # Removes the cgroup directories for a job
    def delete(self, jobid, do_offline=True):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Make multiple attempts to kill tasks in the cgroup. Keep
        # trying for kill_timeout seconds.
        success = True
        for subsys in self.subsystems:
            path = self.__cgroup_path(subsys, '', jobid)
            if not os.path.isdir(path):
                continue
            if success:
                success = self.__remove_cgroup(path, jobid,
                                               self.cfg['kill_timeout'],
                                               do_offline)
            else:
                # Do not perform offline because of previous failure
                self.__remove_cgroup(path, jobid)
        if not success:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       '%s: Unable to delete cgroup for job %s' %
                       (caller_name(), jobid))

    # Write a value to a limit file
    def write_value(self, filename, value, mode='w'):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: writing %s to %s" %
                   (caller_name(), value, filename))
        try:
            with open(filename, mode) as fd:
                fd.write(str(value) + '\n')
        except IOError, exc:
            if exc.errno == errno.ENOENT:
                pbs.logmsg(pbs.EVENT_SYSTEM, "%s: No such file: %s" %
                           (caller_name(), filename))
            elif exc.errno in [errno.EACCES, errno.EPERM]:
                pbs.logmsg(pbs.EVENT_SYSTEM, "%s: Permission denied: %s" %
                           (caller_name(), filename))
            elif exc.errno == errno.EBUSY:
                raise CgroupBusyError("Limit rejected")
            elif exc.errno == errno.EINVAL:
                raise CgroupLimitError("Invalid limit value: %s" % (value))
            else:
                raise
        except:
            raise

    # Return memory failcount
    def __get_mem_failcnt(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self.__cgroup_path('memory', 'failcnt',
                      jobid), 'r') as fd:
                return int(fd.readline().strip())
        except:
            return None

    # Return vmem failcount
    def __get_memsw_failcnt(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self.__cgroup_path('memsw', 'failcnt',
                      jobid), 'r') as fd:
                return int(fd.readline().strip())
        except:
            return None

    # Return hpmem failcount
    def __get_hugetlb_failcnt(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self.__cgroup_path('hugetlb', 'failcnt',
                      jobid), 'r') as fd:
                return int(fd.readline().strip())
        except:
            return None

    # Return the max usage of memory in bytes
    def __get_max_mem_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self.__cgroup_path('memory', 'max_usage_in_bytes',
                      jobid), 'r') as fd:
                return int(fd.readline().strip())
        except:
            return None

    # Return the max usage of memsw in bytes
    def __get_max_memsw_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self.__cgroup_path('memsw', 'max_usage_in_bytes',
                      jobid), 'r') as fd:
                return int(fd.readline().strip())
        except:
            return None

    # Return the max usage of hugetlb in bytes
    def __get_max_hugetlb_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self.__cgroup_path('hugetlb', 'max_usage_in_bytes',
                      jobid), 'r') as fd:
                return int(fd.readline().strip())
        except:
            return None

    # Return the cpuacct.usage in cpu seconds
    def __get_cpu_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        path = self.__cgroup_path('cpuacct', 'usage', jobid)
        try:
            with open(path, 'r') as fd:
                return int(fd.readline().strip())
        except:
            return None

    # Assign CPUs to the cpuset
    def select_cpus(self, path, ncpus):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: path is %s" % (caller_name(), path))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: ncpus is %s" %
                   (caller_name(), ncpus))
        if ncpus < 1:
            ncpus = 1
        # Must select from those currently available
        cpufile = os.path.basename(path)
        base = os.path.dirname(path)
        parent = os.path.dirname(base)
        with open(os.path.join(parent, cpufile), 'r') as fd:
            avail = expand_list(fd.read().strip())
        if len(avail) < 1:
            raise CgroupProcessingError("No CPUs avaialble in cgroup.")
        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Available CPUs: %s" %
                   (caller_name(), avail))
        assigned = []
        for f in glob.glob(os.path.join(parent, '[0-9]*', cpufile)):
            if job.endswith('-orphan'):
                continue
            with open(f, 'r') as fd:
                cpus = expand_list(fd.read().strip())
            for id in cpus:
                if id in avail:
                    avail.remove(id)
        if len(avail) < ncpus:
            raise CgroupProcessingError("Insufficient CPUs in cgroup.")
        if len(avail) == ncpus:
            return avail
        # TODO: Try to minimize NUMA nodes based on memory requirement
        return avail[:ncpus]

    # Return the error message in system message file
    def __get_error_msg(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        proc = subprocess.Popen(['dmesg'], shell=False, stdout=subprocess.PIPE)
        out = proc.communicate()[0].splitlines()
        out.reverse()
        # Check to see if the job id is found in dmesg otherwise
        # you could get the information for another job that was killed
        # the line will look like Memory cgroup stats for /pbspro/279.centos7
        kill_line = ""
        for line in out:
            start = line.find('Killed process ')
            if start >= 0:
                kill_line = line[start:]
            job_start = line.find(jobid)
            if job_start >= 0:
                return kill_line
        return ""

    # Write out host cgroup assigned resources for this job
    def write_out_cgroup_host_job_env_file(self, jobid, env_list):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        if not os.path.exists(self.host_job_env_dir):
            os.makedirs(self.host_job_env_dir, 0755)
        # Write out assigned_resources
        try:
            lines = string.join(env_list, '\n')
            filename = self.host_job_env_filename % jobid
            with open(filename, 'w') as fd:
                fd.write(lines)
            pbs.logmsg(pbs.EVENT_DEBUG4, "Wrote out file: %s" % (filename))
            pbs.logmsg(pbs.EVENT_DEBUG4, "Data: %s" % (lines))
            return True
        except:
            return False

    # Write out host cgroup assigned resources for this job
    def write_out_cgroup_assigned_resources(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        if not os.path.exists(self.hook_storage_dir):
            os.makedirs(self.hook_storage_dir, 0755)
        # Write out assigned_resources
        try:
            json_str = json.dumps(self.assigned_resources)
            filename = os.path.join(self.hook_storage_dir, jobid)
            with open(filename, 'w') as fd:
                fd.write(json_str)
            pbs.logmsg(pbs.EVENT_DEBUG4, "Wrote out file: %s" %
                       (os.path.join(self.hook_storage_dir, jobid)))
            pbs.logmsg(pbs.EVENT_DEBUG4, "Data: %s" % (json_str))
            return True
        except:
            return False

    def read_in_cgroup_assigned_resources(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        pbs.logmsg(pbs.EVENT_DEBUG4, "Host assigned resources: %s" %
                   (self.assigned_resources))
        hrfile = os.path.join(self.hook_storage_dir, jobid)
        if os.path.isfile(hrfile):
            # Read in assigned_resources
            try:
                with open(hrfile, 'r') as fd:
                    json_data = json.load(fd, object_hook=decode_dict)
                self.assigned_resources = json_data
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Host assigned resources: %s" %
                           (self.assigned_resources))
            except IOError:
                raise CgroupConfigError("I/O error reading config file")
            except json.JSONDecodeError:
                raise CgroupConfigError(
                    "JSON parsing error reading config file")
            except:
                raise
        if self.assigned_resources is not None:
            return True
        else:
            return False


#
# FUNCTION main
#
def main():
    global pbs_version
    global pbs_home
    global pbs_exec
    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Function called" % (caller_name()))
    hostname = pbs.get_local_nodename()
    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Host is %s" % (caller_name(), hostname))
    # Log the hook event type
    e = pbs.event()
    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Hook name is %s" %
               (caller_name(), e.hook_name))
    # Determine location of PBS_HOME and PBS_EXEC
    try:
        # This block will work for PBS Pro versions 13 and later
        pbs_conf = pbs.get_pbs_conf()
        pbs_home = pbs_conf['PBS_HOME']
        pbs_exec = pbs_conf['PBS_EXEC']
    except:
        # Fall back to the old method
        if 'PBS_HOME' in self.cfg:
            pbs_home = self.cfg['PBS_HOME']
        else:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "PBS_HOME needs to be defined in the config file")
            pbs.logmsg(pbs.EVENT_DEBUG, "Exiting the cgroups hook")
            pbs.event().accept()
        if 'PBS_EXEC' in self.cfg:
            pbs_exec = self.cfg['PBS_EXEC']
        else:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "PBS_EXEC needs to be defined in the config file")
            pbs.logmsg(pbs.EVENT_DEBUG, "Exiting the cgroups hook")
            pbs.event().accept()
    # Determine PBS Pro version
    cmd = os.path.join(pbs_exec, 'bin', 'pbs_hostn')
    process = subprocess.Popen([cmd, '--version'], shell=False,
                               stdout=subprocess.PIPE)
    stdout = process.communicate()[0].splitlines()
    regex = re.compile('\D*(\d+).(\d+).(\d+).*')
    m = regex.match(stdout[0])
    if m is None:
        pbs.logmsg(pbs.EVENT_DEBUG, "Failed to detemine PBS Pro version")
        pbs.logmsg(pbs.EVENT_DEBUG, "Exiting the cgroups hook")
        pbs.event().accept()
    pbs_version = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: PBS Pro version is %d.%d.%d" %
               (caller_name(), pbs_version[0], pbs_version[1], pbs_version[2]))
    try:
        # Instantiate the hook utility class
        hooks = HookUtils()
        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Event type is %s" %
                   (caller_name(), hooks.event_name(e.type)))
        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Hook utility class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s" % (caller_name(), repr(hooks)))
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
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "%s: Job information class instantiated" %
                       (caller_name()))
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s" %
                       (caller_name(), repr(jobutil)))
        else:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Event does not include a job" %
                       (caller_name()))
        # Instantiate the cgroup utility class
        vnode = None
        if hasattr(e, 'vnode_list'):
            if hostname in e.vnode_list:
                vnode = e.vnode_list[hostname]
        cgroup = CgroupUtils(hostname, vnode)
        pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Cgroup utility class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s" % (caller_name(), repr(cgroup)))
        # Bail out if there is nothing to do
        if not cgroup.subsystems:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: Cgroups disabled or none to manage" %
                       (caller_name()))
            e.accept()
        # Call the appropriate handler
        if hooks.invoke_handler(e, cgroup, jobutil) is True:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Hook handler returned success" %
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
                msg += " (held)"
            except:
                msg += " (hold failed)"
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
                msg += " (held)"
            except:
                msg += " (hold failed)"
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
                msg += " (held)"
            except:
                msg += " (hold failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        e.reject(msg)

# The following block is skipped if this is a unit testing environment.
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

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

"""
PBS Professional hook for managing cgroups on Linux execution hosts.
This hook contains the handlers required for PBS Professional to support
cgroups on Linux hosts that support them (kernel 2.6.28 and higher)

This hook services the following events:
- exechost_periodic
- exechost_startup
- execjob_attach
- execjob_begin
- execjob_end
- execjob_epilogue
- execjob_launch
"""

# NOTES:
#
# When soft_limit is true for memory, memsw represents the hard limit.
#
# The resources value in sched_config must contain entries for mem and
# vmem if those subsystems are enabled in the hook configuration file. The
# amount of resource requested will not be avaiable to the hook if they
# are not present.

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
PBS_EXEC = ''
PBS_HOME = ''
PBS_MOM_HOME = ''

# ============================================================================
# Derived error classes
# ============================================================================


class AdminError(Exception):
    """
    Base class for errors fixable only by administrative action.
    """
    pass


class ProcessingError(Exception):
    """
    Base class for errors in processing, unknown cause.
    """
    pass


class UserError(Exception):
    """
    Base class for errors fixable by the user.
    """
    pass


class JobValueError(UserError):
    """
    Errors in PBS job resource values.
    """
    pass


class CgroupBusyError(ProcessingError):
    """
    Errors when the cgroup is busy.
    """
    pass


class CgroupConfigError(AdminError):
    """
    Errors in configuring cgroup.
    """
    pass


class CgroupLimitError(AdminError):
    """
    Errors in configuring cgroup.
    """
    pass


class CgroupProcessingError(ProcessingError):
    """
    Errors processing cgroup.
    """
    pass


class TimeoutError(ProcessingError):
    """
    Timeout encountered.
    """
    pass


# ============================================================================
# Utility functions
# ============================================================================

#
# FUNCTION caller_name
#
def caller_name():
    """
    Return the name of the calling function or method.
    """
    return str(sys._getframe(1).f_code.co_name)


#
# FUNCTION convert_size
#
def convert_size(value, units='b'):
    """
    Convert a string containing a size specification (e.g. "1m") to a
    string using different units (e.g. "1024k").

    This function only interprets a decimal number at the start of the string,
    stopping at any unrecognized character and ignoring the rest of the string.

    When down-converting (e.g. MB to KB), all calculations involve integers and
    the result returned is exact. When up-converting (e.g. KB to MB) floating
    point numbers are involved. The result is rounded up. For example:

    1023MB -> GB yields 1g
    1024MB -> GB yields 1g
    1025MB -> GB yields 2g  <-- This value was rounded up

    Pattern matching or conversion may result in exceptions.
    """
    logs = {'b': 0, 'k': 10, 'm': 20, 'g': 30,
            't': 40, 'p': 50, 'e': 60, 'z': 70, 'y': 80}
    try:
        new = units[0].lower()
        if new not in logs:
            raise ValueError('Invalid unit value')
        val, old = re.match(r'([-+]?\d+)([bkmgtpezy]?)',
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
        return str(val) + new
    except KeyboardInterrupt:
        raise
    except:
        return None


#
# FUNCTION size_as_int
#
def size_as_int(value):
    """
    Convert a size string to an integer representation of size in bytes
    """
    return int(convert_size(value).rstrip(string.ascii_lowercase))


#
# FUNCTION convert_time
#
def convert_time(value, return_unit='s'):
    """
    Converts a integer value for time into the value of the return unit

    A valid decimal number, with optional sign, may be followed by a character
    representing a scaling factor.  Scaling factors may be either upper or
    lower case. Examples include:
    250ms
    40s
    +15min

    Valid scaling factors are:
    ns  = 10**-9
    us  = 10**-6
    ms  = 10**-3
    s   =      1
    min =     60
    hr  =   3600

    Pattern matching or conversion may result in exceptions.
    """
    multipliers = {'':  1, 'ns': 10 ** -9, 'us': 10 ** -6,
                   'ms': 10 ** -3, 's': 1, 'min': 60, 'hr': 3600}
    num, factor = re.match(r'([-+]?\d+)\s*([a-zA-Z]+)',
                           str(value).lower()).groups()
    # Check to see if there was not unit of time specified
    if factor is None:
        factor = ''
    # Check to see if the unit is valid
    if str.lower(factor) not in multipliers:
        raise ValueError('Time unit not recognized.')
    # Convert the value to seconds
    value = float(num) * float(multipliers[str.lower(factor)])
    if return_unit != 's':
        value = value / multipliers[str.lower(return_unit)]
    # _pbs_v1.validate_input breaks with very small time values
    # because Python converts them to values like 1e-05
    if value < 0.001:
        value = 0.0
    return value


def decode_list(data):
    """
    json hook to convert lists from unicode to utf-8
    """
    ret = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        ret.append(item)
    return ret


def decode_dict(data):
    """
    json hook to convert dictionaries from unicode to utf-8
    """
    ret = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        ret[key] = value
    return ret


def merge_dict(base, new):
    """
    Merge together two multilevel dictionaries where new
    takes precedence over base
    """
    if not isinstance(base, dict):
        raise ValueError('base must be type dict')
    if not isinstance(new, dict):
        raise ValueError('new must be type dict')
    newkeys = new.keys()
    merged = {}
    for key in base:
        if key in newkeys and isinstance(base[key], dict):
            # Take it off the list of keys to copy
            newkeys.remove(key)
            merged[key] = merge_dict(base[key], new[key])
        else:
            merged[key] = copy.deepcopy(base[key])
    # Copy the remaining unique keys from new
    for key in newkeys:
        merged[key] = copy.deepcopy(new[key])
    return merged


def expand_list(old):
    """
    Convert condensed list format (with ranges) to an expanded Python list.
    The input string is a comma separated list of digits and ranges.
    Examples include:
    0-3,8-11
    0,2,4,6
    2,5-7,10
    """
    new = []
    stripped = old.strip()
    if not stripped:
        return new
    for entry in stripped.split(','):
        if '-' in entry[1:]:
            start, end = entry.split('-', 1)
            for i in range(int(start), int(end) + 1):
                new.append(i)
        else:
            new.append(int(entry))
    return new


def find_files(path, pattern='*', kind=''):
    """
    Return a list of files similar to the find command
    """
    if isinstance(pattern, str):
        pattern = [pattern]
    if isinstance(kind, str):
        kind = [kind]
    if not isinstance(pattern, list):
        raise TypeError('Pattern must be a string or list.')
    if not isinstance(kind, list):
        raise TypeError('Kind must be a string or list.')
    for root, dirs, files in os.walk(path):
        for name in [os.path.join(root, x) for x in dirs + files]:
            pattern_matched = False
            for pat in pattern:
                if fnmatch.fnmatchcase(os.path.basename(name), pat):
                    pattern_matched = True
                    break
            if not pattern_matched:
                continue
            if not kind:
                yield name
                continue
            statinfo = os.lstat(name).st_mode
            for entry in kind:
                if not entry:
                    yield name
                    break
                for letter in entry:
                    if letter == 'f' and stat.S_ISREG(statinfo):
                        yield name
                        break
                    elif letter == 'l' and stat.S_ISLNK(statinfo):
                        yield name
                        break
                    elif letter == 'c' and stat.S_ISCHR(statinfo):
                        yield name
                        break
                    elif letter == 'b' and stat.S_ISBLK(statinfo):
                        yield name
                        break
                    elif letter == 'p' and stat.S_ISFIFO(statinfo):
                        yield name
                        break
                    elif letter == 's' and stat.S_ISSOCK(statinfo):
                        yield name
                        break
                    elif letter == 'd' and stat.S_ISDIR(statinfo):
                        yield name
                        break


def initialize_resource(resc):
    """
    Return a properly cast zero value
    """
    if isinstance(resc, pbs.pbs_int):
        ret = pbs.pbs_int(0)
    elif isinstance(resc, pbs.pbs_float):
        ret = pbs.pbs_float(0)
    elif isinstance(resc, pbs.size):
        ret = pbs.size('0')
    elif isinstance(resc, int):
        ret = 0
    elif isinstance(resc, float):
        ret = 0.0
    elif isinstance(resc, list):
        ret = []
    elif isinstance(resc, dict):
        ret = {}
    elif isinstance(resc, tuple):
        ret = ()
    elif isinstance(resc, str):
        ret = ''
    else:
        raise ValueError('Unable to initialize unknown resource type.')
    return ret


def ignore_job(jobid):
    """
    Helper function to ignore suspended jobs when removing
    currently assigned resources
    """
    printjob_cmd = os.path.join(PBS_EXEC, 'bin', 'printjob')
    job_file = os.path.join(PBS_MOM_HOME, 'mom_priv', 'jobs', '%s.JB' % jobid)
    if not os.path.isfile(job_file):
        pbs.logmsg(pbs.EVENT_DEBUG4, "File not found: %s" % (job_file))
        return False
    cmd = [printjob_cmd, job_file]
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
        regex = re.compile(r"substate:\s+(0x[0-9a-f]+)")
        substate = regex.search(out)
    except Exception as exc:
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Unexpected error: %s" %
                   (caller_name(), exc))
    if substate:
        substate = substate.group(1)
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Job %s has substate %s" % (jobid, substate))
        return substate in ['0x2b', '0x2d', 'unknown']
    return False


# ============================================================================
# Utility classes
# ============================================================================

#
# CLASS Lock
#
class Lock(object):
    """
    Implement a simple locking mechanism using a file lock
    """

    def __init__(self, path):
        self.path = path
        self.lockfd = None

    def getpath(self):
        """
        Return the path of the lock file.
        """
        return self.path

    def getlockfd(self):
        """
        Return the file descriptor of the lock file.
        """
        return self.lockfd

    def __enter__(self):
        self.lockfd = open(self.path, 'w')
        fcntl.flock(self.lockfd, fcntl.LOCK_EX)

    def __exit__(self, exc, val, trace):
        if self.lockfd:
            fcntl.flock(self.lockfd, fcntl.LOCK_UN)
            self.lockfd.close()


#
# CLASS Timeout
#
class Timeout(object):
    """
    Implement a timeout mechanism via SIGALRM
    """

    def __init__(self, duration=1, message='Operation timed out.'):
        self.duration = duration
        self.message = message

    def handler(self, sig, frame):
        """
        Throw a timeout error when SIGALRM is received
        """
        raise TimeoutError(self.message)

    def getduration(self):
        """
        Return the timeout duration
        """
        return self.duration

    def getmessage(self):
        """
        Return the timeout message
        """
        return self.message

    def __enter__(self):
        if signal.getsignal(signal.SIGALRM):
            raise RuntimeError('Alarm handler already registered.')
        signal.signal(signal.SIGALRM, self.handler)
        signal.alarm(self.duration)

    def __exit__(self, exc, val, trace):
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)


#
# CLASS HookUtils
#
class HookUtils(object):
    """
    Hook utility methods
    """

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
                'handler': self._execjob_begin_handler
            }
            self.hook_events[pbs.EXECJOB_PROLOGUE] = {
                'name': 'execjob_prologue',
                'handler': None
            }
            self.hook_events[pbs.EXECJOB_EPILOGUE] = {
                'name': 'execjob_epilogue',
                'handler': self._execjob_epilogue_handler
            }
            self.hook_events[pbs.EXECJOB_PRETERM] = {
                'name': 'execjob_preterm',
                'handler': None
            }
            self.hook_events[pbs.EXECJOB_END] = {
                'name': 'execjob_end',
                'handler': self._execjob_end_handler
            }
            self.hook_events[pbs.EXECJOB_LAUNCH] = {
                'name': 'execjob_launch',
                'handler': self._execjob_launch_handler
            }
            self.hook_events[pbs.EXECHOST_PERIODIC] = {
                'name': 'exechost_periodic',
                'handler': self._exechost_periodic_handler
            }
            self.hook_events[pbs.EXECHOST_STARTUP] = {
                'name': 'exechost_startup',
                'handler': self._exechost_startup_handler
            }
            self.hook_events[pbs.EXECJOB_ATTACH] = {
                'name': 'execjob_attach',
                'handler': self._execjob_attach_handler
            }
            self.hook_events[pbs.MOM_EVENTS] = {
                'name': 'mom_events',
                'handler': None
            }

    def __repr__(self):
        return "HookUtils(%s)" % (repr(self.hook_events))

    def event_name(self, hooktype):
        """
        Return the event name for the supplied hook type.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if hooktype in self.hook_events:
            return self.hook_events[hooktype]['name']
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "%s: Type: %s not found" % (caller_name(), type))
        return None

    def hashandler(self, hooktype):
        """
        Return the handler for the supplied hook type.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if hooktype in self.hook_events:
            return self.hook_events[hooktype]['handler'] is not None
        return None

    def invoke_handler(self, event, cgroup, jobutil, *args):
        """
        Call the appropriate handler for the supplied event.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: UID: real=%d, effective=%d" %
                   (caller_name(), os.getuid(), os.geteuid()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: GID: real=%d, effective=%d" %
                   (caller_name(), os.getgid(), os.getegid()))
        if self.hashandler(event.type):
            result = self.hook_events[event.type][
                'handler'](event, cgroup, jobutil, *args)
            return result
        pbs.logmsg(pbs.EVENT_DEBUG2,
                   "%s: %s event not handled by this hook." %
                   (caller_name(), self.event_name(event.type)))
        return False

    def _execjob_begin_handler(self, event, cgroup, jobutil):
        """
        Handler for execjob_begin events.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Instantiate the NodeConfig class for get_memory_on_node and
        # get_vmem_on node
        node = NodeConfig(cgroup.cfg)
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: NodeConfig class instantiated" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Host assigned job resources: %s" %
                   (caller_name(), jobutil.assigned_resources))
        with Lock(cgroup.cfg['cgroup_lock_file']):
            # Make sure the parent cgroup directories exist
            cgroup.create_paths()
            # Make sure the cgroup does not already exist
            # from a failed run
            cgroup.delete(event.job.id, False)
            # Create the cgroup(s) for the job
            cgroup.create_job(event.job.id, node)
            # Configure the new cgroup
            cgroup.configure_job(event.job.id,
                                 jobutil.assigned_resources, node)
            # Initialize resource usage for the job
            cgroup.update_job_usage(event.job.id, event.job.resources_used)
            # Write out the assigned resources
            cgroup.write_cgroup_assigned_resources(event.job.id)
            # Write out the environment variable for the host (pbs_attach)
            if 'device_names' in cgroup.assigned_resources:
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Devices: %s" %
                           (caller_name(),
                            cgroup.assigned_resources['device_names']))
                env_list = []
                if cgroup.assigned_resources['device_names']:
                    mics = []
                    gpus = []
                    for key in cgroup.assigned_resources['device_names']:
                        if key.startswith('mic'):
                            mics.append(key[3:])
                        elif key.startswith('nvidia'):
                            gpus.append(key[6:])
                    if mics:
                        env_list.append('OFFLOAD_DEVICES="%s"' %
                                        string.join(mics, ','))
                    if gpus:
                        # Don't put quotes around the values. ex "0" or "0,1".
                        # This will cause it to fail.
                        env_list.append('CUDA_VISIBLE_DEVICES=%s' %
                                        string.join(gpus, ','))
                pbs.logmsg(pbs.EVENT_DEBUG4, "ENV_LIST: %s" % env_list)
                cgroup.write_cgroup_host_job_env_file(event.job.id, env_list)
        return True

    def _execjob_epilogue_handler(self, event, cgroup, jobutil):
        """
        Handler for execjob_epilogue events.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # The resources_used information has a base type of pbs_resource.
        with Lock(cgroup.cfg['cgroup_lock_file']):
            # Update the usage data
            cgroup.update_job_usage(event.job.id, event.job.resources_used)
            # The job script has completed, but the obit has not been sent.
            # Delete the cgroups for this job so that they don't interfere
            # with incoming jobs assigned to this node.
            cgroup.delete(event.job.id)
        return True

    def _execjob_end_handler(self, event, cgroup, jobutil):
        """
        Handler for execjob_end events.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # The cgroup was already deleted in the epilogue handler.
        # Remove the assigned_resources and job_env files.
        filelist = []
        filelist.append(os.path.join(cgroup.hook_storage_dir, event.job.id))
        filelist.append(cgroup.host_job_env_filename % event.job.id)
        for filename in filelist:
            try:
                os.remove(filename)
            except OSError:
                pbs.logmsg(pbs.EVENT_DEBUG4, "File: %s not found" % (filename))
            except KeyboardInterrupt:
                raise
            except:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Error removing file: %s" % (filename))
        return True

    def _execjob_launch_handler(self, event, cgroup, jobutil):
        """
        Handler for execjob_launch events.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Add the parent process id to the appropriate cgroups.
        cgroup.add_pids(os.getppid(), jobutil.job.id)
        # FUTURE: Add environment variable to the job environment
        # if job requested mic or gpu
        cgroup.read_cgroup_assigned_resources(event.job.id)
        if cgroup.assigned_resources is not None:
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "assigned_resources: %s" %
                       (cgroup.assigned_resources))
            cgroup.setup_job_devices_env()
        return True

    def _exechost_periodic_handler(self, event, cgroup, jobutil):
        """
        Handler for exechost_periodic events.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        with Lock(cgroup.cfg['cgroup_lock_file']):
            # Cleanup cgroups for jobs not present on this node
            remaining = cgroup.cleanup_orphans(event.job_list)
            # Online nodes that were offlined due to a cgroup not cleaning up
            if remaining == 0 and cgroup.cfg['online_offlined_nodes']:
                vnode = pbs.event().vnode_list[cgroup.hostname]
                if os.path.isfile(cgroup.offline_file):
                    msg = 'Orphan cgroup(s) have been cleaned up. '
                    # Check with the server to see if the node comment matches.
                    # TODO: Avoid contacting the server if possible.
                    try:
                        with Timeout(10, 'Timed out contacting server'):
                            comment = \
                                pbs.server().vnode(cgroup.hostname).comment
                            while not comment:
                                time.sleep(1)
                                comment = \
                                    pbs.server().vnode(cgroup.hostname).comment
                            pbs.logmsg(pbs.EVENT_DEBUG4,
                                       "Comment: %s" % comment)
                    except KeyboardInterrupt:
                        raise
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
                    except KeyboardInterrupt:
                        raise
                    except:
                        pbs.logmsg(pbs.EVENT_DEBUG, "%s: Failed to remove %s" %
                                   (caller_name(), msg))
            # Update the resource usage information for each job
            if cgroup.cfg['periodic_resc_update']:
                for job in event.job_list:
                    pbs.logmsg(pbs.EVENT_DEBUG4,
                               "%s: Updating resource usage for %s" %
                               (caller_name(), job))
                    try:
                        cgroup.update_job_usage(
                            job, event.job_list[job].resources_used)
                    except KeyboardInterrupt:
                        raise
                    except:
                        pbs.logmsg(pbs.EVENT_DEBUG,
                                   "%s: Resource usage update failed for %s" %
                                   (caller_name(), job))
        return True

    def _exechost_startup_handler(self, event, cgroup, jobutil):
        """
        Handler for exechost_startup events.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        cgroup.create_paths()
        node = NodeConfig(cgroup.cfg)
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: NodeConfig class instantiated" %
                   (caller_name()))
        node.create_vnodes()
        host = node.hostname
        # The memory limits are interdependent and might fail when set.
        # There are three limits. Worst case scenario is to loop three
        # times in order to set them all.
        for _ in range(3):
            result = True
            if 'memory' in cgroup.subsystems:
                val = node.get_memory_on_node(cgroup.cfg)
                if val is not None:
                    if not cgroup.cfg['vnode_per_numa_node']:
                        event.vnode_list[host].resources_available['mem'] = \
                            pbs.size(val)
                try:
                    cgroup.set_limit('mem', val)
                except KeyboardInterrupt:
                    raise
                except:
                    result = False
            if 'memsw' in cgroup.subsystems:
                val = node.get_vmem_on_node(cgroup.cfg)
                if val is not None:
                    event.vnode_list[host].resources_available['vmem'] = \
                        pbs.size(val)
                    try:
                        cgroup.set_limit('vmem', val)
                    except KeyboardInterrupt:
                        raise
                    except:
                        result = False
            if 'hugetlb' in cgroup.subsystems:
                val = node.get_hpmem_on_node(cgroup.cfg)
                if val is not None:
                    event.vnode_list[host].resources_available['hpmem'] = \
                        pbs.size(val)
                    try:
                        cgroup.set_limit('hpmem', val)
                    except KeyboardInterrupt:
                        raise
                    except:
                        result = False
            if result:
                return True
        return False

    def _execjob_attach_handler(self, event, cgroup, jobutil):
        """
        Handler for execjob_attach events.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logjobmsg(jobutil.job.id, "%s: Attaching PID %s" %
                      (caller_name(), event.pid))
        # Add the job process id to the appropriate cgroups.
        cgroup.add_pids(event.pid, jobutil.job.id)
        return True


#
# CLASS JobUtils
#
class JobUtils(object):
    """
    Job utility methods
    """

    def __init__(self, job, hostname=None, assigned_resources=None):
        self.job = job
        if hostname is not None:
            self.hostname = hostname
        else:
            self.hostname = pbs.get_local_nodename()
        if assigned_resources is not None:
            self.assigned_resources = assigned_resources
        else:
            self.assigned_resources = self._get_assigned_job_resources()

    def __repr__(self):
        return ("JobUtils(%s, %s, %s)" %
                (repr(self.job),
                 repr(self.hostname),
                 repr(self.assigned_resources)))

    # Return a dictionary of assigned resources on the local node
    def _get_assigned_job_resources(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Bail out if no hostname was provided
        if self.hostname is None:
            raise CgroupProcessingError('No hostname available')
        # Bail out if no job information is present
        if self.job is None:
            raise CgroupProcessingError('No job information available')
        # Create a list of local vnodes
        vnodes = []
        vnhost_pattern = r'%s\[[\d+]\]' % self.hostname
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: vnhost pattern: %s" %
                   (caller_name(), vnhost_pattern))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Job exec_vnode list: %s" %
                   (caller_name(), self.job.exec_vnode))
        for match in re.findall(vnhost_pattern, str(self.job.exec_vnode)):
            vnodes.append(match)
        if vnodes:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Vnodes on %s: %s" %
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
                if isinstance(chunk.chunk_resources[resc],
                              (pbs.pbs_int, pbs.pbs_float, pbs.size)):
                    resources[resc] += chunk.chunk_resources[resc]
                    pbs.logmsg(pbs.EVENT_DEBUG4,
                               "%s: resources[%s][%s] is now %s" %
                               (caller_name(), self.hostname, resc,
                                resources[resc]))
                    if vnodes:
                        resources['vnodes'][chunk.vnode_name][resc] += \
                            chunk.chunk_resources[resc]
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG4,
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

    def write_to_stderr(self, job, msg):
        """
        Write a message to the job stderr file
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            filename = job.stderr_file()
            if filename is None:
                return
            with open(filename, 'a') as desc:
                desc.write(msg)
        except KeyboardInterrupt:
            raise
        except:
            pass

    def write_to_stdout(self, job, msg):
        """
        Write a message to the job stdout file
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            filename = job.stdout_file()
            if filename is None:
                return
            with open(filename, 'a') as desc:
                desc.write(msg)
        except KeyboardInterrupt:
            raise
        except:
            pass


#
# CLASS NodeConfig
#
class NodeConfig(object):
    """
    Node utility methods
    NOTE: Multiple log messages pertaining to devices have been commented
          out due to the size of the messages. They may be uncommented for
          additional debugging if necessary.
    """

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
            self.cpuinfo = self._discover_cpuinfo()
        if meminfo is not None:
            self.meminfo = meminfo
        else:
            self.meminfo = self._discover_meminfo()
        if numa_nodes is not None:
            self.numa_nodes = numa_nodes
        else:
            self.numa_nodes = self._discover_numa_nodes()
        if devices is not None:
            self.devices = devices
        else:
            self.devices = self._discover_devices()
        # Add the devices count i.e. nmics and ngpus to the numa nodes
        self._add_device_counts_to_numa_nodes()

    def __repr__(self):
        return ("NodeConfig(%s, %s, %s, %s, %s, %s)" %
                (repr(self.cfg),
                 repr(self.hostname),
                 repr(self.cpuinfo),
                 repr(self.meminfo),
                 repr(self.numa_nodes),
                 repr(self.devices)))

    def _add_device_counts_to_numa_nodes(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # pbs.logmsg(pbs.EVENT_DEBUG4, "Node Devices: %s" %
        #            self.devices.keys())
        for cls in self.devices:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Device class: %s" %
                       (caller_name(), cls))
            if cls == 'mic' or cls == 'gpu':
                # pbs.logmsg(pbs.EVENT_DEBUG4, "Devices: %s" %
                #            self.devices[cls].keys())
                for inst in self.devices[cls]:
                    numa_node = self.devices[cls][inst]['numa_node']
                    if cls == 'mic' and inst.find('mic') != -1:
                        if 'nmics' not in self.numa_nodes[numa_node]:
                            self.numa_nodes[numa_node]['nmics'] = 1
                        else:
                            self.numa_nodes[numa_node]['nmics'] += 1
                    elif cls == 'gpu':
                        if 'ngpus' not in self.numa_nodes[numa_node]:
                            self.numa_nodes[numa_node]['ngpus'] = 1
                        else:
                            self.numa_nodes[numa_node]['ngpus'] += 1
        pbs.logmsg(pbs.EVENT_DEBUG4, "NUMA nodes: %s" % (self.numa_nodes))
        return

    # Discover what type of hardware is on this node and how is it partitioned
    def _discover_numa_nodes(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        numa_nodes = {}
        for node in glob.glob(os.path.join(os.sep, "sys", "devices",
                                           "system", "node", "node*")):
            # The basename will be node0, node1, etc.
            # Capture the numeric portion as the identifier/ordinal.
            num = int(os.path.basename(node)[4:])
            if num not in numa_nodes:
                numa_nodes[num] = {}
                numa_nodes[num]['devices'] = []
            with open(os.path.join(node, "cpulist"), 'r') as desc:
                numa_nodes[num]['cpus'] = expand_list(desc.readline())
            with open(os.path.join(node, "meminfo"), 'r') as desc:
                for line in desc:
                    # Each line will contain four or five fields. Examples:
                    # Node 0 MemTotal:       32995028 kB
                    # Node 0 HugePages_Total:     0
                    entries = line.split()
                    if len(entries) < 4:
                        continue
                    if entries[2] == "MemTotal:":
                        numa_nodes[num]['MemTotal'] = \
                            convert_size(entries[3] + entries[4], 'kb')
                    elif entries[2] == "HugePages_Total:":
                        numa_nodes[num]['HugePages_Total'] = entries[3]
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s" % (caller_name(), numa_nodes))
        return numa_nodes

    # Identify devices and to which numa nodes they are attached
    def _discover_devices(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        devices = {}
        # First loop identifies all devices and determines their true path,
        # major/minor device IDs, and NUMA node affiliation (if any).
        for path in glob.glob(os.path.join(os.sep, "sys", "class", "*", "*")):
            # Skip this path if it is not a directory
            if not os.path.isdir(path):
                continue
            dirs = path.split(os.sep)   # Path components
            cls = dirs[-2]   # Device class
            inst = dirs[-1]   # Device instance
            if cls not in devices:
                devices[cls] = {}
            devices[cls][inst] = {}
            devices[cls][inst]['realpath'] = os.path.realpath(path)
            # Determine the PCI bus ID of the device
            devices[cls][inst]['bus_id'] = ''
            dirs = devices[cls][inst]['realpath'].split(os.sep)
            bus = dirs[3]
            if bus.startswith('pci'):
                devices[cls][inst]['bus_id'] = dirs[4]
            # Determine the major and minor device numbers
            filename = os.path.join(devices[cls][inst]['realpath'], 'dev')
            devices[cls][inst]['major'] = None
            devices[cls][inst]['minor'] = None
            if os.path.isfile(filename):
                with open(filename, 'r') as desc:
                    major, minor = map(int, desc.readline().strip().split(':'))
                    devices[cls][inst]['major'] = major
                    devices[cls][inst]['minor'] = minor
            numa_node = -1
            subdir = os.path.join(devices[cls][inst]['realpath'], 'device')
            # The numa_node file is not always in the same place
            # so work our way up the path trying to find it.
            while len(subdir.split(os.sep)) > 2:
                filename = os.path.join(subdir, 'numa_node')
                if os.path.isfile(filename):
                    # The file should contain a single integer
                    with open(filename, 'r') as desc:
                        numa_node = int(desc.readline().strip())
                    break
                subdir = os.path.dirname(subdir)
            if numa_node < 0:
                numa_node = 0
            devices[cls][inst]['numa_node'] = numa_node
        # Second loop determines device types and their location
        # under /dev. Only look for block and character devices.
        for path in find_files(os.path.join(os.sep, 'dev'), kind='bc'):
            # If the stat fails, log it and continue.
            try:
                statinfo = os.stat(path)
            except KeyboardInterrupt:
                raise
            except:
                pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Stat error on %s" %
                           (caller_name(), path))
                continue
            major = os.major(statinfo.st_rdev)
            minor = os.minor(statinfo.st_rdev)
            pbs.logmsg(pbs.EVENT_DEBUG4, "Path: %s, Major: %d, Minor: %d" %
                       (path, major, minor))
            for cls in devices:
                for inst in devices[cls]:
                    if 'type' not in devices[cls][inst]:
                        devices[cls][inst]['type'] = None
                    if 'device' not in devices[cls][inst]:
                        devices[cls][inst]['device'] = None
                    if devices[cls][inst]['major'] == major:
                        if devices[cls][inst]['minor'] == minor:
                            if stat.S_ISCHR(statinfo.st_mode):
                                devices[cls][inst]['type'] = 'c'
                            else:
                                devices[cls][inst]['type'] = 'b'
                            devices[cls][inst]['device'] = path
        # Check to see if there are gpus on the node and copy them
        # into their own dictionary.
        devices['gpu'] = {}
        gpus = self._discover_gpus()
        if gpus:
            for cls in devices:
                for inst in devices[cls]:
                    for gpuid in gpus:
                        if gpus[gpuid] == devices[cls][inst]['bus_id']:
                            devices['gpu'][gpuid] = devices[cls][inst]
        # pbs.logmsg(pbs.EVENT_DEBUG4, "Discovered devices: %s" % (devices))
        return devices

    # Return a dictionary where the keys are the name of the GPU devices
    # and the values are the PCI bus IDs.
    def _discover_gpus(self):
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
        except KeyboardInterrupt:
            raise
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
                    bus_id = child.get('id')
                    name = 'nvidia%s' % child.find('minor_number').text
                    gpus[name] = bus_id
        except Exception as exc:
            pbs.logmsg(pbs.EVENT_DEBUG, "Unexpected error: %s" % exc)
        pbs.logmsg(pbs.EVENT_DEBUG4, "GPUs: %s" % gpus)
        return gpus

    # Return a dictionary where the keys are the NUMA node ordinals
    # and the values are the various memory sizes
    def _discover_meminfo(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        meminfo = {}
        with open(os.path.join(os.sep, "proc", "meminfo"), 'r') as desc:
            for line in desc:
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
    def _discover_cpuinfo(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        cpuinfo = {}
        cpuinfo['cpu'] = {}
        proc = None
        with open(os.path.join(os.sep, "proc", "cpuinfo"), 'r') as desc:
            for line in desc:
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
                        cores = cpuinfo['cpu'].keys()
                        threads = []
                        # CPUs with matching core IDs are hyperthreads
                        # sharing the same physical core. Loop through
                        # the cores to construct a list of threads.
                        for xid in cores:
                            xcore = cpuinfo['cpu'][xid]
                            for yid in cores:
                                ycore = cpuinfo['cpu'][yid]
                                if xid >= yid:
                                    continue
                                if xcore['physical id'] != \
                                        ycore['physical id']:
                                    continue
                                if xcore['core id'] == ycore['core id']:
                                    cpuinfo['cpu'][xid]['threads'].append(yid)
                                    threads.append(yid)
                        pbs.logmsg(pbs.EVENT_DEBUG4, "HT cores: %s" % threads)
                        cpuinfo['hyperthreads'] = threads
        except KeyboardInterrupt:
            raise
        except:
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Hyperthreading check failed" %
                       (caller_name()))
        cpuinfo['physical_cpus'] = cpuinfo['logical_cpus'] / \
            cpuinfo['hyperthreads_per_core']
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s returning: %s" %
                   (caller_name(), cpuinfo))
        return cpuinfo

    def gather_jobs_on_node(self):
        """
        Gather the jobs assigned to this node and local vnodes
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Get the job list from the jobs directory
        joblist = []
        try:
            for filename in [os.path.basename(x) for x in
                             glob.glob(os.path.join(PBS_MOM_HOME, 'mom_priv',
                                                    'jobs', '*.JB'))]:
                joblist.append(filename[:-3])
        except KeyboardInterrupt:
            raise
        except:
            pbs.logmsg(pbs.EVENT_DEBUG, "Could not get job list for %s" %
                       self.hostname)
            raise
        pbs.logmsg(pbs.EVENT_DEBUG4, "Jobs from server for %s: %s" %
                   (self.hostname, joblist))
        return joblist

    def get_memory_on_node(self, config, memtotal=None):
        """
        Get the memory resource on this mom
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Calculate total memory
        try:
            if memtotal is None:
                total = size_as_int(self.meminfo['MemTotal'])
            else:
                total = size_as_int(memtotal)
        except KeyboardInterrupt:
            raise
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
        except KeyboardInterrupt:
            raise
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

    def get_vmem_on_node(self, config, vmemtotal=None):
        """
        Get the virtual memory resource on this mom
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Calculate total swap
        try:
            if vmemtotal is None:
                swap = size_as_int(self.meminfo['SwapTotal'])
            else:
                swap = size_as_int(vmemtotal)
        except KeyboardInterrupt:
            raise
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
        except KeyboardInterrupt:
            raise
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

    def get_hpmem_on_node(self, config, hpmemtotal=None):
        """
        Get the huge page memory resource on this mom
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Calculate hpmem
        try:
            if hpmemtotal is None:
                total = size_as_int(self.meminfo['Hugepagesize'])
                total *= (self.meminfo['HugePages_Total'] -
                          self.meminfo['HugePages_Rsvd'])
            else:
                total = size_as_int(hpmemtotal)
        except KeyboardInterrupt:
            raise
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
        except KeyboardInterrupt:
            raise
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

    def create_vnodes(self):
        """
        Create individual vnodes per socket
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        vnode_list = pbs.event().vnode_list
        if self.cfg['vnode_per_numa_node']:
            vnodes = True
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: vnode_per_numa_node is enabled" %
                       (caller_name()))
        else:
            vnodes = False
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "%s: vnode_per_numa_node is disabled" % (caller_name()))
        vnode_name = self.hostname
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: numa nodes: %s" %
                   (caller_name(), self.numa_nodes))
        vnode_list[vnode_name] = pbs.vnode(vnode_name)
        host_resc_avail = vnode_list[self.hostname].resources_available
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: host_resc_avail: %s" %
                   (caller_name(), host_resc_avail))
        vnode_msg = "%s: vnode_list[%s].resources_available['ncpus'] = %d"
        for nnid in self.numa_nodes:
            if vnodes:
                vnode_name = self.hostname + "[%d]" % nnid
                vnode_list[vnode_name] = pbs.vnode(vnode_name)
                vnode_resc_avail = vnode_list[vnode_name].resources_available
            for key, val in sorted(self.numa_nodes[nnid].iteritems()):
                if key is None:
                    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: key is None" %
                               (caller_name()))
                    continue
                if val is None:
                    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: val is None" %
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
                        if not isinstance(host_resc_avail['ncpus'],
                                          (int, pbs.pbs_int)):
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
                        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: key = %s (%s)" %
                                   (caller_name(), key, type(key)))
                        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: val = %s (%s)" %
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
class CgroupUtils(object):
    """
    Cgroup utility methods
    """

    def __init__(self, hostname, vnode, cfg=None, subsystems=None,
                 paths=None, vntype=None, assigned_resources=None):
        self.hostname = hostname
        self.vnode = vnode
        # _check_os will raise an exception if cgroups are not present
        self._check_os()
        # Read in the config file
        if cfg is not None:
            self.cfg = cfg
        else:
            self.cfg = self._parse_config_file()
        # Collect the cgroup mount points
        if paths is not None:
            self.paths = paths
        else:
            self.paths = self._get_paths()
        # Raise an error if nothing is mounted
        if not self.paths:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: No cgroups mounted" %
                       (caller_name()))
            raise CgroupProcessingError("No CPUs avaialble in cgroup.")
        # Define the local vnode type
        if vntype is not None:
            self.vntype = vntype
        else:
            self.vntype = self._get_vnode_type()
        # Determine which subsystems we care about
        if subsystems is not None:
            self.subsystems = subsystems
        else:
            self.subsystems = self._target_subsystems()
        # Return now if nothing is enabled
        if not self.subsystems:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: No cgroups enabled" %
                       (caller_name()))
            self.assigned_resources = {}
            return
        # location to store information for the different hook events
        self.hook_storage_dir = os.path.join(PBS_MOM_HOME, 'mom_priv',
                                             'hooks', 'hook_data')
        self.host_job_env_dir = os.path.join(PBS_MOM_HOME, 'aux')
        self.host_job_env_filename = os.path.join(self.host_job_env_dir,
                                                  '%s.env')
        # information for offlining nodes
        self.offline_file = os.path.join(PBS_MOM_HOME, 'mom_priv', 'hooks',
                                         ('%s.offline' %
                                          pbs.event().hook_name))
        self.offline_msg = "Hook %s: " % pbs.event().hook_name
        self.offline_msg += "Unable to clean up one or more cgroups"
        # Collect the cgroup resources
        if assigned_resources:
            self.assigned_resources = assigned_resources
        else:
            self.assigned_resources = self._get_assigned_cgroup_resources()

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
    def _check_os(self):
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
                       "%s: Kernel needs to be >= 2.6.28. Found %s.%s.%s" %
                       (caller_name(), rel[0], rel[1], rel[2]))
            raise CgroupConfigError("Kernel does not support cgroups")
        return supported

    # Read the config file in json format
    def _parse_config_file(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Turn everything off by default. These settings be modified
        # when the configuration file is read. Keep the keys in sync
        # with the default cgroup configuration files.
        defaults = {}
        defaults['cgroup_prefix'] = 'pbspro'
        defaults['cgroup_lock_file'] = os.path.join(PBS_MOM_HOME, 'mom_priv',
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
            tmpcfg = os.path.join(PBS_MOM_HOME, 'mom_priv', 'hooks',
                                  'pbs_cgroups.CF')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            tmpcfg = os.path.join(PBS_HOME, 'server_priv', 'hooks',
                                  'pbs_cgroups.CF')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            tmpcfg = os.path.join(PBS_MOM_HOME, 'mom_priv', 'hooks',
                                  'pbs_cgroups.json')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            tmpcfg = os.path.join(PBS_HOME, 'server_priv', 'hooks',
                                  'pbs_cgroups.json')
            if os.path.isfile(tmpcfg):
                config_file = tmpcfg
        if not config_file:
            raise CgroupConfigError("Config file not found")
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Config file is %s" %
                   (caller_name(), config_file))
        try:
            with open(config_file, 'r') as desc:
                config = merge_dict(defaults,
                                    json.load(desc, object_hook=decode_dict))
        except IOError:
            raise CgroupConfigError("I/O error reading config file")
        except KeyboardInterrupt:
            raise
        except:
            raise
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "%s: cgroup hook configuration: %s" %
                   (caller_name(), config))
        return config

    # Determine which subsystems are being requested
    def _target_subsystems(self):
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
    def _copy_from_parent(self, dest):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        filename = os.path.basename(dest)
        subdir = os.path.dirname(dest)
        parent = os.path.dirname(subdir)
        source = os.path.join(parent, filename)
        if not os.path.isfile(source):
            raise CgroupConfigError('Failed to read %s' % (source))
        with open(source, 'r') as desc:
            self.write_value(dest, desc.read().strip())

    # Determine the path for a cgroup directory given the subsystem, mount
    # point, and mount flags
    def _assemble_path(self, subsys, mnt_point, flags):
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
        return os.path.join(mnt_point, self.cfg['cgroup_prefix'], prefix)

    # Create a dictionary of the cgroup subsystems and their corresponding
    # directories taking mount options (noprefix) into account
    def _get_paths(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        paths = {}
        # Loop through the mounts and collect the ones for cgroups
        with open(os.path.join(os.sep, "proc", "mounts"), 'r') as desc:
            for line in desc:
                entries = line.split()
                if entries[2] != "cgroup":
                    continue
                # It is possible to have more than one cgroup mounted in
                # the same place, so check them all for each mount.
                flags = entries[3].split(',')
                if 'cpu' in flags:
                    paths['cpu'] = \
                        self._assemble_path('cpu', entries[1], flags)
                if 'cpuacct' in flags:
                    paths['cpuacct'] = \
                        self._assemble_path('cpuacct', entries[1], flags)
                if 'cpuset' in flags:
                    paths['cpuset'] = \
                        self._assemble_path('cpuset', entries[1], flags)
                if 'devices' in flags:
                    paths['devices'] = \
                        self._assemble_path('devices', entries[1], flags)
                if 'hugetlb' in flags:
                    paths['hugetlb'] = \
                        self._assemble_path('hugetlb', entries[1], flags)
                if 'memory' in flags:
                    paths['memory'] = \
                        self._assemble_path('memory', entries[1], flags)
                    # memory and memsw share a common mount point,
                    # but use a different prefix
                    paths['memsw'] = \
                        self._assemble_path('memsw', entries[1], flags)
        if not paths:
            raise CgroupConfigError("Cgroup paths not detected")
        return paths

    # Return the path to a cgroup file or directory
    def _cgroup_path(self, subsys, cgfile='', jobid=''):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Note: The tasks file never uses a prefix (e.g. use tasks and not
        # cpuset.tasks).
        # Note: The os.path.join() method is smart enough to ignore
        # empty strings unless they occur as the last parameter.
        if not subsys or subsys not in self.paths:
            return None
        try:
            subdir, prefix = os.path.split(self.paths[subsys])
        except KeyboardInterrupt:
            raise
        except:
            return None
        if not cgfile:
            # Caller wants directory name
            if jobid:
                return os.path.join(subdir, jobid, '')
            return os.path.join(subdir, '')
        # Caller wants file name
        if cgfile == 'tasks':
            return os.path.join(subdir, jobid, cgfile)
        return os.path.join(subdir, jobid, (prefix + cgfile))

    def create_paths(self):
        """
        Create the cgroup parent directories that will contain the jobs
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            # Create the directories that PBS will use to house the jobs
            old_umask = os.umask(0022)
            for subsys in self.subsystems:
                subdir = self._cgroup_path(subsys)
                if not subdir:
                    raise CgroupConfigError('No path for subsystem: %s' %
                                            (subsys))
                if not os.path.exists(subdir):
                    os.makedirs(subdir, 0755)
                    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Created directory %s" %
                               (caller_name(), subdir))
                    if subsys == 'memory' or subsys == 'memsw':
                        # Enable 'use_hierarchy' for memory when either memory
                        # or memsw is in use.
                        filename = self._cgroup_path('memory',
                                                     'use_hierarchy')
                        if not os.path.isfile(filename):
                            raise CgroupConfigError('Failed to configure %s' %
                                                    (filename))
                        self.write_value(filename, 1)
                    elif subsys == 'cpuset':
                        self._copy_from_parent(self._cgroup_path(subsys,
                                                                 'cpus'))
                        self._copy_from_parent(self._cgroup_path(subsys,
                                                                 'mems'))
        except KeyboardInterrupt:
            raise
        except:
            raise CgroupConfigError("Failed to create directory: %s" %
                                    (self.paths[subsys]))
        finally:
            os.umask(old_umask)

    # Return the vnode type of the local node
    def _get_vnode_type(self):
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
        filename = os.path.join(PBS_MOM_HOME, 'mom_priv', 'vntype')
        try:
            with open(filename, 'r') as desc:
                file_vntype = desc.readline().strip()
        except KeyboardInterrupt:
            raise
        except:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       "%s: Failed to read vntype file %s" %
                       (caller_name(), filename))
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
                with open(filename, 'w') as desc:
                    desc.write(resc_vntype)
            except KeyboardInterrupt:
                raise
            except:
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "%s: Failed to update vntype file %s" %
                           (caller_name(), filename))
        pbs.logmsg(pbs.EVENT_DEBUG4, "vntype: %s" % resc_vntype)
        return resc_vntype

    # Return a dictionary of currently assigned cgroup resources per job
    def _get_assigned_cgroup_resources(self):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        assigned = {}
        for key in self.paths:
            path = os.path.dirname(self._cgroup_path(key))
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Examining %s" %
                       (caller_name(), path))
            # Do not exclude orphans
            for subdir in glob.glob(os.path.join(path, '[0-9]*')):
                jobid = os.path.basename(subdir)
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Job ID is %s" %
                           (caller_name(), jobid))
                if jobid not in assigned:
                    assigned[jobid] = {}
                if key in ('cpu', 'cpuacct', 'memsw'):
                    continue
                if key not in assigned[jobid]:
                    assigned[jobid][key] = {}
                if key == 'cpuset':
                    with open(self._cgroup_path(key, 'cpus', jobid)) as desc:
                        assigned[jobid][key]['cpus'] = \
                            expand_list(desc.readline())
                    with open(self._cgroup_path(key, 'mems', jobid)) as desc:
                        assigned[jobid][key]['mems'] = \
                            expand_list(desc.readline())
                elif key == 'memory':
                    with open(self._cgroup_path(key, 'limit_in_bytes',
                                                jobid)) as desc:
                        assigned[jobid][key]['limit_in_bytes'] = \
                            int(desc.readline())
                    with open(self._cgroup_path(key, 'soft_limit_in_bytes',
                                                jobid)) as desc:
                        assigned[jobid][key]['soft_limit_in_bytes'] = \
                            int(desc.readline())
                    with open(self._cgroup_path('memsw', 'limit_in_bytes',
                                                jobid)) as desc:
                        assigned[jobid]['memsw'] = {}
                        assigned[jobid]['memsw']['limit_in_bytes'] = \
                            int(desc.readline())
                elif key == 'hugetlb':
                    with open(self._cgroup_path(key, 'limit_in_bytes',
                                                jobid)) as desc:
                        assigned[jobid][key]['limit_in_bytes'] = \
                            int(desc.readline())
                elif key == 'devices':
                    path = self._cgroup_path(key, 'list', jobid)
                    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Devices path is %s" %
                               (caller_name(), path))
                    with open(path) as desc:
                        assigned[jobid][key]['list'] = []
                        for line in desc:
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

    def enabled(self, subsystem):
        """
        Return whether a subsystem is enabled
        """
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

    def default(self, subsystem):
        """
        Return the default value for a subsystem
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if subsystem in self.cfg['cgroup']:
            if 'default' in self.cfg['cgroup'][subsystem]:
                return self.cfg['cgroup'][subsystem]['default']
        return None

    # Check to see if the pid's owner matches the job's owner
    def _is_pid_owner(self, pid, job_uid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            proc_uid = os.stat('/proc/%d' % pid).st_uid
        except OSError:
            pbs.logmsg(pbs.EVENT_DEBUG, "Unknown pid: %d" % pid)
            return False
        except Exception as exc:
            pbs.logmsg(pbs.EVENT_DEBUG, "Unexpected error: %s" % exc)
            return False
        pbs.logmsg(pbs.EVENT_DEBUG4, '/proc/%d uid:%d' % (pid, proc_uid))
        pbs.logmsg(pbs.EVENT_DEBUG4, "Job uid: %d" % job_uid)
        if proc_uid != job_uid:
            pbs.logmsg(pbs.EVENT_DEBUG4, "Proc uid: %d != Job owner: %d" %
                       (proc_uid, job_uid))
            return False
        return True

    def add_pids(self, pids, jobid):
        """
        Add some number of PIDs to the cgroup tasks files for each subsystem
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # make pids a list
        if isinstance(pids, int):
            pids = [pids]
        if not pids:
            return
        if pbs.event().type == pbs.EXECJOB_LAUNCH:
            if 1 in pids:
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "%s: Job %s contains defunct process" %
                           (caller_name(), jobid))
                # Use a list comprehension to remove all instances of the
                # number 1
                pids = [x for x in pids if x != 1]
        if not pids:
            return
        # check pids to make sure that they are owned by the job owner
        if pbs.event().type == pbs.EXECJOB_ATTACH:
            pbs.logmsg(pbs.EVENT_DEBUG4, "event type: attach")
            try:
                uid = pwd.getpwnam(pbs.event().job.euser).pw_uid
            except KeyboardInterrupt:
                raise
            except:
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "Failed to lookup UID by name")
                raise
            tmp_pids = []
            for process in pids:
                if self._is_pid_owner(process, uid):
                    tmp_pids.append(process)
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               "process %d not owned by %s" %
                               (process, uid))
            pids = tmp_pids
        if not pids:
            return
        # Determine which subsystems will be used
        for subsys in self.subsystems:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: subsys = %s" %
                       (caller_name(), subsys))
            # memsw and memory use the same tasks file
            if subsys == "memsw" and "memory" in self.subsystems:
                continue
            tasks_file = self._cgroup_path(subsys, 'tasks', jobid)
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: tasks file = %s" %
                       (caller_name(), tasks_file))
            try:
                for process in pids:
                    self.write_value(tasks_file, process, 'a')
            except IOError as exc:
                raise CgroupLimitError("Failed to add PIDs %s to %s (%s)" %
                                       (str(pids), tasks_file,
                                        errno.errorcode[exc.errno]))
            except KeyboardInterrupt:
                raise
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
                value = string.join(offload_devices, ',')
                pbs.event().env['OFFLOAD_DEVICES'] = '"%s"' % value
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "offload_devices: %s" % offload_devices)
            if cuda_visible_devices:
                value = string.join(cuda_visible_devices, ',')
                pbs.event().env['CUDA_VISIBLE_DEVICES'] = '"%s"' % value
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "cuda_visible_devices: %s" % cuda_visible_devices)
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "Environment: %s" % pbs.event().env)
            return [offload_devices, cuda_visible_devices]
        else:
            return False

    def _setup_subsys_devices(self, jobid, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if 'devices' not in self.subsystems:
            return
        devices_list_file = self._cgroup_path('devices', 'list', jobid)
        devices_deny_file = self._cgroup_path('devices', 'deny', jobid)
        devices_allow_file = self._cgroup_path('devices', 'allow', jobid)
        # Add devices the user is granted access to
        with open(devices_list_file, 'r') as desc:
            devices_allowed = desc.read().splitlines()
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
                statinfo = os.stat(stat_filename)
            except OSError:
                pbs.logmsg(pbs.EVENT_DEBUG,
                           "%s: Entry not added to devices.allow: %s" %
                           (caller_name(), item))
                pbs.logmsg(pbs.EVENT_DEBUG4, "%s: File not found: %s" %
                           (caller_name(), stat_filename))
                continue
            except Exception as exc:
                pbs.logmsg(pbs.EVENT_DEBUG, "Unexpected error: %s" % exc)
                continue
            device_type = None
            if stat.S_ISBLK(statinfo.st_mode):
                device_type = "b"
            elif stat.S_ISCHR(statinfo.st_mode):
                device_type = "c"
            if not device_type:
                pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Unknown device type: %s" %
                           (caller_name(), stat_filename))
                continue
            if len(item) == 3 and isinstance(item[2], str):
                value = "%s %s:%s %s" % (device_type,
                                         os.major(statinfo.st_rdev),
                                         item[2], item[1])
            else:
                value = "%s %s:%s %s" % (device_type,
                                         os.major(statinfo.st_rdev),
                                         os.minor(statinfo.st_rdev),
                                         item[1])
            self.write_value(devices_allow_file, value)
            pbs.logmsg(pbs.EVENT_DEBUG4, "write_value: %s" % value)
        with open(devices_list_file, 'r') as desc:
            devices_allowed = desc.read().splitlines()
        pbs.logmsg(pbs.EVENT_DEBUG4, "Updated devices.list: %s" %
                   devices_allowed)

    # Select devices to assign to the job
    def _assign_devices(self, device_kind, device_list, device_count, node):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        devices = device_list[:device_count]
        pbs.logmsg(pbs.EVENT_DEBUG4, "Device List: %s" % devices)
        device_names = []
        device_allowed = []
        for dev in devices:
            # Skip device if already present in names
            if dev in device_names:
                continue
            # Skip device if already present in allowed
            device_info = node.devices[device_kind][dev]
            dev_entry = "%s %d:%d rwm" % (device_info['type'],
                                          device_info['major'],
                                          device_info['minor'])
            if dev_entry in device_allowed:
                continue
            # Device controllers must also be added for certain devices
            if device_kind == 'mic':
                # Requires the ctrl (0) and the scif (1) to be added
                dev_entry = "%s %d:0 rwm" % (device_info['type'],
                                             device_info['major'])
                if dev_entry not in device_allowed:
                    device_allowed.append(dev_entry)
                dev_entry = "%s %d:1 rwm" % (device_info['type'],
                                             device_info['major'])
                if dev_entry not in device_allowed:
                    device_allowed.append(dev_entry)
            elif device_kind == 'gpu':
                # Requires the ctrl (255) to be added
                dev_entry = "%s %d:255 rwm" % (device_info['type'],
                                               device_info['major'])
                if dev_entry not in device_allowed:
                    device_allowed.append(dev_entry)
            # Now append the device name and entry
            device_names.append(dev)
            dev_entry = "%s %d:%d rwm" % (device_info['type'],
                                          device_info['major'],
                                          device_info['minor'])
            if dev_entry not in device_allowed:
                device_allowed.append(dev_entry)
        return device_names, device_allowed

    def get_device_name(self, node, available, socket, major, minor):
        """
        Find the device name
        """
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

    # Take two dictionaries containing known types and combine them together
    def _combine_resources(self, dict1, dict2):
        dest = {}
        for src in [dict1, dict2]:
            for key in src:
                val = src[key]
                vtype = type(val)
                if key not in dest:
                    if vtype is int:
                        dest[key] = 0
                    elif vtype is float:
                        dest[key] = 0.0
                    elif vtype is str:
                        dest[key] = ''
                    elif vtype is list:
                        dest[key] = []
                    elif vtype is dict:
                        dest[key] = {}
                    elif vtype is tuple:
                        dest[key] = ()
                    else:
                        raise ValueError('Unrecognized resource type.')
                dest[key] += val
        return dest

    # Determine whether a job fits within resources
    def _assign_resources(self, requested, available, socketlist, node):
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
                    for htcore in node.cpuinfo['hyperthreads']:
                        if htcore in cores:
                            cores.remove(htcore)
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
            names, devices = self._assign_devices('mic', mics[:nmics],
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
            names, devices = self._assign_devices('gpu', gpus[:ngpus],
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
            if 'mem' not in assigned:
                assigned['mem'] = 0
            assigned['mem'] += req_mem
        return assigned

    def assign_job(self, requested, available, node):
        """
        Assign resources to the job. There are two scenarios that need to
        be handled:
        1. If vnodes are present in the requested resources, then the
           scheduler has already decided where the job is to run. Check
           the available resources to ensure an orphaned cgroup is not
           consuming them.
        2. If no vnodes are present in the requested resources, try to
           span the fewest number of sockets when creating the assignment.
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4,
                   "Requested: %s, Available: %s, Numa Nodes: %s" %
                   (requested, available, node.numa_nodes))
        # pbs.logmsg(pbs.EVENT_DEBUG4, "Devices: %s" % (node.devices))
        #
        # Create a list of memory-only NUMA nodes (for KNL). These get assigned
        # in addition to NUMA nodes with assigned devices or cpus.
        memory_only_nodes = []
        for nnid in node.numa_nodes:
            if not node.numa_nodes[nnid]['cpus'] and \
                   not node.numa_nodes[nnid]['devices']:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Found memory only NUMA node: %s" %
                           (node.numa_nodes[nnid]))
                memory_only_nodes.append(nnid)
        # Create a list of vnode/socket pairs
        if 'vnodes' in requested:
            regex = re.compile(r'(.*)\[(\d+)\].*')
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
                for sock in sockets:
                    jobcount[sock] = 0
                for job in self.assigned_resources:
                    jobresc = self.assigned_resources[job]
                    if 'cpuset.mems' in jobresc:
                        for sock in jobresc['cpuset.mems']:
                            jobcount[sock] += 1
                sorted_jobcounts = sorted(jobcount.items(),
                                          key=operator.itemgetter(1))
                reordered = []
                for counts in sorted_jobcounts:
                    reordered.append(counts[0])
                sockets = reordered
            pairlist = []
            for sock in sockets:
                pairlist.append([None, int(sock)])
        # Loop through the sockets or vnodes and assign resources
        assigned = {}
        for pair in pairlist:
            vnode = pair[0]
            socket = pair[1]
            if vnode:
                myname = 'vnode %s[%d]' % (vnode, socket)
                req = requested['vnodes']["%s[%d]" % (vnode, socket)]
            else:
                myname = 'socket %d' % socket
                req = requested
            pbs.logmsg(pbs.EVENT_DEBUG4, 'Current target is %s' % myname)
            new = self._assign_resources(req, available[socket],
                                         [socket], node)
            if new:
                new['cpuset.mems'].append(socket)
                # Add the memory-only NUMA nodes
                for nnid in memory_only_nodes:
                    if nnid not in new['cpuset.mems']:
                        new['cpuset.mems'].append(nnid)
                pbs.logmsg(pbs.EVENT_DEBUG4, "Resources assigned to %s" %
                           myname)
                if vnode:
                    assigned = self._combine_resources(assigned, new)
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
        for pair in pairlist:
            socket = pair[1]
            socketlist.append(socket)
            total = self._combine_resources(total, available[socket])
        pbs.logmsg(pbs.EVENT_DEBUG4, "Combined available resources: %s" %
                   (total))
        return self._assign_resources(requested, total, socketlist, node)

    def available_node_resources(self, node):
        """
        Determine which resources are available from the supplied node
        dictionary (i.e. the local node) by removing resources already
        assigned to jobs.
        """
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
            if not ignore_job(job):
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
                        except KeyboardInterrupt:
                            raise
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
                            if available[socket]['devices']:
                                pbs.logmsg(pbs.EVENT_DEBUG4,
                                           "Check device: %s" % (device))
                                pbs.logmsg(pbs.EVENT_DEBUG4,
                                           "Available device: %s" %
                                           (available[socket]['devices']))
                                major, minor = device.split()[1].split(':')
                                avail_device = self.get_device_name(node,
                                                                    available,
                                                                    socket,
                                                                    major,
                                                                    minor)
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
                        except Exception as exc:
                            pbs.logmsg(pbs.EVENT_DEBUG2,
                                       "Unexpected error: %s" % exc)
                            pbs.logmsg(pbs.EVENT_DEBUG2,
                                       "Error removing %s from %s" %
                                       (device, available[socket]['devices']))
            else:
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Job %s res not removed from host " % job +
                           "available res: suspended job")
        pbs.logmsg(pbs.EVENT_DEBUG4, "Available resources: %s" % (available))
        return available

    def set_limit(self, resource, value, jobid=''):
        """
        Set a cgroup limit on a node or a job
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        if jobid:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s = %s for job %s" %
                       (caller_name(), resource, value, jobid))
        else:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: %s = %s for node" %
                       (caller_name(), resource, value))
        if resource == 'mem':
            if 'memory' in self.subsystems:
                path = self._cgroup_path('memory', 'limit_in_bytes', jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'softmem':
            if 'memory' in self.subsystems:
                path = self._cgroup_path('memory', 'soft_limit_in_bytes',
                                         jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'vmem':
            if 'memsw' in self.subsystems:
                if 'memory' not in self.subsystems:
                    path = self._cgroup_path('memory', 'limit_in_bytes',
                                             jobid)
                    self.write_value(path, size_as_int(value))
                path = self._cgroup_path('memsw', 'limit_in_bytes', jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'hpmem':
            if 'hugetlb' in self.subsystems:
                path = self._cgroup_path('hugetlb', 'limit_in_bytes', jobid)
                self.write_value(path, size_as_int(value))
        elif resource == 'ncpus':
            if 'cpuset' in self.subsystems:
                path = self._cgroup_path('cpuset', 'cpus', jobid)
                cpus = self.select_cpus(path, value)
                if not cpus:
                    raise CgroupLimitError("Failed to configure cpuset.")
                cpus = string.join(map(str, cpus), ',')
                self.write_value(path, cpus)
                if jobid:
                    path = self._cgroup_path('cpuset', 'mems', jobid)
                    self._copy_from_parent(path)
        elif resource == 'cpuset.cpus':
            if 'cpuset' in self.subsystems:
                path = self._cgroup_path('cpuset', 'cpus', jobid)
                cpus = value
                if not cpus:
                    raise CgroupLimitError("Failed to configure cpuset cpus.")
                cpus = string.join(map(str, cpus), ',')
                self.write_value(path, cpus)
        elif resource == 'cpuset.mems':
            if 'cpuset' in self.subsystems:
                path = self._cgroup_path('cpuset', 'mems', jobid)
                mems = value
                if not mems:
                    raise CgroupLimitError("Failed to configure cpuset mems.")
                mems = string.join(map(str, mems), ',')
                self.write_value(path, mems)
        elif resource == 'devices':
            if 'devices' in self.subsystems:
                path = self._cgroup_path('devices', 'allow', jobid)
                devices = value
                if not devices:
                    raise CgroupLimitError("Failed to configure devices.")
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Setting devices: %s for %s" % (devices, jobid))
                for dev in devices:
                    self.write_value(path, dev)
                path = self._cgroup_path('devices', 'list', jobid)
                with open(path, 'r') as desc:
                    output = desc.readlines()
                pbs.logmsg(pbs.EVENT_DEBUG4, "devices.list: %s" % output)
        else:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Resource %s not handled" %
                       (caller_name(), resource))

    def update_job_usage(self, jobid, resc_used):
        """
        Update resource usage for a job
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: resc_used = %s" %
                   (caller_name(), str(resc_used)))
        # Sort the subsystems so that we consistently look at the subsystems
        # in the same order every time
        self.subsystems.sort()
        for subsys in self.subsystems:
            if subsys == "memory":
                max_mem = self._get_max_mem_usage(jobid)
                if max_mem is None:
                    pbs.logjobmsg(jobid, "%s: No max mem data" %
                                  (caller_name()))
                else:
                    resc_used['mem'] = pbs.size(convert_size(max_mem, 'kb'))
                    pbs.logjobmsg(jobid,
                                  "%s: Memory usage: mem=%s" %
                                  (caller_name(), resc_used['mem']))
                mem_failcnt = self._get_mem_failcnt(jobid)
                if mem_failcnt is None:
                    pbs.logjobmsg(jobid, "%s: No mem fail count data" %
                                  (caller_name()))
                else:
                    # Check to see if the job exceeded its resource limits
                    if mem_failcnt > 0:
                        err_msg = self._get_error_msg(jobid)
                        pbs.logjobmsg(jobid,
                                      "Cgroup memory limit exceeded: %s" %
                                      (err_msg))
            elif subsys == "memsw":
                max_vmem = self._get_max_memsw_usage(jobid)
                if max_vmem is None:
                    pbs.logjobmsg(jobid, "%s: No max vmem data" %
                                  (caller_name()))
                else:
                    resc_used['vmem'] = pbs.size(convert_size(max_vmem, 'kb'))
                    pbs.logjobmsg(jobid,
                                  "%s: Memory usage: vmem=%s" %
                                  (caller_name(), resc_used['vmem']))
                vmem_failcnt = self._get_memsw_failcnt(jobid)
                if vmem_failcnt is None:
                    pbs.logjobmsg(jobid, "%s: No vmem fail count data" %
                                  (caller_name()))
                else:
                    pbs.logjobmsg(jobid, "%s: vmem fail count: %d " %
                                  (caller_name(), vmem_failcnt))
                    if vmem_failcnt > 0:
                        err_msg = self._get_error_msg(jobid)
                        pbs.logjobmsg(jobid,
                                      "Cgroup memsw limit exceeded: %s" %
                                      (err_msg))
            elif subsys == "hugetlb":
                max_hpmem = self._get_max_hugetlb_usage(jobid)
                if max_hpmem is None:
                    pbs.logjobmsg(jobid, "%s: No max hpmem data" %
                                  (caller_name()))
                    return
                hpmem_failcnt = self._get_hugetlb_failcnt(jobid)
                if hpmem_failcnt is None:
                    pbs.logjobmsg(jobid, "%s: No hpmem fail count data" %
                                  (caller_name()))
                    return
                if hpmem_failcnt > 0:
                    err_msg = self._get_error_msg(jobid)
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
                cput = self._get_cpu_usage(jobid)
                if cput is None:
                    pbs.logjobmsg(jobid, "%s: No CPU usage data" %
                                  (caller_name()))
                    return
                cput = convert_time(str(cput) + "ns")
                resc_used['cput'] = pbs.duration(cput)
                pbs.logjobmsg(jobid, "%s: CPU usage: %.3lf secs" %
                              (caller_name(), cput))

    def create_job(self, jobid, node):
        """
        Creates the cgroup if it doesn't exists
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Iterate over the enabled subsystems
        for subsys in self.subsystems:
            # Create a directory for the job
            old_umask = os.umask(0022)
            try:
                path = self._cgroup_path(subsys, '', jobid)
                if not os.path.exists(path):
                    pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Creating directory %s" %
                               (caller_name(), path))
                    os.makedirs(path, 0755)
                if subsys == 'devices':
                    self._setup_subsys_devices(jobid, node)
            except OSError as exc:
                raise CgroupConfigError("Failed to create directory: %s (%s)" %
                                        (path, errno.errorcode[exc.errno]))
            except KeyboardInterrupt:
                raise
            except:
                raise
            finally:
                os.umask(old_umask)

    def configure_job(self, jobid, hostresc, node):
        """
        Determine the cgroup limits and configure the cgroups
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        mem_enabled = 'memory' in self.subsystems
        vmem_enabled = 'memsw' in self.subsystems
        if mem_enabled or vmem_enabled:
            # Initialize mem variables
            mem_avail = node.get_memory_on_node(self.cfg)
            pbs.logmsg(pbs.EVENT_DEBUG4, "mem_avail %s" % mem_avail)
            mem_requested = None
            if 'mem' in hostresc:
                mem_requested = convert_size(hostresc['mem'], 'kb')
            mem_default = None
            if mem_enabled:
                mem_default = self.default('memory')
            # Initialize vmem variables
            vmem_avail = node.get_vmem_on_node(self.cfg)
            pbs.logmsg(pbs.EVENT_DEBUG4, "vmem_avail %s" % vmem_avail)
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
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               ("%s: WARNING: vmem is enabled in the hook " +
                                "configuration file and should also be " +
                                "listed in the resources line of the " +
                                "scheduler configuration file") %
                               (caller_name()))
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
                except KeyboardInterrupt:
                    raise
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
                    time.sleep(0.5)
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
    def _kill_tasks(self, tasks_file, timeout=0):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        end = time.time() + timeout
        while True:
            count = 0
            with open(tasks_file, 'r') as tasks_desc:
                for line in tasks_desc:
                    count += 1
                    os.kill(int(line.strip()), signal.SIGKILL)
            if count == 0 or time.time() >= end:
                break
            else:
                time.sleep(0.1)
        if count == 0:
            return 0
        count = 0
        with open(tasks_file, 'r') as tasks_desc:
            for line in tasks_desc:
                count += 1
                pid = line.strip()
                filename = os.path.join(os.sep, 'proc', pid, 'status')
                statlist = []
                try:
                    with open(filename, 'r') as status_desc:
                        for line2 in status_desc:
                            if line2.find('Name:') != -1:
                                statlist.append(line2.strip())
                            if line2.find('State:') != -1:
                                statlist.append(line2.strip())
                            if line2.find('Uid:') != -1:
                                statlist.append(line2.strip())
                except KeyboardInterrupt:
                    raise
                except:
                    pass
                pbs.logmsg(pbs.EVENT_DEBUG2, "%s: PID %s survived: %s" %
                           (caller_name(), pid, statlist))
        return count

    # Perform the actual removal of the cgroup directory.
    # Make only one attempt at killing tasks in cgroup,
    # since this method could be called many times (for N
    # directories times M jobs).
    def _remove_cgroup(self, path, jobid, timeout=0, do_offline=True):
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
            remaining = self._kill_tasks(tasks_file, timeout)
        except KeyboardInterrupt:
            raise
        except:
            remaining = 0
        if remaining == 0:
            pbs.logmsg(pbs.EVENT_DEBUG2, "%s: Removing directory %s" %
                       (caller_name(), path))
            for _ in range(2):
                try:
                    with Timeout(2, 'Timed out removing cgroup %s' % (path)):
                        os.rmdir(path)
                except TimeoutError as exc:
                    pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s" %
                               (caller_name(), exc))
                except OSError as exc:
                    pbs.logmsg(pbs.EVENT_SYSTEM,
                               "OS error removing cgroup path: %s (%s)" %
                               (path, errno.errorcode[exc.errno]))
                except KeyboardInterrupt:
                    raise
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
            except KeyboardInterrupt:
                raise
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
                    with open(self.offline_file, 'w') as desc:
                        desc.write('Offlined %s\n' % time.strftime("%c"))
                except KeyboardInterrupt:
                    raise
                except:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               "Failed to write to %s" % self.offline_file)
                vnode.comment = self.offline_msg
                pbs.logmsg(pbs.EVENT_DEBUG2, self.offline_msg)
                if os.path.isfile(self.offline_file):
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               'Offlined: %s' % time.strftime("%c"))
                else:
                    pbs.logmsg(pbs.EVENT_DEBUG2,
                               'File not found: %s' % self.offline_file)
        return False

    def cleanup_orphans(self, local_jobs):
        """
        Removes cgroup directories that are not associated with a local job
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "Local jobs: %s" % (local_jobs))
        remaining = 0
        for key in self.paths:
            path = os.path.dirname(self._cgroup_path(key))
            for subdir in glob.glob(os.path.join(path, '[0-9]*')):
                jobid = os.path.basename(subdir)
                if jobid not in local_jobs:
                    if not jobid.endswith('-orphan'):
                        try:
                            os.rename(subdir, subdir + '-orphan')
                        except KeyboardInterrupt:
                            raise
                        except:
                            pass
            for subdir in glob.glob(os.path.join(path, '[0-9]*-orphan')):
                jobid = os.path.basename(subdir)
                pbs.logmsg(pbs.EVENT_DEBUG2,
                           "%s: Removing orphaned cgroup: %s" %
                           (caller_name(), subdir))
                if not self._remove_cgroup(subdir, jobid):
                    pbs.logmsg(pbs.EVENT_DEBUG,
                               "%s: Removing orphaned cgroup %s failed " %
                               (caller_name(), subdir))
                    remaining += 1
        return remaining

    def delete(self, jobid, do_offline=True):
        """
        Removes the cgroup directories for a job
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        # Make multiple attempts to kill tasks in the cgroup. Keep
        # trying for kill_timeout seconds.
        success = True
        for subsys in self.subsystems:
            path = self._cgroup_path(subsys, '', jobid)
            if not os.path.isdir(path):
                continue
            if success:
                success = self._remove_cgroup(path, jobid,
                                              self.cfg['kill_timeout'],
                                              do_offline)
            else:
                # Do not perform offline because of previous failure
                self._remove_cgroup(path, jobid)
        if not success:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       '%s: Unable to delete cgroup for job %s' %
                       (caller_name(), jobid))

    def write_value(self, filename, value, mode='w'):
        """
        Write a value to a limit file
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: writing %s to %s" %
                   (caller_name(), value, filename))
        try:
            with open(filename, mode) as desc:
                desc.write(str(value) + '\n')
        except IOError as exc:
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
        except KeyboardInterrupt:
            raise
        except:
            raise

    # Return memory failcount
    def _get_mem_failcnt(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self._cgroup_path('memory', 'failcnt', jobid),
                      'r') as desc:
                return int(desc.readline().strip())
        except KeyboardInterrupt:
            raise
        except:
            return None

    # Return vmem failcount
    def _get_memsw_failcnt(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self._cgroup_path('memsw', 'failcnt', jobid),
                      'r') as desc:
                return int(desc.readline().strip())
        except KeyboardInterrupt:
            raise
        except:
            return None

    # Return hpmem failcount
    def _get_hugetlb_failcnt(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self._cgroup_path('hugetlb', 'failcnt', jobid),
                      'r') as desc:
                return int(desc.readline().strip())
        except KeyboardInterrupt:
            raise
        except:
            return None

    # Return the max usage of memory in bytes
    def _get_max_mem_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self._cgroup_path('memory', 'max_usage_in_bytes',
                                        jobid), 'r') as desc:
                return int(desc.readline().strip())
        except KeyboardInterrupt:
            raise
        except:
            return None

    # Return the max usage of memsw in bytes
    def _get_max_memsw_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self._cgroup_path('memsw', 'max_usage_in_bytes', jobid),
                      'r') as desc:
                return int(desc.readline().strip())
        except KeyboardInterrupt:
            raise
        except:
            return None

    # Return the max usage of hugetlb in bytes
    def _get_max_hugetlb_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        try:
            with open(self._cgroup_path('hugetlb', 'max_usage_in_bytes',
                                        jobid),
                      'r') as desc:
                return int(desc.readline().strip())
        except KeyboardInterrupt:
            raise
        except:
            return None

    # Return the cpuacct.usage in cpu seconds
    def _get_cpu_usage(self, jobid):
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        path = self._cgroup_path('cpuacct', 'usage', jobid)
        try:
            with open(path, 'r') as desc:
                return int(desc.readline().strip())
        except KeyboardInterrupt:
            raise
        except:
            return None

    def select_cpus(self, path, ncpus):
        """
        Assign CPUs to the cpuset
        """
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
        with open(os.path.join(parent, cpufile), 'r') as desc:
            avail = expand_list(desc.read().strip())
        if len(avail) < 1:
            raise CgroupProcessingError("No CPUs avaialble in cgroup.")
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Available CPUs: %s" %
                   (caller_name(), avail))
        for filename in glob.glob(os.path.join(parent, '[0-9]*', cpufile)):
            if filename.endswith('-orphan'):
                continue
            with open(filename, 'r') as desc:
                cpus = expand_list(desc.read().strip())
            for entry in cpus:
                if entry in avail:
                    avail.remove(entry)
        if len(avail) < ncpus:
            raise CgroupProcessingError("Insufficient CPUs in cgroup.")
        if len(avail) == ncpus:
            return avail
        # TODO: Try to minimize NUMA nodes based on memory requirement
        return avail[:ncpus]

    # Return the error message in system message file
    def _get_error_msg(self, jobid):
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

    def write_cgroup_host_job_env_file(self, jobid, env_list):
        """
        Write out host cgroup environment for this job
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        if not os.path.exists(self.host_job_env_dir):
            os.makedirs(self.host_job_env_dir, 0755)
        # Write out assigned_resources
        try:
            lines = string.join(env_list, '\n')
            filename = self.host_job_env_filename % jobid
            with open(filename, 'w') as desc:
                desc.write(lines)
            pbs.logmsg(pbs.EVENT_DEBUG4, "Wrote out file: %s" % (filename))
            pbs.logmsg(pbs.EVENT_DEBUG4, "Data: %s" % (lines))
            return True
        except KeyboardInterrupt:
            raise
        except:
            return False

    def write_cgroup_assigned_resources(self, jobid):
        """
        Write out host cgroup assigned resources for this job
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        if not os.path.exists(self.hook_storage_dir):
            os.makedirs(self.hook_storage_dir, 0755)
        # Write out assigned_resources
        try:
            json_str = json.dumps(self.assigned_resources)
            filename = os.path.join(self.hook_storage_dir, jobid)
            with open(filename, 'w') as desc:
                desc.write(json_str)
            pbs.logmsg(pbs.EVENT_DEBUG4, "Wrote out file: %s" %
                       (os.path.join(self.hook_storage_dir, jobid)))
            pbs.logmsg(pbs.EVENT_DEBUG4, "Data: %s" % (json_str))
            return True
        except KeyboardInterrupt:
            raise
        except:
            return False

    def read_cgroup_assigned_resources(self, jobid):
        """
        Read assigned resources from job file stored in hook storage area
        """
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Method called" % (caller_name()))
        jobid = str(jobid)
        pbs.logmsg(pbs.EVENT_DEBUG4, "Host assigned resources: %s" %
                   (self.assigned_resources))
        hrfile = os.path.join(self.hook_storage_dir, jobid)
        if os.path.isfile(hrfile):
            # Read in assigned_resources
            try:
                with open(hrfile, 'r') as desc:
                    json_data = json.load(desc, object_hook=decode_dict)
                self.assigned_resources = json_data
                pbs.logmsg(pbs.EVENT_DEBUG4,
                           "Host assigned resources: %s" %
                           (self.assigned_resources))
            except IOError:
                raise CgroupConfigError("I/O error reading config file")
            except json.JSONDecodeError:
                raise CgroupConfigError(
                    "JSON parsing error reading config file")
            except KeyboardInterrupt:
                raise
            except:
                raise
        return self.assigned_resources is not None


def set_global_vars():
    """
    Define some global variables that the hook may use
    """
    global PBS_EXEC
    global PBS_HOME
    global PBS_MOM_HOME
    # Determine location of PBS_HOME, PBS_MOM_HOME, and PBS_EXEC. These
    # should have each be initialized to empty strings near the beginning
    # of this hook.
    # Try the environment first
    if not PBS_EXEC and 'PBS_EXEC' in os.environ:
        PBS_EXEC = os.environ['PBS_EXEC']
    if not PBS_HOME and 'PBS_HOME' in os.environ:
        PBS_HOME = os.environ['PBS_HOME']
    if not PBS_MOM_HOME and 'PBS_MOM_HOME' in os.environ:
        PBS_MOM_HOME = os.environ['PBS_MOM_HOME']
    # Try the built in config values next
    pbs_conf = pbs.get_pbs_conf()
    if pbs_conf:
        if not PBS_EXEC and 'PBS_EXEC' in pbs_conf:
            PBS_EXEC = pbs_conf['PBS_EXEC']
        if not PBS_HOME and 'PBS_HOME' in pbs_conf:
            PBS_HOME = pbs_conf['PBS_HOME']
        if not PBS_MOM_HOME and 'PBS_MOM_HOME' in pbs_conf:
            PBS_MOM_HOME = pbs_conf['PBS_MOM_HOME']
    # Try reading the config file directly
    if not PBS_EXEC or not PBS_HOME or not PBS_MOM_HOME:
        if 'PBS_CONF_FILE' in os.environ:
            pbs_conf_file = os.environ['PBS_CONF_FILE']
        else:
            pbs_conf_file = os.path.join(os.sep, 'etc', 'pbs.conf')
        regex = re.compile(r'\s*([^\s]+)\s*=\s*([^\s]+)\s*')
        try:
            with open(pbs_conf_file, 'r') as desc:
                for line in desc:
                    match = regex.match(line)
                    if match:
                        if not PBS_EXEC and match.group(1) == 'PBS_EXEC':
                            PBS_EXEC = match.group(2)
                        if not PBS_HOME and match.group(1) == 'PBS_HOME':
                            PBS_HOME = match.group(2)
                        if not PBS_MOM_HOME and (match.group(1) ==
                                                 'PBS_MOM_HOME'):
                            PBS_MOM_HOME = match.group(2)
        except KeyboardInterrupt:
            raise
        except:
            pass
    # If PBS_MOM_HOME is not set, use the PBS_HOME value
    if not PBS_MOM_HOME:
        PBS_MOM_HOME = PBS_HOME
    # Sanity check to make sure each global path is set
    if not PBS_EXEC:
        raise CgroupConfigError("Unable to determine PBS_EXEC.")
    if not PBS_HOME:
        raise CgroupConfigError("Unable to determine PBS_HOME.")
    if not PBS_MOM_HOME:
        raise CgroupConfigError("Unable to determine PBS_MOM_HOME.")


#
# FUNCTION main
#
def main():
    """
    Main function for execution
    """
    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Function called" % (caller_name()))
    # If an exception occurs, jobutil must be set to something
    jobutil = None
    hostname = pbs.get_local_nodename()
    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Host is %s" % (caller_name(), hostname))
    # Log the hook event type
    event = pbs.event()
    pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Hook name is %s" %
               (caller_name(), event.hook_name))
    try:
        set_global_vars()
    except KeyboardInterrupt:
        raise
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "%s: Hook failed to initialize configuration properly" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        event.accept()
    # Instantiate the hook utility class
    try:
        hooks = HookUtils()
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Event type is %s" %
                   (caller_name(), hooks.event_name(event.type)))
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Hook utility class instantiated" %
                   (caller_name()))
    except KeyboardInterrupt:
        raise
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   "%s: Failed to instantiate hook utility class" %
                   (caller_name()))
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        event.accept()
    # Bail out if there is no handler for this event
    if not hooks.hashandler(event.type):
        pbs.logmsg(pbs.EVENT_DEBUG, "%s: %s event not handled by this hook" %
                   (caller_name(), hooks.event_name(event.type)))
        event.accept()
    try:
        # Instantiate the job utility class first so jobutil can be accessed
        # by the exception handlers.
        if hasattr(event, 'job'):
            jobutil = JobUtils(event.job)
            pbs.logmsg(pbs.EVENT_DEBUG4,
                       "%s: Job information class instantiated" %
                       (caller_name()))
        else:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Event does not include a job" %
                       (caller_name()))
        # Instantiate the cgroup utility class
        vnode = None
        if hasattr(event, 'vnode_list'):
            if hostname in event.vnode_list:
                vnode = event.vnode_list[hostname]
        cgroup = CgroupUtils(hostname, vnode)
        pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Cgroup utility class instantiated" %
                   (caller_name()))
        # Bail out if there is nothing to do
        if not cgroup.subsystems:
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "%s: Cgroups disabled or none to manage" %
                       (caller_name()))
            event.accept()
        # Call the appropriate handler
        if hooks.invoke_handler(event, cgroup, jobutil) is True:
            pbs.logmsg(pbs.EVENT_DEBUG4, "%s: Hook handler returned success" %
                       (caller_name()))
            event.accept()
        else:
            pbs.logmsg(pbs.EVENT_DEBUG, "%s: Hook handler returned failure" %
                       (caller_name()))
            event.reject()
    except SystemExit:
        # The event.accept() and event.reject() methods generate a SystemExit
        # exception.
        pass
    except AdminError as exc:
        # Something on the system is misconfigured
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("Admin error in %s handling %s event" %
               (event.hook_name, hooks.event_name(event.type)))
        if jobutil is not None:
            msg += (" for job %s" % (event.job.id))
            try:
                event.job.Hold_Types = pbs.hold_types("s")
                event.job.rerun()
                msg += " (held)"
            except KeyboardInterrupt:
                raise
            except:
                msg += " (hold failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        event.reject(msg)
    except JobValueError as exc:
        # Something in PBS is misconfigured
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("Job value error in %s handling %s event" %
               (event.hook_name, hooks.event_name(event.type)))
        if jobutil is not None:
            msg += (" for job %s" % (event.job.id))
            try:
                event.job.Hold_Types = pbs.hold_types("s")
                event.job.rerun()
                msg += " (held)"
            except KeyboardInterrupt:
                raise
            except:
                msg += " (hold failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        event.reject(msg)
    except UserError as exc:
        # User must correct problem and resubmit job
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("User error in %s handling %s event" %
               (event.hook_name, hooks.event_name(event.type)))
        if jobutil is not None:
            msg += (" for job %s" % (event.job.id))
            try:
                event.job.delete()
                msg += " (deleted)"
            except KeyboardInterrupt:
                raise
            except:
                msg += " (delete failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        event.reject(msg)
    except Exception as exc:
        # Catch all other exceptions and report them.
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
        msg = ("Unexpected error in %s handling %s event" %
               (event.hook_name, hooks.event_name(event.type)))
        if jobutil is not None:
            msg += (" for job %s" % (event.job.id))
            try:
                event.job.Hold_Types = pbs.hold_types("s")
                event.job.rerun()
                msg += " (held)"
            except KeyboardInterrupt:
                raise
            except:
                msg += " (hold failed)"
        msg += (": %s %s" % (exc.__class__.__name__, str(exc.args)))
        pbs.logmsg(pbs.EVENT_ERROR, msg)
        event.reject(msg)

# The following block is skipped if this is a unit testing environment.
if __name__ == "__builtin__":
    START = time.time()
    try:
        main()
    except SystemExit:
        # The event.accept() and event.reject() methods generate a SystemExit
        # exception.
        pass
    except:
        pbs.logmsg(pbs.EVENT_DEBUG,
                   str(traceback.format_exc().strip().splitlines()))
    finally:
        pbs.logmsg(pbs.EVENT_DEBUG, "Elapsed time: %0.4lf" %
                   (time.time() - START))

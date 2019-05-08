# coding: utf-8

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

"""
PBS Professional hook for consuming the Shasta Northbound API.

This hook services the following events:
- execjob_begin
- execjob_end
"""


import sys
import os
import json
import urllib
import signal
import time
import site
import requests
import requests_unixsocket  # referred as R-US
import pbs
import pwd
import copy

requests_unixsocket.monkeypatch()

# ============================================================================
# Utility functions
# ============================================================================


class OfflineError(Exception):
    """
    Exception that will offline the node and reject the event
    """
    pass


class RejectError(Exception):
    """
    Exception that will reject the event
    """
    pass


class TimedoutError(Exception):
    """
    Timeout encountered.
    """
    pass


class Timeout(object):
    """
    Implement a timeout mechanism via SIGALRM
    """

    def __init__(self, duration=1, message='Operation timed out'):
        self.duration = duration
        self.message = message

    def handler(self, sig, frame):
        """
        Throw a timeout error when SIGALRM is received
        """
        raise TimedoutError(self.message)

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
            raise RuntimeError('Alarm handler already registered')
        signal.signal(signal.SIGALRM, self.handler)
        signal.alarm(self.duration)

    def __exit__(self, exc, val, trace):
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)


class HookHelper(object):
    """
    Helper to load config and event
    """
    config = None
    event = None

    def __init__(self):
        raise Exception('Access class via static methods')

    @classmethod
    def load_config(cls):
        """
        Read the config file
        """
        log_function_name()
        defaults = {
            'apconfig': {
                'beginjob_timeout': 30,
                'unix_socket_file': '/var/run/jacsd/jacsd.sock',

                # the following are hidden
                'version_uri': '/rm/v1',
                'resource_name': '/compute/jobs',
            },
            'healthcheck': {
                'enabled': True,
                'interval': .4,
                'unix_socket_file': '/var/run/hatsd/hatsd.sock',

                # the following are hidden
                'version_uri': '/nhc/v1',
                'resource_name': '/healthchecks'
            },
        }
        # Identify the config file and read in the data
        config_file = ''
        if 'PBS_HOOK_CONFIG_FILE' in os.environ:
            config_file = os.environ['PBS_HOOK_CONFIG_FILE']
        else:
            raise RuntimeError('%s: No config file set' % caller_name())
        pbs.logmsg(pbs.EVENT_DEBUG3, 'config file is %s' % config_file)
        try:
            with open(config_file, 'r') as cfg:
                config = merge_dict(defaults, json.load(cfg))
        except IOError:
            raise IOError('I/O error reading config file')
        pbs.logmsg(pbs.EVENT_DEBUG, 'loaded config is: %s' % (str(config)))
        cls.config = config

    @classmethod
    def get_event(cls):
        """
        Fetch the event if it hasn't already been fetched.
        Return the event
        """
        if not cls.event:
            cls.event = pbs.event()
        return cls.event

    @classmethod
    def get_config(cls):
        """
        Load the config if it hasn't already been loaded.
        Return the config
        """
        if not cls.config:
            cls.load_config()
        pbs.logmsg(pbs.EVENT_DEBUG, '%s' % (str(cls.config)))
        return cls.config

    @staticmethod
    def build_path(config, jobid=None):
        """
        Given a jobid and a config type build the path.
        If jobid is none, build a path to the collection
        R-US requires the socket path to be percent-encoded
        """
        log_function_name()
        cfg = HookHelper.get_config()

        if config not in cfg:
            pbs.logmsg(pbs.EVENT_DEBUG, '%s: Invalid config type %s' %
                       (caller_name(), config))
            raise RejectError()

        # urllib.quote will have to be changed to urllib.parse.quote with Py3
        path = 'http+unix://%s%s%s%s' % (
            urllib.quote(cfg[config]['unix_socket_file'], safe=''),
            cfg[config]['version_uri'],
            cfg[config]['resource_name'],
            ('/' + jobid) if jobid else ''
        )
        pbs.logmsg(pbs.EVENT_DEBUG, 'path is %s' % path)
        return path


def caller_name(frames=1):
    """
    Return the name of the nth calling function or method.
    """
    return str(sys._getframe(frames).f_code.co_name)


def log_function_name():
    """
    Log the caller's name
    """
    pbs.logmsg(pbs.EVENT_DEBUG4, '%s: Method called' % caller_name(2))


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


def handle_execjob_end():
    """
    Handler for execjob_end events.
    """
    log_function_name()
    jid = HookHelper.get_event().job.id
    url = HookHelper.build_path(config='apconfig', jobid=jid)
    r = requests.delete(url)
    pbs.logmsg(pbs.EVENT_DEBUG, '%s:%s:DELETE-RECV: status[%d]' %
               (caller_name(), jid, r.status_code))
    try:
        r.raise_for_status()
    except requests.HTTPError:
        pbs.logmsg(pbs.EVENT_DEBUG, '%s:DELETE job failed, skip healthcheck' %
                   (caller_name()))
        raise RejectError('Job delete failed')

    if not HookHelper.get_config()['healthcheck']['enabled']:
        return

    url = HookHelper.build_path(config='healthcheck')
    data = {
        'jobid': jid,
        'jobExitCode': HookHelper.get_event().job.Exit_status,
        'testSet': 'job'
    }
    r = requests.post(url, json=data)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        pbs.logmsg(pbs.EVENT_DEBUG, '%s:POST Healthcheck failed' %
                   (caller_name()))
        raise RejectError('POST Healthcheck failed')
    hcid = r.json()['hcid']
    get_url = HookHelper.build_path(config='healthcheck', jobid=hcid)

    # This will loop until the hook alarm triggers
    # or the healthcheck is complete.
    while True:
        r = requests.get(get_url)
        if r.status_code not in (200, 202):
            pbs.logmsg(pbs.EVENT_DEBUG, '%s: Invalid status code %d' %
                       (caller_name(), r.status_code))
            raise RejectError()
        if r.status_code == 202:
            time.sleep(HookHelper.get_config()['healthcheck']['interval'])
            continue
        response = r.json()
        # status code must be 200 here.
        if response['failedTests']:
            pbs.logmsg(pbs.EVENT_DEBUG, '%s: The following tests failed: %s' %
                       (caller_name(), str(response['failedTests'])))
            raise OfflineError()
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3, '%s: All tests passed!' %
                       (caller_name()))
            return


def handle_execjob_begin():
    """
    Handler for execjob_begin events.
    """
    log_function_name()
    event = HookHelper.get_event()
    jid = event.job.id
    for _, v in event.vnode_list.items():
        pbs.logmsg(pbs.EVENT_DEBUG, "vnodes assigned to job %s | %s" %
                   (jid, v.name))
    uid = pwd.getpwnam(event.job.euser).pw_uid
    pbs.logmsg(pbs.EVENT_DEBUG, 'UID is %d' % uid)
    data = {
        'jobid': jid,
        'uid': uid
    }
    url = HookHelper.build_path(config='apconfig')
    r = requests.post(url, json=data, timeout=10)
    pbs.logmsg(pbs.EVENT_DEBUG, 'data %s' % json.dumps(data))
    pbs.logmsg(pbs.EVENT_DEBUG, 'text %s' % r.text)
    pbs.logmsg(pbs.EVENT_DEBUG, "%s: Received status code = %s" %
               (jid, r.status_code))
    pbs.logmsg(pbs.EVENT_DEBUG, "%s" % r.json())
    if r.status_code != requests.codes['ok']:
        pbs.logmsg(pbs.EVENT_DEBUG, '%s: Invalid status code %d' %
                   (caller_name(), r.status_code))
        raise RejectError()
    msg = "%s:%s: POST-RECV: status=[%d]" % \
        (caller_name(), jid, r.status_code)
    msg += " data=%s" % r.json()
    pbs.logmsg(pbs.EVENT_DEBUG, msg)


def main():
    """
    Main function for execution
    """
    log_function_name()
    hostname = pbs.get_local_nodename()
    pbs.logmsg(pbs.EVENT_DEBUG4, '%s: Host is %s' % (caller_name(), hostname))
    # Log the hook event type
    event = HookHelper.get_event()
    pbs.logmsg(pbs.EVENT_DEBUG4, '%s: Hook name is %s' %
               (caller_name(), event.hook_name))

    handlers = {
        pbs.EXECJOB_END: handle_execjob_end,
        pbs.EXECJOB_BEGIN: handle_execjob_begin
    }

    handler = handlers[event.type]
    if not handler:
        pbs.logmsg(pbs.EVENT_DEBUG, '%s: %s event is not handled by this hook'
                   % (caller_name(), event.type))
        event.accept()
    handler()


if __name__ == '__builtin__':
    START = time.time()
    try:
        main()
    except SystemExit:
        # The event.accept() and event.reject() methods generate a
        # SystemExit exception
        pass
    except OfflineError:
        vnode = HookHelper.get_event().vnode_list[pbs.get_local_nodename()]
        vnode.state = pbs.ND_OFFLINE
        vnode.comment = 'Node offlined due to Health Check Failure'
        HookHelper.get_event().reject()
    except RejectError:
        HookHelper.get_event().reject()
    finally:
        pbs.logmsg(pbs.EVENT_DEBUG, 'Elapsed time: %0.4lf' %
                   (time.time() - START))

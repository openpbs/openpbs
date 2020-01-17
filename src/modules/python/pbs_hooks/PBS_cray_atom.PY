# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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
import json as JSON
import urllib
import site
site.main()
import requests
import requests_unixsocket
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


class HookHelper(object):
    """
    Helper to load config and event
    """
    config = None

    def __init__(self):
        raise Exception('Access class via static methods')

    @classmethod
    def load_config(cls):
        """
        Read the config file
        """
        log_function_name()
        defaults = {
            'post_timeout': 30,
            'delete_timeout': 30,
            'unix_socket_file': '/var/run/atomd/atomd.sock',
        }
        constants = {
            'version_uri': '/rm/v1',
            'resources': {
                'job': '/jobs',
                'task': '/tasks'
            }
        }
        # Identify the config file and read in the data
        config_file = ''
        if 'PBS_HOOK_CONFIG_FILE' in os.environ:
            config_file = os.environ['PBS_HOOK_CONFIG_FILE']
        else:
            raise RuntimeError('%s: No config file set' % caller_name())
        pbs.logmsg(pbs.EVENT_DEBUG4, 'config file is %s' % config_file)
        try:
            with open(config_file, 'r') as cfg:
                config = merge_dict(defaults, JSON.load(cfg))
        except IOError:
            raise IOError('I/O error reading config file')
        config = merge_dict(config, constants)
        pbs.logmsg(pbs.EVENT_DEBUG4, 'loaded config is: %s' % (str(config)))
        cls.config = config

    @classmethod
    def validate_config(cls):
        """
        Validate the config file
        This will check if the unix_socket_file resolves to a file.
        """
        if not os.path.exists(cls.get_config()['unix_socket_file']):
            log_with_caller(pbs.EVENT_DEBUG4,
                            'Unix socket file does not exist, skipping hook',
                            jobid=False)
            pbs.event().accept()

    @classmethod
    def get_config(cls):
        """
        Load the config if it hasn't already been loaded.
        Return the config
        """
        if not cls.config:
            cls.load_config()
            cls.validate_config()
        return cls.config

    @staticmethod
    def build_path(resource, jobid=None):
        """
        Given a jobid and a resource type build the path.
        If jobid is none, build a path to the collection
        requests_unixsockets requires the socket path to be percent-encoded
        """
        log_function_name()
        cfg = HookHelper.get_config()

        if resource not in cfg['resources']:
            log_with_caller(pbs.EVENT_ERROR, 'Invalid resource type %s' %
                            resource, jobid=False)
            raise RejectError()

        path = 'http+unix://%s%s%s%s' % (
            urllib.parse.quote(cfg['unix_socket_file'], safe=''),
            cfg['version_uri'],
            cfg['resources'][resource],
            ('/' + jobid) if jobid else ''
        )
        log_with_caller(pbs.EVENT_DEBUG4, 'path is %s' % path)
        return path


def post(url, json=None, **kwargs):
    """
    Wrapper to requests.post

    Logs before and after
    """
    log_with_caller(pbs.EVENT_DEBUG2, 'Sending POST to %s' % url, caller=1)
    log_with_caller(pbs.EVENT_DEBUG2, 'Sending POST JSON: %s' %
                    JSON.dumps(json), caller=1)
    r = requests.post(url, json=json, **kwargs)
    log_with_caller(pbs.EVENT_DEBUG2, 'Received POST status code = %s' %
                    r.status_code, caller=1)
    log_with_caller(pbs.EVENT_DEBUG2, 'Received POST text %s' %
                    r.text, caller=1)
    return r


def get(url, params=None, **kwargs):
    """
    Wrapper to requests.get

    Logs before and after
    """
    log_with_caller(pbs.EVENT_DEBUG2, 'Sending GET to %s' % url, caller=1)
    if params:
        log_with_caller(pbs.EVENT_DEBUG2,
                        'Sending GET params: %s' % params, caller=1)
    r = requests.get(url, params=params, **kwargs)
    log_with_caller(pbs.EVENT_DEBUG2, 'Received GET status code = %s' %
                    r.status_code, caller=1)
    log_with_caller(pbs.EVENT_DEBUG2, 'Received GET text %s' %
                    r.text, caller=1)
    return r


def delete(url, **kwargs):
    """
    Wrapper to requests.delete

    Logs before and after
    """
    log_with_caller(pbs.EVENT_DEBUG2, 'Sending DELETE to %s' % url, caller=1)
    r = requests.delete(url, **kwargs)
    log_with_caller(pbs.EVENT_DEBUG2, 'Received DELETE status code = %s' %
                    r.status_code, caller=1)
    log_with_caller(pbs.EVENT_DEBUG2, 'Received DELETE text %s' %
                    r.text, caller=1)
    return r


def caller_name(frames=1):
    """
    Return the name of the nth calling function or method.
    """
    return str(sys._getframe(frames).f_code.co_name)


def log_function_name():
    """
    Log the caller's name
    """
    pbs.logmsg(pbs.EVENT_DEBUG4, '%s:%s: Method called' %
               (pbs.event().hook_name, caller_name(2)))


def log_with_caller(sev, mes, caller=0, jobid=True):
    """
    Wrapper to pbs.logmsg with caller's name prepended

    Increment caller to get the caller of the calling function

    If jobid is true, add the jobid from the event to the log message
    """
    if jobid:
        pbs.logmsg(sev, '%s:%s:%s: %s' %
                   (pbs.event().hook_name, pbs.event().job.id,
                    caller_name(2 + caller), mes))
    else:
        pbs.logmsg(sev, '%s:%s: %s' %
                   (pbs.event().hook_name, caller_name(2 + caller), mes))


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


def retry_post(data):
    """
    In the case where a POST fails due to a 400 error,
    it could be because there is already a job on the cray side.
    In that case, we should try to delete the existing job and
    resubmit a new one.

    If a previous POST timedout so we rejected it, but the service
    just took too long to respond, it would exist on the service.
    """
    event = pbs.event()
    jid = event.job.id

    joburl = HookHelper.build_path(resource='job', jobid=jid)
    del_timeout = HookHelper.get_config()['delete_timeout']
    try:
        r_del = delete(joburl, timeout=del_timeout)
        r_del.raise_for_status()
    except requests.Timeout:
        log_with_caller(pbs.EVENT_ERROR, 'DELETE timed out')
        raise OfflineError('Job delete timed out')
    except requests.HTTPError:
        # If 404, then maybe the job that was there is now gone,
        # try posting again. Otherwise, raise an OfflineError
        if r_del.status_code != 404:
            log_with_caller(pbs.EVENT_ERROR, 'DELETE job failed')
            raise OfflineError('Job delete failed')

    url = HookHelper.build_path(resource='job')
    post_timeout = HookHelper.get_config()['post_timeout']
    try:
        r_post = post(url, json=data, timeout=post_timeout)
        r_post.raise_for_status()
    except requests.Timeout:
        log_with_caller(pbs.EVENT_ERROR, 'POST timed out')
        raise OfflineError('Job POST timed out')
    except requests.HTTPError:
        log_with_caller(pbs.EVENT_ERROR,
                        'Invalid status code %d' % r_post.status_code)
        raise OfflineError('Job POST encountered invalid status code')

    # if we got here, we've successfully deleted and re-posted the job
    log_with_caller(pbs.EVENT_DEBUG, 'Job %s registered' % jid)
    return


def handle_execjob_begin():
    """
    Handler for execjob_begin events.
    """
    log_function_name()
    event = pbs.event()
    jid = event.job.id
    uid = pwd.getpwnam(event.job.euser).pw_uid
    log_with_caller(pbs.EVENT_DEBUG4, 'UID is %d' % uid)
    data = {
        'jobid': jid,
        'uid': uid
    }
    url = HookHelper.build_path(resource='job')
    timeout = HookHelper.get_config()['post_timeout']
    try:
        r = post(url, json=data, timeout=timeout)
        r.raise_for_status()
    except requests.Timeout:
        log_with_caller(pbs.EVENT_ERROR, 'POST timed out')
        raise OfflineError('Job POST timed out')
    except requests.HTTPError:
        if r.status_code == 400:
            retry_post(data)
        else:
            log_with_caller(pbs.EVENT_ERROR, 'Invalid status code %d' %
                            r.status_code)
            raise OfflineError('Job POST encountered invalid status code')
    log_with_caller(pbs.EVENT_DEBUG, 'Job %s registered' % jid)


def handle_execjob_end():
    """
    Handler for execjob_end events.
    """
    log_function_name()
    jid = pbs.event().job.id
    url = HookHelper.build_path(resource='job', jobid=jid)
    timeout = HookHelper.get_config()['delete_timeout']
    try:
        r = delete(url, timeout=timeout)
        r.raise_for_status()
    except requests.Timeout:
        log_with_caller(pbs.EVENT_ERROR, 'DELETE timed out')
        raise RejectError('Job delete timed out')
    except requests.HTTPError:
        log_with_caller(pbs.EVENT_ERROR, 'DELETE job failed')
        raise RejectError('Job delete failed')

    log_with_caller(pbs.EVENT_DEBUG, 'Job %s deleted' % jid)


def main():
    """
    Main function for execution
    """
    log_function_name()
    hostname = pbs.get_local_nodename()
    # Log the hook event type
    event = pbs.event()

    handlers = {
        pbs.EXECJOB_BEGIN: (handle_execjob_begin, OfflineError),
        pbs.EXECJOB_END: (handle_execjob_end, RejectError)
    }

    handler, timeout_exc = handlers.get(event.type, (None, None))
    if not handler:
        log_with_caller(pbs.EVENT_ERROR, '%s event is not handled by this hook'
                        % event.type, jobid=False)
        event.accept()
    try:
        handler()
    except KeyboardInterrupt:
        raise timeout_exc('Handler alarmed')


if __name__ == 'builtins':
    try:
        main()
    except OfflineError as e:
        for v in pbs.event().vnode_list.keys():
            vnode = pbs.event().vnode_list[v]
            vnode.state = pbs.ND_OFFLINE
            vnode.comment = '%s: vnode set to offline: %s' % (
                pbs.event().hook_name, e.message)
        pbs.event().reject()
    except RejectError:
        pbs.event().reject()

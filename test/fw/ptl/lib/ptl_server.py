# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


import ast
import base64
import collections
import copy
import datetime
import grp
import json
import logging
import os
import pickle
import pwd
import random
import re
import socket
import string
import sys
import tempfile
import threading
import time
import traceback
from collections import OrderedDict
from distutils.version import LooseVersion
from operator import itemgetter

from ptl.lib.pbs_api_to_cli import api_to_cli
from ptl.utils.pbs_cliutils import CliUtils
from ptl.utils.pbs_dshutils import DshUtils, PtlUtilError
from ptl.utils.pbs_procutils import ProcUtils
from ptl.utils.pbs_testusers import (ROOT_USER, TEST_USER, PbsUser,
                                     DAEMON_SERVICE_USER)

try:
    import psycopg2
    PSYCOPG = True
except:
    PSYCOPG = False

try:
    from ptl.lib.pbs_ifl import *
    API_OK = True
except:
    try:
        from ptl.lib.pbs_ifl_mock import *
    except:
        sys.stderr.write("failed to import pbs_ifl, run pbs_swigify " +
                         "to make it\n")
        raise ImportError
    API_OK = False

from ptl.lib.ptl_expect_action import *
from ptl.lib.ptl_error import *
from ptl.lib.ptl_batchutils import *
from ptl.lib.ptl_types import *
from ptl.lib.ptl_object import *
from ptl.lib.ptl_service import *
from ptl.lib.ptl_resources import *
from ptl.lib.ptl_job import *


def get_server_obj(name=None, attrs={}, defaults={}, pbsconf_file=None,
                   snapmap={}, snap=None, client=None,
                   client_pbsconf_file=None, db_access=None, stat=True):
    return Server(name, attrs, defaults, pbsconf_file, snapmap, snap, client,
                  client_pbsconf_file, db_access, stat)

from ptl.lib.ptl_mom import get_mom_obj
from ptl.lib.ptl_sched import get_sched_obj
from ptl.lib.pbs_testlib import *


class Server(PBSService):

    """
    PBS server ``configuration`` and ``control``

    The Server class is a container to PBS server attributes
    and implements wrappers to the ``IFL API`` to perform
    operations on the server. For example to submit, status,
    delete, manage, etc... jobs, reservations and configurations.

    This class also offers higher-level routines to ease testing,
    see functions, for ``example: revert_to_defaults,
    init_logging, expect, counter.``

    :param name: The hostname of the server. Defaults to
                 calling pbs_default()
    :type name: str
    :param attrs: Dictionary of attributes to set, these will
                  override defaults.
    :type attrs: Dictionary
    :param defaults: Dictionary of default attributes.
                     Default: dflt_attributes
    :type defaults: Dictionary
    :param pbsconf_file: path to config file to parse for PBS_HOME,
                         PBS_EXEC, etc
    :type pbsconf_file: str
    :param snapmap: A dictionary of PBS objects (node,server,etc)
                    to mapped files from PBS snap directory
    :type snapmap: Dictionary
    :param snap: path to PBS snap directory (This will overrides
                 snapmap)
    :type snap: str
    :param client: The host to use as client for CLI queries.
                   Defaults to the local hostname.
    :type client: str
    :param client_pbsconf_file: The path to a custom PBS_CONF_FILE
                                on the client host. Defaults to
                                the same path as pbsconf_file.
    :type client_pbsconf_file: str
    :param db_acccess: set to either file containing credentials
                       to DB access or dictionary containing
                       {'dbname':...,'user':...,'port':...}
    :param stat: if True, stat the server attributes
    :type stat: bool
    """

    dflt_attributes = {
        ATTR_dfltque: "workq",
        ATTR_nodefailrq: "310",
        ATTR_FlatUID: 'True',
        ATTR_DefaultChunk + ".ncpus": "1",
    }

    dflt_sched_name = 'default'

    # this pattern is a bit relaxed to match common developer build numbers
    version_tag = re.compile(r"[a-zA-Z_]*(?P<version>[\d\.]+.[\w\d\.]*)[\s]*")

    actions = ExpectActions()

    def __init__(self, name=None, attrs={}, defaults={}, pbsconf_file=None,
                 snapmap={}, snap=None, client=None, client_pbsconf_file=None,
                 db_access=None, stat=True):
        self.jobs = {}
        self.nodes = {}
        self.reservations = {}
        self.queues = {}
        self.resources = {}
        self.hooks = {}
        self.pbshooks = {}
        self.entities = {}
        self.schedulers = {}
        self.version = None
        self.default_queue = None
        self.last_error = []  # type: array. Set for CLI IFL errors. Not reset
        self.last_out = []  # type: array. Set for CLI IFL output. Not reset
        self.last_rc = None  # Set for CLI IFL return code. Not thread-safe
        self.moms = {}

        # default timeout on connect/disconnect set to 60s to mimick the qsub
        # buffer introduced in PBS 11
        self._conn_timeout = 60
        self._conn_timer = None
        self._conn = None
        self._db_conn = None
        self.current_user = pwd.getpwuid(os.getuid())[0]

        if len(defaults.keys()) == 0:
            defaults = self.dflt_attributes

        self.pexpect_timeout = 15
        self.pexpect_sleep_time = .1

        PBSService.__init__(self, name, attrs, defaults, pbsconf_file, snapmap,
                            snap)
        _m = ['server ', self.shortname]
        if pbsconf_file is not None:
            _m += ['@', pbsconf_file]
        _m += [': ']
        self.logprefix = "".join(_m)
        self.pi = PBSInitServices(hostname=self.hostname,
                                  conf=self.pbs_conf_file)
        self.set_client(client)

        if client_pbsconf_file is None:
            self.client_pbs_conf_file = self.du.get_pbs_conf_file(self.client)
        else:
            self.client_pbs_conf_file = client_pbsconf_file

        self.client_conf = self.du.parse_pbs_config(
            self.client, file=self.client_pbs_conf_file)

        if self.client_pbs_conf_file == '/etc/pbs.conf':
            self.default_client_pbs_conf = True
        elif (('PBS_CONF_FILE' not in os.environ) or
              (os.environ['PBS_CONF_FILE'] != self.client_pbs_conf_file)):
            self.default_client_pbs_conf = False
        else:
            self.default_client_pbs_conf = True

        a = {}
        if os.getuid() == 0:
            a = {ATTR_aclroot: 'root'}
        self.dflt_attributes.update(a)

        if not API_OK:
            # mode must be set before the first stat call
            self.set_op_mode(PTL_CLI)

        if stat:
            try:
                tmp_attrs = self.status(SERVER, level=logging.DEBUG,
                                        db_access=db_access)
            except (PbsConnectError, PbsStatusError):
                tmp_attrs = None

            if tmp_attrs is not None and len(tmp_attrs) > 0:
                self.attributes = tmp_attrs[0]

            if ATTR_dfltque in self.attributes:
                self.default_queue = self.attributes[ATTR_dfltque]

            self.update_version_info()

    def update_version_info(self):
        """
        Update the version information.
        """
        if ATTR_version not in self.attributes:
            self.attributes[ATTR_version] = 'unknown'
        else:
            m = self.version_tag.match(self.attributes[ATTR_version])
            if m:
                v = m.group('version')
                self.version = LooseVersion(v)
        self.logger.info(self.logprefix + 'version ' +
                         self.attributes[ATTR_version])

    def set_client(self, name=None):
        """
        Set server client

        :param name: Client name
        :type name: str
        """
        if name is None:
            self.client = socket.gethostname()
        else:
            self.client = name

    def _connect(self, hostname, attempt=1):
        if ((self._conn is None or self._conn < 0) or
                (self._conn_timeout == 0 or self._conn_timer is None)):
            self._conn = pbs_connect(hostname)
            self._conn_timer = time.time()

        if self._conn is None or self._conn < 0:
            if attempt > 5:
                m = self.logprefix + 'unable to connect'
                raise PbsConnectError(rv=None, rc=-1, msg=m)
            else:
                self._disconnect(self._conn, force=True)
                time.sleep(1)
                return self._connect(hostname, attempt + 1)

        return self._conn

    def _disconnect(self, conn, force=False):
        """
        disconnect a connection to a Server.
        For performance of the API calls, a connection is
        maintained up to _conn_timer, unless the force parameter
        is set to True

        :param conn: Server connection
        :param force: If true then diconnect forcefully
        :type force: bool
        """
        if ((conn is not None and conn >= 0) and
            (force or
             (self._conn_timeout == 0 or
              (self._conn_timer is not None and
               (time.time() - self._conn_timer > self._conn_timeout))))):
            pbs_disconnect(conn)
            self._conn_timer = None
            self._conn = None

    def set_connect_timeout(self, timeout=0):
        """
        Set server connection timeout

        :param timeout: Timeout value
        :type timeout: int
        """
        self._conn_timeout = timeout

    def get_op_mode(self):
        """
        Returns operating mode for calls to the PBS server.
        Currently, two modes are supported, either the ``API``
        or the ``CLI``. Default is ``API``
        """
        if (not API_OK or (self.ptl_conf['mode'] == PTL_CLI)):
            return PTL_CLI
        return PTL_API

    def set_op_mode(self, mode):
        """
        set operating mode to one of either ``PTL_CLI`` or
        ``PTL_API``.Returns the mode that was set which can
        be different from the value requested, for example, if
        requesting to set ``PTL_API``, in the absence of the
        appropriate SWIG wrappers, the library will fall back to
        ``CLI``, or if requesting ``PTL_CLI`` and there is no
        ``PBS_EXEC`` on the system, None is returned.

        :param mode: Operating mode
        :type mode: str
        """
        if mode == PTL_API:
            if self._conn is not None or self._conn < 0:
                self._conn = None
            if not API_OK:
                self.logger.error(self.logprefix +
                                  'API submission is not available')
                return PTL_CLI
        elif mode == PTL_CLI:
            if ((not self.has_snap) and
                not os.path.isdir(os.path.join(self.client_conf['PBS_EXEC'],
                                               'bin'))):
                self.logger.error(self.logprefix +
                                  'PBS commands are not available')
                return None
        else:
            self.logger.error(self.logprefix + "Unrecognized operating mode")
            return None

        self.ptl_conf['mode'] = mode
        self.logger.info(self.logprefix + 'server operating mode set to ' +
                         mode)
        return mode

    def add_expect_action(self, name=None, action=None):
        """
        Add an action handler to expect. Expect Actions are
        custom handlers that are triggered when an unexpected
        value is encountered

        :param name: Action name
        :type name: str or None
        :param action: Action to add
        """
        if name is None and action.name is None:
            return
        if name is None and action.name is not None:
            name = action.name

        if not self.actions.has_action(name):
            self.actions.add_action(action, self.shortname)

    def set_attributes(self, a={}):
        """
        set server attributes

        :param a: Attribute dictionary
        :type a: Dictionary
        """
        super(Server, self).set_attributes(a)
        self.__dict__.update(a)

    def isUp(self):
        """
        returns ``True`` if server is up and ``False`` otherwise
        """
        if self.has_snap:
            return True
        i = 0
        op_mode = self.get_op_mode()
        if ((op_mode == PTL_API) and (self._conn is not None)):
            self._disconnect(self._conn, force=True)
        while i < self.ptl_conf['max_attempts']:
            rv = False
            try:
                if op_mode == PTL_CLI:
                    self.status(SERVER, level=logging.DEBUG, logerr=False)
                else:
                    c = self._connect(self.hostname)
                    self._disconnect(c, force=True)
                return True
            except (PbsConnectError, PbsStatusError):
                # if the status/connect operation fails then there might be
                # chances that server process is running but not responsive
                # so we wait until the server is reported operational.
                rv = self._isUp(self)
                # We really mean to check != False rather than just "rv"
                if str(rv) != 'False':
                    self.logger.warning('Server process started' +
                                        'but not up yet')
                    time.sleep(1)
                    i += 1
                else:
                    # status/connect failed + no server process means
                    # server is actually down
                    return False
        return False

    def signal(self, sig):
        """
        Send signal to server

        :param sig: Signal to send
        :type sig: str
        """
        self.logger.info('server ' + self.shortname + ': sent signal ' + sig)
        return super(Server, self)._signal(sig, inst=self)

    def get_pid(self):
        """
        Get the server pid
        """
        return super(Server, self)._get_pid(inst=self)

    def all_instance_pids(self):
        """
        Get all pids for a given instance
        """
        return super(Server, self)._all_instance_pids(inst=self)

    def start(self, args=None, launcher=None):
        """
        Start the PBS server

        :param args: Argument required to start the server
        :type args: str
        :param launcher: Optional utility to invoke the launch of the service
        :type launcher: str or list
        """
        if args is not None or launcher is not None:
            rv = super(Server, self)._start(inst=self, args=args,
                                            launcher=launcher)
        else:
            try:
                rv = self.pi.start_server()
                pid = self._validate_pid(self)
                if pid is None:
                    raise PbsServiceError(rv=False, rc=-1,
                                          msg="Could not find PID")
            except PbsInitServicesError as e:
                raise PbsServiceError(rc=e.rc, rv=e.rv, msg=e.msg)
        if self.isUp():
            return rv
        else:
            raise PbsServiceError(rv=False, rc=1, msg=rv['err'])

    def stop(self, sig=None):
        """
        Stop the PBS server

        :param sig: Signal to stop PBS server
        :type sig: str
        """
        if sig is not None:
            self.logger.info(self.logprefix + 'stopping Server on host ' +
                             self.hostname)
            rc = super(Server, self)._stop(sig, inst=self)
        else:
            try:
                self.pi.stop_server()
            except PbsInitServicesError as e:
                raise PbsServiceError(rc=e.rc, rv=e.rv, msg=e.msg,
                                      post=self._disconnect, conn=self._conn,
                                      force=True)
            rc = True
        self._disconnect(self._conn, force=True)
        return rc

    def restart(self):
        """
        Terminate and start a PBS server.
        """
        if self.isUp():
            if not self.stop():
                return False
        return self.start()

    def log_match(self, msg=None, id=None, n=50, tail=True, allmatch=False,
                  regexp=False, max_attempts=None, interval=None,
                  starttime=None, endtime=None, level=logging.INFO,
                  existence=True):
        """
        Match given ``msg`` in given ``n`` lines of Server log

        :param msg: log message to match, can be regex also when
                    ``regexp`` is True
        :type msg: str
        :param id: The id of the object to trace. Only used for
                   tracejob
        :type id: str
        :param n: 'ALL' or the number of lines to search through,
                  defaults to 50
        :type n: str or int
        :param tail: If true (default), starts from the end of
                     the file
        :type tail: bool
        :param allmatch: If True all matching lines out of then
                         parsed are returned as a list. Defaults
                         to False
        :type allmatch: bool
        :param regexp: If true msg is a Python regular expression.
                       Defaults to False
        :type regexp: bool
        :param max_attempts: the number of attempts to make to find
                             a matching entry
        :type max_attempts: int
        :param interval: the interval between attempts
        :type interval: int
        :param starttime: If set ignore matches that occur before
                          specified time
        :type starttime: float
        :param endtime: If set ignore matches that occur after
                        specified time
        :type endtime: float
        :param level: The logging level, defaults to INFO
        :type level: int
        :param existence: If True (default), check for existence of
                        given msg, else check for non-existence of
                        given msg.
        :type existence: bool

        :return: (x,y) where x is the matching line
                 number and y the line itself. If allmatch is True,
                 a list of tuples is returned.
        :rtype: tuple
        :raises PtlLogMatchError:
                When ``existence`` is True and given
                ``msg`` is not found in ``n`` line
                Or
                When ``existence`` is False and given
                ``msg`` found in ``n`` line.

        .. note:: The matching line number is relative to the record
                  number, not the absolute line number in the file.
        """
        return self._log_match(self, msg, id, n, tail, allmatch, regexp,
                               max_attempts, interval, starttime, endtime,
                               level=level, existence=existence)

    def revert_to_defaults(self, reverthooks=True, revertqueues=True,
                           revertresources=True, delhooks=True,
                           delqueues=True, delscheds=True, delnodes=True,
                           server_stat=None):
        """
        reset server attributes back to out of box defaults.

        :param reverthooks: If True disable all hooks. Defaults
                            to True
        :type reverthooks: bool
        :param revertqueues: If True disable all non-default
                             queues. Defaults to True
        :type revertqueues: bool
        :param revertresources: If True, resourcedef file is
                                removed. Defaults to True.
                                Reverting resources causes a server
                                restart to occur.
        :type revertresources: bool
        :param delhooks: If True, hooks are deleted, if deletion
                         fails, fall back to reverting hooks. Defaults
                         to True.
        :type delhooks: bool
        :param delqueues: If True, all non-default queues are deleted,
                          will attempt to delete all jobs first, if it
                          fails, revertqueues will be honored,
                          otherwise,revertqueues is ignored. Defaults
                          to True
        :type delqueues: bool
        :param delscheds: If True all non-default schedulers are deleted
                          The sched_priv and sched_logs directories will be
                          deleted.
        :type delscheds: bool
        :param delnodes: If True all vnodes are deleted
        :type delnodes: bool
        :returns: True upon success and False if an error is
                  encountered.
        :raises: PbsStatusError or PbsManagerError
        """
        setdict = {}
        skip_site_hooks = ['pbs_cgroups']
        self.logger.info(self.logprefix +
                         'reverting configuration to defaults')
        self.cleanup_jobs_and_reservations()
        self.atom_hk = os.path.join(self.pbs_conf['PBS_HOME'],
                                    'server_priv', 'hooks',
                                    'PBS_cray_atom.HK')
        self.dflt_atom_hk = os.path.join(self.pbs_conf['PBS_EXEC'],
                                         'lib', 'python', 'altair',
                                         'pbs_hooks',
                                         'PBS_cray_atom.HK')
        self.atom_cf = os.path.join(self.pbs_conf['PBS_HOME'],
                                    'server_priv', 'hooks',
                                    'PBS_cray_atom.CF')
        self.dflt_atom_cf = os.path.join(self.pbs_conf['PBS_EXEC'],
                                         'lib', 'python', 'altair',
                                         'pbs_hooks',
                                         'PBS_cray_atom.CF')
        self.unset_svr_attrib()
        for k in self.dflt_attributes.keys():
            if(k not in self.attributes or
               self.attributes[k] != self.dflt_attributes[k]):
                setdict[k] = self.dflt_attributes[k]
        if self.platform == 'cray' or self.platform == 'craysim':
            setdict[ATTR_restrict_res_to_release_on_suspend] = 'ncpus'
        if delhooks:
            self.delete_site_hooks()
        if delqueues:
            revertqueues = False
            self.delete_queues()
            a = {ATTR_qtype: 'Execution',
                 ATTR_enable: 'True',
                 ATTR_start: 'True'}
            self.manager(MGR_CMD_CREATE, QUEUE, a, id='workq')
            setdict.update({ATTR_dfltque: 'workq'})
        if delscheds:
            self.delete_sched_config()

        if delnodes:
            self.delete_nodes()
        if reverthooks:
            if self.platform == 'shasta':
                dohup = False
                if (self.du.cmp(self.hostname, self.dflt_atom_hk,
                                self.atom_hk, sudo=True) != 0):
                    self.du.run_copy(self.hostname, src=self.dflt_atom_hk,
                                     dest=self.atom_hk, mode=0o644, sudo=True)
                    dohup = True
                if self.du.cmp(self.hostname, self.dflt_atom_cf,
                               self.atom_cf, sudo=True) != 0:
                    self.du.run_copy(self.hostname, src=self.dflt_atom_cf,
                                     dest=self.atom_cf, mode=0o644, sudo=True)
                    dohup = True
                if dohup:
                    self.signal('-HUP')
            hooks = self.status(HOOK, level=logging.DEBUG)
            hooks = [h['id'] for h in hooks]
            a = {ATTR_enable: 'false'}
            if len(hooks) > 0:
                self.manager(MGR_CMD_SET, MGR_OBJ_HOOK, a, hooks)
        if revertqueues:
            self.status(QUEUE, level=logging.DEBUG)
            queues = []
            for (qname, qobj) in self.queues.items():
                # skip reservation queues. This syntax for Python 2.4
                # compatibility
                if (qname.startswith('R') or qname.startswith('S') or
                        qname == server_stat[ATTR_dfltque]):
                    continue
                qobj.revert_to_defaults()
                queues.append(qname)
                a = {ATTR_enable: 'false'}
                self.manager(MGR_CMD_SET, QUEUE, a, id=queues)
            a = {ATTR_enable: 'True', ATTR_start: 'True'}
            self.manager(MGR_CMD_SET, MGR_OBJ_QUEUE, a,
                         id=server_stat[ATTR_dfltque])
        if len(setdict) > 0:
            self.manager(MGR_CMD_SET, MGR_OBJ_SERVER, setdict)
        if revertresources:
            self.delete_resources()
        return True

    def delete_resources(self):
        """
        Delete all resources
        """
        try:
            rescs = self.status(RSC)
            rescs = [r['id'] for r in rescs]
        except:
            rescs = []
        if len(rescs) > 0:
            self.manager(MGR_CMD_DELETE, RSC, id=rescs)

    def unset_svr_attrib(self, server_stat=None):
        """
        Unset server attributes
        """
        ignore_attrs = ['id', 'pbs_license', ATTR_NODE_ProvisionEnable]
        ignore_attrs += [ATTR_status, ATTR_total, ATTR_count]
        ignore_attrs += [ATTR_rescassn, ATTR_FLicenses, ATTR_SvrHost]
        ignore_attrs += [ATTR_license_count, ATTR_version, ATTR_managers]
        ignore_attrs += [ATTR_operators, ATTR_license_min]
        ignore_attrs += [ATTR_pbs_license_info, ATTR_power_provisioning]
        unsetlist = []
        self.cleanup_jobs_and_reservations()
        if server_stat is None:
            server_stat = self.status(SERVER, level=logging.DEBUG)[0]
        for k in server_stat.keys():
            if (k in ignore_attrs) or (k in self.dflt_attributes.keys()):
                continue
            elif (('.' in k) and (k.split('.')[0] in ignore_attrs)):
                continue
            else:
                unsetlist.append(k)
        if len(unsetlist) != 0:
            self.manager(MGR_CMD_UNSET, MGR_OBJ_SERVER, unsetlist)

    def delete_site_hooks(self):
        """
        Delete site hooks from PBS
        """
        skip_site_hooks = ['pbs_cgroups']
        hooks = self.status(HOOK, level=logging.DEBUG)
        hooks = [h['id'] for h in hooks]
        for h in skip_site_hooks:
            if h in hooks:
                hooks.remove(h)
        if len(hooks) > 0:
            self.manager(MGR_CMD_DELETE, HOOK, id=hooks)

    def delete_queues(self):
        """
        Delete queues
        """
        queues = self.status(QUEUE, level=logging.DEBUG)
        queues = [q['id'] for q in queues]
        if len(queues) > 0:
            try:
                nodes = self.status(VNODE, logerr=False)
                for node in nodes:
                    if 'queue' in node.keys():
                        self.manager(MGR_CMD_UNSET, NODE, 'queue',
                                     node['id'])
            except:
                pass
            self.manager(MGR_CMD_DELETE, QUEUE, id=queues)

    def delete_sched_config(self):
        """
        Delete sched_priv & sched_log files
        """
        self.manager(MGR_CMD_LIST, SCHED)
        for name in list(self.schedulers.keys()):
            if name != 'default':
                self.schedulers[name].terminate()
                sched_log = self.schedulers[
                    name].attributes['sched_log']
                sched_priv = self.schedulers[
                    name].attributes['sched_priv']
                self.du.rm(path=sched_log, sudo=True,
                           recursive=True, force=True)
                self.du.rm(path=sched_priv, sudo=True,
                           recursive=True, force=True)
                self.manager(MGR_CMD_DELETE, SCHED, id=name)

    def delete_nodes(self):
        """
        Remove all the nodes from PBS
        """
        try:
            self.manager(MGR_CMD_DELETE, VNODE, id="@default")
        except PbsManagerError as e:
            if "Unknown node" not in e.msg[0]:
                raise

    def save_configuration(self, outfile=None, mode='w'):
        """
        Save a server configuration, this includes:

          - ``server_priv/resourcedef``

          - ``qmgr -c "print server"``

          - ``qmgr -c "print sched"``

          - ``qmgr -c "print hook"``

        :param outfile: the output file to which onfiguration is
                        saved
        :type outfile: str
        :param mode: The mode in which to open outfile to save
                     configuration. The first object being saved
                     should open this file with 'w' and subsequent
                     calls from other objects should save with
                     mode 'a' or 'a+'. Defaults to a+
        :type mode: str
        :returns: True on success, False on error
        """
        conf = {}
        # save pbs.conf file
        cfg_path = self.du.get_pbs_conf_file()
        with open(cfg_path, 'r') as p:
            pbs_cfg = p.readlines()
            config = self.utils.convert_to_dictlist(pbs_cfg)
            cfg_str = str(config[0])
            encode_utf = cfg_str.encode('UTF-8')
            pbs_cfg_b64 = base64.b64encode(encode_utf)
            decode_utf = pbs_cfg_b64.decode('UTF-8')
        conf['pbs_conf'] = decode_utf
        # save hook files
        hooks_str = self._save_hook_files()
        if hooks_str:
            conf.update(hooks_str)
            conf['hooks'] = hooks_str
        else:
            self.logger.error('Failed to save site hooks')
            return False
        qmgr = os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qmgr')
        pbsnodes = os.path.join(
            self.client_conf['PBS_EXEC'], 'bin', 'pbsnodes')
        ret = self.du.run_cmd(
            self.hostname, [
                qmgr, '-c', 'print server'], sudo=True,
            logerr=False, level=logging.DEBUG)
        if ret['rc'] != 0:
            self.logger.error('Failed to get Server attributes')
            return False
        else:
            conf['qmgr_print_server'] = ret['out']
        ret = self.du.run_cmd(self.hostname, [qmgr, '-c', 'print sched'],
                              logerr=False, level=logging.DEBUG, sudo=True)
        if ret['rc'] != 0:
            self.logger.error('Failed to get sched attributes')
            return False
        else:
            conf['qmgr_print_sched'] = ret['out']

        # sudo=True is added while running "pbsnodes -av", to make
        # sure that all the node attributes are preserved in
        # save_configuration. If this command is run without sudo,
        # some of the node attributes like port, version is not listed.
        ret = self.du.run_cmd(self.hostname, [pbsnodes, '-av'],
                              logerr=False, level=logging.DEBUG, sudo=True)
        err_msg = "Server has no node list"
        # pbsnodes -av returns a non zero exit code when there are
        # no nodes in cluster
        if ret['rc'] != 0 and err_msg in ret['err']:
            self.logger.error('Failed to get nodes info')
            return False
        else:
            nodes_val = self.utils.convert_to_dictlist(ret['out'])
            conf['pbsnodes'] = nodes_val
        self.saved_config[MGR_OBJ_SERVER] = conf
        if outfile is not None:
            try:
                with open(outfile, mode) as f:
                    json.dump(self.saved_config, f)
                    self.saved_config[MGR_OBJ_SERVER].clear()
            except:
                self.logger.error('Error processing file ' + outfile)
                return False

        return True

    def _save_hook_files(self):
        """
        save all the hooks .CF, .PY, .HK files
        """
        qmgr = os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qmgr')
        cfg = {"hooks": ""}
        cmd = [qmgr, '-c', 'print hook @default']
        ret = self.du.run_cmd(self.hostname, cmd,
                              sudo=True)
        if ret['rc'] != 0:
            self.logger.error('Failed to save hook files ')
            return False
        else:
            cfg['qmgr_print_hook'] = ret['out']
        return cfg

    def load_configuration(self, infile):
        """
        load server configuration from saved file ``infile``
        """
        rv = self._load_configuration(infile, MGR_OBJ_SERVER)
        return rv

    def get_hostname(self):
        """
        return the default server hostname
        """

        if self.get_op_mode() == PTL_CLI:
            return self.hostname
        return pbs_default()

    def _db_connect(self, db_access=None):
        if self._db_conn is None:
            if 'user' not in db_access or\
               'password' not in db_access:
                self.logger.error('missing credentials to access DB')
                return None

            if 'dbname' not in db_access:
                db_access['dbname'] = 'pbs_datastore'
            if 'port' not in db_access:
                db_access['port'] = '15007'

            if 'host' not in db_access:
                db_access['host'] = self.hostname

            user = db_access['user']
            dbname = db_access['dbname']
            port = db_access['port']
            password = db_access['password']
            host = db_access['host']

            cred = "host=%s dbname=%s user=%s password=%s port=%s" % \
                (host, dbname, user, password, port)
            self._db_conn = psycopg2.connect(cred)

        return self._db_conn

    def _db_server_host(self, cur=None, db_access=None):
        """
        Get the server host name from the database. The server
        host name is stored in the pbs.server table and not in
        pbs.server_attr.

        :param cur: Optional, a predefined cursor to use to
                    operate on the DB
        :param db_acccess: set to either file containing
                           credentials to DB access or
                           dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        """
        local_init = False

        if cur is None:
            conn = self._db_connect(db_access)
            local_init = True
            if conn is None:
                return None
            cur = conn.cursor()

        # obtain server name. The server hostname is stored in table
        # pbs.server
        cur.execute('SELECT sv_hostname from pbs.server')
        if local_init:
            conn.commit()

        tmp_query = cur.fetchone()
        if len(tmp_query) > 0:
            svr_host = tmp_query[0]
        else:
            svr_host = "unknown"
        return svr_host

    def status_db(self, obj_type=None, attrib=None, id=None, db_access=None,
                  logerr=True):
        """
        Status PBS objects from the SQL database

        :param obj_type: The type of object to query, one of the
                         * objects, Default: SERVER
        :param attrib: Attributes to query, can a string, a list,
                       a dictionary Default: None. All attributes
                       will be queried
        :type attrib: str or list or dictionary
        :param id: An optional identifier, the name of the object
                   to status
        :type id: str
        :param db_access: information needed to access the database,
                          can be either a file containing user,
                          port, dbname, password info or a
                          dictionary of key/value entries
        :type db_access: str or dictionary
        """
        if not PSYCOPG:
            self.logger.error('psycopg module unavailable, install from ' +
                              'http://initd.org/psycopg/ and retry')
            return None

        if not isinstance(db_access, dict):
            try:
                with open(db_access, 'r') as f:
                    lines = f.readlines()
            except IOError:
                self.logger.error('Unable to access ' + db_access)
                return None
            db_access = {}
            for line in lines:
                (k, v) = line.split('=')
                db_access[k] = v

        conn = self._db_connect(db_access)
        if conn is None:
            return None

        cur = conn.cursor()

        stmt = []
        if obj_type == SERVER:
            stmt = ["SELECT sv_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.server_attr"]
            svr_host = self.hostname  # self._db_server_host(cur)
        elif obj_type == SCHED:
            stmt = ["SELECT sched_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.scheduler_attr"]
            # reuse server host name for sched host
            svr_host = self.hostname
        elif obj_type == JOB:
            stmt = ["SELECT ji_jobid,attr_name,attr_resource,attr_value " +
                    "FROM pbs.job_attr"]
            if id:
                id_stmt = ["ji_jobid='" + id + "'"]
        elif obj_type == QUEUE:
            stmt = ["SELECT qu_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.queue_attr"]
            if id:
                id_stmt = ["qu_name='" + id + "'"]
        elif obj_type == RESV:
            stmt = ["SELECT ri_resvid,attr_name,attr_resource,attr_value " +
                    "FROM pbs.resv_attr"]
            if id:
                id_stmt = ["ri_resvid='" + id + "'"]
        elif obj_type in (NODE, VNODE):
            stmt = ["SELECT nd_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.node_attr"]
            if id:
                id_stmt = ["nd_name='" + id + "'"]
        else:
            self.logger.error('status: object type not handled')
            return None

        if attrib or id:
            stmt += ["WHERE"]
            extra_stmt = []
            if attrib:
                if isinstance(attrib, dict):
                    attrs = attrib.keys()
                elif isinstance(attrib, list):
                    attrs = attrib
                elif isinstance(attrib, str):
                    attrs = attrib.split(',')
                for a in attrs:
                    extra_stmt += ["attr_name='" + a + "'"]
                stmt += [" OR ".join(extra_stmt)]
            if id:
                stmt += [" AND ", " AND ".join(id_stmt)]

        exec_stmt = " ".join(stmt)
        self.logger.debug('server: executing db statement: ' + exec_stmt)
        cur.execute(exec_stmt)
        conn.commit()
        _results = cur.fetchall()
        obj_dict = {}
        for _res in _results:
            if obj_type in (SERVER, SCHED):
                obj_name = svr_host
            else:
                obj_name = _res[0]
            if obj_name not in obj_dict:
                obj_dict[obj_name] = {'id': obj_name}
            attr = _res[1]
            if _res[2]:
                attr += '.' + _res[2]

            obj_dict[obj_name][attr] = _res[3]

        return list(obj_dict.values())

#
# Begin IFL Wrappers
#

    def __del__(self):
        del self.__dict__

    def status(self, obj_type=SERVER, attrib=None, id=None,
               extend=None, level=logging.INFO, db_access=None, runas=None,
               resolve_indirectness=False, logerr=True):
        """
        Stat any PBS object ``[queue, server, node, hook, job,
        resv, sched]``.If the Server is setup from snap input,
        see snap or snapmap member, the status calls are routed
        directly to the data on files from snap.

        The server can be queried either through the 'qstat'
        command line tool or through the wrapped PBS IFL api,
        see set_op_mode.

        Return a dictionary representation of a batch status object
        raises ``PbsStatsuError on error``.

        :param obj_type: The type of object to query, one of the *
                         objects.Default: SERVER
        :param attrib: Attributes to query, can be a string, a
                       list, a dictionary.Default is to query all
                       attributes.
        :type attrib: str or list or dictionary
        :param id: An optional id, the name of the object to status
        :type id: str
        :param extend: Optional extension to the IFL call
        :param level: The logging level, defaults to INFO
        :type level: str
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        :param runas: run stat as user
        :type runas: str
        :param resolve_indirectness: If True resolves indirect node
                                     resources values
        :type resolve_indirectness: bool
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool

        In addition to standard IFL stat call, this wrapper handles
        a few cases that aren't implicitly offered by pbs_stat*,
        those are for Hooks,Resources, and a formula evaluation.
        """

        prefix = 'status on ' + self.shortname
        if runas:
            prefix += ' as ' + str(runas)
        prefix += ': '
        self.logit(prefix, obj_type, attrib, id, level)

        bs = None
        bsl = []
        freebs = False
        # 2 - Special handling for gathering the job formula value.
        if attrib is not None and PTL_FORMULA in attrib:
            if (((isinstance(attrib, list) or isinstance(attrib, dict)) and
                 (len(attrib) == 1)) or
                    (isinstance(attrib, str) and len(attrib.split(',')) == 1)):
                bsl = self.status(
                    JOB, 'Resource_List.select', id=id, extend='t')
            if self.schedulers[self.dflt_sched_name] is None:
                self.schedulers[self.dflt_sched_name] = get_sched_obj(
                    self.hostname)
            _prev_events = self.status(SCHED, 'log_events',
                                       id=self.dflt_schd_name)[0]['log_events']

            # Job sort formula events are logged at DEBUG2 (256)
            if not int(_prev_events) & 256:
                self.manager(MGR_CMD_SET, SCHED, {'log_events': 2047},
                             id=self.dflt_schd_name)
            self.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
            if id is None:
                _formulas = self.schedulers[self.dflt_sched_name].job_formula()
            else:
                _formulas = {
                    id: self.schedulers[
                        self.dflt_sched_name].job_formula(
                        jobid=id)
                }
            if not int(_prev_filter) & 256:
                self.manager(MGR_CMD_SET, SCHED, {'log_events': _prev_events},
                             id=self.dflt_schd_name)
            if len(bsl) == 0:
                bsl = [{'id': id}]
            for _b in bsl:
                if _b['id'] in _formulas:
                    _b[PTL_FORMULA] = _formulas[_b['id']]
            return bsl

        # 3- Serve data from database if requested... and available for the
        # given object type
        if db_access and obj_type in (SERVER, SCHED, NODE, QUEUE, RESV, JOB):
            bsl = self.status_db(obj_type, attrib, id, db_access=db_access,
                                 logerr=logerr)

        # 4- Serve data from snap files
        elif obj_type in self.snapmap:
            if obj_type in (HOOK, PBS_HOOK):
                for f in self.snapmap[obj_type]:
                    _b = self.utils.file_to_dictlist(f, attrib)
                    if _b and 'hook_name' in _b[0]:
                        _b[0]['id'] = _b[0]['hook_name']
                    else:
                        _b[0]['id'] = os.path.basename(f)
                    if id is None or id == _b[0]['id']:
                        bsl.extend(_b)
            else:
                bsl = self.utils.file_to_dictlist(self.snapmap[obj_type],
                                                  attrib, id=id)
        # 6- Stat using PBS CLI commands
        elif self.get_op_mode() == PTL_CLI:
            tgt = self.client
            if obj_type in (JOB, QUEUE, SERVER):
                pcmd = [os.path.join(
                        self.client_conf['PBS_EXEC'],
                        'bin',
                        'qstat')]

                if extend:
                    pcmd += ['-' + extend]

                if obj_type == JOB:
                    pcmd += ['-f']
                    if id:
                        pcmd += [id]
                    else:
                        pcmd += ['@' + self.hostname]
                elif obj_type == QUEUE:
                    pcmd += ['-Qf']
                    if id:
                        if '@' not in id:
                            pcmd += [id + '@' + self.hostname]
                        else:
                            pcmd += [id]
                    else:
                        pcmd += ['@' + self.hostname]
                elif obj_type == SERVER:
                    pcmd += ['-Bf', self.hostname]

            elif obj_type in (NODE, VNODE, HOST):
                pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                     'pbsnodes')]
                pcmd += ['-s', self.hostname]
                if obj_type in (NODE, VNODE):
                    pcmd += ['-v']
                if obj_type == HOST:
                    pcmd += ['-H']
                if id:
                    pcmd += [id]
                else:
                    pcmd += ['-a']
            elif obj_type == RESV:
                pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                     'pbs_rstat')]
                pcmd += ['-f']
                if id:
                    pcmd += [id]
            elif obj_type in (SCHED, PBS_HOOK, HOOK, RSC):
                try:
                    rc = self.manager(MGR_CMD_LIST, obj_type, attrib, id,
                                      runas=runas, level=level, logerr=logerr)
                except PbsManagerError as e:
                    rc = e.rc
                    # PBS bug, no hooks yields a return code of 1, we ignore
                    if obj_type != HOOK:
                        raise PbsStatusError(
                            rc=rc, rv=[], msg=self.geterrmsg())
                if rc == 0:
                    if obj_type == HOOK:
                        o = self.hooks
                    elif obj_type == PBS_HOOK:
                        o = self.pbshooks
                    elif obj_type == SCHED:
                        o = self.schedulers
                    elif obj_type == RSC:
                        o = self.resources
                    if id:
                        if id in o:
                            return [o[id].attributes]
                        else:
                            return None
                    return [h.attributes for h in o.values()]
                return []

            else:
                self.logger.error(self.logprefix + "unrecognized object type")
                raise PbsStatusError(rc=-1, rv=[],
                                     msg="unrecognized object type")
                return None

            # as_script is used to circumvent some shells that will not pass
            # along environment variables when invoking a command through sudo
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            elif obj_type == RESV and not self._is_local:
                pcmd = ['PBS_SERVER=' + self.hostname] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(tgt, pcmd, runas=runas, as_script=as_script,
                                  level=logging.INFOCLI, logerr=logerr)
            o = ret['out']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if ret['rc'] != 0:
                raise PbsStatusError(rc=ret['rc'], rv=[], msg=self.geterrmsg())

            bsl = self.utils.convert_to_dictlist(o, attrib, mergelines=True)

        # 7- Stat with impersonation over PBS IFL swig-wrapped API
        elif runas is not None:
            _data = {'obj_type': obj_type, 'attrib': attrib, 'id': id}
            bsl = self.pbs_api_as('status', user=runas, data=_data,
                                  extend=extend)
        else:
            # 8- Stat over PBS IFL API
            #
            # resources are special attributes, all resources are queried as
            # a single attribute.
            # e.g. querying the resources_available attribute returns all
            # resources such as ncpus, mem etc. when querying for
            # resources_available.ncpus and resources_available.mem only query
            # resources_available once and retrieve the resources desired from
            # there
            if isinstance(attrib, dict):
                attribcopy = {}
                restype = []
                for k, v in attrib.items():
                    if isinstance(v, tuple):
                        # SET requires a special handling because status may
                        # have been called through counter to count the number
                        # of objects have a given attribute set, in this case
                        # we set the attribute to an empty string rather than
                        # the number of elements requested. This is a
                        # side-effect of the way pbs_statjob works
                        if v[0] in (SET, MATCH_RE):
                            v = ''
                        else:
                            v = v[1]
                    if isinstance(v, collections.Callable):
                        v = ''
                    if '.' in k:
                        _r = k.split('.')[0]
                        if _r not in restype:
                            attribcopy[k] = v
                            restype.append(_r)
                    else:
                        attribcopy[k] = v
            elif isinstance(attrib, list):
                attribcopy = []
                for k in attrib:
                    if '.' in k:
                        _found = False
                        for _e in attribcopy:
                            _r = k.split('.')[0]
                            if _r == _e.split('.')[0]:
                                _found = True
                                break
                        if not _found:
                            attribcopy.append(k)
                    else:
                        attribcopy.append(k)
            else:
                attribcopy = attrib

            a = self.utils.convert_to_attrl(attribcopy)
            c = self._connect(self.hostname)

            if obj_type == JOB:
                bs = pbs_statjob(c, id, a, extend)
            elif obj_type == QUEUE:
                bs = pbs_statque(c, id, a, extend)
            elif obj_type == SERVER:
                bs = pbs_statserver(c, a, extend)
            elif obj_type == HOST:
                bs = pbs_statnode(c, id, a, extend)
            elif obj_type == VNODE:
                bs = pbs_statvnode(c, id, a, extend)
            elif obj_type == RESV:
                bs = pbs_statresv(c, id, a, extend)
            elif obj_type == SCHED:
                bs = pbs_statsched(c, a, extend)
            elif obj_type == RSC:
                # up to PBS 12.3 pbs_statrsc was not in pbs_ifl.h
                bs = pbs_statrsc(c, id, a, extend)
            elif obj_type in (HOOK, PBS_HOOK):
                if os.getuid() != 0:
                    try:
                        rc = self.manager(MGR_CMD_LIST, obj_type, attrib,
                                          id, level=level)
                        if rc == 0:
                            if id:
                                if (obj_type == HOOK and
                                        id in self.hooks):
                                    return [self.hooks[id].attributes]
                                elif (obj_type == PBS_HOOK and
                                      id in self.pbshooks):
                                    return [self.pbshooks[id].attributes]
                                else:
                                    return None
                            if obj_type == HOOK:
                                return [h.attributes for h in
                                        self.hooks.values()]
                            elif obj_type == PBS_HOOK:
                                return [h.attributes for h in
                                        self.pbshooks.values()]
                    except:
                        pass
                else:
                    bs = pbs_stathook(c, id, a, extend)
            else:
                self.logger.error(self.logprefix +
                                  "unrecognized object type " + str(obj_type))

            freebs = True
            err = self.geterrmsg()
            self._disconnect(c)

            if err:
                raise PbsStatusError(rc=-1, rv=[], msg=err)

            if not isinstance(bs, list):
                bsl = self.utils.batch_status_to_dictlist(bs, attrib)
            else:
                bsl = self.utils.filter_batch_status(bs, attrib)

        # Update each object's dictionary with corresponding attributes and
        # values
        self.update_attributes(obj_type, bsl)

        # Hook stat is done through CLI, no need to free the batch_status
        if (not isinstance(bs, list) and freebs and
                obj_type not in (HOOK, PBS_HOOK) and os.getuid() != 0):
            pbs_statfree(bs)

        # 9- Resolve indirect resources
        if obj_type in (NODE, VNODE) and resolve_indirectness:
            nodes = {}
            for _b in bsl:
                for k, v in _b.items():
                    if v.startswith('@'):
                        if v[1:] in nodes:
                            _b[k] = nodes[v[1:]][k]
                        else:
                            for l in bsl:
                                if l['id'] == v[1:]:
                                    nodes[k] = l[k]
                                    _b[k] = l[k]
                                    break
            del nodes
        return bsl

    def submit_interactive_job(self, job, cmd):
        """
        submit an ``interactive`` job. Returns a job identifier
        or raises PbsSubmitError on error

        :param cmd: The command to run to submit the interactive
                    job
        :type cmd: str
        :param job: the job object. The job must have the attribute
                    'interactive_job' populated. That attribute is
                    a list of tuples of the form:
                    (<command>, <expected output>, <...>)
                    for example to send the command
                    hostname and expect 'myhost.mydomain' one would
                    set:job.interactive_job =
                    [('hostname', 'myhost.mydomain')]
                    If more than one lines are expected they are
                    appended to the tuple.
        :raises: PbsSubmitError
        """
        ij = InteractiveJob(job, cmd, self.client)
        # start the interactive job submission thread and wait to pickup the
        # actual job identifier
        ij.start()
        while ij.jobid is None:
            continue
        return ij.jobid

    def submit(self, obj, script=None, extend=None, submit_dir=None,
               env=None):
        """
        Submit a job or reservation. Returns a job identifier
        or raises PbsSubmitError on error

        :param obj: The Job or Reservation instance to submit
        :param script: Path to a script to submit. Default: None
                       as an executable /bin/sleep 100 is submitted
        :type script: str or None
        :param extend: Optional extension to the IFL call.
                       see pbs_ifl.h
        :type extend: str or None
        :param submit_dir: directory from which job is submitted.
                           Defaults to temporary directory
        :type submit_dir: str or None
        :raises: PbsSubmitError
        """

        _interactive_job = False
        as_script = False
        rc = None
        if isinstance(obj, Job):
            if self.platform == 'cray' or self.platform == 'craysim':
                m = False
                vncompute = False
                if 'Resource_List.select' in obj.attributes:
                    select = obj.attributes['Resource_List.select']
                    start = select.startswith('vntype=cray_compute')
                    m = start or ':vntype=cray_compute' in select
                if 'Resource_List.vntype' in obj.attributes:
                    vn_type = obj.attributes['Resource_List.vntype']
                    if vn_type == 'cray_compute':
                        vncompute = True
                if obj.script is not None:
                    script = obj.script
                elif m or vncompute:
                    aprun_cmd = "aprun -b -B"
                    executable = obj.attributes[ATTR_executable]
                    start = executable.startswith('aprun ')
                    aprun_exist = start or '/aprun' in executable
                    if script:
                        aprun_cmd += " " + script
                    else:
                        if aprun_exist:
                            aprun_cmd = executable
                        else:
                            aprun_cmd += " " + executable
                        arg_list = obj.attributes[ATTR_Arglist]
                        aprun_cmd += " " + self.utils.convert_arglist(arg_list)
                    fn = self.du.create_temp_file(hostname=None,
                                                  prefix='PtlPbsJobScript',
                                                  asuser=obj.username,
                                                  body=aprun_cmd)
                    self.du.chmod(path=fn, mode=0o755)
                    script = fn
            elif script is None and obj.script is not None:
                script = obj.script
            if ATTR_inter in obj.attributes:
                _interactive_job = True
                if ATTR_executable in obj.attributes:
                    del obj.attributes[ATTR_executable]
                if ATTR_Arglist in obj.attributes:
                    del obj.attributes[ATTR_Arglist]
        elif not isinstance(obj, Reservation):
            m = self.logprefix + "unrecognized object type"
            self.logger.error(m)
            return None

        if not submit_dir:
            submit_dir = pwd.getpwnam(obj.username)[5]

        cwd = os.getcwd()
        if self.platform != 'shasta':
            if submit_dir:
                os.chdir(submit_dir)
        c = None
        # 1- Submission using the command line tools
        runcmd = []
        if env:
            runcmd += ['#!/bin/bash\n']
            for k, v in env.items():
                if '()' in k:
                    f_name = k.replace('()', '')
                    runcmd += [k, v, "\n", "export", "-f", f_name]
                else:
                    runcmd += ['export %s=\"%s\"' % (k, v)]
                runcmd += ["\n"]

        script_file = None
        if self.get_op_mode() == PTL_CLI:
            exclude_attrs = []  # list of attributes to not convert to CLI
            if isinstance(obj, Job):
                runcmd += [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                        'qsub')]
            elif isinstance(obj, Reservation):
                runcmd += [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                        'pbs_rsub')]
                if ATTR_resv_start in obj.custom_attrs:
                    start = obj.custom_attrs[ATTR_resv_start]
                    obj.custom_attrs[ATTR_resv_start] = \
                        self.utils.convert_seconds_to_datetime(start)
                if ATTR_resv_end in obj.custom_attrs:
                    end = obj.custom_attrs[ATTR_resv_end]
                    obj.custom_attrs[ATTR_resv_end] = \
                        self.utils.convert_seconds_to_datetime(end)
                if ATTR_resv_timezone in obj.custom_attrs:
                    exclude_attrs += [ATTR_resv_timezone, ATTR_resv_standing]
                    # handling of impersonation differs widely across OS's,
                    # when setting PBS_TZID we standardize on running the cmd
                    # as a script instead of customizing for each OS flavor
                    _tz = obj.custom_attrs[ATTR_resv_timezone]
                    runcmd = ['PBS_TZID=' + _tz] + runcmd
                    as_script = True
                    if ATTR_resv_rrule in obj.custom_attrs:
                        _rrule = obj.custom_attrs[ATTR_resv_rrule]
                        if _rrule[0] not in ("'", '"'):
                            _rrule = "'" + _rrule + "'"
                        obj.custom_attrs[ATTR_resv_rrule] = _rrule
                if ATTR_job in obj.attributes:
                    runcmd += ['--job', obj.attributes[ATTR_job]]
                    exclude_attrs += [ATTR_job]

            if not self._is_local:
                if ATTR_queue not in obj.attributes:
                    runcmd += ['-q@' + self.hostname]
                elif '@' not in obj.attributes[ATTR_queue]:
                    curq = obj.attributes[ATTR_queue]
                    runcmd += ['-q' + curq + '@' + self.hostname]
                if obj.custom_attrs and (ATTR_queue in obj.custom_attrs):
                    del obj.custom_attrs[ATTR_queue]

            _conf = self.default_client_pbs_conf
            cmd = self.utils.convert_to_cli(obj.custom_attrs, IFL_SUBMIT,
                                            self.hostname, dflt_conf=_conf,
                                            exclude_attrs=exclude_attrs)

            if cmd is None:
                try:
                    os.chdir(cwd)
                except OSError:
                    pass
                return None
            runcmd += cmd

            if script:
                runcmd += [script]
            else:
                if ATTR_executable in obj.attributes:
                    runcmd += ['--', obj.attributes[ATTR_executable]]
                    if ((ATTR_Arglist in obj.attributes) and
                            (obj.attributes[ATTR_Arglist] is not None)):
                        args = obj.attributes[ATTR_Arglist]
                        arglist = self.utils.convert_arglist(args)
                        if arglist is None:
                            try:
                                os.chdir(cwd)
                            except OSError:
                                pass
                            return None
                        runcmd += [arglist]
            if obj.username != self.current_user:
                runas = obj.username
            else:
                runas = None

            if isinstance(obj, Reservation) and obj.hosts:
                runcmd += ['--hosts'] + obj.hosts

            if _interactive_job:
                ijid = self.submit_interactive_job(obj, runcmd)
                try:
                    os.chdir(cwd)
                except OSError:
                    pass
                return ijid

            if not self.default_client_pbs_conf:
                runcmd = [
                    'PBS_CONF_FILE=' + self.client_pbs_conf_file] + runcmd
                as_script = True
            if env:
                user = PbsUser.get_user(obj.username)
                host = user.host
                run_str = " ".join(runcmd)
                script_file = self.du.create_temp_file(hostname=host,
                                                       body=run_str)
                self.du.chmod(hostname=host, path=script_file, mode=0o755)
                runcmd = [script_file]
            ret = self.du.run_cmd(self.client, runcmd, runas=runas,
                                  level=logging.INFOCLI, as_script=as_script,
                                  env=env, logerr=False)
            if ret['rc'] != 0:
                objid = None
            else:
                objid = ret['out'][0]
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc = ret['rc']

        # 2- Submission with impersonation over API
        elif obj.username != self.current_user:
            # submit job as a user requires setting uid to that user. It's
            # done in a separate process
            obj.set_variable_list(obj.username, submit_dir)
            obj.set_attributes()
            if (obj.script is not None and not self._is_local):
                # This copy assumes that the file system layout on the
                # remote host is identical to the local host. When not
                # the case, this code will need to be updated to copy
                # to a known remote location and update the obj.script
                self.du.run_copy(
                    self.hostname, src=obj.script, dest=obj.script)
                os.remove(obj.script)
            objid = self.pbs_api_as('submit', obj, user=obj.username,
                                    extend=extend)
        # 3- Submission as current user over API
        else:
            c = self._connect(self.hostname)

            if isinstance(obj, Job):
                if script:
                    if ATTR_o not in obj.attributes:
                        obj.attributes[ATTR_o] = (self.hostname + ':' +
                                                  obj.script + '.o')
                    if ATTR_e not in obj.attributes:
                        obj.attributes[ATTR_e] = (self.hostname + ':' +
                                                  obj.script + '.e')
                    sc = os.path.basename(script)
                    obj.unset_attributes([ATTR_executable, ATTR_Arglist])
                    if ATTR_N not in obj.custom_attrs:
                        obj.attributes[ATTR_N] = sc
                if ATTR_queue in obj.attributes:
                    destination = obj.attributes[ATTR_queue]
                    # queue must be removed otherwise will cause the submit
                    # to fail silently
                    del obj.attributes[ATTR_queue]
                else:
                    destination = None

                    if (ATTR_o not in obj.attributes or
                            ATTR_e not in obj.attributes):
                        fn = self.utils.random_str(
                            length=4, prefix='PtlPbsJob')
                        tmp = self.du.get_tempdir(self.hostname)
                        fn = os.path.join(tmp, fn)
                    if ATTR_o not in obj.attributes:
                        obj.attributes[ATTR_o] = (self.hostname + ':' +
                                                  fn + '.o')
                    if ATTR_e not in obj.attributes:
                        obj.attributes[ATTR_e] = (self.hostname + ':' +
                                                  fn + '.e')

                obj.attropl = self.utils.dict_to_attropl(obj.attributes)
                objid = pbs_submit(c, obj.attropl, script, destination,
                                   extend)
            elif isinstance(obj, Reservation):
                if ATTR_resv_duration in obj.attributes:
                    # reserve_duration is not a valid attribute, the API call
                    # will get rejected if it is used
                    wlt = ATTR_l + '.walltime'
                    obj.attributes[wlt] = obj.attributes[ATTR_resv_duration]
                    del obj.attributes[ATTR_resv_duration]

                obj.attropl = self.utils.dict_to_attropl(obj.attributes)
                objid = pbs_submit_resv(c, obj.attropl, extend)

        prefix = 'submit to ' + self.shortname + ' as '
        if isinstance(obj, Job):
            self.logit(prefix + '%s: ' % obj.username, JOB, obj.custom_attrs,
                       objid)
            if obj.script_body:
                self.logger.log(logging.INFOCLI, 'job script ' + script +
                                '\n---\n' + obj.script_body + '\n---')
            if objid is not None:
                self.jobs[objid] = obj
        elif isinstance(obj, Reservation):
            # Reservations without -I option return as 'R123 UNCONFIRMED'
            # so split to get the R123 only

            self.logit(prefix + '%s: ' % obj.username, RESV, obj.attributes,
                       objid)
            if objid is not None:
                objid = objid.split()[0]
                self.reservations[objid] = obj

        if objid is not None:
            obj.server[self.hostname] = objid
        else:
            try:
                os.chdir(cwd)
            except OSError:
                pass
            raise PbsSubmitError(rc=rc, rv=None, msg=self.geterrmsg(),
                                 post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        try:
            os.chdir(cwd)
        except OSError:
            pass

        return objid

    def deljob(self, id=None, extend=None, runas=None, wait=False,
               logerr=True, attr_W=None):
        """
        delete a single job or list of jobs specified by id
        raises ``PbsDeljobError`` on error

        :param id: The identifier(s) of the jobs to delete
        :type id: str or list
        :param extend: Optional parameters to pass along to PBS
        :type extend: str or None
        :param runas: run as user
        :type runas: str or None
        :param wait: Set to True to wait for job(s) to no longer
                     be reported by PBS. False by default
        :type wait: bool
        :param logerr: Whether to log errors. Defaults to True.
        :type logerr: bool
        :param attr_w: -W args to qdel (Only for cli mode)
        :type attr_w: str
        :raises: PbsDeljobError
        """
        prefix = 'delete job on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if id is not None:
            if not isinstance(id, list):
                id = id.split(',')
            prefix += ', '.join(id)
        self.logger.info(prefix)
        c = None
        rc = 0
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qdel')]
            if extend is not None:
                pcmd += self.utils.convert_to_cli(extend, op=IFL_DELETE,
                                                  hostname=self.hostname)
            if attr_W is not None:
                pcmd += ['-W']
                if attr_W != PTL_NOARG:
                    pcmd += [attr_W]
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            elif not self._is_local:
                pcmd = ['PBS_SERVER=' + self.hostname] + pcmd
                as_script = True
            else:
                as_script = False
            if id is not None:
                chunks = [id[i:i + 2000] for i in range(0, len(id), 2000)]
                for chunk in chunks:
                    ret = self.du.run_cmd(self.client, pcmd + chunk,
                                          runas=runas, as_script=as_script,
                                          logerr=logerr, level=logging.INFOCLI)
                    rc = ret['rc']
                    if ret['err'] != ['']:
                        self.last_error = ret['err']
                    self.last_rc = rc
                    if rc != 0:
                        break
            else:
                ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                      as_script=as_script, logerr=logerr,
                                      level=logging.INFOCLI)
                rc = ret['rc']
                if ret['err'] != ['']:
                    self.last_error = ret['err']
                self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('deljob', id, user=runas, extend=extend)
        else:
            c = self._connect(self.hostname)
            rc = 0
            for ajob in id:
                tmp_rc = pbs_deljob(c, ajob, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsDeljobError(rc=rc, rv=False, msg=self.geterrmsg(),
                                 post=self._disconnect, conn=c)
        if self.jobs is not None:
            for j in id:
                if j in self.jobs:
                    if self.jobs[j].interactive_handle is not None:
                        self.jobs[j].interactive_handle.close()
                    del self.jobs[j]
        if c:
            self._disconnect(c)
        if wait and id is not None:
            for oid in id:
                self.expect(JOB, 'queue', id=oid, op=UNSET, runas=runas,
                            level=logging.DEBUG)
        return rc

    def delresv(self, id=None, extend=None, runas=None, wait=False,
                logerr=True):
        """
        delete a single job or list of jobs specified by id
        raises ``PbsDeljobError`` on error

        :param id: The identifier(s) of the jobs to delete
        :type id: str or list
        :param extend: Optional parameters to pass along to PBS
        :type extend: str or None
        :param runas: run as user
        :type runas: str or None
        :param wait: Set to True to wait for job(s) to no longer
                     be reported by PBS. False by default
        :type wait: bool
        :param logerr: Whether to log errors. Defaults to True.
        :type logerr: bool
        :raises: PbsDeljobError
        """
        prefix = 'delete resv on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if id is not None:
            if not isinstance(id, list):
                id = id.split(',')
            prefix += ', '.join(id)
        self.logger.info(prefix)
        c = None
        rc = 0
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'pbs_rdel')]
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            elif not self._is_local:
                pcmd = ['PBS_SERVER=' + self.hostname] + pcmd
                as_script = True
            else:
                as_script = False
            if id is not None:
                chunks = [id[i:i + 2000] for i in range(0, len(id), 2000)]
                for chunk in chunks:
                    ret = self.du.run_cmd(self.client, pcmd + chunk,
                                          runas=runas, as_script=as_script,
                                          logerr=logerr, level=logging.INFOCLI)
                    rc = ret['rc']
                    if ret['err'] != ['']:
                        self.last_error = ret['err']
                    self.last_rc = rc
                    if rc != 0:
                        break
            else:
                ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                      as_script=as_script, logerr=logerr,
                                      level=logging.INFOCLI)
                rc = ret['rc']
                if ret['err'] != ['']:
                    self.last_error = ret['err']
                self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('delresv', id, user=runas, extend=extend)
        else:
            c = self._connect(self.hostname)
            rc = 0
            for ajob in id:
                tmp_rc = pbs_delresv(c, ajob, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsDelresvError(rc=rc, rv=False, msg=self.geterrmsg(),
                                  post=self._disconnect, conn=c)
        if self.reservations is not None:
            for j in id:
                if j in self.reservations:
                    del self.reservations[j]
        if c:
            self._disconnect(c)
        if wait and id is not None:
            for oid in id:
                self.expect(RESV, 'queue', id=oid, op=UNSET, runas=runas,
                            level=logging.DEBUG)
        return rc

    def delete(self, id=None, extend=None, runas=None, wait=False,
               logerr=True):
        """
        delete a single job or list of jobs specified by id
        raises ``PbsDeleteError`` on error

        :param id: The identifier(s) of the jobs/resvs to delete
        :type id: str or list
        :param extend: Optional parameters to pass along to PBS
        :type extend: str or none
        :param runas: run as user
        :type runas: str
        :param wait: Set to True to wait for job(s)/resv(s) to
                     no longer be reported by PBS. False by default
        :type wait: bool
        :param logerr: Whether to log errors. Defaults to True.
        :type logerr: bool
        :raises: PbsDeleteError
        """
        prefix = 'delete on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if id is not None:
            if not isinstance(id, list):
                id = id.split(',')
            prefix += ','.join(id)
        if extend is not None:
            prefix += ' with ' + str(extend)
        self.logger.info(prefix)

        if not len(id) > 0:
            return 0

        obj_type = {}
        for j in id:
            if j[0] in ('R', 'S', 'M'):
                obj_type[j] = RESV
                try:
                    rc = self.delresv(j, extend, runas, logerr=logerr)
                except PbsDelresvError as e:
                    rc = e.rc
                    msg = e.msg
                    rv = e.rv
            else:
                obj_type[j] = JOB
                try:
                    rc = self.deljob(j, extend, runas, logerr=logerr)
                except PbsDeljobError as e:
                    rc = e.rc
                    msg = e.msg
                    rv = e.rv

        if rc != 0:
            raise PbsDeleteError(rc=rc, rv=rv, msg=msg)

        if wait:
            for oid in id:
                self.expect(obj_type[oid], 'queue', id=oid, op=UNSET,
                            runas=runas, level=logging.DEBUG)

        return rc

    def select(self, attrib=None, extend=None, runas=None, logerr=True):
        """
        Select jobs that match attributes list or all jobs if no
        attributes raises ``PbsSelectError`` on error

        :param attrib: A string, list, or dictionary of attributes
        :type attrib: str or list or dictionary
        :param extend: the extended attributes to pass to select
        :type extend: str or None
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :returns: A list of job identifiers that match the
                  attributes specified
        :raises: PbsSelectError
        """
        prefix = "select on " + self.shortname
        if runas is not None:
            prefix += " as " + str(runas)
        prefix += ": "
        if attrib is None:
            s = PTL_ALL
        elif not isinstance(attrib, dict):
            self.logger.error(prefix + "attributes must be a dictionary")
            return
        else:
            s = str(attrib)
        self.logger.info(prefix + s)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'],
                                 'bin', 'qselect')]

            cmd = self.utils.convert_to_cli(attrib, op=IFL_SELECT,
                                            hostname=self.hostname)
            if extend is not None:
                pcmd += ['-' + extend]

            if not self._is_local and ((attrib is None) or
                                       (ATTR_queue not in attrib)):
                pcmd += ['-q', '@' + self.hostname]

            pcmd += cmd
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsSelectError(rc=self.last_rc, rv=False,
                                     msg=self.geterrmsg())
            jobs = ret['out']
            # command returns no jobs as empty, since we expect a valid id,
            # we reset the jobs to an empty array
            if len(jobs) == 1 and jobs[0] == '':
                jobs = []
        elif runas is not None:
            jobs = self.pbs_api_as('select', user=runas, data=attrib,
                                   extend=extend)
        else:
            attropl = self.utils.convert_to_attropl(attrib, op=EQ)
            c = self._connect(self.hostname)
            jobs = pbs_selectjob(c, attropl, extend)
            err = self.geterrmsg()
            if err:
                raise PbsSelectError(rc=-1, rv=False, msg=err,
                                     post=self._disconnect, conn=c)
            self._disconnect(c)

        return jobs

    def selstat(self, select_list, rattrib, runas=None, extend=None):
        """
        stat and filter jobs attributes.

        :param select_list: The filter criteria
        :type select: List
        :param rattrib: The attributes to query
        :type rattrib: List
        :param runas: run as user
        :type runas: str or None

        .. note:: No ``CLI`` counterpart for this call
        """

        attrl = self.utils.convert_to_attrl(rattrib)
        attropl = self.utils.convert_to_attropl(select_list)

        c = self._connect(self.hostname)
        bs = pbs_selstat(c, attropl, attrl, extend)
        self._disconnect(c)
        return bs

    def manager(self, cmd, obj_type, attrib=None, id=None, extend=None,
                level=logging.INFO, sudo=None, runas=None, logerr=True):
        """
        issue a management command to the server, e.g to set an
        attribute

        Returns 0 for Success and non 0 number for Failure

        :param cmd: The command to issue,
                    ``MGR_CMD_[SET,UNSET, LIST,...]`` see pbs_ifl.h
        :type cmd: str
        :param obj_type: The type of object to query, one of
                         the * objects
        :param attrib: Attributes to operate on, can be a string, a
                       list,a dictionary
        :type attrib: str or list or dictionary
        :param id: The name or list of names of the object(s) to act
                   upon.
        :type id: str or list
        :param extend: Optional extension to the IFL call. see
                       pbs_ifl.h
        :type extend: str or None
        :param level: logging level
        :param sudo: If True, run the manager command as super user.
                     Defaults to None. Some attribute settings
                     should be run with sudo set to True, those are
                     acl_roots, job_sort_formula, hook operations,
                     no_sched_hook_event, in those cases, setting
                     sudo to False is only needed for testing
                     purposes
        :type sudo: bool
        :param runas: run as user
        :type runas: str
        :param logerr: If False, CLI commands do not log error,
                       i.e. silent mode
        :type logerr: bool
        :raises: PbsManagerError
        """

        if isinstance(id, str):
            oid = id.split(',')
        else:
            oid = id

        self.logit('manager on ' + self.shortname +
                   [' as ' + str(runas), ''][runas is None] + ': ' +
                   PBS_CMD_MAP[cmd] + ' ', obj_type, attrib, oid, level=level)

        c = None  # connection handle

        if (self.get_op_mode() == PTL_CLI or
            sudo is not None or
            obj_type in (HOOK, PBS_HOOK) or
            (attrib is not None and ('job_sort_formula' in attrib or
                                     'acl_roots' in attrib or
                                     'no_sched_hook_event' in attrib))):

            execcmd = [PBS_CMD_MAP[cmd], PBS_OBJ_MAP[obj_type]]

            if oid is not None:
                if cmd == MGR_CMD_DELETE and obj_type == NODE and oid[0] == "":
                    oid[0] = "@default"
                execcmd += [",".join(oid)]

            if attrib is not None and cmd != MGR_CMD_LIST:
                if cmd == MGR_CMD_IMPORT:
                    execcmd += [attrib['content-type'],
                                attrib['content-encoding'],
                                attrib['input-file']]
                else:
                    if isinstance(attrib, (dict, OrderedDict)):
                        kvpairs = []
                        for k, v in attrib.items():
                            if isinstance(v, tuple):
                                if v[0] == INCR:
                                    op = '+='
                                elif v[0] == DECR:
                                    op = '-='
                                else:
                                    msg = 'Invalid operation: %s' % (v[0])
                                    raise PbsManagerError(rc=1, rv=False,
                                                          msg=msg)
                                v = v[1]
                            else:
                                op = '='
                            if isinstance(v, list) and not isinstance(v, str):
                                # handle string arrays with strings
                                # that contain special characters
                                # with multiple manager calls
                                if any((c in vv) for c in set(', \'\n"')
                                       for vv in v):
                                    if op == '+=' or op == '=':
                                        oper = INCR
                                    else:
                                        oper = DECR
                                    for vv in v:
                                        a = {k: (oper, vv)}
                                        rc = self.manager(cmd=cmd,
                                                          obj_type=obj_type,
                                                          attrib=a, id=id,
                                                          extend=extend,
                                                          level=level,
                                                          sudo=sudo,
                                                          runas=runas,
                                                          logerr=logerr)
                                        if rc:
                                            return rc
                                    return 0
                                # if there are no special characters, then
                                # join the list and parse it normally.
                                v = ','.join(v)
                            if isinstance(v, str):
                                # don't quote if already quoted
                                if v[0] == v[-1] and v[0] in set('"\''):
                                    pass
                                # handle string arrays
                                elif ',' in v and v[0] != '"':
                                    v = '"' + v + '"'
                                # handle strings that need to be quoted
                                elif any((c in v) for c in set(', \'\n"')):
                                    if '"' in v:
                                        v = "'%s'" % v
                                    else:
                                        v = '"%s"' % v
                            kvpairs += [str(k) + op + str(v)]
                        if kvpairs:
                            execcmd += [",".join(kvpairs)]
                            del kvpairs
                    elif isinstance(attrib, list):
                        execcmd += [",".join(attrib)]
                    elif isinstance(attrib, str):
                        execcmd += [attrib]

            if not self.default_pbs_conf or not self.default_client_pbs_conf:
                as_script = True
            else:
                as_script = False

            if (not self._is_local or as_script or
                (runas and
                 not self.du.is_localhost(PbsUser.get_user(runas).host))):
                execcmd = '\'' + " ".join(execcmd) + '\''
            else:
                execcmd = " ".join(execcmd)

            # Hooks can only be queried as a privileged user on the host where
            # the server is running, care must be taken to use the appropriate
            # path to qmgr and appropriate escaping sequences
            # VERSION INFO: no_sched_hook_event introduced in 11.3.120 only
            if sudo is None:
                if (obj_type in (HOOK, PBS_HOOK) or
                    (attrib is not None and
                     ('job_sort_formula' in attrib or
                      'acl_roots' in attrib or
                      'no_sched_hook_event' in attrib))):
                    sudo = True
                else:
                    sudo = False

            pcmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'bin', 'qmgr'),
                    '-c', execcmd]

            if as_script:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd

            ret = self.du.run_cmd(self.hostname, pcmd, sudo=sudo, runas=runas,
                                  level=logging.INFOCLI, as_script=as_script,
                                  logerr=logerr)
            rc = ret['rc']
            # NOTE: workaround the fact that qmgr overloads the return code in
            # cases where the list returned is empty an error flag is set even
            # through there is no error. Handled here by checking if there is
            # no err and out message, in which case return code is set to 0
            if rc != 0 and (ret['out'] == [''] and ret['err'] == ['']):
                rc = 0
            if rc == 0:
                if cmd == MGR_CMD_LIST:
                    bsl = self.utils.convert_to_dictlist(ret['out'],
                                                         mergelines=True)
                    # Since we stat everything, overwrite the cache
                    self.update_attributes(obj_type, bsl, overwrite=True)
                    # Filter out the attributes requested
                    if attrib:
                        bsl_attr = []
                        for obj in bsl:
                            dnew = {}
                            for k in obj.keys():
                                if k in attrib:
                                    dnew[k] = obj[k]
                            bsl_attr.append(dnew)
                        bsl = bsl_attr
            else:
                # Need to rework setting error, this is not thread safe
                self.last_error = ret['err']
            self.last_rc = ret['rc']
        elif runas is not None:
            _data = {'cmd': cmd, 'obj_type': obj_type, 'attrib': attrib,
                     'id': oid}
            rc = self.pbs_api_as('manager', user=runas, data=_data,
                                 extend=extend)
        else:
            a = self.utils.convert_to_attropl(attrib, cmd)
            c = self._connect(self.hostname)
            rc = 0
            if obj_type == SERVER and oid is None:
                oid = [self.hostname]
            if oid is None:
                # server will run strlen on id, it can not be NULL
                oid = ['']
            if cmd == MGR_CMD_LIST:
                if oid is None:
                    bsl = self.status(obj_type, attrib, oid, extend)
                else:
                    bsl = None
                    for i in oid:
                        tmpbsl = self.status(obj_type, attrib, i, extend)
                        if tmpbsl is None:
                            rc = 1
                        else:
                            if bsl is None:
                                bsl = tmpbsl
                            else:
                                bsl += tmpbsl
            else:
                rc = 0
                if oid is None:
                    rc = pbs_manager(c, cmd, obj_type, i, a, extend)
                else:
                    for i in oid:
                        tmprc = pbs_manager(c, cmd, obj_type, i, a, extend)
                        if tmprc != 0:
                            rc = tmprc
                            break
                    if rc == 0:
                        rc = tmprc

        if id is None and obj_type == SERVER:
            id = self.pbs_conf['PBS_SERVER']
        bs_list = []
        if cmd == MGR_CMD_DELETE and oid is not None and rc == 0:
            for i in oid:
                if obj_type == MGR_OBJ_HOOK and i in self.hooks:
                    del self.hooks[i]
                if obj_type in (NODE, VNODE) and i in self.nodes:
                    del self.nodes[i]
                if obj_type == MGR_OBJ_QUEUE and i in self.queues:
                    del self.queues[i]
                if obj_type == MGR_OBJ_RSC and i in self.resources:
                    del self.resources[i]
                if obj_type == SCHED and i in self.schedulers:
                    del self.schedulers[i]

        elif cmd == MGR_CMD_SET and rc == 0 and id is not None:
            if isinstance(id, list):
                for name in id:
                    tbsl = copy.deepcopy(attrib)
                    tbsl['name'] = name
                    bs_list.append(tbsl)
                    self.update_attributes(obj_type, bs_list)
            else:
                tbsl = copy.deepcopy(attrib)
                tbsl['id'] = id
                bs_list.append(tbsl)
                self.update_attributes(obj_type, bs_list)

        elif cmd == MGR_CMD_CREATE and rc == 0:
            if isinstance(id, list):
                for name in id:
                    bsl = self.status(obj_type, id=name, extend=extend)
                    self.update_attributes(obj_type, bsl)
            else:
                bsl = self.status(obj_type, id=id, extend=extend)
                self.update_attributes(obj_type, bsl)

        if rc != 0:
            raise PbsManagerError(rv=False, rc=rc, msg=self.geterrmsg(),
                                  post=self._disconnect, conn=c)

        if c is not None:
            self._disconnect(c)
        if cmd == MGR_CMD_SET and 'scheduling' in attrib:
            if attrib['scheduling'] in PTL_FALSE:
                if obj_type == SERVER:
                    sname = 'default'
                else:
                    sname = id

                # Default max cycle length is 1200 seconds (20m)
                self.expect(SCHED, {'state': 'scheduling'}, op=NE, id=sname,
                            interval=1, max_attempts=1200,
                            trigger_sched_cycle=False)
        return rc

    def sigjob(self, jobid=None, signal=None, extend=None, runas=None,
               logerr=True):
        """
        Send a signal to a job. Raises ``PbsSignalError`` on error.

        :param jobid: identifier of the job or list of jobs to send
                      the signal to
        :type jobid: str or list
        :param signal: The signal to send to the job, see pbs_ifl.h
        :type signal: str or None
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsSignalError
        """

        prefix = 'signal on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if signal is not None:
            prefix += ' with signal = ' + str(signal)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qsig')]
            if signal is not None:
                pcmd += ['-s']
                if signal != PTL_NOARG:
                    pcmd += [str(signal)]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('sigjob', jobid, runas, data=signal)
        else:
            c = self._connect(self.hostname)
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_sigjob(c, ajob, signal, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsSignalError(rc=rc, rv=False, msg=self.geterrmsg(),
                                 post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def msgjob(self, jobid=None, to_file=None, msg=None, extend=None,
               runas=None, logerr=True):
        """
        Send a message to a job. Raises ``PbsMessageError`` on
        error.

        :param jobid: identifier of the job or list of jobs to
                      send the message to
        :type jobid: str or List
        :param msg: The message to send to the job
        :type msg: str or None
        :param to_file: one of ``MSG_ERR`` or ``MSG_OUT`` or
                        ``MSG_ERR|MSG_OUT``
        :type to_file: str or None
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsMessageError
        """
        prefix = 'msgjob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if to_file is not None:
            prefix += ' with to_file = '
            if MSG_ERR == to_file:
                prefix += 'MSG_ERR'
            elif MSG_OUT == to_file:
                prefix += 'MSG_OUT'
            elif MSG_OUT | MSG_ERR == to_file:
                prefix += 'MSG_ERR|MSG_OUT'
            else:
                prefix += str(to_file)
        if msg is not None:
            prefix += ' msg = %s' % (str(msg))
        if extend is not None:
            prefix += ' extend = %s' % (str(extend))
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qmsg')]
            if to_file is not None:
                if MSG_ERR == to_file:
                    pcmd += ['-E']
                elif MSG_OUT == to_file:
                    pcmd += ['-O']
                elif MSG_OUT | MSG_ERR == to_file:
                    pcmd += ['-E', '-O']
                else:
                    pcmd += ['-' + str(to_file)]
            if msg is not None:
                pcmd += [msg]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            data = {'msg': msg, 'to_file': to_file}
            rc = self.pbs_api_as('msgjob', jobid, runas, data=data,
                                 extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            for ajob in jobid:
                tmp_rc = pbs_msgjob(c, ajob, to_file, msg, extend)
                if tmp_rc != 0:
                    rc = tmp_rc

        if rc != 0:
            raise PbsMessageError(rc=rc, rv=False, msg=self.geterrmsg(),
                                  post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def alterjob(self, jobid=None, attrib=None, extend=None, runas=None,
                 logerr=True):
        """
        Alter attributes associated to a job. Raises
        ``PbsAlterError`` on error.

        :param jobid: identifier of the job or list of jobs to
                      operate on
        :type jobid: str or list
        :param attrib: A dictionary of attributes to set
        :type attrib: dictionary
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If False, CLI commands do not log error,
                       i.e. silent mode
        :type logerr: bool
        :raises: PbsAlterError
        """
        prefix = 'alter on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if attrib is not None:
            prefix += ' %s' % (str(attrib))
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qalter')]
            if attrib is not None:
                _conf = self.default_client_pbs_conf
                pcmd += self.utils.convert_to_cli(attrib, op=IFL_ALTER,
                                                  hostname=self.client,
                                                  dflt_conf=_conf)
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('alterjob', jobid, runas, data=attrib)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            a = self.utils.convert_to_attrl(attrib)
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_alterjob(c, ajob, a, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsAlterError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def holdjob(self, jobid=None, holdtype=None, extend=None, runas=None,
                logerr=True):
        """
        Hold a job. Raises ``PbsHoldError`` on error.

        :param jobid: identifier of the job or list of jobs to hold
        :type jobid: str or list
        :param holdtype: The type of hold to put on the job
        :type holdtype: str or None
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsHoldError
        """
        prefix = 'holdjob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if holdtype is not None:
            prefix += ' with hold_list = %s' % (holdtype)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qhold')]
            if holdtype is not None:
                pcmd += ['-h']
                if holdtype != PTL_NOARG:
                    pcmd += [holdtype]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  logerr=logerr, as_script=as_script,
                                  level=logging.INFOCLI)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('holdjob', jobid, runas, data=holdtype,
                                 logerr=logerr)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_holdjob(c, ajob, holdtype, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsHoldError(rc=rc, rv=False, msg=self.geterrmsg(),
                               post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def rlsjob(self, jobid, holdtype, extend=None, runas=None, logerr=True):
        """
        Release a job. Raises ``PbsReleaseError`` on error.

        :param jobid: job or list of jobs to release
        :type jobid: str or list
        :param holdtype: The type of hold to release on the job
        :type holdtype: str
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsReleaseError
        """
        prefix = 'release on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if holdtype is not None:
            prefix += ' with hold_list = %s' % (holdtype)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qrls')]
            if holdtype is not None:
                pcmd += ['-h']
                if holdtype != PTL_NOARG:
                    pcmd += [holdtype]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('rlsjob', jobid, runas, data=holdtype)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_rlsjob(c, ajob, holdtype, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsHoldError(rc=rc, rv=False, msg=self.geterrmsg(),
                               post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def rerunjob(self, jobid=None, extend=None, runas=None, logerr=True):
        """
        Rerun a job. Raises ``PbsRerunError`` on error.
        :param jobid: job or list of jobs to release
        :type jobid: str or list
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsRerunError
        """
        prefix = 'rerun on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if extend is not None:
            prefix += extend
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qrerun')]
            if extend:
                pcmd += ['-W', extend]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('rerunjob', jobid, runas, extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_rerunjob(c, ajob, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsRerunError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def orderjob(self, jobid1=None, jobid2=None, extend=None, runas=None,
                 logerr=True):
        """
        reorder position of ``jobid1`` and ``jobid2``. Raises
        ``PbsOrderJob`` on error.

        :param jobid1: first jobid
        :type jobid1: str or None
        :param jobid2: second jobid
        :type jobid2: str or None
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsOrderJob
        """
        prefix = 'orderjob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        prefix += str(jobid1) + ', ' + str(jobid2)
        if extend is not None:
            prefix += ' ' + str(extend)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qorder')]
            if jobid1 is not None:
                pcmd += [jobid1]
            if jobid2 is not None:
                pcmd += [jobid2]
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('orderjob', jobid1, runas, data=jobid2,
                                 extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = pbs_orderjob(c, jobid1, jobid2, extend)
        if rc != 0:
            raise PbsOrderError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def runjob(self, jobid=None, location=None, run_async=False, extend=None,
               runas=None, logerr=False):
        """
        Run a job on given nodes. Raises ``PbsRunError`` on error.

        :param jobid: job or list of jobs to run
        :type jobid: str or list
        :param location: An execvnode on which to run the job
        :type location: str or None
        :param run_async: If true the call will return immediately
                      assuming success.
        :type run_async: bool
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsRunError
        """
        if run_async:
            prefix = 'Async run on ' + self.shortname
        else:
            prefix = 'run on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if location is not None:
            prefix += ' with location = %s' % (location)
        self.logger.info(prefix)

        if self.has_snap:
            return 0

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qrun')]
            if run_async:
                pcmd += ['-a']
            if location is not None:
                pcmd += ['-H']
                if location != PTL_NOARG:
                    pcmd += [location]
            if jobid:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as(
                'runjob', jobid, runas, data=location, extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                if run_async:
                    tmp_rc = pbs_asyrunjob(c, ajob, location, extend)
                else:
                    tmp_rc = pbs_runjob(c, ajob, location, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsRunError(rc=rc, rv=False, msg=self.geterrmsg(),
                              post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def movejob(self, jobid=None, destination=None, extend=None, runas=None,
                logerr=True):
        """
        Move a job or list of job ids to a given destination queue.
        Raises ``PbsMoveError`` on error.

        :param jobid: A job or list of job ids to move
        :type jobid: str or list
        :param destination: The destination queue@server
        :type destination: str or None
        :param extend: extend options
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsMoveError
        """
        prefix = 'movejob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if destination is not None:
            prefix += ' destination = %s' % (destination)
        self.logger.info(prefix)

        c = None
        rc = 0

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qmove')]
            if destination is not None:
                pcmd += [destination]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  logerr=logerr, as_script=as_script,
                                  level=logging.INFOCLI)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('movejob', jobid, runas, data=destination,
                                 extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            for ajob in jobid:
                tmp_rc = pbs_movejob(c, ajob, destination, extend)
                if tmp_rc != 0:
                    rc = tmp_rc

        if rc != 0:
            raise PbsMoveError(rc=rc, rv=False, msg=self.geterrmsg(),
                               post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def qterm(self, manner=None, extend=None, server_name=None, runas=None,
              logerr=True):
        """
        Terminate the ``pbs_server`` daemon

        :param manner: one of ``(SHUT_IMMEDIATE | SHUT_DELAY |
                       SHUT_QUICK)`` and can be\
                       combined with SHUT_WHO_SCHED, SHUT_WHO_MOM,
                       SHUT_WHO_SECDRY, \
                       SHUT_WHO_IDLESECDRY, SHUT_WHO_SECDONLY. \
        :param extend: extend options
        :param server_name: name of the pbs server
        :type server_name: str or None
        :param runas: run as user
        :type runas: str or None
        :param logerr: If True (default) logs run_cmd errors
        :type logerr: bool
        :raises: PbsQtermError
        """
        prefix = 'terminate ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': with manner '
        attrs = manner
        if attrs is None:
            prefix += "None "
        elif isinstance(attrs, str):
            prefix += attrs
        else:
            if ((attrs & SHUT_QUICK) == SHUT_QUICK):
                prefix += "quick "
            if ((attrs & SHUT_IMMEDIATE) == SHUT_IMMEDIATE):
                prefix += "immediate "
            if ((attrs & SHUT_DELAY) == SHUT_DELAY):
                prefix += "delay "
            if ((attrs & SHUT_WHO_SCHED) == SHUT_WHO_SCHED):
                prefix += "schedular "
            if ((attrs & SHUT_WHO_MOM) == SHUT_WHO_MOM):
                prefix += "mom "
            if ((attrs & SHUT_WHO_SECDRY) == SHUT_WHO_SECDRY):
                prefix += "secondary server "
            if ((attrs & SHUT_WHO_IDLESECDRY) == SHUT_WHO_IDLESECDRY):
                prefix += "idle secondary "
            if ((attrs & SHUT_WHO_SECDONLY) == SHUT_WHO_SECDONLY):
                prefix += "shoutdown secondary only "

        self.logger.info(prefix)

        if self.has_snap:
            return 0

        c = None
        rc = 0

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qterm')]
            _conf = self.default_client_pbs_conf
            pcmd += self.utils.convert_to_cli(manner, op=IFL_TERMINATE,
                                              hostname=self.hostname,
                                              dflt_conf=_conf)
            if server_name is not None:
                pcmd += [server_name]

            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  level=logging.INFOCLI, as_script=as_script)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            attrs = {'manner': manner, 'server_name': server_name}
            rc = self.pbs_api_as('terminate', None, runas, data=attrs,
                                 extend=extend)
        else:
            if server_name is None:
                server_name = self.hostname
            c = self._connect(self.hostname)
            rc = pbs_terminate(c, manner, extend)
        if rc != 0:
            raise PbsQtermError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c, force=True)

        if c:
            self._disconnect(c, force=True)

        return rc
    teminate = qterm

    def geterrmsg(self):
        """
        Get the error message
        """
        mode = self.get_op_mode()
        if mode == PTL_CLI:
            return self.last_error
        elif self._conn is not None and self._conn >= 0:
            m = pbs_geterrmsg(self._conn)
            if m is not None:
                m = m.split('\n')
            return m
#
# End IFL Wrappers
#

    def qdisable(self, queue=None, runas=None, logerr=True):
        """
        Disable queue. ``CLI`` mode only

        :param queue: The name of the queue or list of queue to
                      disable
        :type queue: str or list
        :param runas: Optional name of user to run command as
        :type runas: str or None
        :param logerr: Set to False ot disable logging command
                       errors.Defaults to True.
        :type logerr: bool
        :raises: PbsQdisableError
        """
        prefix = 'qdisable on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qdisable')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQdisableError(rc=self.last_rc, rv=False,
                                       msg=self.last_error)
        else:
            _msg = 'qdisable: currently not supported in API mode'
            raise PbsQdisableError(rv=False, rc=1, msg=_msg)

    def qenable(self, queue=None, runas=None, logerr=True):
        """
        Enable queue. ``CLI`` mode only

        :param queue: The name of the queue or list of queue to
                      enable
        :type queue: str or list
        :param runas: Optional name of user to run command as
        :type runas: str or None
        :param logerr: Set to False ot disable logging command
                       errors.Defaults to True.
        :type logerr: bool
        :raises: PbsQenableError
        """
        prefix = 'qenable on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qenable')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQenableError(rc=self.last_rc, rv=False,
                                      msg=self.last_error)
        else:
            _msg = 'qenable: currently not supported in API mode'
            raise PbsQenableError(rv=False, rc=1, msg=_msg)

    def qstart(self, queue=None, runas=None, logerr=True):
        """
        Start queue. ``CLI`` mode only

        :param queue: The name of the queue or list of queue
                      to start
        :type queue: str or list
        :param runas: Optional name of user to run command as
        :type runas: str or None
        :param logerr: Set to False ot disable logging command
                       errors.Defaults to True.
        :type logerr: bool
        :raises: PbsQstartError
        """
        prefix = 'qstart on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qstart')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQstartError(rc=self.last_rc, rv=False,
                                     msg=self.last_error)
        else:
            _msg = 'qstart: currently not supported in API mode'
            raise PbsQstartError(rv=False, rc=1, msg=_msg)

    def qstop(self, queue=None, runas=None, logerr=True):
        """
        Stop queue. ``CLI`` mode only

        :param queue: The name of the queue or list of queue to stop
        :type queue: str or list
        :param runas: Optional name of user to run command as
        :type runas: str or None
        :param logerr: Set to False ot disable logging command errors.
                       Defaults to True.
        :type logerr: bool
        :raises: PbsQstopError
        """
        prefix = 'qstop on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qstop')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQstopError(rc=self.last_rc, rv=False,
                                    msg=self.last_error)
        else:
            _msg = 'qstop: currently not supported in API mode'
            raise PbsQstopError(rv=False, rc=1, msg=_msg)

    def parse_resources(self):
        """
        Parse server resources as defined in the resourcedef file
        Populates instance variable self.resources

        :returns: The resources as a dictionary
        """
        if not self.has_snap:
            self.manager(MGR_CMD_LIST, RSC)
        return self.resources

    def remove_resource(self, name):
        """
        Remove an entry from resourcedef

        :param name: The name of the resource to remove
        :type name: str
        :param restart: Whether to restart the server or not.
                        Applicable to update_mode 'file'
                        operations only.
        :param update_mode: one of 'file' or 'auto' (the default).
                            If 'file', updates the resourcedef file
                            only and will not use the qmgr
                            operations on resources introduced in
                            12.3. If 'auto', will automatically
                            handle the update on resourcedef or
                            using qmgr based on the version of the
                            Server.
        """
        self.parse_resources()
        if not self.has_snap:
            if name in self.resources:
                self.manager(MGR_CMD_DELETE, RSC, id=name)

    def add_resource(self, name, type=None, flag=None):
        """
        Define a server resource

        :param name: The name of the resource to add to the
                     resourcedef file
        :type name: str
        :param type: The type of the resource, one of string,
                     long, boolean, float
        :param flag: The target of the resource, one of n, h, q,
                     or none
        :type flag: str or None
        :param restart: Whether to restart the server after adding
                        a resource.Applicable to update_mode 'file'
                        operations only.
        :param update_mode: one of 'file' or 'auto' (the default).
                            If 'file', updates the resourcedef file
                            only and will not use the qmgr
                            operations on resources introduced in
                            12.3. If 'auto', will automatically
                            handle the update on resourcedef or
                            using qmgr based on the version of the
                            Server.
        :returns: True on success False on error
        """
        rv = self.parse_resources()
        if rv is None:
            return False

        resource_exists = False
        if name in self.resources:
            msg = [self.logprefix + "resource " + name]
            if type:
                msg += ["type: " + type]
            if flag:
                msg += ["flag: " + flag]
            msg += [" already defined"]
            self.logger.info(" ".join(msg))

            (t, f) = (self.resources[name].type, self.resources[name].flag)
            if type == t and flag == f:
                return True

            self.logger.info("resource: redefining resource " + name +
                             " type: " + str(type) + " and flag: " + str(flag))
            del self.resources[name]
            resource_exists = True

        r = Resource(name, type, flag)
        self.resources[name] = r
        a = {}
        if type:
            a['type'] = type
        if flag:
            a['flag'] = flag
        if resource_exists:
            self.manager(MGR_CMD_SET, RSC, a, id=name)
        else:
            self.manager(MGR_CMD_CREATE, RSC, a, id=name)
        return True

    def write_resourcedef(self, resources=None, filename=None, restart=True):
        """
        Write into resource def file

        :param resources: PBS resources
        :type resources: dictionary
        :param filename: resourcedef file name
        :type filename: str or None
        """
        if resources is None:
            resources = self.resources
        if isinstance(resources, Resource):
            resources = {resources.name: resources}
        fn = self.du.create_temp_file()
        with open(fn, 'w+') as f:
            for r in resources.values():
                f.write(r.attributes['id'])
                if r.attributes['type'] is not None:
                    f.write(' type=' + r.attributes['type'])
                if r.attributes['flag'] is not None:
                    f.write(' flag=' + r.attributes['flag'])
                f.write('\n')
        if filename is None:
            dest = os.path.join(self.pbs_conf['PBS_HOME'], 'server_priv',
                                'resourcedef')
        else:
            dest = filename
        self.du.run_copy(self.hostname, src=fn, dest=dest, sudo=True,
                         preserve_permission=False)
        os.remove(fn)
        if restart:
            return self.restart()
        return True

    def parse_resourcedef(self, file=None):
        """
        Parse an arbitrary resource definition file passed as
        input and return a dictionary of resources

        :param file: resource definition file
        :type file: str or None
        :returns: Dictionary of resource
        :raises: PbsResourceError
        """
        if file is None:
            file = os.path.join(self.pbs_conf['PBS_HOME'], 'server_priv',
                                'resourcedef')
        ret = self.du.cat(self.hostname, file, logerr=False, sudo=True)
        if ret['rc'] != 0 or len(ret['out']) == 0:
            # Most probable error is that file does not exist, we'll let it
            # be created
            return {}

        resources = {}
        lines = ret['out']
        try:
            for l in lines:
                l = l.strip()
                if l == '' or l.startswith('#'):
                    continue
                name = None
                rtype = None
                flag = None
                res = l.split()
                e0 = res[0]
                if len(res) > 1:
                    e1 = res[1].split('=')
                else:
                    e1 = None
                if len(res) > 2:
                    e2 = res[2].split('=')
                else:
                    e2 = None
                if e1 is not None and e1[0] == 'type':
                    rtype = e1[1]
                elif e2 is not None and e2[0] == 'type':
                    rtype = e2[1]
                if e1 is not None and e1[0] == 'flag':
                    flag = e1[0]
                elif e2 is not None and e2[0] == 'flag':
                    flag = e2[1]
                name = e0
                r = Resource(name, rtype, flag)
                resources[name] = r
        except:
            raise PbsResourceError(rc=1, rv=False,
                                   msg="error in parse_resources")
        return resources

    def pbs_api_as(self, cmd=None, obj=None, user=None, **kwargs):
        """
        Generic handler to run an ``API`` call impersonating
        a given user.This method is only used for impersonation
        over the ``API`` because ``CLI`` impersonation takes place
        through the generic ``DshUtils`` run_cmd mechanism.

        :param cmd: PBS command
        :type cmd: str or None
        :param user: PBS user or current user
        :type user: str or None
        :raises: eval
        """
        fn = None
        objid = None
        _data = None

        if user is None:
            user = self.du.get_current_user()
        else:
            # user may be a PbsUser object, cast it to string for the remainder
            # of the function
            user = str(user)

        if cmd == 'submit':
            if obj is None:
                return None

            _data = copy.copy(obj)
            # the following attributes cause problems 'pickling',
            # since they are not needed we unset them
            _data.attrl = None
            _data.attropl = None
            _data.logger = None
            _data.utils = None

        elif cmd in ('alterjob', 'holdjob', 'sigjob', 'msgjob', 'rlsjob',
                     'rerunjob', 'orderjob', 'runjob', 'movejob',
                     'select', 'delete', 'status', 'manager', 'terminate',
                     'deljob', 'delresv', 'alterresv'):
            objid = obj
            if 'data' in kwargs:
                _data = kwargs['data']

        if _data is not None:
            fn = self.du.create_temp_file()
            with open(fn, 'w+b') as tmpfile:
                pickle.dump(_data, tmpfile)

            os.chmod(fn, 0o755)

            if self._is_local:
                os.chdir(tempfile.gettempdir())
            else:
                self.du.run_copy(self.hostname, src=fn, dest=fn)

        if not self._is_local:
            p_env = '"import os; print(os.environ[\'PTL_EXEC\'])"'
            ret = self.du.run_cmd(self.hostname, ['python3', '-c', p_env],
                                  logerr=False)
            if ret['out']:
                runcmd = [os.path.join(ret['out'][0], 'pbs_as')]
            else:
                runcmd = ['pbs_as']
        elif 'PTL_EXEC' in os.environ:
            runcmd = [os.path.join(os.environ['PTL_EXEC'], 'pbs_as')]
        else:
            runcmd = ['pbs_as']

        runcmd += ['-c', cmd, '-u', user]

        if objid is not None:
            runcmd += ['-o']
            if isinstance(objid, list):
                runcmd += [','.join(objid)]
            else:
                runcmd += [objid]

        if fn is not None:
            runcmd += ['-f', fn]

        if 'hostname' in kwargs:
            hostname = kwargs['hostname']
        else:
            hostname = self.hostname
        runcmd += ['-s', hostname]

        if 'extend' in kwargs and kwargs['extend'] is not None:
            runcmd += ['-e', kwargs['extend']]

        ret = self.du.run_cmd(self.hostname, runcmd, logerr=False, runas=user)
        out = ret['out']
        if ret['err']:
            if cmd in CMD_ERROR_MAP:
                m = CMD_ERROR_MAP[cmd]
                if m in ret['err'][0]:
                    if fn is not None:
                        os.remove(fn)
                        if not self._is_local:
                            self.du.rm(self.hostname, fn)
                    raise eval(str(ret['err'][0]))
            self.logger.debug('err: ' + str(ret['err']))

        if fn is not None:
            os.remove(fn)
            if not self._is_local:
                self.du.rm(self.hostname, fn)

        if cmd == 'submit':
            if out:
                return out[0].strip()
            else:
                return None
        elif cmd in ('alterjob', 'holdjob', 'sigjob', 'msgjob', 'rlsjob',
                     'rerunjob', 'orderjob', 'runjob', 'movejob', 'delete',
                     'terminate', 'alterresv'):
            if ret['out']:
                return int(ret['out'][0])
            else:
                return 1

        elif cmd in ('manager', 'select', 'status'):
            return eval(out[0])

    def alterresv(self, resvid, attrib, extend=None, runas=None,
                  logerr=True):
        """
        Alter attributes associated to a reservation. Raises
        ``PbsResvAlterError`` on error.

        :param resvid: identifier of the reservation.
        :type resvid: str.
        :param attrib: A dictionary of attributes to set.
        :type attrib: dictionary.
        :param extend: extend options.
        :param runas: run as user.
        :type runas: str or None.
        :param logerr: If False, CLI commands do not log error,
                       i.e. silent mode.
        :type logerr: bool.
        :raises: PbsResvAlterError.
        """
        prefix = 'reservation alter on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': ' + resvid

        if attrib is not None:
            prefix += ' %s' % (str(attrib))
        self.logger.info(prefix)

        c = None
        resvid = resvid.split()
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'pbs_ralter')]
            if attrib is not None:
                if extend is not None:
                    attrib['extend'] = extend
                _conf = self.default_client_pbs_conf
                pcmd += self.utils.convert_to_cli(attrib, op=IFL_RALTER,
                                                  hostname=self.client,
                                                  dflt_conf=_conf)
            pcmd += resvid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            if ret['out'] != ['']:
                self.last_out = ret['out']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('alterresv', resvid, runas, data=attrib,
                                 extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            a = self.utils.convert_to_attrl(attrib)
            rc = pbs_modify_resv(c, resvid, a, extend)

        if rc != 0:
            raise PbsResvAlterError(rc=rc, rv=False, msg=self.geterrmsg(),
                                    post=self._disconnect, conn=c)
        else:
            return rc

        if c:
            self._disconnect(c)

    def expect(self, obj_type, attrib=None, id=None, op=EQ, attrop=PTL_AND,
               attempt=0, max_attempts=None, interval=None, count=None,
               extend=None, offset=0, runas=None, level=logging.INFO,
               msg=None, trigger_sched_cycle=True):
        """
        expect an attribute to match a given value as per an
        operation.

        :param obj_type: The type of object to query, JOB, SERVER,
                         SCHEDULER, QUEUE, NODE
        :type obj_type: str
        :param attrib: Attributes to query, can be a string, a list,
                       or a dict
        :type attrib: str or list or dictionary
        :param id: The id of the object to act upon
        :param op: An operation to perform on the queried data,
                   e.g., EQ, SET, LT,..
        :param attrop: Operation on multiple attributes, either
                       PTL_AND, PTL_OR when an PTL_AND is used, only
                       batch objects having all matches are
                       returned, otherwise an OR is applied
        :param attempt: The number of times this function has been
                        called
        :type attempt: int
        :param max_attempts: The maximum number of attempts to
                             perform
        :type max_attempts: int or None
        :param interval: The interval time between attempts.
        :param count: If True, attrib will be accumulated using
                      function counter
        :type count: bool
        :param extend: passed to the stat call
        :param offset: the time to wait before the initial check.
                       Defaults to 0.
        :type offset: int
        :param runas: query as a given user. Defaults to current
                      user
        :type runas: str or None
        :param msg: Message from last call of this function, this
                    message will be used while raising
                    PtlExpectError.
        :type msg: str or None
        :param trigger_sched_cycle: True by default can be set to False if
                          kicksched_action is not supposed to be called
        :type trigger_sched_cycle: Boolean

        :returns: True if attributes are as expected

        :raises: PtlExpectError if attributes are not as expected
        """

        if attempt == 0 and offset > 0:
            self.logger.log(level, self.logprefix + 'expect offset set to ' +
                            str(offset))
            time.sleep(offset)

        if attrib is None:
            attrib = {}

        if ATTR_version in attrib and max_attempts is None:
            max_attempts = 3

        if max_attempts is None:
            max_attempts = self.ptl_conf['max_attempts']

        if interval is None:
            interval = self.ptl_conf['attempt_interval']

        if attempt >= max_attempts:
            _msg = "expected on " + self.logprefix + msg
            raise PtlExpectError(rc=1, rv=False, msg=_msg)

        if obj_type == SERVER and id is None:
            id = self.hostname

        if isinstance(attrib, str):
            attrib = {attrib: ''}
        elif isinstance(attrib, list):
            d = {}
            for l in attrib:
                d[l] = ''
            attrib = d

        # Add check for substate=42 for jobstate=R, if not added explicitly.
        if obj_type == JOB:
            add_attribs = {}
            substate = False
            for k, v in attrib.items():
                if k == 'job_state' and ((isinstance(v, tuple) and
                                          'R' in v[-1]) or v == 'R'):
                    add_attribs['substate'] = 42
                elif k == 'job_state=R':
                    add_attribs['substate=42'] = v
                elif 'substate' in k:
                    substate = True
            if add_attribs and not substate:
                attrib.update(add_attribs)
                attrop = PTL_AND
            del add_attribs, substate

        prefix = 'expect on ' + self.logprefix
        msg = []
        attrs_to_ignore = []
        for k, v in attrib.items():
            args = None
            if isinstance(v, tuple):
                operator = v[0]
                if len(v) > 2:
                    args = v[2:]
                val = v[1]
            else:
                operator = op
                val = v
            if operator not in PTL_OP_TO_STR:
                self.logger.log(level, "Operator not supported by expect(), "
                                "cannot verify change in " + str(k))
                attrs_to_ignore.append(k)
                continue
            msg += [k, PTL_OP_TO_STR[operator].strip()]
            if isinstance(val, collections.Callable):
                msg += ['callable(' + val.__name__ + ')']
                if args is not None:
                    msg.extend([str(x) for x in args])
            else:
                msg += [str(val)]
            msg += [PTL_ATTROP_TO_STR[attrop]]

        # Delete the attributes that we cannot verify
        for k in attrs_to_ignore:
            del(attrib[k])

        if attrs_to_ignore and len(attrib) < 1 and op == SET:
            return True

        # remove the last converted PTL_ATTROP_TO_STR
        if len(msg) > 1:
            msg = msg[:-1]

        if len(attrib) == 0:
            msg += [PTL_OP_TO_STR[op]]

        msg += [PBS_OBJ_MAP[obj_type]]
        if id is not None:
            msg += [str(id)]
        if attempt > 0:
            msg += ['attempt:', str(attempt + 1)]

        # Default count to True if the attribute contains an '=' in its name
        # for example 'job_state=R' implies that a count of job_state is needed
        if count is None and self.utils.operator_in_attribute(attrib):
            count = True

        if count:
            newattr = self.utils.convert_attributes_by_op(attrib)
            if len(newattr) == 0:
                newattr = attrib

            statlist = [self.counter(obj_type, newattr, id, extend, op=op,
                                     attrop=attrop, level=logging.DEBUG,
                                     runas=runas)]
        else:
            try:
                statlist = self.status(obj_type, attrib, id=id,
                                       level=logging.DEBUG, extend=extend,
                                       runas=runas, logerr=False)
            except PbsStatusError:
                statlist = []

        if (statlist is None or len(statlist) == 0 or
                statlist[0] is None or len(statlist[0]) == 0):
            if op == UNSET or list(set(attrib.values())) == [0]:
                self.logger.log(level, prefix + " ".join(msg) + ' ...  OK')
                return True
            else:
                time.sleep(interval)
                msg = " no data for " + " ".join(msg)
                self.logger.log(level, prefix + msg)
                return self.expect(obj_type, attrib, id, op, attrop,
                                   attempt + 1, max_attempts, interval, count,
                                   extend, level=level, msg=msg)

        if attrib is None:
            time.sleep(interval)
            return self.expect(obj_type, attrib, id, op, attrop, attempt + 1,
                               max_attempts, interval, count, extend,
                               runas=runas, level=level, msg=" ".join(msg))
        inp_op = op
        for k, v in attrib.items():
            varargs = None
            if isinstance(v, tuple):
                op = v[0]
                if len(v) > 2:
                    varargs = v[2:]
                v = v[1]
            else:
                op = inp_op

            for stat in statlist:
                if k not in stat:
                    if op == UNSET:
                        continue

                    # Sometimes users provide the wrong case for attributes
                    # Convert to lowercase and compare
                    attrs_lower = {
                        ks.lower(): [ks, vs] for ks, vs in stat.items()}
                    k_lower = k.lower()
                    if k_lower not in attrs_lower:
                        time.sleep(interval)
                        _tsc = trigger_sched_cycle
                        return self.expect(obj_type, attrib, id, op, attrop,
                                           attempt + 1, max_attempts,
                                           interval, count, extend,
                                           level=level, msg=" ".join(msg),
                                           trigger_sched_cycle=_tsc)
                    stat_v = attrs_lower[k_lower][1]
                    stat_k = attrs_lower[k_lower][0]
                else:
                    stat_v = stat[k]
                    stat_k = k

                if stat_k == ATTR_version:
                    m = self.version_tag.match(stat_v)
                    if m:
                        stat_v = m.group('version')
                    else:
                        time.sleep(interval)
                        return self.expect(obj_type, attrib, id, op, attrop,
                                           attempt + 1, max_attempts, interval,
                                           count, extend, runas=runas,
                                           level=level, msg=" ".join(msg))

                # functions/methods are invoked and their return value
                # used on expect
                if isinstance(v, collections.Callable):
                    if varargs is not None:
                        rv = v(stat_v, *varargs)
                    else:
                        rv = v(stat_v)
                    if isinstance(rv, bool):
                        if op == NOT:
                            if not rv:
                                continue
                        if rv:
                            continue
                    else:
                        v = rv

                stat_v = self.utils.decode_value(stat_v)
                v = self.utils.decode_value(str(v))

                if stat_k == ATTR_version:
                    stat_v = LooseVersion(str(stat_v))
                    v = LooseVersion(str(v))

                if op == EQ and stat_v == v:
                    continue
                elif op == SET and count and stat_v == v:
                    continue
                elif op == SET and count in (False, None):
                    continue
                elif op == NE and stat_v != v:
                    continue
                elif op == LT:
                    if stat_v < v:
                        continue
                elif op == GT:
                    if stat_v > v:
                        continue
                elif op == LE:
                    if stat_v <= v:
                        continue
                elif op == GE:
                    if stat_v >= v:
                        continue
                elif op == MATCH_RE:
                    if re.search(str(v), str(stat_v)):
                        continue
                elif op == MATCH:
                    if str(stat_v).find(str(v)) != -1:
                        continue

                msg += [' got: ' + stat_k + ' = ' + str(stat_v)]
                self.logger.info(prefix + " ".join(msg))
                time.sleep(interval)

                # run custom actions defined for this object type
                if trigger_sched_cycle and self.actions:
                    for act_obj in self.actions.get_actions_by_type(obj_type):
                        if act_obj.enabled:
                            act_obj.action(self, obj_type, attrib, id, op,
                                           attrop)
                return self.expect(obj_type, attrib, id, op, attrop,
                                   attempt + 1, max_attempts, interval, count,
                                   extend, level=level, msg=" ".join(msg),
                                   trigger_sched_cycle=trigger_sched_cycle)

        self.logger.log(level, prefix + " ".join(msg) + ' ...  OK')
        return True

    def is_history_enabled(self):
        """
        Short-hand method to return the value of job_history_enable
        """
        a = ATTR_JobHistoryEnable
        attrs = self.status(SERVER, level=logging.DEBUG)[0]
        if ((a in attrs.keys()) and attrs[a] == 'True'):
            return True
        return False

    def cleanup_jobs(self):
        """
        Helper function to delete all jobs.
        By default this method will determine whether
        job_history_enable is on and will cleanup all history
        jobs. Specifying an extend parameter could override
        this behavior.
        """
        delete_xt = 'force'
        select_xt = None
        if self.is_history_enabled():
            delete_xt += 'deletehist'
            select_xt = 'x'
        jobs = self.status(JOB, extend=select_xt)
        job_ids = sorted(list(set([x['id'] for x in jobs])))
        running_jobs = sorted([j['id'] for j in jobs if j['job_state'] == 'R'])
        host_pid_map = {}
        for job in jobs:
            exec_host = job.get('exec_host', None)
            if not exec_host or 'session_id' not in job:
                continue
            _host = exec_host.split('/')[0].split(':')[0]
            if _host not in host_pid_map:
                host_pid_map.setdefault(_host, [])
            host_pid_map[_host].append(job['session_id'])

        # Turn off scheduling so jobs don't start when trying to
        # delete. Restore the orignial scheduling state
        # once jobs are deleted.
        sched_state = []
        scheds = self.status(SCHED)
        for sc in scheds:
            if sc['scheduling'] == 'True':
                sched_state.append(sc['id'])
                # runas is required here because some tests remove
                # current user from managers list
                a = {'scheduling': 'False'}
                self.manager(MGR_CMD_SET, SCHED, a, id=sc['id'],
                             runas=ROOT_USER)
        try:
            self.deljob(id=job_ids, extend=delete_xt,
                        runas=ROOT_USER, wait=False)
        except PbsDeljobError:
            pass
        st = time.time()
        if len(job_ids) > 100:
            for host, pids in host_pid_map.items():
                chunks = [pids[i:i + 5000] for i in range(0, len(pids), 5000)]
                for chunk in chunks:
                    self.du.run_cmd(host, ['kill', '-9'] + chunk,
                                    runas=ROOT_USER, logerr=False)
            if running_jobs:
                last_running_job = running_jobs[-1]
                _msg = last_running_job + ';'
                _msg += 'Job Obit notice received has error 15001'
                try:
                    self.log_match(_msg, starttime=st, interval=10,
                                   max_attempts=10)
                except PtlLogMatchError:
                    # don't fail on log match error as here purpose
                    # of log match is to allow mom to catch up with
                    # sigchild but we don't want to wait too long
                    # so limit max attempts to 10 ~ total 100 sec
                    # of wait
                    pass
        rv = self.expect(JOB, {'job_state': 0}, count=True, op=SET)
        # restore 'scheduling' state
        for sc in sched_state:
            a = {'scheduling': 'True'}
            self.manager(MGR_CMD_SET, SCHED, a, id=sc, runas=ROOT_USER)
            self.expect(SCHED, a, id=sc)
        return rv

    def cleanup_reservations(self):
        """
        Helper function to delete all reservations
        """
        reservations = self.status(RESV, runas=ROOT_USER)
        while reservations:
            resvs = [r['id'] for r in reservations]
            if len(resvs) > 0:
                try:
                    self.delresv(resvs, runas=ROOT_USER)
                except:
                    pass
                reservations = self.status(RESV, runas=ROOT_USER)

    def cleanup_jobs_and_reservations(self):
        """
        Helper function to delete all jobs and reservations
        """
        rv = self.cleanup_jobs()
        self.cleanup_reservations()
        return rv

    def update_attributes(self, obj_type, bs, overwrite=False):
        """
        Populate objects from batch status data
        """
        if bs is None:
            return

        for binfo in bs:
            if 'id' not in binfo:
                continue
            id = binfo['id']
            obj = None
            if obj_type == JOB:
                if ATTR_owner in binfo:
                    user = binfo[ATTR_owner].split('@')[0]
                else:
                    user = None
                if id in self.jobs:
                    if overwrite:
                        self.jobs[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.jobs[id].attributes.update(binfo)
                    if self.jobs[id].username != user:
                        self.jobs[id].username = user
                else:
                    self.jobs[id] = Job(user, binfo)
                obj = self.jobs[id]
            elif obj_type in (VNODE, NODE):
                if id in self.nodes:
                    if overwrite:
                        self.nodes[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.nodes[id].attributes.update(binfo)
                else:
                    self.nodes[id] = get_mom_obj(id, binfo,
                                                 snapmap={NODE: None},
                                                 server=self)
                obj = self.nodes[id]
            elif obj_type == SERVER:
                if overwrite:
                    self.attributes = copy.deepcopy(binfo)
                else:
                    self.attributes.update(binfo)
                obj = self
            elif obj_type == QUEUE:
                if id in self.queues:
                    if overwrite:
                        self.queues[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.queues[id].attributes.update(binfo)
                else:
                    self.queues[id] = Queue(id, binfo, server=self)
                obj = self.queues[id]
            elif obj_type == RESV:
                if id in self.reservations:
                    if overwrite:
                        self.reservations[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.reservations[id].attributes.update(binfo)
                else:
                    self.reservations[id] = Reservation(id, binfo)
                obj = self.reservations[id]
            elif obj_type == HOOK:
                if id in self.hooks:
                    if overwrite:
                        self.hooks[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.hooks[id].attributes.update(binfo)
                else:
                    self.hooks[id] = Hook(id, binfo, server=self)
                obj = self.hooks[id]
            elif obj_type == PBS_HOOK:
                if id in self.pbshooks:
                    if overwrite:
                        self.pbshooks[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.pbshooks[id].attributes.update(binfo)
                else:
                    self.pbshooks[id] = Hook(id, binfo, server=self)
                obj = self.pbshooks[id]
            elif obj_type == SCHED:
                if id in self.schedulers:
                    if overwrite:
                        self.schedulers[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.schedulers[id].attributes.update(binfo)
                    if 'sched_priv' in binfo:
                        self.schedulers[id].setup_sched_priv(
                            binfo['sched_priv'])
                else:
                    if 'sched_host' not in binfo:
                        hostname = self.hostname
                    else:
                        hostname = binfo['sched_host']
                    if SCHED in self.snapmap:
                        snap = self.snap
                        snapmap = self.snapmap
                    else:
                        snap = None
                        snapmap = {}
                    spriv = None
                    if 'sched_priv' in binfo:
                        spriv = binfo['sched_priv']
                    self.schedulers[id] = get_sched_obj(hostname=hostname,
                                                        server=self,
                                                        snap=snap,
                                                        snapmap=snapmap,
                                                        id=id,
                                                        sched_priv=spriv)
                    if overwrite:
                        self.schedulers[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.schedulers[id].attributes.update(binfo)
                obj = self.schedulers[id]

            elif obj_type == RSC:
                if id in self.resources:
                    if overwrite:
                        self.resources[id].attributes = copy.deepcopy(binfo)
                    else:
                        self.resources[id].attributes.update(binfo)
                else:
                    rtype = None
                    rflag = None
                    if 'type' in binfo:
                        rtype = binfo['type']
                    if 'flag' in binfo:
                        rflag = binfo['flag']
                    self.resources[id] = Resource(id, rtype, rflag)

            if obj is not None:
                self.utils.update_attributes_list(obj)
                obj.__dict__.update(binfo)

    def counter(self, obj_type=None, attrib=None, id=None, extend=None,
                op=None, attrop=None, bslist=None, level=logging.INFO,
                idonly=True, grandtotal=False, db_access=None, runas=None,
                resolve_indirectness=False):
        """
        Accumulate properties set on an object. For example, to
        count number of free nodes:
        ``server.counter(VNODE,{'state':'free'})``

        :param obj_type: The type of object to query, one of the
                         * objects
        :param attrib: Attributes to query, can be a string, a
                       list, a dictionary
        :type attrib: str or list or dictionary
        :param id: The id of the object to act upon
        :param extend: The extended parameter to pass to the stat
                       call
        :param op: The operation used to match attrib to what is
                   queried. SET or None
        :type op: str or None
        :param attrop: Operation on multiple attributes, either
                       PTL_AND, PTL_OR
        :param bslist: Optional, use a batch status dict list
                       instead of an obj_type
        :param idonly: if true, return the name/id of the matching
                       objects
        :type idonly: bool
        :param db_access: credentials to access db, either a path
                          to file or dictionary
        :type db_access: str or dictionary
        :param runas: run as user
        :type runas: str or None
        """
        self.logit('counter: ', obj_type, attrib, id, level=level)
        return self._filter(obj_type, attrib, id, extend, op, attrop, bslist,
                            PTL_COUNTER, idonly, grandtotal, db_access,
                            runas=runas,
                            resolve_indirectness=resolve_indirectness)

    def filter(self, obj_type=None, attrib=None, id=None, extend=None, op=None,
               attrop=None, bslist=None, idonly=True, grandtotal=False,
               db_access=None, runas=None, resolve_indirectness=False):
        """
        Filter objects by properties. For example, to filter all
        free nodes:``server.filter(VNODE,{'state':'free'})``

        For each attribute queried, if idonly is True, a list of
        matching object names is returned; if idonly is False, then
        the value of each attribute queried is returned.

        This is unlike Python's built-in 'filter' that returns a
        subset of objects matching from a pool of objects. The
        Python filtering mechanism remains very useful in some
        situations and should be used programmatically to achieve
        desired filtering goals that can not be met easily with
        PTL's filter method.

        :param obj_type: The type of object to query, one of the
                         * objects
        :param attrib: Attributes to query, can be a string, a
                       list, a dictionary
        :type attrib: str or list or dictionary
        :param id: The id of the object to act upon
        :param extend: The extended parameter to pass to the stat
                       call
        :param op: The operation used to match attrib to what is
                   queried. SET or None
        :type op: str or None
        :param bslist: Optional, use a batch status dict list
                       instead of an obj_type
        :type bslist: List or None
        :param idonly: if true, return the name/id of the matching
                       objects
        :type idonly: bool
        :param db_access: credentials to access db, either path to
                          file or dictionary
        :type db_access: str or dictionary
        :param runas: run as user
        :type runas: str or None
        """
        self.logit('filter: ', obj_type, attrib, id)
        return self._filter(obj_type, attrib, id, extend, op, attrop, bslist,
                            PTL_FILTER, idonly, db_access, runas=runas,
                            resolve_indirectness=resolve_indirectness)

    def _filter(self, obj_type=None, attrib=None, id=None, extend=None,
                op=None, attrop=None, bslist=None, mode=PTL_COUNTER,
                idonly=True, grandtotal=False, db_access=None, runas=None,
                resolve_indirectness=False):

        if bslist is None:
            try:
                _a = resolve_indirectness
                tmp_bsl = self.status(obj_type, attrib, id,
                                      level=logging.DEBUG, extend=extend,
                                      db_access=db_access, runas=runas,
                                      resolve_indirectness=_a)
                del _a
            except PbsStatusError:
                return None

            bslist = self.utils.filter_batch_status(tmp_bsl, attrib)
            del tmp_bsl

        if bslist is None:
            return None

        if isinstance(attrib, str):
            attrib = attrib.split(',')

        total = {}
        for bs in bslist:
            if isinstance(attrib, list):
                # when filtering on multiple values, ensure that they are
                # all present on the object, otherwise skip
                if attrop == PTL_AND:
                    match = True
                    for k in attrib:
                        if k not in bs:
                            match = False
                    if not match:
                        continue

                for a in attrib:
                    if a in bs:
                        if op == SET:
                            k = a
                        else:
                            # Since this is a list of attributes, no operator
                            # was provided so we settle on "equal"
                            k = a + '=' + str(bs[a])
                        if mode == PTL_COUNTER:
                            amt = 1
                            if grandtotal:
                                amt = self.utils.decode_value(bs[a])
                                if not isinstance(amt, (int, float)):
                                    amt = 1
                                if a in total:
                                    total[a] += amt
                                else:
                                    total[a] = amt
                            else:
                                if k in total:
                                    total[k] += amt
                                else:
                                    total[k] = amt
                        elif mode == PTL_FILTER:
                            if k in total:
                                if idonly:
                                    total[k].append(bs['id'])
                                else:
                                    total[k].append(bs)
                            else:
                                if idonly:
                                    total[k] = [bs['id']]
                                else:
                                    total[k] = [bs]
                        else:
                            self.logger.error("Unhandled mode " + str(mode))
                            return None

            elif isinstance(attrib, dict):
                tmptotal = {}  # The running count that will be used for total

                # when filtering on multiple values, ensure that they are
                # all present on the object, otherwise skip
                match = True
                for k, v in attrib.items():
                    if k not in bs:
                        match = False
                        if attrop == PTL_AND:
                            break
                        else:
                            continue
                    amt = self.utils.decode_value(bs[k])
                    if isinstance(v, tuple):
                        op = v[0]
                        val = self.utils.decode_value(v[1])
                    elif op == SET:
                        val = None
                        pass
                    else:
                        op = EQ
                        val = self.utils.decode_value(v)

                    if ((op == LT and amt < val) or
                            (op == LE and amt <= val) or
                            (op == EQ and amt == val) or
                            (op == GE and amt >= val) or
                            (op == GT and amt > val) or
                            (op == NE and amt != val) or
                            (op == MATCH and str(amt).find(str(val)) != -1) or
                            (op == MATCH_RE and
                             re.search(str(val), str(amt))) or
                            (op == SET)):
                        # There is a match, proceed to track the attribute
                        self._filter_helper(bs, k, val, amt, op, mode,
                                            tmptotal, idonly, grandtotal)
                    elif attrop == PTL_AND:
                        match = False
                        if mode == PTL_COUNTER:
                            # requesting specific key/value pairs should result
                            # in 0 available elements
                            tmptotal[str(k) + PTL_OP_TO_STR[op] + str(val)] = 0
                        break
                    elif mode == PTL_COUNTER:
                        tmptotal[str(k) + PTL_OP_TO_STR[op] + str(val)] = 0

                if attrop != PTL_AND or (attrop == PTL_AND and match):
                    for k, v in tmptotal.items():
                        if k not in total:
                            total[k] = v
                        else:
                            total[k] += v
        return total

    def _filter_helper(self, bs, k, v, amt, op, mode, total, idonly,
                       grandtotal):
        # default operation to '='
        if op is None or op not in PTL_OP_TO_STR:
            op = '='
        op_str = PTL_OP_TO_STR[op]

        if op == SET:
            # override PTL_OP_TO_STR fro SET operations
            op_str = ''
            v = ''

        ky = k + op_str + str(v)
        if mode == PTL_COUNTER:
            incr = 1
            if grandtotal:
                if not isinstance(amt, (int, float)):
                    incr = 1
                else:
                    incr = amt
            if ky in total:
                total[ky] += incr
            else:
                total[ky] = incr
        elif mode == PTL_FILTER:
            if ky in total:
                if idonly:
                    total[ky].append(bs['id'])
                else:
                    total[ky].append(bs)
            else:
                if idonly:
                    total[ky] = [bs['id']]
                else:
                    total[ky] = [bs]

    def logit(self, msg, obj_type, attrib, id, level=logging.INFO):
        """
        Generic logging routine for ``IFL`` commands

        :param msg: The message to log
        :type msg: str
        :param obj_type: object type, i.e *
        :param attrib: attributes to log
        :param id: name of object to log
        :type id: str or list
        :param level: log level, defaults to ``INFO``
        """
        s = []
        if self.logger is not None:
            if obj_type is None:
                obj_type = MGR_OBJ_NONE
            s = [msg + PBS_OBJ_MAP[obj_type]]
            if id:
                if isinstance(id, list):
                    s += [' ' + ",".join(id)]
                else:
                    s += [' ' + str(id)]
            if attrib:
                s += [' ' + str(attrib)]
            self.logger.log(level, "".join(s))

    def equivalence_classes(self, obj_type=None, attrib={}, bslist=None,
                            op=RESOURCES_AVAILABLE, show_zero_resources=True,
                            db_access=None, resolve_indirectness=False):
        """
        :param obj_type: PBS Object to query, one of *
        :param attrib: attributes to build equivalence classes
                       out of.
        :type attrib: dictionary
        :param bslist: Optional, list of dictionary representation
                       of a batch status
        :type bslist: List
        :param op: set to RESOURCES_AVAILABLE uses the dynamic
                   amount of resources available, i.e., available -
                   assigned, otherwise uses static amount of
                   resources available
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        """

        if attrib is None:
            attrib = {}

        if len(attrib) == 0 and obj_type is not None:
            if obj_type in (VNODE, NODE):
                attrib = ['resources_available.ncpus',
                          'resources_available.mem', 'state']
            elif obj_type == JOB:
                attrib = ['Resource_List.select',
                          'queue', 'array_indices_submitted']
            elif obj_type == RESV:
                attrib = ['Resource_List.select']
            else:
                return {}

        if bslist is None and obj_type is not None:
            # To get the resources_assigned we must stat the entire object so
            # bypass the specific attributes that would filter out assigned
            if op == RESOURCES_AVAILABLE:
                bslist = self.status(obj_type, None, level=logging.DEBUG,
                                     db_access=db_access,
                                     resolve_indirectness=resolve_indirectness)
            else:
                bslist = self.status(obj_type, attrib, level=logging.DEBUG,
                                     db_access=db_access,
                                     resolve_indirectness=resolve_indirectness)

        if bslist is None or len(bslist) == 0:
            return {}

        # automatically convert an objectlist into a batch status dict list
        # for ease of use.
        if not isinstance(bslist[0], dict):
            bslist = self.utils.objlist_to_dictlist(bslist)

        if isinstance(attrib, str):
            attrib = attrib.split(',')

        self.logger.debug("building equivalence class")
        equiv = {}
        for bs in bslist:
            cls = ()
            skip_cls = False
            # attrs will be part of the EquivClass object
            attrs = {}
            # Filter the batch attributes by the attribs requested
            for a in attrib:
                if a in bs:
                    amt = self.utils.decode_value(bs[a])
                    if a.startswith('resources_available.'):
                        val = a.replace('resources_available.', '')
                        if (op == RESOURCES_AVAILABLE and
                                'resources_assigned.' + val in bs):
                            amt = (int(amt) - int(self.utils.decode_value(
                                   bs['resources_assigned.' + val])))
                        # this case where amt goes negative is not a bug, it
                        # may happen when computing whats_available due to the
                        # fact that the computation is subtractive, it does
                        # add back resources when jobs/reservations end but
                        # is only concerned with what is available now for
                        # a given duration, that is why in the case where
                        # amount goes negative we set it to 0
                        if amt < 0:
                            amt = 0

                        # TODO: not a failproof way to catch a memory type
                        # but PbsTypeSize should return the right value if
                        # it fails to parse it as a valid memory value
                        if a.endswith('mem'):
                            try:
                                amt = PbsTypeSize().encode(amt)
                            except:
                                # we guessed the type incorrectly
                                pass
                    else:
                        val = a
                    if amt == 0 and not show_zero_resources:
                        skip_cls = True
                        break
                    # Build the key of the equivalence class
                    cls += (val + '=' + str(amt),)
                    attrs[val] = amt
            # Now that we are done with this object, add it to an equiv class
            if len(cls) > 0 and not skip_cls:
                if cls in equiv:
                    equiv[cls].add_entity(bs['id'])
                else:
                    equiv[cls] = EquivClass(cls, attrs, [bs['id']])

        return list(equiv.values())

    def show_equivalence_classes(self, eq=None, obj_type=None, attrib={},
                                 bslist=None, op=RESOURCES_AVAILABLE,
                                 show_zero_resources=True, db_access=None,
                                 resolve_indirectness=False):
        """
        helper function to show the equivalence classes

        :param eq: equivalence classes as compute by
                   equivalence_classes see equivalence_classes
                   for remaining parameters description
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        """
        if eq is None:
            equiv = self.equivalence_classes(obj_type, attrib, bslist, op,
                                             show_zero_resources, db_access,
                                             resolve_indirectness)
        else:
            equiv = eq
        equiv = sorted(equiv, key=lambda e: len(e.entities))
        for e in equiv:
            # e.show()
            print((str(e)))

    def whats_available(self, attrib=None, jobs=None, resvs=None, nodes=None):
        """
        Returns what's available as a list of node equivalence
        classes listed by availability over time.

        :param attrib: attributes to consider
        :type attrib: List
        :param jobs: jobs to consider, if None, jobs are queried
                     locally
        :param resvs: reservations to consider, if None, they are
                      queried locally
        :param nodes: nodes to consider, if None, they are queried
                      locally
        """

        if attrib is None:
            attrib = ['resources_available.ncpus',
                      'resources_available.mem', 'state']

        if resvs is None:
            self.status(RESV)
            resvs = self.reservations

        if jobs is None:
            self.status(JOB)
            jobs = self.jobs

        if nodes is None:
            self.status(NODE)
            nodes = self.nodes

        nodes_id = list(nodes.keys())
        avail_nodes_by_time = {}

        def alloc_resource(self, node, resources):
            # helper function. Must work on a scratch copy of nodes otherwise
            # resources_available will get corrupted
            for rsc, value in resources.items():
                if isinstance(value, int) or value.isdigit():
                    avail = node.attributes['resources_available.' + rsc]
                    nvalue = int(avail) - int(value)
                    node.attributes['resources_available.' + rsc] = nvalue

        # Account for reservations
        for resv in resvs.values():
            resvnodes = resv.execvnode('resv_nodes')
            if resvnodes:
                starttime = self.utils.convert_stime_to_seconds(
                    resv.attributes['reserve_start'])
                for node in resvnodes:
                    for n, resc in node.items():
                        tm = int(starttime) - int(self.ctime)
                        if tm < 0 or n not in nodes_id:
                            continue
                        if tm not in avail_nodes_by_time:
                            avail_nodes_by_time[tm] = []
                        if nodes[n].attributes['sharing'] in ('default_excl',
                                                              'force_excl'):
                            avail_nodes_by_time[tm].append(nodes[n])
                            try:
                                nodes_id.remove(n)
                            except:
                                pass
                        else:
                            ncopy = copy.copy(nodes[n])
                            ncopy.attributes = copy.deepcopy(
                                nodes[n].attributes)
                            avail_nodes_by_time[tm].append(ncopy)
                            self.alloc_resource(nodes[n], resc)

        # go on to look at the calendar of scheduled jobs to run and set
        # the node availability according to when the job is estimated to
        # start on the node
        for job in self.jobs.values():
            if (job.attributes['job_state'] != 'R' and
                    'estimated.exec_vnode' in job.attributes):
                estimatednodes = job.execvnode('estimated.exec_vnode')
                if estimatednodes:
                    st = job.attributes['estimated.start_time']
                    # Tweak for nas format of estimated time that has
                    # num seconds from epoch followed by datetime
                    if st.split()[0].isdigit():
                        starttime = st.split()[0]
                    else:
                        starttime = self.utils.convert_stime_to_seconds(st)
                    for node in estimatednodes:
                        for n, resc in node.items():
                            tm = int(starttime) - int(self.ctime)
                            if (tm < 0 or n not in nodes_id or
                                    nodes[n].state != 'free'):
                                continue
                            if tm not in avail_nodes_by_time:
                                avail_nodes_by_time[tm] = []
                            if (nodes[n].attributes['sharing'] in
                                    ('default_excl', 'force_excl')):
                                avail_nodes_by_time[tm].append(nodes[n])
                                try:
                                    nodes_id.remove(n)
                                except:
                                    pass
                            else:
                                ncopy = copy.copy(nodes[n])
                                ncopy.attributes = copy.deepcopy(
                                    nodes[n].attributes)
                                avail_nodes_by_time[tm].append(ncopy)
                                self.alloc_resource(nodes[n], resc)

        # remaining nodes are free "forever"
        for node in nodes_id:
            if self.nodes[node].state == 'free':
                if 'infinity' not in avail_nodes_by_time:
                    avail_nodes_by_time['infinity'] = [nodes[node]]
                else:
                    avail_nodes_by_time['infinity'].append(nodes[node])

        # if there is a dedicated time, move the availaility time up to that
        # time as necessary
        if self.schedulers[self.dflt_sched_name] is None:
            self.schedulers[self.dflt_sched_name] = get_sched_obj(server=self)

        self.schedulers[self.dflt_sched_name].parse_dedicated_time()

        if self.schedulers[self.dflt_sched_name].dedicated_time:
            dedtime = self.schedulers[
                self.dflt_sched_name].dedicated_time[0]['from'] - int(
                self.ctime)
            if dedtime <= int(time.time()):
                dedtime = None
        else:
            dedtime = None

        # finally, build the equivalence classes off of the nodes availability
        # over time
        self.logger.debug("Building equivalence classes")
        whazzup = {}
        if 'state' in attrib:
            attrib.remove('state')
        for tm, nds in avail_nodes_by_time.items():
            equiv = self.equivalence_classes(VNODE, attrib, bslist=nds,
                                             show_zero_resources=False)
            if dedtime and (tm > dedtime or tm == 'infinity'):
                tm = dedtime
            if tm != 'infinity':
                tm = str(datetime.timedelta(seconds=int(tm)))
            whazzup[tm] = equiv

        return whazzup

    def show_whats_available(self, wa=None, attrib=None, jobs=None,
                             resvs=None, nodes=None):
        """
        helper function to show availability as computed by
        whats_available

        :param wa: a dictionary of available attributes. see
                   whats_available for a\
                   description of the remaining parameters
        :type wa: Dictionary
        """
        if wa is None:
            wa = self.whats_available(attrib, jobs, resvs, nodes)
        if len(wa) > 0:
            print(("%24s\t%s" % ("Duration of availability", "Resources")))
            print("-------------------------\t----------")
        swa = sorted(wa.items(), key=lambda x: x[0])
        for (k, eq_classes) in swa:
            for eq_cl in eq_classes:
                print(("%24s\t%s" % (str(k), str(eq_cl))))

    def utilization(self, resources=None, nodes=None, jobs=None, entity={}):
        """
        Return utilization of consumable resources on a set of
        nodes

        :param nodes: A list of dictionary of nodes on which to
                      compute utilization.Defaults to nodes
                      resulting from a stat call to the current
                      server.
        :type nodes: List
        :param resources: comma-separated list of resources to
                          compute utilization on. The name of the
                          resource is for example, ncpus or mem
        :type resources: List
        :param entity: An optional dictionary of entities to
                       compute utilization of,
                       ``e.g. {'user':u1, 'group':g1, 'project'=p1}``
        :type entity: Dictionary

        The utilization is returned as a dictionary of percentage
        utilization for each resource.

        Non-consumable resources are silently ignored.
        """
        if nodes is None:
            nodes = self.status(NODE)

        if jobs is None:
            jobs = self.status(JOB)

        if resources is None:
            rescs = ['ncpus', 'mem']
        else:
            rescs = resources

        utilization = {}
        resavail = {}
        resassigned = {}
        usednodes = 0
        totnodes = 0
        nodes_set = set()

        for res in rescs:
            resavail[res] = 0
            resassigned[res] = 0

        # If an entity is specified utilization must be collected from the
        # Jobs usage, otherwise we can get the information directly from
        # the nodes.
        if len(entity) > 0 and jobs is not None:
            for job in jobs:
                if 'job_state' in job and job['job_state'] != 'R':
                    continue
                entity_match = True
                for k, v in entity.items():
                    if k not in job or job[k] != v:
                        entity_match = False
                        break
                if entity_match:
                    for res in rescs:
                        r = 'Resource_List.' + res
                        if r in job:
                            tmpr = int(self.utils.decode_value(job[r]))
                            resassigned[res] += tmpr
                    if 'exec_host' in job:
                        hosts = ResourceResv.get_hosts(job['exec_host'])
                        nodes_set |= set(hosts)

        for node in nodes:
            # skip nodes in non-schedulable state
            nstate = node['state']
            if ('down' in nstate or 'unavailable' in nstate or
                    'unknown' in nstate or 'Stale' in nstate):
                continue

            totnodes += 1

            # If an entity utilization was requested, all used nodes were
            # already filtered into the nodes_set specific to that entity, we
            # simply add them up. If no entity was requested, it suffices to
            # have the node have a jobs attribute to count it towards total
            # used nodes
            if len(entity) > 0:
                if node['id'] in nodes_set:
                    usednodes += 1
            elif 'jobs' in node:
                usednodes += 1

            for res in rescs:
                avail = 'resources_available.' + res
                if avail in node:
                    val = self.utils.decode_value(node[avail])
                    if isinstance(val, int):
                        resavail[res] += val

                        # When entity matching all resources assigned are
                        # accounted for by the job usage
                        if len(entity) == 0:
                            assigned = 'resources_assigned.' + res
                            if assigned in node:
                                val = self.utils.decode_value(node[assigned])
                                if isinstance(val, int):
                                    resassigned[res] += val

        for res in rescs:
            if res in resavail:
                if res in resassigned:
                    if resavail[res] > 0:
                        utilization[res] = [resassigned[res], resavail[res]]

        # Only report nodes utilization if no specific resources were requested
        if resources is None:
            utilization['nodes'] = [usednodes, totnodes]

        return utilization

    def create_vnodes(self, name=None, attrib=None, num=1, mom=None,
                      additive=False, sharednode=True, restart=True,
                      delall=True, natvnode=None, usenatvnode=False,
                      attrfunc=None, fname=None, vnodes_per_host=1,
                      createnode=True, expect=True):
        """
        helper function to create vnodes.

        :param name: prefix name of the vnode(s) to create
        :type name: str or None
        :param attrib: attributes to assign to each node
        :param num: the number of vnodes to create. Defaults to 1
        :type num: int
        :param mom: the MoM object on which the vnode definition is
                    to be inserted
        :param additive: If True, vnodes are added to the existing
                         vnode defs.Defaults to False.
        :type additive: bool
        :param sharednode: If True, all vnodes will share the same
                           host.Defaults to True.
        :type sharednode: bool
        :param restart: If True the MoM will be restarted.
        :type restart: bool
        :param delall: If True delete all server nodes prior to
                       inserting vnodes
        :type delall: bool
        :param natvnode: name of the natural vnode.i.e. The node
                         name in qmgr -c "create node <name>"
        :type natvnode: str or None
        :param usenatvnode: count the natural vnode as an
                            allocatable node.
        :type usenatvnode: bool
        :param attrfunc: an attribute=value function generator,
                         see create_vnode_def
        :param fname: optional name of the vnode def file
        :type fname: str or None
        :param vnodes_per_host: number of vnodes per host
        :type vnodes_per_host: int
        :param createnode: whether to create the node via manage or
                           not. Defaults to True
        :type createnode: bool
        :param expect: whether to expect attributes to be set or
                       not. Defaults to True
        :type expect: bool
        :returns: True on success and False otherwise
        """
        if mom is None or name is None or attrib is None:
            self.logger.error("name, attributes, and mom object are required")
            return False

        if natvnode is None:
            natvnode = mom.shortname

        if delall:
            try:
                rv = self.manager(MGR_CMD_DELETE, NODE, None, "")
                if rv != 0:
                    return False
            except PbsManagerError:
                pass

        vdef = mom.create_vnode_def(name, attrib, num, sharednode,
                                    usenatvnode=usenatvnode, attrfunc=attrfunc,
                                    vnodes_per_host=vnodes_per_host)
        mom.insert_vnode_def(vdef, fname=fname, additive=additive,
                             restart=restart)

        new_vnodelist = []
        if usenatvnode:
            new_vnodelist.append(natvnode)
            num_check = num - 1
        else:
            num_check = num
        for i in range(num_check):
            new_vnodelist.append("%s[%s]" % (name, i))

        if createnode:
            try:
                statm = self.status(NODE, id=natvnode)
            except:
                statm = []
            if len(statm) >= 1:
                _m = 'Mom %s already exists, not creating' % (natvnode)
                self.logger.info(_m)
            else:
                if mom.pbs_conf and 'PBS_MOM_SERVICE_PORT' in mom.pbs_conf:
                    m_attr = {'port': mom.pbs_conf['PBS_MOM_SERVICE_PORT']}
                else:
                    m_attr = None
                self.manager(MGR_CMD_CREATE, NODE, m_attr, natvnode)
        # only expect if vnodes were added rather than the nat vnode modified
        if expect and num > 0:
            attrs = {'state': 'free'}
            attrs.update(attrib)
            for vn in new_vnodelist:
                self.expect(VNODE, attrs, id=vn)
        return True

    def create_moms(self, name=None, attrib=None, num=1, delall=True,
                    createnode=True, conf_prefix='pbs.conf_m',
                    home_prefix='pbs_m', momhosts=None, init_port=15011,
                    step_port=2):
        """
        Create MoM configurations and optionall add them to the
        server. Unique ``pbs.conf`` files are defined and created
        on each hosts on which MoMs are to be created.

        :param name: Optional prefix name of the nodes to create.
                     Defaults to the name of the MoM host.
        :type name: str or None
        :param attrib: Optional node attributes to assign to the
                       MoM.
        :param num: Number of MoMs to create
        :type num: int
        :param delall: Whether to delete all nodes on the server.
                       Defaults to True.
        :type delall: bool
        :param createnode: Whether to create the nodes and add them
                           to the server.Defaults to True.
        :type createnode: bool
        :param conf_prefix: The prefix of the PBS conf file.Defaults
                            to pbs.conf_m
        :type conf_prefix: str
        :param home_prefix: The prefix of the PBS_HOME directory.
                            Defaults to pbs_m
        :type home_prefix: str
        :param momhosts: A list of hosts on which to deploy num
                         MoMs.
        :type momhosts: List
        :param init_port: The initial port number to start assigning
                          ``PBS_MOM_SERIVCE_PORT to.
                          Default 15011``.
        :type init_port: int
        :param step_port: The increments at which ports are
                          allocated. Defaults to 2.
        :type step_port: int

        .. note:: Since PBS requires that
                  PBS_MANAGER_SERVICE_PORT = PBS_MOM_SERVICE_PORT+1
                  The step number must be greater or equal to 2.
        """

        if not self.isUp():
            logging.error("An up and running PBS server on " + self.hostname +
                          " is required")
            return False

        if delall:
            try:
                rc = self.manager(MGR_CMD_DELETE, NODE, None, "")
            except PbsManagerError as e:
                rc = e.rc
            if rc:
                if len(self.status(NODE)) > 0:
                    self.logger.error("create_moms: Error deleting all nodes")
                    return False

        pi = PBSInitServices()
        if momhosts is None:
            momhosts = [self.hostname]

        if attrib is None:
            attrib = {}

        error = False
        for hostname in momhosts:
            _pconf = self.du.parse_pbs_config(hostname)
            if 'PBS_HOME' in _pconf:
                _hp = _pconf['PBS_HOME']
                if _hp.endswith('/'):
                    _hp = _hp[:-1]
                _hp = os.path.dirname(_hp)
            else:
                _hp = '/var/spool'
            _np_conf = _pconf
            _np_conf['PBS_START_SERVER'] = '0'
            _np_conf['PBS_START_SCHED'] = '0'
            _np_conf['PBS_START_MOM'] = '1'
            for i in range(0, num * step_port, step_port):
                _np = os.path.join(_hp, home_prefix + str(i))
                _n_pbsconf = os.path.join('/etc', conf_prefix + str(i))
                _np_conf['PBS_HOME'] = _np
                port = init_port + i
                _np_conf['PBS_MOM_SERVICE_PORT'] = str(port)
                _np_conf['PBS_MANAGER_SERVICE_PORT'] = str(port + 1)
                self.du.set_pbs_config(hostname, fout=_n_pbsconf,
                                       confs=_np_conf)
                pi.initd(hostname, conf_file=_n_pbsconf, op='start')
                m = get_mom_obj(hostname, pbsconf_file=_n_pbsconf)
                if m.isUp():
                    m.stop()
                if hostname != self.hostname:
                    m.add_config({'$clienthost': self.hostname})
                try:
                    m.start()
                except PbsServiceError:
                    # The service failed to start
                    self.logger.error("Service failed to start using port " +
                                      str(port) + "...skipping")
                    self.du.rm(hostname, _n_pbsconf)
                    continue
                if createnode:
                    attrib['Mom'] = hostname
                    attrib['port'] = port
                    if name is None:
                        name = hostname.split('.')[0]
                    _n = name + '-' + str(i)
                    rc = self.manager(MGR_CMD_CREATE, NODE, attrib, id=_n)
                    if rc != 0:
                        self.logger.error("error creating node " + _n)
                        error = True
        if error:
            return False

        return True

    def create_hook(self, name, attrs):
        """
        Helper function to create a hook by name.

        :param name: The name of the hook to create
        :type name: str
        :param attrs: The attributes to create the hook with.
        :type attrs: str
        :returns: False if hook already exists
        :raises: PbsManagerError, otherwise return True.
        """
        hooks = self.status(HOOK)
        if ((hooks is None or len(hooks) == 0) or
                (name not in [x['id'] for x in hooks])):
            self.manager(MGR_CMD_CREATE, HOOK, None, name)
        else:
            self.logger.error('hook named ' + name + ' exists')
            return False

        self.manager(MGR_CMD_SET, HOOK, attrs, id=name)
        return True

    def delete_hook(self, name):
        """
        Helper function to delete a hook by name.

        :param name: The name of the hook to delete
        :type name: str
        :returns: False if hook does not exist
        :raises: PbsManagerError, otherwise return True.
        """
        hooks = self.status(HOOK, level=logging.DEBUG)
        for hook in hooks:
            if hook['id'] == name:
                self.logger.info("Removing hook:%s" % name)
                self.manager(MGR_CMD_DELETE, HOOK, id=name)
        return True

    def import_hook(self, name, body, level=logging.INFO):
        """
        Helper function to import hook body into hook by name.
        The hook must have been created prior to calling this
        function.

        :param name: The name of the hook to import body to
        :type name: str
        :param body: The body of the hook as a string.
        :type body: str
        :returns: True on success.
        :raises: PbsManagerError
        """
        # sync_mom_hookfiles_timeout is 15min by default
        # Setting it to lower value to avoid the race condition at hook copy
        srv_stat = self.status(SERVER, 'sync_mom_hookfiles_timeout')
        try:
            sync_val = srv_stat[0]['sync_mom_hookfiles_timeout']
        except:
            self.logger.info("Setting sync_mom_hookfiles_timeout to 15s")
            self.manager(MGR_CMD_SET, SERVER,
                         {"sync_mom_hookfiles_timeout": 15})

        fn = self.du.create_temp_file(body=body)

        if not self._is_local:
            tmpdir = self.du.get_tempdir(self.hostname)
            rfile = os.path.join(tmpdir, os.path.basename(fn))
            self.du.run_copy(self.hostname, src=fn, dest=rfile)
        else:
            rfile = fn

        a = {'content-type': 'application/x-python',
             'content-encoding': 'default',
             'input-file': rfile}
        self.manager(MGR_CMD_IMPORT, HOOK, a, name)

        os.remove(rfile)
        if not self._is_local:
            self.du.rm(self.hostname, rfile)
        self.logger.log(level, 'server ' + self.shortname +
                        ': imported hook body\n---\n' +
                        body + '---')
        return True

    def create_import_hook(self, name, attrs=None, body=None, overwrite=True,
                           level=logging.INFO):
        """
        Helper function to create a hook, import content into it,
        set the event and enable it.

        :param name: The name of the hook to create
        :type name: str
        :param attrs: The attributes to create the hook with.
                      Event and Enabled are mandatory. No defaults.
        :type attrs: str
        :param body: The hook body as a string
        :type body: str
        :param overwrite: If True, if a hook of the same name
                          already exists, bypass its creation.
                          Defaults to True
        :returns: True on success and False otherwise
        """
        # Check for log messages 20 seconds earlier, to account for
        # server and mom system time differences
        t = time.time() - 20

        if 'event' not in attrs:
            self.logger.error('attrs must specify at least an event and key')
            return False

        hook_exists = False
        hooks = self.status(HOOK)
        for h in hooks:
            if h['id'] == name:
                hook_exists = True

        if not hook_exists or not overwrite:
            rv = self.create_hook(name, attrs)
            if not rv:
                return False
        else:
            if attrs is None:
                attrs = {'enabled': 'true'}
            rc = self.manager(MGR_CMD_SET, HOOK, attrs, id=name)
            if rc != 0:
                return False

        # In 12.0 A MoM hook must be enabled and the event set prior to
        # importing, otherwise the MoM does not get the hook content
        ret = self.import_hook(name, body, level)

        # In case of mom hooks, make sure that the hook related files
        # are successfully copied to the MoM
        events = attrs['event']
        if not isinstance(events, (list,)):
            events = [events]
        events = [hk for hk in events if 'exec' in hk]
        msg = "successfully sent hook file"
        for hook in events:
            hook_py = name + '.PY'
            hook_hk = name + '.HK'
            pyfile = os.path.join(self.pbs_conf['PBS_HOME'],
                                  "server_priv", "hooks", hook_py)
            hfile = os.path.join(self.pbs_conf['PBS_HOME'],
                                 "server_priv", "hooks", hook_hk)
            logmsg = hook_py + ";copy hook-related file request received"
            cmd = os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                               'pbsnodes') + ' -a' + ' -Fjson'
            cmd_out = self.du.run_cmd(self.hostname, cmd, sudo=True)
            if cmd_out['rc'] != 0:
                return False
            pbsnodes_json = json.loads('\n'.join(cmd_out['out']))
            for m in pbsnodes_json['nodes']:
                if m in self.moms:
                    try:
                        self.log_match("%s %s to %s" %
                                       (msg, hfile, m), interval=1)
                        self.log_match("%s %s to %s" %
                                       (msg, pyfile, m), interval=1)
                        self.moms[m].log_match(logmsg, starttime=t)
                    except PtlLogMatchError:
                        return False
        return ret

    def import_hook_config(self, hook_name, hook_conf, hook_type,
                           level=logging.INFO):
        """
        Helper function to import hook config body into hook by name.
        The hook must have been created prior to calling this
        function.

        :param hook_name: The name of the hook to import hook config
        :type name: str
        :param hook_conf: The body of the hook config as a dict.
        :type hook_conf: dict
        :param hook_type: The hook type "site" or "pbshook"
        :type hook_type: str
        :returns: True on success.
        :raises: PbsManagerError
        """
        if hook_type == "site":
            hook_t = HOOK
        else:
            hook_t = PBS_HOOK

        hook_config_data = json.dumps(hook_conf, indent=4)
        fn = self.du.create_temp_file(body=hook_config_data)

        if not self._is_local:
            tmpdir = self.du.get_tempdir(self.hostname)
            rfile = os.path.join(tmpdir, os.path.basename(fn))
            rc = self.du.run_copy(self.hostname, src=fn, dest=rfile)
            if rc != 0:
                raise AssertionError("Failed to copy file %s"
                                     % (rfile))
        else:
            rfile = fn

        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': rfile}

        self.manager(MGR_CMD_IMPORT, hook_t, a, hook_name)

        os.remove(rfile)
        if not self._is_local:
            self.du.rm(self.hostname, rfile)
        self.logger.log(level, 'server ' + self.shortname +
                        ': imported hook config\n---\n' +
                        str(hook_config_data) + '\n---\n')
        return True

    def export_hook_config(self, hook_name, hook_type):
        """
        Helper function to export hook config body.
        The hook must have been created prior to calling this
        function.

        :param hook_name: The name of the hook to export config from
        :type name: str
        :param hook_type: The hook type "site" or "pbshook"
        :type hook_type: str
        :returns: Dictionary on success False on failure
        """
        if hook_type == "site":
            hook_t = "hook"
        else:
            hook_t = "pbshook"
        cmd = ["export", hook_t, hook_name]
        cmd += ["application/x-config", "default"]
        cmd = " ".join(cmd)
        pcmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'bin', 'qmgr'),
                '-c', cmd]
        ret = self.du.run_cmd(self.hostname, pcmd, sudo=True)
        if ret['rc'] == 0:
            config_out = ''.join(ret['out'])
            config_dict = json.loads(config_out)
            return config_dict
        else:
            raise AssertionError("Failed to export hook config, %s"
                                 % (ret['err']))

    def evaluate_formula(self, jobid=None, formula=None, full=True,
                         include_running_jobs=False, exclude_subjobs=True):
        """
        Evaluate the job sort formula

        :param jobid: If set, evaluate the formula for the given
                      jobid, if not set,formula is evaluated for
                      all jobs in state Q
        :type jobid: str or None
        :param formula: If set use the given formula. If not set,
                        the server's formula, if any, is used
        :param full: If True, returns a dictionary of job
                     identifiers as keys and the evaluated formula
                     as values. Returns None if no formula is used.
                     Each job id formula is returned as a tuple
                     (s,e) where s is the formula expression
                     associated to the job and e is the evaluated
                     numeric value of that expression, for example,
                     if job_sort_formula is ncpus + mem
                     a job requesting 2 cpus and 100kb of memory
                     would return ('2 + 100', 102). If False, if
                     a jobid is specified, return the integer
                     value of the evaluated formula.
        :type full: bool
        :param include_running_jobs: If True, reports formula
                                     value of running jobs.
                                     Defaults to False.
        :type include_running_jobs: bool
        :param exclude_subjobs: If True, only report formula of
                                parent job array
        :type exclude_subjobs: bool
        """
        _f_builtins = ['queue_priority', 'job_priority', 'eligible_time',
                       'fair_share_perc']
        if formula is None:
            d = self.status(SERVER, 'job_sort_formula')
            if len(d) > 0 and 'job_sort_formula' in d[0]:
                formula = d[0]['job_sort_formula']
            else:
                return None

        template_formula = self.utils._make_template_formula(formula)
        # to split up the formula into keywords, first convert all possible
        # operators into spaces and split the string.
        # TODO: The list of operators may need to be expanded
        T = formula.maketrans('()%+*/-', ' ' * 7)
        fres = formula.translate(T).split()
        if jobid:
            d = self.status(JOB, id=jobid, extend='t')
        else:
            d = self.status(JOB, extend='t')
        ret = {}
        for job in d:
            if not include_running_jobs and job['job_state'] != 'Q':
                continue
            f_value = {}
            # initialize the formula values to 0
            for res in fres:
                f_value[res] = 0
            if 'queue_priority' in fres:
                queue = self.status(JOB, 'queue', id=job['id'])[0]['queue']
                d = self.status(QUEUE, 'Priority', id=queue)
                if d and 'Priority' in d[0]:
                    qprio = int(d[0]['Priority'])
                    qprio = int(d[0]['Priority'])
                    f_value['queue_priority'] = qprio
                else:
                    continue
            if 'job_priority' in fres:
                if 'Priority' in job:
                    jprio = int(job['Priority'])
                    f_value['job_priority'] = jprio
                else:
                    continue
            if 'eligible_time' in fres:
                if 'eligible_time' in job:
                    f_value['eligible_time'] = self.utils.convert_duration(
                        job['eligible_time'])
            if 'fair_share_perc' in fres:
                if self.schedulers[self.dflt_sched_name] is None:
                    self.schedulers[self.dflt_sched_name] = get_sched_obj(
                        server=self)

                if 'fairshare_entity' in self.schedulers[
                    self.dflt_sched_name
                ].sched_config:
                    entity = self.schedulers[
                        self.dflt_sched_name
                    ].sched_config['fairshare_entity']
                else:
                    self.logger.error(self.logprefix +
                                      ' no fairshare entity in sched config')
                    continue
                if entity not in job:
                    self.logger.error(self.logprefix +
                                      ' job does not have property ' + entity)
                    continue
                try:
                    fs_info = self.schedulers[
                        self.dflt_sched_name
                    ].query_fairshare(
                        name=job[entity])
                    if fs_info is not None and 'TREEROOT' in fs_info.perc:
                        f_value['fair_share_perc'] = \
                            (fs_info.perc['TREEROOT'] / 100)
                except PbsFairshareError:
                    f_value['fair_share_perc'] = 0

            for job_res, val in job.items():
                val = self.utils.decode_value(val)
                if job_res.startswith('Resource_List.'):
                    job_res = job_res.replace('Resource_List.', '')
                if job_res in fres and job_res not in _f_builtins:
                    f_value[job_res] = val
            tf = string.Template(template_formula)
            tfstr = tf.safe_substitute(f_value)
            if (jobid is not None or not exclude_subjobs or
                    (exclude_subjobs and not self.utils.is_subjob(job['id']))):
                ret[job['id']] = (tfstr, eval(tfstr))
        if not full and jobid is not None and jobid in ret:
            return ret[job['id']][1]
        return ret

    def _parse_limits(self, container=None, dictlist=None, id=None,
                      db_access=None):
        """
        Helper function to parse limits syntax on a given
        container.

        :param container: The PBS object to query, one of ``QUEUE``
                          or ``SERVER``.Metascheduling node group
                          limits are not yet queri-able
        :type container: str or None
        :param dictlist: A list of dictionaries off of a batch
                         status
        :type diclist: List
        :param id: Optional id of the object to query
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        """
        if container is None:
            self.logger.error('parse_limits expect container to be set')
            return {}

        if dictlist is None:
            d = self.status(container, db_access=db_access)
        else:
            d = dictlist

        if not d:
            return {}

        limits = {}
        for obj in d:
            # filter the id here instead of during the stat call so that
            # we can call a full stat once rather than one stat per object
            if id is not None and obj['id'] != id:
                continue
            for k, v in obj.items():
                if k.startswith('max_run'):
                    v = v.split(',')
                    for rval in v:
                        rval = rval.strip("'")
                        l = self.utils.parse_fgc_limit(k + '=' + rval)
                        if l is None:
                            self.logger.error("Couldn't parse limit: " +
                                              k + str(rval))
                            continue

                        (lim_type, resource, etype, ename, value) = l
                        if (etype, ename) not in self.entities:
                            entity = Entity(etype, ename)
                            self.entities[(etype, ename)] = entity
                        else:
                            entity = self.entities[(etype, ename)]

                        lim = Limit(lim_type, resource, entity, value,
                                    container, obj['id'])

                        if container in limits:
                            limits[container].append(lim)
                        else:
                            limits[container] = [lim]

                        entity.set_limit(lim)
        return limits

    def parse_server_limits(self, server=None, db_access=None):
        """
        Parse all server limits

        :param server: list of dictionary of server data
        :type server: List
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        """
        return self._parse_limits(SERVER, server, db_access=db_access)

    def parse_queue_limits(self, queues=None, id=None, db_access=None):
        """
        Parse queue limits

        :param queues: list of dictionary of queue data
        :type queues: List
        :param id: The id of the queue to parse limit for. If None,
                   all queue limits are parsed
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        """
        return self._parse_limits(QUEUE, queues, id=id, db_access=db_access)

    def parse_all_limits(self, server=None, queues=None, db_access=None):
        """
        Parse all server and queue limits

        :param server: list of dictionary of server data
        :type server: List
        :param queues: list of dictionary of queue data
        :type queues: List
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        """
        if hasattr(self, 'limits'):
            del self.limits

        slim = self.parse_server_limits(server, db_access=db_access)
        qlim = self.parse_queue_limits(queues, id=None, db_access=db_access)
        self.limits = dict(list(slim.items()) + list(qlim.items()))
        del slim
        del qlim
        return self.limits

    def limits_info(self, etype=None, ename=None, server=None, queues=None,
                    jobs=None, db_access=None, over=False):
        """
        Collect limit information for each entity on which a
        ``server/queue`` limit is applied.

        :param etype: entity type, one of u, g, p, o
        :type etype: str or None
        :param ename: entity name
        :type ename: str or None
        :param server: optional list of dictionary representation
                       of server object
        :type server: List
        :param queues: optional list of dictionary representation
                       of queues object
        :type queues: List
        :param jobs: optional list of dictionary representation of
                     jobs object
        :type jobs: List
        :param db_acccess: set to either file containing credentials
                           to DB access or dictionary containing
                           ``{'dbname':...,'user':...,'port':...}``
        :type db_access: str or dictionary
        :param over: If True, show only entities that are over their
                     limit.Default is False.
        :type over: bool
        :returns: A list of dictionary similar to that returned by
                  a converted batch_status object, i.e., can be
                  displayed using the Utils.show method
        """
        def create_linfo(lim, entity_type, id, used):
            """
            Create limit information

            :param lim: Limit to apply
            :param entity_type: Type of entity
            """
            tmp = {}
            tmp['id'] = entity_type + ':' + id
            c = [PBS_OBJ_MAP[lim.container]]
            if lim.container_id:
                c += [':', lim.container_id]
            tmp['container'] = "".join(c)
            s = [str(lim.limit_type)]
            if lim.resource:
                s += ['.', lim.resource]
            tmp['limit_type'] = "".join(s)
            tmp['usage/limit'] = "".join([str(used), '/', str(lim.value)])
            tmp['remainder'] = int(lim.value) - int(used)

            return tmp

        def calc_usage(jobs, attr, name=None, resource=None):
            """
            Calculate the usage for the entity

            :param attr: Job attribute
            :param name: Entity name
            :type name: str or None
            :param resource: PBS resource
            :type resource: str or None
            :returns: The usage
            """
            usage = {}
            # initialize usage of the named entity
            if name is not None and name not in ('PBS_GENERIC', 'PBS_ALL'):
                usage[name] = 0
            for j in jobs:
                entity = j[attr]
                if entity not in usage:
                    if resource:
                        usage[entity] = int(
                            self.utils.decode_value(
                                j['Resource_List.' + resource]))
                    else:
                        usage[entity] = 1
                else:
                    if resource:
                        usage[entity] += int(
                            self.utils.decode_value(
                                j['Resource_List.' + resource]))
                    else:
                        usage[entity] += 1
            return usage

        self.parse_all_limits(server, queues, db_access)
        entities_p = self.entities.values()

        linfo = []
        cache = {}

        if jobs is None:
            jobs = self.status(JOB)

        for entity in sorted(entities_p, key=lambda e: e.name):
            for lim in entity.limits:
                _t = entity.type
                # skip non-matching entity types. We can't skip the entity
                # name due to proper handling of the PBS_GENERIC limits
                # we also can't skip overall limits
                if (_t != 'o') and (etype is not None and etype != _t):
                    continue

                _n = entity.name

                a = {}
                if lim.container == QUEUE and lim.container_id is not None:
                    a['queue'] = (EQ, lim.container_id)
                if lim.resource:
                    resource = 'Resource_List.' + lim.resource
                    a[resource] = (GT, 0)
                a['job_state'] = (EQ, 'R')
                a['substate'] = (EQ, 42)
                if etype == 'u' and ename is not None:
                    a['euser'] = (EQ, ename)
                else:
                    a['euser'] = (SET, '')
                if etype == 'g' and ename is not None:
                    a['egroup'] = (EQ, ename)
                else:
                    a['egroup'] = (SET, '')
                if etype == 'p' and ename is not None:
                    a['project'] = (EQ, ename)
                else:
                    a['project'] = (SET, '')

                # optimization: cache filtered results
                d = None
                for v in cache.keys():
                    if cmp(a, eval(v)) == 0:
                        d = cache[v]
                        break
                if d is None:
                    d = self.filter(JOB, a, bslist=jobs, attrop=PTL_AND,
                                    idonly=False, db_access=db_access)
                    cache[str(a)] = d
                if not d or 'job_state=R' not in d:
                    # in the absence of jobs, display limits defined with usage
                    # of 0
                    if ename is not None:
                        _u = {ename: 0}
                    else:
                        _u = {_n: 0}
                else:
                    if _t in ('u', 'o'):
                        _u = calc_usage(
                            d['job_state=R'], 'euser', _n, lim.resource)
                        # an overall limit applies across all running jobs
                        if _t == 'o':
                            all_used = sum(_u.values())
                            for k in _u.keys():
                                _u[k] = all_used
                    elif _t == 'g':
                        _u = calc_usage(
                            d['job_state=R'], 'egroup', _n, lim.resource)
                    elif _t == 'p':
                        _u = calc_usage(
                            d['job_state=R'], 'project', _n, lim.resource)

                for k, used in _u.items():
                    if not over or (int(used) > int(lim.value)):
                        if ename is not None and k != ename:
                            continue
                        if _n in ('PBS_GENERIC', 'PBS_ALL'):
                            if k not in ('PBS_GENERIC', 'PBS_ALL'):
                                k += '/' + _n
                        elif _n != k:
                            continue
                        tmp_linfo = create_linfo(lim, _t, k, used)
                        linfo.append(tmp_linfo)
                del a
        del cache
        return linfo

    def __insert_jobs_in_db(self, jobs, hostname=None):
        """
        An experimental interface that converts jobs from file
        into entries in the PBS database that can be recovered
        upon server restart if all other ``objects``, ``queues``,
        ``resources``, etc... are already defined.

        The interface to PBS used in this method is incomplete
        and will most likely cause serious issues. Use only for
        development purposes
        """

        if not jobs:
            return []

        if hostname is None:
            hostname = socket.gethostname()

        # a very crude, and not quite maintainale way to get the flag value
        # of an attribute. This is one of the reasons why this conversion
        # of jobs is highly experimental
        flag_map = {'ctime': 9, 'qtime': 9, 'hop_count': 9, 'queue_rank': 9,
                    'queue_type': 9, 'etime': 9, 'job_kill_delay': 9,
                    'run_version': 9, 'job_state': 9, 'exec_host': 9,
                    'exec_host2': 9, 'exec_vnode': 9, 'mtime': 9, 'stime': 9,
                    'substate': 9, 'hashname': 9, 'comment': 9, 'run_count': 9,
                    'schedselect': 13}

        state_map = {'Q': 1, 'H': 2, 'W': 3, 'R': 4, 'E': 5, 'X': 6, 'B': 7}

        job_attr_stmt = ("INSERT INTO pbs.job_attr (ji_jobid, attr_name, "
                         "attr_resource, attr_value, attr_flags)")

        job_stmt = ("INSERT INTO pbs.job (ji_jobid, ji_sv_name, ji_state, "
                    "ji_substate, ji_svrflags, ji_stime, "
                    "ji_queue, ji_destin, ji_un_type, "
                    "ji_exitstat, ji_quetime, ji_rteretry, "
                    "ji_fromsock, ji_fromaddr, ji_jid, "
                    "ji_credtype, ji_savetm, ji_creattm)")

        all_stmts = []

        for job in jobs:

            keys = []
            values = []
            flags = []

            for k, v in job.items():
                if k in ('id', 'Mail_Points', 'Mail_Users'):
                    continue
                keys.append(k)
                if not v.isdigit():
                    values.append("'" + v + "'")
                else:
                    values.append(v)
                if k in flag_map:
                    flags.append(flag_map[k])
                elif k.startswith('Resource_List'):
                    flags.append(15)
                else:
                    flags.append(11)

            jobid = job['id'].split('.')[0] + '.' + hostname

            for i in range(len(keys)):
                stmt = job_attr_stmt
                stmt += " VALUES('" + jobid + "', "
                if '.' in keys[i]:
                    k, v = keys[i].split('.')
                    stmt += "'" + k + "', '" + v + "'" + ", "
                else:
                    stmt += "'" + keys[i] + "', ''" + ", "
                stmt += values[i] + "," + str(flags[i])
                stmt += ");"
                self.logger.debug(stmt)
                all_stmts.append(stmt)

            js = job['job_state']
            svrflags = 1
            state = 1
            if js in state_map:
                state = state_map[js]
                if state == 4:
                    # Other states svrflags aren't handled and will
                    # cause issues, another reason this is highly experimental
                    svrflags = 12289

            tm = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            stmt = job_stmt
            stmt += " VALUES('" + jobid + "', 1, "
            stmt += str(state) + ", " + job['substate']
            stmt += ", " + str(svrflags)
            stmt += ", 0, 0, 0"
            if 'stime' in job:
                print(job['stime'])
                st = time.strptime(job['stime'], "%a %b %d %H:%M:%S %Y")
                stmt += ", " + str(time.mktime(st))
            else:
                stmt += ", 0"
            stmt += ", 0"
            stmt += ", '" + job['queue'] + "'"
            if 'exec_host2' in job:
                stmt += ", " + job['exec_host2']
            else:
                stmt += ", ''"
            stmt += ", 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0, 0"
            stmt += ", '" + tm + "', '" + tm + "');"
            self.logger.debug(stmt)

            all_stmts.append(stmt)

        return all_stmts

    def clusterize(self, conf_file=None, hosts=None, acct_logs=None,
                   import_jobs=False, db_creds_file=None):
        """
        Mimic a ``pbs_snapshot`` snapshot onto a set of hosts running
        a PBS ``server``,``scheduler``, and ``MoM``.

        This method clones the following information from the snap:

        ``Server attributes``
        ``Server resourcedef``
        ``Hooks``
        ``Scheduler configuration``
        ``Scheduler resource_group``
        ``Scheduler holiday file``
        ``Per Queue attributes``

        Nodes are copied as a vnode definition file inserted into
        each host's MoM instance.

        Currently no support for cloning the server 'sched' object,
        nor to copy nodes to multi-mom instances.

        Jobs are copied over only if import_jobs is True, see below
        for details

        :param conf_file: Configuration file for the MoM instance
        :param hosts: List of hosts on which to clone the snap
                      snapshot
        :type hosts: List
        :param acct_logs: path to accounting logs
        :type acct_logs str
        :param include_jobs: [Experimental] if True jobs from the
                             pbs_snapshot are imported into the host's
                             database. There are several caveats to
                             this option:
                             The scripts are not imported
                             The users and groups are not created on
                             the local system.There are no actual
                             processes created on the MoM for each
                             job so operations on the job such as
                             signals or delete will fail (delete -W
                             force will still work)
        :type include_jobs: bool
        :param db_creds_file: Path to file containing credentials
                              to access the DB
        :type db_creds_file: str or None
        """
        if not self.has_snap:
            return
        if hosts is None:
            return

        # Create users & groups (need to associate users to groups)
        if acct_logs is not None:
            self.logger.info("Parsing accounting logs to find "
                             "users & groups to create")
            groups = set()
            users = {}
            for name in os.listdir(acct_logs):
                fpath = os.path.join(acct_logs, name)
                with open(fpath, "r") as fd:
                    for line in fd:
                        rec_list = line.split(";", 3)
                        if len(rec_list) < 4 or rec_list[1] != "E":
                            continue
                        try:
                            uname = rec_list[3].split(
                                "user=")[1].split()[0]
                            if uname not in users:
                                users[uname] = set()
                            gname = rec_list[3].split(
                                "group=")[1].split()[0]
                            users[uname].add(gname)
                            groups.add(gname)
                        except IndexError:
                            continue
            # Create groups first
            for grp in groups:
                try:
                    self.du.groupadd(name=grp)
                except PtlUtilError as e:
                    if "already exists" not in e.msg[0]:
                        raise
            # Now create users and add them to their associated groups
            for user, u_grps in users.items():
                try:
                    self.du.useradd(name=user, groups=list(u_grps))
                except PtlUtilError as e:
                    if "already exists" not in e.msg[0]:
                        raise

        for h in hosts:
            svr = Server(h)
            sched = Scheduler(server=svr, snap=self.snap,
                              snapmap=self.snapmap)
            try:
                svr.manager(MGR_CMD_DELETE, NODE, None, id="")
            except:
                pass
            svr.revert_to_defaults(delqueues=True, delhooks=True)
            local = svr.pbs_conf['PBS_HOME']

            snap_rdef = os.path.join(self.snap, 'server_priv', 'resourcedef')
            snap_sc = os.path.join(self.snap, 'sched_priv', 'sched_config')
            snap_rg = os.path.join(self.snap, 'sched_priv', 'resource_group')
            snap_hldy = os.path.join(self.snap, 'sched_priv', 'holidays')
            nodes = os.path.join(self.snap, 'node', 'pbsnodes_va.out')
            snap_hooks = os.path.join(self.snap, 'hook',
                                      'qmgr_ph_default.out')
            snap_ps = os.path.join(self.snap, 'server', 'qmgr_ps.out')
            snap_psched = os.path.join(self.snap, 'scheduler',
                                       'qmgr_psched.out')
            snap_pq = os.path.join(self.snap, 'server', 'qmgr_pq.out')

            local_rdef = os.path.join(local, 'server_priv', 'resourcedef')
            local_sc = os.path.join(local, 'sched_priv', 'sched_config')
            local_rg = os.path.join(local, 'sched_priv', 'resource_group')
            local_hldy = os.path.join(local, 'sched_priv', 'holidays')

            _fcopy = [(snap_rdef, local_rdef), (snap_sc, local_sc),
                      (snap_rg, local_rg), (snap_hldy, local_hldy)]

            # Restart since resourcedef may have changed
            svr.restart()

            if os.path.isfile(snap_ps):
                with open(snap_ps) as tmp_ps:
                    cmd = [os.path.join(svr.pbs_conf['PBS_EXEC'], 'bin',
                                        'qmgr')]
                    self.du.run_cmd(h, cmd, stdin=tmp_ps, sudo=True,
                                    logerr=False)
            else:
                self.logger.error("server information not found in snapshot")

            # Unset any site-sensitive attributes
            for a in ['pbs_license_info', 'mail_from', 'acl_hosts']:
                try:
                    svr.manager(MGR_CMD_UNSET, SERVER, a, sudo=True)
                except:
                    pass

            for (d, l) in _fcopy:
                if os.path.isfile(d):
                    self.logger.info('copying ' + d + ' to ' + l)
                    self.du.run_copy(h, src=d, dest=l, sudo=True)

            if os.path.isfile(snap_pq):
                with open(snap_pq) as tmp_pq:
                    cmd = [os.path.join(svr.pbs_conf['PBS_EXEC'], 'bin',
                                        'qmgr')]
                    self.du.run_cmd(h, cmd, stdin=tmp_pq, sudo=True,
                                    logerr=False)
            else:
                self.logger.error("queue information not found in snapshot")

            if os.path.isfile(snap_psched):
                with open(snap_psched) as tmp_psched:
                    cmd = [os.path.join(svr.pbs_conf['PBS_EXEC'], 'bin',
                                        'qmgr')]
                    self.du.run_cmd(h, cmd, stdin=tmp_psched, sudo=True,
                                    logerr=False)
            else:
                self.logger.error("sched information not found in snapshot")

            if os.path.isfile(nodes):
                with open(nodes) as f:
                    lines = f.readlines()
                dl = self.utils.convert_to_dictlist(lines)
                vdef = self.utils.dictlist_to_vnodedef(dl)
                if vdef:
                    try:
                        svr.manager(MGR_CMD_DELETE, NODE, None, "")
                    except:
                        pass
                    get_mom_obj(h, pbsconf_file=conf_file).insert_vnode_def(
                        vdef)
                    svr.restart()
                    svr.manager(MGR_CMD_CREATE, NODE, id=svr.shortname)
                # check if any node is associated to a queue.
                # This is needed because the queues 'hasnodes' attribute
                # does not get set through vnode def update and must be set
                # via qmgr. It only needs to be set once, not for each node
                qtoset = {}
                for n in dl:
                    if 'queue' in n and n['queue'] not in qtoset:
                        qtoset[n['queue']] = n['id']

                # before setting queue on nodes make sure that the vnode
                # def is all set
                svr.expect(NODE, {'state=free': (GE, len(dl))}, interval=3)
                for k, v in qtoset.items():
                    svr.manager(MGR_CMD_SET, NODE, {'queue': k}, id=v)
            else:
                self.logger.error("nodes information not found in snapshot")

            # populate hooks
            if os.path.isfile(snap_hooks):
                hooks = svr.status(HOOK, level=logging.DEBUG)
                hooks = [hk['id'] for hk in hooks]
                if len(hooks) > 0:
                    svr.manager(MGR_CMD_DELETE, HOOK, id=hooks)
                with open(snap_hooks) as tmp_hook:
                    cmd = [os.path.join(svr.pbs_conf['PBS_EXEC'], 'bin',
                                        'qmgr')]
                    self.du.run_cmd(h, cmd, stdin=tmp_hook, sudo=True)
            else:
                self.logger.error("hooks information not found in snapshot")

            # import jobs
            if import_jobs:
                jobs = self.status(JOB)
                sql_stmt = self.__insert_jobs_in_db(jobs, h)
                print("\n".join(sql_stmt))
                if db_creds_file is not None:
                    pass

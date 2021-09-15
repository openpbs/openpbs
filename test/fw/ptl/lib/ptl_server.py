# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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
import copy
import datetime
import grp
import json
import logging
import os
import socket
import string
import sys
import time

from ptl.utils.pbs_dshutils import DshUtils, PtlUtilError
from ptl.utils.pbs_testusers import (ROOT_USER, TEST_USER, PbsUser,
                                     DAEMON_SERVICE_USER)

try:
    import psycopg2
    PSYCOPG = True
except Exception:
    PSYCOPG = False
from ptl.lib.ptl_error import (PbsStatusError, PbsSubmitError,
                               PbsDeljobError, PbsDelresvError,
                               PbsDeleteError, PbsSelectError,
                               PbsManagerError, PbsSignalError,
                               PbsAlterError, PbsHoldError,
                               PbsRerunError, PbsOrderError,
                               PbsRunError, PbsMoveError,
                               PbsQtermError, PbsQdisableError,
                               PbsQenableError, PbsQstartError,
                               PbsQstopError, PbsResourceError,
                               PbsResvAlterError, PtlExpectError,
                               PbsConnectError, PbsServiceError,
                               PbsInitServicesError, PbsMessageError,
                               PtlLogMatchError)
from ptl.lib.ptl_types import PbsAttribute
from ptl.lib.ptl_constants import *
from ptl.lib.ptl_entities import (Hook, Queue, Entity, Limit,
                                  EquivClass, Resource)
from ptl.lib.ptl_sched import Scheduler
from ptl.lib.ptl_mom import MoM, get_mom_obj
from ptl.lib.ptl_service import PBSService, PBSInitServices
from ptl.lib.ptl_wrappers import *


class Server(Wrappers):

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

    def __init__(self, name=None, attrs={}, defaults={}, pbsconf_file=None,
                 snapmap={}, snap=None, client=None, client_pbsconf_file=None,
                 db_access=None, stat=True):
        super().__init__(name, attrs, defaults, pbsconf_file, snapmap,
                         snap, client, client_pbsconf_file, db_access, stat)

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
                            runas=runas, level=level,
                            resolve_indirectness=resolve_indirectness)

    def set_attributes(self, a={}):
        """
        set server attributes
        :param a: Attribute dictionary
        :type a: Dictionary
        """
        super(Server, self).set_attributes(a)
        self.__dict__.update(a)

    def isUp(self, max_attempts=None):
        """
        returns ``True`` if server is up and ``False`` otherwise
        """
        if max_attempts is None:
            max_attempts = self.ptl_conf['max_attempts']
        if self.has_snap:
            return True
        i = 0
        op_mode = self.get_op_mode()
        if ((op_mode == PTL_API) and (self._conn is not None)):
            self._disconnect(self._conn, force=True)
        while i < max_attempts:
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
                rv = self._isUp()
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
        start_rc = self.start()
        self.expect(NODE, {'state=state-unknown,down': 0})
        return start_rc

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
        except Exception:
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
            except Exception:
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

    def create_node(self, name, level="INFO", logerr=False):
        """
        Add a node to PBS
        """
        ret = self.manager(MGR_CMD_CREATE, VNODE, name,
                           level=level, logerr=logerr)
        return ret

    def delete_node(self, name, level="INFO", logerr=False):
        """
        Remove a node from PBS
        """
        try:
            ret = self.manager(MGR_CMD_DELETE, VNODE, name,
                               level=level, logerr=logerr)
        except PbsManagerError as err:
            if "Unknown node" not in err.msg[0]:
                raise
            else:
                ret = 15062
        return ret

    def delete_nodes(self):
        """
        Remove all the nodes from PBS
        """
        try:
            self.manager(MGR_CMD_DELETE, VNODE, id="@default",
                         runas=ROOT_USER)
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
            except Exception:
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
                strip_line = l.strip()
                if strip_line == '' or strip_line.startswith('#'):
                    continue
                name = None
                rtype = None
                flag = None
                res = strip_line.split()
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
        except Exception:
            raise PbsResourceError(rc=1, rv=False,
                                   msg="error in parse_resources")
        return resources

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
                pbsnodes = os.path.join(
                    self.client_conf['PBS_EXEC'], 'bin', 'pbsnodes')
                ret = self.du.run_cmd(
                    self.hostname, [pbsnodes, '-v', host, '-F', 'json'],
                    logerr=False, level=logging.DEBUG, sudo=True)
                pbsnodes_json = json.loads('\n'.join(ret['out']))
                host = pbsnodes_json['nodes'][host]['Mom']
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
                except Exception:
                    pass
                reservations = self.status(RESV, runas=ROOT_USER)

    def cleanup_jobs_and_reservations(self):
        """
        Helper function to delete all jobs and reservations
        """
        rv = self.cleanup_jobs()
        self.cleanup_reservations()
        return rv

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
                    amt = PbsAttribute.decode_value(bs[a])
                    if a.startswith('resources_available.'):
                        val = a.replace('resources_available.', '')
                        if (op == RESOURCES_AVAILABLE and
                                'resources_assigned.' + val in bs):
                            amt = (int(amt) - int(PbsAttribute.decode_value(
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
                            except Exception:
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
                            except Exception:
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
                                except Exception:
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
            self.schedulers[self.dflt_sched_name] = Scheduler(server=self)

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
                            tmpr = int(PbsAttribute.decode_value(job[r]))
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
                    val = PbsAttribute.decode_value(node[avail])
                    if isinstance(val, int):
                        resavail[res] += val

                        # When entity matching all resources assigned are
                        # accounted for by the job usage
                        if len(entity) == 0:
                            assigned = 'resources_assigned.' + res
                            if assigned in node:
                                val = PbsAttribute.decode_value(
                                    node[assigned])
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
                node_length = 0
                try:
                    node_length = len(self.status(NODE))
                except PbsStatusError as err:
                    if "Server has no node list" not in err.msg[0]:
                        self.logger.error(
                            "Error while checking node length:" + str(err))
                        return False
                if node_length > 0:
                    self.logger.error("create_moms: Error deleting all nodes")
                    return False

        pi = PBSInitServices()
        if momhosts is None:
            momhosts = [self.hostname]

        if attrib is None:
            attrib = {}

        error = False
        momnum = 0
        for hostname in momhosts:
            momnum += 1
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
            _np_conf['PBS_START_COMM'] = '0'
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
                m = MoM(self, hostname, pbsconf_file=_n_pbsconf)
                if m.isUp():
                    m.stop()
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
                    if momnum == 1:
                        _n = name + '-' + str(i)
                    else:
                        _n = name + str(momnum) + '-' + str(i)
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
        self.update_special_attr(HOOK, id=name)
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
        except Exception:
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
        if not self._is_local:
            cmd = '\'' + " ".join(cmd) + '\''
        else:
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
                    self.schedulers[self.dflt_sched_name] = Scheduler(
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
                    ].fairshare.query_fairshare(
                        name=job[entity])
                    if fs_info is not None and 'TREEROOT' in fs_info.perc:
                        f_value['fair_share_perc'] = \
                            (fs_info.perc['TREEROOT'] / 100)
                except PbsFairshareError:
                    f_value['fair_share_perc'] = 0

            for job_res, val in job.items():
                val = PbsAttribute.decode_value(val)
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
                        limit_list = self.utils.parse_fgc_limit(k + '=' + rval)
                        if limit_list is None:
                            self.logger.error("Couldn't parse limit: " +
                                              k + str(rval))
                            continue

                        (lim_type, resource, etype, ename, value) = limit_list
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
                            PbsAttribute.decode_value(
                                j['Resource_List.' + resource]))
                    else:
                        usage[entity] = 1
                else:
                    if resource:
                        usage[entity] += int(
                            PbsAttribute.decode_value(
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
            except Exception:
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
                except Exception:
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
                    except Exception:
                        pass
                    MoM(self, h, pbsconf_file=conf_file).insert_vnode_def(
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

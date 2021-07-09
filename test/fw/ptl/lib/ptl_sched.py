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
import copy
import datetime
import grp
import json
import logging
import os
import pwd
import re
import string
import sys
import tempfile
import time
import traceback
from distutils.version import LooseVersion
from operator import itemgetter

from ptl.utils.pbs_cliutils import CliUtils
from ptl.utils.pbs_testusers import (ROOT_USER, TEST_USER, PbsUser,
                                     DAEMON_SERVICE_USER)
from ptl.lib.ptl_service import PBSService, PBSInitServices
from ptl.lib.ptl_fairshare import (FairshareTree, FairshareNode,
                                   Fairshare)
from ptl.lib.ptl_entities import Holidays
from ptl.lib.ptl_error import (PbsManagerError, PbsStatusError,
                               PbsInitServicesError, PbsServiceError,
                               PtlLogMatchError, PbsSchedConfigError,
                               PbsFairshareError)
from ptl.lib.ptl_constants import (SCHED, MGR_CMD_SET, MGR_CMD_UNSET,
                                   MGR_CMD_LIST, MGR_OBJ_SCHED, NE)


class Scheduler(PBSService):

    """
    Container of Scheduler related properties

    :param hostname: The hostname on which the scheduler instance
                     is operating
    :type hostname: str or None
    :param server: A PBS server instance to which this scheduler
                   is associated
    :param pbsconf_file: path to a PBS configuration file
    :type pbsconf_file: str or None
    :param snapmap: A dictionary of PBS objects (node,server,etc)
                    to mapped files from PBS snap directory
    :type snapmap: Dictionary
    :param snap: path to PBS snap directory (This will overrides
                 snapmap)
    :type snap: str or None
    :param db_acccess: set to either file containing credentials
                       to DB access or dictionary containing
                       ``{'dbname':...,'user':...,'port':...}``
    :type db_access: str or dictionary
    """

    # A vanilla scheduler configuration. This set may change based on
    # updates to PBS
    sched_dflt_config = {
        "backfill": "true        ALL",
        "backfill_prime": "false ALL",
        "strict_ordering": "false ALL",
        "provision_policy": "\"aggressive_provision\"",
        "preempt_order": "\"SCR\"",
        "fairshare_entity": "euser",
        "dedicated_prefix": "ded",
        "primetime_prefix": "p_",
        "nonprimetime_prefix": "np_",
        "preempt_queue_prio": "150",
        "preempt_prio": "\"express_queue, normal_jobs\"",
        "prime_exempt_anytime_queues": "false",
        "round_robin": "False    all",
        "fairshare_usage_res": "cput",
        "smp_cluster_dist": "pack",
        "fair_share": "false     ALL",
        "preempt_sort": "min_time_since_start",
        "node_sort_key": "\"sort_priority HIGH\" ALL",
        "sort_queues": "true     ALL",
        "by_queue": "True                ALL",
        "preemptive_sched": "true        ALL",
        "resources": "\"ncpus, mem, arch, host, vnode, aoe\"",
    }

    sched_config_options = ["node_group_key",

                            "fairshare_enforce_no_shares",
                            "strict_ordering",
                            "resource_unset_infinite",
                            "unknown_shares",
                            "dedicated_prefix",
                            "sort_queues",
                            "backfill",
                            "primetime_prefix",
                            "nonprimetime_prefix",
                            "backfill_prime",
                            "prime_exempt_anytime_queues",
                            "prime_spill",
                            "prime_exempt_anytime_queues",
                            "prime_spill",
                            "resources",
                            "mom_resources",
                            "smp_cluster_dist",
                            "preempt_queue_prio",
                            "preempt_suspend",
                            "preempt_checkpoint",
                            "preempt_requeue",
                            "preemptive_sched",
                            "node_group_key",
                            "fairshare_enforce_no_shares",
                            "strict_ordering",
                            "resource_unset_infinite",
                            "provision_policy",
                            "resv_confirm_ignore",
                            "allow_aoe_calendar",
                            "max_job_check",
                            "preempt_attempts",
                            "update_comments",
                            "sort_by",
                            "key",
                            "assign_ssinodes",
                            "cpus_per_ssinode",
                            "mem_per_ssinode",
                            "strict_fifo",
                            "mem_per_ssinode",
                            "strict_fifo"
                            ]

    def __init__(self, server, hostname=None, pbsconf_file=None,
                 snapmap={}, snap=None, db_access=None, id='default',
                 sched_priv=None):

        self.sched_config_file = None
        self.dflt_holidays_file = None
        self.holidays_file = None
        self.sched_config = {}
        self._sched_config_comments = {}
        self._config_order = []
        self.dedicated_time_file = None
        self.dedicated_time = None
        self.dedicated_time_as_str = None
        self.fairshare_tree = None
        self.resource_group = None
        self.holidays_obj = None
        self.server = None
        self.db_access = None
        self.user = None

        self.server = server
        if snap is None and self.server.snap is not None:
            snap = self.server.snap
        if (len(snapmap) == 0) and (len(self.server.snapmap) != 0):
            snapmap = self.server.snapmap

        if hostname is None:
            hostname = self.server.hostname

        super().__init__(hostname, pbsconf_file=pbsconf_file,
                         snap=snap, snapmap=snapmap)
        _m = ['scheduler ', self.shortname]
        if pbsconf_file is not None:
            _m += ['@', pbsconf_file]
        _m += [': ']
        self.logprefix = "".join(_m)
        self.pi = PBSInitServices(hostname=self.hostname,
                                  conf=self.pbs_conf_file)
        self.pbs_conf = self.server.pbs_conf
        self.sc_name = id

        self.user = DAEMON_SERVICE_USER
        self.fairshare = Fairshare(self.has_snap, self.pbs_conf, self.sc_name,
                                   self.hostname, self.user)

        self.dflt_sched_config_file = os.path.join(self.pbs_conf['PBS_EXEC'],
                                                   'etc', 'pbs_sched_config')

        self.dflt_holidays_file = os.path.join(self.pbs_conf['PBS_EXEC'],
                                               'etc', 'pbs_holidays')

        self.dflt_resource_group_file = os.path.join(self.pbs_conf['PBS_EXEC'],
                                                     'etc',
                                                     'pbs_resource_group')
        self.dflt_dedicated_file = os.path.join(self.pbs_conf['PBS_EXEC'],
                                                'etc',
                                                'pbs_dedicated')
        self.setup_sched_priv(sched_priv)
        self.setup_sched_logs()

        self.db_access = db_access

        self.version = None

    def setup_sched_priv(self, sched_priv=None):
        """
        Initialize Scheduler() member variables on initialization or if
        sched_priv changes
        """
        if sched_priv is None:
            if 'sched_priv' in self.attributes:
                sched_priv = self.attributes['sched_priv']
            else:
                sched_priv = os.path.join(self.pbs_conf['PBS_HOME'],
                                          'sched_priv')

        self.du.chown(self.hostname, sched_priv, uid=self.user,
                      recursive=True, sudo=True)

        self.sched_config_file = os.path.join(sched_priv, 'sched_config')
        self.resource_group_file = os.path.join(sched_priv, 'resource_group')
        self.holidays_file = os.path.join(sched_priv, 'holidays')
        self.set_dedicated_time_file(os.path.join(sched_priv,
                                                  'dedicated_time'))

        if not os.path.exists(sched_priv):
            return

        self.parse_sched_config()

        self.fairshare_tree = self.fairshare.query_fairshare()
        rg = self.parse_resource_group(self.hostname, self.resource_group_file)
        self.resource_group = rg

        self.holidays_obj = Holidays()
        self.holidays_parse_file(level=logging.DEBUG)

    def setup_sched_logs(self):
        if 'sched_log' in self.attributes:
            sched_logs = self.attributes['sched_log']
        else:
            sched_logs = os.path.join(self.pbs_conf['PBS_HOME'],
                                      'sched_logs')

        self.du.chown(self.hostname, sched_logs, uid=self.user,
                      recursive=True, sudo=True)

    def initialise_service(self):
        """
        initialise the scheduler object
        """
        super().initialise_service()
        try:
            attrs = self.server.status(SCHED, level=logging.DEBUG,
                                       db_access=self.db_access,
                                       id=self.sc_name)
            if attrs is not None and len(attrs) > 0:
                self.attributes = attrs[0]
        except (PbsManagerError, PbsStatusError) as e:
            self.logger.error('Error querying scheduler %s' % e.msg)

    def start(self, sched_home=None, args=None, launcher=None):
        """
        Start the scheduler
        :param sched_home: Path to scheduler log and home directory
        :type sched_home: str
        :param args: Arguments required to start the scheduler
        :type args: str
        :param launcher: Optional utility to invoke the launch of the service
        :type launcher: str or list
        """
        if self.attributes['id'] != 'default':
            cmd = [os.path.join(self.pbs_conf['PBS_EXEC'],
                                'sbin', 'pbs_sched')]
            cmd += ['-I', self.attributes['id']]
            if sched_home is not None:
                cmd += ['-d', sched_home]
            try:
                ret = self.du.run_cmd(self.hostname, cmd, sudo=True,
                                      logerr=False, level=logging.INFOCLI)
            except PbsInitServicesError as e:
                raise PbsServiceError(rc=e.rc, rv=e.rv, msg=e.msg)
            self.server.manager(MGR_CMD_LIST, SCHED)
            return ret

        if args is not None or launcher is not None:
            return super()._start(inst=self, args=args,
                                  launcher=launcher)
        else:
            try:
                rv = self.pi.start_sched()
                pid = self._validate_pid(self)
                if pid is None:
                    raise PbsServiceError(rv=False, rc=-1,
                                          msg="Could not find PID")
            except PbsInitServicesError as e:
                raise PbsServiceError(rc=e.rc, rv=e.rv, msg=e.msg)
            return rv

    def stop(self, sig=None):
        """
        Stop the PBS scheduler

        :param sig: Signal to stop the PBS scheduler
        :type sig: str
        """
        if sig is not None:
            self.logger.info(self.logprefix + 'stopping Scheduler on host ' +
                             self.hostname)
            return super()._stop(sig, inst=self)
        elif self.attributes['id'] != 'default':
            self.logger.info(self.logprefix + 'stopping MultiSched ' +
                             self.attributes['id'] + ' on host ' +
                             self.hostname)
            return super()._stop(inst=self)
        else:
            try:
                self.pi.stop_sched()
            except PbsInitServicesError as e:
                raise PbsServiceError(rc=e.rc, rv=e.rv, msg=e.msg)
            return True

    def restart(self):
        """
        Restart the PBS scheduler
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
        Match given ``msg`` in given ``n`` lines of Scheduler log

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

    def run_scheduling_cycle(self):
        """
        Convenience method to start and finish a sched cycle
        """
        sched = self.attributes['id']
        old_val = self.server.status(SCHED, 'scheduling', id=sched)[
            0]['scheduling']

        # Make sure that we aren't in a sched cycle already
        self.server.manager(MGR_CMD_SET, SCHED, {
                            'scheduling': 'False'}, id=sched)

        # Kick a new cycle
        tbefore = time.time()
        self.server.manager(MGR_CMD_SET, SCHED, {
                            'scheduling': 'True'}, id=sched)
        self.log_match("Starting Scheduling",
                       starttime=tbefore)

        if old_val == 'False':
            # This will also ensure that the sched cycle is over before
            # returning
            self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'False'},
                                id=sched)
        else:
            self.server.expect(SCHED, {'state': 'scheduling'}, op=NE,
                               id=sched, interval=1, max_attempts=1200,
                               trigger_sched_cycle=False)

    def pbs_version(self):
        """
        Get the version of the scheduler instance
        """
        if self.version:
            return self.version

        version = self.log_match('pbs_version', tail=False)
        if version:
            version = version[1].strip().split('=')[1]
        else:
            version = "unknown"

        self.version = LooseVersion(version)

        return self.version

    def parse_sched_config(self, schd_cnfg=None):
        """
        Parse a sceduling configuration file into a dictionary.
        Special handling of identical keys ``(e.g., node_sort_key)``
        is done by appending a delimiter, '%', between each value
        of the key. When printed back to file, each delimited entry
        gets written on a line of its own. For example, the python
        dictionary entry:

        ``{'node_sort_key':
        ["ncpus HIGH unusued" prime", "node_priority HIH"
        non-prime"]}``

        will get written as:

        ``node_sort_key: "ncpus HIGH unusued" prime``
        ``node_sort_key: "node_priority HIGH"  non-prime``

        Returns sched_config dictionary that gets reinitialized
        every time this method is called.
        """
        # sched_config is initialized
        if self.sched_config:
            del(self.sched_config)
            self.sched_config = {}
            self._sched_config_comments = {}
            self._config_order = []
        if schd_cnfg is None:
            if self.sched_config_file is not None:
                schd_cnfg = self.sched_config_file
            else:
                self.logger.error('no scheduler configuration file to parse')
                return False

        try:
            conf_opts = self.du.cat(self.hostname, schd_cnfg,
                                    sudo=(not self.has_snap),
                                    level=logging.DEBUG2)['out']
        except Exception:
            self.logger.error('error parsing scheduler configuration')
            return False

        _comment = []
        conf_re = re.compile(
            r'[#]?[\s]*(?P<conf_id>[\w]+):[\s]*(?P<conf_val>.*)')
        for line in conf_opts:
            m = conf_re.match(line)
            if m:
                key = m.group('conf_id')
                val = m.group('conf_val')
                # line is a comment, it could be a commented out scheduling
                # option, or the description of an option. It could also be
                # that part of the description is an example setting of the
                # option.
                # We must keep track of commented out options in order to
                # rewrite the configuration in the same order as it was defined
                if line.startswith('#'):
                    if key in self.sched_config_options:
                        _comment += [line]
                        if key in self._sched_config_comments:
                            self._sched_config_comments[key] += _comment
                            _comment = []
                        else:
                            self._sched_config_comments[key] = _comment
                            _comment = []
                        if key not in self._config_order:
                            self._config_order.append(key)
                    else:
                        _comment += [line]
                    continue

                if key not in self._sched_config_comments:
                    self._sched_config_comments[key] = _comment
                else:
                    self._sched_config_comments[key] += _comment
                if key not in self._config_order:
                    self._config_order.append(key)

                _comment = []
                if key in self.sched_config:
                    if isinstance(self.sched_config[key], list):
                        if isinstance(val, list):
                            self.sched_config[key].extend(val)
                        else:
                            self.sched_config[key].append(val)
                    else:
                        if isinstance(val, list):
                            self.sched_config[key] = [self.sched_config[key]]
                            self.sched_config[key].extend(val)
                        else:
                            self.sched_config[key] = [self.sched_config[key],
                                                      val]
                else:
                    self.sched_config[key] = val
            else:
                _comment += [line]
        self._sched_config_comments['PTL_SCHED_CONFIG_TAIL'] = _comment
        return True

    def check_defaults(self, config):
        """
        Check the values in argument config against default values
        """

        if len(config.keys()) == 0:
            return
        for k, v in self.sched_dflt_config.items():
            if k in config:
                s1 = v
                s1 = s1.replace(" ", "")
                s1 = s1.replace("\t", "").strip()
                s2 = config[k]
                s2 = s2.replace(" ", "")
                s2 = s2.replace("\t", "").strip()

                if s1 != s2:
                    self.logger.debug(k + ' non-default: ' + v +
                                      ' != ' + config[k])

    def apply_config(self, config=None, validate=True, path=None):
        """
        Apply the configuration specified by config

        :param config: Configurations to set. Default: self.
                       sched_config
        :param validate: If True (the default) validate that
                         settings did not yield an error.
                         Validation is done by parsing the
                         scheduler log which, in some cases may
                         be slow and therefore undesirable.
        :type validate: bool
        :param path: Optional path to file to which configuration
                     is written. If None, the configuration is
                     written to PBS_HOME/sched_priv/sched_config
        :type path: str
        :returns: True on success and False otherwise. Success
                  means that upon applying the new configuration
                  the scheduler did not emit an
                  "Error reading line" in its log file.
        """

        if config is None:
            config = self.sched_config

        if len(config) == 0:
            return True

        reconfig_time = time.time()
        try:
            fn = self.du.create_temp_file()
            with open(fn, "w", encoding="utf-8") as fd:
                for k in self._config_order:
                    if k in config:
                        if k in self._sched_config_comments:
                            fd.write("\n".join(self._sched_config_comments[k]))
                            fd.write("\n")
                        v = config[k]
                        if isinstance(v, list):
                            for val in v:
                                fd.write(k + ": " + str(val) + "\n")
                        else:
                            fd.write(k + ": " + str(v) + "\n")
                    elif k in self._sched_config_comments:
                        fd.write("\n".join(self._sched_config_comments[k]))
                        fd.write("\n")
                for k, v in self.sched_config.items():
                    if k not in self._config_order:
                        fd.write(k + ": " + str(v).strip() + "\n")

                if 'PTL_SCHED_CONFIG_TAIL' in self._sched_config_comments:
                    fd.write("\n".join(
                        self._sched_config_comments['PTL_SCHED_CONFIG_TAIL']))
                    fd.write("\n")

            if path is None:
                if 'sched_priv' in self.attributes:
                    sched_priv = self.attributes['sched_priv']
                else:
                    sched_priv = os.path.join(self.pbs_conf['PBS_HOME'],
                                              "sched_priv")
                sp = os.path.join(sched_priv, "sched_config")
            else:
                sp = path
            self.du.run_copy(self.hostname, src=fn, dest=sp,
                             preserve_permission=False,
                             sudo=True, uid=self.user)
            os.remove(fn)

            self.logger.debug(self.logprefix + "updated configuration")
        except Exception:
            m = self.logprefix + 'error in apply_config '
            self.logger.error(m + str(traceback.print_exc()))
            raise PbsSchedConfigError(rc=1, rv=False, msg=m)

        if validate:
            self.get_pid()
            self.signal('-HUP')
            try:
                self.log_match("Sched;reconfigure;Scheduler is reconfiguring",
                               starttime=reconfig_time)
                self.log_match("Error reading line", max_attempts=2,
                               starttime=reconfig_time, existence=False)
            except PtlLogMatchError as log_error:
                self.logger.error(log_error.msg)
                _msg = 'Error in validating sched_config changes'
                raise PbsSchedConfigError(rc=1, rv=False,
                                          msg=_msg)
        return True

    def set_sched_config(self, confs={}, apply=True, validate=True):
        """
        set a ``sched_config`` property

        :param confs: dictionary of key value sched_config entries
        :type confs: Dictionary
        :param apply: if True (the default), apply configuration.
        :type apply: bool
        :param validate: if True (the default), validate the
                         configuration settings.
        :type validate: bool
        """
        self.parse_sched_config()
        self.logger.info(self.logprefix + "config " + str(confs))
        self.sched_config = {**self.sched_config, **confs}
        if apply:
            try:
                self.apply_config(validate=validate)
            except PbsSchedConfigError as sched_error:
                _msg = sched_error.msg
                self.logger.error(_msg)
                for k in confs:
                    del self.sched_config[k]
                self.apply_config(validate=validate)
                raise PbsSchedConfigError(rc=1, rv=False, msg=_msg)
        return True

    def add_server_dyn_res(self, custom_resource, script_body=None,
                           res_file=None, apply=True, validate=True,
                           dirname=None, host=None, perm=0o700,
                           prefix='PtlPbsSvrDynRes', suffix='.scr'):
        """
        Add a root owned server dynamic resource script or file to the
        scheduler configuration.

        :param custom_resource: The name of the custom resource to
                                define
        :type custom_resource: str
        :param script_body: The body of the server dynamic resource
        :param res_file: Alternatively to passing the script body, use
                     the file instead
        :type res_file: str or None
        :param apply: if True (the default), apply configuration.
        :type apply: bool
        :param validate: if True (the default), validate the
                         configuration settings.
        :type validate: bool
        :param dirname: the file will be created in this directory
        :type dirname: str or None
        :param host: the hostname on which dyn res script is created
        :type host: str or None
        :param perm: perm to use while creating scripts
                     (must be octal like 0o777)
        :param prefix: the file name will begin with this prefix
        :type prefix: str
        :param suffix: the file name will end with this suffix
        :type suffix: str
        :return Absolute path of the dynamic resource script
        """
        if res_file is not None:
            with open(res_file) as f:
                script_body = f.readlines()
                self.du.chmod(hostname=host, path=res_file, mode=perm,
                              sudo=True)
        else:
            if dirname is None:
                dirname = self.pbs_conf['PBS_HOME']
            tmp_file = self.du.create_temp_file(prefix=prefix, suffix=suffix,
                                                body=script_body,
                                                hostname=host)
            res_file = os.path.join(dirname, tmp_file.split(os.path.sep)[-1])
            self.du.run_copy(host, src=tmp_file, dest=res_file, sudo=True,
                             preserve_permission=False)

            user = self.user
            group = pwd.getpwnam(str(user)).pw_gid

            self.du.chown(hostname=host, path=res_file, uid=user, gid=group,
                          sudo=True)
            self.du.chmod(hostname=host, path=res_file, mode=perm, sudo=True)
            if host is None:
                self.dyn_created_files.append(res_file)

        self.logger.info(self.logprefix + "adding server dyn res " + res_file)
        self.logger.info("-" * 30)
        self.logger.info(script_body)
        self.logger.info("-" * 30)

        a = {'server_dyn_res': '"' + custom_resource + ' !' + res_file + '"'}
        self.set_sched_config(a, apply=apply, validate=validate)
        return res_file

    def unset_sched_config(self, name, apply=True):
        """
        Delete a ``sched_config`` entry

        :param name: the entry to delete from sched_config
        :type name: str
        :param apply: if True, apply configuration. Defaults to True
        :type apply: bool
        """
        self.parse_sched_config()
        if name not in self.sched_config:
            return True
        self.logger.info(self.logprefix + "unsetting config " + name)
        del self.sched_config[name]

        if apply:
            return self.apply_config()

    def set_dedicated_time_file(self, filename):
        """
        Set the path to a dedicated time
        """
        self.logger.info(self.logprefix + " setting dedicated time file to " +
                         str(filename))
        self.dedicated_time_file = filename

    def revert_to_defaults(self):
        """
        Revert scheduler configuration to defaults.

        :returns: True on success, False otherwise
        """
        self.logger.info(self.logprefix +
                         "reverting configuration to defaults")

        ignore_attrs = ['id', 'pbs_version', 'sched_host', 'state']
        unsetattrs = []
        for k in self.attributes.keys():
            if k not in ignore_attrs:
                unsetattrs.append(k)
        if len(unsetattrs) > 0:
            self.server.manager(MGR_CMD_UNSET, SCHED, unsetattrs)
        self.clear_dedicated_time(hup=False)
        if self.du.cmp(self.hostname, self.dflt_resource_group_file,
                       self.resource_group_file, sudo=True) != 0:
            self.du.run_copy(self.hostname, src=self.dflt_resource_group_file,
                             dest=self.resource_group_file,
                             preserve_permission=False,
                             sudo=True, uid=self.user)
        rc = self.holidays_revert_to_default()
        if self.du.cmp(self.hostname, self.dflt_sched_config_file,
                       self.sched_config_file, sudo=True) != 0:
            self.du.run_copy(self.hostname, src=self.dflt_sched_config_file,
                             dest=self.sched_config_file,
                             preserve_permission=False,
                             sudo=True, uid=self.user)
        if self.du.cmp(self.hostname, self.dflt_dedicated_file,
                       self.dedicated_time_file, sudo=True):
            self.du.run_copy(self.hostname, src=self.dflt_dedicated_file,
                             dest=self.dedicated_time_file,
                             preserve_permission=False, sudo=True,
                             uid=self.user)

        self.signal('-HUP')
        if self.platform == 'cray' or self.platform == 'craysim':
            self.add_resource('vntype')
            self.add_resource('hbmem')
        # Revert fairshare usage
        self.fairshare.revert_fairshare()
        self.fairshare_tree = None
        self.resource_group = None
        self.parse_sched_config()
        return self.isUp()

    def create_scheduler(self, sched_home=None):
        """
        Start scheduler with creating required directories for scheduler
        :param sched_home: path of scheduler home and log directory
        :type sched_home: str
        """
        if sched_home is None:
            sched_home = self.server.pbs_conf['PBS_HOME']
        sched_priv_dir = os.path.join(sched_home,
                                      self.attributes['sched_priv'])
        sched_logs_dir = os.path.join(sched_home,
                                      self.attributes['sched_log'])
        self.server.update_special_attr(SCHED, id=self.attributes['id'])
        if not os.path.exists(sched_priv_dir):
            self.du.mkdir(path=sched_priv_dir, sudo=True)
            if self.user.name != 'root':
                self.du.chown(hostname=self.hostname, path=sched_priv_dir,
                              sudo=True, uid=self.user)
            self.du.run_copy(self.hostname, src=self.dflt_resource_group_file,
                             dest=self.resource_group_file, mode=0o644,
                             sudo=True, uid=self.user)
            self.du.run_copy(self.hostname, src=self.dflt_holidays_file,
                             dest=self.holidays_file, mode=0o644,
                             sudo=True, uid=self.user)
            self.du.run_copy(self.hostname, src=self.dflt_sched_config_file,
                             dest=self.sched_config_file, mode=0o644,
                             sudo=True, uid=self.user)
            self.du.run_copy(self.hostname, src=self.dflt_dedicated_file,
                             dest=self.dedicated_time_file, mode=0o644,
                             sudo=True, uid=self.user)
        if not os.path.exists(sched_logs_dir):
            self.du.mkdir(path=sched_logs_dir, sudo=True)
            if self.user.name != 'root':
                self.du.chown(hostname=self.hostname, path=sched_logs_dir,
                              sudo=True, uid=self.user)

        self.setup_sched_priv(sched_priv=sched_priv_dir)

    def save_configuration(self, outfile=None, mode='w'):
        """
        Save scheduler configuration

        :param outfile: Optional Path to a file to which configuration
                        is saved, when not provided, data is saved in
                        class variable saved_config
        :type outfile: str
        :param mode: mode to use to access outfile. Defaults to
                     append, 'w'.
        :type mode: str
        :returns: True on success and False otherwise
        """
        conf = {}
        if 'sched_priv' in self.attributes:
            sched_priv = self.attributes['sched_priv']
        else:
            sched_priv = os.path.join(
                self.pbs_conf['PBS_HOME'], 'sched_priv')
        sc = os.path.join(sched_priv, 'sched_config')
        self._save_config_file(conf, sc)
        rg = os.path.join(sched_priv, 'resource_group')
        self._save_config_file(conf, rg)
        dt = os.path.join(sched_priv, 'dedicated_time')
        self._save_config_file(conf, dt)
        hd = os.path.join(sched_priv, 'holidays')
        self._save_config_file(conf, hd)

        self.server.saved_config[MGR_OBJ_SCHED] = conf
        if outfile is not None:
            try:
                with open(outfile, mode) as f:
                    json.dump(self.server.saved_config, f)
                    self.server.saved_config[MGR_OBJ_SCHED].clear()
            except Exception:
                self.logger.error('error saving configuration ' + outfile)
                return False

        return True

    def load_configuration(self, infile):
        """
        load scheduler configuration from saved file infile
        """
        rv = self._load_configuration(infile, MGR_OBJ_SCHED)
        self.signal('-HUP')
        return rv

    def get_resources(self, exclude=[]):
        """
        returns a list of allocatable resources.

        :param exclude: if set, excludes the named resources, if
                        they exist, from the resulting list
        :type exclude: List
        """
        if 'resources' not in self.sched_config:
            return None
        resources = self.sched_config['resources']
        resources = resources.replace('"', '')
        resources = resources.replace(' ', '')
        res = resources.split(',')
        if len(exclude) > 0:
            for e in exclude:
                if e in res:
                    res.remove(e)
        return res

    def add_resource(self, name, apply=True):
        """
        Add a resource to ``sched_config``.

        :param name: the resource name to add
        :type name: str
        :param apply: if True, apply configuration. Defaults to True
        :type apply: bool
        :returns: True on success and False otherwise.
                  Return True if the resource is already defined.
        """
        # if the sched_config has not been read in yet, parse it
        if not self.sched_config:
            self.parse_sched_config()

        if 'resources' in self.sched_config:
            resources = self.sched_config['resources']
            resources = resources.replace('"', '')
            splitres = [r.strip() for r in resources.split(",")]
            if name in splitres:
                return True
            resources = '"' + resources + ', ' + name + '"'
        else:
            resources = '"' + name + '"'

        return self.set_sched_config({'resources': resources}, apply=apply)

    def remove_resource(self, name, apply=True):
        """
        Remove a resource to ``sched_config``.

        :param name: the resource name to remove
        :type name: str
        :param apply: if True, apply configuration. Defaults to True
        :type apply: bool
        :returns: True on success and False otherwise
        """
        # if the sched_config has not been read in yet, parse it
        if not self.sched_config:
            self.parse_sched_config()

        if 'resources' in self.sched_config:
            resources = self.sched_config['resources']
            resources = resources.replace('"', '')
            splitres = [r.strip() for r in resources.split(",")]
            if name not in splitres:
                return True

            newres = []
            for r in splitres:
                if r != name:
                    newres.append(r)

            resources = '"' + ",".join(newres) + '"'
            return self.set_sched_config({'resources': resources}, apply=apply)

    def holidays_revert_to_default(self, level=logging.INFO):
        """
        Revert holidays file to default
        """
        self.logger.log(level, self.logprefix +
                        "reverting holidays file to default")

        rc = None
        # Copy over the holidays file from PBS_EXEC if it exists
        if self.du.cmp(self.hostname, self.dflt_holidays_file,
                       self.holidays_file, sudo=True) != 0:
            ret = self.du.run_copy(self.hostname, src=self.dflt_holidays_file,
                                   dest=self.holidays_file,
                                   preserve_permission=False, sudo=True,
                                   logerr=True)
            rc = ret['rc']
            # Update the internal data structures for the updated file
            self.holidays_parse_file(level=level)
        else:
            rc = 1
        return rc

    def holidays_parse_file(self, path=None, obj=None, level=logging.INFO):
        """
        Parse the existing holidays file

        :param path: optional path to the holidays file to parse
        :type path: str or None
        :param obj: optional holidays object to be used instead
                    of internal
        :returns: The content of holidays file as a list of lines
        """
        self.logger.log(level, self.logprefix + "Parsing holidays file")

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set
        if path is None:
            path = self.holidays_file
        lines = self.du.cat(self.hostname, path, sudo=True)['out']

        content = []    # valid content to return

        self.holidays_delete_entry(
            'a', apply=False, obj=obj, level=logging.DEBUG)

        for line in lines:
            entry = str(line).split()
            if len(entry) == 0:
                continue
            tag = entry[0].lower()
            if tag == "year":   # initialize year
                content.append("\t".join(entry))
                obj.year['valid'] = True
                if len(entry) > 1:
                    obj.year['value'] = entry[1]
            elif tag in days_map.keys():   # initialize a day
                content.append("\t".join(entry))
                day = days_map[tag]
                day['valid'] = True
                days_set.append(day)
                day['position'] = len(days_set) - 1
                if len(entry) > 1:
                    day['p'] = entry[1]
                if len(entry) > 2:
                    day['np'] = entry[2]
            elif tag.isdigit():   # initialize a holiday
                content.append("\t".join(entry))
                obj.holidays.append(tag)
            else:
                pass
        return content

    def holidays_set_day(self, day_id, prime="", nonprime="", apply=True,
                         obj=None, level=logging.INFO):
        """
        Set prime time values for a day

        :param day_id: the day to be set (string)
        :type day_id: str
        :param prime: the prime time value
        :param nonprime: the non-prime time value
        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead
                    of internal
        :returns: The position ``(0-7)`` of the set day
        """
        self.logger.log(level, self.logprefix +
                        "setting holidays file entry for %s",
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        day = obj._days_map[str(day_id).lower()]
        days_set = obj.days_set

        if day['valid'] is None:    # Fresh entry
            days_set.append(day)
            day['position'] = len(days_set) - 1
        elif day['valid'] is False:  # Previously invalidated entry
            days_set.insert(day['position'], day)
        else:
            pass

        day['valid'] = True
        day['p'] = str(prime)
        day['np'] = str(nonprime)

        self.logger.debug("holidays_set_day(): changed day struct: " +
                          str(day))

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

        return day['position']

    def holidays_get_day(self, day_id, obj=None, level=logging.INFO):
        """
        :param obj: optional holidays object to be used instead
                    of internal
        :param day_id: either a day's name or "all"
        :type day_id: str
        :returns: A copy of info about a day/all set days
        """
        self.logger.log(level, self.logprefix +
                        "getting holidays file entry for " +
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        days_set = obj.days_set
        days_map = obj._days_map

        if day_id == "all":
            return days_set[:]
        else:
            return days_map[day_id].copy()

    def holidays_reposition_day(self, day_id, new_pos, apply=True, obj=None,
                                level=logging.INFO):
        """
        Change position of a day ``(0-7)`` as it appears in the
        holidays file

        :param day_id: name of the day
        :type day_id: str
        :param new_pos: new position
        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead
                    of internal
        :returns: The new position of the day
        """
        self.logger.log(level, self.logprefix +
                        "repositioning holidays file entry for " +
                        day_id + " to position " + str(new_pos))

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set
        day = days_map[str(day_id).lower()]

        if new_pos == day['position']:
            return

        # We also want to update order of invalid days, so add them to
        # days_set temporarily
        invalid_days = []
        for name in days_map:
            if days_map[name]['valid'] is False:
                invalid_days.append(days_map[name])
        days_set += invalid_days

        # Sort the old list
        days_set.sort(key=itemgetter('position'))

        # Change position of 'day_id'
        day['position'] = new_pos
        days_set.remove(day)
        days_set.insert(new_pos, day)

        # Update the 'position' field
        for i in range(0, len(days_set)):
            days_set[i]['position'] = i

        # Remove invalid days from days_set
        len_days_set = len(days_set)
        days_set = [days_set[i] for i in range(0, len_days_set)
                    if days_set[i] not in invalid_days]

        self.logger.debug("holidays_reposition_day(): List of days after " +
                          " re-positioning " + str(day_id) + " is:\n" +
                          str(days_set))

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

        return new_pos

    def holidays_unset_day(self, day_id, apply=True, obj=None,
                           level=logging.INFO):
        """
        Unset prime time values for a day

        :param day_id: day to unset (string)
        :type day_id: str
        :param apply: to reflect the changes to file
        :param obj: optional holidays object to be used instead
                    of internal

        .. note:: we do not unset the 'valid' field here so the entry
                  will still be displayed but without any values
        """
        self.logger.log(level, self.logprefix +
                        "unsetting holidays file entry for " + day_id)

        if obj is None:
            obj = self.holidays_obj

        day = obj._days_map[str(day_id).lower()]
        day['p'] = ""
        day['np'] = ""

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_invalidate_day(self, day_id, apply=True, obj=None,
                                level=logging.INFO):
        """
        Remove a day's entry from the holidays file

        :param day_id: the day to remove (string)
        :type day_id: str
        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead
                    of internal
        """
        self.logger.log(level, self.logprefix +
                        "invalidating holidays file entry for " +
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set

        day = days_map[str(day_id).lower()]
        day['valid'] = False
        days_set.remove(day)

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_validate_day(self, day_id, apply=True, obj=None,
                              level=logging.INFO):
        """
        Make valid a previously set day's entry

        :param day_id: the day to validate (string)
        :type day_id: str
        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead
                    of internal

        .. note:: The day will retain its previous position in
                  the file
        """
        self.logger.log(level, self.logprefix +
                        "validating holidays file entry for " +
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set

        day = days_map[str(day_id).lower()]
        if day in days_set:  # do not insert a pre-existing day
            self.logger.debug("holidays_validate_day(): " +
                              day_id + " is already valid!")
            return

        day['valid'] = True
        days_set.insert(day['position'], day)

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_delete_entry(self, entry_type, idx=None, apply=True,
                              obj=None, level=logging.INFO):
        """
        Delete ``one/all`` entries from holidays file

        :param entry_type: 'y':year, 'd':day, 'h':holiday or 'a': all
        :type entry_type: str
        :param idx: either a day of week (monday, tuesday etc.)
                    or Julian date  of a holiday
        :type idx: str or None
        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead of
                    internal
        :returns: False if entry_type is invalid, otherwise True

        .. note:: The day cannot be validated and will lose it's
                  position in the file
        """
        self.logger.log(level, self.logprefix +
                        "Deleting entries from holidays file")

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set
        holiday_list = obj.holidays
        year = obj.year

        if entry_type not in ['a', 'y', 'd', 'h']:
            return False

        if entry_type == 'y' or entry_type == 'a':
            self.logger.debug(self.logprefix +
                              "deleting year entry from holidays file")
            # Delete year entry
            year['value'] = None
            year['valid'] = False

        if entry_type == 'd' or entry_type == 'a':
            # Delete one/all day entries
            num_days_to_delete = 1
            if entry_type == 'a':
                self.logger.debug(self.logprefix +
                                  "deleting all days from holidays file")
                num_days_to_delete = len(days_set)
            for i in range(0, num_days_to_delete):
                if (entry_type == 'd'):
                    self.logger.debug(self.logprefix +
                                      "deleting " + str(idx) +
                                      " entry from holidays file")
                    day = days_map[str(idx).lower()]
                else:
                    day = days_set[0]

                day['p'] = None
                day['np'] = None
                day['valid'] = None
                day['position'] = None
                days_set.remove(day)
                if entry_type == 'd':
                    # Correct 'position' field of every day
                    for i in range(0, len(days_set)):
                        days_set[i]['position'] = i

        if entry_type == 'h' or entry_type == 'a':
            # Delete one/all calendar holiday entries
            if entry_type == 'a':
                self.logger.debug(self.logprefix +
                                  "deleting all holidays from holidays file")
                del holiday_list[:]
            else:
                self.logger.debug(self.logprefix +
                                  "deleting holiday on " + str(idx) +
                                  " from holidays file")
                holiday_list.remove(str(idx))

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

        return True

    def holidays_set_year(self, new_year="", apply=True, obj=None,
                          level=logging.INFO):
        """
        Set the year value

        :param newyear: year value to set
        :type newyear: str
        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead
                    of internal
        """
        self.logger.log(level, self.logprefix +
                        "setting holidays file year entry to " +
                        str(new_year))
        if obj is None:
            obj = self.holidays_obj

        year = obj.year

        year['value'] = str(new_year)
        year['valid'] = True

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_unset_year(self, apply=True, obj=None, level=logging.INFO):
        """
        Unset the year value

        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead
                    of internal
        """
        self.logger.log(level, self.logprefix +
                        "unsetting holidays file year entry")
        if obj is None:
            obj = self.holidays_obj

        obj.year['value'] = ""

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_get_year(self, obj=None, level=logging.INFO):
        """
        :param obj: optional holidays object to be used instead
                    of internal
        :returns: The year entry of holidays file
        """
        self.logger.log(level, self.logprefix +
                        "getting holidays file year entry")
        if obj is None:
            obj = self.holidays_obj

        year = obj.year
        return year.copy()

    def holidays_add_holiday(self, date=None, apply=True, obj=None,
                             level=logging.INFO):
        """
        Add a calendar holiday to the holidays file

        :param date: Date value for the holiday
        :param apply: to reflect the changes to file
        :type apply: bool
        :param obj: optional holidays object to be used instead
                    of internal
        """
        self.logger.log(level, self.logprefix +
                        "adding holiday " + str(date) +
                        " to holidays file")
        if obj is None:
            obj = self.holidays_obj

        holiday_list = obj.holidays

        if date is not None:
            holiday_list.append(str(date))
        else:
            pass
        self.logger.debug("holidays list after adding one: " +
                          str(holiday_list))
        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_get_holidays(self, obj=None, level=logging.INFO):
        """
        :param obj: optional holidays object to be used instead
                    of internal
        :returns: The list of holidays in holidays file
        """
        self.logger.log(level, self.logprefix +
                        "retrieving list of holidays")

        if obj is None:
            obj = self.holidays_obj

        holiday_list = obj.holidays
        return holiday_list[:]

    def _holidays_process_content(self, content, obj=None):
        """
        Process a user provided list of holidays file content

        :param obj: optional holidays object to be used instead
                    of internal
        """
        self.logger.debug("_holidays_process_content(): " +
                          "Processing user provided holidays content:\n" +
                          str(content))
        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        year = obj.year
        holiday_list = obj.holidays
        days_set = obj.days_set

        self.holidays_delete_entry(
            'a', apply=False, obj=obj, level=logging.DEBUG)

        if content is None:
            self.logger.debug("Holidays file was wiped out")
            return

        for line in content:
            entry = line.split()
            if len(entry) == 0:
                continue
            tag = entry[0].lower()
            if tag == "year":   # initialize self.year
                year['valid'] = True
                if len(entry) > 1:
                    year['value'] = entry[1]
            elif tag in days_map.keys():   # initialize self.<day>
                day = days_map[tag]
                day['valid'] = True
                days_set.append(day)
                day['position'] = len(days_set) - 1
                if len(entry) > 1:
                    day['p'] = entry[1]
                if len(entry) > 2:
                    day['np'] = entry[2]
            elif tag.isdigit():   # initialize self.holiday
                holiday_list.append(tag)
            else:
                pass

    def holidays_write_file(self, content=None, out_path=None,
                            hup=True, obj=None, level=logging.INFO):
        """
        Write to the holidays file with content ``given/generated``

        :param hup: SIGHUP the scheduler after writing the holidays
                    file
        :type hup: bool
        :param obj: optional holidays object to be used instead of
                    internal
        """
        self.logger.log(level, self.logprefix +
                        "Writing to the holidays file")

        if obj is None:
            obj = self.holidays_obj

        if out_path is None:
            out_path = self.holidays_file

        if content is not None:
            self._holidays_process_content(content, obj)
        else:
            content = str(obj)

        self.logger.debug("content being written:\n" + str(content))

        fn = self.du.create_temp_file(self.hostname, body=content)
        ret = self.du.run_copy(self.hostname, src=fn, dest=out_path,
                               preserve_permission=False, sudo=True)
        self.du.rm(self.hostname, fn)

        if ret['rc'] != 0:
            raise PbsSchedConfigError(rc=ret['rc'], rv=ret['out'],
                                      msg=('error applying holidays file' +
                                           ret['err']))
        if hup:
            rv = self.signal('-HUP')
            if not rv:
                raise PbsSchedConfigError(rc=1, rv=False,
                                          msg='error applying holidays file')
        return True

    def parse_dedicated_time(self, file=None):
        """
        Parse the dedicated_time file and populate dedicated times
        as both a string dedicated_time array of dictionaries defined
        as ``[{'from': datetime, 'to': datetime}, ...]`` as well as a
        dedicated_time_as_str array with a string representation of
        each entry

        :param file: optional file to parse. Defaults to the one under
                     ``PBS_HOME/sched_priv``
        :type file: str or None

        :returns: The dedicated_time list of dictionaries or None on
                  error.Return an empty array if dedicated time file
                  is empty.
        """
        self.dedicated_time_as_str = []
        self.dedicated_time = []

        if file:
            dt_file = file
        elif self.dedicated_time_file:
            dt_file = self.dedicated_time_file
        else:
            dt_file = os.path.join(self.pbs_conf['PBS_HOME'], 'sched_priv',
                                   'dedicated_time')
        try:
            lines = self.du.cat(self.hostname, dt_file, sudo=True)['out']
            if lines is None:
                return []

            for line in lines:
                if not line.startswith('#') and len(line) > 0:
                    self.dedicated_time_as_str.append(line)
                    (dtime_from, dtime_to) = self.utils.convert_dedtime(line)
                    self.dedicated_time.append({'from': dtime_from,
                                                'to': dtime_to})
        except Exception:
            self.logger.error('error in parse_dedicated_time')
            return None

        return self.dedicated_time

    def clear_dedicated_time(self, hup=True):
        """
        Clear the dedicated time file
        """
        self.parse_dedicated_time()
        if ((len(self.dedicated_time) == 0) and
                (len(self.dedicated_time_as_str) == 0)):
            return True
        if self.dedicated_time:
            for d in self.dedicated_time:
                del d
        if self.dedicated_time_as_str:
            for d in self.dedicated_time_as_str:
                del d
        self.dedicated_time = []
        self.dedicated_time_as_str = []
        dt = "# FORMAT: MM/DD/YYYY HH:MM MM/DD/YYYY HH:MM"
        return self.add_dedicated_time(dt, hup=hup)

    def add_dedicated_time(self, as_str=None, start=None, end=None, hup=True):
        """
        Append a dedicated time entry. The function can be called
        in one of two ways, either by passing in start and end as
        time values, or by passing as_str, a string that gets
        appended to the dedicated time entries and formatted as
        follows, note that no check on validity of the format will
        be made the function uses strftime to parse the datetime
        and will fail if the strftime can not convert the string.
        ``MM/DD/YYYY HH:MM MM/DD/YYYY HH:MM``

        :returns: True on success and False otherwise
        """
        if self.dedicated_time is None:
            self.parse_dedicated_time()

        if start is not None and end is not None:
            dtime_from = time.strftime("%m/%d/%Y %H:%M", time.localtime(start))
            dtime_to = time.strftime("%m/%d/%Y %H:%M", time.localtime(end))
            dedtime = dtime_from + " " + dtime_to
        elif as_str is not None:
            (dtime_from, dtime_to) = self.utils.convert_dedtime(as_str)
            dedtime = as_str
        else:
            self.logger.warning("no dedicated from/to specified")
            return True

        for d in self.dedicated_time_as_str:
            if dedtime == d:
                if dtime_from is None or dtime_to is None:
                    self.logger.info(self.logprefix +
                                     "dedicated time already defined")
                else:
                    self.logger.info(self.logprefix +
                                     "dedicated time from " + dtime_from +
                                     " to " + dtime_to + " already defined")
                return True

        if dtime_from is not None and dtime_to is not None:
            self.logger.info(self.logprefix +
                             "adding dedicated time " + dedtime)

        self.dedicated_time_as_str.append(dedtime)
        if dtime_from is not None and dtime_to is not None:
            self.dedicated_time.append({'from': dtime_from, 'to': dtime_to})
        try:
            fn = self.du.create_temp_file()
            with open(fn, "w") as fd:
                for l in self.dedicated_time_as_str:
                    fd.write(l + '\n')
            ddfile = os.path.join(self.pbs_conf['PBS_HOME'], 'sched_priv',
                                  'dedicated_time')
            self.du.run_copy(self.hostname, src=fn, dest=ddfile, sudo=True,
                             preserve_permission=False)
            os.remove(fn)
        except Exception:
            raise PbsSchedConfigError(rc=1, rv=False,
                                      msg='error adding dedicated time')

        if hup:
            ret = self.signal('-HUP')
            if ret['rc'] != 0:
                raise PbsSchedConfigError(rc=1, rv=False,
                                          msg='error adding dedicated time')

        return True

    def terminate(self):
        self.signal('-KILL')

    def valgrind(self):
        """
        run scheduler instance through valgrind
        """
        if self.isUp():
            self.terminate()

        rv = CliUtils().check_bin('valgrind')
        if not rv:
            self.logger.error(self.logprefix + 'valgrind not available')
            return None

        cmd = ['valgrind']

        cmd += ["--log-file=" + os.path.join(tempfile.gettempdir(),
                                             'schd.vlgrd')]
        cmd += [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbs_sched')]

        return self.du.run_cmd(self.hostname, cmd, sudo=True)

    def alloc_to_execvnode(self, chunks):
        """
        convert a resource allocation to an execvnode string representation
        """
        execvnode = []
        for chunk in chunks:
            execvnode += ["(" + chunk.vnode]
            for res, val in chunk.resources.items():
                execvnode += [":" + str(res) + "=" + str(val)]
            for vchk in chunk.vchunk:
                execvnode += ["+" + vchk.vnode]
                for res, val in vchk.resources():
                    execvnode += [":" + str(res) + "=" + str(val)]
            execvnode += [")+"]

        if len(execvnode) != 0:
            ev = execvnode[len(execvnode) - 1]
            ev = ev[:-1]
            execvnode[len(execvnode) - 1] = ev

        return "".join(execvnode)

    def cycles(self, start=None, end=None, firstN=None, lastN=None):
        """
        Analyze scheduler log and return cycle information

        :param start: Optional setting of the start time to consider
        :param end: Optional setting of the end time to consider
        :param firstN: Optional setting to consider the given first
                       N cycles
        :param lastN: Optional setting to consider only the given
                      last N cycles
        """
        try:
            from ptl.utils.pbs_logutils import PBSSchedulerLog
        except Exception:
            self.logger.error('error loading ptl.utils.pbs_logutils')
            return None

        if 'sched_log' in self.attributes:
            logdir = self.attributes['sched_log']
        else:
            logdir = os.path.join(self.pbs_conf['PBS_HOME'], 'sched_logs')

        tm = time.strftime("%Y%m%d", time.localtime())
        log_file = os.path.join(logdir, tm)

        if start is not None or end is not None:
            analyze_path = os.path.dirname(log_file)
        else:
            analyze_path = log_file

        sl = PBSSchedulerLog()
        sl.analyze(analyze_path, start, end, self.hostname)
        cycles = sl.cycles
        if cycles is None or len(cycles) == 0:
            return []

        if lastN is not None:
            return cycles[-lastN:]
        elif firstN is not None:
            return cycles[:firstN]

        return cycles

    def decay_fairshare_tree(self):
        """
        Decay the fairshare tree through pbsfs
        """
        if self.has_snap:
            return True

        cmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')]
        if self.sc_name is not 'default':
            cmd += ['-I', self.sc_name]
        cmd += ['-d']

        ret = self.du.run_cmd(self.hostname, cmd, runas=self.user)
        if ret['rc'] == 0:
            self.fairshare_tree = self.fairshare.query_fairshare()
            return True
        return False

    def parse_resource_group(self, hostname=None, resource_group=None):
        """
        Parse the Scheduler's ``resource_group`` file

        :param hostname: The name of the host from which to parse
                         resource_group
        :type hostname: str or None
        :param resource_group: The path to a resource_group file
        :type resource_group: str or None
        :returns: A fairshare tree
        """

        if hostname is None:
            hostname = self.hostname
        # if resource_group is None:
        resource_group = self.resource_group_file
        # if.has_snap is True acces to sched_priv may not require su privilege
        ret = self.du.cat(hostname, resource_group, sudo=(not self.has_snap))
        if ret['rc'] != 0:
            self.logger.error(hostname + ' error reading ' + resource_group)
        tree = FairshareTree(hostname, resource_group)
        root = FairshareNode('root', -1, parent_id=0, nshares=100)
        tree.add_node(root, apply=False)
        lines = ret['out']
        for line in lines:
            line = line.strip()
            if not line.startswith("#") and len(line) > 0:
                # could have 5th column but we only need the first 4
                (name, id, parent, nshares) = line.split()[:4]
                node = FairshareNode(name, id, parent_name=parent,
                                     nshares=nshares)
                tree.add_node(node, apply=False)
        tree.update()
        return tree

    def add_to_resource_group(self, name, fairshare_id, parent, nshares,
                              validate=True):
        """
        Add an entry to the resource group file

        :param name: The name of the entity to add
        :type name: str or :py:class:`~ptl.lib.pbs_testlib.PbsUser`
        :param fairshare_id: The numeric identifier of the entity to add
        :type fairshare_id: int
        :param parent: The name of the parent group
        :type parent: str
        :param nshares: The number of shares associated to the entity
        :type nshares: int
        :param validate: if True (the default), validate the
                         configuration settings.
        :type validate: bool
        """
        if self.resource_group is None:
            self.resource_group = self.parse_resource_group(
                self.hostname, self.resource_group_file)
        if not self.resource_group:
            self.resource_group = FairshareTree(
                self.hostname, self.resource_group_file)
        if isinstance(name, PbsUser):
            name = str(name)
        reconfig_time = time.time()
        rc = self.resource_group.create_node(name, fairshare_id,
                                             parent_name=parent,
                                             nshares=nshares)
        if validate:
            self.get_pid()
            self.signal('-HUP')
            try:
                self.log_match("Sched;reconfigure;Scheduler is reconfiguring",
                               starttime=reconfig_time)
                self.log_match("fairshare;resgroup: error ",
                               starttime=reconfig_time, existence=False,
                               max_attempts=2)
            except PtlLogMatchError:
                _msg = 'Error in validating resource_group changes'
                raise PbsSchedConfigError(rc=1, rv=False,
                                          msg=_msg)
        return rc

    def job_formula(self, jobid=None, starttime=None, max_attempts=None):
        """
        Extract formula value out of scheduler log

        :param jobid: Optional, the job identifier for which to get
                      the formula.
        :type jobid: str or int
        :param starttime: The time at which to start parsing the
                          scheduler log
        :param max_attempts: The number of attempts to search for
                             formula in the logs
        :type max_attempts: int
        :returns: If jobid is specified, return the formula value
                  associated to that job if no jobid is specified,
                  returns a dictionary mapping job ids to formula
        """
        if jobid is None:
            jobid = "(?P<jobid>.*)"
            _alljobs = True
        else:
            if isinstance(jobid, int):
                jobid = str(jobid)
            _alljobs = False

        formula_pat = (".*Job;" + jobid +
                       ".*;Formula Evaluation = (?P<fval>.*)")
        if max_attempts is None:
            max_attempts = self.ptl_conf['max_attempts']
        rv = self.log_match(formula_pat, regexp=True, starttime=starttime,
                            n='ALL', allmatch=True,
                            max_attempts=max_attempts)
        ret = {}
        if rv:
            for _, l in rv:
                m = re.match(formula_pat, l)
                if m:
                    if _alljobs:
                        jobid = m.group('jobid')
                    ret[jobid] = float(m.group('fval').strip())

        if not _alljobs:
            if jobid in ret:
                return ret[jobid]
            else:
                return
        return ret

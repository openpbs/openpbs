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

import unittest
import logging
import subprocess
import pwd
import grp
import os
import sys
import platform
import socket
import time
import calendar
import ptl
from ptl.utils.pbs_logutils import PBSLogAnalyzer
from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_cliutils import CliUtils
from ptl.utils.pbs_procutils import ProcMonitor
from ptl.lib.pbs_testlib import *
try:
    from ptl.utils.plugins.ptl_test_tags import tags
except ImportError:
    def tags(*args, **kwargs):
        pass
try:
    from nose.plugins.skip import SkipTest
except ImportError:
    class SkipTest(Exception):
        pass


# Test users/groups are expected to exist on the test systems
# User running the tests and the test users should have passwordless sudo
# access configured to avoid interrupted (queries for password) test runs

# Groups
TSTGRP0 = PbsGroup('tstgrp00', gid=1900)
TSTGRP1 = PbsGroup('tstgrp01', gid=1901)
TSTGRP2 = PbsGroup('tstgrp02', gid=1902)
TSTGRP3 = PbsGroup('tstgrp03', gid=1903)
TSTGRP4 = PbsGroup('tstgrp04', gid=1904)
TSTGRP5 = PbsGroup('tstgrp05', gid=1905)
TSTGRP6 = PbsGroup('tstgrp06', gid=1906)
TSTGRP7 = PbsGroup('tstgrp07', gid=1907)
GRP_PBS = PbsGroup('pbs', gid=901)
GRP_AGT = PbsGroup('agt', gid=1146)
ROOT_GRP = PbsGroup(grp.getgrgid(0).gr_name, gid=0)

# Users
# first group from group list is primary group of user
TEST_USER = PbsUser('pbsuser', uid=4359, groups=[TSTGRP0])
TEST_USER1 = PbsUser('pbsuser1', uid=4361, groups=[TSTGRP0, TSTGRP1, TSTGRP2])
TEST_USER2 = PbsUser('pbsuser2', uid=4362, groups=[TSTGRP0, TSTGRP1, TSTGRP3])
TEST_USER3 = PbsUser('pbsuser3', uid=4363, groups=[TSTGRP0, TSTGRP1, TSTGRP4])
TEST_USER4 = PbsUser('pbsuser4', uid=4364, groups=[TSTGRP1, TSTGRP4, TSTGRP5])
TEST_USER5 = PbsUser('pbsuser5', uid=4365, groups=[TSTGRP2, TSTGRP4, TSTGRP6])
TEST_USER6 = PbsUser('pbsuser6', uid=4366, groups=[TSTGRP3, TSTGRP4, TSTGRP7])
TEST_USER7 = PbsUser('pbsuser7', uid=4368, groups=[TSTGRP1])

OTHER_USER = PbsUser('pbsother', uid=4358, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                   GRP_AGT])
PBSTEST_USER = PbsUser('pbstest', uid=4355, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                    GRP_AGT])
TST_USR = PbsUser('tstusr00', uid=11000, groups=[TSTGRP0])
TST_USR1 = PbsUser('tstusr01', uid=11001, groups=[TSTGRP0])

BUILD_USER = PbsUser('pbsbuild', uid=9000, groups=[TSTGRP0])
DATA_USER = PbsUser('pbsdata', uid=4372, groups=[TSTGRP0])
MGR_USER = PbsUser('pbsmgr', uid=4367, groups=[TSTGRP0])
OPER_USER = PbsUser('pbsoper', uid=4356, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                 GRP_AGT])
ADMIN_USER = PbsUser('pbsadmin', uid=4357, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                   GRP_AGT])
PBSROOT_USER = PbsUser('pbsroot', uid=4371, groups=[TSTGRP0, TSTGRP2])
ROOT_USER = PbsUser('root', uid=0, groups=[ROOT_GRP])

PBS_USERS = (TEST_USER, TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
             TEST_USER5, TEST_USER6, TEST_USER7, OTHER_USER, PBSTEST_USER,
             TST_USR, TST_USR1)

PBS_GROUPS = (TSTGRP0, TSTGRP1, TSTGRP2, TSTGRP3, TSTGRP4, TSTGRP5, TSTGRP6,
              TSTGRP7, GRP_PBS, GRP_AGT)

PBS_OPER_USERS = (OPER_USER,)

PBS_MGR_USERS = (MGR_USER, ADMIN_USER)

PBS_DATA_USERS = (DATA_USER,)

PBS_ROOT_USERS = (PBSROOT_USER, ROOT_USER)

PBS_BUILD_USERS = (BUILD_USER,)

SETUPLOG = 'setuplog'
TEARDOWNLOG = 'teardownlog'

SMOKE = 'smoke'
REGRESSION = 'regression'
NUMNODES = 'numnodes'
TIMEOUT_KEY = '__testcase_timeout__'


def timeout(val):
    """
    Decorator to set timeout value of test case
    """
    def wrapper(obj):
        setattr(obj, TIMEOUT_KEY, int(val))
        return obj
    return wrapper


def checkModule(modname):
    """
    Decorator to check if named module is available on the system
    and if not skip the test
    """
    def decorated(function):
        def wrapper(self, *args, **kwargs):
            import imp
            try:
                imp.find_module(modname)
            except ImportError:
                self.skipTest(reason='Module unavailable ' + modname)
            else:
                function(self, *args, **kwargs)
        wrapper.__doc__ = function.__doc__
        wrapper.__name__ = function.__name__
        return wrapper
    return decorated


def skipOnCray(function):
    """
    Decorator to skip a test on a ``Cray`` system
    """

    def wrapper(self, *args, **kwargs):
        if self.mom.is_cray():
            self.skipTest(reason='capability not supported on Cray')
        else:
            function(self, *args, **kwargs)
    wrapper.__doc__ = function.__doc__
    wrapper.__name__ = function.__name__
    return wrapper


def skipOnCpuSet(function):
    """
    Decorator to skip a test on a CpuSet system
    """

    def wrapper(self, *args, **kwargs):
        if self.mom.is_cpuset_mom():
            self.skipTest(reason='capability not supported on Cpuset')
        else:
            function(self, *args, **kwargs)
    wrapper.__doc__ = function.__doc__
    wrapper.__name__ = function.__name__
    return wrapper


class PBSServiceInstanceWrapper(dict):

    """
    A wrapper class to handle multiple service
    ``(i.e., mom, server, scheduler)``instances as passed along
    through the test harness ``(pbs_benchpress)``.Returns an
    ordered dictionary of PBS service instances ``(i.e., mom/server/
    scheduler)``

    Users may invoke PTL using pointers to multiple services per
    host, for example:

    ``pbs_benchpress -p moms=hostA@/etc/pbs.conf,hostB,hostA@/etc/pbs.conf3``

    In such cases, the moms instance variable must be able to distinguish
    the ``self.moms['hostA']`` instances, each instance will be mapped
    to a unique configuration file
    """

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(self, *args, **kwargs)
        self.orderedlist = super(self.__class__, self).keys()

    def __setitem__(self, key, value):
        super(self.__class__, self).__setitem__(key, value)
        if key not in self.orderedlist:
            self.orderedlist.append(key)

    def __getitem__(self, key):
        for k, v in self.items():
            if k == key:
                return v
            if '@' in k:
                name, _ = k.split('@')
                if key in name:
                    return v
            else:
                name = k
            # Users may have specified shortnames instead of FQDN, in order
            # to not enforce that PBS_SERVER match the hostname passed in as
            # parameter, we check if a shortname matches a FQDN entry
            if '.' in key and key.split('.')[0] in name:
                return v
            if '.' in name and name.split('.')[0] in key:
                return v
        return None

    def __contains__(self, key):
        if key in self.keys():
            return True

        for k in self.keys():
            if '@' in k:
                name, _ = k.split('@')
                if key in name:
                    return True
            else:
                name = k
            # Users may have specified shortnames instead of FQDN, in order
            # to not enforce that PBS_SERVER match the hostname passed in as
            # parameter, we check if a shortname matches a FQDN entry
            if '.' in key and key.split('.')[0] in name:
                return True
            if '.' in name and name.split('.')[0] in key:
                return True
        return False

    def __iter__(self):
        return iter(self.orderedlist)

    def host_keys(self):
        return map(lambda h: h.split('@')[0], self.keys())

    def keys(self):
        return self.orderedlist

    def itervalues(self):
        return (self[key] for key in self.orderedlist)

    def values(self):
        return [self[key] for key in self.orderedlist]


class setUpClassError(Exception):
    pass


class tearDownClassError(Exception):
    pass


class PBSTestSuite(unittest.TestCase):

    """
    Generic ``setup``, ``teardown``, and ``logging`` functions to
    be used as parent class for most tests.
    Class instantiates:

    ``server object connected to localhost``

    ``scheduler objected connected to localhost``

    ``mom object connected to localhost``

    Custom parameters:

    :param server: The hostname on which the PBS ``server/scheduler``
                   are running
    :param mom: The hostname on which the PBS MoM is running
    :param servers: Colon-separated list of hostnames hosting a PBS server.
                    Servers are then accessible as a dictionary in the
                    instance variable servers.
    :param client: For CLI mode only, name of the host on which the PBS
                   client commands are to be run from. Format is
                   ``<host>@<path-to-config-file>``
    :param moms: Colon-separated list of hostnames hosting a PBS MoM.
                 MoMs are made accessible as a dictionary in the instance
                 variable moms.
    :param comms: Colon-separated list of hostnames hosting a PBS Comm.
                  Comms are made accessible as a dictionary in the
                  instance variable comms.
    :param nomom=<host1>\:<host2>...: expect no MoM on given set of hosts
    :param mode: Sets mode of operation to PBS server. Can be either
                 ``'cli'`` or ``'api'``.Defaults to API behavior.
    :param conn_timeout: set a timeout in seconds after which a pbs_connect
                         IFL call is refreshed (i.e., disconnected)
    :param skip-setup: Bypasses setUp of PBSTestSuite (not custom ones)
    :param skip-teardown: Bypasses tearDown of PBSTestSuite (not custom ones)
    :param procinfo: Enables process monitoring thread, logged into
                     ptl_proc_info test metrics. The value can be set to
                     _all_ to monitor all PBS processes,including
                     ``pbs_server``, ``pbs_sched``, ``pbs_mom``, or a process
                     defined by name.
    :param revert-to-defaults=<True|False>: if False, will not revert to
                                            defaults.True by default.
    :param revert-hooks=<True|False>: if False, do not revert hooks to
                                      defaults.Defaults to True.
                                      ``revert-to-defaults`` set to False
                                      overrides this setting.
    :param del-hooks=<True|False>: If False, do not delete hooks. Defaults
                                   to False.``revert-to-defaults`` set to
                                   False overrides this setting.
    :param revert-queues=<True|False>: If False, do not revert queues to
                                       defaults.Defaults to True.
                                       ``revert-to-defaults`` set to False
                                       overrides this setting.
    :param revert-resources=<True|False>: If False, do not revert resources
                                          to defaults. Defaults to True.
                                          ``revert-to-defaults`` set to False
                                          overrides this setting.
    :param del-queues=<True|False>: If False, do not delete queues. Defaults
                                    to False.``revert-to-defaults`` set to
                                    Falseoverrides this setting.
    :param del-vnodes=<True|False>: If False, do not delete vnodes on MoM
                                    instances.Defaults to True.
    :param server-revert-to-defaults=<True|False>: if False, don't revert
                                                   Server to defaults
    :param comm-revert-to-defaults=<True|False>: if False, don't revert Comm
                                                 to defaults
    :param mom-revert-to-defaults=<True|False>: if False, don't revert MoM
                                                to defaults
    :param sched-revert-to-defaults=<True|False>: if False, don't revert
                                                  Scheduler to defaults
    :param procmon: Enables process monitoring. Multiple values must be
                    colon separated. For example to monitor ``server``,
                    ``sched``, and ``mom`` use
                    ``procmon=pbs_server:pbs_sched:pbs_mom``
    :param procmon-freq: Sets a polling frequency for the process monitoring
                         tool.Defaults to 10 seconds.
    :param test-users: colon-separated list of users to use as test users.
                       The users specified override the default users in the
                       order in which they appear in the ``PBS_USERS`` list.
    :param default-testcase-timeout: Default test case timeout value.
    :param data-users: colon-separated list of data users.
    :param oper-users: colon-separated list of operator users.
    :param mgr-users: colon-separated list of manager users.
    :param root-users: colon-separated list of root users.
    :param build-users: colon-separated list of build users.
    :param clienthost: the hostnames to set in the MoM config file
    """

    logger = logging.getLogger(__name__)
    metrics_data = {}
    conf = {}
    param = None
    du = DshUtils()
    _procmon = None
    _process_monitoring = False
    revert_to_defaults = True
    server_revert_to_defaults = True
    mom_revert_to_defaults = True
    sched_revert_to_defaults = True
    revert_queues = True
    revert_resources = True
    revert_hooks = True
    del_hooks = True
    del_queues = True
    del_vnodes = True
    server = None
    scheduler = None
    mom = None
    comm = None
    servers = None
    schedulers = {}
    scheds = None
    moms = None
    comms = None

    @classmethod
    def setUpClass(cls):
        cls.log_enter_setup(True)
        cls._testMethodName = 'setUpClass'
        cls.parse_param()
        cls.init_param()
        cls.check_users_exist()
        cls.init_servers()
        cls.init_comms()
        cls.init_schedulers()
        cls.init_moms()
        cls.log_end_setup(True)

    def setUp(self):
        if 'skip-setup' in self.conf:
            return
        self.log_enter_setup()
        self.init_proc_mon()
        self.revert_servers()
        self.revert_comms()
        self.revert_schedulers()
        self.revert_moms()
        self.log_end_setup()

    @classmethod
    def log_enter_setup(cls, iscls=False):
        _m = ' Entered ' + cls.__name__ + ' setUp'
        if iscls:
            _m += 'Class'
        _m_len = len(_m)
        cls.logger.info('=' * _m_len)
        cls.logger.info(_m)
        cls.logger.info('=' * _m_len)

    @classmethod
    def log_end_setup(cls, iscls=False):
        _m = 'Completed ' + cls.__name__ + ' setUp'
        if iscls:
            _m += 'Class'
        _m_len = len(_m)
        cls.logger.info('=' * _m_len)
        cls.logger.info(_m)
        cls.logger.info('=' * _m_len)

    @classmethod
    def _validate_param(cls, pname):
        """
        Check if parameter was enabled at the ``command-line``

        :param pname: parameter name
        :type pname: str
        :param pvar: class variable to set according to command-line setting
        """
        if pname not in cls.conf:
            return
        if cls.conf[pname] in PTL_TRUE:
            setattr(cls, pname.replace('-', '_'), True)
        else:
            setattr(cls, pname.replace('-', '_'), False)

    @classmethod
    def _set_user(cls, name, user_list):
        if name in cls.conf:
            for idx, u in enumerate(cls.conf[name].split(':')):
                user_list[idx].__init__(u)

    @classmethod
    def check_users_exist(cls):
        """
        Check whether the user is exist or not
        """
        testusersexist = True
        for u in [TEST_USER, TEST_USER1, TEST_USER2, TEST_USER3]:
            rv = cls.du.check_user_exists(str(u))
            if not rv:
                _msg = 'User ' + str(u) + ' does not exist!'
                raise setUpClassError(_msg)
        return testusersexist

    @classmethod
    def kicksched_action(cls, server, obj_type, *args, **kwargs):
        """
        custom scheduler action to kick a scheduling cycle when expectig
        a job state change
        """
        if server is None:
            cls.logger.error('no server defined for custom action')
            return
        if obj_type == JOB:
            if (('scheduling' in server.attributes) and
                    (server.attributes['scheduling'] != 'False')):
                server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                               {'scheduling': 'True'},
                               level=logging.DEBUG)

    @classmethod
    def parse_param(cls):
        """
        get test configuration parameters as a ``comma-separated``
        list of attributes.

        Attributes may be ``'='`` separated key value pairs or standalone
        entries.

        ``Multi-property`` attributes are colon-delimited.
        """
        if cls.param is None:
            return
        for h in cls.param.split(','):
            if '=' in h:
                k, v = h.split('=')
                cls.conf[k.strip()] = v.strip()
            else:
                cls.conf[h.strip()] = ''
        if (('clienthost' in cls.conf) and
                not isinstance(cls.conf['clienthost'], list)):
            cls.conf['clienthost'] = cls.conf['clienthost'].split(':')
        users_map = [('test-users', PBS_USERS),
                     ('oper-users', PBS_OPER_USERS),
                     ('mgr-users', PBS_MGR_USERS),
                     ('data-users', PBS_DATA_USERS),
                     ('root-users', PBS_ROOT_USERS),
                     ('build-users', PBS_BUILD_USERS)]
        for k, v in users_map:
            cls._set_user(k, v)

    @classmethod
    def init_param(cls):
        cls._validate_param('revert-to-defaults')
        cls._validate_param('server-revert-to-defaults')
        cls._validate_param('comm-revert-to-defaults')
        cls._validate_param('mom-revert-to-defaults')
        cls._validate_param('sched-revert-to-defaults')
        cls._validate_param('del-hooks')
        cls._validate_param('revert-hooks')
        cls._validate_param('del-queues')
        cls._validate_param('del-vnodes')
        cls._validate_param('revert-queues')
        cls._validate_param('revert-resources')
        if 'default-testcase-timeout' not in cls.conf.keys():
            cls.conf['default_testcase_timeout'] = 180
        else:
            cls.conf['default_testcase_timeout'] = int(
                cls.conf['default-testcase-timeout'])

    @classmethod
    def is_server_licensed(cls, server):
        """
        Check if server is licensed or not
        """
        for i in range(0, 10, 1):
            lic = server.status(SERVER, 'license_count', level=logging.INFOCLI)
            if lic and 'license_count' in lic[0]:
                lic = PbsTypeLicenseCount(lic[0]['license_count'])
                if int(lic['Avail_Sockets']) > 0:
                    return True
                elif int(lic['Avail_Global']) > 0:
                    return True
                elif int(lic['Avail_Local']) > 0:
                    return True
            time.sleep(i)
        return False

    @classmethod
    def init_from_conf(cls, conf, single=None, multiple=None, skip=None,
                       func=None):
        """
        Helper method to parse test parameters for`` mom/server/scheduler``
        instances.

        The supported format of each service request is:

        ``hostname@configuration/path``

        For example:

        ``pbs_benchpress -p server=remote@/etc/pbs.conf.12.0``

        initializes a remote server instance that is configured according to
        the remote file ``/etc/pbs.conf.12.0``
        """
        endpoints = []
        if ((multiple in conf) and (conf[multiple] is not None)):
            __objs = conf[multiple].split(':')
            for _m in __objs:
                tmp = _m.split('@')
                if len(tmp) == 2:
                    endpoints.append(tuple(tmp))
                elif len(tmp) == 1:
                    endpoints.append((tmp[0], None))
        elif ((single in conf) and (conf[single] is not None)):
            tmp = conf[single].split('@')
            if len(tmp) == 2:
                endpoints.append(tuple(tmp))
            elif len(tmp) == 1:
                endpoints.append((tmp[0], None))
        else:
            endpoints = [(socket.gethostname(), None)]
        objs = PBSServiceInstanceWrapper()
        for name, objconf in endpoints:
            if ((skip is not None) and (skip in conf) and
                    ((name in conf[skip]) or (conf[skip] in name))):
                continue
            if objconf is not None:
                n = name + '@' + objconf
            else:
                n = name
            if getattr(cls, "server", None) is not None:
                objs[n] = func(name, pbsconf_file=objconf,
                               server=cls.server.hostname)
            else:
                objs[n] = func(name, pbsconf_file=objconf)
            if objs[n] is None:
                _msg = 'Failed %s(%s, %s)' % (func.__name__, name, objconf)
                raise setUpClassError(_msg)
            objs[n].initialise_service()
        return objs

    @classmethod
    def init_servers(cls, init_server_func=None, skip=None):
        """
        Initialize servers
        """
        if init_server_func is None:
            init_server_func = cls.init_server
        if 'servers' in cls.conf:
            if 'comms' not in cls.conf:
                cls.conf['comms'] = cls.conf['servers']
            if 'schedulers' not in cls.conf:
                cls.conf['schedulers'] = cls.conf['servers']
            if 'moms' not in cls.conf:
                cls.conf['moms'] = cls.conf['servers']
        if 'server' in cls.conf:
            if 'comm' not in cls.conf:
                cls.conf['comm'] = cls.conf['server']
            if 'scheduler' not in cls.conf:
                cls.conf['scheduler'] = cls.conf['server']
            if 'mom' not in cls.conf:
                cls.conf['mom'] = cls.conf['server']
        cls.servers = cls.init_from_conf(conf=cls.conf, single='server',
                                         multiple='servers', skip=skip,
                                         func=init_server_func)
        if cls.servers:
            cls.server = cls.servers.values()[0]

    @classmethod
    def init_comms(cls, init_comm_func=None, skip=None):
        """
        Initialize comms
        """
        if init_comm_func is None:
            init_comm_func = cls.init_comm
        cls.comms = cls.init_from_conf(conf=cls.conf,
                                       single='comm',
                                       multiple='comms', skip=skip,
                                       func=init_comm_func)
        if cls.comms:
            cls.comm = cls.comms.values()[0]

    @classmethod
    def init_schedulers(cls, init_sched_func=None, skip=None):
        """
        Initialize schedulers
        """
        if init_sched_func is None:
            init_sched_func = cls.init_scheduler
        cls.scheds = cls.init_from_conf(conf=cls.conf,
                                        single='scheduler',
                                        multiple='schedulers', skip=skip,
                                        func=init_sched_func)

        for sched in cls.scheds.values():
            if sched.server.name in cls.schedulers:
                continue
            else:
                cls.schedulers[sched.server.name] = sched.server.schedulers
        # creating a short hand for current host server.schedulers
        cls.scheds = cls.server.schedulers
        cls.scheduler = cls.scheds['default']

    @classmethod
    def init_moms(cls, init_mom_func=None, skip='nomom'):
        """
        Initialize moms
        """
        if init_mom_func is None:
            init_mom_func = cls.init_mom
        cls.moms = cls.init_from_conf(conf=cls.conf, single='mom',
                                      multiple='moms', skip=skip,
                                      func=init_mom_func)
        if cls.moms:
            cls.mom = cls.moms.values()[0]

    @classmethod
    def init_server(cls, hostname, pbsconf_file=None):
        """
        Initialize a server instance

        Define custom expect action to trigger a scheduling cycle when job
        is not in running state

        :returns: The server instance on success and None on failure
        """
        client = hostname
        client_conf = None
        if 'client' in cls.conf:
            _cl = cls.conf['client'].split('@')
            client = _cl[0]
            if len(_cl) > 1:
                client_conf = _cl[1]
        server = Server(hostname, pbsconf_file=pbsconf_file, client=client,
                        client_pbsconf_file=client_conf)
        server._conn_timeout = 0
        if cls.conf is not None:
            if 'mode' in cls.conf:
                if cls.conf['mode'] == 'cli':
                    server.set_op_mode(PTL_CLI)
            if 'conn_timeout' in cls.conf:
                conn_timeout = int(cls.conf['conn_timeout'])
                server.set_connect_timeout(conn_timeout)
        sched_action = ExpectAction('kicksched', True, JOB,
                                    cls.kicksched_action)
        server.add_expect_action(action=sched_action)
        return server

    @classmethod
    def init_comm(cls, hostname, pbsconf_file=None, server=None):
        """
        Initialize a Comm instance associated to the given hostname.

        This method must be called after init_server

        :param hostname: The host on which the Comm is running
        :type hostname: str
        :param pbsconf_file: Optional path to an alternate pbs config file
        :type pbsconf_file: str or None
        :returns: The instantiated Comm upon success and None on failure.
        :param server: The server name associated to the Comm
        :type server: str
        Return the instantiated Comm upon success and None on failure.
        """
        try:
            server = cls.servers[server]
        except:
            server = None
        return Comm(hostname, pbsconf_file=pbsconf_file, server=server)

    @classmethod
    def init_scheduler(cls, hostname, pbsconf_file=None, server=None):
        """
        Initialize a Scheduler instance associated to the given server.
        This method must be called after ``init_server``

        :param server: The server name associated to the scheduler
        :type server: str
        :param pbsconf_file: Optional path to an alternate config file
        :type pbsconf_file: str or None
        :param hostname: The host on which Sched is running
        :type hostname: str
        :returns: The instantiated scheduler upon success and None on failure
        """
        try:
            server = cls.servers[server]
        except:
            server = None
        return Scheduler(hostname=hostname, server=server,
                         pbsconf_file=pbsconf_file)

    @classmethod
    def init_mom(cls, hostname, pbsconf_file=None, server=None):
        """
        Initialize a ``MoM`` instance associated to the given hostname.

        This method must be called after ``init_server``

        :param hostname: The host on which the MoM is running
        :type hostname: str
        :param pbsconf_file: Optional path to an alternate pbs config file
        :type pbsconf_file: str or None
        :returns: The instantiated MoM upon success and None on failure.
        """
        try:
            server = cls.servers[server]
        except:
            server = None
        return MoM(hostname, pbsconf_file=pbsconf_file, server=server)

    def init_proc_mon(self):
        """
        Initialize process monitoring when requested
        """
        if 'procmon' in self.conf:
            _proc_mon = []
            for p in self.conf['procmon'].split(':'):
                _proc_mon += ['.*' + p + '.*']
            if _proc_mon:
                if 'procmon-freq' in self.conf:
                    freq = int(self.conf['procmon-freq'])
                else:
                    freq = 10
                self.start_proc_monitor(name='|'.join(_proc_mon), regexp=True,
                                        frequency=freq)
                self._process_monitoring = True

    def revert_servers(self, force=False):
        """
        Revert the values set for servers
        """
        for server in self.servers.values():
            self.revert_server(server, force)

    def revert_comms(self, force=False):
        """
        Revert the values set for comms
        """
        for comm in self.comms.values():
            self.revert_comm(comm, force)

    def revert_schedulers(self, force=False):
        """
        Revert the values set for schedulers
        """
        for scheds in self.schedulers.values():
            for sched in scheds.keys():
                if sched == 'default':
                    self.revert_scheduler(scheds[sched], force)

    def revert_moms(self, force=False):
        """
        Revert the values set for moms
        """
        self.del_all_nodes = True
        for mom in self.moms.values():
            self.revert_mom(mom, force)

    def revert_server(self, server, force=False):
        """
        Revert the values set for server
        """
        rv = server.isUp()
        if not rv:
            self.logger.error('server ' + server.hostname + ' is down')
            server.start()
            msg = 'Failed to restart server ' + server.hostname
            self.assertTrue(server.isUp(), msg)
        server_stat = server.status(SERVER)[0]
        current_user = pwd.getpwuid(os.getuid())[0]
        try:
            # remove current user's entry from managers list (if any)
            a = {ATTR_managers: (DECR, current_user + '@*')}
            server.manager(MGR_CMD_SET, SERVER, a, sudo=True)
        except:
            pass
        a = {ATTR_managers: (INCR, current_user + '@*')}
        server.manager(MGR_CMD_SET, SERVER, a, sudo=True)
        if ((self.revert_to_defaults and self.server_revert_to_defaults) or
                force):
            server.revert_to_defaults(reverthooks=self.revert_hooks,
                                      delhooks=self.del_hooks,
                                      revertqueues=self.revert_queues,
                                      delqueues=self.del_queues,
                                      revertresources=self.revert_resources,
                                      server_stat=server_stat)
        rv = self.is_server_licensed(server)
        _msg = 'No license found on server %s' % (server.shortname)
        self.assertTrue(rv, _msg)
        self.logger.info('server: %s licensed', server.hostname)

    def revert_comm(self, comm, force=False):
        """
        Revert the values set for comm
        """
        rv = comm.isUp()
        if not rv:
            self.logger.error('comm ' + comm.hostname + ' is down')
            comm.start()
            msg = 'Failed to restart comm ' + comm.hostname
            self.assertTrue(comm.isUp(), msg)

    def revert_scheduler(self, scheduler, force=False):
        """
        Revert the values set for scheduler
        """
        rv = scheduler.isUp()
        if not rv:
            self.logger.error('scheduler ' + scheduler.hostname + ' is down')
            scheduler.start()
            msg = 'Failed to restart scheduler ' + scheduler.hostname
            self.assertTrue(scheduler.isUp(), msg)
        if ((self.revert_to_defaults and self.sched_revert_to_defaults) or
                force):
            rv = scheduler.revert_to_defaults()
            _msg = 'Failed to revert sched %s' % (scheduler.hostname)
            self.assertTrue(rv, _msg)

    def revert_mom(self, mom, force=False):
        """
        Revert the values set for mom

        :param mom: the MoM object whose values are to be reverted
        :type mom: MoM object
        :param force: Option to reverse forcibly
        :type force: bool
        """
        rv = mom.isUp()
        if not rv:
            self.logger.error('mom ' + mom.hostname + ' is down')
            mom.start()
            msg = 'Failed to restart mom ' + mom.hostname
            self.assertTrue(mom.isUp(), msg)
        mom.pbs_version()
        if ((self.revert_to_defaults and self.mom_revert_to_defaults) or
                force):
            rv = mom.revert_to_defaults(delvnodedefs=self.del_vnodes)
            _msg = 'Failed to revert mom %s' % (mom.hostname)
            self.assertTrue(rv, _msg)
            if 'clienthost' in self.conf:
                mom.add_config({'$clienthost': self.conf['clienthost']})
            a = {'state': 'free', 'resources_available.ncpus': (GE, 1)}
            nodes = self.server.counter(NODE, a, attrop=PTL_AND,
                                        level=logging.DEBUG)
            if not nodes:
                try:
                    self.server.manager(MGR_CMD_DELETE, NODE, None, '')
                except:
                    pass
                mom.delete_vnode_defs()
                mom.delete_vnodes()
                mom.restart()
                self.logger.info('server: no nodes defined, creating one')
                self.server.manager(MGR_CMD_CREATE, NODE, None, mom.shortname)
        name = mom.shortname
        if mom.platform == 'cray' or mom.platform == 'craysim':
            # delete all nodes(@default) on first call of revert_mom
            # and create all nodes specified by self.moms one by one
            try:
                if self.del_all_nodes:
                    self.server.manager(MGR_CMD_DELETE, NODE, None, '')
                    self.del_all_nodes = False
            except:
                pass
            self.server.manager(MGR_CMD_CREATE, NODE, None, name)
        else:
            try:
                self.server.status(NODE, id=name)
            except PbsStatusError:
                # server doesn't have node with shortname
                # check with hostname
                name = mom.hostname
                try:
                    self.server.status(NODE, id=name)
                except PbsStatusError:
                    # server doesn't have node for this mom yet
                    # so create with shortname
                    name = mom.shortname
                    self.server.manager(MGR_CMD_CREATE, NODE, None,
                                        mom.shortname)
        self.server.expect(NODE, {ATTR_NODE_state: 'free'}, id=name,
                           interval=1)
        return mom

    def analyze_logs(self):
        """
        analyze accounting and scheduler logs from time test was started
        until it finished
        """
        pla = PBSLogAnalyzer()
        self.metrics_data = pla.analyze_logs(serverlog=self.server.logfile,
                                             schedlog=self.scheduler.logfile,
                                             momlog=self.mom.logfile,
                                             acctlog=self.server.acctlogfile,
                                             start=self.server.ctime,
                                             end=int(time.time()))

    def start_proc_monitor(self, name=None, regexp=False, frequency=60):
        """
        Start the process monitoring

        :param name: Process name
        :type name: str or None
        :param regexp: Regular expression to match
        :type regexp: bool
        :param frequency: Frequency of monitoring
        :type frequency: int
        """
        if self._procmon is not None:
            self.logger.info('A process monitor is already instantiated')
            return
        self.logger.info('starting process monitoring of ' + name +
                         ' every ' + str(frequency) + 'seconds')
        self._procmon = ProcMonitor(name=name, regexp=regexp,
                                    frequency=frequency)
        self._procmon.start()

    def stop_proc_monitor(self):
        """
        Stop the process monitoring
        """
        if not self._process_monitoring:
            return
        self.logger.info('stopping process monitoring')
        self._procmon.stop()
        self.metrics_data['procs'] = self._procmon.db_proc_info
        self._process_monitoring = False

    def skipTest(self, reason=None):
        """
        Skip Test

        :param reason: message to indicate why test is skipped
        :type reason: str or None
        """
        if reason:
            self.logger.warning('test skipped: ' + reason)
        else:
            reason = 'unknown'
        raise SkipTest(reason)

    skip_test = skipTest

    @classmethod
    def log_enter_teardown(cls, iscls=False):
        _m = ' Entered ' + cls.__name__ + ' tearDown'
        if iscls:
            _m += 'Class'
        _m_len = len(_m)
        cls.logger.info('=' * _m_len)
        cls.logger.info(_m)
        cls.logger.info('=' * _m_len)

    @classmethod
    def log_end_teardown(cls, iscls=False):
        _m = 'Completed ' + cls.__name__ + ' tearDown'
        if iscls:
            _m += 'Class'
        _m_len = len(_m)
        cls.logger.info('=' * _m_len)
        cls.logger.info(_m)
        cls.logger.info('=' * _m_len)

    def tearDown(self):
        """
        verify that ``server`` and ``scheduler`` are up
        clean up jobs and reservations
        """
        if 'skip-teardown' in self.conf:
            return
        self.log_enter_teardown()
        self.stop_proc_monitor()
        self.log_end_teardown()

    @classmethod
    def tearDownClass(cls):
        cls._testMethodName = 'tearDownClass'

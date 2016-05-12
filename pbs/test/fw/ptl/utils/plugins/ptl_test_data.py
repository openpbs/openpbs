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

import sys
import logging
from nose.plugins.base import Plugin
from ptl.utils.pbs_dshutils import DshUtils
import time
import os
import socket
import threading
import Queue

log = logging.getLogger('nose.plugins.PTLTestData')


class PTLTestData(Plugin):

    """
    Save post analysis data on test cases failure or error
    """
    name = 'PTLTestData'
    score = sys.maxint - 3
    logger = logging.getLogger(__name__)

    def __init__(self):
        self.sharedpath = None
        self.du = DshUtils()
        self.__syncth = None
        self.__queue = Queue.Queue()

    def options(self, parser, env):
        """
        Register command line options
        """
        pass

    def set_data(self, sharedpath):
        self.sharedpath = sharedpath

    def configure(self, options, config):
        """
        Configure the plugin and system, based on selected options
        """
        self.config = config
        self.enabled = True

    def __get_sntnbi_name(self, test):
        if hasattr(test, 'test'):
            _test = test.test
            sn = _test.__class__.__name__
        elif hasattr(test, 'context'):
            _test = test.context
            sn = _test.__name__
        else:
            return ('unknown', 'unknown', 'unknown')
        tn = getattr(_test, '_testMethodName', 'unknown')
        if (hasattr(_test, 'server') and
                (getattr(_test, 'server', None) is not None)):
            bi = _test.server.attributes['pbs_version']
        else:
            bi = 'unknown'
        return (sn, tn, bi)

    def __save_home(self, test, status):
        if hasattr(test, 'test'):
            _test = test.test
        elif hasattr(test, 'context'):
            _test = test.context
        else:
            # test does not have any PBS Objects, so just return
            return
        if not hasattr(_test, 'server'):
            # test does not have any PBS Objects, so just return
            return
        st = getattr(test, 'start_time', None)
        if st is not None:
            st = time.mktime(st.timetuple())
        else:
            st = time.time()
        st -= 180  # starttime - 3 min
        et = getattr(test, 'end_time', None)
        if et is not None:
            et = time.mktime(et.timetuple())
        else:
            et = time.time()
        hostname = socket.gethostname().split('.')[0]
        lp = os.environ.get('PBS_JOBID', time.strftime("%Y%b%d_%H_%m_%S",
                                                       time.localtime()))
        sn, tn, bi = self.__get_sntnbi_name(test)
        if getattr(_test, 'servers', None) is not None:
            shosts = map(lambda x: x.split('.')[0], _test.servers.host_keys())
        else:
            shosts = []
        if getattr(_test, 'schedulers', None) is not None:
            schosts = map(lambda x: x.split('.')[0],
                          _test.schedulers.host_keys())
        else:
            schosts = []
        if getattr(_test, 'moms', None) is not None:
            mhosts = map(lambda x: x.split('.')[0], _test.moms.host_keys())
        else:
            mhosts = []
        hosts = []
        hosts.extend(shosts)
        hosts.extend(schosts)
        hosts.extend(mhosts)
        hosts.append(hostname)
        hosts = sorted(set(hosts))
        for host in hosts:
            confpath = self.du.get_pbs_conf_file(host)
            tmpdir = self.du.get_tempdir(host)
            datadir = os.path.join(tmpdir, bi, sn, hostname, tn, lp)
            _s = ['#!/bin/bash']
            _s += ['. %s' % (confpath)]
            _s += ['mkdir -p %s' % (datadir)]
            _s += ['chmod -R 0755 %s' % (datadir)]
            if host == _test.server.shortname:
                _l = '${PBS_EXEC}/bin/qstat -tf > %s/qstat_tf &' % (datadir)
                _s += [_l]
                _l = '${PBS_EXEC}/bin/pbsnodes -av > %s/pbsnodes &' % (datadir)
                _s += [_l]
                _l = '${PBS_EXEC}/bin/qmgr -c "p s"'
                _l += ' > %s/print_server &' % (datadir)
                _s += [_l]
            _s += ['echo "%s" >> %s/uptime' % ('*' * 80, datadir)]
            _s += ['echo "On host : %s" >> %s/uptime' % (host, datadir)]
            _s += ['uptime >> %s/uptime' % (datadir)]
            _s += ['echo "" >> %s/uptime' % (datadir)]
            _s += ['echo "%s" >> %s/netstat' % ('*' * 80, datadir)]
            _s += ['echo "On host : %s" >> %s/netstat' % (host, datadir)]
            _cmd = self.du.which(host, 'netstat')
            if _cmd == 'netstat':
                _cmd = 'ss'
            if sys.platform.startswith('linux'):
                _cmd += ' -ap'
            else:
                _cmd += ' -an'
            _s += ['%s >> %s/netstat' % (_cmd, datadir)]
            _s += ['echo "" >> %s/netstat' % (datadir)]
            _s += ['echo "%s" >> %s/ps' % ('*' * 80, datadir)]
            _s += ['echo "On host : %s" >> %s/ps' % (host, datadir)]
            _s += ['ps -ef | grep pbs_ >> %s/ps' % (datadir)]
            _s += ['echo "" >> %s/ps' % (datadir)]
            _s += ['echo "%s" >> %s/df' % ('*' * 80, datadir)]
            _s += ['echo "On host : %s" >> %s/df' % (host, datadir)]
            _s += ['df -h >> %s/df' % (datadir)]
            _s += ['echo "" >> %s/df' % (datadir)]
            _s += ['echo "%s" >> %s/vmstat' % ('*' * 80, datadir)]
            _s += ['echo "On host : %s" >> %s/vmstat' % (host, datadir)]
            _s += ['vmstat >> %s/vmstat' % (datadir)]
            _s += ['echo "" >> %s/vmstat' % (datadir)]
            _dst = os.path.join(datadir, 'PBS_' + host)
            _s += ['cp -rp ${PBS_HOME} %s' % (_dst)]
            _s += ['tar -cf %s/datastore.tar %s/datastore' % (_dst, _dst)]
            _s += ['gzip -rf %s/datastore.tar' % (_dst)]
            _s += ['rm -rf %s/datastore' % (_dst)]
            _s += ['rm -rf %s/*_logs' % (_dst)]
            _s += ['rm -rf %s/server_priv/accounting' % (_dst)]
            _s += ['cp %s %s/pbs.conf.%s' % (confpath, _dst, host)]
            if host == hostname:
                _s += ['cat > %s/logfile_%s <<EOF' % (datadir, status)]
                _s += ['%s' % (getattr(test, 'err_in_string', ''))]
                _s += ['']
                _s += ['EOF']
            _s += ['wait']
            fd, fn = self.du.mkstemp(hostname, mode=0755, body='\n'.join(_s))
            os.close(fd)
            self.du.run_cmd(hostname, cmd=fn, sudo=True, logerr=False)
            self.du.rm(hostname, fn, force=True, sudo=True)
            svr = _test.servers[host]
            if svr is not None:
                self.__save_logs(svr, _dst, 'server_logs', st, et)
                _adst = os.path.join(_dst, 'server_priv')
                self.__save_logs(svr, _adst, 'accounting', st, et)
            if getattr(_test, 'moms', None) is not None:
                self.__save_logs(_test.moms[host], _dst, 'mom_logs', st, et)
            if getattr(_test, 'schedulers', None) is not None:
                self.__save_logs(_test.schedulers[host], _dst, 'sched_logs',
                                 st, et)
            if ((self.sharedpath is not None) and (self.__syncth is not None)):
                self.__queue.put((host, datadir, bi, sn, hostname, tn, lp))

    def __save_logs(self, obj, dst, name, st, et, jid=None):
        if name == 'accounting':
            logs = obj.log_lines('accounting', n='ALL', starttime=st,
                                 endtime=et)
            logs = map(lambda x: x + '\n', logs)
        elif name == 'tracejob':
            logs = obj.log_lines('tracejob', id=jid, n='ALL')
            name += '_' + jid
        else:
            logs = obj.log_lines(obj, n='ALL', starttime=st, endtime=et)
        f = open(os.path.join(dst, name), 'w+')
        f.writelines(logs)
        f.close()

    def begin(self):
        if self.sharedpath is not None:
            self.__syncth = SyncData(self.sharedpath, self.__queue)
            self.__syncth.daemon = True
            self.__syncth.start()

    def addError(self, test, err):
        self.__save_home(test, 'ERROR')

    def addFailure(self, test, err):
        self.__save_home(test, 'FAIL')

    def finalize(self, result):
        if ((self.sharedpath is not None) and (self.__syncth is not None)):
            while not self.__queue.empty():
                pass
            self.__syncth.stop()
            self.__syncth.join()


class SyncData(threading.Thread):

    """
    Sync thread
    """

    def __init__(self, sharedpath, queue):
        threading.Thread.__init__(self)
        self.sharedpath = sharedpath
        self.queue = queue
        self._go = True
        self.du = DshUtils()

    def run(self):
        while self._go:
            try:
                host, datadir, bi, sn, hostname, tn, lp = self.queue.get(False,
                                                                         1.0)
            except Queue.Empty:
                continue
            destdatadir = os.path.join(self.sharedpath, bi, sn, hostname, tn,
                                       lp)
            homedir = os.path.join(datadir, 'PBS_' + host)
            _s = ['#!/bin/bash']
            _s += ['mkdir -p %s' % (destdatadir)]
            _s += ['chmod -R 0755 %s' % (destdatadir)]
            _s += ['cp -rp %s %s' % (homedir, destdatadir)]
            _s += ['cp %s/qstat_tf %s' % (datadir, destdatadir)]
            _s += ['cp %s/pbsnodes %s' % (datadir, destdatadir)]
            _s += ['cp %s/print_server %s' % (datadir, destdatadir)]
            _s += ['cp %s/logfile_* %s' % (datadir, destdatadir)]
            _s += ['cat %s/uptime >> %s/uptime' % (datadir, destdatadir)]
            _s += ['cat %s/vmstat >> %s/vmstat' % (datadir, destdatadir)]
            _s += ['cat %s/netstat >> %s/netstat' % (datadir, destdatadir)]
            _s += ['cat %s/ps >> %s/ps' % (datadir, destdatadir)]
            _s += ['cat %s/df >> %s/df' % (datadir, destdatadir)]
            fd, fn = self.du.mkstemp(host, mode=0755, body='\n'.join(_s))
            os.close(fd)
            self.du.run_cmd(host, cmd=fn, sudo=True)

    def stop(self):
        self._go = False

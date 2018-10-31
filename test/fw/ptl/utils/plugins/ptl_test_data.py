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
import os
import sys
import socket
import logging
import signal
import pwd
import re
from nose.util import isclass
from nose.plugins.base import Plugin
from nose.plugins.skip import SkipTest
from ptl.utils.plugins.ptl_test_runner import TimeOut
from ptl.utils.pbs_dshutils import DshUtils

log = logging.getLogger('nose.plugins.PTLTestData')


class PTLTestData(Plugin):

    """
    Save post analysis data on test cases failure or error
    """
    name = 'PTLTestData'
    score = sys.maxint - 6
    logger = logging.getLogger(__name__)

    def __init__(self):
        Plugin.__init__(self)
        self.post_data_dir = None
        self.max_postdata_threshold = None
        self.__save_data_count = 0
        self.__priv_sn = ''
        self.du = DshUtils()

    def options(self, parser, env):
        """
        Register command line options
        """
        pass

    def set_data(self, post_data_dir, max_postdata_threshold):
        self.post_data_dir = post_data_dir
        self.max_postdata_threshold = max_postdata_threshold

    def configure(self, options, config):
        """
        Configure the plugin and system, based on selected options
        """
        self.config = config
        if self.post_data_dir is not None:
            self.enabled = True
        else:
            self.enabled = False

    def __save_home(self, test, status, err=None):
        if hasattr(test, 'test'):
            _test = test.test
            sn = _test.__class__.__name__
        elif hasattr(test, 'context'):
            _test = test.context
            sn = _test.__name__
        else:
            # test does not have any PBS Objects, so just return
            return
        if self.__priv_sn != sn:
            self.__save_data_count = 0
            self.__priv_sn = sn
        # Saving home might take time so disable timeout
        # handler set by runner
        tn = getattr(_test, '_testMethodName', 'unknown')
        testlogs = getattr(test, 'captured_logs', '')
        datadir = os.path.join(self.post_data_dir, sn, tn)
        if os.path.exists(datadir):
            _msg = 'Old post analysis data exists at %s' % datadir
            _msg += ', skipping saving data for this test case'
            self.logger.warn(_msg)
            _msg = 'Please remove old directory or'
            _msg += ' provide different directory'
            self.logger.warn(_msg)
            return
        if getattr(test, 'old_sigalrm_handler', None) is not None:
            _h = getattr(test, 'old_sigalrm_handler')
            signal.signal(signal.SIGALRM, _h)
            signal.alarm(0)
        self.logger.log(logging.DEBUG2, 'Saving post analysis data...')
        current_host = socket.gethostname().split('.')[0]
        self.du.mkdir(current_host, path=datadir, mode=0755,
                      parents=True, logerr=False, level=logging.DEBUG2)
        if err is not None:
            if isclass(err[0]) and issubclass(err[0], SkipTest):
                status = 'SKIP'
                status_data = 'Reason = %s' % (err[1])
            else:
                if isclass(err[0]) and issubclass(err[0], TimeOut):
                    status = 'TIMEDOUT'
                status_data = getattr(test, 'err_in_string', '')
        else:
            status_data = ''
        logfile = os.path.join(datadir, 'logfile_' + status)
        f = open(logfile, 'w+')
        f.write(testlogs + '\n')
        f.write(status_data + '\n')
        f.write('test duration: %s\n' % str(getattr(test, 'duration', '0')))
        if status in ('PASS', 'SKIP'):
            # Test case passed or skipped, no need to save post analysis data
            f.close()
            return
        if ((self.max_postdata_threshold != 0) and
                (self.__save_data_count >= self.max_postdata_threshold)):
            _msg = 'Total number of saved post analysis data for this'
            _msg += ' testsuite is exceeded max postdata threshold'
            _msg += ' (%d)' % self.max_postdata_threshold
            f.write(_msg + '\n')
            self.logger.error(_msg)
            f.close()
            return
        svr = getattr(_test, 'server', None)
        if svr is not None:
            svr_host = svr.hostname
        else:
            _msg = 'Could not find Server Object in given test object'
            _msg += ', skipping saving post analysis data'
            f.write(_msg + '\n')
            self.logger.warning(_msg)
            f.close()
            return
        pbs_diag = os.path.join(svr.pbs_conf['PBS_EXEC'],
                                'unsupported', 'pbs_diag')
        cur_user = self.du.get_current_user()
        cmd = [pbs_diag, '-f', '-d', '2']
        cmd += ['-u', cur_user]
        cmd += ['-o', pwd.getpwnam(cur_user).pw_dir]
        if len(svr.jobs) > 0:
            cmd += ['-j', ','.join(svr.jobs.keys())]
        ret = self.du.run_cmd(svr_host, cmd, sudo=True, level=logging.DEBUG2)
        if ret['rc'] != 0:
            _msg = 'Failed to get diag information for '
            _msg += 'on %s:' % svr_host
            _msg += '\n\n' + '\n'.join(ret['err']) + '\n\n'
            f.write(_msg + '\n')
            self.logger.error(_msg)
            f.close()
            return
        else:
            diag_re = r"(?P<path>\/.*\/pbs_diag_[\d]+_[\d]+\.tar\.gz).*"
            m = re.search(diag_re, '\n'.join(ret['out']))
            if m is not None:
                diag_out = m.group('path')
            else:
                _msg = 'Failed to find generated diag path in below output:'
                _msg += '\n\n' + '-' * 80 + '\n'
                _msg += '\n'.join(ret['out']) + '\n'
                _msg += '-' * 80 + '\n\n'
                f.write(_msg)
                self.logger.error(_msg)
                f.close()
                return
        diag_out_dest = os.path.join(datadir, os.path.basename(diag_out))
        if not self.du.is_localhost(svr_host):
            diag_out_r = svr_host + ':' + diag_out
        else:
            diag_out_r = diag_out
        ret = self.du.run_copy(current_host, diag_out_r, diag_out_dest,
                               sudo=True, level=logging.DEBUG2)
        if ret['rc'] != 0:
            _msg = 'Failed to copy generated diag from'
            _msg += ' %s to %s' % (diag_out_r, diag_out_dest)
            f.write(_msg + '\n')
            self.logger.error(_msg)
            f.close()
            return
        else:
            self.du.rm(svr_host, path=diag_out, sudo=True, force=True,
                       level=logging.DEBUG2)
        cores = []
        dir_list = ['server_priv', 'sched_priv', 'mom_priv']
        for d in dir_list:
            path = os.path.join(svr.pbs_conf['PBS_HOME'], d)
            files = self.du.listdir(hostname=svr_host, path=path, sudo=True,
                                    level=logging.DEBUG2)
            for _f in files:
                if os.path.basename(_f).startswith('core'):
                    cores.append(_f)
        cores = list(set(cores))
        if len(cores) > 0:
            cmd = ['gunzip', diag_out_dest]
            ret = self.du.run_cmd(current_host, cmd, sudo=True,
                                  level=logging.DEBUG2)
            if ret['rc'] != 0:
                _msg = 'Failed unzip generated diag at %s:' % diag_out_dest
                _msg += '\n\n' + '\n'.join(ret['err']) + '\n\n'
                f.write(_msg + '\n')
                self.logger.error(_msg)
                f.close()
                return
            diag_out_dest = diag_out_dest.rstrip('.gz')
            cmd = ['tar', '-xf', diag_out_dest, '-C', datadir]
            ret = self.du.run_cmd(current_host, cmd, sudo=True,
                                  level=logging.DEBUG2)
            if ret['rc'] != 0:
                _msg = 'Failed extract generated diag %s' % diag_out_dest
                _msg += ' to %s:' % datadir
                _msg += '\n\n' + '\n'.join(ret['err']) + '\n\n'
                f.write(_msg + '\n')
                self.logger.error(_msg)
                f.close()
                return
            self.du.rm(hostname=current_host, path=diag_out_dest,
                       force=True, sudo=True, level=logging.DEBUG2)
            diag_out_dest = diag_out_dest.rstrip('.tar')
            for c in cores:
                cmd = [pbs_diag, '-g', c]
                ret = self.du.run_cmd(svr_host, cmd, sudo=True,
                                      level=logging.DEBUG2)
                if ret['rc'] != 0:
                    _msg = 'Failed to get core file information for '
                    _msg += '%s on %s:' % (c, svr_host)
                    _msg += '\n\n' + '\n'.join(ret['err']) + '\n\n'
                    f.write(_msg + '\n')
                    self.logger.error(_msg)
                else:
                    of = os.path.join(diag_out_dest,
                                      os.path.basename(c) + '.out')
                    _f = open(of, 'w+')
                    _f.write('\n'.join(ret['out']) + '\n')
                    _f.close()
                    self.du.rm(hostname=svr_host, path=c, force=True,
                               sudo=True, level=logging.DEBUG2)
            cmd = ['tar', '-cf', diag_out_dest + '.tar']
            cmd += [os.path.basename(diag_out_dest)]
            ret = self.du.run_cmd(current_host, cmd, sudo=True, cwd=datadir,
                                  level=logging.DEBUG2)
            if ret['rc'] != 0:
                _msg = 'Failed generate tarball of diag directory'
                _msg += ' %s' % diag_out_dest
                _msg += ' after adding core(s) information in it:'
                _msg += '\n\n' + '\n'.join(ret['err']) + '\n\n'
                f.write(_msg + '\n')
                self.logger.error(_msg)
                f.close()
                return
            cmd = ['gzip', diag_out_dest + '.tar']
            ret = self.du.run_cmd(current_host, cmd, sudo=True,
                                  level=logging.DEBUG2)
            if ret['rc'] != 0:
                _msg = 'Failed compress tarball of diag %s' % diag_out_dest
                _msg += '.tar after adding core(s) information in it:'
                _msg += '\n\n' + '\n'.join(ret['err']) + '\n\n'
                f.write(_msg + '\n')
                self.logger.error(_msg)
                f.close()
                return
            self.du.rm(current_host, diag_out_dest, sudo=True,
                       recursive=True, force=True, level=logging.DEBUG2)
        else:
            diag_out_dest = diag_out_dest.rstrip('.tar.gz')
        dest = os.path.join(datadir,
                            'PBS_' + current_host.split('.')[0] + '.tar.gz')
        ret = self.du.run_copy(current_host, diag_out_dest + '.tar.gz',
                               dest, sudo=True, level=logging.DEBUG2)
        if ret['rc'] != 0:
            _msg = 'Failed rename tarball of diag from %s' % diag_out_dest
            _msg += '.tar.gz to %s:' % dest
            _msg += '\n\n' + '\n'.join(ret['err']) + '\n\n'
            f.write(_msg + '\n')
            self.logger.error(_msg)
            f.close()
            return
        self.du.rm(current_host, path=diag_out_dest + '.tar.gz',
                   force=True, sudo=True, level=logging.DEBUG2)
        f.close()
        self.__save_data_count += 1
        _msg = 'Successfully saved post analysis data'
        self.logger.log(logging.DEBUG2, _msg)

    def addError(self, test, err):
        self.__save_home(test, 'ERROR', err)

    def addFailure(self, test, err):
        self.__save_home(test, 'FAIL', err)

    def addSuccess(self, test):
        self.__save_home(test, 'PASS')

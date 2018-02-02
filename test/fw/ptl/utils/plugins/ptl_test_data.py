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
        self.logger.info('Saving post analysis data...')
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
        additional_hosts = []
        moms = getattr(_test, 'moms', None)
        if moms is not None:
            additional_hosts.extend(moms.host_keys())
        comms = getattr(_test, 'comms', None)
        if comms is not None:
            additional_hosts.extend(comms.host_keys())
        servers = getattr(_test, 'servers', None)
        if servers is not None:
            additional_hosts.extend(servers.host_keys())
        additional_hosts = ",".join(list(set(additional_hosts)))
        cmd = [os.path.join(svr.pbs_conf['PBS_EXEC'], 'sbin', 'pbs_snapshot')]
        cmd += ['--additional-hosts', additional_hosts]
        cmd += ['-o', datadir]
        cmd += ['-H', current_host]
        ret = self.du.run_cmd(current_host, cmd, sudo=True,
                              level=logging.DEBUG2, logerr=False)
        if ret['rc'] != 0:
            _msg = ['Failed to save post analysis data, see below for reason:']
            _msg += ['=' * 80]
            _msg += ['Cmd: ' + ' '.join(cmd)]
            _msg += ['=' * 80]
            _msg += ['Output:']
            _msg.extend(ret['out'])
            _msg += ['=' * 80]
            _msg += ['Error:']
            _msg.extend(ret['err'])
            _msg += ['=' * 80]
            f.write('\n'.join(_msg) + '\n')
            self.logger.error('\n'.join(_msg))
            f.close()
            return
        f.close()
        self.__save_data_count += 1
        self.logger.info('Successfully saved post analysis data')

    def addError(self, test, err):
        self.__save_home(test, 'ERROR', err)

    def addFailure(self, test, err):
        self.__save_home(test, 'FAIL', err)

    def addSuccess(self, test):
        self.__save_home(test, 'PASS')

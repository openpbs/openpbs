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


import resource

from tests.functional import *


class TestDaemonServiceUser(TestFunctional):

    """
    Test suite to test running schedulers as a non-root user
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.orig_pbs_conf = self.du.parse_pbs_config(self.server.shortname)

    def tearDown(self):
        self.du.set_pbs_config(self.server.shortname,
                               confs=self.orig_pbs_conf,
                               append=False)
        TestFunctional.tearDown(self)

    def common_test(self, binary, runas, scheduser, msg):
        """
        Test if running `binary` as `runas` with
        PBS_DAEMON_SERVICE_USER set as `scheduser`
        Check to see `msg` is in stderr
        """
        if scheduser:
            self.du.set_pbs_config(
                self.server.hostname,
                confs={'PBS_DAEMON_SERVICE_USER': str(scheduser)}
            )
        else:
            self.du.unset_pbs_config(
                self.server.hostname,
                confs='PBS_DAEMON_SERVICE_USER'
            )
        pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        binpath = os.path.join(pbs_conf['PBS_EXEC'], 'sbin', binary)
        ret = self.du.run_cmd(self.server.shortname,
                              cmd=[binpath], runas=runas)
        self.assertEquals(ret['rc'], 1)
        self.assertIn(msg, '\n'.join(ret['err']))

    def test_sched_runas_root(self):
        """
        Test if running sched as root with
        PBS_DAEMON_SERVICE_USER set as another user
        """
        self.common_test('pbs_sched', ROOT_USER, TEST_USER,
                         'Must be run by PBS_DAEMON_SERVICE_USER')

    def test_pbsfs_runas_root(self):
        """
        Test if running pbsfs as root with
        PBS_DAEMON_SERVICE_USER set as another user
        """
        self.common_test('pbsfs', ROOT_USER, TEST_USER,
                         'Must be run by PBS_DAEMON_SERVICE_USER')

    def test_sched_runas_nonroot(self):
        """
        Test if running sched as nonroot with
        PBS_DAEMON_SERVICE_USER set as another user
        """
        self.common_test('pbs_sched', TEST_USER, TEST_USER1,
                         'Must be run by PBS_DAEMON_SERVICE_USER')

    def test_pbsfs_runas_nonroot(self):
        """
        Test if running pbsfs as root with
        PBS_DAEMON_SERVICE_USER set as another user
        """
        self.common_test('pbsfs', TEST_USER, TEST_USER1,
                         'Must be run by PBS_DAEMON_SERVICE_USER')

    def test_sched_runas_nonroot_notset(self):
        """
        Test if running sched as nonroot with
        PBS_DAEMON_SERVICE_USER not set
        """
        self.common_test('pbs_sched', TEST_USER, None,
                         'Must be run by PBS_DAEMON_SERVICE_USER if '
                         'set or root if not set')

    def test_pbsfs_runas_nonroot_notset(self):
        """
        Test if running pbsfs as nonroot with
        PBS_DAEMON_SERVICE_USER not set
        """
        self.common_test('pbsfs', TEST_USER, None,
                         'Must be run by PBS_DAEMON_SERVICE_USER if '
                         'set or root if not set')

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

from tests.functional import *
import socket


class Test_systemd(TestFunctional):
    """
    Test whether you are able to control pbs using systemd
    """

    def setUp(self):
        TestFunctional.setUp(self)
        # Skip test if systemctl command is not found.
        is_systemctl = self.du.which(exe='systemctl')
        if is_systemctl == 'systemctl':
            self.skipTest("Systemctl command not found")

    def shutdown_all(self):
        if self.server.isUp():
            self.server.stop()
        if self.scheduler.isUp():
            self.scheduler.stop()
        if self.comm.isUp():
            self.comm.stop()
        if self.mom.isUp():
            self.mom.stop()

    def start_using_systemd(self):
        cmd = "systemctl start pbs"
        self.du.run_cmd(self.hostname, cmd, True)
        if ('1' == self.server.pbs_conf['PBS_START_SERVER'] and
                not self.server.isUp()):
            return False
        if ('1' == self.server.pbs_conf['PBS_START_SCHED'] and
                not self.scheduler.isUp()):
            return False
        if ('1' == self.server.pbs_conf['PBS_START_COMM'] and
                not self.comm.isUp()):
            return False
        if ('1' == self.server.pbs_conf['PBS_START_MOM'] and
                not self.mom.isUp()):
            return False
        return True

    def stop_using_systemd(self):
        cmd = "systemctl stop pbs"
        self.du.run_cmd(self.hostname, cmd, True)
        if ('1' == self.server.pbs_conf['PBS_START_SERVER'] and
                self.server.isUp()):
            return False
        if ('1' == self.server.pbs_conf['PBS_START_SCHED'] and
                self.scheduler.isUp()):
            return False
        if '1' == self.server.pbs_conf['PBS_START_COMM'] and self.comm.isUp():
            return False
        if '1' == self.server.pbs_conf['PBS_START_MOM'] and self.mom.isUp():
            return False
        return True

    def test_systemd(self):
        """
        Test whether you are able to control pbs using systemd
        """
        self.hostname = socket.gethostname()
        cmd = "systemctl daemon-reload"
        out = self.du.run_cmd(self.hostname, cmd, True)
        self.shutdown_all()
        rv = self.start_using_systemd()
        self.assertTrue(rv)
        rv = self.stop_using_systemd()
        self.assertTrue(rv)
        rv = self.start_using_systemd()

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
        ret = self.du.run_cmd(self.server.hostname, "systemctl is-active dbus")
        if ret['rc'] == 1:
            self.skipTest("Systemd not functional")

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
                self.server.isUp(max_attempts=10)):
            return False
        if ('1' == self.server.pbs_conf['PBS_START_SCHED'] and
                self.scheduler.isUp(max_attempts=10)):
            return False
        if ('1' == self.server.pbs_conf['PBS_START_COMM'] and
                self.comm.isUp(max_attempts=10)):
            return False
        if ('1' == self.server.pbs_conf['PBS_START_MOM'] and
                self.mom.isUp(max_attempts=10)):
            return False
        return True

    @skipOnShasta
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

    @skipOnShasta
    def test_missing_daemon(self):
        """
        Test whether missing daemons starts without re-starting other daemons
        """
        self.hostname = self.server.hostname
        self.shutdown_all()
        rv = self.start_using_systemd()
        self.assertTrue(rv)
        cmd = "systemctl reload pbs"
        # Mom
        self.mom.signal("-KILL")
        if self.mom.isUp(max_attempts=10):
            self.fail("MoM is still running")
        self.du.run_cmd(self.hostname, cmd, True)
        if self.mom.isUp(max_attempts=10):
            self.logger.info("MoM started and running")
        else:
            self.fail("MoM not started")
        # Sched
        self.scheduler.signal("-KILL")
        if self.scheduler.isUp(max_attempts=10):
            self.fail("Sched is still running")
        self.du.run_cmd(self.hostname, cmd, True)
        if self.scheduler.isUp(max_attempts=10):
            self.logger.info("Sched started and running")
        else:
            self.fail("Sched not started")
        # Comm
        self.comm.signal("-KILL")
        if self.comm.isUp(max_attempts=10):
            self.fail("Comm is still running")
        self.du.run_cmd(self.hostname, cmd, True)
        if self.comm.isUp(max_attempts=10):
            self.logger.info("Comm started and running")
        else:
            self.fail("Comm not started")
        # Server
        self.server.signal("-KILL")
        if self.server.isUp(max_attempts=10):
            self.fail("Server is still running")
        self.du.run_cmd(self.hostname, cmd, True)
        if self.server.isUp(max_attempts=10):
            self.logger.info("Server started and running")
        else:
            self.fail("Server not started")

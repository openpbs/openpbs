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


import array
import fcntl
import socket
import struct
import sys

from tests.functional import *


class TestVerifyLogOutput(TestFunctional):
    """
    Test that hostname and interface information
    is added to all logs at log open
    """

    def setUp(self):
        TestFunctional.setUp(self)

    def all_interfaces(self):
        """
        Miscellaneous function to return all interface names
        that should also be added to logs
        """
        is_64bits = sys.maxsize > 2**32
        struct_size = 40 if is_64bits else 32
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        max_possible = 8
        while True:
            bytes = max_possible * struct_size
            names = array.array('B', b'\0' * bytes)
            outbytes = struct.unpack('iL', fcntl.ioctl(
                s.fileno(),
                0x8912,
                struct.pack('iL', bytes, names.buffer_info()[0])
            ))[0]
            if outbytes == bytes:
                max_possible *= 2
            else:
                break
        namestr = names.tostring()
        for i in range(0, outbytes, struct_size):
            yield namestr[i:i + 16].split(b'\0', 1)[0].decode()

    def test_hostname_add(self):
        """
        Test for hostname presence in log files
        """
        log_val = socket.gethostname()
        momname = self.mom.shortname
        self.scheduler.log_match(
            log_val,
            regexp=False,
            starttime=self.server.ctime,
            max_attempts=5,
            interval=2)
        self.server.log_match(
            log_val,
            regexp=False,
            starttime=self.server.ctime,
            max_attempts=5,
            interval=2)
        self.mom.log_match(
            momname,
            regexp=False,
            starttime=self.server.ctime,
            max_attempts=5,
            interval=2)

    def test_if_info_add(self):
        """
        Test for interface info presence in log files
        """
        interfaceGenerator = self.all_interfaces()
        for ifname in interfaceGenerator:
            name = "[(" + ifname + ")]"
            log_val = "[( interface: )]" + name
            # Workaround for PTL regex to match
            # entire word once using () inside []
            self.scheduler.log_match(
                log_val,
                regexp=True,
                starttime=self.server.ctime,
                max_attempts=5,
                interval=2)
            self.server.log_match(
                log_val,
                regexp=True,
                starttime=self.server.ctime,
                max_attempts=5,
                interval=2)
            self.mom.log_match(
                log_val,
                regexp=True,
                starttime=self.server.ctime,
                max_attempts=5,
                interval=2)

    def test_auto_sched_cycle_trigger(self):
        """
        Test case to verify that scheduling cycle is triggered automatically
        without any delay  after restart of PBS Services.
        """
        started_time = time.time()
        self.logger.info('Restarting PBS Services')
        PBSInitServices().restart()

        if self.server.isUp() and self.scheduler.isUp():
            self.scheduler.log_match("Req;;Starting Scheduling Cycle",
                                     starttime=started_time)
            self.scheduler.log_match("Req;;Leaving Scheduling Cycle",
                                     starttime=started_time)

    def test_supported_auth_method_msgs(self):
        """
        Test to verify PBS_SUPPORTED_AUTH_METHODS is logged in server
        and comm daemon logs after start or restart
        """
        attr_name = 'PBS_SUPPORTED_AUTH_METHODS'
        started_time = time.time()
        # check the logs after restarting the server and comm daemon
        self.server.restart()
        self.comm.restart()
        resvport_msg = 'Supported authentication method: ' + 'resvport'
        if self.server.isUp() and self.comm.isUp():
            self.server.log_match(resvport_msg, starttime=started_time)
            self.comm.log_match(resvport_msg, starttime=started_time)

        # Added an attribute PBS_SUPPORTED_AUTH_METHODS in pbs.conf file
        conf_attr = {'PBS_SUPPORTED_AUTH_METHODS': 'munge,resvport'}
        self.du.set_pbs_config(confs=conf_attr)
        started_time = time.time()
        # check the logs after restarting the server and comm daemon
        self.server.restart()
        self.comm.restart()
        munge_msg = 'Supported authentication method: ' + 'munge'
        if self.server.isUp() and self.comm.isUp():
            self.server.log_match(munge_msg, starttime=started_time)
            self.comm.log_match(munge_msg, starttime=started_time)
            self.server.log_match(resvport_msg, starttime=started_time)
            self.comm.log_match(resvport_msg, starttime=started_time)

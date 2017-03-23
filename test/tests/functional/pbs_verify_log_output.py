# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.


from tests.functional import *

import sys
import socket
import fcntl
import struct
import array


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
            names = array.array('B', '\0' * bytes)
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
            yield namestr[i:i+16].split('\0', 1)[0]

    def test_hostname_add(self):
        """
        Test for hostname presence in log files
        """
        log_val = socket.gethostname()
        rv = self.scheduler.log_match(
            log_val,
            regexp=False,
            starttime=self.server.ctime,
            max_attempts=5,
            interval=2)
        self.assertTrue(rv)
        rv = self.server.log_match(
            log_val,
            regexp=False,
            starttime=self.server.ctime,
            max_attempts=5,
            interval=2)
        self.assertTrue(rv)
        rv = self.mom.log_match(
            log_val,
            regexp=False,
            starttime=self.server.ctime,
            max_attempts=5,
            interval=2)
        self.assertTrue(rv)

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
            rv = self.scheduler.log_match(
                log_val,
                regexp=True,
                starttime=self.server.ctime,
                max_attempts=5,
                interval=2)
            self.assertTrue(rv)
            rv = self.server.log_match(
                log_val,
                regexp=True,
                starttime=self.server.ctime,
                max_attempts=5,
                interval=2)
            self.assertTrue(rv)
            rv = self.mom.log_match(
                log_val,
                regexp=True,
                starttime=self.server.ctime,
                max_attempts=5,
                interval=2)
            self.assertTrue(rv)

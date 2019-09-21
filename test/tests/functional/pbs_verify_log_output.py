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
            log_val,
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
            try:
                self.scheduler.log_match("Req;;Starting Scheduling Cycle",
                                         max_attempts=10,
                                         starttime=started_time)
                self.scheduler.log_match("Req;;Leaving Scheduling Cycle",
                                         max_attempts=10,
                                         starttime=started_time)
            except PtlLogMatchError:
                self.assertFalse(True)

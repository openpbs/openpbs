# coding: utf-8
#

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

try:
    import os
    import time
    import sys
    from operator import itemgetter
    import socket
    from fcntl import flock, LOCK_EX, LOCK_UN

    def __get_uptime():
        """
        This function will return system uptime in epoch pattern
        it will find system uptime either reading to '/proc/uptime' file is exists
        otherwise by using 'uptime' command
        """
        _boot_time = 0
        if os.path.exists('/proc/uptime'):
            # '/proc/uptime' file exists, get system uptime from it
            _uptime = open('/proc/uptime', 'r')
            _boot_time = int(
                time.time() - float(_uptime.readline().split()[0]))
            _uptime.close()
        else:
            # '/proc/uptime' file not exists, get system uptime from 'uptime' command
            # here uptime format will be as follow:
            # <current time> <uptime>, <number of user logged into system>, <load average>
            # Example: 11:14pm  up 150 days  5:39,  5 users,  load average: 0.07, 0.25, 0.22
            # from above format the <uptime> will be one of the following format:
            #
            # 1. up MM min,
            # 	Example 1: up 1 min,
            # 	Example 2: up 12 min,
            #
            # 2. up HH:MM,
            # 	Example 2: up 12:45,
            #
            # 3. up <number of days> day<(s)>,
            # 	Example 3.1: up 23 day(s),
            # 	Example 3.2: up 23 days
            #
            # 4. up <number of days> day<(s)> HH:MM,
            # 	Example 4.1: up 23 day(s) 12:45,
            # 	Example 4.2: up 23 days 12:45,
            # 	Example 4.3: up 23 days, 12:45,

            _uptime = os.popen('uptime').readline()
            _days = _hours = _min = 0
            if 'day' in _uptime:
                (_days, _hm) = itemgetter(2, 4)(_uptime.split())
            else:
                _hm = itemgetter(2)(_uptime.split())
            if ':' in _hm:
                (_hours, _min) = _hm.split(':')
                _min = _min.strip(',')
            else:
                _min = _hm
            _boot_time = int(time.time()) - \
                (int(_days) * 86400 + int(
                    _hours) * 3600 + int(_min) * 60)
        return _boot_time

    boot_time = __get_uptime()
    boot_check_file = sys.argv[1]
    prev_pbs_start_time = int(time.time())
    hostname = socket.gethostname()
    new_lines = ['###################################',
                 '#      DO NOT EDIT THIS FILE      #',
                 '#   THIS FILE IS MANAGED BY PBS   #',
                 '###################################',
                 hostname + '==' + str(prev_pbs_start_time)]
    if os.path.exists(boot_check_file):
        f = open(boot_check_file, 'a+')
    else:
        f = open(boot_check_file, 'w+')
    flock(f.fileno(), LOCK_EX)
except Exception:
    sys.exit(255)
try:
    f.seek(0)
    lines = f.readlines()
    for (line_no, line_content) in enumerate(lines):
        if line_content[0] != '#' and line_content.strip() != '':
            (host, start_time) = line_content.split('==')
            if host == hostname:
                prev_pbs_start_time = int(start_time)
            else:
                new_lines.append(line_content)
    f.seek(0)
    f.truncate()
    f.writelines('\n'.join(new_lines))
    flock(f.fileno(), LOCK_UN)
except Exception:
    flock(f.fileno(), LOCK_UN)
    f.close()
    sys.exit(255)
f.close()
os.chmod(boot_check_file, 0o644)
# if system being booted then exit with 0 otherwise exit with 1
if boot_time >= prev_pbs_start_time:
    sys.exit(0)
else:
    sys.exit(1)

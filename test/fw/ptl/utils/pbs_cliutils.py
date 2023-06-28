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


import logging
import os
import re


class CliUtils(object):
    """
    Command line interface utility
    """

    @classmethod
    def get_logging_level(cls, level):
        """
        Get the logging levels

        :param level: Name of the logging level
        :type level: str
         """
        logging.DEBUG2 = logging.DEBUG - 1
        logging.INFOCLI = logging.INFO - 1
        logging.INFOCLI2 = logging.INFOCLI - 1

        log_lvl = None
        level = str(level).upper()
        if level == 'INFO':
            log_lvl = logging.INFO
        elif level == 'INFOCLI':
            log_lvl = logging.INFOCLI
        elif level == 'INFOCLI2':
            log_lvl = logging.INFOCLI2
        elif level == 'DEBUG':
            log_lvl = logging.DEBUG
        elif level == 'DEBUG2':
            log_lvl = logging.DEBUG2
        elif level == 'WARNING':
            log_lvl = logging.WARNING
        elif level == 'ERROR':
            log_lvl = logging.ERROR
        elif level == 'FATAL':
            log_lvl = logging.FATAL

        return log_lvl

    @staticmethod
    def check_bin(bin_name):
        """
        Check for command exist

        :param bin_name: Command to be checked
        :type bin_name: str
        :returns: True if command exist else return False
        """
        ec = os.system("/usr/bin/which " + bin_name + " > /dev/null")
        if ec == 0:
            return True
        return False

    @staticmethod
    def __json__(data):
        try:
            import json
            return json.dumps(data, sort_keys=True, indent=4)
        except Exception:
            # first escape any existing double quotes
            _pre = str(data).replace('"', '\\"')
            # only then, replace the single quotes with double quotes
            return _pre.replace('\'', '"')

    @staticmethod
    def expand_abs_path(path):
        """
        Expand the path to absolute path
        """
        if path.startswith('~'):
            return os.path.expanduser(path)
        return os.path.abspath(path)

    @staticmethod
    def priv_ports_info(hostname=None):
        """
        Return a list of privileged ports in use on a given host

        :param hostname: The host on which to query privilege ports
                         usage. Defaults to the local host
        :type hostname: str or None
        """
        from ptl.utils.pbs_dshutils import DshUtils

        netstat_tag = re.compile(r"tcp[\s]+[\d]+[\s]+[\d]+[\s]+"
                                 r"(?P<srchost>[\w\*\.]+):(?P<srcport>[\d]+)"
                                 r"[\s]+(?P<desthost>[\.\w\*:]+):"
                                 r"(?P<destport>[\d]+)"
                                 r"[\s]+(?P<state>[\w]+).*")
        du = DshUtils()
        ret = du.run_cmd(hostname, ['netstat', '-at', '--numeric-ports'])
        if ret['rc'] != 0:
            return False

        msg = []
        lines = ret['out']
        resv_ports = {}
        source_hosts = []
        for line in lines:
            m = netstat_tag.match(line)
            if m:
                srcport = int(m.group('srcport'))
                srchost = m.group('srchost')
                destport = int(m.group('destport'))
                desthost = m.group('desthost')
                if srcport < 1024:
                    if srchost not in source_hosts:
                        source_hosts.append(srchost)
                    msg.append(line)
                    if srchost not in resv_ports:
                        resv_ports[srchost] = [srcport]
                    elif srcport not in resv_ports[srchost]:
                        resv_ports[srchost].append(srcport)
                if destport < 1024:
                    msg.append(line)
                    if desthost not in resv_ports:
                        resv_ports[desthost] = [destport]
                    elif destport not in resv_ports[desthost]:
                        resv_ports[desthost].append(destport)

        if len(resv_ports) > 0:
            msg.append('\nPrivilege ports in use: ')
            for k, v in resv_ports.items():
                msg.append('\t' + k + ': ' +
                           str(",".join([str(l) for l in v])))
            for sh in source_hosts:
                msg.append('\nTotal on ' + sh + ': ' +
                           str(len(resv_ports[sh])))
        else:
            msg.append('No privileged ports currently allocated')

        return msg

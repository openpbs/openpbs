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


import copy
import datetime
import logging
import os
import re
import socket
import string
import sys
import time
from ptl.lib.ptl_service import PBSService, PbsServiceControl


class Comm(PBSService):

    """
    PBS ``Comm`` configuration and control
    """

    """
    :param name: The hostname of the Comm. Defaults to current hostname.
    :type name: str
    :param attrs: Dictionary of attributes to set, these will override
                  defaults.
    :type attrs: dictionary
    :param pbsconf_file: path to config file to parse for PBS_HOME,
                         PBS_EXEC, etc
    :type pbsconf_file: str or None
    :param snapmap: A dictionary of PBS objects (node,server,etc) to
                    mapped files from PBS snap directory
    :type snapmap: dictionary
    :param snap: path to PBS snap directory (This will override snapmap)
    :type snap: str or None
    :param server: A PBS server instance to which this Comm is associated
    :type server: str
    :param db_access: set to either file containing credentials to DB access or
                      dictionary containing {'dbname':...,'user':...,
                      'port':...}
    :type db_access: str or dictionary
        """
    dflt_attributes = {}

    def __init__(self, server, name=None, attrs={}, pbsconf_file=None,
                 snapmap={}, snap=None, db_access=None):
        self.server = server
        if snap is None and self.server.snap is not None:
            snap = self.server.snap
        if (len(snapmap) == 0) and (len(self.server.snapmap) != 0):
            snapmap = self.server.snapmap
        super().__init__(name, attrs, self.dflt_attributes,
                         pbsconf_file, snapmap, snap)
        _m = ['Comm ', self.shortname]
        if pbsconf_file is not None:
            _m += ['@', pbsconf_file]
        _m += [': ']
        self.logprefix = "".join(_m)
        self.conf_to_cmd_map = {
            'PBS_COMM_ROUTERS': '-r',
            'PBS_COMM_THREADS': '-t'
        }
        self.pi = PbsServiceControl(hostname=self.hostname,
                                    conf=self.pbs_conf_file)

    def start(self, args=None, launcher=None):
        """
        Start the comm

        :param args: Argument required to start the comm
        :type args: str
        :param launcher: Optional utility to invoke the launch of the service
        :type launcher: str or list
        """
        if args is not None or launcher is not None:
            return super()._start(inst=self, args=args,
                                  cmd_map=self.conf_to_cmd_map,
                                  launcher=launcher)
        else:
            try:
                rv = self.pi.start_comm()
                pid = self._validate_pid(self)
                if pid is None:
                    raise PbsServiceError(rv=False, rc=-1,
                                          msg="Could not find PID")
            except PbsServiceControlError as e:
                raise PbsServiceError(rc=e.rc, rv=e.rv, msg=e.msg)
            return rv

    def stop(self, sig=None):
        """
        Stop the comm.

        :param sig: Signal to stop the comm
        :type sig: str
        """
        if sig is not None:
            self.logger.info(self.logprefix + 'stopping Comm on host ' +
                             self.hostname)
            return super(Comm, self)._stop(sig, inst=self)
        else:
            try:
                self.pi.stop_comm()
            except PbsServiceControlError as e:
                raise PbsServiceError(rc=e.rc, rv=e.rv, msg=e.msg)
            return True

    def restart(self):
        """
        Restart the comm.
        """
        if self.isUp():
            if not self.stop():
                return False
        return self.start()

    def log_match(self, msg=None, id=None, n=50, tail=True, allmatch=False,
                  regexp=False, max_attempts=None, interval=None,
                  starttime=None, endtime=None, level=logging.INFO,
                  existence=True):
        """
        Match given ``msg`` in given ``n`` lines of Comm log

        :param msg: log message to match, can be regex also when
                    ``regexp`` is True
        :type msg: str
        :param id: The id of the object to trace. Only used for
                   tracejob
        :type id: str
        :param n: 'ALL' or the number of lines to search through,
                  defaults to 50
        :type n: str or int
        :param tail: If true (default), starts from the end of
                     the file
        :type tail: bool
        :param allmatch: If True all matching lines out of then
                         parsed are returned as a list. Defaults
                         to False
        :type allmatch: bool
        :param regexp: If true msg is a Python regular expression.
                       Defaults to False
        :type regexp: bool
        :param max_attempts: the number of attempts to make to find
                             a matching entry
        :type max_attempts: int
        :param interval: the interval between attempts
        :type interval: int
        :param starttime: If set ignore matches that occur before
                          specified time
        :type starttime: float
        :param endtime: If set ignore matches that occur after
                        specified time
        :type endtime: float
        :param level: The logging level, defaults to INFO
        :type level: int
        :param existence: If True (default), check for existence of
                        given msg, else check for non-existence of
                        given msg.
        :type existence: bool

        :return: (x,y) where x is the matching line
                 number and y the line itself. If allmatch is True,
                 a list of tuples is returned.
        :rtype: tuple
        :raises PtlLogMatchError:
                When ``existence`` is True and given
                ``msg`` is not found in ``n`` line
                Or
                When ``existence`` is False and given
                ``msg`` found in ``n`` line.

        .. note:: The matching line number is relative to the record
                  number, not the absolute line number in the file.
        """
        return self._log_match(self, msg, id, n, tail, allmatch, regexp,
                               max_attempts, interval, starttime, endtime,
                               level=level, existence=existence)

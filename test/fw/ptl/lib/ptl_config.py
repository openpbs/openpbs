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


import copy
import datetime
import logging
import os
import random
import re
import sys
import time

from ptl.utils.pbs_dshutils import DshUtils
from ptl.lib.ptl_object import *


class PtlConfig(object):

    """
    Holds configuration options
    The options can be stored in a file as well as in the OS environment
    variables.When set, the environment variables will override
    definitions in the file.By default, on Unix like systems, the file
    read is ``/etc/ptl.conf``, the environment variable ``PTL_CONF_FILE``
    can be used to set the path to the file to read.

    The format of the file is a series of ``<key> = <value>`` properties.
    A line that starts with a '#' is ignored and can be used for comments

    :param conf: Path to PTL configuration file
    :type conf: str or None
    """
    logger = logging.getLogger(__name__)

    def __init__(self, conf=None):
        self.options = {
            'PTL_SUDO_CMD': 'sudo -H',
            'PTL_RSH_CMD': 'ssh',
            'PTL_CP_CMD': 'scp -p',
            'PTL_MAX_ATTEMPTS': 180,
            'PTL_ATTEMPT_INTERVAL': 0.5,
            'PTL_UPDATE_ATTRIBUTES': True,
        }
        self.handlers = {
            'PTL_SUDO_CMD': DshUtils.set_sudo_cmd,
            'PTL_RSH_CMD': DshUtils.set_rsh_cmd,
            'PTL_CP_CMD': DshUtils.set_copy_cmd,
            'PTL_MAX_ATTEMPTS': PBSObject.set_max_attempts,
            'PTL_ATTEMPT_INTERVAL': PBSObject.set_attempt_interval,
            'PTL_UPDATE_ATTRIBUTES': PBSObject.set_update_attributes
        }
        if conf is None:
            conf = os.environ.get('PTL_CONF_FILE', '/etc/ptl.conf')
        try:
            with open(conf) as f:
                lines = f.readlines()
        except IOError:
            lines = []
        for line in lines:
            line = line.strip()
            if (line.startswith('#') or (line == '')):
                continue
            try:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                self.options[k] = v
            except:
                self.logger.error('Error parsing line ' + line)
        # below two if block are for backword compatibility
        if 'PTL_EXPECT_MAX_ATTEMPTS' in self.options:
            _o = self.options['PTL_EXPECT_MAX_ATTEMPTS']
            _m = self.options['PTL_MAX_ATTEMPTS']
            _e = os.environ.get('PTL_EXPECT_MAX_ATTEMPTS', _m)
            del self.options['PTL_EXPECT_MAX_ATTEMPTS']
            self.options['PTL_MAX_ATTEMPTS'] = max([int(_o), int(_m), int(_e)])
            _msg = 'PTL_EXPECT_MAX_ATTEMPTS is deprecated,'
            _msg += ' use PTL_MAX_ATTEMPTS instead'
            self.logger.warn(_msg)
        if 'PTL_EXPECT_INTERVAL' in self.options:
            _o = self.options['PTL_EXPECT_INTERVAL']
            _m = self.options['PTL_ATTEMPT_INTERVAL']
            _e = os.environ.get('PTL_EXPECT_INTERVAL', _m)
            del self.options['PTL_EXPECT_INTERVAL']
            self.options['PTL_ATTEMPT_INTERVAL'] = \
                max([int(_o), int(_m), int(_e)])
            _msg = 'PTL_EXPECT_INTERVAL is deprecated,'
            _msg += ' use PTL_ATTEMPT_INTERVAL instead'
            self.logger.warn(_msg)
        for k, v in self.options.items():
            if k in os.environ:
                v = os.environ[k]
            else:
                os.environ[k] = str(v)
            if k in self.handlers:
                self.handlers[k](v)

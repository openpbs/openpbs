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
import logging
import os
import pwd
import re
import sys
import time
from collections import OrderedDict

from ptl.lib.pbs_testlib import *
from ptl.lib.ptl_batchutils import *


class PBSObject(object):

    """
    Generic PBS Object encapsulating attributes and defaults

    The ptl_conf dictionary holds general configuration for the
    framework's operations, specifically, one can control:

    mode: set to ``PTL_CLI`` to operate in ``CLI`` mode or
    ``PTL_API`` to operate in ``API`` mode

    max_attempts: the default maximum number of attempts
    to be used by different methods like expect, log_match.
    Defaults to 60

    attempt_interval: the default time interval (in seconds)
    between each requests. Defaults to 0.5

    update_attributes: the default on whether Object attributes
    should be updated using a list of dictionaries. Defaults
    to True

    :param name: The name associated to the object
    :type name: str
    :param attrs: Dictionary of attributes to set on object
    :type attrs: Dictionary
    :param defaults: Dictionary of default attributes. Setting
                     this will override any other object's default
    :type defaults: Dictionary
    """

    logger = logging.getLogger(__name__)
    utils = BatchUtils()
    platform = sys.platform

    ptl_conf = {
        'mode': PTL_API,
        'max_attempts': 60,
        'attempt_interval': 0.5,
        'update_attributes': True,
    }

    def __init__(self, name, attrs={}, defaults={}):
        self.attributes = OrderedDict()
        self.name = name
        self.dflt_attributes = defaults
        self.attropl = None
        self.custom_attrs = OrderedDict()
        self.ctime = time.time()

        self.set_attributes(attrs)

    @classmethod
    def set_update_attributes(cls, val):
        """
        Set update attributes
        """
        cls.logger.info('setting update attributes ' + str(val))
        if val or (val.isdigit() and int(val) == 1) or val[0] in ('t', 'T'):
            val = True
        else:
            val = False
        cls.ptl_conf['update_attributes'] = val

    @classmethod
    def set_max_attempts(cls, val):
        """
        Set max attempts
        """
        cls.logger.info('setting max attempts ' + str(val))
        cls.ptl_conf['max_attempts'] = int(val)

    @classmethod
    def set_attempt_interval(cls, val):
        """
        Set attempt interval
        """
        cls.logger.info('setting attempt interval ' + str(val))
        cls.ptl_conf['attempt_interval'] = float(val)

    def set_attributes(self, a={}):
        """
        set attributes and custom attributes on this object.
        custom attributes are used when converting attributes
        to CLI

        :param a: Attribute dictionary
        :type a: Dictionary
        """
        if isinstance(a, list):
            a = OrderedDict(a)

        self.attributes = OrderedDict(list(self.dflt_attributes.items()) +
                                      list(self.attributes.items()) +
                                      list(a.items()))

        self.custom_attrs = OrderedDict(list(self.custom_attrs.items()) +
                                        list(a.items()))

    def unset_attributes(self, attrl=[]):
        """
        Unset attributes from object's attributes and custom
        attributes

        :param attrl: Attribute list
        :type attrl: List
        """
        for attr in attrl:
            if attr in self.attributes:
                del self.attributes[attr]
            if attr in self.custom_attrs:
                del self.custom_attrs[attr]

    def __str__(self):
        """
        Return a string representation of this PBSObject
        """
        if self.name is None:
            return ""

        s = []
        if isinstance(self, Job):
            s += ["Job Id: " + self.name + "\n"]
        elif isinstance(self, Queue):
            s += ["Queue: " + self.name + "\n"]
        elif isinstance(self, Server):
            s += ["Server: " + self.hostname + "\n"]
        elif isinstance(self, Reservation):
            s += ["Name: " + "\n"]
        else:
            s += [self.name + "\n"]
        for k, v in self.attributes.items():
            s += ["    " + k + " = " + str(v) + "\n"]
        return "".join(s)

    def __repr__(self):
        return str(self.attributes)

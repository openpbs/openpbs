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
import pwd
import re
import sys
import time

from ptl.utils.pbs_testusers import (ROOT_USER, TEST_USER, PbsUser,
                                     DAEMON_SERVICE_USER)
from ptl.lib.pbs_testlib import *


class Resource(PBSObject):

    """
    PBS resource referenced by name, type and flag

    :param name: Resource name
    :type name: str or None
    :param type: Type of resource
    """

    def __init__(self, name=None, type=None, flag=None):
        PBSObject.__init__(self, name)
        self.set_name(name)
        self.set_type(type)
        self.set_flag(flag)

    def __del__(self):
        del self.__dict__

    def set_name(self, name):
        """
        Set the resource name
        """
        self.name = name
        self.attributes['id'] = name

    def set_type(self, type):
        """
        Set the resource type
        """
        self.type = type
        self.attributes['type'] = type

    def set_flag(self, flag):
        """
        Set the flag
        """
        self.flag = flag
        self.attributes['flag'] = flag

    def __str__(self):
        s = [self.attributes['id']]
        if 'type' in self.attributes:
            s.append('type=' + self.attributes['type'])
        if 'flag' in self.attributes:
            s.append('flag=' + self.attributes['flag'])
        return " ".join(s)


class Hook(PBSObject):

    """
    PBS hook objects. Holds attributes information and pointer
    to server

    :param name: Hook name
    :type name: str or None
    :param attrs: Hook attributes
    :type attrs: Dictionary
    :param server: Pointer to server
    """

    dflt_attributes = {}

    def __init__(self, name=None, attrs={}, server=None):
        PBSObject.__init__(self, name, attrs, self.dflt_attributes)
        self.server = server


class ResourceResv(PBSObject):

    """
    Generic PBS resource reservation, i.e., job or
    ``advance/standing`` reservation
    """

    def execvnode(self, attr='exec_vnode'):
        """
        PBS type execution vnode
        """
        if attr in self.attributes:
            return PbsTypeExecVnode(self.attributes[attr])
        else:
            return None

    def exechost(self):
        """
        PBS type execution host
        """
        if 'exec_host' in self.attributes:
            return PbsTypeExecHost(self.attributes['exec_host'])
        else:
            return None

    def resvnodes(self):
        """
        nodes assigned to a reservation
        """
        if 'resv_nodes' in self.attributes:
            return self.attributes['resv_nodes']
        else:
            return None

    def select(self):
        if hasattr(self, '_select') and self._select is not None:
            return self._select

        if 'schedselect' in self.attributes:
            self._select = PbsTypeSelect(self.attributes['schedselect'])

        elif 'select' in self.attributes:
            self._select = PbsTypeSelect(self.attributes['select'])
        else:
            return None

        return self._select

    @classmethod
    def get_hosts(cls, exechost=None):
        """
        :returns: The hosts portion of the exec_host
        """
        hosts = []
        exechosts = cls.utils.parse_exechost(exechost)
        if exechosts:
            for h in exechosts:
                eh = list(h.keys())[0]
                if eh not in hosts:
                    hosts.append(eh)
        return hosts

    def get_vnodes(self, execvnode=None):
        """
        :returns: The unique vnode names of an execvnode as a list
        """
        if execvnode is None:
            if 'exec_vnode' in self.attributes:
                execvnode = self.attributes['exec_vnode']
            elif 'resv_nodes' in self.attributes:
                execvnode = self.attributes['resv_nodes']
            else:
                return []

        vnodes = []
        execvnodes = PbsTypeExecVnode(execvnode)
        if execvnodes:
            for n in execvnodes:
                ev = list(n.keys())[0]
                if ev not in vnodes:
                    vnodes.append(ev)
        return vnodes

    def walltime(self, attr='Resource_List.walltime'):
        if attr in self.attributes:
            return self.utils.convert_duration(self.attributes[attr])


class Reservation(ResourceResv):

    """
    PBS Reservation. Attributes and Resources

    :param attrs: Reservation attributes
    :type attrs: Dictionary
    :param hosts: List of hosts for maintenance
    :type hosts: List
    """

    dflt_attributes = {}

    def __init__(self, username=TEST_USER, attrs=None, hosts=None):
        self.server = {}
        self.script = None

        if attrs:
            self.attributes = attrs
        else:
            self.attributes = {}

        if hosts:
            self.hosts = hosts
        else:
            self.hosts = []

        if username is None:
            userinfo = pwd.getpwuid(os.getuid())
            self.username = userinfo[0]
        else:
            self.username = str(username)

        # These are not in dflt_attributes because of the conversion to CLI
        # options is done strictly
        if ATTR_resv_start not in self.attributes and \
           ATTR_job not in self.attributes:
            self.attributes[ATTR_resv_start] = str(int(time.time()) +
                                                   36 * 3600)

        if ATTR_resv_end not in self.attributes and \
           ATTR_job not in self.attributes:
            if ATTR_resv_duration not in self.attributes:
                self.attributes[ATTR_resv_end] = str(int(time.time()) +
                                                     72 * 3600)

        PBSObject.__init__(self, None, self.attributes, self.dflt_attributes)
        self.set_attributes()

    def __del__(self):
        del self.__dict__

    def set_variable_list(self, user, workdir=None):
        pass


class Queue(PBSObject):

    """
    PBS Queue container, holds attributes of the queue and
    pointer to server

    :param name: Queue name
    :type name: str or None
    :param attrs: Queue attributes
    :type attrs: Dictionary
    """

    dflt_attributes = {}

    def __init__(self, name=None, attrs={}, server=None):
        PBSObject.__init__(self, name, attrs, self.dflt_attributes)

        self.server = server
        m = ['queue']
        if server is not None:
            m += ['@' + server.shortname]
        if self.name is not None:
            m += [' ', self.name]
        m += [': ']
        self.logprefix = "".join(m)

    def __del__(self):
        del self.__dict__

    def revert_to_defaults(self):
        """
        reset queue attributes to defaults
        """

        ignore_attrs = ['id', ATTR_count, ATTR_rescassn]
        ignore_attrs += [ATTR_qtype, ATTR_enable, ATTR_start, ATTR_total]
        ignore_attrs += ['THE_END']

        len_attrs = len(ignore_attrs)
        unsetlist = []
        setdict = {}

        self.logger.info(
            self.logprefix +
            "reverting configuration to defaults")
        if self.server is not None:
            self.server.status(QUEUE, id=self.name, level=logging.DEBUG)

        for k in self.attributes.keys():
            for i in range(len_attrs):
                if k.startswith(ignore_attrs[i]):
                    break
            if (i == (len_attrs - 1)) and k not in self.dflt_attributes:
                unsetlist.append(k)

        if len(unsetlist) != 0 and self.server is not None:
            try:
                self.server.manager(MGR_CMD_UNSET, MGR_OBJ_QUEUE, unsetlist,
                                    self.name)
            except PbsManagerError as e:
                self.logger.error(e.msg)

        for k in self.dflt_attributes.keys():
            if (k not in self.attributes or
                    self.attributes[k] != self.dflt_attributes[k]):
                setdict[k] = self.dflt_attributes[k]

        if len(setdict.keys()) != 0 and self.server is not None:
            self.server.manager(MGR_CMD_SET, MGR_OBJ_QUEUE, setdict)

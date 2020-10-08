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
from ptl.lib.ptl_error import PbsManagerError
from ptl.lib.ptl_object import PBSObject
from ptl.lib.ptl_constants import (ATTR_resv_start, ATTR_job,
                                   ATTR_resv_end, ATTR_resv_duration,
                                   ATTR_count, ATTR_rescassn, ATTR_qtype,
                                   ATTR_enable, ATTR_start, ATTR_total)


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


class Entity(object):

    """
    Abstract representation of a PBS consumer that has an
    external relationship to the PBS system. For example, a
    user associated to an OS identifier (uid) maps to a PBS
    user entity.

    Entities may be subject to policies, such as limits, consume
    a certain amount of resource and/or fairshare usage.

    :param etype: Entity type
    :type etype: str or None
    :param name: Entity name
    :type name: str or None
    """

    def __init__(self, etype=None, name=None):
        self.type = etype
        self.name = name
        self.limits = []
        self.resource_usage = {}
        self.fairshare_usage = 0

    def set_limit(self, limit=None):
        """
        :param limit: Limit to be set
        :type limit: str or None
        """
        for l in self.limits:
            if str(limit) == str(l):
                return
        self.limits.append(limit)

    def set_resource_usage(self, container=None, resource=None, usage=None):
        """
        Set the resource type

        :param resource: PBS resource
        :type resource: str or None
        :param usage: Resource usage value
        :type usage: str or None
        """
        if self.type:
            if container in self.resource_usage:
                if self.resource_usage[self.type]:
                    if resource in self.resource_usage[container]:
                        self.resource_usage[container][resource] += usage
                    else:
                        self.resource_usage[container][resource] = usage
                else:
                    self.resource_usage[container] = {resource: usage}

    def set_fairshare_usage(self, usage=0):
        """
        Set fairshare usage

        :param usage: Fairshare usage value
        :type usage: int
        """
        self.fairshare_usage += usage

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return str(self.limits) + ' ' + str(self.resource_usage) + ' ' + \
            str(self.fairshare_usage)


class Policy(object):

    """
    Abstract PBS policy. Can be one of ``limits``,
    ``access control``, ``scheduling policy``, etc...this
    class does not currently support any operations
    """

    def __init__(self):
        pass


class Limit(Policy):

    """
    Representation of a PBS limit
    Limits apply to containers, are of a certain type
    (e.g., max_run_res.ncpus) associated to a given resource
    (e.g., resource), on a given entity (e.g.,user Bob) and
    have a certain value.

    :param limit_type: Type of the limit
    :type limit_type: str or None
    :param resource: PBS resource
    :type resource: str or None
    :param entity_obj: Entity object
    :param value: Limit value
    :type value: int
    """

    def __init__(self, limit_type=None, resource=None,
                 entity_obj=None, value=None, container=None,
                 container_id=None):
        self.set_container(container, container_id)
        self.soft_limit = False
        self.hard_limit = False
        self.set_limit_type(limit_type)
        self.set_resource(resource)
        self.set_value(value)
        self.entity = entity_obj

    def set_container(self, container, container_id):
        """
        Set the container

        :param container: Container which is to be set
        :type container: str
        :param container_id: Container id
        """
        self.container = container
        self.container_id = container_id

    def set_limit_type(self, t):
        """
        Set the limit type

        :param t: Limit type
        :type t: str
        """
        self.limit_type = t
        if '_soft' in t:
            self.soft_limit = True
        else:
            self.hard_limit = True

    def set_resource(self, resource):
        """
        Set the resource

        :param resource: resource value to set
        :type resource: str
        """
        self.resource = resource

    def set_value(self, value):
        """
        Set the resource value

        :param value: Resource value
        :type value: str
        """
        self.value = value

    def __eq__(self, value):
        if str(self) == str(value):
            return True
        return False

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        l = [self.container_id, self.limit_type, self.resource, '[',
             self.entity.type, ':', self.entity.name, '=', self.value, ']']
        return " ".join(l)


class EquivClass(PBSObject):

    """
    Equivalence class holds information on a collection of entities
    grouped according to a set of attributes
    :param attributes: Dictionary of attributes
    :type attributes: Dictionary
    :param entities: List of entities
    :type entities: List
    """

    def __init__(self, name, attributes={}, entities=[]):
        self.name = name
        self.attributes = attributes
        self.entities = entities

    def add_entity(self, entity):
        """
        Add entities

        :param entity: Entity to add
        :type entity: str
        """
        if entity not in self.entities:
            self.entities.append(entity)

    def __str__(self):
        s = [str(len(self.entities)), ":", ":".join(self.name)]
        return "".join(s)

    def show(self, showobj=False):
        """
        Show the entities

        :param showobj: If true then show the entities
        :type showobj: bool
        """
        s = " && ".join(self.name) + ': '
        if showobj:
            s += str(self.entities)
        else:
            s += str(len(self.entities))
        print(s)
        return s


class Holidays():
    """
    Descriptive calss for Holiday file.
    """

    def __init__(self):
        self.year = {'id': "YEAR", 'value': None, 'valid': False}
        self.weekday = {'id': "weekday", 'p': None, 'np': None, 'valid': None,
                        'position': None}
        self.monday = {'id': "monday", 'p': None, 'np': None, 'valid': None,
                       'position': None}
        self.tuesday = {'id': "tuesday", 'p': None, 'np': None, 'valid': None,
                        'position': None}
        self.wednesday = {'id': "wednesday", 'p': None, 'np': None,
                          'valid': None, 'position': None}
        self.thursday = {'id': "thursday", 'p': None, 'np': None,
                         'valid': None, 'position': None}
        self.friday = {'id': "friday", 'p': None, 'np': None, 'valid': None,
                       'position': None}
        self.saturday = {'id': "saturday", 'p': None, 'np': None,
                         'valid': None, 'position': None}
        self.sunday = {'id': "sunday", 'p': None, 'np': None, 'valid': None,
                       'position': None}

        self.days_set = []  # list of set days
        self._days_map = {'weekday': self.weekday, 'monday': self.monday,
                          'tuesday': self.tuesday, 'wednesday': self.wednesday,
                          'thursday': self.thursday, 'friday': self.friday,
                          'saturday': self.saturday, 'sunday': self.sunday}
        self.holidays = []  # list of calendar holidays

    def __str__(self):
        """
        Return the content to write to holidays file as a string
        """
        content = []
        if self.year['valid']:
            content.append(self.year['id'] + "\t" +
                           self.year['value'])

        for i in range(0, len(self.days_set)):
            content.append(self.days_set[i]['id'] + "\t" +
                           self.days_set[i]['p'] + "\t" +
                           self.days_set[i]['np'])

        # Add calendar holidays
        for day in self.holidays:
            content.append(day)

        return "\n".join(content)

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

from ptl.utils.pbs_dshutils import DshUtils
from ptl.lib.pbs_testlib import *


class FairshareTree(object):

    """
    Object representation of the Scheduler's resource_group
    file and pbsfs data

    :param hostname: Hostname of the machine
    :type hostname: str
    """
    du = DshUtils()

    def __init__(self, hostname=None, resource_group=None):
        self.logger = logging.getLogger(__name__)
        self.hostname = hostname
        self.resource_group = resource_group
        self.nodes = {}
        self.root = None
        self._next_id = -1

    def update_resource_group(self):
        if self.resource_group:
            fn = self.du.create_temp_file(body=self.__str__())
            ret = self.du.run_copy(self.hostname, src=fn,
                                   dest=self.resource_group,
                                   preserve_permission=False, sudo=True)
            os.remove(fn)

            if ret['rc'] != 0:
                raise PbsFairshareError(rc=1, rv=False,
                                        msg='error updating resource group')
        return True

    def update(self):
        for node in self.nodes.values():
            if node._parent is None:
                pnode = self.get_node(id=node.parent_id)
                if pnode:
                    node._parent = pnode
                    if node not in pnode._child:
                        pnode._child.append(node)

    def _add_node(self, node):
        if node.name == 'TREEROOT' or node.name == 'root':
            self.root = node
        self.nodes[node.name] = node
        if node.parent_name in self.nodes:
            self.nodes[node.parent_name]._child.append(node)
            node._parent = self.nodes[node.parent_name]

    def add_node(self, node, apply=True):
        """
        add node to the fairshare tree
        """
        self._add_node(node)
        if apply:
            return self.update_resource_group()
        return True

    def create_node(self, name, id, parent_name, nshares):
        """
        Add an entry to the ``resource_group`` file

        :param name: The name of the entity to add
        :type name: str
        :param id: The uniqe numeric identifier of the entity
        :type id: int
        :param parent: The name of the parent/group of the entity
        :type parent: str
        :param nshares: The number of shares assigned to this entity
        :type nshares: int
        :returns: True on success, False otherwise
        """
        if name in self.nodes:
            self.logger.warning('fairshare: node ' + name + ' already defined')
            return True
        self.logger.info('creating tree node: ' + name)

        node = FairshareNode(name, id, parent_name=parent_name,
                             nshares=nshares)
        self._add_node(node)
        return self.update_resource_group()

    def get_node(self, name=None, id=None):
        """
        Return a node of the fairshare tree identified by either
        name or id.

        :param name: The name of the entity to query
        :type name: str or None
        :param id: The id of the entity to query
        :returns: The fairshare information of the entity when
                  found, if not, returns None

        .. note:: The name takes precedence over the id.
        """
        for node in self.nodes.values():
            if name is not None and node.name == name:
                return node
            if id is not None and node.id == id:
                return node
        return None

    def __batch_status__(self):
        """
        Convert fairshare tree object to a batch status format
        """
        dat = []
        for node in self.nodes.values():
            if node.name == 'root':
                continue
            einfo = {}
            einfo['cgroup'] = node.id
            einfo['id'] = node.name
            einfo['group'] = node.parent_id
            einfo['nshares'] = node.nshares
            if len(node.prio) > 0:
                p = []
                for k, v in node.prio.items():
                    p += ["%s:%d" % (k, int(v))]
                einfo['penalty'] = ", ".join(p)
            einfo['usage'] = node.usage
            if node.perc:
                p = []
                for k, v in node.perc.items():
                    p += ["%s:%.3f" % (k, float(v))]
                    einfo['shares_perc'] = ", ".join(p)
            ppnode = self.get_node(id=node.parent_id)
            if ppnode:
                ppname = ppnode.name
                ppid = ppnode.id
            else:
                ppnode = self.get_node(name=node.parent_name)
                if ppnode:
                    ppname = ppnode.name
                    ppid = ppnode.id
                else:
                    ppname = ''
                    ppid = None
            einfo['parent'] = "%s (%s) " % (str(ppid), ppname)
            dat.append(einfo)
        return dat

    def get_next_id(self):
        self._next_id -= 1
        return self._next_id

    def __repr__(self):
        return self.__str__()

    def _dfs(self, node, dat):
        if node.name != 'root':
            s = []
            if node.name is not None:
                s += [node.name]
            if node.id is not None:
                s += [str(node.id)]
            if node.parent_name is not None:
                s += [node.parent_name]
            if node.nshares is not None:
                s += [str(node.nshares)]
            if node.usage is not None:
                s += [str(node.usage)]
            dat.append("\t".join(s))
        for n in node._child:
            self._dfs(n, dat)

    def __str__(self):
        dat = []
        if self.root:
            self._dfs(self.root, dat)
        if len(dat) > 0:
            dat += ['\n']
        return "\n".join(dat)


class FairshareNode(object):

    """
    Object representation of the fairshare data as queryable through
    the command ``pbsfs``.

    :param name: Name of fairshare node
    :type name: str or None
    :param nshares: Number of shares
    :type nshares: int or None
    :param usage: Fairshare usage
    :param perc: Percentage the entity has of the tree
    """

    def __init__(self, name=None, id=None, parent_name=None, parent_id=None,
                 nshares=None, usage=None, perc=None):
        self.name = name
        self.id = id
        self.parent_name = parent_name
        self.parent_id = parent_id
        self.nshares = nshares
        self.usage = usage
        self.perc = perc
        self.prio = {}
        self._parent = None
        self._child = []

    def __str__(self):
        ret = []
        if self.name is not None:
            ret.append(self.name)
        if self.id is not None:
            ret.append(str(self.id))
        if self.parent_name is not None:
            ret.append(str(self.parent_name))
        if self.nshares is not None:
            ret.append(str(self.nshares))
        if self.usage is not None:
            ret.append(str(self.usage))
        if self.perc is not None:
            ret.append(str(self.perc))
        return "\t".join(ret)

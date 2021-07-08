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
import logging
import os
import pwd
import re
import grp
import sys
import time

from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_testusers import ROOT_USER, PbsUser
from ptl.lib.ptl_error import PbsFairshareError


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


class Fairshare(object):
    du = DshUtils()
    logger = logger = logging.getLogger(__name__)
    fs_re = r'(?P<name>[\S]+)[\s]*:[\s]*Grp:[\s]*(?P<Grp>[-]*[0-9]*)' + \
            r'[\s]*cgrp:[\s]*(?P<cgrp>[-]*[0-9]*)[\s]*' + \
            r'Shares:[\s]*(?P<Shares>[-]*[0-9]*)[\s]*Usage:[\s]*' + \
            r'(?P<Usage>[0-9]+)[\s]*Perc:[\s]*(?P<Perc>.*)%'
    fs_tag = re.compile(fs_re)

    def __init__(self, has_snap=None, pbs_conf={}, sc_name=None,
                 hostname=None, user=None):
        self.has_snap = has_snap
        self.pbs_conf = pbs_conf
        self.sc_name = sc_name
        self.hostname = hostname
        self.user = user
        _m = ['fairshare']
        if self.sc_name is not None:
            _m += ['-', str(self.sc_name)]
        if self.user is not None:
            _m += ['-', str(self.user)]
        _m += [':']
        self.logprefix = "".join(_m)

    def revert_fairshare(self):
        """
        Helper method to revert scheduler's fairshare tree.
        """
        cmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs'), '-e']
        if self.sc_name is not 'default':
            cmd += ['-I', self.sc_name]
        self.du.run_cmd(self.hostname, cmd=cmd, runas=self.user)

    def query_fairshare(self, name=None, id=None):
        """
        Parse fairshare data using ``pbsfs`` and populates
        fairshare_tree.If name or id are specified, return the data
        associated to that id.Otherwise return the entire fairshare
        tree
        """
        if self.has_snap:
            return None

        tree = FairshareTree()
        cmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')]
        if self.sc_name != 'default':
            cmd += ['-I', self.sc_name]

        ret = self.du.run_cmd(self.hostname, cmd=cmd,
                              sudo=True, logerr=False)

        if ret['rc'] != 0:
            raise PbsFairshareError(rc=ret['rc'], rv=None,
                                    msg=str(ret['err']))
        pbsfs = ret['out']
        for p in pbsfs:
            m = self.fs_tag.match(p)
            if m:
                usage = int(m.group('Usage'))
                perc = float(m.group('Perc'))
                nm = m.group('name')
                cgrp = int(m.group('cgrp'))
                pid = int(m.group('Grp'))
                nd = tree.get_node(id=pid)
                if nd:
                    pname = nd.parent_name
                else:
                    pname = None
                # if an entity has a negative cgroup it should belong
                # to the unknown resource, we work around the fact that
                # PBS (up to 13.0) sets this cgroup id to -1 by
                # reassigning it to 0
                # TODO: cleanup once PBS code is updated
                if cgrp < 0:
                    cgrp = 0
                node = FairshareNode(name=nm,
                                     id=cgrp,
                                     parent_id=pid,
                                     parent_name=pname,
                                     nshares=int(m.group('Shares')),
                                     usage=usage,
                                     perc={'TREEROOT': perc})
                if perc:
                    node.prio['TREEROOT'] = float(usage) / perc
                if nm == name or id == cgrp:
                    return node

                tree.add_node(node, apply=False)
        # now that all nodes are known, update parent and child
        # relationship of the tree
        tree.update()

        for node in tree.nodes.values():
            pnode = node._parent
            while pnode is not None and pnode.id != 0:
                if pnode.perc['TREEROOT']:
                    node.perc[pnode.name] = \
                        (node.perc['TREEROOT'] * 100 / pnode.perc[
                         'TREEROOT'])
                if pnode.name in node.perc and node.perc[pnode.name]:
                    node.prio[pnode.name] = (
                        node.usage / node.perc[pnode.name])
                pnode = pnode._parent

        if name:
            n = tree.get_node(name)
            if n is None:
                raise PbsFairshareError(rc=1, rv=None,
                                        msg='Unknown entity ' + name)
            return n
        if id:
            n = tree.get_node(id=id)
            raise PbsFairshareError(rc=1, rv=None,
                                    msg='Unknown entity ' + str(id))
            return n
        return tree

    def set_fairshare_usage(self, name=None, usage=None):
        """
        Set the fairshare usage associated to a given entity.

        :param name: The entity to set the fairshare usage of
        :type name: str or :py:class:`~ptl.lib.pbs_testlib.PbsUser` or None
        :param usage: The usage value to set
        """
        if self.has_snap:
            return True

        if name is None:
            self.logger.error(self.logprefix + ' an entity name required')
            return False

        if isinstance(name, PbsUser):
            name = str(name)

        if usage is None:
            self.logger.error(self.logprefix + ' a usage is required')
            return False

        cmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')]
        if self.sc_name is not 'default':
            cmd += ['-I', self.sc_name]
        cmd += ['-s', name, str(usage)]
        ret = self.du.run_cmd(self.hostname, cmd, runas=self.user)
        if ret['rc'] == 0:
            return True
        return False

    def cmp_fairshare_entities(self, name1=None, name2=None):
        """
        Compare two fairshare entities. Wrapper of ``pbsfs -c e1 e2``

        :param name1: name of first entity to compare
        :type name1: str or :py:class:`~ptl.lib.pbs_testlib.PbsUser` or None
        :param name2: name of second entity to compare
        :type name2: str or :py:class:`~ptl.lib.pbs_testlib.PbsUser` or None
        :returns: the name of the entity of higher priority or None on error
        """
        if self.has_snap:
            return None

        if name1 is None or name2 is None:
            self.logger.erro(self.logprefix + 'two fairshare entity names ' +
                             'required')
            return None

        if isinstance(name1, PbsUser):
            name1 = str(name1)

        if isinstance(name2, PbsUser):
            name2 = str(name2)

        cmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')]
        if self.sc_name is not 'default':
            cmd += ['-I', self.sc_name]
        cmd += ['-c', name1, name2]
        ret = self.du.run_cmd(self.hostname, cmd, runas=self.user)
        if ret['rc'] == 0:
            return ret['out'][0]
        return None

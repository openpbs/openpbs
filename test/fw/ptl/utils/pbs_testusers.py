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


import grp


class PbsGroup(object):

    """
    The PbsGroup type augments a PBS groupname to associate it
    to users to which the group belongs

    :param name: The group name referenced
    :type name: str
    :param gid: gid of group
    :type gid: int or None
    :param users: The list of PbsUser objects the group belongs to
    :type users: List or None
    """

    def __init__(self, name, gid=None, users=None):
        self.name = name
        if gid is not None:
            self.gid = int(gid)
        else:
            self.gid = None

        try:
            _group = grp.getgrnam(self.name)
            self.gid = _group.gr_gid
        except:
            pass

        if users is None:
            self.users = []
        elif isinstance(users, list):
            self.users = users
        else:
            self.users = users.split(",")

        for u in self.users:
            if isinstance(u, str):
                self.users.append(PbsUser(u, groups=[self]))
            elif self not in u.groups:
                u.groups.append(self)

    def __repr__(self):
        return str(self.name)

    def __str__(self):
        return self.__repr__()

    def __int__(self):
        return int(self.gid)


class PbsUser(object):

    """
    The PbsUser type augments a PBS username to associate
    it to groups to which the user belongs

    :param name: The user name referenced
    :type name: str
    :param uid: uid of user
    :type uid: int or None
    :param groups: The list of PbsGroup objects the user
                   belongs to
    :type groups: List or None
    """

    def __init__(self, name, uid=None, groups=None):
        self.name = name
        if uid is not None:
            self.uid = int(uid)
        else:
            self.uid = None
        self.home = None
        self.gid = None
        self.shell = None
        self.gecos = None

        try:
            _user = pwd.getpwnam(self.name)
            self.uid = _user.pw_uid
            self.home = _user.pw_dir
            self.gid = _user.pw_gid
            self.shell = _user.pw_shell
            self.gecos = _user.pw_gecos
        except:
            pass

        if groups is None:
            self.groups = []
        elif isinstance(groups, list):
            self.groups = groups
        else:
            self.groups = groups.split(",")

        for g in self.groups:
            if isinstance(g, str):
                self.groups.append(PbsGroup(g, users=[self]))
            elif self not in g.users:
                g.users.append(self)

    def __repr__(self):
        return str(self.name)

    def __str__(self):
        return self.__repr__()

    def __int__(self):
        return int(self.uid)

# Test users/groups are expected to exist on the test systems
# User running the tests and the test users should have passwordless sudo
# access configured to avoid interrupted (queries for password) test runs

# Groups

TSTGRP0 = PbsGroup('tstgrp00', gid=1900)
TSTGRP1 = PbsGroup('tstgrp01', gid=1901)
TSTGRP2 = PbsGroup('tstgrp02', gid=1902)
TSTGRP3 = PbsGroup('tstgrp03', gid=1903)
TSTGRP4 = PbsGroup('tstgrp04', gid=1904)
TSTGRP5 = PbsGroup('tstgrp05', gid=1905)
TSTGRP6 = PbsGroup('tstgrp06', gid=1906)
TSTGRP7 = PbsGroup('tstgrp07', gid=1907)
GRP_PBS = PbsGroup('pbs', gid=901)
GRP_AGT = PbsGroup('agt', gid=1146)
ROOT_GRP = PbsGroup(grp.getgrgid(0).gr_name, gid=0)

# Users
# first group from group list is primary group of user
TEST_USER = PbsUser('pbsuser', uid=4359, groups=[TSTGRP0])
TEST_USER1 = PbsUser('pbsuser1', uid=4361, groups=[TSTGRP0, TSTGRP1, TSTGRP2])
TEST_USER2 = PbsUser('pbsuser2', uid=4362, groups=[TSTGRP0, TSTGRP1, TSTGRP3])
TEST_USER3 = PbsUser('pbsuser3', uid=4363, groups=[TSTGRP0, TSTGRP1, TSTGRP4])
TEST_USER4 = PbsUser('pbsuser4', uid=4364, groups=[TSTGRP1, TSTGRP4, TSTGRP5])
TEST_USER5 = PbsUser('pbsuser5', uid=4365, groups=[TSTGRP2, TSTGRP4, TSTGRP6])
TEST_USER6 = PbsUser('pbsuser6', uid=4366, groups=[TSTGRP3, TSTGRP4, TSTGRP7])
TEST_USER7 = PbsUser('pbsuser7', uid=4368, groups=[TSTGRP1])

OTHER_USER = PbsUser('pbsother', uid=4358, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                   GRP_AGT])
PBSTEST_USER = PbsUser('pbstest', uid=4355, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                    GRP_AGT])
TST_USR = PbsUser('tstusr00', uid=11000, groups=[TSTGRP0])
TST_USR1 = PbsUser('tstusr01', uid=11001, groups=[TSTGRP0])

BUILD_USER = PbsUser('pbsbuild', uid=9000, groups=[TSTGRP0])
DATA_USER = PbsUser('pbsdata', uid=4372, groups=[TSTGRP0])
MGR_USER = PbsUser('pbsmgr', uid=4367, groups=[TSTGRP0])
OPER_USER = PbsUser('pbsoper', uid=4356, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                 GRP_AGT])
ADMIN_USER = PbsUser('pbsadmin', uid=4357, groups=[TSTGRP0, TSTGRP2, GRP_PBS,
                                                   GRP_AGT])
PBSROOT_USER = PbsUser('pbsroot', uid=4371, groups=[TSTGRP0, TSTGRP2])
ROOT_USER = PbsUser('root', uid=0, groups=[ROOT_GRP])

PBS_USERS = (TEST_USER, TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
             TEST_USER5, TEST_USER6, TEST_USER7, OTHER_USER, PBSTEST_USER,
             TST_USR, TST_USR1)

PBS_GROUPS = (TSTGRP0, TSTGRP1, TSTGRP2, TSTGRP3, TSTGRP4, TSTGRP5, TSTGRP6,
              TSTGRP7, GRP_PBS, GRP_AGT)

PBS_OPER_USERS = (OPER_USER,)

PBS_MGR_USERS = (MGR_USER, ADMIN_USER)

PBS_DATA_USERS = (DATA_USER,)

PBS_ROOT_USERS = (PBSROOT_USER, ROOT_USER)

PBS_BUILD_USERS = (BUILD_USER,)

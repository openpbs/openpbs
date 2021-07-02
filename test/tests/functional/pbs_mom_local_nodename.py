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

from tests.functional import *
from ptl.lib.pbs_testlib import BatchUtils
import socket


class TestMomLocalNodeName(TestFunctional):
    """
    This test suite tests that mom sets its short name correctly
    and that mom.get_local_nodename() returns the correct value
    """

    def test_url_nodename_not_truncated(self):
        """
        This test case tests that mom does not truncate the value of
        PBS_MOM_NODE_NAME when it contains dots
        """
        self.du.set_pbs_config(hostname=self.mom.shortname,
                               confs={'PBS_MOM_NODE_NAME': 'a.b.c.d'})
        # Restart PBS for changes
        self.server.restart()
        self.mom.restart()
        # add hook
        a = {'event': 'execjob_begin', 'enabled': 'True'}
        hook_name = "begin"
        hook_body = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG,
           'my local nodename is %s'
           % pbs.get_local_nodename())
"""
        self.server.create_import_hook(hook_name, a, hook_body)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.mom.log_match("my local nodename is a.b.c.d")

    def test_ip_nodename_not_truncated(self):
        """
        This test case tests that mom does not truncate the value of
        PBS_MOM_NODE_NAME when it is an ipaddress
        """
        ipaddr = socket.gethostbyname(self.mom.hostname)
        self.du.set_pbs_config(hostname=self.mom.shortname,
                               confs={'PBS_MOM_NODE_NAME': ipaddr})
        # Restart PBS for changes
        self.server.restart()
        self.mom.restart()
        # add hook
        a = {'event': 'execjob_begin', 'enabled': 'True'}
        hook_name = "begin"
        hook_body = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG,
           'my local nodename is %s'
           % pbs.get_local_nodename())
"""
        self.server.create_import_hook(hook_name, a, hook_body)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.mom.log_match("my local nodename is %s" % ipaddr)

    def tearDown(self):
        self.du.unset_pbs_config(hostname=self.mom.shortname,
                                 confs=['PBS_MOM_NODE_NAME'])
        self.server.restart()
        self.server.manager(MGR_CMD_DELETE, VNODE, id="@default",
                            runas=ROOT_USER)
        self.mom.restart()
        TestFunctional.tearDown(self)

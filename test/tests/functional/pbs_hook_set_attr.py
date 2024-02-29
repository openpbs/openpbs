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

hook_body_node_attr_alter = """
import pbs
e = pbs.event()
vnl = pbs.event().vnode_list
local_node = pbs.get_local_nodename()
vnl[local_node].Mom = None
vnl[local_node].Port = 123
"""


class TestHookSetAttr(TestFunctional):

    def test_node_ro_attr_hook(self):
        """
        Try to alter RO node attributes from hook and check
        the attributes are protected to the write.
        """
        hook_name = "node_attr_ro"
        a = {'event': 'exechost_periodic',
             'enabled': 'True',
             'freq': 3}
        rv = self.server.create_import_hook(
            hook_name, a, hook_body_node_attr_alter, overwrite=True)
        self.assertTrue(rv)

        msg = 'Error 15003 setting attribute Mom in update from mom hook'
        self.server.log_match(msg, starttime=time.time())

        msg = 'Error 15003 setting attribute Port in update from mom hook'
        self.server.log_match(msg, starttime=time.time())

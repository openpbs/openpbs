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


class TestNodesQueues(TestFunctional):

    def setUp(self):
        TestFunctional.setUp(self)
        self.server.add_resource('foo', 'string', 'h')

        a = {'resources_available.ncpus': 4}
        self.mom.create_vnodes(
            a, 8, attrfunc=self.cust_attr)
        self.vn = ['%s[%d]' % (self.mom.shortname, i) for i in range(4)]
        a = {'queue_type': 'execution', 'started': 't', 'enabled': 't'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')

        self.server.manager(MGR_CMD_SET, NODE, {
                            'queue': 'workq2'}, id=self.vn)
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_key': 'foo'})
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_enable': 't'})

    def cust_attr(self, name, totnodes, numnode, attrib):
        a = {}
        if numnode % 2 == 0:
            a['resources_available.foo'] = 'A'
        else:
            a['resources_available.foo'] = 'B'
        return {**attrib, **a}

    def test_node_queue_assoc_ignored(self):
        """
        Issue with node grouping and nodes associated with queues.  If
        node_grouping is set at the server level, node/queue association is
        not honored
        """

        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'vscatter', 'queue': 'workq2'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        nodes = j.get_vnodes(j.exec_vnode)
        self.assertTrue((nodes[0] == self.vn[0] and
                         nodes[1] == self.vn[2]) or
                        (nodes[0] == self.vn[1] and
                         nodes[1] == self.vn[3]))

# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from tests.interfaces import *


@tags('multisched')
class TestQueuePartition(TestInterfaces):
    """
    Test suite to test partition attr for queue
    """

    def create_queue_partition(
            self,
            q_type="execution",
            q_name="Q1",
            partition="P1",
            enable="True",
            start="True"):
        """
        Common function to create queue with partition
        :param q_type: "queue_type" attribute of queue object ,
                    Defaults to "execution"
        :type q_type:  str
        :param q_name: name of the queue, Defaults to "Q1"
        :type q_name: str
        :param partition: "partition" attribute of queue object,
                    Defaults to "P1"
        :type partition: str
        :param enable: "enabled" attribute of queue object, Defaults to "True"
        :type enable: boolean
        :param start: "started" attribute of queue object, Defaults to "True"
        :type start: boolean
        """
        attr = {
            'queue_type': q_type,
            'enabled': enable,
            'started': start,
            'partition': partition}
        self.server.manager(MGR_CMD_CREATE,
                            QUEUE, attr,
                            id=q_name, expect=True)

    def test_set_unset_partition(self):
        """
        Test to set/unset the partition attribute of queue object
        """
        self.create_queue_partition()
        self.server.manager(MGR_CMD_SET,
                            QUEUE, {'partition': "P2"},
                            id="Q1", expect=True)
        # resetting the same partition value
        self.server.manager(MGR_CMD_SET,
                            QUEUE, {'partition': "P2"},
                            id="Q1", expect=True)
        self.server.manager(MGR_CMD_UNSET,
                            QUEUE, 'partition',
                            id="Q1", expect=True)

    def test_set_partition_user_permissions(self):
        """
        Test to check the user permissions for set/unset the partition
        attribute of queue
        """
        self.create_queue_partition()
        msg1 = "Unauthorized Request"
        msg2 = "checking the qmgr error message"
        try:
            self.server.manager(MGR_CMD_SET,
                                QUEUE, {'partition': "P2"},
                                id="Q1", runas=TEST_USER)
        except PbsManagerError as e:
            self.assertTrue(msg1 in e.msg[0], msg2)
        try:
            self.server.manager(MGR_CMD_UNSET,
                                QUEUE, 'partition',
                                id="Q1", runas=TEST_USER)
        except PbsManagerError as e:
            # self.assertEquals(e.rc, 15007)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

    def test_set_partition_to_routing_queue(self):
        """
        Test to check the set of partition attribute on routing queue
        """
        msg1 = "Can not assign a partition to route queue"
        msg2 = "checking the qmgr error message"
        try:
            self.create_queue_partition(
                q_type='route', enable='False', start='False')
        except PbsManagerError as e:
            # self.assertEquals(e.rc, 15217)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)
        self.server.manager(
            MGR_CMD_CREATE, QUEUE, {
                'queue_type': 'r'}, id='Q1')
        try:
            self.server.manager(MGR_CMD_SET,
                                QUEUE, {'partition': "P1"},
                                id="Q1")
        except PbsManagerError as e:
            # self.assertEquals(e.rc, 15007)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

    def test_modify_queue_with_partition_to_routing(self):
        """
        Test to check the modify of execution queue to routing when
        partition attribute is set
        """
        self.create_queue_partition()
        msg1 = ("Route queues are incompatible "
                "with the partition attribute queue_type")
        msg2 = "checking the qmgr error message"
        try:
            self.server.manager(MGR_CMD_SET,
                                QUEUE, {'queue_type': "r"},
                                id="Q1")
        except PbsManagerError as e:
            # self.assertEquals(e.rc, 15218)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

    def test_set_partition_without_queue_type(self):
        """
        Test to check the set of partition attribute on queue
        with not queue_type set
        """
        self.server.manager(MGR_CMD_CREATE,
                            QUEUE, {'partition': "P1"},
                            id="Q1", expect=True)
        self.server.manager(MGR_CMD_SET,
                            QUEUE, {'partition': "P2"},
                            id="Q1", expect=True)
        self.server.manager(MGR_CMD_SET,
                            QUEUE, {'queue_type': "execution"},
                            id="Q1", expect=True)

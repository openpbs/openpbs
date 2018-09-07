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

from tests.interfaces import *


class TestPartition(TestInterfaces):
    """
    Test suite to test partition attr
    """

    def partition_attr(self, mgr_cmd=MGR_CMD_SET,
                       obj_name="QUEUE", q_type=None,
                       name="Q1", enable="True",
                       start="True", partition="P1", user=ROOT_USER):
        """
        Common function to set partition attribute/s to node/queue object
        :param mgr_cmd: qmgr "MGR_CMD_SET/MGR_CMD_UNSET/MGR_CMD_CREATE" cmd,
        Defaults to MGR_CMD_SET
        :type mgr_cmd: int
        :param obj_name: PBS object vnode/queue. Defaults to queue
        :type obj_name: str
        :param q_type: "queue_type" attribute of queue object ,
                    Defaults to "execution"
        :type q_type:  str
        :param name: name of the queue/vnode , Defaults to Q1 for Queue object,
        and server shortname for Node object
        :type name: str
        :param enable: "enabled" attribute of queue object, Defaults to "True"
        :type enable: boolean
        :param start: "started" attribute of queue object, Defaults to "True"
        :type start: boolean
        :param partition: "partition" attribute of vnode/queue object,
                    Defaults to "P1"
        :type partition: str
        :param user: one of the pre-defined set of users
        :type user: :py:class:`~ptl.lib.pbs_testlib.PbsUser`
        """
        if obj_name is "QUEUE":
            if mgr_cmd == MGR_CMD_CREATE:
                if q_type is None:
                    attr = {'partition': partition}
                else:
                    attr = {
                        'queue_type': q_type,
                        'enabled': enable,
                        'started': start,
                        'partition': partition}
                self.server.manager(MGR_CMD_CREATE,
                                    QUEUE, attr, id=name, runas=user)
            elif mgr_cmd == MGR_CMD_SET:
                attr = {'partition': partition}
                self.server.manager(MGR_CMD_SET, QUEUE,
                                    attr, id=name, runas=user)
            elif mgr_cmd == MGR_CMD_UNSET:
                self.server.manager(MGR_CMD_UNSET, QUEUE,
                                    "partition", id=name, runas=user)
            else:
                msg = ("Error: partition_attr function takes only "
                       "MGR_CMD_[CREATE/SET/UNSET] value for mgr_cmd when "
                       "pbs object is queue")
                self.assertTrue(False, msg)
        elif obj_name is "NODE":
            if name is "Q1":
                name = self.server.shortname
            attr = {'partition': partition}
            if mgr_cmd == MGR_CMD_SET:
                self.server.manager(MGR_CMD_SET, NODE, attr,
                                    id=name, runas=user)
            elif mgr_cmd == MGR_CMD_UNSET:
                self.server.manager(MGR_CMD_UNSET, NODE,
                                    "partition", id=name, runas=user)
            else:
                msg = ("Error: partition_attr function takes only "
                       "MGR_CMD_SET/MGR_CMD_UNSET value for mgr_cmd when "
                       "pbs object is node")
                self.assertTrue(False, msg)
        else:
            msg = ("Error: partition_attr function takes only "
                   "QUEUE/NODE objects value for obj_name")
            self.assertTrue(False, msg)

    def test_set_unset_queue_partition(self):
        """
        Test to set/unset the partition attribute of queue object
        """
        self.partition_attr(mgr_cmd=MGR_CMD_CREATE, q_type="execution")
        self.partition_attr(mgr_cmd=MGR_CMD_SET, partition="P2")
        # resetting the same partition value
        self.partition_attr(mgr_cmd=MGR_CMD_SET, partition="P2")
        self.partition_attr(mgr_cmd=MGR_CMD_UNSET)

    def test_set_queue_partition_user_permissions(self):
        """
        Test to check the user permissions for set/unset the partition
        attribute of queue
        """
        self.partition_attr(mgr_cmd=MGR_CMD_CREATE, q_type="execution")
        msg1 = "Unauthorized Request"
        msg2 = "checking the qmgr error message"
        try:
            self.partition_attr(mgr_cmd=MGR_CMD_SET, partition="P2")
        except PbsManagerError as e:
            self.assertTrue(msg1 in e.msg[0], msg2)
        try:
            self.partition_attr(mgr_cmd=MGR_CMD_UNSET)
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15007)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

    def test_set_partition_to_routing_queue(self):
        """
        Test to check the set of partition attribute on routing queue
        """
        msg0 = "Route queues are incompatible with the "\
               "partition attribute"
        msg1 = "Cannot assign a partition to route queue"
        msg2 = "Qmgr error message do not match"
        try:
            self.partition_attr(
                mgr_cmd=MGR_CMD_CREATE,
                q_type="route",
                enable="False",
                start="False")
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15217)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg0 in e.msg[0], msg2)
        self.server.manager(
            MGR_CMD_CREATE, QUEUE, {
                'queue_type': 'route'}, id='Q1')
        try:
            self.partition_attr(mgr_cmd=MGR_CMD_SET)
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15007)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

    def test_modify_queue_with_partition_to_routing(self):
        """
        Test to check the modify of execution queue to routing when
        partition attribute is set
        """
        self.partition_attr(mgr_cmd=MGR_CMD_CREATE, q_type="execution")
        msg1 = ("Route queues are incompatible "
                "with the partition attribute queue_type")
        msg2 = "checking the qmgr error message"
        try:
            self.partition_attr(mgr_cmd=MGR_CMD_SET, q_type="route")
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15218)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

    def test_set_partition_without_queue_type(self):
        """
        Test to check the set of partition attribute on queue
        with not queue_type set
        """
        self.partition_attr(mgr_cmd=MGR_CMD_CREATE)
        self.partition_attr(mgr_cmd=MGR_CMD_SET, partition="P2")
        self.partition_attr(mgr_cmd=MGR_CMD_SET, q_type="execution")

    def test_partition_node_attr(self):
        """
        Test to set/unset the partition attribute of node object
        """
        self.partition_attr(obj_name="NODE")
        self.partition_attr(obj_name="NODE", partition="P2")
        # resetting the same partition value
        self.partition_attr(obj_name="NODE", partition="P2")
        self.partition_attr(mgr_cmd=MGR_CMD_UNSET, obj_name="NODE")

    def test_set_partition_node_attr_user_permissions(self):
        """
        Test to check the user permissions for set/unset the partition
        attribute of node
        """
        self.partition_attr(obj_name="NODE")
        msg1 = "Unauthorized Request"
        msg2 = "didn't receive expected error message"
        try:
            self.partition_attr(
                obj_name="NODE",
                partition="P2",
                user=TEST_USER)
        except PbsManagerError as e:
            self.assertTrue(msg1 in e.msg[0], msg2)
        try:
            self.partition_attr(mgr_cmd=MGR_CMD_UNSET,
                                obj_name="NODE", user=TEST_USER)
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15007)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

    def test_partition_association_with_node_and_queue(self):
        """
        Test to check the set of partition attribute and association
        between queue and node
        """
        self.partition_attr(mgr_cmd=MGR_CMD_CREATE, q_type="execution")
        self.partition_attr(obj_name="NODE")
        self.partition_attr(
            mgr_cmd=MGR_CMD_CREATE,
            q_type="execution",
            name="Q2",
            partition="P2")
        self.partition_attr(mgr_cmd=MGR_CMD_UNSET, obj_name="NODE")
        self.server.manager(MGR_CMD_SET, NODE, {
                            'queue': "Q2"}, id=self.server.shortname)
        self.partition_attr(obj_name="NODE", partition="P2")

    def test_mismatch_of_partition_on_node_and_queue(self):
        """
        Test to check the set of partition attribute is disallowed
        if partition ids do not match on queue and node
        """
        self.test_partition_association_with_node_and_queue()
        msg1 = "Invalid partition in queue"
        msg2 = "didn't receive expected error message"
        try:
            self.partition_attr(mgr_cmd=MGR_CMD_SET, name="Q2")
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15221)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)
        msg1 = "Partition P2 is not part of queue for node"
        try:
            self.server.manager(MGR_CMD_SET,
                                NODE, {'queue': "Q1"},
                                id=self.server.shortname)
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15220)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)
        msg1 = "Queue Q2 is not part of partition for node"
        try:
            self.partition_attr(obj_name="NODE")
        except PbsManagerError as e:
            # self.assertEqual(e.rc, 15219)
            # The above code has to be uncommented when the PTL framework
            # bug PP-881 gets fixed
            self.assertTrue(msg1 in e.msg[0], msg2)

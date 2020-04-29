# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

import os

from tests.functional import *
from ptl.lib.pbs_ifl_mock import *


@tags('smoke')
class TestQmgr(TestFunctional):

    """
    Test suite for PBSPro's qmgr command
    """

    resc_flags = [None, 'n', 'h', 'nh', 'q', 'f', 'fh', 'm', 'mh']
    resc_flags_ctl = [None, 'r', 'i']
    objs = [QUEUE, SERVER, NODE, JOB, RESV]
    resc_name = "ptl_custom_res"
    avail_resc_name = 'resources_available.' + resc_name

    def setUp(self):
        TestFunctional.setUp(self)
        self.obj_map = {QUEUE: self.server.default_queue,
                        SERVER: self.server.name,
                        NODE: self.mom.shortname,
                        JOB: None, RESV: None}

    def __check_whitespace_prefix(self, line):
        """
        Check whether the whitespace prefix for the line specified is correct

        :param line: the line to check
        :type line: String
        """
        if line is None:
            return

        if line[0] == " ":
            # Spaces are the prefix for new attribute lines
            # Make sure that this is a new attribute line
            self.assertTrue("=" in line)
        elif line[0] == "\t":
            # Tabs are prefix for line extensions
            # Make sure that this is a line extension
            self.assertTrue("=" not in line)

    def test_listcmd_whitespaces(self):
        """
        Check that the prefix for new attributes listed out by qmgr list
        are spaces and that for line extensions is a tab
        """
        fn = self.du.create_temp_file()
        node_prefix = "vn"
        nodename = node_prefix + "[0]"
        vndef_file = None
        qmgr_path = os.path.join(self.server.pbs_conf["PBS_EXEC"], "bin",
                                 "qmgr")
        if not os.path.isfile(qmgr_path):
            self.server.skipTest("qmgr binary not found!")

        try:
            # Check 1: New attributes are prefixed with spaces and not tabs
            # Execute qmgr -c 'list sched' and store output in a temp file
            if self.du.is_localhost(self.server.hostname) is True:
                qmgr_cmd = [qmgr_path, "-c", "list sched"]
            else:
                qmgr_cmd = [qmgr_path, "-c", "\'list sched\'"]
            with open(fn, "w+") as tempfd:
                ret = self.du.run_cmd(self.server.hostname, qmgr_cmd,
                                      stdout=tempfd)

                self.assertTrue(ret['rc'] == 0)
                for line in tempfd:
                    self.__check_whitespace_prefix(line)

            # Check 2: line extensions are prefixed with tabs and not spaces
            # Create a random long, comma separated string
            blah = "blah"
            long_string = ""
            for i in range(49):
                long_string += blah + ","
            long_string += blah
            # Create a new vnode
            attrs = {ATTR_rescavail + ".ncpus": 2}
            self.server.create_vnodes(node_prefix, attrs, 1, self.mom)
            # Set 'comment' attribute to the long string we created above
            attrs = {ATTR_comment: long_string}
            self.server.manager(MGR_CMD_SET, VNODE, attrs, nodename)
            # Execute "qmgr 'list node vn[0]'"
            # The comment attribute should generate a line extension
            if self.du.is_localhost(self.server.hostname) is True:
                qmgr_cmd = [qmgr_path, "-c", "list node " + nodename]
            else:
                qmgr_cmd = [qmgr_path, "-c", "\'list node " + nodename + "\'"]
            with open(fn, "w+") as tempfd:
                ret = self.du.run_cmd(self.server.hostname, qmgr_cmd,
                                      stdout=tempfd)
                self.assertTrue(ret['rc'] == 0)
                for line in tempfd:
                    self.__check_whitespace_prefix(line)

        finally:
            # Cleanup
            # Remove the temporary file
            os.remove(fn)
            # Delete the vnode created
            if vndef_file is not None:
                self.mom.delete_vnodes()
                self.server.manager(MGR_CMD_DELETE, VNODE, id=nodename)

    def test_multi_attributes(self):
        """
        Test to verify that if multiple attributes are set
        simultaneously and out of which one fail then none
        will be set.
        """

        a = {'queue_type': 'execution',
             'enabled': 'True',
             'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')

        a = {'partition': 'foo'}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq')

        a = {'partition': 'bar'}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq2')

        a = {'queue': 'workq', 'partition': 'bar'}
        try:
            self.server.manager(MGR_CMD_SET, NODE, a,
                                id=self.mom.shortname)
        except PbsManagerError as e:
            self.assertNotEqual(e.rc, '0')
            # Due to PP-1073 checking for the partial message
            msg = " is not part of queue for node"
            self.logger.info("looking for error, %s" % msg)
            self.assertTrue(msg in e.msg[0])
        self.server.expect(NODE, 'queue', op=UNSET, id=self.mom.shortname)

    def set_and_test_comment(self, comment):
        """
        Set the node's comment, then print it and re-import it
        """
        a = {'comment': comment}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)
        qmgr_path = \
            os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', 'qmgr')
        qmgr_cmd_print = qmgr_path + \
            (' -c "p n %s comment"' % self.mom.shortname)
        ret = self.du.run_cmd(self.server.hostname,
                              cmd=qmgr_cmd_print, as_script=True)
        self.assertEqual(ret['rc'], 0)
        fn = self.du.create_temp_file()
        for line in ret['out']:
            if '#' in line:
                continue
            if 'create node' in line:
                continue
            with open(fn, 'w') as f:
                f.write(line)
            qmgr_cmd_set = qmgr_path + ' < ' + fn
            ret_s = self.du.run_cmd(self.server.hostname,
                                    cmd=qmgr_cmd_set, as_script=True)
            self.assertEqual(ret_s['rc'], 0)

    def create_resource_helper(self, resc_type, resc_flag, ctrl_flag):
        """
        create a resource with associated type, flag, and control flag

        resc_type - Type of the resource

        resc_flag - Permissions/flags associated to the resource

        ctrl_flag - Control flags
        """
        attr = {}
        if resc_type:
            attr['type'] = resc_type
        if resc_flag:
            attr['flag'] = resc_flag
        if ctrl_flag:
            if 'flag' in attr:
                attr['flag'] += ctrl_flag
            else:
                attr['flag'] = ctrl_flag
        if attr is not None:
            try:
                rc = self.server.manager(MGR_CMD_CREATE, RSC, attr,
                                         id=self.resc_name)
            except PbsManagerError as e:
                msg = 'Erroneous to have'
                self.assertIn(msg, e.msg[0])
                return False
        else:
            rv = self.server.resources[self.resc_name].attributes['type']
            if resc_type is None:
                self.assertEqual(rv, 'string')
            else:
                self.assertEqual(rv, resc_type)

            if ctrl_flag is not None:
                resc_flag += ctrl_flag
            if resc_flag:
                rv = self.server.resources[self.resc_name].attributes['flag']
                self.assertEqual(sorted(rv), sorted(resc_flag))
        return True

    def delete_resource_helper(self, resc_type, resc_flg, ctrl_flg,
                               obj_type, obj_id):
        """
        Vierify behavior upon deleting a resource that is set on a PBS object.

        resc_type - The type of resource

        resc_flg - The permissions/flags of the resource

        ctrl_flg - The control flags of the resource

        obj_type - The object type (server, queue, node, job, reservation) on
        which the resource is set.

        obj_id - The object identifier/name
        """
        ar = 'resources_available.' + self.resc_name
        resc_map = {'long': 1, 'float': 1.0, 'string': 'abc', 'boolean': False,
                    'string_array': 'abc', 'size': '1gb'}
        if resc_type is not None:
            val = resc_map[resc_type]
        else:
            val = 'abc'
        objs = [JOB, RESV]
        if obj_type in objs:
            attr = {'Resource_List.' + self.resc_name: val}
            if obj_type == JOB:
                j = Job(TEST_USER1, attr)
            else:
                j = Reservation(TEST_USER1, attr)
            try:
                jid = self.server.submit(j)
            except PbsSubmitError as e:
                jid = e.rv
            if ctrl_flg is not None and ('r' in ctrl_flg or 'i' in ctrl_flg):
                self.assertEqual(jid, None)
                self.server.manager(MGR_CMD_DELETE, RSC, id=self.resc_name)
                return
            if obj_type == RESV:
                a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
                self.server.expect(RESV, a, id=jid)
            self.assertNotEqual(jid, None)
        else:
            self.server.manager(MGR_CMD_SET, obj_type, {ar: val},
                                id=obj_id)
        try:
            rc = self.server.manager(MGR_CMD_DELETE, RSC, id=self.resc_name)
        except PbsManagerError as e:
            if obj_type in objs:
                self.assertNotEqual(e.rc, 0)
                m = "Resource busy on " + PBS_OBJ_MAP[obj_type]
                self.assertIn(m, e.msg[0])
                self.server.delete(jid)
                self.server.expect(obj_type, 'queue', op=UNSET)
                self.server.manager(MGR_CMD_DELETE, RSC, id=self.resc_name)
            else:
                self.assertEqual(e.rc, 0)
                d = self.server.status(obj_type, ar, id=obj_id)
                if d:
                    self.assertNotIn(ar, d[0])

    def test_string_single_quoting(self):
        """
        Test to verify that if a string attribute has a double quote,
        the value is single-quoted correctly
        """
        self.set_and_test_comment('This is "my" node.')

    def test_string_double_quoting(self):
        """
        Test to verify that if a string attribute has a quote, the value
        is double-quoted correctly
        """
        self.set_and_test_comment("This node isn't good.")

    def test_string_type_resource_create_delete(self):
        """
        Test behavior of string type resource creation and deletion
        by all possible and supported types and flags.
        """
        for k, v in self.obj_map.items():
            for resc_flag in self.resc_flags:
                for ctrl_flag in self.resc_flags_ctl:
                    rv = self.create_resource_helper('string', resc_flag,
                                                     ctrl_flag)
                    if rv:
                        self.delete_resource_helper('string', resc_flag,
                                                    ctrl_flag, k, v)

    def test_long_type_resource_create_delete(self):
        """
        Test behavior of long type resource creation and deletion
        by all possible and supported types and flags.
        """
        for k, v in self.obj_map.items():
            for resc_flag in self.resc_flags:
                for ctrl_flag in self.resc_flags_ctl:
                    rv = self.create_resource_helper('long', resc_flag,
                                                     ctrl_flag)
                    if rv:
                        self.delete_resource_helper('long', resc_flag,
                                                    ctrl_flag, k, v)

    def test_float_type_resource_create_delete(self):
        """
        Test behavior of float type resource creation and deletion
        by all possible and supported types and flags.
        """
        for k, v in self.obj_map.items():
            for resc_flag in self.resc_flags:
                for ctrl_flag in self.resc_flags_ctl:
                    rv = self.create_resource_helper('float', resc_flag,
                                                     ctrl_flag)
                    if rv:
                        self.delete_resource_helper('float', resc_flag,
                                                    ctrl_flag, k, v)

    def test_boolean_type_resource_create_delete(self):
        """
        Test behavior of boolean type resource creation and deletion
        by all possible and supported types and flags.
        """
        for k, v in self.obj_map.items():
            for resc_flag in self.resc_flags:
                for ctrl_flag in self.resc_flags_ctl:
                    rv = self.create_resource_helper('boolean', resc_flag,
                                                     ctrl_flag)
                    if rv:
                        self.delete_resource_helper('boolean', resc_flag,
                                                    ctrl_flag, k, v)

    def test_size_type_resource_create_delete(self):
        """
        Test behavior of size type resource creation and deletion
        by all possible and supported types and flags.
        """
        for k, v in self.obj_map.items():
            for resc_flag in self.resc_flags:
                for ctrl_flag in self.resc_flags_ctl:
                    rv = self.create_resource_helper('size', resc_flag,
                                                     ctrl_flag)
                    if rv:
                        self.delete_resource_helper('size', resc_flag,
                                                    ctrl_flag, k, v)

    def test_string_array_type_resource_create_delete(self):
        """
        Test behavior of string_array type resource creation and deletion
        by all possible and supported types and flags.
        """
        for k, v in self.obj_map.items():
            for resc_flag in self.resc_flags:
                for ctrl_flag in self.resc_flags_ctl:
                    rv = self.create_resource_helper('string_array', resc_flag,
                                                     ctrl_flag)
                    if rv:
                        self.delete_resource_helper('string_array', resc_flag,
                                                    ctrl_flag, k, v)

    def test_none_type_resource_create_delete(self):
        """
        Test behavior of None type resource creation and deletion
        by all possible and supported types and flags.
        """
        for k, v in self.obj_map.items():
            for resc_flag in self.resc_flags:
                for ctrl_flag in self.resc_flags_ctl:
                    rv = self.create_resource_helper(None, resc_flag,
                                                     ctrl_flag)
                    if rv:
                        self.delete_resource_helper(None, resc_flag,
                                                    ctrl_flag, k, v)

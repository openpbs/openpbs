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


@tags('commands')
class TestPbsnodes(TestFunctional):

    """
    This test suite contains regression tests for pbsnodes command.
    """

    def setUp(self):
        TestFunctional.setUp(self)

        self.header = ['vnode', 'state', 'OS', 'hardware', 'host',
                       'queue', 'mem', 'ncpus', 'nmics', 'ngpus', 'comment']
        self.pbs_exec = self.server.pbs_conf['PBS_EXEC']
        self.pbsnodes = [os.path.join(self.pbs_exec, 'bin', 'pbsnodes')]
        self.svrname = self.server.pbs_server_name
        self.hostA = self.moms.values()[0].shortname

    def common_setUp(self):
        """
        Common setUp for tests test_pbsnodes_as_user and test_pbsnodes_as_root
        """
        TestFunctional.setUp(self)
        self.server.manager(MGR_CMD_DELETE, NODE, id="", sudo=True)
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.mom.shortname)
        self.server.expect(NODE, {'state': 'free'})

    def get_newnode_attrs(self, user):
        """
        return expected values of attributes on a newly created node
        """
        expect_dict = {}
        expect_dict[ATTR_NODE_Mom] = self.mom.hostname
        expect_dict[ATTR_NODE_ntype] = 'PBS'
        expect_dict[ATTR_NODE_state] = 'free'
        expect_dict[ATTR_rescavail + '.vnode'] = self.mom.shortname
        expect_dict[ATTR_rescavail + '.host'] = self.mom.shortname
        expect_dict[ATTR_NODE_resv_enable] = 'True'

        if user == 'root':
            expect_dict[ATTR_version] = self.server.pbs_version
            expect_dict[ATTR_NODE_Port] = '15002'

        if self.mom.is_cpuset_mom():
            del expect_dict['resources_available.vnode']

        return expect_dict

    def verify_node_dynamic_val(self, last_state_change_time, available_ncpus,
                                pcpus, sharing, available_mem):
        """
        verifies node dynamic attributes have expected value
        """
        sharing_list = ['default_shared', 'default_excl', 'default_exclhost',
                        'ignore_excl', 'force_excl', 'force_exclhost']

        # Verify that 'last_state_change_time' has value in datetime format
        last_state_change_time = str(last_state_change_time)
        try:
            time.strptime(last_state_change_time, "%a %b %d %H:%M:%S %Y")
        except ValueError:
            self.fail("'last_state_change_time' has value in incorrect format")
        else:
            mssg = "'last_state_change_time' has value in correct format"
            self.logger.info(mssg)

        # checking resources_avalable.ncpus and pcpus value are positive value
        ncpus_val = int(available_ncpus)
        if ncpus_val >= 0:
            mssg = "resources_available.ncpus have positive int value"
            self.logger.info(mssg)
        else:
            self.fail("resources_available.ncpus have negative value")
        pcpus_val = int(pcpus)
        if pcpus_val >= 0:
            self.logger.info("pcpus have positive int value")
        else:
            self.fail("pcpus have negative value")

        # verify pcpus and ncpus value are same
        if pcpus_val == ncpus_val:
            self.logger.info("pcpus and ncpus have same value")
        else:
            self.fail("pcpus and ncpus not having same value")

        # verify node sharing attribute have one of the value in
        # sharing_val list
        mssg = "Node sharing attribute not have expected value"
        self.assertIn(sharing, sharing_list, mssg)

        # checking resources_avalable.mem value is positive value
        index = available_mem.find('kb')
        if int(available_mem[:index]) >= 0:
            mssg = "resources_available.mem have positive int value"
            self.logger.info(mssg)
        else:
            self.fail("resources_available.mem not having positive int value")

    def test_pbsnodes_S(self):
        """
        This verifies that 'pbsnodes -S' results in a usage message
        """
        pbsnodes_S = self.pbsnodes + ['-S']
        out = self.du.run_cmd(self.svrname, cmd=pbsnodes_S)
        self.logger.info(out['err'][0])
        self.assertIn('usage:', out['err'][
                      0], 'usage not found in error message')

    def test_pbsnodes_S_host(self):
        """
        This verifies that 'pbsnodes -S <host>' results in an output
        with correct headers.
        """
        pbsnodes_S_host = self.pbsnodes + ['-S', self.hostA]
        out1 = self.du.run_cmd(self.svrname, cmd=pbsnodes_S_host)
        self.logger.info(out1['out'])
        for hdr in self.header:
            self.assertIn(
                hdr, out1['out'][0],
                "header %s not found in output" % hdr)

    def test_pbsnodes_aS(self):
        """
        This verifies that 'pbsnodes -aS' results in an output
        with correct headers.
        """
        pbsnodes_aS = self.pbsnodes + ['-aS']
        out2 = self.du.run_cmd(self.svrname, cmd=pbsnodes_aS)
        self.logger.info(out2['out'])
        for hdr in self.header:
            self.assertIn(
                hdr, out2['out'][0],
                "header %s not found in output" % hdr)

    def test_pbsnodes_av(self):
        """
        This verifies the values of last_used_time in 'pbsnodes -av'
        result before and after server shutdown, once a job submitted.
        """
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid = self.server.submit(j)
        self.server.accounting_match("E;%s;" % jid)
        if self.mom.is_cpuset_mom():
            i = 1
        else:
            i = 0

        prev = self.server.status(NODE, 'last_used_time')[i]['last_used_time']
        self.logger.info("Restarting server")
        self.server.restart()
        self.assertTrue(self.server.isUp(), 'Failed to restart Server Daemon')

        now = self.server.status(NODE, 'last_used_time')[i]['last_used_time']
        self.logger.info("Before: " + prev + ". After: " + now + ".")
        self.assertEqual(prev.strip(), now.strip(),
                         'Last used time mismatch after server restart')

    @skipOnCray
    def test_pbsnodes_as_user(self):
        """
        Validate default values of node attributes for non-root user
        """
        self.common_setUp()
        attr_dict = {}
        expected_attrs = self.get_newnode_attrs(TEST_USER)
        command = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                               'bin', 'pbsnodes -a')
        ret = self.du.run_cmd(self.server.hostname, command)
        self.assertEqual(ret['rc'], 0)
        attr_list = ret['out']
        list_len = len(attr_list) - 1
        for i in range(1, list_len):
            attr = attr_list[i].split('=')[0].strip()
            val = attr_list[i].split('=')[1].strip()
            attr_dict[attr] = val

        # comparing the pbsnodes -a output with expected result
        for attr in expected_attrs:
            self.assertEqual(expected_attrs[attr], attr_dict[attr])

        self.verify_node_dynamic_val(attr_dict['last_state_change_time'],
                                     attr_dict['resources_available.ncpus'],
                                     attr_dict['pcpus'], attr_dict['sharing'],
                                     attr_dict['resources_available.mem'])

    @tags('smoke')
    @skipOnCray
    def test_pbsnodes_as_root(self):
        """
        Validate default values of node attributes for root user
        """
        self.common_setUp()
        attr_dict = {}
        expected_attrs = self.get_newnode_attrs('root')
        command = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                               'bin', 'pbsnodes -a')
        ret = self.du.run_cmd(self.server.hostname, command, sudo=True)
        self.assertEqual(ret['rc'], 0)
        attr_list = ret['out']
        list_len = len(attr_list) - 1
        for i in range(1, list_len):
            attr = attr_list[i].split('=')[0].strip()
            val = attr_list[i].split('=')[1].strip()
            attr_dict[attr] = val

        # comparing the pbsnodes -a output with expected result
        for attr in expected_attrs:
            self.assertEqual(expected_attrs[attr], attr_dict[attr])

        self.verify_node_dynamic_val(attr_dict['last_state_change_time'],
                                     attr_dict['resources_available.ncpus'],
                                     attr_dict['pcpus'], attr_dict['sharing'],
                                     attr_dict['resources_available.mem'])

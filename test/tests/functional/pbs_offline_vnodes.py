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


class TestOfflineVnode(TestFunctional):
    """
    Tests if vnodes are marked offline:
     - when a hook fails and the hook fail action is 'offline_vnodes'
     - using pbsnodes -o
    """
    is_cray = True

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.is_cray = False

        TestFunctional.setUp(self)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

    def create_mom_hook(self):
        name = "h1"
        body = ("import pbs\n"
                "import time\n"
                "time.sleep(60)\n"
                "pbs.event.accept()")
        attr = {'event': 'execjob_begin', 'fail_action': 'offline_vnodes',
                'alarm': '3', 'enabled': 'true'}
        self.server.create_import_hook(name, attr, body)

    def create_bad_begin_hook(self):
        name = "h2"
        body = ("import pbs\n"
                "e=pbs.event()\n"
                "if e.job.in_ms_mom():\n"
                "    e.accept()\n"
                "raise ValueError('invalid name')\n")
        attr = {'event': 'execjob_begin', 'fail_action': 'offline_vnodes'}
        self.server.create_import_hook(name, attr, body)

    def create_bad_startup_hook(self):
        name = "h3"
        body = ("import pbs\n"
                "raise ValueError('invalid name')\n")
        attr = {'event': 'exechost_startup', 'fail_action': 'offline_vnodes'}
        self.server.create_import_hook(name, attr, body)

    def create_multi_vnodes(self, num_moms, num_vnode=3):
        if num_moms != len(self.moms):
            self.server.manager(MGR_CMD_DELETE, NODE, id="@default")
        if self.is_cray is True:
            if num_moms == 1 and len(self.moms) != 1:
                self.server.manager(MGR_CMD_CREATE, NODE,
                                    id=self.moms.values()[0].shortname)
                # adding a sleep of two seconds because it takes some time
                # before node resources start showing up
                time.sleep(2)
            return
        # No need to create vnodes on a cpuset mom
        if self.moms.values()[0].is_cpuset_mom() is True:
            return
        vn_attrs = {ATTR_rescavail + '.ncpus': 1,
                    ATTR_rescavail + '.mem': '1024mb'}
        for i in range(num_moms):
            self.moms.values()[i].create_vnodes(vn_attrs, num_vnode,
                                                usenatvnode=True, delall=False,
                                                expect=False)
            # Calling an explicit expect on newly created nodes.
            self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                               id=self.moms.values()[i].shortname)

    def verify_vnodes_state(self, expected_state, nodes):
        """
        Verify that the vnodes are set to the expected state
        """
        vlist = []
        for nd in nodes:
            vn = nd.shortname
            if self.is_cray is True:
                vnl = self.server.filter(
                    VNODE, {'resources_available.vntype': 'cray_compute'})
                vlist = vnl["resources_available.vntype=cray_compute"]
            elif nd.is_cpuset_mom() is True:
                vnl = self.server.status(NODE)
                vlist = [x['id'] for x in vnl if x['id'] !=
                         self.mom.shortname]
            else:
                vlist = [vn + "[0]", vn + "[1]"]
            for v1 in vlist:
                # Check the vnode state
                self.server.expect(
                    VNODE, {'state': expected_state}, id=v1, interval=2)
        return vlist[0]

    def tearDown(self):
        TestFunctional.tearDown(self)

        # Restore original node setup for future test cases.
        self.server.cleanup_jobs()
        self.server.manager(MGR_CMD_DELETE, NODE, id="@default")
        for m in self.moms.values():
            self.server.manager(MGR_CMD_CREATE, NODE,
                                id=m.shortname)

    def test_single_mom_hook_failure_affects_vnode(self):
        """
        Run an execjob_begin hook that sleep for sometime,
        at the same time set an alarm value so less that
        the hook alarms out and server executes the fail_action
        After this check if vnodes are marked offline.
        In case of a single mom reporting vnodes, it should mark
        all the vnodes and mom as offline.
        Once offlined, reset the mom by issueing pbsnodes -r
        and check if the job runs on one of the vnodes.
        """
        single_mom = self.moms.values()[0]
        start_time = time.time()
        self.create_multi_vnodes(1)
        self.create_mom_hook()

        # Check if hook files were copied to mom
        single_mom.log_match(
            "h1.HK;copy hook-related file request received",
            starttime=start_time, interval=2)
        single_mom.log_match(
            "h1.PY;copy hook-related file request received",
            starttime=start_time, interval=2)

        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=single_mom.shortname, interval=2)
        j1 = Job(TEST_USER)
        j1.set_sleep_time(1000)
        jid = self.server.submit(j1)
        # mom hook will alarm out and job will get into Q state
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)

        # since mom hook alarm out it's fail_action will put the
        # node in offline state
        self.server.expect(
            NODE, {ATTR_NODE_state: 'offline'},
            id=single_mom.shortname, interval=2)

        vname = self.verify_vnodes_state('offline', [single_mom])

        mom_host = single_mom.shortname
        pbs_exec = self.server.pbs_conf['PBS_EXEC']
        pbsnodes_cmd = os.path.join(pbs_exec, 'bin', 'pbsnodes')
        pbsnodes_reset = pbsnodes_cmd + ' -r ' + mom_host

        # Set mom sync hook timeout to be a low value because if mom fails to
        # get the hook after disabling it then next sync will happen after
        # 2 minutes by default and we don't want to wait that long.
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'sync_mom_hookfiles_timeout': '5'})
        self.server.manager(MGR_CMD_SET, HOOK, {'enabled': 'False'}, id="h1")
        # Make sure that hook has been sent to mom
        self.server.log_match("successfully sent hook file")
        self.du.run_cmd(self.server.hostname, cmd=pbsnodes_reset)
        self.server.delete(jid, wait=True)

        j2 = Job(TEST_USER)
        j2.set_attributes({ATTR_l + '.select': '1:vnode=' + vname})
        jid2 = self.server.submit(j2)
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=single_mom.shortname, interval=2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

    @requirements(num_moms=2)
    def test_multi_mom_hook_failure_affects_vnode(self):
        """
        Run an execjob_begin hook that sleeps for sometime,
        at the same time set an alarm value so less that
        the hook alarms out and server executes the fail_action
        After this check if vnodes are marked offline.
        In case of a multiple mom reporting same set of vnodes,
        it should not mark the vnodes and mom as offline because
        there are other moms active and reporting same vnodes.
        NOTE: This test needs moms to report the same set of vnodes
        """
        if len(self.moms) != 2:
            self.skipTest("Provide 2 moms while invoking test")

        for m in self.moms.values():
            if m.is_cpuset_mom():
                self.skipTest("Skipping test on cpuset moms")

        # The moms provided to the test may have unwanted vnodedef files.
        if self.moms.values()[0].has_vnode_defs():
            self.moms.values()[0].delete_vnode_defs()
        if self.moms.values()[1].has_vnode_defs():
            self.moms.values()[1].delete_vnode_defs()

        start_time = time.time()
        self.create_multi_vnodes(2)
        self.create_mom_hook()

        # Check if hook files were copied to mom
        for m in self.moms.values():
            m.log_match(
                "h1.HK;copy hook-related file request received",
                starttime=start_time, interval=2)
            m.log_match(
                "h1.PY;copy hook-related file request received",
                starttime=start_time, interval=2)

        # set one natural node to have higher ncpus than the other one so
        # that the job only goes to this natural node.
        self.server.manager(MGR_CMD_SET, NODE, {
                            ATTR_rescavail + '.ncpus': '256'},
                            id=self.moms.values()[0].shortname)
        self.server.manager(MGR_CMD_SET, NODE, {
                            ATTR_rescavail + '.ncpus': '1'},
                            id=self.moms.values()[1].shortname)

        j1 = Job(TEST_USER)

        if self.is_cray is True:
            # on a cray, make sure job runs on login node with higher number of
            # ncpus
            j1.set_attributes(
                {ATTR_l + '.select': '1:ncpus=256:vntype=cray_login'})
        else:
            j1.set_attributes({ATTR_l + '.select': '1:ncpus=256'})

        jid = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)

        self.server.expect(NODE, {ATTR_NODE_state: 'offline'},
                           id=self.moms.values()[0].shortname, interval=2)
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=self.moms.values()[1].shortname, interval=2)

        self.verify_vnodes_state('free', [self.moms.values()[1]])
        self.verify_vnodes_state('offline', [self.moms.values()[0]])

    @requirements(num_moms=2)
    def test_multi_mom_hook_failure_affects_vnode2(self):
        """
        Run an execjob_begin hook that gets an exception
        when executed by sister mom, causing
        the server to execute the fail_action=offline_vnodes, which
        result in sister vnode to be marked offline.
        """
        if len(self.moms) != 2:
            self.skipTest("Provide 2 moms while invoking test")

        for m in self.moms.values():
            if m.is_cpuset_mom():
                self.skipTest("Skipping test on cpuset moms")

        if self.is_cray is True:
            self.skipTest("Skipping test on Crays")

        # The moms provided to the test may have unwanted vnodedef files.
        if self.moms.values()[0].has_vnode_defs():
            self.moms.values()[0].delete_vnode_defs()
        if self.moms.values()[1].has_vnode_defs():
            self.moms.values()[1].delete_vnode_defs()

        start_time = time.time()
        self.create_multi_vnodes(num_moms=2, num_vnode=1)

        self.create_bad_begin_hook()

        # Check if hook files were copied to mom
        for m in self.moms.values():
            m.log_match(
                "h2.HK;copy hook-related file request received",
                starttime=start_time, interval=2)
            m.log_match(
                "h2.PY;copy hook-related file request received",
                starttime=start_time, interval=2)

        j1 = Job(TEST_USER)

        a = {ATTR_l + '.select': '2:ncpus=1',
             ATTR_l + '.place': 'scatter'}
        j1.set_attributes(a)

        jid = self.server.submit(j1)

        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=self.moms.values()[0].shortname, interval=2)
        # sister mom's vnode gets offlined due to hook exception
        self.server.expect(NODE,
                           {ATTR_NODE_state: 'offline',
                            ATTR_comment:
                            "offlined by hook 'h2' due to hook error"},
                           id=self.moms.values()[1].shortname,
                           interval=2, attrop=PTL_AND)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)

    def test_fail_action_startup_hook(self):
        """
        Run an exechost_startup hook that gets an
        exception when local mom is restarted. Vnode representing
        local mom would be marked offline.
        """
        mom = self.moms.values()[0]
        if mom.is_cpuset_mom():
            self.skipTest("Skipping test on cpuset moms")

        if self.is_cray is True:
            self.skipTest("Skipping test on Crays")

        # The moms provided to the test may have unwanted vnodedef files.
        if mom.has_vnode_defs():
            mom.delete_vnode_defs()

        start_time = time.time()
        self.create_multi_vnodes(1)
        self.create_bad_startup_hook()

        # Check if hook files were copied to mom
        mom.log_match(
            "h3.HK;copy hook-related file request received",
            starttime=start_time, interval=2)
        mom.log_match(
            "h3.PY;copy hook-related file request received",
            starttime=start_time, interval=2)

        mom.stop()
        mom.start()

        # primary mom's vnode gets offlined due to startup hook exception
        self.server.expect(NODE,
                           {ATTR_NODE_state: 'offline',
                            ATTR_comment:
                            "offlined by hook 'h3' due to hook error"},
                           id=mom.shortname,
                           interval=2, attrop=PTL_AND)

    def test_pbsnodes_o_single_mom(self):
        """
        Offline a mom using pbsnodes -o.
        Since it is the only mom, all vnodes reported by her
        should also be offline.
        """
        single_mom = self.moms.values()[0]
        self.create_multi_vnodes(1)
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=single_mom.shortname, interval=2)

        mom_host = single_mom.shortname
        pbs_exec = self.server.pbs_conf['PBS_EXEC']
        pbsnodes_cmd = os.path.join(pbs_exec, 'bin', 'pbsnodes')
        pbsnodes_offline = [pbsnodes_cmd, '-o', mom_host]
        self.du.run_cmd(self.server.hostname, cmd=pbsnodes_offline)

        # the mom node and all of her children should be offline
        self.server.expect(
            NODE, {ATTR_NODE_state: 'offline'},
            id=single_mom.shortname, interval=2)

        self.verify_vnodes_state('offline', [single_mom])

    @requirements(num_moms=2)
    def test_pbsnodes_o_multi_mom_only_one_offline(self):
        """
        Offline one mom using pbsnodes -o.
        In the case of multiple moms reporting the same set of vnodes,
        none of the vnodes should be marked offline,
        including the children vnodes.
        NOTE: This test needs moms to report the same set of vnodes.
        """
        if len(self.moms) != 2:
            self.skipTest("Provide 2 moms while invoking test")

        for m in self.moms.values():
            if m.is_cpuset_mom():
                self.skipTest("Skipping test on cpuset moms")

        momA = self.moms.values()[0]
        momB = self.moms.values()[1]

        # The moms provided to the test may have unwanted vnodedef files.
        if momA.has_vnode_defs():
            momA.delete_vnode_defs()
        if momB.has_vnode_defs():
            momB.delete_vnode_defs()

        self.create_multi_vnodes(2)

        # Offline only one of the moms, the other mom and her children
        # should still be free
        pbs_exec = self.server.pbs_conf['PBS_EXEC']
        pbsnodes_cmd = os.path.join(pbs_exec, 'bin', 'pbsnodes')
        pbsnodes_offline = [pbsnodes_cmd, '-o', momA.shortname]
        self.du.run_cmd(self.server.hostname, cmd=pbsnodes_offline)

        # MomA should be offline
        self.server.expect(
            NODE, {ATTR_NODE_state: 'offline'},
            id=momA.shortname, interval=2)

        # momB and the rest of the vnodes should be free
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=momB.shortname, interval=2)
        self.verify_vnodes_state('free', [momB])
        self.verify_vnodes_state('offline', [momA])

    @requirements(num_moms=2)
    def test_pbsnodes_multi_mom_offline_online(self):
        """
        When all of the moms reporting a vnode are offline,
        the vnode should also be marked offline.
        And when pbsnodes -r is used to clear the offline from at
        least one of the moms reporting a vnode, then that vnode
        should also get the offline cleared.
        Note: This test needs moms to report the same set of vnodes.
        """
        if len(self.moms) != 2:
            self.skipTest("Provide 2 moms while invoking test")

        for m in self.moms.values():
            if m.is_cpuset_mom():
                self.skipTest("Skipping test on cpuset moms")

        momA = self.moms.values()[0]
        momB = self.moms.values()[1]

        # The moms provided to the test may have unwanted vnodedef files.
        if momA.has_vnode_defs():
            momA.delete_vnode_defs()
        if momB.has_vnode_defs():
            momB.delete_vnode_defs()

        self.create_multi_vnodes(2)

        # Offline both of the moms, the vnodes reported by them
        # will also be offlined
        pbs_exec = self.server.pbs_conf['PBS_EXEC']
        pbsnodes_cmd = os.path.join(pbs_exec, 'bin', 'pbsnodes')
        pbsnodes_offline = [pbsnodes_cmd, '-o', momA.shortname, momB.shortname]
        self.du.run_cmd(self.server.hostname, cmd=pbsnodes_offline)

        # MomA and MomB should be offline
        self.server.expect(
            NODE, {ATTR_NODE_state: 'offline'},
            id=momA.shortname, interval=2)

        self.server.expect(
            NODE, {ATTR_NODE_state: 'offline'},
            id=momB.shortname, interval=2)

        self.verify_vnodes_state('offline', [momA, momB])

        # Now call pbsnodes -r to clear the offline from MomA
        pbsnodes_clear_offline = [pbsnodes_cmd, '-r', momA.shortname]
        self.du.run_cmd(self.server.hostname, cmd=pbsnodes_clear_offline)

        # MomB should still be offline
        self.server.expect(
            NODE, {ATTR_NODE_state: 'offline'},
            id=momB.shortname, interval=2)

        # momA and the vnodes she reports should be free
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=momA.shortname, interval=2)
        self.verify_vnodes_state('free', [momA])
        self.verify_vnodes_state('offline', [momB])

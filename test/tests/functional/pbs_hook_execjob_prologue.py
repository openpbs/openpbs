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
# A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
# distribute them - whether embedded or bundled with other software - under a
# commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.
from tests.functional import *


class TestPbsExecutePrologue(TestFunctional):
    """
    This tests the feature in PBS that allows execjob_prologue hook to
    execute on all sister moms all the time, and not just when first
    task is spawned on the node.

    PRE: Have a cluster of PBS with 3 mom hosts.
    """
    def setUp(self):
        if len(self.moms) != 3:
            self.skip_test(reason="need 3 mom hosts: -p moms=<m1>:<m2>:<m3>")
            return

        TestFunctional.setUp(self)

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momC = self.moms.values()[2]

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.momC.shortname

        self.server.expect(VNODE, {'state=free': 3}, op=GE, max_attempts=10,
                           interval=2)

    def test_prologue_execute_on_all_moms(self):
        """
        Test to make sure execjob_prologue always get
        executed on all sister moms when mother superior
        has successfully executed its prologue hook.
        """
        hook_name = "prologue_logmsg"
        hook_body = ("import pbs\n"
                     "e = pbs.event()\n"
                     "pbs.logjobmsg(e.job.id, 'executed prologue hook')\n")
        attr = {'event': 'execjob_prologue', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        attr = {'resources_available.ncpus': 1,
                'resources_available.mem': '2gb'}
        self.server.manager(MGR_CMD_SET, NODE, attr, id=self.hostA)
        self.server.manager(MGR_CMD_SET, NODE, attr, id=self.hostB)
        self.server.manager(MGR_CMD_SET, NODE, attr, id=self.hostC)

        attr = {'Resource_List.select': '3:ncpus=1',
                'Resource_List.place': 'scatter',
                'Resource_List.walltime': 30}
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        self.momB.log_match("Job;%s;JOIN_JOB as node" % jid, n=100,
                            max_attempts=10, interval=2)
        self.momC.log_match("Job;%s;JOIN_JOB as node" % jid, n=100,
                            max_attempts=10, interval=2)
        self.momA.log_match("Job;%s;executed prologue hook" % jid,
                            n=100, max_attempts=10, interval=2)
        self.momB.log_match("Job;%s;executed prologue hook" % jid,
                            n=100, max_attempts=10, interval=2)
        self.momC.log_match("Job;%s;executed prologue hook" % jid,
                            n=100, max_attempts=10, interval=2)

    def test_prologue_internal_error_no_fail_action(self):
        """
        Test a prologue hook with an internal error and no fail_action.
        """
        hook_name = "prologue_exception"
        hook_body = ("import pbs\n"
                     "e = pbs.event()\n"
                     "x\n")

        attr = {'event': 'execjob_prologue',
                'enabled': 'True'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        attr = {'Resource_List.select': 'vnode=%s' % self.hostA,
                'Resource_List.walltime': 30}
        j = Job(TEST_USER, attrs=attr)
        j.set_sleep_time(1)
        self.server.submit(j)

        self.server.expect(NODE, {'state': 'free'}, id=self.hostA, offset=1)

    def test_prologue_internal_error_offline_vnodes(self):
        """
        Test a prologue hook with an internal error and
        fail_action=offline_vnodes.
        """
        attr = {'resources_available.mem': '2gb',
                'resources_available.ncpus': '1'}
        self.server.create_vnodes(self.hostC, attr, 3, self.momC, delall=True,
                                  usenatvnode=True)

        hook_name = "prologue_exception"
        hook_body = ("import pbs\n"
                     "e = pbs.event()\n"
                     "x\n")
        attr = {'event': 'execjob_prologue',
                'enabled': 'True',
                'fail_action': 'offline_vnodes'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        attr = {'Resource_List.select': 'vnode=%s[0]' % self.hostC,
                'Resource_List.walltime': 30}
        j = Job(TEST_USER, attrs=attr)
        self.server.submit(j)

        attr = {'state': 'offline',
                'comment': "offlined by hook '%s' due to hook error"
                % hook_name}
        self.server.expect(VNODE, attr, id=self.hostC, max_attempts=10,
                           interval=2)
        self.server.expect(VNODE, attr, id='%s[0]' % self.hostC,
                           max_attempts=10, interval=2)
        self.server.expect(VNODE, attr, id='%s[1]' % self.hostC,
                           max_attempts=10, interval=2)

        # revert momC
        self.server.manager(MGR_CMD_SET, NODE, {'state': (DECR, 'offline')},
                            id=self.hostC)
        self.server.manager(MGR_CMD_SET, NODE, {'state': (DECR, 'offline')},
                            id='%s[0]' % self.hostC)
        self.server.manager(MGR_CMD_SET, NODE, {'state': (DECR, 'offline')},
                            id='%s[1]' % self.hostC)

        self.server.manager(MGR_CMD_UNSET, NODE, 'comment',
                            id=self.hostC)
        self.server.manager(MGR_CMD_UNSET, NODE, 'comment',
                            id='%s[0]' % self.hostC)
        self.server.manager(MGR_CMD_UNSET, NODE, 'comment',
                            id='%s[1]' % self.hostC)
        self.momC.revert_to_defaults()

    def test_prologue_hook_set_fail_action(self):
        """
        Test that fail_actions can be set on execjob_prologue
        hooks by qmgr.
        """
        hook_name = "prologue"
        hook_body = ("import pbs\n"
                     "pbs.event().accept()\n")
        attr = {'event': 'execjob_prologue',
                'enabled': 'True'}
        self.server.create_import_hook(hook_name, attr, hook_body)
        self.server.expect(HOOK, {'fail_action': 'none'})

        self.server.manager(MGR_CMD_SET, HOOK,
                            {'fail_action': 'offline_vnodes'},
                            id=hook_name)
        self.server.expect(HOOK, {'fail_action': 'offline_vnodes'})

        self.server.manager(MGR_CMD_SET, HOOK,
                            {'fail_action': 'scheduler_restart_cycle'},
                            id=hook_name)
        self.server.expect(HOOK, {'fail_action': 'scheduler_restart_cycle'},
                           id=hook_name)

    def test_prologue_hook_set_job_attr(self):
        """
        Test that a execjob_prologue hook can modify job attributes.
        """
        hook_name = "prologue_set_job_attr"
        hook_body = ("import pbs\n"
                     "pbs.event().job.resources_used['file']="
                     "pbs.size('2gb')\n")
        attr = {'event': 'execjob_prologue',
                'enabled': 'True'}
        self.server.create_import_hook(hook_name, attr, hook_body)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid = self.server.submit(j)

        attr = {'resources_used.file': '2gb'}
        self.server.expect(JOB, attr, id=jid, extend='x', offset=1)
        self.server.accounting_match(
            "E;%s;.*%s.*" % jid, 'resources_used.file=2gb', regexp=True,
            max_attempts=10)

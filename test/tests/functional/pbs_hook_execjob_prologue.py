# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
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
            "E;" + jid + ";.*resources_used.file=2gb", regexp=True,
            max_attempts=10)

    def test_prologue_hook_fail_action_non_mom_hook(self):
        """
        Test that when fail action is set to anything other than 'None' on
        a mom hook, and the mom hook event is not either execjob_begin,
        exechost_startup, execjob_prologue, an error message is dispalyed
        """
        hook_name = "prologue"
        hook_body = ("import pbs\n"
                     "pbs.event().accept()\n")
        attr = {'event': 'exechost_periodic',
                'fail_action': 'offline_vnodes'}
        try:
            self.server.create_import_hook(hook_name, attr, hook_body)
        except PbsManagerError, e:
            exp_err = "Can't set hook fail_action value to 'offline_vnodes':"
            exp_err += " hook event must"
            exp_err += " contain at least one of execjob_begin"
            exp_err += ", exechost_startup, execjob_prologue"
            self.assertTrue(exp_err in e.msg[0])

    def test_prologue_hook_does_not_execute_twice_on_pbsdsh(self):
        """
        This test creates a hook and then submits a job.
        It then uses the job output file to do a log_match
        on both the moms
        """
        hook_name = 'prologue'
        hook_body = ("import pbs\n"
                     "e = pbs.event()\n"
                     "pbs.logjobmsg(e.job.id, 'executed prologue hook')\n")
        attr = {'event': 'execjob_prologue'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        j = Job(TEST_USER, {'Resource_List.select': '2:ncpus=1',
                            'Resource_List.place': 'scatter'})
        j.create_script('#!/bin/sh\npbsdsh  hostname\nsleep 10\n')
        jid = self.server.submit(j)
        attribs = self.server.status(JOB, id=jid)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)
        host, opath = attribs[0]['Output_Path'].split(':', 1)
        ret = self.du.cat(hostname=host, filename=opath, runas=TEST_USER)
        _msg = "cat command failed with error: %s" % ret['err']
        self.assertEqual(ret['rc'], 0, _msg)
        mom1 = ret['out'][2].split(".")[0]
        mom2 = ret['out'][3].split(".")[0]
        self.exec_mom1 = self.moms[mom1]
        self.exec_mom2 = self.moms[mom2]
        self.exec_mom1.log_match("Job;%s;executed prologue hook" % jid)
        self.exec_mom2.log_match("Job;%s;executed prologue hook" % jid)

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


class TestAcctLog(TestFunctional):
    """
    Tests dealing with the PBS accounting logs
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'type': 'string', 'flag': 'h'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='foo_str')

    def test_long_resource_end(self):
        """
        Test to see if a very long string resource is neither truncated
        in the job's resources_used attr or the accounting log at job end
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

        # Create a very long string - the truncation was 2048 characters
        # 4096 is plenty big to show it

        hstr = '1'*4096
        hook_body = "import pbs\n"
        hook_body += "e = pbs.event()\n"
        hook_body += "hstr=\'" + hstr + "\'\n"
        hook_body += "e.job.resources_used[\"foo_str\"] = hstr\n"

        a = {'event': 'execjob_epilogue', 'enabled': 'True'}
        self.server.create_import_hook("ep", a, hook_body)

        J = Job()
        J.set_sleep_time(1)
        jid = self.server.submit(J)

        # Make sure the resources_used value hasn't been truncated
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        self.server.expect(
            JOB, {'resources_used.foo_str': hstr}, extend='x', max_attempts=1)

        # Make sure the accounting log hasn't been truncated
        log_match = 'resources_used.foo_str=' + hstr
        self.server.accounting_match(
            "E;%s;.*%s.*" % (jid, log_match), regexp=True)

        # Make sure the server log hasn't been truncated
        log_match = 'resources_used.foo_str=' + hstr
        self.server.log_match("%s;.*%s.*" % (jid, log_match), regexp=True)

    def test_long_resource_reque(self):
        """
        Test to see if a very long string value is truncated
        in the 'R' requeue accounting record
        """

        # Create a very long string - the truncation was 2048 characters
        # 4096 is plenty big to show it
        hstr = ""
        for i in range(4096):
            hstr += "1"

        hook_body = "import pbs\n"
        hook_body += "e = pbs.event()\n"
        hook_body += "hstr=\'" + hstr + "\'\n"
        hook_body += "e.job.resources_used[\"foo_str\"] = hstr\n"

        a = {'event': 'execjob_prologue', 'enabled': 'True'}
        self.server.create_import_hook("pr", a, hook_body)

        J = Job()
        jid = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        self.server.rerunjob(jid)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        # Make sure the accounting log hasn't been truncated
        acctlog_match = 'resources_used.foo_str=' + hstr
        self.server.accounting_match(
            "R;%s;.*%s.*" % (jid, acctlog_match), regexp=True)

    def test_queue_record(self):
        """
        Test the correct data is being printed in the queue record
        """
        t = time.time()
        a = {ATTR_g: TEST_USER.groups[0], ATTR_project: 'foo',
             ATTR_A: 'bar', ATTR_N: 'baz', ATTR_l + '.walltime': '1:00:00'}
        j1 = Job(TEST_USER, a)
        jid1 = self.server.submit(j1)

        (_, line) = self.server.accounting_match(';Q;' + jid1)

        # Check for euser
        self.assertIn('user=' + str(TEST_USER), line)

        # Check for egroup
        self.assertIn('group=' + str(TEST_USER.groups[0]), line)

        # Check for project
        self.assertIn('project=foo', line)

        # Check for account name
        self.assertIn('account=\"bar\"', line)

        # Check for job name
        self.assertIn('jobname=baz', line)

        # Check for queue
        self.assertIn('queue=workq', line)

        # Check for the existance of times
        self.assertIn('etime=', line)
        self.assertIn('ctime=', line)
        self.assertIn('qtime=', line)
        self.assertNotIn('start=', line)

        # Check for walltime
        self.assertIn('Resource_List.walltime=01:00:00', line)

        j2 = Job(TEST_USER, {ATTR_J: '1-2', ATTR_depend: 'afterok:' + jid1})
        jid2 = self.server.submit(j2)

        (_, line) = self.server.accounting_match(';Q;' + jid2)

        self.assertIn('array_indices=1-2', line)
        self.assertIn('depend=afterok:' + jid1, line)

        r = Reservation()
        rid1 = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid1)
        j3 = Job(TEST_USER, {ATTR_queue: rid1.split('.')[0]})
        jid3 = self.server.submit(j3)

        (_, line) = self.server.accounting_match(';Q;' + jid3)

        self.assertIn('resvID=' + rid1, line)

    def test_queue_record_hook(self):
        """
        Test that changes made in a queuejob hook are reflected in the Q record
        """
        qj_hook = """
import pbs
pbs.event().job.project = 'foo'
pbs.event().accept()
"""
        qj_attrs = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook('qj', qj_attrs, qj_hook)

        j = Job()
        jid1 = self.server.submit(j)

        (_, line) = self.server.accounting_match(';Q;' + jid1)
        self.assertIn('project=foo', line)

    def test_alter_record(self):
        """
        Test the accounting log alter record
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        j1 = Job(TEST_USER1)
        jid1 = self.server.submit(j1)

        # Basic test for existance of record for Resource_List
        self.server.alterjob(jid1, {ATTR_l + '.walltime': '1:00:00'})
        self.server.accounting_match(';a;' + jid1 +
                                     ';Resource_List.walltime=01:00:00')

        # Check for default value when unsetting
        self.server.manager(MGR_CMD_SET, SERVER,
                            {ATTR_rescdflt + '.walltime': '30:00'})
        self.server.alterjob(jid1, {ATTR_l + '.walltime': ''})
        self.server.accounting_match(';a;' + jid1 +
                                     ';Resource_List.walltime=00:30:00')

        self.server.alterjob(jid1, {ATTR_l + '.software': 'foo'})
        self.server.accounting_match(';a;' + jid1 +
                                     ';Resource_List.software=foo')
        # Check for UNSET record when value is unset
        self.server.alterjob(jid1, {ATTR_l + '.software': '\"\"'})
        self.server.accounting_match(';a;' + jid1 +
                                     ';Resource_List.software=UNSET')

        # Check for non-resource attribute
        self.server.alterjob(jid1, {ATTR_p: 150})
        self.server.accounting_match(';a;' + jid1 + ';Priority=150')

        self.server.alterjob(jid1, {ATTR_g: str(TSTGRP1)})
        self.server.accounting_match(';a;' + jid1 +
                                     ';group_list=' + str(TSTGRP1))

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        # Check that scheduler's alters are not logged
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.accounting_match(
            ';a;' + jid1 + ';comment', existence=False, max_attempts=2)

    def test_alter_record_hooks(self):
        """
        Test that when hooks set attributes, an 'a' record is logged
        """
        mj_hook = """
import pbs
pbs.event().job.comment = 'foo'
pbs.event().accept()
"""
        mj_attrs = {'event': 'modifyjob', 'enabled': 'True'}
        rj_hook = """
import pbs
pbs.event().job.project = 'abc'
pbs.event().reject('foo')
"""
        rj_attrs = {'event': 'runjob', 'enabled': 'True'}

        self.server.create_import_hook('mj', mj_attrs, mj_hook)
        self.server.create_import_hook('rj', rj_attrs, rj_hook)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        j1 = Job()
        jid1 = self.server.submit(j1)

        self.server.alterjob(jid1, {ATTR_p: 150})
        (_, line) = self.server.accounting_match(';a;' + jid1 + ';')
        self.assertIn('Priority=150', line)
        self.assertIn('comment=foo', line)

        try:
            self.server.runjob(jid1)
        except PbsRunError:
            # runjob hook is rejecting the run request
            pass
        self.server.accounting_match(';a;' + jid1 + ';project=abc')

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


class TestAcctlogTrunc(TestFunctional):
    """
    Test that the resources_used information doesn't get truncated
    in accounting log records
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
        hstr = ""
        for i in range(4096):
            hstr += "1"

        hook_body = "import pbs\n"
        hook_body += "e = pbs.event()\n"
        hook_body += "hstr=\'" + hstr + "\'\n"
        hook_body += "e.job.resources_used[\"foo_str\"] = hstr\n"

        a = {'event': 'execjob_epilogue', 'enabled': 'True'}
        self.server.create_import_hook("ep", a, hook_body)

        J = Job()
        J.set_attributes({ATTR_m: 'e'})
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

        # Make sure emails are not truncated
        mailfile = os.environ['MAIL']
        if not os.path.isfile(mailfile):
            self.logger.info("Mail file does not exist or mail is not setup.\
                     Hence this step would be skipped. Please check manually.")
            return 1
        mailpass = 0
        for x in range(1, 5):
            fo = open(mailfile, 'r')
            maillog = fo.readlines()[-10:]
            fo.close()
            if (log_match in str(maillog)):
                self.logger.info("Message found in " + mailfile)
                mailpass = 1
                break

        self.assertTrue(mailpass, "Message not found in " + mailfile)

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

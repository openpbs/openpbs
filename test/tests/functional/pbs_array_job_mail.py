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
import os


class Test_array_job_email(TestFunctional):
    """
    This test suite is for testing arrayjob e-mailing (parent job and subjob)
    """

    def test_emails(self):
        """
        Run arrayjob with -m jabe and test if the e-mails are received
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'true'})
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 2},
                            id=self.mom.shortname)

        mailfile = os.path.join("/var/mail", str(TEST_USER))
        if not os.path.isfile(mailfile):
            self.skip_test("Mail file '%s' does not exist or "
                           "mail is not setup. "
                           "Hence this step would be skipped. "
                           "Please check manually." % mailfile)

        J = Job(TEST_USER, attrs={ATTR_m: 'jabe', ATTR_J: '1-2'})
        J.set_sleep_time(1)
        parent_jid = self.server.submit(J)

        self.server.expect(JOB, {'job_state': 'F'}, parent_jid,
                           extend='x', max_attempts=15, interval=2)

        subjob_jid = parent_jid.replace("[]", "[1]")

        emails = [("PBS Job Id: " + parent_jid, "Begun execution"),
                  ("PBS Job Id: " + parent_jid, "Execution terminated"),
                  ("PBS Job Id: " + subjob_jid, "Begun execution"),
                  ("PBS Job Id: " + subjob_jid, "Execution terminated")]

        self.logger.info("Wait 10s for saving the e-mails")
        time.sleep(10)

        ret = self.du.cat(filename=mailfile, sudo=True)
        maillog = [x.strip() for x in ret['out'][-600:]]

        for (jobid, msg) in emails:
            emailpass = 0
            for i in range(0, len(maillog)-2):
                if jobid == maillog[i] and msg == maillog[i+2]:
                    emailpass = 1

            self.assertTrue(emailpass, "Message '" + jobid + " " + msg +
                            "' not found in " + mailfile)

    def test_qsub_errors_j_mailpoint(self):
        """
        Try to submit 'qsub -m j' and test possible errors
        """

        J = Job(TEST_USER, attrs={ATTR_m: 'j'})

        error_msg = "mail option 'j' can not be used without array job"
        try:
            self.server.submit(J)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

        J = Job(TEST_USER, attrs={ATTR_m: 'j', ATTR_J: '1-2'})

        error_msg = "illegal -m value"
        try:
            self.server.submit(J)
        except PbsSubmitError as e:
            self.assertTrue(error_msg in e.msg[0])

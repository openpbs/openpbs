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

        for (jobid, msg) in emails:
            emailpass = 0
            for j in range(5):
                time.sleep(5)
                ret = self.du.cat(filename=mailfile, sudo=True)
                maillog = [x.strip() for x in ret['out'][-600:]]
                for i in range(0, len(maillog) - 2):
                    if jobid == maillog[i] and msg == maillog[i + 2]:
                        emailpass = 1
                        break
                else:
                    continue
                break
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

    def test_email_non_existent_user(self):
        """
        Verify when a job array is submitted with a valid and invalid
        mail recipients and all file stageout attempts fails then
        email should get delivered to valid recipient and no email
        would be sent to invalid recipient.
        """
        non_existent_user = PbsAttribute.random_str(length=5)
        non_existent_mailfile = os.path.join(os.sep, "var", "mail",
                                             non_existent_user)
        pbsuser_mailfile = os.path.join(os.sep, "var", "mail",
                                        str(TEST_USER))

        # Check mail file should exist for existent user
        if not os.path.isfile(pbsuser_mailfile):
            msg = "Skipping this test as Mail file '%s' " % pbsuser_mailfile
            msg += "does not exist or mail is not setup."
            self.skip_test(msg)

        # Check non existent user mail file should not exist
        self.assertFalse(os.path.isfile(non_existent_mailfile))

        src_file = PbsAttribute.random_str(length=5)
        stageout_path = os.path.join(os.sep, '1', src_file)
        dest_file = stageout_path + '1'
        if not os.path.isdir(stageout_path) and os.path.exists(src_file):
            os.remove(src_file)

        # Submit job with invalid stageout path
        usermail_list = str(TEST_USER) + "," + non_existent_user
        set_attrib = {ATTR_stageout: stageout_path + '@' +
                      self.mom.shortname + ':' + dest_file,
                      ATTR_M: usermail_list, ATTR_J: '1-2',
                      ATTR_S: '/bin/bash'}
        j = Job()
        j.set_attributes(set_attrib)
        j.set_sleep_time(1)
        jid = self.server.submit(j)
        subjid = j.create_subjob_id(jid, 1)

        self.server.expect(JOB, 'queue', op=UNSET, id=jid)

        # Check stageout file should not be present
        self.assertFalse(os.path.exists(dest_file))

        exp_msg = "PBS Job Id: " + subjid
        err_msg = "%s msg not found in pbsuser's mail log" % exp_msg

        email_pass = 0
        for i in range(5):
            time.sleep(5)
            # Check if mail is deliverd to valid user mail file
            ret = self.du.tail(filename=pbsuser_mailfile, runas=TEST_USER,
                               option="-n 50")
            maillog = [x.strip() for x in ret['out']]
            if exp_msg in maillog:
                email_pass = 1
                break
        self.assertTrue(email_pass, err_msg)

        # Verify there should not be any email for invalid user
        self.assertFalse(os.path.isfile(non_existent_mailfile))

# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class TestExceededResourcesNotification(TestFunctional):
    """
    This test suite tests exceeding resources notification.
    The notification is done via email, job comment, and job exit code.
    """

    def setUp(self):
        TestFunctional.setUp(self)

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

    def check_mail(self, jid, msg):
        """
        Check the mail file of TEST_USER for message.
        """

        mailfile = os.path.join('/var/mail', str(TEST_USER))

        self.logger.info('Wait 3s for saving the e-mail')
        time.sleep(3)

        if not os.path.isfile(mailfile):
            self.skip_test("Mail file '%s' does not exist or "
                           "mail is not setup. "
                           "Hence this step would be skipped. "
                           "Please check manually." % mailfile)

        ret = self.du.tail(filename=mailfile, sudo=True, option='-n 10')
        maillog = [x.strip() for x in ret['out']]

        self.assertIn('PBS Job Id: ' + jid, maillog)
        self.assertIn(msg, maillog)

    def test_exceeding_walltime(self):
        """
        This test suite tests exceeding walltime.
        """

        a = {'Resource_List.walltime': 1}
        j = Job(TEST_USER, a)

        j.set_sleep_time(60)

        jid = self.server.submit(j)
        j_comment = '.* and exceeded resource walltime'
        self.server.expect(JOB, {ATTR_state: 'F',
                                 ATTR_comment: (MATCH_RE, j_comment),
                                 ATTR_exit_status: -29},
                           id=jid, extend='x')

        msg = 'Job exceeded resource walltime'
        self.check_mail(jid, msg)

    def test_exceeding_mem(self):
        """
        This test suite tests exceeding memory.
        """

        self.mom.add_config({'$enforce mem': ''})

        self.mom.stop()
        self.mom.start()

        a = {'Resource_List.walltime': 3600,
             'Resource_List.select': 'mem=1kb'}
        j = Job(TEST_USER, a)

        test = []
        test += ['#!/bin/bash']
        test += ['tail -c 100K /dev/zero']
        j.create_script(body=test)

        jid = self.server.submit(j)
        j_comment = '.* and exceeded resource mem'
        self.server.expect(JOB, {ATTR_state: "F",
                                 ATTR_comment: (MATCH_RE, j_comment),
                                 ATTR_exit_status: -27},
                           id=jid, extend='x')

        msg = 'Job exceeded resource mem'
        self.check_mail(jid, msg)

    def test_exceeding_ncpus_sum(self):
        """
        This test suite tests exceeding ncpus (sum).
        """

        self.mom.add_config(
            {'$enforce average_percent_over': '0',
             '$enforce average_cpufactor': '0.1',
             '$enforce average_trialperiod': '1',
             '$enforce cpuaverage': ''})

        self.mom.stop()
        self.mom.start()

        a = {'Resource_List.walltime': 3600}
        j = Job(TEST_USER, a)

        test = []
        test += ['#!/bin/bash']
        test += ['dd if=/dev/zero of=/dev/null']
        j.create_script(body=test)

        jid = self.server.submit(j)
        j_comment = '.* and exceeded resource ncpus \(sum\)'
        self.server.expect(JOB, {ATTR_state: 'F',
                                 ATTR_comment: (MATCH_RE, j_comment),
                                 ATTR_exit_status: -25},
                           id=jid, extend='x')

        msg = 'Job exceeded resource ncpus (sum)'
        self.check_mail(jid, msg)

    def test_exceeding_ncpus_burst(self):
        """
        This test suite tests exceeding ncpus (burst).
        """

        self.mom.add_config(
            {'$enforce delta_percent_over': '0',
             '$enforce delta_cpufactor': '0.1',
             '$enforce cpuburst': ''})

        self.mom.stop()
        self.mom.start()

        a = {'Resource_List.walltime': 3600}
        j = Job(TEST_USER, a)

        test = []
        test += ['#!/bin/bash']
        test += ['dd if=/dev/zero of=/dev/null']
        j.create_script(body=test)

        jid = self.server.submit(j)
        j_comment = '.* and exceeded resource ncpus \(burst\)'
        self.server.expect(JOB, {ATTR_state: 'F',
                                 ATTR_comment: (MATCH_RE, j_comment),
                                 ATTR_exit_status: -24},
                           id=jid, extend='x')

        msg = 'Job exceeded resource ncpus (burst)'
        self.check_mail(jid, msg)

    def test_exceeding_cput(self):
        """
        This test suite tests exceeding cput.
        """

        a = {'Resource_List.cput': 10}
        j = Job(TEST_USER, a)

        # we need at least two processes otherwise the kernel
        # would kill the process first
        test = []
        test += ['#!/bin/bash']
        test += ['dd if=/dev/zero of=/dev/null & \
dd if=/dev/zero of=/dev/null']
        j.create_script(body=test)

        jid = self.server.submit(j)
        j_comment = '.* and exceeded resource cput'
        self.server.expect(JOB, {ATTR_state: 'F',
                                 ATTR_comment: (MATCH_RE, j_comment),
                                 ATTR_exit_status: -28},
                           id=jid, extend='x')

        msg = 'Job exceeded resource cput'
        self.check_mail(jid, msg)

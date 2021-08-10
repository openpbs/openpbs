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


class TestMomJobDir(TestFunctional):
    """
    This test suite tests the mom's ability to create job directories.
    """

    def change_server_name(self, servername):
        """
        Stops the server, changes the server name to `servername`,
        sets the server hostname to the old servername,
        and starts the server again.
        """
        self.server.stop()
        self.assertFalse(self.server.isUp(), 'Failed to stop PBS')

        conf = self.du.parse_pbs_config(self.server.hostname)
        self.du.set_pbs_config(
            self.server.hostname,
            confs={'PBS_SERVER_HOST_NAME': conf['PBS_SERVER'],
                   'PBS_SERVER': servername})

        self.server.start()
        self.assertTrue(self.server.isUp(), 'Failed to start PBS')
        return

    def test_existing_directory_longid(self):
        """
        If a job directory already exists, the mom should clean it up
        after rejecting the job. When the server sends the request for
        the second time, the mom will run the job correctly.
        The mom has special code if the job id is less than 11 characters,
        so this will test job ids longer than 11 characters.
        """

        # Change the server name to create a job id longer than 11 characters
        self.change_server_name('superlongservername')

        j = Job(TEST_USER, attrs={ATTR_h: None})
        j.set_sleep_time(3)
        jid = self.server.submit(j)

        # Create the job directory in mom_priv
        path = self.mom.get_formed_path(self.mom.pbs_conf['PBS_HOME'],
                                        'mom_priv', 'jobs', jid + '.TK')
        self.logger.info('Creating directory %s', path)
        self.du.mkdir(hostname=self.mom.hostname, path=path, sudo=True)

        # Rls the job, ensure it finishes and the directory no longer exists
        self.server.rlsjob(jid, USER_HOLD)
        self.server.expect(JOB, 'queue', id=jid, op=UNSET, max_attempts=20,
                           interval=1, offset=1)
        ret = self.du.isdir(hostname=self.mom.hostname, path=path, sudo=True)
        self.assertFalse(ret, 'Directory %s still exists.' % path)

    def test_existing_directory_shortid(self):
        """
        If a job directory already exists, the mom should clean it up
        after rejecting the job. When the server sends the request for
        the second time, the mom will run the job correctly.
        The mom has special code if the job id is less than 11 characters,
        so this will test job ids shorter than 11 characters.
        """

        # Change the server name to create a job id shorter than 11 characters
        self.change_server_name('svr')

        # Submit a held job so the job id is known
        j = Job(TEST_USER, attrs={ATTR_h: None})
        j.set_sleep_time(3)
        jid = self.server.submit(j)

        # Create the job directory in mom_priv
        path = self.mom.get_formed_path(self.mom.pbs_conf['PBS_HOME'],
                                        'mom_priv', 'jobs', jid + '.TK')
        self.logger.info('Creating directory %s', path)
        self.du.mkdir(hostname=self.mom.hostname, path=path, sudo=True)

        # Rls the job, ensure it finishes and the directory no longer exists
        self.server.rlsjob(jid, USER_HOLD)
        self.server.expect(JOB, 'queue', id=jid, op=UNSET, max_attempts=20,
                           interval=1, offset=1)
        ret = self.du.isdir(hostname=self.mom.hostname, path=path, sudo=True)
        self.assertFalse(ret, 'Directory %s still exists.' % path)

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

from tests.security import *


class Test_job_security(TestSecurity):
    """
    This test suite is for testing job security
    """

    def setUp(self):
        TestSecurity.setUp(self)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

    def test_interactive_job_env_V(self):
        """
        This test checks if the PBS job related cookies are passed on to
        the job that is submitted within the interactive job with -V.
        """
        self.pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")
        j = Job(TEST_USER)
        set_attr = {ATTR_inter: ''}
        j.set_attributes(set_attr)
        j.interactive_script = [('export PATH=$PATH:%s' %
                                 self.exec_path, '.*'),
                                ('qsub -V -- /bin/sleep 5', '.*'),
                                ('sleep 30', '.*')]
        jid = self.server.submit(j)
        jid2 = str(int(jid.split('.')[0]) + 1)
        self.server.expect(JOB, {'job_state=R': 2}, count=True)
        stat = self.server.status(JOB, id=jid2, extend='x')
        for s in stat:
            variable_list = s.get('Variable_List', '')
            if 'PBS_JOBCOOKIE' in variable_list or 'PBS_INTERACTIVE_COOKIE' in variable_list:
                self.fail("Job Cookie(s) passed on to the inner job.")

    def test_interactive_job_env_v(self):
        """
        This test checks if the PBS job related cookies are passed on to
        the job that is submitted within the interactive job
        with -v PBS_JOBCOOKIE.
        """
        self.pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")
        j = Job(TEST_USER)
        set_attr = {ATTR_inter: ''}
        j.set_attributes(set_attr)
        j.interactive_script = [('export PATH=$PATH:%s' %
                                 self.exec_path, '.*'),
                                ('qsub -v PBS_JOBCOOKIE -- /bin/sleep 5', '.*'),
                                ('sleep 30', '.*')]
        jid = self.server.submit(j)
        jid2 = str(int(jid.split('.')[0]) + 1)
        self.server.expect(JOB, {'job_state=R': 2}, count=True)
        stat = self.server.status(JOB, id=jid2, extend='x')
        for s in stat:
            variable_list = s.get('Variable_List', '')
            if 'PBS_JOBCOOKIE' in variable_list or 'PBS_INTERACTIVE_COOKIE' in variable_list:
                self.fail("Job Cookie(s) passed on to the inner job.")

    def tearDown(self):
        TestSecurity.tearDown(self)

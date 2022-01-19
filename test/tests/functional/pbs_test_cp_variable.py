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
import time


class Test_PBS_CP_Variable(TestFunctional):
    """
    This test suite tests local file transfer commands via PBS_CP variable
    """

    def setUp(self):
        TestFunctional.setUp(self)

    def test_PBSCP_with_dir_permission(self):
        """
        This test to include default PBS_CP path, wrong PBS_SCP path in pbs.conf and and Submit a job from directory where we have permission to 
        copy output files and observe stage out message in momlogs
        """
        conf = {'PBS_CP': '/bin/cp','PBS_SCP': '/tmp/scp'}
        self.du.set_pbs_config(hostname=self.server.hostname, confs=conf)
        self.server.manager(MGR_CMD_SET, SERVER, {'job_history_enable': 'True'})
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid=self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        output_path = self.server.status(JOB, id=jid, extend='x')[0]['Output_Path'].split(':')[1] 
        rv = self.du.isfile(hostname=self.server.hostname, path=output_path)
        _msg = "File is not present"
        self.assertTrue(rv, _msg)
        exp_msg = "Staged 2/2 items out"
        self.mom.log_match(exp_msg)

    def test_PBSCP_without_dir_permission(self):
        """
        This test to include default PBS_CP path, wrong PBS_SCP path in pbs.conf and Submit a job from directory where we don’t have permission to 
        copy output files and check failure messages related to copy command in momlogs
        """
        conf = {'PBS_CP': '/bin/cp','PBS_SCP': '/tmp/scp'}
        self.du.set_pbs_config(hostname=self.server.hostname, confs=conf)
        self.server.manager(MGR_CMD_SET, SERVER, {'job_history_enable': 'True'})
        sub_dir=self.du.create_temp_dir(asuser=TEST_USER2)
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid=self.server.submit(j,submit_dir=sub_dir)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        output_path = self.server.status(JOB, id=jid, extend='x')[0]['Output_Path']
        rv = self.du.isfile(hostname=self.server.hostname, path=output_path)
        _msg = "File is present"
        self.assertFalse(rv, _msg)
        exp_msg = "Job files not copied"
        self.mom.log_match(exp_msg)


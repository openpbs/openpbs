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


class TestJobPurge(TestFunctional):
    """
    This test suite tests the Job purge process
    """

    def test_job_files_after_execution(self):
        """
        Checks the job related files and ensures that files are
        deleted successfully upon job completion
        """
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        jobs_dir_path = os.path.join(
            self.server.pbs_conf['PBS_HOME'], 'mom_priv', 'jobs/')
        # Submit a normal and an array job
        j = Job(TEST_USER)
        j.create_script(body="sleep 5")
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid)
        j1 = Job(TEST_USER)
        j1.create_script(body="sleep 5")
        j1.set_attributes({ATTR_J: '1-2'})
        jid_1 = self.server.submit(j1)
        jobid_list = [jid, j1.create_subjob_id(jid_1, 1),
                      j1.create_subjob_id(jid_1, 2)]
        self.server.expect(JOB, {'job_state': 'B'}, id=jid_1)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid_1)
        # Checking the job control(.JB) file, job script(.SC) file
        # and job task(.TK) directory after successful job execution
        jobs_suffix_list = ['.JB', '.SC', '.TK']
        for jobid in jobid_list:
            for suffix in jobs_suffix_list:
                job_file = jobs_dir_path + jobid + suffix
                self.assertFalse(self.du.isfile(path=job_file, sudo=True))

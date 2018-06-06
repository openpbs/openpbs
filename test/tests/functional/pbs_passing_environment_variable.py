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


class Test_passing_environment_variable_via_qsub(TestFunctional):
    """
    Test to check passing environment variables via qsub
    """

    def test_commas_in_custom_variable(self):
        """
        Submit a job with -v "var1='A,B,C,D'" and check that the value
        is passed correctly
        """
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 10}
        script = ['#PBS -v "var1=\'A,B,C,D\'"']
        script += ['env | grep var1']
        j = Job(TEST_USER, attrs=a)
        j.create_script(body=script)
        jid = self.server.submit(j)

        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_ofile = qstat[0][ATTR_o].split(':')[1]

        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        job_output = ""
        with open(job_ofile, 'r') as f:
            job_output = f.read().strip()

        self.assertEqual(job_output, "var1=A,B,C,D")

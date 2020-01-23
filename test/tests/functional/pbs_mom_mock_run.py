# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class TestMomMockRun(TestFunctional):
    def test_rsc_used(self):
        """
        Test that resources_used are set correctly by mom under mock run
        """
        # Kill the existing mom process
        self.mom.stop()

        # Start mom in mock run mode
        mompath = os.path.join(self.server.pbs_conf["PBS_EXEC"], "sbin",
                               "pbs_mom")
        cmd = [mompath, "-m"]
        self.du.run_cmd(cmd=cmd, sudo=True)

        # Submit a job requesting ncpus, mem and walltime
        attr = {ATTR_l + ".select": "1:ncpus=1:mem=5mb",
                ATTR_l + ".walltime": "00:00:05"}
        j = Job(attrs=attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # This job should end in 5 seconds, let's sleep
        time.sleep(7)

        # Check accounting record for this job
        used_ncpus = "resources_used.ncpus=1"
        self.server.accounting_match(msg=used_ncpus, id=jid)
        used_mem = "resources_used.mem=5mb"
        self.server.accounting_match(msg=used_mem, id=jid)
        used_walltime = "resources_used.walltime=00:00:05"
        self.server.accounting_match(msg=used_walltime, id=jid)

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


@skipOnCpuSet
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
        self.du.run_cmd(hosts=self.mom.shortname, cmd=cmd, sudo=True)

        # Submit a job requesting ncpus, mem and walltime
        attr = {ATTR_l + ".select": "1:ncpus=1:mem=5mb",
                ATTR_l + ".walltime": "00:00:20"}
        j = Job(attrs=attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info("Waiting until job finishes")
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=22)

        # Check accounting record for this job
        used_ncpus = "resources_used.ncpus=1"
        self.server.accounting_match(msg=used_ncpus, id=jid, n='ALL')
        used_mem = "resources_used.mem=5mb"
        self.server.accounting_match(msg=used_mem, id=jid, n='ALL')
        used_walltime = "resources_used.walltime=00:00:00"
        self.server.accounting_match(
            msg="resources_used.walltime", id=jid, n='ALL')
        self.server.accounting_match(
            msg=used_walltime, existence=False, id=jid,
            max_attempts=1, n='ALL')

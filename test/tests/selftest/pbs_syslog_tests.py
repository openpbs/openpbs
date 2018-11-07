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

from tests.selftest import *


class TestSyslog(TestSelf):
    """
    Test pbs syslog logging
    """

    def setup_syslog(self, hostname=None, local_log=None, syslog_facility=None, syslog_severity=None):
        """
        Setup syslog in pbs.conf
        """
        a = {'PBS_SYSLOG': syslog_facility, 'PBS_SYSLOGSEVR': syslog_severity, 'PBS_LOCALLOG': local_log}
        self.du.set_pbs_config(hostname=hostname, confs=a, append=True)
        PBSInitServices().restart()
        self.assertTrue(self.server.isUp(), 'Failed to restart PBS Daemons')

    def test_basic_syslog_match(self):
        """
        Basic test to check if logging via syslog works
        Each individaul daemon is logged seperately
        :return:
        """
        self.setup_syslog(local_log=0, syslog_facility=9, syslog_severity=7)
        a = {'Resource_List.ncpus': 1}
        J1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        str = "Job;" + jid1 + ";Job Run at request of Scheduler"
        self.server.log_match(str, n=500)

    def test_basic_syslog_severity(self):
        """
        Test that that PBS logs messages via syslog
        according to the set priority
        :return:
        """
	self.t = int(time.time())
        self.setup_syslog(local_log=0, syslog_facility=9, syslog_severity=6)
        a = {'Resource_List.ncpus': 1}
        J1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        str = "Job;" + jid1 + ";Considering job to run"
        #self.scheduler.log_match(str, n=500, max_attempts=10)
        with self.assertRaises(PtlLogMatchError):
            self.scheduler.log_match(str, n=500, max_attempts=10, starttime=self.t)
        #self.assertTrue("Log File to check is not set", self.scheduler.log_match(str, n=100, starttime=self.t))
        self.server.deljob(jid1, wait=True)
        self.setup_syslog(local_log=0, syslog_facility=9, syslog_severity=7)
        J2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        str = "Job;" + jid2 + ";Considering job to run"
        self.scheduler.log_match(str, n=500, max_attempts=10)



    def test_muti_host_syslog_match(self):
        """
        Test that syslog matching works on a multihost system
        :return:
        """
        self.setup_syslog(local_log=0, syslog_facility=9, syslog_severity=7)
        if len(self.moms) != 2:
            self.skip_test(reason="need 2 mom hosts: -p moms=<m1>:<m2>")

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        attr = {'Resource_List.select': '2:ncpus=1'}
        j = Job(TEST_USER, attrs=attr)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        str = "Job; " + jid1 + ";Started"
        self.momA.log_match(str, starttime=self.t, n=200)
        self.momB.log_match(str, starttime=self.t, n=200)


    def test_local_and_syslog_match(self):
        """
        Test that local logging and sylog logging can work simultaneously
        """
        self.setup_syslog(local_log=1, syslog_facility=9, syslog_severity=7)
        self.t = int(time.time())
        a = {'Resource_List.ncpus': 1}
        J1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J1)
        # self.server.log_match(jid2,
        #                      max_attempts=1)
        str = "Job;" + jid1 + ";Job Queued at request of "
        self.server.log_match(str,
                              max_attempts=1, starttime=self.t, n=200)

    def tearDown(self):
        confs = self.du.parse_pbs_config()
        print("confs is: " + str(confs))
        if 'PBS_SYSLOG' in confs:
            del confs['PBS_SYSLOG']
        if 'PBS_SYSLOGSEVR' in confs:
            del confs['PBS_SYSLOGSEVR']
        if 'PBS_LOCALLOG' in confs:
            del confs['PBS_LOCALLOG']

        self.du.set_pbs_config(confs=confs, append=False)
        PBSInitServices().restart()
        PBSTestSuite.tearDown(self)

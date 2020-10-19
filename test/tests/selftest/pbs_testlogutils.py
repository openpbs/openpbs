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


from tests.selftest import *
from ptl.utils.pbs_logutils import PBSLogUtils


class TestLogUtils(TestSelf):
    """
    Test PBSLogUtils functionality in PTL
    """

    def switch_microsecondlogging(self, hostname=None, highrestimestamp=1):
        """
        Set microsecond logging in pbs.conf
        """
        if hostname is None:
            hostname = self.server.hostname
        a = {'PBS_LOG_HIGHRES_TIMESTAMP': highrestimestamp}
        self.du.set_pbs_config(hostname=hostname, confs=a, append=True)
        PBSInitServices().restart()
        self.assertTrue(self.server.isUp(), 'Failed to restart PBS Daemons')

    def test_log_match_microsec_logging(self):
        """
        Test that log_match will work when microsecond logging
        is turned on and then off
        """
        # Turn of microsecond logging and test log_match()
        self.switch_microsecondlogging(highrestimestamp=1)
        a = {'Resource_List.ncpus': 1}
        J1 = Job(TEST_USER, attrs=a)
        st = time.time()
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        msg_str = "Job;" + jid1 + ";Job Run at request of Scheduler"
        et = time.time()
        self.server.log_match(msg_str, starttime=st, endtime=et)
        self.server.deljob(jid1, wait=True)

        # Turn off microsecond logging and test log_match()
        st = int(time.time())
        self.switch_microsecondlogging(highrestimestamp=0)
        a = {'Resource_List.ncpus': 1}
        J2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        et = int(time.time())
        msg_str = "Job;" + jid2 + ";Job Run at request of Scheduler"
        self.server.log_match(msg_str, starttime=st, endtime=et)

    def test_get_timestamps(self):
        """
        test that LogUtils.get_timestamps() works correctly
        """
        # Submit a 1 cpu job, this will create some accounting records
        a = {'Resource_List.ncpus': 1}
        j = Job(attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        acctpath = os.path.join(self.server.pbs_conf["PBS_HOME"],
                                "server_priv", "accounting")
        self.assertTrue(self.du.isdir(self.server.hostname, acctpath,
                                      sudo=True))
        logs = self.du.listdir(self.server.hostname, acctpath, sudo=True)
        log_today = sorted(logs, reverse=True)[0]
        self.assertTrue(self.du.isfile(self.server.hostname, acctpath,
                                       sudo=True))

        # Call LogUtils.get_timestamps() for today's accounting log file
        lu = PBSLogUtils()
        tm = lu.get_timestamps(log_today, self.server.hostname, num=1,
                               sudo=True)
        self.assertIsNotNone(tm)
        self.assertEqual(len(tm), 1)

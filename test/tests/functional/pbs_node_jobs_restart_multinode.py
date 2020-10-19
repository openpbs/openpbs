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
from time import sleep


@requirements(num_moms=2)
class TestMultiNodeJobsRestart(TestFunctional):
    """
    Make sure that jobs remain active after node restart
    """

    def test_restart_hosts_resume(self):

        if len(self.moms) != 2:
            self.skipTest("test requires atleast two MoMs as input, " +
                          "use -p moms=<mom1:mom2>")
        momA = self.moms.values()[0]
        momB = self.moms.values()[1]

        # Make sure moms are running with -p flag
        momA.restart(args=['-p'])
        momB.restart(args=['-p'])

        pbsdsh_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                   "bin", "pbsdsh")
        script = "sleep 30 && %s echo 'Hello, World'" % pbsdsh_path
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2',
                          'Resource_List.place': 'scatter'})
        j.create_script(script)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        momA.restart(args=['-p'])
        momB.restart(args=['-p'])

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        sleep(60)

        self.server.log_match("%s;Exit_status=0" % jid)

        # Restart moms without -p flag
        momA.restart()
        momB.restart()

    def test_restart_hosts_resume_withoutp(self):

        if len(self.moms) != 2:
            self.skipTest("test requires atleast two MoMs as input, " +
                          "use -p moms=<mom1:mom2>")
        momA = self.moms.values()[0]
        momB = self.moms.values()[1]

        # Make sure moms are running with -p flag
        momA.restart(args=[])
        momB.restart(args=[])

        pbsdsh_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                   "bin", "pbsdsh")
        script = "sleep 30 && %s echo 'Hello, World'" % pbsdsh_path
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2',
                          'Resource_List.place': 'scatter'})
        j.create_script(script)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        momA.restart(args=['-p'])
        momB.restart(args=['-p'])

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        sleep(60)

        self.server.log_match("%s;Exit_status=0" % jid)

        # Restart moms without -p flag
        momA.restart()
        momB.restart()

    def test_premature_kill_restart(self):

        if len(self.moms) != 2:
            self.skipTest("test requires atleast two MoMs as input, " +
                          "use -p moms=<mom1:mom2>")
        momA = self.moms.values()[0]
        momB = self.moms.values()[1]

        # Make sure moms are running with -p flag
        momA.restart(args=['-p'])
        momB.restart(args=['-p'])

        pbsdsh_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                   "bin", "pbsdsh")
        script = "sleep 30 && %s echo 'Hello, World'" % pbsdsh_path
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2',
                          'Resource_List.place': 'scatter'})
        j.create_script(script)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        momA.signal("-KILL")
        momB.signal("-KILL")
        sleep(5)
        momA.start(args=['-p'])
        momB.start(args=['-p'])

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        sleep(55)

        self.server.log_match("%s;Exit_status=0" % jid)

        # Restart moms without -p flag
        momA.restart()
        momB.restart()

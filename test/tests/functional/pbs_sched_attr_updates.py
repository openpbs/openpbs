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


class TestSchedAttrUpdates(TestFunctional):

    def test_basic_throttling(self):
        """
        Test the behavior of sched's 'attr_update_period' attribute
        """
        self.server.manager(MGR_CMD_SET, NODE,
                            {"resources_available.ncpus": 1},
                            id=self.mom.shortname)

        jid1 = self.server.submit(Job())
        jid2 = self.server.submit(Job())

        self.server.expect(JOB, {"job_state": "R"}, id=jid1)
        self.server.expect(JOB, {"job_state": "Q"}, id=jid2)
        self.server.expect(JOB, "comment", op=SET, id=jid2)

        self.server.cleanup_jobs()

        a = {"attr_update_period": 45, "scheduling": "False"}
        self.server.manager(MGR_CMD_SET, SCHED, a, id="default")

        self.server.submit(Job())
        jid4 = self.server.submit(Job())

        self.scheduler.run_scheduling_cycle()

        # Scheduler should send attr updates in the first cycle
        # after attr_update_period is set
        self.server.expect(JOB, "comment", op=SET, id=jid4)

        jid5 = self.server.submit(Job())
        jid6 = self.server.submit(Job())

        t = time.time()
        self.scheduler.run_scheduling_cycle()

        # Verify that scheduler didn't send attr updates for new jobs
        self.server.expect(JOB, "comment", op=UNSET, id=jid5)
        self.server.expect(JOB, "comment", op=UNSET, id=jid6)
        self.server.log_match("Type 96 request received", existence=False,
                              starttime=t, max_attempts=5)

        self.logger.info("Sleep for 45s for the attr_update_period to pass")
        time.sleep(45)
        jid7 = self.server.submit(Job())
        jid8 = self.server.submit(Job())

        t = time.time()
        self.scheduler.run_scheduling_cycle()

        # Verify that scheduler sent attr updates for all new jobs
        self.server.expect(JOB, "comment", op=SET, id=jid7)
        self.server.expect(JOB, "comment", op=SET, id=jid8)
        self.server.log_match("Type 96 request received", starttime=t)

    def test_accrue_type(self):
        """
        Test that accrue_type updates are sent immediately
        """
        self.server.manager(MGR_CMD_SET, NODE,
                            {"resources_available.ncpus": 1},
                            id=self.mom.shortname)

        a = {"attr_update_period": 600, "scheduling": "False"}
        self.server.manager(MGR_CMD_SET, SCHED, a, id="default")

        j = Job()
        j.set_sleep_time(1000)
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(Job())

        self.scheduler.run_scheduling_cycle()
        self.server.expect(JOB, {"job_state": "R"}, id=jid1)
        self.server.expect(JOB, {"job_state": "Q"}, id=jid2)
        self.server.expect(JOB, "comment", op=SET, id=jid2)

        jid3 = self.server.submit(Job())
        self.scheduler.run_scheduling_cycle()
        self.server.expect(JOB, "comment", op=UNSET, id=jid3)

        # Now, turn eligible time on and add a limit that'll be crossed
        # by the user, this will trigger an accrue_type update from sched
        a = {"eligible_time_enable": "True"}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run_res.ncpus': '[u:PBS_GENERIC=1]'})

        # We should still be within the throttling window
        # But, because accrue_type needed to be sent out,
        # sched will send all updates for the jobs
        jid4 = self.server.submit(Job())
        self.scheduler.run_scheduling_cycle()
        self.server.expect(JOB, "comment", op=SET, id=jid4, max_attempts=1)
        self.server.expect(JOB, {"accrue_type": "1"}, id=jid4, max_attempts=1)
        self.server.expect(JOB, "comment", op=SET, id=jid3, max_attempts=1)
        self.server.expect(JOB, {"accrue_type": "1"}, id=jid3, max_attempts=1)
        self.server.expect(JOB, {"accrue_type": "1"}, id=jid2, max_attempts=1)

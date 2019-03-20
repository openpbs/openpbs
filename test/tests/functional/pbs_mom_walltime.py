# coding: utf-8

# Copyright (C) 1994-2019 Altair Engineering, Inc.
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
from ptl.lib.pbs_testlib import BatchUtils


class TestMomWalltime(TestFunctional):

    def test_mom_hook_not_counted_in_walltime(self):
        """
        Test that time spent on mom hooks is not counted in walltime of the job
        """
        hook_name_event_dict = {
            'begin': 'execjob_begin',
            'prologue': 'execjob_prologue',
            'launch': 'execjob_launch',
            'epilogue': 'execjob_epilogue',
            'preterm': 'execjob_preterm',
            'end': 'execjob_end'
        }
        hook_script = (
            "import pbs\n"
            "import time\n"
            "time.sleep(2)\n"
            "pbs.event().accept\n"
        )
        hook_attrib = {'event': '', 'enabled': 'True'}
        for name, event in hook_name_event_dict.items():
            hook_attrib['event'] = event
            self.server.create_import_hook(name, hook_attrib, hook_script)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})
        job = Job(TEST_USER)
        job.set_sleep_time(3)
        jid = self.server.submit(job)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid, extend='x',
                           offset=15)
        self.server.expect(JOB, {'resources_used.walltime': 5}, op=LE, id=jid,
                           extend='x')

    def test_hold_time_not_counted_in_walltime(self):
        """
        Test that hold time is not counted in walltime
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})

        a = {'Resource_List.ncpus': 1}
        J1 = Job(TEST_USER, attrs=a)
        J1.set_sleep_time(60)
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        # Wait for job to run for sometime
        time.sleep(15)
        self.server.expect(JOB, {'resources_used.walltime': 0}, op=GT, id=jid1,
                           extend='x')

        self.server.holdjob(jid1, USER_HOLD)
        self.server.rerunjob(jid1)
        self.server.expect(JOB, {'Hold_Types': 'u'}, jid1)
        # Wait for sometime to verify that this time is not
        # accounted in 'resource_used.walltime'
        time.sleep(20)
        self.server.rlsjob(jid1, USER_HOLD)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid1, extend='x',
                           offset=45)
        # Verify if the job's walltime is in between 60 to 70
        self.server.expect(JOB, {'resources_used.walltime': 60}, op=GE,
                           id=jid1, extend='x')
        self.server.expect(JOB, {'resources_used.walltime': 70}, op=LE,
                           id=jid1, extend='x')

    def test_suspend_time_not_counted_in_walltime(self):
        """
        Test that suspend time is not counted in walltime
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'True'})
        a = {'Resource_List.ncpus': 1}

        script_content = (
            'for i in {1..30}\n'
            'do\n'
            '\techo "time wait"\n'
            '\tsleep 1\n'
            'done'
        )

        J1 = Job(TEST_USER, attrs=a)
        J1.create_script(body=script_content)
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        # Accumulate wall time
        time.sleep(10)

        self.server.sigjob(jobid=jid1, signal="suspend")
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)

        # Make sure the sched cycle is completed before reading
        # the walltime
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        jstat = self.server.status(JOB, id=jid1,
                                   attrib=['resources_used.walltime'])
        walltime = BatchUtils().convert_duration(
            jstat[0]['resources_used.walltime'])
        self.logger.info("Walltime before sleep: %d secs" % walltime)
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})

        # Sleep for the job's entire walltime secs so we can catch any
        # walltime increment during job suspension time
        self.logger.info("Suspending job for 30s, job's execution time. " +
                         "Walltime should not get incremented while job " +
                         "is suspended")
        time.sleep(30)

        # Used walltime should remain the same
        self.server.expect(JOB, {'resources_used.walltime': walltime}, op=EQ,
                           id=jid1)

        self.server.sigjob(jobid=jid1, signal="resume")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid1, extend='x',
                           offset=20)

        # Verify if the job's total walltime is within limits
        # Adding 10s buffer since min mom poll time is 10s
        jstat = self.server.status(JOB, id=jid1,
                                   attrib=['resources_used.walltime'],
                                   extend='x')
        walltime_final = BatchUtils().convert_duration(
            jstat[0]['resources_used.walltime'])
        self.assertGreater(walltime_final, 0,
                           'Error fetching resources_used.walltime value')
        self.logger.info("Walltime at job completion: %d secs"
                         % walltime_final)
        self.assertIn(walltime_final, range(25, 41),
                      'Walltime is not in expected range')

    def test_mom_restart(self):
        """
        Test that time spent on jobs running on MoM will not reset when
        MoM is restarted
        """
        job = Job(TEST_USER)
        job.set_sleep_time(300)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        self.server.expect(JOB, {'resources_used.walltime': 30}, op=GT,
                           id=jid, offset=30)

        self.mom.stop(sig='-INT')
        self.mom.start(args=['-p'])

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        try:
            self.assertFalse(
                self.server.expect(JOB, {'resources_used.walltime': 30},
                                   op=LT, id=jid, max_attempts=5, interval=5))
        except PtlExpectError:
            pass

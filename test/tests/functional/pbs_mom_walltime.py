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
            'for i in {1..10}\n'
            'do\n'
            '\techo "time wait"\n'
            '\tsleep 1\n'
            'done'
        )

        J1 = Job(TEST_USER, attrs=a)
        J1.create_script(body=script_content)
        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        self.server.sigjob(jobid=jid1, signal="suspend")
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)

        time.sleep(15)
        self.server.sigjob(jobid=jid1, signal="resume")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        self.server.expect(JOB, {ATTR_state: 'F'}, id=jid1, extend='x',
                           offset=5)

        # Used walltime should be less than the sleep time after suspend
        self.server.expect(JOB, {'resources_used.walltime': 10}, op=LE,
                           id=jid1, extend='x')

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

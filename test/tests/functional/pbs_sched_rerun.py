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


class TestSchedRerun(TestFunctional):
    """
    Tests to verify scheduling of rerun jobs.
    """

    @requirements(num_moms=2)
    def test_rerun_job_over_reservation(self):
        """
        Test that job will not run over reservation/top job
        after first failed attempt to run (with used resource set).
        """
        now = int(time.time())

        usage_string = 'test requires two moms,' + \
                       'use -p "servers=M1,moms=M1:M2"'

        if len(self.moms.values()) != 2:
            self.skip_test(usage_string)

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        if not self.hostA or not self.hostB:
            self.skip_test(usage_string)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (INCR, '%s@*' % TEST_USER)})

        a = {'type': 'long', 'flag': 'i'}
        r = 'foo'
        self.server.manager(MGR_CMD_CREATE, RSC, a, id=r)

        hook_body = f"""
import pbs
e = pbs.event()
if e.type == pbs.EXECJOB_BEGIN:
    e.job.resources_used["foo"] = 123
    if e.job.run_count == 1:
        for v in e.vnode_list:
            if v == "{self.hostA}":
                e.vnode_list[v].state = pbs.ND_OFFLINE
        e.job.rerun()
        e.reject("rerun job")
e.accept()
"""

        hook_name = "rerun_job"
        a = {'event': 'execjob_begin',
             'enabled': 'True'}
        rv = self.server.create_import_hook(
            hook_name, a, hook_body, overwrite=True)
        self.assertTrue(rv)

        a = {'reserve_start': now + 60,
             'reserve_end': now + 7200}
        h = [self.hostB]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        self.server.submit(r)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '24:00:00'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(1000)
        jid = self.server.submit(j)

        self.logger.info("Wait for the job to try to rerun (10 seconds)")
        time.sleep(10)

        # the job shoud not run because first mom is offline
        # second mom is occupied by maintenance reservation
        a = {'job_state': 'Q'}
        self.server.expect(JOB, a, id=jid)

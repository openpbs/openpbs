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

from tests.performance import *


class TestRunjobWaitPerf(TestPerformance):
    """
    Performance tests related to performance testing of sched job_run_wait attr
    """

    def common_test(self, rw_val):
        """
        Common testing method for job_run_wait tests
        """
        # Create 100 vnodes with 100 ncpus each, capable of running 10k jobs
        a = {"resources_available.ncpus": 100}
        self.mom.create_vnodes(
            a, 100, sharednode=False, expect=False)
        self.server.expect(NODE, {'state=free': (GE, 100)})

        # Start pbs_mom in mock run mode
        self.mom.stop()
        mompath = os.path.join(self.server.pbs_conf["PBS_EXEC"], "sbin",
                               "pbs_mom")
        cmd = [mompath, "-m"]
        self.du.run_cmd(cmd=cmd, sudo=True)
        self.assertTrue(self.mom.isUp(self.mom))
        self.server.expect(NODE, {'resources_available.ncpus=100': (GE, 100)})

        self.server.manager(MGR_CMD_SET, SCHED, {'job_run_wait': rw_val},
                            id="default")

        self.server.manager(MGR_CMD_SET, SERVER, {"scheduling": "False"})
        a = {'Resource_List.select': '1:ncpus=1'}
        for i in range(10000):
            self.server.submit(Job(attrs=a))

        t = time.time()
        self.scheduler.run_scheduling_cycle()

        c = self.scheduler.cycles(lastN=1)[0]
        t = c.end - c.start
        self.logger.info('#' * 80)
        m = "Time taken for job_run_wait=%s: %s" % (rw_val, str(t))
        self.logger.info(m)
        self.logger.info('#' * 80)

        return t

    @timeout(7200)
    def test_rw_none(self):
        """
        Test performance of job_run_wait=none
        """
        t = self.common_test("none")
        self.perf_test_result(t, "time_taken_run_wait_none", "sec")

    @timeout(7200)
    def test_rw_runjobhook(self):
        """
        Test performance of job_run_wait=runjob_hook
        """
        # Create runjob hook so that sched doesn't upgrade runjob_hook to none
        hook_txt = """
import pbs

pbs.event().accept()
"""
        hk_attrs = {'event': 'runjob', 'enabled': 'True'}
        self.server.create_import_hook('rj', hk_attrs, hook_txt)
        t = self.common_test("runjob_hook")
        self.perf_test_result(t, "time_taken_run_wait_runjobhook", "sec")

    @timeout(7200)
    def test_rw_execjobhook(self):
        """
        Test performance of job_run_wait=execjob_hook
        """
        t = self.common_test("execjob_hook")
        self.perf_test_result(t, "time_taken_run_wait_execjobhook", "sec")

    @timeout(14400)
    def test_rw_runjobhook_nohook(self):
        """
        Test performance of job_run_wait=runjob_hook without a runjob hook
        """
        t_rj = self.common_test("runjob_hook")
        t_none = self.common_test("none")

        # Verify that time taken by runjob_hook mode was less than 1.5 times
        # the time taken by none mode, as without a runjob hook, the
        # scheduler should assume none mode even if job_run_wait=runjob_hook
        self.assertLess(t_rj / t_none, 1.5)
        self.perf_test_result(
            t_rj, "time_taken_run_wait_runjobhook_nohook", "sec")
        self.perf_test_result(t_none, "time_taken_run_wait_none", "sec")
        self.perf_test_result(
            (t_none - t_rj),
            "time_diff_run_wait_none_and_run_wait_runjobhook_nohook", "sec")

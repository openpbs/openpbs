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

from tests.interfaces import *


class TestPreemptParamsQmgr(TestInterfaces):
    """
    This testsuite is for testing setting/unsetting of preemption paramaters
    that were moved from sched_config to the scheduler object.
    """
    UNAUTH = 1

    def func_set_fail(self, a, msg, user=ROOT_USER, error_type=0):
        """
        function to confirm that setting the value fails.
        """
        error = ""
        error_code = ""
        if error_type == self.UNAUTH:
            error = "Unauthorized Request"
            error_code = "15007"
        else:
            error = "Illegal attribute or resource value"
            error_code = "15014"

        try:
            self.server.manager(MGR_CMD_SET, SCHED, a, runas=user)
        except PbsManagerError as e:
            self.assertTrue(error in e.msg[0])
            self.assertTrue(error_code in e.msg[1])
        else:
            self.fail(msg)

    def common_tests(self, param, msg):
        """
        function that executes common steps in the actual tests.
        """
        a = {param: 'abc'}
        self.func_set_fail(a, msg)

        a = {param: '123abc'}
        self.func_set_fail(a, msg)

        a = {param: 'abc123'}
        self.func_set_fail(a, msg)

    def test_set_unset_preempt_queue_prio(self):
        """
        This test case sets preempt_queue_prio parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        msg = "preempt_queue_prio set to invalid value"
        param = 'preempt_queue_prio'

        self.common_tests(param, msg)

        a = {param: 120}
        self.func_set_fail(a, msg, TEST_USER, self.UNAUTH)

        self.server.manager(MGR_CMD_SET, SCHED, a, runas=ROOT_USER)

        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_queue_prio',
                            runas=ROOT_USER)

        a = {param: 150}
        self.server.manager(MGR_CMD_LIST, SCHED, a, runas=ROOT_USER)

    def test_set_unset_preempt_prio(self):
        """
        This test case sets preempt_prio parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        msg = "preempt_prio set to invalid value"
        param = 'preempt_prio'

        self.common_tests(param, msg)

        p = '"express_queue, nrmal_jobs, server_softlimits, queue_softlimits"'
        a = {param: p}
        self.func_set_fail(a, msg)

        p = '"express_queue, normal_jobs, server_softlimits, queue_softlimits"'
        a = {param: p}
        self.func_set_fail(a, msg, TEST_USER, self.UNAUTH)

        self.server.manager(MGR_CMD_SET, SCHED, a, runas=ROOT_USER)

        p = '"starving_jobs, normal_jobs, starving_jobs+fairshare, fairshare"'
        a = {param: p}
        self.server.manager(MGR_CMD_SET, SCHED, a,
                            runas=ROOT_USER)

        p = 'starving_jobs, normal_jobs, starving_jobs+fairshare,fairshare'
        a = {param: p}
        self.server.manager(MGR_CMD_LIST, SCHED, a, runas=ROOT_USER)

        self.server.manager(MGR_CMD_UNSET, SCHED, param,
                            runas=ROOT_USER)

        p = 'express_queue, normal_jobs'
        a = {param: p}
        self.server.manager(MGR_CMD_LIST, SCHED, a, runas=ROOT_USER)

    def test_set_unset_preempt_order(self):
        """
        This test case sets preempt_order parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        msg = "preempt_order set to invalid value"
        param = 'preempt_order'

        self.common_tests(param, msg)

        a = {param: '"SCR 80 PQR"'}
        self.func_set_fail(a, msg)

        a = {param: '"PQR"'}
        self.func_set_fail(a, msg)

        a = {param: '"SCR SC"'}
        self.func_set_fail(a, msg)

        a = {param: '"80 SC"'}
        self.func_set_fail(a, msg)

        a = {param: '"SCR 80 70"'}
        self.func_set_fail(a, msg)

        a = {param: '"SCR 80 SC 50 S"'}
        self.server.manager(MGR_CMD_SET, SCHED, a, runas=ROOT_USER)

        a = {param: 'SCR'}
        self.func_set_fail(a, msg, TEST_USER, self.UNAUTH)

        self.server.manager(MGR_CMD_SET, SCHED, a, runas=ROOT_USER)

        self.server.manager(MGR_CMD_UNSET, SCHED, param, runas=ROOT_USER)

        self.server.manager(MGR_CMD_LIST, SCHED, a, runas=ROOT_USER)

    def test_set_unset_preempt_sort(self):
        """
        This test case sets preempt_sort parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        msg = "preempt_sort set to invalid value"
        param = 'preempt_sort'

        self.common_tests(param, msg)

        a = {param: '123'}
        self.func_set_fail(a, msg)

        a = {param: 'min_time_sincestart'}
        self.func_set_fail(a, msg)

        a = {param: 'min_time_since_start'}
        self.func_set_fail(a, msg, TEST_USER, self.UNAUTH)

        self.server.manager(MGR_CMD_SET, SCHED, a, runas=ROOT_USER)

        self.server.manager(MGR_CMD_UNSET, SCHED, param, runas=ROOT_USER)
        self.server.manager(MGR_CMD_LIST, SCHED, a, runas=ROOT_USER)

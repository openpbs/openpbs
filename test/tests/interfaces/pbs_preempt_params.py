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

from tests.interfaces import *


class TestPreemptParamsQmgr(TestInterfaces):
    """
    This testsuite is for testing setting/unsetting of preemption paramaters
    that were moved from sched_config to the scheduler object.
    """
    error_illegal = "Illegal attribute or resource value"
    error_code_illegal = "15014"
    error_unauth = "Unauthorized Request"
    error_code_unauth = "15007"

    def setUp(self):
        self.server.expect(SERVER, {'pbs_version': (GE, '19.0')},
                           max_attempts=2)

    def test_set_unset_preempt_queue_prio(self):
        """
        This test case sets preempt_queue_prio parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        a = {'preempt_queue_prio': 'abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_queue_prio': '123abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_queue_prio': 'abc123'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_queue_prio': 120}
        self.server.manager(MGR_CMD_SET, SCHED, a,
                            expect=True, runas=ROOT_USER)
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=TEST_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_unauth in e.msg[0])
            self.assertTrue(self.error_code_unauth in e.msg[1])

        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_queue_prio',
                            runas=ROOT_USER)

        a = {'preempt_queue_prio': 150}
        self.server.manager(MGR_CMD_LIST, SCHED, a,
                            expect=True, runas=ROOT_USER)

    def test_set_unset_preempt_prio(self):
        """
        This test case sets preempt_prio parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        a = {'preempt_prio': 'abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_prio': '123abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_prio': 'abc123'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        p = '"express_queue, nrmal_jobs, server_softlimits, queue_softlimits"'
        a = {'preempt_prio': p}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        p = '"express_queue, normal_jobs, server_softlimits, queue_softlimits"'
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_SET, SCHED, a,
                            expect=True, runas=ROOT_USER)
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=TEST_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_unauth in e.msg[0])
            self.assertTrue(self.error_code_unauth in e.msg[1])

        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_prio',
                            runas=ROOT_USER)

        p = 'express_queue, normal_jobs'
        a = {'preempt_prio': p}
        self.server.manager(MGR_CMD_LIST, SCHED, a,
                            expect=True, runas=ROOT_USER)

    def test_set_unset_preempt_order(self):
        """
        This test case sets preempt_order parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        a = {'preempt_order': 'abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': '123abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': 'abc123'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': '"SCR 80 PQR"'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': '"PQR"'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': '"SCR SC"'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': '"80 SC"'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': '"SCR 80 70"'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_order': '"SCR 80 SC 50 S"'}
        self.server.manager(MGR_CMD_SET, SCHED, a,
                            expect=True, runas=ROOT_USER)

        a = {'preempt_order': 'SCR'}
        self.server.manager(MGR_CMD_SET, SCHED, a,
                            expect=True, runas=ROOT_USER)
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=TEST_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_unauth in e.msg[0])
            self.assertTrue(self.error_code_unauth in e.msg[1])

        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_order',
                            runas=ROOT_USER)

        a = {'preempt_order': 'SCR'}
        self.server.manager(MGR_CMD_LIST, SCHED, a,
                            runas=ROOT_USER)

    def test_set_unset_preempt_sort(self):
        """
        This test case sets preempt_sort parameter to valid/invalid
        values and checks if the server allows/disallows the operation.
        """
        a = {'preempt_sort': 'abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_sort': '123'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_sort': 'abc123'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_sort': '123abc'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_sort': 'min_time_sincestart'}
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_illegal in e.msg[0])
            self.assertTrue(self.error_code_illegal in e.msg[1])

        a = {'preempt_sort': 'min_time_since_start'}
        self.server.manager(MGR_CMD_SET, SCHED, a,
                            expect=True, runas=ROOT_USER)
        try:
            self.server.manager(MGR_CMD_SET, SCHED, a,
                                expect=True, runas=TEST_USER)
        except PbsManagerError as e:
            self.assertTrue(self.error_unauth in e.msg[0])
            self.assertTrue(self.error_code_unauth in e.msg[1])

        self.server.manager(MGR_CMD_UNSET, SCHED, 'preempt_sort',
                            runas=ROOT_USER)

        self.server.manager(MGR_CMD_LIST, SCHED, a,
                            expect=False, runas=ROOT_USER)

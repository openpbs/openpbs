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


class TestMomDynRes(TestFunctional):

    def create_mom_resources(self, resc_name,
                             resc_type, resc_flag,
                             script_body):
        """
        helper function for create mom_resources.
        """
        attr = {"type": resc_type, "flag": resc_flag}
        self.server.manager(MGR_CMD_CREATE, RSC, attr,
                            id=resc_name, expect=True)

        fp = self.du.create_temp_file(prefix="mom_resc", suffix=".scr",
                                      body=script_body)
        self.du.chmod(path=fp, mode=0755)

        mom_config_str = "!" + fp
        self.mom.add_config({resc_name: mom_config_str})
        self.scheduler.set_sched_config({'mom_resources': '"foo"'},
                                        validate=True)
        self.scheduler.add_resource(resc_name)

    def test_t3(self):
        """
        Test for host level string resource
        with string mom dynamic value
        """
        resc_name = "foo"
        self.create_mom_resources(resc_name, "string", "h", "/bin/echo pqr")

        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a job that requests different mom dynamic resource
        # not return from script
        attr = {"Resource_List." + resc_name: 'abc'}
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        # The job shouldn't run
        c = "Can Never Run: Insufficient amount of resource: foo (abc != pqr)"
        self.server.expect(JOB, {'job_state': 'Q', 'comment': c},
                           id=jid, attrop=PTL_AND)

    def test_t5(self):
        """
        Tets for host level string_array resource
        with string mom dynamic value
        """

        resc_name = "foo"
        self.create_mom_resources(resc_name, "string_array",
                                  "h", "/bin/echo red,green,blue")

        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a job that requests mom dynamic resource
        attr = {"Resource_List." + resc_name: 'red'}
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        # The job should run
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Submit a job that requests different mom dynamic resource
        # not return from script
        attr = {"Resource_List." + resc_name: 'white'}
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        # The job shouldn't run
        c = "Can Never Run: Insufficient amount of resource:"
        c += " foo (white != red,green,blue)"
        self.server.expect(JOB, {'job_state': 'Q', 'comment': c},
                           id=jid, attrop=PTL_AND)

    def test_t6(self):
        """
        Test for host level string resource
        with mom dynamic value “This is a test”
        """
        resc_name = "foo"
        self.create_mom_resources(resc_name, "string",
                                  "h", "/bin/echo This is a test")

        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Submit a job that requests different mom dynamic resource
        attr = {"Resource_List." + resc_name: 'red'}
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        # The job shouldn't run
        c = "Can Never Run: Insufficient amount of resource:"
        c += " foo (red != This is a test)"
        self.server.expect(JOB, {'job_state': 'Q', 'comment': c},
                           id=jid, attrop=PTL_AND)

        # Submit a job that requests mom dynamic resource
        attr = {"Resource_List." + resc_name: '"This is a test"'}
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        # The job should run
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

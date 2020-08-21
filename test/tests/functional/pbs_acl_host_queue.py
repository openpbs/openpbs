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


class Test_acl_host_queue(TestFunctional):
    """
    This test suite is for testing the queue attributes acl_host_enable
    and acl_hosts.
    """

    def test_acl_host_enable_refuse(self):
        """
        Set acl_host_enable = True on queue and check whether or not
        the submit is refused.
        """
        a = {"acl_host_enable": True,
             "acl_hosts": "foo"}
        self.server.manager(MGR_CMD_SET, QUEUE, a,
                            self.server.default_queue)

        j = Job(TEST_USER)
        try:
            self.server.submit(j)
        except PbsSubmitError as e:
            error_msg = "qsub: Access from host not allowed, or unknown host"
            self.assertEquals(e.msg[0], error_msg)
        else:
            self.fail("Queue is violating acl_hosts")

    def test_acl_host_enable_allow(self):
        """
        Set acl_host_enable = True along with acl_hosts and check
        whether or not a job can be submitted.
        """
        a = {"acl_host_enable": True,
             "acl_hosts": self.server.hostname}
        self.server.manager(MGR_CMD_SET, QUEUE, a,
                            self.server.default_queue)

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.logger.info('Job submitted successfully: ' + jid)

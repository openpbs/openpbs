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

import time
import socket
from tests.functional import *


@tags('smoke')
class TestPbsNode(TestFunctional):

    """
    This tests Node create and delete.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

        self.server.cleanup_jobs()

    def tearDown(self):

        TestFunctional.tearDown(self)
        # Delete managers and operators if added
        attrib = ['operators', 'managers']
        self.server.manager(MGR_CMD_UNSET, SERVER, attrib)

    def test_create_and_delete_00(self):
        """
        Test:  this will test two things:
        1.  The stopping and starting of a mom and the proper log messages.
        2.  The stopping and starting of a mom and the proper hook firing.
        """
        self.logger.info("---- TEST STARTED ----")
        self.logger.error("socket.gethostname():%s", socket.gethostname())
        self.logger.error("***self.server.name:%s", str(self.server.name))
        self.logger.error("self.server.moms:%s", str(self.server.moms))
        for name, value in self.server.moms.items():
            start_time = int(time.time())
            self.logger.error("    ***%s:%s, type:%s", name, value, type(value))
            self.logger.error("    ***%s:fqdn:    %s", name, value.fqdn)
            self.logger.error("    ***%s:hostname:%s", name, value.hostname)
            self.logger.error("    ***stopping mom:%s", value)
            value.stop()
            self.logger.error("    ***start    mom:%s", value)
            value.start()
            self.logger.error("    ***restart  mom:%s", value)
            value.restart()
            self.server.log_match("Node;%s;node up" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("Node;%s;node down" % value.fqdn,
                                  starttime=start_time)
        self.logger.info("---- TEST ENDED ----")       
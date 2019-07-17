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

import os

from tests.functional import *


class TestConf(TestFunctional):
    """
    This test suite tests the PBS configuration file
    """

    def test_sched_host_name_envvar(self):
        """
        Start the server with the PBS_SCHEDULER_HOST_NAME
        set to the name of the local host to show the variable works
        Also set it to some other existing machine that isn't set up
        to work with this machine (e.g. cvs.pbspro.com) and show
        the server can't talk to the sched, to prove that the
        variable is being used.
        """
        conf = self.du.parse_pbs_config(self.server.hostname)
        self.du.set_pbs_config(
            self.server.hostname,
            confs={'PBS_SCHEDULER_HOST_NAME': conf['PBS_SERVER']})
        now = int(time.time())
        self.server.restart()
        self.assertTrue(self.server.isUp(), 'Failed to start PBS')
        logmsg = 'request received from Scheduler@%s' % (self.server.hostname)
        self.server.log_match(logmsg, starttime=now)

        # Now set it to cvs and show that the server can't talk to the sched
        self.du.set_pbs_config(
            self.server.hostname,
            confs={'PBS_SCHEDULER_HOST_NAME': 'cvs.pbspro.com'})
        now = int(time.time())
        self.server.restart()
        logmsg = 'Could not contact Scheduler'
        self.server.log_match(logmsg, starttime=now)

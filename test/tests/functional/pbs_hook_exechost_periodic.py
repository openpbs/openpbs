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


class TestHookExechostPeriodic(TestFunctional):
    """
    Tests to test exechost_periodic hook
    """

    def test_multiple_exechost_periodic_hooks(self):
        """
        This test sets two exechost_periodic hooks and restarts the mom,
        which tests whether both the hooks will successfully run on node
        startup and the mom not crashes.
        """
        self.attr = {'event': 'exechost_periodic',
                     'enabled': 'True', 'freq': '30'}
        self.hook_body1 = ("import pbs\n"
                           "e = pbs.event()\n"
                           "pbs.logmsg(pbs.EVENT_DEBUG,\n"
                           "\t\"exechost_periodic hook1\")\n"
                           "e.accept()\n")
        self.hook_body2 = ("import pbs\n"
                           "e = pbs.event()\n"
                           "pbs.logmsg(pbs.EVENT_DEBUG,\n"
                           "\t\"exechost_periodic hook2\")\n"
                           "e.accept()\n")
        self.server.create_import_hook("exechost_periodic1",
                                       self.attr, self.hook_body1)
        self.server.create_import_hook("exechost_periodic2",
                                       self.attr, self.hook_body2)
        self.mom.restart()
        self.assertTrue(self.mom.isUp(self.mom))
        self.mom.log_match("exechost_periodic hook1",
                           max_attempts=5, interval=5)
        self.mom.log_match("exechost_periodic hook2",
                           max_attempts=5, interval=5)

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


class TestHookInterrupt(TestFunctional):

    """
    This suite contains hook test to verify that pbs generates
    KeyBoardInterrupt via hook alarm on long running hook
    """

    def test_hook_interrupt(self):
        """
        Test hook interrupt
        """
        hook_name = "testhook"
        hook_body = """
import pbs
import time

pbs.logmsg(pbs.LOG_DEBUG, "TestHook Started")
time.sleep(100000)
pbs.logmsg(pbs.LOG_DEBUG, "TestHook Ended")
"""
        a = {'event': 'runjob', 'enabled': 'True', 'alarm': '5'}
        self.server.create_import_hook(hook_name, a, hook_body)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': -1})
        j = Job(TEST_USER)
        st = time.time()
        jid = self.server.submit(j)

        self.server.log_match("TestHook Started", starttime=st)

        _msg = "Not Running: PBS Error: request rejected"
        _msg += " as filter hook '%s' got an alarm call." % hook_name
        _msg += " Please inform Admin"
        self.server.expect(JOB,
                           {'job_state': 'Q', 'comment': _msg},
                           id=jid, offset=5)

        self.server.log_match("Hook;catch_hook_alarm;alarm call received",
                              starttime=st)
        _msg1 = "PBS server internal error (15011)"
        _msg1 += " in Python script received a KeyboardInterrupt, "
        _msg2 = "<class 'KeyboardInterrupt'>"
        _msg3 = "<could not figure out the exception value>"
        self.server.log_match(_msg1 + _msg2, starttime=st)
        self.server.log_match(_msg1 + _msg3, starttime=st)
        self.server.log_match("Hook;%s;finished" % hook_name, starttime=st)
        _msg = "alarm call while running runjob hook"
        _msg += " '%s', request rejected" % hook_name
        self.server.log_match(_msg, starttime=st)
        self.server.log_match("TestHook Ended", existence=False, starttime=st)

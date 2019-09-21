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

from tests.selftest import *
from io import StringIO
import logging


class TestExpect(TestSelf):
    """
    Contains tests for the expect() function
    """

    def test_attribute_case(self):
        """
        Test that when verifying attribute list containing attribute names
        with different case, expect() is case insensitive
        """
        # Create a queue
        a = {'queue_type': 'execution'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, 'expressq')

        # Set the Priority attribute on the queue but provide 'p' lowercase
        # Set other attributes normally
        a = {'enabled': 'True', 'started': 'True', 'priority': 150}
        self.server.manager(MGR_CMD_SET, QUEUE, a, 'expressq')
        self.server.expect(QUEUE, a, id='expressq')

    def test_unsupported_operator(self):
        """
        Test that expect can handle unsupported operators correctly
        """
        # Add a new log handler which writes into a StringIO buffer
        logbuffer = StringIO()
        ptllogger = logging.getLogger('ptl')
        temploghandler = logging.StreamHandler(logbuffer)
        tempfmt = logging.Formatter("%(message)s")
        temploghandler.setFormatter(tempfmt)
        ptllogger.addHandler(temploghandler)
        ptllogger.propagate = True

        # Call manager on an unsupported operator (INCR)
        # As expect is done automatically for set operations,
        # we should see a log message for unsupported operator
        manager = str(MGR_USER) + '@*'
        rc = self.server.manager(MGR_CMD_SET, SERVER,
                                 {'managers': (INCR, manager)}, sudo=True)
        self.assertEqual(rc, 0)
        ptllogger.removeHandler(temploghandler)

        # Verify that expect logged the expected log message
        logmsg = "Operator not supported by expect(), " +\
            "cannot verify change in managers"
        msgfound = False
        for line in logbuffer.getvalue().splitlines():
            if line == logmsg:
                msgfound = True
                break
        self.assertTrue(msgfound,
                        "Didn't find expected log message from expect()")

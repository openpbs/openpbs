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

from tests.functional import *


@tags('cray', 'mom')
class TestBasilParserErrors(TestFunctional):
    """
    Test the BASIL parser error messages
    """

    def setUp(self):
        TestFunctional.setUp(self)
        momA = self.moms.values()[0]
        if not momA.is_cray():
            self.skipTest("%s: not a cray mom." % (momA.shortname))

    def test_basil_errors(self):
        """
        Check for the non existence of BASIL errors in mom logs
        """
        self.mom.log_match("PERMANENT BASIL error from SYNTAX",
                           max_attempts=10,
                           interval=1,
                           existence=False)
        self.mom.log_match("Error in BASIL response",
                           max_attempts=10,
                           interval=1,
                           existence=False)

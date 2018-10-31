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


class Test_pbs_types(TestFunctional):
    """
    This test suite tests pbs python types and their related functions
    """
    def test_pbs_size_deepcopy(self):
        """
        Test that deepcopy works for pbs.size type
        """
        hook_content = ("""
import pbs
import copy
a = pbs.size(1000)
b = copy.deepcopy(a)
c = a
pbs.logmsg(pbs.EVENT_DEBUG, 'a=%s, b=%s, c=%s' % (a, b, c))
d = pbs.size('1m')
e = copy.deepcopy(d)
f = d
pbs.logmsg(pbs.EVENT_DEBUG, 'd=%s, e=%s, f=%s' % (d, e, f))
""")
        hook_name = 'deepcopy'
        hook_attr = {'enabled': 'true', 'event': 'queuejob'}
        self.server.create_import_hook(hook_name, hook_attr, hook_content)

        j = Job(TEST_USER)
        self.server.submit(j)
        self.server.log_match("a=1000b, b=1000b, c=1000b")
        self.server.log_match("d=1mb, e=1mb, f=1mb")

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


class Test_single_event_multiple_hooks(TestFunctional):
    """
    Test if changes made to pbs objects by multiple hooks of same
    event type takes effect or not.
    """
    hook_string = """
import pbs
e = pbs.event()
e.job.Resource_List["%s"]=%s
%s
"""

    def create_hook_scr(self, accept, resource, value):
        """
        function to create a hook script.
        It accepts 3 arguments
        - accept	If set to true, then hook will accept else reject
        - resource	Resource whose value we want to change
        - value		New value to be assigned
        """
        hook_action = "e.accept()"
        if not accept:
            hook_action = "e.reject()"
        final_hook = self.hook_string % (resource, value, hook_action)
        return final_hook

    def test_two_queuejob_hooks(self):
        """
        Submit two queue job hooks. One of the hook modifies resource ncpus
        and other hook modifies walltime. Check the result of modification.
        """
        hook_name = "h1"
        scr = self.create_hook_scr(True, "ncpus", "int(5)")
        attrs = {'event': "queuejob", 'order': '1'}
        rv = self.server.create_import_hook(
            hook_name,
            attrs,
            scr,
            overwrite=True)
        self.assertTrue(rv)

        hook_name = "h2"
        scr = self.create_hook_scr(True, "walltime", "600")
        attrs = {'event': "queuejob", 'order': '2'}
        rv = self.server.create_import_hook(
            hook_name,
            attrs,
            scr,
            overwrite=True)
        self.assertTrue(rv)
        a = {'Resource_List.ncpus': 1,
             'Resource_List.walltime': 10}
        j = Job(TEST_USER)
        j.set_attributes(a)
        j.set_sleep_time("10")
        jid = self.server.submit(j)
        self.server.expect(JOB, {
            'Resource_List.ncpus': 5,
            'Resource_List.walltime': '00:10:00'},
            offset=2, id=jid)

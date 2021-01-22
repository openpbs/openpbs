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

    def test_revert_attributes(self):
        """
        test that when we unset any attribute in expect(),
        attribute will be unset and should get value on attribute basis.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': False})
        self.server.manager(MGR_CMD_UNSET, SERVER, 'scheduling')
        self.server.expect(SERVER, 'scheduling', op=UNSET)

        self.server.manager(MGR_CMD_UNSET, SERVER, 'max_job_sequence_id')
        self.server.expect(SERVER, 'max_job_sequence_id', op=UNSET)

        self.server.manager(MGR_CMD_UNSET, SCHED, 'sched_host')
        self.server.expect(SCHED, 'sched_host', op=UNSET)

        self.server.manager(MGR_CMD_UNSET, SCHED, ATTR_sched_cycle_len)
        self.server.expect(SCHED, ATTR_sched_cycle_len, op=UNSET)

        self.server.manager(MGR_CMD_UNSET, NODE, ATTR_NODE_resv_enable,
                            id=self.mom.shortname)
        self.server.expect(NODE, ATTR_NODE_resv_enable,
                           op=UNSET, id=self.mom.shortname)

        hook_name = "testhook"
        hook_body = "import pbs\npbs.event().reject('my custom message')\n"
        a = {'event': 'queuejob', 'enabled': 'True', 'alarm': 10}
        self.server.create_import_hook(hook_name, a, hook_body)
        self.server.manager(MGR_CMD_UNSET, HOOK, 'alarm', id=hook_name)
        self.server.expect(HOOK, 'alarm', op=UNSET, id=hook_name)

        a = {'partition': 'P1',
             'sched_host': self.server.hostname,
             'sched_port': '15050'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc1")
        new_sched_home = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                      'sc_1_mot')
        self.scheds['sc1'].create_scheduler(sched_home=new_sched_home)
        self.scheds['sc1'].start()
        self.server.manager(MGR_CMD_UNSET, SCHED, 'sched_priv', id='sc1')
        self.server.expect(SCHED, 'sched_priv', op=UNSET, id='sc1')

        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vn', a, num=2, mom=self.mom)
        self.server.manager(MGR_CMD_UNSET, VNODE,
                            'resources_available.ncpus', id='vn[1]')
        self.server.expect(VNODE, 'resources_available.ncpus',
                           id='vn[1]', op=UNSET)
        self.server.manager(MGR_CMD_UNSET, VNODE,
                            ATTR_NODE_resv_enable, id='vn[1]')
        self.server.expect(VNODE, ATTR_NODE_resv_enable,
                           op=UNSET, id='vn[1]')

        self.server.manager(MGR_CMD_UNSET, NODE, 'resources_available.ncpus',
                            id=self.mom.shortname)
        self.server.expect(NODE, 'resources_available.ncpus',
                           op=UNSET, id=self.mom.shortname)

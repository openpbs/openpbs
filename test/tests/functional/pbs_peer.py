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


class TestPeering(TestFunctional):
    """
    Some tests for Peering queues
    """

    cres = "custom_res"
    cqueue = "custom_queue"

    def create_resource(self, name=None, server=None):
        if not name:
            name = self.cres

        if not server:
            server = self.server

        server.manager(MGR_CMD_CREATE, RSC,
                       {'type': 'long', 'flag': 'q'},
                       id=name)

        self.scheduler.add_resource(name)

    def create_queue(self, name=None, server=None, a=None):
        if not name:
            name = self.cqueue

        if not server:
            server = self.server

        if not a:
            a = {'queue_type': 'execution', 'enabled': True, 'started': True}

        server.manager(MGR_CMD_CREATE, QUEUE, a, id=name)

    def test_local_resc_limits(self):
        """
        Test that a local peering queue enforces new limits
        """
        self.create_resource()
        self.create_queue()
        a = {'resources_max.' + self.cres: 4}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id=self.cqueue)
        a = {'started': False}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq')
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': False})

        a = {'peer_queue': '"' + self.cqueue + ' workq"'}
        self.scheduler.set_sched_config(a)

        j = Job(TEST_USER, attrs={'Resource_List.' + self.cres: 100})
        jid = self.server.submit(j)
        j = Job(TEST_USER, attrs={'Resource_List.' + self.cres: 1})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        msg = (jid + ';Failed to run: Job violates queue and/or server'
               ' resource limits (15036)')
        self.scheduler.log_match(msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

    @requirements(num_servers=2)
    def test_remote_resc_limits(self):
        """
        Test that a remote peering queue enforces new limits
        """
        s1 = self.servers.values()[0]
        s2 = self.servers.values()[1]
        self.create_resource(server=s1)
        self.create_resource(server=s2)
        a = {'resources_max.' + self.cres: 4}
        s1.manager(MGR_CMD_SET, QUEUE, a, id='workq')
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': False})

        a = {'flatuid': True}
        s1.manager(MGR_CMD_SET, SERVER, a)
        s2.manager(MGR_CMD_SET, SERVER, a)

        a = {'peer_queue': '"workq workq@' + s2.hostname + '"'}
        self.scheduler.set_sched_config(a)

        a = {'Resource_List.' + self.cres: 100,
             ATTR_queue: 'workq@' + s2.hostname}
        j = Job(TEST_USER, attrs=a)
        jid = s1.submit(j)
        a['Resource_List.' + self.cres] = 1
        j = Job(TEST_USER, attrs=a)
        jid2 = s1.submit(j)
        s2.expect(JOB, {'job_state': 'Q'}, id=jid)
        s2.expect(JOB, {'job_state': 'Q'}, id=jid2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        s1.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        s1.expect(JOB, {'job_state': 'Q'}, id=jid)
        msg = (jid + r';Failed to run: .* \(15039\)')
        self.scheduler.log_match(msg, regexp=True)
        msg = jid + ';send of job to workq@.* failed error = 15036'
        s2.log_match(msg, regexp=True)
        s1.expect(JOB, {'job_state': 'R'}, id=jid2)

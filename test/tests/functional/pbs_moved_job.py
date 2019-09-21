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


class TestMovedJob(TestFunctional):
    """
    This test suite tests moved jobs between two servers
    """
    @timeout(500)
    def test_moved_job_history(self):
        """
        This test suite verifies that moved (M) job preserves in the system
        at least until the job is really finished on the target server.
        Supposing the job is finished, this test also checks whether
        the M job is removed after <job_history_duration>.
        """
        # Skip test if number of servers is not equal to two
        if len(self.servers) != 2:
            self.skipTest("test requires atleast two servers as input, " +
                          "use -p servers=<server1:server2>,moms=<server1>")

        second_server = self.servers.keys()[1]

        attr = {'job_history_enable': 'True', 'job_history_duration': 5}
        self.servers[second_server].manager(MGR_CMD_SET, SERVER, attr)

        attr = {'queue_type': 'execution',
                'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, attr, id='p2p')
        self.servers[second_server].manager(MGR_CMD_CREATE, QUEUE,
                                            attr, id='p2p')

        attr = {'peer_queue': '\"p2p p2p@' + second_server + '\"'}
        self.scheduler.set_sched_config(attr)

        attr = {'scheduler_iteration': 5}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        self.server.restart()

        attr = {ATTR_queue: "p2p", ATTR_j: "oe",
                ATTR_W: "Output_Path=%s:/dev/null"
                % self.servers.keys()[0],
                'Resource_List.select': 'host=%s'
                % self.moms.keys()[0]}
        j = Job(TEST_USER, attrs=attr)
        j.set_sleep_time(300)
        jid = self.servers[second_server].submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.servers[second_server].expect(JOB, {'job_state': 'M'},
                                           id=jid, extend='x')

        # history work task runs every two minutes
        self.logger.info("Wait for history work task to process...")
        time.sleep(125)

        # the jid should be still present with state M
        self.servers[second_server].expect(JOB, {'job_state': 'M'},
                                           id=jid, extend='x')

        self.server.delete(id=jid, wait=True)

        # history work task runs every two minutes
        self.logger.info("Wait for history work task to process...")
        time.sleep(125)

        # the jid should be gone
        try:
            qstat = self.servers[second_server].status(JOB, 'status',
                                                       id=jid,
                                                       extend='x')
        except PbsStatusError as err:
            #  rc = 153 is for 'Unknown Job Id'
            self.assertEqual(err.rc, 153)
            qstat = ""

        self.assertEqual(qstat, "")

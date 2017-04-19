# coding: utf-8

# Copyright (C) 1994-2016 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero
# General Public License agreement ("AGPL"), except where a separate
# commercial license agreement for PBS Pro version 14 or later has been
# executed in writing with Altair.
#
# Altair’s dual-license business model allows companies, individuals,
# and organizations to create proprietary derivative works of PBS Pro
# and distribute them - whether embedded or bundled with other software
# - under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to
# Altair's trademark licensing policies

from ptl.utils.pbs_testsuite import *


class Test_JobArray_In_RoutingQueue(PBSTestSuite):
    """
    Test for bug when deleting a subjob of a Job Array in H state in
    Routing queue causes jobs to fail to route
    """

    def test_delete_subjob_routingqueue(self):

        dflt_q = self.server.default_queue
        # Create a route queue with destination to default queue
        a = {ATTR_qtype: 'route',
             ATTR_routedest: dflt_q,
             ATTR_enable: 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='routeq')
        # Submit an array job in Held state
        j = Job(TEST_USER, attrs={ATTR_queue: 'routeq',
                                  ATTR_l + '.ncpus': 1,
                                  ATTR_h: 'u',
                                  ATTR_J: '1-2:1',
                                  ATTR_r: 'y'})

        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'H'}, jid)
        self.server.expect(JOB, {ATTR_state + '=Q': 2}, count=True,
                           id=jid, extend='t')
        subjobs = self.server.status(JOB, id=jid, extend='t')
        # Delete one of the subjob
        self.server.deljob(subjobs[-1]['id'])
        self.server.expect(JOB, {ATTR_state: 'H'}, jid)
        self.server.expect(JOB, {ATTR_state + '=Q': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=X': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_queue + '=routeq': 3}, count=True,
                           id=jid, extend='t')
        # Release the array and state changed to B
        self.server.rlsjob(jid, 'u')
        self.server.expect(JOB, {ATTR_state: 'B'}, jid)
        self.server.expect(JOB, {ATTR_state + '=Q': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=X': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_queue + '=routeq': 3}, count=True,
                           id=jid, extend='t')
        # No errors should be in server logs
        m = self.server.tracejob_match(
            msg='(job_route) Request invalid for state of job, state=7',
            id=jid)
        self.assertEqual(m, None)
        # Start routing queue and array jobs queue chnaged to default queue
        a = {ATTR_start: 'True'}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='routeq')
        self.server.expect(JOB, {ATTR_queue + '=workq': 3}, count=True,
                           id=jid, extend='t')

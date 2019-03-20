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


class TestJobRouting(TestFunctional):
    """
    This test suite validates state of parent job and subjobs in a Job Array.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.momA = self.moms.values()[0]
        self.momA.delete_vnode_defs()

        self.hostA = self.momA.shortname

        self.server.manager(MGR_CMD_DELETE, NODE, None, "")

        self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)

        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostA)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'false'})

    def test_t1(self):
        """
        This test case validates Job array state when one
        of the subjob is deleted while the array job is HELD in a routing
        queue and is released after the subjob is deleted.
        """
        dflt_q = self.server.default_queue
        # Create a route queue with destination to default queue
        queue_attrib = {ATTR_qtype: 'route',
                        ATTR_routedest: dflt_q,
                        ATTR_enable: 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, queue_attrib, id='routeq')

        job_attrib = Job(TEST_USER, attrs={ATTR_queue: 'routeq',
                                           ATTR_l + '.ncpus': 1,
                                           ATTR_h: None,
                                           ATTR_J: '1-2',
                                           ATTR_r: 'y'})

        # Submit an array job in Held state
        jid = self.server.submit(job_attrib)

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

        # Release the array and verify job array state
        self.server.rlsjob(jid, 'u')
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid)
        self.server.expect(JOB, {ATTR_state + '=Q': 2}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=X': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_queue + '=routeq': 3}, count=True,
                           id=jid, extend='t')

        # No errors should be in server logs
        msg = '(job_route) Request invalid for state of job, state=7'
        self.server.log_match(msg, id=jid, existence=False)

        # Start routing queue and verify job array queue set to default queue
        a = {ATTR_start: 'True'}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='routeq')
        self.server.expect(JOB, {ATTR_queue + '=' + dflt_q: 3}, count=True,
                           id=jid, extend='t')

    def test_t2(self):
        """
        This test case validates Job array state when running subjobs
        are force fully deleted. After deleting the running subjob
        Array job is held and released, this should cause job array
        state change to Q from B.
        """

        # Submit a job array of size 3
        job = Job()
        job.set_attributes({ATTR_l + '.ncpus': 1,
                            ATTR_J: '1-3',
                            ATTR_r: 'y'})

        job.set_sleep_time(1000)
        jid = self.server.submit(job)

        self.server.expect(JOB, {ATTR_state + '=Q': 4}, count=True,
                           id=jid, extend='t')

        # Start scheduling cycle. This will move all 3 subjobs to R state.
        # And parent job state to B state.
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'true'})

        self.server.expect(JOB, {ATTR_state + '=R': 3}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=B': 1}, count=True,
                           id=jid, extend='t')

        # Delete two of the subjobs.
        subjobs = self.server.status(JOB, id=jid, extend='t')
        self.server.deljob(subjobs[1]['id'])
        self.server.deljob(subjobs[2]['id'])

        # Mark node offline, and  rerun the third job.
        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        a = {'state': 'offline'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostA)

        # Rerun Third job, job will move to Q state.
        self.server.rerunjob(subjobs[3]['id'])
        self.server.expect(JOB, {ATTR_state + '=Q': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=X': 2}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=B': 1}, count=True,
                           id=jid, extend='t')

        # Hold the job array. Parent job will move to H state.

        self.server.holdjob(jid)
        self.server.expect(JOB, {ATTR_state + '=H': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=Q': 1}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=X': 2}, count=True,
                           id=jid, extend='t')

        # Release the job and validate array job state.
        # Expected parent array job state is Q

        self.server.rlsjob(jid, 'u')
        self.server.expect(JOB, {ATTR_state + '=Q': 2}, count=True,
                           id=jid, extend='t')
        self.server.expect(JOB, {ATTR_state + '=X': 2}, count=True,
                           id=jid, extend='t')

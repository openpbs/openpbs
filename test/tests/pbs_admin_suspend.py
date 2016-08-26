# coding: utf-8

# Copyright (C) 1994-2016 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

import time
from ptl.utils.pbs_testsuite import *


class TestAdminSuspend(PBSTestSuite):
    """
    Test the admin-suspend/admin-resume feature for node maintenance
    """

    def setUp(self):
        PBSTestSuite.setUp(self)
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.server.create_vnodes('vn', a, 1, self.mom)

    def test_basic(self):
        """
        Test basic admin-suspend functionality
        """
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        j2 = Job(TEST_USER)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        # admin-suspend job 1.
        self.server.sigjob(jid1, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid1})

        # admin-suspend job 2
        self.server.sigjob(jid2, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid1 + "," + jid2})

        # admin-resume job 1.  Make sure the node is still in state maintenance
        self.server.sigjob(jid1, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid2})

        # admin-resume job 2.  Make sure the node retuns to state free
        self.server.sigjob(jid2, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

    def test_basic_ja(self):
        """
        Test basic admin-suspend functionality for job arrays
        """
        jA = Job(TEST_USER)
        jA.set_attributes({'Resource_List.select': '1:ncpus=1', ATTR_J: '1-2'})
        jidA = self.server.submit(jA)
        self.server.expect(JOB, {'job_state': 'B'}, id=jidA)

        subjobs = self.server.status(JOB, id=jidA, extend='t')
        # subjobs[0] is the array itself.  Need the subjobs
        jid1 = subjobs[1]['id']
        jid2 = subjobs[2]['id']

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        # admin-suspend job 1.
        self.server.sigjob(jid1, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid1})

        # admin-suspend job 2
        self.server.sigjob(jid2, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid1 + "," + jid2})

        # admin-resume job 1.  Make sure the node is still in state maintenance
        self.server.sigjob(jid1, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid2})

        # admin-resume job 2.  Make sure the node retuns to state free
        self.server.sigjob(jid2, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

    def test_basic_restart(self):
        """
        Test basic admin-suspend functionality with server restart
        The restart will test if the node recovers properly in maintenance
        """
        j1 = Job(TEST_USER)
        jid = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # admin-suspend job
        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid})

        self.server.restart()

        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid})

        # admin-resume job
        self.server.sigjob(jid, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

    def test_cmd_perm(self):
        """
        Test permissions on admin-suspend, admin-resume, maintenance_jobs
        and the maintenace node state.
        """

        # Test to make sure we can't set the maintenance node state
        try:
            self.server.manager(
                MGR_CMD_SET, NODE,
                {'state': 'maintenance'}, id='vn[0]', runas=ROOT_USER)
        except PbsManagerError, e:
            self.assertTrue('Illegal value for node state' in e.msg[0])

        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

        # Test to make sure we can't set the 'maintenance_jobs' attribute
        try:
            self.server.manager(
                MGR_CMD_SET, NODE,
                {'maintenance_jobs': 'foo'}, id='vn[0]', runas=ROOT_USER)
        except PbsManagerError, e:
            self.assertTrue(
                'Cannot set attribute, read only or insufficient permission'
                in e.msg[0])

        self.server.expect(NODE, 'maintenance_jobs', op=UNSET, id='vn[0]')

        # Test to make sure regular users can't admin-suspend jobs
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        try:
            self.server.sigjob(jid, 'admin-suspend', runas=TEST_USER)
        except PbsSignalError, e:
            self.assertTrue('Unauthorized Request' in e.msg[0])

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Test to make sure regular users can't admin-resume jobs
        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

        try:
            self.server.sigjob(jid, 'admin-resume', runas=TEST_USER)
        except PbsSignalError, e:
            self.assertTrue('Unauthorized Request' in e.msg[0])

        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

    def test_wrong_state1(self):
        """
        Test using wrong resume signal is correctly rejected
        """

        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        self.server.sigjob(jid1, "suspend", runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)

        try:
            self.server.sigjob(jid1, "admin-resume", runas=ROOT_USER)
        except PbsSignalError, e:
            self.assertTrue(
                'Job can not be resumed with the requested resume signal'
                in e.msg[0])

        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)

    def test_wrong_state2(self):
        """
        Test using wrong resume signal is correctly rejected
        """

        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        self.server.sigjob(jid1, "admin-suspend", runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(JOB, {'substate': 43}, id=jid1)

        try:
            self.server.sigjob(jid1, "resume", runas=ROOT_USER)
        except PbsSignalError, e:
            self.assertTrue(
                'Job can not be resumed with the requested resume signal'
                in e.msg[0])

        # If resume had worked, the job would be in substate 45
        self.server.expect(JOB, {'substate': 43}, id=jid1)

    def test_deljob(self):
        """
        Test whether a node leaves the maintenance state when
        an admin-suspendedd job is deleted
        """

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        self.server.deljob(jid, wait=True)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

    def test_deljob_force(self):
        """
        Test whether a node leaves the maintenance state when
        an admin-suspendedd job is deleted with -Wforce
        """

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        self.server.deljob(jid, extend='force', wait=True)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

    def test_rerunjob(self):
        """
        Test whether a node leaves the maintenance state when
        an admin-suspended job is requeued
        """

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        self.server.rerunjob(jid, extend='force')
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

    def test_multivnode(self):
        """
        Submit a job to multiple vnodes.  Send an admin-suspend signal
        and see all nodes go into maintenance
        """
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.server.create_vnodes('vn', a, 3, self.mom, usenatvnode=True)

        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '3:ncpus=1',
                          'Resource_List.place': 'vscatter'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state=maintenance': 3})
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

        self.server.sigjob(jid, 'admin-resume', runas=ROOT_USER)
        self.server.expect(NODE, {'state=free': 3})

    def test_multivnode2(self):
        """
        Submit a job to multiple vnodes.  Send an admin-suspend signal
        and see all nodes go into maintenance
        Submit a single node job to one of the nodes.  Resume the multinode
        Job and see the single node job's node stil in maintenance
        """
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.server.create_vnodes('vn', a, 3, self.mom, usenatvnode=True)

        # Submit multinode job 1
        j1 = Job(TEST_USER)
        j1.set_attributes({'Resource_List.select': '3:ncpus=1',
                           'Resource_List.place': 'vscatter'})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        # Submit Job 2 to specific node
        j2 = Job(TEST_USER)
        j2.set_attributes({'Resource_List.select': '1:ncpus=1:vnode=vn[0]'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        # admin-suspend job 1 and see all three nodes go into maintenance
        self.server.sigjob(jid1, 'admin-suspend')
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(NODE, {'state=maintenance': 3})

        # admin-suspend job 2
        self.server.sigjob(jid2, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)

        # admin-resume job1 and see one node stay in maintenance
        self.server.sigjob(jid1, 'admin-resume', runas=ROOT_USER)
        self.server.expect(NODE, {'state=free': 2})
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

    def test_multivnode_excl(self):
        """
        Submit an excl job to multiple vnodes.  Send an admin-suspend
        signal and see all nodes go into maintenance
        """
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.server.create_vnodes('vn', a, 3, self.mom, usenatvnode=True)

        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '3:ncpus=1',
                          'Resource_List.place': 'vscatter:excl'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(NODE, {'state=job-exclusive': 3})

        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state=maintenance': 3})
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

        self.server.sigjob(jid, 'admin-resume', runas=ROOT_USER)
        self.server.expect(NODE, {'state=job-exclusive': 3})

    def test_degraded_resv(self):
        """
        Test if a reservation goes into the degraded state after its node is
        put into maintenance
        """

        # Submit a reservation
        r = Reservation(TEST_USER)
        r.set_attributes({'Resource_List.select': '1:ncpus=1',
                          'reserve_start': time.time() + 3600,
                          'reserve_end': time.time() + 7200})
        rid = self.server.submit(r)

        # See reservation is confirmed
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        d = self.server.expect(RESV, a, rid)

        # Submit a job and see it run
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '1:ncpus=1',
                          'Resource_List.walltime': 120})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Admin-suspend job
        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # See reservation in degreaded state
        a = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}
        d = self.server.expect(RESV, a, rid)

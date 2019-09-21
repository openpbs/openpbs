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

import time
from tests.functional import *


class TestAdminSuspend(TestFunctional):

    """
    Test the admin-suspend/admin-resume feature for node maintenance
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.server.create_vnodes('vn', a, 1, self.mom)

    def test_basic(self):
        """
        Test basic admin-suspend functionality
        """
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        j2 = Job(TEST_USER)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)

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

        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)

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
        self.server.expect(
            JOB, {'job_state': 'R', 'substate': 42}, attrop=PTL_AND, id=jid)

        # admin-suspend job
        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid})

        self.server.restart()

        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(NODE, {'maintenance_jobs': jid})

        # Checking licenses to avoid failure at resume since PBS licenses
        # might not be available and as a result resume fails
        rv = self.is_server_licensed(self.server)
        _msg = 'No license found on server %s' % (self.server.shortname)
        self.assertTrue(rv, _msg)

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
        except PbsManagerError as e:
            self.assertTrue('Illegal value for node state' in e.msg[0])

        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

        # Test to make sure we can't set the 'maintenance_jobs' attribute
        try:
            self.server.manager(
                MGR_CMD_SET, NODE,
                {'maintenance_jobs': 'foo'}, id='vn[0]', runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertTrue(
                'Cannot set attribute, read only or insufficient permission'
                in e.msg[0])

        self.server.expect(NODE, 'maintenance_jobs', op=UNSET, id='vn[0]')

        # Test to make sure regular users can't admin-suspend jobs
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(
            JOB, {'job_state': 'R', 'substate': 42}, attrop=PTL_AND, id=jid)

        try:
            self.server.sigjob(jid, 'admin-suspend', runas=TEST_USER)
        except PbsSignalError as e:
            self.assertTrue('Unauthorized Request' in e.msg[0])

        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

        # Test to make sure regular users can't admin-resume jobs
        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

        try:
            self.server.sigjob(jid, 'admin-resume', runas=TEST_USER)
        except PbsSignalError as e:
            self.assertTrue('Unauthorized Request' in e.msg[0])

        self.server.expect(JOB, {'job_state': 'S'}, id=jid)

    def test_wrong_state1(self):
        """
        Test using wrong resume signal is correctly rejected
        """

        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        self.server.sigjob(jid1, "suspend", runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)

        try:
            self.server.sigjob(jid1, "admin-resume", runas=ROOT_USER)
        except PbsSignalError as e:
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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        self.server.sigjob(jid1, "admin-suspend", runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(JOB, {'substate': 43}, id=jid1)

        try:
            self.server.sigjob(jid1, "resume", runas=ROOT_USER)
        except PbsSignalError as e:
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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        self.server.rerunjob(jid, extend='force')
        # Job eventually goes to R state after being requeued for short time
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        # Submit Job 2 to specific node
        j2 = Job(TEST_USER)
        j2.set_attributes({'Resource_List.select': '1:ncpus=1:vnode=vn[0]'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)

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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)
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
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

        # Admin-suspend job
        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # See reservation in degreaded state
        a = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}
        d = self.server.expect(RESV, a, rid)

    @timeout(400)
    def test_resv_jobend(self):
        """
        Test if a node goes back to free state when reservation ends and
        admin-suspended job is killed
        """

        # Submit a reservation
        r = Reservation(TEST_USER)
        r.set_attributes({'Resource_List.select': '1:ncpus=1',
                          'reserve_start': time.time() + 30,
                          'reserve_end': time.time() + 60})
        rid = self.server.submit(r)

        # See reservation is confirmed
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        d = self.server.expect(RESV, a, id=rid)

        # Submit a job
        j = Job(TEST_USER)
        rque = rid.split(".")
        j.set_attributes({'queue': rque[0]})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        # Wait for reservation to start
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|3')}
        d = self.server.expect(RESV, a, rid, offset=30)

        # job is running as well
        self.server.expect(
            JOB, {'job_state': 'R', 'substate': 42},
            id=jid, max_attempts=30)

        # Admin-suspend job
        self.server.sigjob(jid, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # Submit another job outside of reservation
        j = Job(TEST_USER)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        # Wait for the reservation to get over
        # Job also gets deleted and node state goes back to free
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=120)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

        # job2 starts running
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2, max_attempts=60)

    def test_que(self):
        """
        Test to check that job gets suspended on non-default queue
        """

        # create a high priority workq2 and a routeq
        a = {'queue_type': 'execution', 'started': 't', 'enabled': 't',
             'priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')
        a = {'queue_type': 'route', 'started': 't', 'enabled': 't',
             'route_destinations': 'workq2'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='route')

        # submit a normal job
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '1:ncpus=3'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        # submit a high priority job. Make sure job1 is suspended.
        j = Job(TEST_USER)
        j.set_attributes(
            {'Resource_List.select': '1:ncpus=3', 'queue': 'route'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)

        # Above will not cause node state to go to maintenance
        self.server.expect(
            NODE, {'state': (MATCH_RE, 'free|job-exclusive')}, id='vn[0]')

        # admin suspend job2
        self.server.sigjob(jid2, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')
        self.server.expect(JOB, {'job_state=S': 2})

        # Releasing job1 will fail and not change node state
        rv = self.server.sigjob(jid1, 'resume', runas=ROOT_USER, logerr='True')
        self.assertFalse(rv)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # deleting job1 will not change node state either
        self.server.deljob(jid1, wait=True)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # Admin-resume job2
        self.server.sigjob(jid2, 'admin-resume', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)
        self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

        # suspend the job
        self.server.sigjob(jid2, 'suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(
            NODE, {'state': (MATCH_RE, 'free|job-exclusive')}, id='vn[0]')

    def test_resume(self):
        """
        Test node state remains in maintenance until
        all jobs are not resumed
        """

        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.server.create_vnodes('vn', a, 3, self.mom, usenatvnode=True)

        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '3:ncpus=1',
                          'Resource_List.place': 'vscatter'})
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state=R': 3, 'substate=42': 3})
        self.server.expect(NODE, {'state=free': 3})

        # admin suspend first 2 jobs and let 3rd job run
        # First only suspend job1 and verify that it will
        # put all the nodes to maintenance state
        self.server.sigjob(jid1, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(NODE, {'state=maintenance': 3})
        self.server.sigjob(jid2, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state=S': 2})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        # submit a new job and it will be queued
        j = Job(TEST_USER)
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)

        # List all maintenance_jobs
        self.server.expect(NODE, {'maintenance_jobs': jid1 + "," + jid2})

        # resume 1 job that will not change node state
        self.server.sigjob(jid1, 'admin-resume', runas=ROOT_USER)
        self.server.expect(NODE, {'state=maintenance': 3})
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid3)

        # resume the remaining job
        self.server.sigjob(jid2, 'admin-resume', runas=ROOT_USER)
        self.server.expect(NODE, {'state=free': 3})
        self.server.expect(JOB, {'job_state=R': 4})

    def test_admin_resume_loop(self):
        """
        Test that running admin-resume in a loop will have no impact on PBS
        """

        # submit a job
        j = Job(TEST_USER)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        # admin suspend and resume job in a loop
        for x in range(15):
            self.server.sigjob(jid1, 'admin-suspend', runas=ROOT_USER)
            self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
            self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

            # sleep for sometime
            time.sleep(3)

            # resume the job
            self.server.sigjob(jid1, 'admin-resume', runas=ROOT_USER)
            self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
            self.server.expect(NODE, {'state': 'free'}, id='vn[0]')

    def test_custom_res(self):
        """
        Test that job will not run on a node in
        maintenance state if explicitly asking
        for a resource on that node
        """

        # create multiple vnodes
        a = {'resources_available.ncpus': 4, 'resources_available.mem': '4gb'}
        self.server.create_vnodes('vn', a, 3, self.mom, usenatvnode=True)

        # create a node level resource
        self.server.manager(
            MGR_CMD_CREATE, RSC, {'type': 'float', 'flag': 'nh'}, id="foo",
            runas=ROOT_USER)

        # set foo on vn[1]
        self.server.manager(
            MGR_CMD_SET, NODE, {'resources_available.foo': 5}, id='vn[1]',
            runas=ROOT_USER)

        # set foo in sched_config
        self.scheduler.add_resource('foo')

        # submit a few jobs
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': 'vnode=vn[1]'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        # admin suspend the job to put the node to maintenance
        self.server.sigjob(jid1, 'admin-suspend', runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[1]')

        # submit other jobs asking for specific resources on vn[1]
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.foo': '2'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        # submit more jobs. They should be running
        j = Job(TEST_USER)
        jid3 = self.server.submit(j)
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid4)

        # verify that vn[1] is still in maintenance and
        # job3 and job4 not running on vn[1]
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[1]')
        try:
            self.server.expect(JOB, {'exec_vnode': (MATCH_RE, 'vn[1]')},
                               id=jid3, max_attempts=20)
            self.server.expect(JOB, {'exec_vnode': (MATCH_RE, 'vn[1]')},
                               id=jid4, max_attempts=20)
        except Exception as e:
            self.assertFalse(e.rv)
            self.logger.info("jid3 and jid4 not running on vn[1] as expected")

    def test_list_jobs_1(self):
        """
        Test to list and set maintenance_jobs as various users
        """
        # This test is run with CLI mode only
        _m = self.server.get_op_mode()
        if _m != PTL_CLI:
            self.skipTest("Not all commands can be run with API mode")

        # submit a few jobs
        j = Job(TEST_USER)
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)
        jid3 = self.server.submit(j)

        # verify that all are running
        self.server.expect(JOB, {'job_state=R': 3, 'substate=42': 3})

        # admin-suspend 2 of them
        self.server.sigjob(jid2, 'admin-suspend', runas=ROOT_USER)
        self.server.sigjob(jid3, 'admin-suspend', runas=ROOT_USER)

        # node state is in maintenance
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # list maintenance_jobs as root
        self.server.expect(NODE, {'maintenance_jobs': jid2 + "," + jid3},
                           runas=ROOT_USER)

        # list maintenance jobs as user
        self.server.expect(NODE, {'maintenance_jobs': jid2 + "," + jid3},
                           runas=TEST_USER)

        # set an operator
        self.server.manager(MGR_CMD_SET, SERVER, {'operators': 'pbsoper@*'})

        # List all jobs in maintenance mode as operator
        self.server.expect(
            NODE, {'maintenance_jobs': jid2 + "," + jid3}, runas='pbsoper')

        # set maintenance_jobs as root
        try:
            self.server.manager(MGR_CMD_SET, NODE,
                                {'maintenance_jobs': jid1}, id='vn[0]',
                                runas=ROOT_USER)
        except PbsManagerError as e:
            self.assertFalse(e.rv)
            msg = "Cannot set attribute, read only" +\
                  " or insufficient permission  maintenance_jobs"
            self.assertTrue(msg in e.msg[0])

        # Set maintenance_jobs as operator
        try:
            self.server.manager(MGR_CMD_SET, NODE,
                                {'maintenance_jobs': jid1}, id='vn[0]',
                                runas='pbsoper')
        except PbsManagerError as e:
            self.assertFalse(e.rv)
            msg = "Cannot set attribute, read only" +\
                  " or insufficient permission  maintenance_jobs"
            self.assertTrue(msg in e.msg[0])

        # Set maintenance_jobs as user
        try:
            self.server.manager(MGR_CMD_SET, NODE,
                                {'maintenance_jobs': jid1}, id='vn[0]',
                                runas=TEST_USER)
        except PbsManagerError as e:
            self.assertFalse(e.rv)
            self.assertTrue("Unauthorized Request" in e.msg[0])

    def test_list_jobs_2(self):
        """
        Test to list maintenance_jobs when no job is admin-suspended
        """

        # Submit a few jobs
        j = Job(TEST_USER)
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)
        jid3 = self.server.submit(j)

        # verify that all are running
        self.server.expect(JOB, {'job_state=R': 3, 'substate=42': 3})

        # list maintenance_jobs. It should be empty
        self.server.expect(NODE, 'maintenance_jobs', op=UNSET, id='vn[0]')

        # Regular suspend a job
        self.server.sigjob(jid2, 'suspend', runas=ROOT_USER)

        # List maintenance_jobs again
        self.server.expect(NODE, 'maintenance_jobs', op=UNSET, id='vn[0]')

    def test_preempt_order(self):
        """
        Test that scheduler preempt_order has no impact
        on admin-suspend
        """

        # create a high priority queue
        a = {'queue_type': 'e', 'enabled': 't', 'started': 't',
             'priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id="highp")

        # set preempt_order to R
        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': 'R'},
                            runas=ROOT_USER)

        # submit a job
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': 'vnode=vn[0]'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid1)

        # submit a high priority job
        j = Job(TEST_USER)
        j.set_attributes({'queue': 'highp', 'Resource_List.select':
                          '1:ncpus=4:vnode=vn[0]'})
        jid2 = self.server.submit(j)

        # job2 is running and job1 is requeued
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

        # admin-suspend job1. It will fail
        try:
            self.server.sigjob(jid1, 'admin-suspend', logerr=False)
        except Exception as e:
            self.assertFalse(e.rv)

        # admin suspend job2
        self.server.sigjob(jid2, 'admin-suspend')
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # admin-resume job2. node state will become job-busy.
        self.server.sigjob(jid2, 'admin-resume')
        self.server.expect(NODE, {'state': 'job-busy'}, id='vn[0]')
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

    def test_hook(self):
        """
        List maintenance_jobs via hook
        """

        # Create and import a hook
        hook_name = "test"
        hook_body = """
import pbs

vn = pbs.server().vnode('vn[0]')
pbs.logmsg(pbs.LOG_DEBUG,\
"list of maintenance_jobs are %s" % vn.maintenance_jobs)
"""

        a = {'event': 'exechost_periodic', 'enabled': 'True', 'freq': 5}
        self.server.create_import_hook(hook_name, a, hook_body)

        # submit few jobs
        j = Job(TEST_USER)
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state=R': 2})

        # wait for the periodic hook
        time.sleep(5)

        # look for the log message
        self.mom.log_match("list of maintenance_jobs are None")

        # admin-suspend jobs
        self.server.sigjob(jid1, 'admin-suspend')
        self.server.sigjob(jid2, 'admin-suspend')

        # wait for periodic hook and check mom_log
        time.sleep(5)
        self.mom.log_match("list of maintenance_jobs are %s" %
                           ((jid1 + "," + jid2),))

        # admin-resume job1
        self.server.sigjob(jid1, 'admin-resume')

        # wait for periodic hook and check mom_log
        time.sleep(5)
        self.mom.log_match(
            "list of maintenance_jobs are %s" % (jid2,))

    def test_offline(self):
        """
        Test that if a node is put to offline
        and removed from maintenance state it
        remains offlined
        """

        # submit a job and admin-suspend it
        j1 = Job(TEST_USER)
        jid1 = self.server.submit(j1)
        j2 = Job(TEST_USER)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': "R", 'substate': 42}, id=jid1)
        self.server.expect(JOB, {'job_state': "R", 'substate': 42}, id=jid2)
        self.server.sigjob(jid1, 'admin-suspend')
        self.server.sigjob(jid2, 'admin-suspend')

        # node state is in maintenance
        self.server.expect(NODE, {'state': 'maintenance'}, id='vn[0]')

        # submit another job. It will be queued
        j3 = Job(TEST_USER)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)

        # mark the node as offline too
        self.server.manager(MGR_CMD_SET, NODE, {'state': 'offline'},
                            id='vn[0]')

        # delete job1 as user and resume job2
        self.server.deljob(jid1, wait=True, runas=TEST_USER)
        self.server.sigjob(jid2, 'admin-resume')

        # verify that node state is offline and
        # job3 is still queued
        self.server.expect(NODE, {'state': 'offline'}, id='vn[0]')
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)

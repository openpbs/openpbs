# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class TestResourceUsageLog(TestFunctional):

    """
    Test various scenarios in which resource usage is logged
    in the accounting logs
    """

    def setUp(self):
        TestFunctional.setUp(self)
        attr1 = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, attr1)
        attr2 = {'resources_available.mem': '200gb'}
        self.server.manager(MGR_CMD_SET, NODE, attr2, id=self.mom.shortname)

    def test_acclog_for_job_states(self):
        """
        Check accounting logs when a job completes successfully and when
        a job is deleted in Q or R state
        """
        a = {'Resource_List.select': '1:ncpus=1:mem=200gb'}
        j1 = Job(TEST_USER, a)
        j1.create_eatcpu_job(40)
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER, a)
        j2.create_eatcpu_job(30)
        jid2 = self.server.submit(j2)

        self.server.expect(JOB, {'job_state': 'R'}, jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        self.server.delete(jid2, wait=True)
        self.server.expect(JOB, {'job_state': 'F'},
                           offset=40, extend='x', id=jid1)

        j3 = Job(TEST_USER, a)
        j3.create_eatcpu_job()
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {'job_state': 'R'}, jid3)
        self.server.delete(jid3, wait=True)

        # No R record ; Only E record for job1 which finished
        self.server.accounting_match(
            msg='E;' + jid1 +
            '.*Exit_status=0.*resources_used.*run_count=1', id=jid1,
            regexp=True)
        self.server.accounting_match(
            msg='R;' + jid1, id=jid1, existence=False,
            max_attempts=10)

        # No R record, No E record for job2 which is in 'Q' state
        self.server.accounting_match(
            msg='R;' + jid2, id=jid2, existence=False,
            max_attempts=10)
        self.server.accounting_match(
            msg='E;' + jid2, id=jid2, existence=False,
            max_attempts=10)

        # No R record ; Only E record for job3 which was deleted
        # when in 'R' state
        self.server.accounting_match(
            msg='R;' + jid3, id=jid3, existence=False,
            max_attempts=10)
        self.server.accounting_match(
            msg='E;' + jid3 +
            '.*Exit_status=271.*resources_used.*run_count=1', id=jid3,
            regexp=True)

    def test_acclog_mom_down(self):
        """
        Check accounting logs when node is down and MoM is restarted
        """
        a = {ATTR_nodefailrq: 15}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        # Submit a job
        a = {'Resource_List.select': '1:ncpus=1:mem=20gb'}
        j = Job(TEST_USER, a)
        j.create_eatcpu_job()
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        # Submit a job array
        ja = Job(TEST_USER, attrs={
            ATTR_J: '1-2',
            'Resource_List.select': 'ncpus=1:mem=20gb'}
        )
        ja.create_eatcpu_job()
        jid_a = self.server.submit(ja)

        subjid1 = j.create_subjob_id(jid_a, 1)
        subjid2 = j.create_subjob_id(jid_a, 2)

        self.server.expect(JOB, {'job_state': 'R'}, subjid1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid2)

        self.assertTrue(self.server.isUp())
        self.assertTrue(self.mom.isUp())

        # kill -9 mom
        self.mom.signal('-KILL')

        # Verify that node is reported to be down.
        self.server.expect(NODE, {ATTR_NODE_state: 'down'},
                           id=self.mom.shortname, offset=15)

        self.server.expect(JOB, {'job_state': 'Q'}, jid)
        self.server.expect(JOB, {'job_state': 'Q'}, subjid1)
        self.server.expect(JOB, {'job_state': 'Q'}, subjid2)

        self.server.tracejob_match(
            msg='Job requeued, execution node .* down', id=jid,
            regexp=True)
        self.server.tracejob_match(
            msg='Job requeued, execution node .* down', id=subjid1,
            regexp=True)
        self.server.tracejob_match(
            msg='Job requeued, execution node .* down', id=subjid2,
            regexp=True)

        # now start mom
        self.mom.start()
        self.assertTrue(self.mom.isUp())
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        self.server.delete(jid, wait=True)
        self.server.delete(jid_a, wait=True)

        # job1 has 2 R records and a E record
        matches = self.server.accounting_match(
            msg='R;' + jid + '.*Exit_status=0.*resources_used.*run_count=1',
            id=jid, regexp=True, allmatch=True)
        self.assertEqual(len(matches), 2, " 2 R records expected")
        self.server.accounting_match(
            msg='E;' + jid +
            '.*Exit_status=271.*resources_used.*run_count=2',
            id=jid, regexp=True)

        # job array's subjobs have 2 R records and
        # the jobarray has E record with run_count=0
        matches = self.server.accounting_match(
            msg='R;' + re.escape(subjid1) +
            '.*Exit_status=0.*resources_used.*run_count=1',
            id=subjid1, regexp=True, allmatch=True)
        self.assertEqual(len(matches), 2, " 2 R records expected")
        matches = self.server.accounting_match(
            msg='R;' + re.escape(subjid2) +
            '.*Exit_status=0.*resources_used.*run_count=1',
            id=subjid2, regexp=True, allmatch=True)
        self.assertEqual(len(matches), 2, " 2 R records expected")
        self.server.accounting_match(
            msg='E;' + re.escape(jid_a) +
            '.*Exit_status=1.*run_count=0', id=jid_a, regexp=True)

    def test_acclog_job_multiple_qrerun(self):
        """
        Check for R record in accounting logs when job is
        requeued using qrerun command
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        # Submit job
        a = {'Resource_List.select': '1:ncpus=1:mem=20gb'}
        j = Job(TEST_USER, a)
        j.create_eatcpu_job()
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        # Submit job array
        ja = Job(TEST_USER, attrs={
            ATTR_J: '1-2',
            'Resource_List.select': 'ncpus=1:mem=20gb'}
        )
        ja.create_eatcpu_job()
        jid_a = self.server.submit(ja)
        subjid1 = j.create_subjob_id(jid_a, 1)
        subjid2 = j.create_subjob_id(jid_a, 2)
        self.server.expect(JOB, {'job_state': 'R'}, subjid1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid2)

        # Turn scheduling off before rerun
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # Rerun jobs first time
        self.server.rerunjob(jobid=jid)
        self.server.rerunjob(jobid=jid_a)

        self.server.expect(JOB, {'job_state': 'Q'}, jid)
        self.server.expect(JOB, {'job_state': 'Q'}, subjid1)
        self.server.expect(JOB, {'job_state': 'Q'}, subjid2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, jid)
        self.server.expect(JOB, {'job_state': 'R'}, subjid1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid2)

        # Rerun jobs second time
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.rerunjob(jobid=jid)
        self.server.rerunjob(jobid=jid_a)

        self.server.expect(JOB, {'job_state': 'Q'}, jid)
        self.server.expect(JOB, {'job_state': 'Q'}, subjid1)
        self.server.expect(JOB, {'job_state': 'Q'}, subjid2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        self.server.expect(JOB, {'job_state': 'R'}, subjid1)
        self.server.expect(JOB, {'job_state': 'R'}, subjid2)

        self.server.delete(jid, wait=True)
        self.server.delete(jid_a, wait=True)

        # Check for R records for every qrerun
        self.server.accounting_match(
            msg='R;' + jid +
            '.*Exit_status=-11.*resources_used.*run_count=1', id=jid,
            regexp=True)
        self.server.accounting_match(
            msg='R;' + jid +
            '.*Exit_status=-11.*resources_used.*run_count=2', id=jid,
            regexp=True)
        self.server.accounting_match(
            msg='E;' + jid +
            '.*Exit_status=271.*resources_used.*run_count=3', id=jid,
            regexp=True)

        matches = self.server.accounting_match(
            msg='R;' + re.escape(subjid1) +
            '.*Exit_status=-11.*resources_used.*run_count=1',
            id=subjid1, regexp=True, allmatch=True)
        self.assertEqual(len(matches), 2, "Expected 2 R records")
        matches = self.server.accounting_match(
            msg='R;' + re.escape(subjid1) +
            '.*Exit_status=-11.*resources_used.*run_count=1',
            id=subjid2, regexp=True, allmatch=True)
        self.assertEqual(len(matches), 2, "Expected 2 R records")
        self.server.accounting_match(
            msg='E;' + re.escape(jid_a) +
            '.*Exit_status=1.*run_count=0',
            id=jid_a, regexp=True)

    def test_acclog_force_requeue(self):
        """
        Check for resource usage when job is force requeued
        """
        a = {'Resource_List.select': '1:ncpus=1:mem=200gb'}
        j1 = Job(TEST_USER, a)
        j1.create_eatcpu_job()
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, jid1)

        # kill -9 mom
        self.mom.signal('-KILL')

        # Verify that nodes are reported to be down.
        self.server.expect(NODE, {ATTR_NODE_state: (MATCH_RE, 'down')},
                           id=self.mom.shortname, offset=15)
        self.server.rerunjob(jid1, extend='force')

        # Look for R record as job was force requeued
        self.server.accounting_match(
            msg='.*R;' +
            jid1 +
            '.*Exit_status=-11.*resources_used.*run_count=1',
            id=jid1,
            regexp=True)

    def test_acclog_services_restart(self):
        """
        Check for resource usage in accounting logs after
        PBS services are restarted
        """
        a = {'Resource_List.select': '1:ncpus=1:mem=200gb'}
        j1 = Job(TEST_USER, a)
        j1.create_eatcpu_job(60)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, jid1)

        # Restart PBS services
        PBSInitServices().restart()

        self.assertTrue(self.server.isUp())

        # Sleep so accounting logs get updated
        time.sleep(40)
        self.logger.info("Sleep for 40s so accounting log is updated")

        # Check for R record
        self.server.accounting_match(
            msg='R;' + jid1 + '.*resources_used.*run_count=1', id=jid1,
            regexp=True)

    def test_acclog_preempt_order(self):
        """
        Check for R record when editing preempt order to "R" and requeuing job
        """
        # Create a high priority queue
        a = {'queue_type': 'e', 'started': 't',
             'enabled': 't', 'priority': '180'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id="highp")
        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': 'R'})

        a = {'Resource_List.select': '1:ncpus=1:mem=200gb'}
        j1 = Job(TEST_USER, a)
        j1.create_eatcpu_job(30)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, jid1)

        a = {'Resource_List.select': '1:ncpus=1:mem=200gb', 'queue': 'highp'}
        j2 = Job(TEST_USER, a)
        j2.create_eatcpu_job(60)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid1)

        self.server.accounting_match(
            msg='.*R;' + jid1 +
            '.*Exit_status=-11.*resources_used.*run_count=1',
            id=jid1, regexp=True)

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


class TestqstatStateCount(TestFunctional):

    def setUp(self):
        TestFunctional.setUp(self)
        # set ncpus to a known value, 2 here
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a,
                            self.mom.shortname, expect=True)

    def submit_waiting_job(self, timedelta):
        """
        Submit a job in W state using -a option.
        The time specified for -a is current time + timedelta.
        """
        attribs = {ATTR_a: BatchUtils().convert_seconds_to_datetime(
            int(time.time()) + timedelta)}
        j = Job(TEST_USER, attribs)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'W'}, id=jid)
        return jid

    def find_state_counts(self):
        """
        From the output of qstat -Bf, parses the number of jobs in R, H, W
        and Q states and the value of total_jobs. Calculates the total number
        of jobs based on individual counts parsed. Returns these values in a
        dictionary.
        """
        counts = {}
        # Get output of qstat
        qstat = self.server.status(SERVER)
        state_count = qstat[0]['state_count'].split()
        all_state_count = 0
        for s in state_count:
            state = s.split(':')
            # Check for negative value
            self.assertGreaterEqual(
                int(state[1]), 0, 'state count has negative values')
            counts[state[0]] = int(state[1])
            all_state_count = all_state_count + int(state[1])
        counts['all_state_count'] = all_state_count
        counts['total_jobs'] = int(qstat[0]['total_jobs'])
        # Find queued count from output of qstat
        counts['expected_queued_count'] = (counts['total_jobs']
                                           - counts['Held']
                                           - counts['Waiting']
                                           - counts['Running'])
        return counts

    def verify_count(self):
        """
        The function does following checks based on output of qstat -Bf:
        1. total_jobs should match the number of jobs submitted
        2. queued_count should match total_jobs minus the number of jobs in
        state other than Q.
        (each job uses ncpus=1)
        """
        counts = self.find_state_counts()
        self.assertEqual(counts['total_jobs'],
                         counts['all_state_count'], 'Job count incorrect')
        self.assertEqual(counts['expected_queued_count'], counts['Queued'],
                         'Queued count incorrect')

    def test_queued_no_restart(self):
        """
        The test case verifies that the reported queued_count in qstat -Bf
        without a server restart is equal to the total_jobs - number of jobs in
        state other than Q.
        (each job uses ncpus=1)
        """
        jid = []
        # submit 4 jobs to ensure some jobs are in state Q as available ncpus=2
        for _ in range(4):
            j = Job(TEST_USER)
            jid.append(self.server.submit(j))

        a = {ATTR_h: None}
        j = Job(TEST_USER, a)
        self.server.submit(j)

        self.submit_waiting_job(600)

        # Wait for jobs to go in R state
        self.server.expect(JOB, {'job_state': 'R'}, id=jid[0])
        self.server.expect(JOB, {'job_state': 'R'}, id=jid[1])
        self.verify_count()

    def test_queued_restart(self):
        """
        The test case verifies that the reported queued_count in qstat -Bf
        is equal to total_jobs - number of jobs in state other than Q,
        even after the server is restarted.
        (each job uses ncpus=1)
        """
        jid = []
        # submit 4 jobs to ensure some jobs are in state Q as available ncpus=2
        for _ in range(4):
            j = Job(TEST_USER)
            jid.append(self.server.submit(j))

        a = {ATTR_h: None}
        j = Job(TEST_USER, a)
        self.server.submit(j)

        self.submit_waiting_job(600)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid[0])
        self.server.expect(JOB, {'job_state': 'R'}, id=jid[1])

        self.server.restart()
        self.verify_count()

    def test_queued_no_restart_multiple_queue(self):
        """
        The test case verifies that the queued_count reported in the output
        of qstat -Bf is equal to total_jobs - running jobs, without server
        restart.
        (each job uses ncpus=1)
        """
        # create 2 execution queues
        qname = ['workq1', 'workq2']
        for que in qname:
            a = {
                'queue_type': 'Execution',
                'enabled': 'True',
                'started': 'True'}
            self.server.manager(MGR_CMD_CREATE, QUEUE,
                                a, que, expect=True)

        q1_attr = {ATTR_queue: 'workq1'}
        q2_attr = {ATTR_queue: 'workq2'}

        # submit 1 job per queue to ensure a running job in each queue,
        # then submit 2 more jobs per queue i.e. overall 3 jobs in each queue
        j = Job(TEST_USER, q1_attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        j = Job(TEST_USER, q2_attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        for _ in range(2):
            j = Job(TEST_USER, q1_attr)
            self.server.submit(j)
            j = Job(TEST_USER, q2_attr)
            self.server.submit(j)

        self.verify_count()

    def test_queued_restart_multiple_queue(self):
        """
        The test case verifies that the queued_count reported in the output
        of qstat -Bf is equal to total_jobs - running jobs, even after the
        server is restart.
        (each job uses ncpus=1)
        """
        qname = ['workq1', 'workq2']
        for que in qname:
            a = {
                'queue_type': 'Execution',
                'enabled': 'True',
                'started': 'True'}
            self.server.manager(MGR_CMD_CREATE, QUEUE,
                                a, que, expect=True)

        q1_attr = {ATTR_queue: 'workq1'}
        q2_attr = {ATTR_queue: 'workq2'}

        # submit 1 job per queue to ensure a running job in each queue,
        # then submit 2 more jobs per queue i.e. overall 3 jobs in each queue
        j = Job(TEST_USER, q1_attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        j = Job(TEST_USER, q2_attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        for _ in range(2):
            j = Job(TEST_USER, q1_attr)
            self.server.submit(j)
            j = Job(TEST_USER, q2_attr)
            self.server.submit(j)

        self.server.restart()
        self.verify_count()

    def test_queued_sched_false(self):
        """
        This test case verifies that the value of queued_count in the output
        of qstat -Bf matches the number of jobs submitted (each using ncpus=1),
        as scheduling is set to False.
        """
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        for _ in range(4):
            j = Job(TEST_USER)
            self.server.submit(j)
        self.server.restart()
        self.verify_count()

    def test_wait_to_queued(self):
        """
        This test case verifies that when a job state changes from W to Q after
        server is restarted, the value of queued_count reported in the
        output of qstat -Bf is as expected.
        """
        a = {
            ATTR_stagein: 'inputData@' +
            self.server.hostname +
            ':' + os.path.join('noDir', 'nofile')}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'W'}, id=jid,
                           offset=30, interval=2)

        jid = self.submit_waiting_job(3)
        j = Job(TEST_USER)
        self.server.submit(j)
        j = Job(TEST_USER)
        self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid, offset=3)
        self.server.restart()
        self.verify_count()

    def test_job_state_count(self):
        """
        Testing if jobs in the 'W' state will cause
        the state_count to go negative or incorrect
        """
        # Failing stage-in operation, to put job into the waiting state
        a = {
            ATTR_stagein: 'inputData@' +
            self.server.hostname +
            ':/noDir/nofile'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'W'}, id=jid,
                           offset=30, interval=2)
        # Restart server
        self.server.restart()
        self.verify_count()

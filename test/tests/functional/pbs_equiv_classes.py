# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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

from tests.functional import *


class TestEquivClass(TestFunctional):
    """
    Test equivalence class functionality
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'resources_available.ncpus': 8}
        self.server.create_vnodes('vnode', a, 1, self.mom, usenatvnode=True)
        self.scheduler.set_sched_config({'log_filter': 2048})
        # capture the start time of the test for log matching
        self.t = int(time.time())

    def submit_jobs(self, num_jobs=1,
                    attrs={'Resource_List.select': '1:ncpus=1'},
                    user=TEST_USER):
        """
        Submit num_jobs number of jobs with attrs attributes for user.
        Return a list of job ids
        """
        ret_jids = []
        for n in range(num_jobs):
            J = Job(user, attrs)
            jid = self.server.submit(J)
            ret_jids += [jid]

        return ret_jids

    def test_basic(self):
        """
        Test the basic behavior of job equivalence classes: submit two
        different types of jobs and see they are in two different classes
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_select(self):
        """
        Test to see if jobs with select resources not in the resources line
        fall into the same equivalence class
        """
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'long', 'flag': 'nh'}, id='foo')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=1:foo=4'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=8'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes: one for the resource eating job and one
        # for the other two jobs. While jobs have different amounts of
        # the foo resource, foo is not on the resources line.
        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_place(self):
        """
        Test to see if jobs with different place statements
        fall into the different equivalence classes
        """
        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'free'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes: one for the resource eating job and
        # one for each place statement
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_reslist1(self):
        """
        Test to see if jobs with resources in Resource_List that are not in
        the sched_config resources line fall into the same equivalence class
        """
        self.server.manager(MGR_CMD_CREATE, RSC, {'type': 'string'},
                            id='baz')
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.software': 'foo'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.software': 'bar'}
        jids2 = self.submit_jobs(3, a)

        a = {'Resource_List.baz': 'foo'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.baz': 'bar'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes.  One for the resource eating job and
        # one for the rest.  The rest of the jobs have differing values of
        # resources not on the resources line.  They fall into one class.
        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_reslist2(self):
        """
        Test to see if jobs with resources in Resource_List that are in the
        sched_config resources line fall into the different equivalence classes
        """
        self.server.manager(MGR_CMD_CREATE, RSC, {'type': 'string'},
                            id='baz')

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})
        self.scheduler.add_resource('software')
        self.scheduler.add_resource('baz')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.software': 'foo'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.software': 'bar'}
        jids2 = self.submit_jobs(3, a)

        a = {'Resource_List.baz': 'foo'}
        jids3 = self.submit_jobs(3, a)

        a = {'Resource_List.baz': 'bar'}
        jids4 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each value of software and baz.
        m = self.scheduler.log_match("Number of job equivalence classes: 5",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_nolimits(self):
        """
        Test to see that jobs from different users, groups, and projects
        all fall into the same equivalence class when there are no limits
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        jids1 = self.submit_jobs(3, user=TEST_USER)
        jids2 = self.submit_jobs(3, user=TEST_USER2)

        b = {'group_list': TSTGRP1, 'Resource_List.select': '1:ncpus=8'}
        jids3 = self.submit_jobs(3, a, TEST_USER1)

        b = {'group_list': TSTGRP2, 'Resource_List.select': '1:ncpus=8'}
        jids4 = self.submit_jobs(3, a, TEST_USER1)

        b = {'project': 'p1', 'Resource_List.select': '1:ncpus=8'}
        jids5 = self.submit_jobs(3, a)

        b = {'project': 'p2', 'Resource_List.select': '1:ncpus=8'}
        jids6 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes: one for the resource eating job and one
        # for the rest.  Since there are no limits, user, group, nor project
        # are taken into account
        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)

    def test_user(self):
        """
        Test to see that jobs from different users fall into the same
        equivalence class without user limits set
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        jids1 = self.submit_jobs(3, user=TEST_USER)
        jids2 = self.submit_jobs(3, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes: One for the resource eating job and
        # one for the rest.  Since there are no limits, both users are
        # in one class.
        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_user_server(self):
        """
        Test to see that jobs from different users fall into different
        equivalence classes with server hard limits set
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run': '[u:PBS_GENERIC=4]'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        jids1 = self.submit_jobs(3, user=TEST_USER)
        jids2 = self.submit_jobs(3, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job
        # and one for each user.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_user_server_soft(self):
        """
        Test to see that jobs from different users fall into different
        equivalence classes with server soft limits set
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run_soft': '[u:PBS_GENERIC=4]'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        jids1 = self.submit_jobs(3, user=TEST_USER)
        jids2 = self.submit_jobs(3, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each user.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_user_queue(self):
        """
        Test to see that jobs from different users fall into different
        equivalence classes with queue limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[u:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        jids1 = self.submit_jobs(3, user=TEST_USER)
        jids2 = self.submit_jobs(3, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each user.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_user_queue_soft(self):
        """
        Test to see that jobs from different users fall into different
        equivalence classes with queue soft limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run_soft': '[u:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        jids1 = self.submit_jobs(3, user=TEST_USER)
        jids2 = self.submit_jobs(3, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each user.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_group(self):
        """
        Test to see that jobs from different groups fall into the same
        equivalence class without group limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'group_list': TSTGRP1}
        jids1 = self.submit_jobs(3, a, TEST_USER1)

        a = {'group_list': TSTGRP2}
        jids2 = self.submit_jobs(3, a, TEST_USER1)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes: One for the resource eating job and
        # one for the rest.  Since there are no limits, both groups are
        # in one class.
        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_group_server(self):
        """
        Test to see that jobs from different groups fall into different
        equivalence class server group limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run': '[g:PBS_GENERIC=4]'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'group_list': TSTGRP1}
        jids1 = self.submit_jobs(3, a, TEST_USER1)

        a = {'group_list': TSTGRP2}
        jids2 = self.submit_jobs(3, a, TEST_USER1)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each group.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_group_server_soft(self):
        """
        Test to see that jobs from different groups fall into different
        equivalence class server soft group limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run_soft': '[g:PBS_GENERIC=4]'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'group_list': TSTGRP1}
        jids1 = self.submit_jobs(3, a, TEST_USER1)

        a = {'group_list': TSTGRP2}
        jids2 = self.submit_jobs(3, a, TEST_USER1)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each group.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_group_queue(self):
        """
        Test to see that jobs from different groups fall into different
        equivalence class queue group limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[g:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'group_list': TSTGRP1}
        jids1 = self.submit_jobs(3, a, TEST_USER1)

        a = {'group_list': TSTGRP2}
        jids2 = self.submit_jobs(3, a, TEST_USER1)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each group.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_group_queue_soft(self):
        """
        Test to see that jobs from different groups fall into different
        equivalence class queue group soft limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run_soft': '[g:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'group_list': TSTGRP1}
        jids1 = self.submit_jobs(3, a, TEST_USER1)

        a = {'group_list': TSTGRP2}
        jids2 = self.submit_jobs(3, a, TEST_USER1)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each group.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_proj(self):
        """
        Test to see that jobs from different projects fall into the same
        equivalence class without project limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'project': 'p1'}
        jids1 = self.submit_jobs(3, a)

        a = {'project': 'p2'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes: One for the resource eating job and
        # one for the rest.  Since there are no limits, both projects are
        # in one class.
        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_proj_server(self):
        """
        Test to see that jobs from different projects fall into different
        equivalence classes with server project limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run': '[p:PBS_GENERIC=4]'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'project': 'p1'}
        jids1 = self.submit_jobs(3, a)

        a = {'project': 'p2'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each project.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_proj_server_soft(self):
        """
        Test to see that jobs from different projects fall into different
        equivalence class server project soft limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run_soft': '[p:PBS_GENERIC=4]'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'project': 'p1'}
        jids1 = self.submit_jobs(3, a)

        a = {'project': 'p2'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each project.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_proj_queue(self):
        """
        Test to see that jobs from different groups fall into different
        equivalence class queue project limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[p:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'project': 'p1'}
        jids1 = self.submit_jobs(3, a)

        a = {'project': 'p2'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each project.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_proj_queue_soft(self):
        """
        Test to see that jobs from different groups fall into different
        equivalence class queue project soft limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run_soft': '[p:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'project': 'p1'}
        jids1 = self.submit_jobs(3, a)

        a = {'project': 'p2'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for each project.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_queue(self):
        """
        Test to see that jobs from different generic queues fall into
        the same equivalence class
        """

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='workq2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'priority': 120}, id='workq')

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'queue': 'workq'}
        jids1 = self.submit_jobs(3, a)

        a = {'queue': 'workq2'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes.  One for the resource eating job and
        # one for the rest.  There is nothing to differentiate the queues
        # so all jobs are in one class.
        m = self.scheduler.log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_queue_limits(self):
        """
        Test to see if jobs in a queue with limits use their queue as part
        of what defines their equivalence class.
        """

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='workq2')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='limits1')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='limits2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'priority': 120}, id='workq')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[o:PBS_ALL=20]'}, id='limits1')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run_soft': '[o:PBS_ALL=20]'}, id='limits2')

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'queue': 'workq'}
        jids1 = self.submit_jobs(3, a)

        a = {'queue': 'workq2'}
        jids2 = self.submit_jobs(3, a)

        a = {'queue': 'limits1'}
        jids3 = self.submit_jobs(3, a)

        a = {'queue': 'limits2'}
        jids4 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # 4 equivalence classes.  One for the resource eating job and
        # One for the queues without limits and one
        # each for the two queues with limits.
        m = self.scheduler.log_match("Number of job equivalence classes: 4",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_queue_nodes(self):
        """
        Test to see if jobs that are submitted into a queue with nodes
        associated with it fall into their own equivalence class
        """

        a = {'resources_available.ncpus': 8}
        self.server.create_vnodes('vnode', a, 2, self.mom, usenatvnode=True)

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'priority': 100}, id='workq2')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='nodes_queue')

        self.server.manager(MGR_CMD_SET, NODE,
                            {'queue': 'nodes_queue'}, id='vnode[0]')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'priority': 120}, id='workq')

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources on the normal node
        a = {'Resource_List.select': '1:ncpus=8', 'queue': 'workq'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        # Eat up all the resources on node associated to nodes_queue
        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'nodes_queue'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'workq'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'workq2'}
        jids2 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'nodes_queue'}
        jids3 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one class for the queue with nodes associated with it.
        # One class for normal queues.
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

        self.server.manager(MGR_CMD_UNSET, NODE, 'queue',
                            id='vnode[0]')

    def test_prime_queue(self):
        """
        Test to see if a job in a primetime queue has its queue be part of
        what defines its equivalence class.  Also see that jobs in anytime
        queues do not use queue as part of what determines their class
        """

        # Force primetime
        self.scheduler.holidays_set_day("weekday", prime="all",
                                        nonprime="none")
        self.scheduler.holidays_set_day("saturday", prime="all",
                                        nonprime="none")
        self.scheduler.holidays_set_day("sunday", prime="all",
                                        nonprime="none")

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'priority': 100},
                            id='anytime1')
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='anytime2')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'priority': 100},
                            id='p_queue1')
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='p_queue2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'priority': 120}, id='workq')

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8', 'queue': 'workq'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'anytime1'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'anytime2'}
        jids2 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'p_queue1'}
        jids3 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'p_queue2'}
        jids4 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Four equivalence classes.  One for the resource eating job and
        # one for the normal queues and one for each prime time queue
        m = self.scheduler.log_match("Number of job equivalence classes: 4",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_non_prime_queue(self):
        """
        Test to see if a job in a non-primetime queue has its queue be part of
        what defines its equivalence class.  Also see that jobs in anytime
        queues do not use queue as part of what determines their class
        """

        # Force non-primetime
        self.scheduler.holidays_set_day("weekday", prime="none",
                                        nonprime="all")
        self.scheduler.holidays_set_day("saturday", prime="none",
                                        nonprime="all")
        self.scheduler.holidays_set_day("sunday", prime="none",
                                        nonprime="all")

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'priority': 100},
                            id='anytime1')
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='anytime2')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'priority': 100},
                            id='np_queue1')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='np_queue2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'priority': 120}, id='workq')

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8', 'queue': 'workq'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'anytime1'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'anytime2'}
        jids2 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'np_queue1'}
        jids3 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4', 'queue': 'np_queue2'}
        jids4 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Four equivalence classes.  One for the resource eating job and
        # one for the normal queues and one for each non-prime time queue
        m = self.scheduler.log_match("Number of job equivalence classes: 4",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

    def test_ded_time_queue(self):
        """
        Test to see if a job in a dedicated time queue has its queue be part
        of what defines its equivalence class.  Also see that jobs in anytime
        queues do not use queue as part of what determines their class
        """

        # Force dedicated time
        now = time.time()
        self.scheduler.add_dedicated_time(start=now - 5, end=now + 3600)

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'priority': 100},
                            id='ded_queue1')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'priority': 100},
                            id='ded_queue2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'priority': 120}, id='workq')

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8', 'queue': 'workq'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=4',
             'Resource_List.walltime': 600, 'queue': 'ded_queue1'}
        jids1 = self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=4',
             'Resource_List.walltime': 600, 'queue': 'ded_queue2'}
        jids2 = self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes: One for the resource eating job and
        # one for each dedicated time queue job
        m = self.scheduler.log_match("Number of job equivalence classes: 3",
                                     max_attempts=10, starttime=self.t)
        self.assertTrue(m)

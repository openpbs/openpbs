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

        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 5",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

    def test_user_old(self):
        """
        Test to see that jobs from different users fall into different
        equivalence classes with old style limits set
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_user_run': 4})

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def test_user_queue_without_limits(self):
        """
        Test that jobs from different users submitted to a queue without
        a user limit set, will not create a multiple equivalence classes.
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[u:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources, this job will make first equiv class
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        # Create a new queue and submit jobs to this queue
        a = {'queue_type': 'e', 'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')

        a = {'Resource_List.select': '1:ncpus=1', ATTR_q: 'workq2'}
        jids1 = self.submit_jobs(3, user=TEST_USER, attrs=a)
        jids2 = self.submit_jobs(3, user=TEST_USER2, attrs=a)
        a = {'Resource_List.select': '1:ncpus=1'}
        J3 = Job(TEST_USER3, attrs=a)
        self.server.submit(J3)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes.  One for the resource eating job and
        # one for all jobs in workq2 and one for TEST_USER3
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def test_user_queue_without_soft_limits(self):
        """
        Test that jobs from different users submitted to a queue without
        a user soft limit set, will not create a multiple equivalence classes.
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run_soft': '[u:PBS_GENERIC=4]'}, id='workq')

        # Eat up all the resources, this job will make first equiv class
        a = {'Resource_List.select': '1:ncpus=8'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        # Create a new queue and submit jobs to this queue
        a = {'queue_type': 'e', 'started': 't', 'enabled': 't'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')

        a = {'Resource_List.select': '1:ncpus=1', ATTR_q: 'workq2'}
        jids1 = self.submit_jobs(3, user=TEST_USER, attrs=a)
        jids2 = self.submit_jobs(3, user=TEST_USER2, attrs=a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes.  One for the resource eating job and
        # one for all jobs in workq2.
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

    def test_group_old(self):
        """
        Test to see that jobs from different groups fall into different
        equivalence class old style group limits set
        """

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_group_run': 4})

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def test_queue(self):
        """
        Test to see that jobs from different generic queues fall into
        the same equivalence class
        """

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='workq2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'Priority': 120}, id='workq')

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
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

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
                            {'Priority': 120}, id='workq')

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
        self.scheduler.log_match("Number of job equivalence classes: 4",
                                 starttime=self.t)

    def test_queue_nodes(self):
        """
        Test to see if jobs that are submitted into a queue with nodes
        associated with it fall into their own equivalence class
        """

        a = {'resources_available.ncpus': 8}
        self.server.create_vnodes('vnode', a, 2, self.mom, usenatvnode=True)

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'Priority': 100}, id='workq2')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='nodes_queue')

        self.server.manager(MGR_CMD_SET, NODE,
                            {'queue': 'nodes_queue'}, id='vnode[0]')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'Priority': 120}, id='workq')

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

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
                             'enabled': 'True', 'Priority': 100},
                            id='anytime1')
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='anytime2')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'Priority': 100},
                            id='p_queue1')
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='p_queue2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'Priority': 120}, id='workq')

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
        self.scheduler.log_match("Number of job equivalence classes: 4",
                                 starttime=self.t)

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
                             'enabled': 'True', 'Priority': 100},
                            id='anytime1')
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='anytime2')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'Priority': 100},
                            id='np_queue1')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='np_queue2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'Priority': 120}, id='workq')

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
        self.scheduler.log_match("Number of job equivalence classes: 4",
                                 starttime=self.t)

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
                             'enabled': 'True', 'Priority': 100},
                            id='ded_queue1')

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True', 'Priority': 100},
                            id='ded_queue2')

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'Priority': 120}, id='workq')

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
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def test_job_array(self):
        """
        Test that various job types will fall into single equivalence
        class with same type of request.
        """

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=8', 'queue': 'workq'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        # Submit a job array
        j = Job(TEST_USER)
        j.set_attributes(
            {ATTR_J: '1-3:1',
             'Resource_List.select': '1:ncpus=8',
             'queue': 'workq'})
        jid = self.server.submit(j)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # One equivalence class
        self.scheduler.log_match("Number of job equivalence classes: 1",
                                 starttime=self.t)

    def test_reservation(self):
        """
        Test that similar jobs inside reservations falls under same
        equivalence class.
        """

        # Submit a reservation
        a = {'Resource_List.select': '1:ncpus=3',
             'reserve_start': int(time.time()) + 10,
             'reserve_end': int(time.time()) + 300, }
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        rname = rid.split('.')
        # Submit jobs inside reservation
        a = {ATTR_queue: rname[0], 'Resource_List.select': '1:ncpus=1'}
        jids1 = self.submit_jobs(3, a)

        # Submit jobs outside of reservations
        jids2 = self.submit_jobs(3)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes: one for jobs inside reservations
        # and one for regular jobs
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

    def test_time_limit(self):
        """
        Test that various time limits will have their own
        equivalence classes
        """

        # Submit a reservation
        a = {'Resource_List.select': '1:ncpus=8',
             'reserve_start': time.time() + 30,
             'reserve_end': time.time() + 300, }
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)

        rname = rid.split('.')

        # Submit jobs with cput limit inside reservation
        a = {'Resource_List.cput': '20', ATTR_queue: rname[0]}
        jid1 = self.submit_jobs(2, a)

        # Submit jobs with min and max walltime inside reservation
        a = {'Resource_List.min_walltime': '20',
             'Resource_List.max_walltime': '200',
             ATTR_queue: rname[0]}
        jid2 = self.submit_jobs(2, a)

        # Submit jobs with regular walltime inside reservation
        a = {'Resource_List.walltime': '20', ATTR_queue: rname[0]}
        jid3 = self.submit_jobs(2, a)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes: one for each job set
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def test_fairshare(self):
        """
        Test that scheduler do not create any equiv classes
        if fairshare is set
        """

        a = {'fair_share': 'true ALL',
             'fairshare_usage_res': 'ncpus*walltime',
             'unknown_shares': 10}
        self.scheduler.set_sched_config(a)

        # Submit jobs as different user
        jid1 = self.submit_jobs(8, user=TEST_USER1)
        jid2 = self.submit_jobs(8, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # One equivalence class
        self.scheduler.log_match("Number of job equivalence classes: 1",
                                 starttime=self.t)

        # Wait sometime for jobs to accumulate walltime
        time.sleep(20)

        # Submit another job
        self.t = int(time.time())
        jid3 = self.submit_jobs(1, user=TEST_USER3)

        # Look at the job equivalence classes again
        self.scheduler.log_match("Number of job equivalence classes: 1",
                                 starttime=self.t)

    def test_server_hook(self):
        """
        Test that job equivalence classes are updated
        when job attributes get updated by hooks
        """

        # Define a queuejob hook
        hook1 = """
import pbs
e = pbs.event()
e.job.Resource_List["walltime"] = 200
"""

        # Define a runjob hook
        hook2 = """
import pbs
e = pbs.event()
e.job.Resource_List["cput"] = 40
"""

        # Define a modifyjob hook
        hook3 = """
import pbs
e = pbs.event()
e.job.Resource_List["cput"] = 20
"""

        # Create a queuejob hook
        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook("t_q", a, hook1)

        # Create a runjob hook
        a = {'event': 'runjob', 'enabled': 'True'}
        self.server.create_import_hook("t_r", a, hook2)

        # Create a modifyjob hook
        a = {'event': 'modifyjob', 'enabled': 'True'}
        self.server.create_import_hook("t_m", a, hook3)

        # Turn scheduling off
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Submit jobs as different users
        a = {'Resource_List.ncpus': 2}
        jid1 = self.submit_jobs(4, a, user=TEST_USER1)
        jid2 = self.submit_jobs(4, a, user=TEST_USER2)
        jid3 = self.submit_jobs(4, a, user=TEST_USER3)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # One equivalence class
        self.scheduler.log_match("Number of job equivalence classes: 1",
                                 starttime=self.t)

        # Alter a queued job
        self.t = int(time.time())
        self.server.alterjob(jid3[2], {ATTR_N: "test"})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence classes: one is for queued jobs that
        # do not have cput set. 2 for the different cputime value
        # set by runjob and modifyjob hook
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def test_mom_hook(self):
        """
        Test for job equivalence classes with mom hooks.
        """

        # Create resource
        attrib = {}
        attrib['type'] = "string_array"
        attrib['flag'] = 'h'
        self.server.manager(MGR_CMD_CREATE, RSC, attrib, id='foo_str')

        # Create vnodes
        a = {'resources_available.ncpus': 4,
             'resources_available.foo_str': "foo,bar,buba"}
        self.server.create_vnodes('vnode', a, 4, self.mom)

        # Add resources to sched_config
        self.scheduler.add_resource("foo_str")

        # Create execjob_begin hook
        hook1 = """
import pbs
e = pbs.event()
j = e.job

if j.Resource_List["host"] == "vnode[0]":
    j.Resource_List["foo_str"] = "foo"
elif j.Resource_List["host"] == "vnode[1]":
    j.Resource_List["foo_str"] = "bar"
else:
    j.Resource_List["foo_str"] = "buba"
"""

        a = {'event': "execjob_begin", 'enabled': 'True'}
        self.server.create_import_hook("test", a, hook1)

        # Turn off the scheduling
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})

        # Submit jobs
        a = {'Resource_List.select': "vnode=vnode[0]:ncpus=2"}
        jid1 = self.submit_jobs(2, a)
        a = {'Resource_List.select': "vnode=vnode[1]:ncpus=2"}
        jid2 = self.submit_jobs(2, a)
        a = {'Resource_List.select': "vnode=vnode[2]:ncpus=2"}
        jid3 = self.submit_jobs(2, a)

        # Turn on the scheduling
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Three equivalence class for each string value
        # set by mom_hook
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def test_incr_decr(self):
        """
        Test for varying job equivalence class values
        """

        # Submit a job
        j = Job(TEST_USER,
                attrs={'Resource_List.select': '1:ncpus=8',
                       'Resource_List.walltime': '20'})
        jid1 = self.server.submit(j)

        # One equivalance class
        self.scheduler.log_match("Number of job equivalence classes: 1",
                                 starttime=self.t)

        # Submit another job
        self.t = int(time.time())
        j = Job(TEST_USER,
                attrs={'Resource_List.select': '1:ncpus=8',
                       'Resource_List.walltime': '30'})
        jid2 = self.server.submit(j)

        # Two equivalence classes
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

        # Submit another job
        self.t = int(time.time())
        j = Job(TEST_USER,
                attrs={'Resource_List.select': '1:ncpus=8',
                       'Resource_List.walltime': '40'})
        jid3 = self.server.submit(j)

        # Three equivalence classes
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

        # Delete job1
        self.server.delete(jid1, wait='True')

        # Rerun scheduling cycle
        self.t = int(time.time())
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # Two equivalence classes
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

        # Delete job2
        self.server.delete(jid2, wait='true')

        # Rerun scheduling cycle
        self.t = int(time.time())
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # One equivalence classes
        self.scheduler.log_match("Number of job equivalence classes: 1",
                                 starttime=self.t)

        # Delete job3
        self.server.delete(jid3, wait='true')

        time.sleep(1)  # adding delay to avoid race condition
        # Rerun scheduling cycle
        self.t = int(time.time())
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})

        # No message for equivalence class
        self.scheduler.log_match("Number of job equivalence classes",
                                 starttime=self.t,
                                 existence=False)
        self.logger.info(
            "Number of job equivalence classes message " +
            "not present when there are no jobs as expected")

    def test_server_queue_limit(self):
        """
        Test with mix of hard and soft limits
        on resources for users and groups
        """

        # Create workq2
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'e', 'started': 'True',
                             'enabled': 'True'}, id='workq2')

        # Set queue limit
        a = {
            'max_run': '[o:PBS_ALL=100],[g:PBS_GENERIC=20],\
                       [u:PBS_GENERIC=20],[g:tstgrp01 = 8],[u:%s=10]' %
                       str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, QUEUE,
                            a, id='workq2')

        a = {'max_run_res.ncpus':
             '[o:PBS_ALL=100],[g:PBS_GENERIC=50],\
             [u:PBS_GENERIC=20],[g:tstgrp01=13],[u:%s=12]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq2')

        a = {'max_run_res_soft.ncpus':
             '[o:PBS_ALL=100],[g:PBS_GENERIC=30],\
             [u:PBS_GENERIC=10],[g:tstgrp01=10],[u:%s=10]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq2')

        # Create server limits
        a = {
            'max_run': '[o:PBS_ALL=100],[g:PBS_GENERIC=50],\
            [u:PBS_GENERIC=20],[g:tstgrp01=13],[u:%s=13]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'max_run_soft':
             '[o:PBS_ALL=50],[g:PBS_GENERIC=25],[u:PBS_GENERIC=10],\
             [g:tstgrp01=10],[u:%s=10]' % str(TEST_USER1)}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        # Turn scheduling off
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'false'})

        # Submit jobs as pbsuser1 from group tstgrp01 in workq2
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP1, ATTR_q: 'workq2'}
        jid1 = self.submit_jobs(10, a, TEST_USER1)

        # Submit jobs as pbsuser1 from group tstgrp02 in workq2
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP2, ATTR_q: 'workq2'}
        jid2 = self.submit_jobs(10, a, TEST_USER1)

        # Submit jobs as pbsuser2 from tstgrp01 in workq2
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP1, ATTR_q: 'workq2'}
        jid3 = self.submit_jobs(10, a, TEST_USER2)

        # Submit jobs as pbsuser2 from tstgrp03 in workq2
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP3, ATTR_q: 'workq2'}
        jid4 = self.submit_jobs(10, a, TEST_USER2)

        # Submit jobs as pbsuser1 from tstgrp01 in workq
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP1, ATTR_q: 'workq'}
        jid5 = self.submit_jobs(10, a, TEST_USER1)

        # Submit jobs as pbsuser1 from tstgrp02 in workq
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP2, ATTR_q: 'workq'}
        jid6 = self.submit_jobs(10, a, TEST_USER1)

        # Submit jobs as pbsuser2 from tstgrp01 in workq
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP1, ATTR_q: 'workq'}
        jid7 = self.submit_jobs(10, a, TEST_USER2)

        # Submit jobs as pbsuser2 from tstgrp03 in workq
        a = {'Resource_List.select': '1:ncpus=1',
             'group_list': TSTGRP3, ATTR_q: 'workq'}
        jid8 = self.submit_jobs(10, a, TEST_USER2)

        self.t = int(time.time())

        # Run only one cycle
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # Eight equivalence classes; one for each combination of
        # users and groups
        self.scheduler.log_match("Number of job equivalence classes: 8",
                                 starttime=self.t)

    def test_preemption(self):
        """
        Suspended jobs are placed into their own equivalence class.  If
        they remain in the class they were in when they were queued, they
        can stop other jobs in that class from running.

        Equivalence classes are created in query-order.  Test to see if
        suspended job which comes first in query-order is added to its own
        class.
        """

        a = {'resources_available.ncpus': 1}
        self.server.create_vnodes('vnode', a, 4, self.mom, usenatvnode=True)

        a = {'queue_type': 'e', 'started': 't',
             'enabled': 't', 'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='expressq')

        (jid1, ) = self.submit_jobs(1)
        (jid2, ) = self.submit_jobs(1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        a = {'Resource_List.ncpus': 3, 'queue': 'expressq'}
        (jid3,) = self.submit_jobs(1, a)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        # Make sure one of the job is suspended
        sus_job = self.server.select(attrib={'job_state': 'S'})
        self.assertEqual(len(sus_job), 1,
                         "Either no or more jobs are suspended")
        self.logger.info("Job %s is suspended" % sus_job[0])

        (jid4,) = self.submit_jobs(1)
        self.server.expect(JOB, 'comment', op=SET)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)

        # 3 equivalence classes: 1 for jid2 and jid4; 1 for jid3; and 1 for
        # jid1 by itself because it is suspended.
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

        # Make sure suspended job is in its own class. If it is still in
        # jid4's class jid4 will not run.  This is because suspended job
        # will be considered first and mark the entire class as can not run.
        if sus_job[0] == jid2:
            self.server.deljob(jid1, wait=True)
        else:
            self.server.deljob(jid2, wait=True)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

    def test_preemption2(self):
        """
        Suspended jobs are placed into their own equivalence class.  If
        they remain in the class they were in when they were queued, they
        can stop other jobs in that class from running.

        Equivalence classes are created in query-order.  Test to see if
        suspended job which comes later in query-order is added to its own
        class instead of the class it was in when it was queued.
        """

        a = {'resources_available.ncpus': 1}
        self.server.create_vnodes('vnode', a, 4, self.mom, usenatvnode=True)

        a = {'queue_type': 'e', 'started': 't',
             'enabled': 't', 'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='expressq')

        a = {'preempt_sort': 'min_time_since_start'}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        (jid1,) = self.submit_jobs(1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        (jid2,) = self.submit_jobs(1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        # Jobs most recently started are suspended first.
        # Sleep for a second to force jid3 to be suspended.
        time.sleep(1)
        (jid3,) = self.submit_jobs(1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        a = {'Resource_List.ncpus': 2, 'queue': 'expressq'}
        (jid4,) = self.submit_jobs(1, a)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

        (jid5,) = self.submit_jobs(1)
        self.server.expect(JOB, 'comment', op=SET)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid5)

        # 3 equivalence classes: 1 for jid1, jid2, and jid5; 1 for jid4;
        # jid3 by itself because it is suspended.
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

        # Make sure jid3 is in its own class.  If it is still in jid5's class
        # jid5 will not run.  This is because jid3 will be considered first
        # and mark the entire class as can not run.

        self.server.deljob(jid2, wait=True)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid5)

    def test_multiple_job_preemption_order(self):
        """
        Test that when multiple jobs from same eqivalence class are
        preempted in reverse order they were created in and they are placed
        into the same equivalence class
        2) Test that for jobs of same type, suspended job which comes
        later in query-order is in its own equivalence class, and can
        be picked up to run along with the queued job in
        the same scheduling cycle.
        """

        # Create 1 vnode with 3 ncpus
        a = {'resources_available.ncpus': 3}
        self.server.create_vnodes('vnode', a, 1, self.mom, usenatvnode=True)

        # Create expressq
        a = {'queue_type': 'execution', 'started': 'true',
             'enabled': 'true', 'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='expressq')

        a = {'preempt_sort': 'min_time_since_start'}
        self.server.manager(MGR_CMD_SET, SCHED, a)

        # Submit 3 jobs with delay of 1 sec
        # Delay of 1 sec will preempt jid3 and then jid2.
        a = {'Resource_List.ncpus': 1}
        J = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        time.sleep(1)

        J2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        time.sleep(1)
        J3 = Job(TEST_USER, attrs=a)
        jid3 = self.server.submit(J3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        # Preempt jid3 with expressq, check 1 equivalence class is created
        a = {'Resource_List.ncpus': 1, 'queue': 'expressq'}
        Je = Job(TEST_USER, attrs=a)
        jid4 = self.server.submit(Je)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)
        self.t = int(time.time())

        # Preempt jid2, check no new equivalence class is created
        Je2 = Job(TEST_USER, attrs=a)
        jid5 = self.server.submit(Je2)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid5)

        # Only One equivalence class for jid2 and jid3 is present since both
        # suspended jobs are of same type and running on same vnode

        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

        # Add a job to Queue state
        a = {'Resource_List.ncpus': 1}
        J = Job(TEST_USER, attrs=a)
        jid6 = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid5)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid6)

        # Set scheduling to false before deleting jobs to free nodes, so that
        # suspended and queued jobs do not run. These jobs will be picked up
        # in the next scheduling cycle when scheduling is again set to true
        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'False'})

        # Delete one running, one suspended job and one of high priority job
        # This will leave 2 free nodes to pick up the suspended and queued job

        self.server.deljob([jid1, jid2, jid5])

        # if we use deljob(wait=True) starts the scheduling cycle if job
        # takes more time to be deleted.
        # The for loop below is to check that the jobs have been deleted
        # without kicking off a new scheduling cycle.

        deleted = False
        for _ in range(20):
            workq_dict = self.server.status(QUEUE, id='workq')[0]
            expressq_dict = self.server.status(QUEUE, id='expressq')[0]

            if workq_dict['total_jobs'] == '2'\
                    and expressq_dict['total_jobs'] == '1':
                deleted = True
                break
            else:
                # jobs take longer than one second to delete, use two seconds
                time.sleep(2)

        self.assertTrue(deleted)

        self.server.manager(MGR_CMD_SET, MGR_OBJ_SERVER,
                            {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid6)

    def test_multiple_equivalence_class_preemption(self):
        """
        This test is to test that -
        1) Suspended jobs of different types go to different equiv classes
        2) Different types of jobs suspended by qsig signal
        go to different equivalence classes
        3) Jobs of same type and same node on suspension by qsig
        or preemption go to same equivalence classes
        4) Same type of suspended jobs, when resumed after qsig
        and jobs suspended by preemption both go to same equivalence classes
        """

        # Create vnode with 4 ncpus
        a = {'resources_available.ncpus': 4}
        self.server.create_vnodes('vnode', a, 1, self.mom, usenatvnode=True)

        # Create a expressq
        a = {'queue_type': 'execution', 'started': 'true',
             'enabled': 'true', 'Priority': 150}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='expressq')

        # Submit regular job
        a = {'Resource_List.ncpus': 1}
        (jid1, jid2) = self.submit_jobs(2, a)

        # Submit a job with walltime
        a2 = {'Resource_List.ncpus': 1, 'Resource_List.walltime': 600}
        (jid3, jid4) = self.submit_jobs(2, a2)

        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

        # Suspend 1 job from each equivalence class
        self.server.sigjob(jobid=jid1, signal="suspend")
        self.server.sigjob(jobid=jid3, signal="suspend")

        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

        # Check that both suspended jobs go to different equivalence class
        # 1 for jid1, 1 for jid2, 1 for jid3, and 1 for jid4
        self.scheduler.log_match("Number of job equivalence classes: 4",
                                 starttime=self.t)

        # Start a high priority job to preempt jid 2 and jid4
        a = {'Resource_List.ncpus': 4, 'queue': 'expressq'}
        Je = Job(TEST_USER, attrs=a)
        jid5 = self.server.submit(Je)

        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid4)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid5)

        # Check only 3 equivalence class are present,
        # i.e 1 equivalence class for jid1 and jid2,1 equivalence class
        # for jid3 and jid4 and 1 equivalence class for jid5

        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)
        self.t = int(time.time())

        # Resume the jobs suspended by qsig
        # 1 second delay is added so that time of next logging moves ahead.
        # This will make sure log_match does not take previous entry.
        time.sleep(1)
        self.server.sigjob(jobid=jid1, signal="resume")
        self.server.sigjob(jobid=jid3, signal="resume")

        # On resume check that there are same number of equivalence classes
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)
        self.t = int(time.time())

        # delete the expressq jobs and check that the suspended jobs
        # go back to running state. equivalence classes=2 again
        self.server.deljob(jid5, wait=True)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

        # Check equivalence classes =2
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

    def test_held_jobs_equiv_class(self):
        """
        1) Test that held jobs do not go into another equivalence class.
        2) Running jobs do not go into a seperate equivalence class
        """

        a = {'resources_available.ncpus': 1}
        self.server.create_vnodes('vnode', a, 1, self.mom, usenatvnode=True)

        a = {'Resource_List.select': '1:ncpus=1', ATTR_h: None}
        J1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J1)

        a = {'Resource_List.select': '1:ncpus=1'}
        J2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(J2)

        self.server.expect(JOB, {'job_state': 'H'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        self.scheduler.log_match("Number of job equivalence classes: 1",
                                 starttime=self.t)

    def test_queue_resav(self):
        """
        Test that jobs in queues with resources_available limits use queue as
        part of the criteria of making an equivalence class
        """

        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vnode', a, 1, self.mom, usenatvnode=True)

        attrs = {'queue_type': 'Execution', 'started': 'True',
                 'enabled': 'True', 'resources_available.ncpus': 1,
                 'Priority': 10}
        self.server.manager(MGR_CMD_CREATE, QUEUE, attrs, id='workq2')

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        a = {'queue': 'workq', 'Resource_List.select': '1:ncpus=1'}
        a2 = {'queue': 'workq2', 'Resource_List.select': '1:ncpus=1'}
        J = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J)

        J = Job(TEST_USER, attrs=a2)
        jid2 = self.server.submit(J)

        J = Job(TEST_USER, attrs=a2)
        jid3 = self.server.submit(J)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid3)

        # 2 quivalence classes - one for jobs inside workq2
        # and one for jobs inside workq
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

    def test_overlap_resv(self):
        """
        Test that 2 overlapping reservation creates 2 different
        equivalence classes
        """

        # Submit a reservation
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': int(time.time()) + 20,
             'reserve_end': int(time.time()) + 300, }
        r1 = Reservation(TEST_USER, a)
        rid1 = self.server.submit(r1)
        r2 = Reservation(TEST_USER, a)
        rid2 = self.server.submit(r2)
        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid1)
        self.server.expect(RESV, a, id=rid2)

        r1name = rid1.split('.')
        r2name = rid2.split('.')
        a = {ATTR_queue: r1name[0], 'Resource_List.select': '1:ncpus=1'}
        j1 = Job(TEST_USER, a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, 'comment', op=SET, id=jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        j2 = Job(TEST_USER, a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, 'comment', op=SET, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        a = {ATTR_queue: r2name[0], 'Resource_List.select': '1:ncpus=1'}
        j3 = Job(TEST_USER, a)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, 'comment', op=SET, id=jid3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        j4 = Job(TEST_USER, a)
        jid4 = self.server.submit(j4)
        self.server.expect(JOB, 'comment', op=SET, id=jid4)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)

        # Wait for reservation to start
        self.server.expect(RESV, {'reserve_state=RESV_RUNNING': 2}, offset=20)

        # Verify that equivalence class is 2; one for
        # each reservation queue
        self.scheduler.log_match("Number of job equivalence classes: 2",
                                 starttime=self.t)

        # Verify that one job from R1 is running and
        # one job from R2 is running

        self.server.expect(JOB, {"job_state": 'R'}, id=jid1)
        self.server.expect(JOB, {"job_state": 'R'}, id=jid3)

    def test_limit_res(self):
        """
        Test when resources are being limited on, but those resources are not
        in the sched_config resources line.  Jobs requesting these resources
        should be split into their own equivalence classes.
        """
        a = {ATTR_RESC_TYPE: 'long'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='foores')

        a = {'max_run_res.foores': '[u:PBS_GENERIC=4]'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'Resource_List.foores': 1, 'Resource_List.select': '1:ncpus=1'}
        self.submit_jobs(2, a)
        a['Resource_List.foores'] = 2
        (_, jid4) = self.submit_jobs(2, a)
        self.server.expect(JOB, {'job_state=R': 3})
        self.server.expect(JOB, 'comment', op=SET, id=jid4)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)
        (jid5, ) = self.submit_jobs(1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid5)

        # Verify that equivalence class is 3; one for
        # foores=1 and one for  foores=2 and
        # one for no foores
        self.scheduler.log_match("Number of job equivalence classes: 3",
                                 starttime=self.t)

    def change_res(self, name, total, node_num, attribs):
        """
        Callback to change the value of memory on one of the node

        :param name: Name of the vnode which is being created
        :type name: str
        :param total: Total number of vnodes being created
        :type total: int
        :param node_num: Index of the node for which callback is being called
        :type node_num: int
        :param attribs: attributes of the node being created
        :type attribs: dict
        """
        if node_num % 2 != 0:
            attribs['resource_available.mem'] = '16gb'
        else:
            attribs['resource_available.mem'] = '4gb'
        return attribs

    def test_equiv_class_not_marked_on_suspend(self):
        """
        Test that if a job is suspended then scheduler does not mark its
        equivalence class as can_not_run within the same cycle when it gets
        suspended.
        """
        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vnode', a, 2, self.mom,
                                  attrfunc=self.change_res)

        # Create an express queue
        a = {'queue_type': 'execution', 'started': 'true',
             'enabled': 'true', 'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq2')
        # Set node sort key so that higher memory node comes up first
        a = {'node_sort_key': '"mem HIGH" ALL'}
        self.scheduler.set_sched_config(a)

        a = {'Resource_List.select': '1:ncpus=1:mem=4gb'}
        (jid1, ) = self.submit_jobs(1, a)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        # Turn off scheduling
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # submit another normal job
        (jid2, ) = self.submit_jobs(1, a)

        # submit a high priority job
        a = {'queue': 'wq2', 'Resource_List.select': '1:ncpus=2:mem=14gb',
             'Resource_List.place': 'excl'}
        (jidh, ) = self.submit_jobs(1, a)

        # Turn on scheduling
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jidh)

        # make sure that the second job ran in the same cycle as the high
        # priority job
        c = self.scheduler.cycles(lastN=3)
        for sched_cycle in c:
            if jidh.split('.')[0] in sched_cycle.sched_job_run:
                break
        self.assertIn(jid2.split('.')[0], sched_cycle.sched_job_run)

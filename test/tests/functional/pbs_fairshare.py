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


@tags('sched')
class TestFairshare(TestFunctional):

    """
    Test the pbs_sched fairshare functionality.  Note there are two
    fairshare tests in the standard smoke test that are not included here.
    """

    def set_up_resource_group(self):
        """
        Set up the resource_group file for test suite
        """
        self.scheduler.add_to_resource_group('group1', 10, 'root', 40)
        self.scheduler.add_to_resource_group('group2', 20, 'root', 60)
        self.scheduler.add_to_resource_group(TEST_USER, 11, 'group1', 50)
        self.scheduler.add_to_resource_group(TEST_USER1, 12, 'group1', 50)
        self.scheduler.add_to_resource_group(TEST_USER2, 21, 'group2', 60)
        self.scheduler.add_to_resource_group(TEST_USER3, 22, 'group2', 40)
        self.scheduler.fairshare.set_fairshare_usage(TEST_USER, 100)
        self.scheduler.fairshare.set_fairshare_usage(TEST_USER1, 100)
        self.scheduler.fairshare.set_fairshare_usage(TEST_USER3, 1000)

    def test_formula_keyword(self):
        """
        Test to see if 'fairshare_tree_usage' and 'fairshare_perc' are allowed
        to be set in the job_sort_formula
        """

        # manager() will throw a PbsManagerError exception if this fails
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_sort_formula': 'fairshare_tree_usage'})

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_sort_formula': 'fairshare_perc'})

        formula = 'pow(2,-(fairshare_tree_usage/fairshare_perc))'
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': formula})

        formula = 'fairshare_factor'
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': formula})

        formula = 'fair_share_factor'
        try:
            self.server.manager(
                MGR_CMD_SET, SERVER, {'job_sort_formula': formula})
        except PbsManagerError as e:
            self.assertTrue("Formula contains invalid keyword" in e.msg[0])

    def test_fairshare_formula(self):
        """
        Test fairshare in the formula.  Make sure the fairshare_tree_usage
        is correct
        """

        self.set_up_resource_group()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_sort_formula': 'fairshare_tree_usage'})
        J1 = Job(TEST_USER)
        jid1 = self.server.submit(J1)
        J2 = Job(TEST_USER1)
        jid2 = self.server.submit(J2)
        J3 = Job(TEST_USER2)
        jid3 = self.server.submit(J3)
        J4 = Job(TEST_USER3)
        jid4 = self.server.submit(J4)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        msg = ';Formula Evaluation = '
        self.scheduler.log_match(str(jid1) + msg + '0.1253')
        self.scheduler.log_match(str(jid2) + msg + '0.1253')
        self.scheduler.log_match(str(jid3) + msg + '0.5004')
        self.scheduler.log_match(str(jid4) + msg + '0.8330')

    def test_fairshare_formula2(self):
        """
        Test fairshare in the formula.  Make sure the fairshare_perc
        is correct
        """

        self.set_up_resource_group()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_sort_formula': 'fairshare_perc'})
        J1 = Job(TEST_USER)
        jid1 = self.server.submit(J1)
        J2 = Job(TEST_USER1)
        jid2 = self.server.submit(J2)
        J3 = Job(TEST_USER2)
        jid3 = self.server.submit(J3)
        J4 = Job(TEST_USER3)
        jid4 = self.server.submit(J4)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        msg = ';Formula Evaluation = '
        self.scheduler.log_match(str(jid1) + msg + '0.2')
        self.scheduler.log_match(str(jid2) + msg + '0.2')
        self.scheduler.log_match(str(jid3) + msg + '0.36')
        self.scheduler.log_match(str(jid4) + msg + '0.24')

    def test_fairshare_formula3(self):
        """
        Test fairshare in the formula.  Make sure entities with small usage
        are negatively affected by their high usage siblings.  Make sure that
        jobs run in the correct order.  Use fairshare_tree_usage in a
        pow() formula
        """

        self.set_up_resource_group()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        formula = 'pow(2,-(fairshare_tree_usage/fairshare_perc))'

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': formula})
        J1 = Job(TEST_USER2)
        jid1 = self.server.submit(J1)
        J2 = Job(TEST_USER3)
        jid2 = self.server.submit(J2)
        J3 = Job(TEST_USER)
        jid3 = self.server.submit(J3)
        J4 = Job(TEST_USER1)
        jid4 = self.server.submit(J4)
        t = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        msg = ';Formula Evaluation = '
        self.scheduler.log_match(str(jid1) + msg + '0.3816')
        self.scheduler.log_match(str(jid2) + msg + '0.0902')
        self.scheduler.log_match(str(jid3) + msg + '0.6477')
        self.scheduler.log_match(str(jid4) + msg + '0.6477')
        self.scheduler.log_match('Leaving Scheduling Cycle', starttime=t)

        c = self.scheduler.cycles(lastN=1)[0]
        job_order = [jid3, jid4, jid1, jid2]
        for i in range(len(job_order)):
            self.assertEqual(job_order[i].split('.')[0], c.political_order[i])

    def test_fairshare_formula4(self):
        """
        Test fairshare in the formula.  Make sure entities with small usage
        are negatively affected by their high usage siblings.  Make sure that
        jobs run in the correct order.  Use keyword fairshare_factor
        """

        self.set_up_resource_group()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        formula = 'fairshare_factor'

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': formula})

        J1 = Job(TEST_USER2)
        jid1 = self.server.submit(J1)
        J2 = Job(TEST_USER3)
        jid2 = self.server.submit(J2)
        J3 = Job(TEST_USER)
        jid3 = self.server.submit(J3)
        J4 = Job(TEST_USER1)
        jid4 = self.server.submit(J4)
        t = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        msg = ';Formula Evaluation = '
        self.scheduler.log_match(str(jid1) + msg + '0.3816')
        self.scheduler.log_match(str(jid2) + msg + '0.0902')
        self.scheduler.log_match(str(jid3) + msg + '0.6477')
        self.scheduler.log_match(str(jid4) + msg + '0.6477')
        self.scheduler.log_match('Leaving Scheduling Cycle', starttime=t)

        c = self.scheduler.cycles(lastN=1)[0]
        job_order = [jid3, jid4, jid1, jid2]
        for i in range(len(job_order)):
            self.assertEqual(job_order[i].split('.')[0], c.political_order[i])

    def test_fairshare_formula5(self):
        """
        Test fairshare in the formula with fair_share set to true in scheduler.
        Make sure formula takes precedence over fairshare usage. Output will be
        same as in test_fairshare_formula4.
        """

        self.set_up_resource_group()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})
        a = {'fair_share': "True ALL"}
        self.scheduler.set_sched_config(a)

        formula = 'fairshare_factor'

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': formula})

        J1 = Job(TEST_USER2, {'Resource_List.cput': 10})
        jid1 = self.server.submit(J1)
        J2 = Job(TEST_USER3, {'Resource_List.cput': 20})
        jid2 = self.server.submit(J2)
        J3 = Job(TEST_USER, {'Resource_List.cput': 30})
        jid3 = self.server.submit(J3)
        J4 = Job(TEST_USER1, {'Resource_List.cput': 40})
        jid4 = self.server.submit(J4)
        t = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        msg = ';Formula Evaluation = '
        self.scheduler.log_match(str(jid1) + msg + '0.3816')
        self.scheduler.log_match(str(jid2) + msg + '0.0902')
        self.scheduler.log_match(str(jid3) + msg + '0.6477')
        self.scheduler.log_match(str(jid4) + msg + '0.6477')
        self.scheduler.log_match('Leaving Scheduling Cycle', starttime=t)

        c = self.scheduler.cycles(start=t, lastN=1)[0]
        job_order = [jid3, jid4, jid1, jid2]
        for i in range(len(job_order)):
            self.assertEqual(job_order[i].split('.')[0], c.political_order[i])

    def test_fairshare_formula6(self):
        """
        Test fairshare in the formula.  Make sure entities with small usage
        are negatively affected by their high usage siblings.  Make sure that
        jobs run in the correct order.  Use keyword fairshare_factor
        with ncpus/walltime
        """

        self.set_up_resource_group()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        formula = 'fairshare_factor + (walltime/ncpus)'

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': formula})

        J1 = Job(TEST_USER2, {'Resource_List.ncpus': 1,
                              'Resource_List.walltime': "00:01:00"})
        jid1 = self.server.submit(J1)
        J2 = Job(TEST_USER3, {'Resource_List.ncpus': 2,
                              'Resource_List.walltime': "00:01:00"})
        jid2 = self.server.submit(J2)
        J3 = Job(TEST_USER, {'Resource_List.ncpus': 3,
                             'Resource_List.walltime': "00:02:00"})
        jid3 = self.server.submit(J3)
        J4 = Job(TEST_USER1, {'Resource_List.ncpus': 4,
                              'Resource_List.walltime': "00:02:00"})
        jid4 = self.server.submit(J4)
        t = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        msg = ';Formula Evaluation = '
        self.scheduler.log_match(str(jid1) + msg + '60.3816')
        self.scheduler.log_match(str(jid2) + msg + '30.0902')
        self.scheduler.log_match(str(jid3) + msg + '40.6477')
        self.scheduler.log_match(str(jid4) + msg + '30.6477')
        self.scheduler.log_match('Leaving Scheduling Cycle', starttime=t)

        c = self.scheduler.cycles(start=t, lastN=1)[0]
        job_order = [jid1, jid3, jid4, jid2]
        for i in range(len(job_order)):
            self.assertEqual(job_order[i].split('.')[0], c.political_order[i])

    def test_pbsfs(self):
        """
        Test to see if running pbsfs affects the scheduler's view of the
        fairshare usage.  This is done by calling the Scheduler()'s
        revert_to_defaults().  This will call pbsfs -e to remove all usage.
        """

        self.scheduler.add_to_resource_group(TEST_USER, 11, 'root', 10)
        self.scheduler.add_to_resource_group(TEST_USER1, 12, 'root', 10)
        self.scheduler.set_sched_config({'fair_share': 'True'})

        self.scheduler.fairshare.set_fairshare_usage(TEST_USER, 100)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        J1 = Job(TEST_USER)
        jid1 = self.server.submit(J1)
        J2 = Job(TEST_USER1)
        jid2 = self.server.submit(J2)

        self.scheduler.run_scheduling_cycle()

        c = self.scheduler.cycles(lastN=1)[0]
        job_order = [jid2, jid1]
        for i in range(len(job_order)):
            self.assertEqual(job_order[i].split('.')[0], c.political_order[i])

        self.server.deljob(id=jid1, wait=True)
        self.server.deljob(id=jid2, wait=True)
        self.scheduler.revert_to_defaults()

        # revert_to_defaults() will set the default scheduler's scheduling
        # back to true.  Need to turn it off again
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # Set TEST_USER1 to 50.  If revert_to_defaults() has affected the
        # scheduler's view of the fairshare usage, it's the only entity with
        # usage.  Its job will run second.  If revert_to_defaults() did
        # nothing, 50 is less than 100, so TEST_USER1's job will run first
        self.scheduler.add_to_resource_group(TEST_USER, 11, 'root', 10)
        self.scheduler.add_to_resource_group(TEST_USER1, 12, 'root', 10)
        self.scheduler.set_sched_config({'fair_share': 'True'})

        self.scheduler.fairshare.set_fairshare_usage(TEST_USER1, 50)

        J3 = Job(TEST_USER)
        jid3 = self.server.submit(J3)
        J4 = Job(TEST_USER1)
        jid4 = self.server.submit(J4)

        self.scheduler.run_scheduling_cycle()

        c = self.scheduler.cycles(lastN=1)[0]
        job_order = [jid3, jid4]
        for i in range(len(job_order)):
            self.assertEqual(job_order[i].split('.')[0], c.political_order[i])

    def test_fairshare_decay_min_usage(self):
        """
        Test that fairshare decay doesn't reduce the usage below 1
        """
        self.scheduler.set_sched_config({'fair_share': 'True'})
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 4095})
        self.scheduler.add_to_resource_group(TEST_USER, 10, 'root', 50)
        self.scheduler.fairshare.set_fairshare_usage(TEST_USER, 1)
        self.scheduler.set_sched_config({"fairshare_decay_time": "00:00:02"})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        t = time.time()
        time.sleep(3)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.scheduler.log_match("Decaying Fairshare Tree", starttime=t)

        # Check that TEST_USER's usage is 1
        fs = self.scheduler.fairshare.query_fairshare(name=str(TEST_USER))
        fs_usage = int(fs.usage)
        self.assertEqual(fs_usage, 1,
                         "Fairshare usage %d not equal to 1" % fs_usage)

    def test_fairshare_topjob(self):
        """
        Test that jobs are run in the augmented fairshare order after a topjob
        is added to the calendar
        """
        self.scheduler.set_sched_config({'fair_share': 'True'})
        self.scheduler.set_sched_config({'fairshare_usage_res': 'ncpus'})
        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        self.scheduler.add_to_resource_group(TEST_USER, 11, 'root', 10)
        self.scheduler.add_to_resource_group(TEST_USER1, 12, 'root', 10)
        self.scheduler.add_to_resource_group(TEST_USER2, 13, 'root', 10)
        a = {'resources_available.ncpus': 5}
        self.mom.create_vnodes(a, 1)
        a = {'Resource_List.select': '5:ncpus=1'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        j2 = Job(TEST_USER1, attrs=a)
        jid2 = self.server.submit(j2)
        j3 = Job(TEST_USER1, attrs=a)
        jid3 = self.server.submit(j3)
        j4 = Job(TEST_USER2, attrs=a)
        jid4 = self.server.submit(j4)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.scheduler.log_match(jid2 + ';Job is a top job and will run at')
        c = self.scheduler.cycles(lastN=1)[0]
        jorder = [jid2, jid4, jid3]
        jorder = [j.split('.')[0] for j in jorder]
        msg = 'Jobs ran out of order'
        self.assertEqual(jorder, c.political_order, msg)

    def test_fairshare_acct_name(self):
        """
        Test fairshare with fairshare_entity as Account_Name
        """
        self.scheduler.set_sched_config({'fair_share': 'True'})
        self.scheduler.set_sched_config({'fairshare_usage_res': 'ncpus'})
        self.scheduler.set_sched_config({'fairshare_entity': ATTR_A})

        self.scheduler.add_to_resource_group('acctA', 11, 'root', 10)
        self.scheduler.fairshare.set_fairshare_usage('acctA', 1)
        self.scheduler.add_to_resource_group('acctB', 12, 'root', 25)
        self.scheduler.fairshare.set_fairshare_usage('acctB', 1)

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': False})
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 1},
                            id=self.mom.shortname)
        a = {ATTR_A: 'acctA'}
        j1 = Job(attrs=a)
        j1.set_sleep_time(15)
        jid1 = self.server.submit(j1)

        a = {ATTR_A: 'acctB'}
        j2 = Job(attrs=a)
        j2.set_sleep_time(15)
        jid2 = self.server.submit(j2)

        j3 = Job(attrs=a)
        j3.set_sleep_time(15)
        jid3 = self.server.submit(j3)

        j4 = Job(attrs=a)
        j4.set_sleep_time(15)
        jid4 = self.server.submit(j4)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})

        # acctB has 2/3s of the shares, so 2 of its jobs will run before acctA
        # a second cycle has to be kicked between jobs to make sure the
        # scheduler acumulates the fairshare usage.
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3, offset=15)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1, offset=15)

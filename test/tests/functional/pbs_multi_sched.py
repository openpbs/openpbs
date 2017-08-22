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


class TestMultipleSchedulers(TestFunctional):

    """
    Test suite to test different scheduler interfaces
    """

    def setup_sc1(self):
        a = {'partition': 'P1,P4',
             'sched_host': self.server.hostname,
             'sched_port': '15050'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc1")
        self.scheds['sc1'].create_scheduler()
        self.scheds['sc1'].start()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1", expect=True)

    def setup_sc2(self):
        dir_path = '/var/spool/pbs/sched_dir'
        if not os.path.exists(dir_path):
            self.du.mkdir(path=dir_path, sudo=True)
        a = {'partition': 'P2',
             'sched_priv': os.path.join(dir_path, 'sched_priv_sc2'),
             'sched_log': os.path.join(dir_path, 'sched_logs_sc2'),
             'sched_host': self.server.hostname,
             'sched_port': '15051'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc2")
        self.scheds['sc2'].create_scheduler(dir_path)
        self.scheds['sc2'].start(dir_path)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc2", expect=True)

    def setup_sc3(self):
        a = {'partition': 'P3',
             'sched_host': self.server.hostname,
             'sched_port': '15052'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc3")
        self.scheds['sc3'].create_scheduler()
        self.scheds['sc3'].start()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc3", expect=True)

    def setup_queues_nodes(self):
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq2')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq3')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq4')
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq1', expect=True)
        p2 = {'partition': 'P2'}
        self.server.manager(MGR_CMD_SET, QUEUE, p2, id='wq2', expect=True)
        p3 = {'partition': 'P3'}
        self.server.manager(MGR_CMD_SET, QUEUE, p3, id='wq3', expect=True)
        p4 = {'partition': 'P4'}
        self.server.manager(MGR_CMD_SET, QUEUE, p4, id='wq4', expect=True)
        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vnode', a, 5, self.mom)
        self.server.manager(MGR_CMD_SET, NODE, p1, id='vnode[0]', expect=True)
        self.server.manager(MGR_CMD_SET, NODE, p2, id='vnode[1]', expect=True)
        self.server.manager(MGR_CMD_SET, NODE, p3, id='vnode[2]', expect=True)
        self.server.manager(MGR_CMD_SET, NODE, p4, id='vnode[3]', expect=True)

    def common_setup(self):
        self.setup_sc1()
        self.setup_sc2()
        self.setup_sc3()
        self.setup_queues_nodes()

    def check_vnodes(self, j, vnodes, jid):
        self.server.status(JOB, 'exec_vnode', id=jid)
        nodes = j.get_vnodes(j.exec_vnode)
        for vnode in vnodes:
            if vnode not in nodes:
                self.assertFalse(True, str(vnode) +
                                 " is not in exec_vnode list as expected")

    def test_set_sched_priv(self):
        """
        Test sched_priv can be only set to valid paths
        and check for appropriate comments
        """
        self.setup_sc1()
        if not os.path.exists('/var/sched_priv_do_not_exist'):
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_priv': '/var/sched_priv_do_not_exist'},
                                id="sc1")
        msg = 'PBS failed validation checks for sched_priv directory'
        a = {'sched_priv': '/var/sched_priv_do_not_exist',
             'comment': msg,
             'scheduling': 'False'}
        self.server.expect(SCHED, a, id='sc1', attrop=PTL_AND, max_attempts=10)
        pbs_home = self.server.pbs_conf['PBS_HOME']
        self.du.run_copy(self.server.hostname,
                         os.path.join(pbs_home, 'sched_priv'),
                         os.path.join(pbs_home, 'sc1_new_priv'),
                         recursive=True)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_priv': '/var/spool/pbs/sc1_new_priv'},
                            id="sc1")
        a = {'sched_priv': '/var/spool/pbs/sc1_new_priv'}
        self.server.expect(SCHED, a, id='sc1', max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        # Blocked by PP-1202 will revisit once its fixed
        # self.server.expect(SCHED, 'comment', id='sc1', op=UNSET)

    def test_set_sched_log(self):
        """
        Test sched_log can be only set to valid paths
        and check for appropriate comments
        """
        self.setup_sc1()
        if not os.path.exists('/var/sched_log_do_not_exist'):
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_log': '/var/sched_log_do_not_exist'},
                                id="sc1")
        a = {'sched_log': '/var/sched_log_do_not_exist',
             'comment': 'Unable to change the sched_log directory',
             'scheduling': 'False'}
        self.server.expect(SCHED, a, id='sc1', max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        pbs_home = self.server.pbs_conf['PBS_HOME']
        self.du.mkdir(path=os.path.join(pbs_home, 'sc1_new_logs'),
                      sudo=True)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_log': '/var/spool/pbs/sc1_new_logs'},
                            id="sc1")
        a = {'sched_log': '/var/spool/pbs/sc1_new_logs'}
        self.server.expect(SCHED, a, id='sc1', max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        # Blocked by PP-1202 will revisit once its fixed
        # self.server.expect(SCHED, 'comment', id='sc1', op=UNSET)

    def test_start_scheduler(self):
        """
        Test that scheduler wont start without appropriate folders created.
        Scheduler will log a message if started without partition. Test
        scheduler states down, idle, scheduling.
        """
        self.setup_queues_nodes()
        pbs_home = self.server.pbs_conf['PBS_HOME']
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            id="sc5")
        a = {'sched_host': self.server.hostname,
             'sched_port': '15055',
             'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SCHED, a, id="sc5")
        # Try starting without sched_priv and sched_logs
        ret = self.scheds['sc5'].start()
        self.server.expect(SCHED, {'state': 'down'}, id='sc5', max_attempts=10)
        msg = "sched_priv dir is not present for scheduler"
        self.assertTrue(ret['rc'], msg)
        self.du.run_copy(self.server.hostname,
                         os.path.join(pbs_home, 'sched_priv'),
                         os.path.join(pbs_home, 'sched_priv_sc5'),
                         recursive=True)
        ret = self.scheds['sc5'].start()
        msg = "sched_logs dir is not present for scheduler"
        self.assertTrue(ret['rc'], msg)
        self.du.run_copy(self.server.hostname,
                         os.path.join(pbs_home, 'sched_logs'),
                         os.path.join(pbs_home, 'sched_logs_sc5'),
                         recursive=True)
        ret = self.scheds['sc5'].start()
        self.scheds['sc5'].log_match(
            "Scheduler does not contain a partition",
            max_attempts=10, starttime=self.server.ctime)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'partition': 'P3'}, id="sc5")
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'Scheduling': 'True'}, id="sc5")
        self.server.expect(SCHED, {'state': 'idle'}, id='sc5', max_attempts=10)
        a = {'resources_available.ncpus': 100}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[2]', expect=True)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc5")
        for _ in xrange(500):
            j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3'})
            self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc5")
        self.server.expect(SCHED, {'state': 'scheduling'},
                           id='sc5', max_attempts=10)

    def test_resource_sched_reconfigure(self):
        """
        Test all schedulers will reconfigure while creating,
        setting or deleting a resource
        """
        self.common_setup()
        t = int(time.time())
        self.server.manager(MGR_CMD_CREATE, RSC, id='foo')
        for name in self.scheds:
            self.scheds[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)
        # sleeping to make sure we are not checking for the
        # same scheduler reconfiguring message again
        time.sleep(1)
        t = int(time.time())
        attr = {ATTR_RESC_TYPE: 'long'}
        self.server.manager(MGR_CMD_SET, RSC, attr, id='foo')
        for name in self.scheds:
            self.scheds[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)
        # sleeping to make sure we are not checking for the
        # same scheduler reconfiguring message again
        time.sleep(1)
        t = int(time.time())
        self.server.manager(MGR_CMD_DELETE, RSC, id='foo')
        for name in self.scheds:
            self.scheds[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)

    def test_remove_partition_sched(self):
        """
        Test that removing all the partitions from a scheduler
        unsets partition attribute on scheduler and update scheduler logs.
        """
        self.setup_sc1()
        # self.setup_sc2()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'partition': (DECR, 'P1')}, id="sc1")
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'partition': (DECR, 'P4')}, id="sc1")
        log_msg = "Scheduler does not contain a partition"
        self.scheds['sc1'].log_match(log_msg, max_attempts=10,
                                     starttime=self.server.ctime)
        # Blocked by PP-1202 will revisit once its fixed
        # self.server.manager(MGR_CMD_UNSET, SCHED, 'partition',
        #                    id="sc2", expect=True)

    def test_job_queue_partition(self):
        """
        Test job submitted to a queue associated to a partition will land
        into a node associated with that partition.
        """
        self.common_setup()
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, ['vnode[0]'], jid)
        self.scheds['sc1'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, ['vnode[1]'], jid)
        self.scheds['sc2'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, ['vnode[2]'], jid)
        self.scheds['sc3'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    def test_multiple_partition_same_sched(self):
        """
        Test that scheduler will serve the jobs from different
        partition and run on nodes assigned to respective partitions.
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=1'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.check_vnodes(j, ['vnode[0]'], jid1)
        self.scheds['sc1'].log_match(
            jid1 + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=1'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.check_vnodes(j, ['vnode[3]'], jid2)
        self.scheds['sc1'].log_match(
            jid2 + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=1'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.check_vnodes(j, ['vnode[0]'], jid3)
        self.scheds['sc1'].log_match(
            jid3 + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    def test_multiple_queue_same_partition(self):
        """
        Test multiple queue associated with same partition
        is serviced by same scheduler
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, ['vnode[0]'], jid)
        self.scheds['sc1'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq4')
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, ['vnode[0]'], jid)
        self.scheds['sc1'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    def test_preemption_highp_queue(self):
        """
        Test preemption occures only within queues
        which are assigned to same partition
        """
        self.common_setup()
        prio = {'Priority': 150, 'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, prio, id='wq4')
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        t = int(time.time())
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=2'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=2'})
        jid5 = self.server.submit(j)
        self.server.expect(JOB, ATTR_comment, op=SET, id=jid5)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid5)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.schedulers['sc1'].log_match(
            jid1 + ';Job preempted by suspension',
            max_attempts=10, starttime=t)

    def test_backfill_per_scheduler(self):
        """
        Test backfilling is applicable only per scheduler
        """
        self.common_setup()
        t = int(time.time())
        self.scheds['sc2'].set_sched_config(
            {'strict_ordering': 'True ALL'})
        a = {ATTR_queue: 'wq2',
             'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 60}
        j = Job(TEST_USER1, attrs=a)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, attrs=a)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.scheds['sc2'].log_match(
            jid2 + ';Job is a top job and will run at',
            max_attempts=10, starttime=t)
        a['queue'] = 'wq3'
        j = Job(TEST_USER1, attrs=a)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        j = Job(TEST_USER1, attrs=a)
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)
        self.scheds['sc3'].log_match(
            jid4 + ';Job is a top job and will run at',
            max_attempts=5, starttime=t, existence=False)

    def test_resource_per_scheduler(self):
        """
        Test resources will be considered only by scheduler
        to which resource is added in sched_config
        """
        self.common_setup()
        a = {'type': 'float', 'flag': 'nh'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='gpus')
        self.scheds['sc3'].add_resource("gpus")
        a = {'resources_available.gpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id='@default', expect=True)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:gpus=2',
                                   'Resource_List.walltime': 60})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:gpus=2',
                                   'Resource_List.walltime': 60})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        job_comment = "Not Running: Insufficient amount of resource: "
        job_comment += "gpus (R: 2 A: 0 T: 2)"
        self.server.expect(JOB, {'comment': job_comment}, id=jid2)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:gpus=2'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:gpus=2'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

    def test_restart_server(self):
        """
        Test after server restarts sched attributes are persistent
        """
        self.setup_sc1()
        sched_priv = os.path.join(
            self.server.pbs_conf['PBS_HOME'], 'sched_priv_sc1')
        sched_logs = os.path.join(
            self.server.pbs_conf['PBS_HOME'], 'sched_logs_sc1')
        a = {'sched_port': 15050,
             'sched_host': self.server.hostname,
             'sched_priv': sched_priv,
             'sched_log': sched_logs,
             'scheduling': 'True',
             'scheduler_iteration': 600,
             'state': 'idle',
             'sched_cycle_length': '00:20:00'}
        self.server.expect(SCHED, a, id='sc1',
                           attrop=PTL_AND, max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduler_iteration': 300,
                             'sched_cycle_length': '00:10:00'},
                            id='sc1')
        self.server.restart()
        a['scheduler_iteration'] = 300
        a['sched_cycle_length'] = '00:10:00'
        self.server.expect(SCHED, a, id='sc1',
                           attrop=PTL_AND, max_attempts=10)

    def test_resv_default_sched(self):
        """
        Test reservations will only go to defualt scheduler
        """
        self.setup_queues_nodes()
        t = int(time.time())
        r = Reservation(TEST_USER)
        a = {'Resource_List.select': '2:ncpus=1'}
        r.set_attributes(a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, rid)
        self.scheds['default'].log_match(
            rid + ';Reservation Confirmed',
            max_attempts=10, starttime=t)

    def test_job_sorted_per_scheduler(self):
        """
        Test jobs are sorted as per job_sort_formula
        inside each scheduler
        """
        self.common_setup()
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_sort_formula': 'ncpus'})
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="default")
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=1'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=2'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="default")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc3")
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=1'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc3")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

    def test_qrun_job(self):
        """
        Test jobs can be run by qrun by a newly created scheduler.
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        self.server.runjob(jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

    def test_run_limts_per_scheduler(self):
        """
        Test run_limits applied at server level is
        applied for every scheduler seperately.
        """
        self.common_setup()
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run': '[u:PBS_GENERIC=1]'})
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=1'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=1'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=1'})
        jc = "Not Running: User has reached server running job limit."
        self.server.expect(JOB, {'comment': jc}, id=jid2)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=1'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=1'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)
        jc = "Not Running: User has reached server running job limit."
        self.server.expect(JOB, {'comment': jc}, id=jid4)

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
import resource


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
        self.scheds['sc1'].set_sched_config({'log_filter': 2048})

    def setup_sc2(self):
        dir_path = os.path.join(os.sep, 'var', 'spool', 'pbs', 'sched_dir')
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
                         recursive=True, sudo=True)
        ret = self.scheds['sc5'].start()
        msg = "sched_logs dir is not present for scheduler"
        self.assertTrue(ret['rc'], msg)
        self.du.run_copy(self.server.hostname,
                         os.path.join(pbs_home, 'sched_logs'),
                         os.path.join(pbs_home, 'sched_logs_sc5'),
                         recursive=True, sudo=True)
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
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id="sc1", expect=True)
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
        Test preemption occures only within queues which are assigned
        to same partition and check for equivalence classes
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
        jid2 = self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        self.scheds['sc1'].log_match("Number of job equivalence classes: 1",
                                     max_attempts=10, starttime=t)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=2'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, ATTR_comment, op=SET, id=jid3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.scheds['sc1'].log_match(
            jid1 + ';Job preempted by suspension',
            max_attempts=10, starttime=t)
        # Two equivalence class one for suspended and one for remaining jobs
        self.scheds['sc1'].log_match("Number of job equivalence classes: 2",
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
            starttime=t)
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

    def test_multi_fairshare(self):
        """
        Test different schedulers have their own fairshare trees with
        their own usage
        """
        self.common_setup()
        default_shares = 10
        default_usage = 100

        sc1_shares = 20
        sc1_usage = 200

        sc2_shares = 30
        sc2_usage = 300

        sc3_shares = 40
        sc3_usage = 400

        self.scheds['default'].add_to_resource_group(TEST_USER, 10, 'root',
                                                     default_shares)
        self.scheds['default'].set_fairshare_usage(TEST_USER, default_usage)

        self.scheds['sc1'].add_to_resource_group(TEST_USER, 10, 'root',
                                                 sc1_shares)
        self.scheds['sc1'].set_fairshare_usage(TEST_USER, sc1_usage)

        self.scheds['sc2'].add_to_resource_group(TEST_USER, 10, 'root',
                                                 sc2_shares)
        self.scheds['sc2'].set_fairshare_usage(TEST_USER, sc2_usage)

        self.scheds['sc3'].add_to_resource_group(TEST_USER, 10, 'root',
                                                 sc3_shares)
        self.scheds['sc3'].set_fairshare_usage(TEST_USER, sc3_usage)

        # requery fairshare info from pbsfs
        default_fs = self.scheds['default'].query_fairshare()
        sc1_fs = self.scheds['sc1'].query_fairshare()
        sc2_fs = self.scheds['sc2'].query_fairshare()
        sc3_fs = self.scheds['sc3'].query_fairshare()

        n = default_fs.get_node(id=10)
        self.assertEquals(n.nshares, default_shares)
        self.assertEquals(n.usage, default_usage)

        n = sc1_fs.get_node(id=10)
        self.assertEquals(n.nshares, sc1_shares)
        self.assertEquals(n.usage, sc1_usage)

        n = sc2_fs.get_node(id=10)
        self.assertEquals(n.nshares, sc2_shares)
        self.assertEquals(n.usage, sc2_usage)

        n = sc3_fs.get_node(id=10)
        self.assertEquals(n.nshares, sc3_shares)
        self.assertEquals(n.usage, sc3_usage)

    def test_fairshare_usage(self):
        """
        Test the schedulers fairshare usage file and
        check the usage file is updating correctly or not
        """
        self.setup_sc1()
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'partition': 'P1'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        # Set resources to node
        resc = {'resources_available.ncpus': 1,
                'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, NODE, resc, self.mom.shortname)
        # Add entry to the resource group of multisched 'sc1'
        self.scheds['sc1'].add_to_resource_group('grp1', 100, 'root', 60)
        self.scheds['sc1'].add_to_resource_group('grp2', 200, 'root', 40)
        self.scheds['sc1'].add_to_resource_group(TEST_USER1,
                                                 101, 'grp1', 40)
        self.scheds['sc1'].add_to_resource_group(TEST_USER2,
                                                 102, 'grp1', 20)
        self.scheds['sc1'].add_to_resource_group(TEST_USER3,
                                                 201, 'grp2', 30)
        self.scheds['sc1'].add_to_resource_group(TEST_USER4,
                                                 202, 'grp2', 10)
        # Set scheduler iteration
        sc_attr = {'scheduler_iteration': 7,
                   'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SCHED, sc_attr, id='sc1')
        # Update scheduler config file
        sc_config = {'fair_share': 'True',
                     'fairshare_usage_res': 'ncpus*100'}
        self.scheds['sc1'].set_sched_config(sc_config)
        # submit jobs to multisched 'sc1'
        sc1_attr = {ATTR_queue: 'wq1',
                    'Resource_List.select': '1:ncpus=1',
                    'Resource_List.walltime': 10}
        sc1_J1 = Job(TEST_USER1, attrs=sc1_attr)
        sc1_jid1 = self.server.submit(sc1_J1)
        sc1_J2 = Job(TEST_USER2, attrs=sc1_attr)
        sc1_jid2 = self.server.submit(sc1_J2)
        sc1_J3 = Job(TEST_USER3, attrs=sc1_attr)
        sc1_jid3 = self.server.submit(sc1_J3)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # pbsuser1 job will run and other two will be queued
        self.server.expect(JOB, {'job_state': 'R'}, id=sc1_jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=sc1_jid3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=sc1_jid2)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # need to delete the running job because PBS has only 1 ncpu and
        # our work is also done with the job.
        # this step will decrease the execution time as well
        self.server.delete(sc1_jid1, wait=True)
        # pbsuser3 job will run after pbsuser1
        self.server.expect(JOB, {'job_state': 'R'}, id=sc1_jid3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=sc1_jid2)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # deleting the currently running job
        self.server.delete(sc1_jid3, wait=True)
        # pbsuser2 job will run in the end
        self.server.expect(JOB, {'job_state': 'R'}, id=sc1_jid2)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # deleting the currently running job
        self.server.delete(sc1_jid2, wait=True)
        # query fairshare and check usage
        sc1_fs_user1 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER1))
        self.assertEquals(sc1_fs_user1.usage, 101)
        sc1_fs_user2 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER2))
        self.assertEquals(sc1_fs_user2.usage, 101)
        sc1_fs_user3 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER3))
        self.assertEquals(sc1_fs_user3.usage, 101)
        sc1_fs_user4 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER4))
        self.assertEquals(sc1_fs_user4.usage, 1)
        # Restart the scheduler
        self.scheds['sc1'].restart()
        # Check the multisched 'sc1' usage file whether it's updating or not
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'False'},
                            id='sc1')
        sc1_J1 = Job(TEST_USER1, attrs=sc1_attr)
        sc1_jid1 = self.server.submit(sc1_J1)
        sc1_J2 = Job(TEST_USER2, attrs=sc1_attr)
        sc1_jid2 = self.server.submit(sc1_J2)
        sc1_J4 = Job(TEST_USER4, attrs=sc1_attr)
        sc1_jid4 = self.server.submit(sc1_J4)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # pbsuser4 job will run and other two will be queued
        self.server.expect(JOB, {'job_state': 'R'}, id=sc1_jid4)
        self.server.expect(JOB, {'job_state': 'Q'}, id=sc1_jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=sc1_jid2)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # deleting the currently running job
        self.server.delete(sc1_jid4, wait=True)
        # pbsuser1 job will run after pbsuser4
        self.server.expect(JOB, {'job_state': 'R'}, id=sc1_jid1)
        self.server.expect(JOB, {'job_state': 'Q'}, id=sc1_jid2)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # deleting the currently running job
        self.server.delete(sc1_jid1, wait=True)
        # pbsuser2 job will run in the end
        self.server.expect(JOB, {'job_state': 'R'}, id=sc1_jid2)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        # deleting the currently running job
        self.server.delete(sc1_jid2, wait=True)
        # query fairshare and check usage
        sc1_fs_user1 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER1))
        self.assertEquals(sc1_fs_user1.usage, 201)
        sc1_fs_user2 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER2))
        self.assertEquals(sc1_fs_user2.usage, 201)
        sc1_fs_user3 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER3))
        self.assertEquals(sc1_fs_user3.usage, 101)
        sc1_fs_user4 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER4))
        self.assertEquals(sc1_fs_user4.usage, 101)

    def test_sched_priv_change(self):
        """
        Test that when the sched_priv directory changes, all of the
        PTL internal scheduler objects (e.g. fairshare tree) are reread
        """

        new_sched_priv = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                      'sched_priv2')
        if os.path.exists(new_sched_priv):
            self.du.rm(path=new_sched_priv, recursive=True,
                       sudo=True, force=True)

        dflt_sched_priv = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                       'sched_priv')

        self.du.run_copy(src=dflt_sched_priv, dest=new_sched_priv,
                         recursive=True, sudo=True)
        self.setup_sc3()
        s = self.server.status(SCHED, id='sc3')
        old_sched_priv = s[0]['sched_priv']

        self.scheds['sc3'].add_to_resource_group(TEST_USER, 10, 'root', 20)
        self.scheds['sc3'].holidays_set_year(new_year="3000")
        self.scheds['sc3'].set_sched_config({'fair_share': 'True ALL'})

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_priv': new_sched_priv}, id='sc3')

        n = self.scheds['sc3'].fairshare_tree.get_node(id=10)
        self.assertFalse(n)

        y = self.scheds['sc3'].holidays_get_year()
        self.assertNotEquals(y, "3000")
        self.assertTrue(self.scheds['sc3'].
                        sched_config['fair_share'].startswith('false'))

        # clean up: revert_to_defaults() will remove the new sched_priv.  We
        # need to remove the old one
        self.du.rm(path=old_sched_priv, sudo=True, recursive=True, force=True)

    def test_fairshare_decay(self):
        """
        Test pbsfs's fairshare decay for multisched
        """
        self.setup_sc3()
        self.scheds['sc3'].add_to_resource_group(TEST_USER, 10, 'root', 20)
        self.scheds['sc3'].set_fairshare_usage(name=TEST_USER, usage=10)
        self.scheds['sc3'].decay_fairshare_tree()
        n = self.scheds['sc3'].fairshare_tree.get_node(id=10)
        self.assertTrue(n.usage, 5)

    def test_cmp_fairshare(self):
        """
        Test pbsfs's compare fairshare functionality for multisched
        """
        self.setup_sc3()
        self.scheds['sc3'].add_to_resource_group(TEST_USER, 10, 'root', 20)
        self.scheds['sc3'].set_fairshare_usage(name=TEST_USER, usage=10)
        self.scheds['sc3'].add_to_resource_group(TEST_USER2, 20, 'root', 20)
        self.scheds['sc3'].set_fairshare_usage(name=TEST_USER2, usage=100)

        user = self.scheds['sc3'].cmp_fairshare_entities(TEST_USER, TEST_USER2)
        self.assertEquals(user, str(TEST_USER))

    def test_pbsfs_invalid_sched(self):
        """
        Test pbsfs -I <sched_name> where sched_name does not exist
        """
        sched_name = 'foo'
        pbsfs_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                 'sbin', 'pbsfs') + ' -I ' + sched_name
        ret = self.du.run_cmd(cmd=pbsfs_cmd, sudo=True)
        err_msg = 'Scheduler %s does not exist' % sched_name
        self.assertEquals(err_msg, ret['err'][0])

    def test_pbsfs_no_fairshare_data(self):
        """
        Test pbsfs -I <sched_name> where sched_priv_<sched_name> dir
        does not exist
        """
        a = {'partition': 'P5',
             'sched_host': self.server.hostname,
             'sched_port': '15050'}
        self.server.manager(MGR_CMD_CREATE, SCHED, a, id="sc5")
        err_msg = 'Unable to access fairshare data: No such file or directory'
        try:
            # Only a scheduler object is created. Corresponding sched_priv
            # dir not created yet. Try to query fairshare data.
            self.scheds['sc5'].query_fairshare()
        except PbsFairshareError as e:
            self.assertTrue(err_msg in e.msg)

    def test_pbsfs_server_restart(self):
        """
        Verify that server restart has no impact on fairshare data
        """
        self.setup_sc1()
        self.scheds['sc1'].add_to_resource_group(TEST_USER, 20, 'root', 50)
        self.scheds['sc1'].set_fairshare_usage(name=TEST_USER, usage=25)
        n = self.scheds['sc1'].query_fairshare().get_node(name=str(TEST_USER))
        self.assertTrue(n.usage, 25)

        self.server.restart()
        n = self.scheds['sc1'].query_fairshare().get_node(name=str(TEST_USER))
        self.assertTrue(n.usage, 25)

    def test_pbsfs_revert_to_defaults(self):
        """
        Test if revert_to_defaults() works properly with multi scheds.
        revert_to_defaults() removes entities from resource_group file and
        removes their usage(with pbsfs -e)
        """
        self.setup_sc1()
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'partition': 'P1'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1', expect=True)
        a = {'partition': 'P1', 'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a,
                            id=self.mom.shortname, expect=True)

        self.scheds['sc1'].add_to_resource_group(TEST_USER,
                                                 11, 'root', 10)
        self.scheds['sc1'].add_to_resource_group(TEST_USER1,
                                                 12, 'root', 10)
        self.scheds['sc1'].set_sched_config({'fair_share': 'True'})
        self.scheds['sc1'].set_fairshare_usage(TEST_USER, 100)

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'False'},
                            id='sc1')
        j1 = Job(TEST_USER, attrs={ATTR_queue: 'wq1'})
        jid1 = self.server.submit(j1)
        j2 = Job(TEST_USER1, attrs={ATTR_queue: 'wq1'})
        jid2 = self.server.submit(j2)

        t_start = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        self.scheds['sc1'].log_match(
            'Leaving Scheduling Cycle', starttime=t_start)
        t_end = int(time.time())
        job_list = self.scheds['sc1'].log_match(
            'Considering job to run', starttime=t_start,
            allmatch=True, endtime=t_end)

        # job 1 runs second as it's run by an entity with usage = 100
        self.assertTrue(jid1 in job_list[0][1])

        self.server.deljob(id=jid1, wait=True)
        self.server.deljob(id=jid2, wait=True)

        # revert_to_defaults() does a pbsfs -I <sched_name> -e and cleans up
        # the resource_group file
        self.scheds['sc1'].revert_to_defaults()

        # Fairshare tree is trimmed now.  TEST_USER1 is the only entity with
        # usage set.  So its job, job2 will run second. If trimming was not
        # successful TEST_USER would still have usage=100 and job1 would run
        # second

        self.scheds['sc1'].add_to_resource_group(TEST_USER,
                                                 15, 'root', 10)
        self.scheds['sc1'].add_to_resource_group(TEST_USER1,
                                                 16, 'root', 10)
        self.scheds['sc1'].set_sched_config({'fair_share': 'True'})
        self.scheds['sc1'].set_fairshare_usage(TEST_USER1, 50)

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'False'},
                            id='sc1')
        j1 = Job(TEST_USER, attrs={ATTR_queue: 'wq1'})
        jid1 = self.server.submit(j1)
        j2 = Job(TEST_USER1, attrs={ATTR_queue: 'wq1'})
        jid2 = self.server.submit(j2)

        t_start = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        self.scheds['sc1'].log_match(
            'Leaving Scheduling Cycle', starttime=t_start)
        t_end = int(time.time())
        job_list = self.scheds['sc1'].log_match(
            'Considering job to run', starttime=t_start,
            allmatch=True, endtime=t_end)

        self.assertTrue(jid2 in job_list[0][1])

    def submit_jobs(self, num_jobs=1, attrs=None, user=TEST_USER):
        """
        Submit num_jobs number of jobs with attrs attributes for user.
        Return a list of job ids
        """
        if attrs is None:
            attrs = {'Resource_List.select': '1:ncpus=2'}
        ret_jids = []
        for _ in range(num_jobs):
            J = Job(user, attrs)
            jid = self.server.submit(J)
            ret_jids += [jid]

        return ret_jids

    def test_equiv_partition(self):
        """
        Test the basic behavior of job equivalence classes: submit two
        different types of jobs into 2 partitions and see they are
        in four different equivalence classes
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        # Eat up all the resources with the first job to each queue
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        self.submit_jobs(4, a)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        self.submit_jobs(4, a)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        self.scheds['sc1'].log_match("Number of job equivalence classes: 4",
                                     max_attempts=10, starttime=t)

    def test_equiv_multisched(self):
        """
        Test the basic behavior of job equivalence classes: submit two
        different types of jobs into 2 different schedulers and see they
        are in two different classes in each scheduler
        """
        self.setup_sc1()
        self.setup_sc2()
        self.setup_queues_nodes()
        self.scheds['sc2'].set_sched_config({'log_filter': 2048})
        t = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc2")

        # Eat up all the resources with the first job to each queue
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        self.submit_jobs(4, a)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq2'}
        self.submit_jobs(4, a)

        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'wq2'}
        self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc2")
        self.scheds['sc1'].log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=t)
        self.scheds['sc2'].log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=t)

    def test_select_partition(self):
        """
        Test to see if jobs with select resources not in the resources line
        fall into the same equivalence class and jobs in different partition
        fall into different equivalence classes
        """
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'long', 'flag': 'nh'}, id='foo')
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())
        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=1:foo=4', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=4', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=8', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=8', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")

        # Four equivalence classes: two for the resource eating job in each
        # partition and two for the other jobs in each partition. While jobs
        # have different amount of the foo resources which isn't in the
        # resources line
        self.scheds['sc1'].log_match("Number of job equivalence classes: 4",
                                     max_attempts=10, starttime=t)

    def test_select_res_partition(self):
        """
        Test to see if jobs with select resources in the resources line and
        in different partitions fall into the different equivalence class
        """
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'long', 'flag': 'nh'}, id='foo')
        self.setup_sc1()
        self.setup_queues_nodes()
        self.scheds['sc1'].add_resource("foo")
        t = int(time.time())
        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=1:foo=4', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=4', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=8', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=8', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")

        # Six equivalence classes: two for the resource eating jobs in each
        # partition and 4 for the other jobs requesting different amounts of
        # the foo resource in each partition.
        self.scheds['sc1'].log_match("Number of job equivalence classes: 6",
                                     max_attempts=10, starttime=t)

    def test_multiple_res_partition(self):
        """
        Test to see if jobs with select resources in the resources line
        with multiple custom resources fall into the different equiv class
        and jobs in different partitions fall into different equiv classes
        """
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'long', 'flag': 'nh'}, id='foo')
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string', 'flag': 'h'}, id='colour')
        self.setup_sc1()
        self.setup_queues_nodes()
        self.scheds['sc1'].add_resource("foo")
        self.scheds['sc1'].add_resource("colour")
        t = int(time.time())
        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=1:foo=4', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:foo=4', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:colour=blue',
             ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1:colour=blue',
             ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")

        # Six equivalence classes: two for the resource eating job in each
        # partition and four for the other jobs. While jobs have different
        # resource requests two for each resource in different partitions
        self.scheds['sc1'].log_match("Number of job equivalence classes: 6",
                                     max_attempts=10, starttime=t)

    def test_place_partition(self):
        """
        Test to see if jobs with different place statements and different
        partitions fall into the different equivalence classes
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2',
             ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2',
             ATTR_queue: 'wq4'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'free',
             ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'free',
             ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")

        # Six equivalence classes: two for the resource eating job in
        # each partition and one for each place statement in each partition
        self.scheds['sc1'].log_match("Number of job equivalence classes: 6",
                                     max_attempts=10, starttime=t)

    def test_nolimits_partition(self):
        """
        Test to see that jobs from different users, groups, and projects
        all fall into the same equivalence class when there are no limits
        but fall into different equivalence classes for each partition
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {ATTR_queue: 'wq1'}
        self.submit_jobs(3, a, user=TEST_USER)
        self.submit_jobs(3, a, user=TEST_USER2)
        a = {ATTR_queue: 'wq4'}
        self.submit_jobs(3, a, user=TEST_USER)
        self.submit_jobs(3, a, user=TEST_USER2)

        b = {'group_list': TSTGRP1, ATTR_queue: 'wq1'}
        self.submit_jobs(3, b, TEST_USER1)
        b = {'group_list': TSTGRP2, ATTR_queue: 'wq1'}
        self.submit_jobs(3, b, TEST_USER1)
        b = {'group_list': TSTGRP1, ATTR_queue: 'wq4'}
        self.submit_jobs(3, b, TEST_USER1)
        b = {'group_list': TSTGRP2, ATTR_queue: 'wq4'}
        self.submit_jobs(3, b, TEST_USER1)

        b = {'project': 'p1', ATTR_queue: 'wq1'}
        self.submit_jobs(3, b)
        b = {'project': 'p2', ATTR_queue: 'wq1'}
        self.submit_jobs(3, b)
        b = {'project': 'p1', ATTR_queue: 'wq4'}
        self.submit_jobs(3, b)
        b = {'project': 'p2', ATTR_queue: 'wq4'}
        self.submit_jobs(3, b)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")

        # Four equivalence classes: two for the resource eating job in each
        # partition and two for the rest. Since there are no limits, user,
        # group, nor project are taken into account
        self.scheds['sc1'].log_match("Number of job equivalence classes: 4",
                                     max_attempts=10, starttime=t)

    def test_limits_partition(self):
        """
        Test to see that jobs from different users fall into different
        equivalence classes with queue hard limits and partitions
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[u:PBS_GENERIC=1]'}, id='wq1')
        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[u:PBS_GENERIC=1]'}, id='wq4')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {ATTR_queue: 'wq1'}
        self.submit_jobs(3, a, user=TEST_USER1)
        self.submit_jobs(3, a, user=TEST_USER2)
        a = {ATTR_queue: 'wq4'}
        self.submit_jobs(3, a, user=TEST_USER1)
        self.submit_jobs(3, a, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")

        # Six equivalence classes. Two for the resource eating job in
        # different partitions and one for each user per partition.
        self.scheds['sc1'].log_match("Number of job equivalence classes: 6",
                                     max_attempts=10, starttime=t)

    def test_job_array_partition(self):
        """
        Test that various job types will fall into single equivalence
        class with same type of request and will only fall into different
        equivalence class if partition is different
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())
        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', 'queue': 'wq1'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', 'queue': 'wq4'}
        J = Job(TEST_USER1, attrs=a)
        self.server.submit(J)

        # Submit a job array
        j = Job(TEST_USER)
        j.set_attributes(
            {ATTR_J: '1-3:1',
             'Resource_List.select': '1:ncpus=2',
             'queue': 'wq1'})
        self.server.submit(j)
        j.set_attributes(
            {ATTR_J: '1-3:1',
             'Resource_List.select': '1:ncpus=2',
             'queue': 'wq4'})
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        # Two equivalence class one for each partition
        self.scheds['sc1'].log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=t)

    def test_equiv_suspend_jobs(self):
        """
        Test that jobs fall into different equivalence classes
        after they get suspended
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(J)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        J = Job(TEST_USER, attrs=a)
        jid3 = self.server.submit(J)
        self.server.submit(J)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        # 2 equivalence classes one for each partition
        self.scheds['sc1'].log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=t)
        t = int(time.time())
        # Make sure that Job is in R state before issuing a signal to suspend
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.sigjob(jobid=jid1, signal="suspend")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.sigjob(jobid=jid3, signal="suspend")
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        # 4 equivalance classes 2 for partition 2 for suspended jobs
        self.scheds['sc1'].log_match("Number of job equivalence classes: 4",
                                     max_attempts=10, starttime=t)

    def test_equiv_single_partition(self):
        """
        Test that jobs fall into same equivalence class if jobs fall
        into queues set to same partition
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        t = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'partition': 'P1'}, id='wq4')
        # Eat up all the resources with the first job to  wq1
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        self.submit_jobs(4, a)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'wq1'}
        self.submit_jobs(3, a)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_queue: 'wq4'}
        self.submit_jobs(3, a)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        # 2 equivalence classes one for each with different ncpus request
        # as both queues are having same partition
        self.scheds['sc1'].log_match("Number of job equivalence classes: 2",
                                     max_attempts=10, starttime=t)

    def test_list_multi_sched(self):
        """
        Test to verify that qmgr list sched works when multiple
        schedulers are present
        """

        self.setup_sc1()
        self.setup_sc2()
        self.setup_sc3()

        self.server.manager(MGR_CMD_LIST, SCHED)

        self.server.manager(MGR_CMD_LIST, SCHED, id="default")

        self.server.manager(MGR_CMD_LIST, SCHED, id="sc1")

        dir_path = os.path.join(os.sep, 'var', 'spool', 'pbs', 'sched_dir')
        a = {'partition': 'P2',
             'sched_priv': os.path.join(dir_path, 'sched_priv_sc2'),
             'sched_log': os.path.join(dir_path, 'sched_logs_sc2'),
             'sched_host': self.server.hostname,
             'sched_port': '15051'}
        self.server.manager(MGR_CMD_LIST, SCHED, a, id="sc2", expect=True)

        self.server.manager(MGR_CMD_LIST, SCHED, id="sc3")

        try:
            self.server.manager(MGR_CMD_LIST, SCHED, id="invalid_scname")
        except PbsManagerError as e:
            err_msg = "Unknown Scheduler"
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")

        # delete sc3 sched
        self.server.manager(MGR_CMD_DELETE, SCHED, id="sc3", sudo=True)

        try:
            self.server.manager(MGR_CMD_LIST, SCHED, id="sc3")
        except PbsManagerError as e:
            err_msg = "Unknown Scheduler"
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")

        self.server.manager(MGR_CMD_LIST, SCHED)

        self.server.manager(MGR_CMD_LIST, SCHED, id="default")

        self.server.manager(MGR_CMD_LIST, SCHED, id="sc1")

        self.server.manager(MGR_CMD_LIST, SCHED, id="sc2")

        # delete sc1 sched
        self.server.manager(MGR_CMD_DELETE, SCHED, id="sc1")

        try:
            self.server.manager(MGR_CMD_LIST, SCHED, id="sc1")
        except PbsManagerError as e:
            err_msg = "Unknown Scheduler"
            self.assertTrue(err_msg in e.msg[0],
                            "Error message is not expected")

    def test_job_sort_formula_threshold(self):
        """
        Test the scheduler attribute job_sort_formula_threshold for multisched
        """
        # Multisched setup
        self.setup_sc3()
        p3 = {'partition': 'P3'}
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True'}
        a.update(p3)
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1', expect=True)
        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vnode', a, 2, self.mom)
        self.server.manager(MGR_CMD_SET, NODE, p3, id='vnode[0]', expect=True)
        # Set job_sort_formula on the server
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': 'ncpus'})
        # Set job_sort_formula_threshold on the multisched
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'job_sort_formula_threshold': '2'},
                            id="sc3", expect=True)
        # Submit job to multisched
        j1_attrs = {ATTR_queue: 'wq1', 'Resource_List.ncpus': '1'}
        J1 = Job(TEST_USER, j1_attrs)
        jid_1 = self.server.submit(J1)
        # Submit job to default scheduler
        J2 = Job(TEST_USER, attrs={'Resource_List.ncpus': '1'})
        jid_2 = self.server.submit(J2)
        msg = {'job_state': 'Q',
               'comment': ('Not Running: Job is ' +
                           'under job_sort_formula threshold value')}
        self.server.expect(JOB, msg, id=jid_1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid_2)

    @staticmethod
    def cust_attr(name, totnodes, numnode, attrib):
        a = {}
        if numnode in range(0, 3):
            a['resources_available.switch'] = 'A'
        if numnode in range(3, 5):
            a['resources_available.switch'] = 'B'
        if numnode in range(6, 9):
            a['resources_available.switch'] = 'A'
            a['partition'] = 'P2'
        if numnode in range(9, 11):
            a['resources_available.switch'] = 'B'
            a['partition'] = 'P2'
        if numnode is 11:
            a['partition'] = 'P2'
        return dict(attrib.items() + a.items())

    def setup_placement_set(self):
        self.server.add_resource('switch', 'string_array', 'h')
        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes(
            'vnode', a, 12, self.mom, attrfunc=self.cust_attr)
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_key': 'switch'})
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_enable': 't'})

    def test_multi_sched_explicit_ps(self):
        """
        Test only_explicit_ps set to sched attr will be in affect
        and will not read from default scheduler
        """
        self.setup_placement_set()
        self.setup_sc2()
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'partition': 'P2'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq2')
        a = {'Resource_List.select': '1:ncpus=2'}
        j = Job(TEST_USER, attrs=a)
        j1id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j1id)
        nodes = ['vnode[5]']
        self.check_vnodes(j, nodes, j1id)
        a = {'Resource_List.select': '2:ncpus=2'}
        j = Job(TEST_USER, attrs=a)
        j2id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        nodes = ['vnode[3]', 'vnode[4]']
        self.check_vnodes(j, nodes, j2id)
        a = {'Resource_List.select': '3:ncpus=2'}
        j = Job(TEST_USER, attrs=a)
        j3id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j3id)
        nodes = ['vnode[0]', 'vnode[1]', 'vnode[2]']
        self.check_vnodes(j, nodes, j3id)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'only_explicit_psets': 't'}, id='sc2')
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq2'}
        j = Job(TEST_USER, attrs=a)
        j4id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j4id)
        nodes = ['vnode[9]']
        self.check_vnodes(j, nodes, j4id)
        a = {'Resource_List.select': '2:ncpus=2', ATTR_queue: 'wq2'}
        j = Job(TEST_USER, attrs=a)
        j5id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j5id)
        nodes = ['vnode[6]', 'vnode[7]']
        self.check_vnodes(j, nodes, j5id)
        a = {'Resource_List.select': '3:ncpus=2', ATTR_queue: 'wq2'}
        j = Job(TEST_USER, attrs=a)
        j6id = self.server.submit(j)
        self.server.expect(JOB, {
                           'job_state': 'Q',
                           'comment': 'Not Running: Placement set switch=A'
                           ' has too few free resources'}, id=j6id)

    def test_jobs_do_not_span_ps(self):
        """
        Test do_not_span_psets set to sched attr will be in affect
        and will not read from default scheduler
        """
        self.setup_placement_set()
        self.setup_sc2()
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'partition': 'P2'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq2')
        # Scheduler sc2 cannot span across placement sets
        self.server.manager(MGR_CMD_SET, SCHED, {
                            'do_not_span_psets': 't'}, id='sc2')
        self.server.manager(MGR_CMD_SET, SCHED, {
                            'scheduling': 't'}, id='sc2')
        a = {'Resource_List.select': '4:ncpus=2',  ATTR_queue: 'wq2'}
        j = Job(TEST_USER, attrs=a)
        j1id = self.server.submit(j)
        self.server.expect(
            JOB, {'job_state': 'Q', 'comment': 'Can Never Run: can\'t fit in '
                  'the largest placement set, and can\'t span psets'}, id=j1id)
        # Default scheduler can span as do_not_span_psets is not set
        a = {'Resource_List.select': '4:ncpus=2'}
        j = Job(TEST_USER, attrs=a)
        j2id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)

    def test_sched_preempt_enforce_resumption(self):
        """
        Test sched_preempt_enforce_resumption can be set to a multi sched
        and that even if topjob_ineligible is set for a preempted job
        and sched_preempt_enforce_resumption is set true , the
        preempted job will be calandered
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        prio = {'Priority': 150, 'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, prio, id='wq4')
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_preempt_enforce_resumption': 'true'},
                            id='sc1')
        self.server.manager(MGR_CMD_SET, SERVER, {'backfill_depth': '2'})

        # Submit a job
        j = Job(TEST_USER, {'Resource_List.walltime': '120',
                            'Resource_List.ncpus': '2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER, {'Resource_List.walltime': '120',
                            'Resource_List.ncpus': '2',
                            ATTR_queue: 'wq1'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        # Alter topjob_ineligible for running job
        self.server.alterjob(jid1, {ATTR_W: "topjob_ineligible = true"},
                             runas=ROOT_USER, logerr=True)
        self.server.alterjob(jid1, {ATTR_W: "topjob_ineligible = true"},
                             runas=ROOT_USER, logerr=True)

        # Create a high priority queue
        a = {'queue_type': 'e', 'started': 't',
             'enabled': 't', 'Priority': '150'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id="highp")

        # Submit 2 jobs to high priority queue
        j = Job(TEST_USER, {'queue': 'highp', 'Resource_List.walltime': '60',
                            'Resource_List.ncpus': '2'})
        jid3 = self.server.submit(j)
        j = Job(TEST_USER, {'queue': 'wq4', 'Resource_List.walltime': '60',
                            'Resource_List.ncpus': '2'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        # Verify that job1 is not calendered
        self.server.expect(JOB, 'estimated.start_time',
                           op=UNSET, id=jid1)
        # Verify that job2 is calendared
        self.server.expect(JOB, 'estimated.start_time',
                           op=SET, id=jid2)
        qstat = self.server.status(JOB, 'estimated.start_time',
                                   id=jid2)
        est_time = qstat[0]['estimated.start_time']
        self.assertNotEqual(est_time, None)
        self.scheds['sc1'].log_match(jid2 + ";Job is a top job",
                                     starttime=self.server.ctime)

    def set_primetime(self, ptime_start, ptime_end, scid='default'):
        """
        This function will set the prime time
        in holidays file
        """
        p_day = 'weekday'
        p_hhmm = time.strftime('%H%M', time.localtime(ptime_start))
        np_hhmm = time.strftime('%H%M', time.localtime(ptime_end))
        self.scheds[scid].holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'saturday'
        self.scheds[scid].holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'sunday'
        self.scheds[scid].holidays_set_day(p_day, p_hhmm, np_hhmm)

    def test_prime_time_backfill(self):
        """
        Test opt_backfill_fuzzy can be set to a multi sched and
        while calandering primetime/nonprimetime will be considered
        """
        self.setup_sc2()
        self.setup_queues_nodes()
        a = {'strict_ordering': "True   ALL"}
        self.scheds['sc2'].set_sched_config(a)
        # set primetime which will start after 30min
        prime_start = int(time.time()) + 1800
        prime_end = int(time.time()) + 3600
        self.set_primetime(prime_start, prime_end, scid='sc2')

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'opt_backfill_fuzzy': 'high'}, id='sc2')
        self.server.manager(MGR_CMD_SET, SERVER, {'backfill_depth': '2'})

        # Submit a job
        j = Job(TEST_USER, {'Resource_List.walltime': '60',
                            'Resource_List.ncpus': '2',
                            ATTR_queue: 'wq2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        j = Job(TEST_USER1, {'Resource_List.ncpus': '2',
                             ATTR_queue: 'wq2'})
        jid2 = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)

        # Verify that job2 is calendared to start at primetime start
        self.server.expect(JOB, 'estimated.start_time',
                           op=SET, id=jid2)
        qstat = self.server.status(JOB, 'estimated.start_time',
                                   id=jid2)
        est_time = qstat[0]['estimated.start_time']
        est_epoch = est_time
        if self.server.get_op_mode() == PTL_CLI:
            est_epoch = int(time.mktime(time.strptime(est_time, '%c')))
        prime_mod = prime_start % 60  # ignoring the seconds
        self.assertEqual((prime_start - prime_mod), est_epoch)

    def test_prime_time_multisched(self):
        """
        Test prime time queue can be set partition and multi sched
        considers prime time queue for jobs submitted to the p_queue
        """
        self.setup_sc2()
        self.setup_queues_nodes()
        # set primetime which will start after 30min
        prime_start = int(time.time()) + 1800
        prime_end = int(time.time()) + 3600
        self.set_primetime(prime_start, prime_end, scid='sc2')
        a = {'queue_type': 'e', 'started': 't',
             'enabled': 't', 'partition': 'P2'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id="p_queue")

        j = Job(TEST_USER1, {'Resource_List.ncpus': '1',
                             ATTR_queue: 'wq2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, {'Resource_List.ncpus': '1',
                             ATTR_queue: 'p_queue'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        msg = 'Job will run in primetime only'
        self.server.expect(JOB, {ATTR_comment: "Not Running: " + msg}, id=jid2)
        self.scheds['sc2'].log_match(jid2 + ";Job only runs in primetime",
                                     starttime=self.server.ctime)

    def test_dedicated_time_multisched(self):
        """
        Test dedicated time queue can be set partition and multi sched
        considers dedicated time for jobs submitted to the ded_queue
        """
        self.setup_sc2()
        self.setup_queues_nodes()
        # Create a dedicated time queue
        ded_start = int(time.time()) + 1800
        ded_end = int(time.time()) + 3600
        self.scheds['sc2'].add_dedicated_time(start=ded_start, end=ded_end)
        a = {'queue_type': 'e', 'started': 't',
             'enabled': 't', 'partition': 'P2'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id="ded_queue")
        j = Job(TEST_USER1, {'Resource_List.ncpus': '1',
                             ATTR_queue: 'wq2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, {'Resource_List.ncpus': '1',
                             ATTR_queue: 'ded_queue'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        msg = 'Dedicated time conflict'
        self.server.expect(JOB, {ATTR_comment: "Not Running: " + msg}, id=jid2)
        self.scheds['sc2'].log_match(jid2 + ";Dedicated Time",
                                     starttime=self.server.ctime)

    def test_auto_sched_off_due_to_fds_limit(self):
        """
        Test to make sure scheduling should be turned off automatically
        when number of open files per process are exhausted
        """

        if os.getuid() != 0 or sys.platform in ('cygwin', 'win32'):
            self.skipTest("Test need to run as root")

        try:
            # get the number of open files per process
            (open_files_soft_limit, open_files_hard_limit) =\
                resource.getrlimit(resource.RLIMIT_NOFILE)

            # set the soft limit of number of open files per process to 10
            resource.setrlimit(resource.RLIMIT_NOFILE,
                               (10, open_files_hard_limit))
        except (ValueError, resource.error):
            self.assertFalse(True, "Error in accessing system RLIMIT_ "
                                   "variables, test fails.")

        self.setup_sc3()

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduler_iteration': 1},
                            id="sc3", expect=True)
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id="sc3", expect=True)

        self.logger.info('The sleep is 15 seconds which will trigger required '
                         'number of scheduling cycles that are needed to '
                         'exhaust open files per process which is 10 in our '
                         'case')
        time.sleep(15)
        # scheduling should not go to false once all fds per process
        # are exhausted.
        self.server.expect(SCHED, {'scheduling': 'True'},
                           id='sc3', max_attempts=10)

        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (open_files_soft_limit,
                                                        open_files_hard_limit))
        except (ValueError, resource.error):
            self.assertFalse(True, "Error in accessing system RLIMIT_ "
                                   "variables, test fails.")

    def test_set_msched_attr_sched_log_with_sched_off(self):
        """
        Test to set Multisched attributes even when its scheduling is off
        and check whether they are actually be effective
        """
        self.setup_sc3()
        self.scheds['sc3'].set_sched_config({'log_filter': 2048})
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc3")

        new_sched_log = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                     'sc3_new_logs')
        if os.path.exists(new_sched_log):
            self.du.rm(path=new_sched_log, recursive=True,
                       sudo=True, force=True)

        self.du.mkdir(path=new_sched_log, sudo=True)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_log': new_sched_log},
                            id="sc3", expect=True)

        a = {'sched_log': new_sched_log}
        self.server.expect(SCHED, a, id='sc3', max_attempts=10)

        # This is required since we need to call log_match only when
        # the new log file is created.
        time.sleep(1)
        self.scheds['sc3'].log_match(
            "scheduler log directory is changed to " + new_sched_log,
            max_attempts=10, starttime=self.server.ctime)

    def test_set_msched_attr_sched_priv_with_sched_off(self):
        """
        Test to set Multisched attributes even when its scheduling is off
        and check whether they are actually be effective
        """
        self.setup_sc3()
        self.scheds['sc3'].set_sched_config({'log_filter': 2048})
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc3")

        # create and set-up a new priv directory for sc3
        new_sched_priv = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                      'sched_priv_new')
        if os.path.exists(new_sched_priv):
            self.du.rm(path=new_sched_priv, recursive=True,
                       sudo=True, force=True)
        dflt_sched_priv = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                       'sched_priv')

        self.du.run_copy(src=dflt_sched_priv, dest=new_sched_priv,
                         recursive=True, sudo=True)
        self.server.manager(MGR_CMD_SET, SCHED, {'sched_priv': new_sched_priv},
                            id="sc3", expect=True)

        a = {'sched_priv': new_sched_priv}
        self.server.expect(SCHED, a, id='sc3', max_attempts=10)

        # This is required since we need to call log_match only when
        # the new log file is created.
        time.sleep(1)
        self.scheds['sc3'].log_match(
            "scheduler priv directory has changed to " + new_sched_priv,
            max_attempts=10, starttime=self.server.ctime)

    def test_set_msched_update_inbuilt_attrs_accrue_type(self):
        """
        Test to make sure Multisched is able to update any one of the builtin
        attributes like accrue_type
        """
        a = {'eligible_time_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.setup_sc3()
        self.setup_queues_nodes()

        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq3'}

        J1 = Job(TEST_USER1, attrs=a)
        J1.set_sleep_time(5)

        J2 = Job(TEST_USER1, attrs=a)
        J2.set_sleep_time(5)

        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid2)

        # accrue_type = 2 is eligible_time
        self.server.expect(JOB, {ATTR_accrue_type: 2}, id=jid2)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        # This makes sure that accrue_type is indeed getting changed
        self.server.expect(JOB, {ATTR_accrue_type: 3}, id=jid2)

    def test_multisched_not_crash(self):
        """
        Test to make sure Multisched does not crash when all nodes in partition
        are not associated with the corresponding queue
        """
        self.setup_sc1()
        self.setup_queues_nodes()

        # Assign a queue with the partition P1. This queue association is not
        # required as per the current Multisched feature. But this is just to
        # verify even if we associate a queue to one of the nodes in partition
        # the scheduler won't crash.
        # Ex: Here we are associating wq1 to vnode[0] but vnode[4] has no
        # queue associated to it. Expectation is in this case scheduler won't
        # crash
        a = {ATTR_queue: 'wq1'}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[0]', expect="True")

        self.scheds['sc1'].terminate()

        self.scheds['sc1'].start()
        # Ideally the following statement is not requried. start() method
        # itself should take care of updating the PID in its cache. I have
        # created a new bug to fix in this framework. For the time being
        # the following statement is required as a work around.
        self.scheds['sc1']._update_pid(self.scheds['sc1'])

        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=1'})
        jid1 = self.server.submit(j)
        # If job goes to R state means scheduler is still alive.
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

    def test_multi_sched_job_sort_key(self):
        """
        Test to make sure that jobs are sorted as per
        job_sort_key in a multi sched
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        a = {'job_sort_key': '"ncpus LOW"'}
        self.scheds['sc1'].set_sched_config(a)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        j = Job(TEST_USER, {'Resource_List.ncpus': '2',
                            ATTR_queue: 'wq1'})
        jid1 = self.server.submit(j)
        j = Job(TEST_USER, {'Resource_List.ncpus': '1',
                            ATTR_queue: 'wq1'})
        jid2 = self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

    def test_multi_sched_node_sort_key(self):
        """
        Test to make sure nodes are sorted in the order
        as per node_sort_key in a multi sched
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        a = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, NODE, a, id='@default', expect=True)
        a = {'node_sort_key': '"ncpus HIGH " ALL'}
        self.scheds['sc1'].set_sched_config(a)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[0]', expect=True)
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[1]', expect=True)
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[2]', expect=True)
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[3]', expect=True)
        # Offlining the node as we do not need for the test
        a = {'state': 'offline'}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[4]', expect=True)
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             ATTR_queue: 'wq1'}
        j = Job(TEST_USER1, a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, ['vnode[3]'], jid)
        j = Job(TEST_USER1, a)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.check_vnodes(j, ['vnode[2]'], jid1)
        j = Job(TEST_USER1, a)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.check_vnodes(j, ['vnode[1]'], jid2)
        j = Job(TEST_USER1, a)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.check_vnodes(j, ['vnode[0]'], jid3)

    def test_multi_sched_priority_sockets(self):
        """
        Test scheduler socket connections from all the schedulers
        are processed on priority
        """
        self.common_setup()
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})
        for name in self.scheds:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'False'}, id=name, expect=True)
        a = {ATTR_queue: 'wq1',
             'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 60}
        j = Job(TEST_USER1, attrs=a)
        self.server.submit(j)
        t = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id='sc1', expect=True)
        self.server.log_match("processing priority socket", starttime=t)
        a = {ATTR_queue: 'wq2',
             'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 60}
        j = Job(TEST_USER1, attrs=a)
        self.server.submit(j)
        t = int(time.time())
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id='sc2', expect=True)
        self.server.log_match("processing priority socket", starttime=t)

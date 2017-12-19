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


@tags('multisched')
class TestMultipleSchedulers(TestFunctional):

    """
    Test suite to test different scheduler interfaces
    """

    def setUp(self):
        TestFunctional.setUp(self)

        a = {'partition': 'P1,P4',
             'sched_host': self.server.hostname,
             'sched_port': '15050'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc1")
        self.sched_configure('sc1', '15050')
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 1,
                             'sched_port': 15050}, id="sc1")
        dir_path = '/var/spool/pbs/sched_dir'
        if not os.path.exists(dir_path):
            self.du.mkdir(path=dir_path, sudo=True)
        a = {'partition': 'P2',
             'sched_priv': '/var/spool/pbs/sched_dir/sched_priv_sc2',
             'sched_log': '/var/spool/pbs/sched_dir/sched_logs_sc2',
             'sched_host': self.server.hostname,
             'sched_port': '15051'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc2")
        self.sched_configure('sc2', '15051', '/var/spool/pbs/sched_dir')
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 1,
                             'sched_port': 15051}, id="sc2")
        a = {'partition': 'P3',
             'sched_host': self.server.hostname,
             'sched_port': '15052'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc3")
        self.sched_configure('sc3', '15052')
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 1,
                             'sched_port': 15052}, id="sc3")

        a = {'queue_type': 'execution',
             'started': 't',
             'enabled': 't'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        print self.server.queues
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq2')
        print self.server.queues
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq3')
        print self.server.queues
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq4')
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq1')
        p2 = {'partition': 'P2'}
        self.server.manager(MGR_CMD_SET, QUEUE, p2, id='wq2')
        p3 = {'partition': 'P3'}
        self.server.manager(MGR_CMD_SET, QUEUE, p3, id='wq3')
        p4 = {'partition': 'P4'}
        self.server.manager(MGR_CMD_SET, QUEUE, p4, id='wq4')
        a = {'resources_available.ncpus': 2}
        self.server.create_vnodes('vnode', a, 5, self.mom)
        self.server.manager(MGR_CMD_SET, NODE, p1, id='vnode[0]', expect=True)
        self.server.manager(MGR_CMD_SET, NODE, p2, id='vnode[1]', expect=True)
        self.server.manager(MGR_CMD_SET, NODE, p3, id='vnode[2]', expect=True)
        self.server.manager(MGR_CMD_SET, NODE, p4, id='vnode[3]', expect=True)

    def sched_configure(self, sched_name, sched_port=None, sched_home=None):
        pbs_home = self.server.pbs_conf['PBS_HOME']
        if sched_home is None:
            sched_home = pbs_home
        sched_priv_dir = 'sched_priv_' + sched_name
        sched_logs_dir = 'sched_logs_' + sched_name
        if not os.path.exists(os.path.join(sched_home, sched_priv_dir)):
            self.du.run_copy(self.server.hostname,
                             os.path.join(pbs_home, 'sched_priv'),
                             os.path.join(sched_home, sched_priv_dir),
                             recursive=True)
        if not os.path.exists(os.path.join(sched_home, sched_logs_dir)):
            self.du.run_copy(self.server.hostname,
                             os.path.join(pbs_home, 'sched_logs'),
                             os.path.join(sched_home, sched_logs_dir),
                             recursive=True)
        self.server.schedulers[sched_name].start(sched_port, sched_home)

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
        a = {'comment': ''}
        self.server.expect(SCHED, a, id='sc1', max_attempts=10)
        self.du.rm(path=os.path.join(pbs_home, 'sc1_new_priv'), recursive=True)

    def test_set_sched_log(self):
        """
        Test sched_log can be only set to valid paths
        and check for appropriate comments
        """
        sched = self.server.schedulers['sc1']
        if not os.path.exists('/var/sched_log_do_not_exist'):
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'sched_log': '/var/sched_log_do_not_exist'},
                                id="sc1")
        a = {'sched_log': '/var/sched_log_do_not_exist',
             'comment': 'Unable to change the sched_logs directory',
             'scheduling': 'False'}
        self.server.expect(SCHED, a, id='sc1', max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        pbs_home = self.server.pbs_conf['PBS_HOME']
        self.du.run_copy(self.server.hostname,
                         os.path.join(pbs_home, 'sched_logs'),
                         os.path.join(pbs_home, 'sc1_new_logs'),
                         recursive=True)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_log': '/var/spool/pbs/sc1_new_logs'},
                            id="sc1")
        a = {'sched_log': '/var/spool/pbs/sc1_new_logs'}
        self.server.expect(SCHED, a, id='sc1', max_attempts=10)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        a = {'comment': ''}
        self.server.expect(SCHED, a, id='sc1', max_attempts=10)
        self.du.rm(path=os.path.join(pbs_home, 'sc1_new_logs'), recursive=True)

    def test_start_scheduler(self):
        """
        Test that scheduler wont start without creation from qmgr and
        appropriate folders created and partition assigned and test
        states of scheduler in each stage
        """
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'partition': (DECR, 'P3')}, id="sc3")
        # Unset sc3's partition to assign to this scheduler
        pbs_home = self.server.pbs_conf['PBS_HOME']
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            id="sc5")
        a = {'sched_host': self.server.hostname,
             'sched_port': '15055',
             'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SCHED, a, id="sc5")
        sched = self.server.schedulers['sc5']
        # Try starting without sched_priv and sched_logs
        ret = self.server.schedulers['sc5'].start(sched_port='15055')
        self.server.expect(SCHED, {'state': 'down'}, id='sc5', max_attempts=10)
        if ret['rc'] == 0:
            self.assertTrue(False)
        self.du.run_copy(self.server.hostname,
                         os.path.join(pbs_home, 'sched_priv'),
                         os.path.join(pbs_home, 'sched_priv_sc5'),
                         recursive=True)
        ret = self.server.schedulers['sc5'].start(sched_port='15055')
        if ret['rc'] == 0:
            self.assertTrue(False)
        self.du.run_copy(self.server.hostname,
                         os.path.join(pbs_home, 'sched_logs'),
                         os.path.join(pbs_home, 'sched_logs_sc5'),
                         recursive=True)
        ret = self.server.schedulers['sc5'].start(sched_port='15055')
        self.server.schedulers['sc5'].log_match(
            "Scheduler does not contain a partition",
            max_attempts=10, starttime=self.server.ctime)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'partition': 'P3'}, id="sc5")
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'Scheduling': 'True'}, id="sc5")
        self.server.expect(SCHED, {'state': 'idle'}, id='sc5', max_attempts=10)
        a = {'resources_available.ncpus': 100}
        self.server.manager(MGR_CMD_SET, NODE, a, id='vnode[2]', expect=True)
        for _ in xrange(100):
            j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3'})
            self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc5")
        self.server.manager(MGR_CMD_LIST, SCHED, id="sc5")
        self.assertEqual(sched.attributes['state'], 'scheduling')
        self.du.rm(path=os.path.join(
            pbs_home, 'sched_priv_sc5'), recursive=True)
        self.du.rm(path=os.path.join(
            pbs_home, 'sched_logs_sc5'), recursive=True)

    def test_resource_sched_reconfigure(self):
        """
        Test all schedulers will reconfigure while creating,
        setting or deleting a resource
        """
        t = int(time.time())
        self.server.manager(MGR_CMD_CREATE, RSC, id='foo')
        sched_list = self.server.schedulers.keys()
        for name in sched_list:
            self.server.schedulers[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)
        t = int(time.time())
        attr = {ATTR_RESC_TYPE: 'long'}
        self.server.manager(MGR_CMD_SET, RSC, attr, id='foo')
        for name in sched_list:
            self.server.schedulers[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)
        t = int(time.time())
        self.server.manager(MGR_CMD_DELETE, RSC, id='foo')
        for name in sched_list:
            self.server.schedulers[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)

    def test_remove_partition_sched(self):
        """
        Test that removing all the partitions from a scheduler.
        """
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'partition': (DECR, 'P1')}, id="sc1")
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'partition': (DECR, 'P4')}, id="sc1")
        log_msg = "Scheduler does not contain a partition"
        self.server.schedulers['sc1'].log_match(log_msg, max_attempts=10,
                                                starttime=self.server.ctime)
        self.server.manager(MGR_CMD_UNSET, SCHED, 'partition',
                            id="sc2")

    def test_job_queue_partition(self):
        """
        Test job submitted to a queue assosciated to a partition will land
        into a node assosciated with that partition.
        """
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodes = ['vnode[0]']
        self.check_vnodes(j, nodes, jid)
        self.server.schedulers['sc1'].log_match(
            str(jid) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodes = ['vnode[1]']
        self.check_vnodes(j, nodes, jid)
        self.server.schedulers['sc2'].log_match(
            str(jid) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodes = ['vnode[2]']
        self.check_vnodes(j, nodes, jid)
        self.server.schedulers['sc3'].log_match(
            str(jid) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    def test_multiple_partition_same_sched(self):
        """
        Test that multiple partition jobs are serviced by same scheduler
        if the partitions are set on the scheduler
        """
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodes = ['vnode[0]']
        self.check_vnodes(j, nodes, jid)
        self.server.schedulers['sc1'].log_match(
            str(jid) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodes = ['vnode[3]']
        self.check_vnodes(j, nodes, jid)
        self.server.schedulers['sc1'].log_match(
            str(jid) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    def test_multiple_queue_same_partition(self):
        """
        Test multiple queue assosciated with same partition
        is serviced by same scheduler
        """
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodes = ['vnode[0]']
        self.check_vnodes(j, nodes, jid)
        self.server.schedulers['sc1'].log_match(
            str(jid) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodes = ['vnode[0]']
        self.check_vnodes(j, nodes, jid)
        self.server.schedulers['sc1'].log_match(
            str(jid) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    def test_preemption_highp_queue(self):
        """
        Test preemption occures only within queues
        which are assigned to same scheduler
        """
        prio = {'Priority': 150}
        self.server.manager(MGR_CMD_SET, QUEUE, prio, id='wq3')
        self.server.manager(MGR_CMD_SET, QUEUE, prio, id='wq4')
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=2'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        t = int(time.time())
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq4',
                                   'Resource_List.select': '1:ncpus=2'})
        jid5 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid5)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.schedulers['sc1'].log_match(
            str(jid1) + ';Job preempted by suspension',
            max_attempts=10, starttime=t)

    def test_backfill_per_scheduler(self):
        """
        Test backfilling is applicable only per scheduler
        """
        t = int(time.time())
        self.server.schedulers['sc2'].set_sched_config(
            {'strict_ordering': 'True ALL'})
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:ncpus=2',
                                   'Resource_List.walltime': 60})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:ncpus=2',
                                   'Resource_List.walltime': 60})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.schedulers['sc2'].log_match(
            str(jid2) + ';Job is a top job and will run at',
            max_attempts=10, starttime=t)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2',
                                   'Resource_List.walltime': 60})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2',
                                   'Resource_List.walltime': 60})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)
        self.server.schedulers['sc3'].log_match(
            str(jid4) + ';Job is a top job and will run at',
            max_attempts=5, starttime=t, existence=False)

    def test_resource_per_scheduler(self):
        """
        Test resources will be considered only by scheduler
        to which resource is added in sched_config
        """
        a = {'type': 'float', 'flag': 'nh'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id='gpus')
        self.server.schedulers['sc3'].add_resource("gpus")
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
        Test after server restarts it can connect to all schedulers
        and jobs will still be running
        """
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.schedulers['sc1'].log_match(
            str(jid1) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:ncpus=2'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.schedulers['sc2'].log_match(
            str(jid2) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.schedulers['sc3'].log_match(
            str(jid3) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'workq',
                                   'Resource_List.select': '1:ncpus=2'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        self.server.schedulers['default'].log_match(
            str(jid4) + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        self.server.restart()
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)

    def test_resv_default_sched(self):
        """
        Test reservations will only go to defualt scheduler
        """
        t = int(time.time())
        r = Reservation(TEST_USER)
        a = {'Resource_List.select': '2:ncpus=1'}
        r.set_attributes(a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, rid)
        self.server.schedulers['default'].log_match(
            str(rid) + ';Reservation Confirmed',
            max_attempts=10, starttime=t)

    def test_job_sorted_per_scheduler(self):
        """
        Test jobs are sorted as per job_sort_formula
        inside each scheduler
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_sort_formula': 'ncpus'})
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=1'})
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        j = Job(TEST_USER1, attrs={'Resource_List.select': '1:ncpus=2'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        self.server.delete(jid1, wait=True)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=1'})
        jid5 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid5)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid6 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid6)
        self.server.delete(jid4, wait=True)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid4)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid6)

    def test_run_limts_per_scheduler(self):
        """
        Test run_limits applied at server level is
        applied for every scheduler seperately.
        """
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

    def tearDown(self):
        self.du.run_cmd(self.server.hostname, [
                        'pkill', '-9', 'pbs_sched'], sudo=True)
        sched_list = ['sc1', 'sc2', 'sc3']
        for name in sched_list:
            priv = self.server.schedulers[name].attributes['sched_priv']
            self.du.rm(path=priv, recursive=True)
            logs = self.server.schedulers[name].attributes['sched_log']
            self.du.rm(path=logs, recursive=True)
        TestFunctional.tearDown(self)

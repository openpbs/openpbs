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


import resource

from tests.functional import *


class TestMultipleSchedulers(TestFunctional):

    """
    Test suite to test different scheduler interfaces
    """

    def setup_sc1(self):
        a = {'partition': 'P1',
             'sched_host': self.server.hostname,
             'sched_port': '15050'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc1")
        self.scheds['sc1'].create_scheduler()
        self.scheds['sc1'].start()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047}, id='sc1')

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
                            {'scheduling': 'True'}, id="sc2")

    def setup_sc3(self):
        a = {'partition': 'P3',
             'sched_host': self.server.hostname,
             'sched_port': '15052'}
        self.server.manager(MGR_CMD_CREATE, SCHED,
                            a, id="sc3")
        self.scheds['sc3'].create_scheduler()
        self.scheds['sc3'].start()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc3")

    def setup_queues_nodes(self):
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq2')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq3')
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq1')
        p2 = {'partition': 'P2'}
        self.server.manager(MGR_CMD_SET, QUEUE, p2, id='wq2')
        p3 = {'partition': 'P3'}
        self.server.manager(MGR_CMD_SET, QUEUE, p3, id='wq3')
        a = {'resources_available.ncpus': 2}
        self.mom.create_vnodes(a, 4)
        vnode0 = self.mom.shortname + '[0]'
        vnode1 = self.mom.shortname + '[1]'
        vnode2 = self.mom.shortname + '[2]'
        self.server.manager(MGR_CMD_SET, NODE, p1, id=vnode0)
        self.server.manager(MGR_CMD_SET, NODE, p2, id=vnode1)
        self.server.manager(MGR_CMD_SET, NODE, p3, id=vnode2)

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

    def get_tzid(self):
        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            tzone = 'America/Los_Angeles'
        return tzone

    def set_scheduling(self, scheds=None, op=False):
        if scheds is not None:
            for each in scheds:
                self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': op},
                                    id=each)

    @skipOnCpuSet
    def test_job_sort_formula_multisched(self):
        """
        Test that job_sort_formula can be set for each sched
        """
        self.common_setup()

        # Set JSF on server and test that it is used by all scheds
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'job_sort_formula': '1*walltime'})

        # Submit 2 jobs to each sched with different walltimes and
        # test that the one with higher walltime is scheduled first
        queues = ['wq1', 'wq2', 'wq3']
        for i in range(1, 4):
            scid = "sc" + str(i)
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'False'}, id=scid)
            a = {'Resource_List.walltime': 100, ATTR_queue: queues[i - 1],
                 'Resource_List.ncpus': 2}
            j = Job(TEST_USER1, attrs=a)
            jid1 = self.server.submit(j)
            a['Resource_List.walltime'] = 1000
            j = Job(TEST_USER1, attrs=a)
            jid2 = self.server.submit(j)
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'True'}, id=scid)
            self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
            self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

        # Set a different JSF on sc1, this should fail
        try:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'job_sort_formula': '2*walltime'}, id='sc1',
                                logerr=False)
            self.fail("Setting job_sort_formula on sched should have failed")
        except PbsManagerError:
            pass

        # Unset server's JSF and set sc1's JSF again
        self.server.manager(MGR_CMD_UNSET, SERVER, 'job_sort_formula')
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'job_sort_formula': '2*walltime'}, id='sc1')

        self.server.cleanup_jobs()

        # Submit 2 jobs with different walltimes to each sched again
        # This time, sc1 should be the only sched to care about walltime
        for i in range(1, 4):
            scid = "sc" + str(i)
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'False'}, id=scid)
            a = {'Resource_List.walltime': 100, ATTR_queue: queues[i - 1],
                 'Resource_List.ncpus': 2}
            j = Job(TEST_USER1, attrs=a)
            jid1 = self.server.submit(j)
            a['Resource_List.walltime'] = 1000
            j = Job(TEST_USER1, attrs=a)
            jid2 = self.server.submit(j)
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'True'}, id=scid)
            if scid == "sc1":
                self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
                self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
            else:
                self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
                self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

    @skipOnCpuSet
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
                         src=os.path.join(pbs_home, 'sched_priv'),
                         dest=os.path.join(pbs_home, 'sc1_new_priv'),
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

    @skipOnCpuSet
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
                         src=os.path.join(pbs_home, 'sched_priv'),
                         dest=os.path.join(pbs_home, 'sched_priv_sc5'),
                         recursive=True, sudo=True)
        ret = self.scheds['sc5'].start()
        msg = "sched_logs dir is not present for scheduler"
        self.assertTrue(ret['rc'], msg)
        self.du.run_copy(self.server.hostname,
                         src=os.path.join(pbs_home, 'sched_logs'),
                         dest=os.path.join(pbs_home, 'sched_logs_sc5'),
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
        vn = self.mom.shortname
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn + '[2]')
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc5")
        for _ in range(500):
            j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3'})
            self.server.submit(j)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc5")
        self.server.expect(SCHED, {'state': 'scheduling'},
                           id='sc5', max_attempts=10)

    @skipOnCpuSet
    def test_resource_sched_reconfigure(self):
        """
        Test all schedulers will reconfigure while creating,
        setting or deleting a resource
        """
        self.common_setup()
        t = time.time()
        self.server.manager(MGR_CMD_CREATE, RSC, id='foo')
        for name in self.scheds:
            self.scheds[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)
        # sleeping to make sure we are not checking for the
        # same scheduler reconfiguring message again
        time.sleep(1)
        t = time.time()
        attr = {ATTR_RESC_TYPE: 'long'}
        self.server.manager(MGR_CMD_SET, RSC, attr, id='foo')
        for name in self.scheds:
            self.scheds[name].log_match(
                "Scheduler is reconfiguring",
                max_attempts=10, starttime=t)
        # sleeping to make sure we are not checking for the
        # same scheduler reconfiguring message again
        time.sleep(1)
        t = time.time()
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
        self.server.manager(MGR_CMD_UNSET, SCHED,
                            'partition', id="sc1")
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id="sc1")
        log_msg = "Scheduler does not contain a partition"
        self.scheds['sc1'].log_match(log_msg, max_attempts=10,
                                     starttime=self.server.ctime)
        # Blocked by PP-1202 will revisit once its fixed
        # self.server.manager(MGR_CMD_UNSET, SCHED, 'partition', id="sc2")

    @skipOnCpuSet
    def test_job_queue_partition(self):
        """
        Test job submitted to a queue associated to a partition will land
        into a node associated with that partition.
        """
        self.common_setup()
        vn = ['%s[%d]' % (self.mom.shortname, i) for i in range(3)]
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, [vn[0]], jid)
        self.scheds['sc1'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq2',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, [vn[1]], jid)
        self.scheds['sc2'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, [vn[2]], jid)
        self.scheds['sc3'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    @skipOnCpuSet
    def test_multiple_queue_same_partition(self):
        """
        Test multiple queue associated with same partition
        is serviced by same scheduler
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        vn0 = self.mom.shortname + '[0]'
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, [vn0], jid)
        self.scheds['sc1'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq3')
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.check_vnodes(j, [vn0], jid)
        self.scheds['sc1'].log_match(
            jid + ';Job run', max_attempts=10,
            starttime=self.server.ctime)

    @skipOnCpuSet
    def test_preemption_highp_queue(self):
        """
        Test preemption occures only within queues which are assigned
        to same partition
        """
        self.common_setup()
        prio = {'Priority': 150, 'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, prio, id='wq3')
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=2'})
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        t = time.time()
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid2 = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq3',
                                   'Resource_List.select': '1:ncpus=2'})
        jid3 = self.server.submit(j)
        self.server.expect(JOB, ATTR_comment, op=SET, id=jid3)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.scheds['sc1'].log_match(
            jid1 + ';Job preempted by suspension',
            max_attempts=10, starttime=t)

    @skipOnCpuSet
    def test_preemption_two_sched(self):
        """
        Test two schedulers preempting jobs at the same time
        """
        self.common_setup()
        q = {'queue_type': 'Execution', 'started': 'True',
             'enabled': 'True', 'Priority': 150}
        q['partition'] = 'P1'
        self.server.manager(MGR_CMD_CREATE, QUEUE, q, id='highp_P1')
        q['partition'] = 'P2'
        self.server.manager(MGR_CMD_CREATE, QUEUE, q, id='highp_P2')

        n = {'resources_available.ncpus': 20}
        vn = ['%s[%d]' % (self.mom.shortname, i) for i in range(2)]
        self.server.manager(MGR_CMD_SET, NODE, n, id=vn[0])
        self.server.manager(MGR_CMD_SET, NODE, n, id=vn[1])

        jids1 = []
        job_attrs = {'Resource_List.select': '1:ncpus=1', 'queue': 'wq1'}
        for _ in range(20):
            j = Job(TEST_USER, job_attrs)
            jid = self.server.submit(j)
            jids1.append(jid)

        jids2 = []
        job_attrs['queue'] = 'wq2'
        for _ in range(20):
            j = Job(TEST_USER, job_attrs)
            jid = self.server.submit(j)
            jids2.append(jid)

        self.server.expect(JOB, {'job_state=R': 40})

        s = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SCHED, s, id='sc1')
        self.server.manager(MGR_CMD_SET, SCHED, s, id='sc2')

        job_attrs = {'Resource_List.select': '20:ncpus=1', 'queue': 'highp_P1'}
        hj1 = Job(TEST_USER, job_attrs)
        hj1_jid = self.server.submit(hj1)

        job_attrs['queue'] = 'highp_P2'
        hj2 = Job(TEST_USER, job_attrs)
        hj2_jid = self.server.submit(hj2)

        s = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SCHED, s, id='sc1')
        self.server.manager(MGR_CMD_SET, SCHED, s, id='sc2')

        for jid in jids1:
            self.server.expect(JOB, {'job_state': 'S'}, id=jid)
            self.scheds['sc1'].log_match(jid + ';Job preempted by suspension')

        for jid in jids2:
            self.server.expect(JOB, {'job_state': 'S'}, id=jid)
            self.scheds['sc2'].log_match(jid + ';Job preempted by suspension')

        self.server.expect(JOB, {'job_state': 'R'}, id=hj1_jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=hj2_jid)

    @skipOnCpuSet
    def test_backfill_per_scheduler(self):
        """
        Test backfilling is applicable only per scheduler
        """
        self.common_setup()
        t = time.time()
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

    @skipOnCpuSet
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
        self.server.manager(MGR_CMD_SET, NODE, a, id='@default')
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

    @skipOnCpuSet
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

    @skipOnCpuSet
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

    @skipOnCpuSet
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

    @skipOnCpuSet
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
        self.assertEqual(n.nshares, default_shares)
        self.assertEqual(n.usage, default_usage)

        n = sc1_fs.get_node(id=10)
        self.assertEqual(n.nshares, sc1_shares)
        self.assertEqual(n.usage, sc1_usage)

        n = sc2_fs.get_node(id=10)
        self.assertEqual(n.nshares, sc2_shares)
        self.assertEqual(n.usage, sc2_usage)

        n = sc3_fs.get_node(id=10)
        self.assertEqual(n.nshares, sc3_shares)
        self.assertEqual(n.usage, sc3_usage)

    @skipOnCpuSet
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
        # need to delete the running job because PBS has only 1 ncpu and
        # our work is also done with the job.
        # this step will decrease the execution time as well
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
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
        self.assertEqual(sc1_fs_user1.usage, 101)
        sc1_fs_user2 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER2))
        self.assertEqual(sc1_fs_user2.usage, 101)
        sc1_fs_user3 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER3))
        self.assertEqual(sc1_fs_user3.usage, 101)
        sc1_fs_user4 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER4))
        self.assertEqual(sc1_fs_user4.usage, 1)
        # Restart the scheduler
        t = time.time()
        self.scheds['sc1'].restart()
        # Check the multisched 'sc1' usage file whether it's updating or not
        self.assertTrue(self.scheds['sc1'].isUp())
        # The scheduler will set scheduler attributes on the first scheduling
        # cycle, so we need to trigger a cycle, have the scheduler configure,
        # then turn it off again
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        self.scheds['sc1'].log_match("Scheduler is reconfiguring", starttime=t)
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
        self.assertEqual(sc1_fs_user1.usage, 201)
        sc1_fs_user2 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER2))
        self.assertEqual(sc1_fs_user2.usage, 201)
        sc1_fs_user3 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER3))
        self.assertEqual(sc1_fs_user3.usage, 101)
        sc1_fs_user4 = self.scheds['sc1'].query_fairshare(name=str(TEST_USER4))
        self.assertEqual(sc1_fs_user4.usage, 101)

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
        self.assertEqual(user, str(TEST_USER))

    def test_pbsfs_invalid_sched(self):
        """
        Test pbsfs -I <sched_name> where sched_name does not exist
        """
        sched_name = 'foo'
        pbsfs_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                 'sbin', 'pbsfs') + ' -I ' + sched_name
        ret = self.du.run_cmd(cmd=pbsfs_cmd, runas=self.scheduler.user)
        err_msg = 'Scheduler %s does not exist' % sched_name
        self.assertEqual(err_msg, ret['err'][0])

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

    @skipOnCpuSet
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
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        a = {'partition': 'P1', 'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a,
                            id=self.mom.shortname)

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

        t_start = time.time()
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        self.scheds['sc1'].log_match(
            'Leaving Scheduling Cycle', starttime=t_start)
        t_end = time.time()
        job_list = self.scheds['sc1'].log_match(
            'Considering job to run', starttime=t_start,
            allmatch=True, endtime=t_end)

        # job 1 runs second as it's run by an entity with usage = 100
        self.assertTrue(jid1 in job_list[-1][1])

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

        t_start = time.time()
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id='sc1')
        self.scheds['sc1'].log_match(
            'Leaving Scheduling Cycle', starttime=t_start)
        t_end = time.time()
        job_list = self.scheds['sc1'].log_match(
            'Considering job to run', starttime=t_start,
            allmatch=True, endtime=t_end)

        self.assertTrue(jid2 in job_list[-1][1])

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

    @skipOnCpuSet
    def test_equiv_multisched(self):
        """
        Test the basic behavior of job equivalence classes: submit two
        different types of jobs into 2 different schedulers and see they
        are in two different classes in each scheduler
        """
        self.setup_sc1()
        self.setup_sc2()
        self.setup_queues_nodes()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047}, id='sc2')
        t = time.time()
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

    @skipOnCpuSet
    def test_limits_queues(self):
        """
        Test to see that jobs from different users fall into different
        equivalence classes with queue hard limits.
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq3')
        t = time.time()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc1")
        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[u:PBS_GENERIC=1]'}, id='wq1')
        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'max_run': '[u:PBS_GENERIC=1]'}, id='wq3')

        # Eat up all the resources
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq1'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq3'}
        J = Job(TEST_USER, attrs=a)
        self.server.submit(J)
        a = {ATTR_queue: 'wq1'}
        self.submit_jobs(3, a, user=TEST_USER1)
        self.submit_jobs(3, a, user=TEST_USER2)
        a = {ATTR_queue: 'wq3'}
        self.submit_jobs(3, a, user=TEST_USER1)
        self.submit_jobs(3, a, user=TEST_USER2)

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id="sc1")

        # Six equivalence classes. Two for the resource eating job in
        # different partitions and one for each user per partition.
        self.scheds['sc1'].log_match("Number of job equivalence classes: 6",
                                     starttime=t)

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
        self.server.manager(MGR_CMD_LIST, SCHED, a, id="sc2")

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

    @skipOnCpuSet
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
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='wq1')
        a = {'resources_available.ncpus': 2}
        self.mom.create_vnodes(a, 2)
        vn0 = self.mom.shortname + '[0]'
        self.server.manager(MGR_CMD_SET, NODE, p3, id=vn0)
        # Set job_sort_formula on the server
        self.server.manager(MGR_CMD_SET, SERVER, {'job_sort_formula': 'ncpus'})
        # Set job_sort_formula_threshold on the multisched
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'job_sort_formula_threshold': '2'}, id="sc3")
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
        return {**attrib, **a}

    def setup_placement_set(self):
        self.server.add_resource('switch', 'string_array', 'h')
        a = {'resources_available.ncpus': 2}
        self.mom.create_vnodes(
            a, 12, attrfunc=self.cust_attr)
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_key': 'switch'})
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_enable': 't'})

    @skipOnCpuSet
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
        vn = ['%s[%d]' % (self.mom.shortname, i) for i in range(10)]
        nodes = [vn[5]]
        self.check_vnodes(j, nodes, j1id)
        a = {'Resource_List.select': '2:ncpus=2'}
        j = Job(TEST_USER, attrs=a)
        j2id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        nodes = [vn[3], vn[4]]
        self.check_vnodes(j, nodes, j2id)
        a = {'Resource_List.select': '3:ncpus=2'}
        j = Job(TEST_USER, attrs=a)
        j3id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j3id)
        self.check_vnodes(j, vn[0:3], j3id)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'only_explicit_psets': 't'}, id='sc2')
        a = {'Resource_List.select': '1:ncpus=2', ATTR_queue: 'wq2'}
        j = Job(TEST_USER, attrs=a)
        j4id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j4id)
        nodes = [vn[9]]
        self.check_vnodes(j, nodes, j4id)
        a = {'Resource_List.select': '2:ncpus=2', ATTR_queue: 'wq2'}
        j = Job(TEST_USER, attrs=a)
        j5id = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=j5id)
        self.check_vnodes(j, vn[6:8], j5id)
        a = {'Resource_List.select': '3:ncpus=2', ATTR_queue: 'wq2'}
        j = Job(TEST_USER, attrs=a)
        j6id = self.server.submit(j)
        self.server.expect(JOB, {
                           'job_state': 'Q',
                           'comment': 'Not Running: Placement set switch=A'
                           ' has too few free resources'}, id=j6id)

    @skipOnCpuSet
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
        a = {'Resource_List.select': '4:ncpus=2', ATTR_queue: 'wq2'}
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

    @skipOnCpuSet
    def test_sched_preempt_enforce_resumption(self):
        """
        Test sched_preempt_enforce_resumption can be set to a multi sched
        and that even if topjob_ineligible is set for a preempted job
        and sched_preempt_enforce_resumption is set true , the
        preempted job will be calandered
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        p1 = {'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, p1, id='wq3')
        prio = {'Priority': 150, 'partition': 'P1'}
        self.server.manager(MGR_CMD_SET, QUEUE, prio, id='wq3')
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
        j = Job(TEST_USER, {'queue': 'wq3', 'Resource_List.walltime': '60',
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
        self.scheds[scid].holidays_delete_entry('a')

        cur_year = datetime.datetime.today().year
        self.scheds[scid].holidays_set_year(cur_year)

        p_day = 'weekday'
        p_hhmm = time.strftime('%H%M', time.localtime(ptime_start))
        np_hhmm = time.strftime('%H%M', time.localtime(ptime_end))
        self.scheds[scid].holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'saturday'
        self.scheds[scid].holidays_set_day(p_day, p_hhmm, np_hhmm)

        p_day = 'sunday'
        self.scheds[scid].holidays_set_day(p_day, p_hhmm, np_hhmm)

    @skipOnCpuSet
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

    @skipOnCpuSet
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

    @skipOnCpuSet
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

        self.setup_sc3()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduler_iteration': 1}, id="sc3")
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id="sc3")
        try:
            # get the number of open files per process
            (open_files_soft_limit, open_files_hard_limit) = \
                resource.getrlimit(resource.RLIMIT_NOFILE)

            # set the soft limit of number of open files per process to 10
            resource.setrlimit(resource.RLIMIT_NOFILE,
                               (10, open_files_hard_limit))

        except (ValueError, resource.error):
            self.assertFalse(True, "Error in accessing system RLIMIT_ "
                                   "variables, test fails.")
        try:
            self.logger.info('The sleep is 15 seconds which will '
                             'trigger required number of scheduling '
                             'cycles that are needed to exhaust open '
                             'files per process which is 10 in our case')
            time.sleep(15)

        except BaseException as exc:
            raise exc
        finally:
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE,
                                   (open_files_soft_limit,
                                    open_files_hard_limit))
                # scheduling should not go to false once all fds per process
                # are exhausted.
                self.server.expect(SCHED, {'scheduling': 'True'},
                                   id='sc3', max_attempts=10)
            except (ValueError, resource.error):
                self.assertFalse(True, "Error in accessing system RLIMIT_ "
                                       "variables, test fails.")

    def test_set_msched_attr_sched_log_with_sched_off(self):
        """
        Test to set Multisched attributes even when its scheduling is off
        and check whether they are actually be effective
        """
        self.setup_sc3()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047}, id='sc3')

        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'False'}, id="sc3")

        new_sched_log = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                     'sc3_new_logs')
        if os.path.exists(new_sched_log):
            self.du.rm(path=new_sched_log, recursive=True,
                       sudo=True, force=True)

        self.du.mkdir(path=new_sched_log, sudo=True)
        self.du.chown(path=new_sched_log, recursive=True,
                      uid=self.scheds['sc3'].user, sudo=True)
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'sched_log': new_sched_log}, id="sc3")

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
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'False',
                                                 'log_events': 2047}, id="sc3")

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
                            id="sc3")

        a = {'sched_priv': new_sched_priv}
        self.server.expect(SCHED, a, id='sc3', max_attempts=10)

        # This is required since we need to call log_match only when
        # the new log file is created.
        time.sleep(1)
        self.scheds['sc3'].log_match(
            "scheduler priv directory has changed to " + new_sched_priv,
            max_attempts=10, starttime=self.server.ctime)

    @skipOnCpuSet
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

        J2 = Job(TEST_USER1, attrs=a)

        jid1 = self.server.submit(J1)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid1)

        jid2 = self.server.submit(J2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid2)

        # accrue_type = 2 is eligible_time
        self.server.expect(JOB, {ATTR_accrue_type: 2}, id=jid2)

        self.server.delete(jid1, wait=True)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)
        # This makes sure that accrue_type is indeed getting changed
        self.server.expect(JOB, {ATTR_accrue_type: 3}, id=jid2)

    @skipOnCpuSet
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
        vn = self.mom.shortname
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn + '[0]')

        self.scheds['sc1'].terminate()

        self.scheds['sc1'].start()

        j = Job(TEST_USER1, attrs={ATTR_queue: 'wq1',
                                   'Resource_List.select': '1:ncpus=1'})
        jid1 = self.server.submit(j)
        # If job goes to R state means scheduler is still alive.
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

    @skipOnCpuSet
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

    @skipOnCpuSet
    def test_multi_sched_node_sort_key(self):
        """
        Test to make sure nodes are sorted in the order
        as per node_sort_key in a multi sched
        """
        self.setup_sc1()
        self.setup_queues_nodes()
        a = {'partition': 'P1'}
        vn = ['%s[%d]' % (self.mom.shortname, i) for i in range(4)]
        self.server.manager(MGR_CMD_SET, NODE, a, id='@default')
        a = {'node_sort_key': '"ncpus HIGH " ALL'}
        self.scheds['sc1'].set_sched_config(a)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn[0])
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn[1])
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn[2])
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=vn[3])

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.place': 'excl',
             ATTR_queue: 'wq1'}
        j = Job(TEST_USER1, a)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.check_vnodes(j, [vn[3]], jid1)
        j = Job(TEST_USER1, a)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.check_vnodes(j, [vn[2]], jid2)
        j = Job(TEST_USER1, a)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.check_vnodes(j, [vn[1]], jid3)
        j = Job(TEST_USER1, a)
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid4)
        self.check_vnodes(j, [vn[0]], jid4)

    @skipOnCpuSet
    def test_multi_sched_priority_sockets(self):
        """
        Test scheduler socket connections from all the schedulers
        are processed on priority
        """
        self.common_setup()
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})
        for name in self.scheds:
            self.server.manager(MGR_CMD_SET, SCHED,
                                {'scheduling': 'False'}, id=name)
        a = {ATTR_queue: 'wq1',
             'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 60}
        j = Job(TEST_USER1, attrs=a)
        self.server.submit(j)
        t = time.time()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id='sc1')
        self.server.log_match("processing priority socket", starttime=t)
        a = {ATTR_queue: 'wq2',
             'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 60}
        j = Job(TEST_USER1, attrs=a)
        self.server.submit(j)
        t = time.time()
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'scheduling': 'True'}, id='sc2')
        self.server.log_match("processing priority socket", starttime=t)

    @skipOnCpuSet
    def test_advance_resv_in_multi_sched(self):
        """
        Test that advance reservations in a multi-sched environment can be
        serviced by any scheduler
        """
        # Create 3 multi-scheds sc1, sc2 and sc3, 3 partitions and 4 vnodes
        self.common_setup()
        # Consume all resources in partitions serviced by sc1 and sc3 and
        # default scheduler
        a = {ATTR_queue: 'wq1',
             'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 60}
        j = Job(TEST_USER1, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        a = {ATTR_queue: 'wq3',
             'Resource_List.select': '1:ncpus=2'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        a = {ATTR_queue: 'workq',
             'Resource_List.select': '1:ncpus=2'}
        j3 = Job(TEST_USER, attrs=a)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)

        # Now submit a reservation which only sc2 can confirm because
        # it has free nodes
        t = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 5,
             'reserve_end': t + 35}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, rid)
        vn1 = self.mom.shortname + '[1]'
        rnodes = {'resv_nodes': '(' + vn1 + ':ncpus=2)'}
        self.server.expect(RESV, rnodes, id=rid)

        # Wait for reservation to run and then submit a job to the
        # reservation
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, rid)
        a = {ATTR_q: rid.split('.')[0]}
        j4 = Job(TEST_USER, attrs=a)
        jid4 = self.server.submit(j4)
        result = {'job_state': 'R', 'exec_vnode': '(' + vn1 + ':ncpus=1)'}
        self.server.expect(JOB, result, id=jid4)

    @skipOnCpuSet
    def test_resv_in_empty_multi_sched_env(self):
        """
        Test that advance reservations gets confirmed by all the schedulers
        running in the complex
        """
        # Create 3 multi-scheds sc1, sc2 and sc3, 3 partitions and 4 vnodes
        self.common_setup()
        # Submit 4 reservations and check they get confirmed
        for _ in range(4):
            t = int(time.time())
            a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 25,
                 'reserve_end': t + 55}
            r = Reservation(TEST_USER, attrs=a)
            rid = self.server.submit(r)
            a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
            self.server.expect(RESV, a, rid)

        # Submit 5th reservation and check that it is denied
        t = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 25,
             'reserve_end': t + 55}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        msg = "Resv;" + rid + ";Reservation denied"
        self.server.log_match(msg)

    @skipOnCpuSet
    def test_asap_resv(self):
        """
        Test ASAP reservation in multisched environment. It should not
        matter if a job is part of a partition. An ASAP reservation could
        confirm on any of the existing partitions and then moved to the
        reservation queue.
        """
        # Create 3 multi-scheds sc1, sc2 and sc3, 4 partitions and 4 vnodes
        self.common_setup()
        # Turn off scheduling in all schedulers but one (say sc3)
        self.set_scheduling(['sc1', 'sc2', 'default'], False)

        # submit a job in partition serviced by sc1
        a = {ATTR_queue: 'wq1',
             'Resource_List.select': '1:ncpus=2',
             'Resource_List.walltime': 600}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        # Now turn this job into a reservation and notice that it runs inside
        # a reservation running on vnode[2] which is part of sc3
        a = {ATTR_convert: jid}
        r = Reservation(TEST_USER, a)
        r.unset_attributes(['reserve_start', 'reserve_end'])
        rid = self.server.submit(r)
        exp_attrs = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, exp_attrs, id=rid)
        exec_vn = '(' + self.mom.shortname + '[2]:ncpus=2)'
        result = {'job_state': 'R', 'exec_vnode': exec_vn}
        self.server.expect(JOB, result, id=jid)

    def test_standing_resv_reject(self):
        """
        Test that if a scheduler serving a partition is not able to
        confirm all the occurrences of the standing reservation on the same
        partition then it will reject it.
        """

        self.common_setup()
        # Turn off scheduling in all schedulers but sc1 because sc1 serves
        # partition P1
        self.set_scheduling(['sc2', 'sc3', 'default'], False)

        # Submit an advance reservation which is going to occupy full
        # partition in future
        t = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 200,
             'reserve_end': t + 4000}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, rid)

        # Submit a standing reservation such that it consumes one partition
        # and an occurrence finishes before the advance reservation starts.
        # This means scheduler will try to place the first occurance right
        # before the advance reservation was confirmed because the
        # node is free, it will not be able to place the second occurrence
        # because of the advance reservation
        start = int(time.time()) + 10
        end = start + 150
        tzone = self.get_tzid()
        a = {ATTR_resv_rrule: 'FREQ=HOURLY;COUNT=2',
             ATTR_resv_timezone: tzone,
             'reserve_start': start,
             'reserve_end': end,
             'Resource_List.select': '1:ncpus=2'
             }
        sr = Reservation(TEST_USER, attrs=a)
        srid = self.server.submit(sr)
        msg = "Resv;" + srid + ";Reservation denied"
        self.server.log_match(msg)

    def test_printing_partition_resv_hook(self):
        """
        Test if a reservation having a partition set on it is readable in
        a reservation hook
        """
        hook_body = """
import pbs
e = pbs.event()
resv = e.resv
pbs.logmsg(pbs.EVENT_DEBUG, "Resv partition is %s" % resv.partition)
e.accept()
"""
        a = {'event': 'resv_end', 'enabled': 'true', 'debug': 'true'}
        self.server.create_import_hook("h1", a, hook_body)
        # Create 3 multi-scheds sc1, sc2 and sc3, 3 partitions and 4 vnodes
        self.common_setup()
        # Turn off scheduling in all schedulers but one (say sc3)
        self.set_scheduling(['sc1', 'sc2', 'default'], False)
        t = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 5,
             'reserve_end': t + 15}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, rid)
        self.logger.info("Wait for reservation to end")
        time.sleep(10)
        msg = "Resv partition is P3"
        self.server.log_match(msg)

    def test_setting_partition_resv_hook(self):
        """
        Test if a reservation can set partition name on reservation object
        """
        hook_body = """
import pbs
e = pbs.event()
resv = e.resv
resv.partition = "P-3"
pbs.logmsg(pbs.EVENT_DEBUG, "Resv partition is %s" % resv.partition)
e.accept()
"""
        a = {'event': 'resvsub', 'enabled': 'true', 'debug': 'true'}
        self.server.create_import_hook("h1", a, hook_body)
        # Create 3 multi-scheds sc1, sc2 and sc3, 3 partitions and 4 vnodes
        self.common_setup()
        t = int(time.time())
        a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 5,
             'reserve_end': t + 15}
        r = Reservation(TEST_USER, a)
        with self.assertRaises(PbsSubmitError) as e:
            rid = self.server.submit(r)
        msg = "resv attribute 'partition' is readonly"
        self.server.log_match(msg)
        self.assertIn("hook 'h1' encountered an exception",
                      e.exception.msg[0])

    @skipOnCpuSet
    def test_resv_alter(self):
        """
        Test if a reservation confirmed by a multi-sched can be altered by the
        same scheduler.
        """
        self.common_setup()
        # Submit 4 reservations to fill up the system and check they are
        # confirmed
        for _ in range(4):
            t = int(time.time())
            a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 60,
                 'reserve_end': t + 120}
            r = Reservation(TEST_USER, a)
            rid = self.server.submit(r)
            attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
            self.server.expect(RESV, attr, rid)
            partition = self.server.status(RESV, 'partition', id=rid)
            if (partition[0]['partition'] == 'P1'):
                old_end_time = a['reserve_end']
                modify_resv = rid
        # Modify the endtime of reservation confirmed on partition P1 and
        # make sure the node solution is correct.
        end_time = old_end_time + 60
        bu = BatchUtils()
        new_end_time = bu.convert_seconds_to_datetime(end_time)
        attrs = {'reserve_end': new_end_time}
        time_now = time.time()
        self.server.alterresv(modify_resv, attrs)
        attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                'partition': 'P1'}
        self.server.expect(RESV, attr, modify_resv)
        vn = self.mom.shortname
        rnodes = {'resv_nodes': '(' + vn + '[0]:ncpus=2)'}
        self.server.expect(RESV, rnodes, id=modify_resv)
        msg = modify_resv + ";Reservation Confirmed"
        self.scheds['sc1'].log_match(msg, starttime=time_now)

    def test_setting_default_partition(self):
        """
        Test if setting default partition on pbs scheduler/queue/node fails
        """

        self.common_setup()
        a = {'partition': 'pbs-default'}
        with self.assertRaises(PbsManagerError) as e:
            self.server.manager(MGR_CMD_SET, QUEUE, a, id='workq')
        self.assertIn("Default partition name is not allowed",
                      e.exception.msg[0])
        with self.assertRaises(PbsManagerError) as e:
            vn3 = self.mom.shortname + '[3]'
            self.server.manager(MGR_CMD_SET, NODE, a, id=vn3)
        self.assertIn("Default partition name is not allowed",
                      e.exception.msg[0])
        with self.assertRaises(PbsManagerError) as e:
            self.server.manager(MGR_CMD_SET, SCHED, a, id='sc1')
        self.assertIn("Default partition name is not allowed",
                      e.exception.msg[0])

    def degraded_resv_reconfirm(self, start, end, rrule=None, run=False):
        """
        Test that a degraded reservation gets reconfirmed in a multi-sched env
        """
        # Add two nodes to partition P1 and turn off scheduling for all other
        # schedulers serving partition P2 and P3. Make scheduler sc1 serve
        # only partition P1 (vnode[0], vnode[1]).
        p1 = {'partition': 'P1'}
        vn = ['%s[%d]' % (self.mom.shortname, i) for i in range(2)]
        self.server.manager(MGR_CMD_SET, NODE, p1, id=vn[1])
        self.server.expect(SCHED, p1, id="sc1")

        a = {'reserve_retry_time': 5}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.set_scheduling(['sc2', 'sc3', 'default'], False)

        attr = {'Resource_List.select': '1:ncpus=2',
                'reserve_start': start,
                'reserve_end': end}
        if rrule is not None:
            attr.update({ATTR_resv_rrule: rrule,
                         ATTR_resv_timezone: self.get_tzid()})
        resv = Reservation(TEST_USER, attr)
        rid = self.server.submit(resv)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.server.status(RESV, 'resv_nodes', id=rid)
        resv_node = self.server.reservations[rid].get_vnodes()[0]

        if run:
            resv_state = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            self.logger.info('Sleeping until reservation starts')
            offset = start - int(time.time())
            self.server.expect(RESV, resv_state, id=rid,
                               offset=offset, interval=1)
        else:
            resv_state = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'false'},
                            id="sc1")
        ret = self.server.status(RESV, 'partition', id=rid)
        a = {'state': 'offline'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=resv_node)

        a = {'reserve_substate': 10}
        a.update(resv_state)
        self.server.expect(RESV, a, id=rid)

        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'True'},
                            id="sc1")
        other_node = vn[resv_node == vn[0]]

        if run:
            a = {'reserve_substate': 5}
        else:
            a = {'reserve_substate': 2}
        a.update({'resv_nodes': (MATCH_RE, re.escape(other_node))})

        self.server.expect(RESV, a, id=rid, interval=1)

    def test_advance_confirmed_resv_reconfirm(self):
        """
        Test degraded reservation gets reconfirmed on a different
        node of the same partition in multi-sched environment
        """
        self.common_setup()
        now = int(time.time())
        self.degraded_resv_reconfirm(start=now + 20, end=now + 200)

    def test_advance_running_resv_reconfirm(self):
        """
        Test degraded running reservation gets reconfirmed on a different
        node of the same partition in multi-sched environment
        """
        self.common_setup()
        now = int(time.time())
        self.degraded_resv_reconfirm(start=now + 20, end=now + 200, run=True)

    def test_standing_confimred_resv_reconfirm(self):
        """
        Test degraded standing resv gets reconfirmed on a different
        node of the same partition in multi-sched environment
        """
        self.common_setup()
        now = int(time.time())
        self.degraded_resv_reconfirm(start=now + 20, end=now + 200,
                                     rrule='FREQ=HOURLY;COUNT=2')

    def test_standing_running_resv_reconfirm(self):
        """
        Test degraded running standing resv gets reconfirmed on a different
        node of the same partition in multi-sched environment
        """
        self.common_setup()
        now = int(time.time())
        self.degraded_resv_reconfirm(start=now + 20, end=now + 200, run=True,
                                     rrule='FREQ=HOURLY;COUNT=2')

    @skipOnCpuSet
    def test_resv_from_job_in_multi_sched_using_qsub(self):
        """
        Test that a user is able to create a reservation out of a job using
        qsub when the job is part of a non-default partition
        """
        self.common_setup()
        # Turn off scheduling in all schedulers but sc1
        self.set_scheduling(['sc2', 'sc3', 'default'], False)

        a = {ATTR_W: 'create_resv_from_job=1', ATTR_q: 'wq1',
             'Resource_List.walltime': 1000}
        job = Job(TEST_USER, a)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid)

        a = {ATTR_job: jid}
        rid = self.server.status(RESV, a)[0]['id'].split(".")[0]

        a = {ATTR_job: jid, 'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'),
             'partition': 'P1'}
        self.server.expect(RESV, a, id=rid)

    @skipOnCpuSet
    def test_resv_from_job_in_multi_sched_using_rsub(self):
        """
        Test that a user is able to create a reservation out of a job using
        pbs_rsub when the job is part of a non-default partition
        """
        self.common_setup()
        # Turn off scheduling in all schedulers but sc1
        self.set_scheduling(['sc2', 'sc3', 'default'], False)

        a = {'Resource_List.select': '1:ncpus=2', ATTR_q: 'wq1',
             'Resource_List.walltime': 1000}
        job = Job(TEST_USER, a)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid)

        a = {ATTR_job: jid}
        resv = Reservation(attrs=a)
        rid = self.server.submit(resv)

        a = {ATTR_job: jid, 'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'),
             'partition': 'P1'}
        self.server.expect(RESV, a, id=rid)

    def test_resv_alter_force_for_confirmed_resv(self):
        """
        Test that in a multi-sched setup ralter -Wforce can
        modify a confirmed reservation successfully even when
        the ralter results into over subscription of resources.
        """

        self.common_setup()
        # Submit 4 reservations to fill up the system and check they are
        # confirmed
        for _ in range(4):
            t = int(time.time())
            a = {'Resource_List.select': '1:ncpus=2', 'reserve_start': t + 300,
                 'reserve_end': t + 900}
            r = Reservation(TEST_USER, a)
            rid = self.server.submit(r)
            attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
            self.server.expect(RESV, attr, rid)
            partition = self.server.status(RESV, 'partition', id=rid)
            if (partition[0]['partition'] == 'P1'):
                p1_start_time = t + 300
        # submit a reservation that will end before the start time of
        # reservation confimed in partition P1
        bu = BatchUtils()
        stime = int(time.time()) + 30
        etime = p1_start_time - 10
        # Turn off scheduling for all schedulers, except sc1
        self.set_scheduling(['sc2', 'sc3', 'default'], False)

        attrs = {'reserve_end': etime, 'reserve_start': stime,
                 'Resource_List.select': '1:ncpus=2'}
        rid_new = self.server.submit(Reservation(TEST_USER, attrs))

        check_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                      'partition': 'P1'}
        self.server.expect(RESV, check_attr, rid_new)

        # Turn off the last running scheduler
        self.server.manager(MGR_CMD_SET, SCHED, {'scheduling': 'false'},
                            id="sc1")
        # extend end time so that it overlaps with an existin reservation
        etime = etime + 300
        a = {'reserve_end': bu.convert_seconds_to_datetime(etime),
             'reserve_start': bu.convert_seconds_to_datetime(stime)}

        self.server.alterresv(rid_new, a, extend='force')
        msg = "pbs_ralter: " + rid_new + " CONFIRMED"
        self.assertEqual(msg, self.server.last_out[0])
        resv_attr = self.server.status(RESV, id=rid_new)[0]
        resv_end = bu.convert_stime_to_seconds(resv_attr['reserve_end'])
        self.assertEqual(int(resv_end), etime)

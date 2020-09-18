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


class TestNodeBuckets(TestFunctional):
    """
    Test basic functionality of node buckets.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        day = time.strftime("%Y%m%d", time.localtime(time.time()))
        filename = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                'sched_logs', day)
        self.du.rm(path=filename, force=True, sudo=True, level=logging.DEBUG2)

        self.colors = \
            ['red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet']
        self.shapes = ['circle', 'square', 'triangle',
                       'diamond', 'pyramid', 'sphere', 'cube']
        self.letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string', 'flag': 'h'}, id='color')
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string_array', 'flag': 'h'}, id='shape')
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string_array', 'flag': 'h'}, id='letter')
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'boolean', 'flag': 'h'}, id='bool')

        a = {'resources_available.ncpus': 2, 'resources_available.mem': '8gb'}
        # 10010 nodes since it divides into 7 evenly.
        # Each node bucket will have 1430 nodes in it
        self.mom.create_vnodes(attrib=a, num=10010,
                               sharednode=False,
                               expect=False, attrfunc=self.cust_attr_func)
        # Make sure all the nodes are in state free.  We can't let
        # create_vnodes() do this because it does a pbsnodes -v on each vnode.
        # This takes a long time.
        self.server.expect(NODE, {'state=free': (GE, 10010)})

        self.scheduler.add_resource('color')

        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

    def cust_attr_func(self, name, totalnodes, numnode, attribs):
        """
        Add resources to vnodes.  There are 10010 nodes, which means 1430
        nodes of each color, letter, and shape.  The value of bool is True
        for the last 5005 nodes and unset for the first 5005 nodes
        """
        a = {'resources_available.color': self.colors[numnode // 1430],
             'resources_available.shape': self.shapes[numnode % 7],
             'resources_available.letter': self.letters[numnode % 7]}

        if numnode // 5005 == 0:
            a['resources_available.bool'] = 'True'

        # Yellow buckets get a higher priority
        if numnode // 1430 == 2:
            a['Priority'] = 100
        return {**attribs, **a}

    def check_normal_path(self, sel='2:ncpus=2:mem=1gb', pl='scatter:excl',
                          queue='workq'):
        """
        Check if a job runs in the normal code path
        """
        a = {'Resource_List.select': sel, 'Resource_List.place': pl,
             'queue': queue}
        j = Job(TEST_USER, attrs=a)

        jid = self.server.submit(j)
        self.scheduler.log_match(jid + ';Evaluating subchunk', n=10000,
                                 interval=1)

        self.server.delete(jid, wait=True)

    @skipOnCpuSet
    def test_basic(self):
        """
        Request nodes of a specific color and make sure they are correctly
        allocated to the job
        """
        chunk = '4:ncpus=1:color=yellow'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'scatter:excl'}
        J = Job(TEST_USER, a)
        jid = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)

        js = self.server.status(JOB, id=jid)
        nodes = J.get_vnodes(js[0]['exec_vnode'])
        for node in nodes:
            n = self.server.status(NODE, 'resources_available.color', id=node)
            self.assertTrue('yellow' in
                            n[0]['resources_available.color'])

    @skipOnCpuSet
    def test_multi_bucket(self):
        """
        Request two different chunk types which need to be allocated from
        different buckets and make sure they are allocated correctly.
        """
        a = {'Resource_List.select':
             '4:ncpus=1:color=yellow+4:ncpus=1:color=blue',
             'Resource_List.place': 'scatter:excl'}
        J = Job(TEST_USER, a)
        jid = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ', n=10000)

        js = self.server.status(JOB, id=jid)
        nodes = J.get_vnodes(js[0]['exec_vnode'])
        # Yellow nodes were requested first.
        # Make sure they come before the blue nodes.
        for i in range(4):
            n = self.server.status(NODE, id=nodes[i])
            self.assertTrue('yellow' in n[0]['resources_available.color'])
        for i in range(4, 8):
            n = self.server.status(NODE, id=nodes[i])
            self.assertTrue('blue' in n[0]['resources_available.color'])

    @skipOnCpuSet
    def test_multi_bucket2(self):
        """
        Request nodes from all 7 different buckets and see them allocated
        correctly
        """
        select = ""
        for c in self.colors:
            select += "1:ncpus=1:color=%s+" % (c)

        # remove the trailing '+'
        select = select[:-1]

        a = {'Resource_List.select': select,
             'Resource_List.place': 'scatter:excl'}

        J = Job(TEST_USER, a)
        jid = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk:', n=10000)

        js = self.server.status(JOB, id=jid)
        nodes = J.get_vnodes(js[0]['exec_vnode'])
        for i, node in enumerate(nodes):
            n = self.server.status(NODE, id=node)
            self.assertTrue(self.colors[i] in
                            n[0]['resources_available.color'])

    @skipOnCpuSet
    def test_not_run(self):
        """
        Request more nodes of one color that is available to make sure
        the job is not run on incorrect nodes.
        """
        chunk = '1431:ncpus=1:color=yellow'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'scatter:excl'}
        J = Job(TEST_USER, a)
        jid = self.server.submit(J)
        a = {'comment': (MATCH_RE, '^Can Never Run'),
             'job_state': 'Q'}
        self.server.expect(JOB, a, attrop=PTL_AND, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)

    @skipOnCpuSet
    def test_calendaring1(self):
        """
        Test to see that nodes that are used in the future for
        calendared jobs are not used for filler jobs that would
        distrupt the scheduled time.
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True'})

        chunk1 = '1:ncpus=1'
        a = {'Resource_List.select': chunk1,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '1:00:00'}
        j = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.scheduler.log_match(jid1 + ';Chunk: ' + chunk1, n=10000)

        chunk2 = '10010:ncpus=1'
        a = {'Resource_List.select': chunk2,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '2:00:00'}
        j = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.expect(JOB, 'comment', op=SET, id=jid2, interval=1)
        self.scheduler.log_match(jid2 + ';Chunk: ' + chunk2, n=10000)

        chunk3 = '2:ncpus=1'
        a = {'Resource_List.select': chunk3,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '30:00'}
        j = Job(TEST_USER, attrs=a)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3, interval=1)
        self.scheduler.log_match(jid3 + ';Chunk: ' + chunk3, n=10000)

        a = {'Resource_List.select': chunk3,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '2:30:00'}
        j = Job(TEST_USER, attrs=a)
        jid4 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid4)
        self.server.expect(JOB, 'comment', op=SET, id=jid4, interval=1)
        self.scheduler.log_match(jid4 + ';Chunk: ' + chunk3, n=10000)

    @skipOnCpuSet
    def test_calendaring2(self):
        """
        Test that nodes that a reservation calendared on them later on
        are used before totally free nodes
        """

        self.scheduler.set_sched_config({'strict_ordering': 'True'})

        now = int(time.time())
        vnode = self.mom.shortname
        select_s = '1:vnode=' + vnode + '[2865]+1:vnode=' + vnode + '[2870]'
        a = {'Resource_List.select': select_s,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '1:00:00',
             'reserve_start': now + 3600, 'reserve_end': now + 7200}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')}, id=rid)

        chunk = '2:ncpus=1:color=yellow'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '30:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)

        s = self.server.status(JOB, 'exec_vnode', id=jid)
        n = j.get_vnodes(s[0]['exec_vnode'])
        msg = 'busy_later nodes not chosen first'
        self.assertTrue(vnode + '[2865]' in n, msg)
        self.assertTrue(vnode + '[2870]' in n, msg)

    @skipOnCpuSet
    def test_calendaring3(self):
        """
        Test that a future reservation's nodes are used first for a job
        that is put into the calendar.
        """

        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        vnode = self.mom.shortname
        now = int(time.time())
        select_s = '1:vnode=' + vnode + '[2865]+1:vnode=' + vnode + '[2870]'
        a = {'Resource_List.select': select_s,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '1:00:00',
             'reserve_start': now + 3600, 'reserve_end': now + 7200}
        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')}, id=rid)

        chunk1 = '1430:ncpus=1:color=yellow'
        a = {'Resource_List.select': chunk1,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '30:00'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk1, n=10000)

        chunk2 = '2:ncpus=1:color=yellow'
        a = {'Resource_List.select': chunk2,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '15:00'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.scheduler.log_match(jid2 + ';Chunk: ' + chunk2, n=10000)
        self.server.expect(JOB, 'estimated.exec_vnode', op=SET, id=jid2)

        s = self.server.status(JOB, 'estimated.exec_vnode', id=jid2)
        n = j2.get_vnodes(s[0]['estimated.exec_vnode'])
        msg = 'busy_later nodes not chosen first'
        self.assertTrue(vnode + '[2865]' in n, msg)
        self.assertTrue(vnode + '[2870]' in n, msg)

    @skipOnCpuSet
    def test_buckets_and_non(self):
        """
        Test that jobs requesting buckets and not requesting buckets
        play nice together
        """

        # vnode[1435] is orange
        vn = self.mom.shortname
        a = {'Resource_List.ncpus': 1,
             'Resource_List.vnode': vn + '[1435]'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.scheduler.log_match(jid1 + ';Evaluating subchunk', n=10000)

        chunk = '1429:ncpus=1:color=orange'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'scatter:excl'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.scheduler.log_match(jid2 + ';Chunk: ' + chunk, n=10000)

        s1 = self.server.status(JOB, 'exec_vnode', id=jid1)
        s2 = self.server.status(JOB, 'exec_vnode', id=jid2)

        nodes1 = j1.get_vnodes(s1[0]['exec_vnode'])
        nodes2 = j2.get_vnodes(s2[0]['exec_vnode'])

        msg = 'Job 1 and Job 2 are sharing nodes'
        for n in nodes2:
            self.assertNotEqual(n, nodes1[0], msg)

    @skipOnCpuSet
    def test_not_buckets(self):
        """
        Test to make sure the jobs that should use the standard node searching
        code path do not use the bucket code path
        """

        # Running a 10010 cpu job through the normal code path spams the log.
        # We don't care about it, so there is no reason to increase
        # the log size by so much.
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 767})
        # Run a job on all nodes leaving 1 cpus available on each node
        j = Job(TEST_USER, {'Resource_List.select': '10010:ncpus=1',
                            'Resource_List.place': 'scatter'})
        j.set_sleep_time(600)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        # Node sorting via unused resources uses the standard code path
        self.logger.info('Test node_sort_key with unused resources')
        a = {'node_sort_key': '\"ncpus HIGH unused\"'}
        self.scheduler.set_sched_config(a)
        self.check_normal_path()

        self.scheduler.revert_to_defaults()
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        # provisioning_policy: avoid_provisioning uses the standard code path
        self.logger.info('Test avoid_provision')
        a = {'provision_policy': 'avoid_provision'}
        self.scheduler.set_sched_config(a)
        self.check_normal_path()

        self.scheduler.revert_to_defaults()
        self.scheduler.add_resource('color')
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        # the bucket codepath requires excl
        self.logger.info('Test different place specs')
        self.check_normal_path(pl='scatter:shared')
        self.check_normal_path(pl='free')

        vn = self.mom.shortname
        # can't request host or vnode resources on the bucket codepath
        self.logger.info('Test jobs requesting host and vnode')
        self.check_normal_path(sel='1:ncpus=2:host=' + vn + '[0]')
        self.check_normal_path(sel='1:ncpus=2:vnode=' + vn + '[0]')

        # suspended jobs use the normal codepath
        self.logger.info('Test suspended job')
        a = {'queue_type': 'execution', 'started': 'True', 'enabled': 'True',
             'priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='expressq')
        self.server.delete(jid, wait=True)

        a = {'Resource_List.select': '1430:ncpus=1:color=orange',
             'Resource_List.place': 'scatter:excl'}
        j2 = Job(TEST_USER, a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        a = {'Resource_List.select': '1:ncpus=1:color=orange',
             'queue': 'expressq'}
        j3 = Job(TEST_USER, a)
        jid3 = self.server.submit(j3)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.scheduler.log_match(jid3 + ';Evaluating subchunk', n=10000)
        self.server.delete([jid2, jid3], wait=True)

        # Checkpointed jobs use normal code path
        self.logger.info('Test checkpointed job')
        chk_script = """#!/bin/bash
                kill $1
                exit 0
                """
        self.mom.add_checkpoint_abort_script(body=chk_script)

        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': 'C'},
                            runas=ROOT_USER)
        attrs = {'Resource_List.select': '1430:ncpus=1:color=orange',
                 'Resource_List.place': 'scatter:excl'}
        j_c1 = Job(TEST_USER, attrs)
        jid_c1 = self.server.submit(j_c1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid_c1)
        self.scheduler.log_match(
            jid_c1 + ';Chunk: 1430:ncpus=1:color=orange', n=10000)
        a = {'Resource_List.select': '1:ncpus=1:color=orange',
             'queue': 'expressq'}
        j_c2 = Job(TEST_USER, a)
        jid_c2 = self.server.submit(j_c2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid_c1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid_c2)
        self.scheduler.log_match(
            jid_c1 + ";Job preempted by checkpointing", n=10000)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.scheduler.log_match(jid_c2 + ';Evaluating subchunk', n=10000)
        self.server.delete([jid_c1, jid_c2], wait=True)

        # Job's in reservations use the standard codepath
        self.logger.info('Test job in reservation')
        now = int(time.time())
        a = {'Resource_List.select': '4:ncpus=2:mem=4gb',
             'Resource_List.place': 'scatter:excl',
             'reserve_start': now + 30, 'reserve_end': now + 120}
        r = Reservation(TEST_USER, a)
        rid = self.server.submit(r)
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')})
        self.logger.info('Waiting 30s for reservation to start')
        self.server.expect(RESV,
                           {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
                           offset=30)
        r_queue = rid.split('.')[0]
        self.check_normal_path(sel='1:ncpus=3', queue=r_queue)
        self.server.delete(rid)

        # Jobs on multi-vnoded systems use the standard codepath
        self.logger.info('Test job on multi-vnoded system')
        a = {'resources_available.ncpus': 2, 'resources_available.mem': '8gb'}
        self.mom.create_vnodes(a, 8, sharednode=False,
                               vnodes_per_host=4)
        self.check_normal_path(sel='2:ncpus=8')

    @skipOnCpuSet
    def test_multi_vnode_resv(self):
        """
        Test that node buckets do not get in the way of running jobs on
        multi-vnoded systems in reservations
        """
        a = {'resources_available.ncpus': 2, 'resources_available.mem': '8gb'}
        self.mom.create_vnodes(a, 12,
                               sharednode=False, vnodes_per_host=4,
                               attrfunc=self.cust_attr_func)

        now = int(time.time())
        a = {'Resource_List.select': '8:ncpus=1',
             'Resource_List.place': 'vscatter',
             'reserve_start': now + 30,
             'reserve_end': now + 3600}

        r = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(r)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.logger.info('Waiting 30s for reservation to start')
        a['reserve_state'] = (MATCH_RE, 'RESV_RUNNING|5')
        self.server.expect(RESV, a, id=rid, offset=30)

        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'group=shape',
             'queue': rid.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Evaluating subchunk', n=10000)

        ev = self.server.status(JOB, 'exec_vnode', id=jid)
        used_nodes = j.get_vnodes(ev[0]['exec_vnode'])

        n = self.server.status(NODE, 'resources_available.shape')
        s = [x['resources_available.shape']
             for x in n if x['id'] in used_nodes]
        self.assertEqual(len(set(s)), 1,
                         "Job1 ran in more than one placement set")

    @skipOnCpuSet
    def test_bucket_sort(self):
        """
        Test if buckets are sorted properly: all of the yellow bucket
        also has priority 100.  It should be the first bucket.
        """
        a = {'node_sort_key': '\"sort_priority HIGH\"'}
        self.scheduler.set_sched_config(a)

        chunk = '2:ncpus=1'
        j = Job(TEST_USER, {'Resource_List.select': chunk,
                            'Resource_List.place': 'scatter:excl'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)

        jobs = self.server.status(JOB, {'exec_vnode'})
        jn = j.get_vnodes(jobs[0]['exec_vnode'])
        n1 = self.server.status(NODE, 'resources_available.color',
                                id=jn[0])
        n2 = self.server.status(NODE, 'resources_available.color',
                                id=jn[1])

        c1 = n1[0]['resources_available.color']
        c2 = n2[0]['resources_available.color']
        self.assertEqual(c1, 'yellow', "Job didn't run on yellow nodes")
        self.assertEqual(c2, 'yellow', "Job didn't run on yellow nodes")

    @skipOnCpuSet
    def test_psets(self):
        """
        Test placement sets with node buckets
        """
        a = {'node_group_key': 'shape', 'node_group_enable': 'True',
             'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        chunk = '1430:ncpus=1'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'scatter:excl'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.scheduler.log_match(jid1 + ';Chunk: ' + chunk, n=10000)
        self.scheduler.log_match(jid2 + ';Chunk: ' + chunk, n=10000)

        ev = self.server.status(JOB, 'exec_vnode', id=jid1)
        used_nodes1 = j1.get_vnodes(ev[0]['exec_vnode'])

        n = self.server.status(NODE, 'resources_available.shape')
        s = [x['resources_available.shape']
             for x in n if x['id'] in used_nodes1]
        self.assertEqual(len(set(s)), 1,
                         "Job1 ran in more than one placement set")

        ev = self.server.status(JOB, 'exec_vnode', id=jid2)
        used_nodes2 = j2.get_vnodes(ev[0]['exec_vnode'])

        s = [x['resources_available.shape']
             for x in n if x['id'] in used_nodes2]
        self.assertEqual(len(set(s)), 1,
                         "Job2 ran in more than one placement set")

        for node in used_nodes1:
            self.assertNotIn(node, used_nodes2, 'Jobs share nodes: ' + node)

    @skipOnCpuSet
    def test_psets_calendaring(self):
        """
        Test that jobs in the calendar fit within a placement set
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True'})
        svr_attr = {'node_group_key': 'shape', 'node_group_enable': 'True',
                    'backfill_depth': 5}
        self.server.manager(MGR_CMD_SET, SERVER, svr_attr)

        chunk1 = '10010:ncpus=1'
        a = {'Resource_List.select': chunk1,
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '1:00:00'}

        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.scheduler.log_match(jid1 + ';Chunk: ' + chunk1, n=10000)

        chunk2 = '1430:ncpus=1'
        a['Resource_List.select'] = chunk2

        j2 = Job(TEST_USER, a)
        jid2 = self.server.submit(j2)

        self.scheduler.log_match(
            jid2 + ';Chunk: ' + chunk2, interval=1, n=10000)
        self.scheduler.log_match(jid2 + ';Job is a top job', n=10000)

        n = self.server.status(NODE, 'resources_available.shape')

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.expect(JOB, 'estimated.start_time', id=jid2, op=SET)
        ev = self.server.status(JOB, 'estimated.exec_vnode', id=jid2)
        used_nodes2 = j2.get_vnodes(ev[0]['estimated.exec_vnode'])

        s = [x['resources_available.shape']
             for x in n if x['id'] in used_nodes2]
        self.assertEqual(len(set(s)), 1,
                         "Job1 will run in more than one placement set")

        j3 = Job(TEST_USER, a)
        jid3 = self.server.submit(j3)

        self.scheduler.log_match(
            jid3 + ';Chunk: ' + chunk2, interval=1, n=10000)
        self.scheduler.log_match(jid3 + ';Job is a top job', n=10000)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid3)
        self.server.expect(JOB, 'estimated.start_time', id=jid3, op=SET)
        ev = self.server.status(JOB, 'estimated.exec_vnode', id=jid3)
        used_nodes3 = j3.get_vnodes(ev[0]['estimated.exec_vnode'])

        s = [x['resources_available.shape']
             for x in n if x['id'] in used_nodes3]
        self.assertEqual(len(set(s)), 1,
                         "Job1 will run in more than one placement set")

        for node in used_nodes2:
            self.assertNotIn(node, used_nodes3,
                             'Jobs will share nodes: ' + node)

    @skipOnCpuSet
    def test_psets_calendaring_resv(self):
        """
        Test that jobs do not run into a reservation and will correctly
        be added to the calendar on the correct vnodes with placement sets
        """

        self.scheduler.set_sched_config({'strict_ordering': True})
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_key': 'shape',
                                                  'node_group_enable': True})

        now = int(time.time())
        a = {'Resource_List.select': '10010:ncpus=1',
             'Resource_List.place': 'scatter:excl',
             'reserve_start': now + 600, 'reserve_end': now + 3600}
        r = Reservation(attrs=a)
        rid = self.server.submit(r)
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')}, id=rid)

        a = {'Resource_List.select': '1430:ncpus=1',
             'Resource_List.place': 'scatter:excl',
             'Resource_List.walltime': '1:00:00'}
        j = Job(attrs=a)
        jid = self.server.submit(j)

        self.server.expect(JOB, 'estimated.exec_vnode', id=jid, op=SET)

        n = self.server.status(NODE, 'resources_available.shape')
        st = self.server.status(JOB, 'estimated.exec_vnode', id=jid)[0]
        nodes = j.get_vnodes(st['estimated.exec_vnode'])

        s = [x['resources_available.shape']
             for x in n if x['id'] in nodes]
        self.assertEqual(len(set(s)), 1,
                         "Job will run in more than one placement set")

    @skipOnCpuSet
    def test_place_group(self):
        """
        Test node buckets with place=group
        """
        chunk = '1430:ncpus=1'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'scatter:excl:group=letter'}

        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)

        ev = self.server.status(JOB, 'exec_vnode', id=jid)
        used_nodes = j.get_vnodes(ev[0]['exec_vnode'])

        n = self.server.status(NODE, 'resources_available.letter')
        s = [x['resources_available.letter']
             for x in n if x['id'] in used_nodes]
        self.assertEqual(len(set(s)), 1,
                         "Job ran in more than one placement set")

    @skipOnCpuSet
    def test_psets_spanning(self):
        """
        Request more nodes than available in one placement set and see
        the job span or not depending on the value of do_not_span_psets
        """
        # Turn off scheduling to be sure there is no cycle running when
        # configurations are changed
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'node_group_key': 'shape', 'node_group_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'do_not_span_psets': 'True'}
        self.server.manager(MGR_CMD_SET, SCHED, a, id='default')

        # request one more node than the largest placement set
        chunk = '1431:ncpus=1'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'scatter:excl'}

        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Trigger a scheduling cycle
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'job_state': 'Q', 'comment':
             (MATCH_RE, 'can\'t fit in the largest placement set, '
              'and can\'t span psets')}
        self.server.expect(JOB, a, attrop=PTL_AND, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)

        a = {'do_not_span_psets': 'False'}
        self.server.manager(MGR_CMD_SET, SCHED, a, id='default')
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        ev = self.server.status(JOB, 'exec_vnode', id=jid)
        used_nodes = j.get_vnodes(ev[0]['exec_vnode'])

        n = self.server.status(NODE, 'resources_available.shape')
        s = [x['resources_available.shape']
             for x in n if x['id'] in used_nodes]
        self.assertGreater(len(set(s)), 1,
                           "Job did not span properly")

    @skipOnCpuSet
    def test_psets_queue(self):
        """
        Test that placement sets work for nodes associated with queues
        """

        a = {'node_group_key': 'shape', 'node_group_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        a = {'queue_type': 'Execution', 'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')

        # Take the first 14 vnodes.  This means there are two nodes per shape
        vn = self.mom.shortname
        nodes = [vn + '[' + str(x) + ']' for x in range(14)]
        self.server.manager(MGR_CMD_SET, NODE, {'queue': 'workq2'}, id=nodes)

        chunk = '2:ncpus=1'
        a = {'Resource_List.select': chunk, 'queue': 'workq2',
             'Resource_List.place': 'scatter:excl'}
        for _ in range(7):
            j = Job(TEST_USER, a)
            j.set_sleep_time(1000)
            jid = self.server.submit(j)
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
            self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)

        # Check to see if jobs ran in one placement set
        jobs = self.server.status(JOB)
        for job in jobs:
            ev = self.server.status(JOB, 'exec_vnode', id=job['id'])
            used_nodes = j.get_vnodes(ev[0]['exec_vnode'])

            n = self.server.status(NODE, 'resources_available.shape')
            s = [x['resources_available.shape']
                 for x in n if x['id'] in used_nodes]
            self.assertEqual(len(set(s)), 1,
                             "Job " + job['id'] +
                             "ran in more than one placement set")

        s = self.server.select()
        for jid in s:
            self.server.delete(jid, wait=True)

        # Check to see of jobs span correctly
        chunk = '7:ncpus=1'
        a = {'Resource_List.select': chunk, 'queue': 'workq2',
             'Resource_List.place': 'scatter:excl'}
        j = Job(TEST_USER, a)
        j.set_sleep_time(1000)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.scheduler.log_match(jid + ';Chunk: ' + chunk, n=10000)
        ev = self.server.status(JOB, 'exec_vnode', id=jid)
        used_nodes = j.get_vnodes(ev[0]['exec_vnode'])

        n = self.server.status(NODE, 'resources_available.shape')
        s = [x['resources_available.shape']
             for x in n if x['id'] in used_nodes]
        self.assertGreater(len(set(s)), 1,
                           "Job did not span properly")

    @skipOnCpuSet
    def test_free(self):
        """
        Test that free placement works with the bucket code path
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        chunk = '1430:ncpus=1:color=yellow'
        a = {'Resource_List.select': chunk,
             'Resource_List.place': 'excl'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.scheduler.log_match(jid1 + ';Chunk: ' + chunk, n=10000)
        self.scheduler.log_match(jid2 + ';Chunk: ' + chunk, n=10000)

        s1 = self.server.status(JOB, 'exec_vnode', id=jid1)
        s2 = self.server.status(JOB, 'exec_vnode', id=jid2)

        n1 = j1.get_vnodes(s1[0]['exec_vnode'])
        n2 = j1.get_vnodes(s2[0]['exec_vnode'])

        msg = 'job did not run on correct number of nodes'
        self.assertEqual(len(n1), 715, msg)
        self.assertEqual(len(n2), 715, msg)

        for node in n1:
            self.assertTrue(node not in n2, 'Jobs share nodes: ' + node)

    @skipOnCpuSet
    def test_queue_nodes(self):
        """
        Test that buckets work with nodes associated to a queue
        """
        v1 = self.mom.shortname + '[1431]'
        v2 = self.mom.shortname + '[1435]'
        a = {'queue_type': 'execution', 'started': 'True', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='q2')

        self.server.manager(MGR_CMD_SET, NODE, {'queue': 'q2'}, id=v1)
        self.server.manager(MGR_CMD_SET, NODE, {'queue': 'q2'}, id=v2)

        chunk1 = '1428:ncpus=1:color=orange'
        a = {'Resource_List.select': chunk1,
             'Resource_List.place': 'scatter:excl'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.scheduler.log_match(jid1 + ';Chunk: ' + chunk1, n=10000)
        job = self.server.status(JOB, 'exec_vnode', id=jid1)[0]
        ev = j1.get_vnodes(job['exec_vnode'])
        msg = 'Job is using queue\'s nodes'
        self.assertNotIn(v1, ev)
        self.assertNotIn(v2, ev)

        chunk2 = '2:ncpus=1'
        a = {'Resource_List.select': chunk2,
             'Resource_List.place': 'scatter:excl',
             'queue': 'q2'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.scheduler.log_match(jid2 + ';Chunk: ' + chunk2, n=10000)
        job = self.server.status(JOB, 'exec_vnode', id=jid2)[0]
        ev = j2.get_vnodes(job['exec_vnode'])
        msg = 'Job running on nodes not associated with queue'
        self.assertIn(v1, ev, msg)
        self.assertIn(v2, ev, msg)

    @skipOnCpuSet
    def test_booleans(self):
        """
        Test that booleans are correctly handled if not in the sched_config
        resources line.  This means that an unset boolean is considered false
        and that booleans that are True are considered even though they
        aren't on the resources line.
        """

        chunk1 = '2:ncpus=1'
        a = {'Resource_List.select': chunk1,
             'Resource_List.place': 'scatter:excl'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.scheduler.log_match(jid1 + ';Chunk: ' + chunk1, n=10000)
        jst = self.server.status(JOB, 'exec_vnode', id=jid1)[0]
        ev = j1.get_vnodes(jst['exec_vnode'])
        for n in ev:
            self.server.expect(
                NODE, {'resources_available.bool': 'True'}, id=n)

        chunk2 = '2:ncpus=1:bool=False'
        a['Resource_List.select'] = chunk2
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.scheduler.log_match(jid2 + ';Chunk: ' + chunk2, n=10000)

        jst = self.server.status(JOB, 'exec_vnode', id=jid2)[0]
        ev = j2.get_vnodes(jst['exec_vnode'])
        for n in ev:
            self.server.expect(
                NODE, 'resources_available.bool', op=UNSET, id=n)

    @skipOnCpuSet
    def test_last_pset_can_never_run(self):
        """
        Test that the job does not retain the error value of last placement
        set seen by the node bucketing code. To check this make sure that the
        last placement set check results into a 'can never run' case because
        resources do not match and check that the job is not marked as
        never run.
        """

        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'long', 'flag': 'nh'}, id='foo')
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string', 'flag': 'h'}, id='bar')
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_key': 'bar'})
        self.server.manager(MGR_CMD_SET, SERVER, {'node_group_enable': 'true'})
        self.mom.delete_vnode_defs()
        a = {'resources_available.ncpus': 80,
             'resources_available.bar': 'large'}
        self.mom.create_vnodes(attrib=a, num=8,
                               sharednode=False)
        self.scheduler.add_resource('foo')
        a['resources_available.foo'] = 8
        a['resources_available.ncpus'] = 8
        a['resources_available.bar'] = 'small'
        for val in range(0, 5):
            vname = self.mom.shortname + "[" + str(val) + "]"
            self.server.manager(MGR_CMD_SET, NODE, a, id=vname)
        chunk1 = '4:ncpus=5:foo=5'
        a = {'Resource_List.select': chunk1,
             'Resource_List.place': 'scatter:excl'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.scheduler.log_match(jid2 + ';Job will never run',
                                 existence=False, max_attempts=10)

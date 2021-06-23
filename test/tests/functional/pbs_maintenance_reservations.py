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


class TestMaintenanceReservations(TestFunctional):
    """
    Various tests to verify behavior of maintenance reservations.
    Two moms (-p "servers=M1,moms=M1:M2") are recommended for the tests.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.server.set_op_mode(PTL_CLI)

    def test_maintenance_acl_denied(self):
        """
        Test if the maintenance reservation is denied for common user
        """
        now = int(time.time())

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [self.mom.shortname]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rsub: Unauthorized Request", msg)

    def test_maintenance_conflicting_parameters(self):
        """
        Test if conflicting parameters are refused
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a = {'Resource_List.select': '1',
             'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [self.mom.shortname]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rsub: can't use -l with --hosts", msg)

        a = {'Resource_List.place': 'scatter',
             'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [self.mom.shortname]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rsub: can't use -l with --hosts", msg)

        a = {'interactive': 300,
             'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [self.mom.shortname]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rsub: can't use -I with --hosts", msg)

    def test_maintenance_unknown_hosts(self):
        """
        Test if the pbs_rsub with all unknown hosts return error.
        Test if the pbs_rsub with any unknown host return error.
        Test if the --hosts without host parameter return error.
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = ["foo"]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        msg = ""

        try:
            self.server.submit(r)
        except PbsSubmitError as err:
            msg = err.msg[0].strip()

        self.assertEqual("pbs_rsub: Host with resources not found: foo", msg)

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [self.mom.shortname, "foo"]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rsub: Host with resources not found: foo", msg)

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [""]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rsub: missing host(s)", msg)

    def test_maintenance_duplicate_host(self):
        """
        Test if the pbs_rsub with duplicate host return error.
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = ["foo", "foo"]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rsub: Duplicate host: foo", msg)

    def test_maintenance_confirm(self):
        """
        Test if the maintenance (prefixed with 'M') is immediately
        confirmed without scheduler and the select, place, and resv_nodes
        are correctly crafted. Also check if resv_enable = False is
        ignored.
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': False})
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a = {'resources_available.ncpus': 2}
        self.mom.create_vnodes(a, num=2)
        vn = self.mom.shortname

        a = {'resv_enable': False}
        self.server.manager(MGR_CMD_SET, NODE, a,
                            id=self.mom.shortname, runas=TEST_USER)
        self.server.manager(MGR_CMD_SET, NODE, a, vn + '[0]', runas=TEST_USER)
        self.server.manager(MGR_CMD_SET, NODE, a, vn + '[1]', runas=TEST_USER)

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [self.mom.shortname]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        rid = self.server.submit(r)

        self.assertTrue(rid.startswith('M'))
        resv_vnodes = '(' + vn + '[0]:ncpus=2)+(' + vn + '[1]:ncpus=2)'
        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                    'Resource_List.select':
                    'host=%s:ncpus=4' % self.mom.shortname,
                    'Resource_List.place': 'exclhost',
                    'resv_nodes': resv_vnodes}
        self.server.expect(RESV, exp_attr, id=rid)

    def test_maintenance_delete(self):
        """
        Test if the maintenance can not be deleted by common user.
        Test if the maintenance reservation can be deleted by a manager.
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (INCR, '%s@*' % TEST_USER)})

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        h = [self.mom.shortname]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        rid = self.server.submit(r)

        self.assertTrue(rid.startswith('M'))

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (DECR, '%s@*' % TEST_USER)})

        with self.assertRaises(PbsDeleteError) as err:
            self.server.delete(rid, runas=TEST_USER)

        msg = err.exception.msg[0].strip()

        self.assertEqual("pbs_rdel: Unauthorized Request  " + rid, msg)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (INCR, '%s@*' % TEST_USER)})

        self.server.delete(rid, runas=TEST_USER)

    def test_maintenance_degrade_reservation_overlap1(self):
        """
        Test if the reservation is degraded by overlapping
        maintenance reservation - overlap: beginning
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a1 = {'Resource_List.select': 'host=%s' % self.mom.shortname,
              'reserve_start': now + 3600,
              'reserve_end': now + 7200}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 1800,
              'reserve_end': now + 5400}
        h2 = [self.mom.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10'),
                    'reserve_substate': 12}
        self.server.expect(RESV, exp_attr, id=rid1)

    def test_maintenance_degrade_reservation_overlap2(self):
        """
        Test if the reservation is degraded by overlapping
        maintenance reservation - overlap: ending
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a1 = {'Resource_List.select': 'host=%s' % self.mom.shortname,
              'reserve_start': now + 3600,
              'reserve_end': now + 7200}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 5400,
              'reserve_end': now + 9000}
        h2 = [self.mom.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10'),
                    'reserve_substate': 12}
        self.server.expect(RESV, exp_attr, id=rid1)

    def test_maintenance_degrade_reservation_overlap3(self):
        """
        Test if the reservation is degraded by overlapping
        maintenance reservation - overlap: inner
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a1 = {'Resource_List.select': 'host=%s' % self.mom.shortname,
              'reserve_start': now + 3600,
              'reserve_end': now + 10800}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 5400,
              'reserve_end': now + 9000}
        h2 = [self.mom.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10'),
                    'reserve_substate': 12}
        self.server.expect(RESV, exp_attr, id=rid1)

    def test_maintenance_degrade_reservation_overlap4(self):
        """
        Test if the reservation is degraded by overlapping
        maintenance reservation - overlap: outer
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a1 = {'Resource_List.select': 'host=%s' % self.mom.shortname,
              'reserve_start': now + 3600,
              'reserve_end': now + 7200}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 1800,
              'reserve_end': now + 9000}
        h2 = [self.mom.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10'),
                    'reserve_substate': 12}
        self.server.expect(RESV, exp_attr, id=rid1)

    def test_maintenance_and_reservation_not_overlap1(self):
        """
        Test if the reservation is not degraded by maintenance
        reservation on the same host - not-overlap: before
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a1 = {'Resource_List.select': 'host=%s' % self.mom.shortname,
              'reserve_start': now + 10800,
              'reserve_end': now + 14400}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 3600,
              'reserve_end': now + 7200}
        h2 = [self.mom.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                    'reserve_substate': 2}
        self.server.expect(RESV, exp_attr, id=rid1)

    def test_maintenance_and_reservation_not_overlap2(self):
        """
        Test if the reservation is not degraded by maintenance
        reservation on the same host - not-overlap: after
        """
        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        a1 = {'Resource_List.select': 'host=%s' % self.mom.shortname,
              'reserve_start': now + 3600,
              'reserve_end': now + 7200}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 9000,
              'reserve_end': now + 12600}
        h2 = [self.mom.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                    'reserve_substate': 2}
        self.server.expect(RESV, exp_attr, id=rid1)

    def get_reg_expr(self, _mom, _host):
        """
        This function forms the match string based on cpuset mom
        """
        if _mom.is_cpuset_mom():
            n = self.server.status(NODE)
            cpuset_nodes = [i['id'] for i in n if i['Mom'] == _mom.hostname]
            reg_str = '\(%s\[0\]:ncpus=[0-9]+\)' % _host
            if (len(cpuset_nodes) - 1) > 1:
                for i in range(1, len(cpuset_nodes)-1):
                    reg_str += '\+' + '\(%s\[%s\]:ncpus=[0-9]+\)' % (_host, i)
        else:
            reg_str = "\(%s:ncpus=[0-9]+\)" % _host
        return reg_str

    @requirements(num_moms=2)
    def test_maintenance_two_hosts(self):
        """
        Test if the maintenance reservation is confirmed on multiple hosts.
        Test the crafted resv_nodes, select, and place.
        Two moms (-p "servers=M1,moms=M1:M2") are needed for this test.
        """
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        reg_expr_hostA = self.get_reg_expr(self.momA, self.hostA)
        reg_expr_hostB = self.get_reg_expr(self.momB, self.hostB)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (INCR, '%s@*' % TEST_USER)})
        now = int(time.time())
        a = {'reserve_start': now + 900,
             'reserve_end': now + 5400}
        h = [self.hostA, self.hostB]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        rid = self.server.submit(r)

        possibility1 = reg_expr_hostA + '\+' + reg_expr_hostB
        possibility2 = reg_expr_hostB + '\+' + reg_expr_hostA

        resv_nodes_re = "%s|%s" % (possibility1, possibility2)

        possibility1 = "host=%s:ncpus=[0-9]+\+host=%s:ncpus=[0-9]+" \
                       % (self.momA.shortname, self.momB.shortname)
        possibility2 = "host=%s:ncpus=[0-9]+\+host=%s:ncpus=[0-9]+" \
                       % (self.momB.shortname, self.momA.shortname)
        select_re = "%s|%s" % (possibility1, possibility2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                    'reserve_substate': 2,
                    'resv_nodes': (MATCH_RE, resv_nodes_re),
                    'Resource_List.select': (MATCH_RE, select_re),
                    'Resource_List.place': 'exclhost'}
        self.server.expect(RESV, exp_attr, id=rid)

    @requirements(num_moms=2)
    def test_maintenance_reconfirm_reservation_and_run(self):
        """
        Test if the overlapping reservation is reconfirmed correctly.
        Wait for both reservations to start and submit jobs into this
        reservations. Test if the jobs will run on correct nodes.
        Two moms (-p "servers=M1,moms=M1:M2") are needed for this test.
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (INCR, '%s@*' % TEST_USER)})
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduler_iteration': 3})

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        if self.momA.is_cpuset_mom():
            self.hostA += '[0]'
        if self.momB.is_cpuset_mom():
            self.hostB += '[0]'

        now = int(time.time())
        a1 = {'Resource_List.select': '1:ncpus=1',
              'reserve_start': now + 60,
              'reserve_end': now + 7200}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                    'resv_nodes': (EQ, '(%s:ncpus=1)' % self.hostA)}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 60,
              'reserve_end': now + 7200}
        h2 = [self.momA.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        rid2 = self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2'),
                    'resv_nodes': (EQ, '(%s:ncpus=1)' % self.hostB)}
        self.server.expect(RESV, exp_attr, id=rid1)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '1000',
             'queue': rid1.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(990)
        jid1 = self.server.submit(j)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '1000',
             'queue': rid2.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(990)
        jid2 = self.server.submit(j)

        self.logger.info("Wait for reservations to start (2 minutes)")
        time.sleep(120)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, exp_attr, id=rid1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, exp_attr, id=rid2)

        exp_attr = {'job_state': 'R',
                    'exec_vnode': "(%s:ncpus=1)" % self.hostB}
        self.server.expect(JOB, exp_attr, id=jid1)

        exp_attr = {'job_state': 'R',
                    'exec_vnode': "(%s:ncpus=1)" % self.hostA}
        self.server.expect(JOB, exp_attr, id=jid2)

    @requirements(num_moms=2)
    def test_maintenance_progressive_degrade_reservation(self):
        """
        Test if the reservation is partially degraded by overlapping
        maintenance reservation at first, and then do full overlap.
        Test if the job in fully overlapped reservation will not run.
        Two moms (-p "servers=M1,moms=M1:M2") are needed for this test.
        """
        if len(self.moms) != 2:
            cmt = "need 2 mom hosts: -p servers=<m1>,moms=<m1>:<m2>"
            self.skip_test(reason=cmt)

        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': '%s@*' % TEST_USER})

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]

        select = 'host=%s+host=%s' % (self.momA.shortname,
                                      self.momB.shortname)
        a1 = {'Resource_List.select': select,
              'reserve_start': now + 60,
              'reserve_end': now + 7200}
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=rid1)

        a2 = {'reserve_start': now + 1800,
              'reserve_end': now + 5400}
        h2 = [self.momA.shortname]
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)

        self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|12'),
                    'reserve_substate': 12}
        self.server.expect(RESV, exp_attr, id=rid1)
        self.server.status(RESV, id=rid1)
        vnodes = r1.get_vnodes()
        self.assertEqual(len(vnodes), 1)
        vnode = self.server.status(NODE, id=vnodes[0])[0]
        self.assertEqual(vnode['Mom'], self.momB.hostname)

        self.logger.info("Wait for reservation to start (2 minutes)")
        time.sleep(120)

        a3 = {'reserve_start': now + 1800,
              'reserve_end': now + 5400}
        h3 = [self.momB.shortname]
        r3 = Reservation(TEST_USER, attrs=a3, hosts=h3)

        self.server.submit(r3)

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': '1000',
             'queue': rid1.split('.')[0]}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(990)
        jid1 = self.server.submit(j)

        self.logger.info("Wait for the job to try to run (30 seconds)")
        time.sleep(30)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

    def test_maintenance_degrade_reservation_jobs_dont_run(self):
        """
        Test if the reservation is degraded by overlapping
        maintenance reservation the jobs inside that degraded reservations do
        not run when the maintenance reservation starts running.
        """

        now = int(time.time())

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'managers': (INCR, '%s@*' % TEST_USER)})

        a1 = {'reserve_start': now + 30,
              'reserve_end': now + 1200}
        start = now + 30
        r1 = Reservation(TEST_USER, attrs=a1)
        rid1 = self.server.submit(r1)
        resv_name = rid1.split('.')[0]

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, exp_attr, id=resv_name)
        self.server.status(RESV, 'resv_nodes', id=rid1)
        resv_node_list = self.server.reservations[rid1].get_vnodes()
        resv_node = resv_node_list[0]

        # On a cpuset machine the resv_node could be a vnode,
        # always pull the hostname from the node attribute
        status = self.server.status(NODE, id=resv_node)
        h2 = [status[0]['resources_available.host']]

        jid = self.server.submit(Job(attrs={ATTR_q: resv_name}))

        a2 = {'reserve_start': now + 35,
              'reserve_end': now + 1000}
        r2 = Reservation(TEST_USER, attrs=a2, hosts=h2)
        rid2 = self.server.submit(r2)

        exp_attr = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10'),
                    'reserve_substate': 12}
        self.server.expect(RESV, exp_attr, id=rid1)
        resv_state = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.logger.info('Sleeping until reservation starts')
        offset = start - int(time.time())
        self.server.expect(RESV, resv_state, id=rid1,
                           offset=offset)
        self.server.expect(RESV, resv_state, id=rid2,
                           offset=offset)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': True})
        a = {'comment': 'Not Running: Queue not started.',
             'job_state': 'Q'}
        self.server.expect(JOB, a, id=jid)

    def test_maintenance_parse_numerous_hosts(self):
        """
        Test if the parsing of numerous hosts succeed.
        """
        now = int(time.time())

        a = {'reserve_start': now + 3600,
             'reserve_end': now + 7200}
        chars = 'abcdefghijklmnopqrstuvwxyz'
        h = [''.join(random.choices(chars, k=8)) for i in range(200)]
        r = Reservation(TEST_USER, attrs=a, hosts=h)

        with self.assertRaises(PbsSubmitError) as err:
            self.server.submit(r)

        msg = err.exception.msg[0].strip()

        regex = "^pbs_rsub: Host with resources not found: .*"
        self.assertTrue(re.search(regex, msg))

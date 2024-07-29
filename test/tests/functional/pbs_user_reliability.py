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

import re

from tests.functional import *


class Test_user_reliability(TestFunctional):

    """
    This test suite is for testing the user reliability workflow feature.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        if len(self.moms) > 1:
            self.fakeuser = 'fakeuser'
            momB = self.moms.values()[1]
            cmd = ['useradd', '-d', '/tmp', self.fakeuser]
            ret = self.du.run_cmd(momB.hostname, cmd=cmd, sudo=True)
            self.assertTrue(ret['rc'] in [0, 9])  # 9 is already existing user

    def test_create_resv_from_job_using_runjob_hook(self):
        """
        This test is for creating a reservation out of a job using runjob hook.
        """
        qmgr_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                'bin', 'qmgr')

        runjob_hook_body = """
import pbs
e = pbs.event()
j = e.job
j.create_resv_from_job=1
"""
        hook_event = "runjob"
        hook_name = "rsub"
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, runjob_hook_body)

        s_ncpus = 'resources_assigned.ncpus'
        s_nodect = 'resources_assigned.nodect'
        try:
            s_ncpus_before = self.server.status(SERVER, s_ncpus)[0][s_ncpus]
            s_nodect_before = self.server.status(SERVER, s_nodect)[0][s_nodect]
        except IndexError:
            s_nodect_before = '0'
            s_ncpus_before = '0'

        a = {'Resource_List.walltime': 9999}
        job = Job(TEST_USER, a)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid)

        a = {ATTR_job: jid}
        rid = self.server.status(RESV, a)[0]['id'].split(".")[0]

        a = {ATTR_job: jid, 'reserve_state': (MATCH_RE, 'RESV_RUNNING|5'),
             'Resource_List.walltime': 9999}
        self.server.expect(RESV, a, id=rid)

        a = {ATTR_queue: rid}
        self.server.expect(JOB, a, id=jid)

        self.server.deljob(jid, wait=True)
        self.server.expect(RESV, a, id=rid)
        self.server.delete(rid)

        s_ncpus_after = self.server.status(SERVER, s_ncpus)[0][s_ncpus]
        s_nodect_after = self.server.status(SERVER, s_nodect)[0][s_nodect]

        self.assertEqual(s_ncpus_before, s_ncpus_after)
        self.assertEqual(s_nodect_before, s_nodect_after)

    def test_create_resv_from_job_using_qsub(self):
        """
        This test is for creating a reservation out of a job using qsub.
        """
        s_ncpus = 'resources_assigned.ncpus'
        s_nodect = 'resources_assigned.nodect'
        try:
            s_ncpus_before = self.server.status(SERVER, s_ncpus)[0][s_ncpus]
            s_nodect_before = self.server.status(SERVER, s_nodect)[0][s_nodect]
        except IndexError:
            s_nodect_before = '0'
            s_ncpus_before = '0'

        now = time.time()

        a = {ATTR_W: 'create_resv_from_job=True'}
        job = Job(TEST_USER, a)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid)

        self.server.log_match("Reject reply code=15095", starttime=now,
                              interval=2, max_attempts=10, existence=False)

        a = {ATTR_job: jid}
        rid = self.server.status(RESV, a)[0]['id'].split(".")[0]

        a = {ATTR_job: jid, 'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid)

        a = {ATTR_queue: rid}
        self.server.expect(JOB, a, id=jid)

        self.server.deljob(jid, wait=True)
        self.server.expect(RESV, a, id=rid)
        self.server.delete(rid)

        s_ncpus_after = self.server.status(SERVER, s_ncpus)[0][s_ncpus]
        s_nodect_after = self.server.status(SERVER, s_nodect)[0][s_nodect]

        self.assertEqual(s_ncpus_before, s_ncpus_after)
        self.assertEqual(s_nodect_before, s_nodect_after)

        a = {ATTR_W: 'create_resv_from_job=False'}
        job = Job(TEST_USER, a)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid)
        self.assertFalse(self.server.status(RESV))

    def test_create_resv_from_job_using_rsub(self):
        """
        This test is for creating a reservation out of a job using pbs_rsub.
        """
        s_ncpus = 'resources_assigned.ncpus'
        s_nodect = 'resources_assigned.nodect'
        try:
            s_ncpus_before = self.server.status(SERVER, s_ncpus)[0][s_ncpus]
            s_nodect_before = self.server.status(SERVER, s_nodect)[0][s_nodect]
        except IndexError:
            s_nodect_before = '0'
            s_ncpus_before = '0'

        a = {'Resource_List.walltime': 9999}
        job = Job(TEST_USER, a)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid)

        a = {ATTR_job: jid}
        resv = Reservation(attrs=a)
        self.server.submit(resv)

        a = {ATTR_job: jid}
        rid = self.server.status(RESV, a)[0]['id'].split(".")[0]

        a = {ATTR_job: jid, 'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, a, id=rid)

        a = {ATTR_queue: rid}
        self.server.expect(JOB, a, id=jid)

        self.server.deljob(jid, wait=True)
        self.server.expect(RESV, a, id=rid)
        self.server.delete(rid)

        s_ncpus_after = self.server.status(SERVER, s_ncpus)[0][s_ncpus]
        s_nodect_after = self.server.status(SERVER, s_nodect)[0][s_nodect]

        self.assertEqual(s_ncpus_before, s_ncpus_after)
        self.assertEqual(s_nodect_before, s_nodect_after)

    def test_create_resv_from_array_job(self):
        """
        This test confirms that a reservation cannot be created out of an
        array job.
        """

        j = Job(TEST_USER)
        j.set_attributes({ATTR_J: '1-3'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'B'}, jid)

        subjobs = self.server.status(JOB, id=jid, extend='t')
        jids1 = subjobs[1]['id']

        a = {ATTR_job: jids1}
        resv = Reservation(attrs=a)
        msg = "Reservation may not be created from an array job"
        try:
            self.server.submit(resv)
        except PbsSubmitError as e:
            self.assertTrue(msg in e.msg[0])
        else:
            self.fail("Error message not as expected")

        a = {ATTR_job: jid}
        resv = Reservation(attrs=a)
        try:
            self.server.submit(resv)
        except PbsSubmitError as e:
            self.assertTrue(msg in e.msg[0])
        else:
            self.fail("Error message not as expected")

    def test_create_resv_by_other_user(self):
        """
        This test confirms that a reservation cannot be created out of an
        job owned by someone else.
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        a = {ATTR_job: jid}
        resv = Reservation(username=TEST_USER2, attrs=a)
        msg = "Unauthorized Request"
        try:
            self.server.submit(resv)
        except PbsSubmitError as e:
            self.assertTrue(msg in e.msg[0])
        else:
            self.fail("Error message not as expected")

    def test_flatuid_false(self):
        """
        This test confirms that a reservation can be created out of a job
        even when flatuid is set to False.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'flatuid': False})
        self.test_create_resv_from_job_using_qsub()

    def test_set_attr_when_job_running(self):
        """
        This test confirms that create_resv_from_job is not allowed to be
        altered when the job is already running.
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)

        msg = "attribute allowed to be modified"
        with self.assertRaises(PbsAlterError, msg=msg) as c:
            self.server.alterjob(jid, {ATTR_W: 'create_resv_from_job=1'})

        msg = "qalter: Cannot modify attribute while job running  "
        msg += "create_resv_from_job"
        self.assertIn(msg, c.exception.msg[0])

    @requirements(num_moms=2)
    def test_validate_user_allow(self):
        """
        This test that non-valid user can submit a job if
        validate_user is disabled. Mom will report the problem.
        """
        self.logger.info("len moms = %d" % (len(self.moms)))
        if len(self.moms) < 2:
            usage_string = 'test requires 2 MoMs as input, ' + \
                           'use -p "servers=M1,moms=M1:M2"'
            self.skip_test(usage_string)

        self.server.manager(MGR_CMD_SET, SERVER, {'validate_user': False})

        momA = self.moms.values()[0]
        momB = self.moms.values()[1]

        qsub_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                'bin', 'qsub')
        select = f'-l select=1:host={momA.hostname}'
        cmd = [qsub_cmd, select, '--', momB.sleep_cmd, '100']
        ret = self.du.run_cmd(momB.hostname, cmd=cmd, runas=self.fakeuser)
        self.assertEquals(ret['rc'], 0)
        momA.log_match("No Password Entry for User")

    @requirements(num_moms=2)
    def test_validate_user_deny(self):
        """
        This test that non-valid user can not submit a job if
        validate_user is enabled on the server.
        """
        self.logger.info("len moms = %d" % (len(self.moms)))
        if len(self.moms) < 2:
            usage_string = 'test requires 2 MoMs as input, ' + \
                           'use -p "servers=M1,moms=M1:M2"'
            self.skip_test(usage_string)

        self.server.manager(MGR_CMD_SET, SERVER, {'validate_user': True})

        momB = self.moms.values()[1]

        qsub_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                'bin', 'qsub')
        cmd = [qsub_cmd, '--', momB.sleep_cmd, '100']
        ret = self.du.run_cmd(momB.hostname, cmd=cmd, runas=self.fakeuser)
        self.assertEquals(ret['err'][0], "qsub: Unauthorized Request ")

    def tearDown(self):
        if self.fakeuser is not None and len(self.moms) > 1:
            momB = self.moms.values()[1]
            cmd = ['userdel', '-f', self.fakeuser]
            self.du.run_cmd(momB.hostname, cmd=cmd, sudo=True)
        TestFunctional.tearDown(self)

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
import re


class Test_user_reliability(TestFunctional):

    """
    This test suite is for testing the user reliability workflow feature.
    """
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

        a = {ATTR_W: 'create_resv_from_job=1'}
        job = Job(TEST_USER, a)
        jid = self.server.submit(job)
        self.server.expect(JOB, {ATTR_state: 'R'}, jid)

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
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')

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

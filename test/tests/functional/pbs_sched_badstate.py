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


import copy
from tests.functional import *


class TestSchedBadstate(TestFunctional):

    def test_sched_badstate_subjob(self):
        """
        This test case tests if scheduler goes into infinite loop
        when following conditions are met.
        - Kill a mom
        - mark the mom's state as free
        - submit an array job
        - check the sched log for "Leaving sched cycle" from the time
          array job was submitted.
        If we are unable to find a log match then scheduler is in
          endless loop and test case has failed.
        """

        self.mom.signal(self.mom, '-KILL')

        attr = {'state': 'free', 'resources_available.ncpus': '2'}
        self.server.manager(MGR_CMD_SET, NODE, attr, self.mom.shortname)

        attr = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)

        j1 = Job(TEST_USER)
        j1.set_attributes({'Resource_List.ncpus': '2', ATTR_J: '1-3'})
        j1id = self.server.submit(j1)

        now = time.time()

        attr = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)

        self.scheduler.log_match("Leaving Scheduling Cycle",
                                 starttime=now,
                                 interval=1)
        self.server.delete(j1id)

    def test_sched_unknown_node_state(self):
        """
        Test to see if the scheduler reports node states as 'Unknown'
        """
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 2047})

        # free is when all ncpus are free
        self.server.expect(NODE, {'state': 'free'}, id=self.mom.shortname)
        self.scheduler.log_match("Unknown Node State",
                                 existence=False, max_attempts=2)
        ncpus = self.server.status(NODE)[0]['resources_available.ncpus']
        if self.mom.is_cpuset_mom():
            vnode_id = self.server.status(NODE)[1]['id']
            vnode_val = 'vnode=' + vnode_id
            ncpus = self.server.status(NODE)[1]['resources_available.ncpus']
            a = {'Resource_List.select': vnode_val + ':ncpus=' + ncpus}
        else:
            a = {'Resource_List.select': '1:ncpus=' + ncpus}
        b = a.copy()
        J = Job(attrs=a)
        jid1 = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        if self.mom.is_cpuset_mom():
            self.server.expect(VNODE, {'state': 'job-busy'}, id=vnode_id)
        else:
            self.server.expect(NODE, {'state': 'job-busy'},
                               id=self.mom.shortname)
        self.scheduler.log_match("Unknown Node State",
                                 existence=False, max_attempts=2)

        # maintenance is when a job is has been admin-suspended
        self.server.sigjob(jid1, 'admin-suspend')
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        if self.mom.is_cpuset_mom():
            self.server.expect(VNODE, {'state': 'maintenance'}, id=vnode_id)
        else:
            self.server.expect(NODE, {'state': 'maintenance'},
                               id=self.mom.shortname)
        self.scheduler.log_match("Unknown Node State",
                                 existence=False, max_attempts=2)

        self.server.delete(jid1, wait=True)

        # job-exclusive is when a job requests place=excl
        b['Resource_List.place'] = 'excl'
        J = Job(attrs=b)
        jid2 = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        if self.mom.is_cpuset_mom():
            self.server.expect(VNODE, {'state': 'job-exclusive'}, id=vnode_id)
        else:
            self.server.expect(NODE, {'state': 'job-exclusive'},
                               id=self.mom.shortname)
        self.scheduler.log_match("Unknown Node State",
                                 existence=False, max_attempts=2)

        self.server.delete(jid2, wait=True)

        # resv-exclusive is when a reservation requersts -lplace=excl
        st = time.time() + 30
        et = st + 30
        b['reserve_start'] = st
        b['reserve_end'] = et
        R = Reservation(attrs=b)
        rid = self.server.submit(R)
        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_CONFIRMED|2')}, id=rid)

        self.server.expect(RESV, {'reserve_state':
                                  (MATCH_RE, 'RESV_RUNNING|5')},
                           id=rid, offset=30)

        if self.mom.is_cpuset_mom():
            self.server.expect(VNODE, {'state': 'resv-exclusive'}, id=vnode_id)
        else:
            self.server.expect(NODE, {'state': 'resv-exclusive'},
                               id=self.mom.shortname)
        self.scheduler.log_match("Unknown Node State",
                                 existence=False, max_attempts=2)
        self.server.delete(rid)

        # Multiple node states eg: down + job-busy
        J = Job(attrs=a)
        jid3 = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        self.mom.signal(self.mom, '-KILL')
        if self.mom.is_cpuset_mom():
            self.server.expect(VNODE, {'state': 'down,job-busy'},
                               id=vnode_id)
        else:
            self.server.expect(NODE, {'state': 'down,job-busy'},
                               id=self.mom.shortname)
        self.scheduler.log_match("Unknown Node State",
                                 existence=False, max_attempts=2)

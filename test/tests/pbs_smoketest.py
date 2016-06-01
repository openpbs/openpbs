# coding: utf-8

# Copyright (C) 1994-2016 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
# Commercial License Information: 
#
# The PBS Pro software is licensed under the terms of the GNU Affero General 
# Public License agreement ("AGPL"), except where a separate commercial license 
# agreement for PBS Pro version 14 or later has been executed in writing with Altair.
# 
# Altair’s dual-license business model allows companies, individuals, and 
# organizations to create proprietary derivative works of PBS Pro and distribute 
# them - whether embedded or bundled with other software - under a commercial 
# license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™", 
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
# trademark licensing policies.

from ptl.utils.pbs_testsuite import *


class SmokeTest(PBSTestSuite):

    """
    This test suite contains a few smoke tests of PBS

    """

    def test_submit_job(self):
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_submit_job_array(self):
        a = {'resources_available.ncpus': (GE, 3), 'state': 'free'}
        try:
            rv = self.server.expect(NODE, a, attrop=PTL_AND, max_attempts=1,
                                    id=self.mom.shortname)
        except PtlExpectError, e:
            rv = e.rv

        if not rv:
            a = {'resources_available.ncpus': 8}
            self.server.create_vnodes('vnode', a, 1, self.mom,
                                      usenatvnode=True)
        j = Job(TEST_USER)
        j.set_attributes({ATTR_J: '1-3:1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')

    def test_standing_reservation(self):
        # PBS_TZID environment variable must be set, there is no way to set
        # it through the API call, use CLI instead for this test

        _m = self.server.get_op_mode()
        if _m != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)

        if 'PBS_TZID' in self.conf:
            tzone = self.conf['PBS_TZID']
        elif 'PBS_TZID' in os.environ:
            tzone = os.environ['PBS_TZID']
        else:
            self.logger.info('Missing timezone, using America/Los_Angeles')
            tzone = 'America/Los_Angeles'

        a = {'Resource_List.select': '1:ncpus=1',
             ATTR_resv_rrule: 'FREQ=WEEKLY;COUNT=3',
             ATTR_resv_timezone: tzone,
             ATTR_resv_standing: '1',
             'reserve_start': time.time() + 20,
             'reserve_end': time.time() + 30,
             }
        r = Reservation(TEST_USER, a)

        rid = self.server.submit(r)

        a = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, a, id=rid)
        if _m == PTL_API:
            self.server.set_op_mode(PTL_API)

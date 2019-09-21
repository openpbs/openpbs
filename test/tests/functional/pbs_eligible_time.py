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
from ptl.utils.pbs_logutils import PBSLogUtils


class TestEligibleTime(TestFunctional):
    """
    Test suite for eligible time tests
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'eligible_time_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.accrue = {'ineligible': 1, 'eligible': 2, 'run': 3, 'exit': 4}

    def test_qsub_a(self):
        """
        Test that jobs requsting qsub -a <time> do not accrue
        eligible time until <time> is reached
        """
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        now = int(time.time())
        now += 120
        s = time.strftime("%H%M.%S", time.localtime(now))

        J1 = Job(TEST_USER, attrs={ATTR_a: s})
        jid = self.server.submit(J1)
        self.server.expect(JOB, {ATTR_state: 'W'}, id=jid)

        self.logger.info("Sleeping 120s till job is out of 'W' state")
        time.sleep(120)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)
        # eligible_time should really be 0, but just incase there is some
        # lag on some slow systems, add a little leeway.
        self.server.expect(JOB, {'eligible_time': 10}, op=LT)

    def test_job_array(self):
        """
        Test that a job array switches from accruing eligible time
        to ineligible time when its last subjob starts running
        """
        logutils = PBSLogUtils()
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

        a = {'log_events': 2047}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        J1 = Job(TEST_USER, attrs={ATTR_J: '1-3'})
        J1.set_sleep_time(20)
        jid = self.server.submit(J1)
        jid_short = jid.split('[')[0]
        sjid1 = jid_short + '[1]'
        sjid2 = jid_short + '[2]'
        sjid3 = jid_short + '[3]'

        # Capture the time stamp when subjob 1 starts run. Accrue type changes
        # to eligible time
        msg1 = J1.create_subjob_id(jid, 1) + ";Job Run at request of Scheduler"
        m1 = self.server.log_match(msg1)
        t1 = logutils.convert_date_time(m1[1].split(';')[0])

        self.server.expect(JOB, {ATTR_state: 'R'}, id=sjid1, extend='t')
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sjid2, extend='t')
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=sjid3, extend='t')

        self.server.expect(JOB, {'accrue_type': self.accrue['eligible']},
                           id=jid)

        self.logger.info("subjobs 1 and 2 finished; subjob 3 must run now")
        self.server.expect(JOB, {ATTR_state: 'R'}, id=sjid3,
                           extend='t', offset=20)
        self.server.expect(JOB, {'accrue_type': self.accrue['ineligible']},
                           id=jid)

        # Capture the time stamp when subjob 3 starts run. Accrue type changes
        # to ineligible time. eligible_time calculation is completed.
        msg2 = J1.create_subjob_id(jid, 3) + ";Job Run at request of Scheduler"
        m2 = self.server.log_match(msg2)
        t2 = logutils.convert_date_time(m2[1].split(';')[0])
        eligible_time = int(t2) - int(t1)

        m1 = jid + ";Accrue type has changed to ineligible_time, "
        m1 += "previous accrue type was eligible_time"

        m2 = m1 + " for %d secs, " % eligible_time
        # Format timedelta object as it does not print a preceding 0 for
        # hours in HH:MM:SS
        m2 += "total eligible_time={!s:0>8}".format(
              datetime.timedelta(seconds=eligible_time))
        try:
            self.server.log_match(m2)
        except PtlLogMatchError as e:
            # In some slow machines, there is a delay observed between
            # job run and accrue type change.
            # Checking if log_match failed because eligible_time
            # value was off only by a few seconds(5 seconds).
            # This is done to acommodate differences in the eligible
            # time calculated by the test and the eligible time
            # calculated by PBS.
            # If the eligible_time value was off by > 5 seconds, test fails.
            match = self.server.log_match(m1)
            e_time = re.search(r'(\d+) secs', match[1])
            if e_time:
                self.logger.info("Checking if log_match failed because "
                                 "the eligible_time value was off by "
                                 "a few seconds, but within the allowed "
                                 "range (5 secs). Expected %d secs Got: %s"
                                 % (eligible_time, e_time.group(1)))
                if int(e_time.group(1)) - eligible_time > 5:
                    raise PtlLogMatchError(rc=1, rv=False, msg=e.msg)
            else:
                raise PtlLogMatchError(rc=1, rv=False, msg=e.msg)

    def test_after_depend(self):
        """
        Make sure jobs accrue eligible time (or not) approprately with an
        after dependency
        """

        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 2},
                            id=self.mom.shortname)
        J1 = Job(TEST_USER)
        jid1 = self.server.submit(J1)
        attribs = {'job_state': 'R', 'accrue_type': self.accrue['run']}
        self.server.expect(JOB, attribs, id=jid1)

        J2 = Job(TEST_USER, {'Resource_List.select': '1:ncpus=2'})
        jid2 = self.server.submit(J2)
        attribs = {'job_state': 'Q', 'accrue_type': self.accrue['eligible']}
        self.server.expect(JOB, attribs, id=jid2)

        a = {'Resource_List.select': '1:ncpus=1',
             ATTR_depend: 'afterany:' + jid2}
        J3 = Job(TEST_USER, a)
        jid3 = self.server.submit(J3)
        attribs = {'job_state': 'H', 'accrue_type': self.accrue['ineligible']}
        self.server.expect(JOB, attribs, id=jid3)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'max_run_res.ncpus': '[u:PBS_GENERIC=1]'})

        # Make sure there are enough resources to run the job, so the reason
        # the job can't run is the limit.  Otherwise, we'd accrue eligible time
        self.server.manager(MGR_CMD_SET, NODE,
                            {'resources_available.ncpus': 3},
                            id=self.mom.shortname)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

        self.server.expect(JOB, {'accrue_type': self.accrue['ineligible']},
                           id=jid2)

        # force the server to reassess the accrue type
        self.server.holdjob(jid2, 'u')
        self.server.rlsjob(jid2, 'u')

        self.server.expect(JOB, {'accrue_type': self.accrue['ineligible']},
                           id=jid2)

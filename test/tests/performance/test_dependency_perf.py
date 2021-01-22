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


from tests.performance import *


class TestDependencyPerformance(TestPerformance):
    """
    Test the performance of job dependency feature
    """

    def check_depend_delete_msg(self, pjid, cjid):
        """
        helper function to check ia message that the dependent job (cjid)
        is deleted because of the parent job (pjid)
        """
        msg = cjid + ";Job deleted as result of dependency on job " + pjid
        self.server.log_match(msg)

    @timeout(1800)
    def test_delete_long_dependency_chains(self):
        """
        Submit a very long chain of dependent jobs and then measure the time
        PBS takes to get rid of all dependent jobs.
        """

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = Job()
        job.set_sleep_time(3600)
        jid = self.server.submit(job)
        j_arr = [jid]
        for _ in range(5000):
            a = {ATTR_depend: 'afternotok:' + jid}
            jid = self.server.submit(Job(attrs=a))
            j_arr.append(jid)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=j_arr[0])
        self.server.expect(JOB, {ATTR_state: 'H'}, id=j_arr[5000])
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        t1 = time.time()
        self.server.delete(j_arr[0])
        self.server.expect(JOB, {ATTR_state: 'F'}, id=j_arr[5000],
                           extend='x', interval=2)
        t2 = time.time()
        self.logger.info('#' * 80)
        self.logger.info('Time taken to delete all jobs %f' % (t2-t1))
        self.logger.info('#' * 80)
        self.check_depend_delete_msg(j_arr[4999], j_arr[5000])
        self.perf_test_result((t2 - t1),
                              "time_taken_delete_all_dependent_jobs", "sec")

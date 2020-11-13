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


import subprocess
import time
import statistics
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import wait
from ptl.utils.pbs_testsuite import *
from ptl.utils.pbs_testusers import PBS_USERS


class TestPerformance(PBSTestSuite):
    """
    Base test suite for Performance tests
    """

    def check_value(self, res):
        if isinstance(res, list):
            for val in res:
                if not isinstance(val, (int, float)):
                    raise self.failureException(
                        "Test result list must be int or float")
        else:
            if not isinstance(res, (int, float)):
                raise self.failureException("Test result must be int or float")

    def perf_test_result(self, result, test_measure, unit):
        """
        Add test results to json file. If a multiple trial values are passed
        calculate mean,std_dev,min,max for the list.
        """
        self.check_value(result)
        if isinstance(result, list) and len(result) > 1:
            mean_res = statistics.mean(result)
            mean_res = round(mean_res, 2)
            stddev_res = statistics.stdev(result)
            stddev_res = round(stddev_res, 2)
            max_res = round(max(result), 2)
            min_res = round(min(result), 2)
            trial_no = 1
            trial_data = []
            for trial_result in result:
                trial_result = round(trial_result, 2)
                trial_data.append(
                    {"trial_no": trial_no, "value": trial_result})
                trial_no += 1
            test_data = {"test_measure": test_measure,
                         "unit": unit,
                         "test_data": {"mean": mean_res,
                                       "std_dev": stddev_res,
                                       "minimum": min_res,
                                       "maximum": max_res,
                                       "trials": trial_data}}
            return self.set_test_measurements(test_data)
        else:
            variance = 0
            if isinstance(result, list):
                result = result[0]
            if isinstance(result, float):
                result = round(result, 2)
            testdic = {"test_measure": test_measure, "unit": unit,
                       "test_data": {"mean": result,
                                     "std_dev": variance,
                                     "minimum": result,
                                     "maximum": result}}
            return self.set_test_measurements(testdic)

    def run_parallel(self, users, cmd, cmd_repeat):
        """
        Run commands parallely with n number of users
        """
        _o = self._outcome
        self._outcome = None
        cmd += ' > /dev/null'
        reslt = []
        with ProcessPoolExecutor(max_workers=users) as executor:
            procs = {executor.submit(
                self.submit_cmd, users, cmd, cmd_repeat) for u in range(users)}
            results, procs = wait(procs)
            for res in results:
                reslt.append(res.result())
        self._outcome = _o
        return reslt

    def submit_cmd(self, u, cmd, cmd_repeat):
        """
        Run commands as user and return time taken
        """
        os.chdir('/tmp')
        users = PBS_USERS * 10
        cmd = 'sudo -u ' + str(users[u]) + ' ' + cmd
        start = time.time()
        for _ in range(cmd_repeat):
            subprocess.call(cmd, shell=True)
        stop = time.time()
        res = stop - start
        return res

    pass

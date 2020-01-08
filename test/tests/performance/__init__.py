# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

import math
from math import sqrt
from ptl.utils.pbs_testsuite import *


class TestPerformance(PBSTestSuite):
    """
    Base test suite for Performance tests
    """

    def mean(self, lst):
        """calculates mean"""
        return sum(lst) / len(lst)

    def stddev(self, lst):
        """returns the standard deviation of lst"""
        mn = self.mean(lst)
        variance = sum([(e - mn) ** 2 for e in lst]) / len(lst)
        return sqrt(variance)

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
            mean_res = self.mean(result)
            mean_res = round(mean_res, 2)
            stddev_res = self.stddev(result)
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

    pass

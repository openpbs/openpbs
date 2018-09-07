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

from tests.selftest import *
from ptl.utils.plugins.ptl_report_json import PTLJsonData


class TestJSONReport(TestSelf):
    """
    Tests to test JSON test report
    """

    def test_json_fields(self):
        """
        Test to verify fields of JSON test report
        """
        test_data = {
            'status': 'PASS',
            'start_time': datetime.datetime(2018, 10, 4, 0, 18, 8, 509426),
            'hostname': self.server.hostname,
            'status_data': '',
            'pbs_version': '19.2.0.20180903140741',
            'testcase': 'test_select',
            'end_time': datetime.datetime(2018, 10, 4, 0, 18, 11, 153022),
            'testdoc': '\n        Test to qselect\n        ',
            'duration': datetime.timedelta(0, 2, 643596),
            'suite': 'SmokeTest',
            'testparam': 'ABC=DEF,x=100',
            'machinfo': {
                self.server.hostname: {
                    'platform': 'Linux centos7alpha3.10.0-862.11.6.el7.x86_64',
                    'pbs_install_type': 'server',
                    'os_info': 'Linux-3.10.0-862.11.6.el7.x86_64-x86_64'
                }
            },
            'suitedoc': '\n    This test suite contains smoke tests of PBS\n',
            'tags': ['smoke'],
            'file': 'tests/pbs_smoketest.py',
            'module': 'tests.pbs_smoketest',
            'requirements': {
                "num_moms": 1,
                "no_comm_on_mom": True,
                "no_comm_on_server": False,
                "num_servers": 1,
                "no_mom_on_server": False,
                "num_comms": 1,
                "num_clients": 1
            }
        }
        verify_data = {
            'test_keys': ["command", "user", "product_version", "run_id",
                          "test_conf", "machine_info", "testsuites",
                          "test_summary", "additional_data"],
            'test_summary_keys': ["result_summary", "test_start_time",
                                  "test_end_time", "tests_with_failures",
                                  "test_suites_with_failures"],
            'test_machine_info': ["platform", "os_info", "pbs_install_type"],
            'test_results': ["run", "succeeded", "failed", "errors", "skipped",
                             "timedout"],
            'test_suites_info': ["testcases", "docstring", "module", "file"],
            'test_cases_info': ["docstring", "tags", "requirements",
                                "results"],
            'test_results_info': ["duration", "status", "status_data",
                                  "start_time", "end_time", "measurements"]
        }
        field_values = {
            'machine_info_name': list(test_data['machinfo'].keys())[0],
            'testresult_status': test_data['status'],
            'requirements': {
                "num_moms": 1,
                "no_comm_on_mom": True,
                "no_comm_on_server": False,
                "num_servers": 1,
                "no_mom_on_server": False,
                "num_comms": 1,
                "num_clients": 1
            }
        }
        faulty_fields = []
        faulty_values = []
        test_cmd = "pbs_benchpress -t SmokeTest.test_submit_job"
        jsontest = PTLJsonData(command=test_cmd)
        jdata = jsontest.get_json(data=test_data, prev_data=None)
        tsname = test_data['suite']
        tcname = test_data['testcase']
        vdata = jdata['testsuites'][tsname]['testcases'][tcname]
        for k in verify_data['test_keys']:
            if k not in jdata:
                faulty_fields.append(k)
        for l in verify_data['test_summary_keys']:
            if l not in jdata['test_summary']:
                faulty_fields.append(l)
        for o in verify_data['test_results']:
            if o not in jdata['test_summary']['result_summary']:
                faulty_fields.append(o)
        for node in jdata['machine_info']:
            for m in verify_data['test_machine_info']:
                if m not in jdata['machine_info'][node]:
                    faulty_fields.append(m)
        for q in jdata['testsuites']:
            for p in verify_data['test_suites_info']:
                if p not in jdata['testsuites'][q]:
                    faulty_fields.append(p)
        for s in jdata['testsuites']:
            for t in jdata['testsuites'][s]:
                for u in jdata['testsuites'][s]['testcases']:
                    for r in verify_data['test_cases_info']:
                        if r not in jdata['testsuites'][s]['testcases'][u]:
                            faulty_fields.append(r)
        for s in jdata['testsuites']:
            for t in jdata['testsuites'][s]['testcases']:
                for v in verify_data['test_results_info']:
                    testcase = jdata['testsuites'][s]['testcases'][t]
                    if v not in testcase['results']:
                        faulty_fields.append(v)
        for k, v in field_values.items():
            if k == 'machine_info_name':
                if list(jdata['machine_info'].keys())[0] != v:
                    faulty_values.append(k)
            if k == 'testresult_status':
                if vdata['results']['status'] != v:
                    faulty_values.append(k)
            if k == 'requirements':
                if vdata['requirements'] != v:
                    faulty_values.append(r)
        if (faulty_fields or faulty_values):
            raise AssertionError("Faulty fields or values",
                                 (faulty_fields, faulty_values))

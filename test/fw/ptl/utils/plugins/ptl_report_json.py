# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
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

import re
from ptl.utils.pbs_dshutils import DshUtils


class PTLJsonData(object):
    """
    The intent of the class is to generate json format of PTL test data
    """

    def __init__(self, command):
        self.__du = DshUtils()
        self.__cmd = command

    def get_json(self, data, prev_data=None):
        """
        Method to generate test data in accordance to json schema

        :param data: dictionary of a test case details
        :type data: dict
        :param prev_data: dictionary of test run details that ran before
                          the current test
        :type prev_data: dict

        :returns a formatted dictionary of the data
        """
        data_json = None
        if not prev_data:
            data_json = {
                'command': self.__cmd,
                'user': self.__du.get_current_user(),
                'product_version': data['pbs_version'],
                'run_id': data['start_time'].strftime('%s'),
                'test_conf': {},
                'machine_info': data['machinfo'],
                'testsuites': {},
                'additional_data': {},
                'test_summary': {
                    'result_summary': {
                        'run': 0,
                        'succeeded': 0,
                        'failed': 0,
                        'errors': 0,
                        'skipped': 0,
                        'timedout': 0
                    },
                    'test_start_time': str(data['start_time']),
                    'tests_with_failures': [],
                    'test_suites_with_failures': []
                }
            }
            if data['testparam']:
                for param in data['testparam'].split(','):
                    par = param.split('=', 1)
                    data_json['test_conf'][par[0]] = par[1]
        else:
            data_json = prev_data
        tsname = data['suite']
        tcname = data['testcase']
        if tsname not in data_json['testsuites']:
            data_json['testsuites'][tsname] = {
                'module': data['module'],
                'file': data['file'],
                'testcases': {}
            }
        tsdoc = []
        if data['suitedoc']:
            tsdoc = (re.sub(r"[\t\n ]+", " ", data['suitedoc'])).strip()
        data_json['testsuites'][tsname]['docstring'] = tsdoc
        tcshort = {}
        tcdoc = []
        if data['testdoc']:
            tcdoc = (re.sub(r"[\t\n ]+", " ", data['testdoc'])).strip()
        tcshort['docstring'] = tcdoc
        if data['tags']:
            tcshort['tags'] = data['tags']
        tcshort['results'] = {
            'status': data['status'],
            'status_data': str(data['status_data']),
            'duration': str(data['duration']),
            'start_time': str(data['start_time']),
            'end_time': str(data['end_time']),
            'measurements': []
        }
        tcshort['requirements'] = {}
        if 'measurements' in data:
            tcshort['results']['measurements'] = data['measurements']
        data_json['testsuites'][tsname]['testcases'][tcname] = tcshort
        if 'additional_data' in data:
            data_json['additional_data'] = data['additional_data']
        data_json['test_summary']['test_end_time'] = str(data['end_time'])
        data_json['test_summary']['result_summary']['run'] += 1
        d_ts = data_json['test_summary']
        if data['status'] == 'PASS':
            d_ts['result_summary']['succeeded'] += 1
        elif data['status'] == 'SKIP':
            d_ts['result_summary']['skipped'] += 1
        elif data['status'] == 'TIMEDOUT':
            d_ts['result_summary']['timedout'] += 1
            d_ts['tests_with_failures'].append(data['testcase'])
            if data['suite'] not in d_ts['test_suites_with_failures']:
                d_ts['test_suites_with_failures'].append(data['suite'])
        elif data['status'] == 'ERROR':
            d_ts['result_summary']['errors'] += 1
            d_ts['tests_with_failures'].append(data['testcase'])
            if data['suite'] not in d_ts['test_suites_with_failures']:
                d_ts['test_suites_with_failures'].append(data['suite'])
        elif data['status'] == 'FAIL':
            d_ts['result_summary']['failed'] += 1
            d_ts['tests_with_failures'].append(data['testcase'])
            if data['suite'] not in d_ts['test_suites_with_failures']:
                d_ts['test_suites_with_failures'].append(data['suite'])
        return data_json

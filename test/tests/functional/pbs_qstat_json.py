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
import json


class Qstat_json(PBSTestSuite):
    """
    Test qstat output can be viewed in json format
    """

    def parse_json(self, dict, qstat_attr):
        """
        Common function for parsing the all values in json output
        """
        for key, val in dict.items():
            qstat_attr.append(str(key))
            if type(val) == type(dict):
                for key, val in val.items():
                    qstat_attr.append(str(key))
                    if type(val) == type(dict):
                        self.parse_json(val, qstat_attr)
        return qstat_attr

    def test_qstat_json_valid(self):
        """
        Test json output of qstat -f is in valid format when querired as a super user and all attributes displayed in qstat are present in output
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        f = open('/tmp/qstat_script', 'w')
        f.write(self.server.pbs_conf['PBS_EXEC'] +
                "/bin/qstat -f -F json > /tmp/qstat_out")
        f.close()
        os.chmod("/tmp/qstat_script", 0755)
        run_script = "sh /tmp/qstat_script"
        ret = self.du.run_cmd(self.server.hostname, cmd=run_script, sudo=True)
        print ret['out']
        f = open('/tmp/qstat_out', 'r')
        qstat_out = f.read()
        print qstat_out
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        self.assertTrue(True)
        attrs_qstatf = ['timestamp', 'pbs_version', 'pbs_server', 'Jobs', jid, 'Job_Name', 'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime', 'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files', 'Mail_Points', 'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable', 'Resource_List', 'ncpus', 'nodect', 'place',
                        'select', 'schedselect', 'substate', 'Variable_List', 'PBS_O_HOME', 'PBS_O_LANG', 'PBS_O_LOGNAME', 'PBS_O_PATH', 'PBS_O_MAIL', 'PBS_O_SHELL', 'PBS_O_WORKDIR', 'PBS_O_SYSTEM', 'PBS_O_QUEUE', 'PBS_O_HOST', 'euser', 'egroup', 'queue_rank', 'queue_type', 'etime', 'Submit_arguments', 'executable', 'argument_list', 'project']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if type(val) == type(json_object):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        for attr in attrs_qstatf:
            if attr not in qstat_attr:
                print attr + "is missing"
                self.assertTrue(False)
        self.assertTrue(True)

    def test_qstat_json_valid_user(self):
        """
        Test json output of qstat -f is in valid format when queried as normal user and all attributes displayed in qstat are present in output
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        f = open('/tmp/qstat_script', 'w')
        f.write(self.server.pbs_conf['PBS_EXEC'] +
                "/bin/qstat -f -F json > /tmp/qstat_out")
        f.close()
        os.chmod("/tmp/qstat_script", 0755)
        run_script = "sh /tmp/qstat_script"
        ret = self.du.run_cmd(self.server.hostname,
                              cmd=run_script, runas=TEST_USER)
        print ret['out']
        f = open('/tmp/qstat_out', 'r')
        qstat_out = f.read()
        print qstat_out
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        self.assertTrue(True)
        attrs_qstatf = ['timestamp', 'pbs_version', 'pbs_server', 'Jobs', jid, 'Job_Name', 'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime', 'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files', 'Mail_Points', 'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable', 'Resource_List',
                        'ncpus', 'nodect', 'place', 'select', 'substate', 'Variable_List', 'PBS_O_HOME', 'PBS_O_LANG', 'PBS_O_LOGNAME', 'PBS_O_PATH', 'PBS_O_MAIL', 'PBS_O_SHELL', 'PBS_O_WORKDIR', 'PBS_O_SYSTEM', 'PBS_O_QUEUE', 'PBS_O_HOST', 'etime', 'Submit_arguments', 'executable', 'argument_list', 'project']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if type(val) == type(json_object):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        for attr in attrs_qstatf:
            if attr not in qstat_attr:
                print attr + "is missing"
                self.assertTrue(False)
        self.assertTrue(True)

    def test_qstat_json_valid_ja(self):
        """
        Test json output of qstat -f of Job arrays is in valid format and all attributes displayed in qstat are present in output
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        j.set_attributes({ATTR_J: '1-3:1'})
        jid = self.server.submit(j)
        f = open('/tmp/qstat_script', 'w')
        f.write(self.server.pbs_conf['PBS_EXEC'] +
                "/bin/qstat -f -F json > /tmp/qstat_out")
        f.close()
        os.chmod("/tmp/qstat_script", 0755)
        run_script = "sh /tmp/qstat_script"
        ret = self.du.run_cmd(self.server.hostname, cmd=run_script, sudo=True)
        print ret['out']
        f = open('/tmp/qstat_out', 'r')
        qstat_out = f.read()
        print qstat_out
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        self.assertTrue(True)
        attrs_qstatf = ['timestamp', 'pbs_version', 'pbs_server', 'Jobs', jid, 'Job_Name', 'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime', 'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files', 'Mail_Points', 'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable', 'Resource_List', 'ncpus', 'nodect', 'place', 'select', 'schedselect', 'substate',
                        'Variable_List', 'PBS_O_HOME', 'PBS_O_LANG', 'PBS_O_LOGNAME', 'PBS_O_PATH', 'PBS_O_MAIL', 'PBS_O_SHELL', 'PBS_O_WORKDIR', 'PBS_O_SYSTEM', 'PBS_O_QUEUE', 'PBS_O_HOST', 'euser', 'egroup', 'queue_rank', 'queue_type', 'etime', 'Submit_arguments', 'executable', 'argument_list', 'array', 'array_state_count', 'array_indices_submitted', 'array_indices_remaining', 'project']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if type(val) == type(json_object):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        print qstat_attr
        for attr in attrs_qstatf:
            if attr not in qstat_attr:
                print attr + "is missing"
                self.assertTrue(False)
        self.assertTrue(True)

    def test_qstat_bf_json_valid(self):
        """
        Test json output of qstat -Bf is in valid format and all attributes displayed in qstat are present in output
        """
        f = open('/tmp/qstat_script', 'w')
        f.write(self.server.pbs_conf['PBS_EXEC'] +
                "/bin/qstat -Bf -F json > /tmp/qstat_out")
        f.close()
        os.chmod("/tmp/qstat_script", 0755)
        run_script = "sh /tmp/qstat_script"
        ret = self.du.run_cmd(self.server.hostname, cmd=run_script, sudo=True)
        print ret['out']
        f = open('/tmp/qstat_out', 'r')
        qstat_out = f.read()
        print qstat_out
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        self.assertTrue(True)
        attrs_qstatbf = ['timestamp', 'pbs_server', 'Server', 'eligible_time_enable', 'managers', 'license_count', 'scheduling', 'total_jobs', 'server_host', 'pbs_license_info', 'default_chunk', 'ncpus', 'FLicenses', 'node_fail_requeue', 'resv_enable', 'flatuid', 'query_other_jobs',
                         'state_count', 'default_queue', 'server_state', 'max_concurrent_provision', 'resources_default', 'ncpus', 'scheduler_iteration', 'pbs_license_linger_time', 'resources_assigned', 'ncpus', 'nodect', 'mail_from', 'log_events', 'pbs_version', 'acl_roots', 'max_array_size', 'pbs_version']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if type(val) == type(json_object):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        print qstat_attr
        for attr in attrs_qstatbf:
            if attr not in qstat_attr:
                print attr + "is missing"
                self.assertTrue(False)
        self.assertTrue(True)

    def test_qstat_qf_json_valid(self):
        """
        Test json output of qstat -Qf is in valid format and all attributes displayed in qstat are present in output
        """
        f = open('/tmp/qstat_script', 'w')
        f.write(self.server.pbs_conf['PBS_EXEC'] +
                "/bin/qstat -Qf -F json > /tmp/qstat_out")
        f.close()
        os.chmod("/tmp/qstat_script", 0755)
        run_script = "sh /tmp/qstat_script"
        ret = self.du.run_cmd(self.server.hostname, cmd=run_script, sudo=True)
        print ret['out']
        f = open('/tmp/qstat_out', 'r')
        qstat_out = f.read()
        print qstat_out
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        self.assertTrue(True)
        attrs_qstatqf = ['Queue', 'workq', 'started', 'enabled', 'queue_type',
                         'state_count', 'total_jobs', 'timestamp', 'pbs_server', 'pbs_version']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if type(val) == type(json_object):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        print qstat_attr
        for attr in attrs_qstatqf:
            if attr not in qstat_attr:
                print attr + "is missing"
                self.assertTrue(False)
        self.assertTrue(True)

    def tearDown(self):
        os.remove("/tmp/qstat_out")
        os.remove("/tmp/qstat_script")
        PBSTestSuite.tearDown(self)

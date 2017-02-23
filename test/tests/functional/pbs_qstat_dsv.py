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


class Qstat_dsv(PBSTestSuite):
    """
    Test qstat output can be viewed in dsv format
    """

    def parse_dsv(self, delimiter, attrs_qstatf, jid, qstat_type):
        """
        Common function to parse qstat output using delimiter
        """
        if delimiter == None:
            delim = " "
        else:
            delim = "-D" + str(delimiter)
        if qstat_type == "job":
            qstat_cmd = os.path.join(self.server.pbs_conf[
                                     'PBS_EXEC'], 'bin', 'qstat') + ' -f -F dsv ' + delim + " " + str(jid)
        elif qstat_type == "server":
            qstat_cmd = os.path.join(self.server.pbs_conf[
                                     'PBS_EXEC'], 'bin', 'qstat') + ' -Bf -F dsv ' + delim
        elif qstat_type == "queue":
            qstat_cmd = os.path.join(self.server.pbs_conf[
                                     'PBS_EXEC'], 'bin', 'qstat') + ' -Qf -F dsv ' + delim
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd, sudo=True)
        qstat_attrs = []
        for line in ret['out']:
            if delimiter == None:
                attr_vals = line.split("|")
            else:
                attr_vals = line.split(str(delimiter))
        for item in attr_vals:
            qstat_attr = item.split("=")
            qstat_attrs.append(qstat_attr[0])
        print qstat_attrs
        rv = True
        for attr in attrs_qstatf:
            if attr not in qstat_attrs:
                print attr + "is missing"
                rv = False
                self.assertTrue(rv)
        self.assertTrue(rv)

    def test_qstat_dsv(self):
        """
        test qstat outputs job info in dsv format with default delimiter pipe
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        print jid
        qstat_cmd = os.path.join(self.server.pbs_conf[
                                 'PBS_EXEC'], 'bin', 'qstat') + ' -f -F dsv ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd, sudo=True)
        attrs_qstatf = ['Job_Name', 'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime', 'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files', 'Mail_Points', 'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable', 'Resource_List.ncpus',
                        'Resource_List.nodect', 'Resource_List.place', 'Resource_List.select', 'schedselect', 'substate', 'Variable_List', 'euser', 'egroup', 'queue_rank', 'queue_type', 'etime', 'Submit_arguments', 'executable', 'argument_list', 'project']
        self.parse_dsv(None, attrs_qstatf, jid, "job")

    def test_qstat_bf_dsv(self):
        """
        test qstat outputs server info in dsv format with default delimiter pipe
        """
        attrs_qstatbf = ['eligible_time_enable', 'managers', 'license_count', 'scheduling', 'total_jobs', 'server_host', 'pbs_license_info', 'default_chunk.ncpus', 'FLicenses', 'node_fail_requeue', 'resv_enable', 'flatuid', 'query_other_jobs', 'state_count', 'default_queue',
                         'server_state', 'max_concurrent_provision', 'resources_default.ncpus', 'scheduler_iteration', 'pbs_license_linger_time', 'resources_assigned.ncpus', 'resources_assigned.nodect', 'mail_from', 'log_events', 'pbs_version', 'acl_roots', 'max_array_size', 'pbs_version']
        self.parse_dsv(None, attrs_qstatbf, None, "server")

    def test_qstat_qf_dsv(self):
        """
        test qstat outputs queue info in dsv format with default delimiter pipe
        """
        attrs_qstatqf = ['started', 'enabled',
                         'queue_type', 'state_count', 'total_jobs']
        self.parse_dsv(None, attrs_qstatqf, None, "queue")

    def test_qstat_dsv_semicolon(self):
        """
        test qstat outputs job info in dsv format with semicolon as delimiter 
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        print jid
        attrs_qstatf = ['Job_Name', 'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime', 'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files', 'Mail_Points', 'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable', 'Resource_List.ncpus',
                        'Resource_List.nodect', 'Resource_List.place', 'Resource_List.select', 'schedselect', 'substate', 'Variable_List', 'euser', 'egroup', 'queue_rank', 'queue_type', 'etime', 'Submit_arguments', 'executable', 'argument_list', 'project']
        self.parse_dsv(";", attrs_qstatf, jid, "job")

    def test_qstat_bf_dsv_semicolon(self):
        """
        test qstat outputs server info in dsv format with semicolon as delimiter
        """
        attrs_qstatbf = ['eligible_time_enable', 'managers', 'license_count', 'scheduling', 'total_jobs', 'server_host', 'pbs_license_info', 'default_chunk.ncpus', 'FLicenses', 'node_fail_requeue', 'resv_enable', 'flatuid', 'query_other_jobs', 'state_count', 'default_queue',
                         'server_state', 'max_concurrent_provision', 'resources_default.ncpus', 'scheduler_iteration', 'pbs_license_linger_time', 'resources_assigned.ncpus', 'resources_assigned.nodect', 'mail_from', 'log_events', 'pbs_version', 'acl_roots', 'max_array_size', 'pbs_version']
        self.parse_dsv(";", attrs_qstatbf, None, "server")

    def test_qstat_qf_dsv_semicolon(self):
        """
        test qstat outputs queue info in dsv format with semicolon as delimiter
        """
        attrs_qstatqf = ['started', 'enabled',
                         'queue_type', 'state_count', 'total_jobs']
        self.parse_dsv(";", attrs_qstatqf, None, "queue")

    def test_qstat_dsv_comma_ja(self):
        """
        test qstat outputs job array info in dsv format with comma as delimiter
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        j.set_attributes({ATTR_J: '1-3:1'})
        jid = self.server.submit(j)
        print jid
        attrs_qstatf = ['Job_Name', 'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime', 'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files', 'Mail_Points', 'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable', 'Resource_List.ncpus', 'Resource_List.nodect', 'Resource_List.place',
                        'Resource_List.select', 'schedselect', 'substate', 'Variable_List', 'euser', 'egroup', 'queue_rank', 'queue_type', 'etime', 'Submit_arguments', 'executable', 'array', 'array_state_count', 'array_indices_submitted', 'array_indices_remaining', 'argument_list', 'project']
        self.parse_dsv(",", attrs_qstatf, jid, "job")

    def test_qstat_bf_dsv_comma(self):
        """
        test qstat outputs server info in dsv format with comma as delimiter
        """
        attrs_qstatbf = ['eligible_time_enable', 'managers', 'license_count', 'scheduling', 'total_jobs', 'server_host', 'pbs_license_info', 'default_chunk.ncpus', 'FLicenses', 'node_fail_requeue', 'resv_enable', 'flatuid', 'query_other_jobs', 'state_count', 'default_queue',
                         'server_state', 'max_concurrent_provision', 'resources_default.ncpus', 'scheduler_iteration', 'pbs_license_linger_time', 'resources_assigned.ncpus', 'resources_assigned.nodect', 'mail_from', 'log_events', 'pbs_version', 'acl_roots', 'max_array_size', 'pbs_version']
        self.parse_dsv(",", attrs_qstatbf, None, "server")

    def test_qstat_qf_dsv_comma(self):
        """
        test qstat outputs queue info in dsv format with comma as delimiter
        """
        attrs_qstatqf = ['started', 'enabled',
                         'queue_type', 'state_count', 'total_jobs']
        self.parse_dsv(",", attrs_qstatqf, None, "queue")

    def test_qstat_dsv_string(self):
        """
        test qstat outputs job info in dsv format with string as delimiter
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        print jid
        attrs_qstatf = ['Job_Name', 'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime', 'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files', 'Mail_Points', 'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable', 'Resource_List.ncpus',
                        'Resource_List.nodect', 'Resource_List.place', 'Resource_List.select', 'schedselect', 'substate', 'Variable_List', 'euser', 'egroup', 'queue_rank', 'queue_type', 'etime', 'Submit_arguments', 'executable', 'argument_list', 'project']
        self.parse_dsv("QWERTY", attrs_qstatf, jid, "job")

    def test_qstat_bf_dsv_string(self):
        """
        test qstat outputs server info in dsv format with string as delimiter
        """
        attrs_qstatbf = ['eligible_time_enable', 'managers', 'license_count', 'scheduling', 'total_jobs', 'server_host', 'pbs_license_info', 'default_chunk.ncpus', 'FLicenses', 'node_fail_requeue', 'resv_enable', 'flatuid', 'query_other_jobs', 'state_count', 'default_queue',
                         'server_state', 'max_concurrent_provision', 'resources_default.ncpus', 'scheduler_iteration', 'pbs_license_linger_time', 'resources_assigned.ncpus', 'resources_assigned.nodect', 'mail_from', 'log_events', 'pbs_version', 'acl_roots', 'max_array_size', 'pbs_version']
        self.parse_dsv("QWERTY", attrs_qstatbf, None, "server")

    def test_qstat_qf_dsv_string(self):
        """
        test qstat outputs queue info in dsv format with string as delimiter
        """
        attrs_qstatqf = ['started', 'enabled',
                         'queue_type', 'state_count', 'total_jobs']
        self.parse_dsv("QWERTY", attrs_qstatqf, None, "queue")

# coding: utf - 8

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

from ptl.utils.pbs_testsuite import *
import json


class TestQstat(PBSTestSuite):
    """
    This test suite validates output of qstat for
    various options
    """

    def parse_json(self, dictitems, qstat_attr):
        """
        Common function for parsing the all values in json output
        """
        for key, val in dictitems.items():
            qstat_attr.append(str(key))
            if isinstance(val, dict):
                for key, val in val.items():
                    qstat_attr.append(str(key))
                    if isinstance(val, dict):
                        self.parse_json(val, qstat_attr)
        return qstat_attr

    def validate_el(self, attr_dict, user):
        """
        Check if the value of server attributes reported by
        qstat -Bf matches the expected values.
        """
        qstat_o = {}
        qstat_o['server_state'] = 'Active'
        qstat_o['server_host'] = self.server.hostname
        qstat_o['scheduling'] = 'True'
        qstat_o['total_jobs'] = '0'
        qstat_o['state_count'] = ['Transit', 'Queued',
                                  'Held', 'Waiting', 'Running',
                                  'Exiting', 'Begun']
        qstat_o['default_queue'] = 'workq'
        qstat_o['log_events'] = '511'
        qstat_o['mail_from'] = 'adm'
        qstat_o['query_other_jobs'] = 'True'
        qstat_o['resources_default.ncpus'] = '1'
        qstat_o['default_chunk.ncpus'] = '1'
        qstat_o['resv_enable'] = 'True'
        qstat_o['node_fail_requeue'] = '310'
        qstat_o['max_array_size'] = '10000'
        qstat_o['pbs_license_linger_time'] = '3600'
        qstat_o['pbs_version'] = self.server.pbs_version
        qstat_o['eligible_time_enable'] = 'False'
        qstat_o['max_concurrent_provision'] = '5'
        qstat_o['FLicenses'] = None
        qstat_o['license_count'] = None
        qstat_o['managers'] = None
        qstat_o['flatuid'] = None
        qstat_o['id'] = self.server.shortname

        # If test case is run as root, PTL sets acl_roots
        if os.getuid() == 0:
            qstat_o['acl_roots'] = None

        if user == ROOT_USER:
            qstat_o['power_provisioning'] = 'False'

        platform = self.du.get_platform()
        if platform == 'cray' or platform == 'craysim':
            qstat_o['restrict_res_to_release_on_suspend'] = 'ncpus'

        for each in attr_dict:
            self.assertIn(each, qstat_o, "Unexpected attribute \"%s\""
                          " encountered in output of qstat -Bf" % each)
            if qstat_o[each] is not None:
                if "state_count" in each:
                    out1 = []
                    out = attr_dict[each].split()
                    for k in out:
                        out1.append(k.split(':')[0])
                    self.assertListEqual(qstat_o[each], out1,
                                         "Value of server attribute \"%s\""
                                         " does not match expected"
                                         " value" % each)
                else:
                    self.assertEqual(qstat_o[each], attr_dict[each],
                                     "Value of server attribute \"%s\""
                                     " does not match expected value" % each)
                self.logger.info("Server attribute \"%s\""
                                 " is validated successfully" % each)
        value = [k for k in qstat_o.keys() if k not in attr_dict.keys()]
        self.assertEqual(len(value), 0, "Output of qstat -Bf is missing"
                                        " some expected attributes - %s"
                                        % value)
        self.logger.info(
            "Server attributes in output of qstat -Bf validated succesfully")

    @tags('smoke')
    def test_qstat_json_valid(self):
        """
        Test json output of qstat -f is in valid format when querired as a
        super user and all attributes displayed in qstat are present in output
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        qstat_cmd_json = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat') + ' -f -F json ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        attrs_qstatf = [
            'timestamp', 'pbs_version', 'pbs_server', 'Jobs', jid, 'Job_Name',
            'Job_Owner', 'job_state', 'queue', 'server', 'Checkpoint', 'ctime',
            'Error_Path', 'Hold_Types', 'Join_Path', 'Keep_Files',
            'mtime', 'Output_Path', 'Priority', 'qtime', 'Rerunable',
            'Resource_List', 'ncpus', 'nodect', 'place', 'select', 'project',
            'executable', 'Variable_List', 'PBS_O_HOME',
            'PBS_O_LOGNAME', 'PBS_O_PATH', 'PBS_O_MAIL', 'PBS_O_SHELL',
            'PBS_O_WORKDIR', 'PBS_O_SYSTEM', 'PBS_O_QUEUE', 'PBS_O_HOST',
            'egroup', 'queue_rank', 'queue_type', 'etime', 'Submit_arguments',
            'Mail_Points', 'schedselect', 'substate', 'argument_list', 'euser']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if isinstance(val, dict):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        for attr in attrs_qstatf:
            if attr not in qstat_attr:
                self.assertFalse(attr + " is missing")

    def test_qstat_json_valid_multiple_jobs(self):
        """
        Test json output of qstat -f is in valid format when multiple jobs are
        queried and make sure that all attributes are displayed in qstat are
        present in the output
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)
        qstat_cmd_json = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                      'qstat') + \
            ' -f -F json ' + str(jid1) + ' ' + str(jid2)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json.loads(qstat_out)
        except ValueError:
            self.assertTrue(False)

    def test_qstat_json_valid_user(self):
        """
        Test json output of qstat -f is in valid format when queried as
        normal user
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)
        qstat_cmd_json = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat') + ' -f -F json ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname,
                              cmd=qstat_cmd_json, runas=TEST_USER)
        qstat_out = "\n".join(ret['out'])
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)

    def test_qstat_json_valid_ja(self):
        """
        Test json output of qstat -f of Job arrays is in valid format
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        j.set_attributes({ATTR_J: '1-3'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "B"}, id=jid)
        qstat_cmd_json = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat') + ' -f -F json ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)

    @tags('smoke')
    def test_qstat_bf_json_valid(self):
        """
        Test json output of qstat -Bf is in valid format and all
        attributes displayed in qstat are present in output
        """
        qstat_cmd_json = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat') + ' -Bf -F json'
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        attrs_qstatbf = [
            'timestamp', 'pbs_server', 'Server', 'eligible_time_enable',
            'license_count', 'scheduling', 'total_jobs', 'server_host',
            'default_chunk', 'ncpus', 'FLicenses',
            'node_fail_requeue', 'resv_enable', 'flatuid', 'query_other_jobs',
            'state_count', 'default_queue', 'server_state', 'managers',
            'max_concurrent_provision', 'resources_default', 'ncpus',
            'pbs_license_linger_time', 'mail_from', 'log_events',
            'pbs_version', 'acl_roots', 'max_array_size', 'pbs_version']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if isinstance(val, dict):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        for attr in attrs_qstatbf:
            if attr not in qstat_attr:
                self.assertFalse(attr + " is missing")

    @tags('smoke')
    def test_qstat_qf_json_valid(self):
        """
        Test json output of qstat -Qf is in valid format and all
        attributes displayed in qstat are present in output
        """
        qstat_cmd_json = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat') + ' -Qf -F json'
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json_object = json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)
        attrs_qstatqf = ['Queue', 'workq', 'started', 'enabled', 'queue_type',
                         'state_count', 'total_jobs', 'timestamp',
                         'pbs_server', 'pbs_version']
        qstat_attr = []
        for key, val in json_object.iteritems():
            qstat_attr.append(str(key))
            if isinstance(val, dict):
                qstat_attrs = self.parse_json(val, qstat_attr)
                qstat_attr.append(qstat_attrs)
        for attr in attrs_qstatqf:
            if attr not in qstat_attr:
                self.assertFalse(attr + " is missing")

    def test_qstat_qf_json_valid_multiple_queues(self):
        """
        Test json output of qstat -Qf is in valid format when
        we query multiple queues
        """
        q_attr = {'queue_type': 'execution', 'enabled': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, q_attr, id='workq1')
        self.server.manager(MGR_CMD_CREATE, QUEUE, q_attr, id='workq2')
        qstat_cmd_json = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat') + ' -Qf -F json workq1 workq2'
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json.loads(qstat_out)
        except ValueError, e:
            self.assertTrue(False)

    @tags('smoke')
    def test_qstat_Bf_as_user(self):
        """
        Validate output of qstat -Bf when executed as non-root user
        """
        ret = self.server.status(runas=TEST_USER)
        attr_dict = ret[0]
        self.validate_el(attr_dict, TEST_USER)

    @tags('smoke')
    def test_qstat_Bf_as_root(self):
        """
        Validate output of qstat -Bf when executed as root user
        """
        ret = self.server.status(runas=ROOT_USER)
        attr_dict = ret[0]
        self.validate_el(attr_dict, ROOT_USER)

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

from tests.functional import *
import json


@tags('commands')
class TestQstatFormats(TestFunctional):
    """
    This test suite validates output of qstat for
    various formats
    """

    def parse_dsv(self, jid, qstat_type, delimiter=None):
        """
        Common function to parse qstat dsv output using delimiter
        """
        if delimiter:
            delim = "-D" + str(delimiter)
        else:
            delim = " "
        if qstat_type == "job":
            cmd = ' -f -F dsv ' + delim + " " + str(jid)
            qstat_cmd_dsv = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                         'bin', 'qstat') + cmd
            qstat_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                     'bin', 'qstat') + ' -f ' + str(jid)
        elif qstat_type == "server":
            qstat_cmd_dsv = os.path.join(self.server.pbs_conf[
                'PBS_EXEC'], 'bin', 'qstat') + ' -Bf -F dsv ' + delim
            qstat_cmd = os.path.join(self.server.pbs_conf[
                'PBS_EXEC'], 'bin', 'qstat') + ' -Bf '
        elif qstat_type == "queue":
            qstat_cmd_dsv = os.path.join(self.server.pbs_conf[
                'PBS_EXEC'], 'bin', 'qstat') + ' -Qf -F dsv ' + delim
            qstat_cmd = os.path.join(self.server.pbs_conf[
                'PBS_EXEC'], 'bin', 'qstat') + ' -Qf '
        rv = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd)
        attrs_qstatf = []
        for line in rv['out']:
            attr = line.split("=")
            if not re.match(r'[\t]', attr[0]):
                attrs_qstatf.append(attr[0].strip())
        attrs_qstatf.pop()
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_dsv)
        qstat_attrs = []
        for line in ret['out']:
            if delimiter:
                attr_vals = line.split(str(delimiter))
            else:
                attr_vals = line.split("|")
        for item in attr_vals:
            qstat_attr = item.split("=")
            qstat_attrs.append(qstat_attr[0])
        for attr in attrs_qstatf:
            if attr not in qstat_attrs:
                self.assertFalse(attr + " is missing")

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

    def test_qstat_dsv(self):
        """
        test qstat outputs job info in dsv format with default delimiter pipe
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)
        self.parse_dsv(jid, "job")

    def test_qstat_bf_dsv(self):
        """
        test qstat outputs server info in dsv format with default
        delimiter pipe
        """
        self.parse_dsv(None, "server")

    def test_qstat_qf_dsv(self):
        """
        test qstat outputs queue info in dsv format with default delimiter pipe
        """
        self.parse_dsv(None, "queue")

    def test_qstat_dsv_semicolon(self):
        """
        test qstat outputs job info in dsv format with semicolon as delimiter
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)
        self.parse_dsv(jid, "job", ";")

    def test_qstat_bf_dsv_semicolon(self):
        """
        test qstat outputs server info in dsv format with semicolon as
        delimiter
        """
        self.parse_dsv(None, "server", ";")

    def test_qstat_qf_dsv_semicolon(self):
        """
        test qstat outputs queue info in dsv format with semicolon as delimiter
        """
        self.parse_dsv(None, "queue", ";")

    def test_qstat_dsv_comma_ja(self):
        """
        test qstat outputs job array info in dsv format with comma as delimiter
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        j.set_attributes({ATTR_J: '1-3'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "B"}, id=jid)
        self.parse_dsv(jid, "job", ",")

    def test_qstat_bf_dsv_comma(self):
        """
        test qstat outputs server info in dsv format with comma as delimiter
        """
        self.parse_dsv(None, "server", ",")

    def test_qstat_qf_dsv_comma(self):
        """
        test qstat outputs queue info in dsv format with comma as delimiter
        """
        self.parse_dsv(None, "queue", ",")

    def test_qstat_dsv_string(self):
        """
        test qstat outputs job info in dsv format with string as delimiter
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)
        self.parse_dsv(jid, "job", "QWERTY")

    def test_qstat_bf_dsv_string(self):
        """
        test qstat outputs server info in dsv format with string as delimiter
        """
        self.parse_dsv(None, "server", "QWERTY")

    def test_qstat_qf_dsv_string(self):
        """
        test qstat outputs queue info in dsv format with string as delimiter
        """
        self.parse_dsv(None, "queue", "QWERTY")

    def test_oneline_dsv(self):
        """
        submit a single job and check the no of attributes parsed from dsv
        is equal to the one parsed from one line output.
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        time.sleep(1)
        qstat_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat')
        [qstat_dsv_script, qstat_dsv_out, qstat_oneline_script,
         qstat_oneline_out] = [DshUtils().create_temp_file() for _ in range(4)]
        f = open(qstat_dsv_script, 'w')
        f.write(qstat_cmd + ' -f -F dsv ' + str(jid) + ' > ' + qstat_dsv_out)
        f.close()
        run_script = "sh " + qstat_dsv_script
        dsv_ret = self.du.run_cmd(
            self.server.hostname,
            cmd=run_script)
        f = open(qstat_dsv_out, 'r')
        dsv_out = f.read()
        f.close()
        dsv_attr_count = len(dsv_out.replace("\|", "").split("|"))
        f = open(qstat_oneline_script, 'w')
        f.write(qstat_cmd + ' -f -w ' + str(jid) + ' > ' + qstat_oneline_out)
        f.close()
        run_script = 'sh ' + qstat_oneline_script
        oneline_ret = self.du.run_cmd(
            self.server.hostname, cmd=run_script)
        oneline_attr_count = sum(1 for line in open(
            qstat_oneline_out) if not line.isspace())
        map(os.remove, [qstat_dsv_script, qstat_dsv_out,
                        qstat_oneline_script, qstat_oneline_out])
        self.assertEqual(dsv_attr_count, oneline_attr_count)

    def test_json(self):
        """
        Check whether the qstat json output can be parsed using
        python json module
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        [qstat_json_script, qstat_json_out] = [DshUtils().create_temp_file()
                                               for _ in range(2)]
        qstat_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat')
        f = open(qstat_json_script, 'w')
        f.write(qstat_cmd + ' -f -F json ' + str(jid) + ' > ' + qstat_json_out)
        f.close()
        self.du.chmod(path=qstat_json_script, mode=0o755)
        run_script = 'sh ' + qstat_json_script
        json_ret = self.du.run_cmd(
            self.server.hostname, cmd=run_script)
        data = open(qstat_json_out, 'r').read()
        map(os.remove, [qstat_json_script, qstat_json_out])
        try:
            json_data = json.loads(data)
        except:
            self.assertTrue(False)

    def test_qstat_tag(self):
        """
        Test <jsdl-hpcpa:Executable> tag is dispalyed with "Executable"
        while doing qstat -f
        """
        ret = True
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        qstat_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                 'qstat') + ' -f ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd, sudo=True)
        if -1 != str(ret).find('Executable'):
            if -1 == str(ret).find('<jsdl-hpcpa:Executable>'):
                ret = False
        self.assertTrue(ret)

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

    def test_qstat_json_valid_job_special_env(self):
        """
        Test json output of qstat -f is in valid format
        with special chars in env
        """
        os.environ["DOUBLEQUOTES"] = 'hi"ha'
        os.environ["REVERSESOLIDUS"] = 'hi\ha'

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'default_qsub_arguments': '-V'})

        j = Job(self.du.get_current_user())
        j.preserve_env = True
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        qstat_cmd_json = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                      'qstat') + \
            ' -f -F json ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json.loads(qstat_out)
        except ValueError:
            self.assertTrue(False)

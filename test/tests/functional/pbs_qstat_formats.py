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
        Common function for parsing all values in json output
        """
        for key, val in dictitems.items():
            qstat_attr.append(str(key))
            if isinstance(val, dict):
                for key, val in val.items():
                    qstat_attr.append(str(key))
                    if isinstance(val, dict):
                        self.parse_json(val, qstat_attr)
        return qstat_attr

    def get_qstat_attribs(self, obj_type):
        """
        Common function to get the qstat attributes in default format.
        Attributes returned by this function are used to validate the
        '-F json' format output.
        The dictionary of attributes as returned by status() can not
        be used directly because some attributes are printed differently
        in '-F json' format.  Hence this function returns a modified
        attributes list.
        obj_type: Can be SERVER, QUEUE or JOB for qstat -Bf, qstat -Qf
              and qstat -f respectively
        """
        attrs = self.server.status(obj_type)
        qstat_attrs = []

        for key, val in attrs[0].items():
            # qstat -F json output does not
            # print the 'id' attribute. Its value
            # is printed instead.
            if key is 'id':
                qstat_attrs.append(str(val))
            else:
                # Extract keys coming after '.' in 'qstat -f' output so they
                # can be matched with 'qstat -f -F json' format.
                # This is because some attributes, like below, are represented
                # differently in 'qstat -f' output and 'qstat -f -F json'
                # outputs
                #
                # Example:
                # qstat -f output:
                #   default_chunk.ncpus = 1
                #   default_chunk.mem = 1gb
                #   Resource_List.ncpus = 1
                #   Resource_List.nodect = 1
                #
                # qstat -f -F json output:
                #   "default_chunk":{
                #      "ncpus":1
                #      "mem":1gb
                #   }
                #    "Resource_List":{
                #       "ncpus":1,
                #      "nodect":1,
                #   }

                k = key.split('.')
                if k[0] not in qstat_attrs:
                    qstat_attrs.append(str(k[0]))
                if len(k) == 2:
                    qstat_attrs.append(str(k[1]))

            # Extract individual variables under 'Variable_List' from
            # 'qstat -f' output so they can be matched with 'qstat -f -F json'
            # format.
            # Example:
            #
            # qstat -f output:
            #    Variable_List = PBS_O_LANG=en_US.UTF-8,
            #        PBS_O_PATH=/usr/lib64/qt-3.3/bin
            #        PBS_O_SHELL=/bin/bash,
            #        PBS_O_WORKDIR=/home/pbsuser,
            #        PBS_O_SYSTEM=Linux,PBS_O_QUEUE=workq,
            #
            # qstat -f -F json output:
            #    "Variable_List":{
            #        "PBS_O_LANG":"en_US.UTF-8",
            #        "PBS_O_PATH":"/usr/lib64/qt-3.3/bin:/usr/local/bin
            #        "PBS_O_SHELL":"/bin/bash",
            #        "PBS_O_WORKDIR":"/home/pbsuser,
            #        "PBS_O_SYSTEM":"Linux",
            #        "PBS_O_QUEUE":"workq",
            #    },

            if key == ATTR_v:
                for v in val.split(','):
                    qstat_attrs.append(str(v).split('=')[0])
        return qstat_attrs

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
        dsv_attr_count = len(dsv_out.replace(r"\|", "").split("|"))
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
        except BaseException:
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
        j.set_sleep_time(40)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

        qstat_cmd_json = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat') + ' -f -F json ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            json_object = json.loads(qstat_out)
        except ValueError as e:
            self.assertTrue(False)

        json_only_attrs = ['Jobs', 'timestamp', 'pbs_version', 'pbs_server']
        attrs_qstatf = self.get_qstat_attribs(JOB)
        qstat_json_attr = []

        for key, val in json_object.items():
            qstat_json_attr.append(str(key))
            if isinstance(val, dict):
                self.parse_json(val, qstat_json_attr)

        for attr in attrs_qstatf:
            if attr not in qstat_json_attr:
                self.assertFalse(attr + " is missing")

        for attr in json_only_attrs:
            if attr not in qstat_json_attr:
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

    def test_qstat_json_valid_multiple_jobs_p(self):
        """
        Test json output of qstat -f is in valid format when multiple jobs are
        queried and make sure that attributes are displayed with `p` option.
        When -p is passed, then only the Resource_List is requested. An
        attribute with type resource list has to be the last attribute
        in order to hit the bug.
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER)
        j.set_sleep_time(100)
        jid = self.server.submit(j)
        jid2 = self.server.submit(j)
        jid3 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)
        self.server.expect(JOB, {'job_state': "R"}, id=jid2)
        self.server.expect(JOB, {'job_state': "R"}, id=jid3)
        qstat_cmd_json = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                      'qstat') + ' -fp -F json '
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = '\n'.join(ret['out'])
        try:
            js = json.loads(qstat_out)
        except ValueError:
            self.assertTrue(False, 'JSON failed to load.')

        self.assertIn('Jobs', js)
        self.assertIn(jid, js['Jobs'])
        self.assertIn('Resource_List', js['Jobs'][jid])
        self.assertIn(jid2, js['Jobs'])
        self.assertIn('Resource_List', js['Jobs'][jid2])
        self.assertIn(jid3, js['Jobs'])
        self.assertIn('Resource_List', js['Jobs'][jid3])

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
        except ValueError as e:
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
        except ValueError as e:
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
        except ValueError as e:
            self.assertTrue(False)

        json_only_attrs = ['Server', 'timestamp', 'pbs_version', 'pbs_server']
        attrs_qstatbf = self.get_qstat_attribs(SERVER)

        qstat_json_attr = []
        for key, val in json_object.items():
            qstat_json_attr.append(str(key))
            if isinstance(val, dict):
                self.parse_json(val, qstat_json_attr)

        for attr in attrs_qstatbf:
            if attr not in qstat_json_attr:
                self.assertFalse(attr + " is missing")

        for attr in json_only_attrs:
            if attr not in qstat_json_attr:
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
        except ValueError as e:
            self.assertTrue(False)

        json_only_attrs = ['Queue', 'timestamp', 'pbs_version', 'pbs_server']
        attrs_qstatqf = self.get_qstat_attribs(QUEUE)

        qstat_json_attr = []
        for key, val in json_object.items():
            qstat_json_attr.append(str(key))
            if isinstance(val, dict):
                self.parse_json(val, qstat_json_attr)

        for attr in attrs_qstatqf:
            if attr not in qstat_json_attr:
                self.assertFalse(attr + " is missing")

        for attr in json_only_attrs:
            if attr not in qstat_json_attr:
                self.assertFalse(attr + " is missing")

    def test_qstat_qf_json_valid_multiple_queues(self):
        """
        Test json output of qstat -Qf is in valid format when
        we query multiple queues
        """
        a = {'queue_type': 'Execution', 'resources_max.walltime': '10:00:00'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq3')
        qstat_cmd_json = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                      'qstat') + ' -Q -f -F json'
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        qstat_out = "\n".join(ret['out'])
        try:
            qs = json.loads(qstat_out)
        except ValueError:
            self.assertTrue(False, "Invalid JSON, failed to load")

        self.assertIn('Queue', qs)
        self.assertIn('workq', qs['Queue'])
        self.assertIn('workq2', qs['Queue'])
        self.assertIn('resources_max', qs['Queue']['workq2'])
        self.assertIn('workq3', qs['Queue'])
        self.assertIn('resources_max', qs['Queue']['workq3'])

    def test_qstat_json_valid_job_special_env(self):
        """
        Test json output of qstat -f is in valid format
        with special chars in env
        """
        os.environ["DOUBLEQUOTES"] = 'hi"ha'
        os.environ["REVERSESOLIDUS"] = r'hi\ha'

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

    def test_qstat_json_valid_job_longint_env(self):
        """
        Test if JSON output of qstat -f is in valid format
        with longint in env
        """
        os.environ["LONGINT"] = '1111111111111111111111111111111111111111' + \
                                '1111111111111111111111111111111111111111' + \
                                '11111111111111111111111111111111111'
        os.environ["LONGDOUBLE"] = '1111111111111111111111111111112.88888' + \
                                   '8888888888888888'

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

    def run_namelength_test(self, options=''):
        """
        Changes the server name, sets a long job and queue name,
        and ensures they're truncated correctly in a wide format
        """
        self.server.stop()
        self.assertFalse(self.server.isUp(), 'Failed to stop PBS')

        conf = self.du.parse_pbs_config(self.server.hostname)
        self.du.set_pbs_config(
            self.server.hostname,
            confs={'PBS_SERVER_HOST_NAME': conf['PBS_SERVER'],
                   'PBS_SERVER': 'supersuperduperlongservername31'})

        self.server.start()
        self.assertTrue(self.server.isUp(), 'Failed to start PBS')
        a = {'queue_type': 'Execution', 'enabled': 'True',
             'started': 'True'}
        qname = 'queuename15char'
        jname = 'jobname16xxxchar'
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id=qname)
        a = {ATTR_queue: qname, ATTR_name: jname}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        qstat_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                 'qstat') + ' ' + options + ' ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd)
        qstat_out = '\n'.join(ret['out'])
        jid_trunc = jid[:29] + '*'
        jname_trunc = jname[:14] + '*'
        self.assertIn(jid_trunc, qstat_out)
        self.assertIn(qname, qstat_out)
        self.assertIn(jname_trunc, qstat_out)
        self.assertNotIn(jid, qstat_out)
        self.assertNotIn(jname, qstat_out)

    def test_qstat_wide(self):
        """
        Test if qstat -w correctly prints in wide format
        This tests the normal display function
        """
        self.run_namelength_test('-w')

    def test_qstat_rwt(self):
        """
        Test if qstat -rwt correctly prints in wide format.
        This tests the alternate display function
        """
        self.run_namelength_test('-rwt')

    def test_qstat_answ(self):
        """
        Test if qstat -answ correctly prints in wide format.
        This tests the alternate display function
        """
        self.run_namelength_test('-answ')

    def test_qstat_ans(self):
        """
        Test if qstat -ans correctly prints with truncation.
        """
        self.server.stop()
        self.assertFalse(self.server.isUp(), 'Failed to stop PBS')

        server_hostname = self.server.pbs_conf['PBS_SERVER']
        self.du.set_pbs_config(
            self.server.hostname,
            confs={'PBS_SERVER_HOST_NAME': server_hostname,
                   'PBS_SERVER': 'supersuperduperlongservername31'})

        self.server.start()
        self.assertTrue(self.server.isUp(), 'Failed to start PBS')
        a = {'queue_type': 'Execution', 'enabled': 'True',
             'started': 'True'}
        qname = 'queuename15char'
        jname = 'jobname16xxxchar'
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id=qname)
        a = {ATTR_queue: qname, ATTR_name: jname}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        qstat_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                 'qstat') + ' -ans ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd)
        qstat_out = '\n'.join(ret['out'])
        jid_trunc = jid[:14] + '*'
        jname_trunc = jname[:9] + '*'
        qname_trunc = qname[:7] + '*'
        self.assertIn(jid_trunc, qstat_out)
        self.assertIn(jname_trunc, qstat_out)
        self.assertIn(qname_trunc, qstat_out)
        self.assertNotIn(jid, qstat_out)
        self.assertNotIn(jname, qstat_out)
        self.assertNotIn(qname, qstat_out)

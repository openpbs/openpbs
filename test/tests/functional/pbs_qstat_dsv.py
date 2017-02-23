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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from ptl.utils.pbs_testsuite import *


class TestQstat_dsv(PBSTestSuite):
    """
    Test qstat output can be viewed in dsv format
    """

    def parse_dsv(self, jid, qstat_type, delimiter=None):
        """
        Common function to parse qstat output using delimiter
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

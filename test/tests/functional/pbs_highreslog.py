# coding: utf-8
# Copyright (C) 1994-2021 Altair Engineering, Inc.
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


from tests.functional import *


class TestHighResLogging(TestFunctional):
    """
    TestSuite for High resolution logging in PBS
    """
    tm_micro_re = re.compile(
        r'(\d{2,2}/\d{2,2}/\d{4,4}\s\d{2,2}:\d{2,2}:\d{2,2}.\d{6,6})')

    def validate_trace_job_lines(self, jid=None):
        """
        Validate that tracejob lines have high resolution time
        stamp
        """
        lines = self.server.log_lines(logtype='tracejob', id=jid, n='ALL')
        if len(lines) > 1:
            # Remove first line as it is not log line
            lines = lines[1:]
        for line in lines:
            m = self.tm_micro_re.match(line)
            if m is None:
                # If this is accounting log, ignore it as
                # Accounting log does not have high res logging
                line = line.split()
                _msg = 'Not Found high resolution time stamp in log'
                self.assertFalse(len(line) >= 3 and
                                 (line[2].strip() != 'A'), _msg)
        _msg = self.server.shortname + \
            ': High resolution time stamp found in log'
        self.logger.info(_msg)

    def validate_server_log_lines(self):
        """
        validates that the server_log lines have high resolution
        time stamp
        """
        lines = self.server.log_lines(logtype=self.server, n=20)
        for line in lines:
            m = self.tm_micro_re.match(line)
            _msg = 'Not Found high resolution time stamp in log'
            self.assertTrue(m, _msg)
        _msg = self.server.shortname + \
            ': High resolution time stamp found in log'
        self.logger.info(_msg)

    def switch_microsecondlogging(self, hostname=None, highrestimestamp=1):
        """
        Set microsecond logging in pbs.conf
        """
        if hostname is None:
            hostname = self.server.hostname
        a = {'PBS_LOG_HIGHRES_TIMESTAMP': highrestimestamp}
        self.du.set_pbs_config(hostname=hostname, confs=a, append=True)
        PbsServiceControl().restart()
        self.assertTrue(self.server.isUp(), 'Failed to restart PBS Daemons')

    def test_disabled(self):
        """
        Disable High res logging, and test that high res timestamp is not
        there in the server logs lines
        """
        self.switch_microsecondlogging(highrestimestamp=0)
        now = time.time()

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        lines = self.server.log_lines(logtype=self.server,
                                      starttime=now)

        _msg = 'Found high resolution time stamp in log,' \
               ' it shouldn\'t be there'

        for line in lines:
            m = self.tm_micro_re.match(line)
            self.assertIsNone(m, _msg)

        _msg = self.server.shortname + \
            ': High resolution time stamp correctly not set in log'
        self.logger.info(_msg)

    def test_disabled_tracejob(self):
        """
        Disable High res logging, and test that high res timestamp is not
        there in the tracejob output
        """
        self.switch_microsecondlogging(highrestimestamp=0)

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        lines = self.server.log_lines(logtype='tracejob', id=jid, n='ALL')
        if len(lines) > 1:
            # Remove first line as it is not log line
            lines = lines[1:]

        _msg = 'Found high resolution time stamp in tracejob, ' \
               'it should not be there'

        for line in lines:
            m = self.tm_micro_re.match(line)
            self.assertIsNone(m, _msg)

        _msg = self.server.shortname + \
            ': High resolution time stamp correctly not set in ' \
            'tracejob output'
        self.logger.info(_msg)

    def test_basic(self):
        """
        Enable High resolution logging, restart server
        and look for high resolution time stamp in server log
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        self.validate_server_log_lines()

    def test_basic_tracejob(self):
        """
        Enable High resolution logging, restart PBS Daemons
        and look for high resolution time stamp in tracejob output
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        self.validate_trace_job_lines(jid=jid)

    def test_env_variable_overwrite(self):
        """
        Check env variable overwrites the pbs.conf value
        """
        a = {'PBS_LOG_HIGHRES_TIMESTAMP': 0}
        self.du.set_pbs_config(confs=a, append=True)
        conf_path = self.du.parse_pbs_config()
        pbs_init = os.path.join(os.sep, conf_path['PBS_EXEC'],
                                'libexec', 'pbs_init.d')
        cmd = copy.copy(self.du.sudo_cmd)
        cmd += ['PBS_LOG_HIGHRES_TIMESTAMP = 1', pbs_init, 'restart']
        self.du.run_cmd(cmd=cmd, as_script=True, wait_on_script=True)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        self.validate_server_log_lines()
        self.validate_trace_job_lines(jid=jid)

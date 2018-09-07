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


class TestQstat(TestFunctional):
    """
    This test suite validates output of qstat with various options
    """

    def test_qstat_pt(self):
        """
        Test that checks correct output for qstat -pt
        """

        attr = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, attr, id=self.mom.hostname)

        job_count = 10
        j = Job(TEST_USER)
        j.set_sleep_time(5)
        j.set_attributes({ATTR_J: '1-' + str(job_count)})
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'B'}, id=jid)

        self.logger.info('Sleep for 7 seconds to let at least one job finish.')
        time.sleep(7)

        qstat_cmd = \
            os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat')
        qstat_cmd_pt = [qstat_cmd, '-pt', str(jid)]
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_pt)

        self.assertEqual(ret['rc'], 0,
                         'Qstat returned with non-zero exit status')
        qstat_out = '\n'.join(ret['out'])

        sjids = [j.create_subjob_id(jid, x) for x in range(1, job_count)]
        for sjid in sjids:
            self.assertIn(sjid, qstat_out, 'Job %s not in output' % sjid)
            sj_escaped = re.escape(sjid)
            match = re.search(
                sj_escaped + r'\s+\S+\s+\S+\s+(--\s+[RQ]|100\s+X)\s+\S+',
                qstat_out)
            self.assertIsNotNone(match, 'Job output does not match')

    def test_qstat_qselect(self):
        """
        Test to check that qstat can handle more than 150 jobs query at a time
        without any connection issues.
        """
        self.server.restart()
        j = Job(TEST_USER)
        for i in range(150):
            self.server.submit(j)
        ret_msg = 'Too many open connections.'
        qselect_cmd = ' `' + \
            os.path.join(
                self.server.client_conf['PBS_EXEC'],
                'bin',
                'qselect') + '`'
        qstat_cmd = os.path.join(
            self.server.client_conf['PBS_EXEC'], 'bin', 'qstat')
        final_cmd = qstat_cmd + qselect_cmd
        ret = self.du.run_cmd(self.server.hostname, final_cmd,
                              as_script=True)
        if ret['rc'] != 0:
            self.assertFalse(ret['err'][0], ret_msg)

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

from tests.functional import *
import json


class TestQstat_oneline_json_dsv(TestFunctional):
    """
    validate qstat output in dsv,json and oneline format
    """

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
            qstat_oneline_out] = [DshUtils().mkstemp()[1] for _ in range(4)]
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
        [qstat_json_script, qstat_json_out] = [DshUtils().mkstemp()[1]
                                               for _ in range(2)]
        qstat_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat')
        f = open(qstat_json_script, 'w')
        f.write(qstat_cmd + ' -f -F json ' + str(jid) + ' > ' + qstat_json_out)
        f.close()
        os.chmod(qstat_json_script, 0o755)
        run_script = 'sh ' + qstat_json_script
        json_ret = self.du.run_cmd(
            self.server.hostname, cmd=run_script)
        data = open(qstat_json_out, 'r').read()
        map(os.remove, [qstat_json_script, qstat_json_out])
        try:
            json_data = json.loads(data)
        except:
            self.assertTrue(False)

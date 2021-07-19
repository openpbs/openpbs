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
from ptl.utils.pbs_secutils import SecConUtils


class TestPbsInitScript(TestFunctional):
    """
    Testing PBS init script
    """

    def setUp(self):
        self.se = SecConUtils()
        for host, mom in self.moms.items():
            if self.se.is_seccon_enabled(mom.hostname):
                msg = "Test not supported on seccon enabled machine"
                self.skip_test(msg)
        TestFunctional.setUp(self)

    def test_env_vars_precede_pbs_conf_file(self):
        """
        Test PBS_START environment variables overrides values in pbs.conf file
        """
        conf = {'PBS_START_SERVER': '1', 'PBS_START_SCHED': '1',
                'PBS_START_COMM': '1', 'PBS_START_MOM': '1'}
        self.du.set_pbs_config(confs=conf)

        conf_path = self.du.parse_pbs_config()
        pbs_init = os.path.join(os.sep, conf_path['PBS_EXEC'],
                                'libexec', 'pbs_init.d')
        self.du.run_cmd(cmd=[pbs_init, 'stop'], sudo=True)

        conf['PBS_START_MOM'] = '0'
        self.du.set_pbs_config(confs=conf)

        cmd = copy.copy(self.du.sudo_cmd)
        cmd += ['PBS_START_SERVER=0', 'PBS_START_SCHED=0',
                'PBS_START_COMM=0', 'PBS_START_MOM=1',
                pbs_init, 'start']

        rc = self.du.run_cmd(cmd=cmd, as_script=True)
        output = rc['out']

        self.assertNotIn("PBS server", output)
        self.assertNotIn("PBS sched", output)
        self.assertNotIn("PBS comm", output)
        self.assertIn("PBS mom", output)

    def tearDown(self):
        # Above test leaves system in unusable state for PTL and PBS.
        # Hence restarting PBS explicitly
        PbsServiceControl().restart()
        TestFunctional.tearDown(self)

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


class TestPbsnodes_json(TestFunctional):
    """
    Tests the json output of pbsnodes
    """

    def test_check_no_escape_json(self):
        """
        Test if the comment with no special characters is valid json
        """

        self.server.manager(MGR_CMD_SET, NODE,
                            {'comment': '"hiha"'}, id=self.mom.shortname)
        cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                           'bin', 'pbsnodes') + ' -av -Fjson'
        n_out = self.du.run_cmd(self.server.hostname, cmd=cmd)['out']

        try:
            json.loads("\n".join(n_out))
        except ValueError:
            self.assertFalse(True, "Json failed to load")

    def test_check_newline_escape_json(self):
        """
        Test if the comment with newline is valid json
        """

        self.server.manager(MGR_CMD_SET, NODE,
                            {'comment': '"hi\nha"'}, id=self.mom.shortname)
        cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                           'bin', 'pbsnodes') + ' -av -Fjson'
        n_out = self.du.run_cmd(self.server.hostname, cmd=cmd)['out']

        try:
            json.loads("\n".join(n_out))
        except ValueError:
            self.assertFalse(True, "Json failed to load")

    def test_check_tab_escape_json(self):
        """
        Test if the comment with tab is valid json
        """

        self.server.manager(MGR_CMD_SET, NODE,
                            {'comment': '"hi\tha"'}, id=self.mom.shortname)
        cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                           'bin', 'pbsnodes') + ' -av -Fjson'
        n_out = self.du.run_cmd(self.server.hostname, cmd=cmd)['out']

        try:
            json.loads("\n".join(n_out))
        except ValueError:
            self.assertFalse(True, "Json failed to load")

    def test_check_quotes_escape_json(self):
        """
        Test if the comment with quotes is valid json
        """

        self.server.manager(MGR_CMD_SET, NODE,
                            {'comment': '\'hi\"ha\''}, id=self.mom.shortname)
        cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                           'bin', 'pbsnodes') + ' -av -Fjson'
        n_out = self.du.run_cmd(self.server.hostname, cmd=cmd)['out']

        try:
            json.loads("\n".join(n_out))
        except ValueError:
            self.assertFalse(True, "Json failed to load")

    def test_check_reverse_solidus_escape_json(self):
        """
        Test if the comment with reverse solidus is valid json
        """

        self.server.manager(MGR_CMD_SET, NODE,
                            {'comment': '"hi\\ha"'}, id=self.mom.shortname)
        cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                           'bin', 'pbsnodes') + ' -av -Fjson'
        n_out = self.du.run_cmd(self.server.hostname, cmd=cmd)['out']

        try:
            json.loads("\n".join(n_out))
        except ValueError:
            self.assertFalse(True, "Json failed to load")

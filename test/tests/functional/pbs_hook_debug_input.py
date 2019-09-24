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
import os
import fnmatch
from ptl.utils.pbs_logutils import PBSLogUtils


class TestHookDebugInput(TestFunctional):
    """
    Tests related to hook debug input files
    """
    def setUp(self):
        TestFunctional.setUp(self)
        if not hasattr(self, 'server_hooks_tmp_dir'):
            self.server_hooks_tmp_dir = \
                os.path.join(self.server.pbs_conf['PBS_HOME'],
                             'server_priv', 'hooks', 'tmp')

    def remove_files_match(self, pattern):
        """
        Remove hook debug files in hooks/tmp folder that
        match pattern
        """
        for item in self.du.listdir(path=self.server_hooks_tmp_dir, sudo=True):
            if fnmatch.fnmatch(item, pattern):
                self.du.rm(path=item, sudo=True)

                # Check if the file was removed
                ret = self.du.isfile(path=item, sudo=True)
                self.assertFalse(ret)

    def match_queue_name_in_input_file(self, input_file_pattern, qname):
        """
        Assert that qname appears in the hook debug input file
        that matches input_file_pattern
        """
        input_file = None
        for item in self.du.listdir(path=self.server_hooks_tmp_dir, sudo=True):
            if fnmatch.fnmatch(item, input_file_pattern):
                input_file = item
                break
        self.assertTrue(input_file is not None)
        with PBSLogUtils().open_log(input_file, sudo=True) as f:
            search_str = 'pbs.event().job.queue=%s' % qname
            self.assertTrue(search_str in f.read().decode())
        self.remove_files_match(input_file_pattern)

    def test_queuejob_hook_debug_input_has_queue_name(self):
        """
        Test that user requested queue name is written to
        queuejob hook debug input file
        """
        hook_name = "queuejob_debug"
        hook_body = ("import pbs\n"
                     "pbs.event().accept()")
        attr = {'enabled': 'true', 'event': 'queuejob', 'debug': 'true'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        new_queue = 'happyq'
        attr = {ATTR_qtype: 'execution', ATTR_enable: 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, attr, id=new_queue)

        input_file_pattern = os.path.join(self.server_hooks_tmp_dir,
                                          'hook_queuejob_%s*.in' % hook_name)
        self.remove_files_match(input_file_pattern)

        j1 = Job(TEST_USER)
        self.server.submit(j1)

        self.match_queue_name_in_input_file(input_file_pattern,
                                            self.server.default_queue)

        attr = {ATTR_queue: new_queue}
        j2 = Job(TEST_USER, attrs=attr)
        self.server.submit(j2)
        self.match_queue_name_in_input_file(input_file_pattern, new_queue)

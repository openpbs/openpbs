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
import os
import time
import socket
import textwrap
import datetime
from tests.functional import *
from tests.functional import MGR_CMD_SET
from tests.functional import SERVER
from tests.functional import ATTR_h
from tests.functional import TEST_USER
from tests.functional import Job
from tests.functional import JOB


class TestHookManagement(TestFunctional):

    def test_hook_00(self):
        """
        By creating an import hook, it executes a management hook.
        """
        self.logger.info("**************** HOOK START ****************")
        # hook_name = "test_management"
        hook_name = "management"
        hook_msg = 'running management hook_00'
        hook_body = """
        import pbs
        e = pbs.event()
        m = e.management
        pbs.logmsg(pbs.LOG_DEBUG, '%s')
        """ % hook_msg
        hook_body = textwrap.dedent(hook_body)
        # attrs = {'event': 'management', 'enabled': 'True'}
        # rv = self.server.create_import_hook(
        #     hook_name, attrs=attrs, body=hook_body, overwrite=True)

        qmgr_path = os.path.join(self.server.pbs_conf["PBS_EXEC"], "bin",
                                 "qmgr")
        fn00 = self.du.create_temp_file()
        fn01 = self.du.create_temp_file()
        with open(fn00, "w+") as tempfd:
            tempfd_name = tempfd.name
            tempfd.write(hook_body)
            self.logger.info("tempfd_name:%s" % tempfd_name)

        self.logger.info("hook_name:%s" % hook_name)
        qmgr_setup = [qmgr_path, "-c",
                      "create hook %s event=management" % hook_name]
        qmgr_cmd = [qmgr_path, "-c",
                    "import hook %s application/x-python default %s" %
                    (hook_name, tempfd_name)]
        qmgr_cleanup = [qmgr_path, "-c",
                        "delete hook %s event=management" % hook_name]
        self.logger.info("qmgr_cmd:%s" % qmgr_cmd)
        current_host = socket.gethostname().split('.')[0]

        start_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = int(time.time())
        with open(fn01, "w+") as tempfd2:
            ret = self.du.run_cmd(current_host, qmgr_setup, stdout=tempfd2,
                                  runas='root')
            ret = self.du.run_cmd(current_host, qmgr_cmd, stdout=tempfd2,
                                  runas='root')
            ret = self.du.run_cmd(current_host, qmgr_cleanup, stdout=tempfd2,
                                  runas='root')
            self.logger.info("tempfd2.name:%s, ts:%s dt:%s" % (tempfd2.name,
                             start_time, start_dt))
        with open(fn01, "r") as tempfd2:
            self.logger.info(tempfd2.read())

        self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")

    def test_hook_01(self):
        """
        By creating an import hook, it executes a management hook.
        hit it again!
        """
        self.logger.info("**************** HOOK START ****************")
        hook_msg = 'running management hook_01'
        hook_body = """
        import pbs
        e = pbs.event()
        m = e.management
        pbs.logmsg(pbs.LOG_DEBUG, '%s')
        """ % hook_msg
        hook_body = textwrap.dedent(hook_body)
        attrs = {'event': 'management', 'enabled': 'True'}

        qmgr_path = os.path.join(self.server.pbs_conf["PBS_EXEC"],
                                 "bin", "qmgr")
        fn00 = self.du.create_temp_file()
        fn01 = self.du.create_temp_file()
        with open(fn00, "w+") as tempfd:
            tempfd_name = tempfd.name
            tempfd.write(hook_body)
            self.logger.info("tempfd_name:%s" % tempfd_name)
        for hook_name in ['a1234', 'b1234', 'c1234']:
            self.logger.info("hook_name:%s" % hook_name)
            qmgr_setup = [qmgr_path, "-c",
                          "create hook %s event=management" % hook_name]
            qmgr_cmd = [qmgr_path, "-c",
                        "import hook %s application/x-python default %s" %
                        (hook_name, tempfd_name)]
            qmgr_cleanup = [qmgr_path, "-c",
                            "delete hook %s event=management" % hook_name]
            self.logger.info("qmgr_cmd:%s" % qmgr_cmd)
            current_host = socket.gethostname().split('.')[0]

            start_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = int(time.time())
            with open(fn01, "w+") as tempfd2:
                ret = self.du.run_cmd(current_host, qmgr_setup,
                                      stdout=tempfd2, runas='root')
                ret = self.du.run_cmd(current_host, qmgr_cmd,
                                      stdout=tempfd2, runas='root')
                ret = self.du.run_cmd(current_host, qmgr_cleanup,
                                      stdout=tempfd2, runas='root')
                self.logger.info("tempfd2.name:%s, ts:%s dt:%s" %
                                 (tempfd2.name, start_time, start_dt))
            with open(fn01, "r") as tempfd2:
                self.logger.info(tempfd2.read())
            self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")

    def test_hook_02(self):
        """
        By creating an import hook, it executes a management hook.
        hit it again!
        """
        self.logger.info("**************** HOOK START ****************")
        hook_msg = 'running management hook_02'
        hook_body = """
        import pbs
        e = pbs.event()
        m = e.management
        pbs.logmsg(pbs.LOG_DEBUG, '%s')
        """ % hook_msg
        hook_body = textwrap.dedent(hook_body)
        attrs = {'event': 'management', 'enabled': 'True'}

        qmgr_path = os.path.join(self.server.pbs_conf["PBS_EXEC"],
                                 "bin", "qmgr")
        fn00 = self.du.create_temp_file()
        fn01 = self.du.create_temp_file()
        with open(fn00, "w+") as tempfd:
            tempfd_name = tempfd.name
            tempfd.write(hook_body)
            self.logger.info("tempfd_name:%s" % tempfd_name)

        hook_name_00 = 'a1234'
        qmgr_setup_00 = [qmgr_path, "-c",
                         "create hook %s event=management" % hook_name_00]
        qmgr_cmd_00 = [qmgr_path, "-c",
                       "import hook %s application/x-python default %s" %
                       (hook_name_00, tempfd_name)]
        qmgr_cleanup_00 = [qmgr_path, "-c",
                           "delete hook %s event=management" % hook_name_00]
        hook_name_01 = 'b1234'
        qmgr_setup_01 = [qmgr_path, "-c",
                         "create hook %s event=management" % hook_name_01]
        qmgr_cmd_01 = [qmgr_path, "-c",
                       "import hook %s application/x-python default %s" %
                       (hook_name_01, tempfd_name)]
        qmgr_cleanup_01 = [qmgr_path, "-c", "delete hook %s event=management" %
                           hook_name_01]
        hook_name_02 = 'c1234'
        qmgr_setup_02 = [qmgr_path, "-c",
                         "create hook %s event=management" % hook_name_02]
        qmgr_cmd_02 = [qmgr_path, "-c",
                       "import hook %s application/x-python default %s" %
                       (hook_name_02, tempfd_name)]
        qmgr_cleanup_02 = [qmgr_path, "-c",
                           "delete hook %s event=management" % hook_name_02]

        current_host = socket.gethostname().split('.')[0]

        start_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = int(time.time())
        with open(fn01, "w+") as tempfd2:
            ret = self.du.run_cmd(current_host, qmgr_setup_00,
                                  stdout=tempfd2, runas='root')
            ret = self.du.run_cmd(current_host, qmgr_setup_01,
                                  stdout=tempfd2, runas='root')
            ret = self.du.run_cmd(current_host, qmgr_setup_02,
                                  stdout=tempfd2, runas='root')
            ret = self.du.run_cmd(current_host, qmgr_cmd_00,
                                  stdout=tempfd2, runas='root')
            ret = self.du.run_cmd(current_host, qmgr_cmd_01,
                                  stdout=tempfd2, runas='root')
            ret = self.du.run_cmd(current_host, qmgr_cmd_02,
                                  stdout=tempfd2, runas='root')
            # out of order delete
            ret = self.du.run_cmd(current_host, qmgr_cleanup_01,
                                  stdout=tempfd2, runas='root')
            ret = self.du.run_cmd(current_host, qmgr_cleanup_00,
                                  stdout=tempfd2, runas='root')
            ret = self.du.run_cmd(current_host, qmgr_cleanup_02,
                                  stdout=tempfd2, runas='root')
            self.logger.info("tempfd2.name:%s, ts:%s dt:%s" %
                             (tempfd2.name, start_time, start_dt))
        with open(fn01, "r") as tempfd2:
            self.logger.info(tempfd2.read())
        self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")

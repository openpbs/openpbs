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


def get_hook_body(hook_msg):
    hook_body = """
    import pbs
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, '%s')
    """ % hook_msg
    hook_body = textwrap.dedent(hook_body)
    return hook_body


def get_hook_body_str(hook_msg):
    hook_body = """
    import pbs
    e = pbs.event()
    m = e.management
    for a in m.attribs:
        pbs.logmsg(pbs.LOG_DEBUG, str(a))
    pbs.logmsg(pbs.LOG_DEBUG, '%s')
    """ % hook_msg
    hook_body = textwrap.dedent(hook_body)
    return hook_body


def get_hook_body_accept(hook_msg):
    hook_body = """
    import pbs
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, '%s')
    e.accept()
    """ % hook_msg
    hook_body = textwrap.dedent(hook_body)
    return hook_body


def get_hook_body_reject(hook_msg):
    hook_body = """
    import pbs
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, '%s')
    e.reject()
    """ % hook_msg
    hook_body = textwrap.dedent(hook_body)
    return hook_body


@tags('hooks', 'smoke')
class TestHookManagement(TestFunctional):

    def test_hook_00(self):
        """
        By creating an import hook, it executes a management hook.
        """
        self.logger.info("**************** HOOK START ****************")
        hook_name = "management"
        hook_msg = 'running management hook_00'
        hook_body = get_hook_body(hook_msg)
        attrs = {'event': 'management', 'enabled': 'True'}
        start_time = int(time.time())
        ret = self.server.create_hook(hook_name, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name)
        ret = self.server.import_hook(hook_name, hook_body)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name)
        ret = self.server.delete_hook(hook_name)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name)

        self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")

    def test_hook_01(self):
        """
        By creating an import hook, it executes a management hook.
        Create three hooks, and create, import and delete each one.
        """
        self.logger.info("**************** HOOK START ****************")
        hook_msg = 'running management hook_01'
        hook_body = get_hook_body(hook_msg)
        attrs = {'event': 'management', 'enabled': 'True'}
        start_time = int(time.time())
        for hook_name in ['a1234', 'b1234', 'c1234']:
            self.logger.info("hook_name:%s" % hook_name)
            ret = self.server.create_hook(hook_name, attrs)
            self.assertEqual(ret, True, "Could not create hook %s" % hook_name)
            ret = self.server.import_hook(hook_name, hook_body)
            self.assertEqual(ret, True, "Could not import hook %s" % hook_name)
            ret = self.server.delete_hook(hook_name)
            self.assertEqual(ret, True, "Could not delete hook %s" % hook_name)
            self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")

    def test_hook_02(self):
        """
        By creating an import hook, it executes a management hook.
        Create three hooks serially, then delete them out of order.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'a1234'
        hook_name_01 = 'b1234'
        hook_name_02 = 'c1234'
        hook_msg_00 = 'running management hook_02 name:%s' % hook_name_00
        hook_body_00 = get_hook_body(hook_msg_00)
        hook_msg_01 = 'running management hook_02 name:%s' % hook_name_01
        hook_body_01 = get_hook_body(hook_msg_01)
        hook_msg_02 = 'running management hook_02 name:%s' % hook_name_02
        hook_body_02 = get_hook_body(hook_msg_02)

        start_time = int(time.time())
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)
        ret = self.server.create_hook(hook_name_01, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_01)
        ret = self.server.create_hook(hook_name_02, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_02)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_01, hook_body_01)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_01)
        ret = self.server.import_hook(hook_name_02, hook_body_02)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_02)

        # out of order delete
        ret = self.server.delete_hook(hook_name_01)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_01)
        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)
        ret = self.server.delete_hook(hook_name_02)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_02)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_msg_01, starttime=start_time)
        self.server.log_match(hook_msg_02, starttime=start_time)

        self.logger.info("**************** HOOK END ****************")

    def test_hook_str_00(self):
        """
        By creating an import hook, it executes a management hook.
        """
        self.logger.info("**************** HOOK START ****************")
        hook_name = "management"
        hook_msg = 'running management hook_str_00'
        hook_body = get_hook_body_str(hook_msg)
        attrs = {'event': 'management', 'enabled': 'True'}
        start_time = int(time.time())
        ret = self.server.create_hook(hook_name, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name)
        ret = self.server.import_hook(hook_name, hook_body)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name)
        ret = self.server.delete_hook(hook_name)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name)

        self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")


    def test_hook_accept_00(self):
        """
        Tests the event.accept() of a hook.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'a1234'
        hook_name_01 = 'b1234'
        hook_name_02 = 'c1234'
        hook_msg_00 = 'running management hook_accept_00 name:%s' % \
            hook_name_00
        hook_body_00 = get_hook_body(hook_msg_00)
        hook_msg_01 = 'running management hook_accept_00 name:%s' % \
            hook_name_01
        hook_body_01 = get_hook_body(hook_msg_01)
        hook_msg_02 = 'running management hook_accept_00 name:%s' % \
            hook_name_02
        hook_body_02 = get_hook_body(hook_msg_02)

        start_time = int(time.time())
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_00)
        ret = self.server.create_hook(hook_name_01, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_01)
        ret = self.server.create_hook(hook_name_02, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_02)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_00)
        ret = self.server.import_hook(hook_name_01, hook_body_01)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_01)
        ret = self.server.import_hook(hook_name_02, hook_body_02)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_02)

        # out of order delete
        ret = self.server.delete_hook(hook_name_01)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_01)
        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_00)
        ret = self.server.delete_hook(hook_name_02)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_02)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_msg_01, starttime=start_time)
        self.server.log_match(hook_msg_02, starttime=start_time)

        self.logger.info("**************** HOOK END ****************")

    def test_hook_reject_00(self):
        """
        Tests the event.reject() of a hook.  The third hook will not fire
        due to the second calling reject.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'a1234'
        hook_name_01 = 'b1234'
        hook_name_02 = 'c1234'
        hook_msg_00 = 'running management hook_reject_00 name:%s' % \
            hook_name_00
        hook_body_00 = get_hook_body(hook_msg_00)
        hook_msg_01 = 'running management hook_reject_00 name:%s' % \
            hook_name_01
        hook_body_01 = get_hook_body_reject(hook_msg_01)
        hook_msg_02 = 'running management hook_reject_00 name:%s' % \
            hook_name_02
        hook_body_02 = get_hook_body(hook_msg_02)

        start_time = int(time.time())
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_00)
        ret = self.server.create_hook(hook_name_01, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_01)
        ret = self.server.create_hook(hook_name_02, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_02)

        self.server.log_match("%s;created at request" % hook_name_00,
            starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_01,
            starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_02,
            starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_00)
        ret = self.server.import_hook(hook_name_01, hook_body_01)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_01)
        ret = self.server.import_hook(hook_name_02, hook_body_02)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_02)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_msg_01, starttime=start_time)
        # we should not see it fire because ^^^ b1234 ^^^ rejects
        self.server.log_match(hook_msg_02, starttime=start_time,
            existence=False)

        # out of order delete, make sure the reject hook is last
        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_00)
        ret = self.server.delete_hook(hook_name_02)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_02)
        # reject hook
        ret = self.server.delete_hook(hook_name_01)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_01)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
            starttime=start_time)
        self.server.log_match("%s;deleted at request of" % hook_name_01,
            starttime=start_time)
        self.server.log_match("%s;deleted at request of" % hook_name_02,
            starttime=start_time)


    def test_hook_reject_01(self):
        """
        Tests the event.reject() of a hook.  All hooks should fire.  The
        second hook is added last thus all three will fire.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'a1234'
        hook_name_01 = 'b1234'
        hook_name_02 = 'c1234'
        hook_msg_00 = 'running management hook_reject_00 name:%s' % \
            hook_name_00
        hook_body_00 = get_hook_body(hook_msg_00)
        hook_msg_01 = 'running management hook_reject_00 name:%s' % \
            hook_name_01
        hook_body_01 = get_hook_body_reject(hook_msg_01)
        hook_msg_02 = 'running management hook_reject_00 name:%s' % \
            hook_name_02
        hook_body_02 = get_hook_body(hook_msg_02)

        start_time = int(time.time())
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_00)
        ret = self.server.create_hook(hook_name_01, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_01)
        ret = self.server.create_hook(hook_name_02, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % \
            hook_name_02)

        self.server.log_match("%s;created at request" % hook_name_00,
            starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_01,
            starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_02,
            starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_00)
        ret = self.server.import_hook(hook_name_02, hook_body_02)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_02)
        # the bad one
        ret = self.server.import_hook(hook_name_01, hook_body_01)
        self.assertEqual(ret, True, "Could not import hook %s" % \
            hook_name_01)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_msg_02, starttime=start_time)
        self.server.log_match(hook_msg_01, starttime=start_time)

        # out of order delete, make sure the reject hook is last
        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_00)
        ret = self.server.delete_hook(hook_name_02)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_02)
        # reject hook
        ret = self.server.delete_hook(hook_name_01)
        self.assertEqual(ret, True, "Could not delete hook %s" % \
            hook_name_01)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
            starttime=start_time)
        self.server.log_match("%s;deleted at request of" % hook_name_01,
            starttime=start_time)
        self.server.log_match("%s;deleted at request of" % hook_name_02,
            starttime=start_time)

        self.logger.info("**************** HOOK END ****************")

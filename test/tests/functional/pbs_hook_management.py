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

import datetime
import os
import socket
import textwrap
import time

from tests.functional import *
from tests.functional import JOB, MGR_CMD_SET, SERVER, TEST_USER, ATTR_h, Job


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


def get_hook_body_reject_with_text(hook_msg, bad_message="badmsg"):
    hook_body = """
    import pbs
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, '%s')
    e.reject('%s')
    """ % (hook_msg, bad_message)
    hook_body = textwrap.dedent(hook_body)
    return hook_body


def get_hook_body_traceback(hook_msg, bad_message="badmsg"):
    hook_body = """
    import pbs
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, '%s')
    raise Exception('%s')
    """ % (hook_msg, bad_message)
    hook_body = textwrap.dedent(hook_body)
    return hook_body


def get_hook_body_sleep(hook_msg, sleeptime=0.0):
    hook_body = """
    import pbs
    import time
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, '%s')
    time.sleep(%s)
    e.accept()
    """ % (hook_msg, sleeptime)
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
        start_time = time.time()
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
        start_time = time.time()
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

        start_time = time.time()
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
        start_time = time.time()
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

        start_time = time.time()
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

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)
        ret = self.server.create_hook(hook_name_01, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_01)
        ret = self.server.create_hook(hook_name_02, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_02)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_01,
                              starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_02,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_01, hook_body_01)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_01)
        ret = self.server.import_hook(hook_name_02, hook_body_02)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_02)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_msg_01, starttime=start_time)
        # we should not see it fire because ^^^ b1234 ^^^ rejects
        self.server.log_match(hook_msg_02, starttime=start_time,
                              existence=False)

        # out of order delete, make sure the reject hook is last
        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)
        ret = self.server.delete_hook(hook_name_02)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_02)
        # reject hook
        ret = self.server.delete_hook(hook_name_01)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_01)

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

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)
        ret = self.server.create_hook(hook_name_01, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_01)
        ret = self.server.create_hook(hook_name_02, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_02)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_01,
                              starttime=start_time)
        self.server.log_match("%s;created at request" % hook_name_02,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_02, hook_body_02)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_02)
        # the bad one
        ret = self.server.import_hook(hook_name_01, hook_body_01)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_01)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_msg_02, starttime=start_time)
        self.server.log_match(hook_msg_01, starttime=start_time)

        # out of order delete, make sure the reject hook is last
        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)
        ret = self.server.delete_hook(hook_name_02)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_02)
        # reject hook
        ret = self.server.delete_hook(hook_name_01)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_01)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)
        self.server.log_match("%s;deleted at request of" % hook_name_01,
                              starttime=start_time)
        self.server.log_match("%s;deleted at request of" % hook_name_02,
                              starttime=start_time)

        self.logger.info("**************** HOOK END ****************")

    def test_hook_reject_02(self):
        """
        Tests the event.reject() of a hook.  The hook will fire and reject
        with a message.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'd1234'
        hook_msg_00 = 'running management hook_reject_02 name:%s' % \
                      hook_name_00
        hook_bad_msg = "badmessagetext"
        hook_body_00 = get_hook_body_reject_with_text(hook_msg_00,
                                                      hook_bad_msg)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_bad_msg, starttime=start_time)

        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)

        self.logger.info("**************** HOOK END ****************")

    def test_hook_traceback_00(self):
        """
        Tests a traceback in a hook.  The hook will fire and reject
        with a message.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'e1234'
        hook_msg_00 = 'running management hook_traceback_00 name:%s' % \
                      hook_name_00
        hook_bad_msg = "badmessagetext"
        hook_body_00 = get_hook_body_traceback(hook_msg_00,
                                               hook_bad_msg)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match(hook_bad_msg, starttime=start_time)

        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)

        self.server.log_match("hook '%s' encountered an exception"
                              % hook_name_00, starttime=start_time)

        self.logger.info("**************** HOOK END ****************")

    def test_hook_alarm_00(self):
        """
        Tests a alarm with a hook.  The hook will fire and reject
        with a message.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True', 'alarm': 1}

        hook_name_00 = 'f1234'
        hook_msg_00 = 'running management hook_alarm_00 name:%s' % \
                      hook_name_00
        hook_body_00 = get_hook_body_sleep(hook_msg_00, sleeptime=2.0)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)

        self.server.log_match("alarm call while running management hook '%s'"
                              % hook_name_00, starttime=start_time)

        self.server.log_match(hook_msg_00, starttime=start_time)

        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)

        self.logger.info("**************** HOOK END ****************")

        self.logger.info("**************** HOOK END ****************")

    def test_hook_import_00(self):
        """
        Test for a set of the management hook attributes.
        """

        def _get_hook_body(hook_msg):
            attributes = ["MGR_CMD_NONE", "MGR_CMD_CREATE", "MGR_CMD_DELETE",
                          "MGR_CMD_SET", "MGR_CMD_UNSET", "MGR_CMD_LIST",
                          "MGR_CMD_PRINT", "MGR_CMD_ACTIVE", "MGR_CMD_IMPORT",
                          "MGR_CMD_EXPORT", "MGR_CMD_LAST", "MGR_OBJ_NONE",
                          "MGR_OBJ_SERVER", "MGR_OBJ_QUEUE", "MGR_OBJ_JOB",
                          "MGR_OBJ_NODE", "MGR_OBJ_RESV", "MGR_OBJ_RSC",
                          "MGR_OBJ_SCHED", "MGR_OBJ_HOST", "MGR_OBJ_HOOK",
                          "MGR_OBJ_PBS_HOOK", "MGR_OBJ_LAST"]
            hook_body = """
            import pbs
            import pbs_ifl
            attributes = %s
            missing = []
            e = pbs.event()
            for attr in attributes:
                if not hasattr(pbs, attr):
                    missing.append(attr)
            if len(missing) > 0:
                e.reject("missing attributes in pbs:" + ",".join(missing))
            else:
                pbs.logmsg(pbs.LOG_DEBUG, 'all attributes found in pbs')
                pbs.logmsg(pbs.LOG_DEBUG, 'dir(pbs_ifl):')
                pbs.logmsg(pbs.LOG_DEBUG, str(dir(pbs_ifl)))
                pbs.logmsg(pbs.LOG_DEBUG, 'dir(pbs):')
                pbs.logmsg(pbs.LOG_DEBUG, str(dir(pbs)))
                m = e.management
                pbs.logmsg(pbs.LOG_DEBUG, '%s')
                e.accept()
            """ % (attributes, hook_msg)
            hook_body = textwrap.dedent(hook_body)
            return hook_body

        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'g1234'
        hook_msg_00 = 'running management hook_import_00 name:%s' % \
                      hook_name_00
        hook_body_00 = _get_hook_body(hook_msg_00)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)

        self.server.log_match(hook_msg_00, starttime=start_time)

        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)

        self.server.log_match("missing attributes in pbs",
                              starttime=start_time, existence=False)
        self.server.log_match("all attributes found in pbs",
                              starttime=start_time, existence=True)

        self.logger.info(str(dir()))
        self.logger.info("**************** HOOK END ****************")

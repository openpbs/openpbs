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
from ptl.utils.pbs_testsuite import generate_hook_body_from_func

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


def hook_accept(hook_msg):
    import pbs
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, hook_msg)
    e.accept()


def hook_reject(hook_msg):
    import pbs
    e = pbs.event()
    m = e.management
    pbs.logmsg(pbs.LOG_DEBUG, hook_msg)
    e.reject()


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


def hook_attrs_func(hook_msg):
    attributes = ["cmd", "objtype", "objname", "request_time",
                    "reply_code", "reply_auxcode", "reply_choice",
                    "reply_text", 'attribs']
    import pbs
    import pbs_ifl
    from pprint import pformat
    missing = []
    e = pbs.event()
    m = e.management
    # pbs.logmsg(pbs.LOG_DEBUG, str(dir(pbs)))
    # pbs.logmsg(pbs.LOG_DEBUG, str(dir(e)))
    # pbs.logmsg(pbs.LOG_DEBUG, str(dir(m)))
    for attr in attributes:
        if not hasattr(m, attr):
            missing.append(attr)
        else:
            value = getattr(m, attr)
            value_lst = []
            if attr == 'attribs':
                if type(value) == list:
                    for obj in value:
                        value_dct = {}
                        value_dct['name'] = obj.name
                        value_dct['value'] = obj.value
                        value_dct['flags'] = obj.flags
                        subvalue_lst = []
                        for k, v in pbs.REVERSE_ATR_VFLAGS.items():
                            if int(k) & int(obj.flags):
                                subvalue_lst.append(str(v))
                        value_dct[f"flags_lst"] = subvalue_lst
                        value_dct['op'] = obj.op
                        value_dct[f"op_str"] = pbs.REVERSE_BATCH_OPS[obj.op]
                        value_dct['resource'] = obj.resource
                        value_dct['sisters'] = obj.sisters
                        value_lst.append(value_dct)
                    pbs.logmsg(pbs.LOG_DEBUG, f"attribs=>{pformat(value_lst)}")
            elif attr == 'objtype':
                value_str = pbs.REVERSE_MGR_OBJS[value]
                pbs.logmsg(pbs.LOG_DEBUG, f"{attr}=>{value_str} (reversed)")
            elif attr == 'reply_choice':
                value_str = pbs.REVERSE_BRP_CHOICES[value]
                pbs.logmsg(pbs.LOG_DEBUG, f"{attr}=>{value_str} (reversed)")
            elif attr == 'cmd':
                value_str = pbs.REVERSE_MGR_CMDS[value]
                pbs.logmsg(pbs.LOG_DEBUG, f"{attr}=>{value_str} (reversed)")
            if attr == 'attribs':
                lst = []
                for idx, dct in enumerate(value_lst):
                    dct_lst = []
                    for key, value in dct.items():
                        dct_lst.append(f"{key}:{value}")
                    # need to sort the list to allow for the test to
                    # find the string correctly.
                    dct_lst = sorted(dct_lst)
                    dct_lst_str = f"{attr}[{idx}]=>{','.join(dct_lst)}"
                    pbs.logmsg(pbs.LOG_DEBUG, f"{dct_lst_str} (stringified)")
            else:
                pbs.logmsg(pbs.LOG_DEBUG, f"{attr}=>{value}")
    if len(missing) > 0:
        e.reject("missing attributes in pbs:" + ",".join(missing))
    else:
        pbs.logmsg(pbs.LOG_DEBUG, 'all attributes found in pbs')
        # pbs.logmsg(pbs.LOG_DEBUG, 'dir(pbs_ifl):')
        # pbs.logmsg(pbs.LOG_DEBUG, str(dir(pbs_ifl)))
        # pbs.logmsg(pbs.LOG_DEBUG, 'dir(pbs):')
        # pbs.logmsg(pbs.LOG_DEBUG, str(dir(pbs)))
        m = e.management
        pbs.logmsg(pbs.LOG_DEBUG, hook_msg)
        e.accept()


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
        hook_body_01 = generate_hook_body_from_func(hook_reject, hook_msg_01)
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
        # we should not see vvv it vvv fire because ^^^ b1234 ^^^ rejects
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
        hook_body_01 = generate_hook_body_from_func(hook_reject, hook_msg_01)
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

        self.logger.info("**************** HOOK END ****************")


    def test_hook_attrs_00(self):
        """
        Test for a set of the management hook attributes.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'h1234'
        hook_msg_00 = 'running management hook_import_00 name:%s' % \
                      hook_name_00
        hook_body_00 = generate_hook_body_from_func(hook_attrs_func,
                                                    hook_msg_00)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match("cmd=>7", starttime=start_time)
        self.server.log_match("objtype=>8", starttime=start_time)
        self.server.log_match("objname=>%s" % hook_name_00,
                              starttime=start_time)
        self.server.log_match("reply_code=>0", starttime=start_time)
        self.server.log_match("reply_auxcode=>0", starttime=start_time)
        self.server.log_match("reply_choice=>1", starttime=start_time)
        self.server.log_match("reply_text=>None", starttime=start_time)

        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)

        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)

        self.server.log_match("missing attributes in pbs",
                              starttime=start_time, existence=False)
        self.server.log_match("all attributes found in pbs",
                              starttime=start_time, existence=True)

        self.logger.info("**************** HOOK END ****************")

    def test_hook_attrs_01(self):
        """
        Test for a set of the management hook attributes.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'i1234'
        hook_msg_00 = 'running management hook_import_00 name:%s' % \
                      hook_name_00
        hook_body_00 = generate_hook_body_from_func(hook_attrs_func,
                                                    hook_msg_00)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match("cmd=>7", starttime=start_time)
        self.server.log_match("objtype=>8", starttime=start_time)
        self.server.log_match("objname=>%s" % hook_name_00,
                              starttime=start_time)
        self.server.log_match("reply_code=>0", starttime=start_time)
        self.server.log_match("reply_auxcode=>0", starttime=start_time)
        self.server.log_match("reply_choice=>1", starttime=start_time)
        self.server.log_match("reply_text=>None", starttime=start_time)

        # run a qmgr command and import the script.
        hook_name_01 = 'i1234accept'
        hook_msg_01 = "%s accept hook" % hook_name_01
        hook_body_01 = generate_hook_body_from_func(hook_accept, hook_msg_01)
        attrs = {'event': 'queuejob', 'enabled': 'True'}
        ret = self.server.create_hook(hook_name_01, attrs)
        ret = self.server.import_hook(hook_name_01, hook_body_01)

        # we don't need to run a job, we just want to check the attributes.
        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match("cmd=>0", starttime=start_time)
        self.server.log_match("objtype=>8", starttime=start_time)
        self.server.log_match("objname=>%s" % hook_name_01,
                              starttime=start_time)
        self.server.log_match("reply_code=>0", starttime=start_time)
        self.server.log_match("reply_auxcode=>0", starttime=start_time)
        self.server.log_match("reply_choice=>1", starttime=start_time)
        self.server.log_match("reply_text=>None", starttime=start_time)
        self.server.log_match("server_priv/hooks/%s.PY" % hook_name_01,
                              starttime=start_time)

        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)
        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)
        ret = self.server.delete_hook(hook_name_01)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_01)
        self.server.log_match("%s;deleted at request of" % hook_name_01,
                              starttime=start_time)
        self.server.log_match("missing attributes in pbs",
                              starttime=start_time, existence=False)
        self.server.log_match("all attributes found in pbs",
                              starttime=start_time, existence=True)

        self.logger.info("**************** HOOK END ****************")

    def test_hook_attrs_02(self):
        """
        Test for a set of the management hook attributes.
        """
        self.logger.info("**************** HOOK START ****************")
        attrs = {'event': 'management', 'enabled': 'True'}

        hook_name_00 = 'j1234'
        hook_msg_00 = 'running management hook_import_00 name:%s' % \
                      hook_name_00
        hook_body_00 = generate_hook_body_from_func(hook_attrs_func,
                                                    hook_msg_00)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

        start_time = time.time()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)

        self.server.log_match("%s;created at request" % hook_name_00,
                              starttime=start_time)

        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name_00)

        self.server.log_match(hook_msg_00, starttime=start_time)
        self.server.log_match("cmd=>7", starttime=start_time)
        self.server.log_match("objtype=>8", starttime=start_time)
        self.server.log_match("objname=>%s" % hook_name_00,
                              starttime=start_time)
        self.server.log_match("reply_code=>0", starttime=start_time)
        self.server.log_match("reply_auxcode=>0", starttime=start_time)
        self.server.log_match("reply_choice=>1", starttime=start_time)
        self.server.log_match("reply_text=>None", starttime=start_time)

        for mom in self.server.moms.values():
            start_time_mom = time.time()
            self.logger.error(f"deleting and creating\n"
                              f"mom.hostname:{mom.hostname}\n"
                              f"mom.fqdn:{mom.fqdn}\n"
                              f"mom.name:{mom.name}\n"
                              f"mom.__dict__:{mom.__dict__}\n"
                              )
            # self.server.delete_node(mom.shortname)
            # self.server.create_node(mom.shortname)
            self.server.manager(MGR_CMD_SET, NODE,
                                {'resources_available.ncpus': '700000'},
                                id=mom.shortname)
            self.server.manager(MGR_CMD_UNSET, NODE,
                                'resources_available.ncpus',
                                id=mom.shortname)
            self.server.log_match("cmd=>MGR_CMD_SET",
                                  starttime=start_time_mom)
            self.server.log_match("objtype=>MGR_OBJ_NODE",
                                  starttime=start_time_mom)
            self.server.log_match("objname=>%s" % mom.shortname,
                                  starttime=start_time_mom)

            self.server.log_match("attribs=>flags:0,flags_lst:[],name:resource"
                                  "s_available,op:0,op_str:BATCH_OP_SET,resour"
                                  "ce:ncpus,sisters:[],value:700000 (stringifi"
                                  "ed)",
                                  starttime=start_time_mom)
            self.server.log_match("attribs=>flags:0,flags_lst:[],name:resource"
                                  "s_available,op:0,op_str:BATCH_OP_SET,resour"
                                  "ce:ncpus,sisters:[],value: (stringified)",
                                  starttime=start_time_mom)

            """07/08/2021 13:57:09.301273;0006;Server@pdw-s1;Hook;Server@pdw-s1;cmd=>MGR_CMD_SET (reversed)
            07/08/2021 13:57:09.301282;0006;Server@pdw-s1;Hook;Server@pdw-s1;cmd=>2
            07/08/2021 13:57:09.301288;0006;Server@pdw-s1;Hook;Server@pdw-s1;objtype=>MGR_OBJ_NODE (reversed)
            07/08/2021 13:57:09.301292;0006;Server@pdw-s1;Hook;Server@pdw-s1;objtype=>3
            07/08/2021 13:57:09.301297;0006;Server@pdw-s1;Hook;Server@pdw-s1;objname=>pdw-c4
            07/08/2021 13:57:09.301301;0006;Server@pdw-s1;Hook;Server@pdw-s1;request_time=>1625752629
            07/08/2021 13:57:09.301306;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_code=>0
            07/08/2021 13:57:09.301310;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_auxcode=>0
            07/08/2021 13:57:09.301314;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_choice=>BRP_CHOICE_NULL (reversed)
            07/08/2021 13:57:09.301318;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_choice=>1
            07/08/2021 13:57:09.301324;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_text=>None
            07/08/2021 13:57:09.301472;0006;Server@pdw-s1;Hook;Server@pdw-s1;attribs=>[{'flags': 0,
            'flags_lst': [],
            'name': 'resources_available',
            'op': 0,
            'op_str': 'BATCH_OP_SET',
            'resource': 'ncpus',
            'sisters': [],
            'value': '700000'}]"""

            """07/08/2021 13:57:09.324183;0006;Server@pdw-s1;Hook;Server@pdw-s1;cmd=>MGR_CMD_UNSET (reversed)
            07/08/2021 13:57:09.324194;0006;Server@pdw-s1;Hook;Server@pdw-s1;cmd=>3
            07/08/2021 13:57:09.324200;0006;Server@pdw-s1;Hook;Server@pdw-s1;objtype=>MGR_OBJ_NODE (reversed)
            07/08/2021 13:57:09.324205;0006;Server@pdw-s1;Hook;Server@pdw-s1;objtype=>3
            07/08/2021 13:57:09.324223;0006;Server@pdw-s1;Hook;Server@pdw-s1;objname=>pdw-c4
            07/08/2021 13:57:09.324228;0006;Server@pdw-s1;Hook;Server@pdw-s1;request_time=>1625752629
            07/08/2021 13:57:09.324232;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_code=>0
            07/08/2021 13:57:09.324237;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_auxcode=>0
            07/08/2021 13:57:09.324241;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_choice=>BRP_CHOICE_NULL (reversed)
            07/08/2021 13:57:09.324245;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_choice=>1
            07/08/2021 13:57:09.324251;0006;Server@pdw-s1;Hook;Server@pdw-s1;reply_text=>None
            07/08/2021 13:57:09.324482;0006;Server@pdw-s1;Hook;Server@pdw-s1;attribs=>[{'flags': 0,
            'flags_lst': [],
            'name': 'resources_available',
            'op': 0,
            'op_str': 'BATCH_OP_SET',
            'resource': 'ncpus',
            'sisters': [],
            'value': ''}]
            """


            # self.server.log_match("Node;%s;node up" % mom.fqdn,
            #                       starttime=start_time)
            # self.server.log_match("Node;%s;node down" % mom.fqdn,
            #                       starttime=start_time)

        ret = self.server.delete_hook(hook_name_00)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name_00)
        self.server.log_match("%s;deleted at request of" % hook_name_00,
                              starttime=start_time)

        self.server.log_match("missing attributes in pbs",
                              starttime=start_time, existence=False)
        self.server.log_match("all attributes found in pbs",
                              starttime=start_time, existence=True)

        self.logger.info("**************** HOOK END ****************")



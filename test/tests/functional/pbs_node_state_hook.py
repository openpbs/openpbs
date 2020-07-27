# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

import time
import socket
import logging
import textwrap
from pprint import pformat
from tests.functional import *
from ptl.utils.pbs_dshutils import get_method_name


def get_hook_body(hook_msg):
    hook_body = """
    import pbs
    import sys, os
    from pprint import pformat
    pbs.logmsg(pbs.LOG_DEBUG, "pbs.__file__:" + pbs.__file__)
    #pbs.logmsg(pbs.LOG_DEBUG, "print(help('modules')):" + str(help('modules')))
    try:
        e = pbs.event()
        pbs.logmsg(pbs.LOG_DEBUG, str(pformat(pbs.REVERSE_NODE_STATES)))
        for key, value in pbs.REVERSE_NODE_STATES.items():
            pbs.logmsg(pbs.LOG_DEBUG, 'k:' + str(key) + ' v:' + str(value))
        hostname = e.node_state.hostname
        new_state = e.node_state.new_state
        old_state = e.node_state.old_state
        pbs.logmsg(pbs.LOG_DEBUG, 'hostname:' + hostname)
        pbs.logmsg(pbs.LOG_DEBUG, 'new_state:' + hex(new_state))
        pbs.logmsg(pbs.LOG_DEBUG, 'old_state:' + hex(old_state))
        pbs.logmsg(pbs.LOG_DEBUG, '%s')
    except Exception as err:
        ty, _, tb = sys.exc_info()
        pbs.logmsg(pbs.LOG_DEBUG, str(ty) + str(tb.tb_frame.f_code.co_filename)
                   + str(tb.tb_lineno))
        e.reject()
    else:
        e.accept()
    """ % hook_msg
    hook_body = textwrap.dedent(hook_body)
    return hook_body


class TestPbsNodeStateHook(TestFunctional):

    """
    This tests Node create and delete.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

        self.server.cleanup_jobs()

    def tearDown(self):

        TestFunctional.tearDown(self)
        # Delete managers and operators if added
        attrib = ['operators', 'managers']
        self.server.manager(MGR_CMD_UNSET, SERVER, attrib)

    def test_check_node_state_lookup(self):
        """
        This test checks for the existance and values of the
        pbs.REVERSE_NODE_STATES dictionary.
        """
        #print(help('modules'))
        #import ptl.lib.pbs_ifl as ptl
        #import ptl.lib.pbs_ifl_mock as ptl
        #print(dir(ptl))

        #from _pbs_v1 import REVERSE_NODE_STATES

        # correct_dct = {0: 'NODE_STATE_FREE',
        #                1: 'NODE_STATE_OFFLINE',
        #                2: 'NODE_STATE_DOWN',
        #                4: 'NODE_STATE_DELETED',
        #                8: 'NODE_STATE_UNRESOLVABLE',
        #                16: 'NODE_STATE_JOB',
        #                32: 'NODE_STATE_STALE',
        #                64: 'NODE_STATE_JOBEXCL',
        #                128: 'NODE_STATE_BUSY',
        #                256: 'NODE_STATE_UNKNOWN',
        #                512: 'NODE_STATE_NEEDS_HELLO_PING',
        #                1024: 'NODE_STATE_INIT',
        #                2048: 'NODE_STATE_PROV',
        #                4096: 'NODE_STATE_WAIT_PROV',
        #                8192: 'NODE_STATE_RESVEXCL',
        #                8400: 'NODE_STATE_VNODE_AVAILABLE',
        #                16384: 'NODE_STATE_OFFLINE_BY_MOM',
        #                32768: 'NODE_STATE_MARKEDDOWN',
        #                65536: 'NODE_STATE_NEED_ADDRS',
        #                131072: 'NODE_STATE_MAINTENANCE',
        #                262144: 'NODE_STATE_SLEEP',
        #                409903: 'NODE_STATE_VNODE_UNAVAILABLE',
        #                524288: 'NODE_STATE_NEED_CREDENTIALS'}
        # self.assertEqual(REVERSE_NODE_STATES, correct_dct)

    @requirements(num_moms=2)
    def test_create_hook_and_delete_00(self):
        """
        Test:  this will test three things:
        1.  The stopping and starting of a mom and the proper log messages.
        2.  The testing of the hook
        3.  The stopping and starting of a mom and the proper hook firing.
        """
        self.logger.info("---- TEST STARTED ----")

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})

        attrs = {'event': 'node_state', 'enabled': 'True', 'debug': 'True'}
        hook_name_00 = 'a1234'
        hook_msg_00 = 'running %s' % get_method_name(self)
        hook_body_00 = get_hook_body(hook_msg_00)
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_00, hook_body_00)
        self.logger.error("socket.gethostname():%s", socket.gethostname())
        self.logger.error("***self.server.name:%s", str(self.server.name))
        self.logger.error("self.server.moms:%s", str(self.server.moms))
        for name, value in self.server.moms.items():
            start_time = int(time.time())
            self.logger.error("    ***%s:%s, type:%s", name, value,
                              type(value))
            self.logger.error("    ***%s:fqdn:    %s", name, value.fqdn)
            self.logger.error("    ***%s:hostname:%s", name, value.hostname)
            self.logger.error("    ***stopping mom:%s", value)
            value.stop()
            self.logger.error("    ***start    mom:%s", value)
            value.start()
            self.logger.error("    ***restart  mom:%s", value)
            value.restart()
            self.server.log_match("Node;%s;node up" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("Node;%s;node down" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match(hook_msg_00, starttime=start_time)
        self.logger.info("---- TEST ENDED ----")

    @requirements(num_moms=2)
    def test_create_hook_and_delete_01(self):
        """
        Test:  this will test three things:
        1.  The stopping and starting of a mom and the proper log messages.
        2.  The testing of the hook
        3.  The stopping and starting of a mom and the proper hook firing.
        """
        self.logger.info("---- TEST STARTED ----")
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})
        attrs = {'event': 'node_state', 'enabled': 'True', 'debug': 'True'}
        hook_name_00 = 'b1234'
        hook_msg_00 = 'running %s' % get_method_name(self)
        hook_body_00 = get_hook_body(hook_msg_00)
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_00, hook_body_00)
        for name, value in self.server.moms.items():
            hostbasename = socket.gethostbyaddr(value.fqdn)[0].split('.', 1)[0]
            start_time = int(time.time())
            self.logger.error("    ***%s:%s, type:%s", name, value,
                              type(value))
            self.logger.error("    ***%s:fqdn:    %s", name, value.fqdn)
            self.logger.error("    ***%s:hostname:%s", name, value.hostname)
            self.logger.error("    ***stopping mom:%s", value)
            start_time = int(time.time())
            value.stop()
            self.server.log_match("Node;%s;node down" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("new_state:0x2", starttime=start_time)
            self.server.log_match("old_state:0x0", starttime=start_time)
            start_time = int(time.time())
            self.logger.error("    ***start    mom:%s", value)
            value.start()
            self.server.log_match("new_state:0x422", starttime=start_time)
            self.server.log_match("old_state:0x400", starttime=start_time)
            start_time = int(time.time())
            self.logger.error("    ***restart  mom:%s", value)
            value.restart()
            self.server.log_match("Node;%s;node down" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("Node;%s;node up" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("new_state:0x0", starttime=start_time)
            self.server.log_match("old_state:0x400", starttime=start_time)
            self.server.log_match(hook_msg_00, starttime=start_time)
            self.server.log_match("hostname:%s" % hostbasename,
                                  starttime=start_time)
        self.logger.info("---- TEST ENDED ----")


    @requirements(num_moms=2)
    def test_pkill_moms_00(self):
        """
        Test:  this will test four things:
        1.  It will pkill pbs_mom, look for the proper log messages.
        2.  It will check the log for the proper hook messages
        3.  It will bring up pbs_mom, look for the proper log messages.
        4.  It will check the log for the proper hook messages
        """
        self.logger.info("---- TEST STARTED ----")
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})
        attrs = {'event': 'node_state', 'enabled': 'True', 'debug': 'True'}
        hook_name_00 = 'c1234'
        hook_msg_00 = 'running %s' % get_method_name(self)
        hook_body_00 = get_hook_body(hook_msg_00)
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_00, hook_body_00)
        for name, value in self.server.moms.items():
            hostbasename = socket.gethostbyaddr(value.fqdn)[0].split('.', 1)[0]
            start_time = int(time.time())
            self.logger.error("    ***%s:%s, type:%s", name, value, type(value))
            self.logger.error("    ***%s:fqdn:    %s", name, value.fqdn)
            self.logger.error("    ***%s:hostname:%s", name, value.hostname)
            self.logger.error("    ***pkilling mom:%s", value)
            start_time = int(time.time())
            pkill_cmd = ['/usr/bin/pkill', '-9', 'pbs_mom']
            fpath = self.du.create_temp_file()
            with open(fpath) as fileobj:
                ret = self.server.du.run_cmd(
                    value.fqdn, pkill_cmd, stdin=fileobj, sudo=True,
                    logerr=True, level=logging.DEBUG)
                self.logger.error("pkill(ret):%s", str(pformat(ret)))
            self.server.log_match("Node;%s;node down" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("new_state:0x2", starttime=start_time)
            self.server.log_match("old_state:0x0", starttime=start_time)
            start_time = int(time.time())
            self.logger.error("    ***start    mom:%s", value)
            value.start()
            self.server.log_match("new_state:0x422", starttime=start_time)
            self.server.log_match("old_state:0x400", starttime=start_time)
            start_time = int(time.time())
            self.logger.error("    ***restart  mom:%s", value)
            value.restart()
            self.server.log_match("Node;%s;node down" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("Node;%s;node up" % value.fqdn,
                                  starttime=start_time)
            self.server.log_match("new_state:0x0", starttime=start_time)
            self.server.log_match("old_state:0x400", starttime=start_time)
            self.server.log_match(hook_msg_00, starttime=start_time)
            self.server.log_match("hostname:%s" % hostbasename,
                                  starttime=start_time)
        self.logger.info("---- TEST ENDED ----")

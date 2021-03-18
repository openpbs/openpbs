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

import socket
import logging
import textwrap
from pprint import pformat
from tests.functional import *
from ptl.utils.pbs_dshutils import get_method_name


node_states = {
    'ND_STATE_FREE': 0,
    'ND_STATE_OFFLINE': 1,
    'ND_STATE_DOWN': 2,
    'ND_STATE_DELETED': 4,
    'ND_STATE_UNRESOLVABLE': 8,
    'ND_STATE_STALE': 32,
    'ND_STATE_JOBBUSY': 16,
    'ND_STATE_JOB_EXCLUSIVE': 64,
    'ND_STATE_RESV_EXCLUSIVE': 8192,
    'ND_STATE_BUSY': 128,
    'ND_STATE_UNKNOWN': 256,
    'ND_STATE_NEEDS_HELLOSVR': 512,
    'ND_STATE_INIT': 1024,
    'ND_STATE_PROV': 2048,
    'ND_STATE_WAIT_PROV': 4096,
    'ND_STATE_SLEEP': 262144,
    'ND_STATE_OFFLINE_BY_MOM': 16384,
    'ND_STATE_MARKEDDOWN': 32768,
    'ND_STATE_NEED_ADDRS': 65536,
    'ND_STATE_MAINTENANCE': 131072,
    'ND_STATE_NEED_CREDENTIALS': 524288,
    'ND_STATE_VNODE_UNAVAILABLE': 409903
}


def get_hook_body_modifyvnode_param_rpt():
    hook_body = """
    import pbs
    import sys
    try:
        e = pbs.event()
        v = e.vnode
        v_o = e.vnode_o
        lsct = v.last_state_change_time
        lsct_o = v_o.last_state_change_time
        state_str_buf_v = ",".join(v.extract_state_strs())
        state_str_buf_v_o = ",".join(v_o.extract_state_strs())
        state_int_buf_v = ','.join([str(_) for _ in v.extract_state_ints()])
        state_int_buf_v_o = ','.join(
            [str(_) for _ in v_o.extract_state_ints()])
        # print show_vnode_state record (bi consumable)
        svs1_data = "v.state_hex=%s v_o.state_hex=%s v.state_strs=%s " \
                    "v_o.state_strs=%s" % \
                    (hex(v.state), hex(v_o.state), state_str_buf_v,
                     state_str_buf_v_o)
        svs2_data = "v.state_ints=%s v_o.state_ints=%s v.lsct=%s " \
                    "v_o.lsct=%s" % \
                    (state_int_buf_v, state_int_buf_v_o, str(lsct),
                     str(lsct_o))
        svs_data = "%s %s" % (svs1_data, svs2_data)
        pbs.logmsg(pbs.LOG_DEBUG,
                   "show_vnode_state;name=%s %s" % (v.name, svs_data))
        # print additional hook parameter values
        pbs.logmsg(pbs.LOG_DEBUG, "name: v=%s, v_o=%s" % (v.name, v_o.name))
        pbs.logmsg(pbs.LOG_DEBUG,
                   "state: v=%s, v_o=%s" % (hex(v.state), hex(v_o.state)))
        pbs.logmsg(pbs.LOG_DEBUG, "last_state_change_time: v=%s, v_o=%s" % (
                   str(lsct), str(lsct_o)))
        pbs.logmsg(pbs.LOG_DEBUG,
                   "comment: v=%s, v_o=%s" % (v.comment, v_o.comment))
        pbs.logmsg(pbs.LOG_DEBUG,
                   "aoe: v=%s, v_o=%s" % (v.current_aoe, v_o.current_aoe))
        pbs.logmsg(pbs.LOG_DEBUG, "in_mvn_host: v=%s, v_o=%s" % (
                   v.in_multivnode_host, v_o.in_multivnode_host))
        pbs.logmsg(pbs.LOG_DEBUG, "jobs: v=%s, v_o=%s" % (v.jobs, v_o.jobs))
        pbs.logmsg(pbs.LOG_DEBUG, "Mom: v=%s, v_o=%s" % (v.Mom, v_o.Mom))
        pbs.logmsg(pbs.LOG_DEBUG,
                   "ntype: v=%s, v_o=%s" % (hex(v.ntype), hex(v_o.ntype)))
        pbs.logmsg(pbs.LOG_DEBUG, "pcpus: v=%s, v_o=%s" % (v.pcpus, v_o.pcpus))
        pbs.logmsg(pbs.LOG_DEBUG,
                   "pnames: v=%s, v_o=%s" % (v.pnames, v_o.pnames))
        pbs.logmsg(pbs.LOG_DEBUG, "Port: v=%s, v_o=%s" % (v.Port, v_o.Port))
        pbs.logmsg(pbs.LOG_DEBUG,
                   "Priority: v=%s, v_o=%s" % (v.Priority, v_o.Priority))
        pbs.logmsg(pbs.LOG_DEBUG, "provision_enable: v=%s, v_o=%s" % (
                   v.provision_enable, v_o.provision_enable))
        pbs.logmsg(pbs.LOG_DEBUG, "queue: v=%s, v_o=%s" % (v.queue, v_o.queue))
        pbs.logmsg(pbs.LOG_DEBUG, "res_assigned: v=%s, v_o=%s" % (
                   v.resources_assigned, v_o.resources_assigned))
        pbs.logmsg(pbs.LOG_DEBUG, "res_avail: v=%s, v_o=%s" % (
                   v.resources_available, v_o.resources_available))
        pbs.logmsg(pbs.LOG_DEBUG, "resv: v=%s, v_o=%s" % (v.resv, v_o.resv))
        pbs.logmsg(pbs.LOG_DEBUG, "resv_enable: v=%s, v_o=%s" % (
                   v.resv_enable, v_o.resv_enable))
        pbs.logmsg(pbs.LOG_DEBUG,
                   "sharing: v=%s, v_o=%s" % (v.sharing, v_o.sharing))
        # sanity test some values
        if (lsct < lsct_o) or (lsct_o <= 0):
            e.reject("last_state_change_time: bad timestamp value")
        else:
            pbs.logmsg(pbs.LOG_DEBUG, "last_state_change_time: good times")
        if (v.name != v_o.name) or (not v.name):
            e.reject(
                "name: vnode and vnode_o name values are null or mismatched")
        else:
            pbs.logmsg(pbs.LOG_DEBUG, "name: good names")
        if (isinstance(v.state, int)) and (isinstance(v_o.state, int)):
            pbs.logmsg(pbs.LOG_DEBUG, "state: good states")
        else:
            e.reject("state: bad state value")
        if len(v.extract_state_strs()) == len(v.extract_state_ints()):
            pbs.logmsg(pbs.LOG_DEBUG, "state sets: good v sets")
        else:
            e.reject("state sets: bad v sets")
        if len(v_o.extract_state_strs()) == len(v_o.extract_state_ints()):
            pbs.logmsg(pbs.LOG_DEBUG, "state sets: good v_o sets")
        else:
            e.reject("state sets: bad v_o sets")
        e.accept()
    except SystemExit:
        pass
    except:
        pbs.event().reject("%s hook failed with %s" % (
                           pbs.event().hook_name, sys.exc_info()[:2]))
    """
    hook_body = textwrap.dedent(hook_body)
    return hook_body


def get_hook_body_reverse_node_state():
    hook_body = """
    import pbs
    e = pbs.event()
    pbs.logmsg(pbs.LOG_DEBUG, "pbs.__file__:" + pbs.__file__)
    # this is backwards as it's a reverse lookup.
    for value, key in pbs.REVERSE_NODE_STATE.items():
        pbs.logmsg(pbs.LOG_DEBUG, "key:%s value:%s" % (key, value))
    e.accept()
    """
    hook_body = textwrap.dedent(hook_body)
    return hook_body


class TestPbsModifyvnodeStateChanges(TestFunctional):

    """
    Test the modifyvnode hook by inducing various vnode state changes and
    inspecting the pbs log for expected values.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        Job.dflt_attributes[ATTR_k] = 'oe'

    def checkLog(self, start_time, mom, check_up, check_down):
        self.server.log_match("set_vnode_state;vnode.state=",
                              starttime=start_time)
        self.server.log_match("show_vnode_state;name=",
                              starttime=start_time)
        self.server.log_match("name: v=", starttime=start_time)
        self.server.log_match("state: v=", starttime=start_time)
        self.server.log_match("last_state_change_time: v=",
                              starttime=start_time)
        self.server.log_match("good times", starttime=start_time)
        self.server.log_match("good names", starttime=start_time)
        self.server.log_match("good states", starttime=start_time)
        self.server.log_match("good v sets", starttime=start_time)
        self.server.log_match("good v_o sets", starttime=start_time)
        if check_up:
            self.server.log_match("Node;%s;node up" % mom,
                                  starttime=start_time)
        if check_down:
            self.server.log_match("Node;%s;node down" % mom,
                                  starttime=start_time)

    def checkNodeFree(self, start_time):
        self.server.log_match("v.state_hex=0x0",
                              starttime=start_time)
        self.server.log_match("v.state_strs=ND_STATE_FREE",
                              starttime=start_time)
        self.server.log_match("v.state_ints=0",
                              starttime=start_time)

    def checkNodeDown(self, start_time):
        self.server.log_match("v.state_hex=0x2",
                              starttime=start_time)
        self.server.log_match(
            "v.state_strs=ND_STATE_DOWN,ND_STATE_VNODE_UNAVAILABLE",
            starttime=start_time)
        self.server.log_match("v.state_ints=2,409903",
                              starttime=start_time)

    def checkNodeOffline(self, start_time):
        self.server.log_match("v.state_hex=0x1",
                              starttime=start_time)
        self.server.log_match(
            "v.state_strs=ND_STATE_OFFLINE,ND_STATE_VNODE_UNAVAILABLE",
            starttime=start_time)
        self.server.log_match("v.state_ints=1,409903",
                              starttime=start_time)

    def checkNodeResvExclusive(self, start_time):
        self.server.log_match("v.state_hex=0x2000",
                              starttime=start_time)
        self.server.log_match("v.state_strs=ND_STATE_RESV_EXCLUSIVE",
                              starttime=start_time)
        self.server.log_match("v.state_ints=8192",
                              starttime=start_time)

    def checkpreviousStateChain(self, start_time, end_time, mom):
        # Check the state change entries for the specified mom
        search_string = ";show_vnode_state;name=" + mom
        self.logger.info(
            'checkpreviousStateChain search_string='+search_string+' start=' +
            str(start_time)+' end='+str(end_time))

        # Retrieve requested entries from the last 2000 lines of the server log
        lines = self.server.log_match(msg=search_string,
                                      allmatch=True,
                                      starttime=start_time,
                                      endtime=end_time,
                                      tail=True,
                                      n=2000)

        not_first = False
        previous_state = None
        previous_lsct = None
        for tupleline in lines:
            line = tupleline[1]
            head, tail = line.rsplit(';', 1)
            pairs = tail.split(' ')
            line_dict = dict([key_value.split("=", 1) for key_value in pairs])
            self.logger.debug('Examining line: ' + line)
            if not_first:
                # compare current "v_o" values with previous entry's "v" values
                self.assertEqual(
                    previous_state, line_dict['v_o.state_hex'],
                    'Node state chain mismatch! previous_state=%s line=%s' %
                    (previous_state, line))
                self.assertEqual(
                    previous_lsct, line_dict['v_o.lsct'],
                    'Node lsct chain mismatch! previous_lsct=%s line=%s' %
                    (previous_lsct, line))
                self.logger.debug('Current and previous matched!')
            else:
                not_first = True
                self.logger.debug('Setting not_first!')
            # current values become the previous values for the next iteration
            previous_state = line_dict['v.state_hex']
            previous_lsct = line_dict['v.lsct']

    def test_hook_state_changes_00(self):
        """
        Test: induce a variety of vnode state changes with debug turned on
        and inspect the pbs log for expected entries
        """
        if os.getuid() != 0 or sys.platform in ('cygwin', 'win32'):
            self.skipTest("Test need to run as root")

        self.logger.debug("---- %s TEST STARTED ----" % get_method_name(self))

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})
        attrs = {'event': 'modifyvnode', 'enabled': 'True', 'debug': 'True'}
        hook_name_00 = 'm1234'
        hook_body_00 = get_hook_body_modifyvnode_param_rpt()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertTrue(ret, "Could not create hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_00, hook_body_00)

        # print info about the test deployment
        self.logger.debug("socket.gethostname():%s" % socket.gethostname())
        self.logger.debug("***self.server.name:%s" % str(self.server.name))
        self.logger.debug("self.server.moms:%s" % str(self.server.moms))
        self.logger.debug("self.server.hostname=%s" % self.server.hostname)
        nodeinfo = self.server.status(NODE)

        # test effects of various state changes on each mom
        for mom in self.server.moms.values():
            # State change test: mom stop
            start_time = time.time()
            state_chain_start_time = start_time
            mom.stop()
            self.checkLog(start_time, mom.fqdn, check_up=False,
                          check_down=True)
            self.checkNodeDown(start_time)

            # State change test: mom start
            start_time = time.time()
            mom.start()
            self.checkLog(start_time, mom.fqdn, check_up=True,
                          check_down=False)
            self.checkNodeFree(start_time)

            # State change test: mom restart
            start_time = time.time()
            mom.restart()
            self.checkLog(start_time, mom.fqdn, check_up=True,
                          check_down=True)
            self.checkNodeDown(start_time)
            self.checkNodeFree(start_time)

            # State change test: take mom offline then online
            # take offline
            start_time = time.time()
            self.logger.debug("    ***offline mom:%s" % mom)
            self.server.manager(MGR_CMD_SET, NODE, {'state': (INCR,
                                'offline')},
                                id=mom.shortname)
            self.checkLog(start_time, mom.fqdn, check_up=False,
                          check_down=False)
            self.checkNodeOffline(start_time)
            # back online
            start_time = time.time()
            self.logger.debug("    ***online mom:%s" % mom)
            self.server.manager(MGR_CMD_SET, NODE, {'state': (DECR,
                                'offline')},
                                id=mom.shortname)
            self.checkLog(start_time, mom.fqdn, check_up=False,
                          check_down=False)
            self.checkNodeFree(start_time)

            # State change test: create and release maintenance reservation
            start_time = time.time()
            res_start_time = start_time + 15
            res_end_time = res_start_time + 1
            attrs = {
                'reserve_start': res_start_time,
                'reserve_end': res_end_time
            }
            self.logger.debug("    ***reserve & release mom:%s" % mom)
            rid = self.server.submit(Reservation(ROOT_USER, attrs,
                                     hosts=[mom.shortname]))
            self.logger.debug("rid=%s" % rid)
            self.checkLog(start_time, mom.fqdn, check_up=False,
                          check_down=False)
            self.checkNodeResvExclusive(start_time)
            self.checkNodeFree(start_time)

            # Verify each preceeding state matches the current previous state
            state_chain_end_time = time.time()
            self.checkpreviousStateChain(state_chain_start_time,
                                         state_chain_end_time,
                                         mom.shortname)

        self.logger.debug("---- %s TEST ENDED ----" % get_method_name(self))

    @tags('smoke')
    def test_check_node_state_constants_00(self):
        """
        Test: verify expected node state constants and associated reverse map
        are defined in the pbs module and contain the expected values.
        """
        self.logger.debug("---- %s TEST STARTED ----" % get_method_name(self))
        self.add_pbs_python_path_to_sys_path()
        import pbs
        self.assertEqual(
            len(pbs.REVERSE_NODE_STATE), len(node_states),
            "node state count mismatch: actual=%s, expected:%s" %
            (len(pbs.REVERSE_NODE_STATE), len(node_states)))
        for attr, value in node_states.items():
            self.logger.debug("checking attribute '%s' in pbs module", attr)
            self.assertTrue(
                hasattr(pbs, attr), "pbs.%s does not exist." % attr)
            self.assertEqual(
                getattr(pbs, attr), value,
                "pbs.%s is incorrect: actual=%s, expected=%s." %
                (attr, getattr(pbs, attr), value))
            self.assertIn(value, pbs.REVERSE_NODE_STATE)
            self.assertEqual(
                pbs.REVERSE_NODE_STATE[value], attr,
                ("pbs.REVERSE_NODE_STATE[%s] is incorrect: actual=%s, " +
                 "expected=%s.") % (value, pbs.REVERSE_NODE_STATE[value],
                                    attr))
        self.logger.debug("---- %s TEST ENDED ----" % get_method_name(self))

    def test_check_node_state_lookup_00(self):
        """
        Test: check for the existence and values of the
        pbs.REVERSE_STATE_CHANGES dictionary

        run a hook that converts a state change hex into a string, then search
        for it in the server log.
        """

        self.add_pbs_python_path_to_sys_path()
        import pbs
        self.logger.debug("---- %s TEST STARTED ----" % get_method_name(self))
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})
        attrs = {'event': 'modifyvnode', 'enabled': 'True', 'debug': 'True'}
        hook_name_00 = 'x1234'
        hook_body_00 = get_hook_body_reverse_node_state()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertTrue(ret, "Could not create hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_00, hook_body_00)
        for mom in self.server.moms.values():
            start_time = time.time()
            mom.restart()
            self.server.log_match("Node;%s;node up" % mom.fqdn,
                                  starttime=start_time)
            self.server.log_match("Node;%s;node down" % mom.fqdn,
                                  starttime=start_time)
            for value, key in pbs.REVERSE_NODE_STATE.items():
                self.server.log_match("key:%s value:%s" % (key, value),
                                      starttime=start_time)
        self.logger.debug("---- %s TEST ENDED ----" % get_method_name(self))

    @tags('smoke')
    def test_hook_state_changes_01(self):
        """
        Test each mom for state changes:
        1.  sigkill the mom; check server log for expected messages
        2.  start the mom; check server log for expected messages
        3.  verify the chain of reported current/previous states is unbroken
        """

        self.logger.debug("---- %s TEST STARTED ----" % get_method_name(self))

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})
        attrs = {'event': 'modifyvnode', 'enabled': 'True', 'debug': 'True'}
        hook_name_00 = 'p1234'
        hook_body_00 = get_hook_body_modifyvnode_param_rpt()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertTrue(ret, "Could not create hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_00, hook_body_00)

        for mom in self.server.moms.values():
            self.logger.debug("    ***sigkilling mom:%s", mom.fqdn)

            start_time = time.time()
            state_chain_start_time = start_time
            mom.signal('-KILL')
            self.checkLog(start_time, mom.fqdn, check_up=False,
                          check_down=True)
            self.checkNodeDown(start_time)

            start_time = time.time()
            mom.start()
            self.checkLog(start_time, mom.fqdn, check_up=True,
                          check_down=False)
            self.checkNodeFree(start_time)

            # Verify each preceeding state matches the current previous state
            state_chain_end_time = time.time()
            self.checkpreviousStateChain(state_chain_start_time,
                                         state_chain_end_time,
                                         mom.shortname)

        self.logger.debug("---- %s TEST ENDED ----" % get_method_name(self))

    def test_hook_state_changes_02(self):
        """
        Test:  stop and start the pbs server; look for proper log messages
        """

        self.logger.debug("---- %s TEST STARTED ----" % get_method_name(self))

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 4095})
        attrs = {'event': 'modifyvnode', 'enabled': 'True', 'debug': 'True'}
        hook_name_00 = 's1234'
        hook_body_00 = get_hook_body_modifyvnode_param_rpt()
        ret = self.server.create_hook(hook_name_00, attrs)
        self.assertTrue(ret, "Could not create hook %s" % hook_name_00)
        ret = self.server.import_hook(hook_name_00, hook_body_00)

        # stop the server and then start it
        start_time = time.time()
        state_chain_start_time = start_time
        self.server.stop()
        self.server.start()

        # look for messages indicating all the vnodes came up
        for mom in self.server.moms.values():
            self.checkLog(start_time, mom.fqdn, check_up=True,
                          check_down=False)
            self.checkNodeFree(start_time)
            # Verify each preceeding state matches the current previous state
            state_chain_end_time = time.time()
            self.checkpreviousStateChain(state_chain_start_time,
                                         state_chain_end_time,
                                         mom.shortname)

        self.logger.debug("---- %s TEST ENDED ----" % get_method_name(self))

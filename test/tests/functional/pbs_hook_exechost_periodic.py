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


common_periodic_hook_script = """import pbs
pbs.logmsg(pbs.LOG_DEBUG, "In exechost_periodic hook")
vn = pbs.event().vnode_list
host = pbs.get_local_nodename()
node = ''
for k in vn.keys():
    if host in k:
        node = k
        break
vn[node].resources_available["mem"] = pbs.size("90gb")
other_node = "invalid_node"
if other_node not in vn:
    vn[other_node] = pbs.vnode(other_node)
vn[other_node].resources_available["mem"] = pbs.size("9gb")
"""


class TestHookExechostPeriodic(TestFunctional):
    """
    Tests to test exechost_periodic hook
    """
    def setUp(self):
        TestFunctional.setUp(self)

    def test_multiple_exechost_periodic_hooks(self):
        """
        This test sets two exechost_periodic hooks and restarts the mom,
        which tests whether both the hooks will successfully run on node
        startup and the mom not crashes.
        """
        self.attr = {'event': 'exechost_periodic',
                     'enabled': 'True', 'freq': '30'}
        self.hook_body1 = ("import pbs\n"
                           "e = pbs.event()\n"
                           "pbs.logmsg(pbs.EVENT_DEBUG,\n"
                           "\t\"exechost_periodic hook1\")\n"
                           "e.accept()\n")
        self.hook_body2 = ("import pbs\n"
                           "e = pbs.event()\n"
                           "pbs.logmsg(pbs.EVENT_DEBUG,\n"
                           "\t\"exechost_periodic hook2\")\n"
                           "e.accept()\n")
        self.server.create_import_hook("exechost_periodic1",
                                       self.attr, self.hook_body1)
        self.server.create_import_hook("exechost_periodic2",
                                       self.attr, self.hook_body2)
        self.mom.restart()
        self.assertTrue(self.mom.isUp())
        self.mom.log_match("exechost_periodic hook1",
                           max_attempts=5, interval=5)
        self.mom.log_match("exechost_periodic hook2",
                           max_attempts=5, interval=5)

    @skipOnCpuSet
    @requirements(num_moms=2)
    def test_exechost_periodic_accept(self):
        """
        Test exechost_periodic which accepts event and verify that
        error is thrown when updating resources of a vnode
        which is owned by different mom
        """
        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname
        hook_name = "periodic"
        hook_attrs = {'event': 'exechost_periodic', 'enabled': 'True'}
        hook_body = common_periodic_hook_script
        self.server.create_import_hook(hook_name, hook_attrs, hook_body)

        exp_msg = "In exechost_periodic hook"
        for mom in self.moms.values():
            mom.log_match(exp_msg)

        other_node = "invalid_node"
        common_msg = " as it is owned by a different mom"
        common_msg2 = "resources_available.mem=9gb per mom hook request"

        exp_msg1 = "autocreated vnode %s" % (other_node)
        msg1 = "%s;Updated vnode %s's resource " % (self.momA.hostname,
                                                    other_node)
        exp_msg2 = msg1 + common_msg2
        msg2 = "%s;Not allowed to update vnode '%s'," % (self.momB.hostname,
                                                         other_node)
        exp_msg3 = msg2 + common_msg

        for msg in [exp_msg1, exp_msg2, exp_msg3]:
            self.server.log_match(msg)

        node_attribs = {'resources_available.mem': "90gb"}
        self.server.expect(NODE, node_attribs, id=self.momB.shortname)

    @skipOnCpuSet
    @requirements(num_moms=2)
    def test_exechost_periodic_alarm(self):
        """
        Test exechost_periodic with alarm timeout in hook script
        """
        hook_name = "periodic"
        hook_attrs = {'event': 'exechost_periodic', 'enabled': 'True',
                      'alarm': '5'}
        hook_script = """time.sleep(10)"""
        hook_body = """import time \n"""
        hook_body += common_periodic_hook_script + hook_script
        self.server.create_import_hook(hook_name, hook_attrs, hook_body)
        log_msg = "alarm call while running exechost_periodic hook"
        log_msg += " '%s', request rejected" % hook_name
        exp_msg = ["In exechost_periodic hook",
                   log_msg,
                   "Non-zero exit status 253 encountered for periodic hook",
                   "exechost_periodic request rejected by '%s'" % hook_name]
        for mom in self.moms.values():
            for msg in exp_msg:
                mom.log_match(msg)

    @skipOnCpuSet
    @requirements(num_moms=2)
    def test_exechost_periodic_error(self):
        """
        Test exechost_periodic with an unhandled exception in the hook script
        """
        hook_name = "periodic"
        hook_attrs = {'event': 'exechost_periodic', 'enabled': 'True'}
        hook_script = """raise Exception('x')"""
        hook_body = common_periodic_hook_script + hook_script
        self.server.create_import_hook(hook_name, hook_attrs, hook_body)

        common_msg = "PBS server internal error (15011) in "
        common_msg += "Error evaluating Python script"
        exp_msg = ["In exechost_periodic hook",
                   common_msg + ", <class 'Exception'>",
                   common_msg + ", x",
                   "Non-zero exit status 254 encountered for periodic hook",
                   "exechost_periodic request rejected by '%s'" % hook_name]
        for mom in self.moms.values():
            for msg in exp_msg:
                mom.log_match(msg)

    @skipOnCpuSet
    @requirements(num_moms=2)
    def test_exechost_periodic_custom_resc(self):
        """
        Test setting custom resource setting on vnode using exechost_periodic
        hook
        """
        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname
        hook_name = "periodic"
        hook_attrs = {'event': 'exechost_periodic', 'enabled': 'True'}
        hook_script = """vn[node].resources_available["foo"] = True"""
        hook_body = common_periodic_hook_script + hook_script
        self.server.create_import_hook(hook_name, hook_attrs, hook_body)
        node_attribs = {'resources_available.foo': True}
        self.server.expect(NODE, node_attribs, id=self.hostB)

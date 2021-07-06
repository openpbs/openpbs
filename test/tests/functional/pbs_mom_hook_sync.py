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


@requirements(num_moms=2)
class TestMomHookSync(TestFunctional):
    """
    This test suite tests to make sure a hook does not disappear in
    a series of hook event change from mom hook to server hook and
    then back to a mom hook. This is a good exercise to make sure
    hook updates are not lost even when mom is stopped, killed, and
    restarted during hook event changes.
    """

    def setUp(self):
        if len(self.moms) != 2:
            self.skip_test(reason="need 2 mom hosts: -p moms=<m1>:<m2>")
        TestFunctional.setUp(self)

        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.momA.delete_vnode_defs()
        self.momB.delete_vnode_defs()

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        rc = self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
        self.assertEqual(rc, 0)

        rc = self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostB)
        self.assertEqual(rc, 0)

        self.hook_name = "cpufreq"
        hook_body = "import pbs\n"
        a = {'event': 'execjob_begin', 'enabled': 'True'}
        self.server.create_import_hook(self.hook_name, a, hook_body)

        hook_config = """{
    "apple"         : "pears",
    "banana"         : "cucumbers"
}
"""
        fn = self.du.create_temp_file(body=hook_config)
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': fn}
        self.server.manager(MGR_CMD_IMPORT, HOOK, a, self.hook_name)
        os.remove(fn)

        self.server.log_match(
            'successfully sent hook file.*cpufreq.HK ' +
            'to %s.*' % self.momA.hostname,
            max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file.*cpufreq.CF ' +
            'to %s.*' % self.momA.hostname,
            max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file.*cpufreq.PY ' +
            'to %s.*' % self.momA.hostname,
            max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file.*cpufreq.HK ' +
            'to %s.*' % self.momB.hostname,
            max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file.*cpufreq.CF ' +
            'to %s.*' % self.momB.hostname,
            max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file.*cpufreq.PY ' +
            'to %s.*' % self.momB.hostname,
            max_attempts=10, regexp=True)

    def tearDown(self):
        self.momB.signal("-CONT")
        TestFunctional.tearDown(self)

    def test_momhook_to_serverhook_with_resume(self):
        """
        Given an existing mom hook, suspend mom on hostB,
        change the hook to be a server hook (causes a
        delete action), then change it back to a mom hook
        (results in a send action), and then resume mom.
        The delete action occurs first and then the send
        action so we end up with a mom hook in place.
        """

        self.momB.signal('-STOP')

        # Turn current mom hook into a server hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'queuejob'},
                            id=self.hook_name)

        # Turn current mom hook back to a mom hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'exechost_periodic'},
                            id=self.hook_name)

        # For testability, delay resuming the mom so we can
        # get a different timestamp on the hook updates
        self.logger.info("Waiting 3 secs for earlier hook updates to complete")
        time.sleep(3)

        now = time.time()
        self.momB.signal('-CONT')

        # Put another sleep delay so log_match() can see all the matches
        self.logger.info("Waiting 3 secs for new hook updates to complete")
        time.sleep(3)
        match_delete = self.server.log_match(
            'successfully deleted hook file cpufreq.HK ' +
            'from %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        # Without the fix, there won't be these sent hook file messages
        match_sent1 = self.server.log_match(
            'successfully sent hook file.*cpufreq.HK ' +
            'to %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        match_sent2 = self.server.log_match(
            'successfully sent hook file.*cpufreq.CF ' +
            'to %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        match_sent3 = self.server.log_match(
            'successfully sent hook file.*cpufreq.PY ' +
            'to %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        # Lower the linecount, earlier the line appears in log
        self.assertTrue(match_delete[0] < match_sent1[0])
        self.assertTrue(match_delete[0] < match_sent2[0])
        self.assertTrue(match_delete[0] < match_sent3[0])

    def test_momhook_to_momhook_with_resume(self):
        """
        Given an existing mom hook, suspend mom on hostB,
        change the hook event to be another mom hook event
        (results in a send action), change the hook to be a
        server hook (causes a delete action),
        and then resume mom.
        The send action occurs first and then the delete
        action so we end up with no mom hook in place.
        """

        self.momB.signal('-STOP')

        # Turn current mom hook back to a mom hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'exechost_periodic'},
                            id=self.hook_name)

        # Turn current mom hook into a server hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'queuejob'},
                            id=self.hook_name)

        # For testability, delay resuming the mom so we can
        # get a different timestamp on the hook updates
        self.logger.info("Waiting 3 secs for earlier hook updates to complete")
        time.sleep(3)

        now = time.time()
        self.momB.signal('-CONT')

        # Put another sleep delay so log_match() can see all the matches
        self.logger.info("Waiting 3 secs for new hook updates to complete")
        time.sleep(3)
        match_delete = self.server.log_match(
            'successfully deleted hook file cpufreq.HK ' +
            'from %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        # Only the hook control file (.HK) is sent since that contains
        # the hook event change to exechost_periodic.
        match_sent = self.server.log_match(
            'successfully sent hook file .*cpufreq.HK ' +
            'to %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        # Lower the linecount, earlier the line appears in log
        self.assertTrue(match_sent[0] < match_delete[0])

        self.server.log_match(
            'successfully sent hook file .*cpufreq.CF ' +
            'to %s.*' % self.momB.hostname, existence=False,
            starttime=now, max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file .*cpufreq.PY ' +
            'to %s.*' % self.momB.hostname, existence=False,
            starttime=now, max_attempts=10, regexp=True)

    def test_momhook_to_serverhook_with_restart(self):
        """
        Like test_1 except instead of resuming mom,
        we kill -9 it and restart.
        """

        self.momB.signal('-STOP')

        # Turn current mom hook into a server hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'queuejob'},
                            id=self.hook_name)

        # Turn current mom hook back to a mom hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'exechost_periodic'},
                            id=self.hook_name)

        # For testability, delay resuming the mom so we can
        # get a different timestamp on the hook updates
        self.logger.info("Waiting 3 secs for earlier hook updates to complete")
        time.sleep(3)

        now = time.time()
        self.momB.signal('-KILL')
        self.momB.start()

        # Killing and restarting mom would cause server to sync
        # up its version of the mom hook file resulting in an
        # additional send action, which would not alter the
        # outcome, as send action occurs after the delete action.
        self.server.log_match(
            'Node;%s.*;' % (self.momB.hostname,) +
            'Hello from MoM',
            starttime=now, max_attempts=10, regexp=True)

        # Put another sleep delay so log_match() can see all the matches
        self.logger.info("Waiting 3 secs for new hook updates to complete")
        time.sleep(3)
        match_delete = self.server.log_match(
            'successfully deleted hook file cpufreq.HK ' +
            'from %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        # Without the fix, there won't be these sent hook file messages
        match_sent1 = self.server.log_match(
            'successfully sent hook file.*cpufreq.HK ' +
            'to %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        match_sent2 = self.server.log_match(
            'successfully sent hook file.*cpufreq.CF ' +
            'to %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        match_sent3 = self.server.log_match(
            'successfully sent hook file.*cpufreq.PY ' +
            'to %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        # Lower the linecount, earlier the line appears in log
        self.assertTrue(match_delete[0] < match_sent1[0])
        self.assertTrue(match_delete[0] < match_sent2[0])
        self.assertTrue(match_delete[0] < match_sent3[0])

    def test_momhook_to_momhook_with_restart(self):
        """
        Like test_2 except instead of resuming mom,
        we kill -9 it and restart.
        """

        self.momB.signal('-STOP')

        # Turn current mom hook back to a mom hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'exechost_periodic'},
                            id=self.hook_name)

        # Turn current mom hook into a server hook
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'event': 'queuejob'},
                            id=self.hook_name)

        # For testability, delay resuming the mom so we can
        # get a different timestamp on the hook updates
        self.logger.info("Waiting 3 secs for earlier hook updates to complete")
        time.sleep(3)

        # Killing and restarting mom would cause server to sync
        # up its version of the mom hook file resulting in an
        # delete mom hook action as that hook is now seen as a
        # server hook. Since it's now a server hook, no further
        # mom hook sends are done.
        now = time.time()
        self.momB.signal('-KILL')
        self.momB.start()

        # Put another sleep delay so log_match() can see all the matches
        self.logger.info("Waiting 3 secs for new hook updates to complete")
        time.sleep(3)
        self.server.log_match(
            'successfully deleted hook file cpufreq.HK ' +
            'from %s.*' % self.momB.hostname,
            starttime=now, max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file .*cpufreq.HK ' +
            'to %s.*' % self.momB.hostname, existence=False,
            starttime=now, max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file .*cpufreq.CF ' +
            'to %s.*' % self.momB.hostname, existence=False,
            starttime=now, max_attempts=10, regexp=True)

        self.server.log_match(
            'successfully sent hook file .*cpufreq.PY ' +
            'to %s.*' % self.momB.hostname, existence=False,
            starttime=now, max_attempts=10, regexp=True)

    def compare_rescourcedef(self):
        srvret = None

        for _ in range(5):
            time.sleep(1)
            if srvret is None:
                file = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                    'server_priv', 'hooks', 'resourcedef')
                srvret = self.du.cat(self.server.hostname, file, logerr=False,
                                     sudo=True)
                if srvret['rc'] != 0 or len(srvret['out']) == 0:
                    srvret = None
                    continue

            file = self.momB.get_formed_path(self.momB.pbs_conf['PBS_HOME'],
                                             'mom_priv', 'hooks',
                                             'resourcedef')
            momret = self.momB.cat(file, logerr=False,
                                   sudo=True)
            if momret['rc'] != 0 or len(momret['out']) == 0:
                continue

            if momret['out'] == srvret['out']:
                return
            else:
                srvret = None
        raise self.failureException("resourcedef file is not in sync")

    def test_rescdef_mom_recreate(self):
        """
        test if rescdef file is recreated when a mom is deleted and added back
        """

        # create a custom resource
        self.server.manager(MGR_CMD_CREATE, RSC,
                            {'type': 'string', 'flag': 'h'}, id='foo')

        # compare rescdef files between mom and server
        self.compare_rescourcedef()

        # delete node
        self.server.manager(MGR_CMD_DELETE, NODE, id=self.momB.shortname)
        self.server.expect(NODE, 'state', id=self.momB.shortname, op=UNSET)

        # check if rescdef is deleted
        file = self.momB.get_formed_path(self.momB.pbs_conf['PBS_HOME'],
                                         'mom_priv', 'resourcedef')
        self.assertFalse(
            self.momB.du.isfile(self.momB.hostname, file, sudo=True),
            "resourcedef not deleted at mom")

        # recreate node
        self.server.manager(MGR_CMD_CREATE, NODE, id=self.momB.shortname)

        # check for status of the node
        self.server.expect(NODE, {'state': 'free'}, id=self.momB.shortname)

        # compare rescdef files between mom and server
        self.compare_rescourcedef()

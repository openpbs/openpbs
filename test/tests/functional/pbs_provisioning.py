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


import time
from tests.functional import *


hook_begin = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG,
"executed execjob_begin hook on job %s" % (pbs.event().job.id))
"""
hook_provision = """
import pbs
import time
e = pbs.event()
vnode = e.vnode
aoe = e.aoe
if aoe == 'App1':
    pbs.logmsg(pbs.LOG_DEBUG, "fake calling application provisioning script")
    e.accept(1)
pbs.logmsg(pbs.LOG_DEBUG, "aoe=%s,vnode=%s" % (aoe,vnode))
pbs.logmsg(pbs.LOG_DEBUG, "fake calling os provisioning script")
e.accept(0)
"""


@requirements(no_mom_on_server=True)
class TestProvisioningJob(TestFunctional):
    """
    This testsuite tests whether OS provisioned jobs are getting all
     required hook files at MOM

      PRE: Have a cluster of PBS with a MOM installed on other
             than PBS server host.

      1) Enable provisioning and set AOEs to the provisioning MOM
      2) Create Hooks
          i) Provisioning hook which is facking OS provisioning.
         ii) execjob_begin hook prints a log message on MOM node.
      3) Submit job with an aoe.
      4) Node will go into the provisioning state while it is
             running provisioning hook.
      5) Deletes execjob_begin hook file begin.PY from MOM
      6) Restarts MOM as we are not doing actual OS provisioning
      7) Then check for hook files are copied to the MOM node
             and job is printing log message from execjob_begin hook.
    """
    hook_list = ['begin', 'my_provisioning']
    hostA = ""

    def setUp(self):
        TestFunctional.setUp(self)
        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        msg = ("We cannot provision on cpuset mom, host has vnodes")
        if self.momA.is_cpuset_mom():
            self.skipTest(msg)
        self.momA.delete_vnode_defs()
        self.logger.info(self.momA.shortname)
        a = {'provision_enable': 'true'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostA)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})
        self.server.expect(NODE, {'state': 'free'}, id=self.hostA)

        a = {'event': 'execjob_begin', 'enabled': 'True'}
        rv = self.server.create_import_hook(
            self.hook_list[0], a, hook_begin, overwrite=True)
        self.assertTrue(rv)

        a = {'event': 'provision', 'enabled': 'True', 'alarm': '300'}
        rv = self.server.create_import_hook(
            self.hook_list[1], a, hook_provision, overwrite=True)
        self.assertTrue(rv)

    def test_execjob_begin_hook_on_os_provisioned_job(self):
        """
        Test the execjob_begin hook is seen by OS provisioned job.
        """
        a = {'resources_available.aoe': 'osimage1'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostA)

        job = Job(TEST_USER1, attrs={ATTR_l: 'aoe=osimage1'})
        job.set_sleep_time(1)
        jid = self.server.submit(job)

        rv = self.server.expect(NODE, {'state': 'provisioning'}, id=self.hostA)
        self.assertTrue(rv)

        phome = self.momA.pbs_conf['PBS_HOME']
        begin = self.momA.get_formed_path(phome, 'mom_priv', 'hooks',
                                          'begin.PY')
        ret = self.momA.rm(path=begin, force=True, sudo=True, logerr=False)
        if not ret:
            self.logger.error("problem deleting %s" % begin)
        self.momA.restart()
        time.sleep(5)
        rv = self.server.log_match(
            "successfully sent hook file "
            "/var/spool/pbs/server_priv/hooks/begin.PY",
            max_attempts=20,
            interval=1)
        self.assertTrue(rv)
        rv = self.mom.log_match("begin.PY;copy hook-related file "
                                "request received",
                                regexp=True,
                                max_attempts=20,
                                interval=1)
        self.assertTrue(rv)
        rv = self.mom.log_match("executed execjob_begin hook on job %s" % jid,
                                regexp=True,
                                max_attempts=20,
                                interval=1)
        self.assertTrue(rv)

    def test_app_provisioning(self):
        """
        Test application provisioning
        """
        a = {'resources_available.aoe': 'App1'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostA)

        job = Job(TEST_USER1, attrs={ATTR_l: 'aoe=App1'})
        jid = self.server.submit(job)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.log_match(
            "fake calling application provisioning script",
            max_attempts=20,
            interval=1)

    def test_os_provisioning_pending_hook_copy(self):
        """
        Test that job still runs after:
        1. os provisioning succeeded
        2. pending mom hook copy action has persisted on
           downed node that is not part of job
        """
        if len(self.moms) < 2:
            cmt = "need 2 non-server mom hosts: -p moms=<m1>:<m2>"
            self.skip_test(reason=cmt)
        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname
        msg = ("We cannot provision on cpuset mom, host has vnodes")
        if self.momA.is_cpuset_mom() or self.momB.is_cpuset_mom():
            self.skipTest(msg)
        a = {'resources_available.aoe': 'osimage1'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostA)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostB)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostA)

        job = Job(TEST_USER1, attrs={ATTR_l: 'aoe=osimage1'})
        job.set_sleep_time(30)
        jid = self.server.submit(job)
        self.server.expect(NODE, {'state': 'provisioning'}, id=self.hostA)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 71}, id=jid)
        self.server.log_match("fake calling os provisioning script")

        # Bring down the mom that is not part of the job
        self.momB.stop()
        # Force a server hook send of mom hooks
        # With momB being down, pending hook copy to momB action persists
        self.server.manager(MGR_CMD_SET, HOOK,
                            {'enabled': 'True'}, self.hook_list[0])

        # a restart is needed to complete os provisioning
        self.momA.restart()
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid)

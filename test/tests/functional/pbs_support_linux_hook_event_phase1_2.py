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
class TestSupportLinuxHookEventPhase1_2(TestFunctional):
    """
    Tests that cover support for Linux hook events in phase 1.2.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.pbs_attach = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                       'bin', 'pbs_attach')
        self.pbs_tmrsh = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                      'bin', 'pbs_tmrsh')

    def test_prologue_attach_order(self):
        """
        Check that the execjob_prologue and execjob_attach event types
        of a hook happen in the sister mom and mom superior.
        Check that execjob_prologue event happens before execjob_attach.
        """

        hook_body = """
import pbs
import time
e = pbs.event()
time.sleep(2)
if e.type == pbs.EXECJOB_PROLOGUE:
        pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_PROLOGUE"))
elif e.type == pbs.EXECJOB_ATTACH:
        pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_ATTACH"))
else:
        pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("UNKNOWN"))
"""

        a = {'event': 'execjob_prologue,execjob_attach', 'enabled': 'True'}
        self.server.create_import_hook("hook1", a, hook_body)

        self.momA = list(self.moms.values())[0]
        self.momB = list(self.moms.values())[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        if self.momA.is_cpuset_mom():
            self.hostA = self.hostA + '[0]'
        if self.momB.is_cpuset_mom():
            self.hostB = self.hostB + '[0]'

        # Job script
        test = []
        test += ['#PBS -l select=vnode=%s+vnode=%s\n' %
                 (self.hostA, self.hostB)]
        test += ['%s -j $PBS_JOBID %s 30\n' %
                 (self.pbs_attach, self.mom.sleep_cmd)]
        test += ['%s %s %s %s 30\n' %
                 (self.pbs_tmrsh, self.momB.hostname, self.pbs_attach,
                  self.mom.sleep_cmd)]

        # Submit a job
        j = Job(TEST_USER)
        j.create_script(body=test)
        check_after1 = time.time()
        check_after2 = check_after1 + 2
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # Check mom logs
        msg_expected = "event is EXECJOB_PROLOGUE"
        s = self.momA.log_match(msg_expected, starttime=check_after1,
                                max_attempts=10)
        self.assertTrue(s)
        s = self.momB.log_match(msg_expected, starttime=check_after1,
                                max_attempts=10)
        self.assertTrue(s)

        msg_expected = "event is EXECJOB_ATTACH"
        s = self.momA.log_match(msg_expected, starttime=check_after2,
                                max_attempts=10)
        self.assertTrue(s)
        # Allow time for log message to appear before checking on sister mom
        time.sleep(31)
        s = self.momB.log_match(msg_expected, starttime=check_after2,
                                max_attempts=10)
        self.assertTrue(s)

    def test_execjob_attach_hook_with_accept(self):
        """
        Check that the execjob_attach event type with accept
        of a hook happen in the sister mom and mom superior;
        execjob_attach hook returns process id, job and vnode list.
        """

        hook_body = """
import pbs
import os
import sys
import time

e = pbs.event()
pbs.logmsg(pbs.LOG_DEBUG,
           "printing pbs.event() values ---------------------->")
if e.type == pbs.EXECJOB_ATTACH:
   pbs.logmsg(pbs.LOG_DEBUG, "Event is: %s" % ("EXECJOB_ATTACH"))
else:
   pbs.logmsg(pbs.LOG_DEBUG, "Event is: %s" % ("UNKNOWN"))

pbs.logmsg(pbs.LOG_DEBUG, "Requestor is: %s" % (e.requestor))
pbs.logmsg(pbs.LOG_DEBUG, "Requestor_host is: %s" % (e.requestor_host))

# Getting/setting vnode_list
vn = pbs.event().vnode_list

for k in vn.keys():
   pbs.logmsg(pbs.LOG_DEBUG, "Vnode: [%s]-------------->" % (k))

pbs.logjobmsg(e.job.id, "PID = %d, type = %s" % (e.pid, type(e.pid)))

if e.job.in_ms_mom():
        pbs.logmsg(pbs.LOG_DEBUG, "job is in_ms_mom")
else:
        pbs.logmsg(pbs.LOG_DEBUG, "job is NOT in_ms_mom")

e.accept()
"""

        a = {'event': 'execjob_attach', 'enabled': 'True'}
        self.server.create_import_hook("hook1", a, hook_body)

        self.momA = list(self.moms.values())[0]
        self.momB = list(self.moms.values())[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        if self.momA.is_cpuset_mom():
            self.hostA = self.hostA + '[0]'
        if self.momB.is_cpuset_mom():
            self.hostB = self.hostB + '[0]'

        # Job script
        test = []
        test += ['#PBS -l select=vnode=%s+vnode=%s\n' %
                 (self.hostA, self.hostB)]
        test += ['%s -j $PBS_JOBID %s 30\n' %
                 (self.pbs_attach, self.mom.sleep_cmd)]
        test += ['%s %s %s %s 30\n' %
                 (self.pbs_tmrsh, self.momB.hostname, self.pbs_attach,
                  self.mom.sleep_cmd)]

        # Submit a job
        j = Job(TEST_USER)
        j.create_script(body=test)
        check_after = time.time()
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # Allow time for log messages to appear before checking mom logs
        time.sleep(31)

        # Check log msgs on sister mom
        log_msgB = [
            "Hook;pbs_python;printing pbs.event() values " +
            "---------------------->",
            "Hook;pbs_python;Event is: EXECJOB_ATTACH",
            "Hook;pbs_python;Requestor is: pbs_mom",
            "Hook;pbs_python;Requestor_host is: %s" %
            self.momB.shortname,
            "Hook;pbs_python;Vnode: [%s]-------------->" %
            self.hostA,
            "Hook;pbs_python;Vnode: [%s]-------------->" %
            self.hostB,
            "pbs_python;Job;%s;PID =" %
            jid,
            "Hook;pbs_python;job is NOT in_ms_mom"]

        for msg in log_msgB:
            rc = self.momB.log_match(msg, starttime=check_after,
                                     max_attempts=10)
            _msg = "Didn't get expected log msg: %s " % msg
            _msg += "on host:%s" % self.hostB
            self.assertTrue(rc, _msg)
            _msg = "Got expected log msg: %s on host: %s" % (msg, self.hostB)
            self.logger.info(_msg)

        # Check log msgs on mom superior
        log_msgA = ["Hook;pbs_python;printing pbs.event() values " +
                    "---------------------->",
                    "Hook;pbs_python;Event is: EXECJOB_ATTACH",
                    "Hook;pbs_python;Requestor is: pbs_mom",
                    "Hook;pbs_python;Requestor_host is: %s" %
                    self.momA.shortname,
                    "Hook;pbs_python;Vnode: [%s]-------------->" % self.hostA,
                    "Job;%s;PID =" % jid,
                    "Hook;pbs_python;Vnode: [%s]-------------->" % self.hostB,
                    "Hook;pbs_python;job is in_ms_mom"]

        for msg in log_msgA:
            rc = self.momA.log_match(msg, starttime=check_after,
                                     max_attempts=10)
            _msg = "Didn't get expected log msg: %s " % msg
            _msg += "on host:%s" % self.hostA
            self.assertTrue(rc, _msg)
            _msg = "Got expected log msg: %s on host: %s" % (msg, self.hostA)
            self.logger.info(_msg)

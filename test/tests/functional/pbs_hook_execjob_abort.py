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

import time
from tests.functional import *
from ptl.utils.pbs_logutils import PBSLogUtils


class TestPbsExecjobAbort(TestFunctional):
    """
    Tests the hook event execjob_abort for when a job prematurely exits
    during startup and the epilogue hook or end hook may not always execute.
    """
    logutils = PBSLogUtils()

    def setUp(self):
        if len(self.moms) != 3:
            self.skipTest('test requires three MoMs as input, ' +
                          'use -p moms=<mom1>:<mom2>:<mom3>')
        TestFunctional.setUp(self)
        self.momC = self.moms.values()[2]

        # execjob_abort hook
        self.abort_hook_body = """import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "called execjob_abort hook")

def print_attribs(pbs_obj, header):
    for a in pbs_obj.attributes:
        v = getattr(pbs_obj, a)
        if v and str(v) != "":
            pbs.logmsg(pbs.LOG_DEBUG, "%s: %s = %s" % (header, a, v))
print_attribs(e.job, "JOB")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    print_attribs(v, "vnode_list[" + vn + "]")
"""
        # instantiate execjob_abort hook
        hook_event = 'execjob_abort'
        hook_name = 'abort'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.abort_hook_body)

        # execjob_abort hook with sleep
        self.abort1_hook_body = """import pbs
import time
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "called execjob_abort hook")
time.sleep(2)
"""
        # execjob_prologue hook, unhandled exception
        self.prolo_hook_body = """import pbs
e=pbs.event()
job=e.job
if %s job.in_ms_mom():
    raise NameError
"""
        # execjob_launch hook, unhandled exception on MS mom
        self.launch_hook_body = """import pbs
e=pbs.event()
job=e.job
if job.in_ms_mom():
    raise NameError
"""
        # execjob_end hook
        self.end_hook_body = """import pbs
e=pbs.event()
e.reject("end hook rejected")
"""
        # execjob_begin hook with sleep
        self.begin_hook_body = """import pbs
import time
e=pbs.event()
e.job.delete()
pbs.logmsg(pbs.LOG_DEBUG, "called execjob_begin hook with job.delete()")
time.sleep(2)
"""
        # job used in the tests
        a = {ATTR_l + '.select': '3:ncpus=1', ATTR_l + '.place': 'scatter'}
        self.j = Job(self.du.get_current_user(), attrs=a)

    def test_execjob_abort_ms_prologue(self):
        """
        An execjob_abort hook is executed in the primary mom and then in the
        connected sister moms when a job has problems starting up and needing
        to be aborted because execjob_prologue hook rejected in the
        primary mom. Job is requeued, gets held (H state).
        """
        # instantiate execjob_prologue hook to run on MS mom
        hook_event = 'execjob_prologue'
        hook_name = 'prolo'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.prolo_hook_body % (''))
        # Submit a job that eventually goes in H state
        start_time = int(time.time())
        jid = self.server.submit(self.j)
        msg = "Job;%s;Job requeued, execution node  down" % jid
        self.server.log_match(msg, starttime=start_time)
        # Check for abort hook message in each of the moms
        msg = "called execjob_abort hook"
        for mom in self.moms.values():
            mom.log_match(msg, starttime=start_time)
        self.server.expect(JOB, {ATTR_state: 'H'}, id=jid, offset=7)

    def test_execjob_abort_exit_job_launch_reject(self):
        """
        An execjob_abort hook is executed in the primary mom and then in the
        connected sister moms when a job has problems starting up and needing
        to be aborted because execjob_launch hook rejected in the
        primary mom. Job exits.
        """
        # instantiate execjob_launch hook to run on primary moms
        hook_event = 'execjob_launch'
        hook_name = 'launch'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.launch_hook_body)
        # Submit a job
        start_time = int(time.time())
        jid = self.server.submit(self.j)
        self.server.expect(JOB, 'exec_host', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        exechost = job_stat[0]['exec_host'].split('/')[0]
        mom_superior = self.moms[exechost]
        msg = "Job;%s;execjob_launch hook 'launch' " % (
            jid) + "encountered an exception, request rejected"
        mom_superior.log_match(msg, starttime=start_time)
        # Check for abort hook message in each of the moms
        msg = "called execjob_abort hook"
        for mom in self.moms.values():
            mom.log_match(msg, starttime=start_time)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=1)

    def msg_order(self, node, msg1, msg2, stime):
        """
        Checks if msg1 appears after stime, and msg1 appears before msg2 in
        mom logs of node. Returns date and time when msg1 and msg2 appeared.
        """
        # msg1 appears before msg2
        (_, str1) = node.log_match(msg1, starttime=stime)
        date_time1 = str1.split(";")[0]
        epoch1 = self.logutils.convert_date_time(date_time1)
        # Use epoch1 to mark the starttime of msg2
        (_, str2) = node.log_match(msg2, starttime=epoch1)
        date_time2 = str2.split(";")[0]
        return (date_time1, date_time2)

    def test_execjob_abort_sis_joinjob_requeue(self):
        """
        An execjob_abort hook is executed on a sister mom when a sister mom
        fails to join job. On connected primary mom an execjob_abort hook is
        executed first then execjob_end hook. On connected mom only an
        execjob_abort hook is executed. Job gets requeued.
        """
        # instantiate execjob_abort hook with sleep
        hook_event = 'execjob_abort'
        hook_name = 'abort'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.abort1_hook_body)
        # instantiate execjob_end hook
        hook_event = 'execjob_end'
        hook_name = 'end'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.end_hook_body)

        # Simulate a sister failure to join job
        # kill -STOP momC, submit a multi-node job, kill -9 momC
        self.momC.signal("-STOP")
        stime = int(time.time())
        jid = self.server.submit(self.j)
        self.server.expect(JOB, 'exec_host', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        exechost = job_stat[0]['exec_host'].split('/')[0]
        pri_mom = self.moms[exechost]
        self.momC.signal("-KILL")
        msg = "Job;%s;job_start_error.+from node %s " % (
            jid, self.momC.hostname) + "could not JOIN_JOB successfully"
        msg_abort = "called execjob_abort hook"
        msg_end = "end hook rejected"

        # momC failed to join job
        pri_mom.log_match(msg, starttime=stime, regexp=True)
        # abort hook executed before end hook on primary mom
        (dt1, dt2) = self.msg_order(pri_mom, msg_abort, msg_end, stime)
        self.logger.info(
            "\n%s: abort hook executed at: %s"
            "\n%s: end   hook executed at: %s" %
            (pri_mom.shortname, dt1, pri_mom.shortname, dt2))
        # only abort hook executed on connected sister mom
        for mom in self.moms.values():
            if mom != pri_mom and mom != self.momC:
                mom.log_match(msg_abort, starttime=stime)
                mom.log_match(
                    msg_end, starttime=stime, max_attempts=10,
                    interval=2, existence=False)
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid, offset=1)

    def test_execjob_abort_sis_joinjob_exit(self):
        """
        An execjob_abort hook is executed on a sister mom when a sister mom
        fails to join job. An execjob_begin hook which instructs the job to
        be deleted via the pbs.event().job.delete() call executes before the
        execjob_abort hook. Job exits.
        """
        # instantiate execjob_begin hook
        hook_event = 'execjob_begin'
        hook_name = 'begin'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.begin_hook_body)

        # Simulate a sister failure to join job
        # kill -STOP momC, submit a multi-node job, kill -9 momC
        self.momC.signal("-STOP")
        stime = int(time.time())
        jid = self.server.submit(self.j)
        self.server.expect(JOB, 'exec_host', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        exechost = job_stat[0]['exec_host'].split('/')[0]
        pri_mom = self.moms[exechost]
        self.momC.signal("-KILL")

        msg = "Job;%s;job_start_error.+from node %s " % (
            jid, self.momC.hostname) + "could not JOIN_JOB successfully"
        msg_begin = "called execjob_begin hook with job.delete()"
        msg_abort = "called execjob_abort hook"

        # momC failed to join job
        pri_mom.log_match(msg, starttime=stime, regexp=True)
        # begin hook executed before abort hook on connected sister mom
        for mom in self.moms.values():
            if mom != pri_mom and mom != self.momC:
                (dt1, dt2) = self.msg_order(
                    pri_mom, msg_begin, msg_abort, stime)
                self.logger.info(
                    "\n%s: begin hook executed at: %s"
                    "\n%s: abort hook executed at: %s" %
                    (mom.shortname, dt1, mom.shortname, dt2))
        # begin hook executed before abort hook executed on primary mom
        (dt1, dt2) = self.msg_order(pri_mom, msg_begin, msg_abort, stime)
        self.logger.info(
            "\n%s: begin hook executed at: %s"
            "\n%s: abort hook executed at: %s" %
            (pri_mom.shortname, dt1, pri_mom.shortname, dt2))
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=1)

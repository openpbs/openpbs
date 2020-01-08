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
from tests.functional import *
from ptl.utils.pbs_logutils import PBSLogUtils


@requirements(num_moms=2)
class TestPbsExecjobSuspendResume(TestFunctional):
    """
    Tests the hook events execjob_postsuspend, execjob_preresume which are
    called after a job is suspended, and before the job is resumed.
    """
    logutils = PBSLogUtils()

    def setUp(self):
        if len(self.moms) != 2:
            self.skipTest('test requires two MoMs as input, ' +
                          'use -p moms=<mom1>:<mom2>')
        TestFunctional.setUp(self)
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]

        # execjob_postsuspend hook
        self.postsuspend_hook_body = """import pbs
e=pbs.event()

def proc_status(pid):
    try:
        for line in open("/proc/%d/status" % pid).readlines():
            if line.startswith("State:"):
                return line.split(":",1)[1].strip().split(' ')[0]
    except:
        pass
    return None

def print_attribs(pbs_obj, header):
    for a in pbs_obj.attributes:
        v = getattr(pbs_obj, a)
        if v and str(v):
            pbs.logjobmsg(e.job.id, "%s: %s = %s" % (header, a, v))
            if a == "session_id":
                st = proc_status(v)
                if st == 'T':
                    pbs.logjobmsg(e.job.id,
                                  "%s: process seen as suspended" % header)

if e.type == pbs.EXECJOB_POSTSUSPEND:
    pbs.logmsg(pbs.LOG_DEBUG, "called execjob_postsuspend hook")
print_attribs(e.job, "JOB")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    print_attribs(v, "vnode_list[" + vn + "]")
"""
        # execjob_postsuspend hook, reject
        self.postsuspend_hook_reject_body = """import pbs
e=pbs.event()
job=e.job
e.reject("bad suspend on ms")
"""
        # execjob_postsuspend hook, reject by sister only
        self.postsuspend_hook_sis_reject_body = """import pbs
e=pbs.event()
job=e.job
if not e.job.in_ms_mom():
    e.reject("bad suspend on sis")
"""
        # hook with an unhandled exception
        self.hook_error_body = """import pbs
e=pbs.event()
job=e.job
raise NameError
"""
        # hook with an unhandled exception, sister only
        self.hook_sis_error_body = """import pbs
e=pbs.event()
job=e.job
if not job.in_ms_mom():
    raise NameError
"""

        # execjob_preresume hook
        self.preresume_hook_body = """import pbs
e=pbs.event()

def proc_status(pid):
    try:
        for line in open("/proc/%d/status" % pid).readlines():
            if line.startswith("State:"):
                return line.split(":",1)[1].strip().split(' ')[0]
    except:
        pass
    return None

def print_attribs(pbs_obj, header):
    for a in pbs_obj.attributes:
        v = getattr(pbs_obj, a)
        if v and str(v):
            pbs.logjobmsg(e.job.id, "%s: %s = %s" % (header, a, v))
            if a == "session_id":
                st = proc_status(v)
                if st == 'T':
                    pbs.logjobmsg(e.job.id,
                                  "%s: process seen as suspended" % header)

if e.type == pbs.EXECJOB_PRERESUME:
    pbs.logmsg(pbs.LOG_DEBUG, "called execjob_preresume hook")

print_attribs(e.job, "JOB")

for vn in e.vnode_list:
    v = e.vnode_list[vn]
    print_attribs(v, "vnode_list[" + vn + "]")
"""
        # execjob_preresume hook, reject
        self.preresume_hook_reject_body = """import pbs
e=pbs.event()
job=e.job
e.reject("bad resumption on ms")
"""
        # execjob_preresume hook, reject by sister only
        self.preresume_hook_sis_reject_body = """import pbs
e=pbs.event()
job=e.job
if not e.job.in_ms_mom():
    e.reject("bad resumption on sis")
"""
        # job used in the tests
        self.j = Job(self.du.get_current_user())

        script = """
#PBS -l select=2:ncpus=1
#PBS -l place=scatter
#PBS -S /bin/bash
pbsdsh -n 1 -- sleep 60 &
sleep 60
"""
        self.j.create_script(script)

    def test_execjob_postsuspend(self):
        """
        An execjob_postsuspend hook is executed by primary mom and then by
        the connected sister moms after a job has been suspended.
        """
        # instantiate execjob_postsuspend hook
        hook_event = 'execjob_postsuspend'
        hook_name = 'psus'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.postsuspend_hook_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend job
        self.server.sigjob(jobid=jid, signal="suspend")

        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with suspend", starttime=stime)
            else:
                vn.log_match("SUSPEND received", starttime=stime)

            vn.log_match("called execjob_postsuspend hook", starttime=stime)
            if vn == self.momA:
                # as postsuspend hook is executing,
                # job's process should be seen as suspended
                vn.log_match("Job;%s;JOB: process seen as suspended" % jid,
                             starttime=stime)

            # Check presence of pbs.event().job
            vn.log_match("Job;%s;JOB: id = %s" % (jid, jid), starttime=stime)

            # Check presence of vnode_list[] parameter
            vnode_list = [self.momA.name, self.momB.name]
            for v in vnode_list:
                vn.log_match("Job;%s;vnode_list[%s]: name = %s" % (
                             jid, v, v), starttime=stime)

        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_preresume(self):
        """
        An execjob_preresume hook is executed by primary mom and then by
        the connected sister moms just before a job is resumed.
        """
        # instantiate execjob_preresume hook
        hook_event = 'execjob_preresume'
        hook_name = 'pres'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.preresume_hook_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend, then resume job
        self.server.sigjob(jobid=jid, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
        self.server.sigjob(jobid=jid, signal="resume")

        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with resume", starttime=stime)
            else:
                vn.log_match("RESUME received", starttime=stime)

            vn.log_match("called execjob_preresume hook", starttime=stime)
            if vn == self.momA:
                # as preresume hook is executing,
                # job's process should be seen as suspended
                vn.log_match("Job;%s;JOB: process seen as suspended" % jid,
                             starttime=stime)
            # Check presence of pbs.event().job
            vn.log_match("Job;%s;JOB: id = %s" % (jid, jid), starttime=stime)

            # Check presence of vnode_list[] parameter
            vnode_list = [self.momA.name, self.momB.name]
            for v in vnode_list:
                vn.log_match("Job;%s;vnode_list[%s]: name = %s" % (
                             jid, v, v), starttime=stime)

        # after hook executes, job should be running again.
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

    def test_execjob_postsuspend_reject(self):
        """
        An execjob_postsuspend hook that results in a reject action
        would not affect the currently suspended job.
        """
        # instantiate execjob_postsuspend hook
        hook_event = 'execjob_postsuspend'
        hook_name = 'psus'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.postsuspend_hook_reject_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend job
        self.server.sigjob(jobid=jid, signal="suspend")

        hook_msg = "bad suspend on ms"
        reject_msg = "%s hook rejected request: %s" % (hook_event, hook_msg)
        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with suspend", starttime=stime)
            else:
                vn.log_match("SUSPEND received", starttime=stime)

            vn.log_match("Job;%s;%s" % (jid, hook_msg), starttime=stime)
            vn.log_match("Job;%s;%s" % (jid, reject_msg), starttime=stime)

        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_postsuspend_reject_sis(self):
        """
        An execjob_postsuspend hook that results in a reject action
        by sister mom only would not affect the currently suspended
        job.
        """
        # instantiate execjob_postsuspend hook
        hook_event = 'execjob_postsuspend'
        hook_name = 'psus'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.postsuspend_hook_sis_reject_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend job
        self.server.sigjob(jobid=jid, signal="suspend")

        hook_msg = "bad suspend on sis"
        reject_msg = "%s hook rejected request: %s" % (hook_event, hook_msg)
        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with suspend", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, hook_msg),
                             starttime=stime, existence=False, max_attempts=30)
                vn.log_match("Job;%s;%s" % (jid, reject_msg),
                             starttime=stime, existence=False, max_attempts=30)
            else:
                vn.log_match("SUSPEND received", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, hook_msg), starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, reject_msg), starttime=stime)

        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_postsuspend_error(self):
        """
        An execjob_postsuspend hook that results in an error action
        would not affect the currently suspended job.
        """
        # instantiate execjob_postsuspend hook
        hook_event = 'execjob_postsuspend'
        hook_name = 'psus'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.hook_error_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend job
        self.server.sigjob(jobid=jid, signal="suspend")

        error_msg = \
            "%s hook \'%s\' encountered an exception, request rejected" \
            % (hook_event, hook_name)

        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with suspend", starttime=stime)
            else:
                vn.log_match("SUSPEND received", starttime=stime)

            vn.log_match("Job;%s;%s" % (jid, error_msg), starttime=stime)

        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_postsuspend_error_sis(self):
        """
        An execjob_postsuspend hook that results in a error action
        by sister mom only would not affect the currently suspended
        job.
        """
        # instantiate execjob_postsuspend hook
        hook_event = 'execjob_postsuspend'
        hook_name = 'psus'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.hook_sis_error_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend job
        self.server.sigjob(jobid=jid, signal="suspend")

        error_msg = \
            "%s hook \'%s\' encountered an exception, request rejected" \
            % (hook_event, hook_name)

        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with suspend", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, error_msg),
                             starttime=stime, existence=False, max_attempts=30)
            else:
                vn.log_match("SUSPEND received", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, error_msg), starttime=stime)

        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_preresume_reject(self):
        """
        An execjob_preresume hook that results in a reject action
        would prevent suspended job from being resumed.
        """
        # instantiate execjob_preresume hook
        hook_event = 'execjob_preresume'
        hook_name = 'pres'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.preresume_hook_reject_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend, then resume job
        self.server.sigjob(jobid=jid, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
        self.server.sigjob(jobid=jid, signal="resume")

        hook_msg = "bad resumption on ms"
        reject_msg = "%s hook rejected request: %s" % (hook_event, hook_msg)
        # Mom hook executes on momA and gets a rejection,
        # so a resume request is not sent to sister momB.
        self.momA.log_match("signal job with resume", starttime=stime)
        self.momA.log_match("Job;%s;%s" % (jid, hook_msg), starttime=stime)
        self.momA.log_match("Job;%s;%s" % (jid, reject_msg), starttime=stime)
        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_preresume_reject_sis(self):
        """
        An execjob_preresume hook that results in a reject action
        by sister mom only would not affect the currently suspended
        job.
        """
        # instantiate execjob_preresume hook
        hook_event = 'execjob_preresume'
        hook_name = 'psus'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.preresume_hook_sis_reject_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend, then resume job
        self.server.sigjob(jobid=jid, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
        self.server.sigjob(jobid=jid, signal="resume")

        hook_msg = "bad resumption on sis"
        reject_msg = "%s hook rejected request: %s" % (hook_event, hook_msg)
        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with resume", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, hook_msg),
                             starttime=stime, existence=False, max_attempts=30)
                vn.log_match("Job;%s;%s" % (jid, reject_msg),
                             starttime=stime, existence=False, max_attempts=30)
            else:
                vn.log_match("RESUME received", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, hook_msg), starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, reject_msg), starttime=stime)

        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_preresume_error(self):
        """
        An execjob_preresume hook that results in a error action
        would prevent suspended job from being resumed.
        """
        # instantiate execjob_preresume hook
        hook_event = 'execjob_preresume'
        hook_name = 'pres'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.hook_error_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend, then resume job
        self.server.sigjob(jobid=jid, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
        self.server.sigjob(jobid=jid, signal="resume")

        error_msg = \
            "%s hook \'%s\' encountered an exception, request rejected" \
            % (hook_event, hook_name)

        # Mom hook executes on momA and gets a errorion,
        # so a resume request is not sent to sister momB.
        self.momA.log_match("signal job with resume", starttime=stime)
        self.momA.log_match("Job;%s;%s" % (jid, error_msg), starttime=stime)
        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

    def test_execjob_preresume_error_sis(self):
        """
        An execjob_preresume hook that results in a error action
        by sister mom only would not affect the currently suspended
        job.
        """
        # instantiate execjob_preresume hook
        hook_event = 'execjob_preresume'
        hook_name = 'psus'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.hook_sis_error_body)

        # Submit a job
        jid = self.server.submit(self.j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        stime = int(time.time())
        # Suspend, then resume job
        self.server.sigjob(jobid=jid, signal="suspend")
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)
        self.server.sigjob(jobid=jid, signal="resume")

        error_msg = \
            "%s hook \'%s\' encountered an exception, request rejected" \
            % (hook_event, hook_name)

        for vn in [self.momA, self.momB]:
            if vn == self.momA:
                vn.log_match("signal job with resume", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, error_msg),
                             starttime=stime, existence=False, max_attempts=30)
            else:
                vn.log_match("RESUME received", starttime=stime)
                vn.log_match("Job;%s;%s" % (jid, error_msg), starttime=stime)

        # after hook executes, job continues to be suspended
        self.server.expect(JOB, {ATTR_state: 'S'}, id=jid)

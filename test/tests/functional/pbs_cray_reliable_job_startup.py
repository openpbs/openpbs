# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
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
import fnmatch
from tests.functional import *
from ptl.utils.pbs_logutils import PBSLogUtils


@tags('cray')
class TestPbsReliableJobStartupOnCray(TestFunctional):

    """
    This tests the Reliable Job Startup Feature on Cray.
    A job can be started with extra nodes with node failures tolerated
    during job start but setting is not supported and ignored on Cray.
    """

    def setUp(self):
        if not self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on a Cray")
        TestFunctional.setUp(self)

        # queuejob hook
        self.qjob_hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "queuejob hook executed")
# Save current select spec in resource 'site'
e.job.Resource_List["site"] = str(e.job.Resource_List["select"])
new_select = e.job.Resource_List["select"].increment_chunks(1)
e.job.Resource_List["select"] = new_select
e.job.tolerate_node_failures = "job_start"
"""

        # prologue hook
        self.prolo_hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing prologue")
# print out the vnode_list[] values
for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "prologue: found vnode_list[" + v.name + "]")
# print out the vnode_list_fail[] values
for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "prologue: found vnode_list_fail[" + v.name + "]")
if e.job.in_ms_mom():
    pj = e.job.release_nodes(keep_select=e.job.Resource_List["site"])
    if pj is None:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at PROLOGUE")
"""

        # launch hook
        self.launch_hook_body = """
import pbs
e=pbs.event()
if 'PBS_NODEFILE' not in e.env:
    e.accept()
pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")
# print out the vnode_list[] values
for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")
# print out the vnode_list_fail[] values:
for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
    v.state = pbs.ND_OFFLINE
if e.job.in_ms_mom():
    pj = e.job.release_nodes(keep_select=e.job.Resource_List["site"])
    if pj is None:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at LAUNCH")
"""

    def match_str_in_input_file(self, file_path, file_pattern, search_str):
        """
        Assert that search string appears in the input file
        that matches file_pattern
        """
        input_file = None
        for item in self.du.listdir(path=file_path, sudo=True):
            if fnmatch.fnmatch(item, file_pattern):
                input_file = item
                break
        self.assertTrue(input_file is not None)
        with PBSLogUtils().open_log(input_file, sudo=True) as f:
            self.assertTrue(search_str in f.read())
            self.logger.info("Found \"%s\" in %s" % (search_str, input_file))

    @tags('cray')
    def test_reliable_job_startup_not_supported_on_cray(self):
        """
        A job is started with extra nodes. Mom superior will show no sign
        of tolerating node failure.  Accounting logs won't have 's' record.
        Input files to prologue and launch hooks will show the
        tolerate_node_failures=none value.
        """
        # instantiate queuejob hook
        hook_event = 'queuejob'
        hook_name = 'qjob'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)

        # instantiate execjob_prologue hook
        hook_event = 'execjob_prologue'
        hook_name = 'prolo'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.prolo_hook_body)

        # instantiate execjob_launch hook
        hook_event = 'execjob_launch'
        hook_name = 'launch'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.launch_hook_body)

        # Submit a job
        j = Job(TEST_USER, {ATTR_l + '.select': '1:ncpus=3:mem=2gb:vntype=' +
                            'cray_compute+1:ncpus=3:mem=2gb:vntype=' +
                            'cray_compute',
                            ATTR_l + '.place': 'scatter'})
        start_time = int(time.time())
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # Check for msg in mom superior logs
        msg = "no nodes released as job does not tolerate node failures"
        self.server.expect(JOB, 'exec_host', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        exechost = job_stat[0]['exec_host'].partition('/')[0]
        mom_superior = self.moms[exechost]
        mom_superior.log_match(msg, starttime=start_time)

        # Check that 's' record is absent since release_nodes() was not called
        self.server.accounting_match(
            msg=".*%s;%s;.*" % ('s', jid),
            regexp=True, n=50, max_attempts=10, existence=False)
        self.logger.info(
            "There was no 's' record found for job %s, test passes" % jid)

        # On mom superior check the input files to prologue and launch hooks
        # showed the tolerate_node_failures=none value
        search_str = 'pbs.event().job.tolerate_node_failures=none'
        self.mom_hooks_tmp_dir = os.path.join(
            self.server.pbs_conf['PBS_HOME'], 'mom_priv', 'hooks', 'tmp')

        hook_name = 'prolo'
        input_file_pattern = os.path.join(
            self.mom_hooks_tmp_dir, 'hook_execjob_prologue_%s*.in' % hook_name)
        self.match_str_in_input_file(
            self.mom_hooks_tmp_dir, input_file_pattern, search_str)

        hook_name = 'launch'
        input_file_pattern = os.path.join(
            self.mom_hooks_tmp_dir, 'hook_execjob_launch_%s*.in' % hook_name)
        self.match_str_in_input_file(
            self.mom_hooks_tmp_dir, input_file_pattern, search_str)

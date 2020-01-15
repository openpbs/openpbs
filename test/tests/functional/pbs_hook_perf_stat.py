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


from tests.functional import *


class Test_hook_perf_stat(TestFunctional):
    """
    This test suite tests that the hook performance stats are in place
    """

    def setUp(self):
        TestFunctional.setUp(self)
        # ensure LOG_EVENT_DEBUG3 is being recorded to see perf stats
        a = {'log_events': 4095}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.mom.add_config({'$logevent': 4095})
        self.mom.signal('-HUP')

        self.hook_content = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "server hook called")
s = pbs.server()
pbs.logmsg(pbs.LOG_DEBUG, "server data collected for %s" % s.name)
"""
        self.mhook_content = """
import pbs
pbs.logmsg(pbs.LOG_DEBUG, "mom hook called")
s = pbs.server()
pbs.logmsg(pbs.LOG_DEBUG, "mom data collected for %s" % s.name)
"""

    def test_queuejob_hook(self):
        """
        Test that pbs_server collects performance stats for queuejob hook
        """
        hook_name = 'qhook'
        hook_event = 'queuejob'
        hook_attr = {'enabled': 'true', 'event': hook_event}
        self.server.create_import_hook(hook_name, hook_attr, self.hook_content)

        j = Job(TEST_USER)
        self.server.submit(j)

        hd = "hook_perf_stat"
        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        tr = "profile_start"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                              regexp=True)

        stat = "walltime=.* cputime=.*"
        act = "action=populate:pbs\.event\(\)\.job\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_func"
        act = "action=populate:pbs.server\(\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        act = "action=run_code"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)
        tr = "profile_stop"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                              regexp=True)

        lbl = "label=hook_%s_.*" % (hook_event,)
        act = "action=hook_output"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

    def test_modifyjob_hook(self):
        """
        Test that pbs_server collects performance stats for modifyjob hook
        """
        hook_name = 'mhook'
        hook_event = 'modifyjob'
        hook_attr = {'enabled': 'true', 'event': hook_event}
        self.server.create_import_hook(hook_name, hook_attr, self.hook_content)

        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.alterjob(jid, {'Priority': 7}, runas=TEST_USER)

        hd = "hook_perf_stat"
        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        tr = "profile_start"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                              regexp=True)

        stat = "walltime=.* cputime=.*"
        act = "action=populate:pbs\.event\(\)\.job\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs.server\(\).job\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs.server\(\).queue\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs.server\(\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        act = "action=run_code"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)
        tr = "profile_stop"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                              regexp=True)

        lbl = "label=hook_%s_.*" % (hook_event,)
        act = "action=hook_output"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

    def test_movejob_hook(self):
        """
        Test that pbs_server collects performance stats for movejob hook
        """
        hook_name = 'mvhook'
        hook_event = 'movejob'
        hook_attr = {'enabled': 'true', 'event': hook_event}
        self.server.create_import_hook(hook_name, hook_attr, self.hook_content)

        j = Job(TEST_USER, {'Hold_Types': None})
        jid = self.server.submit(j)
        self.server.movejob(jobid=jid, destination="workq")

        hd = "hook_perf_stat"
        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        tr = "profile_start"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                              regexp=True)

        stat = "walltime=.* cputime=.*"
        act = "action=populate:pbs.server\(\).job\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs.server\(\).queue\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs.server\(\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        act = "action=run_code"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)
        tr = "profile_stop"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                              regexp=True)

        lbl = "label=hook_%s_.*" % (hook_event,)
        act = "action=hook_output"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

    def test_runjob_hook(self):
        """
        Test that pbs_server collects performance stats for runjob hook
        """
        hook_name = 'rhook'
        hook_event = 'runjob'
        hook_attr = {'enabled': 'true', 'event': hook_event}
        self.server.create_import_hook(hook_name, hook_attr, self.hook_content)

        j = Job(TEST_USER)
        self.server.submit(j)

        hd = "hook_perf_stat"
        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        tr = "profile_start"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                              regexp=True)

        stat = "walltime=.* cputime=.*"
        act = "action=populate:pbs.server\(\).job\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs.server\(\).queue\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs.server\(\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        act = "action=run_code"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)
        tr = "profile_stop"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                              regexp=True)

    def test_resvsub_hook(self):
        """
        Test that pbs_server collects performance stats for resvsub hook
        """
        hook_name = 'rhook'
        hook_event = 'resvsub'
        hook_attr = {'enabled': 'true', 'event': hook_event}
        self.server.create_import_hook(hook_name, hook_attr, self.hook_content)

        r = Reservation(TEST_USER)
        self.server.submit(r)

        hd = "hook_perf_stat"
        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        tr = "profile_start"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                              regexp=True)

        stat = "walltime=.* cputime=.*"
        act = "action=populate:pbs\.event\(\)\.resv\(.*\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_func"
        act = "action=populate:pbs.server\(\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        act = "action=run_code"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)
        tr = "profile_stop"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                              regexp=True)

        lbl = "label=hook_%s_.*" % (hook_event,)
        act = "action=hook_output"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

    def test_periodic_hook(self):
        """
        Test that pbs_server collects performance stats for periodic hook
        """
        hook_name = 'phook'
        hook_event = 'periodic'
        hook_attr = {'event': hook_event, 'freq': 5}
        self.server.create_import_hook(hook_name, hook_attr,
                                       self.hook_content, overwrite=True)

        hd = "hook_perf_stat"
        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        tr = "profile_start"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                              regexp=True)

        stat = "walltime=.* cputime=.*"
        act = "action=populate:pbs\.event\(\)\.vnode_list"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        act = "action=populate:pbs\.event\(\)\.resv_list"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_func"
        act = "action=populate:pbs.server\(\)"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        act = "action=run_code"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)
        tr = "profile_stop"
        act = "action=server_process_hooks"
        self.server.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                              regexp=True)

        lbl = "label=hook_%s_.*" % (hook_event,)
        act = "action=hook_output"
        self.server.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                              regexp=True)

    def test_mom_hooks(self):
        """
        Test that pbs_mom collects performance stats for mom hooks
        """
        for hook_event in ['execjob_begin',
                           'execjob_launch',
                           'execjob_prologue',
                           'execjob_epilogue',
                           'execjob_end']:
            hook_name = hook_event.replace('execjob_', '')
            hook_attr = {'enabled': 'true', 'event': hook_event}
            self.server.create_import_hook(hook_name, hook_attr,
                                           self.mhook_content)
        j = Job(TEST_USER)
        j.set_sleep_time(5)
        self.server.submit(j)

        for hook_event in ['execjob_begin',
                           'execjob_launch',
                           'execjob_prologue',
                           'execjob_epilogue',
                           'execjob_end']:
            hook_name = hook_event.replace('execjob_', '')

            hd = "hook_perf_stat"
            lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
            tr = "profile_start"
            act = "action=mom_process_hooks"
            self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                               regexp=True)

            act = "action=pbs_python"
            self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                               regexp=True)

            stat = "walltime=.* cputime=.*"
            act = "action=load_hook_input_file"
            self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                               regexp=True)

            act = "action=start_interpreter"
            self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                               regexp=True)

            act = "action=populate:pbs\.event\(\)\.job\(.*\)"
            self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                               regexp=True)

            act = "action=run_code"
            self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                               regexp=True)

            act = "action=hook_output:.*"
            self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                               regexp=True)

            tr = "profile_stop"
            act = "action=pbs_python"
            self.mom.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                               regexp=True)

            act = "action=mom_process_hooks"
            self.mom.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                               regexp=True)

    def test_mom_period_hook(self):
        """
        Test that pbs_mom collects performance stats for mom period hooks
        """
        hook_name = "mom_period"
        hook_event = "exechost_periodic"
        hook_attr = {'enabled': 'true', 'event': hook_event}
        self.server.create_import_hook(hook_name, hook_attr,
                                       self.mhook_content)

        hd = "hook_perf_stat"
        lbl = "label=hook_%s_%s_.*" % (hook_event, hook_name)
        tr = "profile_start"
        act = "action=pbs_python"
        self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, tr),
                           regexp=True)

        stat = "walltime=.* cputime=.*"
        act = "action=load_hook_input_file"
        self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                           regexp=True)

        act = "action=start_interpreter"
        self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                           regexp=True)

        act = "action=populate:pbs\.event\(\)\.vnode_list"
        self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                           regexp=True)

        act = "action=populate:pbs\.event\(\)\.job_list"
        self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                           regexp=True)

        act = "action=run_code"
        self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                           regexp=True)

        act = "action=hook_output:.*"
        self.mom.log_match("%s;%s %s %s" % (hd, lbl, act, stat),
                           regexp=True)

        tr = "profile_stop"
        act = "action=pbs_python"
        self.mom.log_match("%s;%s %s %s %s" % (hd, lbl, act, stat, tr),
                           regexp=True)

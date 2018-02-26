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

from tests.performance import *


class TestCgroupsStress(TestPerformance):
    """
    This test suite targets Linux Cgroups hook stress.
    """

    def setUp(self):
        TestPerformance.setUp(self)

        self.true_script = """#!/bin/bash
#PBS -joe
/bin/true
"""
        self.cfg0 = """{
    "cgroup_prefix"         : "pbspro",
    "exclude_hosts"         : [],
    "exclude_vntypes"       : [],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : false,
    "vnode_per_numa_node"   : false,
    "online_offlined_nodes" : false,
    "use_hyperthreads"      : false,
    "cgroup" : {
        "cpuacct" : {
            "enabled"         : false
        },
        "cpuset" : {
            "enabled"         : false
        },
        "devices" : {
            "enabled"         : false
        },
        "hugetlb" : {
            "enabled"         : false
        },
        "memory":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : [],
            "soft_limit"      : false,
            "default"         : "256MB",
            "reserve_percent" : "0",
            "reserve_amount"  : "0MB"
        },
        "memsw":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : [],
            "default"         : "256MB",
            "reserve_percent" : "0",
            "reserve_amount"  : "128MB"
        }
    }
}"""

        self.paths = self.get_paths()
        if not self.paths:
            self.skipTest("No cgroups mounted")
        self.server.set_op_mode(PTL_CLI)
        self.server.cleanup_jobs(extend='force')
        Job.dflt_attributes[ATTR_k] = 'oe'
        # Configure the scheduler to schedule using vmem
        a = {'resources': 'ncpus,mem,vmem,host,vnode'}
        self.scheduler.set_sched_config(a)
        # Import the hook
        self.hook_name = 'pbs_cgroups'
        self.hook_file = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                      'lib',
                                      'python',
                                      'altair',
                                      'pbs_hooks',
                                      'pbs_cgroups.PY')
        self.load_hook(self.hook_file)
        # Enable the cgroups hook
        conf = {'enabled': 'True', 'freq': 2}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        # Restart mom so exechost_startup hook is run
        self.mom.signal('-HUP')

    @staticmethod
    def get_paths():
        """
        Returns a dictionary containing the location where each cgroup
        is mounted.
        """
        paths = {}
        # Loop through the mounts and collect the ones for cgroups
        with open(os.path.join(os.sep, "proc", "mounts"), 'r') as fd:
            for line in fd:
                entries = line.split()
                if entries[2] != "cgroup":
                    continue
                flags = entries[3].split(',')
                subsys = os.path.basename(entries[1])
                paths[subsys] = entries[1]
                if 'memory' in flags:
                    paths['memsw'] = paths[subsys]
                    paths['memory'] = paths[subsys]
        return paths

    def load_hook(self, filename):
        """
        Import and enable a hook pointed to by the URL specified.
        """
        try:
            with open(filename, 'r') as fd:
                script = fd.read()
        except IOError:
            self.assertTrue(False, "Failed to open hook file %s" % filename)
        events = '"execjob_begin,execjob_launch,execjob_attach,'
        events += 'execjob_epilogue,execjob_end,exechost_startup,'
        events += 'exechost_periodic"'
        a = {'enabled': 'True',
             'freq': '2',
             'event': events}
        self.server.create_import_hook(self.hook_name, a, script,
                                       overwrite=True)
        # Add the configuration
        self.load_config(self.cfg0)

    def load_config(self, cfg):
        """
        Create a hook configuration file with the provided contents.
        """
        (fd, fn) = self.du.mkstemp()
        os.write(fd, cfg)
        os.close(fd)
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': fn}
        self.server.manager(MGR_CMD_IMPORT, HOOK, a, self.hook_name)
        os.remove(fn)
        self.mom.log_match('pbs_cgroups.CF;copy hook-related ' +
                           'file request received',
                           max_attempts=5,
                           starttime=self.server.ctime)
        self.logger.info("Current config: %s" % cfg)
        # Restart MoM to work around PP-993
        self.mom.restart()

    @timeout(600)
    def test_cgroups_race_condition(self):
        """
        Test to ensure a cgroups event does not read the cgroups file system
        while another event is writing to it. By submitting 1000 instant jobs,
        the events should collide at least once.
        """
        pcpus = 0
        with open('/proc/cpuinfo', 'r') as desc:
            for line in desc:
                if re.match('^processor', line):
                    pcpus += 1
        if pcpus < 8:
            self.skipTest("Test requires at least 8 physical CPUs")

        attr = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        self.load_config(self.cfg0)
        now = time.time()
        j = Job(TEST_USER, attrs={ATTR_J: '0-1000'})
        j.create_script(self.true_script)
        jid = self.server.submit(j)
        jid = jid.split(']')[0]
        done = False
        for i in range(0, 1000):
            # Build the subjob id and ensure it is complete
            sjid = jid + str(i) + "]"
            # If the array job is finished, it and all subjobs will be put
            # into the F state. This can happen while checking the last
            # couple of subjobs. If this happens, we need to check for the
            # F state instead of the X state.
            if done:
                self.server.expect(
                    JOB, {'job_state': 'F'}, id=sjid, extend='x')
            else:
                try:
                    self.server.expect(
                        JOB, {'job_state': 'X'}, id=sjid, extend='tx')
                except PtlExpectError:
                    # The expect failed, maybe because the array job finished
                    # Check for the F state for this and future subjobs.
                    done = True
                    self.server.expect(
                        JOB, {'job_state': 'F'}, id=sjid, extend='x')
            # Check the logs for IOError every 100 subjobs, to reduce time of
            # a failing test.
            if i % 100 == 0:
                self.mom.log_match(msg="IOError", starttime=now,
                                   existence=False, max_attempts=1, n="ALL")
        # Check the logs one last time to ensure it passed
        self.mom.log_match(msg="IOError", starttime=now,
                           existence=False, max_attempts=10, n="ALL")

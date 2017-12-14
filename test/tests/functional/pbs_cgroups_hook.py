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

from tests.functional import *


class TestCgroupsHook(TestFunctional):
    """
    This test suite targets Linux Cgroups hook functionality.
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.paths = self.get_paths()
        if not self.paths:
            self.skipTest("No cgroups mounted")
        self.server.set_op_mode(PTL_CLI)
        self.server.cleanup_jobs(extend='force')
        self.remove_vntype()
        self.eatmem_script = """
import sys
MB = 2 ** 20
iterations = 1
chunkSizeMb = 1
if (len(sys.argv) > 1):
    iterations = int(sys.argv[1])
if (len(sys.argv) > 2):
    chunkSizeMb = int(sys.argv[2])
if (iterations < 1):
    print('Iteration count must be greater than zero.')
    exit(1)
if (chunkSizeMb < 1):
    print('Chunk size must be greater than zero.')
    exit(1)
totalSizeMb = chunkSizeMb * iterations
print('Allocating %d chunk(s) of size %dMB. (%dMB total)' %
      (iterations, chunkSizeMb, totalSizeMb))
buf = ""
for i in range(0, iterations):
    print("allocating %dMB" % ((i + 1) * chunkSizeMb))
    buf += ('#' * MB * chunkSizeMb)
"""
        self.eatmem_job1 = \
            '#PBS -joe\n' + \
            'sleep 2\n' + \
            'python - 400 10 <<EOF\n' + \
            self.eatmem_script + 'EOF\n' + \
            'sleep 5\n'
        self.eatmem_job2 = \
            '#PBS -joe\n' + \
            'sleep 2\n' + \
            'python - 300 10 <<EOF\n' + \
            self.eatmem_script + 'EOF\n' + \
            'sleep 4\n' + \
            'python - 400 10 <<EOF\n' + \
            self.eatmem_script + 'EOF\n' + \
            'sleep 4\n'
        self.eatmem_job3 = \
            '#PBS -S /bin/bash\n' + \
            '#PBS -joe\n' + \
            'sleep 2\n' + \
            'let i=0; while [ $i -lt 20 ]; do\n' + \
            'python - 3000 1 <<EOF\n' + \
            self.eatmem_script + 'EOF\n' + \
            'done\n' + \
            'sleep 5\n' + \
            'python - 4000 1 <<EOF\n' + \
            self.eatmem_script + 'EOF\n' + \
            'sleep 10\n'
        self.cpuset_mem_script = """#!/bin/bash
#PBS -joe
echo $PBS_JOBID
cpuset_base=`grep cgroup /proc/mounts | grep cpuset | cut -d' ' -f2`
if [ -z "$cpuset_base" ]; then
    echo "Cpuset subsystem not mounted."
else
    base="$cpuset_base/pbspro/$PBS_JOBID"
    if [ -d "$base" ]; then
        cpus=`cat $base/cpuset.cpus`
        echo "CpuIDs=${cpus}"
        mems=`cat $base/cpuset.mems`
        echo "MemorySocket=${mems}"
    fi
fi
memory_base=`grep cgroup /proc/mounts | grep memory | cut -d' ' -f2`
if [ -z "$memory_base" ]; then
    echo "Memory subsystem not mounted."
else
    base="$memory_base/pbspro/$PBS_JOBID"
    if [ -d "$base" ]; then
       mem_limit=`cat $base/memory.limit_in_bytes`
       echo "MemoryLimit=${mem_limit}"
       memsw_limit=`cat $base/memory.memsw.limit_in_bytes`
       echo "MemswLimit=${memsw_limit}"
    fi
fi
sleep 2
"""
        self.check_dirs_script = """#!/bin/bash
#PBS -joe
cpuset_base=`grep cgroup /proc/mounts | grep cpuset | cut -d' ' -f2`
cpuacct_base=`grep cgroup /proc/mounts | grep cpuacct | cut -d' ' -f2`
memory_base=`grep cgroup /proc/mounts | grep memory | cut -d' ' -f2`
devices_base=`grep cgroup /proc/mounts | grep devices | cut -d' ' -f2`
if [ -d "$devices_base/pbs/$PBS_JOBID" ]; then
    device_list=`cat $devices_base/pbs/$PBS_JOBID/devices.list`
    echo "${device_list}"
    if [ -d $cpuacct_base/pbs/$PBS_JOBID ] ||
       [ -d $cpuset_base/pbs/$PBS_JOBID ] ||
       [ -d $memory_base/pbs/$PBS_JOBID ]; then
        echo "Disabled cgroup subsystems are populated with the job id"
    fi
else
    echo "Devices directory should be populated"
fi
sleep 2
"""
        self.sleep15_job = """#!/bin/bash
#PBS -joe
sleep 15
"""
        self.eat_cpu_script = """#!/bin/bash
#PBS -joe
for i in 1 2 3 4; do while : ; do : ; done & done
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
        "memory" : {
            "enabled"         : false
        },
        "memsw" : {
            "enabled"         : false
        }
    }
}
"""
        self.cfg1 = """{
    "cgroup_prefix"         : "pbspro",
    "exclude_hosts"         : [%s],
    "exclude_vntypes"       : [%s],
    "run_only_on_hosts"     : [%s],
    "periodic_resc_update"  : true,
    "vnode_per_numa_node"   : false,
    "online_offlined_nodes" : true,
    "use_hyperthreads"      : false,
    "cgroup":
    {
        "cpuacct":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "cpuset":
        {
            "enabled"         : true,
            "exclude_hosts"   : [%s],
            "exclude_vntypes" : []
        },
        "devices":
        {
            "enabled"         : false
        },
        "hugetlb":
        {
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
}
"""
        self.cfg2 = """{
    "cgroup_prefix"         : "pbs",
    "exclude_hosts"         : [],
    "exclude_vntypes"       : [],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : false,
    "vnode_per_numa_node"   : true,
    "online_offlined_nodes" : false,
    "use_hyperthreads"      : false,
    "cgroup":
    {
        "cpuacct":
        {
            "enabled"         : false
        },
        "cpuset":
        {
            "enabled"         : false
        },
        "devices":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : [],
            "allow"           : [
                "b *:* rwm",
                ["console","rwm"],
                ["tty0","rwm", "*"],
                "c 1:* rwm",
                "c 10:* rwm"
            ]
        },
        "hugetlb":
        {
            "enabled"         : false
        },
        "memory":
        {
            "enabled"         : false
        },
        "memsw":
        {
            "enabled"         : false
        }
    }
}
"""
        self.cfg3 = """{
    "cgroup_prefix"         : "pbspro",
    "exclude_hosts"         : [],
    "exclude_vntypes"       : ["no_cgroups"],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : true,
    "vnode_per_numa_node"   : false,
    "online_offlined_nodes" : true,
    "use_hyperthreads"      : false,
    "cgroup":
    {
        "cpuacct":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "cpuset":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : ["no_cgroups_cpus"]
        },
        "devices":
        {
            "enabled"         : false
        },
        "hugetlb":
        {
            "enabled"         : false
        },
        "memory":
        {
            "enabled"         : true,
            "default"         : "256MB",
            "reserve_amount"  : "50MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : ["no_cgroups_mem"]
        },
        "memsw":
        {
            "enabled"         : true,
            "default"         : "256MB",
            "reserve_amount"  : "45MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        }
    }
}
"""
        self.cfg4 = """{
    "cgroup_prefix"         : "pbspro",
    "exclude_hosts"         : [],
    "exclude_vntypes"       : ["no_cgroups"],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : true,
    "vnode_per_numa_node"   : false,
    "online_offlined_nodes" : true,
    "use_hyperthreads"      : false,
    "cgroup":
    {
        "cpuacct":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "cpuset":
        {
            "enabled"         : true,
            "exclude_hosts"   : [],
            "exclude_vntypes" : ["no_cgroups_cpus"]
        },
        "devices":
        {
            "enabled"         : false
        },
        "hugetlb":
        {
            "enabled"         : false
        },
        "memory":
        {
            "enabled"         : true,
            "default"         : "256MB",
            "reserve_amount"  : "100MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : ["no_cgroups_mem"]
        },
        "memsw":
        {
            "enabled"         : true,
            "default"         : "256MB",
            "reserve_amount"  : "90MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        }
    }
}
"""
        Job.dflt_attributes[ATTR_k] = 'oe'
        # Increase the log level
        a = {'log_events': '4095'}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)
        # Configure the scheduler to schedule using vmem
        a = {'resources': 'ncpus,mem,vmem,host,vnode'}
        self.scheduler.set_sched_config(a)
        # Configure the mom
        self.momA = self.moms.values()[0]
        c = {'$logevent': '0xffffffff', '$clienthost': self.server.name,
             '$min_check_poll': 8, '$max_check_poll': 12}
        self.momA.add_config(c)
        # Create resource as root
        attr = {'type': 'long', 'flag': 'nh'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='nmics',
                            runas=ROOT_USER, logerr=False)
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='ngpus',
                            runas=ROOT_USER, logerr=False)
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

    def get_paths(self):
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
                    paths['memsw'] = paths['memory']
        return paths

    def load_hook(self, filename):
        """
        Import and enable a hook pointed to by the URL specified.
        """
        try:
            with open(filename, 'r') as fd:
                script = fd.read()
        except:
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
                           max_attempts=3,
                           starttime=self.server.ctime)
        self.logger.info("Current config: %s" % cfg)
        # Restart MoM to work around PP-993
        self.mom.restart()

    def set_vntype(self, typestring='myvntype'):
        """
        Set the vnode type for the local mom.
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = os.path.join(pbs_home, 'mom_priv', 'vntype')
        self.logger.info("Setting vntype to %s in %s" %
                         (typestring, vntype_file))
        (fd, fn) = self.du.mkstemp()
        os.write(fd, typestring)
        os.close(fd)
        ret = self.du.run_copy(hosts=self.mom.hostname, src=fn,
                               dest=vntype_file, sudo=True, uid='root',
                               gid='root', mode=0644, runas=ROOT_USER)
        os.remove(fn)
        if ret['rc'] != 0:
            self.skipTest("pbs_cgroups_hook: need root privileges")

    def remove_vntype(self):
        """
        Unset the vnode type for the local mom.
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = os.path.join(pbs_home, 'mom_priv', 'vntype')
        ret = self.du.rm(hostname=self.mom.hostname, path=vntype_file,
                         force=True, sudo=True, runas=ROOT_USER)
        if not ret:
            self.skipTest("pbs_cgroups_hook: need root privileges")

    def wait_and_remove_file(self, filename=''):
        """
        Wait up to ten seconds for a file to appear and then remove it.
        """
        self.logger.info("Removing file: %s" % filename)
        if not filename:
            raise ValueError('Invalid filename')
        for _ in range(10):
            if not os.path.isfile(filename):
                break
            try:
                self.du.rm(hostname=self.mom.hostname, path=filename,
                           force=True, sudo=True, runas=TEST_USER)
            except:
                time.sleep(1)
        self.assertFalse(os.path.isfile(filename),
                         "File not removed: %s" % filename)

    def wait_and_read_file(self, filename=''):
        """
        Wait up to ten seconds for a file to appear and then read it.
        """
        from ptl.utils.pbs_logutils import PBSLogUtils
        self.logger.info("Reading file: %s" % filename)
        if not filename:
            raise ValueError('Invalid filename')
        for _ in range(10):
            if os.path.isfile(filename):
                break
            time.sleep(1)
        self.assertTrue(os.path.isfile(filename),
                        "File not found: %s" % filename)
        with PBSLogUtils().open_log(filename, sudo=True) as fd:
            output = fd.read().splitlines()
        return output

    def test_cgroup_vntype_excluded(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have an exclude vntype file set
        """
        name = 'CGROUP8'
        self.set_vntype("no_cgroups")
        self.load_config(self.cfg1 % ("", '"no_cgroups"', "", ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.mom.log_match("no_cgroups is in the excluded vnode " +
                           "type list: ['no_cgroups']",
                           max_attempts=3,
                           starttime=self.server.ctime)
        self.wait_and_remove_file(o.split(':')[1])

    def test_cgroup_host_excluded(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have the exclude_hosts set
        """
        name = 'CGROUP9'
        self.load_config(self.cfg1 % ('"%s"' % self.mom.shortname, "", "", ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.mom.log_match("%s" % self.mom.shortname +
                           " is in the excluded host list: " +
                           "['%s']" % self.mom.shortname,
                           max_attempts=5,
                           starttime=self.server.ctime)
        self.wait_and_remove_file(o.split(':')[1])

    def test_cgroup_exclude_vntype_mem(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have an exclude vntype file set
        """
        name = 'CGROUP12'
        self.set_vntype("no_cgroups_mem")
        self.load_config(self.cfg3)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.mom.log_match("cgroup excluded for subsystem memory " +
                           "on vnode type no_cgroups_mem",
                           max_attempts=5,
                           starttime=self.server.ctime)
        self.wait_and_remove_file(o.split(':')[1])

    def test_cgroup_periodic_update(self):
        """
        Test to verify that cgroups are reporting usage for cput and mem
        """
        name = 'CGROUP13'
        self.load_config(self.cfg3)
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job2)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.mom.log_match("%s;update_job_usage: " % jid +
                           "CPU usage: 0.000 secs",
                           max_attempts=2)
        self.mom.log_match("%s;update_job_usage: " % jid +
                           "Memory usage: mem=0b",
                           max_attempts=2)
        self.mom.log_match("%s;update_job_usage: " % jid +
                           "Memory usage: vmem=0b",
                           max_attempts=2)
        # Allow some time to pass for values to be updated
        time.sleep(5)
        self.mom.log_match("%s;update_job_usage: " % jid +
                           "CPU usage: [0-9.]+ secs",
                           regexp=True,
                           max_attempts=5)
        self.mom.log_match("%s;update_job_usage: " % jid +
                           "Memory usage: vmem=[1-9][0-9]+kb",
                           regexp=True,
                           max_attempts=5)
        self.wait_and_remove_file(o.split(':')[1])

    def test_cgroup_cpuset_and_memory(self):
        """
        Test to verify that the job cgroup is created correctly
        Check to see that cpuset.cpus=0, cpuset.mems=0 and that
        memory.limit_in_bytes = 314572800
        """
        name = 'CGROUP1'
        self.load_config(self.cfg3)
        j = Job(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j.set_attributes(a)
        j.create_script(self.cpuset_mem_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        tmp_file = filename.split(':')[1]
        tmp_out = self.wait_and_read_file(tmp_file)
        self.logger.info("%s: %s" % (name, tmp_out))
        self.wait_and_remove_file(tmp_file)
        self.assertTrue(jid in tmp_out)
        self.logger.info("job dir check passed")
        self.assertTrue("CpuIDs=0" in tmp_out)
        self.logger.info("CpuIDs check passed")
        self.assertTrue("MemorySocket=0" in tmp_out)
        self.logger.info("MemorySocket check passed")
        self.assertTrue("MemoryLimit=314572800" in tmp_out)
        self.logger.info("MemoryLimit check passed")

    def test_cgroup_cpuset_and_memsw(self):
        """
        Test to verify that the job cgroup is created correctly
        using the default memory and vmem
        Check to see that cpuset.cpus=0, cpuset.mems=0 and that
        memory.limit_in_bytes = 268435456
        memory.memsw.limit_in_bytes = 268435456
        """
        name = 'CGROUP2'
        self.load_config(self.cfg3)
        j = Job(TEST_USER)
        a = {'Resource_List.select': '1:ncpus=1', ATTR_N: name}
        j.set_attributes(a)
        j.create_script(self.cpuset_mem_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        tmp_file = filename.split(':')[1]
        tmp_out = self.wait_and_read_file(tmp_file)
        self.wait_and_remove_file(tmp_file)
        self.assertTrue(jid in tmp_out)
        self.logger.info("job dir check passed")
        self.assertTrue("CpuIDs=0" in tmp_out)
        self.logger.info("CpuIDs check passed")
        self.assertTrue("MemorySocket=0" in tmp_out)
        self.logger.info("MemorySocket check passed")
        self.assertTrue("MemoryLimit=268435456" in tmp_out)
        self.assertTrue("MemswLimit=268435456" in tmp_out)
        self.logger.info("MemoryLimit check passed")

    def test_cgroup_prefix_and_devices(self):
        """
        Test to verify that the cgroup prefix is set to pbs and that
        only the devices subsystem is enabled with the correct devices
        allowed
        """
        name = "CGROUP3"
        self.load_config(self.cfg2)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.check_dirs_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        tmp_file = filename.split(':')[1]
        tmp_out = self.wait_and_read_file(tmp_file)
        self.wait_and_remove_file(tmp_file)
        check_devices = ['b *:* rwm',
                         'c 5:1 rwm',
                         'c 4:* rwm',
                         'c 1:* rwm',
                         'c 10:* rwm']
        for device in check_devices:
            self.assertTrue(device in tmp_out,
                            '"%s" not found in: %s' % (device, tmp_out))
        self.logger.info("device_list check passed")
        self.assertFalse("Disabled cgroup subsystems are populated" in tmp_out,
                         'Found disabled cgroup subsystems populated')
        self.logger.info("Disabled subsystems check passed")

    def test_cgroup_cpuset(self):
        """
        Test to verify that 2 jobs are not assigned the same cpus
        """
        pcpus = 0
        with open('/proc/cpuinfo', 'r') as desc:
            for line in desc:
                if re.match('^processor', line):
                    pcpus += 1
        if pcpus < 2:
            self.skipTest("Test requires at least two physical CPUs")
        name = "CGROUP4"
        self.load_config(self.cfg3)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name + 'a'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.cpuset_mem_script)
        jid1 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid1)
        self.server.status(JOB, ATTR_o, jid1)
        filename1 = j1.attributes[ATTR_o]
        b = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name + 'b'}
        j2 = Job(TEST_USER, attrs=b)
        j2.create_script(self.cpuset_mem_script)
        jid2 = self.server.submit(j2)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        filename2 = j2.attributes[ATTR_o]
        self.logger.info("Job1 .o file: %s" % filename1)
        tmp_file1 = filename1.split(':')[1]
        tmp_out1 = self.wait_and_read_file(tmp_file1)
        self.logger.info("tmp_out1: %s" % tmp_out1)
        self.wait_and_remove_file(tmp_file1)
        self.assertTrue(jid1 in tmp_out1, '%s not found in output' % jid1)
        self.logger.info("Job2 .o file: %s" % filename2)
        tmp_file2 = filename2.split(':')[1]
        tmp_out2 = self.wait_and_read_file(tmp_file2)
        self.logger.info("tmp_out2: %s" % tmp_out2)
        self.wait_and_remove_file(tmp_file2)
        self.assertTrue(jid2 in tmp_out2, '%s not found in output' % jid2)
        self.logger.info("job dir check passed")
        if 'CpuIDs=0' in tmp_out1 and 'CpuIDs=1' in tmp_out2:
            pass
        elif 'CpuIDs=1' in tmp_out1 and 'CpuIDs=0' in tmp_out2:
            pass
        else:
            self.assertTrue(False,
                            "Processes should be assigned to different CPUs")
        self.logger.info("CpuIDs check passed")

    def test_cgroup_enforce_memory(self):
        """
        Test to verify that the job is killed when it tries to
        use more memory then it requested
        """
        name = 'CGROUP5'
        self.load_config(self.cfg3)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        # mem and vmem limit will both be set, and either could be detected
        self.mom.log_match("%s;Cgroup mem(ory|sw) limit exceeded" % jid,
                           regexp=True,
                           max_attempts=20)
        self.wait_and_remove_file(o.split(':')[1])

    def test_cgroup_enforce_memsw(self):
        """
        Test to verify that the job is killed when it tries to
        use more vmem then it requested
        """
        name = 'CGROUP6'
        self.load_config(self.cfg3)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:vmem=320mb',
             ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        tmp_file = filename.split(':')[1]
        tmp_out = self.wait_and_read_file(tmp_file)
        self.wait_and_remove_file(tmp_file)
        self.assertTrue("MemoryError" in tmp_out,
                        'MemoryError not present in output')

    def test_cgroup_offline_node(self):
        """
        Test to verify that the node is offlined when it can't clean up
        the cgroup and brought back online once the cgroup is cleaned up
        """
        name = 'CGROUP7'
        if 'freezer' not in self.paths:
            self.skipTest("Freezer cgroup is not mounted")
        fdir = self.paths['freezer']
        if not os.path.isdir(fdir):
            self.skipTest("Freezer cgroup is not found")
        # Configure the hook
        self.load_config(self.cfg3)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Resource_List.walltime': 3, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        tmp_file = filename.split(':')[1]
        # Make dir in freezer subsystem
        fdir = os.path.join(fdir, 'pbspro')
        self.du.mkdir(hostname=self.mom.hostname, path=fdir, parents=False,
                      mode=0755, sudo=True, runas=ROOT_USER)
        fdir = os.path.join(fdir, jid)
        self.du.mkdir(hostname=self.mom.hostname, path=fdir, parents=False,
                      mode=0755, sudo=True, runas=ROOT_USER)
        if not os.path.isdir(fdir):
            self.skipTest("Unable to create %s" % fdir)
        freezer_tasks_file = os.path.join(fdir, 'tasks')
        if not os.path.isfile(freezer_tasks_file):
            self.skipTest("File not found: %s" % freezer_tasks_file)
        # Query the pids in the cgroup
        cpuset_tasks_file = os.path.join(self.paths['cpuset'], 'pbspro',
                                         jid, 'tasks')
        ret = self.du.cat(self.mom.hostname, cpuset_tasks_file,
                          sudo=True, runas=ROOT_USER)
        tasks = ret['out']
        self.logger.info("Tasks: %s" % tasks)
        self.assertTrue(tasks, "No tasks in cpuset cgroup for job")
        self.logger.info("Server name: %s" % self.server.name)
        # Write each PID into the tasks file for the freezer cgroup
        for task in tasks[1:]:
            cmd = ['/bin/echo', '%s' % task]
            with open(freezer_tasks_file, 'w') as fd:
                ret = self.du.run_cmd(self.mom.hostname, cmd, stdout=fd,
                                      sudo=True, runas=ROOT_USER)
            if ret['rc'] != 0:
                self.skipTest("pbs_cgroups_hook: need root privileges")
        # Freeze the cgroup
        cmd = ['/bin/echo', 'FROZEN']
        with open(os.path.join(fdir, 'freezer.state'), 'w') as fd:
            ret = self.du.run_cmd(self.mom.hostname, cmd, stdout=fd,
                                  sudo=True, runas=ROOT_USER)
        if ret['rc'] != 0:
            self.skipTest("pbs_cgroups_hook: need root privileges")
        self.server.expect(NODE, {'state': 'offline'},
                           id=self.mom.shortname, interval=3)
        # Thaw the cgroup
        cmd = ['/bin/echo', 'THAWED']
        with open(os.path.join(fdir, 'freezer.state'), 'w') as fd:
            ret = self.du.run_cmd(self.mom.hostname, cmd, stdout=fd,
                                  sudo=True, runas=ROOT_USER)
        if ret['rc'] != 0:
            self.skipTest("pbs_cgroups_hook: need root privileges")
        time.sleep(1)
        self.du.rm(hostname=self.mom.hostname, path=os.path.dirname(fdir),
                   force=True, recursive=True, sudo=True, runas=ROOT_USER)
        self.server.expect(NODE, {'state': 'free'},
                           id=self.mom.shortname, interval=3)
        self.wait_and_remove_file(tmp_file)

    def test_cgroup_cpuset_host_excluded(self):
        """
        Test to verify that cgroups subsystems are not enforced on nodes
        that have the exclude_hosts set
        """
        name = 'CGROUP10'
        self.load_config(self.cfg1 % ("", "", "", '"%s"' % self.mom.shortname))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.mom.log_match("cgroup excluded for subsystem cpuset " +
                           "on host %s" % self.mom.shortname,
                           max_attempts=5,
                           starttime=self.server.ctime)
        self.wait_and_remove_file(o.split(':')[1])

    def test_cgroup_run_on_host(self):
        """
        Test to verify that the cgroup hook only runs on nodes
        in the run_only_on_hosts
        """
        name = 'CGROUP11'
        self.load_config(self.cfg1 % ("", "", '"NonexistentNode"', ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        time.sleep(1)
        self.mom.log_match("%s is not in " % (self.mom.shortname) +
                           "the approved host list: " +
                           "\['NonexistentNode'\]",
                           regexp=True,
                           max_attempts=5,
                           starttime=self.server.ctime)
        self.wait_and_remove_file(o.split(':')[1])

    def test_cgroup_qstat_resources(self):
        """
        Test to verify that cgroups are reporting usage for
        mem, and vmem in qstat
        """
        name = 'CGROUP14'
        self.load_config(self.cfg3)
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job3)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.logger.info("OUTPUT: %s" % o)
        resc_list = ['resources_used.cput']
        resc_list += ['resources_used.mem']
        resc_list += ['resources_used.vmem']
        qstat1 = self.server.status(JOB, resc_list, id=jid)
        for q in qstat1:
            self.logger.info("Q1: %s" % q)
        cput1 = qstat1[0]['resources_used.cput']
        mem1 = qstat1[0]['resources_used.mem']
        vmem1 = qstat1[0]['resources_used.vmem']
        self.logger.info("Waiting 15 seconds for CPU time to accumulate")
        time.sleep(15)
        qstat2 = self.server.status(JOB, resc_list, id=jid)
        for q in qstat2:
            self.logger.info("Q2: %s" % q)
        cput2 = qstat2[0]['resources_used.cput']
        mem2 = qstat2[0]['resources_used.mem']
        vmem2 = qstat2[0]['resources_used.vmem']
        self.wait_and_remove_file(o.split(':')[1])
        self.assertNotEqual(cput1, cput2)
        self.assertNotEqual(mem1, mem2)
        self.assertNotEqual(vmem1, vmem2)

    def test_cgroup_reserve_mem(self):
        """
        Test to verify that the mom reserve memory for OS
        when there is a reserve mem request in the config.
        Install cfg3 and then cfg4 and measure diffenece
        between the amount of available memory and memsw.
        For example, on a system with 1GB of physical memory
        and 1GB of active swap. With cfg3 in place, we should
        see 1GB - 50MB = 950MB of available memory and
        2GB - (50MB + 45MB) = 1905MB of available vmem.
        With cfg4 in place, we should see 1GB - 100MB = 900MB
        of available memory and 2GB - (100MB + 90MB) = 1810MB
        of available vmem. When we calculate the differences
        we get:
        mem: 950MB - 900MB = 50MB = 51200KB
        vmem: 1905MB - 1810MB = 95MB = 97280KB
        """
        self.load_config(self.cfg3)
        self.momA.stop()
        self.server.expect(NODE, {'state': 'down'},
                           self.momA.shortname, interval=3)
        self.momA.delete_vnode_defs()
        self.momA.start()
        self.server.expect(NODE, {'state': 'free'},
                           self.momA.shortname, interval=3)
        vmem = self.server.status(NODE, 'resources_available.vmem')
        self.logger.info("vmem: %s" % str(vmem))
        vmem1 = PbsTypeSize(vmem[0]['resources_available.vmem'])
        mem = self.server.status(NODE, 'resources_available.mem')
        mem1 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info("Mem-1: %s" % mem1.value)
        self.logger.info("Vmem-1: %s" % vmem1.value)
        self.load_config(self.cfg4)
        self.momA.stop()
        self.server.expect(NODE, {'state': 'down'},
                           self.momA.shortname, interval=3)
        self.momA.delete_vnode_defs()
        self.momA.start()
        self.server.expect(NODE, {'state': 'free'},
                           self.momA.shortname, interval=3)
        vmem = self.server.status(NODE, 'resources_available.vmem')
        vmem2 = PbsTypeSize(vmem[0]['resources_available.vmem'])
        mem = self.server.status(NODE, 'resources_available.mem')
        mem2 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info("Mem-2: %s" % mem2.value)
        self.logger.info("Vmem-2: %s" % vmem2.value)
        mem_resv = mem1 - mem2
        vmem_resv = vmem1 - vmem2
        self.logger.info("Mem resv: %s" % mem_resv.value)
        self.logger.info("Vmem resv: %s" % vmem_resv.value)
        self.assertEqual(mem_resv.value, 51200)
        self.assertEqual(mem_resv.unit, 'kb')
        self.assertEqual(vmem_resv.value, 97280)
        self.assertEqual(vmem_resv.unit, 'kb')

    def tearDown(self):
        TestFunctional.tearDown(self)
        self.load_config(self.cfg0)
        self.remove_vntype()
        # Disable the cgroups hook
        conf = {'enabled': 'False', 'freq': 30}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)

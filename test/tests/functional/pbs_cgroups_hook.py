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
from glob import glob


def have_swap():
    """
    Returns 1 if swap space is not 0 otherwise returns 0
    """
    tt = 0
    with open(os.path.join(os.sep, "proc", "meminfo"), 'r') as fd:
        for line in fd:
            entry = line.split()
            if ((entry[0] == "SwapFree:") and (entry[1] != '0')):
                tt = 1
    return tt


def is_memsw_enabled(mem_path):
    """
    Check if system has swapcontrol enabled, then return true
    else return false
    """

    # List all files and check if memsw files exists
    for files in os.listdir(mem_path):
        if "memory.memsw" in files:
            return "true"

    return "false"


@tags('mom', 'multi_node')
class TestCgroupsHook(TestFunctional):

    """
    This test suite targets Linux Cgroups hook functionality.
    """

    def setUp(self):
        TestFunctional.setUp(self)

        # Some of the tests requires 2 nodes.
        # Hence setting the values to default when no mom is specified

        self.momA = socket.gethostname()
        self.momB = self.momA
        self.vntypenameA = "no_cgroups"
        self.vntypenameB = self.vntypenameA
        self.iscray = 0
        self.tempfile = []
        if self.moms:
            if len(self.moms) == 1:
                self.hostA = self.moms.values()[0]
                self.hostB = self.hostA
                self.momA = self.hostA.shortname
                self.momB = self.momA
                self.vntypenameA = self.get_vntype(self.momA)
                self.vntypenameB = self.vntypenameA
                if self.hostA.is_cray():
                    self.iscray = 1
            if len(self.moms) == 2:
                self.hostA = self.moms.values()[0]
                self.hostB = self.moms.values()[1]
                self.momA = self.hostA.shortname
                self.momB = self.hostB.shortname
                self.vntypenameA = self.get_vntype(self.momA)
                self.vntypenameB = self.get_vntype(self.momB)
                if self.hostA.is_cray() or self.hostB.is_cray():
                    self.iscray = 1

        self.serverA = self.servers.values()[0].name

        self.paths = self.get_paths()
        if not self.paths:
            self.skipTest("No cgroups mounted")
        self.swapctl = is_memsw_enabled(self.paths['memsw'])

        self.server.set_op_mode(PTL_CLI)
        self.server.cleanup_jobs(extend='force')

        if not self.iscray:
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
            'python - 80 10 <<EOF\n' + \
            self.eatmem_script + 'EOF\n' + \
            'sleep 5\n'
        self.eatmem_job2 = \
            '#PBS -joe\n' + \
            'sleep 2\n' + \
            'python - 200 10 <<EOF\n' + \
            self.eatmem_script + 'EOF\n' + \
            'sleep 10\n' + \
            'python - 100 10 <<EOF\n' + \
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
        cpupath1="$base/cpuset.cpus"
        cpupath2="$base/cpus"
        if [ -f "$cpupath1" ]; then
            cpus=`cat $base/cpuset.cpus`
        elif [ -f "$cpupath2" ]; then
            cpus=`cat $base/cpus`
        fi
        echo "CpuIDs=${cpus}"
        mempath1="$base/cpuset.mems"
        mempath2="$base/mems"
        if [ -f "$mempath1" ]; then
            mems=`cat $base/cpuset.mems`
        elif [ -f "$mempath2" ]; then
            mems=`cat $base/mems`
        fi
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
sleep 15
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
            "enabled"         : %s,
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
    "exclude_vntypes"       : [%s],
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
            "exclude_vntypes" : [%s]
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
            "exclude_vntypes" : [%s]
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "45MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : [%s]
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
            "enabled"         : %s,
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
        c = {'$logevent': '0xffffffff', '$clienthost': self.server.name,
             '$min_check_poll': 8, '$max_check_poll': 12}
        self.hostA.add_config(c)
        self.hostB.add_config(c)
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
        events = '"execjob_begin,execjob_launch,execjob_attach,'
        events += 'execjob_epilogue,execjob_end,exechost_startup,'
        events += 'exechost_periodic"'
        # Enable the cgroups hook
        conf = {'enabled': 'True', 'freq': 2, 'event': events}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        # Restart mom so exechost_startup hook is run
        self.hostA.signal('-HUP')
        self.hostB.signal('-HUP')
        self.logger.info("vntype set for %s is %s" %
                         (self.momA, self.vntypenameA))
        self.logger.info("vntype set for %s is %s" %
                         (self.momB, self.vntypenameB))

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
                    paths['memsw'] = paths[subsys]
                    paths['memory'] = paths[subsys]
                if 'cpuacct' in flags:
                    paths['cpuacct'] = paths[subsys]
                else:
                    paths['cpuacct'] = 0
                if 'devices' in flags:
                    paths['devices'] = paths[subsys]
                else:
                    paths['devices'] = 0
        return paths

    def is_dir(self, cpath, mom):
        """
        Returns True if path exists otherwise false
        """
        for _ in range(10):
            rv = self.du.isdir(hostname=mom, path=cpath, sudo=True)
            if rv:
                return True
        return False

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
        fn = self.du.create_temp_file(hostname=self.serverA, body=cfg)
        self.tempfile.append(fn)
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': fn}
        self.server.manager(MGR_CMD_IMPORT, HOOK, a, self.hook_name)
        self.hostA.log_match('pbs_cgroups.CF;copy hook-related '
                             'file request received',
                             starttime=self.server.ctime)
        self.logger.info("Current config: %s" % cfg)
        # Restart MoM to work around PP-993
        self.hostA.restart()
        self.hostB.restart()

    def set_vntype(self, mom, typestring='myvntype'):
        """
        Set the vnode type for the local mom.
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = os.path.join(pbs_home, 'mom_priv', 'vntype')
        self.logger.info("Setting vntype to %s in %s on mom %s" %
                         (typestring, vntype_file, mom))
        localhost = socket.gethostname()
        fn = self.du.create_temp_file(hostname=localhost, body=typestring)
        self.tempfile.append(fn)
        ret = self.du.run_copy(hosts=mom, src=fn,
                               dest=vntype_file, sudo=True, uid='root',
                               gid='root', mode=0644)
        if ret['rc'] != 0:
            self.skipTest("pbs_cgroups_hook: need root privileges")

    def remove_vntype(self):
        """
        Unset the vnode type for the local mom.
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = os.path.join(pbs_home, 'mom_priv', 'vntype')
        self.logger.info("Deleting vntype files from moms")
        ret = self.du.rm(hostname=self.momA, path=vntype_file,
                         force=True, sudo=True, logerr=False)
        ret1 = self.du.rm(hostname=self.momB, path=vntype_file,
                          force=True, sudo=True, logerr=False)
        if not (ret or ret1):
            self.skipTest("pbs_cgroups_hook: need root privileges")

    def get_vntype(self, mom):
        """
        Get the vntype if it exists for example on cray
        """
        vntype = "no_cgroups"
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_f = os.path.join(pbs_home, 'mom_priv', 'vntype')
        self.logger.info("Reading the vntype value for mom %s" % mom)
        if self.du.isfile(hostname=mom, path=vntype_f):
            output = self.du.cat(hostname=mom, filename=vntype_f, sudo=True)
            vntype = output['out'][0]
        return vntype

    def wait_and_remove_file(self, mom, filename=''):
        """
        Wait up to ten seconds for a file to appear and then remove it.
        """
        self.logger.info("Removing file: %s on mom: %s" % (filename, mom))
        if not filename:
            raise ValueError('Invalid filename')
        for _ in range(10):
            if not self.du.isfile(hostname=mom, path=filename):
                break
            try:
                self.du.rm(hostname=mom, path=filename,
                           force=True, sudo=True, runas=TEST_USER)
            except:
                time.sleep(1)
        self.assertFalse(self.du.isfile(hostname=mom, path=filename),
                         "File not removed: %s" % filename)

    def wait_and_read_file(self, mom, filepath=''):
        """
        Wait up to ten seconds for a file to appear and then read it.
        """
        self.logger.info("Reading file: %s on mom: %s" % (filepath, mom))
        if not filepath:
            raise ValueError('Invalid filename')
        for _ in range(30):
            if self.du.isfile(hostname=mom, path=filepath):
                break
            time.sleep(1)
        self.assertTrue(self.du.isfile(hostname=mom, path=filepath),
                        "File %s not found on mom %s" % (filepath, mom))
        output = self.du.cat(hostname=mom, filename=filepath, sudo=True)
        return output['out']

    def get_hostname(self, mom):
        """
        get short hostname of the mom.
        This is needed since cgroups logs hostname not mom name
        """

        cmd = "hostname"
        rv = self.du.run_cmd(hosts=mom, cmd=cmd)
        host = rv['out'][0].split('.')[0]
        return host

    def get_host_names(self, mom):
        """
        get shortname and hostname of the mom. This is needed
        for some systems where hostname and shortname is different.
        """
        cmd1 = "hostname -s"
        rv1 = self.du.run_cmd(hosts=mom, cmd=cmd1)
        host2 = self.get_hostname(mom)
        hostlist = '"' + host2 + '"'
        moms = [hostlist]
        mlog = ["'" + host2 + "'"]

        # if shortname and hostname is not same then construct a
        # list including both to be passed to cgroups hook
        if (str(rv1['out'][0]) != host2):
            moms.append('"' + str(rv1['out'][0]) + '"')
            mlog.append("'" + str(rv1['out'][0]) + "'")
        if len(moms) > 1:
            mom1 = ','.join(moms)
            log1 = ', '.join(mlog)
        else:
            mom1 = '"' + host2 + '"'
            log1 = "'" + host2 + "'"
        return mom1, log1

    def test_cgroup_vntype_excluded(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have an exclude vntype file set
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest("Test requires two Moms as input, "
                          "use -p moms=<mom1:mom2>")

        name = 'CGROUP8'
        if self.vntypenameA == "no_cgroups":
            self.logger.info("Adding vntype %s to mom %s " %
                             (self.vntypenameA, self.momA))
            self.set_vntype(typestring=self.vntypenameA, mom=self.momA)
        self.load_config(
            self.cfg1
            % ("", '"' + self.vntypenameA + '"', "", "", self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.logger.info("memory subsystem is at location %s" %
                         self.paths['memory'])
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid)
        self.assertFalse(self.is_dir(cpath, self.momA))
        self.hostA.log_match("%s is in the excluded vnode type list: ['%s']"
                             % (self.vntypenameA, self.vntypenameA),
                             starttime=self.server.ctime)
        self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momA)

        self.logger.info("vntypes on both hosts are: %s and %s"
                         % (self.vntypenameA, self.vntypenameB))
        if self.vntypenameB == self.vntypenameA:
            self.logger.info(
                "Skipping the second part of this test"
                " since hostB also has same vntype value")
            return
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momB, ATTR_N: name}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid2 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid2)
        self.assertTrue(self.is_dir(cpath, self.momB))

    def test_cgroup_host_excluded(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have the exclude_hosts set
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest("Test requires two Moms as input, "
                          "use -p moms=<mom1:mom2>")

        name = 'CGROUP9'
        mom, log = self.get_host_names(self.momA)
        self.load_config(self.cfg1 % ('%s' % mom, "", "", "", self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid)
        self.assertFalse(self.is_dir(cpath, self.momA))
        host = self.get_hostname(self.momA)
        self.hostA.log_match("%s is in the excluded host list: [%s]"
                             % (host, log),
                             starttime=self.server.ctime)
        self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momA)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momB, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid2)
        self.assertTrue(self.is_dir(cpath, self.momB))

    def test_cgroup_exclude_vntype_mem(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have an exclude vntype file set
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest("Test requires two Moms as input, "
                          "use -p moms=<mom1:mom2>")

        name = 'CGROUP12'
        if self.vntypenameA == "no_cgroups":
            self.logger.info("Adding vntype %s to mom %s " %
                             (self.vntypenameA, self.momA))
            self.set_vntype(typestring="no_cgroups", mom=self.momA)
        self.load_config(self.cfg3 % (
            "", "", '"' + self.vntypenameA + '"', self.swapctl,
            '"' + self.vntypenameA + '"'))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s'
             % self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.hostA.log_match("cgroup excluded for subsystem memory "
                             "on vnode type %s" % self.vntypenameA,
                             starttime=self.server.ctime)
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid)
        self.assertFalse(self.is_dir(cpath, self.momA))

        self.logger.info("vntype values for each hosts are: %s and %s"
                         % (self.vntypenameA, self.vntypenameB))
        if self.vntypenameB == self.vntypenameA:
            self.logger.info("Skipping the second part of this test" +
                             " since hostB also has same vntype value")
            return
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momB, ATTR_N: name}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid2 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid2)
        self.assertTrue(self.is_dir(cpath, self.momB))
        self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momA)

    @timeout(600)
    def test_cgroup_periodic_update(self):
        """
        Test to verify that cgroups are reporting usage for cput and mem
        """
        name = 'CGROUP13'
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb:host=%s' %
             self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        if self.paths['cpuacct']:
            self.hostA.log_match("%s;update_job_usage: CPU usage: 0.000 secs"
                                 % jid)
        if self.paths['memory']:
            self.hostA.log_match(
                "%s;update_job_usage: Memory usage: mem=0b" % jid)
            if self.swapctl == "true":
                self.hostA.log_match(
                    "%s;update_job_usage: Memory usage: vmem=0b" % jid)
        # Allow some time to pass for values to be updated
        time.sleep(5)
        if self.paths['cpuacct']:
            self.hostA.log_match(
                "%s;update_job_usage: CPU usage: [0-9.]+ secs" % jid,
                regexp=True)
        if self.paths['memory']:
            self.hostA.log_match(
                "%s;update_job_usage: Memory usage: mem=[1-9][0-9]+kb"
                % jid, regexp=True)
            self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momA)

    def test_cgroup_cpuset_and_memory(self):
        """
        Test to verify that the job cgroup is created correctly
        Check to see that cpuset.cpus=0, cpuset.mems=0 and that
        memory.limit_in_bytes = 314572800
        """
        name = 'CGROUP1'
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             ATTR_N: name, ATTR_k: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.cpuset_mem_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filepath=tmp_file, mom=tmp_host)
        self.logger.info("%s: %s" % (name, tmp_out))
        self.wait_and_remove_file(filename=tmp_file, mom=tmp_host)
        self.assertTrue(jid in tmp_out)
        self.logger.info("job dir check passed")
        if self.paths['cpuacct']:
            self.assertTrue("CpuIDs=0" in tmp_out)
            self.logger.info("CpuIDs check passed")
        if self.paths['memory']:
            self.assertTrue("MemorySocket=0" in tmp_out)
            self.logger.info("MemorySocket check passed")
            if self.swapctl == "true":
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
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {'Resource_List.select': '1:ncpus=1:host=%s' %
             self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.cpuset_mem_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filepath=tmp_file, mom=self.momA)
        self.logger.info("output of job is %s" % tmp_out)
        self.wait_and_remove_file(filename=tmp_file, mom=self.momA)
        self.assertTrue(jid in tmp_out)
        self.logger.info("job dir check passed")
        if self.paths['cpuacct']:
            self.assertTrue("CpuIDs=0" in tmp_out)
            self.logger.info("CpuIDs check passed")
        if self.paths['memory']:
            self.assertTrue("MemorySocket=0" in tmp_out)
            self.logger.info("MemorySocket check passed")
            if self.swapctl == "true":
                self.assertTrue("MemoryLimit=268435456" in tmp_out)
                self.assertTrue("MemswLimit=268435456" in tmp_out)
                self.logger.info("MemoryLimit check passed")

    def test_cgroup_prefix_and_devices(self):
        """
        Test to verify that the cgroup prefix is set to pbs and that
        only the devices subsystem is enabled with the correct devices
        allowed
        """
        if not self.paths['devices']:
            self.skipTest("Skipping test since no devices subsystem defined")
        name = "CGROUP3"
        self.load_config(self.cfg2)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.check_dirs_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filepath=tmp_file, mom=tmp_host)
        self.wait_and_remove_file(filename=tmp_file, mom=tmp_host)
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
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momA, ATTR_N: name + 'a'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.cpuset_mem_script)
        jid1 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid1)
        attrib = [ATTR_o, 'exec_host']
        self.server.status(JOB, attrib, jid1)
        filename1 = j1.attributes[ATTR_o]
        ehost1 = j1.attributes['exec_host']
        b = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momA, ATTR_N: name + 'b'}
        j2 = Job(TEST_USER, attrs=b)
        j2.create_script(self.cpuset_mem_script)
        jid2 = self.server.submit(j2)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, attrib, jid2)
        filename2 = j2.attributes[ATTR_o]
        ehost2 = j2.attributes['exec_host']
        self.logger.info("Job1 .o file: %s" % filename1)
        tmp_file1 = filename1.split(':')[1]
        tmp_host1 = ehost1.split('/')[0]
        tmp_out1 = self.wait_and_read_file(filepath=tmp_file1, mom=tmp_host1)
        self.logger.info("tmp_out1: %s" % tmp_out1)
        self.wait_and_remove_file(filename=tmp_file1, mom=tmp_host1)
        self.assertTrue(
            jid1 in tmp_out1, '%s not found in output on host %s'
            % (jid1, tmp_host1))
        self.logger.info("Job2 .o file: %s" % filename2)
        tmp_file2 = filename2.split(':')[1]
        tmp_host2 = ehost2.split('/')[0]
        tmp_out2 = self.wait_and_read_file(filepath=tmp_file2, mom=tmp_host2)
        self.logger.info("tmp_out2: %s" % tmp_out2)
        self.wait_and_remove_file(filename=tmp_file2, mom=tmp_host2)
        self.assertTrue(
            jid2 in tmp_out2, '%s not found in output on host %s'
            % (jid2, tmp_host2))
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
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        # mem and vmem limit will both be set, and either could be detected
        self.hostA.log_match("%s;Cgroup mem(ory|sw) limit exceeded" % jid,
                             regexp=True,
                             max_attempts=20)
        self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momA)

    def test_cgroup_enforce_memsw(self):
        """
        Test to verify that the job is killed when it tries to
        use more vmem then it requested
        """
        # run the test if swap space is available
        if have_swap() == 0:
            self.skipTest("no swap space available on the local host")
        name = 'CGROUP6'
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {
            'Resource_List.select':
            '1:ncpus=1:mem=300mb:vmem=320mb:host=%s' % self.momA,
            ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filepath=tmp_file, mom=tmp_host)
        self.wait_and_remove_file(filename=tmp_file, mom=tmp_host)
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
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' % self.momA,
             'Resource_List.walltime': 3, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        tmp_file = filename.split(':')[1]

        # Query the pids in the cgroup
        tasks_file = os.path.join(self.paths['cpuset'], 'pbspro', jid, 'tasks')
        ret = self.du.cat(self.momA, tasks_file, sudo=True)
        tasks = ret['out']
        self.logger.info("Tasks: %s" % tasks)
        self.assertTrue(tasks, "No tasks in cpuset cgroup for job")

        # Make dir in freezer subsystem
        fdir = os.path.join(fdir, 'PtlPbs')
        if not self.du.isdir(fdir):
            self.du.mkdir(hostname=self.momA, path=fdir,
                          mode=0755, sudo=True)
        fdir = os.path.join(fdir, jid)
        if not os.path.isdir(fdir):
            self.du.mkdir(hostname=self.momA, path=fdir,
                          mode=0755, sudo=True)
        self.logger.info("Server name: %s" % self.server.name)
        self.logger.info("tasks: %s" % tasks)
        # Write each PID into the tasks file for the freezer cgroup
        task_file = os.path.join(fdir, 'tasks')
        for task in tasks[1:]:
            fn = self.du.create_temp_file(hostname=self.serverA, body=task)
            self.tempfile.append(fn)
            ret = self.du.run_copy(self.momA, src=fn,
                                   dest=task_file, sudo=True,
                                   uid='root', gid='root',
                                   mode=0644)
            if ret['rc'] != 0:
                self.skipTest("pbs_cgroups_hook: need root privileges")
        # Freeze the cgroup
        freezer_file = os.path.join(fdir, 'freezer.state')
        state = 'FROZEN'
        fn = self.du.create_temp_file(hostname=self.serverA, body=state)
        self.tempfile.append(fn)
        ret = self.du.run_copy(self.momA, src=fn,
                               dest=freezer_file, sudo=True,
                               uid='root', gid='root',
                               mode=0644)
        if ret['rc'] != 0:
            self.skipTest("pbs_cgroups_hook: need root privileges")
        self.server.expect(NODE, {'state': (MATCH_RE, 'offline')},
                           id=self.momA, interval=3)
        # Thaw the cgroup
        state = 'THAWED'
        fn = self.du.create_temp_file(hostname=self.serverA, body=state)
        self.tempfile.append(fn)
        ret = self.du.run_copy(self.momA, src=fn,
                               dest=freezer_file, sudo=True,
                               uid='root', gid='root',
                               mode=0644)

        if ret['rc'] != 0:
            self.skipTest("pbs_cgroups_hook: need root privileges")
        time.sleep(1)
        self.du.rm(hostname=self.momA, path=os.path.dirname(fdir),
                   force=True, recursive=True, sudo=True)
        self.server.expect(NODE, {'state': 'free'},
                           id=self.momA, interval=3)
        self.wait_and_remove_file(filename=tmp_file, mom=self.momA)

    def test_cgroup_cpuset_host_excluded(self):
        """
        Test to verify that cgroups subsystems are not enforced on nodes
        that have the exclude_hosts set but are enforced on other systems
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest("Test requires two Moms as input, " +
                          "use -p moms=<mom1:mom2>")

        name = 'CGROUP10'
        momn = self.get_host_names(self.momA)
        self.load_config(
            self.cfg1 % ("", "", "", '%s' % momn[0], self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        hostn = self.get_hostname(self.momA)
        self.hostA.log_match("cgroup excluded for subsystem cpuset "
                             "on host %s" % hostn,
                             starttime=self.server.ctime)
        self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momA)
        cpath = os.path.join(self.paths['cpuset'], 'pbspro', jid)
        self.assertFalse(self.is_dir(cpath, self.momA))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momB, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        cpath = os.path.join(self.paths['cpuset'], 'pbspro', jid2)
        self.assertTrue(self.is_dir(cpath, self.momB))

    def test_cgroup_run_on_host(self):
        """
        Test to verify that the cgroup hook only runs on nodes
        in the run_only_on_hosts
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest("Test requires two Moms as input, " +
                          "use -p moms=<mom1:mom2>")

        name = 'CGROUP11'
        mom, log = self.get_host_names(self.momA)
        self.load_config(self.cfg1 % ("", "", '%s' % mom, "", self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momB, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        time.sleep(1)
        hostn = self.get_hostname(self.momB)
        self.hostB.log_match("%s is not in the approved host list: [%s]"
                             % (hostn, log),
                             starttime=self.server.ctime)
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid)
        self.assertFalse(self.is_dir(cpath, self.momB))
        self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momB)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.momA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j.attributes[ATTR_o]
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid2)
        self.assertTrue(self.is_dir(cpath, self.momA))
        self.wait_and_remove_file(filename=o.split(':')[1], mom=self.momA)

    def test_cgroup_qstat_resources(self):
        """
        Test to verify that cgroups are reporting usage for
        mem, and vmem in qstat
        """
        name = 'CGROUP14'
        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job2)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        o = j.attributes[ATTR_o]
        host = j.attributes['exec_host']
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
        self.wait_and_remove_file(
            filename=o.split(':')[1], mom=host.split('/')[0])
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
        if self.iscray:
            self.skipTest("Test is skipped on cray due to PTL errors")

        self.load_config(self.cfg3 % ("", "", "", self.swapctl, ""))
        self.hostA.stop()
        self.server.expect(NODE, {'state': 'down'},
                           self.hostA.shortname, interval=3)
        self.hostA.start()
        self.server.expect(NODE, {'state': 'free'},
                           self.hostA.shortname, interval=3)
        if self.swapctl == "true":
            vmem = self.server.status(NODE, 'resources_available.vmem')
            self.logger.info("vmem: %s" % str(vmem))
            vmem1 = PbsTypeSize(vmem[0]['resources_available.vmem'])
            self.logger.info("Vmem-1: %s" % vmem1.value)
        mem = self.server.status(NODE, 'resources_available.mem')
        mem1 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info("Mem-1: %s" % mem1.value)
        self.load_config(self.cfg4 % (self.swapctl))
        self.hostA.stop()
        self.server.expect(NODE, {'state': 'down'},
                           self.hostA.shortname, interval=3)
        self.hostA.start()
        self.server.expect(NODE, {'state': 'free'},
                           self.hostA.shortname, interval=3)
        if self.swapctl == "true":
            vmem = self.server.status(NODE, 'resources_available.vmem')
            vmem2 = PbsTypeSize(vmem[0]['resources_available.vmem'])
            self.logger.info("Vmem-2: %s" % vmem2.value)
            vmem_resv = vmem1 - vmem2
            self.logger.info("Vmem resv: %s" % vmem_resv.value)
            self.assertEqual(vmem_resv.value, 97280)
            self.assertEqual(vmem_resv.unit, 'kb')
        mem = self.server.status(NODE, 'resources_available.mem')
        mem2 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info("Mem-2: %s" % mem2.value)
        mem_resv = mem1 - mem2
        self.logger.info("Mem resv: %s" % mem_resv.value)
        self.assertEqual(mem_resv.value, 51200)
        self.assertEqual(mem_resv.unit, 'kb')

    def test_cgroup_multi_node(self):
        """
        Test that multi-node jobs with cgroups works fine
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest("Test requires two Moms as input, " +
                          "use -p moms=<mom1:mom2>")

        name = 'CGROUP16'
        self.load_config(self.cfg1 % ("", "", "", "", self.swapctl))
        a = {'Resource_List.select': '2:ncpus=1:mem=300mb',
             'Resource_List.place': 'scatter', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)

        self.server.status(JOB, 'exec_host', jid)
        ehost = j.attributes['exec_host']
        tmp_host = ehost.split('+')
        ehost1 = tmp_host[0].split('/')[0]
        ehost2 = tmp_host[1].split('/')[0]

        cpath = os.path.join(self.paths['memory'], 'pbspro', jid)
        self.assertTrue(self.is_dir(cpath, ehost1))
        self.assertTrue(self.is_dir(cpath, ehost2))

        # Wait for job to finish and make sure that cgroup directories
        # has been cleaned up by the hook
        self.server.expect(
            JOB, 'queue', op=UNSET, offset=15, interval=1, id=jid)
        self.assertFalse(self.is_dir(cpath, ehost1))
        self.assertFalse(self.is_dir(cpath, ehost2))

    def test_cgroup_job_array(self):
        """
        Test that cgroups are created for subjobs like
        a regular job
        """
        name = 'CGROUP17'
        self.load_config(self.cfg1 % ("", "", "", "", self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' % self.momA,
             ATTR_N: name,
             ATTR_J: "1-4",
             'Resource_List.place': "pack:excl"}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(60)
        jid = self.server.submit(j)
        a = {'job_state': 'B'}
        self.server.expect(JOB, a, jid)
        # Get subjob ID
        subj1 = jid.replace('[]', '[1]')
        self.server.expect(JOB, {'job_state': 'R'}, subj1)
        rv = self.server.status(JOB, ['exec_host'], subj1)
        ehost = rv[0].get('exec_host')
        ehost1 = ehost.split('/')[0]
        # Verify that cgroups files created for subjobs
        # but not for parent job array
        cpath = os.path.join(self.paths['memory'], 'pbspro', subj1)
        self.assertTrue(self.is_dir(cpath, ehost1))
        cpath = os.path.join(self.paths['memory'], 'pbspro', jid)
        self.assertFalse(self.is_dir(cpath, ehost1))

        # Verify that subjob4 is queued and no cgroups
        # files are created for queued subjob
        subj4 = jid.replace('[]', '[4]')
        self.server.expect(JOB, {'job_state': 'Q'}, id=subj4)
        cpath = os.path.join(self.paths['cpuset'], 'pbspro', subj4)
        self.assertFalse(self.is_dir(cpath, self.momA))

        # Delete subjob1 and verify that cgroups files are cleaned up
        self.server.delete(id=subj1)
        self.server.expect(JOB, {'job_state': 'X'}, subj1)
        cpath = os.path.join(self.paths['memory'], 'pbspro', subj1)
        self.assertFalse(self.is_dir(cpath, ehost1))

        # Verify if subjob2 is running
        subj2 = jid.replace('[]', '[2]')
        self.server.expect(JOB, {'job_state': 'R'}, id=subj2)
        # Force delete the subjob and verify cgroups
        # files are cleaned up
        self.server.delete(id=subj2, extend="force")
        self.server.expect(JOB, {'job_state': 'X'}, subj2)
        # Adding extra sleep for file to clean up
        time.sleep(2)
        cpath = os.path.join(self.paths['memory'], 'pbspro', subj2)
        self.assertFalse(self.is_dir(cpath, self.momA))

    def test_cgroup_cleanup(self):
        """
        Test that cgroups files are cleaned up after qdel
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest("Test requires two Moms as input, " +
                          "use -p moms=<mom1:mom2>")

        hook_body = """
import pbs
import time
time.sleep(20)
"""
        a = {'event': "execjob_prologue", "enabled": "True"}
        self.server.create_import_hook("pro", a, hook_body)
        self.load_config(self.cfg1 % ("", "", "", "", self.swapctl))
        a = {'Resource_List.select': '2:ncpus=1:mem=300mb',
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'substate': '41'}
        self.server.expect(JOB, a, jid)

        self.server.status(JOB, ['exec_host'], jid)
        ehost = j.attributes['exec_host']
        tmp_host = ehost.split('+')
        ehost1 = tmp_host[0].split('/')[0]
        ehost2 = tmp_host[1].split('/')[0]
        # Adding delay for cgroups files to get created
        time.sleep(1)
        cpath = os.path.join(self.paths['cpuset'], 'pbspro', jid)
        self.assertTrue(self.is_dir(cpath, ehost1))
        self.assertTrue(self.is_dir(cpath, ehost2))

        self.server.delete(id=jid, wait=True)

        self.assertFalse(self.is_dir(cpath, ehost1))
        self.assertFalse(self.is_dir(cpath, ehost2))

    def test_cgroup_execjob_end_should_delete_cgroup(self):
        """
        Test to verify that if execjob_epilogue hook failed to run or to
        clean up cgroup files for a job, execjob_end hook should clean them up
        """
        self.load_config(self.cfg4 % (self.swapctl))
        # remove epilogue and periodic from the list of events
        attr = {'enabled': 'True', 'event': '"execjob_begin,execjob_launch,\
execjob_attach,execjob_end,exechost_startup"'}
        self.server.manager(MGR_CMD_SET, HOOK, attr, self.hook_name)
        self.server.expect(NODE, {'state': 'free'})
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid = self.server.submit(j)
        # wait for job to finish
        self.server.expect(JOB, 'queue', id=jid, op=UNSET, max_attempts=20,
                           interval=1, offset=1)
        # verify that cgroup files for this job are gone even if
        # epilogue and periodic events are not disabled
        for subsys, path in self.paths.items():
            # only check under subsystems that are enabled
            enabled_subsys = ['cpuacct', 'cpuset', 'memory', 'memsw']
            if (any([x in subsys for x in enabled_subsys])):
                continue
            if path:
                filename = os.path.join(path, 'pbspro', str(jid))
                self.logger.info("Checking that file %s should not exist"
                                 % filename)
                self.assertFalse(os.path.isfile(filename))

    def test_cgroup_assign_resources_mem_only_vnode(self):
        """
        Test to verify that job requesting mem larger than any single vnode
        works properly
        """
        vn_attrs = {ATTR_rescavail + '.ncpus': 1,
                    ATTR_rescavail + '.mem': '500mb'}
        self.server.create_vnodes('vnode', vn_attrs, 2, self.moms.values()[0],
                                  expect=False)
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=self.moms.values()[0].shortname)

        self.load_config(self.cfg4 % (self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script('date')
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, 'queue', id=jid1, op=UNSET, max_attempts=20,
                           interval=1, offset=1)
        a = {'Resource_List.select': '1:ncpus=1:mem=1gb'}
        j2 = Job(TEST_USER, attrs=a)
        j2.create_script('date')
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, 'queue', id=jid2, op=UNSET, max_attempts=30,
                           interval=1, offset=1)
        a = {'Resource_List.select': '1:ncpus=1:mem=40gb'}
        j3 = Job(TEST_USER, attrs=a)
        j3.create_script('date')
        jid3 = self.server.submit(j3)

        a = {'job_state': 'Q',
             'comment':
             (MATCH_RE,
              '.*Can Never Run: Insufficient amount of resource: mem.*')}
        self.server.expect(JOB, a, attrop=PTL_AND, id=jid3, offset=10,
                           interval=1, max_attempts=30)

    def tearDown(self):
        TestFunctional.tearDown(self)
        self.load_config(self.cfg0)
        if not self.iscray:
            self.remove_vntype()
        events = '"execjob_begin,execjob_launch,execjob_attach,'
        events += 'execjob_epilogue,execjob_end,exechost_startup,'
        events += 'exechost_periodic"'
        # Disable the cgroups hook
        conf = {'enabled': 'False', 'freq': 30, 'event': events}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        # Cleanup any temp file created
        self.logger.info("Deleting temporary files %s" % self.tempfile)
        self.du.rm(hostname=self.serverA, path=self.tempfile,
                   force=True)
        # Cleanup frozen jobs
        if 'freezer' in self.paths:
            self.logger.info("Cleaning up frozen jobs ****")
            fdir = self.paths['freezer']
            if os.path.isdir(fdir):
                fpath = os.path.join(fdir, 'PtlPbs')
                if os.path.isdir(fpath):
                    jid = glob(os.path.join(fpath, "*", ""))
                    if jid:
                        for files in jid:
                            self.logger.info("*** found jobdir %s" % files)
                            jpath = os.path.join(fpath, files)
                            freezer_file = os.path.join(jpath, 'freezer.state')
                            # Thaw the cgroup
                            state = 'THAWED'
                            fn = self.du.create_temp_file(
                                hostname=self.momA, body=state)
                            self.du.run_copy(hosts=self.momA, src=fn,
                                             dest=freezer_file, sudo=True,
                                             uid='root', gid='root',
                                             mode=0644)
                            self.du.rm(hostname=self.momA, path=fn)
                            cmd = ["rmdir", jpath]
                            self.logger.info("deleting jobdir %s" % cmd)
                            self.du.run_cmd(cmd=cmd, sudo=True)
        # Remove the jobdir if any under other cgroups
        cgroup_subsys = ('cpuset', 'memory')
        for subsys in cgroup_subsys:
            self.logger.info("Looking for orphaned jobdir in %s" % subsys)
            if self.paths[subsys]:
                cdir = self.paths['cpuset']
                if os.path.isdir(cdir):
                    cpath = os.path.join(cdir, 'pbspro')
                    if os.path.isdir(cpath):
                        jid = glob(os.path.join(cpath, "*", ""))
                        if jid:
                            for files in jid:
                                self.logger.info("***Found jobid %s" % files)
                                jdir = os.path.join(cpath, files)
                                cmd2 = ["rmdir", jdir]
                                self.logger.info("deleting jobdir %s" % cmd2)
                                self.du.run_cmd(cmd=cmd2, sudo=True)

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
import glob


def have_swap():
    """
    Returns 1 if swap space is not 0 otherwise returns 0
    """
    tt = 0
    with open(os.path.join(os.sep, 'proc', 'meminfo'), 'r') as fd:
        for line in fd:
            entry = line.split()
            if ((entry[0] == 'SwapFree:') and (entry[1] != '0')):
                tt = 1
    return tt


def is_memsw_enabled(mem_path):
    """
    Check if system has swapcontrol enabled, then return true
    else return false
    """
    # List all files and check if memsw files exists
    for files in os.listdir(mem_path):
        if 'memory.memsw' in files:
            return 'true'
    return 'false'


def systemd_escape(buf):
    """
    Escape strings for usage in system unit names
    Some distros don't provide the systemd-escape command
    """
    if not isinstance(buf, basestring):
        raise ValueError('Not a basetype string')
    ret = ''
    for i, char in enumerate(buf):
        if i < 1 and char == '.':
            ret += '\\x' + char.encode('hex')
            continue
        if char.isalnum() or char in '_.':
            ret += char
        elif char == '/':
            ret += '-'
        else:
            hexval = char.encode('hex')
            for j in range(0, len(hexval), 2):
                ret += '\\x' + hexval[j:j + 2]
    return ret


@tags('mom', 'multi_node')
class TestCgroupsHook(TestFunctional):

    """
    This test suite targets Linux Cgroups hook functionality.
    """

    def setUp(self):
        TestFunctional.setUp(self)

        # Some of the tests requires 2 nodes.
        # Hence setting the values to default when no mom is specified

        self.vntypenameA = 'no_cgroups'
        self.vntypenameB = self.vntypenameA
        self.iscray = False
        self.noprefix = False
        self.tempfile = []
        if self.moms:
            if len(self.moms) == 1:
                self.momA = self.moms.values()[0]
                self.momB = self.momA
                if self.momA.is_cray():
                    self.iscray = True
                self.hostA = self.momA.shortname
                self.hostB = self.hostA
                if self.iscray:
                    self.nodeA = self.get_hostname(self.momA.shortname)
                    self.nodeB = self.hostA
                else:
                    self.nodeA = self.momA.shortname
                    self.nodeB = self.hostA
                self.vntypenameA = self.get_vntype(self.hostA)
                self.vntypenameB = self.vntypenameA
                self.momA.delete_vnode_defs()
                self.server.manager(MGR_CMD_DELETE, NODE, None, "")
                self.server.manager(MGR_CMD_CREATE, NODE, id=self.hostA)
            elif len(self.moms) == 2:
                self.momA = self.moms.values()[0]
                self.momB = self.moms.values()[1]
                if self.momA.is_cray() or self.momB.is_cray():
                    self.iscray = True
                self.hostA = self.momA.shortname
                self.hostB = self.momB.shortname
                if self.iscray:
                    self.nodeA = self.get_hostname(self.momA.shortname)
                    self.nodeB = self.get_hostname(self.momB.shortname)
                else:
                    self.nodeA = self.momA.shortname
                    self.nodeB = self.momB.shortname
                self.vntypenameA = self.get_vntype(self.hostA)
                self.vntypenameB = self.get_vntype(self.hostB)
                if self.momA.is_cray() or self.momB.is_cray():
                    self.iscray = True
                self.momA.delete_vnode_defs()
                self.momB.delete_vnode_defs()
                self.server.manager(MGR_CMD_DELETE, NODE, None, "")
                self.server.manager(MGR_CMD_CREATE, NODE, id=self.nodeA)
                self.server.manager(MGR_CMD_CREATE, NODE, id=self.nodeB)
            else:
                self.skipTest('Tests require one or two MoMs, '
                              'use -p moms=<mom1>:<mom2>')
        self.serverA = self.servers.values()[0].name
        self.paths = self.get_paths()
        if not (self.paths['cpuset'] and self.paths['memory']):
            self.skipTest('cpuset or memory cgroup subsystem not mounted')
        self.swapctl = is_memsw_enabled(self.paths['memsw'])
        self.server.set_op_mode(PTL_CLI)
        self.server.cleanup_jobs(extend='force')
        if not self.iscray:
            self.remove_vntype()

        self.eatmem_script = """
import sys
import time
MB = 2 ** 20
iterations = 1
chunkSizeMb = 1
sleeptime = 0
if (len(sys.argv) > 1):
    iterations = int(sys.argv[1])
if (len(sys.argv) > 2):
    chunkSizeMb = int(sys.argv[2])
if (len(sys.argv) > 3):
    sleeptime = int(sys.argv[3])
if (iterations < 1):
    print('Iteration count must be greater than zero.')
    exit(1)
if (chunkSizeMb < 1):
    print('Chunk size must be greater than zero.')
    exit(1)
totalSizeMb = chunkSizeMb * iterations
print('Allocating %d chunk(s) of size %dMB. (%dMB total)' %
      (iterations, chunkSizeMb, totalSizeMb))
buf = ''
for i in range(iterations):
    print('allocating %dMB' % ((i + 1) * chunkSizeMb))
    buf += ('#' * MB * chunkSizeMb)
if sleeptime > 0:
    time.sleep(sleeptime)
"""
        self.eatmem_job1 = \
            '#PBS -joe\n' \
            '#PBS -S /bin/bash\n' \
            'sleep 4\n' \
            'python - 80 10 10 <<EOF\n' \
            '%s\nEOF\n' % self.eatmem_script
        self.eatmem_job2 = \
            '#PBS -joe\n' \
            '#PBS -S /bin/bash\n' \
            'let i=0; while [ $i -lt 400000 ]; do let i+=1 ; done\n' \
            'python - 200 2 10 <<EOF\n' \
            '%s EOF\n' \
            'let i=0; while [ $i -lt 400000 ]; do let i+=1 ; done\n' \
            'python - 100 4 10 <<EOF\n' \
            '%sEOF\n' \
            'let i=0; while [ $i -lt 400000 ]; do let i+=1 ; done\n' \
            'sleep 25\n' % (self.eatmem_script, self.eatmem_script)
        self.eatmem_job3 = \
            '#PBS -joe\n' \
            '#PBS -S /bin/bash\n' \
            'sleep 2\n' \
            'let i=0; while [ $i -lt 500000 ]; do let i+=1 ; done\n' \
            'python - 90 5 30 <<EOF\n' \
            '%s\nEOF\n' % self.eatmem_script
        self.cpuset_mem_script = """#!/bin/bash
#PBS -joe
echo $PBS_JOBID
cpuset_base=`grep cgroup /proc/mounts | grep cpuset | cut -d' ' -f2 | \
             tr " " "\n" | sed -n '1p'`
if [ -z "$cpuset_base" ]; then
    echo "Cpuset subsystem not mounted."
    exit 1
fi
memory_base=`grep cgroup /proc/mounts | grep memory | cut -d' ' -f2 | \
             tr " " "\n" | sed -n '1p'`
if [ -z "$memory_base" ]; then
    echo "Memory subsystem not mounted."
    exit 1
fi
echo "cpuset_base is $cpuset_base"
if [ -d "$cpuset_base/pbspro" ]; then
    base="$cpuset_base/pbspro/$PBS_JOBID"
else
    jobnum=${PBS_JOBID%%.*}
    base="$cpuset_base/pbspro.slice/pbspro-${jobnum}.*.slice"
fi
echo "cgroups base path for cpuset is $base"
if [ -d $base ]; then
    cpupath1=$base/cpuset.cpus
    cpupath2=$base/cpus
    if [ -f $cpupath1 ]; then
        cpus=`cat $cpupath1`
    elif [ -f $cpupath2 ]; then
        cpus=`cat $cpupath2`
    fi
    echo "CpuIDs=${cpus}"
    mempath1="$base/cpuset.mems"
    mempath2="$base/mems"
    if [ -f $mempath1 ]; then
        mems=`cat $mempath1`
    elif [ -f $mempath2 ]; then
        mems=`cat $mempath2`
    fi
    echo "MemorySocket=${mems}"
else
    echo "Cpuset subsystem job directory not created."
fi
if [ -d "$memory_base/pbspro" ]; then
    base="$memory_base/pbspro/$PBS_JOBID"
else
    jobnum=${PBS_JOBID%%.*}
    base="$memory_base/pbspro.slice/pbspro-${jobnum}.*.slice"
fi
echo "cgroups base path for memory is $base"
if [ -d $base ]; then
   mem_limit=`cat $base/memory.limit_in_bytes`
   echo "MemoryLimit=${mem_limit}"
   memsw_limit=`cat $base/memory.memsw.limit_in_bytes`
   echo "MemswLimit=${memsw_limit}"
else
    echo "Memory subsystem job directory not created."
fi
sleep 10
"""
        self.check_dirs_script = """#!/bin/bash
#PBS -joe

check_file_diff() {
    for filename in $1/*.*; do
        filename=$(basename $filename)
        [ $filename = memory.kmem.slabinfo ] && continue
        [ ! -r $1/$filename ] && continue
        [ ! -r $2/$filename ] && continue
        if ! diff $1/$filename $2/$filename >/dev/null ; then
            echo "Disabled cgroup subsystems are populated with the job id"
        fi
    done
}

jobnum=${PBS_JOBID%%.*}
cpuset_base=`grep cgroup /proc/mounts | grep cpuset | cut -d' ' -f2`
if [ -d "$cpuset_base/propbs" ]; then
    cpuset_job="$cpuset_base/propbs/$PBS_JOBID"
else
    cpuset_job="$cpuset_base/propbs.slice/propbs-${jobnum}.*.slice"
fi
cpuacct_base=`grep cgroup /proc/mounts | grep cpuacct | cut -d' ' -f2`
if [ -d "$cpuacct_base/propbs" ]; then
    cpuacct_job="$cpuacct_base/propbs/$PBS_JOBID"
else
    cpuacct_job="$cpuacct_base/propbs.slice/propbs-${jobnum}.*.slice"
fi
memory_base=`grep cgroup /proc/mounts | grep memory | cut -d' ' -f2`
if [ -d "$memory_base/propbs" ]; then
    memory_job="$memory_base/propbs/$PBS_JOBID"
else
    memory_job="$memory_base/propbs.slice/propbs-${jobnum}.*.slice"
fi
devices_base=`grep cgroup /proc/mounts | grep devices | cut -d' ' -f2`
if [ -d "$devices_base/propbs" ]; then
    devices_job="$devices_base/propbs/$PBS_JOBID"
else
    devices_job="$devices_base/propbs.slice/propbs-${jobnum}.*.slice"
fi
echo ====
ls -l $devices_base
echo ====
ls -l $devices_job
echo ====
if [ -d $devices_job ]; then
    device_list=`cat $devices_job/devices.list`
    echo "${device_list}"
    sysd=`systemctl --version | grep systemd | awk '{print $2}'`
    if [ "$sysd" -ge 205 ]; then
        if [ -d $cpuacct_job ]; then
            check_file_diff $cpuacct_base/propbs.slice/ $cpuacct_job
        fi
        if [ -d $cpuset_job ]; then
            check_file_diff $cpuset_base/propbs.slice/ $cpuset_job
        fi
        if [ -d $memory_job ] ; then
            check_file_diff $memory_base/propbs.slice/ $memory_job
        fi
    else
        if [ -d $cpuacct_job -o -d $cpuset_job -o -d $memory_job ]; then
            echo "Disabled cgroup subsystems are populated with the job id"
        fi
    fi
else
    echo "Devices directory should be populated"
fi
sleep 10
"""
        self.check_gpu_script = """#!/bin/bash
#PBS -joe

jobnum=${PBS_JOBID%%.*}
devices_base=`grep cgroup /proc/mounts | grep devices | cut -d' ' -f2`
if [ -d "$devices_base/propbs" ]; then
    devices_job="$devices_base/propbs/$PBS_JOBID"
else
    devices_job="$devices_base/propbs.slice/propbs-${jobnum}.*.slice"
fi
device_list=`cat $devices_job/devices.list`
grep "195" $devices_job/devices.list
echo "There are `nvidia-smi -q -x | grep "GPU" | wc -l` GPUs"
sleep 10
"""
        self.sleep15_job = """#!/bin/bash
#PBS -joe
sleep 15
"""
        self.sleep5_job = """#!/bin/bash
#PBS -joe
sleep 5
"""
        self.eat_cpu_script = """#!/bin/bash
#PBS -joe
for i in 1 2 3 4; do while : ; do : ; done & done
"""
        self.job_scr2 = """#!/bin/bash
#PBS -l select=host=%s:ncpus=1+ncpus=4:mem=2gb
#PBS -l place=vscatter
#PBS -W umask=022
#PBS -koe
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
sleep 300
""" % self.hostB
        self.job_scr3 = """#!/bin/bash
#PBS -l select=2:ncpus=4:mem=2gb
#PBS -l place=pack
#PBS -W umask=022
#PBS -W tolerate_node_failures=job_start
#PBS -koe
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
sleep 300
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
            "default"         : "96MB",
            "reserve_percent" : "0",
            "reserve_amount"  : "0MB"
        },
        "memsw":
        {
            "enabled"         : %s,
            "exclude_hosts"   : [],
            "exclude_vntypes" : [],
            "default"         : "96MB",
            "reserve_percent" : "0",
            "reserve_amount"  : "128MB"
        }
    }
}
"""
        self.cfg2 = """{
    "cgroup_prefix"         : "propbs",
    "exclude_hosts"         : [],
    "exclude_vntypes"       : [],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : false,
    "vnode_per_numa_node"   : false,
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
    "use_hyperthreads"      : true,
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
            "default"         : "96MB",
            "reserve_amount"  : "50MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : [%s]
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "96MB",
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
            "default"         : "96MB",
            "reserve_amount"  : "100MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : ["no_cgroups_mem"]
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "96MB",
            "reserve_amount"  : "90MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        }
    }
}
"""
        self.cfg5 = """{
    "vnode_per_numa_node" : %s,
    "cgroup" : {
        "cpuset" : {
            "enabled"            : true,
            "exclude_cpus"       : [%s],
            "mem_fences"         : %s,
            "mem_hardwall"       : %s,
            "memory_spread_page" : %s
        },
        "memory" : {
            "enabled" : true
        },
        "memsw" : {
            "enabled" : %s
        }
    }
}
"""
        self.cfg6 = """{
    "vnode_per_numa_node" : false,
    "cgroup" : {
        "memory":
        {
            "enabled"         : true,
            "default"         : "64MB",
            "reserve_percent" : "0",
            "reserve_amount"  : "0MB"
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "64MB",
            "reserve_percent" : "0",
            "reserve_amount"  : "0MB"
        }
    }
}
"""
        self.cfg7 = """{
    "cgroup_prefix"         : "pbspro",
    "exclude_hosts"         : [],
    "exclude_vntypes"       : [],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : true,
    "vnode_per_numa_node"   : true,
    "online_offlined_nodes" : true,
    "use_hyperthreads"      : false,
    "cgroup" : {
        "cpuacct" : {
            "enabled"            : true,
            "exclude_hosts"      : [],
            "exclude_vntypes"    : []
        },
        "cpuset" : {
            "enabled"            : true,
            "exclude_cpus"       : [],
            "exclude_hosts"      : [],
            "exclude_vntypes"    : []
        },
        "devices" : {
            "enabled"            : false
        },
        "hugetlb" : {
            "enabled"            : false
        },
        "memory" : {
            "enabled"            : true,
            "exclude_hosts"      : [],
            "exclude_vntypes"    : [],
            "default"            : "256MB",
            "reserve_amount"     : "64MB"
        },
        "memsw" : {
            "enabled"            : true,
            "exclude_hosts"      : [],
            "exclude_vntypes"    : [],
            "default"            : "256MB",
            "reserve_amount"     : "64MB"
        }
    }
}
"""
        Job.dflt_attributes[ATTR_k] = 'oe'
        # Increase the log level
        a = {'log_events': '4095'}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)
        # Configure the scheduler to schedule using vmem
        a = {'resources': 'ncpus,mem,vmem,host,vnode,ngpus,nmics'}
        self.scheduler.set_sched_config(a)
        # Configure the mom
        c = {'$logevent': '0xffffffff', '$clienthost': self.server.name,
             '$min_check_poll': 8, '$max_check_poll': 12}
        self.momA.add_config(c)
        if self.hostA != self.hostB:
            self.momB.add_config(c)
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
        events += 'exechost_periodic,execjob_resize"'
        # Enable the cgroups hook
        conf = {'enabled': 'True', 'freq': 10, 'alarm': 30, 'event': events}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        # Restart mom so exechost_startup hook is run
        self.momA.signal('-HUP')
        if self.hostA != self.hostB:
            self.momB.signal('-HUP')
        self.logger.info('vntype set for %s is %s' %
                         (self.momA, self.vntypenameA))
        self.logger.info('vntype set for %s is %s' %
                         (self.momB, self.vntypenameB))

        # queuejob hook
        self.qjob_hook_body = """
import pbs
e=pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "queuejob hook executed")
# Save current select spec in resource 'site'
e.job.Resource_List["site"] = str(e.job.Resource_List["select"])

# Add 1 chunk to each chunk (except the first chunk) in the job's select s
new_select = e.job.Resource_List["select"].increment_chunks(1)
e.job.Resource_List["select"] = new_select

# Make job tolerate node failures that occur only during start.
e.job.tolerate_node_failures = "job_start"
"""
        # launch hook
        self.launch_hook_body = """
import pbs
import time
e=pbs.event()

pbs.logmsg(pbs.LOG_DEBUG, "Executing launch")

# print out the vnode_list[] values
for vn in e.vnode_list:
    v = e.vnode_list[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list[" + v.name + "]")

# print out the vnode_list_fail[] values:
for vn in e.vnode_list_fail:
    v = e.vnode_list_fail[vn]
    pbs.logjobmsg(e.job.id, "launch: found vnode_list_fail[" + v.name + "]")
if e.job.in_ms_mom():
    pj = e.job.release_nodes(keep_select=%s)
    if pj is None:
        e.job.Hold_Types = pbs.hold_types("s")
        e.job.rerun()
        e.reject("unsuccessful at LAUNCH")
"""
        # resize hook
        self.resize_hook_body = """
import pbs
e=pbs.event()
if %s e.job.in_ms_mom():
    e.reject("Cannot resize the job")
"""

    def get_paths(self):
        """
        Returns a dictionary containing the location where each cgroup
        is mounted.
        """
        paths = {'pids': None,
                 'blkio': None,
                 'systemd': None,
                 'cpuset': None,
                 'memory': None,
                 'memsw': None,
                 'cpuacct': None,
                 'devices': None}
        # Loop through the mounts and collect the ones for cgroups
        with open(os.path.join(os.sep, 'proc', 'mounts'), 'r') as fd:
            for line in fd:
                entries = line.split()
                if entries[2] != 'cgroup':
                    continue
                flags = entries[3].split(',')
                if 'noprefix' in flags:
                    self.noprefix = True
                subsys = os.path.basename(entries[1])
                paths[subsys] = entries[1]
                if 'memory' in flags:
                    paths['memsw'] = paths[subsys]
                    paths['memory'] = paths[subsys]
                if 'cpuacct' in flags:
                    paths['cpuacct'] = paths[subsys]
                if 'devices' in flags:
                    paths['devices'] = paths[subsys]
        return paths

    def is_dir(self, cpath, host):
        """
        Returns True if path exists otherwise false
        """
        for _ in range(5):
            rv = self.du.isdir(hostname=host, path=cpath, sudo=True)
            if rv:
                return True
            time.sleep(0.1)
        return False

    def is_file(self, cpath, host):
        """
        Returns True if path exists otherwise false
        """
        for _ in range(5):
            rv = self.du.isfile(hostname=host, path=cpath, sudo=True)
            if rv:
                return True
            time.sleep(0.1)
        return False

    def get_cgroup_job_dir(self, subsys, jobid, host):
        """
        Returns path of subsystem
        """
        basedir = self.paths[subsys]
        if self.du.isdir(hostname=host, path=os.path.join(basedir, 'pbspro')):
            return os.path.join(basedir, 'pbspro', jobid)
        else:
            return os.path.join(basedir, 'pbspro.slice',
                                'pbspro-%s.slice' % systemd_escape(jobid))

    def load_hook(self, filename):
        """
        Import and enable a hook pointed to by the URL specified.
        """
        try:
            with open(filename, 'r') as fd:
                script = fd.read()
        except IOError:
            self.assertTrue(False, 'Failed to open hook file %s' % filename)
        events = '"execjob_begin,execjob_launch,execjob_attach,'
        events += 'execjob_epilogue,execjob_end,exechost_startup,'
        events += 'exechost_periodic"'
        a = {'enabled': 'True',
             'freq': '10',
             'event': events}
        # Sometimes the deletion of the old hook is still pending
        failed = True
        for _ in range(5):
            try:
                self.server.create_import_hook(self.hook_name, a, script,
                                               overwrite=True)
            except Exception:
                time.sleep(2)
            else:
                failed = False
                break
        if failed:
            self.skipTest('pbs_cgroups_hook: failed to load hook')
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
        self.momA.log_match('pbs_cgroups.CF;copy hook-related '
                            'file request received',
                            starttime=self.server.ctime)
        self.logger.info('Current config: %s' % cfg)
        # Restart MoM to work around PP-993
        self.momA.restart()
        if self.hostA != self.hostB:
            self.momB.restart()

    def set_vntype(self, host, typestring='myvntype'):
        """
        Set the vnode type for the local mom.
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = os.path.join(pbs_home, 'mom_priv', 'vntype')
        self.logger.info('Setting vntype to %s in %s on mom %s' %
                         (typestring, vntype_file, host))
        localhost = socket.gethostname()
        fn = self.du.create_temp_file(hostname=localhost, body=typestring)
        self.tempfile.append(fn)
        ret = self.du.run_copy(hosts=host, src=fn,
                               dest=vntype_file, sudo=True, uid='root',
                               gid='root', mode=0644)
        if ret['rc'] != 0:
            self.skipTest('pbs_cgroups_hook: failed to set vntype')

    def remove_vntype(self):
        """
        Unset the vnode type for the local mom.
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = os.path.join(pbs_home, 'mom_priv', 'vntype')
        self.logger.info('Deleting vntype files from moms')
        ret = self.du.rm(hostname=self.hostA, path=vntype_file,
                         force=True, sudo=True, logerr=False)
        if not ret:
            self.skipTest('pbs_cgroups_hook: failed to remove vntype')
        if self.hostA != self.hostB:
            ret = self.du.rm(hostname=self.hostB, path=vntype_file,
                             force=True, sudo=True, logerr=False)
            if not ret:
                self.skipTest('pbs_cgroups_hook: failed to remove vntype')

    def get_vntype(self, host):
        """
        Get the vntype if it exists for example on cray
        """
        vntype = 'no_cgroups'
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_f = os.path.join(pbs_home, 'mom_priv', 'vntype')
        self.logger.info('Reading the vntype value for mom %s' % host)
        if self.du.isfile(hostname=host, path=vntype_f):
            output = self.du.cat(hostname=host, filename=vntype_f, sudo=True)
            vntype = output['out'][0]
        return vntype

    def wait_and_read_file(self, host, filename=''):
        """
        Make several attempts to read a file and return its contents
        """
        self.logger.info('Reading file: %s on host: %s' % (filename, host))
        if not filename:
            raise ValueError('Invalid filename')
        for _ in range(30):
            if self.du.isfile(hostname=host, path=filename):
                break
            time.sleep(0.5)
        self.assertTrue(self.du.isfile(hostname=host, path=filename),
                        'File %s not found on host %s' % (filename, host))
        # Wait for output to flush
        time.sleep(2)
        output = self.du.cat(hostname=host, filename=filename, sudo=True)
        return output['out']

    def get_hostname(self, host):
        """
        get hostname of the mom.
        This is needed since cgroups logs hostname not mom name
        """
        cmd = 'hostname'
        rv = self.du.run_cmd(hosts=host, cmd=cmd)
        ret = rv['out'][0].split('.')[0]
        return ret

    def get_host_names(self, host):
        """
        get shortname and hostname of the mom. This is needed
        for some systems where hostname and shortname is different.
        """
        cmd1 = 'hostname -s'
        rv1 = self.du.run_cmd(hosts=host, cmd=cmd1)
        host2 = self.get_hostname(host)
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
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        name = 'CGROUP8'
        if self.vntypenameA == 'no_cgroups':
            self.logger.info('Adding vntype %s to mom %s ' %
                             (self.vntypenameA, self.momA))
            self.set_vntype(typestring=self.vntypenameA, host=self.hostA)
        self.load_config(self.cfg1 %
                         ('', '"' + self.vntypenameA + '"',
                          '', '', self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        self.logger.info('memory subsystem is at location %s' %
                         self.paths['memory'])
        cpath = self.get_cgroup_job_dir('memory', jid, self.hostA)
        self.assertFalse(self.is_dir(cpath, self.hostA))
        self.momA.log_match("%s is in the excluded vnode type list: ['%s']"
                            % (self.vntypenameA, self.vntypenameA),
                            starttime=self.server.ctime)
        self.logger.info('vntypes on both hosts are: %s and %s'
                         % (self.vntypenameA, self.vntypenameB))
        if self.vntypenameB == self.vntypenameA:
            self.logger.info('Skipping the second part of this test '
                             'since hostB also has same vntype value')
            return
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostB, ATTR_N: name}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid2 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j1.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hostB)
        self.assertTrue(self.is_dir(cpath, self.hostB))

    def test_cgroup_host_excluded(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have the exclude_hosts set
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        name = 'CGROUP9'
        mom, log = self.get_host_names(self.hostA)
        self.load_config(self.cfg1 % ('%s' % mom, '', '', '', self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid, self.hostA)
        self.assertFalse(self.is_dir(cpath, self.hostA))
        host = self.get_hostname(self.hostA)
        self.momA.log_match('%s is in the excluded host list: [%s]' %
                            (host, log), starttime=self.server.ctime)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostB, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hostB)
        self.assertTrue(self.is_dir(cpath, self.hostB))

    def test_cgroup_exclude_vntype_mem(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have an exclude vntype file set
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        name = 'CGROUP12'
        if self.vntypenameA == 'no_cgroups':
            self.logger.info('Adding vntype %s to mom %s' %
                             (self.vntypenameA, self.momA))
            self.set_vntype(typestring='no_cgroups', host=self.hostA)
        self.load_config(self.cfg3 % ('', '', '"' + self.vntypenameA + '"',
                                      self.swapctl,
                                      '"' + self.vntypenameA + '"'))
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s'
             % self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        self.momA.log_match('cgroup excluded for subsystem memory '
                            'on vnode type %s' % self.vntypenameA,
                            starttime=self.server.ctime)
        self.logger.info('vntype values for each hosts are: %s and %s'
                         % (self.vntypenameA, self.vntypenameB))
        if self.vntypenameB == self.vntypenameA:
            self.logger.info('Skipping the second part of this test '
                             'since hostB also has same vntype value')
            return
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostB, ATTR_N: name}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid2 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j1.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hostB)
        self.assertTrue(self.is_dir(cpath, self.hostB))

    @timeout(300)
    def test_cgroup_periodic_update_check_values(self):
        """
        Test to verify that cgroups are reporting usage for cput and mem
        """
        name = 'CGROUP13'
        conf = {'freq': 2}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb:host=%s' %
             self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job3)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        # Scouring the logs for initial values takes too long
        resc_list = ['resources_used.cput', 'resources_used.mem']
        if self.swapctl == 'true':
            resc_list.append('resources_used.vmem')
        qstat = self.server.status(JOB, resc_list, id=jid)
        cput = qstat[0]['resources_used.cput']
        self.assertEqual(cput, '00:00:00')
        mem = qstat[0]['resources_used.mem']
        match = re.match(r'(\d+)kb', mem)
        self.assertFalse(match is None)
        usage = int(match.groups()[0])
        self.assertGreater(30000, usage)
        if self.swapctl == 'true':
            vmem = qstat[0]['resources_used.vmem']
            match = re.match(r'(\d+)kb', vmem)
            self.assertFalse(match is None)
            usage = int(match.groups()[0])
            self.assertGreater(30000, usage)
        err_msg = "Unexpected error in pbs_cgroups " + \
            "handling exechost_periodic event: TypeError"
        self.mom.log_match(err_msg, max_attempts=3,
                           interval=1, n=100, existence=False)
        # Allow some time to pass for values to be updated
        begin = int(time.time())
        self.logger.info('Waiting for periodic hook to update usage data.')
        time.sleep(15)
        if self.paths['cpuacct']:
            lines = self.momA.log_match(
                '%s;update_job_usage: CPU usage:' %
                jid, allmatch=True, starttime=begin)
            usage = 0.0
            for line in lines:
                match = re.search(r'CPU usage: ([0-9.]+) secs', line[1])
                if not match:
                    continue
                usage = float(match.groups()[0])
                if usage > 1.0:
                    break
            self.assertGreater(usage, 1.0)
        if self.paths['memory']:
            lines = self.momA.log_match(
                '%s;update_job_usage: Memory usage: mem=' % jid,
                allmatch=True, max_attempts=5, starttime=begin)
            usage = 0
            for line in lines:
                match = re.search(r'mem=(\d+)kb', line[1])
                if not match:
                    continue
                usage = int(match.groups()[0])
                if usage > 400000:
                    break
            self.assertGreater(usage, 400000, 'Max memory usage: %dkb' % usage)
            if self.swapctl == 'true':
                lines = self.momA.log_match(
                    '%s;update_job_usage: Memory usage: vmem=' % jid,
                    allmatch=True, max_attempts=5, starttime=begin)
                usage = 0
                for line in lines:
                    match = re.search(r'vmem=(\d+)kb', line[1])
                    if not match:
                        continue
                    usage = int(match.groups()[0])
                    if usage > 400000:
                        break
                self.assertGreater(usage, 400000)

    def test_cgroup_cpuset_and_memory(self):
        """
        Test to verify that the job cgroup is created correctly
        Check to see that cpuset.cpus=0, cpuset.mems=0 and that
        memory.limit_in_bytes = 314572800
        """
        name = 'CGROUP1'
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             ATTR_N: name, ATTR_k: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.cpuset_mem_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        self.tempfile.append(filename)
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filename=tmp_file, host=tmp_host)
        self.logger.info("Job output is %s\n" % tmp_out)
        self.assertTrue(jid in tmp_out)
        self.logger.info('job dir check passed')
        if self.paths['cpuacct']:
            self.assertTrue('CpuIDs=0' in tmp_out)
            self.logger.info('CpuIDs check passed')
        if self.paths['memory']:
            self.assertTrue('MemorySocket=0' in tmp_out)
            self.logger.info('MemorySocket check passed')
            if self.swapctl == 'true':
                self.assertTrue('MemoryLimit=314572800' in tmp_out)
                self.logger.info('MemoryLimit check passed')

    def test_cgroup_cpuset_and_memsw(self):
        """
        Test to verify that the job cgroup is created correctly
        using the default memory and vmem
        Check to see that cpuset.cpus=0, cpuset.mems=0 and that
        memory.limit_in_bytes = 268435456
        memory.memsw.limit_in_bytes = 268435456
        """
        name = 'CGROUP2'
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        a = {'Resource_List.select': '1:ncpus=1:host=%s' %
             self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.cpuset_mem_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        self.tempfile.append(filename)
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filename=tmp_file, host=tmp_host)
        self.logger.info("Job output is %s\n" % tmp_out)
        self.assertTrue(jid in tmp_out)
        self.logger.info('job dir check passed')
        if self.paths['cpuacct']:
            self.assertTrue('CpuIDs=0' in tmp_out)
            self.logger.info('CpuIDs check passed')
        if self.paths['memory']:
            self.assertTrue('MemorySocket=0' in tmp_out)
            self.logger.info('MemorySocket check passed')
            if self.swapctl == 'true':
                self.assertTrue('MemoryLimit=100663296' in tmp_out)
                self.assertTrue('MemswLimit=100663296' in tmp_out)
                self.logger.info('MemoryLimit check passed')

    def test_cgroup_prefix_and_devices(self):
        """
        Test to verify that the cgroup prefix is set to pbs and that
        only the devices subsystem is enabled with the correct devices
        allowed
        """
        if not self.paths['devices']:
            self.skipTest('Skipping test since no devices subsystem defined')
        name = 'CGROUP3'
        self.load_config(self.cfg2)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.check_dirs_script)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        self.tempfile.append(filename)
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filename=tmp_file, host=tmp_host)
        check_devices = ['b *:* rwm',
                         'c 5:1 rwm',
                         'c 4:* rwm',
                         'c 1:* rwm',
                         'c 10:* rwm']
        for device in check_devices:
            self.assertTrue(device in tmp_out,
                            '"%s" not found in: %s' % (device, tmp_out))
        self.logger.info('device_list check passed')
        self.assertFalse('Disabled cgroup subsystems are populated '
                         'with the job id' in tmp_out,
                         'Found disabled cgroup subsystems populated')
        self.logger.info('Disabled subsystems check passed')

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
            self.skipTest('Test requires at least two physical CPUs')
        name = 'CGROUP4'
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        # Submit two jobs
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name + 'a'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.cpuset_mem_script)
        jid1 = self.server.submit(j1)
        b = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name + 'b'}
        j2 = Job(TEST_USER, attrs=b)
        j2.create_script(self.cpuset_mem_script)
        jid2 = self.server.submit(j2)
        a = {'job_state': 'R'}
        # Make sure they are both running
        self.server.expect(JOB, a, jid1)
        self.server.expect(JOB, a, jid2)
        # Status the jobs for their output files
        attrib = [ATTR_o]
        self.server.status(JOB, attrib, jid1)
        filename1 = j1.attributes[ATTR_o]
        self.logger.info('Job1 .o file: %s' % filename1)
        self.tempfile.append(filename1)
        self.server.status(JOB, attrib, jid2)
        filename2 = j2.attributes[ATTR_o]
        self.logger.info('Job2 .o file: %s' % filename2)
        self.tempfile.append(filename2)
        # Read the output files
        tmp_file1 = filename1.split(':')[1]
        tmp_out1 = self.wait_and_read_file(filename=tmp_file1, host=self.hostA)
        self.logger.info("test output for job1: %s" % (tmp_out1))
        self.assertTrue(
            jid1 in tmp_out1, '%s not found in output on host %s'
            % (jid1, self.hostA))
        tmp_file2 = filename2.split(':')[1]
        tmp_out2 = self.wait_and_read_file(filename=tmp_file2, host=self.hostA)
        self.logger.info("test output for job2: %s" % (tmp_out2))
        self.assertTrue(
            jid2 in tmp_out2, '%s not found in output on host %s'
            % (jid2, self.hostA))
        self.logger.info('job dir check passed')
        # Ensure the CPU ID for each job differs
        cpuid1 = None
        for kv in tmp_out1:
            if 'CpuIDs=' in kv:
                cpuid1 = kv
                break
        self.assertNotEqual(cpuid1, None, 'Could not read first CPU ID.')
        cpuid2 = None
        for kv in tmp_out2:
            if 'CpuIDs=' in kv:
                cpuid2 = kv
                break
        self.assertNotEqual(cpuid2, None, 'Could not read second CPU ID.')
        self.logger.info("cpuid1 = %s and cpuid2 = %s" % (cpuid1, cpuid2))
        self.assertNotEqual(cpuid1, cpuid2,
                            'Processes should be assigned to different CPUs')
        self.logger.info('CpuIDs check passed')

    def test_cgroup_enforce_memory(self):
        """
        Test to verify that the job is killed when it tries to
        use more memory then it requested
        """
        name = 'CGROUP5'
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        # mem and vmem limit will both be set, and either could be detected
        self.momA.log_match('%s;Cgroup mem(ory|sw) limit exceeded' % jid,
                            regexp=True,
                            max_attempts=20)

    def test_cgroup_enforce_memsw(self):
        """
        Test to verify that the job is killed when it tries to
        use more vmem then it requested
        """
        # run the test if swap space is available
        if have_swap() == 0:
            self.skipTest('no swap space available on the local host')
        fn = self.get_cgroup_job_dir('memory', '123.foo', self.hostA)
        # Get the grandparent directory
        fn = os.path.dirname(fn)
        fn = os.path.dirname(fn)
        fn = os.path.join(fn, 'memory.memsw.limit_in_bytes')
        if not self.is_file(fn, self.hostA):
            self.skipTest('vmem resource not present on node')
        name = 'CGROUP6'
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        a = {
            'Resource_List.select':
            '1:ncpus=1:mem=300mb:vmem=320mb:host=%s' % self.hostA,
            ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        self.tempfile.append(filename)
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filename=tmp_file, host=tmp_host)
        self.assertTrue('MemoryError' in tmp_out,
                        'MemoryError not present in output')

    @timeout(300)
    def test_cgroup_offline_node(self):
        """
        Test to verify that the node is offlined when it can't clean up
        the cgroup and brought back online once the cgroup is cleaned up
        """
        name = 'CGROUP7'
        if 'freezer' not in self.paths:
            self.skipTest('Freezer cgroup is not mounted')
        fdir = self.get_cgroup_job_dir('freezer', '123.foo', self.hostA)
        # Get the grandparent directory
        fdir = os.path.dirname(fdir)
        fdir = os.path.dirname(fdir)
        if not self.is_dir(fdir, self.hostA):
            self.skipTest('Freezer cgroup is not found')
        # Configure the hook
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, 'Resource_List.walltime': 3, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        self.tempfile.append(filename)
        tmp_file = filename.split(':')[1]
        # Query the pids in the cgroup
        jdir = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        tasks_file = os.path.join(jdir, 'tasks')
        time.sleep(2)
        ret = self.du.cat(self.hostA, tasks_file, sudo=True)
        tasks = ret['out']
        if len(tasks) < 2:
            self.skipTest('pbs_cgroups_hook: only one task in cgroup')
        self.logger.info('Tasks: %s' % tasks)
        self.assertTrue(tasks, 'No tasks in cpuset cgroup for job')
        # Make dir in freezer subsystem
        fdir = os.path.join(fdir, 'PtlPbs')
        if not self.du.isdir(fdir):
            self.du.mkdir(hostname=self.hostA, path=fdir,
                          mode=0755, sudo=True)
            self.tempfile.append(fdir)
        # Write a PID into the tasks file for the freezer cgroup
        task_file = os.path.join(fdir, 'tasks')
        success = False
        for pid in reversed(tasks[1:]):
            fn = self.du.create_temp_file(hostname=self.hostA, body=pid)
            self.tempfile.append(fn)
            ret = self.du.run_copy(hosts=self.hostA, src=fn,
                                   dest=task_file, sudo=True,
                                   uid='root', gid='root',
                                   mode=0644)
            if ret['rc'] == 0:
                success = True
                break
            self.logger.info('Failed to copy %s to %s on %s' %
                             (fn, task_file, self.hostA))
            self.logger.info('rc = %d', ret['rc'])
            self.logger.info('stdout = %s', ret['out'])
            self.logger.info('stderr = %s', ret['err'])
        if not success:
            self.skipTest('pbs_cgroups_hook: Failed to copy freezer tasks')
        # Freeze the cgroup
        freezer_file = os.path.join(fdir, 'freezer.state')
        state = 'FROZEN'
        fn = self.du.create_temp_file(hostname=self.hostA, body=state)
        self.tempfile.append(fn)
        ret = self.du.run_copy(self.hostA, src=fn,
                               dest=freezer_file, sudo=True,
                               uid='root', gid='root',
                               mode=0644)
        if ret['rc'] != 0:
            self.skipTest('pbs_cgroups_hook: Failed to copy '
                          'freezer state FROZEN')
        self.server.expect(NODE, {'state': (MATCH_RE, 'offline')},
                           id=self.nodeA, interval=3)
        # Thaw the cgroup
        state = 'THAWED'
        fn = self.du.create_temp_file(hostname=self.hostA, body=state)
        self.tempfile.append(fn)
        ret = self.du.run_copy(self.hostA, src=fn,
                               dest=freezer_file, sudo=True,
                               uid='root', gid='root',
                               mode=0644)
        if ret['rc'] != 0:
            self.skipTest('pbs_cgroups_hook: Failed to copy '
                          'freezer state THAWED')
        time.sleep(1)
        self.du.rm(hostname=self.hostA, path=os.path.dirname(fdir),
                   force=True, recursive=True, sudo=True)
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3)

    def test_cgroup_cpuset_host_excluded(self):
        """
        Test to verify that cgroups subsystems are not enforced on nodes
        that have the exclude_hosts set but are enforced on other systems
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')

        name = 'CGROUP10'
        mom, _ = self.get_host_names(self.hostA)
        self.load_config(self.cfg1 % ('', '', '', '%s' % mom, self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        hostn = self.get_hostname(self.hostA)
        self.momA.log_match('cgroup excluded for subsystem cpuset '
                            'on host %s' % hostn, starttime=self.server.ctime)
        cpath = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        self.assertFalse(self.is_dir(cpath, self.hostA))
        # Now try a job on momB
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostB, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        cpath = self.get_cgroup_job_dir('cpuset', jid2, self.hostB)
        self.logger.info('Checking for %s on %s' % (cpath, self.momB))
        self.assertTrue(self.is_dir(cpath, self.hostB))

    def test_cgroup_run_on_host(self):
        """
        Test to verify that the cgroup hook only runs on nodes
        in the run_only_on_hosts
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')

        name = 'CGROUP11'
        mom, log = self.get_host_names(self.hostA)
        self.load_config(self.cfg1 % ('', '', '%s' % mom, '', self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostB, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        time.sleep(1)
        hostn = self.get_hostname(self.hostB)
        self.momB.log_match('%s is not in the approved host list: [%s]' %
                            (hostn, log), starttime=self.server.ctime)
        cpath = self.get_cgroup_job_dir('memory', jid, self.hostB)
        self.assertFalse(self.is_dir(cpath, self.hostB))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hostA)
        self.assertTrue(self.is_dir(cpath, self.hostA))

    def test_cgroup_qstat_resources(self):
        """
        Test to verify that cgroups are reporting usage for
        mem, and vmem in qstat
        """
        name = 'CGROUP14'
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job2)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        host = j.attributes['exec_host']
        self.logger.info('OUTPUT: %s' % o)
        resc_list = ['resources_used.cput']
        resc_list += ['resources_used.mem']
        resc_list += ['resources_used.vmem']
        qstat1 = self.server.status(JOB, resc_list, id=jid)
        for q in qstat1:
            self.logger.info('Q1: %s' % q)
        cput1 = qstat1[0]['resources_used.cput']
        mem1 = qstat1[0]['resources_used.mem']
        vmem1 = qstat1[0]['resources_used.vmem']
        self.logger.info('Waiting 25 seconds for CPU time to accumulate')
        time.sleep(25)
        qstat2 = self.server.status(JOB, resc_list, id=jid)
        for q in qstat2:
            self.logger.info('Q2: %s' % q)
        cput2 = qstat2[0]['resources_used.cput']
        mem2 = qstat2[0]['resources_used.mem']
        vmem2 = qstat2[0]['resources_used.vmem']
        self.assertNotEqual(cput1, cput2)
        self.assertNotEqual(mem1, mem2)
        self.assertNotEqual(vmem1, vmem2)

    @timeout(500)
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
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        if self.swapctl == 'true':
            vmem = self.server.status(NODE, 'resources_available.vmem',
                                      id=self.nodeA)
            self.logger.info('vmem: %s' % str(vmem))
            vmem1 = PbsTypeSize(vmem[0]['resources_available.vmem'])
            self.logger.info('Vmem-1: %s' % vmem1.value)
        mem = self.server.status(NODE, 'resources_available.mem',
                                 id=self.nodeA)
        mem1 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info('Mem-1: %s' % mem1.value)
        self.load_config(self.cfg4 % (self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        if self.swapctl == 'true':
            vmem = self.server.status(NODE, 'resources_available.vmem',
                                      id=self.nodeA)
            vmem2 = PbsTypeSize(vmem[0]['resources_available.vmem'])
            self.logger.info('Vmem-2: %s' % vmem2.value)
            vmem_resv = vmem1 - vmem2
            self.logger.info('Vmem resv: %s' % vmem_resv.value)
            self.assertEqual(vmem_resv.value, 97280)
            self.assertEqual(vmem_resv.unit, 'kb')
        mem = self.server.status(NODE, 'resources_available.mem',
                                 id=self.nodeA)
        mem2 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info('Mem-2: %s' % mem2.value)
        mem_resv = mem1 - mem2
        self.logger.info('Mem resv: %s' % mem_resv.value)
        self.assertEqual(mem_resv.value, 51200)
        self.assertEqual(mem_resv.unit, 'kb')

    def test_cgroup_multi_node(self):
        """
        Test multi-node jobs with cgroups
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        name = 'CGROUP16'
        self.load_config(self.cfg6 % (self.swapctl))
        a = {'Resource_List.select': '2:ncpus=1:mem=100mb',
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
        ehjd1 = self.get_cgroup_job_dir('memory', jid, ehost1)
        self.assertTrue(self.is_dir(ehjd1, ehost1),
                        'Missing memory subdirectory: %s' % ehjd1)
        ehost2 = tmp_host[1].split('/')[0]
        ehjd2 = self.get_cgroup_job_dir('memory', jid, ehost2)
        self.assertTrue(self.is_dir(ehjd2, ehost2))
        # Wait for job to finish and make sure that cgroup directories
        # has been cleaned up by the hook
        self.server.expect(JOB, 'queue', op=UNSET, offset=15, interval=1,
                           id=jid)
        self.assertFalse(self.is_dir(ehjd1, ehost1),
                         'Directory still present: %s' % ehjd1)
        self.assertFalse(self.is_dir(ehjd2, ehost2),
                         'Directory still present: %s' % ehjd2)

    def test_cgroup_job_array(self):
        """
        Test that cgroups are created for subjobs like a regular job
        """
        name = 'CGROUP17'
        self.load_config(self.cfg1 % ('', '', '', '', self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hostA, ATTR_N: name, ATTR_J: '1-4',
             'Resource_List.place': 'pack:excl'}
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
        cpath = self.get_cgroup_job_dir('memory', subj1, ehost1)
        self.assertTrue(self.is_dir(cpath, ehost1))
        cpath = self.get_cgroup_job_dir('memory', jid, ehost1)
        self.assertFalse(self.is_dir(cpath, ehost1))
        # Verify that subjob4 is queued and no cgroups
        # files are created for queued subjob
        subj4 = jid.replace('[]', '[4]')
        self.server.expect(JOB, {'job_state': 'Q'}, id=subj4)
        cpath = self.get_cgroup_job_dir('memory', subj4, ehost1)
        self.assertFalse(self.is_dir(cpath, self.hostA))
        # Delete subjob1 and verify that cgroups files are cleaned up
        self.server.delete(id=subj1)
        self.server.expect(JOB, {'job_state': 'X'}, subj1)
        cpath = self.get_cgroup_job_dir('memory', subj1, ehost1)
        self.assertFalse(self.is_dir(cpath, ehost1))
        # Verify if subjob2 is running
        subj2 = jid.replace('[]', '[2]')
        self.server.expect(JOB, {'job_state': 'R'}, id=subj2)
        # Force delete the subjob and verify cgroups
        # files are cleaned up
        self.server.delete(id=subj2, extend='force')
        self.server.expect(JOB, {'job_state': 'X'}, subj2)
        # Adding extra sleep for file to clean up
        time.sleep(2)
        cpath = self.get_cgroup_job_dir('memory', subj2, ehost1)
        self.assertFalse(self.is_dir(cpath, ehost1))

    def test_cgroup_cleanup(self):
        """
        Test that cgroups files are cleaned up after qdel
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        self.load_config(self.cfg1 % ('', '', '', '', self.swapctl))
        a = {'Resource_List.select': '2:ncpus=1:mem=100mb',
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ['exec_host'], jid)
        ehost = j.attributes['exec_host']
        tmp_host = ehost.split('+')
        ehost1 = tmp_host[0].split('/')[0]
        ehost2 = tmp_host[1].split('/')[0]
        ehjd1 = self.get_cgroup_job_dir('cpuset', jid, ehost1)
        self.assertTrue(self.is_dir(ehjd1, ehost1))
        ehjd2 = self.get_cgroup_job_dir('cpuset', jid, ehost2)
        self.assertTrue(self.is_dir(ehjd2, ehost2))
        self.server.delete(id=jid, wait=True)
        self.assertFalse(self.is_dir(ehjd1, ehost1))
        self.assertFalse(self.is_dir(ehjd2, ehost2))

    def test_cgroup_execjob_end_should_delete_cgroup(self):
        """
        Test to verify that if execjob_epilogue hook failed to run or to
        clean up cgroup files for a job, execjob_end hook should clean
        them up
        """
        self.load_config(self.cfg4 % (self.swapctl))
        # remove epilogue and periodic from the list of events
        attr = {'enabled': 'True',
                'event': '"execjob_begin,execjob_launch,'
                         'execjob_attach,execjob_end,exechost_startup"'}
        self.server.manager(MGR_CMD_SET, HOOK, attr, self.hook_name)
        self.server.expect(NODE, {'state': 'free'}, id=self.nodeA)
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
                self.logger.info('Checking that file %s should not exist'
                                 % filename)
                self.assertFalse(os.path.isfile(filename))

    @skipOnCray
    def test_cgroup_assign_resources_mem_only_vnode(self):
        """
        Test to verify that job requesting mem larger than any single vnode
        works properly
        """
        vn_attrs = {ATTR_rescavail + '.ncpus': 1,
                    ATTR_rescavail + '.mem': '500mb'}
        self.load_config(self.cfg4 % (self.swapctl))
        self.server.expect(NODE, {ATTR_NODE_state: 'free'}, id=self.nodeA)
        self.server.create_vnodes('vnode', vn_attrs, 2, self.moms.values()[0])
        self.server.expect(NODE, {ATTR_NODE_state: 'free'}, id=self.nodeA)
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script('date')
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, 'queue', id=jid1, op=UNSET, max_attempts=20,
                           interval=1, offset=1)
        a = {'Resource_List.select': '1:ncpus=1:mem=1000mb'}
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

    @timeout(500)
    def test_cgroup_cpuset_exclude_cpu(self):
        """
        Confirm that exclude_cpus reduces resources_available.ncpus
        """
        # Fetch the unmodified value of resources_available.ncpus
        self.load_config(self.cfg5 % ('false', '', 'false', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=self.nodeA)
        orig_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(orig_ncpus, 0)
        self.logger.info('Original value of ncpus: %d' % orig_ncpus)
        if orig_ncpus < 2:
            self.skipTest('Node must have at least two CPUs')
        # Now exclude CPU zero
        self.load_config(self.cfg5 % ('false', '0', 'false', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=self.nodeA)
        new_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(new_ncpus, 0)
        self.logger.info('New value with one CPU excluded: %d' % new_ncpus)
        self.assertEqual((new_ncpus + 1), orig_ncpus)
        # Repeat the process with vnode_per_numa_node set to true
        vnode = '%s[0]' % self.nodeA
        self.load_config(self.cfg5 % ('true', '', 'false', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=vnode, interval=3, offset=10)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=vnode)
        orig_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(orig_ncpus, 0)
        self.logger.info('Original value of vnode ncpus: %d' % orig_ncpus)
        # Exclude CPU zero again
        self.load_config(self.cfg5 % ('true', '0', 'false', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=vnode, interval=3, offset=10)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=vnode)
        new_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertEqual((new_ncpus + 1), orig_ncpus)

    def test_cgroup_cpuset_mem_fences(self):
        """
        Confirm that mem_fences affects setting of cpuset.mems
        """
        cpuset_base = self.get_cgroup_job_dir('cpuset', '123.foo', self.hostA)
        # Get the grandparent directory
        cpuset_base = os.path.dirname(cpuset_base)
        cpuset_base = os.path.dirname(cpuset_base)
        cpuset_mems = os.path.join(cpuset_base, 'cpuset.mems')
        result = self.du.cat(hostname=self.hostA, filename=cpuset_mems,
                             sudo=True)
        if result['rc'] != 0 or result['out'][0] == '0':
            self.skipTest('Test requires two NUMA nodes')
        # First try with mem_fences set to true (the default)
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        fn = os.path.join(fn, 'cpuset.mems')
        result = self.du.cat(hostname=self.hostA, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '0')
        # Now try with mem_fences set to false
        self.load_config(self.cfg5 % ('false', '', 'false', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        fn = os.path.join(fn, 'cpuset.mems')
        result = self.du.cat(hostname=self.hostA, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertNotEqual(result['out'][0], '0')

    def test_cgroup_cpuset_mem_hardwall(self):
        """
        Confirm that mem_hardwall affects setting of cpuset.mem_hardwall
        """
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        memh_path = 'cpuset.mem_hardwall'
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        if self.noprefix:
            memh_path = 'mem_hardwall'
        fn = os.path.join(fn, memh_path)
        result = self.du.cat(hostname=self.hostA, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '0')
        self.load_config(self.cfg5 % ('false', '', 'true', 'true',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        fn = os.path.join(fn, memh_path)
        result = self.du.cat(hostname=self.hostA, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '1')

    def test_cgroup_find_gpus(self):
        """
        Confirm that the hook finds the correct number
        of GPUs.
        """
        if not self.paths['devices']:
            self.skipTest('Skipping test since no devices subsystem defined')
        name = 'CGROUP3'
        self.load_config(self.cfg2)
        cmd = ['nvidia-smi', '-L']
        try:
            rv = self.du.run_cmd(cmd=cmd)
        except OSError:
            rv = {'err': True}
        if rv['err'] or 'GPU' not in rv['out'][0]:
            self.skipTest('Skipping test since nvidia-smi not found')
        gpus = int(len(rv['out']))
        if gpus < 1:
            self.skipTest('Skipping test since no gpus found')
        self.server.expect(NODE, {'state': 'free'}, id=self.nodeA)
        ngpus = self.server.status(NODE, 'resources_available.ngpus',
                                   id=self.nodeA)[0]
        ngpus = int(ngpus['resources_available.ngpus'])
        self.assertEqual(gpus, ngpus, 'ngpus is incorrect')
        a = {'Resource_List.select': '1:ngpus=1', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.check_gpu_script)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        filename = j.attributes[ATTR_o]
        self.tempfile.append(filename)
        ehost = j.attributes['exec_host']
        tmp_file = filename.split(':')[1]
        tmp_host = ehost.split('/')[0]
        tmp_out = self.wait_and_read_file(filename=tmp_file, host=tmp_host)
        self.logger.info(tmp_out)
        self.assertIn('There are 1 GPUs', tmp_out, 'No gpus were assigned')
        self.assertIn('c 195:255 rwm', tmp_out, 'Nvidia controller not found')
        m = re.search(r'195:(?!255)', '\n'.join(tmp_out))
        self.assertIsNotNone(m.group(0), 'No gpu assigned in cgroups')

    def test_cgroup_cpuset_memory_spread_page(self):
        """
        Confirm that mem_spread_page affects setting of
        cpuset.memory_spread_page
        """
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'false', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        spread_path = 'cpuset.memory_spread_page'
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        if self.noprefix:
            spread_path = 'memory_spread_page'
        fn = os.path.join(fn, spread_path)
        result = self.du.cat(hostname=self.hostA, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '0')
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'true', self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodeA, interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hostA)
        fn = os.path.join(fn, spread_path)
        result = self.du.cat(hostname=self.hostA, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '1')

    def test_cgroup_use_hierarchy(self):
        """
        Test that memory.use_hierarchy is enabled by default
        when PBS cgroups hook is instantiated
        """
        now = int(time.time())
        # Remove PBS directories from memory subsystem
        if 'memory' in self.paths and self.paths['memory']:
            cdir = self.paths['memory']
            if os.path.isdir(cdir):
                cpath = os.path.join(cdir, 'pbspro')
                if not os.path.isdir(cpath):
                    cpath = os.path.join(cdir, 'pbspro.slice')
        else:
            self.skipTest(
                "memory subsystem is not enabled for cgroups")
        cmd = ["rmdir", cpath]
        self.logger.info("Removing %s" % cpath)
        self.du.run_cmd(cmd=cmd, sudo=True)
        self.load_config(self.cfg6 % (self.swapctl))
        self.momA.restart()
        # Wait for exechost_startup hook to run
        self.momA.log_match("Hook handler returned success for"
                            " exechost_startup event",
                            starttime=now)
        # Verify that memory.use_hierarchy is enabled
        fpath = os.path.join(cpath, "memory.use_hierarchy")
        self.logger.info("looking for file %s" % fpath)
        if os.path.isfile(fpath):
            with open(fpath, 'r') as fd:
                val = fd.read()
                self.assertEqual(
                    val.rstrip(), "1", "%s is not equal to 1"
                    % val.rstrip())
            self.logger.info("memory.use_hierarchy is enabled")
        else:
            self.assertFalse(1, "File %s not present" % fpath)

    def test_cgroup_periodic_update_known_jobs(self):
        """
        Verify that jobs known to mom are updated, not orphans
        """
        conf = {'freq': 5, 'order': 100}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        self.load_config(self.cfg3 % ('', '', '', self.swapctl, ''))
        # Submit a short job and let it run to completion
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep5_job)
        jid1 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid1)
        self.server.status(JOB, ATTR_o, jid1)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        err_msg = "Unexpected error in pbs_cgroups " + \
            "handling exechost_periodic event: TypeError"
        self.mom.log_match(err_msg, max_attempts=3,
                           interval=1, n=100, existence=False)
        self.server.log_match(jid1 + ';Exit_status=0')
        # Create a periodic hook that runs more frequently than the
        # cgroup hook to prepend jid1 to mom_priv/hooks/hook_data/cgroup_jobs
        hookname = 'prependjob'
        hookbody = """
import pbs
import os
import re
import traceback
event = pbs.event()
jid_to_prepend = '%s'
pbs_home = ''
pbs_mom_home = ''
if 'PBS_HOME' in os.environ:
    pbs_home = os.environ['PBS_HOME']
if 'PBS_MOM_HOME' in os.environ:
    pbs_mom_home = os.environ['PBS_MOM_HOME']
pbs_conf = pbs.get_pbs_conf()
if pbs_conf:
    if not pbs_home and 'PBS_HOME' in pbs_conf:
        pbs_home = pbs_conf['PBS_HOME']
    if not pbs_mom_home and 'PBS_MOM_HOME' in pbs_conf:
        pbs_mom_home = pbs_conf['PBS_MOM_HOME']
if not pbs_home or not pbs_mom_home:
    if 'PBS_CONF_FILE' in os.environ:
        pbs_conf_file = os.environ['PBS_CONF_FILE']
    else:
        pbs_conf_file = os.path.join(os.sep, 'etc', 'pbs.conf')
    regex = re.compile(r'\\s*([^\\s]+)\\s*=\\s*([^\\s]+)\\s*')
    try:
        with open(pbs_conf_file, 'r') as desc:
            for line in desc:
                match = regex.match(line)
                if match:
                    if not pbs_home and match.group(1) == 'PBS_HOME':
                        pbs_home = match.group(2)
                    if not pbs_mom_home and (match.group(1) ==
                                             'PBS_MOM_HOME'):
                        pbs_mom_home = match.group(2)
    except Exception:
        pass
if not pbs_home:
    pbs.logmsg(pbs.EVENT_DEBUG, 'Failed to locate PBS_HOME')
    event.reject()
if not pbs_mom_home:
    pbs_mom_home = pbs_home
jobsfile = os.path.join(pbs_mom_home, 'mom_priv', 'hooks',
                        'hook_data', 'cgroup_jobs')
try:
    with open(jobsfile, 'r+') as desc:
        joblist = desc.readline().split()
        jobset = set(joblist)
        if jid_to_prepend not in jobset:
            jobset.add(jid_to_prepend)
            desc.seek(0)
            desc.write(' '.join(jobset))
            desc.truncate()
except Exception as exc:
    pbs.logmsg(pbs.EVENT_DEBUG, 'Failed to modify ' + jobsfile)
    pbs.logmsg(pbs.EVENT_DEBUG,
               str(traceback.format_exc().strip().splitlines()))
    event.reject()
event.accept()
""" % jid1
        events = '"execjob_begin,exechost_periodic"'
        hookconf = {'enabled': 'True', 'freq': 2, 'alarm': 30, 'event': events}
        self.server.create_import_hook(hookname, hookconf, hookbody,
                                       overwrite=True)
        # Submit a second job and verify that the following message
        # does NOT appear in the mom log:
        # _exechost_periodic_handler: Failed to update jid1
        presubmit = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hostA}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        err_msg = "Unexpected error in pbs_cgroups " + \
            "handling exechost_periodic event: TypeError"
        self.mom.log_match(err_msg, max_attempts=3,
                           interval=1, n=100, existence=False)
        self.server.log_match(jid2 + ';Exit_status=0')
        self.server.manager(MGR_CMD_DELETE, HOOK, None, hookname)
        command = ['truncate', '-s0',
                   os.path.join(self.momA.pbs_conf['PBS_HOME'], 'mom_priv',
                                'hooks', 'hook_data', 'cgroup_jobs')]
        self.du.run_cmd(cmd=command, hosts=self.hostA, sudo=True)
        logmsg = '_exechost_periodic_handler: Failed to update %s' % jid1
        self.momA.log_match(msg=logmsg, starttime=presubmit,
                            max_attempts=1, existence=False)

    def check_req_rjs(self):
        """
        Check the requirements for the reliable job startup tests.
        MomA must have two free vnodes and MomB has one free vnode.
        Return 1 if requirements are not satisfied.
        """
        # Check that momA has two free vnodes
        attr = {'state': 'free'}
        rv1 = True
        try:
            self.server.expect(VNODE, attr, id='%s[0]' % self.hostA,
                               max_attempts=3, interval=2)
        except PtlExpectError as exc:
            rv1 = exc.rv
        rv2 = True
        try:
            self.server.expect(VNODE, attr, id='%s[1]' % self.hostA,
                               max_attempts=3, interval=2)
        except PtlExpectError as exc:
            rv2 = exc.rv
        # Check that momB has one free vnode
        rv3 = True
        try:
            self.server.expect(VNODE, attr, id='%s[0]' % self.hostB,
                               max_attempts=3, interval=2)
        except PtlExpectError as exc:
            rv3 = exc.rv
        if not rv1 or not rv2 or not rv3:
            return 1
        return 0

    def test_cgroup_release_nodes(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        tolerate_node_failures=job_start
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        self.load_config(self.cfg7)
        # Check that MomA has two free vnodes and MomB has a free vnode
        if self.check_req_rjs() == 1:
            self.skipTest(
                'MomA must have two free vnodes and MomB one free vnode')
        # instantiate queuejob hook
        hook_event = 'queuejob'
        hook_name = 'qjob'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)
        # instantiate execjob_launch hook
        hook_event = 'execjob_launch'
        hook_name = 'launch'
        a = {'event': hook_event, 'enabled': 'true'}
        self.keep_select = 'e.job.Resource_List["site"]'
        self.server.create_import_hook(
            hook_name, a, self.launch_hook_body % (self.keep_select))
        # Submit a job that requires 2 nodes
        j = Job(TEST_USER)
        j.create_script(self.job_scr2)
        jid = self.server.submit(j)
        # Check the exec_vnode while in substate 41
        self.server.expect(JOB, {ATTR_substate: '41'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode1 = job_stat[0]['exec_vnode']
        self.logger.info("initial exec_vnode: %s" % execvnode1)
        initial_vnodes = execvnode1.split('+')
        # Check the exec_vnode after job is in substate 42
        self.server.expect(JOB, {ATTR_substate: '42'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode2 = job_stat[0]['exec_vnode']
        self.logger.info("pruned exec_vnode: %s" % execvnode2)
        pruned_vnodes = execvnode2.split('+')
        # Check that the pruned exec_vnode has one less than initial value
        self.assertEqual(len(pruned_vnodes) + 1, len(initial_vnodes))
        # Find the released vnode
        for vn in initial_vnodes:
            if vn not in pruned_vnodes:
                rel_vn = vn
        vnodeB = rel_vn.split(':')[0].split('(')[1]
        self.logger.info("released vnode: %s" % vnodeB)
        # Submit a second job requesting the released vnode, job runs
        j2 = Job(TEST_USER,
                 {ATTR_l + '.select': '1:ncpus=1:mem=2gb:vnode=%s' % vnodeB})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

    def test_cgroup_sismom_resize_fail(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        exec_job_resize failure in sister mom,
        tolerate_node_failures=job_start
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        self.load_config(self.cfg7)
        # Check that MomA has two free vnodes and MomB has a free vnode
        if self.check_req_rjs() == 1:
            self.skipTest(
                'MomA must have two free vnodes and MomB one free vnode')
        # instantiate queuejob hook
        hook_event = 'queuejob'
        hook_name = 'qjob'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)
        # instantiate execjob_launch hook
        hook_event = 'execjob_launch'
        hook_name = 'launch'
        a = {'event': hook_event, 'enabled': 'true'}
        self.keep_select = 'e.job.Resource_List["site"]'
        self.server.create_import_hook(
            hook_name, a, self.launch_hook_body % (self.keep_select))
        # instantiate execjob_resize hook
        hook_event = 'execjob_resize'
        hook_name = 'resize'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.resize_hook_body % ('not'))
        # Submit a job that requires 2 nodes
        j = Job(TEST_USER)
        j.create_script(self.job_scr2)
        stime = int(time.time())
        jid = self.server.submit(j)
        # Check the exec_vnode while in substate 41
        self.server.expect(JOB, {ATTR_substate: '41'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode1 = job_stat[0]['exec_vnode']
        self.logger.info("initial exec_vnode: %s" % execvnode1)
        initial_vnodes = execvnode1.split('+')
        # Check the exec_resize hook reject message in sister mom logs
        self.momA.log_match(
            "Job;%s;Cannot resize the job" % (jid),
            starttime=stime, interval=2)
        # Check the exec_vnode after job is in substate 42
        self.server.expect(JOB, {ATTR_substate: '42'}, id=jid)
        # Check for the pruned exec_vnode due to release_nodes() in launch hook
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode2 = job_stat[0]['exec_vnode']
        self.logger.info("pruned exec_vnode: %s" % execvnode2)
        pruned_vnodes = execvnode2.split('+')
        # Check that the pruned exec_vnode has one less than initial value
        self.assertEqual(len(pruned_vnodes) + 1, len(initial_vnodes))
        # Check that the exec_vnode got pruned
        self.momB.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.momB.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, execvnode2), starttime=stime)
        # Check that the sister mom failed to update the job
        self.momB.log_match(
            "Job;%s;sister node %s.* failed to update job" % (jid, self.hostA),
            starttime=stime, interval=2, regexp=True)
        # Because of resize hook reject Mom failed to update the job.
        # Check that job got requeued.
        self.server.log_match("Job;%s;Job requeued" % (jid), starttime=stime)

    def test_cgroup_msmom_resize_fail(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        exec_job_resize failure in mom superior,
        tolerate_node_failures=job_start
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        self.load_config(self.cfg7)
        # Check that MomA has two free vnodes and MomB has a free vnode
        if self.check_req_rjs() == 1:
            self.skipTest(
                'MomA must have two free vnodes and MomB one free vnode')
        # instantiate queuejob hook
        hook_event = 'queuejob'
        hook_name = 'qjob'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)
        # instantiate execjob_launch hook
        hook_event = 'execjob_launch'
        hook_name = 'launch'
        a = {'event': hook_event, 'enabled': 'true'}
        self.keep_select = 'e.job.Resource_List["site"]'
        self.server.create_import_hook(
            hook_name, a, self.launch_hook_body % (self.keep_select))
        # instantiate execjob_resize hook
        hook_event = 'execjob_resize'
        hook_name = 'resize'
        a = {'event': hook_event, 'enabled': 'true'}
        self.server.create_import_hook(
            hook_name, a, self.resize_hook_body % (''))
        # Submit a job that requires 2 nodes
        j = Job(TEST_USER)
        j.create_script(self.job_scr2)
        stime = int(time.time())
        jid = self.server.submit(j)
        # Check the exec_vnode while in substate 41
        self.server.expect(JOB, {ATTR_substate: '41'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode1 = job_stat[0]['exec_vnode']
        self.logger.info("initial exec_vnode: %s" % execvnode1)
        initial_vnodes = execvnode1.split('+')
        # Check the exec_resize hook reject message in mom superior logs
        self.momB.log_match(
            "Job;%s;Cannot resize the job" % (jid),
            starttime=stime, interval=2)
        # Check the exec_vnode after job is in substate 42
        self.server.expect(JOB, {ATTR_substate: '42'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode2 = job_stat[0]['exec_vnode']
        self.logger.info("pruned exec_vnode: %s" % execvnode2)
        pruned_vnodes = execvnode2.split('+')
        # Check that the pruned exec_vnode has one less than initial value
        self.assertEqual(len(pruned_vnodes) + 1, len(initial_vnodes))
        # Check that the exec_vnode got pruned
        self.momB.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.momB.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, execvnode2), starttime=stime)
        # Because of resize hook reject Mom failed to update the job.
        # Check that job got requeued
        self.server.log_match("Job;%s;Job requeued" % (jid), starttime=stime)

    def test_cgroup_msmom_nodes_only(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        job is using only vnodes from mother superior host,
        tolerate_node_failures=job_start
        """
        # Test requires 2 nodes
        if len(self.moms) != 2:
            self.skipTest('Test requires two Moms as input, '
                          'use -p moms=<mom1:mom2>')
        self.load_config(self.cfg7)
        # Check that MomA has two free vnodes and MomB has a free vnode
        if self.check_req_rjs() == 1:
            self.skipTest(
                'MomA must have two free vnodes and MomB one free vnode')
        # disable queuejob hook
        hook_event = 'queuejob'
        hook_name = 'qjob'
        a = {'event': hook_event, 'enabled': 'false'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)
        # instantiate execjob_launch hook
        hook_event = 'execjob_launch'
        hook_name = 'launch'
        a = {'event': hook_event, 'enabled': 'true'}
        self.keep_select = '"ncpus=4:mem=2gb"'
        self.server.create_import_hook(
            hook_name, a, self.launch_hook_body % (self.keep_select))
        # disable execjob_resize hook
        hook_event = 'execjob_resize'
        hook_name = 'resize'
        a = {'event': hook_event, 'enabled': 'false'}
        self.server.create_import_hook(
            hook_name, a, self.resize_hook_body % (''))
        # Submit a job that requires two vnodes on one host
        j = Job(TEST_USER)
        j.create_script(self.job_scr3)
        stime = int(time.time())
        jid = self.server.submit(j)
        # Check the exec_vnode while in substate 41
        self.server.expect(JOB, {ATTR_substate: '41'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode1 = job_stat[0]['exec_vnode']
        self.logger.info("initial exec_vnode: %s" % execvnode1)
        initial_vnodes = execvnode1.split('+')
        # Check the exec_vnode after job is in substate 42
        self.server.expect(JOB, {ATTR_substate: '42'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode2 = job_stat[0]['exec_vnode']
        self.logger.info("pruned exec_vnode: %s" % execvnode2)
        pruned_vnodes = execvnode2.split('+')
        # Check that the pruned exec_vnode has one less than initial value
        self.assertEqual(len(pruned_vnodes) + 1, len(initial_vnodes))
        # Check that the exec_vnode got pruned
        self.momA.log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.momA.log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, execvnode2), starttime=stime)
        # Find out the released vnode
        if initial_vnodes[0] == execvnode2:
            execvnodeB = initial_vnodes[1]
        else:
            execvnodeB = initial_vnodes[0]
        vnodeB = execvnodeB.split(':')[0].split('(')[1]
        self.logger.info("released vnode: %s" % vnodeB)
        # Submit job2 requesting the released vnode, job runs
        j2 = Job(TEST_USER, {
            ATTR_l + '.select': '1:ncpus=1:mem=2gb:vnode=%s' % vnodeB})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

    def tearDown(self):
        TestFunctional.tearDown(self)
        self.load_config(self.cfg0)
        if not self.iscray:
            self.remove_vntype()
        self.momA.delete_vnode_defs()
        if self.hostA != self.hostB:
            self.momB.delete_vnode_defs()
        events = '"execjob_begin,execjob_launch,execjob_attach,'
        events += 'execjob_epilogue,execjob_end,exechost_startup,'
        events += 'exechost_periodic,execjob_resize"'
        # Disable the cgroups hook
        conf = {'enabled': 'False', 'freq': 30, 'event': events}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        # Cleanup any temp file created
        self.logger.info('Deleting temporary files %s' % self.tempfile)
        self.du.rm(hostname=self.serverA, path=self.tempfile, force=True,
                   recursive=True, sudo=True)
        # Cleanup frozen jobs
        if 'freezer' in self.paths:
            self.logger.info('Cleaning up frozen jobs ****')
            fdir = self.paths['freezer']
            if os.path.isdir(fdir):
                self.logger.info('freezer directory present')
                fpath = os.path.join(fdir, 'PtlPbs')
                if os.path.isdir(fpath):
                    jid = glob.glob(os.path.join(fpath, '*', ''))
                    self.logger.info('found jobs %s' % jid)
                    if jid:
                        for files in jid:
                            self.logger.info('*** found jobdir %s' % files)
                            jpath = os.path.join(fpath, files)
                            freezer_file = os.path.join(jpath, 'freezer.state')
                            # Thaw the cgroup
                            state = 'THAWED'
                            fn = self.du.create_temp_file(
                                hostname=self.hostA, body=state)
                            self.du.run_copy(hosts=self.hostA, src=fn,
                                             dest=freezer_file, sudo=True,
                                             uid='root', gid='root',
                                             mode=0644)
                            self.du.rm(hostname=self.hostA, path=fn)
                            cmd = ['rmdir ', jpath]
                            self.logger.info('deleting jobdir %s' % cmd)
                            self.du.run_cmd(cmd=cmd, sudo=True)
                        self.du.rm(hostname=self.hostA, path=fpath)
        # Remove the jobdir if any under other cgroups
        cgroup_subsys = ('cpuset', 'memory', 'blkio', 'devices', 'cpuacct',
                         'pids', 'systemd')
        for subsys in cgroup_subsys:
            if subsys in self.paths and self.paths[subsys]:
                self.logger.info('Looking for orphaned jobdir in %s' % subsys)
                cdir = self.paths[subsys]
                if os.path.isdir(cdir):
                    cpath = os.path.join(cdir, 'pbspro')
                    if not os.path.isdir(cpath):
                        cpath = os.path.join(cdir, 'pbspro.slice')
                    if os.path.isdir(cpath):
                        for jdir in glob.glob(os.path.join(cpath, '*', '')):
                            if not os.path.isdir(jdir):
                                continue
                            self.logger.info('deleting jobdir %s' % jdir)
                            cmd2 = ['rmdir', jdir]
                            self.du.run_cmd(cmd=cmd2, sudo=True)

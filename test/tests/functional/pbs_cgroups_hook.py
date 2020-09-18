# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


import glob

from tests.functional import *


#
# FUNCTION convert_size
#
def convert_size(value, units='b'):
    """
    Convert a string containing a size specification (e.g. "1m") to a
    string using different units (e.g. "1024k").

    This function only interprets a decimal number at the start of the string,
    stopping at any unrecognized character and ignoring the rest of the string.

    When down-converting (e.g. MB to KB), all calculations involve integers and
    the result returned is exact. When up-converting (e.g. KB to MB) floating
    point numbers are involved. The result is rounded up. For example:

    1023MB -> GB yields 1g
    1024MB -> GB yields 1g
    1025MB -> GB yields 2g  <-- This value was rounded up

    Pattern matching or conversion may result in exceptions.
    """
    logs = {'b': 0, 'k': 10, 'm': 20, 'g': 30,
            't': 40, 'p': 50, 'e': 60, 'z': 70, 'y': 80}
    try:
        new = units[0].lower()
        if new not in logs:
            raise ValueError('Invalid unit value')
        result = re.match(r'([-+]?\d+)([bkmgtpezy]?)',
                          str(value).lower())
        if not result:
            raise ValueError('Unrecognized value')
        val, old = result.groups()
        if int(val) < 0:
            raise ValueError('Value may not be negative')
        if old not in logs:
            old = 'b'
        factor = logs[old] - logs[new]
        val = float(val)
        val *= 2 ** factor
        if (val - int(val)) > 0.0:
            val += 1.0
        val = int(val)
        return str(val) + units.lower()
    except Exception:
        return None


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
    if not mem_path:
        return 'false'
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
    if not isinstance(buf, str):
        raise ValueError('Not a basetype string')
    ret = ''
    for i, char in enumerate(buf):
        if i < 1 and char == '.':
            if (sys.version_info[0] < 3):
                ret += '\\x' + '.'.encode('hex')
            else:
                ret += '\\x' + b'.'.hex()
        elif char.isalnum() or char in '_.':
            ret += char
        elif char == '/':
            ret += '-'
        else:
            # Will turn non-ASCII into UTF-8 hex sequence on both Py2/3
            if (sys.version_info[0] < 3):
                hexval = char.encode('hex')
            else:
                hexval = char.encode('utf-8').hex()
            for j in range(0, len(hexval), 2):
                ret += '\\x' + hexval[j:j + 2]
    return ret


def count_items(items):
    """
    Given a comma-separated string of numerical items of either
    singular value or a range of values (<start>-<stop>),
    return the actual number of items.
    For example,
         items="4-6,9,12-15"
         count(items) = 8
    since items expands to "4,5,6,9,12,13,14,15"
    """
    ct = 0
    if items is None:
        return ct
    for i in items.split(','):
        j = i.split('-')
        if len(j) == 2:
            ct += len(range(int(j[0]), int(j[1]))) + 1
        else:
            ct += 1
    return ct


@tags('mom', 'multi_node')
class TestCgroupsHook(TestFunctional):

    """
    This test suite targets Linux Cgroups hook functionality.
    """

    def setUp(self):

        self.hook_name = 'pbs_cgroups'
        # Cleanup previous pbs_cgroup hook so as to not interfere with test
        c_hook = self.server.filter(HOOK, {'enabled': True}, id=self.hook_name)
        if c_hook:
            self.server.manager(MGR_CMD_DELETE, HOOK, id=self.hook_name)

        a = {'resources_available.ncpus': (EQ, 0), 'state': 'free'}
        no_cpu_vnodes = self.server.filter(VNODE, a, attrop=PTL_AND)
        if no_cpu_vnodes:
            # TestFunctional.setUp() would error out if leftover setup
            # has no cpus vnodes. Best to cleanup vnodes altogether.
            self.logger.info("Deleting the existing vnodes")
            self.mom.delete_vnode_defs()
            self.mom.restart()

        for mom in self.moms.values():
            if mom.is_cpuset_mom():
                mom.revert_to_default = False

        TestFunctional.setUp(self)

        # Some of the tests requires 2 or 3 nodes.
        # Setting the default values when no mom is specified

        self.vntypename = []
        self.iscray = False
        self.noprefix = False
        self.tempfile = []
        self.moms_list = []
        self.hosts_list = []
        self.nodes_list = []
        for cnt in range(0, len(self.moms)):
            mom = self.moms.values()[cnt]
            if mom.is_cray():
                self.iscray = True
            host = mom.shortname
            # Check if mom has needed cgroup mounted, otherwise skip test
            self.paths = self.get_paths(host)
            if not self.paths['cpuset']:
                self.skipTest('cpuset subsystem not mounted')
            self.logger.info("%s: cgroup cpuset is mounted" % host)
            if self.iscray:
                node = self.get_hostname(host)
            else:
                node = host
            vntype = self.get_vntype(host)
            if vntype is None:
                vntype = "no_cgroups"
            self.logger.info("vntype value is %s" % vntype)
            self.logger.info("Deleting the existing vnodes on %s" % host)
            mom.delete_vnode_defs()
            mom.restart()
            # Configure the mom
            self.logger.info("increase log level for mom and \
                             set polling intervals")
            c = {'$logevent': '0xffffffff', '$clienthost': self.server.name,
                 '$min_check_poll': 8, '$max_check_poll': 12}
            mom.add_config(c)

            self.moms_list.append(mom)
            self.hosts_list.append(host)
            self.nodes_list.append(node)
            self.vntypename.append(vntype)

        # Setting self.mom defaults to primary mom as some of
        # library methods assume that
        self.mom = self.moms_list[0]

        # Delete ALL vnodes
        # Re-creation moved to the end *after* we correctly set up the hook
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")

        self.serverA = self.servers.values()[0].name
        self.mem = 'true'
        if not self.paths['memory']:
            self.mem = 'false'
        self.swapctl = is_memsw_enabled(self.paths['memsw'])
        self.server.set_op_mode(PTL_CLI)
        self.server.cleanup_jobs()
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
        self.eatmem_script2 = """
import sys
import time
MB = 2 ** 20

iterations1 = 1
chunkSizeMb1 = 1
sleeptime1 = 0
if (len(sys.argv) > 1):
    iterations1 = int(sys.argv[1])
if (len(sys.argv) > 2):
    chunkSizeMb1 = int(sys.argv[2])
if (len(sys.argv) > 3):
    sleeptime1 = int(sys.argv[3])
if (iterations1 < 1):
    print('Iteration count must be greater than zero.')
    exit(1)
if (chunkSizeMb1 < 1):
    print('Chunk size must be greater than zero.')
    exit(1)
totalSizeMb1 = chunkSizeMb1 * iterations1
print('Allocating %d chunk(s) of size %dMB. (%dMB total)' %
      (iterations1, chunkSizeMb1, totalSizeMb1))
start_time1 = time.time()
buf = ''
for i in range(iterations1):
    print('allocating %dMB' % ((i + 1) * chunkSizeMb1))
    buf += ('#' * MB * chunkSizeMb1)
end_time1 = time.time()
if sleeptime1 > 0 and (end_time1 - start_time1) < sleeptime1 :
    time.sleep(sleeptime1 - end_time1 + start_time1)

if len(sys.argv) <= 4:
    exit(0)

iterations2 = 1
chunkSizeMb2 = 1
sleeptime2 = 0
if (len(sys.argv) > 4):
    iterations2 = int(sys.argv[4])
if (len(sys.argv) > 5):
    chunkSizeMb2 = int(sys.argv[5])
if (len(sys.argv) > 6):
    sleeptime2 = int(sys.argv[6])
if (iterations2 < 1):
    print('Iteration count must be greater than zero.')
    exit(1)
if (chunkSizeMb2 < 1):
    print('Chunk size must be greater than zero.')
    exit(1)
totalSizeMb2 = chunkSizeMb2 * iterations2
print('Allocating %d chunk(s) of size %dMB. (%dMB total)' %
      (iterations2, chunkSizeMb2, totalSizeMb2))
start_time2 = time.time()
# Do not reinitialize buf!!
for i in range(iterations2):
    print('allocating %dMB' % ((i + 1) * chunkSizeMb2))
    buf += ('#' * MB * chunkSizeMb2)
end_time2 = time.time()
if sleeptime2 > 0 and (end_time2 - start_time2) < sleeptime2 :
    time.sleep(sleeptime2 - end_time2 + start_time2)
"""
        self.eatmem_job1 = \
            '#PBS -joe\n' \
            '#PBS -S /bin/bash\n' \
            'sync\n' \
            'sleep 4\n' \
            'python_path=`which python 2>/dev/null`\n' \
            'python3_path=`which python3 2>/dev/null`\n' \
            'python2_path=`which python2 2>/dev/null`\n' \
            'if [ -z "$python_path" ]; then\n' \
            '    if [ -n "$python3_path" ]; then\n' \
            '        python_path=$python3_path\n' \
            '    else\n' \
            '        python_path=$python2_path\n' \
            '    fi\n' \
            'fi\n' \
            'if [ -z "$python_path" ]; then\n' \
            '    echo Exiting -- no python found\n' \
            '    exit 1\n' \
            'fi\n' \
            '$python_path - 80 10 10 <<EOF\n' \
            '%s\nEOF\n' % self.eatmem_script
        self.eatmem_job2 = \
            '#PBS -joe\n' \
            '#PBS -S /bin/bash\n' \
            'sync\n' \
            'python_path=`which python 2>/dev/null`\n' \
            'python3_path=`which python3 2>/dev/null`\n' \
            'python2_path=`which python2 2>/dev/null`\n' \
            'if [ -z "$python_path" ]; then\n' \
            '    if [ -n "$python3_path" ]; then\n' \
            '        python_path=$python3_path\n' \
            '    else\n' \
            '        python_path=$python2_path\n' \
            '    fi\n' \
            'fi\n' \
            'if [ -z "$python_path" ]; then\n' \
            '    echo Exiting -- no python found\n' \
            '    exit 1\n' \
            'fi\n' \
            'let i=0; while [ $i -lt 400000 ]; do let i+=1 ; done\n' \
            '$python_path - 200 2 10 <<EOF\n' \
            '%s\nEOF\n' \
            'let i=0; while [ $i -lt 400000 ]; do let i+=1 ; done\n' \
            '$python_path - 100 4 10 <<EOF\n' \
            '%s\nEOF\n' \
            'let i=0; while [ $i -lt 400000 ]; do let i+=1 ; done\n' \
            'sleep 25\n' % (self.eatmem_script, self.eatmem_script)
        self.eatmem_job3 = \
            '#PBS -joe\n' \
            '#PBS -S /bin/bash\n' \
            'sync\n' \
            'python_path=`which python 2>/dev/null`\n' \
            'python3_path=`which python3 2>/dev/null`\n' \
            'python2_path=`which python2 2>/dev/null`\n' \
            'if [ -z "$python_path" ]; then\n' \
            '    if [ -n "$python3_path" ]; then\n' \
            '        python_path=$python3_path\n' \
            '    else\n' \
            '        python_path=$python2_path\n' \
            '    fi\n' \
            'fi\n' \
            'if [ -z "$python_path" ]; then\n' \
            '    echo Exiting -- no python found\n' \
            '    exit 1\n' \
            'fi\n' \
            'timeout 8 md5sum </dev/urandom\n' \
            '# Args are segments1 sizeMB1 sleep1 segments2 sizeMB2 sleep2\n' \
            '$python_path -  9 25 9  8 25 300 <<EOF\n' \
            '%s\nEOF\n' % self.eatmem_script2

        self.cpuset_mem_script = """
base='%s'
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
mbase='%s'
if [ "${mbase}" != "None" ] ; then
    echo "cgroups base path for memory is $mbase"
    if [ -d $mbase ]; then
        mem_limit=`cat $mbase/memory.limit_in_bytes`
        echo "MemoryLimit=${mem_limit}"
        memsw_limit=`cat $mbase/memory.memsw.limit_in_bytes`
        echo "MemswLimit=${memsw_limit}"
    else
        echo "Memory subsystem job directory not created."
    fi
fi
"""
# no need to cater for cgroup_prefix options, it is obviously sbp here
        self.check_dirs_script = """
PBS_JOBID='%s'
jobnum=${PBS_JOBID%%.*}
devices_base='%s'
if [ -d "$devices_base/sbp" ]; then
    if [ -d "$devices_base/sbp/$PBS_JOBID" ]; then
        devices_job="$devices_base/sbp/$PBS_JOBID"
    elif [ -d "$devices_base/sbp.service/jobid/$PBS_JOBID" ]; then
        devices_job="$devices_base/sbp.service/jobid/$PBS_JOBID"
    else
        devices_job="$devices_base/sbp/sbp-${jobnum}.*.slice"
    fi
elif [ -d "$devices_base/sbp.service/jobid/$PBS_JOBID" ]; then
    devices_job="$devices_base/sbp.service/jobid/$PBS_JOBID"
else
    devices_job="$devices_base/sbp.slice/sbp-${jobnum}.*.slice"
fi
echo "devices_job: $devices_job"
sleep 10
if [ -d $devices_job ]; then
    device_list=`cat $devices_job/devices.list`
    echo "${device_list}"
else
    echo "Devices directory should be populated"
fi
"""

        self.check_gpu_script = """#!/bin/bash
#PBS -joe

jobnum=${PBS_JOBID%%.*}
devices_base=`grep cgroup /proc/mounts | grep devices | cut -d' ' -f2`
if [ -d "$devices_base/sbp" ]; then
    if [ -d "$devices_base/sbp/$PBS_JOBID" ]; then
        devices_job="$devices_base/sbp/$PBS_JOBID"
    elif [ -d "$devices_base/sbp.service/jobid/$PBS_JOBID" ]; then
        devices_job="$devices_base/sbp.service/jobid/$PBS_JOBID"
        devices_job="$devices_base/sbp/sbp-${jobnum}.*.slice"
    fi
elif [ -d "$devices_base/sbp.service/jobid/$PBS_JOBID" ]; then
    devices_job="$devices_base/sbp.service/jobid/$PBS_JOBID"
else
    devices_job="$devices_base/sbp.slice/sbp-${jobnum}.*.slice"
sleep 10
"""
        self.cpu_controller_script = """
base='%s'
echo "cgroups base path for cpuset is $base"
if [ -d $base ]; then
    shares=$base/cpu.shares
    echo shares=${shares}
    if [ -f $shares ]; then
        cpu_shares=`cat $shares`
        echo "cpu_shares=${cpu_shares}"
    fi
    cfs_period_us=$base/cpu.cfs_period_us
    echo cfs_period_us=${cfs_period_us}
    if [ -f $cfs_period_us ]; then
        cpu_cfs_period_us=`cat $cfs_period_us`
        echo "cpu_cfs_period_us=${cpu_cfs_period_us}"
    fi
    cfs_quota_us=$base/cpu.cfs_quota_us
    echo cfs_quota_us=$cfs_quota_us
    if [ -f $cfs_quota_us ]; then
        cpu_cfs_quota_us=`cat $cfs_quota_us`
        echo "cpu_cfs_quota_us=${cpu_cfs_quota_us}"
    fi
else
    echo "Cpu subsystem job directory not created."
fi
"""
        self.sleep15_job = """#!/bin/bash
#PBS -joe
sleep 15
"""
        self.sleep30_job = """#!/bin/bash
#PBS -joe
sleep 30
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
#PBS -l select=host=%s:ncpus=1+ncpus=1
#PBS -l place=vscatter
#PBS -W umask=022
#PBS -koe
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
sleep 300
"""
        self.job_scr3 = """#!/bin/bash
#PBS -l select=2:ncpus=1:mem=100mb
#PBS -l place=vscatter
#PBS -W umask=022
#PBS -W tolerate_node_failures=job_start
#PBS -koe
echo "$PBS_NODEFILE"
cat $PBS_NODEFILE
sleep 300
"""
        self.cfg0 = """{
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
            "enabled"         : %s,
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
    "cgroup_prefix"         : "sbp",
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
    "exclude_hosts"         : [],
    "exclude_vntypes"       : [%s],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : true,
    "vnode_per_numa_node"   : %s,
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
            "enabled"         : %s,
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
            "enabled"         : %s,
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
            "enabled" : %s
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
            "enabled"         : %s,
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
            "enabled"            : %s,
            "exclude_hosts"      : [],
            "exclude_vntypes"    : [],
            "default"            : "256MB",
            "reserve_amount"     : "64MB"
        },
        "memsw" : {
            "enabled"            : %s,
            "exclude_hosts"      : [],
            "exclude_vntypes"    : [],
            "default"            : "256MB",
            "reserve_amount"     : "64MB"
        }
    }
}
"""
        self.cfg8 = """{
    "exclude_hosts"         : [],
    "exclude_vntypes"       : [%s],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : true,
    "vnode_per_numa_node"   : false,
    "online_offlined_nodes" : true,
    "use_hyperthreads"      : true,
    "ncpus_are_cores"       : true,
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
            "enabled"         : %s,
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
        self.cfg9 = """{
    "exclude_hosts"         : [],
    "exclude_vntypes"       : [],
    "run_only_on_hosts"     : [],
    "periodic_resc_update"  : true,
    "vnode_per_numa_node"   : true,
    "online_offlined_nodes" : true,
    "use_hyperthreads"      : true,
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
            "enabled"            : %s,
            "exclude_hosts"      : [],
            "exclude_vntypes"    : [],
            "default"            : "256MB",
            "reserve_amount"     : "64MB"
        },
        "memsw" : {
            "enabled"            : %s,
            "exclude_hosts"      : [],
            "exclude_vntypes"    : [],
            "default"            : "256MB",
            "reserve_amount"     : "64MB"
        }
    }
}
"""
        self.cfg10 = """{
    "exclude_hosts"         : [],
    "exclude_vntypes"       : ["no_cgroups"],
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
            "exclude_cpus"    : [],
            "exclude_hosts"   : [],
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
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "cpu" : {
            "enabled"                    : true,
            "enforce_per_period_quota"   : true
          }
    }
}
"""
        self.cfg11 = """{
    "exclude_hosts"         : [],
    "exclude_vntypes"       : ["no_cgroups"],
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
            "exclude_cpus"    : [],
            "exclude_hosts"   : [],
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
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "cpu" : {
            "enabled"                    : true,
            "enforce_per_period_quota"   : true,
            "cfs_period_us"              : %d,
            "cfs_quota_fudge_factor"     : %f
          }
    }
}
"""
        self.cfg12 = """{
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
            "exclude_cpus"    : [],
            "exclude_hosts"   : [],
            "exclude_vntypes" : [],
            "allow_zero_cpus" : true
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
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "cpu" : {
            "enabled"                    : true,
            "enforce_per_period_quota"   : true
          }
    }
}
"""
        self.cfg13 = """{
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
            "exclude_cpus"    : [],
            "exclude_hosts"   : [],
            "exclude_vntypes" : [],
            "allow_zero_cpus" : true
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
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "memsw":
        {
            "enabled"         : %s,
            "default"         : "256MB",
            "reserve_amount"  : "64MB",
            "exclude_hosts"   : [],
            "exclude_vntypes" : []
        },
        "cpu" : {
            "enabled"                    : true,
            "enforce_per_period_quota"   : true,
            "cfs_period_us"              : %d,
            "cfs_quota_fudge_factor"     : %f,
            "zero_cpus_shares_fraction"  : %f,
            "zero_cpus_quota_fraction"   : %f
          }
    }
}
"""
        Job.dflt_attributes[ATTR_k] = 'oe'
        # Increase the server log level
        a = {'log_events': '4095'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        # Configure the scheduler to schedule using vmem
        a = {'resources': 'ncpus,mem,vmem,host,vnode,ngpus,nmics'}
        self.scheduler.set_sched_config(a)
        # Create resources
        attr = {'type': 'long', 'flag': 'nh'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='nmics',
                            logerr=False)
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='ngpus',
                            logerr=False)
        # Import the hook
        self.hook_file = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                      'lib',
                                      'python',
                                      'altair',
                                      'pbs_hooks',
                                      'pbs_cgroups.PY')

        # Load hook, but do not check MoMs
        # since the vnodes are deleted on the server
        self.load_hook(self.hook_file, mom_checks=False)

        # Recreate the nodes moved to the end, after we set up
        # the hook with its default config
        # Make sure the load_hook is done on server first
        time.sleep(2)
        for host in self.hosts_list:
            self.server.manager(MGR_CMD_CREATE, NODE, id=host)

        # Make sure that by the time we send a HUP and the test
        # actually tinkers with the hooks once more,
        # MoM will already have gone through its initial setup
        # after the new hello from the server
        time.sleep(4)

        # HUP mom so exechost_startup hook is run for each mom...
        for mom in self.moms_list:
            mom.signal('-HUP')
        # ...then wait for exechost_startup updates to propagate to server
        time.sleep(4)

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

    def get_paths(self, host):
        """
        Returns a dictionary containing the location where each cgroup
        is mounted on host.
        """
        paths = {'pids': None,
                 'blkio': None,
                 'systemd': None,
                 'cpuset': None,
                 'memory': None,
                 'memsw': None,
                 'cpuacct': None,
                 'devices': None,
                 'cpu': None,
                 'hugetlb': None,
                 'perf_event': None,
                 'freezer': None,
                 'net_cls': None,
                 'net_prio': None}
        # Loop through the mounts and collect the ones for cgroups
        fd = self.du.cat(host, '/proc/mounts')
        for line in fd['out']:
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
            if 'cpu' in flags:
                paths['cpu'] = paths[subsys]
            # Add these to support future unified hierarchy
            # (everything in one dir)
            if paths['pids'] is None and 'pids' in flags:
                paths['pids'] = paths[subsys]
            if paths['blkio'] is None and 'blkio' in flags:
                paths['blkio'] = paths[subsys]
            if paths['systemd'] is None and 'systemd' in flags:
                paths['systemd'] = paths[subsys]
            if paths['cpuset'] is None and 'cpuset' in flags:
                paths['cpuset'] = paths[subsys]
            if paths['hugetlb'] is None and 'hugetlb' in flags:
                paths['hugetlb'] = paths[subsys]
            if paths['perf_event'] is None and 'perf_event' in flags:
                paths['perf_event'] = paths[subsys]
            if paths['freezer'] is None and 'freezer' in flags:
                paths['freezer'] = paths[subsys]
            if paths['net_cls'] is None and 'net_cls' in flags:
                paths['net_cls'] = paths[subsys]
            if paths['net_prio'] is None and 'net_prio' in flags:
                paths['net_prio'] = paths[subsys]
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
            time.sleep(0.5)
        return False

    def get_cgroup_job_dir(self, subsys, jobid, host):
        """
        Returns path of subsystem for jobid
        """
        basedir = self.paths[subsys]
        # One of the entries in the following list should exist
        #
        # This cleaned version assumes cgroup_prefix is always pbs_jobs,
        # i.e. that cgroup_prefix is not changed if you use this routine
        #
        # The separate test for a different prefix ("sbp") uses its own
        # script instead; that script need not support multi-host jobs
        #
        # Older possible per job paths (relative to the basedir) looked:
        # 1) <prefix>.slice/<prefix>-<jobid>.slice
        #     (and <jobid> needs to be passed through systemd_escape)
        # 2) <prefix>/<jobid>
        #
        # Some older hooks used either depending on the OS platform
        # which was the reason to support a list in the first place
        #
        # If you need to add paths to make the tests support older hooks,
        # put the least likely paths at the end of the list, to avoid
        # changing test timings too much.
        #
        jobdirs = [os.path.join(basedir, 'pbs_jobs.service/jobid', jobid)]
        for jdir in jobdirs:
            if self.du.isdir(hostname=host, path=jdir, sudo=True):
                return jdir
        return None

    def find_main_cpath(self, cdir):
        if os.path.isdir(cdir):
            paths = ['pbs_jobs.service/jobid',
                     'pbs.service/jobid',
                     'pbs.slice',
                     'pbs']
            for p in paths:
                cpath = os.path.join(cdir, p)
                if os.path.isdir(cpath):
                    return cpath
        return None

    def load_hook(self, filename, mom_checks=True):
        """
        Import and enable a hook pointed to by the URL specified.
        """
        try:
            with open(filename, 'r') as fd:
                script = fd.read()
        except IOError:
            self.assertTrue(False, 'Failed to open hook file %s' % filename)
        events = ['execjob_begin', 'execjob_launch', 'execjob_attach',
                  'execjob_epilogue', 'execjob_end', 'exechost_startup',
                  'exechost_periodic', 'execjob_resize', 'execjob_abort']
        a = {'enabled': 'True',
             'freq': '10',
             'alarm': 30,
             'event': events}
        # Sometimes the deletion of the old hook is still pending
        failed = True
        for _ in range(5):
            try:
                self.server.create_import_hook(self.hook_name, a, script,
                                               overwrite=True,
                                               level=logging.DEBUG)
            except Exception:
                time.sleep(2)
            else:
                failed = False
                break
        if failed:
            self.skipTest('pbs_cgroups_hook: failed to load hook')
        # Add the configuration
        self.load_default_config(mom_checks=mom_checks)

    def load_config(self, cfg, mom_checks=True):
        """
        Create a hook configuration file with the provided contents.
        """
        fn = self.du.create_temp_file(hostname=self.serverA, body=cfg)
        self.tempfile.append(fn)
        self.logger.info('Current config: %s' % cfg)
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': fn}
        # In tests that use this, make sure that other hook CF
        # copies from setup, node creations, MoM restarts etc.
        # are all finished, so that we don't match a CF copy
        # message in the logs from someone else!
        time.sleep(5)
        just_before_import = time.time() - 1
        self.server.manager(MGR_CMD_IMPORT, HOOK, a, self.hook_name)
        if mom_checks:
            self.moms_list[0].log_match('pbs_cgroups.CF;'
                                        'copy hook-related '
                                        'file request received',
                                        starttime=just_before_import)
        pbs_home = self.server.pbs_conf['PBS_HOME']
        svr_conf = os.path.join(
            os.sep, pbs_home, 'server_priv', 'hooks', 'pbs_cgroups.CF')
        pbs_home = self.mom.pbs_conf['PBS_HOME']
        mom_conf = os.path.join(
            os.sep, pbs_home, 'mom_priv', 'hooks', 'pbs_cgroups.CF')
        if mom_checks:
            # reload config if server and mom cfg differ up to count times
            count = 5
            while (count > 0):
                r1 = self.du.run_cmd(cmd=['cat', svr_conf], sudo=True)
                r2 = self.du.run_cmd(cmd=['cat', mom_conf], sudo=True)
                if r1['out'] != r2['out']:
                    self.logger.info('server & mom pbs_cgroups.CF differ')
                    just_before_import = time.time() - 1
                    self.server.manager(MGR_CMD_IMPORT, HOOK, a,
                                        self.hook_name)
                    self.moms_list[0].log_match('pbs_cgroups.CF;'
                                                'copy hook-related '
                                                'file request received',
                                                starttime=just_before_import)
                else:
                    self.logger.info('server & mom pbs_cgroups.CF match')
                    break
                time.sleep(1)
                count -= 1
            self.assertGreater(count, 0, "pbs_cgroups.CF failed to load")
            # A HUP of each mom ensures update to hook config file is
            # seen by the exechost_startup hook.
            for mom in self.moms_list:
                mom.signal('-HUP')

    def load_default_config(self, mom_checks=True):
        """
        Load the default pbs_cgroups hook config file
        """
        self.config_file = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                        'lib',
                                        'python',
                                        'altair',
                                        'pbs_hooks',
                                        'pbs_cgroups.CF')

        now = time.time()
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': self.config_file}
        self.server.manager(MGR_CMD_IMPORT, HOOK, a, self.hook_name)
        if not mom_checks:
            return
        self.moms_list[0].log_match('pbs_cgroups.CF;copy hook-related '
                                    'file request received',
                                    starttime=now)

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
                               gid='root', mode=0o644)
        if ret['rc'] != 0:
            self.skipTest('pbs_cgroups_hook: failed to set vntype')

    def remove_vntype(self):
        """
        Unset the vnode type on the moms.
        """
        for mom in self.moms_list:
            pbs_home = mom.pbs_conf['PBS_HOME']
            vn_file = os.path.join(pbs_home, 'mom_priv', 'vntype')
            host = mom.shortname
            self.logger.info('Deleting vntype files %s from mom %s'
                             % (vn_file, host))
            ret = self.du.rm(hostname=host, path=vn_file,
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

    @requirements(num_moms=2)
    def test_cgroup_vntype_excluded(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have an exclude vntype file set
        """
        name = 'CGROUP8'
        if self.vntypename[0] == 'no_cgroups':
            self.logger.info('Adding vntype %s to mom %s ' %
                             (self.vntypename[0], self.moms_list[0]))
            self.set_vntype(typestring=self.vntypename[0],
                            host=self.hosts_list[0])
        a = self.cfg1 % ('', '"' + self.vntypename[0] + '"',
                         '', '', self.mem, self.swapctl)
        self.load_config(a)
        for m in self.moms.values():
            m.restart()
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name}
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
        cpath = self.get_cgroup_job_dir('memory', jid, self.hosts_list[0])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[0]))
        self.moms_list[0].log_match(
            "%s is in the excluded vnode type list: ['%s']"
            % (self.vntypename[0],
               self.vntypename[0]),
            starttime=self.server.ctime)
        self.logger.info('vntypes on both hosts are: %s and %s'
                         % (self.vntypename[0], self.vntypename[1]))
        if self.vntypename[1] == self.vntypename[0]:
            self.logger.info('Skipping the second part of this test '
                             'since hostB also has same vntype value')
            return
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[1], ATTR_N: name}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid2 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j1.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hosts_list[1])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[1]))

    @requirements(num_moms=2)
    def test_cgroup_host_excluded(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have the exclude_hosts set
        """
        name = 'CGROUP9'
        mom, log = self.get_host_names(self.hosts_list[0])
        self.load_config(self.cfg1 % ('%s' % mom, '', '', '',
                                      self.mem, self.swapctl))
        for m in self.moms.values():
            m.restart()
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid, self.hosts_list[0])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[0]))
        host = self.get_hostname(self.hosts_list[0])
        self.moms_list[0].log_match('%s is in the excluded host list: [%s]' %
                                    (host, log), starttime=self.server.ctime)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[1], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hosts_list[1])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[1]))

    @requirements(num_moms=2)
    def test_cgroup_exclude_vntype_mem(self):
        """
        Test to verify that cgroups are not enforced on nodes
        that have an exclude vntype file set
        """
        name = 'CGROUP12'
        if self.vntypename[0] == 'no_cgroups':
            self.logger.info('Adding vntype %s to mom %s' %
                             (self.vntypename[0], self.moms_list[0]))
            self.set_vntype(typestring='no_cgroups', host=self.hosts_list[0])
        self.load_config(self.cfg3 % ('', 'false', '', self.mem,
                                      '"' + self.vntypename[0] + '"',
                                      self.swapctl,
                                      '"' + self.vntypename[0] + '"'))
        for m in self.moms.values():
            m.restart()
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s'
             % self.hosts_list[0], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        self.moms_list[0].log_match('cgroup excluded for subsystem memory '
                                    'on vnode type %s' % self.vntypename[0],
                                    starttime=self.server.ctime)
        self.logger.info('vntype values for each hosts are: %s and %s'
                         % (self.vntypename[0], self.vntypename[1]))
        if self.vntypename[0] == self.vntypename[1]:
            self.logger.info('Skipping the second part of this test '
                             'since hostB also has same vntype value')
            return
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hosts_list[1], ATTR_N: name}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid2 = self.server.submit(j1)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j1.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hosts_list[1])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[1]))

    def test_cgroup_periodic_update_check_values(self):
        """
        Test to verify that cgroups are reporting usage for cput and mem
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        name = 'CGROUP13'
        conf = {'freq': 2}
        self.server.manager(MGR_CMD_SET, HOOK, conf, self.hook_name)
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb:host=%s' %
             self.hosts_list[0], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job3)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        # Scouring the logs for initial values takes too long
        resc_list = ['resources_used.mem']
        if self.swapctl == 'true':
            resc_list.append('resources_used.vmem')
        qstat = self.server.status(JOB, resc_list, id=jid)
        mem = convert_size(qstat[0]['resources_used.mem'], 'kb')
        match = re.match(r'(\d+)kb', mem)
        self.assertFalse(match is None)
        usage = int(match.groups()[0])
        self.assertGreater(300000, usage)
        if self.swapctl == 'true':
            vmem = convert_size(qstat[0]['resources_used.vmem'], 'kb')
            match = re.match(r'(\d+)kb', vmem)
            self.assertFalse(match is None)
            usage = int(match.groups()[0])
            self.assertGreater(300000, usage)
        err_msg = "Unexpected error in pbs_cgroups " + \
            "handling exechost_periodic event: TypeError"
        self.moms_list[0].log_match(err_msg, max_attempts=3,
                                    interval=1, n=100, existence=False)
        # Allow some time to pass for values to be updated
        begin = time.time()
        self.logger.info('Waiting for periodic hook to update usage data.')
        # loop to check if cput, mem, vmem are expected values
        cput_usage = 0.0
        mem_usage = 0
        vmem_usage = 0
        for count in range(10):
            # Faster systems might have expected usage after 8 seconds
            # TH3 can take up to a minute
            time.sleep(8)
            if self.paths['cpuacct'] and cput_usage <= 1.0:
                lines = self.moms_list[0].log_match(
                    '%s;update_job_usage: CPU usage:' %
                    jid, allmatch=True, starttime=begin)
                for line in lines:
                    match = re.search(r'CPU usage: ([0-9.]+) secs', line[1])
                    if not match:
                        continue
                    cput_usage = float(match.groups()[0])
                    if cput_usage > 1.0:
                        break
            if self.paths['memory'] and mem_usage <= 400000:
                lines = self.moms_list[0].log_match(
                    '%s;update_job_usage: Memory usage: mem=' % jid,
                    allmatch=True, starttime=begin)
                for line in lines:
                    match = re.search(r'mem=(\d+)kb', line[1])
                    if not match:
                        continue
                    mem_usage = int(match.groups()[0])
                    if mem_usage > 400000:
                        break
                if self.swapctl == 'true' and vmem_usage <= 400000:
                    lines = self.moms_list[0].log_match(
                        '%s;update_job_usage: Memory usage: vmem=' % jid,
                        allmatch=True, starttime=begin)
                    for line in lines:
                        match = re.search(r'vmem=(\d+)kb', line[1])
                        if not match:
                            continue
                        vmem_usage = int(match.groups()[0])
                        if vmem_usage > 400000:
                            break
            if cput_usage > 1.0 and mem_usage > 400000:
                if self.swapctl == 'true':
                    if vmem_usage > 400000:
                        break
                else:
                    break
        self.assertGreater(cput_usage, 1.0)
        self.assertGreater(mem_usage, 400000)
        if self.swapctl == 'true':
            self.assertGreater(vmem_usage, 400000)

    def test_cgroup_cpuset_and_memory(self):
        """
        Test to verify that the job cgroup is created correctly
        Check to see that cpuset.cpus=0, cpuset.mems=0 and that
        memory.limit_in_bytes = 314572800
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        name = 'CGROUP1'
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # This test expects the job to land on CPU 0.
        # The previous test may have qdel -Wforce its jobs, and then it takes
        # some time for MoM to run the execjob_epilogue and execjob_end
        # *after* the job has disappeared on the server.
        # So wait a while before restarting MoM
        time.sleep(10)
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        a = {'Resource_List.select':
             '1:ncpus=1:mem=300mb:host=%s' % self.hosts_list[0],
             ATTR_N: name, ATTR_k: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        fna = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        self.assertFalse(fna is None, 'No job directory for cpuset subsystem')
        fnma = self.get_cgroup_job_dir('memory', jid, self.hosts_list[0])
        self.assertFalse(fnma is None, 'No job directory for memory subsystem')
        memscr = self.du.run_cmd(cmd=[self.cpuset_mem_script % (fna, fnma)],
                                 as_script=True)
        memscr_out = memscr['out']
        self.logger.info('memscr_out:\n%s' % memscr_out)
        self.assertTrue('CpuIDs=0' in memscr_out)
        self.logger.info('CpuIDs check passed')
        self.assertTrue('MemorySocket=0' in memscr_out)
        self.logger.info('MemorySocket check passed')
        if self.swapctl == 'true':
            self.assertTrue('MemoryLimit=314572800' in memscr_out)
            self.logger.info('MemoryLimit check passed')

    def test_cgroup_cpuset_and_memsw(self):
        """
        Test to verify that the job cgroup is created correctly
        using the default memory and vmem
        Check to see that cpuset.cpus=0, cpuset.mems=0 and that
        memory.limit_in_bytes = 100663296
        memory.memsw.limit_in_bytes = 100663296
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        name = 'CGROUP2'
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        a = {'Resource_List.select': '1:ncpus=1:host=%s' %
             self.hosts_list[0], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        fnm = self.get_cgroup_job_dir('memory', jid, self.hosts_list[0])
        scr = self.du.run_cmd(cmd=[self.cpuset_mem_script % (fn, fnm)],
                              as_script=True)
        scr_out = scr['out']
        self.logger.info('scr_out:\n%s' % scr_out)
        self.assertTrue('CpuIDs=0' in scr_out)
        self.logger.info('CpuIDs check passed')
        self.assertTrue('MemorySocket=0' in scr_out)
        self.logger.info('MemorySocket check passed')
        if self.swapctl == 'true':
            self.assertTrue('MemoryLimit=100663296' in scr_out)
            self.assertTrue('MemswLimit=100663296' in scr_out)
            self.logger.info('MemoryLimit check passed')

    def test_cgroup_prefix_and_devices(self):
        """
        Test to verify that the cgroup prefix is set to "sbp" and that
        the devices subsystem exists with the correct devices allowed
        """
        if not self.paths['devices']:
            self.skipTest('Skipping test since no devices subsystem defined')
        name = 'CGROUP3'
        self.load_config(self.cfg2)
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        # Make sure to run on the MoM just restarted
        a = {ATTR_N: name}
        a['Resource_List.select'] = \
            '1:ncpus=1:mem=300mb:host=%s' % self.hosts_list[0]
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(20)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        devd = self.paths['devices']
        scr = self.du.run_cmd(
            cmd=[self.check_dirs_script % (jid, devd)],
            as_script=True)
        scr_out = scr['out']
        self.logger.info('scr_out:\n%s' % scr_out)
        # the config file named entries must be translated to major/minor
        # containers will make them different!!
        # self.du.run_cmd returns a list of one-line strings
        # the console awk command produces major and minor on separate lines
        console_results = \
            self.du.run_cmd(cmd=['ls -al /dev/console'
                                 '| awk \'BEGIN {FS=" |,"} '
                                 '{print $5} {print $7}\''],
                            as_script=True)
        (console_major, console_minor) = console_results['out']
        # only one line here
        tty0_major_results = \
            self.du.run_cmd(cmd=['ls -al /dev/tty0'
                                 '| awk \'BEGIN {FS=" |,"} '
                                 '{print $5}\''],
                            as_script=True)
        tty0_major = tty0_major_results['out'][0]
        check_devices = ['b *:* rwm',
                         'c %s:%s rwm' % (console_major, console_minor),
                         'c %s:* rwm' % (tty0_major),
                         'c 1:* rwm',
                         'c 10:* rwm']

        for device in check_devices:
            self.assertTrue(device in scr_out,
                            '"%s" not found in: %s' % (device, scr_out))
        self.logger.info('device_list check passed')

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
        # since we do not configure vnodes ourselves wait for the setup
        # of this test to propagate all hooks etc.
        # otherwise the load_config tests to see if it's all done
        # might get confused
        # occasional trouble seen on TH2
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        # Submit two jobs
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name + 'a'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid1 = self.server.submit(j1)
        b = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name + 'b'}
        j2 = Job(TEST_USER, attrs=b)
        j2.create_script(self.sleep15_job)
        jid2 = self.server.submit(j2)
        a = {'job_state': 'R'}
        # Make sure they are both running
        self.server.expect(JOB, a, jid1)
        self.server.expect(JOB, a, jid2)
        # cpuset paths for both jobs
        fn1 = self.get_cgroup_job_dir('cpuset', jid1, self.hosts_list[0])
        fn2 = self.get_cgroup_job_dir('cpuset', jid2, self.hosts_list[0])
        # Capture the output of cpuset_mem_script for both jobs
        scr1 = self.du.run_cmd(cmd=[self.cpuset_mem_script % (fn1, None)],
                               as_script=True)
        scr1_out = scr1['out']
        self.logger.info('scr1_out:\n%s' % scr1_out)
        scr2 = self.du.run_cmd(cmd=[self.cpuset_mem_script % (fn2, None)],
                               as_script=True)
        scr2_out = scr2['out']
        self.logger.info('scr2_out:\n%s' % scr2_out)
        # Ensure the CPU ID for each job differs
        cpuid1 = None
        for kv in scr1_out:
            if 'CpuIDs=' in kv:
                cpuid1 = kv
                break
        self.assertNotEqual(cpuid1, None, 'Could not read first CPU ID.')
        cpuid2 = None
        for kv in scr2_out:
            if 'CpuIDs=' in kv:
                cpuid2 = kv
                break
        self.assertNotEqual(cpuid2, None, 'Could not read second CPU ID.')
        self.logger.info("cpuid1 = %s and cpuid2 = %s" % (cpuid1, cpuid2))
        self.assertNotEqual(cpuid1, cpuid2,
                            'Processes should be assigned to different CPUs')
        self.logger.info('CpuIDs check passed')

    @timeout(1800)
    def test_cgroup_cpuset_ncpus_are_cores(self):
        """
        Test to verify that correct number of jobs run on a hyperthread
        enabled system when ncpus_are_cores is set to true.
        """
        # Check that system has hyperthreading enabled and has
        # at least two threads ("pcpus")
        # WARNING: do not assume that physical CPUs are numbered from 0
        # and that all processors from a physical ID are contiguous
        # count the number of different physical IDs with a set!
        pcpus = 0
        sibs = 0
        cores = 0
        pval = 0
        phys_set = set()
        with open('/proc/cpuinfo', 'r') as desc:
            for line in desc:
                if re.match('^processor', line):
                    pcpus += 1
                sibs_match = re.search(r'siblings	: ([0-9]+)', line)
                cores_match = re.search(r'cpu cores	: ([0-9]+)', line)
                phys_match = re.search(r'physical id	: ([0-9]+)', line)
                if sibs_match:
                    sibs = int(sibs_match.groups()[0])
                if cores_match:
                    cores = int(cores_match.groups()[0])
                if phys_match:
                    pval = int(phys_match.groups()[0])
                    phys_set.add(pval)
        phys = len(phys_set)
        if (sibs == 0 or cores == 0):
            self.skipTest('Insufficient information about the processors.')
        if pcpus < 2:
            self.skipTest('This test requires at least two processors.')
        if sibs / cores == 1:
            self.skipTest('This test requires hyperthreading to be enabled.')

        name = 'CGROUP18'
        self.load_config(self.cfg8 % ('', '', self.mem, '', self.swapctl,
                                      ''))
        # Make sure to restart MOM
        # HUP is not enough to get rid of earlier
        # per socket vnodes created when vnode_per_numa_node=True
        self.mom.restart()

        # Submit M jobs N cpus wide, where M is the amount of physical
        # processors and N is number of 'cpu cores' per M. Expect them to run.
        njobs = phys
        if njobs > 64:
            self.skipTest("too many jobs (%d) to submit" % njobs)
        a = {'Resource_List.select': '1:ncpus=%s:mem=300mb:host=%s' %
             (cores, self.hosts_list[0]), ATTR_N: name + 'a'}
        for _ in range(njobs):
            j = Job(TEST_USER, attrs=a)
            # make sure this stays around for an hour
            # (or until deleted in teardown)
            j.set_sleep_time(3600)
            jid = self.server.submit(j)
            a1 = {'job_state': 'R'}
            # give the scheduler, server and MoM some time
            # it's not a luxury on containers with few CPU resources
            time.sleep(2)
            self.server.expect(JOB, a1, jid)
        # Submit another job, expect in Q state -- this one with only 1 CPU
        b = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name + 'b'}
        j2 = Job(TEST_USER, attrs=b)
        jid2 = self.server.submit(j2)
        b1 = {'job_state': 'Q'}
        # Make sure to give the scheduler ample time here:
        # we want to make sure jid2 doesn't run because it can't,
        # not because the scheduler has not yet gotten to it
        time.sleep(30)
        self.server.expect(JOB, b1, jid2)

    def test_cgroup_enforce_memory(self):
        """
        Test to verify that the job is killed when it tries to
        use more memory then it requested
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        name = 'CGROUP5'
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.eatmem_job1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        # mem and vmem limit will both be set, and either could be detected
        self.mom.log_match('%s;Cgroup mem(ory|sw) limit exceeded' % jid,
                           regexp=True)

    def test_cgroup_enforce_memsw(self):
        """
        Test to verify that the job is killed when it tries to
        use more vmem then it requested
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        # run the test if swap space is available
        if have_swap() == 0:
            self.skipTest('no swap space available on the local host')
        # Get the grandparent directory
        fn = self.paths['memory']
        fn = os.path.join(fn, 'memory.memsw.limit_in_bytes')
        if not self.is_file(fn, self.hosts_list[0]):
            self.skipTest('vmem resource not present on node')
        name = 'CGROUP6'
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        # Make sure output file is gone, otherwise wait and read
        # may pick up stale copy of earlier test
        self.du.rm(runas=TEST_USER, path='~/' + name + '.*', as_script=True)
        a = {
            'Resource_List.select':
            '1:ncpus=1:mem=300mb:vmem=320mb:host=%s' % self.hosts_list[0],
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

    def cgroup_offline_node(self, name, vnpernuma):
        """
        Per vnode_per_numa_node config setting, return True if able to
        verify that the node is offlined when it can't clean up the cgroup
        and brought back online once the cgroup is cleaned up.
        """
        if 'freezer' not in self.paths:
            self.skipTest('Freezer cgroup is not mounted')
        # Get the grandparent directory
        fdir = self.paths['freezer']
        if not self.is_dir(fdir, self.hosts_list[0]):
            self.skipTest('Freezer cgroup is not found')
        # Configure the hook
        self.load_config(self.cfg3 % ('', vnpernuma, '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], 'Resource_List.walltime': 3, ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        filename = j.attributes[ATTR_o]
        tmp_file = filename.split(':')[1]
        self.tempfile.append(tmp_file)
        # Query the pids in the cgroup
        jdir = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        tasks_file = os.path.join(jdir, 'tasks')
        time.sleep(2)
        ret = self.du.cat(self.hosts_list[0], tasks_file, sudo=True)
        tasks = ret['out']
        if len(tasks) < 2:
            self.skipTest('pbs_cgroups_hook: only one task in cgroup')
        self.logger.info('Tasks: %s' % tasks)
        self.assertTrue(tasks, 'No tasks in cpuset cgroup for job')
        # Make dir in freezer subsystem
        fdir_pbs = os.path.join(fdir, 'PtlPbs')
        if not self.du.isdir(fdir_pbs):
            self.du.mkdir(hostname=self.hosts_list[0], path=fdir_pbs,
                          mode=0o755, sudo=True)
        # Write a PID into the tasks file for the freezer cgroup
        task_file = os.path.join(fdir_pbs, 'tasks')
        success = False
        for pid in reversed(tasks[1:]):
            fn = self.du.create_temp_file(
                hostname=self.hosts_list[0], body=pid)
            self.tempfile.append(fn)
            ret = self.du.run_copy(hosts=self.hosts_list[0], src=fn,
                                   dest=task_file, sudo=True,
                                   uid='root', gid='root',
                                   mode=0o644)
            if ret['rc'] == 0:
                success = True
                break
            self.logger.info('Failed to copy %s to %s on %s' %
                             (fn, task_file, self.hosts_list[0]))
            self.logger.info('rc = %d', ret['rc'])
            self.logger.info('stdout = %s', ret['out'])
            self.logger.info('stderr = %s', ret['err'])
        if not success:
            self.skipTest('pbs_cgroups_hook: Failed to copy freezer tasks')
        # Freeze the cgroup
        freezer_file = os.path.join(fdir_pbs, 'freezer.state')
        state = 'FROZEN'
        fn = self.du.create_temp_file(hostname=self.hosts_list[0], body=state)
        self.tempfile.append(fn)
        ret = self.du.run_copy(self.hosts_list[0], src=fn,
                               dest=freezer_file, sudo=True,
                               uid='root', gid='root',
                               mode=0o644)
        if ret['rc'] != 0:
            self.skipTest('pbs_cgroups_hook: Failed to copy '
                          'freezer state FROZEN')
        # Catch any exception so we can thaw the cgroup or the jobs
        # will remain frozen and impact subsequent tests
        passed = True
        try:
            self.server.expect(NODE, {'state': (MATCH_RE, 'offline')},
                               id=self.nodes_list[0], offset=10, interval=3)
        except Exception as exc:
            passed = False
            self.logger.info('Node never went offline')
        # Thaw the cgroup
        state = 'THAWED'
        fn = self.du.create_temp_file(hostname=self.hosts_list[0], body=state)
        self.tempfile.append(fn)
        ret = self.du.run_copy(self.hosts_list[0], src=fn,
                               dest=freezer_file, sudo=True,
                               uid='root', gid='root',
                               mode=0o644)
        if ret['rc'] != 0:
            self.skipTest('pbs_cgroups_hook: Failed to copy '
                          'freezer state THAWED')
        time.sleep(3)
        cmd = ["rmdir", fdir_pbs]
        self.logger.info("Removing %s" % fdir_pbs)
        self.du.run_cmd(cmd=cmd, sudo=True)
        # Due to orphaned jobs node is not coming back to free state
        # workaround is to recreate the nodes. Orphaned jobs will
        # get cleaned up in tearDown hence not doing it here
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")
        for host in self.hosts_list:
            self.server.manager(MGR_CMD_CREATE, NODE, id=host)
            self.server.expect(NODE, {'state': 'free'},
                               id=host, interval=3)
        return passed

    def test_cgroup_offline_node(self):
        """
        Test to verify that the node is offlined when it can't clean up
        the cgroup and brought back online once the cgroup is cleaned up.
        vnode_per_numa_node = false
        """
        name = 'CGROUP7.1'
        vn_per_numa = 'false'
        rv = self.cgroup_offline_node(name, vn_per_numa)
        self.assertTrue(rv)

    def test_cgroup_offline_node_vnpernuma(self):
        """
        Test to verify that the node is offlined when it can't clean up
        the cgroup and brought back online once the cgroup is cleaned up.
        vnode_per_numa_node = true
        """
        with open(os.path.join(os.sep, 'proc', 'meminfo'), 'r') as fd:
            meminfo = fd.read()
        if 'Hugepagesize' not in meminfo:
            self.skipTest('Hugepagesize not in meminfo')
        name = 'CGROUP7.2'
        vn_per_numa = 'true'
        rv = self.cgroup_offline_node(name, vn_per_numa)
        self.assertTrue(rv)

    @requirements(num_moms=2)
    def test_cgroup_cpuset_host_excluded(self):
        """
        Test to verify that cgroups subsystems are not enforced on nodes
        that have the exclude_hosts set but are enforced on other systems
        """
        name = 'CGROUP10'
        mom, _ = self.get_host_names(self.hosts_list[0])
        self.load_config(self.cfg1 % ('', '', '', '%s' % mom,
                                      self.mem, self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        hostn = self.get_hostname(self.hosts_list[0])
        self.moms_list[0].log_match('cgroup excluded for subsystem cpuset '
                                    'on host %s' % hostn,
                                    starttime=self.server.ctime)
        cpath = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[0]))
        # Now try a job on momB
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[1], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        cpath = self.get_cgroup_job_dir('cpuset', jid2, self.hosts_list[1])
        self.logger.info('Checking for %s on %s' % (cpath, self.moms_list[1]))
        self.assertTrue(self.is_dir(cpath, self.hosts_list[1]))

    @requirements(num_moms=2)
    def test_cgroup_run_on_host(self):
        """
        Test to verify that the cgroup hook only runs on nodes
        in the run_only_on_hosts
        """
        name = 'CGROUP11'
        mom, log = self.get_host_names(self.hosts_list[0])
        self.load_config(self.cfg1 % ('', '', '%s' % mom, '',
                                      self.mem, self.swapctl))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[1], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        time.sleep(1)
        hostn = self.get_hostname(self.hosts_list[1])
        self.moms_list[1].log_match(
            'set enabled to False based on run_only_on_hosts',
            starttime=self.server.ctime)
        cpath = self.get_cgroup_job_dir('memory', jid, self.hosts_list[1])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[1]))
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid2 = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid2)
        self.server.status(JOB, ATTR_o, jid2)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        cpath = self.get_cgroup_job_dir('memory', jid2, self.hosts_list[0])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[0]))

    def test_cgroup_qstat_resources(self):
        """
        Test to verify that cgroups are reporting usage for
        mem, and vmem in qstat
        """
        name = 'CGROUP14'
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
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
        self.logger.info('Waiting 35 seconds for CPU time to accumulate')
        time.sleep(35)
        qstat2 = self.server.status(JOB, resc_list, id=jid)
        for q in qstat2:
            self.logger.info('Q2: %s' % q)
        cput2 = qstat2[0]['resources_used.cput']
        mem2 = qstat2[0]['resources_used.mem']
        vmem2 = qstat2[0]['resources_used.vmem']
        self.assertNotEqual(cput1, cput2)
        self.assertNotEqual(mem1, mem2)
        # Check vmem only if system has swap control
        if self.swapctl == 'true':
            self.assertNotEqual(vmem1, vmem2)

    def test_cgroup_reserve_mem(self):
        """
        Test to verify that the mom reserve memory for OS
        when there is a reserve mem request in the config.
        Install cfg3 and then cfg4 and measure difference
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
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=3, offset=10)
        if self.swapctl == 'true':
            vmem = self.server.status(NODE, 'resources_available.vmem',
                                      id=self.nodes_list[0])
            self.logger.info('vmem: %s' % str(vmem))
            vmem1 = PbsTypeSize(vmem[0]['resources_available.vmem'])
            self.logger.info('Vmem-1: %s' % vmem1.value)
        mem = self.server.status(NODE, 'resources_available.mem',
                                 id=self.nodes_list[0])
        mem1 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info('Mem-1: %s' % mem1.value)
        self.load_config(self.cfg4 % (self.mem, self.swapctl))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=3, offset=10)
        if self.swapctl == 'true':
            vmem = self.server.status(NODE, 'resources_available.vmem',
                                      id=self.nodes_list[0])
            vmem2 = PbsTypeSize(vmem[0]['resources_available.vmem'])
            self.logger.info('Vmem-2: %s' % vmem2.value)
            vmem_resv = vmem1 - vmem2
            if (vmem_resv.unit == 'b'):
                vmem_resv_bytes = vmem_resv.value
            elif (vmem_resv.unit == 'kb'):
                vmem_resv_bytes = vmem_resv.value * 1024
            elif (vmem_resv.unit == 'mb'):
                vmem_resv_bytes = vmem_resv.value * 1024 * 1024
            self.logger.info('Vmem resv diff in bytes: %s' % vmem_resv_bytes)
            # rounding differences may make diff slighly smaller than we expect
            # accept 1MB deviation as irrelevant
            # Note: since we don't know if there is swap, memsw reserved
            # increase might not have been heeded. Change this to a higher
            # value (cfr. above) only on test harnesses that have enough swap
            self.assertGreaterEqual(vmem_resv_bytes, (51200 - 1024) * 1024)
        mem = self.server.status(NODE, 'resources_available.mem',
                                 id=self.nodes_list[0])
        mem2 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info('Mem-2: %s' % mem2.value)
        mem_resv = mem1 - mem2
        if (mem_resv.unit == 'b'):
            mem_resv_bytes = mem_resv.value
        elif (mem_resv.unit == 'kb'):
            mem_resv_bytes = mem_resv.value * 1024
        elif (mem_resv.unit == 'mb'):
            mem_resv_bytes = mem_resv.value * 1024 * 1024
        self.logger.info('Mem resv diff in bytes: %s' % mem_resv_bytes)
        # rounding differences may make diff slighly smaller than we expect
        # accept 1MB deviation as irrelevant
        self.assertGreaterEqual(mem_resv_bytes, (51200 - 1024) * 1024)

    @requirements(num_moms=2)
    def test_cgroup_multi_node(self):
        """
        Test multi-node jobs with cgroups
        """
        name = 'CGROUP16'
        self.load_config(self.cfg6 % (self.mem, self.swapctl))
        a = {'Resource_List.select': '2:ncpus=1:mem=100mb',
             'Resource_List.place': 'scatter', ATTR_N: name}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep30_job)
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
        self.assertTrue(self.is_dir(ehjd2, ehost2),
                        'Missing memory subdirectory: %s' % ehjd2)
        # Wait for job to finish and make sure that cgroup directories
        # has been cleaned up by the hook
        self.server.expect(JOB, 'queue', op=UNSET, offset=30, interval=1,
                           id=jid)
        self.assertFalse(self.is_dir(ehjd1, ehost1),
                         'Directory still present: %s' % ehjd1)
        self.assertFalse(self.is_dir(ehjd2, ehost2),
                         'Directory still present: %s' % ehjd2)

    def test_cgroup_job_array(self):
        """
        Test that cgroups are created for subjobs like a regular job
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        name = 'CGROUP17'
        self.load_config(self.cfg1 % ('', '', '', '', self.mem, self.swapctl))
        # Restart mom for cgroups hook changes to take effect
        self.mom.restart()
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name, ATTR_J: '1-4',
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
        self.assertFalse(self.is_dir(cpath, self.hosts_list[0]))
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
        # since qdel -Wforce changed state of subjob
        # without waiting for MoM
        # retry 10 times (for 20 seconds max. in total)
        # if the directory is still there...
        cpath = self.get_cgroup_job_dir('memory', subj2, ehost1)
        for trial in range(0, 10):
            time.sleep(2)
            if not self.is_dir(cpath, ehost1):
                # we're done
                break
        self.assertFalse(self.is_dir(cpath, ehost1))

    @requirements(num_moms=2)
    def test_cgroup_cleanup(self):
        """
        Test that cgroups files are cleaned up after qdel
        """
        self.load_config(self.cfg1 % ('', '', '', '', self.mem, self.swapctl))
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
        self.load_config(self.cfg4 % (self.mem, self.swapctl))
        # remove epilogue and periodic from the list of events
        attr = {'enabled': 'True',
                'event': ['execjob_begin', 'execjob_launch',
                          'execjob_attach', 'execjob_end', 'exechost_startup']}
        self.server.manager(MGR_CMD_SET, HOOK, attr, self.hook_name)
        self.server.expect(NODE, {'state': 'free'}, id=self.nodes_list[0])
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid = self.server.submit(j)
        # wait for job to finish
        self.server.expect(JOB, 'queue', id=jid, op=UNSET,
                           interval=1, offset=1)
        # verify that cgroup files for this job are gone even if
        # epilogue and periodic events are disabled
        for subsys, path in self.paths.items():
            # only check under subsystems that are enabled
            enabled_subsys = ['cpuacct', 'cpuset', 'memory', 'memsw']
            if (any([x in subsys for x in enabled_subsys])):
                continue
            if path:
                # Following code only works with recent hooks
                # and default cgroup_prefix
                # change the path if testing with older hooks
                # see comments in get_cgroup_job_dir()
                filename = os.path.join(path,
                                        'pbs_jobs.service',
                                        'jobid', str(jid))
                self.logger.info('Checking that file %s should not exist'
                                 % filename)
                self.assertFalse(os.path.isfile(filename))

    @skipOnCray
    def test_cgroup_assign_resources_mem_only_vnode(self):
        """
        Test to verify that job requesting mem larger than any single vnode
        works properly
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')

        vn_attrs = {ATTR_rescavail + '.ncpus': 1,
                    ATTR_rescavail + '.mem': '500mb'}
        self.load_config(self.cfg4 % (self.mem, self.swapctl))
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=self.nodes_list[0])
        self.moms.values()[0].create_vnodes(vn_attrs, 2)
        self.server.expect(NODE, {ATTR_NODE_state: 'free'},
                           id=self.nodes_list[0])
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script('date')
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, 'queue', id=jid1, op=UNSET,
                           interval=1, offset=1)
        a = {'Resource_List.select': '1:ncpus=1:mem=1000mb'}
        j2 = Job(TEST_USER, attrs=a)
        j2.create_script('date')
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, 'queue', id=jid2, op=UNSET,
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
                           interval=1)

    @timeout(1800)
    def test_cgroup_cpuset_exclude_cpu(self):
        """
        Confirm that exclude_cpus reduces resources_available.ncpus
        """
        # Fetch the unmodified value of resources_available.ncpus
        self.load_config(self.cfg5 % ('false', '', 'false', 'false',
                                      'false', self.mem, self.swapctl))
        # Restart mom for cgroups hook changes to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=1)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=self.nodes_list[0])
        orig_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(orig_ncpus, 0)
        self.logger.info('Original value of ncpus: %d' % orig_ncpus)
        if orig_ncpus < 2:
            self.skipTest('Node must have at least two CPUs')
        # Now exclude CPU zero
        self.load_config(self.cfg5 % ('false', '0', 'false', 'false',
                                      'false', self.mem, self.swapctl))
        # Restart mom for cgroups hook changes to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=1)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=self.nodes_list[0])
        new_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(new_ncpus, 0)
        self.logger.info('New value with one CPU excluded: %d' % new_ncpus)
        self.assertEqual((new_ncpus + 1), orig_ncpus)
        # Repeat the process with vnode_per_numa_node set to true
        vnode = '%s[0]' % self.nodes_list[0]
        self.load_config(self.cfg5 % ('true', '', 'false', 'false',
                                      'false', self.mem, self.swapctl))
        # Restart mom for cgroups hook changes to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=vnode, interval=1)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=vnode)
        orig_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(orig_ncpus, 0)
        self.logger.info('Original value of vnode ncpus: %d' % orig_ncpus)
        # Exclude CPU zero again
        self.load_config(self.cfg5 % ('true', '0', 'false', 'false',
                                      'false', self.mem, self.swapctl))
        # Restart mom for cgroups hook changes to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=vnode, interval=1)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=vnode)
        new_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertEqual((new_ncpus + 1), orig_ncpus)

    def test_cgroup_cpuset_mem_fences(self):
        """
        Confirm that mem_fences affects setting of cpuset.mems
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        # Get the grandparent directory
        cpuset_base = self.paths['cpuset']
        cpuset_mems = os.path.join(cpuset_base, 'cpuset.mems')
        result = self.du.cat(hostname=self.hosts_list[0], filename=cpuset_mems,
                             sudo=True)
        if result['rc'] != 0 or result['out'][0] == '0':
            self.skipTest('Test requires two NUMA nodes')
        # First try with mem_fences set to true (the default)
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'false', self.mem, self.swapctl))
        # Restart mom for cgroups hook changes to take effect
        self.mom.restart()
        # Do not use node_list -- vnode_per_numa_node is NOW off
        # so use the natural node. Otherwise might 'expect' stale vnode
        self.server.expect(NODE, {'state': 'free'},
                           id=self.hosts_list[0], interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hosts_list[0]}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        fn = os.path.join(fn, 'cpuset.mems')
        result = self.du.cat(hostname=self.hosts_list[0],
                             filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        value_mem_fences = result['out'][0]
        self.logger.info("value with mem_fences: %s" % value_mem_fences)
        # Now try with mem_fences set to false
        self.load_config(self.cfg5 % ('false', '', 'false', 'false',
                                      'false', self.mem, self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hosts_list[0]}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        fn = os.path.join(fn, 'cpuset.mems')
        result = self.du.cat(hostname=self.hosts_list[0],
                             filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        # compare mem value under mem_fences and under no mem_fences
        value_no_mem_fences = result['out'][0]
        self.logger.info("value with no mem_fences:%s" % value_no_mem_fences)
        self.assertNotEqual(value_no_mem_fences, value_mem_fences)

    def test_cgroup_cpuset_mem_hardwall(self):
        """
        Confirm that mem_hardwall affects setting of cpuset.mem_hardwall
        """
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'false', self.mem, self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hosts_list[0]}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        memh_path = 'cpuset.mem_hardwall'
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        if self.noprefix:
            memh_path = 'mem_hardwall'
        fn = os.path.join(fn, memh_path)
        self.logger.info('fn is %s' % fn)
        if not (self.is_file(fn, self.hosts_list[0])):
            self.skipTest('cgroup mem_hardwall of job does not exist')
        result = self.du.cat(hostname=self.hosts_list[0],
                             filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '0')
        self.load_config(self.cfg5 % ('false', '', 'true', 'true',
                                      'false', self.mem, self.swapctl))
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hosts_list[0]}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, self.hosts_list[0])
        fn = os.path.join(fn, memh_path)
        if not (self.is_file(fn, self.hosts_list[0])):
            self.skipTest('cgroup mem_hardwall of job does not exist')
        result = self.du.cat(hostname=self.hosts_list[0],
                             filename=fn, sudo=True)
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
        self.server.expect(NODE, {'state': 'free'}, id=self.nodes_list[0])
        ngpus = self.server.status(NODE, 'resources_available.ngpus',
                                   id=self.nodes_list[0])[0]
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
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'false', self.mem, self.swapctl))
        nid = self.nodes_list[0]
        self.server.expect(NODE, {'state': 'free'}, id=nid,
                           interval=3, offset=10)
        hostn = self.hosts_list[0]
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' % hostn}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        spread_path = 'cpuset.memory_spread_page'
        fn = self.get_cgroup_job_dir('cpuset', jid, hostn)
        if self.noprefix:
            spread_path = 'memory_spread_page'
        fn = os.path.join(fn, spread_path)
        self.assertTrue(self.is_file(fn, hostn))
        result = self.du.cat(hostname=hostn, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '0')
        self.load_config(self.cfg5 % ('false', '', 'true', 'false',
                                      'true', self.mem, self.swapctl))
        self.server.expect(NODE, {'state': 'free'}, id=nid,
                           interval=3, offset=10)
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' % hostn}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, ATTR_o, jid)
        o = j.attributes[ATTR_o]
        self.tempfile.append(o)
        fn = self.get_cgroup_job_dir('cpuset', jid, hostn)
        fn = os.path.join(fn, spread_path)
        result = self.du.cat(hostname=hostn, filename=fn, sudo=True)
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['out'][0], '1')

    def test_cgroup_use_hierarchy(self):
        """
        Test that memory.use_hierarchy is enabled by default
        when PBS cgroups hook is instantiated
        """
        now = time.time()
        # Remove PBS directories from memory subsystem
        cpath = None
        if 'memory' in self.paths and self.paths['memory']:
            cdir = self.paths['memory']
            cpath = self.find_main_cpath(cdir)
        else:
            self.skipTest(
                "memory subsystem is not enabled for cgroups")
        if cpath is not None:
            cmd = ["rmdir", cpath]
        self.logger.info("Removing %s" % cpath)
        self.du.run_cmd(cmd=cmd, sudo=True)
        self.load_config(self.cfg6 % (self.mem, self.swapctl))
        self.moms_list[0].restart()
        # Wait for exechost_startup hook to run
        self.moms_list[0].log_match("Hook handler returned success for"
                                    " exechost_startup event",
                                    starttime=now)
        # check where cpath is once more
        # since we loaded a new cgroup config file
        cpath = None
        if 'memory' in self.paths and self.paths['memory']:
            cdir = self.paths['memory']
            cpath = self.find_main_cpath(cdir)
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
        self.load_config(self.cfg3 % ('', 'false', '', self.mem, '',
                                      self.swapctl, ''))
        # Submit a short job and let it run to completion
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hosts_list[0]}
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
        self.moms_list[0].log_match(err_msg, max_attempts=3,
                                    interval=1, n=100,
                                    existence=False)
        self.server.log_match(jid1 + ';Exit_status=0')
        # Create a periodic hook that runs more frequently than the
        # cgroup hook to prepend jid1 to mom_priv/hooks/hook_data/cgroup_jobs
        hookname = 'prependjob'
        hookbody = """
import pbs
import os
import re
import time
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
        jobdict = eval(desc.read())
        if jid_to_prepend not in jobdict:
            jobdict[jid_to_prepend] = time.time()
            desc.seek(0)
            desc.write(str(jobdict))
            desc.truncate()
except Exception as exc:
    pbs.logmsg(pbs.EVENT_DEBUG, 'Failed to modify ' + jobsfile)
    pbs.logmsg(pbs.EVENT_DEBUG,
               str(traceback.format_exc().strip().splitlines()))
    event.reject()
event.accept()
""" % jid1
        events = ['execjob_begin', 'exechost_periodic']
        hookconf = {'enabled': 'True', 'freq': 2, 'alarm': 30, 'event': events}
        self.server.create_import_hook(hookname, hookconf, hookbody,
                                       overwrite=True)
        # Submit a second job and verify that the following message
        # does NOT appear in the mom log:
        # _exechost_periodic_handler: Failed to update jid1
        presubmit = time.time()
        a = {'Resource_List.select': '1:ncpus=1:mem=100mb:host=%s' %
             self.hosts_list[0]}
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
        self.moms_list[0].log_match(err_msg, max_attempts=3,
                                    interval=1, n=100,
                                    existence=False)
        self.server.log_match(jid2 + ';Exit_status=0')
        self.server.manager(MGR_CMD_DELETE, HOOK, None, hookname)
        command = ['rm', '-rf',
                   os.path.join(self.moms_list[0].pbs_conf['PBS_HOME'],
                                'mom_priv', 'hooks', 'hook_data',
                                'cgroup_jobs')]
        self.du.run_cmd(cmd=command, hosts=self.hosts_list[0], sudo=True)
        logmsg = '_exechost_periodic_handler: Failed to update %s' % jid1
        self.moms_list[0].log_match(msg=logmsg, starttime=presubmit,
                                    max_attempts=1, existence=False)

    @requirements(num_moms=3)
    def test_cgroup_release_nodes(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        tolerate_node_failures=job_start
        """
        self.load_config(self.cfg7 % (self.mem, self.mem))
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
        j.create_script(self.job_scr2 % (self.hosts_list[1]))
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
                 {ATTR_l + '.select': '1:ncpus=1:mem=100mb:vnode=%s' % vnodeB})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

    @requirements(num_moms=3)
    def test_cgroup_sismom_resize_fail(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        exec_job_resize failure in sister mom,
        tolerate_node_failures=job_start
        """
        self.load_config(self.cfg7 % (self.mem, self.mem))
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
        # Note mother superior is mom[1] not mom[0]
        j.create_script(self.job_scr2 % (self.hosts_list[1]))
        stime = time.time()
        jid = self.server.submit(j)
        # Check the exec_vnode while in substate 41
        self.server.expect(JOB, {ATTR_substate: '41'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode1 = job_stat[0]['exec_vnode']
        self.logger.info("initial exec_vnode: %s" % execvnode1)
        initial_vnodes = execvnode1.split('+')
        # Check the exec_resize hook reject message in sister mom logs
        self.moms_list[0].log_match(
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
        self.moms_list[1].log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.moms_list[1].log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, execvnode2), starttime=stime)
        # Check that MS saw that the sister mom failed to update the job
        # This message is on MS mom[1] but mentions sismom mom[0]
        self.moms_list[1].log_match(
            "Job;%s;sister node %s.* failed to update job"
            % (jid, self.hosts_list[0]),
            starttime=stime, interval=2, regexp=True)
        # Because of resize hook reject Mom failed to update the job.
        # Check that job got requeued.
        self.server.log_match("Job;%s;Job requeued" % (jid), starttime=stime)

    @requirements(num_moms=3)
    def test_cgroup_msmom_resize_fail(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        exec_job_resize failure in mom superior,
        tolerate_node_failures=job_start
        """
        self.load_config(self.cfg7 % (self.mem, self.mem))
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
        j.create_script(self.job_scr2 % (self.hosts_list[1]))
        stime = time.time()
        jid = self.server.submit(j)
        # Check the exec_vnode while in substate 41
        self.server.expect(JOB, {ATTR_substate: '41'}, id=jid)
        self.server.expect(JOB, 'exec_vnode', id=jid, op=SET)
        job_stat = self.server.status(JOB, id=jid)
        execvnode1 = job_stat[0]['exec_vnode']
        self.logger.info("initial exec_vnode: %s" % execvnode1)
        initial_vnodes = execvnode1.split('+')
        # Check the exec_resize hook reject message in MS log
        self.moms_list[1].log_match(
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
        self.moms_list[1].log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.moms_list[1].log_match("Job;%s;pruned to exec_vnode=%s" % (
            jid, execvnode2), starttime=stime)
        # Because of resize hook reject Mom failed to update the job.
        # Check that job got requeued
        self.server.log_match("Job;%s;Job requeued" % (jid), starttime=stime)

    @requirements(num_moms=3)
    def test_cgroup_msmom_nodes_only(self):
        """
        Verify that exec_vnode values are trimmed
        when execjob_launch hook prunes job via release_nodes(),
        job is using only vnodes from mother superior host,
        tolerate_node_failures=job_start
        """
        self.load_config(self.cfg7 % (self.mem, self.mem))
        # disable queuejob hook
        hook_event = 'queuejob'
        hook_name = 'qjob'
        a = {'event': hook_event, 'enabled': 'false'}
        self.server.create_import_hook(hook_name, a, self.qjob_hook_body)
        # instantiate execjob_launch hook
        hook_event = 'execjob_launch'
        hook_name = 'launch'
        a = {'event': hook_event, 'enabled': 'true'}
        self.keep_select = '"ncpus=1:mem=100mb"'
        self.server.create_import_hook(
            hook_name, a, self.launch_hook_body % (self.keep_select))
        # disable execjob_resize hook
        hook_event = 'execjob_resize'
        hook_name = 'resize'
        a = {'event': hook_event, 'enabled': 'false'}
        self.server.create_import_hook(
            hook_name, a, self.resize_hook_body % (''))
        # Submit a job that requires two vnodes
        j = Job(TEST_USER)
        j.create_script(self.job_scr3)
        stime = time.time()
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
        self.moms_list[0].log_match("Job;%s;pruned from exec_vnode=%s" % (
            jid, execvnode1), starttime=stime)
        self.moms_list[0].log_match("Job;%s;pruned to exec_vnode=%s" % (
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
            ATTR_l + '.select': '1:ncpus=1:mem=100mb:vnode=%s' % vnodeB})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid2)

    @requirements(num_moms=3)
    def test_cgroups_abort(self):
        """
        Verify that if one of the sister mom is down then
        cgroups hook will call the abort event which will
        cleanup the cgroups files on sister moms and primary
        mom
        """
        self.logger.info("Stopping mom on host %s" % self.hosts_list[1])
        self.moms_list[1].signal('-19')

        a = {'Resource_List.select':
             '1:ncpus=1:host=%s+1:ncpus=1:host=%s+1:ncpus=1:host=%s' %
             (self.hosts_list[0], self.hosts_list[1], self.hosts_list[2])}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R', 'substate': '41'}
        self.server.expect(JOB, a, jid)

        self.logger.info("Killing mom on host %s" % self.hosts_list[1])
        now = time.time()
        self.moms_list[1].signal('-9')

        self.server.expect(NODE, {'state': "down"}, id=self.hosts_list[1])
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        # Verify that cgroups directories are cleaned on primary mom
        cpath = self.get_cgroup_job_dir('memory', jid, self.hosts_list[0])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[0]))

        # Verify that cgroups directories are cleaned by execjob_abort
        # hook on sister mom
        cpath = self.get_cgroup_job_dir('memory', jid, self.hosts_list[2])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[2]))

        self.moms_list[0].log_match("job_start_error", starttime=now)
        self.moms_list[0].log_match("Event type is execjob_abort",
                                    starttime=now)
        self.moms_list[0].log_match("Event type is execjob_epilogue",
                                    starttime=now)
        self.moms_list[0].log_match("Event type is execjob_end",
                                    starttime=now)
        self.moms_list[2].log_match("Event type is execjob_abort",
                                    starttime=now)

        self.moms_list[1].restart()

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=15)

        a = {'Resource_List.select': '3:ncpus=1:mem=100mb',
             'Resource_List.place': 'scatter'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)

    @timeout(1800)
    def test_big_cgroup_cpuset(self):
        """
        With vnodes_per_numa and use_hyperthreads set to "true",
        test to verify that a job requesting at least 10 vnodes
        (i.e. 10 memory sockets) get a cgroup cpuset with the
        correct number of cpus and memory sockets.
        """
        name = 'CGROUP_BIG'
        self.load_config(self.cfg9 % (self.mem, self.mem))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()

        vnodes_count = 10
        try:
            self.server.expect(VNODE, {'state=free': vnodes_count},
                               op=GE, count=True, interval=2)
        except Exception as exc:
            self.skipTest("Test require >= %d free vnodes" % (vnodes_count,))

        rncpus = 'resources_available.ncpus'
        a = {rncpus: (GT, 0), 'state': 'free'}
        free_nodes = self.server.filter(VNODE, a, attrop=PTL_AND, idonly=False)
        vnodes = list(free_nodes.values())[0]
        self.assertGreaterEqual(len(vnodes), vnodes_count,
                                'Test does not have enough free vnodes')
        # find the minimum number of cpus found among the vnodes
        cpus_per_vnode = None
        for v in vnodes:
            v_rncpus = int(v[rncpus])
            if not cpus_per_vnode:
                cpus_per_vnode = v_rncpus
            if v_rncpus < cpus_per_vnode:
                cpus_per_vnode = v_rncpus

        # Submit a job
        select_spec = "%d:ncpus=%d" % (vnodes_count, cpus_per_vnode)
        a = {'Resource_List.select': select_spec, ATTR_N: name + 'a'}
        j1 = Job(TEST_USER, attrs=a)
        j1.create_script(self.sleep15_job)
        jid1 = self.server.submit(j1)
        a = {'job_state': 'R'}
        # Make sure job is running
        self.server.expect(JOB, a, jid1)
        # cpuset path for job
        fn1 = self.get_cgroup_job_dir('cpuset', jid1, self.hosts_list[0])
        # Capture the output of cpuset_mem_script for job
        scr1 = self.du.run_cmd(cmd=[self.cpuset_mem_script % (fn1, None)],
                               as_script=True)
        tmp_out1 = scr1['out']
        self.logger.info("test output for job1: %s" % (tmp_out1))
        # Ensure the number of cpus assigned matches request
        cpuids = None
        for kv in tmp_out1:
            if 'CpuIDs=' in kv:
                cpuids = kv.split("=")[1]
                break
        cpus_assn = count_items(cpuids)
        cpus_req = vnodes_count * cpus_per_vnode
        self.logger.info("CpuIDs assn=%d req=%d" % (cpus_assn, cpus_req))
        self.assertEqual(cpus_assn, cpus_req,
                         'CpuIDs assigned did not match requested')
        self.logger.info('CpuIDs check passed')

        # Ensure the number of sockets assigned matches request
        memsocket = None
        for kv in tmp_out1:
            if 'MemorySocket=' in kv:
                memsocket = kv.split("=")[1]
                break
        mem_assn = count_items(memsocket)
        self.logger.info("MemSocket assn=%d req=%d" % (mem_assn, vnodes_count))
        self.assertEqual(mem_assn, vnodes_count,
                         'MemSocket assigned not match requested')
        self.logger.info('MemSocket check passed')

    @requirements(num_moms=2)
    def test_checkpoint_abort_preemption(self):
        """
        Test to make sure that when scheduler preempts a multi-node job with
        checkpoint_abort, execjob_abort cgroups hook on secondary node
        gets called.  The abort hook cleans up assigned cgroups, allowing
        the higher priority job to run on the same node.
        """
        # Skip test if number of mom provided is not equal to two
        if len(self.moms) != 2:
            self.skipTest("test requires two MoMs as input, " +
                          "use -p moms=<mom1>:<mom2>")

        # create express queue
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "express")

        # have scheduler preempt lower priority jobs using 'checkpoint'
        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': 'C'})

        # have moms do checkpoint_abort
        chk_script = """#!/bin/bash
kill $1
exit 0
"""
        a = {'resources_available.ncpus': 1}
        for m in self.moms.values():
            chk_file = m.add_checkpoint_abort_script(body=chk_script)
            # ensure resulting checkpoint file has correct permission
            self.du.chown(hostname=m.shortname, path=chk_file, uid=0, gid=0,
                          sudo=True)
            self.server.manager(MGR_CMD_SET, NODE, a, id=m.shortname)

        # submit multi-node job
        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'scatter:exclhost'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        # to work around a scheduling race, check for substate 42
        # if you test for R then a slow job startup might update
        # resources_assigned late and make scheduler overcommit nodes
        # and run both jobs
        self.server.expect(JOB, {'substate': '42'}, id=jid1)

        # Submit an express queue job requesting needing also 2 nodes
        a[ATTR_q] = 'express'
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        err_msg = "%s;.*Failed to assign resources.*" % (jid2,)
        for m in self.moms.values():
            m.log_match(err_msg, max_attempts=3, interval=1, n=100,
                        regexp=True, existence=False)

        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, id=jid2)

    @requirements(num_moms=2)
    def test_checkpoint_restart(self):
        """
        Test to make sure that when a preempted and checkpointed multi-node
        job restarts, execjob_begin cgroups hook gets called on both mother
        superior and sister moms.
        """
        # create express queue
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "express")

        # have scheduler preempt lower priority jobs using 'checkpoint'
        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': 'C'})

        # have moms do checkpoint_abort
        chk_script = """#!/bin/bash
kill $1
exit 0
"""
        restart_script = """#!/bin/bash
sleep 300
"""
        a = {'resources_available.ncpus': 1}
        for m in self.moms.values():
            # add checkpoint script
            m.add_checkpoint_abort_script(body=chk_script)
            m.add_restart_script(body=restart_script, abort_time=300)
            self.server.manager(MGR_CMD_SET, NODE, a, id=m.shortname)

        # submit multi-node job
        a = {'Resource_List.select': '2:ncpus=1',
             'Resource_List.place': 'scatter:excl'}
        j1 = Job(TEST_USER, attrs=a)
        j1.set_sleep_time(300)
        jid1 = self.server.submit(j1)
        # to work around a scheduling race, check for substate 42
        # if you test for R then a slow job startup might update
        # resources_assigned late and make scheduler overcommit nodes
        # and run both jobs
        self.server.expect(JOB, {'substate': '42'}, id=jid1)
        time.sleep(5)
        cpath = self.get_cgroup_job_dir('cpuset', jid1, self.hosts_list[0])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[0]))
        cpath = self.get_cgroup_job_dir('cpuset', jid1, self.hosts_list[1])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[1]))

        # Submit an express queue job requesting needing also 2 nodes
        a[ATTR_q] = 'express'
        j2 = Job(TEST_USER, attrs=a)
        j2.set_sleep_time(300)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        self.server.expect(JOB, {'substate': '42'}, id=jid2)
        time.sleep(5)
        cpath = self.get_cgroup_job_dir('cpuset', jid2, self.hosts_list[0])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[0]))
        cpath = self.get_cgroup_job_dir('cpuset', jid2, self.hosts_list[1])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[1]))

        # delete express queue job
        self.server.delete(jid2)
        # wait until the preempted job is sent to MoM again
        # the checkpointing script hangs, so it stays in substate 41
        self.server.expect(JOB, {'job_state': 'R', 'substate': 41}, id=jid1)
        # we need to give the hooks some time here...
        time.sleep(10)
        # check the cpusets for the deleted preemptor are gone
        cpath = self.get_cgroup_job_dir('cpuset', jid2, self.hosts_list[0])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[0]))
        cpath = self.get_cgroup_job_dir('cpuset', jid2, self.hosts_list[1])
        self.assertFalse(self.is_dir(cpath, self.hosts_list[1]))
        # check the cpusets for the restarted formerly-preempted are there
        cpath = self.get_cgroup_job_dir('cpuset', jid1, self.hosts_list[0])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[0]))
        cpath = self.get_cgroup_job_dir('cpuset', jid1, self.hosts_list[1])
        self.assertTrue(self.is_dir(cpath, self.hosts_list[1]))

    def test_cpu_controller_enforce_default(self):
        """
        Test an enabled cgroup 'cpu' controller with quotas enforced
        using default (non-specified) values of cfs_period_us, and
        cfs_quota_fudge_factor.
        """
        root_quota_host1 = None
        try:
            root_quota_host1_str = \
                self.du.run_cmd(hosts=self.hosts_list[0],
                                cmd=['cat',
                                     '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'])
            root_quota_host1 = int(root_quota_host1_str['out'][0])
        except Exception:
            pass
        # If that link is missing and it's only
        # mounted under the cpu/cpuacct unified directory...
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/'
                                         'cpu,cpuacct/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass
        # If still not found, try to see if it is in a unified cgroup mount
        # as in cgroup v2
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass

        if root_quota_host1 is None:
            self.skipTest('cpu group controller test: '
                          'could not determine root cfs_quota_us')
        elif root_quota_host1 != -1:
            self.skipTest('cpu group controller test: '
                          'root cfs_quota_us is not unlimited, cannot test '
                          'cgroup hook CPU quotas in this environment')

        name = 'CGROUP1'
        self.load_config(self.cfg10 % (self.mem, self.mem))
        default_cfs_period_us = 100000
        default_cfs_quota_fudge_factor = 1.03

        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=1)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=self.nodes_list[0])
        orig_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(orig_ncpus, 0)
        self.logger.info('Original value of ncpus: %d' % orig_ncpus)
        if orig_ncpus >= 2:
            ncpus_req = 2
        else:
            ncpus_req = 1

        a = {'Resource_List.select':
             "ncpus=%d" % ncpus_req,
             ATTR_N: name, ATTR_k: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        fna = self.get_cgroup_job_dir('cpu', jid, self.hosts_list[0])
        self.assertFalse(fna is None, 'No job directory for cpu subsystem')
        cpu_scr = self.du.run_cmd(cmd=[self.cpu_controller_script % fna],
                                  as_script=True)
        cpu_scr_out = cpu_scr['out']
        self.logger.info('cpu_scr_out:\n%s' % cpu_scr_out)

        shares_match = (ncpus_req * 1000)
        self.assertTrue("cpu_shares=%d" % shares_match in cpu_scr_out)
        self.logger.info("cpu_shares check passed (match %d)" % shares_match)

        self.assertTrue("cpu_cfs_period_us=%d" %
                        (default_cfs_period_us) in cpu_scr_out)
        self.logger.info("cpu_cfs_period_us check passed (match %d)" %
                         (default_cfs_period_us))

        cfs_quota_us_match = default_cfs_period_us * \
            ncpus_req * default_cfs_quota_fudge_factor
        self.assertTrue("cpu_cfs_quota_us=%d" %
                        (cfs_quota_us_match) in cpu_scr_out)
        self.logger.info("cpu_cfs_quota_us check passed (match %d)" %
                         (cfs_quota_us_match))

    def test_cpu_controller_enforce(self):
        """
        Test an enabled cgroup 'cpu' controller with quotas enforced,
        using specific values to:
              cfs_period_us
              cfs_quota_fudge_factor
        in config file 'cfg11'.
        """
        root_quota_host1 = None
        try:
            root_quota_host1_str = \
                self.du.run_cmd(hosts=self.hosts_list[0],
                                cmd=['cat',
                                     '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'])
            root_quota_host1 = int(root_quota_host1_str['out'][0])
        except Exception:
            pass
        # If that link is missing and it's only
        # mounted under the cpu/cpuacct unified directory...
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/'
                                         'cpu,cpuacct/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass
        # If still not found, try to see if it is in a unified cgroup mount
        # as in cgroup v2
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass

        if root_quota_host1 is None:
            self.skipTest('cpu group controller test: '
                          'could not determine root cfs_quota_us')
        elif root_quota_host1 != -1:
            self.skipTest('cpu group controller test: '
                          'root cfs_quota_us is not unlimited, cannot test '
                          'cgroup hook CPU quotas in this environment')

        name = 'CGROUP1'
        cfs_period_us = 200000
        cfs_quota_fudge_factor = 1.05
        self.load_config(self.cfg11 % (self.mem, self.mem,
                                       cfs_period_us, cfs_quota_fudge_factor))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        self.server.expect(NODE, {'state': 'free'},
                           id=self.nodes_list[0], interval=1)
        result = self.server.status(NODE, 'resources_available.ncpus',
                                    id=self.nodes_list[0])
        orig_ncpus = int(result[0]['resources_available.ncpus'])
        self.assertGreater(orig_ncpus, 0)
        self.logger.info('Original value of ncpus: %d' % orig_ncpus)
        if orig_ncpus >= 2:
            ncpus_req = 2
        else:
            ncpus_req = 1
        a = {'Resource_List.select':
             "ncpus=%d" % ncpus_req,
             ATTR_N: name, ATTR_k: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        fna = self.get_cgroup_job_dir('cpu', jid, self.hosts_list[0])
        self.assertFalse(fna is None, 'No job directory for cpu subsystem')
        cpu_scr = self.du.run_cmd(cmd=[self.cpu_controller_script % fna],
                                  as_script=True)
        cpu_scr_out = cpu_scr['out']
        self.logger.info('cpu_scr_out:\n%s' % cpu_scr_out)
        shares_match = (ncpus_req * 1000)
        self.assertTrue("cpu_shares=%d" % shares_match in cpu_scr_out)
        self.logger.info("cpu_shares check passed (match %d)" % shares_match)

        self.assertTrue("cpu_cfs_period_us=%d" %
                        (cfs_period_us) in cpu_scr_out)
        self.logger.info(
            "cpu_cfs_period_us check passed (match %d)" % (cfs_period_us))
        cfs_quota_us_match = cfs_period_us * ncpus_req * cfs_quota_fudge_factor
        self.assertTrue("cpu_cfs_quota_us=%d" %
                        (cfs_quota_us_match) in cpu_scr_out)
        self.logger.info("cpu_cfs_quota_us check passed (match %d)" %
                         (cfs_quota_us_match))

    def test_cpu_controller_enforce_default_zero_job(self):
        """
        Test an enabled cgroup 'cpu' controller with quotas enforced
        on zero-cpu job, using default (non-specified) values of:
              cfs_period_us
              cfs_quota_fudge_factor
              zero_cpus_shares_fraction
              zero_cpus_quota_fraction
        """
        root_quota_host1 = None
        try:
            root_quota_host1_str = \
                self.du.run_cmd(hosts=self.hosts_list[0],
                                cmd=['cat',
                                     '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'])
            root_quota_host1 = int(root_quota_host1_str['out'][0])
        except Exception:
            pass
        # If that link is missing and it's only
        # mounted under the cpu/cpuacct unified directory...
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/'
                                         'cpu,cpuacct/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass
        # If still not found, try to see if it is in a unified cgroup mount
        # as in cgroup v2
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass

        if root_quota_host1 is None:
            self.skipTest('cpu group controller test: '
                          'could not determine root cfs_quota_us')
        elif root_quota_host1 != -1:
            self.skipTest('cpu group controller test: '
                          'root cfs_quota_us is not unlimited, cannot test '
                          'cgroup hook CPU quotas in this environment')

        name = 'CGROUP1'
        # config file 'cfg12' has 'allow_zero_cpus=true' under cpuset, to allow
        # zero-cpu jobs.
        self.load_config(self.cfg12 % (self.mem, self.mem))
        default_cfs_period_us = 100000
        default_cfs_quota_fudge_factor = 1.03
        default_zero_shares_fraction = 0.002
        default_zero_quota_fraction = 0.2
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        a = {'Resource_List.select': 'ncpus=0',
             ATTR_N: name, ATTR_k: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        fna = self.get_cgroup_job_dir('cpu', jid, self.hosts_list[0])
        self.assertFalse(fna is None, 'No job directory for cpu subsystem')
        cpu_scr = self.du.run_cmd(cmd=[self.cpu_controller_script % fna],
                                  as_script=True)
        cpu_scr_out = cpu_scr['out']
        self.logger.info('cpu_scr_out:\n%s' % cpu_scr_out)
        shares_match = (default_zero_shares_fraction * 1000)
        self.assertTrue("cpu_shares=%d" % shares_match in cpu_scr_out)
        self.logger.info("cpu_shares check passed (match %d)" % shares_match)

        self.assertTrue("cpu_cfs_period_us=%d" %
                        (default_cfs_period_us) in cpu_scr_out)
        self.logger.info("cpu_cfs_period_us check passed (match %d)" %
                         (default_cfs_period_us))
        cfs_quota_us_match = default_cfs_period_us * \
            default_zero_quota_fraction * default_cfs_quota_fudge_factor
        self.assertTrue("cpu_cfs_quota_us=%d" %
                        (cfs_quota_us_match) in cpu_scr_out)
        self.logger.info("cpu_cfs_quota_us check passed (match %d)" %
                         (cfs_quota_us_match))

    def test_cpu_controller_enforce_zero_job(self):
        """
        Test an enabled cgroup 'cpu' controller with quotas enforced on a
        zero-cpu job. Quotas are enforced using specific values to:
              cfs_period_us
              cfs_quota_fudge_factor
              zero_cpus_shares_fraction
              zero_cpus_quota_fraction
        in config file 'cfg13'.
        """
        root_quota_host1 = None
        try:
            root_quota_host1_str = \
                self.du.run_cmd(hosts=self.hosts_list[0],
                                cmd=['cat',
                                     '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'])
            root_quota_host1 = int(root_quota_host1_str['out'][0])
        except Exception:
            pass
        # If that link is missing and it's only
        # mounted under the cpu/cpuacct unified directory...
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/'
                                         'cpu,cpuacct/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass
        # If still not found, try to see if it is in a unified cgroup mount
        # as in cgroup v2
        if root_quota_host1 is None:
            try:
                root_quota_host1_str = \
                    self.du.run_cmd(hosts=self.hosts_list[0],
                                    cmd=['cat',
                                         '/sys/fs/cgroup/cpu.cfs_quota_us'])
                root_quota_host1 = int(root_quota_host1_str['out'][0])
            except Exception:
                pass

        if root_quota_host1 is None:
            self.skipTest('cpu group controller test: '
                          'could not determine root cfs_quota_us')
        elif root_quota_host1 != -1:
            self.skipTest('cpu group controller test: '
                          'root cfs_quota_us is not unlimited, cannot test '
                          'cgroup hook CPU quotas in this environment')
        name = 'CGROUP1'
        cfs_period_us = 200000
        cfs_quota_fudge_factor = 1.05
        zero_cpus_shares_fraction = 0.3
        zero_cpus_quota_fraction = 0.5
        # config file 'cfg13' has 'allow_zero_cpus=true' under cpuset, to allow
        # zero-cpu jobs.
        self.load_config(self.cfg13 % (self.mem, self.mem, cfs_period_us,
                                       cfs_quota_fudge_factor,
                                       zero_cpus_shares_fraction,
                                       zero_cpus_quota_fraction))
        # Restart mom for changes made by cgroups hook to take effect
        self.mom.restart()
        a = {'Resource_List.select': 'ncpus=0',
             ATTR_N: name, ATTR_k: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(JOB, [ATTR_o, 'exec_host'], jid)
        fna = self.get_cgroup_job_dir('cpu', jid, self.hosts_list[0])
        self.assertFalse(fna is None, 'No job directory for cpu subsystem')
        cpu_scr = self.du.run_cmd(cmd=[self.cpu_controller_script % fna],
                                  as_script=True)
        cpu_scr_out = cpu_scr['out']
        self.logger.info('cpu_scr_out:\n%s' % cpu_scr_out)
        shares_match = (zero_cpus_shares_fraction * 1000)
        self.assertTrue("cpu_shares=%d" % shares_match in cpu_scr_out)
        self.logger.info("cpu_shares check passed (match %d)" % shares_match)

        self.assertTrue("cpu_cfs_period_us=%d" %
                        (cfs_period_us) in cpu_scr_out)
        self.logger.info(
            "cpu_cfs_period_us check passed (match %d)" % (cfs_period_us))
        cfs_quota_us_match = cfs_period_us * \
            zero_cpus_quota_fraction * cfs_quota_fudge_factor
        self.assertTrue("cpu_cfs_quota_us=%d" %
                        (cfs_quota_us_match) in cpu_scr_out)
        self.logger.info("cpu_cfs_quota_us check passed (match %d)" %
                         (cfs_quota_us_match))

    def test_vnodepernuma_use_hyperthreads(self):
        """
        Test to verify that correct number of jobs run with
        vnodes_per_numa=true and use_hyperthreads=true
        """
        pcpus = 0
        sibs = 0
        cores = 0
        pval = 0
        phys = {}
        with open('/proc/cpuinfo', 'r') as desc:
            for line in desc:
                if re.match('^processor', line):
                    pcpus += 1
                sibs_match = re.search(r'siblings	: ([0-9]+)', line)
                cores_match = re.search(r'cpu cores	: ([0-9]+)', line)
                phys_match = re.search(r'physical id	: ([0-9]+)', line)
                if sibs_match:
                    sibs = int(sibs_match.groups()[0])
                if cores_match:
                    cores = int(cores_match.groups()[0])
                if phys_match:
                    pval = int(phys_match.groups()[0])
                    phys[pval] = 1
        if (sibs == 0 or cores == 0):
            self.skipTest('Insufficient information about the processors.')
        if pcpus < 2:
            self.skipTest('This test requires at least two processors.')

        hyperthreads_per_core = int(sibs / cores)
        name = 'CGROUP20'
        # set vnode_per_numa=true with use_hyperthreads=true
        self.load_config(self.cfg3 % ('', 'true', '', self.mem, '',
                                      self.swapctl, ''))
        # Restart mom so vnodes created by cgroups would show
        self.mom.restart()
        # Submit M*N*P jobs, where M is the number of physical processors,
        # N is the number of 'cpu cores' per M. and P being the
        # number of hyperthreads per core.
        njobs = len(phys) * cores * hyperthreads_per_core
        if njobs > 64:
            self.skipTest("too many jobs (%d) to submit" % njobs)
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name + 'a'}
        for _ in range(njobs):
            j = Job(TEST_USER, attrs=a)
            jid = self.server.submit(j)
            a1 = {'job_state': 'R'}
            self.server.expect(JOB, a1, jid)

        # Submit another job, expect in Q state
        b = {'Resource_List.select': '1:ncpus=1:mem=300mb:host=%s' %
             self.hosts_list[0], ATTR_N: name + 'b'}
        j2 = Job(TEST_USER, attrs=b)
        jid2 = self.server.submit(j2)
        b1 = {'job_state': 'Q'}
        self.server.expect(JOB, b1, jid2)

    def test_cgroup_default_config(self):
        """
        Test to make sure using the default hook config file
        still run a basic job, and cleans up cpuset upon qdel.
        """
        # The default hook config has 'memory' subsystem enabled
        if not self.paths['memory']:
            self.skipTest('Test requires memory subystem mounted')
        self.load_default_config()
        # Reduce the noise in mom_logs for existence=False matching
        c = {'$logevent': '511'}
        self.mom.add_config(c)
        a = {'Resource_List.select': 'ncpus=1:mem=100mb'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(self.sleep15_job)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        err_msg = "write_value: Permission denied.*%s.*memsw" % (jid)
        self.mom.log_match(err_msg, max_attempts=3, interval=1, n=100,
                           regexp=True, existence=False)
        self.server.status(JOB, ['exec_host'], jid)
        ehost = j.attributes['exec_host']
        ehost1 = ehost.split('/')[0]
        ehjd1 = self.get_cgroup_job_dir('cpuset', jid, ehost1)
        self.assertTrue(self.is_dir(ehjd1, ehost1), "job cpuset dir not found")
        self.server.delete(id=jid, wait=True)
        self.assertFalse(self.is_dir(ehjd1, ehost1), "job cpuset dir found")

    def tearDown(self):
        TestFunctional.tearDown(self)
        mom_checks = True
        if self.moms_list[0].is_cpuset_mom():
            mom_checks = False
        self.load_default_config(mom_checks=mom_checks)
        if not self.iscray:
            self.remove_vntype()
        events = ['execjob_begin', 'execjob_launch', 'execjob_attach',
                  'execjob_epilogue', 'execjob_end', 'exechost_startup',
                  'exechost_periodic', 'execjob_resize', 'execjob_abort']
        # Disable the cgroups hook
        conf = {'enabled': 'False', 'freq': 10, 'event': events}
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
                                hostname=self.hosts_list[0], body=state)
                            self.du.run_copy(hosts=self.hosts_list[0], src=fn,
                                             dest=freezer_file, sudo=True,
                                             uid='root', gid='root',
                                             mode=0o644)
                            self.du.rm(hostname=self.hosts_list[0], path=fn)
                            cmd = ['rmdir', jpath]
                            self.logger.info('deleting jobdir %s' % cmd)
                            self.du.run_cmd(cmd=cmd, sudo=True)
                        self.du.rm(hostname=self.hosts_list[0], path=fpath)
        # Remove the jobdir if any under other cgroups
        cgroup_subsys = ('systemd', 'cpu', 'cpuacct', 'cpuset', 'devices',
                         'memory', 'hugetlb', 'perf_event', 'freezer',
                         'blkio', 'pids', 'net_cls', 'net_prio')
        for subsys in cgroup_subsys:
            if subsys in self.paths and self.paths[subsys]:
                self.logger.info('Looking for orphaned jobdir in %s' % subsys)
                cdir = self.paths[subsys]
                if os.path.isdir(cdir):
                    cpath = self.find_main_cpath(cdir)
                    if cpath is not None and os.path.isdir(cpath):
                        for jdir in glob.glob(os.path.join(cpath, '*', '')):
                            if not os.path.isdir(jdir):
                                continue
                            self.logger.info('deleting jobdir %s' % jdir)
                            cmd2 = ['rmdir', jdir]
                            self.du.run_cmd(cmd=cmd2, sudo=True)

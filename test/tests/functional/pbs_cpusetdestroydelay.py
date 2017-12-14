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

import os
import time
from tests.functional import *


class TestCpusetDestroyDelay(TestFunctional):

    """
    Testing function kill_cpuset_procs() on SGI systems
    PP-345: cpuset_destroy_delay ignores child processes
    """

    def setUp(self):
        """
            Base class method overridding
            builds absolute path of commands to execute
        """
        self.server.expect(SERVER, {'pbs_version': (GE, '13.0')},
                           max_attempts=2)
        self.server.set_op_mode(PTL_CLI)
        self.server.cleanup_jobs(extend='force')
        if not self.mom.is_cpuset_mom():
            self.skipTest("Not running cpuset mom")
        self.resilient_job_script = """

# To adjust the process count set RESILIENT_JOB_PROCS
# To adjust the job duration set RESILIENT_JOB_DURATION

# Default is to maintain 10 active processes
RESILIENT_JOB_PROCS=${RESILIENT_JOB_PROCS:-10}
export RESILIENT_JOB_PROCS

# Default is to run for 10 seconds
RESILIENT_JOB_DURATION=${RESILIENT_JOB_DURATION:-10}
export RESILIENT_JOB_DURATION

# Calculate the end time only once at the beginning
RESILIENT_JOB_END=`date +%s`
let RESILIENT_JOB_END+=${RESILIENT_JOB_DURATION}
export RESILIENT_JOB_END

mount=`cat /proc/mounts | grep cpuset | cut -d' ' -f2`
myset=`cpuset -w $$`
RESILIENT_JOB_TASKS="$mount$myset/tasks"
[ -f "$RESILIENT_JOB_TASKS" ] || exit 1
export RESILIENT_JOB_TASKS

RESILIENT_JOB_SCRIPT=$(cat <<'EOF'
[ -z "$RESILIENT_JOB_PROCS" ] && exit 1
[ -z "$RESILIENT_JOB_END" ] && exit 1
[ -z "$RESILIENT_JOB_TASKS" ] && exit 1
while [ `date +%s` -lt $RESILIENT_JOB_END ]; do
  count=`wc -l "$RESILIENT_JOB_TASKS" | cut -d' ' -f1`
  if [ $count -lt $RESILIENT_JOB_PROCS ]; then
    ( echo "$RESILIENT_JOB_SCRIPT" | nohup /bin/sh >/dev/null 2>&1 ) &
  fi
  # Pause briefly between loops
  # usleep 10
done
EOF
)
export RESILIENT_JOB_SCRIPT

( echo "$RESILIENT_JOB_SCRIPT" | nohup /bin/sh >/dev/null 2>&1 ) &

sleep $RESILIENT_JOB_DURATION
"""
        Job.dflt_attributes[ATTR_k] = 'oe'
        self.resilient_job = Job()
        self.resilient_job.create_script(
            '\n\n' +
            'RESILIENT_JOB_PROCS=10\n' +
            'RESILIENT_JOB_DURATION=20\n\n' +
            self.resilient_job_script)

    def test_t1(self):
        """
        Resilient job run time exceeds cpuset_destroy_delay
        Confirm job is killed before cpuset_destroy_delay expires
        """
        delay = 10
        self.mom.add_config({'cpuset_destroy_delay': delay})
        self.mom.add_config({'$logevent': 2047})
        self.mom.signal('-HUP')
        self.logger.info("sleeping for one second after sending MoM SIGHUP")
        time.sleep(1)
        jid = self.server.submit(self.resilient_job)
        self.server.expect(JOB, {'job_state': 'R', 'substate': 42}, jid)
        self.logger.info(jid + "is running")
        self.logger.info("sleeping for one second to let the job spin up")
        time.sleep(1)
        path = os.path.join(os.path.sep, 'dev', 'cpuset', 'PBSPro',
                            jid, 'tasks')
        cmd = 'wc -l ' + path
        self.logger.info('Task count: ' + os.popen(cmd).read())
        started = time.time()
        self.server.delete(jid, wait=True)
        ended = time.time()
        self.assertTrue(ended < (started + delay))

# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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

# This is a queuejob hook script that determines if a job entering the system
# is an interactive job. And if so, directs it to the high priority queue
# specified in 'high_priority_queue', and also tells the server to restart
# the scheduling cycle. This  for faster qsub -Is throughput.
#
# Prerequisite:
#    Site must define a "high" queue as follows:
#        qmgr -c "create queue high queue_type=e,Priority=150
#        qenable high
#        qstart high
#    NOTE:
#        A) 150 is the default priority for an express (high) queue.
#           This will have the interactive job to preempt currently running
#           work.
#        B) If site does not want this, lower the priority of the high
#           priority queue.  This might not cause the job to run right away,
#           but will try.
#
#    This hook is instantiated as follows:
#        qmgr -c "create hook rapid event=queuejob"
#        qmgr -c "import hook rapid_inter application/x-python default rapid_inter.py"
import pbs

high_priority_queue="high"

e = pbs.event()
if e.job.interactive:
    high = pbs.server().queue(high_priority_queue)
    if high is not None:
        e.job.queue = high
        pbs.logmsg(pbs.LOG_DEBUG, "quick start interactive job")
        pbs.server().scheduler_restart_cycle()

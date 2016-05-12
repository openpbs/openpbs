# coding: utf-8
#

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
    if high != None:
        e.job.queue = high
        pbs.logmsg(pbs.LOG_DEBUG, "quick start interactive job")
        pbs.server().scheduler_restart_cycle()


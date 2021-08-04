#!/bin/bash

# Used to achieve faster job submission of large number of jobs for performance testing

if [ $# -lt 2 ]; then
	echo "syntax: $0 <num-threads> <jobs-per-thread>"
	exit 1
fi

function submit_jobs {
	njobs=$1

	echo "New thread submitting jobs=$njobs"

	for i in $(seq 1 $njobs)
	do
		qsub -- /bin/date > /dev/null
	done
}

if [ "$1" = "submit" ]; then
	njobs=$2
	submit_jobs $njobs
	exit 0
fi

nthreads=$1
njobs=$2

echo "parameters supplied: nthreads=$nthreads, njobs=$njobs"

start_time=`date +%s%3N`

for i in $(seq 1 $nthreads)
do
	setsid $0 submit $njobs &
done

wait

end_time=`date +%s%3N`

diff=`bc -l <<< "scale=3; ($end_time - $start_time) / 1000"`
total_jobs=`bc -l <<< "$njobs * $nthreads"`
perf=`bc -l <<< "scale=3; $total_jobs / $diff"`

echo "Time(ms) started=$start_time, ended=$end_time"
echo "Total jobs submitted=$total_jobs, time taken(secs.ms)=$diff, jobs/sec=$perf"

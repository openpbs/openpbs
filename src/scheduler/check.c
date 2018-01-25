/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */

/**
 * @file    pbs_sched_win.c
 *
 * @brief
 * 		pbs_sched_win.c - contains functions related to Pbs scheduler for Windows.
 *
 * Functions included are:
 *	is_ok_to_run_queue()
 *	time_to_ded_boundary()
 *	time_to_prime_boundary()
 *	shrink_to_boundary()
 *	shrink_to_minwt()
 *	shrink_to_run_event()
 *	shrink_job_algorithm()
 *	is_ok_to_run_STF()
 *	is_ok_to_run()
 *	check_avail_resources()
 *	dynamic_avail()
 *	count_res_by_user()
 *	find_counts_elm()
 *	check_ded_time_boundary()
 *	dedtime_conflict()
 *	check_nodes()
 *	check_ded_time_queue()
 *	should_check_resvs()
 *	check_prime_queue()
 *	check_nonprime_queue()
 *	check_prime_boundary()
 *	false_res()
 *	unset_str_res()
 *	zero_res()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <pbs_ifl.h>
#include <pbs_internal.h>
#include <log.h>
#include <libutil.h>
#include "check.h"
#include "config.h"
#include "server_info.h"
#include "queue_info.h"
#include "job_info.h"
#include "misc.h"
#include "constant.h"
#include "globals.h"
#include "dedtime.h"
#include "node_info.h"
#include "fifo.h"
#include "resource_resv.h"
#ifdef NAS
#include "site_code.h"
#endif
#include "node_partition.h"
#include "sort.h"
#include "server_info.h"
#include "queue_info.h"
#include "limits_if.h"
#include "simulate.h"
#include "resource.h"


/**
 *
 * @brief
 *		check to see if jobs can be run in a queue
 *
 * @param[in]	policy	-	policy info
 * @param[in]	qinfo	-	queue in question
 *
 * @return	int
 * @retval	SUCCESS	: on success or
 * @retval	scheduler failure code	: jobs can' run in queue
 *
 * @note
 * 		This function will be run once per queue every scheduling cycle
 *
 */

int
is_ok_to_run_queue(status *policy, queue_info *qinfo)
{
	int rc = 0;			/* Return Code */

	if (!qinfo->is_exec)
		return QUEUE_NOT_EXEC;

	if (!qinfo->is_started)
		return QUEUE_NOT_STARTED;

	if ((rc = check_ded_time_queue(qinfo)))
		return rc;

	if ((rc = check_prime_queue(policy, qinfo)))
		return rc;

	if ((rc = check_nonprime_queue(policy, qinfo)))
		return rc;

	if (rc == 0)
		return SUCCESS;

	return rc;
}

/**
 *
 * @brief
 * 		Time before dedicated time boundary if the job is hitting the boundary.
 *
 *	@param[in]	policy	-	policy structure
 *	@param[in]	njob	-	resource resv
 *
 *	@return	time duration up to dedicated boundary
 *	@retval sch_resource_t:	time duration upto dedicated boundary
 *							or full duration of the job if not
 *							hitting dedicated boundary.
 *	@retval UNSPECIFIED	: if job's min duration is hitting dedicated boundary
 *	@retval -3	: on error
 *
 */
sch_resource_t
time_to_ded_boundary(status *policy, resource_resv *njob)
{
	sch_resource_t 		time_left = UNSPECIFIED;
	sch_resource_t 		min_time_left = UNSPECIFIED;
	int			ded;	/* is it currently ded time? */
	struct timegap 		ded_time;
	sch_resource_t 		start = UNSPECIFIED;
	sch_resource_t 		end = UNSPECIFIED;
	sch_resource_t 		duration = UNSPECIFIED;
	sch_resource_t 		min_end = UNSPECIFIED;

	if (njob == NULL || policy == NULL)
		return -3;/* error */

	duration = njob->duration;
	ded_time = find_next_dedtime(njob->server->server_time);
	ded = is_ded_time(njob->server->server_time);
	if (!ded) {
		if (njob->start == UNSPECIFIED && njob->end ==UNSPECIFIED) {
			start = njob->server->server_time;
			time_left = calc_time_left_STF(njob, &min_time_left);
			min_end = start + min_time_left;
			end = start + time_left;
		}
		else if (njob->start == UNSPECIFIED || njob->end ==UNSPECIFIED) {
			return -3;/* error */
		}
		else {
			start = njob->start;
			end = njob->end;
			min_end = njob->start + njob->min_duration;
		}
		/* Currently not dedicated time,Job can not complete it's
		 * maximum duration before dedicated time would start,
		 * See if it can complete it's minimum duration before the start of
		 * dedicated time. If yes, set duration upto start of the dedicated time.
		 */
		if (end > ded_time.from && end < ded_time.to) {
			time_left = calc_time_left_STF(njob, &min_time_left);
			min_end = start + min_time_left;
			if (min_end > ded_time.from && min_end < ded_time.to)
				duration = UNSPECIFIED;
			else
				duration = ded_time.from - start;
		}
		/* Long job -- one which includes dedicated time.  In other words,
		 * it starts at or before dedicated time starts and
		 * it ends at or after dedicated time ends, if run for maximum duration.
		 * Check whether the job can be run for minimum duration without hitting dedicated time?
		 * If yes, set duration upto start of the dedicated time.
		 */
		if (start <= ded_time.from && end >= ded_time.to) {
			if (min_end >= ded_time.from)
				duration = UNSPECIFIED;
			else
				duration = ded_time.from - start;
		}
	}
	else /*Dedicated time */  {
		time_left = calc_time_left_STF(njob, &min_time_left);
		min_end = njob->server->server_time + min_time_left;
		end = njob->server->server_time + time_left;
		/* See if job's minimum duration can be completed without hitting
		 * dedicated time boundary. If yes, see if job's complete duration
		 * too can be satisfied. If No, set duration to the end of the dedicated time.
		 */
		if (min_end > ded_time.to)
			duration = UNSPECIFIED;
		/* Set duration only if it is hitting */
		else if (end > ded_time.to)
			duration = ded_time.to - njob->server->server_time;
	}
	return (duration);
}

/**
 *
 *	@brief
 *		Time to prime time boundary if the job is hitting prime/non-prime boundary
 *
 *
 *	@param[in]	policy	-	policy structure
 *	@param[in]	njob	-	resource resv
 *
 *	@return	time duration upto prime/non-prime boundary
 *	@retval sch_resource_t	: time duration upto prime/non-prime boundary
 *								or full duration of the job if not hitting
 *	@retval UNSPECIFIED	: if job's minimum duration is hitting prime/non-prime boundary
 *	@retval -3	: if njob is NULL or policy is NULL
 *
 */
sch_resource_t
time_to_prime_boundary(status *policy, resource_resv *njob)
{
	sch_resource_t time_left = UNSPECIFIED;
	sch_resource_t min_time_left = UNSPECIFIED; /* time left for minimum duration */
	sch_resource_t duration = UNSPECIFIED;

	if (njob == NULL || policy == NULL)
		return -3;/* error */

	duration = njob->duration;
	/* If backfill_prime is not set to true or if prime status never ends return full duration of the job */
	if (policy->prime_status_end == SCHD_INFINITY || !(policy->backfill_prime))
		return duration;

	time_left = calc_time_left_STF(njob, &min_time_left);
	/* If not hitting, return full duration */
	if (njob->server->server_time + time_left < policy->prime_status_end + policy->prime_spill)
		return duration;

	/* Job can be shrunk to time available before prime/non-prime time boundary */
	if (njob->server->server_time + min_time_left < policy->prime_status_end + policy->prime_spill)
		/* Shrink the job's duration to prime time boundary */
		duration = (policy->prime_status_end + policy->prime_spill) - (njob->server->server_time);
	else
		duration = UNSPECIFIED;
	return (duration);
}

/**
 *	@brief
 *		Shrink job to dedicated/prime time boundary(Job's duration will be set),
 *		if hitting and see if job can run. If job is not hitting a boundary see if it
 *		can run with full duration.
 *		Job duration may be set inside this function and it is caller's responsibility
 *		to keep track of the earlier value of job duration  if needed.
 *
 *	@param[in]	policy	-	policy structure
 *	@param[in]	pbs_sd  -	the connection descriptor to the pbs_server
 *	@param[in]	sinfo	-	server info
 *	@param[in]	qinfo	-	queue info
 *	@param[in]	resresv -	resource resv
 *	@param[in,out]	err	-	error reply structure
 *
 *	@par NOTE
 *			return value is required to be freed by caller
 *
 *	@return	node solution of where job will run - more info in err
 *	@retval	nspec**	: array
 *	@retval NULL	: if job/resv can not run/error
 *
 */
nspec **
shrink_to_boundary(status *policy, int pbs_sd, server_info *sinfo,
	queue_info *qinfo, resource_resv *njob, schd_error *err)
{
	nspec** ns_arr = NULL;
	sch_resource_t time_to_dedboundary = 0;
	sch_resource_t time_to_primeboundary = 0;
	time_t orig_duration = 0;

	if (njob == NULL || policy == NULL || sinfo == NULL || err == NULL)
		return NULL;
	/* No need to shrink the job to prime/dedicated boundary,
	 * if it is not hitting */
	if (err->error_code == CROSS_PRIME_BOUNDARY ||
		err->error_code == CROSS_DED_TIME_BOUNDRY) {
		orig_duration = njob->duration;
		time_to_dedboundary = time_to_ded_boundary(policy, njob);
		if (time_to_dedboundary == UNSPECIFIED)
			return NULL;
		time_to_primeboundary = time_to_prime_boundary(policy, njob);
		if (time_to_primeboundary == UNSPECIFIED)
			return NULL;
		clear_schd_error(err);
		/* Shrink job to prime/ded boundary if hitting,
		 * If both prime and ded boundaries are getting hit
		 * shrink job to the nearest of the two
		 */
		njob->duration = time_to_dedboundary < time_to_primeboundary ? time_to_dedboundary : time_to_primeboundary;
		ns_arr = is_ok_to_run(policy, pbs_sd, sinfo, qinfo, njob, NO_FLAGS, err);
		if (ns_arr && orig_duration > njob->duration) {
			char logbuf[MAX_LOG_SIZE];
			char timebuf[TIMEBUF_SIZE];
			convert_duration_to_str(njob->duration, timebuf, TIMEBUF_SIZE);
			snprintf(logbuf, MAX_LOG_SIZE, "Considering shrinking job to duration=%s, due to a prime/dedicated time conflict", timebuf);
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_NOTICE, njob->name, logbuf);
		}
	}
	return (ns_arr);
}

/**
 *
 *	@brief
 *		Shrink the job to it's minimum duration and see if it can run
 *		(Job's duration will be set to minimum duration)
 *		Job duration may be set inside this function and it is caller's responsibility
 *		to keep track of the earlier value of job duration  if needed.
 *
 *	@param[in]	policy	-	policy structure
 *	@param[in]	pbs_sd	-	the connection descriptor to the pbs_server
 *	@param[in]	sinfo	-	server info
 *	@param[in]	qinfo   -	queue info
 *	@param[in]	resresv -	resource resv
 *	@param[out]	err     -	error reply structure
 *	@par NOTE
 *		return value is required to be freed by caller
 *	@return	node solution of where job will run - more info in err
 *	@retval	nspec** array
 *	@retval NULL	: if job/resv can not run/error
 **/
nspec **
shrink_to_minwt(status *policy, int pbs_sd, server_info *sinfo,
	queue_info *qinfo, resource_resv *njob, schd_error *err)
{
	nspec** ns_arr = NULL;
	if (njob == NULL || policy == NULL || sinfo == NULL || err == NULL)
		return NULL;
	njob->duration = njob->min_duration;
	ns_arr = is_ok_to_run(policy, pbs_sd, sinfo, qinfo, njob, NO_FLAGS, err);
	return (ns_arr);
}

/**
 *
 *	@brief
 *		Shrink upto a run event and see if it can run
 *		Try only upto SHRINK_MAX_RETRY=5 events.
 *		Initially retry_count=SHRINK_MAX_RETRY.
 *	@par Algorithm:
 *		In each iteration:
 *		1.	Calculate job's possible_shrunk_duration. This should be
 *			the duration between min_end_time and last tried event's event_time.
 *			If it is the first event to be tried, possible_shrunk_duration should be
 *			the duration between min_end_time and farthest_event's event_time.
 *		2.	Divide the possible_shrunk_duration into retry_count equal segments.
 *		3.	try shrinking to the last event of the last segment.
 *		4.	If job still can't run, traverse backwards and skip rest of the events in that segment.
 *			and try last event of the next segment.
 *		5.	reduce the retry_count by 1.
 *		Repeat these iterations until either retry_count==0 or job is ok to run.
 *
 *		So what this algorithm does, is:
 *		First try shrinking to the farthest event. If it fails, divide the
 *		possible_shrunk_duration(duration between min_end_time and this event's event_time)
 *		into 5 equal segments. Skip rest of the events in the 5th segment.
 *		Try last event of the 4th segment. If it fails, recalculate possible_shrunk_duration and divide it
 *		into 4 equal segments. Skip rest of the events in the 4th segment.
 *		Try last event of the 3rd segment. If it fails, recalculate possible_shrunk_duration and divide it
 *		into 3 equal segments. Skip rest of the events in the 3rd segment.
 *		Try last event of the 2nd segment. If it fails, recalculate possible_shrunk_duration and divide it
 *		into 2 equal segments. Skip rest of the events in the 2nd segment.
 *		Try last event of the 1st segment.
 *		Example:
 *		The farthest event within job's duration is 100 hours after min_end_time.
 *		Try shrinking to this event's start time i.e. 100 hours.
 *		Let's say shrinking fails, now divide 100 hours into 5 equal segments
 *		of 20 hours each. Skip rest of the events of the last(5th) segment, since
 *		we have tried one event in this segment already. We keep traversing
 *		and skipping events untill we found an event that falls in the
 *		4th segment e.g. within (100-20=80)hours.
 *		Try shrinking to this event's start time say it is: 56 hours.
 *		Let's say shrinking fails, divide 56 hours into 4 equal segments
 *		of 14 hours each. Skip rest of the events of the last(4th) segment, since
 *		we have tried one event in this segment already. We keep traversing
 *		and skipping events untill we found an event that falls in the
 *		3rd segment e.g. within (56-14=42)hours.
 *		Try shrinking to this event's start time say it is: 36 hours.
 *		Let's say shrinking fails, divide 36 hours into 3 equal segments
 *		of 12 hours each. Skip rest of the events of the last(3rd) segment, since
 *		we have tried one event in this segment already. We keep traversing
 *		and skipping events untill we found an event that falls in the
 *		2nd segment e.g. within (36-12=24)hours.
 *		Try shrinking to this event's start time say it is: 20 hours.
 *		Let's say shrinking fails, divide 20 hours into 2 equal segments
 *		of 10 hours each. Skip rest of the events of the last(2nd) segment, since
 *		we have tried one event in this segment already. We keep traversing
 *		and skipping events untill we found an event that falls in the
 *		1st segment e.g. within (20-10=10)hours.
 *		Try shrinking to this event's start time say it is: 6 hours.
 *		If job still can't run, indicate failure.
 *
 *	@param[in]	policy	-	policy structure
 *	@param[in]	pbs_sd	-	the connection descriptor to the pbs_server
 *	@param[in]	sinfo	-	server info
 *	@param[in]	qinfo   -	queue info
 *	@param[in]	resresv -	resource resv
 *	@param[in,out]	err	-	error reply structure
 *
 *	@par NOTE:
 *		return value is required to be freed by caller
 *
 *	@return	node solution of where job will run - more info in err
 *	@retval	nspec** array
 *	@retval	NULL	: if job/resv can not run/error
 *
 */
nspec **
shrink_to_run_event(status *policy, int pbs_sd, server_info *sinfo,
	queue_info *qinfo, resource_resv *njob, schd_error *err)
{
	time_t orig_duration = UNSPECIFIED;
	time_t possible_shrink_duration = UNSPECIFIED;
	nspec** ns_arr = NULL;
	timed_event *te = NULL;
	timed_event *initial_event = NULL;
	timed_event *farthest_event = NULL;
	timed_event *last_skipped_event = NULL;
	time_t last_tried_event_time = 0;
	time_t end_time = 0;
	time_t min_end_time = 0;
	time_t servertime_now = 0;
	unsigned int event_mask;
	int retry_count = 0;

	if (njob == NULL || policy == NULL || sinfo == NULL || err == NULL)
		return NULL;

	orig_duration = njob->duration;
	possible_shrink_duration = njob->duration - njob->min_duration;
	servertime_now = sinfo->server_time;
	end_time = servertime_now + njob->duration;
	min_end_time = servertime_now + njob->min_duration;
	/* Go till farthest event in the event list between job's min and max duration */
	te = get_next_event(sinfo->calendar);
	/* Get the front pointer of the event list. It may not always be NULL. */
	if (te != NULL)
		initial_event = te->prev;
	event_mask = TIMED_RUN_EVENT;
	for (te = find_init_timed_event(te, IGNORE_DISABLED_EVENTS, event_mask);
		te != NULL && te->event_time < end_time;
		te = find_next_timed_event(te, IGNORE_DISABLED_EVENTS, event_mask)) {
		farthest_event = te;
	}
	clear_schd_error(err);
	/* If no events between job's min and max duration, try running with complete duration */
	if (farthest_event == NULL || farthest_event->event_time < min_end_time)
		ns_arr = is_ok_to_run(policy, pbs_sd, sinfo, qinfo, njob, NO_FLAGS, err);
	else {
		/* try shrinking upto the farthest event */
		end_time = farthest_event->event_time;
		retry_count = SHRINK_MAX_RETRY;
		event_mask = TIMED_RUN_EVENT;
		last_skipped_event = NULL;
		/* Now, go backwards in the events list */
		for (te = farthest_event; retry_count != 0;
			te = find_prev_timed_event(te, IGNORE_DISABLED_EVENTS, event_mask)) {
			/* If there are no events left to check or if we have reached the front of event list or
			 * if the event is falling before min end time, break.
			 */
			if ((te == NULL && last_skipped_event == NULL) || te == initial_event || te->event_time < min_end_time)
				break;
			/* If no events in this segment, then try last skipped event of the previous segment */
			else if (te == NULL) {
				te = last_skipped_event;
				last_skipped_event = NULL;
				/* No need to try next segments after this event as there are no events left */
				retry_count = 0;
			}
			/* Skip events that fall in the previous segment or if the event time is already tried */
			else if (te->event_time > end_time || te->event_time == last_tried_event_time) {
				last_skipped_event = te;
				continue;
			}
			/* Shrink job to the start of this event */
			njob->duration = te->event_time - servertime_now;
			clear_schd_error(err);
			ns_arr = is_ok_to_run(policy, pbs_sd, sinfo, qinfo, njob, NO_FLAGS, err);
			/* break if success */
			if (ns_arr != NULL)
				break;
			last_skipped_event = NULL;/* This event does not get skipped */
			last_tried_event_time = te->event_time;
			/* Shrink end_time to the next segment */
			possible_shrink_duration = njob->duration - njob->min_duration;
			end_time = min_end_time + possible_shrink_duration * (retry_count - 1)/retry_count;
			retry_count--;
		}
	}
	if (ns_arr && njob->duration == njob->min_duration) {
		char logbuf[MAX_LOG_SIZE];
		snprintf(logbuf, MAX_LOG_SIZE, "Considering shrinking job to it's minimum walltime");
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_NOTICE, njob->name, logbuf);
	}
	else if (ns_arr && orig_duration > njob->duration) {
		char logbuf[MAX_LOG_SIZE];
		char timebuf[TIMEBUF_SIZE];
		convert_duration_to_str(njob->duration, timebuf, TIMEBUF_SIZE);
		snprintf(logbuf, MAX_LOG_SIZE, "Considering shrinking job to duration=%s, due to a reservation/top job conflict", timebuf);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_NOTICE, njob->name, logbuf);
	}
	return (ns_arr);
}

/**
 *
 *	@brief
 *		Generic algorithm for shrinking a job
 *
 *	@param[in]	policy	-	policy structure
 *	@param[in]	pbs_sd	-	the connection descriptor to the pbs_server
 *	@param[in]	sinfo	-	server info
 *	@param[in]	qinfo	-	queue info
 *	@param[in]	resresv	-	resource resv
 *	@param[in,out]	err	-	error reply structure
 *
 *	@par NOTE:
 *		return value is required to be freed by caller
 *
 *	@return	node solution of where job will run - more info in err
 *	@retval	nspec** array
 *	@retval NULL	: if job/resv can not run/error
 **/
nspec **
shrink_job_algorithm(status *policy, int pbs_sd, server_info *sinfo,
	queue_info *qinfo, resource_resv *njob, schd_error *err)
{
	nspec **ns_arr = NULL;/* node solution for job */
	nspec **ns_arr_minwt = NULL;/* node solution for job if run for min_duration */
	time_t transient_duration;

	if (njob == NULL || policy == NULL || sinfo == NULL || err == NULL)
		return NULL;
	transient_duration = njob->duration;
	/* We are here because job could not run with full duration, check the error code
	 * and see if dedicated/prime conflict was found, if yes, try shrinking to boundary
	 */
	if (err->error_code == CROSS_PRIME_BOUNDARY ||
		err->error_code == CROSS_DED_TIME_BOUNDRY) {
		/* Return ns_arr on success */
		/* err will be cleared inside shrink_to_boundary if min walltime is not hitting the
		 * prime/dedicated boundary. If min walltime is still hitting prime/dedicated
		 * boundary, the err will not be cleared.
		 */
		if ((ns_arr = shrink_to_boundary(policy, pbs_sd, sinfo, qinfo, njob, err)) != NULL)
			return ns_arr;
	}
	/* Inside shrink_to_boundary(), job's duration would be set to time upto the
	 * prime/dedicated boundary if hitting. If the job could still not run,
	 * we need to see if the job can be run by shrinking further within the boundary.
	 * If err is set to CROSS_PRIME_BOUNDARY or CROSS_DED_TIME_BOUNDRY, no need to try further
	 * since we know that minimum duration of the job, itself is hitting boundary.
	 */
	transient_duration = njob->duration;
	if (ns_arr == NULL &&
		err->error_code != CROSS_PRIME_BOUNDARY &&
		err->error_code != CROSS_DED_TIME_BOUNDRY) {
		/* Try with lesser time durations */
		/* Clear any scheduling errors we got during earlier shrink attempts. */
		clear_schd_error(err);
		ns_arr_minwt = shrink_to_minwt(policy, pbs_sd, sinfo, qinfo, njob, err);
		/* Return NULL if job can't run at all */
		if (ns_arr_minwt == NULL)
			return NULL;
		else { /* If success with min walltime, try running with a bigger walltime possible */
			njob->duration = transient_duration;
			clear_schd_error(err);
			ns_arr = shrink_to_run_event(policy, pbs_sd, sinfo, qinfo, njob, err);
			/* If job still could not be run, should be run with min_duration */
			if (ns_arr == NULL) {
				ns_arr = ns_arr_minwt;
				njob->duration = njob->min_duration;
			}
			else
				free_nspecs(ns_arr_minwt);
		}
	}
	return (ns_arr);
}

/**
 *
 *	@brief
 *		check to see if the STF job is OK to run.
 *
 *	@param[in]	pbs_sd	-	the connection descriptor to the pbs_server
 *	@param[in]	policy	-	policy structure
 *	@param[in]	sinfo	-	server info
 *	@param[in]	qinfo	-	queue info
 *	@param[in]	resresv	-	resource resv
 *	@param[out]	err	-	error reply structure
 *	@par NOTE:
 *		return value is required to be freed by caller
 *
 *	@return	node solution of where job will run - more info in err
 *	@retval	nspec** array
 *	@retval NULL	: if job/resv can not run/error
 */
nspec **
is_ok_to_run_STF(status *policy, int pbs_sd, server_info *sinfo,
	queue_info *qinfo, resource_resv *njob, schd_error *err,
	nspec **(*shrink_heuristic)(status *policy, int pbs_sd, server_info *sinfo,
	queue_info *qinfo, resource_resv *njob, schd_error *err))
{
	nspec **ns_arr = NULL; /* node solution for job */
	sch_resource_t orig_duration;

	if (njob == NULL || policy == NULL || sinfo == NULL || err == NULL)
		return NULL;

	orig_duration = njob->duration;

	/* First see if it can run with full walltime */
	ns_arr = is_ok_to_run(policy, pbs_sd, sinfo, qinfo, njob, NO_FLAGS, err);
	/* If the job can not run for non-calender reasons, return NULL*/
	if (ns_arr != NULL)
		return (ns_arr);

	if (err->error_code == DED_TIME ||
		err->error_code == PRIME_ONLY ||
		err->error_code == NONPRIME_ONLY)
		return NULL;
	/* Apply the shrink heuristic  and try running the job after shrinking it */
	ns_arr = shrink_heuristic(policy, pbs_sd, sinfo, qinfo, njob, err);
	/* Reset the job duration on failure */
	if (ns_arr == NULL)
		njob->duration = orig_duration;
	else
		njob->hard_duration = njob->duration;
	return (ns_arr);
}

/**
 *
 *  @brief
 *  	Check to see if the resresv can fit within the system limits
 *	  	Used for both job to run and confirming/running of reservations.
 *
 *  @par the err structure can be set in two ways:
 *	1. For simple check functions, the error code comes from the function.
 *	   We set the error code into err within is_ok_to_run()
 *	2. For more complex check functions, we pass in err by reference.
 *	   The err will be completed inside the check function.
 *	* As an extension of #2, even more complex check functions may construct
 *	  a list of error structures.
 *
 * @param[in] policy	-	policy info
 * @param[in] pbs_sd	-	the connection descriptor to the pbs_server
 * @param[in] sinfo	-	server info
 * @param[in] qinfo	-	queue info
 * @param[in] resresv	-	resource resv
 * @param[in] flags	-	RETURN_ALL_ERR - Return all reasons why the job
 * 					can not run, not just the first.  @warning: may be expensive.
 *					This flag will ignore equivalence classes
 *				IGNORE_EQUIV_CLASS - Ignore job equivalence class feature.
 *					If a job equivalence class has been seen before and marked
 *					can_not_run, the job will still be evaluated normally.
 *
 * @par NOTE:
 *		return value is required to be freed by caller (using free_nspecs())
 *
 * @return	node solution of where job/resv will run - more info in err
 * @retval	nspec** array
 * @retval	NULL	: if job/resv can not run/error
 *
 *
 */
nspec **
is_ok_to_run(status *policy, int pbs_sd, server_info *sinfo,
	queue_info *qinfo, resource_resv *resresv, unsigned int flags, schd_error *perr)
{
	int		rc = 0;			/* Return Code */
	schd_resource	*res = NULL;		/* resource list to check */
	int		endtime = 0;		/* end time of job if started now */
	nspec		**ns_arr = NULL;	/* node solution of where request will run */
	node_partition	*allpart = NULL;	/* all partition to use (queue's or servers) */
	schd_error	*prev_err = NULL;
	schd_error	*err;
	resource_req	*resreq = NULL;

	if (sinfo == NULL || resresv == NULL || perr == NULL)
		return NULL;

	err = perr;

	if(resresv->is_job && sinfo->equiv_classes != NULL &&
	   !(flags & (IGNORE_EQUIV_CLASS|RETURN_ALL_ERR)) &&
	   resresv->ec_index != UNSPECIFIED &&
	   sinfo->equiv_classes[resresv->ec_index]->can_not_run) {
		copy_schd_error(err, sinfo->equiv_classes[resresv->ec_index]->err);
		return NULL;
	}

	if (resresv->is_job && qinfo == NULL) {
		set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
		add_err(&prev_err, err);

		if (!(flags & RETURN_ALL_ERR))
			return NULL;
		else {
			err = new_schd_error();
			if (err == NULL)
				return NULL;
		}

	}

	if (!in_runnable_state(resresv)) {
		if (resresv->is_job) {
			set_schd_error_codes(err, NOT_RUN, NOT_QUEUED);
			add_err(&prev_err, err);

			if (!(flags & RETURN_ALL_ERR))
				return NULL;

			err = new_schd_error();
			if (err == NULL)
				return NULL;
		}

		/* if a reservation is unconfirmed or being altered, we can try and confirm it */
		if ((resresv->is_resv) && 
			resresv->resv->resv_state != RESV_UNCONFIRMED &&
			resresv->resv->resv_state != RESV_BEING_ALTERED) {

			set_schd_error_codes(err, NOT_RUN, NOT_QUEUED);
			add_err(&prev_err, err);

			if (!(flags & RETURN_ALL_ERR))
				return NULL;

			err = new_schd_error();
			if (err == NULL)
				return NULL;
		}
	}


	/* quick check to see if there are enough consumable resources over all nodes
	 * on the system to see if the resresv can possibly fit.
	 * This check is bypassed for jobs in reservations.  They have their own
	 * universe of nodes
	 */
	if (resresv->is_job && resresv->job != NULL &&
			resresv->job->resv != NULL)
		allpart = NULL;
	else if (qinfo != NULL && qinfo->has_nodes)
		allpart = qinfo->allpart;
	else
		allpart = sinfo->allpart;

	if (allpart != NULL) {
		if (resresv_can_fit_nodepart(policy, allpart, resresv, flags, err) == 0) {
			schd_error *toterr;
			toterr = new_schd_error();
			if (toterr == NULL) {
				if(err != perr)
					free_schd_error(err);
				return NULL;
			}
			/* We can't fit now, lets see if we can ever fit */
			if (resresv_can_fit_nodepart(policy, allpart, resresv, flags|COMPARE_TOTAL, toterr) == 0) {
				move_schd_error(err, toterr);
				err->status_code = NEVER_RUN;
			}

			add_err(&prev_err, err);
			if (!(flags & RETURN_ALL_ERR)) {
				free_schd_error(toterr);
				return NULL;
			}
			/* reuse toterr since we've already allocated it*/
			err = toterr;
			clear_schd_error(err);
		}
	}

	/* override these limits if we were issued a qrun request */
	if (sinfo->qrun_job == NULL) {
#ifdef NAS_HWY149 /* localmod 033 */
		if (resresv->job == NULL || resresv->job->priority != NAS_HWY149)
#endif /* localmod 033 */
#ifdef NAS_HWY101 /* localmod 032 */
		if (resresv->job == NULL || resresv->job->priority != NAS_HWY101)
#endif /* localmod 032 */
		if (resresv->is_job) {
			if ((rc = check_limits(sinfo, qinfo, resresv, err, flags | CHECK_LIMIT))) {

				add_err(&prev_err, err);
				if (rc == SCHD_ERROR)
					return NULL;
				if (!(flags & RETURN_ALL_ERR))
					return NULL;
				err = new_schd_error();
				if (err == NULL)
					return NULL;

			}

			if ((rc = check_prime_boundary(policy, resresv, err))) {
				add_err(&prev_err, err);
				if (!(flags & RETURN_ALL_ERR))
					return NULL;

				err = new_schd_error();
				if (err == NULL)
					return NULL;

			}

			if ((rc = check_ded_time_queue(qinfo))) {
				set_schd_error_codes(err, NOT_RUN, rc);
				add_err(&prev_err, err);
				if (!(flags & RETURN_ALL_ERR))
					return NULL;

				err = new_schd_error();
				if (err == NULL)
					return NULL;
			}

			if ((rc = check_prime_queue(policy, qinfo))) {
				set_schd_error_codes(err, NOT_RUN, rc);
				add_err(&prev_err, err);
				if (!(flags & RETURN_ALL_ERR))
					return NULL;

				err = new_schd_error();
				if (err == NULL)
					return NULL;
			}

			if ((rc = check_nonprime_queue(policy, qinfo))) {
				enum schd_err_status scode;
				if(policy->prime_status_end == SCHD_INFINITY) /* only primetime and we're in a non-prime queue*/
					scode = NEVER_RUN;
				else
					scode = NOT_RUN;
				set_schd_error_codes(err, scode, rc);
				add_err(&prev_err, err);
				if (!(flags & RETURN_ALL_ERR))
					return NULL;

				err = new_schd_error();
				if (err == NULL)
					return NULL;
			}
#ifdef NAS /* localmod 034 */
				if ((rc = site_check_cpu_share(sinfo, policy, resresv))) {
					set_schd_error_codes(err, NOT_RUN, rc);
					add_err(&prev_err, err);
					if (!(flags & RETURN_ALL_ERR))
						return NULL;

					err = new_schd_error();
					if (err == NULL)
						return NULL;
					}
#endif /* localmod 034 */
		}
	}
	if (resresv->is_job || (resresv->is_resv && !conf.resv_conf_ignore)) {
		if ((rc = check_ded_time_boundary(resresv))) {
			set_schd_error_codes(err, NOT_RUN, rc);
			add_err(&prev_err, err);
			if (!(flags & RETURN_ALL_ERR))
				return NULL;
			err = new_schd_error();
			if (err == NULL)
				return NULL;
		}
	}


	if ((sinfo->has_nonCPU_licenses == 0) &&
		(resresv->select->total_cpus  >  sinfo->flt_lic)) {
		char errbuf[MAX_LOG_SIZE];
		set_schd_error_codes(err, NOT_RUN, ERR_SPECIAL);
		if (resresv->is_job && resresv->job !=NULL) {
			snprintf(errbuf, sizeof(errbuf),
				"Could not %s job - unable to obtain %d cpu licenses. avail_licenses=%d",
				(resresv->job->is_suspended?"resume":"run"),
				resresv->select->total_cpus, sinfo->flt_lic);
			set_schd_error_arg(err, SPECMSG, errbuf);
		}
		else if (resresv->is_resv && resresv->resv !=NULL) {
			sprintf(errbuf,
				"Could not confirm reservation - unable to obtain %d cpu licenses at requested time. avail_licenses=%d",
				resresv->select->total_cpus, sinfo->flt_lic);
			set_schd_error_arg(err, SPECMSG, errbuf);

		}
		else
			set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);

		add_err(&prev_err, err);

		if (!(flags & RETURN_ALL_ERR))
			return NULL;

		err = new_schd_error();
		if(err == NULL)
			return NULL;
	}

	if (exists_resv_event(sinfo->calendar, sinfo->server_time + resresv->hard_duration))
		endtime = sinfo->server_time + calc_time_left(resresv, 1);
	else
		endtime = sinfo->server_time + calc_time_left(resresv, 0);

	if (resresv->is_job) {
		if (resresv->job->resv == NULL) {
			res = simulate_resmin(qinfo->qres, endtime, sinfo->calendar,
				qinfo->jobs, resresv);
		}
		else
#ifdef NAS /* localmod 036 */
		{
			if (resresv->job->resv->resv->is_standing) {
				resource_req *req = find_resource_req(resresv->resreq, getallres(RES_MIN_WALLTIME));

				if (req != NULL) {
					int resv_time_left = calc_time_left(resresv->job->resv, 0);
					if (req->amount > resv_time_left) {
						set_schd_error_codes(err, NOT_RUN, INSUFFICIENT_RESOURCE);
						add_err(&prev_err, err);
						if (!(flags & RETURN_ALL_ERR))
							return NULL;

						err = new_schd_error();
						if (err == NULL)
							return NULL;
					}
				}
			}
#endif /* localmod 036 */
			res = qinfo->qres;
#ifdef NAS /* localmod 036 */
		}
#endif /* localmod 036 */
		/* If job already has a list of resources released, use that list
		 * check for available resources
		 */
		if ((resresv->job != NULL) && (resresv->job->resreq_rel != NULL))
			resreq = resresv->job->resreq_rel;
		else
			resreq = resresv->resreq;
		if (check_avail_resources(res, resreq,
			flags, policy->resdef_to_check, INSUFFICIENT_QUEUE_RESOURCE, err) == 0) {
			struct schd_error *toterr;
			toterr = new_schd_error();
			if(toterr == NULL) {
				if(err != perr)
					free_schd_error(err);
				return NULL;
			}
			/* We can't fit now, lets see if we can ever fit */
			if (check_avail_resources(res, resreq,
				flags|COMPARE_TOTAL, policy->resdef_to_check, INSUFFICIENT_QUEUE_RESOURCE, toterr) == 0) {
				move_schd_error(err , toterr);
				err->status_code = NEVER_RUN;
			}

			add_err(&prev_err, err);
			err = toterr;
			clear_schd_error(err);

			if (!(flags & RETURN_ALL_ERR)) {
				if(err != perr)
					free_schd_error(err);
				return NULL;
			}
		}
	}

	/* Don't check the server resources if a job is in a reservation.  This is
	 * because the server resources_assigned will already reflect the entire
	 * resource amount for the reservation
	 */
	if (resresv->is_resv ||
	(resresv->is_job && resresv->job->resv == NULL)) {
		res = simulate_resmin(sinfo->res, endtime, sinfo->calendar, NULL, resresv);
		if ((resresv->job != NULL) && (resresv->job->resreq_rel != NULL))
			resreq = resresv->job->resreq_rel;
		else
			resreq = resresv->resreq;
		if (check_avail_resources(res, resreq, flags,
					  policy->resdef_to_check, INSUFFICIENT_SERVER_RESOURCE, err) == 0) {
			struct schd_error *toterr;
			toterr = new_schd_error();
			if (toterr == NULL) {
				if (err != perr)
					free_schd_error(err);
				return NULL;
			}
			/* We can't fit now, lets see if we can ever fit */
			if (check_avail_resources(res, resreq,
						  flags | COMPARE_TOTAL, policy->resdef_to_check,
						  INSUFFICIENT_SERVER_RESOURCE, toterr) == 0) {
				toterr->status_code = NEVER_RUN;
				move_schd_error(err, toterr);
			}

			add_err(&prev_err, err);
			err = toterr;
			clear_schd_error(err);

			if (!(flags & RETURN_ALL_ERR)) {
				if (err != perr)
					free_schd_error(err);
				return NULL;
			}
		}
	}

	ns_arr = check_nodes(policy, sinfo, qinfo, resresv, flags, err);

	if (err->error_code != SUCCESS)
		add_err(&prev_err, err);

	/* If any more checks are added after check_nodes(),
	 * the RETURN_ALL_ERR case must be added here */

	/* This is the case where we allocated a error structure for use, but
	 * didn't end up using it.  We have to check against perr, so we don't
	 * free the caller's memory.
	 */
	if(err->status_code == SCHD_UNKWN && err != perr)
		free_schd_error(err);

	return ns_arr;
}

/**
 *
 * @brief
 * 		This function will calculate the number of
 *		multiples of the requested resources in reqlist
 *		which can be satisfied by the resources
 *		available in the reslist for the resources in checklist
 *
 * @param[in]	reslist	-	resources list
 * @param[in]	reqlist	-	the list of resources requested
 * @param[in]	flags	-	valid flags:
 *							CHECK_ALL_BOOLS - always check all boolean resources
 *							UNSET_RES_ZERO - a resource which is unset defaults to 0
 *							COMPARE_TOTAL - do comparisons against resource total rather
 *							than what is currently available
 *	        				ONLY_COMP_NONCONS - only compare non-consumable resources
 *							ONLY_COMP_CONS - only compare consumable resources
 * @param[in]	checklist	-	array of resources to check
 *                         		If NULL, all resources are checked.
 * @param[in]	fail_code	-	error code if resource request is rejected
 *	@param[out]	perr	-	if not NULL the the reason request is not
 *			  				satisfiable (i.e. the resource there is not
 *			   				enough of).  If err is NULL, no error reason is
 *			  				 returned.
 *
 * @return	int
 * @retval	number of chunks which can be allocated
 * @retval	-1	: on error
 *
 */
long long
check_avail_resources(schd_resource *reslist, resource_req *reqlist,
	unsigned int flags, resdef **checklist,
	enum sched_error fail_code, schd_error *perr)
{
	/* The resource needs to be found on the server and the requested resource
	 * needs to be found from the job, these pointers are used to store the
	 * results
	 */
	resource_req *resreq;
	schd_resource *res;
	long long num_chunk = SCHD_INFINITY;
	long long cur_chunk = 0;
	int fail = 0;
	int any_fail = 0;
	schd_error *prev_err = NULL;
	schd_error *err;
	sch_resource_t avail;			/* amount of available resource */
	schd_resource *fres = false_res();
	schd_resource *zres = zero_res();
	schd_resource *ustr = unset_str_res();
	char resbuf1[MAX_LOG_SIZE];
	char resbuf2[MAX_LOG_SIZE];
	char resbuf3[MAX_LOG_SIZE];
	char buf[MAX_LOG_SIZE];

	if (reslist == NULL || reqlist == NULL) {
		if (perr != NULL)
			set_schd_error_codes(perr, NOT_RUN, SCHD_ERROR);

		return -1;
	}

	if (fres == NULL || zres == NULL || ustr == NULL)
		return -1;

	err = perr;

	/*
	 * When we are checking for a property type resource (boolean or string)
	 * we only check for failure cases.  A successful check will be one when
	 * we fall out of the bottom of the if/else if block and move onto the
	 * next.
	 */
	for (resreq = reqlist; resreq != NULL && !fail; resreq = resreq->next) {
		if (((flags & CHECK_ALL_BOOLS) && resreq->type.is_boolean) ||
			(checklist == NULL || resdef_exists_in_array(checklist, resreq->def))) {
			res = find_resource(reslist, resreq->def);

			if (res == NULL || res->orig_str_avail == NULL) {
				/* if resources_assigned.res is unset and resources is in
				 * resource_unset_infinite, ignore the check and assume a match
				 */
				if (match_string_to_array(resreq->name, conf.ignore_res)
					!= SA_NO_MATCH) {
					continue;
				}
			}

			if (res == NULL) {
				/* If the requested resource is boolean and the resource isn't set in
				 * reslist, then this means the boolean is false
				 */
				if (resreq->type.is_boolean)
					res = fres;
				else if (resreq->type.is_num && (flags & UNSET_RES_ZERO))
					res = zres;
				else if (resreq->type.is_string && (flags & UNSET_RES_ZERO))
					res = ustr;
				else /* ignore check: effect is resource is infinite */
					continue;

				res->name = resreq->name;
				res->def = resreq->def;
			}

			if (res->indirect_res != NULL) {
				res = res->indirect_res;
			}

			if (res->type.is_non_consumable && !(flags & ONLY_COMP_CONS)) {
				if (!compare_non_consumable(res, resreq)) {
					fail = 1;
					if (err != NULL) {
						set_schd_error_codes(err, NOT_RUN, fail_code);
						err->rdef = res->def;

						snprintf(buf, sizeof(buf), "(%s != %s)",
							res_to_str_r(resreq, RF_REQUEST, resbuf1, sizeof(resbuf1)),
							res_to_str_r(res, RF_AVAIL, resbuf2, sizeof(resbuf2)));
						set_schd_error_arg(err, ARG1, buf);
					}
				}
			}
			else if (res->type.is_consumable && !(flags & ONLY_COMP_NONCONS)) {
				if (flags & COMPARE_TOTAL)
					avail = res->avail;
				else
					avail = dynamic_avail(res);

				if (avail == SCHD_INFINITY && (flags & UNSET_RES_ZERO))
					avail = 0;

				/* if there is an infinite amount available or we are requesting
				 * 0 amount of the resource, we do not need to check if any is
				 * available
				 */
				if (avail != SCHD_INFINITY && resreq->amount != 0) {
					if (avail < resreq->amount) {
						fail = 1;
						if (err != NULL) {
							set_schd_error_codes(err, NOT_RUN, fail_code);
							err->rdef = res->def;

							res_to_str_r(resreq, RF_REQUEST, resbuf1, sizeof(resbuf1));
							res_to_str_c(avail, res->def, RF_AVAIL, resbuf2, sizeof(resbuf2));
							if ((flags & UNSET_RES_ZERO) && res->avail == SCHD_INFINITY)
								res_to_str_c(0, res->def, RF_AVAIL, resbuf3, sizeof(resbuf3));
							else
								res_to_str_r(res, RF_AVAIL, resbuf3, sizeof(resbuf3));
							snprintf(buf, sizeof(buf), "(R: %s A: %s T: %s)", resbuf1, resbuf2, resbuf3);
							set_schd_error_arg(err, ARG1, buf);

						}
					}
					else {
						cur_chunk = avail / resreq->amount;
						if (cur_chunk < num_chunk || num_chunk == SCHD_INFINITY)
							num_chunk = cur_chunk;
					}
				}
			}
			if(fail && (flags&RETURN_ALL_ERR)) {
				fail = 0;
				any_fail = 1;
				err->next = new_schd_error();
				if(err->next == NULL)
					return 0;
				prev_err = err;
				err = err->next;
			}
		}
	}

	if(fail)
		any_fail = 1;

	if (any_fail)
		num_chunk = 0;

	if (prev_err != NULL && (flags & RETURN_ALL_ERR)) {
		if (prev_err != NULL) {
			free_schd_error(err);
			prev_err->next = NULL;
		}
	}

	return num_chunk;
}



/**
 * @brief
 *		dynamic_avail - find out how much of a resource is available on a
 *			server.  If the resources_available attribute is
 *			set, use that, else use resources_max.
 *
 * @param[in]	res	-	the resource to check
 *
 * @return	available amount of the resource
 *
 */

sch_resource_t
dynamic_avail(schd_resource *res)
{
	if (res->avail == SCHD_INFINITY)
		return SCHD_INFINITY;
	else if ((res->avail - res->assigned) <=0)
		return 0;
	else
		return res->avail - res->assigned;
}

/**
 * @brief
 *		count_res_by_user - count a user's current running resource usage
 *
 * @param[in]	resresv_arr	-	the resource resvs to accumulate from
 * @param[in]	user	-	the user
 * @param[in]	res	-	the resource name
 * @param[in]	cts_list	-	the user counts list
 *
 * @return	the amount of the resource used by the user
 *
 */
sch_resource_t
count_res_by_user(resource_resv **resresv_arr, char *user,
	char *res, counts *cts_list)
{
	resource_req *req;			/* the resource of the current job */
	sch_resource_t used = 0;
	counts *cts;

	int i;

	if (resresv_arr == NULL || user == NULL || res == NULL)
		return 0;

	if ((cts = find_counts(cts_list, user)) != NULL) {
		if ((req = find_resource_req_by_str(cts->rescts, res)) != NULL)
			return req->amount;
	}

	for (i = 0; resresv_arr[i] != NULL; i++) {
		if (!strcmp(resresv_arr[i]->user, user)) {
			req = find_resource_req_by_str(resresv_arr[i]->resreq, res);
			if (req != NULL)
				used += req->amount;
		}
	}
	return used;
}

/**
 *	@brief
 *		find a element of a counts structure by name.
 *		  If res arg is NULL return 'running' element.
 *		  otherwise return named resource
 *
 * @param[in]	cts_list	-	counts list to search
 * @param[in]	name	-	name of counts structure to find
 * @param[in]	res	-	resource to find or if NULL,
 *						return number of running
 *
 * @return	resource amount
 */
sch_resource_t
find_counts_elm(counts *cts_list, char *name, char *res)
{
	resource_req *req;
	counts *cts;

	if (cts_list == NULL || name == NULL)
		return 0;

	if ((cts = find_counts(cts_list, name)) != NULL) {

		if (res == NULL)
			return cts->running;
		else {
			if ((req = find_resource_req_by_str(cts->rescts, res)) != NULL)
				return req->amount;
		}
	}

	return 0;
}

/**
 * @brief
 * 		check to see if a resource resv will cross
 *		  into dedicated time
 *
 * @param[in]	resresv	-	the resource resv to check
 *
 * @retval	0	: will not cross a ded time boundary
 * @retval	CROSS_DED_TIME_BOUNDRY	: will cross a ded time boundary
 */
int
check_ded_time_boundary(resource_resv *resresv)
{
	sch_resource_t time_left;
	sch_resource_t finish_time;	/* the finish time of the job */
	int ded;			/* is it currently ded time ? */
	struct timegap ded_time;

	if (resresv == NULL)
		return 0;

	ded_time = find_next_dedtime(resresv->server->server_time);

	/* we have no dedicated time */
	if (ded_time.from == 0 && ded_time.to == 0)
		return 0;

	ded = is_ded_time(resresv->server->server_time);

	if (!ded) {
		if (dedtime_conflict(resresv)) /* has conflict or has no duration */
			return CROSS_DED_TIME_BOUNDRY;
	}
	else {
		time_left = calc_time_left(resresv, 0);
		finish_time = resresv->server->server_time + time_left;

		if (finish_time > ded_time.to)
			return CROSS_DED_TIME_BOUNDRY;
	}
	return 0;
}

/**
 * @brief
 *		dedtime_conflict - check for dedtime conflicts
 *
 * @param[in]	resresv	-	resource resv to check for conflects
 *
 * @return	int
 * @retval	1	: the reservation conflicts
 * @retval	0	: the reservation doesn't conflict
 * @retval	-1	: error
 *
 */
int
dedtime_conflict(resource_resv *resresv)
{
	time_t start;
	time_t end;
	time_t duration;
	struct timegap ded_time;

	if (resresv == NULL)
		return -1;

	if (resresv->start == UNSPECIFIED && resresv->end ==UNSPECIFIED) {
		duration = calc_time_left(resresv, 0);

		start = resresv->server->server_time;
		end = start + duration;
	}
	else if (resresv->start == UNSPECIFIED || resresv->end ==UNSPECIFIED)
		return -1;
	else {
		start = resresv->start;
		end = resresv->end;
	}

	ded_time = find_next_dedtime(start);

	/* no ded time */
	if (ded_time.from == 0 && ded_time.to == 0)
		return 0;

	/* it is currently dedicated time */
	if (start > ded_time.from && start < ded_time.to)
		return 1;

	/* currently not dedicated time, but job would not
	 * complete before dedicated time would start
	 */
	if (end > ded_time.from && end < ded_time.to)
		return 1;

	/* Long job -- one which includes dedicated time.  In other words,
	 *             it starts at or before dedicated time starts and
	 *             it ends at or after dedicated time ends
	 */
	if (start <= ded_time.from && end >= ded_time.to)
		return 1;

	return 0;
}
/**
 *	@brief
 *		check to see if there is sufficient nodes available to run a job/resv.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	sinfo	-	server associated with job/resv
 * @param[in]	qinfo	-	queue associated with job (NULL if resv)
 * @param[in]	resresv	-	resource resv to check
 * @param[in]	flags   -	flags to change functions behavior
 *					EVAL_OKBREAK - ok to break chunk up across vnodes
 *					EVAL_EXCLSET - allocate entire nodelist exclusively
 * @param[out]	err	-	error structure on why job/resv can't run
 *
 * @return	nspec **
 * @retval	node solution of where the job/resv will run
 * @retval	NULL	: if the job/resv can't run now
 *
 */
nspec **
check_nodes(status *policy, server_info *sinfo, queue_info *qinfo, resource_resv *resresv, unsigned int flags, schd_error *err)
{
	nspec			**nspec_arr = NULL;
	selspec			*spec = NULL;
	place			*pl = NULL;
	int			rc = 0;
	char			*grouparr[2] = {0};
	np_cache		*npc = NULL;
	int			error = 0;
	node_partition		**nodepart = NULL;
	node_info		**ninfo_arr = NULL;

	if (sinfo == NULL || resresv == NULL || err == NULL) {
		if (err != NULL)
			set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
		return NULL;
	}

	if (resresv->is_job) {
		if (qinfo == NULL)
			return NULL;

		if (resresv->job == NULL)
			return NULL;

		if (resresv->job->resv != NULL && resresv->job->resv->resv == NULL)
			return NULL;
	}

	/* For a reservation alter, if the reservation has not started running
	 * note that alternate nodes (that do not belong to the reservation)
	 * should also be looked at if the alter cannot be confirmed on the
	 * nodes belonging to the reservation.
	 */
	if (resresv->is_resv && resresv->resv &&
		resresv->resv->resv_state == RESV_BEING_ALTERED &&
		resresv->resv->resv_substate == RESV_CONFIRMED) {

		resresv->resv->check_alternate_nodes = 1;
	}

	/* Sets of nodes:
	   * 1. job is in a reservation - use reservation nodes
	   * 2. job or reservation has nodes -- use them
	   * 3. queue job is in has nodes associated with it - use queue's nodes
	   * 4. catchall - either the job is being run on nodes not associated with
	   * any queue, or we're node grouping and we the job can't fit into any
	   * node partition, therefore it falls in here
	   */

	/* if we're in a reservation, only check nodes assigned to the resv
	 * and not worry about node grouping since the nodes for the reservation
	 * are already in a group
	 */
	if (resresv->is_job && resresv->job->resv != NULL) {
		ninfo_arr = resresv->job->resv->resv->resv_nodes;
		nodepart = NULL;
	}
	else if (resresv->is_resv && resresv->resv && resresv->resv->check_alternate_nodes) {
		ninfo_arr = sinfo->unassoc_nodes;
		nodepart = NULL;
	}
	/* if we have nodes, use them
	 * don't care about node grouping because nodes are already assigned
	 * to the job.  We won't need to search for them.
	 */
	else if (resresv->ninfo_arr != NULL) {
		ninfo_arr = resresv->ninfo_arr;
		nodepart = NULL;
	} else {
		if (resresv->is_job && qinfo->nodepart != NULL)
			nodepart = qinfo->nodepart;
		else if (sinfo->nodepart != NULL)
			nodepart = sinfo->nodepart;
		else
			nodepart = NULL;

		if (resresv->is_job && qinfo->has_partition)
			ninfo_arr = qinfo->nodes_in_partition;
		else {
			/* if there are nodes assigned to the queue, then check those */
			if (resresv->is_job && qinfo->has_nodes)
				ninfo_arr = qinfo->nodes;
			/* last up we're not in a queue with nodes -- use the unassociated nodes */
			else
				ninfo_arr = sinfo->unassoc_nodes;
		}

	}

	if (resresv->node_set_str != NULL) {
		/* Note that jobs inside reservations have their node_set
		 * created in query_reservations()
		 */
		if (resresv->node_set == NULL) {
			resresv->node_set = create_node_array_from_str(
				qinfo->num_nodes > 0 ? qinfo->nodes :
				sinfo->unassoc_nodes,
				resresv->node_set_str);
		}
		ninfo_arr = resresv->node_set;
		nodepart = NULL;
	}

	/* job's place=group=res replaces server or queue node grouping
	 * We'll search the node partition cache for the job's pool of node partitions
	 * If it doesn't exist, we'll create it and add it to the cache
	 */
	if (resresv->place_spec->group != NULL) {
		grouparr[0] = resresv->place_spec->group;
		grouparr[1] = NULL;
		npc = find_alloc_np_cache(policy, &(sinfo->npc_arr), grouparr, ninfo_arr, cmp_placement_sets);
		if (npc != NULL)
			nodepart = npc->nodepart;
		else
			error = 1;
	}

	if (ninfo_arr == NULL || error)
		return NULL;

	get_resresv_spec(resresv, &spec, &pl);

	err->status_code = NOT_RUN;
	rc = eval_selspec(policy, spec, pl, ninfo_arr, nodepart, resresv,
		flags, &nspec_arr, err);

	/* We can run, yippie! */
	if (rc > 0)
		return nspec_arr;

	/* We were not told why the resresv can't run: Use generic reason */
	if (err->status_code == SCHD_UNKWN)
		set_schd_error_codes(err, NOT_RUN, NO_NODE_RESOURCES);

	free_nspecs(nspec_arr);

	return NULL;
}

/**
 * @brief
 *		check_ded_time_queue - check if it is the appropriate time to run jobs
 *					in a dedtime queue
 *
 * @param[in]	qinfo	-	the queue
 *
 * @return	int
 * @retval	0	: if it is dedtime and qinfo is a dedtime queue or
 *	     			if it is not dedtime and qinfo is not a dedtime queue
 * @retval	DED_TIME	: if jobs can not run in queue because of dedtime restrictions
 *
 */
int
check_ded_time_queue(queue_info *qinfo)
{
	int rc = 0;		/* return code */

	if (is_ded_time(qinfo->server->server_time)) {
		if (qinfo->is_ded_queue)
			rc = 0;
		else
			rc = DED_TIME;
	}
	else {
		if (qinfo->is_ded_queue)
			rc = DED_TIME;
		else
			rc = 0;
	}
	return rc;
}

/**
 * @brief
 *		should_check_resvs - do some simple checks to see if it is possible
 *			     for a job to interfere with reservations.
 *			     This function is called for two cases.  One we
 *			     are checking for reseservations on a specific
 *			     node, and the other is a more simple case of just
 *			     checking for reservations on the entire server
 *
 * @param[in]	sinfo	-	the server where the reservations reside
 * @param[in]	ninfo	-	to check for reservations on (may be NULL)
 * @param[in]	job	-	the job which could interfere with reservations
 *
 * @return	int
 * @retval	1	: we should check for resv conflicts
 * @retval	0	: no reservation conflicts
 * @retval	-1	: error
 */
int
should_check_resvs(server_info *sinfo, node_info *ninfo, resource_resv *job)
{
	if (sinfo == NULL || job == NULL)
		return -1;

	/* no resvs in the system - no possibility for interference */
	if (sinfo->resvs == NULL)
		return 0;

	/* check if a job is in a reservation */
	if (job->is_job && job->job != NULL && job->job->resv != NULL) {
		if (job->job->resv->resv->resv_state == RESV_RUNNING) {
			/* if we are not checking a specific node and the job is in a
			 * running reservation, there can't be any conflicts
			 */
			if (ninfo == NULL)
				return 0;

			/* we're checking a specific node, the node better be part of the
			 * reservation the job is in
			 */
			if (find_node_info(job->job->resv->ninfo_arr, ninfo->name) != NULL)
				return 0;
			else
				/* error case - a job in a running reservation should never be
				 * checked to see if it can run on a node not in it's reservation
				 */
				return -1;
		} else
			/* error case - all non-running reservations are marked can_not_run at
			 * the top of the scheduling cycle and should never make it here
			*/
			return -1;
	}

	/* So we made it here... We now know
	 * 1. all of our input is kosher
	 * 2. There are reservations in the system and the job is not in any
	 *    any of them
	 * We've done all the easy checks to see if we can bypass checking our
	 * reservations... now we have to.
	 */

	return 1;
}


/**
 *
 *	@brief
 *		Check primetime status of the queue.  If the queue
 *		    is a primetime queue and it is primetime or if the
 *		    queue is an anytime queue, jobs can run in it.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	qinfo	-	the queue to check
 *
 * @retval	0	: if the queue is an anytime queue or if it is a primetime
 * 					queue and its is currently primetime
 * @retval	PRIME_ONLY	: its a primetime queue and its not primetime
 *
 */
int
check_prime_queue(status *policy, queue_info *qinfo)
{
	/* if the queue is an anytime queue, allow jobs to run */
	if (!qinfo->is_prime_queue && !qinfo->is_nonprime_queue)
		return 0;

	if (!policy->is_prime && qinfo->is_prime_queue)
		return PRIME_ONLY;

	return 0;
}

/**
 * @brief
 * 		Check nonprime status of the queue.  If the
 *			       queue is a nonprime queue and it is nonprimetime
 *			       of the queue is an anytime queue, jobs can run
 *
 * @param[in]	policy	-	policy info
 * @param[in]	qinfo	-	the queue to check
 *
 * @return	int
 * @retval	0	: if the queue is an anytime queue or if it is nonprimetime
 * 	             	and the queue is a nonprimetime queue
 * @retval	NONPRIME_ONLY	: its a nonprime queue and its primetime
 *
 */
int
check_nonprime_queue(status *policy, queue_info *qinfo)
{
	/* if the queue is an anytime queue, allow jobs to run */
	if (!qinfo->is_prime_queue && !qinfo->is_nonprime_queue)
		return 0;

	if (policy->is_prime && qinfo->is_nonprime_queue)
		return NONPRIME_ONLY;

	return 0;
}

/**
 * @brief
 * 		check to see if the resource resv can run before
 *		the prime status changes (from primetime to nonprime etc)
 *
 * @param[in]	policy	-	policy info
 * @param[in]	resresv	-	the resource_resv to check
 * @param[out]	err     -	error structure to return
 *
 * @retval	CROSS_PRIME_BOUNDARY	: if the resource resv crosses
 * @retval	0	: if it doesn't
 * @retval	SCHD_ERROR	: on error
 *
 */
int
check_prime_boundary(status *policy, resource_resv  *resresv, struct schd_error *err)
{
	sch_resource_t time_left;

	if (resresv == NULL || policy == NULL) {
		set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
		return SCHD_ERROR;
	}

	/*
	 *   If the job is not in a prime or non-prime queue, we do not
	 *   need to check the prime boundary.
	 */
	if (resresv->is_job) {
		if (conf.prime_exempt_anytime_queues &&
			!resresv->job->queue->is_nonprime_queue &&
			!resresv->job->queue->is_prime_queue)
			return 0;
	}

	/* prime status never ends */
	if (policy->prime_status_end == SCHD_INFINITY)
		return 0;

	if (policy->backfill_prime) {
		time_left = calc_time_left(resresv, 0);

		/*
		 *   Job has no walltime requested.  Lets be conservative and assume the
		 *   job will conflict with primetime.
		 */
		if (time_left < 0) {
			set_schd_error_codes(err, NOT_RUN, CROSS_PRIME_BOUNDARY);
			set_schd_error_arg(err, ARG1, policy->is_prime ? NONPRIMESTR : PRIMESTR);
			return CROSS_PRIME_BOUNDARY;
		}

		if (resresv->server->server_time + time_left >
			policy->prime_status_end + policy->prime_spill) {
			set_schd_error_codes(err, NOT_RUN, CROSS_PRIME_BOUNDARY);
			set_schd_error_arg(err, ARG1, policy->is_prime ? NONPRIMESTR : PRIMESTR);
			return CROSS_PRIME_BOUNDARY;
		}
	}
	return 0;
}

/**
 * @brief
 * 		return a boolean resource that is False
 *         It is up to the caller to set the name and def fields
 *
 * @return	schd_resource * (set to False)
 *
 * @par MT-safe: No
 */
schd_resource *
false_res()
{
	static schd_resource *res = NULL;

	if (res == NULL) {
		res = new_resource();
		if (res != NULL) {
			res->type.is_non_consumable = 1;
			res->type.is_boolean = 1;
			res->orig_str_avail = string_dup(ATR_FALSE);
			res->avail = 0;
		}
		else
			return NULL;
	}

	res->def = NULL;
	res->name = NULL;

	return res;
}

/**
 * @brief
 * 		return a string resource that is "unset" (set to "")
 *         It is up to the caller to set the name and def fields
 *
 * @return	schd_resource *
 * @retval	NULL	: fail
 *
 * @par MT-safe: No
 */
schd_resource *
unset_str_res()
{
	static schd_resource *res = NULL;

	if (res == NULL) {
		res = new_resource();
		if ((res->str_avail = malloc(sizeof(char*) * 2)) !=NULL) {
			if (res->str_avail != NULL) {
				res->str_avail[0] = string_dup("");
				res->str_avail[1] = NULL;
			}
			else {
				log_err(errno, "unset_str_res", MEM_ERR_MSG);
				free_resource(res);
				return NULL;
			}
			res->type.is_non_consumable = 1;
			res->type.is_string = 1;
			res->orig_str_avail = string_dup("");
			res->avail = 0;
		}
		else
			return NULL;
	}

	res->name = NULL;
	res->def = NULL;

	return res;
}
/**
 * @brief
 * 		return a numeric resource that is 0
 *         It is up to the caller to set the name and def fields
 *
 * @return	schd_resource *
 * @retval	NULL	: fail
 */
schd_resource *
zero_res()
{
	static schd_resource *res = NULL;

	if (res == NULL) {
		res = new_resource();
		if (res != NULL) {
			res->type.is_consumable = 1;
			res->type.is_num = 1;
			res->orig_str_avail = string_dup("0");
			res->avail = 0;
		}
		else
			return NULL;
	}

	res->name = NULL;
	res->def = NULL;

	return res;
}

/**
 * @brief get_resresv_spec - this function returns the correct value of select and
 *	    place to be used for node searching.
 * @param[in]  *resresv resources reservation object
 * @param[out] **spec output select specification
 * @param[out] **pl  output placement specification
 *
 * @par MT-Safe: No
 * @return void
 */
void get_resresv_spec(resource_resv *resresv, selspec **spec, place **pl)
{
	static place place_spec;
	if (resresv->is_job && resresv->job != NULL) {
		if (resresv->execselect != NULL) {
			*spec = resresv->execselect;
			place_spec = *resresv->place_spec;

			/* Placement was handled the first time.  Don't let it get in the way */
			place_spec.scatter = place_spec.vscatter = place_spec.pack = 0;
			place_spec.free = 1;
			*pl = &place_spec;
		} else {
			*pl = resresv->place_spec;
			*spec = resresv->select;
		}
	} else if (resresv->is_resv && resresv->resv != NULL) {
		if (resresv->resv->resv_state == RESV_BEING_ALTERED && !resresv->resv->check_alternate_nodes)
			*spec = resresv->execselect;
		else
			*spec = resresv->select;
		place_spec = *resresv->place_spec;
		*pl = &place_spec;
	}
}


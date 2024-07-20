/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of both the OpenPBS software ("OpenPBS")
 * and the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * OpenPBS is free software. You can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * OpenPBS is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * PBS Pro is commercially licensed software that shares a common core with
 * the OpenPBS software.  For a copy of the commercial license terms and
 * conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
 * Altair Legal Department.
 *
 * Altair's dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of OpenPBS and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair's trademarks, including but not limited to "PBS™",
 * "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
 * subject to Altair's trademark licensing policies.
 */

#include <pbs_config.h>
#include "libpbs.h"
#include "server.h"
#include "svrfunc.h"

/* Global Data */

extern struct server server;
extern char server_name[];
extern char *msg_sched_called;

int scheduler_jobs_stat = 0; /* set to 1 once scheduler queried jobs in a cycle*/
extern int svr_unsent_qrun_req;

/**
 * @brief
 * 		am_jobs - array of pointers to jobs which were moved or which had certain
 * 		attributes altered (qalter) while a schedule cycle was in progress.
 *		If a job in the array is run by the scheduler in the cycle, that run
 *		request is rejected as the move/modification may impact the job's
 *		requirements and placement.
 */
static struct am_jobs {
	int am_used;	/* number of jobs in the array  */
	int am_max;	/* number of slots in the array */
	job **am_array; /* pointer the malloc-ed array  */
} am_jobs = {0, 0, NULL};

/**
 * @brief
 *	send sched command 'cmd' to given sched
 *	if cmd == SCH_SCHEDULE_AJOB send jobid also
 *
 * @param[in]	sched	-	pointer to sched obj
 * @param[in]	cmd	-	the command to send
 * @param[in]	jobid	-	the jobid to send if 'cmd' is SCH_SCHEDULE_AJOB
 *
 * @return	int
 * @retval	1	for success
 * @retval	0	for failure
 */
int
send_sched_cmd(pbs_sched *sched, int cmd, char *jobid)
{
	int ret = -1;

	DIS_tcp_funcs();

	if (sched->sc_secondary_conn < 0)
		goto err;

	if ((ret = diswsi(sched->sc_secondary_conn, cmd)) != DIS_SUCCESS)
		goto err;

	if (cmd == SCH_SCHEDULE_AJOB) {
		if ((ret = diswst(sched->sc_secondary_conn, jobid)) != DIS_SUCCESS)
			goto err;
	}

	if (dis_flush(sched->sc_secondary_conn) != 0)
		goto err;

	log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_SERVER, LOG_INFO, server_name, msg_sched_called, cmd);

	sched->sc_cycle_started = 1;

	return 1;

err:
	log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_SERVER, LOG_INFO, server_name, "write to scheduler failed, err=%d", ret);
	return 0;
}

/**
 * @brief
 * 		find_assoc_sched_jid - find the corresponding scheduler which is responsible
 * 		for handling this job.
 *
 * @param[in]	jid - job id
 * @param[out]	target_sched - pointer to the corresponding scheduler to which the job belongs to
 *
 * @retval - 1  if success
 * 	   - 0 if fail
 */
int
find_assoc_sched_jid(char *jid, pbs_sched **target_sched)
{
	job *pj;
	int t;

	*target_sched = NULL;

	t = is_job_array(jid);
	if ((t == IS_ARRAY_NO) || (t == IS_ARRAY_ArrayJob))
		pj = find_job(jid); /* regular or ArrayJob itself */
	else
		pj = find_arrayparent(jid); /* subjob(s) */

	if (pj == NULL)
		return 0;

	return find_assoc_sched_pque(pj->ji_qhdr, target_sched);
}

/**
 * @brief
 * 		find_assoc_sched_pque - find the corresponding scheduler which is responsible
 * 		for handling this job.
 *
 * @param[in]	pq		- pointer to pbs_queue
 * @param[out]  target_sched	- pointer to the corresponding scheduler to which the job belongs to
 *
  * @retval - 1 if success
 * 	    - 0 if fail
 */
int
find_assoc_sched_pque(pbs_queue *pq, pbs_sched **target_sched)
{
	pbs_sched *psched;

	*target_sched = NULL;
	if (pq == NULL)
		return 0;

	if (is_qattr_set(pq, QA_ATR_partition)) {
		char *partition = get_qattr_str(pq, QA_ATR_partition);

		if (strcmp(partition, DEFAULT_PARTITION) == 0) {
			*target_sched = dflt_scheduler;
			return 1;
		}
		for (psched = (pbs_sched *) GET_NEXT(svr_allscheds); psched; psched = (pbs_sched *) GET_NEXT(psched->sc_link)) {
			if (is_sched_attr_set(psched, SCHED_ATR_partition)) {
				if (!strcmp(get_sched_attr_str(psched, SCHED_ATR_partition), partition)) {
					*target_sched = psched;
					return 1;
				}
			}
		}
	} else {
		*target_sched = dflt_scheduler;
		return 1;
	}
	return 0;
}

/**
 * @brief
 * 		find_sched_from_sock - find the corresponding scheduler which is having
 * 		the given socket.
 *
 * @param[in]	sock	- socket descriptor
 * @param[in]	which	- which connection to check, primary or secondary
 * 			  can be one of CONN_SCHED_PRIMARY or CONN_SCHED_SECONDARY
 *
 * @retval - pointer to the corresponding pbs_sched object if success
 * 		 -  NULL if fail
 */
pbs_sched *
find_sched_from_sock(int sock, conn_origin_t which)
{
	pbs_sched *psched;

	if (sock < 0 || (which != CONN_SCHED_PRIMARY && which != CONN_SCHED_SECONDARY && which != CONN_SCHED_ANY))
		return NULL;

	for (psched = (pbs_sched *) GET_NEXT(svr_allscheds); psched; psched = (pbs_sched *) GET_NEXT(psched->sc_link)) {
		if ((which == CONN_SCHED_PRIMARY || which == CONN_SCHED_ANY) && psched->sc_primary_conn == sock)
			return psched;
		if ((which == CONN_SCHED_SECONDARY || which == CONN_SCHED_ANY) && psched->sc_secondary_conn == sock)
			return psched;
	}
	return NULL;
}

/**
 * @brief
 * Sets SCHED_ATR_sched_state and then sets flags on SVR_ATR_State if default scheduler.
 * We need to set MOD_MCACHE so the attribute can get re-encoded
 *
 * @param[in] psched - scheduler to set state on
 * @param[in] state - state of scheduler
 *
 */
static void
set_sched_state(pbs_sched *psched, char *state)
{
	if (psched == NULL)
		return;

	set_sched_attr_str_slim(psched, SCHED_ATR_sched_state, state, NULL);
	if (psched == dflt_scheduler)
		(get_sattr(SVR_ATR_State))->at_flags |= ATR_MOD_MCACHE;
}

/**
 * @brief
 * 	Receives end of cycle notification from the corresponding Scheduler
 *
 * @param[in] sock - socket to read
 *
 * @return int
 * @retval 0  - on success
 * @retval !0 - on error
 */
int
recv_sched_cycle_end(int sock)
{
	int rc = 0;
	pbs_sched *psched = find_sched_from_sock(sock, CONN_SCHED_SECONDARY);
	char *state = SC_IDLE;

	if (!psched)
		return 0;

	DIS_tcp_funcs();
	(void) disrsi(sock, &rc); /* read end cycle marker and ignore as we don't need its value */
	psched->sc_cycle_started = 0;

	if (rc != 0)
		state = SC_DOWN;

	set_sched_state(psched, state);

	/* clear list of jobs which were altered/modified during cycle */
	am_jobs.am_used = 0;
	scheduler_jobs_stat = 0;
	handle_deferred_cycle_close(psched);

	if (rc == DIS_EOF)
		rc = -1;

	return rc;
}

/**
 * @brief
 * 		schedule_high	-	send high priority commands to the scheduler
 *
 * @return	int
 * @retval  1	: scheduler busy
 * @retval  0	: scheduler notified
 * @retval	-1	: error
 */
int
schedule_high(pbs_sched *psched)
{
	if (psched == NULL)
		return -1;
	if (psched->sc_cycle_started == 0) {
		if (!send_sched_cmd(psched, psched->svr_do_sched_high, NULL)) {
			set_sched_state(psched, SC_DOWN);
			return -1;
		}
		psched->svr_do_sched_high = SCH_SCHEDULE_NULL;
		set_sched_state(psched, SC_SCHEDULING);
		return 0;
	}
	return 1;
}

/**
 * @brief
 * 		Contact scheduler and direct it to run a scheduling cycle
 *		If a request is already outstanding, skip this one.
 *
 * @return	int
 * @retval	-1	: error
 * @reval	0	: scheduler notified
 * @retval	+1	: scheduler busy
 *
 * @par Side Effects:
 *     the global variable (first_time) is changed.
 *
 * @par MT-safe: No
 */

int
schedule_jobs(pbs_sched *psched)
{
	int cmd;
	int s;
	static int first_time = 1;
	struct deferred_request *pdefr = NULL;
	pbs_list_head *deferred_req;
	char *jid = NULL;

	if (psched == NULL)
		return -1;

	if (first_time)
		cmd = SCH_SCHEDULE_FIRST;
	else
		cmd = psched->svr_do_schedule;

	if (psched->sc_cycle_started == 0) {

		/* are there any qrun requests from manager/operator */
		/* which haven't been sent,  they take priority      */
		deferred_req = fetch_sched_deferred_request(psched, false);
		if (deferred_req) {
			pdefr = (struct deferred_request *) GET_NEXT(*deferred_req);
		} /* else pdefr is NULL */
		while (pdefr) {
			if (pdefr->dr_sent == 0) {
				s = is_job_array(pdefr->dr_id);
				if (s == IS_ARRAY_NO) {
					if (find_job(pdefr->dr_id) != NULL) {
						jid = pdefr->dr_id;
						cmd = SCH_SCHEDULE_AJOB;
						break;
					}
				} else if ((s == IS_ARRAY_Single) ||
					   (s == IS_ARRAY_Range)) {
					if (find_arrayparent(pdefr->dr_id) != NULL) {
						jid = pdefr->dr_id;
						cmd = SCH_SCHEDULE_AJOB;
						break;
					}
				}
			}
			pdefr = (struct deferred_request *) GET_NEXT(pdefr->dr_link);
		}

		if (!send_sched_cmd(psched, cmd, jid)) {
			set_sched_state(psched, SC_DOWN);
			return -1;
		} else if (pdefr != NULL)
			pdefr->dr_sent = 1; /* mark entry as sent to sched */

		psched->svr_do_schedule = SCH_SCHEDULE_NULL;
		set_sched_state(psched, SC_SCHEDULING);

		first_time = 0;

		/* if there are more qrun requests queued up, reset cmd so */
		/* they are sent when the Scheduler completes this cycle   */
		if (deferred_req) {
			pdefr = GET_NEXT(*deferred_req);
		} /* else pdefr is NULL */
		while (pdefr) {
			if (pdefr->dr_sent == 0) {
				pbs_sched *target_sched;
				if (find_assoc_sched_jid(pdefr->dr_preq->rq_ind.rq_queuejob.rq_jid, &target_sched))
					target_sched->svr_do_schedule = SCH_SCHEDULE_AJOB;
				break;
			}
			pdefr = (struct deferred_request *) GET_NEXT(pdefr->dr_link);
		}

		return (0);
	} else
		return (1); /* scheduler was busy */
}

/**
 * @brief
 * 		scheduler_close - connection to scheduler has closed, clear scheduler_called
 * @par
 * 		Connection to scheduler has closed, mark scheduler sock as
 *		closed with -1 and if any clean up any outstanding deferred scheduler
 *		requests (qrun).
 * @par
 * 		Perform some cleanup as connection to scheduler has closed
 *
 * @param[in]	sock	-	communication endpoint.
 * 							closed (scheduler connection) socket, not used but
 *							required to match general prototype of functions called when
 *							a socket is closed.
 * @return	void
 */
void
scheduler_close(int sock)
{
	pbs_sched *psched;
	int other_conn = -1;

	psched = find_sched_from_sock(sock, CONN_SCHED_ANY);
	if (psched == NULL)
		return;

	if (sock == psched->sc_primary_conn)
		other_conn = psched->sc_secondary_conn;
	else if (sock == psched->sc_secondary_conn)
		other_conn = psched->sc_primary_conn;
	else
		return;
	log_eventf(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SCHED, LOG_CRIT, psched->sc_name, "scheduler disconnected");
	psched->sc_secondary_conn = -1;
	psched->sc_primary_conn = -1;
	if (other_conn != -1) {
		net_add_close_func(other_conn, NULL);
		close_conn(other_conn);
	}
	psched->sc_cycle_started = 0;
	set_sched_state(psched, SC_DOWN);

	/* clear list of jobs which were altered/modified during cycle */
	am_jobs.am_used = 0;
	scheduler_jobs_stat = 0;

	handle_deferred_cycle_close(psched);
}

/**
 * @brief
 * 		Add a job to the am_jobs array, called when a job is moved (locally)
 *		or modified (qalter) during a scheduling cycle
 *
 * @param[in]	pjob	-	pointer to job to add to the array.
 */
void
am_jobs_add(job *pjob)
{
	if (am_jobs.am_used == am_jobs.am_max) {
		/* Need to expand the array, increase by 4 slots */
		job **tmp = realloc(am_jobs.am_array, sizeof(job *) * (am_jobs.am_max + 4));
		if (tmp == NULL)
			return; /* cannot increase array, so be it */
		am_jobs.am_array = tmp;
		am_jobs.am_max += 4;
	}
	*(am_jobs.am_array + am_jobs.am_used++) = pjob;
}

/**
 * @brief
 * 		Determine if the job in question is in the list of moved/altered
 *		jobs.  Called when a run request for a job comes from the Scheduler.
 *
 * @param[in]	pjob	-	pointer to job in question.
 *
 * @return	int
 * @retval	0	- job not in list
 * @retval	1	- job is in list
 */
int
was_job_alteredmoved(job *pjob)
{
	int i;
	for (i = 0; i < am_jobs.am_used; ++i) {
		if (*(am_jobs.am_array + i) == pjob)
			return 1;
	}
	return 0;
}

/**
 * @brief
 * 		set_scheduler_flag - set the flag to call the Scheduler
 *		certain flag values should not be overwritten
 *
 * @param[in]	flag	-	scheduler command.
 * @param[in] psched -   pointer to sched object. Then set the flag only for this object.
 *                                     NULL. Then set the flag for all the scheduler objects.
 */
void
set_scheduler_flag(int flag, pbs_sched *psched)
{
	int single_sched;

	if (psched)
		single_sched = 1;
	else {
		single_sched = 0;
		psched = (pbs_sched *) GET_NEXT(svr_allscheds);
	}

	for (; psched; psched = (pbs_sched *) GET_NEXT(psched->sc_link)) {
		/* high priority commands:
		 * Note: A) usually SCH_QUIT is sent directly and not via here
		 *       B) if we ever add a 3rd high prio command, we can lose them
		 */
		if (flag == SCH_CONFIGURE || flag == SCH_QUIT) {
			if (psched->svr_do_sched_high == SCH_QUIT)
				return; /* keep only SCH_QUIT */

			psched->svr_do_sched_high = flag;
		} else
			psched->svr_do_schedule = flag;
		if (single_sched)
			break;
	}
}

/**
 * @brief
 * 	Handles deferred requests during scheduling cycle closure
 *
 * @return void
 */
void
handle_deferred_cycle_close(pbs_sched *psched)
{
	pbs_list_head *deferred_req;
	struct deferred_request *pdefr;

	deferred_req = fetch_sched_deferred_request(psched, false);
	if (deferred_req == NULL) {
		return;
	}

	/*
	 * If a deferred (from qrun) had been sent to the Scheduler and is still
	 * there, then the Scheduler must have closed the connection without
	 * dealing with the job. Tell qrun it failed if the qrun connection
	 * is still there.
	 *
	 * If any qrun request is pending in the deffered list, set svr_unsent_qrun_req so
	 * they are sent when the Scheduler completes this cycle
	 */
	pdefr = (struct deferred_request *) GET_NEXT(*deferred_req);

	while (pdefr) {
		struct deferred_request *next_pdefr = (struct deferred_request *) GET_NEXT(pdefr->dr_link);

		if (pdefr->dr_sent != 0) {
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_NOTICE, pdefr->dr_id, "deferred qrun request to scheduler failed");
			if (pdefr->dr_preq != NULL)
				req_reject(PBSE_INTERNAL, 0, pdefr->dr_preq);
			/* unlink and free the deferred request entry */
			delete_link(&pdefr->dr_link);
			free(pdefr);
		} else if (pdefr->dr_sent == 0 && svr_unsent_qrun_req == 0)
			svr_unsent_qrun_req = 1;

		pdefr = next_pdefr;
	}

	clear_sched_deferred_request(psched);
}

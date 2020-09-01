/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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


/**
 * @file    queue_info.c
 *
 * @brief
 * 		queue_info.c -  contains functions which are related to queue_info structure.
 *
 * Functions included are:
 * 	query_queues()
 * 	query_queue_info()
 * 	new_queue_info()
 * 	free_queues()
 * 	update_queue_on_run()
 * 	update_queue_on_end()
 * 	free_queue_info()
 * 	dup_queues()
 * 	dup_queue_info()
 * 	find_queue_info()
 * 	node_queue_cmp()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <pbs_error.h>
#include <pbs_ifl.h>
#include <log.h>
#include "queue_info.hpp"
#include "job_info.hpp"
#include "resv_info.hpp"
#include "constant.hpp"
#include "misc.hpp"
#include "check.hpp"
#include "config.hpp"
#include "globals.hpp"
#include "node_info.hpp"
#include "sort.hpp"
#include "resource_resv.hpp"
#include "resource.hpp"
#include "state_count.hpp"
#ifdef NAS
#include "site_code.hpp"
#endif
#include "node_partition.hpp"
#include "limits_if.h"
#include "pbs_internal.h"
#include "fifo.hpp"

/**
 * @brief
 * 		creates an array of queue_info structs which contain
 *			an array of jobs
 *
 * @param[in]	policy	-	policy info
 * @param[in]	pbs_sd	-	connection to the pbs_server
 * @param[in]	sinfo	-	server to query queues from
 *
 * @return	pointer to the head of the queue structure
 *
 */
queue_info **
query_queues(status *policy, int pbs_sd, server_info *sinfo)
{
	/* the linked list of queues returned from the server */
	struct batch_status *queues;

	/* the current queue in the linked list of queues */
	struct batch_status *cur_queue;

	/* array of pointers to internal scheduling structure for queues */
	queue_info **qinfo_arr;

	/* the current queue we are working on */
	queue_info *qinfo;

	/* return code */
	sched_error ret;

	/* buffer to store comment message */
	char comment[MAX_LOG_SIZE];

	/* buffer to store log message */
	char log_msg[MAX_LOG_SIZE];

	/* used to count users/groups */
	counts *cts;

	/* peer server descriptor */
	int peer_sd = 0;

	int i, j, qidx;
	int num_queues = 0;

	int err = 0;			/* an error has occurred */

	/* used for pbs_geterrmsg() */
	const char *errmsg;

	schd_error *sch_err;

	if (policy == NULL || sinfo == NULL)
		return NULL;

	sch_err = new_schd_error();

	if(sch_err == NULL)
		return NULL;

	/* get queue info from PBS server */
	if ((queues = pbs_statque(pbs_sd, NULL, NULL, NULL)) == NULL) {
		errmsg = pbs_geterrmsg(pbs_sd);
		if (errmsg == NULL)
			errmsg = "";
	log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_QUEUE, LOG_NOTICE, "queue_info",
			"Statque failed: %s (%d)", errmsg, pbs_errno);
		free_schd_error(sch_err);
		return NULL;
	}

	cur_queue = queues;

	while (cur_queue != NULL) {
		num_queues++;
		cur_queue = cur_queue->next;
	}

	if ((qinfo_arr = (queue_info **) malloc(sizeof(queue_info *) * (num_queues + 1))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		pbs_statfree(queues);
		free_schd_error(sch_err);
		return NULL;
	}
	qinfo_arr[0] = NULL;

	cur_queue = queues;

	for (i = 0, qidx=0; cur_queue != NULL && !err; i++) {
		/* convert queue information from batch_status to queue_info */
		if ((qinfo = query_queue_info(policy, cur_queue, sinfo)) == NULL) {
			free_schd_error(sch_err);
			pbs_statfree(queues);
			free_queues(qinfo_arr);
			return NULL;
		}

		if (queue_in_partition(qinfo, sc_attrs.partition)) {
			/* check if the queue is a dedicated time queue */
			if (conf.ded_prefix[0] != '\0')
				if (!strncmp(qinfo->name, conf.ded_prefix, strlen(conf.ded_prefix))) {
					qinfo->is_ded_queue = 1;
					sinfo->has_ded_queue = 1;
				}

			/* check if the queue is a prime time queue */
			if (conf.pt_prefix[0] != '\0')
				if (!strncmp(qinfo->name, conf.pt_prefix, strlen(conf.pt_prefix))) {
					qinfo->is_prime_queue = 1;
					sinfo->has_prime_queue = 1;
				}

			/* check if the queue is a nonprimetime queue */
			if (conf.npt_prefix[0] != '\0')
				if (!strncmp(qinfo->name, conf.npt_prefix, strlen(conf.npt_prefix))) {
					qinfo->is_nonprime_queue = 1;
					sinfo->has_nonprime_queue = 1;
				}

			/* check if it is OK for jobs to run in the queue */
			ret = is_ok_to_run_queue(sinfo->policy, qinfo);
			if (ret == SUCCESS)
				qinfo->is_ok_to_run = 1;
			else
				qinfo->is_ok_to_run = 0;

			if (qinfo->has_nodes) {
				qinfo->nodes = node_filter(sinfo->nodes, sinfo->num_nodes,
					node_queue_cmp, (void *) qinfo->name, 0);

				qinfo->num_nodes = count_array(qinfo->nodes);

			}

			if (ret != QUEUE_NOT_EXEC) {
				/* get all the jobs which reside in the queue */
				qinfo->jobs = query_jobs(policy, pbs_sd, qinfo, NULL, qinfo->name);

				for (j = 0; j < NUM_PEERS && conf.peer_queues[j].local_queue != NULL; j++) {
					int peer_on = 1;

					if (!strcmp(conf.peer_queues[j].local_queue, qinfo->name)) {
						/* Locally-peered queues reuse the scheduler's connection */
						if (conf.peer_queues[j].remote_server == NULL) {
							peer_sd = pbs_sd;
						}
						else if ((peer_sd = pbs_connect_noblk(conf.peer_queues[j].remote_server, 2)) < 0) {
							/* Message was PBSEVENT_SCHED - moved to PBSEVENT_DEBUG2 for
							 * failover reasons (see bz3002)
							 */
							log_eventf(PBSEVENT_DEBUG2, PBS_EVENTCLASS_REQUEST, LOG_INFO, qinfo->name,
								"Can not connect to peer %s", conf.peer_queues[j].remote_server);
							conf.peer_queues[j].peer_sd = -1;
							peer_on = 0; /* do not proceed */
						}
						if (peer_on) {
								conf.peer_queues[j].peer_sd = peer_sd;
								qinfo->is_peer_queue = 1;
								/* get peered jobs */
								qinfo->jobs = query_jobs(policy, peer_sd, qinfo, qinfo->jobs, conf.peer_queues[j].remote_queue);
						}
					}
				}

				clear_schd_error(sch_err);
				set_schd_error_codes(sch_err, NOT_RUN, ret);
				if (qinfo->is_ok_to_run == 0) {
					translate_fail_code(sch_err, comment, log_msg);
					update_jobs_cant_run(pbs_sd, qinfo->jobs, NULL, sch_err, START_WITH_JOB);
				}

				count_states(qinfo->jobs, &(qinfo->sc));

				qinfo->running_jobs = resource_resv_filter(qinfo->jobs,
					qinfo->sc.total, check_run_job, NULL, 0);

				if (qinfo->running_jobs  == NULL)
					err = 1;

				if (qinfo->has_soft_limit || qinfo->has_hard_limit) {
					counts *allcts;
					allcts = find_alloc_counts(qinfo->alljobcounts,
						PBS_ALL_ENTITY);
					if (qinfo->alljobcounts == NULL)
						qinfo->alljobcounts = allcts;

					if (qinfo->running_jobs != NULL) {
						/* set the user and group counts */
						for (j = 0; qinfo->running_jobs[j] != NULL; j++) {
							cts = find_alloc_counts(qinfo->user_counts,
								qinfo->running_jobs[j]->user);
							if (qinfo->user_counts == NULL)
								qinfo->user_counts = cts;

							update_counts_on_run(cts, qinfo->running_jobs[j]->resreq);

							cts = find_alloc_counts(qinfo->group_counts,
								qinfo->running_jobs[j]->group);

							if (qinfo->group_counts == NULL)
								qinfo->group_counts = cts;

							update_counts_on_run(cts, qinfo->running_jobs[j]->resreq);

							cts = find_alloc_counts(qinfo->project_counts,
								qinfo->running_jobs[j]->project);

							if (qinfo->project_counts == NULL)
								qinfo->project_counts = cts;

							update_counts_on_run(cts, qinfo->running_jobs[j]->resreq);

							update_counts_on_run(allcts, qinfo->running_jobs[j]->resreq);
						}
						create_total_counts(NULL, qinfo, NULL, QUEUE);
					}
				}
			}

			qinfo_arr[qidx++] = qinfo;
			qinfo_arr[qidx] = NULL;

		} else
			free_queue_info(qinfo);

		cur_queue = cur_queue->next;
	}
	qinfo_arr[qidx] = NULL;


	pbs_statfree(queues);
	free_schd_error(sch_err);
	if (err) {
		if (qinfo_arr != NULL)
			free_queues(qinfo_arr);

		return NULL;
	}

	return qinfo_arr;
}

/**
 * @brief
 *		query_queue_info - collects information from a batch_status and
 *			   puts it in a queue_info struct for easier access
 *
 * @param[in]	policy	-	policy info
 * @param[in]	queue	-	batch_status struct to get queue information from
 * @param[in]	sinfo	-	server where queue resides
 *
 * @return	newly allocated and filled queue_info
 * @retval	NULL	: on error
 *
 */

queue_info *
query_queue_info(status *policy, struct batch_status *queue, server_info *sinfo)
{
	struct attrl *attrp;		/* linked list of attributes from server */
	struct queue_info *qinfo;	/* queue_info being created */
	schd_resource *resp;		/* resource in resource qres list */
	char *endp;			/* used with strtol() */
	sch_resource_t count;		/* used to convert string -> num */

	if ((qinfo = new_queue_info(1)) == NULL)
		return NULL;

	if (qinfo->liminfo == NULL)
		return NULL;

	if ((qinfo->name = string_dup(queue->name)) == NULL) {
		free_queue_info(qinfo);
		return NULL;
	}

	attrp = queue->attribs;
	qinfo->server = sinfo;
	while (attrp != NULL) {
		if (!strcmp(attrp->name, ATTR_start)) { /* started */
			if (!strcmp(attrp->value, ATR_TRUE))
				qinfo->is_started = 1;
			else
				qinfo->is_started = 0;
		}
		else if (!strcmp(attrp->name, ATTR_HasNodes)) {
			if (!strcmp(attrp->value, ATR_TRUE)) {
				sinfo->has_nodes_assoc_queue = 1;
				qinfo->has_nodes = 1;
			}
			else
				qinfo->has_nodes = 0;
		}
		else if(!strcmp(attrp->name, ATTR_backfill_depth)) {
			qinfo->backfill_depth = strtol(attrp->value, NULL, 10);
			if(qinfo->backfill_depth > 0)
				policy->backfill = 1;
		}
		else if(!strcmp(attrp->name, ATTR_partition)) {
			if (attrp->value != NULL) {
				qinfo->partition = string_dup(attrp->value);
				if (qinfo->partition == NULL) {
					log_err(errno, __func__, MEM_ERR_MSG);
					free_queue_info(qinfo);
					return NULL;
				}
			}
		}
		else if (is_reslimattr(attrp)) {
			(void) lim_setlimits(attrp, LIM_RES, qinfo->liminfo);
			if(strstr(attrp->value, "u:") != NULL)
				qinfo->has_user_limit = 1;
			if(strstr(attrp->value, "g:") != NULL)
				qinfo->has_grp_limit = 1;
			if(strstr(attrp->value, "p:") != NULL)
				qinfo->has_proj_limit = 1;
			if(strstr(attrp->value, "o:") != NULL)
				qinfo->has_all_limit = 1;
		}
		else if (is_runlimattr(attrp)) {
			(void) lim_setlimits(attrp, LIM_RUN, qinfo->liminfo);
			if(strstr(attrp->value, "u:") != NULL)
				qinfo->has_user_limit = 1;
			if(strstr(attrp->value, "g:") != NULL)
				qinfo->has_grp_limit = 1;
			if(strstr(attrp->value, "p:") != NULL)
				qinfo->has_proj_limit = 1;
			if(strstr(attrp->value, "o:") != NULL)
				qinfo->has_all_limit = 1;
		}
		else if (is_oldlimattr(attrp)) {
			const char *limname = convert_oldlim_to_new(attrp);
			(void) lim_setlimits(attrp, LIM_OLD, qinfo->liminfo);

			if(strstr(limname, "u:") != NULL)
				qinfo->has_user_limit = 1;
			if(strstr(limname, "g:") != NULL)
				qinfo->has_grp_limit = 1;
			/* no need to check for project limits because there were no old style project limits */
		}
		else if (!strcmp(attrp->name, ATTR_p)) { /* priority */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			qinfo->priority = count;
		}
		else if (!strcmp(attrp->name, ATTR_qtype)) { /* queue_type */
			if (!strcmp(attrp->value, "Execution")) {
				qinfo->is_exec = 1;
				qinfo->is_route = 0;
			}
			else if (!strcmp(attrp->value, "Route")) {
				qinfo->is_route = 1;
				qinfo->is_exec = 0;
			}
		}
		else if (!strcmp(attrp->name, ATTR_NodeGroupKey))
			qinfo->node_group_key = break_comma_list(attrp->value);
		else if (!strcmp(attrp->name, ATTR_rescavail)) { /* resources_available*/
#ifdef NAS
			/* localmod 040 */
			if (!strcmp(attrp->resource, ATTR_ignore_nodect_sort)) {
				if (!strcmp(attrp->value, ATR_TRUE))
					qinfo->ignore_nodect_sort = 1;
				else
					qinfo->ignore_nodect_sort = 0;

				resp = NULL;
			}/* localmod 038 */
			else if (!strcmp(attrp->resource, ATTR_topjob_setaside)) {
				if (!strcmp(attrp->value, ATR_TRUE))
					qinfo->is_topjob_set_aside = 1;
				else
					qinfo->is_topjob_set_aside = 0;

				resp = NULL;
			} else
#endif
				resp = find_alloc_resource_by_str(qinfo->qres, attrp->resource);
			if (resp != NULL) {
				if (qinfo->qres == NULL)
					qinfo->qres = resp;

				if (set_resource(resp, attrp->value, RF_AVAIL) == 0) {
					free_queue_info(qinfo);
					return NULL;
				}
				qinfo->has_resav_limit = 1;
			}
		} else if (!strcmp(attrp->name, ATTR_rescassn)) { /* resources_assigned */
			resp = find_alloc_resource_by_str(qinfo->qres, attrp->resource);
			if (qinfo->qres == NULL)
				qinfo->qres = resp;
			if (resp != NULL) {
				if (set_resource(resp, attrp->value, RF_ASSN) == 0) {
					free_queue_info(qinfo);
					return NULL;
				}
			}
		}
#ifdef NAS
		/* localmod 046 */
		else if (!strcmp(attrp->name, ATTR_maxstarve)) {
			time_t	starve;
			starve = site_decode_time(attrp->value);
			qinfo->max_starve = starve;
		}
		/* localmod 034 */
		else if (!strcmp(attrp->name, ATTR_maxborrow)) {
			time_t	borrow;
			borrow = site_decode_time(attrp->value);
			qinfo->max_borrow = borrow;
		}
#endif

		attrp = attrp->next;
	}

	if (has_hardlimits(qinfo->liminfo))
		qinfo->has_hard_limit = 1;
	if (has_softlimits(qinfo->liminfo))
		qinfo->has_soft_limit = 1;

	return qinfo;
}

/**
 * @brief
 *		new_queue_info - allocate and initalize a new queue_info struct
 *
 * @param[in]	limallocflag	-	limit allocation flag.
 *
 * @return	the newly allocated struct
 * @retval	NULL	: on error
 *
 */

queue_info *
new_queue_info(int limallocflag)
{
	queue_info *qinfo;

	if ((qinfo = (queue_info *)malloc(sizeof(queue_info))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	qinfo->is_started	 = 0;
	qinfo->is_exec	 = 0;
	qinfo->is_route	 = 0;
	qinfo->is_ded_queue = 0;
	qinfo->is_prime_queue = 0;
	qinfo->is_nonprime_queue = 0;
	qinfo->is_ok_to_run	 = 0;
	qinfo->has_nodes = 0;
	qinfo->priority	 = 0;
	qinfo->has_soft_limit = 0;
	qinfo->has_hard_limit = 0;
	qinfo->is_peer_queue = 0;
	qinfo->has_resav_limit = 0;
	qinfo->has_user_limit = 0;
	qinfo->has_grp_limit = 0;
	qinfo->has_proj_limit = 0;
	qinfo->has_all_limit = 0;
	init_state_count(&(qinfo->sc));
	if ((limallocflag != 0))
		qinfo->liminfo = lim_alloc_liminfo();
	qinfo->num_nodes	 = 0;
	qinfo->name		 = NULL;
	qinfo->qres		 = NULL;
	qinfo->jobs		 = NULL;
	qinfo->running_jobs	 = NULL;
	qinfo->server	 = NULL;
	qinfo->resv		 = NULL;
	qinfo->nodes	 = NULL;
	qinfo->alljobcounts	 = NULL;
	qinfo->group_counts  = NULL;
	qinfo->project_counts  = NULL;
	qinfo->user_counts   = NULL;
	qinfo->total_alljobcounts	 = NULL;
	qinfo->total_group_counts  = NULL;
	qinfo->total_project_counts  = NULL;
	qinfo->total_user_counts   = NULL;
	qinfo->nodepart	 = NULL;
	qinfo->node_group_key= NULL;
	qinfo->allpart       = NULL;
	qinfo->num_parts = 0;
	qinfo->num_topjobs = 0;
	qinfo->backfill_depth = UNSPECIFIED;
#ifdef NAS
	/* localmod 046 */
	qinfo->max_starve	 = 0;
	/* localmod 034 */
	qinfo->max_borrow	 = UNSPECIFIED;
	/* localmod 038 */
	qinfo->is_topjob_set_aside	 = 0;
	/* localmod 040 */
	qinfo->ignore_nodect_sort	 = 0;
#endif
	qinfo->partition = NULL;
	return qinfo;
}

/**
 * @brief
 *		free_queues - free an array of queues
 *
 * @param[in,out]	qarr	-	qinfo array to delete
 *
 * @return	nothing
 *
 */

void
free_queues(queue_info **qarr)
{
	int i;
	if (qarr == NULL)
		return;

	for (i = 0; qarr[i] != NULL; i++) {
		free_resource_resv_array(qarr[i]->jobs);
		free_queue_info(qarr[i]);
	}

	free(qarr);

}

/**
 * @brief
 *		update_queue_on_run - update the information kept in a qinfo structure
 *				when a resource resv is run
 *
 * @param[in,out]	qinfo	-	the queue to update
 * @param[in]	resresv	-	the resource resv that was run
 * @param[in]  job_state -	the old state of a job if resresv is a job
 *				If the old_state is found to be suspended
 *				then only resources that were released
 *				during suspension will be accounted.
 *
 * @return	nothing
 *
 */
void
update_queue_on_run(queue_info *qinfo, resource_resv *resresv, char *job_state)
{
	resource_req *req;
	schd_resource *res;
	counts *cts;
	counts *allcts;

	if (qinfo == NULL || resresv == NULL)
		return;

	if (resresv->is_job &&  resresv->job == NULL)
		return;

	if (resresv->is_job) {
		qinfo->sc.running++;
		/* note: if job is suspended, counts will get off.
		 *       sc.queued is not used, and sc.suspended isn't used again
		 *       after this point
		 *       BZ 5798
		 */
		qinfo->sc.queued--;
	}

	if (cstat.node_sort[0].res_name != NULL &&
		conf.node_sort_unused && qinfo->nodes != NULL)
		qsort(qinfo->nodes, qinfo->num_nodes, sizeof(node_info *),
			multi_node_sort);


	if ((job_state != NULL) && (*job_state == 'S') && (resresv->job->resreq_rel != NULL))
		req = resresv->job->resreq_rel;
	else
		req = resresv->resreq;

	while (req != NULL) {
		res = find_resource(qinfo->qres, req->def);

		if (res != NULL)
			res->assigned += req->amount;

		req = req->next;
	}

	qinfo->running_jobs = add_resresv_to_array(qinfo->running_jobs, resresv, NO_FLAGS);

	if (qinfo->has_soft_limit || qinfo->has_hard_limit) {

		if (resresv->is_job && resresv->job !=NULL) {
			update_total_counts(NULL, qinfo, resresv, QUEUE);

			cts = find_alloc_counts(qinfo->group_counts, resresv->group);

			if (qinfo->group_counts == NULL)
				qinfo->group_counts = cts;

			update_counts_on_run(cts, resresv->resreq);

			cts = find_alloc_counts(qinfo->project_counts, resresv->project);

			if (qinfo->project_counts == NULL)
				qinfo->project_counts = cts;

			update_counts_on_run(cts, resresv->resreq);

			cts = find_alloc_counts(qinfo->user_counts, resresv->user);

			if (qinfo->user_counts == NULL)
				qinfo->user_counts = cts;

			update_counts_on_run(cts, resresv->resreq);

			allcts = find_alloc_counts(qinfo->alljobcounts, PBS_ALL_ENTITY);

			if (qinfo->alljobcounts == NULL)
				qinfo->alljobcounts = allcts;

			update_counts_on_run(allcts, resresv->resreq);
		}
	}
}

/**
 * @brief
 *		update_queue_on_end - update a queue when a resource resv
 *				has finished running
 *
 * @par	NOTE:	job must be in pre-ended state
 *
 * @param[in,out]	qinfo	-	the queue to update
 * @param[in]	resresv	-	the resource resv which is no longer running
 * @param[in]  job_state -	the old state of a job if resresv is a job
 *				If the old_state is found to be suspended
 *				then only resources that were released
 *				during suspension will be accounted.
 *
 * @return	nothing
 *
 */
void
update_queue_on_end(queue_info *qinfo, resource_resv *resresv,
	const char *job_state)
{
	schd_resource *res = NULL;			/* resource from queue */
	resource_req *req = NULL;			/* resource request from job */
	counts *cts;					/* update user/group counts */

	if (qinfo == NULL || resresv == NULL)
		return;

	if (resresv->is_job && resresv->job == NULL)
		return;

	if (resresv->is_job) {
		if (resresv->job->is_running) {
			qinfo->sc.running--;
			remove_resresv_from_array(qinfo->running_jobs, resresv);
		}
		else if (resresv->job->is_exiting)
			qinfo->sc.exiting--;

		state_count_add(&(qinfo->sc), job_state, 1);
	}

	if ((job_state != NULL) && (*job_state == 'S') && (resresv->job->resreq_rel != NULL))
		req = resresv->job->resreq_rel;
	else
		req = resresv->resreq;

	while (req != NULL) {
		res = find_resource(qinfo->qres, req->def);

		if (res != NULL) {
			res->assigned -= req->amount;

			if (res->assigned < 0) {
				log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
					"%s turned negative %.2lf, setting it to 0", res->name, res->assigned);
				res->assigned = 0;
			}
		}
		req = req->next;
	}

	if (qinfo->has_soft_limit || qinfo->has_hard_limit) {
		if (is_resresv_running(resresv)) {
			update_total_counts_on_end(NULL, qinfo, resresv , QUEUE);
			cts = find_counts(qinfo->group_counts, resresv->group);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);

			cts = find_counts(qinfo->project_counts, resresv->project);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);

			cts = find_counts(qinfo->user_counts, resresv->user);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);

			cts = find_alloc_counts(qinfo->alljobcounts, PBS_ALL_ENTITY);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);
		}
	}
}

/**
 * @brief
 *		free_queue_info - free space used by a queue info struct
 *
 * @param[in,out]	qinfo	-	queue to free
 *
 * @return	nothing
 *
 */
void
free_queue_info(queue_info *qinfo)
{
	if (qinfo->name != NULL)
		free(qinfo->name);
	if (qinfo->qres != NULL)
		free_resource_list(qinfo->qres);
	if (qinfo->running_jobs != NULL)
		free(qinfo->running_jobs);
	if (qinfo->nodes != NULL)
		free(qinfo->nodes);
	if (qinfo->alljobcounts != NULL)
		free_counts_list(qinfo->alljobcounts);
	if (qinfo->group_counts != NULL)
		free_counts_list(qinfo->group_counts);
	if (qinfo->project_counts != NULL)
		free_counts_list(qinfo->project_counts);
	if (qinfo->user_counts != NULL)
		free_counts_list(qinfo->user_counts);
	if (qinfo->total_alljobcounts != NULL)
		free_counts_list(qinfo->total_alljobcounts);
	if (qinfo->total_group_counts != NULL)
		free_counts_list(qinfo->total_group_counts);
	if (qinfo->total_project_counts != NULL)
		free_counts_list(qinfo->total_project_counts);
	if (qinfo->total_user_counts != NULL)
		free_counts_list(qinfo->total_user_counts);
	if (qinfo->nodepart != NULL)
		free_node_partition_array(qinfo->nodepart);
	if (qinfo->allpart != NULL)
		free_node_partition(qinfo->allpart);
	if (qinfo->node_group_key != NULL)
		free_string_array(qinfo->node_group_key);

	if (qinfo->liminfo != NULL) {
		lim_free_liminfo(qinfo->liminfo);
		qinfo->liminfo = NULL;
	}
	if (qinfo->partition != NULL)
		free(qinfo->partition);

	free(qinfo);
}

/**
 * @brief
 *		dup_queues - duplicate the queues on a server
 *
 * @param[in]	oqueues	-	the queues to duplicate
 * @param[in]	nsinfo	-	the new server
 *
 * @return	the duplicated queue array
 *
 */
queue_info **
dup_queues(queue_info **oqueues, server_info *nsinfo)
{
	queue_info **new_queues;
	int i;

	if (oqueues == NULL)
		return NULL;

	if ((new_queues = (queue_info **) malloc(
		(nsinfo->num_queues + 1) * sizeof(queue_info*))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	for (i = 0; oqueues[i] != NULL; i++) {
		if ((new_queues[i] = dup_queue_info(oqueues[i], nsinfo)) == NULL) {
			free_queues(new_queues);
			return NULL;
		}
	}

	new_queues[i] = NULL;

	return new_queues;
}

/**
 * @brief
 *		dup_queue_info - duplicate a queue_info structure
 *
 * @param[in]	oqinfo	-	the queue_info to copy
 * @param[in]	nsinfo	-	the server which owns the duplicated queue
 *
 * @return	duplicated queue_info struct
 * @retval	NULL	: on error
 *
 */
queue_info *
dup_queue_info(queue_info *oqinfo, server_info *nsinfo)
{
	queue_info *nqinfo;

	if ((nqinfo = new_queue_info(0)) == NULL)
		return NULL;

	nqinfo->name = string_dup(oqinfo->name);
	nqinfo->server = nsinfo;

	nqinfo->is_started = oqinfo->is_started;
	nqinfo->is_exec = oqinfo->is_exec;
	nqinfo->is_route = oqinfo->is_route;
	nqinfo->is_ok_to_run = oqinfo->is_ok_to_run;
	nqinfo->is_ded_queue = oqinfo->is_ded_queue;
	nqinfo->is_prime_queue = oqinfo->is_prime_queue;
	nqinfo->is_nonprime_queue = oqinfo->is_nonprime_queue;
	nqinfo->has_nodes = oqinfo->has_nodes;
	nqinfo->has_soft_limit = oqinfo->has_soft_limit;
	nqinfo->has_hard_limit = oqinfo->has_hard_limit;
	nqinfo->is_peer_queue = oqinfo->is_peer_queue;
	nqinfo->has_resav_limit = oqinfo->has_resav_limit;
	nqinfo->has_user_limit = oqinfo->has_user_limit;
	nqinfo->has_grp_limit = oqinfo->has_grp_limit;
	nqinfo->has_proj_limit = oqinfo->has_proj_limit;
	nqinfo->has_all_limit = oqinfo->has_all_limit;
	nqinfo->sc = oqinfo->sc;
	nqinfo->liminfo = lim_dup_liminfo(oqinfo->liminfo);
	nqinfo->priority = oqinfo->priority;
	nqinfo->num_parts = oqinfo->num_parts;
	nqinfo->num_topjobs = oqinfo->num_topjobs;
	nqinfo->backfill_depth = oqinfo->backfill_depth;
#ifdef	NAS
	/* localmod 046 */
	nqinfo->max_starve = oqinfo->max_starve;
	/* localmod 034 */
	nqinfo->max_borrow = oqinfo->max_borrow;
	/* localmod 038 */
	nqinfo->is_topjob_set_aside = oqinfo->is_topjob_set_aside;
	/* localmod 040 */
	nqinfo->ignore_nodect_sort = oqinfo->ignore_nodect_sort;
#endif

	nqinfo->qres = dup_resource_list(oqinfo->qres);
	nqinfo->alljobcounts = dup_counts_list(oqinfo->alljobcounts);
	nqinfo->group_counts = dup_counts_list(oqinfo->group_counts);
	nqinfo->project_counts = dup_counts_list(oqinfo->project_counts);
	nqinfo->user_counts = dup_counts_list(oqinfo->user_counts);
	nqinfo->total_alljobcounts = dup_counts_list(oqinfo->total_alljobcounts);
	nqinfo->total_group_counts = dup_counts_list(oqinfo->total_group_counts);
	nqinfo->total_project_counts = dup_counts_list(oqinfo->total_project_counts);
	nqinfo->total_user_counts = dup_counts_list(oqinfo->total_user_counts);
	nqinfo->nodepart = dup_node_partition_array(oqinfo->nodepart, nsinfo);
	nqinfo->allpart = dup_node_partition(oqinfo->allpart, nsinfo);
	nqinfo->node_group_key = dup_string_arr(oqinfo->node_group_key);

	if (oqinfo->resv != NULL) {
		nqinfo->resv = find_resource_resv_by_indrank(nsinfo->resvs, oqinfo->resv->resresv_ind, oqinfo->resv->rank);
		if (!nqinfo->resv->resv->is_standing) {
			/* just incase we we didn't set the reservation cross pointer */
			nqinfo->resv->resv->resv_queue = nqinfo;
		} else {
			/* For standing reservations, we need to restore the resv_queue pointers for all occurrences */
			int i;
			for(i = 0; nqinfo->server->resvs[i] != NULL; i++) {
				if (!strcmp(nqinfo->server->resvs[i]->name, nqinfo->resv->name))
					nqinfo->server->resvs[i]->resv->resv_queue = nqinfo;
			}
		}
	}
	nqinfo->jobs = dup_resource_resv_array(oqinfo->jobs,
		nqinfo->server, nqinfo);

	if (nqinfo->jobs != NULL)
		nqinfo->running_jobs = resource_resv_filter(nqinfo->jobs,
			nqinfo->sc.total, check_run_job, NULL, 0);

	if (oqinfo->nodes != NULL)
		nqinfo->nodes = node_filter(nsinfo->nodes, nsinfo->num_nodes,
			node_queue_cmp, (void *) nqinfo->name, 0);

	if (oqinfo->partition != NULL) {
		nqinfo->partition = string_dup(oqinfo->partition);
		if (nqinfo->partition == NULL) {
			free_queue_info(nqinfo);
			return NULL;
		}
	}

	return nqinfo;
}

/**
 * @brief
 * 		find a queue by name
 *
 * @param[in]	qinfo_arr	-	the array of queues to look in
 * @param[in]	name	-	the name of the queue
 *
 * @return	the found queue
 * @retval	NULL	: error.
 *
 */
queue_info *
find_queue_info(queue_info **qinfo_arr, char *name)
{
	int i;

	if (qinfo_arr == NULL)
		return NULL;

	for (i = 0; qinfo_arr[i] != NULL && strcmp(name, qinfo_arr[i]->name); i++)
		;

	/* either we have found our queue or the NULL sentinal value */
	return qinfo_arr[i];
}

/**
 * @brief
 *		node_queue_cmp - used with node_filter to filter nodes attached to a
 *		         specific queue
 *
 * @param[in]	node	-	the node we're currently filtering
 * @param[in]	arg	-	the name of the queue
 *
 * @return	int
 * @return	1	: keep the node
 * @return	0	: don't keep the node
 *
 */
int
node_queue_cmp(node_info *ninfo, void *arg)
{
	if (ninfo->queue_name != NULL)
		if (!strcmp(ninfo->queue_name,  (char *) arg))
			return 1;

	return 0;
}

/**
 * @brief
 *      queue_in_partition	-  Tells whether the given node belongs to this scheduler
 *
 * @param[in]	qinfo		-  queue information
 * @param[in]	partition	-  partition associated to scheduler
 *
 * @return	a node_info filled with information from node
 *
 * @return	int
 * @retval	1	: if success
 * @retval	0	: if failure
 */
int
queue_in_partition(queue_info *qinfo, char *partition)
{
	if (dflt_sched) {
		if (qinfo->partition == NULL || (strcmp(qinfo->partition, DEFAULT_PARTITION) == 0))
			return 1;
		else
			return 0;
	}
	if (qinfo->partition == NULL)
		return 0;

	if (strcmp(partition, qinfo->partition) == 0)
		return 1;
	else
		return 0;
}

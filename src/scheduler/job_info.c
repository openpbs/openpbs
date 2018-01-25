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
 * @file    job_info.c
 *
 * @brief
 * 		job_info.c - This file contains functions related to job_info structure.
 *
 * Functions included are:
 * 	query_jobs()
 * 	query_job()
 * 	new_job_info()
 * 	free_job_info()
 * 	set_job_state()
 * 	update_job_attr()
 * 	send_job_updates()
 * 	send_attr_updates()
 * 	unset_job_attr()
 * 	update_job_comment()
 * 	update_jobs_cant_run()
 * 	translate_fail_code()
 * 	dup_job_info()
 * 	preempt_job_set_filter()
 * 	get_preemption_order()
 * 	preempt_job()
 * 	find_and_preempt_jobs()
 * 	find_jobs_to_preempt()
 * 	select_index_to_preempt()
 * 	preempt_level()
 * 	set_preempt_prio()
 * 	create_subjob_name()
 * 	create_subjob_from_array()
 * 	update_array_on_run()
 * 	is_job_array()
 * 	modify_job_array_for_qrun()
 * 	queue_subjob()
 * 	formula_evaluate()
 * 	make_eligible()
 * 	make_ineligible()
 * 	update_accruetype()
 * 	getaoename()
 * 	job_starving()
 * 	mark_job_starving()
 * 	mark_job_preempted()
 * 	update_estimated_attrs()
 * 	check_preempt_targets_for_none()
 * 	is_finished_job()
 * 	preemption_similarity()
 * 	geteoename()
 *
 */
#include <pbs_config.h>

#ifdef PYTHON
#include <Python.h>
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>
#include <sys/types.h>
#include <math.h>
#include <pbs_ifl.h>
#include <log.h>
#include <libutil.h>
#include <pbs_share.h>
#include <pbs_internal.h>
#include <pbs_error.h>
#include "queue_info.h"
#include "job_info.h"
#include "resv_info.h"
#include "constant.h"
#include "misc.h"
#include "config.h"
#include "globals.h"
#include "fairshare.h"
#include "node_info.h"
#include "check.h"
#include "sort.h"
#include "fifo.h"
#include "range.h"
#include "resource_resv.h"
#include "limits_if.h"
#include "simulate.h"
#include "resource.h"
#include "server_info.h"
#include "attribute.h"

#ifdef NAS
#include "site_code.h"
#include "site_queue.h"
#endif


extern char *pbse_to_txt(int err);

/**
 *	This table contains job comment and information messages that correspond
 *	to the sched_error enums in "constant.h".  The order of the strings in
 *	the table must match the numeric order of the sched_error enum values.
 *	The length of the resultant strings (including any arguments inserted
 *	via % formatting directives by translate_fail_code(), q.v.) must not
 *	exceed the dimensions of the schd_error elements.  See data_types.h.
 */
struct fc_translation_table {
	char	*fc_comment;	/**< job comment string */
	char	*fc_info;	/**< job error string */
};
static struct fc_translation_table fctt[] = {
	{
		"",
		""
	},
	{	/* SUCCESS */
		"",
		""
	},
	{	/* SCHD_ERROR */
		"Internal Scheduling Error",
		"A scheduling error has occurred"
	},
	{	/* NOT_QUEUED */
		"Job not in queued state",
		"Job is not in queued state"
	},
	{	/* QUEUE_NOT_STARTED */
		"Queue not started.",
		"Queue not started"
	},
	{	/* QUEUE_NOT_EXEC */
		"Queue not an execution queue.",
		"Queue not an execution queue"
	},
	{	/* QUEUE_JOB_LIMIT_REACHED */
		"Queue %s job limit has been reached.",
		"Queue %s job limit reached"
	},
	{	/* SERVER_JOB_LIMIT_REACHED */
		"Server job limit has been reached.",
		"Server job limit reached"
	},
	{	/* SERVER_USER_LIMIT_REACHED */
		"User has reached server running job limit.",
		"Server per-user job limit reached"
	},
	{	/* QUEUE_USER_LIMIT_REACHED */
		"User has reached queue %s running job limit.",
		"Queue %s per-user job limit reached"
	},
	{	/* SERVER_GROUP_LIMIT_REACHED */
		"Group has reached server running limit.",
		"Server per-group limit reached"
	},
	{	/* QUEUE_GROUP_LIMIT_REACHED */
		"Group has reached queue %s running limit.",
		"Queue %s per-group job limit reached"
	},
	{	/* DED_TIME */
		"Dedicated time conflict",
		"Dedicated Time"
	},
	{	/* CROSS_DED_TIME_BOUNDRY */
		"Job would cross dedicated time boundary",
		"Job would not finish before dedicated time"
	},
	{	/* NO_AVAILABLE_NODE */
		"",
		""
	},
	{	/* NOT_ENOUGH_NODES_AVAIL */
		"Not enough of the right type of nodes are available",
		"Not enough of the right type of nodes available"
	},
	{	/* BACKFILL_CONFLICT */
		"Job would interfere with a top job",
		"Job would interfere with a top job"
	},
	{	/* RESERVATION_INTERFERENCE */
		"Job would interfere with a confirmed reservation",
		"Job would interfere with a reservation"
	},
	{	/* PRIME_ONLY */
		"Job will run in primetime only",
		"Job only runs in primetime"
	},
	{	/* NONPRIME_ONLY */
		"Job will run in nonprimetime only",
		"Job only runs in nonprimetime"
	},
	{	/* CROSS_PRIME_BOUNDARY */
		"Job will cross into %s",
		"Job would cross into %s"
	},
	{	/* NODE_NONEXISTENT */
		"Specified %s does not exist: %s",
		"Specified %s does not exist: %s"
	},
	{	/* NO_NODE_RESOURCES */
		"No available resources on nodes",
		"No available resources on nodes"
	},
	{	/* CANT_PREEMPT_ENOUGH_WORK */
		"Can't preempt enough work to run job",
		"Can't preempt enough work to run job"
	},
	{	/* QUEUE_USER_RES_LIMIT_REACHED */
		"Queue %s per-user limit reached on resource %s",
		"Queue %s per-user limit reached on resource %s"
	},
	{	/* SERVER_USER_RES_LIMIT_REACHED */
		"Server per-user limit reached on resource %s",
		"Server per-user limit reached on resource %s"
	},
	{	/* QUEUE_GROUP_RES_LIMIT_REACHED */
		"Queue %s per-group limit reached on resource %s",
		"Queue %s per-group limit reached on resource %s"
	},
	{	/* SERVER_GROUP_RES_LIMIT_REACHED */
		"Server per-group limit reached on resource %s",
		"Server per-group limit reached on resource %s"
	},
	{	/* NO_FAIRSHARES */
		"Job has zero shares for fairshare",
		"Job has zero shares for fairshare"
	},
	{	/* INVALID_NODE_STATE */
		"Node is in an ineligible state: %s",
#ifdef NAS /* localmod 031 */
		"Node is in an ineligible state: %s: %s"
#else
		"Node is in an ineligible state: %s"
#endif /* localmod 031 */
	},
	{	/* INVALID_NODE_TYPE */
		"Node is of an ineligible type: %s",
		"Node is of an ineligible type: %s"
	},
	{	/* NODE_NOT_EXCL */
#ifdef NAS /* localmod 031 */
		"Nodes not available",
#else
		"%s is requesting an exclusive node and node is in use",
#endif /* localmod 031 */
		"%s is requesting an exclusive node and node is in use"
	},
	{	/* NODE_JOB_LIMIT_REACHED */
		"Node has reached job run limit",
		"Node has reached job run limit"
	},
	{	/* NODE_USER_LIMIT_REACHED */
		"Node has reached user run limit",
		"Node has reached user run limit"
	},
	{	/* NODE_GROUP_LIMIT_REACHED */
		"Node has reached group run limit",
		"Node has reached group run limit"
	},
	{	/* NODE_NO_MULT_JOBS */
		"Node can't satisfy a multi-node job",
		"Node can't satisfy a multi-node job"
	},
	{	/* NODE_UNLICENSED */
		"Node has no PBS license",
		"Node has no PBS license"
	},
	{	/* NODE_HIGH_LOAD */
		"Load is above max limit",
		"Load is above max limit"
	},
	{	/* NO_SMALL_CPUSETS */
		"Max number of small cpusets has been reached",
		"Max number of small cpusets has been reached"
	},
	{	/* INSUFFICIENT_RESOURCE */
		"Insufficient amount of resource: %s %s",
		"Insufficient amount of resource: %s %s"
	},
	{	/* RESERVATION_CONFLICT */
		"Job would conflict with reservation or top job",
		"Job would conflict with reservation or top job"
	},
	{	/* NODE_PLACE_PACK */
		"Node ineligible because job requested pack placement and won't fit on node",
		"Node ineligible because job requested pack placement and won't fit on node"
	},
	{	/* NODE_RESV_ENABLE */
		"Node not eligible for advance reservation",
		"Node not eligible for advance reservation"
	},
	{	/* STRICT_ORDERING */
		"Job would break strict sorted order",
		"Job would break strict sorted order"
	},
	{	/* MAKE_ELIGIBLE */
		"",
		""
	},
	{	/* MAKE_INELIGIBLE */
		"",
		""
	},
	{	/* INSUFFICIENT_QUEUE_RESOURCE */
		"Insufficient amount of queue resource: %s %s",
		"Insufficient amount of queue resource: %s %s"
	},
	{	/* INSUFFICIENT_SERVER_RESOURCE */
		"Insufficient amount of server resource: %s %s",
		"Insufficient amount of server resource: %s %s"
	},
	{	/* QUEUE_BYGROUP_JOB_LIMIT_REACHED */
		"Queue %s job limit reached for group %s",
		"Queue %s job limit reached for group %s"
	},
	{	/* QUEUE_BYUSER_JOB_LIMIT_REACHED */
		"Queue %s job limit reached for user %s",
		"Queue %s job limit reached for user %s"
	},
	{	/* SERVER_BYGROUP_JOB_LIMIT_REACHED */
		"Server job limit reached for group %s",
		"Server job limit reached for group %s"
	},
	{	/* SERVER_BYUSER_JOB_LIMIT_REACHED */
		"Server job limit reached for user %s",
		"Server job limit reached for user %s"
	},
	{	/* SERVER_BYGROUP_RES_LIMIT_REACHED */
		"would exceed group %s's limit on resource %s in complex",
		"would exceed group %s's limit on resource %s in complex"
	},
	{	/* SERVER_BYUSER_RES_LIMIT_REACHED */
		"would exceed user %s's limit on resource %s in complex",
		"would exceed user %s's limit on resource %s in complex"
	},
	{	/* QUEUE_BYGROUP_RES_LIMIT_REACHED */
		"would exceed group %s's limit on resource %s in queue %s",
		"would exceed group %s's limit on resource %s in queue %s"
	},
	{	/* QUEUE_BYUSER_RES_LIMIT_REACHED */
		"would exceed user %s's limit on resource %s in queue %s",
		"would exceed user %s's limit on resource %s in queue %s"
	},
	{	/* QUEUE_RESOURCE_LIMIT_REACHED */
		"would exceed overall limit on resource %s in queue %s",
		"would exceed overall limit on resource %s in queue %s"
	},
	{	/* SERVER_RESOURCE_LIMIT_REACHED */
		"would exceed overall limit on resource %s in complex",
		"would exceed overall limit on resource %s in complex"
	},
	{	/* PROV_DISABLE_ON_SERVER */
		"Cannot provision, provisioning disabled on server",
		"Cannot provision, provisioning disabled on server"
	},
	{	/* PROV_DISABLE_ON_NODE */
		"Cannot provision, provisioning disabled on vnode",
		"Cannot provision, provisioning disabled on vnode"
	},
	{	/* AOE_NOT_AVALBL */
		"Cannot provision, requested AOE %s not available on vnode",
		"Cannot provision, requested AOE %s not available on vnode"
	},
	{	/* EOE_NOT_AVALBL */
		"Cannot provision, requested EOE %s not available on vnode",
		"Cannot provision, requested EOE %s not available on vnode"
	},
	{	/* PROV_BACKFILL_CONFLICT */
		"Provisioning for job would interfere with backfill job",
		"Provisioning for job would interfere with backfill job"
	},
	{	/* IS_MULTI_VNODE */
		"Cannot provision, host has multiple vnodes",
		"Cannot provision, host has multiple vnodes"
	},
	{	/* PROV_RESRESV_CONFLICT */
		"Provision conflict with existing job/reservation",
		"Provision conflict with existing job/reservation"
	},
	{	/* RUN_FAILURE */
		"PBS Error: %s",
		"Failed to run: %s (%s)"
	},
	{	/* SET_TOO_SMALL */
		"%s set %s has too few free resources",
		"%s set %s has too few free resources or is too small"
	},
	{	/* CANT_SPAN_PSET */
		"can't fit in the largest placement set, and can't span psets",
		"Can't fit in the largest placement set, and can't span placement sets"
	},
	{   /* NO_FREE_NODES */
		"Not enough free nodes available",
		"Not enough free nodes available"
	},
	{	/* SERVER_PROJECT_LIMIT_REACHED */
		"Project has reached server running limit.",
		"Server per-project limit reached"
	},
	{	/* SERVER_PROJECT_RES_LIMIT_REACHED */
		"Server per-project limit reached on resource %s",
		"Server per-project limit reached on resource %s"
	},
	{	/* SERVER_BYPROJECT_RES_LIMIT_REACHED */
		"would exceed project %s's limit on resource %s in complex",
		"would exceed project %s's limit on resource %s in complex"
	},
	{	/* SERVER_BYPROJECT_JOB_LIMIT_REACHED */
		"Server job limit reached for project %s",
		"Server job limit reached for project %s"
	},
	{	/* QUEUE_PROJECT_LIMIT_REACHED */
		"Project has reached queue %s's running limit.",
		"Queue %s per-project job limit reached"
	},
	{	/* QUEUE_PROJECT_RES_LIMIT_REACHED */
		"Queue %s per-project limit reached on resource %s",
		"Queue %s per-project limit reached on resource %s"
	},
	{	/* QUEUE_BYPROJECT_RES_LIMIT_REACHED */
		"would exceed project %s's limit on resource %s in queue %s",
		"would exceed project %s's limit on resource %s in queue %s"
	},
	{	/* QUEUE_BYPROJECT_JOB_LIMIT_REACHED */
		"Queue %s job limit reached for project %s",
		"Queue %s job limit reached for project %s"
	},
	{	/* NO_TOTAL_NODES */
		"Not enough total nodes available",
		"Not enough total nodes available"
	},
	{     /* INVALID_RESRESV */
		"Invalid Job/Resv %s",
		"Invalid Job/Resv %s"
	},
	{	/* JOB_UNDER_THRESHOLD */
		"Job is under job_sort_formula threshold value",
		"Job is under job_sort_formula threshold value"
#ifdef NAS
	},
	/* localmod 034 */
	{	/* GROUP_CPU_SHARE */
		"Job would exceed mission CPU share",
		"Job would exceed mission CPU share",
	},
	{	/* GROUP_CPU_INSUFFICIENT */
		"Job exceeds total mission share",
		"Job exceeds total mission share",
	},
	/* localmod 998 */
	{	/* RESOURCES_INSUFFICIENT */
		"Too few free resources",
		"Too few free resources",
#endif
	}
};

#define	ERR2COMMENT(code)	(fctt[(code) - RET_BASE].fc_comment)
#define	ERR2INFO(code)		(fctt[(code) - RET_BASE].fc_info)

/**
 * @brief
 * 		create an array of jobs in a specified queue
 *
 * @par NOTE:
 * 		anything reservation related needs to happen in
 *		query_reservations().  Since it is called after us,
 *		reservations aren't available at this point.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	pbs_sd	-	connection to pbs_server
 * @param[in]	qinfo	-	queue to get jobs from
 * @param[in]	pjobs   -	possible job array to add too
 * @param[in]	queue_name	-	the name of the queue to query (local/remote)
 *
 * @return	pointer to the head of a list of jobs
 * @par MT-safe: No
 */
resource_resv **
query_jobs(status *policy, int pbs_sd, queue_info *qinfo, resource_resv **pjobs, char *queue_name)
{
	/* pbs_selstat() takes a linked list of attropl structs which tell it
	 * what information about what jobs to return.  We want all jobs which are
	 * in a specified queue
	 */
	struct attropl opl = { NULL, ATTR_q, NULL, NULL, EQ };
	static struct attropl opl2[2] = { { &opl2[1], ATTR_state, NULL, "Q", EQ},
		{ NULL, ATTR_array, NULL, "True", NE} };

	/* linked list of jobs returned from pbs_selstat() */
	struct batch_status *jobs;

	/* current job in jobs linked list */
	struct batch_status *cur_job;

	/* array of internal scheduler structures for jobs */
	resource_resv **resresv_arr;

	/* current job in resresv_arr array */
	resource_resv *resresv;

	/* number of jobs in resresv_arr */
	int num_jobs = 0;
	/* number of jobs in pjobs */
	int num_prev_jobs;


	/* how starving is a starving job */
	long starve_num;

	/* string to look up a group_info */
	char fairshare_name[100];

	/* used to add the resources_used to resource list */
	resource_req *req;

	schd_error *err;

	int i;
	/* used for pbs_geterrmsg() */
	char *errmsg;

	/* Determine start, end, and duration */
	resource_req *walltime_req = NULL;
	resource_req *soft_walltime_req = NULL;
	time_t start;
	time_t end;
	time_t server_time;
	long duration;

	if (policy == NULL || qinfo == NULL || queue_name == NULL)
		return pjobs;

	opl.value = queue_name;

	if (qinfo->is_peer_queue)
		opl.next = &opl2[0];

	server_time = qinfo->server->server_time;

	/* get jobs from PBS server */
	if ((jobs = pbs_selstat(pbs_sd, &opl, NULL, "S")) == NULL) {
		if (pbs_errno > 0) {
			errmsg = pbs_geterrmsg(pbs_sd);
			if (errmsg == NULL)
				errmsg = "";
			sprintf(log_buffer, "pbs_selstat failed: %s (%d)", errmsg, pbs_errno);
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_NOTICE, "job_info", log_buffer);
		}
		return pjobs;
	}

	/* count the number of new jobs */
	cur_job = jobs;
	while (cur_job != NULL) {
		num_jobs++;
		cur_job = cur_job->next;
	}

	/* if there are previous jobs, count those too */
	num_prev_jobs = count_array((void **)pjobs);
	num_jobs += num_prev_jobs;


	/* allocate enough space for all the jobs and the NULL sentinal */
	if (pjobs != NULL)
		resresv_arr = (resource_resv **)
			realloc(pjobs, sizeof(resource_resv*) * (num_jobs + 1));
	else
		resresv_arr = (resource_resv **)
			malloc(sizeof(resource_resv*) * (num_jobs + 1));

	if (resresv_arr == NULL) {
		log_err(errno, "query_jobs", "Error allocating memory");
		pbs_statfree(jobs);
		return NULL;
	}
	resresv_arr[num_prev_jobs] = NULL;

	cur_job = jobs;
	err = new_schd_error();
	if(err == NULL)
		return NULL;

	for (i = num_prev_jobs; cur_job != NULL; i++) {
		char *selectspec = NULL;
		if ((resresv = query_job(cur_job, qinfo->server, err)) ==NULL) {
			free_schd_error(err);
			pbs_statfree(jobs);
			free_resource_resv_array(resresv_arr);
			return NULL;
		}

		/* do a validity check to see if the job is sane.  If we're peering and
		 * we're not a manager at the remote host, we wont have necessary attribs
		 * like euser and egroup
		 */
		if (resresv->is_invalid || !is_resource_resv_valid(resresv, err) ) {
			schdlogerr(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, resresv->name,
				"Job is invalid - ignoring for this cycle", err);
			/* decrement i because we're about to increment it as part of the for()
			 * header.  We to continue adding valid jobs to our array.  We're
			 * freeing what we allocated and ignoring this job completely.
			 */
			i--;
			free_resource_resv(resresv);
			cur_job = cur_job->next;
			continue;
		}

		resresv->job->queue = qinfo;

#ifdef NAS /* localmod 040 */
		/* we modify nodect to be the same value for all jobs in queues that are
		 * configured to ignore nodect key sorting, for two reasons:
		 * 1. obviously to accomplish ignoring of nodect key sorting
		 * 2. maintain stability of qsort when comparing with a job in a queue that
		 *    does not require nodect key sorting
		 * note that this assumes nodect is used only for sorting
		 */
		if (qinfo->ignore_nodect_sort)
			resresv->job->nodect = 999999;
#endif /* localmod 040 */

		resresv->aoename = getaoename(resresv->select);
		if ((resresv->eoename = geteoename(resresv->select)) != NULL) {
			/* job with a power profile can't be checkpointed or suspended */
			resresv->job->can_checkpoint = 0;
			resresv->job->can_suspend = 0;
		}

		if (resresv->select != NULL && resresv->select->chunks != NULL) {
			/*
			 * Job is invalid if there are no resources in a chunk.  Usually
			 * happens because we strip out resources not in conf.res_to_check
			 */
			int k;
			for (k = 0; resresv->select->chunks[k] != NULL; k++)
				if (resresv->select->chunks[k]->req == NULL) {
					set_schd_error_codes(err, NEVER_RUN, INVALID_RESRESV);
					set_schd_error_arg(err, ARG1, "invalid chunk in select");
					break;
				}
		}
		if (resresv->place_spec->scatter &&
			resresv->select->total_chunks >1)
			resresv->will_use_multinode = 1;

		if (resresv->job->is_queued && resresv->nspec_arr != NULL)
			resresv->job->is_checkpointed = 1;

		/* If we did not wait for mom to start the job (throughput mode),
		 * it is possible that we’re seeing a running job without a start time set.
		 * The stime is set when the mom reports back to the server to say the job is running.
		 */
		if ((resresv->job->is_running) && (resresv->job->stime == UNSPECIFIED))
			resresv->job->stime = server_time + 1;

		/* Assumption: Parent job array will be queried before running subjobs.
		 * This is because the subjobs do not become real jobs until after they are run
		 * If this assumption is ever proven false, nothing bad will really
		 * happen.  This is here for consistencies sake mostly.
		 */
		if(resresv->job->array_id != NULL)
			resresv->job->parent_job = find_resource_resv(resresv_arr, resresv->job->array_id);

		/* For jobs that have an exec_vnode, we create a "select" based
		 * on its exec_vnode.  We do this so if we ever need to run the job 
		 * again, we will replace the job on the exact vnodes/resources it originally used.
		 */
		if (resresv->job->is_suspended && resresv->job->resreleased != NULL)
			/* For jobs that are suspended and have resource_released, the "select" 
			* we create is based off of resources_released instead of the exec_vnode.
			*/
			selectspec = create_select_from_nspec(resresv->job->resreleased);
		else if (resresv->nspec_arr != NULL)
			selectspec = create_select_from_nspec(resresv->nspec_arr);

		if (resresv->nspec_arr != NULL) {
			resresv->execselect = parse_selspec(selectspec);
			free(selectspec);
		}

		/* Find out if it is a shrink-to-fit job.
		 * If yes, set the duration to max walltime.
		 */
		req = find_resource_req(resresv->resreq, getallres(RES_MIN_WALLTIME));
		if (req != NULL) {
			resresv->is_shrink_to_fit = 1;
			/* Set the min duration */
			resresv->min_duration = (time_t) req->amount;
			req = find_resource_req(resresv->resreq, getallres(RES_MAX_WALLTIME));

#ifdef NAS /* localmod 026 */
			/* if no max_walltime is set then we want to look at what walltime
			 * is (if it's set at all) - it may be user-specified, queue default,
			 * queue max, or server max.
			 */
			if (req == NULL) {
				req = find_resource_req(resresv->resreq, getallres(RES_WALLTIME));

				/* if walltime is set, use it if it's greater than min_walltime */
				if (req != NULL && resresv->min_duration > req->amount) {
					req = find_resource_req(resresv->resreq, getallres(RES_MIN_WALLTIME));
				}
			}
#endif /* localmod 026 */
		}

		if ((req == NULL) || (resresv->job->is_running == 1)) {
			soft_walltime_req = find_resource_req(resresv->resreq, getallres(RES_SOFT_WALLTIME));
			walltime_req = find_resource_req(resresv->resreq, getallres(RES_WALLTIME));
			if (soft_walltime_req != NULL)
				req = soft_walltime_req;
			else
				req = walltime_req;
		}

		if (req != NULL)
			duration = (long)req->amount;
		else /* set to virtual job infinity: 5 years */
			duration = JOB_INFINITY;


		if (walltime_req != NULL)
			resresv->hard_duration = (long)walltime_req->amount;
		else if (resresv->min_duration != UNSPECIFIED)
			resresv->hard_duration = resresv->min_duration;
		else
			resresv->hard_duration = JOB_INFINITY;

		if (resresv->job->stime != UNSPECIFIED &&
			!(resresv->job->is_queued || resresv->job->is_suspended) &&
			resresv->ninfo_arr != NULL) {
			start = resresv->job->stime;

			/* if a job is exiting, then its end time can be more closely
			 * estimated by setting it to now + EXITING_TIME
			 */
			if (resresv->job->is_exiting)
				end = server_time + EXITING_TIME;
			/* Normal Case: Job's end is start + duration and it ends in the future */
			else if (start + duration >= server_time)
				end = start + duration;
			/* Duration has been exceeded - either extend soft_walltime or expect the job to be killed */
			else {
				if (soft_walltime_req != NULL) {
					duration = extend_soft_walltime(resresv, server_time);
					if (duration > soft_walltime_req->amount) {
						char timebuf[128];
						convert_duration_to_str(duration, timebuf, 128);
						update_job_attr(pbs_sd, resresv, ATTR_estimated, "soft_walltime", timebuf, NULL, UPDATE_NOW);
					}
				} else /* Job has exceeded its walltime.  It'll soon be killed and be put into the exiting state */
					duration += EXITING_TIME;
				end = start + duration;
			}
			resresv->start = start;
			resresv->end = end;
		}
		resresv->duration = duration;


		if (qinfo->is_peer_queue) {
			resresv->is_peer_ob = 1;
			resresv->job->peer_sd = pbs_sd;
		}

		/* if the fairshare entity was not set by query_job(), then check
		 * if it's 'queue' and if so, set the group info to the queue name
		 */
		if (!strcmp(conf.fairshare_ent, "queue")) {
			if (resresv->server->fairshare !=NULL) {
				resresv->job->ginfo =
					find_alloc_ginfo(qinfo->name, resresv->server->fairshare->root);
			}
			else
				resresv->job->ginfo = NULL;
		}

		/* if fairshare_ent is invalid or the job doesn't have one, give a default
		 * of something most likely unique - egroup:euser
		 */

		if (resresv->job->ginfo ==NULL) {
#ifdef NAS /* localmod 058 */
			sprintf(fairshare_name, "%s:%s:%s", resresv->group, resresv->user,
				(qinfo->name != NULL ? qinfo->name : ""));
#else
			sprintf(fairshare_name, "%s:%s", resresv->group, resresv->user);
#endif /* localmod 058 */
			if (resresv->server->fairshare !=NULL) {
				resresv->job->ginfo = find_alloc_ginfo(fairshare_name,
					resresv->server->fairshare->root);
			}
			else
				resresv->job->ginfo = NULL;
		}
#ifdef NAS /* localmod 034 */
		if (resresv->job->sh_info == NULL) {
			sprintf(fairshare_name, "%s:%s", resresv->group, resresv->user);
			resresv->job->sh_info = site_find_alloc_share(resresv->server,
								      fairshare_name);
		}
		site_set_share_type(resresv->server, resresv);
#endif /* localmod 034 */

		/* if the job's fairshare entity has no percentage of the machine,
		 * the job can not run if enforce_no_shares is set
		 */
		if (policy->fair_share && conf.enforce_no_shares) {
			if (resresv->job->ginfo != NULL &&
			resresv->job->ginfo->tree_percentage == 0) {
				set_schd_error_codes(err, NEVER_RUN, NO_FAIRSHARES);
			}
		}

		/* add the resources_used and the resource_list together.  If the resource
		 * request is not tracked via resources_used, it's most likely a static
		 * resource like a license which is used for the duration of the job.
		 * Since the first resource found in the list is returned in the find
		 * function, if it's in both lists, the one in resources_used will be
		 * returned first
		 */
		req = resresv->job->resused;

		if (req != NULL) {
			while (req->next != NULL)
				req = req->next;

			req->next = dup_resource_req_list(resresv->resreq);
		}
#ifdef NAS /* localmod 034 */
		site_set_job_share(resresv);
#endif /* localmod 034 */

		starve_num = job_starving(policy, resresv);
		if (starve_num)
			mark_job_starving(resresv, starve_num);

		/* Don't consider a job not in a queued state as runnable */
		if (!in_runnable_state(resresv))
			resresv->can_not_run = 1;

#ifdef RESC_SPEC
		/* search_for_rescspec() sets jinfo->rspec */
		if (!search_for_rescspec(resresv, qinfo->server->nodes))
			set_schd_error_codes(err, NOT_RUN, NO_NODE_RESOURCES);
#endif

		if (err->error_code != SUCCESS) {
			update_job_can_not_run(pbs_sd, resresv, err);
			clear_schd_error(err);
		}

		resresv_arr[i] = resresv;
		resresv_arr[i+1] = NULL;	/* Make array searchable */

		cur_job = cur_job->next;
	}
	resresv_arr[i] = NULL;

	pbs_statfree(jobs);
	free_schd_error(err);

	return resresv_arr;
}

/**
 * @brief
 *		query_job - takes info from a batch_status about a job and
 *			 converts it into a resource_resv struct
 *
 *	  @param[in] job - batch_status struct of job
 *	  @param[in] qinfo - queue where job resides
 *	  @param[out] err - returns error info
 *
 *	@return resource_resv
 *	@retval job (may be invalid, if so, err will report why)
 *	@retval  or NULL on error
 */

resource_resv *
query_job(struct batch_status *job, server_info *sinfo, schd_error *err)
{
	resource_resv *resresv;		/* converted job */
	struct attrl *attrp;		/* list of attributes returned from server */
	int count;			/* int used in string->int conversion */
	char *endp;			/* used for strtol() */
	resource_req *resreq;		/* resource_req list for resources requested  */

	if ((resresv = new_resource_resv()) == NULL)
		return NULL;

	if ((resresv->job = new_job_info()) ==NULL) {
		free_resource_resv(resresv);
		return NULL;
	}

	resresv->name = string_dup(job->name);
	resresv->rank = get_sched_rank();

	attrp = job->attribs;

	resresv->server = sinfo;

	resresv->is_job = 1;

	resresv->job->can_checkpoint = 1;	/* default can be checkpointed */
	resresv->job->can_requeue = 1;		/* default can be requeued */
	resresv->job->can_suspend = 1;		/* default can be suspended */

	/* A Job identifier must be of the form <numeric>.<alpha> or
	 * <numeric>[<numeric>].<alpha> in the case of job arrays, any other
	 * form is considered malformed
	 */
	resresv->job->job_id = strtol(resresv->name, &endp, 10);
	if ((*endp != '.') && (*endp != '[')) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "Malformed job identifier");
		resresv->is_invalid = 1;
	}

	while (attrp != NULL && !resresv->is_invalid) {
		clear_schd_error(err);
		if (!strcmp(attrp->name, conf.fairshare_ent)) {
			if (sinfo->fairshare != NULL) {
#ifdef NAS /* localmod 059 */
				/* This is a hack to allow -A specification for testing, but
				 * ignore most incorrect user -A values
				 */
				if (strchr(attrp->value, ':') != NULL) {
					/* moved to query_jobs() in order to include the queue name
					 resresv->job->ginfo = find_alloc_ginfo( attrp->value,
					 sinfo->fairshare->root );
					 */
					/* localmod 034 */
					resresv->job->sh_info = site_find_alloc_share(sinfo,
						attrp->value);
				}
#else
				resresv->job->ginfo = find_alloc_ginfo(attrp->value,
					sinfo->fairshare->root);
#endif /* localmod 059 */
			}
			else
				resresv->job->ginfo = NULL;
		}
		if (!strcmp(attrp->name, ATTR_p)) { /* priority */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\n')
				resresv->job->priority = count;
			else
				resresv->job->priority = -1;
#ifdef NAS /* localmod 045 */
			resresv->job->NAS_pri = resresv->job->priority;
#endif /* localmod 045 */
		}
		else if (!strcmp(attrp->name, ATTR_qtime)) { /* queue time */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\n')
				resresv->qtime = count;
			else
				resresv->qtime = -1;
		}
		else if (!strcmp(attrp->name, ATTR_qrank)) { /* queue rank */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				resresv->qrank = count;
			else
				resresv->qrank = -1;
		}
		else if (!strcmp(attrp->name, ATTR_etime)) { /* eligible time */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\n')
				resresv->job->etime = count;
			else
				resresv->job->etime = -1;
		}
		else if (!strcmp(attrp->name, ATTR_stime)) { /* job start time */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\n')
				resresv->job->stime = count;
			else
				resresv->job->stime = -1;
		}
		else if (!strcmp(attrp->name, ATTR_N))		/* job name (qsub -N) */
			resresv->job->job_name = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_state)) { /* state of job */
			if (set_job_state(attrp->value, resresv->job) == 0) {
				set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
				set_schd_error_arg(err, SPECMSG, "Job is in an invalid state");
				resresv->is_invalid = 1;
			}
		}
		else if (!strcmp(attrp->name, ATTR_substate)) {
			if (!strcmp(attrp->value, SUSP_BY_SCHED_SUBSTATE))
				resresv->job->is_susp_sched = 1;
			if (!strcmp(attrp->value, PROVISIONING_SUBSTATE))
				resresv->job->is_provisioning = 1;
		}
		else if (!strcmp(attrp->name, ATTR_sched_preempted)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\n') {
				resresv->job->time_preempted = count;
				resresv->job->is_preempted = 1;
			}
		}
		else if (!strcmp(attrp->name, ATTR_comment))	/* job comment */
			resresv->job->comment = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_released)) /* resources_released */
			resresv->job->resreleased = parse_execvnode(attrp->value, sinfo);
		else if (!strcmp(attrp->name, ATTR_euser))	/* account name */
			resresv->user = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_egroup))	/* group name */
			resresv->group = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_project))	/* project name */
			resresv->project = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_resv_ID))	/* reserve_ID */
			resresv->job->resv_id = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_altid))    /* vendor ID */
			resresv->job->alt_id = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_SchedSelect))
#ifdef NAS /* localmod 031 */
		{
			resresv->job->schedsel = string_dup(attrp->value);
#endif /* localmod 031 */

			resresv->select = parse_selspec(attrp->value);
#ifdef NAS /* localmod 031 */
		}
#endif /* localmod 031 */
		else if (!strcmp(attrp->name, ATTR_array_id))
			resresv->job->array_id = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_node_set))
			resresv->node_set_str = break_comma_list(attrp->value);
		else if (!strcmp(attrp->name, ATTR_array)) { /* array */
			if (!strcmp(attrp->value, ATR_TRUE))
				resresv->job->is_array = 1;
		}
		else if (!strcmp(attrp->name, ATTR_array_index)) { /* array_index */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\n')
				resresv->job->array_index = count;
			else
				resresv->job->array_index = -1;

			resresv->job->is_subjob = 1;
		}
		else if (!strcmp(attrp->name, ATTR_topjob_ineligible)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				resresv->job->topjob_ineligible = 1;
		}
		/* array_indices_remaining */
		else if (!strcmp(attrp->name, ATTR_array_indices_remaining))
			resresv->job->queued_subjobs = range_parse(attrp->value);
		else if (!strcmp(attrp->name, ATTR_execvnode)) { /* where job is running*/
			/*
			 * An execvnode may have a vnode chunk in it multiple times.
			 * parse_execvnode() will return us a nspec array with a nspec per
			 * chunk.  The rest of the scheduler expects one nspec per vnode.
			 * This combining of vnode chunks is the job of combine_nspec_array().
			 */
			resresv->nspec_arr = parse_execvnode(attrp->value, sinfo);
			combine_nspec_array(resresv->nspec_arr);

			if (resresv->nspec_arr != NULL)
				resresv->ninfo_arr = create_node_array_from_nspec(resresv->nspec_arr);
		}
		else if (!strcmp(attrp->name, ATTR_l)) { /* resources requested*/
			resreq = find_alloc_resource_req_by_str(resresv->resreq, attrp->resource);
			if (resreq == NULL) {
				free_resource_resv(resresv);
				return NULL;
			}

			if (set_resource_req(resreq, attrp->value) != 1) {
				set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
				set_schd_error_arg(err, SPECMSG, "Bad requested resource data");
				resresv->is_invalid = 1;
			} else {
				if (resresv->resreq == NULL)
					resresv->resreq = resreq;
#ifdef NAS
				if (!strcmp(attrp->resource, "nodect")) { /* nodect for sort */
					/* localmod 040 */
					count = strtol(attrp->value, &endp, 10);
					if (*endp != '\n')
						resresv->job->nodect = count;
					else
						resresv->job->nodect = 0;
					/* localmod 034 */
					resresv->job->accrue_rate = resresv->job->nodect; /* XXX should be SBU rate */
				}
#endif
				if (!strcmp(attrp->resource, "place")) {
					resresv->place_spec = parse_placespec(attrp->value);
					if (resresv->place_spec == NULL) {
						set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
						set_schd_error_arg(err, SPECMSG, "invalid placement spec");
						resresv->is_invalid = 1;

					}
				}
			}
		}
		else if (!strcmp(attrp->name, ATTR_rel_list)) {
			resreq = find_alloc_resource_req_by_str(resresv->job->resreq_rel, attrp->resource);
			if (resreq != NULL)
				set_resource_req(resreq, attrp->value);
			if (resresv->job->resreq_rel == NULL)
				resresv->job->resreq_rel = resreq;
		}
		else if (!strcmp(attrp->name, ATTR_used)) { /* resources used */
			resreq =
				find_alloc_resource_req_by_str(resresv->job->resused, attrp->resource);
			if (resreq != NULL)
				set_resource_req(resreq, attrp->value);
			if (resresv->job->resused ==NULL)
				resresv->job->resused = resreq;
		}
		else if (!strcmp(attrp->name, ATTR_accrue_type)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\n')
				resresv->job->accrue_type = count;
			else
				resresv->job->accrue_type = 0;
		}
		else if (!strcmp(attrp->name, ATTR_eligible_time))
			resresv->job->eligible_time = (time_t) res_to_num(attrp->value, NULL);
		else if (!strcmp(attrp->name, ATTR_estimated)) {
			if (!strcmp(attrp->resource, "start_time")) {
				resresv->job->est_start_time =
					(time_t) res_to_num(attrp->value, NULL);
			}
			else if (!strcmp(attrp->resource, "execvnode"))
				resresv->job->est_execvnode = string_dup(attrp->value);
		}
		else if (!strcmp(attrp->name, ATTR_c)) { /* checkpoint allowed? */
			if (strcmp(attrp->value, "n") == 0)
				resresv->job->can_checkpoint = 0;
		}
		else if (!strcmp(attrp->name, ATTR_r)) { /* reque allowed ? */
			if (strcmp(attrp->value, ATR_FALSE) == 0)
				resresv->job->can_requeue = 0;
		}

		attrp = attrp->next;
	}

	return resresv;
}

/**
 *	@brief
 *		job_info constructor
 *
 * @return job_info *
 */
job_info *
new_job_info()
{
	job_info *jinfo;

	if ((jinfo = (job_info *) malloc(sizeof(job_info))) == NULL) {
		log_err(errno, "new_job_info", MEM_ERR_MSG);
		return NULL;
	}

	jinfo->is_queued = 0;
	jinfo->is_running = 0;
	jinfo->is_held = 0;
	jinfo->is_waiting = 0;
	jinfo->is_transit = 0;
	jinfo->is_exiting = 0;
	jinfo->is_suspended = 0;
	jinfo->is_susp_sched = 0;
	jinfo->is_userbusy = 0;
	jinfo->is_begin = 0;
	jinfo->is_expired = 0;
	jinfo->is_checkpointed = 0;
	jinfo->accrue_type=0;
	jinfo->eligible_time=0;
	jinfo->can_not_preempt = 0;
	jinfo->topjob_ineligible = 0;

	jinfo->is_starving = 0;
	jinfo->is_array = 0;
	jinfo->is_subjob = 0;

	jinfo->can_checkpoint = 1; /* default can be checkpointed */
	jinfo->can_requeue = 1;	   /* default can be reuqued */
	jinfo->can_suspend = 1;    /* default can be suspended */

	jinfo->is_provisioning = 0;
	jinfo->is_preempted = 0;

	jinfo->job_name = NULL;
	jinfo->comment = NULL;
	jinfo->job_name = NULL;
	jinfo->resv_id = NULL;
	jinfo->alt_id = NULL;
	jinfo->queue = NULL;
	jinfo->resv = NULL;
	jinfo->priority = 0;
	jinfo->etime = UNSPECIFIED;
	jinfo->stime = UNSPECIFIED;
	jinfo->preempt = 0;
	jinfo->preempt_status = 0;
	jinfo->peer_sd = -1;
	jinfo->est_start_time = UNSPECIFIED;
	jinfo->time_preempted = UNSPECIFIED;
	jinfo->est_execvnode = NULL;
	jinfo->resused = NULL;
	jinfo->ginfo = NULL;

	jinfo->array_id = NULL;
	jinfo->array_index = UNSPECIFIED;
	jinfo->queued_subjobs = NULL;
	jinfo->parent_job = NULL;
	jinfo->attr_updates = NULL;
	jinfo->resreleased = NULL;
	jinfo->resreq_rel = NULL;


	jinfo->formula_value = 0.0;

#ifdef RESC_SPEC
	jinfo->rspec = NULL;
#endif

#ifdef NAS
	/* localmod 045 */
	jinfo->NAS_pri = 0;
	/* localmod 034 */
	jinfo->sh_amts = NULL;
	jinfo->sh_info = NULL;
	jinfo->accrue_rate = 0;
	/* localmod 040 */
	jinfo->nodect = 0;
	/* localmod 031 */
	jinfo->schedsel = NULL;
	/* localmod 053 */
	jinfo->u_info = NULL;
#endif

	return jinfo;
}

/**
 *	@brief
 *		job_info destructor
 *
 * @param[in,out]	jinfo	-	Job Info structure to be freed.
 */

void
free_job_info(job_info *jinfo)
{
	if (jinfo->comment != NULL)
		free(jinfo->comment);

	if (jinfo->job_name != NULL)
		free(jinfo->job_name);

	if (jinfo->resv_id != NULL)
		free(jinfo->resv_id);

	if (jinfo->alt_id != NULL)
		free(jinfo->alt_id);

	if (jinfo->est_execvnode != NULL)
		free(jinfo->est_execvnode);

	if (jinfo->array_id != NULL)
		free(jinfo->array_id);

	if (jinfo->queued_subjobs != NULL)
		free_range_list(jinfo->queued_subjobs);

	free_resource_req_list(jinfo->resused);

	free_attrl_list(jinfo->attr_updates);

	free_resource_req_list(jinfo->resreq_rel);

	free_nspecs(jinfo->resreleased);

#ifdef RESC_SPEC
	free_rescspec(jinfo->rspec);
#endif
#ifdef NAS
	/* localmod 034 */
	if (jinfo->sh_amts)
		free(jinfo->sh_amts);

	/* localmod 031 */
	if (jinfo->schedsel)
		free(jinfo->schedsel);
#endif

	free(jinfo);
}


/**
 * @brief
 *		set_job_state - set the state flag in a job_info structure
 *			i.e. the is_* bit
 *
 * @param[in]	state	-	the state
 * @param[in,out]	jinfo	-	the job info structure
 *
 * @return	1	-	if state is successfully set
 * @return	0	-	if state is not set
 */
int
set_job_state(char *state, job_info *jinfo)
{
	if (jinfo == NULL)
		return 0;

	/* turn off all state bits first to make sure only 1 is set at the end */
	jinfo->is_queued = jinfo->is_running = jinfo->is_transit =
		jinfo->is_held = jinfo->is_waiting = jinfo->is_exiting =
		jinfo->is_suspended = jinfo->is_userbusy = jinfo->is_begin =
		jinfo->is_expired = 0;

	switch (state[0]) {
		case 'Q':
			jinfo->is_queued = 1;
			break;

		case 'R':
			jinfo->is_running = 1;
			break;

		case 'T':
			jinfo->is_transit = 1;
			break;

		case 'H':
			jinfo->is_held = 1;
			break;

		case 'W':
			jinfo->is_waiting = 1;
			break;

		case 'E':
			jinfo->is_exiting = 1;
			break;

		case 'S':
			jinfo->is_suspended = 1;
			break;

		case 'U':
			jinfo->is_userbusy = 1;
			break;

		case 'B':
			jinfo->is_begin = 1;
			break;

		case 'X':
			jinfo->is_expired = 1;
			break;

		default:
			return 0;
	}
	return 1;
}

/**
 * @brief
 * 		update job attributes on the server
 *
 * @param[in]	pbs_sd     -	connection to the pbs_server
 * @param[in]	resresv    -	job to update
 * @param[in]	attr_name  -	the name of the attribute to alter
 * @param[in]	attr_resc  -	resource part of the attribute (if any)
 * @param[in]	attr_value -	the value of the attribute to alter (as a str)
 * @param[in]	extra	-	extra attrl attributes to tag along on the alterjob
 * @param[in]	flags	-	UPDATE_NOW - call send_attr_updates() to update the attribute now
 *			     			UPDATE_LATER - attach attribute change to job to be sent all at once
 *							for the job.  NOTE: Only the jobs that are part
 *							of the server in main_sched_loop() will be updated in this way.
 *
 * @retval	1	attributes were updated or successfully attached to job
 * @retval	0	no attributes were updated for a valid reason
 * @retval -1	no attributes were updated for an error
 *
 */
int
update_job_attr(int pbs_sd, resource_resv *resresv, char *attr_name,
	char *attr_resc, char *attr_value, struct attrl *extra, unsigned int flags)
{
	struct attrl *pattr = NULL;
	struct attrl *pattr2 = NULL;
	struct attrl *end;

	if (resresv == NULL  ||
		(attr_name == NULL && attr_value == NULL && extra == NULL))
		return -1;

	if (extra == NULL && (attr_name == NULL || attr_value == NULL))
		return -1;

	if (!resresv->is_job)
		return 0;

	/* if running in simulation then don't update but simulate that we have*/
	if (pbs_sd == SIMULATE_SD)
		return 1;

	/* don't try and update attributes for jobs on peer servers */
	if (resresv->is_peer_ob)
		return 0;

	/* if we've received a SIGPIPE, it means our connection to the server
	 * has gone away.  No need to attempt to contact again
	 */
	if (got_sigpipe)
		return -1;

	if (attr_name == NULL && attr_value == NULL) {
		end = pattr = dup_attrl_list(extra);
		if(pattr == NULL)
			return -1;
	} else {
		pattr = new_attrl();

		if (pattr == NULL)
			return -1;
		pattr->name = string_dup(attr_name);
		pattr->value = string_dup(attr_value);
		pattr->resource = string_dup(attr_resc);
		end = pattr;
		if (extra != NULL) {
			pattr2 = dup_attrl_list(extra);
			if (pattr2 == NULL) {
				free_attrl(pattr);
				return -1;
			}
			pattr->next = pattr2;
			/* extra may have been a list, let's find the end */
			for(end = pattr2; end->next != NULL; end = end ->next)
				;
		}
	}

	if(flags & UPDATE_LATER) {
		end->next = resresv->job->attr_updates;
		resresv->job->attr_updates = pattr;

	}

	if (pattr != NULL && (flags & UPDATE_NOW)) {
		int rc;
		rc = send_attr_updates(pbs_sd, resresv->name, pattr);
		free_attrl_list(pattr);
		return rc;
	}

	return 0;
}

/**
 * @brief
 * 		send delayed job attribute updates for job using send_attr_updates().
 *
 * @par
 * 		The main reason to use this function over a direct send_attr_update()
 *      call is so that the job's attr_updates list gets free'd and NULL'd.
 *      We don't want to send the attr updates multiple times
 *
 * @param[in]	pbs_sd	-	server connection descriptor
 * @param[in]	job	-	job to send attributes to
 *
 * @return	int(ret val from send_attr_updates)
 * @retval	1	- success
 * @retval	0	- failure to update
 */
int send_job_updates(int pbs_sd, resource_resv *job) {
	int rc;

	if(job == NULL)
		return 0;

	rc = send_attr_updates(pbs_sd, job->name, job->job->attr_updates) ;

	free_attrl_list(job->job->attr_updates);
	job->job->attr_updates = NULL;
	return rc;
	}
/**
 * @brief
 * 		send delayed attributes to the server for a job
 *
 * @param[in]	pbs_sd	-	server connection descriptor
 * @param[in]	job_name	-	name of job for pbs_alterjob()
 * @param[in]	pattr	-	attrl list to update on the server
 *
 * @return	int
 * @retval	1	success
 * @retval	0	failure to update
 */
int send_attr_updates(int pbs_sd, char *job_name, struct attrl *pattr) {
	char *errbuf;
	char logbuf[MAX_LOG_SIZE];
	int one_attr = 0;

	if (job_name == NULL || pattr == NULL)
		return 0;

	if (pbs_sd == SIMULATE_SD)
		return 1; /* simulation always successful */


		if (pattr->next == NULL)
			one_attr = 1;

		if (pbs_alterjob(pbs_sd, job_name, pattr, NULL) == 0)
			return 1;
		else {
			if (is_finished_job(pbs_errno) == 1) {
				if (one_attr)
					snprintf(logbuf, MAX_LOG_SIZE, "Failed to update attr \'%s\' = %s, Job already finished", pattr->name, pattr->value);
				else
					snprintf(logbuf, MAX_LOG_SIZE, "Failed to update job attributes, Job already finished");
				schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO,
					job_name, logbuf);
				return 0;
			}
			errbuf = pbs_geterrmsg(pbs_sd);
			if (errbuf == NULL)
				errbuf = "";
			if (one_attr)
				snprintf(logbuf, MAX_LOG_SIZE, "Failed to update attr \'%s\' = %s: %s (%d)", pattr->name, pattr->value, errbuf, pbs_errno);

			else
				snprintf(logbuf, MAX_LOG_SIZE, "Failed to update job attributes: %s (%d)", errbuf, pbs_errno);

			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_SCHED, LOG_WARNING,
				job_name, logbuf);
			return 0;
		}

	return 0;
}

/**
 *	@brief
 *		unset job attributes on the server
 *
 * @param[in]	pbs_sd	-	connection to the pbs_server
 * @param[in]	resresv	-	job to update
 * @param[in]	attr_name	-	the name of the attribute to unset
 * @param[in]	flags	-	UPDATE_NOW : call send_attr_updates() to update the attribute now
 *			     			UPDATE_LATER - attach attribute change to job to be sent all at once
 *							for the job.  NOTE: Only the jobs that are part
 *							of the server in main_sched_loop() will be updated in this way.
 *
 *	@retval	1	: attributes were unset
 *	@retval	0	: no attributes were unset for a valid reason
 *	@retval -1	: no attributes were unset for an error
 *
 */
int
unset_job_attr(int pbs_sd, resource_resv *resresv, char *attr_name, unsigned int flags)
{
	return (update_job_attr(pbs_sd, resresv, attr_name, NULL, "", NULL, flags));

}

/**
 * @brief
 *		update_job_comment - update a job's comment attribute.  If the job's
 *			     comment attr is identical, don't update
 *
 * @param[in]	pbs_sd	-	pbs connection descriptor
 * @param[in]	resresv -	the job to update
 * @param[in]	comment -	the comment string
 *
 * @return	int
 * @retval	1	: if the comment was updated
 * @retval	0	: if not
 *
 */
int
update_job_comment(int pbs_sd, resource_resv *resresv, char *comment) {
	int rc = 0;

	if (resresv == NULL || comment == NULL)
		return 0;

	if (!resresv->is_job || resresv->job ==NULL)
		return 0;

	/* no need to update the job comment if it is the same */
	if (resresv->job->comment == NULL ||
		strcmp(resresv->job->comment, comment)) {
		if (conf.update_comments) {
			rc = update_job_attr(pbs_sd, resresv, ATTR_comment, NULL, comment, NULL, UPDATE_LATER);
			if (rc > 0) {
				if (resresv->job->comment !=NULL)
					free(resresv->job->comment);
				resresv->job->comment = string_dup(comment);
			}
		}
	}
	return rc;
}

/**
 * @brief
 *		update_jobs_cant_run - update an array of jobs which can not run
 *
 * @param[in]	pbs_sd	-	connection to the PBS server
 * @param[in,out]	resresv_arr	-	the array to update
 * @param[in]	start	-	the job which couldn't run
 * @param[in]	comment	-	the comment to update
 * @param[in]	log_msg	-	the message to log for the job
 *
 * @return nothing
 *
 */
void
update_jobs_cant_run(int pbs_sd, resource_resv **resresv_arr,
	resource_resv *start, struct schd_error *err, int start_where)
{
	int i = 0;

	if (resresv_arr == NULL)
		return;

	/* We are not starting at the front of the array, so we need to find the
	 * element to start with.
	 */
	if (start != NULL) {
		for (; resresv_arr[i] != NULL && resresv_arr[i] != start; i++)
			;
	} else
		i = 0;

	if (resresv_arr[i] != NULL) {
		if (start_where == START_BEFORE_JOB)
			i--;
		else if (start_where == START_AFTER_JOB)
			i++;

		for (; resresv_arr[i] != NULL; i++) {
			if (!resresv_arr[i]->can_not_run) {
				update_job_can_not_run(pbs_sd, resresv_arr[i], err);
			}
		}
	}
}

/**
 * @brief
 * 		translate failure codes intoa comment and log message
 *
 * @param[in]	err	-	error reply structure to translate
 * @param[out]	comment_msg	-	translated comment (may be NULL)
 * @param[out]	log_msg	-	translated log message (may be NULL)
 *
 * @return	int
 * @retval	1	: comment and log messages were set
 * @retval	0	: comment and log messages were not set
 *
 */
int
translate_fail_code(schd_error *err, char *comment_msg, char *log_msg)
{
	int rc = 1;
	char *pbse;
	char commentbuf[MAX_LOG_SIZE];
	char *arg1;
	char *arg2;
	char *arg3;
	char *spec;

	if (err == NULL)
		return 0;

	if(err->status_code == SCHD_UNKWN) {
		if(comment_msg != NULL)
			comment_msg[0] = '\0';
		if(log_msg != NULL)
			log_msg[0] = '\0';
		return 0;
	}

	if (err->error_code < RET_BASE) {
		if (err->specmsg != NULL)
			pbse = err->specmsg;
		else
			pbse = pbse_to_txt(err->error_code);

		if (pbse == NULL)
			pbse = "";

		if (comment_msg != NULL)
			snprintf(commentbuf, sizeof(commentbuf), "%s", pbse);
		if (log_msg != NULL)
			snprintf(log_msg, MAX_LOG_SIZE, "%s", pbse);
	}

	arg1 = err->arg1;
	arg2 = err->arg2;
	arg3 = err->arg3;
	spec = err->specmsg;
	if(arg1 == NULL)
		arg1 = "";
	if(arg2 == NULL)
		arg2 = "";
	if(arg3 == NULL)
		arg3 = "";
	if(spec == NULL)
		spec = "";

	switch (err->error_code) {
		case ERR_SPECIAL:

			if (comment_msg != NULL)
				snprintf(commentbuf, sizeof(commentbuf), "%s", spec);
			if (log_msg != NULL)
				snprintf(log_msg, MAX_LOG_SIZE, "%s", spec);
			break;

			/* codes using arg1  */
		case BACKFILL_CONFLICT:
		case CANT_PREEMPT_ENOUGH_WORK:
		case CROSS_DED_TIME_BOUNDRY:
		case DED_TIME:
#ifndef NAS /* localmod 031 */
		case INVALID_NODE_STATE:
#endif /* localmod 031 */
		case INVALID_NODE_TYPE:
		case NODE_GROUP_LIMIT_REACHED:
		case NODE_HIGH_LOAD:
		case NODE_JOB_LIMIT_REACHED:
		case NODE_NOT_EXCL:
		case NODE_NO_MULT_JOBS:
		case NODE_PLACE_PACK:
		case NODE_RESV_ENABLE:
		case NODE_UNLICENSED:
		case NODE_USER_LIMIT_REACHED:
		case NONPRIME_ONLY:
		case NOT_ENOUGH_NODES_AVAIL:
		case NO_FAIRSHARES:
		case NO_NODE_RESOURCES:
		case NO_SMALL_CPUSETS:
		case PRIME_ONLY:
		case QUEUE_GROUP_LIMIT_REACHED:
		case QUEUE_PROJECT_LIMIT_REACHED:
		case QUEUE_JOB_LIMIT_REACHED:
		case QUEUE_NOT_STARTED:
		case QUEUE_USER_LIMIT_REACHED:
		case RESERVATION_CONFLICT:
		case SCHD_ERROR:
		case SERVER_BYGROUP_JOB_LIMIT_REACHED:
		case SERVER_BYPROJECT_JOB_LIMIT_REACHED:
		case SERVER_BYUSER_JOB_LIMIT_REACHED:
		case SERVER_GROUP_LIMIT_REACHED:
		case SERVER_PROJECT_LIMIT_REACHED:
		case SERVER_GROUP_RES_LIMIT_REACHED:
		case SERVER_PROJECT_RES_LIMIT_REACHED:
		case SERVER_JOB_LIMIT_REACHED:
		case SERVER_RESOURCE_LIMIT_REACHED:
		case SERVER_USER_LIMIT_REACHED:
		case SERVER_USER_RES_LIMIT_REACHED:
		case STRICT_ORDERING:
		case PROV_DISABLE_ON_SERVER:
		case PROV_DISABLE_ON_NODE:
		case PROV_BACKFILL_CONFLICT:
		case CANT_SPAN_PSET:
		case IS_MULTI_VNODE:
		case AOE_NOT_AVALBL:
		case EOE_NOT_AVALBL:
		case PROV_RESRESV_CONFLICT:
		case CROSS_PRIME_BOUNDARY:
		case NO_FREE_NODES:
		case NO_TOTAL_NODES:
		case INVALID_RESRESV:
		case JOB_UNDER_THRESHOLD:
#ifdef NAS
			/* localmod 034 */
		case GROUP_CPU_SHARE:
		case GROUP_CPU_INSUFFICIENT:
			/* localmod 998 */
		case RESOURCES_INSUFFICIENT:
#endif
			if (comment_msg != NULL)
				snprintf(commentbuf, sizeof(commentbuf), ERR2COMMENT(err->error_code), arg1);
			if (log_msg != NULL)
				snprintf(log_msg, MAX_LOG_SIZE, ERR2INFO(err->error_code), arg1);
			break;

			/* codes using two arguments */
#ifdef NAS /* localmod 031 */
		case INVALID_NODE_STATE:
#endif /* localmod 031 */
		case QUEUE_BYGROUP_JOB_LIMIT_REACHED:
		case QUEUE_BYPROJECT_JOB_LIMIT_REACHED:
		case QUEUE_BYUSER_JOB_LIMIT_REACHED:
		case QUEUE_GROUP_RES_LIMIT_REACHED:
		case QUEUE_PROJECT_RES_LIMIT_REACHED:
		case QUEUE_USER_RES_LIMIT_REACHED:
		case RUN_FAILURE:
		case NODE_NONEXISTENT:
		case SET_TOO_SMALL:
			if (comment_msg != NULL) {
				snprintf(commentbuf, sizeof(commentbuf), ERR2COMMENT(err->error_code), arg1, arg2);
			}
			if (log_msg != NULL) {
				snprintf(log_msg, MAX_LOG_SIZE, ERR2INFO(err->error_code), arg1, arg2);
			}
			break;
			/* codes using a resource and arg1  */
		case INSUFFICIENT_QUEUE_RESOURCE:
		case INSUFFICIENT_SERVER_RESOURCE:
		case INSUFFICIENT_RESOURCE:
			if (comment_msg != NULL && err->rdef != NULL) {
				snprintf(commentbuf, sizeof(commentbuf), ERR2COMMENT(err->error_code), err->rdef->name,
					arg1);
			}
			if (log_msg != NULL && err->rdef != NULL) {
				snprintf(log_msg, MAX_LOG_SIZE, ERR2INFO(err->error_code), err->rdef->name,
					arg1);
			}
			break;

			/* codes using three arguments (in a weird order) */
		case QUEUE_BYGROUP_RES_LIMIT_REACHED:
		case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
		case QUEUE_BYUSER_RES_LIMIT_REACHED:
			if (comment_msg != NULL) {
				snprintf(commentbuf, sizeof(commentbuf), ERR2COMMENT(err->error_code), arg3, arg2, arg1);
			}
			if (log_msg != NULL) {
				snprintf(log_msg, MAX_LOG_SIZE, ERR2INFO(err->error_code), arg3, arg2, arg1);
			}
			break;

			/* codes using arg1 and arg2  in a different order */
		case QUEUE_RESOURCE_LIMIT_REACHED:
		case SERVER_BYGROUP_RES_LIMIT_REACHED:
		case SERVER_BYPROJECT_RES_LIMIT_REACHED:
		case SERVER_BYUSER_RES_LIMIT_REACHED:
			if (comment_msg != NULL) {
				snprintf(commentbuf, sizeof(commentbuf), ERR2COMMENT(err->error_code), arg2,
					arg1);
			}
			if (log_msg != NULL) {
				snprintf(log_msg, MAX_LOG_SIZE, ERR2INFO(err->error_code), arg2,
					arg1);
			}
			break;

		case RESERVATION_INTERFERENCE:
			if (*arg1 !='\0') {
				if (comment_msg != NULL) {
					sprintf(commentbuf, "%s: %s",
						ERR2COMMENT(err->error_code), arg1);
				}
				if (log_msg != NULL) {
					snprintf(log_msg, MAX_LOG_SIZE, "%s: %s",
						ERR2INFO(err->error_code), arg1);
				}
			}
			else  {
				if (comment_msg != NULL)
					snprintf(commentbuf, sizeof(commentbuf), "%s", ERR2COMMENT(err->error_code));
				if (log_msg != NULL)
					snprintf(log_msg, MAX_LOG_SIZE, "%s", ERR2INFO(err->error_code));
			}
			break;

		case NOT_QUEUED:
		default:
			rc = 0;
			if (comment_msg != NULL)
				commentbuf[0] = '\0';
			if (log_msg != NULL)
				log_msg[0] = '\0';
	}

	if (comment_msg != NULL) {
		/* snprintf() use MAX_LOG_SIZE because all calls to this function
		 * pass in comment_msg buffers of size MAX_LOG_SIZE.  This needs to be
		 * fixed by passing in the size of comment_msg and log_msg (SPID268659)
		 */
		switch (err->status_code) {
			case SCHD_UNKWN:
			case NOT_RUN:
				snprintf(comment_msg, MAX_LOG_SIZE, "%s: %s", NOT_RUN_PREFIX, commentbuf);
				break;
			case NEVER_RUN:
				snprintf(comment_msg, MAX_LOG_SIZE, "%s: %s", NEVER_RUN_PREFIX, commentbuf);
				break;
			default:
				strcpy(comment_msg, commentbuf);
		}
	}

	return rc;
}

/**
 * @brief resresv_set constructor
 */
resresv_set *
new_resresv_set(void)
{
	resresv_set *rset;

	rset = malloc(sizeof(resresv_set));
	if (rset == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	rset->can_not_run = 0;
	rset->err = NULL;
	rset->user = NULL;
	rset->group = NULL;
	rset->project = NULL;
	rset->partition = NULL;
	rset->place_spec = NULL;
	rset->req = NULL;
	rset->select_spec = NULL;
	rset->qinfo = NULL;
	rset->resresv_arr = NULL;
	rset->num_resresvs = 0;

	return rset;
}
/**
 * @brief resresv_set destructor
 */
void
free_resresv_set(resresv_set *rset) {
	if(rset == NULL)
		return;

	free_schd_error(rset->err);
	free(rset->user);
	free(rset->group);
	free(rset->project);
	free(rset->partition);
	free_selspec(rset->select_spec);
	free_place(rset->place_spec);
	free_resource_req_list(rset->req);
	free(rset->resresv_arr);
	free(rset);
}
/**
 *  @brief resresv_set array destructor
 */
void
free_resresv_set_array(resresv_set **rsets) {
	int i;

	if (rsets == NULL)
		return;

	for(i = 0; rsets[i] != NULL; i++)
		free_resresv_set(rsets[i]);

	free(rsets);
}

/**
 * @brief resresv_set copy constructor
 */
resresv_set *
dup_resresv_set(resresv_set *oset, server_info *nsinfo)
{
	resresv_set *rset;

	if (oset == NULL || nsinfo == NULL)
		return NULL;

	rset = new_resresv_set();
	if (rset == NULL)
		return NULL;

	rset->can_not_run = oset->can_not_run;

	rset->err = dup_schd_error(oset->err);
	if (oset->err != NULL && oset->err == NULL) {
		free_resresv_set(rset);
		return NULL;
	}

	rset->user = string_dup(oset->user);
	if (oset->user != NULL && rset->user == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->group = string_dup(oset->group);
	if (oset->group != NULL && rset->group == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->project = string_dup(oset->project);
	if (oset->project != NULL && rset->project == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->partition = string_dup(oset->partition);
	if (oset->partition != NULL && rset->partition == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->select_spec = dup_selspec(oset->select_spec);
	if (rset->select_spec == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->place_spec = dup_place(oset->place_spec);
	if (rset->place_spec == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->req = dup_resource_req_list(oset->req);
	if (oset->req != NULL && rset->req == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->resresv_arr = copy_resresv_array(oset->resresv_arr, nsinfo->all_resresv);
	if (rset->resresv_arr == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	if(oset->qinfo != NULL)
		rset->qinfo = find_queue_info(nsinfo->queues, oset->qinfo->name);

	rset->num_resresvs = oset->num_resresvs;

	return rset;
}
/**
 * @brief resresv_set array copy constructor
 */
resresv_set **
dup_resresv_set_array(resresv_set **osets, server_info *nsinfo)
{
	int i;
	int len;
	resresv_set **rsets;
	if (osets == NULL || nsinfo == NULL)
		return NULL;

	len = count_array((void **) osets);

	rsets = malloc((len + 1) * sizeof(resresv_set *));
	if (rsets == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	for (i = 0; osets[i] != NULL; i++) {
		rsets[i] = dup_resresv_set(osets[i], nsinfo);
		if (rsets[i] == NULL) {
			free_resresv_set_array(rsets);
			return NULL;
		}
	}
	rsets[i] = NULL;
	return rsets;

}

/**
 * @brief should a resresv_set use the user
 * @param sinfo - server info
 * @retval 1 - yes
 * @retval 0 - no
 */
int
resresv_set_use_user(server_info *sinfo)
{
	if (sinfo == NULL)
		return 0;
	if (sinfo->has_user_limit)
		return 1;


	return 0;
}

/**
 * @brief should a resresv_set use the group
 * @param sinfo - server info
 * @retval 1 - yes
 * @retval 0 - no
 */
int
resresv_set_use_grp(server_info *sinfo)
{
	if (sinfo == NULL)
		return 0;
	if (sinfo->has_grp_limit)
		return 1;


	return 0;
}

/**
 * @brief should a resresv_set use the project
 * @param sinfo - server info
 * @retval 1 - yes
 * @retval 0 - no
 */
int
resresv_set_use_proj(server_info *sinfo)
{
	if (sinfo == NULL)
		return 0;
	if (sinfo->has_proj_limit)
		return 1;


	return 0;
}

/**
 * @brief should a resresv_set use the queue
 * 	A resresv_set should use queue for the following reasons:
 * 	Hard limits	max_run_res, etc
 * 	Soft Limits	max_run_res_soft, etc
 * 	Nodes		Queue has nodes(e.g., node's queue attribute)
 * 	Dedtime queue 	Queue is a dedicated time queue
 * 	Primetime	Queue is a primetime queue
 * 	Non-primetime	Queue is a non-primetime queue
 * 	Resource limits	Queue has resources_available limits
 * 	Reservation	Queue is a reservation queue
 *
 * @param qinfo - the queue
 * @retval 1 - yes
 * @retval 0 - no
 */
int
resresv_set_use_queue(queue_info *qinfo)
{
	if (qinfo == NULL)
		return 0;

	if (qinfo->has_hard_limit || qinfo->has_soft_limit || qinfo->has_nodes ||
	    qinfo->is_ded_queue || qinfo->is_prime_queue || qinfo->is_nonprime_queue ||
	    qinfo->has_resav_limit || qinfo->resv != NULL)
		return 1;

	return 0;
}

/**
 * @brief determine which selspec to use from a resource_resv for a resresv_set
 *
 * @par Jobs that have an execselect are either running or need to be placed
 *	back on the nodes they were originally running on (e.g., suspended jobs).
 *	We need to put them in their own set because they are no longer
 *	requesting the same resources as jobs with the same select spec.
 *	They are requesting the resources on each vnode they are running on.
 *	We don't care about running jobs because the only time they will be
 *	looked at is if they are requeued.  At that point they are back in
 *	the queued state and have the same select spec as they originally did.
 *
 * @return selspec *
 * @retval selspec to use
 * @retval NULL on error
 */
selspec *
resresv_set_which_selspec(resource_resv *resresv)
{
	if(resresv == NULL)
		return NULL;

	if (resresv->job != NULL && !resresv->job->is_running && resresv->execselect != NULL)
		return resresv->execselect;

	return resresv->select;
}

/**
 * @brief create the list of resources to consider when creating the resresv sets
 * @param policy[in] - policy info
 * @param sinfo[in] - server universe
 * @return resdef **
 * @retval array of resdefs for creating resresv_set's resources.
 * @retval NULL on error
 */
resdef **
create_resresv_sets_resdef(status *policy, server_info *sinfo) {
	resdef **defs;
	int ct;
	int i;
	if (policy == NULL || sinfo == NULL)
		return NULL;

	ct = count_array((void **) policy->resdef_to_check);
	/* 6 for ctime, walltime, max_walltime, min_walltime, preempt_targets (maybe), and NULL*/
	defs = malloc((ct+6) * sizeof(resdef *));

	for (i = 0; i < ct; i++)
		defs[i] = policy->resdef_to_check[i];
	defs[i++] = getallres(RES_CPUT);
	defs[i++] = getallres(RES_WALLTIME);
	defs[i++] = getallres(RES_MAX_WALLTIME);
	defs[i++] = getallres(RES_MIN_WALLTIME);
	if(sinfo->preempt_targets_enable)
		defs[i++] = getallres(RES_PREEMPT_TARGETS);
	defs[i] = NULL;

	return defs;
}

/**
 * @brief create a resresv_set based on a resource_resv
 *
 * @param[in] policy - policy info
 * @param[in] sinfo - server info
 * @param[in] resresv - resresv to create resresv set from
 *
 * @return resresv_set **
 * @retval newly created resresv_set
 * @retval NULL on error
 */
resresv_set *
create_resresv_set_by_resresv(status *policy, server_info *sinfo, resource_resv *resresv)
{
	resresv_set *rset;
	if (policy == NULL || resresv == NULL)
		return NULL;

	rset = new_resresv_set();
	if (rset == NULL)
		return NULL;

	if (resresv_set_use_user(sinfo))
		rset->user = string_dup(resresv->user);
	if (resresv_set_use_grp(sinfo))
		rset->group = string_dup(resresv->group);
	if (resresv_set_use_proj(sinfo))
		rset->project = string_dup(resresv->project);

	if (resresv->is_job && resresv->job != NULL) {
		if (resresv->job->queue->partition != NULL)
			rset->partition = string_dup(resresv->job->queue->partition);
	}

	rset->select_spec = dup_selspec(resresv_set_which_selspec(resresv));
	if (rset->select_spec == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	rset->place_spec = dup_place(resresv->place_spec);
	if (rset->place_spec == NULL) {
		free_resresv_set(rset);
		return NULL;
	}
	/* rset->req may be NULL if the intersection of resresv->resreq and policy->equiv_class_resdef is the NULL set */
	rset->req = dup_selective_resource_req_list(resresv->resreq, policy->equiv_class_resdef);

	if (resresv->is_job && resresv->job != NULL) {
		if (resresv_set_use_queue(resresv->job->queue))
			rset->qinfo = resresv->job->queue;
	}

	return rset;
}

/**
 * @brief find the index of a resresv_set by its component parts
 * @par qinfo, user, group, project, or req can be NULL if the resresv_set does not have one
 * @param[in] policy - policy info
 * @param[in] rsets - resresv_sets to search
 * @param[in] user - user name
 * @param[in] group - group name
 * @param[in] project - project name
 * @param[in] sel - select spec
 * @param[in] pl - place spec
 * @param[in] req - list of resources (i.e., qsub -l)
 * @param[in] qinfo - queue
 * @return int
 * @retval index of resresv if found
 * @retval -1 if not found or on error
 */
int
find_resresv_set(status *policy, resresv_set **rsets, char *user, char *group, char *project, char *partition, selspec *sel, place *pl, resource_req *req, queue_info *qinfo)
{
	int i;

	if (rsets == NULL)
		return -1;

	for (i = 0; rsets[i] != NULL; i++) {
		if ((qinfo != NULL && rsets[i]->qinfo == NULL) || (qinfo == NULL && rsets[i]->qinfo != NULL))
			continue;
		if ((qinfo != NULL && rsets[i]->qinfo != NULL) && cstrcmp(qinfo->name, rsets[i]->qinfo->name) != 0)

			continue;
		if ((user != NULL && rsets[i]->user == NULL) || (user == NULL && rsets[i]->user != NULL))
			continue;
		if (user != NULL && cstrcmp(user, rsets[i]->user) != 0)
			continue;

		if ((group != NULL && rsets[i]->group == NULL) || (group == NULL && rsets[i]->group != NULL))
			continue;
		if (group != NULL && cstrcmp(group, rsets[i]->group) != 0)
			continue;

		if ((project != NULL && rsets[i]->project == NULL) || (project == NULL && rsets[i]->project != NULL))
			continue;
		if (project != NULL && cstrcmp(project, rsets[i]->project) != 0)
			continue;

		if ((partition != NULL && rsets[i]->partition == NULL) || (partition == NULL && rsets[i]->partition != NULL))
			continue;
		if (partition != NULL && cstrcmp(partition, rsets[i]->partition) != 0)
			continue;

		if (compare_selspec(rsets[i]->select_spec, sel) == 0)
			continue;
		if (compare_place(rsets[i]->place_spec, pl) == 0)
			continue;
		if (compare_resource_req_list(rsets[i]->req, req, policy->equiv_class_resdef) == 0)
			continue;
		/* If we got here, we have found our set */
		return i;
	}
	return -1;

}

/**
 * @brief find the index of a resresv_set by a resresv inside it
 * @param[in] policy - policy info
 * @param[in] rsets - resresv_set array to search
 * @param[in] resresv - resresv to search for
 * @return index of resresv
 */
int
find_resresv_set_by_resresv(status *policy, resresv_set **rsets, resource_resv *resresv)
{
	char *user = NULL;
	char *grp = NULL;
	char *proj = NULL;
	char *partition = NULL;
	queue_info *qinfo = NULL;
	selspec *sspec;

	if (policy == NULL || rsets == NULL || resresv == NULL)
		return -1;

	if (resresv_set_use_user(resresv->server))
		user = resresv->user;

	if (resresv_set_use_grp(resresv->server))
		grp = resresv->group;

	if (resresv_set_use_proj(resresv->server))
		proj = resresv->project;

	if (resresv->is_job && resresv->job != NULL) {
		if (resresv->job->queue->partition != NULL)
			partition = resresv->job->queue->partition;
	}

	sspec = resresv_set_which_selspec(resresv);

	if (resresv->is_job && resresv->job != NULL)
		if (resresv_set_use_queue(resresv->job->queue))
			qinfo = resresv->job->queue;

	return find_resresv_set(policy, rsets, user, grp, proj, partition, sspec, resresv->place_spec, resresv->resreq, qinfo);
}

/**
 * @brief create equivalence classes based on an array of resresvs
 * @param[in] policy - policy info
 * @param[in] sinfo - server universe
 * @return array of equivalence classes (resresv_sets)
 */
resresv_set **
create_resresv_sets(status *policy, server_info *sinfo)
{
	int i;
	int j = 0;
	int cur_ind;
	int len;
	resource_resv **resresvs;
	resresv_set **rsets;
	resresv_set **tmp_rset_arr;
	resresv_set *cur_rset;

	if (policy == NULL || sinfo == NULL)
		return NULL;

	resresvs = sinfo->jobs;

	len = count_array((void **) resresvs);
	rsets = malloc((len + 1) * sizeof(resresv_set));
	if (rsets == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	rsets[0] = NULL;

	for (i = 0; resresvs[i] != NULL; i++) {
		cur_ind = find_resresv_set_by_resresv(policy, rsets, resresvs[i]);

		/* Didn't find the set, create it.*/
		if (cur_ind == -1) {
			cur_rset = create_resresv_set_by_resresv(policy, sinfo, resresvs[i]);
			if (cur_rset == NULL) {
				free_resresv_set_array(rsets);
				return NULL;
			}
			cur_rset->resresv_arr = malloc((len + 1) * sizeof(resource_resv));
			if (cur_rset->resresv_arr == NULL) {
				log_err(errno, __func__, MEM_ERR_MSG);
				free_resresv_set_array(rsets);
				free_resresv_set(cur_rset);
				return NULL;
			}
			cur_ind = j;
			rsets[j++] = cur_rset;
			rsets[j] = NULL;
		} else
			cur_rset = rsets[cur_ind];

		cur_rset->resresv_arr[cur_rset->num_resresvs] = resresvs[i];
		cur_rset->resresv_arr[++cur_rset->num_resresvs] = NULL;
		resresvs[i]->ec_index = cur_ind;
	}

	/* tidy up */
	for (i = 0; rsets[i] != NULL; i++) {
		resource_resv **tmp_arr;
		tmp_arr = realloc(rsets[i]->resresv_arr, (rsets[i]->num_resresvs + 1) * sizeof(resource_resv *));
		if (tmp_arr != NULL)
			rsets[i]->resresv_arr = tmp_arr;
	}

	tmp_rset_arr = realloc(rsets,(j + 1) * sizeof(resresv_set *));
	if (tmp_rset_arr != NULL)
		rsets = tmp_rset_arr;

	if (i > 0) {
		snprintf(log_buffer, sizeof(log_buffer), "Number of job equivalence classes: %d", i);
		schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, log_buffer);
	}

	return rsets;
}

/**
 * @brief
 * 		job_info copy constructor
 *
 * @param[in]	ojinfo	-	Pointer to JobInfo structure
 * @param[in]	nqinfo	-	Queue Info
 * @param[in]	sinfo	-	Server Info
 *
 * @return	job_info *
 * @retval	NULL	:	when function fails to duplicate job_info
 * @retval	!NULL	:	duplicated job_info structure pointer
 */
job_info *
dup_job_info(job_info *ojinfo, queue_info *nqinfo, server_info *nsinfo)
{
	job_info *njinfo;

	if ((njinfo = new_job_info()) == NULL)
		return NULL;

	njinfo->queue = nqinfo;

	njinfo->is_queued = ojinfo->is_queued;
	njinfo->is_running = ojinfo->is_running;
	njinfo->is_held = ojinfo->is_held;
	njinfo->is_waiting = ojinfo->is_waiting;
	njinfo->is_transit = ojinfo->is_transit;
	njinfo->is_exiting = ojinfo->is_exiting;
	njinfo->is_userbusy = ojinfo->is_userbusy;
	njinfo->is_begin = ojinfo->is_begin;
	njinfo->is_expired = ojinfo->is_expired;
	njinfo->is_suspended = ojinfo->is_suspended;
	njinfo->is_susp_sched = ojinfo->is_susp_sched;
	njinfo->is_starving = ojinfo->is_starving;
	njinfo->is_array = ojinfo->is_array;
	njinfo->is_subjob = ojinfo->is_subjob;
	njinfo->can_not_preempt = ojinfo->can_not_preempt;
	njinfo->topjob_ineligible = ojinfo->topjob_ineligible;
	njinfo->is_checkpointed = ojinfo->is_checkpointed;
	njinfo->is_provisioning = ojinfo->is_provisioning;

	njinfo->can_checkpoint = ojinfo->can_checkpoint;
	njinfo->can_requeue    = ojinfo->can_requeue;
	njinfo->can_suspend    = ojinfo->can_suspend;

	njinfo->priority = ojinfo->priority;
	njinfo->etime = ojinfo->etime;
	njinfo->stime = ojinfo->stime;
	njinfo->preempt = ojinfo->preempt;
	njinfo->preempt_status = ojinfo->preempt_status;
	njinfo->peer_sd = ojinfo->peer_sd;
	njinfo->job_id = ojinfo->job_id;
	njinfo->est_start_time = ojinfo->est_start_time;
	njinfo->formula_value = ojinfo->formula_value;
	njinfo->est_execvnode = string_dup(ojinfo->est_execvnode);
	njinfo->job_name = string_dup(ojinfo->job_name);
	njinfo->comment = string_dup(ojinfo->comment);
	njinfo->resv_id = string_dup(ojinfo->resv_id);
	njinfo->alt_id = string_dup(ojinfo->alt_id);

	if (ojinfo->resv != NULL) {
		njinfo->resv = find_resource_resv_by_rank(nqinfo->server->resvs,
			ojinfo->resv->rank);
	}

	njinfo->resused = dup_resource_req_list(ojinfo->resused);

	njinfo->array_index = ojinfo->array_index;
	njinfo->array_id = string_dup(ojinfo->array_id);
	if(njinfo->parent_job != NULL )
		njinfo->parent_job = find_resource_resv_by_rank(nqinfo->jobs, ojinfo->parent_job->rank);
	njinfo->queued_subjobs = dup_range_list(ojinfo->queued_subjobs);

	njinfo->resreleased = dup_nspecs(ojinfo->resreleased, nsinfo->nodes);
	njinfo->resreq_rel = dup_resource_req_list(ojinfo->resreq_rel);

	if (nqinfo->server->fairshare !=NULL) {
		njinfo->ginfo = find_group_info(ojinfo->ginfo->name,
			nqinfo->server->fairshare->root);
	}
	else
		njinfo->ginfo = NULL;

#ifdef RESC_SPEC
	njinfo->rspec = dup_rescspec(ojinfo->rspec);
#endif

#ifdef NAS
	/* localmod 045 */
	njinfo->NAS_pri = ojinfo->NAS_pri;
	/* localmod 034 */
	njinfo->sh_amts = site_dup_share_amts(ojinfo->sh_amts);
	njinfo->sh_info = ojinfo->sh_info;
	njinfo->accrue_rate = ojinfo->accrue_rate;
	/* localmod 040 */
	njinfo->nodect = ojinfo->nodect;
	/* localmod 031 */
	njinfo->schedsel = string_dup(ojinfo->schedsel);
	/* localmod 053 */
	njinfo->u_info = ojinfo->u_info;
#endif

	return njinfo;
}

/**
 * @brief
 * 		filter function used with resource_resv_filter
 *        create limited running job set for use with preemption.
 *        If there are multiple resources found in preempt_targets
 *        the scheduler will select a preemptable job which satisfies
 *        any one of them.
 *
 * @see	resource_resv_filter()
 *
 * @param[in]	job	-	job to consider to include
 * @param[in]	arg	-	attribute=value pairs criteria for inclusion
 *
 * @retval	int
 * @return	1	: If job falls into one of the preempt_targets
 * @return	0	: If job dos not fall into any of the preempt_targets
 */
int
preempt_job_set_filter(resource_resv *job, void *arg)
{
	resource_req *req;
	char **arglist;
	char *p;
	char *dot;
	int i;

	if (job == NULL || arg == NULL || job->job == NULL ||
		job->job->queue == NULL || job->job->is_running != 1)
		return 0;

	arglist = (char **) arg;

	for (i = 0; arglist[i] != NULL; i++) {
		p = strpbrk(arglist[i], ".=");
		if (p != NULL) {
			/* two valid attributes: queue and Resource_List.<res> */
			if (!strncasecmp(arglist[i], ATTR_queue, p - arglist[i])) {
				if (!strcmp(job->job->queue->name, p+1))
					return 1;
			}
			else if (!strncasecmp(arglist[i], ATTR_l, p - arglist[i])) {
				dot = p;
				p = strpbrk(arglist[i], "=");
				if (p == NULL)
					return 0;
				else {
					*p = '\0';
					req = find_resource_req_by_str(job->resreq, dot+1);
					*p = '=';
					if (req != NULL) {
						if (!strcmp(req->res_str, p+1))
							return 1;
					}
				}
			}
		}
	}
	return 0;
}

/**
 * @brief
 *  	get_preemption_order - deduce the preemption ordering to be used for a job
 *
 * @param[in]	pjob	-	the job to preempt
 * @param[in]	sinfo	-	Pointer to server info structure.
 *
 * @return	: struct preempt_ordering.  array containing preemption order
 *
 */
struct preempt_ordering *get_preemption_order(resource_resv *pjob,
	server_info *sinfo)
{
	/* the order to preempt jobs in */
	struct preempt_ordering *po = &conf.preempt_order[0];
	int i;

	if (pjob == NULL || pjob->job == NULL)
		return 0;

	/* continue validity checks */
	if (!pjob->job->is_running || pjob->ninfo_arr == NULL)
		return 0;

	/* check if we have more then one range... no need to choose if not */
	if (conf.preempt_order[1].high_range != 0) {
		resource_req *req;		/* the jobs requested soft_walltime/walltime/cput */
		resource_req *used;		/* the amount of the walltime/cput used */

		req = find_resource_req(pjob->resreq, getallres(RES_SOFT_WALLTIME));

		if(req == NULL)
			req = find_resource_req(pjob->resreq, getallres(RES_WALLTIME));

		if (req == NULL) {
			req = find_resource_req(pjob->resreq, getallres(RES_CPUT));
			used = find_resource_req(pjob->job->resused, getallres(RES_CPUT));
		}
		else
			used = find_resource_req(pjob->job->resused, getallres(RES_WALLTIME));

		if (req == NULL || used == NULL) {
			schdlog(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO, pjob->name,
				"No walltime/cput to determine percent of time left - will use first "
				"preempt order");
		}
		else {
			float percent_left;
			percent_left = (int)(100 - (used->amount / req->amount) * 100);
			/* if a job has exceeded its soft_walltime, percent_left will be less than 0 */
			if (percent_left < 0)
				percent_left = 1;

			for (i = 0; i < PREEMPT_ORDER_MAX; i++) {
				if (percent_left <= conf.preempt_order[i].high_range &&
					percent_left >= conf.preempt_order[i].low_range)
					po = &conf.preempt_order[i];
			}
		}
	}
	return po;
}


/**
 * @brief
 * 		preempt a job to allow another job to run.  First the
 *		      job will try to be suspended, then checkpointed and
 *		      finally forcablly requeued
 *
 * @param[in] param	-	policy info
 * @param[in] pbs_sd	-	communication descriptor to the PBS server
 *                 			If pbs_sd is < 0 then just simulate through the function
 * @param[in]	pjob	-	the job to preempt
 *
 * @return	int
 * @retval	1	: successfully preempted the job
 * @retval	0	: failure to preempt
 */
int
preempt_job(status *policy, int pbs_sd, resource_resv *pjob, server_info *sinfo)
{
	/* the order to preempt jobs in */
	struct preempt_ordering *po;
	int ret = -1;
	int i;
	int histjob = 0;
	int job_preempted = 0;

	/* used for stating job state */
	struct attrl state = {NULL, ATTR_state, NULL, ""};
	struct batch_status *status;

	/* used for calendar correction */
	timed_event *te;

	if (pjob == NULL || pjob->job == NULL)
		return 0;

	/* continue validity checks */
	if (!pjob->job->is_running || pjob->ninfo_arr == NULL)
		return 0;

	po = get_preemption_order(pjob, sinfo);
	for (i = 0; i < PREEMPT_METHOD_HIGH && pjob->job->is_running; i++) {
		if (po->order[i] == PREEMPT_METHOD_SUSPEND &&
				pjob->job->can_suspend) {
			ret = pbs_sigjob(pbs_sd, pjob->name, "suspend", NULL);
			if ((ret != 0) && (is_finished_job(pbs_errno) == 1)) {
				histjob = 1;
				ret = 0;
			}

			if ((!ret) && (histjob != 1)) {
				update_universe_on_end(policy, pjob, "S");
				pjob->job->is_susp_sched = 1;
				schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO,
					pjob->name, "Job preempted by suspension");
				job_preempted = 1;
			}
		}

		/* try only if checkpointing is enabled */
		if (po->order[i] == PREEMPT_METHOD_CHECKPOINT && pjob->job->can_checkpoint) {
				ret = pbs_holdjob(pbs_sd, pjob->name, "s", NULL);
				if ((ret != 0) && (is_finished_job(pbs_errno) == 1)) {
					histjob = 1;
					ret = 0;
			}
			else
				ret = 0;  /* in simulation, assume success */

			if ((!ret) && (histjob != 1)) {
				if ((status = pbs_statjob(pbs_sd, pjob->name, &state, NULL)) != NULL) {
					/* if the job has been requeued, it was successfully checkpointed */
					if (status->attribs->value[0] =='H') {
						pjob->job->is_checkpointed = 1;
						update_universe_on_end(policy, pjob, "Q");
						schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO,
							pjob->name, "Job preempted by checkpointing");
						job_preempted = 1;
					} else
						ret = -1;

					if (pbs_sd != SIMULATE_SD)
						pbs_statfree(status);
				} else
					ret = -1; /* failure */
			}
			/* in either case, release the hold */
			pbs_rlsjob(pbs_sd, pjob->name, "s", NULL);
		}

		/* try only of requeueing is enabled */
		if (po->order[i] == PREEMPT_METHOD_REQUEUE && pjob->job->can_requeue) {
			ret = pbs_rerunjob(pbs_sd, pjob->name, NULL);
			if ((ret != 0) && (is_finished_job(pbs_errno) == 1)) {
				histjob = 1;
				ret = 0;
			}
			else
				ret = 0;  /* in simulation, assume success */

			if ((!ret) && (histjob != 1)){
			    update_universe_on_end(policy, pjob, "Q");
				schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO,
				    pjob->name, "Job preempted by requeuing");

				job_preempted = 1;
			}
		}
	}

	if (histjob == 1) {
		update_universe_on_end(policy, pjob, "E");
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO,
				pjob->name, "Job already finished");
		histjob = 0;
	}
	if (ret) {
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO, pjob->name, "Job failed to be preempted");
		return 0;
	} else {
		/* we're prematurely ending a job.  We need to correct our calendar */
		if (sinfo->calendar != NULL) {
			te = find_timed_event(sinfo->calendar->events, pjob->name, TIMED_END_EVENT, 0);
			if (te != NULL) {
				if (delete_event(sinfo, te, DE_NO_FLAGS) == 0)
					schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO, pjob->name, "Failed to delete end event for job.");
			}

		}
	}
	if (job_preempted == 1) {
		update_accruetype(pbs_sd, sinfo, ACCRUE_MAKE_ELIGIBLE, SUCCESS, pjob);
		mark_job_preempted(pbs_sd, pjob, sinfo->server_time);
		sinfo->num_preempted++;
	}
	return 1;
}

/**
 * @brief
 * 		find the jobs to preempt and then preempt them
 *
 * @param[in]	policy	-	policy info
 * @param[in]	pbs_sd	-	communication descriptor to the PBS server
 * @param[in]	hjob	-	the high priority job
 * @param[in]	sinfo	-	the server to find jobs to preempt
 * @param[out]	err	-	schd_error to return error from runjob
 *
 * @return	int
 * @retval	1	: success
 * @retval  0	: failure
 * @retval -1	: error
 *
 */
int
find_and_preempt_jobs(status *policy, int pbs_sd, resource_resv *hjob, server_info *sinfo, schd_error *err)
{

	int i;
	int *jobs = NULL;
	resource_resv *job = NULL;
	int ret = -1;
	int done = 0;
	int rc = 1;
	int *preempted_list;
	int preempted_count=0;
	int *fail_list = NULL;
	int fail_count=0;
	int num_tries=0;

	/* jobs with AOE cannot preempt (atleast for now) */
	if (hjob->aoename != NULL)
		return 0;

	/* using calloc - saves the trouble to put NULL at end of list */
	if ((preempted_list = calloc((sinfo->sc.running + 1), sizeof(int))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return -1;
	}

	if ((fail_list = calloc((sinfo->sc.running + 1), sizeof(int))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		free(preempted_list);
		return -1;
	}

	/* loop till done is true, ie, all selected jobs are truely preempted,
	 * or we cant find enough jobs to preempt
	 * or the maximum number of tries has been exhausted
	 */
	while (!done &&
		((jobs = find_jobs_to_preempt(policy, hjob, sinfo, fail_list)) != NULL) &&
		num_tries < MAX_PREEMPT_RETRIES) {
		done = 1;
		for (i = 0 ; jobs[i] != 0; i++) {
			job = find_resource_resv_by_rank(sinfo->running_jobs, jobs[i]);
			if (job != NULL) {
				ret = preempt_job(policy, pbs_sd, job, sinfo);

				if (ret)
					/* copy this job into the preempted array list */
					preempted_list[preempted_count++] = jobs[i];
				else  {
					done = 0; /* preemption failed for some job, need to loop */
					/* add to the fail list */
					fail_list[fail_count++] = jobs[i];
				}
			}
		}
		free(jobs);
		num_tries++;
	}

	if (done) {
		clear_schd_error(err);
		ret = run_update_resresv(policy, pbs_sd, sinfo, hjob->job->queue, hjob, NULL, RURR_ADD_END_EVENT, err);

		/* oops... we screwed up.. the high priority job didn't run.  Forget about
		 * running it now and resume preempted work
		 */
		if (!ret) {
			schd_error *serr;
			serr = new_schd_error();
			if(serr == NULL)
				return -1;
			schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, hjob->name,
				"Preempted work didn't run job - rerun it");
			for (i = 0; i < preempted_count; i++) {
				job = find_resource_resv_by_rank(sinfo->jobs, preempted_list[i]);
				if (job != NULL && !job->job->is_running) {
					clear_schd_error(serr);
					if (run_update_resresv(policy, pbs_sd, sinfo, job->job->queue, job, NULL, RURR_NO_FLAGS, serr) == 0) {
						schdlogerr(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, job->name, "Failed to rerun job:", serr);
					}
				}
			}
			rc = 0;
			free_schd_error_list(serr);
		}
	}
	else if (num_tries == MAX_PREEMPT_RETRIES) {
		rc = 0;
		schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, hjob->name,
			"Maximum number of preemption tries exceeded - cannot run job");
	}
	else
		rc = 0;

	free(preempted_list);
	free(fail_list);
	return rc;
}


/**
 * @brief
 * 		find jobs to preempt in order to run a high priority job.
 *        First we'll check if the reason the job can't run will be helped
 *        if we preempt work (i.e. job won't run because of dedtime) then
 *        we'll simulate preempting jobs to find a list which will work.
 *        We will then go back through the list to find if any work doesn't
 *        need to be preempted.  Finally we'll return the list if we found
 *        one, NULL if not.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	hjob	-	the high priority job
 * @param[in]	sinfo	-	the server of the jobs to preempt
 * @param[in]	fail_list	-	list of jobs which preemption has failed
 *				 				do not attempt to preempt again
 *
 * @return	int *
 * @retval	array of job ranks to preempt
 * @retval	NULL	: error/no jobs
 * @par NOTE:	returned array is allocated with malloc() --  needs freeing
 *
 */
int *
find_jobs_to_preempt(status *policy, resource_resv *hjob, server_info *sinfo, int *fail_list)
{
	int i;
	int j = 0;
	int has_lower_jobs = 0;	/* there are jobs of a lower preempt priority */
	int prev_prio;		/* jinfo's preempt field before simulation */
	server_info *nsinfo;
	resource_resv **rjobs = NULL;	/* the running jobs to choose from */
	resource_resv **pjobs = NULL;	/* jobs to preempt */
	int *pjobs_list = NULL;	/* list of job ids */
	resource_resv *njob = NULL;
	resource_resv *pjob = NULL;
	int rc = 0;
	int retval = 0;
	char buf[MAX_LOG_SIZE];
	char log_buf[MAX_LOG_SIZE];
	nspec **ns_arr = NULL;
	schd_error *err = NULL;

	enum sched_error old_errorcode = SUCCESS;
	char *old_errorarg1 = NULL;
	long indexfound;
	long skipto;

	schd_error *full_err = NULL;
	schd_error *cur_err = NULL;
	timed_event *te = NULL;

	resource_req *preempt_targets_req = NULL;
	char **preempt_targets_list = NULL;
	resource_resv **prjobs = NULL;
	int rjobs_count = 0;


	if (hjob == NULL || sinfo == NULL)
		return NULL;

	/* if the job is in an express queue and there are multiple express queues,
	 * we need see if there are any running jobs who we can preempt.  All
	 * express queues fall into the same preempt level but have different
	 * preempt priorities.
	 */
	if ((hjob->job->preempt_status & PREEMPT_TO_BIT(PREEMPT_EXPRESS)) &&
		sinfo->has_mult_express) {
		for (i = 0; sinfo->running_jobs[i] != NULL && !has_lower_jobs; i++)
			if (sinfo->running_jobs[i]->job->preempt < hjob->job->preempt)
				has_lower_jobs = TRUE;
	}
	else {
		for (i = 0; i < NUM_PPRIO && !has_lower_jobs; i++)
			if (conf.pprio[i][1] < hjob->job->preempt &&
				sinfo->preempt_count[i] > 0)
				has_lower_jobs = TRUE;
	}

	if (has_lower_jobs == FALSE)
		return NULL;

	/* we increment cstat.preempt_attempts when we check, if we only did a
	 * cstat.preempt_attempts > conf.max_preempt_attempts we would actually
	 * attempt to preempt conf.max_preempt_attempts + 1 times
	 */
	if (conf.max_preempt_attempts != SCHD_INFINITY) {
		if (cstat.preempt_attempts >= conf.max_preempt_attempts) {
			schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, hjob->name,
				"Not attempting to preempt: over max cycle preempt limit");
			return NULL;
		}
		else
			cstat.preempt_attempts++;
	}


	schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, hjob->name,
		"Employing preemption to try and run high priority job.");

	/* Let's get all the reasons the job won't run now.
	 * This will help us find the set of jobs to preempt
	 */

	full_err = new_schd_error();
	if(full_err == NULL) {
		return NULL;
	}

	ns_arr = is_ok_to_run(policy, -1, sinfo, hjob->job->queue, hjob, RETURN_ALL_ERR, full_err);

	/* This should be NULL, but just in case */
	free_nspecs(ns_arr);

	/* If a job can't run due to any of these reasons, no amount of preemption will help */
	for (cur_err = full_err; cur_err != NULL; cur_err = cur_err->next) {
		int cant_preempt = 0;
		switch((int) cur_err->error_code)
		{
			case SCHD_ERROR:
			case NOT_QUEUED:
			case QUEUE_NOT_STARTED:
			case QUEUE_NOT_EXEC:
			case DED_TIME:
			case CROSS_DED_TIME_BOUNDRY:
			case PRIME_ONLY:
			case NONPRIME_ONLY:
			case CROSS_PRIME_BOUNDARY:
			case NODE_NONEXISTENT:
			case CANT_SPAN_PSET:
			case RESERVATION_INTERFERENCE:
			case PROV_DISABLE_ON_SERVER:
				cant_preempt = 1;
				break;
		}
		if(cur_err->status_code == NEVER_RUN)
			cant_preempt = 1;
		if (cant_preempt) {
			translate_fail_code(cur_err, NULL, log_buf);
			sprintf(buf, "Preempt: Can not preempt to run job: %s", log_buf);
			schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
				LOG_DEBUG, hjob->name, buf);
			free_schd_error_list(full_err);
			return NULL;
		}
	}

	if ((pjobs = (resource_resv **) malloc(sizeof(resource_resv *) * (sinfo->sc.running + 1))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		free_schd_error_list(full_err);
		return NULL;
	}

	if (sinfo->preempt_targets_enable) {
		preempt_targets_req = find_resource_req(hjob->resreq, getallres(RES_PREEMPT_TARGETS));
		if (preempt_targets_req != NULL) {

			preempt_targets_list = break_comma_list(preempt_targets_req->res_str);
			retval = check_preempt_targets_for_none(preempt_targets_list);
			if (retval == PREEMPT_NONE) {
				schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, hjob->name,
					"No preemption set specified for the job: Job will not preempt");
				free_schd_error_list(full_err);
				free(pjobs);
				free_string_array(preempt_targets_list);
				return NULL;
			}
		}
	}

	if ((nsinfo = dup_server_info(sinfo)) == NULL) {
		free_schd_error_list(full_err);
		free(pjobs);
		free_string_array(preempt_targets_list);
		return NULL;
	}

	njob = find_resource_resv_by_rank(nsinfo->jobs, hjob->rank);
	prev_prio = njob->job->preempt;

	if (nsinfo->preempt_targets_enable) {
		if (preempt_targets_req != NULL) {
			prjobs = resource_resv_filter(nsinfo->running_jobs,
				count_array((void **) nsinfo->running_jobs),
				preempt_job_set_filter,
				(void *) preempt_targets_list, NO_FLAGS);
			free_string_array(preempt_targets_list);
		}
	}

	if (prjobs != NULL) {
		rjobs = prjobs;
		rjobs_count = count_array((void **)prjobs);
		if (rjobs_count > 0) {
			sprintf(log_buf, "Limited running jobs used for preemption from %d to %d",
				nsinfo->sc.running, rjobs_count);
			schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, njob->name, log_buf);
		}
		else {
			sprintf(log_buf, "Limited running jobs used for preemption from %d to 0: No jobs to preempt",
				nsinfo->sc.running);
			schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, njob->name, log_buf);
			free_server(nsinfo, 1);
			free_schd_error_list(full_err);
			free(pjobs);
			free(prjobs);
			return NULL;
		}

	}
	else {
		rjobs = nsinfo->running_jobs;
		rjobs_count = nsinfo->sc.running;
	}

	/* sort jobs in ascending preemption priority and starttime... we want to preempt them
	 * from lowest prio to highest
	 */
	if (conf.preempt_min_wt_used) {
		qsort(rjobs, rjobs_count, sizeof(job_info *),
			cmp_preempt_stime_asc);
	}
	else {
		/* sort jobs in ascending preemption priority... we want to preempt them
		 * from lowest prio to highest
		 */
		qsort(rjobs, rjobs_count, sizeof(job_info *),
		cmp_preempt_priority_asc);
	}

	err = dup_schd_error(full_err);	/* only first element */
	if(err == NULL) {
		free_schd_error_list(full_err);
		free_server(nsinfo, 1);
		free(pjobs);
		free(prjobs);
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	skipto=0;
	while ((indexfound = select_index_to_preempt(policy, njob, rjobs, skipto, err, fail_list)) != NO_JOB_FOUND) {
		if (indexfound == ERR_IN_SELECT) {
			/* System error occurred, no need to proceed */
			free_server(nsinfo, 1);
			free(pjobs);
			free(prjobs);
			free(old_errorarg1);
			free_schd_error_list(full_err);
			free_schd_error(err);
			log_err(errno, __func__, MEM_ERR_MSG);
			return NULL;
		}
		pjob=rjobs[indexfound];
		if (pjob->job->preempt < njob->job->preempt) {
			schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, pjob->name,
				"Simulation: preempting job");

			pjob->job->resreleased = create_res_released_array(policy, pjob);
			pjob->job->resreq_rel = create_resreq_rel_list(policy, pjob);

			update_universe_on_end(policy, pjob,  "S");
			if ( nsinfo->calendar != NULL ) {
				te = find_timed_event(nsinfo->calendar->events, pjob->name, TIMED_END_EVENT, 0);
				if (te != NULL) {
					if (delete_event(nsinfo, te, DE_NO_FLAGS) == 0)
						schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO, pjob->name, "Failed to delete end event for job.");
				}
			}

			pjobs[j] = pjob;
			j++;

			if( err != NULL) {
				old_errorcode = err->error_code;
				if (old_errorarg1 != NULL)
					free(old_errorarg1);
				switch(old_errorcode)
				{
					case SERVER_USER_RES_LIMIT_REACHED:
					case SERVER_BYUSER_RES_LIMIT_REACHED:
					case QUEUE_USER_RES_LIMIT_REACHED:
					case QUEUE_BYUSER_RES_LIMIT_REACHED:

					case SERVER_GROUP_RES_LIMIT_REACHED:
					case SERVER_BYGROUP_RES_LIMIT_REACHED:
					case QUEUE_GROUP_RES_LIMIT_REACHED:
					case QUEUE_BYGROUP_RES_LIMIT_REACHED:

					case SERVER_PROJECT_RES_LIMIT_REACHED:
					case SERVER_BYPROJECT_RES_LIMIT_REACHED:
					case QUEUE_PROJECT_RES_LIMIT_REACHED:
					case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
						old_errorarg1 = string_dup(err->arg1);
						break;
					case INSUFFICIENT_RESOURCE:
						old_errorarg1 = string_dup(err->rdef->name);
						break;
					default:
						old_errorarg1 = NULL;
				}
			}


			clear_schd_error(err);
			if ((ns_arr = is_ok_to_run(policy, -1, nsinfo,
				njob->job->queue, njob, NO_FLAGS, err)) != NULL) {

				/* Normally when running a subjob, we do not care about the subjob. We just care that it successfully runs.
				 * We allow run_update_resresv() to enqueue and run the subjob.  In this case, we need to act upon the
				 * subjob after it runs.  To handle this case, we enqueue it first then we run it.
				 */
				if (njob->job->is_array) {
					resource_resv *nj;
					nj = queue_subjob(njob, nsinfo, njob->job->queue);

					if (nj == NULL) {
						free_server(nsinfo, 1);
						free(pjobs);
						free(prjobs);
						free_schd_error_list(full_err);
						free_schd_error(err);
						free(old_errorarg1);
						return NULL;
					}
					njob = nj;
				}


				schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, njob->name,
					"Simulation: Preempted enough work to run job");
				rc = sim_run_update_resresv(policy, njob, ns_arr, RURR_NO_FLAGS);
				break;
			}

			if (old_errorcode == err->error_code) {
				switch(old_errorcode)
				{
					case SERVER_USER_RES_LIMIT_REACHED:
					case SERVER_BYUSER_RES_LIMIT_REACHED:
					case QUEUE_USER_RES_LIMIT_REACHED:
					case QUEUE_BYUSER_RES_LIMIT_REACHED:

					case SERVER_GROUP_RES_LIMIT_REACHED:
					case SERVER_BYGROUP_RES_LIMIT_REACHED:
					case QUEUE_GROUP_RES_LIMIT_REACHED:
					case QUEUE_BYGROUP_RES_LIMIT_REACHED:

					case SERVER_PROJECT_RES_LIMIT_REACHED:
					case SERVER_BYPROJECT_RES_LIMIT_REACHED:
					case QUEUE_PROJECT_RES_LIMIT_REACHED:
					case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
						if (strcmp(old_errorarg1, err->arg1) != 0)
						/* same limit type, but different resource, revisit earlier jobs */
							skipto = 0;
						break;
					case INSUFFICIENT_RESOURCE:
						if (strcmp(old_errorarg1, err->rdef->name) != 0)
						/* same limit type, but different resource, revisit earlier jobs */
							skipto = 0;
						break;
					default:
					/* same error as before -- continue to consider next job in rjobs */
					/* don't forget current job found has been removed from sinfo->running_jobs! */
					/* So we need to start again "where we last were" */
						skipto = indexfound;
				}
			} else {
				/* error changed, so we need to revisit jobs discarded as preemption candidates earlier */
				skipto = 0;
			}

		}
		translate_fail_code(err, NULL, log_buf);
		sprintf(buf, "Simulation: not enough work preempted: %s", log_buf);
		schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB,
			LOG_DEBUG, njob->name, buf);
	}

	pjobs[j] = NULL;

	/* check to see if we lowered our preempt priority in our simulation
	 * if we have, then punt and don't
	 */
	if (prev_prio > njob->job->preempt) {
		rc = 0;
		schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, njob->name,
			"Job not run because it would immediately be preemptable.");
	}


	/* Right now we have a list of jobs we know will create enough space.  It
	 * might preempt too much work.  We need to determine if each job is
	 * still needed.
	 *
	 * We look to see if jobs are similar to the high priority job (preemption_similarity())
	 * or we try and rerun them in the simulated universe.
	 * If we can run them or the jobs aren't similar, then we don't have to
	 * preempt them.  We will go backwards from the end of the list because we
	 * started preempting with the lowest priority jobs.
	 */

	if (rc > 0) {
		if ((pjobs_list = calloc((j + 1), sizeof(int))) == NULL) {
			free_server(nsinfo, 1);
			free(pjobs);
			free(prjobs);
			free(old_errorarg1);
			free_schd_error_list(full_err);
			free_schd_error(err);
			log_err(errno, __func__, MEM_ERR_MSG);
			return NULL;
		}

		for (j--, i = 0; j >= 0 ; j--) {
			int remove_job = 0;
			clear_schd_error(err);
			if (preemption_similarity(njob, pjobs[j], full_err) == 0) {
				remove_job = 1;
				ns_arr = pjobs[j]->nspec_arr;
			} else if ((ns_arr = is_ok_to_run(policy, SIMULATE_SD, nsinfo,
				pjobs[j]->job->queue, pjobs[j], NO_FLAGS, err)) != NULL) {
				remove_job = 1;
				rc = sim_run_update_resresv(policy, pjobs[j], ns_arr, RURR_NO_FLAGS);
			}


			if (remove_job) {
				schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
					pjobs[j]->name, "Simulation: preemption of job not needed.");
				remove_resresv_from_array(pjobs, pjobs[j]);

			} else {
				pjobs_list[i] = pjobs[j]->rank;
				i++;
			}
		}

		pjobs_list[i] = 0;
		/* i == 0 means we removed all the jobs: Should not happen */
		if (i == 0) {
			schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, njob->name,
				"Simulation Error: All jobs removed from preemption list");
			rc = 0;
		}
	}

	free_server(nsinfo, 1);
	free(pjobs);
	free(prjobs);
	free_schd_error_list(full_err);
	free_schd_error(err);
	free(old_errorarg1);


	return pjobs_list;
}

/**
 * @brief
 *		select a good candidate for preemption
 *
 * @param[in] policy - policy info
 * @param[in] hjob - the high priority job to preempt for
 * @param[in] rjobs - the list of running jobs to select from
 * @param[in] skipto - Index from where we need to start looking into rjobs
 * @param[in] err    - reason the high prio job isn't running
 * @param[in] fail_list - list of jobs to skip. They previously failed to be preempted.
 *			  Do not select them again.
 *
 * @return long
 * @retval index of the job to preempt
 * @retval NO_JOB_FOUND nothing can be selected for preemption
 * @retval ERR_IN_SELECT error
 */
long
select_index_to_preempt(status *policy, resource_resv *hjob,
	resource_resv **rjobs, long skipto, schd_error *err,
	int *fail_list)
{
	int i, j, k;
	resource_req *req;
	int good = 1, certainlygood = 0;		/* good boolean: Is job eligible to be preempted */
	struct preempt_ordering *po;
	resource_req *req2;
	resdef **rdtc_non_consumable = NULL;
	char *limitres_name = NULL;
	int limitres_injob = 1;
	resource_req *req_scan;

	int rc;

	if ( err == NULL || hjob == NULL || hjob->job == NULL ||
		rjobs == NULL || rjobs[0] == NULL)
		return NO_JOB_FOUND;

	rc = err->error_code;

	switch(rc)
	{
		case SERVER_USER_RES_LIMIT_REACHED:
		case SERVER_BYUSER_RES_LIMIT_REACHED:
		case QUEUE_USER_RES_LIMIT_REACHED:
		case QUEUE_BYUSER_RES_LIMIT_REACHED:

		case SERVER_GROUP_RES_LIMIT_REACHED:
		case SERVER_BYGROUP_RES_LIMIT_REACHED:
		case QUEUE_GROUP_RES_LIMIT_REACHED:
		case QUEUE_BYGROUP_RES_LIMIT_REACHED:

		case SERVER_PROJECT_RES_LIMIT_REACHED:
		case SERVER_BYPROJECT_RES_LIMIT_REACHED:
		case QUEUE_PROJECT_RES_LIMIT_REACHED:
		case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
			if (err->arg1 != NULL)
			{
				limitres_name = string_dup (err->arg1);
				if (limitres_name == NULL)
					return ERR_IN_SELECT;
			}
			break;
		case INSUFFICIENT_RESOURCE:
			if (err->rdef != NULL) {
				limitres_name = string_dup(err->rdef->name);
				if (limitres_name == NULL)
					return ERR_IN_SELECT;
			}
			break;
		default:
			limitres_name = NULL;
	}

	/* This shouldn't happen, but you can never be too paranoid */
	if (hjob->job->is_running && hjob->ninfo_arr == NULL)
		return NO_JOB_FOUND;

	/* if we find a good job, we'll break out at the bottom
	 * we can't break out up here since i will be incremented by this point
	 * and we'll be returning the job AFTER the one we want too
	 */
	for (i = skipto; rjobs[i] != NULL; i++) {
		/* Does the running job have any resource we need? */
		int node_good = 1;
		int svr_res_good = 1;

		/* lets be optimistic.. we'll start off assuming this is a good candidate */
		good = 1;
		certainlygood = 0;

		/* if hjob hit a hard limit, check if candidate job has requested that resource
		 * if reason is different then set flag as if resource was found
		 */
		switch(rc)
		{
			case SERVER_USER_RES_LIMIT_REACHED:
			case SERVER_BYUSER_RES_LIMIT_REACHED:
			case QUEUE_USER_RES_LIMIT_REACHED:
			case QUEUE_BYUSER_RES_LIMIT_REACHED:

			case SERVER_GROUP_RES_LIMIT_REACHED:
			case SERVER_BYGROUP_RES_LIMIT_REACHED:
			case QUEUE_GROUP_RES_LIMIT_REACHED:
			case QUEUE_BYGROUP_RES_LIMIT_REACHED:

			case SERVER_PROJECT_RES_LIMIT_REACHED:
			case SERVER_BYPROJECT_RES_LIMIT_REACHED:
			case QUEUE_PROJECT_RES_LIMIT_REACHED:
			case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
			case INSUFFICIENT_RESOURCE:
				limitres_injob = 0;
				for (j = 0; rjobs[i]->select->chunks[j] != NULL; j++)
				{
					req_scan=rjobs[i]->select->chunks[j]->req;
					while (req_scan)
					{
						if ( strcmp(req_scan->name,limitres_name) == 0 )
						{
							if ((req_scan->type.is_non_consumable) ||
								(req_scan->amount > 0)) {
								limitres_injob = 1;
								break;
							}
						}
						req_scan = req_scan->next;
					}
					if (limitres_injob == 1)
						 break;
				}

				break;
			default:
				limitres_injob = 1;
		}


		if (rjobs[i]->job == NULL || rjobs[i]->ninfo_arr == NULL)
			continue; /* we have problems... */

		if (!rjobs[i]->job->is_running)
			/* Only running jobs have resources allocated to them.
			 * They are only eligible to preempt.
			 */
			good = 0;


		if (rjobs[i]->job->is_provisioning)
			good = 0; /* provisioning job cannot be preempted */

		if (good) {
			if (rjobs[i]->job->can_not_preempt ||
			rjobs[i]->job->preempt >= hjob->job->preempt)
				good = 0;
		}

		if (good) {
			for (j = 0; fail_list[j] != 0; j++) {
				if (fail_list[j] == rjobs[i]->rank) {
					good = 0;
					break;
				}
			}
		}


		if (good) {
			/* get the preemption order to be used for this job */
			po = get_preemption_order(rjobs[i], rjobs[i]->server);

			/* check whether chosen order is enabled for this job */
			for (j = 0; j < PREEMPT_METHOD_HIGH; j++) {
				if (po->order[j] == PREEMPT_METHOD_SUSPEND  &&
					rjobs[i]->job->can_suspend)
					break; /* suspension is always allowed */

				if (po->order[j] == PREEMPT_METHOD_CHECKPOINT &&
					rjobs[i]->job->can_checkpoint)
					break; /* choose if checkpoint is allowed */

				if (po->order[j] == PREEMPT_METHOD_REQUEUE &&
					rjobs[i]->job->can_requeue)
					break; /* choose if requeue is allowed */
			}
			if (j == PREEMPT_METHOD_HIGH) /* no preemption method good */
				good = 0;
		}

		if (good) {
			for (j = 0; good && rjobs[i]->ninfo_arr[j] != NULL; j++) {
				if (rjobs[i]->ninfo_arr[j]->is_down || rjobs[i]->ninfo_arr[j]->is_offline)
					good = 0;
			}
		}

		if (good) {
			switch(rc)
			{
				case QUEUE_JOB_LIMIT_REACHED:
				case QUEUE_RESOURCE_LIMIT_REACHED:
					if (rjobs[i]->job->queue != hjob->job->queue)
						good = 0;
					else
						certainlygood = 1;
					break;
				case SERVER_USER_LIMIT_REACHED:
				case SERVER_BYUSER_JOB_LIMIT_REACHED:
				case SERVER_USER_RES_LIMIT_REACHED:
				case SERVER_BYUSER_RES_LIMIT_REACHED:
					if (strcmp(rjobs[i]->user, hjob->user) || !limitres_injob)
						good = 0;
					else
						certainlygood = 1;
					break;
				case QUEUE_USER_LIMIT_REACHED:
				case QUEUE_BYUSER_JOB_LIMIT_REACHED:
				case QUEUE_USER_RES_LIMIT_REACHED:
				case QUEUE_BYUSER_RES_LIMIT_REACHED:
					if (rjobs[i]->job->queue != hjob->job->queue)
						good = 0;
					if (strcmp(rjobs[i]->user, hjob->user))
						good = 0;
					if (!limitres_injob)
						good = 0;
					if (good)
						certainlygood = 1;
					break;
				case SERVER_GROUP_LIMIT_REACHED:
				case SERVER_BYGROUP_JOB_LIMIT_REACHED:
				case SERVER_GROUP_RES_LIMIT_REACHED:
				case SERVER_BYGROUP_RES_LIMIT_REACHED:
					if (strcmp(rjobs[i]->group, hjob->group) || !limitres_injob)
						good = 0;
					else
						certainlygood = 1;
					break;
				case QUEUE_GROUP_LIMIT_REACHED:
				case QUEUE_BYGROUP_JOB_LIMIT_REACHED:
				case QUEUE_GROUP_RES_LIMIT_REACHED:
				case QUEUE_BYGROUP_RES_LIMIT_REACHED:
					if (rjobs[i]->job->queue != hjob->job->queue)
						good = 0;
					if (strcmp(rjobs[i]->group, hjob->group))
						good = 0;
					if (!limitres_injob)
						good = 0;
					if (good)
						certainlygood = 1;
					break;
				case SERVER_PROJECT_LIMIT_REACHED:
				case SERVER_BYPROJECT_JOB_LIMIT_REACHED:
				case SERVER_PROJECT_RES_LIMIT_REACHED:
				case SERVER_BYPROJECT_RES_LIMIT_REACHED:
					if (strcmp(rjobs[i]->project, hjob->project) || !limitres_injob)
						good = 0;
					else
						certainlygood = 1;
					break;
				case QUEUE_PROJECT_LIMIT_REACHED:
				case QUEUE_BYPROJECT_JOB_LIMIT_REACHED:
				case QUEUE_PROJECT_RES_LIMIT_REACHED:
				case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
					if (rjobs[i]->job->queue != hjob->job->queue)
						good = 0;
					if (strcmp(rjobs[i]->project, hjob->project))
						good = 0;
					if (!limitres_injob)
						good = 0;
					if (good)
						certainlygood = 1;
					break;
				case INSUFFICIENT_RESOURCE:
					if (!limitres_injob)
						good = 0;
					else
						certainlygood = 1;
					break;

			}
		}

		/* if the high priority job is suspended then make sure we only
		 * select jobs from the node the job is currently suspended on
		 */

		if (good && !certainlygood) {
			if (hjob->ninfo_arr != NULL) {
				for (j = 0; hjob->ninfo_arr[j] != NULL; j++) {
					if (find_node_by_rank(rjobs[i]->ninfo_arr,
						hjob->ninfo_arr[j]->rank) != NULL)
						break;
				}

				/* if we made all the way through the list, then rjobs[i] has no useful
				 * nodes for us to use... don't select it, unless it's not node resources we're after
				 */

				if (hjob->ninfo_arr[j] == NULL) {
					good = 0;
					svr_res_good = 0;
					for (req = hjob->resreq; req != NULL; req = req->next) {
					/* Check for resources in the resources line that are not RASSN resources.
					 * RASSN resources are accumulated across the select.
					 * This means all jobs will have them, and it invalidates the earlier check.
					 */
						if (resdef_exists_in_array(policy->resdef_to_check, req->def) &&
						   (resdef_exists_in_array(policy->resdef_to_check_rassn, req->def) == 0)) {
							req2 = find_resource_req(rjobs[i]->resreq, req->def);
							if (req2 != NULL)
								svr_res_good = 1;
						}
					}
					if ( svr_res_good == 1)
						certainlygood = 1;
				} else
					/* we'll have to consider this, since it's sitting on vnodes this suspended job lives on */
					certainlygood = 1;
			}
		}
		if (good) {
			schd_error *err;
			node_good = 0;

			err = new_schd_error();
			if(err == NULL)
				return NO_JOB_FOUND;

			for (j = 0; rjobs[i]->ninfo_arr[j] != NULL && !node_good; j++) {
				resdef **rdtc_here = NULL; /* at first assume all resources (including consumables) need to be checked */
				node_info *node = rjobs[i]->ninfo_arr[j];
				if (node->is_multivnoded) {
					/* unsafe to consider vnodes from multivnoded hosts "no good" when "not enough" of some consumable
					 * resource can be found in the vnode, since rest may be provided by other vnodes on the same host
					 * restrict check on these vnodes to check only against non consumable resources
					 */
					if (rdtc_non_consumable == NULL) {
						long max_resdefs = 0;
						if (policy != NULL) {
							max_resdefs = count_array( (void **) policy->resdef_to_check);
						}
						if (max_resdefs > 0)    {
							rdtc_non_consumable = (resdef **) calloc(sizeof(resdef *),(size_t) max_resdefs + 1);
							if (rdtc_non_consumable != NULL) {
								long resdef_index = 0;
								long rdtc_nc_index = 0;
								for (; policy->resdef_to_check[resdef_index] != NULL; resdef_index++) {
									if (policy->resdef_to_check[resdef_index]->type.is_non_consumable) {
										rdtc_non_consumable[rdtc_nc_index] = policy->resdef_to_check[resdef_index];
										rdtc_nc_index++;
									}
									rdtc_non_consumable[rdtc_nc_index] = NULL;
								}
							}
						}
					}
					rdtc_here = rdtc_non_consumable;
				}
				for (k = 0; hjob->select->chunks[k] != NULL; k++) {
					long num_chunks_returned = 0;
					/* if only non consumables are checked, infinite number of chunks can be satisfied,
					 * and SCHD_INFINITY is negative, so don't be tempted to check on positive value
					 */
					clear_schd_error(err);
					num_chunks_returned = check_avail_resources(node->res, hjob->select->chunks[k]->req,
								COMPARE_TOTAL | CHECK_ALL_BOOLS | UNSET_RES_ZERO,
								rdtc_here, INSUFFICIENT_RESOURCE, err);
					if ( (num_chunks_returned > 0) || (num_chunks_returned == SCHD_INFINITY) ) {
						node_good = 1;
						break;
					}

				}
			}
			free_schd_error(err);

			if (node_good == 0) {
				svr_res_good = 0;
				for (req = hjob->resreq; req != NULL; req = req->next) {
					/* Check for resources in the resources line that are not RASSN resources.
					 * RASSN resources are accumulated across the select.
					 * This means all jobs will have them, and it invalidates this check.
					 */
					if (resdef_exists_in_array(policy->resdef_to_check, req->def) && (resdef_exists_in_array(policy->resdef_to_check_rassn, req->def) == 0)) {
						req2 = find_resource_req(rjobs[i]->resreq, req->def);
						if (req2 != NULL) {
							svr_res_good = 1;
						}
					}
				}
			}


		}

		if (!certainlygood && node_good == 0 && svr_res_good == 0)
			good = 0;


		if (good || certainlygood)
			break;
	}
	if (rdtc_non_consumable != NULL)
		free (rdtc_non_consumable);

	if (limitres_name != NULL)
		free (limitres_name);

	if (good && rjobs[i] != NULL)
		return i;

	return NO_JOB_FOUND;
}

/**
 * @brief
 *		preempt_level - take a preemption priority and return a preemption
 *			level
 *
 * @param[in]	prio	-	the preemption priority
 *
 * @return	the preemption level
 *
 */
int
preempt_level(int prio)
{
	int level = NUM_PPRIO;
	int i;

	for (i = 0; i < NUM_PPRIO && level == NUM_PPRIO ; i++)
		if (conf.pprio[i][1] == prio)
			level = i;

	return level;
}

/**
 * @brief
 *		set_preempt_prio - set a job's preempt field to the correct value
 *
 * @param[in]	job	-	the job to set
 * @param[in]	qinfo	-	the queue the job is in
 * @param[in]	sinfo	-	the job's server
 *
 * @return	nothing
 *
 */
void
set_preempt_prio(resource_resv *job, queue_info *qinfo, server_info *sinfo)
{
	int i;
	job_info *jinfo;
	int rc;

	if (job == NULL || job->job == NULL || qinfo == NULL || sinfo == NULL)
		return;

	jinfo = job->job;

	/* in the case of reseting the value, we need to clear them first */
	jinfo->preempt = 0;
	jinfo->preempt_status = 0;

	if (job == sinfo->qrun_job)
		jinfo->preempt_status |= PREEMPT_TO_BIT(PREEMPT_QRUN);

	if (conf.preempt_queue_prio != SCHD_INFINITY &&
		qinfo->priority >= conf.preempt_queue_prio)
		jinfo->preempt_status |= PREEMPT_TO_BIT(PREEMPT_EXPRESS);

	if (conf.preempt_fairshare && over_fs_usage(jinfo->ginfo))
		jinfo->preempt_status |= PREEMPT_TO_BIT(PREEMPT_OVER_FS_LIMIT);

	if (jinfo->is_starving && conf.preempt_starving)
		jinfo->preempt_status |= PREEMPT_TO_BIT(PREEMPT_STARVING);

	if ((rc = check_soft_limits(sinfo, qinfo, job)) != 0) {
		if ((rc & PREEMPT_TO_BIT(PREEMPT_ERR)) != 0) {
			job->can_not_run = 1;
			schdlog(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_ERR, job->name,
				"job marked as not runnable due to check_soft_limits internal error");
			return;
		}
		else
			jinfo->preempt_status |= rc;
	}

	/* we haven't set it yet, therefore it's a normal job */
	if (jinfo->preempt_status == 0)
		jinfo->preempt_status = PREEMPT_TO_BIT(PREEMPT_NORMAL);

	/* now that we've set all the possible preempt status's on the job, lets
	 * set its priority compared to those statuses.  The statuses are sorted
	 * by number of bits first, and priority second.  We need to just search
	 * through the list once and set the priority to the first one we find
	 */

	for (i = 0; i < NUM_PPRIO && conf.pprio[i][0] != 0 &&
		jinfo->preempt == 0; i++) {
		if ((jinfo->preempt_status & conf.pprio[i][0]) == conf.pprio[i][0]) {
			jinfo->preempt = conf.pprio[i][1];
			/* if the express bit is on, then we'll add the priority of that
			 * queue into our priority to allow for multiple express queues
			 */
			if (conf.pprio[i][0] & PREEMPT_TO_BIT(PREEMPT_EXPRESS))
				jinfo->preempt += jinfo->queue->priority;
		}
	}
	/* we didn't find our preemption level -- this means we're a normal job */
	if (jinfo->preempt == 0) {
		jinfo->preempt_status = PREEMPT_TO_BIT(PREEMPT_NORMAL);
		jinfo->preempt = conf.preempt_normal;
	}
}

/**
 * @brief
 * 		create subjob name from subjob id and array name
 *
 * @param[in]	array_id	-	the parent array name
 * @param[in]	index	-	subjob index
 *
 * @return	created subjob name
 */
char *
create_subjob_name(char *array_id, int index)
{
	int spn;
	char *rest;
	char tmpid[128];		/* hold job id and leading '[' */
	char buf[1024];		/* buffer to hold new subjob identifer */

	spn = strcspn(array_id, "[");
	if (spn == 0)
		return NULL;

	rest = array_id + spn + 1;

	if (*rest != ']')
		return NULL;

	strncpy(tmpid, array_id, spn+1);
	tmpid[spn+1] = '\0';
	sprintf(buf, "%s%d%s", tmpid, index, rest);

	return string_dup(buf);
}

/**
 * @brief
 *		create_subjob_from_array - create a resource_resv structure for a
 *				   subjob from a job array structure.  The
 *				   subjob will be in state 'Q'
 *
 * @param[in]	array	-	the job array
 * @param[in]	index	-	the subjob index
 * @param[in]	subjob_name	-	name of subjob @see create_subjob_name()
 *
 * @return	the new subjob
 * @retval	NULL	: on error
 *
 */
resource_resv *
create_subjob_from_array(resource_resv *array, int index, char *subjob_name)
{
	resource_resv *subjob;	/* job_info structure for new subjob */
	range *tmp;			/* a tmp ptr to hold the queued_indices ptr */

	if (array == NULL || array->job == NULL)
		return NULL;

	if (!array->job->is_array)
		return NULL;

	/* so we don't dup the queued_indices for the subjob */
	tmp = array->job->queued_subjobs;
	array->job->queued_subjobs = NULL;

	subjob = dup_resource_resv(array, array->server, array->job->queue);

	array->job->queued_subjobs = tmp;

	if (subjob == NULL)
		return NULL;

	subjob->job->is_begin = 0;
	subjob->job->is_array = 0;

	subjob->job->is_queued = 1;
	subjob->job->is_subjob = 1;
	subjob->job->array_index = index;
	subjob->job->array_id = string_dup(array->name);
	subjob->job->parent_job = array;

	free(subjob->name);
	if (subjob_name != NULL)
		subjob->name = subjob_name;
	else
		subjob->name = create_subjob_name(array->name, index);

	subjob->job->parent_job = array;

	subjob->rank =  get_sched_rank();

	return subjob;
}

/**
 * @brief
 *		update_array_on_run - update a job array object when a subjob is run
 *
 * @param[in]	array	-	the job array to update
 * @param[in]	subjob	-	the subjob which was run
 *
 * @return	success or failure
 *
 */
int
update_array_on_run(job_info *array, job_info *subjob)
{
	if (array == NULL || subjob == NULL)
		return 0;

	range_remove_value(&array->queued_subjobs, subjob->array_index);

	if (array->is_queued) {
		array->is_begin = 1;
		array->is_queued = 0;
	}

	return 1;
}

/**
 * @brief
 *		is_job_array - is a job name a job array range
 *			  valid_form: 1234[]
 *			  valid_form: 1234[N]
 *			  valid_form: 1234[N-M]
 *
 * @param[in]	jobname	-	jobname to check
 *
 * @return int
 * @retval	1	: if jobname is a job array
 * @retval	2	: if jobname is a subjob
 * @retval	3	: if jobname is a range
 * @retval	0	: if it is not a job array
 */
int
is_job_array(char *jobname)
{
	char *bracket;
	int ret = 0;

	if (jobname == NULL)
		return 0;

	bracket = strchr(jobname, (int) '[');

	if (bracket != NULL) {
		if (*(bracket+1) == ']')
			ret = 1;
		if (strchr(bracket, (int) '-') != NULL)
			ret = 3;
		else
			ret = 2;
	}

	return ret;
}

/**
 * @brief
 *		modify_job_array_for_qrun - modify a job array for qrun -
 *				    set queued_subjobs to just the
 *				    range which is being run
 *				    set qrun_job on server
 *
 * @param[in,out]	sinfo	-	server to modify job array
 * @param[in]	jobid	-	string job name
 *
 * @return	int
 * @retval	1	: on success
 * @retval	0	: on failure
 * @retval	-1	: on error
 *
 */
int
modify_job_array_for_qrun(server_info *sinfo, char *jobid)
{
	char name[128];
	char rest[128];
	char *rangestr;
	char *ptr;
	range *r, *r2;
	int len;

	resource_resv *job;

	if (sinfo == NULL || jobid == NULL)
		return -1;

	strcpy(name, jobid);

	if ((ptr = strchr(name, (int) '[')) == NULL)
		return 0;

	*ptr = '\0';
	rangestr = ptr + 1;

	if ((ptr = strchr(rangestr, ']')) == NULL)
		return 0;

	strcpy(rest, ptr);

	*ptr = '\0';

	/* now rangestr should be the subjob index or range of indices */
	if ((r = range_parse(rangestr)) == NULL)
		return 0;

	/* now that we've converted the subjob index or range into a range list
	 * we can munge our original name to find the job array
	 */
	len = strlen(name);
	name[len] = '[';
	name[len + 1] = '\0';
	strcat(name, rest);

	job = find_resource_resv(sinfo->jobs, name);

	if (job != NULL) {
		/* lets only run the jobs which were requested */
		r2 = range_intersection(r, job->job->queued_subjobs);
		if (r2 != NULL) {
			free_range_list(job->job->queued_subjobs);
			job->job->queued_subjobs = r2;
		}
		else {
			free_range_list(r);
			return 0;
		}
	}
	else {
		free_range_list(r);
		return 0;
	}

	sinfo->qrun_job = job;
	free_range_list(r);
	return 1;
}

/**
 * @brief
 *		create a subjob from a job array and queue it
 *
 * @param[in]	array	-	job array to create the next subjob from
 * @param[in]	sinfo	-	the server the job array is in
 * @param[in]	qinfo	-	the queue the job array is in
 *
 * @return	resource_resv *
 * @retval	new subjob
 * @retval	NULL	: on error
 *
 * @note
 * 		subjob will be attached to the server/queue job lists
 *
 */
resource_resv *
queue_subjob(resource_resv *array, server_info *sinfo,
	queue_info *qinfo)
{
	int subjob_index;
	char *subjob_name;
	resource_resv *rresv = NULL;
	resource_resv **tmparr = NULL;

	if (array == NULL || array->job == NULL || sinfo == NULL || qinfo == NULL)
		return NULL;

	if (!array->job->is_array)
		return NULL;

	subjob_index = range_next_value(array->job->queued_subjobs, -1);
	if (subjob_index >= 0) {
		subjob_name = create_subjob_name(array->name, subjob_index);
		if (subjob_name != NULL) {
			if ((rresv = find_resource_resv(sinfo->jobs, subjob_name)) != NULL) {
				free(subjob_name);
				/* Set tmparr to something so we're not considered an error */
				tmparr = sinfo->jobs;
				/* check of array parent is not set then set that here */
				if (rresv->job->parent_job == NULL)
					rresv->job->parent_job = array;
			}
			else if ((rresv = create_subjob_from_array(array, subjob_index,
				subjob_name)) != NULL) {
				/* add_resresv_to_array calls realloc, so we need to treat this call
				 * as a call to realloc.  Put it into a temp variable to check for NULL
				 */
				tmparr = add_resresv_to_array(sinfo->jobs, rresv);
				if (tmparr != NULL) {
					sinfo->jobs = tmparr;
					sinfo->sc.queued++;
					sinfo->sc.total++;

					tmparr = add_resresv_to_array(sinfo->all_resresv, rresv);
					if (tmparr != NULL) {
						sinfo->all_resresv = tmparr;

						tmparr = add_resresv_to_array(qinfo->jobs, rresv);
						if (tmparr != NULL) {
							qinfo->jobs = tmparr;
							qinfo->sc.queued++;
							qinfo->sc.total++;
						}
					}
				}
			}
		}
	}

	if (tmparr == NULL || rresv == NULL) {
		schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, array->name,
			"Unable to create new subjob for job array");
		return NULL;
	}

	return rresv;
}

/**
 * @brief
 * 		evaluate a math formula for jobs based on their resources
 *		NOTE: currently done through embedded python interpreter
 *
 * @param[in]	formula	-	formula to evaluate
 * @param[in]	resresv	-	job for special case key words
 * @param[in]	resreq	-	resources to use when evaluating
 *
 * @return	evaluated formula answer or 0 on exception
 *
 */

#ifdef PYTHON
sch_resource_t
formula_evaluate(char *formula, resource_resv *resresv, resource_req *resreq)
{
	char buf[1024];
	char *globals;
	int globals_size = 1024;  /* initial size... will grow if needed */
	char errbuf[MAX_LOG_SIZE];
	resource_req *req;
	sch_resource_t ans = 0;
	char *str;
	int i;
	char *formula_buf;
	int formula_buf_len;

	PyObject *module;
	PyObject *dict;
	PyObject *obj;

	if (formula == NULL || resresv == NULL ||
		resresv->job == NULL || consres == NULL)
		return 0;

	formula_buf_len = sizeof(buf) + strlen(formula) + 1;

	formula_buf = malloc(formula_buf_len);
	if (formula_buf == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return 0;
	}

	if ((globals = malloc(globals_size * sizeof(char))) == NULL  ) {
		log_err(errno, __func__, MEM_ERR_MSG);
		free(formula_buf);
		return 0;
	}

	globals[0] = '\0';

	if (pbs_strcat(&globals, &globals_size, "globals_dict = {") == NULL) {
		free(globals);
		free(formula_buf);
		return 0;
	}


	for (i = 0; consres[i] != NULL; i++) {
		req = find_resource_req(resreq, consres[i]);

		if (req != NULL)
			sprintf(buf, "\'%s\':%.*f,", consres[i]->name,
				float_digits(req->amount, FLOAT_NUM_DIGITS), req->amount);
		else
			sprintf(buf, "\'%s\' : 0,", consres[i]->name);

		if (pbs_strcat(&globals, &globals_size, buf) == NULL) {
			free(globals);
			free(formula_buf);
			return 0;
		}
	}

	/* special cases */
	sprintf(buf, "\'%s\':%ld,\'%s\':%d,\'%s\':%d,\'%s\':%f, \'%s\': %f, \'%s\': %f, \'%s\': %f, \'%s\':%d}",
		FORMULA_ELIGIBLE_TIME, resresv->job->eligible_time,
		FORMULA_QUEUE_PRIO, resresv->job->queue->priority,
		FORMULA_JOB_PRIO, resresv->job->priority,
		FORMULA_FSPERC, resresv->job->ginfo->tree_percentage,
		FORMULA_FSPERC_DEP, resresv->job->ginfo->tree_percentage,
		FORMULA_TREE_USAGE, resresv->job->ginfo->usage_factor,
		FORMULA_FSFACTOR, resresv->job->ginfo->tree_percentage == 0 ? 0 : 
			pow(2, -(resresv->job->ginfo->usage_factor/resresv->job->ginfo->tree_percentage)),
		FORMULA_ACCRUE_TYPE, resresv -> job -> accrue_type);
	if (pbs_strcat(&globals, &globals_size, buf) == NULL) {
		free(globals);
		free(formula_buf);
		return 0;
	}

	PyRun_SimpleString(globals);
	free(globals);

	/* now that we've set all the values, let's calculate the answer */
	snprintf(formula_buf, formula_buf_len,
		"_PBS_PYTHON_EXCEPTIONSTR_=\"\"\n"
		"ex = None\n"
		"try:\n"
		"\t_FORMANS_ = eval(\"%s\", globals_dict, locals())\n"
		"except Exception, ex:"
		"\t_PBS_PYTHON_EXCEPTIONSTR_=str(ex)\n", formula);

	PyRun_SimpleString(formula_buf);
	free(formula_buf);

	module = PyImport_AddModule("__main__");
	dict = PyModule_GetDict(module);
	obj = PyMapping_GetItemString(dict, "_FORMANS_");

	if (obj != NULL) {
		ans = PyFloat_AsDouble(obj);
		Py_XDECREF(obj);
	}

	obj = PyMapping_GetItemString(dict, "_PBS_PYTHON_EXCEPTIONSTR_");
	if (obj != NULL) {
		str = PyString_AsString(obj);
		if (str != NULL) {
			if (strlen(str) > 0) { /* exception happened */
				sprintf(errbuf,
					"Formula evaluation for job had an error.  Zero value will be used: %s",
					str);
				schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
					resresv->name, errbuf);
				ans = 0;
			}
		}
		Py_XDECREF(obj);
	}



	return ans;
}
#else
sch_resource_t
formula_evaluate(char *formula, resource_resv *resresv, resource_req *resreq)
{
	return 0;
}
#endif

/**
 * @brief
 * 		Set the job accrue type to eligible time.
 *
 * @param[in]	pbs_sd	-	connection to pbs_server
 * @param[out]	resresv	-	pointer to job
 *
 * @return	void
 *
 */
static void
make_eligible(int pbs_sd, resource_resv *resresv)
{
	if (resresv == NULL || resresv->job == NULL)
		return;
	if (resresv->job->accrue_type !=JOB_ELIGIBLE) {
		update_job_attr(pbs_sd, resresv, ATTR_accrue_type, NULL, ACCRUE_ELIG, NULL, UPDATE_LATER);
		resresv->job->accrue_type = JOB_ELIGIBLE;
	}
	return;
}

/**
 * @brief
 * 		Set the job accrue type to ineligible time.
 *
 * @param[in]	pbs_sd	-	connection to pbs_server
 * @param[out]	resresv	-	pointer to job
 *
 * @return	void
 */
static void
make_ineligible(int pbs_sd, resource_resv *resresv)
{
	if (resresv == NULL || resresv->job == NULL)
		return;
	if (resresv->job->accrue_type !=JOB_INELIGIBLE) {
		update_job_attr(pbs_sd, resresv, ATTR_accrue_type, NULL, ACCRUE_INEL, NULL, UPDATE_LATER);
		resresv->job->accrue_type = JOB_INELIGIBLE;
	}
	return;
}

/**
 * @brief
 * 		Updates accrue_type of job on server. The accrue_type is determined
 * 		from the values of mode and err_code. If resresv is a job array, special
 * 		action is taken. If mode is set to something other than ACCRUE_CHECK_ERR
 * 		then the value of err_code is ignored unless it is set to SCHD_ERROR.
 *
 * @param[in]	pbs_sd	-	connection to pbs_server
 * @param[in]	sinfo	-	pointer to server
 * @param[in]	mode	-	mode of operation
 * @param[in]	err_code	-	sched_error value
 * @param[in,out]	resresv	-	pointer to job
 *
 * @return void
 *
 */
void
update_accruetype(int pbs_sd, server_info *sinfo,
	enum update_accruetype_mode mode, enum sched_error err_code,
	resource_resv *resresv)
{
	if (sinfo == NULL || resresv == NULL || resresv->job == NULL)
		return;

	/* if SCHD_ERROR, don't change accrue type */
	if (err_code == SCHD_ERROR)
		return;

	if (sinfo->eligible_time_enable == 0)
		return;

	/* behavior of job array's eligible_time calc differs from jobs/subjobs,
	 *  it depends on:
	 *    1) job array is empty - accrues ineligible time
	 *    2) job array has instantiated all subjobs - accrues ineligible time
	 *    3) job array has atleast one subjob to run - accrues eligible time
	 */

	if (resresv->job->is_array && resresv->job->is_begin &&
		(range_next_value(resresv->job->queued_subjobs, -1) < 0)) {
		make_ineligible(pbs_sd, resresv);
		return;
	}

	if ((resresv->job->preempt_status & PREEMPT_QUEUE_SERVER_SOFTLIMIT) >0) {
		make_ineligible(pbs_sd, resresv);
		return;
	}

	if (mode == ACCRUE_MAKE_INELIGIBLE) {
		make_ineligible(pbs_sd, resresv);
		return;
	}

	if (mode == ACCRUE_MAKE_ELIGIBLE) {
		make_eligible(pbs_sd, resresv);
		return;
	}

	/* determine accruetype from err code */
	switch (err_code) {

		case SUCCESS:
			/* server updates accrue_type to RUNNING, hence, simply move out */
			/* accrue type is set to running in update_resresv_on_run() */
			break;

		case SERVER_BYUSER_JOB_LIMIT_REACHED:
		case SERVER_BYUSER_RES_LIMIT_REACHED:
		case SERVER_USER_LIMIT_REACHED:
		case SERVER_USER_RES_LIMIT_REACHED:
		case SERVER_BYGROUP_JOB_LIMIT_REACHED:
		case SERVER_BYPROJECT_JOB_LIMIT_REACHED:
		case SERVER_BYGROUP_RES_LIMIT_REACHED:
		case SERVER_BYPROJECT_RES_LIMIT_REACHED:
		case SERVER_GROUP_LIMIT_REACHED:
		case SERVER_GROUP_RES_LIMIT_REACHED:
		case SERVER_PROJECT_LIMIT_REACHED:
		case SERVER_PROJECT_RES_LIMIT_REACHED:
		case QUEUE_BYUSER_JOB_LIMIT_REACHED:
		case QUEUE_BYUSER_RES_LIMIT_REACHED:
		case QUEUE_USER_LIMIT_REACHED:
		case QUEUE_USER_RES_LIMIT_REACHED:
		case QUEUE_BYGROUP_JOB_LIMIT_REACHED:
		case QUEUE_BYPROJECT_JOB_LIMIT_REACHED:
		case QUEUE_BYGROUP_RES_LIMIT_REACHED:
		case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
		case QUEUE_GROUP_LIMIT_REACHED:
		case QUEUE_GROUP_RES_LIMIT_REACHED:
		case QUEUE_PROJECT_LIMIT_REACHED:
		case QUEUE_PROJECT_RES_LIMIT_REACHED:
		case NODE_GROUP_LIMIT_REACHED:
		case JOB_UNDER_THRESHOLD:
			make_ineligible(pbs_sd, resresv);
			break;

			/*
			 * The list of ineligible cases must be complete, the remainer are eligible.
			 * Some eligible cases include:
			 * - SERVER_JOB_LIMIT_REACHED
			 * - QUEUE_JOB_LIMIT_REACHED
			 * - CROSS_PRIME_BOUNDARY
			 * - CROSS_DED_TIME_BOUNDRY
			 * - ERR_SPECIAL
			 * - NO_NODE_RESOURCES
			 * - INSUFFICIENT_RESOURCE
			 * - BACKFILL_CONFLICT
			 * - RESERVATION_INTERFERENCE
			 * - PRIME_ONLY
			 * - NONPRIME_ONLY
			 * - DED_TIME
			 * - INSUFFICIENT_QUEUE_RESOURCE
			 * - INSUFFICIENT_SERVER_RESOURCE
			 */
		default:
			make_eligible(pbs_sd, resresv);
			break;
	}

	return;
}

/**
 * @brief
 *		Get AOE name from select of job/reservation.
 *
 * @see
 *		query_jobs
 *		query_reservations
 *
 * @param[in]	select	-	select of job/reservation
 *
 * @return	char *
 * @retval	NULL	: no AOE requested
 * @retval	aoe	: AOE requested
 *
 * @par Side Effects:
 *		None
 *
 * @par	MT-safe: Yes
 *
 */
char*
getaoename(selspec *select)
{
	resource_req *req;

	if (select == NULL)
		return NULL;

	/* we only need to look at 1st chunk since either all request aoe
	 * or none request aoe.
	 */
	req = find_resource_req(select->chunks[0]->req, getallres(RES_AOE));
	if (req != NULL)
		return string_dup(req->res_str);

	return NULL;
}

/**
 * @brief
 *	Get EOE name from select of job/reservation.
 *
 * @see
 *	query_jobs
 *	query_reservations
 *
 * @param[in]	select	  -	select of job/reservation
 *
 * @return	char *
 * @retval	NULL : no EOE requested
 * @retval	eoe  : EOE requested
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
char*
geteoename(selspec *select)
{
	resource_req *req;

	if (select == NULL)
		return NULL;

	/* we only need to look at 1st chunk since either all request eoe
	 * or none request eoe.
	 */
	req = find_resource_req(select->chunks[0]->req, getallres(RES_EOE));
	if (req != NULL)
		return string_dup(req->res_str);

	return NULL;
}

/**
 * @brief
 * 		returns if a job is starving, and if the job is
 *		       starving, it returns a notion of how starving the
 *		       job is.  The higher the number, the more starving.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	sjob	-	the job to check if it's starving
 *
 * @return	starving number
 * @retval	0	: if not starving
 #ifdef NAS
 * @param[in,out]	sjob	-	the job to check, NAS_pri will be updated
 #endif
 *
 */
long
job_starving(status *policy, resource_resv *sjob)
{
	long starve_num = 0;
	time_t etime = 0;
	time_t stime = 0;
	time_t max_starve;

	if (policy == NULL || sjob == NULL)
		return 0;

	if (!sjob->is_job || sjob->job ==NULL)
		return 0;

#ifndef NAS /* localmod 045 */
	if (policy->help_starving_jobs) {
#endif /* localmod 045 */
		/* Running jobs which were starving when they were run continue
		 * to be starving for their life.  It is possible to have starving
		 * jobs preempt lower priority jobs.  If running job was no longer
		 * starving, other starving jobs would preempt it in a subsequent cycle
		 */
		max_starve = conf.max_starve;
#ifdef NAS
		/* localmod 046 */
		max_starve = sjob->job->queue->max_starve;
		/* localmod 045 */
		if (max_starve == 0)
			max_starve = conf.max_starve;
		/* Large-enough setting for max_starve->never starve */
		if (max_starve < Q_SITE_STARVE_NEVER)
#endif
		if (in_runnable_state(sjob) || sjob->job->is_running) {
			if (sjob->job->queue->is_ok_to_run &&
				sjob->job->resv_id ==NULL) {

				if (sjob->server->eligible_time_enable ==1) {
					if (max_starve < sjob->job->eligible_time)
						starve_num = sjob->job->eligible_time;
				}
				else {
					if (sjob->job->etime == UNSPECIFIED)
						etime = sjob->qtime;
					else
						etime = sjob->job->etime;

					if (sjob->job->is_running)
						stime = sjob->job->stime;
					else
						stime = sjob->server->server_time;

					if (etime + max_starve < stime) {
						if (policy->help_starving_jobs) {
							starve_num = sjob->server->server_time +
								stime - etime - max_starve;
						}
					}
				}
#ifdef NAS /* localmod 045 */
				/* localmod 116 */
				site_set_NAS_pri(sjob->job, max_starve, starve_num);
#endif
			}
		}
#ifndef NAS /* localmod 045 */
	}
#endif /* localmod 045 */
	return starve_num;
}

/**
 *	@brief
 *		mark a job starving and handle setting all the
 *			    approprate elements and bits which go with it.
 *
 * @param[in]	sjob	-	the starving job
 * @param[in]	sch_priority	-	the sch_priority of the starving job
 *
 * @return nothing
 */
void
mark_job_starving(resource_resv *sjob, long sch_priority)
{
	if (sjob == NULL || sjob->job == NULL)
		return;

	sjob->job->is_starving = 1;
	sjob->sch_priority = sch_priority;
	schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		sjob->name, (sjob->job->is_running ? "Job was starving when it ran" : "Job is starving"));

	if (conf.dont_preempt_starving)
		sjob->job->can_not_preempt = 1;
}

/**
 * @brief
 * 		mark a job preempted and set ATTR_sched_preempted to
 *	        server time.
 *
 * @param[in]	pbs_sd	-	connection descriptor to pbs server
 * @param[in]	rjob	-	the preempted job
 * @param[in]	server_time	-	time reported by server_info object
 *
 * @return	nothing
 */
void
mark_job_preempted(int pbs_sd, resource_resv *rjob, time_t server_time)
{
	char time_str[MAX_PTIME_SIZE] = {0};
	snprintf(time_str, MAX_PTIME_SIZE, "%ld", server_time);
	update_job_attr(pbs_sd, rjob, ATTR_sched_preempted,
		NULL, time_str, NULL, UPDATE_LATER);
	rjob->job->is_preempted = 1;
	rjob->job->time_preempted = server_time;
}

/**
 * @brief
 * 		updated the estimated.start_time and
 *		 estimated.exec_vnode attributes on a job
 *
 * @param[in]	pbs_sd	-	connection descriptor to pbs server
 * @param[in]	job	-	job to update
 * @param[in]	start_time	-	start time of job
 * @param[in]	exec_vnode	-	exec_vnode of job or NULL to create it from
 *			      				job->nspec_arr
 * @param[in]	force	-	forces attributes to update now -- no checks
 *
 * @return	int
 * @retval	1	: if attributes were successfully updated
 * @retval	0	: if attributes were not updated for a valid reason
 * @retval	-1	: if attributes were not updated for an error
 */
int
update_estimated_attrs(int pbs_sd, resource_resv *job,
	time_t start_time, char *exec_vnode, int force)
{
	struct attrl attr = {0};
	char timebuf[128];
	resource_resv *array = NULL;
	resource_resv *resresv;
	enum update_attr_flags aflags;

	if (job == NULL)
		return -1;

	if (job->is_job && job->job ==NULL)
		return -1;

	if (!force) {
		if (job->job->is_subjob) {
			array = find_resource_resv(job->server->jobs, job->job->array_id);
			if (array != NULL) {
				if (job->job->array_index !=
					range_next_value(array->job->queued_subjobs, -1)) {
					return -1;
				}
			}
			else
				return -1;
		}
		aflags = UPDATE_LATER;
	}
	else {
		aflags = UPDATE_NOW;
		if (job->job->array_id !=NULL)
			array = find_resource_resv(job->server->jobs, job->job->array_id);
	}


	/* create attrl for estimated.exec_vnode to be passed as the 'extra' field
	 * to update_job_attr().  This will cause both attributes to be updated
	 * in one call to pbs_alterjob()
	 */
	attr.name = ATTR_estimated;
	attr.resource = "exec_vnode";
	if (exec_vnode == NULL)
		attr.value = create_execvnode(job->nspec_arr);
	else
		attr.value = exec_vnode;

	snprintf(timebuf, 128, "%ld", (long) start_time);

	if (array)
		resresv = array;
	else
		resresv = job;

	return update_job_attr(pbs_sd, resresv, ATTR_estimated, "start_time",
		timebuf, &attr, aflags);
}

/**
 * @brief
 * 		This function checks if preemption set has been configured as TARGET_NONE
 *          If its found that preempt_targets = TARGET_NONE then this function returns PREEMPT_NONE.
 * @param[in]	res_list	-	list of resources created from comma seperated resource list.
 *
 * @return	int
 * @retval	PREEMPT_NONE	: If preemption set is set to TARGET_NONE
 * @retval	0	: If preemption set is not set as TARGET_NONE
 */
int
check_preempt_targets_for_none(char ** res_list)
{
	char *arg = NULL;
	int i = 0;
	if (res_list == NULL)
		return 0;

	for (arg = res_list[i]; arg != NULL; i++, arg = res_list[i]) {
		if (!strcasecmp(arg, TARGET_NONE)) {
			return PREEMPT_NONE;
		}
	}
	return 0;
}

/**
 * @brief
 * 		checks whether the IFL interface failed because it was a finished job
 *
 * @param[in]	error	-	pbs_errno set by server
 *
 * @retval	1	: if job is a finished job
 * @retval	0	: if job is not a finished job
 */
int
is_finished_job(int error)
{
	switch(error) {
		case PBSE_UNKJOBID:
		case PBSE_HISTJOBID:
			return(1);
		default:
			return(0);
	}
}


/**
 * @brief
 * 		preemption_similarity - Compare two running jobs to see if they have
 *			overlap.  Overlap is defined in terms of preemption.
 *			Can pre-emptee pjob help in running hjob.  In doing this
 *			we look at the full list of reasons hjob can not run and
 *			run a similarity heuristic against the two jobs to see if
 *			they are alike.
 *
 * @param[in]	hjob	-	high priority job
 * @param[in]	pjob	-	job to see if it is similar to the high priority job
 * @param[in]	full_err	-	list of reasons why hjob can not run right now.  It gets
 *                      		created by passing the RETURN_ALL_ERRS to is_ok_to_run()
 * @return	int
 * @retval	1	: jobs are similar
 * @retval	0	: jobs are not similar
 */
int
preemption_similarity(resource_resv *hjob, resource_resv *pjob, schd_error *full_err)
{
	schd_error *cur_err;
	int match = 0;
	schd_resource *res;
	int j;

	for (cur_err = full_err; match == 0 && cur_err != NULL; cur_err = cur_err->next) {
		switch (cur_err->error_code) {
			case QUEUE_JOB_LIMIT_REACHED:
			case QUEUE_RESOURCE_LIMIT_REACHED:
				if (pjob->job->queue == hjob->job->queue)
					match = 1;
				break;
			case SERVER_USER_LIMIT_REACHED:
			case SERVER_USER_RES_LIMIT_REACHED:
			case SERVER_BYUSER_JOB_LIMIT_REACHED:
			case SERVER_BYUSER_RES_LIMIT_REACHED:
				if (strcmp(pjob->user, hjob->user) == 0)
					match = 1;
				break;
			case QUEUE_USER_LIMIT_REACHED:
			case QUEUE_USER_RES_LIMIT_REACHED:
			case QUEUE_BYUSER_JOB_LIMIT_REACHED:
			case QUEUE_BYUSER_RES_LIMIT_REACHED:
				if (pjob->job->queue == hjob->job->queue &&
					strcmp(pjob->user, hjob->user) == 0)
					match = 1;

				break;
			case SERVER_GROUP_LIMIT_REACHED:
			case SERVER_GROUP_RES_LIMIT_REACHED:
			case SERVER_BYGROUP_JOB_LIMIT_REACHED:
			case SERVER_BYGROUP_RES_LIMIT_REACHED:
				if (strcmp(pjob->group, hjob->group) == 0)
					match = 1;
				break;

			case QUEUE_GROUP_LIMIT_REACHED:
			case QUEUE_GROUP_RES_LIMIT_REACHED:
			case QUEUE_BYGROUP_JOB_LIMIT_REACHED:
			case QUEUE_BYGROUP_RES_LIMIT_REACHED:
				if (pjob->job->queue == hjob->job->queue &&
					strcmp(pjob->group, hjob->group) == 0)
					match = 1;
				break;
			case SERVER_PROJECT_LIMIT_REACHED:
			case SERVER_PROJECT_RES_LIMIT_REACHED:
			case SERVER_BYPROJECT_RES_LIMIT_REACHED:
			case SERVER_BYPROJECT_JOB_LIMIT_REACHED:
				if (strcmp(pjob->project, hjob->project) == 0)
					match = 1;
				break;
			case QUEUE_PROJECT_LIMIT_REACHED:
			case QUEUE_PROJECT_RES_LIMIT_REACHED:
			case QUEUE_BYPROJECT_RES_LIMIT_REACHED:
			case QUEUE_BYPROJECT_JOB_LIMIT_REACHED:
				if (pjob->job->queue == hjob->job->queue &&
					strcmp(pjob->project, hjob->project) == 0)
					match = 1;
				break;
			case SERVER_JOB_LIMIT_REACHED:
			case SERVER_RESOURCE_LIMIT_REACHED:
				match = 1;
				break;
			/* Codes from check_nodes(): check_nodes() returns a code for one node.
			 * The code itself doesn't really help us.  What it does do is signal us
			 * that we searched the nodes and didn't find a match.  We need to check if
			 * there are nodes in the exec_vnodes that are similar
			 */
			case NO_AVAILABLE_NODE:
			case NOT_ENOUGH_NODES_AVAIL:
			case NO_NODE_RESOURCES:
			case INVALID_NODE_STATE:
			case INVALID_NODE_TYPE:
			case NODE_JOB_LIMIT_REACHED:
			case NODE_USER_LIMIT_REACHED:
			case NODE_GROUP_LIMIT_REACHED:
			case NODE_NO_MULT_JOBS:
			case NODE_UNLICENSED:
			case NODE_HIGH_LOAD:
			case INSUFFICIENT_RESOURCE:
			case AOE_NOT_AVALBL:
			case PROV_RESRESV_CONFLICT:
			case NO_FREE_NODES:
			case NO_TOTAL_NODES:
			case NODE_NOT_EXCL:
			case CANT_SPAN_PSET:
			case IS_MULTI_VNODE:
			case RESERVATION_CONFLICT:
			case SET_TOO_SMALL:

				if (hjob->ninfo_arr != NULL && pjob->ninfo_arr != NULL) {
					for (j = 0; hjob->ninfo_arr[j] != NULL && !match; j++) {
						if (find_node_by_rank(pjob->ninfo_arr, hjob->ninfo_arr[j]->rank) != NULL)
							match = 1;
					}
				}

				break;
			case INSUFFICIENT_QUEUE_RESOURCE:
				if (hjob->job->queue == pjob->job->queue) {
					for (res = hjob->job->queue->qres; res != NULL; res = res->next) {
						if (res->avail != SCHD_INFINITY)
							if (find_resource_req(pjob->resreq, res->def) != NULL)
								match = 1;
					}
				}
				break;
			case INSUFFICIENT_SERVER_RESOURCE:
				for (res = hjob->server->res; res != NULL; res = res->next) {
					if (res->avail != SCHD_INFINITY)
						if (find_resource_req(pjob->resreq, res->def) != NULL)
							match = 1;
				}
				break;
			default:
				/* Something we didn't expect, err on the side of caution */
				match = 1;
				break;
		}
	}
	return match;
}

/**
 * @brief Create the resources_released and resource_released_list for a job 
 *	    and return the resources_released in exec_vnode string form
 *
 * @param[in] policy - policy object
 * @param[in] pjob - Job structure using which resources_released string is created
 *
 * @retval - char* 
 * @return - string of resources released similar to exec_vnode format
 */
char *create_res_released(status *policy, resource_resv *pjob)
{
	if (pjob->job->resreleased == NULL) {
		pjob->job->resreleased = create_res_released_array(policy, pjob);
		if (pjob->job->resreleased == NULL) {
			return NULL;
		}
		pjob->job->resreq_rel = create_resreq_rel_list(policy, pjob);
	}
	return create_execvnode(pjob->job->resreleased);
}

/**
 * @brief This function populates resreleased job structure for a particular job.
 *	  It does so by duplicating the job's exec_vnode and only keeping the 
 *	  consumable resources in policy->rel_on_susp
 *
 * @param[in] policy - policy object
 * @param[in] resresv - Job to create resources_released
 *
 * @return nspec **
 * @retval nspec array of released resources
 * @retval NULL
 *
 */
nspec **create_res_released_array(status *policy, resource_resv *resresv)
{
	nspec **nspec_arr = NULL;
	int i = 0;
	resource_req *req;

	if ((resresv == NULL) || (resresv->nspec_arr == NULL) || (resresv->ninfo_arr == NULL))
		return NULL;

	nspec_arr = dup_nspecs(resresv->nspec_arr, resresv->ninfo_arr);
	if (nspec_arr == NULL)
		return NULL;
	if (policy->rel_on_susp != NULL) {
		for (i = 0; nspec_arr[i] != NULL; i++) {
			for (req = nspec_arr[i]->resreq; req != NULL; req = req->next) {
				if (req->type.is_consumable == 1 && resdef_exists_in_array(policy->rel_on_susp, req->def) ==  0)
					req->amount = 0;
			}
		}
	}
	return nspec_arr;
}

/**
 * @brief create a resource_rel array for a job by accumulating all of the RASSN
 *	    resources in a resources_released nspec array.
 * 
 * @note only uses RASSN resources on the sched_config resources line
 * 
 * @param policy - policy info
 * @param pjob -  resource reservation structure
 * @return resource_req *
 * @retval newly created resreq_rel array
 * @retval NULL on error
 */
resource_req *create_resreq_rel_list(status *policy, resource_resv *pjob)
{
	resource_req *resreq_rel = NULL;
	resource_req *rel;
	resource_req *req;
	if (policy == NULL || pjob == NULL)
		return NULL;

	for (req = pjob->resreq; req != NULL; req = req->next) {
		if (resdef_exists_in_array(policy->resdef_to_check_rassn, req->def)) {
			if ((policy->rel_on_susp != NULL) && resdef_exists_in_array(policy->rel_on_susp, req->def) == 0)
				continue;
			rel = find_alloc_resource_req(resreq_rel, req->def);
			if (rel != NULL) {
				rel->amount += req->amount;
				if (resreq_rel == NULL)
					resreq_rel = rel;
			}
		}
	}
	return resreq_rel;
}

/**
 * @brief extend the soft walltime of job.  A job's soft_walltime will be extended by 100% of its
 * 		original soft_walltime.  If this extension would go past the job's normal walltime
 * 		the soft_walltime is set to the normal walltime.
 * @param[in] policy - policy info
 * @param[in] resresv - job to extend soft walltime
 * @param[in] server_time - current time on the sinfo
 * @return extended soft walltime duration
 */
long
extend_soft_walltime(resource_resv *resresv, time_t server_time)
{
	resource_req *walltime_req;
	resource_req *soft_walltime_req;

	int extension = 0;
	int num_ext_over;

	long job_duration = UNSPECIFIED;
	long extended_duration = UNSPECIFIED;


	if (resresv == NULL)
		return UNSPECIFIED;

	soft_walltime_req = find_resource_req(resresv->resreq, getallres(RES_SOFT_WALLTIME));
	walltime_req = find_resource_req(resresv->resreq, getallres(RES_WALLTIME));

	if (soft_walltime_req == NULL) { /* Nothing to extend */
		if(walltime_req != NULL)
			return walltime_req->amount;
		else
			return JOB_INFINITY;
	}


	job_duration = soft_walltime_req->amount;

	/* number of times the job has been extended */
	num_ext_over = (server_time - resresv->job->stime) / job_duration;

	extension = num_ext_over * job_duration;
	extended_duration = job_duration + extension;
	if (walltime_req != NULL) {
		if (extended_duration > walltime_req->amount) {
			extended_duration = walltime_req->amount;
		}
	}
	return extended_duration;
}

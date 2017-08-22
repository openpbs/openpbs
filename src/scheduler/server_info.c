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
 * @file    server_info.c
 *
 * @brief
 * server_info.c - contains functions related to server_info structure.
 *
 * Functions included are:
 * 	query_server()
 * 	query_server_info()
 * 	query_server_dyn_res()
 * 	query_sched_obj()
 * 	find_alloc_resource()
 * 	find_alloc_resource_by_str()
 * 	find_resource_by_str()
 * 	find_resource()
 * 	free_server_info()
 * 	free_resource_list()
 * 	free_resource()
 * 	new_server_info()
 * 	new_resource()
 * 	create_resource()
 * 	add_resource_list()
 * 	add_resource_value()
 * 	add_resource_str_arr()
 * 	add_resource_bool()
 * 	free_server()
 * 	update_server_on_run()
 * 	update_server_on_end()
 * 	create_server_arrays()
 * 	check_run_job()
 * 	check_exit_job()
 * 	check_run_resv()
 * 	check_susp_job()
 * 	check_job_not_in_reservation()
 * 	check_resv_running_on_node()
 * 	dup_server_info()
 * 	dup_resource_list()
 * 	dup_selective_resource_list()
 * 	dup_ind_resource_list()
 * 	dup_resource()
 * 	is_unassoc_node()
 * 	new_counts()
 * 	free_counts()
 * 	free_counts_list()
 * 	dup_counts()
 * 	dup_counts_list()
 * 	find_counts()
 * 	find_alloc_counts()
 * 	update_counts_on_run()
 * 	update_counts_on_end()
 * 	counts_max()
 * 	update_universe_on_end()
 * 	set_resource()
 * 	find_indirect_resource()
 * 	resolve_indirect_resources()
 * 	update_preemption_on_run()
 * 	read_formula()
 * 	new_status()
 * 	dup_status()
 * 	free_status()
 * 	free_queue_list()
 * 	create_total_counts()
 * 	update_total_counts()
 * 	update_total_counts_on_end()
 * 	refresh_total_counts()
 * 	get_sched_rank()
 * 	add_queue_to_list()
 * 	find_queue_list_by_priority()
 * 	append_to_queue_list()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <ctype.h>
#include <pbs_ifl.h>
#include <pbs_error.h>
#include <log.h>
#include <rpp.h>
#include <pbs_share.h>
#include "server_info.h"
#include "constant.h"
#include "queue_info.h"
#include "job_info.h"
#include "misc.h"
#include "config.h"
#include "node_info.h"
#include "globals.h"
#include "resv_info.h"
#include "sort.h"
#include "resource_resv.h"
#include "state_count.h"
#include "node_partition.h"
#include "resource.h"
#include "assert.h"
#include "limits_if.h"
#include "resource.h"
#include "pbs_internal.h"
#include "simulate.h"
#include "fairshare.h"
#include "check.h"
#include "pbs_sched.h"
#include "fifo.h"
#ifdef NAS
#include "site_code.h"
#endif


/**
 *	@brief
 *		creates a structure of arrays consisting of a server
 *		and all the queues and jobs that reside in that server
 *
 * @par Order of Query
 *		query_server()
 *      -> query_sched()
 *	 	-> query_nodes()
 *	 	-> query_queues()
 *	    -> query_jobs()
 *	 	->query_reservations()
 *
 * @param[in]	pol		-	input policy structure - will be dup'd
 * @param[in]	pbs_sd	-	connection to pbs_server
 *
 * @return	the server_info struct
 * @retval	server_info -> policy - policy structure for cycle
* @retval	NULL	: error
 *
 */
server_info *
query_server(status *pol, int pbs_sd)
{
	struct batch_status *server;	/* info about the server */
	struct batch_status *sched;	/* info about the server's scheduler object */
	struct batch_status *bs_resvs = NULL;	/* batch status of the reservations */
	server_info *sinfo;		/* scheduler internal form of server info */
	queue_info **qinfo;		/* array of queues on the server */
	counts *cts;			/* used to count running per user/grp */
	int num_express_queues = 0;	/* number of express queues */
	int i;
	int size;
	char *errmsg;
	resource_resv **jobs_not_in_reservations;
	status *policy;

	if (pol == NULL)
		return NULL;

	if (update_resource_defs(pbs_sd) == 0) {
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_SCHED, LOG_WARNING, "resources",
			"Failed to update global resource definition arrays");
		return NULL;
	}

	/* get server information from pbs server */
	if ((server = pbs_statserver(pbs_sd, NULL, NULL)) == NULL) {
		errmsg = pbs_geterrmsg(pbs_sd);
		if (errmsg == NULL)
			errmsg = "";
		sprintf(log_buffer, "pbs_statserver failed: %s (%d)", errmsg, pbs_errno);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_SERVER, LOG_NOTICE, "server_info",
			log_buffer);
		return NULL;
	}

	/* convert batch_status structure into server_info structure */
	if ((sinfo = query_server_info(pol, server)) == NULL) {
		pbs_statfree(server);
		return NULL;
	}

	/* We dup'd the policy structure for the cycle */
	policy = sinfo->policy;

	/* set the time to the current time */
	sinfo->server_time = policy->current_time;

	if( query_server_dyn_res(sinfo) == -1 ) {
		pbs_statfree(server);
		sinfo -> fairshare = NULL;
		free_server( sinfo, 0 );
		return NULL;
	}


	if ((sched = pbs_statsched(pbs_sd, PBS_DFLT_SCHED_NAME, NULL, NULL)) == NULL) {
		errmsg = pbs_geterrmsg(pbs_sd);
		if (errmsg == NULL)
			errmsg = "";
		sprintf(log_buffer, "pbs_statsched failed: %s (%d)", errmsg, pbs_errno);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_SERVER, LOG_NOTICE, "server_info",
			log_buffer);
		pbs_statfree(server);
		sinfo->fairshare = NULL;
		free_server(sinfo, 0);
		return NULL;
	}
	query_sched_obj(policy, sched, sinfo);
	pbs_statfree(sched);


	/* to avoid a possible race condition in which the time it takes to
	 * query nodes is long enough that a reservation may have crossed
	 * into running state, we stat the reservation just before nodes and
	 * will populate internal data structures based on this batch status
	 * after all other data is queried
	 */
	if (dflt_sched)
		bs_resvs = stat_resvs(pbs_sd);

	/* get the nodes, if any - NOTE: will set sinfo -> num_nodes */
	if ((sinfo->nodes = query_nodes(pbs_sd, sinfo)) == NULL) {
		pbs_statfree(server);
		sinfo->fairshare = NULL;
		free_server(sinfo, 0);
		return NULL;
	}

	/* sort the nodes before we filter them down to more useful lists */
	if (policy->node_sort[0].res_name != NULL)
		qsort(sinfo->nodes, sinfo->num_nodes, sizeof(node_info *),
			multi_node_sort);

	/* get the queues */
	if ((sinfo->queues = query_queues(policy, pbs_sd, sinfo)) == NULL) {
		pbs_statfree(server);
		sinfo->fairshare = NULL;
		free_server(sinfo, 0);
		return NULL;
	}

	if (sinfo->has_nodes_assoc_queue)
		sinfo->unassoc_nodes =
			node_filter(sinfo->nodes, sinfo->num_nodes, is_unassoc_node, NULL, 0);
	else
		sinfo->unassoc_nodes = sinfo->nodes;

	/* count the queues and total up the individual queue states
	 * for server totals. (total up all the state_count structs)
	 */
	qinfo = sinfo->queues;
	while (*qinfo != NULL) {
		sinfo->num_queues++;
		total_states(&(sinfo->sc), &((*qinfo)->sc));

		if ((*qinfo)->priority >= conf.preempt_queue_prio)
			num_express_queues++;

		qinfo++;
	}

	if (num_express_queues > 1)
		sinfo->has_mult_express = 1;


	/* sort the queues before we collect the jobs list (i.e. set_jobs())
	 * in the case we don't sort the jobs and don't have by_queue turned on
	 */
	if ((policy->round_robin == 1) || (policy->by_queue == 1))
		qsort(sinfo->queues, sinfo->num_queues, sizeof(queue_info *),
			cmp_queue_prio_dsc);
	if (policy->round_robin == 1) {
		int ret_val;
		/* queues are already sorted in descending order of their priority */
		for (i = 0; i < sinfo->num_queues; i++) {
			ret_val = add_queue_to_list(&sinfo->queue_list, sinfo->queues[i]);
			if (ret_val == 0) {
				sinfo->fairshare = NULL;
				free_server(sinfo, 1);
				return NULL;
			}
		}
	}

	/* get reservations, if any - NOTE: will set sinfo -> num_resvs */
	sinfo->resvs = query_reservations(sinfo, bs_resvs);

	if (create_server_arrays(sinfo) == 0) { /* bad stuff happened */
		sinfo->fairshare = NULL;
		free_server(sinfo, 1);
		return NULL;
	}
#ifdef NAS /* localmod 050 */
	/* Give site a chance to tweak values before jobs are sorted */
	if (site_tidy_server(sinfo) == 0) {
		free_server(sinfo, 1);
		return NULL;
	}
#endif /* localmod 050 */

	/* create res_to_check arrays based on current jobs/resvs */
	policy->resdef_to_check = collect_resources_from_requests(sinfo->all_resresv);
	policy->resdef_to_check_no_hostvnode = (resdef **)
		filter_array((void **) policy->resdef_to_check,
		no_hostvnode, NULL, NO_FLAGS);
	policy->resdef_to_check_rassn = (resdef **)
		filter_array((void **) policy->resdef_to_check,
		def_rassn, NULL, NO_FLAGS);
	policy->resdef_to_check_rassn_select = (resdef **)
		filter_array((void **) policy->resdef_to_check,
		def_rassn_select, NULL, NO_FLAGS);

	sinfo->calendar = create_event_list(sinfo);

	sinfo->running_jobs =
		resource_resv_filter(sinfo->jobs, sinfo->sc.total, check_run_job,
		NULL, FILTER_FULL);
	sinfo->exiting_jobs = resource_resv_filter(sinfo->jobs,
		sinfo->sc.total, check_exit_job, NULL, 0);
	if (sinfo->running_jobs == NULL || sinfo->exiting_jobs ==NULL) {
		sinfo->fairshare = NULL;
		free_server(sinfo, 1);
		return NULL;
	}

	jobs_not_in_reservations = resource_resv_filter(sinfo->jobs,
		sinfo->sc.total,
		check_job_not_in_reservation, NULL, 0);

	if (sinfo->has_soft_limit || sinfo->has_hard_limit) {
		counts *allcts;

		allcts = find_alloc_counts(sinfo->alljobcounts, "o:" PBS_ALL_ENTITY);
		if (sinfo->alljobcounts == NULL)
			sinfo->alljobcounts = allcts;

		/* set the user, group , project counts */
		for (i = 0; sinfo->running_jobs[i] != NULL; i++) {
			cts = find_alloc_counts(sinfo->user_counts,
				sinfo->running_jobs[i]->user);
			if (sinfo->user_counts == NULL)
				sinfo->user_counts = cts;

			update_counts_on_run(cts, sinfo->running_jobs[i]->resreq);

			cts = find_alloc_counts(sinfo->group_counts,
				sinfo->running_jobs[i]->group);

			if (sinfo->group_counts == NULL)
				sinfo->group_counts = cts;

			update_counts_on_run(cts, sinfo->running_jobs[i]->resreq);

			cts = find_alloc_counts(sinfo->project_counts,
				sinfo->running_jobs[i]->project);

			if (sinfo->project_counts == NULL)
				sinfo->project_counts = cts;

			update_counts_on_run(cts, sinfo->running_jobs[i]->resreq);

			update_counts_on_run(allcts, sinfo->running_jobs[i]->resreq);
		}
		create_total_counts(sinfo, NULL, NULL, SERVER);
	}

	policy->equiv_class_resdef = create_resresv_sets_resdef(policy, sinfo);
	sinfo->equiv_classes = create_resresv_sets(policy, sinfo);

	size = sinfo->sc.running + sinfo->sc.exiting + sinfo->sc.suspended
		+ sinfo->sc.userbusy;
	/* To avoid duplicate accounting of jobs on nodes, we are only interested in
	 * jobs that are bound to the server nodes and not those bound to reservation
	 * nodes, which are accounted for by collect_jobs_on_nodes in
	 * query_reservation, hence the use of the filtered list of jobs
	 */
	collect_jobs_on_nodes(sinfo->nodes, jobs_not_in_reservations, size);

	/* Now that the job_arr is created, garbage collect the jobs in resv list */
	free(jobs_not_in_reservations);

	collect_resvs_on_nodes(sinfo->nodes, sinfo->resvs, sinfo->num_resvs);
	/* Create the node equivalence classes*/
	for (i = 0; sinfo->nodes[i] != NULL; i++) {
		node_info *ninfo = sinfo->nodes[i];
		ninfo->nodesig = create_resource_signature(ninfo  ->res,
			policy->resdef_to_check_no_hostvnode, CHECK_ALL_BOOLS);
		ninfo->nodesig_ind = add_str_to_unique_array(&(sinfo->nodesigs),
			ninfo->nodesig);

		if(ninfo->has_ghost_job)
			create_resource_assn_for_node(ninfo);

	}

	adjust_alter_resv_nodes(sinfo->resvs, sinfo->nodes);

	/* Create placement sets  after collecting jobs on nodes because
	 * we don't want to account for resources consumed by ghost jobs
	 */
	create_placement_sets(policy, sinfo);

	pbs_statfree(server);

	return sinfo;
}

/**
 * @brief
 * 		takes info from a batch_status structure about
 *		a server into a server_info structure for easy access
 *
 * @param[in]	pol		-	scheduler policy structure
 * @param[in]	server	-	batch_status struct of server info
 *							chain possibly NULL
 *
 * @return	newly allocated and filled server_info struct
 *
 */
server_info *
query_server_info(status *pol, struct batch_status *server)
{
	struct attrl *attrp;	/* linked list of attributes */
	server_info *sinfo;	/* internal scheduler structure for server info */
	schd_resource *resp;	/* a resource to help create the resource list */
	sch_resource_t count;	/* used to convert string -> integer */
	char *endp;		/* used with strtol() */
	status *policy;

	if (pol == NULL || server == NULL)
		return NULL;

	if ((sinfo = new_server_info(1)) == NULL)
		return NULL;		/* error */

	if (sinfo->liminfo == NULL)
		return NULL;

	if ((sinfo->name = string_dup(server->name)) == NULL) {
		free_server_info(sinfo);
		return NULL;
	}

	if ((sinfo->policy = dup_status(pol)) == NULL) {
		free_server_info(sinfo);
		return NULL;
	}

	policy = sinfo->policy;

	attrp = server->attribs;

	while (attrp != NULL) {
		if (is_reslimattr(attrp)) {
			(void) lim_setlimits(attrp, LIM_RES, sinfo->liminfo);
			if(strstr(attrp->value, "u:") != NULL)
				sinfo->has_user_limit = 1;
			if(strstr(attrp->value, "g:") != NULL)
				sinfo->has_grp_limit = 1;
			if(strstr(attrp->value, "p:") != NULL)
				sinfo->has_proj_limit = 1;
		}
		else if (is_runlimattr(attrp)) {
			(void) lim_setlimits(attrp, LIM_RUN, sinfo->liminfo);
			if(strstr(attrp->value, "u:") != NULL)
				sinfo->has_user_limit = 1;
			if(strstr(attrp->value, "g:") != NULL)
				sinfo->has_grp_limit = 1;
			if(strstr(attrp->value, "p:") != NULL)
				sinfo->has_proj_limit = 1;
		}
		else if (is_oldlimattr(attrp)) {
			char *limname = convert_oldlim_to_new(attrp);
			(void) lim_setlimits(attrp, LIM_OLD, sinfo->liminfo);

			if(strstr(limname, "u:") != NULL)
				sinfo->has_user_limit = 1;
			if(strstr(limname, "g:") != NULL)
				sinfo->has_grp_limit = 1;
			/* no need to check for project limits because there were no old style project limits */
		}
		else if (!strcmp(attrp->name, ATTR_FLicenses)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;

			sinfo->flt_lic = count;
		}
		else if (!strcmp(attrp->name, ATTR_NodeGroupEnable)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				sinfo->node_group_enable = 1;
			else
				sinfo->node_group_enable = 0;
		}
		else if (!strcmp(attrp->name, ATTR_NodeGroupKey))
			sinfo->node_group_key = break_comma_list(attrp->value);
		else if (!strcmp(attrp->name, ATTR_job_sort_formula)) {
			sinfo->job_formula = read_formula();
			if (policy->sort_by[1].res_name != NULL) /* 0 is the formula itself */
				schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG,
					"query_server",
					"Job sorting formula and job_sort_key are incompatible.  "
					"The job sorting formula will be used.");

		} else if (!strcmp(attrp->name, ATTR_rescavail)) { /* resources_available*/
			resp = find_alloc_resource_by_str(sinfo->res, attrp->resource);

			if (resp != NULL) {
				if (sinfo->res == NULL)
					sinfo->res = resp;

				if (set_resource(resp, attrp->value, RF_AVAIL) == 0) {
					free_server_info(sinfo);
					return NULL;
				}
			}
		} else if (!strcmp(attrp->name, ATTR_rescassn)) { /* resources_assigned */
			resp = find_alloc_resource_by_str(sinfo->res, attrp->resource);
			if (sinfo->res == NULL)
				sinfo->res = resp;
			if (resp != NULL) {
				if (set_resource(resp, attrp->value, RF_ASSN) == 0) {
					free_server_info(sinfo);
					return NULL;
				}
			}
		} else if (!strcmp(attrp->name, ATTR_rpp_retry)) { /* rpp_retry */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = RPP_RETRY;

			/*
			 ** The value for rpp_retry can be zero or a positive value.
			 ** Zero means "no retries" or "send it once".
			 */
			if (count >= 0 && (int)count != rpp_retry) {
				sprintf(log_buffer, "rpp_retry changed from %d to %d",
					rpp_retry, (int)count);
				log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
					LOG_DEBUG, __func__, log_buffer);
				rpp_retry = (int)count;
			}
		}
		else if (!strcmp(attrp->name, ATTR_rpp_highwater)) { /* rpp_highwater */
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = RPP_HIGHWATER;

			/*
			 ** The value for rpp_highwater must be greater than zero.
			 ** It is the number of packets allowed to be "on the wire"
			 ** at any give time.
			 */
			if (count > 0 && (int)count != rpp_highwater) {
				sprintf(log_buffer, "rpp_highwater changed from %d to %d",
					rpp_highwater, (int)count);
				log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
					LOG_DEBUG, __func__, log_buffer);
				rpp_highwater = (int)count;
			}
		}
		else if (!strcmp(attrp->name, ATTR_EligibleTimeEnable)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				sinfo->eligible_time_enable = 1;
			else
				sinfo->eligible_time_enable = 0;
		}
		else if (!strcmp(attrp->name, ATTR_ProvisionEnable)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				sinfo->provision_enable = 1;
			else
				sinfo->provision_enable = 0;
		}
		else if (!strcmp(attrp->name, ATTR_power_provisioning)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				sinfo->power_provisioning = 1;
			else
				sinfo->power_provisioning = 0;
		}
		else if (!strcmp(attrp->name, ATTR_backfill_depth)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp == '\0')
				sinfo->policy->backfill_depth = count;
			if (count == 0)
				sinfo->policy->backfill = 0;
		}
		else if(!strcmp(attrp->name, ATTR_restrict_res_to_release_on_suspend)) {
			char **resl;
			resl = break_comma_list(attrp->value);
			if(resl != NULL) {
				policy->rel_on_susp = resstr_to_resdef(resl);
				free_string_array(resl);
			}
		}

		attrp = attrp->next;
	}

	if (has_hardlimits(sinfo->liminfo))
		sinfo->has_hard_limit = 1;
	if (has_softlimits(sinfo->liminfo))
		sinfo->has_soft_limit = 1;

	/* Since we want to keep track of fairshare changes from cycle to cycle
	 * copy in the global fairshare tree root.  Be careful to not free it
	 * at the end of the cycle.
	 */
	sinfo->fairshare = conf.fairshare;
#ifdef NAS /* localmod 034 */
	site_set_share_head(sinfo);
#endif /* localmod 034 */

	return sinfo;
}

/**
 * @brief
 * 		execute all configured server_dyn_res scripts
 *
 * @param[in]	sinfo	-	server info
 *
 * @retval	0	: on success
 * @retval -1	: on error
 */
int
query_server_dyn_res(server_info *sinfo)
{
	int i, k;
	int pipe_err;
	char res_zero[] = "0";	/* dynamic res failure implies resource <-0 */
	char buf[256];		/* buffer for reading from pipe */
	schd_resource *res;		/* used for updating node resources */
	FILE *fp;			/* for popen() for res_assn */
#ifdef WIN32
	struct  pio_handles	  pio;  /* for win_popen() for res_assn */
	char			  cmd_line[512];
#endif

	for (i = 0; i < MAX_SERVER_DYN_RES && conf.dynamic_res[i].res != NULL; i ++) {
		res = find_alloc_resource_by_str(sinfo->res, conf.dynamic_res[i].res);
		if (res != NULL) {
			if (sinfo->res == NULL)
				sinfo->res = res;

			pipe_err = errno = 0;
#ifdef	WIN32
			/* In Windows, don't use popen() as this crashes if COMSPEC not set */
			/* also, let's quote command line so that paths with spaces can be */
			/* executed. */
			snprintf(cmd_line, sizeof(cmd_line), "\"%s\"",
				conf.dynamic_res[i].program);

			if (((win_popen(cmd_line, "r", &pio, NULL) == 0) ||
				((k = win_pread(&pio, buf, 255)) <= 0))) {
				pipe_err = errno;
				k = 0;
			}
			if (pio.hReadPipe_out != INVALID_HANDLE_VALUE) /* did win_popen() succeed? */
				win_pclose(&pio);
#else
			if (((fp = popen(conf.dynamic_res[i].program, "r")) == NULL) ||
				(fgets(buf, 256, fp) == NULL)) {
				pipe_err = errno;
				k = 0;
			}
			else
				k = strlen(buf);
			if (fp != NULL)
				pclose(fp);
#endif
			if (k > 0) {
				buf[k] = '\0';
				/* chop \r or \n from buf so that is_num() doesn't think it's a str */
				while (--k) {
					if ((buf[k] != '\n') && (buf[k] != '\r'))
						break;
					buf[k] = '\0';
				}

				if (set_resource(res, buf, RF_AVAIL) == 0) {
					return -1;
				}
			}
			else {
				if (pipe_err != 0)
					snprintf(buf, sizeof(buf), "Can't pipe to program %s: %s",
						conf.dynamic_res[i].program, strerror(pipe_err));
				else
					snprintf(buf, sizeof(buf), "Error piping to program %s.",
						conf.dynamic_res[i].program);
				schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG,
					"server_dyn_res", buf);
				(void) set_resource(res, res_zero, RF_AVAIL);
			}
			if (res->type.is_non_consumable) {
				snprintf(log_buffer, sizeof(log_buffer), "%s = %s",
					conf.dynamic_res[i].program, res_to_str(res, RF_AVAIL));
			}
			else {
				snprintf(log_buffer, sizeof(log_buffer), "%s = %s (\"%s\")",
					conf.dynamic_res[i].program, res_to_str(res, RF_AVAIL), buf);
			}
			schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SERVER, LOG_DEBUG,
				"server_dyn_res", log_buffer);
		}
	}

	if (i == MAX_SERVER_DYN_RES) { /* reached max and stopped */
		sprintf(buf, "Reached max number of server_dyn_res of %d",
			MAX_SERVER_DYN_RES);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_SERVER, LOG_INFO, "server_dyn_res",
			buf);
	}

	return 0;
}

/**
 * @brief
 * 		query_sched_obj - query the server's scheduler object and
 *		convert attributes to scheduler's internal data structures
 *
 * @param[in,out]	policy 	-	policy object to set policy on
 * @param[in]		sched 	-	result of pbs_statsched()
 * @param[in]		sinfo 	-	server_info to store sched obj attributes
 *
 * @return	int
 *	@retval	1	: success
 *	@retval	0	: failure
 *
 */
int
query_sched_obj(status *policy, struct batch_status *sched, server_info *sinfo)
{
	struct attrl *attrp;          /* linked list of attributes from server */

	if (sched == NULL || sinfo == NULL)
		return 0;

	attrp = sched->attribs;

	if (pbs_conf.pbs_use_tcp == 1) {
		/* set throughput mode to 1 by default */
		sinfo->throughput_mode = 1;
	}

	while (attrp != NULL) {
		if (!strcmp(attrp->name, ATTR_sched_cycle_len)) {
			sinfo->sched_cycle_len = res_to_num(attrp->value, NULL);
		}
		else if (!strcmp(attrp->name, ATTR_do_not_span_psets)) {
			sinfo->dont_span_psets = res_to_num(attrp->value, NULL);
		}
		else if (!strcmp(attrp->name, ATTR_only_explicit_psets)) {
			policy->only_explicit_psets = res_to_num(attrp->value, NULL);
		}
		else if (!strcmp(attrp->name, ATTR_sched_preempt_enforce_resumption)) {
			if (!strcasecmp(attrp->value, ATR_FALSE))
				sinfo->enforce_prmptd_job_resumption = 0;
			else
				sinfo->enforce_prmptd_job_resumption = 1;
		}
		else if (!strcmp(attrp->name, ATTR_preempt_targets_enable)) {
			if (!strcasecmp(attrp->value, ATR_FALSE))
				sinfo->preempt_targets_enable = 0;
			else
				sinfo->preempt_targets_enable = 1;
		}
		else if (!strcmp(attrp->name, ATTR_job_sort_formula_threshold)) {
			policy->job_form_threshold_set = 1;
			policy->job_form_threshold = res_to_num(attrp->value, NULL);
		} else if (!strcmp(attrp->name, ATTR_throughput_mode)) {
			sinfo->throughput_mode = res_to_num(attrp->value, NULL);
		} else if (!strcmp(attrp->name, ATTR_opt_backfill_fuzzy)) {
			if (!strcasecmp(attrp->value, "off"))
				sinfo->opt_backfill_fuzzy_time = BF_OFF;
			else if (!strcasecmp(attrp->value, "low")) sinfo->opt_backfill_fuzzy_time = BF_LOW;
			else if (!strcasecmp(attrp->value, "med") || !strcasecmp(attrp->value, "medium"))
				sinfo->opt_backfill_fuzzy_time = BF_MED;
			else if (!strcasecmp(attrp->value, "high"))
				sinfo->opt_backfill_fuzzy_time = BF_HIGH;
			else
				sinfo->opt_backfill_fuzzy_time = BF_DEFAULT;
		}
		attrp = attrp->next;
	}

	return 1;
}

/**
 * @brief
 * 		try and find a resource by resdef, and if it is not
 *		there, allocate space for it and add it to the resource list
 *
 * @param[in]	resplist	- 	the resource list
 * @param[in]	name 		-	the name of the resource
 *
 * @return	schd_resource
 * @retval	NULL	: error
 *
 * @par MT-Safe:	no
 */
schd_resource *
find_alloc_resource(schd_resource *resplist, resdef *def)
{
	schd_resource *resp;		/* used to search through list of resources */
	schd_resource *prev = NULL;	/* the previous resources in the list */

	if (def == NULL)
		return NULL;

	resp = resplist;
	for (resp = resplist; resp != NULL && resp->def != def; resp = resp->next) {
		prev = resp;
	}

	if (resp == NULL) {
		if ((resp = new_resource()) == NULL)
			return NULL;

		resp->def = def;
		resp->type = def->type;
		resp->name = def->name;

		if (prev != NULL)
			prev->next = resp;
	}

	return resp;
}

/**
 * @brief
 * 		try and find a resource by name, and if it is not
 *		there, allocate space for it and add it to the resource list
 *
 * @param[in]	resplist 	- 	the resource list
 * @param[in]	name 		- 	the name of the resource
 *
 * @return	schd_resource
 * @retval	NULL :	Error
 *
 * @par MT-Safe:	no
 */
schd_resource *
find_alloc_resource_by_str(schd_resource *resplist, char *name)
{
	schd_resource *resp;		/* used to search through list of resources */
	schd_resource *prev = NULL;	/* the previous resources in the list */

	if (name == NULL)
		return NULL;

	for (resp = resplist; resp != NULL && strcmp(resp->name, name);
		resp = resp->next) {
		prev = resp;
	}

	if (resp == NULL) {
		if ((resp = create_resource(name, NULL, RF_NONE)) == NULL)
			return NULL;

		if (prev != NULL)
			prev->next = resp;
	}

	return resp;
}

/**
 * @brief
 * 		finds a resource by string in a resource list
 *
 * @param[in]	reslist - 	the resource list
 * @param[in]	name	- 	the name of the resource
 *
 * @return	schd_resource
 * @retval	NULL	: if not found
 *
 * @par MT-Safe:	no
 */
schd_resource *
find_resource_by_str(schd_resource *reslist, const char *name)
{
	schd_resource *resp;	/* used to search through list of resources */

	if (reslist == NULL || name == NULL)
		return NULL;

	resp = reslist;

	while (resp != NULL && strcmp(resp->name, name))
		resp = resp->next;

	return resp;
}
/**
 * @brief
 * 		find resource by resource definition
 *
 * @param 	reslist - 	resource list to search
 * @param 	def 	- 	resource definition to search for
 *
 * @return	the found resource
 * @retval	NULL	: if not found
 */
schd_resource *
find_resource(schd_resource *reslist, resdef *def)
{
	schd_resource *resp;

	if (reslist == NULL || def == NULL)
		return NULL;

	resp = reslist;

	while (resp != NULL && resp->def != def)
		resp = resp->next;

	return resp;
}

/**
 * @brief
 * 		free_server_info - free the space used by a server_info
 *		structure
 *
 * @param[in]	sinfo	-	the server_info structure to free
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
free_server_info(server_info *sinfo)
{
	if (sinfo->name != NULL)
		free(sinfo->name);
	if (sinfo->jobs != NULL)
		free(sinfo->jobs);
	if (sinfo->all_resresv != NULL)
		free(sinfo->all_resresv);
	if (sinfo->running_jobs != NULL)
		free(sinfo->running_jobs);
	if (sinfo->exiting_jobs != NULL)
		free(sinfo->exiting_jobs);
	/* if we don't have nodes associated with queues, this is a reference */
	if (sinfo->has_nodes_assoc_queue == 0)
		sinfo->unassoc_nodes = NULL;
	else if (sinfo->unassoc_nodes != NULL)
		free(sinfo->unassoc_nodes);
	if (sinfo->alljobcounts != NULL)
		free_counts_list(sinfo->alljobcounts);
	if (sinfo->group_counts != NULL)
		free_counts_list(sinfo->group_counts);
	if (sinfo->project_counts != NULL)
		free_counts_list(sinfo->project_counts);
	if (sinfo->user_counts != NULL)
		free_counts_list(sinfo->user_counts);
	if (sinfo->total_alljobcounts != NULL)
		free_counts_list(sinfo->total_alljobcounts);
	if (sinfo->total_group_counts != NULL)
		free_counts_list(sinfo->total_group_counts);
	if (sinfo->total_project_counts != NULL)
		free_counts_list(sinfo->total_project_counts);
	if (sinfo->total_user_counts != NULL)
		free_counts_list(sinfo->total_user_counts);
	if (sinfo->nodepart != NULL)
		free_node_partition_array(sinfo->nodepart);
	if (sinfo->allpart)
		free_node_partition(sinfo->allpart);
	if (sinfo->hostsets != NULL)
		free_node_partition_array(sinfo->hostsets);
	if (sinfo->nodesigs)
		free_string_array(sinfo->nodesigs);
	if (sinfo->npc_arr != NULL)
		free_np_cache_array(sinfo->npc_arr);
	if (sinfo->node_group_key != NULL)
		free_string_array(sinfo->node_group_key);
	if (sinfo->job_formula != NULL)
		free(sinfo->job_formula);
	if (sinfo->calendar != NULL)
		free_event_list(sinfo->calendar);
	if (sinfo->policy != NULL)
		free_status(sinfo->policy);
	if (sinfo->fairshare != NULL)
		free_fairshare_head(sinfo->fairshare);
	if (sinfo->liminfo != NULL) {
		lim_free_liminfo(sinfo->liminfo);
		sinfo->liminfo = NULL;
	}
	if (sinfo->queue_list != NULL)
		free_queue_list(sinfo->queue_list);
	if(sinfo->equiv_classes != NULL)
		free_resresv_set_array(sinfo->equiv_classes);

	free_resource_list(sinfo->res);
#ifdef NAS
	/* localmod 034 */
	site_free_shares(sinfo);
	/* localmod 049 */
	if (sinfo->nodes_by_NASrank != NULL)
		free(sinfo->nodes_by_NASrank);
#endif

	free(sinfo);
}

/**
 * @brief
 *		free_resource_list - frees the memory used by a resource list
 *
 * @param[in]	reslist	-	the resource list to free
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
free_resource_list(schd_resource *reslist)
{
	schd_resource *resp, *tmp;

	resp = reslist;
	while (resp != NULL) {
		tmp = resp->next;
		free_resource(resp);

		resp = tmp;
	}
}

/**
 * @brief
 * 		free_resource - frees the memory used by a resource structure
 *
 * @param[in]	reslist	-	the resource to free
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
free_resource(schd_resource *resp)
{
	if (resp == NULL)
		return;

	if (resp->orig_str_avail != NULL)
		free(resp->orig_str_avail);

	if (resp->indirect_vnode_name != NULL)
		free(resp->indirect_vnode_name);

	if (resp->str_avail != NULL)
		free_string_array(resp->str_avail);

	if (resp->str_assigned != NULL)
		free(resp->str_assigned);

	free(resp);
}

/**
 * @brief
 * 		new_server_info - allocate and initialize a new
 *		server_info struct
 *
 * @param[in]	limallocflag	-	if nonzero, a liminfo structure will
 *									also be allocated
 *
 * @return	new allocated struct
 *
 * @see	lim_alloc_liminfo
 *
 * @par MT-Safe:	no
 */
server_info *
new_server_info(int limallocflag)
{
	server_info *sinfo;			/* the new server */

	if ((sinfo = (server_info *) malloc(sizeof(server_info))) == NULL) {
		log_err(errno, "new_server_info", MEM_ERR_MSG);
		return NULL;
	}

	sinfo->has_soft_limit = 0;
	sinfo->has_hard_limit = 0;
	sinfo->has_user_limit = 0;
	sinfo->has_grp_limit = 0;
	sinfo->has_proj_limit = 0;
	sinfo->has_mult_express = 0;
	sinfo->has_multi_vnode = 0;
	sinfo->has_prime_queue = 0;
	sinfo->has_nonprime_queue = 0;
	sinfo->has_nodes_assoc_queue = 0;
	sinfo->has_ded_queue = 0;
	sinfo->node_group_enable = 0;
	sinfo->eligible_time_enable = 0;
	sinfo->provision_enable = 0;
	sinfo->power_provisioning = 0;
	sinfo->dont_span_psets = 0;
	sinfo->throughput_mode = 0;
	sinfo->has_nonCPU_licenses = 0;
	sinfo->enforce_prmptd_job_resumption = 0;
	sinfo->use_hard_duration = 0;
	sinfo->sched_cycle_len = 0;
	sinfo->opt_backfill_fuzzy_time = conf.dflt_opt_backfill_fuzzy;
	sinfo->name = NULL;
	sinfo->res = NULL;
	sinfo->queues = NULL;
	sinfo->queue_list = NULL;
	sinfo->jobs = NULL;
	sinfo->all_resresv = NULL;
	sinfo->calendar = NULL;
	sinfo->running_jobs = NULL;
	sinfo->exiting_jobs = NULL;
	sinfo->nodes = NULL;
	sinfo->unassoc_nodes = NULL;
	sinfo->resvs = NULL;
	sinfo->alljobcounts = NULL;
	sinfo->group_counts = NULL;
	sinfo->project_counts = NULL;
	sinfo->user_counts = NULL;
	sinfo->total_alljobcounts = NULL;
	sinfo->total_group_counts = NULL;
	sinfo->total_project_counts = NULL;
	sinfo->total_user_counts = NULL;
	sinfo->nodepart = NULL;
	sinfo->allpart = NULL;
	sinfo->hostsets = NULL;
	sinfo->nodesigs = NULL;
	sinfo->node_group_key = NULL;
	sinfo->preempt_targets_enable = 1; /* enabled by default */
	sinfo->npc_arr = NULL;
	sinfo->qrun_job = NULL;
	sinfo->job_formula = NULL;
	sinfo->policy = NULL;
	sinfo->fairshare = NULL;
	sinfo->equiv_classes = NULL;
	sinfo->num_queues = 0;
	sinfo->num_nodes = 0;
	sinfo->num_resvs = 0;
	sinfo->num_hostsets = 0;
	sinfo->flt_lic = 0;
	sinfo->server_time = 0;

	if ((limallocflag != 0))
		sinfo->liminfo = lim_alloc_liminfo();
	init_state_count(&(sinfo->sc));
	memset(sinfo->preempt_count, 0, (NUM_PPRIO + 1) * sizeof(int));

#ifdef NAS
	/* localmod 034 */
	sinfo->share_head = NULL;
	/* localmod 049 */
	sinfo->nodes_by_NASrank = NULL;
#endif

	return sinfo;
}

/**
 * @brief
 * 		new_resource - allocate and initialize new resource struct
 *
 * @return	schd_resource
 * @retval	NULL	: Error
 *
 * @par MT-Safe:	yes
 */
schd_resource *
new_resource()
{
	schd_resource *resp;		/* the new resource */

	if ((resp = calloc(1,  sizeof(schd_resource))) == NULL) {
		log_err(errno, "new_resource", MEM_ERR_MSG);
		return NULL;
	}

	/* member type zero'd by calloc() */

	resp->name = NULL;
	resp->next = NULL;
	resp->def = NULL;
	resp->orig_str_avail = NULL;
	resp->indirect_vnode_name = NULL;
	resp->indirect_res = NULL;
	resp->str_avail = NULL;
	resp->str_assigned = NULL;
	resp->assigned = RES_DEFAULT_ASSN;
	resp->avail = RES_DEFAULT_AVAIL;

	return resp;
}

/**
 * @brief
 * 		Create new resource with given data
 *
 * @param[in]	name	-	name of resource
 * @param[in] 	value	-	value of resource
 * @param[in] 	field	-	is the value RF_AVAIL or RF_ASSN
 *
 * @see	set_resource()
 *
 * @return schd_resource *
 * @retval newly created resource
 * @retval NULL	: on error
 */
schd_resource *
create_resource(char *name, char *value, enum resource_fields field)
{
	schd_resource *nres = NULL;
	resdef *rdef;

	if (name == NULL)
		return NULL;

	if(value == NULL && field != RF_NONE)
		return NULL;

	rdef = find_resdef(allres, name);

	if (rdef != NULL) {
		if ((nres = new_resource()) != NULL) {
			nres->def = rdef;
			nres->name = rdef->name;
			nres->type = rdef->type;

			if (value != NULL) {
				if (set_resource(nres, value, field) == 0) {
					free_resource(nres);
					return NULL;
				}
			}
		}
	}
	else {
		schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SCHED, LOG_DEBUG, name, "Resource definition does not exist, resource may be invalid");
		return NULL;
	}

	return nres;
}

/**
 * @brief
 * 		add_resource_list - add one resource list to another
 *		i.e. r1 += r2
 *
 * @param[in]	policy	-	policy info
 * @param[in]	r1 		- 	lval resource
 * @param[in]	r2 		- 	rval resource
 * @param[in]	flags 	-
 *							NO_UPDATE_NON_CONSUMABLE - do not update
 *							non consumable resources
 *							USE_RESOURCE_LIST - use policy->resdef_to_check
 *							(and all bools) instead of all resources
 *							ADD_UNSET_BOOLS_FALSE - add unset bools as false
 *
 * @return	int
 * @retval	1	: success
 * @retval	0	: failure
 *
 * @par MT-Safe:	no
 */
int
add_resource_list(status *policy, schd_resource *r1, schd_resource *r2, unsigned int flags)
{
	schd_resource *cur_r1;
	schd_resource *cur_r2;
	schd_resource *end_r1;
	schd_resource *nres;
	sch_resource_t assn;
	int i;

	if (r1 == NULL || r2 == NULL)
		return 0;

	end_r1 = r1;

	while (end_r1->next != NULL)
		end_r1 = end_r1->next;

	for (cur_r2 = r2; cur_r2 != NULL; cur_r2 = cur_r2->next) {
		if ((flags & USE_RESOURCE_LIST)) {
			if (!resdef_exists_in_array(policy->resdef_to_check, cur_r2->def) &&
				!cur_r2->type.is_boolean)
				continue;
		}

		cur_r1 = find_resource(r1, cur_r2->def);
		if (cur_r1 == NULL) { /* resource in r2 which is not in r1 */
			if (!(flags & NO_UPDATE_NON_CONSUMABLE) || cur_r2->type.is_consumable) {
				end_r1->next = dup_resource(cur_r2);
				if (end_r1->next == NULL)
					return 0;
				end_r1 = end_r1->next;
			}
		} else if (cur_r1->type.is_consumable) {
			if ((flags & ADD_AVAIL_ASSIGNED)) {
				if (cur_r2->avail == RES_DEFAULT_AVAIL)
					assn = RES_DEFAULT_ASSN; /* nothing is set, so add nothing */
				else
					assn = cur_r2->avail;
			} else
				assn = cur_r2->assigned;
			add_resource_value(&(cur_r1->avail), &(cur_r2->avail),
					   RES_DEFAULT_AVAIL);
			add_resource_value(&(cur_r1->assigned),
					   &assn, RES_DEFAULT_ASSN);
		} else {
			if (!(flags & NO_UPDATE_NON_CONSUMABLE)) {
				if (cur_r1->type.is_string) {
					if (cur_r1->def == getallres(RES_VNODE))
						add_resource_str_arr(cur_r1, cur_r2->str_avail, 1);
					else
						add_resource_str_arr(cur_r1, cur_r2->str_avail, 0);
				} else if (cur_r1->type.is_boolean)
					(void)add_resource_bool(cur_r1, cur_r2);
			}
		}
	}

	if (flags & ADD_UNSET_BOOLS_FALSE) {
		if (boolres != NULL) {
			for (i = 0; boolres[i] != NULL; i++) {
				if (find_resource(r2, boolres[i]) == NULL) {
					cur_r1 = find_resource(r1, boolres[i]);
					if (cur_r1 == NULL) {
						nres = create_resource(boolres[i]->name, ATR_FALSE, RF_AVAIL);
						if (nres == NULL)
							return 0;

						end_r1->next = nres;
						end_r1 = nres;
					} else {
						nres = false_res();
						nres->name = boolres[i]->name;
						if (nres == NULL)
							return 0;
						(void)add_resource_bool(cur_r1, nres);
					}
				}
			}
		}
	}
	return 1;
}

/**
 * @brief
 *		add_resource_value - add a resource value to another
 *				i.e. val1 += val2
 *
 * @param[in]	val1		-	value 1
 * @param[in]	val2		-	value 2
 * @param[in]	initial_val - 	value set by resource constructor
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
add_resource_value(sch_resource_t *val1, sch_resource_t *val2,
	sch_resource_t initial_val)
{
	if (val1 == NULL || val2 == NULL)
		return;

	if (*val1 == initial_val)
		*val1 = *val2;
	else if (*val2 != initial_val)
		*val1 += *val2;
	/* else val2 is default and val1 isn't, so we leave val1 alone */
}

/**
 * @brief
 * 		Add values from a string array to a string resource (available).
 *		Only add values if they do not exist.
 *
 * @param[in]	res			-	resource to add values to
 * @param[in]	str_arr		-	string array of values to add
 * @param[in]	allow_dup 	- 	should we allow dups or not?
 *
 * @return	int
 *
 * @retval	1	: success
 * @retval	0	: failure
 *
 * @par MT-Safe:	no
 */
int
add_resource_str_arr(schd_resource *res, char **str_arr, int allow_dup)
{
	int i;

	if (res == NULL || str_arr == NULL)
		return 0;

	if (!res->type.is_string)
		return 0;

	for (i = 0; str_arr[i] != NULL; i++) {
		if (add_str_to_unique_array(&(res->str_avail), str_arr[i]) < 0)
			return 0;
	}
	return 1;
}

/**
 * @brief
 * 		accumulate two boolean resources together
 *		T + T = True | F + F = False | T + F = TRUE_FALSE
 *
 * @param[in] 	r1	-	lval : left side boolean to add to
 * @param[in]	r2 	-	rval : right side boolean - if NULL, treat as false
 *
 * @return int
 * @retval	1	: Ok
 * @retval	0	: Error
 */
int
add_resource_bool(schd_resource *r1, schd_resource *r2)
{
	int r1val, r2val;
	if (r1 == NULL)
		return 0;

	if (!r1->type.is_boolean || (r2 != NULL && !r2->type.is_boolean))
		return 0;

	/* We can't accumulate any more values than TRUE and FALSE,
	 * so if we have both than return success early
	 */
	r1val = r1->avail;
	if (r1val == TRUE_FALSE)
		return 1;

	r2val = r2 == NULL ? FALSE : r2->avail;

	/********************************************
	 *        Possible Value Combinations       *
	 *       r1     *    r2   *    r1 result    *
	 * ******************************************
	 *       T      *     T    *       T        *
	 *       T      *     F    *   TRUE_FALSE   *
	 *       F      *     T    *   TRUE_FALSE   *
	 *       F      *     F    *       F        *
	 ********************************************/

	if (r1val && !r2val)
		r1->avail = TRUE_FALSE;
	else if (!r1val && r2val)
		r1->avail = TRUE_FALSE;

	return 1;
}

/**
 * @brief
 * 		free_server - free a server_info and possibly its queues also
 *
 * @param[in]	sinfo 			- 	server_info list head
 * @param[in]	free_queues_too - 	flag to free the queues attached
 *									to server also
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
free_server(server_info *sinfo, int free_objs_too)
{
	if (sinfo == NULL)
		return;

	if (free_objs_too) {
		free_queues(sinfo->queues, 1);
		free_nodes(sinfo->nodes);
		free_resource_resv_array(sinfo->resvs);
	}

#ifdef NAS /* localmod 053 */
	site_restore_users();
#endif /* localmod 053 */
	free_server_info(sinfo);
}

/**
 * @brief
 * 		update_server_on_run - update server_info structure
 *				when a resource resv is run
 *
 * @policy[in]	policy 	- 	policy info
 * @param[in]	sinfo 	- 	server_info to update
 * @param[in]	qinfo 	- 	queue_info the job is in
 *							(if resresv is a job)
 * @param[in]	resresv - 	resource_resv that was run
 * @param[in]  job_state -	the old state of a job if resresv is a job
 *				If the old_state is found to be suspended
 *				then only resources that were released
 *				during suspension will be accounted.
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
update_server_on_run(status *policy, server_info *sinfo,
	queue_info *qinfo, resource_resv *resresv, char * job_state)
{
	resource_req *req;		/* used to cycle through resources to update */
	schd_resource *res;		/* used in finding a resource to update */
	counts *cts;			/* used in updating project/group/user counts */
	int num_unassoc;		/* number of unassociated nodes */
	counts *allcts;			/* used in updating counts for all jobs */

	if (sinfo == NULL || resresv == NULL)
		return;

	if (resresv->is_job) {
		if (resresv->job == NULL)
			return;
		if (qinfo == NULL)
			return;
	}


	/*
	 * Update the server level resources 
	 *   -- if a job is in a reservation, the resources have already been
	 *      accounted for and assigned to the reservation.  We don't want to
	 *      double count them
	 */
	if (resresv->is_resv || (qinfo != NULL && qinfo->resv == NULL)) {
		if (resresv->is_job && (job_state != NULL) && (*job_state == 'S'))
			req = resresv->job->resreq_rel;
		else
			req = resresv->resreq;
		while (req != NULL) {
			if (req->type.is_consumable) {
				res = find_resource(sinfo->res, req->def);

				if (res)
					res->assigned += req->amount;
			}
			req = req->next;
		}
	}

	if (resresv->is_job) {
		sinfo->sc.running++;
		/* note: if job is suspended, counts will get off.
		 *       sc.queued is not used, and sc.suspended isn't used again
		 *       after this point
		 *       BZ 5798
		 */
		sinfo->sc.queued--;

		/* sort the nodes before we filter them down to more useful lists */
		if (cstat.node_sort[0].res_name != NULL && conf.node_sort_unused) {
			if (resresv->job->resv != NULL &&
				resresv->job->resv->resv != NULL) {
				node_info **resv_nodes;
				int num_resv_nodes;

				resv_nodes = resresv->job->resv->resv->resv_nodes;
				num_resv_nodes = count_array((void **) resv_nodes);
				qsort(resv_nodes, num_resv_nodes, sizeof(node_info *),
					multi_node_sort);
			}
			else {
				qsort(sinfo->nodes, sinfo->num_nodes, sizeof(node_info *),
					multi_node_sort);

				if (sinfo->nodes != sinfo->unassoc_nodes) {
					num_unassoc = count_array((void **) sinfo->unassoc_nodes);
					qsort(sinfo->unassoc_nodes, num_unassoc, sizeof(node_info *),
						multi_node_sort);
				}
			}
		}

		/* We're running a job or reservation, which will affect the cached data.
		 * We'll flush the cache and rebuild it if needed
		 */
		if (sinfo->npc_arr != NULL) {
			free_np_cache_array(sinfo->npc_arr);
			sinfo->npc_arr = NULL;
		}

		/* should probably be in update_all_nodepart() for consistency
		 * when moved, this copy and update_node_on_end() must be moved
		 */
		if (sinfo->node_group_enable && sinfo->node_group_key !=NULL) {
			node_partition_update_array(policy, sinfo->nodepart);
			qsort(sinfo->nodepart, sinfo->num_parts,
				sizeof(node_partition *), cmp_placement_sets);
		}

		/* a new job has been run, recreate running jobs array */
		free(sinfo->running_jobs);
		sinfo->running_jobs = resource_resv_filter(
			sinfo->jobs, sinfo->sc.total, check_run_job, NULL, 0);
	}

	if (sinfo->has_soft_limit || sinfo->has_hard_limit) {
		if (resresv->is_job) {
			update_total_counts(sinfo, NULL , resresv, SERVER);

			cts = find_alloc_counts(sinfo->group_counts, resresv->group);

			if (sinfo->group_counts == NULL)
				sinfo->group_counts = cts;

			update_counts_on_run(cts, resresv->resreq);

			cts = find_alloc_counts(sinfo->project_counts, resresv->project);

			if (sinfo->project_counts == NULL)
				sinfo->project_counts = cts;

			update_counts_on_run(cts, resresv->resreq);

			cts = find_alloc_counts(sinfo->user_counts, resresv->user);

			if (sinfo->user_counts == NULL)
				sinfo->user_counts = cts;

			update_counts_on_run(cts, resresv->resreq);

			allcts = find_alloc_counts(sinfo->alljobcounts, "o:" PBS_ALL_ENTITY);

			if (sinfo->alljobcounts == NULL)
				sinfo->alljobcounts = allcts;

			update_counts_on_run(allcts, resresv->resreq);
		}
	}
}

/**
 * @brief
 * 		update_server_on_end - update a server_info structure when a
 *		resource resv has finished running
 *
 * @param[in]   policy 	- policy info
 * @param[in]	sinfo	- server_info to update
 * @param[in]	qinfo 	- queue_info the job is in
 * @param[in]	resresv - resource_resv that finished running
 * @param[in]  job_state -	the old state of a job if resresv is a job
 *				If the old_state is found to be suspended
 *				then only resources that were released
 *				during suspension will be accounted.
 *
 * @return	void
 *
 * @note
 * 		Job must be in pre-ended state (job_state is new state)
 *
 * @par MT-Safe:	no
 */
void
update_server_on_end(status *policy, server_info *sinfo, queue_info *qinfo,
	resource_resv *resresv, char *job_state)
{
	resource_req *req;		/* resource request from job */
	schd_resource *res;		/* resource on server */
	int i;

	if (sinfo == NULL ||  resresv == NULL)
		return;
	if (resresv->is_job) {
		if (resresv->job == NULL)
			return;
		if (qinfo == NULL)
			return;
	}

	if (resresv->is_job) {
		if (resresv->job->is_running) {
			sinfo->sc.running--;
			remove_resresv_from_array(sinfo->running_jobs, resresv);
		}
		else if (resresv->job->is_exiting) {
			sinfo->sc.exiting--;
			remove_resresv_from_array(sinfo->exiting_jobs, resresv);
		}
		state_count_add(&(sinfo->sc), job_state, 1);
	}

	/*
	 *	if the queue is a reservation then the resources belong to it and not
	 *	the server
	 */
	if (resresv->is_resv || (qinfo != NULL && qinfo->resv ==NULL)) {

		if (resresv->is_job && (job_state != NULL) && (*job_state == 'S'))
			req = resresv->job->resreq_rel;
		else
			req = resresv->resreq;

		while (req != NULL) {
			res = find_resource(sinfo->res, req->def);

			if (res != NULL)
				res->assigned -= req->amount;

			req = req->next;
		}
	}

	/* We're ending a job or reservation, which will affect the cached data.
	 * We'll flush the cache and rebuild it if needed
	 */
	if (sinfo->npc_arr != NULL) {
		free_np_cache_array(sinfo->npc_arr);
		sinfo->npc_arr = NULL;
	}

	/* should probably be in update_all_nodepart() for consistency -
	 * when moved, both this and update_node_on_run most be moved
	 */
	if (sinfo->node_group_enable && sinfo->node_group_key !=NULL) {
		node_partition_update_array(policy, sinfo->nodepart);
		qsort(sinfo->nodepart, sinfo->num_parts,
			sizeof(node_partition *), cmp_placement_sets);
	}

	if (sinfo->has_soft_limit || sinfo->has_hard_limit) {
		if (resresv->is_job && resresv->job->is_running) {
			counts *cts;			/* update user/group/project counts */

			update_total_counts_on_end(sinfo, NULL, resresv, SERVER);
			cts = find_counts(sinfo->group_counts, resresv->group);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);

			cts = find_counts(sinfo->project_counts, resresv->project);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);

			cts = find_counts(sinfo->user_counts, resresv->user);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);

			cts = find_alloc_counts(sinfo->alljobcounts, "o:" PBS_ALL_ENTITY);

			if (cts != NULL)
				update_counts_on_end(cts, resresv->resreq);

		}
	}

	/* The only thing which will change preemption priorities in the middle of
	 * a scheduling cycle is soft user/group/project limits.  If a user, group,
	 * or project  goes under a limit because of this job ending, we need to mark
	 * those jobs differently
	 */
	if (cstat.preempting && resresv->is_job) {
		if (sinfo->has_soft_limit || resresv->job->queue->has_soft_limit) {
			for (i = 0; sinfo->jobs[i] != NULL; i++) {
				if (sinfo->jobs[i]->job !=NULL) {
					if (!strcmp(resresv->user, sinfo->jobs[i]->user) ||
						!strcmp(resresv->group, sinfo->jobs[i]->group) ||
						!strcmp(resresv->project, sinfo->jobs[i]->project))
						set_preempt_prio(sinfo->jobs[i],
							sinfo->jobs[i]->job->queue, sinfo);
				}
			}

			/* now that we've set all the preempt levels, we need to count them */
			memset(sinfo->preempt_count, 0, NUM_PPRIO * sizeof(int));
			for (i = 0; sinfo->running_jobs[i] != NULL; i++)
				if (!sinfo->running_jobs[i]->job->can_not_preempt)
					sinfo->
					preempt_count[preempt_level(sinfo->running_jobs[i]->job->preempt)]++;
		}
	}
}

/**
 * @brief
 * 		create_server_arrays - create a large server resresv array
 *		of all jobs on the system by coping all the jobs from the
 *		queue job arrays.  Also create an array of both jobs and
 *		reservations.
 *
 * @param[in]	sinfo	-	the server
 *
 * @return	int
 * @retval	1	: success
 * @retval	0 	: failure
 *
 * @par MT-Safe:	no
 */
int
create_server_arrays(server_info *sinfo)
{
	queue_info **qinfo;		/* used to cycle through the array of queues */
	resource_resv **job_arr;	/* used in copying jobs to job array */
	resource_resv **all_arr;	/* used in copying jobs to job/resv array */
	resource_resv **resresv_arr;	/* used as source array to copy */
	int i = 0, j;

	if ((job_arr = (resource_resv **)
		malloc(sizeof(resource_resv *) * (sinfo->sc.total + 1))) ==NULL) {
		log_err(errno, "create_server_arrays", "Error allocating memory");
		return 0;
	}

	if ((all_arr = (resource_resv **) malloc(sizeof(resource_resv *) *
		(sinfo->sc.total + sinfo->num_resvs +1))) == NULL) {
		free(job_arr);
		log_err(errno, "create_server_arrays", "Error allocating memory");
		return 0;
	}

	qinfo = sinfo->queues;
	while (*qinfo != NULL) {
		resresv_arr = (*qinfo)->jobs;

		if (resresv_arr != NULL) {
			for (j = 0; resresv_arr[j] != NULL; j++, i++)
				job_arr[i] = all_arr[i] = resresv_arr[j];
			if (i > sinfo->sc.total) {
				free(job_arr);
				free(all_arr);
				return 0;
			}
		}
		qinfo++;
	}
	job_arr[i] = NULL;

#ifdef NAS /* localmod 054 */
	if (i != sinfo->sc.total) {
		sprintf(log_buffer, "Expected %d jobs, but found %d", sinfo->sc.total, i);
		log_err(-1, "create_server_arrays", log_buffer);
		sinfo->sc.total = i;
	}
#endif /* localmod 054 */

	if (sinfo->resvs != NULL) {
		for (j = 0; sinfo->resvs[j] != NULL; j++, i++)
			all_arr[i] = sinfo->resvs[j];
#ifdef NAS /* localmod 054 */
		if (j != sinfo->num_resvs) {
			sprintf(log_buffer, "Expected %d resv, but found %d", sinfo->num_resvs, j);
			log_err(-1, "create_server_arrays", log_buffer);
			if (j > sinfo->num_resvs) {
				abort();
			}
			sinfo->num_resvs = j;
		}
#endif /* localmod 054 */
	}
	all_arr[i] = NULL;

	sinfo->jobs = job_arr;
	sinfo->all_resresv = all_arr;

	return 1;
}

/**
 * @brief
 * 		helper function for resource_resv_filter() - returns 1 if
 *		job is running
 *
 * @param[in]	job	-	resource reservation job.
 * @param[in]	arg	-	argument (not used here)
 *
 * @return	int
 * @retval	0	: job not running
 * @retval	1	: job is running
 */
int
check_run_job(resource_resv *job, void *arg)
{
	if (job->is_job && job->job !=NULL)
		return job->job->is_running;

	return 0;
}

/**
 * @brief
 * 		helper function for resource_resv_filter()
 *
 * @param[in]	job	-	resource reservation job.
 * @param[in]	arg	-	argument (not used here)
 *
 * @return	int
 * @retval	1	: if job is exiting
 */
int
check_exit_job(resource_resv *job, void *arg)
{
	if (job->is_job && job->job !=NULL)
		return job->job->is_exiting;

	return 0;
}

/**
 * @brief
 * 		helper function for resource_resv_filter()
 *
 * @param[in]	job	-	resource reservation job.
 * @param[in]	arg	-	argument (not used here)
 *
 * @return	int
 * @retval	1	: if reservation is running
 * @retval	0	: if reservation is not running.
 */
int
check_run_resv(resource_resv *resv, void *arg)
{
	if (resv->is_resv && resv->resv !=NULL)
		return resv->resv->resv_state == RESV_RUNNING;

	return 0;
}

/**
 * @brief
 * 		helper function for resource_resv_filter()
 *
 * @param[in]	job	-	resource reservation job.
 * @param[in]	arg	-	argument (not used here)
 *
 * @return	int
 * @retval	1	: if job is suspended
 * @retval	0	: if job is not suspended
 */
int
check_susp_job(resource_resv *job, void *arg)
{
	if (job->is_job && job->job !=NULL)
		return job->job->is_suspended;

	return 0;
}

/**
 * @brief
 * 		helper function for resource_resv_filter()
 *
 * @param[in]	job	-	resource reservation job.
 * @param[in]	arg	-	argument (not used here)
 *
 * @return	int
 * @retval	1	: if job is not in reservation passed in arg
 * @retval	0	:  if job is there in reservation passed in arg
 */
int
check_job_not_in_reservation(resource_resv *job, void *arg)
{
	if (job->is_job && job->job != NULL && job->job->resv== NULL)
		return 1;

	return 0;
}

/**
 * @brief
 * 		helper function for resource_resv_filter()
 *
 * @param[in]	resv	-	resource reservation structure
 * @param[in]	arg		-	the array of nodes to look in
 *
 * @return	int
 * @retval	1	: if reservation is running on node passed in arg
 * @retval	0	: if reservation is not running on node passed in arg
 */
int
check_resv_running_on_node(resource_resv *resv, void *arg)
{
	if (resv->is_resv && resv->resv !=NULL) {
		if (resv->resv->resv_state == RESV_RUNNING || resv->resv->resv_state == RESV_BEING_DELETED)
			if (find_node_info(resv->ninfo_arr, (char *) arg))
				return 1;
	}
	return 0;
}

/**
 * @brief
 * 		dup_server_info - duplicate a server_info struct
 *
 * @param[in]	osinfo	-	the struct to copy
 *
 * @return	duplicated server_info
 * @retval	NULL	: something wrong!
 *
 * @par MT-Safe:	no
 */
server_info *
dup_server_info(server_info *osinfo)
{
	server_info *nsinfo;		/* scheduler internal form of server info */
	int i;

	if (osinfo == NULL)
		return NULL;

	/* duplicate the server information */
	if ((nsinfo = new_server_info(0)) == NULL)
		return NULL;                /* error */

	if (osinfo->fairshare != NULL) {
		nsinfo->fairshare = dup_fairshare_head(osinfo->fairshare);
		if (nsinfo->fairshare == NULL) {
			free_server(nsinfo, 1);
			return NULL;
		}
	}
	nsinfo->has_mult_express = osinfo->has_mult_express;
	nsinfo->has_soft_limit = osinfo->has_soft_limit;
	nsinfo->has_hard_limit = osinfo->has_hard_limit;
	nsinfo->has_user_limit = osinfo->has_user_limit;
	nsinfo->has_grp_limit = osinfo->has_grp_limit;
	nsinfo->has_proj_limit = osinfo->has_proj_limit;
	nsinfo->has_multi_vnode = osinfo->has_multi_vnode;
	nsinfo->has_prime_queue = osinfo->has_prime_queue;
	nsinfo->has_nonprime_queue = osinfo->has_nonprime_queue;
	nsinfo->has_ded_queue = osinfo->has_ded_queue;
	nsinfo->has_nodes_assoc_queue = osinfo->has_nodes_assoc_queue;
	nsinfo->node_group_enable = osinfo->node_group_enable;
	nsinfo->eligible_time_enable = osinfo->eligible_time_enable;
	nsinfo->provision_enable = osinfo->provision_enable;
	nsinfo->power_provisioning = osinfo->power_provisioning;
	nsinfo->dont_span_psets = osinfo->dont_span_psets;
	nsinfo->has_nonCPU_licenses = osinfo->has_nonCPU_licenses;
	nsinfo->enforce_prmptd_job_resumption = osinfo->enforce_prmptd_job_resumption;
	nsinfo->use_hard_duration = osinfo->use_hard_duration;
	nsinfo->sched_cycle_len = osinfo->sched_cycle_len;
	nsinfo->opt_backfill_fuzzy_time = osinfo->opt_backfill_fuzzy_time;
	nsinfo->name = string_dup(osinfo->name);
	nsinfo->preempt_targets_enable = osinfo->preempt_targets_enable;
	nsinfo->liminfo = lim_dup_liminfo(osinfo->liminfo);
	nsinfo->server_time = osinfo->server_time;
	nsinfo->flt_lic = osinfo->flt_lic;
	nsinfo->res = dup_resource_list(osinfo->res);
	nsinfo->alljobcounts = dup_counts_list(osinfo->alljobcounts);
	nsinfo->group_counts = dup_counts_list(osinfo->group_counts);
	nsinfo->project_counts = dup_counts_list(osinfo->project_counts);
	nsinfo->user_counts = dup_counts_list(osinfo->user_counts);
	nsinfo->total_alljobcounts = dup_counts_list(osinfo->total_alljobcounts);
	nsinfo->total_group_counts = dup_counts_list(osinfo->total_group_counts);
	nsinfo->total_project_counts = dup_counts_list(osinfo->total_project_counts);
	nsinfo->total_user_counts = dup_counts_list(osinfo->total_user_counts);
	nsinfo->node_group_key = dup_string_array(osinfo->node_group_key);
	nsinfo->job_formula = string_dup(osinfo->job_formula);
	nsinfo->nodesigs = dup_string_array(osinfo->nodesigs);

	nsinfo->policy = dup_status(osinfo->policy);

	nsinfo->num_nodes = osinfo->num_nodes;

	/* dup the nodes, if there are any nodes */
#ifdef NAS /* localmod 049 */
	nsinfo->nodes = dup_nodes(osinfo->nodes, nsinfo, NO_FLAGS, 1);
#else
	nsinfo->nodes = dup_nodes(osinfo->nodes, nsinfo, NO_FLAGS);
#endif /* localmod 049 */

	if (nsinfo->has_nodes_assoc_queue) {
		nsinfo->unassoc_nodes =
			node_filter(nsinfo->nodes, nsinfo->num_nodes, is_unassoc_node, NULL, 0);
	} else
		nsinfo->unassoc_nodes = nsinfo->nodes;


	/* dup the reservations */
	nsinfo->resvs = dup_resource_resv_array(osinfo->resvs, nsinfo, NULL);
	nsinfo->num_resvs = osinfo->num_resvs;

#ifdef NAS /* localmod 053 */
	site_save_users();
#endif /* localmod 053 */

	/* duplicate the queues */
	nsinfo->num_queues = osinfo->num_queues;
	if ((nsinfo->queues = dup_queues(osinfo->queues, nsinfo)) == NULL) {
		free_server(nsinfo, 0);
		return NULL;
	}

	if (osinfo->queue_list != NULL) {
		int ret_val;
		/* queues are already sorted in descending order of their priority */
		for (i = 0; i < nsinfo->num_queues; i++) {
			ret_val = add_queue_to_list(&nsinfo->queue_list, nsinfo->queues[i]);
			if (ret_val == 0) {
				nsinfo->fairshare = NULL;
				free_server(nsinfo, 1);
				return NULL;
			}
		}
	}

	nsinfo->sc = osinfo->sc;

	/* sets nsinfo -> jobs and nsinfo -> all_resresv */
#ifdef NAS /* localmod 054 */
	if (create_server_arrays(nsinfo) == 0) {
		free_server(nsinfo, 1);
		return NULL;
	}
#else
	create_server_arrays(nsinfo);
#endif /* localmod 054 */

	nsinfo->equiv_classes = dup_resresv_set_array(osinfo->equiv_classes, nsinfo);

	/* the event list is created dynamically during the evaluation of resource
	 * reservations. It is a sorted list of all_resresv, initialized to NULL to
	 * appropriately be freed in free_event_list */
	nsinfo->calendar = dup_event_list(osinfo->calendar, nsinfo);
	if (nsinfo->calendar == NULL) {
		free_server(nsinfo, 1);
		return NULL;
	}

	nsinfo->running_jobs =
		resource_resv_filter(nsinfo->jobs, nsinfo->sc.total,
		check_run_job, NULL, FILTER_FULL);

	nsinfo->exiting_jobs =
		resource_resv_filter(nsinfo->jobs, nsinfo->sc.total,
		check_exit_job, NULL, 0);

	nsinfo->num_preempted = osinfo->num_preempted;

	if (osinfo->qrun_job != NULL)
		nsinfo->qrun_job = find_resource_resv(nsinfo->jobs,
			osinfo->qrun_job->name);

	for (i = 0; i < NUM_PPRIO; i++)
		nsinfo->preempt_count[i] = osinfo->preempt_count[i];

#ifdef NAS /* localmod 034 */
	if (!site_dup_shares(osinfo, nsinfo)) {
		free_server(nsinfo, 1);
		return NULL;
	}
#endif /* localmod 034 */

	/* Now we do any processing which has to happen last */

	/* the jobs are not dupped when we dup the nodes, so we need to copy
	 * the node's job arrays now
	 */
	for (i = 0; osinfo->nodes[i] != NULL; i++)
		nsinfo->nodes[i]->job_arr =
			copy_resresv_array(osinfo->nodes[i]->job_arr, nsinfo->jobs);

	nsinfo->num_parts = osinfo->num_parts;
	if (osinfo->nodepart != NULL) {
		nsinfo->nodepart = dup_node_partition_array(osinfo->nodepart, nsinfo);
		if (nsinfo->nodepart == NULL) {
			free_server(nsinfo, 1);
			return NULL;
		}
	}
	nsinfo->allpart = dup_node_partition(osinfo->allpart, nsinfo);
	if (osinfo->hostsets != NULL) {
		int j, k;
		nsinfo->hostsets = dup_node_partition_array(osinfo->hostsets, nsinfo);
		if (nsinfo->hostsets == NULL) {
			free_server(nsinfo, 1);
			return NULL;
		}
		/* reattach nodes to their host sets*/
		for (j = 0; nsinfo->hostsets[j] != NULL; j++) {
			node_partition *hset = nsinfo->hostsets[j];
			for (k = 0; hset->ninfo_arr[k] != NULL; k++)
				hset->ninfo_arr[k]->hostset = hset;
		}
		nsinfo->num_hostsets = osinfo->num_hostsets;
	}

	/* the running resvs are not dupped when we dup the nodes, so we need to copy
	 * the node's running resvs arrays now
	 */
	for (i = 0; osinfo->nodes[i] != NULL; i++)
		nsinfo->nodes[i]->run_resvs_arr =
			copy_resresv_array(osinfo->nodes[i]->run_resvs_arr,
			nsinfo->resvs);

	return nsinfo;
}

/**
 * @brief
 * 		dup_resource_list - dup a resource list
 *
 * @param[in]	res - the resource list to duplicate
 *
 * @return	duplicated resource list
 * @retval	NULL	: Error
 *
 * @par MT-Safe:	no
 */
schd_resource *
dup_resource_list(schd_resource *res)
{
	schd_resource *pres;
	schd_resource *nres;
	schd_resource *prev = NULL;
	schd_resource *head = NULL;

	for (pres = res; pres != NULL; pres = pres->next) {
		nres = dup_resource(pres);
		if (prev == NULL)
			head = nres;
		else
			prev->next = nres;

		prev = nres;
	}

	return head;
}
/**
 * @brief
 * 		dup a resource list selectively + booleans (set or unset=false)
 *
 *
 *	@param[in]	res - the resource list to duplicate
 *	@param[in]	deflist -  dup resources in this list
 *	@param[in]	flags - @see add_resource_list()
 *
 * @return	duplicated resource list
 * @retval	NULL	: Error
 *
 * @par MT-Safe:	no
 */
schd_resource *
dup_selective_resource_list(schd_resource *res, resdef **deflist, unsigned flags)
{
	schd_resource *pres;
	schd_resource *nres;
	schd_resource *prev = NULL;
	schd_resource *head = NULL;
	int i;

	for (pres = res; pres != NULL; pres = pres->next) {
		if (pres->type.is_boolean ||
			resdef_exists_in_array(deflist, pres->def)) {
			nres = dup_resource(pres);
			if (nres == NULL) {
				free_resource_list(head);
				return NULL;
			}
			if ((flags & ADD_AVAIL_ASSIGNED)) {
				if (nres->avail == RES_DEFAULT_AVAIL)
					nres->assigned = RES_DEFAULT_ASSN;
				else
					nres->assigned = nres->avail;
			}
			if (prev == NULL)
				head = nres;
			else
				prev->next = nres;
			prev = nres;
		}
	}
	/* add on any booleans which are unset (i.e.,  false) */
	if (boolres != NULL && (flags & ADD_UNSET_BOOLS_FALSE)) {
		for (i = 0; boolres[i] != NULL; i++) {
			if (find_resource(res, boolres[i]) == NULL) {
				nres = create_resource(boolres[i]->name, ATR_FALSE, RF_AVAIL);
				if (nres == NULL) {
					free_resource_list(head);
					return NULL;
				}
				if (prev == NULL)
					head = nres;
				else
					prev->next = nres;
				prev = nres;
			}
		}
	}
	return head;
}

/**
 * @brief
 * 		dup_ind_resource_list - dup a resource list - if a resource in
 *		the list is indirect, dup the pointed to resource instead
 *
 * @param[in]	res - the resource list to duplicate
 *
 * @return	duplicated resource list
 * @retval	NULL	: Error
 *
 * @par MT-Safe:	no
 */
schd_resource *
dup_ind_resource_list(schd_resource *res)
{
	schd_resource *pres;
	schd_resource *nres;
	schd_resource *prev = NULL;
	schd_resource *head = NULL;

	for (pres = res; pres != NULL; pres = pres->next) {
		if (pres->indirect_res != NULL)
			nres = dup_resource(pres->indirect_res);
		else
			nres = dup_resource(pres);

		if (nres == NULL) {
			free_resource_list(head);
			return NULL;
		}

		if (prev == NULL)
			head = nres;
		else
			prev->next = nres;

		prev = nres;
	}

	return head;
}

/**
 * @brief
 * 		dup_resource - duplicate a resource struct
 *
 * @param[in]	res	- the resource to dup
 *
 * @return	the duplicated resource
 * @retval	NULL	: Error
 *
 * @par MT-Safe:	no
 */
schd_resource *
dup_resource(schd_resource *res)
{
	schd_resource *nres;

	if ((nres = new_resource()) == NULL)
		return NULL;

	nres->def = res->def;
	if (nres->def != NULL)
		nres->name = nres->def->name;


	if (res->indirect_vnode_name != NULL)
		nres->indirect_vnode_name = string_dup(res->indirect_vnode_name);

	if (res->orig_str_avail != NULL)
		nres->orig_str_avail = string_dup(res->orig_str_avail);

	if (res->str_avail != NULL)
		nres->str_avail = dup_string_array(res->str_avail);

	if (res->str_assigned != NULL)
		nres->str_assigned = string_dup(res->str_assigned);

	nres->avail = res->avail;
	nres->assigned = res->assigned;

	memcpy(&(nres->type), &(res->type), sizeof(struct resource_type));

	return nres;
}

/**
 * @brief
 * 		is_unassoc_node - finds nodes which are not associated
 *		with queues used with node_filter
 *
 * @param[in]	ninfo - the node to check
 *
 * @return	int
 * @retval	1	-	if the node does not have a queue associated with it
 * @retval	0	- 	otherwise
 *
 * @par MT-Safe:	yes
 */
int
is_unassoc_node(node_info *ninfo, void *arg)
{
	if (ninfo->queue_name == NULL)
		return 1;

	return 0;
}

/**
 * @brief
 * 		new_counts - create a new counts structure and return it
 *
 * @return	new counts structure
 * @retval	NULL	: malloc failed
 *
 * @par MT-Safe:	yes
 */
counts *
new_counts(void)
{

	counts *cts;

	if ((cts = malloc(sizeof(struct counts)))  == NULL) {
		log_err(errno, "new_counts", MEM_ERR_MSG);
		return NULL;
	}

	cts->name = NULL;
	cts->running = 0;
	cts->rescts = NULL;
	cts->next = NULL;

	return cts;
}

/**
 * @brief
 * 		free_counts - free a counts structure
 *
 * @param[in]	cts	-	the counts structure to free
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
free_counts(counts *cts)
{
	if (cts == NULL)
		return;

	if (cts->name != NULL)
		free(cts->name);

	if (cts->rescts != NULL)
		free_resource_req_list(cts->rescts);

	cts->next = NULL;

	free(cts);
}

/**
 * @brief
 * 		free_counts_list - free a list of counts structures
 *
 * @param[in]	ctslist	- the counts structure to free
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
free_counts_list(counts *ctslist)
{
	counts *prev, *cur;

	cur = prev = ctslist;

	while (cur != NULL) {
		prev = cur->next;
		free_counts(cur);
		cur = prev;
	}
}

/**
 * @brief
 * 		dup_counts - duplicate a counts structure
 *
 * @param[in]	ctslist	- the counts structure to duplicate
 *
 * @return	new counts structure
 * @retval	NULL	: on error
 *
 * @par MT-Safe:	no
 */
counts *
dup_counts(counts *octs)
{
	counts *ncts;

	ncts = new_counts();

	if (ncts != NULL) {
		if (octs->name != NULL)
			ncts->name = string_dup(octs->name);

		ncts->running = octs->running;

		ncts->rescts = dup_resource_req_list(octs->rescts);
	}

	return ncts;
}

/**
 * @brief
 * 		dup_counts_list - duplicate a counts list
 *
 * @param[in]	octs - the counts structure to duplicate
 *
 * @return	duplicated counts list
 * @retval	NULL	: error
 *
 * @par MT-Safe:	no
 */
counts *
dup_counts_list(counts *ctslist)
{
	counts *cur;
	counts *nhead;
	counts *prev;
	counts *ncts;

	nhead = NULL;
	prev = NULL;
	cur = ctslist;

	while (cur != NULL) {
		if ((ncts = dup_counts(cur)) != NULL) {
			if (nhead == NULL)
				nhead = ncts;
			else
				prev->next = ncts;

			prev = ncts;
		}
		cur = cur->next;
	}

	return nhead;
}

/**
 * @brief
 * 		find_counts - find a counts structure by name
 *
 * @param[in]	ctslist - the counts list to search
 * @param[in]	name 	- the name to find
 *
 * @return	found counts structure
 * @retval	NULL	: error
 *
 * @par MT-Safe:	no
 */
counts *
find_counts(counts *ctslist, char *name)
{
	counts *cur;

	if (ctslist == NULL || name == NULL)
		return NULL;

	cur = ctslist;

	while (cur != NULL && strcmp(cur->name, name))
		cur = cur->next;

	return cur;
}

/**
 * @brief
 * 		find_alloc_counts - find a counts structure by name or allocate
 *		 a new counts, name it, and add it to the end of the list
 *
 * @param[in]	ctslist - the counts list to search
 * @param[in]	name 	- the name to find
 *
 * @return	found or newly-allocated counts structure
 * @retval	NULL	: error
 *
 * @par MT-Safe:	no
 */
counts *
find_alloc_counts(counts *ctslist, char *name)
{
	counts *cur, *prev;
	counts *new;

	if (name == NULL)
		return NULL;

	prev = cur = ctslist;

	while (cur != NULL && strcmp(cur->name, name)) {
		prev = cur;
		cur = cur->next;
	}

	if (cur == NULL) {
		new = new_counts();

		if (new != NULL)
			new->name = string_dup(name);

		if (prev != NULL)
			prev->next = new;

		return new;
	}
	else
		return cur;
}

/**
 * @brief
 * 		update_counts_on_run - update a counts struct on the running of
 *		a job
 *
 * @param[in]	cts 	- the counts structure to update
 * @param[in]	resreq 	- the resource requirements of the job which ran
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
update_counts_on_run(counts *cts, resource_req *resreq)
{
	resource_req *ctsreq;			/* rescts to update */
	resource_req *req;			/* current in resreq */

	if (cts == NULL)
		return;

	cts->running++;

	if (resreq == NULL)
		return;

	req = resreq;

	while (req != NULL) {
		ctsreq = find_alloc_resource_req(cts->rescts, req->def);

		if (ctsreq != NULL) {
			if (cts->rescts == NULL)
				cts->rescts = ctsreq;

			ctsreq->amount += req->amount;
		}
		req = req->next;
	}
}

/**
 * @brief
 * 		update_counts_on_end - update a counts structure on the end
 *		of a job
 *
 * @param[in]	cts 	- counts structure to update
 * @param[in]	resreq 	- the resource requirements of the job which
 *							ended
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
update_counts_on_end(counts *cts, resource_req *resreq)
{
	resource_req *ctsreq;			/* rescts to update */
	resource_req *req;			/* current in resreq */

	if (cts == NULL || resreq == NULL)
		return;

	cts->running--;

	req = resreq;
	while (req != NULL) {
		ctsreq = find_resource_req(cts->rescts, req->def);
		if (ctsreq != NULL)
			ctsreq->amount -= req->amount;


		req = req->next;
	}
}

/**
 * @brief
 * 		perform a max() between the current list of maxes and a
 *		new list.  If any element from the new list is greater
 *		than the current max, we free the old, and dup the new
 *		and attach it in.
 *
 * @param[in]	cmax - current max
 * @param[in]	new  - new counts lists.  If anything in this list is
 *						greater than the cur_max, it needs to be dup'd.
 *
 * @return	the new max
 * @retval	NULL : error
 */
counts *
counts_max(counts *cmax, counts *new)
{
	counts *cur;
	counts *cur_fmax;
	counts *cmax_head;
	resource_req *cur_res;
	resource_req *cur_res_max;

	if (new == NULL)
		return cmax;

	if (cmax == NULL)
		return dup_counts_list(new);

	cmax_head = cmax;

	for (cur = new; cur != NULL; cur = cur->next) {
		cur_fmax = find_counts(cmax, cur->name);
		if (cur_fmax == NULL) {
			cur_fmax = dup_counts(cur);
			if (cur_fmax == NULL) {
				free_counts_list(cmax_head);
				return NULL;
			}

			cur_fmax->next = cmax_head;
			cmax_head = cur_fmax;
		}
		else {
			if (cur->running > cur_fmax->running)
				cur_fmax->running = cur->running;

			for (cur_res = cur->rescts; cur_res != NULL; cur_res = cur_res->next) {
				cur_res_max = find_resource_req(cur_fmax->rescts, cur_res->def);
				if (cur_res_max == NULL) {
					cur_res_max = dup_resource_req(cur_res);
					if (cur_res_max == NULL) {
						free_counts_list(cmax_head);
						return NULL;
					}

					cur_res_max->next = cur_fmax->rescts;
					cur_fmax->rescts = cur_res_max;
				}
				else {
					if (cur_res->amount > cur_res_max->amount)
						cur_res_max->amount = cur_res->amount;
				}
			}
		}
	}
	return cmax_head;
}

/**
 * @brief
 * 		update_universe_on_end - update a pbs universe when a job/resv
 *		ends
 *
 * @param[in]   policy 		- policy info
 * @param[in]	resresv 	- the resresv itself which is ending
 * @param[in]	job_state 	- the new state of a job if resresv is a job
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
void
update_universe_on_end(status *policy, resource_resv *resresv, char *job_state)
{
	int i;
	server_info *sinfo = NULL;
	queue_info *qinfo = NULL;

	if (resresv == NULL)
		return;

	if (resresv->is_job && job_state == NULL)
		return;

	if (!is_resource_resv_valid(resresv, NULL))
		return;

	sinfo = resresv->server;

	if (resresv->is_job) {
		qinfo = resresv->job->queue;
		if (resresv->job != NULL && resresv->execselect != NULL &&
			resresv->execselect->defs != NULL) {
			int need_metadata_update = 0;
			for (i = 0; resresv->execselect->defs[i] != NULL;i++) {
				if (!resdef_exists_in_array(policy->resdef_to_check, resresv->execselect->defs[i])) {
					add_resdef_to_array(&(policy->resdef_to_check), resresv->execselect->defs[i]);
					need_metadata_update = 1;
				}
			}
			if (need_metadata_update) {
				int j;
				/* Since a new resource was added to resdef_to_check, the meta data needs to be recreated.
				 * This will happen on the next call to node_partition_update()
				 */
				if (sinfo->allpart != NULL) {
					free_resource_list(sinfo->allpart->res);
					sinfo->allpart->res = NULL;
				}
				for (j = 0; sinfo->queues[j] != NULL; j++) {
					queue_info *q = sinfo->queues[j];
					if (q->allpart != NULL) {
						free_resource_list(q->allpart->res);
						q->allpart->res = NULL;
					}
				}
			}
		}
	}

	if (resresv->ninfo_arr != NULL)
		for (i = 0; resresv->ninfo_arr[i] != NULL; i++)
			update_node_on_end(resresv->ninfo_arr[i], resresv, job_state);


	update_server_on_end(policy, sinfo, qinfo, resresv, job_state);

	if (qinfo != NULL)
		update_queue_on_end(qinfo, resresv, job_state);

	update_all_nodepart(policy, sinfo, resresv);

	update_resresv_on_end(resresv, job_state);

#ifdef NAS /* localmod 057 */
	site_update_on_end(sinfo, qinfo, resresv);
#endif /* localmod 057 */
}

/**
 * @brief
 * 		set_resource - set the values of the resource structure.  This
 *		function can be called in one of two ways.  It can be called
 *		with resources_available value, or the resources_assigned
 *		value.
 *
 * @param[in]	res 	- the resource to set
 * @param[in]	val 	- the value to set upon the resource
 * @param[in]	field 	- the type of field to set (available or assigned)
 *
 * @return	int
 * @retval	1 : success
 * @retval	0 : failure/error
 *
 * @note
 * 		If we have resource type information from the server,
 *		we will use it.  If not, we will try to set the
 *		resource type from the resources_available value first,
 *		then from the resources_assigned
 *
 * @par MT-Safe:	no
 */
int
set_resource(schd_resource *res, char *val, enum resource_fields field)
{
	resdef *rdef;

	if (res == NULL || val == NULL)
		return 0;

	if (field == RF_AVAIL) {
		/* if this resource is being re-set, lets free the memory we previously
		 * allocated in the last call to this function.  We NULL the values just
		 * incase we don't reset them later (e.g. originally set a resource
		 * indirect and then later set it directly)
		 */
		if (res->orig_str_avail != NULL) {
			free(res->orig_str_avail);
			res->orig_str_avail = NULL;
		}
		if (res->indirect_vnode_name != NULL) {
			free(res->indirect_vnode_name);
			res->indirect_vnode_name = NULL;
		}
		if (res->str_avail != NULL) {
			free_string_array(res->str_avail);
			res->str_avail = NULL;
		}

		res->orig_str_avail = string_dup(val);
		if (res->orig_str_avail == NULL)
			return 0;

		if (val[0] == '@') {
			res->indirect_vnode_name = string_dup(&val[1]);
			/* res -> indirect_res is assigned by a call to
			 * resolve_indirect_resources()
			 */
			if (res->indirect_vnode_name == NULL)
				return 0;
		}
		else {
			/* if the resource type is already set, clear it so we can set it here */
			if (res->type.is_consumable != 0 || res->type.is_non_consumable !=0)
				memset(&(res->type), 0, sizeof(struct resource_type));

			/* if val is a string, avail will be set to SCHD_INFINITY */
			res->avail = res_to_num(val, &(res->type));
			if (res->avail == SCHD_INFINITY) {
				/* Verify that this is a string type resource */
				if (!res->def->type.is_string)
					return 0;
			}
			res->str_avail = break_comma_list(val);
			if (res->str_avail == NULL)
				return 0;
		}
	}
	else if (field == RF_ASSN) {
		/* clear previously allocated memory in the case of a reassignment */
		if (res->str_assigned != NULL) {
			free(res->str_assigned);
			res->str_assigned = NULL;
		}
		/* only set the type there is not type set */
		if (res->type.is_non_consumable == 0 && res->type.is_consumable == 0)
			res->assigned = res_to_num(val, &(res->type));
		else
			res->assigned = res_to_num(val, NULL);
		res->str_assigned = string_dup(val);
		if (res->str_assigned == NULL)
			return 0;
	}

	if(res->def != NULL)
		rdef = res->def;
	else {
		rdef = find_resdef(allres, res->name);
		res->def = rdef;
	}
	if (rdef != NULL)
		res->type = rdef->type;

	return 1;
}

/**
 * @brief
 * 		find_indirect_resource - follow the indirect resource pointers
 *		to find the real resource at the end
 *
 * @param[in]	res 	- the indirect resource
 * @param[in]	nodes 	- the nodes to search
 *
 * @return	the indirect resource
 * @retval	NULL	: on error
 *
 * @par MT-Safe:	no
 */
schd_resource *
find_indirect_resource(schd_resource *res, node_info **nodes)
{
	node_info *ninfo;
	schd_resource *cur_res = NULL;
	char logbuf[MAX_LOG_SIZE];
	int i;
	int error = 0;
	const int max = 10;

	if (res == NULL || nodes == NULL)
		return NULL;

	cur_res = res;

	for (i = 0; i < max && cur_res != NULL &&
		cur_res->indirect_vnode_name != NULL && !error; i++) {
		ninfo = find_node_info(nodes, cur_res->indirect_vnode_name);
		if (ninfo != NULL) {
			cur_res = find_resource(ninfo->res, cur_res->def);
			if (cur_res == NULL) {
				error = 1;
				sprintf(logbuf,
					"Resource %s is indirect, and does not exist on indirect node %s",
					res->name, ninfo->name);
				schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
					LOG_DEBUG, "find_indirect_resource", logbuf);
			}
		}
		else {
			error = 1;
			sprintf(logbuf,
				"Resource %s is indirect but points to node %s, which was not found",
				res->name, cur_res->indirect_vnode_name);
			schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
				LOG_DEBUG, "find_indirect_resource", logbuf);
			cur_res = NULL;
		}
	}
	if (i == max) {
		sprintf(logbuf, "Attempted %d indirection lookups for resource %s=@%s-- "
			"looks like a cycle, bailing out.",
			max, cur_res->name, cur_res->indirect_vnode_name);
		schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			"find_indirect_resource", logbuf);
		return NULL;
	}

	if (error)
		return NULL;

	return cur_res;
}

/**
 * @brief
 * 		resolve_indirect_resources - resolve indirect resources for node
 *		array
 *
 * @param[in/out]	nodes	-	the nodes to resolve
 *
 * @return	int
 * @retval	1	: if successful
 * @retval	0	: if there were any errors
 *
 * @par MT-Safe:	no
 */
int
resolve_indirect_resources(node_info **nodes)
{
	int i;
	schd_resource *cur_res;
	int error = 0;

	if (nodes == NULL)
		return 0;

	for (i = 0; nodes[i] != NULL; i++) {
		cur_res = nodes[i]->res;
		while (cur_res != NULL) {
			if (cur_res->indirect_vnode_name) {
				cur_res->indirect_res = find_indirect_resource(cur_res, nodes);
				if (cur_res->indirect_res == NULL)
					error = 1;
			}
			cur_res = cur_res->next;
		}
	}

	if (error)
		return 0;

	return 1;
}

/**
 * @brief
 * 		update_preemption_on_run - update preemption status when a
 *		job is run
 *
 * @param[in]	sinfo 	- server where job was run
 * @param[in]	resresv - job which was run
 *
 * @return	void
 *
 * @note
 * 		Must be called after update_server_on_run() and
 *		update_queue_on_run()
 *
 * @note
 * 		The only thing which will change preemption priorities
 *		in the middle of a scheduling cycle is soft user/group/project
 *		limits. If a user, group, or project goes under a limit because
 *		of this job running, we need to update those jobs
 *
 * @par MT-Safe:	no
 */
void
update_preemption_on_run(server_info *sinfo, resource_resv *resresv)
{
	int i;

	if (cstat.preempting && resresv->is_job) {
		if (sinfo->has_soft_limit || resresv->job->queue->has_soft_limit) {
			for (i = 0; sinfo->jobs[i] != NULL; i++) {
				if (sinfo->jobs[i]->job !=NULL) {
					if (!strcmp(resresv->user, sinfo->jobs[i]->user) ||
						!strcmp(resresv->group, sinfo->jobs[i]->group) ||
						!strcmp(resresv->project, sinfo->jobs[i]->project))
						set_preempt_prio(sinfo->jobs[i],
							sinfo->jobs[i]->job->queue, sinfo);
				}
			}
			qsort(sinfo->jobs, sinfo->sc.total,
				sizeof(resource_resv *), cmp_sort);
			for (i = 0; sinfo->queues[i] != NULL; i++) {
				qsort(sinfo->queues[i]->jobs, sinfo->queues[i]->sc.total,
					sizeof(resource_resv *), cmp_sort);
			}

			/* now that we've set all the preempt levels, we need to count them */
			memset(sinfo->preempt_count, 0, NUM_PPRIO * sizeof(int));
			for (i = 0; sinfo->running_jobs[i] != NULL; i++)
				if (!sinfo->running_jobs[i]->job->can_not_preempt)
					sinfo->
					preempt_count[preempt_level(sinfo->running_jobs[i]->job->preempt)]++;
		}
	}
}

/**
 * @brief
 * 		read_formula - read the formula from a well known file
 *
 * @return	formula in malloc'd buffer
 * @retval	NULL	: on error
 *
 * @par MT-Safe:	no
 */
#define RF_BUFSIZE 1024
char *
read_formula(void)
{
	char *form;
	char *tmp;
	char buf[RF_BUFSIZE];
	size_t bufsize = RF_BUFSIZE;
	int len;
	char pathbuf[MAXPATHLEN];
	FILE *fp;


	sprintf(pathbuf, "%s/%s", pbs_conf.pbs_home_path, FORMULA_ATTR_PATH_SCHED);
	if ((fp = fopen(pathbuf, "r")) == NULL) {
		schdlog(PBSEVENT_SYSTEM, PBS_EVENTCLASS_REQUEST, LOG_INFO,
			"read_formula",
			"Can not open file to read job_sort_formula.  "
			"Please reset formula with qmgr.");
		return NULL;
	}

	if ((form = malloc(bufsize + 1)) == NULL) {
		log_err(errno, "read_formula", MEM_ERR_MSG);
		fclose(fp);
		return NULL;
	}

	form[0] = '\0';

	/* first line is a comment */
	fgets(buf, RF_BUFSIZE, fp);

	while (fgets(buf, RF_BUFSIZE, fp) != NULL) {
		len = strlen(form) + strlen(buf);
		if (len > bufsize) {
			tmp = realloc(form, len*2 + 1);
			if (tmp == NULL) {
				log_err(errno, "read_formula", MEM_ERR_MSG);
				free(form);
				fclose(fp);
				return NULL;
			}
			form = tmp;
			bufsize = len;
		}
		strcat(form, buf);
	}

	if (form[strlen(form) - 1] == '\n')
		form[strlen(form) - 1] = '\0';

	fclose(fp);
	return form;
}

/**
 * @brief
 * 		new_status - status constructor
 *
 * @return	status*
 * @retval	NULL	: malloc failed
 */
status *
new_status(void)
{
	status *st;

	st = malloc(sizeof(status));

	if (st == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	memset(st, 0, sizeof(status));

	return st;
}

/**
 * @brief
 * 		dup_status - status copy constructor
 *
 * @param[in]	ost	-	status input
 *
 * @return	duplicated status
 * @retval	NULL	: on error
 */
status *
dup_status(status *ost)
{
	status *nst;

	if (ost == NULL)
		return NULL;

	nst = new_status();
	if (nst == NULL)
		return NULL;

	/* structure to structure shallow copy */
	*nst = *ost;

	/* deep copy what is required */
	nst->resdef_to_check = copy_resdef_array(ost->resdef_to_check);
	nst->resdef_to_check_no_hostvnode =
		copy_resdef_array(ost->resdef_to_check_no_hostvnode);
	nst->resdef_to_check_rassn = copy_resdef_array(ost->resdef_to_check_rassn);
	nst->resdef_to_check_rassn_select = copy_resdef_array(ost->resdef_to_check_rassn_select);
	nst->resdef_to_check_noncons = copy_resdef_array(ost->resdef_to_check_noncons);
	nst->equiv_class_resdef = copy_resdef_array(ost->equiv_class_resdef);
	nst->rel_on_susp = copy_resdef_array(ost->rel_on_susp);


	return nst;
}

/**
 * @brief
 * 		free_status - status destructor
 *
 * @param[in,out]	st	-	status input
 */
void
free_status(status *st)
{
	if (st == NULL)
		return;
	if (st->resdef_to_check != NULL)
		free(st->resdef_to_check);
	if (st->resdef_to_check_no_hostvnode != NULL)
		free(st->resdef_to_check_no_hostvnode);
	if (st->resdef_to_check_rassn != NULL)
		free(st->resdef_to_check_rassn);
	if (st->resdef_to_check_rassn_select != NULL)
		free(st->resdef_to_check_rassn_select);
	if (st->resdef_to_check_noncons != NULL)
		free(st->resdef_to_check_noncons);
	if (st->rel_on_susp != NULL)
		free(st->rel_on_susp);
	if (st->equiv_class_resdef != NULL)
		free(st->equiv_class_resdef);
	free(st);
}

/**
 * @brief
 * 		free_queue_list - to free two dimensional queue_list array
 *
 * @param[in]	in_list - List which need to be deleted.
 *
 * @return	void
 */
void
free_queue_list(queue_info *** queue_list)
{
	int i;

	if (queue_list == NULL)
		return;
	for (i = 0; queue_list[i] != NULL; i++)
		free(queue_list[i]);
	free(queue_list);
}

/**
 * @brief
 * 		create_total_counts - This function checks if
 *	    total_*_counts list for user/group/project and alljobcounts
 *	    is empty and if so, it duplicates or creates new counts with the
 *	    user/group/project name mentioned in resource_resv structure.
 *
 * @param[in,out]  sinfo	-	server_info structure used to check and set
 *                          	total_*_counts
 * @param[in,out]  qinfo   	-	queue_info structure used to check and set
 *                          	total_*_counts
 * @param[in]      resresv 	-	resource_resv structure to get user/group/project
 * @param[in]      mode    	-	To state whether total_*_counts in server_info
 *                          	structure needs to be created or in queue_info.
 *
 * @return	void
 */
void
create_total_counts(server_info *sinfo, queue_info * qinfo,
	resource_resv *resresv, int mode)
{
	if (mode == SERVER || mode == ALL) {
		if (sinfo->total_group_counts == NULL) {
			if (sinfo->group_counts != NULL)
				sinfo->total_group_counts = dup_counts_list(
					sinfo->group_counts);
			else if (resresv != NULL)
				sinfo->total_group_counts = find_alloc_counts(
					sinfo->total_group_counts, resresv->group);
		}
		if (sinfo->total_user_counts == NULL) {
			if (sinfo->user_counts != NULL)
				sinfo->total_user_counts = dup_counts_list(
					sinfo->user_counts);
			else if (resresv != NULL)
				sinfo->total_user_counts = find_alloc_counts(
					sinfo->total_user_counts, resresv->user);
		}
		if (sinfo->total_project_counts == NULL) {
			if (sinfo->project_counts != NULL)
				sinfo->total_project_counts = dup_counts_list(
					sinfo->project_counts);
			else if (resresv != NULL)
				sinfo->total_project_counts = find_alloc_counts(
					sinfo->total_project_counts, resresv->project);
		}
		if (sinfo->total_alljobcounts == NULL) {
			if (sinfo->alljobcounts != NULL)
				sinfo->total_alljobcounts = dup_counts_list(sinfo->alljobcounts);
			else
				sinfo->total_alljobcounts = find_alloc_counts(
					sinfo->total_alljobcounts, "o:" PBS_ALL_ENTITY);
		}
	}
	if (mode == QUEUE || mode == ALL) {
		if (qinfo->total_group_counts == NULL) {
			if (qinfo->group_counts != NULL)
				qinfo->total_group_counts = dup_counts_list(
					qinfo->group_counts);
			else if (resresv != NULL)
				qinfo->total_group_counts = find_alloc_counts(
					qinfo->total_group_counts, resresv->group);
		}
		if (qinfo->total_user_counts == NULL) {
			if (qinfo->user_counts != NULL)
				qinfo->total_user_counts = dup_counts_list(
					qinfo->user_counts);
			else if (resresv != NULL)
				qinfo->total_user_counts = find_alloc_counts(
					qinfo->total_user_counts, resresv->user);
		}
		if (qinfo->total_project_counts == NULL) {
			if (qinfo->project_counts != NULL)
				qinfo->total_project_counts = dup_counts_list(
					qinfo->project_counts);
			else if (resresv != NULL)
				qinfo->total_project_counts = find_alloc_counts(
					qinfo->total_project_counts, resresv->project);
		}
		if (qinfo->total_alljobcounts == NULL) {
			if (qinfo->alljobcounts != NULL)
				qinfo->total_alljobcounts = dup_counts_list(qinfo->alljobcounts);
			else if (resresv != NULL)
				qinfo->total_alljobcounts = find_alloc_counts(
					qinfo->total_alljobcounts, "o:" PBS_ALL_ENTITY);
		}
	}
	return;
}

/**
 * @brief
 * 		update_total_counts update a total counts list on running or
 *         queing a job
 *
 * @param[in]	si		-	server_info structure to use for count updation
 * @param[in]	qi		-	queue_info structure to use for count updation
 * @param[in]	rr		-	resource_resv structure to use for count updation
 * @param[in]  	mode	-	To state whether total_*_counts in server_info
 *                      	structure needs to be updated or in queue_info.
 *
 * @return	void
 *
 */
void
update_total_counts(server_info *si, queue_info* qi,
	resource_resv *rr, int mode)
{
	counts *cts = NULL;
	create_total_counts(si, qi, rr, mode);
	if (((mode == SERVER) || (mode == ALL)) &&
		((si != NULL) && si->has_hard_limit)) {
		cts = si->total_group_counts;
		update_counts_on_run(find_alloc_counts(cts, rr->group), rr->resreq);
		cts = si->total_project_counts;
		update_counts_on_run(find_alloc_counts(cts, rr->project), rr->resreq);
		cts = si->total_alljobcounts;
		update_counts_on_run(cts, rr->resreq);
		cts = si->total_user_counts;
		update_counts_on_run(find_alloc_counts(cts, rr->user), rr->resreq);
	}
	else if (((mode == QUEUE) || (mode == ALL)) &&
		((qi != NULL) && qi->has_hard_limit)) {
		cts = qi->total_group_counts;
		update_counts_on_run(find_alloc_counts(cts, rr->group), rr->resreq);
		cts = qi->total_project_counts;
		update_counts_on_run(find_alloc_counts(cts, rr->project), rr->resreq);
		cts = qi->total_alljobcounts;
		update_counts_on_run(cts, rr->resreq);
		cts = qi->total_user_counts;
		update_counts_on_run(find_alloc_counts(cts, rr->user), rr->resreq);
	}
}

/**
 * @brief
 * 		update_total_counts_on_end update a total counts list on preempting
 *         a running job
 *
 * @param[in]	si		-	server_info structure to use for count updation
 * @param[in]	qi		-	queue_info structure to use for count updation
 * @param[in]	rr		-	resource_resv structure to use for count updation
 * @param[in]  	mode	-	To state whether total_*_counts in server_info
 *                      	structure needs to be updated or in queue_info.
 *
 * @return	void
 *
 */
void
update_total_counts_on_end(server_info *si, queue_info* qi,
	resource_resv *rr, int mode)
{
	counts *cts = NULL;
	create_total_counts(si, qi, rr, mode);
	if (((mode == SERVER) || (mode == ALL)) &&
		((si != NULL) && si->has_hard_limit)) {
		cts = si->total_group_counts;
		update_counts_on_end(find_alloc_counts(cts, rr->group), rr->resreq);
		cts = si->total_project_counts;
		update_counts_on_end(find_alloc_counts(cts, rr->project), rr->resreq);
		cts = si->total_alljobcounts;
		update_counts_on_end(cts, rr->resreq);
		cts = si->total_user_counts;
		update_counts_on_end(find_alloc_counts(cts, rr->user), rr->resreq);
	}
	else if (((mode == QUEUE) || (mode == ALL)) &&
		((qi != NULL) &&  qi->has_hard_limit)) {
		cts = qi->total_group_counts;
		update_counts_on_end(find_alloc_counts(cts, rr->group), rr->resreq);
		cts = qi->total_project_counts;
		update_counts_on_end(find_alloc_counts(cts, rr->project), rr->resreq);
		cts = qi->total_alljobcounts;
		update_counts_on_end(cts, rr->resreq);
		cts = qi->total_user_counts;
		update_counts_on_end(find_alloc_counts(cts, rr->user), rr->resreq);
	}
}

/**
 * @brief
 * 		refresh_total_counts - This function releases memory allocated
 *	    for total_*_counts structure in server_info and queue_info and
 *	    then reassigns again by duplicating it from running counts list.
 *
 * @param[in,out]	sinfo	-	server_info structure used to get all the
 *                          	total_*_counts and free them.
 *
 * @return	void
 */
void
refresh_total_counts(server_info *sinfo)
{
	int i = 0;
	if (sinfo != NULL) {
		free_counts_list(sinfo->total_group_counts);
		sinfo->total_group_counts = NULL;
		free_counts_list(sinfo->total_user_counts);
		sinfo->total_user_counts = NULL;
		free_counts_list(sinfo->total_project_counts);
		sinfo->total_project_counts = NULL;
		free_counts_list(sinfo->total_alljobcounts);
		sinfo->total_alljobcounts = NULL;
		create_total_counts(sinfo, NULL, NULL, SERVER);
		for (; i < sinfo->num_queues; i++) {
			free_counts_list(sinfo->queues[i]->total_group_counts);
			sinfo->queues[i]->total_group_counts = NULL;
			free_counts_list(sinfo->queues[i]->total_user_counts);
			sinfo->queues[i]->total_user_counts = NULL;
			free_counts_list(sinfo->queues[i]->total_project_counts);
			sinfo->queues[i]->total_project_counts = NULL;
			free_counts_list(sinfo->queues[i]->total_alljobcounts);
			sinfo->queues[i]->total_alljobcounts = NULL;
			create_total_counts(NULL, sinfo->queues[i], NULL, QUEUE);
		}
	}
	return;
}

/**
 * @brief
 * 		get a unique rank to uniquely identify an object
 *
 * @return	int
 * @retval	unique number for this scheduling cycle
 */
int
get_sched_rank()
{
	cstat.order++;
	return cstat.order;
}


/**
 * @brief
 * 		add_queue_to_list - This function alligns all queues according to
 *                              their priority.
 *
 * @param[in,out]	qlhead	-	address of 3 dimensional queue list.
 * @param[in]		qinfo	-	queue which is getting added in queue_list.
 *
 * @return	int
 * @retval	1	: If successful in adding the qinfo to queue_list.
 * @retval	0	: If failed to add qinfo to queue_list.
 */
int
add_queue_to_list(queue_info **** qlhead, queue_info * qinfo)
{
	int queue_list_size = 0;
	void * temp = NULL;
	queue_info ***temp_list = NULL;
	queue_info ***list_head;

	if (qlhead == NULL)
	    return 0;

	list_head = *qlhead;
	queue_list_size = count_array((void **)list_head);

	temp_list = find_queue_list_by_priority(list_head, qinfo->priority);
	if (temp_list == NULL) {
		temp = realloc(list_head, (queue_list_size + 2) * sizeof(queue_info**));
		if (temp == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			return 0;
		}
		*qlhead = list_head = temp;
		list_head[queue_list_size] = NULL;
		list_head[queue_list_size + 1] = NULL;
		if (append_to_queue_list(&list_head[queue_list_size], qinfo) == NULL)
			return 0;
	}
	else {
		if (append_to_queue_list(temp_list, qinfo) == NULL)
			return 0;
	}
	return 1;
}

/**
 * @brief
 * 		find_queue_list_by_priority - function finds out the array of queues
 *                               which matches with the priority passed to this
 *                               function. It returns the base address of matching
 *                               array.
 *
 * @param[in]	list_head 	- 	Head pointer to queue_info list.
 * @param[in]	priority 	-  	Priority of the queue that needs to be searched.
 *
 * @return	queue_info*** - base address of array which has given priority.
 * @retval	NULL	: when function is not able to find the array.
 *
 */
struct queue_info *** find_queue_list_by_priority(queue_info *** list_head, int priority)
{
	int i;
	if (list_head == NULL)
		return NULL;
	for (i = 0; list_head[i] != NULL; i++) {
		if ((list_head[i][0] != NULL) && list_head[i][0]->priority == priority)
			return (&list_head[i]);
	}
	return NULL;

}

/**
 * @brief
 * 		append_to_queue_list - function that will reallocate and append
 *                               "add" to the list provided.
 * @param[in,out]	list	-	pointer to queue_info** which gets reallocated
 *                       		and "add" is appended to it.
 * @param[in] 		add 	-   queue_info  that needs to be appended.
 *
 * @return	queue_info** : newly appended list.
 * @retval	NULL	: when realloc fails.
 *           			pointer to appended list.
 */
struct queue_info** append_to_queue_list(queue_info ***list, queue_info *add)
{
	int count = 0;
	queue_info ** temp = NULL;

	if ((list == NULL) || (add == NULL))
		return NULL;
	count = count_array((void **)*list);

	/* count contains number of elements in list (excluding NULL). we add 2 to add the NULL
	 * back in, plus our new element.
	 */
	temp = (queue_info**) realloc(*list, (count + 2) * sizeof(queue_info*));
	if (temp == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}
	temp[count]  = add;
	temp[count + 1] = NULL;
	*list = temp;
	return (*list);
}

/**
 * @brief basically do a reslist->assigned += reqlist->amount for all of reqlist
 * @param reslist - resource list
 * @param reqlist - resource_req list
 * @return
 */
void
add_req_list_to_assn(schd_resource *reslist, resource_req *reqlist)
{
	schd_resource *r;
	resource_req *req;

	if(reslist == NULL || reqlist == NULL)
		return;

	for(req = reqlist; req != NULL; req = req->next) {
		r = find_resource(reslist, req->def);
		if(r != NULL && r->type.is_consumable)
			r->assigned += req->amount;
	}
}

/**
 * @brief create the ninfo->res->assigned values for the node
 * @param ninfo - the node
 * @return int
 * @retval 1 success
 * @retval 0 failure
 */
int
create_resource_assn_for_node(node_info *ninfo)
{
	schd_resource *r;
	int i;

	if(ninfo == NULL)
		return 0;

	for (r = ninfo->res; r != NULL; r = r->next)
		if(r->type.is_consumable)
			r->assigned = 0;

	if (ninfo->job_arr != NULL) {
		for (i = 0; ninfo->job_arr[i] != NULL; i++) {
			/* ignore jobs in reservations.  The resources will be accounted for with the reservation itself.  */
			if (ninfo->job_arr[i]->job != NULL && ninfo->job_arr[i]->job->resv == NULL) {
				if (ninfo->job_arr[i]->nspec_arr != NULL) {
					int j;
					for (j = 0; ninfo->job_arr[i]->nspec_arr[j] != NULL; j++) {
						nspec *n = ninfo->job_arr[i]->nspec_arr[j];
						if (n->ninfo->rank == ninfo->rank)
							add_req_list_to_assn(ninfo->res, n->resreq);
					}
				}
			}
		}
	}

	if (ninfo->run_resvs_arr != NULL) {
		for (i = 0; ninfo->run_resvs_arr[i] != NULL; i++) {
			if (ninfo->run_resvs_arr[i]->nspec_arr != NULL) {
				int j;
				for (j = 0; ninfo->run_resvs_arr[i]->nspec_arr[j] != NULL; j++) {
					nspec *n = ninfo->run_resvs_arr[i]->nspec_arr[j];
					if (n->ninfo->rank == ninfo->rank)
						add_req_list_to_assn(ninfo->res, n->resreq);
				}
			}
		}
	}

	return 1;
}

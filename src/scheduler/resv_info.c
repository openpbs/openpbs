/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
 * @file    resv_info.c
 *
 * @brief
 * 	resv_info.c - This file contains functions related to advance reservations.
 *
 * Functions included are:
 *	stat_resvs()
 *	query_reservations()
 *	query_resv()
 *	new_resv_info()
 *	free_resv_info()
 *	dup_resv_info()
 *	check_new_reservations()
 *	disable_reservation_occurrence()
 *	confirm_reservation()
 *	check_vnodes_down()
 *	release_nodes()
 *	create_resv_nodes()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <pbs_ifl.h>
#include <log.h>
#include <libutil.h>

#include "data_types.h"
#include "resv_info.h"
#include "job_info.h"
#include "queue_info.h"
#include "server_info.h"
#include "misc.h"
#include "sort.h"
#include "globals.h"
#include "node_info.h"
#include "resource_resv.h"
#include "resource.h"
#include "fifo.h"
#include "check.h"
#include "simulate.h"
#include "constant.h"
#include "node_partition.h"
#include "pbs_internal.h"


/**
 * @brief
 * 		Statuses reservations from the server in batch status form.
 *
 * @param[in]	pbs_sd	-	The socket descriptor to the server's connection
 *
 * @return	batch status form of the reservations
 */
struct batch_status *
stat_resvs(int pbs_sd)
{
	struct batch_status *resvs;
	/* used for pbs_geterrmsg() */
	char *errmsg;

	/* get the reservation info from the PBS server */
	if ((resvs = pbs_statresv(pbs_sd, NULL, NULL, NULL)) == NULL) {
		if (pbs_errno) {
			errmsg = pbs_geterrmsg(pbs_sd);
			if (errmsg == NULL)
				errmsg = "";
			sprintf(log_buffer, "pbs_statresv failed: %s (%d)", errmsg, pbs_errno);
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_RESV, LOG_NOTICE, "resv_info",
				log_buffer);
		}
		return NULL;
	}
	return resvs;
}

/**
 *
 *	query_reservations - query the reservations from the server.
 *
 *  Each reservation, is created to reflect its current state in the server.
 *  For a standing reservation, the parent reservation represents the soonest
 *  occurrence known to the server; each remaining occurrence is unrolled to
 *  account for the resources consumed by the standing reservation as a whole.
 *
 *  A degraded reservation, is handled in a manner similar to a confirmed
 *  reservation. Even though resources of a degraded reservation may change in
 *  this scheduling cycle, in case no alternate resources are found, the
 *  reservation retains its currently allocated resources, such that no other
 *  requests make use of the same resources.
 *
 *	  sinfo - the server to query from
 *	  resvs - batch status of the stat'ed reservations
 *
 *	returns an array of reservations
 *
 */
resource_resv **
query_reservations(server_info *sinfo, struct batch_status *resvs)
{
	/* the current reservation in the list */
	struct batch_status *cur_resv;

	/* the array of pointers to internal scheduling structure for reservations */
	resource_resv **resresv_arr;

	/* the current resv */
	resource_resv *resresv;

	/* a convient ptr to make things more simple */
	resource_resv *rjob;

	/* used to calculate the resources assigned per node */
	schd_resource *res;
	resource_req *req;
	nspec *ns;
	node_info *resvnode;
	int j;
	int k;
	int idx = 0; /* index of the server info's resource reservation array */
	int num_resv = 0;

	schd_error *err;

	char logmsg[MAX_LOG_SIZE];

	if (resvs == NULL)
		return NULL;

	err = new_schd_error();
	if(err == NULL)
		return NULL;

	cur_resv = resvs;

	while (cur_resv != NULL) {
		num_resv++;
		cur_resv = cur_resv->next;
	}

	if ((resresv_arr = (resource_resv **) malloc(sizeof(resource_resv *)
		* (num_resv + 1))) == NULL) {
		log_err(errno, "query_reservations", MEM_ERR_MSG);
		pbs_statfree(resvs);
		free_schd_error(err);
		return NULL;
	}
	resresv_arr[0] = NULL;
	sinfo->num_resvs = num_resv;

	for (cur_resv = resvs; cur_resv != NULL; cur_resv = cur_resv->next) {
		int ignore_resv = 0;
		/* convert resv info from server batch_status into resv_info */
		if ((resresv = query_resv(cur_resv, sinfo)) == NULL) {
			pbs_statfree(resvs);
			free_resource_resv_array(resresv_arr);
			free_schd_error(err);
			return NULL;
		}
#ifdef NAS /* localmod 047 */
		if (resresv->place_spec == NULL) {
			resresv->place_spec = parse_placespec("scatter");
		}
#endif /* localmod 047 */

		/* We continue adding valid resvs to our array.  We're
		 * freeing what we allocated and ignoring this resv completely.
		 */
		if (!is_resource_resv_valid(resresv, err) || resresv->is_invalid) {
			schdlogerr(PBSEVENT_DEBUG, PBS_EVENTCLASS_RESV, LOG_DEBUG, resresv->name,
				"Reservation is invalid - ignoring for this cycle", err);
			ignore_resv = 1;
		}
		/* Make sure it is not a future reservation that is being deleted, if so ignore it */
		else if ((resresv->resv->resv_state == RESV_BEING_DELETED) && (resresv->start > sinfo->server_time)) {
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_RESV, LOG_DEBUG,
				resresv->name, "Future reservation is being deleted, ignoring this reservation");
			ignore_resv = 1;
		}
		else if ((resresv->resv->resv_state == RESV_BEING_DELETED) && (resresv->resv->resv_nodes != NULL) &&
			(!is_string_in_arr(resresv->resv->resv_nodes[0]->resvs, resresv->name))) {
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_RESV, LOG_DEBUG,
				resresv->name, "Reservation is being deleted and not present on node, ignoring this reservation");
			ignore_resv = 1;
		}

		if (ignore_resv == 1) {
			sinfo->num_resvs--;
			free_resource_resv(resresv);
			continue;
		}

		resresv->rank = get_sched_rank();

		resresv->aoename = getaoename(resresv->select);
		resresv->eoename = geteoename(resresv->select);

		/* reservations requesting AOE mark nodes as exclusive */
		if (resresv->aoename) {
			resresv->place_spec->share = 0;
			resresv->place_spec->excl = 1;
		}

		/*
		 * Check to see if we can attempt to confirm this reservation.
		 * If we can, then then all we will do in this cycle is attempt
		 * to confirm reservations.  In that case, build the calendar
		 * using the hard durations of jobs.
		 */
		if (will_confirm(resresv, sinfo->server_time))
			sinfo->use_hard_duration = 1;

		resresv->duration = resresv->resv->req_duration;
		resresv->hard_duration = resresv->duration;
		if (resresv->resv->resv_state !=RESV_UNCONFIRMED) {
			resresv->start = resresv->resv->req_start;
			if(resresv->resv->resv_state == RESV_BEING_DELETED ||
			   resresv->start + resresv->duration <= sinfo->server_time) {
				resresv->end = sinfo->server_time + EXITING_TIME;
			} else
				resresv->end = resresv->resv->req_end;
		}

		/* Skip all but general reservations. */
		if (resresv->resv->resv_type == 2) {
			if (resresv->node_set_str != NULL) {
				resresv->node_set = create_node_array_from_str(
					resresv->server->unassoc_nodes, resresv->node_set_str);
			}
			resresv->resv->resv_queue =
				find_queue_info(sinfo->queues, resresv->resv->queuename);
			if (is_resresv_running(resresv)) {
				for (j = 0; resresv->ninfo_arr[j] != NULL; j++)
					resresv->ninfo_arr[j]->num_run_resv++;
			}

			if (resresv->resv->resv_queue != NULL) {
				resresv->resv->resv_queue->resv = resresv;
				if (resresv->resv->resv_queue->jobs != NULL) {
					for (j = 0; resresv->resv->resv_queue->jobs[j] != NULL; j++) {
						rjob = resresv->resv->resv_queue->jobs[j];
						rjob->job->resv = resresv;
						rjob->job->can_not_preempt = 1;
						if (rjob->node_set_str != NULL)
							rjob->node_set =
								create_node_array_from_str(resresv->resv->resv_nodes,
								rjob->node_set_str);

						/* if a job will exceed the end time of a duration, it will be
						 * killed by the server. We set the job's end time to the resv's
						 * end time for better estimation.
						 */
						if (sinfo->server_time + rjob->duration > resresv->end) {
							rjob->duration = resresv->end - sinfo->server_time;
							rjob->hard_duration = rjob->duration;
							if (rjob->end != UNSPECIFIED)
								rjob->end = resresv->end;
						}

						if (rjob->job->is_running) {
							/* the reservations resv_nodes is pointing to
							 * a node_info array with just the reservations part of the node
							 * i.e. the universe of the reservation
							 */
							for (k = 0; rjob->nspec_arr[k] != NULL; k++) {
								ns = rjob->nspec_arr[k];
								resvnode = find_node_info(resresv->resv->resv_nodes,
									ns->ninfo->name);

								if (resvnode != NULL) {
									/* update the ninfo to point to the ninfo in our universe */
									ns->ninfo = resvnode;
									rjob->ninfo_arr[k] = resvnode;

									/* update resource assigned amounts on the nodes in the
									 * reservation's universe
									 */
									req = ns->resreq;
									while (req != NULL) {
										if (req->type.is_consumable) {
											res = find_resource(ns->ninfo->res, req->def);
											if (res != NULL)
												res->assigned += req->amount;
										}
										req = req->next;
									}
								}
								else {
#ifdef NAS /* localmod 031 */
									sprintf(log_buffer, "Job has been assigned a node that doesn't exist in its reservation: %s", ns->ninfo->name);
									schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, rjob->name, log_buffer);
#else
									schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, rjob->name,
										"Job has been assigned a node which doesn't exist in its reservation");
#endif /* localmod 031 */
								}
							}
							if (rjob->ninfo_arr[k] != NULL) {
								schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, rjob->name,
									"Job's node array has different length than nspec_arr in query_reservations()");
							}
						}
					}
					collect_jobs_on_nodes(resresv->resv->resv_nodes, resresv->resv->resv_queue->jobs, j);

					/* Sort the nodes to ensure correct job placement. */
					qsort(resresv->resv->resv_nodes,
						count_array((void **) resresv->resv->resv_nodes),
						sizeof(node_info *), multi_node_sort);
				}
			}
			/* The server's info only gives information about a single reservation
			 * object. In the case of a standing reservation, it is up to the
			 * scheduler to account for each occurrence and attempt to confirm the
			 * reservation.
			 *
			 * In such a case, each occurrence has to be 'cloned'
			 * by duplicating the parent reservation and setting the specific start
			 * and end times and unique execvnodes for each occurrence.
			 *
			 * Note that because the first occurrence may reschedule the start time
			 * from the one submitted by reserve_start (see -R of pbs_rsub), the
			 * initial start time has to be reconfirmed. An example of such
			 * rescheduling is:
			 *   pbs_rsub -R 2000 -E 2100 -r "FREQ=DAILY;BYHOUR=9,20;COUNT=2"
			 * for which the first occurrence is 9am and then 8pm.
			 * BYHOUR takes priority over the start time specified by -R of pbs_rsub.
			 *
			 * Only unroll the occurrences if the parent reservation has been
			 * confirmed.
			 */
			if (resresv->resv->is_standing &&
				(resresv->resv->resv_state == RESV_CONFIRMED ||
				resresv->resv->resv_state == RESV_BEING_ALTERED ||
				resresv->resv->resv_state == RESV_RUNNING)) {
				resource_resv *resresv_ocr = NULL; /* the occurrence's resource_resv */
				char *execvnodes_seq = NULL; /* confirmed execvnodes sequence string */
				char **execvnode_ptr = NULL;
				char **tofree = NULL;
				resource_resv **tmp = NULL;
				time_t dtstart;
				time_t next;
				char *rrule = NULL;
				char *tz = NULL;
				struct tm* loc_time;
				char start_time[18];
				int count = 0;
				int occr_count; /* occurrences  count as reported by execvnodes_seq */
				int occr_idx = 1; /* the occurrence index of a standing reservation */
				int degraded_idx; /* index corrected to account for reconfirmation */

				/* occr_idx refers to the soonest occurrence to run or currently running
				 * Note that resv_idx starts at 1 on the first occurrence and not 0.
				 */
				occr_idx = resresv->resv->resv_idx;
				execvnodes_seq = string_dup(resresv->resv->execvnodes_seq);
				/* the error handling for the string duplication returning NULL is
				 * combined with the following assignment, because get_execvnodes_count
				 * returns 0 if passed a NULL argument
				 */
				occr_count = get_execvnodes_count(execvnodes_seq);
				/* this should happen only if the execvnodes_seq are corrupted. In such
				 * case, we ignore the reservation and move on to the next one */
				if (occr_count == 0) {
					schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_RESV, LOG_DEBUG,
						resresv->name, "Error processing standing reservation");
					free(execvnodes_seq);
					sinfo->num_resvs--;
					free_resource_resv(resresv);
					continue;
				}
				/* unroll_execvnode_seq will destroy the first argument that is passed
				 * to it by calling tokenizing functions, hence, it has to be duplicated
				 */
				execvnode_ptr = unroll_execvnode_seq(execvnodes_seq, &tofree);
				count = resresv->resv->count;

				/* 'count' and 'occr_idx' attributes persist through the life of the
				 * standing reservation. After a reconfirmation, the new execvnodes
				 * sequence may be shortened, therefore the occurrence index used to
				 * identify which execvnode is associated to which occurrence needs to
				 * be adjusted to take into account the elapsed occurrences
				 */
				degraded_idx = occr_idx - (count - occr_count);

				/* The number of remaining occurrences to add to the svr_info is given
				 * by the total number of occurrences (count) to which we subtract the
				 * number of elapsed occurrences that started at 1.
				 * For example, if a standing reservation for a count of 10 is submitted
				 * and the reservation has already run 2 and is now scheduling the 3rd
				 * one to start, then occr_idx is 3. The number of remaining occurrences
				 * to add to the server info is then 10-3=7
				 * Note that 'count - occr_idx' is identical to
				 * 'occr_count - degraded_idx'
				 */
				sinfo->num_resvs += count - occr_idx;

				/* Resize the reservations array to append each occurrence */
				if ((tmp = (resource_resv **) realloc(resresv_arr,
					sizeof(resource_resv *) * (sinfo->num_resvs + 1))) == NULL) {
					log_err(errno, "query_reservations", MEM_ERR_MSG);
					pbs_statfree(resvs);
					free_resource_resv_array(resresv_arr);
					free_execvnode_seq(tofree);
					free(execvnodes_seq);
					free(execvnode_ptr);
					free_schd_error(err);
					return NULL;
				}
				resresv_arr = tmp;

				rrule = resresv->resv->rrule;
				dtstart = resresv->resv->req_start;
				tz = resresv->resv->timezone;

				/* Do not attempt to re-confirm a degraded reservations with a
				 * retry time in the past that is currently in state running */
				if (resresv->resv->resv_state == RESV_RUNNING &&
					resresv->resv->resv_substate == RESV_DEGRADED &&
					resresv->resv->retry_time <= sinfo->server_time)
					resresv->resv->retry_time = (sinfo->server_time) + 1;

				/* Add each occurrence to the universe's view by duplicating the
				 * parent reservation and resetting start and end times and the
				 * execvnode on which the occurrence is confirmed to run.
				 */
				for (j = 0; occr_idx <= count; occr_idx++, j++, degraded_idx++) {
					/* Get the start time of the next occurrence computed from dtstart.
					 * The server maintains state of a single reservation object for
					 * which in the case of a standing reservation, it updates start
					 * and end times and execvnodes.
					 * The last argument (j+1) indicates the occurrence index from dtstart
					 * starting at 1. Returns dtstart if it's an advance reservation.
					 */
					next = get_occurrence(rrule, dtstart, tz, j + 1);

					/* Duplicate the "master" resv only for subsequent occurrences */
					if (j == 0)
						resresv_ocr = resresv;
					else {
						resresv_ocr = dup_resource_resv(resresv, sinfo, NULL);
						if (resresv_ocr == NULL) {
							log_err(errno,
								"query_reservations",
								"Error duplicating resource reservation");
							pbs_statfree(resvs);
							free_resource_resv_array(resresv_arr);
							free_execvnode_seq(tofree);
							free(execvnodes_seq);
							free(execvnode_ptr);
							free_schd_error(err);
							return NULL;
						}
						if (resresv->resv->resv_state == RESV_RUNNING ||
							resresv->resv->resv_state == RESV_BEING_ALTERED) {
							/* Each occurrence will be added to the simulation framework and
							 * should not be in running state. Their state should be
							 * Confirmed instead of possibly inheriting the Running state
							 * from the parent reservation.
							 */
							resresv_ocr->resv->resv_state = RESV_CONFIRMED;
						}
						/* Duplication deep-copies node info array. This array gets
						 * overwritten and needs to be freed. This is an alternative
						 * to creating another duplication function that only duplicates
						 * the required fields.
						 */
						release_nodes(resresv_ocr);

						resresv_ocr->nspec_arr = parse_execvnode(
							execvnode_ptr[degraded_idx-1], sinfo);
						resresv_ocr->ninfo_arr
						= create_node_array_from_nspec(resresv_ocr->nspec_arr);
						resresv_ocr->resv->resv_nodes = create_resv_nodes(
							resresv_ocr->nspec_arr, sinfo);
					}

					/* Set occurrence start and end time and nodes information. On the
					 * first occurrence the start time may need to be reset to the time
					 * specified by the recurrence rule. See description at the head of
					 * this block.
					 */
					resresv_ocr->resv->req_start = next;
					resresv_ocr->resv->req_end = next + resresv->duration;
					resresv_ocr->start = resresv_ocr->resv->req_start;
					resresv_ocr->end = resresv_ocr->resv->req_end;
					resresv_ocr->resv->resv_idx = occr_idx;

					/* Add the occurrence to the global array of reservations */
					resresv_arr[idx++] = resresv_ocr;
					resresv_arr[idx] = NULL;

					loc_time = localtime(&resresv_ocr->start);

					if (loc_time == NULL ||
						strftime(start_time, sizeof(start_time), "%Y%m%d-%H:%M:%S",
						loc_time) == 0) {
						free_resource_resv_array(resresv_arr);
						free_execvnode_seq(tofree);
						free(execvnodes_seq);
						free(execvnode_ptr);
						free_schd_error(err);
						return NULL;
					}
					sprintf(logmsg, "Occurrence %d/%d,%s", occr_idx, count, start_time);
					schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_RESV, LOG_DEBUG,
						resresv->name, logmsg);
				}
				/* The parent reservation has already been added so move on to handling
				 * the next reservation
				 */

				free_execvnode_seq(tofree);
				free(execvnodes_seq);
				free(execvnode_ptr);

				continue;
			} else {
				resresv_arr[idx++] = resresv;
				resresv_arr[idx] = NULL;
			}
		}
	}

	pbs_statfree(resvs);
	free_schd_error(err);

	return resresv_arr;
}


/**
 * @brief
 *		query_resv - convert the servers batch_status structure into a
 *			 resource_resv/resv_info structs for easier access
 *
 * @param[in]	resv	-	a single reservation in batch_status form
 * @param[in]	sinfo 	- 	the server
 *
 * @return	the converted resource_resv struct
 *
 */
resource_resv *
query_resv(struct batch_status *resv, server_info *sinfo)
{
	struct attrl	*attrp = NULL;		/* linked list of attributes from server */
	resource_resv	*advresv = NULL;	/* resv_info to be created */
	resource_req	*resreq = NULL;		/* used for the ATTR_l resources */
	char		*endp = NULL;		/* used with strtol() */
	long		count = 0; 		/* used to convert string -> num */
	char		*selectspec = NULL;	/* used for holding select specification. */

	if ((advresv = new_resource_resv()) == NULL)
		return NULL;

	if ((advresv->resv = new_resv_info()) == NULL) {
		free_resource_resv(advresv);
		return NULL;
	}

	attrp = resv->attribs;
	advresv->name = string_dup(resv->name);
	advresv->server = sinfo;
	advresv->is_resv = 1;

	while (attrp != NULL) {
		if (!strcmp(attrp->name, ATTR_resv_owner))
			advresv->user = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_egroup))
			advresv->group = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_queue))
			advresv->resv->queuename = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_SchedSelect)) {
			advresv->select = parse_selspec(attrp->value);
			if (advresv->select != NULL && advresv->select->chunks != NULL) {
				/* Ignore resv if any of the chunks has no resource req. */
				int i;
				for (i = 0; advresv->select->chunks[i] != NULL; i++)
					if (advresv->select->chunks[i]->req == NULL)
						advresv->is_invalid = 1;
			}
		}
		else if (!strcmp(attrp->name, ATTR_resv_start)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			advresv->resv->req_start = count;
		}
		else if (!strcmp(attrp->name, ATTR_resv_end)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			advresv->resv->req_end = count;
		}
		else if (!strcmp(attrp->name, ATTR_resv_duration)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			advresv->resv->req_duration = count;
		}
		else if (!strcmp(attrp->name, ATTR_resv_retry)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			advresv->resv->retry_time = count;
		}
		else if (!strcmp(attrp->name, ATTR_resv_type)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			advresv->resv->resv_type = count;
		}
		else if (!strcmp(attrp->name, ATTR_resv_state)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			advresv->resv->resv_state = (enum resv_states) count;
		}
		else if (!strcmp(attrp->name, ATTR_resv_substate)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp != '\0')
				count = -1;
			advresv->resv->resv_substate = (enum resv_states) count;
		} else if (!strcmp(attrp->name, ATTR_l)) { /* resources requested*/
			resreq = find_alloc_resource_req_by_str(advresv->resreq, attrp->resource);
			if (resreq == NULL) {
				free_resource_resv(advresv);
				return NULL;
			}

			if (set_resource_req(resreq, attrp->value) != 1)
				advresv->is_invalid = 1;
			else {
				if (advresv->resreq == NULL)
					advresv->resreq = resreq;
				if (!strcmp(attrp->resource, "place")) {
					advresv->place_spec = parse_placespec(attrp->value);
					if (advresv->place_spec == NULL)
						advresv->is_invalid = 1;
				}
			}
		}
		else if (!strcmp(attrp->name, ATTR_resv_nodes)) {
			/* parse the execvnode and create an nspec array with ninfo ptrs pointing
			 * to nodes in the real server
			 */
			advresv->nspec_arr = parse_execvnode(attrp->value, sinfo);
			advresv->ninfo_arr = create_node_array_from_nspec(advresv->nspec_arr);

			/* create a node info array by copying the nodes and setting
			 * available resources to only the ones assigned to the reservation
			 */
			advresv->resv->resv_nodes = create_resv_nodes(advresv->nspec_arr,
				sinfo);
			selectspec = create_select_from_nspec(advresv->nspec_arr);
			advresv->execselect = parse_selspec(selectspec);
			free(selectspec);
		}
		else if (!strcmp(attrp->name, ATTR_node_set))
			advresv->node_set_str = break_comma_list(attrp->value);
		else if (!strcmp(attrp->name, ATTR_resv_timezone))
			advresv->resv->timezone = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_resv_rrule))
			advresv->resv->rrule = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_resv_execvnodes))
			advresv->resv->execvnodes_seq = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_resv_idx))
			advresv->resv->resv_idx = atoi(attrp->value);
		else if (!strcmp(attrp->name, ATTR_resv_standing)) {
			count = atoi(attrp->value);
			advresv->resv->is_standing = count;
		}
		else if (!strcmp(attrp->name, ATTR_resv_count))
			advresv->resv->count = atoi(attrp->value);
		attrp = attrp->next;
	}
	/* If reservation is unconfirmed and the number of occurrences is 0 then flag
	 * the reservation as invalid. This is an extra check but isn't supposed to
	 * happen because the server will purge such reservations.
	 */
	if (advresv->resv->resv_state == RESV_UNCONFIRMED &&
		get_num_occurrences(advresv->resv->rrule,
		advresv->resv->req_start,
		advresv->resv->timezone) ==0)
		advresv->is_invalid = 1;

	/* When a reservation is recognized as DEGRADED, it is converted into
	 * state = CONFIRMED; substate = DEGRADED
	 * From the scheduler's perspective, the reservation is CONFIRMED in that its
	 * allocated resources remain scheduled in the calendar, but it is
	 * handled as an UNCONFIRMED reservation when its resources are to be
	 * replaced.
	 */
	if (advresv->resv->resv_state ==RESV_DEGRADED) {
		advresv->resv->resv_state = RESV_CONFIRMED;
		advresv->resv->resv_substate = RESV_DEGRADED;
	}
	return advresv;
}

/**
 * @brief
 *		new_resv_info - allocate and initialize new resv_info structure
 *
 * @return	the new structure
 *
 */
resv_info *
new_resv_info()
{
	resv_info *rinfo;

	if ((rinfo = (resv_info *) malloc(sizeof(resv_info))) == NULL) {
		log_err(errno, "new_resv_info", MEM_ERR_MSG);
		return NULL;
	}

	rinfo->queuename = NULL;
	rinfo->req_start = UNSPECIFIED;
	rinfo->req_end = UNSPECIFIED;
	rinfo->req_duration = UNSPECIFIED;
	rinfo->retry_time = UNSPECIFIED;
	rinfo->resv_type = UNSPECIFIED;
	rinfo->resv_state = RESV_NONE;
	rinfo->resv_substate = RESV_NONE;
	rinfo->resv_queue = NULL;
	rinfo->resv_nodes = NULL;
	rinfo->timezone = NULL;
	rinfo->rrule = NULL;
	rinfo->resv_idx = 1;
	rinfo->execvnodes_seq = NULL;
	rinfo->count = 0;
	rinfo->is_standing = 0;
	rinfo->check_alternate_nodes = 0;
	rinfo->occr_start_arr = NULL;

	return rinfo;
}

/**
 * @brief
 *		free_resv_info - free all the memory used by a rev_info structure
 *
 * @param[in]	rinfo	-	the resv_info to free
 *
 * @return	nothing
 *
 */
void
free_resv_info(resv_info *rinfo)
{
	if (rinfo->queuename != NULL)
		free(rinfo->queuename);

	if (rinfo->resv_nodes != NULL)
		free_nodes(rinfo->resv_nodes);

	if (rinfo->timezone != NULL)
		free(rinfo->timezone);

	if (rinfo->rrule != NULL)
		free(rinfo->rrule);

	if (rinfo->execvnodes_seq != NULL)
		free(rinfo->execvnodes_seq);

	if (rinfo->occr_start_arr != NULL)
		free(rinfo->occr_start_arr);

	free(rinfo);

}

/**
 * @brief
 *		dup_resv_info - duplicate a reservation
 *
 * @param[in]	rinfo	-	the reservation to duplicate
 * @param[in]	sinfo 	-	the server the NEW reservation belongs to
 *
 * @return	duplicated reservation
 *
 */
resv_info *
dup_resv_info(resv_info *rinfo, server_info *sinfo)
{
	resv_info *nrinfo;

	if (rinfo == NULL)
		return NULL;

	if ((nrinfo = new_resv_info()) == NULL)
		return NULL;

	if (rinfo->queuename != NULL)
		nrinfo->queuename = string_dup(rinfo->queuename);

	nrinfo->req_start = rinfo->req_start;
	nrinfo->req_end = rinfo->req_end;
	nrinfo->req_duration = rinfo->req_duration;
	nrinfo->retry_time = rinfo->retry_time;
	nrinfo->resv_type = rinfo->resv_type;
	nrinfo->resv_state = rinfo->resv_state;
	nrinfo->resv_substate = rinfo->resv_substate;
	nrinfo->is_standing = rinfo->is_standing;
	nrinfo->check_alternate_nodes = rinfo->check_alternate_nodes;
	nrinfo->timezone = string_dup(rinfo->timezone);
	nrinfo->rrule = string_dup(rinfo->rrule);
	nrinfo->resv_idx = rinfo->resv_idx;
	nrinfo->execvnodes_seq = string_dup(rinfo->execvnodes_seq);
	nrinfo->count = rinfo->count;

	/* the queues may not be available right now.  If they aren't, we'll
	 * catch this when we duplicate the queues
	 */
	if (rinfo->resv_queue != NULL)
		nrinfo->resv_queue = find_queue_info(sinfo->queues, rinfo->queuename);

	if (rinfo->resv_nodes != NULL)
#ifdef NAS /* localmod 049 */
		nrinfo->resv_nodes = dup_nodes(rinfo->resv_nodes, sinfo, NO_FLAGS, 0);
#else
		nrinfo->resv_nodes = dup_nodes(rinfo->resv_nodes, sinfo, NO_FLAGS);
#endif /* localmod 049 */

	return nrinfo;
}

/**
 * @brief
 * 		check for new reservations and handle them
 *		if we can serve the reservation, we reserve it
 *		and if we can't, we delete the reservation
 * @par
 *  	For a standing reservation, each occurrence is unrolled and attempted
 * 		to be confirmed. If a single occurrence fails to be confirmed, then the
 * 		standing reservation is rejected.
 * @par
 *  	For a degraded reservation, the resources allocated to the reservation
 * 		are free'd in the simulated universe, and we attempt to reconfirm resources
 * 		for it. If it fails then we inform the server that the reconfirmation has
 * 		failed. If it succeeds, then the previously allocated resources are freed
 * 		from the real universe and replaced by the newly allocated resources.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	pbs_sd	-	communication descriptor to PBS server
 * @param[in]	resvs	-	list of reservations
 * @param[in]	sinfo	-	the server who owns the reservations
 *
 * @return	int
 * @retval	number of reservations confirmed
 * @retval	-1	: something went wrong with confirmation, retry later
 *
 */
int
check_new_reservations(status *policy, int pbs_sd, resource_resv **resvs, server_info *sinfo)
{
	int		count = 0;	/* new reservation count */
	int		pbsrc = 0;	/* return code from pbs_confirmresv() */

	server_info	*nsinfo = NULL;
	resource_resv	*nresv = NULL;
	resource_resv	*nresv_copy = NULL;
	resource_resv	**tmp_resresv = NULL;

	char		**occr_execvnodes_arr = NULL;
	char		**tofree = NULL;
	int		occr_count =1;
	int		i;
	int		j;

	if (sinfo == NULL)
		return -1;

	/* If no reservations to check then return, this is not an error */
	if (resvs == NULL)
		return 0;

	qsort(sinfo->resvs, sinfo->num_resvs, sizeof(resource_resv*), cmp_resv_state);

	for (i = 0; sinfo->resvs[i] != NULL; i++) {

		if (sinfo->resvs[i]->resv ==NULL) {
			schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
				sinfo->resvs[i]->name,
				"Error determining if reservation can be confirmed: "
				"Could not find the reservation.");
			continue;
		}

		/* If the reservation is unconfirmed OR is degraded and not running, with a
		 * retry time that is in the past, then the reservation has to be
		 * respectively confirmed and reconfirmed.
		 */
		if (will_confirm(sinfo->resvs[i], sinfo->server_time)) {
			/* Clone the real universe for simulation scratch work. This universe
			 * will be garbage collected after simulation completes.
			 */
			nsinfo = dup_server_info(sinfo);

			if (nsinfo == NULL)
				return -1;

			/* Resource reservations are ordered by event time, in the case of a
			 * standing reservation, the first to be found will be the "parent"
			 * reservation
			 */
			nresv = find_resource_resv_by_indrank(nsinfo->resvs, sinfo->resvs[i]->rank, sinfo->resvs[i]->resresv_ind);
			if (nresv == NULL) {
				schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
					sinfo->resvs[i]->name,
					"Error determining if reservation can be confirmed: "
					"Resource not found.");
				free_server(nsinfo, 1);
				return -1;
			}

			/* Attempt to confirm the reservation. For a standing reservation,
			 * each occurrence is unrolled and attempted to be confirmed within the
			 * function.
			 */
			pbsrc = confirm_reservation(policy, pbs_sd, nresv , nsinfo);

			/* confirm_reservation only returns success if all occurrences were
			 * confirmed and the communication with the server returned no error
			 */
			if (pbsrc == RESV_CONFIRM_SUCCESS) {
				/* If a degraded reservation, then we need to release the resources
				 * that were previously allocated to the reservation in the real
				 * universe. These resources will be replaced by the newly allocated
				 * ones from the simulated server universe.
				 */
				if (nresv->resv->resv_substate == RESV_DEGRADED)
					release_nodes(sinfo->resvs[i]);

				/* the number of occurrences is set during the confirmation process */
				occr_count = nresv->resv->count;

				/* Now deal with updating the "real" server universe */

				/* If a standing reservation, unroll the string representation of the
				 * sequence of execvnodes into an array of pointer to execvnodes */
				if (nresv->resv->is_standing) {
					/* "tofree" is a pointer array to a list of unique execvnodes. It is
					 * safely freed exclusively by calling free_execvnode_seq
					 */
					occr_execvnodes_arr = unroll_execvnode_seq(
						nresv->resv->execvnodes_seq, &tofree);
					if (occr_execvnodes_arr == NULL) {
						schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
							sinfo->resvs[i]->name,
							"Error unrolling standing reservation.");
						free_server(nsinfo, 1);
						return -1;
					}
				}
				else {
					/* Since we will use occr_execvnodes_arr both for standing and advance
					 * reservations, we create an array with a single entry to hold the
					 * advance reservation's execvnode.
					 */
					occr_execvnodes_arr = malloc(sizeof(char *));
					if (occr_execvnodes_arr == NULL) {
						free_server(nsinfo, 1);
						log_err(errno, "check_new_reservations", MEM_ERR_MSG);
						return -1;
					}
					*occr_execvnodes_arr = nresv->resv->execvnodes_seq;
				}

				/* Iterate over all occurrences (would be 1 for advance reservations)
				 * and copy the information collected during simulation back into the
				 * real universe
				 */
				for (j = 0; j < occr_count; j++) {
					/* On first occurrence, the reservation is the "parent" reservation */
					if (j == 0) {
						nresv_copy = sinfo->resvs[i];
					}
					/* Subsequent occurrences need to be either modified or created
					 * depending on whether the reservation is to be reconfirmed or
					 * is getting confirmed for the first time.
					 */
					else {
						/* For a degraded reservation, it had already been confirmed in a
						 * previous scheduling cycle. We retrieve the existing object from
						 * the all_resresv list
						 */
						if (nresv->resv->resv_substate == RESV_DEGRADED) {
							nresv_copy = find_resource_resv_by_time(sinfo->all_resresv,
								nresv_copy->name, nresv->resv->occr_start_arr[j]);
							if (nresv_copy == NULL) {
								schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV,
									LOG_INFO, nresv->name,
									"Error determining if reservation can be confirmed: "
									"Could not find reservation by time.");
								break;
							}
						}
						else {
							/* For a new, unconfirmed, reservation, we duplicate the parent
							 * reservation
							 */
							nresv_copy = dup_resource_resv(nresv_copy, sinfo, NULL);
							if (nresv_copy == NULL)
								break;
						}
						/* Duplication deep-copies node info array. This array gets
						 * overwritten and needs to be freed. This is an alternative
						 * to creating another duplication function that only duplicates
						 * the required fields.
						 */
						release_nodes(nresv_copy);
						nresv_copy->nspec_arr = parse_execvnode(occr_execvnodes_arr[j],
							sinfo);
						nresv_copy->ninfo_arr = create_node_array_from_nspec(
							nresv_copy->nspec_arr);
						nresv_copy->resv->resv_nodes = create_resv_nodes(
							nresv_copy->nspec_arr, sinfo);
					}

					/* Note that the sequence of occurrence dates and time are determined
					 * during confirm_reservation and set to the reservation in the
					 * simulated server
					 */
					nresv_copy->start = nresv->resv->occr_start_arr[j];

					/* update start time, duration, and execvnodes of the occurrence */
					nresv_copy->end = nresv_copy->start + nresv_copy->duration ;

					/* Only add the occurrence to the real universe if we are not
					 * processing a degraded reservation as otherwise, the resources
					 * had already been added to the real universe in query_reservations
					 */
					if (nresv_copy->resv->resv_substate != RESV_DEGRADED) {
						timed_event *te_start;
						timed_event *te_end;
						te_start = create_event(TIMED_RUN_EVENT, nresv_copy->start,
							nresv_copy, NULL, NULL);
						if (te_start == NULL)
							break;
						te_end = create_event(TIMED_END_EVENT, nresv_copy->end,
							nresv_copy, NULL, NULL);
						if (te_end == NULL) {
							free_timed_event(te_start);
							break;
						}
						add_event(sinfo->calendar, te_start);
						add_event(sinfo->calendar, te_end);

						if (j > 0) {
							tmp_resresv = add_resresv_to_array(sinfo->resvs, nresv_copy);
							if (tmp_resresv == NULL)
								break;
							sinfo->resvs = tmp_resresv;
							sinfo->num_resvs++;
						}
					}

					/* Confirm the reservation such that it is not looked at again in the
					 * main loop of this function.
					 */
					nresv_copy->resv->resv_state = RESV_CONFIRMED;
					nresv_copy->resv->resv_substate = RESV_CONFIRMED;
				}
				/* increment the count if we successfully processed all occurrences */
				if (j == occr_count)
					count++;
			}
			else if (pbsrc == RESV_CONFIRM_FAIL) {
				/* For a degraded reservation, it had already been confirmed in a
				 * previous scheduling cycle. We retrieve the existing object from
				 * the all_resresv list and update the retry_time to break out of
				 * the main loop that checks for reservations that need confirmation
				 */
				if (nresv->resv->resv_substate == RESV_DEGRADED) {
					for (j = 0; j < nresv->resv->count; j++) {
						nresv_copy = find_resource_resv_by_time(sinfo->all_resresv,
							nresv->name, nresv->resv->occr_start_arr[j]);
						if (nresv_copy == NULL) {
							schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV,
								LOG_INFO, nresv->name,
								"Error determining if reservation can be confirmed: "
								"Could not find reservation by time.");
							break;
						}
						/* Update the retry time such that occurrences of a standing
						 * reservation do not independently attempt to be reconfirmed
						 * This is meant to break out of the conditional that checks what
						 * will be considered "confirmable" by the scheduler. Either one
						 * of updating the substate to something else than RESV_DEGRADED or
						 * updating the reservation retry time to some time in the future
						 * invalidating the condition would work.
						 *
						 * We choose to update the retry_time for consistency with what
						 * the server actually does upon receiving the message informing
						 * it that the reservation could not be reconfirmed.
						 */
						nresv_copy->resv->retry_time = sinfo->server_time + 1;
					}
				}
			}
			/* clean up */
			free(nresv->resv->occr_start_arr);
			nresv->resv->occr_start_arr = NULL;
			free_execvnode_seq(tofree);
			tofree = NULL;
			free(occr_execvnodes_arr);
			occr_execvnodes_arr = NULL;

			/* Clean up simulated server info */
			free_server(nsinfo, 1);
		}
		/* Something went wrong with reservation confirmation, retry later */
		if (pbsrc == RESV_CONFIRM_RETRY)
			return -1;
	}

	return count;
}

/**
 * @brief
 * 		mark the timed event associated to a resource reservation at a given time as
 * 		disabled.
 *
 * @param[in]	events	-	the event which to be disabled in the calendar.
 * @param[in]	resv	-	the resource reservation being disabled
 *
 * @return	int
 * @retval	1	: on success
 * @retval	0	: on failure
 */
static int
disable_reservation_occurrence(timed_event *events,
	resource_resv *resv)
{
	timed_event *te;

	te = find_timed_event(events, resv->name, TIMED_RUN_EVENT, resv->start);
	if (te != NULL)
		set_timed_event_disabled(te, 1);
	else
		return 0;

	te = find_timed_event(events, resv->name, TIMED_END_EVENT, resv->end);
	if (te != NULL)
		set_timed_event_disabled(te, 1);
	else
		return 0;

	return 1;
}

/**
 * @brief
 * 		determines if a resource reservation can be satisfied
 *
 * @param[in]	policy	-	policy info
 * @param[in]	pbs_sd	-	connection to server
 * @param[in]	unconf_resv	-	the reservation to confirm
 * @param[in]	nsinfo	-	the simulated server info universe
 *
 * @return	int
 * @retval	RESV_CONFIRM_SUCCESS
 * @retval	RESV_CONFIRM_FAIL
 *
 * @note
 * 		This function modifies the resource reservation by adding the number of
 * 		occurrences and the sequence of occurrence times, which are then used when
 * 		checking for new and degraded reservations.
 */
int
confirm_reservation(status *policy, int pbs_sd, resource_resv *unconf_resv, server_info *nsinfo)
{
	time_t sim_time;          /* time in simulation */
	unsigned int simrc = TIMED_NOEVENT;/* ret code from simulate_events() */
	schd_error *err = NULL;
	int pbsrc = 0;    /* return code from pbs_confirmresv() */
	enum resv_conf rconf = RESV_CONFIRM_SUCCESS; /* assume reconf success */
	char logmsg[MAX_LOG_SIZE];
	char logmsg2[MAX_LOG_SIZE];
	char *errmsg;
	char *msgbuf;

	nspec **ns = NULL;
	resource_resv *nresv = unconf_resv;
	resource_resv **tmp_resresv = NULL;
	resource_resv *nresv_copy = NULL;

	resource_resv *nresv_parent = nresv; /* the "original" / parent reservation */

	int confirmd_occr = 0;   /* the number of confirmed occurrence(s) */
	int j, cur_count;

	int tot_vnodes;   /* total number of vnodes associated to the reservation */
	int vnodes_down = 0;   /* the number of vnodes that are down */
	char names_of_down_vnodes[MAXVNODELIST] = "";  /* the list of down vnodes */

	/* resv_start_time is used both for calculating the time of an ASAP
	 * reservation and to keep track of the start time of the first occurrence
	 * of a standing reservation.
	 */
	time_t resv_start_time = 0;       /* estimated start time for resv */
	time_t *occr_start_arr = NULL;   /* an array of occurrence start times */

	char *execvnodes = NULL;
	char *short_xc = NULL;
	char *tmp = NULL;
	char *vnode_seq_tmp;
	time_t next;

	char *rrule = nresv->resv->rrule; /* NULL for advance reservation */
	time_t dtstart = nresv->resv->req_start;
	char *tz = nresv->resv->timezone;
	int occr_count = nresv->resv->count;
	int ridx = nresv->resv->resv_idx - 1;

	logmsg[0] = logmsg2[0] = '\0';

	err = new_schd_error();
	if (err == NULL)
		return RESV_CONFIRM_FAIL;

	/* If the number of occurrences is not set, this is a first time confirmation
	 * otherwise it is a reconfirmation request
	 */
	if (occr_count == 0)
		occr_count = get_num_occurrences(rrule, dtstart, tz);
	else {
		/* If the number of occurrences (occr_count) was already set, then we are
		 * dealing with the reconfirmation of a reservation. We need to adjust the
		 * number of occurrences to account only for the remaining occurrences and
		 * not the original number at the time the reservation was first submitted
		 */
		if (nresv->resv->resv_state != RESV_BEING_ALTERED)
			occr_count -= ridx;
		else
			occr_count = 1;
	}

	if ((occr_start_arr = (time_t *) calloc(sizeof(time_t), occr_count))
		== NULL) {
		log_err(errno, "confirm_reservation", MEM_ERR_MSG);
		return RESV_CONFIRM_FAIL;
	}


	/* Each reservation attempts to confirm a set of nodes on which to run for
	 * a given start and end time. When handling an advance reservation,
	 * the current reservation is considered. For a standing reservation,
	 * each occurrence is processed by duplicating the parent reservation
	 * and attempts to confirm it.
	 *
	 * All the scratch work attempting to confirm the reservation takes place
	 * in a deep copy of the server info,and is done by simulating events just
	 * as if the server were processing them.
	 *
	 * At the end of the simulation, this cloned server info is completely
	 * wiped and a fresh version is created from the recorded 'sinfo' state.
	 *
	 * It's critical that when handling a standing reservation, each occurrence
	 * be added to the server info such that the duplicated server info has up to
	 * date information.
	 */
	for (j = 0, cur_count = 0; j < occr_count && rconf == RESV_CONFIRM_SUCCESS;
		j++, cur_count = j) {
		/* Get the start time of the next occurrence.
		 * See call to same function in query_reservations for a more in-depth
		 * description.
		 */
		next = get_occurrence(rrule, dtstart, tz, j+1);
		/* keep track of each occurrence's start time */
		occr_start_arr[j] = next;

		/* Processing occurrences of a standing reservation requires duplicating
		 * the "parent" reservation as template for each occurrence, modifying its
		 * start time and duration and running a simulation for that occurrence
		 *
		 * This duplication is only done for subsequent occurrences, not for the
		 * parent reservation.
		 */
		if (j > 0) {
			/* If the reservation is Degraded, then it has already been added to the
			 * real universe, so instead of duplicating the parent reservation, it
			 * is retrieved from the duplicated real server universe
			 */
			if (nresv->resv->resv_substate == RESV_DEGRADED) {
				nresv_copy = find_resource_resv_by_time(nsinfo->all_resresv,
					nresv->name, next);
				if (nresv_copy == NULL) {
					schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv->name,
						"Error determining if reservation can be confirmed: "
						"Could not find reservation by time.");
					rconf = RESV_CONFIRM_FAIL;
					break;
				}
				nresv = nresv_copy;
			}
			else {
				nresv_copy = dup_resource_resv(nresv, nsinfo, NULL);

				if (nresv_copy == NULL) {
					rconf = RESV_CONFIRM_FAIL;
					break;
				}
				nresv = nresv_copy;

				/* add it to the simulated universe of reservations.
				 * Also add it to the reservation list (resvs) to be garbage collected
				 */
				tmp_resresv = add_resresv_to_array(nsinfo->resvs, nresv);
				if (tmp_resresv == NULL) {
					free_resource_resv(nresv);
					rconf = RESV_CONFIRM_FAIL;
					break;
				}
				nsinfo->resvs = tmp_resresv;

				tmp_resresv = add_resresv_to_array(nsinfo->all_resresv, nresv);
				if (tmp_resresv == NULL) {
					free_resource_resv(nresv);
					rconf = RESV_CONFIRM_FAIL;
					break;
				}
				nsinfo->all_resresv = tmp_resresv;
				nsinfo->num_resvs++;
			}
			/* Concatenate the execvnode to a Token separator */
			tmp = (char *) concat_str(execvnodes, TOKEN_SEPARATOR, NULL, 1);
			if (tmp == NULL) {
				schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv->name,
					"Error determining if reservation can be confirmed: "
					"String concatenation failed.");
				free_resource_resv(nresv);
				rconf = RESV_CONFIRM_FAIL;
				break;
			}
			execvnodes = tmp;
		}

		/* If reservation is degraded, then verify that some node(s) associated to
		 * the reservation are down before attempting to reconfirm it. If some
		 * are, then resources allocated to this reservation are released and the
		 * reconfirmation proceeds.
		 */
		if (nresv->resv->resv_substate == RESV_DEGRADED) {
			/* determine the number of vnodes associated to the reservation that are
			 * unavailable. If none, then this reservation or occurrence does not
			 * require reconfirmation.
			 */
			vnodes_down = check_vnodes_down(nresv->ninfo_arr, &tot_vnodes,
				names_of_down_vnodes);
			if (vnodes_down == -1) {
				rconf = RESV_CONFIRM_FAIL;
				break;
			}
			else if (vnodes_down > 0)
				release_nodes(nresv);
			else if (vnodes_down == 0) {
				/* this occurrence doesn't require reconfirmation so skip it by
				 * incrementing the number of occurrences confirmed and appending
				 * this occurrence's execvnodes to the sequence of execvnodes
				 */
				confirmd_occr++;
				tmp = create_execvnode(nresv->nspec_arr);
				if (j == 0)
					execvnodes = (char *) string_dup(tmp);
				else  { /* subsequent occurrences */
					vnode_seq_tmp = (char *) concat_str(execvnodes, tmp, NULL, 1);
					if (vnode_seq_tmp == NULL) {
						schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv->name,
							"Error determining if reservation can be confirmed: "
							"String concatenation failed.");
						rconf = RESV_CONFIRM_FAIL;
						break;
					}
					execvnodes = vnode_seq_tmp;

					vnode_seq_tmp = (char *) concat_str(execvnodes, TOKEN_SEPARATOR,
						NULL, 1);
					if (vnode_seq_tmp == NULL) {
						schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv->name,
							"Error determining if reservation can be confirmed: "
							"String concatenation failed.");
						rconf = RESV_CONFIRM_FAIL;
						break;
					}
					execvnodes = vnode_seq_tmp;

				}
				continue;
			}
			if (disable_reservation_occurrence(nsinfo->calendar->events, nresv)
				!= 1) {
				schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv->name,
					"Error determining if reservation can be confirmed: "
					"Could not mark occurrence disabled.");
				rconf = RESV_CONFIRM_FAIL;
				break;
			}

			/* unconfirm the reservation to let the process of confirmation go on */
			nresv->resv->resv_state = RESV_UNCONFIRMED;
		}
		if (nresv->resv->req_start ==PBS_RESV_FUTURE_SCH) { /* ASAP Resv */
			resv_start_time = calc_run_time(nresv->name, nsinfo, NO_FLAGS);
			/* Update occr_start_arr used to update the real sinfo structure */
			occr_start_arr[j] = resv_start_time;
		}
		else {
			nresv->resv->req_start = next;
			nresv->start = nresv->resv->req_start;
			nresv->end = nresv->start + nresv->resv->req_duration;

			/* "next" is used in simulate_events to determine the time up to which
			 * to simulate the universe
			 */
			simrc = simulate_events(policy, nsinfo, SIM_TIME, (void *) &next, &sim_time);
		}
		if (!(simrc & TIMED_ERROR) && resv_start_time >= 0) {
			clear_schd_error(err);
			if ((ns = is_ok_to_run(nsinfo->policy, nsinfo, NULL, nresv, NO_ALLPART, err)) != NULL) {
				combine_nspec_array(ns);
				tmp = create_execvnode(ns);
				free_nspecs(ns);
				if (tmp == NULL) {
					schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
						nresv->name,
						"Error determining if reservation can be confirmed: "
						"Creation of execvnode failed.");
					rconf = RESV_CONFIRM_FAIL;
					break;
				}

				if (j == 0) { /* first occurrence keeps track of first execvnode */
					execvnodes = (char *) string_dup(tmp);
					/* Update resv_start_time only if not an ASAP reservation to
					 * schedule the reservation on the first occurrence.
					 */
					if (resv_start_time == 0)
						resv_start_time = next;
				}
				else  { /* subsequent occurrences */
					vnode_seq_tmp = (char *) concat_str(execvnodes, tmp, NULL, 1);
					if (!vnode_seq_tmp) {
						schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
							nresv->name,
							"Error determining if reservation can be confirmed: "
							"String concatenation failed.");
						rconf = RESV_CONFIRM_FAIL;
						break;
					}
					execvnodes = vnode_seq_tmp;
				}
				confirmd_occr++;
			}
			/* Something went wrong trying to determine if it's "ok to run", which
			 * may be a problem checking for limits or checking for availability of
			 * resources.
			 */
			else {
				(void) translate_fail_code(err, NULL, logmsg);

				/* If the reservation is degraded, we log a message and continue */
				if (nresv->resv->resv_substate == RESV_DEGRADED) {
					pbs_asprintf(&msgbuf, "Reservation Failed to Reconfirm: %s", logmsg);
					schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
						nresv->name, msgbuf);
					free(msgbuf);
				}
				/* failed to confirm so move on. This will throw flow out of the
				 * loop
				 */
				rconf = RESV_CONFIRM_FAIL;
			}
		} /* end of simulation */
		else {
			schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
				nresv->name,
				"Error determining if reservation can be confirmed: "
				"Simulation failed.");
			rconf = RESV_CONFIRM_FAIL;
		}
	}

	/* Finished simulating occurrences now time to confirm if ok. Currently
	 * the confirmation is an all or nothing process but may come to change. */
	if (confirmd_occr == occr_count) {
		/* We either confirm a standing or advance reservation, the standing
		 * has a special sequence of execvnodes while the advance has a single
		 * execvnode. The sequence of execvnodes is created by concatenating
		 * each execvnode and condensing the concatenated string.
		 */
		if (nresv_parent->resv->is_standing)
			short_xc = condense_execvnode_seq(execvnodes);
		else
			short_xc = string_dup(execvnodes);

		sprintf(logmsg, "Confirming %d Occurrences", occr_count);
		schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv_parent->name,
			logmsg);

		/* Send a reservation confirm message, if anything goes wrong pbsrc
		 * will return an error
		 */
		pbsrc = pbs_confirmresv(pbs_sd, nresv_parent->name, short_xc,
			resv_start_time, PBS_RESV_CONFIRM_SUCCESS);
	}
	else {
		/* This message is sent to inform that we could not confirm the reservation.
		 * If the reservation was degraded then the retry time will be reset.
		 * "null" is used satisfy the API but any string would do because we've
		 * failed to confirm the reservation and no execvnodes were determined
		 */
		pbsrc = pbs_confirmresv(pbs_sd, nresv_parent->name, "null",
			resv_start_time, PBS_RESV_CONFIRM_FAIL);
	}

	/* Error handling first checks for the return code from the server and the
	 * confirmation flag. If either failed, we print the error message, otherwise
	 * we print success
	 */
	if (pbsrc > 0 || rconf == RESV_CONFIRM_FAIL) {
		/* If the scheduler could not find a place for the reservation, use the
		 * translated error code. Otherwise, use the error message from the server.
		 */
		if (rconf == RESV_CONFIRM_FAIL)
			pbs_asprintf(&msgbuf, "PBS Failed to confirm resv: %s", logmsg);
		else {
			errmsg = pbs_geterrmsg(pbs_sd);
			if (errmsg == NULL)
				errmsg = "";
			pbs_asprintf(&msgbuf, "PBS Failed to confirm resv: %s (%d)", errmsg, pbs_errno);
			rconf = RESV_CONFIRM_RETRY;
		}
		schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv_parent->name, msgbuf);
		free(msgbuf);
		if (nresv_parent->resv->resv_substate == RESV_DEGRADED) {
			snprintf(logmsg, MAX_LOG_SIZE,
				"Reservation is in degraded mode, %d out of %d vnodes are unavailable; %s",
				vnodes_down, tot_vnodes, names_of_down_vnodes);
			schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO,
				nresv_parent->name, logmsg);

			/* we failed to confirm the degraded reservation but we still need to
			 * set the remaining occurrences start time to avoid looking at them
			 * in the future. We had set the occr_start_arr times in the main loop
			 * so we only care about the remaining ones
			 */
			for (; cur_count < occr_count; cur_count++) {
				next = get_occurrence(rrule, dtstart, tz, cur_count + 1);
				occr_start_arr[cur_count] = next;
			}
		}
	}
	/* If the (re)confirmation was a success then we update the sequence of
	 * occurrence start times, the number of occurrences, and the sequence of
	 * execvnodes
	 */
	else if (rconf == RESV_CONFIRM_SUCCESS) {
		schdlog(PBSEVENT_RESV, PBS_EVENTCLASS_RESV, LOG_INFO, nresv_parent->name,
			"Reservation Confirmed");

		/* If handling a degraded reservation or while altering a standing reservation
		 * we recreate a new execvnode sequence string, so the old should be cleared.
		 */
		free(nresv_parent->resv->execvnodes_seq);

		/* set or update (for reconfirmation) the sequence of execvnodes */
		nresv_parent->resv->execvnodes_seq = short_xc;
	}
	/* The sequence of occurrence times and the total number of occurrences are
	 * made available to populate the 'real' sinfo in check_new_reservations
	 */
	nresv_parent->resv->occr_start_arr = occr_start_arr;
	nresv_parent->resv->count = occr_count;

	/* clean up */
	free(execvnodes);
	free_schd_error(err);

	/* the return value is initialized to RESV_CONFIRM_SUCCESS */
	return rconf;
}

/**
 * @brief
 * 		Checks the state of all vnodes associated to a reservation and counts the
 * 		number that are unavailable.
 *
 * @param[in]	ninfo_arr	-	the nodes to check
 * @param[out]	tot_vnodes	-	the total number of vnodes associated to the reservation
 * @param[in,out]	names_of_down_vnodes	-	the string of vnodes that are down that are then
 * 												printed into the log. This has to be of maximum length MAXVNODELIST
 *
 * @return	the number of vnodes down. The total number of vnodes is passed back
 * 			by reference.
 * @retval	-1	: on error.
 */
int
check_vnodes_down(node_info **ninfo_arr, int *tot_vnodes, char *names_of_down_vnodes)
{
	int nn_length; /* number of characters allowable in log buffer */
	int vnodes_down; /* number of unavailable vnodes */
	int j;

	if (tot_vnodes == NULL)
		return -1;

	if (ninfo_arr == NULL)
		return -1;

	*tot_vnodes = 0; /* initialize the total number of vnodes */
	vnodes_down = 0;

	for (j = 0; ninfo_arr[j] != NULL; j++) {
		/* Increment total number of vnodes associated to this reservation */
		(*tot_vnodes)++;
		if (ninfo_arr[j]->is_down || ninfo_arr[j]->is_offline
			|| ninfo_arr[j]->is_stale || ninfo_arr[j]->is_unknown) {
			vnodes_down++;
			if (names_of_down_vnodes != NULL) {
				/* -4 accounts for the trailing "...\0" for truncation */
				nn_length = MAXVNODELIST - strlen(names_of_down_vnodes) - 4;
				if (nn_length > 0) {
					strncat(names_of_down_vnodes, ninfo_arr[j]->name, nn_length);
					nn_length = MAXVNODELIST - strlen(names_of_down_vnodes) - 4;
					if (nn_length > 0)
						strncat(names_of_down_vnodes, ",", nn_length);
				}
			}
		}
	}
	if (names_of_down_vnodes != NULL) {
		nn_length = MAXVNODELIST - strlen(names_of_down_vnodes);
		if (nn_length == 4)
			strncat(names_of_down_vnodes, "...", nn_length);
		else /* for non-truncated list of vnodes, remove last comma separator */
			names_of_down_vnodes[strlen(names_of_down_vnodes) - 1] = '\0';
	}

	return vnodes_down;
}

/**
 * @brief
 * 		Release resources allocated to a reservation
 *
 * @param[in]	resresv	-	the reservation
 *
 * @return	void
 */
void
release_nodes(resource_resv *resresv)
{
	free_nodes(resresv->resv->resv_nodes);
	resresv->resv->resv_nodes = NULL;
	free(resresv->ninfo_arr);
	resresv->ninfo_arr = NULL;
	free_nspecs(resresv->nspec_arr);
	resresv->nspec_arr = NULL;
	if (resresv->nodepart_name != NULL) {
		free(resresv->nodepart_name);
		resresv->nodepart_name = NULL;
	}
}

/**
 * @brief
 *		create_resv_nodes - create a node info array by copying the
 *			    nodes and setting available resources to
 *			    only the ones assigned to the reservation
 *
 * @param[in]	nspec_arr -	the nspec array created from the resv_nodes
 * @param[in]	sinfo     -	server reservation belongs too
 *
 * @return	new node universe
 * @retval	NULL	: on error
 */
node_info **
create_resv_nodes(nspec **nspec_arr, server_info *sinfo)
{
	node_info **nodes = NULL;
	schd_resource *res;
	resource_req *req;
	int i;

	if (nspec_arr != NULL) {
		for (i = 0; nspec_arr[i] != NULL; i++)
			;
		nodes = malloc((i+1) * sizeof(node_info *));
		if (nodes != NULL) {
			for (i = 0; nspec_arr[i] != NULL; i++) {
				/* please note - the new duplicated nodes will NOT be part
				 * of sinfo.  This means that you can't find a node in
				 * node -> server -> nodes.  We include the server because
				 * it is expected that every node have a server pointer and
				 * parts of the code gets cranky if it isn't there.
				 */
				nodes[i] = dup_node_info(nspec_arr[i]->ninfo, sinfo, DUP_INDIRECT);
				nodes[i]->svr_node = nspec_arr[i]->ninfo;

				/* reservation nodes in state resv_exclusive can be assigned to jobs
				 * within the reservation
				 */
				if (nodes[i]->is_resv_exclusive)
					remove_node_state(nodes[i], ND_resv_exclusive);

				req = nspec_arr[i]->resreq;
				while (req != NULL) {
					res = find_alloc_resource(nodes[i]->res, req->def);

					if (res != NULL) {
						if (res->indirect_res != NULL)
							res = res->indirect_res;
						res->avail = req->amount;
						memcpy(&(res->type), &(req->type), sizeof(struct resource_type));
						if (res->type.is_consumable)
							res->assigned = 0; /* clear now, set later */
					}
					req = req->next;
				}
			}
			nodes[i] = NULL;
		}
	}
	return nodes;
}

/**
 * @brief - adjust resources on nodes belonging to a reservation that is
 *	    being altered.
 *
 * @param[in] all_resvs - array of all the reservations.
 * @param[in] all_nodes - array of all the nodes.
 *
 * @par - This routine will adjust the assigned resources on nodes that
 *	  are being used by a reservation which is being altered. The
 *	  need to do this is because a reservation if it is running and
 *	  needs to be altered, will have resources assigned on its nodes.
 *	  This may render check_avail_resources to reject the alter request
 *	  Also, for the nodes that are reservation exclusive should also
 *	  be seen as free nodes for this reservation in order to get altered
 *	  successfully.
 */

void
adjust_alter_resv_nodes(resource_resv **all_resvs, node_info **all_nodes)
{
	int i = 0;
	int j = 0;
	node_info **resv_nodes = NULL;
	node_info *ninfo = NULL;

	if (all_resvs == NULL || all_nodes == NULL )
		return;
	for (j = 0; all_resvs[j] != NULL; j++) {
		if (all_resvs[j]->resv->resv_state == RESV_BEING_ALTERED) {
			if (all_resvs[j]->resv->resv_substate == RESV_RUNNING) {
				resv_nodes = all_resvs[j]->ninfo_arr;
				for (i = 0; resv_nodes[i] != NULL; i++) {
					ninfo = find_node_by_rank(all_nodes, resv_nodes[i]->rank);
					update_node_on_end(ninfo, all_resvs[j], NULL);
				}
			}
		}
	}
}

/**
 * 	@brief determine if the scheduler will attempt to confirm a reservation
 *
 * 	@return int
 * 	@retval 1 - will attempt confirmation
 * 	@retval 0 - will not attempt confirmation
 */
int will_confirm(resource_resv *resv, time_t server_time) {
	/* If the reservation is unconfirmed OR is degraded and not running, with a
	 * retry time that is in the past, then the reservation has to be
	 * respectively confirmed and reconfirmed.
	 */
	if (resv->resv->resv_state == RESV_UNCONFIRMED ||
		resv->resv->resv_state == RESV_BEING_ALTERED ||
		((resv->resv->resv_state != RESV_RUNNING &&
		resv->resv->resv_substate == RESV_DEGRADED &&
		resv->resv->retry_time != UNSPECIFIED &&
		resv->resv->retry_time <= server_time)))
		return 1;

	return 0;
}

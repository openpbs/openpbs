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
 * @file    resource_resv.c
 *
 * @brief
 * 	resource_resv.c - This file contains functions related to resource reservations.
 *
 * Functions included are:
 * 	new_resource_resv()
 * 	free_resource_resv_array()
 * 	free_resource_resv()
 * 	dup_resource_resv_array()
 * 	dup_resource_resv()
 * 	find_resource_resv()
 * 	find_resource_resv_by_indrank()
 * 	find_resource_resv_by_time()
 * 	find_resource_resv_func()
 * 	cmp_job_arrays()
 * 	is_resource_resv_valid()
 * 	dup_resource_req_list()
 * 	dup_resource_req()
 * 	new_resource_req()
 * 	create_resource_req()
 * 	find_alloc_resource_req()
 * 	find_alloc_resource_req_by_str()
 * 	find_resource_req_by_str()
 * 	find_resource_req()
 * 	set_resource_req()
 * 	free_resource_req_list()
 * 	free_resource_req()
 * 	update_resresv_on_run()
 * 	update_resresv_on_end()
 * 	resource_resv_filter()
 * 	remove_resresv_from_array()
 * 	add_resresv_to_array()
 * 	copy_resresv_array()
 * 	is_resresv_running()
 * 	new_place()
 * 	free_place()
 * 	dup_place()
 * 	new_chunk()
 * 	dup_chunk_array()
 * 	dup_chunk()
 * 	free_chunk_array()
 * 	free_chunk()
 * 	new_selspec()
 * 	dup_selspec()
 * 	free_selspec()
 * 	compare_res_to_str()
 * 	compare_non_consumable()
 * 	create_select_from_nspec()
 * 	in_runnable_state()
 *
 */

#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <log.h>
#include <libutil.h>
#include "pbs_config.h"
#include "data_types.h"
#include "resource_resv.h"
#include "job_info.h"
#include "resv_info.h"
#include "node_info.h"
#include "misc.h"
#include "node_partition.h"
#include "constant.h"
#include "globals.h"
#include "resource.h"
#include "pbs_internal.h"
#include "check.h"
#include "fifo.h"
#include "range.h"


/**
 * @brief
 *		new_resource_resv() - allocate and initialize a resource_resv struct
 *
 * @return	ptr to newly allocated resource_resv struct
 *
 */
resource_resv *
new_resource_resv()
{
	resource_resv *resresv = NULL;

	if ((resresv = malloc(sizeof(resource_resv))) == NULL) {
		log_err(errno, "new_resource_resv", "Error allocating memory");
		return NULL;
	}


	resresv->name = NULL;
	resresv->user = NULL;
	resresv->group = NULL;
	resresv->project = NULL;
	resresv->nodepart_name = NULL;
	resresv->select = NULL;
	resresv->execselect = NULL;

	resresv->place_spec = NULL;

	resresv->is_invalid = 0;
	resresv->can_not_fit = 0;
	resresv->can_not_run = 0;
	resresv->can_never_run = 0;
	resresv->is_peer_ob = 0;

	resresv->is_prov_needed = 0;
	resresv->is_job = 0;
	resresv->is_shrink_to_fit = 0;
	resresv->is_resv = 0;

	resresv->will_use_multinode = 0;

	resresv->sch_priority = 0;
	resresv->rank = 0;
	resresv->qtime = 0;
	resresv->qrank = 0;

	resresv->ec_index = UNSPECIFIED;

	resresv->start = UNSPECIFIED;
	resresv->end = UNSPECIFIED;
	resresv->duration = UNSPECIFIED;
	resresv->hard_duration = UNSPECIFIED;
	resresv->min_duration = UNSPECIFIED;

	resresv->resreq = NULL;
	resresv->server = NULL;
	resresv->ninfo_arr = NULL;
	resresv->nspec_arr = NULL;

	resresv->job = NULL;
	resresv->resv = NULL;

	resresv->aoename = NULL;
	resresv->eoename = NULL;

#ifdef NAS /* localmod 034 */
	resresv->share_type = J_TYPE_ignore;
#endif /* localmod 034 */

	resresv->node_set_str = NULL;
	resresv->node_set = NULL;
	resresv->resresv_ind = -1;

	return resresv;
}

/**
 * @brief
 *		free_resource_resv_array - free an array of resource resvs
 *
 * @param[in,out]	resresv_arr	-	resource resv to free
 *
 * @return	nothing
 *
 */
void
free_resource_resv_array(resource_resv **resresv_arr)
{
	int i;

	if (resresv_arr == NULL)
		return;

	for (i = 0; resresv_arr[i] != NULL; i++)
		free_resource_resv(resresv_arr[i]);

	free(resresv_arr);
}

/**
 * @brief
 *		free_resource_resv - free a resource resv strcture an all of it's ptrs
 *
 * @param[in]	resresv	-	resource_resv to free
 *
 * @return	nothing
 *
 */
void
free_resource_resv(resource_resv *resresv)
{
	if (resresv == NULL)
		return;

	if (resresv->name != NULL)
		free(resresv->name);

	if (resresv->user != NULL)
		free(resresv->user);

	if (resresv->group != NULL)
		free(resresv->group);

	if (resresv->project != NULL)
		free(resresv->project);

	if (resresv->nodepart_name != NULL)
		free(resresv->nodepart_name);

	if (resresv->select != NULL)
		free_selspec(resresv->select);

	if (resresv->execselect != NULL)
		free_selspec(resresv->execselect);

	if (resresv->place_spec != NULL)
		free_place(resresv->place_spec);

	if (resresv->resreq != NULL)
		free_resource_req_list(resresv->resreq);

	if (resresv->ninfo_arr != NULL)
		free(resresv->ninfo_arr);

	if (resresv->nspec_arr != NULL)
		free_nspecs(resresv->nspec_arr);

	if (resresv->job != NULL)
		free_job_info(resresv->job);

	if (resresv->resv != NULL)
		free_resv_info(resresv->resv);

	if (resresv->aoename != NULL)
		free(resresv->aoename);

	if (resresv->eoename != NULL)
		free(resresv->eoename);

	if (resresv->node_set_str != NULL)
		free_string_array(resresv->node_set_str);

	if (resresv->node_set != NULL)
		free(resresv->node_set);

	free(resresv);
}

/**
 * @brief
 *		dup_resource_resv_array - dup a array of pointers of resource resvs
 *
 * @param[in]	oresresv_arr	-	array of resource_resv do duplicate
 * @param[in]	nsinfo	-	new server ptr for new resresv array
 * @param[in]	nqinfo	-	new queue ptr for new resresv array
 *
 * @return	new resource_resv array
 * @retval	NULL	: on error
 *
 */
resource_resv **
dup_resource_resv_array(resource_resv **oresresv_arr,
	server_info *nsinfo, queue_info *nqinfo)
{
	resource_resv **nresresv_arr;
	int i;

	if (oresresv_arr == NULL || nsinfo == NULL)
		return NULL;

	for (i = 0; oresresv_arr[i] != NULL; i++)
		;

	if ((nresresv_arr = malloc((i + 1) * sizeof(resource_resv *))) == NULL) {
		log_err(errno, "dup_resource_resv_array",  "Error allocating memory");
		return NULL;
	}

	for (i = 0; oresresv_arr[i] != NULL; i++) {
		if ((nresresv_arr[i] =
			dup_resource_resv(oresresv_arr[i], nsinfo, nqinfo)) == NULL) {
			free_resource_resv_array(nresresv_arr);
			return NULL;
		}
	}
	nresresv_arr[i] = NULL;

	return nresresv_arr;
}


/**
 * @brief
 *		dup_resource_resv - duplicate a resource resv structure
 *
 * @param[in]	oresresv	-	res resv to duplicate
 * @param[in]	nsinfo	-	new server info for resource_resv
 * @param[in]	nqinfo	-	new queue info for resource_resv if job (NULL if resv)
 *
 * @return	newly duplicated resource resv
 * @retval	NULL	: on error
 *
 */
resource_resv *
dup_resource_resv(resource_resv *oresresv,
	server_info *nsinfo, queue_info *nqinfo)
{
	resource_resv *nresresv;
	static schd_error *err;

	if (oresresv == NULL || nsinfo == NULL)
		return NULL;
	
	if (err == NULL) {
		err = new_schd_error();
		if (err == NULL)
			return NULL;
	} else
		clear_schd_error(err);

	if (!is_resource_resv_valid(oresresv, err)) {
		schdlogerr(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SCHED, LOG_DEBUG, oresresv->name, "Can't dup resresv", err);
		return NULL;
	}

	nresresv = new_resource_resv();

	if (nresresv == NULL)
		return NULL;

	nresresv->server = nsinfo;

	nresresv->name = string_dup(oresresv->name);
	nresresv->user = string_dup(oresresv->user);
	nresresv->group = string_dup(oresresv->group);
	nresresv->project = string_dup(oresresv->project);

	nresresv->nodepart_name = string_dup(oresresv->nodepart_name);
	nresresv->select = dup_selspec(oresresv->select);
	nresresv->execselect = dup_selspec(oresresv->execselect);

	nresresv->is_invalid = oresresv->is_invalid;
	nresresv->can_not_fit = oresresv->can_not_fit;
	nresresv->can_not_run = oresresv->can_not_run;
	nresresv->can_never_run = oresresv->can_never_run;
	nresresv->is_peer_ob = oresresv->is_peer_ob;
	nresresv->is_prov_needed = oresresv->is_prov_needed;
	nresresv->is_shrink_to_fit = oresresv->is_shrink_to_fit;
	nresresv->will_use_multinode = oresresv->will_use_multinode;

	nresresv->ec_index = oresresv->ec_index;

	nresresv->sch_priority = oresresv->sch_priority;
	nresresv->rank = oresresv->rank;
	nresresv->qtime = oresresv->qtime;
	nresresv->qrank = oresresv->qrank;

	nresresv->start = oresresv->start;
	nresresv->end = oresresv->end;
	nresresv->duration = oresresv->duration;
	nresresv->hard_duration = oresresv->hard_duration;
	nresresv->min_duration = oresresv->min_duration;

	nresresv->resreq = dup_resource_req_list(oresresv->resreq);

	nresresv->place_spec = dup_place(oresresv->place_spec);

	nresresv->aoename = string_dup(oresresv->aoename);
	nresresv->eoename = string_dup(oresresv->eoename);

	nresresv->node_set_str = dup_string_array(oresresv->node_set_str);

	nresresv->resresv_ind = oresresv->resresv_ind;
#ifdef NAS /* localmod 049 */
	nresresv->node_set = copy_node_ptr_array(oresresv->node_set, nsinfo->nodes, nsinfo);
#else
	nresresv->node_set = copy_node_ptr_array(oresresv->node_set, nsinfo->nodes);
#endif /* localmod 049 */

	if (oresresv->is_job) {
		nresresv->is_job = 1;
		nresresv->job = dup_job_info(oresresv->job, nqinfo, nsinfo);
		if (nresresv->job != NULL) {
			if (nresresv->job->resv !=NULL) {
#ifdef NAS /* localmod 049 */
				nresresv->ninfo_arr = copy_node_ptr_array(oresresv->ninfo_arr,
					nresresv->job->resv->resv->resv_nodes, NULL);
				nresresv->nspec_arr = dup_nspecs(oresresv->nspec_arr,
					nresresv->job->resv->ninfo_arr, NULL);
#else
				nresresv->ninfo_arr = copy_node_ptr_array(oresresv->ninfo_arr,
					nresresv->job->resv->resv->resv_nodes);
				nresresv->nspec_arr = dup_nspecs(oresresv->nspec_arr,
					nresresv->job->resv->ninfo_arr);
#endif /* localmod 049 */
			}
			else {
#ifdef NAS /* localmod 049 */
				nresresv->ninfo_arr = copy_node_ptr_array(oresresv->ninfo_arr,
					nsinfo->nodes, nsinfo);
				nresresv->nspec_arr = dup_nspecs(oresresv->nspec_arr,
					nsinfo->nodes, nsinfo);
#else
				nresresv->ninfo_arr = copy_node_ptr_array(oresresv->ninfo_arr,
					nsinfo->nodes);
				nresresv->nspec_arr = dup_nspecs(oresresv->nspec_arr,
					nsinfo->nodes);
#endif /* localmod 049 */
			}
		}
	}
	else if (oresresv->is_resv) {
		nresresv->is_resv = 1;
		nresresv->resv = dup_resv_info(oresresv->resv, nsinfo);

#ifdef NAS /* localmod 049 */
		nresresv->ninfo_arr = copy_node_ptr_array(oresresv->ninfo_arr,
			nsinfo->nodes, nsinfo);
		nresresv->nspec_arr = dup_nspecs(oresresv->nspec_arr,
			nsinfo->nodes, nsinfo);
#else
		nresresv->ninfo_arr = copy_node_ptr_array(oresresv->ninfo_arr,
			nsinfo->nodes);
		nresresv->nspec_arr = dup_nspecs(oresresv->nspec_arr,
			nsinfo->nodes);
#endif /* localmod 049 */
	}
	else  { /* error */
		free_resource_resv(nresresv);
		return NULL;
	}
#ifdef NAS /* localmod 034 */
	nresresv->share_type = oresresv->share_type;
#endif /* localmod 034 */

	if (!is_resource_resv_valid(nresresv, err)) {
		schdlogerr(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SCHED, LOG_DEBUG, oresresv->name, "Failed to dup resresv", err);
		free_resource_resv(nresresv);
		return NULL;
	}

	return nresresv;
}

/**
 * @brief
 * 		find a resource_resv by name
 *
 * @param[in]	resresv_arr	-	array of resource_resvs to search
 * @param[in]	name        -	name of resource_resv to find
 *
 * @return	resource_resv *
 * @retval	resource_resv if found
 * @retval	NULL	: if not found or on error
 *
 */
resource_resv *
find_resource_resv(resource_resv **resresv_arr, char *name)
{
	int i;
	if (resresv_arr == NULL || name == NULL)
		return NULL;

	for (i = 0; resresv_arr[i] != NULL && strcmp(resresv_arr[i]->name, name);i++)
		;

	return resresv_arr[i];
}

/**
 * @brief
 * 		find a resource_resv by index in all_resresv array or by unique numeric rank
 *
 * @param[in]	resresv_arr	-	array of resource_resvs to search
 * @param[in]	rank        -	rank of resource_resv to find
 * @param[in]	index	    -	index of resource_resv to find
 *
 * @return	resource_resv *
 * @retval resource_resv	: if found
 * @retval NULL	: if not found or on error
 *
 */
resource_resv *
find_resource_resv_by_indrank(resource_resv **resresv_arr, int rank, int index)
{
	int i;
	if (resresv_arr == NULL)
		return NULL;

	if (index != -1 && resresv_arr[0] != NULL && resresv_arr[0]->server != NULL &&
	    resresv_arr[0]->server->all_resresv != NULL)
		return resresv_arr[0]->server->all_resresv[index];

	for (i = 0; resresv_arr[i] != NULL && resresv_arr[i]->rank != rank; i++)
		;

	return resresv_arr[i];
}

/**
 * @brief
 * 		find a resource_resv by name and start time
 *
 * @param[in]	resresv_arr -	array of resource_resvs to search
 * @param[in]	name        -	name of resource_resv to find
 * @param[in]	start_time  -	the start time of the resource_resv
 *
 * @return	resource_resv *
 * @retval	resource_resv	: if found
 * @retval	NULL	: if not found or on error
 *
 */
resource_resv *
find_resource_resv_by_time(resource_resv **resresv_arr, char *name, time_t start_time)
{
	int i;
	if (resresv_arr == NULL || name == NULL)
		return NULL;

	for (i = 0; resresv_arr[i] != NULL;i++) {
		if ((strcmp(resresv_arr[i]->name, name) == 0) && (resresv_arr[i]->start == start_time))
			break;
	}

	return resresv_arr[i];
}

/**
 * @brief
 * 		find a resource resv by calling a caller provided comparison function
 *
 * @param[in]	resresv_arr - array of resource_resvs to search
 * @param[in]	fn int cmp_func(resource_resv *rl, void *cmp_arg)
 * @param[in]	cmp_arg - opaque argument for cmp_func()
 *
 * @return found resource_resv or NULL
 *
 */
resource_resv *
find_resource_resv_func(resource_resv **resresv_arr,
	int (*cmp_func)(resource_resv*, void*), void *cmp_arg)
{
	int i;
	if (resresv_arr == NULL || cmp_func == NULL || cmp_arg == NULL)
		return NULL;

	for (i = 0; resresv_arr[i] != NULL &&
		cmp_func(resresv_arr[i], cmp_arg) == 0; i++)
		;
	return resresv_arr[i];
}

/**
 * @brief
 * 		function used by find_resource_resv_func to see if two subjobs are
 *	 	 part of the same job array (e.g., 1234[])
 *
 * @param[in]	resresv	-	resource_resv structure
 * @param[in]	arg	-	argument resource reservation.
 */
int
cmp_job_arrays(resource_resv *resresv, void *arg)
{
	resource_resv *argresv;

	if (resresv == NULL || arg == NULL)
		return 0;

	argresv = (resource_resv *) arg;

	if (resresv->job == NULL || argresv->job ==NULL)
		return 0;

	/* if one is not a subjob = no match */
	if (resresv->job->array_id == NULL || argresv->job->array_id== NULL)
		return 0;

	if (strcmp(resresv->job->array_id, argresv->job->array_id)== 0)
		return 1;

	return 0;
}

/**
 * @brief
 *		is_resource_resv_valid - do simple validity checks for a resource resv
 *
 *
 *	@param[in] resresv - the resource_resv to do check
 *	@param[out] err - error struct to return why resource_resv is invalid
 *
 *	@returns int
 *	@retva1 1 if valid
 *	@retval 0 if invalid (err returns reason why)
 */
int
is_resource_resv_valid(resource_resv *resresv, schd_error *err)
{
	if (resresv == NULL)
		return 0;

	if (resresv->server == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "No server pointer");
		return 0;
	}

	if (resresv->is_job && resresv->job == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "Job has no job sub-structure");
		return 0;
	}

	if (resresv->is_resv && resresv->resv == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "Reservation has no resv sub-structure");
		return 0;
	}

	if (resresv->name == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "No Name");
		return 0;
	}

	if (resresv->user == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "No User");
		return 0;
	}

	if (resresv->group == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "No Group");
		return 0;
	}

	if (resresv->select == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "No Select");
		return 0;
	}

	if (resresv->place_spec == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "No Place");
		return 0;
	}

	if (!resresv->is_job && !resresv->is_resv) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "Is neither job nor resv");
		return 0;
	}

	if (is_resresv_running(resresv)) {
		if (resresv->nspec_arr == NULL) {
			set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
			set_schd_error_arg(err, SPECMSG, "Is running w/o exec_vnode1");
			return 0;
		}

		if (resresv->ninfo_arr == NULL) {
			set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
			set_schd_error_arg(err, SPECMSG, "Is running w/o exec_vnode2");
			return 0;
	}
	}

	if (resresv->ninfo_arr != NULL && resresv->nspec_arr == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "exec_vnode mismatch 1");
		return 0;
	}

	if (resresv->nspec_arr != NULL && resresv->ninfo_arr == NULL) {
		set_schd_error_codes(err, NEVER_RUN, ERR_SPECIAL);
		set_schd_error_arg(err, SPECMSG, "exec_vnode mismatch 2");
		return 0;
	}

	return 1;
}


/**
 * @brief
 *		dup_resource_req_list - duplicate a resource_req list
 *
 * @param[in]	oreq	-	resource_req list to duplicate
 *
 * @return	duplicated resource_req list
 *
 */
resource_req *
dup_resource_req_list(resource_req *oreq)
{
	resource_req *req;
	resource_req *nreq;
	resource_req *head;
	resource_req *prev;

	head = NULL;
	prev = NULL;
	req = oreq;

	while (req != NULL) {
		if ((nreq = dup_resource_req(req)) != NULL) {
			if (head == NULL)
				head = nreq;
			else
				prev->next = nreq;
			prev = nreq;
		}
		req = req->next;
	}

	return head;
}

/**
 * @brief
 *		dup_selective_resource_req_list - duplicate a resource_req list
 *
 * @param[in]	oreq	-	resource_req list to duplicate
 * @paral[in]	deflist		only duplicate resources in this list - if NULL, dup all
 *
 * @return	duplicated resource_req list
 *
 */
resource_req *
dup_selective_resource_req_list(resource_req *oreq, resdef **deflist)
{
	resource_req *req;
	resource_req *nreq;
	resource_req *head;
	resource_req *prev;

	head = NULL;
	prev = NULL;

	for (req = oreq; req != NULL; req = req->next) {
		if (deflist == NULL || resdef_exists_in_array(deflist, req->def)) {
			if ((nreq = dup_resource_req(req)) != NULL) {
				if (head == NULL)
					head = nreq;
				else
					prev->next = nreq;
				prev = nreq;
			}
		}
	}

	return head;
}

/**
 * @brief
 *		dup_resource_req - duplicate a resource_req struct
 *
 * @param[in]	oreq	-	the resource_req to duplicate
 *
 * @return	duplicated resource req
 *
 */
resource_req *
dup_resource_req(resource_req *oreq)
{
	resource_req *nreq;
	if (oreq == NULL)
		return NULL;

	if ((nreq = new_resource_req()) == NULL)
		return NULL;


	nreq->def = oreq->def;
	if(nreq->def)
		nreq->name = nreq->def->name;

	memcpy(&(nreq->type), &(oreq->type), sizeof(struct resource_type));
	nreq->res_str = string_dup(oreq->res_str);
	nreq->amount = oreq->amount;


	return nreq;
}

/**
 * @brief
 *		new_resource_req - allocate and initalize new resource_req
 *
 * @return	the new resource_req
 *
 */

resource_req *
new_resource_req()
{
	resource_req *resreq;

	if ((resreq = (resource_req *) calloc(1, sizeof(resource_req))) == NULL) {
		log_err(errno, "new_resource_req", MEM_ERR_MSG);
		return NULL;
	}

	/* member type zero'd by calloc() */

	resreq->name = NULL;
	resreq->res_str = NULL;
	resreq->amount = 0;
	resreq->def = NULL;
	resreq->next = NULL;

	return resreq;
}

/**
 * @brief
 * 		Create new resource_req with given data
 *
 * @param[in]	name	-	name of resource
 * @param[in]	value	-	value of resource
 *
 * @return	newly created resource_req
 * @retval	NULL	: Fail
 */
resource_req *
create_resource_req(char *name, char *value)
{
	resource_req *resreq = NULL;
	resdef *rdef;

	if (name == NULL)
		return NULL;


	rdef = find_resdef(allres, name);

	if (rdef != NULL) {
		if ((resreq = new_resource_req()) != NULL) {
			resreq->def = rdef;
			resreq->name = rdef->name;
			resreq->type = rdef->type;

			if (value != NULL) {
				if (set_resource_req(resreq, value) != 1) {
					schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SCHED, LOG_DEBUG, name,
						"Bad requested resource data");
					return NULL;
				}
			}
		}
	} else {
		schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SCHED, LOG_DEBUG, name, "Resource definition does not exist, resource may be invalid");
		return NULL;
	}

	return resreq;
}

/**
 * @brief
 *		find resource_req by resource definition or allocate and
 *		initialize a new resource_req also adds new one to the list
 *
 * @param[in]	reqlist	-	list to search
 * @param[in]	name	-	resource_req to find
 *
 * @return	resource_req *
 * @retval	found or newly allocated resource_req
 *
 */
resource_req *
find_alloc_resource_req(resource_req *reqlist, resdef *def)
{
	resource_req *req;		/* used to find or create resource_req */
	resource_req *prev = NULL;	/* previous resource_req in list */

	if (def == NULL)
		return NULL;

	for (req = reqlist; req != NULL && req->def != def; req = req->next) {
		prev = req;
	}

	if (req == NULL) {
		if ((req = new_resource_req()) == NULL)
			return NULL;

		req->def = def;
		req->type = req->def->type;
		req->name = def->name;
		if (prev != NULL)
			prev->next = req;
	}

	return req;
}

/**
 * @brief
 * 		find resource_req by name or allocate and initialize a new
 *		resource_req also adds new one to the list
 *
 * @param[in]	reqlist	-	list to search
 * @param[in]	name	-	resource_req to find
 *
 * @return	resource_req *
 * @retval	found or newly allocated resource_req
 *
 */
resource_req *
find_alloc_resource_req_by_str(resource_req *reqlist, char *name)
{
	resource_req *req;		/* used to find or create resource_req */
	resource_req *prev = NULL;	/* previous resource_req in list */

	if (name == NULL)
		return NULL;

	for (req = reqlist; req != NULL && strcmp(req->name, name); req = req->next) {
		prev = req;
	}

	if (req == NULL) {
		if ((req = create_resource_req(name, NULL)) == NULL)
			return NULL;

		if (prev != NULL)
			prev->next = req;
	}

	return req;
}

/**
 * @brief
 * 		find a resource_req from a resource_req list by string name
 *
 * @param[in]	reqlist	-	the resource_req list
 * @param[in]	name	-	resource name to look for
 *
 * @return	resource_req *
 * @retval	found resource request
 * @retval NULL	: if not found
 *
 */
resource_req *
find_resource_req_by_str(resource_req *reqlist, const char *name)
{
	resource_req *resreq;

	resreq = reqlist;

	while (resreq != NULL && strcmp(resreq->name, name))
		resreq = resreq->next;

	return resreq;
}

/**
 * @brief
 * 		find resource_req by resource definition
 *
 * @param	reqlist	-	req list to search
 * @param	def	-	resource definition to search for
 *
 * @return	found resource_req
 * @retval	NULL	: if not found
 */
resource_req *
find_resource_req(resource_req *reqlist, resdef *def)
{
	resource_req *resreq;

	resreq = reqlist;

	while (resreq != NULL && resreq->def != def)
		resreq = resreq->next;

	return resreq;
}

/**
 * @brief
 *		set_resource_req - set the value and type of a resource req
 *
 * @param[out]	req	-	the resource_req to set
 * @param[in]	val -	the string value
 *
 * @return	int
 * @retval	1 for Success
 * @retval	0 for Error
 */
int
set_resource_req(resource_req *req, char *val)
{
	resdef *rdef;

	/* if val is a string, req -> amount will be set to SCHD_INFINITY */
	req->amount = res_to_num(val, &(req->type));
	req->res_str = string_dup(val);

	if (req->def != NULL)
		rdef = req->def;
	else {
		rdef = find_resdef(allres, req->name);
		req->def = rdef;
	}
	if (rdef != NULL)
		req->type = rdef->type;

	if (req->amount == SCHD_INFINITY) {
		/* Verify that this is actually a non-numeric resource */
		if (!req->def->type.is_string)
			return 0;
	}

	return 1;
}


/**
 * @brief
 *		free_resource_req_list - frees memory used by a resource_req list
 *
 * @param[in]	list	-	resource_req list
 *
 * @return	nothing
 */
void
free_resource_req_list(resource_req *list)
{
	resource_req *resreq, *tmp;

	resreq = list;
	while (resreq != NULL) {
		tmp = resreq;
		resreq = resreq->next;
		free_resource_req(tmp);
	}
}

/**
 * @brief
 *		free_resource_req - free memory used by a resource_req structure
 *
 * @param[in,out]	req	-	resource_req to free
 *
 * @return	nothing
 *
 */
void
free_resource_req(resource_req *req)
{
	if (req == NULL)
		return;

	if (req->res_str != NULL)
		free(req->res_str);

	free(req);
}

/**
 * @brief compare two resource_req structures
 * @return equal or not
 * @retval 1 two structures are equal
 * @retval 0 two strictures are not equal
 */
int
compare_resource_req(resource_req *req1, resource_req *req2) {

	if (req1 == NULL && req2 == NULL)
		return 1;
	else if (req1 == NULL || req1 == NULL)
		return 0;

	if (req1->type.is_consumable || req1->type.is_boolean)
		return (req1->amount == req2->amount);

	if (req1->type.is_string)
		if (strcmp(req1->res_str, req2->res_str) == 0)
			return 1;

	return 0;

}

/**
 * @brief compare two resource_req lists possibly excluding certain resources
 * @param[in] req1 - list1
 * @param[in] req2 - list2
 * @param[in] comparr - list of resources to compare or NULL for all resources
 * @return int
 * @retval 1 two lists are equal
 * @retval 0 two lists are not equal
 */
int
compare_resource_req_list(resource_req *req1, resource_req *req2, resdef **comparr) {
	resource_req *cur_req1;
	resource_req *cur_req2;
	resource_req *cur;
	int ret1 = 1;
	int ret2 = 1;


	if (req1 == NULL && req2 == NULL)
		return 1;

	if (req1 == NULL || req2 == NULL)
		return 0;

	for (cur_req1 = req1; ret1 && cur_req1 != NULL; cur_req1 = cur_req1->next) {
		if (comparr == NULL || resdef_exists_in_array(comparr, cur_req1->def)) {
			cur = find_resource_req(req2, cur_req1->def);
			if (cur == NULL)
				ret1 = 0;
			else
				ret1 = compare_resource_req(cur_req1, cur);
		}
	}

	for (cur_req2 = req2; ret2 && cur_req2 != NULL; cur_req2 = cur_req2->next) {
		if (comparr == NULL || resdef_exists_in_array(comparr, cur_req2->def)) {
			cur = find_resource_req(req1, cur_req2->def);
			if (cur == NULL)
				ret2 = 0;
			else
				ret2 = compare_resource_req(cur_req2, cur);
		}
	}

	/* Either we found a not-match or one list is larger than the other*/
	if (!ret1 || !ret2)
		return 0;

	return 1;
}

/**
 * @brief
 * 		update information kept in a resource_resv when one is started
 *
 * @param[in]	resresv	-	the resource resv to update
 * @param[in]	nspec_arr	-	the nodes the job ran in
 *
 * @return	void
 */
void
update_resresv_on_run(resource_resv *resresv, nspec **nspec_arr)
{
	int ns_size;
	queue_info *resv_queue;
	int ret;
	int i;

	if (resresv == NULL || nspec_arr == NULL)
		return;

	if (resresv->is_job) {
		if (resresv->job->is_suspended) {
			for (ns_size = 0; nspec_arr[ns_size] != NULL; ns_size++)
				nspec_arr[ns_size]->ninfo->num_susp_jobs--;
		}

		set_job_state("R", resresv->job);
		resresv->job->is_susp_sched = 0;
		resresv->job->stime = resresv->server->server_time;
		resresv->start = resresv->server->server_time;
		resresv->end = resresv->start + calc_time_left(resresv, 0);
		resresv->job->accrue_type = JOB_RUNNING;

		if (resresv->aoename != NULL) {
			for (i = 0; nspec_arr[i] != NULL; i++) {
				if (nspec_arr[i]->go_provision) {
					resresv->job->is_provisioning = 1;
					break;
				}
			}
		}
		if (resresv->execselect == NULL) {
			char *selectspec;
			selectspec = create_select_from_nspec(nspec_arr);
			if (selectspec != NULL) {
				resresv->execselect = parse_selspec(selectspec);
				free(selectspec);
			}
		}
	}
	else if (resresv->is_resv && resresv->resv !=NULL) {
		resresv->resv->resv_state = RESV_RUNNING;

		resv_queue = find_queue_info(resresv->server->queues,
			resresv->resv->queuename);
		if (resv_queue != NULL) {
			/* reservation queues are stopped before the reservation is started */
			resv_queue->is_started = 1;
			/* because the reservation queue was previously stopped, we need to
			 * reevaluate resv_queue -> is_ok_to_run
			 */
			ret = is_ok_to_run_queue(resresv->server->policy, resv_queue);
			if (ret == SUCCESS)
				resv_queue->is_ok_to_run = 1;
			else
				resv_queue->is_ok_to_run = 0;
		}
	}
	if (resresv->ninfo_arr == NULL)
		resresv->ninfo_arr = create_node_array_from_nspec(nspec_arr);
}

/**
 * @brief
 *		update_resresv_on_end - update a resource_resv structure when
 *				      it ends
 *
 * @param[out]	resresv	-	the resresv to update
 * @param[in]	job_state	-	the new state if resresv is a job
 *
 * @return	nothing
 *
 */
void
update_resresv_on_end(resource_resv *resresv, char *job_state)
{
	queue_info *resv_queue;
	resource_resv *next_occr = NULL;
	time_t next_occr_time;
	char logbuf[MAX_LOG_SIZE];
	int ret;
	int i;

	if (resresv == NULL)
		return;

	/* now that it isn't running, it might be runnable again */
	resresv->can_not_run = 0;

	/* unless of course it's a job and its queue is in an ineligible state */
	if (resresv->is_job && resresv->job != NULL &&
		!resresv->job->queue->is_ok_to_run)
		resresv->can_not_run = 1;

	/* no longer running... clear start and end times */
	resresv->start = UNSPECIFIED;
	resresv->end = UNSPECIFIED;

	if (resresv->is_job && resresv->job != NULL) {
		set_job_state(job_state, resresv->job);
		if (resresv->job->is_suspended) {
#ifndef NAS /* localmod 005 */
			int i;
#endif /* localmod 005 */
			nspec **ns = resresv->nspec_arr;
			resresv->job->is_susp_sched = 1;
			for (i = 0; ns[i] != NULL; i++)
				ns[i]->ninfo->num_susp_jobs++;
		}

		resresv->job->is_provisioning = 0;

		/* free resources allocated to job since it's now been requeued */
		if (resresv->job->is_queued && !resresv->job->is_checkpointed) {
			free(resresv->ninfo_arr);
			resresv->ninfo_arr = NULL;
			free_nspecs(resresv->nspec_arr);
			resresv->nspec_arr = NULL;
			free_resource_req_list(resresv->job->resused);
			resresv->job->resused = NULL;
			if (resresv->nodepart_name != NULL) {
				free(resresv->nodepart_name);
				resresv->nodepart_name = NULL;
			}
			free_selspec(resresv->execselect);
			resresv->execselect = NULL;
		}
	}
	else if (resresv->is_resv && resresv->resv !=NULL) {
		resresv->resv->resv_state = RESV_DELETED;

		resv_queue = find_queue_info(resresv->server->queues,
			resresv->resv->queuename);
		if (resv_queue != NULL) {
			resv_queue->is_started = 0;
			ret = is_ok_to_run_queue(resresv->server->policy, resv_queue);
			if (ret == SUCCESS)
				resv_queue->is_ok_to_run = 1;
			else
				resv_queue->is_ok_to_run = 0;

			if (resresv->resv->is_standing) {
				/* This occurrence is over, move resv pointers of all jobs that are
				 * left to next occurrence if one exists
				 */
				if (resresv->resv->resv_idx < resresv->resv->count) {
					next_occr_time = get_occurrence(resresv->resv->rrule,
						resresv->resv->req_start, resresv->resv->timezone, 2);
					if (next_occr_time >= 0) {
						next_occr = find_resource_resv_by_time(resresv->server->resvs,
							resresv->name, next_occr_time);
						if (next_occr != NULL) {
							if (resv_queue->jobs != NULL) {
								for (i = 0; resv_queue->jobs[i] != NULL; i++) {
									if (in_runnable_state(resv_queue->jobs[i]))
										resv_queue->jobs[i]->job->resv = next_occr;
								}
							}
						}
						else {
							snprintf(logbuf, MAX_LOG_SIZE,
								"Can't find occurrence of standing reservation at time %ld",
								next_occr_time);
							schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG,
								resresv->name, logbuf);
						}
					}
				}
			}
		}
	}
}

/**
 * @brief
 *		resource_resv_filter - filters jobs on specified argument
 *
 * @param[in]	resresv_arr	-	array of jobs to filter through
 * @param[in]	size	-	amount of jobs in array
 * @param[in]	filter_func	-	pointer to a function that will filter
 *								- returns 1: job will be added to new array
 *								- returns 0: job will not be added to new array
 * @param[in]	arg	-	an extra arg to pass to filter_func
 * @param[in]	flags	-	flags to describe the filtering
 *
 * @return	pointer to filtered list
 *
 * @par	NOTE:	this function allocates a new array
 * @note
 *		filter_func prototype: int func( resource_resv *, void * )
 *
 */
resource_resv **
resource_resv_filter(resource_resv **resresv_arr, int size,
	int (*filter_func)(resource_resv*, void*), void *arg, int flags)
{
	resource_resv **new_resresvs = NULL;			/* new array of jobs */
	resource_resv **tmp;
	int i, j = 0;

	if (filter_func == NULL) {
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO,
			"resource_resv_filter", "NULL filter function passed in.");
		return NULL;
	}
	if (resresv_arr == NULL && size != 0) {
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO,
			"resource_resv_filter", "NULL input array with non-zero size.");
		return NULL;
	}

	/* NOTE: if resresv_arr is NULL, a one element array will be returned
	 * the one element being the NULL terminator
	 */

	if ((new_resresvs = malloc((size + 1) * sizeof(resource_resv *))) == NULL) {
		log_err(errno, "resource_resv_filter", MEM_ERR_MSG);
		return NULL;
	}

	for (i = 0; i < size; i++) {
		if (filter_func(resresv_arr[i], arg)) {
			new_resresvs[j] = resresv_arr[i];
			j++;
		}
	}
	/* FILTER_FULL - leave the filtered array full size */
	if (!(flags & FILTER_FULL)) {
		if ((tmp = realloc(new_resresvs, (j+1) *
			sizeof(resource_resv *))) == NULL) {
			free(new_resresvs);
			log_err(errno, "resource_resv_filter", "Error allocating memory");
			return NULL;
		}
		else
			new_resresvs = tmp;
	}
	new_resresvs[j] = NULL;

	return new_resresvs;
}

/**
 * @brief
 *		remove_resresv_from_array - remove a resource_resv from an array
 *				    without leaving a hole
 *
 * @param[in,out]	resresv_arr	-	the array
 * @param[in]	resresv	-	the resresv to remove
 *
 * @return	success / failure
 *
 */
int
remove_resresv_from_array(resource_resv **resresv_arr,
	resource_resv *resresv)
{
	int i;

	if (resresv_arr == NULL || resresv == NULL)
		return 0;

	for (i = 0; resresv_arr[i] != NULL && resresv_arr[i] != resresv; i++)
		;

	if (resresv_arr[i] == resresv) {
		/* copy all the jobs past the one we found back one spot.  Including
		 * coping the NULL back one as well
		 */
		for (; resresv_arr[i] != NULL; i++)
			resresv_arr[i] = resresv_arr[i+1];
	}
	return 1;
}

/**
 * @brief
 *		add_resresv_to_array - add a resource resv to an array
 * 			   note: requires reallocating array
 *
 * @param[in]	resresv_arr	-	job array to add job to
 * @param[in]	resresv	-	job to add to array
 *
 * @return	array (changed from realloc)
 * @retval	NULL	: on error
 *
 */
resource_resv **
add_resresv_to_array(resource_resv **resresv_arr,
	resource_resv *resresv)
{
	int size;
	resource_resv **new_arr;

	if (resresv_arr == NULL && resresv == NULL)
		return NULL;

	if (resresv_arr == NULL && resresv != NULL) {
		new_arr = malloc(2*sizeof(resource_resv *));
		if (new_arr == NULL)
			return NULL;
		new_arr[0] = resresv;
		new_arr[1] = NULL;
		return new_arr;
	}

	size = count_array((void **) resresv_arr);

	/* realloc for 1 more ptr (2 == 1 for new and 1 for NULL) */
	new_arr = realloc(resresv_arr, ((size+2) * sizeof(resource_resv *)));

	if (new_arr != NULL) {
		new_arr[size] = resresv;
		new_arr[size+1] = NULL;
	}
	else {
		log_err(errno, "add_resresv_to_array", MEM_ERR_MSG);
		return NULL;
	}

	return new_arr;
}

/**
 * @brief
 *		copy_resresv_array - copy an array of resource_resvs by name.
 *			This is useful  when duplicating a data structure
 *			with a job array in it which isn't easily reproduced.
 *
 * @par NOTE:	if a job in resresv_arr is not in tot_arr, that resresv will be
 *			left out of the new array
 *
 * @param[in]	resresv_arr	-	the job array to copy
 * @param[in]	tot_arr	    -		the total array of jobs
 *
 * @return	new resource_resv array or NULL on error
 *
 */
resource_resv **
copy_resresv_array(resource_resv **resresv_arr,
	resource_resv **tot_arr)
{
	resource_resv *resresv;
	resource_resv **new_resresv_arr;
	int size;
	int i, j;

	if (resresv_arr == NULL || tot_arr == NULL)
		return NULL;

	for (size = 0; resresv_arr[size] != NULL; size++)
		;

	new_resresv_arr =
		(resource_resv **) malloc((size + 1) * sizeof(resource_resv *));
	if (new_resresv_arr == NULL) {
		schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			"copy_resresv_array",  "not enough memory.");
		return NULL;
	}

	for (i = 0, j = 0; resresv_arr[i] != NULL; i++) {
		resresv = find_resource_resv_by_indrank(tot_arr, resresv_arr[i]->rank, resresv_arr[i]->resresv_ind);

		if (resresv != NULL) {
			new_resresv_arr[j] = resresv;
			j++;
		}
	}
	new_resresv_arr[j] = NULL;

	return new_resresv_arr;
}

/**
 * @brief
 *		is_resresv_running - is a resource resv in the running state
 *			     for a job it's in the "R" state
 *			     for an advanced reservation it's in RESV_RUNNING
 *
 *
 * @param[in]	resresv	-	the resresv to check if it's running
 *
 * @return	int
 * @retval	1	: if running
 * @retval	0	: if not running
 *
 */
int
is_resresv_running(resource_resv *resresv)
{
	if (resresv == NULL)
		return 0;

	if (resresv->is_job) {
		if (resresv->job == NULL)
			return 0;

		if (resresv->job->is_running)
			return 1;
	}

	if (resresv->is_resv) {
		if (resresv->resv == NULL)
			return 0;

		if (resresv->resv->resv_state ==RESV_RUNNING)
			return 1;
	}

	return 0;
}

/**
 * @brief
 *		new_place - allocate and initialize a placement spec
 *
 * @return	newly allocated place
 *
 */
place *
new_place()
{
	place *pl;

	if ((pl = malloc(sizeof(place))) == NULL) {
		log_err(errno, "new_place", MEM_ERR_MSG);
		return NULL;
	}

	pl->pack = 0;
	pl->free = 0;
	pl->excl = 0;
	pl->share = 0;
	pl->scatter = 0;
	pl->vscatter = 0;
	pl->exclhost = 0;

	pl->group = NULL;

	return pl;
}

/**
 * @brief
 *		free_place - free a placement spec
 *
 * @param[in,out]	pl	-	the placement spec to free
 *
 * @return	nothing
 *
 */
void
free_place(place *pl)
{
	if (pl == NULL)
		return;

	if (pl->group != NULL)
		free(pl->group);

	free(pl);
}

/**
 * @brief
 *		dup_place - duplicate a place structure
 *
 * @param[in]	pl	-	the place structure to duplicate
 *
 * @return	duplicated place structure
 *
 */
place *
dup_place(place *pl)
{
	place *newpl;

	if (pl == NULL)
		return NULL;

	newpl = new_place();

	if (newpl == NULL)
		return NULL;

	newpl->pack = pl->pack;
	newpl->free = pl->free;
	newpl->scatter = pl->scatter;
	newpl->vscatter = pl->vscatter;
	newpl->excl = pl->excl;
	newpl->exclhost = pl->exclhost;
	newpl->share = pl->share;

	newpl->group = string_dup(pl->group);

	return newpl;
}

/**
 * @brief
 *		new_chunk - constructor for chunk
 *
 * @return	new_chunk
 * @retval	NULL	: malloc failed.
 */
chunk *
new_chunk()
{
	chunk *ch;

	if ((ch = malloc(sizeof(chunk))) == NULL) {
		log_err(errno, "new_chunk", MEM_ERR_MSG);
		return NULL;
	}

	ch->num_chunks = 0;
	ch->seq_num = 0;
	ch->str_chunk = NULL;
	ch->req = NULL;

	return ch;
}

/**
 * @brief
 *		dup_chunk_array - array copy constructor for array of chunk pointers
 *
 * @param[in]	old_chunk_arr	-	old array of chunk pointers
 *
 * @return	duplicate chunk array.
 */
chunk **
dup_chunk_array(chunk **old_chunk_arr)
{
	int i;
	int ct;
	chunk **new_chunk_arr = NULL;
	int error = 0;

	if (old_chunk_arr == NULL)
		return NULL;

	ct = count_array((void **) old_chunk_arr);

	if ((new_chunk_arr = calloc(ct + 1, sizeof(chunk *))) == NULL) {
		log_err(errno, "dup_chunk_array", MEM_ERR_MSG);
		return NULL;
	}

	for (i = 0; old_chunk_arr[i] != NULL && !error; i++) {
		new_chunk_arr[i] = dup_chunk(old_chunk_arr[i]);
		if (new_chunk_arr[i] == NULL)
			error = 1;
	}


	new_chunk_arr[i] = NULL;

	if (error) {
		free_chunk_array(new_chunk_arr);
		return NULL;
	}

	return new_chunk_arr;
}

/**
 * @brief
 *		dup_chunk - copy constructor for chunk
 *
 * @param[in]	ochunk	-	old chunk structure
 *
 * @return	duplicate chunk structure.
 */
chunk *
dup_chunk(chunk *ochunk)
{
	chunk *nchunk;

	if (ochunk == NULL)
		return NULL;

	nchunk = new_chunk();

	if (nchunk == NULL)
		return NULL;

	nchunk->num_chunks = ochunk->num_chunks;
	nchunk->seq_num = ochunk->seq_num;
	nchunk->str_chunk = string_dup(ochunk->str_chunk);
	nchunk->req = dup_resource_req_list(ochunk->req);

	if (nchunk->req == NULL) {
		free_chunk(nchunk);
		return NULL;
	}

	return nchunk;
}

/**
 * @brief
 *		free_chunk_array - array destructor for array of chunk ptrs
 *
 * @param[in,out]	chunk_arr	-	old array of chunk pointers
 *
 * @return	void
 */
void
free_chunk_array(chunk **chunk_arr)
{
	int i;

	if (chunk_arr == NULL)
		return;

	for (i = 0; chunk_arr[i] != NULL; i++)
		free_chunk(chunk_arr[i]);

	free(chunk_arr);
}

/**
 * @brief
 *		free_chunk - destructor for chunk
 *
 * @param[in,out]	ch	-	chunk structure to be freed.
 */
void
free_chunk(chunk *ch)
{
	if (ch == NULL)
		return;

	if (ch->str_chunk != NULL)
		free(ch->str_chunk);

	if (ch->req != NULL)
		free_resource_req_list(ch->req);

	free(ch);
}

/**
 * @brief
 *		new_selspec - constructor for selspec
 *
 * @return	new selspec
 * @retval	NULL	: Fail
 */
selspec *
new_selspec()
{
	selspec *spec;

	if ((spec = malloc(sizeof(selspec))) == NULL) {
		log_err(errno, "new_selspec", MEM_ERR_MSG);
		return NULL;
	}

	spec->total_chunks = 0;
	spec->total_cpus = 0;
	spec->defs = NULL;
	spec->chunks = NULL;

	return spec;
}

/**
 * @brief
 *		dup_selspec - copy constructor for selspec
 *
 * @param[in]	oldspec	-	old selspec to be copied
 *
 * @return	new selspec
 * @retval	NULL	: Fail
 */
selspec *
dup_selspec(selspec *oldspec)
{
	selspec *newspec;

	if (oldspec == NULL)
		return NULL;

	newspec = new_selspec();

	if (newspec == NULL)
		return NULL;

	newspec->total_chunks = oldspec->total_chunks;
	newspec->total_cpus = oldspec->total_cpus;
	newspec->chunks = dup_chunk_array(oldspec->chunks);
	newspec->defs = copy_resdef_array(oldspec->defs);

	if (newspec->chunks == NULL || newspec->defs == NULL) {
		free_selspec(newspec);
		return NULL;
	}

	return newspec;
}

/**
 * @brief
 *		free_selspec - destructor for selspec
 *
 * @param[in,out]	spec	-	selspec to be freed.
 */
void
free_selspec(selspec *spec)
{
	if (spec == NULL)
		return;

	if (spec->defs != NULL)
		free(spec->defs);

	if (spec->chunks != NULL)
		free_chunk_array(spec->chunks);

	free(spec);
}


/**
 * @brief
 *		compare_res_to_str - compare a resource structure of type string to
 *			     a character array string
 *
 * @param[in]	res	-	the resource
 * @param[in]	str	-	the string
 * @param[in]	cmpflag	-	case sensitive or insensitive comparison
 *
 * @return	int
 * @retval	1	: if they match
 * @retval	0	: if they don't or res is not a string or error
 *
 */
int
compare_res_to_str(schd_resource *res, char *str , enum resval_cmpflag cmpflag)
{
	int i;

	if (res == NULL || str == NULL)
		return 0;

	if (res->str_avail == NULL)
		return 0;

	for (i = 0; res->str_avail[i] != NULL; i++) {
		if (cmpflag == CMP_CASE) {
			if (!strcmp(res->str_avail[i], str))
				return 1;
		}
		else if (cmpflag == CMP_CASELESS) {
			if (!strcasecmp(res->str_avail[i], str))
				return 1;
		}
		else {
			schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_NOTICE, res->name, "Incorrect flag for comparison.");
			return 0;
		}
	}
	/* if we got here, we didn't match the string */
	return 0;
}

/**
 * @brief
 *		compare_non_consumable - perform the == operation on a non consumable
 *				resource and resource_req
 *
 * @param[in]	res	-	the resource
 * @param[in]	req	-	resource request
 *
 * @return	int
 * @retval	1	: for a match
 * @retval	0	: for not a match
 *
 */
int
compare_non_consumable(schd_resource *res, resource_req *req)
{

	if (res == NULL && req == NULL)
		return 0;

	if (req == NULL)
		return 0;

	if (!req->type.is_non_consumable)
		return 0;

	if (res != NULL) {
		if (!res->type.is_non_consumable)
			return 0;

		if (res->type.is_string && res->str_avail == NULL)
			return 0;
	}

	/* successful boolean match: (req = request res = resource on object)
	 * req: True  res: True
	 * req: False res: False
	 * req: False res: NULL
	 * req:   *   res: TRUE_FALSE
	 */
	if (req->type.is_boolean) {
		if (!req->amount  && res == NULL)
			return 1;
		else if (req->amount && res == NULL)
			return 0;
		else if (res->avail == TRUE_FALSE)
			return 1;
		else
			return res->avail == req->amount;
	}

	if (req->type.is_string && res != NULL) {
		/* 'host' to follow IETF rules; 'host' is case insensitive  */
		if (!strcmp(res->name, "host"))
			return compare_res_to_str(res, req->res_str, CMP_CASELESS);
		else
			return compare_res_to_str(res, req->res_str, CMP_CASE);
	}

	return 0;
}

/**
 * @brief
 * 		create a select from an nspec array to place chunks back on the
 *        same nodes as before
 *
 * @param[in]	nspec_array	-	npsec array to convert
 *
 * @return	converted select string
 */
char *
create_select_from_nspec(nspec **nspec_array)
{
	char *select_spec = NULL;
	int selsize = 0;
	char buf[1024];
	resource_req *req;
	int i;

	if (nspec_array == NULL || nspec_array[0] == NULL)
		return NULL;

	/* convert form (node:foo=X:bar=Y) into 1:vnode=node:foo=X:bay=Y*/
	for (i = 0; nspec_array[i] != NULL; i++) {
		/* Don't add exclhost chunks into our select. They will be added back when
		 * we call  eval_selspec() with the original place=exclhost.  If we added
		 * them, we'd have issues placing chunks w/o resources
		 */
		if (nspec_array[i]->resreq != NULL) {
			snprintf(buf, sizeof(buf), "1:vnode=%s", nspec_array[i]->ninfo->name);
			if (pbs_strcat(&select_spec, &selsize, buf) == NULL) {
				if (selsize > 0)
					free(select_spec);
				return NULL;
			}
			for (req = nspec_array[i]->resreq; req != NULL; req = req->next) {
				snprintf(buf, sizeof(buf), ":%s=%s", req->name, res_to_str(req, RF_REQUEST));
				if (pbs_strcat(&select_spec, &selsize, buf) == NULL) {
					if (selsize > 0)
						free(select_spec);
					return NULL;
				}
			}
			if (pbs_strcat(&select_spec, &selsize, "+") == NULL) {
				if (selsize > 0)
					free(select_spec);
				return NULL;
			}
		}
	}
	/* get rid of trailing '+' */
	select_spec[strlen(select_spec)-1] = '\0';

	return select_spec;
}

/**
 * @brief
 * 		true if job/resv is in a state in which it can be run
 * 		Jobs are runnable if:
 *	   	in state 'Q'
 *		suspended by the scheduler
 *		is job array in state 'B' and there is a queued subjob
 *		Reservations are runnable if they are in state RESV_CONFIRMED
 *
 *
 * @param[in] resresv - resource resv to check
 *
 * @return int
 * @retval	1	: if the resource resv is in a runnable state
 * @retval  0	: if not
 *
 */
int
in_runnable_state(resource_resv *resresv)
{
	if (resresv == NULL)
		return 0;

	if (resresv->is_job && resresv->job !=NULL) {
		if (resresv->job->is_array) {
			if (range_next_value(resresv->job->queued_subjobs, -1) >= 0 ) {
				if(resresv->job->is_begin || resresv->job->is_queued)
					return 1;
			}
			else
				return 0;
		}

		if (resresv->job  ->is_queued)
			return 1;

		if (resresv->job->is_susp_sched)
			return 1;
	}
	else if (resresv->is_resv && resresv->resv !=NULL) {
		if (resresv->resv->resv_state ==RESV_CONFIRMED)
			return 1;
	}

	return 0;
}

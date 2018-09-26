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
 * @file    node_partition.c
 *
 * @brief
 * node_partition.c - contains functions to related to node_partition structure.
 *
 * Functions included are:
 * 	new_node_partition()
 * 	free_node_partition_array()
 * 	free_node_partition()
 * 	dup_node_partition_array()
 * 	dup_node_partition()
 * 	find_node_partition()
 * 	find_node_partition_by_rank()
 * 	create_node_partitions()
 * 	node_partition_update_array()
 * 	node_partition_update()
 * 	new_np_cache()
 * 	free_np_cache_array()
 * 	free_np_cache()
 * 	find_alloc_np_cache()
 * 	add_np_cache()
 * 	resresv_can_fit_nodepart()
 * 	create_specific_nodepart()
 * 	create_placement_sets()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "errno.h"

#include <log.h>
#include <pbs_ifl.h>
#include <pbs_internal.h>
#include "config.h"
#include "constant.h"
#include "data_types.h"
#include "server_info.h"
#include "queue_info.h"
#include "node_info.h"
#include "resource_resv.h"
#include "resource.h"
#include "misc.h"
#include "node_partition.h"
#include "check.h"
#include "globals.h"
#include "sort.h"
#include "buckets.h"


/**
 * @brief
 *		new_node_partition - allocate and initialize a node_partition
 *
 * @return new node partition
 * @retval	NULL	: on error
 *
 */
node_partition *
new_node_partition()
{
	node_partition *np;

	if ((np = malloc(sizeof(node_partition))) == NULL) {
		log_err(errno, "new_node_partition", MEM_ERR_MSG);
		return NULL;
	}

	np->ok_break = 1;
	np->excl = 0;
	np->name = NULL;
	np->def = NULL;
	np->res_val = NULL;
	np->tot_nodes = 0;
	np->free_nodes = 0;
	np->res = NULL;
	np->ninfo_arr = NULL;
	np->bkts = NULL;

	np->rank = -1;

	return np;
}

/**
 * @brief
 *		free_node_partition_array - free an array of node_partitions
 *
 * @param[in]	np_arr	-	node partition array to free
 *
 * @return	nothing
 *
 */
void
free_node_partition_array(node_partition **np_arr)
{
	int i;

	if (np_arr == NULL)
		return;

	for (i = 0; np_arr[i] != NULL; i++)
		free_node_partition(np_arr[i]);

	free(np_arr);
}

/**
 * @brief
 *		free_node_partition - free a node_partition structure
 *
 * @param[in]	np	-	the node_partition to free
 *
 */
void
free_node_partition(node_partition *np)
{
	if (np == NULL)
		return;

	if (np->name != NULL)
		free(np->name);

	np->def = NULL;

	if (np->res_val != NULL)
		free(np->res_val);

	if (np->res != NULL)
		free_resource_list(np->res);

	if (np->ninfo_arr != NULL)
		free(np->ninfo_arr);

	if (np->bkts != NULL)
		free_node_bucket_array(np->bkts);

	free(np);
}

/**
 * @brief
 *		dup_node_partition_array - duplicate a node_partition array
 *
 * @param[in]	onp_arr	-	the node_partition array to duplicate
 * @param[in]	nsinfo	-	server for the new node partition
 *
 * @return	duplicated array
 * @retval	NULL	: on error
 *
 */
node_partition **
dup_node_partition_array(node_partition **onp_arr, server_info *nsinfo)
{
	int i;
	node_partition **nnp_arr;
	if (onp_arr == NULL)
		return NULL;

	for (i = 0; onp_arr[i] != NULL; i++)
		;

	if ((nnp_arr = malloc((i+1) * sizeof(node_partition *))) == NULL) {
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
			"dup_node_partition_array", "error allocating memory");
		return NULL;
	}

	for (i = 0; onp_arr[i] != NULL; i++) {
		nnp_arr[i] = dup_node_partition(onp_arr[i], nsinfo);
		if (nnp_arr[i] == NULL) {
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
				"dup_node_partition_array", "error allocating memory");
			free_node_partition_array(nnp_arr);
			return NULL;
		}
	}

	nnp_arr[i] = NULL;

	return nnp_arr;
}

/**
 * @brief
 *		dup_node_partition - duplicate a node_partition structure
 *
 * @param[in]	onp	-	the node_partition structure to duplicate
 * @param[in]	nsinfo	-	server for the new node partiton (the nodes are needed)
 *
 * @return	duplicated node_partition
 * @retval	NULL	: on error
 *
 */
node_partition *
dup_node_partition(node_partition *onp, server_info *nsinfo)
{
	node_partition *nnp;

	if (onp == NULL)
		return NULL;

	if ((nnp = new_node_partition()) == NULL)
		return NULL;

	if (onp->name != NULL)
		nnp->name = string_dup(onp->name);

	if (onp->def != NULL)
		nnp->def = onp->def;

	if (onp->res_val != NULL)
		nnp->res_val = string_dup(onp->res_val);

	nnp->ok_break = onp->ok_break;
	nnp->excl = onp->excl;
	nnp->tot_nodes = onp->tot_nodes;
	nnp->free_nodes = onp->free_nodes;
	nnp->res = dup_resource_list(onp->res);
#ifdef NAS /* localmod 049 */
	nnp->ninfo_arr = copy_node_ptr_array(onp->ninfo_arr, nsinfo->nodes, nsinfo);
#else
	nnp->ninfo_arr = copy_node_ptr_array(onp->ninfo_arr, nsinfo->nodes);
#endif

	nnp->bkts = dup_node_bucket_array(onp->bkts, nsinfo);
	nnp->rank = onp->rank;

	/* validity check */
	if (onp->name == NULL || onp->res_val == NULL ||
		nnp->res == NULL || nnp->ninfo_arr == NULL) {
		free_node_partition(nnp);
		return NULL;
	}
	return nnp;
}

/**
 * @brief
 *		find_node_partition - find a node partition by (resource_name=value)
 *			      partition name from a pool of partitions
 *
 * @param[in]	np_arr	-	array of node partitions to search name
 *
 * @return	found node partition
 * @retval	NULL	: if not found
 *
 */
node_partition *
find_node_partition(node_partition **np_arr, char *name)
{
	int i;
	if (np_arr == NULL || name == NULL)
		return NULL;

	for (i = 0; np_arr[i] != NULL && strcmp(np_arr[i]->name, name); i++)
		;

	return np_arr[i];
}

/**
 * @brief
 * 		find node partition by unique rank
 *
 * @param[in]	np_arr	-	array of node partitions to search
 * @param[in]	rank	-	unique rank of node partition
 *
 * @return	node_partition **
 * @retval	found node partition
 * @retval	NULL	: if node partition isn't found or on error
 */

node_partition *
find_node_partition_by_rank(node_partition **np_arr, int rank)
{
	int i;
	if (np_arr == NULL)
		return NULL;

	for (i = 0; np_arr[i] != NULL && np_arr[i]->rank != rank; i++)
		;

	return np_arr[i];
}

/**
 * @brief
 * 		break apart nodes into partitions
 *		A possible side-effect of this function when multiple identical
 *		resources are defined on an attribute, is that the node
 *		partitions accounting for this node may count this node in the
 *		total count of "free_nodes" for that partition (if the node was
 *		free in the first place). Due to this, incorrect accounting,
 *		the metadata of the node partition may cause eval_selspec to
 *		descend into the node matching code instead of bailing out right
 *		away due to the fact that the node partition has insufficient
 *		resources.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	nodes	-	the nodes which to create partitions from
 * @param[in]	resnames	-	node grouping resource names
 * @param[in]	flags	-	flags which change operations of node partition creation
 *							NP_IGNORE_EXCL - ignore vnodes marked excl
 *	 						NP_CREATE_REST - create a part for vnodes w/ no np resource
 * @param[out]	num_parts	-	the number of partitions created
 *
 * @return	node_partition ** (NULL terminated node_partition array)
 * @retval	: created node_partition array
 * @retval	: NULL on error
 *
 */
node_partition **
create_node_partitions(status *policy, node_info **nodes, char **resnames, unsigned int flags, int *num_parts)
{
	node_partition **np_arr;
	node_partition *np;
	node_partition **tmp_arr;
	char buf[1024];
	char *str;
	int free_str = 0;
	int np_arr_size = 0;
	schd_resource *res;

	int num_nodes;
	int reslen;
	int i;

	schd_resource *hostres;
	schd_resource *tmpres;

	int res_i;		/* index of placement set resource name (resnames) */
	int val_i;		/* index of placement set resource value */
	int node_i;		/* index into nodes array */
	int np_i;		/* index into node partition array we are creating */

	schd_resource unset_res;
	char *unsetarr[] = {"\"\"", NULL};

	resdef *def;

	queue_info **queues = NULL;

	if (nodes == NULL || resnames == NULL)
		return NULL;

	if (nodes[0] != NULL && nodes[0]->server != NULL)
		queues = nodes[0]->server->queues;

	num_nodes = count_array((void **) nodes);

	if ((np_arr = (node_partition **)
		malloc((num_nodes + 1) * sizeof(node_partition *))) == NULL) {
		log_err(errno, "create_node_partitions", MEM_ERR_MSG);
		return NULL;
	}

	np_arr_size = num_nodes;

	np_i = 0;
	np_arr[0] = NULL;

	if (flags & NP_CREATE_REST) {
		memset(&unset_res, 0, sizeof(unset_res));
		unset_res.str_avail = (char **) unsetarr;
		unset_res.type.is_non_consumable = 1;
		unset_res.type.is_string = 1;
	}

	for (res_i = 0; resnames[res_i] != NULL; res_i++) {
		def = find_resdef(allres, resnames[res_i]);
		reslen = strlen(resnames[res_i]);
		for (node_i = 0; nodes[node_i] != NULL; node_i++) {
			if (nodes[node_i]->is_stale)
				continue;

			res = find_resource(nodes[node_i]->res, def);

			if (res == NULL && (flags & NP_CREATE_REST)) {
				unset_res.name = resnames[res_i];
				res = &unset_res;
			}
			if (res != NULL) {
				for (val_i = 0; res->str_avail[val_i] != NULL; val_i++) {
					/* 2: 1 for '=' 1 for '\0' */
					if (reslen + strlen(res->str_avail[val_i]) + 2 < 1024) {
						sprintf(buf, "%s=%s", resnames[res_i], res->str_avail[val_i]);
						str = buf;
					}
					else {
						str = concat_str(resnames[res_i], "=", res->str_avail[val_i], 0);
						free_str = 1;
					}
					/* If we find the partition, we've already created it - add the node
					 * to the existing partition.  If we don't find it, we create it.
					 */
					np = find_node_partition(np_arr, str);
					if (np == NULL) {
						if (np_i >= np_arr_size) {
							tmp_arr = realloc(np_arr,
								(np_arr_size * 2 + 1) * sizeof(node_partition *));
							if (tmp_arr == NULL) {
								log_err(errno, "create_node_partitions", MEM_ERR_MSG);
								free_node_partition_array(np_arr);
								if (free_str == 1)
									free(str);

								return NULL;
							}
							np_arr = tmp_arr;
							np_arr_size *= 2;
						}

						np_arr[np_i] = new_node_partition();
						if (np_arr[np_i] != NULL) {
							if (free_str) {
								np_arr[np_i]->name = str;
								free_str = 0;
							}
							else
								np_arr[np_i]->name = string_dup(str);

							np_arr[np_i]->def = def;
							np_arr[np_i]->res_val = string_dup(res->str_avail[val_i]);
							np_arr[np_i]->tot_nodes = 1;
							if (nodes[node_i]->is_free)
								np_arr[np_i]->free_nodes = 1;
							np_arr[np_i]->rank = get_sched_rank();

							if (np_arr[np_i]->res_val == NULL) {
								np_arr[np_i+1] = NULL;
								free_node_partition_array(np_arr);
								return NULL;
							}

							np_i++;
							np_arr[np_i] = NULL;
						}
						else {
							free_node_partition_array(np_arr);
							return NULL;
						}
					}
					else {
						np->tot_nodes++;
						if (nodes[node_i]->is_free)
							np->free_nodes++;
					}
					if (free_str) {
						free(str);
						free_str = 0;
					}

				}
			}
			/* else we ignore nodes without the node partition resource set
			 * unless the NP_CREATE_REST flag is set
			 */
		}
	}


	/* now that we have a list of node partitions and number of nodes in each
	 * lets allocate a node array and fill it
	 */

	for (np_i = 0; np_arr[np_i] != NULL; np_i++) {
		i = 0;
		np_arr[np_i]->ok_break = 1;
		hostres = NULL;

		np_arr[np_i]->ninfo_arr =
			malloc((np_arr[np_i]->tot_nodes + 1) * sizeof(node_info *));

		if (np_arr[np_i]->ninfo_arr == NULL) {
			free_node_partition_array(np_arr);
			return NULL;
		}

		np_arr[np_i]->ninfo_arr[0] = NULL;

		for (node_i = 0; nodes[node_i] != NULL &&
			i < np_arr[np_i]->tot_nodes; node_i++) {
			if (nodes[node_i]->is_stale)
				continue;

			res = find_resource(nodes[node_i]->res, np_arr[np_i]->def);
			if (res == NULL && (flags & NP_CREATE_REST)) {
				unset_res.name = resnames[res_i];
				res = &unset_res;
			}
			if (res != NULL) {
				if (compare_res_to_str(res, np_arr[np_i]->res_val, CMP_CASE)) {
					if (np_arr[np_i]->ok_break) {
						tmpres = find_resource(nodes[node_i]->res, getallres(RES_HOST));
						if (tmpres != NULL) {
							if (hostres == NULL)
								hostres = tmpres;
							else {
								if (!compare_res_to_str(hostres, tmpres->str_avail[0], CMP_CASELESS))
									np_arr[np_i]->ok_break = 0;
							}
						}
					}
					np_arr[np_i]->ninfo_arr[i] = nodes[node_i];
					i++;
					np_arr[np_i]->ninfo_arr[i] = NULL;
				}
			}
		}
		/* if multiple resource values are present, tot_nodes may be incorrect.
		 * recalculating tot_nodes for each node partition.
		 */
		np_arr[np_i]->tot_nodes = count_array((void **) np_arr[np_i]->ninfo_arr);
		np_arr[np_i]->bkts = create_node_buckets(policy, np_arr[np_i]->ninfo_arr, queues, NO_PRINT_BUCKETS);
		node_partition_update(policy, np_arr[np_i]);
	}

	*num_parts = np_i;
	return np_arr;
}

/**
 * @brief update the node buckets associated with a node partition on
 *        job/resv run/end
 *
 *  @param[in] bkts - the buckets to update
 *  @param[in] ninfo_arr - the nodes of the job/resv
 */
void
update_buckets_for_node_array(node_bucket **bkts, node_info **ninfo_arr) {
	int i, j;

	if (bkts == NULL || ninfo_arr == NULL)
		return;

	for (i = 0; ninfo_arr[i] != NULL; i++) {
		for (j = 0; bkts[j] != NULL; j++) {
			int node_ind = ninfo_arr[i]->node_ind;
			if (pbs_bitmap_get_bit(bkts[j]->bkt_nodes, node_ind)) {
				if (ninfo_arr[i]->num_jobs > 0 || ninfo_arr[i]->num_run_resv > 0) {
					if (pbs_bitmap_get_bit(bkts[j]->free_pool->truth, node_ind)) {
						pbs_bitmap_bit_off(bkts[j]->free_pool->truth, node_ind);
						bkts[j]->free_pool->truth_ct--;
					} else if(pbs_bitmap_get_bit(bkts[j]->busy_later_pool->truth, node_ind)) {
						pbs_bitmap_bit_off(bkts[j]->busy_later_pool->truth, node_ind);
						bkts[j]->busy_later_pool->truth_ct--;
					}
					pbs_bitmap_bit_on(bkts[j]->busy_pool->truth, node_ind);
					bkts[j]->busy_pool->truth_ct++;
				} else if (pbs_bitmap_get_bit(bkts[j]->busy_pool->truth, node_ind)) {
					pbs_bitmap_bit_off(bkts[j]->busy_pool->truth, node_ind);
					bkts[j]->busy_pool->truth_ct--;

					if (ninfo_arr[i]->node_events != NULL) {
						pbs_bitmap_bit_on(bkts[j]->busy_later_pool->truth, node_ind);
						bkts[j]->busy_later_pool->truth_ct++;
					}
					else {
						pbs_bitmap_bit_on(bkts[j]->free_pool->truth, node_ind);
						bkts[j]->free_pool->truth_ct++;
					}
				}

				break;
			}
		}
	}

}

/**
 * @brief
 * 		update metadata for an entire array of node partitions
 *
 * @param[in] policy	-	policy info
 * @param[in] nodepart	-	partition array to update
 * @param[in] ninfo_arr - 	nodes being updated (may be NULL)
 *
 * @return	int
 * @retval	1	: on all success
 * @retval	0	: on any failure
 *
 * @note
 * 		This is not an atomic operation -- this means that if this
 *		function fails, some node partitions may have been updated and
 *		others not.
 *
 */
int
node_partition_update_array(status *policy, node_partition **nodepart, node_info **ninfo_arr)
{
	int i;
	int cur_rc = 0;
	int rc = 1;

	if (policy == NULL || nodepart == NULL)
		return 0;

	for (i = 0; nodepart[i] != NULL; i++) {
		cur_rc = node_partition_update(policy, nodepart[i]);
		if (cur_rc == 0)
			rc = 0;
		update_buckets_for_node_array(nodepart[i]->bkts, ninfo_arr);
	}

	return rc;
}


/**
 * @brief
 * 		update the meta data about a node partition
 *			like free_nodes and consumable resources in res
 *
 * @param[in]	policy	-	policy info
 * @param[in]	np	-	the node partition to update
 * @param[in]	nodes	-	the entire node array used to create these node partitions
 *
 * @return	int
 * @retval	1	: on success
 * @retval	0	: on failure
 *
 */
int
node_partition_update(status *policy, node_partition *np)
{
	int i;
	int rc = 1;
	schd_resource *res;
	unsigned int arl_flags = USE_RESOURCE_LIST | ADD_ALL_BOOL;

	if (np == NULL)
		return 0;

	/* if res is not NULL, we are updating.  Clear the meta data for the update*/
	if (np->res != NULL) {
		arl_flags |= NO_UPDATE_NON_CONSUMABLE;
		for (res = np->res; res != NULL; res = res->next) {
			if (res->type.is_consumable) {
				res->assigned = 0;
				res->avail = 0;
			}
		}
	}
	else
		arl_flags |= ADD_UNSET_BOOLS_FALSE;

	np->free_nodes = 0;

	for (i = 0; i < np->tot_nodes; i++) {
		if (np->ninfo_arr[i]->is_free) {
			np->free_nodes++;
			arl_flags &= ~ADD_AVAIL_ASSIGNED;
		} else
			arl_flags |= ADD_AVAIL_ASSIGNED;

		if (np->res == NULL)
			np->res = dup_selective_resource_list(np->ninfo_arr[i]->res,
				policy->resdef_to_check, arl_flags);
		else if (!add_resource_list(policy, np->res, np->ninfo_arr[i]->res, arl_flags)) {
			rc = 0;
			break;
		}
	}

	if (policy->node_sort[0].res_name != NULL && conf.node_sort_unused) {
		/* Resort the nodes in the partition so that selection works correctly. */
		qsort(np->ninfo_arr, np->tot_nodes, sizeof(node_info*),
			multi_node_sort);
	}

	return rc;
}

/**
 * @brief
 *		new_np_cache - constructor
 *
 * @return	new np_cache structure
 */
np_cache *
new_np_cache(void)
{
	np_cache *npc;

	if ((npc = malloc(sizeof(np_cache))) == NULL) {
		log_err(errno, "new_np_cache", MEM_ERR_MSG);
		return NULL;
	}

	npc->resnames = NULL;
	npc->ninfo_arr = NULL;
	npc->nodepart = NULL;
	npc->num_parts = UNSPECIFIED;

	return npc;
}

/**
 * @brief
 *		free_np_cache_array - destructor for array
 *
 * @param[in,out]	npc_arr	-	np cashe array.
 */
void
free_np_cache_array(np_cache **npc_arr)
{
	int i;

	if (npc_arr == NULL)
		return;

	for (i = 0; npc_arr[i] != NULL; i++)
		free_np_cache(npc_arr[i]);

	free(npc_arr);

	return;
}

/**
 * @brief
 *		free_np_cache - destructor
 *
 * @param[in,out]	npc_arr	-	np cashe array.
 */
void
free_np_cache(np_cache *npc)
{
	if (npc == NULL)
		return;

	if (npc->resnames != NULL)
		free_string_array(npc->resnames);

	if (npc->nodepart != NULL)
		free_node_partition_array(npc->nodepart);

	/* reference to an array of nodes, the owner will free */
	npc->ninfo_arr = NULL;

	free(npc);
}

/**
 * @brief
 *		find_np_cache - find a np_cache by the array of resource names and
 *			nodes which created it.
 *
 * @param[in]	npc_arr	-	the array to search
 * @param[in]	resnames	-	the list of names
 * @param[in]	ninfo_arr	-	array of nodes
 *
 * @par NOTE:
 * 		function does node node_info pointer comparison to save time
 *
 * @return	the node found node partition
 * @retval	NULL	: if not (or on error)
 *
 */
np_cache *
find_np_cache(np_cache **npc_arr,
	char **resnames, node_info **ninfo_arr)
{
	int i;

	if (npc_arr == NULL || resnames == NULL || ninfo_arr == NULL)
		return NULL;

	for (i = 0; npc_arr[i] != NULL; i++) {
		if (npc_arr[i]->ninfo_arr == ninfo_arr &&
			match_string_array(npc_arr[i]->resnames, resnames) == SA_FULL_MATCH)
			break;
	}

	return npc_arr[i];
}

/**
 * @brief
 * 		find a np_cache by the array of resource names
 *		and nodes which created it.  If the np_cache
 *		does not exist, create it and add it to the list
 *
 * @param[in]	policy	-	policy info
 * @param[in,out]	pnpc_arr	-	pointer to np_cache array -- if *npc_arr == NULL
 *		 	           				a np_cache will be created and it will be set
 *			           				Example: you pass &(sinfo->npc_arr)
 * @param[in]	resnames	-	the names used to create the pool of node parts
 * @param[in]	ninfo_arr	-	the node array used to create the pool of node_parts
 * @param[in]	sort_func	-	sort function to sort placement sets.
 *				  				sets are only sorted when they are created.
 *				  				If NULL is passed in, no sorting is done
 *
 * @return	np_cache *
 * @retval	found	: created np_cache
 * @retval 	NULL	: on error
 *
 */
np_cache *
find_alloc_np_cache(status *policy, np_cache ***pnpc_arr,
	char **resnames, node_info **ninfo_arr,
	int (*sort_func)(const void *, const void *))
{
	node_partition **nodepart = NULL;
	int num_parts;
	np_cache *npc = NULL;
	int error = 0;

	if (resnames == NULL || ninfo_arr == NULL || pnpc_arr == NULL)
		return NULL;

	npc = find_np_cache(*pnpc_arr, resnames, ninfo_arr);

	if (npc == NULL) {
		/* didn't find node partition cache, need to allocate and create */
		nodepart = create_node_partitions(policy, ninfo_arr, resnames,
			policy->only_explicit_psets ? NO_FLAGS : NP_CREATE_REST,
			&num_parts);
		if (nodepart != NULL) {
			if (sort_func != NULL)
				qsort(nodepart, num_parts, sizeof(node_partition *), sort_func);

			npc = new_np_cache();
			if (npc != NULL) {
				npc->ninfo_arr = ninfo_arr;
				npc->resnames = dup_string_array(resnames);
				npc->num_parts = num_parts;
				npc->nodepart = nodepart;
				if (npc->resnames == NULL || add_np_cache(pnpc_arr, npc) ==0) {
					free_np_cache(npc);
					error = 1;
				}
			}
			else {
				free_node_partition_array(nodepart);
				error = 1;
			}
		}
		else
			error = 1;
	}

	if (error)
		return NULL;

	return npc;
}


/**
 * @brief
 *		add_np_cache - add an np_cache to an array
 *
 * @param[in]	policy	-	policy info
 * @param[in,out]	pnpc_arr	-	pointer to np_cache array -- if *npc_arr == NULL
 *
 * @return	1	: on success
 * @return	0	: on failure
 */
int
add_np_cache(np_cache ***npc_arr, np_cache *npc)

{
	np_cache **new_cache;
	np_cache **cur_cache;
	int ct;

	if (npc_arr == NULL || npc == NULL)
		return 0;

	cur_cache = *npc_arr;

	ct = count_array((void **) cur_cache);

	/* ct+2: 1 for new element 1 for NULL ptr */
	new_cache = realloc(cur_cache, (ct+2) * sizeof(np_cache *));

	if (new_cache == NULL)
		return 0;

	new_cache[ct] = npc;
	new_cache[ct+1] = NULL;

	*npc_arr = new_cache;
	return 1;
}

/**
 * @brief
 * 		do an initial check to see if a resresv can fit into a node partition
 *        based on the meta data we keep.
 *
 * @param[in]	policy	-	policy info
 * @param[in]	np	-	node partition to check
 * @param[in]	resresv	-	job/resv to see if it can fit
 * @param[in]	flags	-	check_flags
 *							COMPARE_TOTAL - compare with resources_available value
 *							RETURN_ALL_ERR - return all the errors, not just the first failure
 * @param[in]	err	-	schd_error structure to return why job/resv can't fit
 *
 * @return	int
 * @retval	1	: can fit
 * @retval	0	: can't fit
 * @retval	-1	: on error
 */
int
resresv_can_fit_nodepart(status *policy, node_partition *np, resource_resv *resresv,
	int flags, schd_error *err)
{
	int i;
	schd_error *prev_err = NULL;
	int can_fit = 1;
	int pass_flags;
	resource_req *req;
	selspec *spec = NULL;
	place *pl = NULL;


	if (policy == NULL || np == NULL || resresv == NULL || err == NULL)
		return -1;

	pass_flags = flags|UNSET_RES_ZERO;

	/* Check 1: Based on the flag check if there are any nodes available or if
	 * they are free.
	 */
	if (flags & COMPARE_TOTAL) {
		/* Check that node partition must have one or more nodes inside it */
		if (np->tot_nodes == 0) {
			set_schd_error_codes(err, NEVER_RUN, NO_TOTAL_NODES);
			if ((flags & RETURN_ALL_ERR)) {
				can_fit = 0;
				err->next = new_schd_error();
				prev_err = err;
				err = err->next;
			} else
				return 0;
		}
	} else {
		/* Check is there at least 1 node in the free state */
		if (np->free_nodes == 0) {
			set_schd_error_codes(err, NOT_RUN, NO_FREE_NODES);
			if ((flags & RETURN_ALL_ERR)) {
				can_fit = 0;
				err->next = new_schd_error();
				prev_err = err;
				err = err->next;
			} else
				return 0;
		}
	}

	/* Check 2: v/scatter - If we're scattering or requesting exclusive nodes
	 * we know we need at least as many nodes as requested chunks */
	if (resresv->place_spec->scatter || resresv->place_spec->vscatter) {
		int nodect;
		enum sched_error error_code;
		enum schd_err_status status_code;
		if ( (flags & COMPARE_TOTAL) ) {
			nodect = np->tot_nodes;
			error_code = NO_TOTAL_NODES;
			status_code = NEVER_RUN;
		} else {
			nodect = np->free_nodes;
			error_code = NO_FREE_NODES;
			status_code = NOT_RUN;
		}

		if (nodect < resresv->select->total_chunks) {
			set_schd_error_codes(err, status_code, error_code);
			if ((flags & RETURN_ALL_ERR)) {
				can_fit = 0;
				err->next = new_schd_error();
				prev_err = err;
				err = err->next;
			} else
				return 0;
		}
	}

	/* Check 3: Job Wide RASSN resources(e.g., ncpus, mem).  We only check
	 * resources that the server has summed over the select statement.  We
	 * know these came from the nodes so should be checked on the nodes.  Other
	 * resources are for server/queue and so we ignore them here
	 */
	if (resresv->is_job && resresv->job != NULL && resresv->job->resreq_rel != NULL)
		req = resresv->job->resreq_rel;
	else
		req = resresv->resreq;
	if (check_avail_resources(np->res, req,
				pass_flags, policy->resdef_to_check_rassn_select,
				INSUFFICIENT_RESOURCE, err) == 0) {
		if ((flags & RETURN_ALL_ERR)) {
			can_fit = 0;
			err->next = new_schd_error();
			prev_err = err;
			err = err->next;
		} else
			return 0;
	}

	/* Check 4: Chunk level resources: Check each chunk compared to the meta data
	 *          This is mostly for non-consumables.  Booleans are always honored
	 *	      on nodes regardless if they are in the resources line.  This is a
	 *	      grandfathering in from the old nodespec properties.
	 */
	/* The call to get_resresv_spec is needed here because we are checking for resources on each
	 * chunk. For jobs that already have execselect specification defined we only need to
	 * traverse through those chunks.
	 * get_resresv_spec sets the spec value to execselect/select depending on whether execselect
	 * was set or not.
	 */
	get_resresv_spec(resresv, &spec, &pl);
	for (i = 0; spec->chunks[i] != NULL; i++) {
		if (check_avail_resources(np->res, spec->chunks[i]->req,
					pass_flags | CHECK_ALL_BOOLS, policy->resdef_to_check,
					INSUFFICIENT_RESOURCE, err) == 0) {
			if ((flags & RETURN_ALL_ERR)) {
				can_fit = 0;
				err->next = new_schd_error();
				prev_err = err;
				err = err->next;
			} else
				return 0;
		}
	}
	if((flags&RETURN_ALL_ERR)) {
		if(prev_err != NULL) {
			prev_err->next = NULL;
			free(err);
		}
		return can_fit;
	}
	return 1;
}

/**
 * @brief
 * 		create_specific_nodepart - create a node partition with specific
 *				          nodes, rather than from a placement
 *				          set resource=value
 *
 * @param[in]	policy	-	policy info
 * @param[in]	name	-	the name of the node partition
 * @param[in]	nodes	-	the nodes to create the placement set with
 *
 * @return	node_partition * - the node partition
 * @NULL	: on error
 */
node_partition *
create_specific_nodepart(status *policy, char *name, node_info **nodes)
{
	node_partition *np;
	int i, j;
	int cnt;

	if (name == NULL || nodes == NULL)
		return NULL;

	np = new_node_partition();
	if (np == NULL)
		return NULL;

	cnt = count_array((void **) nodes);

	np->name = string_dup(name);
	np->def = NULL;
	np->res_val = string_dup("none");
	np->rank = get_sched_rank();

	np->ninfo_arr = malloc((cnt + 1) * sizeof(node_info*));
	if (np->ninfo_arr == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		free_node_partition(np);
		return NULL;
	}

	j = 0;
	for (i = 0; i < cnt; i++) {
		if (!nodes[i]->is_stale) {
			np->ninfo_arr[j] = nodes[i];
			j++;
		}

	}
	np->tot_nodes = j;



	np->ninfo_arr[np->tot_nodes] = NULL;

	if (node_partition_update(policy, np) == 0) {
		free_node_partition(np);
		return NULL;
	}

	return np;
}


/**
 * @brief
 * 		create the placement sets for the server and queues
 *
 * @param[in]	policy	-	policy info
 * @param[in]	sinfo	-	the server
 *
 * @return	int
 * @retval	1	: success
 * @retval	0	: failure
 */
int
create_placement_sets(status *policy, server_info *sinfo)
{
	int i;
	int is_success = 1;
	char *resstr[] = {"host", NULL};
	int num;

	sinfo->allpart = create_specific_nodepart(policy, "all", sinfo->unassoc_nodes);
	if (sinfo->has_multi_vnode) {
		sinfo->hostsets = create_node_partitions(policy, sinfo->nodes,
			resstr, policy->only_explicit_psets ? NO_FLAGS : NP_CREATE_REST, &num);
		if (sinfo->hostsets != NULL) {
			sinfo->num_hostsets = num;
			for (i = 0; sinfo->nodes[i] != NULL; i++) {
				schd_resource *hostres;
				char hostbuf[256];

				hostres = find_resource(sinfo->nodes[i]->res, getallres(RES_HOST));
				if (hostres != NULL) {
					snprintf(hostbuf, sizeof(hostbuf), "host=%s", hostres->str_avail[0]);
					sinfo->nodes[i]->hostset =
						find_node_partition(sinfo->hostsets, hostbuf);
				}
				else {
					snprintf(hostbuf, sizeof(hostbuf), "host=\"\"");
					sinfo->nodes[i]->hostset =
						find_node_partition(sinfo->hostsets, hostbuf);
				}
			}
		}
		else {
			schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG, "",
				"Failed to create host sets for server");
			is_success = 0;
		}
	}

	if (sinfo->node_group_enable && sinfo->node_group_key != NULL) {
		sinfo->nodepart = create_node_partitions(policy, sinfo->unassoc_nodes,
			sinfo->node_group_key,
			policy->only_explicit_psets ? NO_FLAGS : NP_CREATE_REST,
			&sinfo->num_parts);

		if (sinfo->nodepart != NULL) {
			qsort(sinfo->nodepart, sinfo->num_parts,
				sizeof(node_partition *), cmp_placement_sets);
		}
		else {
			schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG, "",
				"Failed to create node partitions for server");
			is_success = 0;
		}
	}

	for (i = 0; sinfo->queues[i] != NULL; i++) {
		node_info **ngroup_nodes;
		char **ngkey;
		queue_info *qinfo = sinfo->queues[i];

		if (qinfo->has_nodes)
			qinfo->allpart = create_specific_nodepart(policy, "all", qinfo->nodes);

		if (sinfo->node_group_enable && (qinfo->has_nodes || qinfo->node_group_key)) {
			if (qinfo->has_nodes)
				ngroup_nodes = qinfo->nodes;
			else
				ngroup_nodes = sinfo->unassoc_nodes;

			if(qinfo->node_group_key)
				ngkey = qinfo->node_group_key;
			else
				ngkey = sinfo->node_group_key;

			qinfo->nodepart = create_node_partitions(policy, ngroup_nodes,
				ngkey, policy->only_explicit_psets ? NO_FLAGS : NP_CREATE_REST,
				&(qinfo->num_parts));
			if (qinfo->nodepart != NULL) {
				qsort(qinfo->nodepart, qinfo->num_parts,
					sizeof(node_partition *), cmp_placement_sets);
			}
			else {
				schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_QUEUE, LOG_DEBUG, qinfo->name,
					"Failed to create node partitions for queue.");
				is_success = 0;
			}
		}
	}
	return is_success;
}


/**
 *
 *	@brief update all node partitions of all queues on the server
 *	@note Call update_all_nodepart() after all nodes have been processed
 *		by update_node_on_end/update_node_on_run
 *
 *	  @param[in] policy - policy info
 *	  @param[in] sinfo - server info
 *	  @param[in] resresv- the job that was just run
 *	  @param[in] flags - flags to modify behavior
 *	  			NO_ALLPART - do not update the metadata in the allpart.
 *	  				     There are circumstances (e.g., calendaring) where
 *	  				     the allpart provides limited use and will constantly
 *	  				     be updated.  It is best to just skip it.
 *
 *	@return nothing
 *
 */
void
update_all_nodepart(status *policy, server_info *sinfo, resource_resv *resresv, unsigned int flags)
{
	queue_info *qinfo;
	int update_allpart = 1;
	int i;

	if (sinfo == NULL || sinfo->queues == NULL || resresv == NULL)
		return;

	if(sinfo->allpart == NULL)
		return;

	if (sinfo->node_group_enable && sinfo->node_group_key != NULL) {
		node_partition_update_array(policy, sinfo->nodepart, resresv->ninfo_arr);
		qsort(sinfo->nodepart, sinfo->num_parts,
			sizeof(node_partition *), cmp_placement_sets);
	}

	/* Update and resort the placement sets on the queues */
	for (i = 0; sinfo->queues[i] != NULL; i++) {
		qinfo = sinfo->queues[i];

		if (sinfo->node_group_enable && qinfo->node_group_key != NULL) {
			node_partition_update_array(policy, qinfo->nodepart, resresv->ninfo_arr);

			qsort(qinfo->nodepart, qinfo->num_parts,
			   sizeof(node_partition *), cmp_placement_sets);
		}
		if ((flags & NO_ALLPART) == 0) {
			if(qinfo->allpart != NULL && qinfo->allpart->res == NULL)
				node_partition_update(policy, qinfo->allpart);
		}
	}

	/* Update and resort the hostsets */
	node_partition_update_array(policy, sinfo->hostsets, NULL);
	if (policy->node_sort[0].res_name != NULL &&
	    conf.node_sort_unused && sinfo->hostsets != NULL) {
		/* Resort the nodes in host sets to correctly reflect unused resources */
		qsort(sinfo->hostsets, sinfo->num_hostsets, sizeof(node_partition*), multi_nodepart_sort);
	}

	if ((flags & NO_ALLPART) == 0) {
		/* If the job is in a queue with nodes, we only need to update
		 * the allpart of that queue.  This has already happened above.
		 * */
		if (resresv != NULL && resresv ->is_job) {
			if (resresv->job != NULL)
				if (resresv->job->queue->has_nodes)
					update_allpart = 0;
		}

		/* Otherwise, update the server's allpart */
		if (update_allpart || sinfo->allpart->res == NULL)
			node_partition_update(policy, sinfo->allpart);
	}

}

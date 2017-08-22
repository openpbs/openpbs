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
 * @file    node_info.c
 *
 * @brief
 * 		misc.c - This file contains functions related to node_info structure.
 *
 * Functions included are:
 * 	query_nodes()
 * 	query_node_info()
 * 	new_node_info()
 * 	free_nodes()
 * 	free_node_info()
 * 	set_node_type()
 * 	set_node_info_state()
 * 	remove_node_state()
 * 	add_node_state()
 * 	talk_with_mom()
 * 	node_filter()
 * 	find_node_info()
 * 	find_node_by_host()
 * 	dup_nodes()
 * 	dup_node_info()
 * 	copy_node_ptr_array()
 * 	collect_resvs_on_nodes()
 * 	collect_jobs_on_nodes()
 * 	update_node_on_run()
 * 	update_node_on_end()
 * 	should_talk_with_mom()
 * 	check_rescspec()
 * 	search_for_rescspec()
 * 	new_nspec()
 * 	free_nspec()
 * 	dup_nspec()
 * 	empty_nspec_array()
 * 	free_nspecs()
 * 	find_nspec()
 * 	find_nspec_by_rank()
 * 	eval_selspec()
 * 	eval_placement()
 * 	eval_complex_selspec()
 * 	eval_simple_selspec()
 * 	is_vnode_eligible()
 * 	is_vnode_eligible_chunk()
 * 	resources_avail_on_vnode()
 * 	check_resources_for_node()
 * 	parse_placespec()
 * 	parse_selspec()
 * 	create_execvnode()
 * 	parse_execvnode()
 * 	node_state_to_str()
 * 	combine_nspec_array()
 * 	create_node_array_from_nspec()
 * 	reorder_nodes()
 * 	reorder_nodes_set()
 * 	ok_break_chunk()
 * 	is_excl()
 * 	alloc_rest_nodepart()
 * 	set_res_on_host()
 * 	update_mom_resources()
 * 	can_fit_on_vnode()
 * 	is_aoe_avail_on_vnode()
 * 	is_provisionable()
 * 	node_up_event()
 * 	node_down_event()
 * 	node_in_str()
 * 	create_node_array_from_str()
 * 	find_node_by_rank()
 * 	new_node_scratch()
 * 	free_node_scratch()
 * 	sim_exclhost()
 * 	sim_exclhost_func()
 * 	set_current_aoe()
 * 	is_exclhost()
 * 	check_node_array_eligibility()
 * 	is_powerok()
 * 	is_eoe_avail_on_vnode()
 * 	set_current_eoe()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <sys/types.h>
#include <errno.h>
#include <math.h>
#include <errno.h>
#include <pbs_ifl.h>
#include <log.h>
#include <rm.h>
#include <grunt.h>
#include <libutil.h>
#include <pbs_internal.h>
#include "node_info.h"
#include "server_info.h"
#include "job_info.h"
#include "misc.h"
#include "globals.h"
#include "check.h"
#include "constant.h"
#include "config.h"
#include "resource_resv.h"
#include "simulate.h"
#include "sort.h"
#include "node_partition.h"
#include "resource.h"
#include "pbs_internal.h"
#include "server_info.h"
#include "pbs_share.h"
#ifdef NAS
#include "site_code.h"
#endif


/* name of the last node a job ran on - used in smp_dist = round robin */
static char last_node_name[PBS_MAXSVRJOBID];

/**
 * @brief
 *      query_nodes - query all the nodes associated with a server
 *
 * @param[in]	pbs_sd	-	communication descriptor wit the pbs server
 * @param[in,out]	sinfo	-	server information
 *
 * @return	array of nodes associated with server
 *
 */
node_info **
query_nodes(int pbs_sd, server_info *sinfo)
{
	struct batch_status *nodes;		/* nodes returned from the server */
	struct batch_status *cur_node;	/* used to cycle through nodes */
	node_info **ninfo_arr;		/* array of nodes for scheduler's use */
	node_info *ninfo;			/* used to set up a node */
	char errbuf[256];
	char *err;				/* used with pbs_geterrmsg() */
	int num_nodes = 0;			/* the number of nodes */
	int i;
	extern char *partitions;

	/* get nodes from PBS server */
	if ((nodes = pbs_statvnode(pbs_sd, NULL, NULL, partitions)) == NULL) {
		err = pbs_geterrmsg(pbs_sd);
		sprintf(errbuf, "Error getting nodes: %s", err);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO, "", errbuf);
		return NULL;
	}

	cur_node = nodes;
	while (cur_node != NULL) {
		num_nodes++;
		cur_node = cur_node->next;
	}

	if ((ninfo_arr = (node_info **) malloc((num_nodes + 1) * sizeof(node_info *))) == NULL) {
		log_err(errno, "query_nodes", "Error allocating memory");
		pbs_statfree(nodes);
		return NULL;
	}
	ninfo_arr[0] = NULL;

#ifdef NAS /* localmod 049 */
	if ((sinfo->nodes_by_NASrank = (node_info **) malloc(num_nodes * sizeof(node_info *))) == NULL) {
		log_err(errno, "query_nodes", "Error allocating nodes_by_NASrank memory");
		pbs_statfree(nodes);
		free_nodes(ninfo_arr);
		return NULL;
	}
#endif /* localmod 049 */

	cur_node = nodes;
	for (i = 0; cur_node != NULL; i++) {
		/* get node info from server */
		if ((ninfo = query_node_info(cur_node, sinfo)) == NULL) {
			pbs_statfree(nodes);
			free_nodes(ninfo_arr);
			return NULL;
		}

#ifdef NAS /* localmod 049 */
		ninfo->NASrank = i;
		sinfo->nodes_by_NASrank[i] = ninfo;
#endif /* localmod 049 */

		ninfo->rank = get_sched_rank();

		/* get node info from mom */
		if (talk_with_mom(ninfo)) {
			/* failed to get information from node, mark it not free for this cycle */
			ninfo->is_free = 0;
			ninfo->is_offline = 1;
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO, ninfo->name,
				"Failed to talk with mom, marking node offline");
		}

		ninfo_arr[i] = ninfo;

		cur_node = cur_node->next;
	}
	ninfo_arr[i] = NULL;

	if (update_mom_resources(ninfo_arr) == 0) {
		pbs_statfree(nodes);
		free_nodes(ninfo_arr);
		return NULL;
	}

#ifdef NAS /* localmod 062 */
	site_vnode_inherit(ninfo_arr);
#endif /* localmod 062 */
	resolve_indirect_resources(ninfo_arr);
	sinfo->num_nodes = num_nodes;
	pbs_statfree(nodes);
	return ninfo_arr;
}

/**
 * @brief
 *      query_node_info	- collect information from a batch_status and
 *      put it in a node_info struct for easier access
 *
 * @param[in]	node	-	a node returned from a pbs_statvnode() call
 * @param[in,out]	sinfo	-	server information
 *
 * @return	a node_info filled with information from node
 *
 */
node_info *
query_node_info(struct batch_status *node, server_info *sinfo)
{
	node_info *ninfo;		/* the new node_info */
	struct attrl *attrp;		/* used to cycle though attribute list */
	schd_resource *res;		/* used to set resources in res list */
	sch_resource_t count;		/* used to convert str->num */
	char *endp;			/* end pointer for strtol */
	char logbuf[256];		/* log buffer */

	if ((ninfo = new_node_info()) == NULL)
		return NULL;

	attrp = node->attribs;

	if ((ninfo->name = string_dup(node->name)) == NULL) {
		free_node_info(ninfo);
		return NULL;
	}

	ninfo->server = sinfo;

	while (attrp != NULL) {
		/* Node State... i.e. offline down free etc */
		if (!strcmp(attrp->name, ATTR_NODE_state))
			set_node_info_state(ninfo, attrp->value);

		/* Host name */
		else if (!strcmp(attrp->name, ATTR_NODE_Mom)) {
			if (ninfo->mom)
				free(ninfo->mom);
			if ((ninfo->mom = string_dup(attrp->value)) == NULL) {
				free_node_info(ninfo);
				return NULL;
			}
		}
		/* TCP port for mom/server communication
		 * we need the resource monitor port which is
		 * defined as mom/server port + 1
		 */
		else if (!strcmp(attrp->name, ATTR_NODE_Port)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp == '\0')
				ninfo->port = count + 1;
		}
		else if (!strcmp(attrp->name, ATTR_NODE_jobs))
			ninfo->jobs = break_comma_list(attrp->value);

		/* the node type... i.e. a pbs node  */
		else if (!strcmp(attrp->name, ATTR_NODE_ntype))
			set_node_type(ninfo, attrp->value);
		else if (!strcmp(attrp->name, ATTR_maxrun)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp == '\0')
				ninfo->max_running = count;
		}
		else if (!strcmp(attrp->name, ATTR_maxuserrun)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp == '\0')
				ninfo->max_user_run = count;
			ninfo->has_hard_limit = 1;
		}
		else if (!strcmp(attrp->name, ATTR_maxgrprun)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp == '\0')
				ninfo->max_group_run = count;
			ninfo->has_hard_limit = 1;
		}
		else if (!strcmp(attrp->name, ATTR_queue))
			ninfo->queue_name = string_dup(attrp->value);
		else if (!strcmp(attrp->name, ATTR_NODE_pcpus)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp == '\0')
				ninfo->pcpus = count;
		}
		else if (!strcmp(attrp->name, ATTR_p)) {
			count = strtol(attrp->value, &endp, 10);
			if (*endp == '\0')
				ninfo->priority = count;
		}
		else if (!strcmp(attrp->name, ATTR_NODE_Sharing)) {
			ninfo->sharing = str_to_vnode_sharing(attrp->value);
			if (ninfo->sharing == VNS_UNSET) {
				sprintf(logbuf, "Unknown sharing type: %s using default shared", attrp->value);
				schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
					ninfo->name, logbuf);
				ninfo->sharing = VNS_DFLT_SHARED;
			}
		}
		else if (!strcmp(attrp->name, ATTR_NODE_License)) {
			switch (attrp->value[0]) {
				case ND_LIC_TYPE_locked:
					ninfo->lic_lock = 1;
					sinfo->has_nonCPU_licenses = 1;
					break;
				default:
					sprintf(logbuf, "Unknown license type: %c", attrp->value[0]);
					schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
						ninfo->name, logbuf);
			}
		} else if (!strcmp(attrp->name, ATTR_rescavail)) {
			res = find_alloc_resource_by_str(ninfo->res, attrp->resource);

			if (res != NULL) {
				if (ninfo->res == NULL)
					ninfo->res = res;

				if (set_resource(res, attrp->value, RF_AVAIL) == 0) {
					free_node_info(ninfo);
					ninfo = NULL;
					break;
				}
#ifdef NAS /* localmod 034 */
				site_set_node_share(ninfo, res);
#endif /* localmod 034 */
			}
		} else if (!strcmp(attrp->name, ATTR_rescassn)) {
			res = find_alloc_resource_by_str(ninfo->res, attrp->resource);

			if (ninfo->res == NULL)
				ninfo->res = res;
			if (res != NULL) {
				if (set_resource(res, attrp->value, RF_ASSN) == 0) {
					free_node_info(ninfo);
					ninfo = NULL;
					break;
				}
			}
		} else if (!strcmp(attrp->name, ATTR_NODE_NoMultiNode)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				ninfo->no_multinode_jobs = 1;
		}
		else if (!strcmp(attrp->name, ATTR_ResvEnable)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				ninfo->resv_enable = 1;
		}
		else if (!strcmp(attrp->name, ATTR_NODE_ProvisionEnable)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				ninfo->provision_enable = 1;
		}
		else if (!strcmp(attrp->name, ATTR_NODE_current_aoe)) {
			if (attrp->value != NULL)
				set_current_aoe(ninfo, attrp->value);
		}
		else if (!strcmp(attrp->name, ATTR_NODE_power_provisioning)) {
			if (!strcmp(attrp->value, ATR_TRUE))
				ninfo->power_provisioning = 1;
		}
		else if (!strcmp(attrp->name, ATTR_NODE_current_eoe)) {
			if (attrp->value != NULL)
				set_current_eoe(ninfo, attrp->value);
		}
		else if (!strcmp(attrp->name, ATTR_NODE_in_multivnode_host)) {
			if (attrp->value != NULL) {
				count = strtol(attrp->value, &endp, 10);
				if (*endp == '\0')
					ninfo->is_multivnoded = count;
				if ((!sinfo->has_multi_vnode) && (count != 0))
					sinfo->has_multi_vnode = 1;
			}
		}
		attrp = attrp->next;
	}
	return ninfo;
}

/**
 * @brief
 *      new_node_info - allocates a new node_info
 *
 * @return	the new node_info
 *
 */
node_info *
new_node_info()
{
	node_info *new;

	if ((new = (node_info *) malloc(sizeof(node_info))) == NULL) {
		log_err(errno, "new_node_info", MEM_ERR_MSG);
		return NULL;
	}

	new->is_down = 0;
	new->is_free = 0;
	new->is_offline = 0;
	new->is_unknown = 0;
	new->is_exclusive = 0;
	new->is_job_exclusive = 0;
	new->is_resv_exclusive = 0;
	new->is_sharing = 0;
	new->is_pbsnode = 0;
	new->is_busy = 0;
	new->is_job_busy = 0;
	new->is_stale = 0;
	new->is_provisioning = 0;
	new->is_multivnoded = 0;
	new->has_ghost_job = 0;

	new->lic_lock = 0;

	new->has_hard_limit = 0;
	new->no_multinode_jobs = 0;
	new->resv_enable = 0;
	new->provision_enable = 0;
	new->power_provisioning = 0;

	new->sharing = VNS_DFLT_SHARED;

	new->num_jobs = 0;
	new->num_run_resv = 0;
	new->num_susp_jobs = 0;

	new->priority = 0;

	new->pcpus = 0;

	new->rank = 0;

	new->nodesig_ind = -1;

	new->name = NULL;
	new->mom = NULL;
	new->port = pbs_rm_port;
	new->jobs = NULL;
	new->job_arr = NULL;
	new->run_resvs_arr = NULL;
	new->res = NULL;
	new->server = NULL;
	new->queue_name = NULL;
	new->group_counts = NULL;
	new->user_counts = NULL;

	new->max_load = 0.0;
	new->ideal_load = 0.0;
	new->loadave = 0.0;

	new->max_running = SCHD_INFINITY;
	new->max_user_run = SCHD_INFINITY;
	new->max_group_run = SCHD_INFINITY;

	new->current_aoe = NULL;
	new->current_eoe = NULL;
	new->nodesig = NULL;

	new->svr_node = NULL;
	new->hostset = NULL;

	memset(&new->nscr, 0, sizeof(node_scratch));

#ifdef NAS
	/* localmod 034 */
	new->sh_type = 0;
	new->sh_cls = 0;
	/* localmod 049 */
	new->NASrank = -1;
#endif
	return new;
}

/**
 * @brief
 *		free_nodes - free all the nodes in a node_info array
 *
 * @param[in,out]	ninfo_arr - the node info array
 *
 * @return	nothing
 *
 */
void
free_nodes(node_info **ninfo_arr)
{
	int i;

	if (ninfo_arr != NULL) {
		for (i = 0; ninfo_arr[i] != NULL; i++)
			free_node_info(ninfo_arr[i]);

		free(ninfo_arr);
	}
}

/**
 * @brief
 *      free_node_info - frees memory used by a node_info
 *
 * @param[in,out]	ninfo	-	the node to free
 *
 * @return	nothing
 *
 */
void
free_node_info(node_info *ninfo)
{
	if (ninfo != NULL) {
		if (ninfo->name != NULL)
			free(ninfo->name);

		if (ninfo->mom != NULL)
			free(ninfo->mom);

		if (ninfo->queue_name != NULL)
			free(ninfo->queue_name);

		if (ninfo->jobs != NULL)
			free_string_array(ninfo->jobs);

		if (ninfo->job_arr != NULL)
			free(ninfo->job_arr);

		if (ninfo->run_resvs_arr != NULL)
			free(ninfo->run_resvs_arr);

		if (ninfo->res != NULL)
			free_resource_list(ninfo->res);

		if (ninfo->group_counts != NULL)
			free_counts_list(ninfo->group_counts);

		if (ninfo->user_counts != NULL)
			free_counts_list(ninfo->user_counts);

		if (ninfo->current_aoe != NULL)
			free(ninfo->current_aoe);

		if (ninfo->current_eoe != NULL)
			free(ninfo->current_eoe);

		if (ninfo->nodesig != NULL)
			free(ninfo->nodesig);

		free(ninfo);
	}
}

/**
 * @brief
 *		set_node_type - set the node type bits
 *
 * @param[in,out]	ninfo	-	the node to set the type
 * @param[in]	ntype	-	the type string from the server
 *
 * @return	non-zero	: on error
 *
 */
int
set_node_type(node_info *ninfo, char *ntype)
{
	char errbuf[256];

	if (ntype != NULL && ninfo != NULL) {
		if (!strcmp(ntype, ND_pbs))
			ninfo->is_pbsnode = 1;
		else {
			sprintf(errbuf, "Unknown node type: %s", ntype);
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
				ninfo->name, errbuf);
			return 1;
		}
		return 0;
	}
	return 1;
}

/**
 * @brief
 * 		set the node state info bits from a single or comma separated list of
 * 		states.
 *
 * @param[in]	ninfo	-	the node to set the state
 * @param[in]	state	-	the state string from the server
 *
 * @retval	0	: on success
 * @retval	1	: on failure
 */
int
set_node_info_state(node_info *ninfo, char *state)
{
	char errbuf[256];
	char statebuf[256];			/* used to strtok() node states */
	char *tok;				/* used with strtok() */

	if (ninfo != NULL && state != NULL) {
		/* clear all states */
		ninfo->is_down = ninfo->is_free = ninfo->is_unknown = 0;
		ninfo->is_sharing = ninfo->is_busy = ninfo->is_job_busy = 0;
		ninfo->is_stale = ninfo->is_provisioning = ninfo->is_exclusive = 0;
		ninfo->is_resv_exclusive = ninfo->is_job_exclusive = 0;

		strcpy(statebuf, state);
		tok = strtok(statebuf, ",");

		while (tok != NULL) {
			while (isspace((int) *tok))
				tok++;

			if (add_node_state(ninfo, tok) == 1) {
				sprintf(errbuf, "Unknown Node State: %s", tok);
				schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
					ninfo->name, errbuf);
			}

			tok = strtok(NULL, ",");
		}
		return 0;
	}

	return 1;
}

/**
 * @brief
 * 		Remove a node state
 *
 * @param[in]	node	-	The node being considered
 * @param[in]	state	-	The state to remove
 *
 * @par Side-Effects:
 * 		Handles node exclusivity in a special way.
 * 		If handling resv-exclusive, unset is_exclusive along
 * 		If handling job-exclusive, unset is_exclusive only if resv-exclusive isn't
 * 		set.
 *
 * @retval	0	: on success
 * @retval	1	: on failure
 */
int
remove_node_state(node_info *ninfo, char *state)
{
	char errbuf[256];

	if (!strcmp(state, ND_down))
		ninfo->is_down = 0;
	else if (!strcmp(state, ND_free))
		ninfo->is_free = 0;
	else if (!strcmp(state, ND_offline))
		ninfo->is_offline = 0;
	else if (!strcmp(state, ND_state_unknown))
		ninfo->is_unknown = 0;
	else if (!strcmp(state, ND_job_exclusive)) {
		ninfo->is_job_exclusive = 0;
		if (ninfo->is_resv_exclusive == 0)
			ninfo->is_exclusive = 0;
	}
	else if (!strcmp(state, ND_resv_exclusive)) {
		ninfo->is_resv_exclusive = 0;
		if (ninfo->is_job_exclusive == 0)
			ninfo->is_exclusive = 0;
	}
	else if (!strcmp(state, ND_job_sharing))
		ninfo->is_sharing = 0;
	else if (!strcmp(state, ND_busy))
		ninfo->is_busy = 0;
	else if (!strcmp(state, ND_jobbusy))
		ninfo->is_job_busy = 0;
	else if (!strcmp(state, ND_Stale))
		ninfo->is_stale = 0;
	else if (!strcmp(state, ND_prov))
		ninfo->is_provisioning = 0;
	else if (!strcmp(state, ND_wait_prov))
		ninfo->is_provisioning = 0;
	else {
		sprintf(errbuf, "Unknown Node State: %s on remove operation", state);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
			ninfo->name, errbuf);
		return 1;
	}

	/* If all state bits are turned off, the node state must be free */
	if (!ninfo->is_free && !ninfo->is_busy && !ninfo->is_exclusive
		&& !ninfo->is_job_exclusive && !ninfo->is_resv_exclusive
		&& !ninfo->is_offline && !ninfo->is_job_busy && !ninfo->is_stale
		&& !ninfo->is_provisioning && !ninfo->is_sharing
		&& !ninfo->is_unknown  && !ninfo->is_down)
		ninfo->is_free = 1;

	return 0;
}

/**
 * @brief
 * 		Add a node state
 *
 * @param[in]	node	-	The node being considered
 * @param[in]	state	-	The state to add
 *
 * @par Side-Effects:
 * 		Handle node exclusivity in a special way.
 * 		If handling resv-exclusive or job-exclusive, turn is_exclusive bit on.
 *
 * @retval	0	: on success
 * @retval	1	: on failure
 */
int
add_node_state(node_info *ninfo, char *state)
{
	char errbuf[256];
	int set_free = 0;

	if (!strcmp(state, ND_down))
		ninfo->is_down = 1;
	else if (!strcmp(state, ND_free)) {
		ninfo->is_free = 1;
		set_free = 1;
	}
	else if (!strcmp(state, ND_offline))
		ninfo->is_offline = 1;
	else if (!strcmp(state, ND_state_unknown) || !strcmp(state, ND_unresolvable))
		ninfo->is_unknown = 1;
	else if (!strcmp(state, ND_job_exclusive)) {
		ninfo->is_job_exclusive = 1;
		ninfo->is_exclusive = 1;
	}
	else if (!strcmp(state, ND_resv_exclusive)) {
		ninfo->is_resv_exclusive = 1;
		ninfo->is_exclusive = 1;
	}
	else if (!strcmp(state, ND_job_sharing))
		ninfo->is_sharing = 1;
	else if (!strcmp(state, ND_busy))
		ninfo->is_busy = 1;
	else if (!strcmp(state, ND_jobbusy))
		ninfo->is_job_busy = 1;
	else if (!strcmp(state, ND_Stale))
		ninfo->is_stale = 1;
	else if (!strcmp(state, ND_prov))
		ninfo->is_provisioning = 1;
	else if (!strcmp(state, ND_wait_prov))
		ninfo->is_provisioning = 1;
	else {
		sprintf(errbuf, "Unknown Node State: %s on add operation", state);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
			ninfo->name, errbuf);
		return 1;
	}

	/* Remove the free state unless it was specifically the state being added */
	if (!set_free)
		ninfo->is_free = 0;

	return 0;
}

/**
 * @brief
 *      talk_with_mom - talk to mom and get resources
 *
 * @param[in,out]	ninfo	-	the node to to talk to its mom
 *
 * @return	int
 * @return	1	: on error
 * @return	0	: on success
 *
 */
int
talk_with_mom(node_info *ninfo)
{
	int mom_sd;			/* connection descriptor to mom */
	int ret = 0;			/* return code of this function */
	char *mom_ans = NULL;		/* the answer from mom - getreq() */
	char *endp;			/* used with strtol() */
	double testd;			/* used to convert string->double */
	schd_resource *res;                /* used for dynamic resources from mom */
	int ncpus = 1;		/* used as a default for loads */
	char errbuf[MAX_LOG_SIZE];
	int i;

	if (!should_talk_with_mom(ninfo))
		return 0;

	schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_NODE, LOG_DEBUG, ninfo->name,
		"Initiating communication with mom");
	if ((mom_sd = openrm(ninfo->mom, ninfo->port)) < 0) {
		schdlog(PBSEVENT_SYSTEM, PBS_EVENTCLASS_REQUEST, LOG_INFO, ninfo->name,
			"Cannot open connection to mom");
		return 1;
	}

	for (i = 0; i < num_resget; i++)
		addreq(mom_sd, (char *) res_to_get[i]);

	if (conf.dyn_res_to_get) {
		for (i = 0; conf.dyn_res_to_get[i]; i++)
			addreq(mom_sd, (char *) conf.dyn_res_to_get[i]);
	}

	if ((res = find_resource(ninfo->res, getallres(RES_NCPUS))))
		ncpus = res->avail;

	for (i = 0; i < num_resget && (mom_ans = getreq(mom_sd)); i++) {
		if (!strcmp(res_to_get[i], "max_load")) {
			testd = strtod(mom_ans, &endp);
			if (*endp == '\0')
				ninfo->max_load = testd;
			else
				ninfo->max_load = ncpus;
		}
		else if (!strcmp(res_to_get[i], "ideal_load")) {
			testd = strtod(mom_ans, &endp);
			if (*endp == '\0')
				ninfo->ideal_load = testd;
			else
				ninfo->ideal_load = ncpus;
		}
		else if (!strcmp(res_to_get[i], "loadave")) {
			testd = strtod(mom_ans, &endp);
			if (*endp == '\0')
				ninfo->loadave = testd;
			else
				ninfo->loadave = -1.0;
		}
		else {
			sprintf(errbuf, "Unknown resource value[%d]: %s", i, mom_ans);
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_INFO,
				ninfo->name, errbuf);
		}
		free(mom_ans);
		mom_ans = NULL;
	}

	/* getreq() returned NULL and we bailed out of the loop */
	if (i < num_resget) {
		ret = 1;
		schdlog(PBSEVENT_SYSTEM, PBS_EVENTCLASS_REQUEST, LOG_INFO, ninfo->name,
			"Communications problem talking with mom.");
	}

	if (mom_ans)
		free(mom_ans);
	mom_ans = NULL;

	if (ret == 0 && conf.dyn_res_to_get) {
		for (i = 0; conf.dyn_res_to_get[i] && (mom_ans = getreq(mom_sd));  i++) {
			res = find_alloc_resource_by_str(ninfo->res, conf.dyn_res_to_get[i]);
			if (res != NULL) {
				if (mom_ans[0] != '?') {
					if (set_resource(res, mom_ans, RF_AVAIL) == 0) {
						ret = 1;
						break;
					}
				}
				else if (res->avail == SCHD_INFINITY)
					res->avail = 0;

				snprintf(errbuf, sizeof(errbuf), "%s = %s (\"%s\")",
					res->name, res_to_str(res, RF_AVAIL), mom_ans);
				schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_NODE, LOG_DEBUG,
					"mom_resources", errbuf);
			}
			free(mom_ans);
			mom_ans = NULL;
		}
		if (conf.dyn_res_to_get[i]) {
			ret = 1;
			schdlog(PBSEVENT_SYSTEM, PBS_EVENTCLASS_REQUEST, LOG_INFO, ninfo->name,
				"Communications problem talking with mom.");
		}
	}
	if (mom_ans)
		free(mom_ans);
	mom_ans = NULL;

	closerm(mom_sd);
	schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_NODE, LOG_DEBUG, ninfo->name,
		"Ended communication with mom");
	return (ret);
}
/**
 * @brief
 *		node_filter - filter a node array and return a new filterd array
 *
 * @param[in]	nodes	-	the array to filter
 * @param[in]	size	-	size of nodes (<0 for function to figure it out)
 * @param[in]	filter_func	-	pointer to a function that will filter the nodes
 *								- returns 1: job will be added to filtered array
 *								- returns 0: job will NOT be added to filtered array
 *	  							arg - an optional arg passed to filter_func
 *	  							flags - describe how nodes are filtered
 *
 * @return pointer to filtered array
 *
 * @par
 * filter_func prototype: int func( node_info *, void * )
 *
 */
node_info **
node_filter(node_info **nodes, int size,
	int (*filter_func)(node_info*, void*), void *arg, int flags)
{
	node_info **new_nodes = NULL;			/* the new node array */
	node_info **new_nodes_tmp = NULL;
	int i, j;

	if (size < 0)
		size = count_array((void **) nodes);

	if ((new_nodes = (node_info **) malloc((size + 1) * sizeof(node_info *))) == NULL) {
		log_err(errno, "node_filter", "Error allocating memory");
		return NULL;
	}

	for (i = 0, j = 0; i < size; i++) {
		if (filter_func(nodes[i], arg)) {
			new_nodes[j] = nodes[i];
			j++;
		}
	}
	new_nodes[j] = NULL;

	if (!(flags & FILTER_FULL)) {
		if ((new_nodes_tmp = (node_info **) realloc(new_nodes, (j+1) * sizeof(node_info *))) == NULL)
			log_err(errno, "node_filter", "Error allocating memory");
		else
			new_nodes = new_nodes_tmp;
	}
	return new_nodes;
}

/**
 * @brief
 *		find_node_info - find a node in a node array
 *
 * @param[in]	nodename	-	the node to find
 * @param[in]	ninfo_arr	-	the array of nodes to look in
 *
 * @return	the node
 * @retval	NULL	: if not found
 *
 */
node_info *
find_node_info(node_info **ninfo_arr, char *nodename)
{
	int i;

	if (nodename == NULL || ninfo_arr == NULL)
		return NULL;

	for (i = 0; ninfo_arr[i] != NULL &&
		strcmp(nodename, ninfo_arr[i]->name) ; i++)
		;

	return ninfo_arr[i];
}

/**
 * @brief
 *		find_node_by_host - find a node by its host resource rather then
 *				its name -- will return first found vnode
 *
 * @param[in]	ninfo_arr	-	array of nodes to search
 * @param[in]	host	-	host of node to find
 *
 * @return	found node
 * @retval	NULL	: not found
 *
 */
node_info *
find_node_by_host(node_info **ninfo_arr, char *host)
{
	int i;
	schd_resource *res;

	if (ninfo_arr == NULL || host == NULL)
		return NULL;

	for (i = 0; ninfo_arr[i] != NULL; i++) {
		res = find_resource(ninfo_arr[i]->res, getallres(RES_HOST));
		if (res != NULL) {
			if (compare_res_to_str(res, host, CMP_CASELESS))
				break;
		}
	}

	return ninfo_arr[i];
}

/**
 * @brief
 *		dup_nodes - duplicate an array of nodes
 *
 * @param[in]	onodes	-	the array to duplicate
 * @param[in]	nsinfo	-	the new server
 * @param[in]	flags	-	DUP_INDIRECT - duplicate
 * 				 			target resources, not indirect
 *
 * @return the duplicated array
 * @retval	NULL	: on error
 *
 */
#ifdef NAS /* localmod 049 */
node_info **
dup_nodes(node_info **onodes, server_info *nsinfo,
	unsigned int flags, int allocNASrank)
#else
node_info **
dup_nodes(node_info **onodes, server_info *nsinfo,
	unsigned int flags)
#endif /* localmod 049 */
{
	node_info **nnodes;
	int num_nodes;
	int i, j;
	schd_resource *nres = NULL;
	schd_resource *ores = NULL;
	schd_resource *tres = NULL;
	node_info *ninfo = NULL;
	char namebuf[1024];

	if (onodes == NULL || nsinfo == NULL)
		return NULL;

	num_nodes = nsinfo->num_nodes;

	if ((nnodes = (node_info **) malloc((num_nodes + 1) * sizeof(node_info *))) == NULL) {
		log_err(errno, "dup_nodes", MEM_ERR_MSG);
		return NULL;
	}

#ifdef NAS /* localmod 049 */
	if (allocNASrank &&
		(nsinfo->nodes_by_NASrank = (node_info **) malloc(num_nodes * sizeof(node_info *))) == NULL) {
		log_err(errno, "dup_nodes", MEM_ERR_MSG);
		free_nodes(nnodes);
		return NULL;
	}
#endif /* localmod 049 */

	for (i = 0; onodes[i] != NULL; i++) {
		if ((nnodes[i] = dup_node_info(onodes[i], nsinfo, flags)) == NULL) {
			free_nodes(nnodes);
			return NULL;
		}

#ifdef NAS /* localmod 049 */
		if (allocNASrank) {
			nnodes[i]->NASrank = onodes[i]->NASrank;
			nsinfo->nodes_by_NASrank[onodes[i]->NASrank] = nnodes[i];
		}
#endif /* localmod 049 */
	}
	nnodes[i] = NULL;

	if (!(flags & DUP_INDIRECT)) {
		for (i = 0; nnodes[i] != NULL; i++) {
			/* since the node list we're duplicating may have indirect resources
			 * which point to resources not in our node list, we need to detect it
			 * if we are in this case, we'll redirect them locally
			 */
			nres = nnodes[i]->res;
			while (nres != NULL) {
				if (nres->indirect_vnode_name != NULL) {
					ninfo = find_node_info(nnodes, nres->indirect_vnode_name);
					/* we found the problem -- first time we see it, we set the value
					 * of THIS node to the indirect value.  We'll then set all the rest
					 * to point to THIS node.
					 */
					if (ninfo == NULL) {
						ninfo = find_node_info(onodes, nnodes[i]->name);
						ores = find_resource(ninfo->res, nres->def);
						if (ores->indirect_res != NULL) {
							sprintf(namebuf, "@%s", nnodes[i]->name);
							for (j = i+1; nnodes[j] != NULL; j++) {
								tres = find_resource(nnodes[j]->res, nres->def);
								if (tres != NULL) {
									if (tres->indirect_vnode_name != NULL &&
										!strcmp(nres->indirect_vnode_name,
										nres->indirect_vnode_name)) {
										if (set_resource(tres, namebuf, RF_AVAIL) == 0) {
											free_nodes(nnodes);
											return NULL;
										}
									}
								}
							}
							if (set_resource(nres,
								ores->indirect_res->orig_str_avail, RF_AVAIL) ==0) {
								free_nodes(nnodes);
								return NULL;
							}
							nres->assigned = ores->indirect_res->assigned;
						}
					}
				}
				nres = nres->next;
			}
		}
	}

	if (resolve_indirect_resources(nnodes) == 0) {
		free_nodes(nnodes);
		return NULL;
	}
	return nnodes;
}

/**
 * @brief
 *		dup_node_info - duplicate a node by creating a new one and coping all
 *		        the data into the new
 *
 * @param[in]	onode	-	the node to dup
 * @param[in]	nsinfo	-	the NEW server (i.e. duplicated)
 * @param[in]	flags	-	DUP_INDIRECT - duplicate target resources, not indirect
 *
 * @return	newly allocated and duped node
 *
 */
node_info *
dup_node_info(node_info *onode, server_info *nsinfo,
	unsigned int flags)
{
	node_info *nnode;

	if (onode == NULL)
		return NULL;

	if ((nnode = new_node_info()) == NULL)
		return NULL;

	nnode->server = nsinfo;
	nnode->name = string_dup(onode->name);
	nnode->mom = string_dup(onode->mom);
	nnode->queue_name = string_dup(onode->queue_name);

	nnode->is_down = onode->is_down;
	nnode->is_free = onode->is_free;
	nnode->is_offline = onode->is_offline;
	nnode->is_unknown = onode->is_unknown;
	nnode->is_exclusive = onode->is_exclusive;
	nnode->is_job_exclusive = onode->is_job_exclusive;
	nnode->is_resv_exclusive = onode->is_resv_exclusive;
	nnode->is_sharing = onode->is_sharing;
	nnode->is_busy = onode->is_busy;
	nnode->is_pbsnode = onode->is_pbsnode;
	nnode->is_job_busy = onode->is_job_busy;
	nnode->is_stale = onode->is_stale;
	nnode->is_provisioning = onode->is_provisioning;
	nnode->is_multivnoded = onode->is_multivnoded;

	nnode->sharing = onode->sharing;

	nnode->port = onode->port;
	nnode->lic_lock = onode->lic_lock;
	nnode->pcpus = onode->pcpus;

	nnode->rank = onode->rank;

	nnode->has_hard_limit = onode->has_hard_limit;
	nnode->no_multinode_jobs = onode->no_multinode_jobs;
	nnode->resv_enable = onode->resv_enable;
	nnode->provision_enable = onode->provision_enable;
	nnode->power_provisioning = onode->power_provisioning;

	nnode->num_jobs = onode->num_jobs;
	nnode->num_run_resv = onode->num_run_resv;
	nnode->num_susp_jobs = onode->num_susp_jobs;

	nnode->priority = onode->priority;

	nnode->jobs = dup_string_array(onode->jobs);
	if (flags & DUP_INDIRECT)
		nnode->res = dup_ind_resource_list(onode->res);
	else
		nnode->res = dup_resource_list(onode->res);

	nnode->max_load = onode->max_load;
	nnode->ideal_load = onode->ideal_load;
	nnode->loadave = onode->loadave;

	nnode->max_running = onode->max_running;
	nnode->max_user_run = onode->max_user_run;
	nnode->max_group_run = onode->max_group_run;

	nnode->group_counts = dup_counts_list(onode->group_counts);
	nnode->user_counts = dup_counts_list(onode->user_counts);

	set_current_aoe(nnode, onode->current_aoe);
	set_current_eoe(nnode, onode->current_eoe);
	nnode->nodesig = string_dup(onode->nodesig);
	nnode->nodesig_ind = onode->nodesig_ind;

	if (onode->svr_node != NULL)
		nnode->svr_node = find_node_by_rank(nsinfo->nodes, onode->rank);

	/* Duplicate list of jobs and running reservations.
	 * If caller is dup_server_info() then nsinfo->resvs/jobs should be NULL,
	 * but running reservations and jobs are collected later in the caller.
	 * Otherwise, we collect running reservations or jobs here.
	 */
	nnode->run_resvs_arr = copy_resresv_array(onode->run_resvs_arr, nsinfo->resvs);
	nnode->job_arr = copy_resresv_array(onode->job_arr, nsinfo->jobs);

	/* If we are called from dup_server(), nsinfo->hostsets are NULL.
	 * They are not created yet.  Hostsets will be attached in dup_server()
	 */
	if (onode->hostset != NULL)
		nnode->hostset = find_node_partition_by_rank(nsinfo->hostsets,
			onode->hostset->rank);

	nnode->nscr = onode->nscr;

#ifdef NAS /* localmod 049 */
	nnode->NASrank = onode->NASrank;
#endif /* localmod 049 */

	return nnode;
}

/**
 * @brief
 *		copy_node_ptr_array - copy an array of jobs using a different set of
 *			      of node pointer (same nodes, different array).
 *			      This means we have to use the names from the
 *			      first array and find them in the second array
 *
 *
 * @param[in]	oarr	-	the old array (filtered array)
 * @param[in]	narr	-	the new array (entire node array)
 *
 * @return	copied array
 * @retval	NULL	: on error
 *
 */
#ifdef NAS /* localmod 049 */
node_info **
copy_node_ptr_array(node_info  **oarr, node_info  **narr,
	server_info *sinfo)
#else
node_info **
copy_node_ptr_array(node_info  **oarr, node_info  **narr)
#endif /* localmod 049 */
{
	int i;
	node_info **ninfo_arr;
	node_info *ninfo;

	if (oarr == NULL || narr == NULL)
		return NULL;

	for (i = 0; oarr[i] != NULL; i++)
		;

	if ((ninfo_arr = malloc(sizeof(node_info *) * (i + 1))) == NULL)
		return NULL;

	for (i = 0; oarr[i] != NULL; i++) {
#ifdef NAS /* localmod 049 */
		if (sinfo != NULL &&
			narr == sinfo->nodes &&
			oarr[i]->rank == sinfo->nodes_by_NASrank[oarr[i]->NASrank]->rank)
			ninfo = sinfo->nodes_by_NASrank[oarr[i]->NASrank];
		else
#endif /* localmod 049 */
		ninfo = find_node_by_rank(narr, oarr[i]->rank);

		if (ninfo == NULL) {
			free(ninfo_arr);
			return NULL;
		}
		ninfo_arr[i] = ninfo;
	}
	ninfo_arr[i] = NULL;

	return ninfo_arr;
}

/**
 * @brief
 *		collect_resvs_on_nodes - collect all the running resvs from resv array
 *				on the nodes
 *
 * @param[in]	ninfo	-	the nodes to collect for
 * @param[in]	resresv_arr	-	the array of resvs to consider
 * @param[in]	size	-	the size (in number of pointers) of the resv array
 *
 * @return	int
 * @retval	1	: success
 * @retval	0	: failure
 *
 */
int
collect_resvs_on_nodes(node_info **ninfo_arr, resource_resv **resresv_arr, int size)
{
	int i;

	if (ninfo_arr == NULL || ninfo_arr[0] == NULL)
		return 0;

	for (i = 0; ninfo_arr[i] != NULL; i++) {
		ninfo_arr[i]->run_resvs_arr = resource_resv_filter(resresv_arr, size,
			check_resv_running_on_node, ninfo_arr[i]->name, 0);
		/* the count of running resvs on the node is set in query_reservations */
	}
	return 1;
}

/**
 * @brief
 *		collect_jobs_on_nodes - collect all the jobs in the job array on the
 *				nodes
 *
 * @param[in]	ninfo	-	the nodes to collect for
 * @param[in]	resresv_arr	-	the array of jobs to consider
 * @param[in]	size	-	the size (in number of pointers) of the job arrays
 *
 * @retval	1	: upon success
 * @retval	2	: if a job reported on nodes was not found in the job arrays
 * @retval	0	: upon failure
 *
 */
int
collect_jobs_on_nodes(node_info **ninfo_arr, resource_resv **resresv_arr, int size)
{
	char *ptr;		/* used to find the '/' in the jobs array */
	resource_resv *job;	/* find the job from the jobs array */
	resource_resv **susp_jobs = NULL; 	/* list of suspended jobs */
	counts *cts;		/* used to update user and group counts */
	int i, j, k;
	node_info *node;	/* used to store pointer of node in ninfo_arr */
	char logbuf[MAX_LOG_SIZE];
	resource_resv **temp_ninfo_arr = NULL;

	if (ninfo_arr == NULL || ninfo_arr[0] == NULL)
		return 0;

	for (i = 0; ninfo_arr[i] != NULL; i++) {
		if ((ninfo_arr[i]->job_arr =
			malloc((size + 1) * sizeof(resource_resv *))) == NULL)
			return 0;
		ninfo_arr[i]->job_arr[0] = NULL;
	}

	for (i = 0; ninfo_arr[i] != NULL; i++) {
		if (ninfo_arr[i]->jobs != NULL) {
			for (j = 0, k = 0; ninfo_arr[i]->jobs[j] != NULL && k < size; j++) {
				/* jobs are in the format of node_name/sub_node.  We don't care about
				 * the subnode... we just want to populate the jobs on our node
				 * structure
				 */
				ptr = strchr(ninfo_arr[i]->jobs[j], '/');
				if (ptr != NULL)
					*ptr = '\0';

				job = find_resource_resv(resresv_arr, ninfo_arr[i]->jobs[j]);
				if ((job != NULL) && (job->nspec_arr != NULL)) {
					/* if a distributed job has more then one instance on this node
					 * it'll show up more then once.  If this is the case, we only
					 * want to have the job in our array once.
					 */
					if (find_resource_resv_by_rank(ninfo_arr[i]->job_arr,
						job->rank) == NULL) {
						if (ninfo_arr[i]->has_hard_limit) {
						cts = find_alloc_counts(ninfo_arr[i]->group_counts,
							job->group);
						if (ninfo_arr[i]->group_counts == NULL)
							ninfo_arr[i]->group_counts = cts;

						update_counts_on_run(cts, job->resreq);

						cts = find_alloc_counts(ninfo_arr[i]->user_counts,
							job->user);
						if (ninfo_arr[i]->user_counts == NULL)
							ninfo_arr[i]->user_counts = cts;

						update_counts_on_run(cts, job->resreq);
						}

						ninfo_arr[i]->job_arr[k] = job;
						k++;
						/* make the job array searchable with find_resource_resv */
						ninfo_arr[i]->job_arr[k] = NULL;
					}
				} else {
					/* Race Condition occurred: nodes were queried when a job existed.
					 * Jobs were queried when the job no longer existed.  Make note
					 * of it on the job so the node's resources_assigned values can be
					 * recalculated later.
					 */
					ninfo_arr[i]->has_ghost_job = 1;
					snprintf(logbuf, sizeof(logbuf),
						"Job %s reported running on node no longer exists or is not in running state",
						ninfo_arr[i]->jobs[j]);
					schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_NODE, LOG_DEBUG,
						ninfo_arr[i]->name, logbuf);
				}

			}
			ninfo_arr[i]->num_jobs = k;
		}
	}

	for (i = 0; ninfo_arr[i] != NULL; i++) {
		temp_ninfo_arr = realloc(
			ninfo_arr[i]->job_arr,
			(ninfo_arr[i]->num_jobs + 1) * sizeof(resource_resv *));
		if (temp_ninfo_arr == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			return 0;
		} else {
			ninfo_arr[i]->job_arr = temp_ninfo_arr;
		}
		ninfo_arr[i]->
		job_arr[ninfo_arr[i]->num_jobs] = NULL;
	}

	susp_jobs = resource_resv_filter(resresv_arr,
		count_array((void **) resresv_arr), check_susp_job, NULL, 0);
	if (susp_jobs == NULL)
		return 0;

	for (i = 0; susp_jobs[i] != NULL; i++) {
		if (susp_jobs[i]->ninfo_arr != NULL) {
			for (j = 0; susp_jobs[i]->ninfo_arr[j] != NULL; j++) {
				/* resresv->ninfo_arr is merely a new list with pointers to server nodes.
				 * resresv->resv->resv_nodes is a new list with pointers to resv nodes
				 */
				node = find_node_info(ninfo_arr,
						susp_jobs[i]->ninfo_arr[j]->name);
				if (node != NULL)
					node->num_susp_jobs++;
			}
		}
	}
	free(susp_jobs);

	return 1;
}

/**
 * @brief
 *		update_node_on_run - update internal scheduler node data when a
 *			     resource resv is run.
 *
 * @param[in]	nspec	-	the nspec for the node allocation
 * @param[in]	resresv -	the resource rev which ran
 * @param[in]  job_state -	the old state of a job if resresv is a job
 *				If the old_state is found to be suspended
 *				then only resources that were released
 *				during suspension will be accounted.
 *
 * @return	nothing
 *
 */
void
update_node_on_run(nspec *ns, resource_resv *resresv, char *job_state)
{
	resource_req *resreq = NULL;
	schd_resource *res = NULL;
	schd_resource *ncpusres = NULL;
	counts *cts;
	resource_resv **tmp_arr;
	node_info *ninfo;

	if (ns == NULL || resresv == NULL)
		return;

	ninfo = ns->ninfo;

	/* Don't account for resources of a node that is unavailable */
	if (ninfo->is_offline || ninfo->is_down)
		return;

	if (resresv->is_job) {
		ninfo->num_jobs++;
		if (find_resource_resv_by_rank(ninfo->job_arr, resresv->rank) ==NULL) {
			tmp_arr = add_resresv_to_array(ninfo->job_arr, resresv);
			if (tmp_arr == NULL)
				return;

			ninfo->job_arr = tmp_arr;
		}

	}
	else if (resresv->is_resv) {
		ninfo->num_run_resv++;
		if (find_resource_resv_by_rank(ninfo->run_resvs_arr, resresv->rank) ==NULL) {
			tmp_arr = add_resresv_to_array(ninfo->run_resvs_arr, resresv);
			if (tmp_arr == NULL)
				return;

			ninfo->run_resvs_arr = tmp_arr;
		}
	}

	resreq = ns->resreq;
	if ((job_state != NULL) && (*job_state == 'S')) {
		if (resresv->job->resreleased != NULL) {
			nspec *temp = find_nspec_by_rank(resresv->job->resreleased, ninfo->rank);
			if (temp != NULL)
				resreq = temp->resreq;
		}
	}
	while (resreq != NULL) {
		if (resreq->type.is_consumable) {
			res = find_resource(ninfo->res, resreq->def);

			if (res != NULL) {
				if (res->indirect_res != NULL)
					res = res->indirect_res;

				res->assigned += resreq->amount;

				if (res->def  == getallres(RES_NCPUS)) {
					ncpusres = res;
					ninfo->loadave += resreq->amount;
					if (!ninfo->lic_lock)
						ninfo->server->flt_lic -= resreq->amount;
				}
			}
		}
		resreq = resreq->next;
	}

	if (ninfo->has_hard_limit && resresv->is_job) {
		cts = find_alloc_counts(ninfo->group_counts, resresv->group);

		if (ninfo->group_counts == NULL)
			ninfo->group_counts = cts;

		update_counts_on_run(cts, ns->resreq);

		cts = find_alloc_counts(ninfo->user_counts, resresv->user);

		if (ninfo->user_counts == NULL)
			ninfo->user_counts = cts;

		update_counts_on_run(cts, ns->resreq);
	}

	if (ninfo->is_pbsnode) {
		/* if we're a cluster node and we have no cpus available, we're job_busy */
		if (ncpusres == NULL)
			ncpusres = find_resource(ninfo->res, getallres(RES_NCPUS));

		if (ncpusres != NULL) {
			if (dynamic_avail(ncpusres) == 0)
				set_node_info_state(ninfo, ND_jobbusy);
		}

		/* if node selected for provisioning, this node is no longer available */
		if (ns->go_provision == 1) {
			set_node_info_state(ninfo, ND_prov);

			/* for jobs inside reservation, update the server's node info as well */
			if (resresv->job != NULL && resresv->job->resv != NULL &&
				ninfo->svr_node != NULL) {
				set_node_info_state(ninfo->svr_node, ND_prov);
			}


			set_current_aoe(ninfo, resresv->aoename);
		}

		/* if job has eoe setting this node gets current_eoe set */
		if (resresv->is_job && resresv->eoename != NULL)
			set_current_eoe(ninfo, resresv->eoename);

		if (is_excl(resresv->place_spec, ninfo->sharing)) {
			if (resresv->is_resv) {
				add_node_state(ninfo, ND_resv_exclusive);
			}
			else {
				add_node_state(ninfo, ND_job_exclusive);
			}
		}
	}
}

/**
 * @brief
 *		update_node_on_end - update a node when a resource resv ends
 *
 * @param[in]	ninfo	-	the node where the job was running
 * @param[in]	resresv -	the resource resv which is ending
 * @param[in]  job_state -	the old state of a job if resresv is a job
 *				If the old_state is found to be suspended
 *				then only resources that were released
 *				during suspension will be accounted.
 *
 * @return	nothing
 *
 */
void
update_node_on_end(node_info *ninfo, resource_resv *resresv, char *job_state)
{
	resource_req *resreq = NULL;
	schd_resource *res = NULL;
	counts *cts;
	nspec *ns;		/* nspec from resresv for this node */
	char logbuf[MAX_LOG_SIZE];
	int i;

	if (ninfo == NULL || resresv == NULL || resresv->nspec_arr == NULL)
		return;

	/* Don't account for resources of a node that is unavailable */
	if (ninfo->is_offline || ninfo->is_down)
		return;

	if (resresv->is_job) {
		ninfo->num_jobs--;
		if (ninfo->num_jobs < 0)
			ninfo->num_jobs = 0;

		remove_resresv_from_array(ninfo->job_arr, resresv);
	}
	else if (resresv->is_resv) {
		ninfo->num_run_resv--;
		if (ninfo->num_run_resv < 0)
			ninfo->num_run_resv = 0;

		remove_resresv_from_array(ninfo->run_resvs_arr, resresv);
	}

	if (ninfo->is_job_busy)
		remove_node_state(ninfo, ND_jobbusy);
	if (is_excl(resresv->place_spec, ninfo->sharing)) {
		if (resresv->is_resv) {
			if (ninfo->svr_node != NULL)
				remove_node_state(ninfo->svr_node, ND_resv_exclusive);
		}
		else {
			remove_node_state(ninfo, ND_job_exclusive);
		}
	}

	for (i = 0; resresv->nspec_arr[i] != NULL; i++) {
		if (resresv->nspec_arr[i]->ninfo == ninfo) {
			ns = resresv->nspec_arr[i];

			resreq = ns->resreq;
			if ((job_state != NULL) && (*job_state == 'S')) {
				if (resresv->job->resreleased != NULL) {
					nspec * temp = find_nspec_by_rank(resresv->job->resreleased, ninfo->rank);
					if (temp != NULL)
						resreq = temp->resreq;
				}
			}
			while (resreq != NULL) {
				if (resreq->type.is_consumable) {
					res = find_resource(ninfo->res, resreq->def);
					if (res != NULL) {
						if (res->indirect_res != NULL)
							res = res->indirect_res;
						res->assigned -= resreq->amount;
						if (res->assigned < 0) {
							snprintf(logbuf, MAX_LOG_SIZE,
								"Setting %s assigned to %.2lf", res->name, res->assigned);
							schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
								LOG_DEBUG, ninfo->name, logbuf);
						}
						if (res->def == getallres(RES_NCPUS)) {
							ninfo->loadave -= resreq->amount;
							if (ninfo->loadave < 0)
								ninfo->loadave = 0;

							if (!ninfo->lic_lock)
								ninfo->server->flt_lic += resreq->amount;
						}
					}
				}
				resreq = resreq->next;
			}
			/* no soft limits on nodes... just hard limits */
			if (ninfo->has_hard_limit && resresv->is_job) {
				cts = find_counts(ninfo->group_counts, resresv->group);

				if (cts != NULL)
					update_counts_on_end(cts, ns->resreq);

				cts = find_counts(ninfo->user_counts, resresv->user);

				if (cts != NULL)
					update_counts_on_end(cts, ns->resreq);
			}
		}
	}
}

/**
 * @brief
 *		should_talk_with_mom - check if we should talk to this mom
 *
 * @param[in]	ninfo	-	the mom we are checking
 *
 * @return	int
 * @retval	1	: talk with the mom
 * @retval	0	: don't talk
 *
 */
int
should_talk_with_mom(node_info *ninfo)
{
	schd_resource *res;
	int talk = 0;

	if (ninfo == NULL)
		return 0;

	if (ninfo->is_down)
		return 0;

	if (ninfo->is_offline)
		return 0;

	if (conf.dyn_res_to_get != NULL)
		talk = 1;

	if (cstat.smp_dist == SMP_LOWEST_LOAD)
		talk = 1;

	if (cstat.load_balancing)
		talk = 1;

	if (conf.assign_ssinodes) {
		res = find_resource(ninfo->res, getallres(RES_ARCH));

		if (res != NULL)
			if (strncmp("irix", res->str_avail[0], 4) == 0)
				talk = 1;
	}

	if (talk) {
		res = find_resource(ninfo->res, getallres(RES_HOST));
		if (res != NULL) {
			if (!compare_res_to_str(res, ninfo->name, CMP_CASELESS))
				talk = 0;
		}
	}

	return talk;
}


/**
 * @brief
 * 		new_nspec - allocate a new nspec
 *
 * @return	newly allocated and initialized nspec
 *
 */
nspec *
new_nspec()
{
	nspec *ns;

	if ((ns = (nspec *) malloc(sizeof(nspec))) == NULL) {
		log_err(errno, "new_nspec", MEM_ERR_MSG);
		return NULL;
	}

	ns->end_of_chunk = 0;
	ns->seq_num = 0;
	ns->sub_seq_num = 0;
	ns->go_provision = 0;
	ns->ninfo = NULL;
	ns->resreq = NULL;

	return ns;
}

/**
 * @brief
 * 		free_nspec - free the memory used for an nspec
 *
 * @param[in]	ns	-	the nspec to free
 *
 * @return	nothing
 *
 */
void
free_nspec(nspec *ns)
{
	if (ns == NULL)
		return;

	if (ns->resreq != NULL)
		free_resource_req_list(ns->resreq);

	free(ns);
}

/**
 * @brief
 * 		dup_nspec - duplicate an nspec
 *
 * @param[in]	ons	-	the nspec to duplicate
 * @param[in]	nsinfo	-	the new server info
 *
 * @return	newly duplicated nspec
 *
 */
#ifdef NAS /* localmod 049 */
nspec *
dup_nspec(nspec *ons, node_info **ninfo_arr, server_info *sinfo)
#else
nspec *
dup_nspec(nspec *ons, node_info **ninfo_arr)
#endif /* localmod 049 */
{
	nspec *nns;

	if (ons == NULL || ninfo_arr == NULL)
		return NULL;

	nns = new_nspec();

	if (nns == NULL)
		return NULL;

	nns->end_of_chunk = ons->end_of_chunk;
	nns->seq_num = ons->seq_num;
	nns->sub_seq_num = ons->sub_seq_num;
	nns->go_provision = ons->go_provision;
#ifdef NAS /* localmod 049 */
	if (sinfo != NULL &&
		ninfo_arr == sinfo->nodes &&
		ons->ninfo->rank == sinfo->nodes_by_NASrank[ons->ninfo->NASrank]->rank)
		nns->ninfo = sinfo->nodes_by_NASrank[ons->ninfo->NASrank];
	else
#endif /* localmod 049 */
	nns->ninfo = find_node_by_rank(ninfo_arr, ons->ninfo->rank);
	nns->resreq = dup_resource_req_list(ons->resreq);

	return nns;
}

/**
 * @brief
 * 		dup_nspecs - duplicate an array of nspecs
 *
 * @param[in]	onspecs	-	the nspecs to duplicate
 * @param[in]	ninfo_arr	-	the nodes corresponding to the nspecs
 *
 * @return	duplicated nspec array
 *
 */
#ifdef NAS /* localmod 049 */
nspec **
dup_nspecs(nspec **onspecs, node_info **ninfo_arr, server_info *sinfo)
#else
nspec **
dup_nspecs(nspec **onspecs, node_info **ninfo_arr)
#endif /* localmod 049 */
{
	nspec **nnspecs;
	int num_ns;
	int i;

	if (onspecs == NULL || ninfo_arr == NULL)
		return NULL;


	for (num_ns = 0; onspecs[num_ns] != NULL; num_ns++)
		;

	if ((nnspecs = (nspec **) malloc(sizeof(nspec) * (num_ns+1))) == NULL)
		return NULL;

	for (i = 0; onspecs[i] != NULL; i++)
#ifdef NAS /* localmod 049 */
		nnspecs[i] = dup_nspec(onspecs[i], ninfo_arr, sinfo);
#else
		nnspecs[i] = dup_nspec(onspecs[i], ninfo_arr);
#endif /* localmod 049 */

	nnspecs[i] = NULL;

	return nnspecs;
}

/**
 * @brief
 *		empty_nspec_array - free the contents of an nspec array but not
 *			    the array itself.
 *
 * @param[in,out]	nspec_arr	-	the nspec array
 *
 * @return	nothing
 *
 */
void
empty_nspec_array(nspec **nspec_arr)
{
	int i;

	if (nspec_arr == NULL)
		return;

	for (i = 0; nspec_arr[i] != NULL; i++) {
		free_nspec(nspec_arr[i]);
		nspec_arr[i] = NULL;
	}
}

/**
 * @brief
 * 		free_nspecs - free a nspec array
 *
 * @param[in,out]	ns	-	the nspec array
 *
 * @return	nothing
 *
 */
void
free_nspecs(nspec **ns)
{
	if (ns == NULL)
		return;

	empty_nspec_array(ns);

	free(ns);
}

/**
 * @brief
 *		find_nspec - find an nspec in an array
 *
 * @param[in]	nspec_arr	-	the array of nspecs to search
 * @param[in]	ninfo	-	the node_info to find
 *
 * @return	the found nspec
 * @retval	NULL
 *
 */
nspec *
find_nspec(nspec **nspec_arr, node_info *ninfo)
{
	int i;

	if (nspec_arr == NULL || ninfo == NULL)
		return NULL;

	for (i = 0; nspec_arr[i] != NULL && nspec_arr[i]->ninfo != ninfo; i++)
		;

	return nspec_arr[i];
}

/**
 * @brief
 * 		find an nspec in an array by rank
 *
 * @param[in]	nspec_arr	-	the array of nspecs to search
 * @param[in]	rank	-	the unique integer identifier of the nspec/node to search for
 *
 * @return	the found nspec
 * @retval	NULL	: Error
 *
 */
nspec *
find_nspec_by_rank(nspec **nspec_arr, unsigned int rank)
{
	int i;

	if (nspec_arr == NULL)
		return NULL;

	for (i = 0; nspec_arr[i] != NULL &&
		nspec_arr[i]->ninfo->rank != rank; i++)
		;

	return nspec_arr[i];
}

/**
 *	@brief
 *		eval a select spec to see if it is satisfiable
 *
 * @param[in]	policy	  -	policy info
 * @param[in]	spec	  -	the select spec
 * @param[in]	placespec -	the placement spec (-l place)
 * @param[in]	ninfo_arr - 	array of nodes to satisfy the spec
 * @param[in]	nodepart  -	the node partition array for node grouping
 *		 	 	if NULL, we're not doing node grouping
 * @param[in]	resresv	  -	the resource resv the spec is from
 * @param[in]	flags	  -	flags to change functions behavior
 *	      			EVAL_OKBREAK - ok to break chunk up across vnodes
 *	      			EVAL_EXCLSET - allocate entire nodelist exclusively
 * @param[out]	nspec_arr -	the node solution
 * @param[out]	err	  -	error structure to return error information
 *
 * @return	int
 * @retval	1	  : 	if the nodespec can be satisfied
 * @retval	0	  : 	if not
 *
 */
int
eval_selspec(status *policy, selspec *spec, place *placespec,
	node_info **ninfo_arr, node_partition **nodepart, resource_resv *resresv,
	unsigned int flags, nspec ***nspec_arr, schd_error *err)
{
	int				tot_nodes = 0;
	place				*pl;
	int				can_fit = 0;
	int				rc = 0;		/* 1 if resources are available, 0 if not */
	char				logbuf[MAX_LOG_SIZE] = {0};
	int				pass_flags = NO_FLAGS;
	char				reason[MAX_LOG_SIZE] = {0};
	int				i = 0;
	static struct schd_error	*failerr = NULL;

	if (spec == NULL || ninfo_arr == NULL || resresv == NULL || placespec == NULL || nspec_arr == NULL)
		return 0;
	/* Unsetting RETURN_ALL_ERR flag, because with this flag set resresv_can_fit_nodepart can return
	 * with multiple errors and the function only needs to see the first error it encounters.
	 */
	flags &= ~RETURN_ALL_ERR;

#ifdef NAS /* localmod 063 */
	/* Should be at least one chunk */
	if (spec->total_chunks < 1)
		return 0;
#endif /* localmod 063 */

	if (failerr == NULL) {
		failerr = new_schd_error();
		if (failerr == NULL) {
			set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
			return 0;
		}
	} else
		clear_schd_error(failerr);

	/* clear the node scratch space for use for node searching */
	for (i = 0; ninfo_arr[i] != NULL; i++) {
		memset(&ninfo_arr[i]->nscr, 0, sizeof(node_scratch));
	}

	pl = placespec;
	tot_nodes = count_array((void **) ninfo_arr);

	if (flags != NO_FLAGS)
		pass_flags = flags;

	/* Worst case is that all nodes show up in every chunk */
	if ((*nspec_arr = (nspec **) calloc(spec->total_chunks * tot_nodes + 1,
		sizeof(nspec*))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return 0;
	}

	check_node_array_eligibility(ninfo_arr, resresv, pl, err);

	if (failerr->status_code == SCHD_UNKWN)
		move_schd_error(failerr, err);
	clear_schd_error(err);

	/* If we are not node grouping or we only have 1 chunk packed onto a single
	 * host, then we should try and satisfy over all nodes in the list
	 *
	 * NOTE: pack && total_chunks == 1 may not be valid once chunks are
	 * broken into vchunks
	 */
	if (nodepart == NULL) {
		if (resresv->server->has_multi_vnode && ok_break_chunk(resresv, ninfo_arr))
			pass_flags |= EVAL_OKBREAK;

		rc = eval_placement(policy, spec, ninfo_arr, pl, resresv, pass_flags, nspec_arr, err);
		if (rc == 0) {
			free_nspecs(*nspec_arr);
			*nspec_arr = NULL;
		}
		if (pass_flags & EVAL_EXCLSET)
			alloc_rest_nodepart(*nspec_arr, ninfo_arr);

		return rc;
	}

	/* Otherwise we're node grouping... */

	for (i = 0; nodepart[i] != NULL && rc == 0; i++) {
		clear_schd_error(err);
		if (resresv_can_fit_nodepart(policy, nodepart[i], resresv, flags, err)) {
			snprintf(logbuf, MAX_LOG_SIZE, "Evaluating placement set: %s",
				nodepart[i]->name);
			schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
				resresv->name, logbuf);
			if (nodepart[i]->ok_break)
				pass_flags |= EVAL_OKBREAK;

			if (nodepart[i]->excl)
				pass_flags |= EVAL_EXCLSET;

			rc = eval_placement(policy, spec, nodepart[i]->ninfo_arr, pl,
				resresv, pass_flags, nspec_arr, err);
			if (rc > 0) {
				if (resresv->nodepart_name != NULL)
					free(resresv->nodepart_name);
				resresv->nodepart_name = string_dup(nodepart[i]->name);
				can_fit = 1;
				if (nodepart[i]->excl)
					alloc_rest_nodepart(*nspec_arr, nodepart[i]->ninfo_arr);
			}
			else {
				empty_nspec_array(*nspec_arr);
				if (failerr->status_code == SCHD_UNKWN)
					move_schd_error(failerr, err);
			}
		}
		else {
			translate_fail_code(err, NULL, reason);
			snprintf(logbuf, MAX_LOG_SIZE,
				"Placement set %s is too small: %s", nodepart[i]->name, reason);
			schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
				resresv->name, logbuf);
			set_schd_error_codes(err, NOT_RUN, SET_TOO_SMALL);
			set_schd_error_arg(err, ARG1, "Placement");
#ifdef NAS /* localmod 031 */
			set_schd_error_arg(err, ARG2, "for resource model");
#else
			set_schd_error_arg(err, ARG2, nodepart[i]->name);
#endif /* localmod 031 */
			if (failerr->status_code == SCHD_UNKWN)
				move_schd_error(failerr, err);
		}

		if (!can_fit && !rc &&
			resresv_can_fit_nodepart(policy, nodepart[i], resresv, flags|COMPARE_TOTAL, err)) {
			can_fit = 1;
		}
		pass_flags = NO_FLAGS;
	}

	if (!can_fit) {
		if (!resresv->server->dont_span_psets) {
			schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG, resresv->name,  "Request won't fit into any placement sets, will use all nodes");
			resresv->can_not_fit = 1;
			if (resresv->server->has_multi_vnode && ok_break_chunk(resresv, ninfo_arr))
				pass_flags |= EVAL_OKBREAK;

			rc = eval_placement(policy, spec, ninfo_arr, pl, resresv, pass_flags, nspec_arr, err);
		}
		else {
			set_schd_error_codes(err, NEVER_RUN, CANT_SPAN_PSET);
			/* CANT_SPAN_PSET is more important than any other error we may have encountered -- keep it*/
			clear_schd_error(failerr);
			move_schd_error(failerr, err);
		}
	}

	if (!rc) {
		free_nspecs(*nspec_arr);
		*nspec_arr = NULL;
	}

	if (err->status_code == SCHD_UNKWN && failerr->status_code != SCHD_UNKWN)
		move_schd_error(err, failerr);

	return rc;
}

/**
 * @brief
 * 		handle the place spec for vnode placement of chunks
 *
 * @param[in] policy     - policy info
 * @param[in] spec       - the select spec
 * @param[in] ninfo_arr  - array of nodes to satisfy the spec
 * @param[in] pl         - parsed placement spec
 * @param[in] resresv    - the resource resv the spec if from
 * @param[in] flags	-	flags to change function's behavior
 *	      				EVAL_OKBREAK - ok to break chunk up across vnodes
 * @param[out]	nspec_arr	-	the node solution will be allocated and
 *				   				returned by this pointer by reference
 * @param[out]	err	-	error structure to return error information
 *
 * @return	int
 * @retval	1	: if the selspec can be satisfied
 * @retval	0	: if not
 *
 */
int
eval_placement(status *policy, selspec *spec, node_info **ninfo_arr, place *pl,
	resource_resv *resresv, unsigned int flags,
	nspec ***nspec_arr, schd_error *err)
{
	np_cache		*npc = NULL;
	node_partition		**hostsets = NULL;
	char			*host_arr[2] = {"host", NULL};
	int			i = 0;
	int			k = 0;
	int			tot = 0;
	int			c = -1;
	int			cur_flt_lic;
	nspec			**nsa = NULL;
	nspec			**ns_head = NULL;
	char			logbuf[MAX_LOG_SIZE] = {0};
	char			reason[MAX_LOG_SIZE] = {0};
	resource_req		*req = NULL;
	schd_resource		*res = NULL;
	selspec			*dselspec = NULL;
	int			do_exclhost = 0;
	node_info		**nptr = NULL;
	static schd_error	*failerr = NULL;


	int rc = 0; /* true if current chunk was successfully allocated */
	/* true if any vnode is allocated from a host - used in exclhost allocation */
	int any_succ_rc = 0;

	if (spec == NULL || ninfo_arr == NULL || pl == NULL || resresv == NULL || nspec_arr == NULL)
		return 0;

	if (failerr == NULL) {
		failerr = new_schd_error();
		if (failerr == NULL) {
			set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
			return 0;
		}
	} else
		clear_schd_error(failerr);

	/* reorder nodes for smp_cluster_dist or avoid_provision.
	 *
	 * remark: reorder_nodes doesn't reorder in place, returns
	 *         a ptr to a reordered static array
	 */
	if ((pl->pack && spec->total_chunks == 1 && nspec_arr != NULL) ||
		(conf.provision_policy == AVOID_PROVISION && resresv->aoename != NULL) ||
		(resresv->is_resv && resresv->resv != NULL && resresv->resv->check_alternate_nodes))
		nptr = reorder_nodes(ninfo_arr, resresv);

	if (nptr == NULL)
		nptr = ninfo_arr;

	/*
	 * eval_complex_selspec() handles placement for single vnoded systems.
	 * it should be merged into this function in a optimized way, but until
	 * we short circuit this function and fall into it.  This function doesn't
	 * handle multi-chunk pack.  We still fall into it in the case of a single
	 * chunk.
	 */
	if (!resresv->server->has_multi_vnode &&
		(!resresv->place_spec->pack || spec->total_chunks == 1)) {
		return eval_complex_selspec(policy, spec, nptr, pl, resresv, flags, nspec_arr, err);
	}

	/* get a pool of node partitions based on host.  If we're using the
	 * server's nodes, we can use the pre-created host sets.
	 */
	if (nptr == resresv->server->nodes)
		hostsets = resresv->server->hostsets;

	if (hostsets == NULL) {
		npc = find_alloc_np_cache(policy, &resresv->server->npc_arr, host_arr, nptr, NULL);
		if (npc != NULL)
			hostsets = npc->nodepart;
	}

	cur_flt_lic = resresv->server->flt_lic;

	if (hostsets != NULL) {
		nsa = *nspec_arr;
		ns_head = *nspec_arr;

		if (pl->scatter || pl->vscatter || pl->free) {
			dselspec = dup_selspec(spec);
			if (dselspec == NULL)
				return 0;
		}

		for (i = 0; hostsets[i] != NULL && tot != spec->total_chunks; i++) {
			/* if one vnode on a host is set to force/dflt exclhost
			 * then they all are.  The mom makes sure of this
			 */
			node_info **dninfo_arr = hostsets[i]->ninfo_arr;
			enum vnode_sharing sharing = VNS_DFLT_SHARED;

			if (dninfo_arr[0] != NULL)
				sharing = dninfo_arr[0]->sharing;

			do_exclhost = 0;
			flags &= ~EVAL_EXCLSET;
			if (sharing == VNS_FORCE_EXCLHOST ||
				(sharing == VNS_DFLT_EXCLHOST && pl->excl == 0 && pl->share ==0)||
				pl->exclhost) {
				do_exclhost = 1;
				flags |= EVAL_EXCLSET;
			}

			rc = any_succ_rc = 0;
			sprintf(logbuf, "Evaluating host %s", hostsets[i]->res_val);
			schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
				resresv->name, logbuf);

			/* Pack on One Host Placement:
			 * place all chunks on one host.  This is done with a call to
			 * to eval_complex_selspec().
			 */
			if (pl->pack) {
				rc = eval_complex_selspec(policy, spec, dninfo_arr, pl,
					resresv, flags | EVAL_OKBREAK, &nsa, err);
				if (rc > 0) {
					tot = spec->total_chunks;
					if (do_exclhost) {
						/* we're only looking at nodes for one host, 1st hostset will do  */
						if (dninfo_arr[0]->hostset != NULL)
							alloc_rest_nodepart(ns_head, dninfo_arr[0]->hostset->ninfo_arr);
						else
							alloc_rest_nodepart(ns_head, dninfo_arr);
					}
					while (*nsa != NULL)
						nsa++;
				}
				else {
					empty_nspec_array(nsa);
					if(failerr->status_code == SCHD_UNKWN)
						move_schd_error(failerr, err);
					clear_schd_error(err);

				}
			}
			/* Scatter by Vnode Placement:
			 * place at most one chunk on any one vnode.  This is done by successive
			 * calls to to eval_simple_selspec().  If it returns true, we remove the
			 * vnode from dninfo_arr[] so we don't allocate it again.
			 */
			else if (pl->vscatter) {
				for (c = 0; dselspec->chunks[c] != NULL; c++) {
					/* setting rc=1 forces at least 1 loop of the while.  This should be
					 * be rewritten in the do/while() style seen in the free block below
					 */
					rc = 1;
					if ((hostsets[i]->free_nodes > 0)
						&& (check_avail_resources(hostsets[i]->res,
						dselspec->chunks[c]->req, UNSET_RES_ZERO,
						NULL, INSUFFICIENT_RESOURCE, err))) {
						for (k = 0; dninfo_arr[k] != NULL; k++)
							dninfo_arr[k]->nscr.visited = 0;
						while (rc > 0 && dselspec->chunks[c]->num_chunks >0) {
							rc = eval_simple_selspec(policy, spec->chunks[c], dninfo_arr, pl,
								resresv, flags, cur_flt_lic, &nsa, err);

							if (rc > 0) {
								any_succ_rc = 1;
								tot++;
								dselspec->chunks[c]->num_chunks--;
								/* if one vnode on a host is unlicensed, they all are */
								if (!hostsets[i]->ninfo_arr[0]->lic_lock) {

									req = find_resource_req(spec->chunks[c]->req, getallres(RES_NCPUS));
									if (req != NULL)
										cur_flt_lic -= req->amount;
								}

								for (; *nsa != NULL; nsa++) {
									node_info *vn;
									vn = find_node_by_rank(dninfo_arr, (*nsa)->ninfo->rank);
									if (vn != NULL)
										vn->nscr.scattered = 1;
								}
							}
							else {
								empty_nspec_array(nsa);
								if (failerr->status_code == SCHD_UNKWN)
									move_schd_error(failerr, err);
								clear_schd_error(err);
							}
						}
					}
					else {
						rc = 0;
						if (hostsets[i]->free_nodes ==0) {
							strncpy(reason, "No free nodes available", MAX_LOG_SIZE - 1);
							reason[MAX_LOG_SIZE - 1] = '\0';
						}
						else
							translate_fail_code(err, NULL, reason);

						snprintf(logbuf, MAX_LOG_SIZE,
							"Insufficient host-level resources %s", reason);
						schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
							resresv->name, logbuf);
						if (failerr->status_code == SCHD_UNKWN)
							move_schd_error(failerr, err);
						clear_schd_error(err);

					}
				}
				if (do_exclhost && any_succ_rc) {
					/* we're only looking at nodes for one host, 1st node's will do  */
					if (dninfo_arr[0]->hostset != NULL)
						alloc_rest_nodepart(ns_head, dninfo_arr[0]->hostset->ninfo_arr);
					else
						alloc_rest_nodepart(ns_head, dninfo_arr);

					while (*nsa != NULL)
						nsa++;
				}
			}
			/* Scatter By Host Placement:
			* place at most one chunk on any one host.  We make a call to
			* eval_simple_selspec() for each sub-chunk (things between the +'s).
			* If it returns success (i.e. rc=1) we are done for this host
			*/
			else if (pl->scatter) {
				for (c = 0; dselspec->chunks[c] != NULL && rc == 0; c++) {
					if ((hostsets[i]->free_nodes > 0)
						&& (check_avail_resources(hostsets[i]->res,
						dselspec->chunks[c]->req, UNSET_RES_ZERO,
						NULL, INSUFFICIENT_RESOURCE, err))) {
						if (dselspec->chunks[c]->num_chunks >0) {
							for (k = 0; dninfo_arr[k] != NULL; k++)
								dninfo_arr[k]->nscr.visited = 0;

							rc = eval_simple_selspec(policy, spec->chunks[c],
								dninfo_arr, pl, resresv, flags| EVAL_OKBREAK,
								cur_flt_lic, &nsa, err);

							if (rc > 0) {
								any_succ_rc = 1;
								tot++;
								dselspec->chunks[c]->num_chunks--;
								req = find_resource_req(spec->chunks[c]->req, getallres(RES_NCPUS));
								if (req != NULL)
									cur_flt_lic -= req->amount;

								while (*nsa != NULL)
									nsa++;
							}
							else {
								empty_nspec_array(nsa);

								if (failerr->status_code == SCHD_UNKWN)
									move_schd_error(failerr, err);
								clear_schd_error(err);

							}
						}
					}
					else {
						if (hostsets[i]->free_nodes ==0) {
							strncpy(reason, "No free nodes available", MAX_LOG_SIZE - 1);
							reason[MAX_LOG_SIZE - 1] = '\0';
						}
						else
							translate_fail_code(err, NULL, reason);

						snprintf(logbuf, MAX_LOG_SIZE,
							"Insufficient host-level resources %s", reason);
						schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
							resresv->name, logbuf);

						if (failerr->status_code == SCHD_UNKWN)
							move_schd_error(failerr, err);
						clear_schd_error(err);

					}
				}
				if (do_exclhost && any_succ_rc) {
					/* we're only looking at nodes for one host, 1st hostset will do  */
					if (dninfo_arr[0]->hostset != NULL)
						alloc_rest_nodepart(ns_head, dninfo_arr[0]->hostset->ninfo_arr);
					else
						alloc_rest_nodepart(ns_head, dninfo_arr);

					while (*nsa != NULL)
						nsa++;
				}
			}
			/* Free Placement:
			 * Place as many chunks as possible on vnodes as they can hold.
			 * We do this by duplicating both the nodes and the select spec.  The
			 * resources and chunks counts are decremented in the duplicated select
			 * when they are allocated.  The assigned resources on the nodes are
			 * increased when resources are allocated.  When the select spec has no
			 *  more resources left, we've successfully fulfilled the request.  If we
			 * run out of nodes to search, then we've failed to fulfill the request.
			 */
			else if (pl->free) {
				node_info **dup_ninfo_arr;
#ifdef NAS /* localmod 049 */
				dup_ninfo_arr = dup_nodes(hostsets[i]->ninfo_arr,
					resresv->server, NO_FLAGS, 0);
#else
				dup_ninfo_arr = dup_nodes(hostsets[i]->ninfo_arr,
					resresv->server, NO_FLAGS);
#endif /* localmod 049 */
				if (dup_ninfo_arr == NULL) {
					free_selspec(dselspec);
					return 0;
				}

				for (c = 0; dselspec->chunks[c] != NULL; c++) {
					if ((hostsets[i]->free_nodes > 0)
						&& (check_avail_resources(hostsets[i]->res,
						dselspec->chunks[c]->req, UNSET_RES_ZERO,
						NULL, INSUFFICIENT_RESOURCE, err))) {
						if (dselspec->chunks[c]->num_chunks >0) {
							for (k = 0; dup_ninfo_arr[k] != NULL; k++)
								dup_ninfo_arr[k]->nscr.visited = 0;
							do {
								rc = eval_simple_selspec(policy, dselspec->chunks[c], dup_ninfo_arr,
									pl, resresv, flags | EVAL_OKBREAK, cur_flt_lic, &nsa, err);

								if (rc > 0) {
									any_succ_rc = 1;
									tot++;
									dselspec->chunks[c]->num_chunks--;

									for (; *nsa != NULL; nsa++) {
										req = (*nsa)->resreq;
										while (req != NULL) {
											if (req->type.is_consumable) {
												res = find_resource((*nsa)->ninfo->res,
													req->def);
												if (res != NULL) {
													if (res->indirect_res != NULL)
														res = res->indirect_res;

													res->assigned += req->amount;
												}
												if (!(*nsa)->ninfo->lic_lock &&
													(req->def == getallres(RES_NCPUS))) {
													cur_flt_lic -= req->amount;
												}
											}
											req = req->next;
										}
										if (nspec_arr != NULL) {
											/* replace duplicated node with real node */
#ifdef NAS /* localmod 049 */
											if ((*nsa)->ninfo->rank == resresv->server->nodes_by_NASrank[(*nsa)->ninfo->NASrank]->rank)
												(*nsa)->ninfo = resresv->server->nodes_by_NASrank[(*nsa)->ninfo->NASrank];
											else
#endif /* localmod 049 */
											(*nsa)->ninfo = find_node_by_rank(nptr,
												(*nsa)->ninfo->rank);
										}
									}
									while (*nsa != NULL)
										nsa++;
								}
								else {
									empty_nspec_array(nsa);

									if (failerr->status_code == SCHD_UNKWN)
										move_schd_error(failerr, err);
									clear_schd_error(err);
								}
							}
							while (rc > 0 && dselspec->chunks[c]->num_chunks >0);
						}
					}
					else {
						if (hostsets[i]->free_nodes ==0) {
							strncpy(reason, "No free nodes available", MAX_LOG_SIZE - 1);
							reason[MAX_LOG_SIZE - 1] = '\0';
						}
						else
							translate_fail_code(err, NULL, reason);

						snprintf(logbuf, MAX_LOG_SIZE,
							"Insufficient host-level resources %s", reason);
						schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
							resresv->name, logbuf);
#ifdef NAS /* localmod 998 */
						set_schd_error_codes(err, NOT_RUN, RESOURCES_INSUFFICIENT);
#else
						set_schd_error_codes(err, NOT_RUN, SET_TOO_SMALL);
#endif /* localmod 998 */
						set_schd_error_arg(err, ARG1, "Host");
						set_schd_error_arg(err, ARG2, hostsets[i]->name);

						if (failerr->status_code != SCHD_UNKWN)
							move_schd_error(failerr, err);
						clear_schd_error(err);
					}
				}
				if (do_exclhost && any_succ_rc) {
					/* we're only looking at nodes for one host, 1st hostset will do  */
					if (hostsets[i]->ninfo_arr[0]->hostset != NULL)
						alloc_rest_nodepart(ns_head, hostsets[i]->
							ninfo_arr[0]->hostset->ninfo_arr);
					else
						alloc_rest_nodepart(ns_head, dninfo_arr);

					while (*nsa != NULL)
						nsa++;
				}
				free_nodes(dup_ninfo_arr);
			}
			else {
				snprintf(logbuf, MAX_LOG_SIZE, "Unexpected Placement: not %s, %s, %s, or %s", PLACE_Scatter, PLACE_VScatter, PLACE_Pack, PLACE_Free);
				schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
					resresv->name, logbuf);
			}
		}
	} else
		set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);

	if (dselspec != NULL)
		free_selspec(dselspec);

	if (tot == spec->total_chunks)
		return 1;

	if (err->status_code == SCHD_UNKWN && failerr->status_code != SCHD_UNKWN)
		move_schd_error(err, failerr);

	return 0;
}

/**
 * @brief
 * 		handle a complex (plus'd) select spec
 *
 * @param[in]	policy	-	policy info
 * @param[in]	spec	-	the select spec
 * @param[in]	ninfo_arr	-	array of nodes to satisify the spec
 * @param[in]	pl	-	parsed placement spec
 * @param[in]	resresv	-	the resource resv the spec if from
 * @param[in]	flags	-	flags to change functions behavior
 *	      					EVAL_OKBREAK - ok to break chunck up across vnodes
 *	      					EVAL_EXCLSET - allocate entire nodelist exclusively
 * @param[out]	nspec_arr	-	the node solution
 * @param[out]	err	-	error structure to return error information
 *
 * @retval	1	: if the selspec can be satisfied
 * @retval	0	: if not
 *
 */
int
eval_complex_selspec(status *policy, selspec *spec, node_info **ninfo_arr, place *pl,
	resource_resv *resresv, unsigned int flags, nspec ***nspec_arr, schd_error *err)
{
	nspec **nsa = NULL;   /* the nspec array to hold node solution */
	node_info **nodes;    /* nodes to search through (possibly duplicated) */
	int rc = 1;		/* used as a return code in the complex spec case */
	int tot_nodes;	/* total number of nodes on the server */
	int cur_flt_lic;	/* current number of floating licenses */
	int num_nodes_used = 0;/* number of nodes used to satisfy spec */

	/* number of nodes used with the no_multinode_job flag set */
	int num_no_multi_nodes = 0;

	int chunks_needed = 0;

	int k;
	int n;
	int c;
	resource_req *req;
	schd_resource *res;

	if (spec == NULL || ninfo_arr == NULL)
		return 0;

	/* we have a simple selspec... just pass it along */
	if (spec->total_chunks == 1)
		return eval_simple_selspec(policy, spec->chunks[0], ninfo_arr, pl, resresv,
			flags, resresv->server->flt_lic, nspec_arr, err);

	tot_nodes = count_array((void **) ninfo_arr);

	nsa = *nspec_arr;


	/* we have a complex select spec
	 * This makes things more complicated now... we can make a single pass
	 * through our nodes and will possibly come up with a solution... but
	 * there is always the chance we could swap out nodes depending on one
	 * node being able to satisfy multiple simple specs.
	 * This resursion could take very long to finish.
	 *
	 * We'll go through the nodes once since it'll probably be fine for most
	 * cases.
	 */

	cur_flt_lic = resresv->server->flt_lic;

	if (pl->scatter || pl->vscatter) {
		nodes = ninfo_arr;
		for (k = 0; nodes[k] != 0; k++)
			nodes[k]->nscr.scattered = 0;
	}
	else {
#ifdef NAS /* localmod 049 */
		if ((nodes = dup_nodes(ninfo_arr, resresv->server, NO_FLAGS, 0)) == NULL) {
#else
		if ((nodes = dup_nodes(ninfo_arr, resresv->server, NO_FLAGS)) == NULL) {
#endif /* localmod 049 */
			/* only free array if we allocated it locally */
			return 0;
		}
	}

	n = -1;
	for (c = 0, chunks_needed = 0; c < spec->total_chunks && rc > 0; c++) {
		if (chunks_needed == 0) {
			n++;
			chunks_needed = spec->chunks[n]->num_chunks;
			for (k = 0; nodes[k] != 0; k++)
				nodes[k]->nscr.visited = 0;
		}

		rc = eval_simple_selspec(policy, spec->chunks[n], nodes, pl, resresv,
			flags, cur_flt_lic, &nsa, err);

		if (rc > 0) {
			while (*nsa != NULL) {
				if (!(*nsa)->ninfo->lic_lock) {
					req = find_resource_req((*nsa)->resreq, getallres(RES_NCPUS));
					if (req != NULL)
						cur_flt_lic -= req->amount;
				}

				num_nodes_used++;
				if ((*nsa)->ninfo->no_multinode_jobs)
					num_no_multi_nodes++;

				if (pl->scatter || pl->vscatter)
					(*nsa)->ninfo->nscr.scattered = 1;
				else {
					req = (*nsa)->resreq;
					while (req != NULL) {
						res = find_resource((*nsa)->ninfo->res, req->def);
						if (res != NULL)
							res->assigned += req->amount;

						req = req->next;
					}
					/* replace the dup'd node with the real one */
#ifdef NAS /* localmod 049 */
					if ((*nsa)->ninfo->rank == resresv->server->nodes_by_NASrank[(*nsa)->ninfo->NASrank]->rank)
						(*nsa)->ninfo = resresv->server->nodes_by_NASrank[(*nsa)->ninfo->NASrank];
					else
#endif /* localmod 049 */
					(*nsa)->ninfo = find_node_by_rank(ninfo_arr, (*nsa)->ninfo->rank);
				}
				nsa++;

				/* if policy is avoid provision, continue to use aoe-sorted list
				 * of nodes.
				 */
				if (conf.provision_policy != AVOID_PROVISION &&
					cstat.node_sort[0].res_name != NULL && conf.node_sort_unused)
					qsort(nodes, tot_nodes, sizeof(node_info *), multi_node_sort);
			}
			chunks_needed--;
		}
	}
	if (!(pl->scatter || pl->vscatter))
		free_nodes(nodes);

	if (num_no_multi_nodes == 0 ||
		(num_no_multi_nodes == 1 && num_nodes_used == 1))
		return rc;

	/* if we've reached this point we're a multi node job and have selected
	 * a node which requested to not be used for multi-node jobs.  We'll
	 * mark the job as a job which will use multiple nodes and use tail
	 * recursion to resatisify the job without the nodes which are marked
	 * as no multi-node jobs
	 */
	resresv->will_use_multinode = 1;
	schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, resresv->name,
		"Used multiple nodes with no_multinode_job=true: Resatisfy");
	if (nspec_arr != NULL)
		empty_nspec_array(*nspec_arr);

	return eval_complex_selspec(policy, spec, ninfo_arr, pl, resresv, flags, nspec_arr, err);
}

/**
 * @brief
 * 		eval a non-plused select spec for satisfiability
 *
 * @param[in]	policy	-	policy info
 * @param[in]	chk	-	the chunk to satisfy
 * @param[in]	pninfo_arr	-	the array of nodes
 * @param[in]	pl	-	placement information (from -l place)
 * @param[in]	resresv	-	the job the spec is from - needed for resvs
 * @param[in]	flags	-	flags to change functions behavior
 *	      					EVAL_OKBREAK - ok to break chunck up across vnodes
 *	      					EVAL_EXCLSET - allocate entire nodelist exclusively
 * @param[in]	flt_lic	-	the number of floating licenses available
 * @param[out]	nspec_arr	-	the node solution
 * @param[out]	err	-	error structure to return error information
 *
 * @return	int
 * @retval	1	: if the select spec is satisfiable
 * @retval	0	: if not
 *
 */
int
eval_simple_selspec(status *policy, chunk *chk, node_info **pninfo_arr,
	place *pl, resource_resv *resresv, unsigned int flags,
	int flt_lic, nspec ***nspec_arr, schd_error *err)
{
	int		chunks_found = 0;	/* number of nodes found to satisfy a subspec */
	nspec		*ns = NULL;		/* current nspec */
	nspec		**nsa = NULL;		/* the nspec array to hold node solution */
	resource_req	*specreq_noncons = NULL;/* non-consumable resources requested by spec */
	resource_req	*specreq_cons = NULL;	/* consumable resources requested by spec */
	resource_req	*req = NULL;		/* used to determine if we're done */
	resource_req	*prevreq = NULL;	/* used to determine if we're done */
	resource_req	*tmpreq = NULL;		/* used to unlink and free */
	char		logbuf[MAX_LOG_SIZE];
	int		need_new_nspec = 1;	/* need to allocate a new nspec for node solution */

	int		allocated = 0;		/* did we allocate resources to a vnode */
	int		nspecs_allocated = 0;	/* number of nodes allocated */
	int		i = 0;
	int		j = 0;
	int		k = 0;

	char		*str_chunk = NULL;	/* ptr to after the number of chunks in the str_chunk */

	node_info	**ninfo_arr = NULL;

	static schd_error *failerr = NULL;

	/* used for floating licensing */
	int		cur_flt_lic = 0;	/* current number of floating licenses */
	int		cur_ncpus = 0;		/* current number of ncpus left to license */
	int		licenses_allocated = 0;	/* licenses allocated to a job on a node */
	resource_req	*ncpusreq = NULL;
	resdef		*ncpusdef = find_resdef(consres, "ncpus");

	if (chk == NULL || pninfo_arr == NULL || resresv== NULL || pl == NULL || nspec_arr == NULL)
		return 0;
#ifdef NAS /* localmod 005 */
	ns = NULL;			/* quiet compiler warnings */
#endif /* localmod 005 */

	if (failerr == NULL) {
		failerr = new_schd_error();
		if(failerr == NULL) {
			set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
			return 0;
		}
	}

	/* if it's OK to break across vnodes, but we can fully fit on one
	 * vnode, then lets do that rather then possibly breaking across multiple
	 */
	if ((flags & EVAL_OKBREAK) &&
		can_fit_on_vnode(chk->req, pninfo_arr)) {
		flags &= ~EVAL_OKBREAK;
	}

	/* we need to dup the nodes to handle indirect resources which need to be
	 * accounted for between nodes allocated to the job.  The only time we
	 * need to account for for this is when we're breaking a chunks across
	 * vnodes.  Otherwise the entire chunk is going onto 1 vnode.
	 */
	if (flags & EVAL_OKBREAK) {
#ifdef NAS /* localmod 049 */
		ninfo_arr = dup_nodes(pninfo_arr, resresv->server, NO_FLAGS, 0);
#else
		ninfo_arr = dup_nodes(pninfo_arr, resresv->server, NO_FLAGS);
#endif /* localmod 049 */
		if (ninfo_arr == NULL) {
			set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
			return 0;
		}
	}
	else
		ninfo_arr = pninfo_arr;


	/* find the requested resources part of a chunk, not the number requested */
	for (i = 0; isdigit(chk->str_chunk[i]); i++)
		;

	if (chk->str_chunk[i] == ':')
		i++;

	str_chunk = &chk->str_chunk[i];

	snprintf(logbuf, MAX_LOG_SIZE, "Evaluating subchunk: %s", str_chunk);
	schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		resresv->name, logbuf);

	/* We're duplicating the entire list here.  This list is organized so that
	 * all non-consumable resources come before the consumable ones.  After
	 * duplicating, we split it into the consumable and non-consumable lists.
	 */
	specreq_noncons = dup_resource_req_list(chk->req);
	clear_schd_error(failerr);

	if (specreq_noncons == NULL) {
		set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);

		if (flags & EVAL_OKBREAK)
			free_nodes(ninfo_arr);
		return 0;
	}

	for (req = specreq_noncons; req != NULL && req->type.is_non_consumable;
		prevreq = req, req = req->next)
			;

	specreq_cons = req;
	if (prevreq != NULL)
		prevreq->next = NULL;
	else
		specreq_noncons = NULL;	/* no non-consumable resources */

	cur_flt_lic = flt_lic;

	nsa = *nspec_arr;

	for (i = 0, j = 0; ninfo_arr[i] != NULL && chunks_found == 0; i++) {
		if (ninfo_arr[i]->nscr.visited || ninfo_arr[i]->nscr.scattered  ||
			ninfo_arr[i]->nscr.ineligible)
			continue;

		allocated = 0;
		licenses_allocated = 0;
		clear_schd_error(err);
		if (ninfo_arr[i]->lic_lock || cur_flt_lic > 0) {
			if (need_new_nspec) {
				need_new_nspec = 0;
				nsa[j] = new_nspec();
				if (nsa[j] == NULL) {
					if (specreq_cons != NULL)
						free_resource_req_list(specreq_cons);
					if (specreq_noncons != NULL)
						free_resource_req_list(specreq_noncons);
					if (flags & EVAL_OKBREAK)
						free_nodes(ninfo_arr);
					set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
					return 0;
				}

				ns = nsa[j];
				j++;
				nspecs_allocated++;
			}

			if (is_vnode_eligible_chunk(specreq_noncons, ninfo_arr[i], resresv,
					err)) {
				if (!ninfo_arr[i]->lic_lock) {
					ncpusreq = find_resource_req(specreq_cons, ncpusdef);
					if (ncpusreq != NULL)
						cur_ncpus = ncpusreq->amount;
					else
						cur_ncpus = 0;
				}

				if (specreq_cons != NULL)
					allocated = resources_avail_on_vnode(specreq_cons, ninfo_arr[i],
						pl, resresv, cur_flt_lic, flags, ns, err);
				if (allocated) {
					need_new_nspec = 1;
					ns->seq_num = chk->seq_num;
					ns->sub_seq_num = get_sched_rank();

					if (flags & EVAL_OKBREAK) {
						/* search through requested consumable resources for resources we've
						 * completely allocated.  We'll unlink and free the resource_req
						 */
						prevreq = NULL;
						req = specreq_cons;
						while (req != NULL) {
							if (req->amount == 0) {
								tmpreq = req;
								if (prevreq == NULL)
									req = specreq_cons = req->next;
								else
									req = prevreq->next = req->next;

								free_resource_req(tmpreq);
							}
							else {
								prevreq = req;
								req = req->next;
							}
						}
						if (specreq_cons == NULL) {
							chunks_found = 1;
							/* we found our solution, we don't need any more nspec's */
							need_new_nspec = 0;
							ns->end_of_chunk = 1;
						}

						if (ns != NULL) {
							/* replace the dup'd node with the real one */
#ifdef NAS /* localmod 049 */
							if (ns->ninfo->rank == resresv->server->nodes_by_NASrank[ns->ninfo->NASrank]->rank)
								ns->ninfo = resresv->server->nodes_by_NASrank[ns->ninfo->NASrank];
							else
#endif /* localmod 049 */
							ns->ninfo = find_node_by_rank(pninfo_arr, ns->ninfo->rank);
						}
						if (!ninfo_arr[i]->lic_lock) {
							ncpusreq = find_resource_req(specreq_cons, ncpusdef);
							if (ncpusreq != NULL)
								licenses_allocated = cur_ncpus - ncpusreq->amount;
							else
								licenses_allocated = cur_ncpus;
						}
					}
					else {
						chunks_found = 1;
						/* we found our solution, we don't need any more nspec's */
						need_new_nspec = 0;
						ns->end_of_chunk = 1;

						if (!ninfo_arr[i]->lic_lock) {
							ncpusreq = find_resource_req(specreq_noncons, ncpusdef);
							if (ncpusreq != NULL)
								licenses_allocated = ncpusreq->amount;
							else
								licenses_allocated = 0;
						}
					}
				}
				else {
					ninfo_arr[i]->nscr.visited = 1;
					if (failerr->status_code == SCHD_UNKWN)
						move_schd_error(failerr, err);
				}
			}
			else {
				ninfo_arr[i]->nscr.visited = 1;
				if (failerr->status_code == SCHD_UNKWN)
					move_schd_error(failerr, err);
			}

			if (licenses_allocated > 0)
				cur_flt_lic -= licenses_allocated;
		}
		else
			set_schd_error_codes(err, NOT_RUN, NODE_UNLICENSED);

		if (err->error_code) {
			schdlogerr(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
				ninfo_arr[i]->name, NULL, err);
			/* Since this node is not eligible, check if it ever eligible
			 * If it is never eligible, mark all nodes like it visited.
			 * If we can break, don't bother with equivalence classes because
			 * because the chunk is pretty much equivalent to ncpus=1 at that point
			 */
			if (ninfo_arr[i]->nodesig_ind >= 0 && !(flags & EVAL_OKBREAK)) {
				if (check_avail_resources(ninfo_arr[i]->res, chk->req,
					COMPARE_TOTAL | UNSET_RES_ZERO | CHECK_ALL_BOOLS,
					policy->resdef_to_check_no_hostvnode,
					INSUFFICIENT_RESOURCE, err) == 0) {
					for (k = 0; ninfo_arr[k] != NULL; k++)
						if (ninfo_arr[k]->nodesig_ind == ninfo_arr[i]->nodesig_ind)
							ninfo_arr[k]->nscr.visited = 1;
				}
			}

		}
		else {
			schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
				ninfo_arr[i]->name, "Node allocated to job");
		}
	}

	nsa[j] = NULL;

	if (specreq_cons != NULL)
		free_resource_req_list(specreq_cons);
	if (specreq_noncons != NULL)
		free_resource_req_list(specreq_noncons);

	if (flags & EVAL_OKBREAK)
		free_nodes(ninfo_arr);

	if (chunks_found) {
		snprintf(logbuf, MAX_LOG_SIZE, "Allocated one subchunk: %s", str_chunk);
		schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			resresv->name, logbuf);
		clear_schd_error(err);
		return 1;
	}

	/* If we didn't allocate any nodes, we need to clean up any nspecs
	 * we've allocated.  This is either the one we allocated in the front of
	 * the main loop above, or for all the nodes we allocated and need to
	 * "deallocate" due to a reason we've decided we can't allocate like exclhost
	 */
	for (i = 0; i < nspecs_allocated; i++) {
		free_nspec(nsa[i]);
		nsa[i] = NULL;
	}

	snprintf(logbuf, MAX_LOG_SIZE, "Failed to satisfy subchunk: %s",
		chk->str_chunk);
	schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		resresv->name, logbuf);

	/* If the last node we looked at was fine, err would be empty.
	 * Actually return an a real error */
	if (err->status_code == SCHD_UNKWN && failerr->status_code != SCHD_UNKWN)
		move_schd_error(err, failerr);
	/* don't be so specific in the comment since it's only for a single node*/
	free(err->arg1);
	err->arg1 = NULL;

	return 0;
}

/**
 * @brief
 * 		evaluate one node to see if it is eligible
 *			    for a simple select spec and return the number
 *			    of chunks it can satisfy
 *
 * @param[in]	specreq	-	resources in the select spec
 * @param[in]	node	-	the node to evaluate
 * @param[in]	pl	-	place spec for request
 * @param[in]	resresv	-	resource resv which is requesting
 * @param[in]	flags	-	flags to change behavior of function
 *							EVAL_OKBREAK - OK to break chunk across vnodes
 * @param[out]	err	-	error status if node is ineligible
 *
 * @par NOTE:
 * 		all resources in specreq will be honored regardless of
 *      whether they are in conf.res_to_check or not due to the fact
 *		that chunk resources only contain such resources.
 *
 * @retval	1	: if node is statically eligible to run the request
 * @retval	0	: if node is ineligible
 *
 */
int
is_vnode_eligible(node_info *node, resource_resv *resresv,
	struct place *pl, schd_error *err)
{
	if (node == NULL || resresv == NULL || pl == NULL || err == NULL)
		return 0;

	/* A node is invalid for an exclusive job if jobs/resvs are running on it
	 * NOTE: this check must be the first check or exclhost may break
	 */
	if (is_excl(pl, node->sharing) &&
		(node->num_jobs > 0 || node->num_run_resv > 0)) {
		set_schd_error_codes(err, NOT_RUN, NODE_NOT_EXCL);
		set_schd_error_arg(err, ARG1, resresv->is_job ? "Job":"Reservation");
		return 0;
	}

	/* Does this chunk have AOE? */
	if (resresv->aoename != NULL) {
		if (!is_aoe_avail_on_vnode(node, resresv)) {
			set_schd_error_codes(err, NOT_RUN, AOE_NOT_AVALBL);
			set_schd_error_arg(err, ARG1, resresv->aoename);
			return 0;
		}
	}

	/* Does this chunk have EOE? */
	if (resresv->eoename != NULL) {
		if (!is_eoe_avail_on_vnode(node, resresv)) {
			set_schd_error_codes(err, NOT_RUN, EOE_NOT_AVALBL);
			set_schd_error_arg(err, ARG1, resresv->eoename);
			return 0;
		}
	}

	if (!node->is_free) {
		set_schd_error_codes(err, NOT_RUN, INVALID_NODE_STATE);
		set_schd_error_arg(err, ARG1, (char*) node_state_to_str(node));
#ifdef NAS /* localmod 031 */
		set_schd_error_arg(err, ARG2, node->name);
#endif /* localmod 031 */
		return 0;
	}

	/*
	 * If we are in the reservation's universe, we need to check the state of
	 * the node in the server's universe.  We may have provisioned the node
	 * and it could be down.
	 */
	if (resresv->job != NULL && resresv->job->resv != NULL) {
		if (node->svr_node != NULL) {
			if (node->svr_node->is_provisioning) {
				set_schd_error_codes(err, NOT_RUN, INVALID_NODE_STATE);
#ifdef NAS /* localmod 031 */
				set_schd_error_arg(err, ARG1, node->name);
				set_schd_error_arg(err, ARG2, node_state_to_str(node->svr_node));
#else
				set_schd_error_arg(err, ARG1, (char*) node_state_to_str(node->svr_node));
#endif /* localmod 031 */
				return 0;
			}
		}
	}

	if (resresv->is_resv && !node->resv_enable) {
		set_schd_error_codes(err, NOT_RUN, NODE_RESV_ENABLE);
		return 0;
	}

	if (resresv->is_job) {
		/* don't enforce max run limits of job is being qrun */
		if (resresv->server->qrun_job ==NULL) {
			if (node->max_running != SCHD_INFINITY &&
			    node->max_running <= node->num_jobs) {
				set_schd_error_codes(err, NOT_RUN, NODE_JOB_LIMIT_REACHED);
				return 0;
			}

			if (node->max_user_run != SCHD_INFINITY &&
			    node->max_user_run <= find_counts_elm(node->user_counts, resresv->user, NULL)) {
				set_schd_error_codes(err, NOT_RUN, NODE_USER_LIMIT_REACHED);
				return 0;
			}

			if (node->max_group_run != SCHD_INFINITY &&
			    node->max_group_run <= find_counts_elm(node->group_counts, resresv->group, NULL)) {
				set_schd_error_codes(err, NOT_RUN, NODE_GROUP_LIMIT_REACHED);
				return 0;
			}
		}

	}

	if (node->no_multinode_jobs && resresv->will_use_multinode) {
		set_schd_error_codes(err, NOT_RUN, NODE_NO_MULT_JOBS);
		return 0; /* multiple nodes jobs/resvs not allowed on this node */
	}

	return 1;
}
/**
 * @brief
 * 		check if a vnode is eligible for a chunk
 *
 * @param[in]	specreq	-	resources from chunk
 * @param[in]	node	-	vnode tocheck
 * @param[out]	err	-	error structure
 *
 * @return	int
 * @retval	1	: eligible
 * @retval	0	: not eligible
 */
int
is_vnode_eligible_chunk(resource_req *specreq, node_info *node,
		resource_resv *resresv, schd_error *err)
{
	if (resresv != NULL) {
		if (node->no_multinode_jobs && resresv->will_use_multinode) {
			set_schd_error_codes(err, NOT_RUN, NODE_NO_MULT_JOBS);
			return 0; /* multiple nodes jobs/resvs not allowed on this node */
		}
	}

	if (specreq != NULL) {
		if (check_avail_resources(node->res, specreq,
				CHECK_ALL_BOOLS | ONLY_COMP_NONCONS | UNSET_RES_ZERO, NULL,
				INSUFFICIENT_RESOURCE, err) == 0) {
			return 0;
		}
	}

	return 1;
}

/**
 * @brief
 *	Checks if a vnode is eligible for power operations.
 *  Based on is_provisionable.
 *
 * @par Functionality:
 *	This function checks if a vnode is eligible to be provisioned.
 *	A vnode is eligible for power operations if it satisfies all of the
 *	following conditions:-
 *	(1) Server has power_provisioning True,
 *	(2) Vnode has power_provisioning True,
 *	(3) No conflicts with reservations already running on the Vnode
 *	(4) No conflicts with jobs already running on the Vnode
 *
 * @param[in]		node	-	pointer to node_info
 * @param[in]		resresv	-	pointer to resource_resv
 * @param[in,out]	err		-	pointer to schd_error
 *
 * @return	int
 * @retval	 NO_PROVISIONING_NEEDED : resresv doesn't request eoe
 *			or resresv is not a job
 * @retval	 PROVISIONING_NEEDED : vnode doesn't have current_eoe set
 *          or it doesn't match job eoe
 * @retval	 NOT_PROVISIONABLE  : vnode is not provisionable
 *			(see err for more details)
 *
 * @par Side Effects:
 *	Unknown
 *
 * @par MT-safe: No
 *
 */
int
is_powerok(node_info *node, resource_resv *resresv, schd_error *err)
{
	int i;
	int ret = NO_PROVISIONING_NEEDED;

	if (!resresv->is_job)
		return NO_PROVISIONING_NEEDED;
	if (resresv->eoename == NULL)
		return NO_PROVISIONING_NEEDED;
	if (!resresv->server->power_provisioning) {
		err->error_code = PROV_DISABLE_ON_SERVER;
		return NOT_PROVISIONABLE;
	}
	if (!node->power_provisioning) {
		err->error_code = PROV_DISABLE_ON_NODE;
		return NOT_PROVISIONABLE;
	}

	/* node doesn't have eoe or it doesn't match job eoe */
	if (node->current_eoe == NULL ||
			strcmp(resresv->eoename, node->current_eoe) != 0) {
		ret = PROVISIONING_NEEDED;

		/* there can't be any jobs on the node */
		if ((node->num_susp_jobs > 0) || (node->num_jobs > 0)) {
			err->error_code = PROV_RESRESV_CONFLICT;
			return NOT_PROVISIONABLE;
		}
	}

	/* node cannot be shared between running reservation without EOE
	 * and job with EOE
	 */
	if (node->run_resvs_arr) {
		for (i = 0; node->run_resvs_arr[i]; i++) {
			if (node->run_resvs_arr[i]->eoename == NULL) {
				err->error_code = PROV_RESRESV_CONFLICT;
				return NOT_PROVISIONABLE;
			}
		}
	}

	return ret;
}

/**
 * @brief
 * 		check to see if there are enough
 *		consumable resources on a vnode to make it
 *		eligible for a request
 *		Note: This function will allocate <= 1 chunk
 *
 * @param[in][out] specreq_cons - IN : requested consumable resources
 *				 				  OUT: requested - allocated resources
 * @param[in]	node	-	the node to evaluate
 * @param[in]	pl	-	place spec for request
 * @param[in]	resresv	-	resource resv which is requesting
 * @param[in]	cur_flt_lic	-	current number of PBS licenses available
 * @param[in]	flags	-	flags to change behavior of function
 *              			EVAL_OKBREAK - OK to break chunk across vnodes
 * @param[out]	err	-	error status if node is ineligible
 *
 *	@retval	1	: if resources were allocated from the node
 *	@retval 0	: if sufficent resources are not available (err is set)
 */
int
resources_avail_on_vnode(resource_req *specreq_cons, node_info *node,
	place *pl, resource_resv *resresv, int cur_flt_lic, unsigned int flags,
	nspec *ns, schd_error *err)
{
	/* used for allocating partial chunks */
	resource_req tmpreq = {0};
	resource_req *req;
	resource_req *newreq, *aoereq;
	schd_resource *res;
	sch_resource_t num;
	sch_resource_t amount;
	int allocated = 0;
	long long num_chunks = 0;
	int is_p;

	char logbuf[MAX_LOG_SIZE];

	if (specreq_cons == NULL || node == NULL ||
		resresv == NULL || pl == NULL || err == NULL)
		return 0;

	if (flags & EVAL_OKBREAK) {
		/* req is the first consumable resource at this point */
		for (req = specreq_cons; req != NULL; req = req->next) {
			if (req->type.is_consumable) {
				num = req->amount;
				tmpreq.amount = 1;

				tmpreq.name = req->name;
				tmpreq.type = req->type;
				tmpreq.res_str = req->res_str;
				tmpreq.def = req->def;
				tmpreq.next = NULL;
				num_chunks = check_resources_for_node(&tmpreq, node, resresv, err);

				if (!node->lic_lock && (cur_flt_lic < num_chunks) &&
					!strcmp(req->name, "ncpus"))
					/* if we can allocate more cpus than we have floating licenses,
				 * we will allocate the number of floating licenses we have.  It
				 * is still possible that more nodelocked licensed nodes are farther
				 * down the node list and we can still satisfy the request.
				 */
					num_chunks = cur_flt_lic;

				if (num_chunks > 0) {
					is_p = is_provisionable(node, resresv, err);
					if (is_p == NOT_PROVISIONABLE) {
						allocated = 0;
						break;
					}
					else if (is_p == PROVISIONING_NEEDED) {
						if (ns != NULL)
							ns->go_provision = 1;
						if (resresv->select->total_chunks >1)
							set_current_aoe(node, resresv->aoename);

						if (resresv->is_job) {
							sprintf(logbuf, "Vnode %s selected for provisioning with AOE %s",
								node->name, resresv->aoename);
							schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_NOTICE,
								resresv->name, logbuf);
						}
					}

					/* check if power eoe needs to be considered */
					is_p = is_powerok(node, resresv, err);
					if (is_p == NOT_PROVISIONABLE) {
						allocated = 0;
						break;
					}
					else if (is_p == PROVISIONING_NEEDED) {
						if (resresv->select->total_chunks > 1)
							set_current_eoe(node, resresv->eoename);

						if (resresv->is_job) {
							snprintf(logbuf, sizeof(logbuf),
								"Vnode %s selected for power with EOE %s",
								node->name, resresv->eoename);
							schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB,
								LOG_NOTICE, resresv->name, logbuf);
						}
					}

					if (num_chunks > num)
						num_chunks = num;

					amount = num_chunks;

					if (ns != NULL) {
						newreq = dup_resource_req(req);
						if (newreq == NULL)
							return 0;

						newreq->amount = amount;

						if (ns->ninfo == NULL) /* check if this is the first res */
							ns->ninfo = node;

						newreq->next = ns->resreq;
						ns->resreq = newreq;
					}

					/* now that we have allocated some resources to this node, we need
					 * to remove them from the requested amount
					 */
					req->amount -= amount;

					res = find_resource(node->res, req->def);
					if (res != NULL) {
						if (res->indirect_res != NULL)
							res->indirect_res->assigned += amount;
						else
							res->assigned += amount;
					}

					/* use tmpreq to wrap the amount so we can use res_to_str */
					tmpreq.amount = amount;
					sprintf(logbuf, "vnode allocated %s=%s",
						req->name, res_to_str(&tmpreq, RF_REQUEST));
					schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
						node->name, logbuf);

					allocated = 1;
				}
			}
		}
		if (allocated) {
			if (ns != NULL && ns->go_provision != 0) {
				aoereq = create_resource_req("aoe", resresv->aoename);
				if (aoereq != NULL) {
					aoereq->next = ns->resreq;
					ns->resreq = aoereq;
				}
			}

			if (pl->pack && num_chunks == 1 && cstat.smp_dist == SMP_ROUND_ROBIN)
				strcpy(last_node_name, node->name);
			return 1;
		}
	}
	else {
		num_chunks = check_resources_for_node(specreq_cons, node, resresv, err);

		if (num_chunks > 0) {
			is_p = is_provisionable(node, resresv, err);
			if (is_p == NOT_PROVISIONABLE)
				return 0;
			else if (is_p == PROVISIONING_NEEDED) {
				if (ns != NULL)
					ns->go_provision = 1;
				if (resresv->select->total_chunks >1) {
					set_current_aoe(node, resresv->aoename);
				}
			}

			is_p = is_powerok(node, resresv, err);
			if (is_p == NOT_PROVISIONABLE)
				return 0;
			else if (is_p == PROVISIONING_NEEDED) {
				if (resresv->select->total_chunks > 1) {
					set_current_eoe(node, resresv->eoename);
				}
			}
		}

		if (!node->lic_lock) {
			req = find_resource_req(specreq_cons, getallres(RES_NCPUS));
			if (req != NULL)
				num = req->amount;
			else
				num = 0;
			if (cur_flt_lic < num) {
				num_chunks = 0;
				set_schd_error_codes(err, NOT_RUN, NODE_UNLICENSED);
			}
		}

		/* if we have infinite amount of resources, the node has been allocated */
		if (num_chunks == SCHD_INFINITY)
			num_chunks = 1;

		if (ns != NULL && num_chunks != 0) {
			ns->ninfo = node;
			ns->resreq = dup_resource_req_list(specreq_cons);

			if (ns->go_provision != 0) {
				aoereq = create_resource_req("aoe", resresv->aoename);
				if (aoereq != NULL) {
					aoereq->next = ns->resreq;
					ns->resreq = aoereq;
				}
			}

			if (pl->pack && cstat.smp_dist == SMP_ROUND_ROBIN)
				strcpy(last_node_name, node->name);
		}
		return num_chunks;
	}

	return 0;
}

/**
 * @brief
 * 		check to see how many chunks can fit on a
 *		node looking at both resources available
 *		now and future advanced reservations
 *
 * @param[in]	resreq	-	requested resources
 * @param[in]	node    -	node to check for
 * @param[in]	resresv -	the resource resv to check for
 * @param[out]	err    -	schd_error reply if there aren't enough resources
 *
 * @par NOTE:
 * 		all resources in resreq will be honored regardless of
 *      whether they are in conf.res_to_check or not due to the fact
 *		that chunk resources only contain such resources.
 *
 * @retval
 * 		number of chunks which can be satisifed during the duration
 * @retval	-1	: on error
 */
long long
check_resources_for_node(resource_req *resreq, node_info *ninfo,
	resource_resv *resresv, schd_error *err)
{
	/* the minimum number of chunks which can be satisified for the duration
	 * of the request
	 */
	long long min_chunks = UNSPECIFIED;
	long long chunks = UNSPECIFIED;   /*number of chunks which can be satisfied*/
	int resresv_excl = 0;
	resource_req *req;
	schd_resource *nres;
	schd_resource *cur_res;
	event_list *calendar;

	schd_resource *noderes;

	time_t event_time = 0;
	time_t cur_time;
	time_t end_time;
	int is_run_event;

	int loadcmp;	/* used for load comparison */

	nspec *ns;
	timed_event *event;
	unsigned int event_mask;
	int i;
	char logbuf[MAX_LOG_SIZE];

	if (resreq == NULL || ninfo == NULL || err == NULL || resresv == NULL)
		return -1;

	noderes = ninfo->res;

	/* don't enforce max load if job is being qrun */
	if (cstat.load_balancing && resresv->server->qrun_job ==NULL) {
		req = find_resource_req(resreq, getallres(RES_NCPUS));
		if (req != NULL && req->amount > 0) {
			/* here we calculate the number of "loadcpus".  Basically this is
			 * the number of cpus we have available if we consider 1 cpu to be
			 * 1 in the loadave.  We need to take the max with 0 just in case
			 * the loadave is higher then the max_load.  This is cast into an
			 * int because we need an integer amount of cpus.
			 */
			loadcmp = (int) IF_NEG_THEN_ZERO(ninfo->max_load - ninfo->loadave);
			chunks = ceil(loadcmp / req->amount);
		}

		if (chunks == 0)
			set_schd_error_codes(err, NOT_RUN, NODE_HIGH_LOAD);
	}

	min_chunks = check_avail_resources(noderes, resreq,
		CHECK_ALL_BOOLS|UNSET_RES_ZERO, NULL, INSUFFICIENT_RESOURCE, err);

	if (chunks != UNSPECIFIED && (min_chunks == SCHD_INFINITY || chunks < min_chunks))
		min_chunks = chunks;

	calendar = ninfo->server->calendar;
	cur_time = ninfo->server->server_time;
	if(resresv->duration != resresv->hard_duration &&
	   exists_resv_event(calendar, cur_time + resresv->hard_duration))
		end_time = cur_time + calc_time_left(resresv, 1);
	else
		end_time = cur_time + calc_time_left(resresv, 0);

	/* check if there are any timed events to check for conflicts with. We do not
	 * need to check for timed conflicts if the current object is a job inside a
	 * reservation.
	 */
	if (min_chunks > 0 && calendar != NULL && exists_run_event(calendar, end_time)
		&& !(resresv->job != NULL && resresv->job->resv != NULL)) {
		/* Check for possible conflicts with timed events by walking the sorted
		 * event list that was created in eval_selspec. This runs a simulation
		 * forward in time to account for timed events consuming and/or releasing
		 * resources.
		 *
		 * For example, if a resource_resv such as a reservation is consuming n cpus
		 * from t1 to t2, then the resources should be taken out at t1 and returned
		 * at t2.
		 */
		nres = dup_ind_resource_list(noderes);
		resresv_excl = is_excl(resresv->place_spec, ninfo->sharing);

		if (nres != NULL) {
			resource_resv *resc_resv;

			/* Walk the event list by time such that the start of an event always
			 * precedes the end of it. The event type (start or end event) is
			 * determined, and the resources are consumed if a start event, and
			 * released if an end event.
			 */
			event = get_next_event(calendar);
			event_mask = TIMED_RUN_EVENT | TIMED_END_EVENT;

			for (event = find_init_timed_event(event, IGNORE_DISABLED_EVENTS, event_mask);
				event != NULL && min_chunks > 0;
				event = find_next_timed_event(event, IGNORE_DISABLED_EVENTS, event_mask)) {
				event_time = event->event_time;
				resc_resv = (resource_resv *) event->event_ptr;

				if (event_time < cur_time)
					continue;
				if (resc_resv->job != NULL && resc_resv->job->resv != NULL)
					continue;

				if (resc_resv->nspec_arr != NULL) {
					for (i = 0; resc_resv->nspec_arr[i] != NULL &&
						resc_resv->nspec_arr[i]->ninfo->rank != ninfo->rank; i++)
						;
					ns = resc_resv->nspec_arr[i];
				}
				else {
					ns = NULL;
					snprintf(logbuf, MAX_LOG_SIZE,
						"Event %s is a run/end event w/o nspec array, ignoring event",
						event->name);
					schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_SCHED, LOG_WARNING,
						resresv->name, logbuf);
				}

				is_run_event = (event->event_type == TIMED_RUN_EVENT);


				/* Normally when one job starts immediately after another (J1 end time == J2 start time)
				 * we have no conflict between the two jobs.  When jobs do not request walltime,
				 * they all have the same (5yr) walltime and fall one after another.
				 * Using <= instead of < has the same effect as the jobs having a 1 second overlap.
				 * Now all non-walltime jobs will overlap with the job before it and cause calendaring to occur.
				 */
				if (((resresv->duration == FIVE_YRS)?(event_time <= end_time):(event_time < end_time))
					&& resresv != resc_resv && ns != NULL) {
					/* One event will need provisioning while the other will not,
					 * they cannot co exist at same time.
					 */
					if (resresv->aoename != NULL && resc_resv->aoename ==NULL) {
						set_schd_error_codes(err, NOT_RUN, PROV_RESRESV_CONFLICT);
						min_chunks = 0;
						break;
					}

					if (is_excl(resc_resv->place_spec, ninfo->sharing) ||resresv_excl) {
						min_chunks = 0;
					}
					else {
						cur_res = nres;
						while (cur_res != NULL) {
							if (cur_res->type.is_consumable) {
								req = find_resource_req(ns->resreq, cur_res->def);
								if (req != NULL) {
									cur_res->assigned += is_run_event ? req->amount : -req->amount;
								}
							}
							cur_res = cur_res->next;
						}
						if (is_run_event) {
							chunks = check_avail_resources(nres, resreq,
								CHECK_ALL_BOOLS|UNSET_RES_ZERO, NULL,
								INSUFFICIENT_RESOURCE, err);
							if (chunks < min_chunks)
								min_chunks = chunks;
						}
					}
				}
			}
			free_resource_list(nres);
		}
		else {
			set_schd_error_codes(err, NOT_RUN, SCHD_ERROR);
			return -1;
		}

		if (min_chunks == 0) {
			if (err->error_code != PROV_RESRESV_CONFLICT)
				set_schd_error_codes(err, NOT_RUN, RESERVATION_CONFLICT);
		}
	}

	return min_chunks;
}

/**
 * @brief compare two place specs to see if they are equal
 * @param[in] pl1 - place spec 1
 * @param[in] pl2 - place spec 2
 * @return  1 if equal 0 if not
 */
int
compare_place(place *pl1, place *pl2)
{
	if (pl1 == NULL && pl2 == NULL)
		return 1;
	else if (pl1 == NULL || pl2 == NULL)
		return 0;

	if (pl1->excl != pl2->excl)
		return 0;

	if (pl1->exclhost != pl2->exclhost)
		return 0;

	if (pl1->share != pl2->share)
		return 0;

	if (pl1->free != pl2->free)
		return 0;

	if (pl1->pack != pl2->pack)
		return 0;

	if (pl1->scatter != pl2->scatter)
		return 0;

	if (pl1->vscatter != pl2->vscatter)
		return 0;

	if (pl1->group != NULL && pl2->group != NULL) {
		if (strcmp(pl1->group, pl2->group))
			return 0;
	} else if (pl1->group != NULL || pl2->group != NULL)
		return 0;

	return 1;
}

/**
 * @brief
 *		parse_placespec - allocate a new place structure and parse
 *		a placement spec (-l place)
 *
 * @param[in]	place_str	-	placespec as a string
 *
 * @return	newly allocated place
 * @retval	NULL	: invalid placement spec
 *
 */
place *
parse_placespec(char *place_str)
{
	/* copy place spec into - max log size should be big enough */
	char str[MAX_LOG_SIZE];
	char *tok;
	char *tokptr;
	int invalid = 0;
	place *pl;

	if (place_str == NULL)
		return NULL;

	pl = new_place();

	if (pl == NULL)
		return NULL;

	strcpy(str, place_str);

	tok = string_token(str, ":", &tokptr);

	while (tok != NULL && !invalid) {
		if (!strcmp(tok, PLACE_Pack)  )
			pl->pack = 1;
		else if (!strcmp(tok, PLACE_Scatter)  )
			pl->scatter = 1;
		else if (!strcmp(tok, PLACE_Excl)  )
			pl->excl = 1;
		else if (!strcmp(tok, PLACE_Free))
			pl->free = 1;
		else if (!strcmp(tok, PLACE_Shared))
			pl->share = 1;
		else if (!strcmp(tok, PLACE_VScatter))
			pl->vscatter = 1;
		else if (!strcmp(tok, PLACE_ExclHost)) {
			pl->exclhost = 1;
			pl->excl = 1;
		}
		else if (!strncmp(tok, PLACE_Group, 5)) {
			/* format: group=res */
			if (tok[5] == '=') {
				/* "group=" is 6 characters so tok[6] should be the first character of
				 * the resource
				 */
				pl->group = string_dup(&tok[6]);
			}
			else
				invalid = 1;
		}
		else
			invalid = 1;

		tok = string_token(NULL, ":", &tokptr);
	}

	/* pack and scatter vscatter, and free are all mutually exclusive */
	if (pl->pack + pl->scatter + pl->free  + pl->vscatter> 1  )
		invalid = 1;

	/* if no scatter, vscatter, pack, or free given, default to free */
	if (pl->pack + pl->scatter + pl->free  + pl->vscatter== 0)
		pl->free = 1;

	if (invalid) {
		free_place(pl);
		return NULL;
	}

	return pl;
}

/**
 * @brief
 * 		parse a select spec into a selspec structure with
 *		a dependant array of chunks.  Non-consuamble resources
 *		are sorted first in the chunk resource list
 *
 * @param[in]	selspec	-	the select spec to parse
 *
 * @return	selspec*
 * @retval	pointer to a selspec obtained by parsing the select spec
 *			of the job/resv.
 * @retval	NULL	: on error or invalid spec
 *
 * @par MT-safe: No
 */
selspec *
parse_selspec(char *select_spec)
{
	/* select specs can be large.  We need to allocate a buffer large enough
	 * to handle the spec.  We'll keep it around so we don't have to allocate
	 * it on every call
	 */
	static char *specbuf = NULL;
	static int specbuf_size = 0;
	int s;
	char *tmpptr;

	selspec *spec;
	int num_plus;
	char *p;

	char *tok;
	char *endp = NULL;

	resource_req *req_head = NULL;
	resource_req *req_end = NULL;
	resource_req *req;
	int ret;
	int invalid = 0;

	int num_kv;
	struct key_value_pair *kv;

	int num_chunks;
	int num_cpus = 0;

	int seq_num = 0;

	int i;
	int n = 0;

	if (select_spec == NULL)
		return NULL;

	if ((spec = new_selspec()) == NULL)
		return NULL;

	for (num_plus = 0, p = select_spec; *p != '\0'; p++) {
		if (*p == '+')
			num_plus++;
	}

	/* num_plus + 2: 1 for the initial chunk 1 for the NULL ptr */
	if ((spec->chunks = calloc(num_plus + 2, sizeof(chunk *))) == NULL) {
		log_err(errno, "parse_selspec", MEM_ERR_MSG);
		free_selspec(spec);
	}

	s = strlen(select_spec);
	if (s > specbuf_size) {
		tmpptr = realloc(specbuf, s * 2 + 1);
		if (tmpptr == NULL) {
			log_err(errno, "parse_selspec", MEM_ERR_MSG);
			return 0;
		}
		specbuf_size = s * 2;
		specbuf = tmpptr;
	}

	strcpy(specbuf, select_spec);

	tok = string_token(specbuf, "+", &endp);

	tmpptr = NULL;
	while (tok != NULL && !invalid) {
		tmpptr = string_dup(tok);
#ifdef NAS /* localmod 082 */
		ret = parse_chunk(tok, 0, &num_chunks, &num_kv, &kv, NULL);
#else
		ret = parse_chunk(tok, &num_chunks, &num_kv, &kv, NULL);
#endif /* localmod 082 */

		if (!ret) {
			for (i = 0; i < num_kv && !invalid; i++) {
				req = create_resource_req(kv[i].kv_keyw, kv[i].kv_val);

				if (req == NULL)
					invalid = 1;
				else  {
						if (strcmp(req->name, "ncpus") == 0) {
							/* Given: -l select=nchunk1:ncpus=Y + nchunk2:ncpus=Z +... */
							/* Then: # of cpus = (nchunk1 * Y) + (nchunk2 * Z) + ... */
							num_cpus += (num_chunks * req->amount);
						}
					if (!invalid && (req->type.is_boolean || conf.res_to_check == NULL ||
						find_string(conf.res_to_check, kv[i].kv_keyw))) {
						if (!resdef_exists_in_array(spec->defs, req->def))
							add_resdef_to_array(&(spec->defs), req->def);
						if (req_head == NULL)
							req_end = req_head = req;
						else {
							if (req->type.is_consumable) {
								req_end->next = req;
								req_end = req;
							}
							else {
								req->next = req_head;
								req_head = req;
							}
						}
					}
					else
						free_resource_req(req);
				}
			}
			spec->chunks[n] = new_chunk();
			if (spec->chunks[n] != NULL) {
				spec->chunks[n]->num_chunks = num_chunks;
				spec->chunks[n]->seq_num = seq_num;
				spec->total_chunks += num_chunks;
				spec->total_cpus = num_cpus;
				spec->chunks[n]->req = req_head;
				spec->chunks[n]->str_chunk = tmpptr;
				tmpptr = NULL;
				req_head = NULL;
				req_end = NULL;
				n++;
			}
			else
				invalid = 1;
		}
		else
			invalid = 1;

		tok = string_token(NULL, "+", &endp);
		seq_num++;
	}

	if (invalid) {
		free_selspec(spec);
		if (tmpptr != NULL)
			free(tmpptr);

		return NULL;
	}

	return spec;
}

/**
 *	@brief compare two chunks for equality
 *	@param[in] c1 - first chunk
 * 	@param[in] c2 - second chunk
 *
 *	@return int
 *	@retval 1 if chunks are equal
 *	@retval 0 if chunks are not equal
 */
int compare_chunk(chunk *c1, chunk *c2) {
	if (c1 == NULL && c2 == NULL)
		return 1;
	if (c1 == NULL || c2 == NULL)
		return 0;

	if (c1->num_chunks != c2->num_chunks)
		return 0;
	if(compare_resource_req_list(c1->req, c2->req, NULL) == 0)
		return 0;
	if(c1->seq_num != c2->seq_num)
		return 0;

	return 1;
}

/**
 *	@brief compare two selspecs for equality
 *	@param[in] s1 - first selspec
 *	@param[in] s2 - second selspec
 *
 *	@returns int
 *	@retval 1 if selspecs are equal
 *	@retval 0 if not equal
 */
int compare_selspec(selspec *s1, selspec *s2) {
	int i;
	int ret = 1;

	if(s1 == NULL && s2 == NULL)
		return 1;
	else if(s1 == NULL || s2 == NULL)
		return 0;

	if(s1->total_chunks != s2->total_chunks)
		return 0;

	if (s1->chunks != NULL && s2->chunks != NULL) {
		for (i = 0; ret && s1->chunks[i] != NULL; i++) {
			if (compare_chunk(s1->chunks[i], s2->chunks[i]) == 0)
				ret = 0;
		}
	} else
		ret = 0;
	return ret;
}

/**
 * @brief
 * 		create an execvnode from a node solution array
 *
 * @param[in]	ns	-	the nspec struct with the chosen nodes to run the job on
 *
 * @par MT-safe:	no
 *
 * @return	execvnode in static memory
 *
 */
char *
create_execvnode(nspec **ns)
{
	static char *execvnode = NULL;
	static int execvnode_size = 0;
	static char *buf = NULL;
	static int bufsize = 0;
	char buf2[128];
	resource_req *req;
	int end_of_chunk = 1;
	int i;

	if (ns == NULL)
		return NULL;

	if (execvnode == NULL) {
		execvnode = malloc(INIT_ARR_SIZE + 1);

		if (execvnode == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			return NULL;
		}
		execvnode_size = INIT_ARR_SIZE;
	}
	if (buf == NULL) {
		buf = malloc(INIT_ARR_SIZE + 1);
		if (buf == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			return NULL;
		}
		bufsize = INIT_ARR_SIZE;
	}
	execvnode[0] = '\0';

	for (i = 0; ns[i] != NULL; i++) {
		if (i > 0)
			strcpy(buf, "+");
		else
			buf[0] = '\0';

		if (end_of_chunk) {
			if (pbs_strcat(&buf, &bufsize, "(") == NULL)
				return NULL;
		}

		if (pbs_strcat(&buf, &bufsize, ns[i]->ninfo->name) ==NULL)
			return NULL;

		end_of_chunk = ns[i]->end_of_chunk;

		req = ns[i]->resreq;
		while (req  != NULL) {
			if (req->type.is_consumable) {
				if (pbs_strcat(&buf, &bufsize, ":") == NULL)
					return NULL;
				if (pbs_strcat(&buf, &bufsize, req->name) == NULL)
					return NULL;
				if (req->type.is_float)
					sprintf(buf2, "=%.*f", float_digits(req->amount, FLOAT_NUM_DIGITS), req->amount);
				else

					sprintf(buf2, "=%.0lf%s", ceil(req->amount),
						req->type.is_size ? "kb" : "");
				if (pbs_strcat(&buf, &bufsize, buf2) == NULL)
					return NULL;
			}
			else if (ns[i]->go_provision && strcmp(req->name, "aoe") ==0) {
				strcpy(buf2, ":aoe=");
				if (pbs_strcat(&buf, &bufsize, buf2) == NULL)
					return NULL;
				if (pbs_strcat(&buf, &bufsize, req->res_str) == NULL)
					return NULL;
			}
			req = req->next;
		}
		if (end_of_chunk)
			if (pbs_strcat(&buf, &bufsize, ")") == NULL)
				return NULL;

		if (pbs_strcat(&execvnode, &execvnode_size, buf) == NULL)
			return NULL;
	}

	return execvnode;
}

/**
 * @brief
 *		parse_execvnode - parse an execvnode into an nspec array
 *
 * @param[in]	execvnode	-	the execvnode to parse
 * @param[in]	sinfo	-	server to get the nodes from
 *
 * @return	a newly allocated nspec array for the execvnode
 *
 */
nspec **
parse_execvnode(char *execvnode, server_info *sinfo)
{
	char *simplespec;
	char *node_name;
	int num_el;
	struct key_value_pair *kv;

	nspec **nspec_arr;
	node_info *ninfo;
	resource_req *req;
	int i, j;
	int ret;

	int invalid = 0;

	int num_chunk;
	char *p;
	char logbuf[256];

	if (execvnode == NULL || sinfo == NULL)
		return NULL;

	p = execvnode;

	/* number of chunks is number of pluses + 1 */
	num_chunk = 1;

	while (p != NULL && *p != '\0') {
		if (*p == '+')
			num_chunk++;

		p++;
	}

	if ((nspec_arr = (nspec **) calloc(num_chunk + 1, sizeof(nspec *))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	simplespec = parse_plus_spec(execvnode, &ret);

	if (ret || simplespec == NULL)
		invalid = 1;
	else if (parse_node_resc(simplespec, &node_name, &num_el, &kv) != 0)
		invalid = 1;

	for (i = 0; i < num_chunk && !invalid && simplespec != NULL; i++) {
		nspec_arr[i] = new_nspec();
		if (nspec_arr[i] != NULL) {
			ninfo = find_node_info(sinfo->nodes, node_name);
			if (ninfo != NULL) {
				nspec_arr[i]->ninfo = ninfo;
				for (j = 0; j < num_el; j++) {
					req = create_resource_req(kv[j].kv_keyw, kv[j].kv_val);
					if (req != NULL) {
						if (nspec_arr[i]->resreq == NULL)
							nspec_arr[i]->resreq = req;
						else {
							req->next = nspec_arr[i]->resreq;
							nspec_arr[i]->resreq = req;
						}
					}
					else
						invalid = 1;
				}
			}
			else {
				schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, node_name,
					"Exechost contains a node that does not exist.");
				invalid = 1;
			}
			if (i == num_chunk - 1)
				nspec_arr[i]->end_of_chunk = 1;
		}
		else
			invalid = 1;

		if (!invalid) {
			simplespec = parse_plus_spec(NULL, &ret);
			if (!ret) {
				if (simplespec != NULL) {
					ret = parse_node_resc(simplespec, &node_name, &num_el, &kv);
					if (ret < 0)
						invalid = 1;
				}
			}
			else
				invalid = 1;
		}
	}

	nspec_arr[i] = NULL;

	if (invalid) {
		snprintf(logbuf, sizeof(logbuf), "Failed to parse execvnode: %s", execvnode);
		schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_WARNING, __func__,
			logbuf);
		free_nspecs(nspec_arr);
		return NULL;
	}

	return nspec_arr;
}

/**
 * @brief
 *		node_state_to_str - convert a node's state into a string for printing
 *
 * @param[in]	ninfo	-	the node
 *
 * @return	static string of node state
 *
 */
const char *
node_state_to_str(node_info *ninfo)
{
	if (ninfo == NULL)
		return "";

	if (ninfo->is_job_busy)
		return ND_jobbusy;

	if (ninfo->is_free)
		return ND_free;

	if (ninfo->is_down)
		return ND_down;

	if (ninfo->is_offline)
		return ND_offline;

	if (ninfo->is_resv_exclusive)
		return ND_resv_exclusive;

	if (ninfo->is_job_exclusive)
		return ND_job_exclusive;

	if (ninfo->is_busy)
		return ND_busy;

	if (ninfo->is_stale)
		return ND_Stale;

	if (ninfo->is_provisioning)
		return ND_prov;

	/* default */
	return ND_state_unknown;
}

/**
 * @brief
 *		combine_nspec_array - find and combine any nspec's for the same node
 *		in an nspec array
 *
 * @param[in,out]	nspec_arr	-	array to combine
 *
 * @return	nothing
 *
 */
void
combine_nspec_array(nspec **nspec_arr)
{
	int i, j;
	resource_req *req_i;
	resource_req *req_j;
	resource_req *prev_j = NULL;
	int combined = 0;

	if (nspec_arr == NULL)
		return;

	for (i = 0; nspec_arr[i] != NULL; i++) {
		for (j = i + 1; nspec_arr[j] != NULL; j++) {
			if (nspec_arr[i]->resreq != NULL &&
				nspec_arr[i]->ninfo == nspec_arr[j]->ninfo) {
				req_j = nspec_arr[j]->resreq;
				prev_j = NULL;

				while (req_j != NULL) {
					req_i =
						find_resource_req(nspec_arr[i]->resreq, req_j->def);
					if (req_i != NULL) {
						/* we assume that if the resource is a boolean or a string
						 * the value is either the same, or doesn't exist
						 * so we don't need to do validity checking
						 */
						if (req_j->type.is_consumable)
							req_i->amount +=  req_j->amount;
						else if (req_j->type.is_string && req_i->res_str ==NULL) {
							req_i->res_str = req_j->res_str;
							req_j->res_str = NULL;
						}
						prev_j = req_j;
						req_j = req_j->next;
					}
					else  { /* nspec_arr[j] has a resource [i] does not, just link j's on */
						req_i = req_j;
						req_j = req_j->next;

						if (prev_j == NULL) /* req_j is the first in the list */
							nspec_arr[j]->resreq = nspec_arr[j]->resreq->next;
						else
							prev_j->next = req_i->next;

						req_i->next = nspec_arr[i]->resreq;
						nspec_arr[i]->resreq = req_i;
					}
				}
				/* We've merged all of nspec_arr[j]'s resources into nspec_arr[i]
				 * We set the ninfo member to NULL to mark the nspec for removal
				 */
				nspec_arr[j]->ninfo = NULL;
				combined = 1;
			}
		}
	}

	if (combined) {
		/* if we've actually done something, we need to remove duplicate entries
		 * we do this by finding the first entry we're going to remove, and then
		 * copy all entries back, only copying entries which we want to keep.
		 * along the way freeing the memory used by all unneeded entries
		 */
		for (i = 0; nspec_arr[i] != NULL; i++)
			if (nspec_arr[i]->ninfo == NULL)
				break;

		free_nspec(nspec_arr[i]);

		for (j = i, i++; nspec_arr[j] != NULL; i++) {
			if (nspec_arr[i] != NULL) {
				if (nspec_arr[i]->ninfo != NULL) {
					nspec_arr[j] = nspec_arr[i];
					j++;
				}
				else
					free_nspec(nspec_arr[i]);
			}
			else
				nspec_arr[j] = NULL;
		}
	}
}

/**
 * @brief
 *		create_node_array_from_nspec - create a node_info array by copying the
 *				       ninfo pointers out of a nspec array
 *
 * @param[in]	nspec_arr	-	source nspec array
 *
 * @return	new node_info array
 * @retval	NULL	: on error
 *
 */
node_info **
create_node_array_from_nspec(nspec **nspec_arr)
{
	node_info **ninfo_arr;
	int count;
	int i, j;

	if (nspec_arr == NULL)
		return NULL;

	count = count_array((void **) nspec_arr);

	if ((ninfo_arr = calloc(count + 1, sizeof(node_info *))) == NULL) {
		schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_INFO, "create_node_array_from_nspec", "malloc failed to allocate node array");
		return NULL;
	}

	/* make ninfo_arr a searchable array */
	ninfo_arr[0] = NULL;

	for (i = 0, j = 0; nspec_arr[i] != NULL; i++) {
		if (find_node_by_rank(ninfo_arr, nspec_arr[i]->ninfo->rank) ==NULL) {
			ninfo_arr[j] = nspec_arr[i]->ninfo;
			j++;
		}
	}

	ninfo_arr[j] = NULL;

	return ninfo_arr;
}

/**
 * @brief
 *	reorder the nodes for the avoid_provision or smp_cluster_dist policies
 *	or when the reservation is being altered without changing the source
 * 	array. We do so by holding our own static array of node pointers that
 * 	we will sort for the different policies.
 *
 * @param[in]	nodes	: nodes to reorder
 * @param[in]	resresv : job or reservation for which reorder is done
 *
 * @see	last_node_name - the last allocated node - used for round_robin
 *
 * @return	node_info **
 * @retval	reordered list of nodes if needed
 * @retval	'nodes' parameter if nodes do not need reordering
 * @retval	NULL	: on error
 *
 * @par Side Effects:
 *      local variable node_array holds onto memory in the heap for reuse.
 *      The caller should not free the return
 *
 * @par MT-safe:	No
 *
 * @par MT-safe: No
 */
node_info **
reorder_nodes(node_info **nodes, resource_resv *resresv)
{
	static node_info	**node_array = NULL;
	static int		node_array_size = 0;
	node_info		**nptr = NULL;
	node_info		**tmparr = NULL;
	schd_resource		*hostres = NULL;
	schd_resource		*cur_hostres = NULL;
	int 			nsize = 0;
	int			i = 0;
	int			j = 0;
	int			k = 0;
	char			errbuf[MAX_LOG_SIZE] = {0};

	if (nodes == NULL)
		return NULL;

	if (resresv == NULL && conf.provision_policy == AVOID_PROVISION)
		return NULL;

	nsize = count_array((void **) nodes);

	if (node_array_size < nsize + 1) {
		tmparr = realloc(node_array, sizeof(node_info *) * (nsize + 1));
		if (tmparr == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			return NULL;
		}

		node_array = tmparr;
		node_array_size = nsize + 1;
	}
	tmparr = NULL;

	node_array[0] = NULL;
	nptr = node_array;

	if (resresv != NULL && resresv->is_resv && resresv->resv != NULL && resresv->resv->check_alternate_nodes) {
		int		i = 0;
		node_info	*temp = NULL;

		memcpy(nptr, nodes, (nsize+1) * sizeof(node_info *));
		for (i = 0; nptr[i] != NULL; i++) {
			temp = find_node_by_rank(resresv->ninfo_arr, nptr[i]->rank);
			if (temp != NULL)
				nptr[i]->nscr.to_be_sorted = 0;
			else
				nptr[i]->nscr.to_be_sorted = 1;
		}
		qsort(nptr, i, sizeof(node_info*), cmp_nodes_sort);
		return nptr;
	}

	if (last_node_name[0] == '\0')
		strcpy(last_node_name, nodes[0]->name);

	if (resresv->aoename != NULL && conf.provision_policy == AVOID_PROVISION) {
		memcpy(nptr, nodes, (nsize+1) * sizeof(node_info *));

		if (cmp_aoename != NULL)
			free(cmp_aoename);

		cmp_aoename = string_dup(resresv->aoename);
		qsort(nptr, nsize, sizeof(node_info *), cmp_aoe);

		sprintf(errbuf, "Re-sorted the nodes on aoe %s, since aoe was requested",
			resresv->aoename);
		errbuf[MAX_LOG_SIZE - 1] = '\0';
		schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG, resresv->name,
			errbuf);

		return nptr;
	}

	switch (cstat.smp_dist) {
		case SMP_NODE_PACK:
			nptr = nodes;
			break;

		case SMP_LOWEST_LOAD:

			memcpy(nptr, nodes, (nsize+1) * sizeof(node_info *));

			qsort(nptr, nsize, sizeof(node_info *), cmp_low_load);
			break;
		case SMP_ROUND_ROBIN:

			if ((tmparr = calloc(node_array_size, sizeof(node_info *))) == NULL) {
				log_err(errno, __func__, MEM_ERR_MSG);
				return NULL;
			}

			memcpy(tmparr, nodes, nsize * sizeof(node_info *));
			qsort(tmparr, nsize, sizeof(node_info *), cmp_node_host);

			for (i = 0; i < nsize && strcmp(last_node_name, tmparr[i]->name); i++)
				;

			if (i < nsize) {
				/* find the vnode of the next host or the end of the list since the
				 * beginning will definitely be a different host because of our sort
				 */
				hostres = find_resource(tmparr[i]->res, getallres(RES_HOST));
				if (hostres != NULL) {
					for (; i < nsize; i++) {
						cur_hostres = find_resource(tmparr[i]->res, getallres(RES_HOST));
						if (cur_hostres != NULL) {
							if (!compare_res_to_str(cur_hostres, hostres->str_avail[0], CMP_CASELESS))
								break;
						}
					}
				}
			}

			/* copy from our last location to the end */
			for (j = 0, k = i; k < nsize; j++, k++)
				nptr[j] = tmparr[k];

			/* copy from the beginning to our last location */
			for (k = 0; k < i; j++, k++)
				nptr[j] = tmparr[k];

			nptr[j] = NULL;

			free(tmparr);
			break;

		default:
			nptr = nodes;
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", "Invalid smp_cluster_dist value");
	}

	return nptr;
}

/**
 * @brief
 *		ok_break_chunk - is it OK to break up a chunk on a list of nodes?
 *
 * @param[in]	resresv	-	the requestor (unused for the moment)
 * @param[in]	nodes   -	the list of nodes to check
 *
 * @return	int
 * @retval	1	: if its OK to break up chunks across the nodes
 * @retval	0	: if it not
 *
 */
int
ok_break_chunk(resource_resv *resresv, node_info **nodes)
{
	int i;
	schd_resource *hostres = NULL;
	schd_resource *res;
	if (resresv == NULL || nodes == NULL)
		return 0;


	for (i = 0; nodes[i] != NULL; i++) {
		res = find_resource(nodes[i]->res, getallres(RES_HOST));
		if (res != NULL) {
			if (hostres == NULL)
				hostres = res;
			else {
				if (match_string_array(hostres->str_avail, res->str_avail)
					!= SA_FULL_MATCH) {
					break;
				}
			}
		}
		else {
			schdlog(PBSEVENT_SCHED, PBS_EVENTCLASS_NODE, LOG_WARNING,
				nodes[i]->name, "Node has no host resource");
		}
	}

	if (nodes[i] == NULL)
		return 1;

	return 0;
}

/**
 * @brief
 *		is_excl - is a request/node combination exclusive?  This is based
 *		  on both the place directive of the request and the
 *		  sharing attribute of the node
 *
 * @param[in]	pl	-	place directive of the request
 * @param[in]	sharing	-	sharing attribute of the node
 *
 * @return	int
 * @retval	1	: if exclusive
 * @retval	0	: if not
 *
 * @note
 *		Assumes if pl is NULL, no request excl/shared request was given
 */
int
is_excl(place *pl, enum vnode_sharing sharing)
{
	if (sharing == VNS_FORCE_EXCL || sharing == VNS_FORCE_EXCLHOST)
		return 1;

	if (sharing == VNS_IGNORE_EXCL)
		return 0;

	if (pl != NULL) {
		if (pl->excl)
			return 1;

		if (pl->share)
			return 0;
	}

	if (sharing == VNS_DFLT_EXCL || sharing == VNS_DFLT_EXCLHOST)
		return 1;

	if (sharing == VNS_DFLT_SHARED)
		return 0;

	return 0;
}

/**
 * @brief
 * 		take a node solution and extend it by allocating the rest of
 *		a node array to it.
 *
 * @param[in][out]	nsa	-	currently allocated node solution to be
 *							extended with ninfo_arr
 * @param[in] ninfo_arr - node array to allocate to nspec array
 *
 * @note
 *		must be allocated by caller
 *
 * @return	int
 * @retval	1	: on success
 * @retval	on error	: nsa may be modified
 *
 */
int
alloc_rest_nodepart(nspec **nsa, node_info **ninfo_arr)
{
	nspec *ns;
	int i, j;
	int max_seq_num = 0;
	if (nsa == NULL || ninfo_arr == NULL)
		return 0;

	/* find the end of our current node solution.  While we're searching, find
	 * the highest nspec sequence number.  We will use this for the sequence
	 * number for the rest of the nodepart
	 */
	for (j = 0; nsa[j] != NULL; j++) {
		if (nsa[j]->seq_num > max_seq_num)
			max_seq_num = nsa[j]->seq_num;
	}

	for (i = 0; ninfo_arr[i] != NULL; i++) {
		ns = find_nspec(nsa, ninfo_arr[i]);

		/* node not part of solution */
		if (ns == NULL) {
			nsa[j] = new_nspec();
			if (nsa[j] != NULL) {
				nsa[j]->ninfo = ninfo_arr[i];
				nsa[j]->end_of_chunk = 1;
				nsa[j]->seq_num = max_seq_num;

				nsa[j]->sub_seq_num = get_sched_rank();

				j++;
				nsa[j] = NULL;
			}
			else
				return 0;
		}
	}

	return 1;
}

/**
 * @brief
 *		set_res_on_host - set a resource on all the vnodes of a host
 *
 * @param[in]	res_name	-	name of the res to set
 * param[in]	res_value	-	value to set the res
 * param[in]	host	-	name of the host
 * param[in]	exclude	-	node to exclude being set
 * param[in,out]	ninfo_arr	-	array to search through
 *
 * @return	int
 * @retval	1	: on success
 * @retval	0	: on error
 *
 */
int
set_res_on_host(char *res_name, char *res_value,
	char *host, node_info *exclude, node_info **ninfo_arr)
{
	int i;
	schd_resource *hostres;
	schd_resource *res;
	int rc = 1;

	if (res_name == NULL || res_value == NULL || host == NULL || ninfo_arr == NULL)
		return 0;

	for (i = 0; ninfo_arr[i] != NULL && rc; i++) {
		if (ninfo_arr[i] != exclude) {
			hostres = find_resource(ninfo_arr[i]->res, getallres(RES_HOST));

			if (hostres != NULL) {
				if (compare_res_to_str(hostres, host, CMP_CASELESS)) {
					res = find_alloc_resource_by_str(ninfo_arr[i]->res, res_name);
					if (res != NULL) {
						if (ninfo_arr[i]->res == NULL)
							ninfo_arr[i]->res = res;

						rc = set_resource(res, res_value, RF_AVAIL);
					}
				}
			}
		}
	}
	return rc;
}

/**
 * @brief
 *		update_mom_resources - update resources set via mom_resources so all
 *		vnodes on a host indirectly point to the
 *		natural vnode
 *
 * @note
 *		ASSUMPTION: only the 'natural' vnodes talk with mom
 *		'natural' vnodes are vnodes whose host resource is the
 *		same as its vnode name
 *
 * @param[in]	ninfo_arr	-	node array to update
 *
 * @return	int
 * @retval	1	: on success
 * @retval	0	: on error
 *
 */
int
update_mom_resources(node_info **ninfo_arr)
{
	char buf[PBS_MAXHOSTNAME + 2];	/* used to store '@<host>' */
	int i, j;
	int rc = 1;

	if (ninfo_arr == NULL)
		return 0;

	/* if there are no mom_resources, we have nothing to do */
	if (conf.dyn_res_to_get == NULL)
		return 1;

	for (i = 0; ninfo_arr[i] != NULL && rc; i++) {
		if (should_talk_with_mom(ninfo_arr[i])) {
			sprintf(buf, "@%s", ninfo_arr[i]->name);
			for (j = 0; conf.dyn_res_to_get[j] && rc; j++) {
				rc = set_res_on_host(conf.dyn_res_to_get[j], buf,
					ninfo_arr[i]->name, ninfo_arr[i], ninfo_arr);
			}
		}
	}
	return rc;
}

/**
 * @brief
 * 		determine if a chunk can fit on one vnode in node list
 *
 * @param[in]	req	-	requested resources to compare to nodes
 * @param[in]	ninfo_arr	-	node array
 *
 * @par NOTE:
 * 		all resources in req will be honored regardless of
 * 	    whether they are in conf.res_to_check or not due to the fact
 *		that chunk resources only contain such resources
 *
 * @return	int
 * @retval	1	: chunk can fit in 1 vnode
 * @retval	0	: chunk can not fit / error
 *
 */
int
can_fit_on_vnode(resource_req *req, node_info **ninfo_arr)
{
	int i;
	static schd_error *dumperr = NULL;

	if (req == NULL || ninfo_arr == NULL)
		return 0;

	if (dumperr == NULL) {
		dumperr = new_schd_error();
		if (dumperr == NULL) {
			set_schd_error_codes(dumperr, NOT_RUN, SCHD_ERROR);
			return 0;
		}
	}



	for (i = 0; ninfo_arr[i] != NULL; i++) {
		clear_schd_error(dumperr);

		if (is_vnode_eligible_chunk(req, ninfo_arr[i], NULL, dumperr)) {
			if (check_avail_resources(ninfo_arr[i]->res, req,
				UNSET_RES_ZERO, NULL, INSUFFICIENT_RESOURCE, NULL))
				return 1;
		}
	}

	return 0;
}

/**
 * @brief
 *		Checks if an AOE is available on a vnode
 *
 * @par Functionality:
 *		This function checks if an AOE is available on a vnode.
 *
 * @param[in]	ninfo		-	pointer to node_info
 * @param[in]	resresv		-	pointer to resource_resv
 *
 * @return	int
 * @retval	 0 : AOE not available
 * @retval	 1 : AOE available
 *
 * @par Side Effects:
 *		Unknown
 *
 * @par MT-safe: No
 *
 */
int
is_aoe_avail_on_vnode(node_info *ninfo, resource_resv *resresv)
{
	schd_resource *resp;

	if (ninfo == NULL || resresv == NULL)
		return 0;

	if (resresv->aoename == NULL)
		return 0;

	if ((resp = find_resource(ninfo->res, getallres(RES_AOE))) != NULL)
		return find_string(resp->str_avail, resresv->aoename);

	return 0;
}

/**
 * @brief
 *	Checks if an EOE is available on a vnode
 *
 * @par Functionality:
 *	This function checks if an EOE is available on a vnode.
 *
 * @see
 *
 * @param[in]	ninfo		-	pointer to node_info
 * @param[in]	resresv		-	pointer to resource_resv
 *
 * @return	int
 * @retval	 0 : EOE not available
 * @retval	 1 : EOE available
 *
 * @par Side Effects:
 *	Unknown
 *
 * @par MT-safe: No
 *
 */
int
is_eoe_avail_on_vnode(node_info *ninfo, resource_resv *resresv)
{
	schd_resource *resp;

	if (ninfo == NULL || resresv == NULL)
		return 0;

	if (resresv->eoename == NULL)
		return 0;

	if ((resp = find_resource(ninfo->res, getallres(RES_EOE))) != NULL)
		return find_string(resp->str_avail, resresv->eoename);

	return 0;
}

/**
 * @brief
 *		Checks if a vnode is eligible to be provisioned
 *
 * @par Functionality:
 *		This function checks if a vnode is eligible to be provisioned.
 *		A vnode is eligible to be provisioned if it satisfies all of the
 *		following conditions:-
 *			(1) AOE instantiated on the vnode is different from AOE requested by the
 *			the job or reservation,
 *			(2) Server has provisioning enabled,
 *			(3) Vnode has provisioning enabled,
 *			(4) Vnode does not have suspended jobs
 *  		(5) Vnode does not have any running jobs (inside / outside resvs)
 *			(6) No conflicts with reservations already running on the Vnode
 *			(7) No conflicts with jobs already running on the Vnode
 *
 * @see
 *		should_backfill_with_job
 *
 * @param[in]	node		-	pointer to node_info
 * @param[in]	resresv		-	pointer to resource_resv
 * @param[in]	err		-	pointer to schd_error
 *
 * @return	int
 * @retval	NO_PROVISIONING_NEEDED	: resresv doesn't request aoe
 *			or node doesn't need provisioning
 * @retval	PROVISIONING_NEEDED : vnode is provisionable and needs
 *			provisioning
 * @retval	NOT_PROVISIONABLE  : vnode is not provisionable
 *			(see err for more details)
 *
 * @par Side Effects:
 *		Unknown
 *
 * @par MT-safe:	No
 *
 */
int
is_provisionable(node_info *node, resource_resv *resresv, schd_error *err)
{
	int i;
	int ret = NO_PROVISIONING_NEEDED;

	if (resresv->aoename == NULL && resresv->is_job)
		return NO_PROVISIONING_NEEDED;

	/* Perform checks if job is going to provision now or if reservation has aoe. */
	if ((resresv->is_job && (node->current_aoe == NULL
		|| strcmp(resresv->aoename, node->current_aoe))) ||
		(resresv->is_resv && resresv->aoename != NULL)) {
		/* we are inside, it means node requires provisioning... */
		ret = PROVISIONING_NEEDED;

		if (node->is_multivnoded) {
			set_schd_error_codes(err, NOT_RUN, IS_MULTI_VNODE);
			return NOT_PROVISIONABLE;
		}

		if (!resresv->server->provision_enable) {
			set_schd_error_codes(err, NEVER_RUN, PROV_DISABLE_ON_SERVER);
			return NOT_PROVISIONABLE;
		}

		if (!node->provision_enable) {
			set_schd_error_codes(err, NOT_RUN,PROV_DISABLE_ON_NODE);
			return NOT_PROVISIONABLE;
		}

		/* Provisioning disallowed if there are suspended jobs on the node */
		if (node->num_susp_jobs > 0) {
			set_schd_error_codes(err, NOT_RUN, PROV_RESRESV_CONFLICT);
			return NOT_PROVISIONABLE;
		}

		/* if there are running jobs, inside or outside a resv,
		 * disallow prov.
		 */
		if (node->num_jobs > 0) {
			set_schd_error_codes(err, NOT_RUN, PROV_RESRESV_CONFLICT);
			return NOT_PROVISIONABLE;
		}
	}

	/* node cannot be shared between running reservation without AOE
	 * and job with AOE
	 */
	if (resresv->is_job && node->run_resvs_arr) {
		for (i = 0; node->run_resvs_arr[i]; i++) {
			if (node->run_resvs_arr[i]->aoename ==NULL) {
				set_schd_error_codes(err, NOT_RUN, PROV_RESRESV_CONFLICT);
				return NOT_PROVISIONABLE;
			}
		}
	}

	/* node cannot be shared between running job with AOE
	 * and reservation without AOE
	 */
	if (resresv->is_resv && resresv->aoename == NULL &&
		node->job_arr) {
		for (i = 0; node->job_arr[i]; i++) {
			if (node->job_arr[i]->aoename !=NULL) {
				set_schd_error_codes(err, NOT_RUN, PROV_RESRESV_CONFLICT);
				return NOT_PROVISIONABLE;
			}
		}
	}

	return ret;
}

/**
 * @brief
 *		handles everything which happens to a node when it comes back up
 *
 * @param[in]	node	-	the node to bring back up
 * @param[in]	arg		-	NULL param
 *
 * @par Side Effects:
 * 		Sets the resv-exclusive state if the node had it
 * 		previously set.
 *
 * @par MT-safe:	Unknown
 *
 * @retval	1 - node was successfully brought up
 * @retval	0 - node couldn't be brought up
 *
 */
int
node_up_event(node_info *node, void *arg)
{
	server_info *sinfo;

	if (node == NULL)
		return 0;

	/* Preserve the resv-exclusive state when previously set */
	if (node->is_resv_exclusive)
		set_node_info_state(node, ND_resv_exclusive);
	else
		set_node_info_state(node, ND_free);

	sinfo = node->server;
	if (sinfo->node_group_enable && sinfo->node_group_key !=NULL) {
		node_partition_update_array(sinfo->policy, sinfo->nodepart);
		qsort(sinfo->nodepart, sinfo->num_parts,
			sizeof(node_partition *), cmp_placement_sets);
	}
	update_all_nodepart(sinfo->policy, sinfo, NULL);

	return 1;
}

/**
 * @brief
 *		handles everything which happens to a node when it goes down
 *
 * @param[in]	node	-	node to bring down
 * @param[in]	arg		-	NULL param
 *
 * @par Side Effects: None
 * @par MT-safe: Unknown
 *
 * @return	int
 * @retval	1	: node was successfully brought down
 * @retval	0	: node couldn't be brought down
 *
 */
int
node_down_event(node_info *node, void *arg)
{
	int i;
	char *job_state;
	server_info *sinfo;

	if (node == NULL)
		return 0;

	sinfo = node->server;
	if (node->job_arr != NULL) {
		for (i = 0; node->job_arr[i] != NULL; i++) {
			if (node->job_arr[i]->job->can_requeue)
				job_state = "Q";
			else
				job_state = "X";
			update_universe_on_end(sinfo->policy, node->job_arr[i], job_state);
		}
	}

	set_node_info_state(node, ND_down);

	if (sinfo->node_group_enable && sinfo->node_group_key !=NULL) {
		node_partition_update_array(sinfo->policy, sinfo->nodepart);
		qsort(sinfo->nodepart, sinfo->num_parts,
			sizeof(node_partition *), cmp_placement_sets);
	}
	update_all_nodepart(sinfo->policy, sinfo, NULL);

	return 1;
}

/**
 * @brief
 * 		filter function to check if node is in a string array of node names
 *
 * @see	node_filter
 *
 * @param[in]	node	- node to check
 * @param[in] 	strarr	- array of node names
 *
 * @returns	int
 * @retval	1	: include node in array
 * @retval	0	: don't include node in array
 */
int
node_in_str(node_info *node, void *strarr)
{
	if (node == NULL || strarr == NULL)
		return 0;

	if (find_string((char **)strarr, node->name))
		return 1;

	return 0;
}

/**
 * @brief
 *		create an array of unique nodes from a names in a string array
 *
 * @param[in]	nodes	-	nodes to create array from
 * @param[in]	strnodes	-	string array of vnode names
 *
 * @return node array
 *
 */
node_info **
create_node_array_from_str(node_info **nodes, char **strnodes)
{
	int i, j;
	node_info **ninfo_arr;
	int cnt;
	char errbuf[MAX_LOG_SIZE];

	if (nodes == NULL || strnodes == NULL)
		return NULL;

	cnt = count_array((void **)strnodes);

	if ((ninfo_arr = malloc((cnt+1) * sizeof(node_info *))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}
	ninfo_arr[0] = NULL;

	for (i = 0, j = 0; strnodes[i] != NULL; i++) {
		if (find_node_info(ninfo_arr, strnodes[i]) == NULL) {
			ninfo_arr[j] = find_node_info(nodes, strnodes[i]);
			if (ninfo_arr[j] != NULL) {
				j++;
				ninfo_arr[j] = NULL;
			}
			else {
				snprintf(errbuf, MAX_LOG_SIZE, "Node %s not found in list.", strnodes[i]);
				schdlog(PBSEVENT_DEBUG2, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__, errbuf);
			}
		}
	}

	return ninfo_arr;
}

/**
 * @brief
 * 		find a node by its unique rank
 *
 * @param[in]	ninfo_arr	-	node array to search
 * @param[in] rank	-	unique numeric identifier for node
 *
 * @return	node_info *
 * @retval	found node
 * @retval	NULL	: if node is not found
 */
node_info *
find_node_by_rank(node_info **ninfo_arr, int rank)
{
	int i;
	if (ninfo_arr == NULL)
		return NULL;

	for (i = 0; ninfo_arr[i] != NULL && ninfo_arr[i]->rank != rank; i++)
		;

	return ninfo_arr[i];
}

/**
 * @brief
 * 		node_scratch constructor
 *
 * @return new node_scratch structure
 */
node_scratch *
new_node_scratch(void)
{
	node_scratch *nscr;
	nscr = malloc(sizeof(node_scratch));
	if (nscr == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}
	nscr->visited = 0;
	nscr->scattered = 0;

	return nscr;
}

/**
 * @brief
 * 		node_scratch destructor
 *
 * @param[in]	nscr	-	node scratch to be freed.
 */
void
free_node_scratch(node_scratch *nscr)
{
	if (nscr == NULL)
		return;

	free(nscr);
}

/**
 * @brief
 * 		determine if resresv conflicts based on exclhost state of the
 *		future events on this node.
 *
 * @param	calendar - server's calendar of events
 * @param	resresv  - job or resv to check
 * @param	ninfo    - node to check
 *
 * @return int
 * @retval 1	: no excl conflict
 * @retval 0	: future excl conflict
 */
int
sim_exclhost(event_list *calendar, resource_resv *resresv, node_info *ninfo)
{
	time_t end;

	if (calendar == NULL || resresv == NULL || ninfo == NULL)
		return 1;

	if (resresv->duration != resresv->hard_duration &&
	    exists_resv_event(calendar, resresv->hard_duration))
		end = resresv->server->server_time + calc_time_left(resresv, 1);
	else
		end = resresv->server->server_time + calc_time_left(resresv, 0);

	return generic_sim(calendar, TIMED_RUN_EVENT,
		end, 1, sim_exclhost_func, (void*)resresv, (void*)ninfo);
}
/**
 * @brief
 * 		helper function for generic_sim() to check if an event has an exclhost
 *	  conflict with a job/resv on a node.  We either find a conflict or
 *	  continue looping.
 *
 * @param[in]	te	-	future event
 * @param[in]	arg1	-	job/reservation
 * @param[in]	arg2	- node
 *
 * @return	int
 * @retval	1	: no excl conflict
 * @retval	0	: continue looping
 * @retval	-1	: excl conflict
 */
int
sim_exclhost_func(timed_event *te, void *arg1, void *arg2)
{
	resource_resv *resresv;
	resource_resv *future_resresv;
	node_info *ninfo;

	if (te == NULL || arg1 == NULL || arg2 == NULL)
		return 0;

	resresv = (resource_resv*) arg1;
	ninfo = (node_info*) arg2;
	future_resresv = (resource_resv*) te->event_ptr;
	if (find_nspec_by_rank(future_resresv->nspec_arr, ninfo->rank) ==NULL)
		return 0; /* event does not affect the node */

	if (is_exclhost(future_resresv->place_spec, ninfo->sharing) ||
		is_exclhost(resresv->place_spec, ninfo->sharing)) {
		return -1;
	}

	return 0;
}

/**
 * @brief
 * 		set current_aoe on a node.  Free existing value if set
 *
 * @param[in]	node	-	node to set
 * @paran[in]	aoe	-	aoe to set on ode
 *
 * @return void
 */
void
set_current_aoe(node_info *node, char *aoe)
{
	if (node == NULL)
		return;
	if (node->current_aoe != NULL)
		free(node->current_aoe);
	if (aoe == NULL)
		node->current_aoe = NULL;
	else
		node->current_aoe = string_dup(aoe);
}

/**
 * @brief set current_eoe on a node.  Free existing value if set
 * @param[in] node - node to set
 * @paran[in] eoe - eoe to set on ode
 * @return void
 */
void
set_current_eoe(node_info *node, char *eoe)
{
	if (node == NULL)
		return;
	if (node->current_eoe != NULL)
		free(node->current_eoe);
	if (eoe == NULL)
		node->current_eoe = NULL;
	else
		node->current_eoe = string_dup(eoe);
}

/**
 * @brief
 * 		should we exclhost this job - a function of node sharing and job place
 *
 * @param[in]	sharing	-	the nodes sharing attribute value
 * @param[in]	placespec	-	job place attribute
 *
 * @return	int
 * @retval	1	: do exclhost
 * @retval	0	: don't do exclhost (or invalid input)
 */
int
is_exclhost(place *placespec, enum vnode_sharing sharing)
{
	/* if the node forces exclhost, we don't care about the place */
	if (sharing == VNS_FORCE_EXCLHOST)
		return 1;

	/* if the node ignores exclusiveness, we don't care about the place */
	if (sharing == VNS_IGNORE_EXCL)
		return 0;

	/* invalid input */
	if (placespec == NULL)
		return 0;

	/* Node defaults to exclhost and the job doesn't disagree */
	if (sharing == VNS_DFLT_EXCLHOST &&
		placespec->excl == 0 && placespec->share ==0)
		return 1;

	/* If the job is requesting exclhost */
	if (placespec->exclhost)
		return 1;

	/* otherwise we're not doing exclhost */
	return 0;
}

/**
 * @brief
 * 		check nodes for eligibility and mark them ineligible if not
 *
 * @param[in]	ninfo_arr	-	array to check
 * @param[in]	resresv	-	resresv to check to place on nodes
 * @param[out]	err	-	error structure
 *
 * @warning
 * 		If an error occurs in this function, no indication will be returned.
 *		This is not a huge concern because, it will just cause more work to be done.
 *
 * @return	void
 */
void
check_node_array_eligibility(node_info **ninfo_arr, resource_resv *resresv, place *pl, schd_error *err)
{
	int i, j;
	static char exclerr_buf[MAX_LOG_SIZE] = {0};
	static schd_error *misc_err = NULL;		/* used to keep err */

	if (ninfo_arr == NULL || resresv == NULL || pl == NULL || err == NULL)
		return;

	if (misc_err == NULL) {
		misc_err = new_schd_error();
		if (misc_err == NULL)
			return;
	}
	if (exclerr_buf[0] == '\0') {
		set_schd_error_codes(misc_err, NOT_RUN, NODE_NOT_EXCL);
		translate_fail_code(misc_err, NULL, exclerr_buf);
	}
	clear_schd_error(misc_err);


	/* Pre-mark all ineligible nodes so we don't need to look at them later */
	for (i = 0; ninfo_arr[i] != NULL; i++) {
		if ((!ninfo_arr[i]->nscr.ineligible)) {
			clear_schd_error(err);
			if (is_vnode_eligible(ninfo_arr[i], resresv, pl, err) == 0) {
				ninfo_arr[i]->nscr.ineligible = 1;
				if (err->status_code != SCHD_UNKWN) {
					if (misc_err->status_code == SCHD_UNKWN)
						move_schd_error(misc_err, err);
					schdlogerr(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
						ninfo_arr[i]->name, NULL, err);
				}
				if (ninfo_arr[i]->hostset != NULL) {
					if ((err->error_code == NODE_NOT_EXCL &&
					    is_exclhost(pl, ninfo_arr[i]->sharing)) ||
					    sim_exclhost(resresv->server->calendar, resresv, ninfo_arr[i]) == 0) {
						for (j = 0; ninfo_arr[i]->hostset->ninfo_arr[j] != NULL; j++) {
							node_info *n = ninfo_arr[i]->hostset->ninfo_arr[j];
							n->nscr.ineligible = 1;
							schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG,
								n->name, exclerr_buf);
						}
					}
				}
			}
		}
	}
	/* If the last node we checked was eligible, err->error_code will be 0.
	 * If a node was previously ineligible, we want to make note of that and
	 * return that err
	 */
	if (err->status_code == SCHD_UNKWN && misc_err->status_code != SCHD_UNKWN)
		move_schd_error(err, misc_err);
}


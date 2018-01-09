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
#ifndef	_NODE_INFO_H
#define	_NODE_INFO_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.h"
#include <pbs_ifl.h>


/*
 *      query_nodes - query all the nodes associated with a server
 */
node_info **query_nodes(int pbs_sd, server_info *sinfo);

/*
 *      query_node_info - collect information from a batch_status and
 *                        put it in a node_info struct for easier access
 */
node_info *query_node_info(struct batch_status *node, server_info *sinfo);

/*
 *      free_nodes - free all the nodes in a node_info array
 */
void free_nodes(node_info **ninfo_arr);


/*
 *      new_node_info - allocates a new node_info
 */
#ifdef NAS /* localmod 005 */
node_info *new_node_info(void);
#else
node_info *new_node_info();
#endif /* localmod 005 */

/*
 *      free_node_info - frees memory used by a node_info
 */
void free_node_info(node_info *ninfo);

/*
 *      set_node_info_state - set a node state
 */
int set_node_info_state(node_info *ninfo, char *state);

/*
 *      remove_node_state
 */
int remove_node_state(node_info *ninfo, char *state);

/*
 *      add_node_state
 */
int add_node_state(node_info *ninfo, char *state);

/*
 *      talk_with_mom - talk to mom and get resources
 */
int talk_with_mom(node_info *ninfo);

/*
 *      node_filter - filter a node array and return a new filterd array
 */
node_info **
node_filter(node_info **nodes, int size,
	int (*filter_func)(node_info*, void*), void *arg, int flags);


/*
 *      is_node_timeshared - check if a node is timeshared
 */
int is_node_timeshared(node_info *node, void *arg);

/*
 *      find_node_info - find a node in the node array
 */
node_info *find_node_info(node_info **ninfo_arr, char *nodename);

/*
 *      dup_node_info - duplicate a node by creating a new one and coping all
 *                      the data into the new
 */
node_info *dup_node(node_info *oninfo, server_info *nsinfo);


/*
 *      dup_nodes - duplicate an array of nodes
 */
#ifdef NAS /* localmod 049 */
node_info **dup_nodes(node_info **onodes, server_info *nsinfo, unsigned int flags, int allocNASrank);
#else
node_info **dup_nodes(node_info **onodes, server_info *nsinfo, unsigned int flags);
#endif /* localmod 049 */

/*
 *      set_node_type - set the node type bits
 */
int set_node_type(node_info *ninfo, char *ntype);

/*
 *      collect_jobs_on_nodes - collect all the jobs in the job array on the
 *                              nodes
 */
int collect_jobs_on_nodes(node_info **ninfo_arr, resource_resv **resresv_arr, int size);

/*
 *      collect_resvs_on_nodes - collect all the running resvs in the resv array
 *                              on the nodes
 */
int collect_resvs_on_nodes(node_info **ninfo_arr, resource_resv **resresv_arr, int size);

/*
 *      is_node_eligible - is this node eligible to run the job
 */
int is_node_eligible(resource_resv *job, node_info *ninfo, char *reason);


/*
 *      find_eligible_nodes - find the eligible node in an array of nodes
 *                            that a job can run on.
 */
node_info **find_eligible_nodes(resource_resv *job, node_info **ninfo_arr, int node_size);

/*
 *      ssinode_reqlist - create a duplicate reqlist for a job for a node's
 *                        ssinode nodeboard mem/proc configuration
 */
resource_req *ssinode_reqlist(resource_req *reqlist, node_info *ninfo);

/*
 *      update_node_on_run - update internal scheduler node data when a job
 *                           is run.
 */
void update_node_on_run(nspec *ns, resource_resv *resresv, char *job_state);

/*
 *      node_queue_cmp - used with node_filter to filter nodes attached to a
 *                       specific queue
 */
int node_queue_cmp(node_info *ninfo, void *arg);

/*
 *      update_node_on_end - update a node when a job ends
 */
void update_node_on_end(node_info *ninfo, resource_resv *resresv, char *job_state);

/*
 *      should_talk_with_mom - check if we should talk to this mom
 */
int should_talk_with_mom(node_info *ninfo);

/*
 *      copy_node_ptr_array - copy an array of jobs using a different set of
 *                            of job pointer (same jobs, different array).
 *                            This means we have to use the names from the
 *                            first array and find them in the second array
 */
#ifdef NAS /* localmod 049 */
node_info **copy_node_ptr_array(node_info  **oarr, node_info  **narr, server_info *sinfo);
#else
node_info **copy_node_ptr_array(node_info  **oarr, node_info  **narr);
#endif /* localmod 049 */



/*
 *      create_execvnode - create an execvnode to run a multi-node job
 */
char *create_execvnode(nspec **ns);

/*
 *      parse_execvnode - parse an execvnode into an nspec array
 */
nspec **parse_execvnode(char *execvnode, server_info *sinfo);

/*
 *      new_nspec - allocate a new nspec
 */
#ifdef NAS /* localmod 005 */
nspec *new_nspec(void);
#else
nspec *new_nspec();
#endif /* localmod 005 */

/*
 *      free_nspec - free the memory used for an nspec
 */
void free_nspec(nspec *ns);

/*
 *      dup_nspec - duplicate an nspec
 */
#ifdef NAS /* localmod 049 */
nspec *dup_nspec(nspec *ons, node_info **ninfo_arr, server_info *sinfo);
#else
nspec *dup_nspec(nspec *ons, node_info **ninfo_arr);
#endif /* localmod 049 */

/*
 *      dup_nspecs - duplicate an array of nspecs
 */
#ifdef NAS /* localmod 049 */
nspec **dup_nspecs(nspec **onspecs, node_info **ninfo_arr, server_info *sinfo);
#else
nspec **dup_nspecs(nspec **onspecs, node_info **ninfo_arr);
#endif /* localmod 049 */

/*
 *	empty_nspec_array - free the contents of an nspec array but not
 *			    the array itself
 *	returns nothing
 */
void empty_nspec_array(nspec **nspec_arr);

/*
 *      free_nspecs - free a nspec array
 */
void free_nspecs(nspec **ns);

/*
 *      find_nspec - find an nspec in an array
 */
nspec *find_nspec(nspec **nspec_arr, node_info *ninfo);

/*
 *      update_nodes_for_resvs - take a node array and make resource effects
 *                               to it for reservations in respect to a job
 *                               This function is for jobs outside of resvs
 */
int
update_nodes_for_resvs(node_info **ninfo_arr, server_info *sinfo,
	resource_resv *job);


/*
 *      dup_node_info - duplicate a node by creating a new one and coping all
 *                      the data into the new
 */
node_info *dup_node_info(node_info *onode, server_info *nsinfo, unsigned int flags);

/*
 *      find_nspec_by_name - find an nspec in an array by nodename
 */
nspec *find_nspec_by_rank(nspec **nspec_arr, unsigned int rank);

/*
 *
 *      update_nodes_for_running_resvs - update resource_assigned values for
 *                                       to reflect running resvs
 */
void update_nodes_for_running_resvs(resource_resv **resvs, node_info **nodes);

/*
 *	global_spec_size - calculate how large a the spec will be
 *			   after the global
 *			   '#' operator has been expanded
 */
int global_spec_size(char *spec, int ncpu_size);

/*
 *	node_state_to_str - convert a node's state into a string for printing
 *	returns static string of node state
 */
const char *node_state_to_str(node_info *ninfo);

/*
 *	parse_placespec - allocate a new place structure and parse
 *				a placement spec (-l place)
 *	returns newly allocated place
 *		NULL: invalid placement spec
 *
 */
place *parse_placespec(char *place_str);

/* compare two place specs to see if they are equal */
int compare_place(place *pl1, place *pl2);

/*
 *	parse_selspec - parse a simple select spec into requested resources
 *
 *	  IN: selspec - the select spec to parse
 *	  OUT: numchunks - the number of chunks
 *
 *	returns requested resource list (& number of chunks in numchunks)
 *		NULL on error or invalid spec
 */
selspec *parse_selspec(char *selspec);

/* compare two selspecs to see if they are equal*/
int compare_selspec(selspec *sel1, selspec *sel2);

/*
 *	combine_nspec_array - find and combine any nspec's for the same node
 *				in an nspec array
 */
void combine_nspec_array(nspec **nspec_arr);

/*
 *	eval_selspec - eval a select spec to see if it is satisifable
 *
 *	  IN: spec - the nodespec
 *	  IN: placespec - the placement spec (-l place)
 *	  IN: ninfo_arr - array of nodes to satisify the spec
 *	  IN: nodepart - the node partition array for node grouping
 *		 	 if NULL, we're not doing node grouping
 *	  IN: resresv - the resource resv the spec is from
 *	  IN: flags - flags to change functions behavior
 *	      EVAL_OKBREAK - ok to break chunck up across vnodes
 *	      EVAL_EXCLSET - allocate entire nodelist exclusively
 *	  OUT: nspec_arr - the node solution
 *
 *	returns 1 if the nodespec can be satisified
 *		0 if not
 */
int
eval_selspec(status *policy, selspec *spec, place *placespec,
	node_info **ninfo_arr, node_partition **nodepart,
	resource_resv *resresv, unsigned int flags,
	nspec ***nspec_arr, schd_error *err);

/*
 *
 *	eval_placement - handle the place spec for node placement
 *
 *	  IN: spec       - the select spec
 *	  IN: ninfo_arr  - array of nodes to satisify the spec
 *	  IN: pl         - parsed placement spec
 *	  IN: resresv    - the resource resv the spec if from
 *	  IN: flags - flags to change functions behavior
 *	      EVAL_OKBREAK - ok to break chunck up across vnodes
 *	  OUT: nspec_arr - the node solution
 *
 *	returns 1 if the selspec can be satisified
 *		0 if not
 *
 */
int
eval_placement(status *policy, selspec *spec, node_info **ninfo_arr, place *pl,
	resource_resv *resresv, unsigned int flags, nspec ***nspec_arr, schd_error *err);
/*
 *	eval_complex_selspec - handle a complex (plus'd) select spec
 *
 *	  IN: spec       - the select spec
 *	  IN: ninfo_arr  - array of nodes to satisify the spec
 *	  IN: pl         - parsed placement spec
 *	  IN: resresv    - the resource resv the spec if from
 *	  IN: flags - flags to change functions behavior
 *	      EVAL_OKBREAK - ok to break chunck up across vnodes
 *	  OUT: nspec_arr - the node solution
 *
 *	returns 1 if the selspec can be satisified
 *		0 if not
 */
int
eval_complex_selspec(status *policy, selspec *spec, node_info **ninfo_arr, place *pl,
	resource_resv *resresv, unsigned int flags, nspec ***nspec_arr, schd_error *err);

/*
 * 	eval_simple_selspec - eval a non-plused select spec for satasifiability
 *
 *        IN: chk - the chunk to satisfy
 * 	  IN: ninfo_arr - the array of nodes
 *	  IN: pl - placement information (from -l place)
 *	  IN: resresv - the job the spec if from (needed for reservations)
 *        IN: flags - flags to change functions behavior
 *            EVAL_OKBREAK - ok to break chunck up across vnodes
 *	  IN: flt_lic - the number of floating licenses available
 *	  OUT: nspec_arr - array of struct nspec's describing the chosen nodes
 *
 * 	returns 1 if the select spec is satifiable
 * 		0 if not
 */
int
eval_simple_selspec(status *policy, chunk *chk, node_info **ninfo_arr,
	place *pl, resource_resv *resresv, unsigned int flags,
	int flt_lic, nspec ***nspec_arr, schd_error *err);

/* evaluate one node to see if it is eligible at the job/resv level */
int
is_vnode_eligible(node_info *node, resource_resv *resresv,
	struct place *pl, schd_error *err);

/* check if a vnode is eligible for a chunk */
int is_vnode_eligible_chunk(resource_req *specreq, node_info *node,
		resource_resv *resresv, schd_error *err);

/*
 *	resources_avail_on_vnode - check to see if there are enough
 *				consuable resources on a vnode to make it
 *				eligible for a request
 *				Note: This function will allocate <= 1 chunk
 *
 *	  specreq_cons - requested consumable resources
 *        IN: node - the node to evaluate
 *        IN: pl - place spec for request
 *        IN: resresv - resource resv which is requesting
 IN: cur_flt_lic - current number of PBS floating licenses available
 *        IN: flags - flags to change behavior of function
 *              EVAL_OKBREAK - OK to break chunk across vnodes
 *        OUT: err - error status if node is ineligible
 *
 *	returns 1 if resources were allocated from the node
 *		0 if sufficent resources are not available (err is set)
 */
int
resources_avail_on_vnode(resource_req *specreq_cons, node_info *node,
	place *pl, resource_resv *resresv, int cur_flt_lic,
	unsigned int flags, nspec *ns, schd_error *err);

/*
 *	check_resources_for_node - check to see how many chunks can fit on a
 *				   node looking at both resources available
 *				   now and future advanced reservations
 *
 *
 *	  IN: resreq     - requested resources
 *	  IN: node       - node to check for
 *	  IN: resersv    - the resource resv to check for
 *	  OUT: err       - schd_error reply if there aren't enough resources
 *
 *	returns number of chunks which can be satisifed during the duration
 *		-1 on error
 */
long long
check_resources_for_node(resource_req *resreq, node_info *ninfo,
	resource_resv *resresv, schd_error *err);

/*
 *	create_node_array_from_nspec - create a node_info array by copying the
 *				       ninfo pointers out of a nspec array
 *	returns new node_info array or NULL on error
 */
node_info **create_node_array_from_nspec(nspec **nspec_arr);

/*
 *	reorder_nodes - reorder nodes for smp_cluster_dist or
 *				provision_policy_types
 *	NOTE: uses global last_node_name for round_robin
 *	returns pointer to static buffer of nodes (reordered appropretly)
 */
node_info **reorder_nodes(node_info **nodes, resource_resv *resresv);

/*
 *	ok_break_chunk - is it OK to break up a chunk on a list of nodes?
 *	  resresv - the requestor (unused for the moment)
 *	  nodes   - the list of nodes to check
 *
 *	returns 1 if its OK to break up chunks across the nodes
 *		0 if it not
 */
int ok_break_chunk(resource_resv *resresv, node_info **nodes);

/*
 *	is_excl - is a request/node combination exclusive?  This is based
 *		  on both the place directive of the request and the
 *		  sharing attribute of the node
 *
 *	  pl      - place directive of the request
 *	  sharing - sharing attribute of the node
 *
 *	returns 1 if exclusive
 *		0 if not
 *
 *	Assumes if pl is NULL, no request excl/shared request was given
 */
int is_excl(place *pl, enum vnode_sharing sharing);
/* similar to is_excl but for exclhost */
int is_exclhost(place *pl, enum vnode_sharing sharing);

/*
 *	alloc_rest_nodepart - allocate the rest of a node partition to a
 *			      nspec array
 *
 *	  IN/OUT: nsa - node solution to be filled out -- allocated by the
 *		        caller with enough space for the entire solution
 *	  IN: ninfo_arr - node array to allocate
 *
 *	returns 1 on success
 *		0 on error -- nsa will be modified
 */
int alloc_rest_nodepart(nspec **nsa, node_info **ninfo_arr);

/*
 *	set_res_on_host - set a resource on all the vnodes of a host
 *
 *	  res_name  - name of the res to set
 *	  res_value - value to set the res
 *	  host      - name of the host
 *	  exclude   - node to exclude from being set
 *	  ninfo_arr - array to search through
 *
 *	returns 1 on success 0 on error
 */
int
set_res_on_host(char *res_name, char *res_value,
	char *host, node_info *exclude, node_info **ninfo_arr);

/*
 *	update_mom_resources - update resources set via mom_reources so all
 *			       vnodes on a host indirectly point to the
 *			       natural vnode
 *
 *	ASSUMPTION: only the 'natural' vnodes talk with mom
 *		    'natural' vnodes are vnodes whose host resource is the
 *		    same as its vnode name
 *
 *	  ninfo_arr - node array to update
 *
 *	returns 1 on success 0 on error
 */
int update_mom_resources(node_info **ninfo_arr);

/*
 *	can_fit_on_vnode - see if a chunk fit on one vnode in node list
 *
 *	  req - requested resources to compare to nodes
 *	  ninfo_arr - node array
 *
 *	returns 1: chunk can fit in 1 vnode
 *		0: chunk can not fit / error
 */
int can_fit_on_vnode(resource_req *req,  node_info **ninfo_arr);


/*
 *      is_aoe_avail_on_vnode - it first finds if aoe is available in node's
 *                              available list
 *
 *      return : 0 if aoe not available on node
 *             : 1 if aoe available
 *
 */
int is_aoe_avail_on_vnode(node_info *ninfo, resource_resv *resresv);

/*
 *      is_eoe_avail_on_vnode - it first finds if eoe is available in node's
 *                              available list
 *
 *      return : 0 if eoe not available on node
 *             : 1 if eoe available
 *
 */
int is_eoe_avail_on_vnode(node_info *ninfo, resource_resv *resresv);

/*
 *      is_provisionable - it checks if a vnode is eligible to be provisioned
 *
 *      return NO_PROVISIONING_NEEDED : resresv doesn't doesn't request aoe
 *                                      or node doesn't need provisioning
 *             PROVISIONING_NEEDED : vnode is provisionable and needs
 *                                   provisioning
 *             NOT_PROVISIONABLE  : vnode is not provisionable
 *
 *
 */
int is_provisionable(node_info *node, resource_resv *job, schd_error *err);

/*
 *	handles everything which happens to a node when it comes back up
 */
int node_up_event(node_info *node, void *arg);

/*
 *	handles everything which happens to a node when it goes down
 */
int node_down_event(node_info *node, void *arg);

/*
 *	create a node_info array from a list of nodes in a string array
 */
node_info **create_node_array_from_str(node_info **nodes, char **strnodes);

/*
 *      find node by unique rank
 */
node_info *find_node_by_rank(node_info **ninfo_arr, int rank);

/*
 * node scratch constructor
 */
node_scratch *new_node_scratch(void);


/*
 * node_scratch destructor
 */
void free_node_scratch(node_scratch *nscr);

/* determine if resresv conflicts with future events on ninfo based on the exclhost state */
int sim_exclhost(event_list *calendar, resource_resv *resresv, node_info *ninfo);

/*
 * helper function for generic_sim() to check if an event has an exclhost
 * conflict with a job/resv on a node
 */
int sim_exclhost_func(timed_event *te, void *arg1, void *arg2);

/*
 *  get the node resource list from the node object.  If there is a
 *  scratch resource list, return that one first.
 */

/**
 * set current_aoe on a node.  Free existing value if set
 */
void set_current_aoe(node_info *node, char *aoe);

/**
 * set current_eoe on a node.  Free existing value if set
 */
void set_current_eoe(node_info *node, char *eoe);

/* check nodes for eligibility and mark them ineligible if not */
void check_node_array_eligibility(node_info **ninfo_arr, resource_resv *resresv, place *pl, schd_error *err);

int node_in_partition(node_info *ninfo);


#ifdef	__cplusplus
}
#endif
#endif	/* _NODE_INFO_H */

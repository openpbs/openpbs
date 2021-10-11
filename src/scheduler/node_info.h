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

#ifndef	_NODE_INFO_H
#define	_NODE_INFO_H

#include "data_types.h"
#include <pbs_ifl.h>

void query_node_info_chunk(th_data_query_ninfo *data);

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
 * pthread routine for freeing up a node_info array
 */
void
free_node_info_chunk(th_data_free_ninfo *data);

/*
 *      free_nodes - free all the nodes in a node_info array
 */
void free_nodes(node_info **ninfo_arr);

/*
 *      set_node_info_state - set a node state
 */
int set_node_info_state(node_info *ninfo, const char *state);

/*
 *      remove_node_state
 */
int remove_node_state(node_info *ninfo, const char *state);

/*
 *      add_node_state
 */
int add_node_state(node_info *ninfo, const char *state);

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
node_info *find_node_info(node_info **ninfo_arr, const std::string& nodename);

/*
 *      dup_node_info - duplicate a node by creating a new one and coping all
 *                      the data into the new
 */
node_info *dup_node(node_info *oninfo, server_info *nsinfo);

void dup_node_info_chunk(th_data_dup_nd_info *data);

/*
 *      dup_nodes - duplicate an array of nodes
 */
node_info **dup_nodes(node_info **onodes, server_info *nsinfo, unsigned int flags);

/*
 *      collect_jobs_on_nodes - collect all the jobs in the job array on the
 *                              nodes
 */
int collect_jobs_on_nodes(node_info **ninfo_arr, resource_resv **resresv_arr, int size, int flags);

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
void update_node_on_run(nspec *ns, resource_resv *resresv, const char *job_state);

/*
 *      node_queue_cmp - used with node_filter to filter nodes attached to a
 *                       specific queue
 */
int node_queue_cmp(node_info *ninfo, void *arg);

/*
 *      update_node_on_end - update a node when a job ends
 */
void update_node_on_end(node_info *ninfo, resource_resv *resresv, const char *job_state);

/*
 *      copy_node_ptr_array - copy an array of jobs using a different set of
 *                            of job pointer (same jobs, different array).
 *                            This means we have to use the names from the
 *                            first array and find them in the second array
 */
node_info **copy_node_ptr_array(node_info  **oarr, node_info  **narr);

/*
 *      create_execvnode - create an execvnode to run a multi-node job
 */
char *create_execvnode(std::vector<nspec *>& ns_arr);

/*
 *      parse_execvnode - parse an execvnode into an nspec array
 */
std::vector<nspec *> parse_execvnode(char *execvnode, server_info *sinfo, selspec *sel);

/*
 *      dup_nspecs - duplicate an array of nspecs
 */
std::vector<nspec *>dup_nspecs(const std::vector<nspec *>& onspecs, node_info **ninfo_arr, selspec *sel);

/* find a chunk by a sequence number */
chunk *find_chunk_by_seq_num(chunk **chunks, int seq_num);

/*
 *      free_nspecs - free a nspec array
 */
void free_nspecs(std::vector<nspec *>& nspec_arr);

/*
 *      find_nspec - find an nspec in an array
 */
nspec *find_nspec(std::vector<nspec *>& nspec_arr, node_info *ninfo);

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
nspec *find_nspec_by_rank(std::vector<nspec *>& nspec_arr, int rank);

/* find node by unique rank and return index into ninfo_arr */
int find_node_ind(node_info **ninfo_arr, int rank);

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
selspec *parse_selspec(const std::string& sspec);

/* compare two selspecs to see if they are equal*/
int compare_selspec(selspec *s1, selspec *s2);

/*
 *	combine_nspec_array - find and combine any nspec's for the same node
 *				in an nspec array
 */
std::vector<nspec *> combine_nspec_array(const std::vector<nspec *>& nspec_arr);

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
 *	returns true if the nodespec can be satisified
 *		false if not
 */
bool
eval_selspec(status *policy, selspec *spec, place *placespec,
	node_info **ninfo_arr, node_partition **nodepart,
	resource_resv *resresv, unsigned int flags,
	std::vector<nspec *>& nspec_arr, schd_error *err);

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
 *	returns true if the selspec can be satisified
 *		false if not
 *
 */
bool
eval_placement(status *policy, selspec *spec, node_info **ninfo_arr, place *pl,
	resource_resv *resresv, unsigned int flags, std::vector<nspec *>& nspec_arr, schd_error *err);
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
 *	returns true if the selspec can be satisified
 *		false if not
 */
bool
eval_complex_selspec(status *policy, selspec *spec, node_info **ninfo_arr, place *pl,
	resource_resv *resresv, unsigned int flags, std::vector<nspec *>& nspec_arr, schd_error *err);

/*
 * 	eval_simple_selspec - eval a non-plused select spec for satasifiability
 *
 *        IN: chk - the chunk to satisfy
 * 	  IN: ninfo_arr - the array of nodes
 *	  IN: pl - placement information (from -l place)
 *	  IN: resresv - the job the spec if from (needed for reservations)
 *        IN: flags - flags to change functions behavior
 *            EVAL_OKBREAK - ok to break chunck up across vnodes
 *	  OUT: nspec_arr - array of struct nspec's describing the chosen nodes
 *
 * 	returns true if the select spec is satifiable
 * 		false if not
 */
bool
eval_simple_selspec(status *policy, chunk *chk, node_info **pninfo_arr,
	place *pl, resource_resv *resresv, unsigned int flags,
	std::vector<nspec *>& nspec_arr, schd_error *err);

/* evaluate one node to see if it is eligible at the job/resv level */
bool
is_vnode_eligible(node_info *node, resource_resv *resresv,
	struct place *pl, schd_error *err);

/* check if a vnode is eligible for a chunk */
bool
is_vnode_eligible_chunk(resource_req *specreq, node_info *node,
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
 *        IN: flags - flags to change behavior of function
 *              EVAL_OKBREAK - OK to break chunk across vnodes
 *        OUT: err - error status if node is ineligible
 *
 *	returns 1 if resources were allocated from the node
 *		0 if sufficent resources are not available (err is set)
 */
bool
resources_avail_on_vnode(resource_req *specreq_cons, node_info *node,
	place *pl, resource_resv *resresv, unsigned int flags,
	nspec *ns, schd_error *err);

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
node_info **create_node_array_from_nspec(std::vector<nspec *>& nspec_arr);

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
int alloc_rest_nodepart(std::vector<nspec*>& nsa, node_info **ninfo_arr);

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

/* find node by index into sinfo->unordered_nodes or by unique rank */
node_info *find_node_by_indrank(node_info **ninfo_arr, int ind, int rank);

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

/*
 * Check eligibility for a chunk of nodes, a supplementary function to check_node_array_eligibility
 */
void
check_node_eligibility_chunk(th_data_nd_eligible *data);

/* check nodes for eligibility and mark them ineligible if not */
void check_node_array_eligibility(node_info **ninfo_arr, resource_resv *resresv, place *pl, schd_error *err);

int node_in_partition(node_info *ninfo, char *partition);
/* add a node to a node array*/
node_info **add_node_to_array(node_info **ninfo_arr, node_info *node);

bool add_event_to_nodes(timed_event *te, std::vector<nspec *>& nspecs);

int add_node_events(timed_event *te, void *arg1, void *arg2);

struct batch_status *send_statvnode(int virtual_fd, char *id, struct attrl *attrib, char *extend);

/*
 * Find a node by its hostname
 */
node_info *find_node_by_host(node_info **ninfo_arr, char *host);
#endif	/* _NODE_INFO_H */

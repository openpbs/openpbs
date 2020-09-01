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

#include "data_types.hpp"
#ifndef _RESOURCE_H
#define _RESOURCE_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 *	query_resources - query a pbs server for the resources it knows about
 *
 *	  pbs_sd - communication descriptor to pbs server
 *
 *	returns resdef list of resources
 */
resdef **query_resources(int pbs_sd);

/*
 *	conv_rsc_type - convert server type number into resource_type struct
 *	  IN:  type - server type number
 *	  OUT: rtype - resource type structure
 *	returns nothing
 */
void conv_rsc_type(int type, struct resource_type *rtype);

/* used with filter_array*/
int def_is_consumable(void *vdef, void *n);
int def_is_bool(void *vdef, void *n);
int filter_noncons(void *v, void *arg);


/* constructors and destructors for resdef list object */
resdef *new_resdef(void);				/* constructor */
resdef *dup_resdef(resdef *olddef);		/* copy constructor */
resdef **dup_resdef_array(resdef **);	/* list copy constructor */
void free_resdef(resdef *def);		/* destructor */
void free_resdef_array(resdef **deflist);

/* find and return a resdef entry by name */
resdef *find_resdef(resdef **deflist, const char *name);

/*
 * does resdef exist in a resdef array?
 */
int resdef_exists_in_array(resdef **deflist, resdef *def);

/*
 *  create resdef array based on a str array of resource names
 */
resdef** resdef_arr_from_str_arr(resdef **deflist, char **strarr);

/*
 *  safely access allres by index.  This can be used if allres is NULL
 */
resdef *getallres(enum resource_index ind);

/*
 * query the resource definition from the server and create derived
 * data structures.  Only query if required.
 */
int update_resource_defs(int pbs_sd);

/*
 * free and clear global resource definition pointers
 */
void reset_global_resource_ptrs(void);

/* checks if a resource avail is set. */
int is_res_avail_set(schd_resource *res);

/* create a resource signature for a set of resources */
char *create_resource_signature(schd_resource *reslist, resdef **resources, unsigned int flags);

/* collect a unique list of resources from an array of requests */
resdef **collect_resources_from_requests(resource_resv **resresv_arr);

/* convert an array of string resource names into resdefs */
resdef **resstr_to_resdef(char **resstr);
/* filter function for filter_array().  Used to filter out host and vnode */
int no_hostvnode(void *v, void *arg);

/* filter function for filter_array().  Used to filter for resources
 * that are at server/queue level and get summed at the job level
 */
int def_rassn(void *v, void *arg);

/* filter function for filter_array().  Used to filter for resources
 * that are host based and get summed at the job level
 */
int def_rassn_select(void *v, void *arg);

/* add resdef to resdef array */
int add_resdef_to_array(resdef ***resdef_arr, resdef *def);

/* make a copy of a resdef array -- array itself is new memory,
 *        pointers point to the same thing
 */
resdef **copy_resdef_array(resdef **deflist);

/* update the def member in sort_info structures in conf */
void update_sorting_defs(int op);

#ifdef __cplusplus
}
#endif
#endif /* _RESOURCE_H */

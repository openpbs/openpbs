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
 * @file    resource.c
 *
 * @brief
 * 	resource.c - contains functions related to resources.
 *
 * Functions included are:
 * 	query_resources()
 * 	conv_rsc_type()
 * 	def_is_consumable()
 * 	def_is_bool()
 * 	new_resdef()
 * 	dup_resdef()
 * 	dup_resdef_array()
 * 	free_resdef()
 * 	add_resdef_to_array()
 * 	copy_resdef_array()
 * 	free_resdef_array()
 * 	find_resdef()
 * 	resdef_exists_in_array()
 * 	reset_global_resource_ptrs()
 * 	is_res_avail_set()
 * 	add_resource_sig()
 * 	create_resource_signature()
 * 	update_resource_defs()
 * 	resstr_to_resdef()
 * 	getallres()
 * 	collect_resources_from_requests()
 * 	no_hostvnode()
 * 	def_rassn()
 * 	def_rassn_select()
 * 	update_sorting_defs()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#include <pbs_ifl.h>
#include <log.h>
#include "resource.hpp"
#include "constant.hpp"
#include "config.hpp"
#include "data_types.hpp"
#include "misc.hpp"
#include "globals.hpp"
#include "resource_resv.hpp"
#include "pbs_internal.h"
#include "limits_if.h"
#include "sort.hpp"
#include "parse.hpp"
#include "limits_if.h"
#include "fifo.hpp"



/**
 * @brief
 * 		query a pbs server for the resources it knows about
 *
 * @param[in]	pbs_sd	-	communication descriptor to pbs server
 *
 * @return	resdef**
 * @retval	array of resources from server
 * @retval	NULL	: on error
 *
 */
resdef **
query_resources(int pbs_sd)
{
	struct batch_status *bs;		/* queried resources from server */
	struct batch_status *cur_bs;		/* used to iterate over resources */
	struct attrl *attrp;			/* iterate over resource fields */
	int num_defs = 0;			/* number of resource definitions */

	resdef **defarr = NULL;		/* internal sched array for resources */
	resdef *def;
	int i = RES_HIGH;			/*index in defarr past known resources*/
	int j = 0;

	int num;				/* int used for converting str to num */

	char *endp;				/* used for strtol() validation */

	const char *errmsg;
	int error = 0;

	if ((bs = pbs_statrsc(pbs_sd, NULL, NULL, const_cast<char *>("p"))) == NULL) {
		errmsg = pbs_geterrmsg(pbs_sd);
		if (errmsg == NULL)
			errmsg = "";

		log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_REQUEST, LOG_INFO, "pbs_statrsc",
			"pbs_statrsc failed: %s (%d)", errmsg, pbs_errno);
		return NULL;
	}

	for (cur_bs = bs; cur_bs != NULL; cur_bs = cur_bs->next)
		num_defs++;

	if (num_defs < RES_HIGH) { /* too few resources! */
		log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_SCHED, LOG_WARNING, __func__,
			"query_resources() returned too few resources");
		pbs_statfree(bs);
		return NULL;
	}

	/* Worst case scenario: query_resources() returns none of the expected builtin
	 * resources.  If that happens, all num_defs are non-expected.  We will have
	 * allocated RES_HIGH resources for the expected resources and overrun our
	 * array.  Better to waste a wee bit of memory for this case.
	 */
	defarr = (resdef **)malloc((num_defs + RES_HIGH + 1) * sizeof(resdef*));
	if (defarr == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}
	for (j = 0; j <= RES_HIGH; j++)
		defarr[j] = NULL;

	for (cur_bs = bs; cur_bs != NULL; cur_bs = cur_bs->next) {
		def = new_resdef();

		if (def == NULL) {
			pbs_statfree(bs);
			free_resdef_array(defarr);
			return NULL;
		}

		def->name = string_dup(cur_bs->name);
		if (def->name == NULL) {
			free_resdef(def);
			pbs_statfree(bs);
			free_resdef_array(defarr);
			return NULL;
		}
		attrp = cur_bs->attribs;

		while (attrp != NULL) {
			if (!strcmp(attrp->name, ATTR_RESC_TYPE)) {
				num = strtol(attrp->value, &endp, 10);
				conv_rsc_type(num, &(def->type));
			}
			else if (!strcmp(attrp->name, ATTR_RESC_FLAG)) {
				def->flags = strtol(attrp->value, &endp, 10);
			}
			attrp = attrp->next;
		}
		for (j = 0; j < RES_HIGH; j++) {
			if (!strcmp(def->name, resind[j].str)) {
				defarr[resind[j].value] = def;
				break;
			}
		}
		if (j == RES_HIGH) {
			defarr[i] = def;
			i++;
			defarr[i] = NULL;
		}
	}

	/* check for all expected resources. If we didn't find one, it will be NULL */
	for (i = 0; i < RES_HIGH; i++) {
		if (defarr[i] == NULL) {
			log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_SCHED, LOG_WARNING, __func__, "query_resources() did not return all expected resources(%d)", i);
			/* Since we didn't get all the expected built in resources, we have holes
			 * in our resdef array.  If we free it, we'll free the first part and leak
			 * the rest.  We need to fill in the holes so we can free the entire thing
			 */
			defarr[i] = new_resdef();
			error = 1;
		}
	}

	pbs_statfree(bs);

	if (error) {
		free_resdef_array(defarr);
		return NULL;
	}
	return defarr;
}

/**
 * @brief
 * 		convert server type number into resource_type struct
 *
 * @param[in]	type	-	server type number
 * @param[out]	rtype	-	resource type structure
 *
 * @return	void
 *
 */
void
conv_rsc_type(int type, struct resource_type *rtype)
{
	if (rtype == NULL)
		return;

	switch (type) {
		case ATR_TYPE_STR:
		case ATR_TYPE_ARST:
			rtype->is_string = 1;
			rtype->is_non_consumable = 1;
			break;
		case ATR_TYPE_BOOL:
			rtype->is_boolean = 1;
			rtype->is_non_consumable = 1;
			break;
		case ATR_TYPE_SIZE:
			rtype->is_size = 1;
			rtype->is_num = 1;
			rtype->is_consumable = 1;
			break;
		case ATR_TYPE_SHORT:
		case ATR_TYPE_LONG:
		case ATR_TYPE_LL:
			rtype->is_long = 1;
			rtype->is_num = 1;
			rtype->is_consumable = 1;
			break;
		case ATR_TYPE_FLOAT:
			rtype->is_float = 1;
			rtype->is_num = 1;
			rtype->is_consumable = 1;
			break;
	}
}
/**
 * @brief
 * 		is resource consumable?
 *
 * @param[in]	vdef	-	resource definition structure.
 * @param[in]	n	- not used here
 *
 * @see	filter_array()
 */
int
def_is_consumable(void *vdef, void *n)
{
	resdef *def = (resdef *) vdef;
	if (vdef == NULL)
		return 0;
	if (def->type.is_consumable)
		return 1;
	return 0;
}
/**
 * @brief
 * 		is resource a boolean?
 *
 * @param[in]	vdef	-	resource definition structure.
 * @param[in]	n	- not used here
 *
 * @see	filter_array()
 */
int
def_is_bool(void *vdef, void *n)
{
	resdef *def = (resdef *) vdef;
	if (vdef == NULL)
		return 0;

	if (def->type.is_boolean)
		return 1;
	return 0;
}
/* constructor, copy constructor and destructors for resdef */

/**
 * @brief
 * 		resdef constructor
 *
 * @return	newly allocated resdef
 */
resdef *
new_resdef(void)
{
	resdef *newdef;

	if ((newdef = (resdef *)calloc(1, sizeof(resdef))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	newdef->name = NULL;
	/* calloc will have zeroed flags and the type structure */

	return newdef;
}

/**
 * @brief
 * 		resdef copy constructor
 *
 * @param[in]	olddef	-	resdef to copy
 *
 * @return	duplicated resdef *
 */
resdef *
dup_resdef(resdef *olddef)
{
	resdef *newdef;

	newdef = new_resdef();

	if (newdef == NULL)
		return NULL;

	newdef->type = olddef->type;
	newdef->flags = olddef->flags;
	newdef->name = string_dup(olddef->name);

	if (newdef->name == NULL) {
		free(newdef);
		return NULL;
	}

	return newdef;
}

/**
 * @brief
 * 		copy constructor for array of resdefs
 *
 * @param[in]	odef_arr	-	array of resdefs to copy
 *
 * @return	duplicated array of resdef **s
 */
resdef **
dup_resdef_array(resdef **odef_arr)
{
	resdef **ndef_arr;
	int ct;
	int i;

	if (odef_arr == NULL)
		return NULL;

	ct = count_array(odef_arr);

	ndef_arr = (resdef **)malloc((ct + 1) * sizeof(resdef*));
	if (ndef_arr == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	for (i = 0; odef_arr[i] != NULL; i++) {
		ndef_arr[i] = dup_resdef(odef_arr[i]);
		if (ndef_arr[i] == NULL) {
			free_resdef_array(ndef_arr);
			return NULL;
		}
	}
	ndef_arr[i] = NULL;

	return ndef_arr;
}

/**
 * @brief
 * 		resdef destructor
 *
 * @param[in,out]	def	-	resdef to free
 *
 * @return	void
 */
void
free_resdef(resdef *def)
{
	if (def->name != NULL)
		free(def->name);

	free(def);
}

/**
 * @brief
 * 		add resdef to resdef array
 *
 * @param[in,out]	resdef_arr	-	pointer to an array of resdef to be added to(i.e. resdef ***)
 * @param[in]	def	-	def to add to array
 *
 * @return	int
 * @retval	index	: index of string on success
 * @retval	-1	: failure
 */
int
add_resdef_to_array(resdef ***resdef_arr, resdef *def)
{
	resdef **tmp_arr;
	int cnt;

	if (resdef_arr == NULL || def == NULL)
		return -1;

	cnt = count_array(*resdef_arr);

	tmp_arr = (resdef **) realloc(*resdef_arr, (cnt + 2) * sizeof(resdef*));
	if (tmp_arr == NULL)
		return -1;

	tmp_arr[cnt] = def;
	tmp_arr[cnt+1] = NULL;

	*resdef_arr = tmp_arr;

	return cnt;
}

/**
 * @brief
 *  	make a copy of a resdef array -- array itself is new memory,
 *      pointers point to the same thing.
 *
 * @param[in]	deflist	-	array to copy
 *
 * @returns	resdef **
 * @retval	copied array
 * @retval	NULL	: on error
 */
resdef **
copy_resdef_array(resdef **deflist)
{
	resdef **new_deflist;
	int cnt;

	if (deflist == NULL)
		return NULL;

	cnt = count_array(deflist);
	new_deflist = (resdef **)malloc((cnt + 1) * sizeof(resdef*));
	if (new_deflist == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}
	memcpy(new_deflist, deflist, (cnt+1)*sizeof(resdef*));

	new_deflist[cnt] = NULL;

	return new_deflist;
}

/**
 * @brief
 * 		destructor for array of resdef
 *
 * @param[in]	deflist	-	array of resdef to free
 *
 * @return	void
 */
void
free_resdef_array(resdef **deflist)
{
	int i;

	if (deflist == NULL)
		return;

	for (i = 0; deflist[i] != NULL; i++)
		free_resdef(deflist[i]);

	free(deflist);
}


/**
 * @brief
 * 		find and return a resdef entry by name
 *
 * @param[in]	deflist	-	array of resdef to search
 * @param[in] name	-	name of resource to search for
 *
 * @return	resdef *
 * @retval	found resource def
 * @retval	NULL	: if not found
 */
resdef *
find_resdef(resdef **deflist, const char *name)
{
	int i;

	if (deflist == NULL || name == NULL)
		return NULL;

	for (i = 0; deflist[i] != NULL && strcmp(deflist[i]->name, name) != 0; i++)
		;

	return deflist[i];
}

/**
 * @brief
 * 		does resdef exist in a resdef array?
 *
 * @param[in]	deflist	-	array of resdef to search
 * @param[in]	def	-	def of resource to search for
 *
 * @return	int
 * @retval	1	: if found
 * @retval	0	: if not found
 */
int
resdef_exists_in_array(resdef **deflist, resdef *def)
{
	int i;
	if (deflist == NULL || def == NULL)
		return 0;

	for (i = 0; deflist[i] != NULL && deflist[i] != def; i++)
		;
	return (deflist[i] != NULL);
}
/**
 * @brief
 * 		free and clear global resource definition pointers
 *
 * @return	void
 */
void
reset_global_resource_ptrs(void)
{
	/* references into allres, only need to free() */
	if (conf.resdef_to_check != NULL) {
		free(conf.resdef_to_check);
		conf.resdef_to_check = NULL;
	}
	if (consres != NULL) {
		free(consres);
		consres = NULL;
	}
	if (boolres != NULL) {
		free(boolres);
		boolres = NULL;
	}
	update_sorting_defs(SD_FREE);

	clear_last_running();

	/* The above references into this array.  We now free the memory */
	if (allres != NULL) {
		free_resdef_array(allres);
		allres = NULL;
	}
	clear_limres();
}

/**
 * @brief
 * 		checks if a resource avail is set.
 *
 * @param[in]	res	-	resource to see if it is set
 *
 * @return	int
 * @retval	1	: is set
 * @retval	0	: not set
 */
int
is_res_avail_set(schd_resource *res)
{
	if (res == NULL)
		return 0;

	if (res->type.is_string) {
		if (res->str_avail != NULL && res->str_avail[0] != NULL)
			return 1;
	}
	else if (res->avail != SCHD_INFINITY_RES)
		return 1;

	return 0;
}

/**
 * @brief
 * 		add the resource signature of 'res' to the string 'sig'
 *
 * @param[in,out]	sig	-	resource signature we're adding to
 * @param[in,out]	sig_size	-	size of string sig
 * @param[in]	res	-	the resource to add to sig
 *
 * @return	success/failure
 * @retval	1	: success
 * @retval	0	: failure
 */
int
add_resource_sig(char **sig, int *sig_size, schd_resource *res)
{
	if (sig == NULL || res == NULL)
		return 0;

	if (pbs_strcat(sig, sig_size, res->name) == 0)
		return 0;
	if (pbs_strcat(sig, sig_size, "=") == 0)
		return 0;
	if (pbs_strcat(sig, sig_size, res_to_str(res, RF_AVAIL)) == 0)
		return 0;

	return 1;
}
/**
 * @brief
 * 		create node string resource node signature based on the resources
 *      in order from the 'resources' parameter.  This signature can be used
 *      to compare two nodes to see if they are equivalent resource wise
 * @par
 *      FORM: res0=val:res1=val:...:resN=val
 *      Where 0, 1, .., N are indices into the resources array
 *
 * @param[in]	node	-	node to create signature from
 * @param[in]	resources	-	string array of resources
 * @param[in]	flags	-	CHECK_ALL_BOOLS - include all booleans even if not in resources
 *
 * @return	char *
 * @retval	signature of node
 * @retval	NULL	: on error
 *
 * @par	it is the responsibility of the caller to free string returned
 */
char *
create_resource_signature(schd_resource *reslist, resdef **resources, unsigned int flags)
{
	char *sig = NULL;
	int sig_size = 0;
	int i;
	schd_resource *res;

	if (reslist == NULL || resources == NULL)
		return NULL;

	if ((sig = (char *)malloc(1024)) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}
	sig_size = 1024;
	sig[0] = '\0';

	for (i = 0; resources[i] != NULL; i++) {
		res = find_resource(reslist, resources[i]);
		if (res != NULL) {
			if (res->indirect_res != NULL) {
				res = res->indirect_res;
			}
			if (is_res_avail_set(res)) {
				add_resource_sig(&sig, &sig_size, res);
				if (pbs_strcat(&sig, &sig_size, ":") == NULL) {
					free(sig);
					return NULL;
				}
			}
		}
	}

	if ((flags & ADD_ALL_BOOL)) {
		for (i = 0; boolres[i] != NULL; i++) {
			if (!resdef_exists_in_array(resources, boolres[i])) {
				res = find_resource(reslist, boolres[i]);
				if (res != NULL) {
					add_resource_sig(&sig, &sig_size, res);
					if (pbs_strcat(&sig, &sig_size, ":") == NULL) {
						free(sig);
						return NULL;
					}
				}
			}
		}
	}
	/* we will have a trailing ':' if we did anything, so strip it*/
	if (sig[0] != '\0')
		sig[strlen(sig) - 1] = '\0';

	return sig;
}



/**
 * @brief
 * 		query the resource definition from the server and create derived
 *        data structures.  Only query if required.
 *
 * @param[in]	pbs_sd	-	connection descriptor to the pbs server
 *
 * @return	int
 * @retval	1	: success - we've updated the global resdef arrays
 * @retval	0	: failure - we haven't updated the global resdef arrays.  Scheduling
 *                     		should not continue.
 */
int
update_resource_defs(int pbs_sd)
{
	int error = 0;
	/* only query when needed*/
	if (allres != NULL)
		return 1;

	allres = query_resources(pbs_sd);

	if (allres != NULL) {
		consres = (resdef**) filter_array((void **) allres,
			def_is_consumable, NULL, NO_FLAGS);
		if (consres == NULL)
			error = 1;

		if (!error) {
			boolres = (resdef**) filter_array((void **) allres,
				def_is_bool, NULL, NO_FLAGS);
			if (boolres == NULL)
				error = 1;
		}


		if (conf.res_to_check != NULL) {
			conf.resdef_to_check = resstr_to_resdef(conf.res_to_check);
			if (conf.resdef_to_check == NULL)
				error = 1;
		}
		update_sorting_defs(SD_UPDATE);
	}
	else
		error = 1;

	if (error) {
		if (consres != NULL) {
			free(consres);
			consres = NULL;
		}
		if (boolres != NULL) {
			free(boolres);
			boolres = NULL;
		}

		if (conf.resdef_to_check != NULL) {
			free(conf.resdef_to_check);
			conf.resdef_to_check = NULL;
		}
		if (allres != NULL) {
			free_resdef_array(allres);
			allres = NULL;
		}

		return 0;
	}

	return 1;
}

/**
 * @brief
 * 		convert an array of string resource names into resdefs
 *
 * @param[in]	resstr	-	array of resource strings
 *
 * @return	resdef array
 * @retval	NULL	: on error
 */
resdef **
resstr_to_resdef(char **resstr)
{
	int cnt;
	int i;
	int j;
	resdef **tmparr;
	resdef *def;

	if (resstr == NULL)
		return NULL;

	cnt = count_array(resstr);
	if ((tmparr = (resdef **)malloc((cnt + 1) * sizeof(resdef *))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	for (i = 0, j = 0; resstr[i] != NULL; i++) {
		def = find_resdef(allres, resstr[i]);
		if (def != NULL) {
			tmparr[j] = def;
			j++;
		}
		else {
			log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, resstr[i], "Unknown Resource");
		}
	}
	tmparr[j] = NULL;

	return tmparr;
}

/**
 * @brief
 * 		safely access allres by index.  This can be used if allres is NULL
 *
 * @param[in]	ind	-	index into allres array
 *
 * @return	resdef*
 */
resdef *
getallres(enum resource_index ind)
{
	if (allres == NULL)
		return NULL;
	return allres[ind];
}

/**
 * @brief
 * 		collect a unique list of resource definitions from an array of requests
 *
 * @param[in]	resresv_arr	-	array of requests
 *
 * @return	array of resource definitions
 */
resdef **
collect_resources_from_requests(resource_resv **resresv_arr)
{
	int i, j;
	resource_req *req;
	resdef **defarr = NULL;

	for (i = 0; resresv_arr[i] != NULL; i++) {
		resource_resv *r = resresv_arr[i];

		/* schedselect: node resources - resources to be satisfied on the nodes */
		if (r->select != NULL && r->select->defs != NULL) {
			for (j = 0; r->select->defs[j] != NULL; j++) {
				if (!resdef_exists_in_array(defarr, r->select->defs[j]))
					add_resdef_to_array(&defarr, r->select->defs[j]);
			}
		}
		/*
		 * execselect: select created from the exec_vnode.  This is likely to
		 * be a subset of resources from schedselect + 'vnode'.  It is possible
		 * that a job was run with qrun -H (res=val) where res is not part of
		 * the schedselect.  The exec_vnode is taken directly from the -H argument
		 * The qrun -H case is why we need to do this check.
		 */
		if (r->execselect != NULL && r->execselect->defs != NULL) {
			if ((r->job != NULL && in_runnable_state(r)) ||
				(r->resv != NULL && (r->resv->resv_state == RESV_BEING_ALTERED || r->resv->resv_substate == RESV_DEGRADED))) {
				for (j = 0; r->execselect->defs[j] != NULL;j++) {
					if (!resdef_exists_in_array(defarr, r->execselect->defs[j]))
						add_resdef_to_array(&defarr, r->execselect->defs[j]);
				}
			}
		}
		/* Resource_List: job wide resources: resources submitted with
		 * qsub -l and resources with the ATTR_DFLAG_RASSN which the server
		 * sums all the requested amounts in the select and sets job wide
		 */
		for (req = r->resreq; req != NULL; req = req->next) {
			if (conf.resdef_to_check == NULL ||
				resdef_exists_in_array(conf.resdef_to_check, req->def)) {
				if (!resdef_exists_in_array(defarr, req->def))
					add_resdef_to_array(&defarr, req->def);
			}
		}
	}
	return defarr;
}

/**
 * @brief
 * 		filter function for filter_array().  Used to filter out host and vnode
 *
 * @param[in]	v	-	pointer to resource definition structure.
 * @param[in]	arg	-	argument (not used)
 *
 * @return	int
 * @retval	1	: no host vnode.
 * @retval	0	: host vnode available.
 */
int
no_hostvnode(void *v, void *arg)
{
	resdef *r = (resdef *)v;
	if (r == getallres(RES_HOST) || r == getallres(RES_VNODE))
		return 0;
	return 1;
}

/**
 * @brief
 * 		filter function for filter_array().  Used to filter for resources
 * 		that are server/queue level and get summed at the job level
 *
 * @param[in]	v	-	pointer to resource definition structure.
 * @param[in]	arg	-	argument (not used)
 *
 * @return	int
 * @retval	1	: reassigned vnode.
 * @retval	0	: not reassigned.
 */
int
def_rassn(void *v, void *arg)
{
	resdef *r = (resdef *)v;
	if (r->flags & ATR_DFLAG_RASSN)
		return 1;
	return 0;
}

/**
 * @brief
 * 		filter function for filter_array().  Used to filter for resources
 * 		that are host based and get summed at the job level
 *
 * @param[in]	v	-	pointer to resource definition structure.
 * @param[in]	arg	-	argument (not used)
 *
 * @return	int
 * @retval	1	: reassigned vnode.
 * @retval	0	: not reassigned.
 */
int
def_rassn_select(void *v, void *arg)
{
	resdef *r = (resdef *)v;
	if ((r->flags & ATR_DFLAG_RASSN) && (r->flags & ATR_DFLAG_CVTSLT))
		return 1;
	return 0;
}

/**
 * @brief filter function for filter_array(). Used to filter out non consumable resources
 */
int
filter_noncons(void *v, void *arg)
{
	resdef *r = (resdef *)v;
	if (r->type.is_non_consumable)
		return 1;
	return 0;
}

/**
 * @brief update the resource definition pointers in the sort_info structures
 *
 * @par	We parse our config file when we start.  We do not have the resource
 *      definitions at that time.  They also can change over time if the server
 *      sends us a SCH_CONFIGURE command.
 *
 * @param[in]	op	-	update(non-zero) or free definitions(0)
 */
void update_sorting_defs(int op)
{
	int i, j;
	const char *prefix = NULL;

	/* Job sorts */
	for (i = 0; i < 4; i++) {
		struct sort_info *si;
		int obj;
		switch(i)
		{
			case 0:
				si = conf.prime_node_sort;
				obj = SOBJ_NODE;
				prefix = "Prime node";
				break;
			case 1:
				si = conf.non_prime_node_sort;
				obj = SOBJ_NODE;
				prefix = "Non-prime node";
				break;
			case 2:
				si = conf.prime_sort;
				obj = SOBJ_JOB;
				prefix = "Prime job";
				break;
			case 3:
				si = conf.non_prime_sort;
				obj = SOBJ_JOB;
				prefix = "Non-prime job";
				break;
			default:
				si = NULL;
				obj = SOBJ_JOB;
		}
		if (si != NULL) {
			for (j = 0; si[j].res_name != NULL; j++) {
				if (op == SD_UPDATE) {
					si[j].def = find_resdef(allres, si[j].res_name);
					if (si[j].def == NULL && !is_speccase_sort(si[j].res_name, obj))
						log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, CONFIG_FILE,
							"%s sorting resource %s is not a valid resource", prefix, si[j].res_name);
				} else
					si[j].def = NULL;

			}
		}
	}
}

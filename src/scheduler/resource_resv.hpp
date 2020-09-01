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

#ifndef	_RESOURCE_RESV_H
#define	_RESOURCE_RESV_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.hpp"

/*
 *      new_resource_resv() - allocate and initialize a resource_resv struct
 */
#ifdef NAS /* localmod 005 */
resource_resv *new_resource_resv(void);
#else
resource_resv *new_resource_resv();
#endif /* localmod 005 */

/*
 *      free_resource_resv - free a resource resv strcture an all of it's ptrs
 */
void free_resource_resv(resource_resv *resresv);

/*
 * pthread routine to free resource_resv array chunk
 */
void
free_resource_resv_array_chunk(th_data_free_resresv *data);

/*
 *      free_resource_resv_array - free an array of resource resvs
 */
void free_resource_resv_array(resource_resv **resresv);


/*
 *      dup_resource_resv - duplicate a resource resv structure
 */
resource_resv *dup_resource_resv(resource_resv *oresresv, server_info *nsinfo,
		queue_info *nqinfo, schd_error *err);

/*
 * pthread routine for duping a chunk of resresvs
 */
void dup_resource_resv_array_chunk(th_data_dup_resresv *data);
/*
 *      dup_resource_resv_array - dup a array of pointers of resource resvs
 */
resource_resv **
dup_resource_resv_array(resource_resv **oresresv_arr,
	server_info *nsinfo, queue_info *nqinfo);

/*
 *      is_resource_resv_valid - do simple validity checks for a resource resv
 *      returns 1 if valid 0 if not
 */
int is_resource_resv_valid(resource_resv *resresv, schd_error *err);

/*
 *      find_resource_resv - find a resource_resv by name
 */
resource_resv *find_resource_resv(resource_resv **resresv_arr, char *name);

/*
 * find a resource_resv by unique numeric rank

 */
resource_resv *find_resource_resv_by_indrank(resource_resv **resresv_arr, int index, int rank);

/**
 *  find_resource_resv_by_time - find a resource_resv by name and start time
 */
resource_resv *find_resource_resv_by_time(resource_resv **resresv_arr, char *name, time_t start_time);

/*
 *      find_resource_req - find a resource_req from a resource_req list
 */
resource_req *find_resource_req_by_str(resource_req *reqlist, const char *name);

/*
 *	find resource_req by resource definition
 */
resource_req *find_resource_req(resource_req *reqlist, resdef *def);

/*
 *	find resource_count by resource definition
 */
resource_count *find_resource_count(resource_count *reqlist, resdef *def);

/*
 *      new_resource_req - allocate and initalize new resoruce_req
 */
#ifdef NAS /* localmod 005 */
resource_req *new_resource_req(void);
#else
resource_req *new_resource_req();
#endif /* localmod 005 */

/*
 * new_resource_count - allocate and initalize new resource_count
 */
resource_count *new_resource_count();

/*
 * find_alloc_resource_req[_by_str] -
 * find resource_req by name/resource definition  or allocate and
 * initialize a new resource_req also adds new one to the list
 */
resource_req *find_alloc_resource_req(resource_req *reqlist, resdef *def);
resource_req *find_alloc_resource_req_by_str(resource_req *reqlist, char *name);

/*
 * find resource_count by resource definition or allocate
 */
resource_count *find_alloc_resource_count(resource_count *reqlist, resdef *def);

/*
 *      free_resource_req_list - frees memory used by a resource_req list
 */
void free_resource_req_list(resource_req *list);

/*
 *	free_resource_req - free memory used by a resource_req structure
 */
void free_resource_req(resource_req *req);

/*
 *      free_resource_count_list - frees memory used by a resource_count list
 */
void free_resource_count_list(resource_count *list);

/*
 *	free_resource_count - free memory used by a resource_count structure
 */
void free_resource_count(resource_count *req);

/*
 *	set_resource_req - set the value and type of a resource req
 */
int set_resource_req(resource_req *req, const char *val);

/*
 *
 *      dup_resource_req_list - duplicate a resource_req list
 */
resource_req *dup_resource_req_list(resource_req *oreq);

resource_req *dup_selective_resource_req_list(resource_req *oreq, resdef **deflist);


/*
 *	dup_resource_count_list - duplicate a resource_req list
 */
resource_count *dup_resource_count_list(resource_count *oreq);

/*
 *      dup_resource_req - duplicate a resource_req struct
 */
resource_req *dup_resource_req(resource_req *oreq);

/*
 *	dup_resource_count - duplicate a resource_count struct
 */
resource_count *dup_resource_count(resource_count *oreq);

/*
 *      update_resresv_on_run - update information kept in a resource_resv
 *                              struct when one is started
 */
void update_resresv_on_run(resource_resv *resresv, nspec **nspec_arr);

/*
 *      update_resresv_on_end - update a resource_resv structure when
 *                                    it ends
 */
void update_resresv_on_end(resource_resv *resresv, const char *job_state);


/*
 *      resource_resv_filter - filters jobs on specified argument
 */
resource_resv **
resource_resv_filter(resource_resv **resresv_arr, int size,
	int (*filter_func)(resource_resv*, void*), void *arg, int flags);


/*
 *      remove_resresv_from_array - remove a resource_resv from an array
 *                                  without leaving a hole
 */
int
remove_resresv_from_array(resource_resv **resresv_arr,
	resource_resv *resresv);

/*
 *      add_resresv_to_array - add a resource resv to an array
 *                         note: requires reallocating array
 */
resource_resv **
add_resresv_to_array(resource_resv **resresv_arr,
	resource_resv *resresv, int flags);

/*
 *      copy_resresv_array - copy an array of resource_resvs by name.
 *                      This is useful  when duplicating a data structure
 *                      with a job array in it which isn't easily reproduced.
 *
 *      NOTE: if a job in resresv_arr is not in tot_arr, that resresv will be
 *              left out of the new array
 */
resource_resv **
copy_resresv_array(resource_resv **resresv_arr,
	resource_resv **tot_arr);

/*
 *	is_resresv_running - is a resource resv in the running state
 *			     for a job it's in the "R" state
 *			     for an advanced reservation it is running
 */
int is_resresv_running(resource_resv *resresv);

/*
 *	new_place - allocate and initialize a placement spec
 *
 *	returns newly allocated place
 */
#ifdef NAS /* localmod 005 */
place *new_place(void);
#else
place *new_place();
#endif /* localmod 005 */

/*
 *	free_place - free a placement spec
 */
void free_place(place *pl);

/*
 *	dup_place - duplicate a place structure
 */
place *dup_place(place *pl);

/*
 *	compare_res_to_str - compare a resource structure of type string to
 *			     a character array string
 */
int compare_res_to_str(schd_resource *res, char *str, enum resval_cmpflag);

/*
 *	compare_non_consumable - perform the == operation on a non consumable
 *				resource and resource_req
 *	returns 1 for a match or 0 for not a match
 */
int compare_non_consumable(schd_resource *res, resource_req *req);

/* compare two resource req lists for equality.  Only compare resources in comparr */
int compare_resource_req_list(resource_req *req1, resource_req *req2, resdef **comparr);

/* compare two resource_reqs for equality*/
int compare_resource_req(resource_req *req1, resource_req *req2);



/*
 *	new_chunk - constructor for chunk
 */
#ifdef NAS /* localmod 005 */
chunk *new_chunk(void);
#else
chunk *new_chunk();
#endif /* localmod 005 */

/*
 *	dup_chunk_array - array copy constructor for array of chunk ptrs
 */
chunk **dup_chunk_array(chunk **old_chunk_arr);

/*
 *	dup_chunk - copy constructor for chunk
 */
chunk *dup_chunk(chunk *ochunk);

/*
 *	free_chunk_array - array destructor for array of chunk ptrs
 */
void free_chunk_array(chunk **chunk_arr);

/*
 *	free_chunk - destructor for chunk
 */
void free_chunk(chunk *ch);

/*
 *	new_selspec - constructor for selspec
 */
#ifdef NAS /* localmod 005 */
selspec *new_selspec(void);
#else
selspec *new_selspec();
#endif /* localmod 005 */

/*
 *	dup_selspec - copy constructor for selspec
 */
selspec *dup_selspec(selspec *oldspec);

/*
 *	free_selspec - destructor for selspec
 */
void free_selspec(selspec *spec);
/*
 *
 * find a resource resv by calling a caller provided comparison function
 *
 *	resresv_arr - array of resource_resvs to search
 *	int cmp_func(resource_resv *rl, void *cmp_arg)
 *	cmp_arg - opaque argument for cmp_func()
 *
 * return found resource_resv or NULL
 *
 */
resource_resv *
find_resource_resv_func(resource_resv **resresv_arr,
	int (*cmp_func)(resource_resv*, void*), void *cmp_arg);
/*
 *
 * function used by find_resource_resv_func to see if two subjobs are
 * part of the same job array (e.g., 1234[])
 *
 */
int cmp_job_arrays(resource_resv *resresv, void *arg);

/*
 * create_resource_req - create a new resource_req
 *
 *	return new resource_req or NULL
 */
resource_req *create_resource_req(const char *name, const char *value);

/*
 * create a select from an nspec array to place chunks back on the
 *        same nodes as befor
 *
 * return converted select string
 */
char *create_select_from_nspec(nspec **nspec_array);

/* function returns true if job/resv is in a state which it can be run */
int in_runnable_state(resource_resv *resresv);

#ifdef	__cplusplus
}
#endif
#endif /* _RESOURCE_RESV_H */

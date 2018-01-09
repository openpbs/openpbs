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
#ifndef	_MISC_H
#define	_MISC_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.h"
#include "server_info.h"
#include "queue_info.h"
#include "job_info.h"

/*
 *	string_dup - duplicate a string
 */
char *string_dup(char *str);

/*
 *	concat_str - contactenate up to three strings together in newly
 *		     allocated memory
 *	  str1 - first string to concat
 *	  str2 - second string to concat
 *	  str3 - third string to concat -- could be NULL
 *	  append - boolean to determine if str1 should be freed
 *
 *
 *	returns newly allocated string with strings concatenated
 */
char *concat_str(char *str1, char *str2, char *str3, int append);


/*
 *      res_to_num - convert a resource string to an integer in the lowest
 *                      form of resource on the machine (btye/word)
 *                      example: 1kb -> 1024 or 1kw -> 1024
 */
sch_resource_t res_to_num(char * res_str, struct resource_type *type);

/*
 *      skip_line - find if the line of the config file needs to be skipped
 *                  due to it being a comment or other means
 */
int skip_line(char *line);

/*
 *      schdlog - write a log entry to the scheduler log file using log_record
 */

void schdlog(int event, int class, int sev, const char *name, const char *text);

/*
 *      schdlogerr - combination of schdlog and translate_fail_code()
 *                   If we're actually going to log a message, translate
 *                   err into a message and then log it.  The translated
 *                   error will be printed after the message
 */
void
schdlogerr(int event, int class, int sev, char *name, char *text,
	schd_error *err);

/*
 *
 *      take a generic NULL terminated pointer array and return a
 *      filtered specialized array based on calling filter_func() on every
 *      member.  This can be used with any standard scheduler array
 *	like resource_resv or node_info or resdef
 *
 *      filter_func prototype: int func( void *, void * )
 *                                       object   arg
 *		  object - specific member of ptrarr[]
 *		  arg    - arg parameter
 *              - returns 1: ptr will be added to filtered array
 *              - returns 0: ptr will NOT be added to filtered array
 */
void **
filter_array(void **ptrarr, int (*filter_func)(void*, void*),
	void *arg, int flags);

/**
 * 	calc_time_left_STF - calculate the amount of time left
 *  for minimum duration and maximum duration of a STF resource resv
 *
 */
int calc_time_left_STF(resource_resv *resresv, sch_resource_t* min_time_left);

/*
 *      dup_string_array - duplicate an array of strings
 */
char **dup_string_array(char **ostrs);

/*
 *      string_array_verify - verify two string arrays are equal
 */
unsigned string_array_verify(char **sa1, char **sa2);

/*
 * find index of str in strarr
 */
int find_string_ind(char **strarr, char *str);

/*
 *	find_string - find a string in a NULL terminated string array
 */
int find_string(char **strarr, char *str);

/*
 *
 *	match_string_array - match two NULL terminated string arrays
 *
 *	returns: SA_FULL_MATCH		: full match
 *		 SA_SUB_MATCH		: one array is a subset of the other
 *		 SA_PARTIAL_MATCH	: at least one match but not all
 *		 SA_NO_MATCH		: no match
 *
 */
enum match_string_array_ret match_string_array(char **strarr1, char **strarr2);

/*
 *
 *	match_string_to_array - see if a string array contains a single string
 *
 *	returns value from match_string_array()
 *
 */
enum match_string_array_ret match_string_to_array(char *str, char **strarr);

/*
 * convert a string array into a printable string
 */
char *string_array_to_str(char **strarr);

/*
 *      calc_time_left - calculate the remaining time of a job
 */
int calc_time_left(resource_resv *jinfo, int use_hard_duration);

/*
 *      cstrcmp - check string compare - compares two strings but doesn't bomb
 *                if either one is null
 */
int cstrcmp(char *s1, char *s2);

/*
 *      is_num - checks to see if the string is a number, size, float
 *               or time in string form
 */
int is_num(char *str);

/*
 *	count_array - count the number of elements in a NULL terminated array
 *		      of pointers
 */
int count_array(void **arr);

/*
 *	remove_ptr_from_array - remove a pointer from a ptr list and move
 *				the rest of the pointers up to fill the hole
 *				Pointer array size will not change - an extra
 *				NULL is added to the end
 *
 *	returns non-zero if the ptr was successfully removed from the array
 *		zero if the array has not been modified
 */
int remove_ptr_from_array(void **arr, void *ptr);

/*
 *      is_valid_pbs_name - is str a valid pbs username (POSIX.1 + ' ')
 *                          a valid name is: alpha numeric '-' '_' '.' or ' '
 */
int is_valid_pbs_name(char *str, int len);

/*
 *
 *      res_to_str - turn a resource (resource/resource_req) into
 *                   a string for printing.
 *      returns the resource in string format.  It is returned in a static
 *              buffer
 *              a null string ("") is returned on error
 */
char *res_to_str(void *p, enum resource_fields fld);

/*
 *
 *    turn a resource/req into a string for printing (reentrant)
 *
 */
char *res_to_str_r(void *p, enum resource_fields fld, char *buf, int bufsize);

/**
 * convert a number that is a resource into a string with a non-expandable
 * buffer. This is useful for size types or scheduler constants
 */
char *
res_to_str_c(sch_resource_t amount, resdef *def, enum resource_fields fld,
	char *buf, int bufsize);


/**
 *
 *    @brief turn a resource (resource/resource_req) into
 *                 a string for printing.  If the buffer needs expanding, it
 *		   will be expanded based on flags
 * flags:
 * 		NOPRINT_INT_CONST - print "" instead of internal sched constants
 *		NOEXPAND - don't expand the buffer, just fill to the max size
 */
char *
res_to_str_re(void *p, enum resource_fields fld, char **buf,
	int *bufsize, unsigned int flags);

int copy_attr_value(char **dest, char *src);

/*
 * clear schd_error structure for reuse
 */
void clear_schd_error(schd_error *err);

/* schd_error constructor */
schd_error *new_schd_error(void);

/* schd_error copy constructor */
schd_error *dup_schd_error(schd_error *oerr);

/* does a shallow copy err = oerr safely moving all argument data to err */
void move_schd_error(schd_error *err, schd_error *oerr);

/* do a deep copy of err, but don't dup the error itself. */
void copy_schd_error(schd_error *err, schd_error *oerr);

/* safely set the schd_config arg buffers without worrying about leaking */
void set_schd_error_arg(schd_error *err, int arg_field, char *arg);

/* set the status code and error code of a schd_error structure to ensure both are set together  */
void set_schd_error_codes(schd_error *err, enum schd_err_status status_code, enum sched_error error_code);

/* schd_error destuctor */
void
free_schd_error(schd_error *err);
void
free_schd_error_list(schd_error *err_list);

/* helper functions to create schd_errors*/
schd_error *
create_schd_error(int error_code, int status_code) ;
schd_error *
create_schd_error_complex(int error_code, int status_code, char *arg1, char *arg2, char *arg3, char *errbuf);

/* add schd_errors to linked list */
void
add_err(schd_error **prev_err, schd_error *err);


/*
 * add string to NULL terminated string array
 */
int
add_str_to_array(char ***str_arr, char *str);

/*
 * add a string to a string array only if it is unique
 */
int
add_str_to_unique_array(char ***str_arr, char *str);

#ifdef	__cplusplus
}
#endif
#endif	/* _MISC_H */

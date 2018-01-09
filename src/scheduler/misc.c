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
 * @file    misc.c
 *
 * @brief
 * 		misc.c - This file contains Miscellaneous functions of scheduler.
 *
 * Functions included are:
 * 		string_dup()
 * 		concat_str()
 * 		add_str_to_unique_array()
 * 		add_str_to_array()
 * 		res_to_num()
 * 		skip_line()
 * 		schdlog()
 * 		schdlogerr()
 * 		filter_array()
 * 		dup_string_array()
 * 		find_string()
 * 		find_string_ind()
 * 		match_string_to_array()
 * 		match_string_array()
 * 		string_array_to_str()
 * 		string_array_verify()
 * 		calc_used_walltime()
 * 		calc_time_left_STF()
 * 		calc_time_left()
 * 		cstrcmp()
 * 		is_num()
 * 		count_array()
 * 		remove_ptr_from_array()
 * 		is_valid_pbs_name()
 * 		clear_schd_error()
 * 		new_schd_error()
 * 		dup_schd_error()
 * 		move_schd_error()
 * 		set_schd_error_arg()
 * 		set_schd_error_codes()
 * 		free_schd_error()
 * 		free_schd_error_list()
 * 		create_schd_error()
 * 		create_schd_error_complex()
 * 		add_err()
 * 		res_to_str()
 * 		res_to_str_c()
 * 		res_to_str_r()
 * 		res_to_str_re()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <ctype.h>
#include <string.h>
#include <errno.h>
#include <math.h>
#include <pbs_ifl.h>
#include <pbs_internal.h>
#include <pbs_error.h>
#include <log.h>
#include <pbs_share.h>
#include <libutil.h>
#include "config.h"
#include "constant.h"
#include "misc.h"
#include "globals.h"
#include "fairshare.h"
#include "resource_resv.h"
#include "resource.h"


/**
 * @brief
 *		string_dup - duplicate a string
 *
 * @param[in]	str	-	string to duplicate
 *
 * @return	newly allocated string
 *
 */

char *
string_dup(char *str)
{
	char *newstr;

	if (str == NULL)
		return NULL;

	if ((newstr = (char *) malloc(strlen(str) + 1)) == NULL) {
		log_err(errno, "string_dup", MEM_ERR_MSG);
		return NULL;
	}

	strcpy(newstr, str);

	return newstr;
}

/**
 * @brief
 *		concat_str - contactenate up to three strings together in newly
 *		     allocated memory
 *
 * @param[in]	str1	-	first string to concat
 * @param[in]	str2	-	second string to concat
 * @param[in]	str3	-	third string to concat -- could be NULL
 * @param[in]	append	-	boolean to determine if str1 should be freed
 *
 * @return	newly allocated string with strings concatenated
 *
 */
char *
concat_str(char *str1, char *str2, char *str3 , int append)
{
	char *newstr;
	int len;

	if (str1 == NULL && str2 != NULL) {
		str1 = strdup(str2);
		return str1;
	}

	if (str1 == NULL || str2 == NULL)
		return NULL;

	len = strlen(str1) + strlen(str2);
	if (str3 != NULL)
		len += strlen(str3);

	if ((newstr = malloc(len + 1)) == NULL) {
		log_err(errno, "concat_str", MEM_ERR_MSG);
		return NULL;
	}

	sprintf(newstr, "%s%s%s", str1, str2, str3 == NULL ? "" : str3);

	if (append)
		free(str1);

	return newstr;
}

/**
 * @brief
 * 		add a string to a string to a string array only if it is unique
 *
 * @param[in,out]	str_arr	-	array of strings of unique values
 * @param[in]	str	-	string to add
 * @return	int
 * @retval	index in array if success	: string is added to array
 * @retval	-1 failure	: string could not be added to the array
 */
int
add_str_to_unique_array(char ***str_arr, char *str)
{
	int ind;
	if (str_arr == NULL || str == NULL)
		return -1;

	ind = find_string_ind(*str_arr, str);
	if (ind >= 0) /* found it! */
		return ind;

	return add_str_to_array(str_arr, str);
}

/**
 * @brief
 * 		add string to string array
 *
 * @param[in]	str_arr	-	pointer to an array of strings to be added to(i.e. char ***)
 * @param[in]	str	-	string to add to array
 *
 * @return	int
 * @retval	index	-	index of string on success
 * @retval	-1	: failure
 */
int
add_str_to_array(char ***str_arr, char *str)
{
	char **tmp_arr;
	int cnt;

	if (str_arr == NULL || str == NULL)
		return -1;

	if (*str_arr == NULL)
		cnt = 0;
	else
		cnt = count_array((void **) *str_arr);

	tmp_arr = realloc(*str_arr, (cnt+2)*sizeof(char*));
	if (tmp_arr == NULL)
		return -1;

	tmp_arr[cnt] = string_dup(str);
	tmp_arr[cnt+1] = NULL;

	*str_arr = tmp_arr;

	return cnt;
}

/**
 * @brief
 * 		res_to_num - convert a resource string to a numeric sch_resource_t
 *
 * @param[in]	res_str	-	the resource string
 * @param[out]	type	-	the type of the resource
 *
 * @return	sch_resource_t
 * @retval	a number in kilobytes or seconds
 * @retval	0 for False, if type is boolean
 * @retval	1 for True, if type is boolean
 * @retval	SCHD_INFINITY	: if not a number
 *
 */
sch_resource_t
res_to_num(char *res_str, struct resource_type *type)
{
	sch_resource_t count = SCHD_INFINITY;	/* convert string resource to numeric */
	sch_resource_t count2 = SCHD_INFINITY;	/* convert string resource to numeric */
	char *endp;				/* used for strtol() */
	char *endp2;				/* used for strtol() */
	long multiplier = 1;			/* multiplier to count */
	int is_size = 0;			/* resource value is a size type */
	int is_time = 0;			/* resource value is a time spec */

	if (res_str == NULL)
		return SCHD_INFINITY;

	if (!strcasecmp(ATR_TRUE, res_str)) {
		if (type != NULL) {
			type->is_boolean = 1;
			type->is_non_consumable = 1;
		}
		count = 1;
	}
	else if (!strcasecmp(ATR_FALSE, res_str)) {
		if (type != NULL) {
			type->is_boolean = 1;
			type->is_non_consumable = 1;
		}
		count = 0;
	}
	else if (!is_num(res_str)) {
		if (type != NULL) {
			type->is_string = 1;
			type->is_non_consumable = 1;
		}
		count = SCHD_INFINITY;
	}
	else {
		count = (sch_resource_t) strtod(res_str, &endp);

		if (*endp == ':') { /* time resource -> convert to seconds */
			count2 = (sch_resource_t) strtod(endp+1, &endp2);
			if (*endp2 == ':') { /* form of HH:MM:SS */
				count *= 3600;
				count += count2 * 60;
				count += strtol(endp2 + 1, &endp, 10);
				if (*endp != '\0')
					count = SCHD_INFINITY;
			}
			else			 { /* form of MM:SS */
				count *= 60;
				count += count2;
			}
			multiplier = 1;
			is_time = 1;
		}
		else if (*endp == 'k' || *endp == 'K') {
			multiplier = 1;
			is_size = 1;
		}
		else if (*endp == 'm' || *endp == 'M') {
			multiplier = MEGATOKILO;
			is_size = 1;
		}
		else if (*endp == 'g' || *endp == 'G') {
			multiplier = GIGATOKILO;
			is_size = 1;
		}
		else if (*endp == 't' || *endp == 'T') {
			multiplier = TERATOKILO;
			is_size = 1;
		}
		else if (*endp == 'b' || *endp == 'B') {
			count = ceil(count / KILO);
			multiplier = 1;
			is_size = 1;
		}
		else if (*endp == 'w') {
			count = ceil(count / KILO);
			multiplier = SIZEOF_WORD;
			is_size = 1;
		}
		else	/* catch all */
			multiplier = 1;

		if (*endp != '\0' && *(endp + 1) == 'w')
			multiplier *= SIZEOF_WORD;

		if (type != NULL) {
			type->is_consumable = 1;
			if (is_size  )
				type->is_size = 1;
			else if (is_time)
				type->is_time = 1;
			else
				type->is_num = 1;
		}
	}

	return count * multiplier;
}

/**
 * @brief
 *      skip_line - find if the line of the config file needs to be skipped
 *                  due to it being a comment or other means
 *
 * @param[in]	line	-	the line from the config file
 *
 * @return	true:1/false:0
 * @retval	true	: if the line should be skipped
 * @retval	false	: if it should be parsed
 *
 */
int
skip_line(char *line)
{
	int skip = 0;				/* whether or not to skil the line */

	if (line != NULL) {
		while (isspace((int) *line))
			line++;

		/* '#' is comment in config files and '*' is comment in holidays file */
		if (line[0] == '\0' || line[0] == '#' || line[0] == '*')
			skip = 1;
	}

	return skip;
}

/**
 * @brief
 *		schdlog - write a log entry to the scheduler log file using log_record
 *
 * @param[in] event	-	the event type
 * @param[in] class	-	the event class
 * @param[in] sev   -	the severity of the log message
 * @param[in] name  -	the name of the object
 * @param[in] text  -	the text of the message
 *
 * @return nothing
 */

void
schdlog(int event, int class, int sev, const char *name, const char *text)
{
	struct tm *ptm;
	if (!(conf.log_filter & event) && text[0] != '\0') {
		log_record(event, class, sev, name, text);
		if (conf.logstderr) {
			time_t logtime;

			logtime = cstat.current_time + (time(NULL) - cstat.cycle_start);

			ptm = localtime(&logtime);
			if (ptm != NULL) {
				fprintf(stderr, "%02d/%02d/%04d %02d:%02d:%02d;%s;%s\n",
					ptm->tm_mon+1, ptm->tm_mday, ptm->tm_year+1900,
					ptm->tm_hour, ptm->tm_min, ptm->tm_sec,
					name, text);
			}
		}
	}
}

/**
 *	@brief  combination of schdlog and translate_fail_code()
 *		If we're actually going to log a message, translate
 *		err into a message and then log it.  The translated
 *		error will be printed after the message
 *
 *	@param[in] event - the event type
 *	@param[in] class - the event class
 *	@param[in] sev   - the severity of the log message
 *	@param[in] name  - the name of the object
 *	@param[in] text  - the text of the message
 *			if NULL, only print translated error text
 *	@param[in] err   - schderr error structure to be translated
 *
 *	@return nothing
 */
void
schdlogerr(int event, int class, int sev, char *name, char *text,
	schd_error *err)
{
	char logbuf[MAX_LOG_SIZE];
	char logbuf2[MAX_LOG_SIZE];

	if (err == NULL)
		return;

	if (!(conf.log_filter & event)) {
		translate_fail_code(err, NULL, logbuf);
		if (text == NULL)
			schdlog(event, class, sev, name, logbuf);
		else {
			snprintf(logbuf2, MAX_LOG_SIZE, "%s %s", text, logbuf);
			schdlog(event, class, sev, name, logbuf2);
		}
	}
}

/**
 * @brief
 * 		take a generic NULL terminated pointer array and return a
 *             filtered specialized array based on calling filter_func() on every
 *             member.  This can be used with any standard scheduler array
 *	       like resource_resv or node_info or resdef
 *
 * @param[in] ptrarr	-	the array to filter
 * @param[in] filter_func	-	pointer to a function that will filter the array
 * @param[in] arg	-	an optional arg passed to filter_func
 * @param[in] flags	-	control how ptrs are filtered
 *						FILTER_FULL - leave the filtered array full size
 *
 * @par
 * 	   filter_func prototype: @fn int func( void *, void * )
 *                                           object   arg
 *		  object - specific member of ptrarr[]
 *		  arg    - arg parameter
 *               - returns 1: ptr will be added to filtered array
 *               - returns 0: ptr will NOT be added to filtered array
 *
 * @return	void ** filtered array.
 */
void **
filter_array(void **ptrarr, int (*filter_func)(void*, void*),
	void *arg, int flags)
{
	void **new_arr = NULL;                      /* the filtered array */
	void **tmp;
	int i, j;
	int size;

	if (ptrarr == NULL || filter_func == NULL)
		return NULL;

	size = count_array((void **) ptrarr);

	if ((new_arr = (void **) malloc((size + 1) * sizeof(void *))) == NULL) {
		log_err(errno, __func__, "Error allocating memory");
		return NULL;
	}

	for (i = 0, j = 0; i < size; i++) {
		if (filter_func(ptrarr[i], arg)) {
			new_arr[j] = ptrarr[i];
			j++;
		}
	}
	new_arr[j] = NULL;

	if (!(flags & FILTER_FULL)) {
		if ((tmp = realloc(new_arr, (j+1) * sizeof(void *))) == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			free(new_arr);
			return NULL;
		}
		new_arr = tmp;
	}
	return new_arr;
}



/**
 * @brief
 *      dup_string_array - duplicate an array of strings
 *
 * @param[in]	ostrs	-	the array to copy
 *
 * @return	the duplicated array.
 *
 */
char **
dup_string_array(char **ostrs)
{
	char **nstrs = NULL;
	int i;

	if (ostrs != NULL) {
		for (i = 0; ostrs[i] != NULL; i++);

		if ((nstrs = (char **)malloc((i + 1) * sizeof(char**))) == NULL) {
			log_err(errno, "dup_string_array", "Error allocating memory");
			return NULL;
		}

		for (i = 0; ostrs[i] != NULL; i++)
			nstrs[i] = string_dup(ostrs[i]);

		nstrs[i] = NULL;
	}
	return nstrs;
}

/**
 * @brief
 *		find a string in a NULL terminated string array
 *
 * @param[in]	strarr	-	the string array to search
 * @param[in]	str	-	the string to find
 *
 * @return	int
 * @retval	1	: if the string is found
 * @retval	0	: the string is not found or on error
 *
 */
int
find_string(char **strarr, char *str)
{
	int ind;

	ind = find_string_ind(strarr, str);

	if (ind >= 0)
		return 1;

	return 0;
}

/**
 * @brief
 * 		find index of str in strarr
 *
 * @param[in]	strarr	-	the string array to search
 * @param[in]	str	-	the string to find
 *
 * @return	int
 * @retval	index of string
 * @retval	-1	: if not found
 */
int
find_string_ind(char **strarr, char *str)
{
	int i;
	if (strarr == NULL || str == NULL)
		return -1;

	for (i = 0; strarr[i] != NULL && strcmp(strarr[i], str); i++)
		;
	if (strarr[i] == NULL)
		return -1;

	return i;
}

/**
 * @brief
 *		match_string_to_array - see if a string array contains a single string
 *
 * @param[in]	strarr	-	the string array to search
 * @param[in]	str	-	the string to find
 *
 * @return	value from match_string_array()
 *
 */
enum match_string_array_ret match_string_to_array(char *str, char **strarr)
{
	char *mockarr[2];

	mockarr[0] = str;
	mockarr[1] = NULL;

	return match_string_array(strarr, (char **) mockarr);
}

/**
 * @brief
 * 		match two NULL terminated string arrays
 *
 * @param[in]	strarr	-	the string array to search
 * @param[in]	str	-	the string to find
 *
 * @return	enum match_string_array_ret
 * @retval	SA_FULL_MATCH	: full match
 * @retval	SA_SUB_MATCH		: full match of one array and it is
 *									a subset of the other
 * @retval	SA_PARTIAL_MATCH	: at least one match but not all
 * @retval	SA_NO_MATCH	: no match
 *
 */
enum match_string_array_ret match_string_array(char **strarr1, char **strarr2)
{
	int match = 0;
	int i;
	int strarr2_len;

	if (strarr1 == NULL || strarr2 == NULL)
		return SA_NO_MATCH;

	strarr2_len = count_array((void **)strarr2);

	for (i = 0; strarr1[i] != NULL; i++) {
		if (find_string(strarr2, strarr1[i]))
			match++;
	}

	/* i is the length of strarr1 since we just looped through the whole array */
	if (match == i && match == strarr2_len)
		return SA_FULL_MATCH;

	if (match == i || match == strarr2_len)
		return SA_SUB_MATCH;

	if (match)
		return SA_PARTIAL_MATCH;

	return SA_NO_MATCH;
}

/**
 * @brief
 * 		convert a string array into a printable string
 *
 * @param[in]	strarr	-	string array to convert
 *
 * @return	converted string stored in local static ptr (no need to free)
 *
 * @par MT-safe:	no
 *
 */
char *
string_array_to_str(char **strarr)
{
	static char *arrbuf = NULL;
	static int arrlen = 0;
	char *tmp;
	int len = 0;
	int i;

	if (strarr == NULL)
		return NULL;

	for (i = 0; strarr[i] != NULL; i++)
		len += strlen(strarr[i]);

	len += i; /* added space for the commas */

	if (arrlen <= len) {
		tmp = realloc(arrbuf, arrlen+len+1);
		if (tmp != NULL) {
			arrlen += len + 1;
			arrbuf = tmp;
		}
		else {
			log_err(errno, __func__, MEM_ERR_MSG);
			return "";
		}
	}

	arrbuf[0] = '\0';

	for (i = 0; strarr[i] != NULL; i++) {
		strcat(arrbuf, strarr[i]);
		strcat(arrbuf, ",");
	}
	arrbuf[strlen(arrbuf)-1] = '\0';

	return arrbuf;
}

/**
 * @brief
 *		string_array_verify - verify two string arrays are equal
 *
 * @param[in]	sa1	-	string array 1
 * @param[in]	sa2	-	string array 2
 *
 * @return	int
 * @retval	0	: array equal
 *					number of the first unequal string
 * @retval	(unsigned) -1	: on error
 *
 */
unsigned string_array_verify(char **sa1, char **sa2)
{
	int i;

	if (sa1 == NULL && sa2 == NULL)
		return 0;

	if (sa1 == NULL || sa2 == NULL)
		return (unsigned) -1;

	for (i = 0; sa1[i] != NULL && sa2[i] != NULL && !cstrcmp(sa1[i], sa2[i]); i++)
		;

	if (sa1[i] != NULL || sa2[i] != NULL)
		return i + 1;

	return 0;
}
/**
 * @brief
 * 		calc_used_walltime - calculate the  used amount of a resource resv
 *
 * @param[in]	resresv	-	the resource resv to calculate
 *
 * @return	used amount of the resource resv
 * @retval	0	: if resresv starts in the future
 *					or if the resource used for walltime is NULL
 */

time_t
calc_used_walltime(resource_resv *resresv)
{
	time_t used_amount = 0;
	resource_req *used = NULL;

	if (resresv == NULL)
		return 0;

	if (resresv->is_job && resresv->job !=NULL) {
		used = find_resource_req(resresv->job->resused, getallres(RES_WALLTIME));

		/* If we can't find the used structure, we will just assume no usage */
		if (used == NULL)
			used_amount = 0;
		else
			used_amount = (time_t) used->amount;
	} else {
		if (resresv->server->server_time > resresv->start)
			used_amount = resresv->server->server_time - resresv->start;
		else
			used_amount = 0;
	}
	return used_amount;
}
/**
 * @brief
 * 		calc_time_left_STF - calculate the amount of time left
 *  	for minimum duration and maximum duration of a STF resource resv
 *
 * 	@param[in]	resresv		-	the resource resv to calculate
 * 	@param[out]	min_time_left	-	time left to complete minimum duration
 *
 * 	@return	time left to complete maximum duration of the job
 * 	@retval	0	: if used amount is greater than duration
 * 	@retval	-1	: on error
 */
int
calc_time_left_STF(resource_resv *resresv, sch_resource_t* min_time_left)
{
	time_t 		used_amount = 0;

	if (min_time_left == NULL || resresv->duration == UNSPECIFIED)
		return -1;

	used_amount = calc_used_walltime(resresv);
	*min_time_left = IF_NEG_THEN_ZERO((resresv->min_duration - used_amount));

	return IF_NEG_THEN_ZERO((resresv->duration - used_amount));
}
/**
 * @brief
 *		calc_time_left - calculate the remaining time of a resource resv
 *
 * @param[in]	resresv	-	the resource resv to calculate
 * @param[in]	use_hard_duration - use the resresv's hard_duration instead of normal duration
 *
 * @return	time left on job
 * @retval	-1	: on error
 *
 */
int
calc_time_left(resource_resv *resresv, int use_hard_duration)
{
	time_t used_amount = 0;
	long duration;

	if (use_hard_duration && resresv->hard_duration == UNSPECIFIED)
		return -1;

	else if (!use_hard_duration && resresv->duration == UNSPECIFIED)
		return -1;

	if (use_hard_duration)
		duration = resresv->hard_duration;
	else
		duration = resresv->duration;

	used_amount = calc_used_walltime(resresv);

	return IF_NEG_THEN_ZERO(duration - used_amount);
}

/**
 * @brief
 *		cstrcmp	- check string compare - compares two strings but doesn't bomb
 *		  if either one is null
 *
 * @param[in]	s1	-	string one
 * @param[in]	s2	-	string two
 *
 * @return	int
 * @retval	-1	: if s1 < s2
 * @retval	0	: if s1 == s2
 * @retval	1	: if s1 > s2
 *
 */
int
cstrcmp(char *s1, char *s2)
{
	if (s1 == NULL && s2 == NULL)
		return 0;

	if (s1 == NULL && s2 != NULL)
		return -1;

	if (s1 != NULL && s2 == NULL)
		return 1;

	return strcmp(s1, s2);
}

/**
 * @brief
 *		is_num - checks to see if the string is a number, size, float
 *		 or time in string form
 *
 * @param[in]	str	-	the string to test
 *
 * @return	int
 * @retval	1	: if str is a number
 * @retval	0	: if str is not a number
 * @retval	-1	: on error
 *
 */
int
is_num(char *str)
{
	int i;
	char c;
	int colon_count = 0;
	int str_len = -1;

	if (str == NULL)
		return -1;

	if (str[0] == '-' || str[0] == '+')
		str++;

	str_len = strlen(str);
	for (i = 0; i < str_len && (isdigit(str[i]) || str[i] == ':'); i++) {
		if (str[i] == ':')
			colon_count++;
	}

	/* is the string completely numeric or a time(HH:MM:SS or MM:SS) */
	if (i == str_len && colon_count <= 2)
		return 1;

	/* is the string a size type resource like 'mem' */
	if ((i == (str_len - 2)) || (i == (str_len - 1))) {
		c = tolower(str[i]);
		if (c == 'k' || c == 'm' || c == 'g' || c == 't') {
			c = tolower(str[i+1]);
			if (c == 'b' || c == 'w' || c == '\0')
				return 1;
		} else if (i == (str_len - 1)) {
			/* catch the case of "b" or "w" */
			if (c == 'b' || c == 'w')
				return 1;
		}
	}

	/* last but not least, make sure we didn't stop on a decmal point */
	if (str[i] == '.') {
		for (i++ ; i < str_len && isdigit(str[i]); i++)
			;

		/* number is a float */
		if (i == str_len)
			return 1;
	}

	/* the string is not a number or a size or time */
	return 0;
}


/**
 * @brief
 *		count_array - count the number of elements in a NULL terminated array
 *		      of pointers
 *
 * @param[in]	arr	-	the array to count
 *
 * @return	number of elements in the array
 *
 */
int
count_array(void **arr)
{
	int i;

	if (arr == NULL)
		return 0;

	for (i = 0; arr[i] != NULL; i++)
		;

	return i;
}

/**
 * @brief
 *		remove_ptr_from_array - remove a pointer from a ptr list and move
 *				the rest of the pointers up to fill the hole
 *				Pointer array size will not change - an extra
 *				NULL is added to the end
 *
 *	  arr - pointer array
 *	  ptr - pointer to remove from array
 *
 *	returns non-zero if the ptr was successfully removed from the array
 *		zero if the array has not been modified
 *
 */
int
remove_ptr_from_array(void **arr, void *ptr)
{
	int i, j;

	if (arr == NULL || ptr == NULL)
		return 0;

	for (i = 0; arr[i] != NULL && arr[i] != ptr; i++)
		;

	if (arr[i] != NULL) {
		for (j = i; arr[j] != NULL; j++)
			arr[j] = arr[j+1];
		return 1;
	}

	return 0;
}

/**
 * @brief
 *		is_valid_pbs_name - is str a valid pbs username (POSIX.1 + ' ')
 *			    a valid name is: alpha numeric '-' '_' '.' ' '
 * 			    For fairshare entities: colen ':'
 *
 * @param[in]	str	-	string to check validity
 * @param[in]	len	-	length of str buffer or -1 if length is unknown
 *
 * @return	int
 * @retval	1	: valid PBS username
 * @retval	0	: not valid username
 */
int
is_valid_pbs_name(char *str, int len)
{
	int i;
	int valid = 1;

	if (str == NULL)
		return 0;

	/* if str is not null terminated, this could cause problems */
	if (len < 0)
		len = strlen(str) + 1;

	for (i = 0; i < len && valid; i++) {
		if (str[i] == '\0')
			break;
		if (!(isalpha(str[i]) || isdigit(str[i]) || str[i] == '.' ||
			str[i] == '-' || str[i] == '_' || str[i] == ' ' || str[i] == ':')) {
			valid = 0;
		}
	}

	if (i == len)
		valid = 0;

	return valid;
}

/**
 * @brief
 * 		clear an schd_error structure for reuse
 *
 * @param[in]	err	-	error structure to clear
 *
 * @return	void
 */
void
clear_schd_error(schd_error *err)
{
	if (err == NULL)
		return;

	set_schd_error_codes(err, SCHD_UNKWN, SUCCESS);
	err->rdef = NULL;

	free(err->arg1);
	err->arg1 = NULL;

	free(err->arg2);
	err->arg2 = NULL;

	free(err->arg3);
	err->arg3 = NULL;

	free(err->specmsg);
	err->specmsg = NULL;
}

/**
 * @brief
 *  	constructor schd_error
 *
 * @return	new schd_error strucuture
 * @retval	NULL	: Error
 */
schd_error *
new_schd_error() {
	schd_error *err;
	if ((err = malloc(sizeof(schd_error))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}
	set_schd_error_codes(err, SCHD_UNKWN, SUCCESS);
	err->rdef = NULL;
	err->arg1 = NULL;
	err->arg2 = NULL;
	err->arg3 = NULL;
	err->specmsg = NULL;
	err->next = NULL;
	return err;
}

/**
 * @brief
 * 		copy constructor for schd_error
 *
 * @param[in]	oerr	-	output error.
 *
 * @return	new schd_error structure
 * @retval	NULL	: Error
 */
schd_error *
dup_schd_error(schd_error *oerr) {
	schd_error *nerr;
	if(oerr == NULL)
		return NULL;

	nerr = new_schd_error();
	if(nerr == NULL)
		return NULL;

	/* Do shallow copy, dup pointers later */
	memcpy(nerr, oerr, sizeof(schd_error));

	nerr->arg1 = NULL;
	nerr->arg2 = NULL;
	nerr->arg3 = NULL;
	nerr->specmsg = NULL;
	nerr->next = NULL;

	if (oerr->arg1 != NULL) {
		nerr->arg1 = string_dup(oerr->arg1);
		if (nerr->arg1 == NULL) {
			free_schd_error(nerr);
			return NULL;
		}
	}
	if (oerr->arg2 != NULL) {
		nerr->arg2 = string_dup(oerr->arg2);
		if (nerr->arg2 == NULL) {
			free_schd_error(nerr);
			return NULL;
		}
	}
	if (oerr->arg3 != NULL) {
		nerr->arg3 = string_dup(oerr->arg3);
		if (nerr->arg3 == NULL) {
			free_schd_error(nerr);
			return NULL;
		}
	}
	if(oerr->specmsg != NULL) {
		nerr->specmsg = string_dup(oerr->specmsg);
		if(nerr->specmsg == NULL) {
			free_schd_error(nerr);
			return NULL;
		}
	}

	return nerr;
}

/**
 * @brief
 * 		make a shallow copy of a schd_error and move all argument data
 *		to err.
 *
 * @param[in]	err	-	schd_error to move TO
 * @param[in]	oerr-	schd_error to move FROM
 *
 * @return	nothing
 */
void move_schd_error(schd_error *err, schd_error *oerr)
{
	if (oerr == NULL || err == NULL)
		return;

	/* we're about to overwrite these, free just incase so we don't leak*/
	free(err->arg1);
	free(err->arg2);
	free(err->arg3);
	free(err->specmsg);
	free_schd_error_list(err->next);

	memcpy(err, oerr, sizeof(schd_error));

	/* Now that err has taken over the memory for the points,
	 * NULL them on the original so we don't accidentally free them
	 */
	oerr->arg1 = NULL;
	oerr->arg2 = NULL;
	oerr->arg3 = NULL;
	oerr->specmsg = NULL;
	oerr->next = NULL;
}

/**
 * @brief
 *		deep copy oerr into err.  This will allocate memory
 *		for members of err, but not a new structure itself (like
 *		dup_schd_error() would.
 * @param[out] err
 * @param[in] oerr
 */
void
copy_schd_error(schd_error *err, schd_error *oerr)
{
	set_schd_error_codes(err, oerr->status_code, oerr->error_code);
	set_schd_error_arg(err, ARG1, oerr->arg1);
	set_schd_error_arg(err, ARG2, oerr->arg2);
	set_schd_error_arg(err, ARG3, oerr->arg3);
	set_schd_error_arg(err, SPECMSG, oerr->specmsg);
	err->rdef = oerr->rdef;
}

/**
 * @brief
 * 		safely set the schd_config arg buffers without worrying about leaking
 *
 * @param[in,out]	err	-	object to set
 * @param[in]	arg_field	-	arg buffer to set
 * @param[in]	arg	-	string to set arg to
 *
 * @return	nothing
 */
void set_schd_error_arg(schd_error *err, int arg_field, char *arg) {

	if(err == NULL || arg == NULL)
		return;

	switch(arg_field) {
		case ARG1:
			free(err->arg1);
			err->arg1 = string_dup(arg);
			break;
		case ARG2:
			free(err->arg2);
			err->arg2 = string_dup(arg);
			break;
		case ARG3:
			free(err->arg3);
			err->arg3 = string_dup(arg);
			break;
		case SPECMSG:
			free(err->specmsg);
			err->specmsg = string_dup(arg);
			break;
		default:
			schdlog(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, "Invalid schd_error arg message type");
	}

}

/**
 * @brief
 * 		set the status code and error code of a schd_error structure
 *
 *	@note
 *		this ensures both codes are set together
 *
 * @param[in,out]	err	-	error structure to set
 * @param[in]	status_code	-	status code
 * @param[in]	error_code	-	error code
 *
 * @return	nothing
 */
void set_schd_error_codes(schd_error *err, enum schd_err_status status_code, enum sched_error error_code)
{
	if(err == NULL)
		return;
	if(status_code < SCHD_UNKWN || status_code >= SCHD_STATUS_HIGH)
		return;
	if(error_code < PBSE_NONE || error_code > ERR_SPECIAL)
		return;

	err->status_code = status_code;
	err->error_code = error_code;
}

/**
 * @brief
 * 		destructor of schd_error: Free a single schd_error structure
 *
 * @param[in]	err	-	Error structure
 */
void
free_schd_error(schd_error *err)
{
	if(err == NULL)
		return;

	free(err->arg1);
	free(err->arg2);
	free(err->arg3);
	free(err->specmsg);

	err->next = NULL; /* just incase people try and access freed memory */

	free(err);
}

/**
 * @brief
 * 		list schd_error destructor: Free multiple schd_error's in a list
 *
 * @param[in]	 err_list	-	Error list.
 */
void
free_schd_error_list(schd_error *err_list) {
	schd_error *err, *tmp;

	err = err_list;
	while (err != NULL) {
		tmp = err->next;
		free_schd_error(err);
		err = tmp;
	}

}

/**
 * @brief
 * 		create a simple schd_error with no arguments
 *
 * @param[in]	error_code	-	error code for new schd_error
 * @param[in]	status_code -	status code for new schd_error
 *
 * @return	new schd_error
 */
schd_error *create_schd_error(int error_code, int status_code)
{
	schd_error *new;
	new = new_schd_error();
	if(new == NULL)
		return NULL;
	set_schd_error_codes(new, status_code, error_code);
	return new;
}

/**
 * @brief
 *		create a schd_error complete with arguments
 * @par
 *	schd_error fields: error_code, status_code, arg1, arg2, arg3 and specmsg.
 *
 * @param[in]	error_code	-	Error Code.
 * @param[in]	status_code	-	Status Code.
 * @param[in]	arg1	-	Argument 1
 * @param[in]	arg2	-	Argument 2
 * @param[in]	arg3	-	Argument 3
 * @param[in]	specmsg	-	string to set arg to
 *
 * @return	new schd_error
 */
schd_error *create_schd_error_complex(int error_code, int status_code, char *arg1, char *arg2, char *arg3, char *specmsg)
{
	schd_error *new;

	new = create_schd_error(error_code, status_code);
	if(new == NULL)
		return NULL;

	if(arg1 != NULL)
		set_schd_error_arg(new, ARG1, arg1);

	if(arg2 != NULL)
		set_schd_error_arg(new, ARG2, arg2);

	if(arg3 != NULL)
		set_schd_error_arg(new, ARG3, arg3);

	if(specmsg != NULL)
		set_schd_error_arg(new, SPECMSG, specmsg);

	return new;
}
/**
 * @brief
 * 		add a schd_error to a linked list of schd_errors.
 *		The way this works: head of the schd_error list is already created and
 *		passed into the caller (e.g., from main_sched_loop() -> is_ok_to_run()).  The caller will maintain
 *		a 'prev_err' pointer.  The address of the prev_err(i.e., &prev_err) is passed into this function.
 *		The first call, we add the head.  Each additional call, we set up the next pointers.
 *		If err-> next is not NULL, we assume we're adding a sublist of schd_error's to the main list.
 *
 *	@example
 *		main_sched_loop(): foo_err = new_schd_error()
 *		main_sched_loop(): is_ok_to_run(..., foo_err)
 *		is_ok_to_run(): schd_error *prev_err = NULL;
 *		is_ok_to_run() add_err(&prev_err, err);
 *		is_ok_to_run(): err = new_schd_err()
 *		is_ok_to_run() add_err(&prev_err, err)
 *		Note: main_sched_loop() did not pass the address of foo_err into is_ok_to_run()
 *		Note2: main_sched_loop() holds the head of the list, so we don't return the list
 *
 * @param[in]	prev_err	-	address of the pointer previous to the end of the list (i.e. (*prev_err)->next->next == NULL
 * @param[in]	err	-	schd_error to add to the list (may be a list of schd_error's)
 *
 * @return	nothing
 *
 * @note	nothing stops duplicate entries from being added
 */
void add_err(schd_error **prev_err, schd_error *err)
{
	schd_error *cur = NULL;

	if (err == NULL || prev_err == NULL)
		return;

	if(*prev_err == NULL)
		(*prev_err) = err;
	else
		(*prev_err)->next = err;


	if(err->next != NULL) {
		for (cur = err; cur->next != NULL; cur = cur->next)
			;
		(*prev_err) = cur;
	} else
		(*prev_err) = err;
}

/**
 * @brief
 * 		turn a resource/resource_req into a string for printing using a
 *		internal static buffer
 *
 * @param[in]	p	-	pointer to resource/req
 * @param[in] fld	-	the field of the resource to print
 *
 * @return	char *
 * @retval	the resource in string format (in internal static string)
 * @retval	"" on error
 *
 * @par	MT-Safe: No
 *
 * @note
 * 		This function can not be used more than once in a printf() type func
 *	 	The static string will be overwritten before printing and you will get
 *	 	the same value for all calls.  Use res_to_str_r().
 */
char *
res_to_str(void *p, enum resource_fields fld)
{
	static char *resbuf = NULL;
	static int resbuf_size = 1024;

	if (resbuf == NULL) {
		if ((resbuf = malloc(resbuf_size)) == NULL)
			return "";
	}
	return res_to_str_re(p, fld, &resbuf, &resbuf_size, NO_FLAGS);

}

/**
 * @brief
 * 		convert a number that is a resource into a string with a provided
 * 		non-expandable buffer.  This is useful for size types or scheduler constants
 *
 * @param[in]	amount	-	amount of resource
 * @param[in]	def	-	resource definition of amount
 * @param[in]	fld	-	the field of the resource to print - Should be RF_REQUEST or
 *              		RF_AVAIL
 * @param[in,out]	buf	-	buffer for res to str conversion -- not expandable
 * @param[in]	bufsize	-	size of buf
 *
 * @return	char *
 * @retval	the resource in string format (in provided buffer)
 * @retval	""	: on error
 */
char *
res_to_str_c(sch_resource_t amount, resdef *def, enum resource_fields fld,
	char *buf, int bufsize)
{
	schd_resource res = {0};
	resource_req req = {0};
	char *unknown[] = {"unknown", NULL};

        if (buf == NULL)
          return "";

        buf[0] = '\0';

	if (def == NULL)
		return "";

	switch (fld) {
		case RF_REQUEST:
			req.amount = amount;
			req.def = def;
			req.name = def->name;
			req.type = def->type;
			req.res_str = "unknown";
			return res_to_str_re(((void*) &req), fld, &buf, &bufsize, NOEXPAND);
			break;
		case RF_AVAIL:
		default:
			res.avail = amount;
			res.assigned = amount;
			res.def = def;
			res.name = def->name;
			res.type = def->type;
			res.orig_str_avail = "unknown";
			res.str_avail = unknown;
			res.str_assigned = "unknown";
			return res_to_str_re(((void*) &res), fld, &buf, &bufsize, NOEXPAND);
	}
	return "";
}
/**
 * @brief
 * 		convert a resource to string with a non-expandable buffer
 *
 * @param[in]	p	-	pointer to resource/req
 * @param[in]	fld	-	the field of the resource to print
 * @param[in]	buf	-	buffer for res to str conversion -- not expandable
 * @param[in,out]	bufsize	-	size of buf
 *
 * @return	char *
 * @retval	the resource in string format (in provided buffer)
 * @retval	""	: on error
 */
char *
res_to_str_r(void *p, enum resource_fields fld, char *buf, int bufsize)
{
	return res_to_str_re(p, fld, &buf, &bufsize, NOEXPAND);
}

/**
 * @brief
 * 		turn a resource (resource/resource_req) into
 *      a string for printing.  If the buffer needs expanding, it
 *		will be expanded(except when specified by flags).
 *
 * @param[in]	p	-	a pointer to a resource/req
 * @param[in]	fld	-	The field of the resource type to print.  This is
 *						used to determine if p is a resource or a resource_req
 * @param[in,out]	buf	-	buffer to copy string into
 * @param[in,out]	buf_size	-	size of buffer
 * @param[in]	flags	-	flags to control printing
 *							PRINT_INT_CONST - print internal constant names
 *							NOEXPAND - don't expand the buffer, just fill upto the max size
 *
 * @return	char *
 * @retval	the resource in string format (in buf)
 * @retval	""  on error
 */
char *
res_to_str_re(void *p, enum resource_fields fld, char **buf,
	int *bufsize, unsigned int flags)
{
	schd_resource *res = NULL;
	resource_req *req = NULL;
	struct resource_type *rt;
	char *str;
	sch_resource_t amount;

	char localbuf[1024];
	char *ret;
	struct resource_type rtype = {0};

	if (buf == NULL || bufsize == NULL)
		return "";

	if (*bufsize > 0)
		**buf = '\0';

	if (p == NULL)
		return "";

	ret = *buf;

	if (*bufsize <= 0) {
		if (!(flags & NOEXPAND)) {
			if ((*buf = malloc(1024)) == NULL) {
				log_err(errno, __func__, MEM_ERR_MSG);
				return "";
			}
			else
				*bufsize = 1024;
		}
	}

	/* empty string */
	**buf = '\0';

	switch (fld) {
		case RF_REQUEST:
			req = (resource_req *) p;
			rt = &(req->type);
			str = req->res_str;
			amount = req->amount;
			break;

		case RF_DIRECT_AVAIL:
			res = (schd_resource *) p;
			if (res->indirect_res != NULL) {
				if (flags & NOEXPAND)
					snprintf(*buf, *bufsize, "@");
				else {
					ret = pbs_strcat(buf, bufsize, "@");
					if (ret == NULL)
						return "";
				}

				str = res->indirect_vnode_name;
				rtype.is_string = 1;
				rtype.is_non_consumable = 1;
				rt = &rtype;
				amount = 0;
				break;
			}
			/* if not indirect, fall through normally */
		case RF_AVAIL:
			res = (schd_resource *) p;
			if (res->indirect_res != NULL)
				res = res->indirect_res;
			rt = &(res->type);
			str = string_array_to_str(res->str_avail);
			amount = res->avail;
			break;

		case RF_ASSN:
			res = (schd_resource *) p;
			rt = &(res->type);
			str = res->str_assigned;
			amount = res->assigned;
			break;

		default:
			return "";
	}

	/* error checking */
	if (rt->is_string) {
		if (flags & NOEXPAND)
			snprintf(*buf, *bufsize, "%s", str);
		else
			ret = pbs_strcat(buf, bufsize, str);
	}
	else if (rt->is_boolean) {
		if (flags & NOEXPAND)
			snprintf(*buf, *bufsize, "%s", amount ? ATR_TRUE : ATR_FALSE);
		else
			ret = pbs_strcat(buf, bufsize, amount ? ATR_TRUE : ATR_FALSE);
	}
	else if (rt->is_size) {
		if (amount == 0) /* need to special case 0 or it falls into tb case */
			snprintf(localbuf, sizeof(localbuf), "0kb");
		else if (((long)amount % TERATOKILO) == 0)
#ifdef NAS /* localmod 005 */
			snprintf(localbuf, sizeof(localbuf), "%ldtb", (long)(amount/TERATOKILO));
		else if (((long)amount % GIGATOKILO) == 0)
			snprintf(localbuf, sizeof(localbuf), "%ldgb", (long)(amount/GIGATOKILO));
		else if (((long)amount % MEGATOKILO) == 0)
			snprintf(localbuf, sizeof(localbuf), "%ldmb", (long)(amount/MEGATOKILO));
#else
			snprintf(localbuf, sizeof(localbuf), "%ldtb", ((long) amount/TERATOKILO));
		else if (((long)amount % GIGATOKILO) == 0)
			snprintf(localbuf, sizeof(localbuf), "%ldgb", ((long) amount/GIGATOKILO));
		else if (((long)amount % MEGATOKILO) == 0)
			snprintf(localbuf, sizeof(localbuf), "%ldmb", ((long) amount/MEGATOKILO));
#endif /* localmod 005 */
		else
			snprintf(localbuf, sizeof(localbuf), "%ldkb", (long) amount);
		if (flags & NOEXPAND)
			snprintf(*buf, *bufsize, "%s", localbuf);
		else
			ret = pbs_strcat(buf, bufsize, localbuf);
	}
	else if (rt->is_num) {
		int const_print = 0;
		if (amount == UNSPECIFIED) {
			if (flags & PRINT_INT_CONST) {
				if (flags & NOEXPAND)
					snprintf(*buf, *bufsize, UNSPECIFIED_STR);
				else
					ret = pbs_strcat(buf, bufsize, UNSPECIFIED_STR);

				const_print = 1;
			}
		} else if (amount == SCHD_INFINITY) {
			if (flags & PRINT_INT_CONST) {
				if (flags & NOEXPAND)
					snprintf(*buf, *bufsize, SCHD_INFINITY_STR);
				else
					ret = pbs_strcat(buf, bufsize, SCHD_INFINITY_STR);

				const_print = 1;
			}
		}

		if (const_print == 0) {
			if (rt->is_float)
				snprintf(localbuf, sizeof(localbuf), "%.*f",
					float_digits(amount, FLOAT_NUM_DIGITS), (double) amount);
			else
				snprintf(localbuf, sizeof(localbuf), "%ld", (long) amount);
			if (flags & NOEXPAND)
				snprintf(*buf, *bufsize, "%s", localbuf);
			else
				ret = pbs_strcat(buf, bufsize, localbuf);
		}
	} else if (rt->is_time) {
		char resbuf[1024];
		convert_duration_to_str((long) amount, resbuf, sizeof(resbuf));
	}

	if (ret == NULL)
		return "";
	return *buf;
}

/**
 * @brief
 *	Helper function used to copy the given source string to the destination string. It also
 *	frees the destination and then allocates required memory before copying.
 *
 * @param[in] dest - Address of pointer to destination string
 * @param[in] dest - pointer to source string
 *
 * @retval
 * @return 0 - Failure
 * @return 1 - Success
 *
 * @par Side Effects:
 *	None
 *
 *
 */
int
copy_attr_value(char **dest, char *src)
{
	int ret = 0;

	if (*dest != NULL)
		free(*dest);

	if (src !=NULL) {
		int len = 0;
		len = strlen(src);
		*dest = (char*)malloc(len + 1);
		if (*dest == NULL) {
			schdlog(PBSEVENT_DEBUG, PBS_EVENTCLASS_SCHED, LOG_INFO, __func__, MEM_ERR_MSG);
			return ret;
		}
		strncpy(*dest, src, len);
		(*dest)[len] = '\0';
		ret = 1;
	}
	return ret;
}


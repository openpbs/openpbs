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
 * @file    range.c
 *
 * @brief
 * 		range.c -  contains functions which are related to range structure.
 *
 * Functions included are:
 * 	new_range()
 * 	free_range_list()
 * 	free_range()
 * 	dup_range_list()
 * 	dup_range()
 * 	range_parse()
 * 	range_next_value()
 * 	range_contains()
 * 	range_contains_single()
 * 	range_remove_value()
 * 	range_add_value()
 * 	range_intersection()
 * 	parse_subjob_index()
 * 	range_to_str()
 *
 */
#include <pbs_config.h>
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <errno.h>
#include <string.h>
#include <log.h>
#include <libutil.h>
#include "range.h"
#include "data_types.h"
#include "constant.h"
#include "misc.h"

/**
 * @brief
 *		new_range - allocate and initialize a range structure
 *
 * @return	newly allocated range
 * @retval	NULL	: on error
 *
 */
range *
new_range()
{
	range *r;

	if ((r = malloc(sizeof(range))) == NULL) {
		log_err(errno, "new_range", MEM_ERR_MSG);
		return NULL;
	}

	r->start = 0;
	r->end = 0;
	r->count = 0;
	r->step = 1;
	r->next = NULL;

	return r;
}

/**
 * @brief
 *		free_range_list - free a list of ranges
 *
 * @param[in,out]	r	-	range list to be freed.
 *
 * @return	nothing
 *
 */
void
free_range_list(range *r)
{
	range *cur_r;
	range *next_r;

	cur_r = r;

	while (cur_r != NULL) {
		next_r = cur_r->next;
		free_range(cur_r);

		cur_r = next_r;
	}
}

/**
 * @brief
 *		free_range - free a range structure
 *
 * @param[in,out]	r	-	range structure to be freed.
 *
 * @return	nothing
 *
 */
void
free_range(range *r)
{
	if (r == NULL)
		return;

	free(r);
}

/**
 * @brief
 *		dup_range_list - duplicate a range list
 *
 * @param[in]	old_r	-	range to dup;
 *
 * @return	newly duplicated range list
 *
 */
range *
dup_range_list(range *old_r)
{
	range *new_r;
	range *new_r_head = NULL;
	range *cur_old_r;
	range *prev_new_r = NULL;

	if (old_r == NULL)
		return NULL;

	cur_old_r = old_r;

	while (cur_old_r != NULL) {
		new_r = dup_range(cur_old_r);

		if (prev_new_r != NULL)
			prev_new_r->next = new_r;
		else
			new_r_head = new_r;

		cur_old_r = cur_old_r->next;
		prev_new_r = new_r;
	}

	return new_r_head;
}

/**
 * @brief
 *		dup_range - duplicate a range structure
 *
 * @param[in]	old_r	-	range structure to duplicate
 *
 * @return	new range structure
 * @retval	NULL	: on error
 *
 */
range *
dup_range(range *old_r)
{
	range *new_r;

	new_r = new_range();

	if (new_r == NULL)
		return NULL;

	new_r->start = old_r->start;
	new_r->end = old_r->end;
	new_r->step = old_r->step;
	new_r->count = old_r->count;

	return new_r;
}


/**
 * @brief
 *		range_parse - parse string of ranges delimited by comma
 *
 * @param[in]	str	-	string of ranges to parse
 *
 * @return	list of ranges
 * @retval	NULL	: on error
 *
 */
range *
range_parse(char *str)
{
	range *head = NULL;
	range *cur = NULL;
	range *r;
	char *p, *endp;
	int x, y, z, count;
	int ret;

	if (str == NULL)
		return NULL;

	p = str;


	do {
		ret = parse_subjob_index(p,  &endp, &x, &y, &z, &count);
		if (!ret) {
			r = new_range();

			if (r == NULL) {
				free_range_list(head);
				return NULL;
			}

			r->start = x;
			r->end = y;
			r->step = z;
			r->count = count;

			/* ensure the end value is contained in the range */
			while (range_contains(r, y) == 0 && y > x)
				y--;

			if (range_contains(r, y))
				r->end = y;
			else   { /* range is majorly hosed */
				free_range_list(head);
				free_range(r);
				return NULL;
			}

			if (head == NULL)
				head = cur = r;
			else {
				cur->next = r;
				cur = r;
			}

			p = endp;
		}
	} while (!ret && *endp == ',');

	if (ret) {
		free_range_list(head);
		return NULL;
	}

	return head;
}

/**
 * @brief
 *		range_next_value - get the next value in a range
 *			   if a current value is given, return the next
 *			   if no current value is given, return the first
 *
 * @param[in]	r	-	the range to return the value from
 * @param[in]	cur_value	-	the current value or if negitive, no value
 *
 * @return	the next value in the range
 * @retval	-1	: on error
 * @retval	-2	: if there is no next value
 *
 */
int
range_next_value(range *r, int cur_value)
{
	range *cur;
	int ret_val = -2;

	if (r == NULL)
		return -1;

	if (cur_value < 0)
		return r->start;

	if (range_contains(r, cur_value) == 0)
		return -1;

	cur = r;
	while (cur != NULL && ret_val < 0) {
		if (range_contains_single(cur, cur_value)) {
			if (cur_value == cur->end) {
				if (cur->next != NULL)
					ret_val = cur->next->start;
			}
			else
				ret_val = cur_value + cur->step;
		}
		cur = cur->next;
	}

	return ret_val;
}
/**
 * @brief
 *		range_contains - find if a range contains a value
 *
 * @param[in]	r	-	range to search
 * @param[in]	val	-	val to find
 *
 * @return	int
 * @retval	1	: if the range contains the value
 * @retval	0	: if the range does not contain the value
 *
 */
int
range_contains(range *r, int val)
{
	range *cur;
	int found = 0;

	cur = r;

	while (cur != NULL && !found) {
		if (range_contains_single(cur, val))
			found = 1;

		cur = cur->next;
	}

	if (found)
		return 1;

	return 0;
}

/**
 * @brief
 *		range_contains_single - is a value contained in a single range
 *				  structure
 *
 * @param[in]	r	-	the range structure
 * @param[in]	val	-	the value
 *
 * @return	int
 * @retval	1	: if the value is in the single range structure
 * @retval	0	: if not
 *
 */
int
range_contains_single(range *r, int val)
{
	if (r == NULL)
		return 0;

	if (val >= r->start && val <= r->end)
		if ((val - r->start) % r->step ==0)
			return 1;

	return 0;
}

/**
 * @brief
 *		range_remove_value - remove a value from a range list
 *
 * @param[in,out]	r	-	pointer to pointer to the head of the range
 * @param[in]	val	-	value to remove
 *
 * @return	int
 * @retval	1	: on success
 * @retval	0	: if not done (see note)
 *
 * @par	NOTE: value of r might be changed if the last value of first range
 *		  is removed. only supports removing values from either the start or end
 *	      of a range, not in the middle
 *
 */
int
range_remove_value(range **r, int val)
{
	range *cur;
	range *prev = NULL;
	int done = 0;

	if (r == NULL || *r == NULL)
		return 0;

	if (!range_contains(*r, val))
		return 0;

	cur = *r;
	while (cur != NULL && !done) {
		if (cur->start == val) {
			cur->start += cur->step;
			cur->count--;
			done = 1;
		}
		else if (cur->end == val) {
			cur->end -= cur->step;
			cur->count--;
			done = 1;
		}

		if (!done) {
			prev = cur;
			cur = cur->next;
		}
	}

	if (done) {
		/* we removed the last value from this section of the range */
		if (cur->start > cur->end) {
			if (prev == NULL) { /* we're removing the first range struct in the list */
				*r = (*r)->next;
				free_range(cur);
			}
			else {
				prev->next = cur->next;
				free_range(cur);
			}
		}
		return 1;
	}

	/* we didn't remove it */
	return 0;
}

/**
 * @brief
 *		range_add_value - add a value to a range list by adding it to the end
 *			  of the list
 *
 * @param[in]	r	-	range to add value too
 * @param[in]	val	-	value to add
 * @param[in]	type	-	enable/disable subrange stepping
 *
 * @return	int
 * @retval	1	: if successfully added value
 * @retval	0	: if val is in range, or val not successfully added
 *
 */
int
range_add_value(range *r, int val, enum range_step_type type)
{
	range *cur;			/* current range structure in list */
	range *prev = NULL;		/* previous range structure in list */
	range *new;			/* if we need to add to the list */
	int done = 0;			/* have we added val to our range, leave loop */

	if (r == NULL)
		return 0;

	if (range_contains(r, val))
		return 0;

	cur = r;

	while (cur != NULL && !done) {
		if (cur->count == 0) {
			cur->start = cur->end = val;
			cur->count++;
			done = 1;
		}
		else if (val == cur->start - cur->step) {
			cur->start = val;
			cur->count++;
			done = 1;
		}
		else if (val == cur->end + cur->step) {
			cur->end = val;
			cur->count++;
			done = 1;
		}

		prev = cur;
		cur = cur->next;
	}

	/* if we made it out of the loop and done is not set, we need to add
	 * the create a new sub-range and add it to the list
	 */
	if (!done) {
		/* if we have a subrange with a count of 1, add our value to it
		 * and up the step to compensate
		 */
		if (prev->count == 1 && type == ENABLE_SUBRANGE_STEPPING) {
			if (prev->start < val)
				prev->end = val;
			else
				prev->start = val;

			prev->step = prev->end - prev->start;
			prev->count++;
		}
		else {
			new = new_range();

			if (new == NULL)
				return 0;

			new->start = new->end = val;
			new->count = 1;

			prev->next = new;
		}
	}

	return 1;
}

/**
 * @brief
 *		range_intersection - create an intersection between two ranges
 *
 * @param[in]	r1	-	range 1
 * @param[in]	r2	-	range 2
 *
 * @return	a new range which is the intersection of r1 and r2
 * @retval	NULL	: on error or intersection is the null set
 *
 */
range *
range_intersection(range *r1, range *r2)
{
	range *intersection = NULL;
	int cur = 0;

	if (r1 == NULL || r2 == NULL)
		return NULL;

	cur = range_next_value(r1, -1);

	while (cur >= 0) {
		if (range_contains(r2, cur)) {
			if (intersection == NULL) {
				intersection = new_range();
				intersection->start = cur;
				intersection->end = cur;
				intersection->step = 1;
				intersection->count = 1;
			}
			else
				range_add_value(intersection, cur, ENABLE_SUBRANGE_STEPPING);
		}
		cur = range_next_value(r1, cur);
	}
	return intersection;
}


/**
 * @brief
 * 		parse_subjob_index - parse a subjob index range of the form:
 *			X[-Y[:Z]][,...]
 *		Each call parses up to the first comma or the end of str if no comma
 * @par
 *		Additional returns which are valid only if zero is returned are:
 *
 * @param[in]	pc	-	subjob index.
 * @param[out]	ep	-	ptr to character that terminated scan (comma or new-line
 * @param[out]	px	-	first number of range
 * @param[out]	py	-	maximum value in range
 * @param[out]	pz	-	stepping factor
 * @param[out]	pct -	number of entries in this section of the range
 *
 * @return	0/1
 * @retval	0	: returned as the function value if no error was detected.
 * @retval	1	: returned if there is a parse/format error
 */
int
parse_subjob_index(char *pc, char **ep, int *px, int *py, int *pz, int *pct)
{
	int   x, y, z;
	char *eptr;

	if (pc == NULL) {
		return (1);
	}

	if (*pc == ',' || isspace((int)*pc)) {
		pc++;
	}

	if (!isdigit((int)*pc)) {
		/* Invalid format, 1st char not digit */
		return (1);
	}
	x = (int)strtol(pc, &eptr, 10);
	pc = eptr;
	if ((*pc == ',') || (*pc == '\0')) {
		/* "X," or "X" case */
		y = x;
		z = 1;
	} else {
		/* should be X-Y[:Z] case */
		if (*pc != '-') {
			/* Invalid format, not in X-Y format */
			return (1);
		}
		y = (int)strtol(++pc, &eptr, 10);
		pc = eptr;
		if ((*pc == '\0') || (*pc == ',')) {
			z = 1;
		} else if (*pc != ':') {
			/* Invalid format, not in X-Y:Z format */
			return (1);
		} else {
			z = (int)strtol(++pc, &eptr, 10);
			pc = eptr;
			/* we're finished with X-Y:Z, only valid char is ',' or '\0' */
			if (*eptr != ',' && *eptr != '\0') {
				return (1);
			}
		}
	}

	if ((x > y) || (z < 1))
		return 1;

	*ep = pc;
	/* now compute the number of extires ((y+1)-x+(z-1))/z = (y-x+z)/z */
	*pct = (y - x + z)/z;
	*px  = x;
	*py  = y;
	*pz  = z;
	return 0;
}

/**
 * @brief
 * 		Returns a string representation of a range structure.
 *
 * @param[in]	r	-	The range for which a string representation is expected

 * @par MT-safe:	no
 *
 * @return	a string representation of the range
 * @retval	""	: on any malloc error
 *
 */
char *
range_to_str(range *r)
{
	static char *range_str = NULL;
	static int size = 0;
	range *cur_r = NULL;
	char numbuf[128];
	int len;

	if (r == NULL)
		return "";

	if (range_str == NULL) {
		if ((range_str = malloc(INIT_ARR_SIZE+1)) == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			return "";
		}
		size = INIT_ARR_SIZE;
	}
	range_str[0] = '\0';

	for (cur_r = r; cur_r != NULL; cur_r = cur_r->next) {
		if (cur_r->count > 1)
			sprintf(numbuf, "%d-%d", cur_r->start, cur_r->end);
		else
			sprintf(numbuf, "%d", cur_r->start);

		if (cur_r->step > 1) {
			if (pbs_strcat(&range_str, &size, numbuf) == NULL)
				return "";
			sprintf(numbuf, ":%d", cur_r->step);
			if (pbs_strcat(&range_str, &size, numbuf) == NULL)
				return "";
		}
		else
			if (pbs_strcat(&range_str, &size, numbuf) == NULL)
				return "";

		if (pbs_strcat(&range_str, &size, ",") == NULL)
			return "";
	}
	len = strlen(range_str);
	if (range_str[len-1] == ',')
		range_str[len-1] = '\0';

	return range_str;
}

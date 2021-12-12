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

#include <pbs_config.h>
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <errno.h>
#include <string.h>
#include <log.h>
#include <libutil.h>
#include "range.h"

/**
 * @brief
 *		new_range - allocate and initialize a range structure
 *
 * @return	newly allocated range
 * @retval	NULL	: on error
 *
 */
range *
new_range(int start, int end, int step, int count, range *next)
{
	range *r;

	if ((r = malloc(sizeof(range))) == NULL) {
		log_err(errno, __func__, RANGE_MEM_ERR_MSG);
		return NULL;
	}

	r->start = start;
	r->end = end;
	r->step = step;
	r->count = count;
	r->next = next;

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
		if (new_r == NULL) {
			free_range_list(new_r_head);
			return NULL;
		}

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

	new_r = new_range(old_r->start, old_r->end, old_r->step, old_r->count, NULL);

	if (new_r == NULL)
		return NULL;

	return new_r;
}

/**
 * @brief
 *	range_count - count number of elements in a given range structure
 *
 * @param[in]	r - range structure to count
 *
 * @return int
 * @retval # - number of elements in range
 *
 */
int
range_count(range *r)
{
	int count = 0;
	range *cur = r;

	while (cur != NULL) {
		count += cur->count;
		cur = cur->next;
	}
	return count;
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
	char *p;
	char *endp;
	int ret;

	if (str == NULL)
		return NULL;

	p = str;

	do {
		int start;
		int end;
		int step;
		int count;

		ret = parse_subjob_index(p, &endp, &start, &end, &step, &count);
		if (!ret) {
			r = new_range(start, end, step, count, NULL);

			if (r == NULL) {
				free_range_list(head);
				return NULL;
			}

			/* ensure the end value is contained in the range */
			while (range_contains(r, end) == 0 && end > start)
				end--;

			if (range_contains(r, end))
				r->end = end;
			else { /* range is majorly hosed */
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
	} while (!ret);

	if (ret == -1) {
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
			} else
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
		if ((val - r->start) % r->step == 0)
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

	if (r == NULL || *r == NULL || val < 0)
		return 0;

	if (!range_contains(*r, val))
		return 0;

	cur = *r;
	while (cur != NULL && !done) {
		if (cur->start == val && cur->end == val) {
			if (prev == NULL) /* we're removing the first range struct in the list */
				*r = (*r)->next;
			else
				prev->next = cur->next;
			free_range(cur);
			return 1;
		} else if (cur->start == val) {
			cur->start += cur->step;
			cur->count--;
			done = 1;
		} else if (cur->end == val) {
			cur->end -= cur->step;
			cur->count--;
			done = 1;
		} else if ((val > cur->start) && (val < cur->end)) {
			range *next_range = NULL;
			if ((next_range = new_range(0, 0, 1, 0, NULL)) == NULL)
				return 0;

			next_range->count = (cur->end - val) / cur->step;
			next_range->step = cur->step;
			next_range->start = val + cur->step;
			next_range->end = cur->end;
			next_range->next = cur->next;

			cur->count = (val - cur->start) / cur->step;
			cur->end = val - cur->step;
			cur->next = next_range;
			return 1;
		}

		if (!done) {
			prev = cur;
			cur = cur->next;
		}
	}

	if (done) {
		/* we removed the last value from this section of the range */
		if (cur->start > cur->end) {
			if (prev == NULL) /* we're removing the first range struct in the list */
				*r = (*r)->next;
			else
				prev->next = cur->next;
			free_range(cur);
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
 * @param[in,out]	r	-	pointer to pointer to the head of the range
 * @param[in]	val	-	value to add
 * @param[in]	type	-	enable/disable subrange stepping
 *
 * @return	int
 * @retval	1	: if successfully added value
 * @retval	0	: if val is in range, or val not successfully added
 *
 */
int
range_add_value(range **r, int val, int range_step)
{
	range *cur; /* current range structure in list */
	range *next_range;

	if (r == NULL)
		return 0;

	if (*r == NULL) {
		/* If there are no range structs in the list; create the new range for first value */
		range *first_range = NULL;
		if ((first_range = new_range(val, val, range_step, 1, NULL)) == NULL) {
			return 0;
		}
		*r = first_range;
		return 1;
	}

	cur = *r;
	/* Value falls before the first sub-range */
	if (cur != NULL && val < cur->start) {
		if (val == cur->start - cur->step) {
			cur->start -= cur->step;
			cur->count++;
			return 1;
		} else {
			/* Add new range as the first element with same value */
			range *first_range = NULL;
			if ((first_range = new_range(val, val, cur->step, 1, cur)) == NULL) {
				return 0;
			}
			*r = first_range;
			return 1;
		}
	}

	/* The value that needs to be added is in between the cur and the next sub-ranges  */

	while (cur != NULL && cur->next != NULL) {

		next_range = cur->next;
		if ((val > cur->end) && (val < next_range->start)) {

			if ((val == cur->end + cur->step) && (val == next_range->start - next_range->step)) {
				/* Adding this value would coalesce these two sub-ranges  */
				cur->end = next_range->end;
				cur->next = next_range->next;
				cur->count += next_range->count + 1;
				free_range(next_range);
				return 1;

			} else if (val == cur->end + cur->step) {
				/* Value falls in the cur sub-range end  */
				cur->end += cur->step;
				cur->count++;
				return 1;

			} else if (val == next_range->start - next_range->step) {
				/* Value falls in the next sub-range start  */
				next_range->start -= next_range->step;
				next_range->count++;
				return 1;

			} else {
				/* Value falls in this range; add new mid-range with same value */
				range *mid_range = NULL;
				if ((mid_range = new_range(val, val, cur->step, 1, cur->next)) == NULL) {
					return 0;
				}
				cur->next = mid_range;
				return 1;
			}
		}
		cur = next_range;
	}

	/* Coming out of the loop and check the extreme right corner case */

	if (cur != NULL && val > cur->end) {
		if (val == cur->end + cur->step) {
			cur->end += cur->step;
			cur->count++;
			return 1;
		} else {
			/* Add new range at the end with same value */
			range *end_range = NULL;
			if ((end_range = new_range(val, val, cur->step, 1, NULL)) == NULL) {
				return 0;
			}
			cur->next = end_range;
			return 1;
		}
	}

	return 0;
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
			range_add_value(&intersection, cur, r2->step);
		}
		cur = range_next_value(r1, cur);
	}
	return intersection;
}

/**
 * @brief
 *		parse_subjob_index - parse a subjob index range of the form:
 *		START[-END[:STEP]][,...]
 *		Each call parses up to the first comma or if no comma the end of
 *		the string or a ']'
 * @param[in]	pc	-	range of sub jobs
 * @param[out]	ep	-	ptr to character that terminated scan (comma or new-line)
 * @param[out]	pstart	-	first number of range
 * @param[out]	pend	-	maximum value in range
 * @param[out]	pstep	-	stepping factor
 * @param[out]	pcount -	number of entries in this section of the range
 *
 * @return	integer
 * @retval	0	- success
 * @retval	1	- no (more) indices are found
 * @retval	-1	- parse/format error
 */
int
parse_subjob_index(char *pc, char **ep, int *pstart, int *pend, int *pstep, int *pcount)
{
	int start;
	int end;
	int step;
	char *eptr;

	if (pc == NULL)
		return (-1);

	while (isspace((int) *pc) || (*pc == ','))
		pc++;
	if ((*pc == '\0') || (*pc == ']')) {
		*pcount = 0;
		*ep = pc;
		return (1);
	}

	if (!isdigit((int) *pc)) {
		/* Invalid format, 1st char not digit */
		return (-1);
	}
	start = (int) strtol(pc, &eptr, 10);
	pc = eptr;
	while (isspace((int) *pc))
		pc++;
	if ((*pc == ',') || (*pc == '\0') || (*pc == ']')) {
		/* "X," or "X" case */
		end = start;
		step = 1;
		if (*pc == ',')
			pc++;
	} else {
		/* should be X-Y[:Z] case */
		if (*pc != '-') {
			/* Invalid format, not in X-Y format */
			*pcount = 0;
			return (-1);
		}
		end = (int) strtol(++pc, &eptr, 10);
		pc = eptr;
		if (isspace((int) *pc))
			pc++;
		if ((*pc == '\0') || (*pc == ',') || (*pc == ']')) {
			step = 1;
		} else if (*pc++ != ':') {
			/* Invalid format, not in X-Y:z format */
			*pcount = 0;
			return (-1);
		} else {
			while (isspace((int) *pc))
				pc++;
			step = (int) strtol(pc, &eptr, 10);
			pc = eptr;
			while (isspace((int) *pc))
				pc++;
			if (*pc == ',')
				pc++;
		}

		/* y must be greater than x for a range and z must be greater 0 */
		if ((start >= end) || (step < 1))
			return (-1);
	}

	*ep = pc;
	/* now compute the number of extires ((end + 1) - start + (step - 1)) / step = (end - start + step) / step */
	*pcount = (end - start + step) / step;
	*pstart = start;
	*pend = end;
	*pstep = step;
	return (0);
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
		if ((range_str = malloc(INIT_RANGE_ARR_SIZE + 1)) == NULL) {
			log_err(errno, __func__, RANGE_MEM_ERR_MSG);
			return "";
		}
		size = INIT_RANGE_ARR_SIZE;
	}
	range_str[0] = '\0';

	for (cur_r = r; cur_r != NULL; cur_r = cur_r->next) {
		if (cur_r->count > 1)
			sprintf(numbuf, "%d-%d", cur_r->start, cur_r->end);
		else
			sprintf(numbuf, "%d", cur_r->start);

		if (cur_r->step > 1 && cur_r->count > 1) {
			if (pbs_strcat(&range_str, &size, numbuf) == NULL)
				return "";
			sprintf(numbuf, ":%d", cur_r->step);
			if (pbs_strcat(&range_str, &size, numbuf) == NULL)
				return "";
		} else if (pbs_strcat(&range_str, &size, numbuf) == NULL)
			return "";

		if (pbs_strcat(&range_str, &size, ",") == NULL)
			return "";
	}
	len = strlen(range_str);
	if (range_str[len - 1] == ',')
		range_str[len - 1] = '\0';

	return range_str;
}

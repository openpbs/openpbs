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


#ifndef _RANGE_H
#define _RANGE_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Control whether to consider stepping or not
 */
enum range_step_type {
	DISABLE_SUBRANGE_STEPPING,
	ENABLE_SUBRANGE_STEPPING
};

typedef struct range
{
	int start;
	int end;
	int step;
	int count;
	struct range *next;
} range;

/* Error message when we fail to allocate memory */
#define RANGE_MEM_ERR_MSG "Unable to allocate memory (malloc error)"

#define INIT_RANGE_ARR_SIZE 2048

/*
 *	new_range - allocate and initialize a range structure
 */

range *new_range(int start, int end, int step, int count, range *next);

/*
 *	free_range_list - free a list of ranges
 */
void free_range_list(range *r);

/*
 *	free_range - free a range structure
 */
void free_range(range *r);

/*
 *	dup_range_list - duplicate a range list
 */
range *dup_range_list(range *old_r);

/*
 *	dup_range - duplicate a range structure
 */
range *dup_range(range *old_r);

/*
 *	range_parse - parse string of ranges delimited by comma
 */
range *range_parse(char *str);

/*
 *
 *	range_next_value - get the next value in a range
 *			   if a current value is given, return the next
 *			   if no current value is given, return the first
 *
 */
int range_next_value(range *r, int cur_value);

/*
 *	range_contains - find if a range contains a value
 */
int range_contains(range *r, int val);

/*
 *	range_contains_single - is a value contained in a single range
 *				  structure
 */
int range_contains_single(range *r, int val);

/*
 *	range_remove_value - remove a value from a range list
 *
 */
int range_remove_value(range **r, int val);

/*
 *	range_add_value - add a value to a range list 
 *
 */
int range_add_value(range **r, int val, int range_step);

/*
 *	range_intersection - create an intersection between two ranges
 */
range *range_intersection(range *r1, range *r2);

extern int parse_subjob_index(char *, char **, int *, int *, int *, int *);

/*
 * Return a string representation of a range structure
 */
char *range_to_str(range *r);

#ifdef __cplusplus
}
#endif

#endif /* _RANGE_H */

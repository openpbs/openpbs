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

#include <stdio.h>
#include <string.h>

#include "pbs_ifl.h"

/**
 * @file	batch_status.c
 *
 * @brief
 *	batch_status.c - batch_status structures utilities
 */

/**
 * @brief
 *	bs_isort - insertion sort for batch_status structures
 *
 * @param[in] bs - batch_status linked list
 * @param[in] cmp_func - compare function to compare two batch_status
 *
 *
 * @return 	structure handle
 * @retval	head of sorted batch status list
 *
 */
struct batch_status *
bs_isort(struct batch_status *bs,
	 int (*cmp_func)(struct batch_status *, struct batch_status *))
{
	struct batch_status *new_head = NULL; /* new list head */
	struct batch_status *cur_old;	      /*where we are in the old list*/
	struct batch_status *cur_new;	      /* where we are in the new list */
	struct batch_status *prev_new = NULL;
	struct batch_status *tmp; /* tmp ptr to hold next */

	cur_old = bs;
	new_head = NULL;

	while (cur_old != NULL) {
		tmp = cur_old->next;

		if (new_head == NULL) {
			cur_old->next = NULL;
			new_head = cur_old;
		} else {
			/* find where our node goes in the new list */
			for (cur_new = new_head, prev_new = NULL;
			     cur_new != NULL && cmp_func(cur_new, cur_old) <= 0;
			     prev_new = cur_new, cur_new = cur_new->next)
				;
			if (prev_new == NULL) {
				cur_old->next = new_head;
				new_head = cur_old;
			} else {
				cur_old->next = cur_new;
				prev_new->next = cur_old;
			}
		}
		cur_old = tmp;
	}
	return new_head;
}

/**
 * @brief
 *	bs_find - find a batch_status with given name in a batch_status structures list.
 *
 * @param[in] bs - batch_status linked list
 * @param[in] name - name of the batch_status structure to be searched
 *
 *
 * @return 	batch_status structure handle
 * @retval	batch_status structure pointer with given name or NULL
 *
 */
struct batch_status *
bs_find(struct batch_status *bs, const char *name)
{

	if (name == NULL)
		return NULL;

	for (; ((bs != NULL) && strcmp(name, bs->name)); bs = bs->next)
		; /* empty for loop */

	return bs;
}

/**
 * @brief
 *	init_bstat - Initialize batch status
 *
 * @param[in] bstat - batch_status struct
 *
 * @return 	void
 */
void
init_bstat(struct batch_status *bstat)
{
	bstat->next = NULL;
	bstat->text = NULL;
	bstat->attribs = NULL;
}

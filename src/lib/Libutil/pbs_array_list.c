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
#include <string.h>
#include "pbs_array_list.h"

/**
 * @brief
 *	return the reallocated chunk of memory to hold range of ip addresses,
 *
 * @return	pntPBS_IP_RANGE
 * @retval	reallocated memory
 *
 */
pntPBS_IP_RANGE
create_pbs_range(void)
{
	return ((pntPBS_IP_RANGE)calloc(CHUNK, sizeof(PBS_IP_RANGE)));
}

/**
 * @brief
 *	resize the present ip list
 *
 * @param[in] list - list of ip address
 *
 * @return	pntPBS_IP_LIST
 * @retval	new list	success
 * @retval	NULL		error
 */
pntPBS_IP_LIST
resize_pbs_iplist(pntPBS_IP_LIST list)
{
	pntPBS_IP_RANGE temp;
	temp = (pntPBS_IP_RANGE)realloc(list->li_range, ((CHUNK + list->li_totalsize)* sizeof(PBS_IP_RANGE)));
	if (temp != NULL) {
		list->li_range = temp;
		memset(((char *)list->li_range + (list->li_totalsize * sizeof(PBS_IP_RANGE))), 0, CHUNK * sizeof(PBS_IP_RANGE));
		list->li_totalsize += CHUNK;
		return list;
	}
	else {
		delete_pbs_iplist(list);
		return NULL;
	}
}

/**
 * @brief
 *	creates ip address list.
 *
 * @return	pntPBS_IP_LIST
 * @retval	reference to created ip addr list	success
 * @retval	NULL					error
 *
 */
pntPBS_IP_LIST
create_pbs_iplist(void)
{
	pntPBS_IP_LIST list= (pntPBS_IP_LIST)calloc(1, sizeof(PBS_IP_LIST));
	if (list) {
		list->li_range = create_pbs_range();
		if (!list->li_range) {
			free(list);
			return NULL;
		}
		list->li_totalsize = CHUNK;
	}
	return list;
}

/**
 * @brief
 *      deletes ip address list.
 *
 * @param[in] pntPBS_IP_LIST pointer to list
 *
 */
void
delete_pbs_iplist(pntPBS_IP_LIST list)
{
	if (list) {
		if (list->li_range)
			free(list->li_range);
		free(list);
	}
	return;
}


/**
 * @brief
 *	searches the the key value in list.
 *
 * @param[in] list - list
 * @param[in] key - key value
 * @param[out] location - index where key found
 *
 * @return	int
 * @retval	location	if found
 * @retval	-1		if not found
 *
 */
int
search_location(pntPBS_IP_LIST list, T key, int *location)
{
	int bottom, middle, top;
	bottom = 0;
	top = list->li_nrowsused - 1;
	while (top >= bottom) {
		middle = (top + bottom) / 2;
		if (key == IPLIST_GET_LOW(list, middle)) {
			*location = middle;
			return middle;
		}
		else if (key < IPLIST_GET_LOW(list, middle))
			top = middle - 1;
		else
			bottom = middle + 1;
	}
	*location = top;
	if (top != -1 && key <= (IPLIST_GET_LOW(list, *location) + IPLIST_GET_HIGH(list, *location))) {
		return (*location);
	}
	return -1;
}

/**
 * @brief
 *      insert the the key value into list.
 *
 * @param[in] list - list
 * @param[in] key - key value
 *
 * @return      int
 * @retval      0	insertion of key successful
 * @retval      !0	insertion of key  failed
 *
 */

int
insert_iplist_element(pntPBS_IP_LIST list, T key)
{
	int location = -1;
	int first_row = 0;
	/* If list is empty, go ahed and input the ip at first location */
	if (IPLIST_GET_LOW(list, 0) == 0 && list->li_nrowsused == 0) {
		IPLIST_SET_LOW(list, 0, key);
		list->li_nrowsused++;
		return IPLIST_INSERT_SUCCESS;
	}

	if (list->li_nrowsused == list->li_totalsize) {
		list = resize_pbs_iplist(list);
		if (!list) {
			return IPLIST_INSERT_FAILURE;
		}
	}

	if (search_location(list, key, &location) >= 0)
		return IPLIST_INSERT_SUCCESS;
	if (location == -1) {
		first_row = 1;
		location++;
	}

	if (IPLIST_IS_CONTINUOUS_ROW(list, location, key)) {
		IPLIST_SET_HIGH(list, location, IPLIST_GET_HIGH(list, location) + 1);
		if (IPLIST_IS_CONTINUOUS_ROW(list, location, IPLIST_GET_LOW(list, location +1))) {
			IPLIST_SET_HIGH(list, location, IPLIST_GET_HIGH(list, location) + 1 + IPLIST_GET_HIGH(list, location + 1));
			/** memove rows up , decrement nrowsused, memset one row with INIT_VALUE **/
			list->li_nrowsused--;
			if (IPLIST_SHIFT_ALL_UP_BY_ONE(list, location +1, list->li_nrowsused - (location +1)) == NULL) {
				list->li_nrowsused++;
				return IPLIST_INSERT_FAILURE;
			}
			memset(list->li_range + list->li_nrowsused, 0 , sizeof(PBS_IP_RANGE));
		}
	} else {
		if (first_row)
			location--;
		if (IPLIST_IS_CONTINUOUS(key, IPLIST_GET_LOW(list, location +1))) {
			IPLIST_SET_LOW(list, location + 1, key);
			IPLIST_SET_HIGH(list, location + 1, IPLIST_GET_HIGH(list, location + 1) + 1);
		}
		else {
			if (IPLIST_GET_LOW(list, location +1) == INIT_VALUE) {
				IPLIST_SET_LOW(list, location+1, key);
				list->li_nrowsused++;
			} else {
				/** Add new Row **/
				if (IPLIST_SHIFT_ALL_DOWN_BY_ONE(list, location + 1, list->li_nrowsused - (location +1)) == NULL)
					return IPLIST_INSERT_FAILURE;
				IPLIST_SET_LOW(list, location + 1, key);
				IPLIST_SET_HIGH(list, location + 1, INIT_VALUE);
				list->li_nrowsused++;
			}
		}
	}
	return IPLIST_INSERT_SUCCESS;
}

/**
 * @brief
 *      delete the the key value into list.
 *
 * @param[in] list - list
 * @param[in] key - key value
 *
 * @return      int
 * @retval      0       deletion of key successful
 * @retval      !0      deletion of key  failed
 *
 */

int
delete_iplist_element(pntPBS_IP_LIST list, T key)
{
	int location = -1;
	T high = 0;

	if (list->li_nrowsused == list->li_totalsize) {
		list = resize_pbs_iplist(list);
		if (!list) {
			return IPLIST_INSERT_FAILURE;
		}
	}

	if (search_location(list, key, &location) == -1)
		return IPLIST_DELETE_FAILURE;
	if ((IPLIST_GET_LOW(list, location) == key) && list->li_nrowsused) { /** If the Lower IP of range **/
		if (IPLIST_GET_HIGH(list, location)==INIT_VALUE) {
			if (IPLIST_SHIFT_ALL_UP_BY_ONE(list, location, list->li_nrowsused - (location +1)) == NULL) {
				list->li_nrowsused++;
				return IPLIST_DELETE_FAILURE;
			}
			list->li_nrowsused--;
			memset(list->li_range + list->li_nrowsused , 0 , sizeof(PBS_IP_RANGE));
		}
		else {
			IPLIST_SET_LOW(list, location, IPLIST_GET_LOW(list, location)+1);
			IPLIST_SET_HIGH(list, location, IPLIST_GET_HIGH(list, location)-1);
		}
	} else if ((IPLIST_GET_LOW(list, location) + IPLIST_GET_HIGH(list, location)) == key) { /** Is the biggest IP of range **/
		IPLIST_SET_HIGH(list, location, IPLIST_GET_HIGH(list, location)-1);
	} else { /** Lies somewhere in between LOW & HIGH **/
		/* temp = IPLIST_GET_HIGH(list,location); */
		high = IPLIST_GET_LOW(list, location) + IPLIST_GET_HIGH(list, location);
		IPLIST_SET_HIGH(list, location, key-IPLIST_GET_LOW(list, location) -1);
		if (IPLIST_SHIFT_ALL_DOWN_BY_ONE(list, location + 1, list->li_nrowsused - (location +1)) == NULL)
			return IPLIST_DELETE_FAILURE;
		IPLIST_SET_LOW(list, location+1, key+1);
		IPLIST_SET_HIGH(list, location+1, high-IPLIST_GET_LOW(list, location+1));
		list->li_nrowsused++;
	}
	return IPLIST_DELETE_SUCCESS;
}

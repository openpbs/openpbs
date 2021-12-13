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

#include <pbs_config.h>

#include "attribute.h"
#include "job.h"
#include "reservation.h"
#include "resv_node.h"

/**
 * @brief	Get attribute of reservation based on given attr index
 *
 * @param[in] presv    - pointer to node struct
 * @param[in] attr_idx - attribute index
 *
 * @return attribute *
 * @retval NULL  - failure
 * @retval !NULL - pointer to attribute struct
 */
attribute *
get_rattr(const resc_resv *presv, int attr_idx)
{
	if (presv != NULL)
		return _get_attr_by_idx((attribute *) presv->ri_wattr, attr_idx);
	return NULL;
}

/**
 * @brief	Getter function for reservation attribute of type string
 *
 * @param[in]	presv - pointer to the reservation
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	char *
 * @retval	string value of the attribute
 * @retval	NULL if presv is NULL
 */
char *
get_rattr_str(const resc_resv *presv, int attr_idx)
{
	if (presv != NULL)
		return get_attr_str(get_rattr(presv, attr_idx));

	return NULL;
}

/**
 * @brief	Getter function for reservation attribute of type string of array
 *
 * @param[in]	presv - pointer to the reservation
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	struct array_strings *
 * @retval	value of the attribute
 * @retval	NULL if presv is NULL
 */
struct array_strings *
get_rattr_arst(const resc_resv *presv, int attr_idx)
{
	if (presv != NULL)
		return get_attr_arst(get_rattr(presv, attr_idx));

	return NULL;
}

/**
 * @brief	Getter for reservation attribute's list value
 *
 * @param[in]	presv - pointer to the reservation
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	pbs_list_head
 * @retval	value of attribute
 */
pbs_list_head
get_rattr_list(const resc_resv *presv, int attr_idx)
{
	return get_attr_list(get_rattr(presv, attr_idx));
}

/**
 * @brief	Getter function for reservation attribute of type long
 *
 * @param[in]	presv - pointer to the reservation
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	long
 * @retval	long value of the attribute
 * @retval	-1 if presv is NULL
 */
long
get_rattr_long(const resc_resv *presv, int attr_idx)
{
	if (presv != NULL)
		return get_attr_l(get_rattr(presv, attr_idx));

	return -1;
}

/**
 * @brief	Generic reservation attribute setter (call if you want at_set() action functions to be called)
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	rscn - new resource val to set, if applicable
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	!0 for failure
 */
int
set_rattr_generic(resc_resv *presv, int attr_idx, char *val, char *rscn, enum batch_op op)
{
	if (presv == NULL || val == NULL)
		return 1;

	return set_attr_generic(get_rattr(presv, attr_idx), &resv_attr_def[attr_idx], val, rscn, op);
}

/**
 * @brief	"fast" reservation attribute setter for string values
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	rscn - new resource val to set, if applicable
 *
 * @return	int
 * @retval	0 for success
 * @retval	!0 for failure
 */
int
set_rattr_str_slim(resc_resv *presv, int attr_idx, char *val, char *rscn)
{
	if (presv == NULL || val == NULL)
		return 1;

	return set_attr_generic(get_rattr(presv, attr_idx), &resv_attr_def[attr_idx], val, rscn, INTERNAL);
}

/**
 * @brief	"fast" reservation attribute setter for long values
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_rattr_l_slim(resc_resv *presv, int attr_idx, long val, enum batch_op op)
{
	if (presv == NULL)
		return 1;

	set_attr_l(get_rattr(presv, attr_idx), val, op);

	return 0;
}

/**
 * @brief	"fast" reservation attribute setter for boolean values
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_rattr_b_slim(resc_resv *presv, int attr_idx, long val, enum batch_op op)
{
	if (presv == NULL)
		return 1;

	set_attr_b(get_rattr(presv, attr_idx), val, op);

	return 0;
}

/**
 * @brief	"fast" reservation attribute setter for char values
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_rattr_c_slim(resc_resv *presv, int attr_idx, char val, enum batch_op op)
{
	if (presv == NULL)
		return 1;

	set_attr_c(get_rattr(presv, attr_idx), val, op);

	return 0;
}

/**
 * @brief	Check if a reservation attribute is set
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to check
 *
 * @return	int
 * @retval	1 if it is set
 * @retval	0 otherwise
 */
int
is_rattr_set(const resc_resv *presv, int attr_idx)
{
	if (presv != NULL)
		return is_attr_set(get_rattr(presv, attr_idx));

	return 0;
}

/**
 * @brief	Free a reservation attribute
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to free
 *
 * @return	void
 */
void
free_rattr(resc_resv *presv, int attr_idx)
{
	if (presv != NULL)
		free_attr(resv_attr_def, get_rattr(presv, attr_idx), attr_idx);
}

/**
 * @brief	clear a reservation attribute
 *
 * @param[in]	presv - pointer to reservation
 * @param[in]	attr_idx - attribute index to clear
 *
 * @return	void
 */
void
clear_rattr(resc_resv *presv, int attr_idx)
{
	clear_attr(get_rattr(presv, attr_idx), &resv_attr_def[attr_idx]);
}

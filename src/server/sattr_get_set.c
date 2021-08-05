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

#include "server.h"

/**
 * @brief	Get attribute of server based on given attr index
 *
 * @param[in] attr_idx - attribute index
 *
 * @return attribute *
 * @retval NULL  - failure
 * @retval !NULL - pointer to attribute struct
 */
attribute *
get_sattr(int attr_idx)
{
	return &(server.sv_attr[attr_idx]);
}

/**
 * @brief	Getter function for server attribute of type string
 *
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	char *
 * @retval	string value of the attribute
 * @retval	NULL if pjob is NULL
 */
char *
get_sattr_str(int attr_idx)
{
	return get_attr_str(get_sattr(attr_idx));
}

/**
 * @brief	Getter function for server attribute of type string of array
 *
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	struct array_strings *
 * @retval	value of the attribute
 * @retval	NULL if pjob is NULL
 */
struct array_strings *
get_sattr_arst(int attr_idx)
{
	return get_attr_arst(get_sattr(attr_idx));
}

/**
 * @brief	Getter for server attribute's list value
 *
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	pbs_list_head
 * @retval	value of attribute
 */
pbs_list_head
get_sattr_list(int attr_idx)
{
	return get_attr_list(get_sattr(attr_idx));
}

/**
 * @brief	Getter function for server attribute of type long
 *
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	long
 * @retval	long value of the attribute
 * @retval	-1 if pjob is NULL
 */
long
get_sattr_long(int attr_idx)
{
	return get_attr_l(get_sattr(attr_idx));
}

/**
 * @brief	Generic server attribute setter (call if you want at_set() action functions to be called)
 *
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
set_sattr_generic(int attr_idx, char *val, char *rscn, enum batch_op op)
{
	return set_attr_generic(get_sattr(attr_idx), &svr_attr_def[attr_idx], val, rscn, op);
}

/**
 * @brief	"fast" server attribute setter for string values
 *
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	rscn - new resource val to set, if applicable
 *
 * @return	int
 * @retval	0 for success
 * @retval	!0 for failure
 */
int
set_sattr_str_slim(int attr_idx, char *val, char *rscn)
{
	return set_attr_generic(get_sattr(attr_idx), &svr_attr_def[attr_idx], val, rscn, INTERNAL);
}

/**
 * @brief	"fast" server attribute setter for long values
 *
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_sattr_l_slim(int attr_idx, long val, enum batch_op op)
{
	set_attr_l(get_sattr(attr_idx), val, op);
	return 0;
}

/**
 * @brief	"fast" server attribute setter for boolean values
 *
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_sattr_b_slim(int attr_idx, long val, enum batch_op op)
{
	set_attr_b(get_sattr(attr_idx), val, op);
	return 0;
}

/**
 * @brief	"fast" server attribute setter for char values
 *
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_sattr_c_slim(int attr_idx, char val, enum batch_op op)
{
	set_attr_c(get_sattr(attr_idx), val, op);
	return 0;
}


/**
 * @brief	Check if a server attribute is set
 *
 * @param[in]	attr_idx - attribute index to check
 *
 * @return	int
 * @retval	1 if it is set
 * @retval	0 otherwise
 */
int
is_sattr_set(int attr_idx)
{
	return is_attr_set(get_sattr(attr_idx));
}

/**
 * @brief	Free a server attribute
 *
 * @param[in]	attr_idx - attribute index to free
 *
 * @return	void
 */
void
free_sattr(int attr_idx)
{
	free_attr(svr_attr_def, get_sattr(attr_idx), attr_idx);
}

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

#include "job.h"

/**
 * @brief	Get attribute of job based on given attr index
 *
 * @param[in] pjob     - pointer to job struct
 * @param[in] attr_idx - attribute index
 *
 * @return attribute *
 * @retval NULL  - failure
 * @retval !NULL - pointer to attribute struct
 */
attribute *
get_jattr(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return _get_attr_by_idx((attribute *) pjob->ji_wattr, attr_idx);
	return NULL;
}

/**
 * @brief	Check if the job is in the state specified
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	state - the state to check
 *
 * @return	int
 * @retval	1 if the job is in the state specified
 * @retval	0 otherwise
 */
int
check_job_state(const job *pjob, char state)
{
	if (pjob == NULL)
		return 0;

	if (get_job_state(pjob) == state)
		return 1;

	return 0;
}

/**
 * @brief	Check if the job is in the substate specified
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	substate - the substate to check
 *
 * @return	int
 * @retval	1 if the job is in the state specified
 * @retval	0 otherwise
 */
int
check_job_substate(const job *pjob, int substate)
{
	if (pjob == NULL)
		return 0;

	if (get_job_substate(pjob) == substate)
		return 1;

	return 0;
}

/**
 * @brief	Get the state character value of a job
 *
 * @param[in]	pjob - the job object
 *
 * @return char
 * @return state character
 * @return -1 for error
 */
char
get_job_state(const job *pjob)
{
	if (pjob != NULL) {
		return get_attr_c(get_jattr(pjob, JOB_ATR_state));
	}

	return JOB_STATE_LTR_UNKNOWN;
}

/**
 * @brief	Convenience function to get the numeric representation of job state value
 *
 * @param[in]	pjob - job object
 *
 * @return int
 * @retval numeric form of job state
 * @retvam -1 for error
 */
int
get_job_state_num(const job *pjob)
{
	char statec;
	int staten;

	if (pjob == NULL)
		return -1;

	statec = get_attr_c(get_jattr(pjob, JOB_ATR_state));
	if (statec == -1)
		return -1;

	staten = state_char2int(statec);

	return staten;
}

/**
 * @brief	Get the substate value of a job
 *
 * @param[in]	pjob - the job object
 *
 * @return long
 * @return substate value
 * @return -1 for error
 */
long
get_job_substate(const job *pjob)
{
	if (pjob != NULL) {
		return get_attr_l(get_jattr(pjob, JOB_ATR_substate));
	}

	return -1;
}

/**
 * @brief	Getter function for job attribute of type string
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	char *
 * @retval	string value of the attribute
 * @retval	NULL if pjob is NULL
 */
char *
get_jattr_str(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return get_attr_str(get_jattr(pjob, attr_idx));

	return NULL;
}

/**
 * @brief	Getter function for job attribute of type string of array
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	struct array_strings *
 * @retval	value of the attribute
 * @retval	NULL if pjob is NULL
 */
struct array_strings *
get_jattr_arst(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return get_attr_arst(get_jattr(pjob, attr_idx));

	return NULL;
}

/**
 * @brief	Getter for job attribute's list value
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	pbs_list_head
 * @retval	value of attribute
 */
pbs_list_head
get_jattr_list(const job *pjob, int attr_idx)
{
	return get_attr_list(get_jattr(pjob, attr_idx));
}

/**
 * @brief	Getter function for job attribute of type long
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	long
 * @retval	long value of the attribute
 * @retval	-1 if pjob is NULL
 */
long
get_jattr_long(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return get_attr_l(get_jattr(pjob, attr_idx));

	return -1;
}

/**
 * @brief	Getter function for job attribute of type long long
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	long long
 * @retval	long long value of the attribute
 * @retval	-1 if pjob is NULL
 */
long long
get_jattr_ll(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return get_attr_ll(get_jattr(pjob, attr_idx));

	return -1;
}

/**
 * @brief	Getter function for job attribute's user_encoded value
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	svrattrl *
 * @retval	user_encoded value of the attribute
 * @retval	NULL if pjob is NULL
 */
svrattrl *
get_jattr_usr_encoded(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return (get_jattr(pjob, attr_idx))->at_user_encoded;

	return NULL;
}

/**
 * @brief	Getter function for job attribute's priv_encoded value
 *
 * @param[in]	pjob - pointer to the job
 * @param[in]	attr_idx - index of the attribute to return
 *
 * @return	svrattrl *
 * @retval	priv_encoded value of the attribute
 * @retval	NULL if pjob is NULL
 */
svrattrl *
get_jattr_priv_encoded(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return (get_jattr(pjob, attr_idx))->at_priv_encoded;

	return NULL;
}

/**
 * @brief	Setter for job state
 *
 * @param[in]	job - pointer to job
 * @param[in]	val - state val
 *
 * @return	void
 */
void
set_job_state(job *pjob, char val)
{
	if (pjob != NULL)
		set_attr_c(get_jattr(pjob, JOB_ATR_state), val, SET);
}

/**
 * @brief	Setter for job substate
 *
 * @param[in]	job - pointer to job
 * @param[in]	val - substate val
 *
 * @return	void
 */
void
set_job_substate(job *pjob, long val)
{
	if (pjob != NULL)
		set_jattr_l_slim(pjob, JOB_ATR_substate, val, SET);
}

/**
 * @brief	Generic Job attribute setter (call if you want at_set() action functions to be called)
 *
 * @param[in]	pjob - pointer to job
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
set_jattr_generic(job *pjob, int attr_idx, char *val, char *rscn, enum batch_op op)
{
	if (pjob == NULL || val == NULL)
		return 1;

	return set_attr_generic(get_jattr(pjob, attr_idx), &job_attr_def[attr_idx], val, rscn, op);
}

/**
 * @brief	"fast" job attribute setter for string values
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	rscn - new resource val to set, if applicable
 *
 * @return	int
 * @retval	0 for success
 * @retval	!0 for failure
 */
int
set_jattr_str_slim(job *pjob, int attr_idx, char *val, char *rscn)
{
	if (pjob == NULL || val == NULL)
		return 1;

	return set_attr_generic(get_jattr(pjob, attr_idx), &job_attr_def[attr_idx], val, rscn, INTERNAL);
}

/**
 * @brief	"fast" job attribute setter for long values
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_jattr_l_slim(job *pjob, int attr_idx, long val, enum batch_op op)
{
	if (pjob == NULL)
		return 1;

	set_attr_l(get_jattr(pjob, attr_idx), val, op);

	return 0;
}

/**
 * @brief	"fast" job attribute setter for long long values
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_jattr_ll_slim(job *pjob, int attr_idx, long long val, enum batch_op op)
{
	if (pjob == NULL)
		return 1;

	set_attr_ll(get_jattr(pjob, attr_idx), val, op);

	return 0;
}

/**
 * @brief	"fast" job attribute setter for boolean values
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_jattr_b_slim(job *pjob, int attr_idx, long val, enum batch_op op)
{
	if (pjob == NULL)
		return 1;

	set_attr_b(get_jattr(pjob, attr_idx), val, op);

	return 0;
}

/**
 * @brief	"fast" job attribute setter for char values
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to set
 * @param[in]	val - new val to set
 * @param[in]	op - batch_op operation, SET, INCR, DECR etc.
 *
 * @return	int
 * @retval	0 for success
 * @retval	1 for failure
 */
int
set_jattr_c_slim(job *pjob, int attr_idx, char val, enum batch_op op)
{
	if (pjob == NULL)
		return 1;

	set_attr_c(get_jattr(pjob, attr_idx), val, op);

	return 0;
}

/**
 * @brief	Check if a job attribute is set
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to check
 *
 * @return	int
 * @retval	1 if it is set
 * @retval	0 otherwise
 */
int
is_jattr_set(const job *pjob, int attr_idx)
{
	if (pjob != NULL)
		return is_attr_set(get_jattr(pjob, attr_idx));

	return 0;
}

/**
 * @brief	Mark a job attribute as "not set"
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to set
 *
 * @return	void
 */
void
mark_jattr_not_set(job *pjob, int attr_idx)
{
	if (pjob != NULL) {
		attribute *attr = get_jattr(pjob, attr_idx);
		ATR_UNSET(attr);
	}
}

/**
 * @brief	Mark a job attribute as "set"
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to set
 *
 * @return	void
 */
void
mark_jattr_set(job *pjob, int attr_idx)
{
	if (pjob != NULL)
		(get_jattr(pjob, attr_idx))->at_flags |= ATR_VFLAG_SET;
}

/**
 * @brief	Free a job attribute
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to free
 *
 * @return	void
 */
void
free_jattr(job *pjob, int attr_idx)
{
	if (pjob != NULL)
		free_attr(job_attr_def, get_jattr(pjob, attr_idx), attr_idx);
}

/**
 * @brief	clear a job attribute
 *
 * @param[in]	pjob - pointer to job
 * @param[in]	attr_idx - attribute index to clear
 *
 * @return	void
 */
void
clear_jattr(job *pjob, int attr_idx)
{
	if (pjob != NULL)
		clear_attr(get_jattr(pjob, attr_idx), &job_attr_def[attr_idx]);
}

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


/**
 * @file    prev_job_info.c
 *
 * @brief
 * 		prev_job_info.c -  contains functions which are related to prev_job_info array.
 *
 * Functions included are:
 * 	create_prev_job_info()
 * 	free_prev_job_info()
 * 	free_pjobs()
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <log.h>
#include "prev_job_info.hpp"
#include "job_info.hpp"
#include "misc.hpp"
#include "resource_resv.hpp"


/**
 * @brief
 *		create_prev_job_info - create the prev_job_info array from an array
 *				of jobs
 *
 * @param[in,out]	jobs	-	job array
 * @param[in]	size	-	size of jinfo_arr or UNSPECIFIED if unknown
 *
 * @return	new prev_job_array
 * @retval	NULL	: on error
 *
 * @par	NOTE: jinfo_arr is modified
 *
 */
prev_job_info *
create_prev_job_info(resource_resv **jobs, int size)
{
	prev_job_info *new_;		/* new prev_job_info array */
	int local_size;		/* the size of the array */
	int i;

	if (jobs == NULL)
		return NULL;

	if (size == UNSPECIFIED) {
		for (i = 0; jobs[i] != NULL; i++)
			;

		local_size = i;
	}
	else
		local_size = size;

	if (local_size == 0)
		return NULL;

	if ((new_ = (prev_job_info *) calloc(local_size, sizeof(prev_job_info))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	for (i = 0; jobs[i] != NULL; i++) {
		if(jobs[i]->job != NULL) {
			new_[i].name = jobs[i]->name;
			new_[i].resused = jobs[i]->job->resused;
			new_[i].entity_name = string_dup(jobs[i]->job->ginfo->name);

			/* so the memory is not freed at the end of the scheduling cycle */
			jobs[i]->name = NULL;
			jobs[i]->job->resused = NULL;
		}
	}

	return new_;
}

/**
 * @brief
 *		free_prev_job_info - free a prev_job_info struct
 *
 * @param[in,out]	pjinfo	-	prev_job_info to free
 *
 * @return	nothing
 *
 */
void
free_prev_job_info(prev_job_info *pjinfo)
{
	if (pjinfo->name != NULL)
		free(pjinfo->name);

	if (pjinfo->entity_name != NULL)
		free(pjinfo->entity_name);

	free_resource_req_list(pjinfo->resused);
}

/**
 * @brief
 *		free_pjobs - free a list of prev_job_info structs
 *
 * @param[in,out]	pjinfo_arr	-	array of prev_job_info structs to free
 * @param[in]	previous job info array.
 *
 * @return	nothing
 *
 */
void
free_pjobs(prev_job_info *pjinfo_arr, int size)
{
	int i;

	if (pjinfo_arr == NULL)
		return;

	for (i = 0; i < size; i++)
		free_prev_job_info(&pjinfo_arr[i]);

	free(pjinfo_arr);
}

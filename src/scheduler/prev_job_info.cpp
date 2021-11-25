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
#include "prev_job_info.h"
#include "job_info.h"
#include "misc.h"
#include "resource_resv.h"
#include "globals.h"

/**
 * @brief
 *		create_prev_job_info - create the prev_job_info array from an array of jobs
 *
 * @param[in]	jobs	-	job array
 *
 * @par	NOTE: jinfo_arr is modified
 *
 */
void
create_prev_job_info(resource_resv **jobs)
{
	int i;

	last_running.clear();

	for (i = 0; jobs[i] != NULL; i++) {
		if (jobs[i]->job != NULL) {
			prev_job_info pjinfo(jobs[i]->name, jobs[i]->job->ginfo->name, jobs[i]->job->resused);

			/* resused is shallow copied, NULL it so it doesn't get freed at the end of the cycle */
			jobs[i]->job->resused = NULL;

			last_running.push_back(pjinfo);
		}
	}
}

prev_job_info::prev_job_info(const std::string &pname, const std::string &ename, resource_req *rused) : name(pname), entity_name(ename), resused(rused)
{
}

prev_job_info::prev_job_info(const prev_job_info &opj) : name(opj.name), entity_name(opj.entity_name)
{
	resused = dup_resource_req_list(opj.resused);
}

prev_job_info::prev_job_info(prev_job_info &&opj) : name(std::move(opj.name)), entity_name(std::move(opj.entity_name))
{
	resused = opj.resused;
	opj.resused = NULL;
}

prev_job_info &
prev_job_info::operator=(const prev_job_info &opj)
{
	name = opj.name;
	entity_name = opj.entity_name;
	resused = dup_resource_req_list(opj.resused);

	return *this;
}

/**
 * @brief
 *		prev_job_info destructor
 *
 */
prev_job_info::~prev_job_info()
{
	free_resource_req_list(resused);
}

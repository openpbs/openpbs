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

#include "attribute.h"
#include "job.h"
#include "pbs_assert.h"
#include "resource.h"
#include <stdlib.h>
#include <sys/types.h>
#include <time.h>

time_t time_now = 0;
double wallfactor = 1.00;

/**
 * @brief
 *
 *		start_walltime() starts counting the walltime of a job.
 *
 * @param[in] 	pjob	    - pointer to the job
 *
 * @return	void
 *
 * @par MT-safe: No
 */
void
start_walltime(job *pjob)
{
	if (NULL == pjob)
		return;
	/*
	 * time_now is global and should have positive value at this time
	 * if not, set it to current time
	 */
	if (0 == time_now)
		time_now = time(NULL);

	pjob->ji_walltime_stamp = time_now;
}

/**
 * @brief
 *
 *	update_walltime() updates the walltime of a job. If walltime is
 *	not in resources_used then update_walltime() creates a new entry
 *	for it.
 *
 * @param[in] 	pjob	    - pointer to the job
 *
 * @return	void
 *
 * @par MT-safe: No
 */
void
update_walltime(job *pjob)
{
	attribute *resources_used;
	resource_def *walltime_def;
	resource *used_walltime;

	resources_used = get_jattr(pjob, JOB_ATR_resc_used);
	assert(resources_used != NULL);
	walltime_def = &svr_resc_def[RESC_WALLTIME];
	used_walltime = find_resc_entry(resources_used, walltime_def);

	/* if walltime entry is not created yet, create it */
	if (NULL == used_walltime) {
		used_walltime = add_resource_entry(resources_used, walltime_def);
		mark_attr_set(&used_walltime->rs_value);
		used_walltime->rs_value.at_type = ATR_TYPE_LONG;
		used_walltime->rs_value.at_val.at_long = 0;
	}

	if (0 != (used_walltime->rs_value.at_flags & ATR_VFLAG_HOOK)) {
		/* walltime is set by hook so do not update here */
		return;
	}

	if (0 != pjob->ji_walltime_stamp) {
		/* walltime counting is not stopped so update it */
		set_attr_l(&used_walltime->rs_value, (long) ((time_now - pjob->ji_walltime_stamp) * wallfactor), INCR);
		pjob->ji_walltime_stamp = time_now;
	}
}

/**
 * @brief
 *
 *		stop_walltime() stops counting the walltime of a job.
 *
 * @param[in] 	pjob	    - pointer to the job
 *
 * @return	void
 *
 * @par MT-safe: No
 */
void
stop_walltime(job *pjob)
{
	if (NULL == pjob)
		return;
	/*
	 * time_now is global and should have positive value at this time
	 * if not, set it to current time
	 */
	if (0 == time_now)
		time_now = time(NULL);

	/* update walltime and stop accumulating */
	update_walltime(pjob);
	pjob->ji_walltime_stamp = 0;
}

/**
 * @brief
 *
 *		recover_walltime() tries to recover the used walltime of a job.
 *
 * @param[in] 	pjob	    - pointer to the job
 *
 * @return	void
 *
 * @par MT-safe: No
 */
void
recover_walltime(job *pjob)
{
	attribute *resources_used;
	resource_def *walltime_def;
	resource *used_walltime;

	if (NULL == pjob)
		return;

	if (0 == pjob->ji_qs.ji_stime)
		return;

	if (0 == time_now)
		time_now = time(NULL);

	resources_used = get_jattr(pjob, JOB_ATR_resc_used);
	assert(resources_used != NULL);
	walltime_def = &svr_resc_def[RESC_WALLTIME];
	assert(walltime_def != NULL);
	used_walltime = find_resc_entry(resources_used, walltime_def);

	/*
	* if the used walltime is not set, try to recover it.
	*/
	if (NULL == used_walltime) {
		used_walltime = add_resource_entry(resources_used, walltime_def);
		mark_attr_set(&used_walltime->rs_value);
		used_walltime->rs_value.at_type = ATR_TYPE_LONG;
		used_walltime->rs_value.at_val.at_long = (long) ((double) (time_now - pjob->ji_qs.ji_stime) * wallfactor);
	}
}

/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */

#include <stdlib.h>
#include <time.h>
#include <sys/types.h>
#include "job.h"
#include "attribute.h"
#include "resource.h"
#include "pbs_assert.h"

time_t			time_now = 0;
double			wallfactor = 1.00;

/**
 * @brief
 *
 *		This function starts counting the walltime of a job
 *
 * @param[in] 	pjob	    - pointer to the job
 * 
 * @return	void
 * 
 * @par MT-safe: No
 */
void
start_walltime(job *pjob) {
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
 *		This function updates the walltime of a job
 *
 * @param[in] 	pjob	    - pointer to the job
 * 
 * @return	void
 * 
 * @par MT-safe: No
 */
void
update_walltime(job *pjob) {
    attribute       *resources_used;
    resource_def    *walltime_def;
    resource        *used_walltime;

    if (0 == pjob->ji_walltime_stamp)
        return;

    resources_used = &pjob->ji_wattr[(int)JOB_ATR_resc_used];
    assert(resources_used != NULL);
    walltime_def = find_resc_def(svr_resc_def, "walltime", svr_resc_size);
    assert(walltime_def != NULL);
    used_walltime = find_resc_entry(resources_used, walltime_def);
    
    if (NULL == used_walltime) {
        used_walltime = add_resource_entry(resources_used, walltime_def);
        used_walltime->rs_value.at_flags |= ATR_VFLAG_SET;
        used_walltime->rs_value.at_type = ATR_TYPE_LONG;
        used_walltime->rs_value.at_val.at_long = 0;
    } else if (0 == (used_walltime->rs_value.at_flags & ATR_VFLAG_HOOK)) {
        /* walltime is not set by hook */
        used_walltime->rs_value.at_val.at_long += (long)((time_now - pjob->ji_walltime_stamp) * wallfactor);
        pjob->ji_walltime_stamp = time_now;
    }
    /* if walltime is set by hook then we do not update it */
}

/**
 * @brief
 *
 *		This function stops counting the walltime of a job
 *
 * @param[in] 	pjob	    - pointer to the job
 * 
 * @return	void
 * 
 * @par MT-safe: No
 */
void
stop_walltime(job *pjob) {
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
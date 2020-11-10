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
#include <stdio.h>

#include "check.h"
#include "constant.h"
#include "data_types.h"
#include "fifo.h"
#include "log.h"
#include "mock_run.h"
#include "resource.h"
#include "server_info.h"

/**
 * @brief	Perform scheduling in "mock run" mode
 *
 * @param[in]	policy	-	policy info
 * @param[in]	sd	-	primary socket descriptor to the server pool
 * @param[in]	sinfo	-	pbs universe we're going to loop over
 * @param[out]	rerr	-	error bits from the last job considered
 *
 *	@return return code of last job scheduled
 *	@retval -1	: on error
 */
int
mock_sched_loop(status *policy, int sd, server_info *sinfo, schd_error **rerr)
{
	node_info **nodes = sinfo->nodes;
	resource_resv **jobs = sinfo->jobs;
	int ij;
	int in = 0;

	/* Algorithm:
     * - Loop over all jobs, assume that they need just 1 ncpu to run, and
     *  choose the next free node for it
     */
	for (ij = 0; jobs[ij] != NULL; ij++) {
		char execvnode[PBS_MAXHOSTNAME + 1];
		execvnode[0] = '\0';

		/* Find the first free node and fill it */
		for (; nodes[in] != NULL; in++) {
			node_info *node = nodes[in];
			schd_resource *ncpures = NULL;

			if (node->is_busy || node->is_job_busy)
				continue;

			ncpures = find_resource(node->res, getallres(RES_NCPUS));
			if (ncpures == NULL)
				continue;

			/* Assign a cpu on this node */
			ncpures->assigned += 1;
			if (dynamic_avail(ncpures) == 0) {
				node->is_busy = 1;
				node->is_job_busy;
				node->is_free = 0;
			}

			/* Create the exec_node for the job */
			snprintf(execvnode, sizeof(execvnode), "(%s:ncpus=1)", node->name);

			/* Send the run request */
			send_run_job(sd, 0, jobs[ij]->name, execvnode);

			break;
		}
		if (execvnode[0] == '\0') {
			log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_NOTICE, "",
				  "No free nodes available, won't consider any more jobs");
			break;
		}
	}
	return SUCCESS;
}

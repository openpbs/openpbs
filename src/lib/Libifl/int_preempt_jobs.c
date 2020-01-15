/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

#include <pbs_config.h>   /* the master config generated by configure */

#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#include "portability.h"
#include "libpbs.h"
#include "dis.h"
#include "rpp.h"
#include "net_connect.h"
#include "pbs_share.h"

/**
 * @brief
 *	-Pass-through call to send preempt jobs batch request
 * 
 * @param[in] connect - connection handler
 * @param[in] preempt_jobs_list - list of jobs to be preempted
 *
 * @return      preempt_job_info *
 * @retval      list of jobs and their preempt_method
 *
 */
preempt_job_info*
PBSD_preempt_jobs(int connect, char **preempt_jobs_list)
{
	struct batch_reply *reply = NULL;
	preempt_job_info *ppj_reply = NULL;
	preempt_job_info *ppj_temp = NULL;

	int rc = -1;
	int sock = 0;

	sock = connection[connect].ch_socket;
	DIS_tcp_setup(sock);

	/* first, set up the body of the Preempt Jobs request */

	if ((rc = encode_DIS_ReqHdr(sock, PBS_BATCH_PreemptJobs, pbs_current_user)) ||
		(rc = encode_DIS_PreemptJobs(sock, preempt_jobs_list)) ||
		(rc = encode_DIS_ReqExtend(sock, NULL))) {
			connection[connect].ch_errtxt = strdup(dis_emsg[rc]);
			if (connection[connect].ch_errtxt == NULL)
				return NULL;
			if (pbs_errno == PBSE_PROTOCOL)
				return NULL;
	}
	if (DIS_tcp_wflush(sock)) {
		pbs_errno = PBSE_PROTOCOL;
		return NULL;
	}

	reply = PBSD_rdrpy(connect);
	if (reply == NULL)
		pbs_errno = PBSE_PROTOCOL;
	else {
		int i = 0;
		int count = 0;
		ppj_temp = reply->brp_un.brp_preempt_jobs.ppj_list;
		count = reply->brp_un.brp_preempt_jobs.count;

		ppj_reply = calloc(sizeof(struct preempt_job_info), count);
		if (ppj_reply == NULL)
			return NULL;

		for (i = 0; i < count; i++) {
			strcpy(ppj_reply[i].job_id, ppj_temp[i].job_id);
			strcpy(ppj_reply[i].order, ppj_temp[i].order);
		}
		PBSD_FreeReply(reply);
	}
	return ppj_reply;
}


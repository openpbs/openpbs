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
 * @file	pbs_deljob.c
 * @brief
 * Send the Delete Job request to the server
 * really just an instance of the manager request
 */

#include <pbs_config.h> /* the master config generated by configure */

#include "cmds.h"
#include "dis.h"
#include "libpbs.h"
#include "libutil.h"
#include "net_connect.h"
#include "pbs_ecl.h"
#include "pbs_ifl.h"
#include "tpp.h"
#include <stdio.h>
#include "dedup_jobids.h"

/**
 * @brief	Deallocate a svr_jobid_list_t list
 * @param[out]	list - the list to deallocate
 * @param[in]	shallow - shallow free (don't free the individual jobids in the array)
 * @return	void
 */
void
free_svrjobidlist(svr_jobid_list_t *list, int shallow)
{
	svr_jobid_list_t *iter_list = NULL;
	svr_jobid_list_t *next = NULL;

	for (iter_list = list; iter_list != NULL; iter_list = next) {
		next = iter_list->next;
		if (shallow)
			free(iter_list->jobids);
		else
			free_str_array(iter_list->jobids);
		free(iter_list);
	}
}

/**
 * @brief
 *	Append a given jobid to the given svr_jobid_list struct.
 *
 * @param[in] svr - Server name
 * @param[in] jobid - Job id
 *
 * @return	int
 * @retval	0 for Success
 * @retval	1 for Failure
 */
int
append_jobid(svr_jobid_list_t *svr, const char *jobid)
{
	if ((svr == NULL) || (jobid == NULL))
		return 0;

	if (svr->max_sz == 0) {
		svr->jobids = malloc((DELJOB_DFLT_NUMIDS + 1) * sizeof(char *));
		if (svr->jobids == NULL)
			goto error;
		svr->max_sz = DELJOB_DFLT_NUMIDS;
	} else if (svr->total_jobs == svr->max_sz) {
		char **realloc_ptr = NULL;

		svr->max_sz *= 2;
		realloc_ptr = realloc(svr->jobids, (svr->max_sz + 1) * sizeof(char *));
		if (realloc_ptr == NULL)
			goto error;
		svr->jobids = realloc_ptr;
	}

	svr->jobids[svr->total_jobs++] = (char *) jobid;
	svr->jobids[svr->total_jobs] = NULL;
	return 0;

error:
	pbs_errno = PBSE_SYSTEM;
	return 1;
}

/**
 * @brief
 *	Identify the respective svr_jobid_list struct
 *  and calls the append_jobid function to append the jobid.
 *
 * @param[in] job_id - Job id
 * @param[in] svrname - server name
 * @param[in,out] svr_jobid_list_hd - head of the svr_jobib_list list
 *
 * @return int
 * @retval	0	- success
 * @retval	1	- failure
 *
 */
int
add_jid_to_list_by_name(char *job_id, char *svrname, svr_jobid_list_t **svr_jobid_list_hd)
{
	svr_jobid_list_t *iter_list = NULL;
	svr_jobid_list_t *new_node = NULL;

	if ((job_id == NULL) || (svrname == NULL) || (svr_jobid_list_hd == NULL))
		return 1;

	for (iter_list = *svr_jobid_list_hd; iter_list != NULL; iter_list = iter_list->next) {
		if (strcmp(svrname, iter_list->svrname) == 0) {
			if (append_jobid(iter_list, job_id) != 0)
				return 1;
			return 0;
		}
	}

	new_node = calloc(1, sizeof(svr_jobid_list_t));
	if (new_node == NULL) {
		pbs_errno = PBSE_SYSTEM;
		return 1;
	}
	new_node->svr_fd = -1;
	pbs_strncpy(new_node->svrname, svrname, sizeof(new_node->svrname));
	if (append_jobid(new_node, job_id) != 0) {
		free(new_node);
		return 1;
	}
	new_node->next = *svr_jobid_list_hd;
	*svr_jobid_list_hd = new_node;

	return 0;
}

/**
 * @brief
 *	Send the Delete Job List request to the server
 *
 *
 * @param[in] c - connection handler
 * @param[in] jobid - job identifier array
 * @param[in] numjids - number of job ids
 * @param[in] extend - string to encode req
 *
 * @return	struct batch_status *
 * @retval     list of jobs which couldn't be deleted
 *
 */
struct batch_deljob_status *
__pbs_deljoblist(int c, char **jobids, int numjids, const char *extend)
{
	int rc, i;
	struct batch_reply *reply;
	struct batch_deljob_status *ret = NULL;

	if ((jobids == NULL) || (*jobids == NULL) || (**jobids == '\0') || c < 0)
		return NULL;

	char *malloc_track = calloc(1, numjids);
	/* Deletes duplicate jobids */
	if (dedup_jobids(jobids, &numjids, malloc_track) != 0)
		goto end;

	DIS_tcp_funcs();

	if ((rc = encode_DIS_ReqHdr(c, PBS_BATCH_DeleteJobList, pbs_current_user)) ||
	    (rc = encode_DIS_JobsList(c, jobids, numjids)) ||
	    (rc = encode_DIS_ReqExtend(c, extend))) {
		if (set_conn_errtxt(c, dis_emsg[rc]) != 0) {
			pbs_errno = PBSE_SYSTEM;
			goto end;
		}
		pbs_errno = PBSE_PROTOCOL;
		goto end;
	}

	if (dis_flush(c)) {
		pbs_errno = PBSE_PROTOCOL;
		goto end;
	}

	if (c < 0)
		goto end;

	reply = PBSD_rdrpy(c);
	if (reply == NULL && pbs_errno == PBSE_NONE)
		pbs_errno = PBSE_PROTOCOL;

	else if (reply->brp_choice != BATCH_REPLY_CHOICE_NULL &&
		 reply->brp_choice != BATCH_REPLY_CHOICE_Text &&
		 reply->brp_choice != BATCH_REPLY_CHOICE_Delete)
		pbs_errno = PBSE_PROTOCOL;

	if ((reply != NULL) && (reply->brp_un.brp_deletejoblist.brp_delstatc != NULL)) {
		ret = reply->brp_un.brp_deletejoblist.brp_delstatc;
		reply->brp_un.brp_deletejoblist.brp_delstatc = NULL;
	}

	PBSD_FreeReply(reply);

end:
	/* We need to free the jobid's that were allocated in dedup_jobids()
		 * rest of the jobid's are not on heap */
	for (i = 0; i < numjids; i++)
		if (malloc_track[i])
			free(jobids[i]);

	free(malloc_track);
	return ret;
}

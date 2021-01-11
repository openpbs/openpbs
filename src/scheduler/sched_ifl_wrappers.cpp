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

#include <stdlib.h>
#include <pbs_ifl.h>
#include <libpbs.h>
#include "data_types.h"
#include "fifo.h"
#include "globals.h"
#include "job_info.h"
#include "misc.h"
#include "log.h"
#include "server_info.h"


/**
 * @brief	Send the relevant runjob request to server
 *
 * @param[in]	virtual_sd	-	virtual sd for the cluster
 * @param[in]	has_runjob_hook	- does server have a runjob hook?
 * @param[in]	jobid	-	id of the job to run
 * @param[in]	execvnode	-	the execvnode to run the job on
 * @param[in]	svr_id_job -	server id of the job
 *
 * @return	int
 * @retval	return value of the runjob call
 */
int
send_run_job(int virtual_sd, int has_runjob_hook, const std::string& jobid, char *execvnode, char *svr_id_job)
{
 	int job_owner_sd;

	if (jobid.empty() || execvnode == NULL)
		return 1;

	job_owner_sd = get_svr_inst_fd(virtual_sd, svr_id_job);

	if (sc_attrs.runjob_mode == RJ_EXECJOB_HOOK)
		return pbs_runjob(job_owner_sd, const_cast<char *>(jobid.c_str()), execvnode, NULL);
	else if (((sc_attrs.runjob_mode == RJ_RUNJOB_HOOK) && has_runjob_hook))
		return pbs_asyrunjob_ack(job_owner_sd, const_cast<char *>(jobid.c_str()), execvnode, NULL);
	else
		return pbs_asyrunjob(job_owner_sd, const_cast<char *>(jobid.c_str()), execvnode, NULL);
}

/**
 * @brief
 * 		send delayed attributes to the server for a job
 *
 * @param[in]	virtual_sd	-	virtual sd for the cluster
 * @param[in]	resresv	-	resource_resv object for job
 * @param[in]	pattr	-	attrl list to update on the server
 *
 * @return	int
 * @retval	1	success
 * @retval	0	failure to update
 */
int
send_attr_updates(int virtual_sd, resource_resv *resresv, struct attrl *pattr)
{
	const char *errbuf;
	int one_attr = 0;
	int job_owner_sd = get_svr_inst_fd(virtual_sd, resresv->svr_inst_id);
	const std::string& job_name = resresv->name;

	if (job_name.empty() || pattr == NULL)
		return 0;

	if (job_owner_sd == SIMULATE_SD)
		return 1; /* simulation always successful */

	if (pattr->next == NULL)
		one_attr = 1;

	if (pbs_asyalterjob(job_owner_sd, const_cast<char *>(job_name.c_str()), pattr, NULL) == 0) {
		last_attr_updates = time(NULL);
		return 1;
	}

	if (is_finished_job(pbs_errno) == 1) {
		if (one_attr)
			log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO, job_name,
				   "Failed to update attr \'%s\' = %s, Job already finished",
				   pattr->name, pattr->value);
		else
			log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_INFO, job_name,
				"Failed to update job attributes, Job already finished");
		return 0;
	}

	errbuf = pbs_geterrmsg(job_owner_sd);
	if (errbuf == NULL)
		errbuf = "";
	if (one_attr)
		log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_SCHED, LOG_WARNING, job_name,
			   "Failed to update attr \'%s\' = %s: %s (%d)",
			   pattr->name, pattr->value, errbuf, pbs_errno);
	else
		log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_SCHED, LOG_WARNING, job_name,
			"Failed to update job attributes: %s (%d)",
			errbuf, pbs_errno);

	return 0;
}

/**
 * @brief	Wrapper for pbs_preempt_jobs
 *
 * @param[in]	virtual_sd - virtual sd for the cluster
 * @param[in]	preempt_jobs_list - list of jobs to preempt
 *
 * @return	preempt_job_info *
 * @retval	return value of pbs_preempt_jobs
 */
preempt_job_info *
send_preempt_jobs(int virtual_sd, char **preempt_jobs_list)
{
    return pbs_preempt_jobs(virtual_sd, preempt_jobs_list);
}

/**
 * @brief	Wrapper for pbs_signaljob
 *
 * @param[in]	virtual_sd - virtual sd for the cluster
 * @param[in]	resresv - resource_resv for the job to send signal to
 * @param[in]	signal - the signal to send (e.g - "resume")
 * @param[in]	extend - extend data for signaljob
 *
 * @return	preempt_job_info *
 * @retval	return value of pbs_preempt_jobs
 */
int
send_sigjob(int virtual_sd, resource_resv *resresv, const char *signal, char *extend)
{
	return pbs_sigjob(get_svr_inst_fd(virtual_sd, resresv->svr_inst_id),
			  const_cast<char *>(resresv->name.c_str()), const_cast<char *>(signal), extend);
}

/**
 * @brief	Wrapper for pbs_confirmresv
 *
 * @param[in]	virtual_sd - virtual sd for the cluster
 * @param[in]	resv - resource_resv for the resv to send confirmation to
 * @param[in] 	location - string of vnodes/resources to be allocated to the resv.
 * @param[in] 	start - start time of reservation if non-zero
 * @param[in] 	extend - extend data for pbs_confirmresv
 *
 * @return	int
 * @retval	0	Success
 * @retval	!0	error
 */
int
send_confirmresv(int virtual_sd, resource_resv *resv, const char *location, unsigned long start, const char *extend)
{
	return pbs_confirmresv(get_svr_inst_fd(virtual_sd, resv->svr_inst_id),
		const_cast<char *>(resv->name.c_str()), const_cast<char *>(location), start, const_cast<char *>(extend));	
}
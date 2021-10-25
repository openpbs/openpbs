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
#include "libutil.h"

/**
 * @brief	Send the relevant runjob request to server
 *
 * @param[in]	sd	-	communication handle
 * @param[in]	has_runjob_hook	- does server have a runjob hook?
 * @param[in]	jobid	-	id of the job to run
 * @param[in]	execvnode	-	the execvnode to run the job on
 * @param[in]	svr_id_job -	server id of the job
 *
 * @return	int
 * @retval	return value of the runjob call
 */
int
send_run_job(int sd, int has_runjob_hook, const std::string& jobid, char *execvnode)
{
	if (jobid.empty() || execvnode == NULL)
		return 1;

	if (sc_attrs.runjob_mode == RJ_EXECJOB_HOOK)
		return pbs_runjob(sd, const_cast<char *>(jobid.c_str()), execvnode, NULL);
	else if (((sc_attrs.runjob_mode == RJ_RUNJOB_HOOK) && has_runjob_hook))
		return pbs_asyrunjob_ack(sd, const_cast<char *>(jobid.c_str()), execvnode, NULL);
	else
		return pbs_asyrunjob(sd, const_cast<char *>(jobid.c_str()), execvnode, NULL);
}

/**
 * @brief
 * 		send delayed attributes to the server for a job
 *
 * @param[in]	sd	-	communication handle
 * @param[in]	resresv	-	resource_resv object for job
 * @param[in]	pattr	-	attrl list to update on the server
 *
 * @return	int
 * @retval	1	success
 * @retval	0	failure to update
 */
int
send_attr_updates(int sd, resource_resv *resresv, struct attrl *pattr)
{
	const char *errbuf;
	int one_attr = 0;
	const std::string& job_name = resresv->name;

	if (job_name.empty() || pattr == NULL)
		return 0;

	if (sd == SIMULATE_SD)
		return 1; /* simulation always successful */

	if (pattr->next == NULL)
		one_attr = 1;

	if (pbs_asyalterjob(sd, const_cast<char *>(job_name.c_str()), pattr, NULL) == 0) {
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

	errbuf = pbs_geterrmsg(sd);
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
 * @param[in]	sd - communication handle
 * @param[in]	preempt_jobs_list - list of jobs to preempt
 *
 * @return	preempt_job_info *
 * @retval	return value of pbs_preempt_jobs
 */
preempt_job_info *
send_preempt_jobs(int sd, char **preempt_jobs_list)
{
    return pbs_preempt_jobs(sd, preempt_jobs_list);
}

/**
 * @brief	Wrapper for pbs_signaljob
 *
 * @param[in]	sd - communication handle
 * @param[in]	resresv - resource_resv for the job to send signal to
 * @param[in]	signal - the signal to send (e.g - "resume")
 * @param[in]	extend - extend data for signaljob
 *
 * @return	int
 * @retval	0 for success, 1 for error
 */
int
send_sigjob(int sd, resource_resv *resresv, const char *signal, char *extend)
{
	return pbs_sigjob(sd, const_cast<char *>(resresv->name.c_str()), const_cast<char *>(signal), extend);
}

/**
 * @brief	Wrapper for pbs_confirmresv
 *
 * @param[in]	sd - communication handle
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
send_confirmresv(int sd, resource_resv *resv, const char *location, unsigned long start, const char *extend)
{
	return pbs_confirmresv(sd, const_cast<char *>(resv->name.c_str()), const_cast<char *>(location), start, const_cast<char *>(extend));
}

/**
 * @brief	Wrapper for pbs_selstat
 *
 * @param[in] sd - communication handle
 * @param[in] attrib - pointer to attropl structure(selection criteria)
 * @param[in] extend - extend string to encode req
 * @param[in] rattrib - list of attributes to return
 *
 * @return	struct batch_status *
 * @retval	list of queried jobs
 * @retval	NULL for error
 */
struct batch_status *
send_selstat(int sd, struct attropl *attrib, struct attrl *rattrib, char *extend)
{
	return pbs_selstat(sd, attrib, rattrib, extend);
}

/**
 * @brief	Wrapper for pbs_statvnode
 *
 * @param[in] sd - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	struct batch_status *
 * @retval	list of queried nodes
 * @retval	NULL for error
 */
struct batch_status *
send_statvnode(int sd, char *id, struct attrl *attrib, char *extend)
{
	return pbs_statvnode(sd, id, attrib, extend);
}

/**
 * @brief	Wrapper for pbs_statsched
 *
 * @param[in] sd - communication handle
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	struct batch_status *
 * @retval	list of queried scheds
 * @retval	NULL for error
 */
struct batch_status *
send_statsched(int sd, struct attrl *attrib, char *extend)
{
	return pbs_statsched(sd, attrib, extend);
}

/**
 * @brief	Wrapper for pbs_statque
 *
 * @param[in] sd - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	struct batch_status *
 * @retval	list of queried queues
 * @retval	NULL for error
 */
struct batch_status *
send_statqueue(int sd, char *id, struct attrl *attrib, char *extend)
{
	return pbs_statque(sd, id, attrib, extend);
}

/**
 * @brief	Wrapper for pbs_statserver
 *
 * @param[in] sd - communication handle
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	struct batch_status *
 * @retval	batch_status for server (aggregated in case of multi-server)
 * @retval	NULL for error
 */
struct batch_status *
send_statserver(int sd, struct attrl *attrib, char *extend)
{
	return pbs_statserver(sd, attrib, extend);
}

/**
 * @brief	Wrapper for pbs_statrsc
 *
 * @param[in] sd - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	struct batch_status *
 * @retval	list of resources
 * @retval	NULL for error
 */
struct batch_status *
send_statrsc(int sd, char *id, struct attrl *attrib, char *extend)
{
	return pbs_statrsc(sd, id, attrib, extend);
}

/**
 * @brief	Wrapper for pbs_statresv
 *
 * @param[in] sd - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	struct batch_status *
 * @retval	list of reservations
 * @retval	NULL for error
 */
struct batch_status *
send_statresv(int sd, char *id, struct attrl *attrib, char *extend)
{
	return pbs_statresv(sd, id, attrib, extend);
}

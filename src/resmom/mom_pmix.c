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
 * @file	mom_pmix.c
 */

#include <pbs_config.h>

#ifdef PMIX

#include <stdio.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <pthread.h>
#include "mom_pmix.h"
#include "mom_func.h"
#include "list_link.h"
#include "log.h"
#include "tm.h"

extern char *log_file;
extern char *path_log;
extern char mom_short_name[];
extern pbs_list_head svr_alljobs;

#if 0

/*
 * Some operations like spawn and fence are not atomic and occur
 * over a series of steps. In some cases, data needs to be retained
 * and used in subsequent steps. We might choose to define a data
 * structure that houses both tracking information (e.g. namespace,
 * operation type, etc.) together with an opaque union to house the
 * underlying data. That is what is being suggested (but not yet
 * implemented) here.
 */

/* Enumerate operations that require PBS to call back */
typedef enum pbs_pmix_oper_type {
	PBS_PMIX_OPER_NONE,
	PBS_PMIX_FENCE,
	PBS_PMIX_SPAWN,
	/* Add new operations before PBS_PMIX_OPER_UNDEFINED */
	PBS_PMIX_OPER_UNDEFINED
} pbs_pmix_oper_type_t;

/* Data structure to house auxiliary PMIx operation data */
typedef struct pbs_pmix_oper {
	pbs_pmix_oper_type_t type;
	job *pjob;
	struct pbs_pmix_oper *next;
	union {
		pbs_pmix_fence_data_t fence;
		pbs_pmix_spawn_data_t spawn;
	} data;
} pbs_pmix_oper_t;

#endif

/* Locking structure and macros */
typedef struct {
	pthread_mutex_t mutex;
	pthread_cond_t cond;
	volatile bool active;
	pmix_status_t status;
} pbs_pmix_lock_t;

#define PBS_PMIX_CONSTRUCT_LOCK(l)                     \
	do {                                           \
		pthread_mutex_init(&(l)->mutex, NULL); \
		pthread_cond_init(&(l)->cond, NULL);   \
		(l)->active = true;                    \
		(l)->status = PMIX_SUCCESS;            \
	} while (0)

#define PBS_PMIX_DESTRUCT_LOCK(l)                   \
	do {                                        \
		pthread_mutex_destroy(&(l)->mutex); \
		pthread_cond_destroy(&(l)->cond);   \
	} while (0)

#define PBS_PMIX_WAIT_THREAD(lck)                                       \
	do {                                                            \
		pthread_mutex_lock(&(lck)->mutex);                      \
		while ((lck)->active) {                                 \
			pthread_cond_wait(&(lck)->cond, &(lck)->mutex); \
		}                                                       \
		pthread_mutex_unlock(&(lck)->mutex);                    \
	} while (0)

#define PBS_PMIX_WAKEUP_THREAD(lck)                   \
	do {                                          \
		pthread_mutex_lock(&(lck)->mutex);    \
		(lck)->active = false;                \
		pthread_cond_broadcast(&(lck)->cond); \
		pthread_mutex_unlock(&(lck)->mutex);  \
	} while (0)

/**
 * @brief
 * This callback function is invoked by the PMIx library after it
 * has been notified a process has exited.
 *
 * @param[in] status - exit status of the process
 * @param[in] cbdata - opaque callback data passed to the caller
 *
 * @retval void
 *
 * @note
 * This function may be superfluous, in which case the call to
 * PMIx_Notify_event() should be passed NULL in pbs_pmix_notify_exit()
 * for its callback and this funtion removed. It has been left in for
 * the time being so that the log shows it being called.
 */
static void
pbs_pmix_notify_exit_cb(pmix_status_t status, void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
}

/**
 * @brief
 * Notify PMIx that a task has exited by constructing a PMIx info
 * array and passing it to PMIx_Notify_event.
 *
 * @param[in] pjob - pointer to the job structure for the exited task
 * @param[in] exitstat - numeric exit status of the task
 * @param[in] msg - optional message supplied by the caller
 *
 * @retval void
 */
void
pbs_pmix_notify_exit(job *pjob, int exitstat, char *msg)
{
	pmix_status_t status;
	pmix_info_t *pinfo;
	size_t ninfo;
	pmix_proc_t procname, procsrc;
	bool flag = true;

	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	if (!pjob) {
		log_event(PBSEVENT_DEBUG, 0, LOG_ERR, __func__,
			  "No job supplied, returning");
		return;
	}
	log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
		  pjob->ji_qs.ji_jobid,
		  "Setting up the info array for termination");
	/* Info array will contain three entries */
	ninfo = 3;
	/* Add one if a message was provided */
	if (msg)
		ninfo++;
	/* Create the info array */
	PMIX_INFO_CREATE(pinfo, ninfo);
	/* Ensure this only goes to the job terminated event handler */
	PMIX_INFO_LOAD(&pinfo[0], PMIX_EVENT_NON_DEFAULT, &flag, PMIX_BOOL);
	/* Provide the exit status of the application */
	PMIX_INFO_LOAD(&pinfo[1], PMIX_JOB_TERM_STATUS, &exitstat, PMIX_STATUS);
	/* Provide the rank */
	PMIX_LOAD_PROCID(&procname, pjob->ji_qs.ji_jobid, PMIX_RANK_WILDCARD);
	PMIX_INFO_LOAD(&pinfo[2], PMIX_EVENT_AFFECTED_PROC, &procname, PMIX_PROC);
	/* Provide the message if provided */
	if (msg)
		PMIX_INFO_LOAD(&pinfo[3], PMIX_EVENT_TEXT_MESSAGE, msg, PMIX_STRING);
	log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
		  pjob->ji_qs.ji_jobid, "Info array populated");
	/*
	 * The source of the event may not be mother superior because it
	 * will cause the PMIx server to upcall recursively. Use an
	 * undefined rank as the source.
	 */
	PMIX_LOAD_PROCID(&procsrc, pjob->ji_qs.ji_jobid, PMIX_RANK_UNDEF);
	status = PMIx_Notify_event(PMIX_ERR_JOB_TERMINATED, &procsrc,
				   PMIX_RANGE_SESSION, pinfo, ninfo, pbs_pmix_notify_exit_cb,
				   NULL);
	switch (status) {
		/* The first four status cases are documented */
		case PMIX_SUCCESS:
			log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
				  pjob->ji_qs.ji_jobid,
				  "Exit notification pending callback");
			break;
		case PMIX_OPERATION_SUCCEEDED:
			log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
				  pjob->ji_qs.ji_jobid,
				  "Exit notification successful");
			break;
		case PMIX_ERR_BAD_PARAM:
			log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
				  pjob->ji_qs.ji_jobid,
				  "Exit notification contains bad parameter");
			break;
		case PMIX_ERR_NOT_SUPPORTED:
			log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
				  pjob->ji_qs.ji_jobid,
				  "Exit notification not supported");
			break;
		default:
			/* An undocumented error type was encountered */
			log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
				   pjob->ji_qs.ji_jobid,
				   "Exit notification failed: %s",
				   PMIx_Error_string(status));
			break;
	}
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
}

/**
 * @brief
 * Client called PMIx_server_register_client
 *
 * @param[in] proc - client handle
 * @param[in] server_object - value provided by caller
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_client_connected(
	const pmix_proc_t *proc,
	void *server_object,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_OPERATION_SUCCEEDED;
}

/**
 * @brief
 * Client called PMIx_Finalize
 *
 * @param[in] proc - client handle
 * @param[in] server_object - value provided by caller
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_client_finalized(
	const pmix_proc_t *proc,
	void *server_object,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_OPERATION_SUCCEEDED;
}

/**
 * @brief
 * Client called PMIx_Abort
 *
 * @param[in] proc - client handle
 * @param[in] server_object - value provided by caller
 * @param[in] status - client status
 * @param[in] msg - client status message
 * @param[in] procs - array of client handle pointers
 * @param[in] nprocs - number of client handle pointers
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_abort(
	const pmix_proc_t *proc,
	void *server_object,
	int status,
	const char msg[],
	pmix_proc_t procs[],
	size_t nprocs,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	int i;
	job *pjob;

	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	if (!proc) {
		log_err(-1, __func__, "pmix_proc_t parameter is NULL");
		log_event(PBSEVENT_DEBUG, 0, LOG_DEBUG, __func__, "returning");
		return PMIX_ERROR;
	}
	if (!proc->nspace || (*proc->nspace == '\0')) {
		log_err(-1, __func__, "Invalid PMIx namespace");
		log_event(PBSEVENT_DEBUG, 0, LOG_DEBUG, __func__, "returning");
		return PMIX_ERROR;
	}
	pjob = find_job((char *) proc->nspace);
	if (!pjob) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "Job not found: %s", proc->nspace);
		log_err(-1, __func__, log_buffer);
		log_event(PBSEVENT_DEBUG, 0, LOG_DEBUG, __func__, "returning");
		return PMIX_ERROR;
	}
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid, "abort status: %d", status);
	if (msg && *msg) {
		log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			   pjob->ji_qs.ji_jobid, "abort message: %s", msg);
	}
	if (!procs) {
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, "All processes to be aborted");
	} else {
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, "Following processes to be aborted:");
		for (i = 0; i < nprocs; i++) {
			log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
				   pjob->ji_qs.ji_jobid, "namespace/rank: %s/%u",
				   procs[i].nspace, procs[i].rank);
		}
	}
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * At least one client called PMIx_Fence (blocking) or
 * PMIx_Fence_nb (non-blocking)
 *
 * @param[in] procs - array of client handle pointers
 * @param[in] nprocs - number of client handle pointers
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] data - data (string) to aggregate
 * @param[in] ndata - length of data
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 *
 * @note
 * Required attributes:
 * PMIX_COLLECT_DATA
 * Optional attributes:
 * PMIX_TIMEOUT
 * PMIX_COLLECTIVE_ALGO
 * PMIX_COLLECTIVE_ALGO_REQD
 */
static pmix_status_t
pbs_pmix_fence_nb(
	const pmix_proc_t proc[],
	size_t nproc,
	const pmix_info_t info[],
	size_t ninfo,
	char *data,
	size_t ndata,
	pmix_modex_cbfunc_t cbfunc,
	void *cbdata)
{
	int i;
	job *pjob;

	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	if (!proc) {
		log_err(-1, __func__, "pmix_proc_t parameter is NULL");
		return PMIX_ERROR;
	}
	if (!proc->nspace || (*proc->nspace == '\0')) {
		log_err(-1, __func__, "Invalid PMIx namespace");
		return PMIX_ERROR;
	}
	pjob = find_job((char *) proc->nspace);
	if (!pjob) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "Job not found: %s", proc->nspace);
		log_err(-1, __func__, log_buffer);
		return PMIX_ERROR;
	}
	for (i = 0; i < nproc; i++) {
		log_eventf(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
			   "proc[%d].nspace = %s", i, proc[i].nspace);
		log_eventf(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
			   "proc[%d].rank = %u", i, (unsigned int) proc[i].rank);
	}
	for (i = 0; i < ninfo; i++) {
		log_eventf(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
			   "info[%d].key = %s", i, info[i].key);
	}
	log_eventf(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
		   "There are %lu data entries", ndata);
	/*
	 * If MS, find/create the barrier for this job. Otherwise, send
	 * a message to MS that a fence has been encountered. Once all
	 * ranks have been accounted for, invoke the callback function.
	 */
	log_eventf(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
		   "cbfunc %s NULL", cbfunc ? "is not" : "is");
	log_eventf(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
		   "cbdata %s NULL", cbdata ? "is not" : "is");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_OPERATION_SUCCEEDED;
}

/**
 * @brief
 * PMIx server on local host is requesting information from remote
 * node hosting provided proc handle
 *
 * @param[in] proc - client handle pointer
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - required callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_direct_modex(
	const pmix_proc_t *proc,
	const pmix_info_t info[],
	size_t ninfo,
	pmix_modex_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Caller is requesting data be published per the PMIx API spec
 *
 * @param[in] proc - client handle pointer
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_publish(
	const pmix_proc_t *proc,
	const pmix_info_t info[],
	size_t ninfo,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Caller is requesting published data be looked up
 *
 * @param[in] proc - client handle pointer
 * @param[in] keys - array of strings to lookup
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_lookup(
	const pmix_proc_t *proc,
	char **keys,
	const pmix_info_t info[],
	size_t ninfo,
	pmix_lookup_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Delete previously published data from the data store
 *
 * @param[in] proc - client handle pointer
 * @param[in] keys - array of strings to lookup
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_unpublish(
	const pmix_proc_t *proc,
	char **keys,
	const pmix_info_t info[],
	size_t ninfo,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Client called PMIx_Spawn
 *
 * @param[in] proc - client handle pointer
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] apps - array of application handles
 * @param[in] napps - number of application handles
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 *
 * @note
 * The PMIx spec refers to the info parameter as job_info. PMIx refers to
 * an application or client as a job, whereas a job refers to a batch job
 * in PBS nomenclature.
 */
static pmix_status_t
pbs_pmix_spawn(
	const pmix_proc_t *proc,
	const pmix_info_t info[],
	size_t ninfo,
	const pmix_app_t apps[],
	size_t napps,
	pmix_spawn_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Record process(es) as connected
 *
 * @param[in] procs - array of client handle pointers
 * @param[in] nprocs - number of client handle pointers
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_connect(
	const pmix_proc_t procs[],
	size_t nprocs,
	const pmix_info_t info[],
	size_t ninfo,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Record process(es) as disconnected
 *
 * @param[in] procs - array of client handle pointers
 * @param[in] nprocs - number of client handle pointers
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_disconnect(
	const pmix_proc_t procs[],
	size_t nprocs,
	const pmix_info_t info[],
	size_t ninfo,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Register to recieve event notifications
 *
 * @param[in] codes - array of status codes to register for
 * @param[in] ncodes - number of codes in the array
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_register_events(
	pmix_status_t *codes,
	size_t ncodes,
	const pmix_info_t info[],
	size_t ninfo,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Deregister from event notifications
 *
 * @param[in] codes - array of status codes to deregister
 * @param[in] ncodes - number of codes in the array
 * @param[in] info - PMIx info array (parameters provided by caller)
 * @param[in] ninfo - number of info array entries
 * @param[in] cbfunc - optional callback function
 * @param[in] cbdata - opaque data provided to cbfunc
 *
 * @return pmix_status_t
 * @retval PMIX_SUCCESS - request in progress, cbfunc should not be called
 *                        here but will be called later by PMIx
 * @retval PMIX_OPERATION_SUCCEEDED - request immediately processed and
 *                                    successful, cbfunc will not be called
 * @retval PMIX_ERR_BAD_PARAM - one of the provided parameters was invalid
 * @retval PMIX_ERR_NOT_IMPLEMENTED - function not implemented
 */
static pmix_status_t
pbs_pmix_deregister_events(
	pmix_status_t *codes,
	size_t ncodes,
	pmix_op_cbfunc_t cbfunc,
	void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return PMIX_ERR_NOT_IMPLEMENTED;
}

/**
 * @brief
 * Initialize the PMIx server
 *
 * @param[in] name - name of daemon (used for logging)
 *
 * @return void
 *
 * @note
 * The PMIx library spawns threads from pbs_mom to act as the PMIx server
 * for applications (PMIx clients) assigned to this vnode. The pbs_mom acts
 * as the PMIx server even though all it does is call PMIx library functions.
 * It also means that if pbs_mom exits, any PMIx clients (PMIx enabled
 * applications) will lose their local server and fail.
 */
void
pbs_pmix_server_init(char *name)
{
	pmix_status_t pstat;
	pmix_server_module_t pbs_pmix_server_module = {
		/* v1x interfaces */
		.client_connected = pbs_pmix_client_connected,
		.client_finalized = pbs_pmix_client_finalized,
		.abort = pbs_pmix_abort,
		.fence_nb = pbs_pmix_fence_nb,
		.direct_modex = pbs_pmix_direct_modex,
		.publish = pbs_pmix_publish,
		.lookup = pbs_pmix_lookup,
		.unpublish = pbs_pmix_unpublish,
		.spawn = pbs_pmix_spawn,
		.connect = pbs_pmix_connect,
		.disconnect = pbs_pmix_disconnect,
		.register_events = pbs_pmix_register_events,
		.deregister_events = pbs_pmix_deregister_events,
		.listener = NULL
#if PMIX_VERSION_MAJOR > 1
		,
		/* v2x interfaces */
		.notify_event = NULL,
		.query = NULL,
		.tool_connected = NULL,
		.log = NULL,
		.allocate = NULL,
		.job_control = NULL,
		.monitor = NULL
#endif
#if PMIX_VERSION_MAJOR > 2
		,
		/* v3x interfaces */
		.get_credential = NULL,
		.validate_credential = NULL,
		.iof_pull = NULL,
		.push_stdin = NULL
#endif
#if PMIX_VERSION_MAJOR > 3
		,
		/* v4x interfaces */
		.group = NULL
#endif
	};

	pstat = PMIx_server_init(&pbs_pmix_server_module, NULL, 0);
	if (pstat != PMIX_SUCCESS) {
		log_eventf(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER,
			   LOG_ERR, name,
			   "Could not initialize PMIx server: %s",
			   PMIx_Error_string(pstat));
	} else {
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER,
			  LOG_DEBUG, name, "PMIx server initialized");
	}
}

/**
 * @brief
 * Generic callback used to wakeup a locked thread
 *
 * @param[in] status - status of locked thread
 * @cbdata[in] cbdata - callback data (pbs_pmix_lock_t *)
 *
 * @return void
 */
static void
pbs_pmix_wait_cb(pmix_status_t status, void *cbdata)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	if (!cbdata) {
		log_err(-1, __func__, "cbdata may not be NULL, returning");
		return;
	}
	log_eventf(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
		   "Setting thread status to %s", PMIx_Error_string(status));
	((pbs_pmix_lock_t *) cbdata)->status = status;
	PBS_PMIX_WAKEUP_THREAD((pbs_pmix_lock_t *) cbdata);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
}

/**
 * @brief
 * Register the PMIx client and adjust the environment so the child will
 * be able to phone home
 *
 * @param[in] pjob - pointer to job structure
 * @param[in] tvnodeid - the global rank of the task
 * @param[in/out] envpp - environment array to modify
 *
 * @return void
 */
void
pbs_pmix_register_client(job *pjob, int tvnodeid, char ***envpp)
{
	char **ep;
	pmix_status_t pstat;
	pmix_proc_t pproc;
	int before, after;
	pbs_pmix_lock_t pmix_lock;

	if (!pjob) {
		log_err(-1, __func__, "Invalid job pointer");
		return;
	}
	if (!envpp) {
		log_err(-1, __func__, "Invalid environment pointer");
		return;
	}
	/* Register the PMIx client */
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "Registering PMIx client %d", tvnodeid);
	/* Rank is based on tvnodeid */
	PMIX_LOAD_PROCID(&pproc, pjob->ji_qs.ji_jobid, tvnodeid);
	PBS_PMIX_CONSTRUCT_LOCK(&pmix_lock);
	pstat = PMIx_server_register_client(&pproc,
					    pjob->ji_qs.ji_un.ji_momt.ji_exuid,
					    pjob->ji_qs.ji_un.ji_momt.ji_exgid,
					    NULL, pbs_pmix_wait_cb, (void *) &pmix_lock);
	PBS_PMIX_WAIT_THREAD(&pmix_lock);
	PBS_PMIX_DESTRUCT_LOCK(&pmix_lock);
	if (pstat != PMIX_SUCCESS) {
		log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			   pjob->ji_qs.ji_jobid,
			   "Failed to register PMIx client: %s",
			   PMIx_Error_string(pstat));
		return;
	}
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
		   pjob->ji_qs.ji_jobid,
		   "PMIx client %d registered", tvnodeid);
	/* Setup for the PMIx fork */
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "Setting up PMIx fork for client %d", tvnodeid);
	/* Allow PMIx to add required environment variables */
	for (before = 0, ep = *envpp; ep && *ep; before++, ep++) {
	}
	pstat = PMIx_server_setup_fork(&pproc, envpp);
	if (pstat != PMIX_SUCCESS) {
		log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			   pjob->ji_qs.ji_jobid,
			   "Failed to setup PMIx server fork: %s",
			   PMIx_Error_string(pstat));
		return;
	}
	for (after = 0, ep = *envpp; ep && *ep; after++, ep++) {
	}
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
		   pjob->ji_qs.ji_jobid,
		   "PMIx server setup fork added %d env var(s)",
		   (after - before));
	log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
		  pjob->ji_qs.ji_jobid, "PMIx server setup fork complete");
}

/**
 * @brief
 * Calculate the number of characters required to print an integer
 *
 * @param[in] val - interger value
 *
 * @return int
 * @retval length of string to print provided integer
 */
static int
intlen(int val)
{
	int i = 1;

	if (val < 0) {
		i++;
		val *= -1;
	}
	for (; val > 9; i++)
		val /= 10;
	return i;
}

/*
 * @brief
 * Construct a map of the vnodes and ranks that will be provided to PMIx.
 *
 * @param[in] pjob - pointer to job structure
 * @param[out] nodelist - comma separated list of node names
 * @param[out] nodect - number of nodes in list
 * @param[out] nodeid - numeric rank of the local node
 * @param[out] ppnlist - list of ranks on all nodes
 * @param[out] ppnlocal - list of ranks on this node
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - failure
 *
 * @note
 * The node list looks like: host0,host1,...
 * There are no duplicates in the node list
 * The ppn list looks like: 0,100,200;1,101,201;...
 * Order matches that of the node list with same number of entries
 * The ppnlocal list is the list of ranks on the local node
 */
static int
pbs_pmix_gen_map(
	job *pjob,
	char **nodelist,
	uint32_t *nodect,
	uint32_t *nodeid,
	char **ppnlist,
	char **ppnlocal)
{
	typedef struct {
		vmpiprocs *pmpiproc;
		int nextrank;
		int locrank;
	} pbs_pmix_map_t;
	pbs_pmix_map_t *map;
	int i, j, ilen, jlen, nodelen, ppnlen, ppnloclen, msnlen, locrank;
	char *iname, *jname, *pn, *pp, *ploc, *pdot;

	if (nodelist)
		*nodelist = NULL;
	if (nodeid)
		*nodeid = 0;
	if (nodect)
		*nodect = 0;
	if (ppnlist)
		*ppnlist = NULL;
	if (ppnlocal)
		*ppnlocal = NULL;
	if (!nodelist || !nodeid || !nodect || !ppnlist || !ppnlocal)
		return -1;
	if (!pjob)
		return -1;
	if (pjob->ji_numvnod < 1)
		return -1;
	map = calloc(pjob->ji_numvnod, sizeof(pbs_pmix_map_t));
	if (!map)
		return -1;
	for (i = 0; i < pjob->ji_numvnod; i++) {
		map[i].pmpiproc = &pjob->ji_vnods[i];
		map[i].nextrank = -1;
		map[i].locrank = -1;
	}
	msnlen = strlen(mom_short_name);
	/*
	 * The following loop calculates the length of the node and
	 * PPN lists. It also sets up the map array so that it will
	 * be easier to construct the lists.
	 */
	for (nodelen = ppnlen = ppnloclen = i = 0; i < pjob->ji_numvnod; i++) {
		if (map[i].locrank >= 0)
			continue;
		map[i].locrank = locrank = 0;
		iname = map[i].pmpiproc->vn_hname ? map[i].pmpiproc->vn_hname : map[i].pmpiproc->vn_host->hn_host;
		if ((pdot = strchr(iname, '.')) != NULL)
			ilen = pdot - iname;
		else
			ilen = strlen(iname);
		nodelen += ilen + 1;
		ppnlen += intlen(i) + 1;
		if (ilen == msnlen) {
			if (strncmp(mom_short_name, iname, ilen) == 0)
				ppnloclen += intlen(i) + 1;
		}
		/* Add additional ranks on this node */
		for (j = i + 1; j < pjob->ji_numvnod; j++) {
			jname = map[j].pmpiproc->vn_hname ? map[j].pmpiproc->vn_hname : map[j].pmpiproc->vn_host->hn_host;
			if ((pdot = strchr(jname, '.')) != NULL)
				jlen = pdot - jname;
			else
				jlen = strlen(jname);
			if (ilen == jlen) {
				if (strncmp(iname, jname, jlen) == 0) {
					map[i].nextrank = j;
					map[j].locrank = ++locrank;
					ppnlen += intlen(j) + 1;
					if (jlen == msnlen) {
						if (strncmp(mom_short_name, jname, jlen) == 0) {
							ppnloclen += intlen(map[j].locrank) + 1;
						}
					}
				}
			}
		}
	}
	/* Perform some sanity checks */
	if (nodelen < 1) {
		log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			   pjob->ji_qs.ji_jobid,
			   "%s: zero length node list", __func__);
		free(map);
		return -1;
	}
	if (ppnlen < 1) {
		log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			   pjob->ji_qs.ji_jobid,
			   "%s: zero length ppn list", __func__);
		free(map);
		return -1;
	}
	if (ppnloclen < 1) {
		log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			   pjob->ji_qs.ji_jobid,
			   "%s: zero length local ppn list", __func__);
		free(map);
		return -1;
	}
	/* Allocate the memory for the lists themselves */
	*nodelist = malloc(nodelen);
	if (!*nodelist) {
		free(map);
		return -1;
	}
	*ppnlist = malloc(ppnlen);
	if (!*ppnlist) {
		free(map);
		free(*nodelist);
		*nodelist = NULL;
		return -1;
	}
	*ppnlocal = malloc(ppnloclen);
	if (!*ppnlocal) {
		free(map);
		free(*nodelist);
		*nodelist = NULL;
		free(*ppnlist);
		*ppnlist = NULL;
		return -1;
	}
	/* Construct the node and PPN lists using the map array */
	pn = *nodelist;
	*pn = '\0';
	pp = *ppnlist;
	*pp = '\0';
	ploc = *ppnlocal;
	*ploc = '\0';
	for (i = 0, j = 0; i < pjob->ji_numvnod; i++) {
		bool localnode;
		int next;

		if (map[i].locrank != 0)
			continue;
		iname = map[i].pmpiproc->vn_hname ? map[i].pmpiproc->vn_hname : map[i].pmpiproc->vn_host->hn_host;
		if ((pdot = strchr(iname, '.')) != NULL)
			ilen = pdot - iname;
		else
			ilen = strlen(iname);
		/* Append to the node list */
		if (pn != *nodelist) {
			sprintf(pn, ",");
			pn++;
		}
		snprintf(pn, ilen + 1, "%s", iname);
		pn += ilen;
		(*nodect)++;
		/* Determine if this rank is on the local node */
		localnode = false;
		if (ilen == msnlen) {
			if (strncmp(mom_short_name, iname, ilen) == 0)
				localnode = true;
		}
		if (localnode)
			*nodeid = j;
		/* Append to the PPN and local PPN lists */
		if (pp != *ppnlist) {
			sprintf(pp, ";");
			pp++;
		}
		sprintf(pp, "%d", i);
		pp += intlen(i);
		if (localnode) {
			sprintf(ploc, "%d", i);
			ploc += intlen(i);
		}
		for (next = map[i].nextrank; next >= 0; next = map[next].nextrank) {
			sprintf(pp, ",%d", next);
			pp += intlen(next) + 1;
			if (localnode) {
				sprintf(ploc, ",%d", next);
				ploc += intlen(next) + 1;
			}
		}
		j++;
	}
	free(map);
	return 0;
}

/**
 * @brief
 * Register the PMIx namespace on the local node
 *
 * @param[in] pjob - pointer to job structure
 *
 * @return void
 *
 * @note
 * Populate a PMIx info array and pass it to PMIx_server_register_nspace().
 * This function relies on pbs_pmix_gen_map() to construct the data in the
 * info array.
 */
static void
pbs_pmix_register_namespace(job *pjob)
{
	pmix_info_t *pinfo;
	pmix_status_t pstat;
	pmix_rank_t rank;
	pbs_pmix_lock_t pmix_lock;
	char *pmix_node_list = NULL;
	char *pmix_ppn_list = NULL;
	char *pmix_ppn_local = NULL;
	char *pmix_node_regex;
	char *pmix_ppn_regex;
	int loc_size;
	int msnlen;
	int rc;
	int i, n, ninfo;
	uint32_t ui, pmix_node_ct, pmix_node_idx;

	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	if (!pjob) {
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_ERR,
			  NULL, "Invalid job pointer");
		return;
	}
	rc = pbs_pmix_gen_map(pjob, &pmix_node_list,
			      &pmix_node_ct, &pmix_node_idx,
			      &pmix_ppn_list, &pmix_ppn_local);
	if (rc != 0) {
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_ERR,
			  pjob->ji_qs.ji_jobid,
			  "Failed to generate PMIx mapping");
		return;
	}
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "PMIX nodes: %s", pmix_node_list);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "PMIX ppn: %s", pmix_ppn_list);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "PMIX local ppn: %s", pmix_ppn_local);
	/* Generate the regex */
	PMIx_generate_regex(pmix_node_list, &pmix_node_regex);
	PMIx_generate_ppn(pmix_ppn_list, &pmix_ppn_regex);
	msnlen = strlen(mom_short_name);
	/* Count the number of ranks assigned to this node */
	for (loc_size = i = 0; i < pjob->ji_numvnod; i++) {
		char *pdot, *hname;
		int hlen;

		hname = pjob->ji_vnods[i].vn_hname ? pjob->ji_vnods[i].vn_hname : pjob->ji_vnods[i].vn_host->hn_host;
		if (!hname || (*hname == '\0'))
			continue;
		pdot = strchr(hname, '.');
		if (pdot)
			hlen = pdot - hname;
		else
			hlen = strlen(hname);
		if (hlen != msnlen)
			continue;
		if (strncmp(mom_short_name, hname, hlen) != 0)
			continue;
		loc_size++;
	}
	free(pmix_node_list);
	pmix_node_list = NULL;
	free(pmix_ppn_list);
	pmix_ppn_list = NULL;
	ninfo = 14;
	PMIX_INFO_CREATE(pinfo, ninfo);
	n = 0;
	/*
	 * INFO #1: Universe size
	 */
	ui = pjob->ji_numvnod;
	/*
	 * Do not increment n in the PMIX_INFO_LOAD macro call!
	 * The macro references the first parameter multiple
	 * times and would thereby increment it multiple times.
	 */
	PMIX_INFO_LOAD(&pinfo[n], PMIX_UNIV_SIZE, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_UNIV_SIZE: %u", ++n, ui);
	/*
	 * INFO #2: Maximum number of processes the user is allowed
	 * to start within this allocation - usually the same as
	 * univ_size
	 */
	ui = pjob->ji_numvnod;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_MAX_PROCS, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_MAX_PROCS: %u", ++n, ui);
	/*
	 * INFO #3: Number of processess being spawned in this job
	 * Note that job refers to a PMIx job (i.e. application)
	 * Note that this again is a value PMIx could compute from
	 * the proc_map
	 */
	ui = pjob->ji_numvnod;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_JOB_SIZE, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_JOB_SIZE: %u", ++n, ui);
	/*
	 * INFO #4: Node map
	 */
	PMIX_INFO_LOAD(&pinfo[n], PMIX_NODE_MAP, pmix_node_regex, PMIX_STRING);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_NODE_MAP: %s", ++n, pmix_node_regex);
	/*
	 * INFO #5: Process map
	 */
	PMIX_INFO_LOAD(&pinfo[n], PMIX_PROC_MAP, pmix_ppn_regex, PMIX_STRING);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_PROC_MAP: %s", ++n, pmix_ppn_regex);
	/*
	 * INFO #6: This process was not created by PMIx_Spawn()
	 */
	ui = 0;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_SPAWNED, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_SPAWNED: %u", ++n, ui);
	/*
	 * INFO #7: Number of local ranks for this application
	 * Note: This could be smaller than the nnumber allocated
	 *       if the application is not utilizing them all.
	 */
	ui = loc_size;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_LOCAL_SIZE, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_LOCAL_SIZE: %u", ++n, ui);
	/*
	 * INFO #8: Number of local ranks for this allocation
	 */
	ui = loc_size;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_NODE_SIZE, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_NODE_SIZE: %u", ++n, ui);
	/*
	 * INFO #9: Number of ranks for the entire job
	 */
	ui = pmix_node_ct;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_NUM_NODES, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_NUM_NODES: %u", ++n, ui);
	/*
	 * INFO #10: Comma delimited list of ranks on local node
	 */
	PMIX_INFO_LOAD(&pinfo[n], PMIX_LOCAL_PEERS, pmix_ppn_local, PMIX_STRING);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_LOCAL_PEERS: %s", ++n, pmix_ppn_local);
	/*
	 * INFO #11: Process leader on local node (first rank)
	 */
	if (sscanf(pmix_ppn_local, "%u", &rank) != 1) {
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			  pjob->ji_qs.ji_jobid,
			  "Invalid rank in local ppn list");
		/* Punt and set it to zero */
		rank = 0;
	}
	PMIX_INFO_LOAD(&pinfo[n], PMIX_LOCALLDR, &rank, PMIX_PROC_RANK);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_LOCALLDR: %u", ++n, rank);
	free(pmix_ppn_local);
	pmix_ppn_local = NULL;
	/*
	 * INFO #12: Index of the local node in the node map
	 */
	ui = pmix_node_idx;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_NODEID, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_NODEID: %u", ++n, ui);
	/*
	 * INFO #13: The job ID string
	 */
	PMIX_INFO_LOAD(&pinfo[n], PMIX_JOBID, pjob->ji_qs.ji_jobid, PMIX_STRING);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_JOBID: %s", ++n, pjob->ji_qs.ji_jobid);
	/*
	 * INFO #14: Number of different executables in this PMIx job
	 */
	ui = 1;
	PMIX_INFO_LOAD(&pinfo[n], PMIX_JOB_NUM_APPS, &ui, PMIX_UINT32);
	log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		   pjob->ji_qs.ji_jobid,
		   "%d. PMIX_JOB_NUM_APPS: %u", ++n, ui);
	/* Grab the lock and register the PMIx namespace */
	PBS_PMIX_CONSTRUCT_LOCK(&pmix_lock);
	log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, "Registering PMIx namespace");
	pstat = PMIx_server_register_nspace(pjob->ji_qs.ji_jobid, loc_size,
					    pinfo, ninfo, pbs_pmix_wait_cb, (void *) &pmix_lock);
	PBS_PMIX_WAIT_THREAD(&pmix_lock);
	PBS_PMIX_DESTRUCT_LOCK(&pmix_lock);
	PMIX_INFO_FREE(pinfo, ninfo);
	if (pstat != PMIX_SUCCESS) {
		log_eventf(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			   pjob->ji_qs.ji_jobid,
			   "Failed to register PMIx namespace: %s",
			   PMIx_Error_string(pstat));
	} else {
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
			  pjob->ji_qs.ji_jobid, "PMIx namespace registered");
	}
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
}

/*
 * @brief
 * Deregister the PMIx namespace for a job on the local node
 *
 * @param[in] pjob - pointer to job structure
 *
 * @return void
 */
static void
pbs_pmix_deregister_namespace(job *pjob)
{
	pbs_pmix_lock_t pmix_lock;

	/* Grab the lock and deregister the PMIx namespace */
	PBS_PMIX_CONSTRUCT_LOCK(&pmix_lock);
	log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, "Deregistering PMIx namespace");
	PMIx_server_deregister_nspace(pjob->ji_qs.ji_jobid,
				      pbs_pmix_wait_cb, (void *) &pmix_lock);
	PBS_PMIX_WAIT_THREAD(&pmix_lock);
	PBS_PMIX_DESTRUCT_LOCK(&pmix_lock);
}

/*
 * @brief
 * Extra processing required when spawning a TM task with PMIx enabled
 *
 * @param[in] pjob - pointer to job structure
 * @param[in] pnode - pointer to node entry for local node
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - failure
 */
int
pbs_pmix_job_join_extra(job *pjob, hnodent *pnode)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	pbs_pmix_register_namespace(pjob);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return 0;
}

/*
 * @brief
 * Extra processing required when reaping a TM task with PMIx enabled
 *
 * @param[in] pjob - pointer to job structure
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - failure
 */
int
pbs_pmix_job_clean_extra(job *pjob)
{
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "called");
	pbs_pmix_deregister_namespace(pjob);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, "returning");
	return 0;
}

#endif /* PMIX */

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
 * @file    req_rerun.c
 *
 * @brief
 * 		req_rerun.c - functions dealing with a Rerun Job Request
 *
 * Included functions are:
 * 	post_rerun()
 * 	force_reque()
 * 	req_rerunjob()
 * 	timeout_rerun_request()
 * 	req_rerunjob2()
 *
 */

#include <pbs_config.h> /* the master config generated by configure */

#include <stdio.h>
#include <sys/types.h>
#include "libpbs.h"
#include <signal.h>
#include "server_limits.h"
#include "list_link.h"
#include "work_task.h"
#include "attribute.h"
#include "server.h"
#include "credential.h"
#include "batch_request.h"
#include "job.h"
#include "pbs_error.h"
#include "log.h"
#include "acct.h"
#include "pbs_nodes.h"
#include "svrfunc.h"
#include "net_connect.h"

/* Private Function local to this file */
static int req_rerunjob2(struct batch_request *preq, job *pjob);

/* Global Data Items: */

extern char *msg_manager;
extern char *msg_jobrerun;
extern time_t time_now;
extern job *chk_job_request(char *, struct batch_request *, int *, int *);

/**
 * @brief
 * 		post_rerun - handler for reply from mom on signal_job sent in req_rerunjob
 *		If mom acknowledged the signal, then all is ok.
 *		If mom rejected the signal for unknown jobid, and force is set by the
 *		original client for a non manager as indicated by the preq->rq_extra being zero,
 *		then do local requeue.
 *
 * @param[in]	pwt	-	work task structure which contains the reply from mom
 */

void
post_rerun(struct work_task *pwt)
{
	job *pjob;
	struct batch_request *preq;
	struct depend *pdep;

	preq = (struct batch_request *) pwt->wt_parm1;

	pjob = find_job(preq->rq_ind.rq_signal.rq_jid);

	if (pjob != NULL) {
		if (preq->rq_reply.brp_code != 0) {
			sprintf(log_buffer, "rerun signal reject by mom: %d",
				preq->rq_reply.brp_code);
			log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
				  preq->rq_ind.rq_signal.rq_jid, log_buffer);

			if (pjob->ji_pmt_preq != NULL)
				reply_preempt_jobs_request(preq->rq_reply.brp_code, PREEMPT_METHOD_REQUEUE, pjob);
		} else {
			/* mom acknowledged to rerun the job, release depend hold on run-one dependency */
			pdep = find_depend(JOB_DEPEND_TYPE_RUNONE, get_jattr(pjob, JOB_ATR_depend));
			if (pdep != NULL)
				depend_runone_release_all(pjob);
		}
	}

	release_req(pwt);
	return;
}

/**
 * @brief
 * 		force_reque - requeue (rerun) a job
 *
 * @param[in,out]	pwt	-	job which needs to be rerun
 */
void
force_reque(job *pjob)
{
	char newstate;
	int newsubstate;
	struct batch_request *preq;
	char hook_msg[HOOK_MSG_SIZE] = {0};
	int rc;

	pjob->ji_qs.ji_obittime = time_now;
	set_jattr_l_slim(pjob, JOB_ATR_obittime, pjob->ji_qs.ji_obittime, SET);

	/* Allocate space for the jobobit hook event params */
	preq = alloc_br(PBS_BATCH_JobObit);
	if (preq == NULL) {
		log_err(PBSE_INTERNAL, __func__, "rq_jobobit alloc failed");
	} else {
		preq->rq_ind.rq_obit.rq_pjob = pjob;
		rc = process_hooks(preq, hook_msg, sizeof(hook_msg), pbs_python_set_interrupt);
		if (rc == -1) {
			log_err(-1, __func__, "rq_jobobit force_reque process_hooks call failed");
		}
		free_br(preq);
	}

	pjob->ji_momhandle = -1;
	pjob->ji_mom_prot = PROT_INVALID;

	if ((is_jattr_set(pjob, JOB_ATR_resc_released))) {
		/* If JOB_ATR_resc_released attribute is set and we are trying to rerun a job
		 * then we need to reassign resources first because
		 * when we suspend a job we don't decrement all the resources.
		 * So we need to set partially released resources
		 * back again to release all other resources
		 */
		set_resc_assigned(pjob, 0, INCR);
		free_jattr(pjob, JOB_ATR_resc_released);
		mark_jattr_not_set(pjob, JOB_ATR_resc_released);
		if (is_jattr_set(pjob, JOB_ATR_resc_released_list)) {
			free_jattr(pjob, JOB_ATR_resc_released_list);
			mark_jattr_not_set(pjob, JOB_ATR_resc_released_list);
		}
	}

	/* simulate rerun: free nodes, clear checkpoint flag, and */
	/* clear exec_vnode string				  */

	rel_resc(pjob);

	/* note in accounting file */
	account_jobend(pjob, pjob->ji_acctrec, PBS_ACCT_RERUN);

	/*
	 * Clear any JOB_SVFLG_Actsuspd flag too, as the job is no longer
	 * suspended (User busy).  A suspended job is rerun in case of a
	 * MOM failure after the workstation becomes active(busy).
	 */
	pjob->ji_qs.ji_svrflags &= ~(JOB_SVFLG_Actsuspd | JOB_SVFLG_StagedIn | JOB_SVFLG_CHKPT);
	free_jattr(pjob, JOB_ATR_exec_host);
	free_jattr(pjob, JOB_ATR_exec_host2);
	free_jattr(pjob, JOB_ATR_exec_vnode);
	/* job dir has no meaning for re-queued jobs, so unset it */
	free_jattr(pjob, JOB_ATR_jobdir);
	unset_extra_attributes(pjob);
	svr_evaljobstate(pjob, &newstate, &newsubstate, 1);
	svr_setjobstate(pjob, newstate, newsubstate);
}

/**
 * @brief
 * 		req_rerunjob - service the Rerun Job Request
 *
 *		This request Reruns a job by:
 *		sending to MOM a signal job request with SIGKILL
 *		marking the job as being rerun by setting the substate.
 *
 *  @param[in,out]	preq	-	Job Request
 */

void
req_rerunjob(struct batch_request *preq)
{
	int anygood = 0;
	int i;
	char jid[PBS_MAXSVRJOBID + 1];
	int jt; /* job type */
	char sjst;
	char *pc;
	job *pjob;
	job *parent;
	char *range;
	int start;
	int end;
	int step;
	int count;
	int err = PBSE_NONE;

	snprintf(jid, sizeof(jid), "%s", preq->rq_ind.rq_signal.rq_jid);
	parent = chk_job_request(jid, preq, &jt, &err);
	if (parent == NULL) {
		pjob = find_job(jid);
		if (pjob != NULL && pjob->ji_pmt_preq != NULL)
			reply_preempt_jobs_request(err, PREEMPT_METHOD_REQUEUE, pjob);
		return; /* note, req_reject already called */
	}

	if ((preq->rq_perm & (ATR_DFLAG_MGWR | ATR_DFLAG_OPWR)) == 0) {
		if (parent->ji_pmt_preq != NULL)
			reply_preempt_jobs_request(PBSE_BADSTATE, PREEMPT_METHOD_REQUEUE, parent);
		req_reject(PBSE_PERM, 0, preq);
		return;
	}

	if (jt == IS_ARRAY_NO) {

		/* just a regular job, pass it on down the line and be done */

		req_rerunjob2(preq, parent);
		return;

	} else if (jt == IS_ARRAY_Single) {
		/* single subjob, if running can signal */
		pjob = get_subjob_and_state(parent, get_index_from_jid(jid), &sjst, NULL);
		if (sjst == JOB_STATE_LTR_UNKNOWN) {
			req_reject(PBSE_IVALREQ, 0, preq);
			return;
		} else if (pjob && sjst == JOB_STATE_LTR_RUNNING) {
			req_rerunjob2(preq, pjob);
		} else {
			req_reject(PBSE_BADSTATE, 0, preq);
			return;
		}
		return;

	} else if (jt == IS_ARRAY_ArrayJob) {

		/* The Array Job itself ... */

		if (!check_job_state(parent, JOB_STATE_LTR_BEGUN)) {
			if (parent->ji_pmt_preq != NULL)
				reply_preempt_jobs_request(PBSE_BADSTATE, PREEMPT_METHOD_REQUEUE, parent);
			req_reject(PBSE_BADSTATE, 0, preq);
			return;
		}

		/* for each subjob that is running, call req_rerunjob2 */

		++preq->rq_refct; /* protect the request/reply struct */

		/* Setting deleted subjobs count to 0,
		 * since all the deleted subjobs will be moved to Q state
		 */
		parent->ji_ajinfo->tkm_dsubjsct = 0;

		for (i = parent->ji_ajinfo->tkm_start; i <= parent->ji_ajinfo->tkm_end; i += parent->ji_ajinfo->tkm_step) {
			pjob = get_subjob_and_state(parent, i, &sjst, NULL);
			if (sjst == JOB_STATE_LTR_UNKNOWN)
				continue;
			if (pjob) {
				if (sjst == JOB_STATE_LTR_RUNNING)
					dup_br_for_subjob(preq, pjob, req_rerunjob2);
				else
					force_reque(pjob);
			} else {
				update_sj_parent(parent, NULL, create_subjob_id(parent->ji_qs.ji_jobid, i), sjst, JOB_STATE_LTR_QUEUED);
			}
		}
		/* if not waiting on any running subjobs, can reply; else */
		/* it is taken care of when last running subjob responds  */
		if (--preq->rq_refct == 0)
			reply_send(preq);
		return;
	}
	/* what's left to handle is a range of subjobs, foreach subjob
	 * if running, all req_rerunjob2
	 */

	range = get_range_from_jid(jid);
	if (range == NULL) {
		req_reject(PBSE_IVALREQ, 0, preq);
		return;
	}

	/* now do the deed */

	++preq->rq_refct; /* protect the request/reply struct */

	while (1) {
		if ((i = parse_subjob_index(range, &pc, &start, &end, &step, &count)) == -1) {
			req_reject(PBSE_IVALREQ, 0, preq);
			break;
		} else if (i == 1)
			break;
		for (i = start; i <= end; i += step) {
			pjob = get_subjob_and_state(parent, i, &sjst, NULL);
			if (pjob && sjst == JOB_STATE_LTR_RUNNING) {
				anygood++;
				dup_br_for_subjob(preq, pjob, req_rerunjob2);
			}
		}
		range = pc;
	}

	if (anygood == 0) {
		preq->rq_refct--;
		req_reject(PBSE_BADSTATE, 0, preq);
		return;
	}

	/* if not waiting on any running subjobs, can reply; else */
	/* it is taken care of when last running subjob responds  */
	if (--preq->rq_refct == 0)
		reply_send(preq);
	return;
}

/**
 * @brief
 * 		Function that causes a rerun request to return with a timeout message.
 *
 * @param[in,out]	pwt	-	work task which contains the job structure which holds the rerun request
 */
static void
timeout_rerun_request(struct work_task *pwt)
{
	job *pjob = (job *) pwt->wt_parm1;
	conn_t *conn = NULL;

	if ((pjob == NULL) || (pjob->ji_rerun_preq == NULL)) {
		return; /* nothing to timeout */
	}
	if (pjob->ji_rerun_preq->rq_conn != PBS_LOCAL_CONNECTION) {
		conn = get_conn(pjob->ji_rerun_preq->rq_conn);
	}
	reply_text(pjob->ji_rerun_preq, PBSE_INTERNAL,
		   "Response timed out. Job rerun request still in progress for");

	/* clear no-timeout flag on connection */
	if (conn)
		conn->cn_authen &= ~PBS_NET_CONN_NOTIMEOUT;

	pjob->ji_rerun_preq = NULL;
}
/**
 * @brief
 * 		req_rerunjob - service the Rerun Job Request
 *
 *  @param[in,out]	preq	-	Job Request
 *  @param[in,out]	pjob	-	ptr to the subjob
 *
 * @return int
 * @retval 0 for Success
 * @retval 1 for Error
 */
static int
req_rerunjob2(struct batch_request *preq, job *pjob)
{
	long force = 0;
	struct work_task *ptask;
	time_t rerun_to;
	conn_t *conn;
	struct depend *pdep;
	int rc;

	if (preq->rq_extend && (strcmp(preq->rq_extend, "force") == 0))
		force = 1;

	/* the job must be rerunnable or force must be on */

	if ((get_jattr_long(pjob, JOB_ATR_rerunable) == 0) &&
	    (force == 0)) {
		if (pjob->ji_pmt_preq != NULL)
			reply_preempt_jobs_request(PBSE_NORERUN, PREEMPT_METHOD_REQUEUE, pjob);
		req_reject(PBSE_NORERUN, 0, preq);
		return 1;
	}

	/* the job must be running */

	if (!check_job_state(pjob, JOB_STATE_LTR_RUNNING)) {
		if (pjob->ji_pmt_preq != NULL)
			reply_preempt_jobs_request(PBSE_BADSTATE, PREEMPT_METHOD_REQUEUE, pjob);

		req_reject(PBSE_BADSTATE, 0, preq);
		return 1;
	}
	/* a node failure tolerant job could be waiting for healthy nodes
	 * and it would have a JOB_SUBSTATE_PRERUN substate.
	 */
	if ((!check_job_substate(pjob, JOB_SUBSTATE_RUNNING)) &&
	    (!check_job_substate(pjob, JOB_SUBSTATE_PRERUN)) && (force == 0)) {
		if (pjob->ji_pmt_preq != NULL)
			reply_preempt_jobs_request(PBSE_BADSTATE, PREEMPT_METHOD_REQUEUE, pjob);
		req_reject(PBSE_BADSTATE, 0, preq);
		return 1;
	}

	/* ask MOM to kill off the job */

	rc = issue_signal(pjob, SIG_RERUN, post_rerun, NULL);

	/*
	 * If force is set and request is from a PBS manager,
	 * job is re-queued regardless of issue_signal to MoM
	 * was a success or failure.
	 * Eventually, when the mom updates server about the job,
	 * server sends a discard message to mom and job is
	 * then deleted from mom as well.
	 */
	if (force == 1) {
		/* Mom is down and issue signal failed or
		 * request is from a manager and "force" is on,
		 * force the requeue */
		if (pjob->ji_pmt_preq != NULL)
			reply_preempt_jobs_request(rc, PREEMPT_METHOD_REQUEUE, pjob);

		pjob->ji_qs.ji_un.ji_exect.ji_exitstat = JOB_EXEC_RERUN;
		set_job_substate(pjob, JOB_SUBSTATE_RERUN3);

		discard_job(pjob, "Force rerun", 0);
		pjob->ji_discarding = 1;
		/**
		 * force_reque will be called in post_discard_job,
		 * after receiving IS_DISCARD_DONE from the MOM.
		 */
		pdep = find_depend(JOB_DEPEND_TYPE_RUNONE, get_jattr(pjob, JOB_ATR_depend));
		if (pdep != NULL)
			depend_runone_release_all(pjob);
		reply_ack(preq);
		return 0;
	}

	if (rc != 0) {
		if (pjob->ji_pmt_preq != NULL)
			reply_preempt_jobs_request(rc, PREEMPT_METHOD_REQUEUE, pjob);
		req_reject(rc, 0, preq);
		return 1;
	}

	/* So job has run and is to be rerun (not restarted) */

	pjob->ji_qs.ji_svrflags = (pjob->ji_qs.ji_svrflags &
				   ~(JOB_SVFLG_CHKPT | JOB_SVFLG_ChkptMig)) |
				  JOB_SVFLG_HASRUN;
	svr_setjobstate(pjob, JOB_STATE_LTR_RUNNING, JOB_SUBSTATE_RERUN);

	sprintf(log_buffer, msg_manager, msg_jobrerun,
		preq->rq_user, preq->rq_host);
	log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO,
		  pjob->ji_qs.ji_jobid, log_buffer);

	/* The following means we've detected an outstanding rerun request  */
	/* for the same job which should not happen. But if it does, let's  */
	/* ack that previous request to also free up its request structure. */
	if (pjob->ji_rerun_preq != NULL) {
		reply_ack(pjob->ji_rerun_preq);
	}
	pjob->ji_rerun_preq = preq;

	/* put a timeout on the rerun request so that it doesn't hang 	*/
	/* indefinitely; if it does, the scheduler would also hang on a */
	/* requeue request  */
	time_now = time(NULL);
	if (!is_sattr_set(SVR_ATR_JobRequeTimeout))
		rerun_to = time_now + PBS_DIS_TCP_TIMEOUT_RERUN;
	else
		rerun_to = time_now + get_sattr_long(SVR_ATR_JobRequeTimeout);
	ptask = set_task(WORK_Timed, rerun_to, timeout_rerun_request, pjob);
	if (ptask) {
		/* this ensures that the ptask created gets cleared in case */
		/* pjob gets deleted before the task is served */
		append_link(&pjob->ji_svrtask, &ptask->wt_linkobj, ptask);
	}

	/* set no-timeout flag on connection to client */
	if (preq->rq_conn != PBS_LOCAL_CONNECTION) {
		conn = get_conn(preq->rq_conn);
		if (conn)
			conn->cn_authen |= PBS_NET_CONN_NOTIMEOUT;
	}

	return 0;
}

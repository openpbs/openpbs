/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */
/**
 * @file	req_select.c
 *
 * @brief
 * 		req_select.c - Functions relating to the Select Job Batch Request and the Select-Status
 * 		(SelStat) Batch Request.
 *
 * Included functions are:
 * 	order_chkpnt()
 * 	comp_chkpnt()
 * 	comp_state()
 * 	chk_job_statenum()
 * 	add_select_entry()
 * 	add_select_array_entries()
 * 	req_selectjobs()
 * 	select_job()
 * 	sel_attr()
 * 	free_sellist()
 * 	build_selentry()
 * 	build_selist()
 * 	select_subjob()
 */

#include <pbs_config.h>   /* the master config generated by configure */

#define STAT_CNTL 1

#include <sys/types.h>
#include <stdlib.h>
#include "libpbs.h"
#include <string.h>
#include "server_limits.h"
#include "list_link.h"
#include "attribute.h"
#include "resource.h"
#include "server.h"
#include "credential.h"
#include "batch_request.h"
#include "job.h"
#include "reservation.h"
#include "queue.h"
#include "pbs_error.h"
#include "log.h"
#include "pbs_nodes.h"
#include "svrfunc.h"


/* Private Data */

/* Global Data Items  */

extern int	 resc_access_perm;
extern pbs_list_head svr_alljobs;
extern time_t	 time_now;
extern char	 statechars[];
extern long svr_history_enable;
extern int scheduler_jobs_stat;

/* Private Functions  */

static int
build_selist(svrattrl *, int perm, struct  select_list **,
	pbs_queue **, int *bad, char **pstate);
static void free_sellist(struct select_list *pslist);
static int  sel_attr(attribute *, struct select_list *);
static int  select_job(job *, struct select_list *, int, int);
static int  select_subjob(int, struct select_list *);


/**
 * @brief
 * 		order_chkpnt - provide order value for various checkpoint attribute values
 *		n > s > c=minutes > c
 *
 * @param[in]	attr	-	attribute structure
 *
 * @return	order value
 * @retval	0	: no match
 * @retval	!0	: value according to the checkpoints
 */

static int
order_chkpnt(attribute *attr)
{
	if (((attr->at_flags & ATR_VFLAG_SET) == 0) ||
		(attr->at_val.at_str == 0))
		return 0;

	switch (*attr->at_val.at_str) {
		case 'n':	return 5;
		case 's':	return 4;
		case 'c':	if (*(attr->at_val.at_str+1) != '\0')
				return 3;
			else
				return 2;
		case 'u':	return 1;
		default:	return 0;
	}
}

/**
 * @brief
 * 		comp_chkpnt - compare two checkpoint attributes for selection
 *
 * @param[in]	attr	-	attribute structure to compare
 * @param[in]	with	-	attribute structure to compare with
 *
 * @return	int
 * @retval	0	: same
 * @retval	1	: attr > with
 * @retval	-1	: attr < with
 */

int
comp_chkpnt(attribute *attr, attribute *with)
{
	int a;
	int w;

	a = order_chkpnt(attr);
	w = order_chkpnt(with);

	if (a == w)
		return 0;
	else if (a > w)
		return 1;
	else
		return -1;
}

/**
 * @brief
 * 		comp_state - compare the state of a job attribute (state) with that in
 *		a select list (multiple state letters)
 *
 * @param[in]	state	-	state of a job attribute
 * @param[in]	selstate	-	select list (multiple state letters)
 *
 * @return	int
 * @retval	0	: match found
 * @retval	1	: no match
 * @retval	-1	: either state or selstate fields are empty
 */
static int
comp_state(attribute *state, attribute *selstate)
{
	char *ps;

	if (!state || !selstate || !selstate->at_val.at_str)
		return (-1);

	for (ps = selstate->at_val.at_str; *ps; ++ps) {
		if (*ps == state->at_val.at_char)
			return (0);
	}
	return (1);
}

static attribute_def state_sel = {
	ATTR_state,
	decode_str,
	encode_str,
	set_str,
	comp_state,
	free_str,
	NULL_FUNC,
	READ_ONLY,
	ATR_TYPE_STR,
	PARENT_TYPE_JOB
};

/**
 * @brief
 * 		chk_job_statenum - check the state of a job (actual numeric state) with
 * 		a list of state letters
 *
 * @param[in]	istat	-	state of a job (actual numeric state)
 * @param[in]	statelist	-	list of state letters
 *
 * @return	int
 * @retval	0	: no match
 * @retval	1	: match found
 */
static int
chk_job_statenum(int istat, char *statelist)
{


	if (statelist == NULL)
		return 1;
	if (istat >= 0 || istat <= 9)
		if (strchr(statelist, (int)(statechars[istat])))
			return 1;
	return 0;
}

/**
 * @brief
 * 		add_select_entry - add one jobid entry to the select return
 *
 * @param[in]	jid	-	jobid entry
 * @param[in,out]	pselx	-	select return
 *
 * @return	int
 * @retval	0	: error and not added
 * @retval	1	: added
 */
static int
add_select_entry(char *jid, struct brp_select ***pselx)
{
	struct brp_select *pselect;

	pselect = (struct brp_select *)malloc(sizeof(struct brp_select));
	if (pselect == (struct brp_select *)0)
		return 0;

	pselect->brp_next = (struct brp_select *)0;
	(void)strcpy(pselect->brp_jobid, jid);
	**pselx = pselect;
	*pselx = &pselect->brp_next;
	return 1;
}

/**
 * @brief
 * 		add_select_array_entries - add one jobid entry to the select return
 *		for each subjob whose state matches
 *
 * @param[in]	pjob	-	pointer to job
 * @param[in]	dosub	-	treat as a normal job or array job
 * @param[in]	statelist	-	If statelist is NULL, then no need to check anything,
 * 								just add the subjobs to the return list.
 * @param[in,out]	pselx	-	select return
 * @param[in]	pjob	-	pointer to select list
 *
 * @return	int
 * @retval	0	: error and not added
 * @retval	>0	: no. of entries added
 */
static int
add_select_array_entries(job *pjob, int dosub, char *statelist,
	struct brp_select ***pselx,
	struct select_list *psel)
{
	int	 ct = 0;
	int	 i;

	if (pjob->ji_qs.ji_svrflags & JOB_SVFLG_SubJob)
		return 0;
	else if ((dosub == 0) ||
		(pjob->ji_qs.ji_svrflags & JOB_SVFLG_ArrayJob) == 0) {
		/* is or treat as a normal job */
		ct = add_select_entry(pjob->ji_qs.ji_jobid, pselx);
	} else {
		/* Array Job */
		for (i=0; i < pjob->ji_ajtrk->tkm_ct; ++i) {
			/*
			 * If statelist is NULL, then no need to check anything,
			 * just add the subjobs to the return list.
			 */
			if ((statelist == NULL) ||
				(select_subjob(pjob->ji_ajtrk->tkm_tbl[i].trk_status, psel))) {
				ct += add_select_entry(mk_subjob_id(pjob, i), pselx);
			}
		}
	}

	return ct;
}

/**
 * @brief
 * 		req_selectjobs - service both the Select Job Request and the (special
 *		for the scheduler) Select-status Job Request
 *
 *		This request selects jobs based on a supplied criteria and returns
 *		Select   - a list of the job identifiers which meet the criteria
 *		Sel_stat - a list of the status of the jobs that meet the criteria
 *		   and only the list of specified attributes if specified
 *
 * @param[in,out]	preq	-	Select Job Request or Select-status Job Request
 */

void
req_selectjobs(struct batch_request *preq)
{
	int		    bad = 0;
	int		    i;
	job		   *pjob;
	svrattrl	   *plist;
	pbs_queue	   *pque;
	struct batch_reply *preply;
	struct brp_select **pselx;
	int		    dosubjobs = 0;
	int		    dohistjobs = 0;
	char		   *pstate = NULL;
	int		    rc;
	struct select_list *selistp;

	/*
	 * if the letter T (or t) is in the extend string,  select subjobs
	 * if the letter S is in the extend string,  select real jobs,
	 * regualar and running subjobs (whatever has a job structure.  This
	 * is for the Scheduler.
	 */
	if ((preq->rq_extend != NULL) && strchr(preq->rq_extend, 'T'))
		dosubjobs = 1;
	else if ((preq->rq_extend != NULL) && strchr(preq->rq_extend, 't'))
		dosubjobs = 1;
	else if ((preq->rq_extend != NULL) && strchr(preq->rq_extend, 'S'))
		dosubjobs = 2;
	/*
	 * If the letter x is in the extend string, Check if the server is
	 * configured for job history info. If it is not SET or set to FALSE
	 * then return with PBSE_JOBHISTNOTSET error. Otherwise select history
	 * jobs also.
	 */
	if ((preq->rq_extend != NULL) && strchr(preq->rq_extend, 'x')) {
		if (svr_history_enable == 0) {
			req_reject(PBSE_JOBHISTNOTSET, 0, preq);
			return;
		}
		dohistjobs = 1;
	}

	/* The first selstat() call from the scheduler indicates that a cycle
	 * is in progress and has reached the point of querying for jobs.
	 * TODO: This approach must be revisited if the scheduler changes its
	 * approach to query for jobs, e.g., by issuing a single pbs_statjob()
	 * instead of a per-queue selstat()
	 */
	if ((find_sched_from_sock(preq->rq_conn) != NULL) && (!scheduler_jobs_stat)) {
		//if ((dflt_scheduler->scheduler_sock != -1) && (preq->rq_conn == dflt_scheduler->scheduler_sock) && (!scheduler_jobs_stat)) {
		scheduler_jobs_stat = 1;
	}

	plist = (svrattrl *)GET_NEXT(preq->rq_ind.rq_select.rq_selattr);

	rc = build_selist(plist, preq->rq_perm, &selistp, &pque, &bad, &pstate);

	if (rc != 0) {
		reply_badattr(rc, bad, plist, preq);
		free_sellist(selistp);
		return;
	}

	/* setup the appropriate return */

	preply = &preq->rq_reply;
	if (preq->rq_type == PBS_BATCH_SelectJobs) {
		preply->brp_choice = BATCH_REPLY_CHOICE_Select;
		preply->brp_un.brp_select = (struct brp_select *)0;
	} else {
		preply->brp_choice = BATCH_REPLY_CHOICE_Status;
		CLEAR_HEAD(preply->brp_un.brp_status);
	}
	pselx = &preply->brp_un.brp_select;

	/* now start checking for jobs that match the selection criteria */

	if (pque)
		pjob = (job *)GET_NEXT(pque->qu_jobs);
	else
		pjob = (job *)GET_NEXT(svr_alljobs);
	while (pjob) {
		if (server.sv_attr[(int)SRV_ATR_query_others].at_val.at_long ||
			(svr_authorize_jobreq(preq, pjob) == 0)) {

			/* either job owner or has special permission to see job */

			/* look at  the job and see if the required attributes match */
			/* If "T" was specified, dosubjobs is set, and if the job is */
			/* an Array Job, then the State is Not checked.  The State   */
			/* must be checked against the state of each Subjob	     */

			if (select_job(pjob, selistp, dosubjobs, dohistjobs)) {

				/* job is selected, include in reply */

				if (preq->rq_type == PBS_BATCH_SelectJobs) {

					/* Select Jobs Reply*/

					preq->rq_reply.brp_auxcode +=
						add_select_array_entries(pjob, dosubjobs, pstate, &pselx, selistp);

				} else if (((pjob->ji_qs.ji_svrflags&JOB_SVFLG_SubJob)==0) || (dosubjobs == 2)) {

					/* Select-Status  Reply */

					plist = (svrattrl *)GET_NEXT(preq->rq_ind.rq_select.rq_rtnattr);
					if ((dosubjobs == 1) && pjob->ji_ajtrk) {
						for (i=0; i<pjob->ji_ajtrk->tkm_ct; ++i) {
							if ((pstate == 0) || chk_job_statenum(pjob->ji_ajtrk->tkm_tbl[i].trk_status, pstate)) {
								rc = status_subjob(pjob, preq, plist, i, &preply->brp_un.brp_status, &bad);
								if (rc && (rc != PBSE_PERM))
									goto out;
								plist = (svrattrl *)GET_NEXT(preq->rq_ind.rq_select.rq_rtnattr);

							}
						}
					} else {
						rc = status_job(pjob, preq, plist,
							&preply->brp_un.brp_status, &bad);
						if (rc && (rc != PBSE_PERM))
							goto out;
					}

				}
			}
		}
		if (pque)
			pjob = (job *)GET_NEXT(pjob->ji_jobque);
		else
			pjob = (job *)GET_NEXT(pjob->ji_alljobs);
	}
out:
	free_sellist(selistp);
	if (rc)
		req_reject(rc, 0, preq);
	else
		(void)reply_send(preq);
}

/**
 * @brief
 * 		select_job - determine if a single job matches the selection criteria
 *
 * @param[in]	pjob	-	pointer to job
 * @param[in]	psel	-	selection list
 * @param[in]	dosubjobs	-	Does it needs to check the subjob.
 * @param[in]	dohistjobs	-	If not being asked for history jobs specifically,
 * 									then just skip them otherwise include them.
 *
 * @return	int
 * @retval	0	: no match
 * @retval	1	: matches
 */

static int
select_job(job *pjob, struct select_list *psel, int dosubjobs, int dohistjobs)
{

	/*
	 * If not being asked for history jobs specifically, then just skip
	 * them otherwise include them. i.e. if the batch request has the special
	 * extended flag 'x'.
	 */
	if ((!dohistjobs) && ((pjob->ji_qs.ji_state == JOB_STATE_FINISHED) ||
		(pjob->ji_qs.ji_state == JOB_STATE_MOVED))) {
		return 0;
	}

	if ((pjob->ji_qs.ji_svrflags & JOB_SVFLG_ArrayJob) == 0)
		dosubjobs = 0;  /* not an Array Job,  ok to check state */
	else if ((dosubjobs != 2) &&
		(pjob->ji_qs.ji_svrflags & JOB_SVFLG_SubJob))
		return 0;	/* don't bother to look at sub job */

	while (psel) {

		if (psel->sl_atindx == (int)JOB_ATR_userlst) {
			if (!acl_check(&psel->sl_attr, pjob->ji_wattr[(int)JOB_ATR_job_owner].at_val.at_str, ACL_User))
				return (0);

		} else if (!dosubjobs || (psel->sl_atindx != JOB_ATR_state)) {

			if (!sel_attr(&pjob->ji_wattr[psel->sl_atindx], psel))
				return (0);
		}
		psel = psel->sl_next;
	}

	return (1);
}

/**
 * @brief
 * 		sel_attr - determine if attribute is according to the selection operator
 *
 * @param[in]	jobat	-	job attribute
 * @param[in]	pselst	-	selection operator
 *
 * @return	int
 * @retval	0	: attribute does not meets criteria
 * @retval	1	: attribute meets criteria
 *
 */

static int
sel_attr(attribute *jobat, struct select_list *pselst)
{
	int	   rc;
	resource  *rescjb;
	resource  *rescsl;

	if (pselst->sl_attr.at_type == ATR_TYPE_RESC) {

		/* Only one resource per selection entry, 		*/
		/* find matching resource in job attribute if one	*/

		rescsl = (resource *)GET_NEXT(pselst->sl_attr.at_val.at_list);
		rescjb = find_resc_entry(jobat, rescsl->rs_defin);

		if (rescjb && (rescjb->rs_value.at_flags & ATR_VFLAG_SET))
			/* found match, compare them */
			rc = pselst->sl_def->at_comp(&rescjb->rs_value, &rescsl->rs_value);
		else		/* not one in job,  force to .lt. */
			rc = -1;

	} else {
		/* "normal" attribute */

		rc = pselst->sl_def->at_comp(jobat, &pselst->sl_attr);
	}

	if (rc < 0) {
		if ((pselst->sl_op == NE) ||
			(pselst->sl_op == LT) ||
			(pselst->sl_op == LE))
			return (1);

	} else if (rc > 0) {
		if ((pselst->sl_op == NE) ||
			(pselst->sl_op == GT) ||
			(pselst->sl_op == GE))
			return (1);

	} else {	/* rc == 0 */
		if ((pselst->sl_op == EQ) ||
			(pselst->sl_op == GE) ||
			(pselst->sl_op == LE))
			return (1);
	}
	return (0);
}

/**
 * @brief
 * 		Free a select_list list created by build_selist()
 * @par
 *		For each entry in the select_list free the enclosed attribute entry
 *		using the index into the job_attr_def array in sl_atindx.  For an
 *		attribute of type resource, this is the index of the resource type
 *		attribute (typically Resource_List).  Where as sl_def is specific to
 *		the resource in the list headed by that attribute.  There is only one
 *		resource per select_list entry.
 *
 * @param[in]	pslist	-	pointer to first entry in the select list.
 *
 * @return	none
 */

static void
free_sellist(struct select_list *pslist)
{
	struct select_list *next;

	while (pslist) {
		next = pslist->sl_next;
		job_attr_def[pslist->sl_atindx].at_free(&pslist->sl_attr); /* free the attr */
		(void)free(pslist);			  /* free the entry */
		pslist = next;
	}
}


/**
 * @brief
 * 		build_selentry - build a single entry for a select list
 *
 * @param[in]	pslist	-	svrattrl structure from which we decode the select list
 * @param[in]	pdef	-	attribute_def structure.
 * @param[in]	perm	-	permission
 * @param[out]	rtnentry	-	pointer to the single entry for the select list
 *
 * @return	int
 * @retval	0	: success
 * @retval	!0	: error code
 *
 */

static int
build_selentry(svrattrl *plist, attribute_def *pdef, int perm, struct select_list **rtnentry)
{
	struct select_list *entry;
	resource_def *prd;
	int old_perms = resc_access_perm;
	int		    rc;

	/* create a select list entry for this attribute */

	entry = (struct select_list *)
		malloc(sizeof(struct select_list));
	if (entry == (struct select_list *)0)
		return (PBSE_SYSTEM);

	entry->sl_next = (struct select_list *)0;

	clear_attr(&entry->sl_attr, pdef);

	if (!(pdef->at_flags & ATR_DFLAG_RDACC & perm)) {
		(void)free(entry);
		return (PBSE_PERM);    /* no read permission */
	}
	if ((pdef->at_flags & ATR_DFLAG_SELEQ) && (plist->al_op != EQ) &&
		(plist->al_op != NE)) {
		/* can only select eq/ne on this attribute */
		(void)free(entry);
		return (PBSE_IVALREQ);
	}

	/*
	 * If a resource is marked flag=r in resourcedef
	 * we need to force the decode function to
	 * decode it to allow us to select upon it.
	 */
	if (plist->al_resc != NULL) {
		prd =find_resc_def(svr_resc_def, plist->al_resc, svr_resc_size);
		if (prd != NULL && (prd->rs_flags&NO_USER_SET) == NO_USER_SET) {
			resc_access_perm = ATR_DFLAG_ACCESS;
		}
	}

	/* decode the attribute into the entry */

	rc = pdef->at_decode(&entry->sl_attr, plist->al_name, plist->al_resc,
		plist->al_value);

	resc_access_perm = old_perms;
	if (rc) {
		(void)free(entry);
		return (rc);
	}
	if ((entry->sl_attr.at_flags & ATR_VFLAG_SET) == 0) {
		(void)free(entry);
		return (PBSE_BADATVAL);
	}

	/*
	 * save the pointer to the attribute definition,
	 * if a resource, use the resource specific one
	 */

	if (entry->sl_attr.at_type == ATR_TYPE_RESC) {
		entry->sl_def = (attribute_def *)find_resc_def(
			svr_resc_def, plist->al_resc, svr_resc_size);
		if (!entry->sl_def) {
			(void)free(entry);
			return (PBSE_UNKRESC);
		}
	} else
		entry->sl_def = pdef;

	/* save the selection operator to pass along */

	entry->sl_op = plist->al_op;

	*rtnentry = entry;
	return (0);
}

/**
 * @brief
 * 		build_selist - build the list of select_list structures based on
 *		the svrattrl structures in the request.
 * @par
 *		Function returns non-zero on an error, also returns into last
 *		four entries of the parameter list.
 *
 * @param[in]	plist	-	svrattrl structure from which we decode the select list
 * @param[in]	perm	-	permission
 * @param[out]	pselist	-	RETURN : select list
 * @param[out]	pque	-	RETURN : queue ptr if limit to que
 * @param[out]	bad	-	RETURN - index of bad attr
 * @param[out]	pstate	-	RETURN - pointer to required state
 *
 * @return	int
 * @retval	0	: success
 * @retval	!0	: error code
 */

static int
build_selist(svrattrl *plist, int perm, struct select_list **pselist, pbs_queue **pque, int *bad, char **pstate)
{
	struct select_list *entry;
	int		    i;
	char		   *pc;
	attribute_def	   *pdef;
	struct select_list *prior = (struct select_list *)0;
	int		    rc;

	/* set permission for decode_resc() */

	resc_access_perm = perm;

	*pque = (pbs_queue *)0;
	*bad = 0;
	*pselist = (struct select_list *)0;
	while (plist) {
		(*bad)++;	/* list counter incase one is bad */

		/* go for all job unless a "destination" other than */
		/* "@server" is specified			    */

		if (!strcasecmp(plist->al_name, ATTR_q)) {
			if (plist->al_valln) {
				if (((pc = strchr(plist->al_value, (int)'@')) == 0) ||
					(pc != plist->al_value)) {

					/* does specified destination exist? */

					*pque = find_queuebyname(plist->al_value);
#ifdef NAS /* localmod 075 */
					if (*pque == NULL)
						*pque = find_resvqueuebyname(plist->al_value);
#endif /* localmod 075 */
					if (*pque == (pbs_queue *)0)
						return (PBSE_UNKQUE);
				}
			}
		} else {
			i = find_attr(job_attr_def, plist->al_name, JOB_ATR_LAST);
			if (i < 0)
				return (PBSE_NOATTR);   /* no such attribute */

			if (i == JOB_ATR_state) {
				pdef = &state_sel;
				*pstate = plist->al_value;
			} else {
				pdef = job_attr_def + i;
			}

			/* create a select list entry for this attribute */

			rc = build_selentry(plist, pdef, perm, &entry);
			if (rc)
				return rc;
			entry->sl_atindx = i;

			/* add the entry to the select list */

			if (prior)
				prior->sl_next = entry;    /* link into list */
			else
				*pselist = entry;    /* return start of list */
			prior = entry;
		}
		plist = (svrattrl *)GET_NEXT(plist->al_link);
	}
	return (0);
}

/**
 * @brief
 *		Select subjob by matching the specified state with select_list
 *
 * @par
 *		Linkage scope: Local(static)
 *
 * @par Functionality:
 *		This function walks through the select list (which is basically a \n
 *		linked list of attribute structures built by build_selist()). Skips \n
 *		the select_list structure if the index is not JOB_ATR_state.
 *
 * @see	add_select_array_entries()
 *
 * @param[in]	state	-	state of the subjob
 * @param[in]	psel	-	pointer to select list
 *
 * @return	int
 *
 * @retval	0	- failure: no match
 * @retval	1	- success: selected subjob
 *
 * @par MT-safety: NO
 *
 */

static int
select_subjob(int state, struct select_list *psel)
{
	attribute *selstate;

	for (; psel; psel = psel->sl_next) {
		if (psel->sl_atindx != JOB_ATR_state)
			continue;
		selstate = &psel->sl_attr;
		if (selstate == NULL)
			continue;
		if (!chk_job_statenum(state, selstate->at_val.at_str))
			return (0);
	}
	return (1);
}

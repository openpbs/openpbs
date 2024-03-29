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
 * @file    req_track.c
 *
 * @brief
 * 	req_track.c	-	Functions relation to the Track Job Request and job tracking.
 *
 * Functions included are:
 *	req_track()
 *	track_save()
 *	issue_track()
 *	track_history_job()
 *
 */
#include <pbs_config.h> /* the master config generated by configure */

#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <stdlib.h>
#include "libpbs.h"
#include <fcntl.h>
#include <signal.h>
#include "server_limits.h"
#include "list_link.h"
#include "attribute.h"
#include "server.h"
#include "credential.h"
#include "batch_request.h"
#include "job.h"
#include "pbs_error.h"
#include "work_task.h"
#include "tracking.h"
#include "log.h"
#include "pbs_nodes.h"
#include "svrfunc.h"

/* External functions */

extern int issue_to_svr(char *svr, struct batch_request *, void (*func)(struct work_task *));

/* Local functions */

static void track_history_job(struct rq_track *, char *);

/* Global Data Items: */

extern char *path_track;
extern struct server server;
extern time_t time_now;
extern char server_name[];

/**
 * @brief
 * 		req_track - record job tracking information
 *
 * @param[in,out]	preq	-	request from the server.
 */

void
req_track(struct batch_request *preq)
{
	struct tracking *empty = NULL;
	int i;
	int need;
	struct tracking *new;
	struct tracking *ptk;
	struct rq_track *prqt;

	/*  make sure request is from a server */

	if (!preq->rq_fromsvr) {
		req_reject(PBSE_IVALREQ, 0, preq);
		return;
	}

	/* attempt to locate tracking record for this job    */
	/* also remember first empty slot in case its needed */

	prqt = &preq->rq_ind.rq_track;

	ptk = server.sv_track;
	for (i = 0; i < server.sv_tracksize; i++) {
		if ((ptk + i)->tk_mtime) {
			if (!strcmp((ptk + i)->tk_jobid, prqt->rq_jid)) {

				/*
				 * found record, discard it if state == exiting,
				 * otherwise, update it if older
				 */

				if (*prqt->rq_state == 'E') {
					(ptk + i)->tk_mtime = 0;
					track_history_job(prqt, NULL);
				} else if ((ptk + i)->tk_hopcount < prqt->rq_hopcount) {
					(ptk + i)->tk_hopcount = prqt->rq_hopcount;
					(void) strcpy((ptk + i)->tk_location, prqt->rq_location);
					(ptk + i)->tk_state = *prqt->rq_state;
					(ptk + i)->tk_mtime = time_now;
					track_history_job(prqt, preq->rq_extend);
				}
				server.sv_trackmodifed = 1;
				reply_ack(preq);
				return;
			}
		} else if (empty == NULL) {
			empty = ptk + i;
		}
	}

	/* if we got here, didn't find it... */

	if (*prqt->rq_state != 'E') {

		/* and need to add it */

		if (empty == NULL) {

			/* need to make room for more */

			need = server.sv_tracksize * 3 / 2;
			new = (struct tracking *) realloc(server.sv_track,
							  need * sizeof(struct tracking));
			if (new == NULL) {
				log_err(errno, "req_track", "malloc failed");
				req_reject(PBSE_SYSTEM, 0, preq);
				return;
			}
			empty = new + server.sv_tracksize; /* first new slot */
			for (i = server.sv_tracksize; i < need; i++)
				(new + i)->tk_mtime = 0;
			server.sv_tracksize = need;
			server.sv_track = new;
		}

		empty->tk_mtime = time_now;
		empty->tk_hopcount = prqt->rq_hopcount;
		(void) strcpy(empty->tk_jobid, prqt->rq_jid);
		(void) strcpy(empty->tk_location, prqt->rq_location);
		empty->tk_state = *prqt->rq_state;
		server.sv_trackmodifed = 1;
	}
	reply_ack(preq);
	return;
}

/**
 * @brief
 * 		track_save - save the tracking records to a file
 * @par
 *		This routine is invoked periodically by a timed work task entry.
 *		The first entry is created at server initialization time and then
 *		recreated on each entry.
 * @par
 *		On server shutdown, track_save is called with a null work task pointer.
 *
 * @param[in]	pwt	-	unused
 */

void
track_save(struct work_task *pwt)
{
	int fd;

	/* set task for next round trip */

	if (pwt) { /* set up another work task for next time period */
		if (!set_task(WORK_Timed, (long) time_now + PBS_SAVE_TRACK_TM,
			      track_save, 0))
			log_err(errno, __func__, "Unable to set task for save");
	}

	if (server.sv_trackmodifed == 0)
		return; /* nothing to do this time */

	fd = open(path_track, O_WRONLY, 0);
	if (fd < 0) {
		log_err(errno, __func__, "Unable to open tracking file");
		return;
	}

	if (write(fd, (char *) server.sv_track, server.sv_tracksize * sizeof(struct tracking)) == -1) 
		log_errf(-1, __func__, "write failed. ERR : %s",strerror(errno));
	(void) close(fd);
	server.sv_trackmodifed = 0;
	return;
}

/**
 * @brief
 * 		issue_track - issue a Track Job Request to another server
 *
 * @param[in]	pwt	-	Job Request to another server
 */

void
issue_track(job *pjob)
{
	struct batch_request *preq;
	char *pc;

	preq = alloc_br(PBS_BATCH_TrackJob);
	if (preq == NULL)
		return;

	preq->rq_ind.rq_track.rq_hopcount = get_jattr_long(pjob, JOB_ATR_hopcount);
	(void) strcpy(preq->rq_ind.rq_track.rq_jid, pjob->ji_qs.ji_jobid);
	(void) strcpy(preq->rq_ind.rq_track.rq_location, pbs_server_name);
	preq->rq_ind.rq_track.rq_state[0] = get_job_state(pjob);
	preq->rq_extend = (char *) malloc(PBS_MAXROUTEDEST + 1);
	if (preq->rq_extend != NULL)
		(void) strncpy(preq->rq_extend, pjob->ji_qs.ji_queue, PBS_MAXROUTEDEST + 1);

	pc = pjob->ji_qs.ji_jobid;
	while (*pc != '.')
		pc++;
	(void) issue_to_svr(++pc, preq, release_req);
}

/**
 * @brief
 * 		track_history_job()	-	It updates the substate and comment attribute of
 * 		history job (job state = JOB_STATE_LTR_MOVED).
 *
 * @param[in]	prqt	-	request track structure
 * @param[in]	extend	-	request "extension" data
 *
 * @return	Nothing
 */
static void
track_history_job(struct rq_track *prqt, char *extend)
{
	char *comment = "Job has been moved to";
	job *pjob = NULL;
	char dest_queue[PBS_MAXROUTEDEST + 1] = {'\0'};

	/* return if the server is not configured for job history */
	if (svr_chk_history_conf() == 0)
		return;

	pjob = find_job(prqt->rq_jid);

	/*
	 * Return if not found the job OR job is not created here
	 * OR job is not in state MOVED.
	 */
	if ((pjob == NULL) ||
	    ((pjob->ji_qs.ji_svrflags & JOB_SVFLG_HERE) == 0) ||
	    (!check_job_state(pjob, JOB_STATE_LTR_MOVED))) {
		return;
	}

	/*
	 * If the track state is 'E', then update the substate of
	 * the history job substate=JOB_SUBSTATE_MOVED to JOB_SUBSTATE_FINISHED
	 * and update the comment message.
	 */
	if (*prqt->rq_state == 'E') {
		set_job_substate(pjob, JOB_SUBSTATE_FINISHED);
		/* over write the default comment message */
		comment = "Job finished at";
	}

	/* If the track state is 'Q' and extend has data, update
	 * history information with new destination queue.
	 */
	if (*prqt->rq_state == 'Q' && extend != NULL) {
		(void) strncpy(dest_queue, extend, PBS_MAXQUEUENAME + 1);
		(void) strcat(dest_queue, "@");
		(void) strcat(dest_queue, prqt->rq_location);
		/* Set the new queue attribute to destination */
		set_jattr_generic(pjob, JOB_ATR_in_queue, dest_queue, NULL, SET);
	}

	/*
	 * Populate the appropriate comment message in log_buffer
	 * and call the decode API for the comment attribute of job
	 * to update the modified comment message.
	 */
	sprintf(log_buffer, "%s \"%s\"", comment, prqt->rq_location);
	set_jattr_str_slim(pjob, JOB_ATR_Comment, log_buffer, NULL);
	svr_histjob_update(pjob, get_job_state(pjob), get_job_substate(pjob));
}

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

/**
 * @file	undolr.c
 * @brief
 *	The Undo Recording API calls to integrate with PBSPro.
 *	It allows our daemons to create an Undo Recording of itself running, which can
 *	then be opened using the Undo Debugger/Player (UndoDB).
 * 
 */

#include <signal.h>
#include <string.h>
#include <unistd.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>
#include <pbs_internal.h>
#include "log.h"
#include "undolr.h"

int sigusr1_flag;
static char recording_file [MAXPATHLEN + 1];

/**
 * @brief
 *	catch_sigusr1() - the signal handler for  SIGUSR1.
 *	Set a flag for the main loop to know that a sigusr1 processes
 *
 * @param[in]	sig	- not used in fun.
 *
 * @return	void
 */
void
catch_sigusr1(int sig)
{
	sigusr1_flag = 1;
}

/**
 * @brief
 *	mk_recording_path - make the recording name and path used by deamons 
 *	based on the date and time: <deamon_name>_yyyymmddHHMM.undo
 *
 * @param[in] fpath - buffer to hold the live recording file path
 *
 * @return  0 - Success
 *          1 - Failure
 *
 */
static void mk_recording_path(char * fpath) 
{
	struct tm ltm;
	struct tm *ptm;
	time_t time_now;

	if (pbs_loadconf(1) == 0)
		log_eventf(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER, LOG_ALERT, msg_daemonname, 
				"%s: Could not load pbs configuration, will use it's default value", __func__);

	time_now = time(NULL);
	ptm = localtime_r(&time_now, &ltm);

	if (pbs_conf.pbs_lr_save_path)
		(void)snprintf(fpath, MAXPATHLEN,
			"%s/%s_%04d%02d%02d%02d%02d.undo",
			pbs_conf.pbs_lr_save_path, msg_daemonname, ptm->tm_year + 1900, ptm->tm_mon + 1,
			ptm->tm_mday, ptm->tm_hour,ptm->tm_min);
	else /* default path */
		(void)snprintf(fpath, MAXPATHLEN,
			"%s/%s/%s_%04d%02d%02d%02d%02d.undo",
			pbs_conf.pbs_home_path, "spool", msg_daemonname, ptm->tm_year + 1900, ptm->tm_mon + 1,
			ptm->tm_mday, ptm->tm_hour,ptm->tm_min);
}

/**
 * @brief 
 *	undolr - call respective Undo Live Recorder APIs
 *	to start and stop the recordings.
 * @return  void 
 */
void undolr()
{
	int e = 0;
	static int recording;
	undolr_error_t err = 0;
	undolr_recording_context_t lr_ctx;

	if (!recording) {
		mk_recording_path(recording_file);
		log_eventf(PBSEVENT_ADMIN | PBSEVENT_FORCE,
				PBS_EVENTCLASS_SERVER, LOG_DEBUG, msg_daemonname, 
				"Undo live recording started, will save to %s", recording_file);

		/**
		 * Undo API call to start recording.
		 * Attaches Live Recorder to the process, and starts recording it.
		 */
		e = undolr_start(&err);
		if (e) {
			log_eventf(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_ALERT, msg_daemonname, 
				"Unable to start undo recording, error=%i errno=%i\n", e, errno);
			return;
		}

		/* Undo API call to save recording on termination. */
		e = undolr_save_on_termination(recording_file);
		if (e) {
			log_eventf(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_ERR, msg_daemonname, 
				"undolr_save_on_termination() failed: error=%i errno=%i\n", e, errno);
			return;
		}
		recording = 1;
	} else {
		/**
		 * Undo API call to stop recording.
		 * Detaches Live Recorder from the process.
		 */
		e = undolr_stop(&lr_ctx);
		if (e) {
			log_eventf(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_ERR, msg_daemonname, 
				"undolr_stop() failed: errno=%i\n", errno);
			return;
		}
		recording = 0;
		log_eventf(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
			LOG_INFO, msg_daemonname, 
			"Stopped Undo live recording");

		/* Undo API call to save recording. */
		e = undolr_save_async(lr_ctx, recording_file);
		if (e) {
			log_eventf(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_ERR, msg_daemonname, 
				"undolr_save_async() failed: errno=%i\n", errno);
			return;
		}
		log_eventf(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
			LOG_INFO, msg_daemonname, 
			"Have created Undo live recording at: %s\n", recording_file);

		/**
		 * Recording state that is currently held in memory is freed.
		 */
		e = undolr_discard(lr_ctx);
		if (e) {
			sprintf(log_buffer,
				"undolr_dicard() failed: errno=%i\n", errno);
			log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_ERR, msg_daemonname, log_buffer);
		}
	}
	sigusr1_flag = 0;
}

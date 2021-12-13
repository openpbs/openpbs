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

#ifndef _SCHED_CMDS_H
#define _SCHED_CMDS_H
#ifdef __cplusplus
extern "C" {
#endif

#include "pbs_ifl.h"
typedef struct sched_cmd sched_cmd;

struct sched_cmd {
	/* sched command */
	int cmd;

	/* jobid assisiated with cmd if any else NULL */
	char *jid;
};

/* server to scheduler commands: */
enum svr_sched_cmd {
	SCH_SCHEDULE_NULL,
	SCH_SCHEDULE_NEW,   /* New job queued or eligible	*/
	SCH_SCHEDULE_TERM,  /* Running job terminated	*/
	SCH_SCHEDULE_TIME,  /* Scheduler interval reached	*/
	SCH_SCHEDULE_RECYC, /* Not currently used		*/
	SCH_SCHEDULE_CMD,   /* Schedule on command 		*/
	SCH_CONFIGURE,
	SCH_QUIT,
	SCH_RULESET,
	SCH_SCHEDULE_FIRST,	     /* First schedule after server starts */
	SCH_SCHEDULE_JOBRESV,	     /* Arrival of an existing reservation time */
	SCH_SCHEDULE_AJOB,	     /* run one, named job */
	SCH_SCHEDULE_STARTQ,	     /* Stopped queue started */
	SCH_SCHEDULE_MVLOCAL,	     /* Job moved to local queue */
	SCH_SCHEDULE_ETE_ON,	     /* eligible_time_enable is turned ON */
	SCH_SCHEDULE_RESV_RECONFIRM, /* Reconfirm a reservation */
	SCH_SCHEDULE_RESTART_CYCLE,  /* Restart a scheduling cycle */
	SCH_CMD_HIGH		     /* This has to be the last command always. Any new command can be inserted above if required */
};

int schedule(int sd, const sched_cmd *cmd);

#ifdef __cplusplus
}
#endif
#endif /* _SCHED_CMDS_H */

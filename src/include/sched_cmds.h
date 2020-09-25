/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

	/*
	 * connection to server from which we got this sched command.
	 * This will be one of the server's secondary connection.
	 *
	 * This will be used in while finding server conn structure before calling
	 * schedule() which needs primary connection to the server
	 *
	 */
	int from_sock;
};

/* server to scheduler commands: */
#define SCH_ERROR         -1
#define SCH_SCHEDULE_NULL  0
#define SCH_SCHEDULE_NEW   1		/* New job queued or eligible	*/
#define SCH_SCHEDULE_TERM  2		/* Running job terminated	*/
#define SCH_SCHEDULE_TIME  3		/* Scheduler interval reached	*/
#define SCH_SCHEDULE_RECYC 4		/* Not currently used		*/
#define SCH_SCHEDULE_CMD   5		/* Schedule on command 		*/
#define SCH_CONFIGURE      7
#define SCH_QUIT           8
#define SCH_RULESET        9
#define SCH_SCHEDULE_FIRST 10		/* First schedule after server starts */
#define SCH_SCHEDULE_JOBRESV 11		/* Arrival of an existing reservation time */
#define SCH_SCHEDULE_AJOB  12		/* run one, named job */
#define SCH_SCHEDULE_STARTQ 13		/* Stopped queue started */
#define SCH_SCHEDULE_MVLOCAL 14		/* Job moved to local queue */
#define SCH_SCHEDULE_ETE_ON 15		/* eligible_time_enable is turned ON */
#define SCH_SCHEDULE_RESV_RECONFIRM 16		/* Reconfirm a reservation */
#define SCH_SCHEDULE_RESTART_CYCLE 17		/* Restart a scheduling cycle */

int schedule(int sd, sched_cmd *cmd);

#ifdef __cplusplus
}
#endif
#endif /* _SCHED_CMDS_H */

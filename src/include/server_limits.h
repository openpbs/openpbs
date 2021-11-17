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

#ifndef _SERVER_LIMITS_H
#define _SERVER_LIMITS_H
#ifdef __cplusplus
extern "C" {
#endif
#include <pbs_config.h>

/*
 * This section contains size limit definitions
 *
 * BEWARE OF CHANGING THESE
 */
#ifndef PBS_MAXNODENAME
#define PBS_MAXNODENAME 79 /* max length of a vnode name		    */
#endif
#define PBS_JOBBASE 11 /* basename size for job file, 11 = 14 -3   */
/* where 14 is min file name, 3 for suffix  */

#define PBS_RESVBASE 11 /* basename size for job file, 10 = 14 -3   */
/* where 14 is max file name, 3 for suffix - ".RF" */
#define PBS_NUMJOBSTATE 10 /* TQHWREXBMF */

#ifdef NAS		   /* localmod 083 */
#define PBS_MAX_HOPCOUNT 3 /* limit on number of routing hops per job */
#else
#define PBS_MAX_HOPCOUNT 10 /* limit on number of routing hops per job */
#endif			    /* localmod 083 */

#define PBS_SEQNUMTOP 999999999999 /* top number for job sequence number, reset */
/* to zero when reached, see req_quejob.c    */

#define PBS_NET_RETRY_TIME 30	    /* Retry time between re-sending requests  */
#define PBS_NET_RETRY_LIMIT 14400   /* Max retry time */
#define PBS_SCHEDULE_CYCLE 600	    /* re-schedule even if no change, 10 min   */
#define PBS_RESTAT_JOB 30	    /* ask mom for status only once in 30 sec  */
#define PBS_STAGEFAIL_WAIT 1800	    /* retry time after stage in failuere */
#define PBS_MAX_ARRAY_JOB_DFL 10000 /* default max size of an array job */

/* Server Database information - path names */

#define PBS_SVR_PRIVATE "server_priv"
#define PBS_ACCT "accounting"
#define PBS_JOBDIR "jobs"
#define PBS_USERDIR "users"
#define PBS_RESCDEF "resourcedef"
#define PBS_RESVDIR "resvs"
#define PBS_SPOOLDIR "spool"
#define PBS_QUEDIR "queues"
#define PBS_LOGFILES "server_logs"
#define PBS_ACTFILES "accounting"
#define PBS_SERVERDB "serverdb"
#define PBS_SVRACL "acl_svr"
#define PBS_TRACKING "tracking"
#define NODE_DESCRIP "nodes"
#define NODE_STATUS "node_status"
#define VNODE_MAP "vnodemap"
#define PBS_PROV_TRACKING "prov_tracking"
#define PBS_SCHEDDB "scheddb"
#define PBS_SCHED_PRIVATE "sched_priv"
#define PBS_SVRLIVE "svrlive"
#define DIGEST_LENGTH 20 /* for now making this equal to SHA_DIGEST_LENGTH  which is 20 */

/*
 * Security, Authentication, Authorization Control:
 *
 *	- What account is PBS mail from
 *	- Who is the default administrator (when none defined)
 *	- Is "root" always an batch adminstrator (manager) (YES/no)
 */

#define PBS_DEFAULT_MAIL "adm"
#define PBS_DEFAULT_ADMIN "root"
#define PBS_ROOT_ALWAYS_ADMIN 1

/* #define NO_SPOOL_OUTPUT 1	User output in home directory,not spool */

/* "simplified" network address structure */

#ifndef PBS_NET_TYPE
typedef unsigned long pbs_net_t; /* for holding host addresses */
#define PBS_NET_TYPE
#endif /* PBS_NET_TYPE */

/*
 * the following funny business is due to the fact that O_SYNC
 * is not currently POSIX
 */
#if defined(O_SYNC)
#define O_Sync O_SYNC
#elif defined(_FSYNC)
#define O_Sync _FSYNC
#elif defined(O_FSYNC)
#define O_Sync O_FSYNC
#else
#define O_Sync 0
#endif

/* defines for job moving (see net_move() ) */

#define MOVE_TYPE_Move 1  /* Move by user request */
#define MOVE_TYPE_Route 2 /* Route from routing queue */
#define MOVE_TYPE_Exec 3  /* Execution (move to MOM) */
#define MOVE_TYPE_MgrMv 4 /* Mover by privileged user, a manager */
#define MOVE_TYPE_Order 5 /* qorder command by user */

#define SEND_JOB_OK 0			 /* send_job sent successfully	  */
#define SEND_JOB_FATAL 1		 /* send_job permenent fatal error */
#define SEND_JOB_RETRY 2		 /* send_job failed, retry later	  */
#define SEND_JOB_NODEDW 3		 /* send_job node down, mark down  */
#define SEND_JOB_HOOKERR 4		 /* send_job hook error */
#define SEND_JOB_HOOK_REJECT 5		 /* send_job hook reject */
#define SEND_JOB_HOOK_REJECT_RERUNJOB 6	 /*send_job hook reject,requeue job*/
#define SEND_JOB_HOOK_REJECT_DELETEJOB 7 /*send_job hook reject, delete job*/
#define SEND_JOB_SIGNAL 8		 /* send_job response for signal received  */

/*
 * server initialization modes
 */
#define RECOV_HOT 0	 /* restart prior running jobs   */
#define RECOV_WARM 1	 /* requeue/reschedule  all jobs */
#define RECOV_COLD 2	 /* discard all jobs		*/
#define RECOV_CREATE 3	 /* discard all info		*/
#define RECOV_UPDATEDB 4 /* migrate data from fs to database */
#define RECOV_Invalid 5

/*
 * for protecting the daemons from kernel killers
 */
enum PBS_Daemon_Protect {
	PBS_DAEMON_PROTECT_OFF,
	PBS_DAEMON_PROTECT_ON
};
void daemon_protect(pid_t, enum PBS_Daemon_Protect);

#ifdef __cplusplus
}
#endif
#endif /* _SERVER_LIMITS_H */

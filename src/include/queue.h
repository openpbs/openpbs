/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
#ifndef	_QUEUE_H
#define	_QUEUE_H
#ifdef	__cplusplus
extern "C" {
#endif

/*
 * queue.h - struture definations for queue objects
 *
 * Include Files Requried:
 *
 *	<sys/types.h>
 *	"attribute.h"
 *	"list_link.h"
 *      "server_limits.h"
 *      "resource.h"
 *      "reservation.h"
 *
 * Queue Types
 */

#define QTYPE_Unset	0
#define QTYPE_Execution 1
#define QTYPE_RoutePush 2
#define QTYPE_RoutePull 3

/*
 * Attributes, including the various resource-lists are maintained in an
 * array in a "decoded or parsed" form for quick access to the value.
 *
 * The following enum defines the index into the array.
 */

enum queueattr {
	QA_ATR_QType,
	QA_ATR_Priority,
	QA_ATR_MaxJobs,
	QA_ATR_TotalJobs,
	QA_ATR_JobsByState,
	QA_ATR_MaxRun,
	QA_ATR_max_queued,
	QA_ATR_max_queued_res,
	QA_ATR_AclHostEnabled,
	QA_ATR_AclHost,
	QA_ATR_AclUserEnabled,
	QA_ATR_AclUsers,
	QA_ATR_FromRouteOnly,
	QA_ATR_ResourceMax,
	QA_ATR_ResourceMin,
	QA_ATR_ResourceDefault,
	QA_ATR_ReqCredEnable,
	QA_ATR_ReqCred,
	QA_ATR_maxarraysize,
	QA_ATR_Comment,
	QE_ATR_AclGroupEnabled,
	QE_ATR_AclGroup,

	/* The following attributes apply only to exection queues */

	QE_ATR_ChkptMim,
	QE_ATR_RendezvousRetry,
	QE_ATR_ReservedExpedite,
	QE_ATR_ReservedSync,
	QE_ATR_DefaultChunk,
	QE_ATR_ResourceAvail,
	QE_ATR_ResourceAssn,
	QE_ATR_KillDelay,
	QE_ATR_MaxUserRun,
	QE_ATR_MaxGrpRun,
	QE_ATR_max_run,
	QE_ATR_max_run_res,
	QE_ATR_max_run_soft,
	QE_ATR_max_run_res_soft,
	QE_ATR_HasNodes,
	QE_ATR_MaxUserRes,
	QE_ATR_MaxGroupRes,
	QE_ATR_MaxUserRunSoft,
	QE_ATR_MaxGrpRunSoft,
	QE_ATR_MaxUserResSoft,
	QE_ATR_MaxGroupResSoft,
	QE_ATR_NodeGroupKey,
	QE_ATR_BackfillDepth,

	/* The following attribute apply only to routing queues... */

	QR_ATR_RouteDestin,
	QR_ATR_AltRouter,
	QR_ATR_RouteHeld,
	QR_ATR_RouteWaiting,
	QR_ATR_RouteRetryTime,
	QR_ATR_RouteLifeTime,

#include "site_que_attr_enum.h"
	QA_ATR_Enabled,	/* these are last for qmgr print function   */
	QA_ATR_Started,
	QA_ATR_queued_jobs_threshold,
	QA_ATR_queued_jobs_threshold_res,
	QA_ATR_partition,
	QA_ATR_LAST	/* WARNING: Must be the highest valued enum */
};

extern attribute_def que_attr_def[];


/* at last we come to the queue definition itself	*/

struct pbs_queue {
	pbs_list_link	qu_link;		/* forward/backward links */
	pbs_list_head	qu_jobs;		/* jobs in this queue */
	resc_resv	*qu_resvp;		/* !=NULL if que established */
	/* to support a reservation */
	int		 qu_nseldft;		/* number of elm in qu_seldft */
	key_value_pair  *qu_seldft;		/* defaults for job -l select */
	struct queuefix {
		int	qu_modified;		/* != 0 => update disk file */
		int	qu_type;		/* queue type: exec, route */
		time_t	qu_ctime;		/* time queue created */
		time_t	qu_mtime;		/* time queue last modified */
		char	qu_name[PBS_MAXQUEUENAME]; /* queue name */
	} qu_qs;

	int	qu_numjobs;			/* current numb jobs in queue */
	int	qu_njstate[PBS_NUMJOBSTATE];	/* # of jobs per state */
	char	qu_jobstbuf[150];

	/* the queue attributes */

	attribute	qu_attr[QA_ATR_LAST];
};
typedef struct pbs_queue pbs_queue;

extern pbs_queue *find_queuebyname(char *);
#ifdef NAS /* localmod 075 */
extern pbs_queue *find_resvqueuebyname(char *);
#endif /* localmod 075 */
extern pbs_queue *get_dfltque(void);
extern pbs_queue *que_alloc(char *name);
extern void   que_free(pbs_queue *);
extern pbs_queue *que_recov_db(char *);
extern int    que_save_db(pbs_queue *, int mode);

#define QUE_SAVE_FULL 0
#define QUE_SAVE_NEW  1

#ifdef	__cplusplus
}
#endif
#endif	/* _QUEUE_H */

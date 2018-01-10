/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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
#ifndef	_SERVER_H
#define	_SERVER_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * server.h - definitions for the server object (structure)
 *
 * Other include files required:
 *	<sys/types.h>
 *	"attribute.h"
 *	"list_link.h"
 *	"server_limits.h"
 *
 * The server object (structure) contains the parameters which
 * control the operation of the server itself.  This includes
 * the server attributes and resource (limits).
 */
#ifndef	_GRUNT_H
#include "grunt.h"
#endif
#include "pbs_sched.h"
#include "server_limits.h"

enum srv_atr {
	SRV_ATR_State,
	SRV_ATR_SvrHost,
	SRV_ATR_scheduling,
	SRV_ATR_max_running,
	SRV_ATR_max_queued,
	SRV_ATR_max_queued_res,
	SRV_ATR_max_run,
	SRV_ATR_max_run_res,
	SRV_ATR_max_run_soft,
	SRV_ATR_max_run_res_soft,
	SRV_ATR_MaxUserRun,
	SRV_ATR_MaxGrpRun,
	SVR_ATR_MaxUserRes,
	SVR_ATR_MaxGroupRes,
	SVR_ATR_MaxUserRunSoft,
	SVR_ATR_MaxGrpRunSoft,
	SVR_ATR_MaxUserResSoft,
	SVR_ATR_MaxGroupResSoft,
	SVR_ATR_PNames,
	SRV_ATR_TotalJobs,
	SRV_ATR_JobsByState,
	SRV_ATR_acl_host_enable,
	SRV_ATR_acl_hosts,
	SRV_ATR_acl_host_moms_enable,
	SRV_ATR_acl_Resvhost_enable,
	SRV_ATR_acl_Resvhosts,
	SRV_ATR_acl_ResvGroup_enable,
	SRV_ATR_acl_ResvGroups,
	SRV_ATR_AclUserEnabled,
	SRV_ATR_AclUsers,
	SRV_ATR_AclResvUserEnabled,
	SRV_ATR_AclResvUsers,
	SRV_ATR_AclRoot,
	SRV_ATR_managers,
	SRV_ATR_operators,
	SRV_ATR_dflt_que,
	SRV_ATR_log_events,
	SRV_ATR_mailfrom,
	SRV_ATR_query_others,
	SRV_ATR_resource_avail,
	SRV_ATR_resource_deflt,
	SVR_ATR_DefaultChunk,
	SRV_ATR_ResourceMax,
	SRV_ATR_resource_assn,
	SRV_ATR_resource_cost,
	SVR_ATR_sys_cost,
	SRV_ATR_scheduler_iteration,
	SRV_ATR_Comment,
	SVR_ATR_DefNode,
	SVR_ATR_NodePack,
	SRV_ATR_FlatUID,
	SVR_ATR_FLicenses,
	SRV_ATR_ResvEnable,
	SRV_ATR_NodeFailReq,
	SVR_ATR_maxarraysize,
	SRV_ATR_ReqCredEnable,
	SRV_ATR_ReqCred,
	SRV_ATR_NodeGroupEnable,
	SRV_ATR_NodeGroupKey,
	SRV_ATR_ssignon_enable,
	SRV_ATR_dfltqdelargs,
	SRV_ATR_dfltqsubargs,
	SRV_ATR_rpp_retry,
	SRV_ATR_rpp_highwater,
	SRV_ATR_license_location,
	SRV_ATR_pbs_license_info,
	SRV_ATR_license_min,
	SRV_ATR_license_max,
	SRV_ATR_license_linger,
	SRV_ATR_license_count,
	SRV_ATR_version,
	SRV_ATR_job_sort_formula,
	SRV_ATR_EligibleTimeEnable,
	SRV_ATR_resv_retry_init,
	SRV_ATR_resv_retry_cutoff,
	SRV_ATR_JobHistoryEnable,
	SRV_ATR_JobHistoryDuration,
	SRV_ATR_ProvisionEnable,
	SRV_ATR_max_concurrent_prov,
	SVR_ATR_provision_timeout,
	SVR_ATR_resv_post_processing,
	SRV_ATR_BackfillDepth,
	SRV_ATR_JobRequeTimeout,
	SRV_ATR_PythonRestartMaxHooks,
	SRV_ATR_PythonRestartMaxObjects,
	SRV_ATR_PythonRestartMinInterval,
#include "site_svr_attr_enum.h"
	SRV_ATR_queued_jobs_threshold,
	SRV_ATR_queued_jobs_threshold_res,
	SVR_ATR_jobscript_max_size,
	SVR_ATR_restrict_res_to_release_on_suspend,
	SRV_ATR_PowerProvisioning,
	SRV_ATR_show_hidden_attribs,
	SRV_ATR_sync_mom_hookfiles_timeout,
	/* This must be last */
	SRV_ATR_LAST
};
extern attribute_def svr_attr_def[];

struct server {
	struct server_qs {
		int  sv_numjobs;	 /* number of job owned by server   */
		int  sv_numque;		/* nuber of queues managed          */
		int  sv_jobidnumber;	/* next number to use in new jobid  */
		time_t sv_savetm;	/* time of server db update         */
	} sv_qs;

	time_t	  sv_started;		/* time server started */
	time_t	  sv_hotcycle;		/* if RECOV_HOT,time of last restart */
	time_t	  sv_next_schedule;	/* when to next run scheduler cycle */
	int	  sv_jobstates[PBS_NUMJOBSTATE];  /* # of jobs per state */
	char	  sv_jobstbuf[150];
	char	  sv_license_ct_buf[150]; /* license_count buffer */
	int	  sv_nseldft;		/* num of elems in sv_seldft	    */
	key_value_pair *sv_seldft;	/* defelts for job's -l select	    */

	attribute sv_attr[SRV_ATR_LAST]; /* the server attributes 	    */

	int	  sv_trackmodifed;	/* 1 if tracking list modified	    */
	int	  sv_tracksize;		/* total number of sv_track entries */
	struct tracking *sv_track;	/* array of track job records	    */
	int	  sv_provtrackmodifed;	/* 1 if prov_tracking list modified */
	int	  sv_provtracksize; /* total number of sv_prov_track entries */
	struct prov_tracking *sv_prov_track; /* array of provision records */
	int	  sv_cur_prov_records; /* number of provisiong requests
					 currently running */
};


extern struct server	server;
extern	pbs_list_head	svr_alljobs;
extern	pbs_list_head	svr_newresvs;	/* incomming new reservations */
extern	pbs_list_head	svr_allresvs;	/* all reservations in server */
extern  int		svr_ping_rate;	/* time between rounds of ping */
extern  int 		ping_nodes_rate; /* time between ping nodes as determined from server_init_type */

/* degraded reservations globals */
extern	long	reserve_retry_init;
extern	long	reserve_retry_cutoff;


/*
 * server state values
 */
#define SV_STATE_DOWN    0
#define SV_STATE_INIT	 1
#define SV_STATE_HOT	 2
#define SV_STATE_RUN     3
#define SV_STATE_SHUTDEL 4
#define SV_STATE_SHUTIMM 5
#define SV_STATE_SHUTSIG 6
#define SV_STATE_SECIDLE 7
#define SV_STATE_PRIMDLY 0x10

/*
 * Other misc defines
 */
#define SVR_HOSTACL "svr_hostacl"
#define PBS_DEFAULT_NODE "1"

#define SVR_SAVE_QUICK 0
#define SVR_SAVE_FULL  1
#define SVR_SAVE_NEW   2

#define SVR_HOT_CYCLE	15	/* retry mom every n sec on hot start     */
#define SVR_HOT_LIMIT	300	/* after n seconds, drop out of hot start */

#define PBS_SCHED_DAEMON_NAME "Scheduler"
#define WALLTIME "walltime"
#define MIN_WALLTIME "min_walltime"
#define MAX_WALLTIME "max_walltime"
#define SOFT_WALLTIME "soft_walltime"
#define SVR_DEFAULT_PING_RATE 300

/*
 * Server failover role
 */
enum failover_state {
	FAILOVER_NONE,		/* Only Server, no failover */
	FAILOVER_PRIMARY,       /* Primary in failover configuration */
	FAILOVER_SECONDARY,	/* Secondary in failover */
	FAILOVER_CONFIG_ERROR,	/* error in configuration */
};

/*
 * Server job history defines & globals
 */
#define SVR_CLEAN_JOBHIST_TM	120	/* after 2 minutes, reschedule the work task */
#define SVR_CLEAN_JOBHIST_SECS	5	/* never spend more than 5 seconds in one sweep to clean hist */
#define SVR_JOBHIST_DEFAULT	1209600	/* default time period to keep job history: 2 weeks */

/* function prototypes */

extern int			svr_recov_db(void);
extern int			svr_save_db(struct server *, int mode);
extern int			sched_recov_db(void);
extern int			sched_save_db(pbs_sched *, int mode);
extern enum failover_state	are_we_primary(void);
extern int			have_socket_licensed_nodes(void);
extern void			unlicense_socket_licensed_nodes(void);
extern void			set_sched_default(pbs_sched *, int unset_flag);

#ifdef	__cplusplus
}
#endif
#endif	/* _SERVER_H */

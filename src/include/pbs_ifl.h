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
#ifndef _PBS_IFL_H
#define _PBS_IFL_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 *
 *  pbs_ifl.h
 *
 */

#include <stdio.h>
#include <time.h>

/* types of attributes: read only, public, all */
#define TYPE_ATTR_READONLY      1
#define TYPE_ATTR_PUBLIC        2
#define TYPE_ATTR_INVISIBLE		4
#define TYPE_ATTR_ALL           TYPE_ATTR_READONLY | TYPE_ATTR_PUBLIC | TYPE_ATTR_INVISIBLE

/* Attribute Names used by user commands */

#define ATTR_a "Execution_Time"
#define ATTR_c "Checkpoint"
#define ATTR_e "Error_Path"
#define ATTR_g	"group_list"
#define ATTR_h "Hold_Types"
#define ATTR_j "Join_Path"
#define ATTR_J "array_indices_submitted"
#define ATTR_k "Keep_Files"
#define ATTR_l "Resource_List"
#define ATTR_l_orig "Resource_List_orig"
#define ATTR_l_acct "Resource_List_acct"
#define ATTR_m "Mail_Points"
#define ATTR_o "Output_Path"
#define ATTR_p "Priority"
#define ATTR_q "destination"
#define ATTR_R "Remove_Files"
#define ATTR_r "Rerunable"
#define ATTR_u "User_List"
#define ATTR_v "Variable_List"
#define ATTR_A "Account_Name"
#define ATTR_M "Mail_Users"
#define ATTR_N "Job_Name"
#define ATTR_S "Shell_Path_List"
#define ATTR_array_indices_submitted ATTR_J
#define ATTR_depend		"depend"
#define ATTR_inter		"interactive"
#define ATTR_sandbox		"sandbox"
#define ATTR_stagein		"stagein"
#define ATTR_stageout		"stageout"
#define ATTR_resvTag		"reserve_Tag"
#define ATTR_resv_start 	"reserve_start"
#define ATTR_resv_end   	"reserve_end"
#define ATTR_resv_duration	"reserve_duration"
#define ATTR_resv_state		"reserve_state"
#define ATTR_resv_substate	"reserve_substate"
#define ATTR_auth_u		"Authorized_Users"
#define ATTR_auth_g		"Authorized_Groups"
#define ATTR_auth_h		"Authorized_Hosts"
#define ATTR_pwd		"pwd"
#define ATTR_cred		"cred"
#define ATTR_nodemux		"no_stdio_sockets"
#define ATTR_umask		"umask"
#define ATTR_block		"block"
#define ATTR_convert            "qmove"
#define ATTR_DefaultChunk	"default_chunk"
#define ATTR_X11_cookie         "forward_x11_cookie"
#define ATTR_X11_port           "forward_x11_port"
#define ATTR_GUI		"gui"

/* Begin Standing Reservation Attributes */
#define ATTR_resv_standing      "reserve_standing"
#define ATTR_resv_count         "reserve_count"
#define ATTR_resv_idx           "reserve_index"
#define ATTR_resv_rrule         "reserve_rrule"
#define ATTR_resv_execvnodes    "reserve_execvnodes"
#define ATTR_resv_timezone      "reserve_timezone"
/* End of standing reservation specific */

/* additional job and general attribute names */

#define ATTR_ctime	"ctime"
#define ATTR_estimated  "estimated"
#define ATTR_exechost	"exec_host"
#define ATTR_exechost_acct	"exec_host_acct"
#define ATTR_exechost_orig	"exec_host_orig"
#define ATTR_exechost2  "exec_host2"
#define ATTR_execvnode	"exec_vnode"
#define ATTR_execvnode_acct	"exec_vnode_acct"
#define ATTR_execvnode_deallocated	"exec_vnode_deallocated"
#define ATTR_execvnode_orig	"exec_vnode_orig"
#define ATTR_resv_nodes	"resv_nodes"
#define ATTR_mtime	"mtime"
#define ATTR_qtime	"qtime"
#define ATTR_session	"session_id"
#define ATTR_jobdir	"jobdir"
#define ATTR_euser	"euser"
#define ATTR_egroup	"egroup"
#define ATTR_project	"project"
#define ATTR_hashname	"hashname"
#define ATTR_hopcount	"hop_count"
#define ATTR_security	"security"
#define ATTR_sched_hint	"sched_hint"
#define ATTR_SchedSelect "schedselect"
#define ATTR_SchedSelect_orig "schedselect_orig"
#define ATTR_substate	"substate"
#define ATTR_name	"Job_Name"
#define ATTR_owner	"Job_Owner"
#define ATTR_used	"resources_used"
#define ATTR_used_acct	"resources_used_acct"
#define ATTR_used_update	"resources_used_update"
#define ATTR_relnodes_on_stageout	"release_nodes_on_stageout"
#define ATTR_tolerate_node_failures	"tolerate_node_failures"
#define ATTR_released	"resources_released"
#define ATTR_rel_list	"resource_released_list"
#define ATTR_state	"job_state"
#define ATTR_queue	"queue"
#define ATTR_server	"server"
#define ATTR_maxrun	"max_running"
#define ATTR_max_run		"max_run"
#define ATTR_max_run_res	"max_run_res"
#define ATTR_max_run_soft	"max_run_soft"
#define ATTR_max_run_res_soft	"max_run_res_soft"
#define ATTR_total	"total_jobs"
#define ATTR_comment	"comment"
#define ATTR_cookie	"cookie"
#define ATTR_qrank	"queue_rank"
#define ATTR_altid	"alt_id"
#define ATTR_altid2     "alt_id2"
#define ATTR_acct_id	"accounting_id"
#define ATTR_array	"array"
#define ATTR_array_id	"array_id"
#define ATTR_array_index		"array_index"
#define ATTR_array_state_count		"array_state_count"
#define ATTR_array_indices_remaining	"array_indices_remaining"
#define ATTR_etime		"etime"
#define ATTR_gridname		"gridname"
#define ATTR_refresh		"last_context_refresh"
#define ATTR_ReqCredEnable	"require_cred_enable"
#define ATTR_ReqCred		"require_cred"
#define ATTR_runcount	"run_count"
#define ATTR_run_version	"run_version"
#define ATTR_stime	"stime"
#define ATTR_pset	"pset"
#define ATTR_executable		"executable"
#define ATTR_Arglist		"argument_list"
#define	ATTR_version	"pbs_version"
#define ATTR_eligible_time	"eligible_time"
#define ATTR_accrue_type	"accrue_type"
#define ATTR_sample_starttime	"sample_starttime"
#define ATTR_job_kill_delay	"job_kill_delay"
#define ATTR_topjob_ineligible "topjob_ineligible"
#define ATTR_history_timestamp	"history_timestamp"
/* Added for finished jobs RFE */
#define ATTR_stageout_status    "Stageout_status"
#define ATTR_exit_status        "Exit_status"
#define ATTR_submit_arguments   "Submit_arguments"
/* additional Reservation attribute names */

#define ATTR_resv_name	 "Reserve_Name"
#define ATTR_resv_owner	 "Reserve_Owner"
#define ATTR_resv_type	 "reserve_type"
#define ATTR_resv_Tag	 "reservation_Tag"
#define ATTR_resv_ID	 "reserve_ID"
#define ATTR_resv_retry "reserve_retry"

/* additional queue attributes names */

#define ATTR_aclgren	"acl_group_enable"
#define ATTR_aclgroup	"acl_groups"
#define ATTR_aclhten	"acl_host_enable"
#define ATTR_aclhost	"acl_hosts"
#define ATTR_aclhostmomsen	"acl_host_moms_enable"
#define ATTR_acluren	"acl_user_enable"
#define ATTR_acluser	"acl_users"
#define ATTR_altrouter	"alt_router"
#define ATTR_chkptmin	"checkpoint_min"
#define ATTR_enable	"enabled"
#define ATTR_fromroute	"from_route_only"
#define ATTR_HasNodes	"hasnodes"
#define ATTR_killdelay	"kill_delay"
#define ATTR_maxgrprun  "max_group_run"
#define ATTR_maxgrprunsoft "max_group_run_soft"
#define ATTR_maxque	"max_queuable"
#define ATTR_max_queued		"max_queued"
#define ATTR_max_queued_res	"max_queued_res"
#define ATTR_queued_jobs_threshold	"queued_jobs_threshold"
#define ATTR_queued_jobs_threshold_res	"queued_jobs_threshold_res"
#define ATTR_maxuserrun "max_user_run"
#define ATTR_maxuserrunsoft "max_user_run_soft"
#define ATTR_qtype	"queue_type"
#define ATTR_rescassn	"resources_assigned"
#define ATTR_rescdflt	"resources_default"
#define ATTR_rescmax	"resources_max"
#define ATTR_rescmin	"resources_min"
#define ATTR_rndzretry  "rendezvous_retry"
#define ATTR_routedest	"route_destinations"
#define ATTR_routeheld	"route_held_jobs"
#define ATTR_routewait	"route_waiting_jobs"
#define ATTR_routeretry	"route_retry_time"
#define ATTR_routelife	"route_lifetime"
#define ATTR_rsvexpdt   "reserved_expedite"
#define ATTR_rsvsync    "reserved_sync"
#define ATTR_start	"started"
#define ATTR_count	"state_count"
#define ATTR_number	"number_jobs"
#define ATTR_jobscript_max_size "jobscript_max_size"
#ifdef NAS
/* localmod 046 */
#define	ATTR_maxstarve	"max_starve"
/* localmod 034 */
#define	ATTR_maxborrow	"max_borrow"
#endif

/* additional server attributes names */

#define ATTR_SvrHost	"server_host"
#define ATTR_aclroot	"acl_roots"
#define ATTR_managers	"managers"
#define ATTR_dfltque	"default_queue"
#define ATTR_defnode	"default_node"
#define ATTR_locsvrs	"location_servers"
#define ATTR_logevents	"log_events"
#define ATTR_logfile	"log_file"
#define ATTR_mailfrom	"mail_from"
#define ATTR_nodepack	"node_pack"
#define ATTR_nodefailrq "node_fail_requeue"
#define ATTR_operators	"operators"
#define ATTR_queryother	"query_other_jobs"
#define ATTR_resccost	"resources_cost"
#define ATTR_rescavail	"resources_available"
#define ATTR_maxuserres "max_user_res"
#define ATTR_maxuserressoft "max_user_res_soft"
#define ATTR_maxgroupres "max_group_res"
#define ATTR_maxgroupressoft "max_group_res_soft"
#define ATTR_maxarraysize "max_array_size"
#define ATTR_PNames	"pnames"
#define ATTR_schediteration	"scheduler_iteration"
#define ATTR_scheduling	"scheduling"
#define ATTR_status	"server_state"
#define ATTR_syscost	"system_cost"
#define ATTR_FlatUID	"flatuid"
#define ATTR_FLicenses	"FLicenses"
#define ATTR_ResvEnable	"resv_enable"
#define ATTR_aclResvgren        "acl_resv_group_enable"
#define ATTR_aclResvgroup       "acl_resv_groups"
#define ATTR_aclResvhten        "acl_resv_host_enable"
#define ATTR_aclResvhost        "acl_resv_hosts"
#define ATTR_aclResvuren        "acl_resv_user_enable"
#define ATTR_aclResvuser        "acl_resv_users"
#define ATTR_NodeGroupEnable	"node_group_enable"
#define ATTR_NodeGroupKey	"node_group_key"
#define ATTR_ssignon_enable	"single_signon_password_enable"
#define ATTR_dfltqdelargs	"default_qdel_arguments"
#define ATTR_dfltqsubargs       "default_qsub_arguments"
#define ATTR_rpp_retry		"rpp_retry"
#define ATTR_rpp_highwater	"rpp_highwater"
#define ATTR_license_location	"pbs_license_file_location"
#define ATTR_pbs_license_info	"pbs_license_info"
#define ATTR_license_min	"pbs_license_min"
#define ATTR_license_max	"pbs_license_max"
#define ATTR_license_linger	"pbs_license_linger_time"
#define ATTR_license_count	"license_count"
#define ATTR_job_sort_formula	"job_sort_formula"
#define ATTR_EligibleTimeEnable "eligible_time_enable"
#define ATTR_resv_retry_init       "reserve_retry_init"
#define ATTR_resv_retry_cutoff       "reserve_retry_cutoff"
#define ATTR_JobHistoryEnable	"job_history_enable"
#define ATTR_JobHistoryDuration	"job_history_duration"
#define ATTR_max_concurrent_prov	"max_concurrent_provision"
#define ATTR_resv_post_processing "resv_post_processing_time"
#define ATTR_backfill_depth     "backfill_depth"
#define ATTR_job_requeue_timeout "job_requeue_timeout"
#define ATTR_show_hidden_attribs "show_hidden_attribs"
#define ATTR_python_restart_max_hooks "python_restart_max_hooks"
#define ATTR_python_restart_max_objects "python_restart_max_objects"
#define ATTR_python_restart_min_interval "python_restart_min_interval"
#define ATTR_power_provisioning "power_provisioning"
#define ATTR_sync_mom_hookfiles_timeout "sync_mom_hookfiles_timeout"

/* additional scheduler "attribute" names */

#define ATTR_SchedHost	"sched_host"
#define ATTR_sched_cycle_len "sched_cycle_length"
#define ATTR_do_not_span_psets "do_not_span_psets"
#define ATTR_only_explicit_psets "only_explicit_psets"
#define ATTR_sched_preempt_enforce_resumption "sched_preempt_enforce_resumption"
#define ATTR_preempt_targets_enable "preempt_targets_enable"
#define ATTR_job_sort_formula_threshold "job_sort_formula_threshold"
#define ATTR_throughput_mode "throughput_mode"
#define ATTR_opt_backfill_fuzzy "opt_backfill_fuzzy"
#define ATTR_sched_port "sched_port"
#define ATTR_partition "partition"
#define ATTR_sched_priv "sched_priv"
#define ATTR_sched_log "sched_log"
#define ATTR_sched_user "sched_user"
#define ATTR_sched_state  "state"

/* additional node "attributes" names */

#define ATTR_NODE_Host		"Host" /* in 8.0, replaced with ATTR_NODE_Mom */
#define ATTR_NODE_Mom		"Mom"
#define ATTR_NODE_Port		"Port"
#define ATTR_NODE_state		"state"
#define ATTR_NODE_ntype         "ntype"
#define ATTR_NODE_jobs          "jobs"
#define ATTR_NODE_resvs         "resv"
#define ATTR_NODE_resv_enable   "resv_enable"
#define ATTR_NODE_np            "np"
#define ATTR_NODE_pcpus		"pcpus"
#define ATTR_NODE_properties	"properties"
#define ATTR_NODE_NoMultiNode	"no_multinode_jobs"
#define ATTR_NODE_No_Tasks	"no_tasks"
#define ATTR_NODE_Sharing	"sharing"
#define ATTR_NODE_ProvisionEnable	"provision_enable"
#define ATTR_NODE_current_aoe	"current_aoe"
#define ATTR_NODE_in_multivnode_host	"in_multivnode_host"
#define ATTR_NODE_License	"license"
#define ATTR_NODE_LicenseInfo	"license_info"
#define ATTR_NODE_TopologyInfo	"topology_info"
#define ATTR_NODE_MaintJobs	"maintenance_jobs"
#define ATTR_NODE_VnodePool	"vnode_pool"
#define ATTR_NODE_current_eoe   "current_eoe"
#define ATTR_NODE_power_provisioning   "power_provisioning"

/* Resource "attribute" names */
#define ATTR_RESC_TYPE		"type"
#define ATTR_RESC_FLAG		"flag"

/* various attribute values */

#define CHECKPOINT_UNSPECIFIED "u"
#define NO_HOLD "n"
#define NO_JOIN	"n"
#define NO_KEEP "n"
#define MAIL_AT_ABORT "a"


#define USER_HOLD "u"
#define OTHER_HOLD "o"
#define SYSTEM_HOLD "s"
#define BAD_PASSWORD_HOLD "p"

/* Add new MGR_CMDs before MGR_CMD_LAST */
enum mgr_cmd {
	MGR_CMD_NONE = -1,
	MGR_CMD_CREATE,
	MGR_CMD_DELETE,
	MGR_CMD_SET,
	MGR_CMD_UNSET,
	MGR_CMD_LIST,
	MGR_CMD_PRINT,
	MGR_CMD_ACTIVE,
	MGR_CMD_IMPORT,
	MGR_CMD_EXPORT,
	MGR_CMD_LAST
};

/* Add new MGR_OBJs before MGR_OBJ_LAST */
enum mgr_obj {
	MGR_OBJ_NONE = -1,
	MGR_OBJ_SERVER,		/* Server	*/
	MGR_OBJ_QUEUE,		/* Queue	*/
	MGR_OBJ_JOB,		/* Job		*/
	MGR_OBJ_NODE,		/* Vnode  	*/
	MGR_OBJ_RESV,		/* Reservation	*/
	MGR_OBJ_RSC,		/* Resource	*/
	MGR_OBJ_SCHED,		/* Scheduler	*/
	MGR_OBJ_HOST,		/* Host  	*/
	MGR_OBJ_HOOK,		/* Hook         */
	MGR_OBJ_PBS_HOOK,	/* PBS Hook     */
	MGR_OBJ_LAST		/* Last entry	*/
};

#define	MGR_OBJ_SITE_HOOK	MGR_OBJ_HOOK
#define	SITE_HOOK		"hook"
#define	PBS_HOOK		"pbshook"

/* Misc defines for various requests */
#define MSG_OUT		1
#define MSG_ERR		2


#define BLUEGENE		"bluegene"
/* SUSv2 guarantees that host names are limited to 255 bytes */
#define PBS_MAXHOSTNAME		255	/* max host name length */
#ifndef MAXPATHLEN
#define MAXPATHLEN		1024	/* max path name length */
#endif
#ifndef MAXNAMLEN
#define MAXNAMLEN		255
#endif
#define PBS_MAXSCHEDNAME 	15
#define PBS_MAXUSER		256	/* max user name length */
#define PBS_MAXPWLEN		256	/* max password length */
#define PBS_MAXGRPN		256	/* max group name length */
#define PBS_MAXQUEUENAME	15	/* max queue name length */
#define PBS_MAXJOBNAME 		236	/* max job name length */
#define PBS_MAXSERVERNAME	PBS_MAXHOSTNAME	/* max server name length */
#define PBS_MAXSEQNUM		7	/* max sequence number length */
#define PBS_MAXPORTNUM		5	/* udp/tcp port numbers max=16 bits */
#define PBS_MAXSVRJOBID		(PBS_MAXSEQNUM - 1 + PBS_MAXSERVERNAME + PBS_MAXPORTNUM + 2) /* server job id size, -1 to keep same length when made SEQ 7 */
#define PBS_MAXSVRRESVID	(PBS_MAXSVRJOBID)
#define PBS_MAXQRESVNAME	(PBS_MAXQUEUENAME)
#define PBS_MAXCLTJOBID		(PBS_MAXSVRJOBID + PBS_MAXSERVERNAME + PBS_MAXPORTNUM + 2) /* client job id size */
#define PBS_MAXDEST		256	/* destination size */
#define PBS_MAXROUTEDEST	(PBS_MAXQUEUENAME + PBS_MAXSERVERNAME + PBS_MAXPORTNUM + 2) /* destination size */
#define PBS_INTERACTIVE		1	/* Support of Interactive jobs */
#define PBS_TERM_BUF_SZ		80	/* Interactive term buffer size */
#define PBS_TERM_CCA		6	/* Interactive term cntl char array */
#define PBS_RESV_ID_CHAR	'R'	/* Character in front of a resv ID */
#define PBS_STDNG_RESV_ID_CHAR   'S'   /* Character in front of a resv ID */
#define PBS_AUTH_KEY_LEN    (129)

enum batch_op {	SET, UNSET, INCR, DECR,
	EQ, NE, GE, GT, LE, LT, DFLT
};

/* PBS supported authentication methods */
enum pbs_auth_method {
	AUTH_RESV_PORT,      /* Reserved port authentication */
	AUTH_MUNGE           /* MUNGE Authentication */
};

/* shutdown manners externally visible */
#define SHUT_IMMEDIATE	0
#define SHUT_DELAY	1
#define SHUT_QUICK	2

/* messages that may be passsed  by pbs_deljob() api to the server  via its extend parameter*/

#define FORCEDEL			"force"
#define NOMAIL  			"nomail"
#define SUPPRESS_EMAIL  		"suppress_email"
#define DELETEHISTORY		"deletehist"
/*
 ** This structure is identical to attropl so they can be used
 ** interchangably.  The op field is not used.
 */
struct attrl {
	struct attrl *next;
	char	     *name;
	char	     *resource;
	char	     *value;
	enum batch_op 	 op;	/* not used */
};

struct attropl {
	struct attropl	*next;
	char		*name;
	char		*resource;
	char		*value;
	enum batch_op 	 op;
};

struct batch_status {
	struct batch_status *next;
	char		    *name;
	struct attrl	    *attribs;
	char		    *text;
};

/* structure to hold an attribute that failed verification at ECL
 * and the associated errcode and errmsg
 */
struct ecl_attrerr {
	struct attropl *ecl_attribute;
	int             ecl_errcode;
	char           *ecl_errmsg;
};

/* structure to hold a number of attributes that failed verification */
struct ecl_attribute_errors {
	int     ecl_numerrors; /* num of attributes that failed verification */
	struct  ecl_attrerr *ecl_attrerr; /* ecl_attrerr array of structs */
};


/* Resource Reservation Information */
typedef int	pbs_resource_t;	/* resource reservation handle */

#define RESOURCE_T_NULL		(pbs_resource_t)0
#define RESOURCE_T_ALL		(pbs_resource_t)-1

enum resv_states { RESV_NONE, RESV_UNCONFIRMED, RESV_CONFIRMED, RESV_WAIT,
	RESV_TIME_TO_RUN, RESV_RUNNING, RESV_FINISHED,
	RESV_BEING_DELETED, RESV_DELETED, RESV_DELETING_JOBS, RESV_DEGRADED,
	RESV_BEING_ALTERED };

#ifdef _USRDLL		/* This is only for building Windows DLLs
			 * and not their static libraries
			 */

#ifdef DLL_EXPORT
#define DECLDIR __declspec(dllexport)
#else
#define DECLDIR __declspec(dllimport)
#endif

#ifndef __PBS_ERRNO
#define __PBS_ERRNO
DECLDIR int *__pbs_errno_location(void);
#define pbs_errno (*__pbs_errno_location ())
#endif

/* server attempted to connect | connected to */
/* see pbs_connect(3B)			      */
#ifndef __PBS_SERVER
#define __PBS_SERVER
DECLDIR char *__pbs_server_location(void);
#define pbs_server (__pbs_server_location ())
#endif

DECLDIR int pbs_asyrunjob(int, char *, char *, char *);

DECLDIR int pbs_alterjob(int, char *, struct attrl *, char *);

DECLDIR int pbs_connect(char *);

DECLDIR int pbs_connect_extend(char *, char *);

DECLDIR char *pbs_default(void);

DECLDIR int pbs_deljob(int, char *, char *);

DECLDIR int pbs_disconnect(int);

DECLDIR char *pbs_geterrmsg(int);

DECLDIR int pbs_holdjob(int, char *, char *, char *);

DECLDIR char *pbs_locjob(int, char *, char *);

DECLDIR int pbs_manager(int, int, int, char *, struct attropl *, char *);

DECLDIR int pbs_movejob(int, char *, char *, char *);

DECLDIR int pbs_msgjob(int, char *, int, char *, char *);

DECLDIR int pbs_relnodesjob(int, char *, char *, char *);

DECLDIR int pbs_orderjob(int, char *, char *, char *);

DECLDIR int pbs_rerunjob(int, char *, char *);

DECLDIR int pbs_rlsjob(int, char *, char *, char *);

DECLDIR int pbs_runjob(int, char *, char *, char *);

DECLDIR char **pbs_selectjob(int, struct attropl *, char *);

DECLDIR int pbs_sigjob(int, char *, char *, char *);

DECLDIR void pbs_statfree(struct batch_status *);

DECLDIR struct batch_status *pbs_statrsc(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_statjob(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_selstat(int, struct attropl *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_statque(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_statserver(int, struct attrl *, char *);

DECLDIR struct batch_status *pbs_statsched(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_stathost(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_statnode(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_statvnode(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_statresv(int, char *, struct attrl *, char *);

DECLDIR struct batch_status *pbs_stathook(int , char *, struct attrl *, char *);

DECLDIR struct ecl_attribute_errors * pbs_get_attributes_in_error(int);

DECLDIR char *pbs_submit(int, struct attropl *, char *, char *, char *);

DECLDIR char *pbs_submit_resv(int, struct attropl *, char *);

DECLDIR int pbs_delresv(int, char *, char *);

DECLDIR int pbs_terminate(int, int, char *);

DECLDIR char *pbs_modify_resv(int, char*, struct attropl *, char *);

#else

#ifndef __PBS_ERRNO
#define __PBS_ERRNO
extern int *__pbs_errno_location(void);
#define pbs_errno (*__pbs_errno_location ())
#endif

/* see pbs_connect(3B)			      */
#ifndef __PBS_SERVER
#define __PBS_SERVER
extern char *__pbs_server_location(void);
#define pbs_server (__pbs_server_location ())
#endif

extern int pbs_asyrunjob(int, char *, char *, char *);

extern int pbs_alterjob(int, char *, struct attrl *, char *);

extern int pbs_connect(char *);

extern int pbs_connect_extend(char *, char *);

extern int pbs_disconnect(int);

extern int pbs_manager(int, int, int, char *, struct attropl *, char *);

extern char *pbs_default(void);

extern int pbs_deljob(int, char *, char *);

extern char *pbs_geterrmsg(int);

extern int pbs_holdjob(int, char *, char *, char *);

extern char *pbs_locjob(int, char *, char *);

extern int pbs_movejob(int, char *, char *, char *);

extern int pbs_msgjob(int, char *, int, char *, char *);

extern int pbs_relnodesjob(int, char *,  char *, char *);

extern int pbs_orderjob(int, char *, char *, char *);

extern int pbs_rerunjob(int, char *, char *);

extern int pbs_rlsjob(int, char *, char *, char *);

extern int pbs_runjob(int, char *, char *, char *);

extern char **pbs_selectjob(int, struct attropl *, char *);

extern int pbs_sigjob(int, char *, char *, char *);

extern void pbs_statfree(struct batch_status *);

extern struct batch_status *pbs_statrsc(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_statjob(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_selstat(int, struct attropl *, struct attrl *, char *);

extern struct batch_status *pbs_statque(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_statserver(int, struct attrl *, char *);

extern struct batch_status *pbs_statsched(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_stathost(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_statnode(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_statvnode(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_statresv(int, char *, struct attrl *, char *);

extern struct batch_status *pbs_stathook(int, char *, struct attrl *, char *);

extern struct ecl_attribute_errors * pbs_get_attributes_in_error(int);

extern char *pbs_submit(int, struct attropl *, char *, char *, char *);

extern char *pbs_submit_resv(int, struct attropl *, char *);

extern int pbs_delresv(int, char *, char *);

extern int pbs_terminate(int, int, char *);

extern char *pbs_modify_resv(int, char*, struct attropl *, char *);
#endif /* _USRDLL */
#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_IFL_H */

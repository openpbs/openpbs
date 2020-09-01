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


#ifndef _CONFIG_H
#define _CONFIG_H

#include "constant.hpp"

/* the level of schd_priority that a suspended job has */
#define SUSPEND_PRIO 500000

/* resources can get too large for a 32 bit number, so the ability to use the
 * nonstandard type long long is necessary.
 */
#define RESOURCE_TYPE double

/* name of config file */
#define CONFIG_FILE "sched_config"
#define USAGE_FILE "usage"
#define USAGE_TOUCH USAGE_FILE ".touch"
#define HOLIDAYS_FILE "holidays"
#define RESGROUP_FILE "resource_group"
#define DEDTIME_FILE "dedicated_time"

/* usage file "magic number" - needs to be 8 chars */
#define USAGE_MAGIC "PBS_MAG!"
#define USAGE_VERSION 2
#define USAGE_NAME_MAX 50

#define UNKNOWN_GROUP_NAME "unknown"

/* preempt priority values */
#define PREEMPT_PRIORITY_HIGH 100000
#define PREEMPT_PRIORITY_STEP 1000

#define PREEMPT_ORDER_MAX 20

/* name of root node in the fairshare tree */
#define FAIRSHARE_ROOT_NAME "TREEROOT"

/* Estimate on how long it will take exiting jobs to end*/
#define EXITING_TIME 1

/* Estimate of time that a job past their walltime will be running */
#define FINISH_TIME 120

/* maximum number of sort keys */
#define MAX_SORTS 21

/* maximum number of scheduling cycle restarts in event of job-run failure */
#define MAX_RESTART_CYCLECNT  5

/* estimate of how long a node will take to provision - used in simulation */
#define PROVISION_DURATION 600

/* Maximum number of events(reservations or top jobs)
 * around which shrinking of a STF job would be attemtpted,
 */
#define SHRINK_MAX_RETRY 5

/* parsing -
 * names that appear on the left hand side in the sched config file
 */
#define PARSE_ROUND_ROBIN "round_robin"
#define PARSE_BY_QUEUE "by_queue"
#define PARSE_FAIR_SHARE "fair_share"
#define PARSE_HALF_LIFE "half_life"
#define PARSE_UNKNOWN_SHARES "unknown_shares"
#define PARSE_LOG_FILTER "log_filter"
#define PARSE_DEDICATED_PREFIX "dedicated_prefix"
#define PARSE_HELP_STARVING_JOBS "help_starving_jobs"
#define PARSE_MAX_STARVE "max_starve"
#define PARSE_SORT_QUEUES "sort_queues"
#define PARSE_BACKFILL "backfill"
#define PARSE_PRIMETIME_PREFIX "primetime_prefix"
#define PARSE_NONPRIMETIME_PREFIX "nonprimetime_prefix"
#define PARSE_BACKFILL_PRIME "backfill_prime"
#define PARSE_PRIME_EXEMPT_ANYTIME_QUEUES "prime_exempt_anytime_queues"
#define PARSE_PRIME_SPILL "prime_spill"
#define PARSE_RESOURCES "resources"
#define PARSE_MOM_RESOURCES "mom_resources"
#define PARSE_SMP_CLUSTER_DIST "smp_cluster_dist"
#define PARSE_PREEMPT_QUEUE_PRIO "preempt_queue_prio"
#define PARSE_PREEMPT_SUSPEND "preempt_suspend"
#define PARSE_PREEMPT_CHKPT "preempt_checkpoint"
#define PARSE_PREEMPT_REQUEUE "preempt_requeue"
#define PARSE_PREEMPIVE_SCHED "preemptive_sched"
#define PARSE_FAIRSHARE_RES "fairshare_usage_res"
#define PARSE_FAIRSHARE_ENT "fairshare_entity"
#define PARSE_FAIRSHARE_DECAY_FACTOR "fairshare_decay_factor"
#define PARSE_FAIRSHARE_DECAY_TIME "fairshare_decay_time"
#define PARSE_SUSP_THRESHOLD "susp_threshold"
#define PARSE_PREEMPT_PRIO "preempt_prio"
#define PARSE_PREEMPT_ORDER "preempt_order"
#define PARSE_PREEMPT_SORT "preempt_sort"
#define PARSE_JOB_SORT_KEY "job_sort_key"
#define PARSE_NODE_SORT_KEY "node_sort_key"
#define PARSE_SORT_NODES "sort_nodes"
#define PARSE_SERVER_DYN_RES "server_dyn_res"
#define PARSE_PEER_QUEUE "peer_queue"
#define PARSE_PEER_TRANSLATION "peer_translation"
#define PARSE_NODE_GROUP_KEY "node_group_key"
#define PARSE_DONT_PREEMPT_STARVING "dont_preempt_starving"
#define PARSE_ENFORCE_NO_SHARES "fairshare_enforce_no_shares"
#define PARSE_STRICT_ORDERING "strict_ordering"
#define PARSE_RES_UNSET_INFINITE "resource_unset_infinite"
#define PARSE_SELECT_PROVISION "provision_policy"

#ifdef NAS
/* localmod 034 */
#define	PARSE_MAX_BORROW "max_borrow"
#define	PARSE_SHARES_TRACK_ONLY "shares_track_only"
#define	PARSE_PER_SHARE_DEPTH	"per_share_depth"	/* old name */
#define	PARSE_PER_SHARE_TOPJOBS	"per_share_topjobs"

/* localmod 038 */
#define	PARSE_PER_QUEUES_TOPJOBS	"per_queues_topjobs"

/* localmod 030 */
#define	PARSE_MIN_INTERRUPTED_CYCLE_LENGTH	"min_interrupted_cycle_length"
#define	PARSE_MAX_CONS_INTERRUPTED_CYCLES	"max_cons_interrupted_cycles"
#endif

/* undocumented */
#define PARSE_MAX_JOB_CHECK "max_job_check"
#define PARSE_PREEMPT_ATTEMPTS "preempt_attempts"
#define PARSE_UPDATE_COMMENTS "update_comments"
#define PARSE_RESV_CONFIRM_IGNORE "resv_confirm_ignore"
#define PARSE_ALLOW_AOE_CALENDAR "allow_aoe_calendar"

/* deprecated */
#define PARSE_PREEMPT_STARVING "preempt_starving"
#define PARSE_PREEMPT_FAIRSHARE "preempt_fairshare"
#define PARSE_ASSIGN_SSINODES "assign_ssinodes"
#define PARSE_CPUS_PER_SSINODE "cpus_per_ssinode"
#define PARSE_MEM_PER_SSINODE "mem_per_ssinode"
#define PARSE_STRICT_FIFO "strict_fifo"



/* max sizes */
#define MAX_HOLIDAY_SIZE 50
#define MAX_DEDTIME_SIZE 50
#define MAX_SERVER_DYN_RES 201    /* 200 elements + 1 sentinel */
#define MAX_LOG_SIZE 1024
#define MAX_RES_NAME_SIZE 256
#define MAX_RES_RET_SIZE 256
#define NUM_PPRIO 20
#define NUM_PEERS 50
#define MAX_DEF_REPLY 5
#define MAX_PTIME_SIZE 64

/* resource names for sorting special cases */
#define SORT_FAIR_SHARE "fair_share_perc"
#define SORT_PREEMPT "preempt_priority"
#define SORT_PRIORITY "sort_priority"
#define SORT_JOB_PRIORITY "job_priority"
#define SORT_USED_TIME "last_used_time"

#ifdef NAS
/* localmod 039 */
#define SORT_QPRI "qpri"

/* localmod 034 */
#define SORT_ALLOC "cpu_alloc"

/* localmod 040 */
#define SORT_NODECT "nodect"
#endif

/* max num of retries for preemption */
#define MAX_PREEMPT_RETRIES     5

/* provisioning policy */
#define PROVPOLICY_AVOID "avoid_provision"
#define PROVPOLICY_AGGRESSIVE "aggressive_provision"

/* Job Comment Prefixes */
#define JOB_COMMENT_NOT_RUN_NOW "Not Running"
#define JOB_COMMENT_NEVER_RUN "Can Never Run"

#define BF_OFF 0
#define BF_LOW 60
#define BF_MED 600
#define BF_HIGH 3600
#define BF_DEFAULT BF_LOW

#define SCH_CYCLE_LEN_DFLT 1200

#ifdef NAS /* attributes we may define in the server's resourcedef file */
/* localmod 040 */
#define ATTR_ignore_nodect_sort "ignore_nodect_sort"

/* localmod 038 */
#define ATTR_topjob_setaside "topjob_set_aside"
#endif

#endif	/* _CONFIG_H */

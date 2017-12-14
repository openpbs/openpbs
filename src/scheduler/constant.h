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
#ifndef	_CONSTANT_H
#define	_CONSTANT_H
#ifdef	__cplusplus
extern "C" {
#endif

/* macro to turn a value from enum preempt into it's bit for the bitfield */
#define PREEMPT_TO_BIT(X) (1 << (X) )

/* bitcount macro for up to 16 bits */
#define BX16_(x)        ((x) - (((x)>>1)&0x7777) - (((x)>>2)&0x3333) - (((x)>>3)&0x1111))
#define BITCOUNT16(x)   (((BX16_(x)+(BX16_(x)>>4)) & 0x0F0F) % 255)

/* max between 0 or a number: basically don't let a number drop below 0 */
#define IF_NEG_THEN_ZERO(a) (((a)>=(0))?(a):(0))

/* multipliers [bw] means either btye or word */
#define KILO		1024UL		/* number of [bw] in a kilo[bw] */
#define MEGATOKILO	1024UL		/* number of mega[bw] in a kilo[bw] */
#define GIGATOKILO	1048576UL	/* number of giga[bw] in a kilo[bw] */
#define TERATOKILO	1073741824UL	/* number of tera[bw] in a kilo[bw] */

/* extra constants */
#define FREE_DEEP 1		/* constant to pass to free_*_list */
#define INITIALIZE -1

/* Constants used as flags to pass to next_job() function
 * Decision of Sorting jobs is taken on the basis of these constants */
enum sort_status
{
	DONT_SORT_JOBS,           /* If there is no need to sort in next_job() */
	MAY_RESORT_JOBS,       /* used to resort all jobs whenever needed */
	MUST_RESORT_JOBS,  /* used to resort all jobs mandatorily */
	SORTED             /* job list is already sorted */
};


/* enum used to find out what to skip while searching for the next job to schedule */

enum skip
{
	SKIP_NOTHING,
	/* Value used to know whether reservations are already scheduled or not */
	SKIP_RESERVATIONS,
	/* Value used to know whether express, preempted, starving jobs are already scheduled or not */
	SKIP_NON_NORMAL_JOBS
};

/* return value of select_index_to_preempt function */
enum select_job_status
{
	NO_JOB_FOUND = -1,	/* fails to find a job to preempt */
	ERR_IN_SELECT = -2	/* error while selecting a job to preempt */
};

#define INIT_ARR_SIZE 2048

/* Unspecified resource value */
#define UNSPECIFIED -1
#define UNSPECIFIED_STR "UNSPECIFIED"
/* infinity value for resources */
#define SCHD_INFINITY -2
#define SCHD_INFINITY_STR "SCHD_INFINITY"

/* infinity walltime value for forever job. This is 5 years(=60 * 60 * 24 * 365 * 5 seconds) */
#define JOB_INFINITY (60 * 60 * 24 * 365 * 5)

/* for filter functions */
#define FILTER_FULL	1	/* leave new array the full size */

/* for update_jobs_cant run */
#define START_BEFORE_JOB -1
#define START_WITH_JOB 0
#define START_AFTER_JOB 1

/* Error message when we fail to allocate memory */
#define MEM_ERR_MSG "Unable to allocate memory (malloc error)"

/* accrue types for update_accruetype */
#define ACCRUE_INIT     "0"
#define ACCRUE_INEL     "1"
#define ACCRUE_ELIG     "2"
#define ACCRUE_RUNN     "3"
#define ACCRUE_EXIT     "4"

/* operational modes for update_accruetype */
enum update_accruetype_mode
{
	ACCRUE_CHECK_ERR = 0,
	ACCRUE_MAKE_INELIGIBLE,
	ACCRUE_MAKE_ELIGIBLE
};

/* Default values for datatype resource */
#define RES_DEFAULT_AVAIL SCHD_INFINITY
#define RES_DEFAULT_ASSN 0

#define PREEMPT_QUEUE_SERVER_SOFTLIMIT (1 << (PREEMPT_OVER_QUEUE_LIMIT) | 1 << (PREEMPT_OVER_SERVER_LIMIT) )

/* strings for prime and non-prime */
#define PRIMESTR "primetime"
#define NONPRIMESTR "non-primetime"

/* dedtime_change */
#define DEDTIME_START "DEDTIME_START"
#define DEDTIME_END "DEDTIME_END"

/* comment prefixes */
#define NOT_RUN_PREFIX "Not Running"
#define NEVER_RUN_PREFIX "Can Never Run"

/* Time in seconds for 5 years */
#define FIVE_YRS 157680000

#define PREEMPT_NONE 1

/* resource comparison flag values */
enum resval_cmpflag
{
	CMP_CASE,
	CMP_CASELESS
};
/* return codes for is_ok_to_run_* functions
 * codes less then RET_BASE are standard PBSE pbs error codes
 * NOTE: RET_BASE MUST be greater than the highest PBSE error code
 */
enum sched_error
{
	RET_BASE = 16300,
	SUCCESS = RET_BASE + 1,
	SCHD_ERROR = RET_BASE + 2,
	NOT_QUEUED = RET_BASE + 3,
	QUEUE_NOT_STARTED = RET_BASE + 4,
	QUEUE_NOT_EXEC = RET_BASE + 5,
	QUEUE_JOB_LIMIT_REACHED = RET_BASE + 6,
	SERVER_JOB_LIMIT_REACHED = RET_BASE + 7,
	SERVER_USER_LIMIT_REACHED = RET_BASE + 8,
	QUEUE_USER_LIMIT_REACHED = RET_BASE + 9,
	SERVER_GROUP_LIMIT_REACHED = RET_BASE + 10,
	QUEUE_GROUP_LIMIT_REACHED = RET_BASE + 11,
	DED_TIME = RET_BASE + 12,
	CROSS_DED_TIME_BOUNDRY = RET_BASE + 13,
	NO_AVAILABLE_NODE = RET_BASE + 14, /* unused */
	NOT_ENOUGH_NODES_AVAIL = RET_BASE + 15,
	BACKFILL_CONFLICT = RET_BASE + 16,
	RESERVATION_INTERFERENCE = RET_BASE + 17,
	PRIME_ONLY = RET_BASE + 18,
	NONPRIME_ONLY = RET_BASE + 19,
	CROSS_PRIME_BOUNDARY = RET_BASE + 20,
	NODE_NONEXISTENT = RET_BASE + 21,
	NO_NODE_RESOURCES = RET_BASE + 22,
	CANT_PREEMPT_ENOUGH_WORK = RET_BASE + 23,
	QUEUE_USER_RES_LIMIT_REACHED = RET_BASE + 24,
	SERVER_USER_RES_LIMIT_REACHED = RET_BASE + 25,
	QUEUE_GROUP_RES_LIMIT_REACHED = RET_BASE + 26,
	SERVER_GROUP_RES_LIMIT_REACHED = RET_BASE + 27,
	NO_FAIRSHARES = RET_BASE + 28,
	INVALID_NODE_STATE = RET_BASE + 29,
	INVALID_NODE_TYPE = RET_BASE + 30,
	NODE_NOT_EXCL = RET_BASE + 31,
	NODE_JOB_LIMIT_REACHED = RET_BASE + 32,
	NODE_USER_LIMIT_REACHED = RET_BASE + 33,
	NODE_GROUP_LIMIT_REACHED = RET_BASE + 34,
	NODE_NO_MULT_JOBS = RET_BASE + 35,
	NODE_UNLICENSED = RET_BASE + 36,
	NODE_HIGH_LOAD = RET_BASE + 37,
	NO_SMALL_CPUSETS = RET_BASE + 38,
	INSUFFICIENT_RESOURCE = RET_BASE + 39,
	RESERVATION_CONFLICT = RET_BASE + 40,
	NODE_PLACE_PACK = RET_BASE + 41,
	NODE_RESV_ENABLE = RET_BASE + 42,
	STRICT_ORDERING = RET_BASE + 43,
	MAKE_ELIGIBLE = RET_BASE + 44, /* unused */
	MAKE_INELIGIBLE = RET_BASE + 45, /* unused */
	INSUFFICIENT_QUEUE_RESOURCE = RET_BASE + 46,
	INSUFFICIENT_SERVER_RESOURCE = RET_BASE + 47,
	QUEUE_BYGROUP_JOB_LIMIT_REACHED = RET_BASE + 48,
	QUEUE_BYUSER_JOB_LIMIT_REACHED = RET_BASE + 49,
	SERVER_BYGROUP_JOB_LIMIT_REACHED = RET_BASE + 50,
	SERVER_BYUSER_JOB_LIMIT_REACHED = RET_BASE + 51,
	SERVER_BYGROUP_RES_LIMIT_REACHED = RET_BASE + 52,
	SERVER_BYUSER_RES_LIMIT_REACHED = RET_BASE + 53,
	QUEUE_BYGROUP_RES_LIMIT_REACHED = RET_BASE + 54,
	QUEUE_BYUSER_RES_LIMIT_REACHED = RET_BASE + 55,
	QUEUE_RESOURCE_LIMIT_REACHED = RET_BASE + 56,
	SERVER_RESOURCE_LIMIT_REACHED = RET_BASE + 57,
	PROV_DISABLE_ON_SERVER = RET_BASE + 58,
	PROV_DISABLE_ON_NODE = RET_BASE + 59,
	AOE_NOT_AVALBL = RET_BASE + 60,
	EOE_NOT_AVALBL = RET_BASE + 61,
	PROV_BACKFILL_CONFLICT = RET_BASE + 62, /* unused */
	IS_MULTI_VNODE = RET_BASE + 63,
	PROV_RESRESV_CONFLICT = RET_BASE + 64,
	RUN_FAILURE = RET_BASE + 65,
	SET_TOO_SMALL = RET_BASE + 66,
	CANT_SPAN_PSET = RET_BASE + 67,
	NO_FREE_NODES = RET_BASE + 68,
	SERVER_PROJECT_LIMIT_REACHED = RET_BASE + 69,
	SERVER_PROJECT_RES_LIMIT_REACHED = RET_BASE + 70,
	SERVER_BYPROJECT_RES_LIMIT_REACHED = RET_BASE + 71,
	SERVER_BYPROJECT_JOB_LIMIT_REACHED = RET_BASE + 72,
	QUEUE_PROJECT_LIMIT_REACHED = RET_BASE + 73,
	QUEUE_PROJECT_RES_LIMIT_REACHED = RET_BASE + 74,
	QUEUE_BYPROJECT_RES_LIMIT_REACHED = RET_BASE + 75,
	QUEUE_BYPROJECT_JOB_LIMIT_REACHED = RET_BASE + 76,
	NO_TOTAL_NODES = RET_BASE + 77,
	INVALID_RESRESV = RET_BASE + 78,
	JOB_UNDER_THRESHOLD = RET_BASE + 79,
#ifdef NAS
	/* localmod 034 */
	GROUP_CPU_SHARE = RET_BASE + 80,
	GROUP_CPU_INSUFFICIENT = RET_BASE + 81,
	/* localmod 998 */
	RESOURCES_INSUFFICIENT = RET_BASE + 82,
#endif
	ERR_SPECIAL = RET_BASE + 1000
};

enum schd_err_status
{
	SCHD_UNKWN,
	NOT_RUN,
	NEVER_RUN,
	SCHD_STATUS_HIGH
};

/* for SORT_BY */
enum sort_type
{
	NO_SORT,
	SHORTEST_JOB_FIRST,
	LONGEST_JOB_FIRST,
	SMALLEST_MEM_FIRST,
	LARGEST_MEM_FIRST,
	HIGH_PRIORITY_FIRST,
	LOW_PRIORITY_FIRST,
	LARGE_WALLTIME_FIRST,
	SHORT_WALLTIME_FIRST,
	FAIR_SHARE,
	PREEMPT_PRIORITY,
	MULTI_SORT
};

#ifdef FALSE
#undef FALSE
#endif

#ifdef TRUE
#undef TRUE
#endif


/* Reservation related constants */
#define MAXVNODELIST 100

enum resv_conf {
	RESV_CONFIRM_FAIL = -1,
	RESV_CONFIRM_VOID ,
	RESV_CONFIRM_SUCCESS,
	RESV_CONFIRM_RETRY
};

/* job substate meaning suspended by scheduler */
#define SUSP_BY_SCHED_SUBSTATE "45"

/* job substate meaning node is provisioning */
#define PROVISIONING_SUBSTATE "71"

/* TRUE_FALSE indicates both true and false for collections of resources */
enum { FALSE, TRUE, TRUE_FALSE };

enum { RUN_JOBS_SORTED = 1, SIM_RUN_JOB = 2 };
enum { SIMULATE_SD = -1 };

enum fairshare_flags
{
	FS_TRIM = 1
};

/* flags used for copy constructors - bit field */
enum dup_flags
{
	DUP_LOW = 0,
	DUP_INDIRECT = 1
	/* next flag 2 then 4, the 8... */
};

/* an enum of 1-off names */
enum misc_constants
{
	NO_FLAGS = 0,
	IGNORE_DISABLED_EVENTS = 1,
	FORCE,
	ALL_MASK = 0xffffffff
};

enum advance
{
	DONT_ADVANCE,
	ADVANCE
};

/* resource list flags is a bitfield = 0, 1, 2, 4, 8...*/
enum add_resource_list_flags
{
	NO_UPDATE_NON_CONSUMABLE = 1,
	USE_RESOURCE_LIST = 2,
	ADD_UNSET_BOOLS_FALSE = 4,
	ADD_AVAIL_ASSIGNED = 8
	/* next flag 16 */
};

/* run update resresv flags is a bitfield = 0, 1, 2, 4, 8, ...*/
enum run_update_resresv_flags
{
	RURR_NO_FLAGS = 0,
	RURR_ADD_END_EVENT = 1, /* add end events to calendar for job */
	RURR_NOPRINT = 2       /* don't print messages */
	/* next value 4 */
};

enum delete_event_flags
{
	DE_NO_FLAGS = 0,
	DE_UNLINK = 1
	/* next flag 2, 4, 8, 16, ...*/
};

enum res_print_flags
{
	PRINT_INT_CONST = 1,
	NOEXPAND = 2
	/* next flex 4, 8, 16, ...*/
};

enum is_provisionable_ret
{
	NOT_PROVISIONABLE,
	NO_PROVISIONING_NEEDED,
	PROVISIONING_NEEDED
};


enum sort_order
{
	NO_SORT_ORDER,
	DESC,			/* decending i.e. 4 3 2 1 */
	ASC			/* ascending i.e. 1 2 3 4 */
};

enum cmptype
{
	CMPAVAIL,
	CMPTOTAL
};

enum match_string_array_ret
{
	SA_NO_MATCH,		/* no match */
	SA_PARTIAL_MATCH,	/* at least one match */
	SA_SUB_MATCH,		/* one array is a subset of the other */
	SA_FULL_MATCH	/* both arrays are the same size and match */
};

enum prime_time
{
	NON_PRIME = 0,
	PRIME = 1,
	ALL,
	NONE,
	HIGH_PRIME
};

enum days
{
	SUNDAY,
	MONDAY,
	TUESDAY,
	WEDNESDAY,
	THURSDAY,
	FRIDAY,
	SATURDAY,
	WEEKDAY,
	HIGH_DAY
};

enum smp_cluster_dist
{
	SMP_NODE_PACK,
	SMP_ROUND_ROBIN,
	SMP_LOWEST_LOAD,
	HIGH_SMP_DIST
};

/*
 *	When adding entries to this enum, be sure to initialize a matching
 *	entry in prempt_prio_info[] (globals.c).
 */
enum preempt
{
	PREEMPT_NORMAL,		/* normal priority jobs */
	PREEMPT_OVER_FS_LIMIT,	/* jobs over their fairshare of the machine */
	PREEMPT_OVER_QUEUE_LIMIT,	/* jobs over queue run limits (maxrun etc) */
	PREEMPT_OVER_SERVER_LIMIT,	/* jobs over server run limits */
	PREEMPT_STARVING,		/* starving jobs */
	PREEMPT_EXPRESS,		/* jobs in express queue */
	PREEMPT_QRUN,			/* job is being qrun */
	PREEMPT_ERR,			/* error occurred during preempt computation */
	PREEMPT_HIGH
};

enum preempt_method
{
	PREEMPT_METHOD_LOW,
	PREEMPT_METHOD_SUSPEND,
	PREEMPT_METHOD_CHECKPOINT,
	PREEMPT_METHOD_REQUEUE,
	PREEMPT_METHOD_HIGH
};

enum schd_simulate_cmd
{
	SIM_NONE,
	SIM_NEXT_EVENT,
	SIM_TIME
};

enum timed_event_types
{
	TIMED_NOEVENT = 1,
	TIMED_ERROR = 2,
	TIMED_RUN_EVENT = 4,
	TIMED_END_EVENT = 8,
	TIMED_POLICY_EVENT = 16,
	TIMED_DED_START_EVENT = 32,
	TIMED_DED_END_EVENT = 64,
	TIMED_NODE_DOWN_EVENT = 128,
	TIMED_NODE_UP_EVENT = 256
};

enum resource_fields
{
	RF_NONE,
	RF_AVAIL,             /* resources_available - if indirect, resolve */
	RF_DIRECT_AVAIL,      /* resources_available - if indirect, return @vnode */
	RF_ASSN,
	RF_REQUEST,
	RF_UNUSED		/* meta field: RF_AVAIL - RF_ASSN: used for sorting */
};

/* bit fields */
enum node_eval
{
	EVAL_LOW = 0,
	EVAL_OKBREAK = 1,		/* OK to break chunk up across placement set */
	EVAL_EXCLSET = 2		/* allocate entire placement set exclusively */
	/* next 4, then 8, etc */
};

enum nodepart
{
	NP_LOW = 0,
	NP_IGNORE_EXCL = 1,
	NP_CREATE_REST = 2
	/* next 4, 8, etc */
};

/* It is used to identify the provisioning policy set on scheduler */
enum provision_policy_types
{
	AGGRESSIVE_PROVISION = 0,
	AVOID_PROVISION = 1
};

enum sort_obj_type
{
	SOBJ_JOB,
	SOBJ_NODE,
	SOBJ_PARTITION,
};

enum update_sort_defs
{
	SD_FREE,
	SD_UPDATE
};

enum update_attr_flags
{
	UPDATE_FLAGS_LOW = 0,
	UPDATE_LATER = 1,
	UPDATE_NOW = 2,
	/* Bit Field, next 4, then 8 */
};

/* static indexes into the allres resdef array for built in resources.  It is
 * likely that the query_rsc() API call will return the resources in the order
 * of the server's resc_def_all array.  It is marginally faster if we try and
 * keep this array in the same order.  There is no dependency on this ordering
 */
enum resource_index
{
	RES_CPUT,
	RES_MEM,
	RES_WALLTIME,
	RES_SOFT_WALLTIME,
	RES_NCPUS,
	RES_ARCH,
	RES_HOST,
	RES_VNODE,
	RES_AOE,
	RES_EOE,
	RES_MIN_WALLTIME,
	RES_MAX_WALLTIME,
	RES_PREEMPT_TARGETS,
	RES_HIGH
};

/* Flags for is_ok_to_run() and the check functions called by it */
enum check_flags {
	CHECK_FLAGS_LOW,
	RETURN_ALL_ERR = 1,
	CHECK_LIMIT = 2,		/* for check_limits */
	CHECK_CUMULATIVE_LIMIT = 4,	/* for check_limits */
	CHECK_ALL_BOOLS = 8,
	UNSET_RES_ZERO = 16,
	COMPARE_TOTAL = 32,
	ONLY_COMP_NONCONS = 64,
	ONLY_COMP_CONS = 128,
	IGNORE_EQUIV_CLASS = 256
	/* next flag 512 */
};

enum schd_error_args {
	ARG1,
	ARG2,
	ARG3,
	SPECMSG
};

#ifdef	__cplusplus
}
#endif
#endif	/* _CONSTANT_H */

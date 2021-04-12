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

#include <pbs_config.h>

#include <stdio.h>
#include <pthread.h>
#include <limits.h>

#include "globals.h"
#include "constant.h"
#include "sort.h"
#include "config.h"
#include "data_types.h"
#include "queue.h"





/**
 * @file    globals.c
 *
 * @brief
 *	sorting_info[] - holds information about all the different ways you
 *			 can sort the jobs
 * @par
 *	Format: { sort_type, config_name, cmp_func_ptr }
 * @par
 *	sort_type    : an element from the enum sort_type
 *	config_name  : the name which appears in the scheduling policy config
 *		         file (sched_config)
 *	cmp_func_ptr : function pointer the qsort compare function
 *			 (located in sort.c)
 *
 */

const struct sort_conv sort_convert[] =
	{
	{"shortest_job_first", "cput", ASC},
	{"longest_job_first", "cput", DESC},
	{"smallest_memory_first", "mem", ASC},
	{"largest_memory_first", "mem", DESC},
	{"high_priority_first", SORT_PRIORITY, DESC},
	{"low_priority_first", SORT_PRIORITY, ASC},
	{"large_walltime_first", "walltime", DESC},
	{"short_walltime_first", "walltime", ASC},
	{"fair_share", SORT_FAIR_SHARE, ASC},
	{"preempt_priority", SORT_PREEMPT, DESC},
	{NULL, NULL, NO_SORT_ORDER}
};


/*
 * 	smp_cluster_info - used to convert parse values into enum
 */
const struct enum_conv smp_cluster_info[] =
	{
	{ SMP_NODE_PACK, "pack" },
	{ SMP_ROUND_ROBIN, "round_robin" },
	{ HIGH_SMP_DIST, "" }
};

/*
 *	prempt_prio_info - used to convert parse values into enum values
 *			   for preemption priority levels
 *
 */
const struct enum_conv preempt_prio_info[] =
	{
	{ PREEMPT_NORMAL, "normal_jobs" },
	{ PREEMPT_OVER_FS_LIMIT, "fairshare" },
	{ PREEMPT_OVER_QUEUE_LIMIT, "queue_softlimits" },
	{ PREEMPT_OVER_SERVER_LIMIT, "server_softlimits" },
	{ PREEMPT_STARVING, "starving_jobs" },
	{ PREEMPT_EXPRESS, "express_queue" },
	{ PREEMPT_ERR, "" },			/* no corresponding config file value */
	{ PREEMPT_HIGH, "" }
};

/* Used to create static indexes into allres */
const struct enum_conv resind[] =
	{
	{RES_CPUT, "cput"},
	{RES_MEM, "mem"},
	{RES_WALLTIME, "walltime"},
	{RES_SOFT_WALLTIME, "soft_walltime"},
	{RES_NCPUS, "ncpus"},
	{RES_ARCH, "arch"},
	{RES_HOST, "host"},
	{RES_VNODE, "vnode"},
	{RES_AOE, "aoe"},
	{RES_EOE, "eoe"},
	{RES_MIN_WALLTIME, "min_walltime"},
	{RES_MAX_WALLTIME, "max_walltime"},
	{RES_PREEMPT_TARGETS, "preempt_targets"},
	{RES_HIGH, ""}
};

struct config conf;
struct status cstat;

/* to make references happy */
int got_sigpipe;

/* Each index of the array is a sched command. Store 1 as a value to indicate that we received a command */
int sched_cmds[SCH_CMD_HIGH];

/* This list stores SCH_SCHEDULE_AJOB commands */
sched_cmd *qrun_list;
int qrun_list_size;

void *poll_context = NULL;

/* Stuff needed for multi-threading */
pthread_mutex_t general_lock;
pthread_mutex_t work_lock;
pthread_mutex_t result_lock;
pthread_cond_t work_cond;
pthread_cond_t result_cond;
ds_queue *work_queue = NULL;
ds_queue *result_queue = NULL;
pthread_t *threads = NULL;
int threads_die = 0;
int num_threads = 0;
pthread_key_t th_id_key;
pthread_once_t key_once = PTHREAD_ONCE_INIT;

/* resource definitions from the server */

/* all resources */
resdef **allres = NULL;
/* consumable resources */
resdef **consres = NULL;
/* boolean resources*/
resdef **boolres = NULL;

/* AOE name used to compare nodes, free when exit cycle */
char *cmp_aoename = NULL;

const char *sc_name = NULL;
char *logfile = NULL;

unsigned int preempt_normal;			/* preempt priority of normal_jobs */

char path_log[_POSIX_PATH_MAX];
int dflt_sched = 0;

struct schedattrs sc_attrs;

time_t last_attr_updates = 0;

int send_job_attr_updates = 1;

/* primary socket descriptor to the server pool */
int clust_primary_sock = -1;

/* secondary socket descriptor to the server pool */
int clust_secondary_sock = -1;

/* a list of running jobs from the last scheduling cycle */
std::vector<prev_job_info> last_running;

/* fairshare tree */
fairshare_head *fstree;

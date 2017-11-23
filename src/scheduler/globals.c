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
#include <pbs_config.h>

#include <stdio.h>
#include "globals.h"
#include "constant.h"
#include "sort.h"
#include "limits.h"



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
	{ SMP_LOWEST_LOAD, "lowest_load", },
	{ HIGH_SMP_DIST, "" }
};

/*
 *	prempt_prio_info - used to convert parse values into enum values
 *			   for preemption priority levels
 */
const struct enum_conv prempt_prio_info[] =
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


/*
 *	res_to_get - resources to get from each nodes mom
 */
const char *res_to_get[] =
	{
	"loadave",		/* the current load average */
	"max_load",		/* static max_load value */
	"ideal_load",		/* static ideal_load value */
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

/* number of indices in the res_to_get array */
const int num_resget = sizeof(res_to_get) / sizeof(char *);

struct config conf;
struct status cstat;

/* to make references happy */
int pbs_rm_port;
int got_sigpipe;

int	second_connection;

/* resource definitions from the server */

/* all resources */
resdef **allres = NULL;
/* consumable resources */
resdef **consres = NULL;
/* boolean resources*/
resdef **boolres = NULL;

/* AOE name used to compare nodes, free when exit cycle */
char *cmp_aoename = NULL;

char *partitions = NULL;
char scheduler_host_name[PBS_MAXHOSTNAME+1] = "Me";  /*arbitrary string*/
char *sc_name = NULL;
int sched_port = -1;
char *logfile = (char *)0;
#ifdef WIN32
char path_log[_MAX_PATH];
#else
char path_log[_POSIX_PATH_MAX];
#endif
int dflt_sched = 0;

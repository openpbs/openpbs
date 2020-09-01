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

/*
 *=====================================================================
 * site_code.c - Code to implement site-specific scheduler functions
 *=====================================================================
 */

#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <pbs_error.h>
#include <pbs_ifl.h>
#include <regex.h>
#include <sched_cmds.h>
#include <time.h>
#include <limits.h>
#include <assert.h>
#include "log.h"
#include "data_types.hpp"
#include "fifo.hpp"
#include "queue_info.hpp"
#include "server_info.hpp"
#include "node_info.hpp"
#include "check.hpp"
#include "constant.hpp"
#include "job_info.hpp"
#include "misc.hpp"
#include "config.hpp"
#include "sort.hpp"
#include "parse.hpp"
#include "globals.hpp"
#include "prev_job_info.hpp"
#include "fairshare.hpp"
#include "prime.hpp"
#include "dedtime.hpp"
#include "resv_info.hpp"
#include "range.h"
#include "resource.hpp"
#include "resource_resv.hpp"
#include "simulate.hpp"

#ifdef NAS

#include "site_data.hpp"
#include "site_code.hpp"
#include "site_queue.h"

#define TJ_COST_MAX	10.0	/* Max CPU to spend searching for top jobs */
/* Global NAS variables */
/* localmod 030 */
int do_soft_cycle_interrupt;
int do_hard_cycle_interrupt;
int consecutive_interrupted_cycles = 0;
time_t interrupted_cycle_start_time;
/* localmod 038 */
int num_topjobs_per_queues;      /* # of per_queues top jobs on the calendar */

struct	shr_type {
	struct shr_type	*next;
	int		sh_tidx;	/* type index */
	int		sh_cls;		/* index into sh_amt arrays */
	int		cpus_per_node;	/* guess as to CPUs per node of type */
	char		name[4];	/* actually as long as needed */
};
struct	shr_class {
	struct shr_class *next;
	int		sh_cls;		/* index into sh_amt arrays */
	char		name[4];	/* actually as long as needed */
};

static void bump_share_count(share_info *, enum site_j_share_type, sh_amt *, int);
static void bump_demand_count(share_info *, enum site_j_share_type, sh_amt *, int);
static void clear_topjob_counts(share_info* root);
static int check_cpu_share(share_head* sh, resource_resv* resv);
static void count_active_cpus(resource_resv **, int, sh_amt *);
static void count_demand_cpus(resource_resv **, int);
static void count_contrib_cpus(share_info *, share_info *, sh_amt *);
static void count_cpus(node_info **, int ncnt, queue_info **, sh_amt *);
static void set_share_cpus(share_info *node, sh_amt *, sh_amt *);
static void zero_share_counts(share_info *node);

static int dup_shares(share_head *oldsh, server_info *nsinfo);
static share_info *dup_share_tree(share_info *oroot);
static share_info *find_entity_share(char *name, share_info *node);
static share_info *find_most_favored_share(share_info* root, int topjobs);
static int find_share_class(struct shr_class *head, char *name);
static share_info *find_share_group(share_info *root, char *name);
static site_user_info *find_user(site_user_info **head, char *name);
/* static int find_share_type(struct shr_type *head, char *name); */
static void free_share_head(share_head *sh, int flag);
static void free_share_tree(share_info *root);
static void free_users(site_user_info **);
static double get_share_ratio(sh_amt*, sh_amt*, sh_amt_array*);
static int init_users(server_info *);
static void list_share_info(FILE *, share_info *, const char *, int, const char *, int);
static struct share_head* new_share_head(int cnt);
static share_info* new_share_info(char *name, int cnt);
static share_info* new_share_info_clone(share_info *old);
static int reconcile_shares(share_info *root, int cnt);
static int reconcile_share_tree(share_info *root, share_info *def, int cnt);
/* static struct shr_class* shr_class_info_by_idx(int); */
/* static struct shr_class* shr_class_info_by_name(const char *); */
static char* shr_class_name_by_idx(int);
/* static struct shr_class* shr_class_info_by_type_name(const char *); */
static struct shr_type* shr_type_info_by_idx(int);
static struct shr_type* shr_type_info_by_name(const char *);
static void squirrel_shr_head(server_info *sinfo);
static void un_squirrel_shr_head(server_info *sinfo);
static void squirrel_shr_tree(share_info *root);
static void un_squirrel_shr_tree(share_info *root);

typedef		int (pick_next_filter)(resource_resv *, share_info *);

static resource_resv* pick_next_job(status *, resource_resv **, int (*)(), share_info *);

#ifdef	NAS_HWY149
static int job_filter_hwy149(resource_resv *, share_info *);
#endif
static int job_filter_dedres(resource_resv *, share_info *);
#ifdef	NAS_HWY101
static int job_filter_hwy101(resource_resv *, share_info *);
#endif
static int job_filter_normal(resource_resv *, share_info *);

/*
 * Private variables used by CPU allocations code
 */

static	struct shr_class *shr_classes = NULL;
static	int		shr_class_count = 0;
static	struct shr_type	*shr_types = NULL;
static	int		shr_type_count = 0;
static	char		*shr_selector = NULL;
static	share_head	*cur_shr_head = NULL;

/*
 * Other private variables
 */
static	site_user_info	*users = NULL;

/*
 *=====================================================================
 * External functions
 *=====================================================================
 */



/*
 *=====================================================================
 * site_bump_topjobs(resv, delta) - Increment topjob count for job's
 *	share group
 * Entry:	resv = resource_resv for job
 *		delta = CPU time needed to calendar the job
 * Returns:	new value for topjob count
 *=====================================================================
 */
int
site_bump_topjobs(resource_resv *resv, double delta)
{
	job_info*	job;
	share_info*	si;

	if (resv == NULL || !resv->is_job || (job = resv->job) == NULL)
		return 0;
	if ((si = job->sh_info) == NULL || (si = si->leader) == NULL)
		return 0;
	si->tj_cpu_cost += delta;
#ifdef NAS_DEBUG
	printf("YYY %s %d %g %g %g\n", si->name, si->topjob_count+1,
		si->ratio, si->ratio_max, si->tj_cpu_cost);
	fflush(stdout);
#endif
	return ++(si->topjob_count);
}



/*
 *=====================================================================
 * site_check_cpu_share(sinfo, resv) - Check whether job
 *			would exceed any group CPU allocation.
 * Entry:	sinfo = Server info
 *		policy = policy in effect at current time
 *		resv = job/reservation
 * Returns:	0 if job not blocked
 *		<> if blocked by group CPU allocation
 *=====================================================================
 */
int
site_check_cpu_share(server_info *sinfo, status *policy, resource_resv *resv)
{
	int		rc = 0;		/* Assume okay */
	job_info	*job;
	share_head	*sh;		/* global share totals */
	timed_event	*te;
	long		time_left, end;
	unsigned int	event_mask;

	if (sinfo == NULL || policy == NULL || resv == NULL)
		return 0;
	if (!resv->is_job || (job = resv->job) == NULL)
		return 0;
	if ((sh = sinfo->share_head) == NULL)
		return 0;
	/* Allow accumulating shares, but not enforcing them */
	if (policy->shares_track_only)
		return 0;
	/*
	 * Skip rest if job exempt from limits
	 */
	if (resv->share_type == J_TYPE_ignore)
		return 0;
#ifdef	NAS_HWY149
	if (job->NAS_pri == NAS_HWY149)
		return 0;
#endif
#ifdef	NAS_HWY101
	if (job->NAS_pri == NAS_HWY101)
		return 0;
#endif
	if (job->resv != NULL)
		return 0;		/* job running in reservation */

	rc = check_cpu_share(sh, resv);
	if (rc != 0) {
		/*
		 * Job cannot run now
		 */
		return rc;
	}
	/*
	 * See if would conflict with anything on calendar
	 */
	if (sinfo->calendar == NULL)
		return rc;
	time_left = calc_time_left(resv, 0);
	end = sinfo->server_time + time_left;
	if (!exists_run_event(sinfo->calendar, end))
		return rc;
	squirrel_shr_head(sinfo);
	te = get_next_event(sinfo->calendar);
	event_mask = TIMED_RUN_EVENT | TIMED_END_EVENT;
	for (te = find_init_timed_event(te, IGNORE_DISABLED_EVENTS, event_mask);
		te != NULL && te->event_time < end;
		te = find_next_timed_event(te, IGNORE_DISABLED_EVENTS, event_mask)) {

		resource_resv *te_rr;

		te_rr = (resource_resv *) te->event_ptr;
		if (te_rr == resv)
			continue;		/* Should not happen */
		if (te->event_type == TIMED_RUN_EVENT) {
			site_update_on_run(sinfo, NULL, te_rr, 0, NULL);
			rc = check_cpu_share(sh, resv);
			if (rc != 0) {
				rc = BACKFILL_CONFLICT;
				break;
			}
		}
		if (te->event_type == TIMED_END_EVENT) {
			site_update_on_end(sinfo, NULL, te_rr);
			/* Next test should never catch anything */
			rc = check_cpu_share(sh, resv);
			if (rc != 0) {
				rc = BACKFILL_CONFLICT;
				break;
			}
		}
	}
	un_squirrel_shr_head(sinfo);
	return rc;
}



/*
 *=====================================================================
 * check_cpu_share(sinfo, resv) - Check whether job would exceed CPU
 *		shares at this instant in time.
 * Entry:	sh = global share totals
 *		resv = resource reservation to check
 *=====================================================================
 */
static int
check_cpu_share(share_head *sh, resource_resv *resv)
{
	int		rc = 0;		/* Assume okay */
	job_info	*job;
	share_info	*leader;	/* info for group leader */
	int		sh_cls;		/* current share class */
	sh_amt		*job_amts;	/* amounts requested by job */

	if (sh == NULL || resv == NULL)
		return rc;
	if ((job = resv->job) == NULL)
		return rc;
	leader = job->sh_info;
	if (leader == NULL || (leader = leader->leader) == NULL)
		return 0;
	job_amts = job->sh_amts;
	if (job_amts == NULL)
		return 0;
	/*
	 * Precedence of blockages: high to low
	 * GROUP_CPU_INSUFFICIENT
	 * GROUP_CPU_SHARE
	 * none
	 */
	for (sh_cls = 0; sh_cls < shr_class_count ; ++sh_cls) {
		int limited, borrowed, allocated;
		int asking;
		int rc2 = 0;

		asking = job_amts[sh_cls];
#if	NAS_CPU_MULT > 1
		if (asking % NAS_CPU_MULT) {
			/*
			 * Round to multiple of NAS_CPU_MULT
			 */
			asking += NAS_CPU_MULT - (asking % NAS_CPU_MULT);
		}
#endif
		limited = leader->share_inuse[sh_cls][J_TYPE_limited];
		borrowed = leader->share_inuse[sh_cls][J_TYPE_borrow];
		allocated = leader->share_ncpus[sh_cls];

		switch (resv->share_type) {
			case J_TYPE_limited:
				/*
				 * If job exceeds share by itself
				 */
				if (asking > allocated) {
					rc2 = GROUP_CPU_INSUFFICIENT;
					break;
				}
				/*
				 * If total limited jobs would exceed share
				 */
				if (asking + limited > allocated) {
					rc2 = GROUP_CPU_SHARE;
					break;
				}
				/* Fall through */
			case J_TYPE_borrow:
				/*
				 * Have we borrowed too much
				 */
				if (asking + limited + borrowed >
					allocated + sh->sh_contrib[sh_cls]) {
					rc2 = GROUP_CPU_SHARE;
					break;
				}
				break;
			default:
				;
		}
		/*
		 * Remember most important limit among shares
		 */
		if (rc == 0 || rc2 == GROUP_CPU_INSUFFICIENT) rc = rc2;
	}
	return rc;
}



/*
 *=====================================================================
 * site_decode_time(str) - decode time string
 * (Based on decode_time in attr_fn_time.c)
 * Entry:	str = string in hh:mm:ss format
 * Returns:	value of str in seconds
 *=====================================================================
 */
#define PBS_MAX_TIME (LONG_MAX - 1)
time_t
site_decode_time(const char *val)
{
	int   i;
	char  msec[4];
	int   ncolon = 0;
	char *pc;
	time_t  rv = 0;
	char *workval;
	char *workvalsv;

	if (val == NULL || *val == '\0') {
		return (0);
	}

	workval = strdup(val);
	workvalsv = workval;

	for (i = 0; i < 3; ++i)
		msec[i] = '0';
	msec[i] = '\0';

	for (pc = workval; *pc; ++pc) {

		if (*pc == ':') {
			if (++ncolon > 2)
				goto badval;
			*pc = '\0';
			rv = (rv * 60) + atoi(workval);
			workval = pc + 1;

		} else if (*pc == '.') {
			*pc++ = '\0';
			for (i = 0; (i < 3) && *pc; ++i)
				msec[i] = *pc++;
			break;
		} else if (!isdigit((int)*pc)) {
			goto badval;	/* bad value */
		}
	}
	rv = (rv * 60) + atoi(workval);
	if (rv > PBS_MAX_TIME)
		goto badval;
	if (atoi(msec) >= 500)
		rv++;
	(void)free(workvalsv);
	return (rv);

	badval:	(void)free(workvalsv);
	return (0);
}



/*
 *=====================================================================
 * site_dup_shares( osinfo, nsinfo ) - Duplicate share info.
 * Entry:	osinfo = ptr to current server info
 *		nsinfo = ptr to new server info
 *			jobs[] in nsinfo must be filled in already
 * Returns:	1 if duped okay, else 0
 * Sets		nsinfo->share_head
 *=====================================================================
 */
int
site_dup_shares(server_info *osinfo, server_info *nsinfo)
{
	share_head	*oldsh;
	resource_resv	*resv;
	int		i;

	if (osinfo == NULL || nsinfo == NULL)
		return 0;
	if ((oldsh = osinfo->share_head) == NULL) {
		/*
		 * If not using shares, done.
		 */
		return 1;
	}
	if (oldsh->root == NULL)
		return 0;
	if (!dup_shares(oldsh, nsinfo))
		return 0;
	/*
	 * Need to go through copy of jobs and point them into the new tree
	 */
	for (i = 0; i < nsinfo->sc.total; ++i) {
		resv = nsinfo->jobs[i];
		if (!resv->is_job || resv->job == NULL || resv->job->sh_info == NULL)
			continue;
		resv->job->sh_info = resv->job->sh_info->tptr;
	}
	return 1;
}



/*
 *=====================================================================
 * site_dup_share_amts(oldp) - Clone share amount array
 * Entry:	oldp = ptr to existing array
 * Returns:	ptr to copy of old
 *=====================================================================
 */
sh_amt *
site_dup_share_amts(sh_amt *oldp)
{
	sh_amt	*newp;
	size_t	sz;

	if (oldp == NULL)
		return NULL;
	sz = shr_class_count * sizeof(*newp);
	newp = (sh_amt *)malloc(sz);
	if (newp == NULL)
		return NULL;
	memcpy(newp, oldp, sz);
	return newp;
}



/*
 *=====================================================================
 * site_find_alloc_share(sinfo, name) - Find share info, allocating new
 *		entry if needed.
 * Entry:	sinfo = Current server info
 *		name = Entity to locate share info for.
 * Returns:	pointer to matching share_info structure,
 *		NULL if no match
 *=====================================================================
 */
share_info *
site_find_alloc_share(server_info *sinfo, char *name)
{
	share_info *	si;
	share_info *	nsi;

	if (sinfo->share_head == NULL || (si = sinfo->share_head->root) == NULL)
		return NULL;
	si = find_entity_share(name, si);
	if (si == NULL) {
		/*
		 * The default group is the root of the tree
		 */
		return sinfo->share_head->root;
	}
	if (si && si->pattern_type == share_info::pattern_type::PATTERN_SEPARATE &&
		strcmp(name, si->name) != 0) {
		/*
		 * On match against SEPARATE pattern, create new entry with
		 * exact match.
		 */
		nsi = new_share_info(name, shr_class_count);
		if (nsi != NULL) {
			nsi->pattern_type = share_info::pattern_type::PATTERN_NONE;
			nsi->leader = si->leader;
			nsi->parent = si;
			if (si->child) {
				for (si = si->child ; si->sibling ; si = si->sibling)
					;
				si->sibling = nsi;
			} else {
				si->child = nsi;
			}
			si = nsi;
		}
	}
	return si;
}



/*
 *=====================================================================
 * site_free_shares(sinfo) - Free cloned share info
 * Entry:	sinfo = server owning cloned info
 *=====================================================================
 */
void
site_free_shares(server_info *sinfo)
{
	share_head	*sh;

	if (sinfo == NULL || (sh = sinfo->share_head) == NULL)
		return;
	free_share_head(sh, 1);
	sinfo->share_head = NULL;
}



/*
 *=====================================================================
 * site_get_share( resresv ) - Get ratio of cpus used to allocated
 * Entry:	resresv = pointer to resource_resv
 * Returns:	Approximate ratio of current CPUs in use to allocation
 *		for job's group.
 *=====================================================================
 */
double
site_get_share(resource_resv *resresv)
{
	job_info	*job;
	share_info	*si;
	double		result = 0.0;

	if (!resresv->is_job ||
		(job = resresv->job) == NULL ||
		(si = job->sh_info) == NULL ||
		(si = si->leader) == NULL)
			return result;
#ifdef	NAS_HWY149
	if (job->priority == NAS_HWY149 || job->NAS_pri == NAS_HWY149) {
		return result;		/* Favor jobs on highway */
	}
#endif
#ifdef	DRT_XXX_NAS_HWY101
	if (job->priority == NAS_HWY101 || job->NAS_pri == NAS_HWY101) {
		return result;		/* Favor jobs on highway */
	}
#endif
	if (resresv->share_type == J_TYPE_ignore) {
		return result;		/* Favor jobs exempt from shares */
	}
	result = get_share_ratio(si->share_ncpus, job->sh_amts,
		si->share_inuse);
	return result;
}




/*
 *=====================================================================
 * site_init_alloc( sinfo ) - Initialize allocated shares CPUs data
 * Entry:	sinfo = ptr to server_info, with all data about jobs,
 *			queues, nodes, etc, already collected.
 * Exit:	alloc info updated
 *=====================================================================
 */
void
site_init_alloc(server_info *sinfo)
{
	share_info	*root;
	share_info	*leader;
	sh_amt *	sh_active;	/* counts of CPUs in use */
	sh_amt *	sh_avail;	/* counts of CPUs not in use */
	sh_amt *	sh_contrib;	/* counts of CPUs avail for borrow */
	sh_amt *	sh_total;	/* total counts of CPUs */
	share_head *	shead;		/* active share info */
	int		i;

	if (sinfo == NULL || (shead = sinfo->share_head) == NULL)
		return;
	sh_active = shead->sh_active;
	sh_avail = shead->sh_avail;
	sh_contrib = shead->sh_contrib;
	sh_total = shead->sh_total;
	root = shead->root;
	if (sh_active == NULL || sh_avail == NULL || sh_contrib == NULL
		|| sh_total == NULL || root == NULL)
		return;
	/*
	 * Scan nodes to total number of CPUs of each type -> sh_total
	 */
	count_cpus(sinfo->nodes, sinfo->num_nodes, sinfo->queues, sh_total);
	/*
	 * Scan jobs to accumulate CPUs in use or requested into share info
	 * structures.
	 */
	zero_share_counts(root);
	memset(sh_active, 0, shr_class_count * sizeof(*sh_active));
	count_active_cpus(sinfo->jobs, sinfo->sc.total, sh_active);
	count_demand_cpus(sinfo->jobs, sinfo->sc.total);
	/*
	 * Now, adjust CPUs available for sharing downward by current
	 * use of jobs not associated with a share group.
	 */
	leader = root->leader;
	for (i = 0; i < shr_class_count; ++i) {
		int t;
		t = sh_total[i];
		if (leader != NULL) {
			int	j;
			for (j = 0; j < J_TYPE_COUNT; ++j) {
				t -= leader->share_inuse[i][j];
			}
		}
		sh_avail[i] = t;
	}
	/*
	 * Convert raw allocations into CPU counts -> share_ncpus.
	 */
	set_share_cpus(root, root->share_gross, sh_avail);
	/*
	 * Count how many CPUs are available for borrowing.
	 */
	count_contrib_cpus(root, root, sh_contrib);
	/*
	 * Root has access to all CPUs.
	 */
	for (i = 0; i < shr_class_count; ++i) {
		root->share_ncpus[i] = sh_total[i];
	}
	if (conf.partition_id == NULL) {
		site_list_shares(stdout, sinfo, "sia_", 1);
		fflush(stdout);
	}
}



/*
 *=====================================================================
 * site_is_queue_topjob_set_aside(resv) - Check the topjob_set_aside attribute
 *		for the queue of the given job
 * Entry:	resv = resource_resv for job
 * Returns:	1 if topjob_set_aside=True for the queue
 *		0 otherwise
 *=====================================================================
 */
int
site_is_queue_topjob_set_aside(resource_resv *resv)
{
	job_info*	job;

	if (resv == NULL || !resv->is_job || (job = resv->job) == NULL ||
		job->queue == NULL)
		return 0;

	return job->queue->is_topjob_set_aside;
}



/*
 *=====================================================================
 * site_is_share_king(policy) - Check if group shares are most important
 *		job sort criterion
 * Entry:	policy = policy in effect
 *		Call with policy = NULL to fetch previously computed value.
 * Returns:	1 if group shares is second job sort key (after formula)
 *		0 otherwise
 *=====================================================================
 */
int
site_is_share_king(status *policy)
{
	static int	is_king = 0;

	if (policy == NULL)
		return is_king;		/* return previous value */
	/*
	 * If no shares, shares are not king.
	 */
	if (cur_shr_head == NULL) {
		is_king = 0;
		return is_king;
	}
	/*
	 * Examine the sort keys to see if shares are primary key
	 */
	is_king = 0;
	if (policy->sort_by) {
		char *res_name;
		if ((res_name = policy->sort_by[0].res_name) != NULL &&
		    strcmp(res_name, SORT_ALLOC) == 0) {
			is_king = 1;
		}
	}
	return is_king;
}



/*
 *=====================================================================
 * site_list_shares(fp, sinfo, pfx, flag) - Write current CPU allocation
 *			info to file
 * Entry:	fp = FILE * to write to
 *		sinfo = server to list data for
 *		pfx = string to prefix each line with
 *		flag = non-zero to list only leaders
 * Exit:	Data from tree written to file
 *=====================================================================
 */
void
site_list_shares(FILE *fp, server_info *sinfo, const char *pfx, int flag)
{
	share_info	*root;
	int		idx;

	if (fp == NULL || sinfo == NULL || sinfo->share_head == NULL
		|| (root = sinfo->share_head->root) == NULL) {
		return;
	}
	for (idx = 0; idx < shr_class_count ; ++idx) {
		char *sname;

		sname = shr_class_name_by_idx(idx);
		list_share_info(fp, root, pfx, idx, sname, flag);
	}
}




/*
 *=====================================================================
 * site_list_jobs( sinfo, rarray ) - List jobs in queue to file
 * Entry:	sinfo = server info
 *		rarray array of pointers to jobs, terminated by NULL
 *=====================================================================
 */
void
site_list_jobs(server_info *sinfo, resource_resv **rarray)
{
	FILE		*sj;
	char		*fname;
	int		i;
	share_info	*si;
	sh_amt		*job_amts;
	char		*sname;
	const char	*starving;

	fname = SORTED_FILE;
	sj = fopen(fname, "w+");
	if (sj == NULL) {
		sprintf(log_buffer, "Cannot open %s: %s\n",
			fname, strerror(errno));
		log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_JOB, LOG_ERR,
			__func__, log_buffer);
		return;
	}
	site_list_shares(sj, sinfo, "#A ", 0);
	for (i = 0; ; ++i) {
		struct resource_resv	*rp;
		struct job_info		*job;
		char 		*name, *queue, *user;
		time_t		start;
		int		jpri;
		int		ncpus;

		rp = rarray[i];
		if (rp == NULL)
			break;
		/*
		 * List only jobs
		 */
		if (!rp->is_job)
			continue;
		job = rp->job;
		/*
		 * that are still in the queue
		 */
		if (!job->is_queued)
			continue;
		name = rp->name;
		queue = job->queue->name;
		user = rp->user;
		si = job->sh_info;
		sname = NULL;
		if (si) {
			switch (si->pattern_type) {
				case share_info::pattern_type::PATTERN_COMBINED:
				case share_info::pattern_type::PATTERN_SEPARATE:
					if (si->leader) sname = si->leader->name;
					break;
				default:
					sname = si->name;
					break;
			}
		}
		if (sname == NULL)
			sname = "<none>";
		starving = job->is_starving ? "s" : "-";
		start = rp->start;
		jpri = job->NAS_pri;
		ncpus = rp->select ? rp->select->total_cpus : -1; /* XXX */
		job_amts = job->sh_amts;
		if (job_amts) {
			int sh_cls;
			ncpus = 0;
			for (sh_cls = 0; sh_cls < shr_class_count; ++sh_cls) {
				ncpus += job_amts[sh_cls];
			}
		}
		if (start == UNSPECIFIED || start == sinfo->server_time)
			start = 0;
		fprintf(sj, "  %s\t%s\t%s\t%s\t%s\t%lu\t%d\t%d\n",
			name, queue, user, sname, starving,
			(unsigned long)start, jpri, ncpus);
	}
	fclose(sj);
}


/*
 *=====================================================================
 * site_parse_shares(fname) - Read CPU shares file
 * Entry	fname = path to file
 * Returns	1 if all okay
 *		0 on errors, messages to log
 * Modifies	static variables declared at start of file
 *=====================================================================
 */
int
site_parse_shares(char *fname)
{
	share_info	*cur;
	int		errcnt = 0;	/* parse error counter */
	FILE 		*fp;		/* shares file */
	int		i;
	int		lineno = 0;	/* current line number in file */
	share_info	*parent;	/* parent of current node */
	share_info	*root = NULL;	/* New tree under construction */
	char		*save_ptr;	/* posn for strtok_r() */
	char		*sp;		/* temp ptr into buf */
	char		*sp2;		/* ditto */
	char		*sp3;		/* ditto */
	int		state;
	sh_amt		*tshares;	/* temp shares values */
	struct shr_class *tclass;	/* temp class pointer */
	struct shr_type	*ttype;		/* temp type pointer */
	int		new_cls_cnt;	/* number of CPU classes */
	int		new_type_cnt;	/* number of CPU types */
	struct shr_class *new_shr_clses;	/* new class list */
	struct shr_class *new_cls_tail;
	struct shr_type	*new_shr_types;	/* new type list */
	struct shr_type	*new_type_tail;
#define	LINE_BUF_SIZE	256
	char		buf[LINE_BUF_SIZE];	/* line buffer */
	char		class_and_type[LINE_BUF_SIZE];	/* [class:]type */
	char		new_sel[LINE_BUF_SIZE];	/* new value for type_selector */
	char		pattern[LINE_BUF_SIZE];	/* share group name/pattern */

	state = 0;
	new_shr_clses = new_cls_tail = NULL;
	new_shr_types = new_type_tail = NULL;
	new_cls_cnt = 0;
	new_type_cnt = 0;
	tshares = NULL;
	if ((fp = fopen(fname, "r")) == NULL) {
		i = errno;
		sprintf(log_buffer, "Error opening file %s", fname);
		log_err(i, __func__, log_buffer);
		return 1;		/* continue without shares */
	}
	while (fgets(buf, LINE_BUF_SIZE, fp) != NULL) {
		++lineno;
		cur = NULL;
		sp = strchr(buf, '\n');
		if (sp == NULL) {
			sprintf(log_buffer, "Line %d excessively long.  Giving up.",
				lineno);
			goto err_out_l;
		}
		/*
		 * Terminate lines at comment
		 */
		sp = strchr(buf, '#');
		if (sp != NULL) {
			sp[0] = '\n';
			sp[1] = '\0';
		}
		/*
		 * First non-comment line is "classes" line.
		 */
		sp = strtok_r(buf, " \t\n", &save_ptr);
		if (sp == NULL)
			continue;	/* Empty or comment */
		if (strcasecmp(sp, "classes") == 0) {
			if (state != 0) {
				sprintf(log_buffer, "\"classes\" must be first line in shares file");
				goto err_out_l;
			}
			sp = strtok_r(NULL, " \t\n", &save_ptr);
			if (sp == NULL) {
				sprintf(log_buffer, "Empty \"classes\" line");
				goto err_out_l;
			}
			strcpy(new_sel, sp);
			/*
			 * Set up default class and type entries
			 */
			strcpy(log_buffer, "Malloc failure"); /* just in case */
			tclass = (shr_class *)malloc(sizeof(*tclass));
			if (tclass == NULL) {
				goto err_out_l;
			}
			tclass->next = NULL;
			tclass->sh_cls = 0;
			tclass->name[0] = '\0';
			new_shr_clses = tclass;
			new_cls_tail = tclass;

			ttype = (shr_type *)malloc(sizeof(*ttype));
			if (ttype == NULL) {
				goto err_out_l;
			}
			ttype->next = NULL;
			ttype->sh_tidx = 0;
			ttype->sh_cls = 0;
			ttype->cpus_per_node = 1;
			ttype->name[0] = '\0';
			new_shr_types = ttype;
			new_type_tail = ttype;

			new_cls_cnt = 1;
			new_type_cnt = 1;
			/*
			 * Now, collect list of selector values
			 */
			while ((sp = strtok_r(NULL, " \t\n", &save_ptr)) != NULL) {
				sp = strcpy(class_and_type, sp);
				sp2 = strchr(sp, ':');
				/* sp gives class, sp2 gives type */
				if (sp2 == NULL) {
					/*
					 * No class given, use previous tclass,
					 * else default.
					 */
					if (tclass == NULL) {
						tclass = new_shr_clses;
					}
					sp2 = sp;
				} else if (sp2 == sp) {
					/*
					 * Empty class, use default
					 */
					tclass = new_shr_clses;
					sp2++;
				} else {
					*sp2++ = '\0';
					for (tclass = new_shr_clses; tclass;
						tclass = tclass->next) {
						if (strcmp(sp, tclass->name) == 0)
							break;
					}
					if (tclass == NULL) {
						/*
						 * New class.  Add to list.
						 */
						tclass = (shr_class *)malloc(sizeof(*tclass)
							+ strlen(sp));
						if (tclass == NULL)
							goto err_out_l;
						tclass->next = NULL;
						tclass->sh_cls = new_cls_cnt++;
						strcpy(tclass->name, sp);
						new_cls_tail->next = tclass;
						new_cls_tail = tclass;
					}
				}
				sp3 = strchr(sp2, '@');
				/* sp3 gives cpus_per_node */
				if (sp3) {
					*sp3++ = '\0';
				}
				/*
				 * Type names must be unique.
				 */
				for (ttype = new_shr_types; ttype; ttype = ttype->next) {
					if (strcmp(sp2, ttype->name) == 0) {
						if (*sp2 == '\0')
							break;
						sprintf(log_buffer, "duplicate type: %s", sp2);
						goto err_out_l;
					}
				}
				if (ttype == NULL) {
					ttype = (shr_type *)malloc(sizeof(*ttype) + strlen(sp2));
					if (ttype == NULL)
						goto err_out_l;
					ttype->sh_tidx = new_type_cnt++;
					ttype->sh_cls = tclass->sh_cls;
					ttype->cpus_per_node = 1;
					if (sp3) {
						i = atoi(sp3);
						if (i > 0)
							ttype->cpus_per_node = i;
					}
					ttype->next = NULL;
					strcpy(ttype->name, sp2);
					new_type_tail->next = ttype;
					new_type_tail = ttype;
				}
			}
			++state;
			tshares = (sh_amt *)malloc(new_cls_cnt * sizeof(*tshares));
			if (tshares == NULL) {
				goto err_out_l;
			}
			continue;
		}
		/*
		 * Remaining lines are tree lines, of form
		 * pattern	parent	[class:share ...] [default_share]
		 */
		if (state == 0) {
			sprintf(log_buffer, "\"classes\" must appear first in shares file");
			goto err_out_l;
		}
		if (root == NULL) {
			/*
			 * Now that we have count of classes, can allocate
			 * root node.
			 */
			root = new_share_info("root", new_cls_cnt);
			if (root == NULL) {
				strcpy(log_buffer, "Cannot allocate ROOT node");
				goto err_out_l;
			}
		}
		strcpy(pattern, sp);
		sp = strtok_r(NULL, " \t\n", &save_ptr);
		if (sp == NULL) {
			sprintf(log_buffer,
				"Unrecognized shares line: %d: begins %s",
				lineno, pattern);
			goto err_parse;
		}
		if (find_share_group(root, pattern) != NULL) {
			sprintf(log_buffer,
				"Duplicated group at line %d: %s",
				lineno, pattern);
			goto err_parse;
		}
		parent = find_share_group(root, sp);	/* check valid parent */
		if (parent == NULL) {
			sprintf(log_buffer, "Unknown parent (%s) at line %d",
				sp, lineno);
			goto err_parse;
		}
		for (i = 0; i < new_cls_cnt; ++i) {
			tshares[i] = -1;
		}
		/*
		 * Extract share pairs from rest of line.
		 * We could skip some of the following if we assumed
		 * that save_ptr pointed into the string at the next place
		 * to start scanning, but its value is supposedly opaque.
		 * Basically, we squash out spaces around colons in the
		 * rest of the line to make it easier to strtok.
		 */
		sp = strtok_r(NULL, "\n", &save_ptr);
		if (sp != NULL) {
			int st = 0;
			int c;
			char *sp4;
			for (sp4 = buf; (c = *sp++) != '\0';) {
				switch (st) {
					case 0:	/* leading space */
						if (!isspace(c)) { st = 1; }
						break;
					case 1:	/* token, possibly with trailing : */
						if (isspace(c)) { st = 2; continue; }
						if (c == ':') { st = 3; break; }
						break;
					case 2:	/* skip spaces before : */
						if (isspace(c))	continue;
						if (c == ':') { st = 3; break; }
						/* Oops, no colon, restore delimiter */
						*sp4++ = ' ';
						st = 0;
						break;
					case 3:	/* skip spaces after : */
						if (isspace(c)) continue;
						st = 4;
						break;
					case 4:	/* token after a colon */
						if (isspace(c)) { st = 0; }
						break;
				}
				*sp4++ = c;
			}
			*sp4 = '\0';
			sp = strtok_r(buf, " \t\n", &save_ptr);
		}
		/*
		 * Whew!  Now ready to extract shares
		 */
		for (; sp ; sp = strtok_r(NULL, " \t\n", &save_ptr)) {
			char	*name;
			char	*value;
			char	*sp5;
			long	l;

			name = sp;
			if ((value = strchr(sp, ':')) != NULL) {
				*value++ = '\0';
			} else {
				value = name;
			}
			/*
			 * Extract name and value
			 */
			if (value == name) {
				i = 0;
				name = "";
			} else {
				if ((i = find_share_class(new_shr_clses, name)) == 0) {
					sprintf(log_buffer, "Unknown share class (%s) on line %d",
						name, lineno);
					goto err_parse;
				}
			}
			l = strtol(value, &sp5, 10);
			if (*sp5 != '\0' || l < 0) {
				sprintf(log_buffer, "Invalid share (%s) on line %d",
					value, lineno);
				goto err_parse;
			}
			if (tshares[i] != -1) {
				sprintf(log_buffer, "Repeated type (%s) on line %d",
					name, lineno);
				goto err_parse;
			}
			tshares[i] = l;
		}
		/*
		 * We have collected everything we need to create new tree
		 * node.
		 */
		cur = new_share_info(pattern, new_cls_cnt);
		if (cur == NULL)
			continue;
		for (i = 0; i < new_cls_cnt; ++i) {
			sh_amt t;
			t = tshares[i];
			if (t < 0)
				t = 0;
			cur->share_gross[i] = t;
		}
		cur->lineno = lineno;
		/*
		 * If the name is a pattern, compile it, after bracketing
		 * between ^ and $.
		 */
		if (strpbrk(pattern, "|*.\\(){}[]+") != NULL) {
			int result;
			enum share_info::pattern_type ptype = share_info::pattern_type::PATTERN_COMBINED;
			char *t = (char *)malloc(strlen(pattern) + 3);
			char *t2 = pattern;
			if (t != NULL) {
				if (*t2 == '+') {
					ptype = share_info::pattern_type::PATTERN_SEPARATE;
					++t2;
				}
				t[0] = '^';
				strcpy(t+1, t2);
				strcat(t+1, "$");
				result = regcomp(&cur->pattern, t,
					REG_ICASE|REG_NOSUB);
				if (result == 0) {
					cur->pattern_type = ptype;
				} else {
					sprintf(log_buffer,
						"Regcomp error on line %d for pattern %s", lineno, t);
					free(t);
					goto err_parse;
				}
				free(t);
			}
		}
		/*
		 * Link in.  We use tptr to hold youngest child.
		 */
		cur->parent = parent;
		if (parent->child == NULL) {
			parent->child = parent->tptr = cur;
		} else {
			parent->tptr->sibling = cur;
			parent->tptr = cur;
		}
		continue;		/* Done with line */
err_parse:
		log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE,
			__func__, log_buffer);
		if (cur) {
			free(cur);
		}
		if (++errcnt > 10) {
			strcpy(log_buffer, "Giving up on shares file.");
			goto err_out_l;
		}
	}
	fclose(fp);
	fp = NULL;
	if (errcnt > 0) {
		strcpy(log_buffer, "Errors encountered in shares file.");
		goto err_out_l;
	}
	if (root == NULL) {
		strcpy(log_buffer, "No share groups defined.");
		goto err_out_l;
	}
	/*
	 * Everything parsed okay, reconcile, then update global values
	 */
	if (!reconcile_shares(root, new_cls_cnt)) {
		strcpy(log_buffer, "Inconsistencies detected");
		goto err_out_l;
	}
	{	struct share_head *newsh;
		newsh = new_share_head(new_cls_cnt);
		if (newsh == NULL) {
			strcpy(log_buffer, "Cannot allocate new share header");
			goto err_out_l;
		}
		if (cur_shr_head) {
			free_share_head(cur_shr_head, 0);
		}
		cur_shr_head = newsh;
	}
	cur_shr_head->root = root;
	{	struct shr_class *nextp;
		for (tclass = shr_classes; tclass; tclass = nextp) {
			nextp = tclass->next;
			free(tclass);
		}
	}
	{	struct shr_type	*nextp;
		for (ttype = shr_types; ttype; ttype = nextp) {
			nextp = ttype->next;
			free(ttype);
		}
	}
	shr_classes = new_shr_clses;
	shr_types = new_shr_types;
	if (shr_selector) free(shr_selector);
	shr_selector = strdup(new_sel);
	shr_class_count = new_cls_cnt;
	shr_type_count = new_type_cnt;
	return 1;

err_out_l:
	log_err(-1, __func__, log_buffer);
	log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, __func__,
		"Warning: CPU shares file parse error: file ignored");
	for (ttype = new_shr_types; ttype; ttype = new_shr_types) {
		new_shr_types = ttype->next;
		free(ttype);
	}
	if (tshares)
		free(tshares);
	free_share_tree(root);
	if (fp)
		fclose(fp);
	return 0;
}



/*
 *=====================================================================
 * site_find_runnable_res( resv_arr ) - Site specific code for picking
 *			next resv/job to try to run
 * Entry:	resv_arr = array of ptrs to resource_resv,
 *			sorted per job sort key list.
 *		Should be called at beginning of job loop with NULL
 *		to reset state.
 * Returns:	ptr to selected resource_resv,
 *			NULL if no more choices.
 *=====================================================================
 */
resource_resv *
site_find_runnable_res(resource_resv** resresv_arr)
{
	static	enum { S_INIT, S_RESV, S_HWY149, S_DEDRES, S_HWY101, S_TOPJOB, S_NORMAL } state;
	resource_resv *	resv;
	server_info *	sinfo;
	share_head *	shp;
	share_info *	si;
	int		i;

	if (resresv_arr == NULL) {
		state = S_INIT;
		return NULL;
	}
	/*
	 * Find any job in list and use it to get current server info,
	 * which, in turn, leads to current share info
	 */
	for (i = 0; (resv = resresv_arr[i]) != NULL; ++i) {
		if (resv->is_job && resv->job != NULL)
			break;
	}
	if (resv == NULL)
		return NULL;
	sinfo = resv->job->queue->server;
	shp = sinfo->share_head;
	si = NULL;

	if (state == S_INIT) {
		if (shp) {
			clear_topjob_counts(shp->root);
		}
		state = S_RESV;
	}
	if (state == S_RESV) {
		for (i = 0; (resv = resresv_arr[i]) != NULL; i++) {
			if (!resv->is_job && !resv->can_not_run &&
					in_runnable_state(resv)) {
				return resv;
			}
		}
		state = S_HWY149;
	}
	if (state == S_HWY149) {
#ifdef	NAS_HWY149
		/*
		 * Go through operator boosted jobs (highest priority)
		 */
		if ((resv = pick_next_job(sinfo->policy, resresv_arr,
			job_filter_hwy149, NULL)) != NULL)
			return resv;
#endif
		state = S_DEDRES;
	}
	/*
	 * Stop looking now if interested only in resuming jobs.
	 * localmod XXXY
	 */
	if (conf.resume_only)
		return NULL;
	if (state == S_DEDRES) {
		/*
		 * Go through jobs in queues that use per_queues_topjobs, these
		 * queues should have nodes assigned to them and therefore
		 * these jobs will not take nodes away from later 101/top jobs
		 * in below code
		 */
		if ((resv = pick_next_job(sinfo->policy, resresv_arr,
			job_filter_dedres, NULL)) != NULL)
			return resv;

		state = S_HWY101;
	}
	if (state == S_HWY101) {
#ifdef	NAS_HWY101
		/*
		 * Go through operator boosted jobs
		 */
		if ((resv = pick_next_job(sinfo->policy, resresv_arr,
			job_filter_hwy101, NULL)) != NULL)
			return resv;
#endif
		state = S_TOPJOB;
	}
	if (state == S_TOPJOB) {
		/*
		 * Find most-favored group not at topjob limit
		 */
		if (shp != NULL)
			si = find_most_favored_share(shp->root, conf.per_share_topjobs);
		if (si == NULL) {
			state = S_NORMAL;
		}
	}
	if ((resv = pick_next_job(sinfo->policy, resresv_arr,
		job_filter_normal, si)) != NULL)
		return resv;

	/*
	 * Searched whole list without match.  Try again with different share
	 * group.
	 */
	if (si != NULL) {
		si->none_left = 1;
		resv = site_find_runnable_res(resresv_arr);
	}
	return resv;
}



/*
 *=====================================================================
 * site_resort_jobs(njob) - Possibly resort queues after starting job
 * Entry:	njob = job that was just started
 *=====================================================================
 */
void
site_resort_jobs(resource_resv *njob)
{
	server_info	*sinfo;
	queue_info	*queue;
	job_info	*job;
	int		i;

	if (njob == NULL || !njob->is_job || (job = njob->job) == NULL
		|| (queue = job->queue) == NULL || (sinfo = njob->server) == NULL)
			return;
	/*
	 * Update values that changed due to job starting.
	 */
	for (i = 0; i < sinfo->sc.total; ++i) {
		resource_resv *resv;

		resv = sinfo->jobs[i];
		if (!resv->is_job || !in_runnable_state(resv))
			continue;
		(void) job_starving(sinfo->policy, resv);
	}
	/*
	 * Now, redo sorting.
	 */
	qsort(sinfo->jobs, sinfo->sc.total, sizeof(resource_resv *), cmp_sort);
	for (i = 0; sinfo->queues[i] != NULL; ++i) {
		qsort(sinfo->queues[i]->jobs, sinfo->queues[i]->sc.total,
			sizeof(resource_resv *), cmp_sort);
	}
}



/*
 *=====================================================================
 * site_restore_users() - Restore user values after adding job to
 *			calendar
 * Exit:	User values reset
 *=====================================================================
 */
void
site_restore_users(void)
{
	site_user_info	*user;

	for (user = users; user ; user = user->next) {
		user->current_use = user->saved_cu;
		user->current_use_pqt = user->saved_cup;
	}
}



/*
 *=====================================================================
 * site_save_users() - Save users values during clone operation.
 * Exit:	Current important values stored away
 *=====================================================================
 */
void
site_save_users(void)
{
	site_user_info	*user;

	for (user = users; user ; user = user->next) {
		user->saved_cu = user->current_use;
		user->saved_cup = user->current_use_pqt;
	}
}




/*
 *=====================================================================
 * site_set_job_share(resresv) - Set counts of share resources
 *		requested by job.
 * Entry:	resresv = resource reservation for job
 *		The select spec is assumed to be parsed into chunks.
 * Exit:	job's sh_amts array set
 *=====================================================================
 */
void
site_set_job_share(resource_resv *resresv)
{
	chunk *			chunk;
	int			i;
	job_info *		job;
	resource_req *		preq;
	selspec *		select;
	sh_amt *		sh_amts;
	struct shr_type *	stp;

	if (resresv == NULL || (select = resresv->select) == NULL)
		return;
	if (!resresv->is_job || (job = resresv->job) == NULL)
		return;
	if (shr_class_count == 0 || shr_selector == NULL)
		return;
	if ((sh_amts = job->sh_amts) == NULL) {
		sh_amts = (sh_amt *)malloc(shr_class_count * sizeof(*sh_amts));
		if (sh_amts == NULL)
			return;
		job->sh_amts = sh_amts;
	}
	memset(sh_amts, 0, shr_class_count * sizeof(*sh_amts));
	for (i = 0; (chunk = select->chunks[i]) != NULL; ++i) {
		int ncpus;
		int sh_cls;

		ncpus = 0;
		stp = NULL;

		for (preq = chunk->req; preq != NULL; preq = preq->next) {
			if (strcmp(preq->name, shr_selector) == 0) {
				stp = shr_type_info_by_name(preq->res_str);
			} else if (strcmp(preq->name, "ncpus") == 0) {
				ncpus = preq->amount;
#if	NAS_CPU_MULT > 1
				if (ncpus % NAS_CPU_MULT) {
					ncpus += NAS_CPU_MULT - (ncpus % NAS_CPU_MULT);
				}
#endif
			}
		}
		if (stp == NULL) {
			stp = shr_type_info_by_idx(0);	/* default */
		}
		sh_cls = stp->sh_cls;
		/*
		 * The next line assumes vnodes are allocated exclusively
		 */
		if (stp->cpus_per_node > ncpus) {
			ncpus = stp->cpus_per_node;
		}
		/* XXX HACK HACK until SBUrate available, localmod 126 */
		ncpus = stp->cpus_per_node;
		/* end HACK localmod 126 */
		sh_amts[sh_cls] += chunk->num_chunks * ncpus;
	}
}



/*
 *=====================================================================
 * site_set_NAS_pri(job, max_starve, starve_num) - calculate the
 *		NAS priority for a job
 * Entry:	job = job to have its NAS_pri field set
 *		max_starve = starve time for queue job is in
 *		starve_num = how long job has starved
 * Exit:	job->NAS_pri set
 *=====================================================================
 */
#if	NAS_HWY101
#define	MAX_NAS_PRI	(NAS_HWY101 - 1)
#else
#define	MAX_NAS_PRI	100
#endif
#define	IDLE_BOOST	10	/* Boost for users with nothing else running */
void
site_set_NAS_pri(job_info *job, time_t max_starve, long starve_num)
{
	queue_info* 	queue;
	site_user_info*	sui;
	long		starve_adjust;

	if (job == NULL || (queue = job->queue) == NULL)
		return;
	if (job->priority > 0) {
		job->NAS_pri = job->priority;
		return;
	}
	/* localmod 116
	 * Queued jobs get their job priority boosted by 2 for each
	 * max_starve interval they have waited, up to a maximum of 20.
	 */
	starve_adjust = 0;
	if (max_starve > 0 && max_starve < Q_SITE_STARVE_NEVER) {
		starve_adjust = 2 * starve_num / max_starve;
		if (starve_adjust < 0) starve_adjust = 0;
		if (starve_adjust > 20) starve_adjust = 20;
	}
	job->NAS_pri = job->queue->priority + starve_adjust;
	/*
	 * Jobs get a boost of 10 if there are no other jobs currently
	 * running for the user.
	 */
	sui = job->u_info;
	if (sui != NULL) {
		sch_resource_t t;
		t = queue->is_topjob_set_aside ? sui->current_use_pqt :
			sui->current_use;
		if (t == 0 && job->NAS_pri < MAX_NAS_PRI) {
			int pri = job->NAS_pri + IDLE_BOOST;
			if (pri > MAX_NAS_PRI) pri = MAX_NAS_PRI;
			job->NAS_pri = pri;
		}
	}
}


/*
 *=====================================================================
 * site_set_node_share(ninfo, res) - Set type of share node supplies
 * Entry:	ninfo = pointer to node info
 *		res = pointer to resource available on node
 * Exit:	ninfo->sh_cls, sh_type set if appropriate
 *=====================================================================
 */
void
site_set_node_share(node_info *ninfo, schd_resource *res)
{
	int		i;
	struct shr_type	*stp = NULL;

	if (ninfo == NULL || res == NULL || shr_selector == NULL)
		return;
	if (strcmp(res->name, shr_selector) != 0)
		return;			/* not our resource */
	ninfo->sh_cls = 0;
	if (res->str_avail == NULL)
		return;
	for (i = 0; res->str_avail[i]; ++i) {
		if ((stp = shr_type_info_by_name(res->str_avail[i]))!=NULL) {
			ninfo->sh_cls = stp->sh_cls;
			ninfo->sh_type = stp->sh_tidx;
			break;
		}
	}
}



/*
 *=====================================================================
 * site_set_share_head(sinfo) - Set share head into server info
 * Entry:	sinfo = ptr to server info
 * Returns:	1 on success, 0 on error
 * Assumes:	cur_shr_head set
 *=====================================================================
 */
int
site_set_share_head(server_info *sinfo)
{
	if (sinfo == NULL)
		return 0;
	if (cur_shr_head == NULL)
		return 0;
	sinfo->share_head = cur_shr_head;
	return 1;
}



/*
 *=====================================================================
 * site_set_share_type(sinfo, resresv) - Set share type for job
 *=====================================================================
 */
void
site_set_share_type(server_info * sinfo, resource_resv * resresv)
{
	job_info *	ji;
	queue_info *	qi;
	time_t		max_borrow;
	time_t		remaining;

	if (sinfo == NULL || resresv == NULL)
		return;
	/*
	 * Assume shares not relevant
	 */
	resresv->share_type = J_TYPE_ignore;
	if (conf.max_borrow == UNSPECIFIED) {
		return;
	}
	ji = resresv->job;
	if (ji == NULL || !resresv->is_job)
		return;
	qi = ji->queue;
	if (qi == NULL)
		return;
	max_borrow = qi->max_borrow;
	if (max_borrow == UNSPECIFIED)
		max_borrow = conf.max_borrow;
	if (max_borrow == 0) {
		return;			/* max borrow of 0 means exempt */
	}
	if (ji->is_running) {
		remaining = resresv->end - sinfo->server_time;
	} else {
		remaining = resresv->duration;
	}
	if (remaining > max_borrow) {
		resresv->share_type = J_TYPE_limited;
	} else {
		resresv->share_type = J_TYPE_borrow;
	}
}



/*
 *=====================================================================
 * site_should_backfill_with_job(policy, sinfo, resresv, ntj, nqtj, err)
 * Entry:	policy = pointer to current policy
 *		sinfo = server state where job resides
 *		resresv = the job to check
 *		ntj = number of topjobs so far
 *		nqtj = number of queue topjobs so far
 *		err = error structure from trying to run job immediately
 * Returns:	0 if should not calendar
 *		1 calendar based on backfill_depth
 *		2 calendar based on per_queue_topjobs
 *		3 calendar based on per_share_topjobs
 *		4 calendar based on share usage ratio
 *=====================================================================
 */
int site_should_backfill_with_job(status *policy, server_info *sinfo, resource_resv *resresv, int ntj, int nqtj, schd_error *err)
{
	int		rc;
	share_info	*si;
	struct job_info	*job;

	if (policy == NULL || sinfo == NULL || resresv == NULL || err == NULL)
		return 0;
	if (!resresv->is_job || (job = resresv->job) == NULL)
		return 0;
	/*
	 * Do normal checks and reject if they reject.
	 */
	rc = should_backfill_with_job(policy, sinfo, resresv, ntj);
	if (rc == 0)
		return rc;
	/*
	 * Start of site-specific calendaring code
	 */
#ifdef NAS_HWY149
	/*
	 * Don't drain for node shuffle jobs or other specials.
	 */
	if (job->NAS_pri == NAS_HWY149)
		return 0;
#endif
	/*
	 * Jobs blocked by other jobs from the same user are not eligible
	 * for starving/backfill help.
	 */
	switch (err->error_code) {
		case SERVER_USER_LIMIT_REACHED:
		case QUEUE_USER_LIMIT_REACHED:
		case SERVER_USER_RES_LIMIT_REACHED:
		case QUEUE_USER_RES_LIMIT_REACHED:
			return 0;
			/*
			 * No point to backfill for jobs blocked by dedicated
			 * time.  All resources will become available at
			 * the end of the dedicated time.
			 */
		case DED_TIME:
		case CROSS_DED_TIME_BOUNDRY:
			return 0;
			/*
			 * If job exceeds total mission allocation,
			 * it can never run.
			 */
		case GROUP_CPU_INSUFFICIENT:
			return 0;
		default:
			;
	}
	/* Check if in queues with special topjob limit */
	/* localmod 038 */
	if (site_is_queue_topjob_set_aside(resresv)
			&& nqtj < conf.per_queues_topjobs)
	  	return 2;
	/* Check if per-share count exhausted. */
	si = job->sh_info;
	if (si) si = si->leader;
	if (si && si->topjob_count < conf.per_share_topjobs)
		return 3;		/* Still within share guarantee */
	/* localmod 154 */
	/* Check if share using less than allocation */
	if (si && si->ratio_max < 1.0 && si->tj_cpu_cost < TJ_COST_MAX /* XXX */)
		return 4;
	/* Back to non-NAS tests.  Have we calendared backfill_depth jobs? */
	if (ntj >= policy->backfill_depth)
		return 0;
	return 1;
}


/*
 *=====================================================================
 * site_tidy_server(sinfo) - Tweak data collected from server
 * Entry:	sinfo = Server info.  The following are some of the
 *			fields that can be used:
 *
 *			nodes = array of nodes
 *			queues = array of queues (sorted)
 *			resvs = array of reservations
 *			jobs = array of jobs (partially sorted or not,
 *				depending on by_queue or round_robin)
 *			all_resresv = array of all jobs and reservations
 *				(sorted on event time)
 *
 *			Note: the following are *not* set: running_resvs,
 *			running_jobs, exiting_jobs, starving_jobs,
 *			user_counts, group_counts.
 * Return:	0 on error, 1 on success
 *=====================================================================
 */
int
site_tidy_server(server_info *sinfo)
{
	int		rc;
	int		i;
	resource_resv	*resv;

	if (sinfo->share_head == NULL)
		sinfo->share_head = cur_shr_head;
	site_init_alloc(sinfo);
	rc = init_users(sinfo);
	if (rc != 0)
		return 0;
	/*
	 * Adjust queued job priorities now that we have user info.
	 */
	for (i = 0; i < sinfo->sc.total; ++i) {
		resv = sinfo->jobs[i];
		if (!resv->is_job || !in_runnable_state(resv))
			continue;
		(void) job_starving(sinfo->policy, resv);
	}
	return 1;
}



/*
 *=====================================================================
 * site_update_on_end(sinfo, qinfo, res) - Do site specific updating
 *		when job ends.
 * Entry:	sinfo = server info
 *		qinfo = info for queue job running in
 *		res = resv/job info
 * Exit:	Local data updated
 *=====================================================================
 */
void
site_update_on_end(server_info *sinfo, queue_info *qinfo, resource_resv *resv)
{
	job_info	*job;
	share_info	*si;
	sh_amt		*sc;
	share_head	*shead;

	if (sinfo == NULL || (shead = sinfo->share_head) == NULL)
		return;
	if (!resv->is_job || (job = resv->job) == NULL)
		return;
	if ((si = job->sh_info) == NULL || (sc = job->sh_amts) == NULL)
		return;
	bump_share_count(si, resv->share_type, sc, -1);
	bump_demand_count(si, resv->share_type, sc, 1);
	if ((si = si->leader) == NULL)
		return;
	if (resv->share_type != J_TYPE_ignore) {
		int i;

		for (i = 0; i < shr_class_count; ++i) {
			int borrowed;
			int ncpus;

			ncpus = sc[i];
			shead->sh_avail[i] += ncpus;
			borrowed = si->share_inuse[i][J_TYPE_limited] +
				si->share_inuse[i][J_TYPE_borrow] -
				si->share_ncpus[i];
			if (borrowed > 0) {
				if (borrowed > ncpus)
					borrowed = ncpus;
				shead->sh_contrib[i] += borrowed;
			}
		}
		si->ratio = get_share_ratio(si->share_ncpus, NULL,
			si->share_inuse);
	}
#ifdef NAS_DEBUG
	printf(" YYY- %s %d %g %g %s\n", si->name, (int)resv->share_type, si->ratio, si->ratio_max, resv->name);
	fflush(stdout);
#endif
}



/*
 *=====================================================================
 * site_update_on_run(sinfo, qinfo, res, flag, ns) - Do site specific
 *		updating when job started.
 * Entry:	sinfo = server info
 *		qinfo = info for queue job running in
 *		res = resv/job info
 *		flag = 0 when calendaring, 1 if really starting
 *		ns = node specification job run on
 * Exit:	Local data updated
 *=====================================================================
 */
void
site_update_on_run(server_info *sinfo, queue_info *qinfo,
	resource_resv *resv, int flag, nspec **ns)
{
	job_info	*job;
	share_info	*si;
	sh_amt		*sc;
	share_head	*shead;
	queue_info	*queue;
	site_user_info	*sui;
	int		i, ncpus, borrowed;

	if (sinfo == NULL || (shead = sinfo->share_head) == NULL)
		return;
	if (!resv->is_job || (job = resv->job) == NULL)
		return;
	if ((si = job->sh_info) == NULL || (sc = job->sh_amts) == NULL)
		return;
	queue = job->queue;
	sui = job->u_info;
	if (flag && sui && queue) {
		if (queue->is_topjob_set_aside) {
			sui->current_use_pqt += job->accrue_rate;
		} else {
			sui->current_use += job->accrue_rate;
		}
	}
	bump_share_count(si, resv->share_type, sc, 1);
	bump_demand_count(si, resv->share_type, sc, -1);
	if ((si = si->leader) == NULL)
		return;
	if (resv->share_type != J_TYPE_ignore) {
		for (i = 0; i < shr_class_count; ++i) {
			ncpus = sc[i];
			shead->sh_avail[i] -= ncpus;
			borrowed = \
			   si->share_inuse[i][J_TYPE_limited]
			  +si->share_inuse[i][J_TYPE_borrow]
			  -si->share_ncpus[i];
			if (borrowed > 0) {
				if (borrowed > ncpus)
					borrowed = ncpus;
				shead->sh_contrib[i] -= borrowed;
			}
		}
		si->ratio = get_share_ratio(si->share_ncpus, NULL,
			si->share_inuse);
		/* localmod 154 */
		/* Keep track of highest ratio seen */
		if (si->ratio > si->ratio_max)
			si->ratio_max = si->ratio;
	}
#ifdef NAS_DEBUG
	printf(" YYY+ %s %d %g %g %s\n", si->name, (int)resv->share_type, si->ratio, si->ratio_max, resv->name);
	fflush(stdout);
#endif
}



/*
 *=====================================================================
 * site_vnode_inherit( nodes ) - Have vnodes inherit certain values
 *		from their natural vnode.
 * Entry:	nodes = array of node_info structures for all vnodes
 * Exit:	vnodes updated
 *=====================================================================
 */
void
site_vnode_inherit(node_info ** nodes)
{
	int		nidx;
	node_info *	natural;
	node_info *	ninfo;
	resource *	res;
	resource *	cur;
	resource *	prev;

	if (nodes == NULL)
		return;
	natural = NULL;
	for (nidx = 0; (ninfo = nodes[nidx]) != NULL; ++nidx) {
		/*
		 * Is this a natural node?
		 */
		res = find_resource(ninfo->res, getallres(RES_HOST));
		if (res == NULL)
			continue;
		if (compare_res_to_str(res, ninfo->name, CMP_CASELESS)) {
			natural = ninfo;	/* Natural vnode */
			continue;
		}
		/*
		 * For vnode, locate natural vnode
		 */
		if (natural == NULL
			|| !compare_res_to_str(res, natural->name, CMP_CASELESS)) {
			int i;
			for (i = 0; (natural = nodes[i]) != NULL; ++i) {
				if (compare_res_to_str(res, natural->name, CMP_CASELESS)) {
					break;
				}
			}
		}
		if (natural == NULL)
			continue;
		/*
		 * Copy interesting status from natural vnode to this vnode
		 */
		ninfo->is_down |= natural->is_down;
		ninfo->is_offline |= natural->is_offline;
		ninfo->is_unknown |= natural->is_unknown;
		if (ninfo->is_down || ninfo->is_offline || ninfo->is_unknown) {
			ninfo->is_free = 0;
		}
		ninfo->no_multinode_jobs |= natural->no_multinode_jobs;
		if (natural->queue_name && ninfo->queue_name == NULL) {
			ninfo->queue_name = strdup(natural->queue_name);
		}
		if (ninfo->priority == 0) {
			ninfo->priority = natural->priority;
		}
		/*
		 * Copy natural vnode resources to this vnode
		 */
		for (res = natural->res; res != NULL; res = res->next) {
			/*
			 * Cannot duplicate consumable resources
			 */
			if (res->type.is_consumable)
				continue;
			/*
			 * Skip if resource already set for vnode
			 */
			for (prev = NULL, cur = ninfo->res; cur != NULL;
				cur = cur->next) {
				if (strcmp(cur->name, res->name) == 0) {
					break;
				}
				prev = cur;
			}
			if (cur != NULL)
				continue;
			/*
			 * Add resource to end of vnode's list
			 */
			cur = new_resource();
			if (cur == NULL)
				continue;
			cur->name = strdup(res->name);
			set_resource(cur, res->orig_str_avail, RF_AVAIL);
			if (prev == NULL) {
				ninfo->res = cur;
			} else {
				cur->next = prev->next;
				prev->next = cur;
			}
		}
	}
}



/*
 *=====================================================================
 * Internal functions
 *=====================================================================
 */



/*
 *=====================================================================
 * clear_topjob_counts(root) - Reset per group topjob counts
 * Entry:       root = root of share subtree to work on
 *=====================================================================
 */
static void
clear_topjob_counts(share_info* root)
{
	if (root == NULL)
		return;
	root->topjob_count = 0;
	root->none_left = 0;
	if (root->leader == root) {
		root->ratio = get_share_ratio(root->share_ncpus, NULL,
			root->share_inuse);
		/* localmod 154 */
		root->ratio_max = root->ratio;
		root->tj_cpu_cost = 0.0;
	}
	if (root->child)
		clear_topjob_counts(root->child);
	if (root->sibling)
		clear_topjob_counts(root->sibling);
}


/*
 *=====================================================================
 * count_cpus(nodes, ncnt, queues, totals) - Count total CPUs available
 *		for allocation
 * Entry:	nodes = array of node_info struct ptrs
 *		ncnt = count of entries in nodes
 *		queues = array of queue_info structures
 *		totals = sh_amt array for totals
 * Exit:	totals array updated with CPU type counts
 *=====================================================================
 */
static void
count_cpus(node_info **nodes, int ncnt, queue_info **queues, sh_amt *totals)
{
	int		i;
	resource	*res;
	sch_resource_t	ncpus;

	for (i = 0; i < shr_class_count; ++i) {
		totals[i] = 0;
	}
	for (i = 0; i < ncnt; ++i) {
		node_info	*node;

		node = nodes[i];
		/*
		 * Skip nodes in unusable states.
		 * (Unless jobs are still assigned to them.)
		 */
		if ((!node->is_pbsnode || node->is_down || node->is_offline)
			&&  (node->jobs == NULL || node->jobs[0] == NULL))
			continue;
#if	NAS_DONT_COUNT_EXEMPT
		/*
		 * Don't count nodes associated with specific queues
		 * if jobs in queue are exempt from CPU shares.
		 */
		if (node->queue_name) {
			queue_info *queue;
			queue = find_queue_info(queues, node->queue_name);
			if (queue == NULL || queue->max_borrow == 0)
				continue;
		}
#endif
		/*
		 * Include available CPUs in count
		 * For hosts that are down or offline, we count only
		 * assigned CPUs.  This should exactly balance the CPUs
		 * counted against running jobs.
		 */
#if 0 /* XXX HACK until SBUrate available, localmod 126 */
		res = find_resource(node->res, getallres(RES_NCPUS));
		if (res != NULL && res->avail != SCHD_INFINITY) {
			if (node->is_down || node->is_offline)
				/*
				 * Use string value, because reservations
				 * can affect res->assigned without updating
				 * str_assigned.
				 */
				ncpus = strtol(res->str_assigned, NULL, 0);
			else
				ncpus = res->avail;
			totals[node->sh_cls] += ncpus;
		}
#else
		{
		struct shr_type *stp;
		stp = shr_type_info_by_idx(node->sh_type);
		totals[node->sh_cls] += stp->cpus_per_node;
		}
#endif /* localmod 126 */
	}
}




/*
 *=====================================================================
 * count_active_cpus(resvs, jcnt, sh_active) - Update share alloc data
 *		based on running jobs.
 * Entry:	resvs = array of resource_resv struct ptrs
 *		jcnt = count of entries in jobs array
 *		sh_active = array to total use into
 * Exit:	share_inuse values updated
 *=====================================================================
 */
static void
count_active_cpus(resource_resv **resvs, int jcnt, sh_amt *sh_active)
{
	int		i, k;
	resource_resv	*resv;

	memset(sh_active, 0, shr_class_count * sizeof(*sh_active));
	for (i = 0; i < jcnt; ++i) {
		job_info *job;

		/*
		 * Skip everything but running jobs
		 */
		resv = resvs[i];
		if (!resv->is_job || (job = resv->job) == NULL)
			continue;
		if (!job->is_running)
			continue;
		if (job->sh_amts == NULL)
			continue;
		/*
		 * Add used CPUs to group total based on job share type
		 */
		if (resv->share_type != J_TYPE_ignore) {
			for (k = 0; k < shr_class_count; ++k) {
				sh_active[k] += job->sh_amts[k];
			}
		}
		bump_share_count(job->sh_info, resv->share_type, job->sh_amts, 1);
	}
}




/*
 *=====================================================================
 * count_demand_cpus(resvs, jcnt, sh_demand) - Update share use data
 *		for queued jobs.
 * Entry:	resvs = array of resource_resv struct ptrs
 *		jcnt = count of entries in jobs array
 * Exit:	share_demand values updated
 *=====================================================================
 */
static void
count_demand_cpus(resource_resv **resvs, int jcnt)
{
	int		i;
	job_info	*job;
	resource_resv	*resv;

	for (i = 0; i < jcnt; ++i) {
		/*
		 * Skip everything but eligible, queued jobs
		 */
		resv = resvs[i];
		if (!resv->is_job || (job = resv->job) == NULL)
			continue;
		if (!in_runnable_state(resv))
			continue;
		bump_demand_count(job->sh_info, resv->share_type, job->sh_amts, 1);
	}
}




/*
 *=====================================================================
 * count_contrib_cpus(root, node, sh_contrib) - Count CPUs available
 *		for borrowing.
 * Entry:	root = base of share info tree
 *		node = base of current sub-tree
 *		sh_contrib = where to accumulate overall totals
 * Exit:	Contents of sh_contrib set
 *=====================================================================
 */
static void
count_contrib_cpus(share_info *root, share_info *node, sh_amt *sh_contrib)
{
	int	i;
	int	contrib;

	if (root == NULL || node == NULL)
		return;
	if (node == root) {
		/* Clear counts */
		memset(sh_contrib, 0, shr_class_count * sizeof(*sh_contrib));
	}
	/*
	 * Only nodes with allocations can contribute
	 */
	if (node == node->leader && node != root) {
		for (i = 0; i < shr_class_count; ++i) {
			contrib = node->share_ncpus[i] -
				(node->share_inuse[i][J_TYPE_limited]
				+ node->share_inuse[i][J_TYPE_borrow]
				+ node->share_demand[i][J_TYPE_limited]
				+ node->share_demand[i][J_TYPE_borrow]
				) ;
			if (contrib > 0)
				sh_contrib[i] += contrib;
		}
	}
	if (node->child)
		count_contrib_cpus(root, node->child, sh_contrib);
	if (node->sibling)
		count_contrib_cpus(root, node->sibling, sh_contrib);
	if (node == root) {
		/*
		 * Remove root demand from amounts available.
		 */
		for (i = 0; i < shr_class_count; ++i) {
			int j;

			contrib = sh_contrib[i];
			for (j = 0; j < J_TYPE_COUNT; ++j) {
				if (j != J_TYPE_borrow) {
					contrib -= root->share_demand[i][j];
				}
			}
			if (contrib < 0)
				contrib = 0;
			sh_contrib[i] = contrib;
		}
	}
}



/*
 *=====================================================================
 * dup_shares (oldsh, nsinfo) - duplicate share tree
 * Entry:	oldsh = existing share head
 *		nsinfo = server info to record new share tree in
 * Returns:	1 on success, 0 on error
 *=====================================================================
 */
static int
dup_shares(share_head *oldsh, server_info *nsinfo)
{
	share_info	*oroot;
	share_info	*nroot;
	share_head	*newsh;

	if (oldsh == NULL || nsinfo == NULL)
		return 0;
	if ((oroot = oldsh->root) == NULL)
		return 0;
	newsh = new_share_head(shr_class_count);
	if (newsh == NULL)
		return 0;
	nroot = dup_share_tree(oroot);
	if (nroot == NULL) {
		free_share_head(newsh, 1);
		return 0;
	}
	newsh->root = nroot;
	newsh->prev = oldsh;
	cur_shr_head = newsh;
	memcpy(newsh->sh_total, oldsh->sh_total,
		shr_class_count*sizeof(*newsh->sh_total));
	memcpy(newsh->sh_avail, oldsh->sh_avail,
		shr_class_count*sizeof(*newsh->sh_avail));
	memcpy(newsh->sh_contrib, oldsh->sh_contrib,
		shr_class_count*sizeof(*newsh->sh_contrib));
	nsinfo->share_head = newsh;
	return 1;
}



/*
 *=====================================================================
 * dup_share_tree(root) - clone a share_info (sub)tree
 * Entry:	root = root of subtree to clone
 * Returns:	root of cloned copy
 * Modifies:	tptr link in original tree points to clone of that node
 *=====================================================================
 */
static share_info *
dup_share_tree(share_info *oroot)
{
	share_info	*nroot;

	if (oroot == NULL)
		return NULL;
	nroot = new_share_info_clone(oroot);
	if (nroot == NULL)
		return NULL;
	oroot->tptr = nroot;
	/*
	 * Update pointers where needed, etc.
	 */
	if (oroot->parent != NULL)
		nroot->parent = oroot->parent->tptr;
	if (oroot->leader != NULL)
		nroot->leader = oroot->leader->tptr;
	/*
	 * Breadth-first tree walk
	 */
	nroot->sibling = dup_share_tree(oroot->sibling);
	nroot->child = dup_share_tree(oroot->child);
	return nroot;
}



/*
 *=====================================================================
 * find_entity_share(name, node) - Look up share info for entity
 *		Patterns are taken into account.
 *		The sub-tree rooted at node is searched for the best
 *		match, where best is either an exact match, or the
 *		pattern with the lowest line number.
 * Entry:	name = Name of entity to locate.
 *		node = Root of subtree to search
 * Returns:	Pointer to matching share_info structure
 *=====================================================================
 */
static share_info *
find_entity_share(char *name, share_info *node)
{
	share_info *	si;
	share_info *	child;
	share_info *	best_si;

	if (node == NULL) {
		return NULL;
	}
	if (strcmp(name, node->name) == 0) {
		return node;		/* Simple match */
	}
	best_si = NULL;
	if (node->pattern_type != PATTERN_NONE) {
		if (regexec(&node->pattern, name, 0, NULL, 0) == 0) {
			/* Found one match */
			best_si = node;
		}
	}
	for (child = node->child; child; child = child->sibling) {
		si = find_entity_share(name, child);
		if (si) {
			if (si->pattern_type == PATTERN_NONE) {
				/* Found simple match in sub-tree */
				best_si = si;
				break;
			}
			if (best_si == NULL) {
				best_si = si;
				continue;
			}
			if (si->lineno < best_si->lineno) {
				best_si = si;
			}
		}
	}
	return best_si;
}



/*
 *=====================================================================
 * find_most_favored_share(root, topjobs) - Search share group list
 *		for group that is under the topjobs limit and has
 *		the lowest share use ratio.
 * Entry:	root = pointer to (sub)tree to search
 *		topjobs = configured topjob guarantee
 * Returns:	Pointer to favored share group info
 *		NULL if no group under topjobs.
 *=====================================================================
 */
share_info *
find_most_favored_share(share_info* root, int topjobs)
{
	share_info*	best;
	share_info*	si;

	if (root == NULL)
		return NULL;
	if (root->leader == root
		&& (root->topjob_count < topjobs
		  || root->tj_cpu_cost < TJ_COST_MAX)
		&& !root->none_left)
		best = root;
	else
		best = NULL;
	if (root->child) {
		si = find_most_favored_share(root->child, topjobs);
		if (best == NULL || (si != NULL && si->ratio < best->ratio))
			best = si;
	}
	if (root->sibling) {
		si = find_most_favored_share(root->sibling, topjobs);
		if (best == NULL || (si != NULL && si->ratio < best->ratio))
			best = si;
	}
	return best;
}



/*
 *=====================================================================
 * find_share_class(root, name) - Find share class in tree and return
 *		its class index
 * Entry:	root = root of class list to search
 *		name = name of class to search for
 * Returns:	matching class index
 *		0 (default) on no match
 *=====================================================================
 */
static int
find_share_class(struct shr_class *root, char *name)
{
	while (root) {
		if (strcmp(root->name, name) == 0)
			break;
		root = root->next;
	}
	return root ? root->sh_cls : 0;
}



/*
 *=====================================================================
 * find_share_group(root, name) - Look up share group info by name.
 *		No pattern matching is performed.
 * Entry:	root = root of share info tree
 *		name = name to find
 * Returns:	ptr to share info, or NULL if not found
 *=====================================================================
 */
static share_info *
find_share_group(share_info *root, char *name)
{
	share_info	*child;
	share_info	*result = NULL;

	if (root == NULL || name == NULL)
		return NULL;
	if (strcmp(root->name, name) == 0)
		return root;
	for (child = root->child; child; child = child->sibling) {
		result = find_share_group(child, name);
		if (result)
			break;
	}
	return result;
}


/*
 *=====================================================================
 * find_share_type(head, name) - Look up type by name and return its
 *	type index.
 * Entry:	head = head of table list
 *		name = name to find
 * Returns:	index, or 0 on no match (default)
 *=====================================================================
 */
#if 0
static int
find_share_type(struct shr_type *head, char *name)
{
	if (head == NULL || name == NULL || *name == '\0')
		return 0;
	for (; head ; head = head->next) {
		if (strcmp(name, head->name) == 0) {
			return head->sh_cls;
		}
	}
	return 0;
}
#endif



/*
 *=====================================================================
 * find_user(head, name) - Look up user in list, adding if missing.
 * Entry:	head = ptr to head of list
 *		name = name to find
 * Returns:	ptr to user info structure
 *		NULL on error
 *		*head possibly updated
 *=====================================================================
 */
static site_user_info*
find_user(site_user_info **head, char *name)
{
	site_user_info	*cur;
	site_user_info	*prev;
	site_user_info	*sui;

	if (head == NULL)
		return NULL;
	prev = NULL;
	for (cur = *head; cur ; cur = cur->next) {
		int rc = strcasecmp(name, cur->user_name);
		if (rc == 0)
			return cur;
		if (rc > 0)
			break;
		prev = cur;
	}
	/*
	 * Not found, allocate a new entry and link it in.
	 */
	sui = malloc(sizeof(site_user_info) + strlen(name));
	if (sui == NULL)
		return NULL;		/* memory allocation failed */
	strcpy(sui->user_name, name);
	sui->current_use = sui->current_use_pqt = 0;
	sui->next = cur;
	if (prev == NULL) {
		*head = sui;
	} else {
		prev->next = sui;
	}
	return sui;
}


/*
 *=====================================================================
 * free_share_head(sh, flag) - Free a share head and associated tree
 * Entry:	sh = ptr to share head
 *		flag = true if tree expected to be a clone
 *=====================================================================
 */
static void
free_share_head(share_head *sh, int flag)
{
	share_info	*root;

	if (sh == NULL)
		return;
	root = sh->root;
	if (root == NULL)
		return;
	if (flag) {
		/*
		 * Be careful when releasing things that are supposed
		 * to be clones.
		 */
		if (!root->am_clone)
			return;
		if (sh != cur_shr_head)
			return;
		cur_shr_head = cur_shr_head->prev;
	}
	free_share_tree(root);
	free(sh);
}



/*
 *=====================================================================
 * free_share_tree(root) - Free share info tree
 * Entry:	root = root of (sub)tree to free
 *=====================================================================
 */
static void
free_share_tree(share_info *root)
{
	if (root == NULL)
		return;
	free_share_tree(root->child);
	free_share_tree(root->sibling);
	if (!root->am_clone) {
		if (root->pattern_type != PATTERN_NONE) {
			regfree(&root->pattern);
		}
	}
	free(root);
}



/*
 *=====================================================================
 * free_users(head) - Free linked list of users rooted at head
 * Entry:	head = ptr to head of list
 * Exit:	List freed, head NULLed
 *=====================================================================
 */
static void
free_users(site_user_info **head)
{
	site_user_info*	cur;
	site_user_info* next;

	for (cur = *head; cur; cur = next) {
		next = cur->next;
		free(cur);
	}
	*head = NULL;
}



/*
 *=====================================================================
 * get_share_ratio(ncpus, asking, amts) - Compute group share use ratio
 *		This is the maximum of the use ratios for classes
 *		that are relevant.
 * Entry:	ncpus = sh_amt array for group allocation
 *		asking = sh_amt array for job,
 *			NULL if desire value for group as a whole.
 *		amts = current use numbers.
 *=====================================================================
 */
double
get_share_ratio(sh_amt* ncpus, sh_amt* asking, sh_amt_array* amts)
{
	int	cls;
	double	ratio = 0.0;
	double	t;

	for (cls = 0; cls < shr_class_count; ++cls) {
		if (ncpus[cls] == 0)
			continue;
		if (asking != NULL && asking[cls] == 0)
			continue;
		t = (double)(amts[cls][J_TYPE_limited]
			+ amts[cls][J_TYPE_borrow])
		/ (double)(ncpus[cls]);
		if (t > ratio)
			ratio = t;
	}
	return ratio;
}



/*
 *=====================================================================
 * init_users(sinfo) - Collect information about users
 * Entry:	sinfo = Server info
 * Returns:	0 on success, else non-zero
 *=====================================================================
 */
static int
init_users(server_info *sinfo)
{
	resource_resv	**resvs = sinfo->jobs;
	resource_resv	*resv;
	job_info	*job;
	int		jcnt = sinfo->sc.total;
	int		i;
	site_user_info	*sui;
	queue_info	*queue;

	free_users(&users);
	for (i = 0; i < jcnt; ++i) {
		resv = resvs[i];
		if (!resv->is_job || (job = resv->job) == NULL)
			continue;
		if ((queue = job->queue) == NULL) {
			job->u_info = NULL;
			continue;
		}
		sui = find_user(&users, resv->user);
		if (sui == NULL) {
			return 1;
		}
		job->u_info = sui;
		/*
		 * Accumulate accrual rates for running jobs
		 */
		if (!job->is_running)
			continue;
		if (queue->is_topjob_set_aside) {
			sui->current_use_pqt += job->accrue_rate;
		} else {
			sui->current_use += job->accrue_rate;
		}
	}
	return 0;
}



/*
 *=====================================================================
 * list_share_info(fp, root, pfx, idx, sname, flag) - Write current share
 *		info to file
 * Entry:	fp = FILE * to write to
 *		root = base of sub-tree to write
 *		pfx = string to prefix each line with
 *		idx = share type to report on
 *		sname = identifier for share type
 *		flag = non-zero to list only leaders
 * Exit:	subtree info written to file
 *=====================================================================
 */
static void
list_share_info(FILE *fp, share_info *root, const char *pfx, int idx, const char *sname, int flag)
{
	if (shr_types == NULL || shr_class_count == 0)
		return;
	if (flag == 0 || root == root->leader) {
		char		buf[J_TYPE_COUNT * 2 * 15];
		char		*p;
		char		*s;
		char		*lname;
		int		j;
		sh_amt		*use_amts;
		sh_amt		*dmd_amts;

		use_amts = &root->share_inuse[idx][0];
		dmd_amts = &root->share_demand[idx][0];
		s = "";
		p = buf;
		for (j = 0; j < J_TYPE_COUNT; ++j) {
			int len;

			len = sprintf(p, "%s%d+%d",
				s, use_amts[j], dmd_amts[j]);
			p += len;
			s = "/";
		}
		lname = root->leader ? root->leader->name : "<no_leader>";
		fprintf(fp, "%s%17s=%s\t%d\t%d\t%d\t%s\t%s\n",
			pfx, root->name, sname,
			root->share_gross[idx], root->share_net[idx],
			root->share_ncpus[idx], buf, lname);
	}
	if (root->child)
		list_share_info(fp, root->child, pfx, idx, sname, flag);
	if (root->sibling)
		list_share_info(fp, root->sibling, pfx, idx, sname, flag);
}



/*
 *=====================================================================
 * set_share_cpus(node, gross, sh_avail) - Apportion CPUs based on allocations
 * Entry:	node = fairshare info subtree
 *		gross = total gross share units
 *		avail = available CPUs of each type
 * Exit:	share_ncpus fields in tree updated
 *=====================================================================
 */
static void
set_share_cpus(share_info *node, sh_amt *gross, sh_amt *sh_avail)
{
	int		i;

	if (node == NULL)
		return;
	/*
	 * Only groups with allocations get ncpus set
	 */
	if (node->share_gross[0] >= 0) {
		int cpus;
		for (i = 0; i < shr_class_count; ++i) {
			if (node->share_net[i] == 0) {
				cpus = 0;
			} else {
				double t_shares, t_cpus;
				t_cpus = sh_avail[i];
				t_shares = gross[i];
				/*
				 * Have to worry about 32-bit overflow in
				 * the following computation.
				 */
				cpus = (int)((t_cpus * node->share_net[i]) /
					t_shares);
				if (cpus < 4) {
					printf("%s: group %s gets only %d %s CPUs\n",
						__func__, node->name,
						cpus, shr_class_name_by_idx(i));
					fflush(stdout);
				}
			}
			node->share_ncpus[i] = cpus;
		}
	} else {
		for (i = 0; i < shr_class_count; ++i) {
			node->share_ncpus[i] = -1;
		}
	}
	if (node->sibling)
		set_share_cpus(node->sibling, gross, sh_avail);
	if (node->child)
		set_share_cpus(node->child, gross, sh_avail);
}



/*
 *=====================================================================
 * bump_share_count(si, stype, sc, sign) - Bump group inuse CPU counts
 * Entry:	si = group's share info
 *		stype = Which counter to bump
 *		sc = Array of counts to bump by.
 *		sign = +/-1 to select incrementing/decrementing
 * Exit:	Counters bumped within tree
 *=====================================================================
 */
static void
bump_share_count(share_info *si, enum site_j_share_type stype, sh_amt *sc, int sign)
{
	share_info	*leader;
	int		i;

	if (si == NULL)
		return;
	/*
	 * Bump count for group itself and for sub-tree leader
	 * (unless group is leader)
	 */
	for (i = 0; i < shr_class_count; ++i) {
		si->share_inuse[i][stype] += sc[i] * sign;
	}
	leader = si->leader;
	if (leader && leader != si) {
		for (i = 0; i < shr_class_count; ++i) {
			leader->share_inuse[i][stype] += sc[i] * sign;
		}
	}
}



/*
 *=====================================================================
 * bump_demand_count(si, stype, sc, sign) - Bump group demand CPU counts
 * Entry:	si = group's share info
 *		stype = Which counter to bump
 *		sc = Array of counts to bump by.
 *		sign = +/-1 to select incrementing/decrementing
 * Exit:	Counters bumped within tree
 *=====================================================================
 */
static void
bump_demand_count(share_info *si, enum site_j_share_type stype, sh_amt *sc, int sign)
{
	share_info	*leader;
	int		i;

	if (si == NULL)
		return;
	for (i = 0; i < shr_class_count; ++i) {
		si->share_demand[i][stype] += sc[i] * sign;
	}
	leader = si->leader;
	if (leader && leader != si) {
		for (i = 0; i < shr_class_count; ++i) {
			leader->share_demand[i][stype] += sc[i] * sign;
		}
	}
}



/*
 *=====================================================================
 * zero_share_counts(node) - zero CPU info in tree
 * Entry:	node = root of portion of tree to zero
 * Exit:	share_inuse[], share_demand[] zeroed in sub-tree
 *=====================================================================
 */
static void
zero_share_counts(share_info *node)
{
	if (node == NULL)
		return;
	memset(node->share_inuse, 0, shr_class_count * sizeof(*node->share_inuse));
	memset(node->share_demand, 0, shr_class_count * sizeof(*node->share_demand));
	if (node->child)
		zero_share_counts(node->child);
	if (node->sibling)
		zero_share_counts(node->sibling);
}



/*
 *=====================================================================
 * new_share_head(cnt) - Allocate new share_info head structure
 * Entry:	cnt = number of sh_amt classes
 * Returns:	pointer to initialized head structure
 *=====================================================================
 */
static share_head *
new_share_head(int cnt)
{
	share_head	*newsh;
	size_t		sz;
	sh_amt		*ptr;

	/*
	 * Double cnt to allow space for backup copy of class values.
	 * Original values go in indices 0..cnt-1, backup in cnt..2*cnt-1
	 */
	cnt *= 2;

	sz = sizeof(struct share_head);
	sz += cnt * sizeof(sh_amt);	/*active*/
	sz += cnt * sizeof(sh_amt);	/*avail*/
	sz += cnt * sizeof(sh_amt);	/*contrib*/
	sz += cnt * sizeof(sh_amt);	/*total*/
	newsh = calloc(1, sz);
	if (newsh == NULL)
		return NULL;
	ptr = (sh_amt *)(newsh + 1);
	newsh->sh_active = ptr;
	ptr += cnt;
	newsh->sh_avail = ptr;
	ptr += cnt;
	newsh->sh_contrib = ptr;
	ptr += cnt;
	newsh->sh_total = ptr;
	ptr += cnt;
	return newsh;
}



/*
 *=====================================================================
 * new_share_info(name, cnt) - Create new share_info node
 * Entry:	name = name to assign to node
 *		cnt = number of classes to make room for.
 * Returns:	pointer to new share_info struct
 *=====================================================================
 */
static share_info *
new_share_info(char *name, int cnt)
{
	size_t		sz;
	sh_amt		*ptr;
	sh_amt_array	*aptr;
	share_info	*si;

	/*
	 * The share_info struct contains pointers to variable-sized
	 * arrays of sh_amts.  These arrays are allocated after the
	 * base structure and the pointers set to point to them.
	 */
	/*
	 * We allocate space for backup copies of some items.
	 * Original values use indices 0..cnt-1, backups use cnt..2*cnt-1.
	 * Note that for sh_amt_arrays, the backup copies are after all
	 * the original arrays, so again, the original values use indices
	 * 0..cnt-1 as the first subscript, and the backups use cnt..2*cnt-1.
	 */
	sz = sizeof(share_info);
	sz += cnt * sizeof(sh_amt);		/*gross*/
	sz += cnt * sizeof(sh_amt);		/*net*/
	sz += cnt * sizeof(sh_amt);		/*ncpus*/
	sz += 2 * cnt * sizeof(sh_amt_array);	/*inuse + backup*/
	sz += 2 * cnt * sizeof(sh_amt_array);	/*demand + backup*/
	si = calloc(1, sz + strlen(name) + 1);
	if (si != NULL) {
		ptr = (sh_amt *)(si + 1);
		si->share_gross = ptr;
		ptr += cnt;
		si->share_net = ptr;
		ptr += cnt;
		si->share_ncpus = ptr;
		ptr += cnt;
		aptr = (sh_amt_array *) ptr;
		si->share_inuse = aptr;
		aptr += 2 * cnt;
		si->share_demand = aptr;
		aptr += 2 * cnt;
		si->name = (char *)aptr;
		assert(si->name - (char *)si <= sz);
		strcpy(si->name, name);
		si->size = sz;
	}
	return si;
}



/*
 *=====================================================================
 * new_share_info_clone(old) - Clone a share_info structure
 *	Returned node has copy of sh_amt values, but shares
 *	name.
 * Entry:	old = ptr to existing share_info to copy
 * Returns:	ptr to clone
 *=====================================================================
 */
static share_info *
new_share_info_clone(share_info *old)
{
	share_info	*si;
	sh_amt		*ptr;
	sh_amt_array	*aptr;
	int		cnt = shr_class_count;

	if (old == NULL)
		return NULL;
	si = malloc(old->size);
	if (si) {
		memcpy(si, old, old->size);
		/* Zap tree pointers */
		si->parent = si->sibling = si->child = si->leader = NULL;
		si->am_clone = 1;
		/*
		 * Adjust internal pointers
		 */
		ptr = (sh_amt *)(si + 1);
		si->share_gross = ptr;
	ptr += cnt;
		si->share_net = ptr;
	ptr += cnt;
		si->share_ncpus = ptr;
	ptr += cnt;
		aptr = (sh_amt_array *) ptr;
		si->share_inuse = aptr;
	aptr += 2 * cnt;
		si->share_demand = aptr;
aptr += 2 * cnt;
	}
	return si;
}



/*
 *=====================================================================
 * reconcile_shares(root, cnt) - Complete construction of share tree after
 *		share file all read.
 * Entry:	root = root of share_info tree
 *		cnt = count of sh_amt entries in amount arrays
 * Returns:	1 if all okay, else 0
 *=====================================================================
 */
static int
reconcile_shares(share_info *root, int cnt)
{
	int	i;
	int	result = 1;

	if (root == NULL)
		return result;		/* Nothing to do */
	root->leader = root;		/* ROOT is its own leader */
	for (i = 0; i < cnt; ++i)
		root->share_gross[i] = -2;
	result = reconcile_share_tree(root, root, cnt);
	return result;
}



/*
 *=====================================================================
 * reconcile_share_tree(root, def, cnt) - Complete construction of
 *		share info subtree.
 * Entry:	root = root of subtree
 *		def = default leader for this subtree
 *		cnt = count of sh_amt entries in amount arrays
 * Returns:	1 if all okay, else 0
 *=====================================================================
 */
static int
reconcile_share_tree(share_info *root, share_info *def, int cnt)
{
	share_info	*child;
	int		i;

	if (root == NULL || def == NULL)
		return 1;
	/*
	 * If current root has allocation, it becomes default leader for
	 * it and its kiddies.
	 */
	for (i = 0; i < cnt; ++i) {
		if (root->share_gross[i] > 0) {
			def = root;
			break;
		}
	}
	root->leader = def;
	/*
	 * Traverse tree depth-first, using share_net as temp to accumulate
	 * gross values for children.
	 */
	for (i = 0; i < cnt; ++i) {
		root->share_net[i] = 0;
	}
	for (child = root->child; child; child = child->sibling) {
		if (!reconcile_share_tree(child, def, cnt)) {
			return 0;
		}
		for (i = 0; i < cnt; ++i) {
			root->share_net[i] += child->share_net[i];
		}
	}
	/*
	 * If we are a leader, make sure our share is sufficient to cover
	 * our children.  If not, gripe and increase it to match.
	 */
	if (def == root) {
		for (i = 0; i < cnt; ++i) {
			sh_amt c_sum, gross;

			gross = root->share_gross[i];
			c_sum = root->share_net[i];
			if (c_sum > gross) {
				if (gross >= 0) {
					sprintf(log_buffer,
						"%s share for %s too small for children: %d < %d",
						root->name, shr_class_name_by_idx(i),
						gross, c_sum);
					log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE,
						LOG_NOTICE, __func__, log_buffer);
				}
				root->share_gross[i] = gross = c_sum;
			}
			root->share_net[i] = gross - c_sum;
		}
	} else {
		for (i = 0; i < cnt; ++i) {
			root->share_gross[i] = -1;
		}
	}
	return 1;
}



/*
 *=====================================================================
 * shr_class_info_by_idx(idx) - Look up Nth CPU share class info.
 * Entry:	idx = index of share class
 * Returns:	pointer to matching class info, or default entry
 *=====================================================================
 */
#if 0
static struct shr_class *
shr_class_info_by_idx(int idx)
{
	struct shr_class	*scp;

	for (scp = shr_classes; scp; scp = scp->next) {
		if (scp->sh_cls == idx)
			break;
	}
	if (scp == NULL)
		scp = shr_classes;
	return scp;
}
#endif



/*
 *=====================================================================
 * shr_class_info_by_name(name) - Look up CPU share class by class name
 * Entry:	name = name of class
 * Returns:	pointer to matching class info, or default entry.
 *=====================================================================
 */
#if 0
static struct shr_class *
shr_class_info_by_name(const char * name)
{
	struct shr_class	*scp;

	for (scp = shr_classes; scp; scp = scp->next) {
		if (strcmp(scp->name, name) == 0)
			break;
	}
	if (scp == NULL)
		scp = shr_classes;
	return scp;
}
#endif



/*
 *=====================================================================
 * shr_class_info_by_type_name(name) - Look up share class by type name
 * Entry:	name = name of CPU type to look up
 * Returns:	pointer to matching share class, or default class if no
 *		match
 *=====================================================================
 */
#if 0
static struct shr_class *
shr_class_info_by_type_name(const char * name)
{
	struct shr_type	*stp;
	struct shr_class	*scp;

	for (stp = shr_types; stp; stp = stp->next) {
		if (strcmp(name, stp->name) == 0) {
			scp = shr_class_info_by_idx(stp->sh_cls);
			break;
		}
	}
	if (stp == NULL || scp == NULL)
		scp = shr_classes;
	return scp;
}
#endif



/*
 *=====================================================================
 * shr_class_name_by_idx(idx) - Look up Nth share class name.
 * Entry:	idx = which share class to find
 * Returns:	matching class name or "" if none
 *=====================================================================
 */
static char *
shr_class_name_by_idx(int idx)
{
	struct shr_class	*scp;
	char *sp;

	for (scp = shr_classes; scp; scp = scp->next) {
		if (scp->sh_cls == idx)
			break;
	}
	sp = scp ? scp->name : "";
	return sp;
}



/*
 *=====================================================================
 * shr_type_info_by_idx(idx) - Look up Nth CPU type info
 * Entry:	idx = desired CPU type
 * Returns:	pointer to idx'th CPU type info, or default type info
 *=====================================================================
 */
static struct shr_type *
shr_type_info_by_idx(int idx)
{
	struct shr_type	*stp;

	for (stp = shr_types; stp; stp = stp->next) {
		if (stp->sh_tidx == idx)
			break;
	}
	if (stp == NULL)
		stp = shr_types;
	return stp;
}



/*
 *=====================================================================
 * shr_type_info_by_name(name) - Look up CPU type info by type name
 * Entry:	name = desired CPU type name
 * Returns:	pointer to matching CPU type info, or default type
 *=====================================================================
 */
static struct shr_type *
shr_type_info_by_name(const char* name)
{
	struct shr_type	*stp;

	for (stp = shr_types; stp; stp = stp->next) {
		if (strcmp(stp->name, name) == 0)
			break;
	}
	if (stp == NULL)
		stp = shr_types;
	return stp;
}



/*
 *=====================================================================
 * squirrel_shr_head(sinfo) - make backup of alterable shares data
 * Entry:	sinfo = current server info
 *=====================================================================
 */
static void
squirrel_shr_head(server_info *sinfo)
{
	share_head	*sh;
	int		cnt = shr_class_count;

	if (sinfo == NULL || (sh = sinfo->share_head) == NULL)
		return;
#define MM(x) memmove(sh->x + cnt, sh->x, cnt * sizeof(*sh->x))
	MM(sh_active);
	MM(sh_avail);
	MM(sh_contrib);
	MM(sh_total);
#undef MM
	squirrel_shr_tree(sh->root);
}


/*
 *=====================================================================
 * un_squirrel_shr_head(sinfo) - restore share values from backup
 * Entry:	sinfo = server info
 *=====================================================================
 */
static void
un_squirrel_shr_head(server_info *sinfo)
{
	share_head	*sh;
	int		cnt = shr_class_count;

	if (sinfo == NULL || (sh = sinfo->share_head) == NULL)
		return;
#define MM(x) memmove(sh->x, sh->x + cnt, cnt * sizeof(*sh->x))
	MM(sh_active);
	MM(sh_avail);
	MM(sh_contrib);
	MM(sh_total);
#undef MM
	un_squirrel_shr_tree(sh->root);
}



/*
 *=====================================================================
 * squirrel_shr_tree(root) - make backup of alterable shares data
 * Entry:	root = root of (sub)tree of share_info to backup.
 *=====================================================================
 */
static void
squirrel_shr_tree(share_info *root)
{
	int		cnt = shr_class_count;

	if (root == NULL)
		return;
#define	MM(x) memmove(root->x + cnt, root->x, cnt * sizeof(*root->x))
	MM(share_inuse);
	MM(share_demand);
#undef MM
	if (root->sibling)
		squirrel_shr_tree(root->sibling);
	if (root->child)
		squirrel_shr_tree(root->child);
	root->ratio_bak = root->ratio;
}



/*
 *=====================================================================
 * un_squirrel_shr_tree(root) - restore alterable share data
 * Entry:	root = root of (sub)tree of share_info to restore.
 *=====================================================================
 */
static void
un_squirrel_shr_tree(share_info *root)
{
	int		cnt = shr_class_count;

	if (root == NULL)
		return;
#define	MM(x) memmove(root->x, root->x + cnt, cnt * sizeof(*root->x))
	MM(share_inuse);
	MM(share_demand);
#undef MM
	if (root->sibling)
		un_squirrel_shr_tree(root->sibling);
	if (root->child)
		un_squirrel_shr_tree(root->child);
	root->ratio = root->ratio_bak;
}



/*
 *=====================================================================
 * pick_next_job(policy, jobs, pnfilter, si) - Slightly modified version
 *		of Altair's extract_fairshare. We add an additional job
 *		check using the pnfilter function
 * Entry:	policy = current scheduler policy structure
 *		jobs = list of jobs to search
 *		pnfilter = pointer to a binary job filter function
 *		si = pointer to current most favored share
 * Returns:	pointer to next job that matches search criteria, else NULL
 *=====================================================================
 */
static resource_resv *
pick_next_job(status *policy, resource_resv **jobs, pick_next_filter pnfilter, share_info *si)
{
	resource_resv *good = NULL;	/* job with the min usage / percentage */
	int cmp;			/* comparison value of two jobs */
	int i;

	if (policy == NULL || jobs == NULL || pnfilter == NULL)
		return NULL;

	for (i = 0; jobs[i] != NULL; i++) {
		if (jobs[i]->is_job && jobs[i]->job !=NULL) {
			if (!jobs[i]->can_not_run && in_runnable_state(jobs[i]) &&
				pnfilter(jobs[i], si)) {
				if (!policy->fair_share)
					return jobs[i];

				if (good == NULL) {
					good = jobs[i];
					continue;
				}
				/*
				 * Restrict share comparisons to same job sort level.
				 */
				if (multi_sort(good, jobs[i]) != 0) {
#if NAS_DEBUG
					printf("%s: stopped at %s vs. %s\n",
						__func__, good->name, jobs[i]->name);
					fflush(stdout);
#endif
					break;
				}
				if (good->job->ginfo != jobs[i]->job->ginfo) {
					cmp = compare_path(good->job->ginfo->gpath,
						jobs[i]->job->ginfo->gpath);
					if (cmp > 0)
						good = jobs[i];
				}
			}
		}
	}
	return good;
}



/*
 *=====================================================================
 * job_filter_hwy149(resv, si) - binary job filter
 * Entry:	resv = job
 *		si = pointer to current most favored share
 * Returns:	1 if job passes filter, else 0
 *=====================================================================
 */
#ifdef	NAS_HWY149
static int
job_filter_hwy149(resource_resv *resv, share_info *si)
{
	if (resv == NULL || resv->job == NULL)
		return 0;

	if (resv->job->priority == NAS_HWY149 ||
		resv->job->NAS_pri == NAS_HWY149)
		return 1;

	return 0;
}
#endif



/*
 *=====================================================================
 * job_filter_dedres(resv, si) - binary job filter
 * Entry:	resv = job
 *		si = pointer to current most favored share
 * Returns:	1 if job passes filter, else 0
 *=====================================================================
 */
static int
job_filter_dedres(resource_resv *resv, share_info *si)
{
	if (resv == NULL)
		return 0;

	if (site_is_queue_topjob_set_aside(resv) &&
		num_topjobs_per_queues < conf.per_queues_topjobs)
		return 1;

	return 0;
}



/*
 *=====================================================================
 * job_filter_hwy101(resv, si) - binary job filter
 * Entry:	resv = job
 *		si = pointer to current most favored share
 * Returns:	1 if job passes filter, else 0
 *=====================================================================
 */
#ifdef	NAS_HWY101
static int
job_filter_hwy101(resource_resv *resv, share_info *si)
{
	if (resv == NULL || resv->job == NULL)
		return 0;

	if (resv->job->priority == NAS_HWY101 ||
		resv->job->NAS_pri == NAS_HWY101)
		return 1;

	return 0;
}
#endif



/*
 *=====================================================================
 * job_filter_normal(resv, si) - binary job filter
 * Entry:	resv = job
 *		si = pointer to current most favored share
 * Returns:	1 if job passes filter, else 0
 *=====================================================================
 */
static int
job_filter_normal(resource_resv *resv, share_info *si)
{
	if (resv == NULL || resv->job == NULL)
		return 0;

	if (si == NULL || resv->job->sh_info == NULL)
		/* Not using shares */
		return 1;
	if (resv->job->sh_info->leader == si &&
		!site_is_queue_topjob_set_aside(resv))
		return 1;

	return 0;
}



/*
 *=====================================================================
 *=====================================================================
 */


/* start localmod 030 */
/*
 *=====================================================================
 * check_for_cycle_interrupt(do_logging) - Check if a cycle interrupt
 has been requested.
 * Entry	do_logging = whether to print to scheduler log
 * Returns	1 if cycle should be interrupted
 *		0 if cycle should continue
 *=====================================================================
 */
int
check_for_cycle_interrupt(int do_logging)
{
	if (!do_soft_cycle_interrupt && !do_hard_cycle_interrupt) {
		return 0;
	}

	if (!do_hard_cycle_interrupt &&
	    consecutive_interrupted_cycles >= conf.max_intrptd_cycles) {
		return 0;
	}

	if (do_hard_cycle_interrupt ||
	    time(NULL) >=
		interrupted_cycle_start_time + conf.min_intrptd_cycle_length) {
		if (do_logging)
			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__,
				"Short circuit of this cycle");

		return 1;
	}

	if (do_logging) {
		sprintf(log_buffer, "Too early to short circuit (%ds elapsed, need %ds)",
			(int)(time(NULL) - interrupted_cycle_start_time),
			conf.min_intrptd_cycle_length);
		log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__, log_buffer);
	}

	return 0;
}
/* end localmod 030 */

#endif /* NAS */

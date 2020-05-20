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
 * site_data.h - Site additions to scheduler data types
 */

#ifdef NAS

typedef sh_amt	sh_amt_array[J_TYPE_COUNT];

struct share_info
{
	char		*name;		/* Name for share group */
	share_info	*parent;	/* Pointers to build share tree */
	share_info	*sibling;
	share_info	*child;
	share_info	*leader;	/* group owning share this group uses */
	share_info	*tptr;		/* temp link for during tree manip */
	size_t		size;		/* total size of struct, less name */
	int		am_clone;	/* true if we are clone of another */
	int		lineno;		/* line number from shares file */
	int		topjob_count;	/* jobs considered this cycle */
	int		none_left;	/* all jobs for share considered */
	enum pattern_type {		/* what type of pattern is name */
		PATTERN_NONE = 0		/* not a pattern -> exact match */
		, PATTERN_COMBINED = 1	/* pattern, usage all lumped together */
		, PATTERN_SEPARATE = 2	/* pattern, record usage for each */
	} pattern_type;
	regex_t pattern;		/* name compiled into a regex */
	double		ratio;		/* current use / allocation */
	double		ratio_bak;	/* backup copy of ratio */
	/* localmod 154 */
	double		ratio_max;	/* max ratio seen during calendaring */
	double		tj_cpu_cost;	/* how much CPU time has been consumed
					 * putting top jobs on calendar */
	sh_amt	*share_gross;		/* group's gross share, if specified */
	sh_amt	*share_net;		/* gross minus children's gross */
	sh_amt	*share_ncpus;		/* share, as CPU count */
	sh_amt_array	*share_inuse;	/* current CPU use by this group */
	sh_amt_array	*share_demand;	/* current CPU unmet demand */
};

struct share_head
{
	share_info	*root;		/* root of share tree */
	share_head	*prev;		/* tree this was cloned from */
	sh_amt		*sh_active;	/* CPU counts in use */
	sh_amt		*sh_avail;	/* CPU counts not in use */
	sh_amt		*sh_contrib;	/* CPU counts that can be borrowed */
	sh_amt		*sh_total;	/* total allocatable CPU counts */
};

struct site_user_info {
	struct site_user_info*	next;	/* Linked list */
	sch_resource_t	current_use;	/* Total accrual rate normal queues */
	sch_resource_t	current_use_pqt; /* Accrual in set-aside queues */
	sch_resource_t	saved_cu;	/* Saved current_use */
	sch_resource_t	saved_cup;	/* Saved current_use_pqt */
	char		user_name[1];	/* Dummy length */
};

#endif /* NAS */

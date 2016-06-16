/*
 * site_data.h - Site additions to scheduler data types
 * $Id: site_data.h,v 1.8 2016/02/26 17:38:56 dtalcott Exp $
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

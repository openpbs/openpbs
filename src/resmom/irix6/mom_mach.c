/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */

#include <pbs_config.h>

#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <dirent.h>
#include <fcntl.h>
#include <errno.h>
#include <strings.h>
#include <pwd.h>
#include <mntent.h>
#include <sys/types.h>
#include <sys/time.h>
#include <sys/procfs.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/quota.h>
#include <sys/statfs.h>
#include <sys/sysmacros.h>
#include <sys/sysmp.h>
#include <sys/resource.h>
#include <sys/schedctl.h>
#include <optional_sym.h>
#if MOM_CHECKPOINT == 1
#include <ckpt.h>
#endif	/* MOM_CHECKPOINT */
#if	NODEMASK != 0
#define SN0XXL 1
#include <sys/syssgi.h>
#include <sys/pmo.h>
#include "bitfield.h"
#endif	/* NODEMASK */
#include <sys/syssgi.h>
#include <sys/pmo.h>
#include "bitfield.h"

#include "pbs_error.h"
#include "portability.h"
#include "list_link.h"
#include "server_limits.h"
#include "attribute.h"
#include "resource.h"
#include "job.h"
#include "log.h"
#include "mom_mach.h"
#include "resmon.h"
#include "../rm_dep.h"
#include "mom_func.h"

/**
 * @file
 * @brief
 *	System dependent code to gather information for the resource
 *	monitor for a Silicon Graphics (SGI) machine.
 *
 * @par Resources known by this code:
 *		cput		cpu time for a pid or session
 *		mem		memory size for a pid or session in KB
 *		resi		resident memory size for a pid or session in KB
 *		sessions	list of sessions in the system
 *		pids		list of pids in a session
 *		nsessions	number of sessions in the system
 *		nusers		number of users in the system
 *		totmem		total memory size in KB
 *		availmem	available memory size in KB
 *		ncpus		number of cpus
 *		physmem		physical memory size in KB
 *		size		size of a file or filesystem in KB
 *		idletime	seconds of idle time (see mom_main.c)
 *		walltime	wall clock time for a pid
 *		loadave		current load average
 *		quota		quota information (sizes in KB)
 */


#ifndef TRUE
#define FALSE	0
#define TRUE	1
#endif	/* TRUE */

/* min period between two cput samples - in seconds */
#define PBS_MIN_CPUPERCENT_PERIOD   30


static	char		*procfs;
static	char		*procfmts;
static	DIR		*pdir = NULL;
static	int		pagesize;
static	int		kfd = -1;
static  time_t		sampletime_ceil;
static	time_t		sampletime_floor;
static  int		cpr_master_flag = CKPT_NQE | CKPT_ATTRFILE_IN_CWD;

#define	TBL_INC		200		/* initial proc table */
#define MAPNUM		512		/* max number of mem segs */

static  rlim64_t(*presi_sum)(job *);
static	int		nproc = 0;
static	int		max_proc = 0;
struct	proc_info {			/* structure used to hold proc info */
	prpsinfo_t	info;
	int		map_num;
	prmap_sgi_t	*map;
};
static	struct	proc_info	*proc_array = NULL;
static  time_t			 sampletime;
static  int     myproc_max = 0;		/* entries in Proc_lnks  */
pbs_plinks     *Proc_lnks = NULL;       /* process links table head */

extern	char	*ret_string;
time_t		wait_time = 10;
extern	char	extra_parm[];
extern	char	no_parm[];

extern	time_t	time_now;
extern	time_t	last_scan;
extern	int	exiting_tasks;

/*
 ** external functions and data
 */
extern	int	nice_val;
extern	struct	config		*search(struct config *, char *);
extern	struct	rm_attribute	*momgetattr(char *);
extern	int			rm_errno;
extern	unsigned	int	reqnum;
extern	double	cputfactor;
extern	double	wallfactor;
extern  int	complex_mem_calc;
extern  pid_t   mom_pid;
extern	int	num_acpus;
extern	int	num_pcpus;
extern  struct rlimit64 orig_stack_size;	/* see mom_main.c */

/*
 ** local functions and data
 */
static char	*resi		(struct rm_attribute *attrib);
static char	*totmem		(struct rm_attribute *attrib);
static char	*availmem	(struct rm_attribute *attrib);
char	*physmem	(struct rm_attribute *attrib);
static char	*ncpus		(struct rm_attribute *attrib);
static char	*walltime	(struct rm_attribute *attrib);
static char	*quota		(struct rm_attribute *attrib);

extern char	*loadave	(struct rm_attribute *attrib);
extern char	*nullproc	(struct rm_attribute *attrib);

extern int nodemask_str2bits(char *, Bitfield *);

extern char *nodemask_bits2str(Bitfield *);

static rlim64_t resi_sum_simple(job *);
static rlim64_t resi_sum_complex(job *);
/*
 ** local resource array
 */
struct	config	dependent_config[] = {
	{ "resi",	resi },
	{ "totmem",	totmem },
	{ "availmem",	availmem },
	{ "physmem",	physmem },
	{ "ncpus",	ncpus },
	{ "loadave",	loadave },
	{ "walltime",	walltime },
	{ "quota",	quota },
	{ NULL,		nullproc },
};

off_t	kern_addr[] = {
	-1,			/* KSYM_PHYS */
	-1,			/* KSYM_LOAD */
};

int	mom_does_chkpnt = 1;

#define	KSYM_PHYS	0
#define	KSYM_LOAD	1

/**
 * @brief
 *      initialize the platform-dependent topology information
 *
 * @return      Void
 *
 */
void
dep_initialize()
{
	int	 i;
	static	char	mem[] = "/dev/kmem";

	pagesize = getpagesize();

	num_pcpus = sysmp(MP_NPROCS);
	num_acpus = sysmp(MP_NAPROCS);

	if (complex_mem_calc == 1) {
		procfs   = "/proc";
		procfmts = "/proc/%s";
		presi_sum = resi_sum_complex;
	} else {
		procfs   = "/proc/pinfo";
		procfmts = "/proc/pinfo/%s";
		presi_sum = resi_sum_simple;
	}

	if ((pdir = opendir(procfs)) == NULL) {
		log_err(errno, __func__, "opendir");
		return;
	}

	kern_addr[KSYM_PHYS] = SEEKLIMIT & sysmp(MP_KERNADDR, MPKA_PHYSMEM);
	kern_addr[KSYM_LOAD] = SEEKLIMIT & sysmp(MP_KERNADDR, MPKA_AVENRUN);

	if ((kfd = open(mem, O_RDONLY)) == -1) {
		log_err(errno, __func__, mem);
		return;
	}

	/* insure /dev/kmem closed on exec */

	if ((i = fcntl(kfd,  F_GETFD)) == -1) {
		log_err(errno, __func__, "F_GETFD");
	}
	i |= FD_CLOEXEC;
	if (fcntl(kfd, F_SETFD, i) == -1) {
		log_err(errno, __func__, "F_SETFD");
	}

	return;
}

/**
 * @brief
 *      clean up platform-dependent topology information
 *
 * @return      Void
 *
 */
void
dep_cleanup()
{

	if (pdir) {
		closedir(pdir);
		pdir = NULL;
	}
	if (kfd != -1)
		close(kfd);
}

/**
 * @brief
 *      Don't need any periodic procsessing except in some special cases.
 *
 * @return      Void
 *
 */
void
end_proc()
{
	return;
}

/**
 * @brief
 * 	set by Administrator to cause OS upgradeable checkpoints to occur
 *
 * @param[in] value value for upgrade
 *
 * @return	unsigned long
 * @return	0		error
 * @retval	1		success
 */
unsigned long
set_checkpoint_upgrade(char *value)
{
	int		val = 0;

	if (set_boolean(__func__, value, &val) == HANDLER_FAIL)
		return 0;

	if (val)
		cpr_master_flag |= CKPT_CHECKPOINT_UPGRADE;

	return 1;
}

/*
 * Time decoding macro.  Accepts a timestruc_t pointer.  Returns unsigned long
 * time in seconds, rounded.
 */

#define tv(val) (ulong)((val).tv_sec + ((val).tv_nsec + 500000000)/1000000000)

/**
 * @brief
 *      Scan a job's list of tasks and return true if one of them matches
 *      the SGI JobID, or process (sid or pid) represented by *psp.
 *
 * @param[in] pjob - job pointer
 * @param[in] psp - pointer to prpsinfo_t structure
 *
 * @return	int
 * @retval	TRUE	Success
 * @retval	FALSE	Error
 *
 */
static int
injob(job *pjob, prpsinfo_t *psp)
{
	task		*ptask;
	pid_t		key;
	pbs_list_head 	*phead;

	if (pjob->ji_extended.ji_ext.ji_jid > 0) {
		/* use sgi job id */
		if (pjob->ji_extended.ji_ext.ji_jid == psp->pr_jid)
			return TRUE;
		else
			return FALSE;
	}

	/* no job id, fall back to sid */

	key = (psp->pr_sid == 0) ? psp->pr_pid : psp->pr_sid;
	phead = &pjob->ji_tasks;
	for (ptask = (task *)GET_NEXT(*phead);
		ptask;
		ptask = (task *)GET_NEXT(ptask->ti_jobtask)) {
		if (ptask->ti_qs.ti_sid <= 1)
			continue;
		if (ptask->ti_qs.ti_sid == key)
			return TRUE;
	}
	return FALSE;
}

/**
 * @brief
 *      Internal session cpu time decoding routine.
 *
 * @param[in] job - a job pointer.
 *
 * @return      ulong
 * @retval      sum of all cpu time consumed for all tasks executed by the job, in seconds,
 *              adjusted by cputfactor.
 *
 */
static unsigned long
cput_sum(job *pjob)
{
	int			i;
	ulong			cputime = 0;
	int			nps = 0;
	int			taskprocs;
	ulong			proctime;
	prpsinfo_t		*pi;
	struct	jobrusage	job_usage;
	task			*ptask;
	pid_t			key;
	u_long			tcput;
	int jlimits_installed = _MIPS_SYMBOL_PRESENT(getjusage);

	memset(&job_usage, 0, sizeof(job_usage));
	if (jlimits_installed && (pjob->ji_extended.ji_ext.ji_jid > 0)) {
		if (getjusage(pjob->ji_extended.ji_ext.ji_jid, JLIMIT_CPU,
			&job_usage) == 0) {
			if (job_usage.high_usage != 0) {
				sampletime_ceil=time(0);
				return (u_long)((double)job_usage.high_usage *
					cputfactor);
			}
		} else if (errno == ENOPKG) {
			/* shouldn't get here with a irixjid */
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
				LOG_WARNING,
				pjob->ji_qs.ji_jobid,
				"IRIX JID of job found but no jlimits");
			pjob->ji_extended.ji_ext.ji_jid = 0;
		}
	}

	/* fall back to looking at each process */
	for (ptask = (task *)GET_NEXT(pjob->ji_tasks);
		ptask != NULL;
		ptask = (task *)GET_NEXT(ptask->ti_jobtask)) {

		/* DEAD task */
		if (ptask->ti_qs.ti_sid <= 1) {
			cputime += ptask->ti_cput;
			continue;
		}

		tcput = 0;
		taskprocs = 0;
		for (i=0; i<nproc; i++) {
			pi = &proc_array[i].info;
			key = (pi->pr_sid == 0) ? pi->pr_pid : pi->pr_sid;

			/* is this process part of the task? */
			if (ptask->ti_qs.ti_sid != key)
				continue;

			nps++;
			taskprocs++;

			/*
			 ** Count a zombie's time only if it is the top process
			 ** in a task.
			 */
			if (pi->pr_zomb &&
				(pi->pr_pid != pi->pr_sid) &&
				(pi->pr_ppid != mom_pid))
				continue;

			proctime = tv(pi->pr_time) + tv(pi->pr_ctime);
			tcput += proctime;
			DBPRT(("%s: ses %d pid %d pcput %lu cputime %lu\n",
				__func__, pi->pr_sid, pi->pr_pid, proctime, tcput))
		}

		if (tcput > ptask->ti_cput)
			ptask->ti_cput = tcput;
		cputime += ptask->ti_cput;
		DBPRT(("%s: task %08.8X cput %lu total %lu\n", __func__,
			ptask->ti_qs.ti_task, ptask->ti_cput, cputime))

		if (taskprocs == 0) {
			sprintf(log_buffer,
				"no active process for task %8.8X",
				ptask->ti_qs.ti_task);
			log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
				LOG_INFO, pjob->ji_qs.ji_jobid,
				log_buffer);
			ptask->ti_qs.ti_exitstat = 0;
			ptask->ti_qs.ti_status = TI_STATE_EXITED;
			if (pjob->ji_qs.ji_un.ji_momt.ji_exitstat >= 0)
				pjob->ji_qs.ji_un.ji_momt.ji_exitstat = 0;
			task_save(ptask);
			exiting_tasks = 1;
		}
	}

	if (nps == 0)
		pjob->ji_flags |= MOM_NO_PROC;

	return ((unsigned long)((double)cputime * cputfactor));
}

/**
 * @brief
 *      Internal session memory usage function.
 *
 * @param[in] job - job pointer
 *
 * @return      ulong
 * @retval      the total number of bytes of address
 *              space consumed by all current processes within the job.
 *
 */
static unsigned long 
mem_sum(job *pjob)
{
	int			i;
	rlim64_t		segadd;
	prpsinfo_t		*pi;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))

	segadd = 0;
	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (!injob(pjob, pi))
			continue;

		DBPRT(("%s: %s(%d:%d) mem %llu\n",
			__func__, pi->pr_fname, pi->pr_sid, pi->pr_pid,
			(rlim64_t)((rlim64_t)pi->pr_size * (rlim64_t)pagesize)))

		segadd += (rlim64_t)((rlim64_t)pi->pr_size*(rlim64_t)pagesize);
	}
	DBPRT(("%s: total mem %llu\n\n", __func__, segadd))
	return (segadd);
}

/**
 * @brief
 * 	Internal session mem (workingset) size function.  COMPLEX CALC VERSION
 *
 * @param[in] pjob - job pointer
 *
 * @return      Returns in a 64 bit intege the number of bytes used by session
 *
 */
static rlim64_t
resi_sum_complex(job *pjob)
{
	rlim64_t		resisize, resisub;
	int			num, i, j;
	prpsinfo_t		*pi;
	prmap_sgi_t		*mp;
	u_long			lastseg, nbps;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))

	resisize = 0;
	lastseg = 99999;
	nbps = (pagesize / sizeof(uint_t)) * pagesize;
	/* sysmacros.h says "4Meg" ...hmmm */

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (!injob(pjob, pi))
			continue;

		DBPRT(("%s: %s(%d:%d) rss %llu\n",
			__func__, pi->pr_fname, pi->pr_sid, pi->pr_pid,
			(rlim64_t)((rlim64_t)pi->pr_rssize *
			(rlim64_t)pagesize)))

		resisub = 0;
		num = proc_array[i].map_num;
		mp = proc_array[i].map;
		for (j=0; j<num; j++, mp++) {
			u_long	cnt = mp->pr_mflags >> MA_REFCNT_SHIFT;
			u_long	end = (u_long)mp->pr_vaddr + mp->pr_size - 1;
			u_long	seg1 = (u_long)mp->pr_vaddr / nbps;
			u_long	seg2 = end / nbps;
			rlim64_t	numseg = seg2 - seg1;

			if (lastseg != seg2)
				numseg++;
			lastseg = seg2;
			numseg = numseg*pagesize/cnt;
			numseg += mp->pr_wsize*pagesize/MA_WSIZE_FRAC/cnt;
			resisub += numseg;
			DBPRT(("%s: %d\t%lluk\t%lluk\n", __func__, j,
				numseg/1024, resisub/1024))
		}
		resisize += resisub;
		DBPRT(("%s: %s subtotal rss %llu\n", __func__,
			pi->pr_fname, resisub))
	}
	DBPRT(("%s: total rss %llu\n\n", __func__, resisize))

	return (resisize);
}

/**
 * @brief
 * 	Internal session mem (workingset) size function.  SIMPLE CALC VERSION
 *
 * @param[in] pjob - job pointer
 *
 * @return	Returns in a 64 bit intege the number of bytes used by session
 *
 */
static rlim64_t
resi_sum_simple(job *pjob)
{
	int			i;
	rlim64_t		resisize;
	prpsinfo_t		*pi;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))

	resisize = 0;
	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (!injob(pjob, pi))
			continue;

		DBPRT(("%s: %s(%d:%d) rss %llu\n",
			__func__, pi->pr_fname, pi->pr_sid, pi->pr_pid,
			(rlim64_t)((rlim64_t)pi->pr_rssize *
			(rlim64_t)pagesize)))
		resisize += (rlim64_t)((rlim64_t)pagesize * pi->pr_rssize);
	}
	DBPRT(("%s: total rss %llu\n\n", __func__, resisize))
	return (resisize);
}

/**
 * @brief
 *      Establish system-enforced limits for the job.
 *
 *      Run through the resource list, checking the values for all items
 *      we recognize.
 *
 * @param[in] pjob - job pointer
 * @param[in]  set_mode - setting mode
 *
 *      If set_mode is SET_LIMIT_SET, then also set hard limits for the
 *                        system enforced limits (not-polled).
 *      If anything goes wrong with the process, return a PBS error code
 *      and print a message on standard error.  A zero-length resource list
 *      is not an error.
 *
 *      If set_mode is SET_LIMIT_SET the entry conditions are:
 *          1.  MOM has already forked, and we are called from the child.
 *          2.  The child is still running as root.
 *          3.  Standard error is open to the user's file.
 *
 *      If set_mode is SET_LIMIT_ALTER, we are beening called to modify
 *      existing limits.  Cannot alter those set by setrlimit (kernel)
 *      because we are the wrong process.
 *
 * @return      int
 * @retval      PBSE_NONE       Success
 * @retval      PBSE_*          Error
 *
 */
int
mom_set_limits(job *pjob, int set_mode)
{
	char		*pname;
	int		retval;
	rlim64_t	sizeval; /* place to build 64 bit value */
	unsigned long	value;	/* place in which to build resource value */
	resource	*pres;
	struct rlimit64	res64lim;
	rlim64_t	mem_limit  = 0;
	rlim64_t	vmem_limit = 0;
	rlim64_t	cpu_limit = 0;
	struct rlimit 	curr_lim;

	DBPRT(("%s: entered\n", __func__))
	assert(pjob != NULL);
	assert(pjob->ji_wattr[(int)JOB_ATR_resource].at_type == ATR_TYPE_RESC);
	pres = (resource *)
		GET_NEXT(pjob->ji_wattr[(int)JOB_ATR_resource].at_val.at_list);

	/*
	 * Cycle through all the resource specifications,
	 * setting limits appropriately.
	 */

	/* mem and vmem limits come from the local node limits, not the job */
	mem_limit  = pjob->ji_hosts[pjob->ji_nodeid].hn_nrlimit.rl_mem << 10;
	vmem_limit = pjob->ji_hosts[pjob->ji_nodeid].hn_nrlimit.rl_vmem << 10;

	while (pres != NULL) {
		assert(pres->rs_defin != NULL);
		pname = pres->rs_defin->rs_name;
		assert(pname != NULL);
		assert(*pname != '\0');

		if (strcmp(pname, "ncpus") == 0) {
			retval = getlong(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if (value == 0) {
				/* applies to SGI only - make weightless */
				schedctl(NDPRI, 0, NDPLOMAX);
			}
		} else if (strcmp(pname, "cput") == 0) {
			retval = local_gettime(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((cpu_limit == 0) || (value < cpu_limit))
				cpu_limit = value;
			if (_MIPS_SYMBOL_PRESENT(setjlimit)) {
				getjlimit(0, JLIMIT_CPU, &curr_lim);
				curr_lim.rlim_max = MIN(curr_lim.rlim_max, (rlim_t)((double)value / cputfactor));
				curr_lim.rlim_cur = curr_lim.rlim_max;
				setjlimit(0, JLIMIT_CPU, &curr_lim);
			}
		} else if  (strcmp(pname, "pcput") == 0) {	/* set */
			retval = local_gettime(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((cpu_limit == 0) || (value < cpu_limit))
				cpu_limit = value;
		} else if (strcmp(pname, "vmem") == 0) {
			retval = local_getsize(pres, &sizeval);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((vmem_limit == 0) || (sizeval < vmem_limit))
				vmem_limit = sizeval;
			if (_MIPS_SYMBOL_PRESENT(setjlimit)) {
				getjlimit(0, JLIMIT_VMEM, &curr_lim);
				curr_lim.rlim_max=MIN(curr_lim.rlim_max, vmem_limit);
				curr_lim.rlim_cur = curr_lim.rlim_max;
				setjlimit(0, JLIMIT_VMEM, &curr_lim);
			}
		} else if (strcmp(pname, "pvmem") == 0) {	/* set */
			retval = local_getsize(pres, &sizeval);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((vmem_limit == 0) || (sizeval < vmem_limit))
				vmem_limit = sizeval;

		} else if (strcmp(pname, "mem") == 0 ||
			strcmp(pname, "pmem") == 0) {	/* set */
			retval = local_getsize(pres, &sizeval);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((mem_limit == 0) || (sizeval < mem_limit))
				mem_limit = sizeval;
		} else if (strcmp(pname, "file") == 0) {	/* set */
			if (set_mode == SET_LIMIT_SET) {
				retval = local_getsize(pres, &sizeval);
				if (retval != PBSE_NONE)
					return (error(pname, retval));
				res64lim.rlim_cur = res64lim.rlim_max = sizeval;
				if (setrlimit64(RLIMIT_FSIZE, &res64lim) < 0)
					return (error(pname, PBSE_SYSTEM));
			}
		} else if (strcmp(pname, "walltime") == 0) {	/* Check */
			retval = getlong(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
		} else if (strcmp(pname, "nice") == 0) {	/* set nice */
			if (set_mode == SET_LIMIT_SET) {
				errno = 0;
				if ((nice((int)pres->rs_value.at_val.at_long) == -1)
					&& (errno != 0))
					return (error(pname, PBSE_BADATVAL));
			}
#if	NODEMASK != 0
		} else if (strcmp(pname, "nodemask") == 0) {  /* set nodemask */

			Bitfield nodemask_set;
			Bitfield nodemask_get;
			int rc;

			/* convert nodemask string to actual bits */
			rc = nodemask_str2bits(pres->rs_value.at_val.at_str,
				&nodemask_set);
			if (rc) {
				sprintf(log_buffer, "Malformed nodemask %s [%d]",
					pres->rs_value.at_val.at_str, rc);
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
					LOG_NOTICE,
					pjob->ji_qs.ji_jobid,
					log_buffer);
				continue;
			}

			/* try to jam it through to the kernel */
			rc = pmoctl(PMO_SETNODEMASK_UINT64, &nodemask_set,
				sizeof(Bitfield));
			if (rc) {
				sprintf(log_buffer,
					"Attempt to set nodemask to %s failed [%d]",
					pres->rs_value.at_val.at_str, rc);
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
					LOG_NOTICE,
					pjob->ji_qs.ji_jobid, log_buffer);
				continue;
			}

			/*===================================================*/
			/* OK, that probably worked -- so what follows       */
			/* qualifies as "overkill". Hence, it may be removed,*/
			/* if that seems like The Right Thing To Do(tm) [for */
			/* efficiency ??]                                    */
			/*===================================================*/
			rc = pmoctl(PMO_GETNODEMASK_UINT64, &nodemask_get,
				sizeof(Bitfield));
			if (rc) {
				sprintf(log_buffer,
					"Can't retrieve nodemask [%d]", rc);
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
					LOG_NOTICE,
					pjob->ji_qs.ji_jobid, log_buffer);
				continue;
			}

			if (BITFIELD_NOTEQ(&nodemask_set, &nodemask_get)) {
				sprintf(log_buffer,
					"Tried to set nodemask %s, got %s",
					pres->rs_value.at_val.at_str,
					nodemask_bits2str(&nodemask_get));
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
					LOG_NOTICE,
					pjob->ji_qs.ji_jobid, log_buffer);
			}

#endif	/* NODEMASK */
		}
		pres = (resource *)GET_NEXT(pres->rs_link);
	}

	if (set_mode == SET_LIMIT_SET) {

		if (setrlimit64(RLIMIT_STACK, &orig_stack_size) < 0)
			return (error("RLIMIT_STACK", PBSE_SYSTEM));

		/* if either mem or pmem was given, set sys limit to lesser */
		if (mem_limit != 0) {
			res64lim.rlim_cur = res64lim.rlim_max = mem_limit;
			if (setrlimit64(RLIMIT_RSS, &res64lim) < 0)
				return (error("RLIMIT_RSS", PBSE_SYSTEM));
		}

		/* if either cput or pcput was given, set process limit to lesser */
		if (cpu_limit != 0) {
			res64lim.rlim_cur = res64lim.rlim_max =
				(rlim64_t)((double)cpu_limit / cputfactor);
			if (setrlimit64(RLIMIT_CPU, &res64lim) < 0)
				return (error("RLIMIT_CPU", PBSE_SYSTEM));
		}

		/* if either of vmem or pvmem was given, set sys limit to lesser */
		if (vmem_limit != 0) {
			res64lim.rlim_cur = res64lim.rlim_max= vmem_limit;
			if (setrlimit64(RLIMIT_VMEM, &res64lim) < 0)
				return (error("RLIMIT_VMEM", PBSE_SYSTEM));
		}
	}
	return (PBSE_NONE);
}

/**
 * @brief
 *      State whether MOM main loop has to poll this job to determine if some
 *      limits are being exceeded.
 *
 * @param[in] pjob - job pointer
 *
 * @return      int
 * @retval      TRUE    if polling is necessary
 * @retval      FALSE   otherwise. 
 *
 * NOTE: Actual polling is done using the mom_over_limit machine-dependent function.
 *
 */
int
mom_do_poll(job *pjob)
{
	char		*pname;
	resource	*pres;

	DBPRT(("%s: entered\n", __func__))
	assert(pjob != NULL);
	assert(pjob->ji_wattr[(int)JOB_ATR_resource].at_type == ATR_TYPE_RESC);
	pres = (resource *)
		GET_NEXT(pjob->ji_wattr[(int)JOB_ATR_resource].at_val.at_list);

	while (pres != NULL) {
		assert(pres->rs_defin != NULL);
		pname = pres->rs_defin->rs_name;
		assert(pname != NULL);
		assert(*pname != '\0');

		if (strcmp(pname, "walltime") == 0 ||
			strcmp(pname, "ncpus") == 0 ||
			strcmp(pname, "cput") == 0 ||
			strcmp(pname, "mem")  == 0 ||
			strcmp(pname, "vmem") == 0)
			return (TRUE);
		pres = (resource *)GET_NEXT(pres->rs_link);
	}

	return (FALSE);
}

/**
 * @brief
 * 	Setup for polling.
 *
 *	Open kernel device and get namelist info.
 *	Also open sgi project files.
 *
 * @return	int
 * @retval	0		Success
 * @retval	PBSE_SYSTEM	error
 */
int
mom_open_poll()
{
	DBPRT(("%s: entered\n", __func__))
	pagesize = getpagesize();

	proc_array = (struct proc_info *)calloc(TBL_INC,
		sizeof(struct proc_info));
	if (proc_array == NULL) {
		log_err(errno, __func__, "malloc");
		return (PBSE_SYSTEM);
	}
	max_proc = TBL_INC;

	return (0);
}

/**
 * @brief
 *      Declare start of polling loop.
 *
 * @return      int
 * @retval      PBSE_INTERNAL   Dir pdir in NULL
 * @retval      PBSE_NONE       Success
 *
 */
int
mom_get_sample(void)
{
	int			fd;
	struct dirent		*dent;
	char			procname[100];
	int			num;
	int			mapsize;
	prmap_sgi_arg_t		maparg;
	prmap_sgi_t		map[MAPNUM];
	struct	proc_info	*pi;
	extern time_t time_last_sample;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))
	if (pdir == NULL)
		return PBSE_INTERNAL;

	rewinddir(pdir);
	nproc = 0;
	pi = proc_array;

	if (complex_mem_calc) {
		mapsize = sizeof(prmap_sgi_t) * MAPNUM;
		maparg.pr_size = mapsize;
	}

	time_last_sample = time(0);
	sampletime_floor = time_last_sample;
	for (fd = -1; (dent = readdir(pdir)) != NULL; close(fd)) {
		if (!isdigit(dent->d_name[0]))
			continue;

		sprintf(procname, procfmts, dent->d_name);
		if ((fd = open(procname, O_RDONLY)) == -1)
			continue;

		if (ioctl(fd, PIOCPSINFO, &pi->info) == -1) {
			if (errno != ENOENT) {
				sprintf(log_buffer,
					"%s: ioctl(PIOCPSINFO)", procname);
				log_err(errno, __func__, log_buffer);
			}
			continue;
		}

		if (complex_mem_calc) {
			if (pi->map) {
				free(pi->map);		/* free any old space */
				pi->map = NULL;
			}
			pi->map_num = 0;
			maparg.pr_vaddr = (caddr_t)map;

			if ((num = ioctl(fd, PIOCMAP_SGI, &maparg)) == -1) {
				if (errno != ENOENT)
					log_err(errno, __func__, "ioctl(PIOCMAP_SGI)");
				continue;
			}
			if (num > 0) {
				size_t	nb = sizeof(prmap_sgi_t) * num;

				assert(num < MAPNUM);
				pi->map = (prmap_sgi_t *) malloc(nb);
				if (pi->map == NULL)
					return PBSE_SYSTEM;
				memcpy(pi->map, map, nb);
				pi->map_num = num;
			}
		}

		if (++nproc == max_proc) {
			struct	proc_info	*hold;

			DBPRT(("%s: alloc more table space %d\n", __func__, nproc))
			max_proc *= 2;

			hold = (struct proc_info *)realloc(proc_array,
				max_proc*sizeof(struct proc_info));
			assert(hold != NULL);
			proc_array = hold;
			memset(&proc_array[nproc], '\0',
				sizeof(struct proc_info) * (max_proc >> 1));
		}
		pi = &proc_array[nproc];
	}
	sampletime = time(0);

	if ((sampletime - time_last_sample) > 5) {
		sprintf(log_buffer, "time lag %ld secs", (long)(sampletime-time_last_sample));
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_WARNING,
			__func__, log_buffer);
		return PBSE_SYSTEM;
	}
	sampletime_ceil = time(0);
	return (PBSE_NONE);
}

/**
 * @brief
 *      Update the job attribute for resources used.
 *
 *      The first time this is called for a job, set up resource entries for
 *      each resource that can be reported for this machine.  Fill in the
 *      correct values.  Return an error code.
 *
 *      Assumes that the session ID attribute has already been set.
 *
 * @param[in] pjob - pointer to job structure
 *
 * @return int
 * @retval PBSE_NONE    for success.
 */
int 
mom_set_use(job *pjob)
{
	resource		*pres;
	attribute		*at;
	resource_def		*rd;
	u_Long 			*lp_sz, lnum_sz;
	unsigned long		*lp, lnum, oldcput;
	long			 dur;
	resource    *pres_req;
	attribute   *at_req;
	long                     ncpus_req;



	assert(pjob != NULL);
	at = &pjob->ji_wattr[(int)JOB_ATR_resc_used];
	assert(at->at_type == ATR_TYPE_RESC);

	if ((pjob->ji_qs.ji_svrflags & JOB_SVFLG_Suspend) != 0)
		return (PBSE_NONE);	/* job suspended, don't track it */

	DBPRT(("%s: entered %s\n", __func__, pjob->ji_qs.ji_jobid))

	at->at_flags |= ATR_VFLAG_MODIFY;
	if ((at->at_flags & ATR_VFLAG_SET) == 0) {
		at->at_flags |= ATR_VFLAG_SET;

		/* Alexis Cousein - copy atribute "ncpus" from requested resources list into
		 used resources list
		 */
		rd = find_resc_def(svr_resc_def, "ncpus", svr_resc_size);
		assert(rd != NULL);
		pres = add_resource_entry(at, rd);
		pres->rs_value.at_flags |= ATR_VFLAG_SET;
		pres->rs_value.at_type = ATR_TYPE_LONG;

		/* get pointer to list of resources *requested* for the job to get ncpus */
		at_req = &pjob->ji_wattr[(int)JOB_ATR_resource];
		assert(at->at_type == ATR_TYPE_RESC);

		pres_req = find_resc_entry(at_req, rd);
		if (pres_req!=NULL && (ncpus_req=pres_req->rs_value.at_val.at_long)!=0)
			pres->rs_value.at_val.at_long = ncpus_req;
		else
			pres->rs_value.at_val.at_long = 0;


		rd = find_resc_def(svr_resc_def, "cput", svr_resc_size);
		assert(rd != NULL);
		pres = add_resource_entry(at, rd);
		pres->rs_value.at_flags |= ATR_VFLAG_SET;
		pres->rs_value.at_type = ATR_TYPE_LONG;
		pres->rs_value.at_val.at_long = 0;

		rd = find_resc_def(svr_resc_def, "cpupercent", svr_resc_size);
		assert(rd != NULL);
		pres = add_resource_entry(at, rd);
		pres->rs_value.at_flags |= ATR_VFLAG_SET;
		pres->rs_value.at_type = ATR_TYPE_LONG;
		pres->rs_value.at_val.at_long = 0;

		rd = find_resc_def(svr_resc_def, "vmem", svr_resc_size);
		assert(rd != NULL);
		pres = add_resource_entry(at, rd);
		pres->rs_value.at_flags |= ATR_VFLAG_SET;
		pres->rs_value.at_type = ATR_TYPE_SIZE;
		pres->rs_value.at_val.at_size.atsv_shift = 10; /* in KB */
		pres->rs_value.at_val.at_size.atsv_units = ATR_SV_BYTESZ;

		rd = find_resc_def(svr_resc_def, "walltime", svr_resc_size);
		assert(rd != NULL);
		pres = add_resource_entry(at, rd);
		pres->rs_value.at_flags |= ATR_VFLAG_SET;
		pres->rs_value.at_type = ATR_TYPE_LONG;

		rd = find_resc_def(svr_resc_def, "mem", svr_resc_size);
		assert(rd != NULL);
		pres = add_resource_entry(at, rd);
		pres->rs_value.at_flags |= ATR_VFLAG_SET;
		pres->rs_value.at_type = ATR_TYPE_SIZE;
		pres->rs_value.at_val.at_size.atsv_shift = 10; /* in KB */
		pres->rs_value.at_val.at_size.atsv_units = ATR_SV_BYTESZ;
	}

	rd = find_resc_def(svr_resc_def, "cput", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	lp = (unsigned long *)&pres->rs_value.at_val.at_long;
	oldcput = *lp;
	lnum = cput_sum(pjob);
	lnum = MAX(*lp, lnum);
	*lp = lnum;

	/* now calculate weight moving average cpu usage percentage */

	if ((dur = sampletime_ceil+1 - pjob->ji_sampletim) >
		PBS_MIN_CPUPERCENT_PERIOD) {
		calc_cpupercent(pjob, oldcput, lnum, dur, at);
	}
	pjob->ji_sampletim = sampletime_floor;

	rd = find_resc_def(svr_resc_def, "vmem", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	lp_sz = &pres->rs_value.at_val.at_size.atsv_num;
	lnum_sz = (mem_sum(pjob) + 1023) >> 10;	/* as KB */
	*lp_sz = MAX(*lp_sz, lnum_sz);

	rd = find_resc_def(svr_resc_def, "walltime", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	pres->rs_value.at_val.at_long = (long)((double)(time_now -
		pjob->ji_qs.ji_stime) * wallfactor);

	rd = find_resc_def(svr_resc_def, "mem", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	lp_sz = &pres->rs_value.at_val.at_size.atsv_num;
	lnum_sz = ((*presi_sum)(pjob) + 1023) >> 10;	/* in KB */
	*lp_sz = MAX(*lp_sz, lnum_sz);

	return (PBSE_NONE);
}

/**
 * @brief
 *      bld_ptree - establish links (parent, child, and sibling) for processes
 *      in a given session.     
 *      
 *      The PBS_PROC_* macros are defined in resmom/.../mom_mach.h
 *      to refer to the correct machine dependent table.
 *              
 * @param[in] sid - session id
 *
 * @return      int
 * @retval      number of processes in session  Success
 *       
 */      
int
bld_ptree(pid_t sid)
{
	int	myproc_ct;	/* count of processes in a session */
	int	i, j;

	if (Proc_lnks == NULL) {
		Proc_lnks = (pbs_plinks *)malloc(TBL_INC * sizeof(pbs_plinks));
		assert(Proc_lnks != NULL);
		myproc_max = TBL_INC;
	}

	/*
	 * Build links for processes in the session in question.
	 * First, load with the processes in the session.
	 */

	myproc_ct = 0;
	for (i = 0; i < nproc; i++) {
		if (PBS_PROC_PID(i) <= 1)
			continue;
		if ((int)PBS_PROC_SID(i) == sid) {
			Proc_lnks[myproc_ct].pl_pid    = PBS_PROC_PID(i);
			Proc_lnks[myproc_ct].pl_ppid   = PBS_PROC_PPID(i);
			Proc_lnks[myproc_ct].pl_parent = -1;
			Proc_lnks[myproc_ct].pl_sib    = -1;
			Proc_lnks[myproc_ct].pl_child  = -1;
			Proc_lnks[myproc_ct].pl_done   = 0;
			if (++myproc_ct == myproc_max) {
				void * hold;

				myproc_max += TBL_INC;
				hold = realloc((void *)Proc_lnks,
					myproc_max*sizeof(pbs_plinks));
				assert(hold != NULL);
				Proc_lnks = (pbs_plinks *)hold;
			}
		}
	}

	/* Now build the tree for those processes */

	for (i = 0; i < myproc_ct; i++) {
		/*
		 * Find all the children for this process, establish links.
		 */
		for (j = 0; j < myproc_ct; j++) {
			if (j == i)
				continue;
			if (Proc_lnks[j].pl_ppid == Proc_lnks[i].pl_pid) {
				Proc_lnks[j].pl_parent = i;
				Proc_lnks[j].pl_sib = Proc_lnks[i].pl_child;
				Proc_lnks[i].pl_child = j;
			}
		}
	}
	return (myproc_ct);	/* number of processes in session */
}

/**
 * @brief
 *      kill_ptree - traverse the process tree, killing the processes as we go
 *
 * @param[in]   idx:    current pid index
 * @param[in]   flag:   traverse order, top down (1) or bottom up (0)
 * @param[in]   sig:    the signal to send
 *
 * @return      Void
 *
 */
static void
kill_ptree(int idx, int flag, int sig)
{
	int		 child;

	if (flag && !Proc_lnks[idx].pl_done) {		/* top down */
		(void)kill(Proc_lnks[idx].pl_pid, sig);
		Proc_lnks[idx].pl_done = 1;
	}
	child = Proc_lnks[idx].pl_child;
	while (child != -1) {
		kill_ptree(child, flag, sig);
		child = Proc_lnks[child].pl_sib;
	}
	if (!flag && !Proc_lnks[idx].pl_done) {		/* bottom up */
		(void)kill(Proc_lnks[idx].pl_pid, sig);
		Proc_lnks[idx].pl_done = 1;
	}
}

/**
 * @brief
 *      kill task session
 *
 * @param[in] ptask - pointer to pbs_task structure
 * @param[in] sig - signal number
 * @param[in] dir - indication how to kill
 *                  0 - kill child first
 *                  1 - kill parent first
 *
 * @return      int
 * @retval      number of tasks
 *
 */
int
kill_task(pbs_task *ptask, int sig, int dir)
{
	return kill_session(ptask->ti_qs.ti_sid, sig, dir);
}

/**
 * @brief
 *      Kill a task session.
 *      Call with the task pointer and a signal number.
 *      
 * @param[in] sesid - session id
 * @param[in] sig - signal number
 * @param[in] dir - indication how to kill
 *                  0 - kill child first
 *                  1 - kill parent first
 *
 * @return      int
 * @retval      number of tasks
 *
 */
int
kill_session(pid_t sesid, int sig, int dir)
{
	int		ct = 0;
	int		i;

	DBPRT(("%s: entered sid %d\n", __func__, sesid))
	if (sesid <= 1)
		return 0;

	(void)mom_get_sample();
	ct = bld_ptree(sesid);
	DBPRT(("%s: bld_ptree %d\n", __func__, ct))

	/*
	 ** Find index into the Proc_lnks table for the session lead.
	 */
	for (i = 0; i < ct; i++) {
		if (Proc_lnks[i].pl_pid == sesid) {
			kill_ptree(i, dir, sig);
			break;
		}
	}
	/*
	 ** Do a linear pass.
	 */
	for (i = 0; i < ct; i++) {
		if (Proc_lnks[i].pl_done)
			continue;
		DBPRT(("%s: cleanup %d\n", __func__, Proc_lnks[i].pl_pid))
		kill(Proc_lnks[i].pl_pid, sig);
	}

	return ct;
}

/**
 * @brief
 *      Clean up everything related to polling.
 *
 * @return      int
 * @retval      PBSE_NONE       Success
 * @retval      PBSE_SYSTEM     Error
 *
 */
int
mom_close_poll(void)
{
	DBPRT(("%s: entered\n", __func__))
	if (proc_array) {
		if (complex_mem_calc) {
			int	i;

			for (i=0; i<max_proc; i++) {
				struct	proc_info	*pi = &proc_array[i];

				if (pi->map)
					free(pi->map);
			}
		}
		free(proc_array);
	}
	if (pdir) {
		if (closedir(pdir) != 0) {
			log_err(errno, __func__, "closedir");
			return (PBSE_SYSTEM);
		}
		pdir = NULL;
	}

	return (PBSE_NONE);
}

/**
 * @brief
 *      Checkpoint the job.
 *
 * @param[in] ptask - pointer to task
 * @param[in] file - filename
 * @param[in] abort - value indicating abort
 *
 * If abort is true, kill it too.
 *
 * @return      int
 * @retval      -1	error
 * @retval	0	success
 */
int
mach_checkpoint(task *ptask, char *file, int abort)
{
#if MOM_CHECKPOINT == 1
	struct	stat	sbuf;

	/* ckpt_setup(0, 0);  Does nothing so why have it */

	if (abort)
		cpr_flags = CKPT_CHECKPOINT_KILL | cpr_master_flag;
	else
		cpr_flags = CKPT_CHECKPOINT_CONT | cpr_master_flag;

	/* if no sid is set, no point in going on */
	if (ptask->ti_qs.ti_sid <= 1) {
		sprintf(log_buffer, "No sid for task %8.8X",
			ptask->ti_qs.ti_task);
		log_err(-1, __func__, log_buffer);
		return 0;
	}	/* no need to checkpoint if file exists and sid is gone */
	else if (kill(ptask->ti_qs.ti_sid, 0) != 0 && errno == ESRCH &&
		stat(file, &sbuf) == 0) {
		sprintf(log_buffer, "task %8.8X sid=%d does not exist and "
			"checkpoint file %s exists",
			ptask->ti_qs.ti_task, ptask->ti_qs.ti_sid, file);
		log_err(-1, __func__, log_buffer);
		return 0;
	}

	return (ckpt_create(file, ptask->ti_qs.ti_sid, P_SID, 0, 0));
#else /* MOM_CHECKPOINT */
	return (-1);
#endif /* MOM_CHECKPOINT */
}

/**
 * @brief
 *      Restart the job from the checkpoint file.
 *
 * @param[in] ptask - pointer to task
 * @param[in] file - filename
 *
 * @return      long
 * @retval      session id      Success
 * @retval      -1              Error
 */
long
mach_restart(task *ptask, char *file)
{
#if MOM_CHECKPOINT == 1
	char irix_release[SYS_NMLN];
	char *irix_overlay;
	int new_cpr_behaviour=0;
	job *pjob2;
	jid_t sgijid;
	int   rv;
	ckpt_id_t rc;
	pid_t    kid;
	int      c2pfd[2], rfd, wfd, i;
	struct rst_rtn {
		ckpt_id_t       ckptid;
		int             errno;
	} rst_rtn;

	cpr_flags = cpr_master_flag;

	/*
	 * ckpt_restart() does its own fork() and sets up the restarted job's
	 * processes.  But because this procedure may end up modifing the
	 * current process' JID and ASH to match with those of "previous"
	 * processes (for IRIX >= 6.5.16), this all needs to happen in a
	 * subprocess to preserve main MOM's JID and ASH info.
	 *
	 * Set up a pipe, then fork.  The child will do the restart.
	 * The child then passes the ckpt_id_t to the parent on the pipe, and
	 * exits.
	 */
	if (pipe(c2pfd) == -1) {
		log_err(errno, __func__, "cannot open pipe");
		return -1;
	}
	rfd = c2pfd[0];		/* The read end of the pipe. */
	wfd = c2pfd[1];		/* The write end of the pipe. */

	(void)memset((void *)&rst_rtn, 0, sizeof(struct rst_rtn));

	if ((kid = fork()) < 0) {
		(void)sprintf(log_buffer, "cannot fork() to restart child");
		log_err(errno,  __func__, log_buffer);

		return -1;
	}

	if (kid == 0) {		/* CHILD CHILD CHILD CHILD CHILD CHILD CHILD */
#ifdef	SGI_SETPSARGS
		/*
		 * Change the psargs field of this process to a more useful
		 * string.  This is a custom modification which is only
		 * cosmetic.  Ignore any error or result codes.
		 */
		(void)sprintf(log_buffer, "%s restart helper",
			ptask->ti_job->ji_qs.ji_jobid);
		(void)syssgi(SGI_SETPSARGS, log_buffer, strlen(log_buffer));
#endif  /* SGI_SETPSARGS */

		rpp_terminate();
		(void)close(rfd);	/* Won't be reading from parent. */


		/* find out if it's CPR or PBSPro that should restore JID and ASH */

		strcpy(irix_release, "0.0.0");
		syssgi(SGI_RELEASE_NAME, sizeof(irix_release), irix_release);
		if (atoi(irix_release) > 6)
			new_cpr_behaviour=1;
		else if (atoi(irix_release)==6) {
			irix_overlay=strchr(irix_release,'.');
			if (irix_overlay) irix_overlay++;
			if (atoi(irix_overlay)>5)
				new_cpr_behaviour=1;
			else if (atoi(irix_overlay)==5) {
				irix_overlay=strchr(irix_overlay,'.');
				if (irix_overlay) irix_overlay++;
				if (atoi(irix_overlay)>15)
					new_cpr_behaviour=1;
			}
		}

		if (new_cpr_behaviour) {

			/*
			 restores JID and ASH
			 necessary because 6.5.16 makes CPR inherit JID and ASH
			 don't bail out in case of errors -- just let restart
			 processes inherit whatever PBS daemons are running
			 under and hope for the best -- but log strangeness...
			 */

			pjob2 = ptask->ti_job;
			if (pjob2->ji_extended.ji_ext.ji_jid > 0) {
				/*
				 * already have a job id - from Mother Superior
				 * join it or create one with that id
				 */

				if (_MIPS_SYMBOL_PRESENT(getjid) && \
					_MIPS_SYMBOL_PRESENT(makenewjob)) {
					/* we are on a system that knows about job limits */


					if ((getjid() != pjob2->ji_extended.ji_ext.ji_jid) \
				&& (syssgi(SGI_JOINJOB,
						pjob2->ji_extended.ji_ext.ji_jid)!=0)) {
						/* attempt to join job failed */
						if (errno == ENOPKG) {
							log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
								LOG_INFO, pjob2->ji_qs.ji_jobid,
								"job limits ENOPKG");
						} else {
							/* have to use makenewjob() to force jid */
							sgijid = \
				   makenewjob(pjob2->ji_extended.ji_ext.ji_jid,
								pjob2->ji_qs.ji_un.ji_momt.ji_exuid);
							if (sgijid != pjob2->ji_extended.ji_ext.ji_jid) {
								/* bad news */
								(void)sprintf(log_buffer,
									"join job limits failed: %d",
									errno);
								log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
									LOG_INFO, pjob2->ji_qs.ji_jobid,
									log_buffer);
							}
						}
					}
				}       /* joined exiting job ok */
			}

			if ((pjob2->ji_extended.ji_ext.ji_ash != 0) &&
				(getash() != pjob2->ji_extended.ji_ext.ji_ash)) {
				rv = syssgi(SGI_JOINARRAYSESS, 0,
					&pjob2->ji_extended.ji_ext.ji_ash);

			}
			if (rv < 0) {
				/* join failed/no session - create new array session */
				if (newarraysess() == -1) {
					(void)sprintf(log_buffer,
						"newarraysess failed, err=%d", errno);
					log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
						LOG_INFO,
						pjob2->ji_qs.ji_jobid,
						log_buffer);
				}
			}

			if ((pjob2->ji_extended.ji_ext.ji_ash != 0) &&
				(getash() != pjob2->ji_extended.ji_ext.ji_ash)) {
				/* may not have arrayd running here */
				/* try to force ashhas to work as we tried to join
				 first */
				if (setash(pjob2->ji_extended.ji_ext.ji_ash) < 0) {
					sprintf(log_buffer, "setash failed to %lld, err %d",
						pjob2->ji_extended.ji_ext.ji_ash, errno);
					log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
						LOG_INFO,
						pjob2->ji_qs.ji_jobid,
						log_buffer);
					/* don't bail out -- could happen if no arrayd is
					 running */
				}
			}
		}

		/* Now, running with same JID, ASH restart checkpoint. */
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
			LOG_INFO,
			ptask->ti_job->ji_qs.ji_jobid,
			"calling ckpt_restart");

		/* KLUDGE to work-around SGI problem, for some reason */
		/* ckpt_restart()  passes open file descriptor to /proc to */
		/* restarted process	     */
		if (pdir)
			closedir(pdir);

		rst_rtn.ckptid =  ckpt_restart(file, (struct ckpt_args **)0, 0);

		/* KLUDGE TO work-around SGI problem, ckpt_restart sets the */
		/* uid of the calling process (me) to that of the restarted */
		/* process       */
		if (setuid(0) == -1) {
			log_err(errno, __func__, "couldn't set uid back to root");
			(void)close(wfd);
			exit(1);
		}

		if (rst_rtn.ckptid == -1)
			rst_rtn.errno  = errno;
		else
			rst_rtn.errno = 0;

		/* And hand the ckpt_id_t back up to the parent. */
		if (write(wfd, &rst_rtn, sizeof(rst_rtn)) != sizeof(rst_rtn)) {
			log_err(errno, __func__, "couldn't pass back data to mom");
			(void)close(wfd);
			exit(1);
		}

		/* Close the pipe and we're done. */
		(void)close(wfd);

		if (!rst_rtn.errno)
			(void)sprintf(log_buffer,
				"restart helper exiting (ckpt %lld)", rst_rtn.ckptid);
		else
			(void)sprintf(log_buffer,
				"restart helper exiting: ckpt %lld, errno %d",
				rst_rtn.ckptid, rst_rtn.errno);
		log_err(-1, __func__, log_buffer);

		exit(0);

		/* NOTREACHED */

	} else {		/* PARENT PARENT PARENT PARENT PARENT PARENT */
		(void)close(wfd);	/* Won't be writing to child. */

		/* In the parent.
		 *
		 * Wait for the child to send up the restart information.
		 */

		/* Wait for the child to exit. */
		(void)waitpid(kid, &i, 0);

		i = read(rfd, &rst_rtn, sizeof(rst_rtn));

		if (i != sizeof(rst_rtn) || rst_rtn.errno != 0) {
			char    ckpt_dirname[MAXPATHLEN+1];
			char    ckpt_filename[MAXPATHLEN+1];
			char    ckpt_dir_copy[MAXPATHLEN+1];
			char    ckpt_file_copy[MAXPATHLEN+1];
			char    *p;
			struct stat sbuf;

			log_err(errno, __func__,
				"failed to read restart info from helper");

			(void)close(rfd);

			/* Move existing checkpoint file */
			strcpy(ckpt_dirname, ".");
			if (p=strrchr(file, '/')) {
				*p = '\0';
				strcpy(ckpt_dirname, file);
				*p = '/';
				strcpy(ckpt_filename, p+1);
			}

			sprintf(ckpt_dir_copy, "%s.old", ckpt_dirname);

			if (stat(ckpt_dir_copy, &sbuf) != 0) {
				(void)mkdir(ckpt_dir_copy,
					S_IRWXU|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH);
				sprintf(log_buffer, "mkdir %s", ckpt_dir_copy);
				log_err(-1, "mach_restart", log_buffer);
			}

			sprintf(ckpt_file_copy, "%s/%s", ckpt_dir_copy,
				ckpt_filename);
			(void)rename(file, ckpt_file_copy);
			sprintf(log_buffer, "rename(%s, %s)", file,
				ckpt_file_copy);
			log_err(-1, "mach_restart", log_buffer);
			return -1;
		}

		(void)close(rfd);
		(void)sprintf(log_buffer,
			"restart helper returned ckpt %lld", rst_rtn.ckptid);
		log_err(-1, __func__, log_buffer);

		rc = rst_rtn.ckptid;	/* for the code below */
		errno = rst_rtn.errno;
	}

	return ((int)rc);
#else	/* MOM_CHECKPOINT */
	return (-1);
#endif	/* MOM_CHECKPOINT */
}

/**
 * @brief
 *	Return 1 if proc table can be read, 0 otherwise.
 */
int
getprocs()
{
	static	unsigned	int	lastproc = 0;

	if (lastproc == reqnum)         /* don't need new proc table */
		return 1;

	if (mom_get_sample() != PBSE_NONE)
		return 0;

	lastproc = reqnum;
	return 1;
}

#define	dsecs(val) ((double)(val).tv_sec + ((double)(val).tv_nsec * 1.0e-9) )

/**
 * @brief
 *      computes and returns the cpu time process with  pid jobid
 *
 * @param[in] jobid - process id for job
 *
 * @return      string
 * @retval      cputime         Success
 * @retval      NULL            Error
 *
 */
char *
cput_job(pid_t jobid)
{
	int			found = 0;
	int			i;
	double			cputime, addtime;
	prpsinfo_t		*pi;

	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	cputime = 0.0;
	for (i=0; i<nproc; i++) {

		pi = &proc_array[i].info;
		if (jobid != pi->pr_sid)
			continue;

		found = 1;
		addtime = dsecs(pi->pr_time) + dsecs(pi->pr_ctime);

		cputime += addtime;
		DBPRT(("%s: total %.2f pid %d %.2f\n", __func__, cputime,
			pi->pr_pid, addtime))

	}
	if (found) {
		sprintf(ret_string, "%.2f", cputime * cputfactor);
		return ret_string;
	}

	rm_errno = PBSE_RMEXIST;
	return NULL;
}

/**
 * @brief
 *      computes and returns the cpu time process with  pid pid.
 *
 * @param[in] pid - process id
 *
 * @return      string
 * @retval      cputime         Success
 * @retval      NULL            Error
 *
 */
char *
cput_proc(pid_t pid)
{
	double			cputime;
	int			i;
	prpsinfo_t		*pi;

	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	cputime = 0.0;
	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (pid == pi->pr_pid)
			break;
	}
	if (i == nproc) {
		rm_errno = PBSE_RMEXIST;
		return NULL;
	}
	cputime = dsecs(pi->pr_time) + dsecs(pi->pr_ctime);

	sprintf(ret_string, "%.2f", cputime * cputfactor);
	return ret_string;
}

/**
 * @brief
 *      wrapper function for cput_proc and cput_job.
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      cputime         Success
 * @retval      NULL            ERRor
 *
 */
char *
cput(struct rm_attribute *attrib)
{
	int			value;

	if (attrib == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if ((value = atoi(attrib->a_value)) == 0) {
		sprintf(log_buffer, "bad param: %s", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (momgetattr(NULL)) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (strcmp(attrib->a_qualifier, "session") == 0)
		return (cput_job((pid_t)value));
	else if (strcmp(attrib->a_qualifier, "proc") == 0)
		return (cput_proc((pid_t)value));
	else {
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
}

/*
 * mem_job() - return memory in KB used by job as a numerical string
 */

char	*
mem_job(sid)
pid_t	sid;
{
	rm_errno = PBSE_RMUNKNOWN;
	return NULL;
}

/**
 * @brief
 *      computes and returns the memory for process with  pid sid..
 *
 * @param[in] pid - process id
 *
 * @return      string
 * @retval      memsize         Success
 * @retval      NULL            Error
 *
 */
char *
mem_proc(pid_t pid)
{
	prpsinfo_t	*pi;
	int		i;

	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (pid == pi->pr_pid)
			break;
	}
	if (i == nproc) {
		rm_errno = PBSE_RMEXIST;
		return NULL;
	}

	sprintf(ret_string, "%llukb",
		((rlim64_t)pi->pr_size * (rlim64_t)pagesize) >> 10); /* in KB */

	return ret_string;
}

/**
 * @brief
 *      wrapper function for mem_job and mem_proc..
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      memsize         Success
 * @retval      NULL            ERRor
 *
 */
char *
mem(struct rm_attribute *attrib)
{
	int			value;

	if (attrib == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if ((value = atoi(attrib->a_value)) == 0) {
		sprintf(log_buffer, "bad param: %s", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (momgetattr(NULL)) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (strcmp(attrib->a_qualifier, "session") == 0)
		return (mem_job((pid_t)value));
	else if (strcmp(attrib->a_qualifier, "proc") == 0)
		return (mem_proc((pid_t)value));
	else {
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
}

/**
 * @brief
 *	resident set size is unknown resource return error
 *
 * @param[in] jobid - pid for job
 *
 * @return	string
 * @retval	NULL
 */
static char	*
resi_job(pid_t jobid)
{
	rm_errno = PBSE_RMUNKNOWN;
	return NULL;
}

/**
 * @brief
 *      computes and returns resident set size for process
 *
 * @param[in] pid - process id
 *
 * @return      string
 * @retval      resident set size       Success
 * @retval      NULL                    Error
 *
 */
static char *
resi_proc(pid_t pid)
{
	prpsinfo_t	*pi;
	int		i;

	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (pid == pi->pr_pid)
			break;
	}
	if (i == nproc) {
		rm_errno = PBSE_RMEXIST;
		return NULL;
	}

	sprintf(ret_string, "%llukb", ((rlim64_t)pi->pr_rssize * pagesize)>>10);
	return ret_string;
}

/**
 * @brief
 *      wrapper function for mem_job and mem_proc..
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      resident set size       Success
 * @retval      NULL                    ERRor
 *
 */
static char *
resi(struct rm_attribute *attrib)
{
	int			value;

	if (attrib == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if ((value = atoi(attrib->a_value)) == 0) {
		sprintf(log_buffer, "bad param: %s", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (momgetattr(NULL)) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (strcmp(attrib->a_qualifier, "session") == 0)
		return (resi_job((pid_t)value));
	else if (strcmp(attrib->a_qualifier, "proc") == 0)
		return (resi_proc((pid_t)value));
	else {
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
}

/**
 * @brief
 *      returns the number of sessions
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      sessions        Success
 * @retval      NULL            error
 *
 */
char *
sessions(struct rm_attribute *attrib)
{
	int			i, j;
	prpsinfo_t		*pi;
	char			*fmt;
	int			njids = 0;
	pid_t			*jids, *hold;
	static		int	maxjid = 200;
	register	pid_t	jobid;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	if ((jids = (pid_t *)calloc(maxjid, sizeof(pid_t))) == NULL) {
		log_err(errno, __func__, "no memory");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	/*
	 ** Search for members of session
	 */
	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (pi->pr_uid == 0)
			continue;
		if ((jobid = pi->pr_sid) == 0)
			continue;
		DBPRT(("%s[%d]: pid %d sid %d\n",
			__func__, njids, pi->pr_pid, jobid))

		for (j=0; j<njids; j++) {
			if (jids[j] == jobid)
				break;
		}
		if (j == njids) {		/* not found */
			if (njids == maxjid) {	/* need more space */
				maxjid += 100;
				hold = (pid_t *)realloc(jids, maxjid);
				if (hold == NULL) {
					log_err(errno, __func__, "realloc");
					rm_errno = PBSE_RMSYSTEM;
					free(jids);
					return NULL;
				}
				jids = hold;
			}
			jids[njids++] = jobid;	/* add jobid to list */
		}
	}

	fmt = ret_string;
	for (j=0; j<njids; j++) {
		checkret(&fmt, 100);
		sprintf(fmt, " %d", (int)jids[j]);
		fmt += strlen(fmt);
	}
	free(jids);
	return ret_string;
}

/**
 * @brief
 *      wrapper function for sessions().
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      sessions        Success
 * @retval      0               error
 *
 */
char *
nsessions(struct rm_attribute *attrib)
{
	char	*result, *ch;
	int	num = 0;

	if ((result = sessions(attrib)) == NULL)
		return result;

	for (ch=result; *ch; ch++) {
		if (*ch == ' ')		/* count blanks */
			num++;
	}
	sprintf(ret_string, "%d", num);
	return ret_string;
}

/**
 * @brief
 *      returns the number of processes in session
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      process        Success
 * @retval      NULL            error
 *
 */
char *
pids(struct rm_attribute *attrib)
{
	pid_t		jobid;
	prpsinfo_t	*pi;
	int		i;
	char		*fmt;
	int		num_pids;

	if (attrib == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if ((jobid = (pid_t)atoi(attrib->a_value)) == 0) {
		sprintf(log_buffer, "bad param: %s", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (momgetattr(NULL)) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (strcmp(attrib->a_qualifier, "session") != 0) {
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	/*
	 ** Search for members of session
	 */
	fmt = ret_string;
	num_pids = 0;
	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		DBPRT(("%s[%d]: pid: %d sid %d\n",
			__func__, num_pids, pi->pr_pid, pi->pr_sid))
		if (jobid != pi->pr_sid)
			continue;

		sprintf(fmt, "%d ", pi->pr_pid);
		fmt += strlen(fmt);
		num_pids++;
	}
	if (num_pids == 0) {
		rm_errno = PBSE_RMEXIST;
		return NULL;
	}
	return ret_string;
}

/**
 * @brief
 *      returns all the process ids
 *
 * @return      pid_t
 * @retval      pids    Success
 * @retval      NULl    Error
 *
 */
pid_t *
allpids(void)
{
	int			 i;
	prpsinfo_t		*pi;
	static	pid_t		*pids = NULL;

	if (getprocs() == 0)
		return NULL;

	if (pids != NULL)
		free(pids);
	if ((pids = (pid_t *)calloc(nproc+1, sizeof(pid_t))) == NULL) {
		log_err(errno, __func__, "no memory");
		return NULL;
	}

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		pids[i] = pi->pr_pid;	/* add pid to list */
	}
	pids[nproc] = -1;
	return pids;
}

/**
 * @brief
 *      returns the number of users
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      users        Success
 * @retval      NULL            error
 *
 */
char *
nusers(struct rm_attribute *attrib)
{
	int			i, j;
	prpsinfo_t		*pi;
	int			nuids = 0;
	uid_t			*uids, *hold;
	static		int	maxuid = 200;
	register	uid_t	uid;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	if ((uids = (uid_t *)calloc(maxuid, sizeof(uid_t))) == NULL) {
		log_err(errno, __func__, "no memory");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if ((uid = pi->pr_uid) == 0)
			continue;

		DBPRT(("%s[%d]: pid %d uid %d\n",
			__func__, nuids, pi->pr_pid, uid))

		for (j=0; j<nuids; j++) {
			if (uids[j] == uid)
				break;
		}
		if (j == nuids) {		/* not found */
			if (nuids == maxuid) {	/* need more space */
				maxuid += 100;
				hold = (uid_t *)realloc(uids, maxuid);
				if (hold == NULL) {
					log_err(errno, __func__, "realloc");
					rm_errno = PBSE_RMSYSTEM;
					free(uids);
					return NULL;
				}
				uids = hold;
			}
			uids[nuids++] = uid;	/* add uid to list */
		}
	}

	sprintf(ret_string, "%d", nuids);
	free(uids);
	return ret_string;
}

/**
 * @brief
 *       return amount of total memory on system in KB as numeric string
 *    
 * @return      string
 * @retval      total memory            Success
 * @retval      NULl                    Error
 *
 */
static char *
totmem(struct rm_attribute *attrib)
{
	struct	statfs	fsbuf;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (statfs(procfs, &fsbuf, sizeof(struct statfs), 0) == -1) {
		log_err(errno, __func__, "statfs");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}
	sprintf(ret_string, "%llukb",
		((rlim64_t)fsbuf.f_bsize * (rlim64_t)fsbuf.f_blocks) >> 10);
	return ret_string;
}

/**
 * @brief
 * 	availmem() - return amount of available memory in system in KB as string
 *
 * @return      string
 * @retval      avbl memory on system 	                Success
 * @retval      NULL                                    Error
 *
 */

 */
static char	*
availmem(struct rm_attribute *attrib)
{
	struct	statfs	fsbuf;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (statfs(procfs, &fsbuf, sizeof(struct statfs), 0) == -1) {
		log_err(errno, __func__, "statfs");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}
	sprintf(ret_string, "%llukb",
		((rlim64_t)fsbuf.f_bsize * (rlim64_t)fsbuf.f_bfree) >> 10);
	return ret_string;
}

/**
 * @brief
 *      return the number of cpus
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      number of cpus  Success
 * @retval      NULL            Error
 *
 */
static char *
ncpus(struct rm_attribute *attrib)
{
	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	sprintf(ret_string, "%ld", (long)num_acpus);
	return ret_string;
}

/**
 * @brief
 *      returns the total physical memory
 *      
 * @param[in] attrib - pointer to rm_attribute structure
 *      
 * @return      string
 * @retval      tot physical memory     Success
 * @retval      NULL                    Error
 *              
 */             
char *
physmem(struct rm_attribute *attrib)
{
	unsigned int	pmem;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (lseek(kfd, (off_t)kern_addr[KSYM_PHYS], SEEK_SET) == -1) {
		sprintf(log_buffer, "lseek to 0x%llx", kern_addr[KSYM_PHYS]);
		log_err(errno, __func__, log_buffer);
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}
	if (read(kfd, (char *)&pmem, sizeof(pmem)) != sizeof(pmem)) {
		log_err(errno, __func__, "read");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	sprintf(ret_string, "%llukb", ((rlim64_t)pmem*(rlim64_t)pagesize) >> 10);
	return ret_string;
}

/**
 * @brief
 *      returns the size of file system present in machine
 *
 * @param[in] param - attribute value(file system)
 *
 * @return      string
 * @retval      size of file system     Success
 * @retval      NULL                    Error
 *
 */
char *
size_fs(char *param)
{
	struct	statfs	fsbuf;

	if (param[0] != '/') {
		sprintf(log_buffer, "%s: not full path filesystem name: %s",
			__func__, param);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (statfs(param, &fsbuf, sizeof(struct statfs), 0) == -1) {
		log_err(errno, __func__, "statfs");
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	sprintf(ret_string, "%llukb",
		((rlim64_t)fsbuf.f_bsize * (rlim64_t)fsbuf.f_bfree) >> 10);
	return ret_string;
}

/**
 * @brief
 *      get file attribute(size) from param and put them in buffer.
 *
 * @param[in] param - file attributes
 *
 * @return      string
 * @retval      size of file    Success
 * @retval      NULL            Error
 *
 */
char *
size_file(char *param)
{
	struct	stat64   sbuf;

	if (param[0] != '/') {
		sprintf(log_buffer, "%s: not full path filesystem name: %s",
			__func__, param);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (stat64(param, &sbuf) == -1) {
		log_err(errno, __func__, "stat");
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	sprintf(ret_string, "%llukb", (sbuf.st_size+512)>>10);
	return ret_string;
}

/**
 * @brief
 *      wrapper function for size_fs which returns the size of file system
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      size of file system     Success
 * @retval      NULL                    Error
 *
 */
char *
size(struct rm_attribute *attrib)
{
	char	*param;

	if (attrib == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if (momgetattr(NULL)) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	param = attrib->a_value;
	if (strcmp(attrib->a_qualifier, "file") == 0)
		return (size_file(param));
	else if (strcmp(attrib->a_qualifier, "fs") == 0)
		return (size_fs(param));
	else {
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
}

/**
 * @brief
 *      computes and returns walltime for process or session.
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return      string
 * @retval      walltime        Success
 * @retval      NULL            Error
 *
 */
static char *
walltime(struct rm_attribute *attrib)
{
	int			value, job, found = 0;
	int			i;
	time_t			now, start;
	prpsinfo_t		*pi;

	if (attrib == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if ((value = atoi(attrib->a_value)) == 0) {
		sprintf(log_buffer, "bad param: %s", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (momgetattr(NULL)) {
		log_err(-1, __func__, extra_parm);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if (strcmp(attrib->a_qualifier, "proc") == 0)
		job = 0;
	else if (strcmp(attrib->a_qualifier, "session") == 0)
		job = 1;
	else {
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if ((now = time(NULL)) <= 0) {
		log_err(errno, __func__, "time");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}
	if (getprocs() == 0) {
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	start = now;
	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (job) {
			if (value != pi->pr_sid)
				continue;
		}
		else {
			if ((pid_t)value != pi->pr_pid)
				continue;
		}

		found = 1;
		start = MIN(start, pi->pr_start.tv_sec);
	}

	if (found) {
		sprintf(ret_string, "%ld", (long)((double)(now - start) * wallfactor));
		return ret_string;
	}

	rm_errno = PBSE_RMEXIST;
	return NULL;
}

/**
 * @brief
 *      reads load avg from file and returns
 *
 * @param[out] rv - var to hold load avg
 *
 * @return      int
 * @retval      0                       Success
 * @retval      RM_ERR_SYSTEM(15205)    error
 *
 */
int
get_la(double *rv)
{
	int	load;	/* 4 byte data item */

	if (lseek(kfd, (off_t)kern_addr[KSYM_LOAD], SEEK_SET) == -1) {
		sprintf(log_buffer, "lseek to 0x%llx", kern_addr[KSYM_LOAD]);
		log_err(errno, __func__, log_buffer);
		return (rm_errno = PBSE_RMSYSTEM);
	}
	if (read(kfd, (char *)&load, sizeof(load)) != sizeof(load)) {
		log_err(errno, __func__, "read");
		return (rm_errno = PBSE_RMSYSTEM);
	}

	/*
	 ** SGI does not have FSCALE like SUN so the 1024
	 ** divisor was found by experment compairing the result
	 ** of this routine to uptime.
	 */
	*rv = (double)load/1024.0;
	sprintf(ret_string, "%.2f", *rv);
	return 0;
}

/**
 * @brief
 *	computes and returns the gracetime
 *
 * @param[in] secs - time
 *
 * @return	u_long
 * @retval	time in secs	if time limit > 0
 * @retval	0		if time limit < 0
 */
u_long
gracetime(u_long secs)
{
	time_t	now = time((time_t *)NULL);

	if (secs > now)		/* time is in the future */
		return (secs - now);
	else
		return 0;
}

/**
 * @brief
 *	return the disk quota for file depending on the type of file
 *
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return	string
 * @retval	quota val	Success
 * @retval	NULL		error
 *
 */
static char	*
quota(struct  rm_attribute  *attrib)
{
	int			type;
	dev_t			dirdev;
	uid_t			uid;
	struct	stat		sb;
	struct	mntent		*me;
	struct	dqblk		qi;
	FILE			*m;
	struct	passwd		*pw;
	static	char		*type_array[] = {
		"harddata",
		"softdata",
		"currdata",
		"hardfile",
		"softfile",
		"currfile",
		"timedata",
		"timefile",
	};
	enum	type_name {
		harddata,
		softdata,
		currdata,
		hardfile,
		softfile,
		currfile,
		timedata,
		timefile,
		type_end
	};

	if (attrib == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if (strcmp(attrib->a_qualifier, "type")) {
		sprintf(log_buffer, "unknown qualifier %s",
			attrib->a_qualifier);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	for (type=0; type<type_end; type++) {
		if (strcmp(attrib->a_value, type_array[type]) == 0)
			break;
	}
	if (type == type_end) {		/* check to see if command is legal */
		sprintf(log_buffer, "bad param: %s=%s",
			attrib->a_qualifier, attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}

	if ((attrib = momgetattr(NULL)) == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if (strcmp(attrib->a_qualifier, "dir") != 0) {
		sprintf(log_buffer, "bad param: %s=%s",
			attrib->a_qualifier, attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (attrib->a_value[0] != '/') {	/* must be absolute path */
		sprintf(log_buffer,
			"not an absolute path: %s", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if (stat(attrib->a_value, &sb) == -1) {
		sprintf(log_buffer, "stat: %s", attrib->a_value);
		log_err(errno, __func__, log_buffer);
		rm_errno = PBSE_RMEXIST;
		return NULL;
	}
	dirdev = sb.st_dev;
	DBPRT(("dir has devnum %d\n", dirdev))

	if ((m = setmntent(MOUNTED, "r")) == NULL) {
		log_err(errno, __func__, "setmntent");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}
	while ((me = getmntent(m)) != NULL) {
		if (strcmp(me->mnt_type, MNTTYPE_IGNORE) == 0)
			continue;
		if (stat(me->mnt_dir, &sb) == -1) {
			sprintf(log_buffer, "stat: %s", me->mnt_dir);
			log_err(errno, __func__, log_buffer);
			continue;
		}
		DBPRT(("%s\t%s\t%d\n", me->mnt_fsname, me->mnt_dir, sb.st_dev))
		if (sb.st_dev == dirdev)
			break;
	}
	endmntent(m);
	if (me == NULL) {
		sprintf(log_buffer,
			"filesystem %s not found", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMEXIST;
		return NULL;
	}
	if (hasmntopt(me, MNTOPT_QUOTA) == NULL) {
		sprintf(log_buffer,
			"no quotas on filesystem %s", me->mnt_dir);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMEXIST;
		return NULL;
	}

	if ((attrib = momgetattr(NULL)) == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = PBSE_RMNOPARAM;
		return NULL;
	}
	if (strcmp(attrib->a_qualifier, "user") != 0) {
		sprintf(log_buffer, "bad param: %s=%s",
			attrib->a_qualifier, attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = PBSE_RMBADPARAM;
		return NULL;
	}
	if ((uid = (uid_t)atoi(attrib->a_value)) == 0) {
		if ((pw = getpwnam(attrib->a_value)) == NULL) {
			sprintf(log_buffer,
				"user not found: %s", attrib->a_value);
			log_err(-1, __func__, log_buffer);
			rm_errno = PBSE_RMEXIST;
			return NULL;
		}
		uid = pw->pw_uid;
	}

	if (quotactl(Q_GETQUOTA, me->mnt_fsname, uid, (caddr_t)&qi) == -1) {
		log_err(errno, __func__, "quotactl");
		rm_errno = PBSE_RMSYSTEM;
		return NULL;
	}

	/* all size values are in KB */
	switch (type) {
		case harddata:
			sprintf(ret_string, "%ukb", BBTOB(qi.dqb_bhardlimit) >> 10);
			break;
		case softdata:
			sprintf(ret_string, "%ukb", BBTOB(qi.dqb_bsoftlimit) >> 10);
			break;
		case currdata:
			sprintf(ret_string, "%ukb", BBTOB(qi.dqb_curblocks) >> 10);
			break;
		case hardfile:
			sprintf(ret_string, "%u", qi.dqb_fhardlimit);
			break;
		case softfile:
			sprintf(ret_string, "%u", qi.dqb_fsoftlimit);
			break;
		case currfile:
			sprintf(ret_string, "%u", qi.dqb_curfiles);
			break;
		case timedata:
			sprintf(ret_string, "%lu", gracetime((u_long)qi.dqb_btimelimit));
			break;
		case timefile:
			sprintf(ret_string, "%lu", gracetime((u_long)qi.dqb_ftimelimit));
			break;
	}

	return ret_string;
}

/**
 * @brief
 *      set priority of processes.
 *
 * @return      Void
 *
 */
void
mom_nice()
{
	if ((nice_val != 0) && (nice(nice_val) == -1)) {
		(void)sprintf(log_buffer, "failed to nice(%d) mom", nice_val);
		log_err(errno, __func__, log_buffer);
	}

}

/**
 * @brief
 *      Unset priority of processes.
 *
 * @return      Void
 *
 */
void
mom_unnice()
{
	if ((nice_val != 0) && (nice(-nice_val) == -1)) {
		(void)sprintf(log_buffer, "failed to nice(%d) mom", nice_val);
		log_err(errno, __func__, log_buffer);
	}
}

#if NODEMASK != 0
/*===================================================================*/
/*                                                                   */
/* utility routines needed by anyone wanting to manipulate nodemasks */
/*                                                                   */
/*===================================================================*/

/**
 * @brief
 *	convert nodemask string to actual bits
 *
 * @param[in] hexmask - node mask string
 * @param[out] nm - pointer to Bitfield structure(bits)
 *
 * @return	int
 * @retval	0	Success
 *
 */
int
nodemask_str2bits(char *hexmask, Bitfield *nm)
{
	static int chunk_size = 2*sizeof(unsigned long long);
	char *p;
	char *endp;
	int len;
	char *copy;
	int i;
	unsigned long long word;


	/* clear out the output nodemask, in case of error */
	BITFIELD_CLRALL(nm);

	/*============================================*/
	/* be rigid -- need enough 'char's to exactly */
	/*    fill a 'Bitfield' or we whine & quit    */
	/*============================================*/
	len = strlen(hexmask);
	if (len % chunk_size)
		return 1;
	if (len/chunk_size != BITFIELD_WORDS)
		return 2;

	/* make a copy that we can munge */
	copy = strdup(hexmask);
	if (copy == NULL)
		return 3;

	p = copy + len;		/* BigEndian -- so go backwards */
	i = 0;
	while (p > copy) {
		p -= chunk_size;		/* start of next chunk */
		word = strtoull(p, &endp, 16);	/* convert it */
		if (*endp) {
			free(copy);
			return 4;	/* found some dreck in the string */
		}
		if (i == BITFIELD_WORDS) {
			free(copy);
			return 5;	/* can't actually happen */
		}
		BITFIELD_SET_WORD(nm, i, word);
		++i;
		*p = '\0';		/* terminate _next_ chunk */
	}

	free(copy);

	return 0;
}

/**
 * @brief
 *      convert actual bits to nodemask string
 *
 * @param[in] nm - pointer to Bitfield structure(bits)
 *
 * @return      string
 * @retval      hexmask	  Success
 *
 */
char *
nodemask_bits2str(Bitfield *nm)
{
	static char hexmask[2*sizeof(Bitfield)+1];	/* WARNING!!! */
	static char width = 2*sizeof(unsigned long long);
	char *p;
	unsigned long long word;
	int ndx;

	p = hexmask;		/* BigEndian, so we go backwards */
	ndx = BITFIELD_WORDS;
	while (ndx) {
		--ndx;
		word = BITFIELD_WORD(nm, ndx);		/* next bunch */
		sprintf(p, "%0*.*llx", width, width, word);	/* string'ize */
		p += strlen(p);
	}

	return hexmask;
}
#endif	/*NODEMASK*/

/**
 * @brief
 *      Get the info required for tm_attach.
 *
 * @param[in] pid - process id
 * @param[in] sid - session id
 * @param[in] uid - user id
 * @param[in] comm - command name
 * @param[in] len - size of command
 *
 * @return      int
 * @retval      TM_OKAY                 Success
 * @retval      TM_ENOPROC(17011)       Error
 *
 */
int
dep_procinfo(pid_t pid, pid_t *sid, uid_t *uid, char *comm, size_t len)
{
	int	i;

	if (getprocs() == 0)
		return TM_ESYSTEM;

	for (i=0; i<nproc; i++) {
		prpsinfo_t	*pi = &proc_array[i].info;

		if (pid == pi->pr_pid) {
			*sid = (pi->pr_sid == 0) ? pi->pr_pid : pi->pr_sid;
			*uid = pi->pr_uid;
			memset(comm, '\0', len);
			memcpy(comm, pi->pr_fname,
				MIN(len-1, sizeof(pi->pr_fname)));
			return TM_OKAY;
		}
	}
	return TM_ENOPROC;
}

/**
 * @brief
 *      No special attach functionality is required.
 *
 * @retturn     int
 * @retval      TM_OKAY
 *
 */
int
dep_attach(task *ptask)
{
	return TM_OKAY;
}


/*
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
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
#if MOM_CHECKPOINT == 1
#include <ckpt.h>
#endif	/* MOM_CHECKPOINT */
#if	NODEMASK != 0
#include <sys/pmo.h>
#include <sys/syssgi.h>
#include <sys/nodemask.h>
#endif	/* NODEMASK */
#include <arraysvcs.h>

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

/*
 **	System dependent code to gather information for the resource
 **	monitor for a Silicon Graphics (SGI) machine.
 **
 **	Resources known by this code:
 **		cput		cpu time for a pid or session
 **		mem		memory size for a pid or session in KB
 **		sessions	list of sessions in the system
 **		pids		list of pids in a session
 **		nsessions	number of sessions in the system
 **		nusers		number of users in the system
 **		totmem		total memory size in KB
 **		availmem	available memory size in KB
 **		ncpus		number of cpus
 **		physmem		physical memory size in KB
 **		size		size of a file or filesystem in KB
 **		idletime	seconds of idle time (see mom_main.c)
 **		loadave		current load average
 **		quota		quota information (sizes in KB)
 */


#define SGI_ZOMBIE_WRONG 1
#define COMPLEX_MEM_CALC 0

#ifndef TRUE
#define FALSE	0
#define TRUE	1
#endif	/* TRUE */

/* min period between two cput samples - in seconds */
#define PBS_MIN_CPUPERCENT_PERIOD   30


#if COMPLEX_MEM_CALC==1
static  char            procfs[] = "/proc";
static  char            procfmts[] = "/proc/%s";
#else
static  char            procfs[] = "/proc/pinfo";
static  char            procfmts[] = "/proc/pinfo/%s";
#endif /* COMPLEX_MEM_CALC */
static	DIR		*pdir = NULL;
static	int		pagesize;
static	int		kfd = -1;
static  time_t		sampletime;

#define	TBL_INC		100		/* initial proc table */
#define MAPNUM		512		/* max number of mem segs */

static	int		nproc = 0;
static	int		max_proc = 0;
struct	proc_info {
	prpsinfo_t	info;
#if COMPLEX_MEM_CALC==1
	int		map_num;
	prmap_sgi_t	*map;
#endif /* COMPLEX_MEM_CALC */
	ash_t		procash;
};
static	struct	proc_info	*proc_array = NULL;

extern	char	*ret_string;
time_t		wait_time = 10;
extern	char	extra_parm[];
extern	char	no_parm[];

extern	time_t	time_now;
extern	time_t	last_scan;

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
extern char	*loadave	(struct rm_attribute *attrib);

/*
 ** local functions and data
 */
static char	*totmem		(struct rm_attribute *attrib);
static char	*availmem	(struct rm_attribute *attrib);
char	*physmem	(struct rm_attribute *attrib);
static char	*ncpus		(struct rm_attribute *attrib);
static char	*quota		(struct rm_attribute *attrib);
#if	NODEMASK != 0
static char	*availmask	(struct rm_attribute *attrib);
#endif	/* NODEMASK */
extern char	*nullproc	(struct rm_attribute *attrib);
static time_t   sampletime_ceil;
static time_t   sampletime_floor;


/*
 ** local resource array
 */
struct	config	dependent_config[] = {
	{ "totmem",	totmem },
	{ "availmem",	availmem },
	{ "physmem",	physmem },
	{ "ncpus",	ncpus },
	{ "loadave",	loadave },
	{ "quota",	quota },
#if	NODEMASK != 0
	{ "availmask",	availmask },
#endif	/* NODEMASK */
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

/*
 * Time decoding macro.  Accepts a timestruc_t pointer.  Returns unsigned long
 * time in seconds, rounded.
 */

#define tv(val) (ulong)((val).tv_sec + ((val).tv_nsec + 500000000)/1000000000)

/**
 * @brief
 *      Scan a list of tasks and return true if one of them matches
 *      the ash.
 *
 * @param[in] pjob - job pointer
 * @param[in] sid - session id
 *
 * @return      Bool
 * @retval      TRUE    
 * @retval      FALSE   Error
 *
 */

static
int
injob(job *pjob, ash_t *pash)
{
	ash_t	ash;

	if (pjob->ji_globid) {
		sscanf(pjob->ji_globid, "%llx", &ash);
		return (ash == *pash);
	} else
		return 0;
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
	char			*id = "cput_ses";
	int			i;
	int			inproc = 0;
	ulong			cputime;
	ulong			deltat;
	int			nps = 0;
	ulong			proctime;
	ulong			perc;
	prpsinfo_t		*pi;

	cputime = 0;
	if (pjob->ji_globid == NULL) {
		pjob->ji_flags |= MOM_NO_PROC;
		return (cputime);
	}

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (!injob(pjob, &proc_array[i].procash))
			if (!inproc)
				continue;
		else
			break;

		inproc = 1;

		nps++;
		proctime = tv(pi->pr_time) + tv(pi->pr_ctime);
		cputime += proctime;
		DBPRT(("%s: ses %d pid %d pcput %lu cputime %lu\n",
			id, pi->pr_sid, pi->pr_pid, proctime, cputime))
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
	int			inproc = 0;
	rlim64_t		segadd;
	prpsinfo_t		*pi;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))
	segadd = 0;
	if (pjob->ji_globid == NULL)
		return (segadd);

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (!injob(pjob, &proc_array[i].procash))
			if (!inproc)
				continue;
		else
			break;

		DBPRT(("%s: %s(%d:%d) mem %llu\n",
			__func__, pi->pr_fname, pi->pr_sid, pi->pr_pid,
			(rlim64_t)((rlim64_t)pi->pr_size * (rlim64_t)pagesize)))

		segadd += (rlim64_t)((rlim64_t)pi->pr_size*(rlim64_t)pagesize);
	}
	DBPRT(("%s: total mem %llu\n\n", __func__, segadd))
	return (segadd);
}

#if COMPLEX_MEM_CALC==1
/**
 * @brief
 * 	Internal session resident memory size function.  COMPLEX VERSION
 *
 * @param[in] job - job pointer
 *
 * @return	(a 64 bit integer) the number of bytes used by session
 *
 */
static rlim64_t
resi_sum(job *pjob)
{
	rlim64_t		resisize, resisub;
	int			num, i, j;
	int			inproc = 0;
	prpsinfo_t		*pi;
	prmap_sgi_t		*mp;
	u_long			lastseg, nbps;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))

	resisize = 0;
	if (pjob->ji_globid == NULL)
		return (resisize);
	lastseg = 99999;
	nbps = (pagesize / sizeof(uint_t)) * pagesize;
	/* sysmacros.h says "4Meg" ...hmmm */

	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (!injob(pjob, &proc_array[i].procash))
			if (!inproc)
				continue;
		else
			break;

		DBPRT(("%s: %s(%d:%d) rss %llu (%lu pages)\n",
			__func__, pi->pr_fname, pi->pr_sid, pi->pr_pid,
			(rlim64_t)((rlim64_t)pi->pr_rssize*(rlim64_t)pagesize),
			pi->pr_rssize))

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
#else /* COMPLEX_MEM_CALC==0 */
/**
 * @brief
 *      Internal session resident memory size function.  COMPLEX VERSION
 *
 * @param[in] job - job pointer
 *
 * @return      (a 64 bit integer) the number of bytes used by session
 *
 */
static rlim64_t
resi_sum(job *pjob)
{
	int			i;
	int			inproc = 0;
	rlim64_t		resisize, resisub;
	prpsinfo_t		*pi;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))

	resisize = 0;
	for (i=0; i<nproc; i++) {
		pi = &proc_array[i].info;

		if (!injob(pjob, &proc_array[i].procash))
			if (!inproc)
				continue;
		else
			break;

		DBPRT(("%s: %s(%d:%d) rss %llu (%lu pages)\n",
			__func__, pi->pr_fname, pi->pr_sid, pi->pr_pid,
			(rlim64_t)((rlim64_t)pi->pr_rssize*(rlim64_t)pagesize),
			pi->pr_rssize))
		resisize += (rlim64_t)((rlim64_t)pagesize * pi->pr_rssize);
	}
	DBPRT(("%s: total rss %llu\n\n", __func__, resisize))
	return (resisize);
}
#endif /* COMPLEX_MEM_CALC */

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
#if	NODEMASK != 0
	__uint64_t	rvalue;
	__uint64_t	nodemask;
#endif	/* NODEMASK */

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

		if (strcmp(pname, "cput") == 0 ||
			strcmp(pname, "pcput") == 0) {		/* set */
			retval = local_gettime(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((cpu_limit == 0) || (value < cpu_limit))
				cpu_limit = value;
		} else if (strcmp(pname, "vmem") == 0 ||
			strcmp(pname, "pvmem") == 0) {	/* set */
			retval = local_getsize(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((vmem_limit == 0) || (value < vmem_limit))
				vmem_limit = value;
		} else if (strcmp(pname, "mem") == 0 ||
			strcmp(pname, "pmem") == 0) {	/* set */
			retval = local_getsize(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			if ((mem_limit == 0) || (value < mem_limit))
				mem_limit = value;
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
			/* call special node mask function */
			nodemask = pres->rs_value.at_val.at_ll;
			rvalue = (__uint64_t)pmoctl(61, nodemask, 0);
			if (rvalue != nodemask) {
				(void)sprintf(log_buffer, "Tried to set node mask to 0x%0llx, was set to 0x%0llx", nodemask, rvalue);
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
					LOG_NOTICE,
					pjob->ji_qs.ji_jobid, log_buffer);
			}
#endif	/* NODEMASK */
		}
		pres = (resource *)GET_NEXT(pres->rs_link);
	}

	if (set_mode == SET_LIMIT_SET) {

		/* if either mem or pmem was given, set sys limit to lesser */
		if (mem_limit != 0) {
			res64lim.rlim_cur = res64lim.rlim_max = mem_limit;
			if (setrlimit64(RLIMIT_RSS, &res64lim) < 0)
				return (error("RLIMIT_RSS", PBSE_SYSTEM));
		}

		/* if either cput or pcput was given, set sys limit to lesser */
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
			strcmp(pname, "mem") == 0 ||
			strcmp(pname, "ncpus") == 0 ||
			strcmp(pname, "cput") == 0 ||
			strcmp(pname, "mem")  == 0 ||
			strcmp(pname, "vmem") == 0)
			return (TRUE);
		pres = (resource *)GET_NEXT(pres->rs_link);
	}

	return (FALSE);
}

int
mom_open_poll()
/**
 * @brief
 *      Setup for polling.
 *
 *      Open kernel device and get namelist info.
 *      Also open sgi project files.
 *
 * @return      int
 * @retval      0               Success
 * @retval      PBSE_SYSTEM     error
 * @retval	-1		error
 */
int
mom_open_poll()
{
	extern int	 open_sgi_proj();

	DBPRT(("%s: entered\n", __func__))
	pagesize = getpagesize();

	proc_array = (struct proc_info *)calloc(TBL_INC,
		sizeof(struct proc_info));
	if (proc_array == NULL) {
		log_err(errno, __func__, "malloc");
		return (PBSE_SYSTEM);
	}
	max_proc = TBL_INC;

	return (open_sgi_proj());
}

/**
 * @brief
 * 	Declare start of polling loop.
 *
 *	for each job, obtain ASH from task tables
 *	then obtain list of pids in each ASH in turn
 *	open and process /proc/(pid)
 *
 * @return      int
 * @retval      PBSE_INTERNAL   Dir pdir in NULL
 * @retval      PBSE_NONE       Success
 *
 */
int
mom_get_sample()
{
	int			fd;
	struct dirent		*dent;
	char			procname[100];
	int			np;
	int			num;
	int			mapsize;
	time_t			currtime;
	prmap_sgi_arg_t		maparg;
	struct	proc_info	*pi;
	prmap_sgi_t		map[MAPNUM];
	job			*pjob;
	aspidlist_t		*taskpids = 0;
	ash_t			ash;
	extern aserror_t 	aserrorcode;
	extern pbs_list_head	svr_alljobs;
	extern time_t time_last_sample;

	time_last_sample = time_now;
	sampletime_floor = time_last_sample;

	DBPRT(("%s: entered pagesize %d\n", __func__, pagesize))
	if (pdir == NULL)
		return PBSE_INTERNAL;

	rewinddir(pdir);
	nproc = 0;
	pi = proc_array;

	mapsize = sizeof(prmap_sgi_t) * MAPNUM;
	maparg.pr_size = mapsize;

	currtime = time(0);
	for (pjob = (job *)GET_NEXT(svr_alljobs);
		pjob;
		pjob = (job *)GET_NEXT(pjob->ji_alljobs)) {
		if (pjob->ji_qs.ji_substate != JOB_SUBSTATE_RUNNING)
			continue;

		if (pjob->ji_globid == NULL)
			continue;

		sscanf(pjob->ji_globid, "%llx", &ash);
		DBPRT(("%s: looking at job %s ASH %llx\n",
			__func__, pjob->ji_qs.ji_jobid, ash))

		taskpids = aspidsinash_local(ash);
		if (taskpids == NULL) {
			sprintf(log_buffer, "no pids in ash %lld for job %s",
				ash, pjob->ji_qs.ji_jobid);
			log_err(aserrorcode, __func__, log_buffer);
			continue;
		}

		for (np=0; np < taskpids->numpids; ++np, (void)close(fd)) {


			DBPRT(("%s:\t\t pid %d\n", __func__, taskpids->pids[np]))
			sprintf(procname, "%s/%d", procfs, taskpids->pids[np]);
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

#if COMPLEX_MEM_CALC==1
			if (pi->map) {
				free(pi->map);		/* free any old space */
				pi->map = NULL;
			}
			pi->map_num = 0;
			maparg.pr_vaddr = (caddr_t)map;

			if ((num = ioctl(fd, PIOCMAP_SGI, &maparg)) == -1) {
				if (errno != ENOENT)
					log_err(errno, __func__, "ioctl(PIOCMAP_SGI)");
				free(map);
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
#endif /* COMPLEX_MEM_CALC */

			/* save the ASH to which the proc belongs */
			pi->procash = ash;

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
		if (taskpids != NULL)
			asfreepidlist(taskpids, 0);
	}
	sampletime = time(0);
	if ((sampletime - currtime) > 5) {
		sprintf(log_buffer, "time lag %d secs", sampletime-currtime);
		log_err(-1, __func__, log_buffer);
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

		rd = find_resc_def(svr_resc_def, "ncpus", svr_resc_size);
		assert(rd != NULL);
		pres = add_resource_entry(at, rd);
		pres->rs_value.at_flags |= ATR_VFLAG_SET;
		pres->rs_value.at_type = ATR_TYPE_LONG;
		/*
		 * get pointer to list of resources *requested* for the job
		 * so the ncpus used can be set to ncpus requested
		 */
		at_req = &pjob->ji_wattr[(int)JOB_ATR_resource];
		assert(at->at_type == ATR_TYPE_RESC);

		pres_req = find_resc_entry(at_req, rd);
		if ((pres_req != NULL) &&
			((ncpus_req=pres_req->rs_value.at_val.at_long) !=0))
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
	lnum = MAX(*lp, cput_sum(pjob));
	*lp = lnum;

	/* now calculate weight moving average cpu usage percentage */

	if ((dur = sampletime_ceil+1 - pjob->ji_sampletim) > PBS_MIN_CPUPERCENT_PERIOD) {
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
	pres->rs_value.at_val.at_long = (long)((double)(time_now - pjob->ji_qs.ji_stime) * wallfactor);

	rd = find_resc_def(svr_resc_def, "mem", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	lp_sz = &pres->rs_value.at_val.at_size.atsv_num;
	lnum_sz = (resi_sum(pjob) + 1023) >> 10;	/* in KB */
	*lp_sz = MAX(*lp_sz, lnum_sz);

	return (PBSE_NONE);
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
	ash_t		ash;
	int		ct = 0;
	int		np;
	struct startjob_rtn sgid;
	aspidlist_t	*taskpids = 0;
	extern aserror_t aserrorcode;

	if (ptask->ti_job->ji_globid != NULL) {
		sscanf(ptask->ti_job->ji_globid, "%llx", &ash);
	} else {
		ash = asashofpid(ptask->ti_qs.ti_sid);
		sgid.sj_ash = ash;
		set_globid(ptask->ti_job, &sgid);
	}

	if ((ash != 0LL) && (ash != -1LL)) {
		taskpids = aspidsinash_local(ash);
		if (taskpids) {
			for (np=0; np<taskpids->numpids; ++np) {
				(void)kill(taskpids->pids[np], sig);
				++ct;
			}
		} else {
			sprintf(log_buffer, "no pids in ash %lld in %s", ash, __func__);
			log_err(aserrorcode, __func__, log_buffer);
		}
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
	int	i;

	DBPRT(("%s: entered\n", __func__))
	if (proc_array) {
#if COMPLEX_MEM_CALC==1
		for (i=0; i<max_proc; i++) {
			struct	proc_info	*pi = &proc_array[i];

			if (pi->map)
				free(pi->map);
		}
#endif /* COMPLEX_MEM_CALC */
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
 * @retval      -1      error
 * @retval      0       success
 */
int
mach_checkpoint(task *ptask, char *file, int abort)
{
#if MOM_CHECKPOINT == 1
	ash_t	ash;

	sscanf(ptask->ti_job->ji_globid, "%llx", &ash);

	/* ckpt_setup(0, 0);  Does nothing so why have it */

	if (abort)
		cpr_flags = CKPT_CHECKPOINT_KILL | CKPT_NQE;
	else
		cpr_flags = CKPT_CHECKPOINT_CONT | CKPT_NQE;
	return (ckpt_create(file, ash, P_ASH, 0, 0));
	/*	return ( ckpt_create(file, ptask->ti_qs.ti_sid, P_SID, 0, 0) ); */
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
	ckpt_id_t rc;
	ash_t	 momash;
	ash_t	 oldash = 0;
	char	 cvtbuf[20];
	cpr_flags = CKPT_NQE;

	/* KLUDGE to work-around SGI problem, for some reason ckpt_restart() */
	/* passes open file descriptor to /proc to restarted process	     */
	if (pdir)
		closedir(pdir);

	/* To restart the job with its old ASH, Mom must be in that ASH	    */
	/* When she does the restart.   However, before changing to that    */
	/* ASH, Mom must put herself in a new ASH all by herself, otherwise */
	/* she will take other system daemons with her into the job's ASH   */

	momash = getash();
	newarraysess();		/* isolate Mom in a ASH by herself  */
	if (ptask->ti_job->ji_globid != NULL) {
		/* now get job's old ASH and set it */
		sscanf(ptask->ti_job->ji_globid, "%llx", &oldash);
		if (setash(oldash) == -1) {
			DBPRT(("setash failed before restart, errno = %d", errno))
		}
	}
	rc =  ckpt_restart(file, (struct ckpt_args **)0, 0);
	if ((ptask->ti_job->ji_globid == NULL) && (rc > 0)) {
		(void)sprintf(cvtbuf, "%llx", rc);
		ptask->ti_job->ji_globid = strdup(cvtbuf);
	}

	newarraysess();		/* again, isolate Mom into ASH by herself */
	if (setash(momash) == -1) {	/* put Mom back to her old ASH */
		DBPRT(("setash failed after restart, errno = %d", errno))
	}

	/* KLUDGE TO work-around SGI problem, ckpt_restart sets the uid of */
	/* the calling process (me) to that of the restarted process       */
	if (setuid(0) == -1) {
		log_err(errno, "mach_restart", "cound't go back to root");
		exit(1);
	}
	if ((pdir = opendir(procfs)) == NULL) {
		log_err(errno, "mach_restart", "opendir");
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

char	*
cput(struct  rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
mem(struct  rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
sessions(struct  rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
pids(struct  rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
nsessions(struct  rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
nusers(struct  rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
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
static char	*
totmem(struct  rm_attribute *attrib)
{
	struct	statfs	fsbuf;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	if (statfs(procfs, &fsbuf, sizeof(struct statfs), 0) == -1) {
		log_err(errno, __func__, "statfs");
		rm_errno = RM_ERR_SYSTEM;
		return NULL;
	}
	DBPRT(("%s: bsize=%ld blocks=%lld\n", __func__,
		fsbuf.f_bsize, fsbuf.f_blocks))
	sprintf(ret_string, "%llukb",
		((rlim64_t)fsbuf.f_bsize * (rlim64_t)fsbuf.f_blocks) >> 10);
	return ret_string;
}

/**
 * @brief
 *      availmem() - return amount of available memory in system in KB as string
 *
 * @return      string
 * @retval      avbl memory on system                   Success
 * @retval      NULL                                    Error
 *
 */
static char	*
availmem(struct  rm_attribute *attrib)
{
	struct	statfs	fsbuf;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	if (statfs(procfs, &fsbuf, sizeof(struct statfs), 0) == -1) {
		log_err(errno, __func__, "statfs");
		rm_errno = RM_ERR_SYSTEM;
		return NULL;
	}
	DBPRT(("%s: bsize=%ld bfree=%lld\n", __func__,
		fsbuf.f_bsize, fsbuf.f_bfree))
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
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}
	sprintf(ret_string, "%ld", sysmp(MP_NAPROCS));
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
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}
	if (lseek(kfd, (off_t)kern_addr[KSYM_PHYS], SEEK_SET) == -1) {
		sprintf(log_buffer, "lseek to 0x%llx", kern_addr[KSYM_PHYS]);
		log_err(errno, __func__, log_buffer);
		rm_errno = RM_ERR_SYSTEM;
		return NULL;
	}
	if (read(kfd, (char *)&pmem, sizeof(pmem)) != sizeof(pmem)) {
		log_err(errno, __func__, "read");
		rm_errno = RM_ERR_SYSTEM;
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
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}
	if (statfs(param, &fsbuf, sizeof(struct statfs), 0) == -1) {
		log_err(errno, __func__, "statfs");
		rm_errno = RM_ERR_BADPARAM;
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
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	if (stat64(param, &sbuf) == -1) {
		log_err(errno, __func__, "stat");
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	sprintf(ret_string, "%llukb", (sbuf.st_size+512)>>10);
	return ret_string;
}

/**
 * @brief
 *      wrapper function for size_file which returns the size of file system
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
		rm_errno = RM_ERR_NOPARAM;
		return NULL;
	}
	if (momgetattr(NULL)) {
		log_err(-1, __func__, extra_parm);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	param = attrib->a_value;
	if (strcmp(attrib->a_qualifier, "file") == 0)
		return (size_file(param));
	else if (strcmp(attrib->a_qualifier, "fs") == 0)
		return (size_fs(param));
	else {
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}
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
	int 	load;

	if (lseek(kfd, (off_t)kern_addr[KSYM_LOAD], SEEK_SET) == -1) {
		sprintf(log_buffer, "lseek to 0x%llx", kern_addr[KSYM_LOAD]);
		log_err(errno, __func__, log_buffer);
		return (rm_errno = RM_ERR_SYSTEM);
	}
	if (read(kfd, (char *)&load, sizeof(load)) != sizeof(load)) {
		log_err(errno, __func__, "read");
		return (rm_errno = RM_ERR_SYSTEM);
	}

	/*
	 ** SGI does not have FSCALE like the SUN so the 1024
	 ** divisor was found by experment compairing the result
	 ** of this routine to uptime.
	 */
	*rv = (double)load/1024.0;
	return 0;
}

/**
 * @brief
 *      computes and returns the gracetime
 *
 * @param[in] secs - time
 *
 * @return      u_long
 * @retval      time in secs    if time limit > 0
 * @retval      0               if time limit < 0
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
 *      return the disk quota for file depending on the type of file
 *
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return      string
 * @retval      quota val       Success
 * @retval      NULL            error
 *
 */
static char     *
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
		rm_errno = RM_ERR_NOPARAM;
		return NULL;
	}
	if (strcmp(attrib->a_qualifier, "type")) {
		sprintf(log_buffer, "unknown qualifier %s",
			attrib->a_qualifier);
		log_err(-1, __func__, log_buffer);
		rm_errno = RM_ERR_BADPARAM;
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
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	if ((attrib = momgetattr(NULL)) == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = RM_ERR_NOPARAM;
		return NULL;
	}
	if (strcmp(attrib->a_qualifier, "dir") != 0) {
		sprintf(log_buffer, "bad param: %s=%s",
			attrib->a_qualifier, attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}
	if (attrib->a_value[0] != '/') {	/* must be absolute path */
		sprintf(log_buffer,
			"not an absolute path: %s", attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}
	if (stat(attrib->a_value, &sb) == -1) {
		sprintf(log_buffer, "stat: %s", attrib->a_value);
		log_err(errno, __func__, log_buffer);
		rm_errno = RM_ERR_EXIST;
		return NULL;
	}
	dirdev = sb.st_dev;
	DBPRT(("dir has devnum %d\n", dirdev))

	if ((m = setmntent(MOUNTED, "r")) == NULL) {
		log_err(errno, __func__, "setmntent");
		rm_errno = RM_ERR_SYSTEM;
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
		rm_errno = RM_ERR_EXIST;
		return NULL;
	}
	if (hasmntopt(me, MNTOPT_QUOTA) == NULL) {
		sprintf(log_buffer,
			"no quotas on filesystem %s", me->mnt_dir);
		log_err(-1, __func__, log_buffer);
		rm_errno = RM_ERR_EXIST;
		return NULL;
	}

	if ((attrib = momgetattr(NULL)) == NULL) {
		log_err(-1, __func__, no_parm);
		rm_errno = RM_ERR_NOPARAM;
		return NULL;
	}
	if (strcmp(attrib->a_qualifier, "user") != 0) {
		sprintf(log_buffer, "bad param: %s=%s",
			attrib->a_qualifier, attrib->a_value);
		log_err(-1, __func__, log_buffer);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}
	if ((uid = (uid_t)atoi(attrib->a_value)) == 0) {
		if ((pw = getpwnam(attrib->a_value)) == NULL) {
			sprintf(log_buffer,
				"user not found: %s", attrib->a_value);
			log_err(-1, __func__, log_buffer);
			rm_errno = RM_ERR_EXIST;
			return NULL;
		}
		uid = pw->pw_uid;
	}

	if (quotactl(Q_GETQUOTA, me->mnt_fsname, uid, (caddr_t)&qi) == -1) {
		log_err(errno, __func__, "quotactl");
		rm_errno = RM_ERR_SYSTEM;
		return NULL;
	}

	/* all size values in KB */
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

#if	NODEMASK != 0

#define MAXCNODES 64	/* Maximum number of nodes available in a nodemask. */

/**
 * @brief
 * 	Return a MAXCNODES-bit string with a '1' in each position where there
 * 	are two CPUs available for a node.
 *
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return 	string
 * @retval	MAXCNODES-bit	success
 * @retval	NULL		error
 */
static char    *
availmask(struct  rm_attribute  *attrib)
{
	int		nprocs, i;
	cnodeid_t	cpumap[MAXCNODES * 2];
	char		nodect[MAXCNODES];

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	/* Initialize cpu/node count and cpumap. */
	for (i = 0; i < MAXCNODES; i++) {
		nodect[i] = 0;
		cpumap[i * 2] = cpumap[i * 2 + 1] = -1;
	}

	nprocs = sysmp(MP_NPROCS);
	if (nprocs < 1) {
		log_err(errno, __func__, "sysmp(MP_NPROCS");
		rm_errno = RM_ERR_SYSTEM;
		return (NULL);
	}

	if (sysmp(MP_NUMA_GETCPUNODEMAP, (void *)cpumap,
		sizeof(cnodeid_t) * nprocs) != 0) {
		log_err(errno, __func__, "sysmp(MP_NUMA_GETCPUNODEMAP");
		rm_errno = RM_ERR_SYSTEM;
		return (NULL);
	}

	/*
	 * cpumap[] now contains either -1, or the number of the node that
	 * corresponds to that CPU.  Each node needs to have 2 CPUs - count
	 * up the references to each node, and generate the return string
	 * based on whether exactly 2 CPUs map to the node at the n'th
	 * position (from the right) or not.
	 */
	for (i = 0; i < MAXCNODES * 2; i++)
		if (cpumap[i] != (cnodeid_t)(-1))
			nodect[cpumap[i]] ++;

	/* Create the null-terminated string for the nodect ref'd in map[]. */
	for (i = 0; i < MAXCNODES; i++)
		ret_string[MAXCNODES - (i + 1)] = (nodect[i] == 2 ? '1' : '0');
	ret_string[i] = '\0';

	return ret_string;
}
#endif /* NODEMASK */

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
	if ((nice_val != 0) && (setpriority(PRIO_PROCESS, 0, nice_val) == -1)) {
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
	if ((nice_val != 0) && (setpriority(PRIO_PROCESS, 0, 0) == -1)) {
		(void)sprintf(log_buffer, "failed to nice(%d) mom", nice_val);
		log_err(errno, __func__, log_buffer);
	}
}

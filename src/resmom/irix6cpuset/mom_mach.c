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
#include <sys/time.h>
#include <sys/types.h>
#include <sys/procfs.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/quota.h>
#include <sys/statfs.h>
#include <sys/sysmacros.h>
#include <sys/sysmp.h>
#include <sys/resource.h>
#include <optional_sym.h>
#if MOM_CHECKPOINT == 1
#include <ckpt.h>
#endif	/* MOM_CHECKPOINT */
#include <sys/syssgi.h>
#if	NODEMASK != 0
#include <sys/pmo.h>
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
#include "resmon.h"
#include "../rm_dep.h"

#include "bitfield.h"

#include "mom_share.h"
#include "cpusets.h"
#include "collector.h"
#include "hammer.h"
#include "allocnodes.h"
#include "mapnodes.h"

#include "mom_func.h"
#include "mom_mach.h"
#include "session.h"

/**
 * @file
 *	System dependent code to gather information for the resource
 *	monitor for a Silicon Graphics (SGI) machine.
 *
 * @par	Resources known by this code:
 *		cput		cpu time for a pid or session
 *		mem		memory size for a pid or session in KB
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
 *		loadave		current load average
 *		quota		quota information (sizes in KB)
 */



#define	FAKE_NODE_RESOURCE	1

#define SGI_ZOMBIE_WRONG 1
#define COMPLEX_MEM_CALC 0

#ifndef TRUE
#define FALSE	0
#define TRUE	1
#endif	/* TRUE */

/* min period between two cput samples - in seconds */
#define PBS_MIN_CPUPERCENT_PERIOD   30


static	int		pagesize;
static	int		kfd = -1;
static  time_t		sampletime;

static	int		cpr_master_flag = CKPT_NQE | CKPT_RESTART_MIGRATE \
			| CKPT_ATTRFILE_IN_CWD;

static  sidpidlist_t    *taskpids = NULL;
static  int     nproc = 0;
static  int     myproc_max = 0;         /* entries in Proc_lnks  */
#define TBL_INC         200             /* initial proc table */
pbs_plinks     *Proc_lnks = NULL;       /* process links table head */

extern	char	*ret_string;
time_t		wait_time = 10;
extern	char	extra_parm[];
extern	char	no_parm[];

extern	time_t	time_now;
extern	time_t	last_scan;
extern  pid_t	mom_pid;
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
extern	struct	var_table	vtable;
extern char     *loadave        (struct rm_attribute *attrib);
extern	int	num_acpus;
extern	int	num_pcpus;
extern  u_Long	av_phy_mem;
extern	int	internal_state_update;
extern  pbs_list_head svr_alljobs;
extern  struct rlimit64 orig_stack_size;	/* see mom_main.c */

/* Bitfields used to maintain state of nodes that are "out of service". */
static Bitfield	rsvdnodes;		/* Nodes assigned to rsvd cpuset. */

/* Global data used by other threads and files. */
cpusetlist	*stuckcpusets = NULL;	/* List of cpusets needing reclaim */
Bitfield	stucknodes;		/* Nodes assigned to stuck cpusets. */
cpusetlist	*inusecpusets = NULL;	/* List of cpusets currently in use. */

/* The "available" pool of nodes to be allocated for jobs. */
Bitfield initialnodes;			/* Nodes physically available. */
Bitfield nodepool;			/* Nodes available for cpusets. */

pid_t		collector_pid;		/* PID of mom     collector thread */
pid_t		hammer_pid;		/* PID of hammer thread */

/* Convert time and memory to easy-to-read formats */
static char	*byte2val	(size_t bytes);
static char	*sec2val	(int seconds);


/*
 ** local functions and data
 */
static char	*totmem		(struct rm_attribute *attrib);
static char	*availmem	(struct rm_attribute *attrib);
char	*physmem	(struct rm_attribute *attrib);
static char	*ncpus		(struct rm_attribute *attrib);
static char	*quota		(struct rm_attribute *attrib);

static char	*physnodes	(struct rm_attribute *attrib);
static char	*sysnodes	(struct rm_attribute *attrib);
static char	*maxnodes	(struct rm_attribute *attrib);
static char	*readynodes	(struct rm_attribute *attrib);
static char	*execmask	(struct rm_attribute *attrib);
static char	*nodersrcs	(struct rm_attribute *attrib);
static char	*querystuck	(struct rm_attribute *attrib);
static char	*freenodes	(struct rm_attribute *attrib);
static char	*query_shared_cpusets(struct rm_attribute *attrib);
static char	*get_small_job_spec   (struct rm_attribute *attrib);
static char	*get_max_shared_nodes   (struct rm_attribute *attrib);
static time_t   sampletime_ceil;
static time_t   sampletime_floor;


extern char	*nullproc	(struct rm_attribute *attrib);

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

	{ "physnodes",	physnodes },
	{ "sysnodes",	sysnodes },
	{ "maxnodes",	maxnodes },
	{ "readynodes",	readynodes },
	{ "execmask",	execmask },
	{ "nodersrcs",	nodersrcs },
	{ "stuck",	querystuck },
	{ "nodepool",   freenodes },
	{ "shared_cpusets",   query_shared_cpusets },
	{ "small_job_spec",   get_small_job_spec },
	{ "max_shared_nodes",   get_max_shared_nodes },
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

	num_pcpus = sysmp(MP_NPROCS);
	num_acpus = sysmp(MP_NAPROCS);
	pagesize = getpagesize();

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

	/* Get local configuration options. */
	dep_configure();
	sprintf(log_buffer, "ALLOCATION POLICY: max_shared_nodes=%d schd_Chunk_Quantum=%d contiguous nodes, alloc_nodes_greedy=%d for request > 64", max_shared_nodes, schd_Chunk_Quantum, alloc_nodes_greedy);
	log_event(PBSEVENT_SYSTEM, 0, LOG_NOTICE, __func__, log_buffer);


	/* Get mappings from cpus to nodes and resources and vice versa. */
	if (mapnodes()) {
		log_err(-1, __func__, "cannot map node resources");
		die(0);
	}

	/* do this after mapnodes() */
	/* set defaults for unset values */
	if (cpuset_small_mem < 0) {
		cpuset_small_mem = maxnodemem*1024; /* convert to kbytes */
	}
	if (cpuset_small_ncpus < 0) {
		cpuset_small_ncpus = 1;
	} else if (cpuset_small_ncpus >= maxnodecpus) {
		sprintf(log_buffer,
			"cpuset_small_ncpus=%d >= maxnodecpus=%d, resetting to 0",
			cpuset_small_ncpus, maxnodecpus);
		log_err(0, "cpuset_small_ncpus_set", log_buffer);
		cpuset_small_ncpus = 0;
	}


	cpuset_create_flags_print("cpuset_create_flags=", cpuset_create_flags);
	sprintf(log_buffer,
		"cpuset_destroy_delay=%d secs cpuset_small_ncpus=%d cpuset_small_mem=%dkb", cpuset_destroy_delay, cpuset_small_ncpus, cpuset_small_mem);
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

	/* Set up the memory segment shared between various mom threads. */
	if (setup_shared_mem() == NULL) {
		log_err(errno, __func__, "Couldn't create shared memory.");
		die(0);
	}

	INIT_LOCK(mom_shared->log_lock);

	/* Start thread to collect resource usage information about jobs. */
	if ((collector_pid = start_collector(0 /* NOW */)) < 0) {
		log_err(errno, __func__, "Couldn't start collector thread.");
		die(0);
	}

	sprintf(log_buffer, "started collector thread, pid %d", collector_pid);
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

	if (enforce_hammer) {
		if ((hammer_pid = start_hammer(0 /* NOW */)) < 0) {
			log_err(errno, __func__, "Couldn't start hammer thread.");
			die(0);
		}

		sprintf(log_buffer, "started hammer thread pid %d", hammer_pid);
		log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

	} else
		hammer_pid = -1;

	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, "Setup complete.");

	return;
}

/**
 * @brief
 * 	returns the name of the cpuset, mem and ncpus assigned to the job. 
 * 	Info is taken from the job's alt_id field. The format of this field is: 
 * 	alt_id = ...cpuset=<cpuset_name>:<mem_assn>kb/<ncpus_assn>p 
 *
 * @param[in] pjob - job pointer
 * @param[out] name - name of cpuset 
 * @param[out] mem - memory
 * @param[out] ncpus - number of cpus
 *
 * @return	Void
 * Returns 1 if cpuset information was obtained; 0 otherwise. 
 */
static void
job_cpuset(job *pjob, char *name, size_t *mem, int *ncpus)
{
	char	*p, *p2;
	char	mems[512];
	char	ncpuss[512];
	int	i;

	strcpy(name, "");
	*mem = 0;
	*ncpus = 0;
	if (pjob->ji_wattr[(int)JOB_ATR_altid].at_flags & ATR_VFLAG_SET) {

		p = strstr(pjob->ji_wattr[(int)JOB_ATR_altid].at_val.at_str,
			"cpuset=");
		if (p) {
			if (p2=strstr(p, "=")) {
				i=0;
				p2++;
				while (p2 && *p2 != ':' && *p2 != '\0') {
					name[i] = *p2;
					i++;
					p2++;
				}
				name[i] = '\0';

				if (p2 && *p2 == ':')
					p2++;

				i=0;
				while (p2 && *p2 != '/' && *p2 != '\0') {
					if (isdigit(*p2)) {
						mems[i] = *p2;
						i++;
					}
					p2++;
				}
				mems[i] = '\0';
				if (strlen(mems) > 0)
					*mem = atoi(mems);

				if (p2 && *p2 == '/')
					p2++;

				i=0;
				while (p2 && *p2 != '\0') {
					if (isdigit(*p2)) {
						ncpuss[i] = *p2;
						i++;
					}
					p2++;
				}
				ncpuss[i] = '\0';
				if (strlen(ncpuss) > 0)
					*ncpus = atoi(ncpuss);

			}

		}
	}
}
/**
 * @brief
 * 	cpusets_initialize must be called AFTER the system has information
 * 	about jobs on the system. This is usually after the call to
 * 	init_abort_jobs().
 * 	This takes care of creating the initial nodepool, rsvnodes, stucknodes,
 * 	and initialnodes list.
 *
 * Strategies:
 *
 * (1) It will not destroy any cpusets that it didn't create. The nodes of these
 *     cpusets will be placed in rsvdnodes pool.
 *
 * (2) Any cpuset that PBS created but with no associated job will be put in
 *     stuckcpusets list and the nodes assigned to it is placed on stucknodes.
 *
 * (3) Any cpuset that PBS created but with an associated, running job will be
 *     put in the inusecpusets list, and nodes assigned to it is made ineligible
 *     in nodepool.
 */
void
cpusets_initialize(void)
{
	cpusetlist	*ptr;
	int		nsets;
	int		rsets;
	job		*pjob = (job *)0;
	char		cpuset_name[QNAME_STRING_LEN+1];
	cpuset_shared	share;
	Bitfield	job_nodes;
	size_t		mem;
	int		ncpus;

	/* add to inusecpusets those jobs that mom sees as running. */
	/* note: since resources_used.walltime is not saved onto file, */
	/* the time_to_live values of jobs are reset back to */
	/* current_time + job's walltime */

	inusecpusets = NULL;
	pjob = (job *)GET_NEXT(svr_alljobs);
	while (pjob != (job *)0) {
		if (pjob->ji_qs.ji_state == JOB_STATE_RUNNING &&
			pjob->ji_qs.ji_substate == JOB_SUBSTATE_RUNNING) {

			/* obtain cpuset info (name,mem,ncpus) from alt_id */
			job_cpuset(pjob, cpuset_name, &mem, &ncpus);
			if (strlen(cpuset_name) > 0) { /* cpuset_name recov */

				cpuset_shared_unset(&share);
				if (is_small_job2(pjob, mem, ncpus, &share)) {
					strcpy(share.owner,
						(char *)pjob->ji_qs.ji_jobid);
				}

				if( cpuset2bitfield(cpuset_name, &job_nodes) \
									== 0 ) {
					(void)add_to_cpusetlist(&inusecpusets,
						cpuset_name,
						&job_nodes,
						&share);
				}

			} else {
				sprintf(log_buffer,
					"job %s could not recover all cpuset info: cpuset=%s mem=%dkb ncpus=%dp", pjob->ji_qs.ji_jobid, cpuset_name, mem, ncpus);
				log_err(0,  "cpusets_initialize", log_buffer);
			}

		}

		pjob = (job *)GET_NEXT(pjob->ji_alljobs);
	}

	/*
	 * Find any cpusets currently in existence that belongs to PBS, and
	 * does not have an associated, running job.
	 * If it matches and try to destroy them.
	 * If any are not destroyed, make a note of the nodes which they are
	 * consuming.
	 */
	BITFIELD_CLRALL(&stucknodes);	/* Start out fresh. */
	BITFIELD_CLRALL(&rsvdnodes);	/* Start out fresh. */
	BITFIELD_CLRALL(&nodepool);	/* Start out fresh. */
	stuckcpusets = NULL;

	if (enforce_cpusets &&
		((nsets = query_cpusets(&stuckcpusets, NULL)) != 0)) {
		/*
		 * Look for and remove any cpuset not owned by PBS from the
		 * list of * current cpusets.  Keep track of the nodes they
		 * occupy.
		 */
		if (rsets=remove_non_pbs_cpusets(&stuckcpusets, &rsvdnodes)) {
			/*
			 * Reserved cpusets (non-PBS owned) were found and
			 * removed from the list * (but not deleted!).  The
			 * nodes they occupy have been copied into rsvdnodes
			 * Subtract # of reserved cpusets from nsets.
			 */
			nsets -= rsets;
		}
		/* Remove any cpusets in use by running jobs from the list. */
		for (ptr = inusecpusets; ptr != NULL; ptr = ptr->next) {
			if (remove_from_cpusetlist(&stuckcpusets,
				NULL, ptr->name, NULL) == 0)
				nsets --;
		}

		/* If any sets remain, compute the nodes they cover. */
		if (nsets) {
			for (ptr = stuckcpusets; ptr != NULL; ptr = ptr->next)
				BITFIELD_SETM(&stucknodes, &(ptr->nodes));

			/*
			 * Now try to reclaim the cpusets, removing the nodes
			 * from stucknodes if they are reclaimed correctly.
			 * If not all could be reclaimed, log a message.
			 */
			if (reclaim_cpusets(&stuckcpusets, &stucknodes)!=nsets) {
				log_err(-1, __func__,
					"some previously-existing cpusets "
					"couldn't be reclaimed.");
			}
		}

		/*
		 * stucknodes now has the union of all stuck cpuset nodes, and
		 * stuckcpusets is a lsit of any cpusets to be reclaimed.
		 *
		 * Both of these exclude the RESERVED_CPUSET, if found.
		 */



	}
	/* Find the set of nodes that are physically available. */
	if (availnodes(&nodepool)) {
		log_err(-1, __func__, "cannot get available nodes");
		die(0);
	}
	BITFIELD_CPY(&initialnodes, &nodepool);

	/* Remove any nodes in the reserved system cpuset. */
	BITFIELD_CLRM(&nodepool, &rsvdnodes);

	/* Remove any nodes remaining that are in stuck cpusets. */
	BITFIELD_CLRM(&nodepool, &stucknodes);

	/* And any nodes in running jobs. */
	for (ptr = inusecpusets; ptr != NULL; ptr = ptr->next)
		BITFIELD_CLRM(&nodepool, &(ptr->nodes));

	(void)sprintf(log_buffer,
		"Initial nodes (hex): %s", bitfield2hex(&initialnodes));
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

#ifdef DEBUG
	(void)sprintf(log_buffer,
		"Initial nodes (binary): %s", bitfield2bin(&initialnodes));
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
#endif

	(void)sprintf(log_buffer, "Avail nodes (nex): %s",
		bitfield2hex(&nodepool));
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

#ifdef DEBUG
	(void)sprintf(log_buffer, "%d Avail nodes (binary): %s",
		BITFIELD_NUM_ONES(&nodepool), bitfield2bin(&nodepool));
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

	(void)sprintf(log_buffer, "%d Reserved nodes (binary): %s",
		BITFIELD_NUM_ONES(&rsvdnodes), bitfield2bin(&rsvdnodes));
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

	(void)sprintf(log_buffer, "%d Stuck nodes (binary): %s",
		BITFIELD_NUM_ONES(&stucknodes),
		bitfield2bin(&stucknodes));
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
#endif

	mom_update_resources();

	cleanup_cpuset_permfiles();
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, "Setup complete.");

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
	cpusetlist	*sets, *rset;
	int		nsets;
	int		rsets;

	if (kfd >= 0)
		(void)close(kfd);

	/* Attempt to destroy any cpusets left standing. */
	sets = NULL;

	if (enforce_cpusets && ((nsets = query_cpusets(&sets, NULL)) != 0)) {
		/* Remove the reserved cpusets (non-PBS owned) from the list of
		 cpusets. */
		if (rsets=remove_non_pbs_cpusets(&sets, NULL))
			nsets -= rsets;

		/* Remove any cpusets in use by running jobs from the list. */
		for (rset = inusecpusets; rset != NULL; rset = rset->next) {
			if (remove_from_cpusetlist(&sets, NULL, rset->name,
				NULL) == 0)
				nsets --;
		}

		if (nsets) {
			/*
			 * Try to reclaim any remaining cpusets.
			 * If not all could be reclaimed, log a message.
			 */
			if (reclaim_cpusets(&sets, NULL) != nsets) {
				log_err(-1, __func__,
					"some previously-existing cpusets "
					"couldn't be reclaimed.");
			}
		}
	}

	if (enforce_cpusets)
		cleanup_cpuset_permfiles();

	if (mom_shared != NULL) {
		mom_shared->do_collect = FALSE;

		/*
		 * Send a SIGTERM to the hammer thread -- don't SIGTERM -1!  Do
		 * this one first, since (in theory) this code won't block and
		 * will exit immediately.
		 */
		if (hammer_pid > 0) {
			kill(hammer_pid, SIGTERM);
			sprintf(log_buffer, "waiting for hammer (pid %d)",
				hammer_pid);
			log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, l, log_buffer);
			waitpid(hammer_pid, NULL, 0);
			hammer_pid = -1;
		}

		/*
		 * Send a SIGTERM to the collector thread -- don't SIGTERM -1!
		 * If the collector is hanging on an ioctl(PICOMAP_SGI), this
		 * may take quite some time to exit.  Perhaps a timeout would
		 * be best here?  The signal will eventually be delivered, but
		 * the process will be a zombie if we don't wait() for it.
		 */
		if (collector_pid > 0) {
			kill(collector_pid, SIGTERM);
			sprintf(log_buffer, "waiting for collector pid %d",
				collector_pid);
			log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
			waitpid(collector_pid, NULL, 0);
			collector_pid = -1;
		}

		if (cleanup_shared_mem())
			log_err(errno, __func__, "Couldn't cleanup shared memory.");
	}

	return;
}

/**
 * @brief
 *	Don't need any periodic procsessing.
 */
void
end_proc()
{

	if (enforce_cpusets && stuckcpusets != NULL) {
		if (reclaim_cpusets(&stuckcpusets, &stucknodes) > 0)
			mom_update_resources();
	}

	return;
}

/**
 * @brief
 * 	set by Administrator to cause OS upgradeable checkpoints to occur
 *
 * @param[in] value value for upgrade
 *
 * @return      unsigned long
 * @return      0               error
 * @retval      1               success
 */
handler_ret_t
set_checkpoint_upgrade(char *value)
{
	int		val = 0;

	if (set_boolean(__func__, value, &val) == HANDLER_FAIL)
		return HANDLER_FAIL;

	if (val)
		cpr_master_flag |= CKPT_CHECKPOINT_UPGRADE;

	return HANDLER_SUCCESS;
}

/*
 * Time decoding macro.  Accepts a timestruc_t pointer.  Returns unsigned long
 * time in seconds, rounded.
 */

#define tv(val) (ulong)((val).tv_sec + ((val).tv_nsec + 500000000)/1000000000)

/**
 * @brief
 *      Scan a job's list of tasks and return true if one of them matches
 *      the SGI JobID, or process (sid or pid) represented by *pi.
 *
 * @param[in] pjob - job pointer
 * @param[in] pi - pointer to proc_info structure
 *
 * @return      int
 * @retval      TRUE    Success
 * @retval      FALSE   Error
 *
 */
static int
injob(job *pjob, proc_info *pi)
{
	pbs_list_head	phead;
	task            *ptask;
	pid_t           key;

	if (pjob->ji_extended.ji_ext.ji_jid > 0) {
		/* use sgi job id */
		if (pjob->ji_extended.ji_ext.ji_jid == pi->pr_jid)
			return TRUE;
		else
			return FALSE;
	}

	/* no job id, fall back to sid */

	key = (pi->pr_sid == 0) ? pi->pr_pid : pi->pr_sid;
	phead = pjob->ji_tasks;
	for (ptask = (task *)GET_NEXT(phead);
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
	int			i, n;
	ulong			cputime = 0;
	int                     nps = 0;
	int			taskprocs;
	ulong			proctime;
	proc_info		*pi;
	pid_t			key;
	int jlimits_installed = _MIPS_SYMBOL_PRESENT(getjusage);
	struct  jobrusage	job_usage;
	task			*ptask;
	ulong			tcput;

	memset(&job_usage, 0, sizeof(job_usage));
	sampletime_floor = time(0);
	if (jlimits_installed && (pjob->ji_extended.ji_ext.ji_jid > 0)) {
		sampletime_floor = time(0);
		if (getjusage(pjob->ji_extended.ji_ext.ji_jid,
			JLIMIT_CPU, &job_usage) == 0) {
			sampletime_ceil = time(0);
			if (job_usage.high_usage != 0) {
				return (ulong)((double)(job_usage.high_usage) *
					cputfactor);
			}
		} else if (errno == ENOPKG) {
			/* shouldn't get here with a irixjid */
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
				LOG_ERR, pjob->ji_qs.ji_jobid,
				"IRIX JID found for job but "
				"no jlimits in kernel");
			pjob->ji_extended.ji_ext.ji_jid = 0;
		}
	}

	/* look at each process */
	ACQUIRE_LOCK(mom_shared->pinfo_lock);
	sampletime_floor = mom_shared->current->samplestart;
	sampletime_ceil  = mom_shared->current->samplestop;
	n = mom_shared->current->entries;

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
		pi = &((proc_info *)mom_shared->current->data)[0];
		for (i=0; i<n; i++, pi++) {
			key = (pi->pr_sid == 0) ? pi->pr_pid : pi->pr_sid;

			/* is this process part of any task? */
			if (ptask->ti_qs.ti_sid != key)
				continue;

			nps++;
			taskprocs++;
			if ((pi->flags & MOM_PROC_IS_ZOMBIE) &&
				pi->pr_sid != pi->pr_pid)
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
	RELEASE_LOCK(mom_shared->pinfo_lock);

	if (nps == 0)
		pjob->ji_flags |= MOM_NO_PROC;

	return ((unsigned long)((double)cputime * cputfactor));
}

/**
 * @brief
 * 	Internal session memory usage function.
 *
 * @param[in] job - a job pointer.
 *
 * @return	Returns the total number of bytes of address
 *      	space consumed by all current tasks within the list of tasks.
 */
static rlim64_t
vmem_sum(job *pjob)
{
	int			i, n;
	int			inproc = 0;
	rlim64_t		totvmem;
	proc_info		*pi;

	DBPRT(("%s: entered pagesize %d %s\n", __func__,
		pagesize, pjob->ji_qs.ji_jobid))
	totvmem = 0;

	ACQUIRE_LOCK(mom_shared->pinfo_lock);
	pi = &((proc_info *)mom_shared->current->data)[0];
	n = mom_shared->current->entries;

	for (i=0; i<n; i++, pi++) {
		if (!injob(pjob, pi)) {
			if (!inproc)
				continue;
			else
				break;
		}

		inproc = 1;

		DBPRT(("%s:    proc %d, vmem %ld, mem %ld\n", __func__, pi->pr_pid,
			pi->vmem, pi->mem));
		totvmem += pi->vmem;
	}
	DBPRT(("%s: total vmem %llu\n\n", __func__, totvmem))

	RELEASE_LOCK(mom_shared->pinfo_lock);
	return (totvmem);
}

/**
 * @brief
 *      Internal session mem (workingset) size function.  COMPLEX CALC VERSION
 *
 * @param[in] pjob - job pointer
 *
 * @return      Returns in a 64 bit intege the number of bytes used by session
 *
 */
static rlim64_t
resi_sum_complex(job *pjob)
{
	int			i, n;
	int			inproc = 0;
	size_t			totmem;
	proc_info		*pi;

	totmem = 0;

	ACQUIRE_LOCK(mom_shared->pinfo_lock);
	pi = &((proc_info *)mom_shared->current->data)[0];
	n = mom_shared->current->entries;

	for (i = 0; i < n; i++, pi++) {
		if (!injob(pjob, pi)) {
			if (!inproc)
				continue;
			else
				break;
		}

		inproc = 1;

		/* Add in the process' share of the private memory. */
		totmem += pi->mem;
	}

	RELEASE_LOCK(mom_shared->pinfo_lock);

	return (totmem);
}

/**
 * @brief
 * 	Update the job attribute for resources used.
 *
 *	The first time this is called for a job, set up resource entries for
 *	each resource that can be reported for this machine.  Fill in the
 *	correct values.  Return an error code.
 *
 * @param[in] pjob - job pointer
 *
 * @return	int
 * @retval	PBSE_NONE
 */
static int
update_resources(job *pjob)
{
	resource	*pres;
	attribute	*at;
	resource_def	*rd;
	u_Long 		*lp_sz, lnum_sz;
	unsigned long	*lp, lnum, oldcput, sampledcput;
	long		dur;
	int 		cput_sample_sane;

	assert(pjob != NULL);
	at = &pjob->ji_wattr[(int)JOB_ATR_resc_used];
	assert(at->at_type == ATR_TYPE_RESC);

	at->at_flags |= ATR_VFLAG_MODIFY;

	rd = find_resc_def(svr_resc_def, "cput", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	lp = (unsigned long *)&pres->rs_value.at_val.at_long;
	oldcput = *lp;
	/* following function has side effect - sets sampletime_floor & _ceil */
	sampledcput=cput_sum(pjob);
	if (sampledcput >= oldcput) {
		*lp=sampledcput;
		cput_sample_sane=1;
	} else {
		*lp=oldcput;
		cput_sample_sane=0;
	}
	/* now calculate weight moving average cpu usage percentage */
	/* note calc_cpupercent does the Right Thing
	 if ji_sampletim is invalid (0 or -1)!
	 */
	if ((dur = sampletime_ceil+1 - pjob->ji_sampletim) > \
					PBS_MIN_CPUPERCENT_PERIOD) {
		calc_cpupercent(pjob, oldcput, *lp, dur, at);
	}
	/* unconditional wrt "dur" test, as is cput update */
	pjob->ji_sampletim = sampletime_floor;
	/* flag invalid sampletime if sample is fishy */
	pjob->ji_sampletim = cput_sample_sane?(pjob->ji_sampletim):0;

	rd = find_resc_def(svr_resc_def, "vmem", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	lp_sz = &pres->rs_value.at_val.at_size.atsv_num;
	lnum_sz = vmem_sum(pjob) >> 10; /* as KB */
	*lp_sz = MAX(*lp_sz, lnum_sz);

	rd = find_resc_def(svr_resc_def, "walltime", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	pres->rs_value.at_val.at_long = (time_now - pjob->ji_qs.ji_stime);

	rd = find_resc_def(svr_resc_def, "mem", svr_resc_size);
	assert(rd != NULL);
	pres = find_resc_entry(at, rd);
	assert(pres != NULL);
	lp_sz = &pres->rs_value.at_val.at_size.atsv_num;
	lnum_sz = resi_sum(pjob) >> 10; /* in KB */
	*lp_sz = MAX(*lp_sz, lnum_sz);

	return (PBSE_NONE);
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
	rlim64_t	cpu_limit  = 0;
	struct rlimit	curr_lim;
#if	NODEMASK != 0
	__uint64_t	rvalue;
	__uint64_t	nodemask;
#endif	/* NODEMASK */
	extern int	local_getsize(resource *, rlim64_t *);

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
			char	hold[16];

			retval = getlong(pres, &value);
			if (retval != PBSE_NONE)
				return (error(pname, retval));
			sprintf(hold, "%d", (int)pres->rs_value.at_val.at_long);

			/* Set MPI envvars - see pe_environ(5) manpage. */
			bld_env_variables(&vtable, "MP_SET_NUMTHREADS", hold);
			bld_env_variables(&vtable, "OMP_DYNAMIC", "FALSE");
		} else if (strcmp(pname, "cput") == 0) {
			retval = getlong(pres, &value);
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
		} else if (strcmp(pname, "pcput") == 0) {	/* set */
			retval = getlong(pres, &value);
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
			/*
			 * "nodemask" has been deprecated in this version.
			 * The cpuset will set an "effective nodemask", so
			 * there is no reason to set one explicitly.
			 */
			/* DO NOTHING */;
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
 */
int
mom_open_poll()
{
	DBPRT(("%s: entered\n", __func__))
	pagesize = getpagesize();

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
int
mom_get_sample()
{
	job	*pjob;
	task	*ptask;
	pid_t	*sids;
	int	thissid, maxsids;
	extern pbs_list_head	svr_alljobs;

	/* Get a lock on the shared segment. */
	ACQUIRE_LOCK(mom_shared->share_lock);

	sids     = (pid_t *)mom_shared->sessions.data;
	maxsids  = mom_shared->sessions.slots;
	thissid  = 0;

	/* Nothing to do yet. */
	mom_shared->sessions.entries = 0;

	if ((pjob = (job *)GET_NEXT(svr_alljobs)) == NULL) {
		RELEASE_LOCK(mom_shared->share_lock);
		return PBSE_NONE;
	}

	for (; pjob != NULL; pjob = (job *)GET_NEXT(pjob->ji_alljobs)) {
		/* Ignore any non-running jobs in the list. */
		if (pjob->ji_qs.ji_substate != JOB_SUBSTATE_RUNNING)
			continue;

		for (ptask = (task *)GET_NEXT(pjob->ji_tasks);
			ptask != NULL;
			ptask = (task *)GET_NEXT(ptask->ti_jobtask)) {
			sids[thissid ++] = ptask->ti_qs.ti_sid;
			if (thissid >= maxsids) {
				sprintf(log_buffer, "Too many SIDs! (%d max)",
					maxsids);
				log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER,
					LOG_DEBUG, __func__, log_buffer);

				/* Set up to bail out. */
				pjob = NULL;
				break;
			}
		}
	}

	mom_shared->sessions.entries = thissid;

	/* If any sessions need to be checked, notify the other threads */
	if (thissid) {
		/*
		 * Start the collector if not already running.  Also post a
		 * wakeup request in case it was asleep.
		 */
		mom_shared->do_collect = TRUE;
		mom_shared->wakeup     = TRUE;
	}

	/*
	 * Now release the lock.  This will cause the collector thread to
	 * start processing the sids if it is idle.
	 */
	RELEASE_LOCK(mom_shared->share_lock);

	sampletime = time(NULL);
	sampletime_ceil = sampletime;
	return (PBSE_NONE);
}

/**
 * @brief
 * 	Stub function for updating resource usage for a job.  The actual updates
 * 	are done at the end of each successful run of the collector thread.
 * 	This part just initializes the values for the job if they are not set.
 *
 * @param[in] pjob - pointer to job structure
 *
 * @return int
 * @retval PBSE_NONE    for success.
 */
int
mom_set_use(job *pjob)
{
	resource	*pres;
	resource	*pres_req;
	attribute	*at;
	attribute	*at_req;
	resource_def	*rd;
	long                     ncpus_req;


	assert(pjob != NULL);
	at = &pjob->ji_wattr[(int)JOB_ATR_resc_used];
	assert(at->at_type == ATR_TYPE_RESC);

	if ((pjob->ji_qs.ji_svrflags & JOB_SVFLG_Suspend) != 0)
		return (PBSE_NONE);	/* job suspended, don't track it */

	DBPRT(("%s: entered %s\n", __func__, pjob->ji_qs.ji_jobid))

	/* Is it already initialized?  If so, just update resource usage. */
	if ((at->at_flags & ATR_VFLAG_SET))
		return update_resources(pjob);
	else {
		DBPRT(("%s: new job %s, call mom_get_sample()\n", __func__,
			pjob->ji_qs.ji_jobid));
		(void)mom_get_sample();			/* update sid list */
	}

	/* Initialize the job's resource usage values. */
	at->at_flags |= ATR_VFLAG_MODIFY;
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

	return PBSE_NONE;
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
	int             ct;
	int             i;

	DBPRT(("%s: entered sid %d\n", __func__, sesid))
	if (sesid <= 1)
		return 0;

	taskpids = sidpidlist_get(sesid);
	if (taskpids == NULL)
		return 0;

	nproc = taskpids->numpids;
	ct = bld_ptree(sesid);

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
	sidpidlist_free(taskpids);

	return ct;
}

/**
 * @brief
 *      Suspends a job.
 *
 * @param[in] pjob - pointer to job to be suspended
 *
 * @return	int
 * @retval	0	Success
 * @retval	-1	error
 *
 */
int
suspend_job(job *pjob)
{
	cpusetlist	*cset;
	task	*ptask;

	if (!(_MIPS_SYMBOL_PRESENT(cpusetMove) &&
		_MIPS_SYMBOL_PRESENT(cpusetMoveMigrate) &&
		enforce_cpusets))
		return 0;

	cset=find_cpuset_byjob(inusecpusets, pjob->ji_qs.ji_jobid);
	if (cset == NULL) {
		sprintf(log_buffer, "did not find a cpuset for job %s",
			pjob->ji_qs.ji_jobid);
		log_err(-1, __func__, log_buffer);
		return (-1);
	}

	if (cset->sharing) {
		for (ptask = (task *)GET_NEXT(pjob->ji_tasks);
			ptask != NULL;
			ptask = (task *)GET_NEXT(ptask->ti_jobtask)) {

			if (!cpusetMove(cset->name, NULL, CPUSET_SID,
				ptask->ti_qs.ti_sid)) {
				sprintf(log_buffer,
					"cpusetMove(%s,NULL,%d) for %s failed",
					cset->name, ptask->ti_qs.ti_sid,
					ptask->ti_job->ji_qs.ji_jobid);
				log_err(-1, __func__, log_buffer);
				return (-1);
			}
			sprintf(log_buffer, "cpusetMove(%s,NULL,%d) for %s ok",
				cset->name, ptask->ti_qs.ti_sid,
				pjob->ji_qs.ji_jobid);
			log_err(-1, __func__, log_buffer);
		}
	} else {	/* exclusive cpuset */
		if (!cpusetDetachAll(cset->name)) {
			sprintf(log_buffer, "cpusetDetachAll(%s) for %s failed",
				cset->name, pjob->ji_qs.ji_jobid);
			log_err(-1, __func__, log_buffer);
			return (-1);
		}
		sprintf(log_buffer, "cpusetDetachAll(%s) for %s ok",
			cset->name, pjob->ji_qs.ji_jobid);
		log_err(-1, __func__, log_buffer);
	}

	clear_cpuset(pjob);
	return 0;
}

/**
 * @brief
 *      Resumes a job.
 *      Call with the job pointer.
 *
 * @param[in] pjob - pointer to job to be suspended
 *
 * @return      int
 * @retval      0       Success
 * @retval      -1      error
 *
 */
int
resume_job(job *pjob)
{
	Bitfield assn_nodes;
	char	 cname[QNAME_STRING_LEN+1];
	cpuset_shared sh_info;
	char    cbuf[512];
	char    obuf[512];
	char    *p;
	int	is_shared;
	task	*ptask;
	/* Assign the job a cpuset.  C.f. mom_start.c */
	int     assign_cpuset(job *, Bitfield *, char *, cpuset_shared *);

	if (!(_MIPS_SYMBOL_PRESENT(cpusetMove) &&
		_MIPS_SYMBOL_PRESENT(cpusetMoveMigrate) &&
		enforce_cpusets))
		return 0;

	if (assign_cpuset(pjob, &assn_nodes, (char *)cname, &sh_info)) {
		(void)sprintf(log_buffer, "Cannot assign cpuset to %s",
			pjob->ji_qs.ji_jobid);
		log_err(errno, __func__, log_buffer);
		errno = EAGAIN;
		return (-1);
	}
	/* IMPORTANT: detach mom's pid from the created cpuset! */
	/*         the recreated queue only "houses" job's processes */
	cpusetDetachPID(cname, getpid());

	/*
	 * Now account for the information back from the restart.  A
	 * cpuset was created -- remove the nodes from the global pool.
	 */

	(void)add_to_cpusetlist(&inusecpusets, cname, &assn_nodes, &sh_info);
#ifdef DEBUG
	print_cpusets(inusecpusets,
		"INUSECPUSETS---------------------------->");
#endif

	/* And add the nodemask field to the job resources_used list. */
	(void)note_nodemask(pjob, bitfield2hex(&assn_nodes));
	BITFIELD_CLRM(&nodepool, &assn_nodes);

	cbuf[0] = '\0';
	if (pjob->ji_wattr[(int)JOB_ATR_altid].at_flags & ATR_VFLAG_SET) {
		strcpy(cbuf, pjob->ji_wattr[(int)JOB_ATR_altid].at_val.at_str);
		if (p=strstr(cbuf, ",cpuset="))
			*p = '\0';
	}

	is_shared = cpuset_shared_is_set(&sh_info);
	if (is_shared) {
		sprintf(obuf, ",cpuset=%s:%dkb/%dp", cname,
			sh_info.free_mem, sh_info.free_cpus);
	} else {
		sprintf(obuf, ",cpuset=%s:%dkb/%dp", cname,
			nodemask_tot_mem(&assn_nodes),
			nodemask_num_cpus(&assn_nodes));
	}

	strcat(cbuf, obuf);
	(void)decode_str(&pjob->ji_wattr[JOB_ATR_altid],
		ATTR_altid, NULL, cbuf);
	update_ajob_status(pjob);

	for (ptask = (task *)GET_NEXT(pjob->ji_tasks);
		ptask != NULL;
		ptask = (task *)GET_NEXT(ptask->ti_jobtask)) {

		(void)kill_session(ptask->ti_qs.ti_sid, SIGCONT, 0);
		if (!cpusetMoveMigrate(NULL, cname, CPUSET_SID,
			ptask->ti_qs.ti_sid)) {
			sprintf(log_buffer,
				"cpusetMoveMigrate(NULL,%s,%d) for %s failed",
				cname, ptask->ti_qs.ti_sid,
				pjob->ji_qs.ji_jobid);
			log_err(-1, __func__, log_buffer);
			clear_cpuset(pjob);
			return (-1);
		}
		sprintf(log_buffer, "cpusetMoveMigrate(NULL,%s,%d) for %s ok",
			cname, ptask->ti_qs.ti_sid,
			pjob->ji_qs.ji_jobid);
		log_err(-1, __func__, log_buffer);
	}

	return 0;
}

/**
 * @brief
 * 	Clean up everything related to polling.
 *
 * @return	int
 * @retval	PBSE_NONE
 */
int
mom_close_poll()
{
	DBPRT(("mom_close_poll: entered\n"))
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
	char 	cbuf[512];
	char 	obuf[512];
	char	*p;

#if MOM_CHECKPOINT == 1
	ckpt_id_t rc;
	char	 cvtbuf[20];

	pid_t    kid;
	int	 c2pfd[2], rfd, wfd, i, rv;
	struct rst_rtn {
		ckpt_id_t	ckptid;
		int		errno;
		cpusetlist	cpuset;
		cpuset_shared	shared_cpuset_info;
	} rst_rtn;
	job *pjob2;
	jid_t sgijid;

	char irix_release[SYS_NMLN];
	char *irix_overlay;
	int new_cpr_behaviour=0;

	/* Assign the job a cpuset.  C.f. mom_start.c */
	int	assign_cpuset(job *, Bitfield *, char *, cpuset_shared *);

	cpr_flags = cpr_master_flag;

	(void)sprintf(log_buffer, "called from pid %d , file %s",
		getpid(), file);
	log_err(-1, "mach_restart", log_buffer);

	/*
	 * ckpt_restart() does its own fork() and sets up the restarted job's
	 * processes.  This all needs to happen within a cpuset, but that
	 * cpuset has to be in a subprocess.
	 *
	 * Set up a pipe, then fork.  The child will create a cpuset, then
	 * do the restart.  The child then passes the ckpt_id_t and bitfield
	 * up to the parent on the pipe, and exits.
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

		if (enforce_cpusets) {
			/*
			 * In the child now.
			 * Create a cpuset for this job, and attach the current
			 * process to that cpuset.  rst_rtn.cpuset.nodes will be set
			 * to include the nodes assigned to that cpuset.
			 * if cpuset assigned is shared, then pass info about it
			 * in rst_rtn.cpuset_shared_info.
			 */
			if (assign_cpuset(ptask->ti_job, &(rst_rtn.cpuset.nodes),
				(char *)rst_rtn.cpuset.name,
				&(rst_rtn.shared_cpuset_info))) {
				(void)sprintf(log_buffer, "Cannot assign cpuset to %s",
					ptask->ti_job->ji_qs.ji_jobid);
				log_err(errno, __func__, log_buffer);
				(void)close(wfd);
				exit(1);
			}
			log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
				LOG_INFO,
				ptask->ti_job->ji_qs.ji_jobid,
				"assign_cpuset success");

		}

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

		/* Now, running inside that cpuset, restart the checkpoint. */
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB,
			LOG_INFO,
			ptask->ti_job->ji_qs.ji_jobid,
			"calling ckpt_restart");

		/* Now, running inside that cpuset, restart the checkpoint. */
		rst_rtn.ckptid = ckpt_restart(file, (struct ckpt_args **)0, 0);

		if (rst_rtn.ckptid == -1)
			rst_rtn.errno  = errno;
		else
			rst_rtn.errno = 0;

		/* And hand the ckpt_id_t and nodes back up to the parent. */
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
		char	*qn;
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

			/* guess the name of existing cpuset created by child */                        /* for sure, this cpuset has not been added to */
			/* inusecpusets */
			qn = job_to_qname(ptask->ti_job);
			if( qn && !find_cpuset(inusecpusets, qn) && \
                                                is_cpuset_pbs_owned(qn) ) {
				sprintf(log_buffer, "destroying cpuset %s",
					qn);
				log_err(errno, "mach_restart", log_buffer);
				destroy_cpuset(qn);
			}

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
			"restart helper returned ckpt %lld nodes %s",
			rst_rtn.ckptid, bitfield2hex(&rst_rtn.cpuset.nodes));
		log_err(-1, __func__, log_buffer);

		/*
		 * Now account for the information back from the restart.  A
		 * cpuset was created -- remove the nodes from the global pool.
		 */

		(void)add_to_cpusetlist(&inusecpusets,
			rst_rtn.cpuset.name,
			&(rst_rtn.cpuset.nodes),
			&(rst_rtn.shared_cpuset_info));
#ifdef DEBUG
		print_cpusets(inusecpusets,
			"INUSECPUSETS---------------------------->");
#endif

		/* And add the nodemask field to the job resources_used list. */                (void)note_nodemask(ptask->ti_job,
			bitfield2hex(&(rst_rtn.cpuset.nodes)));
		BITFIELD_CLRM(&nodepool, &(rst_rtn.cpuset.nodes));

		cbuf[0] = '\0';
		if (ptask->ti_job->ji_wattr[(int)JOB_ATR_altid].at_flags & ATR_VFLAG_SET) {
			strcpy(cbuf,
				ptask->ti_job->ji_wattr[(int)JOB_ATR_altid].at_val.at_str);

			if (p=strstr(cbuf, ",cpuset="))
				*p = '\0';
		}

		if (cpuset_shared_is_set(&rst_rtn.shared_cpuset_info)) {
			sprintf(obuf, ",cpuset=%s:%dkb/%dp",
				rst_rtn.cpuset.name,
				rst_rtn.shared_cpuset_info.free_mem,
				rst_rtn.shared_cpuset_info.free_cpus);
		} else {
			sprintf(obuf, ",cpuset=%s:%dkb/%dp",
				rst_rtn.cpuset.name,
				nodemask_tot_mem(&rst_rtn.cpuset.nodes),
				nodemask_num_cpus(&rst_rtn.cpuset.nodes));
		}

		strcat(cbuf, obuf);
		(void)decode_str(&ptask->ti_job->ji_wattr[JOB_ATR_altid],
			ATTR_altid, NULL, cbuf);
		update_ajob_status(ptask->ti_job);

		rc = rst_rtn.ckptid;	/* for the code below */
		errno = rst_rtn.errno;
	}

	/* KLUDGE TO work-around SGI problem, ckpt_restart sets the uid of */
	/* the calling process (me) to that of the restarted process       */
	if (setuid(0) == -1) {
		log_err(-1, "mach_restart", "couldn't go back to root");
		exit(1);
	}

	/* Retrieve the cpuset if the restart failed. */
	if (rc < 0 && enforce_cpusets && \
				BITFIELD_IS_NONZERO(&rst_rtn.cpuset.nodes)) {

		cpusetlist	*cset;
		if ((cset=find_cpuset(inusecpusets,
			rst_rtn.cpuset.name)) != NULL) {

			if( !cset->sharing || \
			cpuset_shared_get_numjobs(cset->sharing)  == 1 ) {
				(void)teardown_cpuset(rst_rtn.cpuset.name,
					&rst_rtn.cpuset.nodes);
			}
		}
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
cput(struct rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
mem(struct rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
sessions(struct rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
pids(struct rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

pid_t	*
allpids(void)
{
	return NULL;
}

char	*
nsessions(struct rm_attribute *attrib)
{
	rm_errno = RM_ERR_UNKNOWN;
	return NULL;
}

char	*
nusers(struct rm_attribute *attrib)
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
static char *
totmem(struct rm_attribute *attrib)
{
	struct	statfs	fsbuf;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	if (statfs("/proc", &fsbuf, sizeof(struct statfs), 0) == -1) {
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
static char     *
availmem(struct rm_attribute *attrib)
{
	struct	statfs	fsbuf;

	if (attrib) {
		log_err(-1, __func__, extra_parm);
		rm_errno = RM_ERR_BADPARAM;
		return NULL;
	}

	if (statfs("/proc", &fsbuf, sizeof(struct statfs), 0) == -1) {
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
	sprintf(ret_string, "%ld", sysmp(MP_NPROCS));
	return ret_string;
}

/**
 * @brief
 *      returns the total physical memory in system in KB as string
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
 *      return file system size in Kb as string
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
 *      return file size in Kb as string
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
	int     load;

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

/**
 * @brief
 * 	physnodes() - Return the number of nodes physically on this host that are physically
 * 	configured with sufficient resources to be considered for scheduling.
 *
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return      string
 */
static char *
physnodes(struct  rm_attribute *attrib)
{
	(void)sprintf(ret_string, "%d", BITFIELD_NUM_ONES(&initialnodes));
	return ret_string;
}

/**
 * @brief
 * 	sysnodes() Return the number of nodes reserved for "system" use.  This is the number
 * 	of nodes in the RESERVED_CPUSET cpsuet, if it exists.
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return      string
 */
 */
static char *
sysnodes(struct  rm_attribute *attrib)
{
	(void)sprintf(ret_string, "%d", BITFIELD_NUM_ONES(&rsvdnodes));
	return ret_string;
}

static char *
nodersrcs(struct  rm_attribute *attrib)
{
	(void)sprintf(ret_string, "%dmb/%dp",
		minnodemem - memreserved, minnodecpus);
	return ret_string;
}

/**
 * @brief
 * 	maxnodes() Return the maximum number of nodes that will ever be available for use by
 * 	user jobs.  This is the number of nodes configured, minus the nodes that
 * 	are reserved for system use (RESERVED_CPUSET).
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return      string
 */
static char *
maxnodes(struct  rm_attribute *attrib)
{
	Bitfield mn;

	BITFIELD_CPY(&mn, &initialnodes);
	BITFIELD_CLRM(&mn, &rsvdnodes);
	(void)sprintf(ret_string, "%d", BITFIELD_NUM_ONES(&mn));
	return ret_string;
}

/* readynodes()
 *
 * Returns the number of nodes which are currently ready to be scheduled.
 * This is the number of nodes that are in the nodepool.
 *
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return      string
 */
static char *
readynodes(struct  rm_attribute *attrib)
{
	(void)sprintf(ret_string, "%d", BITFIELD_NUM_ONES(&nodepool));
	return ret_string;
}

/**
 * @brief
 * 	querystuck() Generate a comma-separated list of cpusets (and a total count of the nodes)
 * 	that are currently in stuck cpusets.  This may be useful in debugging or
 * 	monitoring.
 *
 * @param[in] attrib - pointer to rm_attribute structure(type)
 *
 * @return      string
 */
static char *
querystuck(struct  rm_attribute  *attrib)
{
	char	*fmt;
	cpusetlist	*ptr;

	fmt = ret_string;
	(void)sprintf(fmt, "%d:", BITFIELD_NUM_ONES(&stucknodes));
	fmt += strlen(fmt);

	for (ptr = stuckcpusets; ptr != NULL; ptr = ptr->next) {
		checkret(&fmt, 128);
		(void)sprintf(fmt, "%s%s", ptr->name, ptr->next ? " " : "");
		fmt += strlen(fmt);
	}
	return ret_string;
}

/**
 * @brief
 *	qusery about the shared cpuset
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return	string
 * @retval	cpuset
 *
 */
static char *
query_shared_cpusets(struct  rm_attribute  *attrib)
{
	char	*fmt;
	cpusetlist	*ptr;
	int	mem, cpus;
	int	n;

	fmt = ret_string;

	strcpy(fmt, "");
	for (ptr = inusecpusets; ptr != NULL; ptr = ptr->next) {
		if (ptr->sharing) {
			checkret(&fmt, 128);
			mem = cpuset_shared_get_free_mem(ptr->sharing);
			cpus = cpuset_shared_get_free_cpus(ptr->sharing);
			(void)sprintf(fmt, "%s/%dnb/%dkb/%dp%s", ptr->name,
				BITFIELD_NUM_ONES(&ptr->nodes), mem, cpus,
				ptr->next ? "," : "");
			fmt += strlen(fmt);
		}
	}
	n = strlen(ret_string);
	if (n > 0 && ret_string[n-1] == ',')
		ret_string[n-1] = '\0';

	return ret_string;
}

/**
 * @brief
 *	returns the # of cpus and memory a small job can request
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return	string
 * @retval	mem/cpus
 *
 */
static char *
get_small_job_spec(struct  rm_attribute *attrib)
{

	(void)sprintf(ret_string, "%dkb/%dp", cpuset_small_mem,
		cpuset_small_ncpus);
	return ret_string;
}

/**
 * @brief
 *	returns the max nodes per host
 *
 * @param[in] attrib - pointer to rm_attribute structure
 *
 * @return	string
 * @retval	maxnodes per host
 *
 */
static char *
get_max_shared_nodes(struct  rm_attribute *attrib)
{

	(void)sprintf(ret_string, "%d", max_shared_nodes);

	return ret_string;
}

static char *
freenodes(struct rm_attribute *attrib)
{
	strcpy(ret_string, bitfield2hex(&nodepool));

	return ret_string;
}

/**
 * @brief
 * 	execmask() - Retained for backwards compatibility.
 */
static char *
execmask(struct rm_attribute *attrib)
{
	Bitfield em;

	BITFIELD_CPY(&em, &initialnodes);
	BITFIELD_CLRM(&em, &rsvdnodes);

	(void)strcpy(ret_string, bitfield2hex(&em));
	return ret_string;
}

/**
 * @brief
 * 	Convert a number of seconds into a text string of the form HH:MM:SS.
 * 
 * @param[in] seconds - number of seconds
 *
 * @return	string
 * @retval	secs in  HH:MM:SS fmt
 *
 */
static char *
sec2val(int seconds)
{
	static char	tval[16];

	int		hours   = 0;
	int		minutes = 0;

	/* Hours */
	if (seconds >= (60 * 60))
		hours = seconds / (60 * 60);

	seconds -= (hours * (60 * 60));

	/* Minutes */
	if (seconds >= 60)
		minutes = seconds / 60;

	/* Seconds */
	seconds -= (minutes * 60);

	(void)sprintf(tval, "%2.2d:%2.2d:%2.2d", hours, minutes, seconds);

	return (tval);
}

/**
 * @brief
 * 	Return a pointer to a static string that is the shortest string by which
 * 	the number of bytes can be accurately represented.
 */
static char *
byte2val(size_t bytes)
{
	size_t	mult		= 1;	/* Initial multiplier */
	int	log_1024	= 0;	/* log base 1024 of multiplier */
	size_t	next_mult	= 1024;	/* multiplier of next-highest unit */
	static char string[32];

	char	*units[] = {
		"b",	/* bytes     */
		"kb",	/* kilobytes */
		"mb",	/* megabytes */
		"gb",	/* gigabytes */
		"tb",	/* terabytes */
		"pb",	/* petabytes */
		"eb"	/* exabytes  */
	};

	/*
	 * Find the first multiplier by which the given byte count is not
	 * evenly divisible.  If we overflow the next multiplier, we have
	 * gone far enough.
	 */
	while (bytes && (bytes % next_mult) == 0) {
		mult = next_mult;
		next_mult <<= 10;
		log_1024 ++;

		if (next_mult == 0)
			break;
	}

	/*
	 * Make 'bytes' be the number of units being represented.
	 */
	bytes /= mult;

	/*
	 * Create a string from number of units, and the symbol for that unit.
	 */
	sprintf(string, "%lu%s", bytes, units[log_1024]);

	return (string);
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

/**
 * @brief
 *	updates the mom state by updating the resources on it
 */
void
mom_update_resources()
{
	/* returns resources that are under the control of PBS */
	av_phy_mem = nodemask_tot_mem(&initialnodes) - \
		     		nodemask_tot_mem(&rsvdnodes) - \
		     		nodemask_tot_mem(&stucknodes);
	num_acpus = nodemask_num_cpus(&initialnodes) - \
		     		nodemask_num_cpus(&rsvdnodes) - \
		    		nodemask_num_cpus(&stucknodes);

#ifdef DEBUG
	sprintf(log_buffer, "updated av_phy_mem to %llu and num_acpus to %d stuck_nodes_ncpus=%d stuck_nodes_mem=%d rsvd_mem=%d rsvd_ncpus=%d",
		av_phy_mem, num_acpus,
		nodemask_tot_mem(&stucknodes), nodemask_num_cpus(&stucknodes),
		nodemask_tot_mem(&rsvdnodes), nodemask_num_cpus(&rsvdnodes));
	log_err(0, "mom_update_resources", log_buffer);
	sprintf(log_buffer, "updated av_phy_mem to %llu and num_acpus to %d",
		av_phy_mem, num_acpus);
	log_err(0, "mom_update_resources", log_buffer);
#endif

	internal_state_update = UPDATE_MOM_STATE;
}

/**
 * @brief
 *      Get the info required for tm_attach.
 *	It is not provided by the collector.
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
	return TM_ENOTIMPLEMENTED;
#if 0
	int		i, n;
	proc_info	*pi;
	int		ret = TM_ENOPROC;

	if (getprocs() == 0)
		return TM_ESYSTEM;

	ACQUIRE_LOCK(mom_shared->pinfo_lock);
	pi = &((proc_info *)mom_shared->current->data)[0];
	n = mom_shared->current->entries;

	for (i=0; i<n; i++, pi++) {

		if (pid == pi->pr_pid) {
			*sid = pi->pr_sid;
			*uid = pi->pr_uid;
			memset(comm, '\0', len);
			memcpy(comm, pi->pr_fname,
				MIN(len-1, sizeof(pi->pr_fname)));
			ret = TM_OKAY;
			break;
		}
	}
	RELEASE_LOCK(mom_shared->pinfo_lock);
	return ret;
#endif
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
	return TM_ENOTIMPLEMENTED;
#if 0
	/* when the collector can be changed to provide the info
	 ** needed, the following code will be usefull.
	 */
	Bitfield assn_nodes;
	char	 cname[QNAME_STRING_LEN+1];
	cpuset_shared sh_info;
	char    cbuf[512];
	char    obuf[512];
	char    *p;
	int	is_shared;
	job	*pjob;
	/* Assign the job a cpuset.  C.f. mom_start.c */
	int     assign_cpuset(job *, Bitfield *, char *, cpuset_shared *);

	if (!(_MIPS_SYMBOL_PRESENT(cpusetMove) &&
		_MIPS_SYMBOL_PRESENT(cpusetMoveMigrate) &&
		enforce_cpusets))
		return TM_OKAY;

	pjob = ptask->ti_job;
	if (assign_cpuset(pjob, &assn_nodes, (char *)cname, &sh_info)) {
		(void)sprintf(log_buffer, "Cannot assign cpuset to %s",
			pjob->ji_qs.ji_jobid);
		return TM_ESYSTEM;
	}
	/* IMPORTANT: detach mom's pid from the created cpuset! */
	/*         the recreated queue only "houses" job's processes */
	cpusetDetachPID(cname, getpid());

	/*
	 * Now account for the information back from the restart.  A
	 * cpuset was created -- remove the nodes from the global pool.
	 */

	(void)add_to_cpusetlist(&inusecpusets, cname, &assn_nodes, &sh_info);
#ifdef DEBUG
	print_cpusets(inusecpusets,
		"INUSECPUSETS---------------------------->");
#endif

	/* And add the nodemask field to the job resources_used list. */
	(void)note_nodemask(pjob, bitfield2hex(&assn_nodes));
	BITFIELD_CLRM(&nodepool, &assn_nodes);

	cbuf[0] = '\0';
	if (pjob->ji_wattr[(int)JOB_ATR_altid].at_flags & ATR_VFLAG_SET) {
		strcpy(cbuf, pjob->ji_wattr[(int)JOB_ATR_altid].at_val.at_str);
		if (p=strstr(cbuf, ",cpuset="))
			*p = '\0';
	}

	is_shared = cpuset_shared_is_set(&sh_info);
	if (is_shared) {
		sprintf(obuf, ",cpuset=%s:%dkb/%dp", cname,
			sh_info.free_mem, sh_info.free_cpus);
	} else {
		sprintf(obuf, ",cpuset=%s:%dkb/%dp", cname,
			nodemask_tot_mem(&assn_nodes),
			nodemask_num_cpus(&assn_nodes));
	}

	strcat(cbuf, obuf);
	(void)decode_str(&pjob->ji_wattr[JOB_ATR_altid],
		ATTR_altid, NULL, cbuf);
	update_ajob_status(pjob);

	if (!cpusetMoveMigrate(NULL, cname, CPUSET_SID,
		ptask->ti_qs.ti_sid)) {
		sprintf(log_buffer,
			"cpusetMoveMigrate(NULL,%s,%d) for %s failed",
			cname, ptask->ti_qs.ti_sid,
			pjob->ji_qs.ji_jobid);
		clear_cpuset(pjob);
		return TM_ESYSTEM;
	}
	sprintf(log_buffer, "cpusetMoveMigrate(NULL,%s,%d) for %s ok",
		cname, ptask->ti_qs.ti_sid,
		pjob->ji_qs.ji_jobid);
	log_err(-1, __func__, log_buffer);

	return TM_OKAY;
#endif
}

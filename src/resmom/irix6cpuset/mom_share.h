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
#ifndef	_MOM_SHARE_H
#define	_MOM_SHARE_H
#ifdef	__cplusplus
extern "C" {
#endif

 *
 * Declaration of structs and objects shared between different threads of the
 * irix6array PBS mom.
 */

#include <sys/types.h>
#include <sys/time.h>
#include <sys/timespec.h>
#include <unistd.h>

#include "pbs_mutex.h"

#ifndef	ROUND_UP_TO
/*
 * Macro to round a value up to the next-highest granularity (or return the
 * exact value if it is on a grain boundary).
 */
#define ROUND_UP_TO(grain,size) \
    (((size) % (grain)) ? (((size) / (grain) + 1) * (grain)) : ((size)))

#endif /* !ROUND_UP_TO */

/* struct proc_info:
 *
 * The structure to hold all the sampled information for each process being
 * monitored by PBS mom.  tv_sample is the time at which the sample was
 * started, and elapsed contains the number of milliseconds the sampling
 * took for this process (subject to hardware clock resolution constraints).
 */
typedef struct proc_info {
	struct timeval	tv_sample;	/* Time this sample was started. */
	unsigned long	elapsed;	/* How long sampling took (msecs). */

	/* Per-process info collected from prpsinfo_t struct. */
	pid_t		pr_pid;		/* Individual process ID. */
	pid_t		pr_sid;		/* Process session group ID. */
	jid_t		pr_jid;		/* sgi job id */
	timespec_t	pr_time;	/* CPU time this process has used */
	timespec_t	pr_ctime;	/* CPU time used by unreaped children */
	timespec_t	pr_start;	/* Walltime since the process started */
	long		pr_size;	/* Size of process image in pages */
	long		pr_rss;		/* Resident Set Size in pages */

	/* Information from the memory map retrieved by PIOCMAP_SGI. */
	size_t		mem;		/* This proc's share of physmem. */
	size_t		vmem;		/* Virtual memory for this process. */

#define	MOM_PROC_IS_ZOMBIE	0x1	/* proc is zombie (prpsinfo) */
	int		flags;		/* Miscellaneous flags for this proc */

} proc_info;


/* struct metaarray:
 *
 * Array "meta" object for grouping dynamic array metadata.
 * stamp is currently unused, but could be used to check for out-of-date
 * data or the like.
 */
typedef struct metaarray {
	void *data;		/* Pointer to array of some type of data     */
	time_t stamp;		/* Time data was last valid (or 0 if not)    */
	time_t samplestart;	/* time of start of sampling cycle	     */
	time_t samplestop; 	/* time of end of sampling cycle	     */
	unsigned int entries;	/* Number of valid entries in the array      */
	unsigned int slots;	/* Total number of elements in the array     */
	size_t size;		/* Size of the data array (in bytes)         */
} metaarray;

/* struct shared_block:
 *
 * This structure is shared between threads of execution within the PBS mom.
 * It is used to synchronize and share data between the threads.
 */
typedef struct shared_block {
	volatile int	do_collect;	/* Collect information if true.      */
	volatile int	wakeup;		/* Mom wants collector to wakeup.    */

	/* Provide a mutex for locking logs between processes. */
	pbs_mutex	log_lock;

	/*
	 * Where to place the information resulting from a collection run.
	 * This is a standard double-buffering scheme -- "valid" data lives
	 * in pinfo[current], while the pinfo[!current] is being filled.
	 *
	 * Once the collector has completed its activity, the 'current' value
	 * will be swapped to the other array (with appropriate locking to
	 * avoid surprising a reader).
	 */
	pbs_mutex	pinfo_lock;	/* Mutex for the information below  */
	metaarray	pinfo[2];	/* current and filling buffers      */

	/* These each point to one of the two elements in the pinfo[] array */
	metaarray	*current;	/* Which buffer holds "valid" info. */
	metaarray	*filling;	/* Collector thread fills this one. */

	/*
	 * Mutual exclusion for job startup -- prevents hammer of processes
	 * before they are registered in the alljobs list.  This shared mutex
	 * overrides the unshared mutex pointed to in ../mom_main.c.
	 */
	pbs_mutex	pbs_commit_mtx;

	/* Information for the collector and hammer threads. */
	pbs_mutex	share_lock;	/* Mutex for access to work lists.  */
	metaarray	sessions;	/* Array of sessions for hammer. */

	/*
	 * Running sessions data pointed to 'sessions' metaarray above.
	 *
	 * This information is relatively small, so take advantage of the
	 * "wasted" space in the rest of the mapped segment.
	 * Note that this implies that the mom_shared arena is mapped at the
	 * same virtual address in all clients.
	 *
	 * Do not address _sidarray directly -- lock work_lock
	 * and access them through the sessions metaarrays.
	 *
	 * One can expect at most one session per CPU in the machine.
	 * 1024 should be far too much for any realistic Origin.
	 */

#define SHARED_BLOCK_ARRAY_SIZE		1024
	pid_t	_sidarray[SHARED_BLOCK_ARRAY_SIZE];	/* PID's tracked. */
} shared_block;

/*
 * Size of shared block, rounded up to a page boundary.  Used to map the
 * anonymous memory segment in which the shared block is placed.
 */
#define SHARED_BLOCK_SIZE \
    ROUND_UP_TO(sysconf(_SC_PAGESIZE),sizeof(shared_block))

/*
 * How large to make the memory segment for each of the shared proc_info
 * arrays.  Note that this is anonymous virtual memory, so this can be
 * quite large without actually using much memory.  This will be filled
 * with proc_info structs, one for each process Mom is tracking.  1000
 * proc_info's is about 132k.  512K should be *way* too much for any
 * Origin we will ever have.  A log message will be generated if this
 * value is ever too small, and it will continue to work, just not well.
 */
#define SHARED_PINFO_SIZE	(512*1024)

/*
 * Shared/global data items used by multiple threads in the mom.
 */
extern	shared_block	*mom_shared;	/* The shared communications block. */

/* Function declarations. */
shared_block		*setup_shared_mem(void);

int			cleanup_shared_mem(void);
int			close_inherited(void);

/*
 * Configuration/enforcement options.
 */
void	dep_configure(void);

extern int	enforce_cput, 		/* Enforce job "cput" request. */
enforce_pcput,		/* Enforce job "pcput" request. */
enforce_cpupct,		/* Enforce job "cpupercent" request. */
enforce_mem,		/* Enforce job "mem" request. */
enforce_vmem,		/* Enforce job "vmem" request. */
enforce_pvmem,		/* Enforce job "pvmem" request. */
enforce_wallt,		/* Enforce job "wallt" request. */
enforce_file,		/* Enforce job "file" request. */
enforce_hammer,		/* "Hammer" unauthorized users. */
enforce_nokill,		/* Hammer only logs unauthorized use. */
enforce_cpusets,	/* Create cpusets for each job. */
minnodemem,		/* Minimum number of megs per node. */
minnodecpus,		/* Minimum number of cpus per node. */
memreserved,		/* Amount of mem/node reserved. */
schd_Chunk_Quantum,	/* contiguity policy on node alloc */
alloc_nodes_greedy,	/* policy in alloc_nodes() */
max_shared_nodes;	/* max # of shared nodeboards */
#ifdef	__cplusplus
}
#endif
#endif /* _MOM_SHARE_H */

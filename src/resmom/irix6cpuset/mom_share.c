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

#include <sys/types.h>
#include <sys/mman.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "collector.h"
#include "resmon.h"

#include "mom_share.h"
#include "bitfield.h"
#include "mapnodes.h"
#include "cpusets.h"
#include "log.h"
/**
 * @file	mom_share.c
 */
/*
 * A global pointer to a shared region used for intercommunication between
 * the threads of the mom.  See mom_share.h for details of the shared_block.
 */
shared_block	*mom_shared = NULL;

/*
 * pbs_commit_ptr points (by default) to an unshared mutex (a slightly
 * expensive no-op).  This code needs to share the mutex between the main
 * mom and its hammer sub-process.  Part of the setup below points the commit
 * mutex pointer to a mutex in shared memory.
 */
extern volatile pbs_mutex	*pbs_commit_ptr;

/**
 * @brief 
 *	setup_shared_mem() - Create a shared anonymous memory segment, and layer a struct shared_block
 * 	onto it.
 *
 * @return	structure handle
 * @retval	a pointer to the shared block	success
 * @retval	A NULL pointer return
 * 		indicates some failure.
 */
shared_block *
setup_shared_mem(void)
{
	void	*ptr;
	int	fd, i, num;
	size_t	size;

	/*
	 * Create an anonymous shared segment for the "shalloc()" shared memory
	 * allocator.  This space is used for dynamic allocation of information
	 * shared between the two processes, specifically shared segment maps
	 * between processes.
	 */
	if ((fd = open("/dev/zero", O_RDWR)) < 0) {
		log_err(errno, __func__, "can't open /dev/zero");
		return NULL;
	}

	/*
	 * Create an anonymous shared memory segment in which to place the shared
	 * metadata (shared_block) passed between the two processes.
	 */
	size = SHARED_BLOCK_SIZE;
	ptr = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, (off_t)0);

	if (ptr == MAP_FAILED) {
		sprintf(log_buffer, "mmap(\"/dev/zero\", %llu)", (unsigned long long)size);
		log_err(errno, __func__, log_buffer);
		goto bail;
	}

	/*
	 * Overlay the shared_block object onto the front of the shared memory
	 * segment.  This memory should be all zeros, implicitly initializing
	 * all the fields in the struct.
	 */
	mom_shared = (shared_block *)ptr;

	/*
	 * Initialize two very large shared segments for the pinfo arrays.  Use
	 * the lazy commit for virtual memory -- this creates a large virtual
	 * address space, but only a small portion will actually be backed with
	 * physical pages.  This is anonymous memory, so it will not be backed to
	 * disk.  It must be unmapped properly, however.
	 */
	size = ROUND_UP_TO(sysconf(_SC_PAGESIZE), SHARED_PINFO_SIZE);

	for (i = 0; i < 2; i++) {
		ptr = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, (off_t)0);

		if (ptr == MAP_FAILED) {
			sprintf(log_buffer, "mmap(\"/dev/zero\", %lu)", size);
			log_err(errno, __func__, log_buffer);
			goto bail;
		}

		/* Fill in the array metadata, point to the new empty shared segment. */
		num = (SHARED_PINFO_SIZE / sizeof(proc_info));

		mom_shared->pinfo[i].data	= (void *)ptr;
		mom_shared->pinfo[i].size	= SHARED_PINFO_SIZE;
		mom_shared->pinfo[i].stamp	= (time_t)0;
		mom_shared->pinfo[i].slots	= num;
		mom_shared->pinfo[i].entries	= 0;
	}

	/* Close the file descriptor and mark inactive. */
	if (close(fd))
		log_err(errno, __func__, "close(\"/dev/zero\")");

	fd = -1;	/* Avoid confusion later (see bail: codepath). */

	/* Point the "current" buffer at one pinfo, "filling" at the other. */
	mom_shared->current			= &(mom_shared->pinfo[0]);
	mom_shared->filling			= &(mom_shared->pinfo[1]);

	/*
	 * Initialize the "session" arrays to point to the shared
	 * memory following the shared_block struct.  This avoids having to
	 * allocate yet another shared arena for this information, and it is
	 * integral to the sharing between the master and collector threads.
	 */
	size = (SHARED_BLOCK_ARRAY_SIZE * sizeof(pid_t));
	mom_shared->sessions.data		= &(mom_shared->_sidarray[0]);
	mom_shared->sessions.size		= size;
	mom_shared->sessions.stamp		= (time_t)0;
	mom_shared->sessions.slots		= SHARED_BLOCK_ARRAY_SIZE;
	mom_shared->sessions.entries	= 0;

	/* Initialize the locks on the pinfo and share (sessions) arrays. */
	INIT_LOCK(mom_shared->pinfo_lock);
	INIT_LOCK(mom_shared->share_lock);
	INIT_LOCK(mom_shared->log_lock);

	/* Point the job start commit private mutex at our shared mutex. */
	INIT_LOCK(mom_shared->pbs_commit_mtx);
	pbs_commit_ptr = (volatile pbs_mutex *)&(mom_shared->pbs_commit_mtx);

#ifdef DEBUG
	/* Enable debugging of mutexes. */
	mom_shared->pinfo_lock.d 		= 1;
	mom_shared->share_lock.d 		= 1;
	mom_shared->log_lock.d 		= 1;
	mom_shared->pbs_commit_mtx.d 	= 1;
#endif /* DEBUG */

	/* Disable collection for the moment.  Forces collector thread to sync. */
	mom_shared->do_collect		= 0;

	/* Shared memory is now set up. */
	return mom_shared;

	bail: /* Reached only on error. */

	log_err(errno, __func__, "can't setup shared memory - cleaning up...");

	if (fd > 0) {
		if (close(fd))
			log_err(errno, __func__, "close(\"/dev/zero\")");
	}

	cleanup_shared_mem();

	return NULL;
}

/**
 * @brief
 * 	cleanup_shared_mem() - Unmap and delete any shared segments.
 *
 * @return	int
 * @retval	0 	on success, 
 * @retval	-1 	if an error occurs.
 */
int
cleanup_shared_mem(void)
{
	int		i;

	if (mom_shared == NULL)
		return -1;

	/* Clean up the shared objects, if any. */
	for (i = 0; i < 2; i++) {
		if (mom_shared->pinfo[i].data) {
			munmap(mom_shared->pinfo[i].data, mom_shared->pinfo[i].size);
			memset(&mom_shared->pinfo[i], 0, sizeof(metaarray));
		}
	}

	/* And clean up the shared metadata. */
	munmap(mom_shared, SHARED_BLOCK_SIZE);
	mom_shared = NULL;

	return 0;
}

/**
 * @brief
 * 	close_inherited() - Close filedescriptors inherited from the main mom process.  Be sure to
 *  	ignore the stdio filedescriptors, and close the log before doing it, so
 * 	that we don't wipe out the log file descriptors.
 *
 * @return	int
 * @retval	0	success
 * 
 */
int
close_inherited(void)
{
	int			fd, max;
	char		closed[1024];
	extern char		*log_file;	/* from mom_main.c */
	extern char		*path_log;	/* from mom_main.c */

	/* Close the pbs logs (but quietly) */
	log_close(0);

	(void)strcpy(closed, "Closed fd");

	for (fd = 0, max = sysconf(_SC_OPEN_MAX); fd <= max; fd ++) {

		/* Skip STDIO file descriptors. */
		if (fd == fileno(stdin) ||
			fd == fileno(stdout) ||
			fd == fileno(stderr)) {
			continue;
		}

		if (close(fd) == 0) {
			(void)sprintf(log_buffer, " %d", fd);
			(void)strcat(closed, log_buffer);
		}
	}

	/* And re-open the log files. */
	log_open(log_file, path_log);
	log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, closed);

	return 0;
}

/*
 * Configuration parameters:
 *   - Enforce settings -- configure enforcement/reporting of various types
 * 	of resource limits and uses.
 *
 *   - Node resource values.  Minimum memory/cpu resources configured on a
 *	node in order for it to be schedulable.  Amount of memory reserved
 *	for system use per node.  These will be defaulted to the minimum
 *	mem/cpu count found on the machine, and 0 memory reserved.
 */
static int	setenforce	(char *limstr);
extern struct config		*config_array;

extern int enforce_mem;
int     enforce_cput, enforce_pcput, enforce_cpupct, enforce_vmem,
enforce_pvmem, enforce_wallt, enforce_file, enforce_hammer,
enforce_nokill, enforce_cpusets;

struct enforce_limit {
	char	*name;		/* Name of limit to enforce. */
	char	*alias;		/* "Alternate name" for limit. */
	int	*enabled;	/* Whether or not limit is enabled. */
};
struct enforce_limit	enforce[16];	/* Configurable enforcement options. */

int	minnodemem = -1;		/* Minimum number of megs per node. */
int	minnodecpus = -1;		/* Minimum number of cpus per node. */
int	memreserved = -1;		/* Amount of mem/node reserved. */
int	do_memreserved_adjustment;	/* Need vnode mem resource adjustment */
int	schd_Chunk_Quantum = -1;	/* Minimum # of nodes per job */
int	max_shared_nodes = MAX_NODES_PER_HOST;

int	alloc_nodes_greedy = 1;		/* if set to 1, allocate nodes in a */
/* way where it tries not to require */
/* requests <= 64 nodes to be in */
/* the same "chunk". */

/**
 * @brief
 *	process string of limits and set enforcements
 *
 * @param[in] limstr - string of limits
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	failure
 *
 */
static int
setenforce(char *limstr)
{
	char	*token, *copy;
	int		is_on, i;

	copy = strdup(limstr);
	if (copy == NULL) {
		log_err(errno, __func__, "strdup(limit)");
		return -1;
	}

	token = strtok(copy, ", \t\n");
	while (token != NULL) {

		/* Trim off any leading negations. */
		is_on = 1;
		while (*token == '!') {
			is_on = !is_on;
			token ++;
		}

		/* And look for a match against a type of enforcement. */
		for (i = 0; enforce[i].name != NULL; i ++) {
			if (strcasecmp(token, enforce[i].name) == 0) {
				*enforce[i].enabled = is_on;
				break;
			}
			if ((enforce[i].alias != NULL) &&
				(strcasecmp(token, enforce[i].name) == 0)) {
				*enforce[i].enabled = is_on;
				break;
			}
		}

		if (enforce[i].name == NULL) {
			(void)sprintf(log_buffer, "limit '%s' unrecognized - ignoring",
				token);
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__, log_buffer);
		} else {

			(void)sprintf(log_buffer, "%s enforcement of %s limits",
				is_on ? "enabling" : "disabling", enforce[i].name);
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__, log_buffer);
		}

		/* On to the next option, if any. */
		token = strtok(NULL, ", \t\n");
	}

	free(copy);
	return 0;
}

/**
 * @brief
 *	does machine dependent configuration.
 *
 * @return	Void
 *
 */
void
dep_configure(void)
{
	struct config	*cptr;
	int		i;
	char		*left;
	unsigned long	ul;

	i = 0;
	enforce[i].name		= "mem";
	enforce[i].alias	= "rss";
	enforce[i++].enabled	= &enforce_mem;	/* Default is on. */

	enforce[i].name		= "pvmem";
	enforce[i].alias	= NULL;
	enforce[i++].enabled	= &enforce_pvmem;
	enforce_pvmem		= 1;		/* Default is on. */

	enforce[i].name		= "vmem";
	enforce[i].alias	= NULL;
	enforce[i++].enabled	= &enforce_vmem;
	enforce_vmem		= 1;		/* Default is on. */

	enforce[i].name		= "walltime";
	enforce[i].alias	= "wallt";
	enforce[i++].enabled	= &enforce_wallt;
	enforce_wallt		= 1;		/* Default is on. */

	enforce[i].name		= "pcput";
	enforce[i].alias	= "pcputime";
	enforce[i++].enabled	= &enforce_pcput;
	enforce_pcput		= 1;		/* Default is on. */

	enforce[i].name		= "cput";
	enforce[i].alias	= "cputime";
	enforce[i++].enabled	= &enforce_cput;
	enforce_cput		= 1;		/* Default is on. */

	enforce[i].name		= "cpupct";
	enforce[i].alias	= "cpupercent";
	enforce[i++].enabled	= &enforce_cpupct;
	enforce_cpupct		= 0;		/* Default is OFF. */

	enforce[i].name		= "file";
	enforce[i].alias	= "filesize";
	enforce[i++].enabled	= &enforce_file;
	enforce_file		= 1;		/* Default is on. */

	enforce[i].name		= "hammer";
	enforce[i].alias	= "logins";
	enforce[i++].enabled	= &enforce_hammer;
	enforce_hammer		= 0;		/* Default is off. */

	enforce[i].name		= "nokill";
	enforce[i].alias	= "no_kill";
	enforce[i++].enabled	= &enforce_nokill;
	enforce_nokill		= 0;		/* Default is off. */

	enforce[i].name		= "cpusets";
	enforce[i].alias	= "miser";
	enforce[i++].enabled	= &enforce_cpusets;
	enforce_cpusets		= 1;		/* Default is on. */

	/* Terminate the enforcement configuration option array. */
	enforce[i].name		= NULL;
	enforce[i].alias	= NULL;
	enforce[i++].enabled	= 0;

	/* Attempt to parse any unrecognized commands. */
	for (cptr = config_array; cptr && cptr->c_name != NULL; cptr ++) {
		if (strcasecmp(cptr->c_name, "enforce") == 0 ||
			strcasecmp(cptr->c_name, "use") == 0 ||
			strcasecmp(cptr->c_name, "enable") == 0) {
			setenforce(cptr->c_u.c_value);

		} else if (strcasecmp(cptr->c_name, "minmem") == 0 ||
			strcasecmp(cptr->c_name, "minnodemem") == 0) {
			ul = strtoul(cptr->c_u.c_value, &left, 0);
			if (*left != '\0' && strcasecmp(left, "mb")) {
				sprintf(log_buffer,
					"cannot parse %s as megabytes for %s",
					cptr->c_u.c_value, cptr->c_name);
				log_event(PBSEVENT_SYSTEM, 0, LOG_NOTICE, __func__, log_buffer);
				continue;
			}
			minnodemem = ul;
		} else if (strcasecmp(cptr->c_name, "schd_quantum") == 0) {
			ul = strtoul(cptr->c_u.c_value, &left, 0);
			if (*left != '\0') {
				sprintf(log_buffer,
					"cannot parse %s for %s",
					cptr->c_u.c_value, cptr->c_name);
				log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
				continue;
			}
			schd_Chunk_Quantum = (int)ul;

		} else if (strcasecmp(cptr->c_name, "mbreserved") == 0 ||
			strcasecmp(cptr->c_name, "mbrsvd") == 0 ||
			strcasecmp(cptr->c_name, "memreserved") == 0 ||
			strcasecmp(cptr->c_name, "memrsvd") == 0) {
			ul = strtoul(cptr->c_u.c_value, &left, 0);
			if (*left != '\0' && strcasecmp(left, "mb")) {
				sprintf(log_buffer,
					"cannot parse %s as megabytes for %s",
					cptr->c_u.c_value, cptr->c_name);
				log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
				continue;
			}
			sprintf(log_buffer, "setting memreserved=%dmb", ul);
			log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);

			memreserved = ul;

		} else if (strcasecmp(cptr->c_name, "mincpus") == 0 ||
			strcasecmp(cptr->c_name, "minnodecpus") == 0) {
			ul = strtoul(cptr->c_u.c_value, &left, 0);
			if (*left != '\0') {
				sprintf(log_buffer,
					"cannot parse %s as # of cpus for %s",
					cptr->c_u.c_value, cptr->c_name);
				log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
				continue;
			}
			minnodecpus = ul;

		} else if (strcasecmp(cptr->c_name,
			"cpuset_create_flags") == 0) {
			cpuset_create_flags_map(cptr->c_u.c_value);

		} else if (strcasecmp(cptr->c_name,
			"cpuset_destroy_delay") == 0) {
			cpuset_destroy_delay_set(cptr->c_u.c_value);

		} else if (strcasecmp(cptr->c_name,
			"cpuset_small_ncpus") == 0) {
			cpuset_small_ncpus_set(cptr->c_u.c_value);

		} else if (strcasecmp(cptr->c_name,
			"cpuset_small_mem") == 0) {
			cpuset_small_mem_set(cptr->c_u.c_value);
		} else if (strcasecmp(cptr->c_name,
			"alloc_nodes_greedy") == 0) {
			ul = strtoul(cptr->c_u.c_value, &left, 0);
			if (*left != '\0') {
				sprintf(log_buffer,
					"cannot parse %s for %s",
					cptr->c_u.c_value, cptr->c_name);
				log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
				continue;
			}

			alloc_nodes_greedy = (int)ul;
		} else if (strcasecmp(cptr->c_name, "max_shared_nodes") == 0) {
			ul = strtoul(cptr->c_u.c_value, &left, 0);
			if (*left != '\0') {
				sprintf(log_buffer,
					"cannot parse %s for %s",
					cptr->c_u.c_value, cptr->c_name);
				log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
				continue;
			}
			max_shared_nodes = (int)ul;

		} else {
			sprintf(log_buffer, "unknown option %s", cptr->c_name);
			log_event(PBSEVENT_SYSTEM, 0, LOG_NOTICE, __func__, log_buffer);
		}
	}

	return;
}

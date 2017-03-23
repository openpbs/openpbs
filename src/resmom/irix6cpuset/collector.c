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

/**
 * @file	collector.c
 * @brief
 * Collect usage and resource information for Mom.  This functionality is
 * multi-threaded since the kernel interfaces used to grab this information
 * can block for long periods of time.
 */
#define _KMEMUSER		1	/* Allow access to more interfaces. */

#include "pbs_config.h"

#include <sys/types.h>
#include <sys/timers.h>
#include <sys/ckpt_procfs.h>
#include <sys/procfs.h>
#include <sys/syssgi.h>
#include <arraysvcs.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "mom_share.h"
#include "collector.h"
#include "log.h"
#include "session.h"

/* Starting brk() point from ../mom_main.c */
extern caddr_t	startbrk;

/* struct dso_info:
 *
 * Information for keeping track of "free" system libraries.
 */
typedef struct dso_info {
#ifdef  DEBUG
	char    *path;			/* Path to the shared object. */
#endif  /* DEBUG */
	dev_t   dev;			/* Device on which the dso resides. */
	ino_t   ino;			/* Inode for the shared object. */
} dso_info;

static dso_info	*dsos = NULL;
static int	ndsos = 0;
static dso_info	*unkdsos = NULL;
static int	nunkdsos = 0;

static size_t	pagesize = 0;

/* Forward declarations for static functions. */
static int	sample_loop(shared_block *, pid_t);
static int	sample_pid(pid_t, proc_info *);
static void     clear_dso_paths(void);
static int      get_dso_paths(char *file);
static int	sort_dev_ino(const void *, const void *);
static int	is_shared_lib(prmap_sgi_t *);
static int	is_rld_segment(prmap_sgi_t *);
static char	*prflags(ulong_t);
static long	tv_msdiff(struct timeval *, struct timeval *);

/**
 * @brief
 * 	start_collector()
 * 	Entry point for the resource collection routine.  This function fork()s
 * 	a child, which then runs the sample_loop() routine.  The parent returns
 * 	immediately.
 *
 * @param[in] secs - time for sleep if requested
 *
 * @return	pid_t
 * @retval	pid of the collector thread	success
 * @retval	-1				on error
 *
 */
pid_t
start_collector(int secs)
{
	pid_t	pid, parent;
	int		rc;

	parent = getpid();		/* This PID, parent of the soon-to-be child. */

	/*
	 * Fork a new process that will collect information about running
	 * processes for mom.
	 */
	pid = fork();

	if (pid == -1) {
		log_err(errno, __func__, "cannot fork collector process.");
		return -1;
	}

	/* If still in original process, return the child's PID to the caller. */
	if (pid != 0)
		return pid;

	/* ======================================================================
	 * This is the child.  Collector loop starts here.
	 */

#ifdef  SGI_SETPSARGS
	/*
	 * Change the psargs field of this process to a more useful string.
	 * This is a custom modification which is only cosmetic.  Ignore any
	 * error or result codes.
	 */
	(void)syssgi(SGI_SETPSARGS, COLLECTOR_NAME, strlen(COLLECTOR_NAME));

#endif  /* SGI_SETPSARGS */

	/* Close un-necessary file descriptors inherited from main mom. */
	(void)close_inherited();

	if (secs)
		sleep(secs);	/* Sleep if requested, then start the collector loop. */

	/*
	 * NAS-local hack for better control of memory usage.  In order to prevent
	 * commonly-used libraries from being loaded into a "compute" node's local
	 * memory, where it might remain indefinitely, the common system libraries
	 * are pre-loaded into the memory of the bottom few nodes.  Since these
	 * libraries are now "resident" and sharable, no one job will be charged
	 * for the memory they are consuming.  Each library will show up as a
	 * shared segment in the process' address space, so collect a list of
	 * the pre-loaded libraries to compare user segments against.
	 */
	(void)clear_dso_paths();

	/* Get a list of "free" -n32 and -64 shared libraries from the system. */
	if (get_dso_paths(DSO32_INDEX_PATH)) {
		log_err(-1, __func__, "Couldn't parse 32-bit DSO description file.");
		exit(1);
	}
	if (get_dso_paths(DSO64_INDEX_PATH)) {
		log_err(-1, __func__, "Couldn't parse 64-bit DSO description file.");
		exit(1);
	}

	/*
	 * Call main collector function.  This function constitutes the body
	 * of the collector process.
	 */
	rc = sample_loop(mom_shared, parent);

	/*
	 * sample_loop() should not return, except in exceptional circumstances.
	 * It normally calls exit() on its own.
	 */
	/* Request a cleanup of allocated memory. */
	(void)sample_pid(-1, NULL);

	exit(rc);

	/* NOTREACHED */
}

/**
 * @brief
 * 	sample_loop()
 * 	Looped function to collect sample data.  This function runs more-or-less
 * 	continuously, filling the non-current process array and swapping it into
 * 	place when no other code is looking at it.
 *
 * @param[in] share - pointer to shared_block structure indicating information which is shared by
 *			multiple threads running on mom
 * @param[in] parent - pid of parent
 *
 * @return	int
 * @retval	-1	error else shouldn return rather should be running continuosly.
 *
 */
static int
sample_loop(shared_block *share, pid_t parent)
{
	time_t		last_time = (time_t)0, now, tmptime;
	sidpidlist_t	*sidpids;

	int			i;
	pid_t		this_pid, this_sid, *temp_sidlist_data;
	int			numpids, pididx, nsids, sididx;
	proc_info		*pi, *pbase;
	metaarray		sidlist, *fill, *swap;
	struct sigaction	act;

	pagesize = sysconf(_SC_PAGESIZE);

	/* Reset signal actions for most to SIG_DFL */
	act.sa_flags   = 0;
	act.sa_handler = SIG_DFL;
	sigemptyset(&act.sa_mask);

	(void)sigaction(SIGCHLD, &act, NULL);
	(void)sigaction(SIGHUP,  &act, NULL);
	(void)sigaction(SIGINT,  &act, NULL);
	(void)sigaction(SIGTERM, &act, NULL);

	/* Reset signal mask */
	(void)sigprocmask(SIG_SETMASK, &act.sa_mask, NULL);

	/* Clear all fields of the sidlist metaarray and allocate some space. */
	memset(&sidlist, 0, sizeof(sidlist));
	sidlist.data = (pid_t *)malloc(sizeof(pid_t) * INITIAL_SID_SIZE);
	if (sidlist.data == NULL) {
		log_err(errno, __func__, "calloc(sidlist)");
		goto bail;
	}
	sidlist.slots = INITIAL_SID_SIZE;
	sidlist.size  = INITIAL_SID_SIZE * sizeof(pid_t);
	memset((void *)sidlist.data, 0, sidlist.size);

	/* Wait for mom to get started.  Make sure parent doesn't go away. */
	while (!share->do_collect) {
		sleep(1);
		if (getppid() != parent) {
			log_err(-1, __func__, "collector was orphaned waiting for mom!");
			errno = 0;
			goto bail;
		}
	}

	log_event(PBSEVENT_SYSTEM | PBSEVENT_FORCE , PBS_EVENTCLASS_SERVER,
		LOG_DEBUG, __func__, "mom rendezvous complete");

	/*
	 * The main loop in the collector.  After a sufficiently long time has
	 * passed, create an array of SID's from the jobs and tasks listed.
	 * Then create a list of process ID's from the sids and take a leisurely
	 * stroll through /proc, collecting information on each of the processes
	 * in the SIDs.  When the table of new information is complete, swap it
	 * with the old one.  Repeat as necessary.
	 */
	while (share->do_collect) {
		/*
		 * Simple rate-limiter.  This code is very expensive, and shouldn't
		 * be allowed to run at maximum warp speed.
		 */
		now = time(NULL);
		if (now - last_time < COLLECTOR_LOOP_INTERVAL) {
			/* Sleep until it's time to run another loop and try again. */

			for (i = COLLECTOR_LOOP_INTERVAL + last_time - now; i > 0; i--) {
				if (share->wakeup) {
					DBPRT(("%s: Mom posted wakeup\n", __func__));
					/* Jump into the actual inspection code. */
					goto restart;
				}
				if (getppid() != parent) {
					log_err(-1, __func__, "collector was orphaned while sleeping!");
					goto bail;
				}

				sleep(1);

			}
		}

restart:
		share->wakeup = 0;
		now = time(NULL);
		last_time = now;

		/*
		 * Make a copy of the active SIDs list from mom.  This allows any
		 * further activity in this process to block without affecting the
		 * rest of mom.
		 */
		ACQUIRE_LOCK(share->share_lock);

		/* If there's nothing to do, go back and sleep a while. */
		if (share->sessions.entries == 0) {
			RELEASE_LOCK(share->share_lock);
			continue;
		}

		while ((nsids = share->sessions.entries) > sidlist.slots) {
			RELEASE_LOCK(share->share_lock);
			/*
			 * Compute how large to make the array to hold these sids.
			 * Round up to the next largest INITIAL_SID_SIZE increment if
			 * necessary.
			 *
			 * This array is local to the collector process, so it does
			 * not need special treatment with regards to sharing with
			 * other processes.
			 */
			sididx = ROUND_UP_TO(INITIAL_SID_SIZE, nsids);

			sidlist.slots = sididx;
			sidlist.size  = sididx * sizeof(pid_t);

			/* Reallocate the new data information */
			temp_sidlist_data = (pid_t *)realloc(sidlist.data, sidlist.size);
			if (temp_sidlist_data == NULL) {
				log_err(errno, __func__, "realloc(sidlist)");
				goto bail;
			} else {
				sidlist.data = temp_sidlist_data;
			}

			ACQUIRE_LOCK(share->share_lock);
		}

		/*
		 * Now copy the shared SID list to our private copy and unlock the
		 * shared segment.
		 */
		memcpy(sidlist.data, share->sessions.data, sidlist.size);
		sidlist.entries = nsids;

		RELEASE_LOCK(share->share_lock);

		/*
		 * Find the "non-current" array and fill it with the PID's in question.
		 * Then go off and query the system for information about those PID's.
		 */
		fill = share->filling;

		/*
		 * Invalidate any previous contents of the metaarray (actually
		 * stamp is ignored, but clear it anyway.).
		 */
		fill->stamp	= 0;
		fill->entries	= 0;

		pbase = (proc_info *)fill->data;

		sidlist_cache_info(&sidlist);
		/*
		 * And fill the array with the appropriate PID/SID information.  On
		 * the last pass, the data in the array will actually be filled in.
		 */
		for (sididx = 0; sididx < sidlist.entries; sididx ++) {

			this_sid = ((pid_t *)sidlist.data)[sididx];

			/* Get a list of the pids associated with this SID. */
			sidpids = sidpidlist_get_from_cache(sididx);
			if (sidpids == NULL) {
#ifdef DEBUG
				(void)sprintf(log_buffer,
					"lookup failed for SID %d - skipping", this_sid);
				log_err(-1, __func__, log_buffer);
#endif
				continue;
			}

			if ((numpids = sidpids->numpids) == 0)
				continue;

			for (pididx = 0; pididx < numpids; pididx ++) {

				this_pid = sidpids->pids[pididx].pid;

				/*
				 * Create a new entry for each pid/SID pair.  Increment the
				 * current proc slot index, keeping a pointer to the current
				 * slot in 'pi'.
				 */
				pi = pbase + fill->entries ++;

				/* Does this entry fill the proc_info table? */
				if (fill->entries > fill->slots) {
					(void)sprintf(log_buffer,
						"ran out of slots (%d max) in filling array @0x%p",
						fill->slots, fill->data);
					log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER,
						LOG_INFO, __func__, log_buffer);

					break;	/* Ignore any remaining pid's in the list. */
				}

				/* Copy the SID and PID of this process into the slot. */
				pi->pr_sid	= this_sid;
				pi->pr_pid	= this_pid;
			}

			/*
			 * Were all pids entered in the table?  If not, the table is full.
			 * Don't bother with any more.
			 */
			if (pididx != numpids)
				break;
		}
		/* Free the SID cache list. */
		sidlist_cache_free();


		/* "This can't happen." but check for it anyway.  */
		tmptime = time(NULL);
		if ((tmptime - last_time) > COLLECTOR_LOOP_INTERVAL) {
			(void)sprintf(log_buffer,
				"Getting pids of session took too long (%d/%d secs) - recycling.",
				time(NULL) - last_time, COLLECTOR_LOOP_INTERVAL);
			log_err(-1, __func__, log_buffer);

			/* This sample run has already taken too long -- start over. */
			goto restart;
		}

		DBPRT(("%s: sampling started at %s", __func__, ctime(&tmptime)));

		fill->samplestart = time(0);
		/*
		 * Now go ask the system for more information about each PID and fill
		 * in the appropriate slot in the array.
		 */
		for (pididx = 0; pididx < fill->entries; pididx ++) {

			if (getppid() != parent) {
				log_err(-1, __func__, "collector was orphaned while collecting!");
				goto bail;
			}

			/* Find the slot in the new memory segment. */
			pi = pbase + pididx;

			this_pid = pi->pr_pid;

			if (sample_pid(this_pid, pi)) {
				if (errno != ENOENT && errno != ESRCH) {
					(void)sprintf(log_buffer, "sample_pid(%d) failed", this_pid);
					log_err(errno, __func__, log_buffer);
				}
				/*
				 * Flag this as an invalid entry, by setting a non-
				 * existent SID handle and pid.
				 */
				pi->pr_sid	= 0;
				pi->pr_pid	= 0;
			}
			DBPRT(("%s: pid %d has vmem %lu, mem %lu\n", __func__, this_pid,
				pi->vmem, pi->mem));

			/* Has too much time elapsed for this iteration? */
			if ((time(NULL) - last_time) > COLLECTOR_LOOP_INTERVAL) {
				(void)sprintf(log_buffer,
					"timed out while querying pid %d (%d/%d secs), %d of %d "
					"pids queried (%d%% done)",
					this_pid, time(NULL) - last_time, COLLECTOR_LOOP_INTERVAL,
					pididx, fill->entries, (pididx * 100) / fill->entries);
				log_err(-1, __func__, log_buffer);

				/* This sample run took too long -- start over. */
				goto restart;
			}
		}
		fill->samplestop = time(0);

		DBPRT(("%s: Poll complete.  Swapping in new table 0x%p\n", __func__, fill));

		/*
		 * Swap in the new array to replace the old one.  This must be done
		 * while no other process is accessing the information, so get the
		 * lock first.
		 */
		ACQUIRE_LOCK(share->pinfo_lock);

		/* Invalidate the timestamp on the now-obsolete "current" array. */
		share->current->stamp = (time_t)0;

		/* Swap the current pointer to point at the "other" array. */
		swap    = share->current;
		share->current = share->filling;
		share->filling = swap;

		/* Set the timestamp on the new "current" array. */
		share->current->stamp = time(NULL);

		RELEASE_LOCK(share->pinfo_lock);

		tmptime = time(NULL);
		DBPRT(("%s: DONE at %s\n", __func__, ctime(&tmptime)));

	}

	DBPRT(("%s: Fell out of while(collect) loop.\n", __func__));

bail:
	log_err(-1, __func__, "Collector bailing out!");

	/*
	 * Let the master mom process clean up the shared segment.  Only the
	 * locally allocated data needs to be freed here.
	 */
	if (sidlist.data) {
		free(sidlist.data);
		memset(&sidlist, 0, sizeof(sidlist));
	}

	return -1;
}

/**
 * @brief
 *	sample_pid()
 * 	For a given PID, open the /proc/<pid> file and gather information about
 * 	the process.  Place it in the slot in the proc_info array pointed to by
 * 	slotp.  Pass it a '-1' PID to clean up the space allocated for the map.
 *
 * @param[in] pid - input process id
 * @param[out] slotp - pointer to proc_info to hold input pid info
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	failure
 *
 */
static int
sample_pid(pid_t pid, proc_info *slotp)
{
	char		proc_path[128];
	int			fd;
	prmap_sgi_arg_t	maparg;
	int			got, i, is_sproc, refcnt;
	prpsinfo_t		psinfo;
	ckpt_psi_t		psckpt;
	prmap_sgi_t		*mp;
	size_t		memused;
	struct timeval	finish;

	static prmap_sgi_t	*map = NULL, *temp_map = NULL;
	static size_t	mapsize;
	static int		num_map;
	/*
	 * Provide a "cleanup" interface for this routine, since the map might
	 * grow to be quite large.  If the pid is -1, just clean up the map and
	 * return success.
	 */
	if (pid == ((pid_t) -1)) {

		DBPRT(("%s: CLEANUP", __func__));
		if (map != NULL) {
			DBPRT((" Map 0x%p size %ld", map, mapsize));
			free(map);
			map     = NULL;
			mapsize = 0;
			num_map = 0;
		}
		DBPRT((".\n"));

		return 0;
	}

	/*
	 * If it has not been already created, allocate some initial space for
	 * the memory mapping.  It will be grown as needed to hold the total
	 * segment map for a process.
	 */
	if (map == NULL) {
		mapsize = sizeof(prmap_sgi_t) * INITIAL_MAP_SIZE;

		if ((map = (prmap_sgi_t *)malloc(mapsize)) == NULL) {
			(void)sprintf(log_buffer, "malloc(%ld)", mapsize);
			log_err(errno, __func__, log_buffer);
			mapsize = 0;
			return -1;
		}
		num_map = INITIAL_MAP_SIZE;

		DBPRT(("%s: allocated %d-slot map (%ld bytes) at 0x%p\n", __func__, num_map,
			mapsize, map));
	}

	/* Note when this sample was started. */
	if (gettimeofday(&slotp->tv_sample)) {
		log_err(errno, __func__, "gettimeofday");
		return -1;
	}

	/***********************************************************************/
	/**   BEWARE: System calls on /proc/<pid> may block indefinitely!!!   **/
	/***********************************************************************/

	/*
	 * Attempt to open the /proc/<pid> path (not pinfo) for this process.
	 * This is only necessary to get the memory maps for this process, so
	 * ignore it if not enforcing memory.
	 */
	if (enforce_mem | enforce_vmem | enforce_pvmem) {
		/* Generate the pathname for this process' /proc/<pid> entry. */
		DBPRT(("%s: Query pid %d\n", __func__, pid));
		(void)sprintf(proc_path, "%s/%d", PROCFS_PATH, pid);
		fd = open(proc_path, O_RDONLY);
		if (fd < 0) {	/* open(2) returned an error -- ignore ENOENT */
			if (errno == ENOENT || errno == ESRCH)
				return 1;
			else {
				(void)sprintf(log_buffer, "%s: %s", proc_path, strerror(errno));
				log_err(errno, __func__, log_buffer);
			}
			return -1;
		}
	} else
		fd = 0;		/* Don't do any of the 'while(fd)' loop below. */

	/*
	 * Ask for a map of all the memory segments for this process.  Pass in
	 * a buffer that we hope is big enough.  If not, enlarge the buffer and
	 * try it again.  This will be expensive at first, but we should only
	 * have to do this a few times.  "We will eventually win the race."
	 *
	 * Overload the "fd" integer filedescriptor to be an "always" for the
	 * loop if the file was opened, or "never" if the file was not opened.
	 */

	got = 0;
	while (fd) {
		/* Set up the request with the current map pointer and size. */
		maparg.pr_vaddr = (caddr_t)map;
		maparg.pr_size = mapsize;

		/* Attempt the PIOCMAP_SGI ioctl. */
		if ((got = ioctl(fd, PIOCMAP_SGI, &maparg)) < 0) {
			if (errno == ENOENT || errno == ESRCH) {
				close(fd);
				return 1;
			} else {
				(void)sprintf(log_buffer, "PIOCMAP_SGI(%s)", proc_path);
				log_err(errno, __func__, log_buffer);
				close(fd);
				return -1;
			}
		}

		/* If the map buffer was large enough to hold all the info, break. */
		if (got < (num_map - 1))	/* last element set to all-0's */
			break;

		DBPRT(("%s: got full map (%d entries) - realloc\n", __func__, got));
		/* Need still more space -- reallocate a bigger map. */
		DBPRT(("%s: ioctl(PIOCMAP_SGI) map 0x%p size %ld (%d entries)\n", __func__,
			map, mapsize, num_map));
		temp_map = (prmap_sgi_t *)realloc(map, mapsize * 2);
		if (temp_map == NULL) {
			(void)sprintf(log_buffer,
				"couldn't grow PIOCMAP map to %d entries (%ld bytes)",
				num_map, mapsize);
			log_err(errno, __func__, log_buffer);
			close(fd);
			return -1;
		} else {
			map = temp_map;
		}

		/* The new map buffer is twice as big as before. */
		mapsize *= 2;
		num_map *= 2;
		DBPRT(("%s: new map %ld bytes (%d entries)\n", __func__, mapsize, num_map));
	}

	/*
	 * Ask for checkpointing information.  This is yet another undocumented
	 * kernel interface, but is necessary to discover if this process is a
	 * member of a sproc(2) share group.  If it is (i.e. psckpt->shref != 0),
	 * the refcnt given in the map segment information is 'n + 1', and must
	 * be adjusted accordingly.  See also below.
	 */

	is_sproc = 0;
	if (ioctl(fd, PIOCCKPTPSINFO, &psckpt) >= 0) {
		/* ps_shrefcnt is non-zero for sproc(2)'d processes. */
		is_sproc = psckpt.ps_shrefcnt;
	}

	if ((fd > 0) && (close(fd) != 0)) {
		(void)sprintf(log_buffer, "close(%s)", proc_path);
		log_err(errno, __func__, log_buffer);
		return -1;
	}

	/* Clear the resident/virtual shared memory values. */
	slotp->mem  = 0;
	slotp->vmem = 0;

	if (got > 0) {

		(void)sprintf(proc_path, "%s/%d", PINFO_PATH, pid);
		fd = open(proc_path, O_RDONLY);
		ioctl(fd, PIOCPSINFO, &psinfo);
		close(fd);

		DBPRT(("%s: %srocess %d [%s] has %d segs:\n", __func__,
			is_sproc ? "sproc(2) p" : "P", pid, psinfo.pr_fname, got));

		/* Walk the segment map, adding up memory usage for each mapping. */
		for (mp = map, i = 0; i < got; i++, mp++) {

			/* Compute memory usage for this segment. */
			memused = mp->pr_wsize * pagesize / MA_WSIZE_FRAC;

			/* XXX
			 * Processes in an sproc(2) process group have a refcount that
			 * is one more than the number of actual references to the seg.
			 * For instance, if there are 4 sproc(2)'d processes, this seg
			 * will have a refcnt of 5.  Adjust it by one if necessary in
			 * order to divide the "shares" correctly.
			 */
			refcnt = (int)(mp->pr_mflags >> MA_REFCNT_SHIFT);
			if (refcnt > 1 && is_sproc)
				refcnt --;

			DBPRT(("%s:   %d: ", __func__, i));

			/* Do not count mapped physical devices. */
			if (mp->pr_mflags & MA_PHYS) {
				DBPRT(("Physical device -- ignored.\n"));
				continue;
			}

			/*
			 * Ignore "system overhead" -- rld, shared system libs, etc.
			 * These are neither writable nor primary, but are shared.
			 */
			if ((mp->pr_mflags & (MA_WRITE|MA_PRIMARY|MA_SHARED)) == MA_SHARED) {

				if (is_rld_segment(mp))
					continue;

				if ((mp->pr_mflags & MA_EXEC) && is_shared_lib(mp))
					continue;
			}

			DBPRT(("0x%016p, vsize %lu, size %lu, wsize %lu, ref %d, dev %d, ino %lu (%s)\n",
				mp->pr_vaddr, mp->pr_vsize, mp->pr_size, mp->pr_wsize,
				refcnt, mp->pr_dev, mp->pr_ino, prflags(mp->pr_mflags)));

			/*
			 * Add in this process's "share" of the shared memory and physical
			 * memory.  Also track its entire virtual size.
			 */
			slotp->mem  += (memused / refcnt);
			slotp->vmem += mp->pr_size;		/* Virtual size */
		}
	}

	/* This information is needed for all but file and wallt enforcement */
	if (enforce_cput | enforce_pcput | enforce_cpupct |
		enforce_mem | enforce_vmem | enforce_pvmem) {
		/* Generate the pathname for this process' /proc/pinfo/<pid> entry. */
		(void)sprintf(proc_path, "%s/%d", PINFO_PATH, pid);

		/* Attempt to open the /proc/pinfo/<pid> path for this process. */
		if ((fd = open(proc_path, O_RDONLY)) < 0) {
			if (errno == ENOENT || errno == ESRCH)
				return 1;
			else {
				(void)sprintf(log_buffer, "open(%s)", proc_path);
				log_err(errno, __func__, log_buffer);
				return -1;
			}
		}

		/* Ask for ps-like information about this job. */
		if (ioctl(fd, PIOCPSINFO, &psinfo) == -1) {
			if (errno == ENOENT || errno == ESRCH)
				return 1;
			else {
				(void)sprintf(log_buffer, "PIOCPSINFO(%s)", proc_path);
				log_err(errno, __func__, log_buffer);
				return -1;
			}
		}

		if (close(fd)) {
			(void)sprintf(log_buffer, "close(%s)", proc_path);
			log_err(errno, __func__, log_buffer);
			return -1;
		}

		/* Fill in the proc_info fields from the returned values in psinfo. */
		slotp->pr_pid	= psinfo.pr_pid;
		slotp->pr_sid	= psinfo.pr_sid;
		slotp->pr_jid	= psinfo.pr_jid;
		slotp->pr_time	= psinfo.pr_time;
		slotp->pr_ctime	= psinfo.pr_ctime;
		slotp->pr_start	= psinfo.pr_start;
		slotp->pr_size	= psinfo.pr_size;
		slotp->pr_rss	= psinfo.pr_rssize;

		if (psinfo.pr_zomb)
			slotp->flags |= MOM_PROC_IS_ZOMBIE;
	}

	if (gettimeofday(&finish) == 0)
		slotp->elapsed = tv_msdiff(&slotp->tv_sample, &finish);
	else
		slotp->elapsed = 0;

	DBPRT(("%s: pid %d polled in %ld ms.\n", __func__, pid, slotp->elapsed));

	/* And it's done.  Return success. */

	return 0;
}

/* ======== Support functions for maintaining list of shared dso's ======== */

/**
 * @brief
 * 	get_dso_paths()
 * 	Create an array containing a device/inode pair for each of the pre-loaded
 * 	system libraries.
 *
 * @param[in] file - filename
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
static int
get_dso_paths(char file)
{
	FILE	*fp;
	int		line = 0, len, count;
	dev_t	dev;
	ino_t	ino;
	char	buffer[1024], *ptr, *remain;
	dso_info *temp_dsos = NULL;

	buffer[sizeof(buffer) - 1] = '\0';

	if ((fp = fopen(file, "r")) == NULL) {
#ifdef DEBUG
		(void)sprintf(log_buffer,
			"cannot read dso file %s -- shared objects may be charged "
			"to multiple processes.", file);
		log_err(errno, __func__, log_buffer);
#endif

		if (errno != ENOENT && errno != ESRCH)
			return 1;	/* Something went wrong. */

		return 0;		/* File doesn't exist.   Bad but not fatal. */
	}

	count = 0;

	/* Read file line-by-line.  Ignore comments and blank lines. */
	while (fgets(buffer, sizeof(buffer) - 1, fp) != NULL) {

		line ++;

		/* Check for overflow and/or strip trailing new line. */
		len = (int)strlen(buffer);

		if (len == (sizeof(buffer) - 1)) {
			(void)sprintf(log_buffer, "%s: line %d too long", file, line);
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_ALERT,
				__func__, log_buffer);
			fclose(fp);
			return 1;
		}

		if (buffer[len - 1] == '\n')
			buffer[len - 1] = '\0';

		if (ptr = strchr(buffer, '#')) {
			*ptr = '\0';	/* Toss '#' comments. */
		}

		/* Look for a device number on this line. */
		if ((ptr = strtok(buffer, " \t")) == NULL)
			continue;		/* No tokens on line -- ignore blank lines. */

		dev = (dev_t)strtoul(ptr, &remain, 0);
		if (*remain != '\0') {
			if (strlen(ptr) > 16)
				strcpy((ptr + 16), "...");	/* Shorten long lines. */
			(void)sprintf(log_buffer, "%s: bad device number '%s' at line %d",
				file, ptr, line);
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_ERR,
				__func__, log_buffer);
			continue;
		}

		/* Found a device number.  Look for the inode. */
		if ((ptr = strtok(NULL, " \t")) == NULL) {
			/* Device number specified, but no other tokens.  Error. */
			(void)sprintf(log_buffer, "%s: missing inode number at line %d",
				file, line);
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_ERR,
				__func__, log_buffer);
			continue;
		}

		ino = (ino_t)strtoul(ptr, &remain, 0);
		if (*remain != '\0') {
			if (strlen(ptr) > 16)
				strcpy((ptr + 16), "...");	/* Shorten long lines. */
			(void)sprintf(log_buffer, "%s: bad inode number '%s' at line %d",
				file, ptr, line);
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_ERR,
				__func__, log_buffer);
			continue;
		}

		/* Found dev and ino numbers.  Create a new entry in the dso list. */
		if ((temp_dsos = realloc(dsos, sizeof(dso_info) * (ndsos + 1))) == NULL) {
			ndsos = 0;
			log_err(errno, __func__, "realloc() failed");
			fclose(fp);
			return 1;
		} else {
			dsos = temp_dsos;
		}

		dsos[ndsos].dev	= dev;
		dsos[ndsos].ino	= ino;

#ifdef	DEBUG
		if ((ptr = strtok(NULL, " \t")) == NULL)
			dsos[ndsos].path	= NULL;
		else
			dsos[ndsos].path	= strdup(ptr);
#endif	/* DEBUG */

		ndsos ++;
		count ++;
	}
	fclose(fp);

	/* Sort the dso's in order of device and inode. */
	qsort((void *)dsos, ndsos, sizeof(dso_info), sort_dev_ino);

#ifdef DEBUG_LOTS
	for (line = 0; line < ndsos; line++) {
		(void)sprintf(log_buffer, " %d:  DSO %s (dev/ino %u/%lu)", line + 1,
			dsos[line].path ? dsos[line].path : "[???]",
			dsos[line].dev, dsos[line].ino);
		log_err(0, __func__, log_buffer);
	}
#endif /* DEBUG_LOTS */

	(void)sprintf(log_buffer, "Loaded %d DSO descriptors from %s (%d total)",
		count, file, ndsos);
	log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_INFO, __func__, log_buffer);

	return 0;
}

/**
 * @brief
 * 	clear_dso_paths()
 * 	Free any memory allocated for the lists of dynamic shared objects that were
 * 	pre-loaded at boot time.
 */
static void
clear_dso_paths(void)
{
#ifdef	DEBUG
	dso_info	*ptr;
	int		i;

	/*
	 * If debugging is enabled, the dso_info contains a pointer to the path
	 * of the shared object.  This storage needs to be freed individually.
	 */
	ptr = dsos;
	for (i = 0; i < ndsos; i++, ptr++) {
		if (ptr->path)
			free(ptr->path);
	}

	ptr = unkdsos;
	for (i = 0; i < nunkdsos; i++, ptr++) {
		if (ptr->path)
			free(ptr->path);
	}
#endif	/* DEBUG */

	if (dsos)
		free(dsos);
	dsos  = NULL;
	ndsos = 0;

	if (unkdsos)
		free(unkdsos);
	unkdsos  = NULL;
	nunkdsos = 0;

	return;
}

/**
 * @brief
 * 	sort_dev_ino()
 * 	qsort(3) comparison function to sort dso_info's first by device number,
 * 	then inode if dev is a tie.
 *
 * @param[in] p1 - pointer to dso info
 * @param[in] p2 - pointer to dso info
 *
 * @return	int
 * @retval	0	if no diff
 * @retval	-1	if diff <0
 *
 */
static int
sort_dev_ino(const void *p1, const void *p2)
{
	dso_info	*d1, *d2;
	long	diff;

	d1 = (dso_info *)p1;
	d2 = (dso_info *)p2;

	/* Compare first on device number, then on inode. */
	if (diff = ((long)d1->dev - (long)d2->dev))
		return (diff < 0 ? -1 : 1);

	if (diff = ((long)d1->ino - (long)d2->ino))
		return (diff < 0 ? -1 : 1);

	return 0;	/* No difference. */
}

/**
 * @brief
 * 	is_shared_lib()
 * 	Check the segment against the list of preloaded shared objects.  Do not
 * 	charge this process for the memory usage if the object is found in the list.
 *
 * @param[in] mp - pointer to map segment
 * 
 * @return	int
 * @retval	1	if the map segment is a preloaded shared library
 * @retval	0	otherwise
 *
 * @par Note:
 *	If this is the first encounter of this segment, it is logged.  The log can
 * 	be used to find libraries that are not being pre-loaded at boot time, but
 * 	which are being used by user applications.
 * 
 */
static int
is_shared_lib(prmap_sgi_t *mp)
{
	char	*ques = "[???]";
	dso_info	*d;
	int		i;
	FILE	*fp;
	time_t	now;
	char	dstr[32];
	dso_info  *temp_unkdsos = NULL;

	/* Attempt to look up the DSO in the list of system shared objects. */
	for (d = dsos, i = 0; i < ndsos; i++, d++) {
		if ((mp->pr_dev == d->dev) && (mp->pr_ino == d->ino)) {
			DBPRT(("%s (%d/%u) -- ignored.\n",
				d->path, d->dev, d->ino));
			return 1; /* Dev and inode match.  Object is a valid system DSO. */
		}
	}

	/*
	 * Object is a dso, but is not found in the "free" system dso's.  If
	 * it hasn't been seen before, make a note of it.
	 */

	for (d = unkdsos, i = 0; i < nunkdsos; i++, d++) {
		if ((mp->pr_dev == d->dev) && (mp->pr_ino == d->ino))
			/*
			 * Dev and inode match.  This object has been seen before.  Just
			 * return that it is not a valid system DSO.
			 */
			return 0;
	}

	/*
	 * Log that this is a new DSO.  This will help find "often used" libraries
	 * that should be pre-loaded.
	 */
	if (fp = fopen(DSO_UNKNOWN_LOG, "a+")) {
		now = time(NULL);
		(void)strcpy(dstr, ctime(&now));
		dstr[24] = '\0';
		(void)fprintf(fp,
			"%s: unknown dso dev %d inode %lu (%lu@0x%016p, flags %s)\n",
			dstr, mp->pr_dev, (int)mp->pr_ino, mp->pr_size, mp->pr_vaddr,
			prflags(mp->pr_mflags));

		fclose(fp);
	}

	/* Add the now-logged DSO to the list of recognized but not system DSOs. */
	temp_unkdsos = realloc(unkdsos, sizeof(dso_info) * (nunkdsos + 1));
	if (temp_unkdsos == NULL) {
		nunkdsos = 0;
		log_err(errno, __func__, "realloc() failed");
		return 0;
	} else {
		unkdsos = temp_unkdsos;
	}
	unkdsos[nunkdsos].dev	= mp->pr_dev;
	unkdsos[nunkdsos].ino	= mp->pr_ino;
#ifdef	DEBUG
	unkdsos[nunkdsos].path	= strdup(ques);
#endif	/* DEBUG */

	(void)sprintf(log_buffer,
		"added unknown dso %s (dev/ino %u/%lu)",
		ques, unkdsos[nunkdsos].dev, (int)unkdsos[nunkdsos].ino);
	log_err(-1, __func__, log_buffer);
	nunkdsos ++;

	return 0;
}

/**
 * @brief
 * 	is_rld_segment()
 * 	The IRIX run-time loader (rld(1)) text is mapped into each process' address
 * 	space.  Don't charge it against them.
 *
 * @param[in] mp - pointer to mapped segments
 *
 * @return	int
 * @retval	1	if this segment is the rld text segment
 * @retval	0	otherwise
 */
static int
is_rld_segment(prmap_sgi_t *mp)
{
	caddr_t	addr;

	addr  = mp->pr_vaddr;

	/* Ignore shared RLD text segment. */
	if (addr == (caddr_t) 0x0fb60000) {
		DBPRT(("RLD text segment -- ignored.\n"));
		return 1;	/* RLD Text segment */
	}

	/* Other segment. */
	return 0;
}

/**
 * @brief
 *	returns the string value for flag as map segment info.
 *
 * @param[in] flag - flag val indicating
 *
 * @return	string
 * @retval	string val for flag	success
 * @rteval	NULL			error
 *
 */
static char *
prflags(ulong_t flags)
{
	static char str[256];

	str[0] = '\0';
	str[1] = '\0';

	if (flags & MA_READ)	strcat(str, " READ");
	if (flags & MA_WRITE)	strcat(str, " WRITE");
	if (flags & MA_EXEC)	strcat(str, " EXEC");
	if (flags & MA_SHARED)	strcat(str, " SHARED");
	if (flags & MA_BREAK)	strcat(str, " BREAK");
	if (flags & MA_STACK)	strcat(str, " STACK");
	if (flags & MA_PHYS)	strcat(str, " PHYS");
	if (flags & MA_PRIMARY)	strcat(str, " PRIMARY");
	if (flags & MA_COW)		strcat(str, " COW");
	if (flags & MA_NOTCACHED)	strcat(str, " NOTCACHED");
	if (flags & MA_SHMEM)	strcat(str, " SHMEM");

	return &str[1];	/* Strip leading ' ' character. */
}

/**
 * @brief
 * 	tv_msdiff()
 * 	Return the difference, in milliseconds, between the time represented by
 * 	two timevals (finish - start).
 *
 * @param[in] start - timeval1
 * @param[in] finish - timeval2
 *
 * @return	long
 * @retval	diff between time values	success
 */
static long
tv_msdiff(struct timeval  *start, struct timeval  *finish)
{
	long		ds, dus;

	ds = finish->tv_sec - start->tv_sec;
	dus = finish->tv_usec - start->tv_usec;

	/* Normalize the resultant deltas so that dus is 0-999999. */
	while (dus < 0) {
		dus += 1000000;		/* Add a second's worth of usecs, */
		ds  -= 1;		/* and remove it from the seconds. */
	}
	while (dus > 999999) {
		dus -= 1000000;		/* Remove a second's worth of usecs, */
		ds  += 1;		/* and add it to the seconds. */
	}

	/* Generate the msecs from the secs and usecs and return it. */
	return (ds * 1000) + (dus / 1000);
}

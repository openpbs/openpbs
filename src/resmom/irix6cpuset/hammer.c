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

#include <sys/types.h>
#include <sys/procfs.h>
#include <sys/syssgi.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "mom_share.h"
#include "hammer.h"
#include "log.h"
/**
 * @file	hammer.c
 */
/* Starting brk() point from ../mom_main.c */
extern caddr_t	startbrk;

/* Lock to prevent hammering embryonic job processes. */
extern volatile pbs_mutex	*pbs_commit_ptr;

/* Forward declarations for static functions. */
static int	ascending_uid(const void *, const void *);

/**
 * @brief
 *	start_hammer() - Entry point for the unauthoized user hammer routine.  
 *	This function fork()s a child, which then runs the hammer_loop() routine.  
 *	The parent returns immediately.  The child will exit when the hammer_loop is killed.
 *
 * @param[in] secs - time in secs for halting hammer_loop
 *
 * @return	pid_t
 * @retval	-1 on error, 
 * @retval	otherwise the pid of the hammer thread.
 */
pid_t
start_hammer(int secs)
{
	char		*id = "start_hammer";
	pid_t		pid, parent;
	int			rc;

	parent = getpid();  /* PID that will parent the child */

	/*
	 * Fork a new process that will watch for user processes that are not
	 * controlled by mom.  These processes will be killed without mercy.
	 */
	pid = fork();

	if (pid == -1) {
		log_err(errno, id, "cannot fork hammer process.");
		return -1;
	}

	/* If still in original process, return the child's PID to the caller. */
	if (pid != 0)
		return pid;

	/* ======================================================================
	 * This is the child.  Hammer loop starts here.
	 */

#ifdef  SGI_SETPSARGS
	/*
	 * Change the psargs field of this process to a more useful string.
	 * This is a custom modification which is only cosmetic.  Ignore any
	 * error or result codes.
	 */
	(void)syssgi(SGI_SETPSARGS, HAMMER_NAME, strlen(HAMMER_NAME));

#endif  /* SGI_SETPSARGS */

	/* Close un-necessary file descriptors inherited from main mom. */
	(void)close_inherited();

	if (secs)
		sleep(secs);	/* Sleep if requested, then start the hammer loop. */

	rc = hammer_loop(mom_shared, parent);   /* Run hammer loop.  */

	/*
	 * hammer_loop() should not return, except in exceptional circumstances.
	 * It normally calls exit() on its own.
	 */
	exit(rc);

	/* NOTREACHED */
}

/**
 * @brief
 * 	hammer_loop()
 *
 * Periodically sweep through the process table looking for unauthorized
 * processes running on the system.  Unauthorized processes are those which
 * do not fit one of the following criteria:
 *
 * + Owned by a pr_uid that is a member of the PBS_EXEMPT_GROUP ("loginok").
 *
 * + Owned by a pr_gid equal to the PBS_EXEMPT_GROUP's (if PBS_EXEMPT_GROUP
 *   is defined and exists).
 *
 * + Owned by a pr_uid less than PBS_HAMMER_MINUID (1000).
 *
 * + Owned by either "guest" or "nobody" (if IGNORE_GUESTS is non-zero)
 *
 * + A member of a session group (pr_sid) that matches that of a running
 *   job's controlling shell.
 *
 * @param[in] share - pointer to shared_block structure
 *			which helps synchronize and share data btwn threads
 * @param[in] parent - parent pid

 * Note: that there is no warning shot, the process is immediately terminated.
 * Also note that, since qsub is not a member of the running job's session
 * id, qsub processes from a non-PBS-owned shell will be terminated,
 * regardless of whether the associated job is running or not.
 *
 * @return	int
 * @retval	-1	error
 *	
 */
int
hammer_loop(shared_block *share, pid_t parent)
{
	char		*id = "hammer_loop";
	time_t		last_time = (time_t)0, now;
	metaarray		sidlist;
	prpsinfo_t		psinfo;
	pid_t		this_pid, momsid;
	pid_t		*sids, temp_sidlist_data = NULL;
	int			i, first, nsids;
	int			fd;
	DIR			*dirhandle;
	struct dirent	*dirp;
	char		*fname;

#ifdef	PBS_EXEMPT_GROUP
	gid_t		exemptgid = 0;
	uid_t		*exempts  = NULL, *temp_exempts = NULL;
	int			nexempts  = 0;
#endif	/* PBS_EXEMPT_GROUP */

	int			ignore;
	struct passwd	*pwent;
	struct group	*grent;

#if	IGNORE_GUESTS != 0
	uid_t		guest, nobody;
#endif	/* IGNORE_GUESTS != 0 */

	struct sigaction	act;

	/* Reset signal actions for most to SIG_DFL */
	act.sa_flags	= 0;
	act.sa_handler	= SIG_DFL;
	sigemptyset(&act.sa_mask);

	(void)sigaction(SIGCHLD, &act, NULL);
	(void)sigaction(SIGHUP,  &act, NULL);
	(void)sigaction(SIGINT,  &act, NULL);
	(void)sigaction(SIGTERM, &act, NULL);

	/* Reset signal mask */
	(void)sigprocmask(SIG_SETMASK, &act.sa_mask, NULL);

	/* Change working directory to the pinfo dir, and open a handle on it. */
	if (chdir(PROC_PINFO_PATH) || ((dirhandle = opendir(".")) == NULL)) {
		log_err(errno, id, PROC_PINFO_PATH);
		return -1;
	}

	/*
	 * Allocate some space for the session id list (sidlist).  Track it with
	 * a metaarray struct (c.f. mom_share.h).
	 */
	(void)memset((void *)&sidlist, 0, sizeof(sidlist));
	sidlist.data = (pid_t *)malloc(sizeof(pid_t) * HAMMER_SIDLIST_SZ);
	if (sidlist.data == NULL) {
		log_err(errno, id, "malloc(sidlist)");
		goto bail;
	}

	momsid = getsid((pid_t)0);	/* Find out what sid mom helpers will run in. */

	sidlist.slots = HAMMER_SIDLIST_SZ;
	sidlist.size  = HAMMER_SIDLIST_SZ * sizeof(pid_t);
	(void)memset((void *)sidlist.data, 0, sidlist.size);

	first = 1;		/* First run. */

	for (; ;) {	/* LOOP FOREVER */
		/*
		 * Simple rate limiter.  Don't do the hammer loop more than once in
		 * a HAMMER_LOOP_INTERVAL time period.  Watch out that the main mom
		 * doesn't orphan this code.
		 */
		now = time(NULL);
		if (now - last_time < HAMMER_LOOP_INTERVAL) {
			for (i = HAMMER_LOOP_INTERVAL + last_time - now; i > 0; i--) {
				if (getppid() != parent) {
					log_err(-1, id, "hammer was orphaned while sleeping!");
					errno = 0;
					goto bail;
				}

				sleep(1);
			}
		}

		/* Time for a new run.  Make a note of when this one starts. */
		last_time = now;

#if     IGNORE_GUESTS != 0
		/* Find out who "guest" and "nobody" are. */
		if (pwent = getpwnam("guest"))
			guest = pwent->pw_uid;
		else
			guest = 0;
		if (pwent = getpwnam("nobody"))
			nobody = pwent->pw_uid;
		else
			nobody = 0;
#endif  /* IGNORE_GUESTS */

#ifdef  PBS_EXEMPT_GROUP
		/*
		 * Convert the named group into an array of UID's that are defined to
		 * be exempt from being hammered.  While this is not exactly cheap,
		 * it isn't expensive enough to warrant special signal handlers or
		 * whatever, and that stuff is a pain from an administrative point of
		 * view.  If the group doesn't exist, clear the exempt list.
		 */
		if ((grent = getgrnam(PBS_EXEMPT_GROUP)) == NULL) {

			/* Empty the exemption list. */
			if (exempts)
				free(exempts);
			exempts = NULL;
			nexempts = 0;

			/* Log (once only) the fact that the group is bogus. */
			if (first) {
				(void)sprintf(log_buffer,
					"cannot find hammer exempt group '%s'", PBS_EXEMPT_GROUP);
				log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_NOTICE,
					id, log_buffer);
				first = 0;
			}

		} else {
			/* Valid group.  Convert to exempts list. */

			for (i = 0; grent->gr_mem[i] != NULL; i++)
				/* Count how many elements are in the members array. */ ;

			/* Track the exempt group gid. */
			exemptgid = grent->gr_gid;

			/* Reallocate space if necessary to hold all members. */
			if (nexempts < i) {

				temp_exempts = (uid_t *)realloc((void *)exempts, sizeof(uid_t) * i);
				if (temp_exempts == NULL) {
					(void)sprintf(log_buffer,
						"realloc exempt list (%llu bytes)", (unsigned long long)sizeof(uid_t) * i);
					log_err(errno, id, log_buffer);
					/* Try again next iteration. */
					continue;
				} else {
					exempts = temp_exempts;
				}
			}
			nexempts = 0;

			/*
			 * Now look up each member of the group in the password database,
			 * and store their uid in the array.  If they don't exist, just
			 * ignore it for now.
			 */
			if (first)
				sprintf(log_buffer, "Exempt group %s: uids ", PBS_EXEMPT_GROUP);

			for (i = 0; grent->gr_mem[i] != NULL; i++) {
				if ((pwent = getpwnam(grent->gr_mem[i])) == NULL)
					continue;

				/* Record the uid in the nexempts array. */
				exempts[nexempts++] = pwent->pw_uid;

				if (first) {
					strcat(log_buffer, grent->gr_mem[i]);
					strcat(log_buffer, ",");
				}
			}

			if (first) {
				first = 0;
				log_buffer[strlen(log_buffer) - 1] = '.';
				log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_INFO, id,
					log_buffer);
			}

			/* And sort the resulting array in ascending order. */
			qsort(exempts, nexempts, sizeof(uid_t), ascending_uid);
		}
#endif  /* PBS_EXEMPT_GROUP */

		/* Get a list of sessions from the main mom thread. */

		/*
		 * Acquire a lock on job commits -- prevent new jobs from starting.
		 * This lock is held throughout the hammer loop to prevent new
		 * sessions from starting after the list of "valid" sessions is
		 * copied to this thread below.
		 *
		 * The test_and_set function used to implement pbs_mutex is (for
		 * some reason) declared to take an unsigned long *, not a volatile
		 * unsigned long *.  However, since it is implemented as inline
		 * assembly, the actual implementation doesn't use registers and
		 * operates directly on the memory.
		 *
		 * The cast is to make the compiler happy about passing a volatile
		 * to a function that doesn't take a volatile.
		 */
		ACQUIRE_LOCK(*(pbs_mutex *)pbs_commit_ptr);

		/* Acquire a lock on the shared session lists. */
		ACQUIRE_LOCK(share->share_lock);

		/* If there are more sessions than slots, allocate more space. */
		while ((nsids = share->sessions.entries) > sidlist.slots) {
			/*
			 * Don't hold the lock while we malloc -- we'll eventually get
			 * enough memory to hold the contents next time we lock.
			 */
			RELEASE_LOCK(share->share_lock);
			RELEASE_LOCK(*(pbs_mutex *)pbs_commit_ptr);

			temp_sidlist_data = (pid_t *)realloc(sidlist.data, sidlist.size * 2);
			if (temp_sidlist_data == NULL) {
				log_err(errno, id, "realloc(sidlist)");
				goto bail;
			} else {
				sidlist.data = temp_sidlist_data;
			}
			sidlist.slots *= 2;
			sidlist.size  *= 2;

			/*
			 * Now reacquire the locks and try again.  This leaves the locks
			 * set if the loop terminates.
			 */
			ACQUIRE_LOCK(*(pbs_mutex *)pbs_commit_ptr);
			ACQUIRE_LOCK(share->share_lock);
		}

		/* Now just copy out the sessions into the sidlist array. */
		memcpy(sidlist.data, share->sessions.data, nsids * sizeof(pid_t));
		sidlist.entries = nsids;

		/*
		 * And release the shared lock so others can use the data.  Still
		 * holding the pbs_commit_mtx lock!
		 */
		RELEASE_LOCK(share->share_lock);

		/* Now sort the sids in ascending order, for efficient lookups. */
		sids = sidlist.data;
		qsort(sids, nsids, sizeof(pid_t), ascending_uid);

		/*
		 * Loop through the pinfo directory, looking up each pid to see if it
		 * should be hammered.  This is a bit tricky, since there are a few
		 * special cases.  Specifically, do *not* hammer root processes!
		 */
		rewinddir(dirhandle);
		while ((dirp = readdir(dirhandle)) != NULL) {
			fname = dirp->d_name;

			/* Ignore non-numeric files/directories. */
			if (*fname < '0' || *fname > '9')
				continue;

			/*
			 * It's possible that the process will go away at any time.  Be
			 * prepared to handle ENOENT properly.
			 */
			if ((fd = open(fname, O_RDONLY)) < 0) {
				if (errno != ENOENT)
					log_err(errno, id, fname);	/* Real error -- log it. */

				continue;
			}

			if (ioctl(fd, PIOCPSINFO, (void *)&psinfo)) {
				if (errno != ENOENT)
					log_err(errno, id, fname);	/* Real error -- log it. */

				(void)close(fd);
				fd = -1;		/* Avoid confusion later. */

				continue;
			}

			(void)close(fd);
			fd = -1;			/* Avoid confusion later. */

			/* Now we have all of the information needed to decide. */

			/* IGNORE any process owned by root (or root group). */
			if (psinfo.pr_uid == 0 || psinfo.pr_gid == 0)
				continue;

			/* IGNORE zombies -- signalling them is, at best, useless. */
			if (psinfo.pr_zomb)
				continue;

			DBPRT(("%s: process %d parent %d owner %d/%d [%s]\n", id,
				psinfo.pr_pid, psinfo.pr_ppid,
				psinfo.pr_uid, psinfo.pr_gid, psinfo.pr_fname));

			/*
			 * Was this process spawned directly by mom (i.e. in same session)?
			 * If so, it is a helper process (i.e. rcp(1)) spawned on behalf
			 * of the user by the main mom.  In this case, it must be allowed
			 * to succeed.  Users get angry when we kill these siblings.
			 */
			if (psinfo.pr_sid == momsid)
				continue;

#ifdef  PBS_HAMMER_MINUID
			/*
			 * Most sites choose not to allocate uid's below some number
			 * (typically 1000) to normal users.  This provides a cheap way
			 * to tell if the uid belongs to a person or a system account.
			 */
			if (psinfo.pr_uid < PBS_HAMMER_MINUID)
				continue;

#endif  /* PBS_HAMMER_MINUID */

#if     IGNORE_GUESTS != 0
			/*
			 * IGNORE any process owned by "guest" or "nobody".  If they
			 * don't exist, they will be '0' -- but that's okay, since uid
			 * zero was checked above.
			 */
			if (psinfo.pr_uid == guest || psinfo.pr_uid == nobody)
				continue;

#endif  /* IGNORE_GUESTS */

#ifdef  PBS_EXEMPT_GROUP
			/* IGNORE any process owned by exempt group or a member thereof. */
			if (psinfo.pr_gid == exemptgid)
				continue;

#ifdef DEBUG_LOTS
			DBPRT(("%s: Checking for exempts (%d exempt uids)\n", id, nexempts));
#endif /* DEBUG_LOTS */

			ignore = 0;
			for (i = 0; i < nexempts; i++) {

				/*
				 * Since uid's are sorted in ascending order, if this one is
				 * greater than the one for which we are searching, that's it.
				 * Otherwise, if it matches the uid, ignore it.
				 */

#ifdef DEBUG_LOTS
				DBPRT(("%s:  running pid %d uid %d exempt uid %d\n", id,
					psinfo.pr_pid, psinfo.pr_uid, exempts[i]));
#endif /* DEBUG_LOTS */

				if (psinfo.pr_uid > exempts[i])
					continue;

				if (psinfo.pr_uid == exempts[i])
					ignore ++;

				/*
				 * Nothing left to do for this uid -- either exempt or we're
				 * not going to find it in the array.
				 */
				break;
			}

			/* Should it be ignored?  If so, continue on to the next pid. */
			if (ignore) {
#ifdef DEBUG_LOTS
				DBPRT(("%s: process %d owned by %d [%s] is exempt\n", id,
					psinfo.pr_pid, psinfo.pr_uid, psinfo.pr_fname));
#endif /* DEBUG_LOTS */

				continue;	/* Ignore this process -- it's exempt. */
			}

#endif  /* PBS_EXEMPT_GROUP */

			/*
			 * Check that it is not a member of a running session.  Use the
			 * same logic as above, since the sessions are sorted in ascending
			 * order as well.
			 */
			ignore = 0;
			for (i = 0; i < nsids; i++) {
				/*
				 * Since sid's are sorted in ascending order, if this one is
				 * greater than the one for which we are searching, that's it.
				 * Otherwise, if it matches a running sid, flag to ignore it.
				 */

#ifdef DEBUG_LOTS
				DBPRT(("%s:  running pid %d sid %d compare to session %d\n", id,
					psinfo.pr_pid, psinfo.pr_sid, sids[i]));
#endif /* DEBUG_LOTS */

				if (psinfo.pr_sid > sids[i])
					continue;

				if (psinfo.pr_sid == sids[i])
					ignore ++;

				/*
				 * Nothing left to do for this uid -- either exempt or we're
				 * not going to find it in the array.
				 */
				break;
			}

			/* Should it be ignored?  If so, continue on to the next pid. */
			if (ignore) {
#ifdef DEBUG_LOTS
				DBPRT(("%s: process %d owned by %d [%s] is exempt\n", id,
					psinfo.pr_pid, psinfo.pr_uid, psinfo.pr_fname));
#endif /* DEBUG_LOTS */

				continue;	/* Ignore this process -- exempt. */
			}

			/* Save a strtol() and just copy the pid out of the struct. */
			this_pid = psinfo.pr_pid;

			/*
			 * If we get this far, then this_pid is a user process that is not
			 * controlled by MOM.  Terminate it.
			 */
			pwent = getpwuid(psinfo.pr_uid);
			grent = getgrgid(psinfo.pr_gid);
			(void)sprintf(log_buffer,
				"%s non-PBS proc p/pp/sid %d/%d/%d %c, u/gid %s/%s [%s]",
				enforce_nokill ? "found" : "killed",
				this_pid, psinfo.pr_ppid, psinfo.pr_sid, psinfo.pr_sname,
				pwent ? pwent->pw_name : "???",
				grent ? grent->gr_name : "???",
				psinfo.pr_fname);
			DBPRT(("%s: %s\n", id, log_buffer));
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_NOTICE,
				id, log_buffer);
			if (!enforce_nokill)
				(void)kill(this_pid, SIGKILL);
		}

		/* Allow job changes to be committed. */
		RELEASE_LOCK(*(pbs_mutex *)pbs_commit_ptr);

		/* Continue with the infinite loop. */
	}
	/* NOTREACHED */

bail:
	if (fd > 0)
		close(fd);
	if (dirhandle != NULL)
		closedir(dirhandle);
	if (sidlist.data)
		free(sidlist.data);

	return -1;
}

/**
 * @brief
 * 	ascending_uid() - qsort(3) sort function to sort uid's into ascending order.
 *
 * @param[in] q1 - uid1
 * @param[in] q2 - uid2
 *
 * @return	int
 * @retval	diff btw uids
 */
static int
ascending_uid(const void *q1, const void *q2)
{
	int		i1, i2;

	i1 = (int)(*(uid_t *)q1);
	i2 = (int)(*(uid_t *)q2);

	return (i1 - i2);
}


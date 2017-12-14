/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
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
#include "session.h"
#include "log.h"

static metaarray cache_sidlist;
/**
 * @file	session.c
 */
/**
 * @brief
 * 	find_index: return the corresponding positional index number that
 *	corresponds to 'sid' in the metarray of session ids 'sesslist'.
 *
 * @param[in] sid - session id
 * @param[in] sesslist - metaarray of sessions
 *
 * @return	int
 * @retval	index	if found
 * @retval	-1 	if not found.
 */
static int
find_index(pid_t sid, metaarray *sesslist)
{
	int sididx;
	pid_t this_sid;

	for (sididx = 0; sididx < sesslist->entries; sididx ++) {

		this_sid = ((pid_t *)sesslist->data)[sididx];

		if (this_sid == sid)
			return (sididx);
	}
	return (-1);
}

/**
 * @brief
 * 	sidpidlist_add: adds a new (sid, pid) entry to the pid list represented by
 *	'pidlist_ptr'.
 *
 * @param[in] sid - session id
 * @param[in] pid - process id
 * @param[in] ppid - parent process id
 * @param[in] pidlist_ptr - pointer to pointer to sidpidlist_t structure
 *
 * @return	int
 * @retval	0 	for success, 
 * @retval	1 	for fail.
 */
static int
sidpidlist_add(pid_t sid, pid_t pid, pid_t ppid, sidpidlist_t **pidlist_ptr)
{
	pidinfo_t *pids_save;
	size_t	pidlist_size;
	sidpidlist_t  	*pidlist;
	pidinfo_t *temp_pidlist_pids = NULL;


	pidlist = *pidlist_ptr;

	/* sidpidlist was not created yet */
	if (pidlist == NULL) {
		pidlist = (sidpidlist_t *)malloc(sizeof(sidpidlist_t));
		if (pidlist == NULL) {
			log_err(errno, __func__, "malloc(pidlist)");
			return (1);
		}
		pidlist->sid = sid;
		pidlist->numpids = 0;
		pidlist->numslots = INITIAL_PIDLIST_SLOTS;
		pidlist_size = sizeof(pidinfo_t)*pidlist->numslots;
		pidlist->pids = (pidinfo_t *) malloc(pidlist_size);

		if (pidlist->pids == NULL) {
			log_err(errno, __func__, "calloc(pidlist->pids)");
			sidpidlist_free(pidlist);
			*pidlist_ptr = NULL;
			return (1);
		}

		memset((pid_t *)pidlist->pids, 0, pidlist_size);
	}

	pidlist->numpids++;

	if (pidlist->numpids > pidlist->numslots) {
		pidlist->numslots = \
			   ROUND_UP_TO(INITIAL_PIDLIST_SLOTS, pidlist->numpids);
		pids_save = pidlist->pids;
		temp_pidlist_pids = (pidinfo_t *) \
		 realloc(pidlist->pids,sizeof(pidinfo_t)*pidlist->numslots);

		if (temp_pidlist_pids == NULL) {
			log_err(errno, __func__, "realloc(pidlist->pids)");
			free(pids_save);
			sidpidlist_free(pidlist);
			*pidlist_ptr = NULL;
			return (1);
		} else {
			pidlist->pids = temp_pidlist_pids;
		}
	}
	pidlist->pids[pidlist->numpids-1].pid = pid;
	pidlist->pids[pidlist->numpids-1].ppid = ppid;

	*pidlist_ptr = pidlist;
	return (0);
}

/**
 * @brief
 * 	sidlist_cache_info: walks through PROC_PINFO_PATH and caches sid-to-pid
 * 	mappings.
 *
 * @param[in] input_sidlist - pointer to input session array
 *
 * @return	int
 * @retval	0 	if successfully cached information; 
 * @retval	1 	otherwise.
 * Note:    be sure to sidlist_cache_free() when info no longer needed.
 */
int
sidlist_cache_info(metaarray *input_sidlist)
{
	DIR		*dirhandle;
	struct dirent	*dirp;
	char    	*fname;
	int     	fd;
	prpsinfo_t  	psinfo;
	int		sid_idx;

	if (input_sidlist == NULL || input_sidlist->size == 0) {
		log_err(-1, __func__, "List of sessions given is empty!");
		return (0);
	}

	/* Change working directory to the pinfo dir, and open a handle on it. */
	if (chdir(PROC_PINFO_PATH) || ((dirhandle = opendir(".")) == NULL)) {
		log_err(errno, __func__, PROC_PINFO_PATH);
		return (1);
	}

	memset(&cache_sidlist, 0, sizeof(cache_sidlist));
	cache_sidlist.slots = input_sidlist->slots;
	cache_sidlist.size  =  sizeof(sidpidlist_t *) * cache_sidlist.slots;
	cache_sidlist.data = (sidpidlist_t **)malloc(cache_sidlist.size);
	if (cache_sidlist.data == NULL) {
		log_err(errno, __func__, "calloc(sidlist)");
		return (1);
	}

	cache_sidlist.entries = input_sidlist->entries;
	/* initialize sidlist */
	memset((void *)cache_sidlist.data, 0, cache_sidlist.size);

	/*
	 * Loop through the pinfo directory, looking up each pid to see if it
	 * is a member of sid. If so, add the pid to the pid list.
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
				log_err(errno, __func__, fname);  /* Real error */
			continue;
		}

		if (ioctl(fd, PIOCPSINFO, (void *)&psinfo)) {
			if (errno != ENOENT)
				log_err(errno, __func__, fname);  /* Real error */

			(void)close(fd);
			fd = -1;                /* Avoid confusion later. */

			continue;
		}

		(void)close(fd);
		fd = -1;                    /* Avoid confusion later. */

		/* Now we have all of the information needed to decide. */

		sid_idx = find_index(psinfo.pr_sid, input_sidlist);

		if (sid_idx >= 0) { /* found a slot */

			if (sidpidlist_add(psinfo.pr_sid, psinfo.pr_pid,
				psinfo.pr_ppid,
				&((sidpidlist_t **)cache_sidlist.data)[sid_idx]) != 0)
				return (1);

		}
	} /* while */

	if (dirhandle != NULL)
		closedir(dirhandle);
	return (0);
}

/**
 * @brief
 * 	sidlist_cache_free: frees up data allocated to cache_sidlist. 
 * 
 * @return	Void
 */
void
sidlist_cache_free(void)
{
	int		sididx;

	for (sididx = 0; sididx < cache_sidlist.entries; sididx ++) {
		sidpidlist_free(((sidpidlist_t **)cache_sidlist.data)[sididx]);
	}
	if (cache_sidlist.data) {
		free(cache_sidlist.data);
		memset(&cache_sidlist, 0, sizeof(cache_sidlist));
	}

}

/**
 * @brief
 * 	sidlist_cache_print: prints out the elements of cache_sidlist.
 *
 * @return	void
 */
void
sidlist_cache_print(void)
{
	int		sididx;

	for (sididx = 0; sididx < cache_sidlist.entries; sididx ++) {
		sidpidlist_print(((sidpidlist_t **)cache_sidlist.data)[sididx]);
		printf("entries=%d slots=%d size=%d\n",  cache_sidlist.entries,
			cache_sidlist.slots, (int)cache_sidlist.size);
	}
}


/**
 * @brief
 * 	sidpidlist_get_from_cache()
 *	Given a session id, sid, return the list of pids who are members of the
 * 	session. This does not walk through PROC_PINFO_PATH to get process
 * 	information; instead, it checks the internal cache_sidlist, created via a
 *	call to sidlist_cache_info(), for sid-to-pids mappings.
 *
 * @param[in] sid_idx - session id index
 *
 * @return 	structure handle
 * @retval	ponter to list of pids from session(sidpidlist_t)
 * 
 */

sidpidlist_t *
sidpidlist_get_from_cache(sid_idx)
int	sid_idx;
{
	return (((sidpidlist_t **)cache_sidlist.data)[sid_idx]);
}

/**
 * @brief
 *	sidpidlist_get()
 *	Given a session id, sid, walk through PROC_PINFO_PATH and return the list
 * 	of pids who are members of the session.
 *
 * @param[in] sid - session id
 *
 * @return 	structure handle
 * @retval	ponter to list of pids from session(sidpidlist_t)	success
 * @retval	NULL							error
 *
 * NOTE: Need to call sidpidlist_free() on the structure returned by this call
 *       when no longer needed.
 */

sidpidlist_t *
sidpidlist_get(pid_t sid)
{
	DIR		*dirhandle;
	struct dirent	*dirp;
	char    	*fname;
	int     	fd;
	prpsinfo_t  	psinfo;
	sidpidlist_t  	*pidlist = NULL;

	/* Change working directory to the pinfo dir, and open a handle on it. */
	if (chdir(PROC_PINFO_PATH) || ((dirhandle = opendir(".")) == NULL)) {
		log_err(errno, __func__, PROC_PINFO_PATH);
		return (NULL);
	}
	/*
	 * Loop through the pinfo directory, looking up each pid to see if it
	 * is a member of sid. If so, add the pid to the pid list.
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
				log_err(errno, __func__, fname);  /* Real error */
			continue;
		}

		if (ioctl(fd, PIOCPSINFO, (void *)&psinfo)) {
			if (errno != ENOENT)
				log_err(errno, __func__, fname);  /* Real error */

			(void)close(fd);
			fd = -1;                /* Avoid confusion later. */

			continue;
		}

		(void)close(fd);
		fd = -1;                    /* Avoid confusion later. */

		/* Now we have all of the information needed to decide. */

		if (psinfo.pr_sid == sid) {

			/* sidpidlist was not created yet */
			if (sidpidlist_add(sid, psinfo.pr_pid, psinfo.pr_ppid,
				&pidlist) != 0)
				return (NULL);
		}
	} /* while */

	if (dirhandle != NULL)
		closedir(dirhandle);
	return (pidlist);
}

/**
 * @brief
 * 	sidpidlist_free() Frees up malloc-ed areas of pidlist.
 *
 * @param[in] pidlist - pointer to process id list
 *
 * @return	Void
 *
 * NOTE: This should be called when structure returned by sidpidlist_get() is
 *       no longer needed.
 */

void
sidpidlist_free(pidlist)
sidpidlist_t  	*pidlist;
{

	if (pidlist != NULL) {
		if (pidlist->pids != NULL) {
			free(pidlist->pids);
			pidlist->pids = NULL;
		}
		free(pidlist);
		pidlist = NULL;
	}
}

/**
 * @brief
 * 	sidpidlist_print: prints out the values in the pidlist array. 
 *
 * @param[in] pointer to session id list
 *
 * @return	Void
 * 
 */
void
sidpidlist_print(sidpidlist_t *pidlist)
{
	int i;
	if (pidlist != NULL) {
		printf("sid=%d npids=%d nslots=%d: ", pidlist->sid,
			pidlist->numpids, pidlist->numslots);
		for (i=0; i < pidlist->numpids; i++) {
			printf("pid=%d ppid=%d", pidlist->pids[i].pid,
				pidlist->pids[i].ppid);
		}
		printf("\n");
	}
}

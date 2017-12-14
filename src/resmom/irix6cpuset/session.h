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
#ifndef	_SESSION_H
#define	_SESSION_H
#ifdef	__cplusplus
extern "C" {
#endif

/*
 * Path to the ps-info files in /proc.  Access to these files (as oppposed
 * to the full-blown /proc/<pid> files) is unrestricted and will not block.
 */
#define PROC_PINFO_PATH		"/proc/pinfo"

/* the initial array of pids size */
#define INITIAL_PIDLIST_SLOTS 256

typedef struct pidinfo {
	pid_t 	pid;
	pid_t	ppid;
} pidinfo_t;

typedef struct sidpidlist {
	pid_t   sid;
	int     numpids;        /* Number of elements in pid list */
	int     numslots;       /* Number of useable slots in pid list */
	pidinfo_t   *pids;          /* the pid list */
} sidpidlist_t;

/* Function declarations. */
sidpidlist_t *sidpidlist_get(pid_t);
sidpidlist_t *sidpidlist_get_from_cache(int);
void sidpidlist_free(sidpidlist_t *);
void sidpidlist_print(sidpidlist_t *);

int sidlist_cache_info(metaarray *);
void sidlist_cache_free(void);
void sidlist_cache_print(void);
#ifdef	__cplusplus
}
#endif
#endif /* _SESSION_H */

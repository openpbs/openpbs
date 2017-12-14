
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
#ifndef	_PBS_MUTEX_H
#define	_PBS_MUTEX_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * Definitions of mutual exclusion primitives used in multi-threaded parts
 * of the MOM code.
 *
 * This is currently only used in the SGI/irix6array case.
 */

#include <limits.h>

#define	PBS_MUTEX_SPIN				500

#if defined(__sgi)

#include <sys/types.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <mutex.h>
#include <string.h>

/* Size of the filename hunk of the mutex. */
#define	PBS_MUTEX_BUFFLEN	2048

typedef struct pbs_mutex {
	unsigned long	m;			/* The mutex itself */
	/* The source file and line of the last successful lock manipulator. */
	unsigned long	l;
	char		f[PBS_MUTEX_BUFFLEN + 1];
	pid_t		p;
	char		d;			/* Debug this mutex? */
} pbs_mutex;

#define	INIT_LOCK(mtx)     {						\
	(mtx).m = 0;							\
	(mtx).l = 0;							\
	(mtx).d = 0;							\
	(mtx).p = 0;							\
	(mtx).f[0] = (mtx).f[1] = (mtx).f[2] = '?';			\
	(mtx).f[3] = (mtx).f[PBS_MUTEX_BUFFLEN - 1] = '\0';		\
}

#define	FMT_PROCFS	"/proc/pinfo/%d"
#define	ACQUIRE_LOCK(mtx) {						\
	unsigned long	_spin;						\
	int		_fd, _err, _gotit = 0;				\
	char		_pname[256];					\
	while (!_gotit) {						\
	    for (_spin = PBS_MUTEX_SPIN; _spin; _spin--, usleep(10000))	\
		if (test_and_set((unsigned long*)&((mtx).m), 1) != 1) {	\
		    _gotit ++;						\
		    break;						\
		}							\
	    if (!_gotit && _spin == 0) {				\
		(void)sprintf(_pname, FMT_PROCFS, (mtx).p);		\
		_fd = open(_pname, O_RDONLY);				\
		_err = errno;						\
		(void)close(_fd);					\
		if (_fd >=0) {						\
		    (void)abort();					\
		} else if (_err != ENOENT) {				\
		    (void)abort();					\
		}							\
		/* re-initalize the lock and retry the acquisition. */	\
		INIT_LOCK(mtx);						\
	    }								\
	}								\
	(mtx).p = getpid();						\
	if ((mtx).d) {							\
	    (mtx).l = __LINE__;						\
	    (void)strncpy((char *)(mtx).f, __FILE__, PBS_MUTEX_BUFFLEN - 1); \
	}								\
}

#define	RELEASE_LOCK(mtx) {						\
	if (getpid() != (mtx).p) {					\
	    (void)abort();						\
	}								\
	test_and_set((unsigned long *)&((mtx).m), 0);			\
	if ((mtx).d) {							\
	    (mtx).l = __LINE__;						\
	    (void)strncpy((char *)(mtx).f, __FILE__, PBS_MUTEX_BUFFLEN - 1);	\
	}								\
}

#else	/* __sgi */

typedef unsigned int pbs_mutex;
#define	INIT_LOCK(mtxp)
#define	ACQUIRE_LOCK(mtxp)
#define	RELEASE_LOCK(mtxp)

#endif	/* __sgi */
#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_MUTEX_H */

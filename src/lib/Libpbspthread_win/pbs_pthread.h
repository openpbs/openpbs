/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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

/**
 * @file	pbs_pthread.h
 *
 * @brief	Pbs pthread wrapper functions header file
 *
 * @par		Functionality:
 *      This module provides an higher level abstraction of the
 *      pthread on windows
 *
 * @Warning
 *  CAUTION!!!!!: This is not a completely pthread/POSIX compliant. Right
 *  now only a few of the pthread functionality is implemented, and in ways
 *  that may not be completely POSIX compliant. For example, the only kind of
 *  mutex supported is PTHEAD_RECURSIVE (error-check, normal etc mutexes are
 *  not supported). The current PBS code uses only the RECURSIVE mutex.
 */

#include <windows.h>
#include <errno.h>

#ifndef _PBS_PTHREAD_H
#define	_PBS_PTHREAD_H

#ifdef	__cplusplus
extern "C" {
#endif


/** the opaque pthread_t. By POSIX, dont rely on the contents of pthread_t */
struct pthread_t {
	/** handle to the windows thread */
	HANDLE thHandle;
	/** the windows thread id */
	DWORD  thId;
};
typedef struct pthread_t pthread_t;


/* the pthread_attr_t - right now mostly unused */
struct pthread_attr_t {
	DWORD thAttr;
};
typedef struct pthread_attr_t pthread_attr_t;


/** the once control structure */
struct pthread_once_t {
	/** whether the once routine was called already */
	int done;
	/** whether the variable is initialized */
	int initialized;
};
typedef struct pthread_once_t pthread_once_t;
#define PTHREAD_ONCE_INIT {0, 1} /* static initialization of pthread once */


struct pthread_mutexattr_t {
	/** type of the mutex */
	int type;
	/** initialized or not? */
	int initialized;
};
typedef struct pthread_mutexattr_t pthread_mutexattr_t;
/* currently only PTHREAD_MUTEX_RECURSIVE is supported */
#define PTHREAD_MUTEX_RECURSIVE 1


/** the key structure to allocate a TLS index */
struct pthread_key_t {
	/** windows TLS index */
	DWORD hKey;
	/** user cleanup routine on thread destory */
	void (*usr_cleanup)(void *);
	/** initialized ? */
	int initialized;
};
typedef struct pthread_key_t pthread_key_t;


struct pthread_mutex_t {
	/** windows HANDLE to mutex */
	HANDLE hMutex;
	/** variable initialized */
	int initialized;
};
typedef struct pthread_mutex_t pthread_mutex_t;


typedef struct {
	pthread_key_t hKey;

	pthread_mutex_t hRmutex;
	long hReaders;

	pthread_mutex_t hWmutex;
	HANDLE hWriterWait;
} pthread_rwlock_t;

#define DllImport   __declspec(dllimport )
#define DllExport   __declspec(dllexport )

/* supported pthread api */

/* mutexattr related api */
DllExport int pthread_mutexattr_init(pthread_mutexattr_t *attr);
DllExport int pthread_mutexattr_destroy(pthread_mutexattr_t *attr);
DllExport int pthread_mutexattr_settype(pthread_mutexattr_t *attr, int type);


/* mutex related api */
DllExport int pthread_mutex_destroy(pthread_mutex_t *mutex);
DllExport int pthread_mutex_init(pthread_mutex_t *mutex, const pthread_mutexattr_t *attr);
DllExport int pthread_mutex_lock(pthread_mutex_t *mutex);
DllExport int pthread_mutex_unlock(pthread_mutex_t *mutex);


/* rwlock related api */
DllExport int pthread_rwlock_init(pthread_rwlock_t *l, void *opts);
DllExport int pthread_rwlock_destroy(pthread_rwlock_t *l);
DllExport int pthread_rwlock_rdlock(pthread_rwlock_t *l);
DllExport int pthread_rwlock_wrlock(pthread_rwlock_t *l);
DllExport int pthread_rwlock_unlock(pthread_rwlock_t *l);


/* pthread_once api */
DllExport  int pthread_once(pthread_once_t *once_control, void(*init_routine)(void));


/* TLS api */
DllExport  int pthread_key_create(pthread_key_t *__key, void (*destr_function)(void *));
DllExport  void *pthread_getspecific(pthread_key_t key);
DllExport  int pthread_setspecific(pthread_key_t key, const void *value);

/* create/join/id api */
DllExport  int
pthread_create(pthread_t * newthread,
	const pthread_attr_t *attr,
	void *(*start_routine)(void *),
	void *arg);
DllExport  int pthread_join(pthread_t th, void **thread_return);
DllExport pthread_t pthread_self(void);
DllExport int pthread_equal(pthread_t t1, pthread_t t2);
DllExport void pthread_exit(void *retval);


#ifdef	__cplusplus
}
#endif

#endif	/* _PBS__PTHREAD_H */

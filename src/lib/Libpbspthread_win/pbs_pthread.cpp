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

/**
 * @file	pbs_pthread.cpp
 *
 * @brief	Pbs pthread wrapper functions implementation
 *
 * @par		Functionality:
 *	This module provides an higher level abstraction of the
 *      pthread on windows
 *
 * @warning
 *  CAUTION!!!!!: This is not yet completely pthread/POSIX compliant. Right
 *  now only a few of the pthread functionality is implemented, and in ways
 *  that may not be completely POSIX compliant. For example, the only kind of
 *  mutex supported is PTHEAD_RECURSIVE (error-check, normal etc mutexes are
 *  not supported). The current PBS code uses only the RECURSIVE mutex.
 *  The header file pbs_pthread.h lists the currently implemneted functions.
 *
 */

#include "pbs_pthread.h"

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <process.h>


/** global TLS key to do some book-keeping */
DWORD ghMainTlsKey;
/** global mutex used in once function implementation */
HANDLE ghOnceMutex;


/**
 *  Whenever a client thread calls a pthread_setspecific, the key it uses is
 *  added to a linked list of keys used by that thread. The data is stored in
 *  the tls of the calling thread. All this is done to ensure that the user
 *  cleanup routine can be called when the thread detaches from the DLL
 */
struct tls_data {
	void (*usr_cleanup)(void *); /* the user cleanup routine to call */
	DWORD hKey;		      /* the windows TLS index */
	struct tls_data * next;	      /* pointer to the next node in the list */
};


/**
 * @brief
 *  Sets the TLSkey in a linked list headed by index ghMainTlsKey
 *
 * @par Functionality:
 *      1. Get a pointer to the TLS index of the current thread\n
 *      2. Checks whether key is already added to the linked list\n
 *      3. If not adds the key to the end of the linked list\n
 *
 * @param[in] key - the pthread key that is to be stored in the linked list
 *
 * @retval 0 - success
 * @retval -1 - failure
 *
 * @par Side effects:
 *      None
 */
int
setTlsKey(pthread_key_t key)
{
	struct tls_data * t = (struct tls_data *) TlsGetValue(ghMainTlsKey);
	struct tls_data * p = NULL;
	struct tls_data * np = NULL;
	while (t) {
		if (t->hKey == key.hKey)
			return 0;
		p = t;
		t = t->next;
	}
	np = (struct tls_data *) malloc(sizeof(struct tls_data));
	if (!np)
		return -1;

	np->next = 0;
	np->hKey = key.hKey;
	np->usr_cleanup = key.usr_cleanup;
	if (p == NULL) {
		p = np;
		if (TlsSetValue(ghMainTlsKey, p)==0)
			return -1;
	}
	else
		p->next = np;
	return 0;
}


/**
 * @brief
 *      Initialize the DLL global data on process attach
 *
 * @par Functionality:
 *      This function is called when a process attaches to this DLL\n
 *      1. Initializes the ghMainTlsKey TLS key\n
 *      2. Initializes the ghOnceMutex\n
 *
 *      called from the process_attach - so that its called only once
 *      per process
 *
 * @retval 0 - success
 * @retval ENOMEM - failure
 *
 * @par Side effects:
 *          None
 */
int
init_lib_data()
{
	/* create the main TLS for this library */
	if ((ghMainTlsKey = TlsAlloc()) == TLS_OUT_OF_INDEXES)
		return ENOMEM;

	ghOnceMutex = CreateMutex(
		NULL,			// default security descriptor
		FALSE,			// mutex owned
		NULL);			// object name

	if (ghOnceMutex == NULL) {
		exit(1);
		return ENOMEM;
	}
	return 0;
}

/**
 * @brief
 *      Destroy the per process global data on process exit
 *
 * @par Functionality:
 *      This function is called when a process detaches from this DLL\n
 *      1. Frees the TLS keys created by this thread\n
 *      2. Frees the ghMainTlsKey\n
 *      3. Closes the HANDLE to the ghOnceMutex.\n
 *
 *      called from the process_detach - so that its called only once
 *      per process
 *
 * @retval 0 - success
 * @retval ENOMEM - failure
 *
 * @par Side effects:
 *          None
 */
int
destroy_lib_data()
{
	struct tls_data * t = (struct tls_data *) TlsGetValue(ghMainTlsKey);
	while (t) {
		TlsFree(t->hKey);
		t = t->next;
	}
	TlsFree(ghMainTlsKey);
	CloseHandle(ghOnceMutex);
	return 0;
}



/**
 * @brief
 *      Destroys the thread specific data (keys etc) when the thread detaches
 *      from the DLL
 *
 * @par Functionality:
 *      This function is called when a thread detaches from this DLL\n
 *      1. Walk through the linked list of TLS keys of the thread\n
 *      2. Call the user_cleanup function if not null, and if TLS has
 *             any value set.\n
 *      3. Cleans up the linked list by freeing the nodes\n
 *
 *      called from the thread_detach - so that its called only once
 *      per thread
 *
 * @retval 0 - success
 * @retval ENOMEM - failure
 *
 * @par Side effects:
 *          None
 */
int
destroy_thread_data()
{
	LPVOID dt;
	struct tls_data * p;
	struct tls_data * t = (struct tls_data *) TlsGetValue(ghMainTlsKey);
	if (t == NULL)
		return 0;
	while (t) {
		if (t->usr_cleanup) {
			/* call user cleanup function */
			dt = TlsGetValue(t->hKey);
			TlsSetValue(t->hKey, NULL);
			if (dt) {
				t->usr_cleanup((void *) dt);
			}
		}
		p = t;
		t = t->next;
		/* free p */
		free(p);
	}
	return 0;
}

/**
 * @brief
 *      Implementation of pthread_mutexattr_init
 *
 * @par Functionality:
 *      Implements the pthread_mutexattr_init function \n
 *      1. Sets the initialized member to 1\n
 *      2. Sets the default attr type to PTHREAD_MUTEX_RECURSIVE\n
 *
 * @param[in] attr - the pthread_mutexattr_t variable to be initialized
 *
 * @retval 0 - success
 * @retval ENOMEM - failure
 *
 * @par Side effects:
 *          None
 */
int
pthread_mutexattr_init(pthread_mutexattr_t *attr)
{
	if (attr == NULL)
		return EINVAL;

	attr->initialized = 1;
	attr->type = PTHREAD_MUTEX_RECURSIVE;
	return 0;
}

/**
 * @brief
 *      Implementation of the pthread_mutexattr_destroy function
 *
 * @par Functionality:
 *      Implements the pthread_mutexattr_destroy function\n
 *      1. Sets the initialized member to 0\n
 *
 * @param[in] attr - the pthread_mutexattr_t variable to be destroyed
 *
 * @retval 0 - success
 * @retval ENOMEM - failure
 *
 * @par Side effects:
 *          None
 */
int
pthread_mutexattr_destroy(pthread_mutexattr_t *attr)
{
	if (attr == NULL)
		return EINVAL;

	attr->initialized = 0;
	return 0;
}

/**
 * @brief
 *      Implementation of the pthread_mutexattr_settype function
 *
 * @par Functionality:
 *      Implements the pthread_mutexattr_settype function\n
 *      1. Checks if mutexattr initialized\n
 *      2. If type is not PTHREAD_MUTEX_RECURSIVE return error\n
 *
 * @param[in] attr - the initialized pthread_mutexattr_t
 * @param[in] type - can only be PTHREAD_MUTEX_RECURSIVE
 *
 * @retval 0 - success
 * @retval ENOMEM - failure
 * @retval EINVAL - mutexattr type not PTHREAD_MUTEX_RECURSIVE
 *
 * @par Side effects:
 *          None
 */
int
pthread_mutexattr_settype(pthread_mutexattr_t *attr, int type)
{
	if (attr == NULL)
		return EINVAL;

	if (attr->initialized != 1)
		return EINVAL;

	if (type != PTHREAD_MUTEX_RECURSIVE)
		return EINVAL;

	return 0;
}

/**
 * @brief
 *      Implementation of the pthread_mutex_init function
 *
 * @par Functionality:
 *      Implements the pthread_mutex_init function\n
 *      1. Checks if mutexattr initialized, if provided\n
 *      2. Creates a windows Mutex object and stores the handle\n
 *
 * @param[in] mutex - the mutex variable to be initialized
 * @param[in] attr - the initialized pthread_mutex_attr_t variable
 *
 * @retval 0 - success
 * @retval ENOMEM - failure
 * @retval EINVAL - mutexattr type not PTHREAD_MUTEX_RECURSIVE
 *
 * @par Side effects:
 *          None
 */
int
pthread_mutex_init(pthread_mutex_t *mutex, const pthread_mutexattr_t *attr)
{
	HANDLE hMutex;

	if (mutex == NULL)
		return EINVAL;

	mutex->initialized = 0;

	if (attr != NULL) {
		if (attr->initialized != 1)
			return EINVAL;
		if (attr->type != PTHREAD_MUTEX_RECURSIVE)
			return EINVAL;
	}

	hMutex = CreateMutex(NULL, FALSE, NULL);
	if (hMutex == NULL)
		return ENOMEM;

	mutex->hMutex = hMutex;
	mutex->initialized = 1;

	return 0;
}

/**
 * @brief
 *      Implementation of the pthread_mutex_destroy function
 *
 * @par Functionality:
 *      Implements the pthread_mutex_destroy function\n
 *      1. Checks if mutex initialized\n
 *      2. Closes the HANDLE to the windows Mutex object\n
 *
 * @param[in] mutex - the initialized mutex to be destroyed
 *
 * @retval 0 - success
 * @retval EINVAL - mutex was not initialized
 *
 * @par Side effects:
 *          None
 */

int
pthread_mutex_destroy(pthread_mutex_t *mutex)
{
	if (mutex == NULL || mutex->initialized != 1)
		return EINVAL;

	CloseHandle(mutex->hMutex);
	mutex->initialized = 0;

	return 0;
}



/**
 * @brief
 *      Implementation of the pthread_mutex_lock function
 *
 * @par Functionality:
 *      Implements the pthread_mutex_lock function\n
 *      1. Checks if mutex initialized\n
 *      2. Calls waitforsingleobject to acquire the mutex
 *         in a blocking call (INFINITE timeout)\n
 *
 * @param[in] mutex - the initialized mutex to be locked
 *
 * @retval 0 - success
 * @retval EINVAL - mutex was not initialized
 * @retval EAGAIN - if mutex could not be acquired
 *                  caller must try again
 *
 * @par Side effects:
 *          None
 */
int
pthread_mutex_lock(pthread_mutex_t *mutex)
{
	DWORD dwWaitResult;

	if (mutex == NULL || mutex->initialized != 1)
		return EINVAL;

	dwWaitResult = WaitForSingleObject(mutex->hMutex, INFINITE);
	if (dwWaitResult == WAIT_OBJECT_0)
		return 0;

	return EAGAIN;
}

/**
 * @brief
 *      Implementation of the pthread_mutex_unlock function
 *
 * @par Functionality:
 *      Implements the pthread_mutex_unlock function\n
 *      1. Checks if mutex initialized\n
 *      2. Calls ReleaseMutex to release the mutex\n
 *
 *  \param[in] mutex - the initialized mutex to be unlocked
 *
 * @retval 0 - success
 * @retval EINVAL - mutex was not initialized
 * @retval EPERM - if mutex was not owned by caller
 *
 * @par Side effects:
 *          None
 */
int
pthread_mutex_unlock(pthread_mutex_t *mutex)
{
	if (mutex == NULL || mutex->initialized != 1)
		return EINVAL;

	if (ReleaseMutex(mutex->hMutex) == 0) {
		return EPERM;
	}
	return 0;
}


/**
 * @brief
 *      Implementation of the pthread_key_create function
 *
 * @par Functionality:
 *      Implements the pthread_key_create function\n
 *      1. Initializes the key variable and stores the user_cleanup function\n
 *      2. Calls TlsAlloc to allocate a TLS indes for threads in the process\n
 *      3. Stores the Tls Index in the key variable\n
 *
 * @param[in] key - the pthread_key_t variable to be initialized
 * @param[in] destr_function - the user defined cleanup function to be called
 *          on thread exit
 *
 * @retval 0 - success
 * @retval EINVAL - mutex was not initialized
 * @retval ENOMEM - No memory to allocate TLS index
 *
 * @par Side effects:
 *          None
 */
int
pthread_key_create(pthread_key_t *key, void (*destr_function)(void *))
{
	DWORD dwTlsIndex;

	/* create the tls key and register the destructor function */
	if (key == NULL)
		return EINVAL;

	key->initialized = 1;
	key->usr_cleanup = destr_function;
	if ((dwTlsIndex = TlsAlloc()) == TLS_OUT_OF_INDEXES) {
		return ENOMEM;
	}
	key->hKey = dwTlsIndex;

	return 0;
}


/**
 * @brief
 *      Implementation of the pthread_getspecific function
 *
 * @par Functionality:
 *      Implements the pthread_getspecific function\n
 *      1. Checks if key is initialize\n
 *      2. Calls TlsGetValue to get the value associated with key\n
 *
 * @param[in] key - the initialized key for which the index pointer is to be
 *                  fetched
 *
 * @retval 0 - success
 * @retval NULL - no data stored, or key invalid
 *
 * @par Side effects:
 *          None
 */
void *
pthread_getspecific(pthread_key_t key)
{
	LPVOID lpvData;

	if (key.initialized != 1)
		return NULL;

	lpvData = TlsGetValue(key.hKey);
	if ((lpvData == 0) && (GetLastError() != ERROR_SUCCESS))
		return NULL;

	return (void *) lpvData;
}

/**
 * @brief
 *      Implementation of the pthread_getspecific function
 *
 * @par Functionality:
 *      Implements the pthread_setspecific function\n
 *      1. Checks if key is initialized\n
 *      2. Calls TlsSetValue to store the value in TLS\n
 *      3. Calls setTlsKey to add key (if not already added)
 *          to the linked list pointed in the TLS entry indexed
 *          by the ghMainTlsIndex index\n
 *
 * @param[in] key - the initialized pthread_key_t variable
 * @param[in] value - the value to be set against the key
 *
 * @retval 0 - success
 * @retval ENOMEM - if out of memory while storing data
 * @retval EINVAL - bad parameters
 *
 * @par Side effects:
 *          None
 */
int
pthread_setspecific(pthread_key_t key, const void *value)
{
	if (key.initialized != 1)
		return EINVAL;

	if (TlsSetValue(key.hKey, (LPVOID) value) == 0)
		return ENOMEM;

	/* set the key pointer in the TLS of the thread */
	if (setTlsKey(key) != 0)
		return ENOMEM;

	return 0;
}

/**
 * @brief
 *      Implementation of the pthread_once function
 *
 * par Functionality:
 *      Implements the pthread_once function\n
 *      1. Checks if pOnce parameter is initialized\n
 *      2. Checks if init_routine is not null\n
 *      3. Allows only one thread to run the init_routine\n
 *      4. Blocks other threads on the ghOnceMutex till
 *         the thread doing the init_routine comes out of the init_routine.\n
 *
 * @param[in] pOnce - The intialized pthread_once_t variable
 * @param[in] init_routine - The routine to be called once
 *
 * @retval 0 - success
 * @retval EINVAL - bad parameters
 *
 * @par Side effects:
 *          None
 */
int
pthread_once(struct pthread_once_t * pOnce, void(*init_routine)(void))
{
	DWORD dwWaitResult;

	if (pOnce == NULL || init_routine == NULL) {
		return EINVAL;
	}
	if (!InterlockedExchangeAdd((LPLONG)&pOnce->done, 0)) {  /* MBR fence */
		dwWaitResult = WaitForSingleObject(ghOnceMutex, INFINITE);
		if (dwWaitResult == WAIT_OBJECT_0) {
			if (pOnce->done != 1) {
				(*init_routine)();
				pOnce->initialized = 1;
				InterlockedExchange((LPLONG) &pOnce->done, 1);/*MBR fence */
			}
			ReleaseMutex(ghOnceMutex);
		}
		else {
			return EINVAL;
		}
	}
	return  0;
}


/**
 * @brief Implementation of the pthread_create function
 *
 * @par Functionality:
 *      Implements the pthread_create function\n
 *      1. Checks if thread routine is not null\n
 *      2. Checks if thread var is not null\n
 *      3. Calls windows CreateThread to create the thread\n
 *      4. Stores the thread HANDLE into the pthread_t variable
 *          member thHandle, the id into thId\n
 *
 * @param[out] newthread - The pointer to which the thread id will be set
 * @param[in] attr - The initialzied attr for the new thread
 * @param[in] start_routine - The user defined function to run the thread on
 * @param[in] arg - Pointer to any user defined data to be consumed by the
 *                  thread function
 *
 * @retval 0 - success
 * @retval EINVAL - bad parameters
 * @retval ENOMEM - No memory to create thread
 *
 * @par Side effects:
 *          None
 */
int
pthread_create(pthread_t * newthread,
	const pthread_attr_t *attr,
	void *(*start_routine)(void *),
	void *arg)
{
	if (newthread == NULL || start_routine == NULL)
		return EINVAL;

	newthread->thHandle = CreateThread(
		NULL,			// default security attributes
		0,				// use default stack size
		(LPTHREAD_START_ROUTINE)
		start_routine,
		(LPVOID) arg,		// argument to thread function
		0,				// use default creation flags
		(LPDWORD) &(newthread->thId));// returns the thread identifier


	// Check the return value for success.
	// If CreateThread fails, terminate execution.
	// This will automatically clean up threads and memory.

	if (newthread->thHandle == NULL) {
		return ENOMEM;
	}
	return 0;
}



/**
 * @brief
 *      Implementation of the pthread_join function
 *
 * @par Functionality:
 *      Implements the pthread_join function\n
 *      1. Checks the handle for validity\n
 *      2. Calls waitforsingleobject to wait for the thread to complete\n
 *      3. Get the return code by calling GetExitCodeThread\n
 *      4. Closes the thread handle\n
 *      5. Passes the exit code in the thread_return parameter\n
 *
 * @param[in] th - Thread id of the thread to join on
 * @param[out] thread_return - The pointer to a location to which the thread
 *                              exit status is copied to.
 *
 * @retval 0 - success
 * @retval ENOMEM - if out of memory while storing data
 * @retval EINVAL - bad parameters
 *
 * @par Side effects:
 *          None
 */
int
pthread_join(pthread_t th, void **thread_return)
{
	DWORD exitcode=0;
	DWORD ret;

	if (th.thHandle == INVALID_HANDLE_VALUE)
		return EINVAL;

	if ((ret=WaitForSingleObject(th.thHandle, INFINITE))
		== WAIT_OBJECT_0) {
		if (thread_return) {
			if (GetExitCodeThread(th.thHandle,
				(LPDWORD) &exitcode) != 0) {
				*thread_return = (void *) exitcode;
			} else {
				*thread_return = NULL;
			}
			CloseHandle(th.thHandle);
		}
		return 0;
	} else {
		return EINVAL;
	}
}

/**
 * @brief
 *      Implementation of the pthead_self function
 *
 * @par Functionality:
 *      Implements the pthread_self function\n
 *      1. Calls GetCurrentThread & GetCurrenThreadId\n
 *      2. Populates a pthread_t variable and returns it\n
 *
 * @retval id of the thread (pthread_t)
 *
 * @par Side effects:
 *          None
 */
pthread_t
pthread_self(void)
{
	pthread_t thrd;
	thrd.thHandle = GetCurrentThread();
	thrd.thId = GetCurrentThreadId();
	return thrd;
}

/**
 * @brief
 *      Implementation of the pthead_equal function
 *
 * @par Functionality:
 *      Implements the pthread_equal function\n
 *      Compares two pthread_t objects
 *
 * @param[in] t1 - Thread 1
 * @param[in] t2 - Thread 2
 *
 * @retval - result of comparison
 * @return -  1 - Threads are equal
 * @return -  0 - Threads are not equal
 *
 * @par Side effects:
 *          None
 */
int
pthread_equal(pthread_t t1, pthread_t t2)
{
	if (t1.thId == t2.thId)
		return 1;

	return 0;
}

/**
 * @brief
 *      Implementation of the pthread_exit function
 *
 * @par Functionality:
 *      Implements the pthread_exit function by calling
 *      ExitThread
 *
 * @par Side effects:
 *          None
 */
void
pthread_exit(void *retval)
{
	/* Ignore the exitcode */
	ExitThread(0);
}

/**
 * @brief
 *      Implementation of pthread_rwlock_init
 *
 * @param[in] l    - The pthread_rwlock variable to initialize
 * @param[in] opts - Not used
 *
 * @par Functionality:
 *      Implements the pthread_rwlock_init function\n
 *      Calls CreateEvent, pthread_mutex\n
 *
 * @retval 0  - Success
 * @retval !0 - Failure
 *
 * @par Side effects:
 *          None
 */
int
pthread_rwlock_init(pthread_rwlock_t *l, void *opts)
{
	int rc;
	l->hReaders = 0;
	if ((rc = pthread_mutex_init(&l->hWmutex, NULL)) != 0)
		return rc;

	if ((rc = pthread_mutex_init(&l->hRmutex, NULL)) != 0)
		return rc;

	if ((l->hWriterWait = CreateEvent(NULL, TRUE, TRUE, NULL)) == NULL)
		return GetLastError();

	if ((rc = pthread_key_create(&l->hKey, NULL)) != 0)
		return rc;

	return 0;
}

/**
 * @brief
 *      Implementation of pthread_rwlock_destroy
 *
 * @param[in] l - The pthread_rwlock variable
 *
 * @par Functionality:
 *      Implements the pthread_rwlock_destroy function\n
 *
 * @retval 0  - Success
 * @retval !0 - Failure
 *
 * @par Side effects:
 *          None
 */
int
pthread_rwlock_destroy(pthread_rwlock_t *l)
{
	int rc;
	rc = WaitForSingleObject(l->hWriterWait, INFINITE);
	if (rc == WAIT_FAILED || rc == WAIT_ABANDONED)
		return -1;

	CloseHandle(l->hWriterWait);

	if (pthread_mutex_destroy(&l->hWmutex) != 0)
		return -1;

	if (pthread_mutex_destroy(&l->hRmutex) != 0)
		return -1;

	return 0;
}

/**
 * @brief
 *      Implementation of pthread_rwlock_rdlock
 *
 * @param[in] l - The pthread_rwlock to read lock
 *
 * @retval  0 - Success
 * @retval !0 - Failure
 *
 * @par Side effects:
 *          None
 */
int
pthread_rwlock_rdlock(pthread_rwlock_t *l)
{
	int *type = NULL;

	/* set the TLS variable to indicate read lock type */
	type = (int *) pthread_getspecific(l->hKey);
	if (type == NULL) {
		type = (int *) calloc(1, sizeof(int));
		if (!type)
			return -1;
		*type = 0; /* initialize to none */
		if (pthread_setspecific(l->hKey, type) != 0)
			return -1;
	}
	if (*type != 0)
		return -1;

	if (pthread_mutex_lock(&l->hWmutex) != 0)
		return -1;

	if (pthread_mutex_lock(&l->hRmutex) != 0)
		return -1;

	if (++l->hReaders == 1) {
		if (!ResetEvent(l->hWriterWait))
			return -1;
	}
	if (pthread_mutex_unlock(&l->hRmutex) != 0)
		return -1;

	if (pthread_mutex_unlock(&l->hWmutex) != 0)
		return -1;

	*type = 1; /* set to reader */

	return 0;
}

/**
 * @brief
 *      Implementation of pthread_rwlock_wrlock
 *
 * @param[in] l - The pthread_rwlock to write lock
 *
 * @retval  0 - Success
 * @retval !0 - Failure
 *
 * @par Side effects:
 *          None
 */
int
pthread_rwlock_wrlock(pthread_rwlock_t *l)
{
	int rc;
	int *type = NULL;

	/* set the TLS variable to indicate read lock type */
	type = (int *) pthread_getspecific(l->hKey);
	if (type == NULL) {
		type = (int *) calloc(1, sizeof(int));
		if (!type)
			return -1;
		*type = 0; /* initialize to none */
		if (pthread_setspecific(l->hKey, type) != 0)
			return -1;
	}
	if (*type != 0)
		return -1;

	if (pthread_mutex_lock(&l->hWmutex) != 0)
		return -1;

	rc = WaitForSingleObject(l->hWriterWait, INFINITE);
	if (rc == WAIT_FAILED || rc == WAIT_ABANDONED)
		return -1;

	*type = 2; /* set to writer */

	return 0;
}

/**
 * @brief
 *      Implementation of pthread_rwlock_unlock
 *
 * @param[in] l - The pthread_rwlock to unlock
 *
 * @retval  0 - Success
 * @retval !0 - Failure
 *
 * @par Side effects:
 *          None
 */
int
pthread_rwlock_unlock(pthread_rwlock_t *l)
{
	int *type = NULL;

	if ((type = (int *) pthread_getspecific(l->hKey)) == NULL)
		return -1;

	if (*type == 1) {
		if (pthread_mutex_lock(&l->hRmutex) != 0)
			return -1;

		if (--(l->hReaders) == 0) {
			if (!SetEvent(l->hWriterWait))
				return -1;
		}
		if (pthread_mutex_unlock(&l->hRmutex) != 0)
			return -1;

	} else if (*type == 2) {
		if (pthread_mutex_unlock(&l->hWmutex) != 0)
			return -1;
	} else
		return -1;

	*type = 0; /* unlocked */

	return 0;
}

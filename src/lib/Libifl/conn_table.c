/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of both the OpenPBS software ("OpenPBS")
 * and the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * OpenPBS is free software. You can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * OpenPBS is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * PBS Pro is commercially licensed software that shares a common core with
 * the OpenPBS software.  For a copy of the commercial license terms and
 * conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
 * Altair Legal Department.
 *
 * Altair's dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of OpenPBS and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair's trademarks, including but not limited to "PBS™",
 * "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
 * subject to Altair's trademark licensing policies.
 */

#include "pbs_config.h"
#include <errno.h>
#include "libpbs.h"

static pbs_conn_t **connection = NULL;
static int curr_connection_sz = 0;
static int allocated_connection = 0;

static pbs_conn_t *get_connection(int);
static int destroy_conntable(void);
static void _destroy_connection(int);
static int add_connection(int fd);

#ifdef WIN32
#define INVALID_SOCK(x) (x == INVALID_SOCKET || x < 0 || x >= PBS_LOCAL_CONNECTION)
#else
#define INVALID_SOCK(x) (x < 0 || x >= PBS_LOCAL_CONNECTION)
#endif

#if defined(linux)
#define MUTEX_TYPE PTHREAD_MUTEX_RECURSIVE_NP
#else
#define MUTEX_TYPE PTHREAD_MUTEX_RECURSIVE
#endif

#define LOCK_TABLE(x)                                               \
	do {                                                        \
		if (pbs_client_thread_init_thread_context() != 0) { \
			return (x);                                 \
		}                                                   \
		if (pbs_client_thread_lock_conntable() != 0) {      \
			return (x);                                 \
		}                                                   \
	} while (0)

#define UNLOCK_TABLE(x)                                          \
	do {                                                     \
		if (pbs_client_thread_unlock_conntable() != 0) { \
			return (x);                              \
		}                                                \
	} while (0)

/**
 * @brief
 * 	add_connection - Add given fd in connection table and initialize it's structures
 *
 * @note: connection table locking/unlocking should be handled by caller
 *
 * @param[in] fd - socket number
 *
 * @return int
 *
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
add_connection(int fd)
{
	pthread_mutexattr_t attr = {{0}};

	if (INVALID_SOCK(fd))
		return -1;

	if (fd >= curr_connection_sz) {
		void *p = NULL;
		int new_sz = fd + 10;
		p = realloc(connection, new_sz * sizeof(pbs_conn_t *));
		if (p == NULL)
			goto add_connection_err;
		connection = (pbs_conn_t **) (p);
		memset((connection + curr_connection_sz), 0, (new_sz - curr_connection_sz) * sizeof(pbs_conn_t *));
		curr_connection_sz = new_sz;
	}
	if (connection[fd] == NULL) {
		connection[fd] = calloc(1, sizeof(pbs_conn_t));
		if (connection[fd] == NULL)
			goto add_connection_err;
		if (pthread_mutexattr_init(&attr) != 0)
			goto add_connection_err;
		if (pthread_mutexattr_settype(&attr, MUTEX_TYPE) != 0)
			goto add_connection_err;
		if (pthread_mutex_init(&(connection[fd]->ch_mutex), &attr) != 0)
			goto add_connection_err;
		(void) pthread_mutexattr_destroy(&attr);
		allocated_connection++;
	} else {
		if (connection[fd]->ch_errtxt)
			free(connection[fd]->ch_errtxt);
		connection[fd]->ch_errtxt = NULL;
		connection[fd]->ch_errno = 0;
	}

	return 0;

add_connection_err:
	if (connection[fd]) {
		free(connection[fd]);
		connection[fd] = NULL;
	}
	return -1;
}

/** @brief
 *	_destroy_connection - destroy connection in connection table
 *
 * @param[in] fd - file descriptor
 *
 * @return void
 *
 */
static void
_destroy_connection(int fd)
{
	if (connection[fd]) {
		if (connection[fd]->ch_errtxt)
			free(connection[fd]->ch_errtxt);
		pthread_mutex_destroy(&(connection[fd]->ch_mutex));
		/*
		 * DON'T free connection[i]->ch_chan
		 * it should be done by dis_destroy_chan
		 */
		free(connection[fd]);
		allocated_connection--;
	}
	connection[fd] = NULL;
}

/** @brief
 * 	destroy_conntable - destroy connection table
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - failure
 *
 */
static int
destroy_conntable(void)
{
	int i = 0;

	if (curr_connection_sz <= 0)
		return 0;

	LOCK_TABLE(-1);
	for (i = 0; i < curr_connection_sz; i++) {
		if (connection[i]) {
			_destroy_connection(i);
		}
	}
	free(connection);
	connection = NULL;
	curr_connection_sz = 0;
	UNLOCK_TABLE(-1);

	return 0;
}

/** @brief
 *	destroy_connection - destroy connection in connection table
 *
 * @param[in] fd - file descriptor
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - failure
 *
 */
int
destroy_connection(int fd)
{
	if (INVALID_SOCK(fd))
		return -1;

	if (fd >= curr_connection_sz || allocated_connection == 0)
		return 0;

	LOCK_TABLE(-1);
	_destroy_connection(fd);
	UNLOCK_TABLE(-1);

	if (allocated_connection == 0)
		return destroy_conntable();

	return 0;
}

/**
 * @brief
 * 	get_connection - get associate connection structure with fd
 *
 * 	If given fd is not part of connection table or not initialized then
 * 	this func will call add_connection(fd) to add fd in connection
 * 	table and initialize it's structures
 *
 * @note: connection table locking/unlocking should be handled by caller
 *
 * @param[in] fd - socket number
 *
 * @return pbs_conn_t *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static pbs_conn_t *
get_connection(int fd)
{
	if (INVALID_SOCK(fd))
		return NULL;
	if ((fd >= curr_connection_sz) || (connection[fd] == NULL)) {
		if (add_connection(fd) != 0)
			return NULL;
	}
	return connection[fd];
}

/**
 * @brief
 * 	set_conn_errtxt - set connection error text synchronously
 *
 * @param[in] fd - socket number
 * @param[in] errtxt - error text to set on connection
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
set_conn_errtxt(int fd, const char *errtxt)
{
	pbs_conn_t *p = NULL;

	if (INVALID_SOCK(fd))
		return -1;

	LOCK_TABLE(-1);
	p = get_connection(fd);
	if (p == NULL) {
		UNLOCK_TABLE(-1);
		return -1;
	}
	if (p->ch_errtxt) {
		free(p->ch_errtxt);
		p->ch_errtxt = NULL;
	}
	if (errtxt) {
		if ((p->ch_errtxt = strdup(errtxt)) == NULL) {
			UNLOCK_TABLE(-1);
			return -1;
		}
	}
	UNLOCK_TABLE(-1);
	return 0;
}

/**
 * @brief
 * 	get_conn_errtxt - get connection error text synchronously
 *
 * @param[in] fd - socket number
 *
 * @return char *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 */
char *
get_conn_errtxt(int fd)
{
	pbs_conn_t *p = NULL;
	char *errtxt = NULL;

	if (INVALID_SOCK(fd))
		return NULL;

	LOCK_TABLE(NULL);
	p = get_connection(fd);
	if (p == NULL) {
		UNLOCK_TABLE(NULL);
		return NULL;
	}
	errtxt = p->ch_errtxt;
	UNLOCK_TABLE(NULL);
	return errtxt;
}

/**
 * @brief
 * 	set_conn_errno - set connection error number synchronously
 *
 * @param[in] fd - socket number
 * @param[in] err - error number to set on connection
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 */
int
set_conn_errno(int fd, int err)
{
	pbs_conn_t *p = NULL;

	if (INVALID_SOCK(fd))
		return -1;

	LOCK_TABLE(-1);
	p = get_connection(fd);
	if (p == NULL) {
		UNLOCK_TABLE(-1);
		return -1;
	}
	p->ch_errno = err;
	UNLOCK_TABLE(-1);
	return 0;
}

/**
 * @brief
 * 	get_conn_errno - get connection error number synchronously
 *
 * @param[in] fd - socket number
 *
 * @return int
 * @retval >= 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 */
int
get_conn_errno(int fd)
{
	pbs_conn_t *p = NULL;
	int err = -1;

	if (INVALID_SOCK(fd))
		return -1;

	LOCK_TABLE(-1);
	p = get_connection(fd);
	if (p == NULL) {
		UNLOCK_TABLE(-1);
		return -1;
	}
	err = p->ch_errno;
	UNLOCK_TABLE(-1);
	return err;
}

/**
 * @brief
 * 	set_conn_chan - set connection tcp chan synchronously
 *
 * @param[in] fd - socket number
 * @param[in] chan - tcp chan to set on connection
 *
 * @return int
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 */
int
set_conn_chan(int fd, pbs_tcp_chan_t *chan)
{
	pbs_conn_t *p = NULL;

	if (INVALID_SOCK(fd))
		return -1;

	LOCK_TABLE(-1);
	p = get_connection(fd);
	if (p == NULL) {
		errno = ENOTCONN;
		UNLOCK_TABLE(-1);
		return -1;
	}
	p->ch_chan = chan;
	UNLOCK_TABLE(-1);
	return 0;
}

/**
 * @brief
 * 	get_conn_chan - get connection tcp chan synchronously
 *
 * @param[in] fd - socket number
 *
 * @return pbs_tcp_chan_t *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 */
pbs_tcp_chan_t *
get_conn_chan(int fd)
{
	pbs_conn_t *p = NULL;
	pbs_tcp_chan_t *chan = NULL;

	if (INVALID_SOCK(fd))
		return NULL;

	LOCK_TABLE(NULL);
	p = get_connection(fd);
	if (p == NULL) {
		errno = ENOTCONN;
		UNLOCK_TABLE(NULL);
		return NULL;
	}
	chan = p->ch_chan;
	UNLOCK_TABLE(NULL);
	return chan;
}

/**
 * @brief
 * 	get_conn_mutex - get connection mutex synchronously
 *
 * @param[in] fd - socket number
 *
 * @return pthread_mutex_t *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
pthread_mutex_t *
get_conn_mutex(int fd)
{
	pbs_conn_t *p = NULL;
	pthread_mutex_t *mutex = NULL;

	if (INVALID_SOCK(fd))
		return NULL;

	LOCK_TABLE(NULL);
	p = get_connection(fd);
	if (p == NULL) {
		UNLOCK_TABLE(NULL);
		return NULL;
	}
	mutex = &(p->ch_mutex);
	UNLOCK_TABLE(NULL);
	return mutex;
}

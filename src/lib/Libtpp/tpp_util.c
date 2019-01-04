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
 * @file	tpp_util.c
 *
 * @brief	Miscellaneous utility routines used by the TPP library
 *
 *
 */
#include <pbs_config.h>
#if RWLOCK_SUPPORT == 2
#if !defined (_XOPEN_SOURCE)
#define _XOPEN_SOURCE 500
#endif
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <pthread.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#ifndef WIN32
#include <netinet/tcp.h>
#include <arpa/inet.h>
#endif
#include "avltree.h"
#include "pbs_error.h"

#include "rpp.h"
#include "tpp_common.h"
#include "tpp_platform.h"

#ifdef PBS_COMPRESSION_ENABLED
#include <zlib.h>
#endif

/*
 *	Global Variables
 */
int tpp_dbprt = 1; /* controls debug printing */

/* TLS data for each TPP thread */
static pthread_key_t tpp_key_tls;
static pthread_once_t tpp_once_ctrl = PTHREAD_ONCE_INIT; /* once ctrl to initialize tls key */

long tpp_log_event_mask = 0;

void (*tpp_log_func)(int level, const char *id, char *mess) = NULL;

/**
 * @brief
 *	Create a packet structure from the inputs provided
 *
 *
 * @param[in] - data - pointer to data buffer (if NULL provided, no copy happens)
 * @param[in] - len  - Lentgh of data buffer
 * @param[in] - mk_data - Make a copy of the data provided?
 *
 * @return Newly allocated packet structure
 * @retval NULL - Failure (Out of memory)
 * @retval !NULL - Address of allocated packet structure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
tpp_packet_t *
tpp_cr_pkt(void *data, int len, int mk_data)
{
	tpp_packet_t *pkt;

	if ((pkt = malloc(sizeof(tpp_packet_t))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating packet");
		return NULL;
	}
	if (mk_data == 0)
		pkt->data = data;
	else {
#ifdef DEBUG
		/* use calloc() to satisfy valgrind in debug mode */
		pkt->data = calloc(len, 1);
#else
		/* use malloc() in non-debug mode for performance */
		pkt->data = malloc(len);
#endif
		if (!pkt->data) {
			free(pkt);
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating packet data of %d bytes", len);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return NULL;
		}
		if (data)
			memcpy(pkt->data, data, len);
	}
	pkt->pos = pkt->data;
	pkt->extra_data = NULL;
	pkt->len = len;
	pkt->ref_count = 1;

	return pkt;
}

/**
 * @brief
 *	Free a packet structure
 *
 * @param[in] - pkt - Ptr to the packet to be freed.
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_free_pkt(tpp_packet_t *pkt)
{
	if (pkt) {
		pkt->ref_count--;

		if (pkt->ref_count <= 0) {
			if (pkt->data)
				free(pkt->data);
			if (pkt->extra_data)
				free(pkt->extra_data);
			free(pkt);
		}
	}
}

/**
 * @brief
 *	Mark a file descriptor as non-blocking
 *
 * @param[in] - fd - The file descriptor
 *
 * @return	Error code
 * @retval -1	Failure
 * @retval  0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_set_non_blocking(int fd)
{
	int flags;

	/* If they have O_NONBLOCK, use the Posix way to do it */
#if defined(O_NONBLOCK)
	if (-1 == (flags = fcntl(fd, F_GETFL, 0)))
		flags = 0;
	return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
#elif defined(WIN32)
	flags=1;
	if (ioctlsocket(fd, FIONBIO, &flags) == SOCKET_ERROR)
		return -1;
	return 0;
#else
	/* Otherwise, use the old way of doing it */
	flags = 1;
	return ioctl(fd, FIOBIO, &flags);
#endif
}

/**
 * @brief
 *	Mark a file descriptor with close on exec flag
 *
 * @param[in] - fd - The file descriptor
 *
 * @return	Error code
 * @retval -1	Failure
 * @retval  0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_set_close_on_exec(int fd)
{
#ifndef WIN32
	int flags;
	if ((flags = fcntl(fd, F_GETFD)) != -1)
		fcntl(fd, F_SETFD, flags | FD_CLOEXEC);
#endif
	return 0;
}

/**
 * @brief
 *	Mark a socket descriptor as keepalive
 *
 * @param[in] - fd - The socket descriptor
 *
 * @return	Error code
 * @retval -1	Failure
 * @retval  0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_set_keep_alive(int fd, struct tpp_config *cnf)
{
	int optval = 1;
	pbs_socklen_t optlen;

	if (cnf->tcp_keepalive == 0)
		return 0; /* not using keepalive, return success */

	optlen = sizeof(optval);

#ifdef SO_KEEPALIVE
	optval = cnf->tcp_keepalive;
	if (tpp_sock_setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, &optval, optlen) < 0) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "setsockopt(SO_KEEPALIVE) errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}
#endif

#ifdef TCP_KEEPIDLE
	optval = cnf->tcp_keep_idle;
	if (tpp_sock_setsockopt(fd, IPPROTO_TCP, TCP_KEEPIDLE, &optval, optlen) < 0) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "setsockopt(TCP_KEEPIDLE) errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}
#endif

#ifdef TCP_KEEPINTVL
	optval = cnf->tcp_keep_intvl;
	if (tpp_sock_setsockopt(fd, IPPROTO_TCP, TCP_KEEPINTVL, &optval, optlen) < 0) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "setsockopt(TCP_KEEPINTVL) errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}
#endif

#ifdef TCP_KEEPCNT
	optval = cnf->tcp_keep_probes;
	if (tpp_sock_setsockopt(fd, IPPROTO_TCP, TCP_KEEPCNT, &optval, optlen) < 0) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "setsockopt(TCP_KEEPCNT) errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}
#endif

	return 0;
}

/**
 * @brief
 *	Create a posix thread
 *
 * @param[in] - start_routine - The threads routine
 * @param[out] - id - The thread id is returned in this field
 * @param[in] - data - The ptr to be passed to the thread routine
 *
 * @return	Error code
 * @retval -1	Failure
 * @retval  0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_cr_thrd(void *(*start_routine)(void*), pthread_t *id, void *data)
{
	pthread_attr_t *attr = NULL;
	int rc = -1;
#ifndef WIN32
	pthread_attr_t setattr;
	size_t stack_size;

	attr = &setattr;
	if (pthread_attr_init(attr) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to initialize attribute");
		return -1;
	}
	if (pthread_attr_getstacksize(attr, &stack_size) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to get stack size of thread");
		return -1;
	} else	{
		if (stack_size < MIN_STACK_LIMIT) {
			if (pthread_attr_setstacksize(attr, MIN_STACK_LIMIT) != 0) {
				tpp_log_func(LOG_CRIT, __func__, "Failed to set stack size for thread");
				return -1;
			}
		} else {
			if (pthread_attr_setstacksize(attr, stack_size) != 0) {
				tpp_log_func(LOG_CRIT, __func__, "Failed to set stack size for thread");
				return -1;
			}
		}
	}
#endif
	if (pthread_create(id, attr, start_routine, data) == 0)
		rc = 0;

#ifndef WIN32
	if (pthread_attr_destroy(attr) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to destroy attribute");
		return -1;
	}
#endif 
	return rc;
}

/**
 * @brief
 *	Initialize a pthread mutex
 *
 * @param[in] - lock - A pthread mutex variable to initialize
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_init_lock(pthread_mutex_t *lock)
{
	pthread_mutexattr_t attr;
	int type;

	if (pthread_mutexattr_init(&attr) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to initialize mutex attr");
		exit(1);
	}
#if defined (linux)
	type = PTHREAD_MUTEX_RECURSIVE_NP;
#else
	type = PTHREAD_MUTEX_RECURSIVE;
#endif
	if (pthread_mutexattr_settype(&attr, type)) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to set mutex type");
		exit(1);
	}

	if (pthread_mutex_init(lock, &attr) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to initialize mutex");
		exit(1);
	}
}

/**
 * @brief
 *	Destroy a pthread mutex
 *
 * @param[in] - lock - The pthread mutex to destroy
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_destroy_lock(pthread_mutex_t *lock)
{
	if (pthread_mutex_destroy(lock) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to destroy mutex");
		exit(1);
	}
}

/**
 * @brief
 *	Acquire lock on a mutex
 *
 * @param[in] - lock - ptr to a mutex variable
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_lock(pthread_mutex_t *lock)
{
	if (pthread_mutex_lock(lock) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to lock mutex");
		exit(1);
	}
}

/**
 * @brief
 *	Release lock on a mutex
 *
 * @param[in] - lock - ptr to a mutex variable
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_unlock(pthread_mutex_t *lock)
{
	if (pthread_mutex_unlock(lock) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to unlock mutex");
		exit(1);
	}
}

/**
 * @brief
 *	Initialize a rw lock
 *
 * @param[in] - lock - A pthread rw variable to initialize
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_init_rwlock(void *lock)
{
	if (pthread_rwlock_init(lock, NULL) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to initialize rw lock");
		exit(1);
	}
}

/**
 * @brief
 *	Acquire read lock on a rw lock
 *
 * @param[in] - lock - ptr to a rw lock variable
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_rdlock_rwlock(void *lock)
{
	if (pthread_rwlock_rdlock(lock) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed in rdlock");
		exit(1);
	}
}

/**
 * @brief
 *	Acquire write lock on a rw lock
 *
 * @param[in] - lock - ptr to a rw lock variable
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_wrlock_rwlock(void *lock)
{
	if (pthread_rwlock_wrlock(lock) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to wrlock");
		exit(1);
	}
}

/**
 * @brief
 *	Unlock an rw lock
 *
 * @param[in] - lock - ptr to a rw lock variable
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_unlock_rwlock(void *lock)
{
	if (pthread_rwlock_unlock(lock) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to unlock rw lock");
		exit(1);
	}
}

/**
 * @brief
 *	Destroy a rw lock
 *
 * @param[in] - lock - The rw to destroy
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_destroy_rwlock(void *lock)
{
	if (pthread_rwlock_destroy(lock) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to destroy rw lock");
		exit(1);
	}
}

/**
 * @brief
 *	Parse a hostname:port format and break into host and port portions.
 *	If port is not available, set the default port to DEF_TPP_ROUTER_PORT.
 *
 * @param[in] - full - The full hostname (host:port)
 * @param[out] - port - The port extracted from the full hostname
 *
 * @return	hostname part
 * @retval NULL Failure
 * @retval !NULL hostname
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
char *
tpp_parse_hostname(char *full, int *port)
{
	char *p;
	char *host = NULL;

	*port = TPP_DEF_ROUTER_PORT;
	if ((host = strdup(full)) == NULL) 
		return NULL;

	if ((p = strstr(host, ":"))) {
		*p = '\0';
		*port = atol(p + 1);
	}
	return host;
}

/**
 * @brief
 *	Enqueue a node to a queue
 *
 * Linked List is from right to left
 * Insertion (tail) is at the right
 * and Deletion (head) is at left
 *
 * head ---> node ---> node ---> tail
 *
 * ---> Next points to right
 *
 * @param[in] - l - The address of the queue
 * @param[in] - data   - Data to be added as a node to the queue
 *
 * @return	The ptr to the newly created queue node
 * @retval	NULL - Failed to enqueue data (out of memory)
 * @retval	!NULL - Ptr to the newly created node
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
tpp_que_elem_t *
tpp_enque(tpp_que_t *l, void *data)
{
	tpp_que_elem_t *nd;

	if ((nd = malloc(sizeof(tpp_que_elem_t))) == NULL) {
		return NULL;
	}
	nd->queue_data = data;

	if (l->tail) {
		nd->prev = l->tail;
		nd->next = NULL;
		l->tail->next = nd;
		l->tail = nd;
	} else {
		l->tail = nd;
		l->head = nd;
		nd->next = NULL;
		nd->prev = NULL;
	}
	return nd;
}

/**
 * @brief
 *	De-queue (remove) a node from a queue
 *
 * Linked List is from right to left
 * Insertion (tail) is at the right
 * and Deletion (head) is at left
 *
 * head ---> node ---> node ---> tail
 *
 * ---> Next points to right
 *
 * @param[in] - l - The address of the queue
 *
 * @return	The ptr to the data from the node just removed from queue
 * @retval	NULL - Queue is empty
 * @retval	!NULL - Ptr to the data
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void *
tpp_deque(tpp_que_t *l)
{
	void *data = NULL;
	tpp_que_elem_t *p;
	if (l->head) {
		data = l->head->queue_data;
		p = l->head;
		l->head = l->head->next;
		if (l->head)
			l->head->prev = NULL;
		else
			l->tail = NULL;
		free(p);
	}
	return data;
}

/**
 * @brief
 *	Delete a specific node from a queue
 *
 * Linked List is from right to left
 * Insertion (tail) is at the right
 * and Deletion (head) is at left
 *
 * head ---> node ---> node ---> tail
 *
 * ---> Next points to right
 *
 * @param[in] - l - The address of the queue
 * @param[in] - n - Ptr of the node to remove
 *
 * @return	The ptr to the previous node in the queue (or NULL)
 * @retval	NULL - Failed to enqueue data (out of memory)
 * @retval	!NULL - Ptr to the previous node
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
tpp_que_elem_t*
tpp_que_del_elem(tpp_que_t *l, tpp_que_elem_t *n)
{
	tpp_que_elem_t *p = NULL;
	if (n) {
		if (n->next) {
			n->next->prev = n->prev;
		}
		if (n->prev) {
			n->prev->next = n->next;
		}

		if (n == l->head) {
			l->head = n->next;
		}
		if (n == l->tail) {
			l->tail = n->prev;
		}
		if (l->head == NULL || l->tail == NULL) {
			l->tail = NULL;
			l->head = NULL;
		}
		if (n->prev)
			p = n->prev;
		/* else return p as NULL, so list QUE_NEXT starts from head again */
		free(n);
	}
	return p;
}

/**
 * @brief
 *	Insert a node a specific position in the queue
 *
 * Linked List is from right to left
 * Insertion (tail) is at the right
 * and Deletion (head) is at left
 *
 * head ---> node ---> node ---> tail
 *
 * ---> Next points to right
 *
 * @param[in] - l - The address of the queue
 * @param[in] - n - Ptr to the location at which to insert node
 * @param[in] - data - Data to be put in the new node
 * @param[in] - before - Insert before or after the node location of n
 *
 * @return	The ptr to the just inserted node
 * @retval	NULL - Failed to insert data (out of memory)
 * @retval	!NULL - Ptr to the newly created node
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
tpp_que_elem_t*
tpp_que_ins_elem(tpp_que_t *l, tpp_que_elem_t *n, void *data, int before)
{
	tpp_que_elem_t *nd = NULL;

	if (n) {
		if ((nd = malloc(sizeof(tpp_que_elem_t))) == NULL) {
			return NULL;
		}
		nd->queue_data = data;
		if (before == 0) {
			/* after */
			nd->next = n->next;
			nd->prev = n;
			if (n->next)
				n->next->prev = nd;
			n->next = nd;
			if (n == l->tail)
				l->tail = nd;

		} else {
			/* before */
			nd->prev = n->prev;
			nd->next = n;
			if (n->prev)
				n->prev->next = nd;
			n->prev = nd;
			if (n == l->head)
				l->head = nd;
		}
	}
	return nd;
}

/**
 * @brief
 *	Convenience function to set the control header and and send the control
 *	packet (TPP_CTL_NOROUTE) to the given destination by calling
 *	tpp_transport_vsend.
 *
 * @param[in] - fd - The physical connection via which to send control packet
 * @param[in] - src - The host:port of the source (sender)
 * @param[in] - dest - The host:port of the destination
 *
 * @return	Error code
 * @retval	-1    - Failure
 * @retval	 0    - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_send_ctl_msg(int fd, int code, tpp_addr_t *src, tpp_addr_t *dest, unsigned int src_sd, char err_num, char *msg)
{
	tpp_ctl_pkt_hdr_t lhdr;
	tpp_chunk_t chunks[2];

	/* send a packet back to where the original packet came from
	 * basically reverse src and dest
	 */
	lhdr.type = TPP_CTL_MSG;
	lhdr.code = code;
	lhdr.src_sd = htonl(src_sd);
	lhdr.error_num = err_num;
	if (src)
		memcpy(&lhdr.dest_addr, src, sizeof(tpp_addr_t));

	if (dest)
		memcpy(&lhdr.src_addr, dest, sizeof(tpp_addr_t));

	if (msg == NULL)
		msg = "";

	chunks[0].data = &lhdr;
	chunks[0].len = sizeof(tpp_ctl_pkt_hdr_t);
	chunks[1].data = msg;
	chunks[1].len = strlen(msg) + 1;

	TPP_DBPRT(("Sending CTL PKT: sd=%d, msg=%s", src_sd, msg));
	if (tpp_transport_vsend(fd, chunks, 2) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "tpp_transport_vsend failed");
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Combine the host and port parameters to a single string.
 *
 * @param[in] - host - hostname
 * @param[in] - port - add port if not already present
 *
 * @return	The combined string with the host:port
 * @retval	NULL - Failure (out of memory)
 * @retval	!NULl - Combined string
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
char *
mk_hostname(char *host, int port)
{
	char *node_name = malloc(strlen(host) + 10);
	if (node_name) {
		if (strchr(host, ':') || port == -1)
			strcpy(node_name, host);
		else
			sprintf(node_name, "%s:%d", host, port);
	}
	return node_name;
}

/**
 * @brief
 *	Once function for initializing TLS key
 *
 *  @return    - Error code
 *	@retval -1 - Failure
 *	@retval  0 - Success
 *
 * @par Side Effects:
 *	Initializes the global tpp_key_tls, exits if fails
 *
 * @par MT-safe: No
 *
 */
static void
tpp_init_tls_key_once()
{
	if (pthread_key_create(&tpp_key_tls, NULL) != 0) {
		fprintf(stderr, "Failed to initialize TLS key\n");
		exit(1);
	}
}

/**
 * @brief
 *	Initialize the TLS key
 *
 *  @return    - Error code
 *	@retval -1 - Failure
 *	@retval  0 - Success
 *
 * @par Side Effects:
 *	Initializes the global tpp_key_tls
 *
 * @par MT-safe: No
 *
 */
int
tpp_init_tls_key()
{
	if (pthread_once(&tpp_once_ctrl, tpp_init_tls_key_once) != 0)
		return -1;
	return 0;
}

/**
 * @brief
 *	Get the data from the thread TLS
 *
 * @return	Pointer of the tpp_thread_data structure from threads TLS
 * @retval	NULL - Pthread functions failed
 * @retval	!NULl - Data from TLS
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
tpp_tls_t *
tpp_get_tls()
{
	tpp_tls_t *ptr;
	if ((ptr = pthread_getspecific(tpp_key_tls)) == NULL) {
		ptr = calloc(1, sizeof(tpp_tls_t));
		if (!ptr)
			return NULL;

		if (pthread_setspecific(tpp_key_tls, ptr) != 0) {
			free(ptr);
			return NULL;
		}
	}
	return (tpp_tls_t *) ptr; /* thread data already initialized */
}

/**
 * @brief
 *	Get the log buffer address from the thread TLS
 *
 * @return	Address of the log buffer from TLS
 *
 * @par Side Effects:
 *	Exits if not fails
 *
 * @par MT-safe: Yes
 *
 */
char *
tpp_get_logbuf()
{
	tpp_tls_t *ptr;

	ptr = tpp_get_tls();
	if (!ptr) {
		fprintf(stderr, "Out of memory\n");
		exit(1);
	}

	return ptr->tpplogbuf;
}

#ifdef PBS_COMPRESSION_ENABLED

#define COMPR_LEVEL Z_DEFAULT_COMPRESSION

struct def_ctx {
	z_stream cmpr_strm;
	void *cmpr_buf;
	int len;
};

/**
 * @brief
 *	Initialize a multi step deflation
 *	Allocate an initial result buffer of given length
 *
 * @param[in] initial_len -  initial length of result buffer
 *
 * @return - The deflate context
 * @retval - NULL  - Failure
 * @retval - !NULL - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void *
tpp_multi_deflate_init(int initial_len)
{
	int ret;
	struct def_ctx *ctx = malloc(sizeof(struct def_ctx));
	if (!ctx) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating context buffer %lu bytes",
			sizeof(struct def_ctx));
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	if ((ctx->cmpr_buf = malloc(initial_len)) == NULL) {
		free(ctx);
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating deflate buffer %d bytes", initial_len);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	/* allocate deflate state */
	ctx->cmpr_strm.zalloc = Z_NULL;
	ctx->cmpr_strm.zfree = Z_NULL;
	ctx->cmpr_strm.opaque = Z_NULL;
	ret = deflateInit(&ctx->cmpr_strm, COMPR_LEVEL);
	if (ret != Z_OK) {
		free(ctx->cmpr_buf);
		free(ctx);
		tpp_log_func(LOG_CRIT, __func__, "Multi compression init failed");
		return NULL;
	}

	ctx->len = initial_len;
	ctx->cmpr_strm.avail_out = initial_len;
	ctx->cmpr_strm.next_out = ctx->cmpr_buf;
	return (void *) ctx;
}

/**
 * @brief
 *	Add data to a multi step deflation
 *
 * @param[in] c - The deflate context
 * @param[in] fini - Whether this call is the final data addition
 * @param[in] inbuf - Pointer to data buffer to add
 * @param[in] inlen - Length of input buffer to add
 *
 * @return - Error code
 * @retval - -1  - Failure
 * @retval -  0  - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_multi_deflate_do(void *c, int fini, void *inbuf, unsigned int inlen)
{
	struct def_ctx *ctx = c;
	int flush;
	int ret;
	int filled;
	void *p;

	ctx->cmpr_strm.avail_in = inlen;
	ctx->cmpr_strm.next_in = inbuf;

	flush = (fini == 1) ? Z_FINISH : Z_NO_FLUSH;
	while (1) {
		ret = deflate(&ctx->cmpr_strm, flush);
		if (ret == Z_OK && ctx->cmpr_strm.avail_out == 0) {
			/* more output pending, but no output buffer space */
			filled = (char *) ctx->cmpr_strm.next_out - (char *) ctx->cmpr_buf;
			ctx->len = ctx->len * 2;
			p = realloc(ctx->cmpr_buf, ctx->len);
			if (!p) {
				deflateEnd(&ctx->cmpr_strm);
				free(ctx->cmpr_buf);
				free(ctx);
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating deflate buffer %d bytes", ctx->len);
				tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
				return -1;
			}
			ctx->cmpr_buf = p;
			ctx->cmpr_strm.next_out = (Bytef *)((char *) ctx->cmpr_buf + filled);
			ctx->cmpr_strm.avail_out = ctx->len - filled;
		} else
			break;
	}
	if (fini == 1 && ret != Z_STREAM_END) {
		deflateEnd(&ctx->cmpr_strm);
		free(ctx->cmpr_buf);
		free(ctx);
		tpp_log_func(LOG_CRIT, __func__, "Multi compression step failed");
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Complete the deflate and
 *
 * @param[in] c - The deflate context
 * @param[out] cmpr_len - The total length after compression
 *
 * @return - compressed buffer
 * @retval - NULL  - Failure
 * @retval - !NULL - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void *
tpp_multi_deflate_done(void *c, unsigned int *cmpr_len)
{
	struct def_ctx *ctx = c;
	void *data = ctx->cmpr_buf;
	int ret;

	*cmpr_len = ctx->cmpr_strm.total_out;

	ret = deflateEnd(&ctx->cmpr_strm);
	free(ctx);
	if (ret != Z_OK) {
		free(data);
		tpp_log_func(LOG_CRIT, __func__, "Compression cleanup failed");
		return NULL;
	}
	return data;
}

/**
 * @brief Deflate (compress) data
 *
 * @param[in] inbuf   - Ptr to buffer to compress
 * @param[in] inlen   - The size of input buffer
 * @param[out] outlen - The size of the compressed data
 *
 * @return      - Ptr to the compressed data buffer
 * @retval  !NULL - Success
 * @retval   NULL - Failure
 *
 * @par MT-safe: No
 **/
void *
tpp_deflate(void *inbuf, unsigned int inlen, unsigned int *outlen)
{
	z_stream strm;
	int ret;
	void *data;
	unsigned int filled;
	void *p;
	int len;

	*outlen = 0;

	/* allocate deflate state */
	strm.zalloc = Z_NULL;
	strm.zfree = Z_NULL;
	strm.opaque = Z_NULL;
	ret = deflateInit(&strm, Z_DEFAULT_COMPRESSION);
	if (ret != Z_OK) {
		tpp_log_func(LOG_CRIT, __func__, "Compression failed");
		return NULL;
	}

	/* set input data to be compressed */
	len = inlen;
	strm.avail_in = len;
	strm.next_in = inbuf;

	/* allocate buffer to temporarily collect compressed data */
	data = malloc(len);
	if (!data) {
		deflateEnd(&strm);
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating deflate buffer %d bytes", len);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	/* run deflate() on input until output buffer not full, finish
	 * compression if all of source has been read in
	 */

	strm.avail_out = len;
	strm.next_out = data;
	while (1) {
		ret = deflate(&strm, Z_FINISH);
		if (ret == Z_OK && strm.avail_out == 0) {
			/* more output pending, but no output buffer space */
			filled = (char *) strm.next_out - (char *) data;
			len = len * 2;
			p = realloc(data, len);
			if (!p) {
				deflateEnd(&strm);
				free(data);
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating deflate buffer %d bytes", len);
				tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
				return NULL;
			}
			data = p;
			strm.next_out = (Bytef *)((char *) data + filled);
			strm.avail_out = len - filled;
		} else
			break;
	}
	deflateEnd(&strm); /* clean up */
	if (ret != Z_STREAM_END) {
		free(data);
		tpp_log_func(LOG_CRIT, __func__, "Compression failed");
		return NULL;
	}
	filled = (char *) strm.next_out - (char *) data;

	/* reduce the memory area occupied */
	if (filled != inlen) {
		p = realloc(data, filled);
		if (!p) {
			free(data);
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating deflate buffer %d bytes", filled);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return NULL;
		}
		data = p;
	}

	*outlen = filled;
	return data;
}

/**
 * @brief Inflate (de-compress) data
 *
 * @param[in] inbuf  - Ptr to compress data buffer
 * @param[in] inlen  - The size of input buffer
 * @param[in] totlen - The total size of the uncompress data
 *
 * @return      - Ptr to the uncompressed data buffer
 * @retval  !NULL - Success
 * @retval   NULL - Failure
 *
 * @par MT-safe: No
 **/
void *
tpp_inflate(void *inbuf, unsigned int inlen, unsigned int totlen)
{
	int ret;
	z_stream strm;
	void *outbuf = NULL;

	outbuf = malloc(totlen);
	if (!outbuf) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Out of memory allocating inflate buffer %d bytes", totlen);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	/* allocate inflate state */
	strm.zalloc = Z_NULL;
	strm.zfree = Z_NULL;
	strm.opaque = Z_NULL;
	strm.avail_in = 0;
	strm.next_in = Z_NULL;
	ret = inflateInit(&strm);
	if (ret != Z_OK) {
		free(outbuf);
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Decompression Init (inflateInit) failed, ret = %d", ret);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	/* decompress until deflate stream ends or end of file */
	strm.avail_in = inlen;
	strm.next_in = inbuf;

	/* run inflate() on input until output buffer not full */
	strm.avail_out = totlen;
	strm.next_out = outbuf;
	ret = inflate(&strm, Z_FINISH);
	inflateEnd(&strm);
	if (ret != Z_STREAM_END) {
		free(outbuf);
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Decompression (inflate) failed, ret = %d", ret);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}
	return outbuf;
}
#else
void *
tpp_multi_deflate_init(int initial_len)
{
	tpp_log_func(LOG_CRIT, __func__, "TPP compression disabled");
	return NULL;
}

int
tpp_multi_deflate_do(void *c, int fini, void *inbuf, unsigned int inlen)
{
	tpp_log_func(LOG_CRIT, __func__, "TPP compression disabled");
	return -1;
}

void *
tpp_multi_deflate_done(void *c, unsigned int *cmpr_len)
{
	tpp_log_func(LOG_CRIT, __func__, "TPP compression disabled");
	return NULL;
}

void *
tpp_deflate(void *inbuf, unsigned int inlen, unsigned int *outlen)
{
	tpp_log_func(LOG_CRIT, __func__, "TPP compression disabled");
	return NULL;
}

void *
tpp_inflate(void *inbuf, unsigned int inlen, unsigned int totlen)
{
	tpp_log_func(LOG_CRIT, __func__, "TPP compression disabled");
	return NULL;
}
#endif

/**
 * @brief Convenience function to validate a tpp header
 *
 * @param[in] tfd       - The transport fd
 * @param[in] pkt_start - The start address of the pkt
 *
 * @return - Packet validity status
 * @retval  0 - Packet has valid header structure
 * @retval -1 - Packet has invalid header structure
 *
 * @par MT-safe: No
 *
 **/
int
tpp_validate_hdr(int tfd, char *pkt_start)
{
	enum TPP_MSG_TYPES type;
	char *data;
	int data_len;

	data_len = ntohl(*((int *) pkt_start));
	data = pkt_start + sizeof(int);
	type = *((unsigned char *) data);

	if ((data_len < 0 || type >= TPP_LAST_MSG) ||
		(data_len > TPP_SEND_SIZE && type != TPP_DATA && type != TPP_MCAST_DATA)) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
				 "tfd=%d, Received invalid packet type with type=%d? data_len=%d", tfd, type, data_len);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}
	return 0;
}

/**
 * @brief Get a list of addresses for a given hostname
 *
 * @param[in] node_names - comma separated hostnames, each of format host:port
 * @param[out] count - return address count
 *
 * @return        - Array of addresses in tpp_addr structures
 * @retval  !NULL - Array of addresses returned
 * @retval  NULL  - call failed
 *
 * @par MT-safe: Yes
 * 
 **/
tpp_addr_t *
tpp_get_addresses(char *names, int *count)
{
	tpp_addr_t *addrs = NULL;
	tpp_addr_t *addrs_tmp = NULL;
	int tot_count = 0;
	int tmp_count;
	int i, j;
	char *token;
	char *saveptr;
	int port;
	char *p;
	char *node_names;

	*count = 0;
	if ((node_names = strdup(names)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating address block");
		return NULL;
	}

	token = strtok_r(node_names, ",", &saveptr);
	while (token) {
		/* parse port from host name */
		if ((p = strchr(token, ':')) == NULL) {
			free(addrs);
			free(node_names);
			return NULL;
		}
		
		*p = '\0';
		port = atol(p+1);
		
		addrs_tmp = tpp_sock_resolve_host(token, &tmp_count); /* get all ipv4 addresses */
		if (addrs_tmp) {
			if ((addrs = realloc(addrs, (tot_count + tmp_count) * sizeof(tpp_addr_t))) == NULL) {
				free(addrs);
				free(node_names);
				tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating address block");
				return NULL;
			}

			for (i = 0; i < tmp_count; i++) {
				for (j = 0; j < tot_count; j++) {
					if (memcmp(&addrs[j].ip, &addrs_tmp[i].ip, sizeof(addrs_tmp[i].ip)) == 0)
						break;
				}

				/* add if duplicate not found already */
				if (j == tot_count) {
					memmove(&addrs[tot_count], &addrs_tmp[i], sizeof(tpp_addr_t));
					addrs[tot_count].port = htons(port);
					tot_count++;
				}
			}
			free(addrs_tmp);
		}

		token = strtok_r(NULL, ",", &saveptr);
	}
	free(node_names);

	*count = tot_count;
	return addrs; /* free @ caller */
}

/**
 * @brief Get the address of the local end of the connection
 *
 * @param[in] sock - connection id
 *
 * @return - Address of the local end of the connection in tpp_addr format
 * @retval  !NULL - address returned
 * @retval  NULL  - call failed
 *
 * @par MT-safe: Yes
 **/
tpp_addr_t *
tpp_get_local_host(int sock)
{
	struct sockaddr addr;
	struct sockaddr_in *inp = NULL;
	struct sockaddr_in6 *inp6 = NULL;
	tpp_addr_t *taddr = NULL;
	socklen_t len = sizeof(addr);

	if (getsockname(sock, &addr, &len) == -1) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Could not get name of peer for sock %d, errno=%d", sock, errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}
	if (addr.sa_family != AF_INET && addr.sa_family != AF_INET6) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Bad address family for sock %d", sock);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	taddr = calloc(1, sizeof(tpp_addr_t));
	if (!taddr) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating address");
		return NULL;
	}

	if (addr.sa_family == AF_INET) {
		inp = (struct sockaddr_in *) &addr;
		memcpy(&taddr->ip, &inp->sin_addr, sizeof(inp->sin_addr));
		taddr->port = inp->sin_port; /* keep in network order */
		taddr->family = TPP_ADDR_FAMILY_IPV4;
	} else if (addr.sa_family == AF_INET6){
		inp6 = (struct sockaddr_in6 *) &addr;
		memcpy(&taddr->ip, &inp6->sin6_addr, sizeof(inp6->sin6_addr));
		taddr->port = inp6->sin6_port; /* keep in network order */
		taddr->family = TPP_ADDR_FAMILY_IPV6;
	}

	return taddr;
}

/**
 * @brief Get the address of the remote (peer) end of the connection
 *
 * @param[in] sock - connection id
 *
 * @return  - Address of the remote end of the connection in tpp_addr format
 * @retval  !NULL - address returned
 * @retval  NULL  - call failed
 *
 * @par MT-safe: Yes
 **/
tpp_addr_t *
tpp_get_connected_host(int sock)
{
	struct sockaddr addr;
	struct sockaddr_in *inp = NULL;
	struct sockaddr_in6 *inp6 = NULL;
	tpp_addr_t *taddr = NULL;
	socklen_t len = sizeof(addr);

	if (getpeername(sock, &addr, &len) == -1) {
		if (errno == ENOTCONN)
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Peer disconnected sock %d", sock);
		else
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Could not get name of peer for sock %d, errno=%d", sock, errno);

		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}
	if (addr.sa_family != AF_INET && addr.sa_family != AF_INET6) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Bad address family for sock %d", sock);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	taddr = calloc(1, sizeof(tpp_addr_t));
	if (!taddr) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating address");
		return NULL;
	}

	if (addr.sa_family == AF_INET) {
		inp = (struct sockaddr_in *) &addr;
		memcpy(&taddr->ip, &inp->sin_addr, sizeof(inp->sin_addr));
		taddr->port = inp->sin_port; /* keep in network order */
		taddr->family = TPP_ADDR_FAMILY_IPV4;
	} else if (addr.sa_family == AF_INET6){
		inp6 = (struct sockaddr_in6 *) &addr;
		memcpy(&taddr->ip, &inp6->sin6_addr, sizeof(inp6->sin6_addr));
		taddr->port = inp6->sin6_port; /* keep in network order */
		taddr->family = TPP_ADDR_FAMILY_IPV6;
	}

	return taddr;
}

/**
 * @brief return a human readable string representation of an address
 *        for either an ipv4 or ipv6 address
 *
 * @param[in] ap - address in tpp_addr format
 *
 * @return  - string representation of address
 *            (uses TLS area to make it easy and yet thread safe)
 *
 * @par MT-safe: Yes
 **/
char *
tpp_netaddr(tpp_addr_t *ap)
{
	tpp_tls_t *ptr;
#ifdef WIN32
	struct sockaddr_in in;
	struct sockaddr_in6 in6;
	int len;
#endif
	char port[7];

	if (ap == NULL)
		return "unknown";

	ptr = tpp_get_tls();
	if (!ptr) {
		fprintf(stderr, "Out of memory\n");
		exit(1);
	}

	ptr->tppstaticbuf[0] = '\0';

	if (ap->family == TPP_ADDR_FAMILY_UNSPEC)
		return "unknown";

#ifdef WIN32
	if (ap->family == TPP_ADDR_FAMILY_IPV4) {
		memcpy(&in.sin_addr, ap->ip, sizeof(in.sin_addr));
		in.sin_family = AF_INET;
		in.sin_port = 0;
		len = TPP_LOGBUF_SZ;
		WSAAddressToString((LPSOCKADDR) &in, sizeof(in), NULL, (LPSTR) &ptr->tppstaticbuf, &len);
	} else if (ap->family == TPP_ADDR_FAMILY_IPV6) {
		memcpy(&in6.sin6_addr, ap->ip, sizeof(in6.sin6_addr));
		in6.sin6_family = AF_INET6;
		in6.sin6_port = 0;
		len = TPP_LOGBUF_SZ;
		WSAAddressToString((LPSOCKADDR) &in6, sizeof(in6), NULL, (LPSTR) &ptr->tppstaticbuf, &len);
	}
#else
	if (ap->family == TPP_ADDR_FAMILY_IPV4) {
		inet_ntop(AF_INET, &ap->ip, ptr->tppstaticbuf, INET_ADDRSTRLEN);
	}  else if (ap->family == TPP_ADDR_FAMILY_IPV6) {
		inet_ntop(AF_INET6, &ap->ip, ptr->tppstaticbuf, INET6_ADDRSTRLEN);
	}
#endif
	sprintf(port, ":%d", ntohs(ap->port));
	strcat(ptr->tppstaticbuf, port);

	/* if log mask is high, then reverse lookup the ip address
	 * to print hostname along with ip
	 */
	if (tpp_log_event_mask >= (PBSEVENT_DEBUG4 - 1)) {
		char host[256];

		if (tpp_sock_resolve_ip(ap, host, sizeof(host)) == 0) {
			char *tmp_buf;

			pbs_asprintf(&tmp_buf, "(%s)%s", host, ptr->tppstaticbuf);
			strcpy(ptr->tppstaticbuf, tmp_buf);
			free(tmp_buf);
		}
	}

	return ptr->tppstaticbuf;
}

/**
 * @brief return a human readable string representation of an address
 *        for either an ipv4 or ipv6 address
 *
 * @param[in] sa - address in sockaddr format
 *
 * @return  - string representation of address
 *            (uses TLS area to make it easy and yet thread safe)
 *
 * @par MT-safe: Yes
 **/
char *
tpp_netaddr_sa(struct sockaddr *sa)
{
	tpp_tls_t *ptr;
	int len = TPP_LOGBUF_SZ;

	ptr = tpp_get_tls();
	if (!ptr) {
		fprintf(stderr, "Out of memory\n");
		exit(1);
	}
	ptr->tppstaticbuf[0] = '\0';

#ifdef WIN32
	WSAAddressToString((LPSOCKADDR)&sa, sizeof(struct sockaddr), NULL, (LPSTR)&ptr->tppstaticbuf, &len);
#else
	if (sa->sa_family == AF_INET)
		inet_ntop(sa->sa_family, &(((struct sockaddr_in *) sa)->sin_addr), ptr->tppstaticbuf, len);
	else
		inet_ntop(sa->sa_family, &(((struct sockaddr_in6 *) sa)->sin6_addr), ptr->tppstaticbuf, len);
#endif

	return ptr->tppstaticbuf;
}

/*
 * Convenience function to delete information about a router
 */
void
free_router(tpp_router_t *r)
{
	if (r) {
		if (r->router_name)
			free(r->router_name);
		free(r);
	}
}

/*
 * Convenience function to delete information about a leaf
 */
void
free_leaf(tpp_leaf_t *l)
{
	if (l) {
		if (l->leaf_addrs)
			free(l->leaf_addrs);

		free(l);
	}
}

/**
 * @brief Set the loglevel for the tpp layer. This is used to print
 * additional information at times (like ip addresses are revers
 * looked-up and hostnames printed in logs).
 *
 * @param[in] logmask - The logmask value to set
 *
 * @par MT-safe: No
 **/
void
tpp_set_logmask(long logmask)
{
	tpp_log_event_mask = logmask;
}

#ifdef DEBUG
/*
 * Convenience function to print the packet header
 *
 * @param[in] fnc - name of calling function
 * @param[in] data - start of data packet
 * @param[in] len - length of data packet
 *
 * @par MT-safe: yes
 */
void
print_packet_hdr(const char *fnc, void *data, int len)
{
	tpp_ctl_pkt_hdr_t *hdr = (tpp_ctl_pkt_hdr_t *) data;

	char str_types[][20] = { "TPP_CTL_JOIN", "TPP_CTL_LEAVE", "TPP_DATA", "TPP_CTL_MSG", "TPP_CLOSE_STRM", "TPP_MCAST_DATA" };
	unsigned char type = hdr->type;

	if (!tpp_dbprt)
		return;

	printf("%ld:%x:%s: ", time(0), (int) pthread_self(), fnc);
	if (type == TPP_CTL_JOIN) {
		tpp_addr_t *addrs = (tpp_addr_t *) (((char *) data) + sizeof(tpp_join_pkt_hdr_t));
		printf("%s message arrived from src_host = %s\n", str_types[type - 1], tpp_netaddr(addrs));
	} else if (type == TPP_CTL_LEAVE) {
		tpp_addr_t *addrs = (tpp_addr_t *) (((char *) data) + sizeof(tpp_leave_pkt_hdr_t));
		printf("%s message arrived from src_host = %s\n", str_types[type - 1], tpp_netaddr(addrs));
	} else if (type == TPP_MCAST_DATA) {
		tpp_mcast_pkt_hdr_t *mhdr = (tpp_mcast_pkt_hdr_t *) data;
		printf("%s message arrived from src_host = %s\n", str_types[type - 1], tpp_netaddr(&mhdr->src_addr));
	} else if ((type == TPP_DATA) || (type == TPP_CLOSE_STRM)) {
		int seq_no_recvd, seq_no_acked;
		unsigned char dup;
		char buff[PATH_MAX+1];
		tpp_data_pkt_hdr_t *dhdr = (tpp_data_pkt_hdr_t *) data;

		seq_no_recvd = ntohl(dhdr->seq_no);
		seq_no_acked = ntohl(dhdr->ack_seq);
		dup = dhdr->dup;

		strncpy(buff, tpp_netaddr(&dhdr->src_addr), sizeof(buff));
		printf("%s: src_host=%s, dest_host=%s, len=%d, src_sd=%d", str_types[type - 1], buff, tpp_netaddr(&dhdr->dest_addr), len,
			ntohl(dhdr->src_sd));

		if (ntohl(dhdr->dest_sd) == UNINITIALIZED_INT)
			printf(", dest_sd=NONE");
		else
			printf(", dest_sd=%d", ntohl(dhdr->dest_sd));

		printf(", seq_no=%d", seq_no_recvd);
		printf(", src_magic=%d", ntohl(dhdr->src_magic));

		if (seq_no_acked == UNINITIALIZED_INT)
			printf(", seq_no_acked=NONE");
		else
			printf(", seq_no_acked=%d", seq_no_acked);

		printf(", dup=%d\n", dup);

	} else {
		printf("%s message arrived from src_host = %s\n", str_types[type - 1], tpp_netaddr(&hdr->src_addr));
	}
	fflush(stdout);
}
#endif

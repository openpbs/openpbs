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


/**
 * @file	tpp_em.c
 *
 * @brief	The event monitor functions for TPP
 *
 * @par		Functionality:
 *
 *		TPP = TCP based Packet Protocol. This layer uses TCP in a multi-
 *		hop router based network topology to deliver packets to desired
 *		destinations. LEAF (end) nodes are connected to ROUTERS via
 *		persistent TCP connections. The ROUTER has intelligence to route
 *		packets to appropriate destination leaves or other routers.
 *
 *		This file implements the em (event monitor) code such that it is
 *		platform independent. It provides a generic interface to add, remove
 *		and wait for file descriptors to be monitored for events.
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <signal.h>
#include "tpp_internal.h"
#ifdef HAVE_SYS_EVENTFD_H
#include <sys/eventfd.h>
#endif

/********************************** START OF MULTIPLEXING CODE *****************************************/
/**
 * @brief
 *	Platform independent function to wait for a event to happen on the event context.
 *	Waits for the specified timeout period. Does not care block/unblock signals.
 *
 * @param[in] -  em_ctx - The event monitor context
 * @param[out] - ev_array - Array of events returned
 * @param[in] - timeout - The timeout in milliseconds to wait for
 *
 * @return	Number of events returned
 * @retval -1	Failure
 * @retval  0	Timeout
 * @retval >0   Success (some events occured)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_em_wait(void *em_ctx, em_event_t **ev_array, int timeout)
{
#ifndef WIN32
	return tpp_em_pwait(em_ctx, ev_array, timeout, NULL);
#else
	return tpp_em_wait_win(em_ctx, ev_array, timeout);
#endif
}

/****************************************** Linux EPOLL ************************************************/

#if defined(PBS_USE_EPOLL)
/**
 * @brief
 *	Initialize event monitoring
 *
 * @param[in] - max_events - max events that needs to be handled
 *
 * @return	Event context
 * @retval  NULL Failure
 * @retval !NULL Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
void *
tpp_em_init(int max_events)
{
	epoll_context_t *ctx = malloc(sizeof(epoll_context_t));
	if (!ctx)
		return NULL;

	ctx->events = malloc(sizeof(em_event_t) * max_events);
	if (ctx->events == NULL) {
		free(ctx);
		return NULL;
	}

#if defined(EPOLL_CLOEXEC)
	ctx->epoll_fd = epoll_create1(EPOLL_CLOEXEC);
#else
	ctx->epoll_fd = epoll_create(max_events);
	if (ctx->epoll_fd > -1) {
		tpp_set_close_on_exec(ctx->epoll_fd);
	}
#endif
	if (ctx->epoll_fd == -1) {
		free(ctx->events);
		free(ctx);
		return NULL;
	}
	ctx->max_nfds = max_events;
	ctx->init_pid = getpid();

	return ((void *) ctx);
}

/**
 * @brief
 *	Destroy event monitoring
 *
 * @param[in] ctx - The event monitoring context to destroy
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
void
tpp_em_destroy(void *em_ctx)
{
	epoll_context_t *ctx = (epoll_context_t *) em_ctx;

	if (ctx != NULL) {
		close(ctx->epoll_fd);
		free(ctx->events);
		free(ctx);
	}
}

/**
 * @brief
 *	Add a file descriptor to the list of descriptors to be monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
 * @param[in] - event_mask - A mask of events to monitor the fd for
 *
 * @return	Error code
 * @retval -1	Failure
 * @retval  0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_em_add_fd(void *em_ctx, int fd, int event_mask)
{
	epoll_context_t *ctx = (epoll_context_t *) em_ctx;
	struct epoll_event ev;

	/*
	 * if not the process which called em_init, (eg a child process),
	 * we should not allow manipulating the epoll fd as it effects
	 * the epoll_fd structure pointed to by the parent process
	 */
	if (ctx->init_pid != getpid())
		return 0;

	memset(&ev, 0, sizeof(ev));
	ev.events = event_mask;
	ev.data.fd = fd;

	if (epoll_ctl(ctx->epoll_fd, EPOLL_CTL_ADD, fd, &ev) < 0)
		return -1;

	return 0;
}

/**
 * @brief
 *	Modify a file descriptor to the list of descriptors to be monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
 * @param[in] - event_mask - A mask of events to monitor the fd for
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
tpp_em_mod_fd(void *em_ctx, int fd, int event_mask)
{
	epoll_context_t *ctx = (epoll_context_t *) em_ctx;
	struct epoll_event ev;

	/*
	 * if not the process which called em_init, (eg a child process),
	 * we should not allow manipulating the epoll fd as it effects
	 * the epoll_fd structure pointed to by the parent process
	 */
	if (ctx->init_pid != getpid())
		return 0;

	memset(&ev, 0, sizeof(ev));
	ev.events = event_mask;
	ev.data.fd = fd;

	if (epoll_ctl(ctx->epoll_fd, EPOLL_CTL_MOD, fd, &ev) < 0)
		return -1;

	return 0;
}

/**
 * @brief
 *	Remove a file descriptor from the list of descriptors monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
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
tpp_em_del_fd(void *em_ctx, int fd)
{
	epoll_context_t *ctx = (epoll_context_t *) em_ctx;
	struct epoll_event ev;

	/*
	 * if not the process which called em_init, (eg a child process),
	 * we should not allow manipulating the epoll fd as it effects
	 * the epoll_fd structure pointed to by the parent process
	 */
	if (ctx->init_pid != getpid())
		return 0;

	memset(&ev, 0, sizeof(ev));
	ev.data.fd = fd;
	if (epoll_ctl(ctx->epoll_fd, EPOLL_CTL_DEL, fd, &ev) < 0)
		return -1;

	return 0;
}

/**
 * @brief
 *	Wait for a event to happen on the event context. Waits for the specified
 *	timeout period.
 *
 * @param[in] -  em_ctx - The event monitor context
 * @param[out] - ev_array - Array of events returned
 * @param[in] - timeout - The timeout in milliseconds to wait for
 * @param[in] - sigmask - The signal mask to atomically unblock before sleeping
 *
 * @return	Number of events returned
 * @retval -1	Failure
 * @retval  0	Timeout
 * @retval >0   Success (some events occured)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
#ifdef PBS_HAVE_EPOLL_PWAIT
int
tpp_em_pwait(void *em_ctx, em_event_t **ev_array, int timeout, const sigset_t *sigmask)
{
        epoll_context_t *ctx = (epoll_context_t *) em_ctx;
        *ev_array = ctx->events;
        return (epoll_pwait(ctx->epoll_fd, ctx->events, ctx->max_nfds, timeout, sigmask));
}
#else
int
tpp_em_pwait(void *em_ctx, em_event_t **ev_array, int timeout, const sigset_t *sigmask)
{
	epoll_context_t *ctx = (epoll_context_t *) em_ctx;
	*ev_array = ctx->events;
	sigset_t origmask;
	int n;
	sigprocmask(SIG_SETMASK, sigmask, &origmask);
	n = epoll_wait(ctx->epoll_fd, ctx->events, ctx->max_nfds, timeout);
	sigprocmask(SIG_SETMASK, &origmask, NULL);
	return n;
}
#endif

#elif defined (PBS_USE_POLL)

/************************************************* POLL ************************************************/

/**
 * @brief
 *	Initialize event monitoring
 *
 * @param[in] - max_events - max events that needs to be handled
 *
 * @return	Event context
 * @retval  NULL Failure
 * @retval !NULL Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
void *
tpp_em_init(int max_events)
{
	int i;
	poll_context_t *ctx = malloc(sizeof(poll_context_t));
	if (!ctx)
		return NULL;

	ctx->events = malloc(sizeof(em_event_t) * max_events);
	if (ctx->events == NULL) {
		free(ctx);
		return NULL;
	}

	ctx->fds = malloc(sizeof(struct pollfd) * max_events);
	if (!ctx->fds) {
		free(ctx->events);
		free(ctx);
		return NULL;
	}
	for (i = 0; i < max_events; i++)
		ctx->fds[i].fd = -1;
	ctx->max_nfds = max_events;
	ctx->curr_nfds = max_events;

	return ((void *) ctx);
}

/**
 * @brief
 *	Destroy event monitoring
 *
 * @param[in] ctx - The event monitoring context to destroy
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
void
tpp_em_destroy(void *em_ctx)
{
	free(((poll_context_t *) em_ctx)->fds);
	free(((poll_context_t *) em_ctx)->events);
	free(em_ctx);
}

/**
 * @brief
 *	Add a file descriptor to the list of descriptors to be monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
 * @param[in] - event_mask - A mask of events to monitor the fd for
 *
 * @return	Error code
 * @retval -1	Failure
 * @retval  0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_em_add_fd(void *em_ctx, int fd, int event_mask)
{
	poll_context_t *ctx = (poll_context_t *) em_ctx;
	int nfds;
	int i;

	if (fd > ctx->curr_nfds - 1) {
		nfds = fd + 1000;
		ctx->fds = realloc(ctx, sizeof(struct pollfd) * nfds);
		if (!ctx->fds) {
			free(ctx);
			return -1;
		}
		for (i = ctx->curr_nfds; i < nfds; i++)
			ctx->fds[i].fd = -1;

		ctx->curr_nfds = nfds;
	}

	ctx->fds[fd].fd = fd;
	ctx->fds[fd].events = event_mask;
	ctx->fds[fd].revents = 0;

	return 0;
}

/**
 * @brief
 *	Modify a file descriptor to the list of descriptors to be monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
 * @param[in] - event_mask - A mask of events to monitor the fd for
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
tpp_em_mod_fd(void *em_ctx, int fd, int event_mask)
{
	poll_context_t *ctx = (poll_context_t *) em_ctx;

	ctx->fds[fd].fd = fd;
	ctx->fds[fd].events = event_mask;
	ctx->fds[fd].revents = 0;

	return 0;
}

/**
 * @brief
 *	Remove a file descriptor from the list of descriptors monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
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
tpp_em_del_fd(void *em_ctx, int fd)
{
	poll_context_t *ctx = (poll_context_t *) em_ctx;
	ctx->fds[fd].fd = -1;
	return 0;
}

/**
 * @brief
 *	Wait for a event to happen on the event context. Waits for the specified
 *	timeout period.
 *
 * @param[in] -  em_ctx - The event monitor context
 * @param[out] - ev_array - Array of events returned
 * @param[in] - timeout - The timeout in milliseconds to wait for
 * @param[in] - sigmask - The signal mask to atomically unblock before sleeping
 *
 * @return	Number of events returned
 * @retval -1	Failure
 * @retval  0	Timeout
 * @retval >0   Success (some events occured)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_em_pwait(void *em_ctx, em_event_t **ev_array, int timeout, const sigset_t *sigmask)
{
	poll_context_t *ctx = (poll_context_t *) em_ctx;
	int nready;
	int i;
	int ev_count;
#ifndef PBS_HAVE_PPOLL
	sigset_t origmask;
#endif

#ifdef PBS_HAVE_PPOLL
	nready = ppoll(ctx->fds, ctx->curr_nfds, timeout, sigmask);
#else
	if (sigmask) {
		if (sigprocmask(SIG_SETMASK, sigmask, &origmask) == -1)
			return -1;
	}

	nready = poll(ctx->fds, ctx->curr_nfds, timeout);

	if (sigmask) {
		sigprocmask(SIG_SETMASK, &origmask, NULL);
	}
#endif

	if (nready == -1 || nready == 0)
		return nready;

	ev_count = 0;
	*ev_array = ctx->events;
	for (i = 0; i < ctx->curr_nfds; i++) {
		if (ctx->fds[i].fd < 0)
			continue;

		if (ctx->fds[i].revents != 0) {
			ctx->events[ev_count].fd = ctx->fds[i].fd;
			ctx->events[ev_count].events = ctx->fds[i].revents;
			ev_count++;

			if (ev_count > ctx->max_nfds)
				return ev_count;
		}
	}
	return ev_count;
}


/*************************************** GENERIC SELECT ************************************************/

#elif defined (PBS_USE_SELECT)
/**
 * @brief
 *	Initialize event monitoring
 *
 * @param[in] - max_events - max events that needs to be handled
 *
 * @return	Event context
 * @retval  NULL Failure
 * @retval !NULL Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
void *
tpp_em_init(int max_events)
{
	sel_context_t *ctx;

	ctx = malloc(sizeof(sel_context_t));
	if (!ctx)
		return NULL;

	ctx->events = malloc(sizeof(em_event_t) * max_events);
	if (ctx->events == NULL) {
		free(ctx);
		return NULL;
	}

	FD_ZERO(&ctx->master_read_fds);
	FD_ZERO(&ctx->master_write_fds);
	FD_ZERO(&ctx->master_err_fds);

	ctx->maxfd = 0;
	ctx->max_nfds = max_events;

	return ((void *) ctx);
}

/**
 * @brief
 *	Destroy event monitoring
 *
 * @param[in] ctx - The event monitoring context to destroy
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
void
tpp_em_destroy(void *em_ctx)
{
	free(((sel_context_t *) em_ctx)->events);
	free(em_ctx);
}

/**
 * @brief
 *	Add a file descriptor to the list of descriptors to be monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
 * @param[in] - event_mask - A mask of events to monitor the fd for
 *
 * @return	Error code
 * @retval -1	Failure
 * @retval  0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_em_add_fd(void *em_ctx, int fd, int event_mask)
{
	sel_context_t *ctx = (sel_context_t *) em_ctx;

	if ((event_mask & EM_IN) == EM_IN)
		FD_SET(fd, &ctx->master_read_fds);

	if ((event_mask & EM_OUT) == EM_OUT)
		FD_SET(fd, &ctx->master_write_fds);

	if ((event_mask & EM_ERR) == EM_ERR)
		FD_SET(fd, &ctx->master_err_fds);

	if (fd >= ctx->maxfd)
		ctx->maxfd = fd + 1;

	return 0;
}

/**
 * @brief
 *	Modify a file descriptor to the list of descriptors to be monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
 * @param[in] - event_mask - A mask of events to monitor the fd for
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
tpp_em_mod_fd(void *em_ctx, int fd, int event_mask)
{
	sel_context_t *ctx = (sel_context_t *) em_ctx;

	FD_CLR(fd, &ctx->master_read_fds);
	FD_CLR(fd, &ctx->master_write_fds);
	FD_CLR(fd, &ctx->master_err_fds);

	if ((event_mask & EM_IN) == EM_IN)
		FD_SET(fd, &ctx->master_read_fds);

	if ((event_mask & EM_OUT) == EM_OUT)
		FD_SET(fd, &ctx->master_write_fds);

	if ((event_mask & EM_ERR) == EM_ERR)
		FD_SET(fd, &ctx->master_err_fds);

	if (fd >= ctx->maxfd)
		ctx->maxfd = fd + 1;

	return 0;
}

/**
 * @brief
 *	Remove a file descriptor from the list of descriptors monitored for
 *	events
 *
 * @param[in] - em_ctx - The event monitor context
 * @param[in] - fd - The file descriptor to add to the monitored list
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
tpp_em_del_fd(void *em_ctx, int fd)
{
	sel_context_t *ctx = (sel_context_t *) em_ctx;

	FD_CLR(fd, &ctx->master_read_fds);
	FD_CLR(fd, &ctx->master_write_fds);
	FD_CLR(fd, &ctx->master_err_fds);

	return 0;
}

/**
 * @brief
 *	Wait for a event to happen on the event context. Waits for the specified
 *	timeout period.
 *
 * @param[in] -  em_ctx - The event monitor context
 * @param[out] - ev_array - Array of events returned
 * @param[in] - timeout - The timeout in milliseconds to wait for
 * @param[in] - sigmask - The signal mask to atomically unblock before sleeping
 *
 * @return	Number of events returned
 * @retval -1	Failure
 * @retval  0	Timeout
 * @retval >0   Success (some events occured)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
#ifndef WIN32
int
tpp_em_pwait(void *em_ctx, em_event_t **ev_array, int timeout, const sigset_t *sigmask)
{
	sel_context_t *ctx = (sel_context_t *) em_ctx;
	int nready;
	int i;
	int ev_count;
	struct timeval tv;
	struct timeval *ptv;
	int event;

	errno = 0;

	memcpy(&ctx->read_fds, &ctx->master_read_fds, sizeof(ctx->master_read_fds));
	memcpy(&ctx->write_fds, &ctx->master_write_fds, sizeof(ctx->master_read_fds));
	memcpy(&ctx->err_fds, &ctx->master_err_fds, sizeof(ctx->master_read_fds));

	if (timeout == -1) {
		ptv = NULL;
	} else {
		tv.tv_sec = timeout / 1000;
		tv.tv_usec = (timeout % 1000) * 1000;
		ptv = &tv;
	}

	nready = pselect(ctx->maxfd, &ctx->read_fds, &ctx->write_fds, &ctx->err_fds, ptv, sigmask);

	if (nready == -1 || nready == 0)
		return nready;

	ev_count = 0;
	*ev_array = ctx->events;
	for (i = 0; i <= ctx->maxfd; i++) {
		event = 0;

		if (FD_ISSET(i, &ctx->read_fds))
			event |= EM_IN;
		if (FD_ISSET(i, &ctx->write_fds))
			event |= EM_OUT;
		if (FD_ISSET(i, &ctx->err_fds))
			event |= EM_ERR;

		if (event != 0) {
			ctx->events[ev_count].fd = i;
			ctx->events[ev_count].events = event;
			ev_count++;
		}

		if (ev_count > ctx->max_nfds)
			break;
	}
	return ev_count;
}
#else
int
tpp_em_wait_win(void *em_ctx, em_event_t **ev_array, int timeout)
{
	sel_context_t *ctx = (sel_context_t *) em_ctx;
	int nready;
	int i;
	int ev_count;
	struct timeval tv;
	struct timeval *ptv;
	int event;

	errno = 0;

	memcpy(&ctx->read_fds, &ctx->master_read_fds, sizeof(ctx->master_read_fds));
	memcpy(&ctx->write_fds, &ctx->master_write_fds, sizeof(ctx->master_read_fds));
	memcpy(&ctx->err_fds, &ctx->master_err_fds, sizeof(ctx->master_read_fds));

	if (timeout == -1) {
		ptv = NULL;
	} else {
		tv.tv_sec = timeout / 1000;
		tv.tv_usec = (timeout % 1000) * 1000;
		ptv = &tv;
	}

	nready = select(ctx->maxfd, &ctx->read_fds, &ctx->write_fds, &ctx->err_fds, ptv);
	/* for windows select, translate the errno and return value */
	if (nready == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		nready = -1;
	}

	if (nready == -1 || nready == 0)
		return nready;

	ev_count = 0;
	*ev_array = ctx->events;
	for (i = 0; i <= ctx->maxfd; i++) {
		event = 0;

		if (FD_ISSET(i, &ctx->read_fds))
			event |= EM_IN;
		if (FD_ISSET(i, &ctx->write_fds))
			event |= EM_OUT;
		if (FD_ISSET(i, &ctx->err_fds))
			event |= EM_ERR;

		if (event != 0) {
			ctx->events[ev_count].fd = i;
			ctx->events[ev_count].events = event;
			ev_count++;
		}

		if (ev_count > ctx->max_nfds)
			break;
	}
	return ev_count;
}
#endif

#endif

/********************************** END OF MULTIPLEXING CODE *****************************************/


/********************************** START OF MBOX CODE ***********************************************/
/**
 * @brief
 *	Initialize an mbox
 *
 * @param[in] - mbox   - The mbox to read from
 * @param[in] - size   - The total size allowed, or -1 for inifinite
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval   0 - success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mbox_init(tpp_mbox_t *mbox, char *name, int size)
{
	tpp_init_lock(&mbox->mbox_mutex);
	tpp_lock(&mbox->mbox_mutex);

	TPP_QUE_CLEAR(&mbox->mbox_queue);

	snprintf(mbox->mbox_name, sizeof(mbox->mbox_name), "%s", name);
	mbox->mbox_size = 0;
	mbox->max_size = size;

#ifdef HAVE_SYS_EVENTFD_H
	if ((mbox->mbox_eventfd = eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK)) == -1) {
		tpp_log(LOG_CRIT, __func__, "eventfd() error, errno=%d", errno);
		tpp_unlock(&mbox->mbox_mutex);
		return -1;
	}
#else
	/*
	 * No eventfd
	 * Using signals with select(), poll() is not race-safe
	 * In linux we have ppoll() and pselect() which are race-safe
	 * but for other Unices (dev/poll, pollset etc) there is no race-safe way
	 * Use the self-pipe trick!
	 */
	if (tpp_pipe_cr(mbox->mbox_pipe) != 0) {
		tpp_log(LOG_CRIT, __func__, "pipe() error, errno=%d", errno);
		tpp_unlock(&mbox->mbox_mutex);
		return -1;
	}
	/* set the cmd pipe to nonblocking now
	 * that we are ready to rock and roll
	 */
	tpp_set_non_blocking(mbox->mbox_pipe[0]);
	tpp_set_non_blocking(mbox->mbox_pipe[1]);
	tpp_set_close_on_exec(mbox->mbox_pipe[0]);
	tpp_set_close_on_exec(mbox->mbox_pipe[1]);
#endif
	tpp_unlock(&mbox->mbox_mutex);
	return 0;
}

/**
 * @brief
 *	Get the underlying file descriptor
 *	associated with the mbox
 *
 * @param[in] - mbox   - The mbox to read from
 *
 * @return  file descriptor
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mbox_getfd(tpp_mbox_t *mbox)
{
#ifdef HAVE_SYS_EVENTFD_H
	return mbox->mbox_eventfd;
#else
	return mbox->mbox_pipe[0];
#endif
}

/**
 * @brief
 *	Destroy a message box
 *
 * @param[in] mbox - The message box to destroy
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
void
tpp_mbox_destroy(tpp_mbox_t *mbox)
{
#ifdef HAVE_SYS_EVENTFD_H
	close(mbox->mbox_eventfd);
#else
	if (mbox->mbox_pipe[0] > -1)
		tpp_pipe_close(mbox->mbox_pipe[0]);
	if (mbox->mbox_pipe[1] > -1)
		tpp_pipe_close(mbox->mbox_pipe[1]);
#endif
}

/**
 * @brief
 *	Add mbox to the monitoring infra
 *	so that messages to the mbox will
 *	wake up handling thread
 *
 * @param[in] - em_ctx - The event monitoring context
 * @param[in] - mbox   - The mbox to read from
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval   0 - success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mbox_monitor(void *em_ctx, tpp_mbox_t *mbox)
{
	/* add eventfd to the poll set */
	if (tpp_em_add_fd(em_ctx, tpp_mbox_getfd(mbox), EM_IN) == -1) {
		tpp_log(LOG_CRIT, __func__, "em_add_fd() error for mbox=%s, errno=%d", mbox->mbox_name, errno);
		return -1;
	}

	return 0;
}

/**
 * @brief
 *	Read a command from the msg box.
 *
 * @param[in]  - mbox   - The mbox to read from
 * @param[out] - cmdval - The command or operation
 * @param[out] - tfd    - The Virtual file descriptor
 * @param[out] - data   - Data associated, if any (or NULL)
 *
 * @return Error code
 * @retval -1 Failure
 * @retval  0 Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mbox_read(tpp_mbox_t *mbox, unsigned int *tfd, int *cmdval, void **data)
{
#ifdef HAVE_SYS_EVENTFD_H
	uint64_t u;
#else
	char b;
#endif
	tpp_cmd_t *cmd = NULL;

	if (cmdval)
		*cmdval = -1;

	errno = 0;

	tpp_lock(&mbox->mbox_mutex);

	/* read the data from the mbox cmd queue head */
	cmd = (tpp_cmd_t *) tpp_deque(&mbox->mbox_queue);

	/* if no more data, clear all notifications */
	if (cmd == NULL) {
		mbox->mbox_size = 0;
#ifdef HAVE_SYS_EVENTFD_H
		read(mbox->mbox_eventfd, &u, sizeof(uint64_t));
#else
		while (tpp_pipe_read(mbox->mbox_pipe[0], &b, sizeof(char)) == sizeof(char));
#endif
	} else {
		/* reduce from mbox size during read */
		mbox->mbox_size -= cmd->sz;
	}

	tpp_unlock(&mbox->mbox_mutex);

	if (cmd == NULL) {
		errno = EWOULDBLOCK;
		return -1;
	}

	if (tfd)
		*tfd = cmd->tfd;

	if (cmdval)
		*cmdval = cmd->cmdval;

	*data = cmd->data;

	free(cmd);
	return 0;
}

/**
 * @brief
 *	Clear pending commands pertaining to a connection
 *	from this mbox
 *	Called usually when the connection got closed and
 *	the caller wants to clear the pending commands for
 *	that connection from this thread mbox
 *
 * @param[in] - mbox   - The mbox to read from
 * @param[in] - n      - The node/position to start searching from
 * @param[in] - tfd    - The Virtual file descriptor
 * @param[out] - cmdval - Return the cmdval
 * @param[out] - data - Return any data associated
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mbox_clear(tpp_mbox_t *mbox, tpp_que_elem_t **n, unsigned int tfd, short *cmdval, void **data)
{
	tpp_cmd_t *cmd;
	int ret = -1;
	errno = 0;

	tpp_lock(&mbox->mbox_mutex);

	while ((*n = TPP_QUE_NEXT(&mbox->mbox_queue, *n))) {
		cmd = TPP_QUE_DATA(*n);
		if (cmd && cmd->tfd == tfd) {
			*n = tpp_que_del_elem(&mbox->mbox_queue, *n);
			if (cmdval)
				*cmdval = cmd->cmdval;
			if (data)
				*data = cmd->data;
			free(cmd);
			ret = 0;
			break;
		}
	}
	mbox->mbox_size = 0;

	tpp_unlock(&mbox->mbox_mutex);

	return ret;
}

/**
 * @brief
 *	Send a command to the threads msg queue
 *
 * @param[in] - mbox   - The mbox to post to
 * @param[in] - cmdval - The command or operation
 * @param[in] - tfd    - The Virtual file descriptor
 * @param[in] - data   - Any data pointer associated, if any (or NULL)
 * @param[in] - sz     - size of the data
 *
 * @return Error code
 * @retval -1 Failure
 * @retval  0 Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mbox_post(tpp_mbox_t *mbox, unsigned int tfd, char cmdval, void *data, int sz)
{
	tpp_cmd_t *cmd;
	ssize_t s;
#ifdef HAVE_SYS_EVENTFD_H
	uint64_t u;
#else
	char b;
#endif

	errno = 0;
	cmd = malloc(sizeof(tpp_cmd_t));
	if (!cmd) {
		tpp_log(LOG_CRIT, __func__, "Out of memory in em_mbox_post for mbox=%s", mbox->mbox_name);
		return -1;
	}
	cmd->cmdval = cmdval;
	cmd->tfd = tfd;
	cmd->data = data;
	cmd->sz = sz;

	/* add the cmd to the threads queue */
	tpp_lock(&mbox->mbox_mutex);

	if (tpp_enque(&mbox->mbox_queue, cmd) == NULL) {
		tpp_unlock(&mbox->mbox_mutex);
		free(cmd);
		tpp_log(LOG_CRIT, __func__, "Out of memory in em_mbox_post for mbox=%s", mbox->mbox_name);
		return -1;
	}
	
	/* add to the size to global size during enque */
	mbox->mbox_size += sz;

	tpp_unlock(&mbox->mbox_mutex);

	while (1) {
		/* send a notification to the thread */
#ifdef HAVE_SYS_EVENTFD_H
		u = 1;
		s = write(mbox->mbox_eventfd, &u, sizeof(uint64_t));
		if (s == sizeof(uint64_t))
			break;
#else
		b = 1;
		s = tpp_pipe_write(mbox->mbox_pipe[1], &b, sizeof(char));
		if (s == sizeof(char))
			break;
#endif
		if (s == -1) {
			if (errno == EAGAIN || errno == EWOULDBLOCK) {
				/* pipe is full, which is fine, anyway we behave like edge triggered */
				break;
			} else if (errno != EINTR) {
				tpp_log(LOG_CRIT, __func__, "mbox post failed for mbox=%s, errno=%d", mbox->mbox_name, errno);
				return -1;
			}
		}
	}
	return 0;
}

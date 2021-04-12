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

#ifndef	__TPP_H
#define __TPP_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <pbs_config.h>
#include <errno.h>
#include "pbs_internal.h"
#include "auth.h"

#if defined (PBS_HAVE_DEVPOLL)
#define PBS_USE_DEVPOLL
#elif defined (PBS_HAVE_EPOLL)
#define PBS_USE_EPOLL
#elif defined (PBS_HAVE_POLLSET)
#define  PBS_USE_POLLSET
#elif defined (HAVE_POLL)
#define PBS_USE_POLL
#elif defined (HAVE_SELECT)
#define PBS_USE_SELECT
#endif

#if defined (PBS_USE_EPOLL)

#include <sys/epoll.h>

#elif defined (PBS_USE_POLL)

#include <poll.h>

#elif defined (PBS_USE_SELECT)

#if defined(FD_SET_IN_SYS_SELECT_H)
#include <sys/select.h>
#endif

#elif defined (PBS_USE_DEVPOLL)

#include <sys/devpoll.h>

#elif defined (PBS_USE_POLLSET)

#include <sys/poll.h>
#include <sys/pollset.h>
#include <fcntl.h>

#endif

/*
 * Default number of RPP packets to check every server iteration
 */
#define RPP_MAX_PKT_CHECK_DEFAULT	64

/* TPP specific definitions and structures */
#define TPP_DEF_ROUTER_PORT 17001
#define TPP_MAXOPENFD 8192 /* limit for pbs_comm max open files */

/* tpp node types, leaf and router */
#define TPP_LEAF_NODE           1  /* leaf node that does not care about TPP_CTL_LEAVE messages from other leaves */
#define TPP_LEAF_NODE_LISTEN    2  /* leaf node that wants to be notified of TPP_CTL_LEAVE messages from other leaves */
#define TPP_ROUTER_NODE         3  /* router */
#define TPP_AUTH_NODE           4  /* authenticated, but yet unknown node type till a join happens */

extern	int	tpp_fd;
struct tpp_config {
	int    node_type; /* leaf, proxy */
	char   **routers; /* other proxy names (and backups) to connect to */
	int    numthreads;
	char   *node_name; /* list of comma separated node names */
	int    compress;
	int    tcp_keepalive; /* use keepalive? */
	int    tcp_keep_idle;
	int    tcp_keep_intvl;
	int    tcp_keep_probes;
	int    tcp_user_timeout;
	int    buf_limit_per_conn; /* buffer limit per physical connection */
	pbs_auth_config_t *auth_config;
	char **supported_auth_methods;
};

/* TPP specific functions */
extern int tpp_init(struct tpp_config *);
extern void tpp_set_app_net_handler(void (*app_net_down_handler)(void *), void (*app_net_restore_handler)(void *));
extern void tpp_set_logmask(long);
extern int set_tpp_config(struct pbs_config *, struct tpp_config *, char *, int, char *);
extern void free_tpp_config(struct tpp_config *);
extern void DIS_tpp_funcs();
extern int tpp_open(char *, unsigned int);
extern int tpp_close(int);
extern int tpp_eom(int);
extern int tpp_bind(unsigned int);
extern int tpp_poll(void);
extern void tpp_terminate(void);
extern void tpp_shutdown(void);
extern struct sockaddr_in *tpp_getaddr(int);
extern void tpp_add_close_func(int, void (*func)(int));
extern char *tpp_parse_hostname(char *, int *);
extern int tpp_init_router(struct tpp_config *);
extern void tpp_router_shutdown(void);

/* special tpp only multicast function prototypes */
extern int tpp_mcast_open(void);
extern int tpp_mcast_add_strm(int, int, bool);
extern int *tpp_mcast_members(int, int *);
extern int tpp_mcast_send(int, void *, unsigned int, unsigned int);
extern int tpp_mcast_close(int);

/**********************************************************************/
/* em related definitions (external version) */
/**********************************************************************/
#if defined (PBS_USE_POLL)

typedef struct {
	int fd;
	int events;
} em_event_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].events

#define EM_IN	POLLIN
#define EM_OUT	POLLOUT
#define EM_HUP	POLLHUP
#define EM_ERR	POLLERR

#elif defined (PBS_USE_EPOLL)

typedef struct epoll_event em_event_t;

#define EM_GET_FD(ev, i) ev[i].data.fd
#define EM_GET_EVENT(ev, i) ev[i].events

#define EM_IN	EPOLLIN
#define EM_OUT	EPOLLOUT
#define EM_HUP	EPOLLHUP
#define EM_ERR	EPOLLERR

#elif defined (PBS_USE_POLLSET)

typedef struct pollfd em_event_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].revents

#define EM_IN	POLLIN
#define EM_OUT	POLLOUT
#define EM_HUP	POLLHUP
#define EM_ERR	POLLERR

#elif defined (PBS_USE_SELECT)

typedef struct {
	int fd;
	int events;
} em_event_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].events

#define EM_IN	0x001
#define EM_OUT	0x002
#define EM_HUP	0x004
#define EM_ERR	0x008

#elif defined (PBS_USE_DEVPOLL)

typedef struct pollfd em_event_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].revents

#define EM_IN	POLLIN
#define EM_OUT	POLLOUT
#define EM_HUP	POLLHUP
#define EM_ERR	POLLERR

#endif

/* platform independent functions that handle the underlying platform specific event
 * handling mechanism. Internally it could use epoll, poll, select etc, depending on the
 * platform.
 */
void *tpp_em_init(int);
void tpp_em_destroy(void *);
int tpp_em_add_fd(void *, int, int);
int tpp_em_mod_fd(void *, int, int);
int tpp_em_del_fd(void *, int);
int tpp_em_wait(void *, em_event_t **, int);
#ifndef WIN32
int tpp_em_pwait(void *, em_event_t **, int, const sigset_t *);
#else
int tpp_em_wait_win(void *, em_event_t **, int);
#endif

extern char *get_all_ips(char *, char *, size_t);

#ifdef	__cplusplus
}
#endif
#endif	/* _TPP_H */

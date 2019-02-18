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

#ifndef	__TPP_PLATFORM_H
#define __TPP_PLATFORM_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <pbs_config.h>

#include <sys/time.h>
#include <limits.h>
#include <time.h>
#include <pthread.h>
#include <errno.h>


#ifndef WIN32


#define tpp_pipe_cr(a)               pipe(a)
#define tpp_pipe_read(a, b, c)         read(a, b, c)
#define tpp_pipe_write(a, b, c)        write(a, b, c)
#define tpp_pipe_close(a)            close(a)

#define tpp_sock_socket(a, b, c)       socket(a, b, c)
#define tpp_sock_bind(a, b, c)         bind(a, b, c)
#define tpp_sock_listen(a, b)         listen(a, b)
#define tpp_sock_accept(a, b, c)       accept(a, b, c)
#define tpp_sock_connect(a, b, c)      connect(a, b, c)
#define tpp_sock_recv(a, b, c, d)       recv(a, b, c, d)
#define tpp_sock_send(a, b, c, d)       send(a, b, c, d)
#define tpp_sock_select(a, b, c, d, e)   select(a, b, c, d, e)
#define tpp_sock_close(a)            close(a)
#define tpp_sock_getsockopt(a, b, c, d, e)   getsockopt(a, b, c, d, e)
#define tpp_sock_setsockopt(a, b, c, d, e)   setsockopt(a, b, c, d, e)

#else

#define EINPROGRESS   EAGAIN

int tpp_pipe_cr(int fds[2]);
int tpp_pipe_read(int s, char *buf, int len);
int tpp_pipe_write(int s, char *buf, int len);
int tpp_pipe_close(int s);

int tpp_sock_socket(int af, int type, int protocol);
int tpp_sock_listen(int s, int backlog);
int tpp_sock_accept(int s, struct sockaddr *addr, int *addrlen);
int tpp_sock_bind(int s, const struct sockaddr *name, int namelen);
int tpp_sock_connect(int s, const struct sockaddr *name, int namelen);
int tpp_sock_recv(int s, char *buf, int len, int flags);
int tpp_sock_send(int s, const char *buf, int len, int flags);
int tpp_sock_select(int nfds, fd_set *readfds, fd_set *writefds, fd_set *exceptfds, const struct timeval *timeout);
int tpp_sock_close(int s);
int tpp_sock_getsockopt(int s, int level, int optname, int *optval, int *optlen);
int tpp_sock_setsockopt(int s, int level, int optname, const int *optval, int optlen);

#endif

int tpp_sock_layer_init();
int tpp_get_nfiles();
int set_pipe_disposition();
int tpp_sock_attempt_connection(int fd, char *host, int port);
void tpp_invalidate_thrd_handle(pthread_t *thrd);
int tpp_is_valid_thrd(pthread_t thrd);
#endif

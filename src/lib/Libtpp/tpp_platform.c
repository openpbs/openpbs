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
 * @file	tpp_platform.c
 *
 * @brief	Miscellaneous socket and pipe routes for WIndows and Unix
 *
 *
 */
#include <pbs_config.h>

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
#include <netinet/tcp.h>
#include <sys/resource.h>
#include <signal.h>
#include "tpp_internal.h"

#ifdef WIN32

/**
 * @brief
 *	Emulate pipe by using sockets on windows
 *
 * @param[in] - fds - returns the opened pipe fds
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
tpp_pipe_cr(int fds[2])
{
	SOCKET listenfd;
	struct sockaddr_in serv_addr;
	pbs_socklen_t len = sizeof(serv_addr);
	char *op;

	errno = 0;
	fds[0] = fds[1] = INVALID_SOCKET;

	if ((listenfd = socket(AF_INET, SOCK_STREAM, 0)) == INVALID_SOCKET) {
		op = "socket";
		goto tpp_pipe_err;
	}

	memset(&serv_addr, 0, len);
	serv_addr.sin_family = AF_INET;
	serv_addr.sin_port = htons(0);
	serv_addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	if (bind(listenfd, (SOCKADDR *) &serv_addr, len) == SOCKET_ERROR) {
		op = "bind";
		goto tpp_pipe_err;
	}

	if (listen(listenfd, 1) == SOCKET_ERROR) {
		op = "listen";
		goto tpp_pipe_err;
	}

	if (getsockname(listenfd, (SOCKADDR *) &serv_addr, &len) == SOCKET_ERROR) {
		op = "getsockname";
		goto tpp_pipe_err;
	}

	if ((fds[1] = socket(PF_INET, SOCK_STREAM, 0)) == INVALID_SOCKET) {
		op = "socket";
		goto tpp_pipe_err;
	}

	if (tpp_sock_connect(fds[1], (SOCKADDR *) &serv_addr, len) == SOCKET_ERROR) {
		op = "connect";
		goto tpp_pipe_err;
	}

	if ((fds[0] = accept(listenfd, (SOCKADDR *) &serv_addr, &len)) == INVALID_SOCKET) {
		op = "accept";
		goto tpp_pipe_err;
	}

	closesocket(listenfd);
	return 0;

tpp_pipe_err:
	closesocket(listenfd);
	if (fds[0] != INVALID_SOCKET)
		closesocket(fds[0]);
	if (fds[1] != INVALID_SOCKET)
		closesocket(fds[1]);

	errno = tr_2_errno(WSAGetLastError());
	tpp_log(LOG_CRIT, __func__, "%s failed, winsock errno= %d", op, WSAGetLastError());
	return -1;
}

/**
 * @brief
 *	Emulate pipe read by using sockets on windows
 *
 * @param[in] - fd  - pipe file descriptor
 * @param[in] - buf - data buffer to read from pipe
 * @param[in] - len - length of the data buffer
 *
 * @return  Amount of data written
 * @retval  0 - Failure - close pipe
 * @retval  >0 - Amount of data written
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_pipe_read(int fd, char *buf, int len)
{
	int ret = recv(fd, buf, len, 0);
	if (ret == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return ret;
}

/**
 * @brief
 *	Emulate pipe write by using sockets on windows
 *
 * @param[in] - fd  - pipe file descriptor
 * @param[in] - buf - data buffer to write to pipe
 * @param[in] - len - length of the data buffer
 *
 * @return  Amount of data written
 * @retval  0 - Failure - close pipe
 * @retval  >0 - Amount of data written
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_pipe_write(int fd, char *buf, int len)
{
	int ret = send(fd, buf, len, 0);
	if (ret == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return ret;
}

/**
 * @brief
 *	Emulate pipe close by using sockets on windows
 *
 * @param[in] - fd  - pipe file descriptor

 * @return  return value of windows closesocket
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_pipe_close(int fd)
{
	return closesocket(fd);
}

/*
 * wrapper to call windows socket() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_socket(int af, int type, int protocol)
{
	int fd;
	DWORD dwFlags = 0;

	/*
	 * Make TPP sockets un-inheritable (windows).
	 *
	 * Windows has a quirky implementation of socket inheritence due to
	 * the support for Layered Service Providers. If Firewall/antivirus
	 * are installed, the socket handle could get inherited despite
	 * the fact that we are setting this as un-inheritable via a call
	 * post the socket creation time.
	 *
	 * Use WSA_FLAG_NO_HANDLE_INHERIT available in newer windows
	 * versions (7SP1 onwards) in the call to WSASocket().
	 *
	 * Also use the SetHandleInformation for older windows. (This may
	 * not work with LSP's installed.
	 *
	 */
#ifdef WSA_FLAG_NO_HANDLE_INHERIT
	dwFlags = WSA_FLAG_NO_HANDLE_INHERIT;
#endif
	if ((fd = WSASocket(af, type, protocol, NULL, 0, dwFlags)) == INVALID_SOCKET) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}

	if (SetHandleInformation((HANDLE) fd, HANDLE_FLAG_INHERIT, 0) == 0) {
		errno = tr_2_errno(WSAGetLastError());
		closesocket(fd);
		return -1;
	}

	return fd;
}

/*
 * wrapper to call windows listen() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_listen(int s, int backlog)
{
	if (listen(s, backlog) == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return 0;
}

/*
 * wrapper to call windows accept() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_accept(int s, struct sockaddr *addr, int *addrlen)
{
	int fd;
	if ((fd = accept(s, addr, addrlen)) == INVALID_SOCKET) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return fd;
}

/*
 * wrapper to call windows bind() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_bind(int s, const struct sockaddr *name, int namelen)
{
	if (bind(s, name, namelen) == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return 0;
}

/*
 * wrapper to call windows connect() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_connect(int s, const struct sockaddr *name, int namelen)
{
	if (connect(s, name, namelen) == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return 0;
}

/*
 * wrapper to call windows recv() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_recv(int s, char *buf, int len, int flags)
{
	int ret = recv(s, buf, len, flags);
	if (ret == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return ret;
}

/*
 * wrapper to call windows send() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_send(int s, const char *buf, int len, int flags)
{
	int ret = send(s, buf, len, flags);
	if (ret == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return ret;
}

/*
 * wrapper to call windows select() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_select(int nfds, fd_set *readfds, fd_set *writefds, fd_set *exceptfds, const struct timeval *timeout)
{
	int nready = select(nfds, readfds, writefds, exceptfds, timeout);
	if (nready == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return nready;
}

/*
 * wrapper to call windows closesocket() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_close(int s)
{
	if (closesocket(s) == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return 0;
}

/*
 * wrapper to call windows getsockopt() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_getsockopt(int s, int level, int optname, int *optval, int *optlen)
{
	if (getsockopt(s, level, optname, (char *) optval, optlen) == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return 0;
}

/*
 * wrapper to call windows setsockopt() and map windows
 * error code to errno and massage the return value
 * so that callers do not need conditionally compiled
 * code
 */
int
tpp_sock_setsockopt(int s, int level, int optname, const int *optval, int optlen)
{
	if (setsockopt(s, level, optname, (const char *) optval, optlen) == SOCKET_ERROR) {
		errno = tr_2_errno(WSAGetLastError());
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Map windows error number to errno
 *
 * @param[in] - win_errno - Windows error

 * @return  errno mapped value
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tr_2_errno(int win_errno)
{
	int ret = 0;
	/* convert only a few to unix errors,
	 * for others, we do not care,
	 */
	switch (win_errno) {
		case WSAEINVAL: ret = EINVAL; break;
		case WSAEINPROGRESS: ret = EINPROGRESS; break;
		case WSAEINTR: ret = EINTR; break;
		case WSAECONNREFUSED: ret = ECONNREFUSED; break;
		case WSAEWOULDBLOCK: ret = EWOULDBLOCK; break;
		case WSAEADDRINUSE: ret = EADDRINUSE; break;
		case WSAEADDRNOTAVAIL: ret = EADDRNOTAVAIL; break;
		default: ret = EINVAL;
	}
	return ret;
}

/**
 * @brief
 *	Initialize winsock
 *
 * @return  errro code
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_sock_layer_init()
{
	WSADATA	data;
	if (WSAStartup(MAKEWORD(2, 2), &data)) {
		tpp_log(LOG_CRIT, NULL, "winsock_init failed! error=%d", WSAGetLastError());
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Retrieve the value of nfiles from OS settings
 *
 * @return  nfiles value, for windows return
 *          constant MAX_CON
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_get_nfiles()
{
	return MAX_CON;
}

/**
 * @brief
 *	Setup SIGPIPE disposition properly.
 *  NOP on windows
 *
 * @return  errro code
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
set_pipe_disposition()
{
	return 0;
}

#else

/**
 * @brief
 *	Initialize socket layer
 *  NOP on non-WIndows
 *
 * @return  errro code
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_sock_layer_init()
{
	return 0;
}

/**
 * @brief
 *	Retrieve the value of nfiles from OS settings
 *
 * @return  nfiles value
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_get_nfiles()
{
	struct rlimit rlp;

	if (getrlimit(RLIMIT_NOFILE, &rlp) == -1) {
		tpp_log(LOG_CRIT, __func__, "getrlimit failed");
		return -1;
	}

	tpp_log(LOG_INFO, NULL, "Max files allowed = %ld", (long) rlp.rlim_cur);

	return (rlp.rlim_cur);
}

/**
 * @brief
 *	Setup SIGPIPE disposition properly
 *
 * @return  errro code
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
set_pipe_disposition()
{
	struct sigaction act;
	struct sigaction oact;

	/*
	 * Check if SIGPIPE's disposition is set to default, if so, set to ignore;
	 * else we assume the application can handle SIGPIPE without quitting.
	 *
	 * MSG_NOSIGNAL is linux specific, and SO_NOSIGPIPE is not portable either.
	 * As of now we do not need any more elegant solution than just ignoring
	 * the sigpipe, if not already handled by the application.
	 */
	if (sigaction(SIGPIPE, NULL, &oact) == 0) {
		if (oact.sa_handler == SIG_DFL) {
			act.sa_handler = SIG_IGN;
			if (sigaction(SIGPIPE, &act, &oact) != 0) {
				tpp_log(LOG_CRIT, __func__, "Could not set SIGPIPE to IGN");
				return -1;
			}
		}
	} else {
		tpp_log(LOG_CRIT, __func__, "Could not query SIGPIPEs disposition");
		return -1;
	}
	return 0;
}
#endif

/**
 * @brief
 *	Find the hostname associated with the provided ip
 *
 * @param[in] addr - The ip address for which we need to find the hostname
 * @param[in] host - The buffer to which to copy the hostname to
 * @param[in] len  - The length of the output buffer
 *
 * @return  error code
 * @retval  !0 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_sock_resolve_ip(tpp_addr_t *addr, char *host, int len)
{
	socklen_t salen;
	struct sockaddr *sa;
	struct sockaddr_in6 sa_in6;
	struct sockaddr_in sa_in;
	int rc;

	if (addr->family == TPP_ADDR_FAMILY_IPV4) {
		memcpy(&sa_in.sin_addr, (struct sockaddr_in *) addr->ip, sizeof(sa_in.sin_addr));
		salen = sizeof(struct sockaddr_in);
		sa = (struct sockaddr *) &sa_in;
		sa->sa_family = AF_INET;
	} else if (addr->family == TPP_ADDR_FAMILY_IPV6) {
		memcpy(&sa_in6.sin6_addr, (struct sockaddr_in *) addr->ip, sizeof(sa_in6.sin6_addr));
		sa = (struct sockaddr *) &sa_in6;
		salen = sizeof(struct sockaddr_in6);
		sa->sa_family = AF_INET6;
	} else
		return -1;

	rc = getnameinfo(sa, salen, host, len, NULL, 0, 0);
	if (rc != 0) {
		TPP_DBPRT("Error: %s", gai_strerror(rc));
	}
	return rc;
}

/**
 * @brief
 *	Resolve the hostname to ip address list
 *
 * @param[in]  host  - The hostname to resolve
 * @param[out] count - The count of addresses returned
 *
 * @return  Array of address resolved from the host
 * @retval  NULL  - Failure
 * @retval  !NULL - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
tpp_addr_t *
tpp_sock_resolve_host(char *host, int *count)
{
	tpp_addr_t *ips = NULL;
	void *tmp;
	int i, j;
	struct addrinfo *aip, *pai;
	struct addrinfo hints;
	int rc = 0;

	errno = 0;
	*count = 0;

	memset(&hints, 0, sizeof(struct addrinfo));
	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_STREAM;
	hints.ai_protocol = IPPROTO_TCP;

#ifndef WIN32
	/* 
	 * introducing a new mutex to prevent child process from 
	 * inheriting getaddrinfo mutex using pthread_atfork handlers
	 */
	tpp_lock(&tpp_nslookup_mutex);
#endif
	rc = getaddrinfo(host, NULL, &hints, &pai);
	/* unlock nslookup mutex */
#ifndef WIN32
		tpp_unlock(&tpp_nslookup_mutex);
#endif
	if (rc != 0) {
		tpp_log(LOG_CRIT, NULL, "Error %d resolving %s", rc, host);
		return NULL;
	}

	*count = 0;
	for (aip = pai; aip != NULL; aip = aip->ai_next) {
		if (aip->ai_family == AF_INET) { /* for now only count IPv4 addresses */
			(*count)++;
		}
	}

	if (*count == 0) {
		tpp_log(LOG_CRIT, NULL, "Could not find any usable IP address for host %s", host);
		return NULL;
	}

	ips = calloc(*count, sizeof(tpp_addr_t));
	if (!ips) {
		*count = 0;
		return NULL;
	}

	i = 0;
	for (aip = pai; aip != NULL; aip = aip->ai_next) {
		/* skip non-IPv4 addresses */
		/*if (aip->ai_family == AF_INET || aip->ai_family == AF_INET6) {*/
		if (aip->ai_family == AF_INET) { /* for now only work with IPv4 */
			if (aip->ai_family == AF_INET) {
				struct sockaddr_in *sa = (struct sockaddr_in *) aip->ai_addr;
				if (ntohl(sa->sin_addr.s_addr) >> 24 == IN_LOOPBACKNET)
					continue;
				memcpy(&ips[i].ip, &sa->sin_addr, sizeof(sa->sin_addr));
			} else if (aip->ai_family == AF_INET6) {
				struct sockaddr_in6 *sa6 = (struct sockaddr_in6 *) aip->ai_addr;
				memcpy(&ips[i].ip, &sa6->sin6_addr, sizeof(sa6->sin6_addr));
			}
			ips[i].family = (aip->ai_family == AF_INET6)? TPP_ADDR_FAMILY_IPV6 : TPP_ADDR_FAMILY_IPV4;
			ips[i].port = 0;

			for (j=0; j < i; j++) {
				/* check for duplicate ip addresses dont add if duplicate */
				if (memcmp(&ips[j].ip, &ips[i].ip, sizeof(ips[j].ip)) == 0) {
					break;
				}
			}
			if (j == i) {
				/* did not find duplicate so use this slot */
				i++;
			}
		}
	}
	freeaddrinfo(pai);

	if (i == 0) {
		free(ips);
		*count = 0;
		return NULL;
	}

	if (i < *count) {
		/* try to resize the buffer, don't bother if resize failed */
		tmp = realloc(ips, i*sizeof(tpp_addr_t));
		if (tmp)
			ips = tmp;
	}
	*count = i; /* adjust count */

	return ips;
}

/**
 * @brief
 *	Helper function to initiate a connection to a remote host
 *
 *
 * @param[in] conn - The physical connection structure
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_sock_attempt_connection(int fd, char *host, int port)
{
	struct sockaddr_in dest_addr;
	int rc = 0;
	tpp_addr_t *addr;
	int count = 0, i;

	errno = 0;

	addr = tpp_sock_resolve_host(host, &count);
	if (count == 0 || addr == NULL) {
		errno = EADDRNOTAVAIL;
		return -1;
	}

	for (i = 0; i < count; i++) {
		if (addr[i].family == TPP_ADDR_FAMILY_IPV4)
			break;
	}
	if (i == count) {
		/* did not find a ipv4 address, fail for now */
		free(addr);
		errno  = EADDRNOTAVAIL;
		return -1;
	}

	dest_addr.sin_family = AF_INET;
	dest_addr.sin_port = htons(port);

	memcpy((char *)&dest_addr.sin_addr, &addr[i].ip, sizeof(dest_addr.sin_addr));
	rc = tpp_sock_connect(fd, (struct sockaddr *)&dest_addr, sizeof(dest_addr));
	free(addr);

	return rc;
}

/**
 * @brief
 *	Initialize thrd handle to an invalid value
 *
 * @param[in] thrd - the thrd handle to invalidate
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_invalidate_thrd_handle(pthread_t *thrd)
{
#ifdef WIN32
	thrd->thHandle = INVALID_HANDLE_VALUE;
	thrd->thId = -1;
#else
	*thrd = -1; /* initialize to -1 */
#endif
}

/**
 * @brief
 *	Check if thrd has a valid handle
 *
 * @param[in] thrd - the thrd handle to check
 *
 * @return  Error code
 * @retval   1 - Valid
 * @retval   0 - invalid handle
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_is_valid_thrd(pthread_t thrd)
{
#ifndef WIN32
	if (thrd != -1)
		return 1;
#else
	if (thrd.thHandle != INVALID_HANDLE_VALUE)
		return 1;
#endif
	return 0;
}

/*
 * Copyright (c) 1983 Regents of the University of California.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms are permitted
 * provided that the above copyright notice and this paragraph are
 * duplicated in all such forms and that any documentation,
 * advertising materials, and other materials related to such
 * distribution and use acknowledge that the software was developed
 * by the University of California, Berkeley.  The name of the
 * University may not be used to endorse or promote products derived
 * from this software without specific prior written permission.
 * THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, WITHOUT LIMITATION, THE IMPLIED
 * WARRANTIES OF MERCHANTIBILITY AND FITNESS FOR A PARTICULAR PURPOSE.
 */

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
#if defined(LIBC_SCCS) && !defined(lint)
static char sccsid[] = "@(#)rcmd.c	5.17 (Berkeley) 6/27/88";
#endif /* LIBC_SCCS and not lint */

#include <stdio.h>
#include <errno.h>
#ifdef WIN32
#include <windows.h>
#include "win.h"
#define EADDRINUSE	WSAEADDRINUSE
#define ECONNREFUSED	WSAECONNREFUSED
#define EADDRNOTAVAIL	WSAEADDRNOTAVAIL
#else
#include "inetprivate.h"
#include <pwd.h>
#include <sys/file.h>
#include <sys/signal.h>
#endif
#include <sys/stat.h>
/**
 * @file	rcmd.c
 */
/**
 * @brief
 *	binds a available reserved port to a socket and returns the socket.
 *
 * @param[in] alport - port number
 *
 * @return	int
 * @retval	socket fd	success
 * @retval	-1		error
 *
 */
int
rresvport(int *alport)
{
	struct sockaddr_in sin;
	int s;

	sin.sin_family = AF_INET;
	sin.sin_addr.s_addr = INADDR_ANY;
	s = socket(AF_INET, SOCK_STREAM, 0);
	if (s < 0) {
		fprintf(stderr, "socket returned -1 with error=%d\n",
			WSAGetLastError());
		return (-1);
	}
	for (;;) {
		sin.sin_port = htons((u_short)*alport);
		if (bind(s, (struct sockaddr *)&sin, sizeof(sin)) >= 0)
			return (s);

#ifdef WIN32
		errno = WSAGetLastError();
#endif

		if (errno != EADDRINUSE && errno != EADDRNOTAVAIL) {
#ifdef WIN32
			(void) closesocket(s);
#else
			(void) close(s);
#endif
			return (-1);
		}
		(*alport)--;
		if (*alport == IPPORT_RESERVED/2) {
#ifdef WIN32
			(void) closesocket(s);
#else
			(void) close(s);
#endif
			errno = EAGAIN;		/* close */
			return (-1);
		}
	}
}

/**
 * @brief
 *	used by the superuser to execute a command on a remote machine using 
 *	an authentication scheme based on privileged port numbers
 *
 * @param[in] ahost - host name
 * @param[in] rport - remote port
 * @param[in] locuser - local user name
 * @param[in] remuser - remote user name
 * @param[in] cmd - cmd to be executed
 * @param[in] fd2p - auxiliary channel to a control process
 *
 * @return	int
 * @retval	socket descriptor	success
 * @retval	-1			error
 *
 */
int
rcmd(char **ahost,
	unsigned short rport,
	const char *locuser,
	const char *remuser,
	const char *cmd,
	int *fd2p)
{
	int s, timo = 1;
#ifdef F_SETOWN
	pid_t pid;
#endif
	struct sockaddr_in sin, from;
	char c;
	int lport = IPPORT_RESERVED - 1;
	struct hostent *hp;

#ifdef F_SETOWN
	pid = getpid();
#endif
	hp = gethostbyname(*ahost);
	if (hp == 0) {
		fprintf(stderr, "%s: unknown host\n", *ahost);
		return (-1);
	}
	*ahost = hp->h_name;
	for (;;) {
		s = rresvport(&lport);
		if (s < 0) {
			if (errno == EAGAIN)
				fprintf(stderr, "socket: All ports in use\n");
			else
				perror("rcmd: socket");
			return (-1);
		}
#ifdef F_SETOWN
		fcntl(s, F_SETOWN, pid);
#endif
		sin.sin_family = hp->h_addrtype;
#ifdef WIN32
		memcpy((void *)&sin.sin_addr, (void *)hp->h_addr_list[0],
			hp->h_length);
#else
		bcopy(hp->h_addr_list[0], (caddr_t)&sin.sin_addr, hp->h_length);
#endif
		sin.sin_port = rport;
		if (connect(s, (struct sockaddr *)&sin, sizeof(sin)) >= 0)
			break;

#ifdef WIN32
		errno = WSAGetLastError();
		(void) closesocket(s);
#else
		(void) close(s);
#endif
		if (errno == EADDRINUSE) {
			lport--;
			continue;
		}
		if (errno == ECONNREFUSED && timo <= 16) {
			sleep(timo);
			timo *= 2;
			continue;
		}
		if (hp->h_addr_list[1] != NULL) {
			int oerrno = errno;

			fprintf(stderr,
				"connect to address %s: ", inet_ntoa(sin.sin_addr));
			errno = oerrno;
			perror(0);
			hp->h_addr_list++;
#ifdef WIN32
			memcpy((void *)&sin.sin_addr,
				(void *)hp->h_addr_list[0], hp->h_length);
#else
			bcopy(hp->h_addr_list[0], (caddr_t)&sin.sin_addr,
				hp->h_length);
#endif

			fprintf(stderr,	"Trying %s...\n",
				inet_ntoa(sin.sin_addr));
			continue;
		}
		perror(hp->h_name);
		return (-1);
	}
	lport--;
	if (fd2p == 0) {
#ifdef WIN32
		send(s, "", 1, 0);
#else
		write(s, "", 1);
#endif
		lport = 0;
	} else {
		char num[8];
		int s2 = rresvport(&lport), s3;
		int len = sizeof(from);

		if (s2 < 0)
			goto bad;
		listen(s2, 1);
		(void) snprintf(num, sizeof(num), "%d", lport);
#ifdef WIN32
		if (send(s, num, strlen(num)+1, 0) != strlen(num)+1) {
			perror("write: setting up stderr");
			(void) closesocket(s2);
			goto bad;
		}
#else
		if (write(s, num, strlen(num)+1) != strlen(num)+1) {
			perror("write: setting up stderr");
			(void) close(s2);
			goto bad;
		}
#endif
		s3 = accept(s2, (struct sockaddr *)&from, &len);
#ifdef WIN32
		(void) closesocket(s2);
#else
		(void) close(s2);
#endif
		if (s3 < 0) {
			perror("accept");
			lport = 0;
			goto bad;
		}
		*fd2p = s3;
		from.sin_port = ntohs((u_short)from.sin_port);
		if (from.sin_family != AF_INET ||
			from.sin_port >= IPPORT_RESERVED) {
			fprintf(stderr,
				"socket: protocol failure in circuit setup.\n");
			goto bad2;
		}
	}
#ifdef WIN32
	(void) send(s, locuser, strlen(locuser)+1, 0);
	(void) send(s, remuser, strlen(remuser)+1, 0);
	(void) send(s, cmd, strlen(cmd)+1, 0);
#else
	(void) write(s, locuser, strlen(locuser)+1);
	(void) write(s, remuser, strlen(remuser)+1);
	(void) write(s, cmd, strlen(cmd)+1);
#endif

#ifdef WIN32
	if (recv(s, &c, 1, 0) != 1)
#else
	if (read(s, &c, 1) != 1)
#endif
	{
		perror(*ahost);
		goto bad2;
	}
	if (c != 0) {

#ifdef WIN32
		while (recv(s, &c, 1, 0) == 1) {
			(void) send(2, &c, 1, 0);
			if (c == '\n')
				break;
		}
#else
		while (read(s, &c, 1) == 1) {
			(void) write(2, &c, 1);
			if (c == '\n')
				break;
		}
#endif
		goto bad2;
	}
	return (s);
bad2:
	if (lport)
#ifdef WIN32
		(void) closesocket(*fd2p);
#else
		(void) close(*fd2p);
#endif
bad:

#ifdef WIN32
	(void) closesocket(s);
#else
	(void) close(s);
#endif
	return (-1);
}


/**
 * @brief
 *	 rcmd2: like rcmd() except 2 new arguments are passed:
 *	passl (password credential length) and passb
 *	(password credential buffer) which are transmitted to rshd.
 *
 * @param[in] ahost - host name
 * @param[in] rport - remote port
 * @param[in] locuser - local user name
 * @param[in] passl - password credential length
 * @param[in] passb - password credential buffer
 * @param[in] remuser - remote user name
 * @param[in] cmd - cmd to be executed
 * @param[in] fd2p - auxiliary channel to a control process
 *
 * @return      int
 * @retval      socket descriptor       success
 * @retval      -1                      error
 *
 */
int
rcmd2(char **ahost,
	unsigned short rport,
	const char *locuser,
	const char *remuser,
	char *passb,
	size_t passl,
	const char *cmd,
	int *fd2p)
{
	int s, timo = 1;
	int run_rcmd = 0;
#ifdef F_SETOWN
	pid_t pid;
#endif
	struct sockaddr_in sin, from;
	char c;
	int lport = IPPORT_RESERVED - 1;
	struct hostent *hp;

#ifdef F_SETOWN
	pid = getpid();
#endif
	hp = gethostbyname(*ahost);
	if (hp == 0) {
		fprintf(stderr, "%s: unknown host\n", *ahost);
		return (-1);
	}
	*ahost = hp->h_name;
	for (;;) {
		s = rresvport(&lport);
		if (s < 0) {
			if (errno == EAGAIN)
				fprintf(stderr, "socket: All ports in use\n");
			else
				perror("rcmd: socket");
			return (-1);
		}
#ifdef F_SETOWN
		fcntl(s, F_SETOWN, pid);
#endif
		sin.sin_family = hp->h_addrtype;
#ifdef WIN32
		memcpy((void *)&sin.sin_addr, (void *)hp->h_addr_list[0],
			hp->h_length);
#else
		bcopy(hp->h_addr_list[0], (caddr_t)&sin.sin_addr, hp->h_length);
#endif
		sin.sin_port = rport;
		if (connect(s, (struct sockaddr *)&sin, sizeof(sin)) >= 0)
			break;

#ifdef WIN32
		errno = WSAGetLastError();
		(void) closesocket(s);
#else
		(void) close(s);
#endif
		if (errno == EADDRINUSE) {
			lport--;
			continue;
		}
		if (errno == ECONNREFUSED && timo <= 16) {
			sleep(timo);
			timo *= 2;
			continue;
		}
		if (hp->h_addr_list[1] != NULL) {
			int oerrno = errno;

			fprintf(stderr,
				"connect to address %s: ", inet_ntoa(sin.sin_addr));
			errno = oerrno;
			perror(0);
			hp->h_addr_list++;
#ifdef WIN32
			memcpy((void *)&sin.sin_addr,
				(void *)hp->h_addr_list[0], hp->h_length);
#else
			bcopy(hp->h_addr_list[0], (caddr_t)&sin.sin_addr,
				hp->h_length);
#endif

			fprintf(stderr,	"Trying %s...\n",
				inet_ntoa(sin.sin_addr));
			continue;
		}
		perror(hp->h_name);
		return (-1);
	}
	lport--;
	if (fd2p == 0) {
#ifdef WIN32
		send(s, "", 1, 0);
#else
		write(s, "", 1);
#endif
		lport = 0;
	} else {
		char num[8];
		int s2 = rresvport(&lport), s3;
		int len = sizeof(from);

		if (s2 < 0)
			goto bad;
		listen(s2, 1);
		(void) snprintf(num, sizeof(num), "%d", lport);
#ifdef WIN32
		if (send(s, num, strlen(num)+1, 0) != strlen(num)+1) {
			perror("write: setting up stderr");
			(void) closesocket(s2);
			goto bad;
		}
#else
		if (write(s, num, strlen(num)+1) != strlen(num)+1) {
			perror("write: setting up stderr");
			(void) close(s2);
			goto bad;
		}
#endif
		s3 = accept(s2, (struct sockaddr *)&from, &len);
#ifdef WIN32
		(void) closesocket(s2);
#else
		(void) close(s2);
#endif
		if (s3 < 0) {
			perror("accept");
			lport = 0;
			goto bad;
		}
		*fd2p = s3;
		from.sin_port = ntohs((u_short)from.sin_port);
		if (from.sin_family != AF_INET ||
			from.sin_port >= IPPORT_RESERVED) {
			fprintf(stderr,
				"socket: protocol failure in circuit setup.\n");
			goto bad2;
		}
	}
#ifdef WIN32
	(void) send(s, locuser, strlen(locuser)+1, 0);
	(void) send(s, remuser, strlen(remuser)+1, 0);

	if ((passl > 0) && (passb != NULL)) { /* send a password req */
		char sendbuf[7];
		char repbuf[11];
		int  slen;

		strcpy(sendbuf, "rcp -E");
		(void) send(s, sendbuf, strlen(sendbuf)+1, 0);

		slen = sizeof(repbuf);
		if ((recv(s, repbuf, slen, 0) != slen) ||
			(strcmp(repbuf, "cred recvd") != 0)) {

			run_rcmd = 1;
			goto bad2;
		}

		(void) send(s, (const char *)&passl, sizeof(size_t), 0);
		(void) send(s, (const char *)passb, passl, 0);
	}

	(void) send(s, cmd, strlen(cmd)+1, 0);
#else
	(void) write(s, locuser, strlen(locuser)+1);
	(void) write(s, remuser, strlen(remuser)+1);
	(void) write(s, cmd, strlen(cmd)+1);
#endif

#ifdef WIN32
	if (recv(s, &c, 1, 0) != 1)
#else
	if (read(s, &c, 1) != 1)
#endif
	{
		perror(*ahost);
		goto bad2;
	}
	if (c != 0) {

#ifdef WIN32
		while (recv(s, &c, 1, 0) == 1) {
			(void) send(2, &c, 1, 0);
			if (c == '\n')
				break;
		}
#else
		while (read(s, &c, 1) == 1) {
			(void) write(2, &c, 1);
			if (c == '\n')
				break;
		}
#endif
		goto bad2;
	}
	return (s);
bad2:
	if (lport)
#ifdef WIN32
		(void) closesocket(*fd2p);
#else
		(void) close(*fd2p);
#endif
bad:

#ifdef WIN32
	(void) closesocket(s);
#else
	(void) close(s);
#endif
	if (run_rcmd) {
		return (rcmd(ahost, rport, locuser, remuser, cmd, fd2p));
	}

	return (-1);
}

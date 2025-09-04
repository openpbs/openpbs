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

#ifndef _PORT_FORWARDING_H
#define _PORT_FORWARDING_H
#ifdef __cplusplus
extern "C" {
#endif

/*Defines used by port_forwarding.c*/
/* Max size of buffer to store data*/
#define PF_BUF_SIZE 8192

/* Limits the number of simultaneous X applications that a single job
 can run in the background to 24 . 1 socket fd is used for storing
 the X11 listening socket fd and 2 socket fds are used whenever an
 X application is started . Hence (24*2+1)=49 fds will be used when
 an attempt is make to start 24 X applications in the background .*/
#define NUM_SOCKS 50

/* Attempt to bind to a available port in the range of 6000+X11OFFSET to
 6000+X11OFFSET+MAX_DISPLAYS */
#define MAX_DISPLAYS 500
#define X11OFFSET 50

#define X_PORT 6000

/* derived from XF4/xc/lib/dps/Xlibnet.h */
#ifndef X_UNIX_PATH
#define X_UNIX_PATH "/tmp/.X11-unix/X%u"
#endif /* X_UNIX_PATH */

#ifndef NI_MAXSERV
#define NI_MAXSERV 32
#endif /* !NI_MAXSERV */

#define QSUB_SIDE 1
#define EXEC_HOST_SIDE 0

/*
 * Structure which maintains the relationship between the producer/consumer
 * sockets and also about the length of the data read/written.
 */
struct pfwdsock {
	int sock;
	int listening;
	int remotesock;
	int bufavail;
	int bufwritten;
	int active;
	int peer;
	char buff[PF_BUF_SIZE];
};
/*Functions available in port_forwarding.h*/
void port_forwarder(struct pfwdsock *, int (*connfunc)(char *phost, long pport),
		    char *, int, int inter_read_sock, int (*readfunc)(int), void (*logfunc)(char *),
		    int is_qsub_side, char *auth_method, char *jobid);
int connect_local_xsocket(u_int);
int x11_connect_display(char *, long);
int set_nonblocking(int);

#ifdef __cplusplus
}
#endif
#endif /* _PORT_FORWARDING_H */

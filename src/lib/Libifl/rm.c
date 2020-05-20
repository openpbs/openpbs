/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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


#include <pbs_config.h>   /* the master config generated by configure */

#include	<stdio.h>
#include	<unistd.h>
#include	<stdlib.h>
#include	<errno.h>
#include	<string.h>
#include	<fcntl.h>
#include	<sys/types.h>
#include	<sys/socket.h>
#include	<sys/param.h>
#include	<sys/time.h>
#include	<netdb.h>
#include	<netinet/in.h>
#include	<arpa/inet.h>

#include	"pbs_ifl.h"
#include	"pbs_internal.h"
#include	"net_connect.h"
#include	"resmon.h"
#include	"log.h"
#include	"dis.h"
#include	"rm.h"
#include	"tpp.h"
#if defined(FD_SET_IN_SYS_SELECT_H)
#include 	<sys/select.h>
#endif

/**
 * @file	rm.c
 */
static	int	full = 1;

/*
 **	This is the structure used to keep track of the resource
 **	monitor connections.  Each entry is linked into as list
 **	pointed to by "outs".  If len is -1, no
 **	request is active.  If len is -2, a request has been
 **	sent and is waiting to be read.  If len is > 0, the number
 **	indicates how much data is waiting to be sent.
 */
struct	out {
	int	stream;
	int	len;
	struct	out	*next;
};

#define	HASHOUT	32
static	struct	out	*outs[HASHOUT];

/**
 * @brief
 *	Create an "out" structure and put it in the hash table.
 *
 * @param[in] stream	socket descriptor
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 */
static int
addrm(int stream)
{
	struct	out		*op, **head;

	if ((op = (struct out *)malloc(sizeof(struct out))) == NULL) {
		pbs_errno = errno;
		return -1;
	}

	head = &outs[stream % HASHOUT];
	op->stream = stream;
	op->len = -1;
	op->next = *head;
	*head = op;
	return 0;
}

/**
 * @brief
 *	Connects to a resource monitor and returns a file descriptor to
 *	talk to it.  If port is zero, use default port.
 *
 * @param[in] host - hostname
 * @param[in] port - port number
 *
 * @return	int
 * @retval	socket stream	success
 * @retval	-1		error
 */
int
openrm(char *host, unsigned int port)
{
	int stream;

	DBPRT(("openrm: host %s port %u\n", host, port))
	pbs_errno = 0;
	if (port == 0)
		port = pbs_conf.manager_service_port;
	DBPRT(("using port %u\n", port))
	stream = tpp_open(host, port);
	pbs_errno = errno;
	if (stream < 0)
		return -1;
	if (addrm(stream) == -1) {
		pbs_errno = errno;
		tpp_close(stream);
		return -1;
	}
	return stream;
}

/**
 * @brief
 *	Routine to close a connection to a resource monitor
 *	and free the "out" structure.
 *
 * @param[in] stream	socket descriptor whose connection to be closed
 *
 * @return	int
 * @retval	0	all well
 * @retval	-1	error
 *
 */
static int
delrm(int stream)
{
	struct	out	*op, *prev = NULL;

	for (op=outs[stream % HASHOUT]; op; op=op->next) {
		if (op->stream == stream)
			break;
		prev = op;
	}
	if (op) {
		tpp_close(stream);

		if (prev)
			prev->next = op->next;
		else
			outs[stream % HASHOUT] = op->next;
		free(op);
		return 0;
	}
	return -1;
}

/**
 * @brief
 *	Internal routine to find the out structure for a stream number.
 *
 * @param[in] stream - socket descriptor
 *
 * @return	structure handle
 * @retval	nin NULL value		success
 * @retval	NULL			error
 *
 */
static struct	out *
findout(int stream)
{
	struct	out	*op;

	for (op=outs[stream % HASHOUT]; op; op=op->next) {
		if (op->stream == stream)
			break;
	}
	if (op == NULL)
		pbs_errno = ENOTTY;
	return op;
}

/**
 * @brief
 *	start and compose command
 *
 * @param[in] stream - socket descriptor
 * @param[in] com - command
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
static int
startcom(int stream, int com)
{
	int	ret;

	DIS_tpp_funcs();
	ret = diswsi(stream, RM_PROTOCOL);
	if (ret == DIS_SUCCESS) {
		ret = diswsi(stream, RM_PROTOCOL_VER);
		if (ret == DIS_SUCCESS)
			ret = diswsi(stream, com);
	}

	if (ret != DIS_SUCCESS) {
		DBPRT(("startcom: diswsi error %s\n", dis_emsg[ret]))
		pbs_errno = errno;
	}
	return ret;
}

/**
 * @brief
 *	Internal routine to compose and send a "simple" command.
 *	This means anything with a zero length body.
 *
 * @param[in] stream - socket descriptor
 * @param[in] com - command
 *
 * @return      int
 * @retval      0       success
 * @retval      -1   	error
 *
 */
static int
simplecom(int stream, int com)
{
	struct	out	*op;

	if ((op = findout(stream)) == NULL)
		return -1;

	op->len = -1;

	if (startcom(stream, com) != DIS_SUCCESS) {
		tpp_close(stream);
		return -1;
	}
	if (dis_flush(stream) == -1) {
		pbs_errno = errno;
		DBPRT(("simplecom: flush error %d\n", pbs_errno))
		tpp_close(stream);
		return -1;
	}
	(void)tpp_eom(stream);
	return 0;
}

/**
 * @brief
 *	Internal routine to read the return value from a command.
 *
 * @param[in] stream - socket descriptor
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      error
 *
 */
static int
simpleget(int stream)
{
	int	ret, num;
	fd_set selset;

	while(1) {
		/* since tpp recvs are essentially always non blocking
		 * we can call a dis function only if we are sure we have
		 * data on that tpp fd
		 */
		FD_ZERO(&selset);
		FD_SET(tpp_fd, &selset);
		if (select(FD_SETSIZE, &selset, NULL, NULL, NULL) > 0) {
			if (tpp_poll() == stream)
				break;
		} else
			break; /* let it flow down and fail in the DIS read */
	}

	num = disrsi(stream, &ret);
	if (ret != DIS_SUCCESS) {
		DBPRT(("simpleget: %s\n", dis_emsg[ret]))
		pbs_errno = errno ? errno : EIO;
		tpp_close(stream);
		return -1;
	}
	if (num != RM_RSP_OK) {
#ifdef	ENOMSG
		pbs_errno = ENOMSG;
#else
		pbs_errno = EINVAL;
#endif
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Close connection to resource monitor.
 *
 * @param[in] stream - socket descriptor
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      error(set pbs_errno).
 *
 */
int
closerm(int stream)
{
	pbs_errno = 0;
	(void)simplecom(stream, RM_CMD_CLOSE);
	if (delrm(stream) == -1) {
		pbs_errno = ENOTTY;
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Shutdown the resource monitor.
 *
 * @param[in] stream - socket descriptor
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      error(set pbs_errno).
 *
 */
int
downrm(int stream)
{
	pbs_errno = 0;
	if (simplecom(stream, RM_CMD_SHUTDOWN))
		return -1;
	if (simpleget(stream))
		return -1;
	(void)delrm(stream);
	return 0;
}

/**
 * @brief
 *	Cause the resource monitor to read the file named.
 *
 * @param[in] stream - socket descriptor
 * @param[in] file - file name
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      error(set pbs_errno).
 *
 */
int
configrm(int stream, char *file)
{
	int	ret, len;
	struct	out	*op;

	pbs_errno = 0;
	if ((op = findout(stream)) == NULL)
		return -1;
	op->len = -1;

	if (file[0] != '/' || (len = strlen(file)) > (size_t)MAXPATHLEN) {
		pbs_errno = EINVAL;
		return -1;
	}

	if (startcom(stream, RM_CMD_CONFIG) != DIS_SUCCESS)
		return -1;
	ret = diswcs(stream, file, len);
	if (ret != DIS_SUCCESS) {
#if	defined(ECOMM)
		pbs_errno = ECOMM;
#elif	defined(ENOCONNECT)
		pbs_errno = ENOCONNECT;
#else

#ifdef WIN32
		pbs_errno = ERROR_IO_INCOMPLETE;
#else
		pbs_errno = ETXTBSY;
#endif

#endif
		DBPRT(("configrm: diswcs %s\n", dis_emsg[ret]))
		return -1;
	}
	if (dis_flush(stream) == -1) {
		pbs_errno = errno;
		DBPRT(("configrm: flush error %d\n", pbs_errno))
		return -1;
	}

	if (simpleget(stream))
		return -1;
	return 0;
}

/**
 * @brief
 *	Begin a new message to the resource monitor if necessary.
 *	Add a line to the body of an outstanding command to the resource
 *	monitor.
 *
 * @param[in] op - pointer to message structure
 * @param[in line - string
 *
 * @return	int
 * @retval	0	if all is ok
 * @retval	-1	if not (set pbs_errno).
 *
 */
static int
doreq(struct out *op, char *line)
{
	int	ret;

	if (op->len == -1) {	/* start new message */
		if (startcom(op->stream, RM_CMD_REQUEST) != DIS_SUCCESS)
			return -1;
		op->len = 1;
	}
	ret = diswcs(op->stream, line, strlen(line));
	if (ret != DIS_SUCCESS) {
#if	defined(ECOMM)
		pbs_errno = ECOMM;
#elif	defined(ENOCONNECT)
		pbs_errno = ENOCONNECT;
#else
#ifdef WIN32
		pbs_errno = ERROR_IO_INCOMPLETE;
#else
		pbs_errno = ETXTBSY;
#endif

#endif
		DBPRT(("doreq: diswcs %s\n", dis_emsg[ret]))
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Add a request to a single stream.
 *
 * @param[in] stream - socket descriptor
 * @param[in line - request string
 *
 * @return      int
 * @retval      0       if all is ok
 * @retval      -1      if not (set pbs_errno).
 *
 */
int
addreq(int stream, char *line)
{
	struct	out	*op;

	pbs_errno = 0;
	if ((op = findout(stream)) == NULL)
		return -1;
	DIS_tpp_funcs();
	if (doreq(op, line) == -1) {
		(void)delrm(stream);
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Add a request to every stream.
 *
 * @param[in] line - request string
 *
 * @return	int
 * @retval	num of stream acted upon	success
 * @retval	0				error
 *
 */
int
allreq(char *line)
{
	struct	out	*op, *prev;
	int		i, num;

	DIS_tpp_funcs();
	pbs_errno = 0;
	num = 0;
	for (i=0; i<HASHOUT; i++) {
		prev=NULL;
		op=outs[i];
		while (op) {
			if (doreq(op, line) == -1) {
				struct	out	*hold = op;

				tpp_close(op->stream);
				if (prev)
					prev->next = op->next;
				else
					outs[i] = op->next;
				op = op->next;
				free(hold);
			}
			else {
				prev = op;
				op = op->next;
				num++;
			}
		}
	}
	return num;
}

/**
 * @brief
 *	Finish (and send) any outstanding message to the resource monitor.
 *
 * @param[in] stream	socket descriptor
 *
 * @return	string
 * @retval	pointer to the next response line
 * @retval	NULL if there are no more or an error occured.  Set pbs_errno on error.
 */
char *
getreq(int stream)
{
	char	*startline;
	struct	out	*op;
	int	ret;

	pbs_errno = 0;
	if ((op = findout(stream)) == NULL)
		return NULL;
	if (op->len >= 0) {	/* there is a message to send */
		if (dis_flush(stream) == -1) {
			pbs_errno = errno;
			DBPRT(("getreq: flush error %d\n", pbs_errno))
			(void)delrm(stream);
			return NULL;
		}
		op->len = -2;
		(void)tpp_eom(stream);
	}
	DIS_tpp_funcs();
	if (op->len == -2) {
		if (simpleget(stream) == -1)
			return NULL;
		op->len = -1;
	}
	startline = disrst(stream, &ret);
	if (ret == DIS_EOF) {
		return NULL;
	}
	else if (ret != DIS_SUCCESS) {
		pbs_errno = errno ? errno : EIO;
		DBPRT(("getreq: cannot read string %s\n", dis_emsg[ret]))
		return NULL;
	}

	if (!full) {
		char	*cc, *hold;
		int	indent = 0;

		for (cc=startline; *cc; cc++) {
			if (*cc == '[')
				indent++;
			else if (*cc == ']')
				indent--;
			else if (*cc == '=' && indent == 0) {
				if ((hold = strdup(cc + 1)) == NULL) {
					pbs_errno = errno ? errno : ENOMEM;
					DBPRT(("getreq: Unable to allocate memory!\n"))
				}
				free(startline);
				startline = hold;
				break;
			}
		}
	}
	return startline;
}

/**
 * @brief
 *	Finish and send any outstanding messages to all resource monitors.
 *
 * @return	int
 * @retval	num of msgs flushed	success
 * @retval	0			error
 *
 */
int
flushreq()
{
	struct	out	*op, *prev;
	int	did, i;

	pbs_errno = 0;
	did = 0;
	for (i=0; i<HASHOUT; i++) {
		for (op=outs[i]; op; op=op->next) {
			if (op->len <= 0)	/* no message to send */
				continue;
			if (dis_flush(op->stream) == -1) {
				pbs_errno = errno;
				DBPRT(("flushreq: flush error %d\n", pbs_errno))
				tpp_close(op->stream);
				op->stream = -1;
				continue;
			}
			op->len = -2;
			(void)tpp_eom(op->stream);
			did++;
		}

		prev = NULL;
		op = outs[i];
		while (op) {		/* get rid of bad streams */
			if (op->stream != -1) {
				prev = op;
				op = op->next;
				continue;
			}
			if (prev == NULL) {
				outs[i] = op->next;
				free(op);
				op = outs[i];
			}
			else {
				prev->next = op->next;
				free(op);
				op = prev->next;
			}
		}
	}
	return did;
}

/**
 * @brief
 *	Return the stream number of the next stream with something
 *	to read or a negative number (the return from tpp_poll)
 *	if there is no stream to read.
 *
 * @return	int
 * @retval	next stream num		success
 * @retval	-ve val			error
 */
int
activereq()
{
	struct	out	*op;
	int		try, i, num;
	int		bucket;
	struct	timeval	tv;
	fd_set		fdset;

	pbs_errno = 0;
	flushreq();
	FD_ZERO(&fdset);

	for (try=0; try<3;) {
		if ((i = tpp_poll()) >= 0) {
			if ((op = findout(i)) != NULL)
				return i;

			op = (struct out *)malloc(sizeof(struct out));
			if (op == NULL) {
				pbs_errno = errno;
				return -1;
			}

			bucket = i % HASHOUT;
			op->stream = i;
			op->len = -2;
			op->next = outs[bucket];
			outs[bucket] = op;
		}
		else if (i == -1) {
			pbs_errno = errno;
			return -1;
		}
		else {
			extern	int	tpp_fd;

			FD_SET(tpp_fd, &fdset);
			tv.tv_sec = 5;
			tv.tv_usec = 0;
			num = select(FD_SETSIZE, &fdset, NULL, NULL, &tv);
			if (num == -1) {
				pbs_errno = errno;
				DBPRT(("%s: select %d\n", __func__, pbs_errno))
				return -1;
			}
			if (num == 0) {
				try++;
				DBPRT(("%s: timeout %d\n", __func__, try))
			}
		}
	}
	return i;
}

/**
 * @brief
 *	If flag is true, turn on "full response" mode where getreq
 *	returns a pointer to the beginning of a line of response.
 *	This makes it possible to examine the entire line rather
 *	than just the answer following the equal sign.
 *
 * @param[in] flag - value indicating whether to turn on full response mode or not.
 *
 */
void
fullresp(int flag)
{
	pbs_errno = 0;
	full = flag;
	return;
}

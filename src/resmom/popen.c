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

/*
 * Copyright (c) 1988, 1993
 *	The Regents of the University of California.  All rights reserved.
 *
 * This code is derived from software written by Ken Arnold and
 * published in UNIX Review, Vol. 6, No. 8.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. All advertising materials mentioning features or use of this software
 *    must display the following acknowledgement:
 *	This product includes software developed by the University of
 *	California, Berkeley and its contributors.
 * 4. Neither the name of the University nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 * $FreeBSD: src/lib/libc/gen/popen.c,v 1.14 2000/01/27 23:06:19 jasone Exp $
 */
/**
 * @file	popen.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <errno.h>
#include <unistd.h>
#include <string.h>

#include <sys/param.h>
#include <sys/wait.h>
#include "log.h"

extern pid_t fork_me(int sock);
extern int kill_session(pid_t pid, int sig, int dir);

extern char **environ;

static struct pid {
	struct pid *next;
	FILE *fp;
	pid_t pid;
} * pidlist;

/**
 * @brief
 *	-implementation of pbs pipe open call.
 *
 * @param[in] command - arguments
 * @param[in] type - mode of pipe
 *
 * @return	FILE pointer
 * @retval	fd		success
 * @retval	NULL		error
 *
 */

FILE *
pbs_popen(const char *command, const char *type)
{
	struct pid *cur;
	FILE *iop;
	int pdes[2], pid, twoway;
	char *argv[4];
	struct pid *p;

	/*
	 * Lite2 introduced two-way popen() pipes using socketpair().
	 * FreeBSD's pipe() is bidirectional, so we use that.
	 */
	if (strchr(type, '+')) {
		twoway = 1;
		type = "r+";
	} else {
		twoway = 0;
		if ((*type != 'r' && *type != 'w') || type[1])
			return NULL;
	}
	if (pipe(pdes) < 0)
		return NULL;

	if ((cur = malloc(sizeof(struct pid))) == NULL) {
		log_err(errno, __func__, "Could not allocate memory for new file descriptor");
		(void) close(pdes[0]);
		(void) close(pdes[1]);
		return NULL;
	}

	argv[0] = "sh";
	argv[1] = "-c";
	argv[2] = (char *) command;
	argv[3] = NULL;

	switch (pid = fork_me(-1)) {
		case -1: /* Error. */
			(void) close(pdes[0]);
			(void) close(pdes[1]);
			free(cur);
			return NULL;
			/* NOTREACHED */
		case 0: /* Child. */
			/* create a new session */
			if (setsid() == -1)
				_exit(127);

			if (*type == 'r') {
				/*
				 * The dup2() to STDIN_FILENO is repeated to avoid
				 * writing to pdes[1], which might corrupt the
				 * parent's copy.  This isn't good enough in
				 * general, since the _exit() is no return, so
				 * the compiler is free to corrupt all the local
				 * variables.
				 */
				(void) close(pdes[0]);
				if (pdes[1] != STDOUT_FILENO) {
					(void) dup2(pdes[1], STDOUT_FILENO);
					(void) close(pdes[1]);
					if (twoway)
						(void) dup2(STDOUT_FILENO, STDIN_FILENO);
				} else if (twoway && (pdes[1] != STDIN_FILENO))
					(void) dup2(pdes[1], STDIN_FILENO);
			} else {
				if (pdes[0] != STDIN_FILENO) {
					(void) dup2(pdes[0], STDIN_FILENO);
					(void) close(pdes[0]);
				}
				(void) close(pdes[1]);
			}
			for (p = pidlist; p; p = p->next) {
				(void) close(fileno(p->fp));
			}
			execve("/bin/sh", argv, environ);
			_exit(127);
			/* NOTREACHED */
	}

	/* Parent; assume fdopen can't fail. */
	if (*type == 'r') {
		iop = fdopen(pdes[0], type);
		(void) close(pdes[1]);
	} else {
		iop = fdopen(pdes[1], type);
		(void) close(pdes[0]);
	}

	/* Link into list of file descriptors. */
	cur->fp = iop;
	cur->pid = pid;
	cur->next = pidlist;
	pidlist = cur;

	return (iop);
}

/**
 * @brief
 * 	-pbs_pkill Send a signal to the child process started by pbs_popen.
 *
 * @param[in] iop - file pointer
 * @param[in] sig - signal number
 *
 * @return	int
 * @retval	o	success
 * @retval	-1	error
 *
 */
int
pbs_pkill(FILE *iop, int sig)
{
	register struct pid *cur;
	int ret;

	/* Find the appropriate file pointer. */
	for (cur = pidlist; cur; cur = cur->next) {
		if (cur->fp == iop)
			break;
	}
	if (cur == NULL)
		return -1;

	ret = kill_session(cur->pid, sig, 0);
	return ret;
}

/**
 * @brief
 * 	-pbs_pclose -- close fds related to opened pipe
 *
 * @par	Pclose returns -1 if stream is not associated with a `popened' command,
 *	if already `pclosed', or waitpid returns an error.
 *
 * @param[in] iop - fd
 *
 * @return 	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
int
pbs_pclose(FILE *iop)
{
	register struct pid *cur, *last;
	int pstat;
	pid_t pid;

	/* Find the appropriate file pointer. */
	for (last = NULL, cur = pidlist; cur; last = cur, cur = cur->next) {
		if (cur->fp == iop)
			break;
	}
	if (cur == NULL)
		return (-1);

	(void) fclose(iop);
	(void) kill_session(cur->pid, SIGKILL, 0);

	do {
		pid = waitpid(cur->pid, &pstat, 0);
	} while (pid == -1 && errno == EINTR);

	/* Remove the entry from the linked list. */
	if (last == NULL)
		pidlist = cur->next;
	else
		last->next = cur->next;
	free(cur);

	return (pid == -1 ? -1 : pstat);
}

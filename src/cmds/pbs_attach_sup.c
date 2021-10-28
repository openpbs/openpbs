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
 * @file	pbs_attach_sup.c
 * @brief
 * supporting file for pbs_attach.c
 *
 */

#include <pbs_config.h>

#include <stdio.h>
#include <sys/wait.h>

#include "cmds.h"
#include "tm.h"

extern char *get_ecname(int rc);

char *getoptargstr = "+j:p:h:m:sP";
/**
 * @brief
 * 	displays how to use pbs_attach command
 *
 * @param[in] id - command name i.e pbs_attach
 *
 * @return Void
 *
 */
void
usage(char *id)
{
	fprintf(stderr, "usage: %s [-j jobid] [-m port] -p pid\n", id);
	fprintf(stderr, "usage: %s [-j jobid] [-m port] [-P] [-s] cmd [arg1 ...]\n", id);
	fprintf(stderr, "usage: %s --version\n", id);
	exit(2);
}

/**
 * @brief
 *	attach the process session to a job via TM
 *
 * @param[in] use_cmd : if TRUE, launch the process using a new command shell. (Not used)
 * @param[in] newsid : if TRUE, create a new process group for the newly spawned process
 * @param[in] port : port to connect to Mom
 * @param[in] doparent : if non-zero, attach the parent pid
 * @param[in] jobid : job id
 * @param[in] host : name of the local host
 * @param[in] argc : number of command line arguments for attach request
 * @param[in] argv : command line arguments for attach request
 *
 * @return void
 *
 */
void
attach(int use_cmd, int newsid, int port, int doparent, pid_t pid, char *jobid, char *host, int argc, char *argv[])
{
	char		*cookie = NULL;
	tm_task_id	tid;
	int             rc = 0;

	if (newsid) {
		if ((pid = fork()) == -1) {
			perror("pbs_attach: fork");
			exit(1);
		} else if (pid > 0) {	/* parent */
			int	status;

			if (wait(&status) == -1) {
				perror("pbs_attach: wait");
				exit(1);
			}
			if (WIFEXITED(status))
				exit(WEXITSTATUS(status));
			else
				exit(2);
		}
		if (setsid() == -1) {
			perror("pbs_attach: setsid");
			exit(1);
		}
	}

	if (pid == 0)
		pid = getpid();

	/*
	 **	Do the attach.
	 */
	rc = tm_attach(jobid, cookie, pid, &tid, host, port);

	/*
	 **	If an error other than "session already attached" is returned,
	 **	complain and return failure.
	 */
	if ((rc != TM_SUCCESS) && (rc != TM_ESESSION)) {
		fprintf(stderr, "%s: tm_attach: %s\n", argv[0], get_ecname(rc));
		exit(1);
	}
	/*
	 **	Optional attach of the parent pid.
	 */
	if (doparent) {
		pid = getppid();
		rc = tm_attach(jobid, cookie, pid, &tid, host, port);
		if ((rc != TM_SUCCESS) && (rc != TM_ESESSION)) {
			fprintf(stderr, "%s: tm_attach parent: %s\n", argv[0], get_ecname(rc));
		}
	}

	if (optind < argc) {
		/*
		 ** Put MPICH_PROCESS_GROUP into the environment so some
		 ** installations of MPICH will not call setsid() and escape
		 ** the new task.
		 */
		(void)setenv("MPICH_PROCESS_GROUP", "no", 1);

		argv += optind;
		argc -= optind;

		execvp(argv[0], argv);
		perror(argv[0]);
		exit(255);	/* not reached */
	}
	exit(0);
}

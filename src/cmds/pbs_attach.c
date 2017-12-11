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
 * @file	pbs_attach.c
 * @brief
 * pbs_attach - attach a session to a job.
 *
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <pwd.h>
#include <netdb.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#include "cmds.h"
#include "pbs_ifl.h"
#include "tm.h"
#include "pbs_version.h"
#ifdef WIN32
#include <windows.h>
#include "win.h"
#include "win_remote_shell.h"
#define PROG_NAME "pbs_attach"
#endif

extern char *get_ecname(int rc);

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
#ifdef WIN32
	/* Windows has an additional option -c, in order to run built-in DOS commands using a new command shell */
	fprintf(stderr, "usage: %s [-j jobid] [-m port] [-P] [-s] [-c] cmd [arg1 ...]\n", id);
#else
	fprintf(stderr, "usage: %s [-j jobid] [-m port] [-P] [-s] cmd [arg1 ...]\n", id);
#endif
	fprintf(stderr, "usage: %s --version\n", id);
	exit(2);
}

#ifdef WIN32
/**
 * @brief
 *	attach the process session to a job via TM on Windows
 *
 * @param[in] use_cmd : if TRUE, launch the process using a new command shell. Useful for built-in DOS commands.
 * @param[in] newsid : if TRUE, create a new process group for the newly spawned process
 * @param[in] port : port to connect to Mom
 * @param[in] doparent : if non-zero, attach the parent pid
 * @param[in] jobid : job id
 * @param[in] host : name of the local host
 * @param[in] ac : number of command line arguments for attach request
 * @param[in] av : command line arguments for attach request
 *
 * @return void
 *
 */
void
win_attach(BOOL use_cmd, int newsid, int port, int doparent, pid_t pid, char *jobid, char *host, int ac, char *av[])
{
	char            *cookie = NULL;
	int             rc = 0;
	tm_task_id      tid;

	if (pid != 0) {
		/* attach PID */
		rc = tm_attach(jobid, cookie, pid, &tid, host, port);

		/*
		 *	if an error other than "session already attached" is returned,
		 *	complain and return failure.
		 */
		if ((rc != TM_SUCCESS) && (rc != TM_ESESSION)) {
			fprintf(stderr, "%s: tm_attach: %s\n", PROG_NAME, get_ecname(rc));
			exit(1);
		}
	} else {
		/* attach given command */
		char                    cmd_line[PBS_CMDLINE_LENGTH] = {'\0'};
		int                     i = 0;
		pio_handles	        pio;
		proc_ctrl               proc_info;

		/* if no job id is supplied, try reading from environment */
		if (jobid == NULL) {
			jobid = getenv("PBS_JOBID");
		}
		/*
		 * Put MPICH_PROCESS_GROUP into the environment so some
		 * installations of MPICH will not open a new session and escape
		 * the new task.
		 */
		(void)setenv("MPICH_PROCESS_GROUP", "no", 1);

		if ((ac > 0) && (av != NULL) && (*av != NULL) && (*av[0] != '\0')) {
			/* create a suspended process */
			/* if newsid, create a new process group */
			if (newsid) {
				proc_info.flags = CREATE_SUSPENDED | CREATE_DEFAULT_ERROR_MODE
					| CREATE_NEW_PROCESS_GROUP;
			}
			else {
				proc_info.flags = CREATE_SUSPENDED | CREATE_DEFAULT_ERROR_MODE
					| CREATE_NO_WINDOW;
			}
			(void)strncpy_s(cmd_line, _countof(cmd_line), av[0], _TRUNCATE);
			for (i = 1; i < ac ; i++) {
				(void)strncat_s(cmd_line, _countof(cmd_line), " ", _TRUNCATE); /* Concatenate a single space */
				(void)strncat_s(cmd_line, _countof(cmd_line), "\"", _TRUNCATE); /* Put inside double quote  */
				(void)strncat_s(cmd_line, _countof(cmd_line), av[i], _TRUNCATE);
				(void)strncat_s(cmd_line, _countof(cmd_line), "\"", _TRUNCATE); /* Put inside double quote */
			}

			proc_info.bInheritHandle = TRUE; /* TRUE since we need to use pipes for communication
							  * with the child process
							  */
			proc_info.bnowait = TRUE; /* creating suspended process, so don't wait for process completion */
			proc_info.need_ptree_termination = FALSE; /* don't need to terminate the process tree,
								   * should not assign a job object to the process.
								   * Mom will assign this process to the corresponding
								   * job object
								   */
			proc_info.buse_cmd = use_cmd; /* does user need a new command shell to run this process? */
			if (win_popen(cmd_line, "r", &pio, &proc_info) == 0) {
				win_pclose(&pio);
				fprintf(stderr, "%s: Unable to create process\n", PROG_NAME);
				exit(1);
			}
		}

		/*
		 **	optional attach of the parent pid.
		 */
		if (doparent) {
			pid = getpid();
			rc = tm_attach(jobid, cookie, pid, &tid, host, port);
			if ((rc != TM_SUCCESS) && (rc != TM_ESESSION)) {
				win_pclose(&pio);
				fprintf(stderr, "%s: tm_attach parent: %s\n", PROG_NAME,
					get_ecname(rc));
				exit(1);
			}
		} else {
			/*
			 **	attach the newly spawned process
			 */
			rc = tm_attach(jobid, cookie, (int)pio.pi.dwProcessId, &tid, host, port);

			/*
			 **	if an error other than "session already attached" is returned,
			 **	complain and return failure.
			 */
			if ((rc != TM_SUCCESS) && (rc != TM_ESESSION)) {
				win_pclose(&pio);
				fprintf(stderr, "%s: tm_attach: %s\n", PROG_NAME,
					get_ecname(rc));
				exit(1);
			}
		}
		/* resume the suspended process now */
		rc = ResumeThread(pio.pi.hThread);
		if (rc == -1) {
			errno = GetLastError();
			win_pclose(&pio);
			perror("ResumeThread");
			exit(1);
		}
		rc = win_pread2(&pio);
		if (rc > 0) {/* wait error */
			perror("WaitForSingleObject");
			win_pclose(&pio);
			exit(1);
		}
		else if (rc == -1) {/* Should not happen. This indicates wrong usage of win_pread2(), programming error */
			win_pclose(&pio);
			fprintf(stderr, "%s: failure reading from pipe\n", PROG_NAME);
			exit(255);
		}
		win_pclose(&pio);
	}
	exit(0);
}
#endif
int
main(int argc, char *argv[])
{
	char		*jobid = NULL;
	char		*host = NULL;
	int		c;
	int		newsid = 0;
	int		port = 0;
	int		err = 0;
#ifdef WIN32
	BOOL use_cmd = FALSE;/* spawn the process using a new cmd shell */
#else
	char		*cookie = NULL;
	tm_task_id	tid;
	int             rc = 0;
#endif
	extern char	*optarg;
	extern int	optind;
	pid_t		pid = 0;
	char	*end;
	int		doparent = 0;

	/*test for real deal or just version and exit*/

	execution_mode(argc, argv);

#ifdef WIN32
	winsock_init();
	/* Windows has an additional option -c, in order to run built-in DOS commands using a new command shell */
	while ((c = getopt(argc, argv, "+j:p:h:m:csP")) != EOF) {
#else
	while ((c = getopt(argc, argv, "+j:p:h:m:sP")) != EOF) {
#endif
		switch (c) {
			case 'j':
				jobid = optarg;
				break;

			case 'p':
				pid = strtol(optarg, &end, 10);
				if (pid <= 0 || *end != '\0') {
					fprintf(stderr, "bad pid: %s\n", optarg);
					err = 1;
				}
				break;

			case 'P':
				doparent = 1;
				break;

			case 'h':
				host = optarg;
				break;
#ifdef WIN32
			case 'c':
				use_cmd = TRUE;
				break;
#endif

			case 'm':
				port = strtol(optarg, &end, 10);
				if (port <= 0 || *end != '\0') {
					fprintf(stderr, "bad port: %s\n", optarg);
					err = 1;
				}
				break;

			case 's':
				newsid = 1;
				break;

			default:
				err = 1;
				break;
		}
	}

	if (pid != 0) {
		if (newsid) {
			fprintf(stderr, "cannot specify pid and session\n");
			err = 1;
		}
		if (doparent) {
			fprintf(stderr, "cannot specify pid and parent\n");
			err = 1;
		}
		if (optind < argc) {
			fprintf(stderr, "cannot specify pid and command\n");
			err = 1;
		}
	}
	else if (optind == argc) {
		fprintf(stderr, "must specify pid or command\n");
		err = 1;
	}

	if (err)
		usage(argv[0]);

	if (port == 0) {
		pbs_loadconf(0);
		port = pbs_conf.manager_service_port;
	}
#ifdef WIN32 /* Windows - attach */
	argv += optind;
	argc -= optind;
	win_attach(use_cmd, newsid, port, doparent, pid, jobid, host, argc, argv);
#else /* Linux - attach */
	if (newsid) {
		if ((pid = fork()) == -1) {
			perror("pbs_attach: fork");
			return 1;
		} else if (pid > 0) {	/* parent */
			int	status;

			if (wait(&status) == -1) {
				perror("pbs_attach: wait");
				return 1;
			}
			if (WIFEXITED(status))
				return WEXITSTATUS(status);
			else
				return 2;
		}
		if (setsid() == -1) {
			perror("pbs_attach: setsid");
			return 1;
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
		fprintf(stderr, "%s: tm_attach: %s\n", argv[0],
			get_ecname(rc));
		return 1;
	}
	/*
	 **	Optional attach of the parent pid.
	 */
	if (doparent) {
		pid = getppid();
		rc = tm_attach(jobid, cookie, pid, &tid, host, port);
		if ((rc != TM_SUCCESS) && (rc != TM_ESESSION)) {
			fprintf(stderr, "%s: tm_attach parent: %s\n", argv[0],
				get_ecname(rc));
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
		return 255;	/* not reached */
	}
	return 0;
#endif
}

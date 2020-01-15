/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

#include <pbs_config.h>   /* the master config generated by configure */

#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <pwd.h>
#include "portability.h"
#include "libpbs.h"
#include "list_link.h"
#include "log.h"
#include "server_limits.h"
#include "attribute.h"
#include "resource.h"
#include "job.h"
#include "mom_mach.h"
#include "mom_func.h"

/**
 * @file
 */
/* Global Variables */

extern int	 exiting_tasks;
extern char	 mom_host[];
extern pbs_list_head svr_alljobs;
extern int	 termin_child;

/* Private variables */

/**
 * @brief
 * 	set_job - set up a new job session
 * 	Set session id and whatever else is required on this machine
 *	to create a new job.
 *
 * @param[in]   pjob - pointer to job structure
 * @param[in]   sjr  - pointer to startjob_rtn structure
 *
 * @return	session/job id or if error:
 * @retval	-1 - if setsid() fails
 * @retval	-2 - if other, message in log_buffer
 *
 */

int set_job(job *pjob, struct startjob_rtn *sjr)
{
	return (sjr->sj_session = setsid());
}

/**
 * @brief
 *      set_globid - set the global id for a machine type.
 *
 * @param[in] pjob - pointer to job structure
 * @param[in] sjr  - pointer to startjob_rtn structure
 *
 * @return Void
 *
 */

void
set_globid( job *pjob, struct startjob_rtn *sjr)
{
	return;
}

/**
 * @brief
 *      set_mach_vars - setup machine dependent environment variables
 *
 * @param[in] pjob - pointer to job structure
 * @param[in] vtab - pointer to var_table structure
 *
 * @return      int
 * @retval      0       Success
 *
 */

int
set_mach_vars(job *pjob, struct var_table *vtab)
{
	return 0;
}

/**
 * @brief
 *      sets the shell to be used
 *
 * @param[in] pjob - pointer to job structure
 * @param[in] pwdp - pointer to passwd structure
 *
 * @return      string
 * @retval      shellname       Success
 *
 */

char *set_shell(job *pjob, struct passwd  *pwdp)
{
	char *cp;
	int   i;
	char *shell;
	struct array_strings *vstrs;
	/*
	 * find which shell to use, one specified or the login shell
	 */

	shell = pwdp->pw_shell;
	if ((pjob->ji_wattr[(int)JOB_ATR_shell].at_flags & ATR_VFLAG_SET) &&
		(vstrs = pjob->ji_wattr[(int)JOB_ATR_shell].at_val.at_arst)) {
		for (i = 0; i < vstrs->as_usedptr; ++i) {
			cp = strchr(vstrs->as_string[i], '@');
			if (cp) {
				if (!strncmp(mom_host, cp+1, strlen(cp+1))) {
					*cp = '\0';	/* host name matches */
					shell = vstrs->as_string[i];
					break;
				}
			} else {
				shell = vstrs->as_string[i];	/* wildcard */
			}
		}
	}
	return (shell);
}

/**
 * @brief
 * 	scan_for_terminated - scan the list of runnings jobs for a task whose
 *	session id matched that of a terminated child pid.  Mark that
 *	task as Exiting.
 *
 * @return 	Void
 *
 */

void scan_for_terminated()
{
	int		exiteval;
	pid_t		pid;
	job		*pjob;
	task		*ptask;
	int		statloc;

	/* update the latest intelligence about the running jobs;         */
	/* must be done before we reap the zombies, else we lose the info */

	termin_child = 0;

	if (mom_get_sample() == PBSE_NONE) {
		pjob = (job *)GET_NEXT(svr_alljobs);
		while (pjob) {
			mom_set_use(pjob);
			pjob = (job *)GET_NEXT(pjob->ji_alljobs);
		}
	}

	/* Now figure out which task(s) have terminated (are zombies) */

	while ((pid = waitpid(-1, &statloc, WNOHANG)) != 0) {
		if (pid == -1) {
			if (errno == EINTR)
				continue;
			else
				break;
		}

		pjob = (job *)GET_NEXT(svr_alljobs);
		while (pjob) {
			/*
			** see if process was a child doing a special
			** function for MOM
			*/
			if (pid == pjob->ji_momsubt)
				break;
			/*
			** look for task
			*/
			ptask = (task *)GET_NEXT(pjob->ji_tasks);
			while (ptask) {
				if (ptask->ti_qs.ti_sid == pid)
					break;
				ptask = (task *)GET_NEXT(ptask->ti_jobtask);
			}
			if (ptask != NULL)
				break;
			pjob = (job *)GET_NEXT(pjob->ji_alljobs);
		}
		if (WIFEXITED(statloc))
			exiteval = WEXITSTATUS(statloc);
		else if (WIFSIGNALED(statloc))
			exiteval = WTERMSIG(statloc) + 10000;
		else
			exiteval = 1;

		if (pjob == NULL) {
			DBPRT(("%s: pid %d not tracked, exit %d\n",
				__func__, pid, exiteval))
			continue;
		}

		if (pid == pjob->ji_momsubt) {
			pjob->ji_momsubt = 0;
			if (pjob->ji_mompost) {
				pjob->ji_mompost(pjob, exiteval);
			}
			(void)job_save(pjob, SAVEJOB_QUICK);
			continue;
		}
		DBPRT(("%s: task %8.8X pid %d exit value %d\n", __func__,
				ptask->ti_qs.ti_task, pid, exiteval))
		kill_session(ptask->ti_qs.ti_sid, SIGKILL, 0);
		ptask->ti_qs.ti_exitstat = exiteval;
		ptask->ti_qs.ti_status = TI_STATE_EXITED;
		(void)task_save(ptask);
		sprintf(log_buffer, "task %8.8X terminated",
				ptask->ti_qs.ti_task);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			pjob->ji_qs.ji_jobid, log_buffer);

		exiting_tasks = 1;
	}
}

/**
 * @brief
 *      This is code adapted from an example for posix_openpt in
 *      The Open Group Base Specifications Issue 6.
 *
 *      On success, this function returns an open descriptor for the
 *      master pseudotty and places a pointer to the (static) name of
 *      the slave pseudotty in *rtn_name;  on failure, -1 is returned.
 *
 * @param[in] rtn_name - holds info tty
 *
 * @return      int
 * @retval      fd      Success
 * @retval      -1      Failure
 *
 */

#define PTY_SIZE 12

int open_master(char **rtn_name)
{
	char 	       *pc1;
	char 	       *pc2;
	int		ptc;	/* master file descriptor */
	static char	ptcchar1[] = "pqrs";
	static char	ptcchar2[] = "0123456789abcdef";
	static char	pty_name[PTY_SIZE+1];	/* "/dev/[pt]tyXY" */

	(void)strncpy(pty_name, "/dev/ptyXY", PTY_SIZE);
	for (pc1 = ptcchar1; *pc1 != '\0'; ++pc1) {
		pty_name[8] = *pc1;
		for (pc2 = ptcchar2; *pc2 != '\0'; ++pc2) {
			pty_name[9] = *pc2;
			if ((ptc = open(pty_name, O_RDWR | O_NOCTTY, 0)) >= 0) {
				/* Got a master, fix name to matching slave */
				pty_name[5] = 't';
				*rtn_name = pty_name;
				return (ptc);

			} else if (errno == ENOENT)
				return (-1);	/* tried all entries, give up */
		}
	}
	return (-1);	/* tried all entries, give up */
}

/*
 * struct sig_tbl = map of signal names to numbers,
 * see req_signal() in ../requests.c
 */

struct sig_tbl sig_tbl[] = {
	{ "NULL", 0 },
	{ "HUP", SIGHUP },
	{ "INT", SIGINT },
	{ "QUIT", SIGQUIT },
	{ "ILL",  SIGILL },
	{ "TRAP", SIGTRAP },
	{ "IOT", SIGIOT },
	{ "ABRT",SIGABRT },
	{ "EMT", SIGEMT },
	{ "FPE", SIGFPE },
	{ "KILL", SIGKILL },
	{ "BUS", SIGBUS },
	{ "SEGV", SIGSEGV },
	{ "SYS", SIGSYS },
	{ "PIPE", SIGPIPE },
	{ "ALRM", SIGALRM },
	{ "TERM", SIGTERM },
	{ "URG", SIGURG },
	{ "STOP", SIGSTOP },
	{ "TSTP", SIGTSTP },
	{ "CONT", SIGCONT },
	{ "CHLD", SIGCHLD },
	{ "TTIN", SIGTTIN },
	{ "TTOU", SIGTTOU },
	{ "IO", SIGIO },
	{ "XCPU", SIGXCPU },
	{ "XFSZ", SIGXFSZ },
	{ "VTALRM", SIGVTALRM },
	{ "PROF", SIGPROF },
	{ "WINCH", SIGWINCH },
	{ "USR1", SIGUSR1 },
	{ "USR2", SIGUSR2 },
	{ NULL, -1 }
};

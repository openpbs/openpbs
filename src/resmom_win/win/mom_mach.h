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
/*
 * Machine-dependent definitions for the Machine Oriented Miniserver
 *
 * Target System: winnt_2000
 */

#ifndef PBS_MACH
#define PBS_MACH "windows"

#define SET_LIMIT_SET		1
#define SET_LIMIT_ALTER		0
#define PBS_CHKPT_MIGRATE	0
#define PBS_SUPPORT_SUSPEND	0
#define task	pbs_task

/*
 **	Need place holders for signal numbers because NT does not
 **	have signals.
 */

typedef struct	pbs_plinks {		/* struct to link processes */
	pid_t	 pl_pid;		/* pid of this proc */
	pid_t	 pl_ppid;		/* parent pid of this proc */
	int	 pl_child;		/* index to child */
	int	 pl_sib;		/* index to sibling */
	int	 pl_parent;		/* index to parent */
	int	 pl_done;		/* kill has been done */
} pbs_plinks;

/* Windows is different in that it needs a task pointer */
extern int kill_task(task *, int, int);

/* struct startjob_rtn = used to pass error/session/other info	*/
/* from mom child process back to parent			*/

struct startjob_rtn {
	int   sj_code;          /* error code   */
	pid_t sj_session;       /* session      */
};

extern int mom_set_limits(job *, int);		/* Set job's limits */
extern int mom_do_poll(job *pjob);		/* Should limits be polled? */
extern int mom_does_chkpnt;                     /* see if mom does chkpnt */
extern int mom_open_poll();			/* Initialize poll ability */
extern int mom_get_sample();			/* Sample kernel poll data */
extern int mom_over_limit(job *pjob);		/* Is polled job over limit? */
extern int mom_set_use(job *pjob);		/* Set resource_used list */
extern int mom_close_poll();			/* Terminate poll ability */
extern int mach_checkpoint(struct task *ptask, char *path, int abt);
/* do the checkpoint */
extern long mach_restart(struct task *, char *path);
/* Restart checkpointed task */
extern int error(char *, int);
extern int	set_job(job *, struct startjob_rtn *);
extern void	starter_return(int, int, int, struct startjob_rtn *);
extern void	set_globid(job *, struct startjob_rtn *);
#endif /* PBS_MACH */

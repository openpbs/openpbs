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
#ifndef	_MOM_MACH_H
#define	_MOM_MACH_H
#ifdef	__cplusplus
extern "C" {
#endif
/*
 * Machine-dependent definitions for the Machine Oriented Miniserver
 *
 * Target System: linux
 */



#ifndef MOM_MACH
#define MOM_MACH "linux"

#define SET_LIMIT_SET   1
#define SET_LIMIT_ALTER 0
#define PBS_CHKPT_MIGRATE 0
#define PBS_PROC_SID(x)  proc_info[x].session
#define PBS_PROC_PID(x)  proc_info[x].pid
#define PBS_PROC_PPID(x) proc_info[x].ppid
#define CLR_SJR(sjr)	sjr.sj_code = 0; \
			sjr.sj_session = 0;
#define PBS_SUPPORT_SUSPEND 1
#define	task	pbs_task

typedef struct	pbs_plinks {		/* struct to link processes */
	pid_t	 pl_pid;		/* pid of this proc */
	pid_t	 pl_ppid;		/* parent pid of this proc */
	int	 pl_child;		/* index to child */
	int	 pl_sib;		/* index to sibling */
	int	 pl_parent;		/* index to parent */
	int	 pl_done;		/* kill has been done */
} pbs_plinks;


extern int kill_session(pid_t pid, int sig, int dir);

/* struct startjob_rtn = used to pass error/session/other info 	*/
/* 			child back to parent			*/

struct startjob_rtn {
	int   sj_code;		/* error code	*/
	pid_t sj_session;	/* session	*/
};

extern int mom_set_limits(job *pjob, int);	/* Set job's limits */
extern int mom_do_poll(job *pjob);		/* Should limits be polled? */
extern int mom_does_chkpnt;                     /* see if mom does chkpnt */
extern int mom_open_poll();		/* Initialize poll ability */
extern int mom_get_sample();		/* Sample kernel poll data */
extern int mom_over_limit(job *pjob);	/* Is polled job over limit? */
extern int mom_set_use(job *pjob);		/* Set resource_used list */
extern int mom_close_poll();		/* Terminate poll ability */
extern int mach_checkpoint(struct task *, char *path, int abt);
extern long mach_restart(struct task *, char *path);	/* Restart checkpointed job */
extern int	set_job(job *, struct startjob_rtn *);
extern void	starter_return(int, int, int, struct startjob_rtn *);
extern void	set_globid(job *, struct startjob_rtn *);


#define	COMSIZE		12
typedef struct proc_stat {
	int		session;	/* session id */
	char		state;		/* one of RSDZT: Running, Sleeping,
						 Sleeping (uninterruptable), Zombie,
						 Traced or stopped on signal */
	int		ppid;		/* parent pid */
	int		pgrp;		/* process group id */
	unsigned	utime;		/* utime this process */
	unsigned	stime;		/* stime this process */
	unsigned	cutime;		/* sum of children's utime */
	unsigned	cstime;		/* sum of children's stime */
	int		pid;		/* process id */
	unsigned	vsize;		/* virtual memory size for proc */
	unsigned	rss;		/* resident set size */
	unsigned	start_time;	/* start time of this process */
	unsigned	flags;		/* the flags of the process */
	unsigned	uid;		/* uid of the process owner */
	char		comm[COMSIZE];	/* command name */
} proc_stat_t;


typedef	struct	proc_map {
	unsigned long	vm_start;	/* start of vm for process */
	unsigned long	vm_end;		/* end of vm for process */
	unsigned long	vm_size;	/* vm_end - vm_start */
	unsigned long	vm_offset;	/* offset into vm? */
	unsigned 	inode;		/* inode of region */
	char		*dev;		/* device */
} proc_map_t;

struct	bnode {
	job		*n_job;
	int		n_up;
	unsigned long	n_mem;
	size_t		n_cpus;
};

extern	struct	bnode	*node_array;
extern	int		num_pcpus;
extern	int		num_acpus;

#endif /* MOM_MACH */
#ifdef	__cplusplus
}
#endif
#endif /* _MOM_MACH_H */

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

#ifndef _MOM_MACH_H
#define _MOM_MACH_H
#ifdef __cplusplus
extern "C" {
#endif
/*
 * Machine-dependent definitions for the Machine Oriented Miniserver
 *
 * Target System: linux
 */

#ifndef PBS_MACH
#define PBS_MACH "linux"
#endif /* PBS_MACH */

#ifndef MOM_MACH
#define MOM_MACH "linux"

#define SET_LIMIT_SET 1
#define SET_LIMIT_ALTER 0
#define PBS_CHKPT_MIGRATE 0
#define PBS_PROC_SID(x) proc_info[x].session
#define PBS_PROC_PID(x) proc_info[x].pid
#define PBS_PROC_PPID(x) proc_info[x].ppid
#define CLR_SJR(sjr) memset(&sjr, 0, sizeof(sjr));
#define PBS_SUPPORT_SUSPEND 1
#define task pbs_task

#if MOM_ALPS
#include <sys/types.h>
#include <dlfcn.h>
#include "/usr/include/job.h"
#include <basil.h>
#endif /* MOM_ALPS */

#include "job.h"

typedef struct pbs_plinks { /* struct to link processes */
	pid_t pl_pid;	    /* pid of this proc */
	pid_t pl_ppid;	    /* parent pid of this proc */
	int pl_child;	    /* index to child */
	int pl_sib;	    /* index to sibling */
	int pl_parent;	    /* index to parent */
	int pl_done;	    /* kill has been done */
} pbs_plinks;

extern unsigned long totalmem;
extern int kill_session(pid_t pid, int sig, int dir);
extern int bld_ptree(pid_t sid);

/* struct startjob_rtn = used to pass error/session/other info 	*/
/* 			child back to parent			*/

struct startjob_rtn {
	int sj_code;	  /* error code	*/
	pid_t sj_session; /* session	*/

#if MOM_ALPS
	jid_t sj_jid;
	long sj_reservation;
	unsigned long long sj_pagg;
#endif /* MOM_ALPS */
};

extern int mom_set_limits(job *pjob, int); /* Set job's limits */
extern int mom_do_poll(job *pjob);	   /* Should limits be polled? */
extern int mom_does_chkpnt;		   /* see if mom does chkpnt */
extern int mom_open_poll();		   /* Initialize poll ability */
extern int mom_get_sample();		   /* Sample kernel poll data */
extern int mom_over_limit(job *pjob);	   /* Is polled job over limit? */
extern int mom_set_use(job *pjob);	   /* Set resource_used list */
extern int mom_close_poll();		   /* Terminate poll ability */
extern int mach_checkpoint(struct task *, char *path, int abt);
extern long mach_restart(struct task *, char *path); /* Restart checkpointed job */
extern int set_job(job *, struct startjob_rtn *);
extern void starter_return(int, int, int, struct startjob_rtn *);
extern void set_globid(job *, struct startjob_rtn *);
extern void mom_topology(void);

#if MOM_ALPS
extern void ck_acct_facility_present(void);

/*
 *	Interface to the Cray ALPS placement scheduler. (alps.c)
 */
extern int alps_create_reserve_request(
	job *,
	basil_request_reserve_t **);
extern void alps_free_reserve_request(basil_request_reserve_t *);
extern int alps_create_reservation(
	basil_request_reserve_t *,
	long *,
	unsigned long long *);
extern int alps_confirm_reservation(job *);
extern int alps_cancel_reservation(job *);
extern int alps_inventory(void);
extern int alps_suspend_resume_reservation(job *, basil_switch_action_t);
extern int alps_confirm_suspend_resume(job *, basil_switch_action_t);
extern void alps_system_KNL(void);
extern void system_to_vnodes_KNL(void);
#endif /* MOM_ALPS */

#define COMSIZE 12
typedef struct proc_stat {
	pid_t session;	    /* session id */
	char state;	    /* one of RSDZT: Running, Sleeping,
						 Sleeping (uninterruptable), Zombie,
						 Traced or stopped on signal */
	pid_t ppid;	    /* parent pid */
	pid_t pgrp;	    /* process group id */
	unsigned long utime;	    /* utime this process */
	unsigned long stime;	    /* stime this process */
	unsigned long cutime;	    /* sum of children's utime */
	unsigned long cstime;	    /* sum of children's stime */
	pid_t pid;	    /* process id */
	unsigned long vsize;	    /* virtual memory size for proc */
	unsigned long rss;	    /* resident set size */
	unsigned long start_time;   /* start time of this process */
	unsigned long flags;	    /* the flags of the process */
	unsigned long uid;	    /* uid of the process owner */
	char comm[COMSIZE]; /* command name */
} proc_stat_t;

typedef struct proc_map {
	unsigned long vm_start;	 /* start of vm for process */
	unsigned long vm_end;	 /* end of vm for process */
	unsigned long vm_size;	 /* vm_end - vm_start */
	unsigned long vm_offset; /* offset into vm? */
	unsigned inode;		 /* inode of region */
	char *dev;		 /* device */
} proc_map_t;
#endif /* MOM_MACH */
#ifdef __cplusplus
}
#endif
#endif /* _MOM_MACH_H */

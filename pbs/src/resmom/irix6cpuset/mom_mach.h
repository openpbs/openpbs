/*
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
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
 * Target System: sgi
 */



#ifndef MOM_MACH
#define MOM_MACH "irix6cpuset"

#define SET_LIMIT_SET   1
#define SET_LIMIT_ALTER 0
#define PBS_CHKPT_MIGRATE 0
#define PBS_PROC_SID(x)  taskpids->sid	/* set to current session tagged... */
/* taspids is a table of all pids */
/* under "current" session */
#define PBS_PROC_PID(x)  taskpids->pids[x].pid
#define PBS_PROC_PPID(x) taskpids->pids[x].ppid
#define CLR_SJR(sjr)	sjr.sj_code = 0; \
			sjr.sj_session = 0; \
			sjr.sj_jid = 0; \
			sjr.sj_ash = 0;
#define PBS_SUPPORT_SUSPEND 1
#define	task	pbs_task

typedef struct  pbs_plinks {            /* struct to link processes */
	pid_t    pl_pid;                /* pid of this proc */
	pid_t    pl_ppid;               /* parent pid of this proc */
	int      pl_child;              /* index to child */
	int      pl_sib;                /* index to sibling */
	int      pl_parent;             /* index to parent */
	int	 pl_done;		/* kill has been done */
} pbs_plinks;


/* struct startjob_rtn = used to pass error/session/other info 	*/
/* 			child back to parent			*/

#include "bitfield.h"
#include "cpusets.h"

struct startjob_rtn {
	int   sj_code;		/* error code	*/
	pid_t sj_session;	/* session	*/
	jid_t sj_jid;		/* sgi job container id */
	ash_t sj_ash;		/* sgi array session    */
	Bitfield sj_nodes;	/* Nodes assigned for this job. */
	char	 sj_cpuset_name[QNAME_STRING_LEN+1]; /* name of cpuset assn */
	cpuset_shared sj_shared_cpuset_info;	  /* assigned shared cpuset */

};

extern int mom_set_limits(job *pjob, int);	/* Set job's limits */
extern int mom_do_poll(job *pjob);		/* Should limits be polled? */
extern int mom_does_chkpnt;                     /* see if mom does chkpnt */
extern int mom_open_poll();			/* Initialize poll ability */
extern int mom_get_sample();			/* Sample kernel poll data */
extern int mom_over_limit(job *pjob);		/* Is polled job over limit? */
extern int mom_set_use(job *pjob);		/* Set resource_used list */
extern int mom_close_poll();			/* Terminate poll ability */
extern int mach_checkpoint(struct task *, char *path, int abt);
/* do the checkpoint */
extern long mach_restart(struct task *, char *path);	/* Restart checkpointed task */
extern void mom_update_resources(void);		/* update avail cpus and mem */
extern void cpusets_initialize(void);
extern int	set_job(job *, struct startjob_rtn *);
extern void	starter_return(int, int, int, struct startjob_rtn *);
extern void	set_globid(job *, struct startjob_rtn *);

/*
 * Allocation of nodes is handled by the PBS mom.  The number of nodes to
 * allocate from available pool is passed to mom in this resource.
 *
 * The "nodes" resource carries the notion of one processing group per host.
 * We allocate portions of a single machine to each job.
 */
#define	NODE_COUNT_RESOURCE	"ssinodes"	/* SSI node count */

/*
 * Configurable enforcement options.
 */
extern int	enforce_cput, 		/* Enforce job "cput" request. */
enforce_pcput,		/* Enforce job "pcput" request. */
enforce_cpupct,		/* Enforce job "cpupercent" request. */
enforce_mem,		/* Enforce job "mem" request. */
enforce_vmem,		/* Enforce job "vmem" request. */
enforce_pvmem,		/* Enforce job "pvmem" request. */
enforce_wallt,		/* Enforce job "wallt" request. */
enforce_file,		/* Enforce job "file" request. */
enforce_hammer,		/* "Hammer" unauthorized users. */
enforce_cpusets;	/* Create cpusets for each job. */

#endif /* MOM_MACH */
#ifdef	__cplusplus
}
#endif
#endif /* _MOM_MACH_H */

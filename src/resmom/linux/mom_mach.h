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
#define	MOM_MACH "linux"

#define	SET_LIMIT_SET   1
#define	SET_LIMIT_ALTER 0
#define	PBS_CHKPT_MIGRATE 0
#define	PBS_PROC_SID(x)  proc_info[x].session
#define	PBS_PROC_PID(x)  proc_info[x].pid
#define	PBS_PROC_PPID(x) proc_info[x].ppid
#define	CLR_SJR(sjr)	memset(&sjr, 0, sizeof(sjr));
#define	PBS_SUPPORT_SUSPEND 1
#define	task	pbs_task

#if	MOM_CPUSET
#if	(CPUSET_VERSION < 4)
#include	<cpuset.h>
#include	<cpumemsets.h>
#else
#include	<sys/types.h>
#include	<sys/stat.h>
#include	<bitmask.h>
#include	<cpuset.h>

/*
 *	In the new version of CPU sets, CPUSET_CPU_EXCLUSIVE and
 *	CPUSET_NAME_MIN_LEN are no longer defined for us when
 *	including <cpuset.h>.  Rather than inventing new names,
 *	we simply reinstantiate them here.
 */
#define	CPU_EXCLUSIVE		1
#define	MEM_EXCLUSIVE		2
#define	CPUSET_NAME_MIN_LEN	16
#endif	/* CPUSET_VERSION < 4 */
#endif	/* MOM_CPUSET */

#if	MOM_CSA || MOM_ALPS
#include <sys/types.h>
#include <dlfcn.h>
#include "/usr/include/job.h"
#if	MOM_CSA
#include <csaacct.h>
#include <csa_api.h>
#endif	/* MOM_CSA */
#endif	/* MOM_CSA || MOM_ALPS */

#if     MOM_BGL
#include <rm_api.h>
#endif  /* MOM_BGL */

#if	MOM_ALPS
#include <basil.h>
#endif	/* MOM_ALPS */

typedef struct	pbs_plinks {		/* struct to link processes */
	pid_t	 pl_pid;		/* pid of this proc */
	pid_t	 pl_ppid;		/* parent pid of this proc */
	int	 pl_child;		/* index to child */
	int	 pl_sib;		/* index to sibling */
	int	 pl_parent;		/* index to parent */
	int	 pl_done;		/* kill has been done */
} pbs_plinks;


extern int kill_session(pid_t pid, int sig, int dir);
extern int bld_ptree(pid_t sid);

/* struct startjob_rtn = used to pass error/session/other info 	*/
/* 			child back to parent			*/

struct startjob_rtn {
	int   sj_code;		/* error code	*/
	pid_t sj_session;	/* session	*/
#if	MOM_CPUSET
#if	(CPUSET_VERSION >= 4)
	/*
	 *	A constant with this name was previously found in <cpuset.h>.
	 *	We need a larger value to account for the longer set names, but
	 *	the actual value is just a guess.
	 */
#define	CPUSET_NAME_SIZE	63
#endif	/* CPUSET_VERSION >= 4 */
	char  sj_cpuset_name[CPUSET_NAME_SIZE+1];
#endif	/* MOM_CPUSET */

#if	MOM_CSA || MOM_ALPS
	jid_t	sj_jid;
#endif	/* MOM_CSA or MOM_ALPS */

#if	MOM_ALPS
	long			sj_reservation;
	unsigned long long	sj_pagg;
#endif	/* MOM_ALPS */
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
extern void	mom_topology(void);

#if	MOM_CSA
extern	int	job_facility_present;
extern	int	job_facility_enabled;
extern	int	acct_facility_present;
extern	int	acct_facility_active;
extern	int	acct_facility_wkmgt_recs;
extern	int	acct_facility_wkmgt_active;
extern	int	acct_facility_csa_active;
extern	int	acct_dmd_wkmg;
extern	jid_t	(*jc_create)();
extern	jid_t	(*jc_getjid)();
extern	int	(*p_csa_check)(struct csa_check_req *);
extern	int	(*p_csa_wracct)(struct csa_wra_req *);
extern	void	write_wkmg_record(int, int, job *);
extern	int	find_in_lib(void*, char*, char*, void**);
extern	char	*get_versioned_libname(int);
#endif	/* MOM_CSA */

#if	MOM_CSA || MOM_ALPS
extern	void	ck_acct_facility_present(void);
#endif	/* MOM_CSA or MOM_ALPS */

#if	MOM_CPUSET
extern int	attach_to_cpuset(job *, struct startjob_rtn *);
extern void	clear_cpuset(job *);		/* destroy cpuset */
extern void	del_cpusetfile(char *, job *);
extern char	*getsetname(job *);
extern char	*make_cpuset(job *);		/* create cpuset */
extern char	*modify_cpuset(job *);
extern int	new_cpuset(job *);		/* get CPU set and set altid */
extern int	resume_job(job *);
extern int	suspend_job(job *);

#if	(CPUSET_VERSION >= 4)
/*
 *	Functions to call before an ftw() (*_setup()) to set initial
 *	conditions and after the ftw()'s return (*_return()) to reap
 *	the results.
 */
extern void	count_shared_CPUs_setup(void);
extern void	count_shared_CPUs_return(ulong *);
extern void	cpuignore_setup(int *, int, struct bitmask *);
extern void	cpuignore_return(void);
extern void	cpusets_initialize(int);
extern void	restart_setup(void);
extern void	restart_return(int *);
extern void	reassociate_job_cpus_setup(int);
extern int	reassociate_job_cpus_return(void);

/*
 *	These are the actual ftw() walker functions themselves.
 */
extern int	inuse_cpus(const char *, const struct stat *, int);
extern int	reassociate_job_cpus(const char *, const struct stat *, int);
extern int	restart_cleanupprep(const char *, const struct stat *, int);

/*
 *	Is this CPU set directory ``interesting?''  If we're going to count
 *	consumed resources or try to prune a CPU set directory, don't bother
 *	if this functions returns true (nonzero).
 */
extern int	is_pbs_container(const char *);

extern int	numnodes(void);

extern int	cpuset_pidlist_broken(void);
extern void	logprocinfo(pid_t, int, const char *);
extern void	prune_subsetsof(const char *, const char *);
extern int	try_remove_set(const char *, const char *);
#else
extern void	cpusets_initialize(void);
#endif	/* CPUSET_VERSION >= 4 */

extern ulong	totalmem;
extern ulong	memreserved;
extern ulong	cpuset_nodes;
extern ulong	cpuset_destroy_delay;
extern int	cpuset_create_flags;
extern ulong	mempernode;
extern ulong	cpupernode;
#if	(CPUSET_VERSION >= 4)
extern int		*cpuignore;
extern int		num_pcpus;
extern pbs_list_head	svr_alljobs;
extern int		cpus_nbits;
extern int		mems_nbits;
#endif	/* CPUSET_VERSION >= 4 */

#if	(CPUSET_VERSION < 4)
#define	PBS_SHARE_PREFIX	"SHR"
#else
/*
 *	Instead of files in a mom's private directory, CPU sets are now
 *	publicly-visible subdirectories of /dev/cpuset.  Those belonging
 *	to PBSPro itself reside in and below "/dev/cpuset/PBSPro".
 */
#define	PBS_SHARE_PREFIX	"/shared/"
#define	DEV_CPUSET		"/dev/cpuset"
#define	DEV_CPUSET_ROOT		"/"
#define	PBS_CPUSETDIR		"/dev/cpuset/PBSPro"

/*
 *	Convert from absolute path name to one consumed by the ProPack 4
 *	CPU set interfaces (in which the initial "/dev/cpuset" is not used
 *	because the CPU set file system doesn't know where it's mounted).
 */
#define	CPUSET_REL_NAME(s)		((s) + sizeof(DEV_CPUSET) - 1)
#endif	/* CPUSET_VERSION >= 4 */
#endif	/* MOM_CPUSET */

#if	MOM_ALPS
/*
 *	Interface to the Cray ALPS placement scheduler. (alps.c)
 */
extern int	alps_create_reserve_request(
	job *,
	basil_request_reserve_t **);
extern void	alps_free_reserve_request(basil_request_reserve_t *);
extern int	alps_create_reservation(
	basil_request_reserve_t *,
	long *,
	unsigned long long *);
extern int	alps_confirm_reservation(job *);
extern int	alps_cancel_reservation(job *);
extern int	alps_inventory(void);
extern int	alps_suspend_resume_reservation(job *, basil_switch_action_t);
extern int	alps_confirm_suspend_resume(job *, basil_switch_action_t);
extern void	alps_system_KNL(void);
extern void	system_to_vnodes_KNL(void);
#endif	/* MOM_ALPS */

#if 	MOM_BGL
#define	CPUS_PER_CNODE 		2
#define	MEM_PER_CNODE  		(512*1024)	/* in kb */

#define	PNAME "partition"
#define PSET_SUFFIX "partition="
#define	CARD_DELIM "#"				/* vnode_name delimeter as in */
/* <bpid>#<qcard>#<ncard_id> */

#define       BGL_ENVIRONMENT_VARS            "BRIDGE_CONFIG_FILE, DB_PROPERTY, MMCS_SERVER_IP, DB2DIR, DB2INSTANCE"

#define BRIDGE_CONFIG_FILE	"/bgl/BlueLight/ppcfloor/bglsys/bin/bridge.config"
#define DB_PROPERTY		"/bgl/BlueLight/ppcfloor/bglsys/bin/db.properties"

#define DB2DIR_GET_CMD		"source /bgl/BlueLight/ppcfloor/bglsys/bin/db2profile; echo $DB2DIR"
#define DB2INSTANCE_GET_CMD	"source /bgl/BlueLight/ppcfloor/bglsys/bin/db2profile; echo $DB2INSTANCE"

#define	BGLADMIN		"bglsysdb"  /* special DB2 accounts */
#define	BGLCLIENT		"bgdb2cli"

typedef enum  {				/* BGL vnode states */
	BGLVN_UNKNOWN,
	BGLVN_FREE,
	BGLVN_BUSY,
	BGLVN_RESERVE,
	BGLVN_DOWN
} bgl_vnstate;

/* List of vnodes and their partitions */
struct bgl_vnode {
	struct bgl_vnode *nextptr;
	char    *vnode_name;  /* i.e. <bpid>#<quarter-id>#<nodecard-id> */
	bgl_vnstate state;
	int	num_cnodes;	/* resources_available.ncpus =          */
	/*      num_cnodes * CPUS_PER_CNODE     */
	/* will be sent to the server on a      */
	/* vnodemap update.                     */
	unsigned long amt_mem;	/* in kb */
	char    *part_list;
};

/* bgl_vnode functions */
extern struct bgl_vnode *bgl_vnode_create(char *vnode_name);
extern bgl_vnstate bgl_vnode_get_state(struct bgl_vnode *head,
	char *vnode_name);
extern int bgl_vnode_get_num_cnodes(struct bgl_vnode *head, char *vnode_name);
extern unsigned long bgl_vnode_get_amt_mem(struct bgl_vnode *head,
	char *vnode_name);
extern char *bgl_vnode_get_part_list(struct bgl_vnode *head, char *vnode_name);
extern char *bgl_vnode_get_part_list_spanning_vnode(struct bgl_vnode *head,
	char *vnode_name, char *bpid);
extern struct bgl_vnode *bgl_vnode_put_state(struct bgl_vnode *head,
	char *vnode_name, bgl_vnstate state);
extern struct bgl_vnode *bgl_vnode_put_num_cnodes(struct bgl_vnode *head,
	char *vnode_name, int num_cnodes);
extern struct bgl_vnode *bgl_vnode_put_amt_mem(struct bgl_vnode *head,
	char *vnode_name, unsigned long amt_mem);
extern struct bgl_vnode *bgl_vnode_put_part_list(struct bgl_vnode *head,
	char *vnode_name, char *part);

extern void bgl_vnode_free(struct bgl_vnode *head);
extern void bgl_vnode_print(struct bgl_vnode *head);

/* List of jobs (PBS and BGL)  and their assigned partition */
struct bgl_job {
	struct bgl_job *nextptr;
	db_job_id_t bgl_jobid;
	char	*pbs_jobid;			/* if assigned to PBS */
	char    *partition;
};

/* bgl_job functions */
extern struct bgl_job *bgl_job_create_given_bgl_jobid(db_job_id_t bgl_jobid);
extern struct bgl_job *bgl_job_create_given_pbs_jobid(char *pbs_jobid);

extern char *bgl_job_get_partition_given_bgl_jobid(struct bgl_job *head,
	db_job_id_t bgl_jobid);
extern char *bgl_job_get_partition_given_pbs_jobid(struct bgl_job *head,
	char *pbs_jobid);
extern db_job_id_t bgl_job_get_bgl_jobid(struct bgl_job *head, char *part);
extern char *bgl_job_get_pbs_jobid(struct bgl_job *head, char *part);

extern struct bgl_job *bgl_job_put_partition_given_bgl_jobid(\
		struct bgl_job *head, db_job_id_t bgl_jobid, char *part);
extern struct bgl_job *bgl_job_put_partition_given_pbs_jobid(\
			struct bgl_job *head, char *pbs_jobid, char *part);

extern struct bgl_job *bgl_job_put_pbs_jobid(struct bgl_job *head, char *part,
	char *pbs_jobid);

extern void bgl_job_free(struct bgl_job *head);
extern void bgl_job_print(struct bgl_job *head);

/* List of partitions and sizes */
struct bgl_partition {
	struct bgl_partition *nextptr;
	char    *part_name;
	int     num_cnodes;
};

/* bgl_partition functions */
extern struct bgl_partition *bgl_partition_create(char *part_name);
extern int bgl_partition_get_num_cnodes(struct bgl_partition *head, char *part_name);
extern struct bgl_partition *bgl_partition_put_part_name(\
					struct bgl_partition *head,
	char *part_name);
extern void bgl_partition_free(struct bgl_partition *head);
extern void bgl_partition_print(struct bgl_partition *head);

extern rm_partition_state_t get_bgl_partition_state(char *part_name);
extern int get_bgl_partition_size(char *part_name, int cnodes_per_bp,
	int cnodes_per_ncard);
extern struct bgl_job *get_bgl_jobs(void);
extern int verify_job_bgl_partition(job *pjob, int *job_error_code);
extern void evaluate_vnodes_phys_state(struct bgl_vnode **p_bglvns,
	char *vn_list, int *num_vns_down, int *num_vns_up, char **down_vn_list);
extern char * job_bgl_partition(job *pjob);
extern int job_bgl_delete(job *pjob);

/* Global variables */
extern char    *reserve_bglpartitions;    	 /* comma-separated list of reserved */
extern struct bgl_partition 	*bglpartitions;       /* unreserved partitions */
extern struct bgl_partition 	*bglpartitions_down;  /* partitions marked down */
extern struct bgl_vnode 	*bglvnodes;           /* vnodes in the system */
extern	char    		*downed_bglvnodes;    /* vnodes phys. down */
extern struct bgl_job 		*stuck_bgljobs;       /* "hanging" BGL jobs */
#endif	/* MOM_BGL */

#define	COMSIZE		12
typedef struct proc_stat {
	pid_t		session;	/* session id */
	char		state;		/* one of RSDZT: Running, Sleeping,
						 Sleeping (uninterruptable), Zombie,
						 Traced or stopped on signal */
	pid_t		ppid;		/* parent pid */
	pid_t		pgrp;		/* process group id */
	ulong		utime;		/* utime this process */
	ulong		stime;		/* stime this process */
	ulong		cutime;		/* sum of children's utime */
	ulong		cstime;		/* sum of children's stime */
	pid_t		pid;		/* process id */
	ulong		vsize;		/* virtual memory size for proc */
	ulong		rss;		/* resident set size */
	ulong		start_time;	/* start time of this process */
	ulong		flags;		/* the flags of the process */
	ulong		uid;		/* uid of the process owner */
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
#endif /* MOM_MACH */
#ifdef	__cplusplus
}
#endif
#endif /* _MOM_MACH_H */

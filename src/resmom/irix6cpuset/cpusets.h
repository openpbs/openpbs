/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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
#ifndef	_CPUSETS_H
#define	_CPUSETS_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <sys/types.h>
#include <cpuset.h>
#include "bitfield.h"
#include "pbs_ifl.h"
#include "list_link.h"
#include "attribute.h"
#include "resource.h"
#include "server_limits.h"
#include "job.h"
#include "cpusets_shared.h"

/* Definitions and constants used by cpuset manipulation code. */

/* Name of a cpuset containing "reserved" or "system" resources. */
#define	RESERVED_CPUSET		"boot"

/* Suffix of filename to create in jobs dir as cpuset's controlling file. */
#define JOB_CPUSETQ_SUFFIX	".cq"

/* Number of chars in a cpuset queue name (not including NULL terminator. */
#define QNAME_STRING_LEN	8

/* MOM_CPUSET_PERMS
 *
 * Set the permissions bits on the vnode associated with the cpuset created
 * for each job.
 *
 * The owner can do anything with the cpuset (except create/destroy).  Any
 * other user can query the cpuset, but cannot execute within it or make any
 * changes to it.
 */
#define MOM_CPUSET_PERMS	S_IRWXU|S_IRGRP|S_IROTH

/* Struct used to maintain lists of cpusets. */
typedef struct cpusetlist {
	struct cpusetlist	*next;		/* Link to next element. */
	char		name[QNAME_STRING_LEN + 1];	/* Name of cpuset. */
	Bitfield		nodes;		/* Nodes held by this cpuset. */
	cpuset_shared	*sharing;	/* set if cpuset is shared */
} cpusetlist;

/* Function declarations for cpuset support library. */
int	query_cpusets(cpusetlist **, Bitfield *);
int	create_cpuset(char *, Bitfield *, char *, uid_t, gid_t);
int	destroy_cpuset(char *);
char	*current_cpuset(void);
int	attach_cpuset(char *);
int	teardown_cpuset(char *, Bitfield *);
int	reclaim_cpusets(cpusetlist **, Bitfield *);

int	add_to_cpusetlist(cpusetlist **, char *, Bitfield *, cpuset_shared *);
int	remove_from_cpusetlist(cpusetlist **, Bitfield *, char *, cpuset_shared *);
char	*job_to_qname(job *);
int	free_cpusetlist(cpusetlist *);
cpusetlist *find_cpuset(cpusetlist *, char *);
cpusetlist *find_cpuset_shared(cpusetlist *, cpuset_shared *);
cpusetlist *find_cpuset_byjob(cpusetlist *, char *);
int	shared_nnodes(cpusetlist *);
void print_cpusets(cpusetlist *, char *);

char  *string_to_qname(char *);

int	bitfield2cpuset(Bitfield *, cpuset_CPUList_t  *);
int	cpuset2bitfield(char *, Bitfield *);

unsigned long cpuset_create_flags_map(char *);
void	cpuset_create_flags_print(char *, int);
unsigned long cpuset_destroy_delay_set(char *);
unsigned long cpuset_small_ncpus_set(char *);
unsigned long cpuset_small_mem_set(char *);

int nodemask_num_cpus(Bitfield *);
int nodemask_tot_mem(Bitfield *);	/* in kb */
int is_small_job(job *, cpuset_shared *);
int is_small_job2(job *, size_t, int, cpuset_shared *);
void cpuset_permfile(char *, char *);	/* returns name of permfile */
void cleanup_cpuset_permfiles(void);	/* cpuset permfile housekeepings */
int  is_cpuset_pbs_owned(char *);	/* return 1 if cpuset is owned by pbs */
int  remove_non_pbs_cpusets(cpusetlist **, Bitfield *);

/* External data items used by cpusets code. */
extern	cpusetlist	*stuckcpusets;		/* from mom_mach.c */
extern	Bitfield	stucknodes;		/* from mom_mach.c */
extern	Bitfield	nodepool;		/* from mom_mach.c */
extern	cpusetlist	*inusecpusets;		/* from mom_mach.c */
extern  int		cpuset_create_flags;
extern  int		cpuset_destroy_delay;
extern  int		cpuset_small_ncpus;
extern  int		cpuset_small_mem;
#ifdef	__cplusplus
}
#endif
#endif /* _CPUSETS_H */

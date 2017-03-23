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
#ifndef	_CPUSETS_SHARED_H
#define	_CPUSETS_SHARED_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <sys/types.h>
#include <cpuset.h>
#include "pbs_ifl.h"
/*
 * Macros:
 *
 */

/* Struct used to maintain shared cpusets. */

typedef struct cpuset_shared {
	int		free_cpus;
	size_t		free_mem;	/* in kb */
	time_t		time_to_live;	/* based on longest job wrpt walltime */
	int		numjobs;	/* # of jobs assigned to this cpuset */
	/* following are cached information */
	char		owner[PBS_MAXSVRJOBID+1]; /*set to 1st job in jobs*/
	void		*jobs;		/* a list of jobids */
} cpuset_shared;

/* Function declarations for cpuset support library. */
cpuset_shared *cpuset_shared_create(void);

void cpuset_shared_unset(cpuset_shared *);
int cpuset_shared_is_set(cpuset_shared *);

int cpuset_shared_get_free_cpus(cpuset_shared *);
void cpuset_shared_set_free_cpus(cpuset_shared *, int);

size_t cpuset_shared_get_free_mem(cpuset_shared *);
void cpuset_shared_set_free_mem(cpuset_shared *, size_t);

time_t cpuset_shared_get_time_to_live(cpuset_shared *);
void cpuset_shared_set_time_to_live(cpuset_shared *);

char *cpuset_shared_get_job_owner(cpuset_shared *);
void cpuset_shared_set_job_owner(cpuset_shared *, char *);

char *cpuset_shared_get_job_owner(cpuset_shared *);
void cpuset_shared_set_job_owner(cpuset_shared *, char *);

void cpuset_shared_add_job(cpuset_shared *, char *, time_t);
void cpuset_shared_remove_job(cpuset_shared *, char *);
int cpuset_shared_get_numjobs(cpuset_shared *);
int cpuset_shared_is_job_member(cpuset_shared *, char *);

void cpuset_shared_free(cpuset_shared *);
void cpuset_shared_print(cpuset_shared *);
#ifdef	__cplusplus
}
#endif
#endif /* _CPUSETS_SHARED_H */

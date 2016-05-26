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
#ifndef	_MAPNODES_H
#define	_MAPNODES_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <sys/types.h>

#if !defined(__STDC__)
#define const
#define volatile
#endif  /* __STDC__ */

/*
 * The Origin2000 (SN0) architecture supports at most 2 cpus per node and no
 * more than 256 nodes total (due to 8-bit nodeid_t's).  However, there is
 * talk of building larger systems (up to 2048P?).  The upper limit imposed
 * within the hardware is around 4096P, so use that for fixed arrays.
 *
 * Memory is cheap.  Debugging buffer overruns is tedious and expensive.
 */
#define	MAX_CPUS_PER_NODE	4
#define	MAX_NODES_PER_HOST	2048
#define	MAX_CPUS_PER_HOST	((MAX_NODES_PER_HOST)*(MAX_CPUS_PER_NODE))
#define	MAX_NODES_PER_MODULE	4

/*
 * These declarations specify the minimal physical resources that must be
 * present on a node in order for it to be considered "availalble" to
 * allocate to a job.
 *
 * See mom_mach.c:availnodes() function.
 */
#define MIN_MEMORY_PER_NODE	512		/* Require 512MB/node minimum */
#define MIN_CPUS_PER_NODE	2		/* Require 2 cpus/noe minimum */


/* Description of resources and paths for each node as discovered at startup. */
typedef struct nodedesc {
	cpuid_t		cpu[MAX_CPUS_PER_NODE];	/* CPUs resident on this node */
	moduleid_t	module;			/* Which module holds node */
	unsigned short  rack;                   /* Which rack holds the module*/
	unsigned short	slot;			/* Which slot in the module */
	int		memory;			/* Memory (in mb) on node */
} nodedesc;

/* Pointers to maps. */
extern nodedesc		*nodemap;	/* Map from node to cpus/memory. */
extern cnodeid_t	*cpumap;	/* Map from cpuid to cnodeid_t. */

/* Pointers to maximum values in maps. */
extern cnodeid_t	maxnodeid;
extern cpuid_t		maxcpuid;
extern int		maxnodemem;
extern int		maxnodecpus;

/* Physical <--> Logical Node mappings: */
extern int *schd_nodes_phys2log;
extern int *schd_nodes_log2phys;

int	mapnodes(void);
int	availnodes(Bitfield *);
#ifdef	__cplusplus
}
#endif
#endif /* _MAPNODES_H */

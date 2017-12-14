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
 * @file	mapnodes.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <sys/sysmp.h>
#include <sys/iograph.h>
#include <invent.h>

#define SN0 1

#include <sys/SN/arch.h>
#include <sys/SN/SN0/arch.h>
#include <sys/SN/SN0/router.h>
#include <sys/SN/SN0/sn0drv.h>

#ifdef HAVE_HUBSTAT_H
#include <sys/SN/hubstat.h>
#endif

#include "bitfield.h"
#include "mapnodes.h"
#include "mom_share.h"
#include "log.h"

#define WHY strerror(errno)

#define MAXTXT 4096

#define HW_NODENUM_PATH "/hw/nodenum"
#define HW_PATH_SUFFIX  "/hub/mon"
#define HW_MODULE_PATH  "/hw/module"

/*==========================================================*/
/* the following structure definitions are only needed here */
/*                                                          */
/* they remember "just enough" topology for us to "get by"  */
/*==========================================================*/
struct node {
	int             logical_nbr;    /* given by its _name_ */
	int             physical_nbr;   /* its NASID */
	struct node     *next;
	/* following here for 'mapnodes()' replacement: */
	cpuid_t         cpu[MAX_CPUS_PER_NODE];
	int		memory;         /* memory (in mbytes) for a node */
	moduleid_t      module;		/* Origin2000 */
	unsigned short  slot;		/* Origin2000 */
	unsigned short	rack;		/* Origin3000 */
};

/* linked list of nodes */
static struct node *first_node = NULL;
static struct node *last_node = NULL;
/* linearized version of that list: */
static int n_nodes = 0;
static struct node *Nodes;


/*=====================================*/
/* the Whole Point(tm) of all of this: */
/*=====================================*/
int *schd_nodes_phys2log = NULL;
int *schd_nodes_log2phys = NULL;

/* The actual maps themselves.  Static to this file to avoid surprises. */
static	nodedesc	xnodemap[MAX_NODES_PER_HOST];
static	cnodeid_t	xcpumap[MAX_CPUS_PER_HOST];

/*
 * Pointers to the maps above.  They are left NULL until the maps have been
 * populated.
 */
nodedesc		*nodemap	= NULL;
cnodeid_t		*cpumap		= NULL;

/* Minimum/maximum values found for physical configuration. */
cnodeid_t		maxnodeid	= -1;
cpuid_t			maxcpuid	= -1;
int			maxnodemem	= 0;
int			maxnodecpus	= 0;
static int		minmem		= 0;
static int		mincpus		= 0;


static char log_bfr[4096];

/*==================*/
/* local prototypes */
/*==================*/
void schd_get_topology(void);
void get_cpus(char *dirname, cpuid_t *cpulist);
void get_mem(char *pathname, int *memp);
static void cleanup_topology_data(void);
static int cmp_nodes(const void *e1, const void *e2);

/*
 * Physical hardware/location discovery code.
 * Grovel through the hardware graph pseudo-filesystem for the location of
 * each node, and the physical memory configured on it.
 */

/**
 * @brief
 * 	mapnodes() - Create mappings from cpu to node, 
 *	and from node to cpus and memory resident
 * 	on that node.
 *
 * @return	int
 * @retval	0 		on success, 
 * @retval	non-zero 	on error.
 *
 */
int
mapnodes(void)
{
	int node_nbr;
	int i = 0;
	int j;
	int count;

	/*===============================================*/
	/* the scheduler and pbs_mom have to agree about */
	/* the actual topology of the system, sooo we'll */
	/*   simply _steal_ the topology discovery code  */
	/*===============================================*/
	schd_get_topology();

	/*=============================================*/
	/* now, map the scheduler's data structures to */
	/*  those that were invented for 'mapnodes()'  */
	/*=============================================*/
	memset(xnodemap, 0, sizeofxnodemap);
	memset(xcpumap, 0, sizeofxcpumap);
	for (i=0 ; i < MAX_NODES_PER_HOST ; ++i)
		for (j=0 ; j < MAX_CPUS_PER_NODE ; ++j)
			xnodemap[i].cpu[j] = -1;
	for (i=0 ; i < MAX_CPUS_PER_HOST ; ++i)
		xcpumap[i] = -1;

	maxnodeid = -1;
	for (i=0 ; i < n_nodes ; ++i) {
		node_nbr = Nodes[i].logical_nbr;
		if (maxnodeid < node_nbr)
			maxnodeid = node_nbr;
		xnodemap[i].module = Nodes[i].module;
		xnodemap[i].slot   = Nodes[i].slot;
		xnodemap[i].rack   = Nodes[i].rack;
		for (count=j=0 ; j < MAX_CPUS_PER_NODE ; ++j) {
			xnodemap[i].cpu[j] = Nodes[i].cpu[j];
			xcpumap[Nodes[i].cpu[j]] = node_nbr;
			if (Nodes[i].cpu[j] >= 0)
				count++;
		}

		if (Nodes[i].memory <= 0)
			xnodemap[i].memory = MIN_MEMORY_PER_NODE;
		else
			xnodemap[i].memory = Nodes[i].memory;

		/* calculate the min # of cpus per nodeboard */
		/* this can be overwritten via the config files */
		if (!mincpus || count < mincpus)
			mincpus = count;

		/* calculate smallest memory on a node. */
		if (!minmem || xnodemap[i].memory < minmem)
			minmem = xnodemap[i].memory;

		/* calculate maximum memory on a node. */
		if (!maxnodemem || xnodemap[i].memory > maxnodemem)
			maxnodemem = xnodemap[i].memory;

		/* calculate maximum # of cpus per nodeboard. */
		if (!maxnodecpus || count > maxnodecpus)
			maxnodecpus = count;
	}


	maxcpuid = -1;
	for (i=0 ; i < MAX_CPUS_PER_HOST ; ++i)
		if (xcpumap[i] != -1)
			maxcpuid = i;

	nodemap = xnodemap;
	cpumap  = xcpumap;

	return 0;
}

/**
 * @brief
 * 	availnodes() - Fill the supplied bitfield with a set bit for each node on which sufficient
 * 	resources (c.f. mapnodes.h) are configured.  This is the set of nodes that
 * 	are physically available to be allocated -- policy, reserved nodes, etc,
 * 	may reduce the total number of nodes that are usable by jobs.
 *
 * NOTE: Must be called after mapnodes().
 *
 * @param[out] maskp - pointer to Bitfield structure
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	failure
 *
 */
int
availnodes(Bitfield *maskp)
{
	int			node, i, count;
	Bitfield		avail;

	/* This function needs a valid node map in order to find available nodes. */
	if (nodemap == NULL)
		return 1;

	/*
	 * If minimum resource values are not set, default them to reasonable
	 * defaults.
	 */
	if (minnodemem < 0)
		minnodemem = minmem;
	if (minnodecpus < 0)
		minnodecpus = mincpus;
	if (memreserved < 0)
		memreserved = 0;

	(void)sprintf(log_buffer,
		"Minimum node resources: %d cpus, %d MB, %d MB rsvd",
		minnodecpus, minnodemem, memreserved);
	log_err(-1, __func__, log_buffer);

	BITFIELD_CLRALL(&avail);

	/*
	 * Walk through the node map, checking for sufficient resources on each
	 * node, and setting the appropriate bit on the mask for that node if it
	 * is sufficiently endowed.  See mapnodes.h for definition of "sufficient".
	 */
	for (node = 0; node <= maxnodeid; node++) {
		/* Enough CPUs?  If not, skip it. */
		for (count = i = 0; i < MAX_CPUS_PER_NODE; i++)
			if (nodemap[node].cpu[i] >= 0)
				count ++;

		/* Enough memory and cpus?  If not, skip it. */
		if (nodemap[node].memory < minnodemem || count < minnodecpus) {
			(void)sprintf(log_buffer,
				"node %d has only %luMB and %d cpus - cannot use",
				node, nodemap[node].memory, count);
			log_err(-1, __func__, log_buffer);

			continue;
		}

		/* Node has sufficient resources.  Count this node as available. */
		BITFIELD_SETB(&avail, node);
	}

	/* Copy the available mask to the passed-in storage, and return success. */
	BITFIELD_CPY(maskp, &avail);

	return 0;
}

int n_cpus;	/* holds nbr of working CPUs ( == 1st invalid CPU nbr ) */

/** 
 * @brief
 *	read nodes and get topology
 *
 */
void
schd_get_topology(void)
{
	char *whoami = "schd_get_topology";
	DIR *dirp;
	struct dirent *dent;
	char *digits ="0123456789";
	char path[MAXPATHLEN];
	char realpath[MAXPATHLEN];
	char realpath2[MAXPATHLEN];
	int len;
	struct node *p;
	int i;
	int j;
	char *s;
	int max_nasid = -1;

#ifdef HAVE_HUBSTAT_H
	int fd;
	hubstat_t hs;
#endif

	/*================================================*/
	/* if not our first time, we need to give back a  */
	/* bunch of heap space before we get started here */
	/*================================================*/
	cleanup_topology_data();

	n_cpus = sysmp(MP_NPROCS);

	/*=======================================*/
	/* figure out just which nodes we've got */
	/*=======================================*/
	if ((dirp=opendir(HW_NODENUM_PATH)) == NULL) {
		sprintf(log_bfr, "opendir(%s)", HW_NODENUM_PATH);
		log_err(errno, whoami, log_bfr);
		exit(EXIT_FAILURE);
	}
	rewinddir(dirp);

	while (dent=readdir(dirp)) {
		/* only want those whose names consist solely of digits */
		if (strspn(dent->d_name, digits) < strlen(dent->d_name))
			continue;
		sprintf(path, "%s/%s", HW_NODENUM_PATH, dent->d_name);
		if ((len = readlink(path, realpath, sizeofrealpath)) < 0) {
			sprintf(log_bfr, "readlink(%s)", path);
			log_err(errno, whoami, log_bfr);
			continue;
		}
		realpath[len] = '\0';	/* 'readlink()' punts on this */
		p = malloc(sizeof*p);
		if (p == NULL) {
			strcpy(log_bfr, "malloc failed");
			log_err(errno, whoami, log_bfr);
			return;		/* probably a BAD choice */
		}
		p->logical_nbr  = atoi(dent->d_name);

		strcat(path, HW_PATH_SUFFIX);
#ifdef HAVE_HUBSTAT_H
		if ((fd=open(path, O_RDONLY)) < 0) {
			sprintf(log_bfr, "open(%s)", path);
			log_err(errno, whoami, log_bfr);
			continue;	/* ??? */
		}

		if (ioctl(fd, SN0DRV_GET_HUBINFO, &hs) < 0) {
			sprintf(log_bfr, "ioctl(%s,GET_HUBINFO)", path);
			log_err(errno, whoami, log_bfr);
			continue;	/* as before: ??? */
		}
		close(fd);
		p->physical_nbr = hs.hs_nasid;
#else
		p->physical_nbr = p->logical_nbr;
#endif

		if (max_nasid < p->physical_nbr)
			max_nasid = p->physical_nbr;

		p->next = NULL;

		s = strstr(realpath, "slot/");
		if (s) {				/* Origin2000 */
			p->slot = atoi(s+5);
			s = strstr(realpath, "module/");
			p->module = atoi(s+7);
			p->rack = 0;
		} else {				/* Origin3000 */
			s = strstr(realpath, "module/");
			p->rack = atoi(s+7);
			p->module = 0;
			p->slot = 0;
		}

		for (i=0 ; i < MAX_CPUS_PER_NODE ; ++i)
			p->cpu[i] = -1;

		strcpy(realpath2, realpath);
		strcat(realpath, "/cpu");
		get_cpus(realpath, p->cpu);

		strcat(realpath2, "/memory");
		get_mem(realpath2, &p->memory);

		/* add this one to our list */
		if (n_nodes == 0)
			first_node = p;
		else
			last_node->next = p;
		last_node = p;
		++n_nodes;
	}
	closedir(dirp);

	/* linearize */
	if (n_nodes) {
		Nodes = malloc(n_nodes*sizeof*Nodes);
		if (Nodes == NULL) {
			sprintf(log_bfr, "malloc(%d nodes)", n_nodes);
			log_err(errno, whoami, log_bfr);
			return;
		}
		i = 0;
		p = first_node;
		while (p) {
			Nodes[i] = *p;
			free(p);
			p = Nodes[i++].next;
		}
		first_node = last_node = NULL;

		/* empirically, next is *unnecessary* */
		qsort(Nodes, n_nodes, sizeof*Nodes, cmp_nodes);
	}

	/*===========================================================*/
	/* now for the Whole Point(tm): determine the permutation    */
	/* that maps "logical" to "physical" node numbers. And its   */
	/* inverse, while we're at it [as it's useful down the road] */
	/*===========================================================*/
	++max_nasid;
	schd_nodes_log2phys = malloc(max_nasid*sizeof*schd_nodes_log2phys);
	if (schd_nodes_log2phys == NULL) {
		strcpy(log_bfr, "malloc(schd_nodes_log2phys)");
		log_err(errno, whoami, log_bfr);
		return;
	}
	schd_nodes_phys2log = malloc(max_nasid*sizeof*schd_nodes_phys2log);
	if (schd_nodes_phys2log == NULL) {
		strcpy(log_bfr, "malloc(schd_nodes_phys2log)");
		log_err(errno, whoami, log_bfr);
		return;
	}

	for (j=0 ; j < max_nasid ; ++j)
		schd_nodes_log2phys[j] = schd_nodes_phys2log[j] = -1;

	for (i=0 ; i < n_nodes ; ++i) {
		j = Nodes[i].physical_nbr;
		schd_nodes_log2phys[i] = j;
		schd_nodes_phys2log[j] = i;
	}

	return;
}

/**
 * @brief
 *	read dirp directory and get number of cpus
 *
 */
void
get_cpus(char *dirname, cpuid_t *cpulist)
{
	char *whoami = "get_cpus";
	DIR *dirp;
	struct dirent *dent;
	char pathname[MAXTXT];
	int len;
	char info[512];
	invent_cpuinfo_t *cpuinfo;

	if ((dirp=opendir(dirname)) == NULL) {
		sprintf(log_bfr, "opendir(%s)", dirname);
		log_err(errno, whoami, log_bfr);
		exit(EXIT_FAILURE);
	}
	rewinddir(dirp);

	while (dent=readdir(dirp)) {
		if (dent->d_name[0] == '.')
			continue;
		sprintf(pathname, "%s/%s", dirname, dent->d_name);
		len = sizeofinfo;
		if (attr_get(pathname, INFO_LBL_DETAIL_INVENT, info, &len, 0))
			break;
		cpuinfo = (invent_cpuinfo_t *)info;
		if (cpuinfo->ic_cpuid < n_cpus)
			cpulist[cpuinfo->ic_slice] = cpuinfo->ic_cpuid;
	}
	closedir(dirp);

	return;
}

/**
 * @brief
 *	get memory information.
 *
 * @param[in] pathname - pathname
 * @param[out] memp - memory info
 *
 */
void
get_mem(char *pathname, int *memp)
{
	int len;
	char info[512];
	invent_meminfo_t *meminfo;

	len = sizeofinfo;
	if (attr_get(pathname, INFO_LBL_DETAIL_INVENT, info, &len, 0) == 0) {
		meminfo = (invent_meminfo_t *)info;
		*memp = (int)meminfo->im_size;

	}
	return;
}

/**
 * @brief
 *	cleans up the topology data
 *
 */
static void
cleanup_topology_data(void)
{
	int i;
	struct node *p;
	struct node *r;

	if (n_nodes) {
		if (first_node) {
			p = first_node;
			while (p) {
				r = p->next;
				free(p);
				p = r;
			}
			first_node = last_node = NULL;
		} else {
			for (i=0 ; i < n_nodes ; ++i)
				free(Nodes+i);
			free(Nodes);
			Nodes = NULL;
		}
		n_nodes = 0;
	}

	free(schd_nodes_log2phys);
	free(schd_nodes_phys2log);

	return;
}

/**
 * @brief
 * 	'qsort()' comparison function for [unnecessary] sort of 'Nodes' 
 * 
 * @param[in] e1 - node1 info
 * @param[in] e2 - node2 info
 *
 * @return	int
 * @retval	diff btw logical num of nodes
 *
 */
static int
cmp_nodes(const void *e1, const void *e2)
{
	struct node *n1 = (struct node *)e1;
	struct node *n2 = (struct node *)e2;

	return n1->logical_nbr - n2->logical_nbr;
}

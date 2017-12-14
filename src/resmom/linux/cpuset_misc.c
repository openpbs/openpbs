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
#include	"pbs_config.h"
/**
 * @file	cpuset_misc.c
 */
#if	defined(MOM_CPUSET) && (CPUSET_VERSION >= 4)
#include	<assert.h>
#include	<errno.h>
#include	<ftw.h>
#include	<string.h>
#include	<stdlib.h>
#include	<stdio.h>
#include	<sys/param.h>
#include	<unistd.h>
#include	<dirent.h>
#include	<sys/stat.h>

#include	"list_link.h"
#include	"log.h"
#include	"attribute.h"
#include	"server_limits.h"
#include	"job.h"
#include	"mom_func.h"
#include	"mom_mach.h"
#include	"mom_vnode.h"

/*
 *	ftw() is a rather clumsy interface to use in this instance, since it
 *	neither allows for customized arguments to be passed to the function
 *	called for each directory entry found nor is there a technique provided
 *	for returning data when the walk terminates.  To work around these
 *	limitations, we use this general technique
 *
 *		foo_setup()		passes information to be cached and
 *					used during each foo() invocation;
 *					the static variables below capture
 *					this information
 *		ftw(..., foo, ...)
 *		foo_return()		reaps the results after ftw() terminates
 */
static int		cleanup_failflag;	/* did cleaning /PBSPro fail? */
static int		*ignoredcpus;		/* array of ignored CPUs ... */
static int		ignoredcpus_maxsize;	/* ... and its maximum size */
static int		reassoc_err;		/* set if no job for a CPU */
static int		restart_nsets;		/* #sets in restart_setlist[] */

static struct bitmask	*availcpus_bits;	/* bitmask of available CPUs */
static struct bitmask	*cpubits;
static struct bitmask	*reassoc_bits;

static void		inuse_prep(void);
static void		remove_subset(const char *, const char *);
static void		reset_cpubits(void);
static void		reset_availcpus_bits(void);
static void
reassoc_job_with_cpus(const char *,
	struct bitmask *);
static void		restart_addset(const char *);
static int		revdirsort(const void *, const void *);

static char		**restart_setlist;

#define	ROUNDDOWN(n, to)	(((n) / (to)) * (to))

/**
 * @brief
 *	sets up the restart
 *
 * @return Void
 *
 */

void
restart_setup(void)
{
	restart_setlist = NULL;
	restart_nsets = 0;
	cleanup_failflag = 0;
}

/**
 * @brief
 *	Try to remove the CPU sets in restart_setlist[] (a list constructed by
 *	restart_cleanupprep()).  If a CPU set cannot be removed, we interpret it
 *	as a sign that tasks are still running in it and mom should be restarted
 *	with a flag to tell it either to kill or preserve them.
 *
 * @param[in] ret - flag to indicate cpu set to be killed or preserved
 *
 * @return Void
 *
 */
void
restart_return(int *ret)
{
	int		i;

	if (restart_setlist != NULL) {
		qsort(restart_setlist, restart_nsets,
			sizeof(*restart_setlist), revdirsort);
		for (i = 0; i < restart_nsets; i++) {
			char	*file = restart_setlist[i];

			if (cpuset_delete(CPUSET_REL_NAME(file)) == -1) {
				sprintf(log_buffer,
					"cpuset_delete %s failed, errno %d",
					CPUSET_REL_NAME(file), errno);
				log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
					LOG_ERR, __func__, log_buffer);

				/* try harder */
				if (rmdir(file) == -1) {
					cleanup_failflag = 1;
					sprintf(log_buffer,
						"rmdir %s failed, errno %d",
						file, errno);
					log_event(PBSEVENT_SYSTEM,
						PBS_EVENTCLASS_NODE, LOG_ERR, __func__,
						log_buffer);
				}
			}
			free(file);
		}
		free(restart_setlist);
	}

	*ret = cleanup_failflag;
}

/**
 * @brief
 *	compare cpu from cpu list
 *
 * @param[in] s1 - cpu 1
 * @param[in] s1 - cpu 2
 *
 * @return int
 * @retval 	1, -1		Failure
 * @retval 	0		Success
 *
 */

static int
revdirsort(const void *s1, const void *s2)
{
	int	ret = strcmp(*((const char **) s1), *((const char **) s2));

	if (ret < 0)
		return (1);
	else if (ret == 0)
		return (0);
	else
		return (-1);
}

/**
 * @brief
 *	wrapper function for reset_availcpus_bits and reset_cpubits.
 *
 * @return Void
 *
 */
static void
inuse_prep(void)
{
	assert(cpus_nbits != 0);
	reset_availcpus_bits();
	reset_cpubits();
}

/**
 * @brief
 *	gets cpubits while parsing the vnode defn
 *
 * @return Void
 *
 */

static void
reset_availcpus_bits(void)
{
	(void) get_cpubits(availcpus_bits);
}

/**
 * @brief
 *	resets the cpubits
 *
 * @return Void
 *
 */

static void
reset_cpubits(void)
{

	/* freed by the *_return() functions */
	if ((cpubits = bitmask_alloc(cpus_nbits)) == NULL) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_ERR,
			__func__, "bitmask_alloc failed");
		return;
	}
	bitmask_clearall(cpubits);
}

/**
 * @brief
 *	sets up for cpu to be ignored
 *
 * @return Void
 *
 */

void
cpuignore_setup(int *ignoredest, int nignoreentries, struct bitmask *availdest)
{
	ignoredcpus = ignoredest;
	ignoredcpus_maxsize = nignoreentries;
	availcpus_bits = availdest;
	inuse_prep();
}

/**
 * @brief
 *	
 * @return Void
 *
 */

void
cpuignore_return(void)
{
#ifdef	DEBUG
#endif	/* DEBUG */
	int		cpunum;
	int		firstbit, lastbit;

	if (cpubits == NULL)
		return;

	firstbit = bitmask_first(cpubits);
	lastbit = bitmask_last(cpubits);
	if (firstbit == bitmask_nbits(cpubits)) {
		DBPRT(("cpuignore_return:  cpubits mask is empty\n"))
		return;
	}
	DBPRT(("cpuignore_return:  cpubits has weight %d\n",
		bitmask_weight(cpubits)))
	for (cpunum = firstbit; cpunum <= lastbit;
		cpunum = bitmask_next(cpubits, cpunum + 1)) {
		assert(cpunum < ignoredcpus_maxsize);
		ignoredcpus[cpunum] = 1;
#ifdef	DEBUG
		/*
		 *	Nowadays, the PBS startup script is expected to pitch
		 *	from the vnode definitions file any CPUs it discovers
		 *	are in use when PBS starts.  Thus we should not have
		 *	discovered it's still set in availcpus_bits, which was
		 *	set in reset_availcpus() to contain only those CPUs in
		 *	vnode definitions files.
		 */
		if (bitmask_isbitset(availcpus_bits, cpunum)) {
			sprintf(log_buffer, "unexpected CPU (%d)", cpunum);
			log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
				log_buffer);
		}
#endif	/* DEBUG */
		bitmask_clearbit(availcpus_bits, cpunum);
	}

	bitmask_free(cpubits);
}

/** 
 * @brief
 * 	set up for reassociating cpus for job
 *
 * @param[in] ncpus - number of cpus
 *
 * @return Void
 *
 */

void
reassociate_job_cpus_setup(int ncpus)
{
	assert(ncpus != 0);

	reassoc_err = 0;
	if ((reassoc_bits = bitmask_alloc(ncpus)) == NULL)
		perror("bitmask_alloc");
}

/**
 * @brief
 *	If we had a failure in reassociate_job_cpuset_setup(), or
 *	there was a CPU for which we could find no job (the latter
 *	likely is caused by restarting pbs_mom without the -p flag,
 *	causing us to kill off any jobs we find still running, but
 *	leaving the job's CPU set intact), indicate an error.
 *
 * @return 	int
 * @retval 	0	Success
 * @retval 	1	Failure
 *
 */

int
reassociate_job_cpus_return(void)
{
	if (reassoc_bits == NULL)
		return (1);
	else
		free(reassoc_bits);

	if (reassoc_err != 0)
		return (1);
	else
		return (0);
}

/**
 * @brief
 *	This function is called by the ftw() in cpusets_initialize().
 *	It initializes the ignoredcpus[] array with a list of CPUs
 *	belonging to jobs that PBSPro does not manage.  This is a
 *	depth one search of DEV_CPUSET.
 *
 *	Because of the constraint that a CPU set's CPUs are always a subset
 *	of its parent's, we need do only a depth one search of /dev/cpuset.
 *	Unfortunately, nftw(3), which includes a depth indication when calling
 *	the iteration function, requires that we define both _XOPEN_SOURCE and
 *	_XOPEN_SOURCE_EXTENDED, which severely breaks PBSPro due to its use of
 *	nonstandardized types.  Thus are we reduced to counting the number of
 *	'/' characters in the path name we're handed.
 *
 * @param[in] file - filename
 * @param[in] sb - pointer to stat structure
 * @param[in] flag -
 *
 * @return 	int
 * @retval   	0	Success
 * @retval 	1	Failure
 *
 */

int
inuse_cpus(const char *file, const struct stat *sb, int flag)
{
	static struct cpuset	*cp = NULL;
	static struct bitmask	*thissetcpubits = NULL;
	char			*p;
	int			nslashes;
	int			slashmax;
#ifdef	DEBUG
	int			cpunum;
	int			firstbit, lastbit;
#endif	/* DEBUG */

	if (availcpus_bits == NULL)
		return (1);
	if (cpubits == NULL)
		return (1);

	/* one-time-only initializations */
	if (thissetcpubits == NULL)
		if ((thissetcpubits = bitmask_alloc(cpus_nbits)) == NULL) {
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
				LOG_ERR, __func__, "bitmask_alloc failed");
			return (1);
		}
	if (cp == NULL)
		if ((cp = cpuset_alloc()) == NULL) {
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
				LOG_ERR, __func__, "cpuset_alloc failed");
			return (1);
		}

	/* only interested in directory names ... */
	if (flag != FTW_D)
		return (0);
	/* ... that don't belong to us */
	if (strstr(file, PBS_CPUSETDIR) == file)
		return (0);
	/* skip all the PBS infrastructure directories themselves */
	if (is_pbs_container(file))
		return (0);

	/*
	 *	A depth one search of DEV_CPUSET corresponds to the magic
	 *	number of exactly three '/'s (DEV_CPUSET itself contains
	 *	two, and may be skipped).
	 *
	 *	Also, note that cpuset_query() does not work on absolute path
	 *	names, so it's necessary to strip off the initial prefix using
	 *	the CPUSET_REL_NAME() macro.
	 */
	slashmax = 4;
	for (p = (char *)file, nslashes = 0; p && *p && (nslashes < slashmax);
		p++)
		if (*p == '/')
			nslashes++;
	if ((nslashes >= slashmax) || (nslashes == 2)) {
		DBPRT(("%s:  file %s, nslashes %d\n", __func__, file, nslashes))
		return (0);
	}

	if (cpuset_query(cp, CPUSET_REL_NAME(file)) == -1) {
		sprintf(log_buffer, "cpuset_query %s (%s) failed",
			file, CPUSET_REL_NAME(file));
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
			LOG_ERR, __func__, log_buffer);
		return (0);
	}
	if (cpuset_getcpus(cp, thissetcpubits) == -1) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
			LOG_ERR, __func__, "cpuset_getcpus failed");
		return (0);
	}

#ifdef	DEBUG
	DBPRT(("%s:  set %s has CPU weight %d\n", __func__, CPUSET_REL_NAME(file),
		bitmask_weight(thissetcpubits)))
	firstbit = bitmask_first(thissetcpubits);
	lastbit = bitmask_last(thissetcpubits);
	if (firstbit == bitmask_nbits(thissetcpubits)) {
		DBPRT(("%s:  thissetcpubits mask is empty\n", __func__))
	} else for (cpunum = firstbit;
		cpunum <= lastbit;
		cpunum = bitmask_next(thissetcpubits, cpunum + 1)) {
		DBPRT(("%s:  set %s uses CPU %d\n", __func__,
			CPUSET_REL_NAME(file), cpunum))
		if (cpunum >= num_pcpus) {
			/*
			 *	One might consider it appropriate to
			 *
			 *		assert(cpunum < # of max CPU in use)
			 *
			 *	here, but mom operates on a static snapshot
			 *	of the available CPUs, so it's possible to
			 *	encounter a value outside the expected range.
			 *	If it happens, it likely means that mom should
			 *	be told to reinitialize, but that's not the
			 *	sort of thing to do in the middle of an ftw()
			 *	so we merely log the anomaly.
			 */
			sprintf(log_buffer,
				"out-of-range but in use CPU (%d) "
				"in CPU set %s", cpunum, file);
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE,
				LOG_ERR, __func__, log_buffer);
		}
	}
#endif	/* DEBUG */

	bitmask_or(cpubits, cpubits, thissetcpubits);
	DBPRT(("%s:  cpubits has weight %d\n", __func__, bitmask_weight(cpubits)))
	return (0);
}

/**
 * @brief
 *	This function is called by the ftw() in cpusets_initialize().
 *	It performs a one-deep search for CPU sets below PBS_CPUSETDIR and,
 *	for each one it finds, calls reassoc_job_with_cpus() to attempt to
 *	find the name of the job corresponding to that set;  if successful,
 *	reassoc_job_with_cpus() marks the CPUs in the set as in use by the
 *	job found.
 *
 * @param[in] file - filename
 * @param[in] sb - pointer to stat structure
 * @param[in] flag -
 *
 * @return      int
 * @retval      0       Success
 * @retval      1       Failure
 *
 */

int
reassociate_job_cpus(const char *file, const struct stat *sb, int flag)
{
	static struct cpuset	*cp = NULL;
	char		*p;
	int		nslashes;
	int		slashmax;
	char		log_buffer[LOG_BUF_SIZE];

	if (reassoc_bits == NULL)
		return (1);

	if (cp == NULL)
		if ((cp = cpuset_alloc()) == NULL) {
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
				LOG_ERR, __func__, "cpuset_alloc failed");
			return (1);
		}

	/* only interested in directory names ... */
	if (flag != FTW_D)
		return (0);
	/* skip all the PBS infrastructure directories themselves */
	if (is_pbs_container(file))
		return (0);

	/*
	 *	A depth one search of PBS_CPUSETDIR corresponds to the magic
	 *	number of exactly four '/'s (PBS_CPUSETDIR itself contains
	 *	three, and may be skipped).
	 *
	 *	Also, note that cpuset_query() does not work on absolute path
	 *	names, so it's necessary to strip off the initial prefix using
	 *	the CPUSET_REL_NAME() macro.
	 */
	slashmax = 5;
	for (p = (char *)file, nslashes = 0; p && *p && (nslashes < slashmax);
		p++)
		if (*p == '/')
			nslashes++;
	if (nslashes != (slashmax - 1)) {
		DBPRT(("%s:  file %s, nslashes %d\n", __func__, file, nslashes))
		return (0);
	}

	if (cpuset_query(cp, CPUSET_REL_NAME(file)) == -1) {
		sprintf(log_buffer, "cpuset_query %s (%s) failed",
			file, CPUSET_REL_NAME(file));
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
			LOG_ERR, __func__, log_buffer);
		return (0);
	}
	if (cpuset_getcpus(cp, reassoc_bits) == -1) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
			LOG_ERR, __func__, "cpuset_getcpus failed");
		return (0);
	}

	reassoc_job_with_cpus(CPUSET_REL_NAME(file), reassoc_bits);
	return (0);
}

/**
 * @brief
 *	Record as inuse a list of CPUs (represented as s bitmask) and associate
 *	them with a running job.  To find the job, we rely on the convention
 *	that a CPU set's name is the same as the concatenation of "/PBSPro/"
 *	and the job name.
 *
 *	If we fail to find a job with matching CPU set name, we can do no more
 *	than log an error and mark the CPU as out of service.
 *
 * @param[in] relname - cpuset rel name(filename)
 * @param[in] reassoc_bits - pointer to bitmask structure
 *
 * @return Void
 *
 */

static void
reassoc_job_with_cpus(const char *relname, struct bitmask *reassoc_bits)
{
	job		*pj;
	char		*jobset;
	unsigned int	cpunum;
	int		firstbit, lastbit;

	assert(reassoc_bits != NULL);

	DBPRT(("%s:  set %s has CPU weight %d\n", __func__, relname,
		bitmask_weight(reassoc_bits)))

	for (pj = (job *) GET_NEXT(svr_alljobs); pj != NULL;
		pj = (job *) GET_NEXT(pj->ji_alljobs)) {
		if (((jobset = getsetname(pj)) != NULL) &&
			(strcmp(jobset, relname) == 0)) {
			/*
			 *	Jobs that either aren't running or are currently
			 *	suspended shouldn't own any CPUs.
			 */
			if ((pj->ji_qs.ji_state != JOB_STATE_RUNNING) ||
				(pj->ji_qs.ji_substate == JOB_SUBSTATE_SUSPEND)) {
				sprintf(log_buffer,
					"CPU set %s:  job (state %d, substate %d)"
					" is suspended or not running",
					relname,
					pj->ji_qs.ji_state, pj->ji_qs.ji_substate);
				log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__,
					log_buffer);
				free(jobset);
				return;
			}
			firstbit = bitmask_first(reassoc_bits);
			lastbit = bitmask_last(reassoc_bits);
			if (firstbit == bitmask_nbits(reassoc_bits)) {
				DBPRT(("%s:  reassoc_bits mask is empty\n", __func__))
				free(jobset);
				return;
			}
			DBPRT(("%s:  reassoc_bits has weight %d\n", __func__,
				bitmask_weight(reassoc_bits)))
			for (cpunum = firstbit; cpunum <= lastbit;
				cpunum = bitmask_next(reassoc_bits, cpunum + 1)) {
				DBPRT(("%s:  set %s (job %s) uses CPU %d\n", __func__,
					relname, pj->ji_qs.ji_jobid, cpunum))
				cpunum_inuse(cpunum, pj);
			}
			free(jobset);
			return;
		}
		if (jobset != NULL)
			free(jobset);
	}

	/*
	 *	A CPU set exists for which we can find no running job.
	 *	If the set contains no CPUs, we remove it.  Otherwise,
	 *	we'll log the problem and take the CPUs out of service
	 *	so we don't overallocate them.
	 */
	firstbit = bitmask_first(reassoc_bits);
	lastbit = bitmask_last(reassoc_bits);
	if (firstbit == bitmask_nbits(reassoc_bits)) {
		char *slashp;

		sprintf(log_buffer,
			"CPU set %s has no matching job and no CPUs - removing",
			relname);
		log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, log_buffer);
		slashp = strrchr(relname, '/');	/* "/PBSPro/foo" -> "foo" */
		(void) try_remove_set(relname,
			(slashp != NULL) ? slashp + 1 : relname);
	} else {
		reassoc_err = 1;

		sprintf(log_buffer,
			"no job found with set name matching %s", relname);
		log_joberr(-1, __func__, log_buffer, (char *)relname);
		for (cpunum = firstbit; cpunum <= lastbit;
			cpunum = bitmask_next(reassoc_bits, cpunum + 1)) {
			DBPRT(("%s:  set %s (job %s) uses CPU %d\n", __func__,
				relname, pj->ji_qs.ji_jobid, cpunum))
			cpunum_outofservice(cpunum);
		}
	}
}

/**
 * @brief
 *	Make a list of the CPU sets in the hierarchy below PBS_CPUSETDIR so we
 *	can attempt to clean up on a restart of the mom by deleting any dangling
 *	CPU set directories that should have been removed when the tasks in them
 *	exited.
 *
 * @param[in] file - filename
 * @param[in] sb - pointer to stat structure
 * @param[in] flag - 
 *
 * @return	int
 * @retval 	0	Success
 *
 */
int
restart_cleanupprep(const char *file, const struct stat *sb, int flag)
{
	/* only interested in directory names ... */
	if (flag != FTW_D)
		return (0);
	/* ... that belong to us */
	if (strstr(file, PBS_CPUSETDIR) != file)
		return (0);

	restart_addset(file);
	return (0);
}

/**
 * @brief
 *	Add an element to the list (restart_setlist[]) of CPU sets to clean up.
 *
 * @param[in] file - filename
 *
 * @return Void
 *
 */
static void
restart_addset(const char *file)
{
	char	*p;
	char	**newlist;

	if ((p = strdup(file)) == NULL)
		return;

	newlist = realloc(restart_setlist,
		(restart_nsets + 1) * sizeof(char *));
	if (newlist != NULL) {
		restart_setlist = newlist;
		newlist[restart_nsets++] = p;
	} else
		free(p);
}

/**
 * @brief
 *	Some users may create one or more sub-CPU sets below the one that PBS
 *	automatically creates for them.  If they do that, PBS won't be able to
 *	remove the set it created.  To account for this, we perform a recursive
 *	depth-first search for children of the given CPU set, removing all that
 *	we find.
 *
 * @param [in]	set - cpu set name.
 * @param [in]  jid - job id
 *
 * @return  Void
 *
 */
void
prune_subsetsof(const char *set, const char *jid)
{
	DIR		*dp;
	struct dirent	*dep;
	struct stat	sb;
	static int	depth = 0;
	static char	*namebuf = NULL;
	static long	namelen;
	size_t		len;
	char		*namebufend;

	if (namebuf == NULL) {
		/*
		 *	Strictly speaking, this value can vary for each
		 *	directory we encounter.  We make the simplifying
		 *	assumption that one value works everywhere - at
		 *	least everywhere within the cpuset file system.
		 */
		if ((namelen = pathconf(DEV_CPUSET, _PC_NAME_MAX)) == -1) {
			log_err(errno, __func__, "pathconf");
			return;
		}
		if ((namebuf = malloc(namelen)) == NULL) {
			log_err(errno, __func__, "malloc namebuf");
			return;
		}
	}

	if (depth == 0) {
		assert((set != NULL) && (*set == '/'));
		(void)strncpy(namebuf, DEV_CPUSET, namelen - 1);
		(void)strncat(namebuf, set, namelen - sizeof(DEV_CPUSET));
		if ((lstat(namebuf, &sb) == -1) || !S_ISDIR(sb.st_mode))
			return;
	}
	len = strlen(namebuf);
	namebufend = namebuf + len;
	if ((dp = opendir(namebuf)) != NULL) {
		while (errno = 0, (dep = readdir(dp)) != NULL) {
			if (!strcmp(dep->d_name, ".") ||
				!strcmp(dep->d_name, ".."))
				continue;
			(void)strncat(namebuf, "/", namelen - len - 1);
			(void)strncat(namebuf, dep->d_name, namelen - len - 2);
			if ((lstat(namebuf, &sb) == -1) ||
				!S_ISDIR(sb.st_mode)) {
				*namebufend = '\0';
				continue;
			}
			depth++;
			prune_subsetsof(namebuf, jid);
			depth--;
			remove_subset(namebuf, jid);
			*namebufend = '\0';
		}
		if (errno != 0 && errno != ENOENT)
			log_err(errno, __func__, "readdir failed");
		closedir(dp);
	}
}

/**
 * @brief
 *	removes sub cpu set.
 * 
 * @param[in] dir - cpu directory
 * @param[in] jid - job id
 *
 * @return Void
 *
 */

static void
remove_subset(const char *dir, const char *jid)
{
	char		buf[LOG_BUF_SIZE];

	if (try_remove_set(CPUSET_REL_NAME(dir), jid) == -1) {
		sprintf(buf, "cpuset_delete %s failed", CPUSET_REL_NAME(dir));
		log_joberr(errno, __func__, buf, (char *)jid);

		if (rmdir(dir) == -1) {
			sprintf(buf, "rmdir %s failed", dir);
			log_joberr(errno, __func__, buf, (char *)jid);
			return;
		}
	}

	sprintf(log_buffer, "removed sub-CPU set %s", CPUSET_REL_NAME(dir));
	log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
		log_buffer);
}

/**
 * @brief
 *	ProPack 4 removed libcpumemsets interfaces, including numnodes().
 *	If forced, we guess that there are two CPUs per node.
 *	The idea for this function is courtesy of pj@sgi.com.
 *
 *	In the future, this number may no longer make much sense
 *	since the number of CPUs per node may vary.
 *
 * @return 	int
 * @retval	nmems	Success
 * @retval 	2	Failure
 *
 */

int
numnodes(void)
{
	int		nmems;
	struct cpuset	*cp;

	if (((cp = cpuset_alloc()) == NULL) ||
		(cpuset_query(cp, DEV_CPUSET_ROOT) == -1))
		return (2);   /* we're screwed - wing it */

	nmems = cpuset_mems_weight(cp);
	cpuset_free(cp);

	return (nmems);
}

/**
 * @brief
 *	checks Is path an absolute (starts with "/dev/cpuset/") or
 *	relative (starts with "/PBSPro/") name?
 *
 * @param[in] path - path 
 *
 * @return 	int
 * @retval 	1	Failure
 * @retval 	0	Success
 *
 */

int
is_pbs_container(const char *path)
{
	/*
	 *	Is path an absolute (starts with "/dev/cpuset/") or
	 *	relative (starts with "/PBSPro/") name?
	 */
	if (strstr(path, PBS_CPUSETDIR) == path)
		if (strcmp(path, PBS_CPUSETDIR) == 0)
			return (1);
	else
		return (0);
	else
		if (strcmp(path, CPUSET_REL_NAME(PBS_CPUSETDIR)) == 0)
			return (1);
	else
		return (0);

}

/**
 * @brief
 *	deletes cpu set for job
 * 
 * @param[in] set - cpu set
 * @param[in] jid - job id
 *
 * @return 	int
 * @retval 	-1	Failure
 * @retval 	0	Success
 *
 */

int
try_remove_set(const char *set, const char *jid)
{
	static struct cpuset	*cp = NULL;
	int			save_errno;

	if ((cp == NULL) && (cp = cpuset_alloc()) == NULL) {
		save_errno = errno;
		log_joberr(save_errno, __func__, log_buffer, (char *)jid);
		return (-1);
	}

	if (cpuset_query(cp, set) == -1) {
		save_errno = errno;
		sprintf(log_buffer, "cpuset_query %s failed", set);
		log_joberr(save_errno, __func__, log_buffer, (char *)jid);
		return (-1);
	}

	cpuset_set_iopt(cp, "notify_on_release", 1);
	cpuset_set_iopt(cp, "cpu_exclusive", 0);
	cpuset_set_iopt(cp, "mem_exclusive", 0);
	if (cpuset_modify(set, cp) == -1) {
		save_errno = errno;
		sprintf(log_buffer, "cpuset_modify %s failed", set);
		log_joberr(save_errno, __func__, log_buffer, (char *)jid);
	}

	/*
	 *	At this point we've done all we can to allow us to
	 *	indicate to our caller that the set will eventually be
	 *	removed, but it's still not safe to claim success since
	 *	there are apparently some latent processes that we can't
	 *	eradicate.  Some resources will remain assigned to the
	 *	named (by jid) job.
	 */
	if ((cpuset_delete(set) == -1) && (errno != ENOENT)) {

		save_errno = errno;
		sprintf(log_buffer, "cpuset_delete cpuset %s failed", set);
		log_joberr(save_errno, __func__, log_buffer, (char *)jid);

		if (!cpuset_pidlist_broken()) {
			struct cpuset_pidlist	*pl;
			int			pll;
			int			i;
			int			isrecursive = 1;

			pl = cpuset_init_pidlist(set, isrecursive);
			pll = cpuset_pidlist_length(pl);
			for (i = 0; i < pll; i++) {
				int	pid = cpuset_get_pidlist(pl, i);

				if (pid == -1) {
					save_errno = errno;
					sprintf(log_buffer,
						"cpuset_get_pidlist index %d "
						"returned -1", i);
					log_joberr(save_errno, __func__, log_buffer,
						(char *)jid);
				} else
					logprocinfo(pid, save_errno, jid);
			}
			cpuset_freepidlist(pl);
			sprintf(log_buffer, "%d tasks in set %s", pll, set);
			log_joberr(save_errno, __func__, log_buffer, (char *)jid);
		}
		return (-1);
	} else {
		/*
		 *	Either the cpuset_delete() failed with errno ENOENT
		 *	(in which case the setting of notify_on_release above
		 *	must have already caused it to be removed), or it did
		 *	not fail.  In either case, it's safe to report that
		 *	the set is now gone.
		 */
		sprintf(log_buffer, "delete cpuset %s", set);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			(char *)jid, log_buffer);
	}

	return (0);
}
#endif	/* MOM_CPUSET && CPUSET_VERSION >= 4 */

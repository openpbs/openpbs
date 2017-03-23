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

 /**
  * @file	cpusets.c
  * @brief
  * Library functions to simplify access to cpusets.
  */

#include <pbs_config.h>

/*
 * Declare that this code is to use the NAS-local IRIX kernel modifications
 * to set memory over-use limits on cpusets.
 */

#include <sys/types.h>
#include <sys/sysmp.h>
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <dirent.h>
#include "bitfield.h"
#include "cpusets.h"
#include "mapnodes.h"
#include "log.h"

extern char	*path_jobs;
extern pbs_list_head svr_alljobs;

extern char	*bitfield2hex(Bitfield *);
extern char	*bitfield2bin(Bitfield *);

int cpuset_create_flags = CPUSET_CPU_EXCLUSIVE
	| CPUSET_MEMORY_LOCAL
| CPUSET_MEMORY_MANDATORY
| CPUSET_MEMORY_EXCLUSIVE
| CPUSET_POLICY_KILL
| CPUSET_EVENT_NOTIFY
;

int cpuset_destroy_delay = 5; /* secs to wait before destroying a cpuset */

int cpuset_small_ncpus = -1;   /* defines the max # of  cpus that a small job */
/* can request, and this job is assigned a */
/* shared cpuset */
int cpuset_small_mem = -1;    /* defines the max amt of mem (kb) that a */
/* small job can request, and this job is */
/* assigned a shared cpuset */

/**
 * @brief
 * 	cpuset_small_ncpus_set: the number obtained must be at least  1 cpu
 * 	less than the maximum # of cpus per nodeboard in the system.
 *
 * @param[in] str - string holding value for ncpus
 *
 * @return	unsigned long
 * @retval	1		success
 * @retval	0		error
 *
 */
unsigned long
cpuset_small_ncpus_set(char *str)
{
	char	*left;
	unsigned long   ul;


	if (str == NULL)
		return (0);

	ul = strtoul(str, &left, 0);
	if (*left != '\0') {
		sprintf(log_buffer,
			"cannot parse %s as # of cpus for cpuset_small_ncpus - default value will be set",
			str);
		log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
		return (0);
	}


	cpuset_small_ncpus = (int)ul;

	return (1);
}

/**
 * @brief 
 *	cpuset_small_mem_set: the number in the config file is in terms of
 * 	kbytes, while internally, it will be represented in bytes.
 *
 * @param[in] str - string holding value for memset
 *
 * @return      unsigned long
 * @retval      1               success
 * @retval      0               error
 *
 */

unsigned long
cpuset_small_mem_set(char *str)
{
	char	*left;
	unsigned long   ul;

	if (str == NULL)
		return (0);

	ul = strtoul(str, &left, 0);
	if (*left != '\0' && strcasecmp(left, "kb") != 0) {
		sprintf(log_buffer,
			"cannot parse %s as kbytes for cpuset_small_mem - default value will be set",
			str);
		log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
		return (0);
	}

	cpuset_small_mem = (int)ul;

	return (1);
}

/**
 * @brief
 *	 sets time val(secs) to wait before destroying a cpuset.
 *
 * @param[in] str - configuration value
 *
 * @return	long
 * @retval	secs to wait 	success
 * @retval	0		error
 *
 */
unsigned long
cpuset_destroy_delay_set(char *str)
{
	char	*left;
	unsigned long   ul;

	if (str == NULL)
		return (0);

	ul = strtoul(str, &left, 0);
	if (*left != '\0' && strcasecmp(left, "s") != 0) {
		sprintf(log_buffer,
			"cannot parse %s as # of secs for cpuset_destroy_delay",
			str);
		log_event(PBSEVENT_SYSTEM, 0, LOG_DEBUG, __func__, log_buffer);
		return (0);
	}
	cpuset_destroy_delay = (int)ul;

	return (1);
}

/**
 * @brief
 * 	creates the flags for 'str' is in the format: "flag1|flag2|..." 
 *
 * @param[in] str - config value
 *
 * @return	long
 * @retval	1	success
 * @retval	0	failure
 *
 */
unsigned long
cpuset_create_flags_map(char *str)
{
	char *val;


	if (str == NULL)
		return (0);

	val = strtok(str, "|");

	cpuset_create_flags = 0;
	while (val) {
		if (strcasecmp(val, "CPUSET_CPU_EXCLUSIVE") == 0)
			cpuset_create_flags |= CPUSET_CPU_EXCLUSIVE;
		else if (strcasecmp(val, "CPUSET_MEMORY_LOCAL") == 0)
			cpuset_create_flags |= CPUSET_MEMORY_LOCAL;
		else if (strcasecmp(val, "CPUSET_MEMORY_EXCLUSIVE") == 0)
			cpuset_create_flags |= CPUSET_MEMORY_EXCLUSIVE;
		else if (strcasecmp(val, "CPUSET_MEMORY_KERNEL_AVOID") == 0)
			cpuset_create_flags |= CPUSET_MEMORY_KERNEL_AVOID;
		else if (strcasecmp(val, "CPUSET_MEMORY_MANDATORY") == 0)
			cpuset_create_flags |= CPUSET_MEMORY_MANDATORY;
		else if (strcasecmp(val, "CPUSET_POLICY_PAGE") == 0)
			cpuset_create_flags |= CPUSET_POLICY_PAGE;
		else if (strcasecmp(val, "CPUSET_POLICY_KILL") == 0)
			cpuset_create_flags |= CPUSET_POLICY_KILL;
		else if (strcasecmp(val, "CPUSET_EVENT_NOTIFY") == 0)
			cpuset_create_flags |= CPUSET_EVENT_NOTIFY;
		else if (strcasecmp(val, "CPUSET_KERN") == 0)
			cpuset_create_flags |= CPUSET_KERN;

		val = strtok(NULL, "|");
	}
	return (1);

}

/**
 * @brief
 *	creates flags in some format.
 *
 * @param[in] head - format
 * @param[in] flags - flag val
 *
 * @return	Void
 *
 */
void
cpuset_create_flags_print(char *head, int flags)
{
	strcpy(log_buffer, head);
	if (flags & CPUSET_CPU_EXCLUSIVE)
		strcat(log_buffer, "|CPUSET_CPU_EXCLUSIVE");

	if (flags & CPUSET_MEMORY_LOCAL)
		strcat(log_buffer, "|CPUSET_MEMORY_LOCAL");

	if (flags & CPUSET_MEMORY_EXCLUSIVE)
		strcat(log_buffer, "|CPUSET_MEMORY_EXCLUSIVE");

	if (flags & CPUSET_MEMORY_KERNEL_AVOID)
		strcat(log_buffer, "|CPUSET_MEMORY_KERNEL_AVOID");

	if (flags & CPUSET_MEMORY_MANDATORY)
		strcat(log_buffer, "|CPUSET_MEMORY_MANDATORY");

	if (flags & CPUSET_POLICY_PAGE)
		strcat(log_buffer, "|CPUSET_POLICY_PAGE");

	if (flags & CPUSET_POLICY_KILL)
		strcat(log_buffer, "|CPUSET_POLICY_KILL");

	if (flags & CPUSET_EVENT_NOTIFY)
		strcat(log_buffer, "|CPUSET_EVENT_NOTIFY");

	if (flags & CPUSET_KERN)
		strcat(log_buffer, "|CPUSET_KERN");

	log_err(-1, "cpuset_create_flags_print", log_buffer);
}

/* ============= Routines to create, destroy and query cpusets ============= */

/**
 * @brief
 * 	query_cpusets()
 * 	Ask for a list of cpusets currently running on the system.  If a pointer
 * 	to a Bitfield was given, fill in the nodes in the bitfield with the union
 * 	of the nodes used in the current cpusets.  The input bitfield is not
 * 	cleared.
 *
 * @param[in] listp - pointer to cpusets
 * @param[in] maskp - pointer to bit mask
 *
 * @par Note:
 *	Cpusets are added to the tail of the list pointed to by listp if non-NULL,
 * 	and the total number of cpusets found is returned.
 *
 * @return	int
 * @retval	-1			error(with errno left as set by sysmp())
 * @retval	count of cpuset		
 */
int
query_cpusets(cpusetlist **listp, Bitfield *maskp)
{
	cpuset_NameList_t *names;
	char		qname[QNAME_STRING_LEN + 1];
	int			i, ret, count = 0;
	Bitfield		nodes;

	if (sysmp(MP_NPROCS) < 1) {
		log_err(errno, __func__, "sysmp(MP_NPROCS");
		return -1;			/* "This can't happen." */
	}

	/* Get the list of names else print error & exit */
	if ((names = cpusetGetNameList()) == NULL) {
		log_err(errno, __func__, "cpusetGetNameList");
		return (-1);
	}

	for (i = 0; i < names->count; i++) {

		if (names->status[i] != CPUSET_QUEUE_NAME)
			continue;

		if (listp) {	/* Add to supplied list? */

			(void)strncpy(qname, names->list[i], QNAME_STRING_LEN);
			qname[QNAME_STRING_LEN] = '\0';

			/* Query the kernel for the nodes for this cpuset. */
			if (cpuset2bitfield(qname, &nodes))
				continue;

			ret = add_to_cpusetlist(listp, qname, &nodes, NULL);

			if (ret < 0)	/* Cpuset not found -- race condition? */
				continue;

			if (ret > 0)	/* Error in list manipulation - give up. */
				break;

			/* Add the nodes for this cpuset into the specified bitmask. */
			if (maskp)
				BITFIELD_SETM(maskp, &nodes);
		}

		count ++;
	}

	return count;
}

/**
 * @brief
 * 	create_cpuset()
 * 	Create a new cpuset, populating the cpu list from the provided mask.
 * 	Cpuset is owned by the uid/gid supplied, exclusive.
 *
 * @param[in] qname - cpuset name
 * @param[in] maskp - pointer to mask bitfield
 * @param[in] path - path for permission filename
 * @param[in] uid - user id
 * @param[in] gid - group id
 *
 * @return	int
 * @retval	0	success
 * @retval	1	error
 *
 */
int
create_cpuset(char *qname, Bitfield *maskp, char *path, uid_t uid, gid_t gid)
{
	int			fd = -1, rc = 0;
	cpuset_QueueDef_t   *qdef;

	/*
	 * Unlink the controlling file, if it already exists.  This prevents two
	 * cpusets from sharing a controlling file descriptor (even if they are
	 * given the same name).
	 */
	(void)unlink(path);

	/* Create the controlling file from "path", perms only for the owner. */
	if ((fd = open(path, O_RDWR | O_CREAT | O_EXCL, 0744)) < 0) {
		(void)sprintf(log_buffer, "could not create %s", path);
		log_err(errno, __func__, log_buffer);
		return -1;
	}

	/* Alloc queue def for 3 CPU IDs */
	qdef = cpusetAllocQueueDef(cpusetGetCPUCount());
	if (!qdef) {
		(void)sprintf(log_buffer, "could not allocate cpuset queue definition");
		log_err(errno, __func__, log_buffer);
		return -1;
	}

	/*
	 * At this point, a file exists in the filesystem.  Be sure to delete it
	 * before returning if an error occurs.
	 */

	/*
	 * The "permissions" on the CPU set will mimic those on the file
	 * referenced by the file descriptor.  Make the controlling file
	 * owned by the user and group.
	 */
	if (chown(path, uid, gid)) {
		(void)sprintf(log_buffer, "could not chown(%s, %d.%d)", path,
			(int)uid, (int)gid);
		log_err(errno, __func__, log_buffer);
		rc = 1;
		goto cleanup;		/* Delete the file and return error. */
	}
	if (chmod(path, MOM_CPUSET_PERMS)) {
		(void)sprintf(log_buffer,
			"could not chmod(%s, %d)", path, MOM_CPUSET_PERMS);
		log_err(errno, __func__, log_buffer);
		rc = 1;
		goto cleanup;		/* Delete the file and return error. */
	}

	if (bitfield2cpuset(maskp, qdef->cpu)) {
		(void)sprintf(log_buffer, "could not convert mask to cpuset %s", qname);
		log_err(errno, __func__, log_buffer);
		rc = 1;
		goto cleanup;		/* Delete the file and return error. */
	}

	/* Define attributes of the cpuset */

	/* Per SGI, can't have the MEMORY_MANDATORY flag if you want to checkpoint */
	/* jobs and have them restart in another cpuset with the same # nodes */
	/* but not necessarily on the same set of cpus. */
	qdef->flags = cpuset_create_flags;

	qdef->permfile = path;

	/* Now close the perm file to ensure it gets created (not deferred) */
	(void)close(fd);
	fd = -1;

	/* Request that the cpuset be created */
	if (!cpusetCreate(qname, qdef)) {
		(void)sprintf(log_buffer, "failed to create cpuset %s", qname);
		log_err(errno, __func__, log_buffer);
		rc = 1;
		goto cleanup;		/* Delete the file and return error. */
	}

	/*
	 * Close our reference to the controlling file, and unlink it from
	 * the filesystem.  This section may be entered upon error, too.
	 */

cleanup:
	if (fd > 0)
		(void)close(fd);

	if (rc == 0) {	/* cpuset creation was successful */
		if (chown(path, 0, 0)) {
			(void)sprintf(log_buffer, "could not chown(%s, %d.%d)", path,
				0, 0);
			log_err(errno, __func__, log_buffer);
		}
	} else {
		(void)unlink(path);
	}
	cpusetFreeQueueDef(qdef);

	return rc;
}

/**
 * @brief
 * 	destroy_cpuset()
 * 	Attempt to destroy the cpuset named by 'qname'.  If
 * 	the cpuset cannot be destroyed because one or more processes are still
 * 	running within it, send a SIGKILL to each of the
 * 	processes(*) within the cpuset.  Wait half a second and retry the destroy
 * 	operation.
 *
 * @param[in] qname - cpuset name
 *
 * @return	int
 * @retval	1	if not destroyed
 * @retval	0	destroyed
 *
 */
int
destroy_cpuset(char *qname)
{
	int			tries;
	cpuset_PIDList_t 	*pids;
	int			i;
	int			proc_killed = 0;
	char                path[MAXPATHLEN];

	for (tries = 0; tries < 25; tries ++) {

		/* Destroy, if error - print error & exit */
		if (cpusetDestroy(qname)) {
			cpuset_permfile(qname, path);
			unlink(path);
			return 0;   /* Successfully deleted. */
		}

		/* Cpuset was not successfully deleted because it no longer exists. */
		if (errno == ESRCH)
			return 0;

		/*
		 * Did a system error occur?  If so, return an error.  If it's still
		 * busy, go on to sleep a bit and try again.
		 */
		if (errno != EBUSY)
			continue;	/* don't give up so easily */

		/*
		 * If couldn't be deleted because some process has a handle on it,
		 * send the process(es) a SIGKILL and try again.
		 */

		/* Get the list of PIDs else print error & exit */
		if ((pids = cpusetGetPIDList(qname)) != NULL) {

			/* Send a SIGKILL to each PID in the cpuset.  Ignore results. */
			proc_killed = 0;
			for (i = 0; i < pids->count; i++) {
				(void)kill(pids->list[i], SIGKILL);
				proc_killed++;
			}

			cpusetFreePIDList(pids);
		}

		if (proc_killed == 0)
			break;	/* no process killed so assume a zombied cpuset */

		/*
		 * Wait a bit for things to exit.  DO NOT make this a long time
		 * period -- the mom will block for this period of time.
		 *
		 * This code wants threading.
		 */
		usleep(200000);		/* Wait for a fifth of a second.  Ick. */
	}

	/* Couldn't delete cpuset.  Return non-success. */
	return 1;
}

/**
 * @brief
 * 	attach_cpuset()
 * 	Attach the current process to the cpuset named by 'qname'.  Note that there
 *	is no kernel interface to remove a specific process from the cpuset.
 *
 * @param[in] qname - cpuset name
 *
 * @return	int
 * @retval	0	success	(current process now constrained to cpuset 'qname')
 * @retval	-1	error	(with errno set by the kernel interface).
 *
 */
int
attach_cpuset(char *qname)
{
	if (!cpusetAttach(qname)) {
		(void)sprintf(log_buffer, "failed to attach to cpuset %s", qname);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_NOTICE,
			__func__, log_buffer);
		return -1;
	}


	/* Okay.  Current process is now running in the cpuset. */
	return 0;
}

/**
 * @brief
 * 	current_cpuset()
 * 	Return a pointer to a static string containing the qname of the cpuset
 * 	to which the current process belongs, or a NULL pointer if not in a cpuset.
 *
 * @par	Note:
 * 	that the string is static, and will be overwritten by subsequent
 * 	invocations.
 *
 * @return	string
 * @retval	qname of cpuset		success
 * @retval	NULL			error
 *
 */
char *
current_cpuset(void)
{
	cpuset_NameList_t	*names;
	static char		qname[QNAME_STRING_LEN + 1];


	/* Get the list of names else print error & exit */
	if ((names = cpusetGetName(0)) == NULL) {
		log_err(errno, __func__, "Failed to get current cpuset name");
		return (NULL);
	}

	if (names->count == 0) {
		log_err(-1, __func__, "Current process not attched");
		cpusetFreeNameList(names);
		qname[QNAME_STRING_LEN] = '\0';
		return (qname);
	}

	if (names->status[0] != CPUSET_QUEUE_NAME) {
		log_err(-1, __func__, "Obtained CPU ID for CPUSET queue name");
		cpusetFreeNameList(names);
		qname[QNAME_STRING_LEN] = '\0';
		return (qname);
	}

	/* Copy the queue name from the response and return a pointer to it. */
	strncpy(qname, names->list[0], QNAME_STRING_LEN);
	qname[QNAME_STRING_LEN] = '\0';

	cpusetFreeNameList(names);
	return qname;
}

/**
 * @brief
 * 	teardown_cpuset()
 * 	Main interface used by mom to revoke cpusets from jobs.
 *
 * @par	Functionality:
 *	Attempt to tear down the cpuset assigned to this job.  If unable to do
 *	so immediately, place the cpuset on the queue of "stuck" cpusets.  This
 * 	list is periodically traversed, and any cpusets that have become
 * 	"unstuck" are freed and returned to the global pool.
 *
 * @par Note:
 * 	A cpuset can become "stuck" if all of the processes in the cpuset are
 * 	not killed before attempting to delete the cpuset.  This is usually a
 * 	symptom of user code attempting to dump core to an NFS filesystem on a
 * 	fileserver that is temporarily unreachable (i.e. crashed).
 *
 * @param[in] qname - cpuset name
 * @param[in] nodesp - pointer to nodes bitfield
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	if the cpuset cannot be deleted
 *
 */
int
teardown_cpuset(char *qname, Bitfield *nodesp)
{
	/*
	 * Attempt to destroy the cpuset named in *cpuset.  If it succeeds, that
	 * is all that needs to be done.  Return the nodes to the nodepool.
	 */
	if (destroy_cpuset(qname) == 0) {
		(void)sprintf(log_buffer, "destroyed cpuset %s", qname);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_JOB, LOG_DEBUG, __func__, log_buffer);

		BITFIELD_SETM(&nodepool, nodesp);

#ifdef	DEBUG
		(void)sprintf(log_buffer, "nodepool now %s", bitfield2hex(&nodepool));
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_JOB, LOG_DEBUG, __func__, log_buffer);
#endif	/* DEBUG */

		return 0;
	}

	/*
	 * The cpuset was not destroyed.  If it was a real system error, log
	 * it.  If it didn't exist, well then consider it torn down.  If it's
	 * busy, put it on the list of cpusets to attempt to reclaim later.
	 */
	if (errno == ESRCH || errno == ENOENT) {
		(void)sprintf(log_buffer, "can't delete nonexistent cpuset '%s'", qname);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_JOB, LOG_INFO, __func__, log_buffer);
		return 1;
	}
	if (errno != EBUSY) {
		(void)sprintf(log_buffer, "failed to destroy cpuset '%s'", qname);
		log_err(errno, __func__, log_buffer);
	}

	/*
	 * The cpuset is "busy".  At some point in the future it should become
	 * empty and be revocable.  Arrange to occasionally check it and clean
	 * it up if possible.
	 */

	if (add_to_cpusetlist(&stuckcpusets, qname, nodesp, NULL)) {
		(void)sprintf(log_buffer, "failed to add cpuset %s to stuck list",
			qname);
		log_err(errno, __func__, log_buffer);
		return 1;
	}

	/* Note that the nodes are stuck and unavailable. */
	BITFIELD_SETM(&stucknodes, nodesp);
	mom_update_resources();

	(void)sprintf(log_buffer,
		"can't destroy cpuset '%s' - retry later", qname);
	log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_JOB, LOG_INFO, __func__, log_buffer);

	return -1;		/* Cpuset cannot be deleted at this time. */
}

/** 
 * @brief
 * 	reclaim_cpusets()
 * 	Given a list of cpusets, attempt to destroy each cpuset named by the list.
 * 	If it can be destroyed, unset the bits corresponding to the cpuset's nodes
 * 	in the mask (if supplied).  This is used to reclaim cpusets that were
 * 	supposed to be deleted, but were in fact "stuck", and placed on stucklist.
 *
 * @param[in] listp - pointer to cpuset list
 * @param[in] maskp - pointer to mask bitfield
 *
 * @return	int
 * @retval	num of cpuset reclaimed		success
 * @retval	0				error
 *
 */
int
reclaim_cpusets(cpusetlist **listp, Bitfield *maskp)
{
	cpusetlist		*set, *next;
	int			count = 0;

	/*
	 * Walk the list of stuck cpusets, attempting to free each one.  Keep
	 * track of the previous and next pointers so the element can be
	 * unlinked and freed.
	 */
	for (set = *listp; set != NULL; set = next) {
		next = set->next;	/* Keep track of next pointer. */

		/* See if this cpuset can be deleted now.  If not, go on. */
		if (destroy_cpuset(set->name)) {
			log_err(0, __func__, "could not destroy cpuset");
			continue;
		}

		/*
		 * Remove the corresponding bits from the given bitmask, if supplied,
		 * and return the nodes to the nodepool.
		 */
		if (maskp != NULL)
			BITFIELD_CLRM(maskp, &(set->nodes));
		BITFIELD_SETM(&nodepool, &(set->nodes));

		/* Log that the cpuset was reclaimed. */
		(void)sprintf(log_buffer, "stuck cpuset %s reclaimed", set->name);
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_INFO, __func__, log_buffer);

#ifdef	DEBUG
		(void)sprintf(log_buffer, "nodepool now %s", bitfield2hex(&nodepool));
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_JOB, LOG_INFO, __func__, log_buffer);
#endif	/* DEBUG */

		/* Now free the storage for the cpusetlist element. */
		if (remove_from_cpusetlist(listp, NULL, set->name, NULL))
			break;

		count ++;		/* Another cpuset reclaimed. */
	}

	/*
	 * Perform a quick sanity check.  If there are no cpusets on the supplied
	 * list, then there should be no bits set in the supplied bitfield.  Log
	 * an error message if this is not the case.
	 */
	if (maskp != NULL && *listp == NULL && !BITFIELD_IS_ZERO(maskp))
		log_err(-1, __func__, "NULL cpusetlist but mask not empty!");

	return (count);
}


/* ================== Routines to handle lists of cpusets ================== */
/**
 * @brief
 * 	add_to_cpusetlist()
 * 	Add a cpuset to a list of cpusets.  Collect the nodes in the cpuset itself
 * 	(by querying the kernel) into the mask pointed to by maskp.  If the cpuset
 * 	does not exist, return -1.  On error, return 1.  Otherwise, return 0.
 *
 * @par	Note:
 * 	if share_req is not NULL, then we're trying to add a shared cpuset. This will
 * 	first try to find a shared cpuset from listp that will match the share_req
 * 	requirements given. If it finds one, then update its sharing information;
 * 	otherwise, * a new shared cpuset entry is created.
 * 
 * @param[in] listp - pointer to cpuset list
 * @param[in] qname - cpuset name to be added to list
 * @param[in] nodes - pointer to nodes bitfield
 * @param[in] share_req - pointer to shared_cpuset
 *
 * @return	int
 * @retval	0	success
 * @retval	1	failure
 *
 */
int
add_to_cpusetlist(cpusetlist **listp, char *qname, Bitfield *nodes, cpuset_shared *share_req)
{
	cpusetlist	*new, *ptr;
	cpusetlist	*candidate = NULL;

	if ((qname == NULL)  || (qname[0] == '\0')) {
		log_err(-1, __func__, "bad cpuset name (set to NULL or 0 length)");
		return 1;
	}

	if ((listp == NULL)  || (nodes == NULL)) {
		log_err(-1, __func__, "invalid input");
		return 1;
	}

	if (cpuset_shared_is_set(share_req)) {

		candidate = find_cpuset(*listp, qname);

		if (candidate) {

			if (!candidate->sharing) {
				sprintf(log_buffer,
					"found duplicate exclusive cpuset %s", qname);
				log_err(-1, __func__, log_buffer);
				return 1;
			}
			cpuset_shared_set_free_cpus(candidate->sharing,
				cpuset_shared_get_free_cpus(candidate->sharing) -
				share_req->free_cpus);
			cpuset_shared_set_free_mem(candidate->sharing,
				cpuset_shared_get_free_mem(candidate->sharing) -
				share_req->free_mem);

			/* time_to_live attribute of candidate automatically set
			 when *_add_job function is called */
			cpuset_shared_add_job(candidate->sharing,
				(char *)share_req->owner, share_req->time_to_live);

			/* NOTE: no need to updates nodes assigned info for that
			 remains unchanged in a shared cpuset */
			return 0;	/* successfully added the job */
		}

	}

	/* Create a new entry to be added to the tail of the list *listp. */
	if ((new = (cpusetlist *)malloc(sizeof(cpusetlist))) == NULL) {
		log_err(errno, __func__, "malloc(cpusetlist)");
		return 1;
	}
	new->next = NULL;

	/*
	 * Copy the node information and the "canonical" queue name into the
	 * newly-allocated struct.  Be sure the queue name is NULL-terminated,
	 * and the next pointer is unset.
	 */
	BITFIELD_CPY(&new->nodes, nodes);	/* Nodes in this cpuset. */
	(void)strncpy(new->name, qname, QNAME_STRING_LEN);
	new->name[QNAME_STRING_LEN] = '\0';

	if (cpuset_shared_is_set(share_req)) {
		new->sharing = (cpuset_shared *)cpuset_shared_create();

		if (new->sharing == NULL) {
			log_err(errno, __func__, "malloc(cpusetlist)");
			return 1;

		}

		cpuset_shared_set_free_cpus(new->sharing,
			nodemask_num_cpus(nodes) - share_req->free_cpus);

		cpuset_shared_set_free_mem(new->sharing,
			nodemask_tot_mem(nodes) - share_req->free_mem);
		sprintf(log_buffer, "set free_mem to %d (ttotmem=%d)",
			cpuset_shared_get_free_mem(new->sharing),
			nodemask_tot_mem(nodes));

		/* *_add_job updates time_to_live attribute of new */
		cpuset_shared_add_job(new->sharing, (char *)share_req->owner,
			share_req->time_to_live);
		cpuset_shared_set_owner(new->sharing, (char *)share_req->owner);
	} else {
		new->sharing = NULL;
	}

	/* Place the new element at the tail of the list. */
	if (*listp != NULL) {
		for (ptr = *listp; ptr->next != NULL; ptr = ptr->next)
			/* Walk down the list, looking for the last element. */ ;

		ptr->next = new;	/* Hang the new element off the last element. */
	} else {
		*listp = new;		/* List was empty -- seed it with 'new'. */
	}

	/* Successfully queried the cpuset and added its information to the list. */
	return 0;
}

/**
 * @brief
 * 	remove_from_cpusetlist()
 * 	exclusive cpuset: search for and remove a cpusetlist element from the
 * 		      supplied list.
 * 	shared cpuset: if share_req is set, then the cpuset being removed is
 *		  a shared cpuset. Remove only if 1 job left assigned to it.
 *		  otherwise, update its cpuset shared info.
 *
 * @par	Functionality:
 * 	If maskp is non-NULL, copy the element's nodes into *maskp.  Then, unlink
 * 	the element from the list and free() it.
 *
 * @param[in] listp - pointer to cpuset list
 * @param[in] qname - cpuset name to be added to list
 * @param[in] nodes - pointer to nodes bitfield
 * @param[in] share_req - pointer to shared_cpuset
 *
 * @return      int
 * @retval      0       success
 * @retval      1       failure( requested cpuset was not found)
 *
 * @par	NOTE: 
 *	This function does *not* destroy the cpuset, merely the element in
 * 	the list that tracks it.
 *
 */
int
remove_from_cpusetlist(cpusetlist **listp, Bitfield *maskp, char *qname, cpuset_shared *share_req)
{
	cpusetlist		*prev, *ptr;
	char		canon[QNAME_STRING_LEN + 1];

	/* Shortcut -- bail out if list is NULL. */
	if (*listp == NULL)
		return 1;

	/* "Canonicalize" the supplied queue name. */
	strncpy(canon, qname, QNAME_STRING_LEN);
	canon[QNAME_STRING_LEN] = '\0';

	/*
	 * Search the supplied list for the canonicalized cpuset name.  Keep track
	 * of the previous pointer, so that the list can be fixed up.
	 */
	prev = NULL;

	for (ptr = *listp; ptr != NULL; prev = ptr, ptr = ptr->next)
		if (strcmp(canon, ptr->name) == 0)	/* Found it? */
			break;

	if (ptr == NULL)	/* Requested cpuset was not found in the list. */
		return 1;

	/* a sharing cpuset */
	if (ptr->sharing) {
		cpuset_shared_set_free_cpus(ptr->sharing,
			cpuset_shared_get_free_cpus(ptr->sharing) +
			share_req->free_cpus);
		cpuset_shared_set_free_mem(ptr->sharing,
			cpuset_shared_get_free_mem(ptr->sharing) +
			share_req->free_mem);
		/* *_remove_job automatically updates ptr's time_to_live attribute */
		cpuset_shared_remove_job(ptr->sharing, (char *)share_req->owner);

		if (cpuset_shared_get_numjobs(ptr->sharing) > 0) {
			return 0;	/* jobs are still left */
		}

	}

	/* If space was provided, copy the cpuset's node bitfield. */
	if (maskp)
		BITFIELD_CPY(maskp, &ptr->nodes);

	/*
	 * Unlink the element from the list.  If first element, just bump the head
	 * pointer.  Otherwise, leapfrog the previous element's next pointer over
	 * this one.
	 */
	if (prev == NULL)		/* No previous element. */
		*listp = ptr->next;
	else
		prev->next = ptr->next;	/* Leapfrog over this element. */

	if (ptr->sharing)
		cpuset_shared_free(ptr->sharing);

	/* Zero the element for safety and free() it. */
	(void)memset(ptr, 0, sizeof(cpusetlist));

	free(ptr);

	return 0;
}

/**
 * @brief
 * 	free_cpusetlist()
 * 	Free a list composed of one or more cpusetlist elements.  
 * 
 * @param[in] list - pointer to list
 *
 * @return	int
 * @retval	num of elements freed	success
 * @retval	0			failure
 *
 */
int
free_cpusetlist(cpusetlist *list)
{
	cpusetlist		*ptr, *next;
	int			n = 0;

	/*
	 * Walk down the list, freeing elements.  Be sure to copy the next pointer
	 * before freeing the memory containing it.
	 */
	for (ptr = list; ptr != NULL; ptr = next) {
		next = ptr->next;

		if (ptr->sharing)
			cpuset_shared_free(ptr->sharing);
		free(ptr);

		n++;
	}

	return n;
}

/**
 * @brief
 * 	find_cpuset()
 * 	Perform a simple linear search on the supplied list, looking for a cpuset
 * 	named by qname.  
 *
 * @param[in] list - pointer to cpuset list
 * @param[in]  qname - cpuset name
 *
 * @return	pointer to cpusetlist
 * @retval	pointer to the list element for this cpuset 	if found
 * @retval	NULL						error
 *
 */
cpusetlist *
find_cpuset(cpusetlist *list, char *qname)
{
	char		canon[QNAME_STRING_LEN + 1];
	cpusetlist		*ptr;

	(void)strncpy(canon, qname, QNAME_STRING_LEN);
	canon[QNAME_STRING_LEN] = '\0';

	for (ptr = list; ptr != NULL; ptr = ptr->next)
		if (strcmp(ptr->name, canon) == 0)
			break;

	return ptr;
}

/**
 * @brief
 *	based on criteria find cpuset in list.
 *
 * @param[in] list - pointer to cpuset list
 * @param[in] criteria - pointer to cpuset_shared struct indicating criteria
 *
 * @return	pointer to cpusetlist
 * @retval	pointer to list		success
 * @retval	NULL			error
 *
 */
cpusetlist *
find_cpuset_shared(cpusetlist *list, cpuset_shared *criteria)
{
	cpusetlist	*ptr;
	cpusetlist	*candidate = NULL;
	time_t	ttl, cand_ttl;

	if (criteria == NULL)
		return (NULL);

	for (ptr = list; ptr; ptr = ptr->next) {

		if (ptr->sharing) {

			if (criteria->free_cpus <=
			cpuset_shared_get_free_cpus(ptr->sharing) && \
                    criteria->free_mem <=
				cpuset_shared_get_free_mem(ptr->sharing)) {

				ttl = cpuset_shared_get_time_to_live(ptr->sharing);
				if (!candidate ||
					(criteria->time_to_live <= ttl && ttl < cand_ttl) ||
					(criteria->time_to_live > cand_ttl && ttl > cand_ttl)) {
					candidate = ptr;
					cand_ttl = ttl;
				}
			}
		}
	}

	return (candidate);
}

/**
 * @brief
 * 	find_cpuset_byjob()
 * 	Perform a simple linear search on the supplied list, looking for a
 * 	cpuset where jobid is assigned.  This can be either an exclusive cpuset,
 * 	or a shared cpuset. NULL is returned If no cpuset was found.
 *
 * @param[in] list - pointer to cpuset list
 * @param[in] jobid - job identifier
 *
 * @return	structure handle
 * @retval	pointer to cpusetlist	success
 * @retval	NULL			error
 *
 */
cpusetlist *
find_cpuset_byjob(cpusetlist *list, char *jobid)
{
	cpusetlist		*ptr;
	char		*qn;

	if (jobid == NULL)
		return (NULL);

	for (ptr = list; ptr; ptr=ptr->next) {

		/* jobid is a member of a shared cpuset or in an exclusive cpuset */
		if( cpuset_shared_is_job_member(ptr->sharing, jobid) || \
	    (!ptr->sharing && (qn=string_to_qname(jobid)) && \
		strcmp(qn, ptr->name) == 0) )
			break;
	}

	return ptr;
}

/**
 * @brief
 * 	shared_nnodes: returns the # of nodeboards currently assigned to all
 * 	cpusets listed in 'list'.
 *
 * @param[in] list - pointer to cpusetlist
 *
 * @return	int
 * @retval	num of nodeboards	success
 * @retval	0			error
 *
 */
int
shared_nnodes(cpusetlist *list)
{
	cpusetlist	*ptr;
	int		ct;

	ct = 0;
	for (ptr = list; ptr; ptr = ptr->next) {

		if (ptr->sharing) {
			ct += BITFIELD_NUM_ONES((&ptr->nodes));
		}
	}
	return (ct);
}

/**
 * @brief
 *	print cpuset from the list.
 *
 * @param[in] list - pointer to cpusetlist
 * @param[in] heading - heading for printed list
 *
 * @return	Void
 *
 */
void
print_cpusets(cpusetlist *list, char *heading)
{
	cpusetlist		*ptr;
	int			i;

	i=0;

	log_err(0, __func__, heading);
	for (ptr = list; ptr != NULL; ptr = ptr->next) {
		sprintf(log_buffer,
			"cpuset[%d] = (name=%s, nodes_hex=%s nodes_bin=%s # of nodes=%d)", i, ptr->name, bitfield2hex(&ptr->nodes), bitfield2bin(&ptr->nodes), BITFIELD_NUM_ONES(&ptr->nodes));
		log_err(0, __func__, log_buffer);
		cpuset_shared_print(ptr->sharing);
		i++;
	}
}

/**
 * @brief
 * 	num_nodes_cpusets()
 * 	return the number of nodeboards assigned to the cpusets on the list.
 *
 * @param[in] list - pointer to cpusetlist
 *
 * @return	int 
 * @retval	num of nodeboards for cpuset	success
 * @retval	0				error
 *
 */
int
num_nodes_cpusets(cpusetlist *list)
{
	cpusetlist		*ptr;
	int			cnt;

	cnt = 0;
	for (ptr = list; ptr != NULL; ptr = ptr->next)
		cnt += BITFIELD_NUM_ONES(&list->nodes);

	return (cnt);
}

/* =========== Functions to convert between bitfields and cpusets ========== */

/**
 * @brief
 *	bitfield2cpuset()
 * 	Fill the provided cpuset_CPUList_t's cpu list with the cpus that
 * 	correspond to any set bits in the mask.  Then set the count
 * 	bit appropriately.  The end result is a cpuset_CPUList_t that is
 * 	ready to hand to the kernel to create a cpuset from the cpus that map
 * 	to the appropriate nodes in the mask.
 *
 * @param[in] cpuset - pointer to cpuset_CPUList_t
 * @param[in] mask - pointer to mask bitfield
 * 
 * @par	Note:
 * 	cpu 0 if found to be one of the cpusets to allocate, will only be part
 *	part of a cpuset if *EXCLUSIVE cpuset_create_flags are not set.
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
int
bitfield2cpuset(Bitfield *mask, cpuset_CPUList_t *cpuset)
{
	int			bit, slot;
	int			ncpus = 0;	/* Number of cpus assigned to cpuset. */
	cpuid_t		*cpus;

	/*
	 * For each set bit in the bitfield, add each cpu on that node to the
	 * array of CPUs in the supplied cpuset struct.
	 */
	for (bit = 0; bit < BITFIELD_SIZE; bit++) {
		if (!BITFIELD_TSTB(mask, bit))
			continue;       		/* Ignore unset bits in the mask. */

		/* Sanity check.  "This can't happen." */
		if (bit > maxnodeid) {
			log_err(errno, __func__, "requested node overruns available nodes");
			return -1;
		}

		/* Find array of cpus on node corresponding to this bit's position. */
		cpus = &nodemap[bit].cpu[0];

		for (slot = 0; slot < MAX_CPUS_PER_NODE; slot++) {
			if (cpus[slot] == (cpuid_t)-1)
				break;			/* No cpus remain for this node/bit. */

			if (((cpuset_create_flags & CPUSET_CPU_EXCLUSIVE) ||
				(cpuset_create_flags & CPUSET_MEMORY_EXCLUSIVE)) &&
				cpus[slot] == (cpuid_t)0)
				continue;		/* CPU 0 cannot be part of a cpuset. */

			cpuset->list[ncpus++] = cpus[slot];
		}
	}

	cpuset->count = ncpus;      /* total number of cpus */

	return 0;
}

/**
 * @brief
 * 	cpuset2bitfield()
 * 	Query the kernel to determine which cpus are assigned to the cpuset.
 * 	Fills the supplied mask with a bit set corresponding to any node from
 * 	which a cpu has been allocated.
 *
 * @param[in] qname - cpuset name
 * @param[in] mask - pointer to mask Bitfield
 *
 * @return	int
 * @retval	0	success
 * @retval	1	error
 *
 */
int
cpuset2bitfield(char *qname, Bitfield *mask)
{
	cpuset_CPUList_t *cpuset;
	Bitfield		new;
	int			i;

	/* Get the list of CPUs else print error & exit */
	if ((cpuset = cpusetGetCPUList(qname)) == NULL) {
		perror("cpusetGetCPUList");
		log_err(errno, __func__, "Error getting cpuset CPU list");
		return (1);
	}

	/* Set bits in mask for any cpus that are included in the cpuset. */
	BITFIELD_CLRALL(&new);
	for (i = 0; i < cpuset->count; i++)
		BITFIELD_SETB(&new, cpumap[cpuset->list[i]]);

	/* Copy the completed new mask into the passed-in one. */
	BITFIELD_CPY(mask, &new);

	cpusetFreeCPUList(cpuset);

	return 0;
}

/**
 * @brief
 * 	string_to_qname: given a generic string, return the first QNAME_STRING_LEN
 * 	characters. Note that the return storage is static
 *   	which will get overwritten on the next call to
 *	string_to_qname().
 *
 * @param[in] str - string which holds qname as substring
 *
 * @return	string
 * @retval	cpuset name	success
 * @retval	NULL		error
 *
 */
char *
string_to_qname(char *str)
{
	static char         qname[QNAME_STRING_LEN+ 1];
	int			len, idx;

	/*
	 * The cpuset must be named, and the queue name must be at least three
	 * characters long.  The caller really ought to check this, but defend
	 * against it anyway.
	 */
	if (str == NULL || (len = strlen(str)) < 3)
		return (NULL);

	if (len > QNAME_STRING_LEN)
		len = QNAME_STRING_LEN;

	for (idx=0; idx < len; idx++) {
		qname[idx] = str[idx];
	}
	qname[QNAME_STRING_LEN] = '\0';

	return (qname);
}

/**
 * @brief
 * 	nodemask_num_cpus: return the total # of cpus attached to the nodes
 * 	that are enabled in nodemask (those bits which are set where each represent
 * 	a node).
 *
 * @param[in] nodemask - pointer to bitfield indicating nodemask
 *
 * @return	int
 * @retval	-1			error
 * @retval	num of cpus on node 	success
 *
 */

int
nodemask_num_cpus(Bitfield *nodemask)
{
	cpuset_QueueDef_t   *qdef;
	int numcpus = -1;

	qdef = cpusetAllocQueueDef(cpusetGetCPUCount());
	if (!qdef) {
		sprintf(log_buffer,
			"couldn't allocate temp struct for %s",
			bitfield2hex(nodemask));
		log_err(errno, __func__, log_buffer);
		return (-1);
	}

	if (bitfield2cpuset(nodemask, qdef->cpu)) {
		(void)sprintf(log_buffer,
			"couldn't convert nodes to cpus info for %s",
			bitfield2hex(nodemask));
		log_err(errno, __func__, log_buffer);
		cpusetFreeQueueDef(qdef);
		return (-1);
	}

	numcpus = qdef->cpu->count;
	cpusetFreeQueueDef(qdef);

	return (numcpus);
}

/**
 * @brief
 * 	nodemask_tot_mem: return the total amt of memory of the nodes
 * 	that are enabled in nodemask (those bits which are set where each represent
 * 	a node). This will return a value in kb, to be consistent with job's
 * 	resource memory unit.
 *
 * @param[in] nodemask - pointer to bitfield indicating nodemask
 *
 * @return	int
 * @retval	-1					error
 * @retval	total amt of memory of the nodes	success
 *
 */
int
nodemask_tot_mem(Bitfield *nodemask)
{
	int			bit;
	size_t		mem = 0;

	/*
	 * For each set bit in the bitfield, this corresponds to a node and
	 * get its mem mapping. Accumulate the result.
	 *
	 */
	for (bit = 0; bit < BITFIELD_SIZE; bit++) {
		if (!BITFIELD_TSTB(nodemask, bit))
			continue;       		/* Ignore unset bits in the mask. */

		/* Sanity check.  "This can't happen." */
		if (bit > maxnodeid) {
			log_err(errno, __func__, "requested node overruns available nodes");
			return -1;
		}

		/* convert from mb to kb */
		mem += (nodemap[bit].memory * 1024);
	}
	return (mem);
}

/**
 * @brief
 *	determine if the given job can share cpuset.
 *
 * @param[in] pjob - job pointer
 * @param[out] share_req - pointer to cpuset info
 *
 * @return	int
 * @retval	1	success(job can share cpuset)
 * @retval	0	failure(cant share)
 *
 */
int
is_small_job(job *pjob, cpuset_shared *share_req)
{
	char                *id = "can_job_share_cpuset";
	resource            *pres;
	char                *jobid;
	unsigned long       ncpus = 0;
	size_t              mem = 0;
	time_t              walltime = 0;


	pres = (resource *)
		GET_NEXT(pjob->ji_wattr[(int)JOB_ATR_resource].at_val.at_list);
	while (pres != NULL) {
		if (strcmp(pres->rs_defin->rs_name,  "ncpus") == 0)
			getlong(pres, &ncpus);
		else if (strcmp(pres->rs_defin->rs_name,  "mem") == 0)
			mem = getsize(pres);
		else if (strcmp(pres->rs_defin->rs_name,  "walltime") == 0)
			local_gettime(pres, &walltime);

		pres = (resource *)GET_NEXT(pres->rs_link);
	}

	jobid = pjob->ji_qs.ji_jobid;
	if (ncpus == 0 || mem ==  0) {
		(void)sprintf(log_buffer,
			"can't determine if job %s can share cpuset - no ncpus or mem",
			jobid);
		log_err(-1, id, log_buffer);
		return (0);
	}

	/* all units in kb */
	if (ncpus <= cpuset_small_ncpus && mem <= cpuset_small_mem) {

		if (share_req) {
			cpuset_shared_unset(share_req);
			share_req->free_cpus = ncpus;
			share_req->free_mem = mem;
			share_req->time_to_live = time(0) + walltime;
			strcpy(share_req->owner, jobid);
		}
		return (1);
	}

	return (0);
}

/**
 * @brief
 * 	is_small_job2: like its predecessor, except recovered values for ncpus
 *	and mem are used first if set; otherwise, use the job resource values 
 *
 * @param[in] pjob - job pointer
 * @param[in] rmem - recovered mem val
 * @param[in] rncpus - recovered num of cpus
 * @param[in] share_req - pointer to cpuset info
 *
 * @return	int
 * @retval	1	success
 * @retval	0	error
 *
 */
int
is_small_job2(job *pjob, size_t rmem, int rncpus, cpuset_shared *share_req)
{
	resource            *pres;
	char                *jobid;
	unsigned long       ncpus = 0;
	size_t              mem = 0;
	time_t              walltime = 0;


	pres = (resource *)
		GET_NEXT(pjob->ji_wattr[(int)JOB_ATR_resource].at_val.at_list);
	while (pres != NULL) {
		if (strcmp(pres->rs_defin->rs_name,  "ncpus") == 0)
			getlong(pres, &ncpus);
		else if (strcmp(pres->rs_defin->rs_name,  "mem") == 0)
			mem = getsize(pres);
		else if (strcmp(pres->rs_defin->rs_name,  "walltime") == 0)
			local_gettime(pres, &walltime);

		pres = (resource *)GET_NEXT(pres->rs_link);
	}

	if (rmem > 0) {
		mem = rmem;	/* use the recovered value for mem */
		sprintf(log_buffer,
			"for job %s, using recovered mem=%d value from alt_id",
			pjob->ji_qs.ji_jobid, mem);
		log_err(-1, __func__, log_buffer);
	} else {
		sprintf(log_buffer,
			"for job %s, using resource value for mem=%d",
			pjob->ji_qs.ji_jobid, mem);
		log_err(-1, __func__, log_buffer);
	}

	if (rncpus > 0) {
		ncpus = rncpus;
		sprintf(log_buffer,
			"for job %s, using recovered ncpus=%d value from alt_id",
			pjob->ji_qs.ji_jobid, ncpus);
		log_err(-1, __func__, log_buffer);
	} else {
		sprintf(log_buffer,
			"for job %s, using resource value for ncpus=%d value",
			pjob->ji_qs.ji_jobid, ncpus);
		log_err(-1, __func__, log_buffer);
	}

	jobid = pjob->ji_qs.ji_jobid;
	if (ncpus == 0 || mem ==  0) {
		(void)sprintf(log_buffer,
			"can't determine if job %s can share cpuset - no ncpus or mem",
			jobid);
		log_err(-1, __func__, log_buffer);
		return (0);
	}

	/* job's memory request is in kb, whereas node memory is in mbytes */
	/* cpuset_small_mem is in kb, whereas mem is in bytes */
	if (ncpus <= cpuset_small_ncpus && mem <= cpuset_small_mem) {

		if (share_req) {
			cpuset_shared_unset(share_req);
			share_req->free_cpus = ncpus;
			share_req->free_mem = mem;
			share_req->time_to_live = time(0) + walltime;
			strcpy(share_req->owner, jobid);
		}
		return (1);
	}

	return (0);
}

/**
 * @brief
 * 	cpuset_permfile: Given a cpuset qname, construct the path to its
 *  	corresponding permfile.
 *
 * @paran[in] qname - cpuset name
 * @param[out] path - path for cpuset permission file
 *
 * @return	Void
 *
 */
void
cpuset_permfile(char *qname, char *path)
{
	(void)strcpy(path, path_jobs);
	(void)strcat(path, qname);
	(void)strcat(path, JOB_CPUSETQ_SUFFIX);   /* def'd in cpusets.h */
}

/**
 * @brief
 * 	cleanup_cpuset_permfiles: look for JOB_CPUSETQ_SUFFIX files, and match
 * 	with an existing job. If did not find a match, then blow away file.
 *
 */
void
cleanup_cpuset_permfiles(void)
{
	DIR		*dir;
	struct dirent	*pdirent;
	job		*pj = (job *)0;
	char		*job_suffix = JOB_CPUSETQ_SUFFIX;
	char		*psuffix;
	int		i, found;
	char		qname[MAXPATHLEN];
	int		job_suf_len = strlen(job_suffix);
	char		path[MAXPATHLEN+1];
	char		*qn;

	dir = opendir(path_jobs);
	if (dir == (DIR *)0) {
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER, LOG_ALERT,
			__func__, "Jobs directory not found");
		return;
	}
	while ((pdirent = readdir(dir)) != (struct dirent *)0) {

		if ((i = strlen(pdirent->d_name)) <= job_suf_len)
			continue;

		psuffix = pdirent->d_name + i - job_suf_len;
		if (strcmp(psuffix, job_suffix))
			continue;

		strcpy(qname, pdirent->d_name);
		psuffix = qname + i - job_suf_len;
		*psuffix = '\0';

		found = 0;
		pj = (job *)GET_NEXT(svr_alljobs);
		while (pj != (job *)0) {
			qn = job_to_qname(pj);
			if (qn && (strcasecmp(qname, qn) == 0)) {
				found = 1;
				break;
			}
			pj = (job *)GET_NEXT(pj->ji_alljobs);
		}
		if (!found) {
			strcpy(path, path_jobs);
			strcat(path, pdirent->d_name);
			unlink(path);
			sprintf(log_buffer, "removed stale cpuset permfile %s",
				path);
			log_err(0, __func__, log_buffer);
		}
	}
	(void)closedir(dir);
}

/**
 * @brief
 * 	is_cpuset_pbs_owned: tests whether or not we created the given cpuset name.
 *
 * @param[in] qname - cpuset name
 *
 * @return	int
 * @retval	1	true
 * @retval	0	false
 *
 */

int
is_cpuset_pbs_owned(char *qname)
{
	struct stat sbuf;
	char	    path[MAXPATHLEN];

	path[0] = '\0';
	cpuset_permfile(qname, path);

	if (stat(path, &sbuf) == 0 && S_ISREG(sbuf.st_mode))
		return (1);
	return (0);

}

/**
 * @brief
 *	remove_non_pbs_cpusets()
 * 	from the supplied list, search for and remove any cpusetlist element that
 * 	is not owned or created * by PBS.
 *
 * @par	Note:
 * 	If maskp is non-NULL, copy the element's nodes into *maskp.  Then, unlink
 * 	the element from the list and free() it.
 *
 * @param[in] listp - pointer to cpuset list
 * @param[in] maskp - pointer to bitfiled indiacating mask field
 *
 * @return	int
 * @retval	num of non-pbs owned cpusets	succes
 * @retval	0				error
 *
 */
int
remove_non_pbs_cpusets(cpusetlist **listp, Bitfield *maskp)
{
	cpusetlist		*prev, *ptr, *nextptr;
	int			ct;

	/* Shortcut -- bail out if list is NULL. */
	if (*listp == NULL)
		return 0;

	/*
	 * Search the supplied list for the canonicalized cpuset name.  Keep track
	 * of the previous pointer, so that the list can be fixed up.
	 */
	prev = NULL;
	ct = 0;
	for (ptr = *listp; ptr != NULL; ptr = nextptr) {

		nextptr = ptr->next;

		if (!is_cpuset_pbs_owned(ptr->name)) {

			/* Add the nodes for this cpuset into the specified bitmask. */
			if (maskp)
				BITFIELD_SETM(maskp, &ptr->nodes);

			/*
			 * Unlink the element from the list.  If first element, just
			 * bump the head pointer.  Otherwise, leapfrog the previous
			 * element's next pointer over this one.
			 */
			if (prev == NULL) {		/* No previous element. */
				*listp = ptr->next;
			} else {
				prev->next = ptr->next;	/* Leapfrog over this elem. */
			}

			/* Zero the element for safety and free() it. */
			(void)memset(ptr, 0, sizeof(cpusetlist));

			free(ptr);
			ptr = NULL;
			ct++;
		}

		if (ptr != NULL)
			prev = ptr;
	}

	return ct;
}

/**
 * @brief
 *	extract cpuset name from jobid.
 *
 * @param[in] pjob - job pointer
 *
 * @return	string
 * @retval	cpuset name	success
 * @retval	NULL		error
 *
 */
char *
job_to_qname(job *pjob)
{

	cpusetlist	*cset;
	char		*jobid;
	static char	qname[QNAME_STRING_LEN+ 1];
	char		*qnam;
	char		suffix[53];
	char		*p;

	jobid = pjob->ji_qs.ji_jobid;

	if (cset=find_cpuset_byjob(inusecpusets, jobid))
		return (cset->name);

	if ((qnam=string_to_qname(jobid)) == NULL)
		return (NULL);

	strcpy(qname, qnam);
	strcpy(suffix, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ");
	p = &suffix[0];
	while (find_cpuset(inusecpusets, qname) != NULL) { /* exists */
		if (*p == NULL)
			return (NULL);

		qname[QNAME_STRING_LEN-1] = *p;
		p++;
	}

	return (qname);
}

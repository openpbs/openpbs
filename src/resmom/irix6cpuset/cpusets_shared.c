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
 * @file	cpusets_shared.c
 * @brief
 * Library functions to simplify access to cpusets.
 */
/*
 #include <pbs_config.h>
 */

#include <sys/types.h>
#include <sys/sysmp.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "pbs_ifl.h"
#include "cpusets_shared.h"
#include "log.h"

typedef struct cpusetjobs {
	struct cpusetjobs *next;                /* Link to next element */
	char              jobid[PBS_MAXSVRJOBID+1];  /* job identifier */
	time_t		  time_to_live;
} cpusetjobs;

/**
 * @brief
 *	creates cpusetjob
 *
 * @return	structure handle
 * @retval	pointer to cpusetjobs	success
 * @retval	NULL			error
 *
 */
static cpusetjobs *
cpusetjobs_create(void)
{

	cpusetjobs *cjptr;

	cjptr = (cpusetjobs *)malloc(sizeof(struct cpusetjobs));

	if (cjptr == NULL) {
		return (NULL);
	}

	cjptr->jobid[0]  = '\0';
	cjptr->time_to_live = 0;
	cjptr->next = NULL;

	return (cjptr);

}

/**
 * @brief
 *	This add jobs in the order of their arrival. 
 *
 * @param[in] head - head pointer to cpusetjobs
 * @param[in] jobid - job id
 * @param[in] ttl - time to live for session
 * @param[in] add_flag - flag to indicate something added
 *
 * @return      structure handle
 * @retval      pointer to cpusetjobs   success
 * @retval      NULL                    error
 *
 */
static cpusetjobs *
cpusetjobs_add(cpusetjobs *head, char *jobid, int ttl, int *add_flag)
{
	cpusetjobs *cjptr, *lastptr, *new_head;

	*add_flag = 0;

	if (jobid == NULL)
		return (NULL);

	/* check if already on the list */
	lastptr = NULL;
	for (cjptr=head; cjptr; cjptr=cjptr->next) {
		lastptr = cjptr;
		if (strcmp(cjptr->jobid, jobid) == 0) { /* found a match */
			cjptr->time_to_live = ttl;	/*   so update ttl */
			return (head);	/* list is unchanged */
		} else if (strlen(cjptr->jobid) == 0) { /* found empty slot */
			strcpy(cjptr->jobid, jobid);
			cjptr->time_to_live = ttl;
			return (head);
		}

	}

	cjptr = cpusetjobs_create();
	if (cjptr == NULL) {
		return (NULL);
	}

	strcpy(cjptr->jobid, jobid);
	cjptr->time_to_live = ttl;
	cjptr->next = NULL;	/* always at the end of the list */
	if (lastptr) {
		new_head = head;
		lastptr->next = cjptr;
	} else {
		new_head = cjptr;
	}
	*add_flag = 1;	/* something indeed got added */
	return (new_head);	/* new head */

}

/**
 * @brief
 *      This removes jobs in the list .
 *
 * @param[in] head - head pointer to cpusetjobs
 * @param[in] jobid - job id
 * @param[in] add_flag - flag to indicate something removed
 *
 * @return      structure handle
 * @retval      pointer to new cpusetjobs   	success
 * @retval      NULL                    	error
 *
 */
static cpusetjobs *
cpusetjobs_remove(cpusetjobs *head, char *jobid, int *rem_flag)
{
	cpusetjobs *cjptr, *cjptr_before, *new_head;

	*rem_flag = 0;

	if (head == NULL || jobid == NULL)
		return (NULL);

	/* check if already on the list */
	new_head = head;
	cjptr_before = NULL;
	for (cjptr=head; cjptr; cjptr=cjptr->next) {
		if (strcmp(cjptr->jobid, jobid) == 0) { /* found a match */

			if (cjptr_before)
				cjptr_before->next = cjptr->next;
			else	/* about to delete current head */
				new_head = cjptr->next;
			(void)free(cjptr);
			*rem_flag = 1;
			break;
		}
		cjptr_before = cjptr;
	}

	return (new_head);
}

/**
 * @brief
 *	frees the cpusetjobs list
 *
 * @param[in] head - head pointer to cpusetjobs
 *
 * @return 	Void
 *
 */
static void
cpusetjobs_free(cpusetjobs *head)
{
	cpusetjobs *cjptr, *cjptr_next;

	if (head == NULL)
		return;

	/* check if already on the list */
	for (cjptr=head; cjptr; cjptr=cjptr_next) {
		cjptr_next = cjptr->next;
		(void)free(cjptr);
	}
}

/**
 * @brief
 *	get cpusetjobs list
 *
 * @param[in] head - head pointer to cpusetjobs list
 *
 * @return	string
 * @retval	cpusetjobs list		success
 * @retval	NUL			error
 *
 */
static char *
cpusetjobs_get(cpusetjobs *head)
{
	cpusetjobs *cjptr;
	static char joblist[4096];
	char	    buf[4096];
	time_t	    tim;
	char	    timestr[30];
	char	    *p;

	joblist[0] = '\0';
	strcpy(joblist, "cpuset_jobs=");
	for (cjptr=head; cjptr; cjptr=cjptr->next) {
		tim = cjptr->time_to_live;
		strcpy(timestr, (char *)ctime(&tim));
		if (p=strstr(timestr, "\n"))
			*p = '\0';
		sprintf(buf, "%s(ttl=%s) ", cjptr->jobid, timestr);
		strcat(joblist, buf);
	}
	return (joblist);	/* static, so next call will overwite this */
}

static time_t
cpusetjobs_max_time_to_live(cpusetjobs *head)
{
	cpusetjobs *cjptr;
	time_t max = -1;

	for (cjptr=head; cjptr; cjptr=cjptr->next) {
		if (cjptr->time_to_live > max) {
			max = cjptr->time_to_live;
		}
	}
	return (max);
}

/**
 * @brief
 *	wrapper function for cpuset_shared_unset.
 *
 * @return	structure handle
 * @retval	pointer to cpuset_shared structure	success
 * @retval	NULL					error
 *
 */
cpuset_shared *
cpuset_shared_create(void)
{
	cpuset_shared *csptr;

	csptr = (cpuset_shared *)malloc(sizeof(cpuset_shared));

	if (csptr == NULL) {
		return (NULL);
	}

	cpuset_shared_unset(csptr);

	return (csptr);
}

/**
 * @brief
 *	unset the values of shared cpuset 
 *
 * @param[in] csptr - pointer to cpuset_shared struct
 *
 * @return	Void
 *
 */
void
cpuset_shared_unset(cpuset_shared *csptr)
{
	if (csptr == NULL)
		return;

	csptr->free_cpus  = -1;
	csptr->free_mem = 0;
	csptr->time_to_live = -1;
	csptr->numjobs = -1;
	csptr->jobs = (cpusetjobs *)NULL;
	csptr->owner[0] = '\0';

}

/**
 * @brief
 *      set the values of shared cpuset
 *
 * @param[in] csptr - pointer to cpuset_shared struct
 *
 * @return     int
 * @retval	1	Failure
 * @retval	0	success 
 *
 */

int
cpuset_shared_is_set(cpuset_shared *csptr)
{
	if (csptr != NULL &&
		(csptr->free_cpus != -1 ||
		csptr->free_mem != 0 ||
		csptr->time_to_live != -1 ||
		csptr->numjobs != -1 ||
		csptr->jobs != NULL ||
		strlen(csptr->owner) != 0))
		return (1);

	return (0);
}

/**
 * @brief
 *      prints the values of shared cpuset
 *
 * @param[in] cs - pointer to cpuset_shared struct
 *
 * @return      Void
 *
 */
void
cpuset_shared_print(cpuset_shared *cs)
{

	time_t	ttl;
	char	timestr[30];
	char	*p;

	if (cs == NULL) {
		return;
	}
	ttl = cs->time_to_live;
	strcpy(timestr, (char *)ctime(&ttl));
	if ((p=strstr(timestr, "\n")))
		*p = '\0';
	sprintf(log_buffer, "free_cpus=%d free_mem=%dkb time_to_live=%s numjobs=%d owner=%s %s", cs->free_cpus, cs->free_mem, timestr, cs->numjobs, cs->owner, cpusetjobs_get(cs->jobs));
	log_err(0, "cpuset_shared_print", log_buffer);

}

/**
 * @brief
 *      frees values of shared cpuset
 *
 * @param[in] cs - pointer to cpuset_shared struct
 *
 * @return      Void
 *
 */
void
cpuset_shared_free(cpuset_shared *cs)
{
	if (cs == NULL)
		return;

	cpusetjobs_free(cs->jobs);
	(void)free(cs);
}

/**
 * @brief
 *      frees cpus values of shared cpuset
 *
 * @param[in] cs - pointer to cpuset_shared struct
 *
 * @return      int
 * @retval	freed val	success
 * @retval	-1		error
 *
 */
int
cpuset_shared_get_free_cpus(cpuset_shared *cs)
{
	if (cs) {
		return (cs->free_cpus);
	}
	return (-1);
}

/**
 * @brief
 *      frees mem values of shared cpuset
 *
 * @param[in] cs - pointer to cpuset_shared struct
 *
 * @return      size_t
 * @retval      freed val       success
 * @retval      0		error
 *
 */
size_t
cpuset_shared_get_free_mem(cpuset_shared *cs)
{
	if (cs) {
		return (cs->free_mem);
	}
	return (0);
}

/**
 * @brief
 *      frees ttl  values of shared cpuset
 *
 * @param[in] cs - pointer to cpuset_shared struct
 *
 * @return      time_t
 * @retval      freed val       success
 * @retval      -1            	error
 *
 */
time_t
cpuset_shared_get_time_to_live(cpuset_shared *cs)
{
	if (cs) {
		return (cs->time_to_live);
	}
	return (-1);
}

/**
 * @brief
 *      frees owner values of shared cpuset
 *
 * @param[in] cs - pointer to cpuset_shared struct
 *
 * @return      string
 * @retval      freed val       success
 * @retval      NULL          	error
 *
 */
char *
cpuset_shared_get_owner(cpuset_shared *cs)
{
	if (cs) {
		return (cs->owner);
	}
	return (NULL);
}

/**
 * @brief
 *      frees num of jobs value of shared cpuset
 *
 * @param[in] cs - pointer to cpuset_shared struct
 *
 * @return      int
 * @retval      freed val       success
 * @retval      0            	error
 *
 */
int
cpuset_shared_get_numjobs(cpuset_shared *cs)
{
	if (cs) {
		return (cs->numjobs);
	}
	return (0);
}


void
cpuset_shared_set_free_cpus(cpuset_shared *cs,  int cpus)
{
	if (cs) {
		cs->free_cpus = cpus;
	}
}

/**
 * @brief
 *	sets the free mem value
 *
 * @param[out] cs - pointer to cpuset_shared struct
 * @param[in] mem - mem value
 *
 * @return	Void
 *
 */
void
cpuset_shared_set_free_mem(cpuset_shared *cs, size_t mem)
{
	if (cs) {
		cs->free_mem = mem;
	}
}

/**
 * @brief
 * 	set to maximum end time among jobs that cs owns 
 *
 * @param[out/in] cs - pointer to cpuset_shared struct
 *
 * @return	void
 *
 */
void
cpuset_shared_set_time_to_live(cpuset_shared *cs)
{
	if (cs) {
		cs->time_to_live = cpusetjobs_max_time_to_live(cs->jobs);
	}
}

/** 
 * @brief 
 *      set owner value of cs 
 *
 * @param[out/in] 	cs - pointer to cpuset_shared struct
 * @param[in] 		owner - owner val
 *
 * @return      void
 *
 */     
void
cpuset_shared_set_owner(cpuset_shared *cs, char *owner)
{
	if (cs) {
		strcpy(cs->owner, owner);
	}
}

/**
 * @brief
 * 	Everytime a job is added, the time_to_live attribute of cs is automatically
 *	updated, and also the owner is set to the first job in the list. 
 *
 * @param[out/in] cs - pointer to cpuset_shared struct
 * @param[in]	  jobid - job id
 * @param[in]	  ttl - time to live
 *
 * @return	void
 *
 */
void
cpuset_shared_add_job(cpuset_shared *cs, char *jobid, time_t ttl)
{
	int	add;

	if (cs) {
		cs->jobs = cpusetjobs_add(cs->jobs, jobid, ttl, &add);
		if (add) {
			if (cs->numjobs < 0)
				cs->numjobs = 1;
			else
				cs->numjobs++;
		}
	}
	cpuset_shared_set_time_to_live(cs);
}

/** 
 * @brief
 * 	wrapper function for cpusetjobs_remove
 *
 * @param[in] cs - pointer to cpuset_shared struct
 * @param[in] jobid - job id
 *
 * @return	Void
 *
 */
void
cpuset_shared_remove_job(cpuset_shared *cs, char *jobid)
{

	int	rem;

	if (cs) {
		cs->jobs = cpusetjobs_remove(cs->jobs, jobid, &rem);
		if (rem) {
			cs->numjobs--;
		}
	}
	cpuset_shared_set_time_to_live(cs);
}

/**
 * @brief
 *	test whether job with jobid is in cpuset_shared list
 *
 * @param[in] cs - pointer to cpuset_shared struct
 * @param[in] jobid - job id
 *
 * @return	int
 * @retval	0	error
 * @retval	1	success
 *
 */
int
cpuset_shared_is_job_member(cpuset_shared *cs, char *jobid)
{
	cpusetjobs *cjptr;

	if (cs == NULL || jobid == NULL)
		return (0);

	for (cjptr=cs->jobs; cjptr; cjptr=cjptr->next) {
		if (strcmp(cjptr->jobid, jobid) == 0)
			return (1);
	}
	return (0);
}

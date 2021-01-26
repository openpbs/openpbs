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


/**
 * @file    job_recov_fs.c
 *
 * @brief
 *	job_recov_fs.c - This file contains the functions to record a job
 *	data struture to disk and to recover it from disk by Mom
 *
 *	The data is recorded in a file whose name is the job_id.
 *
 *	The following public functions are provided:
 *		job_save_fs() -		save the disk image
 *		job_recov_fs() -		recover (read) job from disk
 */

#include <pbs_config.h>   /* the master config generated by configure */

#include <stdio.h>
#include <sys/types.h>
#include <sys/param.h>

#include "pbs_ifl.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

#include <unistd.h>
#include "server_limits.h"
#include "list_link.h"
#include "attribute.h"

#include <sys/stat.h>

#include "job.h"
#include "reservation.h"
#include "queue.h"
#include "log.h"
#include "pbs_nodes.h"
#include "svrfunc.h"
#include <memory.h>
#include "libutil.h"


#define MAX_SAVE_TRIES 3

/* global data items */

extern char  *path_jobs;
extern time_t time_now;
extern char   pbs_recov_filename[];

/* data global only to this file */

static const size_t fixedsize = sizeof(struct jobfix);
static const size_t extndsize = sizeof(union jobextend);


/**
 * @brief
 *		Saves (or updates) a job structure image on disk
 *
 *		Save does either - a quick update for state changes only,
 *			 - a full update for an existing file, or
 *			 - a full write for a new job
 *
 *		For a quick update, the data written is less than a disk block
 *		size and no size change occurs.
 *
 *		No need of O_SYNC flag as this will improve the performance.
 *		This might lead to data loss from file system in case of system
 *		crash. This is not an issue as data is mostly recovered from the
 *		database.
 *
 *		For a new file write, first time, the data is written directly to
 *		the file.
 *
 * @param[in]	pjob - Pointer to the job structure to save
 *
 * @return      Error code
 * @retval	 0  - Success
 * @retval	-1  - Failure
 *
 */

int
job_save_fs(job *pjob)
{
	int	fds;
	int	i;
	char	*filename;
	char	namebuf1[MAXPATHLEN+1];
	char	namebuf2[MAXPATHLEN+1];
	int	openflags;
	int	redo;
	int	pmode;
	int quick = 1;
	struct attribute *pattr;

#ifdef WIN32
	pmode = _S_IWRITE | _S_IREAD;
#else
	pmode = 0600;
#endif

	(void)strcpy(namebuf1, path_jobs);	/* job directory path */
	if (*pjob->ji_qs.ji_fileprefix != '\0')
		(void)strcat(namebuf1, pjob->ji_qs.ji_fileprefix);
	else
		(void)strcat(namebuf1, pjob->ji_qs.ji_jobid);
	(void)strcpy(namebuf2, namebuf1);	/* setup for later */
	(void)strcat(namebuf1, JOB_FILE_SUFFIX);



	if (pjob->ji_qs.ji_jsversion != JSVERSION) {
		/* version of job structure changed, force full write */
		pjob->ji_qs.ji_jsversion = JSVERSION;
		quick = 0;
	}

	pattr = pjob->ji_wattr;
	for (i = 0; i < JOB_ATR_LAST; i++) {
		if ((pattr+i)->at_flags & ATR_VFLAG_MODIFY) {
			quick = 0;
			break;
		}
	}

	if (quick) {
		openflags =  O_WRONLY;
		fds = open(namebuf1, openflags, pmode);
		if (fds < 0) {
			log_errf(errno, __func__, "Failed to open %s file", namebuf1);
			return (-1);
		}
#ifdef WIN32
		secure_file(namebuf1, "Administrators",
			READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED);
		setmode(fds, O_BINARY);
#endif

		/* just write the "critical" base structure to the file */

		save_setup(fds);
		if ((save_struct((char *)&pjob->ji_qs, fixedsize) == 0) &&
			(save_struct((char *)&pjob->ji_extended, extndsize) == 0) &&
			(save_flush() == 0)) {
			(void)close(fds);
		} else {
			log_err(errno, "job_save", "error quickwrite");
			(void)close(fds);
			return (-1);
		}

	} else {
		/* an attribute changed,  update mtime */
		set_jattr_l_slim(pjob, JOB_ATR_mtime, time_now, SET);

		/*
		 * write the whole structure to the file.
		 * For a update, this is done to a new file to protect the
		 * old against crashs.
		 * The file is written in four parts:
		 * (1) the job structure,
		 * (2) the extended area,
		 * (3) if a Array Job, the index tracking table
		 * (4) the attributes in the "encoded "external form, and last
		 * (5) the dependency list.
		 */

		(void)strcat(namebuf2, JOB_FILE_COPY);
		openflags =  O_CREAT | O_WRONLY;

#ifdef WIN32
		fix_perms2(namebuf2, namebuf1);
#endif

		filename = namebuf2;

		fds = open(filename, openflags, pmode);
		if (fds < 0) {
			log_err(errno, "job_save",
				"error opening for full save");
			return (-1);
		}

#ifdef WIN32
		secure_file(filename, "Administrators",
			READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED);
		setmode(fds, O_BINARY);
#endif

		for (i=0; i<MAX_SAVE_TRIES; ++i) {
			redo = 0;	/* try to save twice */
			save_setup(fds);
			if (save_struct((char *)&pjob->ji_qs, fixedsize)
				!= 0) {
				redo++;
			} else if (save_struct((char *)&pjob->ji_extended,
				extndsize) != 0) {
				redo++;
			} else if (save_attr_fs(job_attr_def, pjob->ji_wattr,
				(int)JOB_ATR_LAST) != 0) {
				redo++;
			} else if (save_flush() != 0) {
				redo++;
			}
			if (redo != 0) {
				if (lseek(fds, (off_t)0, SEEK_SET) < 0) {
					log_err(errno, "job_save", "error lseek");
				}
			} else
				break;
		}


		(void)close(fds);
		if (i >= MAX_SAVE_TRIES)
			return (-1);

#ifdef WIN32
		if (MoveFileEx(namebuf2, namebuf1,
			MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH) == 0) {

			errno = GetLastError();
			sprintf(log_buffer, "MoveFileEx(%s,%s) failed!",
				namebuf2, namebuf1);
			log_err(errno, "job_save", log_buffer);
		}
		secure_file(namebuf1, "Administrators",
			READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED);
#else
		if (rename(namebuf2, namebuf1) == -1) {
			log_event(PBSEVENT_ERROR|PBSEVENT_SECURITY,
				PBS_EVENTCLASS_JOB, LOG_ERR,
				pjob->ji_qs.ji_jobid,
				"rename in job_save failed");
		}
#endif
	}
	return (0);
}

/**
 * @brief
 *		recover (read in) a job from its save file
 *
 *		This function is only needed upon server start up.
 *
 *		The job structure, its attributes strings, and its dependencies
 *		are recovered from the disk.  Space to hold the above is
 *		malloc-ed as needed.
 *
 *
 * @param[in]	filename	- Name of job file to load job from
 *
 * @return	pointer to new job structure
 *
 * @retval	 NULL - Failure
 * @retval	!NULL - Success
 *
 */

job *
job_recov_fs(char *filename)
{
	int		 fds;
	char		 basen[MAXPATHLEN+1];
	job		*pj;
	char		*pn;
	char		*psuffix;


	pj = job_alloc();	/* allocate & initialize job structure space */
	if (pj == NULL) {
		return NULL;
	}

	(void)strcpy(pbs_recov_filename, path_jobs);	/* job directory path */
	(void)strcat(pbs_recov_filename, filename);
#ifdef WIN32
	fix_perms(pbs_recov_filename);
#endif

	/* change file name in case recovery fails so we don't try same file */

	pbs_strncpy(basen, pbs_recov_filename, sizeof(basen));
	psuffix = basen + strlen(basen) - strlen(JOB_BAD_SUFFIX);
	(void)strcpy(psuffix, JOB_BAD_SUFFIX);
#ifdef WIN32
	if (MoveFileEx(pbs_recov_filename, basen,
		MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) == 0) {
		errno = GetLastError();
		sprintf(log_buffer, "MoveFileEx(%s, %s) failed!",
			pbs_recov_filename, basen);
		log_err(errno, "nodes", log_buffer);

	}
	secure_file(basen, "Administrators",
		READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED);
#else
	if (rename(pbs_recov_filename, basen) == -1) {
		sprintf(log_buffer, "error renaming job file %s",
			pbs_recov_filename);
		log_err(errno, __func__, log_buffer);
		free((char *)pj);
		return NULL;
	}
#endif

	fds = open(basen, O_RDONLY, 0);
	if (fds < 0) {
		sprintf(log_buffer, "error opening of job file %s",
			pbs_recov_filename);
		log_err(errno, __func__, log_buffer);
		free((char *)pj);
		return NULL;
	}
#ifdef WIN32
	setmode(fds, O_BINARY);
#endif

	/* read in job fixed sub-structure */

	errno = -1;
	if (read(fds, (char *)&pj->ji_qs, fixedsize) != (int)fixedsize) {
		sprintf(log_buffer, "error reading fixed portion of %s",
			pbs_recov_filename);
		log_err(errno, __func__, log_buffer);
		free((char *)pj);
		(void)close(fds);
		return NULL;
	}
	/* Does file name match the internal name? */
	/* This detects ghost files */

#ifdef WIN32
	pn = strrchr(pbs_recov_filename, (int)'/');
	if (pn == NULL)
		pn = strrchr(pbs_recov_filename, (int)'\\');
	if (pn == NULL) {
		sprintf(log_buffer, "bad path %s", pbs_recov_filename);
		log_err(errno, __func__, log_buffer);
		free((char *)pj);
		(void)close(fds);
		return NULL;
	}
	pn++;
#else
	pn = strrchr(pbs_recov_filename, (int)'/') + 1;
#endif

	if (strncmp(pn, pj->ji_qs.ji_jobid, strlen(pn)-3) != 0) {
		/* mismatch, discard job */

		(void)sprintf(log_buffer,
			"Job Id %s does not match file name for %s",
			pj->ji_qs.ji_jobid,
			pbs_recov_filename);
		log_err(-1, __func__, log_buffer);
		free((char *)pj);
		(void)close(fds);
		return NULL;
	}

	/* read in extended save area depending on JSVERSION */

	errno = 0;
	DBPRT(("Job save version %d\n", pj->ji_qs.ji_jsversion))
	if (pj->ji_qs.ji_jsversion >= JSVERSION_18) {
		/* since there is no change in jobextend structure for JSVERSION(1900) and JSVERSION_18(800),
		 * read the current structure.
		 */
		if (read(fds, (char *)&pj->ji_extended,
			sizeof(union jobextend)) !=
			sizeof(union jobextend)) {
			sprintf(log_buffer,
				"error reading extended portion of %s",
				pbs_recov_filename);
			log_err(errno, __func__, log_buffer);
			free((char *)pj);
			(void)close(fds);
			return NULL;
		}
	} else {
		/* If really an old version(i.e. pre 13.x), it wasn't there, abort out */
		sprintf(log_buffer,
			"Job structure version cannot be recovered for job %s",
			pbs_recov_filename);
		log_err(errno, __func__, log_buffer);
		free((char *)pj);
		(void)close(fds);
		return NULL;
	}

	/* read in working attributes */

	if (recov_attr_fs(fds, pj, job_attr_idx, job_attr_def, pj->ji_wattr, (int)JOB_ATR_LAST,
		(int)JOB_ATR_UNKN) != 0) {
		sprintf(log_buffer, "error reading attributes portion of %s",
			pbs_recov_filename);
		log_err(errno, __func__, log_buffer);
		job_free(pj);
		(void)close(fds);
		return NULL;
	}
	(void)close(fds);

#if defined(WIN32)
	/* get a handle to the job (may not exist) */
	pj->ji_hJob = OpenJobObject(JOB_OBJECT_ALL_ACCESS, FALSE,
		pj->ji_qs.ji_jobid);
#endif

	/* all done recovering the job, change file name back to .JB */

#ifdef WIN32
	if (MoveFileEx(basen, pbs_recov_filename,
		MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) == 0) {
		errno = GetLastError();
		sprintf(log_buffer, "MoveFileEx(%s, %s) failed!",
			basen, pbs_recov_filename);
		log_err(errno, "nodes", log_buffer);

	}
	secure_file(pbs_recov_filename, "Administrators",
		READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED);
#else
	(void)rename(basen, pbs_recov_filename);
#endif

	return (pj);
}

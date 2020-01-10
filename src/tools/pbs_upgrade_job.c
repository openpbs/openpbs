/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
 * @file pbs_upgrade_job.c
 *
 * @brief
 *		pbs_upgrade_job.c - This file contains the functions to read in an older .JB file (from 13.x to 19.x versions)
 *		and convert it into the newer format.
 * @par
 *		This tool is required due to the change in PBS macros which are defined in the pbs_ifl.h/server_limits.h
 		or in any other file and the same macros PBS uses in the job structure(see job.h) as well that alters the
		size of the jobfix and taskfix structures.
 *
 * Functions included are:
 * 	main()
 * 	print_usage()
 * 	check_job_file()
 * 	upgrade_job_file()
 * 	upgrade_task_file()
 * 	main()
 */

/* Need to define PBS_MOM to get the pbs_task structure from job.h */
#define PBS_MOM

#include "pbs_config.h"

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include "pbs_ifl.h"
#include "list_link.h"
#include "attribute.h"
#include "job.h"
#include "tm.h"
#include "server_limits.h"
#include "pbs_version.h"

#ifndef WIN32
#define O_BINARY 0
#endif

/*
 * Define macros that controlled the size of the jobfix and taskfix structure (see job.h)
 * from 13.x to pre 19.x versions. Append the _PRE19 suffix to each.
 */

/* From pbs_ifl.h */
#define PBS_MAXSEQNUM_PRE19	7
#define PBS_MAXSVRJOBID_PRE19	(PBS_MAXSEQNUM_PRE19 - 1 + PBS_MAXSERVERNAME + PBS_MAXPORTNUM + 2)

/*
 * Replicate the jobfix and taskfix structures as they were defined in 13.x to pre 19.x versions.
 * Use the macros defined above for convenience.
 */
typedef struct jobfix_PRE19
{
	int ji_jsversion;   	/* job structure version - JSVERSION */
	int ji_state;		/* internal copy of state */
	int ji_substate;	/* job sub-state */
	int ji_svrflags;	/* server flags */
	int ji_numattr;		/* not used */
	int ji_ordering;	/* special scheduling ordering */
	int ji_priority;	/* internal priority */
	time_t ji_stime;	/* time job started execution */
	time_t ji_endtBdry; 	/* estimate upper bound on end time */

	char ji_jobid[PBS_MAXSVRJOBID_PRE19 + 1]; /* job identifier */
	char ji_fileprefix[PBS_JOBBASE + 1];	  /* no longer used */
	char ji_queue[PBS_MAXQUEUENAME + 1];	  /* name of current queue */
	char ji_destin[PBS_MAXROUTEDEST + 1];	  /* dest from qmove/route */
	/* MomS for execution    */

	int ji_un_type; /* type of ji_un union */
	union {		/* depends on type of queue currently in */
		struct
		{					/* if in execution queue .. */
			pbs_net_t ji_momaddr;		/* host addr of Server */
			unsigned int ji_momport;	/* port # */
			int ji_exitstat;		/* job exit status from MOM */
		} ji_exect;
		struct
		{
			time_t ji_quetime;  /* time entered queue */
			time_t ji_rteretry; /* route retry time */
		} ji_routet;
		struct
		{
			int ji_fromsock;		/* socket job coming over */
			pbs_net_t ji_fromaddr;		/* host job coming from   */
			unsigned int ji_scriptsz; 	/* script size */
		} ji_newt;
		struct
		{
			pbs_net_t ji_svraddr;		/* host addr of Server */
			int ji_exitstat;	  	/* job exit status from MOM */
			uid_t ji_exuid;		  	/* execution uid */
			gid_t ji_exgid;		  	/* execution gid */
		} ji_momt;
	} ji_un;
} jobfix_PRE19;

typedef struct taskfix_PRE19
{
	char ti_parentjobid[PBS_MAXSVRJOBID_PRE19 + 1];
	tm_node_id ti_parentnode;	/* parent vnode */
	tm_node_id ti_myvnode;		/* my vnode */
	tm_task_id ti_parenttask;	/* parent task */
	tm_task_id ti_task;		/* task's taskid */
	int ti_status;			/* status of task */
	pid_t ti_sid;			/* session id */
	int ti_exitstat;		/* exit status */
	union {
		int ti_hold[16]; 	/* reserved space */
	} ti_u;
} taskfix_PRE19;

/* Create a global buffer for reading and writing data. */
char buf[4096];

/**
 * @brief
 *		Print usage text to stderr and exit.
 *
 * @return	void
 */
void
print_usage(void)
{
	fprintf(stderr, "Invalid parameter specified. Usage:\n");
	fprintf(stderr, "pbs_upgrade_job [-c] -f file.JB\n");
}

/**
 * @brief
 *		Attempt to identify the format version of job file.
 *
 * @param[in]	fd	-File descriptor from which to read
 *
 * @return	int
 * @retval	-1	: failure
 * @retval	>=0	: version number
 */
int
check_job_file(int fd)
{
	off_t pos_saved;
	off_t pos_new;
	int ret_version = -1;
	int length = -1;
	jobfix_PRE19 old_jobfix_pre19;
	errno = 0;

	/* Save our current position so we can comeback to it */
	pos_saved = lseek(fd, 0, SEEK_CUR);

	/*---------- For PBSPro >=13.x or <=18.x versions jobfix structure ---------- */
	pos_new = lseek(fd, pos_saved, SEEK_SET);
	if (pos_new != 0) {
			fprintf(stderr, "Couldn't set the file position to zero [%s]\n",
					errno ? strerror(errno) : "No error");
			goto check_job_file_exit;
	}
	old_jobfix_pre19.ji_jsversion = 0;
	length = read(fd, (char *)&old_jobfix_pre19.ji_jsversion, sizeof(old_jobfix_pre19.ji_jsversion));
	if (length < 0) {
		fprintf(stderr, "Failed to read input file [%s]\n",
				errno ? strerror(errno) : "No error");
		goto check_job_file_exit;
	}
	if (old_jobfix_pre19.ji_jsversion == JSVERSION_18) {
		/* for all type of jobfix structures, from 13.x to 18.x PBS versions */
		ret_version = 18;
		goto check_job_file_exit;
	} else if (old_jobfix_pre19.ji_jsversion == JSVERSION) {
		/* if job has already updated structure */
		ret_version = 19;
		goto check_job_file_exit;
	} else {
		fprintf(stderr, "Job structure version (JSVERSION) not recognized, found=%d.\n",
				old_jobfix_pre19.ji_jsversion);
		goto check_job_file_exit;
	}

check_job_file_exit:
	pos_new = lseek(fd, pos_saved, SEEK_SET);
	if (pos_new != 0) {
			fprintf(stderr, "Couldn't set the file position back to zero [%s]\n",
					errno ? strerror(errno) : "No error");
			goto check_job_file_exit;
		}
	return ret_version;
}

/**
 * @brief
 *		Upgrade a job file from an earlier version.
 *
 * @param[in]	fd		-	File descriptor from which to read
 * 
 * @return	int
 * @retval	-1	: failure
 * @retval	 0	: success
 */
int
upgrade_job_file(int fd)
{
	FILE *tmp = NULL;
	int tmpfd = -1;
	int len;
	int ret;
	off_t pos;
	jobfix_PRE19 old_jobfix_pre19;
	job new_job;
	errno = 0;

	/* The following code has been modeled after job_recov_fs() */

	/* Read in the pre19 jobfix structure */
	memset(&old_jobfix_pre19, 0, sizeof(old_jobfix_pre19));
	len = read(fd, (char *)&old_jobfix_pre19, sizeof(old_jobfix_pre19));
	if (len < 0) {
		fprintf(stderr, "Failed to read input file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	if (len != sizeof(old_jobfix_pre19)) {
		fprintf(stderr, "Format not recognized, not enough fixed data.\n");
		return 1;
	}

	/* Copy the data to the new jobfix structure */
	memset(&new_job, 0, sizeof(new_job));
	memcpy(&new_job.ji_qs, &old_jobfix_pre19, sizeof(old_jobfix_pre19));
	snprintf(new_job.ji_qs.ji_jobid, sizeof(new_job.ji_qs.ji_jobid),
			"%s", old_jobfix_pre19.ji_jobid);
	snprintf(new_job.ji_qs.ji_fileprefix, sizeof(new_job.ji_qs.ji_fileprefix),
			"%s", old_jobfix_pre19.ji_fileprefix);
	snprintf(new_job.ji_qs.ji_queue, sizeof(new_job.ji_qs.ji_queue),
			"%s", old_jobfix_pre19.ji_queue);
	snprintf(new_job.ji_qs.ji_destin, sizeof(new_job.ji_qs.ji_destin),
			"%s", old_jobfix_pre19.ji_destin);
	new_job.ji_qs.ji_un_type = old_jobfix_pre19.ji_un_type;
	memcpy(&new_job.ji_qs.ji_un, &old_jobfix_pre19.ji_un, sizeof(new_job.ji_qs.ji_un));

	/* Open a temporary file to stage data */
	tmp = tmpfile();
	if (!tmp) {
		fprintf(stderr, "Failed to open temporary file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	tmpfd = fileno(tmp);
	if (tmpfd < 0) {
		fprintf(stderr, "Failed to find temporary file descriptor [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Write the new jobfix structure to the output file */
	len = write(tmpfd, &new_job.ji_qs, sizeof(new_job.ji_qs));
	if (len != sizeof(new_job.ji_qs)) {
		fprintf(stderr, "Failed to write jobfix to output file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Read the rest of the input and write it to the temporary file */
	do {
		len = read(fd, buf, sizeof(buf));
		if (len < 0) {
			fprintf(stderr, "Failed to read input file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len < 1)
			break;
		len = write(tmpfd, buf, len);
		if (len < 0) {
			fprintf(stderr, "Failed to write output file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
	} while (len > 0);

	/* Reset the file descriptors to zero */
	pos = lseek(fd, 0, SEEK_SET);
	if (pos != 0) {
		fprintf(stderr, "Failed to reset job file position [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	pos = lseek(tmpfd, 0, SEEK_SET);
	if (pos != 0) {
		fprintf(stderr, "Failed to reset temporary file position [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Copy the data from the temporary file back to the original */
	do {
		len = read(tmpfd, buf, sizeof(buf));
		if (len < 0) {
			fprintf(stderr, "Failed to read temporary file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len < 1)
			break;
		len = write(fd, buf, len);
		if (len < 0) {
			fprintf(stderr, "Failed to write job file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
	} while (len > 0);

	ret = fclose(tmp);
	if (ret != 0) {
		fprintf(stderr, "Failed to close temporary file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	return 0;
}

/**
 * @brief
 *		Upgrade a task file from an earlier version.
 *
 * @param[in]	taskfile		-	File name of the task file
 * @return	int
 * @retval	-1	: failure
 * @retval	0	: success
 */
int
upgrade_task_file(char *taskfile)
{
	FILE *tmp = NULL;
	int fd;
	int tmpfd = -1;
	int len;
	int ret;
	off_t pos;
	taskfix_PRE19 old_taskfix_pre19;
	pbs_task new_task;
	errno = 0;

	/* The following code has been modeled after task_recov() */

	/* Open the task file */
	fd = open(taskfile, O_BINARY | O_RDWR);
	if (fd < 0) {
		fprintf(stderr, "Failed to open %s [%s]\n", taskfile,
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Read in the pre19 task structure */
	memset(&old_taskfix_pre19, 0, sizeof(old_taskfix_pre19));
	len = read(fd, (char *)&old_taskfix_pre19, sizeof(old_taskfix_pre19));
	if (len < 0) {
		fprintf(stderr, "Failed to read input file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	if (len != sizeof(old_taskfix_pre19)) {
		fprintf(stderr, "Format not recognized, not enough fixed data.\n");
		return 1;
	}
	/* Copy the data to the new task structure */
	memset(&new_task, 0, sizeof(new_task));
	strncpy(new_task.ti_qs.ti_parentjobid, old_taskfix_pre19.ti_parentjobid,
			sizeof(new_task.ti_qs.ti_parentjobid));
	new_task.ti_qs.ti_parentnode = old_taskfix_pre19.ti_parentnode;
	new_task.ti_qs.ti_myvnode = old_taskfix_pre19.ti_myvnode;
	new_task.ti_qs.ti_parenttask = old_taskfix_pre19.ti_parenttask;
	new_task.ti_qs.ti_task = old_taskfix_pre19.ti_task;
	new_task.ti_qs.ti_status = old_taskfix_pre19.ti_status;
	new_task.ti_qs.ti_sid = old_taskfix_pre19.ti_sid;
	new_task.ti_qs.ti_exitstat = old_taskfix_pre19.ti_exitstat;
	memcpy(&new_task.ti_qs.ti_u, &old_taskfix_pre19.ti_u, sizeof(old_taskfix_pre19.ti_u));

	/* Open a temporary file to stage data */
	tmp = tmpfile();
	if (!tmp) {
		fprintf(stderr, "Failed to open temporary file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	tmpfd = fileno(tmp);
	if (tmpfd < 0) {
		fprintf(stderr, "Failed to find temporary file descriptor [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Write the new taskfix structure to the output file */
	len = write(tmpfd, &new_task.ti_qs, sizeof(new_task.ti_qs));
	if (len != sizeof(new_task.ti_qs)) {
		fprintf(stderr, "Failed to write taskfix to output file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Read the rest of the input and write it to the temporary file */
	do {
		len = read(fd, buf, sizeof(buf));
		if (len < 0) {
			fprintf(stderr, "Failed to read input file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len < 1)
			break;
		len = write(tmpfd, buf, len);
		if (len < 0) {
			fprintf(stderr, "Failed to write output file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
	} while (len > 0);

	/* Reset the file descriptors to zero */
	pos = lseek(fd, 0, SEEK_SET);
	if (pos != 0) {
		fprintf(stderr, "Failed to reset task file position [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	pos = lseek(tmpfd, 0, SEEK_SET);
	if (pos != 0) {
		fprintf(stderr, "Failed to reset temporary file position [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Copy the data from the temporary file back to the original */
	do {
		len = read(tmpfd, buf, sizeof(buf));
		if (len < 0) {
			fprintf(stderr, "Failed to read temporary file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len < 1)
			break;
		len = write(fd, buf, len);
		if (len < 0) {
			fprintf(stderr, "Failed to write job file [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
	} while (len > 0);

	ret = fclose(tmp);
	if (ret != 0) {
		fprintf(stderr, "Failed to close temporary file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	return 0;
}
/**
 * @brief
 *      This is main function of pbs_upgrade_job process.
 */
int
main(int argc, char *argv[])
{
	DIR *dir;
	struct stat statbuf;
	struct dirent *dirent;
	char taskdir[MAXPATHLEN + 1] = {'\0'};
	char namebuf[MAXPATHLEN + 1] = {'\0'};
	char *jobfile = NULL;
	char *p;
	char *task_start;
	int fd = -1;
	int flags = 0;
	int err = 0;
	int check_flag = 0;
	int i;
	int ret;

	errno = 0;

	/* Print pbs_version and exit if --version specified */
	PRINT_VERSION_AND_EXIT(argc, argv);

	/* Parse the command line parameters */
	while (!err && ((i = getopt(argc, argv, "cf:")) != EOF)) {
		switch (i) {
			case 'c':
				check_flag = 1;
				break;
			case 'f':
				if (jobfile) {
					err = 1;
					break;
				}
				jobfile = optarg;
				break;
			default:
				err = 1;
				break;
		}
	}
	if (!jobfile)
		err = 1;
	if (err) {
		print_usage();
		return 1;
	}

	/* Ensure the tasks directory exists */
	snprintf(namebuf, sizeof(namebuf), "%s", jobfile);
	p = strrchr(namebuf, '.');
	if (!p) {
		fprintf(stderr, "Missing job file suffix");
		return 1;
	}
	if (strncmp(p, JOB_FILE_SUFFIX, strlen(JOB_FILE_SUFFIX)) != 0) {
		fprintf(stderr, "Invalid job file suffix");
		return 1;
	}
	strcpy(p, JOB_TASKDIR_SUFFIX);
	p += strlen(JOB_TASKDIR_SUFFIX);
	ret = stat(namebuf, &statbuf);
	if (ret < 0) {
		fprintf(stderr, "Failed to stat task directory %s [%s]\n",
				namebuf, errno ? strerror(errno) : "No error");
		return 1;
	}
	if (!S_ISDIR(statbuf.st_mode)) {
		fprintf(stderr, "Expected directory at %s", namebuf);
		return 1;
	}
	strncpy(taskdir, namebuf, sizeof(taskdir));
	strcat(p, "/");
	task_start = ++p;

	if (check_flag)
		flags = O_BINARY | O_RDONLY;
	else
		flags = O_BINARY | O_RDWR;

	/* Open the job file for reading */
	fd = open(jobfile, flags);
	if (fd < 0) {
		fprintf(stderr, "Failed to open %s [%s]\n", jobfile,
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Determine the format of the file */
	ret = check_job_file(fd);
	if (ret < 0) {
		fprintf(stderr, "Unknown job format: %s\n", jobfile);
		return 1;
	}
	if (check_flag) {
		printf("%d\n", ret);
		close(fd);
		return 0;
	}

	switch (ret) {
		case 18:
			/* this case will execute for all PBSPro >=13.x or <=18.x versions */
			break;
		case 19:
			/* no need to update the job sturcture */
			return 0;
		default:
			fprintf(stderr, "Unsupported version, job_name=%s\n", jobfile);
			return 1;
	}

	/* Upgrade the job file */
	ret = upgrade_job_file(fd);
	if (ret != 0) {
		fprintf(stderr, "Failed to upgrade the job file:%s\n", jobfile);
		return 1;
	}

	/* Close the job file */
	ret = close(fd);
	if (ret < 0) {
		fprintf(stderr, "Failed to close the job file [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Upgrade the task files */
	dir = opendir(taskdir);
	if (!dir) {
		fprintf(stderr, "Failed to open the task directory [%s]\n",
				errno ? strerror(errno) : "No error");
		return 1;
	}
	while (errno = 0, (dirent = readdir(dir)) != NULL) {
		if (errno != 0) {
			fprintf(stderr, "Failed to read directory [%s]\n",
					errno ? strerror(errno) : "No error");
			return 1;
		}
		if (dirent->d_name[0] == '.')
			continue;
		strcpy(task_start, dirent->d_name);
		ret = upgrade_task_file(namebuf);
		if (ret != 0) {
			fprintf(stderr, "Failed to upgrade the task file:%s\n",jobfile);
			return 1;
		}
	}
	closedir(dir);
	return 0;
}

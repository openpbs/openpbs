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

#define O_BINARY 0

/*
 * Define macros that controlled the size of the jobfix and taskfix structure (see job.h)
 * from 13.x to pre 19.x versions. Append the _PRE19 suffix to each.
 */

/* From pbs_ifl.h */
#define PBS_MAXSEQNUM_PRE19 7
#define PBS_MAXSVRJOBID_PRE19 (PBS_MAXSEQNUM_PRE19 - 1 + PBS_MAXSERVERNAME + PBS_MAXPORTNUM + 2)
#define PBS_MAXSVRJOBID_19_21 (PBS_MAXSEQNUM - 1 + PBS_MAXSERVERNAME + PBS_MAXPORTNUM + 2)

/*
 * Replicate the jobfix structure as it was defined in versions 19.x - 21.x
 */
typedef struct jobfix_19_21 {
	int ji_jsversion;   /* job structure version - JSVERSION */
	int ji_state;	    /* internal copy of state */
	int ji_substate;    /* job sub-state */
	int ji_svrflags;    /* server flags */
	int ji_numattr;	    /* not used */
	int ji_ordering;    /* special scheduling ordering */
	int ji_priority;    /* internal priority */
	time_t ji_stime;    /* time job started execution */
	time_t ji_endtBdry; /* estimate upper bound on end time */

	char ji_jobid[PBS_MAXSVRJOBID_19_21 + 1]; /* job identifier */
	char ji_fileprefix[PBS_JOBBASE + 1];	  /* no longer used */
	char ji_queue[PBS_MAXQUEUENAME + 1];	  /* name of current queue */
	char ji_destin[PBS_MAXROUTEDEST + 1];	  /* dest from qmove/route */
	/* MomS for execution    */

	int ji_un_type;				 /* type of ji_un union */
	union {					 /* depends on type of queue currently in */
		struct {			 /* if in execution queue .. */
			pbs_net_t ji_momaddr;	 /* host addr of Server */
			unsigned int ji_momport; /* port # */
			int ji_exitstat;	 /* job exit status from MOM */
		} ji_exect;
		struct {
			time_t ji_quetime;  /* time entered queue */
			time_t ji_rteretry; /* route retry time */
		} ji_routet;
		struct {
			int ji_fromsock;	  /* socket job coming over */
			pbs_net_t ji_fromaddr;	  /* host job coming from   */
			unsigned int ji_scriptsz; /* script size */
		} ji_newt;
		struct {
			pbs_net_t ji_svraddr; /* host addr of Server */
			int ji_exitstat;      /* job exit status from MOM */
			uid_t ji_exuid;	      /* execution uid */
			gid_t ji_exgid;	      /* execution gid */
		} ji_momt;
	} ji_un;
} jobfix_19_21;

union jobextend_19_21 {
	char fill[256]; /* fill to keep same size */
	struct {
#if defined(__sgi)
		jid_t ji_jid;
		ash_t ji_ash;
#else
		char ji_4jid[8];
		char ji_4ash[8];
#endif /* sgi */
		int ji_credtype;
#ifdef PBS_MOM
		tm_host_id ji_nodeidx; /* my node id */
		tm_task_id ji_taskidx; /* generate task id's for job */
#if MOM_ALPS
		long ji_reservation;
		/* ALPS reservation identifier */
		unsigned long long ji_pagg;
		/* ALPS process aggregate ID */
#endif /* MOM_ALPS */
#endif /* PBS_MOM */
	} ji_ext;
};

/*
 * Replicate the jobfix and taskfix structures as they were defined in 13.x to pre 19.x versions.
 * Use the macros defined above for convenience.
 */
typedef struct jobfix_PRE19 {
	int ji_jsversion;   /* job structure version - JSVERSION */
	int ji_state;	    /* internal copy of state */
	int ji_substate;    /* job sub-state */
	int ji_svrflags;    /* server flags */
	int ji_numattr;	    /* not used */
	int ji_ordering;    /* special scheduling ordering */
	int ji_priority;    /* internal priority */
	time_t ji_stime;    /* time job started execution */
	time_t ji_endtBdry; /* estimate upper bound on end time */

	char ji_jobid[PBS_MAXSVRJOBID_PRE19 + 1]; /* job identifier */
	char ji_fileprefix[PBS_JOBBASE + 1];	  /* no longer used */
	char ji_queue[PBS_MAXQUEUENAME + 1];	  /* name of current queue */
	char ji_destin[PBS_MAXROUTEDEST + 1];	  /* dest from qmove/route */
	/* MomS for execution    */

	int ji_un_type; /* type of ji_un union */
	union {		/* depends on type of queue currently in */
		struct
		{				 /* if in execution queue .. */
			pbs_net_t ji_momaddr;	 /* host addr of Server */
			unsigned int ji_momport; /* port # */
			int ji_exitstat;	 /* job exit status from MOM */
		} ji_exect;
		struct
		{
			time_t ji_quetime;  /* time entered queue */
			time_t ji_rteretry; /* route retry time */
		} ji_routet;
		struct
		{
			int ji_fromsock;	  /* socket job coming over */
			pbs_net_t ji_fromaddr;	  /* host job coming from   */
			unsigned int ji_scriptsz; /* script size */
		} ji_newt;
		struct
		{
			pbs_net_t ji_svraddr; /* host addr of Server */
			int ji_exitstat;      /* job exit status from MOM */
			uid_t ji_exuid;	      /* execution uid */
			gid_t ji_exgid;	      /* execution gid */
		} ji_momt;
	} ji_un;
} jobfix_PRE19;

typedef struct taskfix_PRE19 {
	char ti_parentjobid[PBS_MAXSVRJOBID_PRE19 + 1];
	tm_node_id ti_parentnode; /* parent vnode */
	tm_node_id ti_myvnode;	  /* my vnode */
	tm_task_id ti_parenttask; /* parent task */
	tm_task_id ti_task;	  /* task's taskid */
	int ti_status;		  /* status of task */
	pid_t ti_sid;		  /* session id */
	int ti_exitstat;	  /* exit status */
	union {
		int ti_hold[16]; /* reserved space */
	} ti_u;
} taskfix_PRE19;

/* Create a global buffer for reading and writing data. */
#define BUFSZ 4096
char buf[BUFSZ];

svrattrl *read_all_attrs_from_jbfile(int fd, char **state, char **substate, char **errbuf);

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

	/*---------- For PBS >=13.x or <=18.x versions jobfix structure ---------- */
	pos_new = lseek(fd, pos_saved, SEEK_SET);
	if (pos_new != 0) {
		fprintf(stderr, "Couldn't set the file position to zero [%s]\n",
			errno ? strerror(errno) : "No error");
		goto check_job_file_exit;
	}
	old_jobfix_pre19.ji_jsversion = 0;
	length = read(fd, (char *) &old_jobfix_pre19.ji_jsversion, sizeof(old_jobfix_pre19.ji_jsversion));
	if (length < 0) {
		fprintf(stderr, "Failed to read input file [%s]\n",
			errno ? strerror(errno) : "No error");
		goto check_job_file_exit;
	}
	if (old_jobfix_pre19.ji_jsversion == JSVERSION_18) {
		/* for all type of jobfix structures, from 13.x to 18.x PBS versions */
		ret_version = 18;
		goto check_job_file_exit;
	} else if (old_jobfix_pre19.ji_jsversion == JSVERSION_19) {
		/* if job has already updated structure */
		ret_version = 19;
		goto check_job_file_exit;
	} else if (old_jobfix_pre19.ji_jsversion == JSVERSION) {
		/* if job has already updated structure */
		ret_version = 21;
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
 * @brief	Upgrade pre 18.x jobfix structure to 19
 *
 * @param[in]	old_jobfix_pre19 - pre-19 jobfix struct
 *
 * @return	jobfix_19_21
 * @retval	v19 converted jobfix
 */
jobfix_19_21
convert_pre19jf_to_19(jobfix_PRE19 old_jobfix_pre19)
{
	jobfix_19_21 jf_19_21;

	/* Copy the data to the new jobfix structure */
	memset(&jf_19_21, 0, sizeof(jf_19_21));
	jf_19_21.ji_jsversion = JSVERSION_19;
	jf_19_21.ji_state = old_jobfix_pre19.ji_state;
	jf_19_21.ji_substate = old_jobfix_pre19.ji_substate;
	jf_19_21.ji_svrflags = old_jobfix_pre19.ji_svrflags;
	jf_19_21.ji_numattr = old_jobfix_pre19.ji_numattr;
	jf_19_21.ji_ordering = old_jobfix_pre19.ji_ordering;
	jf_19_21.ji_priority = old_jobfix_pre19.ji_priority;
	jf_19_21.ji_stime = old_jobfix_pre19.ji_stime;
	jf_19_21.ji_endtBdry = old_jobfix_pre19.ji_endtBdry;
	snprintf(jf_19_21.ji_jobid, sizeof(jf_19_21.ji_jobid),
		 "%s", old_jobfix_pre19.ji_jobid);
	snprintf(jf_19_21.ji_fileprefix, sizeof(jf_19_21.ji_fileprefix),
		 "%s", old_jobfix_pre19.ji_fileprefix);
	snprintf(jf_19_21.ji_queue, sizeof(jf_19_21.ji_queue),
		 "%s", old_jobfix_pre19.ji_queue);
	snprintf(jf_19_21.ji_destin, sizeof(jf_19_21.ji_destin),
		 "%s", old_jobfix_pre19.ji_destin);
	jf_19_21.ji_un_type = old_jobfix_pre19.ji_un_type;
	memcpy(&jf_19_21.ji_un, &old_jobfix_pre19.ji_un, sizeof(jf_19_21.ji_un));

	return jf_19_21;
}

/**
 * @brief	Upgrade 19-21 jobfix structure to latest
 *
 * @param[in]	old_jf - 19-21 jobfix struct
 *
 * @return	jobfix_19_21
 * @retval	converted jobfix
 */
struct jobfix
convert_19jf_to_22(jobfix_19_21 old_jf)
{
	struct jobfix jf;

	memset(&jf, 0, sizeof(jf));
	jf.ji_jsversion = JSVERSION;
	jf.ji_svrflags = old_jf.ji_svrflags;
	jf.ji_stime = old_jf.ji_stime;
	snprintf(jf.ji_jobid, sizeof(jf.ji_jobid), "%s", old_jf.ji_jobid);
	snprintf(jf.ji_fileprefix, sizeof(jf.ji_fileprefix), "%s", old_jf.ji_fileprefix);
	snprintf(jf.ji_queue, sizeof(jf.ji_queue), "%s", old_jf.ji_queue);
	snprintf(jf.ji_destin, sizeof(jf.ji_destin), "%s", old_jf.ji_destin);
	jf.ji_un_type = old_jf.ji_un_type;
	memcpy(&jf.ji_un, &old_jf.ji_un, sizeof(jf.ji_un));

	return jf;
}

/**
 * @brief	Upgrade 19-21 jobextend structure to latest
 *
 * @param[in]	old_extend - 19-21 jobextend struct
 *
 * @return	jobextend
 * @retval	converted jobextend
 */
union jobextend
convert_19ext_to_22(union jobextend_19_21 old_extend)
{
	union jobextend je;

	memset(&je, 0, sizeof(je));
	snprintf(je.fill, sizeof(je.fill), "%s", old_extend.fill);
#if !defined(__sgi)
	snprintf(je.ji_ext.ji_jid, sizeof(je.ji_ext.ji_jid), "%s", old_extend.ji_ext.ji_4jid);
#endif
	je.ji_ext.ji_credtype = old_extend.ji_ext.ji_credtype;
#ifdef PBS_MOM
	je.ji_ext.ji_nodeidx = old_extend.ji_ext.ji_nodeidx;
	je.ji_ext.ji_taskidx = old_extend.ji_ext.ji_taskidx;
#if MOM_ALPS
	je.ji_ext.ji_reservation = old_extend.ji_ext.ji_reservation;
	je.ji_ext.ji_pagg = old_extend.ji_ext.ji_pagg;
#endif
#endif

	return je;
}

/**
 * @brief
 *		Upgrade a job file from an earlier version.
 *
 * @param[in]	fd		-	File descriptor from which to read
 * @param[in]	ver		-	Old version
 *
 * @return	int
 * @retval	1	: failure
 * @retval	 0	: success
 */
int
upgrade_job_file(int fd, int ver)
{
	FILE *tmp = NULL;
	int tmpfd = -1;
	jobfix_19_21 qs_19_21;
	jobfix_PRE19 old_jobfix_pre19;
	union jobextend_19_21 old_ji_extended;
	int ret;
	off_t pos;
	job new_job;
	errno = 0;
	int len;
	svrattrl *pal = NULL;
	char statechar;
	svrattrl *pali;
	svrattrl dummy;
	char statebuf[2];
	char ssbuf[5];
	char *charstrm;

	/* The following code has been modeled after job_recov_fs() */

	if (ver == 18) {
		/* Read in the pre19 jobfix structure */
		memset(&old_jobfix_pre19, 0, sizeof(old_jobfix_pre19));
		len = read(fd, (char *) &old_jobfix_pre19, sizeof(old_jobfix_pre19));
		if (len < 0) {
			fprintf(stderr, "Failed to read input file [%s]\n",
				errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len != sizeof(old_jobfix_pre19)) {
			fprintf(stderr, "Format not recognized, not enough fixed data.\n");
			return 1;
		}

		qs_19_21 = convert_pre19jf_to_19(old_jobfix_pre19);
	} else {
		/* Read in the 19_21 jobfix structure */
		memset(&qs_19_21, 0, sizeof(qs_19_21));
		len = read(fd, (char *) &qs_19_21, sizeof(qs_19_21));
		if (len < 0) {
			fprintf(stderr, "Failed to read input file [%s]\n",
				errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len != sizeof(qs_19_21)) {
			fprintf(stderr, "Format not recognized, not enough fixed data.\n");
			return 1;
		}
	}
	memset(&new_job, 0, sizeof(new_job));
	new_job.ji_qs = convert_19jf_to_22(qs_19_21);

	/* Convert old extended data to new */
	memset(&old_ji_extended, 0, sizeof(old_ji_extended));
	len = read(fd, (char *) &old_ji_extended, sizeof(union jobextend_19_21));
	if (len < 0) {
		fprintf(stderr, "Failed to read input file [%s]\n", errno ? strerror(errno) : "No error");
		return 1;
	}
	if (len != sizeof(union jobextend_19_21)) {
		fprintf(stderr, "Format not recognized, not enough extended data.\n");
		return 1;
	}
	new_job.ji_extended = convert_19ext_to_22(old_ji_extended);

	/* previous versions may not have updated values of state and substate in the attribute list
	 * since we now rely on these attributes instead of the quick save area, it's important
	 * to make sure that state and substate attributes are set correctly */
	statechar = state_int2char(qs_19_21.ji_state);
	if (statechar != JOB_STATE_LTR_UNKNOWN) {
		bool stateset = false;
		bool substateset = false;
		char *errbuf = malloc(1024);

		if (errbuf == NULL) {
			fprintf(stderr, "Malloc error\n");
			return 1;
		}
		snprintf(statebuf, sizeof(statebuf), "%c", statechar);
		snprintf(ssbuf, sizeof(ssbuf), "%d", qs_19_21.ji_substate);
		pal = read_all_attrs_from_jbfile(fd, NULL, NULL, &errbuf);
		if (pal == NULL && errbuf[0] != '\0') {
			fprintf(stderr, "%s\n", errbuf);
			return 1;
		}
		pali = pal;
		while (pali != NULL) {
			if (strcmp(pali->al_name, ATTR_state) == 0) {
				pali->al_valln = strlen(statebuf) + 1;
				pali->al_value = pali->al_name + pali->al_nameln + pali->al_rescln;
				strcpy(pali->al_value, statebuf);
				pali->al_tsize = sizeof(svrattrl) + pali->al_nameln + pali->al_valln;
				stateset = true;
				if (substateset)
					break;
			} else if (strcmp(pali->al_name, ATTR_substate) == 0) {
				pali->al_valln = strlen(ssbuf) + 1;
				pali->al_value = pali->al_name + pali->al_nameln + pali->al_rescln;
				strcpy(pali->al_value, ssbuf);
				pali->al_tsize = sizeof(svrattrl) + pali->al_nameln + pali->al_valln;
				substateset = true;
				if (stateset)
					break;
			}
			if (pali->al_link.ll_next == NULL)
				break;
			pali = GET_NEXT(pali->al_link);
		}
	}

	/* Open a temporary file to stage data */
	tmp = tmpfile();
	if (!tmp) {
		fprintf(stderr, "Failed to open temporary file [%s]\n", errno ? strerror(errno) : "No error");
		return 1;
	}
	tmpfd = fileno(tmp);
	if (tmpfd < 0) {
		fprintf(stderr, "Failed to find temporary file descriptor [%s]\n", errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Write the new jobfix structure to the output file */
	len = write(tmpfd, &new_job.ji_qs, sizeof(new_job.ji_qs));
	if (len != sizeof(new_job.ji_qs)) {
		fprintf(stderr, "Failed to write jobfix to output file [%s]\n", errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Write the new extend structure to the output file */
	len = write(tmpfd, &new_job.ji_extended, sizeof(new_job.ji_extended));
	if (len != sizeof(new_job.ji_extended)) {
		fprintf(stderr, "Failed to write job extend data to output file [%s]\n",
			errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Write the job attribute list to the output file */
	pali = pal;
	while (pali != NULL) { /* Modeled after save_struct() */
		int copysize;
		int objsize;

		objsize = pali->al_tsize;
		charstrm = (char *) pali;
		while (objsize > 0) {
			if (objsize > BUFSZ)
				copysize = BUFSZ;
			else
				copysize = objsize;
			memcpy(buf, charstrm, copysize);
			len = write(tmpfd, buf, copysize);
			if (len < 0) {
				fprintf(stderr, "Failed to write output file [%s]\n", errno ? strerror(errno) : "No error");
				return 1;
			}
			objsize -= len;
			charstrm += len;
		}
		if (pali->al_link.ll_next == NULL)
			break;
		pali = GET_NEXT(pali->al_link);
	}

	/* Write a dummy attribute to indicate the end of attribute list, refer to save_attr_fs */
	dummy.al_tsize = ENDATTRIBUTES;
	charstrm = (char *) &dummy;
	memcpy(buf, charstrm, sizeof(dummy));
	len = write(tmpfd, buf, sizeof(dummy));
	if (len < 0) {
		fprintf(stderr, "Failed to write dummy to output file [%s]\n", errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Read the rest of the input and write it to the temporary file */
	do {
		len = read(fd, buf, BUFSZ);
		if (len < 0) {
			fprintf(stderr, "Failed to read input file [%s]\n", errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len < 1)
			break;
		len = write(tmpfd, buf, len);
		if (len < 0) {
			fprintf(stderr, "Failed to write output file [%s]\n", errno ? strerror(errno) : "No error");
			return 1;
		}
	} while (len > 0);

	/* Reset the file descriptors to zero */
	pos = lseek(fd, 0, SEEK_SET);
	if (pos != 0) {
		fprintf(stderr, "Failed to reset job file position [%s]\n", errno ? strerror(errno) : "No error");
		return 1;
	}
	pos = lseek(tmpfd, 0, SEEK_SET);
	if (pos != 0) {
		fprintf(stderr, "Failed to reset temporary file position [%s]\n",
			errno ? strerror(errno) : "No error");
		return 1;
	}

	/* truncate the original file before writing new contents */
	if (ftruncate(fd, 0) != 0) {
		fprintf(stderr, "Failed to truncate the job file [%s]\n",
			errno ? strerror(errno) : "No error");
		return 1;
	}

	/* Copy the data from the temporary file back to the original */
	do {
		len = read(tmpfd, buf, BUFSZ);
		if (len < 0) {
			fprintf(stderr, "Failed to read temporary file [%s]\n", errno ? strerror(errno) : "No error");
			return 1;
		}
		if (len < 1)
			break;
		len = write(fd, buf, len);
		if (len < 0) {
			fprintf(stderr, "Failed to write job file [%s]\n", errno ? strerror(errno) : "No error");
			return 1;
		}
	} while (len > 0);

	ret = fclose(tmp);
	if (ret != 0) {
		fprintf(stderr, "Failed to close temporary file [%s]\n", errno ? strerror(errno) : "No error");
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
	len = read(fd, (char *) &old_taskfix_pre19, sizeof(old_taskfix_pre19));
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
			/* this case will execute for all PBS >=13.x or <=18.x versions */
		case 19:
			/* this case will execute for all PBS >=19.x or <=21.x versions */
			break;
		case 21:
			/* no need to update the job sturcture */
			return 0;
		default:
			fprintf(stderr, "Unsupported version, job_name=%s\n", jobfile);
			return 1;
	}

	/* Upgrade the job file */
	ret = upgrade_job_file(fd, ret);
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
	errno = 0;
	while ((dirent = readdir(dir)) != NULL) {
		if (errno != 0) {
			fprintf(stderr, "Failed to read directory [%s]\n",
				errno ? strerror(errno) : "No error");
			closedir(dir);
			return 1;
		}
		if (dirent->d_name[0] == '.')
			continue;
		strcpy(task_start, dirent->d_name);
		ret = upgrade_task_file(namebuf);
		if (ret != 0) {
			fprintf(stderr, "Failed to upgrade the task file:%s\n", jobfile);
			closedir(dir);
			return 1;
		}
	}
	closedir(dir);
	return 0;
}

/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

#ifndef	_LOG_H
#define	_LOG_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdio.h>
#if SYSLOG
#include <syslog.h>
#else
/* normally found in syslog.h, need to be defined for calls, but */
/* will be ingnored in pbs_log.c				 */
#define	LOG_EMERG	0
#define	LOG_ALERT	1
#define	LOG_CRIT	2
#define	LOG_ERR		3
#define	LOG_WARNING	4
#define	LOG_NOTICE	5
#define	LOG_INFO	6
#define	LOG_DEBUG	7
#define	LOG_AUTH	8
#endif	/* SYSLOG */

#include <sys/stat.h>

/*
 * include file for error/event logging
 */

/*
 * The default log buffer size should be large enough to hold a short message
 * together with the full pathname of a file. A full pathname may be up to 4096
 * characters. Add to this an extra 256 characters. This helps to avoid format
 * truncation warnings from certain compilers.
 */
#define LOG_BUF_SIZE 4352

/* The following macro assist in sharing code between the Server and Mom */
#define LOG_EVENT log_event

/*
 ** Set up a debug print macro.
 */
#define	sys_printf(...)	syslog(LOG_NOTICE, __VA_ARGS__);
#ifdef	DEBUG
#define	DBPRT(x)	printf x;
#else
#define	DBPRT(x)
#endif

#define IFNAME_MAX 256
#define IFFAMILY_MAX 16

struct log_net_info { /* interface info for logging */
	struct log_net_info *next;
	char ifname[IFNAME_MAX];
	char iffamily[IFFAMILY_MAX];
	char **ifhostnames;
};

extern char *msg_daemonname;

extern long *log_event_mask;

extern void set_logfile(FILE *fp);
extern int set_msgdaemonname(char *ch);
void set_log_conf(char *leafname, char *nodename,
		  unsigned int islocallog, unsigned int sl_fac, unsigned int sl_svr,
		  unsigned int log_highres);
extern void *log_get_tls_data(void);

extern struct log_net_info *get_if_info(char *msg);
extern void free_if_info(struct log_net_info *ni);

extern void log_close(int close_msg);
extern void log_err(int err, const char *func, const char *text);
extern void log_errf(int errnum, const char *routine, const char *fmt, ...);
extern void log_joberr(int err, const char *func, const char *text, const char *pjid);
extern void log_event(int type, int objclass, int severity, const char *objname, const char *text);
extern void log_eventf(int eventtype, int objclass, int sev, const char *objname, const char *fmt, ...);
extern int will_log_event(int type);
extern void log_suspect_file(const char *func, const char *text, const char *file, struct stat *sb);
extern int  log_open(char *name, char *directory);
extern int  log_open_main(char *name, char *directory, int silent);
extern void log_record(int type, int objclass, int severity, const char *objname, const char *text);
extern char log_buffer[LOG_BUF_SIZE];
extern int log_level_2_etype(int level);

extern int  chk_path_sec(char *path, int dir, int sticky, int bad, int);
extern int  chk_file_sec(char *path, int isdir, int sticky, int disallow, int fullpath);
extern int  chk_file_sec_user(char *path, int isdir, int sticky, int disallow, int fullpath, int uid);
extern int  tmp_file_sec(char *path, int isdir, int sticky, int disallow, int fullpath);
extern int  tmp_file_sec_user(char *path, int isdir, int sticky, int disallow, int fullpath, int uid);

#ifdef WIN32
extern int  chk_file_sec2(char *path, int isdir, int sticky,
	int disallow, int fullpath, char *owner);
#endif
extern char *get_script_name(char *input);

extern int  setup_env(char *filename);
extern void log_supported_auth_methods(char **supported_auth_methods);

/* Event types */

#define PBSEVENT_ERROR		0x0001		/* internal errors */
#define PBSEVENT_SYSTEM		0x0002		/* system (server) events */
#define PBSEVENT_ADMIN		0x0004		/* admin events */
#define PBSEVENT_JOB		0x0008		/* job related events */
#define PBSEVENT_JOB_USAGE	0x0010		/* End of Job accounting */
#define PBSEVENT_SECURITY	0x0020		/* security violation events */
#define PBSEVENT_SCHED		0x0040		/* scheduler events */
#define PBSEVENT_DEBUG		0x0080		/* common debug messages */
#define PBSEVENT_DEBUG2		0x0100		/* less needed debug messages */
#define PBSEVENT_RESV		0x0200		/* reservation related msgs */
#define PBSEVENT_DEBUG3		0x0400		/* less needed debug messages */
#define PBSEVENT_DEBUG4		0x0800		/* rarely needed debugging */
#define PBSEVENT_FORCE		0x8000		/* set to force a message */
#define SVR_LOG_DFLT		PBSEVENT_ERROR | PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_JOB \
				| PBSEVENT_JOB_USAGE | PBSEVENT_SECURITY | PBSEVENT_SCHED \
				| PBSEVENT_DEBUG | PBSEVENT_DEBUG2
#define SCHED_LOG_DFLT		PBSEVENT_ERROR | PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_JOB | PBSEVENT_JOB_USAGE \
				| PBSEVENT_SECURITY | PBSEVENT_SCHED | PBSEVENT_DEBUG | PBSEVENT_RESV

/* Event Object Classes, see array class_names[] in ../lib/Liblog/pbs_log.c */

#define PBS_EVENTCLASS_SERVER	1	/* The server itself */
#define PBS_EVENTCLASS_QUEUE	2	/* Queues */
#define PBS_EVENTCLASS_JOB	3	/* Jobs	 */
#define PBS_EVENTCLASS_REQUEST	4	/* Batch Requests */
#define PBS_EVENTCLASS_FILE	5	/* A Job related File */
#define PBS_EVENTCLASS_ACCT	6	/* Accounting info */
#define PBS_EVENTCLASS_NODE	7	/* Nodes */
#define PBS_EVENTCLASS_RESV	8	/* Reservations */
#define PBS_EVENTCLASS_SCHED	9	/* Scheduler */
#define PBS_EVENTCLASS_HOOK	10	/* Hook	 */
#define PBS_EVENTCLASS_RESC	11	/* Resource */
#define PBS_EVENTCLASS_TPP 	12	/* TPP */

/* Logging Masks */

#define PBSEVENT_MASK	0x01ff

#ifdef __cplusplus
}
#endif


#endif /* _LOG_H */
